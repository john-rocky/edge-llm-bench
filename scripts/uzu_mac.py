#!/usr/bin/env python3
"""Mac uzu SDK cells: one fresh engine process per run, schema-v1 JSONL.

Install uzu==0.5.30 in a private venv. See docs/uzu-arm-v1.md for provenance,
cache isolation, host snapshot input and the distinction between Metal allocation
high-water memory and process RSS. All captures here are contended smoke tests,
not performance measurements.
"""
import argparse
import asyncio
import ctypes
import datetime as dt
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import resource
import shlex
import signal
import subprocess
import sys
import time
import traceback
import uuid

from cell_gate import degenerate

REPO = Path(__file__).resolve().parents[1]
VERSION = "0.5.30"
STAMP = "uzu-mac-v1-2026-09-24"
TASKS = ("short-chat", "long-context-2048-gen256")
MEMORY_BASIS = ("uzu ChatReplyStats.memory_used_bytes: Metal device current_allocated_size "
                "high-water sampled on allocations in this engine context; not process RSS "
                "or phys_footprint; MB = 1,000,000 bytes")
RSS_BASIS = ("resource.getrusage(RUSAGE_CHILDREN).ru_maxrss in a fresh wrapper with exactly "
             "one SDK child; macOS bytes, converted to MB / 1e6; process lifetime RSS high-water, "
             "including model load and download")
RECIPE_LABELS = {
    "lalamo-d1cfe68e-bfloat16-default": "lalamo bfloat16 (default), lalamo@d1cfe68e9b0cee64705b83e4bde1bf650a01cb1a",
    "lalamo-d1cfe68e-qwen3-0.6b-mlx-affine-4bit-gs64": "lalamo@d1cfe68e9b0cee64705b83e4bde1bf650a01cb1a import of mlx-community Qwen3-0.6B-4bit, MLX affine 4-bit gs64",
    "lalamo-d1cfe68e-qwen3-1.7b-mlx-affine-4bit-gs64": "lalamo@d1cfe68e9b0cee64705b83e4bde1bf650a01cb1a import of mlx-community Qwen3-1.7B-4bit, MLX affine 4-bit gs64",
    "lalamo-d1cfe68e-qwen3-4b-mlx-affine-4bit-gs64": "lalamo@d1cfe68e9b0cee64705b83e4bde1bf650a01cb1a import of mlx-community Qwen3-4B-4bit, MLX affine 4-bit gs64"
}


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def task_input(task):
    budgets = dict(line.split() for line in (REPO / "prompts/text/budgets.tsv").read_text().splitlines()
                   if line.strip() and not line.startswith("#"))
    # Preserve the repository prompt without an additional system prompt.
    prompt = (REPO / f"prompts/text/{task}.txt").read_text().rstrip("\n")
    return prompt, int(budgets[task])


def host_snapshot(path, sample_load=False):
    """Read supplied machine facts and optionally sample load; never assume idle."""
    if path:
        data = json.loads(path.read_text())
        if not isinstance(data.get("device"), dict) or not isinstance(data.get("snapshot"), dict):
            raise ValueError("--host-info requires device and snapshot objects")
        if sample_load:
            loads = os.getloadavg()
            data["snapshot"].update(loadAverage=loads[0], loadAverages=list(loads),
                                    loadAverageApproximate=False, loadAverageWindow="1 minute",
                                    loadSampledAt=dt.datetime.now(dt.timezone.utc).isoformat(),
                                    loadSource="os.getloadavg")
        return data
    if sample_load:
        raise ValueError("--sample-load also requires --host-info for the device facts")
    return {
        "device": {"systemName": "macOS", "modelIdentifier": "unknown",
                   "systemVersion": "unknown", "batteryState": "unknown",
                   "buildConfiguration": "PyPI wheel (build flags not exposed)"},
        "snapshot": {"thermal": "unknown", "load": None, "others": None,
                     "charging": "unknown", "lowPowerMode": "unknown"},
        "source": "unavailable; supply device and snapshot objects with --host-info",
    }


