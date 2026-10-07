"""Parsers for the Android engine CLIs' console output.

Formats verified against the v0.16.0 sources (runtime/framework/io_types.cc
BenchmarkInfo operator<<) and llama.cpp b8999. Absent metrics stay absent —
never derived, never defaulted (a fabricated field is worse than a hole).
"""
import hashlib
import json
import math
import os
import re

# litert_lm_main --benchmark / task mode (io_types.cc)
RE_TTFT = re.compile(r"Time to first token: ([\d.]+) s")
RE_PREFILL = re.compile(r"Prefill Speed: ([\d.]+) tokens/sec")
RE_DECODE = re.compile(r"Decode Speed: ([\d.]+) tokens/sec")
# real v0.16.0 device output: "Prefill Turn 1: Processed 20 tokens in 764.48ms duration."
RE_PREFILL_TOKENS = re.compile(r"Prefill Turn \d+: Processed (\d+) tokens")
RE_DECODE_TOKENS = re.compile(r"Decode Turn \d+: Processed (\d+) tokens")
RE_PEAK_MEM = re.compile(r"[Pp]eak memory.*?([\d.]+) *(MB|GB|bytes)")

# llama-cli perf lines. b8999's -st mode prints the bracket summary
# "[ Prompt: 217.7 t/s | Generation: 20.6 t/s ]" (no token counts — those stay
# absent); the llama_perf_context_print form is kept as a fallback for other
# builds.
RE_LLAMA_BRACKET = re.compile(
    r"\[ Prompt: ([\d.]+) t/s \| Generation: ([\d.]+) t/s \]")
RE_LLAMA_PROMPT = re.compile(
    r"prompt eval time =\s*[\d.]+ ms /\s*(\d+) tokens.*?([\d.]+) tokens per second")
RE_LLAMA_EVAL = re.compile(
    r"(?<!prompt )eval time =\s*[\d.]+ ms /\s*(\d+) (?:tokens|runs).*?([\d.]+) tokens per second")


def _last_float(rx, text):
    hits = rx.findall(text)
    return float(hits[-1]) if hits else None


def parse_litert(text):
    """litert_lm_main console -> metrics dict (BenchmarkResult field names)."""
    m = {}
    ttft = _last_float(RE_TTFT, text)
    if ttft is not None:
        m["firstTokenLatencyMS"] = ttft * 1000
    prefill = _last_float(RE_PREFILL, text)
    if prefill is not None:
        m["promptTokensPerSecond"] = prefill
    decode = _last_float(RE_DECODE, text)
    if decode is not None:
        m["decodeTokensPerSecond"] = decode
    pt = RE_PREFILL_TOKENS.findall(text)
    if pt:
        m["promptTokenCount"] = sum(int(x) for x in pt)
    dt = RE_DECODE_TOKENS.findall(text)
    if dt:
        m["generatedTokenCount"] = sum(int(x) for x in dt)
    peak = RE_PEAK_MEM.search(text)
    if peak:
        val, unit = float(peak.group(1)), peak.group(2)
        mb = val * 1024 if unit == "GB" else val / (1024 * 1024) if unit == "bytes" else val
        m["memoryPeakEngineReportedMB"] = mb
    return m


def parse_litert_iterations(text):
    """One BenchmarkInfo per fresh Conversation in advanced_main's loop.

    NoPrefix logging prints the marker at column zero (v0.16.0 io_types.cc).
    Never feed the whole multi-iteration log to parse_litert: it sums counts.
    A missing marker is missing evidence, not a fabricated generation.
    """
    return [parse_litert(block) for block in
            re.split(r"(?m)^BenchmarkInfo:\s*$", text)[1:]]


def context_prompt_results(text, context_tokens, budget):
    """Parse and flag a two-iteration launch without making admission policy.

    Raw output (including decoded text and the settings dump) remains stored
    verbatim by run_cell. Flags are retained on BOTH records of the launch.
    """
    iterations = parse_litert_iterations(text)
    witnesses = [int(v) for v in re.findall(r"\bmax_tokens:\s*(\d+)", text)]
    invalid = len(re.findall(r"Invalid decode", text, re.IGNORECASE))
    flags = []
    if len(iterations) != 2:
        flags.append(f"benchmark-iteration-count-{len(iterations)}-expected-2")
    if not witnesses:
        flags.append("allocation-witness-missing")
    elif any(v != context_tokens for v in witnesses):
        flags.append("allocation-witness-mismatch")
    if invalid:
        flags.append("invalid-decode")
    for i, m in enumerate(iterations, 1):
        required = ("promptTokenCount", "generatedTokenCount",
                    "promptTokensPerSecond", "decodeTokensPerSecond")
        if any(k not in m or not math.isfinite(m[k]) or m[k] <= 0 for k in required):
            flags.append(f"iteration-{i}-incomplete-metrics")
        if m.get("generatedTokenCount", 0) > budget:
            flags.append(f"iteration-{i}-output-budget-exceeded")
        if m.get("promptTokenCount", 0) + m.get("generatedTokenCount", 0) > context_tokens:
            flags.append(f"iteration-{i}-context-budget-exceeded")
    return iterations, {"allocationWitnessTokens": witnesses,
                        "invalidDecodeCount": invalid, "protocolFlags": flags}


def context_prompt_texts(text):
    """Printed responses before each BenchmarkInfo, using the R3/R4 boundaries.

    Preserve whitespace-only output. The region includes CLI separator newlines;
    character counts are not token counts. This extracts text, not engine rates.
    """
    outputs = []
    for start in re.finditer(r"^.* Running single-turn conversation\s*$", text, re.M):
        stop = re.search(r"^BenchmarkInfo:\s*$", text[start.end():], re.M)
        if not stop:
            continue
        end = start.end() + stop.start()
        prefix = text[start.end():end]
        if "[thought]" in prefix:
            offset = prefix.index("[thought]")
        else:
            traces = list(re.finditer(r"^external/[^\n]+:\d+[ \t]*$", prefix, re.M))
            logs = list(re.finditer(r"^[IWEF]\d{4} [^\n]*\n", prefix, re.M))
            offset = traces[-1].end() if traces else logs[-1].end() if logs else 0
        value = prefix[offset:]
        outputs.append(value.strip() if value.strip() else value)
    return outputs


def text_integrity(value):
    """Automated screen; retained full text is also reviewed after the sitting."""
    words = re.findall(r"[A-Za-z]+", value.lower())
    alnum = sum(ch.isalnum() for ch in value)
    terms = bool(re.search(r"on.device|phone|local|cloud|offline|privacy|\bai\b", value, re.I))
    lines = [line.strip() for line in value.splitlines() if line.strip()]
    repeats = max((lines.count(line) for line in set(lines)), default=0)
    flags = []
    if alnum < 32 or len(set(words)) < 10:
        flags.append("text-empty-or-degenerate")
    if not terms:
        flags.append("text-off-task-screen")
    if len(lines) >= 4 and repeats / len(lines) > 0.5:
        flags.append("text-repetition-loop")
    return {"status": "FAIL" if flags else "PASS", "alphanumericCount": alnum,
            "distinctWords": len(set(words)), "taskTerms": terms,
            "flags": flags, "method": "r3-r4-response-boundary + lexical screen; full text retained"}


