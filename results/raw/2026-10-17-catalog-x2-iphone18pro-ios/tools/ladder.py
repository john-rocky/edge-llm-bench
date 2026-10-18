#!/usr/bin/env python3
"""Readout of one round-mode sitting of catalog X2's iPhone leg (2026-10-17).

  python3 tools/ladder.py <campaign dir> [--anchor-ref <tok/s>] [--rounds 1,2,3]

Reads the schema-v1 records in <campaign>/device-jsonl/ (the raw records the app wrote, pulled by
tools/round_driver.sh) and the driver's launches.tsv (which launch pulled which record: round, index,
allocation), and writes next to them:

  ladder.md / ladder.csv — per (arm, model, allocation, regime cold|warm): decode and prefill tok/s and TTFT as
                           median [min–max] over the rounds, n, spread (max/min − 1), Δ of the decode median
                           from the smallest allocation, prompt / output tokens, stop reasons, thermal states
  records.md             — every record, one row each (round, launch, allocation, regime, rates, tokens, thermal,
                           battery, resident peak, the first 120 characters of outputSample)
  text_check.md          — the LiteRT records' answer check: output tokens vs the 256 budget, stop reason, a
                           lexical screen of outputSample (a numbered list on the asked topic, no refusal / filler
                           words) — iOS records carry the first ~200 characters only, not the whole text
  anchor.md              — the anchor rows (mlx-swift short-chat) per launch, warm median, ratio to --anchor-ref

Nothing here pools across campaigns; a record without a launch line is listed as unmapped and excluded from
the ladder. Rounds are the driver's; --rounds selects complete rounds for the ladder (default: every round
that has a record, listed per cell).
"""
import argparse, csv, glob, json, os, re, statistics

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("campaign")
ap.add_argument("--anchor-ref", type=float, help="reference warm median of the anchor cell (tok/s)")
ap.add_argument("--rounds", help="comma list of rounds to read into the ladder (default: all)")
a = ap.parse_args()
C = a.campaign.rstrip("/")

# launches.tsv: round idx rt mid task ctx t0 t1 rc run_ok th_i th_f console pulled
launch_of = {}
launches = []
lt = os.path.join(C, "launches.tsv")
if os.path.exists(lt):
    for line in open(lt):
        f = line.rstrip("\n").split("\t")
        if len(f) < 14:
            continue
        rec = dict(round=int(f[0]), idx=int(f[1]), rt=f[2], mid=f[3], task=f[4], ctx=f[5], t0=f[6], t1=f[7],
                   rc=f[8], run_ok=f[9], th_i=f[10], th_f=f[11], console=f[12], pulled=[x for x in f[13].split(";") if x])
        launches.append(rec)
        for name in rec["pulled"]:
            launch_of[name] = rec

rows = []
for f in sorted(glob.glob(os.path.join(C, "device-jsonl", "*.json"))):
    d = json.load(open(f))
    if d.get("schemaVersion") != 1:
        continue
    m, dev = d.get("metrics", {}), d.get("device", {})
    L = launch_of.get(os.path.basename(f))
    rows.append(dict(
        file=os.path.basename(f), round=L["round"] if L else None, launch=L["idx"] if L else None,
        arm=d.get("runtime"), model=d.get("model", {}).get("id"), task=d.get("task"),
        ctx=m.get("contextTokensConfigured"), cold=bool(m.get("coldRun")),
        decode=m.get("decodeTokensPerSecond"), decode_wall=m.get("decodeTokensPerSecondWallClock"),
        prefill=m.get("promptTokensPerSecond"), prefill_wall=m.get("promptTokensPerSecondWallClock"),
        ttft=m.get("firstTokenLatencyMS"), p=m.get("promptTokenCount"), g=m.get("generatedTokenCount"),
        stop=m.get("stopReason"), th_i=m.get("initialThermalState"), th_p=m.get("peakThermalState"),
        th_f=m.get("finalThermalState"), battery=dev.get("batteryLevel"), bstate=dev.get("batteryState"),
        rss=m.get("memoryPeakResidentMB"), footprint=m.get("memoryPeakDuringDecodeMB"),
        load_s=m.get("loadTimeSeconds"), engine=d.get("engineVersion"), build=dev.get("buildConfiguration"),
        sample=(d.get("outputSample") or "").replace("\n", "\\n").replace("|", "\\|"), ts=d.get("timestamp"),
        budget=d.get("parameters", {}).get("maxTokens")))

