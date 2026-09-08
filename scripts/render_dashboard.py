#!/usr/bin/env python3
"""Render the dashboard table — the display surface behind the recurring job.

  ./bench dashboard                       # -> DASHBOARD.md + .dashboard/dashboard-v1.{csv,json}
  python3 scripts/render_dashboard.py --cells matrices/dashboard-text-v1.cells --stale-days 10
  python3 scripts/render_dashboard.py --check      # CI: render into a temp dir, exit 1 on error

One row per (device, model, arm) cell of the cells FILE, filled from
results/summary/device-runs.csv through render_leaderboard.arm_row — the one
aggregation (latest capture session per cell, never pooled across sessions,
firstEver rows excluded) — so the dashboard, LEADERBOARD.md and the charts
cannot show two numbers for one cell.

What this adds over LEADERBOARD.md:
  - the cells file is the authority: a cell with no rows renders "not yet
    measured", an exclude= cell renders its reason (failed-runs-stay), and
    rows that are not in the file are not shown.
  - session admission: a campaign whose SESSION.json (written by
    scripts/dashboard_job.py) says "admitted": false is dropped BEFORE arm_row
    picks the latest session, so an aborted sitting never displaces the last
    admitted one. Campaigns without SESSION.json (the first passes, hand-run
    sessions) stay admitted, as they were.
  - staleness: a cell older than --stale-days carries "stale", so a missed
    weekly slot shows in the table and not only in the job ledger.
  - no ranking: rows in cells-file order (light -> heavy), arm columns in a
    fixed alphabetical order. The recipe (artifact, quantization, engine pin)
    sits next to every number (quant-per-arm-rule); cold and warm are named,
    never mixed (cold-warm-split).

Every output is LOCAL and gitignored: the rendered table is cross-runtime
standings, which this repo does not publish (CLAUDE.md, owner decision
2026-08-27). Paste it into the team channel or read it here.
"""
import argparse
import csv
import datetime
import glob
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bench_common import (DEVICE_DISPLAY, atomic_write, bandwidth_ceiling,  # noqa: E402
                          bandwidth_utilization, fmt_bw, logical_model)
from render_leaderboard import SPREAD_FLAG, arm_row  # noqa: E402
from validate_cells import parse_line  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_CELLS = os.path.join("matrices", "dashboard-text-v1.cells")
DEFAULT_SCHEDULE = os.path.join("ops", "dashboard-v1", "schedule.json")
SUMMARY_CSV = os.path.join(ROOT, "results", "summary", "device-runs.csv")
# cells-file platform token -> device-runs.csv platform value
CSV_PLATFORM = {"ios": "ios", "mac": "mac", "android": "android"}
# headline regime per platform: Apple lanes have in-process warm runs, the
# Android CLIs do not (methodology/android.md) — the column header says which
REGIME = {"ios": "warm", "mac": "warm", "android": "cold"}


def rel(p):
    return os.path.relpath(p, ROOT)


def arm_of(plat, runtime, opts):
    """The arm id as device-runs.csv records it: Android litert carries its
    backend in the runtime string (litert-lm-cpu / litert-lm-gpu)."""
    if plat == "android" and runtime == "litert-lm" and opts.get("backend"):
        return f"{runtime}-{opts['backend']}"
    return runtime


def model_row(mid):
    """Dashboard row label = the model block (family + size). LOGICAL_MODELS
    keeps recipe variants apart ("Gemma 4 E2B (QAT OptiQ)") so pivots never
    pool them; here the cell key is (arm, model_id), nothing pools, and the
    recipe travels in the detail table — so the parenthetical comes off the
    row label. load_cells restores it where two cells of one arm would
    otherwise share a row (the CQ4 lineages case)."""
    name = logical_model(mid)
    return name.split(" (", 1)[0] if " (" in name else name


