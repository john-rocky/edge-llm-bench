#!/usr/bin/env python3
"""K/r5/matrix_b.py — the K/MATRIX.md row of the round-5 session (read only; prints markdown): the same cell as
K/r2/matrix.py (Qwen3-1.7B GPU short-chat, wi4b32, runs=3) on m1q-36 with main-16ab54914, campaign
results/raw/2026-10-16-ddp-buildref-m1q-36-b-android. Its records are copied into a temp tree and
scripts/build_summary.build_device() runs with ROOT / OUT patched to it (results/summary/ on disk is never
written); pooled = render_leaderboard.arm_row of this session's runs alone. The columns are K/r2/matrix.py's.
Values only: no difference, no order."""
import csv
import glob
import json
import os
import shutil
import sys
import tempfile
from unittest.mock import patch

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import build_summary  # noqa: E402
import render_leaderboard  # noqa: E402

CELL = ("litert-lm-gpu", "litert-community/Qwen3-1.7B", "short-chat")
CAMPAIGN = "results/raw/2026-10-16-ddp-buildref-m1q-36-b-android"


def num(v, digits=2):
    try:
        return f"{round(float(v), digits):g}"
    except (TypeError, ValueError):
        return "—"


def rows_of_campaign():
    tmp = tempfile.mkdtemp(prefix="matrix-r5-")
    try:
        dst = os.path.join(tmp, CAMPAIGN, "app-path-android")
        os.makedirs(dst)
        for f in glob.glob(os.path.join(ROOT, CAMPAIGN, "app-path-android", "*.json")):
            shutil.copy(f, dst)
        with patch.object(build_summary, "ROOT", tmp), patch.object(build_summary, "OUT", os.path.join(tmp, "summary")):
            os.makedirs(build_summary.OUT)
            path, _ = build_summary.build_device()
        with open(path) as fh:
            rows = [r for r in csv.DictReader(fh) if r["campaign"] == CAMPAIGN
                    and (r["runtime"], r["model_id"], r["task"]) == CELL]
        return sorted(rows, key=lambda r: r["timestamp"] or "")
    finally:
        shutil.rmtree(tmp)


def main():
    rows = rows_of_campaign()
    recs = [json.load(open(os.path.join(ROOT, r["source"]))) for r in rows]
    pins = json.load(open(os.path.join(ROOT, "android", "engine-pins.json")))
    versions = sorted({r["engine_version"] for r in rows})
    built = pins["litert-lm"][versions[0]].get("built", "")
    commit = built.rsplit("commit ", 1)[-1].rstrip(")") if "commit " in built else "—"
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
        runs.append(f"{num(r['decode_tps'])} / {num(r['prefill_tps'])}†, {num(r['mem_resident_peak_mb'], 1)}, "
                    + ", ".join(flags))
    runs += ["—"] * (3 - len(runs))
    a = render_leaderboard.arm_row(rows)
    pooled = (f"{num(a['cold_median'])} ({a['cold_n']}) / {num(a['prefill'])}† / {num(a['mem_peak'], 1)} "
              f"({a['mem_peak_n']}) / {a['cpu_capped_counted_n']}"
              + (f" (max fall {num(a['cpu_capped_counted_max_drop'], 1)} %)"
                 if a['cpu_capped_counted_max_drop'] is not None else ""))
    print(f"| Qwen3-1.7B GPU short-chat (wi4b32, runs=3) | {' / '.join(versions)} ({commit}) | m1q-36, "
          f"{' / '.join(models)}, {' / '.join(serials)} | {' / '.join(sessions)} | " + " | ".join(runs[:3])
          + f" | {pooled} |")
    print(f"\n- arm_row campaign {a['campaign']}, engine {a['engine']}, pool n {a['n']}, records {len(rows)}")


if __name__ == "__main__":
    main()
