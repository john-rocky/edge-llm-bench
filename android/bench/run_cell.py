#!/usr/bin/env python3
"""Run one Android benchmark cell: N fresh-process runs -> schema-v1 JSON each.

  python3 android/bench/run_cell.py --runtime litert-lm --backend gpu \\
      --model-id litert-community/Qwen3-0.6B --task short-chat --runs 3 \\
      --out results/raw/<campaign>/app-path-android

Design decisions (methodology/android.md):
  - one engine process per run = COLD by the repo's definition; the very first
    run per (model, backend) builds engine caches and is labelled firstEver.
    Detection is a marker file on the DEVICE ({DEV_DIR}/markers/): the caches
    live there, so host-side state cannot know whether this device already
    compiled this (model, backend). litert-lm (its NPU arm too, by the same
    marker: whether an AOT bundle builds anything on its first launch is for a
    device run to show), and the chat launches of a llama.cpp side build on the
    GPU (its OpenCL program cache); the pinned CPU llama.cpp build and llama.cpp
    on the NPU keep no persistent compile cache, so their first run is an
    ordinary cold run.
  - metrics use BenchmarkResult field names (what build_summary.py reads);
    absent metrics stay absent. llama-cli has no TTFT; litert has no sampler
    control (conditions.sampler = "engine-default", a disclosed same-budget
    deviation).
  - the recorded runtime is litert-lm-<backend> / llama.cpp — backend is part
    of arm identity (the join key has no backend column; same convention as
    core-ai's -ane/-gpu model ids). llama.cpp with --backend npu|gpu is
    llama.cpp-npu / llama.cpp-gpu: a side build (--engine-build <tag>, the
    official Snapdragon asset in {DEV_DIR}/engines/<tag>/{bin,lib}) run on the
    Hexagon HTP or the Adreno GPU (OpenCL); the bare llama.cpp arm is the
    pinned CPU build in the flat {DEV_DIR}, as before. litert-lm with
    --backend npu is a side build too (--engine-build <tag>: a LiteRT-LM
    runtime build with the Qualcomm dispatch and QNN libraries, flat in
    {DEV_DIR}/engines/<tag>/), arm litert-lm-npu.
  - side-build witness and device lines: the tool's sha AND every shared lib
    its pin lists (engine-pins.json so_files) must match, else the stamp is
    'unknown'; the engine's own device lines (llama.cpp: registry, `using
    device`, offloaded N/M, model buffer; LiteRT-LM: the chosen backend, the
    NPU accelerator's registration, the dispatch delegate's subgraphs) go to
    conditions.backendRegistered, and a launch whose lines do not show the
    cell's device is flagged backend-not-registered — kept, and out of every
    pool (render_leaderboard.arm_row).
  - executorch (docs/executorch-arm-v1.md): the tag's own runner of the model's
    family (llama_main for Qwen 3, gemma4_e2e_runner for Gemma 4) from
    {DEV_DIR}/executorch-<tag>[-<backend>]/, arm executorch-<backend>, an own
    export staged on the host under ET_MODEL_DIR (parsers.executorch_inputs:
    .pte, recipe.json, tokenizer, the prompt the runner reads). Its stderr goes
    to a file of its own, read after the launch: one stream would put a log
    line into the text (llama_main logs right after the first token).
  - CPU affinity: BENCH_CPU_MASK (default f0 — upstream recommendation, tuned
    on Pixel 8a; empty = no taskset). Recorded per run in conditions; the mask
    is a per-device choice, see CPU_MASK below and devices/*.md.
  - RSS is sampled from /proc/<pid>/status by an on-device loop (RSS_BASIS):
    VmRSS -> memoryMedianResidentMB, VmHWM -> memoryPeakResidentMB; iOS
    phys_footprint has no Android equivalent and is never fabricated.
  - conditions.screen is read from the phone right before every launch
    (device_probe.screen_conditions: "on-usb" / "off-usb (mWakefulness=…)",
    conditions.screenSource "measured" or "env"); on and off are both
    admissible, the record says which it was.
  - CPU frequency cap (cpu-cap-rule): a launch waits up to CPUCAP_WAIT s for
    every cpufreq policy's scaling_max_freq to be back at cpuinfo_max_freq; the
    on-device sampler reads each policy's scaling_max_freq with the RSS, and a
    run during which a policy of the engine's CPUs sat below its hardware
    maximum carries protocolFlags cpu-capped (conditions.cpuMaxFreqMHz). The
    run stays a record and pools into no number (render_leaderboard.arm_row).
  - engine sockets (onnxruntime-genai launches): the sampler lists the engine's
    socket fds every tick and classifies each new one once against the engine's
    /proc/<pid>/net tables (conditions.engineSockets = {"unix": n, "inet": m},
    distinct sockets over the launch; "other" = in neither table) — the official
    ORT GenAI build ships a telemetry SDK (docs/ortgenai-arm-v1.md). The other
    arms' launch shell and record layout are unchanged.
  - onnxruntime-genai (docs/ortgenai-arm-v1.md): --backend cpu, file= the GenAI
    folder in the HF repo at --revision (or a local folder), pushed file by file
    to {DEV_DIR}/models/<repo>_<folder name>/ and removed when the invocation
    ends (BENCH_ORTGENAI_KEEP_MODEL=1 keeps it; run_campaign.py keeps it for the
    whole campaign and removes it at the end). The engine is ortgenai_run in
    {DEV_DIR}/ortgenai/ beside the release AAR's libraries; its ORTGENAI report
    line is parsed by parsers.parse_ortgenai and kept whole in
    conditions.engineReport; model.quantization is the folder's entry in
    models/ortgenai-recipes.json (an unregistered folder is refused).
"""
import argparse
import atexit
import datetime
import hashlib
import json
import os
import shlex
import statistics
import subprocess
import sys
import time
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from device_probe import adb, battery, device_info, screen_conditions, thermal_status  # noqa: E402
import endurance_cell  # noqa: E402
import parsers  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import ortgenai_recipe  # noqa: E402  (stdlib lookup of the recipe registry)

DEV_DIR = "/data/local/tmp/llmbench"
# ONNX Runtime GenAI: ortgenai_run + model_benchmark + the AAR's libonnxruntime-genai.so
# and libmat.so + Maven onnxruntime-android's libonnxruntime.so (android/README.md)
ORTGENAI_DIR = f"{DEV_DIR}/ortgenai"
ORTGENAI_LIBS = ("libonnxruntime-genai.so", "libmat.so", "libonnxruntime.so")
ORTGENAI_CHAT_MODE = "single-turn, model chat_template.jinja default (Qwen3 thinking on)"
ORTGENAI_TELEMETRY = "off: ORT_DISABLE_TELEMETRY=1 before init + OgaSetTelemetryEnabled(false)"
ORTGENAI_METRICS = (
    "prefill tok/s = promptTokenCount / prefill_ms, the wall clock of ortgenai_run's "
    "AppendTokenSequences(prompt) (prompt forward pass + logits); TTFT = ttft_ms = "
    "AppendTokenSequences + the first GenerateNextToken (greedy pick from the prefill logits); "
    "decode tok/s = decode_tps = (gen_tokens - 1) / decode_ms_total, the summed wall clock of "
    "GenerateNextToken calls 2..N (each = one forward pass + greedy pick); gen_tokens counts "
    "every GenerateNextToken call, the one that samples EOS included; stop = EOS (IsDone) or "
    "the output budget (-g), no min_length; memory = the runner's VmRSS / VmHWM sampler of the "
    "engine process (rssBasis); past_present_share_buffer true allocates and zero-fills the KV "
    "cache for max_length = contextTokens (-ml) when the generator is created, so the memory "
    "numbers include it")
HARNESS_STAMP = "2026-08-android-cli-v1"
# CPU affinity mask for the engine process. "f0" (the upstream recommendation,
# tuned on Pixel 8a's 4 contiguous mid cores) is NOT device-neutral: on the
# Galaxy S26 (6 perf + 2 prime, no little cores) f0 spans the cluster boundary
# and collapses ggml's thread sync — 15 tok/s vs 105.6 unmasked on the same
# binary/model (probes: results/raw/2026-08-25-s26-llama-affinity-probes/).
# Empty string = no taskset. The actual value is recorded per run in
# conditions.cpuAffinity either way; devices/*.md states each device's choice.
CPU_MASK = os.environ.get("BENCH_CPU_MASK", "f0")
STRICT_SMOKE = os.environ.get("BENCH_STRICT_SMOKE") == "1"
# llama.cpp side builds (cells engine-build=<tag>): the release asset unpacked on the device as
# {ENGINES_DIR}/<tag>/{bin,lib} (android/README.md), never into the flat DEV_DIR, where the
# pinned CPU build's shared libs live — a second build's libggml*.so / libllama*.so there
# would replace them under the weekly job's llama.cpp rows.
ENGINES_DIR = f"{DEV_DIR}/engines"
# backend= of an Android llama.cpp row -> the ggml device its layers run on (--device, with
# -ngl 99): Hexagon HTP session 0, or the Adreno GPU through OpenCL
LLAMA_DEVICES = {"npu": "HTP0", "gpu": "GPUOpenCL"}
# A side build runs with the official Snapdragon wrapper's defaults (b11469
# scripts/snapdragon/run.py — the vendor's intended settings), not the binaries' bare ones:
# the chat tool -ngl 99 -fa on -ub 1024 -t 6; llama-bench -t 6, and -ub 1024 on an HTP device
# only (no -fa: llama-bench's own default, flash attention auto); every run
# GGML_HEXAGON_OPPOLL=1, an HTP run GGML_HEXAGON_DEVICES=<device>. Added here: llama-bench's
# -ngl 99 (every layer on the device, as the arm says) and a per-build OpenCL program cache.
# The CPU arm keeps its -t 4.
SIDE_THREADS = 6
SIDE_UBATCH = 1024
# the model buffer each device's weights land in (llama's "<name> model buffer size" line)
LLAMA_DEVICE_BUFFERS = {"HTP0": "HTP0", "GPUOpenCL": "OpenCL"}
# The side build's chat tool and its extra flags, in one place. The 2026-10-07 S26 smoke of
# b11469-snapdragon ran the b8999 form (llama-cli … -f … -st) and printed the same
# "[ Prompt: … | Generation: … ]" line; a later build that needs another tool or flags
# changes these two lines (the witness reads the tool's sha as <tool>_sha256 from the pin,
# so a new tool also needs that field in engine-pins.json).
SNAPDRAGON_CHAT_TOOL = "llama-cli"
SNAPDRAGON_CHAT_FLAGS = ""
# A side build's layout under {ENGINES_DIR}/<tag>: (the tool's subdir, the libs' subdir).
# llama.cpp's release asset keeps bin/ and lib/; the LiteRT-LM NPU build sits flat, its
# Hexagon skel in dsp/ (the pin's so_files names it dsp/<file>).
SIDE_DIRS = {"llama.cpp": ("bin", "lib"), "litert-lm": ("", "")}
# LiteRT-LM on the NPU (cells backend=npu engine-build=<tag>; arm litert-lm-npu): the
# build's advanced_main, which takes the NPU switches and prints BenchmarkInfo with
# --benchmark. The hardware KV-cache update stays off: with it on, the one bundle this arm
# runs (an own Qwen3 0.6B export) decodes garbage on the S26 (google-ai-edge/litert-torch#1290).
LITERT_NPU_TOOL = "litert_lm_advanced_main"
# Own NPU ahead-of-time exports the runner can name, keyed by the file's sha256:
# npu_export names every output model_qualcomm_<SoC>.litertlm whatever the model and
# recipe, so the name says nothing (quant-label-rule). "cacheTokens" = the KV cache the
# export fixed: an AOT bundle takes no --max_num_tokens, and the engine prints its length
# only when a request differs from it. docs/dashboard-cells-v1.md "LiteRT-LM on the NPU".
OWN_NPU_BUNDLES = {
    # Qwen3 0.6B for SM8850, model_qualcomm_SM8850.litertlm (783,864,161 bytes): Stage 4 of
    # the 2026-08-21 day-1 static-range build (its LlmMetadata section is that build's, byte
    # for byte); the export logs give the recipe, the calibration and the cache
    "f8909326639011c6123126c06c4f7d205857b1915c8b49de6844522fe5d211f2": {
        "quantization": ("own export, NPU AOT for SM8850: int8 weights (dynamic_wi8_afp32) with "
                         "static-range int16 activations, calibration 3 prompts x 8 decode steps; "
                         "prefill 128, cache 1024 (litert-torch npu_export, 2026-08-21)"),
        "cacheTokens": 1024},
}
# provenance.rssBasis of every record (schema: memoryPeakResidentMB). Until
# 2026-10-06 VmHWM was read only under BENCH_STRICT_SMOKE, so earlier records
# from any other sitting carry no peak.
RSS_BASIS = ("VmRSS and VmHWM from /proc/<engine pid>/status, read every 0.5 s from 1 s "
             "after launch until the engine process exits (load, prefill and decode inside "
             "the window); memoryMedianResidentMB = median of the VmRSS reads, "
             "memoryPeakResidentMB = the largest VmHWM read (the kernel's resident "
             "high-water mark since process start); kB / 1024")
