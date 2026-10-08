#!/usr/bin/env python3
"""Validate matrix cell files (matrices/*.cells). Grammar: matrices/README.md.

  python3 scripts/validate_cells.py matrices/*.cells
  python3 scripts/validate_cells.py --require-anchor matrices/release-regression-litert.cells
  python3 scripts/validate_cells.py --catalog catalog.json matrices/apple-warm-matrix.cells

--catalog: output of `yardstick list --json`; model ids are checked against it
(cells with local=1 or platform=android are exempt — android ids are HF repos
resolved by the android driver, not ModelCatalog entries).
exclude-on=<device key>[,<key>…]:<reason> keys are checked against the devices
of ops/dashboard-v1/schedule.json (--schedule), read only when a row has one.
Exit 1 on any error; warnings don't fail.
"""
import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_SCHEDULE = os.path.join(ROOT, "ops", "dashboard-v1", "schedule.json")
PLATFORMS = {"ios", "mac", "android"}
RUNTIMES = {"mlx-swift", "llama.cpp", "coreml-llm", "litert-lm", "executorch",
            "anemll", "apple-fm", "core-ai", "cactus",
            # the LiteRT runtime itself (ai-edge-litert CompiledModel) driven by a
            # model's public host-side pipeline — the tts-rtf-* instrument in v1
            "litert",
            # Mirai's uzu engine through its Python SDK (Mac only; docs/uzu-arm-v1.md)
            "uzu",
            # ONNX Runtime GenAI on a published GenAI folder (docs/ortgenai-arm-v1.md):
            # scripts/ortgenai_mac.py on the Mac, android/bench/run_cell.py on Android
            "onnxruntime-genai"}
TASKS = {"short-chat", "long-context-512", "long-context-1024",
         "long-context-1024-gen256", "long-context-2048-gen256", "long-context",
         "long-context-3k",
         "long-context-8k", "long-context-32k", "cactus-parity", "sustained",
         "energy", "quality", "lifecycle",
         # ASR real-time factor over a pinned utterance set (docs/asr-rtf-v1.md;
         # scripts/asr_rtf_mac.py TASK_SETS names the set behind each id).
         "asr-rtf-librispeech-82s",
         # Vision-language response time over a pinned image + prompt (docs/vl-response-v1.md;
         # scripts/vl_response_mac.py TASK_SETS) and TTS real-time factor over a pinned text
         # (docs/tts-rtf-v1.md; scripts/tts_rtf_mac.py TASK_SETS).
         "vl-describe-catcouch-gen64", "tts-rtf-libri1272-2sent"}
ASR_TASK = re.compile(r"^asr-rtf-")
VL_TASK = re.compile(r"^vl-")
TTS_TASK = re.compile(r"^tts-rtf-")
# graph sets a tts-rtf-* android row can name with recipe= (docs/tts-rtf-v1.md)
TTS_RECIPES = {"mtp-folded-int8-codec-split"}
NATIVE_TASK = re.compile(r"^native-benchmark-\d+x\d+$")
# endurance-chat-<N>m — multi-turn endurance sessions (methodology/endurance.md);
# duration is part of the task id, like the long-context sweep variants.
ENDURANCE_TASK = re.compile(r"^endurance-chat-\d+m$")
INT_KEYS = {"runs", "context-tokens", "max-tokens", "cooldown"}
FLAG_KEYS = {"anchor", "manual", "local"}          # value must be 1
STR_KEYS = {"exclude", "exclude-on", "file", "backend", "recipe", "thinking", "engine-counters",
            "engine-build", "revision"}