def parse_llama_cli(text):
    """llama-cli perf print -> metrics dict. No TTFT (absent, not derived)."""
    m = {}
    b = RE_LLAMA_BRACKET.search(text)
    if b:
        m["promptTokensPerSecond"] = float(b.group(1))
        m["decodeTokensPerSecond"] = float(b.group(2))
        return m
    p = RE_LLAMA_PROMPT.search(text)
    if p:
        m["promptTokenCount"] = int(p.group(1))
        m["promptTokensPerSecond"] = float(p.group(2))
    e = RE_LLAMA_EVAL.search(text)
    if e:
        m["generatedTokenCount"] = int(e.group(1))
        m["decodeTokensPerSecond"] = float(e.group(2))
    return m


RE_ORTGENAI = re.compile(r"^ORTGENAI (.*)$", re.M)
RE_ORTGENAI_LIBS = re.compile(r"^ORTGENAI_LIBS (.*)$", re.M)
RE_ORTGENAI_OUTPUT = re.compile(r"\[OUTPUT BEGIN\](.*?)\[OUTPUT END\]", re.S)
ORTGENAI_STOP = {"eos": "stop", "budget": "length", "max_length": "max_length"}


def _number(value):
    try:
        return int(value)
    except ValueError:
        try:
            return float(value)
        except ValueError:
            return value


def parse_ortgenai(text):
    """ortgenai_run console (android/ortgenai/ortgenai_run.cpp output contract) ->
    (metrics, report, libraries, decoded text).

    report = every key=value of the ORTGENAI line, numbers as numbers and unknown keys
    kept (the record carries it whole); libraries = the ORTGENAI_LIBS paths; decoded
    text = the [OUTPUT BEGIN]..[OUTPUT END] span, None when the run printed none.
    metrics use BenchmarkResult names: prompt tok/s = prompt_tokens / prefill_ms (the
    AppendTokenSequences wall clock), TTFT = ttft_ms, decode = the line's decode_tps
    ((gen_tokens - 1) / decode_ms_total), stopReason eos -> stop, budget -> length.
    Absent keys stay absent."""
    m = RE_ORTGENAI.search(text)
    if not m:
        return {}, {}, [], None
    report = {}
    for item in m.group(1).split():
        key, sep, value = item.partition("=")
        if sep:
            report[key] = _number(value)
    metrics = {}
    if isinstance(report.get("prompt_tokens"), int):
        metrics["promptTokenCount"] = report["prompt_tokens"]
    if isinstance(report.get("gen_tokens"), int):
        metrics["generatedTokenCount"] = report["gen_tokens"]
    prefill = report.get("prefill_ms")
    if isinstance(prefill, (int, float)) and prefill > 0 and "promptTokenCount" in metrics:
        metrics["promptTokensPerSecond"] = metrics["promptTokenCount"] / prefill * 1000.0
    if isinstance(report.get("ttft_ms"), (int, float)):
        metrics["firstTokenLatencyMS"] = float(report["ttft_ms"])
    if isinstance(report.get("decode_tps"), (int, float)):
        metrics["decodeTokensPerSecond"] = float(report["decode_tps"])
    if report.get("stop") in ORTGENAI_STOP:
        metrics["stopReason"] = ORTGENAI_STOP[report["stop"]]
    libs = RE_ORTGENAI_LIBS.search(text)
    out = RE_ORTGENAI_OUTPUT.search(text)
    return metrics, report, (libs.group(1).split() if libs else []), (out.group(1) if out else None)


def parse_llama_bench_json(text):
    """llama-bench -o json -> list of per-test dicts {kind, avg_ts, n_prompt, n_gen,
    stddev_ts} plus the fields that say where the tests ran (BENCH_DEVICE_FIELDS).

    The array is the block from the first line that is exactly "[" to the last line that
    is exactly "]" — llama-bench's json printer writes both alone. A side build's backend
    lines before it carry brackets of their own (b11469's Hexagon registry logs
    "FASTRPC_GET_DOMAINS[0]: …"), which the first-"[" slice, kept as the fallback, would
    take for the array's start."""
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if line.strip() == "["), None)
    end = next((i for i in range(len(lines) - 1, -1, -1) if lines[i].strip() == "]"), None)
    if start is not None and end is not None and end > start:
        data = json.loads("\n".join(lines[start:end + 1]))
    else:
        data = json.loads(text[text.index("["):text.rindex("]") + 1])
    out = []
    for t in data:
        kind = "prefill" if t.get("n_prompt", 0) > 0 and t.get("n_gen", 0) == 0 else "decode"
        out.append({"kind": kind, "avg_ts": t.get("avg_ts"),
                    "n_prompt": t.get("n_prompt"), "n_gen": t.get("n_gen"),
                    "stddev_ts": t.get("stddev_ts"),
                    **{k: t.get(k) for k in BENCH_DEVICE_FIELDS}})
    return out


# llama-bench's JSON fields that say where its tests ran: `devices` = the device the tests
# ran on (HTP0 / GPUOpenCL), `backends` = every backend the build registered (not the one
# used), `gpu_info`, and the settings that shape the run on it
BENCH_DEVICE_FIELDS = ("devices", "backends", "gpu_info", "n_gpu_layers", "flash_attn", "n_ubatch")


def llama_bench_device_lines(tests):
    """A llama-bench launch's conditions.backendRegistered: its JSON's BENCH_DEVICE_FIELDS,
    one line per distinct set across its tests ("llama-bench json: {...}"). The fields are
    the witness; the backend init lines before the JSON only say what the build loaded."""
    out = []
    for t in tests or []:
        line = "llama-bench json: " + json.dumps({k: t.get(k) for k in BENCH_DEVICE_FIELDS})
        if line not in out:
            out.append(line)
    return out


# llama.cpp side builds (run_cell.engine_command with engine-build=): the chat tool's own
# lines that say which device a launch registered and used, in their b11469 forms (2026-10-07
# S26 smoke at -lv 4; ggml-hexagon.cpp, ggml-opencl.cpp, src/llama.cpp, src/llama-model.cpp):
#   ggml-hex: Hexagon Arch version v81, DMA64 enabled            (Hexagon registry)
#   ggml_opencl: device: 'QUALCOMM Adreno(TM) 840 (OpenCL 3.0 Adreno(TM) 840)'   (OpenCL registry)
#   ggml_opencl: OpenCL driver: OpenCL 3.0 QUALCOMM build: 0842.19.8 Compiler E031.50.19.18
#   ggml_opencl: kernel cache enabled at '<engines dir>/<tag>/clcache'
#   llama_prepare_model_devices: using device HTP0 (Hexagon) (unknown id) - 0 MiB free
#   load_tensors: offloaded 29/29 layers to GPU
#   load_tensors:         HTP0 model buffer size =   406.58 MiB   (also CPU / OpenCL)
# The build loads both backends whichever device runs, so the registry lines of both appear.
# A -lv 4 line carries a "<m>.<s>.<ms>.<us> <level> " prefix; the match starts after it.
BACKEND_LINE_PATTERNS = (
    re.compile(r"ggml-hex: Hexagon Arch version v\d+, DMA64 (?:enabled|disabled)"),
    re.compile(r"ggml_opencl: device: '[^']+'"),
    re.compile(r"ggml_opencl: OpenCL driver: .+"),
    re.compile(r"ggml_opencl: kernel cache enabled at '[^']*'"),
    re.compile(r"\w+: using device \S+ \(.*"),
    re.compile(r"\w+: offloaded \d+/\d+ layers to GPU"),
    re.compile(r"\w+:\s+\S+ model buffer size =\s*[\d.]+ MiB"),
)
# the backend each device belongs to, as llama-bench's `backends` field names it
DEVICE_BACKEND = {"HTP0": "HTP", "GPUOpenCL": "OpenCL"}


