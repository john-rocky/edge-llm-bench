#!/usr/bin/env python3
"""Device-free, network-free selftest of the DDP backend (android/ddp/; design:
results/raw/2026-10-15-ddp-backend-dev/DESIGN.md).

  BENCH_ANDROID_BIN_DIR=<dir with v0.18.0/> ./android/ddp/selftest.py   # exit 0 = pass; temp kept on failure

1. plan (no subprocess, no network): matrices/dashboard-text-v1.cells on akita-35 (8 jobs, 1
   session), m1q-36 (16 jobs, 2 sessions) and caiman-35 (no schedule key); skip reasons with their
   key; each job's --command= = run_campaign.planned_command's engine command, --env / --mask apart;
   the request against the API contract's field names and limits; the engine files against the
   pins (one changed byte stops the plan); the CPU-cap wait per id (devices.json cpucapWaitSeconds:
   m1q-36 0, akita-35 the default 300); --project / --bucket in the plan and the request; bench
   matrix --ddp --dry-run with a gcloud on PATH that must never run, its summary line naming the
   project and bucket passed.
2. the wrapper: --print_shell = run_cell.sampler_shell for every planned job, the command arg
   whole or split at its spaces; a host run with stand-in device tools (runs, files, exit codes, a
   failing and a timed-out engine, the budget, bad args; always exit 0).
3. the attached-phone route's FAKESELF campaign (android/bench/selftest.py's fake device tool, round mode)
   for the record layout the DDP records must carry.
4. the billed path against a fake gcloud (a temp dir as the bucket) and a fake Device Run REST
   server: upload of the missing objects only, one POST per session, poll, session, pull, the pulled
   logcats scrubbed (no lab string left beside ddp/, the originals in ddp-raw/, ddp/scrub.json's
   counts), records; a 4xx body kept verbatim; the records' keys, witness, model sha, conditions.ddp,
   conditions.engineCache (built / loaded / GPU not-loaded / GPU loaded / absent), raw log, the 1K
   cell's two iterations and text check, firstEver, the uuid5 ids; --records-only writes the same
   files again; the witness of a changed sha.
5. scripts/build_summary.py into a temp dir: the device column of a DDP row, never the attached
   phone's; render_leaderboard's tree key and arm_row apart; render_dashboard's devices_for.
6. android/ddp/scrub.py: each rule on one line and what it keeps; the file form (the original copied
   once, a second scrub writing the same bytes and counts, bytes that are not UTF-8 kept); the CLI.
"""
import contextlib
import copy
import csv
import glob
import hashlib
import http.server
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import uuid
from argparse import Namespace
from unittest.mock import patch

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.join(ROOT, "android", "bench"))
sys.path.insert(0, HERE)
import run_campaign  # noqa: E402
import run_cell  # noqa: E402
import run_ddp  # noqa: E402
import record  # noqa: E402
import scrub  # noqa: E402

DASHBOARD = os.path.join(ROOT, "matrices", "dashboard-text-v1.cells")
FIXTURES = os.path.join(ROOT, "android", "bench", "testdata", "litert-lm")
SHORT_FIXTURE = os.path.join(FIXTURES, "pixel8a-v0.18.0-gpu-qwen3-0.6b-short-chat.console.txt")
LONG_FIXTURE = os.path.join(FIXTURES, "pixel8a-v0.18.0-gpu-qwen3-0.6b-long-context-1024-gen256.console.txt")
PROJECT = "fake-project"
BUCKET = "gs://fake-bucket"
# the request's field paths, from the SDK's devicerun v1alpha messages (SessionConfig, JobConfig,
# JobAction, AndroidNativeBinary, InputFile, GcsPath, AllocationConfig, DeviceConfig,
# DeviceRequirement, DeviceAction, AndroidPushFilesDeviceAction(+FileConfig),
# AndroidPullFilesDeviceAction, SessionConfigSessionOutputFileDirectoryConfig); labels are user keys
J = "sessionConfig.jobConfigs[]"
A = J + ".allocationConfig.deviceConfigs[].actions[]"
ALLOWED = {
    "sessionConfig", "sessionConfig.displayName", "sessionConfig.outputDirectoryConfig",
    "sessionConfig.outputDirectoryConfig.gcsOutputDirectory",
    "sessionConfig.outputDirectoryConfig.gcsOutputDirectory.path", "sessionConfig.jobConfigs",
    J + ".displayName", J + ".action", J + ".action.androidNativeBinary",
    J + ".action.androidNativeBinary.androidNativeBinary",
    J + ".action.androidNativeBinary.androidNativeBinary.gcsInputFile",
    J + ".action.androidNativeBinary.androidNativeBinary.gcsInputFile.path",
    J + ".action.androidNativeBinary.args", J + ".action.androidNativeBinary.executionTimeout",
    J + ".allocationConfig", J + ".allocationConfig.deviceConfigs",
    J + ".allocationConfig.deviceConfigs[].requirement", J + ".allocationConfig.deviceConfigs[].requirement.deviceId",
    J + ".allocationConfig.deviceConfigs[].actions",
    A + ".androidPushFiles", A + ".androidPushFiles.fileConfigs", A + ".androidPushFiles.fileConfigs[].sourceFile",
    A + ".androidPushFiles.fileConfigs[].sourceFile.gcsInputFile",
    A + ".androidPushFiles.fileConfigs[].sourceFile.gcsInputFile.path",
    A + ".androidPushFiles.fileConfigs[].destinationPath",
    A + ".androidPullFiles", A + ".androidPullFiles.paths", A + ".androidLogcat",
    J + ".labels", J + ".labels.*"}
DISPLAY_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")

_fails = []
_count = [0]


def ok(cond, msg):
    _count[0] += 1
    print(("  ok  " if cond else "  FAIL ") + msg)
    if not cond:
        _fails.append(msg)


def key_layout(rec):
    out = []
    for k, v in rec.items():
        out += [f"{k}.{sub}" for sub in v] if isinstance(v, dict) else [k]
    return out


def field_paths(obj, prefix=""):
    out = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            path = f"{prefix}.{k}" if prefix else k
            if prefix.endswith(".labels"):
                path = prefix + ".*"
            out.add(path)
            out |= field_paths(v, path)
    elif isinstance(obj, list):
        for v in obj:
            out |= field_paths(v, prefix + "[]") if isinstance(v, (dict, list)) else set()
    return out


def write(path, text, mode=0o644):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write(text)
    os.chmod(path, mode)


def plan_args(bin_dir, **kw):
    return Namespace(bin_dir=bin_dir, job_timeout=kw.get("job_timeout", 3600), jobs_per_session=8,
                     dry_run=kw.get("dry_run", True), bucket=BUCKET, project=PROJECT)


# ---------------------------------------------------------------- 1. plan

