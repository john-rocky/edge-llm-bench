"""Mac CPU prefill ladder: the shape reference for the Galaxy S26 ladder
(ORT GenAI 1K prefill diagnosis, round r2b, 2026-10-07). Its numbers are for
the shape (does the per-token prefill cost stay flat as the prompt grows?),
not for comparison with any other row.

The S26 ladder runs upstream model_benchmark (benchmark/c v0.17.0) as
    model_benchmark -i <dir> --use_random_tokens -l N -g 8 -ml 2048 -r 1 -w 0
and this is the same measurement on the Mac CPU in the r1 venv
(onnxruntime-genai 0.17.1 + onnxruntime 1.30.0): one fresh process per N,
model load, a generator with max_length 2048 and min_length N + 8 (as
model_benchmark's MakeGeneratorParams), N random token ids in [0, 99] (its
--use_random_tokens), the wall time of append_tokens (its "Prompt
processing"), then 8 generate_next_token calls. Upstream benchmark_e2e.py
does not run in the r1 venv (it imports pandas and psutil, which the venv does
not have, and the venv is not changed), hence this script.

--profile N adds one process at N with ORT run-level profiling switched on
around append_tokens only (set_runtime_option("enable_profiling", prefix),
as model_benchmark --profile_prefill does), which writes
<out>/mac_prefill_profile_<timestamp>.json; its prefill time carries the
profiler's cost and is not a ladder point.

Telemetry off: ORT_DISABLE_TELEMETRY=1 is set at the top of this file, before
anything can load onnxruntime, so the parent and every child run with it; the
parent never imports onnxruntime or onnxruntime_genai (versions come from the
package metadata); each child also calls disable_telemetry_events(); the
telemetry directory is listed before and after the ladder. (The first version
imported both packages in the parent without the variable: that parent ran
ORT with its telemetry on, see ROUND2b.md.)

usage: python -I mac_ladder.py <model dir> <out dir> [--lengths 64,256,512,1024]
                               [--profile 1024] [--gen 8] [--max-length 2048]
Writes <out>/mac_ladder.jsonl (one JSON line per process) and appends to
<out>/mac_ladder.log.
"""
import os

os.environ["ORT_DISABLE_TELEMETRY"] = "1"  # before any import that could load onnxruntime

import argparse
import importlib.metadata
import json
import random
import resource
import subprocess
import sys
import time
from pathlib import Path

TELEMETRY_DIR = Path.home() / "Library/Application Support/Microsoft/DeveloperTools/.onnxruntime"


def child(args):
    if os.environ.get("ORT_DISABLE_TELEMETRY") != "1":
        raise SystemExit("ORT_DISABLE_TELEMETRY=1 missing from the child environment")
    import onnxruntime_genai as og

    og.disable_telemetry_events()
    n = args.child
    t0 = time.perf_counter()
    model = og.Model(str(args.model_dir))
    load_ms = (time.perf_counter() - t0) * 1e3
    params = og.GeneratorParams(model)
    params.set_search_options(max_length=args.max_length, min_length=n + args.gen)
    t0 = time.perf_counter()
    gen = og.Generator(model, params)
    generator_ms = (time.perf_counter() - t0) * 1e3
    rng = random.Random()
    tokens = [rng.randrange(100) for _ in range(n)]
    if args.profile_prefix:
        gen.set_runtime_option("enable_profiling", args.profile_prefix)
    t0 = time.perf_counter()
    gen.append_tokens(tokens)
    prefill_ms = (time.perf_counter() - t0) * 1e3
    if args.profile_prefix:
        gen.set_runtime_option("enable_profiling", "0")
    steps = []
    for _ in range(args.gen):
        t0 = time.perf_counter()
        gen.generate_next_token()
        gen.is_done()
        steps.append((time.perf_counter() - t0) * 1e3)
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss  # bytes on macOS
    print("MACLADDER " + json.dumps({
        "n": n, "profiled": bool(args.profile_prefix), "load_ms": round(load_ms, 3),
        "generator_ms": round(generator_ms, 3), "prefill_ms": round(prefill_ms, 3),
        "prefill_per_token_ms": round(prefill_ms / n, 4), "prefill_tps": round(n / prefill_ms * 1e3, 2),
        "first_step_ms": round(steps[0], 3), "decode_steps_ms": [round(s, 3) for s in steps[1:]],
        "token_count": gen.token_count(), "peak_rss_mib": round(peak / 2**20, 1),
        "cpu_count": os.cpu_count(),
    }), flush=True)