# appended to a side build's rssBasis: on the S26 the NPU chat launch's VmHWM was 217 MiB with
# 406 MiB of weights and 448 MiB of KV in the HTP0 buffers (2026-10-07 smoke)
SIDE_RSS_NOTE = ("; the host process only: the device's buffers (HTP0 / OpenCL: weights, KV "
                 "cache, compute) are not in VmRSS / VmHWM")
# the same for the LiteRT-LM NPU build (its own deploy script's note: DSP-side allocation is
# not counted in VmHWM)
LITERT_NPU_RSS_NOTE = ("; the host process only: the NPU's buffers (Hexagon, through the Qualcomm "
                       "dispatch and QNN) are not in VmRSS / VmHWM")
# cpu-cap-rule (methodology/fairness-rules.md). On a charging Pixel 8a the mid cluster's
# scaling_max_freq fell from 2367 to 1418-2130 MHz 20-30 s into heavy runs, with the
# thermal status at 0, and every such llama.cpp run decoded at a third to a quarter of the
# uncapped runs' rate (2026-10-07, 7 of 21 launches). A launch waits up to CPUCAP_WAIT s
# for a cap to lift (those caps had lifted by the next launch, 120 s later), then runs
# anyway, flagged.
CPUFREQ = "/sys/devices/system/cpu/cpufreq"
CPUCAP_WAIT = int(os.environ.get("CPUCAP_WAIT", "300"))
# every policy's name, hardware maximum, current cap and CPUs, one line each
CPU_POLICY_PROBE = ("for p in " + CPUFREQ + "/policy*; do h=; m=; r=; read h <$p/cpuinfo_max_freq; "
                    "read m <$p/scaling_max_freq; read r <$p/related_cpus; "
                    "echo \"CPUFREQ ${p##*/} ${h:--} ${m:--} $r\"; done")
# executorch arm (docs/executorch-arm-v1.md): the tag's runners, one build directory per
# backend, android/bin/executorch-<tag>[-<backend>]/ on the host
# (android/scripts/build_executorch_llama_main.sh; the XNNPACK build has no suffix), pushed by
# hand to the same directory under DEV_DIR (the builds share their file names). A model's
# inputs are staged on the host under ET_MODEL_DIR and pushed beside its .pte.
EXECUTORCH_TAG = os.environ.get("BENCH_EXECUTORCH_TAG", "v1.5.1")
EXECUTORCH_BACKENDS = ("xnnpack", "vulkan", "qnn")
EXECUTORCH_MODEL_DIR = os.environ.get("ET_MODEL_DIR", os.path.join(ROOT, "models", "executorch"))
ANDROID_BIN_DIR = os.environ.get("BENCH_ANDROID_BIN_DIR", os.path.join(ROOT, "android", "bin"))
# the runner's stderr, read and removed after each launch (executorch_stderr)
EXECUTORCH_STDERR = f"{DEV_DIR}/run_err.txt"
# harnessStamp suffix: run_cell's launch protocol, the runner's own stats read by parsers
EXECUTORCH_STAMP = "+executorch-runner-stats"
# appended to rssBasis: the runner's own peak beside the sampler's VmHWM reads
EXECUTORCH_RSS_NOTE = {
    "llama_main": ("; executorch: memoryPeakResidentMB = the larger of that and the runner's own "
                   "peak (memoryPeakEngineReportedMB: getrusage ru_maxrss at the end of generation, "
                   "its stderr line 'RSS after finishing text generation', MiB) — a launch can end "
                   "between two 0.5 s reads above the last one"),
    "gemma4_e2e_runner": ("; executorch: memoryPeakResidentMB = the larger of that and the runner's "
                          "own peak (memoryPeakEngineReportedMB: the largest VmRSS it read at each "
                          "decode step, its report's 'Memory (peak)', MB = MiB)"),
}


def load_pins(serial=None):
    """android/engine-pins.json. BENCH_TEST_PINS names a fixture registry instead, for the
    FAKESELF selftest only: a side build whose sha256 the device round registers is
    witnessed in the selftest without an entry in the real registry."""
    p = os.environ.get("BENCH_TEST_PINS")
    if p and serial != "FAKESELF":
        raise SystemExit("BENCH_TEST_PINS is only for the FAKESELF selftest fixture")
    p = p or os.path.join(ROOT, "android", "engine-pins.json")
    if not os.path.exists(p):
        return {}
    with open(p) as fh:
        return json.load(fh)


def observed_engine(binname, pins, serial, engine_dir=None):
    """Stamp the OBSERVED on-device binary, matched by sha256 against the pins
    registry — never 'the newest pin' (registry/witness rule: the binary that
    is on the device is the one that measured the row; during an A/B rehearsal
    two tags alternate on the same device).

    A side build (engine_dir = {ENGINES_DIR}/<tag>, laid out as SIDE_DIRS says) must
    match its pin's so_files as well: there the engine is the shared libs (llama.cpp's
    tool is a 7 KB launcher; LiteRT-LM's NPU path runs in the Qualcomm dispatch and QNN
    libraries), so a lib that differs from the pin stamps 'unknown' whatever the tool
    says. A side build that is not on the device stops the cell before any launch."""
    key_by_bin = {"litert_lm_main": ("litert-lm", "litert_lm_main_sha256"),
                  "litert_lm_advanced_main": ("litert-lm", "litert_lm_advanced_main_sha256"),
                  "litert_lm_endurance_main": ("litert-lm", "litert_lm_endurance_main_sha256"),
                  "llama-cli": ("llama.cpp", "llama_cli_sha256"),
                  "llama-bench": ("llama.cpp", "llama_bench_sha256"),
                  "ortgenai/ortgenai_run": ("onnxruntime-genai", "ortgenai_run_sha256"),
                  "ortgenai/model_benchmark": ("onnxruntime-genai", "model_benchmark_sha256")}
    engine, field = key_by_bin.get(binname) or ("llama.cpp", binname.replace("-", "_") + "_sha256")
    if not engine_dir:
        out = adb(["shell", f"sha256sum {DEV_DIR}/{binname}"], serial)
    else:
        path = side_path(engine_dir, SIDE_DIRS[engine][0], binname)
        out = adb(["shell", f"sha256sum {path} 2>&1 || true"], serial)
        if not out.split() or len(out.split()[0]) != 64:
            raise SystemExit(f"{path} is not on the device ({out.strip()!r}) — push the side "
                             "build first (android/README.md, 'Side builds')")
    sha = out.split()[0]
    if binname.split("/")[0].startswith("executorch-"):
        # executorch: the tag's pin holds one sha per runner and build, <runner>_sha256 for
        # the XNNPACK build and <runner>_<backend>_sha256 for executorch-<tag>-<backend>/
        build_dir, runner = binname.split("/", 1)
        backend = next((b for b in EXECUTORCH_BACKENDS if build_dir.endswith("-" + b)), "")
        field = f"{runner}_{backend}_sha256" if backend else f"{runner}_sha256"
        for tag, entry in pins.get("executorch", {}).items():
            if entry.get(field) == sha:
                return tag, sha
        return f"unknown (on-device {binname} sha unmatched in android/engine-pins.json)", sha
    for tag, entry in pins.get(engine, {}).items():
        if entry.get(field) == sha:
            libs = entry.get("so_files") if (engine_dir or engine == "onnxruntime-genai") else None
            if libs:
                # a side build's pinned libs sit where SIDE_DIRS says; the ORT GenAI runtime
                # dir holds them beside ortgenai_run (the engine is the libraries there too)
                paths = {name: (side_path(engine_dir, SIDE_DIRS[engine][1], name) if engine_dir
                                else f"{DEV_DIR}/{os.path.dirname(binname)}/{name}") for name in libs}
                got = adb(["shell", "sha256sum " + " ".join(paths[name] for name in sorted(libs))
                           + " 2>&1 || true"], serial)
                on_device = {parts[1]: parts[0] for parts in
                             (line.split() for line in got.splitlines()) if len(parts) == 2}
                bad = [name for name in sorted(libs) if on_device.get(paths[name]) != libs[name]]
                if bad:
                    return (f"unknown (on-device {tag} {binname} with lib {', '.join(bad)} "
                            "unmatched in android/engine-pins.json)"), sha
            return tag, sha
    return f"unknown (on-device {binname} sha unmatched in android/engine-pins.json)", sha


def side_path(engine_dir, sub, name):
    """A file of a side build on the device: <engine_dir>/<sub>/<name>, or flat."""
    return f"{engine_dir}/{sub}/{name}" if sub else f"{engine_dir}/{name}"


def own_npu_bundle(sha):
    """An own NPU export's facts by the file's sha256 (OWN_NPU_BUNDLES) ->
    (model.quantization label or None, conditions.contextTokens): "aot-fixed-<n>" = the KV
    cache the export fixed. An unknown export gets no label here (guess_quant then says
    'unrecorded') and a cache length marked unrecorded."""
    entry = OWN_NPU_BUNDLES.get(sha)
    if not entry:
        return None, "aot-fixed (cache length unrecorded)"
    return entry["quantization"], f"aot-fixed-{entry['cacheTokens']}"


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_model(model_id, file_hint, runtime, serial):
    """HF-download (host cache) then adb-push once; returns (device_path, local_path).

    file= is REQUIRED when the repo holds more than one artifact: the quant
    variant is part of arm identity, and the Android arm must run the same
    file the iOS catalog pins (ModelCatalog primaryFile) — picking one by
    sort order would silently measure a different recipe.
    """
    # file= may be a LOCAL PATH (side-loaded artifact — e.g. a conversion that
    # is not published on HF, like the litert-local LFM/MiniCPM bundles): push
    # it directly, no download. Everything else resolves through the HF hub.
    if file_hint and os.path.exists(os.path.expanduser(file_hint)):
        local = os.path.expanduser(file_hint)
        dev_path = f"{DEV_DIR}/models/{model_id.replace('/', '_')}_{os.path.basename(local)}"
        push_verified(local, dev_path, serial)
        return dev_path, local
    from huggingface_hub import hf_hub_download, list_repo_files
    if file_hint:
        fname = file_hint
    else:
        files = list_repo_files(model_id)
        ext = ".litertlm" if runtime.startswith("litert-lm") else ".gguf"
        cands = [f for f in files if f.endswith(ext)]
        if len(cands) != 1:
            raise SystemExit(
                f"{model_id} holds {len(cands)} {ext} artifacts — pass file= in the "
                f"cell (match the iOS ModelCatalog primaryFile):\n  " + "\n  ".join(sorted(cands)))
        fname = cands[0]
    local = hf_hub_download(model_id, fname)
    # Guard against cache poisoning: a DIFFERENT downloader's interrupted
    # attempt can leave a truncated blob that hf_hub_download then trusts
    # (measured: 188 MB of a 1833 MB .litertlm, planted by the Mac app's
    # HubBridge — both platforms then failed on 'bad magic' / engine-create,
    # which read as an engine incompatibility until the size was checked).
    declared = None
    try:
        from huggingface_hub import HfApi
        info = HfApi().model_info(model_id, files_metadata=True)
        declared = next((f.size for f in info.siblings if f.rfilename == fname), None)
    except Exception:
        pass  # offline etc. — proceed on the cached file
    if declared and os.path.getsize(local) != declared:
        print(f"cached {fname} is {os.path.getsize(local)} bytes, HF declares "
              f"{declared} — re-downloading (poisoned cache)", file=sys.stderr)
        local = hf_hub_download(model_id, fname, force_download=True)
        if os.path.getsize(local) != declared:
            raise SystemExit(f"{fname}: size still mismatched after re-download")
    dev_path = f"{DEV_DIR}/models/{model_id.replace('/', '_')}_{fname}"
    push_verified(local, dev_path, serial)
    return dev_path, local