def check_plan(tmp, bin_dir, models):
    print("--- 1. plan: dashboard cells on akita-35 / m1q-36 / caiman-35 (no subprocess, no network, no HF cache)")
    plans = {}

    def fake_model(model_id, filename, dry_run):  # a selftest file per model name, never the HF cache
        path = models.get(filename)
        if path is None:
            path = models[filename] = os.path.join(tmp, "models", filename)
            write(path, f"weights of {filename}\n")
        return {"local": path, "bytes": os.path.getsize(path), "sha256": run_cell.sha256_file(path)}

    with patch.object(subprocess, "run", side_effect=AssertionError("subprocess in a plan")), \
            patch.object(subprocess, "Popen", side_effect=AssertionError("subprocess in a plan")), \
            patch.object(run_ddp, "model_file", fake_model):
        for dev in ("akita-35", "m1q-36", "caiman-35"):
            plans[dev] = run_ddp.plan(DASHBOARD, dev, f"selftest-{dev}-android", plan_args(bin_dir))
    want = {"akita-35": (8, 1, 10, 12, "pixel8a"), "m1q-36": (16, 2, 10, 4, "s26"), "caiman-35": (8, 1, 10, 0, None)}
    for dev, (jobs, sessions, rt, on, key) in want.items():
        p = plans[dev]
        reasons = [r for _, r, _ in p["skips"]]
        keyed = [(r, k) for _, r, k in p["skips"] if k]
        ok(len(p["jobs"]) == jobs and len(p["sessions"]) == sessions,
           f"{dev}: {len(p['jobs'])} jobs in {len(p['sessions'])} session(s) (want {jobs} / {sessions})")
        ok(reasons.count("runtime-not-wired-on-ddp") == rt and len(keyed) == on
           and all(k == key for _, k in keyed),
           f"{dev}: skips = {rt} llama.cpp rows + {on} exclude-on rows with key {key} "
           f"(got {reasons.count('runtime-not-wired-on-ddp')} + {len(keyed)}: {sorted({k for _, k in keyed})})")
    unk = [r for _, r, _ in plans["caiman-35"]["skips"] if r == "ddp-device-key-unknown"]
    ok(len(unk) == 12 and all(j["mask"] == "" for j in plans["caiman-35"]["jobs"]),
       f"caiman-35 (no schedule key): the 12 litert-lm rows with an exclude-on skip as ddp-device-key-unknown, "
       f"no mask (got {len(unk)})")
    sched = run_ddp.load_json(run_ddp.SCHEDULE)["devices"]
    bad_cmd, bad_req = [], []
    for dev in ("akita-35", "m1q-36"):
        p = plans[dev]
        mask = sched[p["device"]["scheduleKey"]]["cpu_mask"]
        for j in p["jobs"]:
            full, binname, _ = run_campaign.planned_command(j["cell"])
            env = run_cell.launch_env(None, j["backend"], j["runtime"])
            affinity = f"taskset {run_cell.CPU_MASK} " if run_cell.CPU_MASK else ""
            core = full[len(f"cd {run_cell.DEV_DIR} && {env} {affinity}"):]
            a = dict(x[2:].split("=", 1) for x in j["args"])
            if (a["command"] != core or a["env"] != env or a["binname"] != binname
                    or a["mask"] != (mask or "none") or a["dir"] != run_cell.DEV_DIR):
                bad_cmd.append((dev, j["index"], a["command"], core))
        for s in p["sessions"]:
            body = s["request"]
            extra = field_paths(body) - ALLOWED
            for jc in body["sessionConfig"]["jobConfigs"]:
                nb = jc["action"]["androidNativeBinary"]
                acts = jc["allocationConfig"]["deviceConfigs"][0]["actions"]
                push = acts[0]["androidPushFiles"]["fileConfigs"]
                pull = acts[1]["androidPullFiles"]["paths"]
                t = re.fullmatch(r"(\d+)s", nb["executionTimeout"])
                labels = jc["labels"]
                problems = [w for w, bad in (
                    ("fields", extra), ("push>50", len(push) > 50), ("pull!=1", pull != [run_ddp.OUTPUT_DIR]),
                    ("labels>16", len(labels) > 16),
                    ("label sizes", any(len(k.encode()) > 32 or len(v.encode()) > 1024 for k, v in labels.items())),
                    ("displayName", len(jc["displayName"].encode()) > 63 or not DISPLAY_NAME.match(jc["displayName"])),
                    ("session displayName", len(body["sessionConfig"]["displayName"].encode()) > 63
                     or not DISPLAY_NAME.match(body["sessionConfig"]["displayName"])),
                    ("executionTimeout", not t or not 60 <= int(t.group(1)) <= 10800),
                    ("args>100", len(nb["args"]) > 100),
                    ("one action per type", len({k for act in acts for k in act}) != len(acts)),
                    ("command last", not nb["args"][-1].startswith("--command="))) if bad]
                if problems:
                    bad_req.append((dev, jc["displayName"], problems))
    ok(not bad_cmd, f"every job's --command= = planned_command's engine command, --env / --binname / --mask / --dir "
                    f"apart (mask = the schedule key's cpu_mask) ({bad_cmd[:1]})")
    ok(not bad_req, f"requests: contract field names only, push <= 50, pull = [{run_ddp.OUTPUT_DIR}], labels <= 16 "
                    f"(key <= 32 B, value <= 1024 B), displayName <= 63 B and the regex, executionTimeout '<n>s' in "
                    f"60..10800, args <= 100, one action per type, --command= last ({bad_req[:1]})")
    j1 = plans["akita-35"]["jobs"][0]
    ok(len(j1["push"]) == 11 and [f["kind"] for f in j1["push"]].count("engine") == 9
       and j1["wrapper"]["object"].endswith("/ddp_cell.sh") and all(f["sha256"] in f["object"] for f in j1["push"]),
       "push = 9 engine files + model + prompt, content-addressed objects; the wrapper is the job's binary")
    pins = run_cell.load_pins()["litert-lm"]["v0.18.0"]
    want_sha = {"litert_lm_main": pins["litert_lm_main_sha256"],
                "litert_lm_advanced_main": pins["litert_lm_advanced_main_sha256"], **pins["so_files"]}
    got_sha = {f["name"]: f["sha256"] for f in j1["push"] if f["kind"] == "engine"}
    ok(got_sha == want_sha, "the 9 engine files' sha256 = android/engine-pins.json litert-lm v0.18.0")
    # D14: the CPU-cap wait is the id's cpucapWaitSeconds (m1q-36 0), else the attached-phone route's 300 s
    default_wait = 300 if "CPUCAP_WAIT" not in os.environ else run_cell.CPUCAP_WAIT
    waits = {dev: sorted({a for j in plans[dev]["jobs"] for a in j["args"] if a.startswith("--cpucap_wait=")})
             for dev in plans}
    ok(waits == {"m1q-36": ["--cpucap_wait=0"], "akita-35": [f"--cpucap_wait={default_wait}"],
                 "caiman-35": [f"--cpucap_wait={default_wait}"]}
       and plans["m1q-36"]["device"]["cpucapWait"] == 0
       and f"--thermal_wait={run_campaign.THERMAL_WAIT}" in plans["m1q-36"]["jobs"][0]["args"],
       f"cpu-cap wait per id: m1q-36 --cpucap_wait=0 (devices.json), akita-35 / caiman-35 {default_wait} (absent key); "
       f"thermal gate unchanged ({waits})")
    bad_wait = {"_doc": "", "x-1": {"scheduleKey": None, "display": "X", "product": "x", "cpucapWaitSeconds": -1}}
    devices_json = os.path.join(tmp, "devices-bad.json")
    json.dump(bad_wait, open(devices_json, "w"))
    with patch.object(run_ddp, "DEVICES", devices_json):
        try:
            run_ddp.device_entry("x-1")
            refused = None
        except SystemExit as exc:
            refused = str(exc)
    ok(refused is not None and "cpucapWaitSeconds" in refused, f"a negative cpucapWaitSeconds stops the plan ({refused})")
    # --project / --bucket: in the plan and in every path of the request
    paths = [v for s in plans["akita-35"]["sessions"] for v in re.findall(r'"path": "([^"]+)"', json.dumps(s["request"]))]
    ok(plans["akita-35"]["project"] == PROJECT and plans["akita-35"]["bucket"] == BUCKET and paths
       and all(v.startswith(BUCKET + "/automation/") for v in paths),
       f"the plan carries --project / --bucket; every request path is under {BUCKET}/automation/ ({len(paths)} paths)")
    # one changed byte in one engine file stops the plan before anything else
    bad_bin = os.path.join(tmp, "bad-bin")
    shutil.copytree(os.path.join(bin_dir, "v0.18.0"), os.path.join(bad_bin, "v0.18.0"))
    victim = os.path.join(bad_bin, "v0.18.0", "libLiteRtOpenClAccelerator.so")
    os.chmod(victim, 0o644)
    with open(victim, "r+b") as fh:
        fh.seek(1000)
        b = fh.read(1)
        fh.seek(1000)
        fh.write(bytes([b[0] ^ 1]))
    try:
        run_ddp.plan(DASHBOARD, "akita-35", "selftest-bad", plan_args(bad_bin))
        stopped = None
    except SystemExit as exc:
        stopped = str(exc)
    ok(stopped is not None and "libLiteRtOpenClAccelerator.so" in stopped and "is not the pin's" in stopped,
       f"an engine file one byte off its pin stops the plan, naming it ({stopped})")
    shutil.rmtree(bad_bin)
    return plans


def check_bench_dry_run(tmp, bin_dir):
    print("--- 1b. bench matrix --ddp --dry-run: no gcloud, other platforms skipped, no summary")
    trap = os.path.join(tmp, "trap-bin")
    marker = os.path.join(tmp, "gcloud-was-called")
    write(os.path.join(trap, "gcloud"), f"#!/bin/sh\necho \"$@\" >> {marker}\nexit 1\n", 0o755)
    env = dict(os.environ, PATH=trap + os.pathsep + "/usr/bin:/bin", BENCH_ANDROID_BIN_DIR=bin_dir)
    summary_csv = os.path.join(ROOT, "results", "summary", "device-runs.csv")
    before = os.path.getmtime(summary_csv) if os.path.exists(summary_csv) else None
    r = subprocess.run([sys.executable, os.path.join(ROOT, "bench"), "matrix", DASHBOARD, "--ddp", "akita-35",
                        "--dry-run", "--campaign", "selftest-dry"], env=env, capture_output=True, text=True)
    after = os.path.getmtime(summary_csv) if os.path.exists(summary_csv) else None
    ok(r.returncode == 0 and "skip: ios rows are not run on DDP" in r.stdout
       and "skip: mac rows are not run on DDP" in r.stdout and '"jobs": 8' in r.stdout,
       f"bench --ddp akita-35 --dry-run: rc 0, ios / mac rows skipped, 8 jobs (rc {r.returncode}, {r.stderr[-300:]!r})")
    ok(not os.path.exists(marker), "the dry run never ran gcloud (a gcloud first on PATH that records calls)")
    ok(before == after, "the dry run rebuilt no summary")
    r2 = subprocess.run([sys.executable, os.path.join(ROOT, "bench"), "matrix", DASHBOARD, "--dry-run"],
                        env=env, capture_output=True, text=True)
    ok(r2.returncode == 2 and "--dry-run is for --ddp only" in r2.stderr,
       f"bench matrix --dry-run without --ddp refuses (rc {r2.returncode})")
    # another team's project and bucket: through bench to run_ddp, in the summary line and the request
    r3 = subprocess.run([sys.executable, os.path.join(ROOT, "bench"), "matrix", DASHBOARD, "--ddp", "m1q-36",
                         "--dry-run", "--campaign", "selftest-dry-other", "--project", "other-team-project",
                         "--bucket", "gs://other-team-bucket/"], env=env, capture_output=True, text=True)
    summary = next((json.loads(x)["summary"] for x in r3.stdout.splitlines() if x.startswith('{"summary"')), {})
    sessions = [json.loads(x) for x in r3.stdout.splitlines() if x.startswith('{"session"')]
    ok(r3.returncode == 0 and summary.get("project") == "other-team-project"
       and summary.get("bucket") == "gs://other-team-bucket" and summary.get("cpucapWaitSeconds") == 0
       and sessions and all('"gs://other-team-bucket/automation/' in json.dumps(s["request"])
                            and "litert-edge-portal" not in json.dumps(s["request"]) for s in sessions),
       f"bench --ddp m1q-36 --dry-run --project other-team-project --bucket gs://other-team-bucket/: the summary line "
       f"names both (trailing / dropped) and cpucapWaitSeconds 0, every request path in that bucket "
       f"(rc {r3.returncode}, {summary})")
    r4 = subprocess.run([sys.executable, os.path.join(ROOT, "bench"), "matrix", DASHBOARD, "--project", "x"],
                        env=env, capture_output=True, text=True)
    r5 = subprocess.run([sys.executable, os.path.join(ROOT, "bench"), "matrix", DASHBOARD, "--ddp", "akita-35",
                         "--dry-run", "--bucket", "other-team-bucket"], env=env, capture_output=True, text=True)
    ok(r4.returncode == 2 and "for --ddp only" in r4.stderr and r5.returncode != 0 and "gs://<bucket>" in r5.stderr,
       f"--project without --ddp refuses (rc {r4.returncode}); a --bucket without gs:// refuses (rc {r5.returncode})")
    ok(not os.path.exists(marker), "none of the dry runs ran gcloud")


# ---------------------------------------------------------------- 2. the wrapper

def check_wrapper_strings(plans):
    print("--- 2. ddp_cell.sh --print_shell = run_cell.sampler_shell, every planned job, arg whole or split")
    bad = []
    n = 0
    for dev in ("akita-35", "m1q-36"):
        for j in plans[dev]["jobs"]:
            a = dict(x[2:].split("=", 1) for x in j["args"])
            want = run_cell.sampler_shell(a["command"], a["binname"], f"{run_cell.DEV_DIR}/run_out.txt", a["env"],
                                          "" if a["mask"] == "none" else f"taskset {a['mask']} ",
                                          f"timeout -k 5 {a['timeout']} ")
            for split in (False, True):
                argv = j["args"][:-1] + (j["args"][-1].split(" ") if split else [j["args"][-1]])
                got = subprocess.run(["sh", run_ddp.WRAPPER, "--print_shell=1"] + argv,
                                     capture_output=True, text=True).stdout.rstrip("\n")
                n += 1
                if got != want:
                    bad.append((dev, j["displayName"], split))
    ok(not bad and n == 48, f"{n} wrapper strings byte-equal to sampler_shell (differ: {bad[:2]})")


