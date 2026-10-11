#!/usr/bin/env python3
"""Build <dir>/table.md from binary_runs.sh outputs: <tag>.stdout.txt (the binary's BenchmarkInfo lines), <tag>.sample.csv
(the 1-second sampler), <tag>.logcat.txt (XNNPACK weight-cache line for CPU runs). usage: binary_table.py <dir> [tags…]"""
import glob, os, re, sys

D = sys.argv[1]
tags = sys.argv[2:] or sorted({os.path.basename(p)[:-11] for p in glob.glob(os.path.join(D, "*.stdout.txt"))}, key=lambda t: (t[0], int(re.sub(r"\D", "", t) or 0)))
ZONES = ["gpuss-0", "cpu-0-0-0", "cpu-1-0-0", "battery", "sys-therm-0"]


def g(pat, txt, grp=1, cast=float):
  m = re.search(pat, txt)
  return cast(m.group(grp)) if m else None


def sampler(tag):
  p = os.path.join(D, f"{tag}.sample.csv")
  rows = []
  for line in open(p) if os.path.exists(p) else []:
    f = line.split()
    if len(f) < 14:
      continue
    try:
      rows.append([float(x) for x in f[:8]] + [float(x) for x in f[9:14]])
    except ValueError:
      pass
  if not rows:
    return None
  return dict(n=len(rows), p0max=min(r[3] for r in rows) / 1000, p6max=min(r[5] for r in rows) / 1000, gpu=max(r[6] for r in rows),
              zones={ZONES[i]: (rows[0][8 + i] / 1000, max(r[8 + i] for r in rows) / 1000) for i in range(5)})


out = ["| tag | backend / bundle | process | prefill tok/s | decode tok/s | TTFT s | init ms | peak private MB | max_tokens | policy0 ceiling min (MHz of 3,628.8) | policy6 ceiling min (MHz of 4,742.4) | GPU max MHz | cpu-0-0-0 zone first → max °C | gpuss-0 zone first → max °C | XNNPACK cache |",
       "|---|---|---|---:|---:|---:|---:|---:|---:|---|---|---:|---|---|---|"]
steps = open(os.path.join(D, "steps.log")).read() if os.path.exists(os.path.join(D, "steps.log")) else ""
for tag in tags:
  so = open(os.path.join(D, f"{tag}.stdout.txt")).read()
  st = re.search(rf"START {tag} backend=(\w+) model=(\S+) mode=(\w+) .*?traced=(\d)", steps)
  be, model, mode, traced = (st.group(1), st.group(2), st.group(3), st.group(4)) if st else ("?", "?", "?", "0")
  pf = g(r"Prefill Speed: ([0-9.]+)", so); dc = g(r"Decode Speed: ([0-9.]+)", so); tt = g(r"Time to first token: ([0-9.]+)", so)
  it = g(r"Init Total: ([0-9.]+) ms", so); pk = g(r"Peak private footprint[^0-9]*([0-9.]+)", so); mt = g(r"max_tokens: (\d+)", so, cast=int)
  lc = open(os.path.join(D, f"{tag}.logcat.txt")).read() if os.path.exists(os.path.join(D, f"{tag}.logcat.txt")) else ""
  cache = "—"
  if be == "cpu":
    cache = "loaded" if "weight cache loaded from" in lc else ("built" if re.search(r"written to|weight cache build", lc) else "?")
  s = sampler(tag)
  f = lambda v, d=2: "—" if v is None else f"{v:.{d}f}"
  zc = s["zones"]["cpu-0-0-0"] if s else (None, None); zg = s["zones"]["gpuss-0"] if s else (None, None)
  out.append(f"| {tag} | {be} / {model} | {mode}{' (traced)' if traced == '1' else ''} | {f(pf)} | {f(dc)} | {f(tt)} | {f(it)} | {f(pk, 3)} | {mt or '—'} | "
             f"{f(s['p0max'], 1) if s else '—'} | {f(s['p6max'], 1) if s else '—'} | {f(s['gpu'], 0) if s else '—'} | {f(zc[0], 1)} → {f(zc[1], 1)} | {f(zg[0], 1)} → {f(zg[1], 1)} | {cache} |")
open(os.path.join(D, "table.md"), "w").write("\n".join(out) + "\n")
print("\n".join(out))
