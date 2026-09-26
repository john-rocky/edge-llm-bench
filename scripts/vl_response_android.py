#!/usr/bin/env python3
"""Vision-language response-time cells on an Android phone over adb (task family `vl-*`), v1.

The Android leg of docs/vl-response-v1.md: the same LiteRT-LM CLI
(`//runtime/engine:litert_lm_advanced_main`, built with `--config=android_arm64`),
the same image, prompt, budget and CLI flags as scripts/vl_response_mac.py, one
process launch per run through `adb shell`. Like scripts/asr_rtf_android.py it
is its own mini-runner: it reads the `android` `vl-*` rows of a cells file,
stages the CLI + the GPU .so files + the image + the bundles under
/data/local/tmp/edge-llm-bench/vl, gates every launch on the phone's thermal
status (0 = nominal, android/bench/device_probe.py vocabulary) and battery
temperature (<= 36 C), and writes the same record shape as the Mac driver into
results/raw/<campaign>-android/.

Streams and clocks. `adb shell` (shell protocol v2) hands the phone process's
stdout and stderr over as two separate streams, so the reply (stdout) and the
engine log (stderr) are read exactly as on the Mac:
  vlResponseSeconds        host arrival of the request marker ("Running
                           single-turn conversation", stderr) -> host arrival
                           of the last reply byte (stdout); the CLI flushes
                           every token (~14 ms apart on the S26 smoke)
  vlFirstTokenHostSeconds  request marker -> first reply byte
Both markers travel the same USB/adb connection, so the deltas carry adb's
jitter (milliseconds) but no offset. loadTimeSeconds and totalWallSeconds are
PHONE-clock differences ($EPOCHREALTIME echoed before exec and after exit, the
absl timestamp of the request marker), so adb start-up latency is not in them.
The engine's own clocks (TTFT, prefill, decode, init phases) come from
--benchmark's BenchmarkInfo as on the Mac. The OpenCL loader prints
"INFO: Loaded OpenCL library with dlopen." on STDOUT; log-shaped lines are
stripped from the reply and ignored for the first-byte clock.
memoryPeakResidentMB = VmHWM of the process polled through adb every 0.5 s
(host memory only: the OpenCL arm's GPU heap is outside it).
conditions.screen is stamped from the phone's measured mWakefulness before each
launch ("on-usb" only when Awake), not copied from the device page's protocol.
conditions.gpuAccelerator names the GPU accelerator the launch's log registered
(vl_response_mac.gpu_accelerator; the first S26 capture's logs read
"LiteRT GPU (libLiteRtGpuAccelerator.so)").

The session anchor is not run by this script: run the android rows of
matrices/anchors.cells first (`./bench matrix matrices/anchors.cells --platform
android --campaign <campaign>-anchor`) and judge the sitting with
scripts/dashboard_job.py's admit() (the dashboard rule), as docs/vl-response-v1.md
describes for the Android leg.

Usage:
  scripts/vl_response_android.py matrices/vl-response-v1.cells --campaign 2026-09-26-vl-response-v1-s26
  (writes results/raw/<campaign>-android/; BENCH_ANDROID_SERIAL or --serial picks the phone)

Environment:
  VL_ANDROID_RUNNER_DIR  litert_lm_advanced_main (android_arm64) + *.so + ENGINE_VERSION
                         (default .build/litert-lm-advanced-main-1dadd00c-android; line 1 of
                         ENGINE_VERSION is stamped as engineVersion, the rest goes into engineArtifact)
  VL_MODEL_DIR           bundles outside the HF cache, with HF_SHA256SUMS (default .build/vl-models)
"""
import argparse
import datetime as dt
import glob
import json
import os
import re
import subprocess
import sys
import threading
import time
import uuid

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
sys.path.insert(0, os.path.join(REPO, "android", "bench"))
from vl_response_mac import ANSI, DISPLAY, TASK_SETS, gpu_accelerator, parse_benchmark, quant_label, sha256  # noqa: E402
from device_probe import adb, battery, device_info, thermal_status  # noqa: E402
from validate_cells import parse_line  # noqa: E402

