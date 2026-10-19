#!/usr/bin/env python3
"""Device-free selftest of scripts/session_check.py (CI).

Builds synthetic campaign dirs under a temp results/raw (no git work tree there, so every file
counts as one the commit would carry), with records stamped by the pin registry as committed, a
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
payload / anchor pair with one half missing; the exit codes; llama.cpp's pin per platform since the
2026-10-19 bump (registry_pin with the Mac and iPhone blocks, the since day and the previous tag;
a Mac sitting on either side of the Mac block's day, an iPhone sitting on the iPhones' block).

It passes whichever platform's LiteRT-LM pin lags the others (a release-triggered pass moves one
platform at a time): the generic cases carry a Mac llama.cpp cell stamped with the Mac's llama.cpp
pin (llama_pin_of, no LiteRT-LM pin read); protocol-off, the rule only LiteRT-LM cells meet, is built on LEADER, a
platform whose pin is the newest release, so its cells stamp the pin the registry holds them to and
the newest (neither engine-stamp nor pin-drift); the lab unit runs the GPU arm while the Android
pin is the newest, else the NPU side build, which no pin rule reads. Every case checks the dir's
live rules against the set it expects, and only the pin rules' own cases expect either pin rule.

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
PINS = committed("android/engine-pins.json")["android_pins"]
LITERT = LOCK["arms"]["litert-lm"]
LITERT_APPLE = LITERT["default_tag"]
# the Mac's LiteRT-LM pin (arms.litert-lm.mac, for a sitting on or after its since day; the 2099 dirs
# below are), else default_tag
MAC_BLOCK = LITERT.get("mac") or {}
LITERT_MAC = MAC_BLOCK.get("tag") or LITERT_APPLE
MLX = LOCK["arms"]["mlx-swift-lm"]["revision"]
LLAMA_ARM = LOCK["arms"]["llama.cpp"]
LLAMA_MODEL = "unsloth/Qwen3-1.7B-GGUF/Q4_K_M"


def release(tag):
    m = re.fullmatch(r"v?(\d+)\.(\d+)(?:\.(\d+))?", str(tag or ""))
    return tuple(int(g or 0) for g in m.groups()) if m else None


def day_of(text):
    try:
        return datetime.date.fromisoformat(str(text))
    except ValueError:
        return None


def applies(block, day):
    """A platform block counts from its since day (session_check.block_applies); day None = the 2099
    dirs, every since day past."""
    since = day_of(block.get("since"))
    return since is None or day is None or day >= since


def pin_of(platform, day=None):
    """(LiteRT-LM pin, where) a platform's records are held to on `day` (session_check.registry_pin):
    Android's the pins file, the Mac's and the iPhones' their lock block from its since day, else
    default_tag."""
    if platform == "android":
        return PINS.get("litert-lm"), "android_pins.litert-lm"
    block = LITERT.get(platform) or {}
    if block.get("tag") and applies(block, day):
        return block["tag"], f"arms.litert-lm.{platform}.tag"
    return LITERT_APPLE, "arms.litert-lm.default_tag"


def llama_pin_of(platform, day=None):
    """(llama.cpp pin, where) a platform's records are held to on `day` (session_check.registry_pin): the
    Mac's and the iPhones' arms.llama.cpp block when it applies, else arms.llama.cpp.tag (Android: the
    pins file) from the lock's since day and previous.tag before it."""
    block = (LLAMA_ARM.get(platform) or {}) if platform in ("mac", "ios") else {}
    if block.get("tag") and applies(block, day):
        return block["tag"], f"arms.llama.cpp.{platform}.tag"
    prev = (LLAMA_ARM.get("previous") or {}).get("tag")
    if prev and not applies(LLAMA_ARM, day):
        return prev, "arms.llama.cpp.previous.tag"
    if platform == "android":
        return PINS.get("llama.cpp"), "android_pins.llama.cpp"
    return LLAMA_ARM.get("tag"), "arms.llama.cpp.tag"


# the generic cases' llama.cpp cell is a Mac cell: it stamps the Mac's llama.cpp pin on the 2099 dirs
LLAMA = llama_pin_of("mac")[0]


def newest(day=None):
    """The newest LiteRT-LM release a platform's pin names on `day` (session_check.newest_litert, what
    pin-drift compares with): default_tag, each platform block from its since day (the android block
    at the higher of its tag and the pins file's), the pins file itself when the lock has no android
    block."""
    tags = [LITERT_APPLE]
    for k in ("mac", "ios", "android"):
        b = LITERT.get(k)
        if not isinstance(b, dict):
            continue
        t = b.get("tag") or (b.get("tag_built") if k == "android" else None)
        if k == "android" and release(PINS.get("litert-lm")) and release(PINS["litert-lm"]) > (release(t) or ()):
            t = PINS["litert-lm"]
        if release(t) and applies(b, day):
            tags.append(t)
    if not isinstance(LITERT.get("android"), dict):
        tags.append(PINS.get("litert-lm"))
    return max((t for t in tags if release(t)), key=release, default=None)


# the LiteRT-LM pins (default_tag, the lock's platform blocks with their since days, the Android pins
# file) and the newest release among them: what pin-drift reads for the 2099 dirs below, every since past
PIN_BLOCKS = [(b.get("tag") or b.get("tag_built"), b.get("since")) for k, b in LITERT.items()
              if k in ("mac", "android", "ios") and isinstance(b, dict)]
IOS_BLOCK = LITERT.get("ios") or {}
NEWEST = newest()
# a stamp older than NEWEST: the iPhones' default_tag while a platform's pin is ahead of it
OLD = LITERT_APPLE if release(LITERT_APPLE) < release(NEWEST) else "v0.0.1"


