#!/usr/bin/env python3
"""TTS real-time-factor cells on an Android phone over adb (task family `tts-rtf-*`), v1.

The Android leg of docs/tts-rtf-v1.md: the same public reference pipeline as
the Mac leg — john-rocky/litert-samples `compiled_model_api/text_to_speech_lm`
at the commit in the sample checkout — through its own Android app
(`kotlin_cpu/android`, the Kotlin port of `python/qwen3_tts_pipeline.py` on the
LiteRT Kotlin `CompiledModel` API, CPU / XNNPACK), one fresh process per run.
The instrumentation harness (`app/src/androidTest/.../TtsRtfBench.kt`) does
what MainActivity's "Speak" does — `Qwen3TtsEngine(filesDir)` then
`synthesize(text, language, seed)` — and writes the 24 kHz WAV plus the
pipeline's own stage clocks; this script pulls them, runs the ASR round trip on
the Mac (the asr-rtf-v1 instrument, exactly as scripts/tts_rtf_mac.py does) and
writes the Mac leg's record shape into results/raw/<campaign>-android/.

What differs from the Mac leg is stated in every record: the runtime is the
LiteRT Android AAR (`engineArtifact` carries the AAR's sha256 and the app's),
the thread counts are the Android sample's own (talker 4 / MTP 2 / codec 4,
`Qwen3TtsEngine.load()`), the tokenizer is the sample's Kotlin BPE over
`vocab.json` + `merges.txt` (its startup self-test result rides along), and the
sampler's RNG is `java.util.Random(seed)`, so the sampled token sequence — and
the audio — is not byte-comparable with the Mac leg's NumPy draw at the same
seed. The model files are the same Hub files: every record carries their
sha256 as read on the phone (`run-as ... sha256sum`) against the Hub's LFS
sha256 (git blob sha1 for the two non-LFS tokenizer files).

Usage:
  scripts/tts_rtf_android.py matrices/tts-rtf-v1.cells --campaign 2026-09-27-tts-rtf-v1-s26 --serial RFGL80R6A6H
  (writes results/raw/<campaign>-android/; the session anchor is NOT run here —
   run the android rows of matrices/anchors.cells first, as the asr / vl legs do)

Environment:
  TTS_ANDROID_APP_DIR   the sample's kotlin_cpu/android checkout (built APKs under
                        app/build/outputs/apk; COMMIT = `git rev-parse HEAD` there)
  TTS_HUB_BLOBS_JSON    cached Hub API answer (?blobs=true) instead of a live fetch
  ASR_RUNNER_DIR / ASR_MODEL_DIR / TTS_ROUNDTRIP_ASR  the round-trip instrument (Mac), as tts_rtf_mac.py
"""
import argparse
import datetime as dt
import glob
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import threading
import time
import urllib.request
import uuid

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
sys.path.insert(0, os.path.join(REPO, "android", "bench"))
from asr_rtf_mac import normalize, wer_counts, sha256  # noqa: E402
from tts_rtf_mac import (DISPLAY, TASK_SETS, ROUND_TRIP_ASRS, quant_label,  # noqa: E402
                         find_asr_model, round_trip)
import tts_rtf_mac  # noqa: E402
from device_probe import adb, battery, device_info, thermal_status, screen_conditions  # noqa: E402
from validate_cells import parse_line  # noqa: E402

HARNESS_STAMP = "tts-rtf-v1-android-2026-09-27"
PKG = "com.google.ai.edge.examples.text_to_speech_lm"
RUNNER = f"{PKG}.test/androidx.test.runner.AndroidJUnitRunner"
DEV_OUT = f"/sdcard/Android/data/{PKG}/files/tts-rtf"
# Hub path -> file name in the app's filesDir (install_to_device.sh flattens tables/ and voices/)
DEVICE_FILES = {
    "talker_int4.tflite": "talker_int4.tflite", "mtp_fp32.tflite": "mtp_fp32.tflite",
    "codec_decoder_fp32.tflite": "codec_decoder_fp32.tflite",
    "tables/codec_embedding_fp32.npy": "codec_embedding_fp32.npy",
    "tables/mtp_embeddings_fp16.npy": "mtp_embeddings_fp16.npy",
    "tables/text_embedding_fp16.npy": "text_embedding_fp16.npy",
    "tables/text_projection_fp32.npz": "text_projection_fp32.npz",
    "voices/demo_speaker.npy": "demo_speaker.npy",
    "vocab.json": "vocab.json", "merges.txt": "merges.txt",
}
SOURCE_FILES = ["Qwen3TtsEngine.kt", "QwenBpeTokenizer.kt", "Npy.kt", "MainActivity.kt"]
SRC_REL = "app/src/main/java/com/google/ai/edge/examples/text_to_speech_lm"


