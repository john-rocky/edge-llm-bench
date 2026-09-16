#!/usr/bin/env python3
"""Which half of the LiteRT-LM v0.16.0 -> v0.17.0 change fixed the odml.rope off-prompt answer on the Android GPU
path: the source-built CLI (LiteRT-LM + the LiteRT it vendors) or the prebuilt GPU accelerator .so set
(prebuilt/android_arm64/, Git LFS, loaded by dlopen at run time)?  Galaxy S26 (RFGL80R6A6H), one engine process at
a time under the owned device hold, thermal-gated, short-chat ("Explain what on-device AI means in simple terms."),
1 run per cell, engine-default sampling, the published litert-community/Qwen3-1.7B GPU build
(Qwen3-1.7B_dynamic_wi4b32_afp32.litertlm, odml.rope x55) — the same file, prompt and harness as the
2026-09-14 sitting (results/raw/2026-09-14-rope-composite-0170-s26-android).

Cells = (cli tag, .so set). The CLI comes from android/bin/<tag>/ (sha256 in android/engine-pins.json); a .so set
is the 7 files of prebuilt/android_arm64/ at one LiteRT-LM commit: the v0.16.0 tag, 96b4819c (08-07), 3dc788a4
(08-25), the v0.17.0 tag (= a2491105, 08-27). The two intermediate sets were materialised from Git LFS
(git cat-file | git lfs smudge) and sha256-checked against their pointers. Every push is sha256-verified on the
device against the local file before the cell runs. Each bundle copy gets a fresh litert-local id so no ML Drift /
XNNPACK cache is shared between cells (cache key = name + size). The device is put back to the full v0.16.0 set
at the end (its standing state), verified against the pins.

Usage:
  python3 run_swap.py phase1      # ctrl16, cli16+so17, cli17+so16, ctrl17
  python3 run_swap.py cell <label> <cli_tag> <so_set> [...]   # e.g. cell so0807-cli16 v0.16.0 96b4819c
  python3 run_swap.py restore     # v0.16.0 binary + set, pins-verified
"""
import glob
import hashlib
import json
import os
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
DEV_DIR = "/data/local/tmp/llmbench"
PINS = json.load(open(os.path.join(ROOT, "android", "engine-pins.json")))["litert-lm"]
SCRATCH = os.environ.get("SWAP_SCRATCH", "/private/tmp/claude-501/-Users-majimadaisuke-code-standup/"
                         "d9e81ab4-aafb-435b-b50b-ba39954d6ef2/scratchpad/accel")
SO_FILES = ["libGemmaModelConstraintProvider.so", "libLiteRtGpuAccelerator.so", "libLiteRtOpenClAccelerator.so",
            "libLiteRtTopKOpenClSampler.so", "libLiteRtTopKWebGpuSampler.so", "libLiteRtWebGpuAccelerator.so",
            "libwebgpu_dawn.so"]
SO_SETS = {  # set name -> local dir holding the 7 .so
    "v0.16.0": os.path.join(ROOT, "android", "bin", "v0.16.0"),
    "v0.17.0": os.path.join(ROOT, "android", "bin", "v0.17.0"),
    "96b4819c": os.path.join(SCRATCH, "96b4819c"),
    "3dc788a4": os.path.join(SCRATCH, "3dc788a4"),
}
PUB = os.path.expanduser(
    "~/.cache/huggingface/hub/models--litert-community--Qwen3-1.7B/snapshots/"
    "73fbc3fe8271c162a603ee66f6e7ed25b6211195/Qwen3-1.7B_dynamic_wi4b32_afp32.litertlm")
assert PUB.endswith(".litertlm") and os.path.exists(PUB), PUB


def log(msg):
    print(time.strftime("[%F %T] ") + msg, flush=True)


def sh(cmd, timeout=600):
    return subprocess.run(["adb", "-s", SERIAL, "shell", cmd], capture_output=True, text=True,
                          timeout=timeout).stdout


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


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


