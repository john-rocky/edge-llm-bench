#!/usr/bin/env python3
"""DDP backend of `bench matrix --ddp <device id>`: the cells file's Android LiteRT-LM rows as
Device Run sessions on a Developer Device Platform (DDP) lab phone (Route C: our request body,
the static wrapper android/ddp/ddp_cell.sh, our own LiteRT-LM build; docs/ddp-integration.md).

  CAMPAIGN=<name>-android android/ddp/run_ddp.py <cells> --device akita-35 --dry-run
  CAMPAIGN=<name>-android android/ddp/run_ddp.py <cells> --device akita-35        # billed
  android/ddp/run_ddp.py --records-only results/raw/<campaign>     # records again from the pulled output

(a) rows: run_campaign.parse_cells, android only; skipped with a reason (printed, SKIPPED.txt):
    a runtime other than litert-lm, exclude= / manual=, a side build (backend=npu / engine-build=),
    anchor=1 (no session anchor on DDP), exclude-on= naming the id's schedule key
    (android/ddp/devices.json -> ops/dashboard-v1/schedule.json), any exclude-on= on an id with
    no schedule key.
(b) one job per row = runs= launches of run_campaign.planned_command's engine command on one
    unit, inside the attached-phone route's sampler shell (run_cell.sampler_shell, built by the wrapper);
    one session per <= --jobs-per-session jobs; the CPU-cap wait before each run = the id's
    cpucapWaitSeconds in devices.json (absent: the attached-phone route's run_cell.CPUCAP_WAIT, 300 s).
(c) pushes: the 9 engine files of android_pins' tag (each checked against engine-pins.json),
    the model (HF cache), the prompt; the wrapper is the job's binary; bucket objects are
    content-addressed under <--bucket>/automation/inputs/edge-llm-bench/.
(d) request bodies (the 2026-09-17 session's shape), POSTed to --project's sessions.
(e) not with --dry-run: missing objects uploaded (gcloud storage ls / cp), one POST per session,
    the operation polled every --poll-seconds, the session read and pulled (gcloud storage cp -r)
    into <campaign>/ddp/, every pulled logcat scrubbed of the lab network's identifiers
    (android/ddp/scrub.py; the originals in <campaign>/ddp-raw/, gitignored; the counts in
    ddp/scrub.json), records written by android/ddp/record.py into app-path-android/.
--dry-run prints (a)-(d) and an estimate as JSON lines and one table, and runs no subprocess:
no gcloud, no network (the model is looked up in the local HF cache only).
--records-only <campaign dir> runs (e)'s last two steps again on what the campaign's sessions
pulled (ddp/plan-<n>.json, ddp/session-<n>.json, ddp/<session>/): no network; the records,
raw logs and decoded texts of the plans' cells are removed and written again (same ids and names).
"""
import argparse
import datetime
import glob
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "android", "bench"))
sys.path.insert(0, HERE)
import run_campaign  # noqa: E402
import run_cell  # noqa: E402
import record  # noqa: E402
import scrub  # noqa: E402

DEVICES = os.path.join(HERE, "devices.json")
WRAPPER = os.path.join(HERE, "ddp_cell.sh")
SCHEDULE = run_campaign.SCHEDULE
INPUTS = "automation/inputs/edge-llm-bench"
OUTPUT_DIR = f"{run_cell.DEV_DIR}/ddp-out"
# D12: the pulled logcats (per run and per execution), scrubbed in place; the originals under
# <campaign>/RAW_DIR/<the same path below ddp/> (.gitignore results/raw/*/ddp-raw/)
LOGCAT = re.compile(r"^(?:run[0-9]+_logcat|logcat)\.txt$")
RAW_DIR = "ddp-raw"
# job displayName / session displayName: <= 63 bytes, ^[A-Za-z0-9][A-Za-z0-9-_ ]*$ (REST reference,
# docs/ddp-integration.md; the SDK contract's docstring prints the regex without its brackets)
NAME_MAX = 63
# an argv element the platform may split at spaces must carry nothing a shell reads specially
SAFE_COMMAND = re.compile(r"^[A-Za-z0-9_./=:,+ -]+$")
SAFE_ENV = re.compile(r"^[A-Za-z0-9_./=:,+-]+$")
# per-run timeout cap (D7) and the margin the wrapper keeps for logcat and the pull
RUN_TIMEOUT_CAP = 1800
PULL_MARGIN = 120
# estimate: largest local elapsed x runs x 1.5 + cooldowns + one cache build
ESTIMATE_FACTOR = 1.5
CACHE_BUILD_S = 300
DEFAULT_ELAPSED_S = 600


def load_json(path):
    with open(path) as fh:
        return json.load(fh)


def sha256_file(path):
    return run_cell.sha256_file(path)


def label_value(text):
    """A label value in the GCP label form (lowercase, digits, - and _, <= 63 bytes): the
    2026-09-17 request wrote its runtime as litert-lm-v0-17-0-own-build."""
    return re.sub(r"[^a-z0-9_-]", "-", str(text).lower())[:NAME_MAX]


