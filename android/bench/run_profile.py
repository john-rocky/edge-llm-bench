#!/usr/bin/env python3
"""Android per-op profiling driver: one (control, profiled) PAIR per LiteRT-LM cell.

  CAMPAIGN=<name> python3 android/bench/run_profile.py matrices/profile-example-android.cells
      [--max-num-tokens 1024,4096] [--allow-large-context]

Only `android litert-lm ... native-benchmark-<P>x<D>` cells with a backend are
eligible: the profile comes from litert_lm_advanced_main's --enable_profiling,
the binary the native-benchmark task already runs. Any other cell is listed
in profiles/SKIPPED.txt with the reason.

Per cell (and per context size when --max-num-tokens is given):
  1. the CONTROL: one normal run_cell.py capture (thermal gate, cooldown,
     capture gate) whose record lands in <campaign>/app-path-android/ as an
     ordinary speed row. A control that is the engine's cache-building run
     (metrics.firstEver) is repeated once after a cooldown, because its wall
     time is the divisor of the whole table. With --max-num-tokens the
     controls go to <campaign>/profiles/controls-ctx<N>/ instead: rows that
     differ only in context size would pool into one median in the summary,
     and the CPU step scales with the allocated context.
  2. the PROFILED twin: the same on-device command plus --enable_profiling.
     Its console log, a copy of the control's log and a record go to
     <campaign>/profiles/ as <tag>_<backend>_prof.log, <tag>_<backend>_ctrl.log
     and <tag>_<backend>.prof.json — outside app-path*/, so build_summary.py
     never counts the profiled rate as speed (the record also carries
     conditions.profiling=true and provenance.controlRecord). The tag is
     model + bundle file + PxD + context, and an existing <tag>_<backend>
     pair is never overwritten (the cell is skipped with the reason).
Then scripts/profile/profile_report.py writes profiles/PROFILE.md and
profile-table.csv. Exit 0 when every pair is complete, 1 when a pair lacks
its control or profile (kept on disk, listed in profiles/FAILURES.txt),
2 on a bad cells file, 3 when another driver holds the device.

Why a pair: profiling changes the number — on the Galaxy S26 (2026-09-11,
v0.16.0) the profiled GPU decode read about half of its own control, on the
Pixel 8a (2026-09-12) about a third. The profiled run's rate is never a
benchmark row; the control's wall time is what the op table is compared
against.

Same one-driver-per-device lock file as run_campaign.py, so a profile run and
a matrix run never overlap on one phone.
"""
import argparse
import datetime
import fcntl
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import parsers  # noqa: E402
import run_campaign  # noqa: E402
import run_cell  # noqa: E402
from device_probe import battery, device_info, thermal_status  # noqa: E402

ROOT = run_cell.ROOT
NATIVE = re.compile(r"^native-benchmark-(\d+)x(\d+)$")
LARGE_CONTEXT = 8192  # the 32771-token GPU profile rebooted the S26 (2026-09-11)
HARNESS_STAMP = run_cell.HARNESS_STAMP + "+profiling"


class PairError(Exception):
    pass


def note(path, line):
    print(line)
    with open(path, "a") as fh:
        fh.write(line + "\n")


def load_record(path):
    return json.load(open(path))


def usable_control(path):
    rec = load_record(path)
    return (rec.get("conditions", {}).get("exitCode") == 0
            and bool(rec.get("metrics", {}).get("decodeTokensPerSecond")))


def control_run(cell, ctx, out_dir):
    """One control capture; returns the path of a NEW, clean record or raises PairError."""
    ccell = dict(cell, opts=dict(cell["opts"]))
    ccell["opts"]["runs"] = "1"
    if ctx:
        ccell["opts"]["context-tokens"] = str(ctx)
    for attempt in (1, 2):
        before = set(run_campaign.cell_records(ccell, out_dir))
        run_campaign.wait_nominal(out_dir)
        run_campaign.run_cell_once(ccell, out_dir, 1)
        run_campaign.apply_gate(ccell, out_dir, 1)  # HOT / DEAD -> quarantine + one re-run, like matrix
        new = [p for p in run_campaign.cell_records(ccell, out_dir) if p not in before]
        if not new:
            raise PairError("control run left no new record")
        path = sorted(new)[-1]
        if not usable_control(path):
            raise PairError(f"control run failed (record {os.path.basename(path)})")
        if load_record(path).get("metrics", {}).get("firstEver") and attempt == 1:
            print("control was the cache-building run (firstEver) — cooldown, then one more control")
            time.sleep(int(cell["opts"].get("cooldown", run_campaign.COOLDOWN)))
            continue
        return path
    return path


