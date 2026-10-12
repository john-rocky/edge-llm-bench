#!/usr/bin/env python3
"""Per-node-type ladder of a LiteRT-LM --enable_profiling profile across the allocated KV (catalog X2).

  python3 tools/prof_ctx_ladder.py <profiles-dir> [--out <profiles-dir>/ctx-ladder.md]
  python3 tools/prof_ctx_ladder.py --log 1280=<prof.log> --log 4096=<prof.log> [--ctrl 1280=<ctrl.log> …]

A profiles dir is what android/bench/run_profile.py --max-num-tokens writes: <tag>_ctx<N>_<backend>_prof.log,
its control <tag>_ctx<N>_<backend>_ctrl.log, the record <tag>_ctx<N>_<backend>.prof.json and the control's
record under controls-ctx<N>/. One table per (tag, backend), one column per allocation N.

Phase split: the Run Order table lists the nodes in execution order, so the decode subgraph's rows follow the
prefill rows. Its first row is the subgraph's entry node, named like the table's first row ([Builtin]:0) and
called once per recorded decode step: the decode block starts at the entry-named row with the most calls
(prof_table's call-count threshold is the fallback). Steps recorded = the most common call count up to D + 44
in that block (prof_table's rule; the profiler buffer can stop short of D). ms per step of a node type =
sum(avg ms x times called) over its decode rows / steps recorded. The node type is the Run Order string, which
names the XNNPACK kernel and its dtypes. Wall per step = 1000 / the control's decode tok/s (unprofiled).
Clock witness: the GEMV group (Fully Connected) per step should not move with the allocation; when it moves
more than 10 %, read the attention ratios against it, not the absolute ms.
"""
import argparse, glob, json, os, re, sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "scripts" / "profile"))
import prof_cmp, prof_table  # noqa: E401,E402

LOG = re.compile(r"^(?P<tag>.+)_ctx(?P<ctx>\d+)_(?P<backend>cpu|gpu)_prof\.log$")


def decode_block(path, d):
    rows = prof_cmp.parse(path)[0]          # (node type, avg ms, times called, name), execution order
    if not rows:
        return None
    entry = [i for i, r in enumerate(rows) if i and r[3] == rows[0][3]]
    if entry:
        b = max(entry, key=lambda i: rows[i][2])
    else:
        b = next(i for i, r in enumerate(rows) if r[2] >= max(2, round(d * 0.39)))
    dec = rows[b:]
    counts = Counter(r[2] for r in dec if r[2] <= d + 44)
    steps = counts.most_common(1)[0][0] if counts else d
    per = defaultdict(lambda: [0.0, 0, 0])  # ms per step, nodes, calls per step
    for t, avg, called, _n in dec:
        per[t][0] += avg * called / steps; per[t][1] += 1; per[t][2] += called / steps
    mixed = sum(1 for r in rows[:b] if r[2] >= steps) + sum(1 for r in dec if r[2] < steps)
    return {"per": dict(per), "steps": steps, "rows": len(rows), "decode_rows": len(dec), "mixed": mixed,
            "profiled_tps": prof_table.speed(path, "Decode")}


def cpu_caps(text):
    """{policy: (lowest scaling_max_freq, cpuinfo_max_freq)} in MHz from run_cell's sampler lines."""
    order, hw, low = [], {}, {}
    for line in text.split("===ENGINE_OUTPUT===", 1)[0].splitlines():
        p = line.split()
        if p[:1] == ["CPUPOLICY"] and len(p) >= 3 and p[2].isdigit():
            order.append(p[1]); hw[p[1]] = int(p[2])
        elif p[:1] == ["CPUMAX"] and len(p) == len(order) + 1:
            for name, v in zip(order, p[1:]):
                if v.isdigit():
                    low[name] = min(low.get(name, 10 ** 9), int(v))
    mhz = lambda khz: khz // 1000 if khz % 1000 == 0 else round(khz / 1000, 1)  # noqa: E731 (run_cell.mhz)
    return {k: (mhz(low[k]), mhz(hw[k])) for k in order if k in low}


def fmt_caps(caps):
    return ", ".join(f"{k} {lo}/{hi}" + (" capped" if lo < hi else "") for k, (lo, hi) in caps.items()) or "no sampler lines"


