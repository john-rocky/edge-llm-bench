#!/usr/bin/env python3
"""Runs the windows rows of cells files on a Windows PC reached over SSH.

The transport of scripts/run_windows_matrix.py (`register_executor`, the runner's contract
fn(plan, campaign_dir, args) -> int): it stages the pinned llama.cpp zips (a CUDA label's CUDA runtime zip with
its own) and windows/run_job.ps1 on the host, starts the job detached so that it outlives the SSH connection, waits for it
through one SSH session held open until the job ends (wait_job), pulls the logs into <campaign>/host-logs/<invocation>/
and writes the records with run_windows_matrix.write_records.

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
  BENCH_WINDOWS_GPU_SAMPLE_SECONDS  N: the job reads the NVIDIA GPU every N s while a GPU row's engine runs
                              (run_job.ps1 -GpuSampleSeconds; default 0 = no read while it runs)
  BENCH_WINDOWS_ENGINE_QOS    on | off | alt: High QoS on each run's engine process, none, or every other run of a
                              row (run_job.ps1 -EngineQos; default on); each record's conditions.engineQos says what
                              the job did

Before anything runs on the host, a job with LiteRT-LM rows stops (exit 1) when --litert-label is in neither
windows/engine-pins.json nor BENCH_EXTRA_PINS, or when the files in <root>\\engines\\<dir> are not that label's build:
its records would name no engine.
"""

import base64
import datetime
import functools
import json
import os
import pathlib
import select
import subprocess
import sys
import tempfile
import time
import uuid

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import run_windows_matrix as rwm  # noqa: E402

HARNESS = "scripts/windows_ssh_executor.py"
RUN_JOB = rwm.REPO / "windows" / "run_job.ps1"
# The wait is one SSH session: its PowerShell loop on the host (WAIT_SCRIPT) reads job.log and job.done every
# WAIT_READ_SECONDS, prints job.log's new lines, prints ALIVE after WAIT_ALIVE_SECONDS without a line, and ends at
# job.done, or by itself after WAIT_SESSION_MINUTES. The Mac closes a session that sends nothing for WAIT_IDLE_SECONDS;
# a session that ends before job.done is opened again after WAIT_RECONNECT_SECONDS and goes on from the next line.
WAIT_READ_SECONDS = 5
WAIT_ALIVE_SECONDS = 60
WAIT_IDLE_SECONDS = 180
WAIT_RECONNECT_SECONDS = 30
WAIT_SESSION_MINUTES = 240
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


def host_mismatch(remote_dir: str, want: dict) -> list:
    """The names in want ({file name: sha256}) whose file in remote_dir on the host is missing or another sha256."""
    names = ",".join(f"'{name}'" for name in sorted(want))
    listing = ssh(f"foreach ($n in {names}) {{ $p = Join-Path '{remote_dir}' $n; if (Test-Path $p) "
                  "{ 'FILE ' + $n + ' ' + (Get-FileHash -Algorithm SHA256 $p).Hash.ToLower() } }").stdout
    have = dict(line.split()[1:3] for line in listing.splitlines() if line.startswith("FILE ") and len(line.split()) == 3)
    return sorted(name for name, sha in want.items() if have.get(name) != sha)


def stage_llama(plan: rwm.Plan, args) -> None:
    """The pinned zips, verified on this machine, expanded on the host under engines\\<tool>\\ (a CUDA label's runtime
    zip into the same dir). A dir whose llama-cli.exe and dll_files all hold the label's sha256s is left as it is: the
    exe alone does not tell the assets apart (b11721's CPU, Vulkan and CUDA zips carry one llama-cli.exe)."""
    if not plan.labels:
        return
    pins = rwm.load_pins()
    zips = rwm.fetch_engines(args.engines_dir, pins, sorted(set(plan.labels.values())))
    for tool, label in sorted(plan.labels.items()):
        remote_dir = f"{root()}\\engines\\{tool}"
        want = rwm.llama_files(pins[label])
        if not host_mismatch(remote_dir, want):
            print(f"  {tool}: {label} already on the host")
            continue
        ssh(f"New-Item -ItemType Directory -Force '{remote_dir}' | Out-Null")
        for zip_path in zips[label]:
            scp_up(zip_path, f"{remote_dir}\\{zip_path.name}")
            # PowerShell 5.1's Expand-Archive draws a progress bar per write unless told not to
            ssh(f"$ProgressPreference = 'SilentlyContinue'; Expand-Archive -Force '{remote_dir}\\{zip_path.name}' "
                f"'{remote_dir}'; Remove-Item '{remote_dir}\\{zip_path.name}'", timeout=600)
        bad = host_mismatch(remote_dir, want)
        if bad:
            raise RuntimeError(f"{remote_dir}: {', '.join(bad)} differ from {label} after staging")
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


