#!/usr/bin/env python3
"""Device-free selftest of scripts/session_check.py (CI).

Builds synthetic campaign dirs under a temp results/raw (no git work tree there, so every file
counts as one the commit would carry), with records stamped by the pin registry on disk, a
history csv handed in with --history and no job logs, and pins the verdicts: a clean Mac
anchor + payload pair PASS; one HOLD per rule it exercises (partial, TIMEOUT, FAILURES,
LEVEL, text check, prompt tokens, reply proxies, engine stamp, account name); one FAIL per rule
(refused at admission, no SESSION.json, stopped sitting, weights, engine binary, credential,
execution-level DDP logcat); an allow-list line turning a HOLD into a PASS and a malformed one
exiting 2; the payload / anchor pair with one half missing; the exit codes.

  python3 scripts/session_check_selftest.py     # exit 0 = pass
"""
import datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHECK = os.path.join(ROOT, "scripts", "session_check.py")
LOCK = json.load(open(os.path.join(ROOT, "environment.lock.json")))
PINS = json.load(open(os.path.join(ROOT, "android", "engine-pins.json")))["android_pins"]
LITERT_APPLE = LOCK["arms"]["litert-lm"]["default_tag"]
MLX = LOCK["arms"]["mlx-swift-lm"]["revision"]
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
                records or cell("litert-lm", "litert-community/Qwen3-1.7B", LITERT_APPLE))
    return d


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
            fh.write(f"results/raw/old-{i}-mac,mac,{LITERT_APPLE},litert-lm,litert-community/Qwen3-1.7B,"
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
        "prompt-tokens": dict(records=cell("litert-lm", "litert-community/Qwen3-1.7B", LITERT_APPLE, prompt=8)),
        "reply-off-task": dict(records=cell("litert-lm", "litert-community/Qwen3-1.7B", LITERT_APPLE,
                                            sample=OFF_TASK)),
        "reply-loop": dict(records=cell("litert-lm", "litert-community/Qwen3-1.7B", LITERT_APPLE,
                                        sample="on-device AI " * 40)),
        "engine-stamp": dict(records=cell("litert-lm", "litert-community/Qwen3-1.7B", "v9.9.9")),
        "gen-budget": dict(records=[dict(r, metrics=dict(r["metrics"], generatedTokenCount=579))
                                    for r in cell("litert-lm", "litert-community/Qwen3-1.7B", LITERT_APPLE)]),
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

    print("--- FAIL: one rule each")
    ra = anchor_dir(raw, "2099-04-01-dashboard-v1-m4max-anchor-mac")
    rp = payload_dir(raw, "2099-04-01-dashboard-v1-m4max-mac", os.path.basename(ra),
                     admitted=False, reason="anchor-collapse")
    nosess = campaign(raw, "2099-04-02-dashboard-v1-m4max-mac")
    write_jsonl(nosess, "litert-lm_litert-community_Qwen3-1_7B_short-chat.jsonl",
                cell("litert-lm", "litert-community/Qwen3-1.7B", LITERT_APPLE))
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
    ok(all(f["allowed_by"]["commit"] == "0123abcd" for f in r["findings"]), "each names the allowing commit")
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
