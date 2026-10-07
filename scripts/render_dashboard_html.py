#!/usr/bin/env python3
"""Render the dashboard as one self-contained HTML page (+ a per-session history CSV).

  python3 scripts/render_dashboard.py                 # first: -> .dashboard/dashboard-v1.{csv,json}
  python3 scripts/render_dashboard_html.py            # -> .dashboard/dashboard-v1.html
                                                      #    .dashboard/dashboard-v1-history.csv
  python3 scripts/render_dashboard_html.py --open-details --out /tmp/d.html   # print / PDF variant

The page reads `.dashboard/dashboard-v1.json` — the cells scripts/render_dashboard.py
built through render_leaderboard.arm_row (latest admitted capture session per
cell, never pooled across sessions) — and draws one grid per (device, task):
rows are the models in cells-file order (a row per KV allocation where the
cells pin context-tokens=), columns are the arms in a fixed alphabetical
order, every number carries its recipe, engine pin and session date. Nothing
is ranked; the bar under a number is the same one hue everywhere and is scaled
to the grid's largest cell, so it reads magnitude, not identity.

The history CSV is the same aggregation applied per admitted session: one row
per (device, model, arm, task, allocation, campaign), for a database or a trend
view. It imports arm_row and filters the rows it hands over the way
render_dashboard.build does; it defines no second aggregation. A session the
text check left without a number has no history row, as an excluded cell has
none (text-check-rule), and so is one the CPU cap left without a number (cpu-cap-rule);
`text_fail` says how many runs of a kept row left the pool.

Every output is LOCAL and gitignored (/.dashboard/): the rendered page is
cross-runtime standings, which this repo does not publish (CLAUDE.md, owner
decision 2026-08-27). Hand the file to the team directly.
"""
import argparse
import csv
import datetime
import html
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from render_dashboard import (MEM_NOTE, SUMMARY_CSV, ctx_key, grid_sections,  # noqa: E402
                              load_admission, rel)
from render_leaderboard import SPREAD_FLAG, arm_row  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_JSON = os.path.join(ROOT, ".dashboard", "dashboard-v1.json")
DEFAULT_OUT = os.path.join(ROOT, ".dashboard", "dashboard-v1.html")
DEFAULT_HISTORY = os.path.join(ROOT, ".dashboard", "dashboard-v1-history.csv")
BANDWIDTH_JSON = os.path.join(ROOT, "devices", "memory-bandwidth.json")

HISTORY_FIELDS = ["platform", "device", "device_display", "regime", "model", "arm", "model_id",
                  "task", "campaign", "captured", "decode_tps", "spread_pct", "n",
                  "prefill_tps", "ttft_ms", "mem_mb", "quant", "engine", "thermal_initial",
                  "context_tokens", "mem_peak_mb", "text_fail"]


def esc(s):
    return html.escape("" if s is None else str(s), quote=True)


def fmt(v, nd=1):
    if v is None:
        return "—"
    return f"{v:,.{nd}f}"


def short_quant(q):
    """The recipe label a grid cell can afford: the family before the first
    parenthesis (INT4 / Q4_K_M / wNa8o8 / INT8); the full string sits in the
    detail table and in the cell's tooltip."""
    q = (q or "").strip()
    if not q:
        return ""
    return q.split(" (", 1)[0].split("/", 1)[0].strip()


def short_engine(e):
    e = (e or "").strip()
    return e[:8] if len(e) >= 32 else e  # a bare git sha -> 8 chars, tags stay whole