def profiled_run(cell, ctx, serial, timeout, prof_dir, control_path, tag, backend):
    """Run the --enable_profiling twin; returns its record (raises PairError on a bad run)."""
    control = load_record(control_path)
    pins = run_cell.load_pins()
    model_dev, model_local = run_cell.ensure_model(cell["model_id"], cell["opts"].get("file"),
                                                   cell["runtime"], serial)
    cmd, binname, sampler, ctx_note = run_cell.engine_command(
        cell["runtime"], backend, model_dev, cell["task"], None, None, None, ctx)
    cmd += " --enable_profiling"
    engine_version, engine_artifact = run_cell.observed_engine(binname, pins, serial)
    raw_status, thermal_name = thermal_status(serial)
    batt = battery(serial)
    t0 = time.time()
    console, exit_code, rss_mb = run_cell.run_once(cmd, binname, serial, timeout)
    elapsed = time.time() - t0
    end_status, end_name = thermal_status(serial)
    metrics = parsers.parse_litert(console)
    metrics.update({"coldRun": True, "harnessStamp": HARNESS_STAMP,
                    "initialThermalState": thermal_name, "finalThermalState": end_name})
    if rss_mb is not None:
        metrics["memoryMedianResidentMB"] = rss_mb
    log_name = f"{tag}_{backend}_prof.log"
    with open(os.path.join(prof_dir, log_name), "w") as fh:
        fh.write(console)
    rec = {
        "schemaVersion": 1,
        "id": str(uuid.uuid4()),
        "runtime": f"litert-lm-{backend}",
        "engineVersion": engine_version,
        "engineArtifact": engine_artifact,
        "model": {"id": cell["model_id"], "quantization": run_cell.guess_quant(model_dev),
                  "file": os.path.basename(model_dev),
                  "sha256": control.get("model", {}).get("sha256") or run_cell.sha256_file(model_local)},
        "task": cell["task"],
        "timestamp": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "device": {**device_info(serial), "batteryLevel": batt["batteryLevel"],
                   "batteryState": batt["batteryState"]},
        "conditions": {"profiling": True, "sampler": sampler,
                       "cpuAffinity": f"taskset {run_cell.CPU_MASK}" if run_cell.CPU_MASK else "none",
                       "contextTokens": ctx_note, "thermalRawStatus": raw_status,
                       "thermalRawStatusFinal": end_status, "screen": "on-usb",
                       "elapsedSeconds": round(elapsed, 1), "exitCode": exit_code},
        "metrics": metrics,
        "provenance": {"rawLog": log_name, "harness": "android/bench/run_profile.py",
                       "controlRecord": control.get("id"),
                       "controlRecordPath": os.path.relpath(control_path, os.path.dirname(prof_dir)),
                       "controlLog": f"{tag}_{backend}_ctrl.log",
                       "note": "profiled run: the rate carries the profiler's cost and is not a speed row"},
    }
    json.dump(rec, open(os.path.join(prof_dir, f"{tag}_{backend}.prof.json"), "w"), indent=2)
    d = metrics.get("decodeTokensPerSecond")
    if exit_code != 0 or not d:
        raise PairError(f"profiled run exit={exit_code} decode={d}")
    if "Run Order" not in console:
        raise PairError("profiled run produced no per-op table (Failed to start profiling?)")
    return rec


