#!/usr/bin/env python3
"""Per-decode-step table from litert_lm_advanced_main --enable_profiling logs.

One row per (tag, backend). The wall time per decode step comes from the
UNPROFILED control run (<tag>_<backend>_ctrl.log: 1000 / "Decode Speed");
the profiled run (<tag>_<backend>_prof.log) supplies the per-op times, summed
per recorded decode step and grouped into weight GEMV / attention+KV /
transfer / other, plus the launches per step. "unprof." is the part of the
wall the profiled ops do not cover (negative when the profiler's own cost
inflates the op times beyond the wall — seen on the CPU).

The profiler buffer can stop short of the requested decode steps (the CPU
runs of 2026-09-11 recorded 131-256 of 256), so sums are normalised by the
number of steps actually recorded: the most common "times called" among the
decode-phase rows. Per-layer-body nodes are called layers*steps and
normalise the same way.

  python3 scripts/profile/prof_table.py <dir> <tag>... [--decode-steps 256]
"""
import argparse
import collections
import re
from pathlib import Path

TAIL = re.compile(r"^(.*?)\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)%\s+([0-9.]+)%\s+"
                  r"([0-9.]+)\s+(\d+)\s+(\[.*)$")
GROUPS = ("gemv", "attn+kv", "xfer", "other")


def rows_of(path):
    """[(node type, avg ms, times called)] from the Run Order table of a profiled log."""
    text = Path(path).read_text(errors="replace").splitlines()
    try:
        i = next(k for k, l in enumerate(text) if "Run Order" in l)
    except StopIteration:
        return []
    out = []
    for l in text[i + 2:]:
        if l.strip().startswith("=====") and out:
            break
        m = TAIL.match(l)
        if m:
            out.append((m.group(1).strip(), float(m.group(4)), int(m.group(8))))
    return out


def speed(path, kind):
    m = re.search(kind + r" Speed: ([0-9.]+) tokens/sec", Path(path).read_text(errors="replace"))
    return float(m.group(1)) if m else None


def group(node_type):
    s = node_type.lower()
    if "fully connected" in s or "fc1x1" in s or "fully_connected" in s or "convolution" in s:
        return "gemv"
    if any(k in s for k in ("batch matrix", "batched_mat_mul", "softmax", "slice",
                            "add_values_to_cache", "dynamic_update", "concat")):
        return "attn+kv"
    if "upload" in s or "download" in s:
        return "xfer"
    return "other"


def table_row(prof, ctrl, decode_steps=256):
    """dict for one (prof, ctrl) pair, or None when a file is missing."""
    prof, ctrl = Path(prof), Path(ctrl)
    if not prof.exists() or not ctrl.exists():
        return None
    rows = rows_of(prof)
    # decode-phase rows: called at least ~0.39*D times (100 at D=256, the threshold the
    # 2026-09-11 table used); the recorded-step count is the most common call count up to
    # D+44 (300 at 256) — per-layer-body nodes are called layers*steps and sit above it
    min_calls = max(2, round(decode_steps * 0.39))
    dec = [r for r in rows if r[2] >= min_calls]
    counts = collections.Counter(r[2] for r in dec if r[2] <= decode_steps + 44)
    steps = counts.most_common(1)[0][0] if counts else decode_steps
    sums = {g: 0.0 for g in GROUPS}
    launches = 0.0
    for name, avg, called in dec:
        sums[group(name)] += avg * called / steps
        launches += called / steps
    dspeed = speed(ctrl, "Decode")
    wall = 1000 / dspeed if dspeed else None
    total = sum(sums.values())
    return {"wall_ms": wall, "steps": steps, "op_sum_ms": total, **{g + "_ms": sums[g] for g in GROUPS},
            "unprofiled_ms": (wall - total) if wall is not None else None,
            "launches_per_step": launches, "control_decode_tps": dspeed,
            "profiled_decode_tps": speed(prof, "Decode"), "nodes": len(rows)}


TAG_W = 60
HEADER = (f"{'tag':{TAG_W}s} {'be':4s}{'wall':>7s}{'steps':>6s}{'op-sum':>7s}{'gemv':>7s}"
          f"{'attn+kv':>8s}{'xfer':>6s}{'other':>7s}{'unprof.':>8s}{'launch/step':>12s}")


def fmt_row(tag, backend, r):
    w = f"{r['wall_ms']:7.1f}" if r["wall_ms"] is not None else f"{'n/a':>7s}"
    u = f"{r['unprofiled_ms']:8.1f}" if r["unprofiled_ms"] is not None else f"{'n/a':>8s}"
    shown = tag if len(tag) <= TAG_W else "…" + tag[-(TAG_W - 1):]  # keep the PxD / ctx suffix
    return (f"{shown:{TAG_W}s} {backend:4s}{w}{r['steps']:6d}{r['op_sum_ms']:7.1f}{r['gemv_ms']:7.1f}"
            f"{r['attn+kv_ms']:8.1f}{r['xfer_ms']:6.1f}{r['other_ms']:7.1f}{u}"
            f"{r['launches_per_step']:12.0f}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dir")
    ap.add_argument("tags", nargs="+")
    ap.add_argument("--decode-steps", type=int, default=256)
    args = ap.parse_args()
    d = Path(args.dir)
    print(HEADER)
    for tag in args.tags:
        for b in ("cpu", "gpu"):
            r = table_row(d / f"{tag}_{b}_prof.log", d / f"{tag}_{b}_ctrl.log", args.decode_steps)
            if r:
                print(fmt_row(tag, b, r))


if __name__ == "__main__":
    main()
