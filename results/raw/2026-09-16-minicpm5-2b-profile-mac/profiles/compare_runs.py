#!/usr/bin/env python3
"""Side-by-side of two profiled runs (ms/step per node type + groups) — run1 dir/tag vs run2 dir/tag."""
import sys, re
from collections import defaultdict
sys.path.insert(0, '/Users/majimadaisuke/code/edge-llm-bench/scripts/profile')
import prof_cmp, prof_table
def load(prof, ctrl, steps_req=256):
    rows, _, _, sp = prof_cmp.parse(prof); _, _, _, csp = prof_cmp.parse(ctrl)
    cc = defaultdict(int)
    for _, _, called, _ in rows:
        if called >= steps_req: cc[called] += 1
    steps = max(cc, key=cc.get)
    tot = defaultdict(float); grp = {}
    for ntype, avg, called, _ in rows:
        if called < steps_req or prof_table.CONTAINER.match(ntype.strip()): continue
        k = prof_cmp.short(ntype); tot[k] += avg * called / steps; grp[k] = prof_table.group(ntype)
    return tot, grp, csp['Decode'], sp['Decode'], steps
a = load(sys.argv[1], sys.argv[2]); b = load(sys.argv[3], sys.argv[4])
print(f"ctrl decode: run1 {a[2]} tok/s, run2 {b[2]} tok/s; prof decode {a[3]} / {b[3]}; steps {a[4]} / {b[4]}")
sa, sb = sum(a[0].values()), sum(b[0].values())
print(f"op sum ms/step: run1 {sa:.2f}, run2 {sb:.2f}")
ga, gb = defaultdict(float), defaultdict(float)
for k, v in a[0].items(): ga[a[1][k]] += v
for k, v in b[0].items(): gb[b[1][k]] += v
for g in ('gemv', 'attn+kv', 'other'):
    print(f"  {g:8s} run1 {ga[g]:6.2f} ({100*ga[g]/sa:4.1f}%)  run2 {gb[g]:6.2f} ({100*gb[g]/sb:4.1f}%)")
print(f"{'node type':40s}{'run1 ms':>9s}{'run2 ms':>9s}{'run1 %':>8s}{'run2 %':>8s}")
for k in sorted(set(a[0]) | set(b[0]), key=lambda k: -max(a[0].get(k, 0), b[0].get(k, 0)))[:14]:
    print(f"{k:40s}{a[0].get(k,0):9.3f}{b[0].get(k,0):9.3f}{100*a[0].get(k,0)/sa:7.1f}%{100*b[0].get(k,0)/sb:7.1f}%")
