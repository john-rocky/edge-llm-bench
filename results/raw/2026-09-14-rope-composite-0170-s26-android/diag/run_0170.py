#!/usr/bin/env python3
"""Does the odml.rope word-order defect seen on the LiteRT-LM v0.16.0 Android GPU path (2026-09-13/14,
Pixel 8a + Galaxy S26) still show on the v0.17.0 Android GPU path?  Galaxy S26 (RFGL80R6A6H), under a
device hold owned by THIS pid (hold_cli.py), one engine process at a time, thermal-gated, short-chat
("Explain what on-device AI means in simple terms."), 1 run per cell, engine-default sampling, thinking
as the bundle declares it.

Two witnesses for 0.17.0:
  cli — the OSS v0.17.0 litert_lm_main (android_arm64 source build at the tag; android/bin/v0.17.0,
        pins entry), pushed into /data/local/tmp/llmbench for the sitting and pushed back to v0.16.0
        afterwards — both directions sha256-verified against android/engine-pins.json.
  apk — the litertlm-android 0.17.0 AAR through android/ddp-bench (Route B instrumentation APK,
        run_local.sh --no-build --no-gate --runs 1).

Every bundle is pushed under a fresh litert-local id (…-e0170) so the v0.17.0 runtime never reads or
overwrites the ML Drift / XNNPACK caches the v0.16.0 lane keeps beside its own copies (the cache key is
name + size, not engine version); each copy and its caches are removed after its cell.

Records land in this diag/ dir (outside app-path-android/, so build_summary.py never counts them —
these are 1-run correctness cells, not catalog rows). The APK records are moved here too (apk/<backend>/).

Usage:
  python3 run_0170.py all                        # the whole sitting (below)
  python3 run_0170.py swap v0.17.0|v0.16.0       # engine swap only (sha-verified)
  python3 run_0170.py cli gpu|cpu <id>:<local .litertlm> [...]
  python3 run_0170.py apk gpu|cpu <local .litertlm>
"""
import glob
import json
import os
import shutil
import subprocess
import sys
import time

ROOT = "/Users/majimadaisuke/code/edge-llm-bench"
sys.path.insert(0, os.path.join(ROOT, "android", "bench"))
from device_probe import thermal_status  # noqa: E402

SERIAL = "RFGL80R6A6H"
HOLD_CLI = os.path.expanduser("~/code/litertlm-convert/community_accel_work/hold_cli.py")
HOLD = os.path.expanduser("~/code/litertlm-convert/community_accel_work/s2_npu_sweep/.device_hold.s26")
OUT = os.path.dirname(os.path.abspath(__file__))
CAMPAIGN = os.path.basename(os.path.dirname(OUT))
DEV_DIR = "/data/local/tmp/llmbench"
APK_DEV_DIR = "/data/local/tmp/edge-llm-bench"
PINS = json.load(open(os.path.join(ROOT, "android", "engine-pins.json")))["litert-lm"]

CONV = os.path.expanduser("~/code/litertlm-convert/qwen3_gpuopt_work/out")
# The snapshot SYMLINK path, never its realpath: the on-device name is built from the basename, and
# 0.17.0 decides the bundle format by the path extension — the blob-hash name (no .litertlm) fails
# engine creation (attempt 1 of this sitting, driver.attempt1.log).
PUB = os.path.expanduser(
    "~/.cache/huggingface/hub/models--litert-community--Qwen3-1.7B/snapshots/"
    "73fbc3fe8271c162a603ee66f6e7ed25b6211195/Qwen3-1.7B_dynamic_wi4b32_afp32.litertlm")