def leader():
    """(platform, day, pin, why) of LEADER, where the LiteRT-LM-only cases run: the first of the Mac,
    the iPhones and the Android lab unit whose LiteRT-LM pin is the newest release on the 2099 dirs;
    when none is (default_tag ahead of every platform: an Apple pin bump before the rebuilds), the
    day before the first since day, when the Apple platforms read default_tag. Platform None when
    neither finds one."""
    def pins(day):
        return ", ".join(f"{name} {pin_of(p, day)[0]}" for p, name in
                         (("mac", "Mac"), ("ios", "iPhone"), ("android", "Android")))

    first = min((d for d in (day_of(s) for _, s in PIN_BLOCKS) if d), default=None)
    for day in [None] + ([first - datetime.timedelta(days=1)] if first else []):
        top = newest(day)
        for plat in ("mac", "ios", "android"):
            pin, where = pin_of(plat, day)
            if release(pin) and release(pin) == release(top):
                when = "the 2099 dirs" if day is None else (
                    f"{day} (on the 2099 dirs no platform's pin is the newest release, {NEWEST})")
                return plat, day, pin, (f"{plat}: its pin {where} {pin} is the newest LiteRT-LM release a "
                                        f"platform's pin names on {when}; {pins(day)}, default_tag {LITERT_APPLE}")
    return None, None, None, (f"none: no platform's LiteRT-LM pin is the newest release {NEWEST}, on the "
                              f"2099 dirs ({pins(None)}, default_tag {LITERT_APPLE}) or the day before the "
                              f"first since day")


LEADER_PLATFORM, LEADER_DAY, LEADER_TAG, LEADER_WHY = leader()
# the lab unit's LiteRT-LM arm: the GPU arm, held to the Android pin, while that pin is the newest
# release; else the NPU side build (registry_pin: its own tag), which neither pin rule reads
DDP_ARM = "litert-lm-gpu" if release(PINS.get("litert-lm")) == release(NEWEST) else "litert-lm-npu"
DDP_WHY = (f"{DDP_ARM}: android_pins.litert-lm {PINS.get('litert-lm')} is the newest release" if DDP_ARM == "litert-lm-gpu"
           else f"{DDP_ARM}, the side build: android_pins.litert-lm {PINS.get('litert-lm')} is behind the newest "
                f"{NEWEST}, so a GPU cell FAILs pin-drift")
IOS_DEVICE = {"modelIdentifier": "iPhone18,2", "systemName": "iOS", "buildConfiguration": "Release"}
ON_TASK = ("On-device AI means the model runs on your phone itself instead of a cloud server, so it "
           "works offline, answers quickly and keeps your private data local on the device.")
OFF_TASK = ("Sure! Here is a short story about a dragon who learns to bake bread in a small village "
            "near the mountains, and the baker who teaches him patience and kindness every morning.")
# the pin rules: a case expects one only when it is the case's subject (clean's pin=True)
PIN_RULES = {"engine-stamp", "pin-drift"}

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


def ddp_record(i, runtime, engine, model="litert-community/Qwen3-1.7B", task="short-chat", prompt=19,
               log=None):
    """Run i of a lab unit's cell: cold, its CPU clocks capped from the start, the model hashed on the
    phone, no reply stored in the record (`log`, the engine log, carries a short-chat reply)."""
    rec = {"schemaVersion": 1, "id": str(uuid.uuid4()), "runtime": runtime, "engineVersion": engine,
           "model": {"id": model}, "task": task, "timestamp": now(i),
           "device": {"modelIdentifier": "SM-S942U1", "systemName": "Android",
                      "ddp": {"deviceId": "m1q-36", "serial": "FAKEUNIT1"}},
           "parameters": {"maxTokens": 128},
           "metrics": {"decodeTokensPerSecond": 20.0, "promptTokenCount": prompt, "generatedTokenCount": 128,
                       "coldRun": True, "firstEver": i == 0},
           "conditions": {"protocolFlags": ["cpu-capped", "cpu-capped-at-start"],
                          "ddp": {"sessionId": "session-fake0001", "deviceId": "m1q-36"}},
           "provenance": {"modelShaSource": "device"}}
    if log:
        rec["provenance"]["rawLog"] = log
    return rec


def leader_record(i, model="litert-community/Qwen3-1.7B", task="short-chat", prompt=19):
    """Run i of a LiteRT-LM cell on LEADER, stamping its pin: a Mac or an iPhone record (litert-lm), or
    a lab unit's (litert-lm-gpu)."""
    if LEADER_PLATFORM == "android":
        return ddp_record(i, "litert-lm-gpu", LEADER_TAG, model, task, prompt)
    rec = mac_record("litert-lm", model, LEADER_TAG, task=task, prompt=prompt, cold=(i == 0), minutes=i)
    if LEADER_PLATFORM == "ios":
        rec["device"] = dict(IOS_DEVICE)
    return rec


def write_jsonl(d, name, records):
    with open(os.path.join(d, name), "w") as fh:
        fh.write("".join(json.dumps(r) + "\n" for r in records))


def jsonl_of(records):
    """The .jsonl a cell's records go in, named as the Mac runner names it: <arm>_<model>_<task>, every
    '/' and '.' an '_' (llama_cpp_unsloth_Qwen3-1_7B-GGUF_Q4_K_M_short-chat.jsonl)."""
    r = records[0]
    return re.sub(r"[/.]", "_", f"{r['runtime']}_{r['model']['id']}_{r['task']}") + ".jsonl"


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
    """A Mac payload: the MLX cell and `records`, by default a llama.cpp cell (it reads no LiteRT-LM pin)."""
    d = campaign(raw, name)
    session(d, "payload", anchor, **over)
    write_jsonl(d, "mlx-swift_mlx-community_Qwen3-0_6B-4bit_short-chat.jsonl",
                cell("mlx-swift", "mlx-community/Qwen3-0.6B-4bit", MLX))
    records = records or cell("llama.cpp", LLAMA_MODEL, LLAMA)
    write_jsonl(d, jsonl_of(records), records)
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


