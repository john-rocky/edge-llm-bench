#!/usr/bin/env python3
"""Device-free selftest of scripts/session_check.py (CI).

Builds synthetic campaign dirs under a temp results/raw (no git work tree there, so every file
counts as one the commit would carry), with records stamped by the pin registry on disk, a
history csv handed in with --history and no job logs, and pins the verdicts: a clean Mac
anchor + payload pair PASS; one HOLD per rule it exercises (partial, TIMEOUT, FAILURES,
LEVEL, text check, prompt tokens, an Android lab unit's off-task reply, engine stamp, account
name); one FAIL per rule (refused at admission, no SESSION.json, stopped sitting, weights, engine
binary, credential, execution-level DDP logcat); the team rules: pin-drift (an iPhone LiteRT-LM
cell older than the newest release a platform's pin names, FAIL; the day before those pins' since
days, none; a stamp that is no release tag, a note) and protocol-off (a protocol cell at context
1056, prompt 1023 or decode 128 and a 1K text cell at context 672, FAIL; MLX's 2523, llama-bench
without a context and the context ladder, none); the text screen (a Mac / iPhone cell's off-task,
looping or empty replies: text_screen.json per run by record id, a note and PASS; the file left
alone when nothing changed; --no-text-screen writes nothing and judges alike; a cell with one run
off; a dir it cannot write and a failed run without an id keep the HOLD; an allow-list line for
the screened rule finds nothing; build_summary reads the file into text_check); an allow-list
line turning a HOLD into a PASS, and a malformed one or a line for either team rule exiting 2; the
payload / anchor pair with one half missing; the exit codes.

  python3 scripts/session_check_selftest.py     # exit 0 = pass
"""
import csv
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHECK = os.path.join(ROOT, "scripts", "session_check.py")
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import build_summary  # noqa: E402


def committed(rel):
    """A registry file as the checker reads it for these dirs (outside a git work tree: the repo's
    newest commit of it, HEAD's), else the file on disk (no git)."""
    p = subprocess.run(["git", "-C", ROOT, "show", f"HEAD:{rel}"], capture_output=True, text=True)
    try:
        return json.loads(p.stdout) if p.returncode == 0 else json.load(open(os.path.join(ROOT, rel)))
    except ValueError:
        return json.load(open(os.path.join(ROOT, rel)))


LOCK = committed("environment.lock.json")
PINS = json.load(open(os.path.join(ROOT, "android", "engine-pins.json")))["android_pins"]
LITERT_APPLE = LOCK["arms"]["litert-lm"]["default_tag"]
# the Mac's LiteRT-LM pin (arms.litert-lm.mac, for a sitting on or after its since day; the dirs here are
# dated 2099), else default_tag: every record below is a Mac record
MAC_BLOCK = LOCK["arms"]["litert-lm"].get("mac") or {}
LITERT_MAC = MAC_BLOCK.get("tag") or LITERT_APPLE
MLX = LOCK["arms"]["mlx-swift-lm"]["revision"]
LLAMA = LOCK["arms"]["llama.cpp"]["tag"]
LLAMA_MODEL = "unsloth/Qwen3-1.7B-GGUF/Q4_K_M"


def release(tag):
    m = re.fullmatch(r"v?(\d+)\.(\d+)(?:\.(\d+))?", str(tag or ""))
    return tuple(int(g or 0) for g in m.groups()) if m else None


# the LiteRT-LM pins (default_tag, the lock's platform blocks with their since days, the Android pins
# file) and the newest release among them: what pin-drift reads for the 2099 dirs below, every since past
PIN_BLOCKS = [(b.get("tag") or b.get("tag_built"), b.get("since")) for k, b in LOCK["arms"]["litert-lm"].items()
              if k in ("mac", "android", "ios") and isinstance(b, dict)]
IOS_BLOCK = LOCK["arms"]["litert-lm"].get("ios") or {}
NEWEST = max((t for t in [LITERT_APPLE, PINS.get("litert-lm")] + [t for t, _ in PIN_BLOCKS] if release(t)), key=release)
# a stamp older than NEWEST: the iPhones' default_tag while a platform's pin is ahead of it
OLD = LITERT_APPLE if release(LITERT_APPLE) < release(NEWEST) else "v0.0.1"
IOS_DEVICE = {"modelIdentifier": "iPhone18,2", "systemName": "iOS", "buildConfiguration": "Release"}
ON_TASK = ("On-device AI means the model runs on your phone itself instead of a cloud server, so it "
           "works offline, answers quickly and keeps your private data local on the device.")
OFF_TASK = ("Sure! Here is a short story about a dragon who learns to bake bread in a small village "
            "near the mountains, and the baker who teaches him patience and kindness every morning.")

_fails = []


def ok(cond, msg):
    print(("  ok  " if cond else "  FAIL ") + msg)
    if not cond:
        _fails.append(msg)


def now(minutes=0):
    t = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=minutes)
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def mac_record(runtime, model, engine, task="short-chat", sample=ON_TASK, prompt=19, cold=False,
               minutes=0, **extra):
    rec = {"schemaVersion": 1, "id": str(uuid.uuid4()), "runtime": runtime, "engineVersion": engine,
           "model": {"id": model, "quantization": "4bit"}, "task": task, "timestamp": now(minutes),
           "device": {"modelIdentifier": "Mac16,9", "systemName": "macOS", "buildConfiguration": "Release"},
           "parameters": {"maxTokens": 128},
           "metrics": {"decodeTokensPerSecond": 500.0, "promptTokenCount": prompt,
                       "generatedTokenCount": 128, "coldRun": cold, "initialThermalState": "nominal"},
           "outputSample": sample}
    rec.update(extra)
    return rec


def write_jsonl(d, name, records):
    with open(os.path.join(d, name), "w") as fh:
        fh.write("".join(json.dumps(r) + "\n" for r in records))


def cell(runtime, model, engine, n=4, **kw):
    return [mac_record(runtime, model, engine, cold=(i == 0), minutes=i, **kw) for i in range(n)]


