#!/usr/bin/env python3
"""One row per (model, backend): unprofiled wall ms/step (ctrl run), profiled op/kernel
sums per recorded decode step grouped into weight-GEMV / attention+KV / transfer / other,
and launches per step. usage: prof_table.py <dir> <tag>..."""
import re, sys
from pathlib import Path
TAIL = re.compile(r"^(.*?)\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)%\s+([0-9.]+)%\s+([0-9.]+)\s+(\d+)\s+(\[.*)$")
def rows_of(p):
    text = p.read_text(errors="replace").splitlines()
    i = next(k for k, l in enumerate(text) if "Run Order" in l); out = []
    for l in text[i + 2:]:
        if l.strip().startswith("=====") and out: break
        m = TAIL.match(l)
        if m: out.append((m.group(1).strip(), float(m.group(4)), int(m.group(8))))
    return out
def speed(p, k):
    m = re.search(k + r" Speed: ([0-9.]+) tokens/sec", p.read_text(errors="replace")); return float(m.group(1)) if m else None
def group(n):
    s = n.lower()
    if "fully connected" in s or "fc1x1" in s or "fully_connected" in s or "convolution" in s: return "gemv"
    if any(k in s for k in ("batch matrix", "batched_mat_mul", "softmax", "slice", "add_values_to_cache", "dynamic_update", "concat")): return "attn+kv"
    if "upload" in s or "download" in s: return "xfer"
    return "other"
D = Path(sys.argv[1])
print(f"{'model':18s}{'be':4s}{'wall':>7s}{'steps':>6s}{'op-sum':>7s}{'gemv':>7s}{'attn+kv':>8s}{'xfer':>6s}{'other':>7s}{'unprof.':>8s}{'launch/step':>12s}")
for tag in sys.argv[2:]:
    for b in ("cpu", "gpu"):
        prof, ctrl = D / f"{tag}_{b}_prof.log", D / f"{tag}_{b}_ctrl.log"
        if not prof.exists() or not ctrl.exists(): continue
        rows = rows_of(prof); dec = [r for r in rows if r[2] >= 100]
        # recorded decode steps = the largest call count <= 300 (the profiler buffer can stop
        # short of 256; per-layer-body nodes are called layers*steps and normalise the same way)
        import collections
        steps = collections.Counter(r[2] for r in dec if r[2] <= 300).most_common(1)[0][0] if dec else 256
        sums = {"gemv": 0, "attn+kv": 0, "xfer": 0, "other": 0}; launches = 0
        for n, avg, called in dec:
            sums[group(n)] += avg * called / steps; launches += called / steps
        wall = 1000 / speed(ctrl, "Decode"); tot = sum(sums.values())
        print(f"{tag:18s}{b:4s}{wall:7.1f}{steps:6d}{tot:7.1f}{sums['gemv']:7.1f}{sums['attn+kv']:8.1f}{sums['xfer']:6.1f}{sums['other']:7.1f}{wall-tot:8.1f}{launches:12.0f}")
