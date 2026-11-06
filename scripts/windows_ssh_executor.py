#!/usr/bin/env python3
"""Runs the windows rows of cells files on a Windows PC reached over SSH.

The transport of scripts/run_windows_matrix.py (`register_executor`, the runner's contract
fn(plan, campaign_dir, args) -> int): it stages the pinned llama.cpp zips and windows/run_job.ps1 on the
host, starts the job detached so that it outlives the SSH connection, waits for it, pulls the logs into
<campaign>/host-logs/<invocation>/ and writes the records with run_windows_matrix.write_records.

  scripts/windows_ssh_executor.py matrices/dashboard-windows-v1.cells --campaign <date>-windows \\
      --litert-label v0.19.0 \\
      --model-file litert-lm:<id>=<file on the host>:<bytes> --model-file llama.cpp:<id>=<file>:<bytes>

The model files are on the host already (BENCH_WINDOWS_MODEL_DIR); a --model-file names one by its bare file
name and size. LiteRT-LM has no Windows release asset: its build sits in <root>\\engines\\litert and its sha256
comes from windows/engine-pins.json, or from BENCH_EXTRA_PINS (windows_litert-lm) for a label not listed there;
windows/build_litert_lm.ps1 makes that dir and that entry. The NPU row loads OpenVINO from <root>\\engines\\openvino
(the runtime's bin\\intel64\\Release and tbb\\bin DLLs). Environment:

  BENCH_WINDOWS_SSH_HOST      ssh host (default winpc)
  BENCH_WINDOWS_ROOT          working dir on the host (default <the host's %USERPROFILE%>\\bench)
  BENCH_WINDOWS_MODEL_DIR     model dir on the host (default <the host's %USERPROFILE%>\\models)
  BENCH_WINDOWS_DEVICE_MODEL  device.modelIdentifier (default the host's Win32_ComputerSystem.Model)
  BENCH_WINDOWS_BUSY_FILE     marker of a shared host, on the host; the job waits for another lane's and
                              holds its own while it measures
  BENCH_WINDOWS_BUSY_LABEL    this lane's name in that marker
  BENCH_WINDOWS_VK_DEVICES    GGML_VK_VISIBLE_DEVICES for the Vulkan llama.cpp rows (a host with two GPUs)
  BENCH_WINDOWS_LITERT_DIR    the dir under <root>\\engines of the LiteRT-LM build to run (default litert)
  BENCH_WINDOWS_INVOCATION    an invocation to resume (its finished runs are kept)

Before anything runs on the host, a job with LiteRT-LM rows stops (exit 1) when --litert-label is in neither
windows/engine-pins.json nor BENCH_EXTRA_PINS, or when the files in <root>\\engines\\<dir> are not that label's build:
its records would name no engine.
"""

import datetime
import functools
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time
import uuid

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import run_windows_matrix as rwm  # noqa: E402

HARNESS = "scripts/windows_ssh_executor.py"
RUN_JOB = rwm.REPO / "windows" / "run_job.ps1"
POLL_SECONDS = 30
# The host is unreachable for this long -> stop waiting; the job goes on over there and BENCH_WINDOWS_INVOCATION
# picks it up later.
UNREACHABLE_LIMIT_SECONDS = 600


def env(name: str, default: str = "") -> str:
    return os.environ.get(name) or default


def host() -> str:
    return env("BENCH_WINDOWS_SSH_HOST", "winpc")


def ssh(command: str, timeout: int = 300, check: bool = True, runner=subprocess.run) -> subprocess.CompletedProcess:
    """One PowerShell command on the host; its stdout as text."""
    full = "[Console]::OutputEncoding = [Text.Encoding]::UTF8; " + command
    done = runner(["ssh", "-o", "ConnectTimeout=20", host(), full], capture_output=True, text=True,
                  errors="replace", timeout=timeout, check=False)
    if check and done.returncode != 0:
        raise RuntimeError(f"ssh {host()}: exit {done.returncode}: {done.stderr.strip()[:500]}")
    return done


@functools.lru_cache(maxsize=1)
def host_home() -> str:
    return ssh("$env:USERPROFILE").stdout.strip().splitlines()[-1]


def root() -> str:
    return env("BENCH_WINDOWS_ROOT") or f"{host_home()}\\bench"


def model_dir() -> str:
    return env("BENCH_WINDOWS_MODEL_DIR") or f"{host_home()}\\models"


def scp_up(local: pathlib.Path, remote: str, runner=subprocess.run) -> None:
    # scp reads a remote path with a colon after the host: C:/Users/... (forward slashes) is what it takes
    target = f"{host()}:{remote.replace(chr(92), '/')}"
    runner(["scp", "-q", "-r", str(local), target], check=True, timeout=1800)


def scp_down(remote: str, local: pathlib.Path, runner=subprocess.run) -> None:
    source = f"{host()}:{remote.replace(chr(92), '/')}"
    runner(["scp", "-q", "-r", source, str(local)], check=True, timeout=1800)