def llama_backend_lines(text):
    """The engine output's device lines (BACKEND_LINE_PATTERNS), in order, each once, runs
    of blanks folded — what conditions.backendRegistered carries for a chat launch. Absent
    lines stay absent."""
    out = []
    for line in text.split("===ENGINE_OUTPUT===", 1)[-1].splitlines():
        for rx in BACKEND_LINE_PATTERNS:
            m = rx.search(line)
            if m:
                found = re.sub(r"\s+", " ", m.group(0).strip())
                if found not in out:
                    out.append(found)
                break
    return out


def llama_backend_registered(lines, device, buffer, tool, bench_tests=None):
    """Did this launch run on `device` (HTP0 / GPUOpenCL)? The chat tool: llama's own
    `using device <device>` line, a model buffer of that device (`buffer`: HTP0 / OpenCL)
    and every layer offloaded (N/N in each offloaded line). llama-bench, whose llama log is
    silenced: every JSON test names the device, -ngl 99 and the device's backend among the
    registered ones. Anything less is a launch that may have run elsewhere."""
    if tool == "llama-bench":
        return bool(bench_tests) and all(
            t.get("devices") == device and t.get("n_gpu_layers") == 99
            and DEVICE_BACKEND[device] in str(t.get("backends") or "").split(",") for t in bench_tests)
    used = any(re.search(rf": using device {re.escape(device)} \(", line) for line in lines)
    weights = any(re.search(rf": {re.escape(buffer)} model buffer size = ", line) for line in lines)
    offloaded = [m.groups() for line in lines for m in [re.search(r"offloaded (\d+)/(\d+) layers", line)] if m]
    return used and weights and bool(offloaded) and all(n == total for n, total in offloaded)


# LiteRT-LM on the NPU (run_cell.engine_command, a side build with engine-build=): the
# engine's own lines that say which backend a launch chose and registered and what the
# Qualcomm dispatch took, in the forms of the self-built litert_lm_advanced_main of
# 2026-08-21 on the Galaxy S26 (the lane's NPU logs of 2026-08-23 to 2026-10-03, outside this
# repo; LiteRT-LM main b12c62c7 runtime/engine/litert_lm_lib.cc for the settings echo):
#   I0000 00:00:1787447197.028690   26280 litert_lm_lib.cc:499] Choose backend: npu
#   I0000 00:00:1787447197.028842   26280 litert_lm_lib.cc:652] executor_settings: backend: NPU
#   use_hw_cache_update_for_npu: false            (the settings echo, one per line)
#   litert_dispatch_lib_dir: /data/local/tmp/llmbench/engines/<tag>
#   INFO: [accelerator_registry.cc:54] RegisterAccelerator: ptr=0xb400007b8f206890, name=NpuAccelerator
#   INFO: [npu_registry.cc:30] NPU accelerator registered.
#   INFO: [litert_dispatch.cc:159] Loading shared library: <dir>/libLiteRtDispatch_Qualcomm.so
#   INFO: [compiler_plugin.cc:260] Loaded plugin at: <dir>/libLiteRtCompilerPlugin_Qualcomm.so  (JIT)
#     BackendType              : Htp(2)          (the dispatch's ::qnn::Options table)
#   VERBOSE: Replacing 1 out of 1 node(s) with delegate (DispatchDelegate) node, yielding 1 partitions for subgraph 0 (prefill_128).
#   INFO: [litert_dispatch_device_context.cc:248] Creating new QNN context for bytecode 0x797af997b0 (size 282300416)
# LiteRT creates its environment several times per launch and only the first registers the
# NPU: the later ones log "NPU accelerator could not be loaded and registered" on a healthy
# run, so that warning is not read. Addresses read as <addr>, so a build's lines are the
# same on every launch.
LITERT_NPU_LINE_PATTERNS = (
    re.compile(r"Choose backend: \w+"),
    re.compile(r"executor_settings: backend: \w+"),
    re.compile(r"^use_hw_cache_update_for_npu: \w+"),
    re.compile(r"^litert_dispatch_lib_dir: .*"),
    re.compile(r"RegisterAccelerator: ptr=\w+, name=NpuAccelerator"),
    re.compile(r"NPU accelerator registered\."),
    re.compile(r"Loading shared library: \S*libLiteRtDispatch\S*"),
    re.compile(r"Loaded plugin at: \S+"),
    re.compile(r"\bBackendType\s+: \S+"),
    re.compile(r"Replacing \d+ out of \d+ node\(s\) with delegate \(DispatchDelegate\) node.*"),
    re.compile(r"Creating new QNN context for bytecode \w+ \(size \d+\)"),
)


def litert_npu_lines(text):
    """The engine output's NPU lines (LITERT_NPU_LINE_PATTERNS), in order, each once, runs of
    blanks folded, addresses as <addr> — conditions.backendRegistered of a LiteRT-LM NPU
    launch. Absent lines stay absent."""
    out = []
    for line in text.split("===ENGINE_OUTPUT===", 1)[-1].splitlines():
        for rx in LITERT_NPU_LINE_PATTERNS:
            m = rx.search(line)
            if m:
                found = re.sub(r"\b0x[0-9a-fA-F]+\b", "<addr>", re.sub(r"\s+", " ", m.group(0).strip()))
                if found not in out:
                    out.append(found)
                break
    return out


def litert_npu_registered(lines):
    """Did this LiteRT-LM launch run on the NPU? It chose the npu backend, LiteRT registered
    its NPU accelerator, and the dispatch delegate took at least one of the model's subgraphs
    (an NPU that registers while the model runs on XNNPACK — a bundle with nothing compiled
    for this NPU — shows no DispatchDelegate line). Anything less is a launch that may have
    run elsewhere."""
    return ("Choose backend: npu" in lines
            and any(ln.endswith("name=NpuAccelerator") or ln == "NPU accelerator registered." for ln in lines)
            and any("with delegate (DispatchDelegate)" in ln for ln in lines))