def ladder(sizes, d, title):
    """sizes: {ctx: {"prof": path, "ctrl": path or None, "rec": path or None}} -> markdown lines."""
    ctxs = sorted(sizes)
    blocks = {c: decode_block(sizes[c]["prof"], d) for c in ctxs}
    ctxs = [c for c in ctxs if blocks[c]]
    lo, hi = ctxs[0], ctxs[-1]
    types = sorted({t for c in ctxs for t in blocks[c]["per"]},
                   key=lambda t: -(blocks[hi]["per"].get(t, [0])[0] - blocks[lo]["per"].get(t, [0])[0]))
    ms = lambda c, t: blocks[c]["per"].get(t, [0.0])[0]  # noqa: E731
    out = [f"## {title}", "", f"ms per recorded decode step; ratio = each allocation / {lo}; sorted by the growth "
           f"from {lo} to {hi}.", "",
           "| node type (Run Order string) | group | nodes | " + " | ".join(f"ms @ {c}" for c in ctxs) + " | "
           + " | ".join(f"× {c}/{lo}" for c in ctxs[1:]) + f" | Δ ms {lo}→{hi} |",
           "|---|---|---:|" + "---:|" * len(ctxs) + "---:|" * (len(ctxs) - 1) + "---:|"]
    for t in types:
        if max(ms(c, t) for c in ctxs) < 0.005:
            continue
        ratios = [f"{ms(c, t) / ms(lo, t):.2f}" if ms(lo, t) else "—" for c in ctxs[1:]]
        out.append(f"| `{t}` | {prof_table.group(t)} | {blocks[hi]['per'].get(t, [0, 0])[1]} | "
                   + " | ".join(f"{ms(c, t):.3f}" for c in ctxs) + " | " + " | ".join(ratios)
                   + f" | {ms(hi, t) - ms(lo, t):+.3f} |")
    group = {c: defaultdict(float) for c in ctxs}
    for c in ctxs:
        for t, (v, _n, _k) in blocks[c]["per"].items():
            group[c][prof_table.group(t)] += v
    out += ["", "| per step | " + " | ".join(str(c) for c in ctxs) + " |", "|---|" + "---:|" * len(ctxs)]
    for g in prof_table.GROUPS:
        out.append(f"| {g} ms | " + " | ".join(f"{group[c][g]:.2f}" for c in ctxs) + " |")
    out.append("| op sum ms | " + " | ".join(f"{sum(group[c].values()):.2f}" for c in ctxs) + " |")
    out.append("| attn+kv / gemv | " + " | ".join(f"{group[c]['attn+kv'] / group[c]['gemv']:.3f}"
                                                   if group[c]["gemv"] else "—" for c in ctxs) + " |")
    walls = {c: (prof_table.speed(sizes[c]["ctrl"], "Decode") if sizes[c].get("ctrl") else None) for c in ctxs}
    out.append("| wall ms (control) | " + " | ".join(f"{1000 / walls[c]:.2f}" if walls[c] else "—" for c in ctxs) + " |")
    out.append("| control decode tok/s | " + " | ".join(f"{walls[c]:.2f}" if walls[c] else "—" for c in ctxs) + " |")
    out.append("| profiled decode tok/s | " + " | ".join(f"{blocks[c]['profiled_tps']}" for c in ctxs) + " |")
    out.append("| steps recorded / decode rows / mixed | " + " | ".join(
        f"{blocks[c]['steps']} / {blocks[c]['decode_rows']} / {blocks[c]['mixed']}" for c in ctxs) + " |")
    g0, g1 = group[lo]["gemv"], group[hi]["gemv"]
    moved = g0 and abs(g1 / g0 - 1) > 0.10
    out += ["", f"GEMV (clock witness) {g0:.2f} → {g1:.2f} ms/step ({(g1 / g0 - 1) * 100:+.1f} %): "
            + ("moved > 10 % — the clock moved; read attn+kv / gemv, not absolute ms." if moved else "flat (≤ 10 %).")
            if g0 else "GEMV absent."]
    top = next((t for t in types if ms(lo, t) > 0.005), types[0])
    out.append(f"Largest growth {lo}→{hi}: `{top}` {ms(lo, top):.3f} → {ms(hi, top):.3f} ms/step "
               f"(× {ms(hi, top) / ms(lo, top):.2f})." if ms(lo, top) else f"Largest growth: `{top}`.")
    out += ["", "CPU clock ceiling, lowest scaling_max_freq / cpuinfo_max_freq MHz per policy:"]
    for c in ctxs:
        prof_caps = fmt_caps(cpu_caps(Path(sizes[c]["prof"]).read_text(errors="replace")))
        ctrl_caps = fmt_caps(cpu_caps(Path(sizes[c]["ctrl"]).read_text(errors="replace"))) if sizes[c].get("ctrl") else "—"
        flags = ""
        if sizes[c].get("rec") and os.path.exists(sizes[c]["rec"]):
            rec = json.load(open(sizes[c]["rec"]))
            ctl = rec.get("provenance", {}).get("controlRecordPath")
            ctl = os.path.join(os.path.dirname(os.path.dirname(sizes[c]["rec"])), ctl) if ctl else None
            if ctl and os.path.exists(ctl):
                flags = f"; control protocolFlags {json.load(open(ctl)).get('conditions', {}).get('protocolFlags', [])}"
        out.append(f"- {c}: profiled run {prof_caps}; control {ctrl_caps}{flags}")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dir", nargs="?")
    ap.add_argument("--log", action="append", default=[], help="CTX=path of a profiled log")
    ap.add_argument("--ctrl", action="append", default=[], help="CTX=path of its control log")
    ap.add_argument("--decode-steps", type=int, default=256)
    ap.add_argument("--out")
    a = ap.parse_args()
    groups = defaultdict(dict)
    if a.dir:
        for p in sorted(glob.glob(os.path.join(a.dir, "*_prof.log"))):
            m = LOG.match(os.path.basename(p))
            if m:
                stem = p[: -len("_prof.log")]
                groups[f"{m['tag']} ({m['backend']})"][int(m["ctx"])] = {
                    "prof": p, "ctrl": stem + "_ctrl.log" if os.path.exists(stem + "_ctrl.log") else None,
                    "rec": stem.rsplit("_", 1)[0] + f"_{m['backend']}.prof.json"}
    ctrl = dict(x.split("=", 1) for x in a.ctrl)
    for x in a.log:
        c, p = x.split("=", 1)
        groups["explicit logs"][int(c)] = {"prof": p, "ctrl": ctrl.get(c), "rec": None}
    if not groups:
        sys.exit("no <tag>_ctx<N>_<backend>_prof.log and no --log")
    md = ["# Per-op ladder across the allocated KV (LiteRT-LM --enable_profiling)", "",
          "Generated by tools/prof_ctx_ladder.py. A profiled run's rate is never a speed row.", ""]
    for title, sizes in groups.items():
        md += ladder(sizes, a.decode_steps, title) + [""]
    text = "\n".join(md)
    if a.out:
        Path(a.out).write_text(text)
    print(text)


if __name__ == "__main__":
    main()
