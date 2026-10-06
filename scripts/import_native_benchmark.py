#!/usr/bin/env python3
"""Turn `YARDSTICK_NATIVE_OK` console lines into result JSON so the native row is auditable.

    python3 scripts/import_native_benchmark.py results/raw/<campaign>/console_NATIVE_*.txt

Why this exists
---------------
`runNativeBenchmark` prints its numbers and returns — it never goes through `ResultStore`, so
the LiteRT-LM vendor-`benchmark()` row (prefill exactly 1024, the ONLY card-comparable prefill
figure we can produce) lands in a `.txt` and nowhere else. `analyze_comparability.py` reads
`*.json`; `verify_published_numbers.py` indexes `results/**/*.json{,l}`. A number that exists
only in a console log is exactly the "number that exists only in prose" those two scripts were
written to refuse. This lifts the console line into the same schema the app writes, so the
native row is audited by the same tools as everything else.

What it deliberately does NOT do
--------------------------------
Invent fields the native path never measured. `runNativeBenchmark` samples memory but starts
no `ThermalSampler` and no `EnergyMonitor`, so thermal/battery/energy are written as null
rather than as a plausible-looking "nominal". `analyze_comparability.py` gates its speed table
on `initialThermalState == "nominal"`, so these rows are excluded from it by default — which
is the correct outcome: we cannot attest the thermal regime of a cell that did not record one.
Pass `--all-thermal` to inspect them anyway, and read the exclusion as a TODO for the app
(the native path should start a ThermalSampler like `BenchmarkRunner` does).

The task id is `native-benchmark-<prefill>x<decode>`, never `long-context-*`: a forced-prefill
vendor entry point and a task-prompt run are different measurements and must not pool into one
median. That separation is the whole point of the protocol's two-row structure.

Core AI rows
------------
A line that says `runtime=core-ai` comes from `--coreai-native-benchmark` (CoreAIRuntime's port
of Apple's llm-benchmark, BenchmarkMain.swift): one line per timed trial after one warmup trial
in the same process, so each becomes its own record (spread stays visible), coldRun false. That
path does sample thermal state, so those rows carry it. A line without `runtime=` is a LiteRT-LM
row and imports exactly as before.

Cold and warm (lines from the 2026-10-07 build on)
--------------------------------------------------
LiteRT-LM lines then carry `run=<i> runs=<N> cold=<0|1>`: `--runs N` calls `benchmark()` N times
back to back in one process, and run 1 (cold=1) is the first call. `benchmark()` builds a new
engine on every call, so a warm run (2...N) differs from the cold one only in the process and the
on-disk caches. They also carry `thermal_initial` / `thermal_final` (ProcessInfo.thermalState read
before and after the call; no peak is sampled) and `wall_s` (the call's wall-clock seconds), which
become initialThermalState / finalThermalState / wallSeconds. Core AI lines carry `cold=`, and the
warmup trial has its own line, trial=0 cold=1 (the first generate on the engine after the load),
which imports with coldRun true. `cold` sets coldRun; the run/trial index lands in `conditions`.
Fields an older line lacks are left out of its record, so an older log imports byte-identically.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from pathlib import Path

# One regex over the whole line; every field is optional so older console logs (which lack
# context_tokens / median_mb / harness) still import, with the missing fields left null
# instead of silently defaulted.
#
# The value pattern is a plain `\S+` on purpose. An earlier `([-\d.]+|\?|[\w.-]+)` truncated
# `harness=2026-07-27-agreed-protocol-r2` to `2026-07-27-`, because the numeric alternative
# matched the leading date and won. A stamp that silently loses its suffix is worse than no
# stamp at all — it reads as a valid, different contract. Numeric coercion happens in `num()`,
# where a non-numeric value returns None rather than a wrong number.
FIELD = re.compile(r"(\w+)=(\S+)")

MODEL_RE = re.compile(r"YARDSTICK_BEGIN native_benchmark model=(\S+)")
BEGIN_RE = re.compile(r"prefill=(\d+) decode=(\d+)")


def parse(path: Path):
    text = path.read_text(errors="replace").replace("\r", "\n")
    model = None
    prefill_cfg = decode_cfg = None
    for line in text.split("\n"):
        if m := MODEL_RE.search(line):
            model = m.group(1)
        if "native_benchmark" in line and (m := BEGIN_RE.search(line)):
            prefill_cfg, decode_cfg = int(m.group(1)), int(m.group(2))
        if "YARDSTICK_NATIVE_OK" not in line:
            continue
        f = dict(FIELD.findall(line.split("YARDSTICK_NATIVE_OK", 1)[1]))

        def num(k, cast=float):
            v = f.get(k)
            if v in (None, "?"):
                return None
            try:
                return cast(v)
            except ValueError:
                return None

        yield {
            "model": model,
            "prefill_cfg": prefill_cfg,
            "decode_cfg": decode_cfg,
            "fields": f,
            "num": num,
        }


def to_result(rec, source: Path, device_id: str, model_id: str | None):
    f, num = rec["fields"], rec["num"]
    prefill = num("prefill_tokens", int) or rec["prefill_cfg"]
    decode = num("decode_tokens", int) or rec["decode_cfg"]
    # The Mac CLI's `--output` for native mode carries only the NATIVE_OK line — no
    # YARDSTICK_BEGIN — so the configured sizes fall back to the measured ones (they are
    # equal whenever the run completed) rather than yielding `native-benchmark-NonexNone`.
    task = f"native-benchmark-{rec['prefill_cfg'] or prefill}x{rec['decode_cfg'] or decode}"
    if f.get("runtime") == "core-ai":
        return core_ai_result(rec, source, device_id, model_id, task, prefill, decode)
    cold = num("cold", int)
    result = {
        "runtime": "litert-lm",
        "task": task,
        "model": {"id": rec["model"] or model_id},
        "device": {"modelIdentifier": device_id},
        "outputSample": "",
        # Provenance is part of the record, not a comment: this row was lifted from a console
        # log by this script, and anyone auditing it should be able to go straight back to the
        # line it came from.
        "provenance": {
            "importedBy": "scripts/import_native_benchmark.py",
            "sourceFile": str(source),
            "entryPoint": "LiteRTLM.benchmark()",
            "note": "vendor force-prefill entry point; not comparable with task-prompt prefill",
        },
        "metrics": {
            "coldRun": None if cold is None else cold == 1,
            "promptTokenCount": prefill,
            "promptTokensPerSecond": num("prefill_tok_s"),
            "generatedTokenCount": decode,
            "decodeTokensPerSecond": num("decode_tok_s"),
            "firstTokenLatencyMS": num("ttft_ms"),
            "loadTimeSeconds": num("init_s"),
            "memoryPeakDuringDecodeMB": num("peak_mb"),
            "memoryMedianMB": num("median_mb"),
            "memoryMedianResidentMB": num("median_resident_mb"),
            "memorySampleCount": num("samples", int),
            # The published 92 MB cell was this quantity. Kept as its own field so it can never
            # again be mistaken for the in-run peak sitting next to it.
            "memoryPostTeardownFootprintMB": num("teardown_footprint_mb"),
            "contextTokensConfigured": num("context_tokens", int),
            "harnessStamp": f.get("harness"),
            # Not measured by the native path before the 2026-10-07 build — see the docstring.
            "initialThermalState": None,
            "peakThermalState": None,
            "energyJoules": None,
        },
    }
    # Only lines from the 2026-10-07 build on carry these; an older line adds nothing.
    if (run := num("run", int)) is not None:
        result["conditions"] = {"run": run, "runs": num("runs", int)}
    if "thermal_initial" in f:
        result["metrics"]["initialThermalState"] = f.get("thermal_initial")
        result["metrics"]["finalThermalState"] = f.get("thermal_final")
    if "wall_s" in f:
        result["metrics"]["wallSeconds"] = num("wall_s")
    return result


def core_ai_result(rec, source: Path, device_id: str, model_id: str | None, task: str,
                   prefill, decode):
    f, num = rec["fields"], rec["num"]
    cached = num("prepare_cached", int)
    cold = num("cold", int)
    return {
        "runtime": "core-ai",
        "task": task,
        "model": {"id": rec["model"] or model_id},
        "device": {"modelIdentifier": device_id},
        "outputSample": "",
        "provenance": {
            "importedBy": "scripts/import_native_benchmark.py",
            "sourceFile": str(source),
            "entryPoint": "CoreAIRuntime.nativeBenchmarkStock",
            "note": ("port of apple/coreai-models llm-benchmark (BenchmarkMain.swift): a synthetic "
                     "prompt of prefill_tokens SplitMix64 token ids, greedy, no stop token; prompt "
                     "tok/s = prefill_tokens / time to the first token, decode tok/s = (tokens - 1) "
                     "/ time from the first token to the end of the stream; not comparable with "
                     "task-prompt prefill"),
        },
        "conditions": {
            "trial": num("trial", int),
            "trials": num("trials", int),
            "warmupTrials": 1,
            "seed": num("seed", int),
            "sampler": "greedy",
        },
        "metrics": {
            # Every timed trial follows a warmup trial in the same process. A line without
            # cold= is a timed trial (older builds printed no other); trial 0 is the warmup.
            "coldRun": False if cold is None else cold == 1,
            "promptTokenCount": prefill,
            "promptTokensPerSecond": num("prefill_tok_s"),
            "generatedTokenCount": decode,
            "decodeTokensPerSecond": num("decode_tok_s"),
            "decodeSeconds": num("decode_s"),
            "firstTokenLatencyMS": num("ttft_ms"),
            "loadTimeSeconds": num("init_s"),
            "prepareCacheHit": None if cached is None else cached == 1,
            "prepareFootprintPeakMB": num("prepare_peak_mb"),
            "engineWarmupSeconds": num("engine_warmup_s"),
            "warmupTrialSeconds": num("warmup_trial_s"),
            "memoryPeakDuringDecodeMB": num("peak_mb"),
            "memoryMedianMB": num("median_mb"),
            "memoryMedianResidentMB": num("median_resident_mb"),
            "memorySampleCount": num("samples", int),
            "contextTokensConfigured": num("context_tokens", int),
            "harnessStamp": f.get("harness"),
            "initialThermalState": f.get("thermal_initial"),
            "peakThermalState": f.get("thermal_peak"),
            "finalThermalState": f.get("thermal_final"),
            "energyJoules": None,
        },
    }


# --schema-v1 (2026-10-06): the audit shape above has no id, timestamp, engine or device snapshot,
# so build_summary cannot place it in a session and the dashboard never sees the vendor row. With
# --schema-v1 each line becomes a full schema-v1 record (schema/result.v1.json), written to the
# campaign's app-path-native/ directory (build_summary globs app-path*/*.json):
#   - device, engineVersion / engineArtifact and model come from --like, a schema-v1 record of the
#     same device, engine build and model (the native path reports none of them). The snapshot's
#     per-run readings are dropped, since nothing read them at the native launch: always
#     initialThermalState, and batteryLevel / batteryState when the device has a battery (a Mac
#     without one records the constants -1 / unknown, which are kept);
#   - timestamp = the launch's start (--launch-times, one per line in file order; the caller takes
#     them from the runner's CELL lines);
#   - metrics carry only what the line measured (no null placeholders), plus coldRun true: one
#     native launch is one process and one engine init; firstEver true on the launches named by
#     --first-ever (the line itself cannot tell that its launch built the compilation cache —
#     on the Mac the GPU program cache in $TMPDIR written during that launch can);
#   - conditions.instrument names the entry point, conditions.launchIndex the launch's position.
# Lines of the app build of 2026-10-07 and later say more, and the record keeps it (a field a line
# lacks is left out, so an older log imports as before):
#   - `thermal_initial` / `thermal_final` (ProcessInfo.thermalState read before and after the call;
#     `thermal_peak` where a path samples one) become metrics.initialThermalState /
#     finalThermalState / peakThermalState — the keys the app's own records use and the ones
#     build_summary and cell_gate read. Without them a phone's native row has no thermal column and
#     a throttled launch cannot be told from a cool one;
#   - `wall_s` (the call's wall-clock seconds) becomes metrics.wallSeconds;
#   - `run=<i> runs=<N> cold=<0|1>`: one launch can call benchmark() N times, so one launch can
#     print N lines. `cold` sets coldRun (run 1 is the process's first call; a warm line stamped
#     cold would pool into the cold median), run / runs land in conditions, and the lines of one
#     launch share its launchIndex and its start time: --launch-times and --first-ever count
#     launches (a line without `run=`, or with run=1, starts one), and firstEver marks only the
#     launch's first line.
PER_RUN_DEVICE_KEYS = ("initialThermalState",)
BATTERY_KEYS = ("batteryLevel", "batteryState")
V1_METRICS = (  # (record key, NATIVE_OK field, cast)
    ("promptTokensPerSecond", "prefill_tok_s", float),
    ("decodeTokensPerSecond", "decode_tok_s", float),
    ("firstTokenLatencyMS", "ttft_ms", float),
    ("loadTimeSeconds", "init_s", float),
    ("memoryPeakDuringDecodeMB", "peak_mb", float),
    ("memoryMedianMB", "median_mb", float),
    ("memoryMedianResidentMB", "median_resident_mb", float),
    ("memorySampleCount", "samples", int),
    ("memoryPostTeardownFootprintMB", "teardown_footprint_mb", float),
    ("contextTokensConfigured", "context_tokens", int),
    ("wallSeconds", "wall_s", float),
)
V1_STATES = (  # (record key, NATIVE_OK field) — strings, copied as printed
    ("initialThermalState", "thermal_initial"),
    ("peakThermalState", "thermal_peak"),
    ("finalThermalState", "thermal_final"),
)
LAUNCH_TIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def load_like(path: Path) -> dict:
    """A .json record, or the first record of a .jsonl."""
    txt = path.read_text()
    try:
        return json.loads(txt)
    except json.JSONDecodeError:
        return json.loads(next(ln for ln in txt.splitlines() if ln.strip()))


def launch_positions(recs) -> list[int]:
    """1-based launch position of each line. A line without `run=` is its own launch (the builds
    before 2026-10-07 print one line per process); `run=1` starts a launch, `run=2..N` continue it."""
    pos, n = [], 0
    for rec in recs:
        run = rec["fields"].get("run", "")
        if not (n and run.isdigit() and int(run) > 1):
            n += 1
        pos.append(n)
    return pos


def to_schema_v1(rec, source: Path, like: dict, launch_time: str, index: int, instrument: str,
                 first_ever: bool = False):
    # rec["num"] closes over parse()'s loop variable, so it reads the LAST line's fields once
    # the generator has been drained (main_schema_v1 counts the lines first) — read this
    # line's own dict instead.
    f = rec["fields"]

    def num(k, cast=float):
        v = f.get(k)
        if v in (None, "?"):
            return None
        try:
            return cast(v)
        except ValueError:
            return None

    prefill = num("prefill_tokens", int) or rec["prefill_cfg"]
    decode = num("decode_tokens", int) or rec["decode_cfg"]
    snap = like.get("device", {})
    device = {k: v for k, v in snap.items() if k not in PER_RUN_DEVICE_KEYS}
    level = snap.get("batteryLevel")
    if isinstance(level, (int, float)) and not isinstance(level, bool) and level >= 0:
        for k in BATTERY_KEYS:
            device.pop(k, None)
    model = dict(like["model"])
    model.setdefault("file", model.get("primaryFile"))
    cold = num("cold", int)
    metrics = {"coldRun": True if cold is None else cold == 1,
               "promptTokenCount": prefill, "generatedTokenCount": decode}
    if first_ever:
        metrics["firstEver"] = True
    for key, field, cast in V1_METRICS:
        v = num(field, cast)
        if v is not None:
            metrics[key] = v
    for key, field in V1_STATES:
        if f.get(field) not in (None, "?"):
            metrics[key] = f[field]
    if f.get("harness"):
        metrics["harnessStamp"] = f["harness"]
    conditions = {"instrument": instrument, "launchIndex": index}
    for key in ("run", "runs"):
        if (v := num(key, int)) is not None:
            conditions[key] = v
    out = {
        "schemaVersion": 1,
        "id": str(uuid.uuid4()).upper(),
        "runtime": like["runtime"],
        "engineVersion": like.get("engineVersion"),
        "engineArtifact": like.get("engineArtifact"),
        "model": model,
        "task": f"native-benchmark-{rec['prefill_cfg'] or prefill}x{rec['decode_cfg'] or decode}",
        "timestamp": launch_time,
        "device": device,
        "conditions": conditions,
        "metrics": metrics,
        "provenance": {"rawLog": str(source), "harness": "scripts/import_native_benchmark.py"},
    }
    if like.get("modelRevision"):
        out["modelRevision"] = like["modelRevision"]
    return out


def main_schema_v1(args) -> int:
    if len(args.logs) != 1 or args.out is None or args.like is None \
            or args.launch_times is None or not args.instrument:
        print("--schema-v1 takes one log and needs --out, --like, --launch-times and --instrument",
              file=sys.stderr)
        return 2
    log = args.logs[0]
    like = load_like(args.like)
    if not str(like.get("runtime", "")).startswith("litert-lm"):
        print(f"--like is a {like.get('runtime')!r} record; the native row is litert-lm", file=sys.stderr)
        return 2
    if like.get("device", {}).get("modelIdentifier") != args.device:
        print(f"--like device {like.get('device', {}).get('modelIdentifier')!r} != --device "
              f"{args.device!r}", file=sys.stderr)
        return 2
    times = [t.strip() for t in args.launch_times.split(",") if t.strip()]
    bad = [t for t in times if not LAUNCH_TIME.match(t)]
    if bad:
        print(f"--launch-times wants UTC YYYY-MM-DDTHH:MM:SSZ, got {bad}", file=sys.stderr)
        return 2
    recs = list(parse(log))
    launches = launch_positions(recs)
    n_launches = launches[-1] if launches else 0
    if n_launches != len(times):
        print(f"{log}: {len(recs)} YARDSTICK_NATIVE_OK lines in {n_launches} launches but "
              f"{len(times)} launch times", file=sys.stderr)
        return 2
    first_ever = {int(x) for x in (args.first_ever or "").split(",") if x.strip()}
    if not first_ever <= set(range(1, n_launches + 1)):
        print(f"--first-ever {sorted(first_ever)} names launches outside 1..{n_launches}",
              file=sys.stderr)
        return 2
    args.out.mkdir(parents=True, exist_ok=True)
    stem = log.stem.replace("console_", "")
    for i, (rec, launch) in enumerate(zip(recs, launches), 1):
        model_id = rec["model"] or args.model_id
        if model_id != like["model"].get("id"):
            print(f"line {i}: model {model_id!r} != --like model {like['model'].get('id')!r}",
                  file=sys.stderr)
            return 2
        out = args.out / f"native_{stem}_{i}.json"
        head = i == 1 or launches[i - 2] != launch  # the launch's first line
        out.write_text(json.dumps(to_schema_v1(rec, log, like, times[launch - 1], launch,
                                               args.instrument,
                                               first_ever=head and launch in first_ever),
                                  indent=2, sort_keys=True) + "\n")
        print(f"wrote {out}", file=sys.stderr)
    print(f"\n{len(recs)} native row(s) imported as schema-v1 records.", file=sys.stderr)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("logs", nargs="+", type=Path)
    # Required, no default. The old `default="iPhone18,1"` stamped a Mac capture as an
    # iPhone the first time this script met Mac logs (2026-07-28) — a silently wrong
    # device label is the exact class of corruption the audit tooling exists to catch.
    ap.add_argument("--device", required=True,
                    help="device model identifier to stamp, e.g. iPhone18,1 or the Mac's "
                         "`sysctl -n hw.model`")
    ap.add_argument("--model-id", default=None,
                    help="model id to stamp when the log has no YARDSTICK_BEGIN line "
                         "(the Mac CLI's --output carries only the NATIVE_OK line)")
    ap.add_argument("--out", type=Path, default=None,
                    help="output dir (default: alongside each console log)")
    ap.add_argument("--schema-v1", action="store_true",
                    help="write full schema-v1 records for <campaign>/app-path-native/ (see the "
                         "comment above to_schema_v1); one log per call, with --out, --like, "
                         "--launch-times and --instrument")
    ap.add_argument("--like", type=Path, default=None,
                    help="--schema-v1: a schema-v1 record (.json or .jsonl) of the same device, "
                         "engine build and model, whose device / engine / model fields are copied")
    ap.add_argument("--launch-times", default=None,
                    help="--schema-v1: comma-separated UTC launch start times "
                         "(YYYY-MM-DDTHH:MM:SSZ), one per launch in file order (a launch is one "
                         "YARDSTICK_NATIVE_OK line, or its run=1..N lines)")
    ap.add_argument("--instrument", default=None,
                    help="--schema-v1: conditions.instrument, the entry point that printed the lines")
    ap.add_argument("--first-ever", default=None,
                    help="--schema-v1: comma-separated launch positions (1-based) that built "
                         "the engine's compilation cache; the launch's first line is marked "
                         "metrics.firstEver (fairness rule 2: never the engine's speed); the caller "
                         "states the evidence")
    args = ap.parse_args()
    if args.schema_v1:
        return main_schema_v1(args)

    written = 0
    for log in args.logs:
        if not log.exists():
            print(f"warn: no such file: {log}", file=sys.stderr)
            continue
        for i, rec in enumerate(parse(log), 1):
            result = to_result(rec, log, args.device, args.model_id)
            outdir = args.out or log.parent
            outdir.mkdir(parents=True, exist_ok=True)
            stem = log.stem.replace("console_", "")
            out = outdir / f"native_{stem}_{i}.json"
            out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
            print(f"wrote {out}", file=sys.stderr)
            written += 1

    if not written:
        print("no YARDSTICK_NATIVE_OK lines found", file=sys.stderr)
        return 1
    print(f"\n{written} native row(s) imported.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
