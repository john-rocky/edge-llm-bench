#!/usr/bin/env python3
"""regression_watch — the team page's red points, computed in the bench, and what follows one.

  python3 scripts/regression_watch.py [--root DIR] [--summary CSV] [--definitions JSON]
                                      [--compare regression.json] [--json OUT] [--markdown OUT]
                                      [--device KEY]
  python3 scripts/regression_watch.py --compare ~/code/litert-bench-dashboard/dist/regression.json
  python3 scripts/regression_watch.py --root <tree> --respond <campaign dir>... --state-dir logs/dashboard-job

Design: docs/dashboard-autopilot-v1.md section 8 (stage 3a of the autopilot). The rule is the
private team page's Regression section (litert-bench-dashboard build.py build_regression), run on
the bench's own data: the constants are copied in ops/autopilot/regression-watch.json with their
build.py lines, the aggregation, the regime, the exclusions and the threshold are the bench's own
functions that build.py imports, and what build.py computes itself is restated below with its
lines. Per LiteRT-LM cell of the page's devices x models x workloads (the cells files'
definitions; a cell excluded on its device has no series), one point per sitting (campaign) of
the admitted weekly rows (SESSION.json, campaign names holding 'dashboard', a lab unit's stand-in
rows out): render_leaderboard.arm_row of that campaign's rows alone, read by
render_dashboard.headline_regime. One point a day (render_leaderboard.latest_session over the
day's rows). Per metric, a shown point with a value against the nearest earlier shown point with
a value of the same prompt version - on decode also of the same regime - by the page's diff_pct;
red = below -render_leaderboard.SPREAD_FLAG. The prompt version (the summary's prompt_version: the 1K
task's tail changed under its id on 2026-10-19) cuts a series as the regime does: the first point of
a new version is compared with none (prompt_changed, "prompt <old> -> <new>: not compared"), so a
changed task text never reads as a regression or queues a retake.

--compare reads the page's regression.json and compares the red sets (device, arm, model id,
task, context, file, campaign, metric) and each red point's percentage: exit 0 when they agree,
1 when they do not (each difference printed).

--respond <campaign dir>... is the post step's red segment (scripts/dashboard_post.py runs it on
the commit's own tree after the page build): the sitting's red points become retakes and a
retake's verdict a bisect request, in the state files under --state-dir:
  retakes.json          a red point that is its cell's newest sitting -> one pending retake: the
                        device key, the cells row byte for byte (the line of the cells file the
                        red sitting ran), the red metrics with their percentage, previous campaign
                        and engine. scripts/dashboard_job.py runs a device's pending retakes as one
                        sitting before its weekly set (retake_cells_text) and marks them done.
  bisect-requests.json  a retake sitting's point still red against the red point's own previous
                        point (diff_pct, the same threshold) on another engine build than that
                        point's -> one pending request: good / bad engine labels, the row, the
                        verdict for scripts/engine_bisect.py, its route (the lab unit of the
                        phone's model on the Developer Device Platform; none for the iPhone and
                        the Mac) and the command when that tool is in the tree. Nothing starts it.
  regression-<date>-<slug>.md  the issue draft's skeleton beside each request, EN and JA: the two
                        points, their sittings and engines, the row, the command that re-measures
                        it. Never posted by the job.
A retake sitting's red points never queue retakes (the second time goes to a request or ends).
--dry-run writes no state. Exit codes: 0 done; 1 --compare found a difference; 2 usage or a
definition the data cannot meet. Reads the tree (--root), never the page repo but the file
--compare names.
"""
import argparse
import collections
import contextlib
import csv
import datetime
import fcntl
import glob
import json
import os
import re
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from render_dashboard import (ctx_key, device_keys, exclusion, headline_regime,  # noqa: E402
                              load_cells, load_schedule, model_row)
from render_leaderboard import CPU_CAP_MAX_DROP_PCT, SPREAD_FLAG, arm_row, latest_session  # noqa: E402
from validate_cells import parse_line  # noqa: E402

DEFINITIONS = os.path.join(ROOT, "ops", "autopilot", "regression-watch.json")
STATE_DIR = os.path.join(ROOT, "logs", "dashboard-job")
RETAKES = "retakes.json"
REQUESTS = "bisect-requests.json"
STATE_LOCK = ".regression.lock"
# build.py NO_NUMBER (l.533): the statuses a rule left with no headline number
NO_NUMBER = ("text-fail:", "cpu-capped:")
# an autopilot retake sitting's campaign: <date>-dashboard-v1-<key>-retake-<slug>[-anchor]-<plat>
# (dashboard_job.py --suffix retake-<slug>); a by-hand "-retake" suffix matches as well
RETAKE_DIR_RE = re.compile(r"-dashboard-v1-.*-retake(-|$)")
# a pending retake older than this is expired: the weekly set re-measures the cell by then
RETAKE_MAX_AGE_DAYS = 7
# sittings a retake may take that do not admit before it is abandoned (a person reads the ledger)
RETAKE_MAX_ATTEMPTS = 2
# dashboard_job.EXIT_BUSY: the device or the Mac measurement window was not free and nothing ran. Logged as an attempt,
# never counted toward RETAKE_MAX_ATTEMPTS (2026-10-20: the Mac retake was abandoned after two busy windows without a
# measurement); RETAKE_MAX_AGE_DAYS still ends a retake that never finds its device free
RETAKE_BUSY_EXIT = 3

# the Developer Device Platform lab unit of each phone's model (android/ddp/devices.json, the
# scheduleKey of each id); the iPhone and the Mac have no route, nor the Pixel 11 Pro (pixel11pro:
# android/ddp/devices.json lists no lab unit of it, 2026-10-27)
BISECT_ROUTE = {"s26": "ddp:m1q-36", "pixel8a": "ddp:akita-35"}
BISECT_TOOL = os.path.join("scripts", "engine_bisect.py")
# engine_bisect.py's speed verdicts (its SPEED_SPEC): decode and prefill; memory has none
VERDICT_WORD = {"decode_tps": "decode", "prefill_tps": "prefill", "mem_peak_mb": "mem"}
BISECT_VERDICTS = ("decode_tps", "prefill_tps")
# the options engine_bisect.py probe_row refuses on a probe row
PROBE_REFUSED_OPTS = ("anchor", "exclude", "manual", "engine-build", "exclude-on")
# words a draft never carries: the commit-msg hook's, an attribution, another runtime's name
# (the draft is about one runtime's builds), a ranking word, a home path
DRAFT_REFUSED = re.compile(r"claude|anthropic|generated with|co-authored|llama\.cpp|\bmlx\b|onnx|executorch|"
                           r"core ai|faster|slower|\bleads?\b|/Users/|/home/", re.I)
# a task's short name in ids and campaign names (build.py TASK_KEY, l.91)
TASK_SLUG = {"long-context-1024-gen256": "1024", "short-chat": "short-chat",
             "native-benchmark-1024x256": "protocol-1024"}
# a metric in a draft: its words, unit and digits (two for a rate, so a -5.05 % reads off its numbers)
METRIC_WORDS = {"decode_tps": ("decode", "tok/s", 2), "prefill_tps": ("prefill", "tok/s", 2),
                "mem_peak_mb": ("peak memory", "MB", 0)}
# a task as the page names it (build.py TASK_LABEL, l.93)
TASK_LABEL = {"long-context-1024-gen256": "text task 1K/256", "native-benchmark-1024x256": "protocol 1024/256 (forced prefill)",
              "short-chat": "short chat 20/128"}
