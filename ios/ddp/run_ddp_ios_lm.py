#!/usr/bin/env python3
"""Runs one LiteRT-LM cell of the bench app on a Developer Device Platform (DDP) iPhone and writes its records.

DDP runs iOS as XCTest (`gcloud beta device-run sessions submit xctest`). The archive from
ios/ddp/build_xctest.sh holds the lab build of the app (ios/BenchmarkApp/project-ddp.yml) and its test
(Tests/DDP), which runs the app's own headless path once, in the app's process, with the words in
Documents/yardstick_args.json: the argv scripts/bench_matrix_iphone.sh gives the app on the attached
iPhone. One call = one cell = one session (one device, one job): the model is pushed from a
content-addressed object in --bucket (uploaded from the local HF cache only when it is missing),
the argv file from the campaign's ddp/ directory; Documents/results/ and Documents/out/ are pulled
back, and the app's records are written with the session's identity:

  <campaign>/device-jsonl/<the app's record name>   + device.ddp, conditions.ddp (build_summary reads it)
  <campaign>/console_<runtime>_<model>_<task>.txt   the run's stdout and stderr, under the attached
                                                    iPhone runner's name (appended, one header per session)
  <campaign>/ddp/<session>/                         plan.json, ddp_session.json, args.json, console.txt,
                                                    records.txt, yardstick.done
  <campaign>/ddp-raw/<session>/                     the pulled tree as the lab returned it (gitignored;
                                                    the lab's system.log and junit.xml are kept here)

  ios/ddp/run_ddp_ios_lm.py --device iphone16pro-18-3 --model-id litert-community/Qwen3-1.7B --backend gpu --dry-run
  ios/ddp/run_ddp_ios_lm.py --device iphone16pro-18-3 --model-id litert-community/Qwen3-1.7B --backend gpu  # billed
  ios/ddp/run_ddp_ios_lm.py … --collect <session id>     # wait for a session submitted earlier with the same flags
  ios/ddp/run_ddp_ios_lm.py --records-only results/raw/<campaign>/ddp/<session id>     # records again, no network

--dry-run prints the plan (JSON lines, then one table) and the gcloud command, and runs no subprocess:
no gcloud, no network (the model is looked up in the local HF cache only); paths are printed
relative to the repository, or with ~ for the home directory. The model ids are ios/ddp/models.json's.

Exit status (as litert-samples' run_ddp_ios.py): 0 the job passed and its records are written; 2 bad
inputs (a model id not in models.json, a timeout outside 1m-1h, no archive or one without a manifest
and BUILD_INFO, a device that is not an iPhone, a collected session that does not match the flags);
3 gcloud missing, or a gcloud command that failed or printed something unexpected before the session
ended; 4 the job did not pass (whatever records came back are written); 5 the job passed but no
record or no yardstick.done came back (also when the download failed); 130 interrupted, with the
session named so it can be cancelled.
"""
import argparse
import datetime
import hashlib
import json
import os
import pathlib
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
import zipfile

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
MODELS = HERE / "models.json"
DEFAULT_ARCHIVE = HERE / "out" / "BenchmarkApp-ddp-xctest.zip"
INPUTS = "automation/inputs/edge-llm-bench"
RUNTIME = "litert-lm"  # RuntimeKind.mediaPipe's raw value: --runtime, the model directory, the console name
MODEL_DIR = "/Documents/models/litert-lm"  # HFDownloader.modelDirectory(runtime: .mediaPipe, …)
ARGS_DEST = "/Documents/yardstick_args.json"
PULL = ("/Documents/results", "/Documents/out")
# --xctest-timeout by backend (results/raw/2026-10-16-build-ref-iphone-lm-dev/DESIGN-D1.md (f))
TIMEOUT = {"gpu": "15m", "cpu": "30m"}
# the wait past --xctest-timeout: the lab's preparation (install, a push of up to 2.6 GB) and cleanup
WAIT_MARGIN_MIN = 45
POLL_SECS = 30
DESCRIBE_TRIES = 3
FIND_TRIES = 6
LABEL_MAX = 63
CAMPAIGN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
DEVICE = re.compile(r"[a-z0-9][a-z0-9-]*")
SHA256 = re.compile(r"[0-9a-f]{64}")
EXIT_INPUT, EXIT_GCLOUD, EXIT_JOB, EXIT_RESULTS, EXIT_INTERRUPTED = 2, 3, 4, 5, 130


class InputError(Exception):
    """A bad input: exit 2."""


class GcloudError(Exception):
    """A gcloud command that could not run, failed, or printed something unexpected: exit 3."""


# ---------------------------------------------------------------- helpers

def shown(path) -> str:
    """A path as printed: relative to the repository when inside it, else with ~ for the home dir."""
    p = os.path.abspath(str(path))
    root, home = str(ROOT), os.path.expanduser("~")
    if p == root or p.startswith(root + os.sep):
        return os.path.relpath(p, root)
    if p.startswith(home + os.sep):
        return "~" + p[len(home):]
    return p