def gpu_sample_seconds() -> str:
    """BENCH_WINDOWS_GPU_SAMPLE_SECONDS as run_job.ps1 takes it: "" when unset (the job's default, no read while the
    engine runs), else a whole number of seconds, 0 for none."""
    value = env("BENCH_WINDOWS_GPU_SAMPLE_SECONDS").strip()
    if value and not value.isdigit():
        raise RuntimeError(f"BENCH_WINDOWS_GPU_SAMPLE_SECONDS={value!r}: a whole number of seconds, 0 for none")
    return str(int(value)) if value else ""


ENGINE_QOS = ("on", "off", "alt")


def engine_qos() -> str:
    """BENCH_WINDOWS_ENGINE_QOS as run_job.ps1 takes it: "" when unset (the job's default, on), else on, off or alt."""
    value = env("BENCH_WINDOWS_ENGINE_QOS").strip()
    if value and value not in ENGINE_QOS:
        raise RuntimeError(f"BENCH_WINDOWS_ENGINE_QOS={value!r}: one of {', '.join(ENGINE_QOS)}")
    return value


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
    if gpu_sample_seconds():
        words += ["-GpuSampleSeconds", gpu_sample_seconds()]
    if engine_qos():
        words += ["-EngineQos", engine_qos()]
    if purge:
        words.append("-PurgeEngineCaches")
    return " ".join(words)


def start_detached(command: str, clear: str = "") -> None:
    """Through WMI: the process does not belong to the SSH session and outlives it. clear names a file on the host
    removed first in the same session: a resumed job's job.done from its earlier start, which the wait's first read
    could otherwise take for this start's before the job itself removes it."""
    quoted = command.replace("'", "''")
    first = f"Remove-Item -LiteralPath '{clear}' -ErrorAction SilentlyContinue; " if clear else ""
    done = ssh(first + "$r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments "
               f"@{{ CommandLine = '{quoted}'; CurrentDirectory = '{root()}' }}; $r.ReturnValue")
    if done.stdout.strip().splitlines()[-1:] != ["0"]:
        raise RuntimeError(f"could not start the job: {done.stdout.strip()[:300]}")