METRIC_WORDS_JA = {"decode_tps": "decode", "prefill_tps": "prefill", "mem_peak_mb": "ピークメモリ"}


class Config(Exception):
    """A definition the data cannot meet, or a bad invocation (exit 2)."""


# ---------------------------------------------------------------- inputs

def load_definitions(path):
    try:
        with open(path) as fh:
            d = json.load(fh)
    except (OSError, ValueError) as e:
        raise Config(f"definitions unreadable: {path}: {e}")
    need = ("subject_arms", "devices", "models", "tasks", "metrics", "cell_files", "optional_cell_files",
            "backend", "stand_in", "page_campaigns_contain")
    missing = [k for k in need if k not in d]
    if missing:
        raise Config(f"{path}: missing {', '.join(missing)}")
    d["better"] = {m: b for m, b in d["metrics"]}
    d["metric_keys"] = [m for m, _ in d["metrics"]]
    return d


def load_admission(root):
    """render_dashboard.load_admission at `root`: campaign (results/raw/<name>) -> admitted? from
    the job's SESSION.json; no file = admitted."""
    out = {}
    for f in glob.glob(os.path.join(root, "results", "raw", "*", "SESSION.json")):
        try:
            with open(f) as fh:
                d = json.load(fh)
        except (OSError, ValueError):
            continue
        if isinstance(d, dict):
            out[os.path.relpath(os.path.dirname(f), root)] = bool(d.get("admitted", True))
    return out


def read_session(root, name):
    try:
        with open(os.path.join(root, "results", "raw", name, "SESSION.json")) as fh:
            d = json.load(fh)
    except (OSError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}


def page_rows(rows, admitted, cfg):
    """build.py load_rows + stand_in_rows (l.366-397) for the subject's arms -> (rows, stand-in rows
    left out): admitted (SESSION.json), a campaign dir name holding 'dashboard'; a lab unit's rows
    out, as build_regression drops every row stand_in_rows marked (l.1254)."""
    arms, stand, word = set(cfg["subject_arms"]), cfg["stand_in"], cfg["page_campaigns_contain"]
    out, stood = [], 0
    for r in rows:
        if not admitted.get(r["campaign"], True) or word not in os.path.basename(r["campaign"]):
            continue
        if r["runtime"] not in arms:
            continue
        if r["device"] in stand:
            stood += 1
            continue
        out.append(r)
    return out, stood


def cell_defs(root, cfg):
    """build.py load_cell_defs (l.400) for the subject's arms -> (definitions, optional files not in
    the tree): per (file, task, only), the file's cells of that task in file order, the first
    definition of a (platform, arm, model id, task, context, file) key winning. Each keeps its file
    and line (the row a retake runs again)."""
    arms = set(cfg["subject_arms"])
    out, seen, skipped = [], set(), []
    for name, task, only in cfg["cell_files"]:
        path = os.path.join(root, "matrices", name)
        if not os.path.exists(path):
            if name in cfg["optional_cell_files"]:
                skipped.append(name)
                continue
            raise Config(f"cells file missing: matrices/{name}")
        for c in load_cells(path):
            if c["arm"] not in arms or c["task"] != task:
                continue
            ctx, fname = c["context_tokens"], c["opts"].get("file", "")
            key = (c["platform"], c["arm"], c["model_id"], c["task"], ctx, fname)
            if key in seen:
                continue
            seen.add(key)
            out.append({"platform": c["platform"], "arm": c["arm"], "model_id": c["model_id"], "file": fname,
                        "task": c["task"], "ctx": ctx, "exclude": c["exclude"] or "",
                        "only": set(only) if only else None, "exclude_on": c.get("exclude_on") or {},
                        "source": f"matrices/{name}", "line": c["line"]})
    return out, sorted(set(skipped))


def regression_devices(root, cfg):
    """The page's regression devices in its order, each with its platform (build.py PANELS) and its
    schedule.json keys (exclude-on= names devices by key)."""
    keys_of = device_keys(load_schedule(os.path.join(root, "ops", "dashboard-v1", "schedule.json")))
    return [{"device": ident, "platform": plat, "keys": sorted(keys_of.get(ident, ()))}
            for ident, plat in cfg["devices"]]


# ---------------------------------------------------------------- the page's rule

def headline(plat, task, a):
    """build.py headline (l.517): (regime, decode, spread, n) of arm_row result `a`."""
    regime = headline_regime(plat, task, a)
    if regime == "warm":
        return regime, a["warm"], a["spread"], a["warm_n"]
    return regime, a["cold_median"], a["cold_spread"], a["cold_n"]


def headline_status(a, dec):
    """build.py headline_status (l.536): measured, no-decode, or the rule that emptied the pool, in
    the page's words (regression_value reads `measured` only)."""
    would = a["n"] + a["text_fail_n"] + a.get("cpu_capped_n", 0)
    if not dec and a["text_fail_n"]:
        return (f"text-fail:text check failed: {a['text_fail_flags']} "
                f"({a['text_fail_n']} of {would} runs)")
    if not dec and a.get("cpu_capped_n"):
        return f"cpu-capped:cpu-capped >{CPU_CAP_MAX_DROP_PCT:g} % ({a['cpu_capped_n']} of {would} runs)"
    return "measured" if dec else "no-decode"


def regression_value(p, key):
    """build.py regression_value (l.1232): a point's value on a metric where its status is measured."""
    return p[key] if p and p["status"] == "measured" else None


def prompt_of(crows):
    """A point's prompt version: the summary's prompt_version of its campaign's rows of the cell ('' =
    the task's first text); the versions joined by '+' when a sitting holds two, which equals no single
    version, so such a point is compared with nothing on either side."""
    return "+".join(sorted({r.get("prompt_version") or "" for r in crows}))


def prompt_word(v):
    """A prompt version as the marks write it: 'none' for the task's first text."""
    return v or "none"


def diff_pct(subject, other, higher):
    """build.py diff_pct (l.812): + = better; a lower-is-better metric as a rate."""
    if higher:
        return (subject - other) / other * 100.0
    return (other - subject) / subject * 100.0


