"""Tables for ORT GenAI round r8-33202 on the Galaxy S26 (2026-10-09):
microsoft/onnxruntime PR #33202 re-measured, the release libonnxruntime.so
(Maven onnxruntime-android 1.30.0, "old") against v1.30.0 + the PR ("new"),
each with the GroupQueryAttention flash path on (default) and off
(ORT_GQA_DISABLE_FLASH_ATTENTION=1).

Reads device/r8-*.engine.txt and device/r8-*.sampler.txt (run_r8.sh), the
1024-token prefill profiles in device/r8-A*-mb1024p-*.d/, and r2b's
graph_nodes.json; prints markdown and writes summary.json next to this file.
r2b's parsers (../2026-10-07-ortgenai-diag-s26-android/summarize_diag.py,
profile_summary.py) do the engine / sampler / profile reading; this file adds
the decode figures, the decode-window cap figures and the identity of each
launch (the ONNX Runtime library it mapped, its Build Info line, the flash
variable in its environment).

Block A (model_benchmark --use_random_tokens -g 8 -ml 2048 -r 1 -w 0 -v -e cpu,
-l 512 and -l 1024 --profile_prefill): prompt processing ms, ms per prompt
token, the 7 generated-token steps (avg and p50 us), the GroupQueryAttention
kernel total of the 1024 profile, and the CPU cap during the prefill and the
decode steps. Block B (ortgenai_run, the 1K task prompt, budget 256): prefill
ms, TTFT, decode tok/s, stop, and the same cap figures.

The windows on the sampler's clock are estimates (summarize_diag.py's): the
prefill starts at the launch + the engine's own load and generator-creation
times and lasts the measured prefill; the decode window follows it (model_benchmark:
7 x the average step; ortgenai_run: from the TTFT on, decode_ms_total long).

usage: python3 -I summarize_r8.py [<dir>]   (default: the directory of this file)
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
R2B = os.path.join(HERE, "..", "2026-10-07-ortgenai-diag-s26-android")
sys.path.insert(0, R2B)
import profile_summary  # noqa: E402
import summarize_diag  # noqa: E402

TAG = re.compile(r"^r8-(?P<id>[AB]\d)-(?P<shape>[a-z0-9]+)-(?P<lib>old|new)-(?P<flash>on|off)$")


def engine_extra(path):
    text = open(path, encoding="utf-8", errors="replace").read()
    out = {}
    tg = re.search(r"Token generation:\s*avg \(us\):\s*([\d.e+]+)\s*avg \(tokens/s\):\s*([\d.e+]+)\s*p50 \(us\):\s*([\d.e+]+)"
                   r"\s*stddev \(us\):\s*([\d.e+]+)\s*n:\s*(\d+)", text)
    if tg:
        out.update(step_avg_us=float(tg.group(1)), step_tps=float(tg.group(2)), step_p50_us=float(tg.group(3)),
                   step_sd_us=float(tg.group(4)), steps=int(tg.group(5)))
    m = re.search(r"^ORTGENAI (.*)$", text, re.M)
    if m:
        kv = dict(x.split("=", 1) for x in m.group(1).split() if "=" in x)
        for k in ("gen_tokens", "seq_tokens", "last_token"):
            out[k] = int(kv[k]) if k in kv else None
        for k in ("decode_ms_total", "load_ms", "generator_ms"):
            out[k] = float(kv[k]) if k in kv else None
        out["decode_tps"] = float(kv["decode_tps"]) if kv.get("decode_tps", "-") != "-" else None
        out["stop"] = kv.get("stop")
        out["ort_version"] = kv.get("ort_version")
    libs = re.search(r"^ORTGENAI_LIBS (.*)$", text, re.M)
    out["ortgenai_libs"] = libs.group(1).split() if libs else None
    o = re.search(r"\[OUTPUT BEGIN\](.*?)\[OUTPUT END\]", text, re.S)
    out["output_chars"] = len(o.group(1)) if o else None
    out["output_head"] = o.group(1)[:120] if o else None
    out["errors"] = re.findall(r"^(?:Error|Exception).*$", text, re.M)
    return out


def sampler_extra(path):
    out = {"ortlib": [], "env": {}, "build_info": None, "dlopen": None, "exit_code": None}
    for line in open(path, encoding="utf-8", errors="replace"):
        if line.startswith("ORTLIB "):
            out["ortlib"].append(line.split(None, 1)[1].strip())
        elif line.startswith("ENV "):
            k, _, v = line[4:].strip().partition("=")
            out["env"][k] = v
        elif "git-commit-id=" in line and out["build_info"] is None:
            out["build_info"] = line.split("ORT Build Info: ", 1)[-1].strip()
        elif "Attempting to dlopen" in line and out["dlopen"] is None:
            out["dlopen"] = line.split("Attempting to dlopen ", 1)[-1].strip()
        elif line.startswith("EXIT_CODE="):
            out["exit_code"] = int(line.split()[0].split("=")[1])
    return out


def window(s, start, end):
    """summarize_diag.window_stats over [start, end], its keys without the "_in_prefill" suffix (also the decode window)."""
    return {k.replace("_in_prefill", ""): v for k, v in summarize_diag.window_stats(s, start, end).items()}


def capped_any(s):
    pols = s.get("policies", [])
    hw = [s["hw"][p] for p in pols]
    return any(any(v < h for v, h in zip(c, hw)) for _, c in s["caps"])


def runs(root):
    dev = os.path.join(root, "device")
    graph = os.path.join(R2B, "graph_nodes.json")
    out = []
    for f in sorted(os.listdir(dev)):
        if not f.endswith(".engine.txt"):
            continue
        tag = f[: -len(".engine.txt")]
        m = TAG.match(tag)
        if not m:
            continue
        e = summarize_diag.parse_engine(os.path.join(dev, f))
        smp_path = os.path.join(dev, tag + ".sampler.txt")
        s = summarize_diag.parse_sampler(smp_path)
        x = engine_extra(os.path.join(dev, f))
        w = sampler_extra(smp_path)
        r = {"tag": tag, **m.groupdict(), "kind": e.get("kind"), "prompt_tokens": e.get("prompt_tokens"),
             "prefill_ms": e.get("prefill_ms"), "ttft_ms": e.get("ttft_ms"), "peak_mib": e.get("peak_mib"),
             "setup_ms": e.get("setup_ms"), **x, **w}
        r["flash_env"] = w["env"].get("ORT_GQA_DISABLE_FLASH_ATTENTION", "unset")
        r["ort_mapped"] = [p for p in w["ortlib"] if p.endswith("/libonnxruntime.so")]
        if e.get("prefill_ms") and "launch" in s:
            launch = float(s["launch"]["uptime"])
            p0 = launch - 0.2 + e["setup_ms"] / 1e3
            p1 = p0 + e["prefill_ms"] / 1e3
            r["per_token_ms"] = round(e["prefill_ms"] / e["prompt_tokens"], 3)
            r["prefill_tps"] = round(e["prompt_tokens"] / e["prefill_ms"] * 1e3, 1)
            r["prefill_window"] = window(s, p0, p1)
            if e.get("kind") == "model_benchmark" and x.get("step_avg_us"):
                d0 = p1
                d1 = d0 + x["steps"] * x["step_avg_us"] / 1e6
            elif e.get("kind") == "ortgenai_run" and x.get("decode_ms_total"):
                d0 = p0 + e["ttft_ms"] / 1e3
                d1 = d0 + x["decode_ms_total"] / 1e3
            else:
                d0 = d1 = None
            if d0 is not None and d1 > d0:
                r["decode_window"] = window(s, d0, d1)
        r["capped"] = capped_any(s)
        r["battery_start"] = s.get("start", {}).get("battery_temp")
        r["battery_end"] = s.get("end", {}).get("battery_temp")
        r["thermal_start"] = s.get("start", {}).get("thermal")
        r["thermal_end"] = s.get("end", {}).get("thermal")
        r["max_threads"] = max((t.get("threads", 0) for t in s["ticks"]), default=None)
        r["sockets"] = s["sockets"]
        r["killed"] = s.get("killed", False)
        prof_dir = os.path.join(dev, tag + ".d")
        profs = sorted(p for p in os.listdir(prof_dir) if p.endswith(".json")) if os.path.isdir(prof_dir) else []
        if profs:
            ps = profile_summary.summarize(os.path.join(prof_dir, profs[0]), graph, tag)
            r["profile"] = {"file": profs[0], "node_kernel_ms": ps["node_kernel_ms"], "model_run_ms": ps["model_run_ms"],
                            "providers": ps["providers"], "kinds": ps["kinds"]}
            gqa = next((k for k in ps["kinds"] if k["kind"] == "GroupQueryAttention"), None)
            r["gqa_ms"] = gqa["ms"] if gqa else None
            r["gqa_nodes"] = gqa["count"] if gqa else None
            r["gqa_share"] = gqa["share"] if gqa else None
        out.append(r)
    return out


def fmt(v, spec=""):
    if v is None:
        return "-"
    return format(v, spec) if spec else str(v)


def cap_text(r, key):
    wdw = r.get(key)
    if not wdw:
        return "-"
    return f"{fmt(wdw.get('mean_cap_ratio'))} (min {fmt(wdw.get('min_cap_ghz'))} GHz)"


def identity_ok(r):
    want_dir = "/ortgenai/" if r["lib"] == "old" else "/ortgenai-33202/"
    want_commit = "git-commit-id=f2c39fe" if r["lib"] == "old" else "git-commit-id=ed0c6ba469"
    want_flash = "1" if r["flash"] == "off" else "unset"
    ok = (len(r["ort_mapped"]) == 1 and want_dir in r["ort_mapped"][0] and want_commit in (r["build_info"] or "")
          and r["flash_env"] == want_flash and r["exit_code"] == 0 and not r["killed"])
    return "yes" if ok else "NO"


def main(root):
    rs = runs(root)
    a = [r for r in rs if r["id"].startswith("A")]
    b = [r for r in rs if r["id"].startswith("B") and r["kind"] == "ortgenai_run" and "dl" not in r["shape"]]
    lines = ["Block A: model_benchmark --use_random_tokens -g 8 -ml 2048 -r 1 -w 0 -v -e cpu (1024 = --profile_prefill), one launch each, in launch order",
             "",
             "| launch | prompt | lib | flash | prompt processing ms | ms / token | tok/s | GQA kernels ms (share) | step avg / p50 us (7 steps) | step tok/s | first cap s | cap / hw in prefill (policy0, policy6) | cap / hw in steps | battery start / end | peak MiB | identity |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in a:
        gqa = f"{fmt(r.get('gqa_ms'), '.1f')} ({fmt(round(r['gqa_share'] * 100, 1) if r.get('gqa_share') is not None else None)} %)" if r.get("gqa_ms") is not None else "-"
        lines.append(f"| {r['id']} | {fmt(r['prompt_tokens'])} | {r['lib']} | {r['flash']} | {fmt(r['prefill_ms'], '.1f')} | {fmt(r.get('per_token_ms'))} | "
                     f"{fmt(r.get('prefill_tps'))} | {gqa} | {fmt(r.get('step_avg_us'), '.0f')} / {fmt(r.get('step_p50_us'), '.0f')} | {fmt(r.get('step_tps'), '.1f')} | "
                     f"{fmt((r.get('prefill_window') or {}).get('first_cap_s_after_launch'))} | {cap_text(r, 'prefill_window')} | {cap_text(r, 'decode_window')} | "
                     f"{fmt(r['battery_start'])} / {fmt(r['battery_end'])} | {fmt(r.get('peak_mib'), '.1f')} | {identity_ok(r)} |")
    lines += ["", "Block B: ortgenai_run, 1K task prompt (long-context-1024-gen256, chat template), -g 256 -ml 2048, one launch each, in launch order",
              "",
              "| launch | lib | flash | prompt tokens | prefill ms | TTFT ms | decode tok/s | gen tokens | stop | first cap s | cap / hw in prefill | cap / hw in decode | battery start / end | peak MiB | identity |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in b:
        lines.append(f"| {r['id']} | {r['lib']} | {r['flash']} | {fmt(r['prompt_tokens'])} | {fmt(r['prefill_ms'], '.1f')} | {fmt(r['ttft_ms'], '.1f')} | "
                     f"{fmt(r.get('decode_tps'), '.2f')} | {fmt(r.get('gen_tokens'))} | {fmt(r.get('stop'))} | "
                     f"{fmt((r.get('prefill_window') or {}).get('first_cap_s_after_launch'))} | {cap_text(r, 'prefill_window')} | {cap_text(r, 'decode_window')} | "
                     f"{fmt(r['battery_start'])} / {fmt(r['battery_end'])} | {fmt(r.get('peak_mib'), '.1f')} | {identity_ok(r)} |")
    lines += ["", "identity = exactly one libonnxruntime.so mapped, from the expected dir; logcat Build Info git-commit-id f2c39fe (old) / ed0c6ba469 (new);",
              "ORT_GQA_DISABLE_FLASH_ATTENTION=1 in the engine's environ exactly for flash off; exit 0, not killed.",
              "", "every launch: " + "; ".join(f"{r['id']} exit {r['exit_code']} libs {r['ortlib']} build {r['build_info']}" for r in rs)]
    print("\n".join(lines))
    with open(os.path.join(root, "summary.json"), "w", encoding="utf-8") as f:
        json.dump({"runs": rs}, f, indent=1)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else HERE)
