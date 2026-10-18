#!/usr/bin/env python3
"""Device- and network-free selftest of scripts/autopilot.py (`./bench autopilot --ddp <id>`, CI).

  BENCH_ANDROID_BIN_DIR=<dir with <pinned tag>/> python3 scripts/autopilot_selftest.py     # exit 0 = pass

1. the dry run through the real chain on this checkout (`--ddp akita-35 --dry-run`), with gcloud, adb,
   xcrun and curl first on PATH as traps: none of them runs, the commands it starts are the plan's
   `bench matrix … --dry-run` and scripts/regression_watch.py only; the step list, the doctor's DDP checks
   without the sign-in call, the plan and the job's `bench matrix` line, the post / table / red / requests
   lines and the command of the run; nothing written under logs/ or results/raw/. The engine files as
   android/ddp/selftest.py takes them (BENCH_ANDROID_BIN_DIR).
2. `bench matrix --ddp --dry-run` takes --project / --bucket from BENCH_DDP_PROJECT / BENCH_DDP_BUCKET.
3. the lab unit: schedule.json's entry for m1q-36, one made here for akita-35 (its key, the identifier the
   summary gives its rows, matrices/ddp-first-run.cells by default), an unknown id (exit 2); --runs's copy.
4. sittings against a fake `bench` in a temp git checkout (its own stub summary builder, table and red
   script, a switch whose page repo does not exist; a PATH without gtimeout, where a stand-in for GNU
   timeout is linked under that name): SESSION.json, the post's commit of the dir and the summary, the page
   skipped in one line, the table's cells of the unit, the red points, the pending retake and bisect request
   with its command and the line for a missing scripts/engine_bisect.py, the one screen's lines, exit 0;
   --no-commit (the check, no commit, exit 0); a HOLD (no commit, REVIEW.md, the rule and what a person
   does, exit 1); a second sitting the same day without --suffix (exit 2, the suffix named); no record
   (exit 5). No gcloud, adb or xcrun call in any of it.
"""
import contextlib
import datetime
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
TRAPPED = ("gcloud", "adb", "xcrun", "curl")
ON_TASK = ("On-device AI means the model runs on your phone itself instead of a cloud server, so it "
           "works offline, answers quickly and keeps your private data local on the device.")

