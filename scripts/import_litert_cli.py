#!/usr/bin/env python3
"""Lift LiteRT-LM CLI consoles into schema-v1 records: `litert_lm_advanced_main --benchmark` launches run on the Mac
outside the Mac runner, by hand or by a lane's driver.

    python3 scripts/import_litert_cli.py <manifest.jsonl> --out results/raw/<campaign>/app-path-cli \
        --like <a schema-v1 record of this Mac in this sitting> --device Mac16,9 --model-id <id> \
        --quantization <label> --engine <engineVersion> --engine-artifact <text> --engine-build <text> \
        --instrument <text>

Why this exists
---------------
The Mac runner (scripts/bench_matrix_mac.sh) runs the yardstick, whose LiteRT-LM is the vendored release. A LiteRT-LM
build other than that (2026-10-23: the HEAD build with YNNPACK of the context ladder, matrices/ctx-ladder-*.cells,
the Mac build of the Android side build head-lm2ef6baeb-rtd469ea48-xnn878f1d8c-ynn-cpuonly) runs as its CLI, whose
console is the one the Android route reads: android/bench/parsers.py parse_litert (TTFT, Prefill Turn 1, decode),
litert_side_lines (the build's lines), ynnpack_counts (YNNPACK's per-op lines and partitions) and
litert_side_off_device (on the CPU, YNNPACK's lines absent when --enable_ynnpack=true asked for it or present when it
did not: protocolFlags backend-not-registered, a row and never a measurement, as on Android). Here those consoles
become the same records, so the context ladder's Mac numbers are records and not a table in a lane's notes.

What a record says
------------------
runtime = litert-lm-<backend>, -ynnpack with --enable_ynnpack=true (the Android arms); task =
native-benchmark-<prefill>x<decode> from the command's --benchmark_prefill_tokens / --benchmark_decode_tokens;
conditions.contextTokens = its --max_num_tokens. The engine sizes the graph's KV placeholder to that flag at load and
logs `magic_number=<M>, target_number=<N>`: a launch whose console has no such line, or another N, is no number
(its record is written as .offtarget, below). Every launch is one process: coldRun true; the manifest's firstEver
marks a cell's first launch (the engine-cache build; the caller states the evidence in engineCache). Memory:
metrics.memoryPeakResidentMB = /usr/bin/time -l's maximum resident set size (the resident high-water mark, as
Android's VmHWM); its peak memory footprint goes to conditions.timePeakFootprintMB. Thermal state: not read by the
CLI, left out. device = --like's device minus what a run or an app build reads (only the keys in DEVICE_KEYS).

The manifest: one JSON object per try of a launch, written by the driver: log (the console with /usr/bin/time -l's
lines and EXIT_CODE=<rc> at its end; a repo path results/raw/<campaign>/..., as the record's provenance.rawLog, or a
path relative to the manifest), command (the argv as run, a list), start (UTC YYYY-MM-DDTHH:MM:SSZ), launchIndex (the
launch's position in the sitting), cellLaunch (1..N within its model, arm and allocation), firstEver (bool),
engineCache (text), verdict (clean, retaken-clean, overlap-twice, superseded = a first try another process overlapped
and that was taken again, or first-overlapped = a cell's first launch, firstEver, overlapped and not taken again),
hostSamples (the sampler's file), modelFile, modelSha256.

What it writes per try, under --out: <stem>.json for a standing launch; <stem>.json.attempt1 for a superseded try;
<stem>.json.overlapped for overlap-twice (no number); <stem>.json.offtarget when the KV check failed. The three
suffixes fall outside build_summary's *.json glob and stay as the audit trail. Exit 0; 3 when a launch failed the KV
check; 2 usage.
"""
import argparse
import json
import os
import re
import sys
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "android", "bench"))
import parsers  # noqa: E402

HARNESS = "2026-10-mac-litert-cli-v1"
# what a device snapshot keeps from --like: the machine, not a run (thermal) or an app build (buildConfiguration)
DEVICE_KEYS = ("modelIdentifier", "systemName", "systemVersion", "physicalMemoryMB", "processorCount",
               "batteryLevel", "batteryState", "isLowPowerModeEnabled")
