#!/usr/bin/env python3
"""table-aligned.md with N sessions per backend: every session's first (cold) and measured (cached) process, then per
backend × process the median and spread (max/min − 1) of prefill, decode, TTFT, init, peak memory.

mktable_aligned_n.py <iter-check dir> gpu:<sid>,<sid>,... cpu:<sid>,<sid>,...
Reads ddp-session/<sid>/<backend>-pa3q-35/{metrics.pb.txt,provenance.txt,logcat-process.txt}.
"""
import pathlib, re, sys, statistics
iterdir = pathlib.Path(sys.argv[1]); groups = {}
for a in sys.argv[2:]:
    b, s = a.split(":", 1); groups[b] = [x for x in s.split(",") if x]
LINE = re.compile(r"^\d\d-\d\d \d\d:\d\d:\d\d\.\d+\s+(\d+)\s+(\d+) \w (\S+)\s*: ?(.*)$")
def parse_iterations(text):
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
def first_process(log):
    lines = log.read_text(errors="replace").splitlines(); pids = []
    for l in lines:
        m = LINE.match(l)
        if m and "litert_lm_lib.cc" in m.group(4) and "Choose backend" in m.group(4) and m.group(1) not in pids: pids.append(m.group(1))
    out = {"pids": pids}
    if not pids: return out
    text = "\n".join(m.group(4) for l in lines if (m := LINE.match(l)) and m.group(1) == pids[0])
    for key, pat in (("init", r"Init Total: ([\d.]+) ms"), ("prefill", r"Prefill Speed: ([\d.]+)"), ("decode", r"Decode Speed: ([\d.]+)"),
                     ("ttft", r"Time to first token: ([\d.]+) s"), ("peak", r"Peak private footprint: ([\d.]+)MB")):
        m = re.search(pat, text); out[key] = float(m.group(1)) if m else None
    m = re.search(r"max_tokens: (\d+)", text); out["max_tokens"] = m.group(1) if m else None
    m = re.search(r"number_of_threads: (\d+)", text); out["threads"] = m.group(1) if m else None
    out["errors"] = len([m.group(4) for l in lines if (m := LINE.match(l)) and m.group(1) in pids and m.group(3) == "native" and re.search(r"Failed to|Invalid decode|INTERNAL:|FATAL", m.group(4))])
    return out
def prov(text):
    g = lambda k: (re.search(rf"^{k}: (.+)$", text, re.M) or [None, None])[1]
    exits = re.findall(r"^(warm-up|measured) process: exit (\d+)$", text, re.M); build = g("build")
    return {"date": g("date"), "build": build.split("/")[-2].split(":")[0] if build else None, "args": g("args"), "exits": ", ".join(f"{a} {b}" for a, b in exits),
            "maxtok_arg": (re.search(r"--max_num_tokens=(\d+)", g("args") or "") or [None, None])[1]}
def f(v, nd=1): return "n/a" if v is None else f"{v:.{nd}f}"
data = {b: [] for b in groups}
for b, sids in groups.items():
    for sid in sids:
        root = iterdir / "ddp-session" / sid / f"{b}-pa3q-35"
        data[b].append({"sid": sid, "its": parse_iterations((root / "metrics.pb.txt").read_text()) if (root / "metrics.pb.txt").exists() else [],
                        "first": first_process(root / "logcat-process.txt"), "prov": prov((root / "provenance.txt").read_text())})
print("| backend | session | process | prefill tok/s | decode tok/s | TTFT s | init ms | peak mem MB | device build | date (device clock) |")
print("|---|---|---|---:|---:|---:|---:|---:|---|---|")
for b in ("gpu", "cpu"):
    for d in data.get(b, []):
        fp = d["first"]; p = d["prov"]
        print(f"| {b} | {d['sid']} | first (no caches, cold) | {f(fp.get('prefill'))} | {f(fp.get('decode'), 2)} | {f(fp.get('ttft'), 3)} | {f(fp.get('init'), 0)} | {f(fp.get('peak'))} | {p['build']} | {p['date']} |")
        for it in d["its"]:
            print(f"| {b} | {d['sid']} | measured (caches present) | {f(it['prefill'])} | {f(it['decode'], 2)} | {f(it['ttft'], 3)} | {f(it['init'], 0)} | {f(it['peak'])} | {p['build']} | {p['date']} |")
print()
print("| backend | process | n | prefill median (each) | prefill spread | decode median (each) | decode spread | TTFT median s | init median ms | peak mem median MB |")
print("|---|---|---:|---|---:|---|---:|---:|---:|---:|")
def spread(v): return f"{max(v)/min(v)-1:.1%}" if v and min(v) > 0 else "n/a"
for b in ("gpu", "cpu"):
    for proc, pick in (("first (cold)", lambda d: d["first"]), ("measured (cached)", lambda d: d["its"][0] if d["its"] else {})):
        vals = [pick(d) for d in data.get(b, []) if pick(d).get("prefill") is not None]
        if not vals: continue
        pf = [v["prefill"] for v in vals]; dc = [v["decode"] for v in vals]; tt = [v["ttft"] for v in vals]; ini = [v["init"] for v in vals]; pk = [v["peak"] for v in vals if v.get("peak") is not None]
        print(f"| {b} | {proc} | {len(vals)} | {statistics.median(pf):.1f} ({', '.join(f'{x:.1f}' for x in pf)}) | {spread(pf)} | {statistics.median(dc):.2f} ({', '.join(f'{x:.2f}' for x in dc)}) | {spread(dc)} | {statistics.median(tt):.3f} | {statistics.median(ini):.0f} | {statistics.median(pk):.1f} |")
print()
print("| backend | session | exits | max_num_tokens (args / settings dump) | error lines | threads |")
print("|---|---|---|---|---:|---|")
for b in ("gpu", "cpu"):
    for d in data.get(b, []):
        print(f"| {b} | {d['sid']} | {d['prov']['exits']} | {d['prov']['maxtok_arg']} / {d['first'].get('max_tokens')} | {d['first'].get('errors','n/a')} | {d['first'].get('threads') or '-'} |")
