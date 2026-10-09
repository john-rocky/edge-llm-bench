#!/usr/bin/env python3
"""table-aligned.md for the warm-shape round: per process (first = cold start, measured = cache present) and per cycle
(iteration 1, 2) the median [min–max] over the sessions of prefill, decode, TTFT, init, peak memory; then every
session's rows; then the args / exit / error check. The first process writes no metrics file, so its cycles are read
from its BenchmarkInfo blocks in the logcat; the measured process's cycles come from metrics.pb.txt and are cross-
checked against its logcat blocks (a mismatch is printed to stderr).

mktable.py <campaign dir> <backend> <sid>,<sid>,...
Reads ddp-session/<sid>/<backend>-pa3q-35/{metrics.pb.txt,provenance.txt,logcat-process.txt}.
"""
import pathlib, re, sys, statistics
camp = pathlib.Path(sys.argv[1]); backend = sys.argv[2]; sids = [x for x in sys.argv[3].split(",") if x]
LINE = re.compile(r"^\d\d-\d\d \d\d:\d\d:\d\d\.\d+\s+(\d+)\s+(\d+) \w (\S+)\s*: ?(.*)$")
def parse_metrics(text):
    out = []
    for block in re.split(r"^metrics \{", text, flags=re.M)[1:]:
        it = {}
        m = re.search(r'init_phase_durations_us \{\s*key: "Init Total"\s*value: (\d+)', block); it["init"] = int(m.group(1)) / 1000 if m else None
        for turn, f in (("prefill_turns", "prefill"), ("decode_turns", "decode")):
            m = re.search(turn + r" \{.*?tokens_per_second: ([\d.eE+-]+)", block, re.S); it[f] = float(m.group(1)) if m else None
        m = re.search(r"time_to_first_token_seconds: ([\d.eE+-]+)", block); it["ttft"] = float(m.group(1)) if m else None
        m = re.search(r"peak_mem_mb: ([\d.eE+-]+)", block); it["peak"] = float(m.group(1)) if m else None
        out.append(it)
    return out
def logcat_processes(log):
    """{pid: {"cycles": [per BenchmarkInfo block], "max_tokens", "threads", "backend_line", "errors"}} in pid order."""
    lines = log.read_text(errors="replace").splitlines(); pids = []
    for l in lines:
        m = LINE.match(l)
        if m and "litert_lm_lib.cc" in m.group(4) and "Choose backend" in m.group(4) and m.group(1) not in pids: pids.append(m.group(1))
    procs = {}
    for pid in pids:
        msgs = [m.group(4) for l in lines if (m := LINE.match(l)) and m.group(1) == pid]
        text = "\n".join(msgs)
        blocks = re.split(r"litert_lm_lib\.cc:\d+\] BenchmarkInfo:", text)[1:]
        cycles = []
        for b in blocks:
            it = {}
            for key, pat in (("init", r"Init Total: ([\d.]+) ms"), ("prefill", r"Prefill Speed: ([\d.]+)"), ("decode", r"Decode Speed: ([\d.]+)"),
                             ("ttft", r"Time to first token: ([\d.]+) s"), ("peak", r"Peak private footprint: ([\d.]+)MB")):
                m = re.search(pat, b); it[key] = float(m.group(1)) if m else None
            cycles.append(it)
        p = {"cycles": cycles}
        m = re.search(r"max_tokens: (\d+)", text); p["max_tokens"] = m.group(1) if m else None
        m = re.search(r"number_of_threads: (\d+)", text); p["threads"] = m.group(1) if m else None
        m = re.search(r"Choose backend: (\S+)", text); p["backend_line"] = m.group(1) if m else None
        p["errors"] = len([x for x in msgs if re.search(r"Failed to|Invalid decode|INTERNAL:|FATAL", x)])
        procs[pid] = p
    return procs
def prov(text):
    g = lambda k: (re.search(rf"^{k}: (.+)$", text, re.M) or [None, None])[1]
    exits = re.findall(r"^(warm-up|measured) process: exit (\d+)$", text, re.M); build = g("build")
    bundle = re.search(r"^([0-9a-f]{64})\s+/data/local/tmp/litert-cli/\S+\.litertlm$", text, re.M)
    binary = re.search(r"^([0-9a-f]{64})\s+litert_lm_advanced_main$", text, re.M)
    return {"date": g("date"), "build": build.split("/")[-2].split(":")[0].split("_")[0] if build else None, "args": g("args"), "exits": ", ".join(f"{a} {b}" for a, b in exits),
            "maxtok_arg": (re.search(r"--max_num_tokens=(\d+)", g("args") or "") or [None, None])[1],
            "iters_arg": (re.search(r"--num_iterations=(\d+)", g("args") or "") or [None, None])[1],
            "bundle_sha": bundle.group(1)[:8] if bundle else None, "binary_sha": binary.group(1)[:8] if binary else None}