def push_verified(local, dev_path, serial):
    """Push unless the on-device file already matches the LOCAL SIZE. A bare
    existence check kept a truncated file forever after a mid-push USB drop
    (measured: 188 MB of a 1.8 GB .litertlm -> every run died on bad magic)."""
    want = os.path.getsize(local)
    have = subprocess.run(["adb"] + (["-s", serial] if serial else []) +
                          ["shell", f"stat -c %s {dev_path}"],
                          capture_output=True, text=True,
                          **({"timeout": 30} if os.environ.get("BENCH_SITTING") == "1" else {}))
    if STRICT_SMOKE:
        if have.returncode or have.stdout.strip() != str(want):
            raise SystemExit(f"strict smoke requires pre-staged matching model: {dev_path}")
        if adb(["shell", f"sha256sum {dev_path}"], serial).split()[0] != sha256_file(local):
            raise SystemExit(f"strict smoke model hash mismatch: {dev_path}")
        return
    if have.returncode == 0 and have.stdout.strip() == str(want):
        return
    adb(["shell", "mkdir", "-p", f"{DEV_DIR}/models"], serial)
    # A real (re)push means the engine caches that lived beside the old copy
    # are gone or stale, so this artifact's firstEver markers must go too —
    # otherwise the next run 1 rebuilds the cache with the marker still saying
    # "built" and pools as the engine's speed. Observed on the Pixel 8a
    # (2026-09-07): 10 markers present, 7 of their bundles deleted between the
    # split dashboard sessions to free storage.
    adb(["shell", f"rm -f {DEV_DIR}/markers/{os.path.basename(dev_path)}.*.cachebuilt"], serial)
    print(f"pushing {os.path.basename(local)} ({want >> 20} MB) …", file=sys.stderr)
    adb(["push", local, dev_path], serial, timeout=1800)
    out = adb(["shell", f"stat -c %s {dev_path}"], serial).strip()
    if out != str(want):
        raise SystemExit(f"push verification failed: device has {out} bytes, "
                         f"local is {want} — check the USB connection")


def ortgenai_dev_dir(model_id, folder):
    """The device folder one ORT GenAI model folder is pushed to (run_campaign.py removes it
    when the campaign ends): {DEV_DIR}/models/<repo>_<folder name>."""
    return f"{DEV_DIR}/models/{model_id.replace('/', '_')}_{os.path.basename(folder.rstrip('/'))}"


def resolve_ortgenai_folder(model_id, folder, revision):
    """onnxruntime-genai file= -> (host folder, {name: {bytes, sha256}}). A path that
    starts with / or ~ is a local (side-loaded) folder; anything else is the folder's
    path inside the HF repo, fetched at `revision` with snapshot_download (that folder
    only, into the host's HF cache)."""
    if folder.startswith(("/", "~")):
        local = os.path.expanduser(folder)
    else:
        if not revision:
            raise SystemExit("onnxruntime-genai: --revision <HF commit> is required for a folder in "
                             "an HF repo (cells revision=)")
        from huggingface_hub import snapshot_download
        local = os.path.join(snapshot_download(model_id, revision=revision,
                                               allow_patterns=[f"{folder}/*"]), folder)
    if not (os.path.isfile(os.path.join(local, "genai_config.json"))
            and os.path.isfile(os.path.join(local, "model.onnx"))):
        raise SystemExit(f"{local}: not a GenAI folder (genai_config.json and model.onnx expected)")
    return local, ortgenai_recipe.folder_files(local)


def push_ortgenai_folder(local, files, dev_dir, serial):
    """Push every file of the folder on its own, from its resolved path: an HF cache
    snapshot holds symlinks into blobs/, and a directory push carries the links, not the
    bytes (adb walks a pushed directory with lstat; not verified on a device).
    push_verified skips a file the device already holds at the same size and checks the
    size after a push, model.onnx and model.onnx.data included."""
    adb(["shell", "mkdir", "-p", dev_dir], serial)
    for name in files:
        push_verified(os.path.realpath(os.path.join(local, name)), f"{dev_dir}/{name}", serial)


def remove_ortgenai_folder(dev_dir, serial):
    """Free the phone's storage once the folder's runs are done (the 4B folder is 2.9 GB):
    one try, no device-loss retries (a phone that is gone keeps the folder, and the exit is
    not held up by it). run_cell.py calls it when it exits, run_campaign.py when the
    campaign ends."""
    if not dev_dir.startswith(f"{DEV_DIR}/models/") or "/.." in dev_dir:
        raise ValueError(f"refusing to remove {dev_dir}")
    try:
        adb(["shell", "rm", "-rf", dev_dir], serial, retries=1)
        print(f"removed {dev_dir}", file=sys.stderr)
    except Exception as exc:  # noqa: BLE001
        print(f"could not remove {dev_dir}: {exc}", file=sys.stderr)


def ortgenai_present(serial):
    out = adb(["shell", f"ls {ORTGENAI_DIR}/ortgenai_run >/dev/null 2>&1 && echo present || echo absent"],
              serial)
    return "present" in out


def engine_sockets(console):
    """{"unix": n, "inet": m[, "other": k]}: the distinct socket fds the sampler saw on the
    engine process, by the /proc/<pid>/net table that lists each one; None when the
    sampler never ticked (the engine exited within its first second)."""
    head = console.split("===ENGINE_OUTPUT===", 1)[0]
    if not any(line.startswith("VmRSS") for line in head.splitlines()):
        return None
    kinds = {}
    for line in head.splitlines():
        parts = line.split()
        if parts[:1] == ["SOCKET"] and len(parts) == 3:
            kinds[parts[1]] = parts[2]
    counts = {"unix": 0, "inet": 0}
    for kind in kinds.values():
        counts[kind] = counts.get(kind, 0) + 1
    return counts


def push_prompt(task, serial):
    local = os.path.join(ROOT, "prompts", "text", f"{task}.txt")
    if not os.path.exists(local):
        raise SystemExit(f"no canonical prompt for task {task!r} "
                         "(scripts/gen_task_prompts.py; same-budget rule)")
    dev_path = f"{DEV_DIR}/prompts/{task}.txt"
    present = False
    if STRICT_SMOKE:
        found = adb(["shell", f"if [ -e {dev_path} ]; then sha256sum {dev_path}; else echo MISSING; fi"], serial)
        if found.strip() != "MISSING":
            if found.split()[0] != sha256_file(local):
                raise SystemExit(f"strict smoke refuses to overwrite prompt: {dev_path}")
            present = True
    if not present:
        adb(["shell", "mkdir", "-p", f"{DEV_DIR}/prompts"], serial)
        adb(["push", local, dev_path], serial)
    budget = None
    for line in open(os.path.join(ROOT, "prompts", "text", "budgets.tsv")):
        t, b = line.split("\t")
        if t == task:
            budget = int(b)
    return dev_path, budget


DEFAULT_LLAMA_CTX = 4096  # llama-cli otherwise defaults to the model's TRAINING
# context (Qwen3: 40960) — measured 4.8 GB RSS for a 0.6B Q4 before this pin.


def context_prompt(runtime, task, context_tokens):
    return (runtime == "litert-lm" and context_tokens is not None
            and not task.startswith(("native-", "endurance-")))


def arm_name(runtime, backend):
    """The recorded runtime = arm identity: litert-lm-<backend>, llama.cpp-<backend> for a
    llama.cpp side build on the npu / gpu device, the bare runtime otherwise (the CPU
    llama.cpp arm stays `llama.cpp`)."""
    if runtime == "litert-lm":
        return f"litert-lm-{backend}"
    return f"{runtime}-{backend}" if backend else runtime


def capture_stem(runtime, backend, model_id, task, file_hint=None,
                 context_tokens=None, round_mode=False):
    arm = arm_name(runtime, backend)
    stem = f"{arm}_{model_id.replace('/', '_')}_{task}"
    # Preserve legacy filenames, including native/endurance captures. The new
    # round path keys both allocation and the exact explicit artifact choice.
    if round_mode or (context_tokens is not None and not task.startswith(("native-", "endurance-"))):
        artifact = hashlib.sha256((file_hint or "auto").encode()).hexdigest()
        stem += f"__ctx{context_tokens or 'default'}_file{artifact}"
    return stem