FAKE_DEVICE_TOOLS = {
    "getprop": """#!/bin/sh
case "$1" in
  ro.product.model) echo "Pixel 8a" ;;
  ro.product.device) echo akita ;;
  ro.build.fingerprint) echo "google/akita/akita:16/FAKE.251005.001/1:user/release-keys" ;;
  ro.serialno) echo HOSTRUN0001 ;;
  ro.build.version.release) echo 16 ;;
  ro.build.version.security_patch) echo 2026-05-05 ;;
  ro.soc.model) echo "Tensor G3" ;;
esac
""",
    "dumpsys": """#!/bin/sh
case "$1" in
  thermalservice) echo "Thermal Status: ${FAKE_THERMAL:-0}" ;;
  battery) printf '  level: 100\\n  status: 2\\n  USB powered: true\\n  temperature: 316\\n' ;;
  power) echo "  mWakefulness=Awake" ;;
esac
""",
    "settings": "#!/bin/sh\necho 0\n",
    "logcat": "#!/bin/sh\n[ \"$1\" = -d ] && echo \"10-15 00:00:00.000 1 1 I fake: logcat line\"\nexit 0\n",
    "taskset": "#!/bin/sh\nshift\nexec \"$@\"\n",
    "timeout": """#!/usr/bin/env python3
import subprocess, sys
a = sys.argv[1:]
grace = 1.0
if a[0] == "-k":
    grace, a = float(a[1]), a[2:]
p = subprocess.Popen(a[1:])
try:
    sys.exit(p.wait(timeout=float(a[0])))
except subprocess.TimeoutExpired:
    p.terminate()
    try:
        p.wait(timeout=grace)
    except subprocess.TimeoutExpired:
        p.kill()
        p.wait()
    sys.exit(124)
""",
    "sha256sum": """#!/usr/bin/env python3
import hashlib, os, sys
rc = 0
for f in sys.argv[1:]:
    if os.path.isfile(f):
        print(hashlib.sha256(open(f, "rb").read()).hexdigest() + "  " + f)
    else:
        sys.stderr.write("sha256sum: " + f + ": No such file or directory\\n")
        rc = 1
sys.exit(rc)
""",
}
FAKE_ENGINE = """#!/bin/sh
sleep "${FAKE_ENGINE_SLEEP:-1.2}"
cat "$FAKE_ENGINE_OUT"
exit "${FAKE_ENGINE_RC:-0}"
"""


def engine_lines(fixture):
    """A fixture's engine output: the text between ===ENGINE_OUTPUT=== and EXIT_CODE=."""
    text = open(fixture).read()
    text = text.split("===ENGINE_OUTPUT===\n", 1)[1]
    return text[:text.rindex("EXIT_CODE=")]


def check_wrapper_host_run(tmp):
    print("--- 2b. ddp_cell.sh on this host with stand-in device tools")
    tools = os.path.join(tmp, "host-tools")
    for name, text in FAKE_DEVICE_TOOLS.items():
        write(os.path.join(tools, name), text, 0o755)
    dev = os.path.join(tmp, "host-dev")
    write(os.path.join(dev, "litert_lm_main"), FAKE_ENGINE, 0o644)
    write(os.path.join(dev, "litert_lm_advanced_main"), "not run\n")
    write(os.path.join(dev, "libFake.so"), "fake lib\n")
    write(os.path.join(dev, "models", "m.litertlm"), "weights\n")
    write(os.path.join(dev, "prompts", "short-chat.txt"), "Explain what on-device AI means in simple terms.\n")
    engine_out = os.path.join(tmp, "engine-out.txt")
    write(engine_out, engine_lines(SHORT_FIXTURE))
    env = dict(os.environ, PATH=tools + os.pathsep + os.environ.get("PATH", ""), FAKE_ENGINE_OUT=engine_out)
    command = (f"./litert_lm_main --backend=cpu --model_path={dev}/models/m.litertlm "
               f"--input_prompt_file={dev}/prompts/short-chat.txt --max_output_tokens=128 --async=false")

    def run(out, extra_env=None, command=command, **kw):
        a = {"runs": 2, "cooldown": 0, "mask": "f0", "env": "LD_LIBRARY_PATH=.", "binname": "litert_lm_main",
             "dir": dev, "output_dir": out, "timeout": 20, "thermal_wait": 2, "cpucap_wait": 1, "budget": 0,
             "cell": "host-cell", **kw}
        argv = [f"--{k}={v}" for k, v in a.items()] + ([f"--command={command}"] if command is not None else [])
        return subprocess.run(["sh", run_ddp.WRAPPER] + argv, env=dict(env, **(extra_env or {})),
                              capture_output=True, text=True, timeout=180)

    out = os.path.join(dev, "ddp-out")
    r = run(out)
    prov = record.parse_provenance(open(os.path.join(out, "provenance.txt")).read()) \
        if os.path.exists(os.path.join(out, "provenance.txt")) else {"props": {}, "args": [], "sha": {}}
    logs = [open(os.path.join(out, f"run{i}.log")).read() if os.path.exists(os.path.join(out, f"run{i}.log")) else ""
            for i in (1, 2)]
    ok(r.returncode == 0 and all("===ENGINE_OUTPUT===" in t and "EXIT_CODE=0" in t and "BenchmarkInfo:" in t
                                 for t in logs),
       f"2 runs: exit 0, each run<i>.log = sampler output, ===ENGINE_OUTPUT===, the engine's output, EXIT_CODE=0 "
       f"(rc {r.returncode}, {r.stderr[-200:]!r})")
    ok(prov["props"].get("ro.serialno") == "HOSTRUN0001" and len(prov["args"]) == 13
       and prov["args"][-1] == f"--command={command}"
       and f"{dev}/litert_lm_main" in prov["sha"] and f"{dev}/models/m.litertlm" in prov["sha"],
       f"provenance.txt: getprop values, every arg (13), sha256 of the engine, model and prompt files "
       f"({len(prov['args'])} args, {len(prov['sha'])} shas)")
    st = record.parse_state(open(os.path.join(out, "run1.state")).read()) \
        if os.path.exists(os.path.join(out, "run1.state")) else {"gate": {}, "start": {}, "end": {}}
    ok(st["start"].get("epoch", "").isdigit() and st["end"].get("epoch", "").isdigit()
       and record.thermal(st["start"].get("thermal"))[0] == 0
       and record.battery(st["start"].get("battery"))["batteryLevel"] == 1.0
       and record.screen(st["start"].get("wakefulness"), st["start"].get("stay_on"))["screen"] == "on-usb"
       and st["gate"].get("thermal_gate_timed_out") == "0",
       f"run1.state: start / end epoch, thermal, battery, screen and the gate results read back ({st['gate']})")
    ok(all(os.path.exists(os.path.join(out, f)) for f in ("run1.exit", "run1.engine.txt", "run1_logcat.txt",
                                                          "run2.exit", "wrapper.log"))
       and open(os.path.join(out, "run1.exit")).read().strip() == "0",
       "run<i>.exit (0), run<i>.engine.txt, run<i>_logcat.txt, wrapper.log written")
    out_split = os.path.join(dev, "ddp-out-split")
    a_split = subprocess.run(["sh", run_ddp.WRAPPER, "--runs=1", "--cooldown=0", "--mask=none", "--env=LD_LIBRARY_PATH=.",
                              "--binname=litert_lm_main", f"--dir={dev}", f"--output_dir={out_split}", "--timeout=20",
                              "--thermal_wait=1", "--cpucap_wait=1", "--budget=0", "--cell=host-cell"]
                             + ("--command=" + command).split(" "), env=env, capture_output=True, text=True, timeout=120)
    t = open(os.path.join(out_split, "run1.log")).read() if os.path.exists(os.path.join(out_split, "run1.log")) else ""
    ok(a_split.returncode == 0 and "EXIT_CODE=0" in t and "BenchmarkInfo:" in t,
       "--command= split at its spaces into separate args runs the same engine command")
    out_fail = os.path.join(dev, "ddp-out-fail")
    r = run(out_fail, {"FAKE_ENGINE_RC": "3"}, runs=1)
    t = open(os.path.join(out_fail, "run1.log")).read() if os.path.exists(os.path.join(out_fail, "run1.log")) else ""
    ok(r.returncode == 0 and "EXIT_CODE=3" in t and open(os.path.join(out_fail, "run1.exit")).read().strip() == "3",
       f"an engine that exits 3: EXIT_CODE=3, run1.exit 3, the wrapper still exits 0 (rc {r.returncode})")
    out_slow = os.path.join(dev, "ddp-out-slow")
    r = run(out_slow, {"FAKE_ENGINE_SLEEP": "30"}, runs=1, timeout=2)
    ok(r.returncode == 0 and os.path.exists(os.path.join(out_slow, "run1.exit"))
       and open(os.path.join(out_slow, "run1.exit")).read().strip() == "124",
       f"an engine past --timeout: timeout ends it (exit 124 in run1.exit), the wrapper exits 0 (rc {r.returncode})")
    out_budget = os.path.join(dev, "ddp-out-budget")
    r = run(out_budget, runs=2, timeout=20, budget=100, cooldown=30)
    ok(r.returncode == 0 and os.path.exists(os.path.join(out_budget, "run1.log"))
       and not os.path.exists(os.path.join(out_budget, "run2.log"))
       and "not started" in (open(os.path.join(out_budget, "run2.skipped")).read()
                             if os.path.exists(os.path.join(out_budget, "run2.skipped")) else ""),
       "--budget 100 s with a 20 s run timeout and a 30 s cooldown: run 1 runs, run 2 is not started (run2.skipped)")
    out_hot = os.path.join(dev, "ddp-out-hot")
    r = run(out_hot, {"FAKE_THERMAL": "2"}, runs=1, thermal_wait=1)
    st = record.parse_state(open(os.path.join(out_hot, "run1.state")).read()) \
        if os.path.exists(os.path.join(out_hot, "run1.state")) else {"gate": {}}
    ok(r.returncode == 0 and st["gate"].get("thermal_gate_timed_out") == "1",
       "a unit at thermal status 2: the gate times out after --thermal_wait, the run still runs, recorded")
    out_bad = os.path.join(dev, "ddp-out-bad")
    r = run(out_bad, command=None, runs=1)
    ok(r.returncode == 0 and not glob.glob(os.path.join(out_bad, "run*.log"))
       and "bad args" in (open(os.path.join(out_bad, "wrapper.log")).read()
                          if os.path.exists(os.path.join(out_bad, "wrapper.log")) else ""),
       "no --command: no run, the reason in wrapper.log, exit 0")


# ---------------------------------------------------------------- 3. the attached-phone route's FAKESELF records

