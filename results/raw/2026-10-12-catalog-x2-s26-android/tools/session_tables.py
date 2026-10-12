#!/usr/bin/env python3
"""Per-launch conditions, per-cell spread and anchor admission of one round-mode campaign (catalog X2).

  python3 tools/session_tables.py <campaign dir> [--rounds 1,2,3,4,5,6]

Writes <campaign>/temperature_log.md (one row per launch: battery °C and thermal status at start / end, the
round's mWakefulness from round_state.jsonl, conditions.screen, launch seconds, sampled peak RSS, the lowest CPU
clock ceiling per policy, protocolFlags), <campaign>/spread.md (per LiteRT cell and regime: n, median, min, max,
max/min - 1 — the acceptance bar, 15 % — and (max - min) / median, the 2026-09-24 re-take's column),
<campaign>/anchor.md (the llama.cpp anchor per round against the admitted 2026-09-14 S26 reference, 105.6 tok/s,
results/raw/2026-09-14-dashboard-v1-s26-android/SESSION.json; the dashboard's 5 % rule) and <campaign>/records.md
+ records.csv (one row per record: round x cell x regime, decode / prefill / TTFT / tokens, flags, the CPU ceiling
fall of build_summary.cpu_cap_drop_of, and whether longctx_ab_report pools the record). Records are read as stored;
nothing is dropped. Selected rounds only feed spread.md and anchor.md; spread.md uses the records the ladder pools.
"""
import argparse, csv, glob, json, os, statistics, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "scripts"))
from build_summary import cpu_cap_drop_of  # noqa: E402
from render_leaderboard import CPU_CAP_EXEMPT_ARMS  # noqa: E402

CAP_FLAGS = {"cpu-capped", "cpu-capped-at-start"}


def pooled(r):
    """longctx_ab_report's rule: no flag, or only the CPU cap's on an accelerator arm; firstEver apart."""
    f = set(r["conditions"].get("protocolFlags", []))
    return not r["metrics"].get("firstEver") and (not f or (f <= CAP_FLAGS and r["runtime"] in CPU_CAP_EXEMPT_ARMS))

REFERENCE, BAR = 105.6, 0.05
ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("campaign")
ap.add_argument("--rounds")
a = ap.parse_args()
d = os.path.join(a.campaign, "app-path-android")
sel = {int(x) for x in a.rounds.split(",")} if a.rounds else None
recs = [json.load(open(f)) for f in sorted(glob.glob(os.path.join(d, "*.json")))]
wake = {}
if os.path.exists(os.path.join(d, "round_state.jsonl")):
    for line in open(os.path.join(d, "round_state.jsonl")):
        if line.strip():
            j = json.loads(line); wake[j["round"]] = j.get("mWakefulness")
launches = {}
for r in recs:
    launches.setdefault(r["conditions"].get("launchIndex"), r)   # both iterations share launch telemetry
t = ["# Per-launch conditions", "", "One row per launch (both iterations of a LiteRT launch share it). Battery °C "
     "and thermal status from the record; mWakefulness from round_state.jsonl; CPU ceiling = lowest "
     "scaling_max_freq / cpuinfo_max_freq MHz the sampler read per policy.", "",
     "| round | launch | arm | model | allocation | °C start | °C end | thermal start | thermal end | gate timed out "
     "| round mWakefulness | screen | launch s | peak RSS MiB | CPU ceiling | protocolFlags |", "|" + "---|" * 16]
for li in sorted(k for k in launches if k is not None):
    r = launches[li]; c, m = r["conditions"], r["metrics"]
    caps = ", ".join(f"{k} {v['min']}/{v['hw']}" for k, v in (c.get("cpuMaxFreqMHz") or {}).items())
    t.append("| " + " | ".join(str(x) for x in (
        c.get("roundIndex"), li, r["runtime"], r["model"]["id"].split("/")[-1], c.get("contextTokens"),
        c.get("batteryTemperatureInitialC"), c.get("batteryTemperatureFinalC"), c.get("thermalRawStatus"),
        c.get("thermalRawStatusFinal"), c.get("thermalGateTimedOut"), wake.get(c.get("roundIndex")), c.get("screen"),
        c.get("elapsedSeconds"), round(m["memoryPeakResidentMB"], 1) if m.get("memoryPeakResidentMB") else "",
        caps, ",".join(c.get("protocolFlags", [])))) + " |")
open(os.path.join(a.campaign, "temperature_log.md"), "w").write("\n".join(t) + "\n")
cells = {}
for r in recs:
    c = r["conditions"]
    if r["runtime"].startswith("litert-lm") and (sel is None or c.get("roundIndex") in sel) and pooled(r):
        cells.setdefault((r["model"]["id"].split("/")[-1], c.get("contextTokens"), c.get("regime")), []).append(
            (r["metrics"].get("decodeTokensPerSecond"), c.get("roundIndex")))
