#!/usr/bin/env python3
"""Per-allocation ladder report for a long-context round-mode campaign.

  python3 scripts/longctx_ab_report.py results/raw/<campaign> [--task long-context-2048-gen256]
                                       [--regime warm|cold|cold-process|first-ever] [--csv out.csv]
                                       [--rounds 1,2,3]

Reads schema-v1 records in the campaign's *.jsonl or app-path-android/*.json,
groups by (runtime label, model id, artifact, allocation) and reports, per
regime (warm = runs 2..N, cold = run 1, cold-process = Android control), the median [min-max] of
decode tok/s, prefill tok/s and TTFT over the rounds, plus the prompt / output
token counts and how many runs stopped short of the budget. The delta column
is each allocation against the smallest one of the same (arm, model) — the
"does decode track the allocated KV" reading of catalog row K5 / X2. Nothing
here pools across campaigns (one sitting per call).
"""
import argparse, csv, glob, json, os, statistics, sys


def load(campaign, task, review=None):
    rows = []
    files = (glob.glob(os.path.join(campaign, "*.jsonl")) +
             glob.glob(os.path.join(campaign, "app-path-android", "*.json")))
    for f in sorted(files):
        with open(f) as fh:
            records = ([json.load(fh)] if f.endswith(".json") else
                       [json.loads(line) for line in fh if line.strip()])
        for d in records:
            if d.get("schemaVersion") != 1:
                continue
            if task and d.get("task") != task:
                continue
            m = d.get("metrics", {})
            c = d.get("conditions", {})
            android = d.get("device", {}).get("systemName") == "Android" or f.endswith(".json")
            regime = c.get("regime") or ("cold-process" if android and m.get("coldRun")
                                         else "cold" if m.get("coldRun") else "warm")
            # Invalid engine evidence never becomes a reported rate. Keep the
            # row and its flags visible for the session reviewer's round admission.
            flags = sorted(set(c.get("protocolFlags", [])) |
                           set((review or {}).get(d.get("id"), [])))
            rows.append({
                "arm": d.get("runtime"), "model": d.get("model", {}).get("id"),
                "quant": d.get("model", {}).get("quantization"),
                "task": d.get("task"), "ctx": m.get("contextTokensConfigured", c.get("contextTokens")),
                "cold": bool(m.get("coldRun")), "decode": m.get("decodeTokensPerSecond"),
                "prefill": m.get("promptTokensPerSecond"), "ttft_ms": m.get("firstTokenLatencyMS"),
                "p": m.get("promptTokenCount"), "g": m.get("generatedTokenCount"),
                "stop": m.get("stopReason"),
                "mem_peak": m.get("memoryPeakResidentMB"),
                "mem_basis": "sampled launch VmHWM, MiB" if android else "resident peak (memoryPeakResidentMB), MiB",
                "ts": d.get("timestamp"), "record_id": d.get("id"), "source": f,
                "engine": d.get("engineVersion"), "file": os.path.basename(f),
                "artifact": d.get("model", {}).get("file") or d.get("model", {}).get("primaryFile", ""),
                "regime": regime, "round": c.get("roundIndex"),
                "launch": c.get("launchIndex"), "firstEver": m.get("firstEver", False),
                "flags": flags, "budget": c.get("outputTokenBudget", 256),
                "thermal": m.get("peakThermalState") or m.get("initialThermalState"),
                "thermal_flag": c.get("initialThermalNonNominal", False),
            })
            if flags:
                for metric in ("decode", "prefill", "ttft_ms", "mem_peak"):
                    rows[-1][metric] = None
    return rows


def select(rows, regime, rounds=None):
    """Explicit round selection never merges sittings or first-ever and cold."""
    return [r for r in rows if (rounds is None or r["round"] in rounds)
            and (r["firstEver"] if regime == "first-ever" else
                 r["regime"] == regime and not r["firstEver"])]


def med(vals):
    vals = [v for v in vals if v]
    if not vals:
        return None
    return statistics.median(vals), min(vals), max(vals), len(vals)


