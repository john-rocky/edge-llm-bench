#!/usr/bin/env python3
"""ASR real-time-factor cells on the Mac (task family `asr-rtf-*`), v1.

One process launch per run of LiteRT-LM's own ASR CLI (`//omni/asr:asr_runner`,
the C++ engine behind the Kotlin ASR API) over ONE stream WAV built from a pinned
utterance set (evaldata/asr/<set>/manifest.json), through the engine's default
streaming protocol: fixed chunk = the model's export window (5 s, whisper 30 s),
40 % overlap, `timestamp` text merger, 4 CPU threads, GPU precision fp32
(all engine defaults; each is stamped in the record's `conditions`).

Per run the record carries (metrics):
  asrRealTimeFactor    = asrProcessingSeconds / asrAudioSeconds   (< 1 = faster than real time)
  asrProcessingSeconds = wall clock between the runner's "Starting speech
                         recognition" and "Finished speech recognition" log lines
                         (the whole chunk loop incl. flush; for whisper this
                         includes the decoder's lazy first-chunk init — engine
                         behaviour, not subtracted)
  loadTimeSeconds      = process start -> "Starting" (model load + compile)
  asrFirstTextLatencyMS, asrWordErrorRate (+ S/D/I counts) vs the manifest
  reference, memoryPeakResidentMB (ps sampling), coldRun = true (fresh process).

Usage (normally via scripts/bench_matrix_mac.sh, which dispatches asr-rtf-* cells here):
  scripts/asr_rtf_mac.py --model-id litert-community/moonshine-tiny \
      --file moonshine_tiny_5s_i8.tflite --backend cpu --runs 3 \
      --task asr-rtf-librispeech-82s --output OUT/<slug>.jsonl --campaign-dir OUT

Environment:
  ASR_RUNNER_DIR   dir with asr_runner + model_metadata.json + the Metal dylibs
                   (default .build/asr-runner-<tag>; see docs/asr-rtf-v1.md)
  ASR_MODEL_DIR    the runner's cache_dir: <model_name>_tokenizer.json pre-staged
                   (default .build/asr-models)
  ASR_ENGINE_VERSION  stamped as engineVersion (default: ASR_RUNNER_DIR/ENGINE_VERSION file)
  ASR_NUM_THREADS / ASR_OVERLAP_RATIO / ASR_TEXT_MERGER  protocol overrides
                   (defaults 4 / 0.4 / timestamp = the runner's own defaults)
"""
import argparse
import datetime as dt
import glob
import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import time
import uuid
import wave

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HARNESS_STAMP = "asr-rtf-v1-2026-09-19"

# HF repo id -> model_name in LiteRT-LM omni/asr/model_metadata.json
MODEL_NAMES = {
    "litert-community/moonshine-tiny": "moonshine-tiny",
    "litert-community/whisper-tiny": "whisper-tiny",
    "litert-community/parakeet-tdt-0.6b-v3": "parakeet-tdt-0.6b-v3",
    "litert-community/parakeet-ctc-0.6b": "parakeet-ctc-0.6b",
    "litert-community/Qwen3-ASR-0.6B": "qwen3-asr-0.6b",
    "litert-community/TinyGemma-ASR": "tinygemma-asr",
}
DISPLAY = {
    "moonshine-tiny": "Moonshine Tiny (27M)",
    "whisper-tiny": "Whisper tiny (39M)",
    "parakeet-tdt-0.6b-v3": "Parakeet TDT 0.6B v3",
    "qwen3-asr-0.6b": "Qwen3-ASR-0.6B",
}
# Task id -> utterance set under evaldata/asr/
TASK_SETS = {
    "asr-rtf-librispeech-82s": "librispeech-dev-clean-1272-82s",
}


def quant_label(model_name, fname):
    """quant-per-arm-rule / quant-label-rule: say what the file name says and no more."""
    if "_f32" in fname:
        return "f32 (file name)"
    if "_i8" in fname:
        if model_name == "moonshine-tiny":
            return "i8: f32 encoder + dynamic-range int8 decoder (model card)"
        return "i8 (dynamic-range int8 per the file name; the model card has no recipe text)"
    return "unstated (file name carries no recipe)"


def sha256(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(chunk), b""):
            h.update(b)
    return h.hexdigest()


def sh(cmd):
    try:
        return subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ""