HARNESS_STAMP = "vl-response-v1-android-2026-09-26"
DEV_DIR = "/data/local/tmp/edge-llm-bench/vl"
DEFAULT_RUNNER = os.path.join(REPO, ".build", "litert-lm-advanced-main-1dadd00c-android")
REQUEST_MARKER = "Running single-turn conversation"
RE_MARKER_TS = re.compile(r"^[IWEF]0000 00:00:(\d+\.\d+)\s+\d+\s+\S+\] " + re.escape(REQUEST_MARKER), re.M)
RE_T0 = re.compile(r"^T0=(\d+\.\d+)\s*$", re.M)
RE_EXIT = re.compile(r"^EXIT=(\d+) T1=(\d+\.\d+)\s*$", re.M)
# log chatter that the OpenCL loader / TFLite print on STDOUT, not part of the reply
RE_STDOUT_LOG = re.compile(r"^(?:INFO|VERBOSE|WARNING|ERROR|DEBUG): [^\n]*\n?", re.M)


def sh(serial, cmd, timeout=120):
    return adb(["shell", cmd], serial, timeout=timeout)


def remote_size(serial, path):
    out = sh(serial, f"stat -c %s {path} 2>/dev/null || echo -1").strip()
    try:
        return int(out.splitlines()[-1])
    except ValueError:
        return -1