def git_head():
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                                       text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def history_rows(cells):
    """One arm_row per admitted campaign of every cell in the JSON."""
    if not os.path.exists(SUMMARY_CSV):
        return []
    rows = list(csv.DictReader(open(SUMMARY_CSV)))
    admitted = load_admission()
    rows = [r for r in rows if admitted.get(r["campaign"], True)]
    out = []
    for c in cells:
        if c["status"] == "excluded":
            continue
        # the same cell selection as render_dashboard.build, allocation included
        ctx = c.get("context_tokens") or ""
        sel = [r for r in rows
               if r["platform"] == c["platform"] and r["device"] == c["device"]
               and r["runtime"] == c["arm"] and r["model_id"] == c["model_id"]
               and r["task"] == c["task"]
               and (not ctx or ctx_key(r.get("context_tokens")) == ctx)]
        by_campaign = {}
        for r in sel:
            by_campaign.setdefault(r["campaign"], []).append(r)
        for camp, group in by_campaign.items():
            a = arm_row(group)
            if c["regime"] == "warm":
                dec, spread, n = a["warm"], a["spread"], a["warm_n"]
            else:
                dec, spread, n = a["cold_median"], a["cold_spread"], a["cold_n"]
            # no number -> no row: a session whose pool the text check or the CPU
            # cap emptied is left out like an excluded cell (text-check-rule,
            # cpu-cap-rule)
            if not dec:
                continue
            out.append({
                "platform": c["platform"], "device": c["device"],
                "device_display": c["device_display"], "regime": c["regime"],
                "model": c["model"], "arm": c["arm"], "model_id": c["model_id"],
                "task": c["task"], "campaign": camp, "captured": a["date"],
                "decode_tps": round(dec, 2), "spread_pct": round(spread, 2), "n": n,
                "prefill_tps": round(a["prefill"], 2) if a["prefill"] else "",
                "ttft_ms": a["ttft"] if a["ttft"] is not None else "",
                "mem_mb": round(a["mem"], 1) if a["mem"] else "",
                "quant": a["quant"], "engine": a["engine"],
                "thermal_initial": ",".join(a["thermal_initial"]),
                "context_tokens": ctx,
                "mem_peak_mb": round(a["mem_peak"], 1) if a["mem_peak"] else "",
                # same "k/N" as the dashboard's text_fail ("" = text not checked)
                "text_fail": (f"{a['text_fail_n']}/{a['n'] + a['text_fail_n'] + a['cpu_capped_n']}"
                              if a["text_checked_n"] else ""),
            })
    out.sort(key=lambda r: (r["platform"], r["device"], r["model"], r["arm"], r["task"],
                            r["context_tokens"], r["captured"]))
    return out


