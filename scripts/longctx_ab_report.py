#!/usr/bin/env python3
"""Per-allocation ladder report for a long-context round-mode campaign.

  python3 scripts/longctx_ab_report.py results/raw/<campaign> [--task long-context-2048-gen256]
                                       [--regime warm|cold] [--csv out.csv]

Reads every schema-v1 record in the campaign's *.jsonl files, groups them by
(runtime label, model id, task, contextTokensConfigured) and reports, per
regime (warm = runs 2..N of a launch, cold = run 1), the median [min-max] of
decode tok/s, prefill tok/s and TTFT over the rounds, plus the prompt / output
token counts and how many runs stopped short of the budget. The delta column
is each allocation against the smallest one of the same (arm, model) — the
"does decode track the allocated KV" reading of catalog row K5 / X2. Nothing
here pools across campaigns (one sitting per call).
"""
import argparse, csv, glob, json, os, statistics, sys


def load(campaign, task):
    rows = []
    for f in sorted(glob.glob(os.path.join(campaign, "*.jsonl"))):
        for line in open(f):
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            if task and d.get("task") != task:
                continue
            m = d.get("metrics", {})
            rows.append({
                "arm": d.get("runtime"), "model": d.get("model", {}).get("id"),
                "quant": d.get("model", {}).get("quantization"),
                "task": d.get("task"), "ctx": m.get("contextTokensConfigured"),
                "cold": bool(m.get("coldRun")), "decode": m.get("decodeTokensPerSecond"),
                "prefill": m.get("promptTokensPerSecond"), "ttft_ms": m.get("firstTokenLatencyMS"),
                "p": m.get("promptTokenCount"), "g": m.get("generatedTokenCount"),
                "stop": m.get("stopReason"), "thermal": m.get("peakThermalState"),
                "mem_peak": m.get("memoryPeakDuringDecodeMB"), "ts": d.get("timestamp"),
                "engine": d.get("engineVersion"), "file": os.path.basename(f),
            })
    return rows


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
    ap.add_argument("--regime", default="warm", choices=["warm", "cold"])
    ap.add_argument("--csv")
    a = ap.parse_args()
    rows = load(a.campaign, a.task)
    if not rows:
        sys.exit(f"no {a.task} records under {a.campaign}")
    sel = [r for r in rows if r["cold"] == (a.regime == "cold")]
    groups = {}
    for r in sel:
        groups.setdefault((r["arm"], r["model"], r["ctx"]), []).append(r)
    cells = sorted({(k[0], k[1]) for k in groups})
    out = []
    print(f"# {os.path.basename(a.campaign)} — {a.task}, regime {a.regime} (median [min–max] over rounds)\n")
    print("| arm | model | ctx | prompt tok | out tok (short stops) | prefill tok/s | TTFT ms | decode tok/s | Δ decode vs smallest ctx | peak thermal |")
    print("|---|---|---:|---:|---|---|---|---|---:|---|")
    for arm, model in cells:
        ctxs = sorted(c for (x, y, c) in groups if x == arm and y == model and c is not None)
        base = None
        for ctx in ctxs:
            g = groups[(arm, model, ctx)]
            dec = med([r["decode"] for r in g]); pre = med([r["prefill"] for r in g])
            ttft = med([r["ttft_ms"] for r in g])
            p = sorted({r["p"] for r in g}); gtoks = med([r["g"] for r in g])
            short = sum(1 for r in g if r["stop"] != "length")
            therm = sorted({r["thermal"] for r in g})
            if base is None and dec:
                base = dec[0]
            delta = f"{(dec[0] / base - 1) * 100:+.1f}%" if (dec and base) else "—"
            print(f"| {arm} | {model} | {ctx} | {'/'.join(map(str, p))} | {fmt(gtoks, 0)} ({short}) | {fmt(pre)} | {fmt(ttft, 0)} | {fmt(dec)} | {delta} | {','.join(map(str, therm))} |")
            out.append({"arm": arm, "model": model, "ctx": ctx, "regime": a.regime,
                        "n": dec[3] if dec else 0, "decode_med": dec[0] if dec else None,
                        "decode_min": dec[1] if dec else None, "decode_max": dec[2] if dec else None,
                        "prefill_med": pre[0] if pre else None, "ttft_med_ms": ttft[0] if ttft else None,
                        "prompt_tokens": "/".join(map(str, p)), "gen_tokens_med": gtoks[0] if gtoks else None,
                        "short_stops": short, "delta_vs_smallest_pct": (dec[0] / base - 1) * 100 if (dec and base) else None})
    if a.csv:
        with open(a.csv, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)
        print(f"\ncsv: {a.csv}")


if __name__ == "__main__":
    main()
