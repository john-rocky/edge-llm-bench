#!/usr/bin/env python3
"""attrib3446.py <turns.ndjson> [...]
Per-turn phys_footprint attribution for LiteRT-LM #3446 (same arithmetic as the issue body).
Delta of footprintAfterTurnMB between consecutive turns; split by the turn's `rollover` flag.
Validated 2026-10-07 23:1x on results/raw/2026-09-01-mac-litert-endurance-v0160 (gemma-4-E2B):
  turns 3547 rollovers 197 first 680.1 last 827.2 total +147.1 | rollover: sum +198.3 mean +1.007 median +0.016 | plain: sum -51.3
= the numbers in the issue body (+198 MB over 197 rollovers, mean +1.0, median 0.016, plain -51 MB, 680 -> 827).
"""
import json, statistics, sys
for path in sys.argv[1:]:
    rows = [json.loads(l) for l in open(path) if l.strip()]
    fp = [r["footprintAfterTurnMB"] for r in rows]
    deltas = [fp[i] - fp[i-1] for i in range(1, len(rows))]
    roll = [bool(rows[i].get("rollover")) for i in range(1, len(rows))]
    rd = [d for d, r in zip(deltas, roll) if r]
    pd = [d for d, r in zip(deltas, roll) if not r]
    reasons = {}
    for r in rows:
        if r.get("rollover"):
            k = str(r.get("rolloverReason"))[:12]
            reasons[k] = reasons.get(k, 0) + 1
    print(path)
    print("  turns %d rollovers %d first %.1f MB last %.1f MB total %+.1f MB" % (len(rows), sum(1 for r in rows if r.get("rollover")), fp[0], fp[-1], fp[-1]-fp[0]))
    if rd:
        print("  rollover turns: n=%d sum %+.1f MB mean %+.3f median %+.3f max %+.1f" % (len(rd), sum(rd), statistics.mean(rd), statistics.median(rd), max(rd)))
    print("  plain turns:    n=%d sum %+.1f MB" % (len(pd), sum(pd)))
    print("  rollover reasons:", reasons)