# the lab unit's `bench` in the temp checkout: `matrix <cells> --ddp <id> --campaign <c> --dry-run` prints the
# plan's JSON lines as android/ddp/run_ddp.py does (dashboard_job.ddp_plan reads them); without --dry-run it
# leaves the campaign dir a DDP sitting leaves (ddp/session-1.json, a per-run logcat, one record per run with
# its raw log; FAKE_GEN generated tokens, FAKE_RECORDS=0 none) and rebuilds the summary, then exits
# FAKE_BENCH_RC. Every call is a line in bench-calls.jsonl, with the project and bucket it was handed.
FAKE_BENCH = r'''#!__PYTHON__
import json, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
a = sys.argv[1:]
with open(os.path.join(HERE, "bench-calls.jsonl"), "a") as fh:
    fh.write(json.dumps({"argv": a, "project": os.environ.get("BENCH_DDP_PROJECT"),
                         "bucket": os.environ.get("BENCH_DDP_BUCKET")}) + "\n")
if a[:1] != ["matrix"] or "--ddp" not in a:
    sys.exit(2)
cells = a[1] if os.path.isabs(a[1]) else os.path.join(HERE, a[1])
ddp_id, camp = a[a.index("--ddp") + 1], a[a.index("--campaign") + 1]
rows = []
for ln in open(cells):
    t = ln.split("#", 1)[0].split()
    if t[:2] == ["android", "litert-lm"]:
        o = dict(x.split("=", 1) for x in t[4:] if "=" in x)
        rows.append(("litert-lm-" + o.get("backend", "cpu"), t[2], t[3], int(o.get("runs", "3"))))
if "--dry-run" in a:
    for i, (arm, model, task, runs) in enumerate(rows, 1):
        print(json.dumps({"job": i, "session": 1, "cell": f"{arm} {model} {task}", "runs": runs}))
    print(json.dumps({"uploadCandidates": [], "uploadBytes": 0, "uncached": []}))
    print(json.dumps({"summary": {"device": ddp_id, "jobs": len(rows), "sessions": 1, "skipped": 0,
                                  "deviceMinutes": 9.0, "engine": "v0.18.0",
                                  "project": os.environ.get("BENCH_DDP_PROJECT"),
                                  "bucket": os.environ.get("BENCH_DDP_BUCKET")}}))
    sys.exit(0)
d = os.path.join(HERE, "results", "raw", camp + "-android")
app = os.path.join(d, "app-path-android")
os.makedirs(os.path.join(d, "ddp", "session-fake0001", "j01"))
os.makedirs(app)
job = {"displayName": "j01", "result": {"resultType": "PASSED"},
       "executionReports": [{"startTime": "2026-10-18T00:00:00Z", "endTime": "2026-10-18T00:06:00Z"}]}
json.dump({"name": "projects/p/locations/global/sessions/session-fake0001",
           "sessionReport": {"jobReports": [job]}}, open(os.path.join(d, "ddp", "session-1.json"), "w"))
open(os.path.join(d, "ddp", "session-fake0001", "j01", "run1_logcat.txt"), "w").write(
    "10-18 00:00:00 I litert: engine loaded\n")
if os.environ.get("FAKE_RECORDS") != "0":
    for arm, model, task, runs in rows:
        log = f"{arm}_{model.replace('/', '_')}_{task}_run.log"
        open(os.path.join(app, log), "w").write(
            "===ENGINE_OUTPUT===\ninput_prompt: What does on-device AI mean?\n" + __ON_TASK__
            + "\nBenchmarkInfo:\n  Prefill Turn 1: Processed 19 tokens\n")
        for i in range(runs):
            rec = {"schemaVersion": 1, "id": f"{camp}-{i}", "runtime": arm, "engineVersion": "v0.18.0",
                   "model": {"id": model}, "task": task, "timestamp": f"2026-10-18T00:0{i}:00Z",
                   "device": {"modelIdentifier": os.environ.get("FAKE_MODEL", "Fake 8a"), "systemName": "Android",
                              "ddp": {"deviceId": ddp_id, "serial": "FAKEUNIT1"}},
                   "parameters": {"maxTokens": 128},
                   "metrics": {"decodeTokensPerSecond": 20.0, "promptTokenCount": 19,
                               "generatedTokenCount": int(os.environ.get("FAKE_GEN", "128")),
                               "coldRun": True, "firstEver": i == 0},
                   "conditions": {"protocolFlags": [], "ddp": {"sessionId": "session-fake0001", "deviceId": ddp_id}},
                   "provenance": {"rawLog": log, "modelShaSource": "device"}}
            json.dump(rec, open(os.path.join(app, f"{arm}_run{i + 1}.json"), "w"))
subprocess.run([sys.executable, os.path.join(HERE, "scripts", "build_summary.py")], check=True)
sys.exit(int(os.environ.get("FAKE_BENCH_RC", "0")))
'''
# the temp checkout's summary builder: one row per record under results/raw/*/app-path-android/
STUB_BUILD_SUMMARY = r'''#!/usr/bin/env python3
import glob, json, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
rows = []
for p in sorted(glob.glob(os.path.join(ROOT, "results", "raw", "*", "app-path-android", "*.json"))):
    r = json.load(open(p))
    dev = r.get("device") or {}
    name = dev.get("modelIdentifier") + (f" (DDP {dev['ddp']['deviceId']})" if dev.get("ddp") else "")
    camp = "results/raw/" + os.path.basename(os.path.dirname(os.path.dirname(p)))
    rows.append(f"{camp},{name},android,{r['runtime']},{r['model']['id']},{r['task']}\n")
os.makedirs(os.path.join(ROOT, "results", "summary"), exist_ok=True)
with open(os.path.join(ROOT, "results", "summary", "device-runs.csv"), "w") as fh:
    fh.write("campaign,device,platform,runtime,model_id,task\n" + "".join(rows))
'''
# the temp checkout's table: one measured cell per (device, arm, model, task) of the summary
STUB_RENDER = r'''#!/usr/bin/env python3
import csv, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
rows = list(csv.DictReader(open(os.path.join(ROOT, "results", "summary", "device-runs.csv"))))
latest = {(r["device"], r["runtime"], r["model_id"], r["task"]): r["campaign"] for r in sorted(rows, key=lambda r: r["campaign"])}
cells = sorted(k + (c,) for k, c in latest.items())
os.makedirs(os.path.join(ROOT, ".dashboard"), exist_ok=True)
with open(os.path.join(ROOT, ".dashboard", "dashboard-v1.csv"), "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["platform", "device", "arm", "model", "model_id", "task", "status", "decode_tps", "n", "campaign"])
    for dev, arm, mid, task, camp in cells:
        w.writerow(["android", dev, arm, mid.split("/")[-1], mid, task, "measured", "20.0", "2", camp])
open(os.path.join(ROOT, "DASHBOARD.md"), "w").write("stub\n")
print(f"wrote DASHBOARD.md and .dashboard/dashboard-v1.{{csv,json}}: {len(cells)} measured of {len(cells)} device-cells")
'''
# the temp checkout's red script (the post's red segment runs the commit tree's copy with --respond; step 4
# runs this checkout's with --json --markdown): one red point of an attached phone; its argv in FAKE_RED_LOG
STUB_RED = r'''#!/usr/bin/env python3
import json, os, sys
a = sys.argv[1:]
open(os.environ["FAKE_RED_LOG"], "a").write(" ".join(x for x in a if not x.startswith("/")) + "\n")
camp = "2026-10-15-dashboard-v1-pixel8a-android"
print("regression: 2 series, 3 sittings (3 shown), red points decode 1 / prefill 0 / memory 0, regime changes 0")
print(f"  red  Pixel 8a | Gemma 4 E2B | short-chat | GPU | {camp} | decode -7.00 % vs "
      "2026-10-08-dashboard-v1-pixel8a-android | engine v0.16.0 -> v0.18.0 (changed)")
doc = {"meta": {"red": 1}, "red": [{"campaign": camp, "metric": "decode_tps", "pct": -7.0}], "compare": None,
       "respond": {"notes": ["no red point in this sitting (1 on the page)"]} if "--respond" in a else None}
if "--json" in a:
    json.dump(doc, open(a[a.index("--json") + 1], "w"))
if "--markdown" in a:
    open(a[a.index("--markdown") + 1], "w").write("regression: 1 red point\n")
'''
TRAP = "#!/bin/sh\necho \"$(basename \"$0\") $*\" >> '%s'\nexit 1\n"
# GNU timeout's stand-in: `timeout --kill-after=60 <seconds> <command…>` runs the command
FAKE_TIMEOUT = "#!/bin/sh\n[ \"${1#--kill-after=}\" != \"$1\" ] && shift\nshift\nexec \"$@\"\n"