def build_series(defs, devices, rows, cfg):
    """build.py build_regression (l.1239-1359), the parts the red points read -> (series, excluded)."""
    by_key = {}
    for r in rows:
        by_key.setdefault((r["platform"], r["device"], r["runtime"], r["model_id"], r["task"]), []).append(r)
    metrics, series, excluded = cfg["metric_keys"], [], []
    for dev in devices:
        ident, plat = dev["device"], dev["platform"]
        for d in defs:
            model = model_row(d["model_id"])
            if (d["platform"] != plat or (d["only"] and ident not in d["only"])
                    or model not in cfg["models"] or d["task"] not in cfg["tasks"]):
                continue
            backend = cfg["backend"].get(f"{plat} {d['arm']}")
            if backend is None:
                raise Config(f"no backend entry for {plat} {d['arm']} (build.py BACKEND)")
            why = exclusion(d, dev["keys"])
            if why:
                excluded.append({"device": ident, "model": model, "backend": backend, "task": d["task"],
                                 "reason": why})
                continue
            sel = [r for r in by_key.get((plat, ident, d["arm"], d["model_id"], d["task"]), [])
                   if not d["ctx"] or ctx_key(r["context_tokens"]) == d["ctx"]]
            sittings = {}
            for r in sel:
                sittings.setdefault(os.path.basename(r["campaign"]), []).append(r)
            if len(sittings) != len({r["campaign"] for r in sel}):
                raise Config(f"two campaigns share a name in the series {ident} {d['arm']} {d['model_id']} {d['task']}")
            points = []
            for crows in sittings.values():
                a = arm_row(crows)
                regime, dec, spread, n = headline(plat, d["task"], a)
                status = headline_status(a, dec)
                points.append({
                    "campaign": os.path.basename(a["campaign"]), "captured": a["date"], "shown": True,
                    "sittings_that_day": 1, "regime": regime, "engine": a["engine"], "prompt": prompt_of(crows),
                    "status": status,
                    "decode_tps": dec, "n": n, "spread_pct": None if status.startswith(NO_NUMBER) else spread,
                    "prefill_tps": a["prefill"], "mem_peak_mb": a["mem_peak"],
                    "vs_prev": dict.fromkeys(metrics)})
            points.sort(key=lambda p: (p["captured"], p["campaign"]))
            days = {}
            for p in points:
                days.setdefault(p["captured"], []).append(p)
            for same in days.values():
                if len(same) > 1:
                    # one point a day: the sitting latest_session picks from the day's rows
                    sess, _ = latest_session([r for p in same for r in sittings[p["campaign"]]])
                    newest = os.path.basename(sess[0]["campaign"])
                    for p in same:
                        p["shown"], p["sittings_that_day"] = p["campaign"] == newest, len(same)
            shown = [p for p in points if p["shown"]]
            for i, p in enumerate(shown):
                for key in metrics:
                    v = regression_value(p, key)
                    if v is None:
                        continue
                    earlier = [q for q in shown[:i] if regression_value(q, key) is not None]
                    changed = False
                    # prompt-version cut: a figure compares within its task text only (the nearest
                    # earlier point with a value on another version = the series' break, marked)
                    before = earlier[-1]["prompt"] if earlier else None
                    prompt_changed = before is not None and before != p["prompt"]
                    earlier = [q for q in earlier if q["prompt"] == p["prompt"]]
                    if key == "decode_tps":
                        # cold-warm-split: a decode figure compares within its regime only
                        changed = bool(earlier) and earlier[-1]["regime"] != p["regime"]
                        earlier = [q for q in earlier if q["regime"] == p["regime"]]
                    prev = earlier[-1] if earlier else None
                    pct = diff_pct(v, regression_value(prev, key), cfg["better"][key] == "higher") if prev else None
                    p["vs_prev"][key] = {
                        "pct": pct, "prev_campaign": prev["campaign"] if prev else None,
                        "regression": pct is not None and pct < -SPREAD_FLAG, "regime_changed": changed,
                        "engine_changed": prev["engine"] != p["engine"] if prev else None,
                        "prompt_changed": prompt_changed, "prev_prompt": before if prompt_changed else None,
                        "value": v, "prev_value": regression_value(prev, key) if prev else None,
                        "prev_engine": prev["engine"] if prev else None}
            # the sitting the page's cell shows now (cells.json: arm_row over every row of the cell)
            current = os.path.basename(latest_session(sel)[0][0]["campaign"]) if sel else None
            series.append({"device": ident, "platform": plat, "model": model, "model_id": d["model_id"],
                           "arm": d["arm"], "backend": backend, "task": d["task"], "ctx": d["ctx"],
                           "artifact_file": d["file"], "source": d["source"], "line": d["line"],
                           "current": current, "points": points})
    return series, excluded


def compute(root, summary, cfg):
    """-> the document --json writes: meta, series, red points."""
    try:
        with open(summary, newline="") as fh:
            all_rows = list(csv.DictReader(fh))
    except OSError as e:
        raise Config(f"summary unreadable: {summary}: {e}")
    admitted = load_admission(root)
    rows, stood = page_rows(all_rows, admitted, cfg)
    defs, skipped = cell_defs(root, cfg)
    series, excluded = build_series(defs, regression_devices(root, cfg), rows, cfg)
    pts = [p for s in series for p in s["points"]]
    red = red_points(series)
    return {"meta": {"threshold_pct": SPREAD_FLAG, "source": cfg.get("source"),
                     "summary_rows": len(all_rows), "rows_read": len(rows), "stand_in_rows": stood,
                     "cells_files_skipped": skipped, "series": len(series), "points": len(pts),
                     "shown": sum(p["shown"] for p in pts), "red": len(red),
                     "red_by_metric": {m: sum(1 for x in red if x["metric"] == m) for m in cfg["metric_keys"]},
                     "regime_changes": sum(1 for p in pts if p["vs_prev"].get("decode_tps")
                                           and p["vs_prev"]["decode_tps"]["regime_changed"]),
                     "prompt_changes": sum(1 for p in pts if p["vs_prev"].get("decode_tps")
                                           and p["vs_prev"]["decode_tps"]["prompt_changed"])},
            "series": series, "excluded": excluded, "red": red, "prompt_breaks": prompt_breaks(series)}


def series_key(s):
    return (s["device"], s["arm"], s["model_id"], s["task"], s.get("ctx") or "", s.get("artifact_file") or "")


def red_points(series):
    out = []
    for s in series:
        for p in s["points"]:
            for metric, vp in p["vs_prev"].items():
                if vp and vp["regression"]:
                    out.append({"device": s["device"], "model": s["model"], "task": s["task"], "backend": s["backend"],
                                "arm": s["arm"], "model_id": s["model_id"], "ctx": s["ctx"],
                                "artifact_file": s["artifact_file"], "campaign": p["campaign"],
                                "captured": p["captured"], "metric": metric, "pct": vp["pct"], "value": vp["value"],
                                "prev_campaign": vp["prev_campaign"], "prev_value": vp["prev_value"],
                                "engine": p["engine"], "prev_engine": vp["prev_engine"],
                                "engine_changed": vp["engine_changed"], "regime": p["regime"],
                                "current": p["campaign"] == s["current"]})
    return out


def prompt_breaks(series):
    """The points where a series' task text changed (prompt_changed on decode): never compared, listed."""
    out = []
    for s in series:
        for p in s["points"]:
            vp = p["vs_prev"].get("decode_tps")
            if vp and vp["prompt_changed"]:
                out.append({"device": s["device"], "model": s["model"], "task": s["task"], "backend": s["backend"],
                            "campaign": p["campaign"], "captured": p["captured"], "prompt": p["prompt"],
                            "prev_prompt": vp["prev_prompt"]})
    return out


def red_key(x):
    return (x["device"], x["arm"], x["model_id"], x["task"], x.get("ctx") or "", x.get("artifact_file") or "",
            x["campaign"], x["metric"])


# ---------------------------------------------------------------- --compare

def page_red(doc):
    """The red points of the page's regression.json (build.py regression_doc)."""
    out = []
    for s in doc.get("series", []):
        for p in s.get("points", []):
            for metric, vp in (p.get("vs_prev") or {}).items():
                if vp and vp.get("regression"):
                    out.append({"device": s.get("device"), "model": s.get("model"), "task": s.get("task"),
                                "backend": s.get("backend"), "arm": s.get("arm"), "model_id": s.get("model_id"),
                                "ctx": s.get("ctx") or "", "artifact_file": s.get("artifact_file") or "",
                                "campaign": p.get("campaign"), "metric": metric, "pct": vp.get("pct"),
                                "engine_changed": vp.get("engine_changed")})
    return out