def telemetry_listing():
    if not TELEMETRY_DIR.exists():
        return "absent"
    return sorted((p.name, p.stat().st_size, int(p.stat().st_mtime)) for p in TELEMETRY_DIR.iterdir())


def parent(args):
    args.out.mkdir(parents=True, exist_ok=True)
    log_path = args.out / "mac_ladder.log"
    jsonl = args.out / "mac_ladder.jsonl"

    def log(msg):
        line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
        print(line, flush=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    version = importlib.metadata.version
    log(f"versions: onnxruntime-genai {version('onnxruntime-genai')} onnxruntime {version('onnxruntime')} "
        f"python {sys.version.split()[0]}")
    log(f"model dir: {args.model_dir}")
    load = os.getloadavg()
    busy = subprocess.run(["ps", "-Ao", "pid,pcpu,comm", "-r"], capture_output=True, text=True).stdout.splitlines()[1:6]
    log(f"loadavg {load[0]:.2f} {load[1]:.2f} {load[2]:.2f}; top CPU: " + " | ".join(" ".join(b.split()) for b in busy))
    before = telemetry_listing()
    log(f"telemetry dir before: {before}")
    env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY")}
    assert env["ORT_DISABLE_TELEMETRY"] == "1"
    plan = [(n, None) for n in args.lengths]
    if args.profile:
        plan.append((args.profile, "mac_prefill_profile"))
    for n, prefix in plan:
        cmd = [sys.executable, "-I", os.path.abspath(__file__), str(args.model_dir), str(args.out),
               "--child", str(n), "--gen", str(args.gen), "--max-length", str(args.max_length)]
        if prefix:
            cmd += ["--profile-prefix", prefix]
        r = subprocess.run(cmd, cwd=args.out, env=env, capture_output=True, text=True, timeout=600)
        lines = [ln for ln in r.stdout.splitlines() if ln.startswith("MACLADDER ")]
        if r.returncode != 0 or not lines:
            log(f"n={n} profile={bool(prefix)} FAILED exit {r.returncode}: {(r.stderr or r.stdout)[-400:]!r}")
            return 1
        rec = json.loads(lines[-1][len("MACLADDER "):])
        with open(jsonl, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
        log(f"n={n} profiled={rec['profiled']} prefill {rec['prefill_ms']:.1f} ms = {rec['prefill_per_token_ms']:.3f} ms/token "
            f"({rec['prefill_tps']:.1f} tok/s); load {rec['load_ms']:.0f} ms; peak {rec['peak_rss_mib']} MiB")
        time.sleep(args.pause)
    after = telemetry_listing()
    log(f"telemetry dir {TELEMETRY_DIR}: " + ("unchanged" if before == after else f"CHANGED before={before} after={after}"))
    profiles = sorted(p.name for p in args.out.glob("mac_prefill_profile_*.json"))
    log(f"profiles: {profiles or 'none'}")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("model_dir", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--lengths", type=lambda s: [int(x) for x in s.split(",")], default=[64, 256, 512, 1024])
    ap.add_argument("--profile", type=int, default=0)
    ap.add_argument("--gen", type=int, default=8)
    ap.add_argument("--max-length", type=int, default=2048)
    ap.add_argument("--pause", type=float, default=3.0)
    ap.add_argument("--child", type=int, help=argparse.SUPPRESS)
    ap.add_argument("--profile-prefix", help=argparse.SUPPRESS)
    args = ap.parse_args()
    if args.child:
        child(args)
        return 0
    args.out = args.out.resolve()
    return parent(args)


if __name__ == "__main__":
    sys.exit(main())