CELLS = [  # (backend, model_id, local path) — the published GPU build first (the verdict), then its CPU control
    ("gpu", "litert-local/Qwen3-1.7B-pub-wi4b32-e0170", PUB),
    ("cpu", "litert-local/Qwen3-1.7B-pub-wi4b32-e0170", PUB),
    ("gpu", "litert-local/Qwen3-1.7B-wi4b32-gpuflags-e0170", f"{CONV}/dtypeonly_1p7b/wi4b32/Qwen3-1.7B_wi4b32_gpuflags.litertlm"),
    ("gpu", "litert-local/Qwen3-1.7B-wi8-gpuflags-e0170", f"{CONV}/dtypeonly_1p7b/wi8/Qwen3-1.7B_wi8_gpuflags.litertlm"),
    ("gpu", "litert-local/Qwen3-1.7B-wi4b32-gpuflags-norope-e0170", f"{CONV}/dtypeonly_1p7b_norope/wi4b32/Qwen3-1.7B_wi4b32_gpuflags_norope.litertlm"),
    ("gpu", "litert-local/Qwen3-1.7B-wi8-gpuflags-norope-e0170", f"{CONV}/dtypeonly_1p7b_norope/wi8/Qwen3-1.7B_wi8_gpuflags_norope.litertlm"),
]


for _b, _m, _p in CELLS:
    assert _p.endswith(".litertlm") and os.path.exists(_p), _p


def log(msg):
    print(time.strftime("[%F %T] ") + msg, flush=True)


def sh(cmd, timeout=600):
    return subprocess.run(["adb", "-s", SERIAL, "shell", cmd], capture_output=True, text=True,
                          timeout=timeout).stdout


def wait_nominal():
    while True:
        raw, name = thermal_status(SERIAL)
        if raw == 0:
            return
        log(f"thermal gate: status={name} — waiting 60 s")
        time.sleep(60)


def freq_line():
    v = sh("cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq "
           "/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq").split()
    return f"cpu0 scaling_max_freq/cpuinfo_max_freq = {v}"


def swap(tag):
    """Push android/bin/<tag>/litert_lm_main + its .so set into DEV_DIR and verify every sha256 against the pins."""
    d = os.path.join(ROOT, "android", "bin", tag)
    want = {"litert_lm_main": PINS[tag]["litert_lm_main_sha256"], **PINS[tag]["so_files"]}
    sh(f"chmod 755 {DEV_DIR}/litert_lm_main {DEV_DIR}/*.so")  # the v0.16.0 binary sits at 0555
    for f in want:
        subprocess.run(["adb", "-s", SERIAL, "push", os.path.join(d, f), f"{DEV_DIR}/{f}"],
                       check=True, capture_output=True, timeout=600)
    sh(f"chmod 755 {DEV_DIR}/litert_lm_main {DEV_DIR}/*.so")
    out = sh(f"cd {DEV_DIR} && sha256sum " + " ".join(want))
    got = {l.split()[1]: l.split()[0] for l in out.splitlines() if len(l.split()) == 2}
    bad = {k: (got.get(k), v) for k, v in want.items() if got.get(k) != v}
    if bad:
        log(f"SWAP VERIFY FAILED for {tag}: {bad}")
        sys.exit(4)
    log(f"engine on device = {tag}: litert_lm_main + {len(want) - 1} .so, every sha256 matches android/engine-pins.json")


def show_text(logfile):
    txt = open(logfile, errors="replace").read()
    i = txt.find("===ENGINE_OUTPUT===")
    body = txt[i + len("===ENGINE_OUTPUT==="):] if i >= 0 else txt
    j = body.find("</think>")
    head = body[:500].replace("\n", " | ")
    ans = body[j:j + 700].replace("\n", " | ") if j >= 0 else "(no </think> in the output)"
    log(f"engine output head: {head}")
    log(f"after </think>: {ans}")


def cli_cell(backend, model_id, path):
    wait_nominal()
    log(freq_line())
    cmd = [sys.executable, os.path.join(ROOT, "android", "bench", "run_cell.py"),
           "--runtime", "litert-lm", "--backend", backend, "--model-id", model_id,
           "--file", path, "--task", "short-chat", "--runs", "1", "--out", OUT,
           "--serial", SERIAL, "--timeout", "1800"]
    env = dict(os.environ, BENCH_ANDROID_SERIAL=SERIAL, BENCH_CPU_MASK="", PYTHONUNBUFFERED="1")
    log("$ " + " ".join(cmd))
    rc = subprocess.run(cmd, env=env, cwd=ROOT).returncode
    log(f"exit {rc}")
    logs = glob.glob(os.path.join(OUT, f"litert-lm-{backend}_{model_id.replace('/', '_')}_short-chat_*_run1.log"))
    if logs:
        show_text(max(logs, key=os.path.getmtime))
    return rc


