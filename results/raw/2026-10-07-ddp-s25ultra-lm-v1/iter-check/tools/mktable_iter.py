#!/usr/bin/env python3
"""table-iter.md: Gemma 4 E2B gpu on pa3q-35 at --num-iterations 1, 2 and 5 (the morning session), first and measured process.

mktable_iter.py <iter-check dir> <campaign dir> <sid-iter1> <sid-iter2> <sid-iter5>
Reads ddp-session/<sid>/gpu-pa3q-35/{metrics.pb.txt,provenance.txt,logcat-process.txt} under the given dirs
(the 5-iteration session from the campaign dir) and prints the markdown.
"""
import pathlib
import re
import sys

iterdir, campaign = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
sids = {1: sys.argv[3], 2: sys.argv[4], 5: sys.argv[5]}
JOB = "gpu-pa3q-35"
LINE = re.compile(r"^\d\d-\d\d \d\d:\d\d:\d\d\.\d+\s+(\d+)\s+(\d+) \w (\S+)\s*: ?(.*)$")


def parse_iterations(text):
    out = []
    for block in re.split(r"^metrics \{", text, flags=re.M)[1:]:
        it = {}
        m = re.search(r'init_phase_durations_us \{\s*key: "Init Total"\s*value: (\d+)', block)
        it["init_ms"] = int(m.group(1)) / 1000 if m else None
        for turn, f in (("prefill_turns", "prefill"), ("decode_turns", "decode")):
            m = re.search(turn + r" \{.*?tokens_per_second: ([\d.eE+-]+)", block, re.S)
            it[f] = float(m.group(1)) if m else None
        m = re.search(r"time_to_first_token_seconds: ([\d.eE+-]+)", block)
        it["ttft"] = float(m.group(1)) if m else None
        m = re.search(r"peak_mem_mb: ([\d.eE+-]+)", block)
        it["peak"] = float(m.group(1)) if m else None
        out.append(it)
    return out


def first_process(log):
    lines = log.read_text(errors="replace").splitlines()
    pids = []
    for l in lines:
        m = LINE.match(l)
        if m and "litert_lm_lib.cc" in m.group(4) and "Choose backend" in m.group(4) and m.group(1) not in pids:
            pids.append(m.group(1))
    out = {"pids": pids}
    if not pids:
        return out
    text = "\n".join(m.group(4) for l in lines if (m := LINE.match(l)) and m.group(1) == pids[0])
    for key, pat in (("init_ms", r"Init Total: ([\d.]+) ms"), ("prefill", r"Prefill Speed: ([\d.]+)"),
                     ("decode", r"Decode Speed: ([\d.]+)"), ("ttft", r"Time to first token: ([\d.]+) s"),
                     ("peak", r"Peak private footprint: ([\d.]+)MB")):
        m = re.search(pat, text)
        out[key] = float(m.group(1)) if m else None
    errs = [m.group(4) for l in lines if (m := LINE.match(l)) and m.group(1) in pids and m.group(3) == "native"
            and re.search(r"Failed to|Invalid decode|INTERNAL:|FATAL", m.group(4))]
    out["errors"] = len(errs)
    return out


def prov(text):
    g = lambda k: (re.search(rf"^{k}: (.+)$", text, re.M) or [None, None])[1]
    exits = re.findall(r"^(warm-up|measured) process: exit (\d+)$", text, re.M)
    build = g("build")
    return {"date": g("date"), "build": build.split("/")[-2].split(":")[0] if build else None,
            "args": g("args"), "exits": ", ".join(f"{a} {b}" for a, b in exits)}


def f(v, nd=1):
    return "n/a" if v is None else f"{v:.{nd}f}"


data = {}
for n, sid in sids.items():
    root = (campaign if n == 5 else iterdir) / "ddp-session" / sid / JOB
    data[n] = {"sid": sid, "its": parse_iterations((root / "metrics.pb.txt").read_text()),
               "first": first_process(root / "logcat-process.txt"), "prov": prov((root / "provenance.txt").read_text())}

print("| --num-iterations | process | iteration | prefill tok/s | decode tok/s | TTFT s | init ms | peak mem MB | session | device build | date (device clock) |")
print("|---:|---|---:|---:|---:|---:|---:|---:|---|---|---|")
for n in (1, 2, 5):
    d = data[n]; fp = d["first"]; p = d["prov"]
    print(f"| {n} | first (no caches) | 1 | {f(fp.get('prefill'))} | {f(fp.get('decode'), 2)} | {f(fp.get('ttft'), 3)} | {f(fp.get('init_ms'), 0)} | {f(fp.get('peak'))} | {d['sid']} | {p['build']} | {p['date']} |")
    for i, it in enumerate(d["its"], 1):
        print(f"| {n} | measured (caches present) | {i} | {f(it['prefill'])} | {f(it['decode'], 2)} | {f(it['ttft'], 3)} | {f(it['init_ms'], 0)} | {f(it['peak'])} | {d['sid']} | {p['build']} | {p['date']} |")
print()
print("Process exit codes and the binary's arguments, from each session's provenance.txt:")
print()
print("| --num-iterations | session | exits | args |")
print("|---:|---|---|---|")
for n in (1, 2, 5):
    d = data[n]
    print(f"| {n} | {d['sid']} | {d['prov']['exits']} | `{d['prov']['args']}` |")
print()
for n in (1, 2, 5):
    d = data[n]
    print(f"- {d['sid']} (--num-iterations {n}): metrics.pb holds {len(d['its'])} iteration(s); the log has {len(d['first']['pids'])} process(es) of the binary, "
          f"{d['first'].get('errors', 'n/a')} error line(s) (Failed to / Invalid decode / INTERNAL / FATAL).")
