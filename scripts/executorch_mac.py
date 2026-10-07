#!/usr/bin/env python3
"""Mac ExecuTorch cells: the ExecuTorch tag's own runner of the model's family, one fresh
process per run, schema-v1 JSONL (docs/executorch-arm-v1.md).

  python3 scripts/executorch_mac.py --model-id own-export/Qwen3-0.6B-ET1.5.1-xnnpack-8da4w-emb8-ctx2048 \\
      --file Qwen3-0.6B-ET1.5.1-xnnpack-8da4w-emb8-ctx2048.pte --recipe et1.5.1-xnnpack-8da4w-g128-emb8 \\
      --backend xnnpack --task short-chat --runs 4 --output results/raw/<campaign>/<cell>.jsonl

Run 1 is cold: a fresh runner process, no --warmup. Runs 2..N are warm: llama_main --warmup
generates the same prompt once, unmeasured, in the same process and the second generation is
measured. gemma4_e2e_runner has no warmup option, so a Gemma 4 cell takes --runs 1 here (its
Mac rows are excluded in the cells file: the Mac headline is warm). The runner is the model
family's (parsers.executorch_runner_for, checked against the recipe.json): llama_main for
Qwen 3, gemma4_e2e_runner for Gemma 4, from --runner-dir (default
.build/executorch-<tag>[-<backend>]/, copied from the ExecuTorch tree's cmake-out). Inputs
(.pte, recipe.json, tokenizer, the prompt the runner reads) are staged under ET_MODEL_DIR and
checked by parsers.executorch_inputs. Memory = os.wait4's ru_maxrss of the runner process
(bytes on macOS) / 2^20 = MiB, model load included.

Exit: 0 = every run ok, 1 = a run failed (its record stays), 75 = the cell's inputs are not
staged (nothing ran), 2 = usage.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import threading
import time
import uuid

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "android" / "bench"))
import parsers  # noqa: E402

STAMP = "executorch-mac-v1-2026-10-08"
TAG = os.environ.get("BENCH_EXECUTORCH_TAG", "v1.5.1")
BACKENDS = ("xnnpack", "mlx", "metal", "coreml")
TASKS = ("short-chat", "long-context-1024-gen256")
RSS_BASIS = ("os.wait4 of the runner process: ru_maxrss (bytes on macOS) / 2^20 = MiB; the "
             "process lifetime resident high-water, model load included")
EXIT_NOT_STAGED = 75


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sh(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def host_snapshot():
    """load, CPU speed limit (pmset), processes above 20 % CPU — read as
    scripts/vl_response_mac.py reads them (disclose-hw-state); never assumed idle."""
    therm = sh(["pmset", "-g", "therm"])
    m = re.search(r"CPU_Speed_Limit\s*=\s*(\d+)", therm)
    limit = int(m.group(1)) if m else None
    others = []
    for line in sh(["ps", "-Ao", "pcpu,pid,comm", "-r"]).splitlines()[1:12]:
        parts = line.split(None, 2)
        try:
            pc, pid = float(parts[0]), int(parts[1])
        except (ValueError, IndexError):
            continue
        if pc >= 20.0 and pid != os.getpid():
            others.append(f"{os.path.basename(parts[2])}:{pc:.0f}%")
    return {"loadAverage": list(os.getloadavg()), "cpuSpeedLimit": limit, "others": others,
            "thermal": "nominal" if (limit is None or limit >= 100) else f"throttled(cpu_speed_limit={limit})"}


def device_info():
    mem = sh(["sysctl", "-n", "hw.memsize"])
    return {"systemName": "macOS", "modelIdentifier": sh(["sysctl", "-n", "hw.model"]),
            "chip": sh(["sysctl", "-n", "machdep.cpu.brand_string"]),
            "systemVersion": f"Version {sh(['sw_vers', '-productVersion'])} (Build {sh(['sw_vers', '-buildVersion'])})",
            "processorCount": int(sh(["sysctl", "-n", "hw.ncpu"]) or 0),
            "physicalMemoryMB": int(mem) // (1024 * 1024) if mem.isdigit() else None,
            "batteryState": "unknown", "buildConfiguration": "Release"}


def witness(runner, binary_sha, backend="xnnpack"):
    """engineVersion = the tag whose environment.lock.json entry holds this binary's sha256:
    arms.executorch.mac.binaries for the XNNPACK builds, arms.executorch.mac.backends.<backend>
    .binaries for another delegate's build — the observed build, never the newest pin."""
    where = "arms.executorch.mac" + ("" if backend == "xnnpack" else f".backends.{backend}")
    try:
        lock = json.loads((REPO / "environment.lock.json").read_text())
        arm = lock["arms"]["executorch"]
        mac = arm["mac"] if backend == "xnnpack" else arm["mac"]["backends"][backend]
        entry = mac["binaries"][runner]
        if entry.get("sha256") == binary_sha:
            return arm["tag"]
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return f"unknown (mac {runner} sha unmatched in environment.lock.json {where})"


