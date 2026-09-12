#!/usr/bin/env python3
"""CPU-vs-GPU per-node-type summary from litert_lm_advanced_main --enable_profiling logs.

Reads <dir>/<tag>_cpu_prof.log and <dir>/<tag>_gpu_prof.log. Every Run Order
row is assigned to a phase by its "times called": at least the decode-step
count -> decode, else prefill; per (phase, node type) the ms are summed over
the turn. Output: the top node types per phase with cpu ms, gpu ms, the ratio
and the node counts.

  python3 scripts/profile/prof_cmp.py <dir> <tag> [--decode-steps 256] [--top 20]
"""
import argparse
import re
from collections import defaultdict
from pathlib import Path

TAIL = re.compile(r"^(.*?)\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)%\s+([0-9.]+)%\s+"
                  r"([0-9.]+)\s+(\d+)\s+(\[.*)$")


def parse(path):
    text = Path(path).read_text(errors="replace").splitlines()
    rows = []
    for i, l in enumerate(text):
        if "Run Order" in l:
            for l2 in text[i + 2:]:
                if l2.strip().startswith("=====") and rows:
                    break
                m = TAIL.match(l2)
                if m:
                    rows.append((m.group(1).strip(), float(m.group(4)), int(m.group(8)), m.group(9)))
            break
    full = "\n".join(text)

    def turn(kind):
        m = re.search(kind + r" Turn 1: Processed (\d+) tokens in ([0-9.]+)(ms|s)", full)
        return (int(m.group(1)), float(m.group(2)) * (1000 if m.group(3) == "s" else 1)) if m else (None, None)

    speeds = {}
    for k in ("Prefill", "Decode"):
        m = re.search(k + r" Speed: ([0-9.]+) tokens/sec", full)
        speeds[k] = float(m.group(1)) if m else None
    return rows, turn("Prefill"), turn("Decode"), speeds


def short(t):
    t = t.replace("Delegate/", "")
    return re.sub(r"\s*\(.*?\)\s*", " ", t).strip()[:34]


def compare(d, tag, steps=256, top=20):
    """-> text report (empty string when neither backend's log exists)."""
    d = Path(d)
    out = {}
    lines = []
    for b in ("cpu", "gpu"):
        p = d / f"{tag}_{b}_prof.log"
        if not p.exists():
            continue
        rows, pre, dec, speed = parse(p)
        tot, cnt = defaultdict(float), defaultdict(int)
        for ntype, avg, called, _name in rows:
            phase = "decode" if called >= steps else "prefill"
            tot[(phase, short(ntype))] += avg * called
            cnt[(phase, short(ntype))] += 1
        out[b] = (tot, cnt)
        lines.append(f"{tag} {b}: nodes {len(rows)}; prefill turn {pre}; decode turn {dec}; speeds {speed}; "
                     f"profiled sum decode {sum(v for k, v in tot.items() if k[0] == 'decode'):.0f} ms, "
                     f"prefill {sum(v for k, v in tot.items() if k[0] == 'prefill'):.0f} ms")
    if not out:
        return ""
    for phase in ("decode", "prefill"):
        keys = sorted({k[1] for (t, _c) in out.values() for k in t if k[0] == phase},
                      key=lambda k: (-max(t.get((phase, k), 0) for (t, _c) in out.values()), k))
        lines.append("")
        lines.append(f"=== {tag} {phase}: ms summed over the turn ({steps} decode steps / all prefill calls); (n nodes) ===")
        lines.append(f"{'node type':36s}{'cpu ms':>10s}{'gpu ms':>10s}{'gpu/cpu':>9s}  nodes cpu/gpu")
        for k in keys[:top]:
            c = out.get("cpu", ({}, {}))[0].get((phase, k), 0.0)
            g = out.get("gpu", ({}, {}))[0].get((phase, k), 0.0)
            nc = out.get("cpu", ({}, {}))[1].get((phase, k), 0)
            ng = out.get("gpu", ({}, {}))[1].get((phase, k), 0)
            r = f"{g / c:8.2f}" if c else "     n/a"
            lines.append(f"{k:36s}{c:10.1f}{g:10.1f}{r:>9s}  {nc}/{ng}")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dir")
    ap.add_argument("tag")
    ap.add_argument("--decode-steps", type=int, default=256)
    ap.add_argument("--top", type=int, default=20)
    args = ap.parse_args()
    text = compare(args.dir, args.tag, args.decode_steps, args.top)
    print(text if text else f"no {args.tag}_{{cpu,gpu}}_prof.log under {args.dir}")


if __name__ == "__main__":
    main()
