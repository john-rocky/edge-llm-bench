#!/usr/bin/env python3
"""The four retake rows of K/MATRIX-IOS.md: python3 -I K/r6/matrix.py <checkout> <repo>
<checkout> = a temp tree of the git index with results/raw/2026-10-16-ddp-iphone16pro-18-3-ios/ copied in and its own
scripts/build_summary.py run (results/summary/ of <repo> untouched); <repo> = the worktree (cell_gate.py).
K/r4/matrix.py's columns plus "thermal gate waited s / state" (conditions.ddp.thermalGate*, the harness's wait before
run 1): per-run values from the records in device-jsonl/ (the retakes; the first captures are in
device-jsonl-flagged/), pooled = render_leaderboard.arm_row of the cell's summary rows in <checkout>, gate =
scripts/cell_gate.py --runs 4 on the cell's records. The reply words are the reader's (r6), set below."""
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
WORDS = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "reply_words.json")))
SPECS = [("Qwen3-1.7B GPU", "litert-lm", QWEN), ("Qwen3-1.7B/int8 CPU", "litert-lm-cpu", QWEN8),
         ("Gemma 4 E2B GPU", "litert-lm", GEMMA), ("Gemma 4 E2B CPU", "litert-lm-cpu", GEMMA)]


def f1(v):
    return "—" if v is None else f"{v:.1f}"


def f0(v):
    return "—" if v is None else f"{v:.0f}"


for cell, runtime, model in SPECS:
    rows = [r for r in ROWS if r["platform"] == "ios" and r["task"] == "short-chat" and r["device"] == LABDEV
            and r["runtime"] == runtime and r["model_id"] == model]
    files = sorted(glob.glob(os.path.join(root, LAB, "device-jsonl", f"{runtime}_{model.replace('/', '_')}_short-chat_*.json")))
    recs = sorted((json.load(open(f)) for f in files), key=lambda r: r.get("timestamp") or "")
    a = rl.arm_row(rows)
    assert a["campaign"] == LAB and a["n"] == len(recs) == 4, (cell, a["campaign"], a["n"], len(recs))
    gate = subprocess.run([sys.executable, os.path.join(repo, "scripts", "cell_gate.py"), "--runs", "4", *files],
                          capture_output=True, text=True).stdout.strip() or "GATE_ERROR"
    m = [r.get("metrics") or {} for r in recs]
    c = next(x for x in m if x.get("coldRun"))
    warm = [x.get("decodeTokensPerSecond") for x in m if not x.get("coldRun")]
    e = recs[0]
    ddp = (e.get("conditions") or {}).get("ddp") or {}
    sids = {((r.get("conditions") or {}).get("ddp") or {}).get("sessionId") for r in recs}
    assert len(sids) == 1, (cell, sids)
    gates = {(((r.get("conditions") or {}).get("ddp") or {}).get("thermalGateWaitedSeconds"),
              ((r.get("conditions") or {}).get("ddp") or {}).get("thermalGateState"),
              ((r.get("conditions") or {}).get("ddp") or {}).get("thermalGateTimedOut")) for r in recs}
    assert len(gates) == 1, (cell, gates)
    waited, gstate, timed_out = gates.pop()
    art = e.get("engineArtifact") or ""
    gen = sorted({f"{x.get('generatedTokenCount')} {x.get('stopReason')}" for x in m})
    th = ", ".join(str(x.get("initialThermalState")) for x in m) + " → " + str(m[-1].get("finalThermalState"))
    sample = (e.get("outputSample") or "")[:60].replace("\n", "⏎").replace("|", "\\|")
    pooled = (f"{f1(a['warm'])} ({a['warm_n']}, {a['spread']:.1f} %) / {f1(a['cold'])} / {f1(a['prefill'])} / "
              f"{f0(a['ttft'])} / {f0(a['mem_peak'])}")
    print(f"| {cell} | {e.get('engineVersion')} ({art.split(' sha256:')[0]} sha256 {art.split('sha256:')[-1][:12]}…) "
          f"| {LABDEV}, iOS {(e.get('device') or {}).get('systemVersion')} (DDP lab iPhone 16 Pro) "
          f"| {ddp.get('sessionId')} (retake) "
          f"| {f1(c.get('decodeTokensPerSecond'))} / {f1(c.get('promptTokensPerSecond'))} / "
          f"{f0(c.get('firstTokenLatencyMS'))} / {f0(c.get('memoryPeakDuringDecodeMB'))} "
          f"| {' / '.join(f1(v) for v in warm)} | {pooled} | {', '.join(gen)} | {gate} | {WORDS[cell]}: \"{sample}\" "
          f"| {waited} s / {gstate}{' (timed out)' if timed_out else ''} | {th} |")