def load_cells(path):
    """Active + excluded cells of the file, in file order."""
    cells = []
    with open(path) as fh:
        for lineno, raw in enumerate(fh, 1):
            line = raw.split("#", 1)[0].strip()
            if not line:
                continue
            plat, rt, mid, task, opts = parse_line(line)
            if opts.get("manual") == "1":
                continue
            cells.append({
                "platform": plat, "runtime": rt, "arm": arm_of(plat, rt, opts),
                "model_id": mid, "task": task, "opts": opts, "line": lineno,
                "model": model_row(mid), "exclude": opts.get("exclude"),
                "anchor": opts.get("anchor") == "1",
            })
    # two artifacts of one arm on one row would collide in the matrix view —
    # give those cells their full logical name back (recipe visible in the row)
    seen = {}
    for c in cells:
        seen.setdefault((c["platform"], c["model"], c["arm"], c["task"]), []).append(c)
    for group in seen.values():
        if len(group) > 1:
            for c in group:
                c["model"] = logical_model(c["model_id"])
    return cells


def load_admission():
    """campaign (results/raw/<name>) -> admitted? from the job's SESSION.json.
    Absent file = admitted (hand-run and first-pass sessions)."""
    out = {}
    for f in glob.glob(os.path.join(ROOT, "results", "raw", "*", "SESSION.json")):
        try:
            d = json.load(open(f))
        except (OSError, ValueError):
            continue
        out[rel(os.path.dirname(f))] = bool(d.get("admitted", True))
    return out


def load_schedule(path):
    if not os.path.exists(path):
        return {}
    return json.load(open(path))


def devices_for(plat, schedule, rows):
    """(csv device identifier, display) per platform: the schedule's devices
    first, then anything else the accumulation layer has seen there."""
    out = []
    for dev in schedule.get("devices", {}).values():
        if CSV_PLATFORM.get({"iphone": "ios"}.get(dev["platform"], dev["platform"])) == plat:
            out.append((dev["identifier"], dev.get("display") or dev["identifier"]))
    seen = {d for d, _ in out}
    for ident in sorted({r["device"] for r in rows if r["platform"] == plat and r["device"]}):
        if ident not in seen:
            out.append((ident, DEVICE_DISPLAY.get(ident, ident)))
    return out


def fmt(v, nd=1):
    return "—" if v is None else f"{v:.{nd}f}"


def bw_of(c):
    """The bandwidth_utilization dict a rendered cell carries (None when n/a)."""
    if c.get("bw_util_pct") is None:
        return None
    return {"pct": c["bw_util_pct"], "bytes": c["artifact_bytes"],
            "gbps": c["bw_ceiling_gbps"], "basis": c["bw_basis"]}