def stage_llama(plan: rwm.Plan, args) -> None:
    """The pinned zips, verified on this machine, expanded on the host under engines\\<tool>\\."""
    if not plan.labels:
        return
    pins = rwm.load_pins()
    zips = rwm.fetch_engines(args.engines_dir, pins, sorted(set(plan.labels.values())))
    for tool, label in sorted(plan.labels.items()):
        artifact = pins[label]["artifact"]
        remote_dir = f"{root()}\\engines\\{tool}"
        have = ssh(f"$p = '{remote_dir}\\llama-cli.exe'; if (Test-Path $p) "
                   "{ (Get-FileHash -Algorithm SHA256 $p).Hash.ToLower() }").stdout.strip()
        if have == pins[label]["llama_cli_sha256"]:
            print(f"  {tool}: {label} already on the host")
            continue
        ssh(f"New-Item -ItemType Directory -Force '{remote_dir}' | Out-Null")
        scp_up(zips[label], f"{remote_dir}\\{artifact}")
        ssh(f"Expand-Archive -Force '{remote_dir}\\{artifact}' '{remote_dir}'; "
            f"Remove-Item '{remote_dir}\\{artifact}'", timeout=600)
        print(f"  {tool}: {label} expanded on the host")


def check_litert_build(plan: rwm.Plan, label: str, runner=subprocess.run) -> None:
    """Refuses, before anything runs, a LiteRT-LM job whose records would name no engine (windows/README.md, Setup 2).

    The label has to be in windows/engine-pins.json or BENCH_EXTRA_PINS, and the files in <root>\\engines\\<dir> have to
    be that label's build: a rebuild of the same commit differs by sha256, and its records would say unknown.
    """
    if not any(row.runtime == "litert-lm" for row in plan.rows):
        return
    pin = rwm.load_litert_pins().get(label)
    if pin is None:
        raise RuntimeError(f"--litert-label {label!r} is in neither windows/engine-pins.json nor BENCH_EXTRA_PINS, so "
                           "the LiteRT-LM records would name no engine: pass the build's own label and point "
                           "BENCH_EXTRA_PINS at the pins.json its build script wrote (windows/README.md, Setup 2)")
    want = dict(pin.get("dll_files") or {})
    want[rwm.LITERT_EXE] = pin.get("litert_lm_advanced_main_windows_sha256") or pin.get("sha256")
    engine_dir = f"{root()}\\engines\\{env('BENCH_WINDOWS_LITERT_DIR', 'litert')}"
    listing = ssh(f"Get-ChildItem '{engine_dir}' -File -ErrorAction SilentlyContinue | ForEach-Object "
                  "{ 'FILE ' + $_.Name + ' ' + (Get-FileHash -Algorithm SHA256 $_.FullName).Hash.ToLower() }",
                  runner=runner).stdout
    have = dict(line.split()[1:3] for line in listing.splitlines() if line.startswith("FILE ") and len(line.split()) == 3)
    bad = sorted(name for name, sha in want.items() if have.get(name) != sha)
    if bad:
        raise RuntimeError(f"{engine_dir} is not the build of --litert-label {label!r} ({', '.join(bad)} differ or "
                           "are missing): pass that build's own label and its pins.json (windows/README.md, Setup 2)")


def write_job(plan: rwm.Plan, job_dir: pathlib.Path) -> None:
    """job.json + prompts\\<task>.txt, what run_job.ps1 reads."""
    job = json.loads(json.dumps(plan.job))
    vk = env("BENCH_WINDOWS_VK_DEVICES")
    for launch in job["launches"]:
        if vk and launch["tool"] == "llama-gpu":
            launch["env"] = {"GGML_VK_VISIBLE_DEVICES": vk}
        if "--backend=npu" in launch["args"]:
            # the Intel dispatch loads OpenVINO from PATH (Google's page: setupvars.ps1)
            launch["env"] = {"Path": f"{root()}\\engines\\openvino;%PATH%"}
    (job_dir / "job.json").write_text(json.dumps(job, indent=1), encoding="utf-8")
    prompts = job_dir / "prompts"
    prompts.mkdir(parents=True, exist_ok=True)
    for row in plan.rows:
        (prompts / f"{row.task}.txt").write_bytes(rwm.prompt_file(row.task).read_bytes())


def run_job_command(job_dir: str, log_dir: str, purge: bool = False) -> str:
    words = [
        "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", f'"{root()}\\run_job.ps1"',
        "-JobDir", f'"{job_dir}"', "-LogDir", f'"{log_dir}"',
        "-ModelDir", f'"{model_dir()}"',
        "-EngineDir", f'"{root()}\\engines"',
    ]
    if env("BENCH_WINDOWS_DEVICE_MODEL"):
        words += ["-DeviceModel", f'"{env("BENCH_WINDOWS_DEVICE_MODEL")}"']
    if env("BENCH_WINDOWS_BUSY_FILE"):
        words += ["-BusyFile", f'"{env("BENCH_WINDOWS_BUSY_FILE")}"',
                  "-BusyLabel", f'"{env("BENCH_WINDOWS_BUSY_LABEL", "windows-job")}"']
    if env("BENCH_WINDOWS_LITERT_DIR"):
        words += ["-LitertDirName", f'"{env("BENCH_WINDOWS_LITERT_DIR")}"']
    if purge:
        words.append("-PurgeEngineCaches")
    return " ".join(words)