def attached_records(tmp, raw_root, models):
    print("--- 3. the attached-phone route's FAKESELF campaign (round mode) for the record layout")
    spec = importlib.util.spec_from_file_location("bench_selftest", os.path.join(ROOT, "android", "bench", "selftest.py"))
    bench_selftest = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bench_selftest)
    state = os.path.join(tmp, "fakeself-state")
    dev = os.path.join(state, "dev")
    tools = os.path.join(tmp, "fakeself-tools")
    os.makedirs(dev)
    # android/bench/selftest.py's fake device tools (its FAKE_<TOOL> templates), on PATH under their names
    for attr in dir(bench_selftest):
        if attr.startswith("FAKE_") and isinstance(getattr(bench_selftest, attr), str):
            write(os.path.join(tools, attr[len("FAKE_"):].lower()), getattr(bench_selftest, attr) % {
                "state": state, "on_task": bench_selftest.ON_TASK, "off_task": bench_selftest.OFF_TASK,
                "bench_htp0": bench_selftest.BENCH_HTP0, "side_lines": bench_selftest.SIDE_LINES,
                "npu_lines": bench_selftest.NPU_LINES}, 0o755)
    for name in ("litert_lm_main", "litert_lm_advanced_main"):
        write(os.path.join(dev, name), "fake " + name)
    json.dump([25.0, 24.5, 20.6, 20.1], open(os.path.join(state, "schedule.json"), "w"))
    cells = os.path.join(tmp, "fakeself.cells")
    write(cells, f"android litert-lm litert-community/Qwen3-1.7B short-chat backend=cpu file={models['Qwen3_1.7B.litertlm']}\n"
                 f"android litert-lm litert-community/Qwen3-1.7B long-context-1024-gen256 backend=gpu "
                 f"file={models['Qwen3-1.7B_dynamic_wi4b32_afp32.litertlm']} context-tokens=2048\n")
    env = dict(os.environ, PATH=tools + os.pathsep + os.environ.get("PATH", ""), BENCH_ANDROID_SERIAL="FAKESELF",
               BENCH_RAW_ROOT=raw_root, CAMPAIGN="selftest-attached-android", ROUNDS="1", COOLDOWN="0",
               THERMAL_WAIT="5", GATE_COOLDOWN="0", CPUCAP_WAIT="1", BENCH_TEST_LOCK_DIR=tmp)
    for k in ("BENCH_ROUND_WAKEFULNESS", "BENCH_TEXT_CHECK", "BENCH_SITTING", "BENCH_STRICT_SMOKE"):
        env.pop(k, None)
    r = subprocess.run([sys.executable, os.path.join(ROOT, "android", "bench", "run_campaign.py"), cells],
                       env=env, capture_output=True, text=True)
    out = os.path.join(raw_root, "selftest-attached-android", "app-path-android")
    recs = {os.path.basename(f): json.load(open(f)) for f in sorted(glob.glob(os.path.join(out, "*.json")))}
    short = [r_ for n, r_ in recs.items() if "_short-chat_" in n]
    long_ = [r_ for n, r_ in recs.items() if "_long-context-1024-gen256_" in n]
    ok(r.returncode == 0 and len(short) == 1 and len(long_) == 2,
       f"FAKESELF campaign: 1 short-chat record + 2 iteration records of the 1K launch (rc {r.returncode}, "
       f"{len(short)} + {len(long_)}; {r.stderr[-300:]!r})")
    head = ""
    if short:
        log = open(os.path.join(out, short[0]["provenance"]["rawLog"])).read()
        head = log.split("===ENGINE_OUTPUT===", 1)[0]
    ok("CPUPOLICY" in head and "VmRSS" in head and "CPUMAX" in head,
       "the FAKESELF console's sampler lines (CPUPOLICY, VmHWM / VmRSS / Cpus_allowed_list, CPUMAX) taken for the fake unit")
    return out, short, long_, head


# ---------------------------------------------------------------- 4. the billed path, faked

FAKE_GCLOUD = '''#!/usr/bin/env python3
import os, shutil, sys
ROOT = %(bucket_root)r
LOG = %(log)r
a = sys.argv[1:]
open(LOG, "a").write(" ".join(a) + "\\n")


def local(url):
    assert url.startswith("gs://"), url
    return os.path.join(ROOT, url[len("gs://"):].rstrip("/"))


if a[:2] == ["auth", "print-access-token"]:
    print("fake-token-0001")
elif a[:2] == ["storage", "ls"]:
    if not os.path.exists(local(a[2])):
        sys.stderr.write("ERROR: (gcloud.storage.ls) One or more URLs matched no objects.\\n")
        sys.exit(1)
    print(a[2])
elif a[:3] == ["storage", "cp", "-r"]:
    src, dst = local(a[3]), a[4]
    shutil.copytree(src, os.path.join(dst, os.path.basename(src)))
elif a[:2] == ["storage", "cp"]:
    dst = local(a[3])
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    open(dst, "w").write("uploaded %%s %%d\\n" %% (a[2], os.path.getsize(a[2])))
else:
    sys.exit(2)
'''


# a lab unit's logcat lines, one rule of android/ddp/scrub.py each (documentation / test values only:
# RFC 7042 MAC 00:00:5e:00:53:xx, RFC 3849 2001:db8::/32, RFC 4193 fd.., test PLMN 001-01, the IMEI
# example 490154203237518), then a line of what stays
FAKE_HASH_SSID = hashlib.sha256(b"fake-lab-ssid-01").hexdigest()
FAKE_HASH_BSSID = hashlib.sha256(b"00:00:5e:00:53:42").hexdigest()
FAKE_LAB_LOGCAT = (
    '10-15 03:00:01.100  1000  1100 I WifiClientModeImpl: SSID: "fake-lab-ssid-01", BSSID: 00:00:5e:00:53:42, '
    'MAC: 02:00:00:00:00:00, Security type: 2\n'
    '10-15 03:00:01.200  1000  1100 D WifiService: getSsid():"fake-lab-ssid-01",networkId=1\n'
    '10-15 03:00:01.300  1000  1100 I SemWifiCoex: connected pBssid:00:00:5e, rssi:-50 freq:5180\n'
    f'10-15 03:00:01.400  1000  1100 I MobileWips: detected [ssid: {FAKE_HASH_SSID}, bssid: {FAKE_HASH_BSSID}]\n'
    '10-15 03:00:01.500  1000  1100 I SemWifi: BSSID: 00:00:5e:**:**:42, MAC: 02:00:00:00:00:00\n'
    '10-15 03:00:01.600  1000  1100 D DhcpClient: lease 10.123.45.67/22 gateway 10.123.44.1 dns 172.20.33.44 '
    '192.168.77.88 mask 255.255.255.0\n'
    '10-15 03:00:01.700  1000  1100 D ApfFilter: RA prefix 2001:db8:abcd:12::/64 dns fd12:3456:789a:1::53 '
    'from fe80::200:5eff:fe00:5342%wlan0\n'
    '10-15 03:00:01.800  1000  1100 I Telephony: iccid=89001012012341234012 imei: 490154203237518 '
    'imsi=001010123456789\n'
    '10-15 03:00:01.900  1000  1100 I Keep: SSID: <unknown ssid> lo ::1 any :: 0.0.0.0 dns 8.8.8.8 '
    'zero 00:00:00:00:00:00 rand 02:00:00:00:00:00 epoch 1792058400\n')
FAKE_LAB_EXEC = '10-15 03:00:02.000  1000  1100 I WifiConfigManager: SSID: "fake-lab-ssid-02" saved\n'
FAKE_LAB_RUN = '10-15 03:00:02.000  1000  1100 D WifiScanner: roam candidate fake-lab-ssid-02 rssi -61\n'
# per logcat: the common lines + one ssid (quoted in the execution's, bare in a run's: known from the session)
FAKE_LAB_COUNTS = {"ssid": 3, "hash": 2, "ip6": 3, "mac": 2, "mac-part": 1, "ip": 4, "id": 3}
FAKE_LAB_STRINGS = ["fake-lab-ssid-01", "fake-lab-ssid-02", "00:00:5e:00:53:42", "pBssid:00:00:5e", FAKE_HASH_SSID,
                    FAKE_HASH_BSSID, "00:00:5e:**:**:42", "10.123.45.67", "10.123.44.1", "172.20.33.44",
                    "192.168.77.88", "2001:db8:abcd:12", "fd12:3456:789a:1", "fe80::200:5eff:fe00:5342",
                    "89001012012341234012", "490154203237518", "001010123456789"]
FAKE_LAB_KEPT = ["02:00:00:00:00:00", "00:00:00:00:00:00", " ::1 ", " :: ", "8.8.8.8", "255.255.255.0",
                 "<unknown ssid>", "0.0.0.0", "epoch 1792058400"]
# the cache lines of a LiteRT-LM raw log (android/ddp/record.py engine_cache), as the v0.18.0 CLI prints them
XNNPACK_BUILD_LINE = ("VERBOSE: XNNPack weight cache build for '/data/local/tmp/llmbench/models/"
                      "litert-community_Qwen3-1.7B_Qwen3_1.7B.litertlm_1792058400_29.xnnpack_cache' started.\n")
XNNPACK_LOADED_LINE = ("VERBOSE: XNNPack weight cache loaded from '/data/local/tmp/llmbench/models/"
                       "litert-community_Qwen3-1.7B_Qwen3_1.7B.litertlm_1792058400_29.xnnpack_cache'.\n")
GPU_LOADED_LINE = ("I0000 00:00:1792058700.100000    4242 delegate_kernel.cc:866] Initialized InferenceContext "
                   "from serialized data.\n")