def session(d, phase, anchor_phase=None, **over):
    s = {"schema": "dashboard-job-session.v1", "job": "dashboard-v1", "phase": phase,
         "campaign": f"results/raw/{os.path.basename(d)}", "device_key": "m4max",
         "device_identifier": "Mac16,9", "platform": "mac", "attempt": 1,
         "started": "2026-10-18 02:00:00", "ended": "2026-10-18 03:00:00", "admitted": True,
         "verdict": "ADMITTED" if phase == "anchor" else "COMPLETED",
         "reason": "anchor nominal, first session on this device", "runner_exit": 0,
         "anchor": {"regime": "warm", "anchors": [{"cell": "mlx-swift mlx-community/Qwen3-0.6B-4bit short-chat",
                                                   "primary": True, "median": 500.0, "n": 3,
                                                   "reference": None}]}}
    if phase == "payload":
        s.update(anchor_phase=f"results/raw/{anchor_phase}", cells_expected=2, cells_with_records=2)
    s.update(over)
    with open(os.path.join(d, "SESSION.json"), "w") as fh:
        json.dump(s, fh, indent=1)


def campaign(raw, name):
    d = os.path.join(raw, name)
    os.makedirs(d)
    return d


def anchor_dir(raw, name):
    d = campaign(raw, name)
    session(d, "anchor")
    write_jsonl(d, "mlx-swift_mlx-community_Qwen3-0_6B-4bit_short-chat.jsonl",
                cell("mlx-swift", "mlx-community/Qwen3-0.6B-4bit", MLX))
    return d


def payload_dir(raw, name, anchor, records=None, **over):
    d = campaign(raw, name)
    session(d, "payload", anchor, **over)
    write_jsonl(d, "mlx-swift_mlx-community_Qwen3-0_6B-4bit_short-chat.jsonl",
                cell("mlx-swift", "mlx-community/Qwen3-0.6B-4bit", MLX))
    write_jsonl(d, "litert-lm_litert-community_Qwen3-1_7B_short-chat.jsonl",
                records or cell("litert-lm", "litert-community/Qwen3-1.7B", LITERT_MAC))
    return d


GEMMA = "litert-community/gemma-4-E2B-it-litert-lm"


def ios_anchor(raw, name):
    d = campaign(raw, name)
    session(d, "anchor")
    write_jsonl(d, "mlx-swift_mlx-community_Qwen3-0_6B-4bit_short-chat.jsonl",
                [dict(r, device=dict(IOS_DEVICE)) for r in cell("mlx-swift", "mlx-community/Qwen3-0.6B-4bit", MLX)])
    return d


def ios_payload(raw, name, anchor, engine):
    """An iPhone sitting's payload: the MLX cell and a LiteRT-LM cell stamping `engine`."""
    d = campaign(raw, name)
    session(d, "payload", os.path.basename(anchor))
    for rt, model, eng in (("mlx-swift", "mlx-community/Qwen3-0.6B-4bit", MLX),
                           ("litert-lm", "litert-community/Qwen3-1.7B", engine)):
        write_jsonl(d, f"{rt}_{model.replace('/', '_')}_short-chat.jsonl",
                    [dict(r, device=dict(IOS_DEVICE)) for r in cell(rt, model, eng)])
    return d


def protocol_record(runtime, model, engine, i, task="native-benchmark-1024x256", ctx=2048, prompt=1024, gen=256):
    """A Mac record of a headline cell: metrics.contextTokensConfigured (absent when ctx is None), the
    prompt and generated token counts, a 256-token budget."""
    rec = mac_record(runtime, model, engine, task=task, prompt=prompt, cold=(i == 0), minutes=i,
                     parameters={"maxTokens": 256})
    rec["metrics"]["generatedTokenCount"] = gen
    if ctx is not None:
        rec["metrics"]["contextTokensConfigured"] = ctx
    return rec


def ddp_unit(raw, name, reply=ON_TASK):
    """A lab unit's job sitting (dashboard_job.py ddp_sitting): three litert-lm-gpu short-chat runs over
    one engine log whose reply is `reply`, a run logcat, the job's SESSION.json."""
    unit = campaign(raw, name)
    app = os.path.join(unit, "app-path-android")
    os.makedirs(app)
    log_name = "litert-lm-gpu_litert-community_Qwen3-1.7B_short-chat_2099-07-01T00-00-00_run1.log"
    with open(os.path.join(app, log_name), "w") as fh:
        fh.write("===ENGINE_OUTPUT===\ninput_prompt: What does on-device AI mean?\n" + reply
                 + "\nBenchmarkInfo:\n  Prefill Turn 1: Processed 19 tokens\n")
    for i in range(3):
        rec = {"schemaVersion": 1, "id": str(uuid.uuid4()), "runtime": "litert-lm-gpu",
               "engineVersion": PINS["litert-lm"], "model": {"id": "litert-community/Qwen3-1.7B"},
               "task": "short-chat", "timestamp": now(i),
               "device": {"modelIdentifier": "SM-S942U1", "systemName": "Android",
                          "ddp": {"deviceId": "m1q-36", "serial": "FAKEUNIT1"}},
               "parameters": {"maxTokens": 128},
               "metrics": {"decodeTokensPerSecond": 20.0, "promptTokenCount": 19, "generatedTokenCount": 128,
                           "coldRun": True, "firstEver": i == 0},
               "conditions": {"protocolFlags": ["cpu-capped", "cpu-capped-at-start"],
                              "ddp": {"sessionId": "session-fake0001", "deviceId": "m1q-36"}},
               "provenance": {"rawLog": log_name, "modelShaSource": "device"}}
        with open(os.path.join(app, f"run{i + 1}.json"), "w") as fh:
            json.dump(rec, fh)
    with open(os.path.join(app, "SKIPPED.txt"), "w") as fh:
        fh.write("CELL_SKIP litert-lm-cpu litert-community/Qwen3-0.6B short-chat exclude-on=s26 reason=x\n")
    os.makedirs(os.path.join(unit, "ddp", "session-fake0001", "j01"))
    with open(os.path.join(unit, "ddp", "session-fake0001", "j01", "run1_logcat.txt"), "w") as fh:
        fh.write("01-01 00:00:00 I litert: engine loaded\n")
    with open(os.path.join(unit, "SESSION.json"), "w") as fh:
        json.dump({"schema": "dashboard-job-session.v1", "job": "dashboard-v1", "phase": "payload",
                   "campaign": f"results/raw/{os.path.basename(unit)}", "device_key": "s26-ddp",
                   "device_identifier": "SM-S942U1 (DDP m1q-36)", "platform": "ddp", "attempt": 1,
                   "started": "2099-07-01 02:00:00", "ended": "2099-07-01 03:00:00", "admitted": True,
                   "verdict": "COMPLETED", "reason": "ddp lab unit: no session anchor; each run carries its "
                   "cap marks and the text check", "anchor": None, "runner_exit": 0,
                   "cells_expected": 1, "cells_with_records": 1,
                   "ddp": {"id": "m1q-36", "sessions": ["session-fake0001"], "jobs": 1, "device_minutes": 9.5}},
                  fh, indent=1)
    return unit