# the lines a LiteRT-LM launch logs among its printed reply: absl's ("W0000 00:00:1787447197.923067
# 26280 tasks.cc:572] …", on its own line or glued to the end of a streamed token), the
# "=== Source Location Trace: ===" block under one and its file:line entries, LiteRT's and
# TFLite's own ("INFO: […]", "VERBOSE: …"), and the QNN libraries' ("[1] graph_prepare.cc:208::…")
RE_ABSL_LOG = re.compile(r"[IWEF]\d{4} \d\d:\d\d:\d+\.\d+\s+\d+ \S+:\d+\] .*$")
RE_LITERT_LOG_LINE = re.compile(
    r"^(?:(?:INFO|WARNING|ERROR|VERBOSE|DEBUG): .*"
    r"|=== Source Location Trace: ===\s*"
    r"|(?:\./|external/)\S+:\d+\s*"
    r"|\[\d+\] (?:\S+\.(?:cc|cpp|h):\d+:|Qnn\w* <\w>).*)$")


def litert_reply(text):
    """The reply a litert_lm_advanced_main single-turn launch printed, for the text check (a
    LiteRT-LM side build's prompt launch: --benchmark with the real prompt, --async=false, so
    the reply comes in one piece after the engine's logs): the output after its "Running
    single-turn conversation" log line up to "BenchmarkInfo:" (or the end, when that never
    came), with the log lines taken out (RE_ABSL_LOG, RE_LITERT_LOG_LINE), from "[thought]"
    on when the reply has a thinking channel. Reasoning and answer both stay, as printed. ""
    when nothing was printed."""
    out = text.split("===ENGINE_OUTPUT===", 1)[-1]
    start = re.search(r"^.* Running single-turn conversation\s*$", out, re.M)
    if not start:
        return ""
    out = out[start.end():]
    stop = re.search(r"^BenchmarkInfo:\s*$", out, re.M)
    out = out[:stop.start()] if stop else out
    kept = []
    for line in out.splitlines():
        if RE_LITERT_LOG_LINE.match(line):
            continue
        cut = RE_ABSL_LOG.sub("", line)
        if cut or not RE_ABSL_LOG.search(line):
            kept.append(cut)
    value = "\n".join(kept)
    if "[thought]" in value:
        value = value[value.index("[thought]"):]
    return value.strip() if value.strip() else value


# a llama.cpp log line as -lv 4 prints it: "<m>.<s>.<ms>.<us> <I|W|D|E> " and the message
RE_LLAMA_LOG = re.compile(r"\d+\.\d+\.\d+\.\d+ [IWDE] .*$")


def llama_cli_reply(text, prompt=None):
    """The reply a llama-cli single-turn launch printed, for the text check: after its echo
    of the prompt ("> <prompt>", or the first 500 bytes and " ... (truncated)" — b11469
    tools/cli/cli-ui.h) up to the "[ Prompt: … ]" line, with the log lines a -lv 4 launch
    interleaves taken out (a whole log line goes; one glued to the end of a reply line is cut
    off it). Reasoning and answer both stay, as printed. "" when nothing follows the echo."""
    out = text.split("===ENGINE_OUTPUT===", 1)[-1]
    stop = RE_LLAMA_BRACKET.search(out)
    out = out[:stop.start()] if stop else out
    start = -1
    if prompt:
        raw = prompt.encode()
        shown = prompt if len(raw) <= 500 else raw[:500].decode(errors="ignore") + " ... (truncated)"
        at = out.find("> " + shown)
        if at >= 0:
            start = at + len("> " + shown)
    if start < 0:
        echo = re.search(r"(?m)^> .*$", out)
        start = echo.end() if echo else len(out)
    kept = []
    for line in out[start:].splitlines():
        cut = RE_LLAMA_LOG.sub("", line)
        if cut or not RE_LLAMA_LOG.search(line):
            kept.append(cut)
    value = "\n".join(kept)
    return value.strip() if value.strip() else value


# ---------------------------------------------------------------- ExecuTorch
# The ExecuTorch arm (docs/executorch-arm-v1.md): an own export of each model with the
# ExecuTorch tag's own exporter, run by the tag's own C++ runner for its model family —
# llama_main (examples/models/llama) for Qwen 3, gemma4_e2e_runner (examples/models/gemma4)
# for Gemma 4 — on Android (android/bench/run_cell.py) and on the Mac
# (scripts/executorch_mac.py). Both writers read the runners' consoles and the staged
# inputs here; executorch_inputs is the one function of this module that reads files.
#   llama_main: stdout = the prompt echo, the generated text, "\n" and one
#     "PyTorchObserver {json}" line (extension/llm/runner/stats.h print_report)
#   gemma4_e2e_runner: stdout = the generated text and "\n"; stderr ends with its
#     "=== Gemma 4 Performance Report ===" (runner/gemma4_stats.h report())
#   stderr also holds ET_LOG lines when the build logs (the Android builds do; the Mac
#   stock Release build compiles them out).