def host_snapshot():
    """load, CPU speed limit (pmset), foreign processes > 20 % CPU — disclose-hw-state."""
    load = sh(["sysctl", "-n", "vm.loadavg"])
    therm = sh(["pmset", "-g", "therm"])
    m = re.search(r"CPU_Speed_Limit\s*=\s*(\d+)", therm)
    limit = int(m.group(1)) if m else None
    thermal = "nominal" if (limit is None or limit >= 100) else f"throttled(cpu_speed_limit={limit})"
    others = []
    me = os.getpid()
    for line in sh(["ps", "-Ao", "pcpu,pid,comm", "-r"]).splitlines()[1:12]:
        parts = line.split(None, 2)
        if len(parts) < 3:
            continue
        try:
            pc, pid = float(parts[0]), int(parts[1])
        except ValueError:
            continue
        if pc >= 20.0 and pid != me:
            others.append(f"{os.path.basename(parts[2])}:{pc:.0f}%")
    return {"load": load, "thermal": thermal, "cpuSpeedLimit": limit, "others": others}


def device_info():
    mem_b = int(sh(["sysctl", "-n", "hw.memsize"]) or 0)
    return {
        "modelIdentifier": sh(["sysctl", "-n", "hw.model"]),
        "chip": sh(["sysctl", "-n", "machdep.cpu.brand_string"]),
        "systemName": "macOS",
        "systemVersion": f"Version {sh(['sw_vers', '-productVersion'])} (Build {sh(['sw_vers', '-buildVersion'])})",
        "processorCount": int(sh(["sysctl", "-n", "hw.ncpu"]) or 0),
        "physicalMemoryMB": mem_b // (1024 * 1024),
        "batteryState": "unknown",
        "buildConfiguration": "Release",
    }


# ---------------------------------------------------------------- audio set
def build_stream(set_name):
    """Concatenate the manifest's utterances (pinned sha256) into one stream WAV."""
    d = os.path.join(REPO, "evaldata", "asr", set_name)
    man = json.load(open(os.path.join(d, "manifest.json")))
    by_utt = {u["utterance"]: u for u in man["utterances"]}
    out_dir = os.path.join(REPO, ".build", "asr-audio")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"{set_name}.wav")
    frames = bytearray()
    for utt in man["stream"]["order"]:
        u = by_utt[utt]
        p = os.path.join(d, u["file"])
        got = sha256(p)
        if got != u["sha256"]:
            sys.exit(f"audio set mismatch: {u['file']} sha256 {got} != manifest {u['sha256']}")
        w = wave.open(p, "rb")
        assert (w.getframerate(), w.getnchannels(), w.getsampwidth()) == (16000, 1, 2), p
        frames += w.readframes(w.getnframes())
        w.close()
    wo = wave.open(out, "wb")
    wo.setnchannels(1); wo.setsampwidth(2); wo.setframerate(16000)
    wo.writeframes(bytes(frames))
    wo.close()
    n = len(frames) // 2
    if n != man["stream"]["frames"]:
        sys.exit(f"stream frames {n} != manifest {man['stream']['frames']}")
    return out, sha256(out), n / 16000.0, man["stream"]["reference"], man


# ---------------------------------------------------------------- WER
def normalize(text):
    t = text.lower().replace("-", " ")
    t = re.sub(r"[^a-z0-9' ]+", " ", t)
    return t.split()


def wer_counts(ref, hyp):
    """Levenshtein over words -> (S, D, I, N_ref)."""
    n, m = len(ref), len(hyp)
    # dp[i][j] = (cost, S, D, I)
    prev = [(j, 0, 0, j) for j in range(m + 1)]
    for i in range(1, n + 1):
        cur = [(i, 0, i, 0)]
        for j in range(1, m + 1):
            if ref[i - 1] == hyp[j - 1]:
                cand = [(prev[j - 1][0],) + prev[j - 1][1:]]
            else:
                cand = [(prev[j - 1][0] + 1, prev[j - 1][1] + 1, prev[j - 1][2], prev[j - 1][3])]
            cand.append((prev[j][0] + 1, prev[j][1], prev[j][2] + 1, prev[j][3]))       # deletion
            cand.append((cur[j - 1][0] + 1, cur[j - 1][1], cur[j - 1][2], cur[j - 1][3] + 1))  # insertion
            cur.append(min(cand))
        prev = cur
    _, s, d, i = prev[m]
    return s, d, i, n


