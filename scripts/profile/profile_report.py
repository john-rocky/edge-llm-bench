#!/usr/bin/env python3
"""Turn a profiles/ directory (control + profiled log pairs) into PROFILE.md and
profile-table.csv, plus a cpu-vs-gpu node-type comparison for every tag that
has both backends.

Pairs are discovered by name: <tag>_<cpu|gpu>_prof.log with its
<tag>_<cpu|gpu>_ctrl.log next to it (what android/bench/run_profile.py writes,
and the layout of results/raw/2026-09-11-catalog-x13-s26-android/profiles/).
A <tag>_<backend>.prof.json record beside the pair supplies the decode-step
count (from its task, native-benchmark-<P>x<D>); otherwise --decode-steps.

  python3 scripts/profile/profile_report.py <profiles-dir> [--out DIR] [--decode-steps 256]
"""
import argparse
import csv
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prof_cmp  # noqa: E402
import prof_table  # noqa: E402

PAIR = re.compile(r"^(?P<tag>.+)_(?P<backend>cpu|gpu)_prof\.log$")


CTRL = re.compile(r"^(?P<tag>.+)_(?P<backend>cpu|gpu)_ctrl\.log$")


def discover(d):
    """[(tag, backend, prof_path_or_None, ctrl_path_or_None)] — orphans of either kind included."""
    seen = {}
    for p in sorted(glob.glob(os.path.join(d, "*_prof.log"))):
        m = PAIR.match(os.path.basename(p))
        if m:
            seen[(m.group("tag"), m.group("backend"))] = [p, None]
    for c in sorted(glob.glob(os.path.join(d, "*_ctrl.log"))):
        m = CTRL.match(os.path.basename(c))
        if m:
            seen.setdefault((m.group("tag"), m.group("backend")), [None, None])[1] = c
    return [(tag, backend, prof, ctrl) for (tag, backend), (prof, ctrl) in sorted(seen.items())]


def decode_steps_of(d, tag, backend, default):
    rec = os.path.join(d, f"{tag}_{backend}.prof.json")
    if os.path.exists(rec):
        task = json.load(open(rec)).get("task", "")
        m = re.match(r"native-benchmark-(\d+)x(\d+)$", task)
        if m:
            return int(m.group(2))
    return default


