#!/usr/bin/env python3
"""make_table_maxtokens.py <out dir>: round-4 tables from the per-process logs and thermal.tsv.
Table 1: one line per process (setting, rep, max_tokens from the settings dump, prefill / decode / TTFT / init, thermal row
at the cycle's end: battery, sys-therm-0, max gpuss zone, GPU MHz, GPU busy). Table 2: per setting, prefill median and
spread (max/min - 1), decode median, init median."""
import glob, os, re, sys, statistics, datetime
out = sys.argv[1]
rows = []
with open(os.path.join(out, "thermal.tsv")) as f:
    hdr = f.readline().rstrip("\n").split("\t")
    for line in f:
        p = line.rstrip("\n").split("\t")
        if len(p) == len(hdr): rows.append(dict(zip(hdr, p)))
gpu_cols = [h for h in hdr if h.startswith("gpuss-")]
def num(x):
    try: return float(x)
    except Exception: return float("nan")
for r in rows:
    r["epoch"] = int(r["epoch"]); r["gpu_max"] = max(num(r[c]) for c in gpu_cols) / 1000
dev2ep = {}
for r in rows: dev2ep.setdefault(r["devtime"], r["epoch"])
def lc_epoch(ts):
    hms = ts[6:14]
    if hms in dev2ep: return dev2ep[hms]
    b = rows[0]; bh = datetime.datetime.strptime(b["devtime"], "%H:%M:%S"); th = datetime.datetime.strptime(hms, "%H:%M:%S")
    return b["epoch"] + int((th - bh).total_seconds())
def nearest(ep): return min(rows, key=lambda r: abs(r["epoch"] - ep))
order = ["D1", "A1", "B1", "C1", "A2", "B2", "C2", "A3", "B3", "C3", "D2"]
label = {"A": "no --max_num_tokens (engine default)", "B": "--max_num_tokens=1280", "C": "--max_num_tokens=4096", "D": "no --max_num_tokens, cache files removed first (cold)"}
per = {}
t1 = ["| process | setting | max_tokens (settings dump) | caches at start | prefill tok/s | decode tok/s | TTFT s | init ms | peak mem MB | cycle end (device clock) | battery °C | sys-therm-0 °C | gpu max °C | GPU MHz | GPU busy % |",
      "|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|"]
steps = open(os.path.join(out, "steps.log"), errors="replace").read()
for tag in order:
    fn = os.path.join(out, f"{tag}.logcat-process.txt")
    if not os.path.exists(fn): fn = os.path.join(out, f"{tag}.logcat.txt")
    if not os.path.exists(fn): continue
    txt = open(fn, errors="replace").read().splitlines()
    pids = [re.match(r"\S+ \S+\s+(\d+)", l).group(1) for l in txt if "Choose backend: gpu" in l]
    want = pids[-1] if pids else None
    cur = {}
    for l in txt:
        m = re.match(r"(\d\d-\d\d \d\d:\d\d:\d\d\.\d+)\s+(\d+)\s+\d+ [IWE] native\s*: (.*)", l)
        if not m or m.group(2) != want: continue
        ts, _, msg = m.groups()
        if "max_tokens:" in msg: cur["maxtok"] = re.search(r"max_tokens: (\d+)", msg).group(1)
        elif "Init Total:" in msg: cur["init"] = re.search(r"([\d.]+) ms", msg).group(1)
        elif "Time to first token:" in msg: cur["ttft"] = re.search(r"([\d.]+) s", msg).group(1)
        elif "Prefill Speed:" in msg: cur["prefill"] = re.search(r"([\d.]+) tokens", msg).group(1)
        elif "Decode Speed:" in msg: cur["decode"] = re.search(r"([\d.]+) tokens", msg).group(1); cur["end"] = ts
        elif "Peak system ram usage:" in msg and "decode" in cur and "peak" not in cur: cur["peak"] = re.search(r"([\d.]+)MB", msg).group(1)
    if "decode" not in cur: continue
    cb = re.search(r"START %s .*caches_before=(\d+)" % tag, steps); cb = cb.group(1) if cb else "?"
    n = nearest(lc_epoch(cur["end"]))
    t1.append(f"| {tag} | {label[tag[0]]} | {cur.get('maxtok','?')} | {cb} | {cur['prefill']} | {cur['decode']} | {cur['ttft']} | {cur['init']} | {cur.get('peak','?')} | {cur['end']} | {num(n['battery'])/1000:.1f} | {num(n['sys-therm-0'])/1000:.1f} | {n['gpu_max']:.1f} | {n['gpu_mhz']} | {n['gpu_busy']} |")
    per.setdefault(tag[0], []).append(cur)
print("\n".join(t1)); print()
print("| setting | n | prefill tok/s (each) | prefill median | spread (max/min − 1) | decode median | TTFT median s | init median ms |")
print("|---|---:|---|---:|---:|---:|---:|---:|")
for k in ["A", "B", "C", "D"]:
    c = per.get(k, [])
    if not c: continue
    pf = [float(x["prefill"]) for x in c]; dc = [float(x["decode"]) for x in c]; tt = [float(x["ttft"]) for x in c]; ini = [float(x["init"]) for x in c]
    print(f"| {k}: {label[k]} | {len(c)} | {', '.join(x['prefill'] for x in c)} | {statistics.median(pf):.1f} | {max(pf)/min(pf)-1:.1%} | {statistics.median(dc):.2f} | {statistics.median(tt):.2f} | {statistics.median(ini):.0f} |")