def compare(doc, page_doc, device=None):
    """The red sets and their percentages (2 decimals), and the series / point / shown counts ->
    {"equal", "only_bench", "only_page", "pct_differs", "counts"}."""
    mine = {red_key(x): x for x in doc["red"] if device in (None, x["device"])}
    theirs = {red_key(x): x for x in page_red(page_doc) if device in (None, x["device"])}
    pct = [(k, mine[k]["pct"], theirs[k]["pct"]) for k in sorted(set(mine) & set(theirs))
           if round(mine[k]["pct"], 2) != round(theirs[k]["pct"] or 0.0, 2)]
    ss = [s for s in page_doc.get("series", []) if device in (None, s.get("device"))]
    ps = [p for s in ss for p in s.get("points", [])]
    bench_ss = [s for s in doc["series"] if device in (None, s["device"])]
    bench_ps = [p for s in bench_ss for p in s["points"]]
    counts = {"series": (len(bench_ss), len(ss)), "points": (len(bench_ps), len(ps)),
              "shown": (sum(p["shown"] for p in bench_ps), sum(1 for p in ps if p.get("shown")))}
    only_b = [mine[k] for k in sorted(set(mine) - set(theirs))]
    only_p = [theirs[k] for k in sorted(set(theirs) - set(mine))]
    equal = not only_b and not only_p and not pct and all(a == b for a, b in counts.values())
    return {"equal": equal, "only_bench": only_b, "only_page": only_p,
            "pct_differs": [{"key": list(k), "bench": a, "page": b} for k, a, b in pct],
            "counts": {k: {"bench": a, "page": b} for k, (a, b) in counts.items()},
            "red": {"bench": len(mine), "page": len(theirs)}}


# ---------------------------------------------------------------- outputs

def fmt_pct(v):
    return "" if v is None else f"{v:+.2f}"


def summary_line(doc):
    """build.py main's regression line, for reading the two side by side."""
    m = doc["meta"]
    r = m["red_by_metric"]
    return (f"regression: {m['series']} series, {m['points']} sittings ({m['shown']} shown), red points decode "
            f"{r.get('decode_tps', 0)} / prefill {r.get('prefill_tps', 0)} / memory {r.get('mem_peak_mb', 0)}, "
            f"regime changes {m['regime_changes']}, prompt changes {m['prompt_changes']}")


def markdown(doc, cmp=None, respond=None):
    lines = [summary_line(doc), "",
             "| device | model | task | backend | campaign | metric | pct | prev campaign | engine | engine_changed | current |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for x in doc["red"]:
        lines.append(f"| {x['device']} | {x['model']} | {x['task']} | {x['backend']} | {x['campaign']} | "
                     f"{VERDICT_WORD[x['metric']]} | {fmt_pct(x['pct'])} | {x['prev_campaign']} | "
                     f"{x['prev_engine']} -> {x['engine']} | {x['engine_changed']} | {x['current']} |")
    if doc.get("prompt_breaks"):
        lines += ["", "prompt version changes (the series' task text changed: not compared):"]
        lines += [f"- {b['device']} {b['model']} {b['task']} {b['backend']} {b['campaign']}: prompt "
                  f"{prompt_word(b['prev_prompt'])} -> {prompt_word(b['prompt'])}" for b in doc["prompt_breaks"]]
    if cmp is not None:
        lines += ["", f"compare: {'equal' if cmp['equal'] else 'DIFFERENT'} (red bench {cmp['red']['bench']}, page "
                      f"{cmp['red']['page']}; " + ", ".join(f"{k} {v['bench']} / {v['page']}" for k, v in cmp["counts"].items())
                  + ")"]
        for side, rows in (("only in the bench", cmp["only_bench"]), ("only in the page", cmp["only_page"])):
            for x in rows:
                lines.append(f"- {side}: {x['device']} {x['model']} {x['task']} {x['backend']} {x['campaign']} "
                             f"{VERDICT_WORD.get(x['metric'], x['metric'])} {fmt_pct(x['pct'])}")
        for d in cmp["pct_differs"]:
            lines.append(f"- pct differs: {' '.join(str(k) for k in d['key'] if k)}: bench {fmt_pct(d['bench'])}, "
                         f"page {fmt_pct(d['page'])}")
    if respond is not None:
        lines += ["", "respond:"] + [f"- {n}" for n in respond["notes"]]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- state files

@contextlib.contextmanager
def state_lock(state_dir):
    """One writer of the state files at a time (the job's sittings run side by side per device)."""
    os.makedirs(state_dir, exist_ok=True)
    fh = open(os.path.join(state_dir, STATE_LOCK), "a+")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fh, fcntl.LOCK_UN)
        fh.close()


def load_state(state_dir, name):
    key = "retakes" if name == RETAKES else "requests"
    try:
        with open(os.path.join(state_dir, name)) as fh:
            d = json.load(fh)
    except FileNotFoundError:
        return []
    except (OSError, ValueError) as e:
        raise Config(f"state file unreadable: {os.path.join(state_dir, name)}: {e}")
    return list(d.get(key) or []) if isinstance(d, dict) else []


def save_state(state_dir, name, entries):
    key = "retakes" if name == RETAKES else "requests"
    os.makedirs(state_dir, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=state_dir, prefix=f".{name}.")
    with os.fdopen(fd, "w") as fh:
        json.dump({"schema": f"autopilot-{key}.v1", key: entries}, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, os.path.join(state_dir, name))


def now_text(now=None):
    return (now or datetime.datetime.now()).strftime("%Y-%m-%d %H:%M:%S")


def parse_now(text):
    try:
        return datetime.datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- the job's side (dashboard_job.py)

def row_gone(root, e):
    """Why a pending retake's row is no longer its cell's row, or None: the cells file it was queued
    from does not hold the row any more (the page's cell moved to another file, context or option
    after the retake was queued). 2026-10-20: the S26 Qwen3 0.6B protocol row moved from
    qwen3_0_6b_mixed_int4.litertlm to the dynamic file an hour after its retake was queued; the retake
    re-ran the old row and its point fell in no series the watch reads ("left no point"). A cells
    file that is not there (renamed, or a test's own tree) supersedes nothing: there is no row to compare."""
    rel = e.get("cells_file") or ""
    path = os.path.join(root, rel)
    if not rel or not os.path.isfile(path):
        return None
    with open(path) as fh:
        rows = {ln.split("#", 1)[0].strip() for ln in fh}
    return None if (e.get("row") or "").split("#", 1)[0].strip() in rows else f"its row is no longer in {rel}"


def pending_retakes(state_dir, key, now=None, write=True, root=None, gone=None):
    """The device's pending retakes, oldest first. A pending one older than RETAKE_MAX_AGE_DAYS is
    marked expired (when `write`): the weekly set has re-measured the cell by then. With `root`, one
    whose row has left its cells file is marked superseded (row_gone; `gone` collects (id, why)): a
    retake of the old row would measure a cell the page no longer shows."""
    now = now or datetime.datetime.now()
    with state_lock(state_dir):
        entries = load_state(state_dir, RETAKES)
        out, changed = [], False
        for e in entries:
            if e.get("device") != key or e.get("status") != "pending":
                continue
            made = parse_now(e.get("created"))
            if made and (now - made).days >= RETAKE_MAX_AGE_DAYS:
                e.update(status="expired", ended=now_text(now))
                changed = True
                continue
            why = row_gone(root, e) if root else None
            if why:
                e.update(status="superseded", superseded=why, ended=now_text(now))
                changed = True
                if gone is not None:
                    gone.append((e.get("id"), why))
                continue
            out.append(e)
        if changed and write:
            save_state(state_dir, RETAKES, entries)
    return sorted(out, key=lambda e: e.get("created") or "")