def foundation_home():
    """Read the actual directory used by the pinned SDK before Engine.create."""
    foundation = ctypes.CDLL("/System/Library/Frameworks/Foundation.framework/Foundation")
    objc = ctypes.CDLL("/usr/lib/libobjc.A.dylib")
    foundation.NSHomeDirectory.argtypes = []
    foundation.NSHomeDirectory.restype = ctypes.c_void_p
    objc.sel_registerName.argtypes = [ctypes.c_char_p]
    objc.sel_registerName.restype = ctypes.c_void_p
    objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    objc.objc_msgSend.restype = ctypes.c_char_p
    return Path(objc.objc_msgSend(foundation.NSHomeDirectory(),
                                objc.sel_registerName(b"UTF8String")).decode()).resolve()


def artifact_identity(path):
    entries = [{"file": str(p.relative_to(path)), "bytes": p.stat().st_size, "sha256": sha256(p)}
               for p in sorted(path.rglob("*")) if p.is_file()]
    manifest = json.dumps(entries, sort_keys=True, separators=(",", ":")).encode()
    return {"files": entries, "bytes": sum(p["bytes"] for p in entries),
            "manifestSha256": hashlib.sha256(manifest).hexdigest(),
            "manifestBasis": "SHA256 of UTF-8 compact sorted-key JSON of the files array"}


def engine_call(args, budget):
    resolve = (f"await engine.model_by_path({str(args.model_path)!r})" if args.model_path else
               f"await engine.model({args.model_id!r})")
    ctx = f".with_context_length(ContextLength.Custom({args.context_tokens}))" if args.context_tokens else ""
    messages = "[ChatMessage.user().with_text(prompt)]"
    if args.thinking == "off":
        messages = ("[ChatMessage.system().with_reasoning_effort(ReasoningEffort.Disabled), "
                    "ChatMessage.user().with_text(prompt)]")
    return (f"engine = await Engine.create(EngineConfig.create()"
            f".with_allow_ollama_usage(False).with_allow_lmstudio_usage(False)); model = {resolve}; "
            + ("" if args.model_path else "await engine.download_state(model); await engine.download(model) [consume iterator]; await engine.download_state(model) [require Downloaded]; ")
            + f"session = await engine.chat(model, ChatConfig.create(){ctx}); "
            f"await session.reply({messages}, "
            f"ChatReplyConfig.create().with_token_limit({budget})"
            ".with_sampling_method(SamplingMethod.Greedy()))")


def download_snapshot(state):
    if state is None:
        return None
    return {"phase": type(state.phase).__name__, "progress": state.progress,
            "downloadedBytes": state.downloaded_bytes, "totalBytes": state.total_bytes}


async def ensure_local_model(engine, model, payload, phases):
    """A registry origin can be local inference; only remote execution is refused."""
    payload["modelAccess"] = {"identifier": model.identifier, "isLocal": model.is_local,
                              "isRemote": model.is_remote, "isDownloadable": model.is_downloadable}
    if model.is_remote:
        raise RuntimeError("cloud/remote execution is not a local uzu arm")
    if model.is_downloadable:
        payload["downloadBefore"] = download_snapshot(await engine.download_state(model))
        # The official downloader is also used on cache hits; no manual store writes.
        async for update in (await engine.download(model)).iterator():
            payload["downloadState"] = download_snapshot(update)
            if isinstance(update.phase, phases.Error):
                raise RuntimeError(f"SDK download failed: {update.phase.message}")
        state = await engine.download_state(model)
        payload["downloadAfter"] = download_snapshot(state)
        if state is None or not isinstance(state.phase, phases.Downloaded):
            raise RuntimeError(f"local registry download incomplete: {payload['downloadAfter']}")
    path = await engine.model_path(model)
    if not path:
        raise RuntimeError("local model has no resolved filesystem path after download-state check")
    return Path(path).resolve()