def build(cells_path, schedule_path, stale_days, today):
    rows = list(csv.DictReader(open(SUMMARY_CSV))) if os.path.exists(SUMMARY_CSV) else []
    admitted = load_admission()
    rows = [r for r in rows if admitted.get(r["campaign"], True)]
    cells = load_cells(cells_path)
    schedule = load_schedule(schedule_path)

    out_cells = []
    for plat in ("mac", "ios", "android"):
        plat_cells = [c for c in cells if c["platform"] == plat]
        if not plat_cells:
            continue
        for ident, display in devices_for(plat, schedule, rows):
            for c in plat_cells:
                sel = [r for r in rows
                       if r["platform"] == plat and r["device"] == ident
                       and r["runtime"] == c["arm"] and r["model_id"] == c["model_id"]
                       and r["task"] == c["task"]]
                rec = {
                    "platform": plat, "device": ident, "device_display": display,
                    "regime": REGIME[plat], "model": c["model"], "arm": c["arm"],
                    "model_id": c["model_id"], "task": c["task"], "anchor": c["anchor"],
                    "status": "missing", "reason": "", "decode_tps": None,
                    "spread_pct": None, "n": 0, "prefill_tps": None, "ttft_ms": None,
                    "mem_mb": None, "quant": "", "engine": "", "captured": "",
                    "campaign": "", "thermal_initial": "", "stale": False,
                    # bw util: decode tok/s x bytes per token / the device ceiling
                    # (bench_common.bandwidth_utilization; both registries cited).
                    # stream_bytes = the per-token figure the column uses (the
                    # artifact minus per-token-gathered tables where registered)
                    "artifact_bytes": None, "stream_bytes": None, "bw_ceiling_gbps": None,
                    "bw_basis": "", "bw_util_pct": None,
                }
                if c["exclude"]:
                    rec.update(status="excluded", reason=c["exclude"])
                elif sel:
                    a = arm_row(sel)
                    if REGIME[plat] == "warm":
                        dec, spread, n = a["warm"], a["spread"], a["warm_n"]
                    else:
                        dec, spread, n = a["cold_median"], a["cold_spread"], a["cold_n"]
                    captured = a["date"]
                    stale = False
                    if captured:
                        age = (today - datetime.date.fromisoformat(captured)).days
                        stale = age > stale_days
                    rec.update(status="measured" if dec else "no-decode",
                               decode_tps=dec, spread_pct=spread, n=n,
                               prefill_tps=a["prefill"], ttft_ms=a["ttft"],
                               mem_mb=a["mem"], quant=a["quant"], engine=a["engine"],
                               captured=captured, campaign=a["campaign"],
                               thermal_initial=",".join(a["thermal_initial"]),
                               stale=stale)
                    u = bandwidth_utilization(dec, c["arm"], c["model_id"], ident, plat)
                    if u:
                        rec.update(artifact_bytes=u["artifact_bytes"], stream_bytes=u["bytes"],
                                   bw_ceiling_gbps=u["gbps"], bw_basis=u["basis"],
                                   bw_util_pct=u["pct"])
                out_cells.append(rec)
    return out_cells, cells