EXECUTORCH_STATS_PREFIX = "PyTorchObserver "
GEMMA4_REPORT_HEAD = "=== Gemma 4 Performance Report ==="
# provenance.definitions of every executorch record, verbatim, per runner
EXECUTORCH_DEFINITIONS = {
    "llama_main": (
        "prefill tok/s = prompt_tokens / (prompt_eval_end_ms - inference_start_ms) * 1000. The window "
        "opens before the runner tokenizes the prompt (TextLLMRunner::generate sets inference_start_ms, "
        "then encodes), so prefill includes tokenization.\n"
        "TTFT ms = first_token_ms - inference_start_ms = the same window (first_token_ms is taken when "
        "prefill returns, before the first token is decoded to text).\n"
        "decode tok/s = generated_tokens / (inference_end_ms - prompt_eval_end_ms) * 1000, "
        "generated_tokens = tokens of the decode loop; the reply has one more token, the one prefill "
        "sampled.\n"
        "cold = one generation in a fresh llama_main process (no --warmup). warm = llama_main --warmup: "
        "one unmeasured generation of the same prompt and max_new_tokens in the same process, stats and "
        "KV position reset, the second generation measured.\n"
        "Clock: integer milliseconds (extension/llm/runner/util.h time_in_ms)."),
    "gemma4_e2e_runner": (
        "prefill tok/s = prompt tokens / prefill ms * 1000, prefill = the one text_decoder forward over "
        "the prompt (Gemma4Runner::generate_text opens the window after it has tokenized the prompt, so "
        "prefill excludes tokenization).\n"
        "TTFT ms = the same prefill window (Gemma4Stats::time_to_first_token_ms, text only).\n"
        "decode tok/s = generated tokens / generation ms * 1000, generation = from after the first token "
        "is sampled from the prefill logits to the end of the decode loop (Gemma4Runner::decode_loop); "
        "generated tokens = every token of the reply, the prefill-sampled one included, so the window "
        "holds one forward pass fewer than the count.\n"
        "cold = one generation in a fresh gemma4_e2e_runner process; the runner has no warmup option, so "
        "there is no warm regime.\n"
        "Clock: std::chrono::steady_clock; the report prints ms with one decimal under 1 s and seconds "
        "with two decimals from 1 s on (10 ms resolution)."),
}
# cells recipe= alias -> the record's model.quantization label (quant-label-rule), the runner
# of its model family and the recipe.json facts the label states: executorch_inputs refuses an
# artifact whose recipe.json says otherwise. A model whose export is not established has no alias.
EXECUTORCH_RECIPES = {
    # export_llm with examples/models/qwen3/config/qwen3_xnnpack_q8da4w.yaml, unchanged: no
    # group_size in the yaml = v1.5.1 quantize.py's 128 (export log block_size=(1, 128)),
    # use_hqq on, every Linear incl. the output projection, embedding_quantize 8,0
    "et1.5.1-xnnpack-8da4w-g128-emb8": {
        "runner": "llama_main", "executorch": "1.5.1",
        "label": ("8da4w: int8 dynamic per-token asymmetric activations x int4 symmetric weights, "
                  "group 128, HQQ scale-only (every Linear incl. lm_head); embedding int8 per-row "
                  "(embedding_byte); fp32 compute and KV cache; own export, ExecuTorch 1.5.1"),
        "yaml": {"qmode": "8da4w", "embedding_quantize": "8,0", "group_size": None,
                 "dtype_override": "fp32"},
    },
    # examples/models/gemma4/export_gemma4.py --quantize 8da4w+emb8 --no-audio --no-vision:
    # quant_utils.apply_linear_quantization -> extension/llm/export/quantize.py 8da4w =
    # Int8DynamicActivationIntxWeightConfig(int4, PerGroup(128), hqq_scale_only) with
    # skip_incompatible_shapes; apply_embedding_quantization = EmbeddingQuantHandler(8 bit,
    # group None); the exporter's defaults as the recipe.json records them
    "et1.5.1-gemma4-xnnpack-8da4w-g128-emb8": {
        "runner": "gemma4_e2e_runner", "executorch": "1.5.1",
        "label": ("8da4w+emb8 (export_gemma4.py): int8 dynamic activations x int4 weights, group 128, "
                  "HQQ scale-only on the Linear layers (a Linear whose input width is not a multiple "
                  "of 128 stays unquantized); embeddings int8 per-row; fp32 compute and KV cache; "
                  "text decoder only; own export, ExecuTorch 1.5.1"),
        "args": {"quantize": "8da4w+emb8", "no_audio": True, "no_vision": True},
        "defaults": {"group_size": 128, "dtype": "float32", "quantize_kv_cache": False},
    },
    # the Qwen 3 yaml above lowered to another delegate by export_llm overrides
    # (scripts/executorch/export_qwen3.py --set; the recipe.json's export_args are what "args"
    # checks, None = the key is not overridden, the yaml's value stands). export_llama_lib takes
    # the xnnpack branch first, so xnnpack is turned off.
    # MLX: no handler for 8da4w's dynamic activation quantization (that export stops at
    # "Missing out variants: torchao::choose_qparams_affine ..."), so 4w = torchao
    # IntxWeightOnlyConfig int4 symmetric PerGroup(128) (the 4w default is 256), hqq_scale_only,
    # every Linear; the yaml's embedding_quantize 8,0 stays outside the delegate
    "et1.5.1-mlx-4w-g128-emb8": {
        "runner": "llama_main", "executorch": "1.5.1",
        "label": ("4w: int4 symmetric weight-only, group 128, HQQ scale-only (every Linear incl. "
                  "lm_head), fp32 activations; embedding int8 per-row (embedding_byte, outside the "
                  "delegate); fp32 compute and KV cache; MLX delegate; own export, ExecuTorch 1.5.1"),
        "args": {"backend.xnnpack.enabled": False, "backend.mlx.enabled": True,
                 "quantization.qmode": "4w", "quantization.group_size": 128,
                 "quantization.embedding_quantize": None, "model.dtype_override": None},
    },
    # Vulkan takes the yaml's 8da4w as it is (et_vk.linear_dq8ca_q4gsw in the export log)
    "et1.5.1-vulkan-8da4w-g128-emb8": {
        "runner": "llama_main", "executorch": "1.5.1",
        "label": ("8da4w: int8 dynamic per-token asymmetric activations x int4 symmetric weights, "
                  "group 128, HQQ scale-only (every Linear incl. lm_head); embedding int8 per-row "
                  "(embedding_byte, outside the delegate); fp32 compute and KV cache; Vulkan delegate; "
                  "own export, ExecuTorch 1.5.1"),
        "args": {"backend.xnnpack.enabled": False, "backend.vulkan.enabled": True,
                 "quantization.qmode": None, "quantization.group_size": None,
                 "quantization.embedding_quantize": None, "model.dtype_override": None},
    },
}
EXECUTORCH_SAMPLER = "greedy (--temperature 0: argmax)"
RE_ET_THREADS = re.compile(r"(?:Resetting threadpool with num threads =|Setting threadpool to) (\d+)")
RE_ET_METADATA = re.compile(r"Metadata: (\w+) = (-?\d+)")
RE_ET_RSS = re.compile(r"RSS after (loading model|prompt prefill|finishing text generation): ([\d.]+) MiB")
RE_ET_MAX_NEW = re.compile(r"Max new tokens resolved: (\d+), given pos_ (\d+), "
                           r"num_prompt_tokens (\d+), max_context_len (\d+)")
RE_ET_REACHED = re.compile(r"Max new tokens (\d+) reached!")
RE_ET_ERROR = re.compile(r"^E \d\d:\d\d:\d\d\.\d+ executorch:.*$", re.M)
ET_RSS_KEYS = {"loading model": "rssAfterLoadMiB", "prompt prefill": "rssAfterPrefillMiB",
               "finishing text generation": "rssAfterGenerationMiB"}
RE_G4_LINE = re.compile(r"^\s+(Model load|Prefill|Generation|TTFT|Total):\s+([\d.]+) (ms|s)"
                        r"(?: \((\d+) tokens, ([\d.]+) tok/s\))?\s*$", re.M)
RE_G4_MEMORY = re.compile(r"^\s+Memory \((load|peak)\):\s+([\d.]+) MB\s*$", re.M)
# a report line: two spaces, a label, a colon ("  Prefill:           101.3 ms (20 tokens, 197 tok/s)")
RE_G4_REPORT_LINE = re.compile(r"^  [A-Z][\w ()]*:\s")


def executorch_runner_for(name):
    """The runner of a model family, from a model id or artifact name: llama_main for
    Qwen 3, gemma4_e2e_runner for Gemma 4, None for anything else (no rule = no launch)."""
    low = os.path.basename(name).lower()
    if re.search(r"gemma-?4", low):
        return "gemma4_e2e_runner"
    if re.search(r"qwen3-", low):
        return "llama_main"
    return None


def executorch_recipe_runner(recipe):
    """The runner a recipe.json's exporter feeds: export_gemma4.py -> gemma4_e2e_runner,
    export_llm with a Qwen 3 config -> llama_main, else None."""
    exporter = (recipe.get("exporter") or {}).get("tree_path") or ""
    if exporter.endswith("examples/models/gemma4/export_gemma4.py"):
        return "gemma4_e2e_runner"
    if (str(recipe.get("model_class") or "").startswith("qwen3")
            or str(recipe.get("config_yaml_path") or "").startswith("examples/models/qwen3/")):
        return "llama_main"
    return None


