#!/usr/bin/env python3
"""r18_table.py CAMPAIGN [CAMPAIGN...] - round r18's table: the current Qwen3 0.6B dynamic INT4 file beside the
candidate, per device x backend x task, from the main checkout's results/summary/device-runs.csv (the runner rebuilds
it after every sitting) through render_leaderboard.arm_row (the one aggregation; no second one here).

CAMPAIGN = a campaign dir name under results/raw (e.g. 2026-10-19-dashboard-v1-m4max-q06cand-mac). The headline regime
is warm on the Mac and the iPhone, cold on Android (every Android run is a fresh process). Per pair: decode and prefill
of the candidate against the current file in the same sitting; "not slower" = both within -3 %; the text check counts
come from the rows (text_check). Prints a markdown table.
"""
import csv
import glob
import os
import re
import sys

MAIN = os.path.expanduser("~/code/edge-llm-bench")
sys.path.insert(0, os.path.join(MAIN, "scripts"))
from render_leaderboard import arm_row  # noqa: E402

CAND = "litert-community/Qwen3-0.6B/dynamic_wi4b32_afp32_r0805meta018"
CUR_APPLE = "litert-community/Qwen3-0.6B/dynamic_wi4b32_afp32"
CUR_ANDROID = ("litert-community/Qwen3-0.6B", "litert-community_Qwen3-0.6B_Qwen3-0.6B_dynamic_wi4b32_afp32.litertlm")


def which(r):
    if r["model_id"] == CAND:
        return "candidate"
    if r["model_id"] == CUR_APPLE or (r["model_id"], r["model_file"]) == CUR_ANDROID:
        return "current"
    return None


def fmt(v, nd=1):
    return "—" if v is None else f"{v:,.{nd}f}"


NATIVE_RE = re.compile(r"(\w+)=(\S+)")


def mac_native_rows(campaign, rows):
    """The Mac runner keeps a native-benchmark cell as YARDSTICK_NATIVE_OK lines in the cell's .jsonl (no
    schema-v1 record, so no summary row): one row per line, in the summary's string form, for arm_row. Device
    and engine come from the campaign's other LiteRT-LM rows; run 1 of a launch is cold (cold=1)."""
    ref = next((r for r in rows if r["campaign"] == f"results/raw/{campaign}" and r["runtime"] == "litert-lm"), None)
    if any(r["campaign"] == f"results/raw/{campaign}" and r["task"].startswith("native-benchmark-") for r in rows):
        return []   # the summary holds the imported records (app-path-native/) already
    out = []
    for f in sorted(glob.glob(os.path.join(MAIN, "results", "raw", campaign, "litert-lm_*native-benchmark-*.jsonl"))):
        name = os.path.basename(f)
        mid = CAND if "r0805meta018" in name else CUR_APPLE
        task = re.search(r"(native-benchmark-\d+x\d+)", name).group(1)
        for line in open(f):
            if not line.startswith("YARDSTICK_NATIVE_OK"):
                continue
            kv = dict(NATIVE_RE.findall(line))
            out.append({"campaign": f"results/raw/{campaign}", "platform": "mac", "device": ref["device"] if ref else "?",
                        "runtime": "litert-lm", "model_id": mid, "model_file": "", "task": task,
                        "context_tokens": kv.get("context_tokens", ""), "timestamp": ref["timestamp"] if ref else "",
                        "engine_version": ref["engine_version"] if ref else "", "quantization": "",
                        "decode_tps": kv.get("decode_tok_s", ""), "prefill_tps": kv.get("prefill_tok_s", ""),
                        "ttft_ms": kv.get("ttft_ms", ""), "prompt_tokens": kv.get("prefill_tokens", ""),
                        "cold_run": "True" if kv.get("cold") == "1" else "False", "first_ever": "",
                        "mem_footprint_median_mb": "", "mem_resident_median_mb": "", "mem_footprint_peak_mb": "",
                        "mem_resident_peak_mb": "", "text_check": "", "cpu_capped": "", "backend_registered": "",
                        "thermal_initial": kv.get("thermal_initial", "")})
    return out


