"""Host side of the ORT GenAI Galaxy S26 smoke (round r2, 2026-10-07), by hand.

Run only while this session owns the S26 hold (queue_cli.py wait) and after the
supervisor's go. One phase per call; everything seen is appended to host.log
next to this file with the wall-clock time.

  probe                 the device-busy probe list (lock, hold, host drivers,
                        engine processes on the phone, thermal, cpufreq, battery)
  push                  runtime dir (3 .so + 2 binaries + run_sampled.sh, sha256
                        checked), model folder (bytes checked), prompts (reused
                        when the sha256 matches, never overwritten)
  run [--big-ml N]      the four launches, 120 s apart, each after the
                        cpu-cap-rule gate; holds the campaign flock meanwhile
  pull                  device out/ -> ./device/
  clean                 removes the model folder and out/ (runtime dir stays)
"""
import fcntl
import hashlib
import os
import re
import subprocess
import sys
import time

SERIAL = "RFGL80R6A6H"
DEV = "/data/local/tmp/llmbench"
RUNTIME_DIR = f"{DEV}/ortgenai"
MODEL_DIR = f"{DEV}/models/onnx-community_Qwen3-0.6B-ONNX_cpu-int4-kld-block-128"
PROMPT_DIR = f"{DEV}/prompts"
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
BIN = os.path.join(REPO, "android", "bin", "ortgenai-0.17.0")
MODEL = os.path.expanduser(
    "~/.cache/huggingface/hub/models--onnx-community--Qwen3-0.6B-ONNX/snapshots/"
    "da1453100cf3ff33ef56d17983fc7a8648706db6/onnxruntime/cpu_and_mobile/cpu-int4-kld-block-128")
RUNTIME_FILES = ["libonnxruntime-genai.so", "libmat.so", "libonnxruntime.so", "ortgenai_run", "model_benchmark"]
MODEL_FILES = ["chat_template.jinja", "config.json", "genai_config.json", "model.onnx",
               "tokenizer.json", "tokenizer_config.json"]
TASKS = ["short-chat", "long-context-1024-gen256"]
HOLD = os.path.expanduser("~/code/litertlm-convert/community_accel_work/s2_npu_sweep/.device_hold")
LOCK = f"/tmp/edge-llm-bench-android-{SERIAL}.lock"
LOG = os.path.join(HERE, "host.log")
GAP_S = 120
GATE_MAX_S = 600
BATTERY_MAX_C = 33.0


def log(msg):
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def adb(*args, timeout=120, check=True):
    r = subprocess.run(["adb", "-s", SERIAL, *args], capture_output=True, text=True, timeout=timeout)
    if check and r.returncode != 0:
        raise SystemExit(f"adb {' '.join(args)} failed ({r.returncode}): {r.stderr.strip() or r.stdout.strip()}")
    return r.stdout


def sh(cmd, timeout=120, check=True):
    return adb("shell", cmd, timeout=timeout, check=check)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def device_sha256(path):
    out = sh(f"if [ -e {path} ]; then sha256sum {path}; else echo MISSING; fi").strip()
    return None if out == "MISSING" else out.split()[0]


def state():
    """Thermal status, battery temperature, cpufreq caps against hardware maxima, memory, screen."""
    thermal = re.search(r"Thermal Status:\s*(\d+)", sh("dumpsys thermalservice"))
    battery = re.search(r"temperature:\s*(\d+)", sh("dumpsys battery"))
    freq = sh("for p in /sys/devices/system/cpu/cpufreq/policy*; do "
              "echo ${p##*/} $(cat $p/cpuinfo_max_freq) $(cat $p/scaling_max_freq); done").split("\n")
    policies = [ln.split() for ln in freq if ln.strip()]
    mem = re.search(r"MemAvailable:\s*(\d+)", sh("cat /proc/meminfo"))
    wake = re.search(r"mWakefulness=(\w+)", sh("dumpsys power"))
    return {
        "thermal": int(thermal.group(1)) if thermal else None,
        "battery_c": int(battery.group(1)) / 10 if battery else None,
        "policies": policies,
        "capped": [p[0] for p in policies if p[1] != p[2]],
        "mem_available_mb": int(mem.group(1)) // 1024 if mem else None,
        "wakefulness": wake.group(1) if wake else None,
    }