def display_name(text):
    name = re.sub(r"[^A-Za-z0-9_-]", "-", text)
    name = re.sub(r"^[^A-Za-z0-9]+", "", name)
    return name.encode()[:NAME_MAX].decode(errors="ignore") or "job"


def device_entry(device_id):
    devices = load_json(DEVICES)
    if device_id not in devices or device_id.startswith("_"):
        raise SystemExit(f"--device {device_id}: not in {os.path.relpath(DEVICES, ROOT)} "
                         f"({', '.join(sorted(k for k in devices if not k.startswith('_')))})")
    entry = dict(devices[device_id])
    key = entry.get("scheduleKey")
    sched = load_json(SCHEDULE).get("devices", {}) if key else {}
    if key and key not in sched:
        raise SystemExit(f"{device_id}: scheduleKey {key!r} is not a device of "
                         f"{os.path.relpath(SCHEDULE, ROOT)}")
    entry["cpuMask"] = (sched.get(key, {}).get("cpu_mask") or "") if key else ""
    entry["identifier"] = sched.get(key, {}).get("identifier") if key else None
    # D14: the wrapper's CPU-cap wait before each run, per id (absent: the attached-phone route's)
    wait = entry.get("cpucapWaitSeconds", run_cell.CPUCAP_WAIT)
    if isinstance(wait, bool) or not isinstance(wait, int) or wait < 0:
        raise SystemExit(f"{device_id}: cpucapWaitSeconds {wait!r} in {os.path.relpath(DEVICES, ROOT)} "
                         "is not a whole number of seconds >= 0")
    entry["cpucapWait"] = wait
    return entry


def select_cells(cells_file, device_id, key):
    """-> (kept cells in file order, [(cell, reason, schedule key or None)])."""
    anchors, payload, skipped = run_campaign.parse_cells(cells_file)
    skips, candidates = [], []
    for cell, reason in skipped:
        skips.append((cell, "runtime-not-wired-on-ddp" if cell["runtime"] != "litert-lm" else reason, None))
    for cell in anchors + payload:
        opts = cell["opts"]
        if cell["runtime"] != "litert-lm":
            skips.append((cell, "runtime-not-wired-on-ddp", None))
        elif opts.get("backend") == "npu" or opts.get("engine-build"):
            skips.append((cell, "side-build-not-wired-on-ddp", None))
        elif opts.get("anchor"):
            skips.append((cell, "no-session-anchor-on-ddp", None))
        else:
            candidates.append(cell)
    if key:
        _, kept, out = run_campaign.skip_on_device([], candidates, None, device_key=key)
        skips += [(cell, reason, k) for cell, k, reason in out]
    else:
        kept = [c for c in candidates if not c["opts"].get("exclude-on")]
        skips += [(c, "ddp-device-key-unknown", None) for c in candidates if c["opts"].get("exclude-on")]
    return kept, skips


def engine_files(bin_dir, tag, pins):
    """The 9 files of the flat LiteRT-LM build: path, bytes, sha256 — each equal to the pins
    entry (tool fields + so_files), else stop."""
    entry = pins.get("litert-lm", {}).get(tag)
    if not entry:
        raise SystemExit(f"android/engine-pins.json has no litert-lm {tag} entry")
    want = {"litert_lm_main": entry.get("litert_lm_main_sha256"),
            "litert_lm_advanced_main": entry.get("litert_lm_advanced_main_sha256"),
            **entry.get("so_files", {})}
    files = []
    for name in ["litert_lm_main", "litert_lm_advanced_main"] + sorted(entry.get("so_files", {})):
        path = os.path.join(bin_dir, tag, name)
        if not os.path.isfile(path):
            raise SystemExit(f"{path}: missing (BENCH_ANDROID_BIN_DIR / --bin-dir holds <tag>/<file>)")
        sha = sha256_file(path)
        if sha != want[name]:
            raise SystemExit(f"{path}: sha256 {sha} is not the pin's {want[name]} "
                             f"(android/engine-pins.json litert-lm {tag}) — nothing is pushed")
        files.append({"kind": "engine", "name": name, "local": path, "bytes": os.path.getsize(path),
                      "sha256": sha, "device": f"{run_cell.DEV_DIR}/{name}",
                      "object": f"{INPUTS}/engines/litert-lm/{tag}/{sha}/{name}"})
    return files