def render_md(out_cells, cells_path, stale_days, today):
    L = []
    L.append(f"# Dashboard v1 — `{rel(cells_path)}`")
    L.append("")
    L.append(f"Rendered {today.isoformat()} by `scripts/render_dashboard.py` from "
             "`results/summary/device-runs.csv` (the same `arm_row` aggregation as "
             "LEADERBOARD.md: latest admitted capture session per cell, never pooled "
             "across sessions, cache-build runs excluded). Local file — the repo does "
             "not publish cross-runtime standings.")
    L.append("")
    L.append("Reading rules: **warm** = median of same-session warm runs (Apple lanes); "
             "**cold** = median of the session's fresh-process runs (Android v1 has no "
             "warm regime). Arms compare only within one device and one model; each cell "
             "runs its arm's own published recipe (artifact, quantization, engine pin in "
             "the detail table) — a different recipe is a different deployment profile, "
             "not a win. Columns are alphabetical, rows are in cells-file order; nothing "
             "is ranked. `⚠ N%` = trial spread above the "
             f"{SPREAD_FLAG:.0f}% bar (spread-rule; Android cold trials legitimately "
             f"spread wider, the mark is information, not a verdict). `stale` = older "
             f"than {stale_days} days. Short-chat prefill is overhead-dominated and does "
             "not compare across arms (docs/OPERATIONS.md); it is listed, not headlined. "
             "`bw N%` = decode tok/s × bytes per token ÷ the device's memory-bandwidth "
             "ceiling (`devices/memory-bandwidth.json`, cited per device below): the share "
             "of the memory bus the arm turns into tokens, which reads the recipe — a 4-bit "
             "and an 8-bit artifact of one model are different byte counts. Bytes per token "
             "= the artifact's weight bytes minus the tables a decode step gathers instead of "
             "streams (Gemma 4's per-layer-embedding table, a LiteRT bundle's separate "
             "input-embedding table, audio/vision/drafter sections), from "
             "`models/artifact-bytes.json` (`scripts/artifact_streamed_bytes.py`); tied "
             "embeddings stay counted as the LM head. `~` marks a ceiling that is a "
             "derivation or an estimate, not a vendor figure; n/a where no ceiling is "
             "citable or the artifact is unregistered. An estimate, not a bus counter.")
    L.append("")

    by_dev = {}
    for c in out_cells:
        by_dev.setdefault((c["platform"], c["device"], c["device_display"]), []).append(c)
    for (plat, ident, display), dcells in by_dev.items():
        arms = sorted({c["arm"] for c in dcells})
        models = []
        for c in dcells:
            if c["model"] not in models:
                models.append(c["model"])
        measured = sum(1 for c in dcells if c["status"] == "measured")
        excluded = sum(1 for c in dcells if c["status"] == "excluded")
        missing = sum(1 for c in dcells if c["status"] in ("missing", "no-decode"))
        dates = sorted({c["captured"] for c in dcells if c["captured"]})
        engines = sorted({c["engine"] for c in dcells if c["engine"]})
        L.append(f"## {display} — `{ident}`, {plat}, headline regime **{REGIME[plat]}**")
        L.append("")
        L.append(f"{measured} of {len(dcells)} cells measured"
                 + (f", {excluded} excluded with a reason" if excluded else "")
                 + (f", {missing} not yet measured" if missing else "")
                 + (f"; captures {dates[0]} .. {dates[-1]}" if dates else "")
                 + (f"; engines observed: {', '.join(engines)}" if engines else "") + ".")
        gbps, basis, source = bandwidth_ceiling(ident)
        if gbps:
            L.append(f"Memory-bandwidth ceiling for `bw`: {gbps:g} GB/s ({basis}) — {source}")
        else:
            L.append(f"Memory-bandwidth ceiling for `bw`: n/a ({basis}) — {source or 'no entry in devices/memory-bandwidth.json'}")
        L.append("")
        L.append("| model | " + " | ".join(f"{a} ({REGIME[plat]} tok/s)" for a in arms) + " |")
        L.append("|---|" + "---|" * len(arms))
        for m in models:
            line = [f"**{m}**"]
            for a in arms:
                c = next((x for x in dcells if x["model"] == m and x["arm"] == a), None)
                if c is None:
                    line.append("·")
                elif c["status"] == "excluded":
                    line.append(f"— ({c['reason']})")
                elif c["status"] == "missing":
                    line.append("not yet measured")
                elif c["status"] == "no-decode":
                    line.append("— (records without a decode figure)")
                else:
                    t = fmt(c["decode_tps"])
                    if c["spread_pct"] is not None and c["spread_pct"] > SPREAD_FLAG:
                        t += f" ⚠ {c['spread_pct']:.0f}%"
                    if c["bw_util_pct"] is not None:
                        t += f" · bw {fmt_bw(bw_of(c))}"
                    if c["stale"]:
                        t += " · stale"
                    line.append(t)
            L.append("| " + " | ".join(line) + " |")
        L.append("")
        L.append("<details><summary>per-cell detail (recipe, session, memory, prefill, bandwidth)</summary>")
        L.append("")
        L.append("| model | arm | artifact | quant | engine | decode tok/s | spread % | n | "
                 "artifact MB | MB/token | bw util | prefill tok/s | TTFT ms | mem MB | "
                 "thermal at start | captured | session |")
        L.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
        for c in dcells:
            if c["status"] == "excluded":
                L.append(f"| {c['model']} | {c['arm']} | `{c['model_id']}` | | | — ({c['reason']}) "
                         "| | | | | | | | | | | |")
                continue
            if c["status"] == "missing":
                L.append(f"| {c['model']} | {c['arm']} | `{c['model_id']}` | | | not yet measured "
                         "| | | | | | | | | | | |")
                continue
            mb = f"{c['artifact_bytes'] / 1e6:.0f}" if c["artifact_bytes"] else "—"
            tok = f"{c['stream_bytes'] / 1e6:.0f}" if c["stream_bytes"] else "—"
            L.append(
                f"| {c['model']} | {c['arm']} | `{c['model_id']}` | {c['quant']} | {c['engine']} | "
                f"{fmt(c['decode_tps'])} | {fmt(c['spread_pct'])} | {c['n']} | "
                f"{mb} | {tok} | {fmt_bw(bw_of(c)) if c['bw_util_pct'] is not None else 'n/a'} | "
                f"{fmt(c['prefill_tps'])} | {fmt(c['ttft_ms'], 0)} | {fmt(c['mem_mb'], 0)} | "
                f"{c['thermal_initial'] or '—'} | {c['captured']}{' (stale)' if c['stale'] else ''} | "
                f"`{os.path.basename(c['campaign'])}` |")
        L.append("")
        L.append("mem MB = phys_footprint on Apple rows, VmRSS on Android rows (the GPU "
                 "arm's buffers sit outside RSS; methodology/android.md). artifact MB = "
                 "decimal megabytes of the whole artifact; MB/token = the bytes a decode step "
                 "reads (artifact minus per-token-gathered tables, models/artifact-bytes.json); "
                 "bw util = decode tok/s × MB/token ÷ this device's ceiling.")
        L.append("")
        L.append("</details>")
        L.append("")
    return "\n".join(L) + "\n"


