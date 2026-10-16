#!/usr/bin/env python3
"""K/r2/matrix.py — the rows of K/MATRIX.md (read only; prints markdown). Four rows of one cell, the
Qwen3-1.7B GPU short-chat (wi4b32 file, runs=3), each one DDP session = one job on one lab unit:
  main@HEAD   results/raw/2026-10-16-ddp-buildref-<id>-android: its records copied into a temp tree,
              scripts/build_summary.build_device() run with ROOT / OUT patched to that tree (the
              android/ddp/selftest.py check_summary form), so results/summary/ on disk is never written
  v0.18.0     the committed rows of results/summary/device-runs.csv (git show HEAD:) of
              results/raw/2026-10-15-ddp-slice-<id>-android
The pooled values are render_leaderboard.arm_row of each row's runs alone (one session each; Android
runs are cold processes, so the decode value is cold_median; firstEver run 1 is outside every pool).
Per run: decode / prefill (promptTokensPerSecond) tok/s, peak resident MB, and from the record
conditions.protocolFlags, conditions.engineCache.gpuCache, firstEver. Values only: no difference, no order."""
import csv
import glob
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from unittest.mock import patch

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import build_summary  # noqa: E402
import render_leaderboard  # noqa: E402

CELL = ("litert-lm-gpu", "litert-community/Qwen3-1.7B", "short-chat")
IDS = ("akita-35", "m1q-36")
NEW = "results/raw/2026-10-16-ddp-buildref-{}-android"
OLD = "results/raw/2026-10-15-ddp-slice-{}-android"


def num(v, digits=2):
    try:
        return f"{round(float(v), digits):g}"
    except (TypeError, ValueError):
        return "—"


def cell_rows(rows, campaign):
    return sorted((r for r in rows if r["campaign"] == campaign and (r["runtime"], r["model_id"], r["task"]) == CELL),
                  key=lambda r: r["timestamp"] or "")


def new_rows():
    tmp = tempfile.mkdtemp(prefix="matrix-r2-")
    try:
        for i in IDS:
            src = os.path.join(ROOT, NEW.format(i), "app-path-android")
            dst = os.path.join(tmp, NEW.format(i), "app-path-android")
            os.makedirs(dst)
            for f in glob.glob(os.path.join(src, "*.json")):
                shutil.copy(f, dst)
        with patch.object(build_summary, "ROOT", tmp), patch.object(build_summary, "OUT", os.path.join(tmp, "summary")):
            os.makedirs(build_summary.OUT)
            path, _ = build_summary.build_device()
        with open(path) as fh:
            return list(csv.DictReader(fh))
    finally:
        shutil.rmtree(tmp)


def committed_rows():
    text = subprocess.run(["git", "-C", ROOT, "show", "HEAD:results/summary/device-runs.csv"],
                          capture_output=True, text=True, check=True).stdout
    return list(csv.DictReader(io.StringIO(text)))


def engine_commit(version, records):
    if version.startswith("main-"):
        pins = json.load(open(os.path.join(ROOT, "android", "engine-pins.json")))
        built = pins["litert-lm"][version].get("built", "")
        return built.rsplit("commit ", 1)[-1].rstrip(")") if "commit " in built else "—"
    return "tag " + version


def main():
    groups = []
    fresh, old = new_rows(), committed_rows()
    for i in IDS:
        groups.append((i, NEW.format(i), cell_rows(fresh, NEW.format(i))))
        groups.append((i, OLD.format(i), cell_rows(old, OLD.format(i))))
    print("| cell | engine (label, commit) | device (id, ro.product.model, serial) | session "
          "| run 1: decode / prefill tok/s, peak MB, flags | run 2 | run 3 "
          "| pooled (arm_row): decode cold_median (n) / prefill median / peak MB median (n) / capped counted |")
    print("|---|---|---|---|---|---|---|---|")
    notes = []
    for dev_id, campaign, rows in groups:
        recs = [json.load(open(os.path.join(ROOT, r["source"]))) for r in rows]
        if not rows:
            print(f"| {' '.join(CELL)} | — | {dev_id} | {campaign}: no rows | | | | |")
            continue
        versions = sorted({r["engine_version"] for r in rows})
        serials = sorted({rec["conditions"]["ddp"]["serial"] for rec in recs})
        models = sorted({rec["device"]["modelIdentifier"] for rec in recs})
        sessions = sorted({rec["conditions"]["ddp"]["sessionId"] for rec in recs})
        runs = []
        for r, rec in zip(rows, recs):
            c = rec["conditions"]
            flags = list(c.get("protocolFlags") or [])
            flags.append("gpuCache " + str((c.get("engineCache") or {}).get("gpuCache")))
            if rec["metrics"].get("firstEver"):
                flags.append("firstEver")
            runs.append(f"{num(r['decode_tps'])} / {num(r['prefill_tps'])}, {num(r['mem_resident_peak_mb'], 1)}, "
                        + ", ".join(flags))
        runs += ["—"] * (3 - len(runs))
        a = render_leaderboard.arm_row(rows)
        pooled = (f"{num(a['cold_median'])} ({a['cold_n']}) / {num(a['prefill'])} / {num(a['mem_peak'], 1)} "
                  f"({a['mem_peak_n']}) / {a['cpu_capped_counted_n']}"
                  + (f" (max fall {num(a['cpu_capped_counted_max_drop'], 1)} %)"
                     if a['cpu_capped_counted_max_drop'] is not None else ""))
        engine = f"{' / '.join(versions)} ({engine_commit(versions[0], recs)})"
        print(f"| Qwen3-1.7B GPU short-chat (wi4b32, runs=3) | {engine} | {dev_id}, {' / '.join(models)}, "
              f"{' / '.join(serials)} | {' / '.join(sessions)} | " + " | ".join(runs[:3]) + f" | {pooled} |")
        notes.append((dev_id, versions[0], serials, sessions, campaign, a["campaign"], a["n"], a["engine"]))
    print()
    for dev_id, version, serials, sessions, campaign, arm_campaign, n, arm_engine in notes:
        print(f"- {dev_id} {version}: {campaign} (arm_row campaign {arm_campaign}, engine {arm_engine}, "
              f"pool n {n}), serial {' / '.join(serials)}, {' / '.join(sessions)}")


if __name__ == "__main__":
    main()
