#!/usr/bin/env python3
"""Run one Android benchmark cell: N fresh-process runs -> schema-v1 JSON each.

  python3 android/bench/run_cell.py --runtime litert-lm --backend gpu \\
      --model-id litert-community/Qwen3-0.6B --task short-chat --runs 3 \\
      --out results/raw/<campaign>/app-path-android

Design decisions (methodology/android.md):
  - one engine process per run = COLD by the repo's definition; the very first
    run per (model, backend) builds engine caches and is labelled firstEver.
    Detection is a marker file on the DEVICE ({DEV_DIR}/markers/): the caches
    live there, so host-side state cannot know whether this device already
    compiled this (model, backend). litert-lm only — llama.cpp keeps no
    persistent compile cache, so its first run is an ordinary cold run.
  - metrics use BenchmarkResult field names (what build_summary.py reads);
    absent metrics stay absent. llama-cli has no TTFT; litert has no sampler
    control (conditions.sampler = "engine-default", a disclosed same-budget
    deviation).
  - the recorded runtime is litert-lm-<backend> / llama.cpp — backend is part
    of arm identity (the join key has no backend column; same convention as
    core-ai's -ane/-gpu model ids).
  - CPU affinity: BENCH_CPU_MASK (default f0 — upstream recommendation, tuned
    on Pixel 8a; empty = no taskset). Recorded per run in conditions; the mask
    is a per-device choice, see CPU_MASK below and devices/*.md.
  - RSS is sampled from /proc/<pid>/status (VmRSS) by an on-device loop ->
    memoryMedianResidentMB; iOS phys_footprint has no Android equivalent and
    is never fabricated.
"""
import argparse
import datetime
import hashlib
import json
import os
import statistics
import subprocess
import sys
import time
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from device_probe import adb, battery, device_info, thermal_status  # noqa: E402
import endurance_cell  # noqa: E402
import parsers  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEV_DIR = "/data/local/tmp/llmbench"
HARNESS_STAMP = "2026-08-android-cli-v1"
# CPU affinity mask for the engine process. "f0" (the upstream recommendation,
# tuned on Pixel 8a's 4 contiguous mid cores) is NOT device-neutral: on the
# Galaxy S26 (6 perf + 2 prime, no little cores) f0 spans the cluster boundary
# and collapses ggml's thread sync — 15 tok/s vs 105.6 unmasked on the same
# binary/model (probes: results/raw/2026-08-25-s26-llama-affinity-probes/).
# Empty string = no taskset. The actual value is recorded per run in
# conditions.cpuAffinity either way; devices/*.md states each device's choice.
CPU_MASK = os.environ.get("BENCH_CPU_MASK", "f0")
STRICT_SMOKE = os.environ.get("BENCH_STRICT_SMOKE") == "1"


def load_pins():
    p = os.path.join(ROOT, "android", "engine-pins.json")
    if not os.path.exists(p):
        return {}
    with open(p) as fh:
        return json.load(fh)


