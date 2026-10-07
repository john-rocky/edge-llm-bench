#!/usr/bin/env python3
"""table-aligned.md rows: Gemma 4 E2B on pa3q-35 at --num-iterations 1 --warmup-runs 0 --max-num-tokens 4096, gpu and cpu,
first (cache-writing, cold) and measured (caches present) process.

mktable_aligned.py <iter-check dir> <gpu sid> <cpu sid>   (a sid may be "none" to skip)
Reads ddp-session/<sid>/<backend>-pa3q-35/{metrics.pb.txt,provenance.txt,logcat-process.txt} and prints the markdown.
"""
import pathlib, re, sys
iterdir = pathlib.Path(sys.argv[1]); sids = {"gpu": sys.argv[2], "cpu": sys.argv[3]}
LINE = re.compile(r"^\d\d-\d\d \d\d:\d\d:\d\d\.\d+\s+(\d+)\s+(\d+) \w (\S+)\s*: ?(.*)$")
def parse_iterations(text):
    out = []
    for block in re.split(r"^metrics \{", text, flags=re.M)[1:]:
        it = {}
        m = re.search(r'init_phase_durations_us \{\s*key: "Init Total"\s*value: (\d+)', block); it["init_ms"] = int(m.group(1)) / 1000 if m else None
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
    for key, pat in (("init_ms", r"Init Total: ([\d.]+) ms"), ("prefill", r"Prefill Speed: ([\d.]+)"), ("decode", r"Decode Speed: ([\d.]+)"),
                     ("ttft", r"Time to first token: ([\d.]+) s"), ("peak", r"Peak private footprint: ([\d.]+)MB")):
        m = re.search(pat, text); out[key] = float(m.group(1)) if m else None
    m = re.search(r"max_tokens: (\d+)", text); out["max_tokens"] = m.group(1) if m else None
    m = re.search(r"number_of_threads: (\d+)", text); out["threads"] = m.group(1) if m else None
    out["accel"] = "GPU OpenCL" if re.search(r"RegisterAccelerator: .*name=GPU OpenCL", text) and "Choose backend: gpu" in text else ("CpuAccelerator (XNNPACK)" if "Choose backend: cpu" in text else "?")
    errs = [m.group(4) for l in lines if (m := LINE.match(l)) and m.group(1) in pids and m.group(3) == "native" and re.search(r"Failed to|Invalid decode|INTERNAL:|FATAL", m.group(4))]
    out["errors"] = len(errs)
    return out
def prov(text):
    g = lambda k: (re.search(rf"^{k}: (.+)$", text, re.M) or [None, None])[1]
    exits = re.findall(r"^(warm-up|measured) process: exit (\d+)$", text, re.M); build = g("build")
    return {"date": g("date"), "build": build.split("/")[-2].split(":")[0] if build else None, "args": g("args"), "exits": ", ".join(f"{a} {b}" for a, b in exits)}
def f(v, nd=1): return "n/a" if v is None else f"{v:.{nd}f}"
data = {}
for b, sid in sids.items():
    if sid == "none": continue
    root = iterdir / "ddp-session" / sid / f"{b}-pa3q-35"
    data[b] = {"sid": sid, "its": parse_iterations((root / "metrics.pb.txt").read_text()) if (root / "metrics.pb.txt").exists() else [],
               "first": first_process(root / "logcat-process.txt"), "prov": prov((root / "provenance.txt").read_text())}
print("| backend | process | prefill tok/s | decode tok/s | TTFT s | init ms | peak mem MB | max_tokens (settings dump) | session | device build | date (device clock) |")
print("|---|---|---:|---:|---:|---:|---:|---:|---|---|---|")
for b in ("gpu", "cpu"):
    if b not in data: continue
    d = data[b]; fp = d["first"]; p = d["prov"]
    print(f"| {b} | first (no caches, cold) | {f(fp.get('prefill'))} | {f(fp.get('decode'), 2)} | {f(fp.get('ttft'), 3)} | {f(fp.get('init_ms'), 0)} | {f(fp.get('peak'))} | {fp.get('max_tokens')} | {d['sid']} | {p['build']} | {p['date']} |")
    for i, it in enumerate(d["its"], 1):
        print(f"| {b} | measured (caches present), cycle {i} | {f(it['prefill'])} | {f(it['decode'], 2)} | {f(it['ttft'], 3)} | {f(it['init_ms'], 0)} | {f(it['peak'])} | {fp.get('max_tokens')} | {d['sid']} | {p['build']} | {p['date']} |")
print(); print("| backend | session | exits | args |"); print("|---|---|---|---|")
for b in ("gpu", "cpu"):
    if b in data: print(f"| {b} | {data[b]['sid']} | {data[b]['prov']['exits']} | `{data[b]['prov']['args']}` |")
print()
for b in ("gpu", "cpu"):
    if b in data:
        d = data[b]; print(f"- {d['sid']} ({b}): metrics.pb holds {len(d['its'])} iteration(s); {len(d['first']['pids'])} process(es) of the binary in the log, {d['first'].get('errors','n/a')} error line(s) (Failed to / Invalid decode / INTERNAL / FATAL); log says {d['first'].get('accel')}" + (f", number_of_threads {d['first'].get('threads')}" if d['first'].get('threads') else "") + ".")
