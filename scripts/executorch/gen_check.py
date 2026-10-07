#!/usr/bin/env python3
"""One generation of an exported .pte on the Mac, to see that it produces readable text.

Not a measurement: one launch, no warmup, no pause, no repetition.

--runner llama_main   llama_main --model_path <pte> --tokenizer_path <tok>
                          --prompt_file <prompt> --temperature 0 --max_new_tokens <n>
                          [--method_name <m>]
                      <prompt> is the host-templated prompt (make_prompts.py); stdout is the
                      echoed prompt + generated text + "\\nPyTorchObserver {json}".
--runner gemma4_e2e   gemma4_e2e_runner --model_path <pte> --tokenizer_path <tok>
                          --prompt <raw text> --temperature 0 --max_new_tokens <n>
                      <raw text> is the untemplated prompt: the runner builds
                      <bos><|turn>user\\n{prompt}<turn|>\\n<|turn>model\\n itself
                      (gemma4_runner.cpp build_input_ids); stdout is the generated text
                      + "\\n", stderr ends with "=== Gemma 4 Performance Report ===".

Writes <out-dir>/<stem>.log (command, host state, stdout and stderr in full),
<stem>.txt (generated text, when it can be cut out), <stem>.json (the runner's
stats as parsed + the text screen). Prints one summary line. The exit code is 0
when the launch ran and the text was cut out, whatever the text says.
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
import time

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "android/bench"))
from parsers import text_integrity  # noqa: E402

GEMMA4_REPORT = {
    "load": r"Model load:\s+([\d.]+) (ms|s)",
    "prefill": r"Prefill:\s+([\d.]+) (ms|s)(?: \((\d+) tokens, ([\d.]+) tok/s\))?",
    "generation": r"Generation:\s+([\d.]+) (ms|s)(?: \((\d+) tokens, ([\d.]+) tok/s\))?",
    "ttft": r"TTFT:\s+([\d.]+) (ms|s)",
    "total": r"Total:\s+([\d.]+) (ms|s)",
}


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ms(value, unit):
    return float(value) * (1000.0 if unit == "s" else 1.0)


def parse_gemma4_report(stderr):
    """Fields of Gemma4Stats::report() (gemma4_stats.h); missing lines stay missing."""
    out = {}
    for key, pat in GEMMA4_REPORT.items():
        m = re.search(pat, stderr)
        if not m:
            continue
        out[f"{key}_ms"] = ms(m.group(1), m.group(2))
        if key in ("prefill", "generation") and m.group(3):
            out[f"{key}_tokens"] = int(m.group(3))
            out[f"{key}_tok_per_s_printed"] = float(m.group(4))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runner", required=True, choices=["llama_main", "gemma4_e2e"])
    ap.add_argument("--binary", type=Path, required=True)
    ap.add_argument("--pte", type=Path, required=True)
    ap.add_argument("--tokenizer", type=Path, required=True)
    ap.add_argument("--prompt-file", type=Path, required=True,
                    help="llama_main: the templated prompt; gemma4_e2e: the raw prompt text")
    ap.add_argument("--max-new-tokens", type=int, default=64)
    ap.add_argument("--method-name", help="llama_main --method_name")
    ap.add_argument("--extra-args", default="")
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--stem", required=True)
    ap.add_argument("--timeout", type=int, default=900)
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    prompt = args.prompt_file.read_text(encoding="utf-8")
    cmd = ["/usr/bin/time", "-l", str(args.binary), "--model_path", str(args.pte),
           "--tokenizer_path", str(args.tokenizer)]
    if args.runner == "llama_main":
        cmd += ["--prompt_file", str(args.prompt_file)]
        if args.method_name:
            cmd += ["--method_name", args.method_name]
    else:
        cmd += ["--prompt", prompt]
    cmd += ["--temperature", "0", "--max_new_tokens", str(args.max_new_tokens)] + shlex.split(args.extra_args)

    started = dt.datetime.now(dt.timezone.utc).isoformat()
    before = {"loadAverage": list(os.getloadavg()), "QUIET_OK": os.environ.get("QUIET_OK")}
    t0 = time.monotonic()
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=args.timeout)
        rc, out, err, timed_out = proc.returncode, proc.stdout, proc.stderr, False
    except subprocess.TimeoutExpired as e:
        rc, out, err, timed_out = None, e.stdout or b"", e.stderr or b"", True
    wall = time.monotonic() - t0
    stdout, stderr = out.decode("utf-8", "replace"), err.decode("utf-8", "replace")

    rec = {"stem": args.stem, "runner": args.runner, "startedAt": started, "exitCode": rc, "timedOut": timed_out,
           "wallSeconds": round(wall, 3), "command": shlex.join(cmd), "binary": str(args.binary),
           "binarySha256": sha256(args.binary), "pte": str(args.pte.resolve()), "pteSha256": sha256(args.pte),
           "tokenizer": str(args.tokenizer.resolve()), "tokenizerSha256": sha256(args.tokenizer),
           "promptFile": str(args.prompt_file), "promptSha256": hashlib.sha256(prompt.encode()).hexdigest(),
           "maxNewTokens": args.max_new_tokens, "hostBefore": before}
    rss = re.search(r"^\s*(\d+)\s+maximum resident set size", stderr, re.M)
    if rss:
        rec["maxRSSBytes"] = int(rss.group(1))

    text = None
    if args.runner == "llama_main":
        stats_lines = [line for line in stdout.splitlines() if line.startswith("PyTorchObserver ")]
        if stats_lines:
            rec["stats"] = json.loads(stats_lines[-1][len("PyTorchObserver "):])
        if stdout.startswith(prompt):
            body = stdout[len(prompt):]
            cut = body.rfind("\nPyTorchObserver ")
            text = body[:cut] if cut >= 0 else body
            rec["textExtraction"] = "stdout minus the echoed prompt, cut before '\\nPyTorchObserver '"
        else:
            rec["textExtraction"] = "FAILED: stdout does not start with the prompt echo"
    else:
        rec["stats"] = parse_gemma4_report(stderr)
        if "=== Gemma 4 Performance Report ===" in stderr:
            text = stdout[:-1] if stdout.endswith("\n") else stdout
            rec["textExtraction"] = "stdout minus the final newline (std::endl after the token stream)"
        else:
            rec["textExtraction"] = "FAILED: no Gemma 4 performance report on stderr (run did not finish)"

    if text is not None:
        (args.out_dir / f"{args.stem}.txt").write_text(text, encoding="utf-8")
        rec["textChars"] = len(text)
        rec["textHead60"] = text[:60]
        rec["textIntegrity"] = text_integrity(text)
        rec["replacementChars"] = text.count("�")
    rec["status"] = "ok" if (rc == 0 and text is not None) else f"FAIL: exit {rc}{' (timeout)' if timed_out else ''}"
    (args.out_dir / f"{args.stem}.json").write_text(json.dumps(rec, indent=2, ensure_ascii=False) + "\n")
    with (args.out_dir / f"{args.stem}.log").open("w", encoding="utf-8") as f:
        f.write(f"# generation check {args.stem}; not a measurement\n# started {started}\n"
                f"# command: {rec['command']}\n# host before: {json.dumps(before)}\n"
                f"# exit {rc} wall {wall:.3f}s\n===== stdout =====\n{stdout}\n===== stderr =====\n{stderr}")
    st = rec.get("stats") or {}
    print(f"{args.stem}: {rec['status']} wall={wall:.1f}s "
          f"prompt={st.get('prompt_tokens', st.get('prefill_tokens'))} "
          f"gen={st.get('generated_tokens', st.get('generation_tokens'))} "
          f"text={rec.get('textIntegrity', {}).get('status')} head60={rec.get('textHead60')!r}", flush=True)
    return 0 if rec["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
