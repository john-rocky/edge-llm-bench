#!/usr/bin/env python3
"""Vision-language response-time cells on the Mac (task family `vl-*`), v1.

One process launch per run of LiteRT-LM's own CLI (`//runtime/engine:
litert_lm_advanced_main`, the same engine the Kotlin / Swift / Python
`litert-lm` surfaces wrap) over ONE pinned image and ONE fixed prompt
(evaldata/vl/<set>/manifest.json), with `--benchmark` on so the engine reports
its own phase timings while still printing the reply. Everything else is the
CLI's default (sampler, vision backend follows the main backend, visual token
budget from the bundle) — each stated in the record's `conditions`. The CLI
refuses an image without an explicit `--vision_backend`, so the vision encoder
runs on the arm's own backend (cpu -> cpu, gpu -> gpu): arm identity.

Per run the record carries (metrics):
  vlResponseSeconds        = host wall from the request marker in the engine
                             log ("Running single-turn conversation") to the last
                             byte of the reply on stdout — image encoding +
                             prefill + decode, the seconds one image costs
  vlTimeToFirstTokenSeconds = the engine's own TTFT (BenchmarkInfo): prefill of
                             the image + prompt tokens up to the first sampled
                             token — it does NOT include the vision encoder
                             (TTFT ≈ vlPrefillSeconds + one decode step)
  vlMarkDurationsMS        = the engine's marks in ms; `vision_executor` is the
                             vision encoder's own clock, outside TTFT (added
                             2026-09-26; earlier records carry it only in their
                             stderr log, and the first S26 records only when it
                             was under 1 s — the log prints "1.73s" above that)
  vlFirstTokenHostSeconds  = request marker -> first reply byte on stdout
                             (image decode + vision encoder + prefill + the
                             first token as the CLI user sees it)
  vlPrefillTokens / vlPrefillTokensPerSec / vlDecodeTokens / vlDecodeTokensPerSec
                             from BenchmarkInfo (prefill turn 1 / decode turn 1)
  loadTimeSeconds          = process start -> request marker (engine creation,
                             weight load / conversion, cache)
  vlTextCheck              = pass | fail — the manifest's keyword rule over the
                             reply (benchmark-mode-needs-a-text-check)
  memoryPeakResidentMB (ps sampling), coldRun = true (fresh process)

Usage (normally via scripts/bench_matrix_mac.sh, which dispatches vl-* cells here):
  scripts/vl_response_mac.py --model-id litert-community/SmolVLM2-500M \
      --file SmolVLM2-500M.litertlm --backend cpu --runs 3 \
      --task vl-describe-catcouch-gen64 --output OUT/<slug>.jsonl --campaign-dir OUT

Environment:
  VL_RUNNER_DIR   dir with litert_lm_advanced_main + the prebuilt/macos_arm64
                  dylibs + ENGINE_VERSION (default .build/litert-lm-advanced-main-1dadd00c;
                  docs/vl-response-v1.md says how to build and stage it)
  VL_ENGINE_VERSION  stamped as engineVersion (default: VL_RUNNER_DIR/ENGINE_VERSION)
  VL_CACHE_ROOT   the engine's --cache_dir root (default .build/vl-cache/<model>;
                  keeps the XNNPACK weight cache out of the HF snapshot dir)
"""
import argparse
import datetime as dt
import glob
import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import time
import uuid

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HARNESS_STAMP = "vl-response-v1-2026-09-24"
DEFAULT_RUNNER = os.path.join(REPO, ".build", "litert-lm-advanced-main-1dadd00c")

# Task id -> image set under evaldata/vl/ (the manifest carries prompt, budget, text check)
TASK_SETS = {
    "vl-describe-catcouch-gen64": "cc0-cat-couch-1024",
}
DISPLAY = {
    "litert-community/SmolVLM2-500M": "SmolVLM2-500M",
    "litert-community/LFM2.5-VL-450M": "LFM2.5-VL-450M",
    "litert-community/LFM2.5-VL-1.6B": "LFM2.5-VL-1.6B",
    "litert-community/InternVL3-1B": "InternVL3-1B",
    "litert-community/Qwen2-VL-2B": "Qwen2-VL-2B",
    "litert-community/MiniCPM-V-4": "MiniCPM-V-4",
    "litert-community/gemma-4-E2B-it-litert-lm": "Gemma 4 E2B it",
    "litert-community/gemma-4-E4B-it-litert-lm": "Gemma 4 E4B it",
}


