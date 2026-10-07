#!/usr/bin/env python3
"""Render the dashboard table — the display surface behind the recurring job.

  ./bench dashboard                       # -> DASHBOARD.md + .dashboard/dashboard-v1.{csv,json}
  python3 scripts/render_dashboard.py --cells matrices/dashboard-text-v1.cells --stale-days 10
  python3 scripts/render_dashboard.py --check      # CI: render into a temp dir, exit 1 on error

One row per (device, model, arm, task, context-tokens) cell of the cells FILE,
filled from results/summary/device-runs.csv through render_leaderboard.arm_row —
the one aggregation (latest capture session per cell, never pooled across
sessions, firstEver rows excluded) — so the dashboard, LEADERBOARD.md and the
charts cannot show two numbers for one cell. A cell with context-tokens= reads
only the rows recorded at that allocation (the long-context ladder is three
cells, not one pooled cell); a cell without it reads every row of its key.

What this adds over LEADERBOARD.md:
  - the cells file is the authority: a cell with no rows renders "not yet
    measured", an exclude= cell renders its reason (failed-runs-stay), an
    exclude-on=<device key>:<reason> cell renders its reason on the devices it
    names (schedule.json key -> the identifier the rows carry) and its number
    everywhere else, and rows that are not in the file are not shown.
  - session admission: a campaign whose SESSION.json (written by
    scripts/dashboard_job.py) says "admitted": false is dropped BEFORE arm_row
    picks the latest session, so an aborted sitting never displaces the last
    admitted one. Campaigns without SESSION.json (the first passes, hand-run
    sessions) stay admitted, as they were.
  - staleness: a cell older than --stale-days carries "stale", so a missed
    weekly slot shows in the table and not only in the job ledger.
  - text check (text-check-rule): arm_row keeps runs whose decoded text
    failed the check out of the pool; a cell left with no headline number
    for that reason renders "— (text check failed: <flags> (k of N runs))"
    (status text-fail), and the detail table's "text fail" column says how
    many runs of a measured cell left the pool (— = the text was not checked).
  - CPU cap (cpu-cap-rule): arm_row keeps runs during which a CPU the engine
    ran on sat below its hardware maximum clock out of the pool the same way;
    a cell left with no headline number for that reason renders
    "— (no valid run: cpu-capped (k of N runs))" (status cpu-capped), and the
    "cpu capped" column says how many runs left the pool (— = caps not read).
  - no ranking: one grid per (device, task), rows in cells-file order
    (light -> heavy; a context-tokens= cell gets its own row per allocation),
    arm columns in a fixed alphabetical order. The recipe (artifact, quantization, engine pin)
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
from validate_cells import parse_exclude_on, parse_line  # noqa: E402

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
    backend in the runtime string (litert-lm-cpu / litert-lm-gpu / litert-lm-npu),
    and so does an Android llama.cpp side build on its npu / gpu device
    (llama.cpp-npu / llama.cpp-gpu; without backend= the row is the CPU arm,
    bare `llama.cpp`); the Mac CPU arm stamps litert-lm-cpu too, while the Mac
    GPU arm keeps the bare `litert-lm` every Apple row has carried (yardstick
    --litert-backend). onnxruntime-genai carries its backend on every platform
    (onnxruntime-genai-cpu / onnxruntime-genai-webgpu)."""
    if runtime == "onnxruntime-genai" and opts.get("backend"):
        return f"{runtime}-{opts['backend']}"
    if plat == "android" and runtime in ("litert-lm", "llama.cpp") and opts.get("backend"):
        return f"{runtime}-{opts['backend']}"
    if plat == "mac" and runtime == "litert-lm" and opts.get("backend") == "cpu":
        return f"{runtime}-cpu"
    # executorch carries its delegate on every platform (executorch-xnnpack, …;
    # docs/executorch-arm-v1.md)
    if runtime == "executorch" and opts.get("backend"):
        return f"{runtime}-{opts['backend']}"
    return runtime