def fmt(t, nd=1):
    if not t:
        return "—"
    m, lo, hi, n = t
    return f"{m:.{nd}f} [{lo:.{nd}f}–{hi:.{nd}f}] n={n}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("campaign")
    ap.add_argument("--task", default="long-context-2048-gen256")
    ap.add_argument("--regime", default="warm", choices=["warm", "cold", "cold-process", "first-ever"])
    ap.add_argument("--rounds", help="explicit completed rounds to report; omitted = all stored rounds")
    ap.add_argument("--review", help="JSON mapping record IDs to additional failure flags; raw records stay unchanged")
    ap.add_argument("--csv")
    a = ap.parse_args()
    with open(a.review) if a.review else open(os.devnull) as fh:
        review = json.load(fh) if a.review else None
    rows = load(a.campaign, a.task, review)
    if not rows:
        sys.exit(f"no {a.task} records under {a.campaign}")
    rounds = {int(x) for x in a.rounds.split(",")} if a.rounds else None
    sel = select(rows, a.regime, rounds)
    if not sel:
        sys.exit(f"no {a.regime} records (firstEver excluded) under {a.campaign}")
    groups = {}
    for r in sel:
        groups.setdefault((r["arm"], r["model"], r["artifact"], r["ctx"]), []).append(r)
    cells = sorted({k[:3] for k in groups})
    out = []
    print(f"# {os.path.basename(a.campaign)} — {a.task}, regime {a.regime} (median [min–max] over rounds)\n")
    if rounds is not None:
        print(f"Selected rounds: {','.join(map(str, sorted(rounds)))}; admission remains the session reviewer's decision.\n")
    if a.regime == "first-ever":
        print("First-ever cache-build observations only; these are not engine-speed estimates.\n")
    for arm, model, artifact in cells:
        print(f"\n## {arm} — {model}\n")
        print("| arm | model | file / recipe | ctx | prompt tok | out tok (short / unknown) | prefill tok/s | TTFT ms | decode tok/s | peak RSS | Δ from smallest ctx | thermal | flags |")
        print("|---|---|---|---:|---:|---|---|---|---|---|---:|---|---|")
        ctxs = sorted(c for (x, y, f, c) in groups if (x, y, f) == (arm, model, artifact) and isinstance(c, int))
        versions = {r["engine"] for r in sel if (r["arm"], r["model"], r["artifact"]) == (arm, model, artifact)}
        if len(versions) > 1:
            sys.exit(f"mixed engine versions for {arm} {model} {artifact}: {versions}")
        base = None
        for ctx in ctxs:
            g = groups[(arm, model, artifact, ctx)]
            dec = med([r["decode"] for r in g]); pre = med([r["prefill"] for r in g])
            ttft = med([r["ttft_ms"] for r in g])
            rss = med([r["mem_peak"] for r in g])
            p = sorted({r["p"] for r in g}, key=str); gtoks = med([r["g"] for r in g])
            short = sum(1 for r in g if r["g"] is not None and r["g"] < r["budget"])
            unknown = sum(1 for r in g if r["g"] is None)
            therm = sorted({r["thermal"] for r in g}, key=str)
            flags = sorted({flag for r in g for flag in r["flags"]} |
                           ({"non-nominal-start"} if any(r["thermal_flag"] for r in g) else set()))
            if ctx == ctxs[0]:
                base = dec[0] if dec else None
            delta = f"{(dec[0] / base - 1) * 100:+.1f}%" if (dec and base) else "—"
            quant = g[0]["quant"]
            print(f"| {arm} | {model} | {artifact} / {quant} | {ctx} | {'/'.join(map(str, p))} | {fmt(gtoks, 0)} ({short} / {unknown}) | {fmt(pre)} | {fmt(ttft, 0)} | {fmt(dec)} | {fmt(rss)} | {delta} | {','.join(map(str, therm))} | {','.join(flags)} |")
            out.append({"arm": arm, "model": model, "ctx": ctx, "regime": a.regime,
                        "artifact": artifact, "quant": quant,
                        "rounds": "/".join(map(str, sorted({r['round'] for r in g}, key=str))),
                        "flags": ",".join(flags), "unknown_output_counts": unknown,
                        "n": dec[3] if dec else 0, "decode_med": dec[0] if dec else None,
                        "decode_min": dec[1] if dec else None, "decode_max": dec[2] if dec else None,
                        "prefill_med": pre[0] if pre else None, "ttft_med_ms": ttft[0] if ttft else None,
                        "prompt_tokens": "/".join(map(str, p)), "gen_tokens_med": gtoks[0] if gtoks else None,
                        "short_stops": short, "delta_vs_smallest_pct": (dec[0] / base - 1) * 100 if (dec and base) else None,
                        "prefill_min": pre[1] if pre else None, "prefill_max": pre[2] if pre else None,
                        "prefill_n": pre[3] if pre else 0, "ttft_min_ms": ttft[1] if ttft else None,
                        "ttft_max_ms": ttft[2] if ttft else None, "ttft_n": ttft[3] if ttft else 0,
                        "rss_med": rss[0] if rss else None, "rss_min": rss[1] if rss else None,
                        "rss_max": rss[2] if rss else None, "rss_n": rss[3] if rss else 0,
                        "rss_basis": g[0]["mem_basis"], "records": len(g),
                        "flagged_records": sum(bool(r["flags"]) for r in g)})
        print("\nRSS basis: " + "; ".join(sorted({r["mem_basis"] for r in sel if (r["arm"], r["model"], r["artifact"]) == (arm, model, artifact)})))
        for target in (4096, 8192):
            entry = next((r for r in out if (r["arm"], r["model"], r["artifact"], r["ctx"]) == (arm, model, artifact, target)), None)
            if ctxs and ctxs[0] == 2304 and entry:
                delta = entry["delta_vs_smallest_pct"]
                print(f"\nΔ 2304→{target} (ratio of decode medians): " + (f"{delta:+.1f}%" if delta is not None else "unavailable"))
    if not out:
        sys.exit("no numeric context allocations in the selected records")
    if a.csv:
        with open(a.csv, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)
        print(f"\ncsv: {a.csv}")


if __name__ == "__main__":
    main()