# ---------------------------------------------------------------- one run
LOG_TS = re.compile(r"^[IWEF]\d{4} \d\d:\d\d:(\d+\.\d+)")


def one_run(args, ctx, run_idx):
    runner_dir, model_dir = ctx["runner_dir"], ctx["model_dir"]
    cmd = [os.path.join(runner_dir, "asr_runner"),
           "--model_name", ctx["model_name"],
           "--metadata_path", os.path.join(runner_dir, "model_metadata.json"),
           "--model_path", ctx["model_path"],
           "--cache_dir", model_dir,
           "--backend", args.backend,
           "--num_threads", str(ctx["num_threads"]),
           "--overlap_ratio", str(ctx["overlap_ratio"]),
           "--text_merger_type", ctx["text_merger"],
           "--audio_path", ctx["stream_path"]]
    env = dict(os.environ, DYLD_LIBRARY_PATH=runner_dir)
    host = host_snapshot()
    events = []            # (mono, stream, line)
    lock = threading.Lock()

    def reader(stream, tag):
        # Byte-level reads: the runner prints each chunk's confirmed text with a
        # flush but no newline (only the final flush ends the line), so a
        # readline() loop would time the first text at stream end.
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
        stream.close()

    t0 = time.monotonic()
    wall0 = dt.datetime.now(dt.timezone.utc)
    p = subprocess.Popen(cmd, cwd=runner_dir, env=env, stdin=subprocess.DEVNULL,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    th = [threading.Thread(target=reader, args=(p.stdout, "out"), daemon=True),
          threading.Thread(target=reader, args=(p.stderr, "err"), daemon=True)]
    for t in th:
        t.start()
    peak_rss_kb = 0
    while p.poll() is None:
        rss = sh(["ps", "-o", "rss=", "-p", str(p.pid)])
        try:
            peak_rss_kb = max(peak_rss_kb, int(rss))
        except ValueError:
            pass
        time.sleep(0.2)
        if time.monotonic() - t0 > args.timeout:
            p.kill()
    for t in th:
        t.join(timeout=5)
    t_exit = time.monotonic()
    rc = p.returncode
    host_after = host_snapshot()

    t_start = t_fin = t_first = None
    stdout_parts, stderr_chunks = [], []
    for mono, tag, text in events:
        if tag == "out":
            stdout_parts.append(text)
            if t_first is None and text.strip():
                t_first = mono
        else:
            stderr_chunks.append(text)
            if "Starting speech recognition" in text and t_start is None:
                t_start = mono
            if "Finished speech recognition" in text:
                t_fin = mono
    stderr_lines = "".join(stderr_chunks).splitlines(keepends=True)
    transcript = re.sub(r"\s+", " ", "".join(stdout_parts)).strip()

    slug = args.slug
    logs = os.path.join(args.campaign_dir, "logs")
    os.makedirs(logs, exist_ok=True)
    err_log = os.path.join(logs, f"{slug}_run{run_idx}.stderr.log")
    with open(err_log, "w") as f:
        f.write(f"# cmd: {' '.join(cmd)}\n# DYLD_LIBRARY_PATH={runner_dir}\n# exit={rc}\n")
        f.writelines(stderr_lines)
    with open(os.path.join(logs, f"{slug}_run{run_idx}.stdout.txt"), "w") as f:
        f.write(transcript + "\n")

    metrics = {"coldRun": True, "harnessStamp": HARNESS_STAMP, "exitCode": rc,
               "memoryPeakResidentMB": round(peak_rss_kb / 1024.0, 1),
               "initialThermalState": host["thermal"], "finalThermalState": host_after["thermal"],
               "asrAudioSeconds": round(ctx["audio_s"], 3)}
    if t_start is not None:
        metrics["loadTimeSeconds"] = round(t_start - t0, 3)
    if t_start is not None and t_fin is not None:
        proc = t_fin - t_start
        metrics["asrProcessingSeconds"] = round(proc, 3)
        metrics["asrRealTimeFactor"] = round(proc / ctx["audio_s"], 4)
        if t_first is not None:
            metrics["asrFirstTextLatencyMS"] = round((t_first - t_start) * 1000.0, 1)
    metrics["totalWallSeconds"] = round(t_exit - t0, 3)
    hyp = normalize(transcript)
    if hyp:
        s, d, i, n = wer_counts(ctx["ref_words"], hyp)
        metrics.update({"asrWordErrorRate": round((s + d + i) / n, 4), "asrSubstitutions": s,
                        "asrDeletions": d, "asrInsertions": i,
                        "asrReferenceWordCount": n, "asrHypothesisWordCount": len(hyp)})
    ok = rc == 0 and "asrRealTimeFactor" in metrics

    rec = {
        "schemaVersion": 1,
        "id": str(uuid.uuid4()).upper(),
        "timestamp": wall0.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "runtime": f"{args.runtime}-{args.backend}",
        "engineVersion": ctx["engine_version"],
        "engineArtifact": ctx["engine_artifact"],
        "model": {
            "id": args.model_id, "hfRepoId": args.model_id, "displayName": DISPLAY.get(ctx["model_name"], ctx["model_name"]),
            "primaryFile": args.file, "file": args.file, "hfFilePatterns": [args.file],
            "hfRevision": ctx["model_revision"], "quantization": quant_label(ctx["model_name"], args.file),
            "onDiskSizeMB": round(os.path.getsize(ctx["model_path"]) / 1e6, 1),
            "sha256": ctx["model_sha256"],
        },
        "modelRevision": ctx["model_revision"],
        "task": args.task,
        "device": ctx["device"],
        "conditions": {
            "asrChunkMilliseconds": ctx["chunk_ms"], "asrOverlapRatio": ctx["overlap_ratio"],
            "asrTextMerger": ctx["text_merger"], "asrNumThreads": ctx["num_threads"],
            "gpuPrecision": "fp32 (AsrEngine sets GpuOptions::Precision::kFp32)" if args.backend == "gpu" else None,
            "sampler": "engine default (ASR decoders are deterministic)",
            "warm": False, "unplugged": False,
            "thermalInitial": host["thermal"], "thermalFinal": host_after["thermal"],
        },
        "metrics": metrics,
        "outputSample": transcript[:200],
        "transcript": transcript,
        "provenance": {
            "audioSet": ctx["set_name"], "audioStream": os.path.relpath(ctx["stream_path"], REPO),
            "audioStreamSha256": ctx["stream_sha256"],
            "metadataJsonSha256": ctx["metadata_sha256"], "tokenizerFile": ctx["tokenizer_file"],
            "tokenizerSha256": ctx["tokenizer_sha256"], "modelSha256": ctx["model_sha256"],
            "hostBefore": host, "hostAfter": host_after,
            "command": " ".join(cmd), "stderrLog": os.path.relpath(err_log, REPO),
        },
    }
    with open(args.output, "a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    tag = "OK " if ok else "FAIL"
    print(f"{tag} run {run_idx}: exit={rc} load={metrics.get('loadTimeSeconds')}s "
          f"proc={metrics.get('asrProcessingSeconds')}s RTF={metrics.get('asrRealTimeFactor')} "
          f"WER={metrics.get('asrWordErrorRate')} rss={metrics['memoryPeakResidentMB']}MB "
          f"others={host['others'] or 'none'}", flush=True)
    return ok


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model-id", required=True)
    ap.add_argument("--file", required=True, help="artifact file name inside the HF repo (cells file=)")
    ap.add_argument("--backend", choices=["cpu", "gpu"], required=True)
    ap.add_argument("--task", required=True)
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--runtime", default="litert-lm")
    ap.add_argument("--output", required=True, help="JSONL to append one record per run")
    ap.add_argument("--campaign-dir", required=True)
    ap.add_argument("--pause", type=float, default=5.0, help="seconds between runs")
    ap.add_argument("--timeout", type=float, default=1800.0)
    args = ap.parse_args()

    if args.task not in TASK_SETS:
        sys.exit(f"unknown asr task {args.task!r}; known: {sorted(TASK_SETS)}")
    if args.model_id not in MODEL_NAMES:
        sys.exit(f"{args.model_id}: not in MODEL_NAMES (omni/asr/model_metadata.json names)")
    model_name = MODEL_NAMES[args.model_id]
    runner_dir = os.path.abspath(os.environ.get("ASR_RUNNER_DIR", os.path.join(REPO, ".build", "asr-runner-1dadd00c")))
    model_dir = os.path.abspath(os.environ.get("ASR_MODEL_DIR", os.path.join(REPO, ".build", "asr-models")))
    runner = os.path.join(runner_dir, "asr_runner")
    if not os.access(runner, os.X_OK):
        sys.exit(f"no asr_runner at {runner} (docs/asr-rtf-v1.md: build + stage)")
    meta_path = os.path.join(runner_dir, "model_metadata.json")
    meta = json.load(open(meta_path))
    if model_name not in meta:
        sys.exit(f"{model_name} not in {meta_path}")

    # model file: HF cache snapshot (revision = snapshot dir) or ASR_MODEL_DIR/<file>
    org, name = args.model_id.split("/", 1)
    cands = glob.glob(os.path.expanduser(f"~/.cache/huggingface/hub/models--{org}--{name}/snapshots/*/{args.file}"))
    if cands:
        model_path = os.path.realpath(cands[0])
        model_revision = cands[0].split("/snapshots/")[1].split("/")[0]
    elif os.path.exists(os.path.join(model_dir, args.file)):
        model_path, model_revision = os.path.realpath(os.path.join(model_dir, args.file)), "local"
    else:
        sys.exit(f"model file {args.file} not found in the HF cache or {model_dir} (hf download {args.model_id} {args.file})")

    tok_file = os.path.join(model_dir, f"{model_name}_tokenizer.json")
    tok_sha = sha256(tok_file) if os.path.exists(tok_file) else None
    if tok_sha is None and meta[model_name].get("tokenizerUrl"):
        print(f"WARNING: {tok_file} missing — the runner will curl {meta[model_name]['tokenizerUrl']}", file=sys.stderr)

    ver_file = os.path.join(runner_dir, "ENGINE_VERSION")
    engine_version = os.environ.get("ASR_ENGINE_VERSION") or (open(ver_file).read().strip() if os.path.exists(ver_file) else "unknown")
    artifact = f"asr_runner sha256:{sha256(runner)} (bazel build //omni/asr:asr_runner, LiteRT-LM {engine_version})"
    metal = os.path.join(runner_dir, "libLiteRtMetalAccelerator.dylib")
    if args.backend == "gpu":
        if not os.path.exists(metal):
            sys.exit(f"gpu backend needs {metal}")
        artifact += f"; libLiteRtMetalAccelerator.dylib sha256:{sha256(metal)}"

    set_name = TASK_SETS[args.task]
    stream_path, stream_sha, audio_s, reference, man = build_stream(set_name)
    ctx = {
        "runner_dir": runner_dir, "model_dir": model_dir, "model_name": model_name,
        "model_path": model_path, "model_revision": model_revision, "model_sha256": sha256(model_path),
        "tokenizer_file": os.path.relpath(tok_file, REPO) if tok_sha else None, "tokenizer_sha256": tok_sha,
        "metadata_sha256": sha256(meta_path), "engine_version": engine_version, "engine_artifact": artifact,
        "num_threads": int(os.environ.get("ASR_NUM_THREADS", "4")),
        "overlap_ratio": float(os.environ.get("ASR_OVERLAP_RATIO", "0.4")),
        "text_merger": os.environ.get("ASR_TEXT_MERGER", "timestamp"),
        "chunk_ms": meta[model_name].get("inputMilliseconds"),
        "stream_path": stream_path, "stream_sha256": stream_sha, "audio_s": audio_s,
        "ref_words": normalize(reference), "set_name": set_name, "device": device_info(),
    }
    args.slug = os.path.splitext(os.path.basename(args.output))[0]
    os.makedirs(args.campaign_dir, exist_ok=True)
    print(f"asr-rtf: {args.model_id} {args.file} backend={args.backend} runs={args.runs} "
          f"stream={os.path.basename(stream_path)} ({audio_s:.3f} s, sha256 {stream_sha[:12]}) "
          f"chunk={ctx['chunk_ms']}ms overlap={ctx['overlap_ratio']} threads={ctx['num_threads']} "
          f"engine={engine_version}", flush=True)
    ok_all = True
    for r in range(1, args.runs + 1):
        if r > 1 and args.pause > 0:
            time.sleep(args.pause)
        ok_all &= one_run(args, ctx, r)
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