CSV_FIELDS = ["platform", "device", "device_display", "regime", "model", "arm", "model_id",
              "task", "anchor", "status", "reason", "decode_tps", "spread_pct", "n",
              "prefill_tps", "ttft_ms", "mem_mb", "quant", "engine", "thermal_initial",
              "captured", "campaign", "stale",
              "artifact_bytes", "stream_bytes", "bw_ceiling_gbps", "bw_basis", "bw_util_pct"]


def write_outputs(out_cells, md, md_path, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    with atomic_write(md_path, "w") as fh:
        fh.write(md)
    with atomic_write(os.path.join(out_dir, "dashboard-v1.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        w.writeheader()
        for c in out_cells:
            row = {k: c.get(k) for k in CSV_FIELDS}
            for k in ("decode_tps", "spread_pct", "prefill_tps", "ttft_ms", "mem_mb", "bw_util_pct"):
                if isinstance(row[k], float):
                    row[k] = round(row[k], 2)
            w.writerow(row)
    with atomic_write(os.path.join(out_dir, "dashboard-v1.json"), "w") as fh:
        json.dump({"generated": datetime.datetime.now().isoformat(timespec="seconds"),
                   "cells": out_cells}, fh, indent=1)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cells", default=os.path.join(ROOT, DEFAULT_CELLS))
    ap.add_argument("--schedule", default=os.path.join(ROOT, DEFAULT_SCHEDULE))
    ap.add_argument("--stale-days", type=int, default=None,
                    help="default: schedule.json stale_days, else 10")
    ap.add_argument("--md", default=os.path.join(ROOT, "DASHBOARD.md"))
    ap.add_argument("--out-dir", default=os.path.join(ROOT, ".dashboard"))
    ap.add_argument("--check", action="store_true",
                    help="render into a temp dir only (CI: the script runs on the shipped raw)")
    args = ap.parse_args()
    stale_days = args.stale_days
    if stale_days is None:
        stale_days = load_schedule(args.schedule).get("stale_days", 10)
    today = datetime.date.today()
    out_cells, cells = build(args.cells, args.schedule, stale_days, today)
    md = render_md(out_cells, args.cells, stale_days, today)
    if args.check:
        tmp = tempfile.mkdtemp(prefix="dashboard-check-")
        write_outputs(out_cells, md, os.path.join(tmp, "DASHBOARD.md"), tmp)
        print(f"rendered {len(out_cells)} device-cells from {len(cells)} file cells into {tmp}")
        return 0
    write_outputs(out_cells, md, args.md, args.out_dir)
    n_meas = sum(1 for c in out_cells if c["status"] == "measured")
    n_stale = sum(1 for c in out_cells if c["stale"])
    print(f"wrote {rel(args.md)} and {rel(args.out_dir)}/dashboard-v1.{{csv,json}}: "
          f"{n_meas} measured of {len(out_cells)} device-cells"
          f"{f', {n_stale} stale' if n_stale else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