_fails = []
_checks = [0]


def ok(cond, msg):
    _checks[0] += 1
    print(("  ok  " if cond else "  FAIL ") + msg)
    if not cond:
        _fails.append(msg)


def write(path, text, mode=0o644):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write(text)
    os.chmod(path, mode)


def git(cwd, *args):
    p = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True,
                       env={k: v for k, v in os.environ.items() if not k.startswith("GIT_")})
    if p.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} in {cwd}: {p.stdout}{p.stderr}")
    return p.stdout.strip()


def listing(*dirs):
    """Every file under the dirs with its size and mtime (what a dry run must leave as it was)."""
    out = set()
    for d in dirs:
        for base, _, files in os.walk(d):
            for f in files:
                p = os.path.join(base, f)
                try:
                    st = os.stat(p)
                except OSError:
                    continue
                out.add((p, st.st_size, st.st_mtime_ns))
    return out


@contextlib.contextmanager
def started_commands():
    """The commands this process starts (subprocess.Popen), as argv lists."""
    seen = []
    real = subprocess.Popen

    class Recording(real):
        def __init__(self, args, *a, **kw):
            seen.append([str(x) for x in (args if isinstance(args, (list, tuple)) else [args])])
            super().__init__(args, *a, **kw)

    subprocess.Popen = Recording
    try:
        yield seen
    finally:
        subprocess.Popen = real


def run_autopilot(ap, *argv):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        try:
            code = ap.main(list(argv))
        except SystemExit as e:
            code = e.code
    if ap.dj._LOG:
        ap.dj._LOG.close()
        ap.dj._LOG = None
    return code, buf.getvalue().splitlines()


def has(lines, text):
    return any(text in ln for ln in lines)


