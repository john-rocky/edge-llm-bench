#!/usr/bin/env python3
"""Summarize leg logs (litert_lm_advanced_main --benchmark, num_iterations=3): per-iteration prefill/decode tok/s + medians."""
import glob, os, re, statistics as st, sys
D = sys.argv[1]
rows = []
for f in sorted(glob.glob(os.path.join(D, "*_b1k.log")) + glob.glob(os.path.join(D, "*_b31k.log"))):
    t = open(f, errors="replace").read()
    pre = [float(x) for x in re.findall(r"Prefill Speed: ([0-9.]+)", t)]
    dec = [float(x) for x in re.findall(r"Decode Speed: ([0-9.]+)", t)]
    ttft = [float(x) for x in re.findall(r"Time to first token: ([0-9.]+) s", t)]
    sm = t.count("Shape mismatch"); ve = t.count("Validation error"); rc = re.search(r"EXIT_CODE=(\d+)", t)
    ntok = re.findall(r"Prefill Turn 1: Processed (\d+) tokens", t)
    rows.append((os.path.basename(f), rc.group(1) if rc else "?", sm, ve, ntok[0] if ntok else "?", pre, dec, ttft))
print(f"{'leg':34} rc sm  verr prefill_tok  prefill tok/s (3 iters) -> median   decode tok/s (3 iters) -> median   ttft s")
for name, rc, sm, ve, ntok, pre, dec, ttft in rows:
    p = "/".join(f"{x:.0f}" for x in pre); d = "/".join(f"{x:.1f}" for x in dec); tt = "/".join(f"{x:.2f}" for x in ttft)
    pm = f"{st.median(pre):.0f}" if pre else "-"; dm = f"{st.median(dec):.1f}" if dec else "-"
    print(f"{name:34} {rc:>2} {sm:3d} {ve:4d}  {ntok:>6}  {p:>24} -> {pm:>6}   {d:>20} -> {dm:>6}   {tt}")