# Files whose recipe the lane already states elsewhere (quant-label-rule): the
# Gemma 4 .litertlm carries no recipe word and Google's repo ships no manifest;
# ios/BenchmarkApp/Sources/Models/ModelCatalog.swift and docs/dashboard-cells-v1.md
# name it. Non-transferable to any other bundle.
KNOWN_RECIPES = {
    "gemma-4-E2B-it.litertlm": "wNa8o8 (int2/int4/int8 + int8 activations, QAT) — Google's mobile schema (ModelCatalog.swift; not 'int4')",
    "gemma-4-E4B-it.litertlm": "wNa8o8 (int2/int4/int8 + int8 activations, QAT) — Google's mobile schema (ModelCatalog.swift; not 'int4')",
}


def quant_label(fname, manifest):
    if fname in KNOWN_RECIPES:
        return KNOWN_RECIPES[fname]
    """quant-per-arm-rule / quant-label-rule: the file name's word plus what the
    repo's litertlm_manifest.json says about that variant, no more. A `_fixB`
    file (vision graphs re-exported with the pooling inside the encoder) inherits
    its base variant's recipe line and says so."""
    m = re.search(r"(?<![a-z0-9])(mixed_int4|int4|int8|q8|fp16|bf16)(?![a-z0-9])", fname, re.I)
    word = m.group(1) if m else None
    detail, via = None, None
    if manifest:
        by_file = {v.get("file"): v for v in manifest.get("variants", [])}
        v = by_file.get(fname)
        if v is None and "_fixB" in fname:
            v = by_file.get(fname.replace("_fixB", ""))
            via = "the base variant's manifest line; fixB = vision graphs re-exported with the pooling inside the encoder, weights unchanged (card)"
        if v is not None:
            q = v.get("quantization") or v.get("recipe")
            detail = json.dumps(q, sort_keys=True) if isinstance(q, dict) else q
    parts = []
    if word:
        parts.append(f"{word} (file name)")
    if detail:
        parts.append(f"manifest: {detail}" + (f" [{via}]" if via else ""))
    if not parts:
        return "unstated (file name carries no recipe word; the repo manifest has no line for this file)"
    if not detail:
        parts.append("the repo manifest states no recipe for this file")
    return "; ".join(parts)


def sha256(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(chunk), b""):
            h.update(b)
    return h.hexdigest()


def sh(cmd):
    try:
        return subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ""


def host_snapshot():
    """load, CPU speed limit (pmset), foreign processes > 20 % CPU — disclose-hw-state."""
    load = sh(["sysctl", "-n", "vm.loadavg"])
    therm = sh(["pmset", "-g", "therm"])
    m = re.search(r"CPU_Speed_Limit\s*=\s*(\d+)", therm)
    limit = int(m.group(1)) if m else None
    thermal = "nominal" if (limit is None or limit >= 100) else f"throttled(cpu_speed_limit={limit})"
    others = []
    me = os.getpid()
    for line in sh(["ps", "-Ao", "pcpu,pid,comm", "-r"]).splitlines()[1:12]:
        parts = line.split(None, 2)
        if len(parts) < 3:
            continue
        try:
            pc, pid = float(parts[0]), int(parts[1])
        except ValueError:
            continue
        if pc >= 20.0 and pid != me:
            others.append(f"{os.path.basename(parts[2])}:{pc:.0f}%")
    return {"load": load, "thermal": thermal, "cpuSpeedLimit": limit, "others": others}


def device_info():
    mem_b = int(sh(["sysctl", "-n", "hw.memsize"]) or 0)
    return {
        "modelIdentifier": sh(["sysctl", "-n", "hw.model"]),
        "chip": sh(["sysctl", "-n", "machdep.cpu.brand_string"]),
        "systemName": "macOS",
        "systemVersion": f"Version {sh(['sw_vers', '-productVersion'])} (Build {sh(['sw_vers', '-buildVersion'])})",
        "processorCount": int(sh(["sysctl", "-n", "hw.ncpu"]) or 0),
        "physicalMemoryMB": mem_b // (1024 * 1024),
        "batteryState": "unknown",
        "buildConfiguration": "Release",
    }


