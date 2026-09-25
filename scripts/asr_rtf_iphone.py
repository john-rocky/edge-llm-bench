#!/usr/bin/env python3
"""ASR real-time-factor cells on an iPhone over devicectl (task family `asr-rtf-*`), v1.

The iPhone leg of docs/asr-rtf-v1.md: LiteRT-LM's `omni/asr` engine through the
`asr_runner` path (AsrEngine + FileAudioSource, the engine's default streaming
protocol) compiled as a static library (`bench_ios/` in a LiteRT-LM worktree,
`bazel --config=ios_arm64`) inside the smallest iOS shell, ios/AsrBench. One
`devicectl device process launch --console` per run; the app writes
Documents/asr/results/<run-id>.json with device-clock timings and prints the
same JSON on the console. This script is its own mini-runner: it reads the `ios`
`asr-rtf-*` rows of a cells file, stages models + tokenizers + model_metadata.json
+ the stream WAV into the app's data container, gates every launch on the phone's
thermal state as the app reports it (nominal; the previous launch's final state),
and writes the same record shape as the Mac and Android drivers into
results/raw/<campaign>-ios/.

Timing is on the phone clock (std::chrono::steady_clock inside the app):
loadTimeSeconds = launch -> "Starting speech recognition" (engine + session
creation), asrProcessingSeconds = "Starting" -> "Finished" (the chunk loop incl.
flush), asrFirstTextLatencyMS = "Starting" -> the first confirmed text.

Usage:
  scripts/asr_rtf_iphone.py matrices/asr-rtf-v1.cells --campaign 2026-09-25-asr-rtf-v1-iphone18pro
  (writes results/raw/<campaign>-ios/; BENCH_UDID or --device picks the phone)

Environment:
  ASR_IOS_APP_DIR      ios/AsrBench (Frameworks/BUILD_INFO stamps the engine)
  ASR_IOS_BUNDLE_ID    the installed app's bundle id (default com.daisukemajima.asrbench)
  ASR_IOS_METADATA     model_metadata.json to stage (default .build/asr-runner-66058c82-ios/model_metadata.json)
  ASR_MODEL_DIR        tokenizers as <model_name>_tokenizer.json (default .build/asr-models)
  ASR_NUM_THREADS / ASR_OVERLAP_RATIO / ASR_TEXT_MERGER  protocol overrides (4 / 0.4 / timestamp)
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
import tempfile
import time
import uuid

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
from asr_rtf_mac import (DISPLAY, HARNESS_STAMP, MODEL_NAMES, TASK_SETS,  # noqa: E402
                         build_stream, normalize, quant_label, sha256, wer_counts)
from validate_cells import parse_line  # noqa: E402

DEFAULT_BUNDLE = "com.daisukemajima.asrbench"


def devicectl(args, timeout=600, check=True):
    cmd = ["xcrun", "devicectl"] + args
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if check and p.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)}\n{p.stdout}\n{p.stderr}")
    return p


def container_copy_to(dev, bundle, local, remote, timeout=1800):
    devicectl(["device", "copy", "to", "--device", dev, "--domain-type", "appDataContainer",
               "--domain-identifier", bundle, "--source", local, "--destination", remote], timeout=timeout)


def container_copy_from(dev, bundle, remote, local, timeout=300):
    p = devicectl(["device", "copy", "from", "--device", dev, "--domain-type", "appDataContainer",
                   "--domain-identifier", bundle, "--source", remote, "--destination", local],
                  timeout=timeout, check=False)
    return p.returncode == 0


def device_details(dev):
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    devicectl(["device", "info", "details", "--device", dev, "--json-output", path])
    d = json.load(open(path))["result"]
    os.unlink(path)
    hw, dp = d["hardwareProperties"], d["deviceProperties"]
    return {"modelIdentifier": hw.get("productType"), "marketingName": hw.get("marketingName"),
            "chip": hw.get("cpuType", {}).get("name") if isinstance(hw.get("cpuType"), dict) else hw.get("cpuType"),
            "systemName": "iOS", "systemVersion": f"{dp.get('osVersionNumber')} ({dp.get('osBuildUpdate')})",
            "deviceName": dp.get("name"), "udid": hw.get("udid"), "buildConfiguration": "Release"}


def stage_file(dev, bundle, local, remote, staged, log):
    """Copy unless the same size+sha was staged this session (devicectl has no stat; we keep a manifest)."""
    key = remote
    sig = f"{os.path.getsize(local)}:{sha256(local)}"
    if staged.get(key) == sig:
        log(f"  keep {remote} (staged this session)")
        return False
    t0 = time.monotonic()
    container_copy_to(dev, bundle, local, remote)
    staged[key] = sig
    log(f"  copied {remote} {os.path.getsize(local)} B in {time.monotonic() - t0:.1f} s")
    return True


def one_run(args, ctx, cell, run_idx, log):
    dev, bundle = args.device, args.bundle
    slug = cell["slug"]
    run_id = f"{slug}_run{run_idx}"
    launch = ["device", "process", "launch", "--console", "--terminate-existing", "--device", dev, bundle,
              "--", "--asr-autorun", "--run-id", run_id, "--model-name", cell["model_name"],
              "--model-file", cell["file"], "--metadata", "model_metadata.json",
              "--backend", cell["backend"], "--threads", str(ctx["num_threads"]),
              "--overlap", str(ctx["overlap_ratio"]), "--merger", ctx["text_merger"],
              "--audio", ctx["stream_name"]]
    wall0 = dt.datetime.now(dt.timezone.utc)
    t0 = time.monotonic()
    p = subprocess.run(["xcrun", "devicectl"] + launch, capture_output=True, text=True, timeout=args.timeout)
    console = p.stdout + p.stderr
    logs = os.path.join(args.out, "logs"); os.makedirs(logs, exist_ok=True)
    with open(os.path.join(logs, f"{slug}_run{run_idx}.console.log"), "w") as f:
        f.write(f"# xcrun devicectl {' '.join(launch)}\n# devicectl exit={p.returncode}\n")
        f.write(console)
    res = None
    for line in console.splitlines():
        if line.startswith("ASRBENCH_RESULT_JSON "):
            try:
                res = json.loads(line[len("ASRBENCH_RESULT_JSON "):])
            except json.JSONDecodeError:
                pass
    # The file in the container is authoritative (the console can truncate); devicectl
    # `copy from` takes a file path as the destination.
    tmp = tempfile.mkdtemp()
    if container_copy_from(dev, bundle, f"Documents/asr/results/{run_id}.json", os.path.join(tmp, "result.json")):
        try:
            res = json.load(open(os.path.join(tmp, "result.json")))
        except (OSError, json.JSONDecodeError):
            pass
    if container_copy_from(dev, bundle, f"Documents/asr/results/{run_id}.log", os.path.join(tmp, "stderr.log")):
        os.replace(os.path.join(tmp, "stderr.log"), os.path.join(logs, f"{slug}_run{run_idx}.stderr.log"))
    launch_refused = bool(re.search(r"CoreDeviceError error 4016|could not be, unlocked|specified device was not found|Device is not connected", console))
    metrics = {"coldRun": True, "harnessStamp": HARNESS_STAMP, "asrAudioSeconds": round(ctx["audio_s"], 3),
               "hostWallSeconds": round(time.monotonic() - t0, 3)}
    transcript = ""
    before_therm = after_therm = None
    if res:
        transcript = re.sub(r"\s+", " ", res.get("transcript") or "").strip()
        metrics["exitCode"] = res.get("exitCode")
        before_therm, after_therm = res.get("thermalInitial"), res.get("thermalFinal")
        metrics["initialThermalState"] = before_therm
        metrics["finalThermalState"] = after_therm
        metrics["loadTimeSeconds"] = round(res["loadTimeSeconds"], 3)
        metrics["engineCreateSeconds"] = round(res["engineCreateSeconds"], 3)
        if res.get("ok") and res.get("asrProcessingSeconds"):
            proc = res["asrProcessingSeconds"]
            metrics["asrProcessingSeconds"] = round(proc, 3)
            metrics["asrRealTimeFactor"] = round(proc / ctx["audio_s"], 4)
        if res.get("asrFirstTextLatencyMS") is not None:
            metrics["asrFirstTextLatencyMS"] = round(res["asrFirstTextLatencyMS"], 1)
        metrics["totalWallSeconds"] = round(res["totalWallSeconds"], 3)
        metrics["memoryPeakResidentMB"] = round(res["memoryPeakResidentMB"], 1)
        metrics["memoryPeakFootprintMB"] = round(res["memoryPeakFootprintMB"], 1)
    hyp = normalize(transcript)
    if hyp:
        s, d, i, n = wer_counts(ctx["ref_words"], hyp)
        metrics.update({"asrWordErrorRate": round((s + d + i) / n, 4), "asrSubstitutions": s,
                        "asrDeletions": d, "asrInsertions": i,
                        "asrReferenceWordCount": n, "asrHypothesisWordCount": len(hyp)})
    ok = bool(res and res.get("ok") and "asrRealTimeFactor" in metrics)
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
        "device": dict(ctx["device"], batteryState=(res or {}).get("batteryState"),
                       batteryLevel=(res or {}).get("batteryLevelInitial"),
                       lowPowerMode=((res or {}).get("device") or {}).get("lowPowerMode")),
        "conditions": {"asrChunkMilliseconds": cell["chunk_ms"], "asrOverlapRatio": ctx["overlap_ratio"],
                       "asrTextMerger": ctx["text_merger"], "asrNumThreads": ctx["num_threads"],
                       "gpuPrecision": "fp32 (AsrEngine sets GpuOptions::Precision::kFp32)" if cell["backend"] == "gpu" else None,
                       "gpuAcceleratorDylib": (res or {}).get("gpuAcceleratorDylib"),
                       "sampler": "engine default (ASR decoders are deterministic)",
                       "warm": False, "unplugged": (res or {}).get("batteryState") == "unplugged",
                       "thermalInitial": before_therm, "thermalFinal": after_therm},
        "metrics": metrics,
        "outputSample": transcript[:200], "transcript": transcript,
        "provenance": {"audioSet": ctx["set_name"], "audioStreamSha256": ctx["stream_sha256"],
                       "metadataJsonSha256": ctx["metadata_sha256"],
                       "tokenizerSha256": cell["tokenizer_sha256"], "modelSha256": cell["sha256"],
                       "launchArguments": launch[launch.index("--") + 1:],
                       "appResult": res, "devicectlExit": p.returncode, "launchRefused": launch_refused,
                       "consoleLog": os.path.relpath(os.path.join(logs, f"{slug}_run{run_idx}.console.log"), REPO)},
    }
    with open(os.path.join(args.out, f"{slug}.jsonl"), "a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    log(f"{'OK ' if ok else 'FAIL'} run {run_idx}: exit={metrics.get('exitCode')} load={metrics.get('loadTimeSeconds')}s "
        f"proc={metrics.get('asrProcessingSeconds')}s RTF={metrics.get('asrRealTimeFactor')} "
        f"WER={metrics.get('asrWordErrorRate')} footprint={metrics.get('memoryPeakFootprintMB')}MB "
        f"thermal={before_therm}->{after_therm} dylib={(res or {}).get('gpuAcceleratorDylib')}")
    return ok, after_therm, launch_refused


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cells")
    ap.add_argument("--campaign", required=True, help="results/raw/<campaign>-ios/")
    ap.add_argument("--device", default=os.environ.get("BENCH_UDID"), help="devicectl identifier")
    ap.add_argument("--bundle", default=os.environ.get("ASR_IOS_BUNDLE_ID", DEFAULT_BUNDLE))
    ap.add_argument("--runs", type=int, default=None, help="override runs= of every cell")
    ap.add_argument("--only", default=None, help="substring filter on model id (smoke)")
    ap.add_argument("--backend", default=None, choices=["cpu", "gpu"], help="run only this backend's rows")
    ap.add_argument("--pause", type=float, default=45.0, help="s between launches (the Android leg's 45 s)")
    ap.add_argument("--timeout", type=float, default=900.0)
    ap.add_argument("--base-cooldown", type=float, default=90.0)
    ap.add_argument("--thermal-wait", type=float, default=600.0,
                    help="max s to wait for the previous launch's final thermal state to be nominal")
    args = ap.parse_args()
    if not args.device:
        sys.exit("--device or BENCH_UDID is required (never guess a phone)")
    args.out = os.path.join(REPO, "results", "raw", f"{args.campaign}-ios")
    os.makedirs(args.out, exist_ok=True)
    runlog = open(os.path.join(args.out, "runlog.txt"), "a")

    def log(msg):
        line = f"{dt.datetime.now().strftime('%H:%M:%S')} {msg}"
        print(line, flush=True); runlog.write(line + "\n"); runlog.flush()

    app_dir = os.path.abspath(os.environ.get("ASR_IOS_APP_DIR", os.path.join(REPO, "ios", "AsrBench")))
    model_dir = os.path.abspath(os.environ.get("ASR_MODEL_DIR", os.path.join(REPO, ".build", "asr-models")))
    meta_path = os.path.abspath(os.environ.get("ASR_IOS_METADATA",
                                               os.path.join(REPO, ".build", "asr-runner-66058c82-ios", "model_metadata.json")))
    build_info = os.path.join(app_dir, "Frameworks", "BUILD_INFO")
    engine_version = open(build_info).read().strip() if os.path.exists(build_info) else "unknown"
    meta = json.load(open(meta_path))
    lib = os.path.join(app_dir, "Frameworks", "libasr_bench_static.a")
    dylib = os.path.join(app_dir, "Frameworks", "libLiteRtMetalAccelerator.dylib")
    engine_artifact = (f"ios/AsrBench (bench_ios/asr_bench_shim over //omni/asr:asr_engine + file_audio_source, "
                       f"bazel --config=ios_arm64 apple_static_library) libasr_bench_static.a sha256:{sha256(lib) if os.path.exists(lib) else 'n/a'}; "
                       f"libLiteRtMetalAccelerator.dylib sha256:{sha256(dylib) if os.path.exists(dylib) else 'n/a'} (prebuilt/ios_arm64 at the same commit)")

    cells = []
    for raw in open(args.cells):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        plat, rt, mid, task, opts = parse_line(line)
        if plat != "ios" or not task.startswith("asr-rtf-"):
            continue
        if args.only and args.only not in mid:
            continue
        if args.backend and opts.get("backend") != args.backend:
            continue
        if opts.get("exclude"):
            log(f"SKIPPED {rt} {mid} {task} backend={opts.get('backend')} reason={opts['exclude']}"); continue
        model_name = MODEL_NAMES[mid]
        org, name = mid.split("/", 1)
        cands = glob.glob(os.path.expanduser(f"~/.cache/huggingface/hub/models--{org}--{name}/snapshots/*/{opts['file']}"))
        cands = [c for c in cands if os.path.exists(c)]
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
        sys.exit("no ios asr-rtf-* cells matched")
    if args.runs:
        for c in cells:
            c["runs"] = args.runs

    task_set = TASK_SETS[cells[0]["task"]]
    stream_path, stream_sha, audio_s, reference, _ = build_stream(task_set)
    ctx = {"engine_version": engine_version, "engine_artifact": engine_artifact,
           "num_threads": int(os.environ.get("ASR_NUM_THREADS", "4")),
           "overlap_ratio": float(os.environ.get("ASR_OVERLAP_RATIO", "0.4")),
           "text_merger": os.environ.get("ASR_TEXT_MERGER", "timestamp"),
           "stream_name": os.path.basename(stream_path), "stream_sha256": stream_sha, "audio_s": audio_s,
           "ref_words": normalize(reference), "set_name": task_set, "metadata_sha256": sha256(meta_path),
           "device": device_details(args.device)}

    with open(os.path.join(args.out, "session_provenance.txt"), "a") as f:
        f.write(f"session start {dt.datetime.now().strftime('%F %T')}\ncells: {args.cells}\ndevice: {args.device}\n"
                f"device details: {json.dumps(ctx['device'])}\nbundle: {args.bundle}\nengine: {engine_version}\n"
                f"artifact: {engine_artifact}\nstream: {ctx['stream_name']} sha256 {stream_sha} {audio_s:.3f} s\n"
                f"protocol: threads={ctx['num_threads']} overlap={ctx['overlap_ratio']} merger={ctx['text_merger']}\n"
                f"pause between launches: {args.pause} s; cooldown before a cell: {args.base_cooldown} s (cells file overrides)\n")
    log(f"device {ctx['device']}")

    log("staging in the app container (Documents/asr/)")
    staged_path = os.path.join(args.out, ".staged.json")
    staged = json.load(open(staged_path)) if os.path.exists(staged_path) else {}
    stage_file(args.device, args.bundle, meta_path, "Documents/asr/bin/model_metadata.json", staged, log)
    stage_file(args.device, args.bundle, stream_path, f"Documents/asr/audio/{ctx['stream_name']}", staged, log)
    seen = set()
    for c in cells:
        if c["file"] not in seen:
            seen.add(c["file"])
            stage_file(args.device, args.bundle, c["local_path"], f"Documents/asr/models/{c['file']}", staged, log)
        if c["tokenizer"]:
            stage_file(args.device, args.bundle, c["tokenizer"], f"Documents/asr/models/{c['model_name']}_tokenizer.json", staged, log)
        elif meta[c["model_name"]].get("tokenizerUrl"):
            log(f"WARNING: no tokenizer staged for {c['model_name']} — the engine has no downloader on the phone")
        json.dump(staged, open(staged_path, "w"), indent=1)

    ok_all = True
    first = True
    last_thermal = "nominal"
    refused = 0
    for c in cells:
        if not first:
            log(f"cooldown {c['cooldown']:.0f}s"); time.sleep(c["cooldown"])
        first = False
        log(f"CELL {c['runtime']} / {c['model_id']} / {c['task']} backend={c['backend']} runs={c['runs']}")
        for r in range(1, c["runs"] + 1):
            if r > 1:
                time.sleep(args.pause)
            waited = 0.0
            while last_thermal not in (None, "nominal") and waited < args.thermal_wait:
                log(f"  thermal gate: previous launch ended {last_thermal} — waiting 30 s")
                time.sleep(30); waited += 30
                last_thermal = "nominal"  # the app reports the state at the next launch; the wait is the gate
            ok, last_thermal, launch_refused = one_run(args, ctx, c, r, log)
            ok_all &= ok
            refused = refused + 1 if launch_refused else 0
            if refused >= 2:
                log("DEVICE_LOST: the phone refused two launches in a row — session ended, captured runs stand")
                with open(os.path.join(args.out, "DEVICE_LOST.txt"), "a") as f:
                    f.write(f"{dt.datetime.now()} after {c['slug']} run {r}\n")
                return 1
    log(f"done: {args.out}")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