def headline(rec, ctx=2048, gen=256):
    """A run as a headline cell's: a 256-token budget, `gen` tokens generated and the context forced to
    `ctx` (none when ctx is None) where its runner writes it: Android's conditions.contextTokens, the
    Apple runners' metrics.contextTokensConfigured (build_summary.context_tokens_of)."""
    rec["parameters"] = dict(rec["parameters"], maxTokens=256)
    rec["metrics"]["generatedTokenCount"] = gen
    if ctx is not None and rec["device"]["systemName"] == "Android":
        rec["conditions"]["contextTokens"] = ctx
    elif ctx is not None:
        rec["metrics"]["contextTokensConfigured"] = ctx
    return rec


def protocol_record(runtime, model, engine, i, task="native-benchmark-1024x256", ctx=2048, prompt=1024, gen=256):
    """A Mac record of a headline cell (headline)."""
    return headline(mac_record(runtime, model, engine, task=task, prompt=prompt, cold=(i == 0), minutes=i), ctx, gen)


def ddp_unit(raw, name, reply=ON_TASK, cells=None):
    """A lab unit's job sitting (dashboard_job.py ddp_sitting): three DDP_ARM short-chat runs over one
    engine log whose reply is `reply` (or `cells`, lists of ddp_record runs), a run logcat, the job's
    SESSION.json."""
    unit = campaign(raw, name)
    app = os.path.join(unit, "app-path-android")
    os.makedirs(app)
    if cells is None:
        log_name = f"{DDP_ARM}_litert-community_Qwen3-1.7B_short-chat_2099-07-01T00-00-00_run1.log"
        with open(os.path.join(app, log_name), "w") as fh:
            fh.write("===ENGINE_OUTPUT===\ninput_prompt: What does on-device AI mean?\n" + reply
                     + "\nBenchmarkInfo:\n  Prefill Turn 1: Processed 19 tokens\n")
        cells = [[ddp_record(i, DDP_ARM, PINS["litert-lm"], log=log_name) for i in range(3)]]
    for i, rec in enumerate(r for c in cells for r in c):
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
                   "cells_expected": len(cells), "cells_with_records": len(cells),
                   "ddp": {"id": "m1q-36", "sessions": ["session-fake0001"], "jobs": 1, "device_minutes": 9.5}},
                  fh, indent=1)
    return unit


def leader_sitting(raw, day, tag, cells):
    """A sitting on LEADER whose payload holds `cells` (lists of leader_record runs), dated `day` (or
    LEADER_DAY) and told from that day's other sittings by `tag`: a Mac or an iPhone anchor phase and
    payload (with the MLX cell), or a lab unit's job sitting (no anchor phase). (dirs, payload)."""
    day = LEADER_DAY.isoformat() if LEADER_DAY else day
    if LEADER_PLATFORM == "android":
        unit = ddp_unit(raw, f"{day}-dashboard-v1-s26-ddp-m1q-36-{tag}-android", cells=cells)
        return [unit], unit
    dev, token, anchor = {"mac": ("m4max", "mac", anchor_dir), "ios": ("iphone18pro", "ios", ios_anchor)}[LEADER_PLATFORM]
    a = anchor(raw, f"{day}-dashboard-v1-{dev}-{tag}-anchor-{token}")
    p = campaign(raw, f"{day}-dashboard-v1-{dev}-{tag}-{token}")
    session(p, "payload", os.path.basename(a))
    mlx = cell("mlx-swift", "mlx-community/Qwen3-0.6B-4bit", MLX)
    for c in [[dict(r, device=dict(IOS_DEVICE)) for r in mlx] if LEADER_PLATFORM == "ios" else mlx] + cells:
        write_jsonl(p, jsonl_of(c), c)
    return [a, p], p


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


def clean(r, expected, pin=False):
    """Whether a dir's live rules are no more than the case `expected`, read before its verdict counts:
    a pin rule beyond them is a fixture reading a LiteRT-LM pin it should not, and a case that is not
    about the pin rules (pin False) never expects one."""
    if not r:
        return False
    extra = (rules(r) - set(expected)) | (set() if pin else set(expected) & PIN_RULES)
    if extra & PIN_RULES:
        print(f"  stray {r['name']}: {sorted(extra & PIN_RULES)} beyond what the case expects "
              f"(LEADER {LEADER_PLATFORM}, {LEADER_TAG}; the newest release {NEWEST})")
    return not extra