async def worker(args):
    # An OS alarm in THIS process also bounds a blocked native SDK call; the
    # parent never sends a signal to a child or an earlier tool command's PID.
    signal.alarm(args.timeout)
    payload = {"pid": os.getpid(), "capturePurpose": "smoke only; not a measurement"}
    try:
        if sys.platform != "darwin":
            raise RuntimeError("uzu arm v1 is Mac-only")
        observed = importlib.metadata.version("uzu")
        if observed != VERSION:
            raise RuntimeError(f"expected uzu {VERSION}, observed {observed}")
        actual_home = foundation_home()
        if args.sdk_store == "private" and actual_home != args.cache_dir / "foundation-home":
            raise RuntimeError(f"SDK cache isolation failed: NSHomeDirectory={actual_home}")
        payload.update(engineVersion=f"uzu {observed}", cacheHome=str(actual_home), sdkStore=args.sdk_store)
        import uzu
        from uzu import ChatConfig, ChatMessage, ChatReplyConfig, ContextLength, DownloadPhase, Engine, EngineConfig, SamplingMethod, ReasoningEffort

        binaries = sorted(Path(uzu.__file__).parent.glob("*.so"))
        payload["engineArtifact"] = "; ".join(f"{p.name} sha256:{sha256(p)}" for p in binaries)
        engine = await Engine.create(EngineConfig.create().with_allow_ollama_usage(False)
                                    .with_allow_lmstudio_usage(False))
        model = (await engine.model_by_path(str(args.model_path)) if args.model_path else
                 await engine.model(args.model_id))
        if model is None:
            raise RuntimeError("model lookup returned None")
        path = await ensure_local_model(engine, model, payload, DownloadPhase)
        payload["modelPath"] = str(path)
        payload["artifact"] = artifact_identity(path)
        chat = ChatConfig.create()
        if args.context_tokens:
            chat = chat.with_context_length(ContextLength.Custom(args.context_tokens))
        t0 = time.monotonic()
        session = await engine.chat(model, chat)
        payload["loadTimeSeconds"] = time.monotonic() - t0
        prompt, budget = task_input(args.task)
        config = (ChatReplyConfig.create().with_token_limit(budget)
                  .with_sampling_method(SamplingMethod.Greedy()))
        t0 = time.monotonic()
        messages = [ChatMessage.user().with_text(prompt)]
        if args.thinking == "off":
            messages.insert(0, ChatMessage.system().with_reasoning_effort(ReasoningEffort.Disabled))
        replies = await session.reply(messages, config)
        payload["replyWallSeconds"] = time.monotonic() - t0
        if len(replies) != 1:
            raise RuntimeError(f"expected one reply without tools, got {len(replies)}")
        reply = replies[0]
        payload["text"] = reply.message.text or ""
        payload["reasoning"] = reply.message.reasoning or ""
        fields = ("duration", "time_to_first_token", "prefill_tokens_per_second",
                  "generate_tokens_per_second", "tokens_count_input", "tokens_count_input_cached",
                  "tokens_count_output", "memory_used_bytes", "total_joules")
        payload["stats"] = {key: getattr(reply.stats, key) for key in fields}
        for key, value in payload["stats"].items():
            if isinstance(value, float) and not math.isfinite(value):
                # Keep invalid native counters visible in strict JSON; the
                # parent fails the numeric gate, rather than losing the record.
                payload["stats"][key] = f"nonfinite:{value}"
        payload["finishReason"] = str(reply.finish_reason)
        payload["ok"] = True
    except Exception as e:
        payload.update(ok=False, error=f"{type(e).__name__}: {e}")
        traceback.print_exc()
    args.worker_result.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    return 0 if payload["ok"] else 1


def rss_wrapper(args):
    """Separate wrapper per run: RUSAGE_CHILDREN never includes earlier runs."""
    signal.alarm(args.timeout + 30)
    # The parent appends --rss-result last. Remove it before the SDK worker,
    # leaving --worker-result so the grandchild executes exactly one engine.
    cmd = [sys.executable, str(Path(__file__).resolve()), *sys.argv[1:-2]]
    child = subprocess.run(cmd)
    peak = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    args.rss_result.write_text(json.dumps({
        "capturePurpose": "smoke only; not a measurement", "childPeakRSSBytes": peak,
        "basis": RSS_BASIS, "childExitCode": child.returncode,
    }, indent=2) + "\n")
    return child.returncode if child.returncode >= 0 else 128 - child.returncode


