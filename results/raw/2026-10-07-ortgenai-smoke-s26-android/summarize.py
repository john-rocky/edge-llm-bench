"""Table of the ORT GenAI Galaxy S26 smoke from the pulled device files (round r2, 2026-10-07).

Reads device/<tag>.engine.txt + device/<tag>.sampler.txt and template_baseline.json next to
this file; prints one markdown row per launch: the engine's own numbers, the sampler's peak
VmHWM / VmRSS, the CPUs the engine was allowed on, the largest socket fd count seen, whether
any policy sat below its hardware maximum during the run, and whether the templated prompt
equals the host baseline.

usage: python summarize.py
"""
import glob
import hashlib
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))


def engine_numbers(text):
    if m := re.search(r"^ORTGENAI (.*)$", text, re.M):
        return dict(kv.split("=", 1) for kv in m.group(1).split())
    out = {}
    if m := re.search(r"prompt tokens: (\d+), tokens to generate: (\d+)", text):
        out["prompt_tokens"], out["gen_tokens"] = m.groups()
    for label, key in [("Prompt processing (time to first token)", "prefill"),
                       ("Token generation", "decode"), ("Token sampling", "sampling")]:
        if m := re.search(re.escape(label) + r":\s*\n\s*avg \(us\):\s*([\d.]+)\s*\n\s*avg \(tokens/s\):\s*([\d.]+)",
                          text):
            out[f"{key}_avg_us"], out[f"{key}_tps"] = m.groups()
    if m := re.search(r"Peak working set size: (\d+) bytes", text):
        out["peak_rss_kb"] = str(int(m.group(1)) // 1024)
    return out


def sampler_numbers(text):
    hwm = [int(x) for x in re.findall(r"VmHWM:(\d+)", text)]
    rss = [int(x) for x in re.findall(r"VmRSS:(\d+)", text)]
    socks = [int(x) for x in re.findall(r"sockets=(\d+)", text)]
    cpus = sorted(set(re.findall(r"Cpus_allowed_list:(\S+)", text)))
    hw = [int(x) for x in re.findall(r"^CPUPOLICY \S+ hw=(\d+)", text, re.M)]
    caps = [[int(v) for v in ln.split()[1:-1]] for ln in re.findall(r"^CPUMAX .*$", text, re.M)]
    capped = any(c < h for row in caps for c, h in zip(row, hw))
    exit_code = re.search(r"EXIT_CODE=(\d+)", text)
    return {"vmhwm_kb": max(hwm, default=None), "vmrss_kb": max(rss, default=None),
            "sockets_max": max(socks, default=None), "ticks": len(socks), "cpus": ",".join(cpus) or "-",
            "capped": capped, "exit": exit_code.group(1) if exit_code else "-"}


def main():
    base = json.load(open(os.path.join(HERE, "template_baseline.json")))
    expected = {os.path.basename(r["prompt_file"]): r for r in base["rows"]}
    print("| launch | exit | prompt_tokens (baseline) | template = baseline | gen_tokens | prefill_ms | ttft_ms "
          "| decode tok/s | stop | peak_rss MiB (ru_maxrss) | VmHWM MiB | CPUs | sockets max (ticks) | cpu capped |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for eng_path in sorted(glob.glob(os.path.join(HERE, "device", "*.engine.txt"))):
        tag = os.path.basename(eng_path)[: -len(".engine.txt")]
        text = open(eng_path, encoding="utf-8", errors="replace").read()
        smp = sampler_numbers(open(os.path.join(HERE, "device", f"{tag}.sampler.txt")).read())
        e = engine_numbers(text)
        prompt = "short-chat.txt" if "short" in tag else "long-context-1024-gen256.txt"
        base_row = expected[prompt]
        same = "-"
        if m := re.search(r"\[PROMPT BEGIN\](.*?)\[PROMPT END\]", text, re.S):
            same = "yes" if hashlib.sha256(m.group(1).encode()).hexdigest() == base_row["templated_sha256"] else "NO"
        decode = e.get("decode_tps", "-")
        prefill = e.get("prefill_ms", "-")
        ttft = e.get("ttft_ms", "-")
        if "prefill_avg_us" in e:  # model_benchmark: averages over its one iteration
            prefill = f"{float(e['prefill_avg_us']) / 1000:.1f}"
            ttft = f"{(float(e['prefill_avg_us']) + float(e['sampling_avg_us'])) / 1000:.1f}"
        peak = e.get("peak_rss_kb")
        print(f"| {tag} | {smp['exit']} | {e.get('prompt_tokens', '-')} ({base_row['prompt_tokens']}) | {same} "
              f"| {e.get('gen_tokens', '-')} | {prefill} | {ttft} | {decode} | {e.get('stop', 'forced (min_length)')} "
              f"| {int(peak) / 1024:.0f} | {smp['vmhwm_kb'] / 1024 if smp['vmhwm_kb'] else 0:.0f} | {smp['cpus']} "
              f"| {smp['sockets_max']} ({smp['ticks']}) | {'yes' if smp['capped'] else 'no'} |"
              if peak else f"| {tag} | {smp['exit']} | no engine numbers |")


if __name__ == "__main__":
    main()