def label_value(text) -> str:
    """A label value in the GCP label form (lowercase, digits, - and _, <= 63 bytes), as android/ddp/run_ddp.py."""
    return re.sub(r"[^a-z0-9_-]", "-", str(text).lower())[:LABEL_MAX]


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def tail(text: str, lines: int = 8) -> str:
    return "\n".join(text.strip().splitlines()[-lines:])


def load_models() -> dict:
    with open(MODELS) as fh:
        return {k: v for k, v in json.load(fh).items() if not k.startswith("_")}


def parse_build_info(text: str) -> dict:
    """BUILD_INFO's key=value lines (build_xctest.sh)."""
    out = {}
    for line in (text or "").splitlines():
        key, sep, value = line.partition("=")
        if sep and key.strip():
            out[key.strip()] = value.strip()
    return out


def manifest_targets(manifest) -> list:
    """The test targets of an .xctestrun: FormatVersion 1 keeps them at the top level, 2 under
    TestConfigurations[].TestTargets[]."""
    if not isinstance(manifest, dict):
        return []
    targets = [v for v in manifest.values() if isinstance(v, dict)]
    for config in manifest.get("TestConfigurations") or []:
        targets += [t for t in (config.get("TestTargets") or []) if isinstance(t, dict)] if isinstance(config, dict) else []
    return targets


def read_archive(path: pathlib.Path) -> dict:
    """The archive's app bundle id (the manifest's TestHostBundleIdentifier), BUILD_INFO, manifest name, sha256."""
    bundle_id = build_info = manifest_name = None
    try:
        with zipfile.ZipFile(path) as zf:
            for name in zf.namelist():
                if name == "BUILD_INFO":
                    build_info = zf.read(name).decode(errors="replace").strip()
                elif name.endswith(".xctestrun") and "/" not in name.lstrip("./") and bundle_id is None:
                    for target in manifest_targets(plistlib.loads(zf.read(name))):
                        if target.get("TestHostBundleIdentifier"):
                            bundle_id = target["TestHostBundleIdentifier"]
                            manifest_name = name.lstrip("./")
                            break
    except (zipfile.BadZipFile, plistlib.InvalidFileException, ValueError, OSError):
        pass
    if not bundle_id or not build_info:
        raise InputError(f"{shown(path)} is not an archive from ios/ddp/build_xctest.sh (no manifest with a "
                         "TestHostBundleIdentifier, or no BUILD_INFO)")
    return {"local": str(path), "bytes": path.stat().st_size, "sha256": sha256_file(path), "bundleId": bundle_id,
            "manifest": manifest_name, "buildInfo": parse_build_info(build_info)}


def cached_file(hf_repo: str, filename: str):
    """The file of refs/main in the HF hub cache, read without huggingface_hub (a host without it)."""
    cache = os.environ.get("HF_HUB_CACHE") or os.path.join(
        os.environ.get("HF_HOME") or os.path.expanduser("~/.cache/huggingface"), "hub")
    repo_dir = os.path.join(cache, "models--" + hf_repo.replace("/", "--"))
    try:
        with open(os.path.join(repo_dir, "refs", "main")) as fh:
            commit = fh.read().strip()
    except OSError:
        return None
    path = os.path.join(repo_dir, "snapshots", commit, filename)
    return path if os.path.exists(path) else None


def model_file(hf_repo: str, filename: str, offline: bool) -> dict:
    """The model's file in the local HF cache and its sha256 (the blob's name, the LFS sha256).
    offline: the cache only, no network (uncached = no sha); else a download when it is not cached."""
    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        local = cached_file(hf_repo, filename) if offline else None
        if local is None and offline:
            return {"local": None, "bytes": None, "sha256": None,
                    "uncached": "not in the HF cache (huggingface_hub not installed)"}
        if local is None:
            raise InputError(f"{hf_repo} {filename}: huggingface_hub is not installed (pip install huggingface_hub)")
    else:
        try:
            local = hf_hub_download(hf_repo, filename, local_files_only=offline)
        except Exception as exc:  # noqa: BLE001 — a dry run's cache miss, or a failed download
            if offline:
                return {"local": None, "bytes": None, "sha256": None, "uncached": type(exc).__name__}
            raise InputError(f"{hf_repo} {filename}: download failed: {exc}")
    real = os.path.realpath(local)
    blob = os.path.basename(real)
    return {"local": real, "bytes": os.path.getsize(real),
            "sha256": blob if SHA256.fullmatch(blob) else sha256_file(real)}


def yardstick_args(model_id: str, task: str, runs: int, context_tokens, backend: str) -> list:
    """The app's argv after `--`, in scripts/bench_matrix_iphone.sh's order."""
    args = ["--yardstick-autorun", "--runtime", RUNTIME, "--model-id", model_id, "--task", task, "--runs", str(runs)]
    if context_tokens:
        args += ["--context-tokens", str(context_tokens)]
    return args + ["--litert-backend", backend]