def _yaml_value(cfg, key):
    hit = re.search(rf"^\s*{key}:\s*(.+?)\s*$", cfg, re.M)
    return hit.group(1).strip("'\"") if hit else None


def executorch_recipe_problems(alias, recipe):
    """What makes a staged artifact's recipe.json disagree with the cells' recipe= alias
    (EXECUTORCH_RECIPES) -> [problem, ...]; [] = the label applies. recipe = the
    <stem>.recipe.json dict the export wrote beside the .pte."""
    want = EXECUTORCH_RECIPES.get(alias)
    if want is None:
        return [f"recipe alias {alias!r} has no label (parsers.EXECUTORCH_RECIPES)"]
    problems = []
    if str(recipe.get("executorch")) != want["executorch"]:
        problems.append(f"recipe.json executorch {recipe.get('executorch')!r} != {want['executorch']!r}")
    runner = executorch_recipe_runner(recipe)
    if runner != want["runner"]:
        problems.append(f"recipe.json feeds runner {runner!r}, the alias names {want['runner']!r}")
    if "yaml" in want:
        cfg = recipe.get("resolved_config_yaml") or recipe.get("config_yaml") or ""
        for key, value in want["yaml"].items():
            if _yaml_value(cfg, key) != value:
                problems.append(f"recipe.json {key} {_yaml_value(cfg, key)!r} != {value!r}")
        if not re.search(r"^\s*xnnpack:\s*\n\s*enabled:\s*[Tt]rue", cfg, re.M):
            problems.append("recipe.json config does not enable the xnnpack backend")
    for section in ("args", "defaults"):
        got = recipe.get("export_args" if section == "args" else "exporter_defaults_in_effect") or {}
        for key, value in want.get(section, {}).items():
            if got.get(key) != value:
                problems.append(f"recipe.json {section} {key} {got.get(key)!r} != {value!r}")
    return problems


def executorch_context_tokens(recipe):
    """The KV allocation fixed at export -> (tokens or None, where the recipe.json says it):
    export_llm's export.max_context_length, export_gemma4.py's --max_seq_len."""
    cfg = recipe.get("resolved_config_yaml") or recipe.get("config_yaml") or ""
    value = _yaml_value(cfg, "max_context_length")
    if value and value.isdigit():
        return int(value), "recipe.json export.max_context_length"
    value = (recipe.get("export_args") or {}).get("max_seq_len")
    if isinstance(value, int) and not isinstance(value, bool):
        return value, "recipe.json export_args.max_seq_len"
    return None, "not in recipe.json"


def parse_executorch(stdout, stderr="", prompt=None):
    """llama_main's stdout and stderr -> {"runner", "metrics", "stats", "statsLine", "text",
    "textExtraction", "log", "engineErrors", "flags"}.

    metrics use BenchmarkResult names, recomputed from the stats line's integer-ms
    timestamps (EXECUTORCH_DEFINITIONS); a rate whose window is 0 ms stays absent, as
    the stats line leaves it out. The line's own prefill_token_per_sec /
    decode_token_per_sec only check the recomputation (flag stats-rate-mismatch).
    text = stdout after the echoed prompt, cut before "\nPyTorchObserver "; an echo
    that is not the prompt leaves text None (flag echo-mismatch) — never a guessed cut.
    log = what the runner logged (thread pool size, the .pte metadata, the RSS
    lines: getrusage ru_maxrss on Linux, 0 where unsupported)."""
    out = {"runner": "llama_main", "metrics": {}, "stats": None, "statsLine": None, "text": None,
           "textExtraction": "not checked (no prompt given)", "log": _executorch_log(stderr),
           "engineErrors": RE_ET_ERROR.findall(stderr or ""), "flags": []}
    lines = [ln for ln in stdout.splitlines() if ln.startswith(EXECUTORCH_STATS_PREFIX)]
    if len(lines) != 1:
        out["flags"].append(f"stats-line-count-{len(lines)}")
    if lines:
        out["statsLine"] = lines[-1]
        try:
            out["stats"] = json.loads(lines[-1][len(EXECUTORCH_STATS_PREFIX):])
        except ValueError:
            out["flags"].append("stats-line-unparsable")
    s = out["stats"] or {}

    def num(key):
        v = s.get(key)
        return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None

    m = out["metrics"]
    start, prefill_end, end = num("inference_start_ms"), num("prompt_eval_end_ms"), num("inference_end_ms")
    prompt_tokens, generated = num("prompt_tokens"), num("generated_tokens")
    if prompt_tokens is not None:
        m["promptTokenCount"] = int(prompt_tokens)
    if generated is not None:
        m["generatedTokenCount"] = int(generated)
    if None not in (start, prefill_end, prompt_tokens) and prefill_end - start > 0:
        m["promptTokensPerSecond"] = prompt_tokens / (prefill_end - start) * 1000
    if None not in (prefill_end, end, generated) and end - prefill_end > 0:
        m["decodeTokensPerSecond"] = generated / (end - prefill_end) * 1000
    first = num("first_token_ms")
    if start and first and first >= start:
        m["firstTokenLatencyMS"] = first - start
    load_start, load_end = num("model_load_start_ms"), num("model_load_end_ms")
    if load_start and load_end and load_end >= load_start:
        m["loadTimeSeconds"] = (load_end - load_start) / 1000
    for ours, theirs in (("promptTokensPerSecond", "prefill_token_per_sec"),
                         ("decodeTokensPerSecond", "decode_token_per_sec")):
        reported = num(theirs)
        # the stats line prints 6 significant digits (std::stringstream default)
        if (reported is None) != (ours not in m) or (
                reported is not None and abs(m[ours] - reported) > 1e-5 * max(1.0, abs(reported))):
            out["flags"].append("stats-rate-mismatch")
            break
    if prompt is not None:
        if stdout.startswith(prompt):
            body = stdout[len(prompt):]
            cut = body.rfind("\n" + EXECUTORCH_STATS_PREFIX)
            out["text"] = body[:cut] if cut >= 0 else body
            out["textExtraction"] = "stdout minus the echoed prompt, cut before '\\nPyTorchObserver '"
        else:
            out["textExtraction"] = "FAILED: stdout does not start with the prompt echo"
            out["flags"].append("echo-mismatch")
    return out


def _executorch_log(stderr):
    log = {}
    threads = RE_ET_THREADS.findall(stderr or "")
    if threads:
        log["cpuThreads"] = int(threads[-1])
    for key, value in RE_ET_METADATA.findall(stderr or ""):
        log.setdefault("metadata", {})[key] = int(value)
    for which, value in RE_ET_RSS.findall(stderr or ""):
        log[ET_RSS_KEYS[which]] = float(value)
    resolved = RE_ET_MAX_NEW.findall(stderr or "")
    if resolved:
        log["maxNewTokensResolved"] = int(resolved[-1][0])
    reached = RE_ET_REACHED.findall(stderr or "")
    if reached:
        log["maxNewTokensReached"] = int(reached[-1])
    return log