def runner_command(binary, inputs, budget, warm):
    """The runner's argv: llama_main reads the rendered prompt file; gemma4_e2e_runner takes
    the unrendered prompt as --prompt and applies its own turn template."""
    cmd = [str(binary), "--model_path", inputs["pte"], "--tokenizer_path", inputs["tokenizer"]]
    if inputs["runner"] == "llama_main":
        cmd += ["--prompt_file", inputs["prompt"]]
    else:
        cmd += ["--prompt", inputs["promptText"]]
    cmd += ["--temperature", "0", "--max_new_tokens", str(budget)]
    return cmd + (["--warmup"] if warm else [])


def launch(cmd, stdout_path, stderr_path, timeout):
    """One runner process, stdout and stderr to files -> (exit code, ru_maxrss bytes, wall s,
    timed out). os.wait4 reaps exactly this child, so its rusage is this run's alone."""
    with open(stdout_path, "wb") as out, open(stderr_path, "wb") as err:
        t0 = time.monotonic()
        proc = subprocess.Popen(cmd, stdout=out, stderr=err, stdin=subprocess.DEVNULL)
    fired = threading.Event()

    def kill():
        fired.set()
        proc.kill()
    timer = threading.Timer(timeout, kill)
    timer.start()
    _, status, usage = os.wait4(proc.pid, 0)
    timer.cancel()
    wall = time.monotonic() - t0
    proc.returncode = os.waitstatus_to_exitcode(status)  # reaped here, not by Popen
    return proc.returncode, usage.ru_maxrss, wall, fired.is_set()


