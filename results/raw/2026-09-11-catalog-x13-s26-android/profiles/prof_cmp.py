#!/usr/bin/env python3
"""CPU-vs-GPU per-op summary from litert_lm_advanced_main --enable_profiling logs
(the prof_summarize.py shape: Run Order rows, node types with spaces kept, phase
split by times-called: >= decode steps -> decode, else prefill).
usage: prof_cmp.py <dir> <tag> [decode_steps=256]"""
import re, sys
from collections import defaultdict
from pathlib import Path
D = Path(sys.argv[1]); tag = sys.argv[2]; STEPS = int(sys.argv[3]) if len(sys.argv) > 3 else 256
TAIL = re.compile(r"^(.*?)\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)%\s+([0-9.]+)%\s+([0-9.]+)\s+(\d+)\s+(\[.*)$")
def parse(path):
    text = path.read_text(errors="replace").splitlines()
    rows = []
    for i, l in enumerate(text):
        if "Run Order" in l:
            for l2 in text[i + 2:]:
                if l2.strip().startswith("=====") and rows: break
                m = TAIL.match(l2)
                if m: rows.append((m.group(1).strip(), float(m.group(4)), int(m.group(8)), m.group(9)))
            break
    full = "\n".join(text)
    def turn(kind):
        m = re.search(kind + r" Turn 1: Processed (\d+) tokens in ([0-9.]+)(ms|s)", full)
        return (int(m.group(1)), float(m.group(2)) * (1000 if m.group(3) == "s" else 1)) if m else (None, None)
    speed = {k: (re.search(k + r" Speed: ([0-9.]+) tokens/sec", full) or [None, None])[1] for k in ("Prefill", "Decode")}
    return rows, turn("Prefill"), turn("Decode"), speed
def short(t):
    t = t.replace("Delegate/", "")
    return re.sub(r"\s*\(.*?\)\s*", " ", t).strip()[:34]
out = {}
for b in ("cpu", "gpu"):
    p = D / f"{tag}_{b}_prof.log"
    if not p.exists(): print(f"missing {p}"); continue
    rows, pre, dec, speed = parse(p)
    tot = defaultdict(float); cnt = defaultdict(int)
    for ntype, avg, called, name in rows:
        phase = "decode" if called >= STEPS else "prefill"  # STEPS = decode-step threshold (v0.16.0 merged summary: decode nodes ~224-256 calls, per-layer bodies x28)
        tot[(phase, short(ntype))] += avg * called; cnt[(phase, short(ntype))] += 1
    out[b] = (tot, cnt, pre, dec, speed, len(rows))
    print(f"{tag} {b}: nodes {len(rows)}; prefill turn {pre}; decode turn {dec}; speeds {speed}; "
          f"profiled sum decode {sum(v for k,v in tot.items() if k[0]=='decode'):.0f} ms, prefill {sum(v for k,v in tot.items() if k[0]=='prefill'):.0f} ms")
for phase in ("decode", "prefill"):
    keys = sorted({k[1] for (t, *_ ) in out.values() for k in t if k[0] == phase},
                  key=lambda k: -max(t.get((phase, k), 0) for (t, *_ ) in out.values()))
    print(f"\n=== {tag} {phase}: ms summed over the turn ({STEPS} decode steps / all prefill calls); (n nodes) ===")
    print(f"{'node type':36s}{'cpu ms':>10s}{'gpu ms':>10s}{'gpu/cpu':>9s}  nodes cpu/gpu")
    for k in keys[:20]:
        c = out.get('cpu', ({},))[0].get((phase, k), 0.0); g = out.get('gpu', ({},))[0].get((phase, k), 0.0)
        nc = out.get('cpu', ({}, {}))[1].get((phase, k), 0); ng = out.get('gpu', ({}, {}))[1].get((phase, k), 0)
        r = f"{g/c:8.2f}" if c else "     n/a"
        print(f"{k:36s}{c:10.1f}{g:10.1f}{r:>9s}  {nc}/{ng}")