def synthesize_session(st, sid, body):
    """The unit's side of one session: what ddp_cell.sh would leave in ddp-out for each job (the
    FAKESELF sampler lines + a v0.18.0 fixture console per run with the run's cache lines, provenance
    with the pushed objects' shas, logcats with the lab network's identifiers), in the fake bucket;
    -> the Session resource."""
    jobs = []
    for jc in body["sessionConfig"]["jobConfigs"]:
        a = {}
        argv = jc["action"]["androidNativeBinary"]["args"]
        for x in argv:
            k, _, v = x[2:].partition("=")
            a[k] = v
        exec_id = str(uuid.UUID(int=len(st["executions"]) + 1))
        st["executions"].append(exec_id)
        rel = f"automation/sessions/{sid}/{jc['displayName']}/execution-{exec_id}"
        base = os.path.join(st["bucket_root"], "fake-bucket", rel)
        out = os.path.join(base, "artifacts", a["output_dir"].lstrip("/"))
        pushes = jc["allocationConfig"]["deviceConfigs"][0]["actions"][0]["androidPushFiles"]["fileConfigs"]
        shas = [(re.search(r"/([0-9a-f]{64})/", p["sourceFile"]["gcsInputFile"]["path"]).group(1), p["destinationPath"])
                for p in pushes]
        sha = dict((d, s) for s, d in shas)
        prov =["date: Wed Oct 15 03:00:00 PDT 2026", "epoch: 1792058400"]
        prov += [f"{k}: {v}" for k, v in st["props"].items()]
        prov += ["kernel: Linux localhost 6.1 aarch64 Toybox", "taskset: /system/bin/taskset",
                 "timeout: /system/bin/timeout", f"cell: {a['cell']}", f"argc: {len(argv)}"]
        prov += [f"arg: {x}" for x in argv] + ["sha256:"] + [f"{s}  {d}" for d, s in sha.items()]
        write(os.path.join(out, "provenance.txt"), "\n".join(prov) + "\n")
        fixture = LONG_FIXTURE if a["binname"] == "litert_lm_advanced_main" else SHORT_FIXTURE
        gpu = "--backend=gpu" in a["command"]
        console = open(fixture).read()
        t0 = 1792058400
        for i in range(1, int(a["runs"]) + 1):
            start = t0 + (i - 1) * 300
            batt = "  level: 96\n  status: 2\n  USB powered: true\n  temperature: 301\n"
            write(os.path.join(out, f"run{i}.state"),
                  f"run={i}\nthermal_gate_waited_s=0\nthermal_gate_timed_out=0\ncpucap_waited_s=0\n"
                  f"cpucap_timed_out=0\ncpucap_caps=\nstart_epoch={start}\nstart_ns={start}123456789\n"
                  f"start_thermal=Thermal Status: 0\nstart_wakefulness=  mWakefulness=Dozing\nstart_stay_on=0\n"
                  f"start_battery_begin\n{batt}start_battery_end\nend_epoch={start + 41}\n"
                  f"end_ns={start + 41}023456789\nend_thermal=Thermal Status: 1\nend_wakefulness=  mWakefulness=Dozing\n"
                  f"end_stay_on=0\nend_battery_begin\n{batt.replace('301', '322')}end_battery_end\n")
            # CPU: run 1 builds the XNNPACK weight cache, later runs load it; GPU (the 1K fixture holds no
            # cache line): run 1 compiles, later runs load the serialized InferenceContext
            if gpu:
                cache = GPU_LOADED_LINE if i > 1 else ""
            else:
                cache = XNNPACK_LOADED_LINE if i > 1 else XNNPACK_BUILD_LINE
            write(os.path.join(out, f"run{i}.log"),
                  st["sampler_head"] + console.replace("===ENGINE_OUTPUT===\n", "===ENGINE_OUTPUT===\n" + cache, 1))
            write(os.path.join(out, f"run{i}.err"), "")
            write(os.path.join(out, f"run{i}.exit"), "0\n")
            write(os.path.join(out, f"run{i}.engine.txt"), engine_lines(fixture))
            write(os.path.join(out, f"run{i}_logcat.txt"), FAKE_LAB_LOGCAT + FAKE_LAB_RUN)
        write(os.path.join(out, "wrapper.log"), "fake wrapper log\n")
        write(os.path.join(base, "logcat.txt"), FAKE_LAB_LOGCAT + FAKE_LAB_EXEC)
        files = sorted(glob.glob(os.path.join(base, "**", "*"), recursive=True))
        outputs = [{"gcsOutputFile": {"path": "gs://fake-bucket/" + os.path.relpath(f, os.path.join(st["bucket_root"], "fake-bucket"))}}
                   for f in files if os.path.isfile(f)]
        times = {"startTime": "2026-10-15T10:00:00.000Z", "endTime": "2026-10-15T10:20:00.000Z"}
        jobs.append({"id": str(uuid.UUID(int=1000 + len(jobs))), "displayName": jc["displayName"],
                     "executionReports": [{"id": exec_id, "displayName": f"execution-{exec_id}",
                                           "startTime": "2026-10-15T10:01:00.000Z", "endTime": "2026-10-15T10:19:00.000Z",
                                           "status": {"statusType": "DONE"}, "result": {"resultType": "PASSED"},
                                           "outputFiles": outputs}],
                     **times, "status": {"statusType": "DONE"}, "result": {"resultType": "PASSED"},
                     "labels": jc["labels"]})
    return {"name": f"projects/{PROJECT}/locations/global/sessions/{sid}", "sessionConfig": body["sessionConfig"],
            "sessionReport": {"id": str(uuid.uuid4()), "jobReports": jobs, "startTime": "2026-10-15T09:59:00.000Z",
                              "endTime": "2026-10-15T10:21:00.000Z", "status": {"statusType": "DONE"},
                              "result": {"resultType": "PASSED"}}}


class FakeDeviceRun(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, obj):
        data = (obj if isinstance(obj, str) else json.dumps(obj)).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        st = self.server.st
        st["auth"].append(self.headers.get("Authorization"))
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if self.path != f"/projects/{PROJECT}/locations/global/sessions":
            return self.send(404, {"error": {"code": 404}})
        if st.get("reject"):
            return self.send(400, st["reject"])
        st["posts"].append(body)
        sid = f"session-test{len(st['posts']):04d}"
        name = f"projects/{PROJECT}/locations/global/operations/operation-test-{len(st['posts'])}"
        st["ops"][name] = {"polls": 0, "session": synthesize_session(st, sid, body)}
        self.send(200, {"name": name, "metadata": {"@type": "type.googleapis.com/google.cloud.devicerun.v1alpha.OperationMetadata",
                                                   "createTime": "2026-10-15T09:58:00.000Z",
                                                   "target": f"projects/{PROJECT}/locations/global/sessions/{sid}",
                                                   "verb": "create", "requestedCancellation": False, "apiVersion": "v1alpha"},
                        "done": False})

    def do_GET(self):
        st = self.server.st
        st["auth"].append(self.headers.get("Authorization"))
        path = self.path.lstrip("/")
        if path in st["ops"]:
            op = st["ops"][path]
            op["polls"] += 1
            sess = op["session"]
            meta = {"createTime": "2026-10-15T09:58:00.000Z", "target": sess["name"], "verb": "create"}
            if op["polls"] < 2:
                return self.send(200, {"name": path, "metadata": meta, "done": False})
            return self.send(200, {"name": path, "metadata": dict(meta, endTime="2026-10-15T10:22:00.000Z",
                                                                  statusMessage="Session is finished"),
                                   "done": True, "response": dict(sess, **{"@type": "Session"})})
        for op in st["ops"].values():
            if path == op["session"]["name"]:
                return self.send(200, op["session"])
        self.send(404, {"error": {"code": 404, "message": f"no {path}"}})


def run_driver(argv, env):
    out = io.StringIO()
    rc = None
    with patch.object(sys, "argv", ["run_ddp.py"] + argv), patch.dict(os.environ, env), \
            contextlib.redirect_stdout(out):
        try:
            rc = run_ddp.main()
        except SystemExit as exc:
            rc = exc
    return rc, out.getvalue()