def observed_engine(binname, pins, serial):
    """Stamp the OBSERVED on-device binary, matched by sha256 against the pins
    registry — never 'the newest pin' (registry/witness rule: the binary that
    is on the device is the one that measured the row; during an A/B rehearsal
    two tags alternate on the same device)."""
    out = adb(["shell", f"sha256sum {DEV_DIR}/{binname}"], serial)
    sha = out.split()[0]
    key_by_bin = {"litert_lm_main": ("litert-lm", "litert_lm_main_sha256"),
                  "litert_lm_advanced_main": ("litert-lm", "litert_lm_advanced_main_sha256"),
                  "litert_lm_endurance_main": ("litert-lm", "litert_lm_endurance_main_sha256"),
                  "llama-cli": ("llama.cpp", "llama_cli_sha256"),
                  "llama-bench": ("llama.cpp", "llama_bench_sha256")}
    engine, field = key_by_bin[binname]
    for tag, entry in pins.get(engine, {}).items():
        if entry.get(field) == sha:
            return tag, sha
    return f"unknown (on-device {binname} sha unmatched in android/engine-pins.json)", sha


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_model(model_id, file_hint, runtime, serial):
    """HF-download (host cache) then adb-push once; returns (device_path, local_path).

    file= is REQUIRED when the repo holds more than one artifact: the quant
    variant is part of arm identity, and the Android arm must run the same
    file the iOS catalog pins (ModelCatalog primaryFile) — picking one by
    sort order would silently measure a different recipe.
    """
    # file= may be a LOCAL PATH (side-loaded artifact — e.g. a conversion that
    # is not published on HF, like the litert-local LFM/MiniCPM bundles): push
    # it directly, no download. Everything else resolves through the HF hub.
    if file_hint and os.path.exists(os.path.expanduser(file_hint)):
        local = os.path.expanduser(file_hint)
        dev_path = f"{DEV_DIR}/models/{model_id.replace('/', '_')}_{os.path.basename(local)}"
        push_verified(local, dev_path, serial)
        return dev_path, local
    from huggingface_hub import hf_hub_download, list_repo_files
    if file_hint:
        fname = file_hint
    else:
        files = list_repo_files(model_id)
        ext = ".litertlm" if runtime.startswith("litert-lm") else ".gguf"
        cands = [f for f in files if f.endswith(ext)]
        if len(cands) != 1:
            raise SystemExit(
                f"{model_id} holds {len(cands)} {ext} artifacts — pass file= in the "
                f"cell (match the iOS ModelCatalog primaryFile):\n  " + "\n  ".join(sorted(cands)))
        fname = cands[0]
    local = hf_hub_download(model_id, fname)
    # Guard against cache poisoning: a DIFFERENT downloader's interrupted
    # attempt can leave a truncated blob that hf_hub_download then trusts
    # (measured: 188 MB of a 1833 MB .litertlm, planted by the Mac app's
    # HubBridge — both platforms then failed on 'bad magic' / engine-create,
    # which read as an engine incompatibility until the size was checked).
    declared = None
    try:
        from huggingface_hub import HfApi
        info = HfApi().model_info(model_id, files_metadata=True)
        declared = next((f.size for f in info.siblings if f.rfilename == fname), None)
    except Exception:
        pass  # offline etc. — proceed on the cached file
    if declared and os.path.getsize(local) != declared:
        print(f"cached {fname} is {os.path.getsize(local)} bytes, HF declares "
              f"{declared} — re-downloading (poisoned cache)", file=sys.stderr)
        local = hf_hub_download(model_id, fname, force_download=True)
        if os.path.getsize(local) != declared:
            raise SystemExit(f"{fname}: size still mismatched after re-download")
    dev_path = f"{DEV_DIR}/models/{model_id.replace('/', '_')}_{fname}"
    push_verified(local, dev_path, serial)
    return dev_path, local


def push_verified(local, dev_path, serial):
    """Push unless the on-device file already matches the LOCAL SIZE. A bare
    existence check kept a truncated file forever after a mid-push USB drop
    (measured: 188 MB of a 1.8 GB .litertlm -> every run died on bad magic)."""
    want = os.path.getsize(local)
    have = subprocess.run(["adb"] + (["-s", serial] if serial else []) +
                          ["shell", f"stat -c %s {dev_path}"],
                          capture_output=True, text=True,
                          **({"timeout": 30} if os.environ.get("BENCH_SITTING") == "1" else {}))
    if STRICT_SMOKE:
        if have.returncode or have.stdout.strip() != str(want):
            raise SystemExit(f"strict smoke requires pre-staged matching model: {dev_path}")
        if adb(["shell", f"sha256sum {dev_path}"], serial).split()[0] != sha256_file(local):
            raise SystemExit(f"strict smoke model hash mismatch: {dev_path}")
        return
    if have.returncode == 0 and have.stdout.strip() == str(want):
        return
    adb(["shell", "mkdir", "-p", f"{DEV_DIR}/models"], serial)
    # A real (re)push means the engine caches that lived beside the old copy
    # are gone or stale, so this artifact's firstEver markers must go too —
    # otherwise the next run 1 rebuilds the cache with the marker still saying
    # "built" and pools as the engine's speed. Observed on the Pixel 8a
    # (2026-09-07): 10 markers present, 7 of their bundles deleted between the
    # split dashboard sessions to free storage.
    adb(["shell", f"rm -f {DEV_DIR}/markers/{os.path.basename(dev_path)}.*.cachebuilt"], serial)
    print(f"pushing {os.path.basename(local)} ({want >> 20} MB) …", file=sys.stderr)
    adb(["push", local, dev_path], serial, timeout=1800)
    out = adb(["shell", f"stat -c %s {dev_path}"], serial).strip()
    if out != str(want):
        raise SystemExit(f"push verification failed: device has {out} bytes, "
                         f"local is {want} — check the USB connection")


