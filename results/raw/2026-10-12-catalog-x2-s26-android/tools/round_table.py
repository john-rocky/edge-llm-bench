#!/usr/bin/env python3
"""Per-round and per-launch timing / thermal table of one round-mode GPU campaign (catalog X2 S26 r2, 2026-10-12).

  python3 round_table.py <campaign dir> [--log <driver log>] [--cooldown 30] [--out <campaign>/rounds.md]

From the stored records only (plus round_state.jsonl / round_completion.jsonl / SITTING_STOP.txt beside them, and the
driver log's "=== <cell> (HH:MM:SS)" lines when --log is given). One row per launch: start and end (JST; end = the
record's timestamp, start = end - elapsedSeconds), the wait before it (start - previous end - cooldown: the thermal
gate, the CPU-cap gate, the pre-launch probes and pushes; split at the "===" line when the log is given: before it =
the thermal gate, after it = run_cell's CPU-cap gate + probes + pushes), thermal status and battery °C at start / end,
the lowest CPU clock ceiling per policy the sampler read (conditions.cpuMaxFreqMHz), output tokens, decode / prefill
per iteration, firstEver, protocolFlags. One row per round: start (round_state), end (its last record), minutes, the
complete flag from round_completion.jsonl, launches that ended at status >= 1, the summed waits, the lowest policy6
ceiling. Nothing is pooled or dropped here; the ladders are longctx_ab_report.py's.
"""
import argparse, datetime, glob, json, os, re

JST = datetime.timezone(datetime.timedelta(hours=9))
ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("campaign")
ap.add_argument("--log")
ap.add_argument("--cooldown", type=float, default=30.0)
ap.add_argument("--out")
a = ap.parse_args()
d = os.path.join(a.campaign, "app-path-android")


def jsonl(name):
    p = os.path.join(d, name)
    return [json.loads(x) for x in open(p) if x.strip()] if os.path.exists(p) else []


recs = [json.load(open(f)) for f in sorted(glob.glob(os.path.join(d, "*.json")))]
launches = {}
for r in recs:
    launches.setdefault(r["conditions"].get("launchIndex"), []).append(r)
order = {j["launch"]: j for j in jsonl("launch_order.jsonl")}
rstate = {j["round"]: j for j in jsonl("round_state.jsonl")}
rdone = {j["round"]: j for j in jsonl("round_completion.jsonl")}
cell_start = {}
if a.log and os.path.exists(a.log):
    stamps = re.findall(r"^=== .* \((\d\d:\d\d:\d\d)\)$", open(a.log, errors="replace").read(), re.M)
    if len(stamps) == len(order):   # one "===" line per launch, in launch order
        cell_start = dict(zip(sorted(order), stamps))


