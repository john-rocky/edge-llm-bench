#!/usr/bin/env python3
"""Summarize tables exported from an Instruments trace (`xcrun xctrace export --xpath ...`).

    xctrace_tables.py gpu <metal-gpu-intervals.xml> [--process NAME]
        GPU occupancy per process and channel from the Metal System Trace
        `metal-gpu-intervals` table: the union of the intervals' [start, start+duration)
        over the process's own window (first to last interval), so overlapping intervals
        never count twice. Occupancy is command-buffer time on the GPU timeline, not
        shader-core utilization.
    xctrace_tables.py cpu <time-profile.xml> [--process NAME] [--top N]
        Self time per leaf symbol and per binary from the Time Profiler `time-profile`
        table (one row per sample, weight in ns), plus the per-thread split.

xctrace writes every value once and then refers back to it by id (`<x ref="12"/>`),
so both readers resolve refs before reading a row.
"""
import argparse
import collections
import sys
import xml.etree.ElementTree as ET


def load_rows(path):
    """Yield each <row> as a list of resolved elements (refs replaced by their targets)."""
    ids = {}
    root = ET.parse(path).getroot()
    for el in root.iter():
        i = el.get("id")
        if i is not None:
            ids[i] = el
    def resolve(el):
        r = el.get("ref")
        return ids[r] if r is not None else el
    schema = root.find(".//schema")
    cols = [c.find("mnemonic").text for c in schema.findall("col")] if schema is not None else []
    for row in root.iter("row"):
        yield cols, [resolve(c) for c in row], resolve


def proc_name(el):
    return (el.get("fmt") or "").rsplit(" (", 1)[0]


def cmd_gpu(args):
    per = collections.defaultdict(lambda: collections.defaultdict(list))  # proc -> channel -> intervals
    for cols, cells, _ in load_rows(args.xml):
        c = dict(zip(cols, cells))
        p = proc_name(c["process"])
        if args.process and p != args.process:
            continue
        start = int(c["start"].text); dur = int(c["duration"].text)
        per[p][c["channel-name"].text or "?"].append((start, start + dur))
    print(f"{'process':28} {'channel':10} {'intervals':>9} {'busy ms':>9} {'window ms':>10} {'occupancy':>9}")
    for p, chans in sorted(per.items(), key=lambda kv: -sum(len(v) for v in kv[1].values())):
        allv = [iv for v in chans.values() for iv in v]
        w0, w1 = min(s for s, _ in allv), max(e for _, e in allv)
        for ch, ivs in sorted(chans.items(), key=lambda kv: -len(kv[1])):
            busy = union_ns(ivs)
            print(f"{p[:28]:28} {ch[:10]:10} {len(ivs):9d} {busy/1e6:9.1f} {(w1-w0)/1e6:10.1f} {busy/(w1-w0):9.1%}")
        if len(chans) > 1:
            busy = union_ns(allv)
            print(f"{p[:28]:28} {'all':10} {len(allv):9d} {busy/1e6:9.1f} {(w1-w0)/1e6:10.1f} {busy/(w1-w0):9.1%}")
        if args.process:
            gaps = sorted(b[0] - a[1] for a, b in zip(sorted(allv), sorted(allv)[1:]) if b[0] > a[1])
            if gaps:
                print(f"gaps between {p} intervals: n={len(gaps)} median {gaps[len(gaps)//2]/1e3:.0f} us, "
                      f"p90 {gaps[int(len(gaps)*0.9)]/1e3:.0f} us, max {gaps[-1]/1e6:.1f} ms")


def union_ns(ivs):
    total, cur_s, cur_e = 0, None, None
    for s, e in sorted(ivs):
        if cur_e is None or s > cur_e:
            if cur_e is not None:
                total += cur_e - cur_s
            cur_s, cur_e = s, e
        else:
            cur_e = max(cur_e, e)
    return total + (cur_e - cur_s if cur_e is not None else 0)


def cmd_cpu(args):
    by_sym = collections.Counter(); by_bin = collections.Counter(); by_thread = collections.Counter()
    total = 0; n = 0
    for cols, cells, resolve in load_rows(args.xml):
        c = dict(zip(cols, cells))
        if args.process and proc_name(c["process"]) != args.process:
            continue
        w = int(c["weight"].text); total += w; n += 1
        frames = [resolve(f) for f in c["stack"] if f.tag == "frame"]
        leaf = frames[0] if frames else None
        if leaf is None:
            by_sym[("?", "?")] += w; by_bin["?"] += w
        else:
            b = leaf.find("binary")
            bname = (resolve(b).get("name") if b is not None else None) or "?"
            by_sym[(leaf.get("name") or "?", bname)] += w; by_bin[bname] += w
        by_thread[c["thread"].get("fmt")] += w
    if not total:
        print("no samples for the selected process"); return
    print(f"samples {n}, weight {total/1e6:.0f} ms")
    print(f"\n{'self%':>6} {'ms':>8}  binary")
    for b, w in by_bin.most_common(args.top):
        print(f"{w/total:6.1%} {w/1e6:8.1f}  {b}")
    print(f"\n{'self%':>6} {'ms':>8}  symbol  [binary]")
    for (s, b), w in by_sym.most_common(args.top):
        print(f"{w/total:6.1%} {w/1e6:8.1f}  {s[:90]}  [{b}]")
    print(f"\n{'self%':>6} {'ms':>8}  thread")
    for t, w in by_thread.most_common(args.top):
        print(f"{w/total:6.1%} {w/1e6:8.1f}  {t}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gpu"); g.add_argument("xml"); g.add_argument("--process"); g.set_defaults(fn=cmd_gpu)
    c = sub.add_parser("cpu"); c.add_argument("xml"); c.add_argument("--process"); c.add_argument("--top", type=int, default=25)
    c.set_defaults(fn=cmd_cpu)
    a = ap.parse_args(); a.fn(a)


if __name__ == "__main__":
    main()
