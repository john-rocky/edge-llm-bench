#!/usr/bin/env python3
"""Build gallery/table.md from the sessions' <tag>.results-ui.json (the app's result card and series sheets) and
<tag>.sample.csv (the 1-second sampler beside the session). Per-run values are the series sheet's {min, median, max}
assigned to runs by the order of the graph's points (see gallery_bench.py graph_point_order)."""
import glob, json, os, re, sys

OUT = sys.argv[1] if len(sys.argv) > 1 else "gallery"
ORDER = ["E2B-gpu-1", "E2B-gpu-2", "E2B-cpu-1", "G3-cpu-1", "G3-cpu-2", "G3-gpu-1"]
WINDOW_S = {"E2B-gpu-1": 30}        # the driver was stopped by hand for this one; the runs ended within ~27 s of Continue


def num(s):
  m = re.search(r"([0-9.]+)", s or "")
  return float(m.group(1)) if m else None


def sampler(tag, window_s):
  p = os.path.join(OUT, f"{tag}.sample.csv")
  if not os.path.exists(p):
    return None
  rows = []
  for line in open(p):
    f = line.split()
    if len(f) < 14:
      continue
    try:
      rows.append([float(f[0]), float(f[1])] + [float(x) for x in f[2:8]] + [float(x) for x in f[9:14]])
    except ValueError:
      continue
  if not rows:
    return None
  t0 = rows[0][0]
  win = [r for r in rows if r[0] - t0 <= window_s + 2]
  p0max = min(r[3] for r in win) / 1000; p6max = min(r[5] for r in win) / 1000
  gpu = max(r[6] for r in win); busy = max(r[7] for r in win)
  z = lambda i: (win[0][8 + i] / 1000, max(r[8 + i] for r in win) / 1000)
  return dict(n=len(win), p0max=p0max, p6max=p6max, gpu=gpu, busy=busy, gpuss=z(0), cpu0=z(1), cpu1=z(2))


rows = []
for tag in ORDER:
  p = os.path.join(OUT, f"{tag}.results-ui.json")
  if not os.path.exists(p):
    continue
  d = json.load(open(p)); ui = d["ui"]
  def pr(key):
    e = ui.get(key, {}); return e.get("per_run_by_graph"), e.get("stats", {})
  prefill, prefill_s = pr("prefill_tok_s"); decode, decode_s = pr("decode_tok_s"); ttft, ttft_s = pr("ttft_s"); steady, steady_s = pr("steady_init_ms")
  first_init = num(ui.get("first_init_ms", {}).get("avg_text"))
  elapsed = d.get("elapsed_s") or WINDOW_S.get(tag, 60)
  smp = sampler(tag, elapsed)
  fmt = lambda v: "—" if v is None else (f"{v:.2f}")
  runs = lambda L: " / ".join(fmt(x) for x in L) if L else "—"
  cap = "—"
  if smp:
    cap = f"{smp['p0max']:.1f} / {smp['p6max']:.1f}"
  rows.append(f"| {tag} | {d['model']} / {d['accel']} | {d['runs']} | {runs(prefill)} | {runs(decode)} | {runs(ttft)} | {fmt(first_init)} | {runs(steady)} | "
              f"{prefill_s.get('avg','—')} / {decode_s.get('avg','—')} / {ttft_s.get('avg','—')} | {cap} | "
              f"{smp['gpu']:.0f} ({smp['busy']:.0f} %) | {smp['cpu0'][0]:.1f} → {smp['cpu0'][1]:.1f} | {smp['gpuss'][0]:.1f} → {smp['gpuss'][1]:.1f} |" if smp else
              f"| {tag} | {d['model']} / {d['accel']} | {d['runs']} | {runs(prefill)} | {runs(decode)} | {runs(ttft)} | {fmt(first_init)} | {runs(steady)} | {prefill_s.get('avg','—')} / {decode_s.get('avg','—')} / {ttft_s.get('avg','—')} | — | — | — | — |")

hdr = ("| session | model / accelerator | runs | prefill tok/s run 1 / 2 / 3 | decode tok/s run 1 / 2 / 3 | TTFT s run 1 / 2 / 3 | first init ms (run 1) | steady init ms run 2 / 3 | "
       "app's avg prefill / decode / TTFT | policy0 / policy6 ceiling min during the runs (MHz of 3,628.8 / 4,742.4) | GPU max MHz (busy max) | cpu-0-0-0 zone first → max °C | gpuss-0 zone first → max °C |\n"
       "|---|---|---:|---|---|---|---:|---|---|---|---|---|---|")
open(os.path.join(OUT, "table.md"), "w").write(hdr + "\n" + "\n".join(rows) + "\n")
print(hdr); print("\n".join(rows))