def parse_gemma4_runner(stdout, stderr=""):
    """gemma4_e2e_runner's stdout and stderr -> the dict parse_executorch returns, from its
    "=== Gemma 4 Performance Report ===" (statsReport, verbatim) instead of a stats line.

    The report prints rounded times (ms with one decimal under 1 s, else seconds with two)
    and rates with none: metrics are the counts over the printed times, and a printed rate
    outside what the rounding allows flags stats-rate-mismatch. text = stdout minus the
    newline the runner ends it with (no prompt echo)."""
    out = {"runner": "gemma4_e2e_runner", "metrics": {}, "stats": {}, "statsReport": None,
           "text": stdout[:-1] if stdout.endswith("\n") else stdout,
           "textExtraction": "stdout minus the final newline (std::endl after the token stream)",
           "log": _executorch_log(stderr), "engineErrors": RE_ET_ERROR.findall(stderr or ""),
           "flags": []}
    at = (stderr or "").rfind(GEMMA4_REPORT_HEAD)
    if at < 0:
        out["flags"].append("stats-report-missing")
        return out
    block = [GEMMA4_REPORT_HEAD]
    for line in stderr[at + len(GEMMA4_REPORT_HEAD):].split("\n")[1:]:
        if not RE_G4_REPORT_LINE.match(line):
            break
        block.append(line)
    out["statsReport"] = "\n".join(block)
    report = "\n".join(block[1:])
    stats = out["stats"]
    for name, value, unit, tokens, rate in RE_G4_LINE.findall(report):
        key = name.lower().replace(" ", "_")
        stats[key + "_ms"] = float(value) * (1000 if unit == "s" else 1)
        stats[key + "_resolution_ms"] = 10.0 if unit == "s" else 0.1
        if tokens:
            stats[key + "_tokens"] = int(tokens)
            stats[key + "_tok_per_s_printed"] = float(rate)
    for which, value in RE_G4_MEMORY.findall(report):
        stats[f"memory_{which}_mb"] = float(value)
    m = out["metrics"]
    for phase, count_key, rate_key in (("prefill", "promptTokenCount", "promptTokensPerSecond"),
                                       ("generation", "generatedTokenCount", "decodeTokensPerSecond")):
        tokens, ms = stats.get(phase + "_tokens"), stats.get(phase + "_ms")
        if tokens is None or not ms:
            continue
        m[count_key] = tokens
        m[rate_key] = tokens / ms * 1000
        half = stats[phase + "_resolution_ms"] / 2
        low, high = tokens / (ms + half) * 1000, tokens / max(ms - half, 1e-9) * 1000
        printed = stats[phase + "_tok_per_s_printed"]
        if not (low - 0.5 <= printed <= high + 0.5):
            out["flags"].append("stats-rate-mismatch")
    if "ttft_ms" in stats:
        m["firstTokenLatencyMS"] = stats["ttft_ms"]
    if "model_load_ms" in stats:
        m["loadTimeSeconds"] = stats["model_load_ms"] / 1000
    if "promptTokenCount" not in m or "generatedTokenCount" not in m:
        out["flags"].append("stats-report-incomplete")
    return out


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def executorch_inputs(model_dir, pte_file, task, alias, repo_root):
    """The host-side inputs of one executorch cell, checked: the .pte (cells file=, under
    model_dir unless absolute), its <stem>.recipe.json (the .pte's sha256 and the recipe=
    alias's facts), the tokenizer it names (sha256) and the prompt the runner reads —
    llama_main a prompt rendered once on the host with the model's chat template
    (<stem>.prompts/<task>.chat.txt and prompts.json beside the .pte, written by
    scripts/executorch/make_prompts.py), gemma4_e2e_runner the repository prompt itself
    (prompts/text/<task>.txt; the runner applies its own turn template).
    -> dict; raises ValueError naming what to stage when something is missing or disagrees."""
    pte = os.path.expanduser(pte_file)
    if not os.path.isabs(pte):
        pte = os.path.join(model_dir, pte)
    if not os.path.isfile(pte):
        raise ValueError(f"{pte} is not staged (ET_MODEL_DIR={model_dir}; docs/executorch-arm-v1.md)")
    stem = pte[:-len(".pte")] if pte.endswith(".pte") else pte
    recipe_path = stem + ".recipe.json"
    if not os.path.isfile(recipe_path):
        raise ValueError(f"{recipe_path} is missing: the export writes it beside the .pte")
    with open(recipe_path) as fh:
        recipe = json.load(fh)
    problems = executorch_recipe_problems(alias, recipe)
    if problems:
        raise ValueError(f"{os.path.basename(recipe_path)} vs recipe={alias}: " + "; ".join(problems))
    runner = EXECUTORCH_RECIPES[alias]["runner"]
    if executorch_runner_for(pte) != runner:
        raise ValueError(f"{os.path.basename(pte)}: the name's model family runs "
                         f"{executorch_runner_for(pte)!r}, the recipe {runner!r}")
    pte_sha = _sha256(pte)
    if recipe.get("pte_sha256") != pte_sha:
        raise ValueError(f"{os.path.basename(pte)} sha256 {pte_sha} != its recipe.json pte_sha256 "
                         f"{recipe.get('pte_sha256')}")
    tok_named = (recipe.get("tokenizer") or {}).get("file") or ""
    tokenizer = os.path.join(os.path.dirname(pte), os.path.basename(tok_named))
    if not tok_named or not os.path.isfile(tokenizer):
        raise ValueError(f"tokenizer {os.path.basename(tok_named) or '?'} is not staged beside {pte}")
    tokenizer_sha = _sha256(tokenizer)
    if tokenizer_sha != (recipe.get("tokenizer") or {}).get("sha256"):
        raise ValueError(f"{tokenizer} sha256 {tokenizer_sha} != the recipe.json's")
    checkpoint = recipe.get("checkpoint") or {}
    manifest = None
    if runner == "llama_main":
        prompts_dir = stem + ".prompts"
        prompt = os.path.join(prompts_dir, f"{task}.chat.txt")
        listing = os.path.join(prompts_dir, "prompts.json")
        render = (f"<python with transformers> scripts/executorch/make_prompts.py --snapshot "
                  f"{checkpoint.get('snapshot', '<the HF snapshot of the checkpoint>')} --suffix chat "
                  f"--out-dir {prompts_dir}")
        if not (os.path.isfile(prompt) and os.path.isfile(listing)):
            raise ValueError(f"{prompt} is not rendered; stage it with: {render}")
        with open(listing) as fh:
            rendered = json.load(fh)
        entry = (rendered.get("tasks") or {}).get(task) or {}
        if checkpoint.get("revision") and checkpoint["revision"] not in str(rendered.get("snapshot")):
            raise ValueError(f"{listing} was rendered from {rendered.get('snapshot')}, not the "
                             f"checkpoint revision {checkpoint['revision']}; re-render: {render}")
        manifest = {"call": rendered.get("call"), "transformers": rendered.get("transformers"),
                    "snapshot": rendered.get("snapshot"), "hostPromptTokens": entry.get("hostPromptTokens"),
                    "renderedSha256": entry.get("renderedSha256")}
    else:
        prompt = os.path.join(repo_root, "prompts", "text", f"{task}.txt")
    with open(prompt, encoding="utf-8") as fh:
        prompt_text = fh.read()
    prompt_sha = hashlib.sha256(prompt_text.encode()).hexdigest()
    if manifest and manifest["renderedSha256"] != prompt_sha:
        raise ValueError(f"{prompt} sha256 {prompt_sha} != prompts.json renderedSha256 (edited after rendering)")
    with open(recipe_path, "rb") as fh:
        recipe_sha = hashlib.sha256(fh.read()).hexdigest()
    context, context_source = executorch_context_tokens(recipe)
    return {"pte": pte, "pteSha256": pte_sha, "recipePath": recipe_path, "recipeSha256": recipe_sha,
            "recipe": recipe, "alias": alias, "label": EXECUTORCH_RECIPES[alias]["label"],
            "runner": runner, "tokenizer": tokenizer, "tokenizerSha256": tokenizer_sha,
            "prompt": prompt, "promptSha256": prompt_sha, "promptText": prompt_text,
            "promptManifest": manifest, "contextTokens": context, "contextSource": context_source,
            "hfRepo": checkpoint.get("hf_repo"), "hfRevision": checkpoint.get("revision"),
            "exporter": ((recipe.get("exporter") or {}).get("tree_path")
                         or "extension/llm/export/export_llm (" + str(recipe.get("config_yaml_path")) + ")")}