def console_name(model_id: str, task: str) -> str:
    """scripts/bench_matrix_iphone.sh: console_$(echo "${rt}_${mid}_${task}" | tr '/.' '__').txt"""
    return "console_" + re.sub(r"[/.]", "_", f"{RUNTIME}_{model_id}_{task}") + ".txt"


def timeout_minutes(text: str) -> int:
    m = re.fullmatch(r"([1-9]\d*)([mh])", text or "")
    return int(m.group(1)) * (60 if m.group(2) == "h" else 1) if m else 0


# ---------------------------------------------------------------- the plan

def plan(args) -> dict:
    """Everything a submission needs, checked; no subprocess, no network in a dry run."""
    models = load_models()
    if args.model_id not in models:
        raise InputError(f"--model-id {args.model_id!r} is not in {shown(MODELS)} ({', '.join(sorted(models))})")
    if not DEVICE.fullmatch(args.device or ""):
        raise InputError(f"--device {args.device!r}: a DDP device id, e.g. iphone16pro-18-3")
    if not CAMPAIGN.fullmatch(args.campaign):
        raise InputError(f"--campaign {args.campaign!r}: ^[A-Za-z0-9][A-Za-z0-9._-]*$")
    if args.runs < 1:
        raise InputError(f"--runs {args.runs}: at least 1")
    if args.context_tokens is not None and args.context_tokens <= 0:
        raise InputError(f"--context-tokens {args.context_tokens}: a positive token count")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", args.task):
        raise InputError(f"--task {args.task!r}: a task id of the app (BenchmarkTaskCatalog), e.g. short-chat")
    timeout = args.timeout or TIMEOUT[args.backend]
    minutes = timeout_minutes(timeout)
    if not 1 <= minutes <= 60:
        raise InputError(f"--timeout {timeout!r} is not between 1m and 1h (the lab's --xctest-timeout range)")
    if not re.fullmatch(r"[a-z0-9][a-z0-9.-]*", args.xcode_version):
        raise InputError(f"--xcode-version {args.xcode_version!r}: an id of `gcloud beta device-run software-versions list`")
    archive_path = pathlib.Path(args.archive)
    if not archive_path.is_file():
        raise InputError(f"no test archive at {shown(archive_path)}; run ios/ddp/build_xctest.sh first")
    archive = read_archive(archive_path)
    archive["object"] = f"{INPUTS}/ios-xctest/{archive['sha256']}/{archive_path.name}"
    archive["url"] = f"{args.bucket}/{archive['object']}"
    entry = models[args.model_id]
    # the cache only: a billed run downloads an uncached model later, before its upload
    model = model_file(entry["hfRepoId"], entry["file"], offline=True)
    model["object"] = f"{INPUTS}/models/{model['sha256'] or 'UNCACHED'}/{entry['file']}"
    model["url"] = f"{args.bucket}/{model['object']}"
    bundle = archive["bundleId"]
    model["dest"] = f"{MODEL_DIR}/{entry['hfRepoId'].replace('/', '__')}/{entry['file']}"
    if args.flat_model_push:  # DDPHarness moves a file pushed into Documents/ to the model directory
        model["dest"] = f"/Documents/{entry['file']}"
    run = uuid.uuid4().hex[:12]
    campaign_dir = pathlib.Path(args.raw_root) / args.campaign
    args_file = campaign_dir / "ddp" / f"args-{run}.json"
    record_runtime = RUNTIME if args.backend == "gpu" else f"{RUNTIME}-cpu"  # MediaPipeRuntime.recordRuntimeLabel
    labels = {"harness": "edge-llm-bench", "campaign": label_value(args.campaign),
              "runtime": label_value(record_runtime), "model": label_value(args.model_id.replace("/", "--")),
              "task": label_value(args.task), "backend": args.backend, "deviceid": label_value(args.device),
              "engine": label_value(archive["buildInfo"].get("litert_lm", "unknown")), "run": run}
    for source in (model["url"], str(args_file)):
        if "," in source or "=" in source:
            raise InputError(f"{source}: gcloud takes no ',' or '=' in a pushed path")
    return {"device": args.device, "modelId": args.model_id, "hfRepoId": entry["hfRepoId"], "file": entry["file"],
            "backend": args.backend, "recordRuntime": record_runtime, "task": args.task, "runs": args.runs,
            "contextTokens": args.context_tokens, "timeout": timeout, "timeoutMinutes": minutes,
            "xcodeVersion": args.xcode_version, "project": args.project, "bucket": args.bucket,
            "campaign": args.campaign, "campaignDir": str(campaign_dir), "argsFile": str(args_file),
            "args": yardstick_args(args.model_id, args.task, args.runs, args.context_tokens, args.backend),
            "bundleId": bundle, "archive": archive, "model": model, "labels": labels, "run": run,
            "push": [{"source": model["url"], "dest": f"{bundle}:{model['dest']}"},
                     {"source": str(args_file), "dest": f"{bundle}:{ARGS_DEST}"}],
            "pull": [f"{bundle}:{p}" for p in PULL],
            "consoleName": console_name(args.model_id, args.task)}