def screen_of(d):
    p = os.path.join(d, "text_screen.json")
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None


def run(dirs, *extra, history=None, allow=None):
    out = tempfile.mktemp(suffix=".json")
    cmd = [sys.executable, CHECK] + dirs + ["--json", out, "--user", "testuser", "-q",
                                            "--allow-list", allow or os.devnull]
    if history:
        cmd += ["--history", history]
    p = subprocess.run(cmd + list(extra), capture_output=True, text=True)
    res = json.load(open(out)) if os.path.exists(out) else {"dirs": []}
    if os.path.exists(out):
        os.remove(out)
    return p.returncode, {r["name"]: r for r in res["dirs"]}, p.stdout + p.stderr


def rules(r, live=True):
    return {f["rule"] for f in r["findings"] if not (live and f["allowed_by"])}


def main():
    tmp = tempfile.mkdtemp(prefix="session-check-selftest-")
    raw = os.path.join(tmp, "results", "raw")
    os.makedirs(raw)
    hist = os.path.join(tmp, "device-runs.csv")
    with open(hist, "w") as fh:
        fh.write("campaign,platform,engine_version,runtime,model_id,task,prompt_tokens,text_check\n")
        for i in range(3):
            fh.write(f"results/raw/old-{i}-mac,mac,{LITERT_MAC},litert-lm,litert-community/Qwen3-1.7B,"
                     f"short-chat,19,\n")

    print("--- PASS: a clean Mac anchor + payload pair, the prompt as the history reads it")
    a = anchor_dir(raw, "2099-01-01-dashboard-v1-m4max-anchor-mac")
    p = payload_dir(raw, "2099-01-01-dashboard-v1-m4max-mac", os.path.basename(a))
    rc, res, out = run([a, p], history=hist)
    ok(rc == 0, f"exit 0 when every dir passes (got {rc})")
    for n in (os.path.basename(a), os.path.basename(p)):
        ok(res.get(n, {}).get("verdict") == "PASS", f"{n}: PASS ({sorted(rules(res.get(n, {'findings': []})))})")
    ok(res[os.path.basename(p)]["samples"] and "on-device" in res[os.path.basename(p)]["samples"][0]["text"].lower(),
       "a sample per cell is listed for a person to read")

    print("--- HOLD: one rule each")
    holds = {
        "partial": dict(cells_with_records=1),
        "verdict": dict(verdict="TIMEOUT", runner_exit=124),
        "prompt-tokens": dict(records=cell("litert-lm", "litert-community/Qwen3-1.7B", LITERT_MAC, prompt=8)),
        "engine-stamp": dict(records=cell("litert-lm", "litert-community/Qwen3-1.7B", "v9.9.9")),
        "gen-budget": dict(records=[dict(r, metrics=dict(r["metrics"], generatedTokenCount=579))
                                    for r in cell("litert-lm", "litert-community/Qwen3-1.7B", LITERT_MAC)]),
    }
    for i, (rule, kw) in enumerate(holds.items()):
        aa = anchor_dir(raw, f"2099-02-{i + 1:02d}-dashboard-v1-m4max-anchor-mac")
        pp = payload_dir(raw, f"2099-02-{i + 1:02d}-dashboard-v1-m4max-mac", os.path.basename(aa), **kw)
        rc, res, out = run([aa, pp], history=hist)
        r = res[os.path.basename(pp)]
        ok(r["verdict"] == "HOLD" and rule in rules(r), f"{rule}: HOLD ({sorted(rules(r))})")
        ok(rc == 1, f"{rule}: exit 1")
    aa = anchor_dir(raw, "2099-03-01-dashboard-v1-m4max-anchor-mac")
    pp = payload_dir(raw, "2099-03-01-dashboard-v1-m4max-mac", os.path.basename(aa))
    with open(os.path.join(pp, "FAILURES.txt"), "w") as fh:
        fh.write("FAIL core-ai core-ai/qwen3-1.7b-gpu short-chat round=1\n")
    with open(os.path.join(pp, "FLAGGED.txt"), "w") as fh:
        fh.write("GATE_FAIL litert-lm litert-community/Qwen3-1.7B short-chat first='COLLAPSE 28' "
                 "retry='LEVEL 20' (retry kept; ⚠ downstream)\n"
                 "GATE_FAIL mlx-swift mlx-community/Qwen3-0.6B-4bit short-chat first='SPREAD 6.4' "
                 "retry='SPREAD 5.9' (retry kept; ⚠ downstream)\n")
    with open(os.path.join(pp, "session_provenance.txt"), "w") as fh:
        fh.write("cwd /Users/testuser/code/edge-llm-bench\n")
    rc, res, out = run([aa, pp], history=hist)
    r = res[os.path.basename(pp)]
    ok({"failures", "flagged", "user-name"} <= rules(r) and r["verdict"] == "HOLD",
       f"a FAILURES line, a LEVEL retry and the account name in a path: HOLD ({sorted(rules(r))})")
    ok(any("SPREAD" in n for n in r["notes"]) and sum(f["rule"] == "flagged" for f in r["findings"]) == 1,
       "a SPREAD retry is a note (renders ⚠), the LEVEL retry the one flagged finding")

    print("--- the text screen: a Mac / iPhone text cell's reply proxies per run go into text_screen.json, a note")
    # a llama.cpp cell, so the screen's cases read no LiteRT-LM pin (engine-stamp, pin-drift)
    llama = f"llama.cpp {LLAMA_MODEL} short-chat ({LLAMA})"
    mlx = f"mlx-swift mlx-community/Qwen3-0.6B-4bit short-chat ({MLX})"
    off_recs = cell("llama.cpp", LLAMA_MODEL, LLAMA, sample=OFF_TASK)
    t1a = anchor_dir(raw, "2099-09-01-dashboard-v1-m4max-anchor-mac")
    t1p = payload_dir(raw, "2099-09-01-dashboard-v1-m4max-mac", os.path.basename(t1a), records=off_recs)
    rc, res, out = run([t1a, t1p], history=hist)
    r = res[os.path.basename(t1p)]
    s = screen_of(t1p) or {"cells": {}}
    c = s["cells"].get(llama, {})
    ok(rc == 0 and r["verdict"] == "PASS" and not any(f["rule"].startswith("reply-") for f in r["findings"])
       and f"screened text-fail: {llama} (reply-off-task): the page shows the cell as text-fail" in r["notes"],
       f"4 of 4 off-task replies on the Mac: no reply-off-task finding, the note, PASS ({sorted(rules(r))}, exit {rc})")
    ok(s.get("schema") == "text-screen.v1" and s.get("rules") == ["reply-empty", "reply-loop", "reply-off-task"]
       and set(s["cells"]) == {llama, mlx} and c.get("verdict") == "FAIL" and c.get("rules") == ["reply-off-task"]
       and (c.get("runs"), c.get("runs_off")) == (4, 4) and c.get("run_rules") == {x["id"]: ["reply-off-task"] for x in off_recs}
       and c.get("sample", "").startswith("Sure! Here is a short story") and "4 of 4 replies name none" in c.get("detail", "")
       and s["cells"][mlx]["verdict"] == "PASS" and set(map(tuple, s["cells"][mlx]["run_rules"].values())) == {()}
       and s.get("written_by", "").startswith("scripts/session_check.py ") and s.get("written_at"),
       f"text_screen.json: the cell FAIL (reply-off-task, 4 of 4, each run by its record id, a sample), the MLX "
       f"cell PASS (every run []), who wrote it and when ({sorted(s['cells'])})")
    ok(r["text_screen"] and r["text_screen"]["state"] == "written" and [x["cell"] for x in r["text_screen"]["text_fail"]] == [llama]
       and "text screen: written text_screen.json (2 cells, 1 text-fail: " in out
       and (screen_of(t1a) or {}).get("cells", {}).keys() == {mlx},
       "the result and the output line say written, with the cell; the anchor phase has its own file")
    path = os.path.join(t1p, "text_screen.json")
    before = (os.stat(path).st_mtime_ns, open(path, "rb").read())
    rc, res, out = run([t1a, t1p], history=hist)
    ok(res[os.path.basename(t1p)]["text_screen"]["state"] == "unchanged"
       and (os.stat(path).st_mtime_ns, open(path, "rb").read()) == before,
       "checked again with the same records: unchanged, the file not touched (mtime and bytes)")
    with open(os.path.join(tmp, "allow-reply.tsv"), "w") as fh:
        fh.write(f"reply-off-task\t*\t{llama}\t0123abcd\tthe replies answer another question\n")
    rc, res, out = run([t1a, t1p], history=hist, allow=os.path.join(tmp, "allow-reply.tsv"))
    r = res[os.path.basename(t1p)]
    ok(r["verdict"] == "PASS" and not rules(r, live=False) & {"reply-off-task"} and any(n.startswith("screened") for n in r["notes"]),
       "an allow-list line for the screened rule finds no finding to excuse (the screen marks the runs)")

    print("--- the text screen: --no-text-screen writes nothing and judges as if it were written")
    loop_recs = cell("llama.cpp", LLAMA_MODEL, LLAMA, sample="on-device AI " * 40)
    t2a = anchor_dir(raw, "2099-09-02-dashboard-v1-m4max-anchor-mac")
    t2p = payload_dir(raw, "2099-09-02-dashboard-v1-m4max-mac", os.path.basename(t2a), records=loop_recs)
    rc, res, out = run([t2a, t2p], "--no-text-screen", history=hist)
    r = res[os.path.basename(t2p)]
    ok(rc == 0 and r["verdict"] == "PASS" and screen_of(t2p) is None and screen_of(t2a) is None
       and r["text_screen"]["state"] == "would write"
       and f"screened text-fail: {llama} (reply-empty, reply-loop): the page shows the cell as text-fail "
           f"(text_screen.json not written: --no-text-screen)" in r["notes"] and "would write text_screen.json" in out,
       f"a looping cell under --no-text-screen: no file in either dir, the note says not written, PASS "
       f"({r['text_screen']['state']}, exit {rc})")
    rc, res, out = run([t2a, t2p], history=hist)
    loop_path = os.path.join(t2p, "text_screen.json")
    before = open(loop_path, "rb").read()
    write_jsonl(t2p, "litert-lm_litert-community_Qwen3-1_7B_short-chat.jsonl",     # the file payload_dir wrote them to
                cell("llama.cpp", LLAMA_MODEL, LLAMA))
    rc, res, out = run([t2a, t2p], "--no-text-screen", history=hist)
    r = res[os.path.basename(t2p)]
    ok(r["text_screen"]["state"] == "would rewrite" and open(loop_path, "rb").read() == before and r["verdict"] == "PASS",
       "records replaced after the file was written: --no-text-screen says would rewrite and leaves the file as it was")
    rc, res, out = run([t2a, t2p], history=hist)
    ok(res[os.path.basename(t2p)]["text_screen"]["state"] == "rewritten"
       and screen_of(t2p)["cells"][llama]["verdict"] == "PASS", "checked without the flag: rewritten, the cell PASS")

    print("--- the text screen: one run of four off; a dir it cannot write; a failed run without a record id")
    part = cell("llama.cpp", LLAMA_MODEL, LLAMA)
    part[2]["outputSample"] = ""
    t3a = anchor_dir(raw, "2099-09-03-dashboard-v1-m4max-anchor-mac")
    t3p = payload_dir(raw, "2099-09-03-dashboard-v1-m4max-mac", os.path.basename(t3a), records=part)
    rc, res, out = run([t3a, t3p], history=hist)
    r = res[os.path.basename(t3p)]
    c = (screen_of(t3p) or {"cells": {}})["cells"].get(llama, {})
    ok(r["verdict"] == "PASS" and (c.get("verdict"), c.get("runs"), c.get("runs_off")) == ("FAIL", 4, 1)
       and c.get("run_rules") == {x["id"]: (["reply-empty"] if i == 2 else []) for i, x in enumerate(part)}
       and f"screened text-fail: {llama} (reply-empty): 1 of 4 runs, which the page leaves out of the cell's number" in r["notes"],
       f"one empty reply of four: the cell FAIL with 1 of 4 runs off, only that run marked, PASS ({c.get('runs_off')})")
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        print("  skip  running as root: a read-only dir does not stop the write")
    else:
        t4a = anchor_dir(raw, "2099-09-04-dashboard-v1-m4max-anchor-mac")
        t4p = payload_dir(raw, "2099-09-04-dashboard-v1-m4max-mac", os.path.basename(t4a),
                          records=cell("llama.cpp", LLAMA_MODEL, LLAMA, sample=OFF_TASK))
        os.chmod(t4p, 0o555)
        try:
            rc, res, out = run([t4a, t4p], history=hist)
        finally:
            os.chmod(t4p, 0o755)
        r = res[os.path.basename(t4p)]
        ok(r["verdict"] == "HOLD" and rules(r) == {"reply-off-task"} and r["text_screen"]["state"].startswith("not written")
           and screen_of(t4p) is None, f"a dir the file cannot be written in: reply-off-task stays HOLD ({r['text_screen']['state'][:40]})")
    noid = cell("llama.cpp", LLAMA_MODEL, LLAMA, sample=OFF_TASK)
    for x in noid:
        x.pop("id")
    t5a = anchor_dir(raw, "2099-09-05-dashboard-v1-m4max-anchor-mac")
    t5p = payload_dir(raw, "2099-09-05-dashboard-v1-m4max-mac", os.path.basename(t5a), records=noid)
    rc, res, out = run([t5a, t5p], history=hist)
    r = res[os.path.basename(t5p)]
    ok(r["verdict"] == "HOLD" and rules(r) == {"reply-off-task"}
       and (screen_of(t5p) or {"cells": {}})["cells"].get(llama, {}).get("run_rules") == {},
       f"failed runs without a record id: the file names none of them, the cell keeps its HOLD ({sorted(rules(r))})")

    print("--- FAIL: one rule each")
    ra = anchor_dir(raw, "2099-04-01-dashboard-v1-m4max-anchor-mac")
    rp = payload_dir(raw, "2099-04-01-dashboard-v1-m4max-mac", os.path.basename(ra),
                     admitted=False, reason="anchor-collapse")
    nosess = campaign(raw, "2099-04-02-dashboard-v1-m4max-mac")
    write_jsonl(nosess, "litert-lm_litert-community_Qwen3-1_7B_short-chat.jsonl",
                cell("litert-lm", "litert-community/Qwen3-1.7B", LITERT_MAC))
    stopped = campaign(raw, "2099-04-03-m4max-i1-stopped-0155-mac")
    sa = anchor_dir(raw, "2099-04-04-dashboard-v1-m4max-anchor-mac")
    sp = payload_dir(raw, "2099-04-04-dashboard-v1-m4max-mac", os.path.basename(sa))
    with open(os.path.join(sp, "qwen3.gguf"), "wb") as fh:
        fh.write(b"GGUF" + b"\0" * 64)
    with open(os.path.join(sp, "litert_lm_main"), "wb") as fh:
        fh.write(b"\x7fELF" + b"\0" * 64)
    with open(os.path.join(sp, "env.txt"), "w") as fh:
        fh.write("ANTHROPIC_API_KEY=" + "sk-" + "ant-" + "x" * 32 + "\n")
    ddp = campaign(raw, "2099-04-05-dashboard-v1-s26-s3-ddp-m1q-36-android")
    ex = os.path.join(ddp, "ddp", "session-1", "j01", "execution-abc")
    os.makedirs(ex)
    with open(os.path.join(ex, "logcat.txt"), "w") as fh:
        fh.write("01-01 00:00:00 I wifi: SSID: \"home-net\" 192.168.1.20\n")
    rc, res, out = run([ra, rp, nosess, stopped, sa, sp, ddp], history=hist)
    ok(res[os.path.basename(rp)]["verdict"] == "FAIL" and "not-admitted" in rules(res[os.path.basename(rp)]),
       "refused at admission: FAIL not-admitted")
    ok(res[os.path.basename(nosess)]["verdict"] == "FAIL" and "session-missing" in rules(res[os.path.basename(nosess)]),
       "a dashboard dir the job made without SESSION.json (no job logs: judged by its name): FAIL session-missing")
    ok(res[os.path.basename(stopped)]["verdict"] == "FAIL" and "stopped-sitting" in rules(res[os.path.basename(stopped)]),
       "a stopped sitting's quarantine: FAIL stopped-sitting")
    big = [f["detail"] for f in res[os.path.basename(sp)]["findings"] if f["rule"] == "big-file"]
    ok(len(big) == 2 and "secret" in rules(res[os.path.basename(sp)]),
       f"weights (.gguf), an ELF binary and a credential: FAIL big-file x2 + secret ({len(big)})")
    r = res[os.path.basename(ddp)]
    ok(r["kind"] == "DDP" and r["verdict"] == "FAIL" and "logcat-unscrubbed" in rules(r)
       and "not-job" in rules(r), f"a DDP dir with an execution-level logcat.txt: FAIL ({sorted(rules(r))})")
    ok(rc == 1, "exit 1 with a FAIL")

    print("--- the allow-list: a line turns its finding into a PASS; a malformed one is a usage error")
    allow = os.path.join(tmp, "allow.tsv")
    name = os.path.basename(pp)
    with open(allow, "w") as fh:
        fh.write("# test\n"
                 f"failures\t{name}\tFAIL core-ai \t0123abcd\tcore-ai bundle not staged\n"
                 f"flagged\t{name}\tre:retry='LEVEL \\d+'\t0123abcd\tretaken in a cooler window\n"
                 f"user-name\t2099-03-*\t*\t0123abcd\tscrubbed in the commit\n")
    rc, res, out = run([aa, pp], history=hist, allow=allow)
    r = res[name]
    ok(r["verdict"] == "PASS" and rules(r) == set() and len(rules(r, live=False)) == 3,
       f"three allow-listed findings: PASS, still listed with their commit ({sorted(rules(r, live=False))})")
    ok(all((f["allowed_by"] or {}).get("commit") == "0123abcd" for f in r["findings"]), "each names the allowing commit")
    with open(allow, "w") as fh:
        fh.write("failures\tx\t*\tnot-a-hash\treason\n")
    rc, res, out = run([aa, pp], history=hist, allow=allow)
    ok(rc == 2, f"an allow-list line without a commit hash: exit 2 (got {rc})")

    print("--- the pair: payload and anchor phase go in together")
    lone = anchor_dir(raw, "2099-05-01-dashboard-v1-m4max-anchor-mac")
    orphan = payload_dir(raw, "2099-05-02-dashboard-v1-m4max-mac", "2099-05-02-dashboard-v1-m4max-anchor-mac")
    xa = anchor_dir(raw, "2099-05-03-dashboard-v1-m4max-anchor-mac")
    xp = payload_dir(raw, "2099-05-03-dashboard-v1-m4max-mac", os.path.basename(xa))
    rc, res, out = run([lone, orphan, xp], history=hist)
    ok("pair-incomplete" in rules(res[os.path.basename(lone)]) and res[os.path.basename(lone)]["verdict"] == "HOLD",
       "an anchor phase no payload names: HOLD pair-incomplete")
    ok("pair-broken" in rules(res[os.path.basename(orphan)]) and res[os.path.basename(orphan)]["verdict"] == "FAIL",
       "a payload whose anchor phase is not on disk: FAIL pair-broken")
    ok("pair-incomplete" in rules(res[os.path.basename(xp)]),
       "a payload checked without its (uncommitted) anchor phase: HOLD pair-incomplete")
    rc, res, out = run([xa, xp], history=hist)
    ok(rc == 0 and all(r["verdict"] == "PASS" for r in res.values()), "the same two checked together: PASS")

    print("--- a lab unit's job sitting (DDP, SESSION.json of the job): the job-session rules, no pair rules")
    unit = ddp_unit(raw, "2099-07-01-dashboard-v1-s26-ddp-m1q-36-android")
    rc, res, out = run([unit], history=hist)
    r = res[os.path.basename(unit)]
    ok(r["kind"] == "job payload (ddp)" and "not-job" not in rules(r) and r["verdict"] == "PASS" and rc == 0,
       f"kind job payload (ddp), no not-job, PASS ({r['kind']}, {sorted(rules(r))}, exit {rc})")
    off_unit = ddp_unit(raw, "2099-07-02-dashboard-v1-s26-ddp-m1q-36-android", reply=OFF_TASK)
    rc, res, out = run([off_unit], history=hist)
    r = res[os.path.basename(off_unit)]
    ok(r["verdict"] == "HOLD" and rules(r) == {"reply-off-task"} and r["text_screen"] is None
       and not os.path.exists(os.path.join(off_unit, "text_screen.json")),
       f"an Android cell the runner did not check with an off-task reply: HOLD reply-off-task, no text screen "
       f"(the runner's check is the rule there) ({sorted(rules(r))})")
    ok(any(n.startswith("pair rules n/a") for n in r["notes"]) and any(n.startswith("cpu-cap: a lab unit")
                                                                        for n in r["notes"]),
       "the pair rules are n/a and the lab unit's caps are a note, never a verdict")
    ex = os.path.join(unit, "ddp", "session-fake0001", "j01", "execution-abc")
    os.makedirs(ex)
    with open(os.path.join(ex, "logcat.txt"), "w") as fh:
        fh.write("01-01 00:00:00 I litert: engine loaded\n")
    with open(os.path.join(unit, "SESSION.json")) as fh:
        sess = json.load(fh)
    with open(os.path.join(unit, "SESSION.json"), "w") as fh:
        json.dump(dict(sess, cells_with_records=0), fh)
    rc, res, out = run([unit], history=hist)
    r = res[os.path.basename(unit)]
    ok(r["verdict"] == "FAIL" and {"logcat-unscrubbed", "partial"} <= rules(r),
       f"its execution-level logcat.txt still FAILs, a cell without records still holds ({sorted(rules(r))})")

    print("--- the Mac's LiteRT-LM pin: arms.litert-lm.mac from its since day, default_tag before it")
    if LITERT_MAC != LITERT_APPLE and MAC_BLOCK.get("since"):
        ma = anchor_dir(raw, "2099-06-01-dashboard-v1-m4max-anchor-mac")
        mp = payload_dir(raw, "2099-06-01-dashboard-v1-m4max-mac", os.path.basename(ma),
                         records=cell("litert-lm", "litert-community/Qwen3-1.7B", LITERT_APPLE))
        rc, res, out = run([ma, mp], history=hist)
        r = res[os.path.basename(mp)]
        stamp = [f["detail"] for f in r["findings"] if f["rule"] == "engine-stamp"]
        ok(stamp and "arms.litert-lm.mac.tag" in stamp[0] and LITERT_MAC in stamp[0]
           and r["verdict"] == "FAIL" and "pin-drift" in rules(r),
           f"a Mac sitting after since stamping default_tag {LITERT_APPLE}: engine-stamp against the "
           f"Mac block's {LITERT_MAC}, and FAIL pin-drift ({stamp[:1]}, {sorted(rules(r))})")
        before = (datetime.date.fromisoformat(MAC_BLOCK["since"]) - datetime.timedelta(days=1)).isoformat()
        ba = anchor_dir(raw, f"{before}-dashboard-v1-m4max-anchor-mac")
        bp = payload_dir(raw, f"{before}-dashboard-v1-m4max-mac", os.path.basename(ba),
                         records=cell("litert-lm", "litert-community/Qwen3-1.7B", LITERT_APPLE))
        hist_old = os.path.join(tmp, "device-runs-old.csv")
        with open(hist_old, "w") as fh:
            fh.write("campaign,platform,engine_version,runtime,model_id,task,prompt_tokens,text_check\n")
            for i in range(3):
                fh.write(f"results/raw/old-{i}-mac,mac,{LITERT_APPLE},litert-lm,litert-community/Qwen3-1.7B,"
                         f"short-chat,19,\n")
        rc, res, out = run([ba, bp], history=hist_old)
        r = res[os.path.basename(bp)]
        ok(r["verdict"] == "PASS" and "engine-stamp" not in rules(r) and "pin-drift" not in rules(r),
           f"a Mac sitting the day before since ({before}) stamping default_tag {LITERT_APPLE}: PASS, no "
           f"engine-stamp, no pin-drift ({sorted(rules(r))})")
    else:
        print("  skip  the lock has no arms.litert-lm.mac block with another tag and a since day")

    print("--- pin-drift: a LiteRT-LM cell older than the newest release a platform's pin names that day FAILs")
    ia = ios_anchor(raw, "2099-08-01-dashboard-v1-iphone18pro-anchor-ios")
    ip = ios_payload(raw, "2099-08-01-dashboard-v1-iphone18pro-ios", ia, OLD)
    rc, res, out = run([ia, ip], history=hist)
    r = res[os.path.basename(ip)]
    drift = [f["detail"] for f in r["findings"] if f["rule"] == "pin-drift"]
    ok(r["verdict"] == "FAIL" and len(drift) == 1 and drift[0].startswith(f"ios litert-lm: stamps {OLD} x4;")
       and f": {NEWEST} (" in drift[0] and rc == 1,
       f"an iPhone sitting stamping {OLD} with {NEWEST} pinned on another platform: FAIL pin-drift, one "
       f"finding per platform and arm ({drift[:1]})")
    ok(res[os.path.basename(ia)]["verdict"] == "PASS", "its anchor phase without a LiteRT-LM cell: PASS")
    newer = [s for t, s in PIN_BLOCKS if release(t) and release(t) > release(OLD)]
    android_block = any(k == "android" for k in LOCK["arms"]["litert-lm"])
    if OLD == LITERT_APPLE and newer and all(newer) and (android_block or release(PINS.get("litert-lm")) <= release(OLD)):
        before = (min(datetime.date.fromisoformat(s) for s in newer) - datetime.timedelta(days=1)).isoformat()
        ba = ios_anchor(raw, f"{before}-dashboard-v1-iphone18pro-anchor-ios")
        bp = ios_payload(raw, f"{before}-dashboard-v1-iphone18pro-ios", ba, OLD)
        rc, res, out = run([ba, bp], history=hist)
        r = res[os.path.basename(bp)]
        ok("pin-drift" not in rules(r) and r["verdict"] == "PASS",
           f"the same the day before the first since of a newer pin ({before}): no pin-drift ({sorted(rules(r))})")
    else:
        print("  skip  no platform pin newer than default_tag with a since day")
    na = anchor_dir(raw, "2099-08-02-dashboard-v1-m4max-anchor-mac")
    np_ = payload_dir(raw, "2099-08-02-dashboard-v1-m4max-mac", os.path.basename(na),
                      records=cell("litert-lm", "litert-community/Qwen3-1.7B", "main@1dadd00c"))
    rc, res, out = run([na, np_], history=hist)
    r = res[os.path.basename(np_)]
    ok("pin-drift" not in rules(r) and r["verdict"] == "HOLD"
       and any("main@1dadd00c: not a release tag, not compared" in n for n in r["notes"]),
       f"a stamp that is no release tag: a note, never pin-drift (engine-stamp holds it: {sorted(rules(r))})")

    print("--- the iPhones' LiteRT-LM pin: arms.litert-lm.ios from its since day, default_tag before it")
    if IOS_BLOCK.get("tag") and IOS_BLOCK.get("since") and release(IOS_BLOCK["tag"]) == release(NEWEST) \
            and release(LITERT_APPLE) < release(NEWEST):
        since = datetime.date.fromisoformat(IOS_BLOCK["since"])
        sa = ios_anchor(raw, f"{since.isoformat()}-dashboard-v1-iphone18pro-anchor-ios")
        sp = ios_payload(raw, f"{since.isoformat()}-dashboard-v1-iphone18pro-ios", sa, IOS_BLOCK["tag"])
        rc, res, out = run([sa, sp], history=hist)
        r = res[os.path.basename(sp)]
        ok(r["verdict"] == "PASS" and not ({"engine-stamp", "pin-drift"} & rules(r)),
           f"an iPhone sitting on the ios block's since day ({since}) stamping its {IOS_BLOCK['tag']}: no "
           f"engine-stamp, no pin-drift, PASS ({sorted(rules(r))})")
        day = since - datetime.timedelta(days=1)
        ahead = [s for t, s in PIN_BLOCKS if release(t) and release(t) > release(LITERT_APPLE) and s
                 and datetime.date.fromisoformat(s) <= day]
        if ahead:
            da = ios_anchor(raw, f"{day.isoformat()}-dashboard-v1-iphone18pro-anchor-ios")
            dp_ = ios_payload(raw, f"{day.isoformat()}-dashboard-v1-iphone18pro-ios", da, LITERT_APPLE)
            rc, res, out = run([da, dp_], history=hist)
            r = res[os.path.basename(dp_)]
            ok(r["verdict"] == "FAIL" and "engine-stamp" not in rules(r) and "pin-drift" in rules(r),
               f"the day before ({day}) stamping default_tag {LITERT_APPLE}: its registry pin, no engine-stamp; "
               f"a newer pin on another platform since {min(ahead)}: FAIL pin-drift ({sorted(rules(r))})")
        else:
            print("  skip  no other platform's newer pin applies the day before the ios block's since")
    else:
        print("  skip  the lock has no arms.litert-lm.ios block at the newest release with a since day")

    print("--- protocol-off: a LiteRT-LM headline cell off the agreed protocol FAILs; other arms and tasks are not read")
    pa = anchor_dir(raw, "2099-08-03-dashboard-v1-m4max-anchor-mac")
    pp = payload_dir(raw, "2099-08-03-dashboard-v1-m4max-mac", os.path.basename(pa))
    native = [protocol_record("litert-lm", GEMMA, LITERT_MAC, i, **kw) for i, kw in
              enumerate(({}, {"ctx": 1056}, {"prompt": 1023}, {"gen": 128}))]
    write_jsonl(pp, "litert-lm_gemma_native-benchmark-1024x256.jsonl", native)
    write_jsonl(pp, "litert-lm_gemma_long-context-1024-gen256.jsonl",
                [protocol_record("litert-lm", GEMMA, LITERT_MAC, i, task="long-context-1024-gen256", ctx=672)
                 for i in range(4)])
    rc, res, out = run([pa, pp], history=hist)
    r = res[os.path.basename(pp)]
    off = sorted(f["detail"] for f in r["findings"] if f["rule"] == "protocol-off")
    ok(r["verdict"] == "FAIL" and len(off) == 2
       and any("native-benchmark-1024x256" in d and "3 of 4 runs" in d and "context 1056 x1; prompt 1023 x1; "
               "generated 128 x1" in d for d in off)
       and any("long-context-1024-gen256" in d and "4 of 4 runs" in d and "context 672 x4" in d for d in off),
       f"a protocol cell at context 1056, prompt 1023, decode 128 and a 1K text cell at context 672: FAIL "
       f"protocol-off, one finding per cell ({off})")
    qa = anchor_dir(raw, "2099-08-04-dashboard-v1-m4max-anchor-mac")
    qp = payload_dir(raw, "2099-08-04-dashboard-v1-m4max-mac", os.path.basename(qa))
    write_jsonl(qp, "mlx-swift_gemma_long-context-1024-gen256.jsonl",
                [protocol_record("mlx-swift", "mlx-community/gemma-4-e2b-it-4bit", MLX, i,
                                 task="long-context-1024-gen256", ctx=2523) for i in range(4)])
    write_jsonl(qp, "llama.cpp_gemma_native-benchmark-1024x256.jsonl",
                [protocol_record("llama.cpp", "unsloth/gemma-4-E2B-it-GGUF/Q4_K_M", LLAMA, i, ctx=None)
                 for i in range(4)])
    write_jsonl(qp, "litert-lm_gemma_long-context-2048-gen256.jsonl",
                [protocol_record("litert-lm", GEMMA, LITERT_MAC, i, task="long-context-2048-gen256", ctx=4096)
                 for i in range(4)])
    rc, res, out = run([qa, qp], history=hist)
    r = res[os.path.basename(qp)]
    ok(r["verdict"] == "PASS" and "protocol-off" not in rules(r, live=False),
       f"MLX's 1K text cell at 2523, llama-bench's protocol cell without a context, the LiteRT-LM context "
       f"ladder at 4096 and the short-chat cells: no protocol-off, PASS ({sorted(rules(r, live=False))})")

    print("--- the team rules take no allow-list line")
    for rule in ("pin-drift", "protocol-off"):
        with open(allow, "w") as fh:
            fh.write(f"{rule}\t2099-*\t*\t0123abcd\tthe older release is fine here\n")
        rc, res, out = run([ia, ip], history=hist, allow=allow)
        ok(rc == 2 and "never allow-listed" in out, f"an allow-list line for {rule}: exit 2 (got {rc})")

    print("--- the text screen: build_summary reads it into text_check, per run by record id")
    late = mac_record("llama.cpp", LLAMA_MODEL, LLAMA, sample=OFF_TASK, minutes=9)
    write_jsonl(t1p, "litert-lm_litert-community_Qwen3-1_7B_short-chat_late.jsonl", [late])
    summary_out = os.path.join(tmp, "summary")
    os.makedirs(summary_out)
    with patch.object(build_summary, "ROOT", tmp), patch.object(build_summary, "OUT", summary_out):
        csv_path, _ = build_summary.build_device()
    with open(csv_path, newline="") as fh:
        rows = list(csv.DictReader(fh))
    got = lambda d, rt: sorted(r["text_check"] for r in rows if r["campaign"] == f"results/raw/{os.path.basename(d)}"
                                and r["runtime"] == rt)
    ok(got(t1p, "llama.cpp") == ["", "FAIL:reply-off-task", "FAIL:reply-off-task", "FAIL:reply-off-task", "FAIL:reply-off-task"]
       and got(t1p, "mlx-swift") == ["PASS:screen"] * 4,
       f"the off-task cell's runs FAIL:reply-off-task, a run the file does not name '', the MLX runs PASS:screen "
       f"({got(t1p, 'llama.cpp')})")
    ok(got(t3p, "llama.cpp") == ["FAIL:reply-empty", "PASS:screen", "PASS:screen", "PASS:screen"]
       and got(t2a, "mlx-swift") == ["PASS:screen"] * 4 and got(t5p, "llama.cpp") == [""] * 4
       and got(unit, "litert-lm-gpu") == [""] * 3 and got(off_unit, "litert-lm-gpu") == [""] * 3,
       "one run of four FAIL; a dir whose file names no run, and the Android dirs (no file), read ''")
    ok(got(ip, "litert-lm") == ["PASS:screen"] * 4 and set((screen_of(ip) or {"cells": {}})["cells"]) == {
        f"litert-lm litert-community/Qwen3-1.7B short-chat ({OLD})", mlx},
       "an iPhone payload's text cells are screened alike (its FAIL on pin-drift aside): PASS:screen")

    print("--- usage")
    rc, res, out = run([os.path.join(raw, "no-such-dir")], history=hist)
    ok(rc == 2, f"a path that is not a directory: exit 2 (got {rc})")

    if _fails:
        print(f"\n{len(_fails)} failure(s); temp dir kept: {tmp}")
        return 1
    shutil.rmtree(tmp)
    print("\nselftest OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