def deploy(cli_tag, so_set):
    """Push android/bin/<cli_tag>/litert_lm_main + the 7 .so of SO_SETS[so_set]; verify every sha256 on the device
    against the local file (and the CLI against the pins)."""
    cli = os.path.join(ROOT, "android", "bin", cli_tag, "litert_lm_main")
    assert sha256(cli) == PINS[cli_tag]["litert_lm_main_sha256"], f"local CLI {cli_tag} is not the pinned one"
    want = {"litert_lm_main": (cli, sha256(cli))}
    for f in SO_FILES:
        p = os.path.join(SO_SETS[so_set], f)
        want[f] = (p, sha256(p))
    sh(f"chmod 755 {DEV_DIR}/litert_lm_main {DEV_DIR}/*.so")
    for f, (p, _) in want.items():
        subprocess.run(["adb", "-s", SERIAL, "push", p, f"{DEV_DIR}/{f}"], check=True, capture_output=True,
                       timeout=600)
    sh(f"chmod 755 {DEV_DIR}/litert_lm_main {DEV_DIR}/*.so")
    out = sh(f"cd {DEV_DIR} && sha256sum " + " ".join(want))
    got = {l.split()[1]: l.split()[0] for l in out.splitlines() if len(l.split()) == 2}
    bad = {k: (got.get(k), v[1]) for k, v in want.items() if got.get(k) != v[1]}
    if bad:
        log(f"DEPLOY VERIFY FAILED cli={cli_tag} so={so_set}: {bad}")
        sys.exit(4)
    log(f"engine on device = CLI {cli_tag} ({want['litert_lm_main'][1][:8]}) + .so set {so_set} "
        f"(GpuAccelerator {want['libLiteRtGpuAccelerator.so'][1][:8]}, OpenClAccelerator "
        f"{want['libLiteRtOpenClAccelerator.so'][1][:8]}); all 8 sha256 verified on device")


def show_text(logfile):
    txt = open(logfile, errors="replace").read()
    i = txt.find("===ENGINE_OUTPUT===")
    body = txt[i + len("===ENGINE_OUTPUT==="):] if i >= 0 else txt
    j = body.find("</think>")
    head = body[:600].replace("\n", " | ")
    ans = body[j:j + 700].replace("\n", " | ") if j >= 0 else "(no </think> in the output) " + body[-700:].replace("\n", " | ")
    log(f"engine output head: {head}")
    log(f"answer: {ans}")


def cell(label, cli_tag, so_set):
    deploy(cli_tag, so_set)
    model_id = f"litert-local/Qwen3-1.7B-pub-wi4b32-{label}"
    wait_nominal()
    log(freq_line())
    cmd = [sys.executable, os.path.join(ROOT, "android", "bench", "run_cell.py"),
           "--runtime", "litert-lm", "--backend", "gpu", "--model-id", model_id,
           "--file", PUB, "--task", "short-chat", "--runs", "1", "--out", OUT,
           "--serial", SERIAL, "--timeout", "1800"]
    env = dict(os.environ, BENCH_ANDROID_SERIAL=SERIAL, BENCH_CPU_MASK="", PYTHONUNBUFFERED="1")
    log(f"CELL {label}: cli={cli_tag} so={so_set}")
    log("$ " + " ".join(cmd))
    rc = subprocess.run(cmd, env=env, cwd=ROOT).returncode
    log(f"exit {rc}")
    logs = glob.glob(os.path.join(OUT, f"litert-lm-gpu_{model_id.replace('/', '_')}_short-chat_*_run1.log"))
    if logs:
        show_text(max(logs, key=os.path.getmtime))
    dev = f"{DEV_DIR}/models/{model_id.replace('/', '_')}_{os.path.basename(PUB)}"
    sh(f"rm -f {dev}* {DEV_DIR}/markers/{os.path.basename(dev)}.*.cachebuilt")
    log(f"removed {dev}* (+ its caches and markers)")
    return rc


def deploy_dir(d, so_dir=None):
    """Push <d>/litert_lm_main + the 7 .so in <d> (a self-consistent build at one LiteRT-LM commit), or, with so_dir,
    the 7 .so of another build dir (a deliberate mix); verify every sha256 on the device against the local file.
    No pins entry exists for these — the driver log records the shas."""
    so_dir = so_dir or d
    want = {"litert_lm_main": (os.path.join(d, "litert_lm_main"), sha256(os.path.join(d, "litert_lm_main")))}
    for f in SO_FILES:
        p = os.path.join(so_dir, f)
        want[f] = (p, sha256(p))
    sh(f"chmod 755 {DEV_DIR}/litert_lm_main {DEV_DIR}/*.so")
    for f, (p, _) in want.items():
        subprocess.run(["adb", "-s", SERIAL, "push", p, f"{DEV_DIR}/{f}"], check=True, capture_output=True,
                       timeout=600)
    sh(f"chmod 755 {DEV_DIR}/litert_lm_main {DEV_DIR}/*.so")
    out = sh(f"cd {DEV_DIR} && sha256sum " + " ".join(want))
    got = {l.split()[1]: l.split()[0] for l in out.splitlines() if len(l.split()) == 2}
    bad = {k: (got.get(k), v[1]) for k, v in want.items() if got.get(k) != v[1]}
    if bad:
        log(f"DEPLOY VERIFY FAILED dir={d}: {bad}")
        sys.exit(4)
    log(f"engine on device = build dir {d}: litert_lm_main {want['litert_lm_main'][1][:8]}, GpuAccelerator "
        f"{want['libLiteRtGpuAccelerator.so'][1][:8]}, OpenClAccelerator {want['libLiteRtOpenClAccelerator.so'][1][:8]}"
        f"; all 8 sha256 verified on device")