def pending_counts(state_dir, root=None):
    """device key -> pending retakes (auto's choice reads it); with `root`, none whose row has left its
    cells file (the device's retake sitting would mark it superseded and run nothing)."""
    try:
        entries = load_state(state_dir, RETAKES)
    except Config:
        return {}
    return dict(collections.Counter(e.get("device") for e in entries if e.get("status") == "pending"
                                    and not (root and row_gone(root, e))))


def cell_key_of(line):
    """validate_cells' duplicate-cell key of a cells row (validate_file): one file holds a key once."""
    plat, rt, mid, task, opts = parse_line(line.split("#", 1)[0].strip())
    return (plat, rt, mid, task, opts.get("backend", ""), opts.get("context-tokens", ""), opts.get("file", ""),
            opts.get("recipe", ""), opts.get("thinking", "model-default") if rt == "uzu" else "")


def retake_slug(entries):
    return entries[0]["slug"] if len(entries) == 1 else f"{len(entries)}cells"


def retake_cells_text(root, anchors_rel, platform_token, entries):
    """The retake sitting's cells file -> (text, [rows as written]): the platform's rows of the
    anchors file byte for byte (the payload re-judges its own anchor rows), then each retake's row
    byte for byte. A retake row that is the same cell as an anchor row (validate_cells refuses a
    cell twice in one file) takes that anchor row's place; an identical row is written once."""
    with open(os.path.join(root, anchors_rel)) as fh:
        raw = [ln.rstrip("\n") for ln in fh]
    anchors = [ln for ln in raw if ln.split("#", 1)[0].strip()
               and ln.split("#", 1)[0].split()[0] == platform_token]
    keys = [cell_key_of(ln) for ln in anchors]
    take, notes, taken = [], [], set()
    for e in entries:
        k = cell_key_of(e["row"])
        if e["row"] in anchors or e["row"] in take:
            notes.append(f"# {e['id']}: the row is written once (an identical row is above or below)")
        elif k in taken:
            notes.append(f"# {e['id']}: the same cell as another retake row: that row is written")
        elif k in keys:
            i = keys.index(k)
            notes.append(f"# {e['id']}: takes the place of the anchor row of the same cell: {anchors[i]}")
            anchors[i] = e["row"]
        else:
            take.append(e["row"])
        taken.add(k)
    head = ["# generated by scripts/dashboard_job.py: a retake sitting of the autopilot "
            "(docs/dashboard-autopilot-v1.md section 8); not a committed matrix",
            f"# the {platform_token} rows of {anchors_rel}, then each retake's row byte for byte from the cells "
            "file its red sitting ran"]
    for e in entries:
        m = ", ".join(f"{VERDICT_WORD[x['metric']]} {fmt_pct(x['pct'])} % vs {x['prev_campaign']}" for x in e["metrics"])
        head.append(f"# {e['id']}: {e['model']} {e['backend']} {e['task']} on {e['identifier']}, red {m} "
                    f"in {e['red_campaign']} ({e['cells_file']} line {e['line']})")
    body = head + notes + anchors + take
    return "\n".join(body) + "\n", anchors + take


def write_retake_cells(root, state_dir, anchors_rel, platform_token, key, entries, date):
    """retake-<date>-<key>.cells under the state dir -> (path, slug, rows)."""
    text, rows = retake_cells_text(root, anchors_rel, platform_token, entries)
    os.makedirs(state_dir, exist_ok=True)
    path = os.path.join(state_dir, f"retake-{date}-{key}.cells")
    with open(path, "w") as fh:
        fh.write(text)
    return path, retake_slug(entries), rows


def finish_retakes(state_dir, ids, code, reason, campaign, cells_file=None, suffix=None, now=None):
    """After the retake sitting: admitted (exit 0) -> done with its payload campaign; otherwise the
    attempt is logged and the retake stays pending, abandoned after RETAKE_MAX_ATTEMPTS sittings that ran
    and did not admit (a busy exit, RETAKE_BUSY_EXIT, is logged and not counted)."""
    now = now or datetime.datetime.now()
    with state_lock(state_dir):
        entries = load_state(state_dir, RETAKES)
        for e in entries:
            if e.get("id") not in ids:
                continue
            e.setdefault("attempts", []).append({"at": now_text(now), "exit": code, "reason": reason,
                                                 "campaign": campaign})
            e.update(retake_cells=cells_file or e.get("retake_cells"), retake_suffix=suffix or e.get("retake_suffix"))
            if code == 0:
                e.update(status="done", retake_campaign=campaign, ended=now_text(now))
            elif (code != RETAKE_BUSY_EXIT and sum(a.get("exit") != RETAKE_BUSY_EXIT for a in e["attempts"])
                  >= RETAKE_MAX_ATTEMPTS):
                e.update(status="abandoned", ended=now_text(now))
        save_state(state_dir, RETAKES, entries)


def profile_plan(platform, entries):
    """(profile?, why) for a retake sitting on a job platform (android / iphone / mac): the per-op
    pair of `./bench profile` where a retake row is an android LiteRT-LM CPU or GPU native-benchmark
    row (litert_lm_advanced_main --benchmark is where --enable_profiling lives), else none and why
    (docs/profiling-subcommand-design.md, Coverage)."""
    if platform == "iphone":
        return False, "none on the iPhone: no CLI on the phone, the app's C API path has no profiling call"
    if platform == "mac":
        return False, ("none on the Mac: the harness's Mac runner goes through the C API, which has no "
                       "profiling call (the pair runs by hand with the built CLI)")
    rows = [e["id"] for e in entries if e["task"].startswith("native-benchmark-")
            and e["arm"] in ("litert-lm-cpu", "litert-lm-gpu")]
    if rows:
        return True, (f"./bench profile over the same file: a control + --enable_profiling pair for "
                      f"{', '.join(rows)} into the payload campaign's profiles/")
    if any(e["task"].startswith("native-benchmark-") for e in entries):
        return False, "none for the NPU side build's row (no profiling route covers it)"
    return False, ("none: the per-op profile comes from the native-benchmark rows' binary "
                   "(litert_lm_advanced_main --enable_profiling); these retakes are text-task rows")


def retake_sitting_dirs(root=ROOT):
    """results/raw/<name> of the autopilot's retake sittings (their SESSION.json names the retakes):
    not a weekly session, so the device's week is still the weekly set's."""
    out = set()
    for f in glob.glob(os.path.join(root, "results", "raw", "*-retake*", "SESSION.json")):
        try:
            with open(f) as fh:
                d = json.load(fh)
        except (OSError, ValueError):
            continue
        if isinstance(d, dict) and d.get("retake"):
            out.add(os.path.relpath(os.path.dirname(f), root))
    return out


# ---------------------------------------------------------------- --respond (the post step's red segment)

def slug_of(s):
    model = re.sub(r"[^a-z0-9]+", "", s["model"].lower())
    task = TASK_SLUG.get(s["task"]) or re.sub(r"[^a-z0-9]+", "-", s["task"].lower()).strip("-")
    return f"{model}-{s['backend'].lower()}-{task}"


