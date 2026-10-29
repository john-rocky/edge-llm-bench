#!/usr/bin/env python3
"""Runs the windows rows of cells files through a pluggable executor.

The Windows counterpart of scripts/run_mac_matrix.py and android/ddp/run_ddp.py. It plans the
`windows` rows of one or more cells files (matrices/README.md grammar) using android/bench/run_cell.py's
command rules, fetches and SHA256-verifies pinned Windows x64 llama.cpp release assets from
windows/engine-pins.json, dispatches execution to a pluggable executor (`register_executor`), and
writes schema/result.v1.json records (`<campaign>/<stem>.jsonl` + `decoded/*.decoded.txt`) from the
landed host logs (`<campaign>/<log_subdir>/<invocation>/`).

  scripts/run_windows_matrix.py --fetch-only [--engines-dir D]
  scripts/run_windows_matrix.py <cells...> --campaign <date>-windows --model-dir <id>=<dir>...

Another harness (e.g. an OmniLab Windows RTX executor) registers its transport and calls `main`:

  import run_windows_matrix
  run_windows_matrix.register_executor("omnilab", fn)  # fn(plan, campaign_dir, args) -> (rc, invocation)
  sys.exit(run_windows_matrix.main(["--executor", "omnilab", ...]))
"""

import argparse
import dataclasses
import datetime
import hashlib
import json
import os
import pathlib
import sys
import urllib.request
import uuid

REPO = pathlib.Path(__file__).resolve().parents[1]
PINS_PATH = REPO / "windows" / "engine-pins.json"
for _p in (REPO / "scripts", REPO / "android" / "bench"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import parsers  # noqa: E402
import run_cell  # noqa: E402
import validate_cells  # noqa: E402

LITERT_EXE = "litert_lm_advanced_main_windows.exe"
HARNESS = "scripts/run_windows_matrix.py"
HARNESS_STAMP = "2026-10-windows-cli-v1"
RSS_BASIS = "PeakWorkingSet64 of the engine process, read every 0.5 s while it runs"
NAMESPACE = uuid.UUID("5d3f8a2e-1c47-4b8e-9a51-7e2c0f6b9d14")
GPU_SUBSTR = "NVIDIA"
ROW_KEYS = {"backend", "context-tokens", "runs", "ynnpack", "local", "file", "exclude", "manual"}
LLAMA_FLAVOR = {"": "cpu", "gpu": "vulkan"}
ANDROID_FLAGS = ("-t", "-ub", "--device")
UNSAFE = frozenset(' \t"%!^&|<>')


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
        return "llama-gpu" if self.backend else "llama-cpu"


@dataclasses.dataclass
class Plan:
    """Planned Windows matrix job: rows, staged model files, llama.cpp labels, and job.json dict."""

    rows: list
    models: dict  # model_key(row) -> (Path, size_bytes)
    labels: dict  # tool -> pinned label
    job: dict


def model_key(row: WinRow) -> str:
    return f"{row.runtime} {row.model_id.lower()}"


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


def pinned_label(pins: dict, backend: str) -> str:
    flavor = LLAMA_FLAVOR[backend]
    labels = [k for k, v in pins.items() if v.get("flavor") == flavor]
    if len(labels) != 1:
        raise ValueError(f"windows/engine-pins.json: want one {flavor} label, got {labels}")
    return labels[0]


def fetch_engines(engines_dir: pathlib.Path, pins: dict, labels: list, dry_run: bool = False,
                  fetch=urllib.request.urlretrieve) -> dict:
    """Download and verify pinned Windows llama.cpp zip assets; mismatching dirs move aside."""

    def matches(p: pathlib.Path, pin: dict) -> bool:
        return p.is_file() and p.stat().st_size == pin["size"] and file_sha256(p) == pin["sha256"]

    out = {}
    for label in labels:
        pin = pins[label]
        dest = out[label] = engines_dir / f"llama-{label}" / pin["artifact"]
        if dry_run or matches(dest, pin):
            print(f"  llama.cpp {label}: {dest} ({pin['sha256'][:12]})")
            continue
        if dest.parent.exists():
            stamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S%f")
            aside = dest.parent.with_name(f"{dest.parent.name}.unverified-{stamp}")
            print(f"  llama.cpp {label}: moving {dest.parent} aside to {aside}")
            dest.parent.rename(aside)
        dest.parent.mkdir(parents=True)
        tmp = dest.with_name(dest.name + ".download")
        fetch(pin["url"], str(tmp))
        if not matches(tmp, pin):
            tmp.unlink(missing_ok=True)
            raise ValueError(f"llama.cpp {label}: {pin['url']} did not match its pin")
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
            if set(opts) - ROW_KEYS:
                problems.append(f"{where}: unsupported option(s): {sorted(set(opts) - ROW_KEYS)}")
            if rt == "litert-lm":
                if backend not in ("cpu", "gpu"):
                    problems.append(f"{where}: litert-lm needs backend=cpu|gpu")
            elif rt == "llama.cpp":
                if backend not in LLAMA_FLAVOR:
                    problems.append(f"{where}: llama.cpp takes no backend= (CPU) or backend=gpu")
            else:
                problems.append(f"{where}: runtime must be litert-lm or llama.cpp")
            if task.startswith(("native-", "endurance-")):
                problems.append(f"{where}: only prompt tasks are supported on windows")
            if not ctx.isdigit():
                problems.append(f"{where}: needs context-tokens=")
            if ynnpack and (rt, backend) != ("litert-lm", "cpu"):
                problems.append(f"{where}: ynnpack=1 is for litert-lm backend=cpu rows only")
            arm = run_cell.arm_name(rt, backend or None, ynnpack)
            runs = int(opts.get("runs", "3"))
            rows.append(WinRow(len(rows), rt, backend, mid, task, runs, int(ctx or 0),
                               ynnpack, arm, opts.get("file", "")))
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
    """run_cell.engine_command's argv for a Windows row, less Android-specific flags."""
    cmd = run_cell.engine_command(
        row.runtime,
        row.backend or None,
        f"{{model:{model_filename}}}",
        row.task,
        f"{{job}}\\prompts\\{row.task}.txt",
        budget,
        None,
        row.ctx,
        engine_dir="E",
        ynnpack=row.ynnpack,
    )[0]
    words, out = cmd.split()[1:], []
    while words:
        word = words.pop(0)
        if row.runtime == "llama.cpp" and word in ANDROID_FLAGS:
            words.pop(0)
        else:
            out.append(word)
    if row.arm == "litert-lm-gpu":
        out.append(f"--preferred_device_substr={gpu_substr}")
    for a in out:
        if UNSAFE & set(a):
            raise ValueError(f"{row.stem}: {a!r} contains a cmd.exe metacharacter")
    return out


def parse_model_specs(specs: list) -> dict:
    """`--model-file [<runtime>:]<model_id>=<path>[:<size>]` -> {(rt_or_empty, mid.lower()): (Path, size)}."""
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
        out[(rt, mid.lower())] = (path, size)
    return out


def resolve_model(row: WinRow, model_specs: dict) -> tuple:
    hit = model_specs.get((row.runtime, row.model_id.lower())) or model_specs.get(("", row.model_id.lower()))
    if hit is None:
        raise ValueError(f"{row.runtime} {row.model_id}: pass --model-file {row.model_id}=<path>")
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
        launches.append({
            "id": row.row_id,
            "stem": row.stem,
            "tool": row.tool,
            "runs": row.runs,
            "args": lab_args(row, models[key][0].name, budget),
        })
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


def catalog_quantization(runtime: str, model_id: str, extra_catalog: str | None = None) -> str:
    """Quantization string from BENCH_EXTRA_CATALOG when present, else 'unknown'."""
    path = extra_catalog or os.environ.get("BENCH_EXTRA_CATALOG")
    if path and pathlib.Path(path).is_file():
        data = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
        for entry in data.get(runtime, []):
            if isinstance(entry, dict) and entry.get("id", "").lower() == model_id.lower():
                if entry.get("quantization"):
                    return entry["quantization"]
    return "unknown"


def _launch_fields(row: WinRow, console: str, ctx: dict, gpu_substr: str = GPU_SUBSTR):
    if row.runtime == "litert-lm":
        samples, cond = parsers.context_prompt_results(console, row.ctx, ctx["budget"])
        lines = parsers.litert_side_lines(console)
        counts = parsers.ynnpack_counts(console)
        cond["backendRegistered"] = lines
        if row.backend == "cpu":
            cond.update(enableYnnpack=row.ynnpack, ynnpackLines=counts)
        off = parsers.litert_side_off_device(lines, row.backend, row.ynnpack, counts)
        if off:
            cond["backendOffReason"] = off
        samples = list(samples) + [{}] * max(0, 2 - len(samples))
        return samples, cond, parsers.context_prompt_texts(console), bool(off), True
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
                if ": using device " in ln and gpu_substr in ln]
        device = used[0].split(" (")[0] if used else None
        cond.update(ggmlDevice=device, nGpuLayers=99, flashAttn="on", backendRegistered=lines)
        off = device is None or not parsers.llama_backend_registered(lines, device, device, "llama-cli")
    samples = [parsers.parse_llama_cli(console)]
    return samples, cond, texts, off, bool(row.backend)