sel_rounds = {int(x) for x in a.rounds.split(",")} if a.rounds else None


def med(vals):
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    return statistics.median(vals), min(vals), max(vals), len(vals)


def fmt(t, nd=1):
    if not t:
        return "—"
    m_, lo, hi, n = t
    return f"{m_:.{nd}f} [{lo:.{nd}f}–{hi:.{nd}f}] n={n}"


def spread(t):
    return f"{(t[2] / t[1] - 1) * 100:.1f} %" if t and t[1] else "—"


ladder = [r for r in rows if str(r["arm"]).startswith("litert-lm") and r["round"] not in (None, 0, 99)
          and (sel_rounds is None or r["round"] in sel_rounds)]
# First-ever: the sitting's first launch at an allocation whose model load took more than twice the cell's
# median load time (the engine (re)built or re-specialized its cache for that allocation: on this phone the
# E2B GPU round-1 launches at 2304 / 4096 loaded in 1.42 s against 0.45 s afterwards and decoded 5 % slower).
# Its cold record is listed apart, as the S26 leg lists `firstEver`; the warm record of the same launch stays.
first_ever = set()
for key in {(r["arm"], r["model"], r["task"], r["ctx"]) for r in ladder}:
    g = sorted([r for r in ladder if (r["arm"], r["model"], r["task"], r["ctx"]) == key and r["cold"]], key=lambda r: r["launch"] or 0)
    loads = [r["load_s"] for r in g if r["load_s"]]
    if g and loads and g[0]["load_s"] and len(loads) > 1 and g[0]["load_s"] > 2 * statistics.median(loads):
        first_ever.add(g[0]["file"])
for r in ladder:
    r["first_ever"] = r["file"] in first_ever
unmapped = [r for r in rows if r["round"] is None]
out, csv_rows = [], []
out.append(f"# {os.path.basename(C)} — ladder (median [min–max] over rounds; spread = max/min − 1; Δ = decode median vs the smallest allocation)\n")
if sel_rounds:
    out.append(f"Rounds selected: {','.join(map(str, sorted(sel_rounds)))}.\n")
engines = sorted({r["engine"] for r in ladder if r["engine"]})
builds = sorted({r["build"] for r in ladder if r["build"]})
out.append(f"Engine stamped: {', '.join(engines) or '—'}; build configuration: {', '.join(builds) or '—'}; "
           f"records in the ladder: {len(ladder)}; unmapped records (no launch line): {len(unmapped)}.\n")