def push_if_needed(serial, local, remote, log):
    size = os.path.getsize(local)
    if remote_size(serial, remote) == size:
        log(f"  keep {os.path.basename(remote)} ({size} B already on the phone)")
        return False
    t0 = time.monotonic()
    subprocess.run(["adb", "-s", serial, "push", local, remote], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    log(f"  pushed {os.path.basename(remote)} {size} B in {time.monotonic() - t0:.1f} s")
    return True


def phone_state(serial):
    raw, name = thermal_status(serial)
    bat = battery(serial)
    out = sh(serial, "dumpsys battery | grep -E '^  temperature'")
    m = re.search(r"temperature: (\d+)", out)
    temp = int(m.group(1)) / 10.0 if m else None
    caps = sh(serial, "for c in /sys/devices/system/cpu/cpufreq/policy*; do echo $(cat $c/scaling_max_freq) $(cat $c/cpuinfo_max_freq); done").split()
    capped = any(caps[i] != caps[i + 1] for i in range(0, len(caps) - 1, 2))
    # the owner's hand settings can change mid-session (developer option "stay
    # awake"); record them beside every launch so a change sits next to the numbers
    pw = sh(serial, "dumpsys power 2>/dev/null | grep -E 'mWakefulness=' | head -1")
    wm = re.search(r"mWakefulness=(\w+)", pw)
    stay = sh(serial, "settings get global stay_on_while_plugged_in").strip().splitlines()
    return {"thermalStatusRaw": raw, "thermal": name, "batteryTempC": temp,
            "batteryLevel": bat.get("batteryLevel"), "batteryState": bat.get("batteryState"),
            "cpuFreqCapped": capped, "cpuMaxFreqKHz": caps[1::2],
            "wakefulness": wm.group(1) if wm else None,
            "stayOnWhilePluggedIn": stay[-1] if stay else None}


def wait_nominal(serial, log, max_wait=600):
    t0 = time.monotonic()
    while True:
        st = phone_state(serial)
        if st["thermalStatusRaw"] == 0 and (st["batteryTempC"] is None or st["batteryTempC"] <= 36.0):
            return st
        if time.monotonic() - t0 > max_wait:
            log(f"  thermal gate: giving up after {max_wait}s (status {st['thermal']}, {st['batteryTempC']} C) — launching anyway, recorded")
            return st
        log(f"  thermal gate: status={st['thermal']} battery={st['batteryTempC']} C — waiting")
        time.sleep(15)


def arrival_of(chunks, offset):
    """Host arrival time of the read that delivered byte `offset` of a joined stream."""
    t = chunks[0][1] if chunks else None
    for start, mono in chunks:
        if start <= offset:
            t = mono
        else:
            break
    return t


def one_run(args, ctx, cell, run_idx, log):
    serial = args.serial
    slug = cell["slug"]
    remote_model = f"{DEV_DIR}/models/{cell['file']}"
    cache_dir = f"{DEV_DIR}/cache/{cell['file']}"
    prompt = f"{ctx['prompt']} [image:{DEV_DIR}/images/{ctx['image_name']}]"
    if "'" in prompt:
        sys.exit("the prompt must not contain a single quote (it is single-quoted for the phone's shell)")
    cmd = (f"cd {DEV_DIR}/bin && export LD_LIBRARY_PATH={DEV_DIR}/bin && echo T0=$EPOCHREALTIME >&2 && "
           f"./litert_lm_advanced_main --backend={cell['backend']} --vision_backend={cell['backend']} "
           f"--model_path={remote_model} --input_prompt='{prompt}' --benchmark "
           f"--max_output_tokens={ctx['max_output_tokens']} --cache_dir={cache_dir}; "
           f"echo EXIT=$? T1=$EPOCHREALTIME >&2")
    before = wait_nominal(serial, log)
    events, lock = [], threading.Lock()
    peak = {"kb": 0}
    stop = threading.Event()

    def reader(stream, tag):
        fd = stream.fileno()
        while True:
            try:
                chunk = os.read(fd, 65536)
            except OSError:
                break
            if not chunk:
                break
            with lock:
                events.append((time.monotonic(), tag, chunk.decode("utf-8", "replace")))

    def mem_poll():
        while not stop.is_set():
            try:
                out = subprocess.check_output(
                    ["adb", "-s", serial, "shell",
                     "p=$(pidof litert_lm_advanced_main); [ -n \"$p\" ] && grep VmHWM /proc/$p/status"],
                    text=True, timeout=10, stderr=subprocess.DEVNULL)
                m = re.search(r"VmHWM:\s+(\d+)", out)
                if m:
                    peak["kb"] = max(peak["kb"], int(m.group(1)))
            except Exception:
                pass
            time.sleep(0.5)

    wall0 = dt.datetime.now(dt.timezone.utc)
    t0 = time.monotonic()
    p = subprocess.Popen(["adb", "-s", serial, "shell", cmd], stdin=subprocess.DEVNULL,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    th = [threading.Thread(target=reader, args=(p.stdout, "out"), daemon=True),
          threading.Thread(target=reader, args=(p.stderr, "err"), daemon=True)]
    for t in th:
        t.start()
    mt = threading.Thread(target=mem_poll, daemon=True)
    mt.start()
    killed = False
    while p.poll() is None:
        time.sleep(0.2)
        if time.monotonic() - t0 > args.timeout and not killed:
            killed = True
            log(f"  timeout after {args.timeout:.0f} s — killing the phone process")
            sh(serial, "pkill -f litert_lm_advanced_main || true")
            p.kill()
    for t in th:
        t.join(timeout=5)
    stop.set()
    mt.join(timeout=3)
    after = phone_state(serial)

    # Join each stream and keep, per read, the offset it started at — a chunk
    # boundary can fall inside a line (the marker) or inside a token.
    out_chunks, err_chunks = [], []
    out_parts, err_parts = [], []
    o = e = 0
    for mono, tag, text in events:
        if tag == "out":
            out_chunks.append((o, mono)); out_parts.append(text); o += len(text)
        else:
            err_chunks.append((e, mono)); err_parts.append(text); e += len(text)
    stdout_raw = "".join(out_parts)
    stderr_text = "".join(err_parts)

    t_req = None
    i = stderr_text.find(REQUEST_MARKER)
    if i >= 0:
        t_req = arrival_of(err_chunks, i)
    # reply bytes = stdout minus the loader's log lines; first / last reply byte by offset
    mask = bytearray(b"\x01" * len(stdout_raw))
    for m in RE_STDOUT_LOG.finditer(stdout_raw):
        mask[m.start():m.end()] = b"\x00" * (m.end() - m.start())
    for m in ANSI.finditer(stdout_raw):
        mask[m.start():m.end()] = b"\x00" * (m.end() - m.start())
    reply_offsets = [k for k, ch in enumerate(stdout_raw) if mask[k] and not ch.isspace()]
    t_first = arrival_of(out_chunks, reply_offsets[0]) if reply_offsets else None
    t_last = arrival_of(out_chunks, reply_offsets[-1]) if reply_offsets else None
    reply = re.sub(r"\s+", " ", ANSI.sub("", RE_STDOUT_LOG.sub("", stdout_raw))).strip()

    t0_dev = t1_dev = ts_req = None
    rc = None
    m = RE_T0.search(stderr_text)
    if m:
        t0_dev = float(m.group(1))
    m = RE_EXIT.search(stderr_text)
    if m:
        rc, t1_dev = int(m.group(1)), float(m.group(2))
    m = RE_MARKER_TS.search(stderr_text)
    if m:
        ts_req = float(m.group(1))
    bench = parse_benchmark(stderr_text)

    logs = os.path.join(args.out, "logs")
    os.makedirs(logs, exist_ok=True)
    err_log = os.path.join(logs, f"{slug}_run{run_idx}.stderr.log")
    with open(err_log, "w") as f:
        f.write(f"# adb -s {serial} shell '{cmd}'\n# exit={rc}\n# stderr stream follows (T0/EXIT markers are the driver's)\n")
        f.write(stderr_text)
    with open(os.path.join(logs, f"{slug}_run{run_idx}.stdout.txt"), "w") as f:
        f.write(stdout_raw)

    metrics = {"coldRun": True, "harnessStamp": HARNESS_STAMP, "exitCode": rc,
               "memoryPeakResidentMB": round(peak["kb"] / 1024.0, 1),
               "initialThermalState": before["thermal"], "finalThermalState": after["thermal"],
               "batteryTempInitialC": before["batteryTempC"], "batteryTempFinalC": after["batteryTempC"]}
    if t0_dev is not None and ts_req is not None:
        metrics["loadTimeSeconds"] = round(ts_req - t0_dev, 3)
    if t0_dev is not None and t1_dev is not None:
        metrics["totalWallSeconds"] = round(t1_dev - t0_dev, 3)
    if t_req is not None:
        if t_last is not None and t_last >= t_req:
            metrics["vlResponseSeconds"] = round(t_last - t_req, 3)
        if t_first is not None and t_first >= t_req:
            metrics["vlFirstTokenHostSeconds"] = round(t_first - t_req, 3)
    if "ttft_s" in bench:
        metrics["vlTimeToFirstTokenSeconds"] = bench["ttft_s"]
    for k_src, k_dst in (("prefill_tokens", "vlPrefillTokens"), ("prefill_tps", "vlPrefillTokensPerSec"),
                         ("decode_tokens", "vlDecodeTokens"), ("decode_tps", "vlDecodeTokensPerSec"),
                         ("prefill_seconds", "vlPrefillSeconds"), ("decode_seconds", "vlDecodeSeconds")):
        if k_src in bench:
            metrics[k_dst] = round(bench[k_src], 4) if isinstance(bench[k_src], float) else bench[k_src]
    if bench.get("initPhasesMS"):
        metrics["vlInitPhasesMS"] = bench["initPhasesMS"]
    if bench.get("markDurationsMS"):
        metrics["vlMarkDurationsMS"] = bench["markDurationsMS"]
    low = reply.lower()
    hit = [w for w in ctx["keywords"] if w in low]
    metrics["vlTextCheck"] = "pass" if hit else "fail"
    metrics["vlKeywordsHit"] = hit
    invalid = len(re.findall(r"Invalid decode", stderr_text))
    if invalid:
        metrics["vlInvalidDecodeLines"] = invalid
    ok = rc == 0 and "vlResponseSeconds" in metrics and metrics["vlTextCheck"] == "pass" and not invalid

    rec = {
        "schemaVersion": 1, "id": str(uuid.uuid4()).upper(),
        "timestamp": wall0.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "runtime": f"{cell['runtime']}-{cell['backend']}",
        "engineVersion": ctx["engine_version"], "engineArtifact": ctx["engine_artifact"],
        "model": {"id": cell["model_id"], "hfRepoId": cell["model_id"],
                  "displayName": DISPLAY.get(cell["model_id"], cell["model_id"]),
                  "primaryFile": cell["file"], "file": cell["file"], "hfFilePatterns": [cell["file"]],
                  "hfRevision": cell["revision"], "quantization": cell["quant_label"],
                  "onDiskSizeMB": round(os.path.getsize(cell["local_path"]) / 1e6, 1), "sha256": cell["sha256"]},
        "modelRevision": cell["revision"],
        "task": cell["task"],
        "device": dict(ctx["device"], batteryState=before["batteryState"], batteryLevel=before["batteryLevel"],
                       cpuMaxFreqKHz=before["cpuMaxFreqKHz"], cpuFreqCapped=before["cpuFreqCapped"]),
        "conditions": {
            "vlPrompt": ctx["prompt"], "vlImages": 1, "vlImageFile": ctx["image_rel"],
            "vlImagePixels": f"{ctx['image_w']}x{ctx['image_h']}",
            "vlMaxOutputTokens": ctx["max_output_tokens"],
            "vlVisionBackend": f"{cell['backend']} (= --backend; the CLI refuses an image without an explicit --vision_backend, so the arm's backend is used for the vision encoder too)",
            "vlVisualTokenBudget": "engine default (-1: the bundle's own)",
            "gpuAccelerator": gpu_accelerator(stderr_text, cell["backend"]),
            "sampler": "engine default (litert_lm_advanced_main flags untouched: repetition_penalty 1.0, no penalties, no constraint)",
            "cacheDir": cache_dir,
            "cpuAffinity": "none (no taskset; the engine sets its own threads)",
            "screen": ("on-usb" if before["wakefulness"] == "Awake"
                       else f"off-usb (mWakefulness={before['wakefulness']})"),
            "warm": False, "unplugged": before["batteryState"] != "charging",
            "thermalInitial": before["thermal"], "thermalFinal": after["thermal"],
        },
        "metrics": metrics,
        "outputSample": reply[:200], "response": reply,
        "provenance": {"imageSet": ctx["set_name"], "imageSha256": ctx["image_sha256"],
                       "manifestSha256": ctx["manifest_sha256"], "modelSha256": cell["sha256"],
                       "remoteModelSha256": cell.get("remote_sha256"),
                       "repoManifest": cell.get("repo_manifest_rel"),
                       "deviceBefore": before, "deviceAfter": after,
                       "command": cmd, "stderrLog": os.path.relpath(err_log, REPO)},
    }
    with open(os.path.join(args.out, f"{slug}.jsonl"), "a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    log(f"{'OK ' if ok else 'FAIL'} run {run_idx}: exit={rc} load={metrics.get('loadTimeSeconds')}s "
        f"resp={metrics.get('vlResponseSeconds')}s ttft={metrics.get('vlTimeToFirstTokenSeconds')}s "
        f"prefill={metrics.get('vlPrefillTokens')}tok@{metrics.get('vlPrefillTokensPerSec')} "
        f"decode={metrics.get('vlDecodeTokens')}tok@{metrics.get('vlDecodeTokensPerSec')} "
        f"text={metrics['vlTextCheck']} hwm={metrics['memoryPeakResidentMB']}MB "
        f"batt={before['batteryTempC']}->{after['batteryTempC']}C thermal={before['thermal']}->{after['thermal']} | {reply[:80]!r}")
    return ok


def resolve_model(model_id, fname, model_dir):
    """-> (local_path, revision, hf_verified, repo_manifest_path) or None when not staged.
    HF cache snapshot (revision = snapshot dir; the path keeps the .litertlm extension the
    engine sniffs) or VL_MODEL_DIR/<file> with an HF_SHA256SUMS line proving the bytes are
    the Hub's (hub-bytes-need-lfs-sha-check)."""
    org, name = model_id.split("/", 1)
    cands = glob.glob(os.path.expanduser(f"~/.cache/huggingface/hub/models--{org}--{name}/snapshots/*/{fname}"))
    mcands = glob.glob(os.path.expanduser(f"~/.cache/huggingface/hub/models--{org}--{name}/snapshots/*/litertlm_manifest.json"))
    manifest = mcands[0] if mcands else None
    if cands:
        return cands[0], cands[0].split("/snapshots/")[1].split("/")[0], True, manifest
    local = os.path.join(model_dir, fname)
    if os.path.exists(local):
        verified = None
        sums = os.path.join(model_dir, "HF_SHA256SUMS")
        if os.path.exists(sums):
            for line in open(sums):
                parts = line.split()
                if len(parts) == 3 and parts[1] == model_id and parts[2] == fname:
                    verified = (parts[0] == sha256(local))
        if verified is not True:
            sys.exit(f"{local}: local copy is not verified against the Hub's LFS sha256 (HF_SHA256SUMS) — refusing")
        return os.path.realpath(local), "local", True, manifest
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cells")
    ap.add_argument("--campaign", required=True, help="results/raw/<campaign>-android/")
    ap.add_argument("--serial", default=os.environ.get("BENCH_ANDROID_SERIAL"))
    ap.add_argument("--runs", type=int, default=None, help="override runs= of every cell")
    ap.add_argument("--only", default=None, help="substring filter on model id (smoke)")
    ap.add_argument("--backend", default=None, choices=["cpu", "gpu"], help="run only this backend's rows (retakes)")
    # 45 s between launches / 90 s between cells: the ASR leg's protocol on this phone
    # (2026-09-19: at 5 s the CPU cells drifted +12-27 % from launch 1 to 3; at 45 s
    # they repeat within +-1 %, spread-rule).
    ap.add_argument("--pause", type=float, default=45.0)
    ap.add_argument("--timeout", type=float, default=900.0)
    ap.add_argument("--base-cooldown", type=float, default=90.0)
    args = ap.parse_args()
    if not args.serial:
        sys.exit("--serial or BENCH_ANDROID_SERIAL is required (never guess a phone)")
    args.out = os.path.join(REPO, "results", "raw", f"{args.campaign}-android")
    os.makedirs(args.out, exist_ok=True)
    runlog = open(os.path.join(args.out, "runlog.txt"), "a")

    def log(msg):
        line = f"{dt.datetime.now().strftime('%H:%M:%S')} {msg}"
        print(line, flush=True); runlog.write(line + "\n"); runlog.flush()

    runner_dir = os.path.abspath(os.environ.get("VL_ANDROID_RUNNER_DIR", DEFAULT_RUNNER))
    model_dir = os.path.abspath(os.environ.get("VL_MODEL_DIR", os.path.join(REPO, ".build", "vl-models")))
    runner = os.path.join(runner_dir, "litert_lm_advanced_main")
    if not os.path.exists(runner):
        sys.exit(f"no android litert_lm_advanced_main at {runner} (docs/vl-response-v1.md, Android leg: build + stage)")
    ver_lines = open(os.path.join(runner_dir, "ENGINE_VERSION")).read().strip().splitlines() if os.path.exists(os.path.join(runner_dir, "ENGINE_VERSION")) else ["unknown"]
    engine_version = ver_lines[0].strip()
    so_files = sorted(glob.glob(os.path.join(runner_dir, "*.so")))
    engine_artifact = (f"litert_lm_advanced_main (android_arm64) sha256:{sha256(runner)} "
                       f"(bazel build //runtime/engine:litert_lm_advanced_main, LiteRT-LM {engine_version}"
                       + (f"; {' '.join(l.strip() for l in ver_lines[1:])}" if len(ver_lines) > 1 else "") + "); "
                       + "; ".join(f"{os.path.basename(s)} sha256:{sha256(s)[:16]}…" for s in so_files))

    # cells
    cells, skipped = [], []
    for raw in open(args.cells):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        plat, rt, mid, task, opts = parse_line(line)
        if plat != "android" or not task.startswith("vl-"):
            continue
        if args.only and args.only not in mid:
            continue
        if args.backend and opts.get("backend") != args.backend:
            continue
        if opts.get("exclude"):
            log(f"SKIPPED {rt} {mid} {task} backend={opts.get('backend')} reason={opts['exclude']}")
            skipped.append(f"SKIPPED {rt} {mid} {task} backend={opts.get('backend')} reason={opts['exclude']}")
            continue
        if task not in TASK_SETS:
            sys.exit(f"unknown vl task {task!r}; known: {sorted(TASK_SETS)}")
        found = resolve_model(mid, opts["file"], model_dir)
        if found is None:
            log(f"SKIPPED {rt} {mid} {task} backend={opts['backend']} reason=model-file-not-staged")
            skipped.append(f"SKIPPED {rt} {mid} {task} backend={opts['backend']} reason=model-file-not-staged")
            continue
        local, rev, _, manifest_path = found
        manifest = json.load(open(manifest_path)) if manifest_path and os.path.exists(manifest_path) else None
        cells.append({"runtime": rt, "model_id": mid, "task": task, "backend": opts["backend"], "file": opts["file"],
                      "runs": int(opts.get("runs", 3)), "cooldown": float(opts.get("cooldown", args.base_cooldown)),
                      "local_path": local, "revision": rev, "sha256": sha256(local),
                      "quant_label": quant_label(opts["file"], manifest),
                      "repo_manifest_rel": (os.path.relpath(manifest_path, os.path.expanduser("~")) if manifest else None),
                      "slug": (f"{rt}_{mid}_{task}".replace("/", "_").replace(".", "_") + f"_{opts['backend']}")})
    if skipped:
        with open(os.path.join(args.out, "SKIPPED.txt"), "a") as f:
            f.write("\n".join(skipped) + "\n")
    if not cells:
        sys.exit("no android vl-* cells matched (or none staged)")
    if args.runs:
        for c in cells:
            c["runs"] = args.runs
    if len({c["task"] for c in cells}) != 1:
        sys.exit("one task per campaign (the image set and prompt are per task)")

    # image set + request
    set_name = TASK_SETS[cells[0]["task"]]
    set_dir = os.path.join(REPO, "evaldata", "vl", set_name)
    man_path = os.path.join(set_dir, "manifest.json")
    man = json.load(open(man_path))
    image_path = os.path.join(set_dir, man["image"]["file"])
    image_sha = sha256(image_path)
    if image_sha != man["image"]["sha256"]:
        sys.exit(f"image set mismatch: {man['image']['file']} sha256 {image_sha} != manifest {man['image']['sha256']}")
    ctx = {"engine_version": engine_version, "engine_artifact": engine_artifact,
           "set_name": set_name, "image_name": man["image"]["file"], "image_rel": os.path.relpath(image_path, REPO),
           "image_sha256": image_sha, "image_w": man["image"]["width"], "image_h": man["image"]["height"],
           "manifest_sha256": sha256(man_path),
           "prompt": man["request"]["prompt"], "max_output_tokens": int(man["request"]["max_output_tokens"]),
           "keywords": [w.lower() for w in man["text_check"]["any_of"]],
           "device": device_info(args.serial)}

    with open(os.path.join(args.out, "session_provenance.txt"), "a") as f:
        f.write(f"session start {dt.datetime.now().strftime('%F %T')}\ncells: {args.cells}\nserial: {args.serial}\n"
                f"device: {json.dumps(ctx['device'])}\nengine: {engine_version}\nartifact: {engine_artifact}\n"
                f"image: {ctx['image_name']} sha256 {image_sha} {ctx['image_w']}x{ctx['image_h']}\n"
                f"request: {ctx['prompt']!r} max_output_tokens={ctx['max_output_tokens']}\n"
                f"protocol: pause={args.pause}s base-cooldown={args.base_cooldown}s timeout={args.timeout}s\n")
    log(f"device {ctx['device']} — {phone_state(args.serial)}")

    # stage
    log("staging on the phone")
    sh(args.serial, f"mkdir -p {DEV_DIR}/bin {DEV_DIR}/models {DEV_DIR}/images {DEV_DIR}/cache {DEV_DIR}/logs")
    push_if_needed(args.serial, runner, f"{DEV_DIR}/bin/litert_lm_advanced_main", log)
    sh(args.serial, f"chmod 755 {DEV_DIR}/bin/litert_lm_advanced_main")
    for s in so_files:
        push_if_needed(args.serial, s, f"{DEV_DIR}/bin/{os.path.basename(s)}", log)
    push_if_needed(args.serial, image_path, f"{DEV_DIR}/images/{ctx['image_name']}", log)
    got = sh(args.serial, f"sha256sum {DEV_DIR}/images/{ctx['image_name']}").split()
    if not got or got[0] != image_sha:
        sys.exit(f"image sha256 on the phone {got[:1]} != {image_sha}")
    seen = {}
    for c in cells:
        if c["file"] not in seen:
            pushed = push_if_needed(args.serial, c["local_path"], f"{DEV_DIR}/models/{c['file']}", log)
            out = sh(args.serial, f"sha256sum {DEV_DIR}/models/{c['file']}", timeout=600).split()
            seen[c["file"]] = out[0] if out else None
            if seen[c["file"]] != c["sha256"]:
                sys.exit(f"remote sha256 mismatch for {c['file']}: {seen[c['file']]} vs {c['sha256']}")
            log(f"  {c['file']} sha256 verified on the phone{' (pushed)' if pushed else ''}")
            # the engine refuses a missing cache dir instead of creating it
            sh(args.serial, f"mkdir -p {DEV_DIR}/cache/{c['file']}")
        c["remote_sha256"] = seen[c["file"]]

    log("cooling down after the pushes")
    wait_nominal(args.serial, log)
    ok_all = True
    first = True
    for c in cells:
        if not first:
            log(f"cooldown {c['cooldown']:.0f}s"); time.sleep(c["cooldown"])
        first = False
        log(f"CELL {c['runtime']} / {c['model_id']} / {c['task']} backend={c['backend']} runs={c['runs']}")
        failed = 0
        for r in range(1, c["runs"] + 1):
            if r > 1:
                time.sleep(args.pause)
            ok = one_run(args, ctx, c, r, log)
            failed += 0 if ok else 1
        if failed:
            ok_all = False
            with open(os.path.join(args.out, "FAILURES.txt"), "a") as f:
                f.write(f"FAIL {c['runtime']} {c['model_id']} {c['task']} backend={c['backend']} runs_failed={failed}/{c['runs']}\n")
    log(f"done: {args.out}")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