def build_record(args, inputs, index, cold, stdout, stderr, exit_code, maxrss_bytes, wall,
                 before, after, device, cmd, binary_sha, logs):
    """One run's schema-v1 record from the runner's output (also the conversion of a stored
    launch: the selftest feeds it a stored stdout)."""
    budget = task_budget(args.task)
    if inputs["runner"] == "llama_main":
        parsed = parsers.parse_executorch(stdout, stderr, inputs["promptText"])
    else:
        parsed = parsers.parse_gemma4_runner(stdout, stderr)
    fields = parsers.executorch_record_fields(parsed, inputs, budget, args.context_tokens)
    text = fields["text"] or ""
    verdict = dict(parsers.text_integrity(text),
                   method="the runner's generated text (parsers: textExtraction) + lexical screen; full text retained")
    flags = fields["flags"] + verdict["flags"]
    if exit_code != 0:
        flags.append(f"engine-exit-{exit_code}")
    metrics = {**fields["metrics"], "coldRun": cold, "harnessStamp": STAMP,
               "initialThermalState": before["thermal"], "finalThermalState": after["thermal"]}
    if isinstance(maxrss_bytes, int) and maxrss_bytes > 0:
        metrics["memoryPeakResidentMB"] = maxrss_bytes / 2 ** 20
    conditions = {**fields["conditions"], "warm": not cold, "regime": "cold" if cold else "warm",
                  "thermalInitial": before["thermal"], "thermalFinal": after["thermal"],
                  "loadAverage": before["loadAverage"][0], "loadAverages": before["loadAverage"],
                  "busyOthers": before["others"], "cpuSpeedLimit": before["cpuSpeedLimit"],
                  "exitCode": exit_code, "launchWallSeconds": round(wall, 3), "runIndex": index,
                  "textCheck": verdict,
                  "textOutputSHA256": hashlib.sha256(text.encode()).hexdigest()}
    if flags:
        conditions["protocolFlags"] = flags
    rel = (lambda p: os.path.relpath(p, REPO) if str(p).startswith(str(REPO)) else str(p))
    rec = {"schemaVersion": 1, "id": str(uuid.uuid4()),
           "timestamp": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "runtime": f"executorch-{args.backend}",
           "engineVersion": witness(inputs["runner"], binary_sha, args.backend),
           "engineArtifact": f"{inputs['runner']} sha256:{binary_sha}",
           "model": {"id": args.model_id, **fields["model"]},
           "task": args.task, "device": device, "conditions": conditions, "metrics": metrics,
           "harnessStamp": STAMP, "decodedText": text, "outputSample": text[:200],
           "provenance": {**fields["provenance"], "harness": "scripts/executorch_mac.py",
                          "rawLog": rel(logs["log"]), "stdoutLog": rel(logs["stdout"]),
                          "stderrLog": rel(logs["stderr"]), "campaign": rel(args.campaign_dir),
                          "command": shlex.join(cmd if inputs["runner"] == "llama_main"
                                                else [c if c != inputs["promptText"] else f"<{inputs['prompt']}>"
                                                      for c in cmd]),
                          "rssBasis": RSS_BASIS, "hostBefore": before, "hostAfter": after},
           "status": "ok" if exit_code == 0 and not flags and "decodeTokensPerSecond" in metrics else "failed"}
    return rec


def validate(rec):
    """schema/result.v1.json when jsonschema is importable (the ExecuTorch export venv has
    it; the system python may not) -> None, or the reason it was not checked."""
    try:
        from jsonschema import Draft7Validator, FormatChecker
    except ImportError:
        return "jsonschema not importable: record written without schema validation"
    schema = json.loads((REPO / "schema" / "result.v1.json").read_text())
    Draft7Validator(schema, format_checker=FormatChecker()).validate(rec)
    return None