def sh(serial, cmd, timeout=120):
    return adb(["shell", cmd], serial, timeout=timeout)


def run_as(serial, cmd, timeout=600):
    return sh(serial, f"run-as {PKG} sh -c {shlex.quote(cmd)}", timeout=timeout)


def phone_state(serial):
    raw, name = thermal_status(serial)
    bat = battery(serial)
    caps = sh(serial, "for c in /sys/devices/system/cpu/cpufreq/policy*; do echo $(cat $c/scaling_max_freq) $(cat $c/cpuinfo_max_freq); done").split()
    capped = any(caps[i] != caps[i + 1] for i in range(0, len(caps) - 1, 2))
    return {"thermalStatusRaw": raw, "thermal": name, "batteryTempC": bat.get("temperatureC"),
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


def hub_blobs(model_id, campaign_dir):
    """{hub path: {"sha256": lfs sha256 or None, "blobId": git blob sha1, "size": n}} + the raw answer stored."""
    cached = os.environ.get("TTS_HUB_BLOBS_JSON")
    if cached:
        raw = open(cached).read()
    else:
        raw = urllib.request.urlopen(f"https://huggingface.co/api/models/{model_id}?blobs=true", timeout=60).read().decode()
    d = json.loads(raw)
    with open(os.path.join(campaign_dir, "hub-api-blobs.json"), "w") as f:
        f.write(raw)
    out = {}
    for s in d["siblings"]:
        out[s["rfilename"]] = {"sha256": (s.get("lfs") or {}).get("sha256"), "blobId": s.get("blobId"), "size": s.get("size")}
    return out, d.get("sha")


def verify_device_files(serial, blobs, log):
    """sha256 (LFS files) / git blob sha1 (plain files) of the app's copies vs the Hub."""
    names = " ".join(DEVICE_FILES.values())
    out = run_as(serial, f"cd files && sha256sum {names} && for f in vocab.json merges.txt; do s=$(stat -c %s $f); (printf 'blob %d\\0' $s; cat $f) | sha1sum | sed \"s/-/$f blob/\"; done; ls -l {names}")
    sha, blob, size = {}, {}, {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) == 2 and len(parts[0]) == 64:
            sha[parts[1]] = parts[0]
        elif len(parts) == 3 and parts[2] == "blob":
            blob[parts[1]] = parts[0]
        elif len(parts) >= 8 and parts[-1] in DEVICE_FILES.values():
            size[parts[-1]] = int(parts[4])
    file_shas, verified = {}, {}
    for hub, dev in DEVICE_FILES.items():
        want = blobs.get(hub, {})
        file_shas[hub] = sha.get(dev)
        if want.get("sha256"):
            verified[hub] = sha.get(dev) == want["sha256"]
        else:
            verified[hub] = blob.get(dev) == want.get("blobId")
        log(f"  {hub}: sha256 {sha.get(dev, '?')[:16]}… {'OK' if verified[hub] else 'MISMATCH'}"
            + (f" (git blob {blob.get(dev, '?')[:12]}… vs Hub {want.get('blobId', '?')[:12]}…)" if not want.get("sha256") else ""))
    if not all(verified.values()):
        sys.exit(f"model files on the phone do not match the Hub: {[k for k, v in verified.items() if not v]}")
    return file_shas, verified, size, blob


def one_run(args, ctx, cell, run_idx, log):
    serial = args.serial
    slug = cell["slug"]
    name = f"{slug}_run{run_idx}"
    logs = os.path.join(args.out, "logs"); os.makedirs(logs, exist_ok=True)
    audio_dir = os.path.join(args.out, "audio"); os.makedirs(audio_dir, exist_ok=True)
    wav24 = os.path.join(audio_dir, f"{name}_24k.wav")
    wav16 = os.path.join(audio_dir, f"{name}_16k.wav")
    out_json = os.path.join(logs, f"{name}.worker.json")
    inst_log = os.path.join(logs, f"{name}.instrument.log")
    logcat_log = os.path.join(logs, f"{name}.logcat.txt")

    before = wait_nominal(serial, log)
    screen = screen_conditions(serial)
    sh(serial, f"am force-stop {PKG}; rm -f {DEV_OUT}/{name}.json {DEV_OUT}/{name}_24k.wav; logcat -c")
    cmd = (f"am instrument -w -r -e text {shlex.quote(ctx['text'])} -e language {ctx['language']} "
           f"-e seed {ctx['seed']} -e name {name} {RUNNER}")
    peak = {"kb": 0}
    stop = threading.Event()

    def mem_poll():
        while not stop.is_set():
            try:
                out = subprocess.check_output(
                    ["adb", "-s", serial, "shell", f"p=$(pidof {PKG}); [ -n \"$p\" ] && grep VmHWM /proc/$p/status"],
                    text=True, timeout=10, stderr=subprocess.DEVNULL)
                m = re.search(r"VmHWM:\s+(\d+)", out)
                if m:
                    peak["kb"] = max(peak["kb"], int(m.group(1)))
            except Exception:
                pass
            time.sleep(0.5)

    wall0 = dt.datetime.now(dt.timezone.utc)
    t0 = time.monotonic()
    mt = threading.Thread(target=mem_poll, daemon=True); mt.start()
    try:
        p = subprocess.run(["adb", "-s", serial, "shell", cmd], stdin=subprocess.DEVNULL,
                           capture_output=True, text=True, timeout=args.timeout)
        inst_out, timed_out = p.stdout + p.stderr, False
    except subprocess.TimeoutExpired as e:
        inst_out, timed_out = (e.stdout or b"").decode("utf-8", "replace") + "\n# TIMEOUT\n", True
        sh(serial, f"am force-stop {PKG}")
    t_exit = time.monotonic()
    stop.set(); mt.join(timeout=3)
    after = phone_state(serial)
    test_ok = ("INSTRUMENTATION_CODE: -1" in inst_out and "OK (1 test)" in inst_out and not timed_out)
    with open(inst_log, "w") as f:
        f.write(f"# adb -s {serial} shell {cmd}\n# testOk={test_ok}\n{inst_out}")
    with open(logcat_log, "w") as f:
        f.write(sh(serial, "logcat -d -v threadtime -s Qwen3Tts Qwen3TtsRtf AndroidRuntime TestRunner tflite XNNPACK", timeout=60))
    w = {}
    if test_ok:
        subprocess.run(["adb", "-s", serial, "pull", f"{DEV_OUT}/{name}.json", out_json], check=True, capture_output=True)
        subprocess.run(["adb", "-s", serial, "pull", f"{DEV_OUT}/{name}_24k.wav", wav24], check=True, capture_output=True)
        w = json.load(open(out_json))
    rc = 0 if test_ok else 1

    metrics = {"coldRun": True, "harnessStamp": HARNESS_STAMP, "exitCode": rc,
               "memoryPeakResidentMB": round(max(peak["kb"], int(w.get("vmHwmKbAfterSynthesis") or 0)) / 1024.0, 1),
               "initialThermalState": before["thermal"], "finalThermalState": after["thermal"],
               "batteryTempInitialC": before["batteryTempC"], "batteryTempFinalC": after["batteryTempC"],
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
            "ttsTokenizerSelfTest": w.get("tokenizerSelfTest"),
        })
        wav_sha = sha256(wav24)
        if ctx["asr_ready"]:
            transcript, asr_rc, asr_cmd = round_trip(wav24, wav16, ctx["asr_runner_dir"], ctx["asr_model_dir"],
                                                     ctx["asr_model_path"], os.path.join(logs, f"{name}.asr.stderr.log"))
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
        # Second opinion, provenance only (not the protocol's number): whisper-tiny
        # reads a ~10 s clip as ONE 30 s window, so it has no chunk-merge seam —
        # the parakeet 5 s instrument can double a word at an overlap boundary.
        if ctx.get("second_asr"):
            sa = ctx["second_asr"]
            tts_rtf_mac.ROUND_TRIP_ASR = sa["cand"]
            try:
                tr2, rc2, cmd2 = round_trip(wav24, wav16, ctx["asr_runner_dir"], ctx["asr_model_dir"], sa["path"],
                                            os.path.join(logs, f"{name}.asr-{sa['cand']['model_name']}.stderr.log"))
            finally:
                tts_rtf_mac.ROUND_TRIP_ASR = ctx["primary_asr"]
            hyp2 = normalize(tr2)
            s2, d2, i2, n2 = wer_counts(ctx["ref_words"], hyp2) if hyp2 else (0, len(ctx["ref_words"]), 0, len(ctx["ref_words"]))
            second = {"model": sa["cand"]["model_name"], "file": sa["cand"]["file"], "sha256": sa["sha256"],
                      "transcript": tr2, "wordErrorRate": round((s2 + d2 + i2) / n2, 4),
                      "substitutions": s2, "deletions": d2, "insertions": i2, "exit": rc2, "command": cmd2}
        else:
            second = None
    else:
        second = None
    ok = rc == 0 and "ttsRealTimeFactor" in metrics and metrics.get("ttsAudioCheck") == "pass"

    rec = {
        "schemaVersion": 1,
        "id": str(uuid.uuid4()).upper(),
        "timestamp": wall0.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "runtime": f"{cell['runtime']}-cpu",
        "engineVersion": ctx["engine_version"],
        "engineArtifact": ctx["engine_artifact"],
        "model": {
            "id": cell["model_id"], "hfRepoId": cell["model_id"], "displayName": DISPLAY.get(cell["model_id"], cell["model_id"]),
            "primaryFile": cell["file"], "file": cell["file"], "hfFilePatterns": list(DEVICE_FILES.keys()),
            "hfRevision": ctx["model_revision"], "quantization": quant_label(cell["file"]),
            "onDiskSizeMB": ctx["on_disk_mb"], "sha256": ctx["file_shas"][cell["file"]],
        },
        "modelRevision": ctx["model_revision"],
        "task": cell["task"],
        "device": dict(ctx["device"], batteryState=before["batteryState"], batteryLevel=before["batteryLevel"],
                       cpuMaxFreqKHz=before["cpuMaxFreqKHz"], cpuFreqCapped=before["cpuFreqCapped"]),
        "conditions": {
            "ttsText": ctx["text"], "ttsLanguage": ctx["language"], "ttsWords": len(ctx["text"].split()),
            "ttsVoice": "demo_speaker.npy (the repo's bundled x-vector, voices/demo_speaker.npy on the Hub)",
            "ttsSampler": f"sampling top-k 50, temperature 0.9, repetition penalty 1.05 (the Kotlin port's fixed values = the Python pipeline's defaults), seed {ctx['seed']} (java.util.Random)",
            "ttsMaxFrames": 512, "ttsThreads": 4, "ttsMtpThreads": 2,
            "ttsGraphs": f"{cell['file']} + mtp_fp32.tflite + codec_decoder_fp32.tflite (the sample's default set; the Android app hard-codes it)",
            "sampler": f"pipeline default, seed {ctx['seed']}",
            "warm": False, "unplugged": before["batteryState"] != "charging",
            "screen": screen.get("screen"), "screenSource": screen.get("screenSource"),
            "stayOnWhilePluggedIn": screen.get("stayOnWhilePluggedIn"),
            "thermalInitial": before["thermal"], "thermalFinal": after["thermal"],
        },
        "metrics": metrics,
        "outputSample": (transcript or "")[:200],
        "transcript": transcript,
        "provenance": {
            "textSet": ctx["set_name"], "manifestSha256": ctx["manifest_sha256"],
            "modelFiles": ctx["file_shas"], "hfLfsSha256Verified": ctx["hf_verified"],
            "modelFilesGitBlobSha1": ctx["blob_shas"], "modelFilesReadOn": f"the phone ({PKG} filesDir, run-as sha256sum)",
            "hubRevisionAtCheck": ctx["hub_sha"],
            "pipelineCommit": ctx["pipeline_commit"], "pipelineSha256": ctx["pipeline_shas"],
            "appApk": ctx["apk"], "testApk": ctx["test_apk"], "litertAar": ctx["aar"],
            "audio24k": os.path.relpath(wav24, REPO), "audio24kSha256": wav_sha,
            "audio16k": os.path.relpath(wav16, REPO) if transcript is not None else None,
            "roundTripAsr": ctx["asr_desc"], "roundTripCommand": asr_cmd, "roundTripExit": asr_rc,
            "roundTripSecondOpinion": second,
            "deviceBefore": dict(before, **screen), "deviceAfter": after,
            "command": f"adb -s {serial} shell {cmd}",
            "instrumentLog": os.path.relpath(inst_log, REPO), "logcat": os.path.relpath(logcat_log, REPO),
            "workerJson": os.path.relpath(out_json, REPO) if w else None,
        },
    }
    with open(os.path.join(args.out, f"{slug}.jsonl"), "a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    log(f"{'OK ' if ok else 'FAIL'} run {run_idx}: exit={rc} load={metrics.get('loadTimeSeconds')}s "
        f"synth={metrics.get('ttsSynthesisSeconds')}s audio={metrics.get('ttsAudioSeconds')}s "
        f"RTF={metrics.get('ttsRealTimeFactor')} frames={metrics.get('ttsFrames')} "
        f"WER={metrics.get('ttsRoundTripWordErrorRate')} check={metrics.get('ttsAudioCheck')} "
        f"hwm={metrics['memoryPeakResidentMB']}MB batt={before['batteryTempC']}->{after['batteryTempC']}C "
        f"thermal={before['thermal']}->{after['thermal']} screen={screen.get('screen')} | {(transcript or '')[:80]!r}")
    return ok


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cells")
    ap.add_argument("--campaign", required=True, help="results/raw/<campaign>-android/")
    ap.add_argument("--serial", default=os.environ.get("BENCH_ANDROID_SERIAL"))
    ap.add_argument("--runs", type=int, default=None, help="override runs= of every cell")
    ap.add_argument("--seed", type=int, default=1)
    # 45 s between launches, as the asr-rtf-v1 Android leg (S26 CPU cells drifted at 5 s pauses)
    ap.add_argument("--pause", type=float, default=45.0)
    ap.add_argument("--timeout", type=float, default=1800.0)
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

    # the sample checkout + its built APKs
    app_dir = os.path.abspath(os.environ.get("TTS_ANDROID_APP_DIR", os.path.expanduser(
        "~/code/litert-samples-qwen3tts-a1f5edf-wt/compiled_model_api/text_to_speech_lm/kotlin_cpu/android")))
    apk = os.path.join(app_dir, "app/build/outputs/apk/debug/app-debug.apk")
    test_apk = os.path.join(app_dir, "app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk")
    for p in (apk, test_apk):
        if not os.path.exists(p):
            sys.exit(f"no APK at {p} (build: ./gradlew :app:assembleDebug :app:assembleDebugAndroidTest)")
    commit = subprocess.run(["git", "-C", app_dir, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip() or "unknown"
    dirty = subprocess.run(["git", "-C", app_dir, "status", "--porcelain", "--", "."], capture_output=True, text=True).stdout.strip()
    pipeline_shas = {f: sha256(os.path.join(app_dir, SRC_REL, f)) for f in SOURCE_FILES if os.path.exists(os.path.join(app_dir, SRC_REL, f))}
    pipeline_shas["app/src/androidTest/.../TtsRtfBench.kt"] = sha256(os.path.join(app_dir, "app/src/androidTest/java/com/google/ai/edge/examples/text_to_speech_lm/TtsRtfBench.kt"))
    gradle = open(os.path.join(app_dir, "app", "build.gradle.kts")).read()
    m = re.search(r'com\.google\.ai\.edge\.litert:litert:([\d.]+)', gradle)
    aar_ver = m.group(1) if m else "unknown"
    aars = glob.glob(os.path.expanduser(f"~/.gradle/caches/modules-2/files-2.1/com.google.ai.edge.litert/litert/{aar_ver}/*/litert-{aar_ver}.aar"))
    aar = {"coordinate": f"com.google.ai.edge.litert:litert:{aar_ver}", "sha256": sha256(aars[0]) if aars else None, "path": aars[0] if aars else None}
    engine_version = f"ai-edge-litert (Android AAR) {aar_ver} + qwen3-tts-sample@{commit[:7]}"
    engine_artifact = (f"com.google.ai.edge.litert:litert:{aar_ver} (CompiledModel, CPU/XNNPACK) sha256:{aar['sha256']} via "
                       f"Qwen3TtsEngine.kt sha256:{pipeline_shas.get('Qwen3TtsEngine.kt')} (john-rocky/litert-samples "
                       f"compiled_model_api/text_to_speech_lm/kotlin_cpu/android @ {commit}); app-debug.apk sha256:{sha256(apk)}")

    # cells
    cells = []
    for raw in open(args.cells):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        plat, rt, mid, task, opts = parse_line(line)
        if plat != "android" or not task.startswith("tts-rtf-"):
            continue
        if opts.get("exclude"):
            log(f"SKIPPED {rt} {mid} {task} reason={opts['exclude']}"); continue
        if task not in TASK_SETS or mid not in DISPLAY:
            sys.exit(f"{mid} {task}: v1 knows only {sorted(DISPLAY)} x {sorted(TASK_SETS)}")
        if opts.get("file") != "talker_int4.tflite":
            sys.exit(f"{opts.get('file')}: the Android app hard-codes talker_int4.tflite (Qwen3TtsEngine.load)")
        cells.append({"runtime": rt, "model_id": mid, "task": task, "file": opts["file"],
                      "runs": int(opts.get("runs", 3)), "cooldown": float(opts.get("cooldown", args.base_cooldown)),
                      "slug": f"{rt}_{mid}_{task}".replace("/", "_").replace(".", "_")})
    if not cells:
        sys.exit("no android tts-rtf-* cells matched")
    if args.runs:
        for c in cells:
            c["runs"] = args.runs
    model_id = cells[0]["model_id"]

    # text + round-trip instrument (the Mac's, exactly as tts_rtf_mac.py)
    set_name = TASK_SETS[cells[0]["task"]]
    man_path = os.path.join(REPO, "evaldata", "tts", set_name, "manifest.json")
    man = json.load(open(man_path))
    asr_runner_dir = os.path.abspath(os.environ.get("ASR_RUNNER_DIR", os.path.join(REPO, ".build", "asr-runner-1dadd00c")))
    asr_model_dir = os.path.abspath(os.environ.get("ASR_MODEL_DIR", os.path.join(REPO, ".build", "asr-models")))
    asr_model_path = find_asr_model(asr_model_dir)
    asr_ready = os.access(os.path.join(asr_runner_dir, "asr_runner"), os.X_OK) and asr_model_path is not None
    if not asr_ready:
        sys.exit(f"round-trip ASR instrument not found ({asr_runner_dir}, {ROUND_TRIP_ASRS[0]['file']}) — a rate without the audio check is not a measurement here")
    primary_asr = tts_rtf_mac.ROUND_TRIP_ASR
    second_asr = None
    want2 = os.environ.get("TTS_SECOND_ASR", "whisper-tiny")
    if want2 and want2 != primary_asr["model_name"]:
        cand = next((c for c in ROUND_TRIP_ASRS if c["model_name"] == want2), None)
        if cand:
            org, nm = cand["model_id"].split("/", 1)
            paths = glob.glob(os.path.expanduser(f"~/.cache/huggingface/hub/models--{org}--{nm}/snapshots/*/{cand['file']}"))
            if paths:
                second_asr = {"cand": cand, "path": os.path.realpath(paths[0]), "sha256": sha256(os.path.realpath(paths[0]))}
    asr_ver = (open(os.path.join(asr_runner_dir, "ENGINE_VERSION")).read().strip().splitlines() or ["unknown"])[0] if os.path.exists(os.path.join(asr_runner_dir, "ENGINE_VERSION")) else "unknown"

    # phone + model files
    dev = device_info(args.serial)
    log(f"device {dev} — {phone_state(args.serial)}")
    installed = sh(args.serial, f"dumpsys package {PKG} | grep -E 'versionName|lastUpdateTime'").strip().replace("\n", " ")
    log(f"app: {installed}")
    log("verifying the app's model files against the Hub")
    blobs, hub_sha = hub_blobs(model_id, args.out)
    file_shas, verified, sizes, blob_shas = verify_device_files(args.serial, blobs, log)
    ctx = {
        "text": man["text"], "language": man.get("language", "english"), "seed": args.seed,
        "ref_words": normalize(man["text"]), "wer_bar": float(man["text_check"]["max_word_error_rate"]),
        "set_name": set_name, "manifest_sha256": sha256(man_path),
        "file_shas": file_shas, "hf_verified": verified, "blob_shas": blob_shas, "hub_sha": hub_sha,
        "model_revision": f"local (the app's copies verified against the Hub's LFS sha256 / git blob sha1 at revision {hub_sha}; see provenance.hfLfsSha256Verified)",
        "on_disk_mb": round(sum(sizes.values()) / 1e6, 1),
        "pipeline_commit": commit + (" (working tree: androidTest harness + gradle test deps + AAR pin added; src/main untouched)" if dirty else ""),
        "pipeline_shas": pipeline_shas, "apk": {"path": apk, "sha256": sha256(apk)},
        "test_apk": {"path": test_apk, "sha256": sha256(test_apk)}, "aar": aar,
        "engine_version": engine_version, "engine_artifact": engine_artifact,
        "primary_asr": primary_asr, "second_asr": second_asr,
        "asr_ready": asr_ready, "asr_runner_dir": asr_runner_dir, "asr_model_dir": asr_model_dir, "asr_model_path": asr_model_path,
        "asr_desc": (f"LiteRT-LM omni/asr asr_runner {asr_ver}, {tts_rtf_mac.ROUND_TRIP_ASR['file']} "
                     f"(sha256 {sha256(asr_model_path)}), --backend cpu, num_threads 4, overlap 0.4, timestamp merger, on the Mac; "
                     f"24 kHz PCM16 (the app's WAV) -> 16 kHz PCM16 mono via afconvert"),
        "device": dev,
    }
    with open(os.path.join(args.out, "session_provenance.txt"), "a") as f:
        f.write(f"session start {dt.datetime.now().strftime('%F %T')}\ncells: {args.cells}\nserial: {args.serial}\n"
                f"device: {json.dumps(dev)}\nengine: {engine_version}\nartifact: {engine_artifact}\n"
                f"app: {installed}\npipeline commit: {ctx['pipeline_commit']}\n"
                f"text: {set_name} ({len(man['text'].split())} words) seed={args.seed}\n"
                f"round-trip asr: {ctx['asr_desc']}\n"
                f"second-opinion asr (provenance only): {json.dumps({k: v for k, v in (second_asr or {}).items() if k != 'cand'} | ({'model': second_asr['cand']['model_name']} if second_asr else {}))}\n")
    sh(args.serial, f"mkdir -p {DEV_OUT}")
    log(f"tts-rtf android: {model_id} runs={[c['runs'] for c in cells]} engine={engine_version} round-trip-asr=ready")
    ok_all = True
    first = True
    for c in cells:
        if not first:
            log(f"cooldown {c['cooldown']:.0f}s"); time.sleep(c["cooldown"])
        first = False
        log(f"CELL {c['runtime']} / {c['model_id']} / {c['task']} file={c['file']} runs={c['runs']}")
        for r in range(1, c["runs"] + 1):
            if r > 1:
                time.sleep(args.pause)
            ok_all &= one_run(args, ctx, c, r, log)
    log(f"done: {args.out}")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