def run_once(args, index, prompt, budget):
    uid = uuid.uuid4().hex
    stem = f"{args.output.stem}_{uid}_run{index}"
    logs = args.campaign_dir / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    raw = logs / f"{stem}.sdk.json"
    rss_path = logs / f"{stem}.rss.json"
    log = logs / f"{stem}.log"
    cmd = [sys.executable, str(Path(__file__).resolve()), *sys.argv[1:],
           "--worker-result", str(raw), "--rss-result", str(rss_path)]
    env = dict(os.environ, HF_HOME=str(args.cache_dir / "huggingface"), HF_HUB_DISABLE_XET="1",
               XDG_CACHE_HOME=str(args.cache_dir), XDG_CONFIG_HOME=str(args.cache_dir / "config"),
               TMPDIR=str(args.cache_dir / "tmp"), PYTHONPYCACHEPREFIX=str(args.cache_dir / "pycache"))
    if args.sdk_store == "private":
        env["CFFIXED_USER_HOME"] = str(args.cache_dir / "foundation-home")
    else:
        # The normal-store option lets the SDK use its ordinary home store.
        env.pop("CFFIXED_USER_HOME", None)
    # No inherited cloud credentials or local registry scan; this instrument is local inference.
    for key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "XAI_API_KEY",
                "BASETEN_API_KEY", "OPENROUTER_API_KEY", "MIRAI_API_KEY", "LOCAL_PATH"):
        env.pop(key, None)
    before = host_snapshot(args.host_info, args.sample_load)
    timestamp = dt.datetime.now(dt.timezone.utc).isoformat()
    start = time.monotonic()
    with log.open("w") as f:
        f.write(f"SMOKE ONLY; non-quiet host; not a measurement.\ncommand: {shlex.join(cmd)}\nengine call: {engine_call(args, budget)}\n")
        f.flush()
        proc = subprocess.run(cmd, env=env, stdout=f, stderr=subprocess.STDOUT)
    data = json.loads(raw.read_text()) if raw.exists() else {"error": f"worker exit {proc.returncode}; no SDK reply"}
    rss = json.loads(rss_path.read_text()) if rss_path.exists() else {}
    rss_bytes = rss.get("childPeakRSSBytes")
    rss_ok = isinstance(rss_bytes, (float, int)) and math.isfinite(rss_bytes) and rss_bytes > 0
    after = host_snapshot(args.host_info, args.sample_load)
    stats = data.get("stats", {})
    text, reasoning = data.get("text", ""), data.get("reasoning", "")
    # The default preserves model thinking; --thinking off is an explicit mode.
    # Check and retain BOTH
    # channels so a 128-token thinking-only reply cannot masquerade as an answer.
    decoded = (f"<think>{reasoning}</think>\n" if reasoning else "") + text
    numeric = ("generate_tokens_per_second", "prefill_tokens_per_second", "time_to_first_token",
               "tokens_count_output", "tokens_count_input", "memory_used_bytes")
    finite = all(isinstance(stats.get(k), (float, int)) and math.isfinite(stats[k]) and stats[k] >= 0
                 for k in numeric)
    within_budget = isinstance(stats.get("tokens_count_output"), int) and 0 < stats["tokens_count_output"] <= budget
    check = {"nonempty": bool(decoded.strip()), "answerNonempty": bool(text.strip()),
             "reasoningNonempty": bool(reasoning.strip()), "replacementCharacters": "\ufffd" in decoded,
             "degenerate": degenerate(decoded[:200], 0.5),
             "method": "existing cell_gate.degenerate first-200-character 6-gram ratio < 0.5; nonempty; U+FFFD",
             "coherence": "requires human review of decodedText; not established by this heuristic"}
    check["passed"] = check["answerNonempty"] and not check["degenerate"] and not check["replacementCharacters"]
    metrics = {"coldRun": True, "initialThermalState": before["snapshot"].get("thermal", "unknown"),
               "finalThermalState": after["snapshot"].get("thermal", "unknown"),
               "exitCode": proc.returncode, "totalWallSeconds": time.monotonic() - start}
    if rss_ok:
        metrics["memoryPeakResidentMB"] = rss_bytes / 1e6
    mapping = {"generate_tokens_per_second": ("decodeTokensPerSecond", 1),
               "prefill_tokens_per_second": ("prefillTokensPerSecond", 1),
               "time_to_first_token": ("firstTokenLatencyMS", 1000),
               "tokens_count_input": ("promptTokenCount", 1),
               "tokens_count_output": ("generatedTokenCount", 1),
               "memory_used_bytes": ("memoryPeakAllocatedMB", 1e-6)}
    for source, (dest, scale) in mapping.items():
        value = stats.get(source)
        if isinstance(value, (int, float)) and math.isfinite(value):
            metrics[dest] = value * scale
    if "loadTimeSeconds" in data:
        metrics["loadTimeSeconds"] = data["loadTimeSeconds"]
    model_id = args.record_model_id or args.model_id or f"own-export/{args.model_path.name}"
    conditions = {"maxOutputTokens": budget, "sampler": "greedy", "warm": False,
                  "thinkingPolicy": "SDK ReasoningEffort.Disabled" if args.thinking == "off" else "model default; reasoning tokens count against the same total budget",
                  "thermalInitial": metrics["initialThermalState"], "thermalFinal": metrics["finalThermalState"],
                  "capturePurpose": "smoke", "timingStatus": "contended; not a measurement",
                  "hostQuiet": False,
                  "contextPolicy": "explicit allocation" if args.context_tokens else "engine/model default"}
    if args.thinking == "off":
        conditions["thinking"] = False
    for key in ("loadAverage", "loadAverageApproximate", "loadAverageWindow"):
        if key in before["snapshot"]:
            conditions[key] = before["snapshot"][key]
    if args.context_tokens:
        conditions.update(contextBudget=args.context_tokens, contextTokens=args.context_tokens)
    rec = {"schemaVersion": 1, "id": uid, "timestamp": timestamp, "runtime": "uzu",
           "engineVersion": data.get("engineVersion", "unavailable (worker failed before version witness)"),
           "engineArtifact": data.get("engineArtifact", "unavailable"),
           "model": {"id": model_id, "quantization": args.recipe,
                     "file": data.get("modelPath", str(args.model_path or args.model_id))},
           "task": args.task, "device": before["device"], "conditions": conditions, "metrics": metrics,
           "harnessStamp": STAMP, "outputSample": decoded[:200], "decodedText": decoded,
           "answerText": text, "reasoningText": reasoning, "textCheck": check,
           "checks": {"finiteNonnegativeMetrics": finite, "outputWithinBudget": within_budget, "processRSSPresent": rss_ok},
           "status": "ok" if data.get("ok") and proc.returncode == 0 and finite and within_budget and rss_ok and check["passed"] else "failed",
           "provenance": {"rawLog": str(log), "sdkReply": str(raw), "campaign": str(args.campaign_dir),
                          "command": shlex.join(cmd), "hostBefore": before, "hostAfter": after,
                          "memoryBasis": MEMORY_BASIS, "rssBasis": RSS_BASIS, "rssReport": str(rss_path),
                          "promptSha256": hashlib.sha256(prompt.encode()).hexdigest(),
                          "promptFile": f"prompts/text/{args.task}.txt", "artifact": data.get("artifact"),
                          "modelProvenance": "own export" if args.model_path else "Mirai published registry artifact",
                          "sdkStore": args.sdk_store, "sdkHome": data.get("cacheHome"),
                          "modelAccess": data.get("modelAccess"),
                          "downloadBefore": data.get("downloadBefore"), "downloadAfter": data.get("downloadAfter"),
                          "engineCall": engine_call(args, budget)}}
    if "error" in data:
        rec["failureDetail"] = data["error"]
    from jsonschema import Draft7Validator, FormatChecker
    Draft7Validator(json.loads((REPO / "schema/result.v1.json").read_text()), format_checker=FormatChecker()).validate(rec)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("a") as f:
        f.write(json.dumps(rec, ensure_ascii=False, allow_nan=False) + "\n")
    (logs / f"{stem}.text.txt").write_text("SMOKE ONLY; non-quiet host; not a measurement.\n\n" + decoded + "\n")
    print(f"{rec['status'].upper()} run {index}: exit={proc.returncode} tokens={stats.get('tokens_count_output')} "
          f"text_check={check['passed']} raw={raw}", flush=True)
    return rec["status"] == "ok"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    source = ap.add_mutually_exclusive_group(required=True)
    source.add_argument("--model-id", help="Mirai registry id or HF repository id")
    source.add_argument("--model-path", type=Path, help="local lalamo export directory")
    ap.add_argument("--record-model-id", help="stable own-export id for file= matrix cells")
    ap.add_argument("--recipe", required=True, help="exact converter or published recipe; never infer from bit count")
    ap.add_argument("--thinking", choices=("model-default", "off"), default="model-default",
                    help="off uses SDK reasoning control without editing the model template")
    ap.add_argument("--task", choices=TASKS, default="short-chat")
    ap.add_argument("--context-tokens", type=int)
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--pause", type=float, default=5)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--campaign-dir", type=Path)
    ap.add_argument("--cache-dir", type=Path, default=Path(os.environ.get("UZU_CACHE_DIR", REPO / ".cache/uzu")))
    ap.add_argument("--sdk-store", choices=("private", "normal"), default=os.environ.get("UZU_SDK_STORE", "private"),
                    help="normal uses the SDK's usual home model store; harness/cache files stay private")
    ap.add_argument("--host-info", type=Path, default=os.environ.get("UZU_HOST_INFO"))
    ap.add_argument("--sample-load", action="store_true", help="sample load locally before/after the SDK process")
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--worker-result", type=Path, help=argparse.SUPPRESS)
    ap.add_argument("--rss-result", type=Path, help=argparse.SUPPRESS)
    args = ap.parse_args()
    args.recipe = RECIPE_LABELS.get(args.recipe, args.recipe)
    if args.runs < 1 or args.pause < 0 or args.timeout < 1:
        ap.error("runs/timeout must be positive and pause nonnegative")
    if args.context_tokens is not None and args.context_tokens < 1:
        ap.error("context-tokens must be positive")
    if args.task == "long-context-2048-gen256" and args.context_tokens is None:
        ap.error("long-context-2048-gen256 requires --context-tokens (allocation, not prompt length)")
    if args.recipe.lower() in ("int4", "4bit", "4-bit"):
        ap.error("recipe must name the actual recipe, not just its bit width")
    args.output = args.output.resolve()
    args.cache_dir = args.cache_dir.resolve()
    args.campaign_dir = (args.campaign_dir or args.output.parent).resolve()
    if args.host_info:
        args.host_info = Path(args.host_info).resolve()
    if args.model_path:
        args.model_path = args.model_path.resolve()
    prompt, budget = task_input(args.task)
    if args.dry_run:
        for index in range(1, args.runs + 1):
            print(f"run {index}/{args.runs} fresh process; pause={args.pause if index > 1 else 0}s; "
                  f"prompt=prompts/text/{args.task}.txt; maxOutputTokens={budget}; recipe={args.recipe}")
            print(engine_call(args, budget))
        return 0
    if args.rss_result:
        return rss_wrapper(args)
    if args.worker_result:
        return asyncio.run(worker(args))
    for name in ("foundation-home", "huggingface", "tmp", "config", "pycache"):
        (args.cache_dir / name).mkdir(parents=True, exist_ok=True)
    ok = True
    for index in range(1, args.runs + 1):
        if index > 1:
            time.sleep(args.pause)
        ok = run_once(args, index, prompt, budget) and ok
        if not ok:
            break  # preserve the failed record; never retry a denial or failed smoke
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