def eligible_cells(cells_file, skipped_path):
    anchors, payload, skipped = run_campaign.parse_cells(cells_file)
    for cell, reason in skipped:
        note(skipped_path, f"CELL_SKIP {run_campaign.cell_id(cell)} reason={reason}")
    cells = []
    for cell in anchors + payload:
        cid = run_campaign.cell_id(cell)
        if cell["runtime"] != "litert-lm":
            note(skipped_path, f"CELL_SKIP {cid} reason=profiling-is-litert-lm-only")
        elif not cell["opts"].get("backend"):
            note(skipped_path, f"CELL_SKIP {cid} reason=litert-lm-cell-needs-backend")
        elif not NATIVE.match(cell["task"]):
            note(skipped_path, f"CELL_SKIP {cid} reason=profiling-needs-native-benchmark-task "
                               "(litert_lm_advanced_main --benchmark is where --enable_profiling lives)")
        else:
            cells.append(cell)
    return cells


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cells")
    ap.add_argument("--max-num-tokens", help="comma-separated context sizes; one pair per size "
                                             "(overrides the cell's context-tokens=)")
    ap.add_argument("--allow-large-context", action="store_true",
                    help=f"permit sizes above {LARGE_CONTEXT} on a phone")
    ap.add_argument("--timeout", type=int, default=1800)
    args = ap.parse_args()
    sys.stdout.reconfigure(line_buffering=True)  # progress lines land in a redirected log as they happen

    sizes = None
    if args.max_num_tokens:
        try:
            sizes = [int(x) for x in args.max_num_tokens.split(",") if x.strip()]
        except ValueError:
            print(f"--max-num-tokens wants integers, got {args.max_num_tokens!r}", file=sys.stderr)
            return 2

    def guard(size):
        if size and size > LARGE_CONTEXT and not args.allow_large_context:
            print(f"refusing context size {size}: above {LARGE_CONTEXT} on a phone (the 32771-token GPU "
                  "profile rebooted the S26); pass --allow-large-context", file=sys.stderr)
            return False
        return True

    serial = run_campaign.SERIAL
    lock_key = serial
    if not lock_key:
        r = subprocess.run(["adb", "get-serialno"], capture_output=True, text=True)
        got = r.stdout.strip()
        lock_key = got if r.returncode == 0 and got and got != "unknown" else "default"
    lock = open(f"/tmp/edge-llm-bench-android-{lock_key}.lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print(f"another driver is already on device {lock_key} — refusing to start", file=sys.stderr)
        return 3

    campaign = os.environ.get("CAMPAIGN", time.strftime("%Y-%m-%d") + "-android-profile")
    raw_root = os.environ.get("BENCH_RAW_ROOT") or os.path.join(ROOT, "results", "raw")
    speed_dir = os.path.join(raw_root, campaign, "app-path-android")
    prof_dir = os.path.join(raw_root, campaign, "profiles")
    os.makedirs(prof_dir, exist_ok=True)
    skipped_path = os.path.join(prof_dir, "SKIPPED.txt")
    failures_path = os.path.join(prof_dir, "FAILURES.txt")

    cells = eligible_cells(args.cells, skipped_path)
    if not cells:
        print("no eligible android litert-lm native-benchmark cells in this file")
        return 2
    for cell in cells:
        for size in (sizes or [cell["opts"].get("context-tokens")]):
            if not guard(int(size) if size else None):
                return 2

    with open(os.path.join(prof_dir, "session_provenance.txt"), "a") as fh:
        fh.write(f"profile session start {time.strftime('%F %T')} cells={args.cells} "
                 f"cooldown={run_campaign.COOLDOWN}s sizes={sizes or 'per-cell context-tokens'}\n")

    incomplete = 0
    first = True
    try:
        for cell in cells:
            backend = cell["opts"]["backend"]
            p, d = NATIVE.match(cell["task"]).groups()
            cell_sizes = sizes or [int(cell["opts"]["context-tokens"]) if cell["opts"].get("context-tokens") else None]
            for ctx in cell_sizes:
                file_stem = os.path.splitext(os.path.basename(cell["opts"].get("file", "")))[0]
                tag = "_".join(x for x in (cell["model_id"].replace("/", "_"), file_stem, f"{p}x{d}",
                                           f"ctx{ctx}" if ctx else "") if x)
                cid = f"{run_campaign.cell_id(cell)} ctx={ctx or 'bundle-default'}"
                if os.path.exists(os.path.join(prof_dir, f"{tag}_{backend}_prof.log")):
                    note(skipped_path, f"CELL_SKIP {cid} reason=pair-already-stored ({tag}_{backend}); "
                                       "use a new --campaign")
                    continue
                out_dir = os.path.join(prof_dir, f"controls-ctx{ctx}") if sizes else speed_dir
                os.makedirs(out_dir, exist_ok=True)
                if not first:
                    time.sleep(int(cell["opts"].get("cooldown", run_campaign.COOLDOWN)))
                first = False
                try:
                    control_path = control_run(cell, ctx, out_dir)
                    raw_log = load_record(control_path)["provenance"]["rawLog"]
                    time.sleep(int(cell["opts"].get("cooldown", run_campaign.COOLDOWN)))
                    run_campaign.wait_nominal(prof_dir)
                    print(f"\n=== profile {cid} ({time.strftime('%H:%M:%S')})")
                    rec = profiled_run(cell, ctx, serial, args.timeout, prof_dir, control_path, tag, backend)
                    # the control's log joins the pair only once the twin is a real profile
                    shutil.copyfile(os.path.join(out_dir, raw_log),
                                    os.path.join(prof_dir, f"{tag}_{backend}_ctrl.log"))
                    print(f"profiled OK decode={rec['metrics'].get('decodeTokensPerSecond')} "
                          f"(control record {os.path.basename(control_path)})")
                except (PairError, SystemExit, RuntimeError, OSError, IndexError, KeyError) as e:
                    note(failures_path, f"{cid}: {e} - pair incomplete")
                    incomplete += 1
    finally:
        rc = subprocess.call([sys.executable, os.path.join(ROOT, "scripts", "profile", "profile_report.py"),
                              prof_dir])
        print(f"\nprofiles dir: {prof_dir}")
    return 1 if (incomplete or rc) else 0


if __name__ == "__main__":
    sys.exit(main())