def check_billed_path(tmp, raw_root, bin_dir, models, sampler_head, att_short, att_long):
    print("--- 4. the billed path against a fake gcloud and a fake Device Run server")
    gbin = os.path.join(tmp, "gcloud-bin")
    bucket_root = os.path.join(tmp, "bucket")
    glog = os.path.join(tmp, "gcloud.log")
    write(os.path.join(gbin, "gcloud"), FAKE_GCLOUD % {"bucket_root": bucket_root, "log": glog}, 0o755)
    props = {"ro.product.model": "Pixel 8a", "ro.product.device": "akita",
             "ro.build.fingerprint": "google/akita/akita:16/FAKE.251005.001/7:user/release-keys",
             "ro.serialno": "FAKEDDP0001", "ro.build.version.release": "16",
             "ro.build.version.security_patch": "2026-09-05", "ro.soc.model": "Tensor G3"}
    st = {"posts": [], "ops": {}, "auth": [], "executions": [], "bucket_root": bucket_root, "props": props,
          "sampler_head": sampler_head}
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), FakeDeviceRun)
    server.st = st
    threading.Thread(target=server.serve_forever, daemon=True).start()
    endpoint = f"http://127.0.0.1:{server.server_address[1]}"
    cells = os.path.join(tmp, "e2e.cells")
    write(cells, "android litert-lm litert-community/Qwen3-1.7B short-chat backend=cpu file=Qwen3_1.7B.litertlm runs=2\n"
                 "android litert-lm litert-community/Qwen3-1.7B long-context-1024-gen256 backend=gpu "
                 "file=Qwen3-1.7B_dynamic_wi4b32_afp32.litertlm context-tokens=2048 runs=2\n"
                 "android llama.cpp unsloth/Qwen3-1.7B-GGUF short-chat file=Qwen3-1.7B-Q4_K_M.gguf\n")
    env = {"PATH": gbin + os.pathsep + os.environ.get("PATH", ""), "BENCH_RAW_ROOT": raw_root}

    def fake_model(model_id, filename, dry_run):
        path = models[filename]
        return {"local": path, "bytes": os.path.getsize(path), "sha256": run_cell.sha256_file(path)}

    common = ["--device", "akita-35", "--endpoint", endpoint, "--bucket", BUCKET, "--project", PROJECT,
              "--poll-seconds", "0.05", "--bin-dir", bin_dir]
    with patch.object(run_ddp, "model_file", fake_model):
        rc, printed = run_driver([cells, "--campaign", "selftest-ddp-akita-35-android"] + common, env)
    campaign = os.path.join(raw_root, "selftest-ddp-akita-35-android")
    ddp = os.path.join(campaign, "ddp")
    out = os.path.join(campaign, "app-path-android")
    gcalls = open(glog).read().splitlines() if os.path.exists(glog) else []
    uploads = [c for c in gcalls if c.startswith("storage cp ") and not c.startswith("storage cp -r")]
    ok(rc in (0, 1) and len(st["posts"]) == 1 and len(uploads) == 14,
       f"one POST for the session's 2 jobs; 14 objects uploaded (9 engine, 2 models, 2 prompts, the wrapper) "
       f"(rc {rc}, posts {len(st['posts'])}, uploads {len(uploads)}){'' if rc in (0, 1) else printed[-600:]}")
    req = json.load(open(os.path.join(ddp, "request-1.json"))) if os.path.exists(os.path.join(ddp, "request-1.json")) else None
    ok(req is not None and st["posts"] and req == st["posts"][0]
       and all(a == "Bearer fake-token-0001" for a in st["auth"]) and len(st["auth"]) >= 4,
       f"ddp/request-1.json = the body POSTed; every call carried the gcloud token ({len(st['auth'])} calls)")
    op = json.load(open(os.path.join(ddp, "operation-1.json"))) if os.path.exists(os.path.join(ddp, "operation-1.json")) else {}
    sess_ok = os.path.exists(os.path.join(ddp, "session-1.json"))
    ok(op.get("done") is True and sess_ok and os.path.isdir(os.path.join(ddp, "session-test0001")),
       "polled until done (ddp/operation-1.json), ddp/session-1.json, the session pulled into ddp/session-test0001/")
    skipped = open(os.path.join(out, "SKIPPED.txt")).read() if os.path.exists(os.path.join(out, "SKIPPED.txt")) else ""
    ok("reason=runtime-not-wired-on-ddp" in skipped, "SKIPPED.txt names the llama.cpp row and its reason")
    recs = {os.path.basename(f): json.load(open(f)) for f in sorted(glob.glob(os.path.join(out, "*.json")))}
    short = [(n, r) for n, r in recs.items() if "_short-chat_" in n]
    long_ = [(n, r) for n, r in recs.items() if "_long-context-1024-gen256_" in n]
    ok(len(short) == 2 and len(long_) == 4, f"records: 2 short-chat runs, 2 x 2 iterations of the 1K cell "
                                            f"(got {len(short)} + {len(long_)})")
    required = all(r.get("schemaVersion") == 1 and r.get("runtime") and r.get("task") and r.get("timestamp")
                   and r.get("model", {}).get("id") and r.get("model", {}).get("quantization") for r in recs.values())
    ok(bool(recs) and required, "every record carries result.v1's required keys")
    added = {"conditions.ddp", "conditions.engineCache", "device.ddp", "provenance.ddpSessionDir", "provenance.wrapper",
             "provenance.wrapperSha256"}
    for label, ddp_rec, att_rec in (("short-chat", short[0][1] if short else None, att_short[0] if att_short else None),
                                    ("1K iteration 1", long_[0][1] if long_ else None,
                                     next((r for r in att_long if r["conditions"].get("iterationIndex") == 1), None))):
        if not ddp_rec or not att_rec:
            ok(False, f"{label}: a DDP and an attached-phone record to compare")
            continue
        d, a = set(key_layout(ddp_rec)), set(key_layout(att_rec))
        ok(d >= a and d - a == added, f"{label}: DDP record keys ⊇ the attached-phone record's; added only "
                                      f"{sorted(added)} (missing {sorted(a - d)}, extra {sorted(d - a - added)})")
    pins = run_cell.load_pins()["litert-lm"]["v0.18.0"]
    s1 = short[0][1] if short else {}
    l1 = long_[0][1] if long_ else {}
    ok(s1.get("engineVersion") == "v0.18.0" and s1.get("engineArtifact") == pins["litert_lm_main_sha256"]
       and l1.get("engineVersion") == "v0.18.0" and l1.get("engineArtifact") == pins["litert_lm_advanced_main_sha256"],
       "witness: v0.18.0 + the launched tool's sha, read from the unit's provenance.txt")
    want_model = run_cell.sha256_file(models["Qwen3_1.7B.litertlm"])
    ok(s1.get("model", {}).get("sha256") == want_model and s1.get("provenance", {}).get("modelShaSource") == "device"
       and s1.get("model", {}).get("file") == "litert-community_Qwen3-1.7B_Qwen3_1.7B.litertlm",
       "model.sha256 = the provenance.txt sha of the pushed model, modelShaSource device, file = the device name")
    c = s1.get("conditions", {}).get("ddp", {})
    fields = ["sessionId", "jobId", "executionId", "deviceId", "deviceKey", "buildFingerprint", "serial", "product",
              "jobStartTime", "jobEndTime", "executionStartTime", "executionEndTime", "executionTimeout",
              "resultType", "runIndex"]
    ok(list(c) == fields and c["sessionId"] == "session-test0001" and c["deviceId"] == "akita-35"
       and c["deviceKey"] == "pixel8a" and c["serial"] == "FAKEDDP0001" and c["product"] == "akita"
       and c["buildFingerprint"] == props["ro.build.fingerprint"] and c["executionTimeout"] == "3600s"
       and c["resultType"] == "PASSED" and c["runIndex"] == 1
       and s1.get("device", {}).get("ddp") == {"deviceId": "akita-35", "buildFingerprint": props["ro.build.fingerprint"],
                                               "serial": "FAKEDDP0001"},
       f"conditions.ddp: all 15 fields from the session report and the unit; device.ddp ({c})")
    raw = os.path.join(out, s1.get("provenance", {}).get("rawLog", "-"))
    pulled = glob.glob(os.path.join(ddp, "session-test0001", "j01-*", "execution-*", "artifacts", "data", "local",
                                    "tmp", "llmbench", "ddp-out", "run1.log"))
    ok(os.path.exists(raw) and pulled and open(raw).read() == open(pulled[0]).read()
       and s1["provenance"]["ddpSessionDir"].startswith("ddp/session-test0001/j01-"),
       "provenance.rawLog = a copy of the pulled run1.log beside the record; ddpSessionDir names the execution")
    ok(s1.get("conditions", {}).get("cpuAffinity") == "taskset f0" and s1["metrics"].get("harnessStamp")
       == "2026-08-android-cli-v1+ddp-route-c" and s1["conditions"].get("screen") == "off-usb (mWakefulness=Dozing)"
       and s1["conditions"].get("elapsedSeconds") == 40.9 and s1["device"].get("batteryLevel") == 0.96
       and s1["conditions"].get("batteryTemperatureFinalC") == 32.2 and s1["conditions"].get("thermalRawStatusFinal") == 1,
       "cpuAffinity = the applied mask, harnessStamp +ddp-route-c, screen / elapsed (ns) / battery / thermal from run1.state")
    regimes = sorted((r["conditions"].get("iterationIndex"), r["conditions"].get("regime")) for _, r in long_)
    texts = [r["provenance"].get("decodedText") for _, r in long_]
    ok(regimes == [(1, "cold"), (1, "cold"), (2, "warm"), (2, "warm")]
       and all(r["conditions"].get("textCheck") for _, r in long_)
       and all(t and os.path.exists(os.path.join(out, t)) for t in texts),
       f"1K cell: per run a cold and a warm record, each with textCheck and its .decoded.txt ({regimes})")
    first = sorted((n, r["metrics"].get("firstEver")) for n, r in short + long_)
    want_first = [(n, True if ("_run1" in n and "_iter2" not in n) else None) for n, _ in first]
    ok(first == want_first, f"firstEver on run 1 only (its iteration 1 in the 1K cell) ({[f for _, f in first]})")
    check_engine_cache(short, long_)
    check_ids(recs)
    check_pull_scrub(campaign, os.path.join(bucket_root, "fake-bucket", "automation", "sessions"))
    check_records_only(campaign, rc)
    # a re-run uploads nothing: every object is in the bucket now
    with patch.object(run_ddp, "model_file", fake_model):
        rc2, _ = run_driver([cells, "--campaign", "selftest-ddp-again-android"] + common, env)
    gcalls2 = open(glog).read().splitlines()[len(gcalls):]
    ok(rc2 in (0, 1) and not [x for x in gcalls2 if x.startswith("storage cp ") and not x.startswith("storage cp -r")]
       and len([x for x in gcalls2 if x.startswith("storage ls ")]) == 14,
       f"a second campaign checks the 14 objects (storage ls) and uploads none (rc {rc2})")
    # a 4xx answer to the POST: its body kept verbatim, nothing else
    st["reject"] = {"error": {"code": 400, "message": "Invalid value at 'session.session_config' (fake)",
                              "status": "INVALID_ARGUMENT"}}
    with patch.object(run_ddp, "model_file", fake_model):
        rc3, _ = run_driver([cells, "--campaign", "selftest-ddp-rejected-android"] + common, env)
    err = os.path.join(raw_root, "selftest-ddp-rejected-android", "ddp", "error-1.json")
    ok(isinstance(rc3, SystemExit) and os.path.exists(err) and json.load(open(err)) == st["reject"]
       and not glob.glob(os.path.join(raw_root, "selftest-ddp-rejected-android", "app-path-android", "*.json")),
       f"a 400 to the POST: the driver stops, ddp/error-1.json holds the body verbatim, no record ({rc3})")
    st.pop("reject")
    # --resume: a session POSTed by an earlier driver that stopped while it polled -> no second POST
    with patch.object(run_ddp, "model_file", fake_model), patch.dict(os.environ, env):
        p = run_ddp.plan(cells, "akita-35", "selftest-ddp-resume-android",
                         plan_args(bin_dir, dry_run=False))
    import urllib.request
    posted = json.load(urllib.request.urlopen(urllib.request.Request(
        f"{endpoint}/projects/{PROJECT}/locations/global/sessions", method="POST",
        data=json.dumps(p["sessions"][0]["request"]).encode(),
        headers={"Authorization": "Bearer fake-token-0001", "Content-Type": "application/json"})))
    n_posts = len(st["posts"])
    with patch.object(run_ddp, "model_file", fake_model):
        rc4, _ = run_driver([cells, "--campaign", "selftest-ddp-resume-android", "--resume", posted["name"]] + common, env)
    resumed = glob.glob(os.path.join(raw_root, "selftest-ddp-resume-android", "app-path-android", "*.json"))
    ok(rc4 in (0, 1) and len(st["posts"]) == n_posts and len(resumed) == 6,
       f"--resume <operation>: no new POST, the session polled, pulled and recorded (rc {rc4}, {len(resumed)} records)")
    # the witness of a changed sha: one .so, then the tool itself
    session = json.load(open(os.path.join(ddp, "session-1.json")))
    plan_s = json.load(open(os.path.join(ddp, "plan-1.json")))
    ok(all("local" not in f for j in plan_s["jobs"] for f in j["push"] + [j["wrapper"]])
       and tmp not in open(os.path.join(ddp, "plan-1.json")).read(),
       "ddp/plan-1.json (what the records are built from) carries no host path")
    job = plan_s["jobs"][0]
    jr = session["sessionReport"]["jobReports"][0]
    ex, rel = record.execution_dirs("session-test0001", jr)[0]
    for victim, want in (("libLiteRtOpenClAccelerator.so",
                          "unknown (on-device v0.18.0 litert_lm_main with lib libLiteRtOpenClAccelerator.so unmatched"),
                         ("litert_lm_main", "unknown (on-device litert_lm_main sha unmatched")):
        copy_dir = os.path.join(tmp, f"tamper-{victim}")
        shutil.copytree(os.path.join(ddp, rel), copy_dir)
        prov_path = glob.glob(os.path.join(copy_dir, "artifacts", "**", "provenance.txt"), recursive=True)[0]
        text = open(prov_path).read()
        line = next(x for x in text.splitlines() if x.endswith(f"/{victim}"))
        write(prov_path, text.replace(line, "0" * 64 + "  " + line.split("  ", 1)[1]))
        tout = os.path.join(tmp, f"tamper-out-{victim}")
        os.makedirs(tout)
        meta = {"sessionId": "session-test0001", "jobId": jr["id"], "jobDisplayName": jr["displayName"],
                "executionId": ex["id"], "jobStartTime": jr["startTime"], "jobEndTime": jr["endTime"],
                "executionStartTime": ex["startTime"], "executionEndTime": ex["endTime"],
                "resultType": "PASSED", "ddpSessionDir": f"ddp/{rel}"}
        record.records_for_execution(job, copy_dir, tout, meta)
        got = [json.load(open(f))["engineVersion"] for f in glob.glob(os.path.join(tout, "*.json"))]
        ok(got and all(g.startswith(want) for g in got), f"provenance sha of {victim} changed -> {got[:1]}")
    # a CPU run whose raw log holds no XNNPACK cache line: "absent", and the reason in provenance.ddpMissing
    copy_dir = os.path.join(tmp, "no-cache-line")
    shutil.copytree(os.path.join(ddp, rel), copy_dir)
    run1 = glob.glob(os.path.join(copy_dir, "artifacts", "**", "run1.log"), recursive=True)[0]
    write(run1, "".join(x for x in open(run1).read().splitlines(True) if record.XNNPACK_BUILT not in x))
    tout = os.path.join(tmp, "no-cache-line-out")
    os.makedirs(tout)
    record.records_for_execution(job, copy_dir, tout, dict(meta, ddpSessionDir=f"ddp/{rel}"))
    r1 = [json.load(open(f)) for f in glob.glob(os.path.join(tout, "*_run1.json"))]
    ok(len(r1) == 1 and r1[0]["conditions"]["engineCache"] == {"xnnpackWeightCache": "absent", "gpuCache": "absent"}
       and any("run1.log has neither" in m for m in r1[0]["provenance"].get("ddpMissing", [])),
       f"a CPU run with neither XNNPACK cache line: engineCache absent / absent, the reason in provenance.ddpMissing "
       f"({[r['provenance'].get('ddpMissing') for r in r1]})")
    server.shutdown()
    return out