def describe(s):
    pol = " ".join(f"{p[0]}={p[2]}/{p[1]}" for p in s["policies"])
    return (f"thermal={s['thermal']} battery={s['battery_c']}C capped={s['capped'] or 'none'} "
            f"cap/hw[{pol}] MemAvailable={s['mem_available_mb']}MB wakefulness={s['wakefulness']}")


def probe():
    try:
        fh = open(LOCK, "w")
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(fh, fcntl.LOCK_UN)
        log(f"probe lock: free ({LOCK})")
    except OSError:
        log(f"probe lock: HELD ({LOCK})")
    log("probe hold: " + (open(HOLD).read().strip() if os.path.exists(HOLD) else "none"))
    # anchored on the interpreter: an unanchored pattern also matches every Claude session whose
    # prompt text mentions android/bench/run_cell.py (three on 2026-10-07 22:31)
    drivers = subprocess.run(["pgrep", "-fl", "^[^ ]*[p]ython[0-9.]* [^ ]*android/bench/run_"],
                             capture_output=True, text=True).stdout.strip()
    log(f"probe host drivers: {drivers or 'none'}")
    engines = sh("ps -A | grep -E 'litert_lm|llama|ortgenai|model_benchmark' | grep -v grep", check=False).strip()
    log(f"probe device engines: {engines or 'none'}")
    log("probe android: " + sh("getprop ro.product.model").strip() + " / Android "
        + sh("getprop ro.build.version.release").strip() + " / patch "
        + sh("getprop ro.build.version.security_patch").strip() + " / "
        + sh("getprop ro.build.fingerprint").strip() + " / uptime " + sh("cat /proc/uptime").split()[0])
    log("probe disk: " + sh("df -k /data | tail -1").strip())
    log("probe state: " + describe(state()))


def push():
    sh(f"mkdir -p {RUNTIME_DIR} {MODEL_DIR} {PROMPT_DIR}")
    for name, local in [(n, os.path.join(BIN, n)) for n in RUNTIME_FILES] + [
            ("run_sampled.sh", os.path.join(HERE, "run_sampled.sh"))]:
        want = sha256(local)
        if device_sha256(f"{RUNTIME_DIR}/{name}") != want:
            adb("push", local, f"{RUNTIME_DIR}/{name}", timeout=600)
        got = device_sha256(f"{RUNTIME_DIR}/{name}")
        if got != want:
            raise SystemExit(f"push verification failed: {name} device {got} local {want}")
        log(f"push runtime {name} sha256 {want}")
    sh(f"chmod 755 {RUNTIME_DIR}/ortgenai_run {RUNTIME_DIR}/model_benchmark")
    for name in MODEL_FILES:
        local = os.path.realpath(os.path.join(MODEL, name))
        adb("push", local, f"{MODEL_DIR}/{name}", timeout=1800)
        got = sh(f"stat -c %s {MODEL_DIR}/{name}").strip()
        if got != str(os.path.getsize(local)):
            raise SystemExit(f"push verification failed: {name} device {got} bytes, local {os.path.getsize(local)}")
        log(f"push model {name} {got} bytes")
    for task in TASKS:
        local = os.path.join(REPO, "prompts", "text", f"{task}.txt")
        want = sha256(local)
        got = device_sha256(f"{PROMPT_DIR}/{task}.txt")
        if got is None:
            adb("push", local, f"{PROMPT_DIR}/{task}.txt")
            got = device_sha256(f"{PROMPT_DIR}/{task}.txt")
            log(f"push prompt {task} sha256 {got}")
        elif got == want:
            log(f"prompt {task} present, sha256 matches {want}")
        if got != want:
            raise SystemExit(f"{PROMPT_DIR}/{task}.txt is {got}, local {want}: not ours, not overwritten")