def write_records(plan: Plan, campaign_dir: pathlib.Path, invocation: str, *,
                  litert_label: str = "unknown", pins: dict | None = None,
                  extra_catalog: str | None = None, default_model: str = "Windows PC",
                  harness: str = HARNESS, log_subdir: str = "omnilab") -> tuple:
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
        "batteryState": "unknown",
    }
    pins = pins if pins is not None else load_pins()
    checking = os.environ.get("BENCH_TEXT_CHECK", "1") == "1"
    built, clean, total = set(), 0, 0
    (campaign_dir / "decoded").mkdir(parents=True, exist_ok=True)
    for row in plan.rows:
        path, size = plan.models[model_key(row)]
        quant = catalog_quantization(row.runtime, row.model_id, extra_catalog)
        if row.runtime == "litert-lm":
            build = version = litert_label
            artifact = f"{LITERT_EXE} sha256:{shas.get(LITERT_EXE)}"
        else:
            build = version = pinned_label(pins, row.backend)
            want = dict(pins[build].get("dll_files") or {})
            want["llama-cli.exe"] = pins[build]["llama_cli_sha256"]
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
            samples, checks, texts, off, checked = _launch_fields(row, console, ctx)
            exit_code, timed_out = meta.get("exitCode"), bool(meta.get("timedOut"))
            flags = list(checks.get("protocolFlags") or [])
            if timed_out:
                flags.append("engine-timeout")
            elif exit_code != 0:
                flags.append(f"engine-exit-{exit_code}")
            first_ever = key not in built and (row.runtime == "litert-lm" or bool(row.backend))
            paired = row.runtime == "litert-lm"
            start = str(meta.get("start") or "")
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
                        "contextTokens": row.ctx,
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
                    if prompt_ver:
                        cond["promptVersion"] = prompt_ver
                    if checked and checking:
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
                            "quantization": quant,
                            "file": path.name,
                            "onDiskSizeBytes": size,
                        },
                        "task": row.task,
                        "timestamp": start[:19] + "Z" if len(start) >= 19 else None,
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
          "(e.g. --executor omnilab)", file=sys.stderr)
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
