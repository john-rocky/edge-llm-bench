#!/usr/bin/env python3
"""Pooled table for NOTES/reply (2026-09-18): per cell (label without _A/_B, mode) the pooled median over all iterations of the
A and B processes, the per-process medians, min/max, and n_iterations; plus the prefill % deltas that PREREG names."""
import glob, os, re, statistics as st, sys, collections
D = sys.argv[1]
cells = collections.defaultdict(lambda: {"pre": {}, "dec": {}, "ttft": {}, "sm": 0, "rc": set()})
for f in sorted(glob.glob(os.path.join(D, "*_b1k.log")) + glob.glob(os.path.join(D, "*_b31k.log"))):
    name = os.path.basename(f)[:-4]; m = re.match(r"(.+)_([AB])_(b1k|b31k)$", name)
    if not m: continue
    label, proc, mode = m.groups(); t = open(f, errors="replace").read()
    c = cells[(label, mode)]
    c["pre"][proc] = [float(x) for x in re.findall(r"Prefill Speed: ([0-9.]+)", t)]
    c["dec"][proc] = [float(x) for x in re.findall(r"Decode Speed: ([0-9.]+)", t)]
    c["ttft"][proc] = [float(x) for x in re.findall(r"Time to first token: ([0-9.]+) s", t)]
    c["sm"] += t.count("Shape mismatch"); r = re.search(r"EXIT_CODE=(\d+)", t); c["rc"].add(r.group(1) if r else "?")
def pooled(d): 
    v = [x for p in sorted(d) for x in d[p]]; return (st.median(v), min(v), max(v), len(v)) if v else (None,)*4
def perproc(d): return " / ".join(f"{st.median(d[p]):.1f}" for p in sorted(d)) if d else "-"
order = ["new_06b_12","new_06b_11","ctl_06b_11","new_06b_11n","new_06b_9","ctl_06b_9","new_4b_12","new_4b_11","ctl_4b_11","new_4b_11n","new_4b_9","ctl_4b_9","ctl_06b_12","ctl_4b_12"]
for mode in ("b31k","b1k"):
    print(f"\n== {mode} ==  (pooled median [min–max, n] | per-process medians A / B)")
    for label in order:
        if (label, mode) not in cells: continue
        c = cells[(label, mode)]; pp = pooled(c["pre"]); dp = pooled(c["dec"]); tp = pooled(c["ttft"])
        print(f"{label:12} {mode:4} rc={','.join(sorted(c['rc']))} sm={c['sm']}  prefill {pp[0]:8.1f} [{pp[1]:.0f}–{pp[2]:.0f}, n={pp[3]}] ({perproc(c['pre'])})   decode {dp[0]:6.1f} [{dp[1]:.1f}–{dp[2]:.1f}] ({perproc(c['dec'])})   ttft {tp[0]:.2f} s")
def pm(label, mode, k="pre"): return pooled(cells[(label, mode)][k])[0]
def pp_all(label, mode, k="pre"): return [st.median(v) for v in cells[(label, mode)][k].values()]
print("\n== PREREG deltas (pooled medians; per-process medians must not overlap for 'lands') ==")
for b in ("06b","4b"):
    for mode in ("b31k","b1k"):
        a, c = pm(f"new_{b}_12", mode), pm(f"new_{b}_11", mode); n = pm(f"new_{b}_11n", mode)
        A, C = pp_all(f"new_{b}_12", mode), pp_all(f"new_{b}_11", mode)
        lands = min(A) > max(C)
        print(f"{b} {mode}: prefill 12flags {a:.0f} vs 11flags(published) {c:.0f} → {100*(a/c-1):+.1f} % ; vs 11flags(1e2d37f) {n:.0f} → {100*(a/n-1):+.1f} % ; per-process A {['%.0f'%x for x in A]} C {['%.0f'%x for x in C]} → non-overlapping={lands}")
        da, dc = pm(f"new_{b}_12", mode, "dec"), pm(f"new_{b}_11", mode, "dec")
        print(f"          decode 12flags {da:.1f} vs 11flags {dc:.1f} → {100*(da/dc-1):+.1f} %")
        d = pm(f"ctl_{b}_11", mode); print(f"          dylib swap on the published 11-flag file: new {c:.0f} vs 09-17 dylib {d:.0f} → {100*(c/d-1):+.1f} % (prefill); decode {dc:.1f} vs {pm(f'ctl_{b}_11', mode, 'dec'):.1f}")