def reading(backend, r):
    """One factual line per row: what the table says, no recommendation."""
    parts = []
    if r["op_sum_ms"] > 0:
        g = max(("gemv", "attn+kv", "xfer", "other"), key=lambda k: r[k + "_ms"])
        parts.append(f"{g} is {100 * r[g + '_ms'] / r['op_sum_ms']:.0f}% of the profiled op time")
    if r["wall_ms"] is not None and r["unprofiled_ms"] is not None:
        if r["unprofiled_ms"] > 0:
            parts.append(f"{r['unprofiled_ms']:.1f} of the {r['wall_ms']:.1f} ms step is outside the profiled ops")
        else:
            parts.append(f"profiled op time exceeds the {r['wall_ms']:.1f} ms wall by {-r['unprofiled_ms']:.1f} ms "
                         "(profiler cost inside the op times)")
    parts.append(f"{r['launches_per_step']:.0f} launches per step")
    if r["control_decode_tps"] and r["profiled_decode_tps"]:
        parts.append(f"profiled run decoded {r['profiled_decode_tps']:.1f} tok/s against the control's "
                     f"{r['control_decode_tps']:.1f} (the gap is the profiler's own cost; never a speed row)")
    return f"{backend}: " + "; ".join(parts)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dir")
    ap.add_argument("--out", help="where PROFILE.md and profile-table.csv go (default: the dir itself)")
    ap.add_argument("--decode-steps", type=int, default=256)
    args = ap.parse_args()
    d = args.dir
    out = args.out or d
    os.makedirs(out, exist_ok=True)
    pairs = discover(d)
    if not pairs:
        print(f"no <tag>_<cpu|gpu>_prof.log under {d}", file=sys.stderr)
        return 1

    rows = []
    incomplete = []
    for tag, backend, prof, ctrl in pairs:
        if prof is None:
            incomplete.append(f"{tag} {backend}: control log without its profile - not tabulated")
            continue
        if ctrl is None:
            incomplete.append(f"{tag} {backend}: profiled log without its control - not tabulated")
            continue
        steps = decode_steps_of(d, tag, backend, args.decode_steps)
        rec_path = os.path.join(d, f"{tag}_{backend}.prof.json")
        if os.path.exists(rec_path):
            rec = json.load(open(rec_path))
            if rec.get("conditions", {}).get("exitCode", 0) != 0 or not rec.get("metrics", {}).get("decodeTokensPerSecond"):
                incomplete.append(f"{tag} {backend}: profiled run failed (exit {rec.get('conditions', {}).get('exitCode')}) - not tabulated")
                continue
        r = prof_table.table_row(prof, ctrl, steps)
        if not r["nodes"]:
            incomplete.append(f"{tag} {backend}: profiled log has no per-op table (Run Order) - not tabulated")
            continue
        rows.append((tag, backend, steps, r))

    fields = ["tag", "backend", "decode_steps_requested", "steps_recorded", "wall_ms_per_step", "op_sum_ms",
              "gemv_ms", "attn_kv_ms", "xfer_ms", "other_ms", "unprofiled_ms", "launches_per_step",
              "control_decode_tps", "profiled_decode_tps", "profiled_nodes"]
    with open(os.path.join(out, "profile-table.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(fields)
        for tag, backend, steps, r in rows:
            rnd = lambda v: None if v is None else round(v, 2)  # noqa: E731
            w.writerow([tag, backend, steps, r["steps"], rnd(r["wall_ms"]), rnd(r["op_sum_ms"]),
                        rnd(r["gemv_ms"]), rnd(r["attn+kv_ms"]), rnd(r["xfer_ms"]),
                        rnd(r["other_ms"]), rnd(r["unprofiled_ms"]), round(r["launches_per_step"], 1),
                        r["control_decode_tps"], r["profiled_decode_tps"], r["nodes"]])

    md = ["# Per-op profile (LiteRT-LM `--enable_profiling`)", "",
          "Wall ms per decode step from the unprofiled control run; op sums per recorded decode step from the",
          "profiled run, grouped into weight GEMV / attention+KV / transfer / other; \"unprof.\" is the part of",
          "the wall the profiled ops do not cover. A profiled run's rate is never a speed row.", "",
          "```", prof_table.HEADER]
    for tag, backend, _steps, r in rows:
        md.append(prof_table.fmt_row(tag, backend, r))
    md += ["```", "", "## Readings", ""]
    for tag, backend, _steps, r in rows:
        md.append(f"- `{tag}` {reading(backend, r)}")
    if incomplete:
        md += ["", "## Incomplete pairs", ""] + [f"- {x}" for x in incomplete]
    tags_both = sorted({t for t, b, _s, _r in rows} & {t for t, b, _s, _r in rows if b == "gpu"}
                       & {t for t, b, _s, _r in rows if b == "cpu"})
    for tag in tags_both:
        steps = next(s for t, b, s, _r in rows if t == tag)
        text = prof_cmp.compare(d, tag, steps)
        if text:
            md += ["", f"## cpu vs gpu per node type: `{tag}`", "", "```", text.rstrip(), "```"]
    md += ["", "Runtime: https://github.com/google-ai-edge/litert ; engine: https://github.com/google-ai-edge/LiteRT-LM",
           ""]
    with open(os.path.join(out, "PROFILE.md"), "w") as fh:
        fh.write("\n".join(md))
    print(prof_table.HEADER)
    for tag, backend, _steps, r in rows:
        print(prof_table.fmt_row(tag, backend, r))
    print(f"wrote {os.path.join(out, 'PROFILE.md')} and profile-table.csv ({len(rows)} rows"
          f"{', ' + str(len(incomplete)) + ' incomplete' if incomplete else ''})")
    return 1 if incomplete else 0


if __name__ == "__main__":
    sys.exit(main())
