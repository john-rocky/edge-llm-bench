#!/usr/bin/env python3
"""Long-context allocation ladder: one campaign against another, in the summary's own terms.

  python3 scripts/longctx_ladder_diff.py \\
      --baseline campaign:2026-09-18-dashboard-longctx-v1-m4max-mac \\
      --candidate campaign:<new campaign> [--task long-context-2048-gen256] [--csv-out FILE]

The dashboard's long-context column (matrices/dashboard-longctx-v1*.cells) measures one
(device, arm, model) cell at three KV allocations, 2304 / 4096 / 8192. The question the
column asks is within-session: does decode at a fixed filled length fall with the
allocated length? So the table prints, per allocation, both sides' medians and — the
number that is comparable across sittings — each side's Δ against its own smallest
allocation. The raw candidate/baseline ratio is printed as information only: two
sittings drift 16–25 % (CLAUDE.md "never pool across capture sessions"); the scored
verdicts come from regression_diff.py, whose cell key carries context_tokens since
2026-10-02 and which normalizes cross-session pairs through the session anchor.

Aggregation is render_leaderboard.arm_row (the repo's one aggregation — not a second
one): warm median / spread / n, cold median / spread / n, prefill and TTFT medians, per
(device, runtime, model_id, task, context_tokens) within one campaign. Regime per
ladder: warm where both sides have warm runs (Mac RUNS=2, Android advanced_main
iteration 2), else cold (llama.cpp on Android is cold-process only).
"""
import argparse
import csv
import os
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import regression_diff  # noqa: E402  (select / load_csv / rebuild_summary)
import render_leaderboard  # noqa: E402  (arm_row)

KEY = ("device", "runtime", "model_id", "task", "context_tokens")


def ladders(rows, task):
    """{(device, runtime, model_id): {ctx: arm_row dict}} for one selection."""
    cells = {}
    for r in rows:
        if r["task"] != task or not r["context_tokens"]:
            continue
        cells.setdefault(tuple(r[k] for k in KEY), []).append(r)
    out = {}
    for key, cell_rows in cells.items():
        out.setdefault(key[:3], {})[int(key[4])] = render_leaderboard.arm_row(cell_rows)
    return out


def regime_of(a, b):
    if a and b and a["warm_n"] and b["warm_n"]:
        return "warm"
    return "cold"


def med(row, regime):
    if row is None:
        return None, 0, 0.0
    if regime == "warm":
        return row["warm"], row["warm_n"], row["spread"]
    return row["cold_median"], row["cold_n"], row["cold_spread"]


def fmt(v, n, spread):
    if v is None:
        return "—"
    return f"{v:.1f} (n={n}, spread {spread:.0f}%)"


def pct(num, den):
    if num is None or not den:
        return None
    return (num / den - 1) * 100


def fpct(v):
    return "—" if v is None else f"{v:+.1f}%"


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--baseline", required=True, help="campaign:<substr> or engine:<prefix>")
    ap.add_argument("--candidate", required=True, help="campaign:<substr> or engine:<prefix>")
    ap.add_argument("--task", default="long-context-2048-gen256")
    ap.add_argument("--csv-out", help="also write the rows as CSV")
    ap.add_argument("--no-rebuild", action="store_true",
                    help="read results/summary as is (default: build_summary.py first)")
    args = ap.parse_args()
    if not args.no_rebuild:
        regression_diff.rebuild_summary()
    rows = regression_diff.load_csv("device-runs.csv")
    base = ladders(regression_diff.select(rows, args.baseline), args.task)
    cand = ladders(regression_diff.select(rows, args.candidate), args.task)
    common = sorted(set(base) & set(cand))
    if not common:
        print(f"no common ladder between {args.baseline} and {args.candidate} for task "
              f"{args.task}; ladders seen:", file=sys.stderr)
        for side, lad in (("baseline", base), ("candidate", cand)):
            for k in sorted(lad):
                print(f"  {side}: {' '.join(k)} ctx {sorted(lad[k])}", file=sys.stderr)
        return 2
    out_rows = []
    print(f"# {args.task} — {args.baseline} (baseline) vs {args.candidate} (candidate)\n")
    print("Δ vs smallest ctx is each side's own within-session number (the column's question); "
          "cand/base is cross-session and informational only (session drift 16–25 %).\n")
    print("| device | arm | model | ctx | regime | baseline decode tok/s | candidate decode tok/s "
          "| Δ vs smallest ctx (base) | Δ vs smallest ctx (cand) | cand/base | prefill base → cand | TTFT ms base → cand |")
    print("|---|---|---|---:|---|---|---|---:|---:|---:|---|---|")
    for key in common:
        b, c = base[key], cand[key]
        ctxs = sorted(set(b) | set(c))
        regime = regime_of(b.get(ctxs[0]), c.get(ctxs[0]))
        b0 = med(b.get(min(b)), regime)[0] if b else None
        c0 = med(c.get(min(c)), regime)[0] if c else None
        for ctx in ctxs:
            bv, bn, bs = med(b.get(ctx), regime)
            cv, cn, cs = med(c.get(ctx), regime)
            db, dc = pct(bv, b0), pct(cv, c0)
            ratio = pct(cv, bv)
            bp = b.get(ctx, {}).get("prefill") if b.get(ctx) else None
            cp = c.get(ctx, {}).get("prefill") if c.get(ctx) else None
            bt = b.get(ctx, {}).get("ttft") if b.get(ctx) else None
            ct = c.get(ctx, {}).get("ttft") if c.get(ctx) else None
            p = (f"{bp:.0f} → {cp:.0f}" if bp and cp else "—")
            t = (f"{bt:.0f} → {ct:.0f}" if bt and ct else "—")
            print(f"| {key[0]} | {key[1]} | {key[2]} | {ctx} | {regime} | {fmt(bv, bn, bs)} | "
                  f"{fmt(cv, cn, cs)} | {fpct(db)} | {fpct(dc)} | {fpct(ratio)} | {p} | {t} |")
            out_rows.append({"device": key[0], "arm": key[1], "model": key[2], "ctx": ctx,
                             "regime": regime, "base_decode_med": bv, "base_n": bn,
                             "base_spread_pct": round(bs, 1), "cand_decode_med": cv,
                             "cand_n": cn, "cand_spread_pct": round(cs, 1),
                             "base_delta_vs_smallest_pct": db, "cand_delta_vs_smallest_pct": dc,
                             "cand_over_base_pct": ratio, "base_prefill_med": bp,
                             "cand_prefill_med": cp, "base_ttft_med_ms": bt, "cand_ttft_med_ms": ct})
    if args.csv_out:
        with open(args.csv_out, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(out_rows[0].keys()))
            w.writeheader()
            w.writerows(out_rows)
        print(f"\ncsv: {args.csv_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