BACKENDS = {"cpu", "gpu", "npu"}
# the backends of the Mac / iPhone LiteRT-LM rows and of the asr / vl instruments
CPU_GPU = {"cpu", "gpu"}
# an Android llama.cpp row: no backend= = the CPU arm `llama.cpp` (the pinned official CPU
# build); backend=npu|gpu = a side build's Hexagon / Adreno OpenCL device, named by
# engine-build=<engine-pins.json key> (docs/dashboard-cells-v1.md "NPU and Android GPU rows")
ANDROID_LLAMA_BACKENDS = {"npu", "gpu"}
# an executorch row's backend= (arm executorch-<backend>, docs/executorch-arm-v1.md): the
# ExecuTorch delegate the runner build carries, per platform runner (android/bench/run_cell.py,
# scripts/executorch_mac.py)
EXECUTORCH_BACKENDS = {"android": {"xnnpack", "vulkan", "qnn"}, "mac": {"xnnpack", "mlx", "metal", "coreml"}}
EXECUTORCH_TASKS = {"short-chat", "long-context-1024-gen256"}
# an iPhone executorch row: the app built from ios/BenchmarkApp/project-executorch.yml, the
# ExecuTorch SwiftPM runtime with the XNNPACK delegate only (docs/executorch-arm-v1.md "iPhone")
EXECUTORCH_BACKENDS["ios"] = {"xnnpack"}
# runtimes whose backend= values are not BACKENDS: the ORT GenAI arm names its execution
# provider (cpu = the CPU EP; webgpu = the WebGPU plugin EP, Mac only); the Core AI stock arm
# names the Neural Engine its engine is pinned to (arm core-ai-ane, docs/coreai-arm-v1.md)
BACKENDS_OF = {"onnxruntime-genai": {"cpu", "webgpu"}, "core-ai": {"ane"}}
# the Core AI stock arm's catalog ids: Apple's own exports on the stock path (bundle folders
# stock_*, CoreAIRuntime.bundleSpec), the export's KV allocation in the id
COREAI_STOCK_ID = re.compile(r"^core-ai/.+-stock-ctx(\d+|default)(?:-[a-z0-9]+)?$")
# onnxruntime-genai: the backends each platform has a published route for (the Android AAR
# and the iOS XCFramework are CPU-only), and the tasks of v1
ORTGENAI_BACKENDS = {"mac": {"cpu", "webgpu"}, "android": {"cpu"}, "ios": {"cpu"}}
ORTGENAI_TASKS = {"short-chat", "long-context-1024-gen256"}
HF_REVISION = re.compile(r"^[0-9a-f]{40}$")
# schedule.json device platform -> cells-file platform token
SCHEDULE_PLATFORM = {"iphone": "ios"}


def parse_exclude_on(value):
    """exclude-on=<device key>[,<key>…]:<reason> -> {key: reason}: the row stays in
    the file and runs on every other device; on the devices named by their
    ops/dashboard-v1/schedule.json key the Android runner skips it and the
    dashboards show the reason (docs/dashboard-cells-v1.md). Raises ValueError."""
    keys, sep, reason = value.partition(":")
    names = keys.split(",")
    if not sep or not reason or not all(names):
        raise ValueError(f"exclude-on={value!r} (want <device key>[,<key>…]:<reason>)")
    if len(set(names)) != len(names):
        raise ValueError(f"exclude-on={value!r} names a device twice")
    return {k: reason for k in names}


def load_schedule_devices(path=DEFAULT_SCHEDULE):
    """schedule.json devices ({key: entry}); {} when the file is absent."""
    if not os.path.exists(path):
        return {}
    with open(path) as fh:
        return json.load(fh).get("devices", {})


def parse_line(line):
    """-> (platform, runtime, model_id, task, opts_dict) or raises ValueError."""
    parts = line.split()
    if len(parts) < 4:
        raise ValueError(f"need at least 4 columns, got {len(parts)}")
    plat, rt, mid, task = parts[:4]
    opts = {}
    for kv in parts[4:]:
        if "=" not in kv:
            raise ValueError(f"option {kv!r} is not key=value")
        k, v = kv.split("=", 1)
        if k in opts:
            raise ValueError(f"duplicate option {k!r}")
        if k == "backend" and rt == "executorch":
            # executorch names its delegate (validate_file checks it per platform)
            if not v:
                raise ValueError("backend= needs a value")
            opts[k] = v
            continue
        if k in INT_KEYS:
            if not v.isdigit():
                raise ValueError(f"{k}={v!r} is not an integer")
        elif k in FLAG_KEYS:
            if v != "1":
                raise ValueError(f"{k}={v!r} (flags take only =1)")
        elif k in STR_KEYS:
            if not v:
                raise ValueError(f"{k}= needs a value")
            if k == "backend" and v not in BACKENDS_OF.get(rt, BACKENDS):
                raise ValueError(f"backend={v!r} (want {'|'.join(sorted(BACKENDS_OF.get(rt, BACKENDS)))})")
            if k == "exclude-on":
                parse_exclude_on(v)
        else:
            raise ValueError(f"unknown option key {k!r}")
        opts[k] = v
    return plat, rt, mid, task, opts