def engine_command(runtime, backend, model_dev, task, prompt_dev, budget, max_tokens,
                   context_tokens, engine_dir=None):
    """The on-device command line for one run. Returns (cmd, binname, sampler, ctx_note).
    engine_dir = a side build ({ENGINES_DIR}/<tag>): the tool by absolute path; llama.cpp
    with every layer on the backend's device, LiteRT-LM on the NPU; its env comes from
    launch_env."""
    if runtime.startswith("litert-lm") and engine_dir:
        # The NPU side build runs a prompt task on the bundle's own KV cache: an AOT bundle's
        # cache length is fixed at export (no --max_num_tokens; main() names it from the
        # bundle, ctx_note here is the placeholder). --benchmark with no synthetic token
        # counts keeps the real prompt and prints BenchmarkInfo (without it advanced_main
        # prints no rate; the reply is printed whenever benchmark_prefill_tokens is 0 —
        # LiteRT-LM main b12c62c7 runtime/engine/litert_lm_lib.cc). The dispatch library is
        # the build's own (--litert_dispatch_lib_dir; unset, LiteRT-LM looks beside the model).
        if context_tokens is not None or task.startswith(("native-", "endurance-")):
            raise SystemExit(f"litert-lm on the NPU runs a prompt task on the bundle's own KV cache "
                             f"(task {task!r}, context-tokens {context_tokens}): an AOT bundle's cache "
                             "is fixed at export, and the protocol and endurance paths are not wired")
        core = (f"{engine_dir}/{LITERT_NPU_TOOL} --backend={backend} --model_path={model_dev} "
                f"--input_prompt_file={prompt_dev} --max_output_tokens={max_tokens or budget} "
                "--async=false --benchmark --benchmark_prefill_tokens=0 --benchmark_decode_tokens=0 "
                f"--use_hw_cache_update_for_npu=false --litert_dispatch_lib_dir={engine_dir}")
        return core, LITERT_NPU_TOOL, "engine-default", "aot-fixed"
    if runtime.startswith("litert-lm"):
        ctx = f" --max_num_tokens={context_tokens}" if context_tokens else ""
        ctx_note = context_tokens or "bundle-default"
        if task.startswith("native-benchmark-"):
            # ONLY advanced_main consumes the benchmark token counts (verified
            # in v0.16.0 sources AND on device: the plain main ran its default
            # ~20-token prompt regardless of the flags).
            p, d = task[len("native-benchmark-"):].split("x")
            core = (f"./litert_lm_advanced_main --backend={backend} --model_path={model_dev} "
                    f"--benchmark --benchmark_prefill_tokens={p} "
                    f"--benchmark_decode_tokens={d} --async=false{ctx}")
            return core, "litert_lm_advanced_main", "engine-default", ctx_note
        if context_prompt(runtime, task, context_tokens):
            # v0.16.0 plain main ignores both context and output limits.
            # --benchmark enables per-Conversation BenchmarkInfo; zero synthetic
            # token overrides retain the real prompt and native output cap.
            core = (f"./litert_lm_advanced_main --backend={backend} --model_path={model_dev} "
                    f"--input_prompt_file={prompt_dev} --max_num_tokens={context_tokens} "
                    f"--max_output_tokens={max_tokens or budget} --num_iterations=2 "
                    "--async=false --benchmark --benchmark_prefill_tokens=0 "
                    "--benchmark_decode_tokens=0 --use_session=false")
            return core, "litert_lm_advanced_main", "engine-default", ctx_note
        core = (f"./litert_lm_main --backend={backend} --model_path={model_dev} "
                f"--input_prompt_file={prompt_dev} "
                f"--max_output_tokens={max_tokens or budget} --async=false{ctx}")
        # no temperature/top-p flags exist -> engine-default sampling, disclosed
        return core, "litert_lm_main", "engine-default", ctx_note
    if runtime == "llama.cpp":
        # -t matches the taskset f0 mask (4 mid cores): llama-bench defaults to
        # 9 threads, which busy-poll against a 4-core mask and hang (measured:
        # >5 min without output; -t 4 completes in seconds).
        ctx = context_tokens or DEFAULT_LLAMA_CTX
        if backend and not engine_dir:
            raise SystemExit(f"llama.cpp backend={backend} runs a side build: the cell needs "
                             "engine-build=<tag> (the pinned flat build is CPU-only)")
        if engine_dir:
            # Side build, the wrapper's defaults (SIDE_THREADS above). -lv 4 comes before
            # --device: b11469's llama-cli logs errors only by default, ggml / llama INFO lines
            # sit at verbosity 4 in its logger (common_log_get_verbosity: INFO -> TRACE), and
            # it loads the backends while it parses --device, so the registry lines need the
            # level set first (2026-10-07 S26 smoke: -lv 4 after --device lost them, -lv 3
            # printed none of the device lines). llama-bench silences llama's log whatever
            # its flags: its records carry the JSON's devices / backends fields instead.
            tool_dir, device = f"{engine_dir}/bin", LLAMA_DEVICES[backend]
            if task.startswith("native-benchmark-"):
                p, d = task[len("native-benchmark-"):].split("x")
                ub = f" -ub {SIDE_UBATCH}" if backend == "npu" else ""
                return (f"{tool_dir}/llama-bench -m {model_dev} -t {SIDE_THREADS} -p {p} -n {d} -o json "
                        f"-ngl 99{ub} --device {device}"), "llama-bench", "n/a (llama-bench)", "llama-bench-managed"
            flags = f" {SNAPDRAGON_CHAT_FLAGS}" if SNAPDRAGON_CHAT_FLAGS else ""
            return (f"{tool_dir}/{SNAPDRAGON_CHAT_TOOL} -lv 4{flags} -m {model_dev} -t {SIDE_THREADS} "
                    f"-c {ctx} -f {prompt_dev} -n {max_tokens or budget} --temp 0 --top-p 1 -st "
                    f"-ngl 99 -fa on -ub {SIDE_UBATCH} --device {device}"), SNAPDRAGON_CHAT_TOOL, "greedy", ctx
        if task.startswith("native-benchmark-"):
            p, d = task[len("native-benchmark-"):].split("x")
            return (f"./llama-bench -m {model_dev} -t 4 -p {p} -n {d} -o json"), \
                "llama-bench", "n/a (llama-bench)", "llama-bench-managed"
        # -st (single-turn): b8999's llama-cli REJECTS --no-conversation ("not
        # supported") and then loops forever echoing "> " on stdin EOF —
        # measured as a silent 1800 s hang. Single-turn chat runs the template
        # once and exits; the model's template defaults apply (Qwen3: thinking
        # ON), disclosed via conditions.chatMode.
        return (f"./llama-cli -m {model_dev} -t 4 -c {ctx} -f {prompt_dev} "
                f"-n {max_tokens or budget} --temp 0 --top-p 1 -st"), \
            "llama-cli", "greedy", ctx
    if runtime == "executorch":
        # The family's runner (parsers.executorch_runner_for: the name; the recipe.json must
        # agree, run_cell main), run through sh -c so that its stderr goes to its own file
        # (EXECUTORCH_STDERR) while run_once takes its stdout; exec makes the runner the
        # process run_once's pgrep and timeout see. llama_main reads the prompt the host
        # rendered with the model's chat template, pushed beside the .pte
        # (executorch_device_paths; prompt_dev is the unrendered one);
        # gemma4_e2e_runner takes the unrendered prompt as --prompt and applies its own
        # turn template.
        runner = parsers.executorch_runner_for(model_dev)
        if runner is None:
            raise SystemExit(f"executorch: no runner for {os.path.basename(model_dev)} "
                             "(parsers.executorch_runner_for knows Qwen 3 and Gemma 4)")
        binname = executorch_binname(backend, runner)
        tokenizer_dev, rendered_dev = executorch_device_paths(model_dev, task)
        prompt_arg = (f"--prompt_file={rendered_dev}" if runner == "llama_main"
                      else f'--prompt="$(cat {prompt_dev})"')
        inner = (f"exec ./{binname} --model_path={model_dev} --tokenizer_path={tokenizer_dev} "
                 f"{prompt_arg} --temperature=0 --max_new_tokens={max_tokens or budget} "
                 f"2>{EXECUTORCH_STDERR}")
        return f"sh -c {shlex.quote(inner)}", binname, parsers.EXECUTORCH_SAMPLER, \
            context_tokens or "export-fixed"
    if runtime == "onnxruntime-genai":
        if task.startswith(("native-", "endurance-")):
            raise SystemExit("onnxruntime-genai v1 rows are prompt tasks (a native-benchmark row "
                             "through model_benchmark is not wired; docs/ortgenai-arm-v1.md)")
        if not context_tokens:
            raise SystemExit("onnxruntime-genai needs --context-tokens: max_length, the KV cache it "
                             "allocates up front (cells context-tokens=)")
        # the tool by absolute path (run_once's mksh note), its env from launch_env;
        # ortgenai_run applies the folder's chat_template.jinja, greedy, no min_length
        core = (f"{ORTGENAI_DIR}/ortgenai_run -i {model_dev} --prompt_file {prompt_dev} "
                f"-g {max_tokens or budget} -ml {context_tokens}")
        return core, "ortgenai/ortgenai_run", "greedy", context_tokens
    raise SystemExit(f"unknown android runtime {runtime!r}")


def executorch_binname(backend, runner):
    """executorch-<tag>[-<backend>]/<runner>, relative to DEV_DIR (and to ANDROID_BIN_DIR)."""
    return f"executorch-{EXECUTORCH_TAG}{'' if backend == 'xnnpack' else '-' + backend}/{runner}"


def executorch_device_paths(model_dev, task):
    """The tokenizer and the rendered prompt pushed beside a .pte on the device."""
    stem = model_dev[:-len(".pte")] if model_dev.endswith(".pte") else model_dev
    return f"{stem}.tokenizer.json", f"{stem}.{task}.prompt.txt"


def push_exact(local, dev_path, serial):
    """Push a small input unless the device holds the same bytes (sha256), then verify.
    Strict smoke refuses to push, as push_verified does."""
    want = sha256_file(local)
    have = adb(["shell", f"sha256sum {dev_path} 2>&1 || true"], serial).split()
    if have[:1] == [want]:
        return
    if STRICT_SMOKE:
        raise SystemExit(f"strict smoke requires pre-staged matching input: {dev_path}")
    adb(["shell", "mkdir", "-p", os.path.dirname(dev_path)], serial)
    adb(["push", local, dev_path], serial, timeout=600)
    have = adb(["shell", f"sha256sum {dev_path} 2>&1 || true"], serial).split()
    if have[:1] != [want]:
        raise SystemExit(f"push verification failed: {dev_path} (device {have[:1]}, local {want})")


def executorch_binary_on_device(binname, serial):
    """Stop before any launch when the runner is not on the device (pushed by hand, as the
    other engines are)."""
    out = adb(["shell", f"sha256sum {DEV_DIR}/{binname} 2>&1 || true"], serial)
    if not out.split() or len(out.split()[0]) != 64:
        build_dir = binname.split("/")[0]
        raise SystemExit(f"{DEV_DIR}/{binname} is not on the device — adb push "
                         f"{os.path.relpath(os.path.join(ANDROID_BIN_DIR, build_dir), ROOT)} {DEV_DIR}/ "
                         "(android/scripts/build_executorch_llama_main.sh builds it)")


def executorch_stderr(serial):
    """The runner's stderr of the launch that just ended, read and removed from the device
    (a launch that never started the runner leaves none)."""
    return adb(["shell", f"cat {EXECUTORCH_STDERR} 2>/dev/null; rm -f {EXECUTORCH_STDERR}"],
               serial, retries=1)


def executorch_fields(console, et, budget, declared_context):
    """One executorch launch's console (run_once's, with the runner's stderr appended after
    ===ENGINE_STDERR===) -> parsers.executorch_record_fields."""
    engine = console.split("===ENGINE_OUTPUT===\n", 1)[-1]
    stdout, _, stderr = engine.partition("\n===ENGINE_STDERR===\n")
    stdout = stdout[:stdout.rfind("EXIT_CODE=")] if "EXIT_CODE=" in stdout else stdout
    if et["runner"] == "llama_main":
        parsed = parsers.parse_executorch(stdout, stderr, et["promptText"])
    else:
        parsed = parsers.parse_gemma4_runner(stdout, stderr)
    return parsers.executorch_record_fields(parsed, et, budget, declared_context)


def dry_run(args, arm, engine_dir):
    """--dry-run: the launch this invocation would make, with no device call — one JSON line
    with the on-device command as run_once starts it, the engine binary and, for executorch,
    the inputs it would push (checked as for a launch)."""
    with open(os.path.join(ROOT, "prompts", "text", "budgets.tsv")) as fh:
        budgets = dict(line.strip().split("\t") for line in fh if line.strip())
    budget = int(budgets[args.task]) if args.task in budgets else None
    plan = {"runtime": arm, "modelId": args.model_id, "task": args.task}
    local = args.file
    if args.runtime == "executorch":
        try:
            et = parsers.executorch_inputs(EXECUTORCH_MODEL_DIR, args.file, args.task, args.recipe, ROOT)
        except ValueError as e:
            raise SystemExit(f"executorch: {e}")
        local = et["pte"]
    if not local:
        raise SystemExit("--dry-run needs --file (no network resolution)")
    name = os.path.basename(local) if os.path.isabs(local) or local.startswith(("~", "./", "../")) else local
    model_dev = f"{DEV_DIR}/models/{args.model_id.replace('/', '_')}_{name}"
    if args.runtime == "onnxruntime-genai":  # a GenAI folder, pushed as <repo>_<folder name>/
        model_dev = ortgenai_dev_dir(args.model_id, args.file)
    prompt_dev = f"{DEV_DIR}/prompts/{args.task}.txt"
    cmd, binname, sampler, _ = engine_command(args.runtime, args.backend, model_dev, args.task, prompt_dev,
                                              budget, args.max_tokens, args.context_tokens,
                                              engine_dir=engine_dir)
    affinity = f"taskset {CPU_MASK} " if CPU_MASK else ""
    plan.update(command=f"cd {DEV_DIR} && {launch_env(engine_dir, args.backend, args.runtime)} {affinity}{cmd} "
                        f">{DEV_DIR}/run_out.txt 2>&1 </dev/null",
                binary=(side_path(engine_dir, SIDE_DIRS[args.runtime][0], binname) if engine_dir
                        else f"{DEV_DIR}/{binname}"), sampler=sampler)
    if args.runtime == "executorch":
        tokenizer_dev, rendered_dev = executorch_device_paths(model_dev, args.task)
        host_bin = os.path.join(ANDROID_BIN_DIR, binname)
        pushes = [(et["pte"], model_dev, et["pteSha256"]), (et["tokenizer"], tokenizer_dev, et["tokenizerSha256"])]
        pushes.append((et["prompt"], rendered_dev if et["runner"] == "llama_main" else prompt_dev,
                       et["promptSha256"]))
        plan.update(pushes=[{"local": a, "device": b, "sha256": c} for a, b, c in pushes],
                    hostBinary=host_bin,
                    hostBinarySha256=sha256_file(host_bin) if os.path.isfile(host_bin) else "missing",
                    quantization=et["label"], executorchRunner=et["runner"],
                    contextTokens=et["contextTokens"], promptSha256=et["promptSha256"],
                    stderrFile=EXECUTORCH_STDERR)
    print(json.dumps(plan, ensure_ascii=False))
    return 0