def ssh_stream(command: str, idle_seconds: float = WAIT_IDLE_SECONDS, popen=subprocess.Popen):
    """One PowerShell command on the host through one SSH session held open while it runs: yields each line of its
    output (stdout and stderr, the CR dropped) as it comes. RuntimeError when the session ends with an exit other than
    0, or when nothing came for idle_seconds (the session is closed then); ssh's own ServerAlive checks end a session
    whose host stopped answering after about two minutes."""
    full = "[Console]::OutputEncoding = [Text.Encoding]::UTF8; " + command
    proc = popen(["ssh", "-o", "ConnectTimeout=20", "-o", "BatchMode=yes", "-o", "ServerAliveInterval=30",
                  "-o", "ServerAliveCountMax=4", host(), full],
                 stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    fd, pending, tail = proc.stdout.fileno(), b"", []
    try:
        while True:
            if not select.select([fd], [], [], idle_seconds)[0]:
                proc.kill()
                raise RuntimeError(f"ssh {host()}: nothing came for {idle_seconds} s")
            chunk = os.read(fd, 65536)
            if not chunk:
                break
            *whole, pending = (pending + chunk).split(b"\n")
            for raw in whole:
                line = raw.decode("utf-8", errors="replace").rstrip("\r")
                tail = (tail + [line])[-3:]
                yield line
        if pending:
            line = pending.decode("utf-8", errors="replace").rstrip("\r")
            tail = (tail + [line])[-3:]
            yield line
        code = proc.wait(timeout=60)
        if code != 0:
            raise RuntimeError(f"ssh {host()}: exit {code}: {' | '.join(tail)[:500]}")
    finally:
        if proc.poll() is None:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        proc.stdout.close()


def encoded(script: str) -> str:
    """A PowerShell script as one command line for the host's default shell: -EncodedCommand carries it through ssh
    with no quoting to break, and takes no arguments, so the values are written into the script."""
    return ("powershell.exe -NoProfile -NonInteractive -EncodedCommand "
            + base64.b64encode(script.encode("utf-16-le")).decode("ascii"))


# The host side of wait_job, Windows PowerShell 5.1, no WMI: reads job.done, then job.log's new bytes, every @EVERY@ s;
# prints each job.log line past the first @SKIP@ as "LOG <line>", "ALIVE" after @ALIVE@ s with nothing printed, and
# ends at job.done with "WAITSTAT <reads> <seconds> <its CPU seconds> <failed reads>" and "JOBDONE <job.done's text>",
# or with "SESSIONEND" after @MINUTES@ min (a session the Mac no longer reads does not outlive that).
WAIT_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$log = '@LOG@'; $done = '@DONE@'; $skip = @SKIP@
$dec = (New-Object Text.UTF8Encoding($false)).GetDecoder()
$out = [Console]::Out; $pos = [long]0; $n = 0; $part = ''; $reads = 0; $fails = 0
$t0 = [DateTime]::UtcNow; $said = $t0
$out.WriteLine('WAITING ' + (Get-Date -Format o) + ' from line ' + $skip); $out.Flush()
while ($true) {
    # job.done first: the job writes it after its last job.log line, so the read below then holds every line
    $fin = [IO.File]::Exists($done)
    if ([IO.File]::Exists($log)) {
        $fs = $null
        try {
            $fs = [IO.File]::Open($log, 'Open', 'Read', 'ReadWrite')
            if ($fs.Length -gt $pos) {
                [void]$fs.Seek($pos, 'Begin')
                $buf = New-Object byte[] ([int]($fs.Length - $pos))
                $got = $fs.Read($buf, 0, $buf.Length)
                $pos += $got
                $chars = New-Object char[] ($dec.GetCharCount($buf, 0, $got))
                [void]$dec.GetChars($buf, 0, $got, $chars, 0)
                $part += -join $chars
            }
        } catch {
            $fails++
        } finally {
            if ($fs) { $fs.Close() }
        }
        while (($i = $part.IndexOf([char]10)) -ge 0) {
            $n++
            if ($n -gt $skip) { $out.WriteLine('LOG ' + $part.Substring(0, $i).TrimEnd([char]13)); $said = [DateTime]::UtcNow }
            $part = $part.Substring($i + 1)
        }
    }
    $reads++
    if ($fin) {
        $t = ''
        try { $t = [IO.File]::ReadAllText($done).Trim() } catch { $fails++ }
        if ($t) {
            $cpu = [Diagnostics.Process]::GetCurrentProcess().TotalProcessorTime.TotalSeconds
            $out.WriteLine('WAITSTAT ' + $reads + ' ' + [int](([DateTime]::UtcNow - $t0).TotalSeconds) + ' ' + [Math]::Round($cpu, 2) + ' ' + $fails)
            $out.WriteLine('JOBDONE ' + $t)
            $out.Flush()
            exit 0
        }
    }
    if (([DateTime]::UtcNow - $t0).TotalMinutes -ge @MINUTES@) { $out.WriteLine('SESSIONEND'); $out.Flush(); exit 0 }
    if (([DateTime]::UtcNow - $said).TotalSeconds -ge @ALIVE@) { $out.WriteLine('ALIVE'); $said = [DateTime]::UtcNow }
    $out.Flush()
    Start-Sleep -Seconds @EVERY@
}
"""


def wait_script(log_dir: str, skip: int) -> str:
    quoted = log_dir.replace("'", "''")
    return (WAIT_SCRIPT.replace("@LOG@", f"{quoted}\\job.log").replace("@DONE@", f"{quoted}\\job.done")
            .replace("@SKIP@", str(int(skip))).replace("@EVERY@", str(WAIT_READ_SECONDS))
            .replace("@ALIVE@", str(WAIT_ALIVE_SECONDS)).replace("@MINUTES@", str(WAIT_SESSION_MINUTES)))


WAIT_LINES = ("WAITING", "LOG", "ALIVE", "WAITSTAT", "SESSIONEND", "JOBDONE")


def wait_job(log_dir: str, stream=None, sleep=time.sleep, clock=time.monotonic) -> str:
    """The job's job.done text, through one SSH session held open on the host until the job ends (WAIT_SCRIPT):
    job.log lines are echoed as they land. A session that ends first is opened again after WAIT_RECONNECT_SECONDS and
    goes on from the next line; no line of WAIT_SCRIPT's for UNREACHABLE_LIMIT_SECONDS stops the wait (RuntimeError,
    the job goes on on the host)."""
    stream = stream or ssh_stream
    printed, last_seen, sessions = 0, clock(), 0
    while True:
        sessions += 1
        why, stat = "the session ended before job.done", ""
        lines = stream(encoded(wait_script(log_dir, printed)))
        try:
            for line in lines:
                kind, _, text = line.partition(" ")
                if kind not in WAIT_LINES:
                    continue  # the host's error text: the session's end says it, and it is no sign of the loop
                last_seen = clock()
                if kind == "LOG":
                    print("  host:", text[:300], flush=True)
                    printed += 1
                elif kind == "WAITSTAT":
                    stat = text
                elif kind == "JOBDONE":
                    reads, seconds, cpu, *_ = (stat.split() + ["?"] * 3)[:3]
                    print(f"== the wait: {sessions} SSH session(s); the last one's loop read job.log and job.done "
                          f"{reads} times over {seconds} s with {cpu} s of CPU on the host", flush=True)
                    return text.strip()
                elif kind == "SESSIONEND":
                    why = f"the session's loop ended after {WAIT_SESSION_MINUTES} min"
        except (RuntimeError, subprocess.TimeoutExpired, OSError) as exc:
            why = str(exc)
        finally:
            close = getattr(lines, "close", None)
            if close:
                close()
        if clock() - last_seen > UNREACHABLE_LIMIT_SECONDS:
            raise RuntimeError(f"host unreachable for {UNREACHABLE_LIMIT_SECONDS} s: {why}")
        print(f"  (the wait's SSH session {sessions} ended: {why[:300]}; the next one in {WAIT_RECONNECT_SECONDS} s, "
              f"from line {printed + 1} of job.log)", flush=True)
        sleep(WAIT_RECONNECT_SECONDS)


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
    gpu_sample_seconds()  # a bad value stops here, before anything reaches the host
    engine_qos()
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
    start_detached(run_job_command(job_remote, logs_remote, purge=not env("BENCH_WINDOWS_INVOCATION")),
                   clear=f"{logs_remote}\\job.done")
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
    planned = sum(row.runs for row in plan.rows)
    print(f"== {clean}/{total} runs clean, records in {campaign_dir}")
    if total < planned:
        # A job that Windows stops (the Windows Update restart of 2026-11-06 17:31 JST) ends through its `finally`,
        # which writes OK into job.done: the records alone would read as a clean sitting.
        print(f"== {planned - total} of {planned} planned runs did not run on the host (job.done {status!r}): "
              "the sitting is incomplete; retake it under a new --campaign")
    return 0 if status == "OK" and clean == total == planned else 1


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