def validate_file(path, catalog=None, require_anchor=False, schedule_path=DEFAULT_SCHEDULE):
    errors, warnings = [], []
    devices = None  # schedule.json devices, read at the first exclude-on= row
    seen = {}
    anchors_by_platform = set()
    platforms_in_file = set()
    with open(path) as fh:
        for lineno, raw in enumerate(fh, 1):
            line = raw.split("#", 1)[0].strip()
            if not line:
                continue
            where = f"{path}:{lineno}"
            try:
                plat, rt, mid, task, opts = parse_line(line)
            except ValueError as e:
                errors.append(f"{where}: {e}")
                continue
            if plat not in PLATFORMS:
                errors.append(f"{where}: unknown platform {plat!r}")
            if rt not in RUNTIMES:
                errors.append(f"{where}: unknown runtime {rt!r}")
            if rt == "uzu":
                if plat != "mac":
                    errors.append(f"{where}: uzu v1 is Mac-only")
                if task not in {"short-chat", "long-context-2048-gen256"}:
                    errors.append(f"{where}: unsupported uzu task {task!r}")
                if int(opts.get("runs", "1")) < 1 or ("context-tokens" in opts and int(opts["context-tokens"]) < 1):
                    errors.append(f"{where}: uzu runs/context-tokens must be positive")
                if task == "long-context-2048-gen256" and not int(opts.get("context-tokens", "0")):
                    errors.append(f"{where}: uzu long-context needs a positive context-tokens allocation")
                if not opts.get("recipe") or opts["recipe"].lower() in {"int4", "4bit", "4-bit"}:
                    errors.append(f"{where}: uzu needs recipe=<converter-or-publisher-recipe>, not a bare bit width")
                if mid.startswith("own-export/") and not opts.get("file"):
                    errors.append(f"{where}: uzu own export needs file=<export-directory>")
                if opts.get("thinking", "model-default") not in {"off", "model-default"}:
                    errors.append(f"{where}: uzu thinking= must be off|model-default")
            elif rt == "executorch":
                if plat not in EXECUTORCH_BACKENDS:
                    errors.append(f"{where}: executorch v1 rows are android / mac (android/bench/run_cell.py, "
                                  "scripts/executorch_mac.py)")
                elif opts.get("backend") not in EXECUTORCH_BACKENDS[plat]:
                    errors.append(f"{where}: executorch needs backend=<"
                                  f"{'|'.join(sorted(EXECUTORCH_BACKENDS[plat]))}> on {plat} (arm identity)")
                if task not in EXECUTORCH_TASKS:
                    errors.append(f"{where}: unsupported executorch task {task!r}")
                if opts.get("local") != "1" or not opts.get("file", "").endswith(".pte"):
                    errors.append(f"{where}: executorch runs an own export: local=1 file=<name>.pte "
                                  "(under ET_MODEL_DIR)")
                if not opts.get("recipe") or opts["recipe"].lower() in {"int4", "4bit", "4-bit", "8da4w"}:
                    errors.append(f"{where}: executorch needs recipe=<alias> (parsers.EXECUTORCH_RECIPES), "
                                  "not a bare bit width")
                # the KV allocation is fixed at export: the model id states it, a context-tokens=
                # names the same number, and the 1K task's rows name it as the other arms' do
                exported = re.search(r"-ctx(\d+)$", mid)
                if not exported:
                    errors.append(f"{where}: executorch model id must end in -ctx<N> (the export's allocation)")
                elif "context-tokens" in opts and opts["context-tokens"] != exported.group(1):
                    errors.append(f"{where}: context-tokens={opts['context-tokens']} but the export "
                                  f"allocates {exported.group(1)} (model id)")
                if task == "long-context-1024-gen256" and "context-tokens" not in opts:
                    errors.append(f"{where}: executorch long-context-1024-gen256 needs context-tokens=<the "
                                  "export's allocation>")
                if "max-tokens" in opts:
                    errors.append(f"{where}: executorch takes the task budget (prompts/text/budgets.tsv), "
                                  "not max-tokens=")
                if plat == "mac" and not opts.get("exclude") and int(opts.get("runs", "4")) < 2:
                    errors.append(f"{where}: a mac executorch row needs runs>=2 (run 1 cold, the rest "
                                  "warm: the Mac headline is warm)")
            elif "recipe" in opts and not (TTS_TASK.match(task) and plat == "android"):
                errors.append(f"{where}: recipe= currently belongs to uzu cells and android "
                              "tts-rtf-* rows only")
            # an iPhone executorch row: the app records the cell's context-tokens= as the run's
            # KV allocation (BenchmarkRunner contextTokensConfigured; without it, its own
            # estimate), so every row names the export's; run 1 is cold, runs 2..N warm in the
            # same app process
            if plat == "ios" and rt == "executorch":
                if "context-tokens" not in opts:
                    errors.append(f"{where}: an ios executorch row needs context-tokens=<the export's "
                                  "allocation> on every task (the app records the cell's value)")
                if not opts.get("exclude") and int(opts.get("runs", "4")) < 2:
                    errors.append(f"{where}: an ios executorch row needs runs>=2 (run 1 cold, the rest warm)")
            if rt != "uzu" and "thinking" in opts:
                errors.append(f"{where}: thinking= currently belongs to uzu cells only")
            if rt == "onnxruntime-genai":
                # Every budget is explicit (docs/ortgenai-arm-v1.md): the backend is arm
                # identity, file= is the GenAI folder in the repo, revision= its HF commit
                # (one per repo: the three onnx-community Qwen3 repos have three), and
                # context-tokens= the max_length the KV cache is allocated for. An excluded
                # row (no published folder) keeps backend= and context-tokens= only.
                if plat not in ORTGENAI_BACKENDS:
                    errors.append(f"{where}: onnxruntime-genai runs on mac / android / ios")
                elif opts.get("backend") not in ORTGENAI_BACKENDS[plat]:
                    errors.append(f"{where}: onnxruntime-genai on {plat} needs backend="
                                  f"{'|'.join(sorted(ORTGENAI_BACKENDS[plat]))} (arm identity)")
                if task not in ORTGENAI_TASKS:
                    errors.append(f"{where}: onnxruntime-genai v1 tasks are {', '.join(sorted(ORTGENAI_TASKS))}")
                if not int(opts.get("context-tokens", "0")):
                    errors.append(f"{where}: onnxruntime-genai needs context-tokens=<max_length> "
                                  "(the KV allocation; past_present_share_buffer allocates it up front)")
                if not opts.get("exclude"):
                    local = opts.get("file", "").startswith(("/", "~"))
                    if not opts.get("file"):
                        errors.append(f"{where}: onnxruntime-genai needs file=<GenAI folder in the repo> "
                                      "(quant-per-arm-rule: the recipe travels with the row)")
                    if not local and not HF_REVISION.match(opts.get("revision", "")):
                        errors.append(f"{where}: onnxruntime-genai needs revision=<the 40-hex HF commit of the repo>")
            elif "revision" in opts:
                errors.append(f"{where}: revision= currently belongs to onnxruntime-genai cells only")
            if rt == "core-ai":
                # The stock arm (docs/coreai-arm-v1.md): Apple's own exports on the stock path stamp
                # core-ai-ane (CoreAIRuntime.recordRuntimeLabel), so backend=ane names the arm and
                # goes with a stock id both ways (a stock row without it would never meet its
                # records); the export fixes the KV allocation (the id's ctx); the app's
                # --coreai-native-benchmark measures the stock path only. Rows without backend= are
                # the own-export arm (v2), unchanged.
                stock = COREAI_STOCK_ID.match(mid)
                if opts.get("backend") and plat not in ("mac", "ios"):
                    errors.append(f"{where}: core-ai backend=ane is a mac / ios row (the Core AI stock arm)")
                if bool(stock) != (opts.get("backend") == "ane"):
                    errors.append(f"{where}: core-ai backend=ane and a stock id (core-ai/<model>-stock-ctx<N>) "
                                  "go together (the stock path stamps core-ai-ane; an own export stamps core-ai)")
                if (stock and stock.group(1).isdigit() and "context-tokens" in opts
                        and opts["context-tokens"] != stock.group(1)):
                    errors.append(f"{where}: context-tokens={opts['context-tokens']} but the export "
                                  f"allocates {stock.group(1)} (model id)")
                if NATIVE_TASK.match(task) and plat == "ios" and not stock:
                    errors.append(f"{where}: an ios core-ai native-benchmark row needs a stock id (the app's "
                                  "--coreai-native-benchmark measures Apple's export on the stock path only)")
            if (task not in TASKS and not NATIVE_TASK.match(task)
                    and not ENDURANCE_TASK.match(task)):
                errors.append(f"{where}: unknown task {task!r}")
            if ENDURANCE_TASK.match(task) and rt != "litert-lm":
                errors.append(f"{where}: endurance-chat is litert-lm-only "
                              "(needs a persistent conversation + per-turn "
                              "engine counters; methodology/endurance.md)")
            if ENDURANCE_TASK.match(task) and opts.get("runs", "1") != "1":
                errors.append(f"{where}: endurance cells take runs=1 — one "
                              "session per cell; sessions are never pooled")
            if ASR_TASK.match(task):
                # v1 instrument = LiteRT-LM's own ASR CLI on the Mac; the litert
                # backend is arm identity (litert-lm-cpu / -gpu never pool) and
                # file= names the artifact (the recipe is stated per row).
                if rt != "litert-lm" or plat not in ("mac", "android", "ios"):
                    errors.append(f"{where}: asr-rtf-* is a mac / android / ios litert-lm cell in v1 "
                                  "(scripts/asr_rtf_mac.py, scripts/asr_rtf_android.py, "
                                  "scripts/asr_rtf_iphone.py; docs/asr-rtf-v1.md)")
                if opts.get("backend") not in CPU_GPU:
                    errors.append(f"{where}: asr-rtf-* needs backend=cpu|gpu (arm identity)")
                if not opts.get("file"):
                    errors.append(f"{where}: asr-rtf-* needs file=<artifact> "
                                  "(quant-per-arm-rule: the recipe travels with the row)")
            if VL_TASK.match(task):
                # v1 instrument = LiteRT-LM's own CLI on the Mac and, built for
                # android_arm64, on a phone; backend is arm identity, file= names
                # the .litertlm (recipe per row).
                if rt != "litert-lm" or plat not in ("mac", "android"):
                    errors.append(f"{where}: vl-* is a mac / android litert-lm cell in v1 "
                                  "(scripts/vl_response_mac.py, scripts/vl_response_android.py; "
                                  "docs/vl-response-v1.md)")
                if opts.get("backend") not in CPU_GPU:
                    errors.append(f"{where}: vl-* needs backend=cpu|gpu (arm identity)")
                if not opts.get("file"):
                    errors.append(f"{where}: vl-* needs file=<artifact.litertlm>")
            if TTS_TASK.match(task):
                # v1 instrument = the model's public LiteRT reference pipeline on the
                # CPU (runtime `litert`): the Python sample on the Mac, the sample's
                # own Android app on a phone; file= names the talker recipe.
                if rt != "litert" or plat not in ("mac", "android"):
                    errors.append(f"{where}: tts-rtf-* is a mac / android `litert` cell in v1 "
                                  "(scripts/tts_rtf_mac.py, scripts/tts_rtf_android.py; docs/tts-rtf-v1.md)")
                if not opts.get("file"):
                    errors.append(f"{where}: tts-rtf-* needs file=<talker artifact> "
                                  "(quant-per-arm-rule: the recipe travels with the row)")
                # the graph set beside the talker: absent = the sample's default set;
                # the fast graphs are the one other set the Android app can select
                # (scripts/tts_rtf_android.py RECIPES; docs/tts-rtf-v1.md)
                if "recipe" in opts and opts["recipe"] not in TTS_RECIPES:
                    errors.append(f"{where}: tts-rtf-* recipe= must be one of {sorted(TTS_RECIPES)} "
                                  "(omit it for the sample's default graph set)")
            if task == "energy" and opts.get("manual") != "1":
                errors.append(f"{where}: energy task requires manual=1 "
                              "(unplug discipline is a human step)")
            if opts.get("backend") and not (
                    plat == "android" or (plat == "mac" and rt in ("litert-lm", "onnxruntime-genai", "core-ai"))
                    or (plat == "ios" and rt in ("litert-lm", "onnxruntime-genai", "core-ai")) or rt == "executorch"):
                errors.append(f"{where}: backend= is for android cells and mac / ios "
                              "litert-lm, onnxruntime-genai and core-ai cells only (the Mac and iPhone "
                              "runners forward it as --litert-backend, the ORT GenAI driver as its "
                              "execution provider; core-ai's backend=ane is arm identity only; every "
                              "other Apple arm encodes its backend in the model id)")
            if plat == "android" and rt == "litert-lm" and not opts.get("backend"):
                errors.append(f"{where}: android litert-lm needs backend=cpu|gpu "
                              "(arm identity; run_cell refuses it — the anchors.cells "
                              "android litert row shipped without one and had never "
                              "actually run until the S26 first session hit it)")
            # backend=npu: the Android arms llama.cpp-npu (a side build's Hexagon HTP) and
            # litert-lm-npu (the Qualcomm dispatch); the Mac / iPhone runners take cpu|gpu
            if opts.get("backend") == "npu" and not (plat == "android" and rt in ("llama.cpp", "litert-lm")):
                errors.append(f"{where}: backend=npu is an android llama.cpp / litert-lm row only")
            if plat == "android" and rt == "llama.cpp":
                if opts.get("backend") and opts["backend"] not in ANDROID_LLAMA_BACKENDS:
                    errors.append(f"{where}: android llama.cpp takes backend=npu|gpu (a side build's "
                                  "device); a row without backend= is the CPU arm `llama.cpp`")
                if bool(opts.get("backend")) != bool(opts.get("engine-build")):
                    errors.append(f"{where}: android llama.cpp backend=npu|gpu and engine-build=<tag> "
                                  "go together (the pinned flat build is CPU-only; engine-build= "
                                  "alone would stamp the CPU arm with a second build)")
            # an android litert-lm row on the NPU (arm litert-lm-npu) runs a side build: a
            # LiteRT-LM runtime with the Qualcomm dispatch libraries, named by engine-build=
            # (docs/dashboard-cells-v1.md "LiteRT-LM on the NPU"); cpu / gpu run the pinned build
            if plat == "android" and rt == "litert-lm":
                if (opts.get("backend") == "npu") != bool(opts.get("engine-build")):
                    errors.append(f"{where}: android litert-lm backend=npu and engine-build=<tag> go "
                                  "together (the NPU runs a LiteRT-LM side build with the Qualcomm "
                                  "dispatch libraries; engine-build= is read for backend=npu only)")
                if (opts.get("backend") == "npu" and not opts.get("exclude")
                        and (opts.get("context-tokens") or NATIVE_TASK.match(task)
                             or ENDURANCE_TASK.match(task))):
                    errors.append(f"{where}: android litert-lm backend=npu runs a prompt task on the "
                                  "bundle's own KV cache: no context-tokens= (an AOT bundle's cache "
                                  "is fixed at export), no native-benchmark- / endurance- task "
                                  "(not wired; android/bench/run_cell.py refuses them)")
            if opts.get("engine-build") and not (plat == "android" and rt in ("llama.cpp", "litert-lm")):
                errors.append(f"{where}: engine-build= is read for android llama.cpp and litert-lm "
                              "rows only (android/bench/run_cell.py --engine-build)")
            if opts.get("max-tokens") and plat == "mac":
                errors.append(f"{where}: the Mac CLI has no --max-tokens flag "
                              "(BenchmarkRunner.Configuration carries no budget "
                              "override) — encode the budget in the task id "
                              "(e.g. long-context-1024-gen256)")
            # context-tokens is part of the cell identity: the Mac runner keys the
            # capture file on it, so one cell at two allocations is two cells.
            key = (plat, rt, mid, task, opts.get("backend", ""),
                   opts.get("context-tokens", ""), opts.get("file", ""), opts.get("recipe", ""),
                   opts.get("thinking", "model-default") if rt == "uzu" else "")
            if key in seen:
                errors.append(f"{where}: duplicate cell (first at line {seen[key]})")
            else:
                seen[key] = lineno
            platforms_in_file.add(plat)
            if opts.get("anchor") == "1":
                anchors_by_platform.add(plat)
                if opts.get("exclude") or opts.get("manual"):
                    errors.append(f"{where}: an anchor cell cannot be "
                                  "excluded/manual")
            if "exclude-on" in opts:
                if plat != "android":
                    errors.append(f"{where}: exclude-on= is read by the Android runner only "
                                  "(android/bench/run_campaign.py); the Mac and iPhone "
                                  "runners would run the row on every device")
                if opts.get("exclude"):
                    errors.append(f"{where}: exclude= already excludes the row on every "
                                  "device; exclude-on= beside it is ambiguous")
                if opts.get("anchor") == "1":
                    errors.append(f"{where}: an anchor cell cannot be excluded on a device "
                                  "(that device's sittings need their session anchor)")
                if devices is None:
                    devices = load_schedule_devices(schedule_path)
                for key in parse_exclude_on(opts["exclude-on"]):
                    dev = devices.get(key)
                    if dev is None:
                        shown = os.path.abspath(schedule_path)
                        if shown.startswith(ROOT + os.sep):
                            shown = os.path.relpath(shown, ROOT)
                        errors.append(f"{where}: exclude-on device key {key!r} is not in "
                                      f"{shown} (keys: {', '.join(sorted(devices)) or 'none'})")
                    elif SCHEDULE_PLATFORM.get(dev.get("platform"), dev.get("platform")) != plat:
                        errors.append(f"{where}: exclude-on device {key!r} is a "
                                      f"{dev.get('platform')} device; the row is {plat}")
            # uzu and the Mac onnxruntime-genai driver resolve HF ids themselves (no
            # yardstick catalog); iPhone onnxruntime-genai rows are app catalog entries
            if (catalog is not None and plat != "android" and rt != "uzu"
                    and not (plat == "mac" and rt == "onnxruntime-genai")
                    and opts.get("local") != "1" and opts.get("exclude") is None):
                if mid not in catalog.get(rt, []):
                    errors.append(f"{where}: model id {mid!r} not in the "
                                  f"{rt} catalog (side-loaded? add local=1)")
    if require_anchor:
        for plat in sorted(platforms_in_file - anchors_by_platform):
            errors.append(f"{path}: no anchor=1 cell for platform {plat!r} "
                          "(regression matrices need one per platform)")
    return errors, warnings


def load_catalog(path):
    """yardstick list --json -> {runtime: [model ids]}."""
    data = json.load(open(path))
    cat = {}
    for rt, models in data.get("models", data).items():
        cat[rt] = [m["id"] if isinstance(m, dict) else m for m in models]
    return cat


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--catalog", help="yardstick list --json output")
    ap.add_argument("--require-anchor", action="store_true")
    ap.add_argument("--schedule", default=DEFAULT_SCHEDULE,
                    help="device registry for exclude-on= keys (default: %(default)s)")
    args = ap.parse_args()
    catalog = load_catalog(args.catalog) if args.catalog else None
    failed = False
    for path in args.files:
        errors, warnings = validate_file(path, catalog, args.require_anchor, args.schedule)
        for w in warnings:
            print(f"WARN {w}")
        for e in errors:
            print(f"ERROR {e}")
            failed = True
        if not errors:
            print(f"OK {path}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