def main():
    tmp = os.path.realpath(tempfile.mkdtemp(prefix="autopilot-selftest-"))   # git names the top by realpath
    calls = os.path.join(tmp, "trap-calls.txt")
    traps = os.path.join(tmp, "traps")
    for t in TRAPPED:
        write(os.path.join(traps, t), TRAP % calls, 0o755)
    bin_dir = os.environ.get("BENCH_ANDROID_BIN_DIR")
    import autopilot as ap   # after the caller's BENCH_ANDROID_BIN_DIR is in the environment
    dj, dp = ap.dj, ap.dp
    path0 = os.environ.get("PATH", "")
    today = datetime.date.today().isoformat()

    print("--- 1. the dry run through the real chain on this checkout, network commands trapped")
    if not bin_dir:
        ok(False, "BENCH_ANDROID_BIN_DIR names the dir that holds <pinned tag>/ (as android/ddp/selftest.py takes it)")
    stand_in = None
    try:
        import huggingface_hub  # noqa: F401
    except ImportError:   # CI's runner: the doctor's check imports it (the plan, a subprocess, reports "uncached")
        stand_in = sys.modules["huggingface_hub"] = types.ModuleType("huggingface_hub")
        stand_in.__version__ = "stand-in (not installed here)"
    before = listing(os.path.join(ROOT, "logs"), os.path.join(ROOT, "results", "raw"))
    os.environ["PATH"] = traps + os.pathsep + path0
    with started_commands() as seen:
        code, lines = run_autopilot(ap, "--ddp", "akita-35", "--dry-run", "--project", "selftest-project",
                                    "--bucket", "gs://selftest-bucket")
    os.environ["PATH"] = path0
    if stand_in is not None:
        del sys.modules["huggingface_hub"]
    camp = f"{today}-dashboard-v1-pixel8a-ddp-akita-35"
    ok(code == 0, f"exit 0 (got {code}){'' if code == 0 else ': ' + ' | '.join(lines[-6:])}")
    ok(not os.path.exists(calls), "no gcloud, adb, xcrun or curl ran (the traps first on PATH recorded nothing)"
       + ("" if not os.path.exists(calls) else ": " + open(calls).read().strip()))
    progs = [c for c in seen]
    plan = [c for c in progs if c[:2] == [os.path.join(ROOT, "bench"), "matrix"]]
    watch = [c for c in progs if len(c) > 1 and c[1].endswith(os.path.join("scripts", "regression_watch.py"))]
    ok(len(progs) == 2 and len(plan) == 1 and plan[0][-1] == "--dry-run" and len(watch) == 1
       and not any(os.path.basename(c[0]) in TRAPPED for c in progs),
       f"two commands started: the plan's bench matrix … --dry-run and regression_watch.py ({progs})")
    ok(has(lines, "autopilot: steps: 1 sitting -> 2 post (scrub, check, local commit) -> 3 table -> 4 red points "
                  "-> 5 requests"), "the step list")
    ok(has(lines, "no schedule.json entry for akita-35: key pixel8a-ddp made here")
       and has(lines, "lab unit Pixel 8a (DDP akita-35), key pixel8a-ddp, cells matrices/ddp-first-run.cells"),
       "akita-35: the key made here, the default cells")
    ok(has(lines, "ddp_max_sessions") and has(lines, "is the bench host's nightly slot, not read by a run by hand"),
       "the switch: the cap read, ddp_weekly not")
    ok(has(lines, "doctor (check_ddp): ready") and has(lines, "SKIP  gcloud sign-in  not checked in a dry run"),
       "the doctor's DDP checks, the sign-in not run")
    ok(has(lines, "ddp plan: 1 jobs in 1 Device Run sessions on akita-35"), "the plan: 1 job, 1 session")
    ok(has(lines, f"bench matrix matrices/ddp-first-run.cells --ddp akita-35 --campaign {camp}"),
       "the job's bench matrix line, printed, not run")
    for label in ("=== autopilot: Pixel 8a (DDP akita-35), key pixel8a-ddp [dry-run: nothing billed, nothing written]",
                  "sitting   OK — results/raw/" + camp + "-android", "post      would run scripts/dashboard_post.py",
                  "          page ", "table     would render DASHBOARD.md", "red       regression:",
                  "requests  retakes pending",
                  "next      the run, billed to selftest-project: ./bench autopilot --ddp akita-35 --project "
                  "selftest-project --bucket gs://selftest-bucket"):
        ok(has(lines, label), f"the one screen: {label.strip()[:70]}")
    after = listing(os.path.join(ROOT, "logs"), os.path.join(ROOT, "results", "raw"))
    ok(after == before, f"nothing written under logs/ or results/raw/ ({len(after ^ before)} files differ)")

    print("--- 2. bench matrix --ddp --dry-run reads BENCH_DDP_PROJECT / BENCH_DDP_BUCKET")
    env = dict(os.environ, PATH=traps + os.pathsep + path0, BENCH_DDP_PROJECT="env-project",
               BENCH_DDP_BUCKET="gs://env-bucket")
    p = subprocess.run([os.path.join(ROOT, "bench"), "matrix", "matrices/ddp-first-run.cells", "--ddp", "akita-35",
                        "--dry-run"], cwd=ROOT, env=env, capture_output=True, text=True)
    summ = [json.loads(ln)["summary"] for ln in p.stdout.splitlines() if ln.startswith('{"summary"')]
    ok(p.returncode == 0 and summ and summ[0].get("project") == "env-project" and summ[0].get("bucket") == "gs://env-bucket",
       f"the plan's summary names the environment's project and bucket ({summ[0] if summ else p.stdout[-300:]})")
    p = subprocess.run([os.path.join(ROOT, "bench"), "matrix", "matrices/ddp-first-run.cells", "--ddp", "akita-35",
                        "--dry-run", "--project", "flag-project"], cwd=ROOT, env=env, capture_output=True, text=True)
    summ = [json.loads(ln)["summary"] for ln in p.stdout.splitlines() if ln.startswith('{"summary"')]
    ok(summ and summ[0].get("project") == "flag-project", "a --project flag wins over the environment")
    ok(not os.path.exists(calls), "no trapped command ran")

    print("--- 3. the lab unit, the default cells, --runs")
    key, unit, notes = ap.lab_unit("m1q-36")
    ok(key == "s26-ddp" and unit["cells"] == "matrices/dashboard-ddp-v1-android-s26.cells"
       and unit["identifier"] == "SM-S942U1 (DDP m1q-36)", f"m1q-36: schedule.json's entry s26-ddp ({key}, {unit['cells']})")
    key, unit, notes = ap.lab_unit("akita-35")
    ok(key == "pixel8a-ddp" and unit["identifier"] == "Pixel 8a (DDP akita-35)" and unit["cells"] == ap.FIRST_RUN_CELLS
       and unit["platform"] == "ddp" and unit["ddp_id"] == "akita-35",
       f"akita-35: key pixel8a-ddp, the summary's identifier, {ap.FIRST_RUN_CELLS} ({key}, {unit['identifier']})")
    code, lines = run_autopilot(ap, "--ddp", "no-such-id", "--dry-run")
    ok(code == 2 and has(lines, "not in android/ddp/devices.json"), f"an unknown id: exit 2 ({code})")

    print("--- 4. sittings against a fake bench in a temp git checkout")
    top = os.path.join(tmp, "bench")
    os.makedirs(top)
    git(top, "init", "-q", "-b", "main")
    for k, v in (("user.email", "selftest@example.com"), ("user.name", "selftest"), ("commit.gpgsign", "false")):
        git(top, "config", k, v)
    write(os.path.join(top, ".gitignore"), "/logs/\n/DASHBOARD.md\n/.dashboard/\n/bench-calls.jsonl\n")
    write(os.path.join(top, "bench"), FAKE_BENCH.replace("__PYTHON__", sys.executable)
          .replace("__ON_TASK__", repr(ON_TASK)), 0o755)
    write(os.path.join(top, "scripts", "build_summary.py"), STUB_BUILD_SUMMARY)
    write(os.path.join(top, "scripts", "render_dashboard.py"), STUB_RENDER)
    write(os.path.join(top, "scripts", "regression_watch.py"), STUB_RED)
    no_page = os.path.join(tmp, "no-page-repo")
    write(os.path.join(top, "ops", "autopilot", "switch.json"), json.dumps(
        {"push_bench": False, "push_page": False, "publish": False, "page_repo": no_page, "ddp_weekly": False,
         "ddp_max_sessions": 2}))
    write(os.path.join(top, "ops", "dashboard-v1", "schedule.json"), json.dumps({"devices": {
        "sam-ddp": {"platform": "ddp", "display": "Fake S (DDP fake-36)", "identifier": "SM-F (DDP fake-36)",
                    "ddp_id": "fake-36", "cells": "matrices/dashboard-ddp-v1-android-sam.cells"}}}))
    write(os.path.join(top, "android", "ddp", "devices.json"), json.dumps({
        "_doc": "fake catalog", "fake-35": {"scheduleKey": "pix", "display": "Fake 8a", "product": "fakeakita"},
        "fake-36": {"scheduleKey": "sam", "display": "Fake S", "product": "fakem1q"}}))
    row = "android litert-lm litert-community/Qwen3-1.7B short-chat backend=gpu file=Qwen3-1.7B.litertlm runs=2\n"
    write(os.path.join(top, "matrices", "ddp-first-run.cells"), "# first run\n" + row)
    write(os.path.join(top, "matrices", "dashboard-ddp-v1-android-sam.cells"), row)
    old = os.path.join(top, "results", "raw", "2026-10-01-ddp-fake-35-android", "app-path-android", "old.json")
    write(old, json.dumps({"runtime": "litert-lm-gpu", "model": {"id": "litert-community/Qwen3-1.7B"},
                           "task": "short-chat", "device": {"modelIdentifier": "Fake 8a",
                                                            "ddp": {"deviceId": "fake-35"}}}))
    subprocess.run([sys.executable, os.path.join(top, "scripts", "build_summary.py")], check=True)
    git(top, "add", "-A")
    git(top, "commit", "-q", "-m", "the temp checkout")
    head0 = git(top, "rev-parse", "HEAD")
    state = os.path.join(top, "logs", "dashboard-job")
    write(os.path.join(state, "retakes.json"), json.dumps({"schema": "autopilot-retakes.v1", "retakes": [
        {"id": "2026-10-15-pixel8a-gemma4e2b-gpu-short-chat", "status": "pending", "display": "Pixel 8a",
         "model": "Gemma 4 E2B", "backend": "GPU", "task": "short-chat"},
        {"id": "2026-10-01-pixel8a-old", "status": "done"}]}))
    bisect_cmd = ("python3 scripts/engine_bisect.py --good v0.16.0 --bad v0.18.0 --cells matrices/dashboard-text-v1.cells "
                  "--row 61 --verdict 'speed:decode<=-5%' --route ddp:akita-35")
    write(os.path.join(state, "bisect-requests.json"), json.dumps({"schema": "autopilot-requests.v1", "requests": [
        {"id": "2026-10-16-pixel8a-gemma4e2b-gpu-short-chat", "status": "pending", "good": "v0.16.0", "bad": "v0.18.0",
         "verdict": "speed:decode<=-5%", "route": "ddp:akita-35", "command": bisect_cmd,
         "draft": "logs/dashboard-job/regression-2026-10-16-gemma4e2b-gpu-short-chat.md"}]}))
    fakebin = os.path.join(tmp, "fakebin")
    write(os.path.join(fakebin, "timeout"), FAKE_TIMEOUT, 0o755)
    for t in TRAPPED:
        write(os.path.join(fakebin, t), TRAP % calls, 0o755)
    os.environ["FAKE_RED_LOG"] = red_log = os.path.join(tmp, "red-calls.txt")

    real = {n: getattr(dj, n) for n in ("ROOT", "LOG_DIR", "SWITCH", "load_rows", "ddp_doctor")}
    real_root = ap.ROOT
    summary_csv = os.path.join(top, "results", "summary", "device-runs.csv")
    ap.ROOT = dj.ROOT = top
    dj.LOG_DIR, dj.SWITCH = state, os.path.join(top, "ops", "autopilot", "switch.json")
    dj.load_rows = lambda path=None: real["load_rows"](summary_csv)
    dj.ddp_doctor = lambda: (0, "OK    gcloud  /fake/gcloud\nOK    gcloud sign-in\n")
    # no gtimeout here (the Homebrew name is not under /usr/bin or /bin): the run links the stand-in timeout
    os.environ["PATH"] = os.pathsep.join([fakebin, "/usr/bin", "/bin", "/usr/sbin", "/sbin"])
    try:
        code, lines = run_autopilot(ap, "--ddp", "fake-35", "--project", "p-1", "--bucket", "gs://b-1")
        c35 = f"{today}-dashboard-v1-pix-ddp-fake-35"
        rel35 = f"results/raw/{c35}-android"
        ok(code == 0, f"a PASS sitting: exit 0 (got {code}){'' if code == 0 else ': ' + ' | '.join(lines[-12:])}")
        ok(has(lines, "ddp_max_sessions 2 caps the plan") and has(lines, "its ddp_weekly (false) is the bench host's nightly slot"),
           "the switch's ddp_weekly false does not stop a run by hand; its cap is read")
        link = os.path.join(top, "logs", "autopilot", "bin", "gtimeout")
        ok(os.path.islink(link) and os.path.realpath(link) == os.path.realpath(os.path.join(fakebin, "timeout"))
           and has(lines, "gtimeout: none on PATH; GNU timeout"),
           "no gtimeout on PATH: the timeout found there linked as logs/autopilot/bin/gtimeout")
        bcalls = [json.loads(ln) for ln in open(os.path.join(top, "bench-calls.jsonl"))]
        ok(len(bcalls) == 2 and bcalls[0]["argv"][-1] == "--dry-run" and "--dry-run" not in bcalls[1]["argv"]
           and all(c["project"] == "p-1" and c["bucket"] == "gs://b-1" for c in bcalls),
           f"the plan, then the run: both bench matrix --ddp calls handed project p-1 and bucket gs://b-1 ({bcalls})")
        s = json.load(open(os.path.join(top, rel35, "SESSION.json")))
        ok(s.get("admitted") is True and s.get("device_key") == "pix-ddp" and s.get("device_identifier") == "Fake 8a (DDP fake-35)"
           and s.get("cells") == "matrices/ddp-first-run.cells" and s.get("cells_with_records") == 1,
           f"SESSION.json: admitted, key pix-ddp, the summary's identifier, the default cells, 1 of 1 cells ({s.get('reason')})")
        files = set(git(top, "show", "--name-only", "--format=", "HEAD").splitlines())
        ok(git(top, "rev-parse", "HEAD~1") == head0 and "results/summary/device-runs.csv" in files
           and all(f.startswith(rel35 + "/") or f == "results/summary/device-runs.csv" for f in files),
           f"the post's one commit: the sitting's dir and the summary ({len(files)} files)")
        sha = git(top, "rev-parse", "HEAD")
        for label in (f"=== autopilot: Fake 8a (DDP fake-35), key pix-ddp", f"sitting   OK — {rel35}",
                      "          Device Run sessions session-fake0001; 1 jobs", "check     PASS",
                      f"commit    {sha[:12]} on main (local), push: ", "summary   results/summary/device-runs.csv ",
                      f"page      skipped: no build.py in {no_page}",
                      "table     wrote DASHBOARD.md", "          this unit's cells: measured 1",
                      "red       regression: 2 series", "          1 red points, 0 of them this sitting's",
                      "requests  retakes pending 1, bisect requests pending 1",
                      "retake 2026-10-15-pixel8a-gemma4e2b-gpu-short-chat: Pixel 8a Gemma 4 E2B GPU short-chat",
                      "scripts/engine_bisect.py is not in this checkout",
                      f"next      bisect 2026-10-16-pixel8a-gemma4e2b-gpu-short-chat: {bisect_cmd}  (needs the tool, below)",
                      f"next      the commit is local: git show --stat {sha[:12]}",
                      f"log       logs/dashboard-job/{today}-pix-ddp.log"):
            ok(has(lines, label), f"the one screen: {label.strip()[:80]}")
        out = os.path.join(top, "logs", "autopilot", f"{c35}-android")
        ok(all(os.path.isfile(os.path.join(out, f)) for f in ("summary.txt", "post.txt", "red.json", "red.md")),
           f"logs/autopilot/{c35}-android/: summary.txt, post.txt, red.json, red.md")
        reds = open(red_log).read().splitlines()
        ok(any("--respond" in r for r in reds) and any("--json" in r and "--markdown" in r and "--respond" not in r
                                                         and "--compare" not in r for r in reds),
           "the post's red segment (--respond) and step 4 (--json --markdown, no --compare) both ran")
        ok(not os.path.exists(os.path.join(top, rel35, "REVIEW.md")), "no REVIEW.md in a committed dir")
        led = open(os.path.join(state, "ledger.tsv")).read().splitlines()
        ok(led[-1].split("\t")[2:5] == ["pix-ddp", rel35, "OK"], f"the job's ledger line ({led[-1].split(chr(9))[2:5]})")

        code, lines = run_autopilot(ap, "--ddp", "fake-35", "--project", "p-1", "--bucket", "gs://b-1")
        ok(code == 2 and has(lines, "holds a sitting already") and has(lines, "--suffix r2"),
           f"a second sitting the same day without --suffix: exit 2, the suffix named ({code})")

        head1 = git(top, "rev-parse", "HEAD")
        os.environ["FAKE_MODEL"] = "SM-F"
        code, lines = run_autopilot(ap, "--ddp", "fake-36", "--no-commit", "--suffix", "nc")
        os.environ.pop("FAKE_MODEL")
        rel36 = f"results/raw/{today}-dashboard-v1-sam-ddp-fake-36-nc-android"
        ok(code == 0 and git(top, "rev-parse", "HEAD") == head1 and os.path.isdir(os.path.join(top, rel36))
           and has(lines, "check     PASS") and has(lines, "commit    none (--no-commit: the post's dry run, nothing written)")
           and has(lines, f"commit once it passes: python3 scripts/dashboard_post.py {rel36}"),
           f"--no-commit on fake-36 (schedule.json's sam-ddp): the check PASS, no commit, exit 0 ({code})")
        s36 = json.load(open(os.path.join(top, rel36, "SESSION.json")))
        ok(s36.get("device_identifier") == "SM-F (DDP fake-36)" and s36.get("cells") == "matrices/dashboard-ddp-v1-android-sam.cells",
           "fake-36 ran as its schedule entry (identifier, cells)")

        os.environ["FAKE_GEN"] = "600"
        code, lines = run_autopilot(ap, "--ddp", "fake-35", "--suffix", "hold", "--runs", "1")
        os.environ.pop("FAKE_GEN")
        relh = f"results/raw/{c35}-hold-android"
        sh = json.load(open(os.path.join(top, relh, "SESSION.json")))
        recs = [f for f in os.listdir(os.path.join(top, relh, "app-path-android")) if f.endswith(".json")]
        ok(code == 1 and git(top, "rev-parse", "HEAD") == head1 and os.path.isfile(os.path.join(top, relh, "REVIEW.md"))
           and has(lines, "check     HOLD (rules: gen-budget)")
           and has(lines, "commit    none (held: a sitting is committed whole or not at all)")
           and has(lines, "next      gen-budget: " + dp.ACTION["gen-budget"])
           and has(lines, f"read {relh}/REVIEW.md"),
           f"a HOLD (generated past the budget): exit 1, no commit, REVIEW.md, the rule and what a person does ({code})")
        ok(len(recs) == 1 and sh.get("cells", "").startswith("logs/autopilot/cells/ddp-first-run-runs1.cells")
           and "runs=1" in open(os.path.join(top, sh["cells"])).read(),
           f"--runs 1: a copy of the cells file with runs=1, one record ({sh.get('cells')}, {len(recs)} records)")

        os.environ.update(FAKE_RECORDS="0", FAKE_BENCH_RC="1")
        code, lines = run_autopilot(ap, "--ddp", "fake-35", "--suffix", "none")
        for k in ("FAKE_RECORDS", "FAKE_BENCH_RC"):
            os.environ.pop(k)
        ok(code == dj.EXIT_DEVICE and has(lines, "sitting   DEVICE (no record") and has(lines, "next      fix what the reason says"),
           f"a sitting that wrote no record: exit 5, the reason and the next step ({code})")
        ok(not os.path.exists(calls), "no gcloud, adb, xcrun or curl call in any sitting")
    finally:
        os.environ["PATH"] = path0
        os.environ.pop("FAKE_RED_LOG", None)
        for n, v in real.items():
            setattr(dj, n, v)
        ap.ROOT = real_root

    if _fails:
        print(f"\n{len(_fails)} failure(s); temp dir kept: {tmp}")
        return 1
    shutil.rmtree(tmp)
    print(f"\nautopilot selftest OK ({_checks[0]} checks)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