cells = sorted({(r["arm"], r["model"], r["task"]) for r in ladder})
for arm, model, task in cells:
    out.append(f"\n## {arm} — {model} — {task}\n")
    out.append("| regime | ctx | rounds | decode tok/s | spread | Δ vs smallest | prefill tok/s | TTFT ms | prompt tok | out tok (short) | stop | thermal start→end | resident peak MiB |")
    out.append("|---|---:|---|---|---:|---:|---|---|---|---|---|---|---|")
    for regime, cold in (("warm", False), ("cold", True)):
        g_all = [r for r in ladder if (r["arm"], r["model"], r["task"]) == (arm, model, task) and r["cold"] == cold and not r["first_ever"]]
        ctxs = sorted({r["ctx"] for r in g_all if isinstance(r["ctx"], int)})
        base = None
        for ctx in ctxs:
            g = [r for r in g_all if r["ctx"] == ctx]
            dec, pre, ttft, rss = med([r["decode"] for r in g]), med([r["prefill"] for r in g]), med([r["ttft"] for r in g]), med([r["rss"] for r in g])
            gt = med([r["g"] for r in g]); short = sum(1 for r in g if r["g"] is not None and r["budget"] and r["g"] < r["budget"] - 2)
            if ctx == ctxs[0]:
                base = dec[0] if dec else None
            delta = f"{(dec[0] / base - 1) * 100:+.1f} %" if (dec and base) else "—"
            rounds = ",".join(str(x) for x in sorted({r["round"] for r in g}))
            ps = "/".join(str(x) for x in sorted({r["p"] for r in g}, key=str))
            stops = ",".join(f"{s}×{n}" for s, n in sorted(__import__('collections').Counter(r['stop'] for r in g).items(), key=str))
            therm = ",".join(sorted({f"{r['th_i']}→{r['th_f']}" for r in g}))
            out.append(f"| {regime} | {ctx} | {rounds} | {fmt(dec)} | {spread(dec)} | {delta} | {fmt(pre, 0)} | {fmt(ttft, 0)} | {ps} | {fmt(gt, 0)} ({short}) | {stops} | {therm} | {fmt(rss, 0)} |")
            csv_rows.append(dict(arm=arm, model=model, task=task, regime=regime, ctx=ctx, rounds=rounds, n=dec[3] if dec else 0,
                                 decode_med=dec[0] if dec else None, decode_min=dec[1] if dec else None, decode_max=dec[2] if dec else None,
                                 spread_pct=(dec[2] / dec[1] - 1) * 100 if dec and dec[1] else None,
                                 delta_vs_smallest_pct=(dec[0] / base - 1) * 100 if (dec and base) else None,
                                 prefill_med=pre[0] if pre else None, prefill_min=pre[1] if pre else None, prefill_max=pre[2] if pre else None,
                                 ttft_med_ms=ttft[0] if ttft else None, prompt_tokens=ps, gen_tokens_med=gt[0] if gt else None, short_stops=short,
                                 stops=stops, thermal=therm, rss_med=rss[0] if rss else None))
    fe = [r for r in ladder if (r["arm"], r["model"], r["task"]) == (arm, model, task) and r["first_ever"]]
    if fe:
        out.append("\nFirst-ever cold records (the allocation's first launch of the sitting, load time > 2× the cell's median; kept apart, not in the cold rows above): "
                   + "; ".join(f"ctx {r['ctx']} round {r['round']}: decode {r['decode']:.1f}, prefill {r['prefill']:.0f}, load {r['load_s']:.2f} s, resident peak {r['rss']:.0f} MiB" for r in sorted(fe, key=lambda r: r["ctx"])) + ".")
    else:
        out.append("\nNo first-ever cold record (every allocation's first launch loaded within 2× the cell's median load time).")