def task_budget(task):
    budgets = dict(line.split() for line in (REPO / "prompts" / "text" / "budgets.tsv").read_text().splitlines()
                   if line.strip() and not line.startswith("#"))
    return int(budgets[task])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model-id", required=True)
    ap.add_argument("--file", required=True, help="the .pte, relative to ET_MODEL_DIR")
    ap.add_argument("--recipe", required=True, help="the cells' recipe= alias (parsers.EXECUTORCH_RECIPES)")
    ap.add_argument("--backend", required=True, choices=BACKENDS)
    ap.add_argument("--task", required=True, choices=TASKS)
    ap.add_argument("--context-tokens", type=int, help="the cells' context-tokens= (checked against the export)")
    ap.add_argument("--runs", type=int, default=4)
    ap.add_argument("--pause", type=float, default=30, help="seconds between runs")
    ap.add_argument("--timeout", type=int, default=1800)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--campaign-dir", type=Path)
    ap.add_argument("--model-dir", type=Path,
                    default=Path(os.environ.get("ET_MODEL_DIR", REPO / "models" / "executorch")))
    ap.add_argument("--runner-dir", type=Path, default=None,
                    help="directory holding llama_main / gemma4_e2e_runner "
                         "(default: ET_MAC_RUNNER_DIR, else .build/executorch-<tag>[-<backend>])")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if args.runs < 1 or args.pause < 0 or args.timeout < 1:
        ap.error("runs and timeout must be positive, pause nonnegative")
    args.output = args.output.resolve()
    args.campaign_dir = (args.campaign_dir or args.output.parent).resolve()
    runner_dir = args.runner_dir or Path(os.environ.get("ET_MAC_RUNNER_DIR") or
                                         REPO / ".build" / f"executorch-{TAG}{'' if args.backend == 'xnnpack' else '-' + args.backend}")
    try:
        inputs = parsers.executorch_inputs(str(args.model_dir), args.file, args.task, args.recipe, str(REPO))
    except ValueError as e:
        print(f"NOT STAGED executorch {args.model_id} {args.task}: {e}", file=sys.stderr)
        return EXIT_NOT_STAGED
    if inputs["runner"] == "gemma4_e2e_runner" and args.runs > 1:
        ap.error("gemma4_e2e_runner has no warmup: no warm runs (--runs 1; the Mac Gemma 4 rows are excluded)")
    binary = runner_dir / inputs["runner"]
    budget = task_budget(args.task)
    if args.dry_run:
        for index in range(1, args.runs + 1):
            cmd = runner_command(binary, inputs, budget, warm=index > 1)
            shown = [c if c != inputs["promptText"] else f"<{inputs['prompt']}>" for c in cmd]
            print(json.dumps({"run": index, "regime": "cold" if index == 1 else "warm",
                              "pauseBefore": args.pause if index > 1 else 0, "command": shlex.join(shown),
                              "runner": inputs["runner"], "binary": str(binary),
                              "binarySha256": sha256(binary) if binary.is_file() else "missing",
                              "quantization": inputs["label"], "contextTokens": inputs["contextTokens"],
                              "promptSha256": inputs["promptSha256"], "output": str(args.output)},
                             ensure_ascii=False))
        return 0
    if not binary.is_file():
        print(f"NOT STAGED executorch runner {binary} (copy it from the ExecuTorch tree's cmake-out; "
              "docs/executorch-arm-v1.md)", file=sys.stderr)
        return EXIT_NOT_STAGED
    binary_sha = sha256(binary)
    device = device_info()
    logs_dir = args.campaign_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    ok = True
    for index in range(1, args.runs + 1):
        if index > 1:
            time.sleep(args.pause)
        cold = index == 1
        cmd = runner_command(binary, inputs, budget, warm=not cold)
        stem = f"{args.output.stem}_{uuid.uuid4().hex[:12]}_run{index}"
        logs = {"stdout": logs_dir / f"{stem}.stdout.txt", "stderr": logs_dir / f"{stem}.stderr.txt",
                "log": logs_dir / f"{stem}.log"}
        before = host_snapshot()
        exit_code, maxrss, wall, timed_out = launch(cmd, logs["stdout"], logs["stderr"], args.timeout)
        after = host_snapshot()
        stdout = logs["stdout"].read_text(encoding="utf-8", errors="replace")
        stderr = logs["stderr"].read_text(encoding="utf-8", errors="replace")
        rec = build_record(args, inputs, index, cold, stdout, stderr, exit_code, maxrss, wall,
                           before, after, device, cmd, binary_sha, logs)
        if timed_out:
            rec["conditions"].setdefault("protocolFlags", []).append("timeout")
            rec["status"] = "failed"
        with logs["log"].open("w", encoding="utf-8") as fh:
            fh.write(f"# executorch {args.model_id} {args.task} run {index} ({rec['conditions']['regime']})\n"
                     f"# command: {rec['provenance']['command']}\n# exit {exit_code} wall {wall:.3f}s "
                     f"ru_maxrss {maxrss}\n===== stdout =====\n{stdout}\n===== stderr =====\n{stderr}")
        unchecked = validate(rec)
        if unchecked:
            print(f"WARNING {unchecked}", file=sys.stderr)
        with args.output.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False, allow_nan=False) + "\n")
        m = rec["metrics"]
        print(f"{rec['status'].upper()} run {index}/{args.runs} {rec['conditions']['regime']}: exit={exit_code} "
              f"prompt={m.get('promptTokenCount')} gen={m.get('generatedTokenCount')} "
              f"decode={m.get('decodeTokensPerSecond')} rss_mib={m.get('memoryPeakResidentMB')} "
              f"text={rec['conditions']['textCheck']['status']}", flush=True)
        ok = ok and rec["status"] == "ok"
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