# first-overlapped: a cell's first launch (the cache build, firstEver: never a number) that another process
# overlapped; the driver does not take it again
VERDICT_SUFFIX = {"clean": ".json", "retaken-clean": ".json", "first-overlapped": ".json",
                  "superseded": ".json.attempt1", "overlap-twice": ".json.overlapped"}
RE_KV = re.compile(r"magic_number=(\d+), target_number=(\d+)")
RE_EXIT = re.compile(r"^EXIT_CODE=(\d+)", re.M)
RE_RSS = re.compile(r"^\s*(\d+)\s+maximum resident set size", re.M)
RE_FOOTPRINT = re.compile(r"^\s*(\d+)\s+peak memory footprint", re.M)
RE_REAL = re.compile(r"^\s*([\d.]+) real\b", re.M)
LAUNCH_TIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def flags_of(argv):
    """--key=value flags of an argv -> {key: value}."""
    return dict(a[2:].split("=", 1) for a in argv[1:] if a.startswith("--") and "=" in a)


def last_int(rx, text):
    hits = rx.findall(text)
    return int(hits[-1]) if hits else None


def to_record(entry, text, like, args, raw_log):
    """One try of a launch -> (record, file suffix, problem or None)."""
    f = flags_of(entry["command"])
    ctx = int(f["max_num_tokens"])
    backend = f["backend"]
    ynn = f.get("enable_ynnpack") == "true"
    runtime = f"litert-lm-{backend}" + ("-ynnpack" if ynn else "")
    metrics = parsers.parse_litert(text)
    lines = parsers.litert_side_lines(text)
    counts = parsers.ynnpack_counts(text)
    off = parsers.litert_side_off_device(lines, backend, ynn, counts)
    kv = sorted({(int(m), int(n)) for m, n in RE_KV.findall(text)})
    rc = last_int(RE_EXIT, text)
    rss = last_int(RE_RSS, text)
    footprint = last_int(RE_FOOTPRINT, text)
    real = RE_REAL.findall(text)
    home = os.path.expanduser("~")
    conditions = {
        "instrument": args.instrument, "launchIndex": entry["launchIndex"], "cellLaunch": entry["cellLaunch"],
        "sampler": "engine-default", "contextTokens": ctx,
        "kvAllocation": [{"magicNumber": m, "targetNumber": n} for m, n in kv],
        "engineBuild": args.engine_build,
        "engineCommand": " ".join(entry["command"]).replace(home, "~"),
        "backendRegistered": lines, "exitCode": rc,
        "elapsedSeconds": float(real[-1]) if real else None,
        "hostOverlap": {"verdict": entry["verdict"], "samples": entry.get("hostSamples")},
        "engineCache": entry.get("engineCache"),
        "protocolFlags": [],
    }
    if footprint is not None:
        conditions["timePeakFootprintMB"] = round(footprint / 1048576, 1)
    if backend == "cpu":
        conditions.update(enableYnnpack=ynn, ynnpackLines=counts)
    if off:
        conditions["backendOffReason"] = off
        conditions["protocolFlags"].append("backend-not-registered")
    if rc not in (0, None):
        conditions["protocolFlags"].append(f"engine-exit-{rc}")
    metrics.update(coldRun=True, harnessStamp=HARNESS)
    if entry.get("firstEver"):
        metrics["firstEver"] = True
    if rss is not None:
        metrics["memoryPeakResidentMB"] = round(rss / 1048576, 1)
    snap = like.get("device", {})
    model = {"id": args.model_id, "quantization": args.quantization,
             "file": os.path.basename(entry["modelFile"]), "sha256": entry["modelSha256"]}
    record = {
        "schemaVersion": 1, "id": str(uuid.uuid4()), "runtime": runtime,
        "engineVersion": args.engine, "engineArtifact": args.engine_artifact, "model": model,
        "task": f"native-benchmark-{f['benchmark_prefill_tokens']}x{f['benchmark_decode_tokens']}",
        "timestamp": entry["start"], "device": {k: snap[k] for k in DEVICE_KEYS if k in snap},
        "conditions": conditions, "metrics": metrics,
        "provenance": {"rawLog": raw_log, "harness": "scripts/import_litert_cli.py",
                       "rssBasis": "/usr/bin/time -l around the CLI process: maximum resident set size (bytes / "
                                   "1048576) = memoryPeakResidentMB; peak memory footprint = "
                                   "conditions.timePeakFootprintMB"},
    }
    problem = None
    if [n for _, n in kv] != [ctx]:
        problem = (f"KV allocation: the console's target_number {[n for _, n in kv] or 'missing'} "
                   f"is not --max_num_tokens {ctx}")
    return record, (".json.offtarget" if problem else VERDICT_SUFFIX[entry["verdict"]]), problem


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("manifest")
    ap.add_argument("--out", required=True, help="results/raw/<campaign>/app-path-cli")
    ap.add_argument("--like", required=True, help="a schema-v1 record of the same device in the same sitting")
    ap.add_argument("--device", required=True, help="the device's modelIdentifier (`sysctl -n hw.model`)")
    ap.add_argument("--model-id", required=True)
    ap.add_argument("--quantization", required=True, help="the artifact's label (quant-label-rule): the string "
                                                          "the other platforms give the same file")
    ap.add_argument("--engine", required=True, help="engineVersion")
    ap.add_argument("--engine-artifact", required=True, help="engineArtifact: the binary that ran (its sha256)")
    ap.add_argument("--engine-build", required=True, help="conditions.engineBuild: how the binary was built")
    ap.add_argument("--instrument", required=True, help="conditions.instrument: the entry point")
    args = ap.parse_args()
    with open(args.like) as fh:
        txt = fh.read()
    try:
        like = json.loads(txt)
    except json.JSONDecodeError:
        like = json.loads(next(ln for ln in txt.splitlines() if ln.strip()))
    if like.get("device", {}).get("modelIdentifier") != args.device:
        print(f"--like device {like.get('device', {}).get('modelIdentifier')!r} != --device {args.device!r}",
              file=sys.stderr)
        return 2
    base = os.path.dirname(os.path.abspath(args.manifest))
    with open(args.manifest) as fh:
        entries = [json.loads(ln) for ln in fh if ln.strip()]
    bad = [e for e in entries if e.get("verdict") not in VERDICT_SUFFIX or not LAUNCH_TIME.match(e.get("start", ""))
           or (e["verdict"] == "first-overlapped" and not e.get("firstEver"))]
    if not entries or bad:
        print(f"{args.manifest}: {len(entries)} entries, {len(bad)} without a known verdict or a UTC start "
              f"(first: {bad[:1]})", file=sys.stderr)
        return 2
    os.makedirs(args.out, exist_ok=True)
    offtarget = 0
    for e in entries:
        log = e["log"]
        path = log if os.path.isabs(log) else os.path.join(base, log)
        if log.startswith("results/raw/"):
            path = os.path.join(base[:base.index("results/raw/")] if "results/raw/" in base else base, log)
        with open(path, errors="replace") as fh:
            text = fh.read()
        record, suffix, problem = to_record(e, text, like, args, log)
        stem = f"{record['runtime']}_{args.model_id.replace('/', '_')}_{record['task']}_{e['start'].replace(':', '-')}"
        out = os.path.join(args.out, stem + suffix)
        with open(out, "w") as fh:
            fh.write(json.dumps(record, indent=2) + "\n")
        print(f"{os.path.basename(out)}{': ' + problem if problem else ''}", file=sys.stderr)
        offtarget += bool(problem)
    print(f"{len(entries)} launch tries imported; {offtarget} failed the KV check", file=sys.stderr)
    return 3 if offtarget else 0


if __name__ == "__main__":
    sys.exit(main())