def main():
    tmp = tempfile.mkdtemp(prefix="session-check-selftest-")
    raw = os.path.join(tmp, "results", "raw")
    os.makedirs(raw)
    hist = os.path.join(tmp, "device-runs.csv")
    with open(hist, "w") as fh:
        fh.write("campaign,platform,engine_version,runtime,model_id,task,prompt_tokens,text_check,model_file\n")
        for i in range(3):
            fh.write(f"results/raw/old-{i}-mac,mac,{LLAMA},llama.cpp,{LLAMA_MODEL},short-chat,19,,\n")
        # the same model id on another file read 9 tokens (a bundle whose template drops the user turn)
        for i in range(3):
            fh.write(f"results/raw/old-file-{i}-mac,mac,{LLAMA},llama.cpp,{LLAMA_MODEL},short-chat,9,,other-file.gguf\n")

    print(f"--- LEADER, the platform of the LiteRT-LM-only cases: {LEADER_WHY}")
    if LEADER_PLATFORM is None:
        ok(False, "no LEADER: the protocol-off cases are not built (a registry where no platform's "
                  "LiteRT-LM pin is the newest release FAILs every LiteRT-LM cell on pin-drift)")

    print("--- prompt history is keyed by the artifact file (2026-10-19: one model id, two files)")
    fa = anchor_dir(raw, "2099-01-03-dashboard-v1-m4max-anchor-mac")
    recs_new = cell("llama.cpp", LLAMA_MODEL, LLAMA)
    for r in recs_new:
        r.setdefault("model", {})["file"] = "new-file.gguf"
    fp = payload_dir(raw, "2099-01-03-dashboard-v1-m4max-mac", os.path.basename(fa), records=recs_new)
    rc, res, out = run([fa, fp], history=hist)
    r = res[os.path.basename(fp)]
    ok("prompt-tokens" not in rules(r) and clean(r, set()),
       f"a cell on a file the history has not seen reads its own prompt count, not another file's ({sorted(rules(r))})")
    recs_old = cell("llama.cpp", LLAMA_MODEL, LLAMA)
    for r in recs_old:
        r.setdefault("model", {})["file"] = "other-file.gguf"
    fp2 = payload_dir(raw, "2099-01-04-dashboard-v1-m4max-mac", os.path.basename(anchor_dir(raw, "2099-01-04-dashboard-v1-m4max-anchor-mac")), records=recs_old)
    rc, res, out = run([os.path.join(raw, "2099-01-04-dashboard-v1-m4max-anchor-mac"), fp2], history=hist)
    r = res[os.path.basename(fp2)]
    ok("prompt-tokens" in rules(r) and clean(r, {"prompt-tokens"}),
       f"the same file's history (9 tokens) holds a 19-token cell on it ({sorted(rules(r))})")

    print("--- PASS: a clean Mac anchor + payload pair, the prompt as the history reads it")
    a = anchor_dir(raw, "2099-01-01-dashboard-v1-m4max-anchor-mac")
    p = payload_dir(raw, "2099-01-01-dashboard-v1-m4max-mac", os.path.basename(a))
    rc, res, out = run([a, p], history=hist)
    ok(rc == 0, f"exit 0 when every dir passes (got {rc})")
    for n in (os.path.basename(a), os.path.basename(p)):
        ok(res.get(n, {}).get("verdict") == "PASS" and clean(res.get(n), set()),
           f"{n}: PASS ({sorted(rules(res.get(n, {'findings': []})))})")
    ok(res[os.path.basename(p)]["samples"] and "on-device" in res[os.path.basename(p)]["samples"][0]["text"].lower(),
       "a sample per cell is listed for a person to read")

    print("--- HOLD: one rule each")
    holds = {
        "partial": dict(cells_with_records=1),
        "verdict": dict(verdict="TIMEOUT", runner_exit=124),
        "prompt-tokens": dict(records=cell("llama.cpp", LLAMA_MODEL, LLAMA, prompt=8)),
        "engine-stamp": dict(records=cell("litert-lm", "litert-community/Qwen3-1.7B", "v9.9.9")),
        "gen-budget": dict(records=[dict(r, metrics=dict(r["metrics"], generatedTokenCount=579))
                                    for r in cell("llama.cpp", LLAMA_MODEL, LLAMA)]),
    }
    for i, (rule, kw) in enumerate(holds.items()):
        aa = anchor_dir(raw, f"2099-02-{i + 1:02d}-dashboard-v1-m4max-anchor-mac")
        pp = payload_dir(raw, f"2099-02-{i + 1:02d}-dashboard-v1-m4max-mac", os.path.basename(aa), **kw)
        rc, res, out = run([aa, pp], history=hist)
        r = res[os.path.basename(pp)]
        ok(r["verdict"] == "HOLD" and rule in rules(r) and clean(r, {rule}, pin=rule in PIN_RULES),
           f"{rule}: HOLD ({sorted(rules(r))})")
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
    ok({"failures", "flagged", "user-name"} <= rules(r) and r["verdict"] == "HOLD"
       and clean(r, {"failures", "flagged", "user-name"}),
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
    ok(rc == 0 and r["verdict"] == "PASS" and clean(r, set())
       and not any(f["rule"].startswith("reply-") for f in r["findings"])
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
    # a hand run (no SESSION.json) with the same off-task Mac cell: HOLD not-job as before, and the
    # screen written all the same (2026-10-19: the file comparison run by hand that enters the summary)
    hand = campaign(raw, "2099-09-01-mlx-file-compare-mac")
    hand_recs = cell("llama.cpp", LLAMA_MODEL, LLAMA, sample=OFF_TASK)
    write_jsonl(hand, jsonl_of(hand_recs), hand_recs)
    rc, res, out = run([hand], history=hist)
    r = res[os.path.basename(hand)]
    sh = (screen_of(hand) or {}).get("cells", {}).get(llama, {})
    ok(r["verdict"] == "HOLD" and rules(r) == {"not-job"} and sh.get("verdict") == "FAIL"
       and (sh.get("runs"), sh.get("runs_off")) == (4, 4)
       and f"screened text-fail: {llama} (reply-off-task): the page shows the cell as text-fail" in r["notes"],
       f"a hand run's Mac text cell is screened too: HOLD not-job only, text_screen.json FAIL 4 of 4, the note ({sorted(rules(r))})")
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
    ok(r["verdict"] == "PASS" and clean(r, set()) and not rules(r, live=False) & {"reply-off-task"}
       and any(n.startswith("screened") for n in r["notes"]),
       "an allow-list line for the screened rule finds no finding to excuse (the screen marks the runs)")

    print("--- the text screen: --no-text-screen writes nothing and judges as if it were written")
    loop_recs = cell("llama.cpp", LLAMA_MODEL, LLAMA, sample="on-device AI " * 40)
    t2a = anchor_dir(raw, "2099-09-02-dashboard-v1-m4max-anchor-mac")
    t2p = payload_dir(raw, "2099-09-02-dashboard-v1-m4max-mac", os.path.basename(t2a), records=loop_recs)
    rc, res, out = run([t2a, t2p], "--no-text-screen", history=hist)
    r = res[os.path.basename(t2p)]
    ok(rc == 0 and r["verdict"] == "PASS" and clean(r, set()) and screen_of(t2p) is None and screen_of(t2a) is None
       and r["text_screen"]["state"] == "would write"
       and f"screened text-fail: {llama} (reply-empty, reply-loop): the page shows the cell as text-fail "
           f"(text_screen.json not written: --no-text-screen)" in r["notes"] and "would write text_screen.json" in out,
       f"a looping cell under --no-text-screen: no file in either dir, the note says not written, PASS "
       f"({r['text_screen']['state']}, exit {rc})")
    rc, res, out = run([t2a, t2p], history=hist)
    loop_path = os.path.join(t2p, "text_screen.json")
    before = open(loop_path, "rb").read()
    write_jsonl(t2p, jsonl_of(loop_recs),     # the file payload_dir wrote them to
                cell("llama.cpp", LLAMA_MODEL, LLAMA))
    rc, res, out = run([t2a, t2p], "--no-text-screen", history=hist)
    r = res[os.path.basename(t2p)]
    ok(r["text_screen"]["state"] == "would rewrite" and open(loop_path, "rb").read() == before and r["verdict"] == "PASS"
       and clean(r, set()),
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
    ok(r["verdict"] == "PASS" and clean(r, set()) and (c.get("verdict"), c.get("runs"), c.get("runs_off")) == ("FAIL", 4, 1)
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
        ok(r["verdict"] == "HOLD" and rules(r) == {"reply-off-task"} and clean(r, {"reply-off-task"})
           and r["text_screen"]["state"].startswith("not written") and screen_of(t4p) is None,
           f"a dir the file cannot be written in: reply-off-task stays HOLD ({r['text_screen']['state'][:40]})")
    noid = cell("llama.cpp", LLAMA_MODEL, LLAMA, sample=OFF_TASK)
    for x in noid:
        x.pop("id")
    t5a = anchor_dir(raw, "2099-09-05-dashboard-v1-m4max-anchor-mac")
    t5p = payload_dir(raw, "2099-09-05-dashboard-v1-m4max-mac", os.path.basename(t5a), records=noid)
    rc, res, out = run([t5a, t5p], history=hist)
    r = res[os.path.basename(t5p)]
    ok(r["verdict"] == "HOLD" and rules(r) == {"reply-off-task"} and clean(r, {"reply-off-task"})
       and (screen_of(t5p) or {"cells": {}})["cells"].get(llama, {}).get("run_rules") == {},
       f"failed runs without a record id: the file names none of them, the cell keeps its HOLD ({sorted(rules(r))})")

    print("--- FAIL: one rule each")
    ra = anchor_dir(raw, "2099-04-01-dashboard-v1-m4max-anchor-mac")
    rp = payload_dir(raw, "2099-04-01-dashboard-v1-m4max-mac", os.path.basename(ra),
                     admitted=False, reason="anchor-collapse")
    nosess = campaign(raw, "2099-04-02-dashboard-v1-m4max-mac")
    nosess_recs = cell("llama.cpp", LLAMA_MODEL, LLAMA)
    write_jsonl(nosess, jsonl_of(nosess_recs), nosess_recs)
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
    ok(res[os.path.basename(rp)]["verdict"] == "FAIL" and "not-admitted" in rules(res[os.path.basename(rp)])
       and clean(res[os.path.basename(rp)], {"not-admitted"}),
       "refused at admission: FAIL not-admitted")
    ok(res[os.path.basename(nosess)]["verdict"] == "FAIL" and "session-missing" in rules(res[os.path.basename(nosess)])
       and clean(res[os.path.basename(nosess)], {"session-missing"}),
       "a dashboard dir the job made without SESSION.json (no job logs: judged by its name): FAIL session-missing")
    ok(res[os.path.basename(stopped)]["verdict"] == "FAIL" and "stopped-sitting" in rules(res[os.path.basename(stopped)])
       and clean(res[os.path.basename(stopped)], {"stopped-sitting"}),
       "a stopped sitting's quarantine: FAIL stopped-sitting")
    big = [f["detail"] for f in res[os.path.basename(sp)]["findings"] if f["rule"] == "big-file"]
    ok(len(big) == 2 and "secret" in rules(res[os.path.basename(sp)])
       and clean(res[os.path.basename(sp)], {"big-file", "secret"}),
       f"weights (.gguf), an ELF binary and a credential: FAIL big-file x2 + secret ({len(big)})")
    r = res[os.path.basename(ddp)]
    ok(r["kind"] == "DDP" and r["verdict"] == "FAIL" and "logcat-unscrubbed" in rules(r)
       and "not-job" in rules(r) and clean(r, {"logcat-unscrubbed", "not-job"}),
       f"a DDP dir with an execution-level logcat.txt: FAIL ({sorted(rules(r))})")
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
    ok(r["verdict"] == "PASS" and rules(r) == set() and rules(r, live=False) == {"failures", "flagged", "user-name"},
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
    ok("pair-incomplete" in rules(res[os.path.basename(lone)]) and res[os.path.basename(lone)]["verdict"] == "HOLD"
       and clean(res[os.path.basename(lone)], {"pair-incomplete"}),
       "an anchor phase no payload names: HOLD pair-incomplete")
    ok("pair-broken" in rules(res[os.path.basename(orphan)]) and res[os.path.basename(orphan)]["verdict"] == "FAIL"
       and clean(res[os.path.basename(orphan)], {"pair-broken"}),
       "a payload whose anchor phase is not on disk: FAIL pair-broken")
    ok("pair-incomplete" in rules(res[os.path.basename(xp)]) and clean(res[os.path.basename(xp)], {"pair-incomplete"}),
       "a payload checked without its (uncommitted) anchor phase: HOLD pair-incomplete")
    rc, res, out = run([xa, xp], history=hist)
    ok(rc == 0 and all(r["verdict"] == "PASS" and clean(r, set()) for r in res.values()),
       "the same two checked together: PASS")

    print(f"--- a lab unit's job sitting (DDP, SESSION.json of the job; {DDP_WHY}): the job-session rules, "
          f"no pair rules")
    unit = ddp_unit(raw, "2099-07-01-dashboard-v1-s26-ddp-m1q-36-android")
    rc, res, out = run([unit], history=hist)
    r = res[os.path.basename(unit)]
    ok(r["kind"] == "job payload (ddp)" and "not-job" not in rules(r) and r["verdict"] == "PASS" and clean(r, set())
       and rc == 0, f"kind job payload (ddp), no not-job, PASS ({r['kind']}, {sorted(rules(r))}, exit {rc})")
    off_unit = ddp_unit(raw, "2099-07-02-dashboard-v1-s26-ddp-m1q-36-android", reply=OFF_TASK)
    rc, res, out = run([off_unit], history=hist)
    r = res[os.path.basename(off_unit)]
    ok(r["verdict"] == "HOLD" and rules(r) == {"reply-off-task"} and clean(r, {"reply-off-task"})
       and r["text_screen"] is None and not os.path.exists(os.path.join(off_unit, "text_screen.json")),
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
    ok(r["verdict"] == "FAIL" and {"logcat-unscrubbed", "partial"} <= rules(r) and clean(r, {"logcat-unscrubbed", "partial"}),
       f"its execution-level logcat.txt still FAILs, a cell without records still holds ({sorted(rules(r))})")

    print("--- the Mac's LiteRT-LM pin: arms.litert-lm.mac from its since day, default_tag before it")
    if LITERT_MAC != LITERT_APPLE and MAC_BLOCK.get("since"):
        ma = anchor_dir(raw, "2099-06-01-dashboard-v1-m4max-anchor-mac")
        mp = payload_dir(raw, "2099-06-01-dashboard-v1-m4max-mac", os.path.basename(ma),
                         records=cell("litert-lm", "litert-community/Qwen3-1.7B", LITERT_APPLE))
        rc, res, out = run([ma, mp], history=hist)
        r = res[os.path.basename(mp)]
        stamp = [f["detail"] for f in r["findings"] if f["rule"] == "engine-stamp"]
        drift = release(LITERT_APPLE) < release(NEWEST)
        ok(stamp and "arms.litert-lm.mac.tag" in stamp[0] and LITERT_MAC in stamp[0]
           and r["verdict"] == ("FAIL" if drift else "HOLD")
           and clean(r, {"engine-stamp"} | ({"pin-drift"} if drift else set()), pin=True),
           f"a Mac sitting after since stamping default_tag {LITERT_APPLE}: engine-stamp against the "
           f"Mac block's {LITERT_MAC}, " + (f"and FAIL pin-drift ({NEWEST} is newer)" if drift else
                                            "no pin-drift (default_tag is the newest release)")
           + f" ({stamp[:1]}, {sorted(rules(r))})")
        day = datetime.date.fromisoformat(MAC_BLOCK["since"]) - datetime.timedelta(days=1)
        before = day.isoformat()
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
        ahead = release(newest(day)) > release(LITERT_APPLE)
        ok(r["verdict"] == ("FAIL" if ahead else "PASS") and "engine-stamp" not in rules(r)
           and clean(r, {"pin-drift"} if ahead else set(), pin=True),
           f"a Mac sitting the day before since ({before}) stamping default_tag {LITERT_APPLE}: no engine-stamp, "
           + (f"FAIL pin-drift ({newest(day)} pinned on another platform that day)" if ahead else
              "no pin-drift, PASS") + f" ({sorted(rules(r))})")
    else:
        print("  skip  the lock has no arms.litert-lm.mac block with another tag and a since day")

    print("--- pin-drift: a LiteRT-LM cell older than the newest release a platform's pin names that day FAILs")
    ia = ios_anchor(raw, "2099-08-01-dashboard-v1-iphone18pro-anchor-ios")
    ip = ios_payload(raw, "2099-08-01-dashboard-v1-iphone18pro-ios", ia, OLD)
    rc, res, out = run([ia, ip], history=hist)
    r = res[os.path.basename(ip)]
    drift = [f["detail"] for f in r["findings"] if f["rule"] == "pin-drift"]
    ios_pin = pin_of("ios")[0]
    also_stamp = str(OLD).lstrip("v") != str(ios_pin).lstrip("v")
    ok(r["verdict"] == "FAIL" and len(drift) == 1 and drift[0].startswith(f"ios litert-lm: stamps {OLD} x4;")
       and f": {NEWEST} (" in drift[0] and rc == 1
       and clean(r, {"pin-drift"} | ({"engine-stamp"} if also_stamp else set()), pin=True),
       f"an iPhone sitting stamping {OLD} with {NEWEST} pinned on another platform: FAIL pin-drift, one "
       f"finding per platform and arm" + (f", and engine-stamp (the iPhones' pin is {ios_pin})" if also_stamp else "")
       + f" ({drift[:1]})")
    ok(res[os.path.basename(ia)]["verdict"] == "PASS" and clean(res[os.path.basename(ia)], set()),
       "its anchor phase without a LiteRT-LM cell: PASS")
    newer = [s for t, s in PIN_BLOCKS if release(t) and release(t) > release(OLD)]
    android_block = any(k == "android" for k in LITERT)
    if OLD == LITERT_APPLE and newer and all(newer) and (android_block or release(PINS.get("litert-lm")) <= release(OLD)):
        before = (min(datetime.date.fromisoformat(s) for s in newer) - datetime.timedelta(days=1)).isoformat()
        ba = ios_anchor(raw, f"{before}-dashboard-v1-iphone18pro-anchor-ios")
        bp = ios_payload(raw, f"{before}-dashboard-v1-iphone18pro-ios", ba, OLD)
        rc, res, out = run([ba, bp], history=hist)
        r = res[os.path.basename(bp)]
        ok("pin-drift" not in rules(r) and r["verdict"] == "PASS" and clean(r, set()),
           f"the same the day before the first since of a newer pin ({before}): no pin-drift ({sorted(rules(r))})")
    else:
        print("  skip  no platform pin newer than default_tag with a since day")
    na = anchor_dir(raw, "2099-08-02-dashboard-v1-m4max-anchor-mac")
    np_ = payload_dir(raw, "2099-08-02-dashboard-v1-m4max-mac", os.path.basename(na),
                      records=cell("litert-lm", "litert-community/Qwen3-1.7B", "main@1dadd00c"))
    rc, res, out = run([na, np_], history=hist)
    r = res[os.path.basename(np_)]
    ok("pin-drift" not in rules(r) and r["verdict"] == "HOLD" and clean(r, {"engine-stamp"}, pin=True)
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
        ok(r["verdict"] == "PASS" and not ({"engine-stamp", "pin-drift"} & rules(r)) and clean(r, set()),
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
            ok(r["verdict"] == "FAIL" and "engine-stamp" not in rules(r) and "pin-drift" in rules(r)
               and clean(r, {"pin-drift"}, pin=True),
               f"the day before ({day}) stamping default_tag {LITERT_APPLE}: its registry pin, no engine-stamp; "
               f"a newer pin on another platform since {min(ahead)}: FAIL pin-drift ({sorted(rules(r))})")
        else:
            print("  skip  no other platform's newer pin applies the day before the ios block's since")
    else:
        print("  skip  the lock has no arms.litert-lm.ios block at the newest release with a since day")

    print("--- llama.cpp's pin per platform: the Mac and iPhone blocks, the lock's since day, previous.tag before it")
    import session_check  # noqa: E402
    l_pins = {"android_pins": {"llama.cpp": "b2"}}
    l_lock = {"arms": {"llama.cpp": {"tag": "b2", "since": "2099-03-02", "previous": {"tag": "b1"}}}}
    got = [session_check.registry_pin(plat, "llama.cpp", l_pins, l_lock, datetime.date.fromisoformat(d))[0]
           for plat in ("mac", "ios", "android") for d in ("2099-03-01", "2099-03-02")]
    ok(got == ["b1", "b2"] * 3, f"registry_pin: previous.tag the day before since, the pin from since on, on the "
                                f"Mac, the iPhone and Android (android_pins) (got {got})")
    l_blocks = {"arms": {"llama.cpp": dict(l_lock["arms"]["llama.cpp"], mac={"tag": "b2", "since": "2099-03-02"},
                                           ios={"tag": "b1"})}}
    got = {plat: session_check.registry_pin(plat, "llama.cpp", l_pins, l_blocks, datetime.date(2099, 3, 2))
           for plat in ("mac", "ios", "android")}
    ok(got["mac"] == ("b2", "environment.lock.json arms.llama.cpp.mac.tag (since 2099-03-02)")
       and got["ios"] == ("b1", "environment.lock.json arms.llama.cpp.ios.tag")
       and got["android"] == ("b2", "android/engine-pins.json android_pins.llama.cpp"),
       f"registry_pin with platform blocks: the Mac reads arms.llama.cpp.mac from its since day, the iPhones "
       f"arms.llama.cpp.ios (no since: always), Android android_pins (got {got})")
    ok(session_check.registry_pin("mac", "llama.cpp", l_pins, l_blocks, datetime.date(2099, 3, 1))[0] == "b1",
       "registry_pin: the day before the Mac block's since day reads previous.tag")
    l_old = {"arms": {"llama.cpp": {"tag": "b1"}}}
    ok(session_check.registry_pin("android", "llama.cpp", {"android_pins": {"llama.cpp": "b1"}}, l_old,
                                  datetime.date(2099, 3, 1))[0] == "b1"
       and session_check.registry_pin("mac", "llama.cpp", {}, l_old, datetime.date(2099, 3, 1))[0] == "b1",
       "registry_pin: a lock without since or previous reads the tag (the registry before 2026-10-19)")
    # the committed lock: Mac sittings on either side of the Mac block's day, iPhone sittings on the iPhones' block
    gguf = "unsloth/Qwen3-0.6B-GGUF/Q4_K_M"
    l_since = day_of((LLAMA_ARM.get("mac") or {}).get("since") or LLAMA_ARM.get("since"))
    l_prev = (LLAMA_ARM.get("previous") or {}).get("tag")
    if l_since and l_prev and l_prev != LLAMA:
        for i, (day, stamp) in enumerate(((l_since - datetime.timedelta(days=1), l_prev), (l_since, l_prev),
                                          (l_since, LLAMA))):
            pin, where = llama_pin_of("mac", day)
            want = stamp != pin
            la = anchor_dir(raw, f"{day.isoformat()}-dashboard-v1-m4max-llama{i}-anchor-mac")
            lp = payload_dir(raw, f"{day.isoformat()}-dashboard-v1-m4max-llama{i}-mac", os.path.basename(la),
                             records=cell("llama.cpp", gguf, stamp))
            rc, res, out = run([la, lp], history=hist)
            r = res[os.path.basename(lp)]
            stamp_f = [f["detail"] for f in r["findings"] if f["rule"] == "engine-stamp"
                       and f["detail"].startswith("mac llama.cpp:")]
            ok(r["verdict"] == ("HOLD" if want else "PASS") and clean(r, {"engine-stamp"} if want else set(), pin=True)
               and (not want or f"registry {pin} (environment.lock.json {where}" in stamp_f[0]),
               f"a Mac sitting on {day} stamping {stamp}: " + (f"engine-stamp against {where} {pin}" if want else
                                                              f"PASS on {where} {pin}") + f" ({stamp_f[:1]})")
        ios_pin, ios_where = llama_pin_of("ios", l_since)
        stamps = [ios_pin] + ([LLAMA_ARM["tag"]] if LLAMA_ARM.get("tag") != ios_pin else [])
        for i, stamp in enumerate(stamps):
            want = stamp != ios_pin
            ia_ = ios_anchor(raw, f"{l_since.isoformat()}-dashboard-v1-iphone18pro-llama{i}-anchor-ios")
            ip_ = campaign(raw, f"{l_since.isoformat()}-dashboard-v1-iphone18pro-llama{i}-ios")
            session(ip_, "payload", os.path.basename(ia_))
            for rt, model, eng in (("mlx-swift", "mlx-community/Qwen3-0.6B-4bit", MLX), ("llama.cpp", gguf, stamp)):
                c = [dict(r, device=dict(IOS_DEVICE)) for r in cell(rt, model, eng)]
                write_jsonl(ip_, jsonl_of(c), c)
            rc, res, out = run([ia_, ip_], history=hist)
            r = res[os.path.basename(ip_)]
            stamp_f = [f["detail"] for f in r["findings"] if f["rule"] == "engine-stamp"
                       and f["detail"].startswith("ios llama.cpp:")]
            ok(r["verdict"] == ("HOLD" if want else "PASS") and clean(r, {"engine-stamp"} if want else set(), pin=True)
               and (not want or f"registry {ios_pin} (environment.lock.json {ios_where}" in stamp_f[0]),
               f"an iPhone sitting on {l_since} stamping {stamp}: " + (f"engine-stamp against {ios_where} {ios_pin}"
                                                                     if want else f"PASS on {ios_where} {ios_pin}")
               + f" ({stamp_f[:1]})")
    else:
        print("  skip  the committed lock has no llama.cpp since day with a previous tag apart from the pin")

    print(f"--- protocol-off: a LiteRT-LM headline cell off the agreed protocol FAILs; other arms and tasks are "
          f"not read (the LiteRT-LM cells on LEADER, {LEADER_PLATFORM})")
    if LEADER_PLATFORM:
        native = [headline(leader_record(i, GEMMA, task="native-benchmark-1024x256", prompt=prompt), ctx, gen)
                  for i, (ctx, prompt, gen) in enumerate(((2048, 1024, 256), (1056, 1024, 256),
                                                          (2048, 1023, 256), (2048, 1024, 128)))]
        text1k = [headline(leader_record(i, GEMMA, task="long-context-1024-gen256", prompt=1024), ctx=672)
                  for i in range(4)]
        dirs, po = leader_sitting(raw, "2099-08-03", "po", [native, text1k])
        rc, res, out = run(dirs, history=hist)
        r = res[os.path.basename(po)]
        off = sorted(f["detail"] for f in r["findings"] if f["rule"] == "protocol-off")
        ok(r["verdict"] == "FAIL" and clean(r, {"protocol-off"}) and len(off) == 2
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
        ladder = [headline(leader_record(i, GEMMA, task="long-context-2048-gen256", prompt=1024), ctx=4096)
                  for i in range(4)]
        dirs, pl = leader_sitting(raw, "2099-08-05", "pl", [ladder])
        rc, res, out = run([qa, qp] + dirs, history=hist)
        r, rl = res[os.path.basename(qp)], res[os.path.basename(pl)]
        ok(r["verdict"] == "PASS" and rl["verdict"] == "PASS" and clean(r, set()) and clean(rl, set())
           and "protocol-off" not in rules(r, live=False) | rules(rl, live=False),
           f"MLX's 1K text cell at 2523, llama-bench's protocol cell without a context, the LiteRT-LM context "
           f"ladder at 4096 and the short-chat cells: no protocol-off, PASS ({sorted(rules(r, live=False))}, "
           f"{sorted(rules(rl, live=False))})")
    else:
        print("  skip  no LEADER")

    print("--- the team rules take no allow-list line")
    for rule in ("pin-drift", "protocol-off"):
        with open(allow, "w") as fh:
            fh.write(f"{rule}\t2099-*\t*\t0123abcd\tthe older release is fine here\n")
        rc, res, out = run([ia, ip], history=hist, allow=allow)
        ok(rc == 2 and "never allow-listed" in out, f"an allow-list line for {rule}: exit 2 (got {rc})")

    print("--- the text screen: build_summary reads it into text_check, per run by record id")
    late = mac_record("llama.cpp", LLAMA_MODEL, LLAMA, sample=OFF_TASK, minutes=9)
    write_jsonl(t1p, jsonl_of([late]).replace(".jsonl", "_late.jsonl"), [late])
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
       and got(unit, DDP_ARM) == [""] * 3 and got(off_unit, DDP_ARM) == [""] * 3,
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
