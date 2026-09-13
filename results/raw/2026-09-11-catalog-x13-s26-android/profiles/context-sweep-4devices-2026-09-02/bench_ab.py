#!/usr/bin/env python3
"""Paired A/B benchmark driver for litert_lm_advanced_main +-YNNPACK.

Alternates A (no_ynnpack binary, flag off) and B (ynnpack binary,
--enable_ynnpack=true) so thermal / background drift hits both sides equally.
Parses "Prefill speed turn N" / "Decode speed turn N" lines from the runtime's
benchmark output, stores every raw log, and reports median + min-max spread.

Runner targets:
  local                     run binaries on this machine
  adb:<serial>              run via adb shell (binaries+model already pushed)
  ssh:<host>                run via ssh (binaries+model already copied)

For adb/ssh the binary/model paths given are the REMOTE paths.
"""

import argparse
import json
import re
import statistics
import subprocess
import sys
import time
from pathlib import Path

PREFILL_RE = re.compile(r"Prefill Speed: ([0-9.]+) tokens/sec")
DECODE_RE = re.compile(r"Decode Speed: ([0-9.]+) tokens/sec")
TTFT_RE = re.compile(r"Time to first token: ([0-9.]+) s")
YNN_ACTIVE_RE = re.compile(r"YNNPACK CPU accelerator registered")


def build_cmd(runner, binary, model, args, enable_ynnpack):
    flags = [
        f"--model_path={model}",
        "--backend=cpu",
        "--benchmark",
        f"--benchmark_prefill_tokens={args.prefill}",
        f"--benchmark_decode_tokens={args.decode}",
    ]
    if args.num_cpu_threads > 0:
        flags.append(f"--num_cpu_threads={args.num_cpu_threads}")
    if enable_ynnpack:
        flags.append("--enable_ynnpack=true")
    # 2026-09-02: pass-through flags (e.g. --max_num_tokens=4096) for the
    # context-length A/B; appended verbatim to BOTH sides.
    flags.extend(args.extra_flag)
    remote = " ".join([binary] + flags)
    if args.remote_prefix:
        remote = f"{args.remote_prefix} {remote}"
    if runner == "local":
        return [binary] + flags
    kind, _, target = runner.partition(":")
    if kind == "adb":
        return ["adb", "-s", target, "shell", remote + " < /dev/null 2>&1"]
    if kind == "ssh":
        return ["ssh", target, remote + " < /dev/null 2>&1"]
    raise ValueError(f"bad runner {runner}")


def run_once(runner, binary, model, args, enable_ynnpack, log_path):
    cmd = build_cmd(runner, binary, model, args, enable_ynnpack)
    t0 = time.time()
    proc = subprocess.run(
        cmd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=args.timeout,
    )
    wall = time.time() - t0
    text = proc.stdout.decode("utf-8", "replace")
    Path(log_path).write_text(text)
    prefills = PREFILL_RE.findall(text)
    decodes = DECODE_RE.findall(text)
    ttft = TTFT_RE.search(text)
    row = {
        "rc": proc.returncode,
        "wall_s": round(wall, 2),
        "prefill_tps": float(prefills[0]) if prefills else None,
        "decode_tps": float(decodes[0]) if decodes else None,
        "ttft_s": float(ttft.group(1)) if ttft else None,
        "ynnpack_active": bool(YNN_ACTIVE_RE.search(text)),
        # Registration alone does not prove delegation (accelerator declines
        # when the flag is off, ynnpack_accelerator.cc:94); the delegate's own
        # per-op messages do.
        "ynn_delegate_msgs": len(re.findall(r"delegates/ynnpack", text)),
    }
    return row


def summarize(rows, key):
    vals = [r[key] for r in rows if r.get(key) is not None]
    if not vals:
        return None
    return {
        "n": len(vals),
        "median": round(statistics.median(vals), 2),
        "min": round(min(vals), 2),
        "max": round(max(vals), 2),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runner", default="local")
    ap.add_argument("--bin-a", required=True, help="no_ynnpack binary path")
    ap.add_argument("--bin-b", required=True, help="ynnpack binary path")
    ap.add_argument("--model", required=True)
    ap.add_argument("--prefill", type=int, default=1024)
    ap.add_argument("--decode", type=int, default=256)
    ap.add_argument("--reps", type=int, default=8)
    ap.add_argument("--num-cpu-threads", type=int, default=0)
    ap.add_argument(
        "--remote-prefix",
        default="",
        help="string prepended to the remote command, e.g. "
        "'LD_LIBRARY_PATH=/data/local/tmp/ynn'",
    )
    ap.add_argument("--timeout", type=int, default=1800)
    ap.add_argument(
        "--extra-flag",
        action="append",
        default=[],
        help="extra litert_lm_advanced_main flag, repeatable "
        "(e.g. --extra-flag=--max_num_tokens=4096); applied to both sides",
    )
    ap.add_argument("--cooldown", type=int, default=5, help="seconds between runs")
    ap.add_argument("--tag", required=True, help="label, e.g. mac_m4max")
    ap.add_argument("--outdir", default=str(Path(__file__).parent / "results"))
    args = ap.parse_args()

    outdir = Path(args.outdir) / args.tag
    outdir.mkdir(parents=True, exist_ok=True)
    jsonl = outdir / "runs.jsonl"

    rows = {"A": [], "B": []}
    with open(jsonl, "a") as jf:
        for rep in range(args.reps):
            for side, binary, ynn in (
                ("A", args.bin_a, False),
                ("B", args.bin_b, True),
            ):
                log = outdir / f"rep{rep}_{side}.log"
                row = run_once(args.runner, binary, args.model, args, ynn, log)
                row.update(
                    side=side,
                    rep=rep,
                    binary=binary,
                    enable_ynnpack=ynn,
                    prefill_tokens=args.prefill,
                    decode_tokens=args.decode,
                    extra_flags=list(args.extra_flag),
                    tag=args.tag,
                    ts=time.strftime("%Y-%m-%dT%H:%M:%S"),
                )
                jf.write(json.dumps(row) + "\n")
                jf.flush()
                rows[side].append(row)
                print(
                    f"rep{rep} {side} rc={row['rc']} "
                    f"prefill={row['prefill_tps']} decode={row['decode_tps']} "
                    f"ynn_active={row['ynnpack_active']}",
                    flush=True,
                )
                time.sleep(args.cooldown)

    summary = {}
    for side, label in (("A", "no_ynnpack"), ("B", "ynnpack")):
        summary[label] = {
            "prefill_tps": summarize(rows[side], "prefill_tps"),
            "decode_tps": summarize(rows[side], "decode_tps"),
            "ttft_s": summarize(rows[side], "ttft_s"),
            "failures": sum(1 for r in rows[side] if r["rc"] != 0),
            "ynnpack_active_runs": sum(
                1 for r in rows[side] if r["ynnpack_active"]
            ),
            "delegate_msg_runs": sum(
                1 for r in rows[side] if r["ynn_delegate_msgs"] > 0
            ),
        }
    (outdir / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    sys.exit(main())