def model_row(mid):
    """Dashboard row label = the model block (family + size). LOGICAL_MODELS
    keeps recipe variants apart ("Gemma 4 E2B (QAT OptiQ)") so pivots never
    pool them; here the cell key is (arm, model_id, task, allocation), nothing pools, and the
    recipe travels in the detail table — so the parenthetical comes off the
    row label. load_cells restores it where two cells of one arm would
    otherwise share a row (the CQ4 lineages case)."""
    name = logical_model(mid)
    return name.split(" (", 1)[0] if " (" in name else name


def ctx_key(v):
    """A KV allocation as the summary's context_tokens column spells it: digits,
    or "" for none (build_summary.context_tokens_of)."""
    v = str(v or "").strip()
    return str(int(v)) if v.isdigit() else ""


def artifact_tag(c):
    """Which artifact a cell runs, short: the file= name when the cell names one,
    else the model id after its org. Shown only where two cells share a grid slot."""
    if c["opts"].get("file"):
        return os.path.basename(c["opts"]["file"])
    return c["model_id"].split("/", 1)[-1]


def grid_sections(dcells):
    """One device's cells as [(task, arms, [(row label key, [cells per arm slot])])]:
    a grid per task in cells-file order, rows = (model, allocation) in file order.
    A slot holding two cells (two artifacts of one arm on one row) keeps both —
    the grid never hides a cell of the file."""
    sections = []
    for task in dict.fromkeys(c["task"] for c in dcells):
        tcells = [c for c in dcells if c["task"] == task]
        arms = sorted({c["arm"] for c in tcells})
        rows = list(dict.fromkeys((c["model"], c["context_tokens"]) for c in tcells))
        grid = [((m, ctx), {a: [c for c in tcells if (c["model"], c["context_tokens"], c["arm"])
                                == (m, ctx, a)] for a in arms}) for m, ctx in rows]
        sections.append((task, arms, grid))
    return sections


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
                # {schedule.json device key: reason}; exclusion() reads it per device
                "exclude_on": parse_exclude_on(opts["exclude-on"]) if opts.get("exclude-on") else {},
                "anchor": opts.get("anchor") == "1",
                "context_tokens": ctx_key(opts.get("context-tokens")),
            })
    # two artifacts of one arm on one row would collide in the matrix view —
    # give those cells their full logical name back (recipe visible in the row);
    # one artifact at several context-tokens= allocations is a row per
    # allocation (grid_sections), not two artifacts
    seen = {}
    for c in cells:
        seen.setdefault((c["platform"], c["model"], c["arm"], c["task"]), []).append(c)
    for group in seen.values():
        if len({(c["model_id"], c["opts"].get("file")) for c in group}) > 1:
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


def device_keys(schedule):
    """device identifier (the rows' device column) -> the schedule.json device
    keys that carry it; exclude-on= names devices by key."""
    out = {}
    for key, dev in schedule.get("devices", {}).items():
        out.setdefault(dev.get("identifier"), set()).add(key)
    return out


def exclusion(c, keys):
    """Why cell `c` is not a measurement on the device with these schedule keys,
    or None: its exclude= (every device), else the exclude-on= reason of one of
    the keys. The one rule for this table and the team page (litert-bench-dashboard)."""
    if c.get("exclude"):
        return c["exclude"]
    on = c.get("exclude_on") or {}
    return next((on[k] for k in sorted(keys) if k in on), None)


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


# the memory columns' reading note, shared with render_dashboard_html
MEM_NOTE = ("mem MB / mem peak MB = the median over the session's runs of each run's median "
            "sample / high-water mark: phys_footprint on Apple rows (sampled every 100 ms over "
            "the generation, load excluded), VmRSS / VmHWM of the engine process on Android rows "
            "(read every 0.5 s over the whole launch, load included; a GPU or NPU arm's device "
            "buffers sit outside RSS; before 2026-10-06 only the BENCH_STRICT_SMOKE sittings read VmHWM, so "
            "older Android short-chat cells show —), the process RSS high-water on uzu rows "
            "(load included, decimal MB) — methodology/memory.md \"Peak memory\".")