CSS = """
:root {
  color-scheme: light;
  --surface: #fcfcfb; --card: #ffffff; --rule: #e6e5e1; --rule-2: #f0efec;
  --text: #0b0b0b; --text-2: #52514e; --text-3: #7c7b76;
  --bar: #2a78d6; --bar-track: #eaf1fb;
  --warn: #fab219; --miss: #b9b8b2;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --surface: #1a1a19; --card: #222220; --rule: #333331; --rule-2: #2a2a28;
    --text: #ffffff; --text-2: #c3c2b7; --text-3: #8f8e86;
    --bar: #3987e5; --bar-track: #26334a;
    --warn: #fab219; --miss: #5b5b57;
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --surface: #1a1a19; --card: #222220; --rule: #333331; --rule-2: #2a2a28;
  --text: #ffffff; --text-2: #c3c2b7; --text-3: #8f8e86;
  --bar: #3987e5; --bar-track: #26334a;
  --warn: #fab219; --miss: #5b5b57;
}
* { box-sizing: border-box; }
html, body { margin: 0; background: var(--surface); color: var(--text);
  font: 14px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
main { max-width: 1180px; margin: 0 auto; padding: 24px 16px 48px; }
h1 { font-size: 22px; font-weight: 600; margin: 0 0 4px; }
h2 { font-size: 17px; font-weight: 600; margin: 0 0 2px; }
h3 { font-size: 13px; font-weight: 600; margin: 14px 0 2px; color: var(--text-2); }
h3 code { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; color: var(--text); }
table.grid th.model .ctx { display: block; font-weight: 400; font-size: 11.5px; color: var(--text-2); }
.entry + .entry { margin-top: 8px; }
.tag code { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 10.5px; color: var(--text-2); }
.sub { color: var(--text-2); margin: 0 0 18px; }
.rules { border: 1px solid var(--rule); border-radius: 8px; padding: 10px 14px; margin: 0 0 22px;
  color: var(--text-2); background: var(--card); }
.rules p { margin: 3px 0; }
section.device { border: 1px solid var(--rule); border-radius: 10px; background: var(--card);
  padding: 14px 16px 10px; margin: 0 0 20px; break-inside: avoid; }
.devmeta { color: var(--text-2); margin: 0 0 10px; }
.devmeta .id { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; }
table.grid { width: 100%; border-collapse: collapse; table-layout: fixed; }
table.grid th, table.grid td { text-align: left; vertical-align: top; padding: 8px 10px 8px 0;
  border-top: 1px solid var(--rule-2); }
table.grid thead th { border-top: 0; color: var(--text-2); font-weight: 500; font-size: 12px;
  text-transform: none; letter-spacing: 0; padding-bottom: 4px; }
table.grid th.model { width: 118px; font-weight: 600; }
.num { font-size: 20px; font-weight: 600; letter-spacing: -0.01em; }
.num .unit { font-size: 11px; font-weight: 400; color: var(--text-3); margin-left: 2px; }
.bar { position: relative; height: 6px; margin: 5px 0 6px; background: var(--bar-track); border-radius: 0 4px 4px 0; }
.bar span { position: absolute; left: 0; top: 0; bottom: 0; background: var(--bar); border-radius: 0 4px 4px 0; }
.meta { color: var(--text-3); font-size: 11.5px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.flags { font-size: 11.5px; color: var(--text-2); margin-top: 2px; }
.flag { display: inline-block; margin-right: 8px; }
.flag.warn::before { content: "\\25B2"; color: var(--warn); font-size: 9px; margin-right: 4px; vertical-align: 1px; }
.flag.stale { color: var(--text-3); }
.gap { color: var(--text-3); }
.gap .why { display: block; font-size: 11.5px; }
details { margin: 10px 0 2px; }
summary { cursor: pointer; color: var(--text-2); font-size: 13px; }
table.detail { width: 100%; border-collapse: collapse; font-size: 12px; margin-top: 8px; }
table.detail th, table.detail td { text-align: left; padding: 4px 8px 4px 0; border-top: 1px solid var(--rule-2);
  vertical-align: top; }
table.detail thead th { border-top: 0; color: var(--text-2); font-weight: 500; }
table.detail td.n, table.detail th.n { text-align: right; padding-right: 12px; font-variant-numeric: tabular-nums; }
table.detail code, .devmeta code { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 11px; }
footer { color: var(--text-3); font-size: 12px; margin-top: 12px; }
footer p { margin: 4px 0; }
table.cov { border-collapse: collapse; margin: 0 0 22px; font-size: 13px; }
table.cov th, table.cov td { text-align: left; padding: 5px 18px 5px 0; border-top: 1px solid var(--rule-2); vertical-align: top; }
table.cov thead th { border-top: 0; color: var(--text-2); font-weight: 500; font-size: 12px; }
table.cov td.n, table.cov th.n { text-align: right; padding-right: 22px; font-variant-numeric: tabular-nums; }
@media print {
  @page { size: A4 landscape; margin: 11mm; }
  html, body { background: #fff; color: #0b0b0b; font-size: 12px; }
  main { max-width: none; padding: 0; }
  section.device { break-before: page; break-inside: auto; box-shadow: none; }
  .head-grid { break-inside: avoid; }
  tr { break-inside: avoid; }
  .num { font-size: 16px; }
  table.grid th, table.grid td { padding: 6px 8px 6px 0; }
  .bar { margin: 4px 0 4px; }
  table.detail { font-size: 9.5px; }
  table.detail code, .devmeta code { font-size: 8.5px; }
  .bar span { print-color-adjust: exact; -webkit-print-color-adjust: exact; }
  .bar { print-color-adjust: exact; -webkit-print-color-adjust: exact; }
  .flag.warn::before { print-color-adjust: exact; -webkit-print-color-adjust: exact; }
  a { color: inherit; text-decoration: none; }
}
"""


