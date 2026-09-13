#!/usr/bin/env python3
"""Run Order parse that keeps node types with spaces (Delegate/... rows). Totals per node type,
split by times-called (prefill signature calls vs 256 decode steps)."""
import re, sys
from collections import defaultdict
from pathlib import Path
S = Path(sys.argv[1])
TAIL = re.compile(r"^(.*?)\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)%\s+([0-9.]+)%\s+([0-9.]+)\s+(\d+)\s+(\[.*)$")
def parse(path):
    text = path.read_text().splitlines()
    i = next(k for k, l in enumerate(text) if "Run Order" in l)
    rows = []
    for l in text[i + 2:]:
        if l.strip().startswith("=====") and rows: break
        m = TAIL.match(l)
        if not m: continue
        rows.append((m.group(1).strip(), float(m.group(4)), int(m.group(8))))
    return rows
def short(t):
    t = t.replace("Delegate/", "")
    return re.sub(r"\s*\(.*?\)\s*", " ", t).replace(" GEMM", "").strip()[:26]
KEEP = ["Batch Matrix Multiply", "Fully Connected", "Softmax", "SELECT_V2", "DYNAMIC_UPDATE_SLICE", "YNNPackDelegate", "Add", "Multiply", "Mean Squared", "Slice", "Transpose", "Copy"]
out = {}
for cfg in ["max1280", "max4096", "p4096"]:
    for side in "AB":
        p = S / f"prof_{side}_{cfg}.log"; rows = parse(p); text = p.read_text()
        dec = re.search(r"Decode Turn 1: Processed (\d+) tokens in ([0-9.]+)(ms|s)", text)
        pre = re.search(r"Prefill Turn 1: Processed (\d+) tokens in ([0-9.]+)(ms|s)", text)
        decode_ms = float(dec.group(2)) * (1000 if dec.group(3) == "s" else 1)
        prefill_ms = float(pre.group(2)) * (1000 if pre.group(3) == "s" else 1)
        tot = defaultdict(float)
        for ntype, avg, called in rows:
            phase = "decode" if called >= 256 else "prefill"
            tot[(phase, short(ntype))] += avg * called
        out[(side, cfg)] = (tot, decode_ms, prefill_ms, len(rows))
        n = len(rows)
        print(f"{side} {cfg}: nodes parsed {n}; reported decode turn {decode_ms:.0f} ms, prefill turn {prefill_ms:.0f} ms; "
              f"profiled sum decode {sum(v for k,v in tot.items() if k[0]=='decode'):.0f} ms, prefill {sum(v for k,v in tot.items() if k[0]=='prefill'):.0f} ms")
for phase in ("decode", "prefill"):
    print(f"\n=== {phase} phase, ms summed over the turn (256 steps / all prefill calls) ===")
    keys = sorted({k[1] for (t, *_ ) in out.values() for k in t if k[0] == phase}, key=lambda k: -max(t[(phase, k)] for (t, *_ ) in out.values() if (phase, k) in t))
    hdr = f"{'node type':28s}" + "".join(f"{s}-{c:8s}" for c in ["max1280","max4096","p4096"] for s in "AB")
    print(hdr)
    for k in keys[:14]:
        line = f"{k:28s}"
        for c in ["max1280","max4096","p4096"]:
            for s in "AB":
                v = out[(s, c)][0].get((phase, k), 0.0)
                line += f"{v:10.1f}"
        print(line)