def launch_env(engine_dir=None, backend=None, runtime="llama.cpp"):
    """The env assignments in front of the engine command. The flat {DEV_DIR} build finds
    its shared libs in the cwd. A llama.cpp side build gets its own lib/ for them and for
    the Hexagon session's DSP libs, and the wrapper's Hexagon settings, in the official
    scripts/snapdragon/run.py order (for either device: the build loads every backend it
    ships), plus an OpenCL program cache of its own (unset, b11469 keeps one cache for
    every build under $TMPDIR/llama.cpp/cl-cache). The LiteRT-LM NPU build finds its
    dispatch and QNN libs in its own dir and the Hexagon skel in its dsp/, the system's
    DSP library dirs after it (the form of the build's own deploy script).
    onnxruntime-genai: its runtime dir holds the release AAR's libonnxruntime-genai.so +
    libmat.so and Maven's libonnxruntime.so, which GenAI dlopens from ORT_LIB_PATH;
    ORT_DISABLE_TELEMETRY=1 before the engine starts keeps the official build's telemetry
    off for the process (ortgenai_run refuses to start without it)."""
    if runtime == "onnxruntime-genai":
        return (f"LD_LIBRARY_PATH={ORTGENAI_DIR} ORT_LIB_PATH={ORTGENAI_DIR}/libonnxruntime.so "
                "ORT_DISABLE_TELEMETRY=1")
    if not engine_dir:
        return "LD_LIBRARY_PATH=."
    if runtime == "litert-lm":
        return (f'LD_LIBRARY_PATH={engine_dir} '
                f'ADSP_LIBRARY_PATH="{engine_dir}/dsp;/system/lib/rfsa/adsp;/vendor/lib/rfsa/adsp;/dsp"')
    env = f"LD_LIBRARY_PATH={engine_dir}/lib ADSP_LIBRARY_PATH={engine_dir}/lib"
    if backend == "npu":
        env += f" GGML_HEXAGON_DEVICES={LLAMA_DEVICES[backend]}"
    return env + f" GGML_HEXAGON_OPPOLL=1 GGML_OPENCL_KERNEL_CACHE_DIR={engine_dir}/clcache"


def run_once(cmd, binname, serial, timeout, env="LD_LIBRARY_PATH=.", sockets=False):
    """One engine process with an RSS sampler wrapped around it on-device.

    $! is the backgrounded subshell, not the engine (measured: sampling it
    reads ~1.7 MB forever) — resolve the real pid with pgrep -n on the binary
    name and sample that."""
    # Engine output goes to an on-device file, cat'ed AFTER wait: a backgrounded
    # engine's stdout is block-buffered and its exit-time flush races the adb
    # pty teardown — a 7-minute gemma GPU run lost its entire BenchmarkInfo
    # that way (EXIT_CODE=0, zero engine lines) while short runs got lucky.
    # Absolute paths only: `cd X && engine & rest` backgrounds the WHOLE
    # `cd && engine` list in mksh, so `rest` never inherits the cd (measured:
    # cat looked for run_out.txt in the wrong cwd while the engine ran fine).
    taskset_prefix = f"taskset {CPU_MASK} " if CPU_MASK else ""
    output_file = f"{DEV_DIR}/run_out_{uuid.uuid4().hex}.txt" if STRICT_SMOKE else f"{DEV_DIR}/run_out.txt"
    # VmHWM is the kernel's high-water mark, so a peak between two 0.5 s
    # VmRSS reads is not lost; Cpus_allowed_list is where the engine may run
    # (LiteRT-LM sets its own affinity, 4-8 on the Pixel 8a's Tensor G3)
    rss_command = "grep -E 'VmRSS|VmHWM|Cpus_allowed_list'"
    # cpu-cap-rule: each policy's hardware maximum and CPUs once, then every
    # policy's scaling_max_freq at launch and on each tick, printed when it
    # changes (read is a builtin: no process per tick)
    cpu_head = ("for p in " + CPUFREQ + "/policy*; do h=; r=; read h <$p/cpuinfo_max_freq; "
                "read r <$p/related_cpus; echo \"CPUPOLICY ${p##*/} ${h:--} $r\"; done; ")
    cpu_tick = ("c=CPUMAX; for f in " + CPUFREQ + "/policy*/scaling_max_freq; do m=; read m <$f; "
                "c=\"$c ${m:--}\"; done; [ \"$c\" = \"$pc\" ] || echo \"$c\"; pc=$c; ")
    # engine sockets: every socket fd of the engine, classified once when first seen
    # against the engine's own /proc/<pid>/net tables (unix, else inet, else other);
    # one ls per tick, the rest are builtins until a new socket appears
    sock_tick = ("for l in $(ls -l /proc/$epid/fd 2>/dev/null); do case $l in socket:\\[*) "
                 "i=${l#socket:\\[}; i=${i%\\]}; case \" $sk \" in *\" $i \"*) ;; *) sk=\"$sk $i\"; k=other; "
                 "if grep -qE \" $i( |\\$)\" /proc/$epid/net/unix 2>/dev/null; then k=unix; "
                 "elif cat /proc/$epid/net/tcp /proc/$epid/net/tcp6 /proc/$epid/net/udp /proc/$epid/net/udp6 "
                 "2>/dev/null | grep -qE \" $i( |\\$)\"; then k=inet; fi; echo \"SOCKET $i $k\";; esac;; esac; done; ")
    timeout_prefix = ""
    if os.environ.get("BENCH_SESSION_DEADLINE"):
        remaining = float(os.environ["BENCH_SESSION_DEADLINE"]) - time.time()
        # Native timeout bounds only this launch's child, including USB loss.
        timeout_prefix = f"timeout -k 2 {max(1, int(min(timeout, remaining - 8)))} "
        timeout = min(timeout, max(1, remaining - 2))
    shell = (f"cd {DEV_DIR} && {env} {taskset_prefix}{timeout_prefix}{cmd} "
             f">{output_file} 2>&1 </dev/null & pid=$!; " + cpu_head + cpu_tick +
             f"sleep 1; epid=$(pgrep -n -f {binname}); [ -z \"$epid\" ] && epid=$pid; "
             "sk=; while kill -0 $pid 2>/dev/null; do "
             f"{rss_command} /proc/$epid/status 2>/dev/null; " + (sock_tick if sockets else "") + cpu_tick
             + "sleep 0.5; done; "
             f"wait $pid; ec=$?; echo ===ENGINE_OUTPUT===; cat {output_file}; echo EXIT_CODE=$ec")
    if STRICT_SMOKE:
        shell = "set -C; " + shell  # refuse even an accidental output-path collision
    try:
        # retries=1: a launch that loses the phone fails here (no record; the
        # campaign lists it in FAILURES.txt) and is never replayed after
        # wait-for-device — a replay runs on whatever the phone became (a reboot
        # on 2026-10-07) and its record would read as this launch
        out = adb(["shell", shell], serial, timeout=timeout, retries=1)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        if not STRICT_SMOKE:
            raise
        out = exc.output or ""
        if isinstance(out, bytes):
            out = out.decode(errors="replace")
        out += f"\nHOST_ADB_FAILURE: {exc}\nEXIT_CODE={getattr(exc, 'returncode', 124)}\n"
    if STRICT_SMOKE:
        out += f"\nON_DEVICE_RAW_LOG={output_file}\n"
    rss_kb = [int(x) for x in
              (line.split()[1] for line in out.splitlines() if line.startswith("VmRSS"))]
    exit_code = 1
    for line in out.splitlines():
        if line.startswith("EXIT_CODE="):
            exit_code = int(line.split("=", 1)[1])
    return out, exit_code, (statistics.median(rss_kb) / 1024 if rss_kb else None)


def khz(text):
    return int(text) if text.isdigit() else None


def mhz(value_khz):
    return value_khz // 1000 if value_khz % 1000 == 0 else round(value_khz / 1000, 1)


def cpu_set(text):
    """A kernel CPU list ("4-8", "0-3,8", "0 1 2 3") -> {4, 5, 6, 7, 8}."""
    cpus = set()
    for part in text.replace(" ", ",").split(","):
        first, _, last = part.partition("-")
        if first.isdigit() and (not last or last.isdigit()):
            cpus.update(range(int(first), int(last or first) + 1))
    return cpus


def cpu_list(cpus):
    """{4, 5, 6, 7} -> "4-7" (the kernel's list form)."""
    runs = []
    for c in sorted(cpus):
        if runs and c == runs[-1][1] + 1:
            runs[-1][1] = c
        else:
            runs.append([c, c])
    return ",".join(f"{a}-{b}" if b > a else f"{a}" for a, b in runs)


def cpu_policies(serial):
    """{policy: {"hw": kHz, "max": kHz, "cpus": {cpu, …}}} as the phone reads now
    (cpuinfo_max_freq, scaling_max_freq, related_cpus); {} without cpufreq."""
    out = adb(["shell", CPU_POLICY_PROBE], serial)
    policies = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) < 4 or parts[0] != "CPUFREQ" or khz(parts[2]) is None:
            continue
        policies[parts[1]] = {"hw": khz(parts[2]), "max": khz(parts[3]),
                              "cpus": cpu_set(" ".join(parts[4:]))}
    return policies


def wait_cpu_uncapped(serial, out_dir):
    """cpu-cap-rule, before a launch: wait up to CPUCAP_WAIT s (10 s polls) until every
    policy's scaling_max_freq is back at its cpuinfo_max_freq. -> True when the wait ran
    out: the launch runs anyway, flagged cpu-capped-at-start, with one line in
    THERMAL_GATE.txt beside the thermal gate's (the job's SESSION.json lists that file)."""
    t0 = time.time()
    deadline = min(t0 + CPUCAP_WAIT, float(os.environ.get("BENCH_SESSION_DEADLINE", "inf")))
    while True:
        capped = {name: p for name, p in cpu_policies(serial).items()
                  if p["max"] is not None and p["max"] < p["hw"]}
        if not capped:
            return False
        caps = ", ".join(f"{name} {mhz(p['max'])}/{mhz(p['hw'])} MHz" for name, p in sorted(capped.items()))
        if time.time() >= deadline:
            with open(os.path.join(out_dir, "THERMAL_GATE.txt"), "a") as fh:
                fh.write(f"cpu cap gate timeout after {time.time() - t0:.0f}s at "
                         f"{time.strftime('%F %T')}; ran anyway: {caps}\n")
            return True
        print(f"cpu cap gate: {caps} — waiting…", flush=True)
        time.sleep(min(10, max(0.1, deadline - time.time())))


def cpu_reads(console):
    """The sampler's CPU lines of one launch (run_once), before the engine output ->
    ({policy: {"hw": kHz or None, "cpus": {cpu, …}}}, {policy: [scaling_max_freq kHz, …]},
    [Cpus_allowed_list reads])."""
    order, policies, maxes, allowed = [], {}, {}, []
    for line in console.split("===ENGINE_OUTPUT===", 1)[0].splitlines():
        parts = line.split()
        if parts[:1] == ["CPUPOLICY"] and len(parts) >= 3:
            order.append(parts[1])
            policies[parts[1]] = {"hw": khz(parts[2]), "cpus": cpu_set(" ".join(parts[3:]))}
        elif parts[:1] == ["CPUMAX"] and len(parts) == len(order) + 1:
            for name, value in zip(order, parts[1:]):
                if khz(value) is not None:
                    maxes.setdefault(name, []).append(khz(value))
        elif parts[:1] == ["Cpus_allowed_list:"] and len(parts) == 2:
            allowed.append(parts[1])
    return policies, maxes, allowed