def drop_cli_copy(model_id, path):
    dev = f"{DEV_DIR}/models/{model_id.replace('/', '_')}_{os.path.basename(path)}"
    sh(f"rm -f {dev}* {DEV_DIR}/markers/{os.path.basename(dev)}.*.cachebuilt")
    log(f"removed {dev}* (+ its caches and markers)")


def apk_cell(backend, path):
    wait_nominal()
    log(freq_line())
    camp = f"{CAMPAIGN}-apk-{backend}-tmp"
    cmd = [os.path.join(ROOT, "android", "ddp-bench", "run_local.sh"), "--serial", SERIAL, "--no-build",
           "--no-gate", "--runs", "1", "--backend", backend, "--model", path, "--campaign", camp,
           "--token-file", "/dev/null",
           # model_path wins over the download (LitertlmBenchTest.kt:94); --repo/--file only label the record
           # (without them the record says the default gemma-3-270m-it id next to the Qwen3 sha — first APK
           # pass of this sitting, kept under attempt1/apk_mislabeled/)
           "--repo", "litert-community/Qwen3-1.7B", "--file", os.path.basename(path)]
    log("$ " + " ".join(cmd))
    rc = subprocess.run(cmd, cwd=ROOT).returncode
    log(f"exit {rc}")
    src = os.path.join(ROOT, "results", "raw", camp, "app-path-android")
    dst = os.path.join(OUT, "apk", backend)
    os.makedirs(dst, exist_ok=True)
    if os.path.isdir(src):
        for f in os.listdir(src):
            shutil.move(os.path.join(src, f), os.path.join(dst, f))
        shutil.rmtree(os.path.join(ROOT, "results", "raw", camp))
        log(f"records moved to {dst} (out of any app-path* dir)")
    sh(f"rm -f {APK_DEV_DIR}/{os.path.basename(path)}*")
    sh(f"rm -rf /sdcard/Android/data/io.github.johnrocky.edgellmbench/files/edge-llm-bench/{camp}")
    log(f"removed {APK_DEV_DIR}/{os.path.basename(path)}* and the app's records for {camp}")
    for lg in glob.glob(os.path.join(dst, "*_run1.log")):
        show_text(lg)
    return rc


def main():
    mode = sys.argv[1]
    rc = subprocess.run([sys.executable, HOLD_CLI, "acquire", HOLD, "edge-llm-bench diag run_0170.py",
                         str(os.getpid())], capture_output=True, text=True)
    if rc.returncode != 0:
        log("hold refused: " + rc.stdout + rc.stderr)
        sys.exit(3)
    log(f"hold taken ({HOLD}, pid {os.getpid()})")
    swapped = False
    try:
        if mode == "swap":
            swap(sys.argv[2])
        elif mode == "cli":
            backend = sys.argv[2]
            for v in sys.argv[3:]:
                mid, p = v.split(":", 1)
                cli_cell(backend, mid, p)
                drop_cli_copy(mid, p)
        elif mode == "apk":
            apk_cell(sys.argv[2], sys.argv[3])
        elif mode == "all":
            log(f"device: {sh('getprop ro.product.model').strip()} {sh('getprop ro.build.version.release').strip()} "
                f"uptime {sh('cat /proc/uptime').split()[0]} s; free: {sh('df -h /data | tail -1').strip()}")
            swap("v0.17.0")
            swapped = True
            for backend, mid, p in CELLS:
                cli_cell(backend, mid, p)
                drop_cli_copy(mid, p)
            swap("v0.16.0")
            swapped = False
            apk_cell("gpu", PUB)
            apk_cell("cpu", PUB)
        else:
            raise SystemExit(__doc__)
    finally:
        if swapped:
            log("restoring v0.16.0 after an error")
            swap("v0.16.0")
        subprocess.run([sys.executable, HOLD_CLI, "release", HOLD, str(os.getpid())])
        log("hold released")


if __name__ == "__main__":
    main()
