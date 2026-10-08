"""Tables for the ORT GenAI Galaxy S26 1K prefill diagnosis (round r2b,
2026-10-07): reads device/<tag>.engine.txt and device/<tag>.sampler.txt
(run_diag.sh) and mac/mac_ladder.jsonl, prints markdown, writes summary.json.

(b) ladder: model_benchmark --use_random_tokens -l N (r2b-D2-*, r2b-D1-*): N,
    prompt processing ms, per-token ms, and the CPU cap during the prefill;
    the Mac ladder (mac_ladder.py, same cut points) beside it.
(c) threads / mask: ortgenai_run on the 1K task prompt (r2b-D3..D6): prefill
    ms, per-token ms, TTFT, the intra-op threads asked for, the process's peak
    thread count, where its running threads sat, the cap during the prefill,
    and the battery before and after.

The prefill window on the sampler's clock is estimated: it starts at the
launch + the engine's own load and generator-creation times (model_benchmark:
Model Creation + Tokenizer Creation + Generator Creation latency; ortgenai_run:
load_ms + generator_ms) and lasts the measured prefill. Tokenizer setup, the
chat template and Encode are not in that sum, so the window opens a little
early; the cap figures are a description of the sampler, not a correction of
any number.

usage: python -I summarize_diag.py [<dir>]   (default: the directory of this file)
"""
import json
import os
import re
import sys


def parse_engine(path):
    text = open(path, encoding="utf-8", errors="replace").read()
    out = {}
    m = re.search(r"^ORTGENAI (.*)$", text, re.M)
    if m:
        out["kind"] = "ortgenai_run"
        for kv in m.group(1).split():
            k, _, v = kv.partition("=")
            out[k] = v
        out["prefill_ms"] = float(out["prefill_ms"])
        out["ttft_ms"] = float(out["ttft_ms"])
        out["prompt_tokens"] = int(out["prompt_tokens"])
        out["setup_ms"] = float(out.get("load_ms", 0)) + float(out.get("generator_ms", 0))
        out["peak_mib"] = int(out["peak_rss_kb"]) / 1024
        return out
    m = re.search(r"prompt tokens: (\d+)", text)
    if m:
        out["kind"] = "model_benchmark"
        out["prompt_tokens"] = int(m.group(1))
        pp = re.search(r"Prompt processing \(time to first token\):\s*avg \(us\):\s*([\d.e+]+)", text)
        out["prefill_ms"] = float(pp.group(1)) / 1e3 if pp else None
        tg = re.search(r"Token generation:\s*avg \(us\):\s*([\d.e+]+)\s*avg \(tokens/s\):\s*([\d.e+]+)", text)
        out["decode_tps"] = float(tg.group(2)) if tg else None
        setup = 0.0
        for key in ("Model Creation Latency", "Tokenizer Creation Latency", "Generator Creation Latency"):
            s = re.search(re.escape(key) + r": ([\d.]+) ms", text)
            setup += float(s.group(1)) if s else 0.0
        out["setup_ms"] = setup
        pk = re.search(r"Peak working set size: (\d+) bytes", text)
        out["peak_mib"] = int(pk.group(1)) / 2**20 if pk else None
        out["profiling"] = "Profiling will run" in text
        return out
    out["kind"] = "unparsed"
    out["error"] = (re.search(r"^(Error|Exception).*$", text, re.M) or [None])[0]
    return out