def executorch_record_fields(parsed, inputs, budget, declared_context=None):
    """What an executorch record carries beyond the runner's harness, the same on Android
    and the Mac -> {"metrics", "model", "conditions", "provenance", "text", "flags"}.
    flags = the parser's, plus prompt-token-count-mismatch (llama_main's count against the
    host tokenizer's), output-budget-exceeded, context-budget-exceeded and
    allocation-witness-mismatch (the cell's context-tokens= against the run's allocation)."""
    runner, log, m = parsed["runner"], parsed["log"], dict(parsed["metrics"])
    flags = list(parsed["flags"])
    if runner == "llama_main":
        witness = (log.get("metadata") or {}).get("get_max_context_len")
        context = witness if witness is not None else inputs["contextTokens"]
        context_source = ("runner log (Metadata: get_max_context_len)" if witness is not None
                          else inputs["contextSource"])
        engine_peak = log.get("rssAfterGenerationMiB")
        reply = m.get("generatedTokenCount", 0) + 1 if "generatedTokenCount" in m else None
        host = (inputs.get("promptManifest") or {}).get("hostPromptTokens")
        if host is not None and m.get("promptTokenCount") is not None and host != m["promptTokenCount"]:
            flags.append("prompt-token-count-mismatch")
        chat = ("host chat template: HF apply_chat_template(add_generation_prompt=True), template "
                f"defaults (transformers {(inputs.get('promptManifest') or {}).get('transformers')}, "
                f"{inputs.get('hfRepo')}@{str(inputs.get('hfRevision'))[:12]}); llama_main "
                "--prompt_file, num_bos 0")
        thinking = ("model default: the chat template rendered without enable_thinking (Qwen 3: "
                    "thinking on); reasoning tokens count against the same budget")
    else:
        context, context_source = inputs["contextTokens"], (
            inputs["contextSource"] + "; the .pte has no metadata method (no get_max_context_len): "
            "its KV cache buffers were read as [1, 1, 2048, …] when the export was inspected")
        engine_peak = parsed["stats"].get("memory_peak_mb")
        reply = m.get("generatedTokenCount")
        chat = ("gemma4_e2e_runner's built-in turn template (Gemma4Runner::build_input_ids: BOS, "
                "turn start, 'user\\n', the prompt, turn end, '\\n', turn start, 'model\\n'); "
                "--prompt = prompts/text/<task>.txt")
        thinking = ("the runner's built-in template has no thinking control; reasoning tokens, if "
                    "any, count against the same budget")
    if engine_peak:
        m["memoryPeakEngineReportedMB"] = engine_peak
    if reply is not None and budget and reply > budget:
        flags.append("output-budget-exceeded")
    if context and m.get("promptTokenCount", 0) + (reply or 0) > context:
        flags.append("context-budget-exceeded")
    if declared_context and context and int(declared_context) != int(context):
        flags.append("allocation-witness-mismatch")
    conditions = {"executorchRunner": runner, "sampler": EXECUTORCH_SAMPLER,
                  "maxOutputTokens": budget, "chatMode": chat, "thinkingPolicy": thinking,
                  "cpuThreadsPolicy": "engine heuristic (--cpu_threads -1: cpuinfo "
                                      "get_num_performant_cores)",
                  "contextSource": context_source}
    if context:
        conditions.update(contextBudget=int(context), contextTokens=int(context))
    if "cpuThreads" in log:
        conditions["cpuThreads"] = log["cpuThreads"]
    if runner == "gemma4_e2e_runner":
        conditions["runnerDefaults"] = "--enable_workspace_sharing true (XNNPACK workspace sharing + weight cache)"
    provenance = {"definitions": EXECUTORCH_DEFINITIONS[runner],
                  "recipe": os.path.basename(inputs["recipePath"]), "recipeSha256": inputs["recipeSha256"],
                  "recipeAlias": inputs["alias"], "exporter": inputs["exporter"],
                  "modelProvenance": ("own export with the ExecuTorch tag's own exporter (recipe.json "
                                      "beside the .pte); not a published artifact"),
                  "promptFile": inputs["prompt"] if runner == "gemma4_e2e_runner"
                  else os.path.join(os.path.basename(os.path.dirname(inputs["prompt"])),
                                    os.path.basename(inputs["prompt"])),
                  "promptSha256": inputs["promptSha256"],
                  "tokenizer": os.path.basename(inputs["tokenizer"]),
                  "tokenizerSha256": inputs["tokenizerSha256"],
                  "textExtraction": parsed["textExtraction"]}
    if runner == "gemma4_e2e_runner":
        provenance["promptFile"] = f"prompts/text/{os.path.basename(inputs['prompt'])}"
        provenance["statsReport"] = parsed.get("statsReport")
    else:
        provenance["statsLine"] = parsed.get("statsLine")
        provenance["promptRender"] = inputs.get("promptManifest")
    if parsed["engineErrors"]:
        provenance["engineErrors"] = parsed["engineErrors"]
    model = {"quantization": inputs["label"], "sha256": inputs["pteSha256"],
             "file": os.path.basename(inputs["pte"])}
    if inputs.get("hfRevision"):
        model["hfRevision"] = inputs["hfRevision"]
    return {"metrics": m, "model": model, "conditions": conditions, "provenance": provenance,
            "text": parsed["text"], "flags": flags}
