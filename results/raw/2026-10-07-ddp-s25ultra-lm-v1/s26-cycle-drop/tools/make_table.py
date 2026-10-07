#!/usr/bin/env python3
"""make_table.py <out dir>: table-cycle-drop.md from the per-setting logcat files and thermal.tsv.
One line per (setting, process, cycle): prefill / decode / TTFT / decode turn seconds from the BenchmarkInfo block,
and the thermal log's row nearest the cycle's end (battery, sys-therm-0, max cpu-* zone, max gpuss-* zone, ddr,
GPU MHz, GPU busy %, cpu7 kHz) plus the max GPU-zone temperature and min GPU MHz seen during the cycle."""
import glob, os, re, sys, datetime
out = sys.argv[1]
# thermal log
rows = []
with open(os.path.join(out, "thermal.tsv")) as f:
    hdr = f.readline().rstrip("\n").split("\t")
    for line in f:
        p = line.rstrip("\n").split("\t")
        if len(p) != len(hdr): continue
        try: rows.append(dict(zip(hdr, p)))
        except Exception: pass
cpu_cols = [h for h in hdr if h.startswith("cpu-")]
gpu_cols = [h for h in hdr if h.startswith("gpuss-")]
def num(x):
    try: return float(x)
    except Exception: return float("nan")
for r in rows:
    r["epoch"] = int(r["epoch"])
    r["cpu_max"] = max(num(r[c]) for c in cpu_cols) / 1000
    r["gpu_max"] = max(num(r[c]) for c in gpu_cols) / 1000
def nearest(ep):
    return min(rows, key=lambda r: abs(r["epoch"] - ep)) if rows else None
def between(a, b):
    return [r for r in rows if a <= r["epoch"] <= b]
# the device's date for the logcat year: logcat has MM-DD HH:MM:SS.mmm in device local time; thermal has epoch + HH:MM:SS
# map logcat time to epoch by matching the HH:MM:SS of thermal rows (same device clock)
devtime_to_epoch = {}
for r in rows:
    devtime_to_epoch.setdefault(r["devtime"], r["epoch"])
def lc_epoch(ts):  # "10-07 16:10:12.749" -> epoch via the thermal log's same-second row (or interpolate from the first row)
    hms = ts[6:14]
    if hms in devtime_to_epoch: return devtime_to_epoch[hms]
    if not rows: return None
    base = rows[0]; bh = datetime.datetime.strptime(base["devtime"], "%H:%M:%S"); th = datetime.datetime.strptime(hms, "%H:%M:%S")
    return base["epoch"] + int((th - bh).total_seconds())
order = ["A0", "A", "B1", "B2", "B3", "C"]
lines = ["| setting | process pid | cycle | prefill tok/s | decode tok/s | decode turn s | TTFT s | init ms | peak mem MB | cycle end (device clock) | battery °C | sys-therm-0 °C | cpu max °C | gpu max °C | ddr °C | gpu MHz | gpu busy % | cpu7 MHz | during cycle: gpu max °C / gpu MHz min–max |",
         "|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
summary = {}
for tag in order:
    fn = os.path.join(out, f"{tag}.logcat-process.txt")   # the record: the binary's process lines only
    if not os.path.exists(fn): fn = os.path.join(out, f"{tag}.logcat.txt")   # the scratch run: the whole logcat window
    if not os.path.exists(fn): continue
    txt = open(fn, errors="replace").read().splitlines()
    # the logcat window starts at the second the process was launched and can hold the tail of the previous process:
    # keep only the pid of the last "Choose backend" line (this setting's process)
    pids = [re.match(r"\S+ \S+\s+(\d+)", l).group(1) for l in txt if "Choose backend: gpu" in l]
    want = pids[-1] if pids else None
    cyc = 0; start_ep = None; pid = None
    cur = {}
    for l in txt:
        m = re.match(r"(\d\d-\d\d \d\d:\d\d:\d\d\.\d+)\s+(\d+)\s+\d+ [IWE] native\s*: (.*)", l)
        if not m: continue
        ts, p, msg = m.groups()
        if p != want: continue
        if "Running single-turn conversation" in msg:
            start_ep = lc_epoch(ts); pid = p; cur = {}
        elif "Init Total:" in msg: cur["init"] = re.search(r"([\d.]+) ms", msg).group(1)
        elif "Time to first token:" in msg: cur["ttft"] = re.search(r"([\d.]+) s", msg).group(1)
        elif "Prefill Speed:" in msg: cur["prefill"] = re.search(r"([\d.]+) tokens", msg).group(1)
        elif "Decode Turn 1:" in msg: cur["dsec"] = re.search(r"in ([\d.]+)s", msg).group(1)
        elif "Decode Speed:" in msg:
            cur["decode"] = re.search(r"([\d.]+) tokens", msg).group(1); cur["end_ts"] = ts
        elif "Peak system ram usage:" in msg and "decode" in cur:
            cur["peak"] = re.search(r"([\d.]+)MB", msg).group(1)
            cyc += 1
            ep = lc_epoch(ts); n = nearest(ep) if ep else None
            win = between(start_ep, ep) if (start_ep and ep) else []
            gmax = max((r["gpu_max"] for r in win), default=float("nan"))
            mhz = [num(r["gpu_mhz"]) for r in win]
            during = f"{gmax:.1f} / {min(mhz):.0f}–{max(mhz):.0f}" if mhz else "-"
            def t(k): return f"{num(n[k])/1000:.1f}" if n else "-"
            lines.append(f"| {tag} | {pid} | {cyc} | {cur['prefill']} | {cur['decode']} | {cur['dsec']} | {cur['ttft']} | {cur['init']} | {cur['peak']} | {ts} | {t('battery')} | {t('sys-therm-0')} | {n['cpu_max']:.1f} | {n['gpu_max']:.1f} | {t('ddr')} | {n['gpu_mhz']} | {n['gpu_busy']} | {int(n['cpu7_khz'])//1000} | {during} |" if n else
                         f"| {tag} | {pid} | {cyc} | {cur['prefill']} | {cur['decode']} | {cur['dsec']} | {cur['ttft']} | {cur['init']} | {cur['peak']} | {ts} | - | - | - | - | - | - | - | - | - |")
            summary.setdefault(tag, []).append((cur['prefill'], cur['decode']))
            cur = {}
print("\n".join(lines))
print()
for tag in order:
    if tag in summary:
        print(f"- {tag}: prefill " + ", ".join(p for p, d in summary[tag]) + "; decode " + ", ".join(d for p, d in summary[tag]))