def grid_text(c):
    """A grid cell's text: the headline decode with its flags, or why there is none."""
    if c["status"] in ("excluded", "text-fail"):
        return f"— ({c['reason']})"
    if c["status"] == "cpu-capped":
        return f"— (no valid run: {c['reason']})"
    if c["status"] == "missing":
        return "not yet measured"
    if c["status"] == "no-decode":
        return "— (records without a decode figure)"
    t = fmt(c["decode_tps"])
    if c["spread_pct"] is not None and c["spread_pct"] > SPREAD_FLAG:
        t += f" ⚠ {c['spread_pct']:.0f}%"
    if c["bw_util_pct"] is not None:
        t += f" · bw {fmt_bw(bw_of(c))}"
    if c["stale"]:
        t += " · stale"
    return t


def build(cells_path, schedule_path, stale_days, today):
    rows = list(csv.DictReader(open(SUMMARY_CSV))) if os.path.exists(SUMMARY_CSV) else []
    admitted = load_admission()
    rows = [r for r in rows if admitted.get(r["campaign"], True)]
    cells = load_cells(cells_path)
    schedule = load_schedule(schedule_path)
    keys_of = device_keys(schedule)

    out_cells = []
    for plat in ("mac", "ios", "android"):
        plat_cells = [c for c in cells if c["platform"] == plat]
        if not plat_cells:
            continue
        for ident, display in devices_for(plat, schedule, rows):
            for c in plat_cells:
                why = exclusion(c, keys_of.get(ident, ()))
                sel = [r for r in rows
                       if r["platform"] == plat and r["device"] == ident
                       and r["runtime"] == c["arm"] and r["model_id"] == c["model_id"]
                       and r["task"] == c["task"]
                       and (not c["context_tokens"]
                            or ctx_key(r.get("context_tokens")) == c["context_tokens"])]
                rec = {
                    "platform": plat, "device": ident, "device_display": display,
                    "regime": REGIME[plat], "model": c["model"], "arm": c["arm"],
                    "model_id": c["model_id"], "task": c["task"], "anchor": c["anchor"],
                    "status": "missing", "reason": "", "decode_tps": None,
                    "spread_pct": None, "n": 0, "prefill_tps": None, "ttft_ms": None,
                    "mem_mb": None, "quant": "", "engine": "", "captured": "",
                    "campaign": "", "thermal_initial": "", "stale": False,
                    # the cell's context-tokens= ("" = none: every allocation's rows)
                    # and the median per-run memory high-water (arm_row mem_peak)
                    "context_tokens": c["context_tokens"], "mem_peak_mb": None,
                    "artifact_tag": artifact_tag(c),
                    # bw util: decode tok/s x bytes per token / the device ceiling
                    # (bench_common.bandwidth_utilization; both registries cited).
                    # stream_bytes = the per-token figure the column uses (the
                    # artifact minus per-token-gathered tables where registered)
                    "artifact_bytes": None, "stream_bytes": None, "bw_ceiling_gbps": None,
                    "bw_basis": "", "bw_util_pct": None,
                    # "k/N": runs of the session the text check kept out of the pool,
                    # of the runs that would have pooled; "" = text not checked
                    "text_fail": "",
                    # "k/N": the same for the CPU cap (cpu-cap-rule); "" = caps not read
                    "cpu_capped": "",
                }
                if why:
                    rec.update(status="excluded", reason=why)
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
                               mem_mb=a["mem"], mem_peak_mb=a["mem_peak"],
                               quant=a["quant"], engine=a["engine"],
                               captured=captured, campaign=a["campaign"],
                               thermal_initial=",".join(a["thermal_initial"]),
                               stale=stale)
                    # the session's runs that would have pooled (cache-build runs aside)
                    would = a["n"] + a["text_fail_n"] + a["cpu_capped_n"]
                    if a["text_checked_n"]:
                        rec["text_fail"] = f"{a['text_fail_n']}/{would}"
                    if a["cpu_read_n"]:
                        rec["cpu_capped"] = f"{a['cpu_capped_n']}/{would}"
                    if not dec and a["text_fail_n"]:
                        # text-check-rule: no headline because the text check emptied
                        # the pool — the reason is the datum, never the rate
                        rec.update(status="text-fail", spread_pct=None,
                                   reason=f"text check failed: {a['text_fail_flags']} "
                                          f"({a['text_fail_n']} of {would} runs)")
                    elif not dec and a["cpu_capped_n"]:
                        # cpu-cap-rule: no headline because every run that could give it
                        # ran under a CPU frequency cap — no valid run, never the rate
                        rec.update(status="cpu-capped", spread_pct=None,
                                   reason=f"cpu-capped ({a['cpu_capped_n']} of {would} runs)")
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
             "not a win. One grid per device and task; columns are alphabetical, rows are in "
             "cells-file order, a cell that pins `context-tokens=` gets a row per allocation "
             "(`ctx N`), and a slot holding two artifacts of one arm lists both, named; nothing "
             "is ranked. `⚠ N%` = trial spread above the "
             f"{SPREAD_FLAG:.0f}% bar (spread-rule; Android cold trials legitimately "
             f"spread wider, the mark is information, not a verdict). `stale` = older "
             f"than {stale_days} days. `— (text check failed: …)` = every run of the "
             "session that could have given the cell's number failed the decoded-text "
             "check (empty, off-task or looping text), so none is shown "
             "(text-check-rule; the runs stay in raw). `— (no valid run: cpu-capped …)` = "
             "every such run ran while the phone held a CPU the engine ran on below its "
             "hardware maximum clock (seen on a charging phone with the thermal status "
             "still 0), so none is shown (cpu-cap-rule; the runs stay in raw). "
             "Short-chat prefill is "
             "overhead-dominated and does "
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
        measured = sum(1 for c in dcells if c["status"] == "measured")
        excluded = sum(1 for c in dcells if c["status"] == "excluded")
        text_failed = sum(1 for c in dcells if c["status"] == "text-fail")
        cpu_capped = sum(1 for c in dcells if c["status"] == "cpu-capped")
        missing = sum(1 for c in dcells if c["status"] in ("missing", "no-decode"))
        dates = sorted({c["captured"] for c in dcells if c["captured"]})
        engines = sorted({c["engine"] for c in dcells if c["engine"]})
        L.append(f"## {display} — `{ident}`, {plat}, headline regime **{REGIME[plat]}**")
        L.append("")
        L.append(f"{measured} of {len(dcells)} cells measured"
                 + (f", {excluded} excluded with a reason" if excluded else "")
                 + (f", {text_failed} failed the text check" if text_failed else "")
                 + (f", {cpu_capped} had no valid run (cpu-capped)" if cpu_capped else "")
                 + (f", {missing} not yet measured" if missing else "")
                 + (f"; captures {dates[0]} .. {dates[-1]}" if dates else "")
                 + (f"; engines observed: {', '.join(engines)}" if engines else "") + ".")
        gbps, basis, source = bandwidth_ceiling(ident)
        if gbps:
            L.append(f"Memory-bandwidth ceiling for `bw`: {gbps:g} GB/s ({basis}) — {source}")
        else:
            L.append(f"Memory-bandwidth ceiling for `bw`: n/a ({basis}) — {source or 'no entry in devices/memory-bandwidth.json'}")
        L.append("")
        for task, arms, grid in grid_sections(dcells):
            L.append(f"### `{task}`")
            L.append("")
            L.append("| model | " + " | ".join(f"{a} ({REGIME[plat]} tok/s)" for a in arms) + " |")
            L.append("|---|" + "---|" * len(arms))
            for (m, ctx), slots in grid:
                line = [f"**{m}**" + (f" · ctx {ctx}" if ctx else "")]
                for a in arms:
                    group = slots[a]
                    if not group:
                        line.append("·")
                    elif len(group) == 1:
                        line.append(grid_text(group[0]))
                    else:
                        line.append("<br>".join(f"`{c['artifact_tag']}`: {grid_text(c)}"
                                                for c in group))
                L.append("| " + " | ".join(line) + " |")
            L.append("")
            L.append("<details><summary>per-cell detail (recipe, session, memory, prefill, bandwidth)</summary>")
            L.append("")
            header = ["model", "arm", "ctx", "artifact", "quant", "engine", "decode tok/s",
                      "spread %", "n", "text fail", "cpu capped", "artifact MB", "MB/token",
                      "bw util", "prefill tok/s", "TTFT ms", "mem MB", "mem peak MB",
                      "thermal at start", "captured", "session"]
            L.append("| " + " | ".join(header) + " |")
            L.append("|" + "---|" * len(header))
            for c in dcells:
                if c["task"] != task:
                    continue
                head = [c["model"], c["arm"], c["context_tokens"] or "—", f"`{c['model_id']}`"]
                if c["status"] in ("excluded", "missing"):
                    why = f"— ({c['reason']})" if c["status"] == "excluded" else "not yet measured"
                    row = head + ["", "", why] + [""] * (len(header) - len(head) - 3)
                else:
                    mb = f"{c['artifact_bytes'] / 1e6:.0f}" if c["artifact_bytes"] else "—"
                    tok = f"{c['stream_bytes'] / 1e6:.0f}" if c["stream_bytes"] else "—"
                    dec = (f"— ({c['reason']})" if c["status"] == "text-fail"
                           else f"— (no valid run: {c['reason']})" if c["status"] == "cpu-capped"
                           else fmt(c["decode_tps"]))
                    row = head + [
                        c["quant"], c["engine"], dec, fmt(c["spread_pct"]),
                        str(c["n"]), c["text_fail"] or "—", c["cpu_capped"] or "—", mb, tok,
                        fmt_bw(bw_of(c)) if c["bw_util_pct"] is not None else "n/a",
                        fmt(c["prefill_tps"]), fmt(c["ttft_ms"], 0), fmt(c["mem_mb"], 0),
                        fmt(c["mem_peak_mb"], 0), c["thermal_initial"] or "—",
                        f"{c['captured']}{' (stale)' if c['stale'] else ''}",
                        f"`{os.path.basename(c['campaign'])}`"]
                L.append("| " + " | ".join(row) + " |")
            L.append("")
            L.append(MEM_NOTE + " ctx = the cell's context-tokens= (its rows are the runs "
                     "recorded at that KV allocation; — = the cell pins none). artifact MB = "
                     "decimal megabytes of the whole artifact; MB/token = the bytes a decode step "
                     "reads (artifact minus per-token-gathered tables, models/artifact-bytes.json); "
                     "bw util = decode tok/s × MB/token ÷ this device's ceiling. text fail = "
                     "the session's runs whose decoded text failed the text check (kept out of "
                     "every number, text-check-rule) / the runs that would have pooled, cold "
                     "and warm; — = the text was not checked. cpu capped = the session's runs "
                     "during which a CPU the engine ran on sat below its hardware maximum clock "
                     "(kept out of every number, cpu-cap-rule) / the same runs that would have "
                     "pooled; — = the caps were not read (records before 2026-10-07).")
            L.append("")
            L.append("</details>")
            L.append("")
    return "\n".join(L) + "\n"


CSV_FIELDS = ["platform", "device", "device_display", "regime", "model", "arm", "model_id",
              "task", "anchor", "status", "reason", "decode_tps", "spread_pct", "n",
              "prefill_tps", "ttft_ms", "mem_mb", "quant", "engine", "thermal_initial",
              "captured", "campaign", "stale",
              "artifact_bytes", "stream_bytes", "bw_ceiling_gbps", "bw_basis", "bw_util_pct",
              "mem_peak_mb", "context_tokens", "text_fail", "cpu_capped"]


def write_outputs(out_cells, md, md_path, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    with atomic_write(md_path, "w") as fh:
        fh.write(md)
    with atomic_write(os.path.join(out_dir, "dashboard-v1.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        w.writeheader()
        for c in out_cells:
            row = {k: c.get(k) for k in CSV_FIELDS}
            for k in ("decode_tps", "spread_pct", "prefill_tps", "ttft_ms", "mem_mb", "bw_util_pct",
                      "mem_peak_mb"):
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
