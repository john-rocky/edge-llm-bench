#!/usr/bin/env python3
"""table-aligned.md for N DDP sessions per backend: per backend × process (first = cold, measured = cached) the median
[min–max] of prefill, decode, TTFT, init, peak memory, with the session ids and device builds; then every session's
rows; then the args / exit / error check.

mktable.py <campaign dir> gpu:<sid>,<sid>,... cpu:<sid>,<sid>,...
Reads ddp-session/<sid>/<backend>-pa3q-35/{metrics.pb.txt,provenance.txt,logcat-process.txt}.
"""
import pathlib, re, sys, statistics
camp = pathlib.Path(sys.argv[1]); groups = {}
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
    m = re.search(r"Choose backend: (\S+)", text); out["backend_line"] = m.group(1) if m else None
    out["errors"] = len([m.group(4) for l in lines if (m := LINE.match(l)) and m.group(1) in pids and m.group(3) == "native" and re.search(r"Failed to|Invalid decode|INTERNAL:|FATAL", m.group(4))])
    return out
def prov(text):
    g = lambda k: (re.search(rf"^{k}: (.+)$", text, re.M) or [None, None])[1]
    exits = re.findall(r"^(warm-up|measured) process: exit (\d+)$", text, re.M); build = g("build")
    bundle = re.search(r"^([0-9a-f]{64})\s+/data/local/tmp/litert-cli/\S+\.litertlm$", text, re.M)
    binary = re.search(r"^([0-9a-f]{64})\s+litert_lm_advanced_main$", text, re.M)
    return {"date": g("date"), "build": build.split("/")[-2].split(":")[0].split("_")[0] if build else None, "args": g("args"), "exits": ", ".join(f"{a} {b}" for a, b in exits),
            "maxtok_arg": (re.search(r"--max_num_tokens=(\d+)", g("args") or "") or [None, None])[1],
            "bundle_sha": bundle.group(1)[:8] if bundle else None, "binary_sha": binary.group(1)[:8] if binary else None}
def f(v, nd=1): return "n/a" if v is None else f"{v:.{nd}f}"
def mmm(v, nd=1): return "n/a" if not v else f"{statistics.median(v):.{nd}f} [{min(v):.{nd}f}–{max(v):.{nd}f}]"
data = {b: [] for b in groups}
for b, sids in groups.items():
    for sid in sids:
        root = camp / "ddp-session" / sid / f"{b}-pa3q-35"
        data[b].append({"sid": sid, "its": parse_iterations((root / "metrics.pb.txt").read_text()) if (root / "metrics.pb.txt").exists() else [],
                        "first": first_process(root / "logcat-process.txt"), "prov": prov((root / "provenance.txt").read_text())})
print("| backend | process | n | prefill tok/s median [min–max] | decode tok/s | TTFT s | init ms | peak mem MB | sessions | device builds |")
print("|---|---|---:|---|---|---|---|---|---|---|")
for b in ("gpu", "cpu"):
    for proc, pick in (("first (cold, no caches)", lambda d: d["first"]), ("measured (cached)", lambda d: d["its"][0] if d["its"] else {})):
        ds = [d for d in data.get(b, []) if pick(d).get("prefill") is not None]
        if not ds: continue
        vals = [pick(d) for d in ds]
        pf = [v["prefill"] for v in vals]; dc = [v["decode"] for v in vals]; tt = [v["ttft"] for v in vals]; ini = [v["init"] for v in vals]; pk = [v["peak"] for v in vals if v.get("peak") is not None]
        print(f"| {b} | {proc} | {len(vals)} | {mmm(pf)} | {mmm(dc, 2)} | {mmm(tt, 3)} | {mmm(ini, 0)} | {mmm(pk)} | {', '.join(d['sid'] for d in ds)} | {', '.join(d['prov']['build'] or '?' for d in ds)} |")
print()
print("| backend | session | process | prefill tok/s | decode tok/s | TTFT s | init ms | peak mem MB | device build | date (device clock) |")
print("|---|---|---|---:|---:|---:|---:|---:|---|---|")
for b in ("gpu", "cpu"):
    for d in data.get(b, []):
        fp = d["first"]; p = d["prov"]
        print(f"| {b} | {d['sid']} | first (cold, no caches) | {f(fp.get('prefill'))} | {f(fp.get('decode'), 2)} | {f(fp.get('ttft'), 3)} | {f(fp.get('init'), 0)} | {f(fp.get('peak'))} | {p['build']} | {p['date']} |")
        for it in d["its"]:
            print(f"| {b} | {d['sid']} | measured (cached) | {f(it['prefill'])} | {f(it['decode'], 2)} | {f(it['ttft'], 3)} | {f(it['init'], 0)} | {f(it['peak'])} | {p['build']} | {p['date']} |")
print()
print("| backend | session | exits | max_num_tokens (args / settings dump) | backend line | error lines | threads | bundle sha256 | binary sha256 |")
print("|---|---|---|---|---|---:|---|---|---|")
for b in ("gpu", "cpu"):
    for d in data.get(b, []):
        p = d["prov"]; fp = d["first"]
        print(f"| {b} | {d['sid']} | {p['exits']} | {p['maxtok_arg']} / {fp.get('max_tokens')} | {fp.get('backend_line') or '-'} | {fp.get('errors','n/a')} | {fp.get('threads') or '-'} | {p['bundle_sha']}… | {p['binary_sha']}… |")
