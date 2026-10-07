"""Parsers for the Android engine CLIs' console output.

Formats verified against the v0.16.0 sources (runtime/framework/io_types.cc
BenchmarkInfo operator<<) and llama.cpp b8999. Absent metrics stay absent —
never derived, never defaulted (a fabricated field is worse than a hole).
"""
import json
import math
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
