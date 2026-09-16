#!/usr/bin/env python3
"""Decode-phase per-node-type table from ONE profiled log (GPU-only pairs): ms per decode step,
share of the profiled op sum, group (prof_table.group), node count. Container rows (LITERT_*) are
listed apart. Usage: gpu_nodes.py <prof.log> <ctrl.log> [--decode-steps 256] [--top 25]"""
import sys, re, argparse
from collections import defaultdict
sys.path.insert(0, '/Users/majimadaisuke/code/edge-llm-bench/scripts/profile')
import prof_cmp, prof_table
ap = argparse.ArgumentParser(); ap.add_argument('prof'); ap.add_argument('ctrl'); ap.add_argument('--decode-steps', type=int, default=256); ap.add_argument('--top', type=int, default=25)
a = ap.parse_args()
rows, pre, dec, speed = prof_cmp.parse(a.prof)
_, cpre, cdec, cspeed = prof_cmp.parse(a.ctrl)
called_counts = defaultdict(int)
for ntype, avg, called, _ in rows:
    if called >= a.decode_steps: called_counts[called] += 1
steps = max(called_counts, key=called_counts.get) if called_counts else a.decode_steps
tot, cnt, grp = defaultdict(float), defaultdict(int), {}
container = defaultdict(float)
for ntype, avg, called, _ in rows:
    if called < a.decode_steps: continue
    k = prof_cmp.short(ntype)
    if prof_table.CONTAINER.match(ntype.strip()):
        container[k] += avg * called / steps; continue
    tot[k] += avg * called / steps; cnt[k] += 1; grp[k] = prof_table.group(ntype)
opsum = sum(tot.values())
wall = 1000.0 / cspeed['Decode'] if cspeed.get('Decode') else None
print(f"control decode {cspeed.get('Decode')} tok/s (wall {wall:.2f} ms/step); profiled decode {speed.get('Decode')} tok/s; recorded steps {steps}; profiled op sum {opsum:.2f} ms/step; container {dict((k, round(v,2)) for k,v in container.items())}")
bygroup = defaultdict(float)
for k, v in tot.items(): bygroup[grp[k]] += v
print("groups (ms/step, share of op sum): " + ", ".join(f"{g} {bygroup[g]:.2f} ({100*bygroup[g]/opsum:.0f}%)" for g in ('gemv','attn+kv','xfer','other') if bygroup[g]))
print(f"{'node type':40s}{'ms/step':>9s}{'share':>7s}  group   nodes")
for k in sorted(tot, key=lambda k: -tot[k])[:a.top]:
    print(f"{k:40s}{tot[k]:9.3f}{100*tot[k]/opsum:6.1f}%  {grp[k]:7s} {cnt[k]}")