def check_engine_cache(short, long_):
    """conditions.engineCache of the billed path's records: the CPU cell's run 1 built / run 2 loaded the
    XNNPACK weight cache; the GPU cell's run 1 compiled (not-loaded) / run 2 loaded the InferenceContext."""
    got = sorted((r["runtime"], r["conditions"]["ddp"]["runIndex"], r["conditions"].get("iterationIndex"),
                  json.dumps(r["conditions"].get("engineCache"), sort_keys=True)) for _, r in short + long_)

    def cache(xnnpack, gpu):
        return json.dumps({"xnnpackWeightCache": xnnpack, "gpuCache": gpu}, sort_keys=True)
    want = sorted([("litert-lm-cpu", 1, 1, cache("built", "absent")), ("litert-lm-cpu", 2, 1, cache("loaded", "absent"))]
                  + [("litert-lm-gpu", 1, k, cache("absent", "not-loaded")) for k in (1, 2)]
                  + [("litert-lm-gpu", 2, k, cache("absent", "loaded")) for k in (1, 2)])
    ok(got == want and not any("ddpMissing" in r["provenance"] for _, r in short + long_),
       f"conditions.engineCache from the raw log: CPU run 1 built, run 2 loaded (gpuCache absent); GPU run 1 "
       f"not-loaded, run 2 loaded (xnnpack absent), both iterations of a 1K launch alike; no ddpMissing ({got})")


def check_ids(recs):
    """D13: id = uuid5(URL, edge-llm-bench/ddp/<session>/<job>/<execution>/run<i>/iter<k>), launchID the
    same without /iter<k>."""
    bad = []
    for name, r in recs.items():
        c = r["conditions"]
        d = c["ddp"]
        base = f"edge-llm-bench/ddp/{d['sessionId']}/{d['jobId']}/{d['executionId']}/run{d['runIndex']}"
        if (r["id"] != str(uuid.uuid5(uuid.NAMESPACE_URL, f"{base}/iter{c['iterationIndex']}"))
                or c["launchID"] != str(uuid.uuid5(uuid.NAMESPACE_URL, base))):
            bad.append(name)
    ids = [r["id"] for r in recs.values()]
    ok(recs and not bad and len(set(ids)) == len(ids),
       f"record id = uuid5(URL, edge-llm-bench/ddp/<session>/<job>/<execution>/run<i>/iter<k>), conditions.launchID "
       f"= the same without /iter<k>; {len(ids)} ids, all distinct (differ: {bad[:2]})")


def check_pull_scrub(campaign, bucket_sessions):
    """D12 after the pull: the lab strings gone from the campaign dir except ddp-raw/, which holds the
    logcats as pulled; ddp/scrub.json's counts."""
    ddp = os.path.join(campaign, "ddp")
    raw = os.path.join(campaign, run_ddp.RAW_DIR)
    logcats = sorted(p for p in glob.glob(os.path.join(ddp, "**", "*.txt"), recursive=True)
                     if run_ddp.LOGCAT.match(os.path.basename(p)))
    leaks = []
    for p in glob.glob(os.path.join(campaign, "**", "*"), recursive=True):
        if os.path.isfile(p) and not p.startswith(raw + os.sep):
            text = open(p, errors="replace").read()
            leaks += [(os.path.relpath(p, campaign), s) for s in FAKE_LAB_STRINGS if s in text]
    raw_files = glob.glob(os.path.join(raw, "**", "*.txt"), recursive=True)
    raw_text = "".join(open(p, errors="replace").read() for p in raw_files)
    as_pulled = all(os.path.exists(os.path.join(raw, os.path.relpath(p, ddp)))
                    and open(os.path.join(raw, os.path.relpath(p, ddp)), "rb").read()
                    == open(os.path.join(bucket_sessions, os.path.relpath(p, ddp)), "rb").read() for p in logcats)
    kept = all(all(k in open(p).read() for k in FAKE_LAB_KEPT) for p in logcats)
    lines = all(open(p).read().count("\n") == open(os.path.join(raw, os.path.relpath(p, ddp))).read().count("\n")
                for p in logcats)
    ok(len(logcats) == 6 and len(raw_files) == 6 and not leaks and all(s in raw_text for s in FAKE_LAB_STRINGS)
       and as_pulled and kept and lines,
       f"after the pull: none of the {len(FAKE_LAB_STRINGS)} lab strings anywhere in the campaign dir beside "
       f"{run_ddp.RAW_DIR}/, which holds the 6 logcats (2 jobs x 2 runs + 2 executions) byte for byte as pulled; "
       f"what stays stays; line counts kept ({len(logcats)} logcats, {len(raw_files)} copies, leaks {leaks[:2]})")
    path = os.path.join(ddp, "scrub.json")
    js = json.load(open(path)) if os.path.exists(path) else {"files": {}, "total": {}}
    files = js["files"]
    per_file = sum(FAKE_LAB_COUNTS.values())
    ok(sorted(files) == sorted(os.path.relpath(p, ddp) for p in logcats)
       and all({k: e.get(k) for k in scrub.KINDS} == FAKE_LAB_COUNTS and e.get("replaced") == per_file
               and e.get("rawSha256") == run_cell.sha256_file(os.path.join(raw, f)) for f, e in files.items())
       and {k: js["total"].get(k) for k in scrub.KINDS} == {k: 6 * v for k, v in FAKE_LAB_COUNTS.items()}
       and js["total"].get("files") == 6,
       f"ddp/scrub.json: one entry per logcat with {FAKE_LAB_COUNTS} ({per_file}), rawSha256 = its {run_ddp.RAW_DIR}/ "
       f"copy, totals x 6 ({js['total']})")
    ok("results/raw/*/ddp-raw/" in open(os.path.join(ROOT, ".gitignore")).read().splitlines(),
       ".gitignore keeps every campaign's ddp-raw/ out of git (results/raw/*/ddp-raw/)")


def snapshot(root):
    out = {}
    for p in sorted(glob.glob(os.path.join(root, "**", "*"), recursive=True)):
        if os.path.isfile(p):
            out[os.path.relpath(p, root)] = open(p, "rb").read()
    return out


def check_records_only(campaign, rc_billed):
    """--records-only on the billed path's campaign dir: no subprocess, no network, every file the same,
    the billed run's exit code (1 there: the fixture's 1K runs are not clean, FAILURES.txt)."""
    before = snapshot(campaign)
    with patch.object(subprocess, "run", side_effect=AssertionError("subprocess in --records-only")), \
            patch.object(subprocess, "Popen", side_effect=AssertionError("subprocess in --records-only")), \
            patch.object(run_ddp.urllib.request, "urlopen", side_effect=AssertionError("network in --records-only")):
        rc, printed = run_driver(["--records-only", campaign], {})
    after = snapshot(campaign)
    line = next((json.loads(x) for x in printed.splitlines() if x.startswith('{"recordsOnly"')), {})
    changed = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
    ok(rc == rc_billed and not changed and line.get("removed") == line.get("written") and line.get("records") == 6
       and not line.get("notWrittenAgain") and not line.get("newNames"),
       f"--records-only <campaign>: no subprocess, no network; the 6 records, their raw logs and decoded texts and "
       f"FAILURES.txt written again, the logcats, ddp-raw/ and scrub.json, all byte for byte as before; the billed "
       f"run's exit code (rc {rc} / {rc_billed}, changed {changed[:3]}, {line})")
    rc2, _ = run_driver(["--records-only", campaign, "--device", "akita-35"], {})
    ok(isinstance(rc2, SystemExit) and rc2.code == 2, f"--records-only with another argument refuses ({rc2!r})")


# ---------------------------------------------------------------- 5. summary

def check_summary(sum_root, att_out):
    print("--- 5. build_summary into a temp dir: the DDP row's device column, never the attached phone's")
    # the attached-phone FAKESELF records stand for the attached Pixel 8a (its fake getprop says FakePhone)
    for f in glob.glob(os.path.join(att_out, "*.json")):
        rec = json.load(open(f))
        rec["device"]["modelIdentifier"] = "Pixel 8a"
        json.dump(rec, open(f, "w"), indent=2)
    import build_summary
    import render_leaderboard
    import render_dashboard
    with patch.object(build_summary, "ROOT", sum_root), patch.object(build_summary, "OUT", os.path.join(sum_root, "summary")):
        os.makedirs(build_summary.OUT, exist_ok=True)
        path, _ = build_summary.build_device()
    rows = list(csv.DictReader(open(path)))
    ddp_rows = [r for r in rows if r["campaign"] == "results/raw/selftest-ddp-akita-35-android"]
    att_rows = [r for r in rows if r["campaign"] == "results/raw/selftest-attached-android"]
    ok(ddp_rows and {r["device"] for r in ddp_rows} == {"Pixel 8a (DDP akita-35)"}
       and {r["device"] for r in att_rows} == {"Pixel 8a"} and {r["platform"] for r in ddp_rows} == {"android"},
       f"device column: DDP rows 'Pixel 8a (DDP akita-35)', the attached phone's 'Pixel 8a' "
       f"({sorted({r['device'] for r in ddp_rows})}, {sorted({r['device'] for r in att_rows})})")
    tree = {}
    for r in rows:
        if r["task"] == render_leaderboard.HEADLINE_TASK and r["model_id"] == "litert-community/Qwen3-1.7B" \
                and r["runtime"] == "litert-lm-cpu" and r["campaign"] in ("results/raw/selftest-ddp-akita-35-android",
                                                                       "results/raw/selftest-attached-android"):
            tree.setdefault((r["platform"], r["device"]), []).append(r)
    arms = {k: render_leaderboard.arm_row(v) for k, v in tree.items()}
    ok(set(tree) == {("android", "Pixel 8a"), ("android", "Pixel 8a (DDP akita-35)")}
       and arms[("android", "Pixel 8a (DDP akita-35)")]["campaign"] == "results/raw/selftest-ddp-akita-35-android"
       and arms[("android", "Pixel 8a")]["campaign"] == "results/raw/selftest-attached-android",
       f"render_leaderboard: the same cell under two (platform, device) keys, one arm_row each, no pooling ({sorted(tree)})")
    sched = render_dashboard.load_schedule(os.path.join(ROOT, "ops", "dashboard-v1", "schedule.json"))
    cols = [ident for ident, _ in render_dashboard.devices_for("android", sched, rows)]
    ok("Pixel 8a (DDP akita-35)" in cols and cols.index("Pixel 8a") < cols.index("Pixel 8a (DDP akita-35)"),
       f"render_dashboard.devices_for: the DDP unit is a column of its own after the schedule's phones ({cols})")