def parse_sampler(path):
    s = {"hw": {}, "caps": [], "ticks": [], "sockets": [], "logcat_lines": None}
    for line in open(path, encoding="utf-8", errors="replace"):
        f = line.split()
        if not f:
            continue
        if f[0] == "CPUPOLICY":
            kv = dict(x.split("=", 1) for x in f[2:] if "=" in x)  # cpus= is a space-separated list
            s["hw"][f[1]] = int(kv["hw"])
            s.setdefault("policies", []).append(f[1])
        elif f[0] in ("START", "END", "LAUNCH"):
            kv = dict(x.split("=", 1) for x in f[1:] if "=" in x)
            s[f[0].lower()] = kv
        elif f[0] == "CPUMAX":
            up = float(f[-1].split("=")[1])
            s["caps"].append((up, [int(x) for x in f[1:-1]]))
        elif f[0] == "TICK":
            t = {"up": float(f[1])}
            for x in f[2:]:
                if x.startswith("Threads:"):
                    t["threads"] = int(x.split(":")[1])
                elif x.startswith("run="):
                    t["run"] = [] if x == "run=-" else [int(c) for c in x[4:].split(",")]
                elif x.startswith("cur="):
                    t["cur"] = [int(c) for c in x[4:].split("/")]
                elif x.startswith("Cpus_allowed_list:"):
                    t["allowed"] = x.split(":", 1)[1]
                elif x.startswith("sockets="):
                    t["sockets"] = int(x.split("=")[1])
            s["ticks"].append(t)
        elif f[0].startswith("SOCKET"):
            s["sockets"].append(line.strip())
        elif f[0].startswith("LOGCAT_LINES="):
            s["logcat_lines"] = int(f[0].split("=")[1])
        elif f[0] == "KILLED":
            s["killed"] = True
    return s


def window_stats(s, start, end):
    """Cap and clock figures for [start, end] on the sampler's uptime clock."""
    pols = s.get("policies", [])
    hw = [s["hw"][p] for p in pols]
    caps = sorted(s["caps"])
    first_capped = next((up for up, c in caps if any(v < h for v, h in zip(c, hw))), None)

    def cap_at(t):
        cur = caps[0][1] if caps else hw
        for up, c in caps:
            if up <= t:
                cur = c
        return cur

    # time-weighted cap ratio per policy over the window, 0.1 s steps
    steps, acc = 0, [0.0] * len(hw)
    t = start
    while t < end:
        c = cap_at(t)
        for i, (v, h) in enumerate(zip(c, hw)):
            acc[i] += v / h
        steps += 1
        t += 0.1
    ratio = [round(a / steps, 3) for a in acc] if steps else None
    inwin = [x for x in s["ticks"] if start <= x["up"] <= end]
    cur_mean = None
    if inwin and all("cur" in x for x in inwin):
        cur_mean = [round(sum(x["cur"][i] for x in inwin) / len(inwin) / 1e6, 3) for i in range(len(hw))]
    placement = {}
    for x in inwin:
        for c in x.get("run", []):
            placement[c] = placement.get(c, 0) + 1
    return {
        "first_cap_s_after_launch": None if first_capped is None else round(first_capped - float(s["launch"]["uptime"]), 1),
        "min_cap_ghz_in_prefill": [round(min([cap_at(start)[i]] + [c[i] for up, c in caps if start <= up <= end]) / 1e6, 4)
                                   for i in range(len(hw))] if hw else None,
        "mean_cap_ratio_in_prefill": ratio,
        "mean_cur_ghz_in_prefill": cur_mean,
        "running_thread_cpu_counts": dict(sorted(placement.items())),
        "ticks_in_prefill": len(inwin),
    }


def runs(root):
    dev = os.path.join(root, "device")
    tags = sorted({f[: -len(".engine.txt")] for f in os.listdir(dev) if f.endswith(".engine.txt")}) if os.path.isdir(dev) else []
    out = []
    for tag in tags:
        e = parse_engine(os.path.join(dev, tag + ".engine.txt"))
        smp = os.path.join(dev, tag + ".sampler.txt")
        s = parse_sampler(smp) if os.path.exists(smp) else None
        r = {"tag": tag, **{k: e.get(k) for k in ("kind", "prompt_tokens", "prefill_ms", "ttft_ms", "decode_tps",
                                                   "threads", "peak_mib", "setup_ms", "error", "profiling")}}
        if e.get("prefill_ms") and s and "launch" in s:
            start = float(s["launch"]["uptime"]) - 0.2 + e["setup_ms"] / 1e3
            r["per_token_ms"] = round(e["prefill_ms"] / e["prompt_tokens"], 3)
            r["prefill_tps"] = round(e["prompt_tokens"] / e["prefill_ms"] * 1e3, 1)
            r.update(window_stats(s, start, start + e["prefill_ms"] / 1e3))
        if s:
            r["max_threads"] = max((x.get("threads", 0) for x in s["ticks"]), default=None)
            r["allowed"] = next((x["allowed"] for x in s["ticks"] if "allowed" in x), None)
            r["battery_start"] = s.get("start", {}).get("battery_temp")
            r["battery_end"] = s.get("end", {}).get("battery_temp")
            r["thermal_start"] = s.get("start", {}).get("thermal")
            r["sockets"] = s["sockets"]
            r["logcat_lines"] = s["logcat_lines"]
            r["killed"] = s.get("killed", False)
        out.append(r)
    return out