def grid_entry(c, dmax):
    """(tooltip, inner HTML) of one cell in a grid slot; dmax = the grid's largest decode."""
    if c["status"] in ("excluded", "text-fail", "cpu-capped"):
        why = f"no valid run: {c['reason']}" if c["status"] == "cpu-capped" else c["reason"]
        return "", f"<span class=\"gap\">—<span class=\"why\">{esc(why)}</span></span>"
    if c["status"] != "measured":
        return "", "<span class=\"gap\">not yet measured</span>"
    pct = max(1.5, 100.0 * (c["decode_tps"] or 0) / dmax)
    meta_bits = [short_quant(c["quant"]), short_engine(c["engine"]), c["captured"]]
    if c.get("bw_util_pct") is not None:
        approx = "~" if c.get("bw_basis") not in ("vendor",) else ""
        meta_bits.append(f"bw {approx}{c['bw_util_pct']:.0f}%")
    tip = (f"{c['model_id']} · {c['quant']} · engine {c['engine']} · n={c['n']} · "
           f"prefill {fmt(c['prefill_tps'])} tok/s · TTFT {fmt(c['ttft_ms'], 0)} ms · "
           f"mem {fmt(c['mem_mb'], 0)} MB · peak {fmt(c['mem_peak_mb'], 0)} MB · "
           + (f"ctx {c['context_tokens']} · " if c["context_tokens"] else "")
           + os.path.basename(c["campaign"]))
    parts = [f"<div class=\"num\">{fmt(c['decode_tps'])}<span class=\"unit\">tok/s</span></div>",
             f"<div class=\"bar\"><span style=\"width:{pct:.1f}%\"></span></div>",
             f"<div class=\"meta\">{esc(' · '.join(b for b in meta_bits if b))}</div>"]
    flags = []
    if (c["spread_pct"] or 0) > SPREAD_FLAG:
        flags.append(f"<span class=\"flag warn\">spread {c['spread_pct']:.0f}%</span>")
    if c["stale"]:
        flags.append("<span class=\"flag stale\">stale</span>")
    if flags:
        parts.append(f"<div class=\"flags\">{''.join(flags)}</div>")
    return tip, "".join(parts)