# ---------------------------------------------------------------- BenchmarkInfo parsing
RE_TTFT = re.compile(r"Time to first token:\s*([0-9.]+)\s*s")
RE_TURN = re.compile(r"(Prefill|Decode) Turn (\d+): Processed (\d+) tokens in ([0-9.]+)(ms|s|us|m|h)")
RE_SPEED = re.compile(r"(Prefill|Decode) Speed:\s*([0-9.]+)\s*tokens/sec")
# "- name: 450.55 ms" (init phases) or an absl duration ("292.047708ms",
# "1.730355468s", "1m2.5s"; the marks) -> stored in ms
RE_PHASE = re.compile(r"^\s*- (.+?):\s*((?:[0-9.]+(?:h|m(?!s)))*[0-9.]+\s*(?:ms|us|ns|s))\s*$")
RE_DUR = re.compile(r"([0-9.]+)\s*(ms|us|ns|h|m|s)")
DUR_MS = {"h": 3.6e6, "m": 6e4, "s": 1e3, "ms": 1.0, "us": 1e-3, "ns": 1e-6}
ANSI = re.compile(r"\x1b\[[0-9;]*m")


def parse_benchmark(stderr_text):
    out = {"initPhasesMS": {}}
    m = RE_TTFT.search(stderr_text)
    if m:
        out["ttft_s"] = float(m.group(1))
    turns = RE_TURN.findall(stderr_text)
    speeds = RE_SPEED.findall(stderr_text)
    for kind, idx, ntok, dur, unit in turns:
        if idx != "1":
            continue
        secs = float(dur) * {"ms": 1e-3, "s": 1.0, "us": 1e-6, "m": 60.0, "h": 3600.0}[unit]
        out[f"{kind.lower()}_tokens"] = int(ntok)
        out[f"{kind.lower()}_seconds"] = secs
    for kind, tps in speeds:
        out.setdefault(f"{kind.lower()}_tps", float(tps))   # first turn's speed
    # "Init Phases (N):" and "Mark Durations (N):" are both lists of
    # "- name: <duration>" lines closed by a "---" rule; the phases print
    # "X ms", the marks an absl duration whose unit changes with the size
    # ("292.047708ms", "1.730355468s"), so every value is converted to ms.
    # The marks carry the vision encoder's own clock (`vision_executor`), which
    # the engine's TTFT does NOT include (TTFT = prefill + the first sampled
    # token; the response column does).
    section = None
    out["markDurationsMS"] = {}
    for line in stderr_text.splitlines():
        if "Init Phases" in line:
            section = "initPhasesMS"
            continue
        if "Mark Durations" in line:
            section = "markDurationsMS"
            continue
        if section:
            pm = RE_PHASE.match(ANSI.sub("", line))
            if pm:
                out[section][pm.group(1).strip()] = round(
                    sum(float(v) * DUR_MS[u] for v, u in RE_DUR.findall(pm.group(2))), 6)
            elif line.strip().startswith("---"):
                section = None
    return out