def model_file(model_id, filename, dry_run):
    """The model's local file (the HF cache blob) and the sha256 of its bytes, which the plan and
    the bucket key carry. The blob's name is the LFS sha256 on older huggingface_hub and the xet
    hash on newer ones (2.2.0, for a file the Hub stores with Xet), so the file is hashed.
    A dry run reads the cache only (uncached = no sha, no size); a real run downloads, checks the
    size against the Hub's (run_cell.ensure_model's guard) and the hash against the Hub's LFS
    sha256 when the file has one (a poisoned or truncated cache stops the run)."""
    if dry_run:
        os.environ["HF_HUB_OFFLINE"] = "1"
    try:
        from huggingface_hub import hf_hub_download
    except ImportError:  # a host without the package: a dry run still plans, a real run cannot download
        if dry_run:
            return {"local": None, "bytes": None, "sha256": None, "uncached": "huggingface_hub not installed"}
        raise SystemExit(f"{model_id} {filename}: huggingface_hub is not installed (pip install huggingface_hub)")
    try:
        local = hf_hub_download(model_id, filename, local_files_only=dry_run)
    except Exception as exc:  # noqa: BLE001 — the cache miss of a dry run, or a failed download
        if dry_run:
            return {"local": None, "bytes": None, "sha256": None, "uncached": f"{type(exc).__name__}"}
        raise SystemExit(f"{model_id} {filename}: download failed: {exc}")
    local = os.path.realpath(local)
    sha = sha256_file(local)
    size = os.path.getsize(local)
    if not dry_run:
        from huggingface_hub import HfApi
        info = HfApi().model_info(model_id, files_metadata=True)
        entry = next((f for f in info.siblings if f.rfilename == filename), None)
        declared = entry.size if entry else None
        if declared is not None and declared != size:
            raise SystemExit(f"{local}: {size} bytes, the Hub declares {declared} (poisoned cache?)")
        lfs = getattr(entry.lfs, "sha256", None) if entry and entry.lfs else None
        if lfs and lfs != sha:
            raise SystemExit(f"{local}: sha256 {sha}, the Hub's LFS sha256 is {lfs} (poisoned cache?)")
    return {"local": local, "bytes": size, "sha256": sha}


def elapsed_basis(cell, stem, identifier, tag):
    """The largest elapsedSeconds of this cell's local records at the pinned tag: on the schedule
    key's phone, else on any Android phone, else DEFAULT_ELAPSED_S. -> (seconds, basis)."""
    opts = cell["opts"]
    ctx = int(opts["context-tokens"]) if opts.get("context-tokens") else None
    stems = {stem, run_cell.capture_stem(cell["runtime"], opts.get("backend"), cell["model_id"],
                                         cell["task"], opts.get("file"), ctx, round_mode=True)}
    found = []
    for s in sorted(stems):
        for path in glob.glob(os.path.join(ROOT, "results", "raw", "*", "app-path-android", s + "_*.json")):
            try:
                rec = load_json(path)
            except (OSError, ValueError):
                continue
            if rec.get("engineVersion") != tag or (rec.get("device") or {}).get("ddp"):
                continue
            elapsed = (rec.get("conditions") or {}).get("elapsedSeconds")
            if isinstance(elapsed, (int, float)):
                found.append(((rec.get("device") or {}).get("modelIdentifier"), elapsed))
    mine = [e for ident, e in found if identifier and ident == identifier]
    if mine:
        return max(mine), f"max of {len(mine)} local {identifier} runs at {tag}"
    if found:
        return max(e for _, e in found), f"max of {len(found)} local Android runs at {tag}"
    return DEFAULT_ELAPSED_S, f"no local run at {tag}: default {DEFAULT_ELAPSED_S} s"