def submit_command(p: dict) -> list:
    """The `sessions submit xctest` argv (gcloud's; --format and --project are added when it runs)."""
    return ["beta", "device-run", "sessions", "submit", "xctest",
            f"--device={p['device']}",
            f"--test={p['archive']['url']}",
            "--other-files-to-push=" + ",".join(f"{x['source']}={x['dest']}" for x in p["push"]),
            "--paths-to-pull=" + ",".join(p["pull"]),
            f"--xctest-timeout={p['timeout']}",
            f"--xcode-version={p['xcodeVersion']}",
            "--labels=" + ",".join(f"{k}={v}" for k, v in p["labels"].items()),
            "--async"]


def print_plan(p: dict, collect=None) -> None:
    m, a = p["model"], p["archive"]
    cmd = submit_command(p)
    shown_cmd = ["gcloud"] + [c.replace(p["argsFile"], shown(p["argsFile"])) for c in cmd] \
        + ["--format=json", f"--project={p['project']}"]
    print(json.dumps({"plan": {k: p[k] for k in ("device", "modelId", "file", "backend", "recordRuntime", "task",
                                                 "runs", "contextTokens", "timeout", "xcodeVersion", "bundleId",
                                                 "campaign", "run")}}))
    print(json.dumps({"args": p["args"]}))
    print(json.dumps({"model": {"local": shown(m["local"]) if m.get("local") else None, "bytes": m.get("bytes"),
                                "sha256": m.get("sha256"), "object": m["url"], "uncached": m.get("uncached")}}))
    print(json.dumps({"archive": {"local": shown(a["local"]), "bytes": a["bytes"], "sha256": a["sha256"],
                                  "manifest": a["manifest"], "object": a["url"], "buildInfo": a["buildInfo"]}}))
    print(json.dumps({"push": [{**x, "source": shown(x["source"]) if not x["source"].startswith("gs://")
                                else x["source"]} for x in p["push"]]}))
    print(json.dumps({"pull": p["pull"]}))
    print(json.dumps({"labels": p["labels"], "count": len(p["labels"])}))
    print(json.dumps({"command": shown_cmd}))
    rows = [("device", p["device"]),
            ("model", f"{p['modelId']} — {p['file']} ({m['bytes']:,} bytes, sha256 {m['sha256']})"
             if m.get("sha256") else f"{p['modelId']} — {p['file']} (not in the local HF cache: {m.get('uncached')})"),
            ("backend / record runtime", f"{p['backend']} / {p['recordRuntime']}"),
            ("task / runs / context", f"{p['task']} / {p['runs']} / {p['contextTokens'] or 'derived by the app'}"),
            ("push 1 (model)", f"{m['url']} → {p['push'][0]['dest']}"),
            ("push 2 (argv)", f"{shown(p['argsFile'])} → {p['push'][1]['dest']}"),
            ("pull", ", ".join(p["pull"])),
            ("--xctest-timeout", p["timeout"]),
            ("--xcode-version", p["xcodeVersion"]),
            (f"labels ({len(p['labels'])})", ", ".join(f"{k}={v}" for k, v in p["labels"].items())),
            ("archive", f"{shown(a['local'])} ({a['bytes']:,} bytes, sha256 {a['sha256']}) → {a['url']}"),
            ("archive BUILD_INFO", f"litert_lm={a['buildInfo'].get('litert_lm')}, "
                                   f"{a['buildInfo'].get('litert_lm_artifact')}, {a['buildInfo'].get('xcode')}"),
            ("records", f"{shown(p['campaignDir'])}/device-jsonl/, {p['consoleName']}")]
    print("\n| field | value |\n|---|---|")
    for k, v in rows:
        print(f"| {k} | {v} |")
    if collect:
        print(f"\n# collecting session {collect}, submitting nothing")
    else:
        print("\n# " + " ".join(shown_cmd))


# ---------------------------------------------------------------- gcloud (the billed path)

def gcloud(*args, project=None) -> str:
    cmd = ["gcloud", *args] + ([f"--project={project}"] if project else [])
    try:
        res = subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError:
        raise GcloudError("gcloud is not on PATH; install the Google Cloud CLI and log in") from None
    if res.returncode != 0:
        raise GcloudError(f"`{' '.join(cmd[:6])} ...` failed:\n{tail(res.stderr)}")
    return res.stdout


def gcloud_json(*args, project=None):
    out = gcloud(*args, "--format=json", project=project)
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        raise GcloudError(f"`gcloud {' '.join(args[:6])} ...` printed no JSON:\n{tail(out)}") from None


def object_exists(url: str) -> bool:
    try:
        res = subprocess.run(["gcloud", "storage", "ls", url], capture_output=True, text=True)
    except FileNotFoundError:
        raise GcloudError("gcloud is not on PATH; install the Google Cloud CLI and log in") from None
    return res.returncode == 0


def ensure_object(local, url: str) -> None:
    """Uploads `local` to `url` unless an object is already there (content-addressed: same path, same bytes)."""
    if object_exists(url):
        print(f"in bucket: {url}")
        return
    if not local:
        raise InputError(f"{url} is not in the bucket and there is no local file to upload")
    print(f"uploading {shown(local)} ({os.path.getsize(local):,} bytes) -> {url}", flush=True)
    gcloud("storage", "cp", str(local), url)