def render(cells, bandwidth, generated, stale_days, history, open_details, head):
    for c in cells:
        # a JSON written before 2026-10-06 lacks these (one task, no allocation)
        c.setdefault("context_tokens", "")
        c.setdefault("mem_peak_mb", None)
        c.setdefault("artifact_tag", c["model_id"].split("/", 1)[-1])
        c.setdefault("text_fail", "")  # a JSON from before the text-check-rule lacks this
    by_dev = {}
    for c in cells:
        by_dev.setdefault((c["platform"], c["device"], c["device_display"]), []).append(c)
    sessions = {}
    for h in history:
        sessions.setdefault((h["device"], h["model_id"], h["arm"], h["task"], h["context_tokens"]),
                            set()).add(h["campaign"])
    tasks = list(dict.fromkeys(c["task"] for c in cells))

    order = {"mac": 0, "ios": 1, "android": 2}
    devs = sorted(by_dev, key=lambda k: (order.get(k[0], 9), k[1]))

    L = []
    L.append("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">")
    L.append("<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">")
    L.append("<title>edge-llm-bench dashboard</title>")
    L.append(f"<style>{CSS}</style></head><body><main>")
    L.append(f"<h1>Local LLM engines on real devices — dashboard v1 (text, {esc(', '.join(tasks))})</h1>")
    n_meas = sum(1 for c in cells if c["status"] == "measured")
    n_cells = sum(1 for c in cells if c["status"] != "missing" or any(
        x["status"] == "measured" for x in by_dev[(c["platform"], c["device"], c["device_display"])]))
    L.append(f"<p class=\"sub\">Rendered {esc(generated[:16].replace('T', ' '))} from the harness's summary layer"
             f"{' at commit ' + esc(head) if head else ''} · {n_meas} measured cells"
             f" · one number per device × model × runtime × task (and KV allocation where the cell pins one), "
             "from the latest admitted capture session of that cell.</p>")
    L.append("<div class=\"rules\">")
    L.append("<p><b>Number</b> = decode tokens/s: the median of one session's runs — warm runs on the Apple devices, "
             "fresh-process (cold) runs on Android, where the CLI has no warm regime. Sessions are never pooled; "
             "a cell shows its latest admitted session and its date.</p>")
    L.append("<p><b>Bar</b> = the same number, scaled to the largest cell of its grid (one device, one task). Columns are "
             "alphabetical and rows are light → heavy, one row per KV allocation where the cells pin one; nothing is ranked. "
             "Runtimes compare only within one device, one task and one model.</p>")
    L.append(f"<p><b>Flags</b>: ▲ spread = the session's runs spread more than {SPREAD_FLAG:.0f}% around the median "
             f"(information, not a verdict; Android cold runs legitimately spread wider) · stale = older than {stale_days} days "
             "· bw = decode tok/s × bytes read per token ÷ the device's memory-bandwidth ceiling (an estimate, cited per device) "
             "· text check failed = every run that could have given the number failed the decoded-text check (empty, off-task "
             "or looping text), so none is shown; the runs stay in the raw records "
             "· no valid run: cpu-capped = every such run ran while the phone held a CPU the engine ran on below its hardware "
             "maximum clock, so none is shown; the runs stay in the raw records.</p>")
    L.append("<p><b>Recipe</b>: each runtime runs its own published artifact and quantization (shown under the number, in full in the "
             "detail table) — a different recipe is a different deployment profile, not a win.</p>")
    L.append("</div>")

    shown = [k for k in devs if any(c["status"] in ("measured", "excluded", "text-fail", "cpu-capped")
                                    for c in by_dev[k])]
    L.append("<table class=\"cov\"><thead><tr><th>device</th><th>regime</th><th class=\"n\">cells measured</th>"
             "<th class=\"n\">stale</th><th>captures</th><th>runtimes in the grid</th></tr></thead><tbody>")
    for key in shown:
        plat, ident, display = key
        dc = by_dev[key]
        meas = [c for c in dc if c["status"] == "measured"]
        dates = sorted({c["captured"] for c in meas if c["captured"]})
        rng = f"{dates[0]} … {dates[-1]}" if dates else "—"
        L.append(f"<tr><td>{esc(display)} <span class=\"gap\">({esc(ident)})</span></td><td>{esc(dc[0]['regime'])}</td>"
                 f"<td class=\"n\">{len(meas)} / {len(dc)}</td><td class=\"n\">{sum(1 for c in meas if c['stale'])}</td>"
                 f"<td>{esc(rng)}</td><td>{esc(', '.join(sorted({c['arm'] for c in dc})))}</td></tr>")
    L.append("</tbody></table>")

    for key in shown:
        plat, ident, display = key
        dc = by_dev[key]
        measured = [c for c in dc if c["status"] == "measured"]
        excluded = [c for c in dc if c["status"] == "excluded"]
        text_failed = [c for c in dc if c["status"] == "text-fail"]
        cpu_capped = [c for c in dc if c["status"] == "cpu-capped"]
        missing = [c for c in dc if c["status"] == "missing"]
        regime = dc[0]["regime"]
        dates = sorted({c["captured"] for c in measured if c["captured"]})
        engines = sorted({e for c in measured for e in (c["engine"] or "").split(" / ") if e})
        bw = (bandwidth.get("devices") or {}).get(ident) or {}

        L.append("<section class=\"device\"><div class=\"head-grid\">")
        L.append(f"<h2>{esc(display)}</h2>")
        cov = f"{len(measured)} of {len(dc)} cells measured"
        if excluded:
            cov += f", {len(excluded)} excluded with a reason"
        if text_failed:
            cov += f", {len(text_failed)} failed the text check"
        if cpu_capped:
            cov += f", {len(cpu_capped)} had no valid run (cpu-capped)"
        if missing:
            cov += f", {len(missing)} not yet measured"
        rng = f"captures {dates[0]} … {dates[-1]}" if dates else "no captures"
        L.append(f"<p class=\"devmeta\"><span class=\"id\">{esc(ident)}</span> · {esc(plat)} · headline regime <b>{esc(regime)}</b>"
                 f" · {esc(cov)} · {esc(rng)}")
        if engines:
            L.append(f" · engines observed: {esc(', '.join(short_engine(e) for e in engines))}")
        if bw.get("gbps"):
            L.append(f"<br>Memory-bandwidth ceiling for bw: {bw['gbps']} GB/s ({esc(bw.get('basis'))})")
        elif bw:
            L.append(f"<br>Memory-bandwidth ceiling for bw: n/a ({esc(bw.get('basis'))}) — no vendor figure")
        L.append("</p></div>")

        for task, arms, grid in grid_sections(dc):
            tcells = [c for c in dc if c["task"] == task]
            dmax = max((c["decode_tps"] or 0) for c in tcells) or 1.0
            L.append(f"<div class=\"head-grid\"><h3>task <code>{esc(task)}</code></h3>")
            L.append("<table class=\"grid\"><thead><tr><th class=\"model\">model</th>")
            for a in arms:
                L.append(f"<th>{esc(a)} <span class=\"gap\">({esc(regime)} tok/s)</span></th>")
            L.append("</tr></thead><tbody>")
            for (m, ctx), slots in grid:
                ctx_label = f"<span class=\"ctx\">ctx {esc(ctx)}</span>" if ctx else ""
                L.append(f"<tr><th class=\"model\">{esc(m)}{ctx_label}</th>")
                for a in arms:
                    group = slots[a]
                    if not group:
                        L.append("<td><span class=\"gap\">—</span></td>")
                    elif len(group) == 1:
                        tip, inner = grid_entry(group[0], dmax)
                        L.append((f"<td title=\"{esc(tip)}\">" if tip else "<td>") + inner + "</td>")
                    else:
                        # two artifacts of one arm on one row: every cell shown, named
                        L.append("<td>")
                        for c in group:
                            tip, inner = grid_entry(c, dmax)
                            L.append((f"<div class=\"entry\" title=\"{esc(tip)}\">" if tip else "<div class=\"entry\">")
                                     + f"<div class=\"tag\"><code>{esc(c['artifact_tag'])}</code></div>" + inner + "</div>")
                        L.append("</td>")
                L.append("</tr>")
            L.append("</tbody></table></div>")

            L.append(f"<details{' open' if open_details else ''}><summary>per-cell detail — artifact, recipe, engine pin, "
                     "prefill, TTFT, memory, session, admitted sessions so far</summary>")
            L.append("<table class=\"detail\"><thead><tr><th>model</th><th>runtime</th><th>ctx</th><th>artifact</th><th>quant</th>"
                     "<th>engine</th><th class=\"n\">decode tok/s</th><th class=\"n\">spread %</th><th class=\"n\">n</th>"
                     "<th class=\"n\">text fail</th><th class=\"n\">prefill tok/s</th><th class=\"n\">TTFT ms</th><th class=\"n\">mem MB</th>"
                     "<th class=\"n\">mem peak MB</th><th class=\"n\">bw</th><th>thermal at start</th><th>captured</th>"
                     "<th>session</th><th class=\"n\">sessions</th></tr></thead><tbody>")
            for c in tcells:
                ns = len(sessions.get((c["device"], c["model_id"], c["arm"], c["task"], c["context_tokens"]), ()))
                lead = (f"<tr><td>{esc(c['model'])}</td><td>{esc(c['arm'])}</td><td>{esc(c['context_tokens'] or '—')}</td>"
                        f"<td><code>{esc(c['model_id'])}</code></td>")
                if c["status"] in ("measured", "text-fail", "cpu-capped"):
                    # a text-fail or cpu-capped row keeps its recipe and session (the runs
                    # are in raw); its decode is "—" and the grid cell carries the reason
                    approx = "~" if c.get("bw_basis") not in ("vendor",) else ""
                    bwc = f"{approx}{c['bw_util_pct']:.1f}%" if c.get("bw_util_pct") is not None else "n/a"
                    L.append(
                        lead + f"<td>{esc(c['quant'])}</td><td><code>{esc(c['engine'])}</code></td>"
                        f"<td class=\"n\">{fmt(c['decode_tps'])}</td><td class=\"n\">{fmt(c['spread_pct'])}</td>"
                        f"<td class=\"n\">{c['n']}</td><td class=\"n\">{esc(c['text_fail'] or '—')}</td>"
                        f"<td class=\"n\">{fmt(c['prefill_tps'])}</td>"
                        f"<td class=\"n\">{fmt(c['ttft_ms'], 0)}</td><td class=\"n\">{fmt(c['mem_mb'], 0)}</td>"
                        f"<td class=\"n\">{fmt(c['mem_peak_mb'], 0)}</td>"
                        f"<td class=\"n\">{esc(bwc)}</td><td>{esc(c['thermal_initial'])}</td>"
                        f"<td>{esc(c['captured'])}{' (stale)' if c['stale'] else ''}</td>"
                        f"<td><code>{esc(os.path.basename(c['campaign']))}</code></td><td class=\"n\">{ns}</td></tr>")
                else:
                    why = c["reason"] if c["status"] == "excluded" else "not yet measured"
                    L.append(lead + f"<td colspan=\"14\" class=\"gap\">— {esc(why)}</td><td class=\"n\">{ns}</td></tr>")
            L.append("</tbody></table>")
            L.append(f"<p class=\"devmeta\">{esc(MEM_NOTE)} ctx = the cell's context-tokens= (its rows are the runs "
                     "recorded at that KV allocation; — = the cell pins none). "
                     "bw = decode tok/s × bytes a decode step reads (the artifact minus per-token-gathered tables) ÷ this device's ceiling; "
                     "~ marks a ceiling that is a derivation or an estimate, not a vendor figure. "
                     "text fail = the session's runs whose decoded text failed the text check (kept out of every number) / the runs "
                     "that would have pooled, cold and warm; — = the text was not checked.</p>")
            L.append("</details>")
        L.append("</section>")

    L.append("<footer>")
    L.append("<p>Source: results/summary/device-runs.csv (one row per run; every run has its stored log and JSON record under "
             "results/raw/&lt;campaign&gt;/). Dates are the record's UTC date. Machine-readable copies of this page: .dashboard/dashboard-v1.csv / .json (latest session per cell) "
             "and .dashboard/dashboard-v1-history.csv (one row per cell per admitted session).</p>")
    L.append("<p>Rules the numbers follow: methodology/fairness-rules.md (recipe per arm, no cross-session pooling, spread rule, stored-report rule). "
             "Local render — the public repository ships the harness and the raw records, not runtime-versus-runtime standings.</p>")
    L.append("</footer></main></body></html>")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", default=DEFAULT_JSON)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--history", default=DEFAULT_HISTORY, help="history CSV path ('' to skip)")
    ap.add_argument("--stale-days", type=int, default=10)
    ap.add_argument("--open-details", action="store_true", help="expand every detail table (print / PDF)")
    args = ap.parse_args()

    d = json.load(open(args.json))
    cells = d["cells"]
    bandwidth = json.load(open(BANDWIDTH_JSON)) if os.path.exists(BANDWIDTH_JSON) else {}
    hist = history_rows(cells)
    if args.history:
        os.makedirs(os.path.dirname(args.history) or ".", exist_ok=True)
        with open(args.history, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=HISTORY_FIELDS)
            w.writeheader()
            w.writerows(hist)
    page = render(cells, bandwidth, d.get("generated", datetime.datetime.now().isoformat()),
                  args.stale_days, hist, args.open_details, git_head())
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w") as fh:
        fh.write(page)
    n_meas = sum(1 for c in cells if c["status"] == "measured")
    print(f"wrote {rel(args.out)} ({n_meas} measured cells)"
          + (f" and {rel(args.history)} ({len(hist)} cell-sessions)" if args.history else ""))


if __name__ == "__main__":
    main()