def plan(cells_file, device_id, campaign, args):
    """Everything up to the request bodies, with no subprocess and no network."""
    dev = device_entry(device_id)
    key = dev.get("scheduleKey")
    pins = run_cell.load_pins()
    tag = pins.get("android_pins", {}).get("litert-lm")
    if not tag:
        raise SystemExit("android/engine-pins.json android_pins has no litert-lm tag")
    kept, skips = select_cells(cells_file, device_id, key)
    with open(os.path.join(ROOT, "prompts", "text", "budgets.tsv")) as fh:
        budgets = dict(line.strip().split("\t") for line in fh if line.strip())
    engines = engine_files(args.bin_dir, tag, pins) if kept else []
    wrapper = {"kind": "wrapper", "name": "ddp_cell.sh", "local": WRAPPER, "bytes": os.path.getsize(WRAPPER),
               "sha256": sha256_file(WRAPPER)}
    wrapper["object"] = f"{INPUTS}/wrapper/{wrapper['sha256']}/ddp_cell.sh"
    mask = dev["cpuMask"]
    jobs, models = [], {}
    for n, cell in enumerate(kept, 1):
        opts = cell["opts"]
        runs = int(opts.get("runs", "3"))
        cooldown = int(opts.get("cooldown", run_campaign.COOLDOWN))
        ctx = int(opts["context-tokens"]) if opts.get("context-tokens") else None
        max_tokens = int(opts["max-tokens"]) if opts.get("max-tokens") else None
        budget = int(budgets[cell["task"]]) if cell["task"] in budgets else None
        full, binname, sampler = run_campaign.planned_command(cell)
        env = run_cell.launch_env(None, opts.get("backend"), cell["runtime"])
        head = f"cd {run_cell.DEV_DIR} && {env} "
        affinity = f"taskset {run_cell.CPU_MASK} " if run_cell.CPU_MASK else ""
        if not full.startswith(head + affinity):
            raise SystemExit(f"planned_command form changed: {full!r}")
        core = full[len(head + affinity):]
        filename = opts["file"]
        model_dev = f"{run_cell.DEV_DIR}/models/{cell['model_id'].replace('/', '_')}_{filename}"
        prompt_dev = f"{run_cell.DEV_DIR}/prompts/{cell['task']}.txt"
        _, _, _, ctx_note = run_cell.engine_command(cell["runtime"], opts.get("backend"), model_dev, cell["task"],
                                                    prompt_dev, budget, max_tokens, ctx)
        if not SAFE_COMMAND.match(core) or not SAFE_ENV.match(env):
            raise SystemExit(f"{run_campaign.cell_id(cell)}: command or env holds a character the job args "
                             f"cannot carry ({core!r}, {env!r})")
        if f"--model_path={model_dev} " not in core + " ":
            raise SystemExit(f"{run_campaign.cell_id(cell)}: the command's model path is not {model_dev}")
        per_run = min(RUN_TIMEOUT_CAP, (args.job_timeout - cooldown * (runs - 1) - PULL_MARGIN) // runs)
        if per_run < 60:
            raise SystemExit(f"{run_campaign.cell_id(cell)}: {runs} runs + cooldowns leave {per_run} s per run "
                             f"in --job-timeout {args.job_timeout}")
        arm = run_cell.arm_name(cell["runtime"], opts.get("backend"))
        stem = run_cell.capture_stem(cell["runtime"], opts.get("backend"), cell["model_id"], cell["task"],
                                     filename, ctx)
        if (cell["model_id"], filename) not in models:
            models[(cell["model_id"], filename)] = model_file(cell["model_id"], filename, args.dry_run)
        m = models[(cell["model_id"], filename)]
        model_push = {"kind": "model", "name": filename, "local": m["local"], "bytes": m["bytes"],
                      "sha256": m["sha256"], "device": model_dev,
                      "object": f"{INPUTS}/models/{m['sha256'] or 'UNCACHED'}/{filename}",
                      **({"uncached": m["uncached"]} if m.get("uncached") else {})}
        prompt_local = os.path.join(ROOT, "prompts", "text", f"{cell['task']}.txt")
        psha = sha256_file(prompt_local)
        prompt_push = {"kind": "prompt", "name": f"{cell['task']}.txt", "local": prompt_local,
                       "bytes": os.path.getsize(prompt_local), "sha256": psha, "device": prompt_dev,
                       "object": f"{INPUTS}/prompts/{psha}/{cell['task']}.txt"}
        push = engines + [model_push, prompt_push]
        wargs = [f"--runs={runs}", f"--cooldown={cooldown}", f"--mask={mask or 'none'}", f"--env={env}",
                 f"--binname={binname}", f"--dir={run_cell.DEV_DIR}", f"--output_dir={OUTPUT_DIR}",
                 f"--timeout={per_run}", f"--thermal_wait={run_campaign.THERMAL_WAIT}",
                 f"--cpucap_wait={dev['cpucapWait']}", f"--budget={args.job_timeout - PULL_MARGIN}",
                 f"--cell={stem}", f"--command={core}"]
        labels = {"harness": "edge-llm-bench", "campaign": label_value(campaign), "cell": label_value(stem),
                  "runtime": label_value(arm), "model": label_value(cell["model_id"].replace("/", "--")),
                  "task": label_value(cell["task"]), "backend": label_value(opts.get("backend")),
                  "devicekey": label_value(key or "none"), "deviceid": label_value(device_id),
                  "engine": label_value(tag)}
        elapsed, basis = elapsed_basis(cell, stem, dev.get("identifier"), tag)
        estimate = round(elapsed * runs * ESTIMATE_FACTOR + cooldown * (runs - 1) + CACHE_BUILD_S)
        jobs.append({
            "index": n, "displayName": display_name(f"j{n:02d}-{opts.get('backend')}-"
                                                    f"{cell['model_id'].split('/')[-1]}-{cell['task']}"),
            "cell": cell, "cellId": run_campaign.cell_id(cell, True), "stem": stem, "arm": arm,
            "runtime": cell["runtime"], "backend": opts.get("backend"), "modelId": cell["model_id"],
            "file": filename, "task": cell["task"], "contextTokens": ctx, "ctxNote": ctx_note,
            "budget": budget, "maxTokens": max_tokens,
            "paired": run_cell.context_prompt(cell["runtime"], cell["task"], ctx),
            "binname": binname, "sampler": sampler, "command": core, "env": env, "mask": mask,
            "runs": runs, "cooldown": cooldown, "perRunTimeout": per_run, "cpucapWait": dev["cpucapWait"],
            "executionTimeout": args.job_timeout, "deviceId": device_id, "deviceKey": key,
            "engineTag": tag, "args": wargs, "labels": labels, "push": push, "wrapper": wrapper,
            "modelDevice": model_dev, "promptDevice": prompt_dev,
            "estimate": {"elapsedSeconds": elapsed, "basis": basis, "jobSeconds": estimate,
                         "overTimeout": estimate > args.job_timeout}})
    sessions = []
    for s, first in enumerate(range(0, len(jobs), args.jobs_per_session), 1):
        chunk = jobs[first:first + args.jobs_per_session]
        name = display_name(f"elb-{campaign}-s{s}")
        for j in chunk:
            j["session"] = s
        sessions.append({"index": s, "displayName": name, "jobs": chunk,
                         "request": request_body(name, chunk, args.bucket)})
    return {"device": dict(dev, deviceId=device_id), "engineTag": tag, "campaign": campaign,
            "project": getattr(args, "project", None), "bucket": args.bucket,
            "skips": skips, "jobs": jobs, "sessions": sessions, "wrapper": wrapper}


def request_body(name, jobs, bucket):
    return {"sessionConfig": {
        "displayName": name,
        "outputDirectoryConfig": {"gcsOutputDirectory": {"path": f"{bucket}/automation/sessions"}},
        "jobConfigs": [{
            "displayName": j["displayName"],
            "action": {"androidNativeBinary": {
                "androidNativeBinary": {"gcsInputFile": {"path": f"{bucket}/{j['wrapper']['object']}"}},
                "args": j["args"],
                "executionTimeout": f"{j['executionTimeout']}s"}},
            "allocationConfig": {"deviceConfigs": [{
                "requirement": {"deviceId": j["deviceId"]},
                "actions": [
                    {"androidPushFiles": {"fileConfigs": [
                        {"sourceFile": {"gcsInputFile": {"path": f"{bucket}/{p['object']}"}},
                         "destinationPath": p["device"]} for p in j["push"]]}},
                    {"androidPullFiles": {"paths": [OUTPUT_DIR]}},
                    {"androidLogcat": {}}]}]},
            "labels": j["labels"]} for j in jobs]}}


def uploads(p):
    """Unique bucket objects of the plan (the upload candidates)."""
    out = {}
    for j in p["jobs"]:
        for f in j["push"] + [j["wrapper"]]:
            out.setdefault(f["object"], f)
    return list(out.values())


def print_plan(p):
    for cell, reason, key in p["skips"]:
        print(json.dumps({"skip": run_campaign.cell_id(cell), "reason": reason,
                          **({"excludeOn": key} if key else {})}))
    for j in p["jobs"]:
        print(json.dumps({"job": j["index"], "session": j["session"], "displayName": j["displayName"],
                          "cell": j["cellId"], "stem": j["stem"], "runs": j["runs"], "cooldownSeconds": j["cooldown"],
                          "executionTimeout": f"{j['executionTimeout']}s", "perRunTimeoutSeconds": j["perRunTimeout"],
                          "args": j["args"], "labels": j["labels"],
                          "push": [{k: f.get(k) for k in ("kind", "device", "bytes", "sha256", "object", "uncached")
                                    if k in f} for f in j["push"]],
                          "pushBytes": sum(f["bytes"] or 0 for f in j["push"]), "estimate": j["estimate"]}))
    for s in p["sessions"]:
        print(json.dumps({"session": s["index"], "displayName": s["displayName"], "jobs": len(s["jobs"]),
                          "deviceMinutes": round(sum(j["estimate"]["jobSeconds"] for j in s["jobs"]) / 60, 1),
                          "request": s["request"]}))
    up = uploads(p)
    print(json.dumps({"uploadCandidates": [{"object": f["object"], "bytes": f["bytes"]} for f in up],
                      "uploadBytes": sum(f["bytes"] or 0 for f in up),
                      "uncached": sorted({f["name"] for f in up if f.get("uncached")})}))
    print(json.dumps({"summary": {"device": p["device"]["deviceId"], "scheduleKey": p["device"].get("scheduleKey"),
                                  "engine": p["engineTag"], "campaign": p["campaign"], "jobs": len(p["jobs"]),
                                  "sessions": len(p["sessions"]), "skipped": len(p["skips"]),
                                  "deviceMinutes": round(sum(j["estimate"]["jobSeconds"] for j in p["jobs"]) / 60, 1),
                                  "project": p["project"], "bucket": p["bucket"],
                                  "cpucapWaitSeconds": p["device"]["cpucapWait"]}}))
    print()
    head = ("job", "s", "cell", "runs", "cool", "t/run", "exec", "est s", "push MB")
    rows = [(str(j["index"]), str(j["session"]), j["cellId"], str(j["runs"]), str(j["cooldown"]),
             str(j["perRunTimeout"]), f"{j['executionTimeout']}s", str(j["estimate"]["jobSeconds"]),
             f"{sum(f['bytes'] or 0 for f in j['push']) / 1e6:.1f}") for j in p["jobs"]]
    widths = [max(len(r[i]) for r in rows + [head]) for i in range(len(head))]
    for r in [head] + rows:
        print("  ".join(c.ljust(w) for c, w in zip(r, widths)))
    print(f"{len(p['jobs'])} job(s) in {len(p['sessions'])} session(s) on {p['device']['deviceId']}, "
          f"{len(p['skips'])} row(s) skipped; upload candidates {len(up)} object(s), "
          f"{sum(f['bytes'] or 0 for f in up):,} bytes (existence not checked)")


# ---------------------------------------------------------------- the billed path (no --dry-run)

def gcloud(argv, check=True):
    r = subprocess.run(["gcloud"] + argv, capture_output=True, text=True)
    if check and r.returncode:
        raise SystemExit(f"gcloud {' '.join(argv)}: exit {r.returncode}: {r.stderr.strip()[-400:]}")
    return r


def access_token():
    return gcloud(["auth", "print-access-token"]).stdout.strip()


def rest(method, url, body=None):
    """-> (http status, parsed JSON or the raw text)."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Authorization": f"Bearer {access_token()}",
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            text = resp.read().decode()
            status = resp.status
    except urllib.error.HTTPError as exc:
        text, status = exc.read().decode(errors="replace"), exc.code
    try:
        return status, json.loads(text)
    except ValueError:
        return status, text


def write_json(path, obj):
    with open(path, "w") as fh:
        json.dump(obj, fh, indent=2)
        fh.write("\n")


def ensure_uploaded(p, bucket):
    for f in uploads(p):
        url = f"{bucket}/{f['object']}"
        if gcloud(["storage", "ls", url], check=False).returncode == 0:
            print(f"in bucket: {url}")
            continue
        if not f.get("local"):
            raise SystemExit(f"{f['name']}: no local file to upload")
        print(f"uploading {f['local']} ({f['bytes']:,} bytes) -> {url}", flush=True)
        gcloud(["storage", "cp", f["local"], url])


def run_session(s, campaign_dir, args, operation=None):
    ddp = os.path.join(campaign_dir, "ddp")
    n = s["index"]
    if operation is None:
        status, op = rest("POST", f"{args.endpoint}/projects/{args.project}/locations/global/sessions",
                          s["request"])
        if status >= 400 or not isinstance(op, dict) or "name" not in op:
            path = os.path.join(ddp, f"error-{n}.json")
            with open(path, "w") as fh:
                fh.write(op if isinstance(op, str) else json.dumps(op, indent=2))
            raise SystemExit(f"session {n}: POST answered {status}; body in {path}")
        write_json(os.path.join(ddp, f"operation-create-{n}.json"), op)
        operation = op["name"]
    print(f"session {n}: operation {operation}", flush=True)
    while True:
        status, op = rest("GET", f"{args.endpoint}/{operation}")
        write_json(os.path.join(ddp, f"operation-{n}.json"), op)
        if status >= 400:
            raise SystemExit(f"session {n}: GET operation answered {status} (ddp/operation-{n}.json)")
        if op.get("done"):
            break
        print(f"session {n}: not done ({time.strftime('%H:%M:%S')})", flush=True)
        time.sleep(args.poll_seconds)
    if op.get("error"):
        raise SystemExit(f"session {n}: operation error {op['error']} (ddp/operation-{n}.json)")
    target = op["metadata"]["target"]
    status, session = rest("GET", f"{args.endpoint}/{target}")
    write_json(os.path.join(ddp, f"session-{n}.json"), session)
    session_id = target.rsplit("/", 1)[-1]
    gcloud(["storage", "cp", "-r", f"{args.bucket}/automation/sessions/{session_id}", ddp])
    total = scrub_campaign(campaign_dir)
    print(f"session {n}: pulled logcats scrubbed ({total['files']} files, "
          + ", ".join(f"{k} {total[k]}" for k in scrub.KINDS) + f"; originals in {RAW_DIR}/)", flush=True)
    return session if isinstance(session, dict) and "sessionReport" in session else op.get("response", {})


def scrub_campaign(campaign_dir):
    """D12: every pulled logcat under <campaign>/ddp/ (run<i>_logcat.txt, the executions' logcat.txt)
    scrubbed in place by android/ddp/scrub.py with the SSIDs any of them names; each original kept once
    in <campaign>/ddp-raw/<the same path below ddp/> (never overwritten: a second scrub reads it, so the
    files and counts stay those of the pulled bytes); ddp/scrub.json = the counts per file.
    -> the totals (+ "files")."""
    ddp = os.path.join(campaign_dir, "ddp")
    files = sorted(p for p in glob.glob(os.path.join(ddp, "**", "*.txt"), recursive=True)
                   if LOGCAT.match(os.path.basename(p)))
    raw_dirs = {p: os.path.join(campaign_dir, RAW_DIR, os.path.relpath(os.path.dirname(p), ddp)) for p in files}
    ssids = set()
    for p in files:
        ssids |= scrub.ssid_values(scrub.original_text(p, raw_dirs[p]))
    entries, total = {}, dict.fromkeys(scrub.KINDS, 0)
    for p in files:
        counts = scrub.scrub_file(p, raw_dirs[p], ssids)
        for k in scrub.KINDS:
            total[k] += counts[k]
        entries[os.path.relpath(p, ddp)] = {**counts, "replaced": sum(counts.values()),
                                            "rawSha256": scrub.sha256_of(os.path.join(raw_dirs[p], os.path.basename(p)))}
    total.update(replaced=sum(total.values()), files=len(files))
    write_json(os.path.join(ddp, "scrub.json"), {
        "_doc": ("D12: the lab network's identifiers replaced in the pulled logcats by android/ddp/scrub.py "
                 "(kinds and their replacement: ssid <lab-ssid>, hash <hash>, ip6 <ip6>, mac <mac>, mac-part "
                 "<mac-part>, ip <ip>, id <id>); files: path below ddp/ -> replacements per kind, rawSha256 = "
                 f"sha256 of the file's bytes before the scrub, kept in {RAW_DIR}/<the same path> beside ddp/ "
                 "(gitignored, never committed). No number is read from a logcat."),
        "kinds": list(scrub.KINDS), "files": entries, "total": total})
    return total


def records_only(campaign_dir):
    """--records-only: the records of a DDP campaign dir written again from what its sessions pulled
    (ddp/plan-<n>.json, ddp/session-<n>.json or operation-<n>.json's response, ddp/<session>/), no
    network: the logcats scrubbed (scrub_campaign), then every record, raw log, decoded text and
    FAILURES.txt of the plans' cells in app-path-android/ removed and written again by record.py
    (same pull -> same ids and file names). SKIPPED.txt stays. -> exit code (1 = a run not clean)."""
    campaign_dir = os.path.abspath(campaign_dir)
    ddp = os.path.join(campaign_dir, "ddp")
    numbered = sorted((int(m.group(1)), p) for p in glob.glob(os.path.join(ddp, "plan-*.json"))
                      for m in [re.search(r"plan-([0-9]+)\.json$", p)] if m)
    if not numbered:
        raise SystemExit(f"{ddp}: no plan-<n>.json — not a DDP campaign dir")
    items = []
    for n, path in numbered:
        session = None
        if os.path.isfile(os.path.join(ddp, f"session-{n}.json")):
            session = load_json(os.path.join(ddp, f"session-{n}.json"))
        if not (isinstance(session, dict) and "sessionReport" in session):
            op_path = os.path.join(ddp, f"operation-{n}.json")
            session = (load_json(op_path).get("response") or {}) if os.path.isfile(op_path) else {}
        if "sessionReport" not in session:
            raise SystemExit(f"{ddp}: session {n} has no session report (session-{n}.json, operation-{n}.json) "
                             "— nothing removed, nothing written")
        items.append((n, load_json(path), session))
    total = scrub_campaign(campaign_dir)
    print(f"logcats scrubbed: {total['files']} files, " + ", ".join(f"{k} {total[k]}" for k in scrub.KINDS)
          + f" (ddp/scrub.json; originals in {RAW_DIR}/)")
    out_dir = os.path.join(campaign_dir, "app-path-android")
    os.makedirs(out_dir, exist_ok=True)
    stems = sorted({j["stem"] for _, s, _ in items for j in s["jobs"]})

    def derived():
        return sorted(f for f in os.listdir(out_dir)
                      if f == "FAILURES.txt" or any(f.startswith(stem + "_") for stem in stems))
    old = derived()
    for f in old:
        os.remove(os.path.join(out_dir, f))
    failed = 0
    for n, s, session in items:
        written, notes = record.write_session(s, session, campaign_dir, out_dir)
        for line in notes:
            print(line)
        failed += sum(1 for _, clean in written if not clean)
    new = derived()
    print(json.dumps({"recordsOnly": os.path.relpath(campaign_dir, ROOT), "sessions": len(items),
                      "removed": len(old), "written": len(new), "records": sum(f.endswith(".json") for f in new),
                      "notWrittenAgain": sorted(set(old) - set(new)), "newNames": sorted(set(new) - set(old))}))
    return 1 if failed else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cells", nargs="?")
    ap.add_argument("--device", help="DDP catalog id (android/ddp/devices.json)")
    ap.add_argument("--campaign", help="campaign dir name (default: env CAMPAIGN, else <date>-ddp-<id>-android)")
    ap.add_argument("--dry-run", action="store_true", help="plan, request bodies and estimate; no subprocess")
    ap.add_argument("--jobs-per-session", type=int, default=8)
    ap.add_argument("--job-timeout", type=int, default=3600, help="executionTimeout per job, s (API: 60-10800)")
    ap.add_argument("--resume", help="an operation name to poll instead of POSTing its session")
    ap.add_argument("--records-only", metavar="CAMPAIGN_DIR",
                    help="records again from a campaign dir's pulled output (no network); takes nothing else")
    ap.add_argument("--bin-dir", default=run_cell.ANDROID_BIN_DIR, help="holds <tag>/<engine files>")
    ap.add_argument("--bucket", default="gs://litert-edge-portal-devicerun",
                    help="gs://<bucket>[/<prefix>] for the inputs and the session outputs")
    ap.add_argument("--project", default="litert-edge-portal", help="the Cloud project of the sessions")
    ap.add_argument("--endpoint", default="https://devicerun.googleapis.com/v1alpha")
    ap.add_argument("--poll-seconds", type=float, default=30)
    args = ap.parse_args()
    if args.records_only:
        if args.cells or args.device or args.dry_run or args.resume or args.campaign:
            ap.error("--records-only takes the campaign dir alone")
        return records_only(args.records_only)
    if not args.cells or not args.device:
        ap.error("a cells file and --device are required (or --records-only <campaign dir>)")
    args.bucket = args.bucket.rstrip("/")
    if not re.fullmatch(r"gs://[^/\s]+(/\S+)?", args.bucket):
        ap.error(f"--bucket {args.bucket!r}: gs://<bucket>[/<prefix>]")
    if not args.project or re.search(r"[/\s]", args.project):
        ap.error(f"--project {args.project!r}: a Cloud project id")
    if not 60 <= args.job_timeout <= 10800:
        ap.error("--job-timeout must be within the API's [1 min, 3 hours]")
    if not 1 <= args.jobs_per_session <= 8:
        ap.error("--jobs-per-session: 1..8 (lane cap, D7)")
    campaign = (args.campaign or os.environ.get("CAMPAIGN")
                or f"{datetime.date.today().isoformat()}-ddp-{args.device}-android")
    p = plan(args.cells, args.device, campaign, args)
    print_plan(p)
    if args.dry_run or not p["jobs"]:
        return 0
    if any(f.get("uncached") for f in uploads(p)):
        raise SystemExit("a model is not in the local HF cache")
    raw_root = os.environ.get("BENCH_RAW_ROOT") or os.path.join(ROOT, "results", "raw")
    campaign_dir = os.path.join(raw_root, campaign)
    out_dir = os.path.join(campaign_dir, "app-path-android")
    if glob.glob(os.path.join(out_dir, "*.json")) and not args.resume:
        print(f"{out_dir} already holds records — a DDP campaign starts fresh (stored-report-rule)", file=sys.stderr)
        return 2
    os.makedirs(os.path.join(campaign_dir, "ddp"), exist_ok=True)
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "SKIPPED.txt"), "a") as fh:
        for cell, reason, key in p["skips"]:
            fh.write(f"CELL_SKIP {run_campaign.cell_id(cell)} "
                     + (f"exclude-on={key} " if key else "") + f"reason={reason}\n")
    for s in p["sessions"]:
        # the plan record.py builds the records from; host paths stay out of the campaign dir
        plan_s = json.loads(json.dumps({k: v for k, v in s.items() if k != "request"}))
        for j in plan_s["jobs"]:
            for f in j["push"] + [j["wrapper"]]:
                f.pop("local", None)
        write_json(os.path.join(campaign_dir, "ddp", f"plan-{s['index']}.json"), plan_s)
        write_json(os.path.join(campaign_dir, "ddp", f"request-{s['index']}.json"), s["request"])
    resume_name = None
    if args.resume:
        status, op = rest("GET", f"{args.endpoint}/{args.resume}")
        if status >= 400 or not isinstance(op, dict):
            raise SystemExit(f"--resume {args.resume}: GET answered {status}")
        resume_name = (op.get("response") or {}).get("sessionConfig", {}).get("displayName")
        if resume_name is None:
            status, sess = rest("GET", f"{args.endpoint}/{op['metadata']['target']}")
            resume_name = (sess.get("sessionConfig") or {}).get("displayName") if isinstance(sess, dict) else None
        if resume_name not in {s["displayName"] for s in p["sessions"]}:
            raise SystemExit(f"--resume: session {resume_name!r} is not one this plan makes")
    ensure_uploaded(p, args.bucket)
    failed = 0
    started = resume_name is None
    for s in p["sessions"]:
        if not started and s["displayName"] != resume_name:
            continue
        operation = args.resume if (resume_name and s["displayName"] == resume_name) else None
        started = True
        session = run_session(s, campaign_dir, args, operation)
        written, notes = record.write_session(s, session, campaign_dir, out_dir)
        for line in notes:
            print(line)
        failed += sum(1 for _, clean in written if not clean)
    print(f"\ncampaign dir: {campaign_dir}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
