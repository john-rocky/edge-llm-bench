#!/usr/bin/env python3
"""ASR real-time-factor cells on an Android phone over adb (task family `asr-rtf-*`), v1.

The Android leg of docs/asr-rtf-v1.md: the same LiteRT-LM `omni/asr` CLI
(`asr_runner`, built with `--config=android_arm64`), the same stream and protocol
as scripts/asr_rtf_mac.py, one process launch per run through `adb shell`. This
script is its own mini-runner: it reads the `android` `asr-rtf-*` rows of a cells
file, stages the runner + GPU .so files + models + tokenizers + the stream WAV
under /data/local/tmp/edge-llm-bench/asr, gates every launch on the phone's
thermal status (0 = nominal, android/bench/device_probe.py vocabulary) and
writes the same record shape as the Mac driver into results/raw/<campaign>/.

Timing: the runner logs `Starting speech recognition` / `Finished speech
recognition` with absl microsecond timestamps on the PHONE clock, and the shell
wrapper prints $EPOCHREALTIME before exec — so loadTimeSeconds and
asrProcessingSeconds are device-clock differences (no adb latency in them).
First-text latency is host-side arrival relative to the host-side arrival of the
`Starting` line (both through the same adb stream).

Usage:
  scripts/asr_rtf_android.py matrices/asr-rtf-v1.cells --campaign 2026-09-19-asr-rtf-v1-s26
  (writes results/raw/<campaign>-android/; BENCH_ANDROID_SERIAL or --serial picks the phone)

Environment:
  ASR_ANDROID_RUNNER_DIR  asr_runner (android) + *.so + model_metadata.json + ENGINE_VERSION
                          (default .build/asr-runner-1dadd00c-android)
  ASR_MODEL_DIR           tokenizers as <model_name>_tokenizer.json (default .build/asr-models)
  ASR_NUM_THREADS / ASR_OVERLAP_RATIO / ASR_TEXT_MERGER  protocol overrides (4 / 0.4 / timestamp)
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
from asr_rtf_mac import (DISPLAY, HARNESS_STAMP, MODEL_NAMES, TASK_SETS,  # noqa: E402
                         build_stream, normalize, quant_label, sha256, wer_counts)
from device_probe import adb, battery, device_info, thermal_status  # noqa: E402
from validate_cells import parse_line  # noqa: E402

DEV_DIR = "/data/local/tmp/edge-llm-bench/asr"
LOG_SIG = re.compile(r"(I0000 |W0000 |E0000 |F0000 |VERBOSE: |DEBUG: |INFO: |WARNING: |ERROR: |FATAL: |=== Source|\s+@\s+0x|omni/asr/|T0=|EXIT=)")
ABSL_TS = re.compile(r"^[IWEF]0000 00:00:(\d+\.\d+)")


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
    return {"thermalStatusRaw": raw, "thermal": name, "batteryTempC": temp,
            "batteryLevel": bat.get("batteryLevel"), "batteryState": bat.get("batteryState"),
            "cpuFreqCapped": capped, "cpuMaxFreqKHz": caps[1::2]}


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


def one_run(args, ctx, cell, run_idx, log):
    serial = args.serial
    slug = cell["slug"]
    remote_model = f"{DEV_DIR}/models/{cell['file']}"
    cmd = (f"cd {DEV_DIR}/bin && export LD_LIBRARY_PATH={DEV_DIR}/bin && echo T0=$EPOCHREALTIME && "
           f"./asr_runner --model_name {cell['model_name']} --metadata_path {DEV_DIR}/bin/model_metadata.json "
           f"--model_path {remote_model} --cache_dir {DEV_DIR}/models --backend {cell['backend']} "
           f"--num_threads {ctx['num_threads']} --overlap_ratio {ctx['overlap_ratio']} "
           f"--text_merger_type {ctx['text_merger']} --audio_path {DEV_DIR}/audio/{ctx['stream_name']} 2>&1; "
           f"echo; echo EXIT=$? T1=$EPOCHREALTIME")
    before = wait_nominal(serial, log)
    events, lock = [], threading.Lock()
    peak = {"kb": 0}
    stop = threading.Event()

    def reader(stream):
        fd = stream.fileno()
        while True:
            try:
                chunk = os.read(fd, 65536)
            except OSError:
                break
            if not chunk:
                break
            with lock:
                events.append((time.monotonic(), chunk.decode("utf-8", "replace")))

    def mem_poll():
        while not stop.is_set():
            try:
                out = subprocess.check_output(
                    ["adb", "-s", serial, "shell", "p=$(pidof asr_runner); [ -n \"$p\" ] && grep VmHWM /proc/$p/status"],
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
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    th = threading.Thread(target=reader, args=(p.stdout,), daemon=True); th.start()
    mt = threading.Thread(target=mem_poll, daemon=True); mt.start()
    while p.poll() is None:
        time.sleep(0.2)
        if time.monotonic() - t0 > args.timeout:
            p.kill()
            sh(serial, "pkill -f asr_runner || true")
    th.join(timeout=5); stop.set(); mt.join(timeout=3)
    after = phone_state(serial)

    # Split the merged stream into log lines and transcript fragments. Lines are
    # split on the JOINED stream (an adb read boundary can fall mid-line), and
    # each line's host arrival time is that of the read that delivered its
    # first byte.
    raw = "".join(text for _, text in events)
    starts = []
    pos = 0
    for mono, text in events:
        starts.append((pos, mono)); pos += len(text)

    def arrival(off):
        t = starts[0][1] if starts else None
        for s, mono in starts:
            if s <= off:
                t = mono
            else:
                break
        return t

    log_lines, transcript_parts = [], []
    t_start_host = t_first_host = None
    off = 0
    for line in raw.splitlines(keepends=True):
        body = line.rstrip("\r\n")
        m = LOG_SIG.search(body)
        frag, logpart = (body, "") if not m else (body[:m.start()], body[m.start():])
        if frag.strip():
            transcript_parts.append(frag.strip())
            if t_first_host is None:
                t_first_host = arrival(off)
        if logpart:
            log_lines.append(logpart)
            if "Starting speech recognition" in logpart and t_start_host is None:
                t_start_host = arrival(off + (m.start() if m else 0))
        off += len(line)
    transcript = re.sub(r"\s+", " ", " ".join(transcript_parts)).strip()
    t0_dev = t1_dev = ts_start = ts_fin = None
    rc = None
    for l in log_lines:
        if l.startswith("T0="):
            t0_dev = float(l[3:].split()[0])
        elif l.startswith("EXIT="):
            m = re.match(r"EXIT=(\d+) T1=([\d.]+)", l)
            if m:
                rc, t1_dev = int(m.group(1)), float(m.group(2))
        else:
            m = ABSL_TS.match(l)
            if m and "Starting speech recognition" in l and ts_start is None:
                ts_start = float(m.group(1))
            elif m and "Finished speech recognition" in l:
                ts_fin = float(m.group(1))

    logs = os.path.join(args.out, "logs"); os.makedirs(logs, exist_ok=True)
    with open(os.path.join(logs, f"{slug}_run{run_idx}.stderr.log"), "w") as f:
        f.write(f"# adb -s {serial} shell '{cmd}'\n# exit={rc}\n# raw merged stream follows (stdout text + stderr logs)\n")
        f.write(raw)
    with open(os.path.join(logs, f"{slug}_run{run_idx}.stdout.txt"), "w") as f:
        f.write(transcript + "\n")

    metrics = {"coldRun": True, "harnessStamp": HARNESS_STAMP, "exitCode": rc,
               "memoryPeakResidentMB": round(peak["kb"] / 1024.0, 1),
               "initialThermalState": before["thermal"], "finalThermalState": after["thermal"],
               "batteryTempInitialC": before["batteryTempC"], "batteryTempFinalC": after["batteryTempC"],
               "asrAudioSeconds": round(ctx["audio_s"], 3)}
    if t0_dev is not None and ts_start is not None:
        metrics["loadTimeSeconds"] = round(ts_start - t0_dev, 3)
    if ts_start is not None and ts_fin is not None:
        proc = ts_fin - ts_start
        metrics["asrProcessingSeconds"] = round(proc, 3)
        metrics["asrRealTimeFactor"] = round(proc / ctx["audio_s"], 4)
    if t_start_host is not None and t_first_host is not None and t_first_host >= t_start_host:
        metrics["asrFirstTextLatencyMS"] = round((t_first_host - t_start_host) * 1000.0, 1)
    if t0_dev is not None and t1_dev is not None:
        metrics["totalWallSeconds"] = round(t1_dev - t0_dev, 3)
    hyp = normalize(transcript)
    if hyp:
        s, d, i, n = wer_counts(ctx["ref_words"], hyp)
        metrics.update({"asrWordErrorRate": round((s + d + i) / n, 4), "asrSubstitutions": s,
                        "asrDeletions": d, "asrInsertions": i,
                        "asrReferenceWordCount": n, "asrHypothesisWordCount": len(hyp)})
    ok = rc == 0 and "asrRealTimeFactor" in metrics
    rec = {
        "schemaVersion": 1, "id": str(uuid.uuid4()).upper(),
        "timestamp": wall0.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "runtime": f"litert-lm-{cell['backend']}",
        "engineVersion": ctx["engine_version"], "engineArtifact": ctx["engine_artifact"],
        "model": {"id": cell["model_id"], "hfRepoId": cell["model_id"],
                  "displayName": DISPLAY.get(cell["model_name"], cell["model_name"]),
                  "primaryFile": cell["file"], "file": cell["file"], "hfFilePatterns": [cell["file"]],
                  "hfRevision": cell["revision"], "quantization": quant_label(cell["model_name"], cell["file"]),
                  "onDiskSizeMB": round(os.path.getsize(cell["local_path"]) / 1e6, 1), "sha256": cell["sha256"]},
        "modelRevision": cell["revision"],
        "task": cell["task"],
        "device": dict(ctx["device"], batteryState=before["batteryState"], batteryLevel=before["batteryLevel"],
                       cpuMaxFreqKHz=before["cpuMaxFreqKHz"], cpuFreqCapped=before["cpuFreqCapped"]),
        "conditions": {"asrChunkMilliseconds": cell["chunk_ms"], "asrOverlapRatio": ctx["overlap_ratio"],
                       "asrTextMerger": ctx["text_merger"], "asrNumThreads": ctx["num_threads"],
                       "gpuPrecision": "fp32 (AsrEngine sets GpuOptions::Precision::kFp32)" if cell["backend"] == "gpu" else None,
                       "sampler": "engine default (ASR decoders are deterministic)",
                       "warm": False, "unplugged": before["batteryState"] != "charging",
                       "thermalInitial": before["thermal"], "thermalFinal": after["thermal"]},
        "metrics": metrics,
        "outputSample": transcript[:200], "transcript": transcript,
        "provenance": {"audioSet": ctx["set_name"], "audioStreamSha256": ctx["stream_sha256"],
                       "metadataJsonSha256": ctx["metadata_sha256"],
                       "tokenizerSha256": cell["tokenizer_sha256"], "modelSha256": cell["sha256"],
                       "remoteModelSha256": cell.get("remote_sha256"),
                       "deviceBefore": before, "deviceAfter": after,
                       "command": cmd, "stderrLog": os.path.relpath(os.path.join(logs, f"{slug}_run{run_idx}.stderr.log"), REPO)},
    }
    with open(os.path.join(args.out, f"{slug}.jsonl"), "a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    log(f"{'OK ' if ok else 'FAIL'} run {run_idx}: exit={rc} load={metrics.get('loadTimeSeconds')}s "
        f"proc={metrics.get('asrProcessingSeconds')}s RTF={metrics.get('asrRealTimeFactor')} "
        f"WER={metrics.get('asrWordErrorRate')} hwm={metrics['memoryPeakResidentMB']}MB "
        f"batt={before['batteryTempC']}->{after['batteryTempC']}C thermal={before['thermal']}->{after['thermal']}")
    return ok


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cells")
    ap.add_argument("--campaign", required=True, help="results/raw/<campaign>-android/")
    ap.add_argument("--serial", default=os.environ.get("BENCH_ANDROID_SERIAL"))
    ap.add_argument("--runs", type=int, default=None, help="override runs= of every cell")
    ap.add_argument("--only", default=None, help="substring filter on model id (smoke)")
    ap.add_argument("--backend", default=None, choices=["cpu", "gpu"], help="run only this backend's rows (retakes)")
    # 45 s between launches / 90 s between cells: at 5 s pauses the S26's CPU
    # cells drifted +12-27 % from launch 1 to 3 (2026-09-19 sitting 1, kept as
    # .jsonl.attempt1); at 45 s they repeat within +-1 % (spread-rule).
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

    runner_dir = os.path.abspath(os.environ.get("ASR_ANDROID_RUNNER_DIR", os.path.join(REPO, ".build", "asr-runner-1dadd00c-android")))
    model_dir = os.path.abspath(os.environ.get("ASR_MODEL_DIR", os.path.join(REPO, ".build", "asr-models")))
    runner = os.path.join(runner_dir, "asr_runner")
    if not os.path.exists(runner):
        sys.exit(f"no android asr_runner at {runner}")
    meta_path = os.path.join(runner_dir, "model_metadata.json")
    meta = json.load(open(meta_path))
    ver_file = os.path.join(runner_dir, "ENGINE_VERSION")
    engine_version = open(ver_file).read().strip() if os.path.exists(ver_file) else "unknown"
    so_files = sorted(glob.glob(os.path.join(runner_dir, "*.so")))
    engine_artifact = (f"asr_runner (android_arm64) sha256:{sha256(runner)} (bazel build //omni/asr:asr_runner, LiteRT-LM {engine_version}); "
                       + "; ".join(f"{os.path.basename(s)} sha256:{sha256(s)[:16]}…" for s in so_files))

    # cells
    cells = []
    for raw in open(args.cells):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        plat, rt, mid, task, opts = parse_line(line)
        if plat != "android" or not task.startswith("asr-rtf-"):
            continue
        if args.only and args.only not in mid:
            continue
        if args.backend and opts.get("backend") != args.backend:
            continue
        if opts.get("exclude"):
            log(f"SKIPPED {rt} {mid} {task} reason={opts['exclude']}"); continue
        model_name = MODEL_NAMES[mid]
        org, name = mid.split("/", 1)
        cands = glob.glob(os.path.expanduser(f"~/.cache/huggingface/hub/models--{org}--{name}/snapshots/*/{opts['file']}"))
        if not cands:
            sys.exit(f"{opts['file']} not in the HF cache (hf download {mid} {opts['file']})")
        local = os.path.realpath(cands[0]); rev = cands[0].split("/snapshots/")[1].split("/")[0]
        tok = os.path.join(model_dir, f"{model_name}_tokenizer.json")
        cells.append({"runtime": rt, "model_id": mid, "task": task, "backend": opts["backend"], "file": opts["file"],
                      "runs": int(opts.get("runs", 3)), "cooldown": float(opts.get("cooldown", args.base_cooldown)),
                      "model_name": model_name, "local_path": local, "revision": rev, "sha256": sha256(local),
                      "tokenizer": tok if os.path.exists(tok) else None,
                      "tokenizer_sha256": sha256(tok) if os.path.exists(tok) else None,
                      "chunk_ms": meta[model_name].get("inputMilliseconds"),
                      "slug": (f"{rt}_{mid}_{task}".replace("/", "_").replace(".", "_") + f"_{opts['backend']}")})
    if not cells:
        sys.exit("no android asr-rtf-* cells matched")
    if args.runs:
        for c in cells:
            c["runs"] = args.runs

    # stream + protocol
    task_set = TASK_SETS[cells[0]["task"]]
    stream_path, stream_sha, audio_s, reference, _ = build_stream(task_set)
    ctx = {"engine_version": engine_version, "engine_artifact": engine_artifact,
           "num_threads": int(os.environ.get("ASR_NUM_THREADS", "4")),
           "overlap_ratio": float(os.environ.get("ASR_OVERLAP_RATIO", "0.4")),
           "text_merger": os.environ.get("ASR_TEXT_MERGER", "timestamp"),
           "stream_name": os.path.basename(stream_path), "stream_sha256": stream_sha, "audio_s": audio_s,
           "ref_words": normalize(reference), "set_name": task_set, "metadata_sha256": sha256(meta_path),
           "device": device_info(args.serial)}

    # provenance header
    with open(os.path.join(args.out, "session_provenance.txt"), "a") as f:
        f.write(f"session start {dt.datetime.now().strftime('%F %T')}\ncells: {args.cells}\nserial: {args.serial}\n"
                f"device: {json.dumps(ctx['device'])}\nengine: {engine_version}\nartifact: {engine_artifact}\n"
                f"stream: {ctx['stream_name']} sha256 {stream_sha} {audio_s:.3f} s\n"
                f"protocol: threads={ctx['num_threads']} overlap={ctx['overlap_ratio']} merger={ctx['text_merger']}\n")
    log(f"device {ctx['device']} — {phone_state(args.serial)}")

    # stage
    log("staging on the phone")
    sh(args.serial, f"mkdir -p {DEV_DIR}/bin {DEV_DIR}/models {DEV_DIR}/audio {DEV_DIR}/logs")
    push_if_needed(args.serial, runner, f"{DEV_DIR}/bin/asr_runner", log)
    sh(args.serial, f"chmod 755 {DEV_DIR}/bin/asr_runner")
    for s in so_files:
        push_if_needed(args.serial, s, f"{DEV_DIR}/bin/{os.path.basename(s)}", log)
    push_if_needed(args.serial, meta_path, f"{DEV_DIR}/bin/model_metadata.json", log)
    push_if_needed(args.serial, stream_path, f"{DEV_DIR}/audio/{ctx['stream_name']}", log)
    seen = set()
    for c in cells:
        if c["file"] not in seen:
            seen.add(c["file"])
            pushed = push_if_needed(args.serial, c["local_path"], f"{DEV_DIR}/models/{c['file']}", log)
            out = sh(args.serial, f"sha256sum {DEV_DIR}/models/{c['file']}", timeout=300).split()
            c["remote_sha256"] = out[0] if out else None
            if c["remote_sha256"] != c["sha256"]:
                sys.exit(f"remote sha256 mismatch for {c['file']}: {c['remote_sha256']} vs {c['sha256']}")
            log(f"  {c['file']} sha256 verified on the phone{' (pushed)' if pushed else ''}")
        else:
            c["remote_sha256"] = next(x["remote_sha256"] for x in cells if x["file"] == c["file"] and x.get("remote_sha256"))
        if c["tokenizer"]:
            push_if_needed(args.serial, c["tokenizer"], f"{DEV_DIR}/models/{c['model_name']}_tokenizer.json", log)
        elif meta[c["model_name"]].get("tokenizerUrl"):
            log(f"WARNING: no tokenizer staged for {c['model_name']} — the runner would need curl on the phone")

    log("cooling down after the pushes")
    wait_nominal(args.serial, log)
    ok_all = True
    first = True
    for c in cells:
        if not first:
            log(f"cooldown {c['cooldown']:.0f}s"); time.sleep(c["cooldown"])
        first = False
        log(f"CELL {c['runtime']} / {c['model_id']} / {c['task']} backend={c['backend']} runs={c['runs']}")
        for r in range(1, c["runs"] + 1):
            if r > 1:
                time.sleep(args.pause)
            ok_all &= one_run(args, ctx, c, r, log)
    log(f"done: {args.out}")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