def row_for(root, s, red_session):
    """(cells file, line, row byte for byte) of the cell in the cells file its red sitting ran
    (SESSION.json cells), else in the file the page's definition comes from."""
    want = (s["platform"], s["arm"], s["model_id"], s["task"], s["ctx"], s["artifact_file"])
    for rel in (red_session.get("cells"), s["source"]):
        path = os.path.join(root, rel) if rel else None
        if not path or not os.path.isfile(path):
            continue
        for c in load_cells(path):
            if (c["platform"], c["arm"], c["model_id"], c["task"], c["context_tokens"],
                    c["opts"].get("file", "")) == want:
                with open(path) as fh:
                    return rel, c["line"], fh.read().split("\n")[c["line"] - 1].rstrip("\r")
    return None, None, None


def fmt_value(metric, v):
    return "?" if v is None else f"{v:.{METRIC_WORDS[metric][2]}f}"


def bisect_ref(label):
    """The LiteRT-LM ref of an engine label: a version tag as is, main@<sha> / main-<sha> as the sha;
    anything else (an artifact name, two builds in one sitting, no stamp) has none."""
    label = label or ""
    if re.fullmatch(r"v\d+(\.\d+)+", label):
        return label
    m = re.fullmatch(r"main[-@]([0-9a-f]{7,40})(\s.*)?", label)
    return m.group(1) if m else None


def bisect_command(root, entry, metric, good, bad, route):
    """(command or None, why not, notes) for scripts/engine_bisect.py."""
    notes = []
    if not os.path.isfile(os.path.join(root, BISECT_TOOL)):
        return None, f"tooling not on this branch ({BISECT_TOOL})", notes
    if route == "none":
        return None, "no route: the bisect runs on a Developer Device Platform lab phone (Android only)", notes
    if metric not in BISECT_VERDICTS:
        return None, f"engine_bisect.py has no {VERDICT_WORD[metric]} verdict (decode or prefill only)", notes
    g, b = bisect_ref(good), bisect_ref(bad)
    if not g or not b:
        return None, f"no LiteRT-LM ref for the engine label {good if not g else bad!r}", notes
    _, rt, _, _, opts = parse_line(entry["row"].split("#", 1)[0].strip())
    refused = [k for k in PROBE_REFUSED_OPTS if opts.get(k)]
    if entry["platform"] != "android" or rt != "litert-lm" or refused or opts.get("backend") == "npu":
        return None, ("the row is not one engine_bisect.py probes (an android litert-lm row without "
                      f"{', '.join(PROBE_REFUSED_OPTS)} and not backend=npu)"), notes
    if route == "ddp:m1q-36" and opts.get("backend") == "cpu":
        notes.append("the m1q-36 lab units started every 2026-10-15 run with policy6 at 3398 of 4742 MHz "
                     "(android/ddp/devices.json): a CPU row's speed verdict there may give no number under the "
                     "cpu-cap rule; a person picks the route")
    verdict = f"speed:{VERDICT_WORD[metric]}<=-{SPREAD_FLAG:g}%"
    cmd = (f"python3 {BISECT_TOOL} --good {g} --bad {b} --cells {entry['cells_file']} --row {entry['line']} "
           f"--verdict '{verdict}' --route {route}")
    return cmd, None, notes


def judge(entry, s, retake_name, cfg):
    """A retake's verdict -> (result, per metric): each red metric of the retake sitting's point
    against the red point's own previous point (the page's diff_pct and threshold). On the red
    point's UTC day the retake is the page's shown point and this is its vs_prev; on a later day
    the page compares the retake with the red point itself, which a regression that stays passes."""
    pts = {p["campaign"]: p for p in s["points"]} if s else {}
    p = pts.get(retake_name)
    out = []
    for m in entry["metrics"]:
        key, row = m["metric"], {"metric": m["metric"], "prev_campaign": m["prev_campaign"]}
        prev = pts.get(m["prev_campaign"])
        v, pv = regression_value(p, key), regression_value(prev, key)
        if s is None:
            row["why"] = "the cells files define this cell no more (its row changed after the retake was queued)"
        elif p is None:
            row["why"] = "the retake sitting left no point of this cell"
        elif v is None:
            row["why"] = f"the retake has no {VERDICT_WORD[key]} value ({p['status'].split(':', 1)[0]})"
        elif pv is None:
            row["why"] = f"the previous point {m['prev_campaign']} has no value"
        elif p["prompt"] != prev["prompt"]:
            row["why"] = (f"the retake's prompt version is {prompt_word(p['prompt'])}, the previous point's "
                          f"{prompt_word(prev['prompt'])}")
        elif key == "decode_tps" and p["regime"] != prev["regime"]:
            row["why"] = f"the retake's regime is {p['regime']}, the previous point's {prev['regime']}"
        else:
            pct = diff_pct(v, pv, cfg["better"][key] == "higher")
            row.update(pct=pct, value=v, prev_value=pv, red=pct < -SPREAD_FLAG, engine=p["engine"],
                       prev_engine=prev["engine"], engine_changed=p["engine"] != prev["engine"],
                       captured=p["captured"])
        out.append(row)
    if any(r.get("red") for r in out):
        return "red-stays", out
    return ("cleared" if out and all("pct" in r for r in out) else "unjudged"), out


def draft_text(entry, req, judged, retake_name, profile):
    """The issue draft's skeleton, EN and JA: numbers, sittings, engines, the row, the commands."""
    m = next(r for r in judged if r["metric"] == req["metric"])
    red = next(x for x in entry["metrics"] if x["metric"] == req["metric"])
    words, unit, _ = METRIC_WORDS[req["metric"]]
    ja = METRIC_WORDS_JA[req["metric"]]
    g, b = req["good"], req["bad"]
    task = f"{TASK_LABEL.get(entry['task'], entry['task'])}, task {entry['task']}"
    where = (f"{entry['display']} ({entry['identifier']})" if entry.get("display") not in (None, entry["identifier"])
             else entry["identifier"])
    reproduce = f"./bench dashboard-job {entry['device']} --cells {req['retake_cells']} --suffix {req['retake_suffix']}"
    bis = f"`{req['command']}` (not started)" if req["command"] else f"none yet: {req['why_no_command']}"
    bis_ja = f"`{req['command']}`(未起動)" if req["command"] else f"まだなし: {req['why_no_command']}"
    prof = profile or "none for this cell (docs/dashboard-autopilot-v1.md section 8, profile)"
    prof_ja = profile or "この cell にはなし(docs/dashboard-autopilot-v1.md 8 節、profile)"
    en = [
        f"# Draft: LiteRT-LM {words} on {where}, {entry['model']} ({entry['backend']}, {task})",
        "",
        "<!-- written by scripts/regression_watch.py beside a bisect request; a person edits and posts it -->",
        "",
        "## EN",
        "",
        f"On {where}, LiteRT-LM {b} runs {entry['model']} on the {entry['backend']} backend ({task}) at "
        f"{fmt_value(req['metric'], red['value'])} {unit} {words}; LiteRT-LM {g} ran the same cells row at "
        f"{fmt_value(req['metric'], red['prev_value'])} {unit} ({fmt_pct(red['pct'])} %). A re-measurement in a sitting "
        f"of its own read {fmt_value(req['metric'], m['value'])} {unit} ({fmt_pct(m['pct'])} % against the {g} point).",
        "",
        f"- {g}: sitting {red['prev_campaign']}",
        f"- {b}: sitting {entry['red_campaign']} ({entry['captured']}), re-measured in {retake_name} ({m.get('captured', '?')})",
        f"- cells row: `{entry['row']}` ({entry['cells_file']} line {entry['line']})",
        f"- re-measure: `{reproduce}` (the anchor rows of matrices/anchors.cells, then the row above)",
        f"- commit range: {bis}",
        f"- per-op profile: {prof}",
        "",
        "## JA",
        "",
        f"{where} で、LiteRT-LM {b} の {entry['model']}({entry['backend']} backend、{task})の {ja} は "
        f"{fmt_value(req['metric'], red['value'])} {unit}、同じ cells 行の LiteRT-LM {g} は "
        f"{fmt_value(req['metric'], red['prev_value'])} {unit}({fmt_pct(red['pct'])} %)。別の sitting で測り直すと "
        f"{fmt_value(req['metric'], m['value'])} {unit}({g} の点に対して {fmt_pct(m['pct'])} %)。",
        "",
        f"- {g}: sitting {red['prev_campaign']}",
        f"- {b}: sitting {entry['red_campaign']}({entry['captured']})、測り直し {retake_name}({m.get('captured', '?')})",
        f"- cells 行: `{entry['row']}`({entry['cells_file']} {entry['line']} 行目)",
        f"- 測り直す command: `{reproduce}`(matrices/anchors.cells の anchor 行、続けて上の行)",
        f"- commit の範囲: {bis_ja}",
        f"- op 単位の profile: {prof_ja}",
    ]
    return "\n".join(en) + "\n"


