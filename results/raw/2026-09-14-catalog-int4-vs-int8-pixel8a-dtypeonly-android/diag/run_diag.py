#!/usr/bin/env python3
"""Diagnostics on the Pixel 8a for the 2026-09-14 dtype-only pair, run under the sibling lane's
device hold with THIS process's pid (hold_cli.py), one engine process at a time, thermal-gated:

  1. the int8 GPU-graph bundle on the CPU backend (short-chat, 1 run) — does the graph itself
     answer on this runtime (v0.16.0) when the GPU delegate is out of the picture?
  2. the one-flag-dropped int8 variants (export_int8_bisect.sh) on the GPU backend, 1 run each —
     which flag turns the 5-token collapse off?

Records land in this diag/ dir (outside app-path-android/, so build_summary.py never counts
them); the console log of each run carries the generated text. Usage:
  python3 run_diag.py cpu                      # step 1
  python3 run_diag.py gpu <variant> [...]      # step 2, variants = bisect dir names
"""
import os, subprocess, sys, time
ROOT = "/Users/majimadaisuke/code/edge-llm-bench"
sys.path.insert(0, os.path.join(ROOT, "android", "bench"))
from device_probe import thermal_status  # noqa: E402

SERIAL = "4C131JEKB15210"
HOLD_CLI = os.path.expanduser("~/code/litertlm-convert/community_accel_work/hold_cli.py")
HOLD = os.path.expanduser("~/code/litertlm-convert/community_accel_work/s2_npu_sweep/.device_hold.pixel8a")
OUT = os.path.dirname(os.path.abspath(__file__))
BISECT = os.path.expanduser("~/code/litertlm-convert/qwen3_gpuopt_work/out/dtypeonly_1p7b/bisect")
PAIR8 = os.path.expanduser("~/code/litertlm-convert/qwen3_gpuopt_work/out/dtypeonly_1p7b/wi8/Qwen3-1.7B_wi8_gpuflags.litertlm")


def log(msg):
    print(time.strftime("[%F %T] ") + msg, flush=True)


def wait_nominal():
    while True:
        raw, name = thermal_status(SERIAL)
        if raw == 0:
            return
        log(f"thermal gate: status={name} — waiting 60 s")
        time.sleep(60)


DEV_DIR = "/data/local/tmp/llmbench"


def adb_rm(pattern):
    subprocess.run(["adb", "-s", SERIAL, "shell", f"rm -f {pattern}"])


def cell(backend, model_id, path, cooldown=60, drop_after=False):
    wait_nominal()
    cmd = [sys.executable, os.path.join(ROOT, "android", "bench", "run_cell.py"),
           "--runtime", "litert-lm", "--backend", backend, "--model-id", model_id,
           "--file", path, "--task", "short-chat", "--runs", "1", "--out", OUT,
           "--serial", SERIAL, "--timeout", "1800"]
    env = dict(os.environ, BENCH_ANDROID_SERIAL=SERIAL, BENCH_CPU_MASK="f0", PYTHONUNBUFFERED="1")
    log("$ " + " ".join(cmd))
    rc = subprocess.run(cmd, env=env, cwd=ROOT).returncode
    log(f"exit {rc}")
    if drop_after:  # a 1.7 GB variant + its ML Drift caches; the phone has ~3 GB free
        dev = f"{DEV_DIR}/models/{model_id.replace('/', '_')}_{os.path.basename(path)}"
        adb_rm(dev + "*")
        log(f"removed {dev}*")
    time.sleep(cooldown)
    return rc


def main():
    mode = sys.argv[1]
    rc = subprocess.run([sys.executable, HOLD_CLI, "acquire", HOLD, "edge-llm-bench diag run_diag.py",
                         str(os.getpid())], capture_output=True, text=True)
    if rc.returncode != 0:
        log("hold refused: " + rc.stdout + rc.stderr)
        sys.exit(3)
    log("hold taken")
    try:
        if mode == "cpu":
            cell("cpu", "litert-local/Qwen3-1.7B-wi8-gpuflags", PAIR8, drop_after=True)
        elif mode == "gpu":
            for v in sys.argv[2:]:
                # a bisect dir name, or name:/abs/path for any other bundle (e.g. the re-exported pair)
                if ":" in v:
                    v, p = v.split(":", 1)
                else:
                    p = os.path.join(BISECT, v, f"Qwen3-1.7B_wi8_{v}.litertlm")
                if not os.path.exists(p):
                    log(f"missing {p}"); continue
                cell("gpu", f"litert-local/Qwen3-1.7B-{v}", p, drop_after=True)
    finally:
        subprocess.run([sys.executable, HOLD_CLI, "release", HOLD, str(os.getpid())])
        log("hold released")


if __name__ == "__main__":
    main()