def main(campaigns):
    want = {f"results/raw/{c}" for c in campaigns}
    rows = [r for r in csv.DictReader(open(os.path.join(MAIN, "results", "summary", "device-runs.csv")))
            if r["campaign"] in want]
    screens = {}   # (runtime, model id, task) -> the Mac / iPhone dir's text screen verdict (session_check)
    for c in campaigns:
        if c.endswith("-mac"):
            rows += mac_native_rows(c, rows)
        p = os.path.join(MAIN, "results", "raw", c, "text_screen.json")
        if os.path.exists(p):
            import json
            for k, v in json.load(open(p))["cells"].items():
                rt, mid, task = k.split(" (")[0].split(" ")[:3]
                screens[(rt, mid, task)] = f"screen {v['verdict']} {v['detail'].split(' replies')[0]}"
    cells = {}
    for r in rows:
        w = which(r)
        if not w:
            continue
        key = (r["device"], r["runtime"], r["task"], r["context_tokens"] or "")
        cells.setdefault(key, {}).setdefault(w, []).append(r)
    # prefill: arm_row's (every run of the pool, cold included = the page's figure) and, on the warm platforms, arm_row
    # over the warm rows only (the owner's rule reads warm decode and warm prefill); Android runs are all cold
    print("| device | arm | task | file | regime | decode tok/s (n, spread %) | prefill tok/s, all runs | prefill tok/s, rule's regime | peak MB | prompt tok | text check | Δ decode | Δ prefill (rule) | Δ prefill (all runs) | reading |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for key in sorted(cells):
        dev, arm, task, ctx = key
        pair = cells[key]
        android = all(r["platform"] == "android" for rs in pair.values() for r in rs)
        regime = "cold" if android else "warm"
        got = {}
        for w in ("current", "candidate"):
            if w not in pair:
                continue
            a = arm_row(pair[w])
            dec = a["cold_median"] if android else a["warm"]
            n = a["cold_n"] if android else a["warm_n"]
            spread = a["cold_spread"] if android else a["spread"]
            warm_rows = [r for r in pair[w] if r["cold_run"] == "False"]
            pre_rule = a["prefill"] if android else (arm_row(warm_rows)["prefill"] if warm_rows else None)
            prompts = sorted({r["prompt_tokens"] for r in pair[w] if r["prompt_tokens"]})
            checked = sum(1 for r in pair[w] if r.get("text_check") and r.get("first_ever") != "True")
            text = (f"FAIL {a['text_fail_n']} ({a['text_fail_flags']})" if a["text_fail_n"]
                    else (f"PASS {checked}" if checked
                          else screens.get((arm, pair[w][0]["model_id"], task), "not checked")))
            got[w] = (dec, pre_rule, a["prefill"])
            delta_d = delta_p = delta_pa = reading = ""
            if w == "candidate" and "current" in got and got["current"][0] and dec:
                dd = (dec / got["current"][0] - 1) * 100
                delta_d = f"{dd:+.1f} %"
                dp = None
                if got["current"][1] and pre_rule:
                    dp = (pre_rule / got["current"][1] - 1) * 100
                    delta_p = f"{dp:+.1f} %"
                if got["current"][2] and a["prefill"]:
                    delta_pa = f"{(a['prefill'] / got['current'][2] - 1) * 100:+.1f} %"
                reading = "not slower" if dd >= -3 and (dp is None or dp >= -3) else "slower"
            elif w == "candidate" and dec and ("current" not in got or not got["current"][0]):
                reading = "current file has no number"
            print(f"| {dev} | {arm} | {task}{' ctx ' + ctx if ctx else ''} | {w} | {regime} | {fmt(dec)} ({n}, {spread:.1f}) | "
                  f"{fmt(a['prefill'])} | {fmt(pre_rule)} | {fmt(a['mem_peak'], 0)} | {'/'.join(prompts) or '—'} | {text} | "
                  f"{delta_d} | {delta_p} | {delta_pa} | {reading} |")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        raise SystemExit(2)
    main(sys.argv[1:])