def launches(big_ml):
    model = f"-i {MODEL_DIR}"
    short, long = f"{PROMPT_DIR}/short-chat.txt", f"{PROMPT_DIR}/long-context-1024-gen256.txt"
    return [
        ("r2-1-short-ml2048", "ortgenai_run", f"{model} --prompt_file {short} -g 128 -ml 2048"),
        ("r2-2-1k-ml2048", "ortgenai_run", f"{model} --prompt_file {long} -g 256 -ml 2048"),
        (f"r2-3-1k-ml{big_ml}", "ortgenai_run", f"{model} --prompt_file {long} -g 256 -ml {big_ml}"),
        ("r2-4-mb-short-ml2048", "model_benchmark",
         f"{model} --prompt_file {short} -g 128 -ml 2048 -r 1 -w 0 -v -e cpu"),
    ]


def gate():
    """cpu-cap-rule before a launch: every policy at its hardware maximum, thermal 0, battery cool."""
    start = time.time()
    while True:
        s = state()
        ok = not s["capped"] and s["thermal"] == 0 and (s["battery_c"] or 99) <= BATTERY_MAX_C
        log(("gate pass: " if ok else "gate wait: ") + describe(s))
        if ok:
            return True
        if time.time() - start > GATE_MAX_S:
            return False
        time.sleep(15)


def run(big_ml):
    lock = open(LOCK, "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        raise SystemExit(f"campaign lock held by another driver: {LOCK}")
    for i, (tag, binary, args) in enumerate(launches(big_ml)):
        if i:
            log(f"pause {GAP_S} s")
            time.sleep(GAP_S)
        if not gate():
            log(f"STOP: the gate did not pass within {GATE_MAX_S} s before {tag}")
            return 1
        log(f"launch {tag}: ./{binary} {args}")
        try:
            out = sh(f"sh {RUNTIME_DIR}/run_sampled.sh {tag} {binary} {args}", timeout=900, check=False)
        except subprocess.TimeoutExpired:
            log(f"launch {tag}: host timeout; no record (not re-run)")
            return 1
        if "EXIT_CODE=" not in out:
            log(f"launch {tag}: lost (adb output {out.strip()[-200:]!r}); no record (not re-run)")
            return 1
        exit_line = [ln for ln in out.splitlines() if ln.startswith("EXIT_CODE=")][-1].strip()
        log(f"launch {tag}: {exit_line}")
        engine = sh(f"cat {RUNTIME_DIR}/out/{tag}.engine.txt", check=False)
        for ln in engine.splitlines():
            if ln.startswith(("ORTGENAI", "Error", "Exception", "Batch size", "Prompt processing",
                              "Token generation", "Peak working set", "CANNOT", "WARNING")) \
                    or "avg (tokens/s)" in ln or "dlopen" in ln:
                log(f"  {tag} | {ln.strip()}")
        log(f"after {tag}: " + describe(state()))
        if exit_line != "EXIT_CODE=0":
            log(f"STOP: {tag} did not exit 0; the engine output is in out/{tag}.engine.txt")
            return 1
    return 0


def pull():
    dest = os.path.join(HERE, "device")
    os.makedirs(dest, exist_ok=True)
    adb("pull", f"{RUNTIME_DIR}/out/.", dest, timeout=300)
    log("pulled: " + " ".join(sorted(os.listdir(dest))))


def clean():
    sh(f"rm -rf {MODEL_DIR} {RUNTIME_DIR}/out")
    left = sh(f"ls -d {MODEL_DIR} {RUNTIME_DIR}/out 2>/dev/null", check=False).strip()
    log(f"clean: model folder and out/ removed{' — LEFT: ' + left if left else ''}; runtime dir: "
        + " ".join(sh(f"ls {RUNTIME_DIR}").split()))
    log("disk after clean: " + sh("df -k /data | tail -1").strip())


def main(argv):
    phase = argv[1] if len(argv) > 1 else ""
    log(f"phase {' '.join(argv[1:]) or '(none)'}")
    try:
        return dispatch(phase, argv)
    except SystemExit as exc:
        if exc.code not in (None, 0):
            log(f"phase {phase} ended: {exc.code}")
        raise


def dispatch(phase, argv):
    if phase == "probe":
        probe()
    elif phase == "push":
        push()
    elif phase == "run":
        big_ml = int(argv[argv.index("--big-ml") + 1]) if "--big-ml" in argv else 8192
        return run(big_ml)
    elif phase == "pull":
        pull()
    elif phase == "clean":
        clean()
    else:
        raise SystemExit(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