# ---------------------------------------------------------------- one run
def one_run(args, ctx, run_idx):
    runner_dir = ctx["runner_dir"]
    prompt = f"{ctx['prompt']} [image:{ctx['image_path']}]"
    cmd = [os.path.join(runner_dir, "litert_lm_advanced_main"),
           f"--backend={args.backend}",
           f"--vision_backend={args.backend}",
           f"--model_path={ctx['model_path']}",
           f"--input_prompt={prompt}",
           "--benchmark",
           f"--max_output_tokens={ctx['max_output_tokens']}",
           f"--cache_dir={ctx['cache_dir']}"]
    env = dict(os.environ, DYLD_LIBRARY_PATH=runner_dir)
    host = host_snapshot()
    events = []            # (mono, stream, chunk)
    lock = threading.Lock()

    def reader(stream, tag):
        fd = stream.fileno()
        while True:
            try:
                chunk = os.read(fd, 65536)
            except OSError:
                break
            if not chunk:
                break
            with lock:
                events.append((time.monotonic(), tag, chunk.decode("utf-8", "replace")))
        stream.close()

    t0 = time.monotonic()
    wall0 = dt.datetime.now(dt.timezone.utc)
    p = subprocess.Popen(cmd, cwd=runner_dir, env=env, stdin=subprocess.DEVNULL,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    th = [threading.Thread(target=reader, args=(p.stdout, "out"), daemon=True),
          threading.Thread(target=reader, args=(p.stderr, "err"), daemon=True)]
    for t in th:
        t.start()
    peak_rss_kb = 0
    while p.poll() is None:
        rss = sh(["ps", "-o", "rss=", "-p", str(p.pid)])
        try:
            peak_rss_kb = max(peak_rss_kb, int(rss))
        except ValueError:
            pass
        time.sleep(0.2)
        if time.monotonic() - t0 > args.timeout:
            p.kill()
    for t in th:
        t.join(timeout=5)
    t_exit = time.monotonic()
    rc = p.returncode
    host_after = host_snapshot()

    t_req = t_first = t_last = None
    out_parts, err_parts = [], []
    for mono, tag, text in events:
        if tag == "out":
            out_parts.append(text)
            if ANSI.sub("", text).strip():
                if t_first is None:
                    t_first = mono
                t_last = mono
        else:
            err_parts.append(text)
            if t_req is None and "Running single-turn conversation" in text:
                t_req = mono
    stderr_text = "".join(err_parts)
    reply_raw = "".join(out_parts)
    reply = re.sub(r"\s+", " ", ANSI.sub("", reply_raw)).strip()
    bench = parse_benchmark(stderr_text)

    slug = args.slug
    logs = os.path.join(args.campaign_dir, "logs")
    os.makedirs(logs, exist_ok=True)
    err_log = os.path.join(logs, f"{slug}_run{run_idx}.stderr.log")
    with open(err_log, "w") as f:
        f.write(f"# cmd: {' '.join(cmd)}\n# DYLD_LIBRARY_PATH={runner_dir}\n# exit={rc}\n")
        f.write(stderr_text)
    with open(os.path.join(logs, f"{slug}_run{run_idx}.stdout.txt"), "w") as f:
        f.write(reply + "\n")

    metrics = {"coldRun": True, "harnessStamp": HARNESS_STAMP, "exitCode": rc,
               "memoryPeakResidentMB": round(peak_rss_kb / 1024.0, 1),
               "initialThermalState": host["thermal"], "finalThermalState": host_after["thermal"],
               "totalWallSeconds": round(t_exit - t0, 3)}
    if t_req is not None:
        metrics["loadTimeSeconds"] = round(t_req - t0, 3)
        if t_last is not None:
            metrics["vlResponseSeconds"] = round(t_last - t_req, 3)
        if t_first is not None:
            metrics["vlFirstTokenHostSeconds"] = round(t_first - t_req, 3)
    if "ttft_s" in bench:
        metrics["vlTimeToFirstTokenSeconds"] = bench["ttft_s"]
    for k_src, k_dst in (("prefill_tokens", "vlPrefillTokens"), ("prefill_tps", "vlPrefillTokensPerSec"),
                         ("decode_tokens", "vlDecodeTokens"), ("decode_tps", "vlDecodeTokensPerSec"),
                         ("prefill_seconds", "vlPrefillSeconds"), ("decode_seconds", "vlDecodeSeconds")):
        if k_src in bench:
            metrics[k_dst] = round(bench[k_src], 4) if isinstance(bench[k_src], float) else bench[k_src]
    if bench.get("initPhasesMS"):
        metrics["vlInitPhasesMS"] = bench["initPhasesMS"]
    if bench.get("markDurationsMS"):
        metrics["vlMarkDurationsMS"] = bench["markDurationsMS"]
    low = reply.lower()
    hit = [w for w in ctx["keywords"] if w in low]
    metrics["vlTextCheck"] = "pass" if hit else "fail"
    metrics["vlKeywordsHit"] = hit
    invalid = len(re.findall(r"Invalid decode", stderr_text))
    if invalid:
        metrics["vlInvalidDecodeLines"] = invalid
    ok = rc == 0 and "vlResponseSeconds" in metrics and metrics["vlTextCheck"] == "pass" and not invalid

    rec = {
        "schemaVersion": 1,
        "id": str(uuid.uuid4()).upper(),
        "timestamp": wall0.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "runtime": f"{args.runtime}-{args.backend}",
        "engineVersion": ctx["engine_version"],
        "engineArtifact": ctx["engine_artifact"],
        "model": {
            "id": args.model_id, "hfRepoId": args.model_id, "displayName": DISPLAY.get(args.model_id, args.model_id),
            "primaryFile": args.file, "file": args.file, "hfFilePatterns": [args.file],
            "hfRevision": ctx["model_revision"], "quantization": ctx["quant_label"],
            "onDiskSizeMB": round(os.path.getsize(ctx["model_path"]) / 1e6, 1),
            "sha256": ctx["model_sha256"],
        },
        "modelRevision": ctx["model_revision"],
        "task": args.task,
        "device": ctx["device"],
        "conditions": {
            "vlPrompt": ctx["prompt"], "vlImages": 1, "vlImageFile": ctx["image_rel"],
            "vlImagePixels": f"{ctx['image_w']}x{ctx['image_h']}",
            "vlMaxOutputTokens": ctx["max_output_tokens"],
            "vlVisionBackend": f"{args.backend} (= --backend; the CLI refuses an image without an explicit --vision_backend, so the arm's backend is used for the vision encoder too)",
            "vlVisualTokenBudget": "engine default (-1: the bundle's own)",
            "sampler": "engine default (litert_lm_advanced_main flags untouched: repetition_penalty 1.0, no penalties, no constraint)",
            "cacheDir": os.path.relpath(ctx["cache_dir"], REPO),
            "warm": False, "unplugged": False,
            "thermalInitial": host["thermal"], "thermalFinal": host_after["thermal"],
        },
        "metrics": metrics,
        "outputSample": reply[:200],
        "response": reply,
        "provenance": {
            "imageSet": ctx["set_name"], "imageSha256": ctx["image_sha256"],
            "manifestSha256": ctx["manifest_sha256"], "modelSha256": ctx["model_sha256"],
            "repoManifest": ctx["repo_manifest_rel"],
            "hostBefore": host, "hostAfter": host_after,
            "command": " ".join(cmd), "stderrLog": os.path.relpath(err_log, REPO),
        },
    }
    with open(args.output, "a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    tag = "OK " if ok else "FAIL"
    print(f"{tag} run {run_idx}: exit={rc} load={metrics.get('loadTimeSeconds')}s "
          f"resp={metrics.get('vlResponseSeconds')}s ttft={metrics.get('vlTimeToFirstTokenSeconds')}s "
          f"prefill={metrics.get('vlPrefillTokens')}tok@{metrics.get('vlPrefillTokensPerSec')} "
          f"decode={metrics.get('vlDecodeTokens')}tok@{metrics.get('vlDecodeTokensPerSec')} "
          f"text={metrics['vlTextCheck']} rss={metrics['memoryPeakResidentMB']}MB "
          f"others={host['others'] or 'none'} | {reply[:80]!r}", flush=True)
    return ok


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model-id", required=True)
    ap.add_argument("--file", required=True, help="artifact file name inside the HF repo (cells file=)")
    ap.add_argument("--backend", choices=["cpu", "gpu"], required=True)
    ap.add_argument("--task", required=True)
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--runtime", default="litert-lm")
    ap.add_argument("--output", required=True, help="JSONL to append one record per run")
    ap.add_argument("--campaign-dir", required=True)
    ap.add_argument("--pause", type=float, default=5.0, help="seconds between runs")
    ap.add_argument("--timeout", type=float, default=1800.0)
    args = ap.parse_args()

    if args.task not in TASK_SETS:
        sys.exit(f"unknown vl task {args.task!r}; known: {sorted(TASK_SETS)}")
    runner_dir = os.path.abspath(os.environ.get("VL_RUNNER_DIR", DEFAULT_RUNNER))
    runner = os.path.join(runner_dir, "litert_lm_advanced_main")
    if not os.access(runner, os.X_OK):
        sys.exit(f"no litert_lm_advanced_main at {runner} (docs/vl-response-v1.md: build + stage)")

    # model file: HF cache snapshot (revision = snapshot dir) or VL_MODEL_DIR/<file>
    # (revision "local"; HF_SHA256SUMS there — "sha256  repo  file" lines from the
    # Hub API — lets the record say whether the local bytes ARE the published ones)
    org, name = args.model_id.split("/", 1)
    model_dir = os.path.abspath(os.environ.get("VL_MODEL_DIR", os.path.join(REPO, ".build", "vl-models")))
    cands = glob.glob(os.path.expanduser(f"~/.cache/huggingface/hub/models--{org}--{name}/snapshots/*/{args.file}"))
    hf_verified = None
    if cands:
        # keep the snapshot path (with its extension): the engine sniffs the
        # format from the file name, and the blob behind the symlink has none
        model_path = cands[0]
        model_revision = cands[0].split("/snapshots/")[1].split("/")[0]
    elif os.path.exists(os.path.join(model_dir, args.file)):
        model_path, model_revision = os.path.realpath(os.path.join(model_dir, args.file)), "local"
        sums = os.path.join(model_dir, "HF_SHA256SUMS")
        if os.path.exists(sums):
            for line in open(sums):
                parts = line.split()
                if len(parts) == 3 and parts[1] == args.model_id and parts[2] == args.file:
                    hf_verified = (parts[0] == sha256(model_path))
    else:
        # not staged: exit 75 (EX_TEMPFAIL) — bench_matrix_mac.sh logs SKIPPED with
        # the reason, so the table reads "not yet measured" instead of a failure
        print(f"SKIPPED {args.model_id} {args.file}: not in the HF cache or {model_dir} "
              f"(hf download {args.model_id} {args.file})", file=sys.stderr)
        sys.exit(75)
    if model_revision == "local" and hf_verified is not True:
        sys.exit(f"{model_path}: local copy is not verified against the Hub's LFS sha256 (HF_SHA256SUMS) — refusing")
    # the repo's litertlm_manifest.json (quant label detail), from the HF cache snapshot
    mcands = glob.glob(os.path.expanduser(f"~/.cache/huggingface/hub/models--{org}--{name}/snapshots/*/litertlm_manifest.json"))
    repo_manifest = mcands[0] if mcands else os.path.join(os.path.dirname(model_path), "litertlm_manifest.json")
    manifest = json.load(open(repo_manifest)) if os.path.exists(repo_manifest) else None

    set_name = TASK_SETS[args.task]
    set_dir = os.path.join(REPO, "evaldata", "vl", set_name)
    man_path = os.path.join(set_dir, "manifest.json")
    man = json.load(open(man_path))
    image_path = os.path.join(set_dir, man["image"]["file"])
    got = sha256(image_path)
    if got != man["image"]["sha256"]:
        sys.exit(f"image set mismatch: {man['image']['file']} sha256 {got} != manifest {man['image']['sha256']}")

    ver_file = os.path.join(runner_dir, "ENGINE_VERSION")
    engine_version = os.environ.get("VL_ENGINE_VERSION") or (open(ver_file).read().strip() if os.path.exists(ver_file) else "unknown")
    artifact = f"litert_lm_advanced_main sha256:{sha256(runner)} (bazel build //runtime/engine:litert_lm_advanced_main, LiteRT-LM {engine_version})"
    metal = os.path.join(runner_dir, "libLiteRtMetalAccelerator.dylib")
    if args.backend == "gpu":
        if not os.path.exists(metal):
            sys.exit(f"gpu backend needs {metal}")
        artifact += f"; libLiteRtMetalAccelerator.dylib sha256:{sha256(metal)}"
    cache_root = os.environ.get("VL_CACHE_ROOT", os.path.join(REPO, ".build", "vl-cache"))
    cache_dir = os.path.join(cache_root, re.sub(r"[^A-Za-z0-9_.-]", "_", f"{name}_{args.file}"))
    os.makedirs(cache_dir, exist_ok=True)

    ctx = {
        "runner_dir": runner_dir, "model_path": model_path, "model_revision": model_revision,
        "model_sha256": sha256(model_path), "quant_label": quant_label(args.file, manifest),
        "repo_manifest_rel": (os.path.relpath(repo_manifest, os.path.expanduser("~")) if manifest else None),
        "engine_version": engine_version, "engine_artifact": artifact, "cache_dir": cache_dir,
        "set_name": set_name, "image_path": image_path, "image_rel": os.path.relpath(image_path, REPO),
        "image_sha256": got, "image_w": man["image"]["width"], "image_h": man["image"]["height"],
        "manifest_sha256": sha256(man_path),
        "prompt": man["request"]["prompt"], "max_output_tokens": int(man["request"]["max_output_tokens"]),
        "keywords": [w.lower() for w in man["text_check"]["any_of"]],
        "device": device_info(),
    }
    args.slug = os.path.splitext(os.path.basename(args.output))[0]
    os.makedirs(args.campaign_dir, exist_ok=True)
    print(f"vl-response: {args.model_id} {args.file} backend={args.backend} runs={args.runs} "
          f"image={os.path.basename(image_path)} ({ctx['image_w']}x{ctx['image_h']}, sha256 {got[:12]}) "
          f"prompt={ctx['prompt']!r} max_output_tokens={ctx['max_output_tokens']} engine={engine_version}", flush=True)
    ok_all = True
    for r in range(1, args.runs + 1):
        if r > 1 and args.pause > 0:
            time.sleep(args.pause)
        ok_all &= one_run(args, ctx, r)
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
