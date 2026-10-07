#!/usr/bin/env python3
"""Smoke launches of ExecuTorch's llama_main on the Mac: one process per launch.

For each task and regime, --runs launches of
  /usr/bin/time -l llama_main --model_path <pte> --tokenizer_path <tokenizer.json>
      --prompt_file <prompts-dir>/<task>.<suffix>.txt --temperature 0
      --max_new_tokens <budgets.tsv> [--warmup]
with --pause seconds between launches. cold = no --warmup (the first generation
of a fresh process); warm = --warmup (llama_main runs the same prompt once,
TextLLMRunner::warmup resets the stats, and the second generation is measured).
--cpu_threads is left at its default (-1: the runtime's performant-core
heuristic) unless --extra-args sets it (diagnostic launches only).

Per launch, in --out-dir:
  <task>-<regime>-<n>.log   command, host state, stdout and stderr in full
  <task>-<regime>-<n>.json  the PyTorchObserver stats object, verbatim
  <task>-<regime>-<n>.txt   the generated text (stdout minus the echoed prompt
                            and the stats line)
and runs.jsonl: one line per launch with the derived metrics, the text screen
and the process facts (exit code, /usr/bin/time -l counters, threads seen).

Derived metrics (extension/llm/runner/stats.h; text_llm_runner.cpp):
  prefill tok/s = prompt_tokens / (prompt_eval_end_ms - inference_start_ms) * 1000
                  (the window starts before the tokenizer encodes the prompt)
  decode tok/s  = generated_tokens / (inference_end_ms - prompt_eval_end_ms) * 1000
                  (generated_tokens = the decode loop's tokens; the reply has one
                  more, the token prefill sampled)
  TTFT ms       = first_token_ms - inference_start_ms (= the prefill window)
A failed launch keeps its files and its line (failed-runs-stay); the script
never retries.
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

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "android/bench"))
from parsers import text_integrity  # noqa: E402

TIME_KEYS = {"maximum resident set size": "maxRSSBytes", "peak memory footprint": "peakFootprintBytes",
             "involuntary context switches": "involuntaryCtxSwitches",
             "voluntary context switches": "voluntaryCtxSwitches",
             "instructions retired": "instructionsRetired", "cycles elapsed": "cyclesElapsed",
             "page faults": "pageFaults", "page reclaims": "pageReclaims"}


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def thermal():
    try:
        out = subprocess.run(["pmset", "-g", "therm"], capture_output=True, text=True, timeout=10).stdout
        return " | ".join(line.strip() for line in out.splitlines() if line.strip())
    except Exception as e:
        return f"unavailable: {e}"


def busy_others():
    """Processes at >= 20 % CPU right now (disclose-hw-state), as vl_response_mac.py lists them."""
    try:
        rows = subprocess.run(["ps", "-Ao", "pcpu,pid,comm", "-r"], capture_output=True, text=True,
                              timeout=10).stdout.splitlines()[1:12]
    except Exception as e:
        return [f"unavailable: {e}"]
    out = []
    for row in rows:
        parts = row.split(None, 2)
        try:
            pc, pid = float(parts[0]), int(parts[1])
        except (ValueError, IndexError):
            continue
        if pc >= 20.0 and pid != os.getpid():
            out.append(f"{os.path.basename(parts[2])}:{pc:.0f}%")
    return out


def parse_time(stderr):
    facts = {}
    m = re.search(r"([\d.]+) real\s+([\d.]+) user\s+([\d.]+) sys", stderr)
    if m:
        facts.update(realSeconds=float(m.group(1)), userSeconds=float(m.group(2)), sysSeconds=float(m.group(3)))
    for line in stderr.splitlines():
        m = re.match(r"\s*(\d+)\s+(.+?)\s*$", line)
        if m and m.group(2) in TIME_KEYS:
            facts[TIME_KEYS[m.group(2)]] = int(m.group(1))
    return facts


def thread_sampler(time_pid, stop, seen):
    """Highest OS thread count of the llama_main child of /usr/bin/time, 1 s apart."""
    while not stop.wait(1.0):
        try:
            kids = subprocess.run(["pgrep", "-P", str(time_pid)], capture_output=True, text=True).stdout.split()
            for pid in kids:
                rows = subprocess.run(["ps", "-M", "-p", pid], capture_output=True, text=True).stdout.splitlines()
                n = max(0, len(rows) - 1)
                seen.append(n)
        except Exception:
            pass
        if len(seen) >= 30:
            return


def derive(stats):
    m = {}
    pre = stats["prompt_eval_end_ms"] - stats["inference_start_ms"]
    dec = stats["inference_end_ms"] - stats["prompt_eval_end_ms"]
    if pre > 0:
        # the prefill rate, under the key build_summary.py reads (prefill_tps)
        m["promptTokensPerSecond"] = stats["prompt_tokens"] / pre * 1000
    if dec > 0:
        m["decodeTokensPerSecond"] = stats["generated_tokens"] / dec * 1000
    m["firstTokenLatencyMS"] = stats["first_token_ms"] - stats["inference_start_ms"]
    m["promptTokenCount"] = stats["prompt_tokens"]
    m["generatedTokenCount"] = stats["generated_tokens"]
    m["prefillWindowMS"] = pre
    m["decodeWindowMS"] = dec
    m["modelLoadMS"] = stats["model_load_end_ms"] - stats["model_load_start_ms"]
    return m


def launch(args, task, regime, n, budget):
    stem = f"{task}-{regime}-{n}"
    prompt_file = args.prompts_dir / f"{task}.{args.suffix}.txt"
    prompt = prompt_file.read_text(encoding="utf-8")
    cmd = ["/usr/bin/time", "-l", str(args.llama_main), "--model_path", str(args.pte),
           "--tokenizer_path", str(args.tokenizer), "--prompt_file", str(prompt_file),
           "--temperature", "0", "--max_new_tokens", str(budget)] + (["--warmup"] if regime == "warm" else []) \
        + shlex.split(args.extra_args)
    before = {"loadAverage": list(os.getloadavg()), "thermal": thermal(), "busyOthers": busy_others(),
              "quietLock": Path(args.quiet_lock).read_text(errors="replace").strip() if Path(args.quiet_lock).exists() else None,
              "QUIET_OK": os.environ.get("QUIET_OK")}
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    t0 = time.monotonic()
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stop, threads = threading.Event(), []
    sampler = threading.Thread(target=thread_sampler, args=(proc.pid, stop, threads), daemon=True)
    sampler.start()
    try:
        out, err = proc.communicate(timeout=args.timeout)
        timed_out = False
    except subprocess.TimeoutExpired:
        proc.kill()
        out, err = proc.communicate()
        timed_out = True
    stop.set()
    sampler.join(timeout=5)
    wall = time.monotonic() - t0
    stdout, stderr = out.decode("utf-8", "replace"), err.decode("utf-8", "replace")
    after = {"loadAverage": list(os.getloadavg()), "thermal": thermal()}

    rec = {"task": task, "regime": regime, "n": n, "stem": stem, "startedAt": started,
           "exitCode": proc.returncode, "timedOut": timed_out, "wallSeconds": round(wall, 3),
           "maxNewTokens": budget, "command": shlex.join(cmd), "promptFile": str(prompt_file),
           "promptSha256": hashlib.sha256(prompt.encode()).hexdigest(),
           "hostBefore": before, "hostAfter": after, "time": parse_time(stderr),
           "threadsSeen": max(threads) if threads else None, "threadSamples": len(threads)}
    stats_lines = [line for line in stdout.splitlines() if line.startswith("PyTorchObserver ")]
    stats = json.loads(stats_lines[-1][len("PyTorchObserver "):]) if stats_lines else None
    if stats is not None:
        (args.out_dir / f"{stem}.json").write_text(json.dumps(stats, indent=2) + "\n")
        rec["stats"] = stats
        rec["metrics"] = derive(stats)
        rec["reportedRates"] = {k: stats.get(k) for k in ("prefill_token_per_sec", "decode_token_per_sec")}
    text = None
    if stdout.startswith(prompt):
        body = stdout[len(prompt):]
        cut = body.rfind("\nPyTorchObserver ")
        text = body[:cut] if cut >= 0 else body
        rec["textExtraction"] = "stdout minus the echoed prompt, cut before '\\nPyTorchObserver '"
    else:
        rec["textExtraction"] = "FAILED: stdout does not start with the prompt echo"
    if text is not None:
        (args.out_dir / f"{stem}.txt").write_text(text, encoding="utf-8")
        rec["textChars"] = len(text)
        rec["textHead60"] = text[:60]
        rec["textIntegrity"] = text_integrity(text)
        rec["thinkOpen"] = "<think>" in text
        rec["thinkClosed"] = "</think>" in text
        rec["replacementChars"] = text.count("�")
    problems = []
    if proc.returncode != 0 or timed_out:
        problems.append(f"exit {proc.returncode}{' (timeout)' if timed_out else ''}")
    if stats is None:
        problems.append("no PyTorchObserver line")
    elif stats["generated_tokens"] + 1 > budget:
        problems.append("reply longer than max_new_tokens")
    if text is None:
        problems.append("text not extracted")
    rec["status"] = "FAIL: " + "; ".join(problems) if problems else "ok"
    with (args.out_dir / f"{stem}.log").open("w", encoding="utf-8") as f:
        f.write(f"# smoke launch {stem}; not a measurement (smoke only)\n# started {started}\n"
                f"# command: {rec['command']}\n# host before: {json.dumps(before)}\n"
                f"# host after: {json.dumps(after)}\n# exit {proc.returncode} wall {wall:.3f}s "
                f"threads seen (max of {len(threads)} ps samples) {rec['threadsSeen']}\n"
                f"===== stdout =====\n{stdout}\n===== stderr =====\n{stderr}")
    with (args.out_dir / "runs.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    m = rec.get("metrics", {})
    print(f"{stem}: {rec['status']} exit={proc.returncode} prompt={m.get('promptTokenCount')} "
          f"gen={m.get('generatedTokenCount')} prefill={m.get('promptTokensPerSecond', float('nan')):.1f} "
          f"decode={m.get('decodeTokensPerSecond', float('nan')):.1f} ttft={m.get('firstTokenLatencyMS')}ms "
          f"rss={rec['time'].get('maxRSSBytes')} threads={rec['threadsSeen']} "
          f"text={rec.get('textIntegrity', {}).get('status')}", flush=True)
    return rec


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--llama-main", type=Path, required=True)
    ap.add_argument("--pte", type=Path, required=True)
    ap.add_argument("--tokenizer", type=Path, required=True)
    ap.add_argument("--prompts-dir", type=Path, required=True)
    ap.add_argument("--suffix", required=True, help="prompt file tag, e.g. qwen3")
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--tasks", nargs="+", default=["short-chat", "long-context-1024-gen256"])
    ap.add_argument("--regimes", nargs="+", default=["cold", "warm"], choices=["cold", "warm"])
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--pause", type=float, default=30)
    ap.add_argument("--lead-pause", type=float, default=0, help="seconds before the first launch")
    ap.add_argument("--extra-args", default="", help="appended to every llama_main command, e.g. '--cpu_threads 12'")
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--quiet-lock", default=os.path.expanduser("~/code/coreai/_GPU_LOCK"))
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    budgets = dict(line.split() for line in (REPO / "prompts/text/budgets.tsv").read_text().splitlines()
                   if line.strip() and not line.startswith("#"))
    manifest = {"llamaMain": str(args.llama_main), "llamaMainSha256": sha256(args.llama_main),
                "pte": str(Path(args.pte).resolve()), "pteSha256": sha256(args.pte),
                "tokenizer": str(Path(args.tokenizer).resolve()), "tokenizerSha256": sha256(args.tokenizer),
                "startedAt": dt.datetime.now(dt.timezone.utc).isoformat(), "argv": sys.argv,
                "order": "task-major: per task, cold 1..runs then warm 1..runs; --pause s between launches"}
    with (args.out_dir / "manifest.jsonl").open("a") as f:
        f.write(json.dumps(manifest) + "\n")
    if args.lead_pause > 0:
        time.sleep(args.lead_pause)
    first = True
    for task in args.tasks:
        for regime in args.regimes:
            for n in range(1, args.runs + 1):
                if not first:
                    time.sleep(args.pause)
                first = False
                launch(args, task, regime, n, int(budgets[task]))


if __name__ == "__main__":
    main()