def push_prompt(task, serial):
    local = os.path.join(ROOT, "prompts", "text", f"{task}.txt")
    if not os.path.exists(local):
        raise SystemExit(f"no canonical prompt for task {task!r} "
                         "(scripts/gen_task_prompts.py; same-budget rule)")
    dev_path = f"{DEV_DIR}/prompts/{task}.txt"
    present = False
    if STRICT_SMOKE:
        found = adb(["shell", f"if [ -e {dev_path} ]; then sha256sum {dev_path}; else echo MISSING; fi"], serial)
        if found.strip() != "MISSING":
            if found.split()[0] != sha256_file(local):
                raise SystemExit(f"strict smoke refuses to overwrite prompt: {dev_path}")
            present = True
    if not present:
        adb(["shell", "mkdir", "-p", f"{DEV_DIR}/prompts"], serial)
        adb(["push", local, dev_path], serial)
    budget = None
    for line in open(os.path.join(ROOT, "prompts", "text", "budgets.tsv")):
        t, b = line.split("\t")
        if t == task:
            budget = int(b)
    return dev_path, budget


DEFAULT_LLAMA_CTX = 4096  # llama-cli otherwise defaults to the model's TRAINING
# context (Qwen3: 40960) — measured 4.8 GB RSS for a 0.6B Q4 before this pin.


def context_prompt(runtime, task, context_tokens):
    return (runtime == "litert-lm" and context_tokens is not None
            and not task.startswith(("native-", "endurance-")))


def capture_stem(runtime, backend, model_id, task, file_hint=None,
                 context_tokens=None, round_mode=False):
    arm = f"litert-lm-{backend}" if runtime == "litert-lm" else runtime
    stem = f"{arm}_{model_id.replace('/', '_')}_{task}"
    # Preserve legacy filenames, including native/endurance captures. The new
    # round path keys both allocation and the exact explicit artifact choice.
    if round_mode or (context_tokens is not None and not task.startswith(("native-", "endurance-"))):
        artifact = hashlib.sha256((file_hint or "auto").encode()).hexdigest()
        stem += f"__ctx{context_tokens or 'default'}_file{artifact}"
    return stem


def engine_command(runtime, backend, model_dev, task, prompt_dev, budget, max_tokens,
                   context_tokens):
    """The on-device command line for one run. Returns (cmd, binname, sampler, ctx_note)."""
    if runtime.startswith("litert-lm"):
        ctx = f" --max_num_tokens={context_tokens}" if context_tokens else ""
        ctx_note = context_tokens or "bundle-default"
        if task.startswith("native-benchmark-"):
            # ONLY advanced_main consumes the benchmark token counts (verified
            # in v0.16.0 sources AND on device: the plain main ran its default
            # ~20-token prompt regardless of the flags).
            p, d = task[len("native-benchmark-"):].split("x")
            core = (f"./litert_lm_advanced_main --backend={backend} --model_path={model_dev} "
                    f"--benchmark --benchmark_prefill_tokens={p} "
                    f"--benchmark_decode_tokens={d} --async=false{ctx}")
            return core, "litert_lm_advanced_main", "engine-default", ctx_note
        if context_prompt(runtime, task, context_tokens):
            # v0.16.0 plain main ignores both context and output limits.
            # --benchmark enables per-Conversation BenchmarkInfo; zero synthetic
            # token overrides retain the real prompt and native output cap.
            core = (f"./litert_lm_advanced_main --backend={backend} --model_path={model_dev} "
                    f"--input_prompt_file={prompt_dev} --max_num_tokens={context_tokens} "
                    f"--max_output_tokens={max_tokens or budget} --num_iterations=2 "
                    "--async=false --benchmark --benchmark_prefill_tokens=0 "
                    "--benchmark_decode_tokens=0 --use_session=false")
            return core, "litert_lm_advanced_main", "engine-default", ctx_note
        core = (f"./litert_lm_main --backend={backend} --model_path={model_dev} "
                f"--input_prompt_file={prompt_dev} "
                f"--max_output_tokens={max_tokens or budget} --async=false{ctx}")
        # no temperature/top-p flags exist -> engine-default sampling, disclosed
        return core, "litert_lm_main", "engine-default", ctx_note
    if runtime == "llama.cpp":
        # -t matches the taskset f0 mask (4 mid cores): llama-bench defaults to
        # 9 threads, which busy-poll against a 4-core mask and hang (measured:
        # >5 min without output; -t 4 completes in seconds).
        ctx = context_tokens or DEFAULT_LLAMA_CTX
        if task.startswith("native-benchmark-"):
            p, d = task[len("native-benchmark-"):].split("x")
            return (f"./llama-bench -m {model_dev} -t 4 -p {p} -n {d} -o json"), \
                "llama-bench", "n/a (llama-bench)", "llama-bench-managed"
        # -st (single-turn): b8999's llama-cli REJECTS --no-conversation ("not
        # supported") and then loops forever echoing "> " on stdin EOF —
        # measured as a silent 1800 s hang. Single-turn chat runs the template
        # once and exits; the model's template defaults apply (Qwen3: thinking
        # ON), disclosed via conditions.chatMode.
        return (f"./llama-cli -m {model_dev} -t 4 -c {ctx} -f {prompt_dev} "
                f"-n {max_tokens or budget} --temp 0 --top-p 1 -st"), \
            "llama-cli", "greedy", ctx
    raise SystemExit(f"unknown android runtime {runtime!r}")