# ---------------------------------------------------------------- 6. scrub.py

SCRUB_TOKENS = {"ssid": "<lab-ssid>", "hash": "<hash>", "ip6": "<ip6>", "mac": "<mac>", "mac-part": "<mac-part>",
                "ip": "<ip>", "id": "<id>"}


def check_scrub(tmp):
    print("--- 6. android/ddp/scrub.py: each rule, what stays, the file form, the CLI")
    h1, h2 = FAKE_HASH_SSID, FAKE_HASH_BSSID
    cases = [  # (line, the line after the scrub, SSIDs known from the session's other logcats)
        ('I Wifi: SSID: "fake-lab-ssid-01" connected', 'I Wifi: SSID: "<lab-ssid>" connected', ()),
        ('D Wifi: getSsid():"fake-lab-ssid-01",networkId=1', 'D Wifi: getSsid():"<lab-ssid>",networkId=1', ()),
        ('D Wifi: ssid="ab" short', 'D Wifi: ssid="<lab-ssid>" short', ()),
        ("D Wifi: ssid=fake-lab-ssid-03, freq=5180", "D Wifi: ssid=<lab-ssid>, freq=5180", ()),
        ("D Scan: roam candidate fake-lab-ssid-02 rssi -61", "D Scan: roam candidate <lab-ssid> rssi -61",
         ("fake-lab-ssid-02",)),
        (f"I MobileWips: [ssid: {h1}, bssid: {h2}]", "I MobileWips: [ssid: <hash>, bssid: <hash>]", ()),
        ("I Wips: bssid=0123456789abcdef0123 seen", "I Wips: bssid=<hash> seen", ()),
        ("D Apf: prefix 2001:db8:abcd:12::/64 from fe80::200:5eff:fe00:5342%wlan0",
         "D Apf: prefix <ip6>/64 from <ip6>%wlan0", ()),
        ("D Dns: server fd12:3456:789a:1::53 port 53", "D Dns: server <ip6> port 53", ()),
        ("I Wifi: BSSID: 00:00:5e:00:53:42, MAC: 02:00:00:00:00:00", "I Wifi: BSSID: <mac>, MAC: 02:00:00:00:00:00", ()),
        ("I SemWifi: BSSID: 00:00:5e:**:**:42 zero 00:00:00:00:00:00", "I SemWifi: BSSID: <mac> zero 00:00:00:00:00:00",
         ()),
        ("I Wifi: BSSID:00:00:5E:00:53:42 joined", "I Wifi: BSSID:<mac> joined", ()),
        ("I SemWifiCoex: pBssid:00:00:5e, rssi:-50", "I SemWifiCoex: pBssid:<mac-part>, rssi:-50", ()),
        ("D Dhcp: lease 10.123.45.67/22 dns 172.20.33.44 192.168.77.88 8.8.8.8 mask 255.255.255.0",
         "D Dhcp: lease <ip>/22 dns <ip> <ip> 8.8.8.8 mask 255.255.255.0", ()),
        ("I Tel: iccid=89001012012341234012 imei: 490154203237518", "I Tel: iccid=<id> imei: <id>", ()),
        ("I Keep: SSID: <unknown ssid> lo ::1 any :: 0.0.0.0 zero 00:00:00:00:00:00 epoch 1792058400", None, ()),
        (f"I Model: sha256 {h1} bytes 12345678901", None, ()),
    ]
    bad = []
    for line, want, ssids in cases:
        want = line if want is None else want
        got, counts = scrub.scrub_text(line + "\n", ssids)
        if got != want + "\n" or counts != {k: want.count(t) for k, t in SCRUB_TOKENS.items()}:
            bad.append((line[:40], got, counts))
    ok(not bad, f"scrub_text: {len(cases)} lines, each rule (ssid quoted / ssid() / short / bare / known from the "
                f"session, hash, ip6, mac incl. star-masked, mac-part, ip, id) and what stays, counted per kind "
                f"({bad[:1]})")
    text = FAKE_LAB_LOGCAT + FAKE_LAB_RUN
    got, counts = scrub.scrub_text(text, {"fake-lab-ssid-02"})
    ok(counts == FAKE_LAB_COUNTS and got.count("\n") == text.count("\n")
       and not [s for s in FAKE_LAB_STRINGS if s in got] and all(k in got for k in FAKE_LAB_KEPT),
       f"the fake lab logcat: {counts}, line count kept, no lab string left, what stays stays")
    # the file form: the original copied once, the scrub of the original written; bytes outside UTF-8 kept
    d = os.path.join(tmp, "scrub-files")
    f1 = os.path.join(d, "a", "run1_logcat.txt")
    original = b"\xff\xfe not utf-8\n" + (FAKE_LAB_LOGCAT + FAKE_LAB_RUN).encode()
    os.makedirs(os.path.dirname(f1))
    open(f1, "wb").write(original)
    raw_dir = os.path.join(d, "raw", "a")
    c1 = scrub.scrub_file(f1, raw_dir, {"fake-lab-ssid-02"})
    after1 = open(f1, "rb").read()
    c2 = scrub.scrub_file(f1, raw_dir, {"fake-lab-ssid-02"})
    raw_copy = open(os.path.join(raw_dir, "run1_logcat.txt"), "rb").read()
    ok(c1 == c2 == FAKE_LAB_COUNTS and raw_copy == original and open(f1, "rb").read() == after1
       and after1.startswith(b"\xff\xfe not utf-8\n") and b"fake-lab-ssid-01" not in after1,
       "scrub_file: the original in the raw dir, the scrub over the file; a second scrub reads the copy: the same "
       "bytes and counts, the copy untouched; bytes outside UTF-8 kept")
    try:
        scrub.scrub_file(f1, os.path.dirname(f1))
        refused = False
    except ValueError:
        refused = True
    ok(refused and open(f1, "rb").read() == after1, "scrub_file refuses a raw dir that is the file's own directory")
    # the CLI (./android/ddp/scrub.py --raw-dir <dir> <file>...): the supervisor's route for files outside a pull
    f2 = os.path.join(d, "b", "logcat.txt")
    f3 = os.path.join(d, "b", "run2_logcat.txt")
    write(f2, FAKE_LAB_LOGCAT + FAKE_LAB_EXEC)
    write(f3, FAKE_LAB_LOGCAT + FAKE_LAB_RUN)
    cli_raw = os.path.join(d, "cli-raw")
    r = subprocess.run([sys.executable, os.path.join(HERE, "scrub.py"), "--raw-dir", cli_raw, f2, f3],
                       capture_output=True, text=True)
    lines = [json.loads(x) for x in r.stdout.splitlines() if x.startswith("{")]
    ok(r.returncode == 0 and len(lines) == 2 and all(x["counts"] == FAKE_LAB_COUNTS for x in lines)
       and os.path.exists(os.path.join(cli_raw, "logcat.txt")) and "fake-lab-ssid-02" not in open(f3).read()
       and os.access(os.path.join(HERE, "scrub.py"), os.X_OK),
       f"scrub.py --raw-dir <dir> <file> <file>: one JSON line per file with its counts, originals in the dir, the "
       f"SSID that only the execution's logcat quotes taken out of the run's too; executable "
       f"(rc {r.returncode}, {[x['counts'] for x in lines]}, {r.stderr[-200:]!r})")
    r2 = subprocess.run([sys.executable, os.path.join(HERE, "scrub.py"), "--raw-dir", cli_raw,
                         os.path.join(d, "b", "missing.txt")], capture_output=True, text=True)
    write(os.path.join(d, "c", "run1_logcat.txt"), "x\n")
    r3 = subprocess.run([sys.executable, os.path.join(HERE, "scrub.py"), "--raw-dir", cli_raw, f1,
                         os.path.join(d, "c", "run1_logcat.txt")], capture_output=True, text=True)
    ok(r2.returncode == 2 and r3.returncode == 2 and "one call per directory" in r3.stderr,
       f"the CLI refuses a missing file (rc {r2.returncode}) and two files of one name (rc {r3.returncode})")


def main():
    tmp = tempfile.mkdtemp(prefix="ddp-selftest-")
    bin_dir = os.environ.get("BENCH_ANDROID_BIN_DIR") or run_cell.ANDROID_BIN_DIR
    if not os.path.isdir(os.path.join(bin_dir, "v0.18.0")):
        print(f"FAIL: {bin_dir}/v0.18.0 missing — set BENCH_ANDROID_BIN_DIR to the dir that holds the pinned build")
        return 1
    sum_root = os.path.join(tmp, "sumroot")
    raw_root = os.path.join(sum_root, "results", "raw")
    os.makedirs(raw_root)
    models = {}
    for name in ("Qwen3_1.7B.litertlm", "Qwen3-1.7B_dynamic_wi4b32_afp32.litertlm"):
        models[name] = os.path.join(tmp, "models", name)
        write(models[name], f"weights of {name}\n")
    plans = check_plan(tmp, bin_dir, models)
    check_bench_dry_run(tmp, bin_dir)
    check_wrapper_strings(plans)
    check_wrapper_host_run(tmp)
    att_out, att_short, att_long, head = attached_records(tmp, raw_root, models)
    check_billed_path(tmp, raw_root, bin_dir, models, head, att_short, att_long)
    check_summary(sum_root, att_out)
    check_scrub(tmp)
    if _fails:
        print(f"\n{len(_fails)} of {_count[0]} check(s) failed; temp dir kept: {tmp}")
        return 1
    shutil.rmtree(tmp)
    print(f"\nddp selftest OK ({_count[0]} checks)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