def ts(r):
    return datetime.datetime.strptime(r["timestamp"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)


def hms(t):
    return t.astimezone(JST).strftime("%H:%M:%S")


def at(day, hhmmss):
    h, m, s = map(int, hhmmss.split(":"))
    return day.astimezone(JST).replace(hour=h, minute=m, second=s, microsecond=0)


rows, per_round, prev_end = [], {}, None
for li in sorted(k for k in launches if k is not None):
    rs = sorted(launches[li], key=lambda r: r["conditions"].get("iterationIndex") or 0)
    r0 = rs[0]; c = r0["conditions"]
    end = max(ts(r) for r in rs)
    start = end - datetime.timedelta(seconds=c.get("elapsedSeconds") or 0)
    rnd = c.get("roundIndex")
    if prev_end is None and rnd in rstate:
        prev_end = datetime.datetime.strptime(rstate[rnd]["timestamp"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=JST)
        cool = 0.0   # no cooldown before the sitting's first launch
    else:
        cool = a.cooldown
    wait = (start - prev_end).total_seconds() - cool if prev_end else None
    split = ""
    if li in cell_start and prev_end:
        cs = at(end, cell_start[li])
        split = f"{(cs - prev_end).total_seconds() - cool:.0f} + {(start - cs).total_seconds():.0f}"
    caps = c.get("cpuMaxFreqMHz") or {}
    lit = r0["runtime"].startswith("litert-lm")
    cell = (f"E4B ctx{c.get('contextTokens')}" if lit else "anchor")
    by = lambda key, fmt="{}": " / ".join(fmt.format(r["metrics"].get(key)) if r["metrics"].get(key) is not None else "" for r in rs)
    flags = sorted({f for r in rs for f in r["conditions"].get("protocolFlags", [])})
    rows.append([rnd, li, cell, hms(start), hms(end), c.get("elapsedSeconds"),
                 "" if wait is None else f"{wait:.0f}", split,
                 f"{c.get('thermalRawStatus')}→{c.get('thermalRawStatusFinal')}",
                 f"{c.get('batteryTemperatureInitialC')}→{c.get('batteryTemperatureFinalC')}",
                 caps.get("policy0", {}).get("min", ""), caps.get("policy6", {}).get("min", ""),
                 by("generatedTokenCount"), by("decodeTokensPerSecond"), by("promptTokensPerSecond"),
                 "yes" if any(r["metrics"].get("firstEver") for r in rs) else "", ",".join(flags)])
    pr = per_round.setdefault(rnd, {"end": end, "n": 0, "hot": 0, "wait": 0.0, "p6": None})
    pr["end"] = max(pr["end"], end); pr["n"] += 1
    pr["hot"] += 1 if (c.get("thermalRawStatusFinal") or 0) >= 1 else 0
    pr["wait"] += wait or 0.0
    p6 = caps.get("policy6", {}).get("min")
    if lit and p6 is not None:
        pr["p6"] = p6 if pr["p6"] is None else min(pr["p6"], p6)
    prev_end = end

out = ["# Rounds and launches", "",
       f"Campaign `{os.path.basename(os.path.normpath(a.campaign))}`. Times JST. Wait = start − previous launch end − "
       f"cooldown {a.cooldown:.0f} s (none before the sitting's first launch): the thermal gate (status 0, 30 s polls), "
       "run_cell's CPU-cap gate (10 s polls), the pre-launch probes and pushes (the first E4B launch pushes the "
       "3.66 GB bundle)." + (" Split = thermal gate + the rest, at the driver log's \"===\" line." if cell_start else ""),
       "", "## Per round", "",
       "| round | start | end | minutes | complete | launches | ended at status ≥ 1 | waits s | lowest policy6 ceiling MHz (LiteRT launches) |",
       "|---|---|---|---|---|---|---|---|---|"]
for rnd in sorted(per_round):
    pr = per_round[rnd]
    st = datetime.datetime.strptime(rstate[rnd]["timestamp"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=JST) if rnd in rstate else None
    mins = f"{(pr['end'] - st).total_seconds() / 60:.1f}" if st else ""
    out.append(f"| {rnd} | {st.strftime('%H:%M:%S') if st else ''} | {hms(pr['end'])} | {mins} | "
               f"{rdone.get(rnd, {}).get('complete', 'no record')} | {pr['n']} | {pr['hot']} | {pr['wait']:.0f} | {pr['p6'] or ''} |")
stop = os.path.join(d, "SITTING_STOP.txt")
if os.path.exists(stop):
    out += ["", "SITTING_STOP.txt: " + " / ".join(x.strip() for x in open(stop) if x.strip())]
cols = ["round", "launch", "cell", "start", "end", "launch s", "wait s", "thermal gate + rest s", "thermal", "battery °C",
        "policy0 min MHz", "policy6 min MHz", "tokens (iter 1 / 2)", "decode tok/s (1 / 2)", "prefill tok/s (1 / 2)",
        "first-ever", "flags"]
out += ["", "## Per launch", "", "| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
out += ["| " + " | ".join("" if v is None else str(v) for v in row) + " |" for row in rows]
text = "\n".join(out) + "\n"
open(a.out or os.path.join(a.campaign, "rounds.md"), "w").write(text)
print(text)