def start_detached(command: str) -> None:
    """Through WMI: the process does not belong to the SSH session and outlives it."""
    quoted = command.replace("'", "''")
    done = ssh("$r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments "
               f"@{{ CommandLine = '{quoted}'; CurrentDirectory = '{root()}' }}; $r.ReturnValue")
    if done.stdout.strip().splitlines()[-1:] != ["0"]:
        raise RuntimeError(f"could not start the job: {done.stdout.strip()[:300]}")


def wait_job(log_dir: str, sleep=time.sleep, clock=time.monotonic) -> str:
    """The job's job.done text; job.log lines are echoed as they land."""
    printed, last_seen = 0, clock()
    while True:
        try:
            done = ssh(f"$l = '{log_dir}\\job.log'; if (Test-Path $l) {{ Get-Content $l -Encoding UTF8 }}; "
                       f"$d = '{log_dir}\\job.done'; if (Test-Path $d) {{ 'JOBDONE ' + (Get-Content $d -Raw) }}",
                       timeout=120)
        except (RuntimeError, subprocess.TimeoutExpired) as exc:
            if clock() - last_seen > UNREACHABLE_LIMIT_SECONDS:
                raise RuntimeError(f"host unreachable for {UNREACHABLE_LIMIT_SECONDS} s: {exc}") from exc
            sleep(POLL_SECONDS)
            continue
        last_seen = clock()
        lines = done.stdout.splitlines()
        marker = [ln for ln in lines if ln.startswith("JOBDONE ")]
        body = [ln for ln in lines if not ln.startswith("JOBDONE ")]
        for line in body[printed:]:
            print("  host:", line[:300], flush=True)
        printed = len(body)
        if marker:
            return marker[-1][len("JOBDONE "):].strip()
        sleep(POLL_SECONDS)


def run(plan: rwm.Plan, campaign_dir: pathlib.Path, args) -> int:
    if args.dry_run:
        print(json.dumps(plan.job, indent=1))
        if any(row.runtime == "litert-lm" for row in plan.rows) and args.litert_label not in rwm.load_litert_pins():
            print(f"warning: --litert-label {args.litert_label!r} is in neither windows/engine-pins.json nor "
                  "BENCH_EXTRA_PINS; a real run refuses it", file=sys.stderr)
        return 0
    invocation = env("BENCH_WINDOWS_INVOCATION") or (
        datetime.datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6])
    logs_local = campaign_dir / "host-logs" / invocation
    marker = logs_local / ".records-written"
    if marker.exists():
        print(f"{invocation}: its records are written already ({marker})", file=sys.stderr)
        return 2
    check_litert_build(plan, args.litert_label)
    job_remote = f"{root()}\\jobs\\{invocation}"
    logs_remote = f"{root()}\\logs\\{invocation}"
    print(f"== host {host()}, invocation {invocation}")
    ssh(f"New-Item -ItemType Directory -Force '{root()}\\engines','{root()}\\jobs','{root()}\\logs' | Out-Null")
    stage_llama(plan, args)
    scp_up(RUN_JOB, f"{root()}\\run_job.ps1")
    with tempfile.TemporaryDirectory(prefix="winjob-") as tmp:
        job_dir = pathlib.Path(tmp) / invocation
        job_dir.mkdir()
        write_job(plan, job_dir)
        scp_up(job_dir, f"{root()}\\jobs")
    # A new invocation starts from no engine cache (firstEver = the run that writes them); a resumed one keeps them
    start_detached(run_job_command(job_remote, logs_remote, purge=not env("BENCH_WINDOWS_INVOCATION")))
    status = wait_job(logs_remote)
    print(f"== job: {status}")
    logs_local.parent.mkdir(parents=True, exist_ok=True)
    if logs_local.exists():
        for old in logs_local.iterdir():
            old.unlink()
        logs_local.rmdir()
    scp_down(logs_remote, logs_local.parent)
    clean, total = rwm.write_records(plan, campaign_dir, invocation, litert_label=args.litert_label,
                                     extra_catalog=args.extra_catalog, harness=HARNESS)
    marker.write_text(datetime.datetime.now().isoformat() + "\n", encoding="utf-8")
    print(f"== {clean}/{total} runs clean, records in {campaign_dir}")
    return 0 if status == "OK" and clean == total else 1


rwm.register_executor("ssh", run)

if __name__ == "__main__":
    argv = sys.argv[1:]
    if "--executor" not in argv:
        argv = ["--executor", "ssh"] + argv
    try:
        sys.exit(rwm.main(argv))
    except RuntimeError as exc:  # the host does not answer, or refused the job: the message says which
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