def respond(doc, sitting, root, state_dir, cfg, now=None, dry=False):
    """The sitting's red points -> retakes; a retake sitting's verdicts -> bisect requests and
    drafts. -> {"queued", "judged", "requests", "notes"} (the post's ledger note reads it)."""
    now = now or datetime.datetime.now()
    date = now.strftime("%Y-%m-%d")
    names = [os.path.basename(os.path.normpath(d)) for d in sitting]
    sessions = {n: read_session(root, n) for n in names}
    key = next((s.get("device_key") for s in sessions.values() if s.get("device_key")), None)
    retake_ids = [i for s in sessions.values() for i in ((s.get("retake") or {}).get("ids") or [])]
    is_retake = bool(retake_ids) or any(RETAKE_DIR_RE.search(n) for n in names)
    by_key = {series_key(s): s for s in doc["series"]}
    out = {"queued": [], "judged": [], "requests": [], "notes": []}
    mine = [x for x in doc["red"] if x["campaign"] in names]
    with state_lock(state_dir):
        retakes, requests = load_state(state_dir, RETAKES), load_state(state_dir, REQUESTS)
        if is_retake:
            payload = next((n for n in names if sessions[n].get("phase") == "payload"
                            and (sessions[n].get("retake") or not retake_ids)), None)
            targets = [e for e in retakes if e.get("id") in retake_ids]
            for i in retake_ids:
                if i not in [e.get("id") for e in targets]:
                    out["notes"].append(f"retake {i}: not in {RETAKES}, not judged")
            target_keys = {tuple(e["series"]) for e in targets}
            for x in mine:
                if tuple(red_key(x)[:6]) not in target_keys:
                    out["notes"].append(f"red in this retake sitting on a cell it did not target: {x['device']} "
                                        f"{x['model']} {x['backend']} {x['task']} {VERDICT_WORD[x['metric']]} "
                                        f"{fmt_pct(x['pct'])} % (logged; a retake sitting queues no retake)")
            if not retake_ids and mine:
                out["notes"].append(f"{len(mine)} red in a retake sitting without a queued retake (by hand): logged")
            for e in targets:
                s = by_key.get(tuple(e["series"]))
                result, judged = judge(e, s, payload, cfg)
                e.update(result=result, judged=judged, judged_at=now_text(now), retake_campaign=e.get("retake_campaign")
                         or (f"results/raw/{payload}" if payload else None))
                staying = [r for r in judged if r.get("red")]
                text = "; ".join(f"{VERDICT_WORD[r['metric']]} {fmt_pct(r['pct'])} % vs {r['prev_campaign']}"
                                 if "pct" in r else f"{VERDICT_WORD[r['metric']]}: {r['why']}" for r in judged)
                out["judged"].append({"id": e["id"], "result": result, "metrics": judged})
                out["notes"].append(f"retake {e['id']}: {result} ({text})")
                if result != "red-stays":
                    continue
                changed = [r for r in staying if r["engine_changed"]]
                if not changed:
                    out["notes"].append(f"retake {e['id']}: red stays on the same engine ({staying[0]['engine']}): "
                                        "not an engine build change, no bisect request")
                    continue
                pick = next((r for r in changed if r["metric"] in BISECT_VERDICTS), changed[0])
                route = BISECT_ROUTE.get(e["device"], "none") if e["platform"] == "android" else "none"
                cmd, why, cmd_notes = bisect_command(root, e, pick["metric"], pick["prev_engine"], pick["engine"], route)
                rid = f"{date}-{e['device']}-{e['slug']}"
                if any(r.get("id") == rid for r in requests):
                    out["notes"].append(f"bisect request {rid}: already written")
                    continue
                prof_dir = os.path.join(root, "results", "raw", payload or "", "profiles", "PROFILE.md")
                profile = f"results/raw/{payload}/profiles/PROFILE.md" if payload and os.path.isfile(prof_dir) else None
                req = {"id": rid, "device": e["device"], "identifier": e["identifier"], "platform": e["platform"],
                       "model": e["model"], "backend": e["backend"], "arm": e["arm"], "task": e["task"],
                       "series": e["series"], "cells_file": e["cells_file"], "line": e["line"], "row": e["row"],
                       "metric": pick["metric"], "metrics_red": [r["metric"] for r in staying],
                       "good": pick["prev_engine"], "bad": pick["engine"],
                       "good_campaign": pick["prev_campaign"], "red_campaign": e["red_campaign"],
                       "retake_campaign": f"results/raw/{payload}" if payload else None,
                       "pct": pick["pct"], "red_pct": next(x["pct"] for x in e["metrics"] if x["metric"] == pick["metric"]),
                       "verdict": f"speed:{VERDICT_WORD[pick['metric']]}<=-{SPREAD_FLAG:g}%", "route": route,
                       "tooling": "present" if os.path.isfile(os.path.join(root, BISECT_TOOL)) else "not on this branch",
                       "command": cmd, "why_no_command": why, "notes": cmd_notes,
                       "retake_cells": e.get("retake_cells") or f"logs/dashboard-job/retake-<date>-{e['device']}.cells",
                       "retake_suffix": e.get("retake_suffix") or f"retake-{e['slug']}",
                       "draft": f"logs/dashboard-job/regression-{date}-{e['slug']}.md",
                       "created": now_text(now), "status": "pending"}
                requests.append(req)
                out["requests"].append(req)
                tool = "" if cmd else f" ({why})"
                out["notes"].append(f"bisect request {rid}: {req['good']} -> {req['bad']}, {req['verdict']}, route "
                                    f"{route}{tool}")
                if not dry:
                    with open(os.path.join(state_dir, f"regression-{date}-{e['slug']}.md"), "w") as fh:
                        fh.write(draft_text(e, req, judged, payload, profile))
        else:
            for x in mine:
                if not x["current"]:
                    out["notes"].append(f"red not queued (not its cell's newest sitting): {x['device']} {x['model']} "
                                        f"{x['backend']} {x['task']} {VERDICT_WORD[x['metric']]} {x['campaign']}")
            grouped = collections.OrderedDict()
            for x in mine:
                if x["current"]:
                    grouped.setdefault((tuple(red_key(x)[:6]), x["campaign"]), []).append(x)
            for (skey, camp), reds in grouped.items():
                s = by_key[skey]
                prevs = {x["prev_campaign"] for x in reds}
                dup = next((e for e in retakes if tuple(e.get("series") or ()) == skey
                            and e.get("status") in ("pending", "done")
                            and prevs & {m["prev_campaign"] for m in e.get("metrics", [])}), None)
                desc = (f"{s['device']} {s['model']} {s['backend']} {s['task']} "
                        + ", ".join(f"{VERDICT_WORD[x['metric']]} {fmt_pct(x['pct'])} % vs {x['prev_campaign']}" for x in reds))
                if dup:
                    out["notes"].append(f"red {desc}: retake {dup['id']} ({dup['status']}) covers it")
                    continue
                if not key:
                    out["notes"].append(f"red {desc}: no device key in the sitting's SESSION.json, no retake")
                    continue
                cells_file, line, row = row_for(root, s, sessions.get(camp) or {})
                if row is None:
                    out["notes"].append(f"red {desc}: no cells row found for the cell, no retake")
                    continue
                rid, n = f"{date}-{key}-{slug_of(s)}", 2
                while any(e.get("id") == rid for e in retakes):
                    rid, n = f"{date}-{key}-{slug_of(s)}-{n}", n + 1
                e = {"id": rid, "slug": slug_of(s), "device": key, "identifier": s["device"],
                     "display": (sessions.get(camp) or {}).get("device_display") or s["device"], "platform": s["platform"],
                     "model": s["model"], "backend": s["backend"], "arm": s["arm"], "model_id": s["model_id"],
                     "task": s["task"], "ctx": s["ctx"], "artifact_file": s["artifact_file"], "series": list(skey),
                     "cells_file": cells_file, "line": line, "row": row, "red_campaign": camp,
                     "captured": reds[0]["captured"], "engine": reds[0]["engine"],
                     "metrics": [{k: x[k] for k in ("metric", "pct", "value", "prev_campaign", "prev_value",
                                                    "prev_engine", "engine_changed", "regime")} for x in reds],
                     "created": now_text(now), "status": "pending"}
                retakes.append(e)
                out["queued"].append(e)
                out["notes"].append(f"red {desc}: retake {rid} queued")
        if not dry:
            save_state(state_dir, RETAKES, retakes)
            save_state(state_dir, REQUESTS, requests)
    if not out["notes"]:
        out["notes"].append(f"no red point in this sitting ({len(doc['red'])} on the page)")
    return out