def fmt(v, spec=""):
    if v is None:
        return "-"
    return format(v, spec) if spec else str(v)


def main(root):
    rs = runs(root)
    mac = {}
    mpath = os.path.join(root, "mac", "mac_ladder.jsonl")
    if os.path.exists(mpath):
        for line in open(mpath, encoding="utf-8"):
            j = json.loads(line)
            if not j["profiled"]:
                mac[j["n"]] = j
    lines = ["(b) ladder — S26 model_benchmark --use_random_tokens -l N -g 8 -ml 2048 -r 1 -w 0 (1024 = the profiled D1); Mac = mac_ladder.py",
             "",
             "| N | S26 prompt processing ms | S26 per-token ms | S26 tok/s | first cap (s after launch) | mean cap / hw in prefill (policy0, policy6) | mean clock GHz in prefill | battery start / end (0.1 C) | Mac per-token ms |",
             "|---|---|---|---|---|---|---|---|---|"]
    for r in sorted((r for r in rs if r["kind"] == "model_benchmark"), key=lambda r: r["prompt_tokens"] or 0):
        m = mac.get(r["prompt_tokens"])
        lines.append(f"| {r['prompt_tokens']} | {fmt(r['prefill_ms'], '.1f')} | {fmt(r.get('per_token_ms'))} | {fmt(r.get('prefill_tps'))} | "
                     f"{fmt(r.get('first_cap_s_after_launch'))} | {fmt(r.get('mean_cap_ratio_in_prefill'))} | {fmt(r.get('mean_cur_ghz_in_prefill'))} | "
                     f"{fmt(r.get('battery_start'))} / {fmt(r.get('battery_end'))} | {fmt(m['prefill_per_token_ms'] if m else None)} |")
    lines += ["", "(c) threads / mask — S26 ortgenai_run, 1K task prompt, -g 32 -ml 2048",
              "",
              "| run | threads asked | peak process threads | CPUs allowed | prompt tokens | prefill ms | per-token ms | tok/s | first cap (s after launch) | mean cap / hw in prefill | mean clock GHz in prefill | running-thread CPU counts | battery start / end |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in (r for r in rs if r["kind"] == "ortgenai_run"):
        lines.append(f"| {r['tag']} | {fmt(r.get('threads'))} | {fmt(r.get('max_threads'))} | {fmt(r.get('allowed'))} | {r['prompt_tokens']} | "
                     f"{fmt(r['prefill_ms'], '.1f')} | {fmt(r.get('per_token_ms'))} | {fmt(r.get('prefill_tps'))} | {fmt(r.get('first_cap_s_after_launch'))} | "
                     f"{fmt(r.get('mean_cap_ratio_in_prefill'))} | {fmt(r.get('mean_cur_ghz_in_prefill'))} | {fmt(r.get('running_thread_cpu_counts'))} | "
                     f"{fmt(r.get('battery_start'))} / {fmt(r.get('battery_end'))} |")
    other = [r for r in rs if r["kind"] not in ("ortgenai_run", "model_benchmark")]
    for r in other:
        lines.append(f"- {r['tag']}: no result ({r.get('error') or 'unparsed'}; killed={r.get('killed')})")
    socks = next((r["sockets"] for r in rs if r.get("sockets")), [])
    lines += ["", "socket fd (first run that showed one):"] + [f"    {x}" for x in socks]
    print("\n".join(lines))
    with open(os.path.join(root, "summary.json"), "w", encoding="utf-8") as f:
        json.dump({"runs": rs, "mac_ladder": list(mac.values())}, f, indent=1)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__)))