open(os.path.join(C, "ladder.md"), "w").write("\n".join(out) + "\n")
if csv_rows:
    with open(os.path.join(C, "ladder.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(csv_rows[0].keys())); w.writeheader(); w.writerows(csv_rows)

# records.md
rec = ["# Every record of the sitting (device-jsonl/), oldest first\n",
       "| round | launch | arm | model | task | ctx | regime | decode tok/s | decode wall | prefill tok/s | TTFT ms | prompt tok | out tok | stop | thermal start/peak/end | battery | resident peak MiB | load s | engine | build | file | outputSample (first 120 chars) |",
       "|---|---|---|---|---|---:|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
for r in sorted(rows, key=lambda r: r["ts"] or ""):
    def n(v, nd=1):
        return "—" if v is None else (f"{v:.{nd}f}" if isinstance(v, float) else str(v))
    rec.append(f"| {n(r['round'])} | {n(r['launch'])} | {r['arm']} | {str(r['model']).split('/')[-1]} | {r['task']} | {n(r['ctx'])} | {'cold' if r['cold'] else 'warm'} | "
               f"{n(r['decode'])} | {n(r['decode_wall'])} | {n(r['prefill'], 0)} | {n(r['ttft'])} | {n(r['p'])} | {n(r['g'])} | {r['stop']} | "
               f"{r['th_i']}/{r['th_p']}/{r['th_f']} | {n(r['battery'], 2)} {r['bstate']} | {n(r['rss'], 0)} | {n(r['load_s'], 2)} | {r['engine']} | {r['build']} | {r['file']} | {r['sample'][:120]} |")
open(os.path.join(C, "records.md"), "w").write("\n".join(rec) + "\n")

# text_check.md (LiteRT records)
# the asked topic itself contains "cannot" ("that a cloud model cannot"), so refusal verbs are not screened
REFUSAL = re.compile(r"\b(lorem|ipsum|placeholder|filler|no specific information|provided text|passage|numbered blocks)\b", re.I)
LIST_START = re.compile(r"(^|\\n|\s)(\*\*)?1[.)]")
tc = ["# Answer check of the LiteRT-LM records (outputSample = the first ~200 characters the app stored; not the whole text)\n",
      "| round | launch | model | ctx | regime | prompt tok | out tok | stop | numbered list starts | refusal / filler words | first 160 chars |",
      "|---|---|---|---:|---|---|---|---|---|---|---|"]
short = refuse = 0
for r in sorted([r for r in rows if str(r["arm"]).startswith("litert-lm")], key=lambda r: (r["ctx"] or 0, r["round"] or 0, r["ts"] or "")):
    s = r["sample"]
    lst = "yes" if LIST_START.search(s) else "no"
    bad = sorted({m.group(0).lower() for m in REFUSAL.finditer(s)})
    if r["g"] is not None and r["budget"] and r["g"] < r["budget"] - 2:
        short += 1
    if bad:
        refuse += 1
    tc.append(f"| {r['round']} | {r['launch']} | {str(r['model']).split('/')[-1]} | {r['ctx']} | {'cold' if r['cold'] else 'warm'} | {r['p']} | {r['g']} | {r['stop']} | {lst} | {','.join(bad) or '—'} | {s[:160]} |")
tc.append(f"\nLiteRT records: {sum(1 for r in rows if str(r['arm']).startswith('litert-lm'))}; short answers (< budget − 2): {short}; samples with refusal / filler words: {refuse}. "
          "A lexical screen is not a semantic review: read the samples.")
open(os.path.join(C, "text_check.md"), "w").write("\n".join(tc) + "\n")

# anchor.md
anc = [r for r in rows if r["round"] in (0, 99) and not str(r["arm"]).startswith("litert-lm")]
am = ["# Anchor launches (head = round 0, tail = round 99)\n",
      "| when | arm | model | regime | decode tok/s | out tok | thermal start→end | file |", "|---|---|---|---|---|---|---|---|"]
for r in sorted(anc, key=lambda r: r["ts"] or ""):
    am.append(f"| {'head' if r['round'] == 0 else 'tail'} | {r['arm']} | {str(r['model']).split('/')[-1]} | {'cold' if r['cold'] else 'warm'} | {r['decode']:.1f} | {r['g']} | {r['th_i']}→{r['th_f']} | {r['file']} |")
warm = [r["decode"] for r in anc if not r["cold"] and r["decode"]]
if warm:
    wm = statistics.median(warm)
    line = f"\nWarm anchor median over the sitting: {wm:.1f} tok/s (n={len(warm)}; head {', '.join(f'{r[chr(100)+chr(101)+chr(99)+chr(111)+chr(100)+chr(101)]:.1f}' for r in anc if r['round'] == 0 and not r['cold'])}; tail {', '.join(f'{r['decode']:.1f}' for r in anc if r['round'] == 99 and not r['cold']) or '—'})."
    if a.anchor_ref:
        line += f" Ratio to the reference {a.anchor_ref:.1f}: {wm / a.anchor_ref:.3f} ({'within' if abs(wm / a.anchor_ref - 1) <= 0.05 else 'outside'} the 5 % rule)."
    am.append(line)
else:
    am.append("\nNo anchor records.")
open(os.path.join(C, "anchor.md"), "w").write("\n".join(am) + "\n")
print("\n".join(out))
print("\n".join(am[-1:]))
print(f"wrote ladder.md / ladder.csv / records.md / text_check.md / anchor.md under {C}")