def f(v, nd=1): return "n/a" if v is None else f"{v:.{nd}f}"
def mmm(v, nd=1): return "n/a" if not v else f"{statistics.median(v):.{nd}f} [{min(v):.{nd}f}–{max(v):.{nd}f}]"
data = []
for sid in sids:
    root = camp / "ddp-session" / sid / f"{backend}-pa3q-35"
    procs = logcat_processes(root / "logcat-process.txt"); pids = list(procs)
    its = parse_metrics((root / "metrics.pb.txt").read_text()) if (root / "metrics.pb.txt").exists() else []
    d = {"sid": sid, "prov": prov((root / "provenance.txt").read_text()), "pids": pids,
         "first": procs[pids[0]] if pids else {"cycles": []}, "measured_log": procs[pids[-1]] if len(pids) > 1 else {"cycles": []}, "measured": its}
    # cross-check metrics vs the measured process's logcat blocks
    for i, (a, b) in enumerate(zip(its, d["measured_log"]["cycles"])):
        for k in ("prefill", "decode"):
            if a[k] is not None and b[k] is not None and abs(a[k] - b[k]) > 0.05 * max(1, abs(b[k])) / 10:
                print(f"{sid} measured cycle {i+1} {k}: metrics {a[k]} vs logcat {b[k]}", file=sys.stderr)
    data.append(d)
rows = [("first (cold start, no caches)", "cycle 1", lambda d: d["first"]["cycles"][0] if len(d["first"]["cycles"]) > 0 else None),
        ("first (cold start, no caches)", "cycle 2 (same process, after cycle 1)", lambda d: d["first"]["cycles"][1] if len(d["first"]["cycles"]) > 1 else None),
        ("measured (caches present)", "cycle 1", lambda d: d["measured"][0] if len(d["measured"]) > 0 else None),
        ("measured (caches present)", "cycle 2 (same process, after cycle 1)", lambda d: d["measured"][1] if len(d["measured"]) > 1 else None)]
print("| backend | process | cycle | n | prefill tok/s median [min–max] | decode tok/s | TTFT s | init ms | peak mem MB | sessions | device builds |")
print("|---|---|---|---:|---|---|---|---|---|---|---|")
for proc, cyc, pick in rows:
    ds = [d for d in data if pick(d) and pick(d).get("prefill") is not None]
    if not ds: continue
    vals = [pick(d) for d in ds]
    pf = [v["prefill"] for v in vals]; dc = [v["decode"] for v in vals]; tt = [v["ttft"] for v in vals if v.get("ttft") is not None]; ini = [v["init"] for v in vals if v.get("init") is not None]; pk = [v["peak"] for v in vals if v.get("peak") is not None]
    print(f"| {backend} | {proc} | {cyc} | {len(vals)} | {mmm(pf)} | {mmm(dc, 2)} | {mmm(tt, 3)} | {mmm(ini, 0)} | {mmm(pk)} | {', '.join(d['sid'] for d in ds)} | {', '.join(d['prov']['build'] or '?' for d in ds)} |")
print()
print("| backend | session | process | cycle | prefill tok/s | decode tok/s | TTFT s | init ms | peak mem MB | device build | date (device clock) |")
print("|---|---|---|---|---:|---:|---:|---:|---:|---|---|")
for d in data:
    p = d["prov"]
    for i, it in enumerate(d["first"]["cycles"]):
        print(f"| {backend} | {d['sid']} | first (cold start, no caches) | {i+1} | {f(it['prefill'])} | {f(it['decode'], 2)} | {f(it['ttft'], 3)} | {f(it['init'], 0)} | {f(it['peak'])} | {p['build']} | {p['date']} |")
    for i, it in enumerate(d["measured"]):
        print(f"| {backend} | {d['sid']} | measured (caches present) | {i+1} | {f(it['prefill'])} | {f(it['decode'], 2)} | {f(it['ttft'], 3)} | {f(it['init'], 0)} | {f(it['peak'])} | {p['build']} | {p['date']} |")
print()
print("| backend | session | exits | --num_iterations (measured args) | BenchmarkInfo blocks first / measured (logcat) | metrics blocks | max_num_tokens (args / settings dump) | backend line | error lines first / measured | threads | bundle sha256 | binary sha256 |")
print("|---|---|---|---|---|---|---|---|---|---|---|---|")
for d in data:
    p = d["prov"]; fp = d["first"]; mp = d["measured_log"]
    print(f"| {backend} | {d['sid']} | {p['exits']} | {p['iters_arg']} | {len(fp['cycles'])} / {len(mp['cycles'])} | {len(d['measured'])} | {p['maxtok_arg']} / {fp.get('max_tokens')} | {fp.get('backend_line') or '-'} | {fp.get('errors','n/a')} / {mp.get('errors','n/a')} | {fp.get('threads') or '-'} | {p['bundle_sha']}… | {p['binary_sha']}… |")
