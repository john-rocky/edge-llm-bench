#!/usr/bin/env python3
"""TTS real-time-factor cells on the Mac (task family `tts-rtf-*`), v1.

One fresh process per run (scripts/tts_rtf_worker.py inside the pinned venv)
of the model's PUBLIC reference pipeline over ONE fixed text
(evaldata/tts/<set>/manifest.json). v1 instrument: the Qwen3-TTS LiteRT
sample — `qwen3_tts_pipeline.py` from john-rocky/litert-samples
`compiled_model_api/text_to_speech_lm/python` at the commit in
TTS_PIPELINE_DIR/COMMIT, on `ai-edge-litert` CompiledModel, CPU — at the
sample's own defaults (talker_int4 + mtp_fp32 + codec_decoder_fp32, 8 XNNPACK
threads for talker / codec and 1 for the MTP, sampling top-k 50 / temperature
0.9 / repetition penalty 1.05, 512-frame cap). Only the sampling seed is fixed
(1) so launches are comparable; every condition is stamped in the record.

Per run the record carries (metrics):
  ttsRealTimeFactor    = ttsSynthesisSeconds / ttsAudioSeconds  (< 1 = faster than real time)
  ttsSynthesisSeconds  = wall clock of the pipeline's synthesize() call (prompt
                         prefill + talker decode + MTP + codec + host glue),
                         model load excluded and reported as loadTimeSeconds
  ttsAudioSeconds, ttsFrames (12.5 Hz codec frames)
  ttsPrefillSeconds / ttsTalkerSeconds / ttsMtpSeconds / ttsCodecSeconds
                         the pipeline's own stage clocks
  ttsRoundTripWordErrorRate (+ S/D/I) — the audio check: the WAV, resampled to
                         16 kHz, transcribed by the asr-rtf-v1 instrument
                         (LiteRT-LM omni/asr asr_runner, parakeet-tdt-0.6b-v3
                         i8, CPU, defaults) and scored against the input text
                         with the ASR set's normalization; above the manifest's
                         bar the rate is "throughput only"
  memoryPeakResidentMB (ps sampling), coldRun = true

Usage (normally via scripts/bench_matrix_mac.sh, which dispatches tts-rtf-* cells here):
  scripts/tts_rtf_mac.py --model-id litert-community/Qwen3-TTS-12Hz-0.6B-Base \
      --file talker_int4.tflite --runs 3 --task tts-rtf-libri1272-2sent \
      --output OUT/<slug>.jsonl --campaign-dir OUT

Environment:
  TTS_PIPELINE_DIR  the pinned sample dir (qwen3_tts_pipeline.py + COMMIT);
                    default .build/qwen3-tts-sample-a1f5edf (docs/tts-rtf-v1.md)
  TTS_VENV_PYTHON   the pinned interpreter (default .build/tts-venv/bin/python)
  TTS_MODEL_DIR     folder with the repo's files (talker/mtp/codec .tflite,
                    tokenizer.json, tables/, voices/); default
                    .build/tts-models/<repo name>; HF_SHA256SUMS there (repo-
                    relative "sha256  path" lines from the HF API) marks each
                    file verified against the Hub
  ASR_RUNNER_DIR / ASR_MODEL_DIR  the asr-rtf-v1 instrument for the round trip
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
import time
import uuid

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
from asr_rtf_mac import normalize, wer_counts, host_snapshot, device_info, sh, sha256  # noqa: E402

HARNESS_STAMP = "tts-rtf-v1-2026-09-24"
TASK_SETS = {
    "tts-rtf-libri1272-2sent": "libri1272-2sent",
}
DISPLAY = {"litert-community/Qwen3-TTS-12Hz-0.6B-Base": "Qwen3-TTS-12Hz-0.6B-Base"}
PIPELINE_FILES = ["mtp_fp32.tflite", "codec_decoder_fp32.tflite", "tokenizer.json",
                  "tables/codec_embedding_fp32.npy", "tables/mtp_embeddings_fp16.npy",
                  "tables/text_embedding_fp16.npy", "tables/text_projection_fp32.npz",
                  "voices/demo_speaker.npy"]
# Round-trip ASR: the asr-rtf-v1 CPU cells that passed their own text check on
# this speaker's real audio, in order of preference (parakeet WER 0.197; whisper
# 0.372 with a 30 s window — one window for a ~10 s clip). The first one staged
# is used and the record names it (provenance.roundTripAsr); TTS_ROUNDTRIP_ASR
# forces one by model_name.
ROUND_TRIP_ASRS = [
    {"model_name": "parakeet-tdt-0.6b-v3", "model_id": "litert-community/parakeet-tdt-0.6b-v3",
     "file": "parakeet_tdt_0.6b_v3_5s_i8_stateful.tflite"},
    {"model_name": "whisper-tiny", "model_id": "litert-community/whisper-tiny",
     "file": "whisper_tiny_30s_i8.tflite"},
]
ROUND_TRIP_ASR = ROUND_TRIP_ASRS[0]


def quant_label(talker_file):
    if "int4" in talker_file:
        return ("talker blockwise-32 int4 (card: data-free OCTAV); mtp fp32; codec decoder fp32; "
                "host tables fp16/fp32 (the repo's default configuration)")
    if "fp32" in talker_file:
        return "talker fp32; mtp fp32; codec decoder fp32 (the repo's reference configuration)"
    return f"unstated ({talker_file})"


def load_hf_shas(model_dir):
    p = os.path.join(model_dir, "HF_SHA256SUMS")
    out = {}
    if os.path.exists(p):
        for line in open(p):
            parts = line.split()
            if len(parts) >= 2:
                out[parts[-1]] = parts[0]
    return out


def find_asr_model(model_dir):
    """-> path of the first staged round-trip ASR model (sets ROUND_TRIP_ASR), or None."""
    global ROUND_TRIP_ASR
    want = os.environ.get("TTS_ROUNDTRIP_ASR")
    for cand in ROUND_TRIP_ASRS:
        if want and cand["model_name"] != want:
            continue
        org, name = cand["model_id"].split("/", 1)
        paths = glob.glob(os.path.expanduser(f"~/.cache/huggingface/hub/models--{org}--{name}/snapshots/*/{cand['file']}"))
        # the runner's own cache layout names the file <model_name>.tflite; the
        # record stamps its sha256 so it can be matched against the asr-rtf-v1 row
        paths += [os.path.join(model_dir, f) for f in (cand["file"], f"{cand['model_name']}.tflite")]
        for p in paths:
            if os.path.exists(p) and os.path.exists(os.path.realpath(p)):
                ROUND_TRIP_ASR = cand
                return os.path.realpath(p)
    return None


def round_trip(wav24, out16, asr_runner_dir, asr_model_dir, asr_model_path, log_path):
    """24 kHz float WAV -> 16 kHz PCM16 (afconvert) -> asr_runner transcript."""
    subprocess.run(["afconvert", "-f", "WAVE", "-d", "LEI16@16000", "-c", "1", wav24, out16],
                   check=True, capture_output=True)
    cmd = [os.path.join(asr_runner_dir, "asr_runner"),
           "--model_name", ROUND_TRIP_ASR["model_name"],
           "--metadata_path", os.path.join(asr_runner_dir, "model_metadata.json"),
           "--model_path", asr_model_path, "--cache_dir", asr_model_dir,
           "--backend", "cpu", "--num_threads", "4", "--overlap_ratio", "0.4",
           "--text_merger_type", "timestamp", "--audio_path", out16]
    env = dict(os.environ, DYLD_LIBRARY_PATH=asr_runner_dir)
    p = subprocess.run(cmd, cwd=asr_runner_dir, env=env, capture_output=True, text=True, timeout=600)
    with open(log_path, "w") as f:
        f.write(f"# cmd: {' '.join(cmd)}\n# exit={p.returncode}\n{p.stderr}")
    return re.sub(r"\s+", " ", p.stdout).strip(), p.returncode, " ".join(cmd)


def one_run(args, ctx, run_idx):
    slug = args.slug
    logs = os.path.join(args.campaign_dir, "logs")
    audio_dir = os.path.join(args.campaign_dir, "audio")
    os.makedirs(logs, exist_ok=True)
    os.makedirs(audio_dir, exist_ok=True)
    wav24 = os.path.join(audio_dir, f"{slug}_run{run_idx}_24k.wav")
    wav16 = os.path.join(audio_dir, f"{slug}_run{run_idx}_16k.wav")
    out_json = os.path.join(logs, f"{slug}_run{run_idx}.worker.json")
    cmd = [ctx["python"], os.path.join(REPO, "scripts", "tts_rtf_worker.py"),
           "--pipeline-dir", ctx["pipeline_dir"], "--model-dir", ctx["model_dir"],
           "--text", ctx["text"], "--language", ctx["language"], "--talker-file", args.file,
           "--seed", str(ctx["seed"]), "--threads", str(ctx["threads"]),
           "--out-wav", wav24, "--out-json", out_json]
    host = host_snapshot()
    t0 = time.monotonic()
    wall0 = dt.datetime.now(dt.timezone.utc)
    p = subprocess.Popen(cmd, cwd=ctx["pipeline_dir"], stdin=subprocess.DEVNULL,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
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
    stdout, stderr = p.communicate()
    t_exit = time.monotonic()
    rc = p.returncode
    host_after = host_snapshot()
    err_log = os.path.join(logs, f"{slug}_run{run_idx}.stderr.log")
    with open(err_log, "w") as f:
        f.write(f"# cmd: {' '.join(cmd)}\n# exit={rc}\n{stderr}")
    w = json.load(open(out_json)) if os.path.exists(out_json) and rc == 0 else {}

    metrics = {"coldRun": True, "harnessStamp": HARNESS_STAMP, "exitCode": rc,
               "memoryPeakResidentMB": round(peak_rss_kb / 1024.0, 1),
               "initialThermalState": host["thermal"], "finalThermalState": host_after["thermal"],
               "totalWallSeconds": round(t_exit - t0, 3)}
    transcript, asr_rc, asr_cmd, wav_sha = None, None, None, None
    if w:
        metrics.update({
            "loadTimeSeconds": w["loadSeconds"], "ttsSynthesisSeconds": w["synthesisSeconds"],
            "ttsAudioSeconds": w["audioSeconds"], "ttsFrames": w["numFrames"],
            "ttsRealTimeFactor": round(w["synthesisSeconds"] / w["audioSeconds"], 4) if w["audioSeconds"] else None,
            "ttsPipelineRealTimeFactor": w["pipelineRTF"],
            "ttsPrefillSeconds": w["prefillSeconds"], "ttsTalkerSeconds": w["talkerSeconds"],
            "ttsMtpSeconds": w["mtpSeconds"], "ttsCodecSeconds": w["codecSeconds"],
            "ttsPeakAbs": round(w["peakAbs"], 4), "ttsRmsDbfs": round(w["rmsDbfs"], 1) if w.get("rmsDbfs") is not None else None,
        })
        wav_sha = sha256(wav24)
        if ctx["asr_ready"]:
            transcript, asr_rc, asr_cmd = round_trip(wav24, wav16, ctx["asr_runner_dir"], ctx["asr_model_dir"],
                                                     ctx["asr_model_path"], os.path.join(logs, f"{slug}_run{run_idx}.asr.stderr.log"))
            hyp = normalize(transcript)
            if hyp:
                s, d, i, n = wer_counts(ctx["ref_words"], hyp)
                metrics.update({"ttsRoundTripWordErrorRate": round((s + d + i) / n, 4),
                                "ttsRoundTripSubstitutions": s, "ttsRoundTripDeletions": d,
                                "ttsRoundTripInsertions": i, "ttsReferenceWordCount": n,
                                "ttsHypothesisWordCount": len(hyp)})
            else:
                metrics["ttsRoundTripWordErrorRate"] = 1.0
                metrics["ttsRoundTripNote"] = "empty transcript"
            metrics["ttsAudioCheck"] = ("pass" if metrics["ttsRoundTripWordErrorRate"] <= ctx["wer_bar"] else "fail")
        else:
            metrics["ttsAudioCheck"] = "not-run (asr instrument missing)"
    ok = rc == 0 and "ttsRealTimeFactor" in metrics and metrics.get("ttsAudioCheck") == "pass"

    rec = {
        "schemaVersion": 1,
        "id": str(uuid.uuid4()).upper(),
        "timestamp": wall0.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "runtime": f"{args.runtime}-cpu",
        "engineVersion": ctx["engine_version"],
        "engineArtifact": ctx["engine_artifact"],
        "model": {
            "id": args.model_id, "hfRepoId": args.model_id, "displayName": DISPLAY.get(args.model_id, args.model_id),
            "primaryFile": args.file, "file": args.file, "hfFilePatterns": [args.file] + PIPELINE_FILES,
            "hfRevision": ctx["model_revision"], "quantization": quant_label(args.file),
            "onDiskSizeMB": ctx["on_disk_mb"], "sha256": ctx["file_shas"][args.file],
        },
        "modelRevision": ctx["model_revision"],
        "task": args.task,
        "device": ctx["device"],
        "conditions": {
            "ttsText": ctx["text"], "ttsLanguage": ctx["language"], "ttsWords": len(ctx["text"].split()),
            "ttsVoice": "voices/demo_speaker.npy (the repo's bundled x-vector)",
            "ttsSampler": f"sampling top-k 50, temperature 0.9, repetition penalty 1.05 (pipeline defaults), seed {ctx['seed']}",
            "ttsMaxFrames": 512, "ttsThreads": ctx["threads"], "ttsMtpThreads": 1,
            "ttsGraphs": f"{args.file} + mtp_fp32.tflite + codec_decoder_fp32.tflite (the sample's default set)",
            "sampler": f"pipeline default, seed {ctx['seed']}",
            "warm": False, "unplugged": False,
            "thermalInitial": host["thermal"], "thermalFinal": host_after["thermal"],
        },
        "metrics": metrics,
        "outputSample": (transcript or "")[:200],
        "transcript": transcript,
        "provenance": {
            "textSet": ctx["set_name"], "manifestSha256": ctx["manifest_sha256"],
            "modelFiles": ctx["file_shas"], "hfLfsSha256Verified": ctx["hf_verified"],
            "pipelineCommit": ctx["pipeline_commit"], "pipelineSha256": ctx["pipeline_shas"],
            "venvFreeze": ctx["venv_freeze"],
            "audio24k": os.path.relpath(wav24, REPO), "audio24kSha256": wav_sha,
            "audio16k": os.path.relpath(wav16, REPO) if transcript is not None else None,
            "roundTripAsr": ctx["asr_desc"], "roundTripCommand": asr_cmd, "roundTripExit": asr_rc,
            "hostBefore": host, "hostAfter": host_after,
            "command": " ".join(cmd), "stderrLog": os.path.relpath(err_log, REPO),
        },
    }
    with open(args.output, "a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    tag = "OK " if ok else "FAIL"
    print(f"{tag} run {run_idx}: exit={rc} load={metrics.get('loadTimeSeconds')}s "
          f"synth={metrics.get('ttsSynthesisSeconds')}s audio={metrics.get('ttsAudioSeconds')}s "
          f"RTF={metrics.get('ttsRealTimeFactor')} frames={metrics.get('ttsFrames')} "
          f"WER={metrics.get('ttsRoundTripWordErrorRate')} check={metrics.get('ttsAudioCheck')} "
          f"rss={metrics['memoryPeakResidentMB']}MB others={host['others'] or 'none'} | {(transcript or '')[:80]!r}", flush=True)
    return ok


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model-id", required=True)
    ap.add_argument("--file", required=True, help="talker file (cells file=): talker_int4.tflite | talker_fp32.tflite")
    ap.add_argument("--task", required=True)
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--runtime", default="litert")
    ap.add_argument("--output", required=True)
    ap.add_argument("--campaign-dir", required=True)
    ap.add_argument("--pause", type=float, default=5.0)
    ap.add_argument("--timeout", type=float, default=1800.0)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--threads", type=int, default=8, help="the sample's --threads default")
    args = ap.parse_args()

    if args.task not in TASK_SETS:
        sys.exit(f"unknown tts task {args.task!r}; known: {sorted(TASK_SETS)}")
    if args.model_id not in DISPLAY:
        sys.exit(f"{args.model_id}: v1 knows only {sorted(DISPLAY)} (docs/tts-rtf-v1.md)")
    pipeline_dir = os.path.abspath(os.environ.get("TTS_PIPELINE_DIR", os.path.join(REPO, ".build", "qwen3-tts-sample-a1f5edf")))
    python = os.path.abspath(os.environ.get("TTS_VENV_PYTHON", os.path.join(REPO, ".build", "tts-venv", "bin", "python")))
    name = args.model_id.split("/", 1)[1]
    model_dir = os.path.abspath(os.environ.get("TTS_MODEL_DIR", os.path.join(REPO, ".build", "tts-models", name)))
    for p, what in ((os.path.join(pipeline_dir, "qwen3_tts_pipeline.py"), "pipeline"), (python, "venv python")):
        if not os.path.exists(p):
            sys.exit(f"no {what} at {p} (docs/tts-rtf-v1.md: stage)")
    files = [args.file] + PIPELINE_FILES
    missing = [f for f in files if not os.path.exists(os.path.join(model_dir, f))]
    if missing:
        sys.exit(f"model files missing under {model_dir}: {missing}")
    file_shas = {f: sha256(os.path.join(model_dir, f)) for f in files}
    hf = load_hf_shas(model_dir)
    hf_verified = {f: (hf.get(f) == file_shas[f]) if f in hf else None for f in files}
    commit = open(os.path.join(pipeline_dir, "COMMIT")).read().strip() if os.path.exists(os.path.join(pipeline_dir, "COMMIT")) else "unknown"
    pipeline_shas = {f: sha256(os.path.join(pipeline_dir, f)) for f in ("qwen3_tts_pipeline.py",) if os.path.exists(os.path.join(pipeline_dir, f))}
    freeze = sh([python, "-m", "pip", "freeze"]).splitlines()
    litert_ver = next((l.split("==")[1] for l in freeze if l.lower().startswith("ai-edge-litert==")), "unknown")
    engine_version = f"ai-edge-litert {litert_ver} + qwen3-tts-sample@{commit[:7]}"
    artifact = (f"ai-edge-litert=={litert_ver} (CompiledModel, CPU/XNNPACK) via qwen3_tts_pipeline.py "
                f"sha256:{pipeline_shas.get('qwen3_tts_pipeline.py', '?')} (john-rocky/litert-samples "
                f"compiled_model_api/text_to_speech_lm/python @ {commit})")

    set_name = TASK_SETS[args.task]
    man_path = os.path.join(REPO, "evaldata", "tts", set_name, "manifest.json")
    man = json.load(open(man_path))

    asr_runner_dir = os.path.abspath(os.environ.get("ASR_RUNNER_DIR", os.path.join(REPO, ".build", "asr-runner-1dadd00c")))
    asr_model_dir = os.path.abspath(os.environ.get("ASR_MODEL_DIR", os.path.join(REPO, ".build", "asr-models")))
    asr_model_path = find_asr_model(asr_model_dir)
    asr_ready = os.access(os.path.join(asr_runner_dir, "asr_runner"), os.X_OK) and asr_model_path is not None
    if not asr_ready:
        print(f"WARNING: round-trip ASR instrument not found ({asr_runner_dir}, {ROUND_TRIP_ASR['file']}) — audio check will not run", file=sys.stderr)
    asr_ver = (open(os.path.join(asr_runner_dir, "ENGINE_VERSION")).read().strip().splitlines() or ["unknown"])[0] if os.path.exists(os.path.join(asr_runner_dir, "ENGINE_VERSION")) else "unknown"
    ctx = {
        "pipeline_dir": pipeline_dir, "python": python, "model_dir": model_dir,
        "model_revision": "local (files verified against the Hub's LFS sha256; see provenance.hfLfsSha256Verified)",
        "file_shas": file_shas, "hf_verified": hf_verified,
        "on_disk_mb": round(sum(os.path.getsize(os.path.join(model_dir, f)) for f in files) / 1e6, 1),
        "pipeline_commit": commit, "pipeline_shas": pipeline_shas, "venv_freeze": freeze,
        "engine_version": engine_version, "engine_artifact": artifact,
        "set_name": set_name, "manifest_sha256": sha256(man_path),
        "text": man["text"], "language": man.get("language", "english"),
        "ref_words": normalize(man["text"]), "wer_bar": float(man["text_check"]["max_word_error_rate"]),
        "seed": args.seed, "threads": args.threads,
        "asr_ready": asr_ready, "asr_runner_dir": asr_runner_dir, "asr_model_dir": asr_model_dir,
        "asr_model_path": asr_model_path,
        "asr_desc": (f"LiteRT-LM omni/asr asr_runner {asr_ver}, {ROUND_TRIP_ASR['file']} "
                     f"(sha256 {sha256(asr_model_path) if asr_model_path else '?'}), --backend cpu, num_threads 4, overlap 0.4, timestamp merger; "
                     f"24 kHz float -> 16 kHz PCM16 mono via afconvert"),
        "device": device_info(),
    }
    args.slug = os.path.splitext(os.path.basename(args.output))[0]
    os.makedirs(args.campaign_dir, exist_ok=True)
    print(f"tts-rtf: {args.model_id} {args.file} runs={args.runs} text={man['text'][:60]!r}... "
          f"({len(man['text'].split())} words) seed={args.seed} threads={args.threads} engine={engine_version} "
          f"round-trip-asr={'ready' if asr_ready else 'MISSING'}", flush=True)
    ok_all = True
    for r in range(1, args.runs + 1):
        if r > 1 and args.pause > 0:
            time.sleep(args.pause)
        ok_all &= one_run(args, ctx, r)
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