# ---------------------------------------------------------------- main

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=ROOT, help="the bench tree whose SESSION.json files, matrices and "
                                                 "schedule are read (default: this checkout)")
    ap.add_argument("--summary", help="device-runs.csv (default: <root>/results/summary/device-runs.csv)")
    ap.add_argument("--definitions", default=DEFINITIONS, help="the page's constants (default: %(default)s)")
    ap.add_argument("--compare", metavar="REGRESSION_JSON", help="the page's regression.json: exit 1 when the red sets differ")
    ap.add_argument("--json", metavar="OUT", help="write the series, the red points, the comparison, the response")
    ap.add_argument("--markdown", metavar="OUT", help="write the red points as a table")
    ap.add_argument("--device", metavar="KEY", help="one device: its schedule.json key")
    ap.add_argument("--respond", nargs="+", metavar="DIR", help="the post step: this sitting's campaign dirs")
    ap.add_argument("--state-dir", default=STATE_DIR, help="retakes.json, bisect-requests.json and the drafts "
                                                           "(default: %(default)s)")
    ap.add_argument("--dry-run", action="store_true", help="with --respond: write no state")
    args = ap.parse_args(argv)
    try:
        root = os.path.abspath(args.root)
        cfg = load_definitions(args.definitions)
        doc = compute(root, args.summary or os.path.join(root, "results", "summary", "device-runs.csv"), cfg)
        ident = None
        if args.device:
            keys = load_schedule(os.path.join(root, "ops", "dashboard-v1", "schedule.json")).get("devices", {})
            if args.device not in keys:
                raise Config(f"unknown device key {args.device!r}; known: {sorted(keys)}")
            ident = keys[args.device]["identifier"]
            doc["red"] = [x for x in doc["red"] if x["device"] == ident]
        cmp = None
        if args.compare:
            try:
                with open(args.compare) as fh:
                    cmp = compare(doc, json.load(fh), ident)
            except (OSError, ValueError) as e:
                raise Config(f"--compare unreadable: {args.compare}: {e}")
        resp = (respond(doc, args.respond, root, os.path.abspath(args.state_dir), cfg, dry=args.dry_run)
                if args.respond else None)
    except Config as e:
        print(f"regression_watch: {e}", file=sys.stderr)
        return 2
    print(summary_line(doc))
    for x in doc["red"]:
        print(f"  red  {x['device']} | {x['model']} | {x['task']} | {x['backend']} | {x['campaign']} | "
              f"{VERDICT_WORD[x['metric']]} {fmt_pct(x['pct'])} % vs {x['prev_campaign']} | "
              f"engine {x['prev_engine']} -> {x['engine']}{' (changed)' if x['engine_changed'] else ''}"
              f"{'' if x['current'] else ' | not the cell newest'}")
    for b in doc.get("prompt_breaks", []):
        print(f"  prompt  {b['device']} | {b['model']} | {b['task']} | {b['backend']} | {b['campaign']} | "
              f"prompt {prompt_word(b['prev_prompt'])} -> {prompt_word(b['prompt'])} (not compared)")
    if cmp is not None:
        print(f"compare with {args.compare}: {'equal' if cmp['equal'] else 'DIFFERENT'} (red bench "
              f"{cmp['red']['bench']}, page {cmp['red']['page']}; "
              + ", ".join(f"{k} {v['bench']} / {v['page']}" for k, v in cmp["counts"].items()) + ")")
        for side, rows in (("only in the bench", cmp["only_bench"]), ("only in the page", cmp["only_page"])):
            for x in rows:
                print(f"  {side}: {x['device']} {x['model']} {x['task']} {x['backend']} {x['campaign']} "
                      f"{VERDICT_WORD.get(x['metric'], x['metric'])} {fmt_pct(x['pct'])}")
        for d in cmp["pct_differs"]:
            print(f"  pct differs: {' '.join(str(k) for k in d['key'] if k)}: bench {fmt_pct(d['bench'])}, "
                  f"page {fmt_pct(d['page'])}")
    if resp is not None:
        for n in resp["notes"]:
            print(f"  respond: {n}" + (" [dry-run: not written]" if args.dry_run else ""))
    if args.json:
        with open(args.json, "w") as fh:
            json.dump(dict(doc, compare=cmp, respond=resp), fh, indent=1, ensure_ascii=False, default=str)
            fh.write("\n")
    if args.markdown:
        with open(args.markdown, "w") as fh:
            fh.write(markdown(doc, cmp, resp))
    return 1 if cmp is not None and not cmp["equal"] else 0


if __name__ == "__main__":
    sys.exit(main())