def catalog_device(device_id: str, project) -> dict | None:
    for entry in gcloud_json("beta", "device-run", "devices", "list", project=project):
        if isinstance(entry, dict) and entry.get("name", "").rsplit("/", 1)[-1] == device_id:
            return entry
    return None


def session_id(submitted) -> str | None:
    """The session id from what `submit --async` printed, when it printed one (gcloud 587 prints [])."""
    if isinstance(submitted, list):
        submitted = next((s for s in submitted if isinstance(s, dict)), {})
    if not isinstance(submitted, dict):
        return None
    for value in (submitted.get("name"), (submitted.get("metadata") or {}).get("session")):
        if isinstance(value, str) and "/sessions/" in value:
            return value.rsplit("/", 1)[-1]
    return None


def session_labels(session: dict) -> dict:
    jobs = (session.get("sessionConfig") or {}).get("jobConfigs") or []
    return (jobs[0].get("labels") or {}) if jobs and isinstance(jobs[0], dict) else {}


def session_device(session: dict):
    jobs = (session.get("sessionConfig") or {}).get("jobConfigs") or []
    configs = ((jobs[0].get("allocationConfig") or {}).get("deviceConfigs") or []) if jobs else []
    return ((configs[0].get("requirement") or {}).get("deviceId")) if configs else None


def find_session(run: str, project) -> str | None:
    """The id of the session labelled run=<run> in `sessions list`; retried while the list lags."""
    for attempt in range(FIND_TRIES):
        for session in gcloud_json("beta", "device-run", "sessions", "list", project=project):
            if isinstance(session, dict) and session_labels(session).get("run") == run:
                return session.get("name", "").rsplit("/", 1)[-1] or None
        if attempt + 1 < FIND_TRIES:
            time.sleep(10)
    return None


def describe(sid: str, project) -> dict:
    for attempt in range(DESCRIBE_TRIES):
        try:
            session = gcloud_json("beta", "device-run", "sessions", "describe", sid, "--full", project=project)
            return session if isinstance(session, dict) else {}
        except GcloudError:
            if attempt + 1 == DESCRIBE_TRIES:
                raise
            time.sleep(POLL_SECS)
    raise AssertionError("unreachable")


def wait_for_session(sid: str, project, max_secs: float) -> dict:
    deadline = time.monotonic() + max_secs
    while True:
        session = describe(sid, project)
        report = session.get("sessionReport") or {}
        status = (report.get("status") or {}).get("statusType", "pending")
        if status == "DONE" or report.get("endTime"):
            return session
        if time.monotonic() >= deadline:
            raise GcloudError(f"session {sid} is still {status} after {int(max_secs)} s; "
                              f"`gcloud beta device-run sessions cancel {sid}` stops it")
        print(f"# {status}; next check in {POLL_SECS} s", flush=True)
        time.sleep(POLL_SECS)


def execution_prefix(job: dict):
    """The GCS directory of the job's execution, from any of its output files."""
    for execution in job.get("executionReports") or []:
        for f in execution.get("outputFiles") or []:
            m = re.match(r"(.*/execution-[^/]+/)", (f.get("gcsOutputFile") or {}).get("path", ""))
            if m:
                return m.group(1)
    return None


# ---------------------------------------------------------------- records

