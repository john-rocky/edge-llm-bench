#!/usr/bin/env python3
"""K/MATRIX-IOS.md's table: python3 -I K/r4/matrix.py <checkout> <repo>
<checkout> = a temp tree of the git index with results/raw/2026-10-16-ddp-iphone16pro-18-3-ios/ copied in and
its own scripts/build_summary.py run (results/summary/ of <repo> untouched); <repo> = the worktree (cell_gate.py).
Per-run values from the records; pooled = render_leaderboard.arm_row of the cell's summary rows (device,
runtime, model, short-chat) in <checkout>; gate = scripts/cell_gate.py --runs 4 on the cell's records.
The reply column's language / on-topic words are the reader's (r4), set below; the text is the record's."""
import glob
import json
import os
import subprocess
import sys

root, repo = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
sys.path.insert(0, os.path.join(root, "scripts"))
import render_leaderboard as rl  # noqa: E402  (the checkout's own: ROOT = <checkout>)

assert os.path.dirname(os.path.dirname(os.path.abspath(rl.__file__))) == root
ROWS = rl.load("device-runs.csv")
LAB, LABDEV = "results/raw/2026-10-16-ddp-iphone16pro-18-3-ios", "iPhone17,1 (DDP iphone16pro-18-3)"
QWEN, QWEN8, GEMMA = ("litert-community/Qwen3-1.7B", "litert-community/Qwen3-1.7B/int8",
                      "litert-community/gemma-4-E2B-it-litert-lm")
P17 = "results/raw/2026-09-09-dashboard-v1-iphone17pro-retake-ios"
P17G = "results/raw/2026-09-09-dashboard-v1-iphone17pro-retake2-ios"
# (cell, runtime, model, device column, records dir or None, who, reply words)
SPECS = [
    ("Qwen3-1.7B GPU", "litert-lm", QWEN, LABDEV, LAB, "DDP lab iPhone 16 Pro",
     "English, on-topic (reasoning preamble), same text in runs 1-4"),
    ("Qwen3-1.7B GPU", "litert-lm", QWEN, "iPhone18,1", P17, "attached iPhone 17 Pro",
     "English, on-topic, same text in runs 1-4"),
    ("Qwen3-1.7B GPU", "litert-lm", QWEN, "iPhone19,2", None, "attached iPhone 18 Pro", ""),
    ("Qwen3-1.7B/int8 CPU", "litert-lm-cpu", QWEN8, LABDEV, LAB, "DDP lab iPhone 16 Pro",
     "English, on-topic (reasoning preamble); 3 texts in 4 runs (runs 3 and 4 the same)"),
    ("Qwen3-1.7B/int8 CPU", "litert-lm-cpu", QWEN8, "iPhone18,1 / iPhone19,2", None, "attached iPhone 17 Pro / 18 Pro", ""),
    ("Gemma 4 E2B GPU", "litert-lm", GEMMA, LABDEV, LAB, "DDP lab iPhone 16 Pro",
     "English, on-topic, same text in runs 1-4"),
    ("Gemma 4 E2B GPU", "litert-lm", GEMMA, "iPhone18,1", P17G, "attached iPhone 17 Pro",
     "English, on-topic, same text in runs 1-4"),
    ("Gemma 4 E2B GPU", "litert-lm", GEMMA, "iPhone19,2", None, "attached iPhone 18 Pro", ""),
    ("Gemma 4 E2B CPU", "litert-lm-cpu", GEMMA, LABDEV, LAB, "DDP lab iPhone 16 Pro",
     "English, on-topic, same text in runs 1-4"),
    ("Gemma 4 E2B CPU", "litert-lm-cpu", GEMMA, "iPhone18,1 / iPhone19,2", None, "attached iPhone 17 Pro / 18 Pro", ""),
]


def f1(v):
    return "—" if v is None else f"{v:.1f}"


def f0(v):
    return "—" if v is None else f"{v:.0f}"


print("| cell | engine (version, artifact) | device (modelIdentifier, iOS; lab id or attached) | session / campaign "
      "| run 1 cold: decode tok/s / prefill tok/s / TTFT ms / peak MB | runs 2-4 decode tok/s "
      "| pooled (arm_row): warm median (n, spread) / cold / prefill / TTFT / peak MB | generated tokens, stop "
      "| gate (cell_gate --runs 4) | reply: language, on-topic, first 60 characters | thermal (initial per run → final) |")
print("|---|---|---|---|---|---|---|---|---|---|---|")
for cell, runtime, model, device, rdir, who, words in SPECS:
    rows = [r for r in ROWS if r["platform"] == "ios" and r["task"] == "short-chat" and r["device"] in device.split(" / ")
            and r["runtime"] == runtime and r["model_id"] == model]
    if rdir is None:
        assert not rows, (cell, device)
        print(f"| {cell} | — | {device} ({who}) | — | no attached-iPhone row "
              f"({runtime} {model} short-chat in results/summary/device-runs.csv: 0) | | | | | | |")
        continue
    files = sorted(glob.glob(os.path.join(root, rdir, "device-jsonl",
                                          f"{runtime}_{model.replace('/', '_')}_short-chat_*.json")))
    recs = sorted((json.load(open(f)) for f in files), key=lambda r: r.get("timestamp") or "")
    a = rl.arm_row(rows)
    assert a["campaign"] == rdir and a["n"] == len(recs) == 4, (cell, a["campaign"], a["n"], len(recs))
    gate = subprocess.run([sys.executable, os.path.join(repo, "scripts", "cell_gate.py"), "--runs", "4", *files],
                          capture_output=True, text=True).stdout.strip() or "GATE_ERROR"
    m = [r.get("metrics") or {} for r in recs]
    c = next(x for x in m if x.get("coldRun"))
    warm = [x.get("decodeTokensPerSecond") for x in m if not x.get("coldRun")]
    e = recs[0]
    art = e.get("engineArtifact") or ""
    sid = ((e.get("conditions") or {}).get("ddp") or {}).get("sessionId")
    where = sid or rdir.rsplit("/", 1)[-1]
    gen = sorted({f"{x.get('generatedTokenCount')} {x.get('stopReason')}" for x in m})
    th = ", ".join(str(x.get("initialThermalState")) for x in m) + " → " + str(m[-1].get("finalThermalState"))
    sample = (e.get("outputSample") or "")[:60].replace("\n", "⏎").replace("|", "\\|")
    pooled = (f"{f1(a['warm'])} ({a['warm_n']}, {a['spread']:.1f} %) / {f1(a['cold'])} / {f1(a['prefill'])} / "
              f"{f0(a['ttft'])} / {f0(a['mem_peak'])}")
    print(f"| {cell} | {e.get('engineVersion')} ({art.split(' sha256:')[0]} sha256 {art.split('sha256:')[-1][:12]}…) "
          f"| {device}, iOS {(e.get('device') or {}).get('systemVersion')} ({who}) | {where} "
          f"| {f1(c.get('decodeTokensPerSecond'))} / {f1(c.get('promptTokensPerSecond'))} / "
          f"{f0(c.get('firstTokenLatencyMS'))} / {f0(c.get('memoryPeakDuringDecodeMB'))} "
          f"| {' / '.join(f1(v) for v in warm)} | {pooled} | {', '.join(gen)} | {gate} | {words}: \"{sample}\" | {th} |")
