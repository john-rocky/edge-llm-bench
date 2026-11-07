#!/usr/bin/env python3
"""Runs the windows rows of cells files through a pluggable executor.

The Windows counterpart of scripts/run_mac_matrix.py and android/ddp/run_ddp.py. It plans the
`windows` rows of one or more cells files (matrices/README.md grammar) using android/bench/run_cell.py's
command rules, fetches and SHA256-verifies pinned Windows x64 llama.cpp release assets from
windows/engine-pins.json (a CUDA label's CUDA runtime zip with it), dispatches execution to a pluggable executor (`register_executor`), and
writes schema/result.v1.json records (`<campaign>/<stem>.jsonl` + `decoded/*.decoded.txt`) from the
landed host logs (`<campaign>/<log_subdir>/<invocation>/`).

  scripts/run_windows_matrix.py --fetch-only [--engines-dir D]
  scripts/run_windows_matrix.py <cells...> --campaign <date>-windows --model-dir <id>=<dir>...

Another harness (e.g. a remote Windows RTX lab executor) registers its transport and calls `main`:

  import run_windows_matrix
  run_windows_matrix.register_executor("lab", fn)  # fn(plan, campaign_dir, args) -> int
  sys.exit(run_windows_matrix.main(["--executor", "lab", ...]))
"""

import argparse
import dataclasses
import datetime
import hashlib
import json
import os
import pathlib
import re
import shlex
import sys
import urllib.request
import uuid