def run_once(cmd, binname, serial, timeout):
    """One engine process with an RSS sampler wrapped around it on-device.

    $! is the backgrounded subshell, not the engine (measured: sampling it
    reads ~1.7 MB forever) — resolve the real pid with pgrep -n on the binary
    name and sample that."""
    # Engine output goes to an on-device file, cat'ed AFTER wait: a backgrounded
    # engine's stdout is block-buffered and its exit-time flush races the adb
    # pty teardown — a 7-minute gemma GPU run lost its entire BenchmarkInfo
    # that way (EXIT_CODE=0, zero engine lines) while short runs got lucky.
    # Absolute paths only: `cd X && engine & rest` backgrounds the WHOLE
    # `cd && engine` list in mksh, so `rest` never inherits the cd (measured:
    # cat looked for run_out.txt in the wrong cwd while the engine ran fine).
    taskset_prefix = f"taskset {CPU_MASK} " if CPU_MASK else ""
    output_file = f"{DEV_DIR}/run_out_{uuid.uuid4().hex}.txt" if STRICT_SMOKE else f"{DEV_DIR}/run_out.txt"
    rss_command = "grep -E 'VmRSS|VmHWM'" if STRICT_SMOKE else "grep VmRSS"
    timeout_prefix = ""
    if os.environ.get("BENCH_SESSION_DEADLINE"):
        remaining = float(os.environ["BENCH_SESSION_DEADLINE"]) - time.time()
        # Native timeout bounds only this launch's child, including USB loss.
        timeout_prefix = f"timeout -k 2 {max(1, int(min(timeout, remaining - 8)))} "
        timeout = min(timeout, max(1, remaining - 2))
    shell = (f"cd {DEV_DIR} && LD_LIBRARY_PATH=. {taskset_prefix}{timeout_prefix}{cmd} "
             f">{output_file} 2>&1 </dev/null & pid=$!; "
             f"sleep 1; epid=$(pgrep -n -f {binname}); [ -z \"$epid\" ] && epid=$pid; "
             "while kill -0 $pid 2>/dev/null; do "
             f"{rss_command} /proc/$epid/status 2>/dev/null; sleep 0.5; done; wait $pid; ec=$?; "
             f"echo ===ENGINE_OUTPUT===; cat {output_file}; echo EXIT_CODE=$ec")
    if STRICT_SMOKE:
        shell = "set -C; " + shell  # refuse even an accidental output-path collision
    try:
        out = adb(["shell", shell], serial, timeout=timeout)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        if not STRICT_SMOKE:
            raise
        out = exc.output or ""
        if isinstance(out, bytes):
            out = out.decode(errors="replace")
        out += f"\nHOST_ADB_FAILURE: {exc}\nEXIT_CODE={getattr(exc, 'returncode', 124)}\n"
    if STRICT_SMOKE:
        out += f"\nON_DEVICE_RAW_LOG={output_file}\n"
    rss_kb = [int(x) for x in
              (line.split()[1] for line in out.splitlines() if line.startswith("VmRSS"))]
    exit_code = 1
    for line in out.splitlines():
        if line.startswith("EXIT_CODE="):
            exit_code = int(line.split("=", 1)[1])
    return out, exit_code, (statistics.median(rss_kb) / 1024 if rss_kb else None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runtime", required=True, choices=["litert-lm", "llama.cpp"])
    ap.add_argument("--backend", default=None, choices=["cpu", "gpu"])
    ap.add_argument("--model-id", required=True)
    ap.add_argument("--file", default=None, help="artifact filename inside the HF repo")
    ap.add_argument("--task", required=True)
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--max-tokens", type=int, default=None)
    ap.add_argument("--context-tokens", type=int, default=None)
    ap.add_argument("--out", required=True)
    ap.add_argument("--serial", default=None)
    ap.add_argument("--first-ever", action="store_true",
                    help="force-mark run 1 as firstEver (the on-device marker "
                         "detects it automatically for litert-lm)")
    ap.add_argument("--cooldown", type=int, default=0,
                    help="seconds to sleep between runs 2..N (the campaign "
                         "runner passes COOLDOWN; bare CLI smoke runs default 0)")
    ap.add_argument("--timeout", type=int, default=1800)
    ap.add_argument("--round-index", type=int)
    ap.add_argument("--launch-index", type=int)
    ap.add_argument("--gate-timed-out", action="store_true")
    args = ap.parse_args()

    if args.runtime == "litert-lm" and not args.backend:
        ap.error("litert-lm needs --backend cpu|gpu (arm identity)")
    arm = f"litert-lm-{args.backend}" if args.runtime == "litert-lm" else "llama.cpp"

    if endurance_cell.ENDURANCE_TASK.match(args.task):
        if args.runtime != "litert-lm":
            ap.error("endurance-chat is litert-lm-only (needs the persistent-"
                     "conversation driver; methodology/endurance.md)")
        if args.runs > 1:
            print(f"WARNING --runs {args.runs} ignored for endurance — one "
                  "session per invocation; sessions are never pooled",
                  file=sys.stderr)
        return endurance_cell.run(args)

    pins = load_pins()

    model_dev, model_local = ensure_model(args.model_id, args.file, args.runtime, args.serial)
    prompt_dev = budget = None
    if not args.task.startswith("native-benchmark-"):
        prompt_dev, budget = push_prompt(args.task, args.serial)
    cmd, binname, sampler, ctx_note = engine_command(
        args.runtime, args.backend, model_dev, args.task,
        prompt_dev, budget, args.max_tokens, args.context_tokens)
    engine_version, engine_artifact = observed_engine(binname, pins, args.serial)
    if os.environ.get("BENCH_SITTING") == "1":
        expected_version = "v0.16.0" if args.runtime == "litert-lm" else "b8999"
        expected_field = "litert_lm_advanced_main_sha256" if args.runtime == "litert-lm" else "llama_cli_sha256"
        if engine_version != expected_version or engine_artifact != pins[args.runtime][expected_version][expected_field]:
            print(f"PIN MISMATCH before launch: {binname} {engine_version} {engine_artifact}", flush=True)
            return 5
    paired = context_prompt(args.runtime, args.task, args.context_tokens)
    extended = paired or args.round_index is not None or (
        args.context_tokens is not None and not args.task.startswith(("native-", "endurance-")))

    # firstEver detection: marker beside the on-device caches (see module doc).
    cache_built = True
    marker = None
    if args.runtime == "litert-lm":
        marker = (f"{DEV_DIR}/markers/"
                  f"{os.path.basename(model_dev)}.{args.backend}.cachebuilt")
        if paired:
            marker = marker.replace(".cachebuilt", f".{engine_artifact}.ctx{args.context_tokens}.cachebuilt")
        out = adb(["shell", f"ls {marker} >/dev/null 2>&1 && echo present || echo absent"],
                  args.serial)
        cache_built = "present" in out

    os.makedirs(args.out, exist_ok=True)
    dev = device_info(args.serial)
    model_sha = sha256_file(model_local)
    ok = 0
    for i in range(1, args.runs + 1):
        if i > 1 and args.cooldown:
            time.sleep(args.cooldown)
        raw_status, thermal_name = thermal_status(args.serial)
        batt = battery(args.serial)
        t0 = time.time()
        console, exit_code, rss_mb = run_once(cmd, binname, args.serial, args.timeout)
        elapsed = time.time() - t0
        launch_id = str(uuid.uuid4()) if extended else None
        launch_checks = {}

        if paired:
            iteration_metrics, launch_checks = parsers.context_prompt_results(
                console, args.context_tokens, args.max_tokens or budget)
            if STRICT_SMOKE and args.task == "long-context-2048-gen256" and any(
                    m.get("promptTokenCount", 0) < 1000 for m in iteration_metrics):
                launch_checks["protocolFlags"].append("real-long-prompt-not-prefilled")
            # Missing iterations still leave failed records and the whole log.
            iteration_metrics += [{} for _ in range(max(0, 2 - len(iteration_metrics)))]
            cold = True
            metrics = iteration_metrics[0]
        elif args.runtime == "llama.cpp" and args.task.startswith("native-benchmark-"):
            tests = parsers.parse_llama_bench_json(console)
            metrics = {}
            for t in tests:
                if t["kind"] == "prefill":
                    metrics["promptTokensPerSecond"] = t["avg_ts"]
                    metrics["promptTokenCount"] = t["n_prompt"]
                else:
                    metrics["decodeTokensPerSecond"] = t["avg_ts"]
                    metrics["generatedTokenCount"] = t["n_gen"]
            cold = False  # llama-bench repeats in-process (warm-ish regime)
        elif args.runtime == "llama.cpp":
            metrics = parsers.parse_llama_cli(console)
            cold = True
        else:
            metrics = parsers.parse_litert(console)
            cold = True

        if extended and not paired:
            invalid = console.lower().count("invalid decode")
            launch_checks = {"invalidDecodeCount": invalid,
                             "protocolFlags": ["invalid-decode"] if invalid else []}
        if extended and exit_code != 0:
            launch_checks["protocolFlags"].append(f"engine-exit-{exit_code}")
        if extended and "HOST_ADB_FAILURE:" in console:
            launch_checks["protocolFlags"].append("host-adb-failure")
        try:
            end_status, end_name = thermal_status(args.serial)
            end_batt = battery(args.serial) if extended else None
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            if not STRICT_SMOKE:
                raise
            end_status, end_name, end_batt = None, "unavailable", {}
            launch_checks.setdefault("protocolFlags", []).append("end-state-unavailable")
        metrics.update({
            "coldRun": cold,
            "harnessStamp": HARNESS_STAMP,
            "initialThermalState": thermal_name,
            "finalThermalState": end_name,
        })
        if rss_mb is not None:
            metrics["memoryMedianResidentMB"] = rss_mb
        high_water = [int(line.split()[1]) for line in console.splitlines() if line.startswith("VmHWM:")]
        if high_water:
            metrics["memoryPeakResidentMB"] = max(high_water) / 1024
        # every run until the first clean exit is (or may be finishing) the
        # cache build; the first run that exits 0 writes the marker
        if (args.first_ever and i == 1) or not cache_built:
            metrics["firstEver"] = True
        if exit_code == 0 and not cache_built and not launch_checks.get("protocolFlags"):
            adb(["shell", f"mkdir -p {DEV_DIR}/markers && touch {marker}"], args.serial)
            cache_built = True

        now = datetime.datetime.now(datetime.timezone.utc)
        iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        # filename stamp carries microseconds: two 1-run invocations of the
        # same cell inside one second silently OVERWROTE each other's record
        # and log (stored-report-rule) — caught by selftest.py on a fast CI
        # runner, where two payload rounds landed in the same second
        stamp = now.strftime("%Y-%m-%dT%H-%M-%S.%f")
        stem = capture_stem(args.runtime, args.backend, args.model_id, args.task,
                            args.file, args.context_tokens, args.round_index is not None)
        console_name = f"{stem}_{stamp}_run{i}.log"
        with open(os.path.join(args.out, console_name), "w") as fh:
            fh.write(console)

        rec = {
            "schemaVersion": 1,
            "id": str(uuid.uuid4()),
            "runtime": arm,
            "engineVersion": engine_version,
            "engineArtifact": engine_artifact,
            "model": {"id": args.model_id, "quantization": guess_quant(model_dev),
                      "file": os.path.basename(model_dev), "sha256": model_sha},
            "task": args.task,
            "timestamp": iso,
            "device": {**dev, "batteryLevel": batt["batteryLevel"],
                       "batteryState": batt["batteryState"]},
            "conditions": {"sampler": sampler,
                           "cpuAffinity": f"taskset {CPU_MASK}" if CPU_MASK else "none",
                           "contextTokens": ctx_note,
                           **({"chatMode": "single-turn template default (-st)"}
                              if args.runtime == "llama.cpp"
                              and not args.task.startswith("native-") else {}),
                           "thermalRawStatus": raw_status,
                           "thermalRawStatusFinal": end_status,
                           "screen": os.environ.get("BENCH_ROUND_WAKEFULNESS", "on-usb"), "elapsedSeconds": round(elapsed, 1),
                           "exitCode": exit_code},
            "metrics": metrics,
            "provenance": {"rawLog": console_name, "harness": "android/bench/run_cell.py"},
        }
        if extended:
            rec["conditions"].update({
                "roundIndex": args.round_index, "launchIndex": args.launch_index,
                "launchID": launch_id, "elapsedScope": "whole-launch",
                "stateAndMemoryScope": "whole-launch",
                "batteryTemperatureInitialC": batt.get("temperatureC"),
                "batteryTemperatureFinalC": end_batt.get("temperatureC"),
                "batteryLevelFinal": end_batt.get("batteryLevel"),
                "thermalGateTimedOut": args.gate_timed_out,
                "thermalGateTimeoutNonNominal": args.gate_timed_out and thermal_name != "nominal",
                "initialThermalNonNominal": thermal_name != "nominal",
                "outputTokenBudget": args.max_tokens or budget,
                "engineCommand": cmd, **launch_checks,
            })
        # Legacy paths retain their one-record shape. Context prompt iterations
        # share a launch/log/state sample, but never share token counters.
        samples = iteration_metrics if paired else [metrics]
        printed_texts = parsers.context_prompt_texts(console) if paired and os.environ.get("BENCH_TEXT_CHECK") == "1" else None
        any_text_failure = False
        for iteration, sample in enumerate(samples, 1):
            row = {**rec, "id": str(uuid.uuid4()) if paired else rec["id"],
                   "metrics": {**metrics, **sample}, "conditions": dict(rec["conditions"]),
                   "provenance": dict(rec["provenance"])}
            if paired:
                # Do not let iteration 1's token counters fill a missing run 2.
                row["metrics"] = {k: v for k, v in metrics.items() if k in (
                    "harnessStamp", "initialThermalState", "finalThermalState",
                    "memoryMedianResidentMB", "memoryPeakResidentMB", "firstEver")}
                row["metrics"].update(sample)
                row["metrics"]["coldRun"] = iteration == 1
                if iteration > 1:
                    row["metrics"].pop("firstEver", None)
            if extended:
                row["conditions"]["iterationIndex"] = iteration
                row["conditions"]["regime"] = ("cold" if iteration == 1 else "warm") if paired else "cold-process"
            if printed_texts is not None:
                value = printed_texts[iteration - 1] if iteration <= len(printed_texts) else ""
                verdict = parsers.text_integrity(value)
                row["conditions"]["protocolFlags"] = list(row["conditions"].get("protocolFlags", [])) + verdict["flags"]
                expected_prompt = os.environ.get("BENCH_EXPECT_PROMPT_TOKENS")
                if expected_prompt and sample.get("promptTokenCount") != int(expected_prompt):
                    row["conditions"]["protocolFlags"].append("prompt-token-count-mismatch")
                row["conditions"]["textCheck"] = verdict
                row["conditions"]["textOutputSHA256"] = hashlib.sha256(value.encode()).hexdigest()
                text_name = f"{stem}_{stamp}_run{i}_iter{iteration}.decoded.txt"
                with open(os.path.join(args.out, text_name), "w") as fh:
                    fh.write(value)
                row["provenance"]["decodedText"] = text_name
                any_text_failure |= bool(row["conditions"]["protocolFlags"])
            name = f"{stem}_{stamp}_run{i}{'_iter' + str(iteration) if paired else ''}.json"
            with open(os.path.join(args.out, name), "w") as fh:
                json.dump(row, fh, indent=2)
        d = metrics.get("decodeTokensPerSecond")
        status = "OK" if exit_code == 0 and d and not launch_checks.get("protocolFlags") and not any_text_failure else f"FAIL(exit={exit_code})"
        print(f"run {i}/{args.runs} {status} decode={d} thermal={thermal_name}->{end_name}")
        if launch_checks.get("protocolFlags"):
            print("protocol flags: " + ", ".join(launch_checks["protocolFlags"]))
        if exit_code == 0 and d and not launch_checks.get("protocolFlags") and not any_text_failure:
            ok += 1
    return 0 if ok == args.runs else 1


# Exact labels for known artifacts — same strings as the iOS ModelCatalog, so
# the same artifact never carries two labels across platforms (quant-label-rule:
# a bare "int4" is not a spec). Adding a model to android cells => add its
# label here (docs/OPERATIONS.md, add-a-model).
ANDROID_QUANT_LABELS = {
    "qwen3_0_6b_mixed_int4.litertlm": "INT4 (mixed, blockwise gs32)",
    # litert-community/Qwen3-{0.6B,1.7B} recipe files — the Mac catalog strings
    # (ModelCatalog liteRTLM) for the wi4b32 builds; the 1.7B INT8 file's label
    # is the repo manifest's recipe name (dynamic_wi8_afp32)
    "Qwen3-0.6B_dynamic_wi4b32_afp32.litertlm": "INT4 (dynamic, block-32 weights, FP32 act; GPU-graph build 2026-08-04)",
    "Qwen3-1.7B_dynamic_wi4b32_afp32.litertlm": "INT4 (dynamic, block-32 weights, FP32 act; GPU-graph build)",
    "Qwen3_1.7B.litertlm": "INT8 (dynamic_wi8_afp32: int8 weights, FP32 act; CPU-recipe file)",
    # 2026-09-14 dtype-only pair: one litert-torch main (6d4c622) GPU-graph export of
    # Qwen3-1.7B per recipe (fused qkv/gate_up, odml.rope + cache composites, bool mask,
    # prefill 1024, cache 4096); the two files differ in the quantization recipe only
    "Qwen3-1.7B_wi8_gpuflags.litertlm": "INT8 (dynamic_wi8_afp32: int8 weights, FP32 act; GPU-graph export 2026-09-14, dtype-only twin of the wi4b32 file)",
    "Qwen3-1.7B_wi4b32_gpuflags.litertlm": "INT4 (dynamic_wi4b32_afp32: block-32 weights, FP32 act; GPU-graph export 2026-09-14, dtype-only twin of the INT8 file)",
    # second pair of the same day: the same export with use_rope_composite off in both files (the
    # odml.rope composite broke the int8 file on the v0.16.0 Android GPU path; rope inlined)
    "Qwen3-1.7B_wi8_gpuflags_norope.litertlm": "INT8 (dynamic_wi8_afp32: int8 weights, FP32 act; GPU-graph export 2026-09-14, rope inlined, dtype-only twin of the wi4b32 file)",
    "Qwen3-1.7B_wi4b32_gpuflags_norope.litertlm": "INT4 (dynamic_wi4b32_afp32: block-32 weights, FP32 act; GPU-graph export 2026-09-14, rope inlined, dtype-only twin of the INT8 file)",
    "gemma-4-E2B-it.litertlm": "wNa8o8 (int2/int4/int8 + int8 activations, QAT)",
    "gemma-4-E4B-it.litertlm": "wNa8o8 (int2/int4/int8 + int8 activations, QAT)",
    # same artifact + label as the Mac endurance baseline row (thinking bundle,
    # disclosed there; ModelCatalog "Granite 4.2 3B (.litertlm, thinking)")
    "granite-4.2-3b_int4.litertlm": "int4 BOCTAV4 (block32, int8 embedder)",
    "DeepSeek-R1-Distill-Qwen-1.5B_multi-prefill-seq_q8_ekv4096.litertlm": "INT8",
    # litert-community filename recipe descriptors, kept verbatim (a bare
    # "int4" is not a spec; the descriptor is exactly what the repo states)
    "minicpm_wi4b32_wi8_afp32.litertlm": "wi4b32_wi8_afp32",
    "minicpm_wi4b32_wi8_afp32_gpu_opt.litertlm": "wi4b32_wi8_afp32 (gpu-opt)",
    "LFM2.5-1.2B-Instruct_int4.litertlm": "int4 (litert-community descriptor)",
    "LFM2.5-1.2B-Instruct_int4_gpu.litertlm": "int4_gpu (litert-community descriptor)",
    # litert-community/MiniCPM5-2B — labels are the repo manifest's recipe text,
    # the same strings as the Mac catalog entries (ModelCatalog liteRTLM).
    "MiniCPM5-2B_int8.litertlm": "INT8 (dynamic, linears + embedding; fp32 GPU activations declared)",
    "MiniCPM5-2B_int4.litertlm": "INT4 (blockwise-32 + OCTAV linears, int8 embedding; GPU activations fp16 default)",
}


def guess_quant(dev_path):
    """Exact label for known artifacts; otherwise only what the filename
    states (GGUF quant suffixes ARE specs), else 'unrecorded'."""
    base = os.path.basename(dev_path)
    for known, label in ANDROID_QUANT_LABELS.items():
        if base.endswith(known):
            return label
    low = base.lower()
    for pat in ("q4_k_m", "q8_0", "f16", "fp16"):
        if pat in low:
            return pat.upper() if pat.startswith("q") else pat
    return "unrecorded (artifact name carries no quant label)"


if __name__ == "__main__":
    sys.exit(main())