def cpu_conditions(console):
    """cpu-cap-rule for one launch -> (conditions, capped).

    conditions.cpusAllowedList = the engine's last Cpus_allowed_list read: where it was
    allowed to run, which conditions.cpuAffinity (the launch mask) is not when the engine
    sets its own affinity (LiteRT-LM: 4-8 on the Pixel 8a's Tensor G3, under taskset f0).
    conditions.cpuMaxFreqMHz = {policy: {"min": the lowest scaling_max_freq the sampler
    read, "hw": cpuinfo_max_freq, "cpus": the policy's CPUs}} in MHz. capped = the
    policies of the engine's CPUs whose min sat below hw: the engine's CPUs are every
    Cpus_allowed_list it was read with (LiteRT-LM widens its own affinity mid-launch),
    else the launch mask, else every CPU."""
    policies, maxes, allowed = cpu_reads(console)
    freq = {name: {"min": mhz(min(maxes[name])), "hw": mhz(p["hw"]), "cpus": cpu_list(p["cpus"])}
            for name, p in policies.items() if p["hw"] is not None and maxes.get(name)}
    conditions = {"cpusAllowedList": allowed[-1]} if allowed else {}
    if freq:
        conditions["cpuMaxFreqMHz"] = freq
    engine_cpus = set().union(*(cpu_set(a) for a in allowed))
    if not engine_cpus and CPU_MASK:
        try:
            mask = int(CPU_MASK, 16)
            engine_cpus = {c for c in range(mask.bit_length()) if mask >> c & 1}
        except ValueError:
            pass
    capped = [f"{name} min {freq[name]['min']}/{freq[name]['hw']} MHz (cpus {freq[name]['cpus']})"
              for name, p in policies.items() if name in freq
              and (not engine_cpus or not p["cpus"] or p["cpus"] & engine_cpus)
              and min(maxes[name]) < p["hw"]]
    return conditions, capped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runtime", required=True, choices=["litert-lm", "llama.cpp", "onnxruntime-genai"])
    ap.add_argument("--backend", default=None, choices=["cpu", "gpu", "npu"],
                    help="litert-lm: cpu|gpu, npu on a side build (--engine-build); llama.cpp: "
                         "npu|gpu on a side build, none = the CPU arm; onnxruntime-genai: cpu")
    ap.add_argument("--engine-build", default=None,
                    help=f"side build on the device, {ENGINES_DIR}/<tag> (an android/engine-pins.json "
                         "key): llama.cpp's {bin,lib}, the LiteRT-LM NPU build flat; without it the "
                         "flat pinned build")
    ap.add_argument("--model-id", required=True)
    ap.add_argument("--file", default=None, help="artifact filename inside the HF repo "
                                                 "(onnxruntime-genai: the GenAI folder's path in it)")
    ap.add_argument("--revision", default=None,
                    help="HF commit to fetch --file at (onnxruntime-genai, cells revision=)")
    ap.add_argument("--task", required=True)
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--max-tokens", type=int, default=None)
    ap.add_argument("--context-tokens", type=int, default=None)
    ap.add_argument("--out", required=True)
    ap.add_argument("--serial", default=None)
    ap.add_argument("--first-ever", action="store_true",
                    help="force-mark run 1 as firstEver (the on-device marker "
                         "detects it automatically for litert-lm)")
    ap.add_argument("--cooldown", type=int, default=0,
                    help="seconds to sleep between runs 2..N (the campaign "
                         "runner passes COOLDOWN; bare CLI smoke runs default 0)")
    ap.add_argument("--timeout", type=int, default=1800)
    ap.add_argument("--round-index", type=int)
    ap.add_argument("--launch-index", type=int)
    ap.add_argument("--gate-timed-out", action="store_true")
    ap.add_argument("--recipe", default=None,
                    help="executorch: the cells' recipe= alias (parsers.EXECUTORCH_RECIPES)")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the launch (on-device command, binary, inputs) without any device call")
    # the executorch arm's runtime and backends (docs/executorch-arm-v1.md)
    for action in ap._actions:
        if action.dest == "runtime":
            action.choices = [*action.choices, "executorch"]
        elif action.dest == "backend":
            action.choices = [*action.choices, *EXECUTORCH_BACKENDS]
    args = ap.parse_args()

    if args.runtime == "litert-lm" and not args.backend:
        ap.error("litert-lm needs --backend cpu|gpu|npu (arm identity)")
    if args.runtime == "litert-lm" and (args.backend == "npu") != bool(args.engine_build):
        ap.error("litert-lm on the NPU is a side build: pass --backend npu and --engine-build together "
                 "(the Qualcomm dispatch runs in a LiteRT-LM build with its libraries, "
                 f"{ENGINES_DIR}/<tag>; --engine-build is read for the NPU only)")
    if args.runtime == "litert-lm" and args.engine_build and (
            args.context_tokens is not None or args.task.startswith(("native-", "endurance-"))):
        ap.error("litert-lm on the NPU runs a prompt task on the bundle's own KV cache: no "
                 "--context-tokens (an AOT bundle's cache is fixed at export), no native-benchmark- "
                 "or endurance- task (not wired)")
    if args.runtime == "llama.cpp" and args.backend == "cpu":
        ap.error("llama.cpp without --backend is the CPU arm (`llama.cpp`); --backend takes npu|gpu")
    if args.runtime == "llama.cpp" and bool(args.backend) != bool(args.engine_build):
        ap.error("llama.cpp on npu|gpu is a side build: pass --backend and --engine-build together "
                 "(--engine-build alone would stamp the CPU arm `llama.cpp` with a second build)")
    ort = args.runtime == "onnxruntime-genai"
    if ort and (args.backend != "cpu" or args.engine_build):
        ap.error("onnxruntime-genai on Android takes --backend cpu (the official AAR is CPU-only) "
                 "and no --engine-build (its runtime dir is " + ORTGENAI_DIR + ")")
    if ort and not args.file:
        ap.error("onnxruntime-genai needs --file <the GenAI folder in the HF repo, or a local folder>")
    arm = arm_name(args.runtime, args.backend)
    engine_dir = f"{ENGINES_DIR}/{args.engine_build}" if args.engine_build else None
    if args.runtime == "executorch":
        if args.backend not in EXECUTORCH_BACKENDS or args.engine_build:
            ap.error("executorch needs --backend xnnpack|vulkan|qnn (arm identity) and no --engine-build")
        if not args.file or not args.recipe:
            ap.error("executorch needs --file <the .pte, under ET_MODEL_DIR> and --recipe <alias>")
    elif args.backend in EXECUTORCH_BACKENDS or args.recipe:
        ap.error("--backend xnnpack|vulkan|qnn and --recipe belong to --runtime executorch")
    if args.dry_run:
        return dry_run(args, arm, engine_dir)

    if endurance_cell.ENDURANCE_TASK.match(args.task):
        if args.runtime != "litert-lm":
            ap.error("endurance-chat is litert-lm-only (needs the persistent-"
                     "conversation driver; methodology/endurance.md)")
        if args.runs > 1:
            print(f"WARNING --runs {args.runs} ignored for endurance — one "
                  "session per invocation; sessions are never pooled",
                  file=sys.stderr)
        return endurance_cell.run(args)

    pins = load_pins(args.serial)

    et = cell_file = None
    if args.runtime == "executorch":
        try:
            et = parsers.executorch_inputs(EXECUTORCH_MODEL_DIR, args.file, args.task, args.recipe, ROOT)
        except ValueError as e:
            raise SystemExit(f"executorch: {e}")
        # ensure_model pushes the staged .pte from its local path; capture_stem keys the
        # records on the cells' file=, as run_campaign does
        cell_file, args.file = args.file, et["pte"]
    ort_model = None
    if ort:
        if not ortgenai_present(args.serial):
            raise SystemExit(f"{ORTGENAI_DIR}/ortgenai_run is not on the device: push android/bin/ortgenai-0.17.0/ "
                             f"to {ORTGENAI_DIR}/ (android/README.md)")
        local, files = resolve_ortgenai_folder(args.model_id, args.file, args.revision)
        recipe = ortgenai_recipe.lookup(args.model_id, args.file, files["model.onnx"]["sha256"])
        if not recipe:
            raise SystemExit(f"{args.model_id} {args.file} (model.onnx sha256 {files['model.onnx']['sha256'][:12]}) "
                             "has no recipe label in models/ortgenai-recipes.json (quant-label-rule); register it: "
                             + ortgenai_recipe.register_command(local, args.model_id, args.file, args.revision))
        model_dev, model_local = ortgenai_dev_dir(args.model_id, args.file), os.path.join(local, "model.onnx")
        push_ortgenai_folder(local, files, model_dev, args.serial)
        if os.environ.get("BENCH_ORTGENAI_KEEP_MODEL") != "1":
            # the folder leaves the phone when this invocation ends (run_campaign.py sets
            # BENCH_ORTGENAI_KEEP_MODEL=1 and removes it when the campaign ends)
            atexit.register(remove_ortgenai_folder, model_dev, args.serial)
        ort_model = {"id": args.model_id, **({"hfRevision": args.revision} if args.revision else {}),
                     "quantization": recipe["label"], "file": args.file,
                     "sha256": files["model.onnx"]["sha256"],
                     # the weights the engine loads: model.onnx and its external data file
                     "bytes": sum(files[n]["bytes"] for n in ("model.onnx", "model.onnx.data") if n in files),
                     "files": files}
    else:
        model_dev, model_local = ensure_model(args.model_id, args.file, args.runtime, args.serial)
    if et:
        args.file = cell_file
    model_sha = ort_model["sha256"] if ort else sha256_file(model_local)
    prompt_dev = budget = prompt_text = None
    if not args.task.startswith("native-benchmark-"):
        prompt_dev, budget = push_prompt(args.task, args.serial)
        if engine_dir:  # the text the chat tool echoes before its reply (llama_cli_reply)
            with open(os.path.join(ROOT, "prompts", "text", f"{args.task}.txt")) as fh:
                prompt_text = fh.read()
    cmd, binname, sampler, ctx_note = engine_command(
        args.runtime, args.backend, model_dev, args.task,
        prompt_dev, budget, args.max_tokens, args.context_tokens, engine_dir=engine_dir)
    litert_npu = args.runtime == "litert-lm" and bool(engine_dir)
    quantization = None
    if litert_npu:  # the label and the KV cache of an own NPU export, by its sha256
        quantization, ctx_note = own_npu_bundle(model_sha)
    env = launch_env(engine_dir, args.backend, args.runtime)
    if et:
        tokenizer_dev, rendered_dev = executorch_device_paths(model_dev, args.task)
        push_exact(et["tokenizer"], tokenizer_dev, args.serial)
        if et["runner"] == "llama_main":
            push_exact(et["prompt"], rendered_dev, args.serial)
        executorch_binary_on_device(binname, args.serial)
    engine_version, engine_artifact = observed_engine(binname, pins, args.serial, engine_dir)
    engine_tag = engine_version
    if not engine_tag.startswith("unknown"):
        # a pins entry may name its build for the record (ORT GenAI: the release AAR's
        # libraries + Maven's onnxruntime-android); the witness stays the tag's shas
        engine_version = pins.get(args.runtime, {}).get(engine_tag, {}).get("engine_version", engine_tag)
    if os.environ.get("BENCH_SITTING") == "1":
        # the expected build: the cell's side build, else the pin; llama.cpp's field follows
        # the tool (a llama-bench cell compared llama-bench's sha with llama_cli_sha256 and
        # always stopped here before 2026-10-07); a build the registry does not hold stops too.
        # executorch (no --engine-build): the tag's pin, one sha per runner and build as
        # observed_engine reads it — <runner>_sha256 for the XNNPACK build,
        # <runner>_<backend>_sha256 for executorch-<tag>-<backend>/ (every executorch cell
        # stopped here before 2026-10-08)
        expected_version = args.engine_build or ("v0.16.0" if args.runtime == "litert-lm"
                                                 else "0.17.0" if ort else "v1.5.1" if et else "b8999")
        expected_field = ("litert_lm_advanced_main_sha256" if args.runtime == "litert-lm"
                          else "ortgenai_run_sha256" if ort else binname.replace("-", "_") + "_sha256")
        if et:
            runner = binname.split("/", 1)[1]
            expected_field = (f"{runner}_sha256" if args.backend == "xnnpack"
                              else f"{runner}_{args.backend}_sha256")
        pinned = pins.get(args.runtime, {}).get(expected_version, {}).get(expected_field)
        if engine_tag != expected_version or engine_artifact != pinned:
            print(f"PIN MISMATCH before launch: {binname} {engine_version} {engine_artifact}", flush=True)
            return 5
    paired = context_prompt(args.runtime, args.task, args.context_tokens)
    extended = paired or args.round_index is not None or (
        args.context_tokens is not None and not args.task.startswith(("native-", "endurance-")))

    # firstEver detection: marker beside the on-device caches (see module doc).
    cache_built = True
    marker = None
    if args.runtime == "litert-lm":
        marker = (f"{DEV_DIR}/markers/"
                  f"{os.path.basename(model_dev)}.{args.backend}.cachebuilt")
        if paired:
            marker = marker.replace(".cachebuilt", f".{engine_artifact}.ctx{args.context_tokens}.cachebuilt")
        out = adb(["shell", f"ls {marker} >/dev/null 2>&1 && echo present || echo absent"],
                  args.serial)
        cache_built = "present" in out
    elif engine_dir and args.backend == "gpu" and binname != "llama-bench":
        # The side build's OpenCL program cache (launch_env): the first chat launch compiles
        # the programs into it (17.7 s at load on the S26, 2026-10-07; 40 ms from the cache
        # after). litert's marker scheme, one marker per (model, arm, build), and a cache
        # dir without a program reads as not built whatever the markers say (a re-pushed
        # build). llama-bench compiles at load too, but times after its warmup run.
        marker = (f"{DEV_DIR}/markers/"
                  f"{os.path.basename(model_dev)}.{arm}.{engine_artifact}.cachebuilt")
        out = adb(["shell", f"ls {marker} >/dev/null 2>&1 && ls {engine_dir}/clcache/*.clbin "
                            ">/dev/null 2>&1 && echo present || echo absent"], args.serial)
        cache_built = "present" in out

    os.makedirs(args.out, exist_ok=True)
    dev = device_info(args.serial)
    ok = 0
    for i in range(1, args.runs + 1):
        if i > 1 and args.cooldown:
            time.sleep(args.cooldown)
        start_capped = wait_cpu_uncapped(args.serial, args.out)
        raw_status, thermal_name = thermal_status(args.serial)
        batt = battery(args.serial)
        screen = screen_conditions(args.serial)
        t0 = time.time()
        console, exit_code, rss_mb = run_once(cmd, binname, args.serial, args.timeout, env, sockets=ort)
        elapsed = time.time() - t0
        if et:
            console += "\n===ENGINE_STDERR===\n" + executorch_stderr(args.serial)
        cpu_cond, cpu_capped = cpu_conditions(console)
        # a measurement condition, not an engine failure: kept out of launch_checks, so
        # the run's OK / exit code / firstEver marker stay what the engine made them
        cpu_flags = (["cpu-capped"] if cpu_capped else []) + (["cpu-capped-at-start"] if start_capped else [])
        launch_id = str(uuid.uuid4()) if extended else None
        launch_checks = {}
        tests = None

        if paired:
            iteration_metrics, launch_checks = parsers.context_prompt_results(
                console, args.context_tokens, args.max_tokens or budget)
            if STRICT_SMOKE and args.task == "long-context-2048-gen256" and any(
                    m.get("promptTokenCount", 0) < 1000 for m in iteration_metrics):
                launch_checks["protocolFlags"].append("real-long-prompt-not-prefilled")
            # Missing iterations still leave failed records and the whole log.
            iteration_metrics += [{} for _ in range(max(0, 2 - len(iteration_metrics)))]
            cold = True
            metrics = iteration_metrics[0]
        elif args.runtime == "llama.cpp" and args.task.startswith("native-benchmark-"):
            tests = parsers.parse_llama_bench_json(console)
            metrics = {}
            for t in tests:
                if t["kind"] == "prefill":
                    metrics["promptTokensPerSecond"] = t["avg_ts"]
                    metrics["promptTokenCount"] = t["n_prompt"]
                else:
                    metrics["decodeTokensPerSecond"] = t["avg_ts"]
                    metrics["generatedTokenCount"] = t["n_gen"]
            cold = False  # llama-bench repeats in-process (warm-ish regime)
        elif args.runtime == "llama.cpp":
            metrics = parsers.parse_llama_cli(console)
            cold = True
        elif et:
            et_fields = executorch_fields(console, et, args.max_tokens or budget, args.context_tokens)
            metrics = dict(et_fields["metrics"])
            cold = True
        elif ort:
            metrics, ort_report, ort_loaded, ort_text = parsers.parse_ortgenai(console)
            cold = True
        else:
            metrics = parsers.parse_litert(console)
            cold = True
        # side build: the engine's own device lines (parsers.llama_backend_lines /
        # litert_npu_lines) say which device this launch registered and used; one that does
        # not show the cell's device measured another one — kept, flagged, out of every pool
        # and not an OK run
        side_cond, backend_flags = {}, []
        if litert_npu:
            lines = parsers.litert_npu_lines(console)
            # the engine's own echo of the setting (its executor_settings dump), absent = null
            echo = next((ln.split(": ", 1)[1] for ln in lines
                         if ln.startswith("use_hw_cache_update_for_npu: ")), None)
            side_cond = {"engineBuild": args.engine_build,
                         "hwCacheUpdateForNpu": {"true": True, "false": False}.get(echo),
                         "engineCommand": f"{env} {cmd}", "backendRegistered": lines}
            if not parsers.litert_npu_registered(lines):
                backend_flags = ["backend-not-registered"]
        elif engine_dir:
            device = LLAMA_DEVICES[args.backend]
            bench = binname == "llama-bench"
            lines = (parsers.llama_bench_device_lines(tests) if bench
                     else parsers.llama_backend_lines(console))
            side_cond = {"engineBuild": args.engine_build, "ggmlDevice": device, "nGpuLayers": 99,
                         "threads": SIDE_THREADS,
                         "flashAttn": "auto (llama-bench default)" if bench else "on",
                         "ubatch": SIDE_UBATCH if not bench or args.backend == "npu"
                         else "512 (llama-bench default)",
                         "hexagonOpPoll": 1, "engineCommand": f"{env} {cmd}",
                         "backendRegistered": lines}
            if not parsers.llama_backend_registered(lines, device, LLAMA_DEVICE_BUFFERS[device],
                                                    binname, tests):
                backend_flags = ["backend-not-registered"]

        if extended and not paired:
            invalid = console.lower().count("invalid decode")
            launch_checks = {"invalidDecodeCount": invalid,
                             "protocolFlags": ["invalid-decode"] if invalid else []}
        if extended and exit_code != 0:
            launch_checks["protocolFlags"].append(f"engine-exit-{exit_code}")
        if extended and "HOST_ADB_FAILURE:" in console:
            launch_checks["protocolFlags"].append("host-adb-failure")
        if et and et_fields["flags"]:
            launch_checks.setdefault("protocolFlags", []).extend(et_fields["flags"])
        try:
            end_status, end_name = thermal_status(args.serial)
            end_batt = battery(args.serial) if extended else None
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            if not STRICT_SMOKE:
                raise
            end_status, end_name, end_batt = None, "unavailable", {}
            launch_checks.setdefault("protocolFlags", []).append("end-state-unavailable")
        metrics.update({
            "coldRun": cold,
            "harnessStamp": HARNESS_STAMP,
            "initialThermalState": thermal_name,
            "finalThermalState": end_name,
        })
        if rss_mb is not None:
            metrics["memoryMedianResidentMB"] = rss_mb
        high_water = [int(line.split()[1]) for line in console.splitlines() if line.startswith("VmHWM:")]
        if high_water:
            metrics["memoryPeakResidentMB"] = max(high_water) / 1024
        if et:
            metrics["harnessStamp"] = HARNESS_STAMP + EXECUTORCH_STAMP
            engine_peak = metrics.get("memoryPeakEngineReportedMB")
            if engine_peak and engine_peak > metrics.get("memoryPeakResidentMB", 0):
                metrics["memoryPeakResidentMB"] = engine_peak
        # every run until the first clean exit is (or may be finishing) the
        # cache build; the first run that exits 0 writes the marker
        if (args.first_ever and i == 1) or not cache_built:
            metrics["firstEver"] = True
        if (exit_code == 0 and not cache_built and not launch_checks.get("protocolFlags")
                and not backend_flags):
            adb(["shell", f"mkdir -p {DEV_DIR}/markers && touch {marker}"], args.serial)
            cache_built = True

        now = datetime.datetime.now(datetime.timezone.utc)
        iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        # filename stamp carries microseconds: two 1-run invocations of the
        # same cell inside one second silently OVERWROTE each other's record
        # and log (stored-report-rule) — caught by selftest.py on a fast CI
        # runner, where two payload rounds landed in the same second
        stamp = now.strftime("%Y-%m-%dT%H-%M-%S.%f")
        stem = capture_stem(args.runtime, args.backend, args.model_id, args.task,
                            args.file, args.context_tokens, args.round_index is not None)
        console_name = f"{stem}_{stamp}_run{i}.log"
        with open(os.path.join(args.out, console_name), "w") as fh:
            fh.write(console)

        rec = {
            "schemaVersion": 1,
            "id": str(uuid.uuid4()),
            "runtime": arm,
            "engineVersion": engine_version,
            "engineArtifact": engine_artifact,
            "model": ort_model or {"id": args.model_id, "quantization": quantization or guess_quant(model_dev),
                                   "file": os.path.basename(model_dev), "sha256": model_sha},
            "task": args.task,
            "timestamp": iso,
            "device": {**dev, "batteryLevel": batt["batteryLevel"],
                       "batteryState": batt["batteryState"]},
            "conditions": {"sampler": sampler,
                           "cpuAffinity": f"taskset {CPU_MASK}" if CPU_MASK else "none",
                           **cpu_cond,
                           "contextTokens": ctx_note,
                           **({"chatMode": "single-turn template default (-st)"}
                              if args.runtime == "llama.cpp"
                              and not args.task.startswith("native-") else {}),
                           "thermalRawStatus": raw_status,
                           "thermalRawStatusFinal": end_status,
                           **screen, "elapsedSeconds": round(elapsed, 1),
                           "exitCode": exit_code, **side_cond},
            "metrics": metrics,
            "provenance": {"rawLog": console_name, "harness": "android/bench/run_cell.py",
                           "rssBasis": RSS_BASIS + (LITERT_NPU_RSS_NOTE if litert_npu
                                                    else SIDE_RSS_NOTE if engine_dir else "")},
        }
        if et:
            rec["model"].update(et_fields["model"])
            rec["conditions"].update(et_fields["conditions"], warm=False)
            rec["provenance"].update(et_fields["provenance"])
            rec["provenance"]["rssBasis"] += EXECUTORCH_RSS_NOTE[et["runner"]]
            rec["outputSample"] = (et_fields["text"] or "")[:200]
            if launch_checks.get("protocolFlags"):
                rec["conditions"]["protocolFlags"] = list(launch_checks["protocolFlags"])
        if ort:
            sockets = engine_sockets(console)
            if sockets is not None:
                rec["conditions"]["engineSockets"] = sockets
            rec["conditions"].update({
                "chatMode": ORTGENAI_CHAT_MODE, "telemetry": ORTGENAI_TELEMETRY,
                "metricDefinitions": ORTGENAI_METRICS, "threads": "engine default",
                # every key=value of ortgenai_run's ORTGENAI line, unknown ones included
                "engineReport": ort_report,
                # the libraries the engine process mapped (ORTGENAI_LIBS); their shas are the
                # witness's (observed_engine checks them against the pins entry)
                "engineLibraries": ort_loaded,
            })
            ort_text_name = f"{stem}_{stamp}_run{i}.decoded.txt"
            with open(os.path.join(args.out, ort_text_name), "w") as fh:
                fh.write(ort_text or "")
            rec["provenance"]["decodedText"] = ort_text_name
            rec["provenance"]["recipe"] = "models/ortgenai-recipes.json (scripts/ortgenai_recipe.py)"
        if extended:
            rec["conditions"].update({
                "roundIndex": args.round_index, "launchIndex": args.launch_index,
                "launchID": launch_id, "elapsedScope": "whole-launch",
                "stateAndMemoryScope": "whole-launch",
                "batteryTemperatureInitialC": batt.get("temperatureC"),
                "batteryTemperatureFinalC": end_batt.get("temperatureC"),
                "batteryLevelFinal": end_batt.get("batteryLevel"),
                "thermalGateTimedOut": args.gate_timed_out,
                "thermalGateTimeoutNonNominal": args.gate_timed_out and thermal_name != "nominal",
                "initialThermalNonNominal": thermal_name != "nominal",
                "outputTokenBudget": args.max_tokens or budget,
                "engineCommand": f"{env} {cmd}" if engine_dir else cmd, **launch_checks,
            })
        # Legacy paths retain their one-record shape. Context prompt iterations
        # share a launch/log/state sample, but never share token counters.
        samples = iteration_metrics if paired else [metrics]
        # text-check-rule: a context-prompt launch's decoded text is checked by
        # default (BENCH_TEXT_CHECK=0 turns it off; before 2026-10-06 it ran only
        # under BENCH_TEXT_CHECK=1, so the weekly job's 1024 cells went unchecked).
        # A FAIL keeps its records, text and log (failed-runs-stay), flags them,
        # and the summary's text_check column keeps them out of every number.
        # A side build's chat launch is checked the same way (its reply: parsers.llama_cli_reply,
        # the -lv 4 log lines taken out; the LiteRT-LM NPU build's: parsers.litert_reply, its
        # log lines taken out); the pinned CPU llama.cpp arm and the LiteRT-LM cpu / gpu
        # short-chat launches are not text-checked.
        checking = os.environ.get("BENCH_TEXT_CHECK", "1") == "1"
        if paired and checking:
            printed_texts = parsers.context_prompt_texts(console)
        elif litert_npu and checking:
            printed_texts = [parsers.litert_reply(console)]
        elif engine_dir and binname != "llama-bench" and checking:
            printed_texts = [parsers.llama_cli_reply(console, prompt_text)]
        elif et and checking:
            printed_texts = [et_fields["text"] or ""]
        else:
            printed_texts = None
        any_text_failure = False
        for iteration, sample in enumerate(samples, 1):
            row = {**rec, "id": str(uuid.uuid4()) if paired else rec["id"],
                   "metrics": {**metrics, **sample}, "conditions": dict(rec["conditions"]),
                   "provenance": dict(rec["provenance"])}
            if paired:
                # Do not let iteration 1's token counters fill a missing run 2.
                row["metrics"] = {k: v for k, v in metrics.items() if k in (
                    "harnessStamp", "initialThermalState", "finalThermalState",
                    "memoryMedianResidentMB", "memoryPeakResidentMB", "firstEver")}
                row["metrics"].update(sample)
                row["metrics"]["coldRun"] = iteration == 1
                if iteration > 1:
                    row["metrics"].pop("firstEver", None)
            if extended:
                row["conditions"]["iterationIndex"] = iteration
                row["conditions"]["regime"] = ("cold" if iteration == 1 else "warm") if paired else "cold-process"
            if printed_texts is not None:
                value = printed_texts[iteration - 1] if iteration <= len(printed_texts) else ""
                verdict = parsers.text_integrity(value)
                row["conditions"]["protocolFlags"] = list(row["conditions"].get("protocolFlags", [])) + verdict["flags"]
                expected_prompt = os.environ.get("BENCH_EXPECT_PROMPT_TOKENS")
                if expected_prompt and sample.get("promptTokenCount") != int(expected_prompt):
                    row["conditions"]["protocolFlags"].append("prompt-token-count-mismatch")
                row["conditions"]["textCheck"] = verdict
                row["conditions"]["textOutputSHA256"] = hashlib.sha256(value.encode()).hexdigest()
                text_name = f"{stem}_{stamp}_run{i}_iter{iteration}.decoded.txt"
                with open(os.path.join(args.out, text_name), "w") as fh:
                    fh.write(value)
                row["provenance"]["decodedText"] = text_name
                any_text_failure |= bool(row["conditions"]["protocolFlags"])
            if ort and args.task.startswith("long-context-"):
                # text-check-rule: the screen the LiteRT-LM context-prompt launches carry,
                # unchanged (the same bar for every arm); short-chat carries none, as on
                # every other Android arm
                verdict = parsers.text_integrity(ort_text or "")
                row["conditions"]["protocolFlags"] = list(row["conditions"].get("protocolFlags", [])) + verdict["flags"]
                row["conditions"]["textCheck"] = verdict
                row["conditions"]["textOutputSHA256"] = hashlib.sha256((ort_text or "").encode()).hexdigest()
                any_text_failure |= bool(verdict["flags"])
            if cpu_flags or backend_flags:
                # cpu-cap-rule / a side build off its device: the record stays, arm_row
                # keeps it out of every pool
                row["conditions"]["protocolFlags"] = (list(row["conditions"].get("protocolFlags", []))
                                                      + cpu_flags + backend_flags)
            name = f"{stem}_{stamp}_run{i}{'_iter' + str(iteration) if paired else ''}.json"
            with open(os.path.join(args.out, name), "w") as fh:
                json.dump(row, fh, indent=2)
        d = metrics.get("decodeTokensPerSecond")
        clean = (exit_code == 0 and d and not launch_checks.get("protocolFlags") and not any_text_failure
                 and not backend_flags)
        status = "OK" if clean else f"FAIL(exit={exit_code})"
        print(f"run {i}/{args.runs} {status} decode={d} thermal={thermal_name}->{end_name}")
        if launch_checks.get("protocolFlags"):
            print("protocol flags: " + ", ".join(launch_checks["protocolFlags"]))
        if backend_flags:
            shown = "the NPU dispatch" if litert_npu else LLAMA_DEVICES[args.backend]
            print(f"backend-not-registered {stem}_{stamp}_run{i}: the engine's lines do not show "
                  f"{shown} — the record stays, no number pools it")
        if cpu_capped:
            line = f"cpu-capped {stem}_{stamp}_run{i}: " + "; ".join(cpu_capped)
            print(line + " — the record stays, no number pools it (cpu-cap-rule)")
            with open(os.path.join(args.out, "THERMAL_GATE.txt"), "a") as fh:
                fh.write(line + "\n")
        if clean:
            ok += 1
    return 0 if ok == args.runs else 1