def home_as_tilde(obj):
    """obj with the home directory written as ~ in every string: plan.json is committed, and the argv file,
    the campaign directory and the argv push source are host paths."""
    home = os.path.expanduser("~").rstrip(os.sep)
    if isinstance(obj, str):
        return obj.replace(home + os.sep, "~" + os.sep) if home else obj
    if isinstance(obj, dict):
        return {k: home_as_tilde(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [home_as_tilde(v) for v in obj]
    return obj


def write_json(path: pathlib.Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as fh:
        json.dump(obj, fh, indent=2, sort_keys=True)
        fh.write("\n")


def pulled_index(raw_dir: pathlib.Path) -> dict:
    """Pulled file name -> path. The lab drops the device path (artifacts/<name>), so files are found by
    name; of two files of one name, the shallower path is taken."""
    index = {}
    for p in sorted(raw_dir.rglob("*"), key=lambda q: (len(q.relative_to(raw_dir).parts), str(q))):
        if p.is_file() and p.name not in index:
            index[p.name] = p
    return index


def ddp_conditions(sid: str, p: dict, session: dict) -> dict:
    report = session.get("sessionReport") or {}
    job = next(iter(report.get("jobReports") or []), {}) or {}
    ex = next(iter(job.get("executionReports") or []), {}) or {}
    jobs = (session.get("sessionConfig") or {}).get("jobConfigs") or [{}]
    action = ((jobs[0] or {}).get("action") or {}).get("iosXcTest") or {}
    prefix = execution_prefix(job)
    return {"sessionId": sid, "jobId": job.get("id"), "jobName": job.get("displayName"),
            "executionId": ex.get("id"),
            "executionDir": prefix.rstrip("/").rsplit("/", 1)[-1] if prefix else None,
            "deviceId": p["device"],
            "sessionStartTime": report.get("startTime"), "sessionEndTime": report.get("endTime"),
            "jobStartTime": job.get("startTime"), "jobEndTime": job.get("endTime"),
            "executionStartTime": ex.get("startTime"), "executionEndTime": ex.get("endTime"),
            "xctestTimeout": action.get("xcTestTimeout") or p["timeout"],
            "xcodeVersion": action.get("xcodeVersion") or p["xcodeVersion"],
            "resultType": (job.get("result") or {}).get("resultType"),
            "runLabel": session_labels(session).get("run") or p["run"],
            "argv": p["args"],
            "modelObject": p["model"]["url"], "modelSha256": p["model"]["sha256"],
            "modelDestination": p["push"][0]["dest"],
            "archiveObject": p["archive"]["url"], "archiveSha256": p["archive"]["sha256"],
            "archiveBuildInfo": p["archive"]["buildInfo"]}


def lay_out(session_dir: pathlib.Path) -> dict:
    """Writes the session's records, console and lab files from <campaign>/ddp/<session>/ (plan.json,
    ddp_session.json) and <campaign>/ddp-raw/<session>/ (the pulled tree). No network; the same files
    again on a second call. -> {"records": n, "done": code or None, "notes": [...]}"""
    p = json.loads((session_dir / "plan.json").read_text())
    session = json.loads((session_dir / "ddp_session.json").read_text())
    sid = session_dir.name
    campaign_dir = session_dir.parent.parent
    raw_dir = campaign_dir / "ddp-raw" / sid
    index = pulled_index(raw_dir) if raw_dir.is_dir() else {}
    notes = []
    for name in ("records.txt", "yardstick.done", "console.txt"):
        if name in index:
            shutil.copyfile(index[name], session_dir / name)
        else:
            notes.append(f"no {name} came back")
    names = []
    if "records.txt" in index:
        names = [n.strip() for n in index["records.txt"].read_text().splitlines() if n.strip()]
    else:  # an older test, or a run that ended before writing it: the cell's own record names
        prefix = f"{p['recordRuntime']}_{p['modelId'].replace('/', '_')}_{p['task']}_"
        names = sorted(n for n in index if n.startswith(prefix) and n.endswith(".json"))
    catalog = p.get("catalog") or {}
    device_ddp = {"deviceId": p["device"], "displayName": catalog.get("displayName"),
                  "osVersion": catalog.get("osVersion")}
    cond = ddp_conditions(sid, p, session)
    out = campaign_dir / "device-jsonl"
    records = []
    for name in names:
        if name not in index:
            notes.append(f"{name} is named in records.txt but did not come back")
            continue
        if name.endswith(".ndjson"):  # an endurance session's turn series, beside its record
            out.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(index[name], out / name)
            continue
        if not name.endswith(".json"):
            continue
        try:
            rec = json.loads(index[name].read_text())
        except (OSError, ValueError) as exc:
            notes.append(f"{name}: not a JSON record ({exc})")
            continue
        got = (rec.get("runtime"), (rec.get("model") or {}).get("id"), rec.get("task"))
        if got != (p["recordRuntime"], p["modelId"], p["task"]):
            notes.append(f"{name}: runtime / model / task {got} is not this cell's; not written")
            continue
        records.append((rec.get("timestamp") or "", name, rec))
    for i, (_, name, rec) in enumerate(sorted(records), 1):
        rec.setdefault("device", {})["ddp"] = device_ddp
        rec.setdefault("conditions", {})["ddp"] = {**cond, "runIndex": i}
        write_json(out / name, rec)
    if "console.txt" in index:
        console = campaign_dir / p["consoleName"]
        header = (f"=== DDP session {sid}: {p['device']}, {p['recordRuntime']}, {p['modelId']}, {p['task']}, "
                  f"runs={p['runs']} ===")
        before = console.read_text(errors="replace") if console.exists() else ""
        if header not in before:
            with open(console, "a") as fh:
                fh.write(header + "\n" + index["console.txt"].read_text(errors="replace"))
    done = None
    try:
        done = int((session_dir / "yardstick.done").read_text().strip())
    except (OSError, ValueError):
        pass
    return {"records": len(records), "done": done, "notes": notes}


def records_only(session_dir: pathlib.Path) -> int:
    for name in ("plan.json", "ddp_session.json"):
        if not (session_dir / name).is_file():
            print(f"run_ddp_ios_lm.py: --records-only {shown(session_dir)}: no {name} (the dir a run or "
                  "--collect wrote under <campaign>/ddp/)", file=sys.stderr)
            return EXIT_INPUT
    result = lay_out(session_dir)
    p = json.loads((session_dir / "plan.json").read_text())
    for note in result["notes"]:
        print(f"# {note}")
    print(f"{result['records']} record(s) of {p['runs']} run(s) -> {shown(session_dir.parent.parent / 'device-jsonl')}; "
          f"yardstick.done {result['done']}")
    return 0 if result["records"] else EXIT_RESULTS


# ---------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--device", help="a DDP iPhone id (gcloud beta device-run devices list), e.g. iphone16pro-18-3")
    ap.add_argument("--model-id", help="an id of ios/ddp/models.json (the app's catalog id)")
    ap.add_argument("--backend", choices=["cpu", "gpu"], help="the app's --litert-backend (arm identity)")
    ap.add_argument("--task", default="short-chat", help="the app's --task (default: %(default)s)")
    ap.add_argument("--runs", type=int, default=4, help="the app's --runs: run 1 cold, 2..N warm (default: %(default)s)")
    ap.add_argument("--context-tokens", type=int, help="the app's --context-tokens (default: derived by the app)")
    ap.add_argument("--archive", default=str(DEFAULT_ARCHIVE), help="the archive build_xctest.sh wrote (default: %(default)s)")
    ap.add_argument("--campaign", default=None,
                    help="results/raw/<campaign> (default: <today>-ddp-<device>-ios)")
    ap.add_argument("--timeout", default=None, help="the lab's --xctest-timeout, 1m to 1h (default: gpu 15m, cpu 30m)")
    ap.add_argument("--xcode-version", default="xcode-26-2", help="the lab's Xcode (software-versions list; default: %(default)s)")
    ap.add_argument("--project", default=os.environ.get("BENCH_DDP_PROJECT", "litert-edge-portal"),
                    help="the Cloud project the session is billed to (default: %(default)s)")
    ap.add_argument("--bucket", default="gs://litert-edge-portal-devicerun",
                    help="gs://<bucket>[/<prefix>] for the content-addressed inputs (default: %(default)s)")
    ap.add_argument("--flat-model-push", action="store_true",
                    help="push the model to Documents/<file>; the test moves it into the app's model directory")
    ap.add_argument("--dry-run", action="store_true", help="print the plan and the gcloud command; run nothing")
    ap.add_argument("--collect", metavar="SESSION_ID",
                    help="submit nothing: wait for this session (submitted with the same flags) and write its records")
    ap.add_argument("--records-only", metavar="SESSION_DIR",
                    help="records again from results/raw/<campaign>/ddp/<session> (no network); takes nothing else")
    args = ap.parse_args()
    if args.records_only:
        if args.device or args.model_id or args.backend or args.collect or args.dry_run:
            ap.error("--records-only takes the session dir alone")
        return records_only(pathlib.Path(args.records_only))
    if not (args.device and args.model_id and args.backend):
        ap.error("--device, --model-id and --backend are required (or --records-only <session dir>)")
    args.bucket = args.bucket.rstrip("/")
    if not re.fullmatch(r"gs://[^/\s]+(/\S+)?", args.bucket):
        ap.error(f"--bucket {args.bucket!r}: gs://<bucket>[/<prefix>]")
    if not args.project or re.search(r"[/\s]", args.project):
        ap.error(f"--project {args.project!r}: a Cloud project id")
    args.campaign = args.campaign or f"{datetime.date.today().isoformat()}-ddp-{args.device}-ios"
    args.raw_root = os.environ.get("BENCH_RAW_ROOT") or str(ROOT / "results" / "raw")
    try:
        p = plan(args)
    except InputError as e:
        print(f"run_ddp_ios_lm.py: {e}", file=sys.stderr)
        return EXIT_INPUT
    print_plan(p, collect=args.collect)
    if args.dry_run:
        return 0

    campaign_dir = pathlib.Path(p["campaignDir"])
    ddp_dir = campaign_dir / "ddp"
    sid = args.collect
    try:
        ddp_dir.mkdir(parents=True, exist_ok=True)
        pathlib.Path(p["argsFile"]).write_text(json.dumps(p["args"]) + "\n")
        device = catalog_device(p["device"], p["project"])
        if device is None or str(device.get("platform")).lower() != "ios":
            print(f"run_ddp_ios_lm.py: {p['device']} is "
                  f"{'not in the catalog' if device is None else device.get('platform')}, not an iPhone; "
                  "`gcloud beta device-run devices list` shows the ids", file=sys.stderr)
            return EXIT_INPUT
        p["catalog"] = {k: device.get(k) for k in ("name", "displayName", "osVersion", "modelCode", "platform")}
        if sid is None:
            if p["model"].get("uncached") or not p["model"].get("sha256"):
                p["model"].pop("uncached", None)
                p["model"].update(model_file(p["hfRepoId"], p["file"], offline=False))
                p["model"]["object"] = f"{INPUTS}/models/{p['model']['sha256']}/{p['file']}"
                p["model"]["url"] = p["push"][0]["source"] = f"{p['bucket']}/{p['model']['object']}"
            ensure_object(p["model"].get("local"), p["model"]["url"])
            ensure_object(p["archive"]["local"], p["archive"]["url"])
            submitted = gcloud_json(*submit_command(p), project=p["project"])
            sid = session_id(submitted) or find_session(p["run"], p["project"])
            if sid is None:
                raise GcloudError(f"the submission printed no session id and no session carries the label "
                                  f"run={p['run']}; `gcloud beta device-run sessions list` shows what was submitted")
            print(f"# session {sid}; `gcloud beta device-run sessions cancel {sid}` stops it", flush=True)
        session_dir = ddp_dir / sid
        session_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p["argsFile"], session_dir / "args.json")
        os.remove(p["argsFile"])
        plan_out = home_as_tilde(json.loads(json.dumps(p)))
        for part in ("model", "archive"):
            plan_out[part].pop("local", None)  # host paths stay out of the campaign dir
        plan_out["sessionId"] = sid
        write_json(session_dir / "plan.json", plan_out)
        session = wait_for_session(sid, p["project"], (p["timeoutMinutes"] + WAIT_MARGIN_MIN) * 60)
    except InputError as e:
        print(f"run_ddp_ios_lm.py: {e}", file=sys.stderr)
        return EXIT_INPUT
    except GcloudError as e:
        print(f"run_ddp_ios_lm.py: {e}", file=sys.stderr)
        return EXIT_GCLOUD
    except KeyboardInterrupt:
        what = f"session {sid}" if sid else f"the session labelled run={p['run']}, if the submission went through"
        print(f"\nrun_ddp_ios_lm.py: interrupted; {what} keeps running until it ends or "
              "`gcloud beta device-run sessions cancel <id>` stops it", file=sys.stderr)
        return EXIT_INTERRUPTED

    if args.collect:
        labels = session_labels(session)
        expected = {"model": p["labels"]["model"], "backend": p["backend"], "task": p["labels"]["task"]}
        mismatch = [f"{k} {labels.get(k)!r}" for k, v in expected.items() if labels.get(k) != v]
        if session_device(session) != p["device"]:
            mismatch.append(f"device {session_device(session)!r}")
        if mismatch:
            print(f"run_ddp_ios_lm.py: session {sid} ran {', '.join(mismatch)}, not what the flags say; "
                  "pass the flags it was submitted with", file=sys.stderr)
            return EXIT_INPUT
        plan_out["run"] = labels.get("run") or p["run"]
        write_json(session_dir / "plan.json", plan_out)
    write_json(session_dir / "ddp_session.json", session)
    report = session.get("sessionReport") or {}
    jobs = report.get("jobReports") or []
    if len(jobs) != 1:
        print(f"run_ddp_ios_lm.py: session {sid} reports {len(jobs)} jobs for one device; "
              f"see {shown(session_dir / 'ddp_session.json')}", file=sys.stderr)
        return EXIT_GCLOUD
    result = (jobs[0].get("result") or {}).get("resultType", "UNKNOWN")
    print(f"\njob {jobs[0].get('displayName') or jobs[0].get('id')}: {result}")
    raw_dir = campaign_dir / "ddp-raw" / sid
    prefix = execution_prefix(jobs[0])
    try:
        if prefix is not None:
            raw_dir.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(dir=raw_dir) as tmp:
                gcloud("storage", "cp", "-r", f"{prefix}artifacts", f"{prefix}system.log", f"{prefix}junit.xml",
                       f"{tmp}/")
                for item in pathlib.Path(tmp).iterdir():
                    target = raw_dir / item.name
                    if target.exists():
                        shutil.rmtree(target) if target.is_dir() else target.unlink()
                    shutil.move(str(item), target)
    except GcloudError as e:
        print(f"run_ddp_ios_lm.py: {e}", file=sys.stderr)  # the verdict below says what is missing
    except KeyboardInterrupt:
        print(f"\nrun_ddp_ios_lm.py: interrupted while downloading; `--collect {sid}` writes it later", file=sys.stderr)
        return EXIT_INTERRUPTED
    laid = lay_out(session_dir)
    for note in laid["notes"]:
        print(f"# {note}")
    console = session_dir / "console.txt"
    for line in console.read_text(errors="replace").splitlines() if console.exists() else []:
        if line.startswith(("YARDSTICK_RUN_OK", "YARDSTICK_RUN_FAIL", "YARDSTICK_FATAL", "YARDSTICK_ALL_DONE")):
            print("  " + line[:200])
    print(f"{laid['records']} record(s) -> {shown(campaign_dir / 'device-jsonl')}; yardstick.done {laid['done']}; "
          f"session files {shown(session_dir)}")
    if result != "PASSED":
        junit = raw_dir / "junit.xml"
        detail = tail(junit.read_text(errors="replace"), 12) if junit.exists() else "no junit.xml came back"
        print(f"run_ddp_ios_lm.py: the job ended {result}; {detail}", file=sys.stderr)
        return EXIT_JOB
    if not laid["records"] or laid["done"] is None:
        print(f"run_ddp_ios_lm.py: the job passed but {'no record' if not laid['records'] else 'no yardstick.done'} "
              f"came back (a run past --xctest-timeout {p['timeout']} leaves this too)", file=sys.stderr)
        return EXIT_RESULTS
    return 0


if __name__ == "__main__":
    sys.exit(main())