s = ["# Per-cell decode spread", "", f"Rounds {a.rounds or 'all stored'}; the records the ladder pools (first-ever and "
     "flagged runs out; a CPU-cap-only flag on an accelerator arm stays in, ◇ in records.md). Acceptance bar: "
     "max/min - 1 <= 15 % per warm cell, else the cell is owed a re-take.", "",
     "| model | allocation | regime | n | median | min (round) | max (round) | max/min - 1 % | (max-min)/median % | <= 15 % |",
     "|" + "---|" * 10]
for (model, ctx, regime), v in sorted(cells.items(), key=lambda kv: (kv[0][0], kv[0][1] or 0, kv[0][2] or "")):
    v = [x for x in v if x[0]]
    if not v:
        continue
    lo, hi, med = min(v), max(v), statistics.median(x[0] for x in v)
    s.append(f"| {model} | {ctx} | {regime} | {len(v)} | {med:.2f} | {lo[0]:.2f} ({lo[1]}) | {hi[0]:.2f} ({hi[1]}) | "
             f"{(hi[0] / lo[0] - 1) * 100:.1f} | {(hi[0] - lo[0]) / med * 100:.1f} | {'yes' if hi[0] / lo[0] - 1 <= 0.15 else 'NO'} |")
open(os.path.join(a.campaign, "spread.md"), "w").write("\n".join(s) + "\n")
anc = sorted((r["conditions"].get("roundIndex"), r["metrics"].get("decodeTokensPerSecond"), r["conditions"].get("protocolFlags", []))
             for r in recs if r["runtime"] == "llama.cpp" and (sel is None or r["conditions"].get("roundIndex") in sel))
vals = [x[1] for x in anc if x[1]]
med = statistics.median(vals) if vals else None
an = ["# Anchor admission", "", f"llama.cpp b8999 Qwen3-0.6B Q4_K_M short-chat, once per round; reference {REFERENCE} "
      "tok/s (results/raw/2026-09-14-dashboard-v1-s26-android/SESSION.json, anchor median); 5 % rule.", "",
      "| round | decode tok/s | protocolFlags |", "|---|---|---|"] + [f"| {x[0]} | {x[1]} | {','.join(x[2])} |" for x in anc]
an += ["", f"median {med:.2f} over {len(vals)} rounds = {med / REFERENCE:.3f} of the reference: "
       + ("admitted" if abs(med / REFERENCE - 1) <= BAR else "NOT admitted") if med else "no anchor record"]
open(os.path.join(a.campaign, "anchor.md"), "w").write("\n".join(an) + "\n")
cols = ["round", "launch", "iteration", "regime", "arm", "model", "allocation", "prompt tok", "output tok", "decode tok/s",
        "prefill tok/s", "TTFT ms", "first-ever", "thermal", "flags", "CPU ceiling fall %", "pooled"]
rows = []
for r in sorted(recs, key=lambda r: (r["conditions"].get("launchIndex") or 0, r["conditions"].get("iterationIndex") or 0)):
    c, m = r["conditions"], r["metrics"]
    fl = c.get("protocolFlags", [])
    rows.append([c.get("roundIndex"), c.get("launchIndex"), c.get("iterationIndex"), c.get("regime"), r["runtime"],
                 r["model"]["id"].split("/")[-1], c.get("contextTokens"), m.get("promptTokenCount"), m.get("generatedTokenCount"),
                 m.get("decodeTokensPerSecond"), m.get("promptTokensPerSecond"), m.get("firstTokenLatencyMS"),
                 bool(m.get("firstEver")), f"{c.get('thermalRawStatus')}->{c.get('thermalRawStatusFinal')}",
                 ",".join(("◇" if pooled(r) else "") + f for f in fl), cpu_cap_drop_of(r),
                 "yes" if pooled(r) and r["runtime"].startswith("litert-lm") else ("anchor" if r["runtime"] == "llama.cpp" else "no")])
with open(os.path.join(a.campaign, "records.csv"), "w", newline="") as fh:
    w = csv.writer(fh); w.writerow(cols); w.writerows(rows)
rec_md = ["# Per-record table", "", "Every stored record, launch order. pooled = what longctx_ab_report.py and spread.md "
          "read (◇ = a CPU-cap-only flag on an accelerator arm, kept and marked).", "",
          "| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)] + ["| " + " | ".join("" if v is None else str(v) for v in row) + " |" for row in rows]
open(os.path.join(a.campaign, "records.md"), "w").write("\n".join(rec_md) + "\n")
print("\n".join(s + [""] + an))