REPO = pathlib.Path(__file__).resolve().parents[1]
PINS_PATH = REPO / "windows" / "engine-pins.json"
for _p in (REPO / "scripts", REPO / "android" / "bench"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import bench_common  # noqa: E402
import parsers  # noqa: E402
import run_cell  # noqa: E402
import validate_cells  # noqa: E402

LITERT_EXE = "litert_lm_advanced_main_windows.exe"
HARNESS = "scripts/run_windows_matrix.py"
HARNESS_STAMP = "2026-10-windows-cli-v1"
RSS_BASIS = "PeakWorkingSet64 of the engine process, read every 0.5 s while it runs"
NAMESPACE = uuid.UUID("5d3f8a2e-1c47-4b8e-9a51-7e2c0f6b9d14")
GPU_SUBSTR = "NVIDIA"
ROW_KEYS = {"backend", "context-tokens", "runs", "ynnpack", "local", "file", "exclude", "manual", "adapter"}
# A LiteRT-LM GPU row's adapter= (validate_cells.ADAPTERS) -> what the host is told and what the run's log has to show.
# LiteRT-LM's WebGPU path asks Dawn by a power preference (use_low_power=0, from the GPU priority) and reads no device
# flag, so a row without adapter= runs on the discrete GPU (the run's `Selected adapter:` line has to name NVIDIA,
# GPU_SUBSTR). adapter=igpu runs under Windows' per-app graphics preference GpuPreference=1; on the tool's exe
# (windows/run_job.ps1 sets the value before the run and removes it after), and its line has to say
# adapterType=Integrated GPU. The arm is litert-lm-gpu-<adapter>: the
# same exe and file on another GPU is another cell, never a run of the litert-lm-gpu one.
ADAPTERS = {
    "igpu": {"preference": "GpuPreference=1;", "substr": "Intel", "line": "adapterType=Integrated GPU"},
}
ADAPTER_LINE = "Selected adapter: "
# A llama.cpp row's backend= -> the registry flavor of its release asset, and the tool dir it runs from on the host.
# backend=gpu is the Vulkan asset (the arm llama.cpp-gpu), backend=cuda the CUDA one (llama.cpp-cuda): two arms, so the
# two rows of one model and task land in capture files and cells of their own.
LLAMA_FLAVOR = {"": "cpu", "gpu": "vulkan", "cuda": "cuda"}
LLAMA_TOOL = {"": "llama-cpu", "gpu": "llama-gpu", "cuda": "llama-cuda"}
# The device a GPU row's own `using device` line has to name: Vulkan<n> on the Vulkan asset, CUDA<n> on the CUDA one.
LLAMA_DEVICE_PREFIX = {"gpu": "Vulkan", "cuda": "CUDA"}
ANDROID_FLAGS = ("-t", "-ub", "--device")
UNSAFE = frozenset(' \t"%!^&|<>')
# run_cell's --chat-template-kwargs value for a Gemma 4 GGUF, quoted for sh: on the host one word, quoted for
# cmd.exe and CommandLineToArgvW (no blank, its quotes balanced), the one word exempt from UNSAFE.
THINKING_OFF_SH = shlex.quote('{"enable_thinking":false}')
THINKING_OFF_CMD = r'"{\"enable_thinking\":false}"'
# The KV cache an NPU bundle was exported with, by file (conditions.contextTokens, the form of Android's own bundles:
# "aot-fixed-<n>"). The file's metadata does not state it and the settings echo reads 0; the source is written per row.
NPU_CACHE_TOKENS = {
    # the engine's refusal of a longer prefill on the host: "Exceeding the maximum number of tokens allowed: 4200 >= 4096"
    "gemma-4-E2B-it_intel_PTL.litertlm": 4096,
}


def raw_root() -> pathlib.Path:
    """Where campaigns live: BENCH_RAW_ROOT, else <repo>/results/raw."""
    return pathlib.Path(os.environ.get("BENCH_RAW_ROOT") or REPO / "results" / "raw")


def file_sha256(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclasses.dataclass(frozen=True)
class WinRow:
    """A planned windows row and its edge-llm-bench arm."""

    index: int
    runtime: str
    backend: str
    model_id: str
    task: str
    runs: int
    ctx: int
    ynnpack: bool
    arm: str
    file_opt: str = ""
    adapter: str = ""

    @property
    def row_id(self) -> str:
        return f"r{self.index:02d}"

    @property
    def stem(self) -> str:
        return f"{self.arm}_{self.model_id.replace('/', '_')}_{self.task}"

    @property
    def tool(self) -> str:
        if self.runtime == "litert-lm":
            return "litert"
        return LLAMA_TOOL[self.backend]


@dataclasses.dataclass
class Plan:
    """Planned Windows matrix job: rows, staged model files, llama.cpp labels, and job.json dict."""

    rows: list
    models: dict  # model_key(row) -> (Path, size_bytes)
    labels: dict  # tool -> pinned label
    job: dict


def model_key(row: WinRow) -> str:
    return f"{row.runtime} {row.model_id.lower()} {row.file_opt}".rstrip()


def load_pins(pins_path: pathlib.Path = PINS_PATH) -> dict:
    """windows/engine-pins.json's llama.cpp entries, plus BENCH_EXTRA_PINS's windows_llama.cpp (add-only)."""
    pins = dict(json.loads(pins_path.read_text(encoding="utf-8"))["llama.cpp"])
    extra_path = os.environ.get("BENCH_EXTRA_PINS")
    if extra_path:
        extra = json.loads(pathlib.Path(extra_path).read_text(encoding="utf-8"))
        for label, entry in (extra.get("windows_llama.cpp") or {}).items():
            if label in pins:
                raise SystemExit(f"BENCH_EXTRA_PINS {extra_path}: windows_llama.cpp {label!r} is already "
                                 f"in {pins_path} (the extra registry only adds labels)")
            pins[label] = entry
    return pins


def load_litert_pins(pins_path: pathlib.Path = PINS_PATH) -> dict:
    """windows/engine-pins.json's litert-lm entries, plus BENCH_EXTRA_PINS's windows_litert-lm (add-only)."""
    pins = dict(json.loads(pins_path.read_text(encoding="utf-8")).get("litert-lm") or {})
    extra_path = os.environ.get("BENCH_EXTRA_PINS")
    if extra_path:
        extra = json.loads(pathlib.Path(extra_path).read_text(encoding="utf-8"))
        for label, entry in (extra.get("windows_litert-lm") or {}).items():
            if label in pins:
                raise SystemExit(f"BENCH_EXTRA_PINS {extra_path}: windows_litert-lm {label!r} is already "
                                 f"in {pins_path} (the extra registry only adds labels)")
            pins[label] = entry
    return pins


def pin_assets(pin: dict) -> list:
    """The release assets a llama.cpp label stages, its own zip first: a CUDA label names the release's CUDA runtime
    zip (`cudart`: the CUDA runtime and cuBLAS DLLs its CUDA backend loads) beside it, expanded into the same dir."""
    return [pin] + ([pin["cudart"]] if pin.get("cudart") else [])


def llama_files(pin: dict) -> dict:
    """{file name: sha256} of the files of a label the witness reads on the host: llama-cli.exe and its dll_files."""
    return {"llama-cli.exe": pin["llama_cli_sha256"], **(pin.get("dll_files") or {})}


def pinned_label(pins: dict, backend: str) -> str:
    flavor = LLAMA_FLAVOR[backend]
    labels = [k for k, v in pins.items() if v.get("flavor") == flavor]
    if len(labels) != 1:
        raise ValueError(f"windows/engine-pins.json: want one {flavor} label, got {labels}")
    return labels[0]


def fetch_engines(engines_dir: pathlib.Path, pins: dict, labels: list, dry_run: bool = False,
                  fetch=urllib.request.urlretrieve) -> dict:
    """Download and verify pinned Windows llama.cpp zip assets (pin_assets: a CUDA label's runtime zip as well) into
    <engines_dir>/llama-<label>/; a dir with an asset missing or mismatching moves aside. -> {label: [zip paths]}"""

    def matches(p: pathlib.Path, asset: dict) -> bool:
        return p.is_file() and p.stat().st_size == asset["size"] and file_sha256(p) == asset["sha256"]

    out = {}
    for label in labels:
        assets = pin_assets(pins[label])
        dests = out[label] = [engines_dir / f"llama-{label}" / a["artifact"] for a in assets]
        if dry_run or all(matches(d, a) for d, a in zip(dests, assets)):
            for dest, asset in zip(dests, assets):
                print(f"  llama.cpp {label}: {dest} ({asset['sha256'][:12]})")
            continue
        folder = dests[0].parent
        if folder.exists():
            stamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S%f")
            aside = folder.with_name(f"{folder.name}.unverified-{stamp}")
            print(f"  llama.cpp {label}: moving {folder} aside to {aside}")
            folder.rename(aside)
        folder.mkdir(parents=True)
        for dest, asset in zip(dests, assets):
            tmp = dest.with_name(dest.name + ".download")
            fetch(asset["url"], str(tmp))
            if not matches(tmp, asset):
                tmp.unlink(missing_ok=True)
                raise ValueError(f"llama.cpp {label}: {asset['url']} did not match its pin")
            tmp.rename(dest)
    return out


def load_rows(cells_files: list, engines: list | None = None) -> list:
    """Parse and check windows rows from one or more cells files."""
    rows, problems = [], []
    for cells in cells_files:
        for lineno, raw in enumerate(pathlib.Path(cells).read_text(encoding="utf-8").splitlines(), 1):
            line = raw.split("#", 1)[0].strip()
            if not line:
                continue
            plat, rt, mid, task, opts = validate_cells.parse_line(line)
            if plat != "windows" or opts.get("manual") == "1" or opts.get("exclude"):
                continue
            if engines and not any(rt.startswith(e) for e in engines):
                continue
            where = f"{cells}:{lineno} (windows {rt} {mid} {task})"
            backend = opts.get("backend", "")
            ctx = opts.get("context-tokens", "")
            ynnpack = opts.get("ynnpack") == "1"
            adapter = opts.get("adapter", "")
            if set(opts) - ROW_KEYS:
                problems.append(f"{where}: unsupported option(s): {sorted(set(opts) - ROW_KEYS)}")
            if rt == "litert-lm":
                if backend not in ("cpu", "gpu", "npu"):
                    problems.append(f"{where}: litert-lm needs backend=cpu|gpu|npu")
            elif rt == "llama.cpp":
                if backend not in LLAMA_FLAVOR:
                    problems.append(f"{where}: llama.cpp takes no backend= (CPU), backend=gpu (Vulkan) or backend=cuda")
            else:
                problems.append(f"{where}: runtime must be litert-lm or llama.cpp")
            if task.startswith(("native-", "endurance-")):
                problems.append(f"{where}: only prompt tasks are supported on windows")
            if backend == "npu":
                if ctx:
                    problems.append(f"{where}: no context-tokens= on the NPU (a bundle's cache is fixed at export)")
                if not opts.get("file"):
                    problems.append(f"{where}: the NPU row needs file=<the bundle of this SoC>")
            elif not ctx.isdigit():
                problems.append(f"{where}: needs context-tokens=")
            if ynnpack and (rt, backend) != ("litert-lm", "cpu"):
                problems.append(f"{where}: ynnpack=1 is for litert-lm backend=cpu rows only")
            if adapter and ((rt, backend) != ("litert-lm", "gpu") or adapter not in ADAPTERS):
                problems.append(f"{where}: adapter= is {'|'.join(sorted(ADAPTERS))} on a litert-lm backend=gpu row only")
            arm = run_cell.arm_name(rt, backend or None, ynnpack) + (f"-{adapter}" if adapter else "")
            runs = int(opts.get("runs", "3"))
            rows.append(WinRow(len(rows), rt, backend, mid, task, runs, int(ctx or 0),
                               ynnpack, arm, opts.get("file", ""), adapter))
    seen = {}
    for row in rows:
        if row.stem in seen:
            problems.append(f"{row.stem}: two rows of one arm, model and task (files {seen[row.stem]!r} and "
                            f"{row.file_opt!r}) would share a capture file and pool in one cell")
        seen.setdefault(row.stem, row.file_opt)
    if problems:
        raise ValueError("; ".join(problems))
    return rows


def prompt_file(task: str) -> pathlib.Path:
    return REPO / "prompts" / "text" / f"{task}.txt"


def task_budget(task: str) -> int:
    tsv = REPO / "prompts" / "text" / "budgets.tsv"
    for line in tsv.read_text(encoding="utf-8").splitlines():
        words = line.split("\t")
        if words[0] == task:
            return int(words[1])
    raise ValueError(f"task {task}: no budget in {tsv}")


def lab_args(row: WinRow, model_filename: str, budget: int, gpu_substr: str = GPU_SUBSTR) -> list:
    """run_cell.engine_command's argv for a Windows row, less Android-specific flags. The CUDA row takes the GPU
    row's line (every layer on the device, flash attention on): the --device it names is an Android device and is
    dropped here, and each release asset loads one GPU backend, so both GPU rows run the same words on their own asset."""
    cmd = run_cell.engine_command(
        row.runtime,
        ("gpu" if row.backend == "cuda" else row.backend) or None,
        f"{{model:{model_filename}}}",
        row.task,
        f"{{job}}\\prompts\\{row.task}.txt",
        budget,
        None,
        row.ctx or None,
        engine_dir="E",
        ynnpack=row.ynnpack,
    )[0]
    words, out = cmd.replace(THINKING_OFF_SH, THINKING_OFF_CMD).split()[1:], []
    while words:
        word = words.pop(0)
        if row.runtime == "llama.cpp" and word in ANDROID_FLAGS:
            words.pop(0)
        else:
            out.append(word)
    if (row.runtime, row.backend) == ("litert-lm", "gpu"):
        # the flag reaches no adapter choice at this tag (ADAPTERS); each row still names the GPU it asks for
        out.append(f"--preferred_device_substr={ADAPTERS[row.adapter]['substr'] if row.adapter else gpu_substr}")
    if row.arm == "litert-lm-npu":
        # run_cell's NPU line carries a Qualcomm setting and a phone's dispatch dir: on the Intel dispatch the
        # engine's defaults (Google's page runs none of its NPU flags), the dispatch DLL beside the tool, and the
        # two iterations of the cpu / gpu rows, so that all three arms read the same regimes
        out = [w for w in out if not w.startswith(("--use_hw_cache_update_for_npu=", "--litert_dispatch_lib_dir="))]
        out += ["--litert_dispatch_lib_dir={tool_dir}", "--num_iterations=2", "--use_session=false"]
    for a in out:
        if a != THINKING_OFF_CMD and UNSAFE & set(a):
            raise ValueError(f"{row.stem}: {a!r} contains a cmd.exe metacharacter")
    return out


def parse_model_specs(specs: list) -> dict:
    """`--model-file [<runtime>:]<model_id>=<path>[:<size>]` -> {(rt_or_empty, mid.lower()): (Path, size)},
    and {(rt_or_empty, mid.lower(), file name): (Path, size)} for a row that names its file=. An id given
    several files has no plain entry (None): each of its rows has to name one."""
    out = {}
    for item in specs or []:
        lhs, sep, rhs = item.partition("=")
        if not sep or not lhs or not rhs:
            raise ValueError(f"--model-file {item!r}: want [<runtime>:]<model_id>=<path>[:<size>]")
        if ":" in lhs and lhs.split(":", 1)[0] in ("litert-lm", "llama.cpp"):
            rt, mid = lhs.split(":", 1)
        else:
            rt, mid = "", lhs
        size = None
        if ":" in rhs and rhs.rsplit(":", 1)[1].isdigit():
            rhs, size_s = rhs.rsplit(":", 1)
            size = int(size_s)
        path = pathlib.Path(rhs).expanduser()
        if size is None and path.is_file():
            size = path.stat().st_size
        out[(rt, mid.lower(), path.name)] = (path, size)
        plain = (rt, mid.lower())
        out[plain] = None if plain in out and out[plain] != (path, size) else (path, size)
    return out


def resolve_model(row: WinRow, model_specs: dict) -> tuple:
    mid = row.model_id.lower()
    hit = None
    if row.file_opt:
        hit = model_specs.get((row.runtime, mid, row.file_opt)) or model_specs.get(("", mid, row.file_opt))
    hit = hit or model_specs.get((row.runtime, mid)) or model_specs.get(("", mid))
    if hit is None:
        name = row.file_opt or "<path>"
        raise ValueError(f"{row.runtime} {row.model_id}: pass --model-file {row.model_id}={name}")
    path, size = hit
    if size is None:
        if not path.is_file():
            raise ValueError(f"{path}: file does not exist and no :<size> was given")
        size = path.stat().st_size
    return path, size


def plan_job(cells_files: list, campaign: str, pins: dict, model_specs: dict,
             engines: list | None = None, run_timeout_s: int = 1800) -> Plan:
    rows = load_rows(cells_files, engines)
    models, labels, launches = {}, {}, []
    for row in rows:
        key = model_key(row)
        if key not in models:
            models[key] = resolve_model(row, model_specs)
        if row.runtime == "llama.cpp":
            labels[row.tool] = pinned_label(pins, row.backend)
        budget = task_budget(row.task)
        launch = {
            "id": row.row_id,
            "stem": row.stem,
            "tool": row.tool,
            "runs": row.runs,
            "args": lab_args(row, models[key][0].name, budget),
        }
        if (row.runtime, row.backend) == ("litert-lm", "gpu"):
            # run_job.ps1: the adapter the run asks for ("" = the engine's own choice), the per-app preference that
            # gets it there, and the model file whose GPU caches the run reads or writes (the caches carry no adapter
            # in their names, so the job removes them when the adapter changes)
            launch.update(adapter=row.adapter, modelFile=models[key][0].name)
            if row.adapter:
                launch["gpuPreference"] = ADAPTERS[row.adapter]["preference"]
        launches.append(launch)
    job = {
        "campaign": campaign,
        "runTimeoutSeconds": run_timeout_s,
        "models": [{"name": p.name, "bytes": s, "parts": []} for p, s in models.values()],
        "engines": {t: pins[lb]["artifact"] for t, lb in labels.items()},
        "launches": launches,
    }
    return Plan(rows, models, labels, job)


def read_json(path: pathlib.Path) -> dict:
    """Read UTF-8 or UTF-8-BOM JSON written by PowerShell 5.1, or {} if missing."""
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


_ISO_TS = re.compile(
    r"^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})(?:\.\d+)?(?:Z|z|([+-])(\d{2}):?(\d{2}))?$"
)


def utc_timestamp(text: str) -> str | None:
    """ISO-8601 timestamp (including PowerShell Get-Date -Format o's 7 fractional digits and local
    offset) -> YYYY-MM-DDTHH:MM:SSZ in UTC."""
    m = _ISO_TS.match((text or "").strip())
    if not m:
        return None
    date_s, time_s, sign, off_h, off_m = m.groups()
    dt = datetime.datetime.strptime(f"{date_s}T{time_s}", "%Y-%m-%dT%H:%M:%S")
    if sign:
        delta = datetime.timedelta(hours=int(off_h), minutes=int(off_m))
        tz = datetime.timezone(delta if sign == "+" else -delta)
    else:
        tz = datetime.timezone.utc
    return dt.replace(tzinfo=tz).astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def catalog_quantization(runtime: str, model_id: str, extra_catalog: str | None = None,
                         model_file: str | pathlib.Path = "") -> str:
    """Quantization string from BENCH_EXTRA_CATALOG when present, else run_cell.guess_quant."""
    path = extra_catalog or os.environ.get("BENCH_EXTRA_CATALOG")
    if path and pathlib.Path(path).is_file():
        data = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
        for entry in data.get(runtime, []):
            if isinstance(entry, dict) and entry.get("id", "").lower() == model_id.lower():
                if entry.get("quantization"):
                    return entry["quantization"]
    return run_cell.guess_quant(str(model_file))


def engine_threads(console: str):
    """The CPU thread count the launch's log states (LiteRT-LM's settings echo, llama-cli at -lv 4), else the fact that
    no flag set one. Rows pass no thread flag, so each engine runs its default (windows/README.md)."""
    m = re.search(r"^number_of_threads: (\d+)", console, re.M) or re.search(r"\bn_threads = (\d+)", console)
    return int(m.group(1)) if m else "engine default"


def _launch_fields(row: WinRow, console: str, ctx: dict, gpu_substr: str = GPU_SUBSTR):
    if row.arm == "litert-lm-npu":
        # The settings echo reads max_tokens: 0 on a bundle (its cache is fixed at export), so there is no
        # allocation to hold the launch to: the budget flag stays, the two allocation flags do not apply.
        samples, cond = parsers.context_prompt_results(console, 0, ctx["budget"])
        cond["protocolFlags"] = [f for f in cond["protocolFlags"]
                                 if f != "allocation-witness-mismatch" and not f.endswith("-context-budget-exceeded")]
        lines = parsers.litert_npu_lines(console)
        cond["backendRegistered"] = lines
        samples = list(samples) + [{}] * max(0, 2 - len(samples))
        return samples, cond, parsers.context_prompt_texts(console), not parsers.litert_npu_registered(lines)
    if row.runtime == "litert-lm":
        samples, cond = parsers.context_prompt_results(console, row.ctx, ctx["budget"])
        lines = parsers.litert_side_lines(console)
        counts = parsers.ynnpack_counts(console)
        cond["backendRegistered"] = lines
        if row.backend == "cpu":
            cond.update(enableYnnpack=row.ynnpack, ynnpackLines=counts)
        off = parsers.litert_side_off_device(lines, row.backend, row.ynnpack, counts)
        if row.backend == "gpu":
            cond["gpuAccelerator"], cond["gpuAcceleratorLine"] = parsers.litert_gpu_accelerator(console)
            adapters = [ln for ln in lines if ln.startswith(ADAPTER_LINE)]
            # the GPU the run ran on is the one its log selected (the cell's adapter= only asks for it)
            cond["gpuAdapter"] = adapters[-1][len(ADAPTER_LINE):] if adapters else None
            if row.adapter and not adapters:
                off = off or f"no {ADAPTER_LINE.strip()} line in the log (the row asks for adapter={row.adapter})"
            elif adapters and (ADAPTERS[row.adapter]["line"] if row.adapter else gpu_substr) not in adapters[-1]:
                off = off or adapters[-1]
        if off:
            cond["backendOffReason"] = off
        samples = list(samples) + [{}] * max(0, 2 - len(samples))
        return samples, cond, parsers.context_prompt_texts(console), bool(off)
    invalid = console.lower().count("invalid decode")
    cond = {
        "invalidDecodeCount": invalid,
        "protocolFlags": ["invalid-decode"] if invalid else [],
        **run_cell.llama_chat_conditions(ctx["model"]),
    }
    texts = [parsers.llama_cli_reply(console, ctx["prompt"])]
    off = False
    if row.backend:
        lines = parsers.llama_backend_lines(console)
        used = [ln.split(": using device ")[1] for ln in lines
                if ": using device " in ln and gpu_substr in ln
                and ln.split(": using device ")[1].startswith(LLAMA_DEVICE_PREFIX[row.backend])]
        device = used[0].split(" (")[0] if used else None
        cond.update(ggmlDevice=device, nGpuLayers=99, flashAttn="on", backendRegistered=lines)
        off = device is None or not parsers.llama_backend_registered(lines, device, device, "llama-cli")
    samples = [parsers.parse_llama_cli(console)]
    return samples, cond, texts, off


def write_records(plan: Plan, campaign_dir: pathlib.Path, invocation: str, *,
                  litert_label: str = "unknown", pins: dict | None = None,
                  litert_pins: dict | None = None, extra_catalog: str | None = None,
                  default_model: str = "Windows PC", harness: str = HARNESS,
                  log_subdir: str = "host-logs") -> tuple:
    """Write schema/result.v1.json `<campaign_dir>/<stem>.jsonl` from `<log_subdir>/<invocation>/`."""
    logs = campaign_dir / log_subdir / invocation
    host = read_json(logs / "host.json")
    shas = host.get("binaries") or {}
    device = {
        "systemName": "Windows",
        "modelIdentifier": host.get("model") or default_model,
        "systemVersion": host.get("os"),
        "chip": host.get("cpu"),
        "gpu": [g.get("name") for g in host.get("gpus") or []],
        "physicalMemoryMB": (host.get("memoryBytes") or 0) // 2**20,
        "batteryState": host.get("batteryState") or "unknown",
    }
    if host.get("batteryLevel") is not None:
        device["batteryLevel"] = host["batteryLevel"]
    pins = pins if pins is not None else load_pins()
    litert_pins = litert_pins if litert_pins is not None else load_litert_pins()
    checking = os.environ.get("BENCH_TEXT_CHECK", "1") == "1"
    built, clean, total = set(), 0, 0
    (campaign_dir / "decoded").mkdir(parents=True, exist_ok=True)
    for row in plan.rows:
        path, size = plan.models[model_key(row)]
        quant = catalog_quantization(row.runtime, row.model_id, extra_catalog, path.name)
        if row.runtime == "litert-lm":
            build = version = litert_label
            lpin = litert_pins.get(build)
            if lpin is None:
                version = f"unknown ({LITERT_EXE} label {build!r} not in windows/engine-pins.json)"
            else:
                version = lpin.get("engine_version") or build
                want = dict(lpin.get("dll_files") or {})
                want[LITERT_EXE] = lpin.get("litert_lm_advanced_main_windows_sha256") or lpin.get("sha256")
                bad = sorted(
                    n for n, sha in want.items()
                    if (shas.get(n) if n == LITERT_EXE else shas.get(f"litert/{n}", shas.get(n))) != sha
                )
                if bad:
                    version = f"unknown ({', '.join(bad)} unmatched in {build})"
            artifact = f"{LITERT_EXE} sha256:{shas.get(LITERT_EXE)}"
        else:
            build = version = pinned_label(pins, row.backend)
            want = llama_files(pins[build])
            bad = sorted(n for n, sha in want.items() if shas.get(f"{row.tool}/{n}") != sha)
            if bad:
                version = f"unknown ({', '.join(bad)} unmatched in {build})"
            artifact = f"llama-cli.exe sha256:{shas.get(row.tool + '/llama-cli.exe')}"
        ctx = {
            "budget": task_budget(row.task),
            "prompt": prompt_file(row.task).read_text(encoding="utf-8"),
            "model": path.name,
        }
        prompt_ver = run_cell.prompt_version(row.task)
        key = (row.arm, path.name, row.ctx)
        for run_idx in range(1, row.runs + 1):
            name = f"{row.row_id}_run{run_idx}"
            meta = read_json(logs / f"{name}.json")
            if not meta:
                print(f"  {row.stem} run {run_idx}: not run on the host")
                continue
            log_file = logs / f"{name}.log"
            console = log_file.read_text(errors="replace") if log_file.is_file() else ""
            samples, checks, texts, off = _launch_fields(row, console, ctx)
            exit_code, timed_out = meta.get("exitCode"), bool(meta.get("timedOut"))
            flags = list(checks.get("protocolFlags") or [])
            if timed_out:
                flags.append("engine-timeout")
            elif exit_code != 0:
                flags.append(f"engine-exit-{exit_code}")
            want_pref = ADAPTERS[row.adapter]["preference"] if row.adapter else None
            if want_pref and meta.get("gpuPreference") != want_pref:
                # a job script that set no preference (or another one) ran this row on whatever GPU it got: not a
                # run of the cell, kept out of every pool as a run on another adapter is (backend-not-registered)
                flags.append("gpu-preference-not-applied")
                checks.setdefault("backendOffReason", f"no {want_pref} on the tool for the run (the job read back "
                                                     f"{meta.get('gpuPreference')!r})")
                off = True
            if meta.get("gpuCacheWrite"):
                # the job found no GPU cache of the file before this run (removed at the job's start, or when the
                # adapter changed): this run compiled and wrote them, whatever ran before it
                built.discard(key)
            first_ever = key not in built and (row.runtime == "litert-lm" or bool(row.backend))
            paired = row.runtime == "litert-lm"
            start = str(meta.get("start") or "")
            # The label of the content the run loaded: a Hub file replaced in place under the same name (the
            # litert-community Qwen3 files of 2026-10-31) takes the replacement's label from its date on, by the
            # correction the summary applies (bench_common.REPLACED_FILE_LABELS)
            run_quant = bench_common.corrected_quant(row.arm, row.model_id, quant, {
                "platform": "windows", "timestamp": utc_timestamp(start) or "", "model_file": path.name})[0]
            peak = meta.get("peakWorkingSetBytes")
            text_failed = False
            with open(campaign_dir / f"{row.stem}.jsonl", "a", encoding="utf-8") as fh:
                for i, sample in enumerate(samples, 1):
                    value = texts[i - 1] if i <= len(texts) else ""
                    metrics = {"harnessStamp": HARNESS_STAMP, **sample, "coldRun": i == 1}
                    if isinstance(peak, int) and peak > 0:
                        metrics["memoryPeakResidentMB"] = peak / 2**20
                    if first_ever and i == 1:
                        metrics["firstEver"] = True
                    pflags = list(flags)
                    cond = {
                        **checks,
                        "sampler": "engine-default" if paired else "greedy",
                        "threads": engine_threads(console),
                        "contextTokens": row.ctx or (
                            f"aot-fixed-{NPU_CACHE_TOKENS[path.name]}" if path.name in NPU_CACHE_TOKENS
                            else "aot-fixed (cache length unrecorded)"),
                        "outputTokenBudget": ctx["budget"],
                        "elapsedSeconds": meta.get("elapsedSeconds"),
                        "exitCode": None if timed_out else exit_code,
                        "engineBuild": build,
                        "engineCommand": meta.get("command"),
                        "launchID": str(uuid.uuid5(NAMESPACE, f"{invocation}/{name}")),
                        "iterationIndex": i,
                        "regime": ("cold" if i == 1 else "warm") if paired else "cold-process",
                        "protocolFlags": pflags,
                    }
                    if (row.runtime, row.backend) == ("litert-lm", "gpu"):
                        # the per-app value the run ran under (None: none), as the job script read it back
                        cond["gpuPreference"] = meta.get("gpuPreference")
                        if meta.get("gpuCachePurge"):
                            cond["gpuCachePurge"] = meta["gpuCachePurge"]
                    if meta.get("before"):
                        cond["hostBefore"] = meta["before"]
                    if meta.get("after"):
                        cond["hostAfter"] = meta["after"]
                    for key in ("sshConnections", "hostCpu"):
                        # two reads of the host around the whole engine process (run_job.ps1 since 2026-11-07),
                        # the same in each of its iterations: recorded as the job read them, never judged here
                        if key in meta:
                            cond[key] = meta[key]
                    if prompt_ver:
                        cond["promptVersion"] = prompt_ver
                    if checking:
                        verdict = parsers.text_integrity(value)
                        pflags.extend(verdict["flags"])
                        text_failed |= bool(verdict["flags"])
                        cond["textCheck"] = verdict
                        cond["textOutputSHA256"] = hashlib.sha256(value.encode()).hexdigest()
                    if off:
                        pflags.append("backend-not-registered")
                    text_rel = f"decoded/{row.stem}_run{run_idx}_iter{i}.decoded.txt"
                    (campaign_dir / text_rel).write_text(value, encoding="utf-8")
                    fh.write(json.dumps({
                        "schemaVersion": 1,
                        "id": str(uuid.uuid5(NAMESPACE, f"{invocation}/{name}/{i}")),
                        "runtime": row.arm,
                        "engineVersion": version,
                        "engineArtifact": artifact,
                        "model": {
                            "id": row.model_id,
                            "quantization": run_quant,
                            "file": path.name,
                            "onDiskSizeBytes": size,
                        },
                        "task": row.task,
                        "timestamp": utc_timestamp(start),
                        "device": device,
                        "conditions": cond,
                        "metrics": metrics,
                        "outputSample": value[:200],
                        "provenance": {
                            "rawLog": f"{log_subdir}/{invocation}/{name}.log",
                            "decodedText": text_rel,
                            "harness": harness,
                            "rssBasis": RSS_BASIS,
                        },
                    }) + "\n")
            ok = bool(exit_code == 0 and not timed_out and not flags and not off
                      and not text_failed and samples[0].get("decodeTokensPerSecond"))
            if ok:
                built.add(key)
            clean, total = clean + ok, total + 1
            print(f"  {row.stem} run {run_idx}/{row.runs} {'OK' if ok else 'FAIL'}")
    return clean, total


def run_unconfigured(plan: Plan, campaign_dir: pathlib.Path, args) -> int:
    del plan, campaign_dir
    if args.dry_run:
        return 0
    print("run_windows_matrix: no local Windows host runner configured; register an executor "
          "(e.g. --executor lab)", file=sys.stderr)
    return 2


EXECUTORS = {"local": run_unconfigured}


def register_executor(name: str, fn) -> None:
    """Register `fn(plan, campaign_dir, args) -> exit_status`."""
    EXECUTORS[name] = fn


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cells", nargs="*", type=pathlib.Path, help="cells files; their windows rows run")
    ap.add_argument("--fetch-only", action="store_true", help="only download and verify pinned llama.cpp zips")
    ap.add_argument("--engines-dir", type=pathlib.Path,
                    default=pathlib.Path(os.environ.get("BENCH_WINDOWS_BIN_DIR") or REPO / "windows" / "bin"))
    ap.add_argument("--campaign", help="campaign dir name (default: <date>-windows)")
    ap.add_argument("--executor", default="local", choices=sorted(EXECUTORS))
    ap.add_argument("--engines", default="all", help="comma list of runtime prefixes to run")
    ap.add_argument("--model-file", action="append", default=[], metavar="[RT:]ID=PATH[:SIZE]",
                    help="staged model file path (repeatable)")
    ap.add_argument("--litert-label", default="unknown", help="engineVersion label for LiteRT-LM rows")
    ap.add_argument("--extra-catalog", default=os.environ.get("BENCH_EXTRA_CATALOG") or None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    pins = load_pins()
    if args.fetch_only:
        try:
            fetch_engines(args.engines_dir, pins, sorted(pins), args.dry_run)
        except (ValueError, OSError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        return 0

    if not args.cells:
        ap.error("cells files required unless --fetch-only is set")
    for c in args.cells:
        if not c.is_file():
            ap.error(f"{c}: no such cells file")

    engines = None if args.engines == "all" else [e.strip() for e in args.engines.split(",") if e.strip()]
    campaign = args.campaign or os.environ.get("CAMPAIGN") or f"{datetime.date.today().isoformat()}-windows"
    try:
        specs = parse_model_specs(args.model_file)
        plan = plan_job(args.cells, campaign, pins, specs, engines)
    except (ValueError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    campaign_dir = raw_root() / campaign
    print(f"== [Windows] {len(plan.rows)} rows -> {campaign_dir}")
    for row in plan.rows:
        print(f"   {row.row_id} {row.arm} {row.model_id} {row.task} x{row.runs}")
    if not plan.rows:
        return 0
    return EXECUTORS[args.executor](plan, campaign_dir, args)


if __name__ == "__main__":
    sys.exit(main())