def cell_dir(label, d, so_dir=None):
    """One GPU short-chat cell on a self-consistent build (binary + its own .so set) from directory d — or, with
    so_dir, the binary of d with the .so set of so_dir (a deliberate mix, see the NOTES)."""
    deploy_dir(d, so_dir)
    model_id = f"litert-local/Qwen3-1.7B-pub-wi4b32-{label}"
    wait_nominal()
    log(freq_line())
    cmd = [sys.executable, os.path.join(ROOT, "android", "bench", "run_cell.py"),
           "--runtime", "litert-lm", "--backend", "gpu", "--model-id", model_id,
           "--file", PUB, "--task", "short-chat", "--runs", "1", "--out", OUT,
           "--serial", SERIAL, "--timeout", "1800"]
    env = dict(os.environ, BENCH_ANDROID_SERIAL=SERIAL, BENCH_CPU_MASK="", PYTHONUNBUFFERED="1")
    log(f"CELL {label}: build dir {d}")
    log("$ " + " ".join(cmd))
    rc = subprocess.run(cmd, env=env, cwd=ROOT).returncode
    log(f"exit {rc}")
    logs = glob.glob(os.path.join(OUT, f"litert-lm-gpu_{model_id.replace('/', '_')}_short-chat_*_run1.log"))
    if logs:
        show_text(max(logs, key=os.path.getmtime))
    dev = f"{DEV_DIR}/models/{model_id.replace('/', '_')}_{os.path.basename(PUB)}"
    sh(f"rm -f {dev}* {DEV_DIR}/markers/{os.path.basename(dev)}.*.cachebuilt")
    log(f"removed {dev}* (+ its caches and markers)")
    return rc


def restore():
    deploy("v0.16.0", "v0.16.0")
    want = {"litert_lm_main": PINS["v0.16.0"]["litert_lm_main_sha256"], **PINS["v0.16.0"]["so_files"]}
    out = sh(f"cd {DEV_DIR} && sha256sum " + " ".join(want))
    got = {l.split()[1]: l.split()[0] for l in out.splitlines() if len(l.split()) == 2}
    bad = {k: (got.get(k), v) for k, v in want.items() if got.get(k) != v}
    if bad:
        log(f"RESTORE VERIFY FAILED against pins: {bad}")
        sys.exit(5)
    log("device back at v0.16.0 (binary + 7 .so), every sha256 matches android/engine-pins.json")


PHASE1 = [("ctrl16", "v0.16.0", "v0.16.0"), ("cli16-so17", "v0.16.0", "v0.17.0"),
          ("cli17-so16", "v0.17.0", "v0.16.0"), ("ctrl17", "v0.17.0", "v0.17.0")]


def main():
    mode = sys.argv[1]
    rc = subprocess.run([sys.executable, HOLD_CLI, "acquire", HOLD, "edge-llm-bench diag run_swap.py",
                         str(os.getpid())], capture_output=True, text=True)
    if rc.returncode != 0:
        log("hold refused: " + rc.stdout + rc.stderr)
        sys.exit(3)
    log(f"hold taken ({HOLD}, pid {os.getpid()})")
    try:
        log(f"device: {sh('getprop ro.product.model').strip()} {sh('getprop ro.build.version.release').strip()} "
            f"uptime {sh('cat /proc/uptime').split()[0]} s; free: {sh('df -h /data | tail -1').strip()}")
        if mode == "phase1":
            for label, c, s in PHASE1:
                cell(label, c, s)
        elif mode == "cell":
            args = sys.argv[2:]
            for i in range(0, len(args), 3):
                cell(args[i], args[i + 1], args[i + 2])
        elif mode == "cell-dir":
            args = sys.argv[2:]
            for i in range(0, len(args), 2):
                cell_dir(args[i], args[i + 1])
        elif mode == "cell-mix":
            args = sys.argv[2:]
            for i in range(0, len(args), 3):
                cell_dir(args[i], args[i + 1], args[i + 2])
        elif mode == "restore":
            pass
        else:
            raise SystemExit(__doc__)
    finally:
        restore()
        subprocess.run([sys.executable, HOLD_CLI, "release", HOLD, str(os.getpid())])
        log("hold released")


if __name__ == "__main__":
    main()