# Exact labels for known artifacts — same strings as the iOS ModelCatalog, so
# the same artifact never carries two labels across platforms (quant-label-rule:
# a bare "int4" is not a spec). Adding a model to android cells => add its
# label here (docs/OPERATIONS.md, add-a-model).
ANDROID_QUANT_LABELS = {
    "qwen3_0_6b_mixed_int4.litertlm": "INT4 (mixed, blockwise gs32)",
    # the same TorchAO mixed-INT4 recipe as the 0.6B file (the Mac catalog labels
    # litert-community/Qwen3-4B's primaryFile identically); until 2026-10-06 this
    # file was missing here, so every Android Qwen3-4B LiteRT record carried
    # "unrecorded" (bench_common.corrected_quant restores the label for those rows)
    "qwen3_4b_mixed_int4.litertlm": "INT4 (mixed, blockwise gs32)",
    # litert-community/Qwen3-{0.6B,1.7B} recipe files — the Mac catalog strings
    # (ModelCatalog liteRTLM) for the wi4b32 builds; the 1.7B INT8 file's label
    # is the repo manifest's recipe name (dynamic_wi8_afp32)
    "Qwen3-0.6B_dynamic_wi4b32_afp32.litertlm": "INT4 (dynamic, block-32 weights, FP32 act; GPU-graph build 2026-08-04)",
    "Qwen3-1.7B_dynamic_wi4b32_afp32.litertlm": "INT4 (dynamic, block-32 weights, FP32 act; GPU-graph build)",
    "Qwen3_1.7B.litertlm": "INT8 (dynamic_wi8_afp32: int8 weights, FP32 act; CPU-recipe file)",
    # 2026-09-14 dtype-only pair: one litert-torch main (6d4c622) GPU-graph export of
    # Qwen3-1.7B per recipe (fused qkv/gate_up, odml.rope + cache composites, bool mask,
    # prefill 1024, cache 4096); the two files differ in the quantization recipe only
    "Qwen3-1.7B_wi8_gpuflags.litertlm": "INT8 (dynamic_wi8_afp32: int8 weights, FP32 act; GPU-graph export 2026-09-14, dtype-only twin of the wi4b32 file)",
    "Qwen3-1.7B_wi4b32_gpuflags.litertlm": "INT4 (dynamic_wi4b32_afp32: block-32 weights, FP32 act; GPU-graph export 2026-09-14, dtype-only twin of the INT8 file)",
    # second pair of the same day: the same export with use_rope_composite off in both files (the
    # odml.rope composite broke the int8 file on the v0.16.0 Android GPU path; rope inlined)
    "Qwen3-1.7B_wi8_gpuflags_norope.litertlm": "INT8 (dynamic_wi8_afp32: int8 weights, FP32 act; GPU-graph export 2026-09-14, rope inlined, dtype-only twin of the wi4b32 file)",
    "Qwen3-1.7B_wi4b32_gpuflags_norope.litertlm": "INT4 (dynamic_wi4b32_afp32: block-32 weights, FP32 act; GPU-graph export 2026-09-14, rope inlined, dtype-only twin of the INT8 file)",
    "gemma-4-E2B-it.litertlm": "wNa8o8 (int2/int4/int8 + int8 activations, QAT)",
    "gemma-4-E4B-it.litertlm": "wNa8o8 (int2/int4/int8 + int8 activations, QAT)",
    # same artifact + label as the Mac endurance baseline row (thinking bundle,
    # disclosed there; ModelCatalog "Granite 4.2 3B (.litertlm, thinking)")
    "granite-4.2-3b_int4.litertlm": "int4 BOCTAV4 (block32, int8 embedder)",
    "DeepSeek-R1-Distill-Qwen-1.5B_multi-prefill-seq_q8_ekv4096.litertlm": "INT8",
    # litert-community filename recipe descriptors, kept verbatim (a bare
    # "int4" is not a spec; the descriptor is exactly what the repo states)
    "minicpm_wi4b32_wi8_afp32.litertlm": "wi4b32_wi8_afp32",
    "minicpm_wi4b32_wi8_afp32_gpu_opt.litertlm": "wi4b32_wi8_afp32 (gpu-opt)",
    "LFM2.5-1.2B-Instruct_int4.litertlm": "int4 (litert-community descriptor)",
    "LFM2.5-1.2B-Instruct_int4_gpu.litertlm": "int4_gpu (litert-community descriptor)",
    # litert-community/MiniCPM5-2B — labels are the repo manifest's recipe text,
    # the same strings as the Mac catalog entries (ModelCatalog liteRTLM).
    "MiniCPM5-2B_int8.litertlm": "INT8 (dynamic, linears + embedding; fp32 GPU activations declared)",
    "MiniCPM5-2B_int4.litertlm": "INT4 (blockwise-32 + OCTAV linears, int8 embedding; GPU activations fp16 default)",
}


def guess_quant(dev_path):
    """Exact label for known artifacts; otherwise only what the filename
    states (GGUF quant suffixes ARE specs), else 'unrecorded'."""
    base = os.path.basename(dev_path)
    for known, label in ANDROID_QUANT_LABELS.items():
        if base.endswith(known):
            return label
    low = base.lower()
    for pat in ("q4_k_m", "q8_0", "f16", "fp16"):
        if pat in low:
            return pat.upper() if pat.startswith("q") else pat
    return "unrecorded (artifact name carries no quant label)"


if __name__ == "__main__":
    sys.exit(main())
