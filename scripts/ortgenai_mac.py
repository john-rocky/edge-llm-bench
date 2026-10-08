#!/usr/bin/env python3
"""Mac ONNX Runtime GenAI cells (docs/ortgenai-arm-v1.md): one engine process per cell, its
--runs generations of the task's prompt appended to one schema-v1 JSONL, run 1 cold and
runs 2..N warm (the yardstick's --runs).

  <venv>/bin/python scripts/ortgenai_mac.py --model-id onnx-community/Qwen3-0.6B-ONNX \\
      --file onnxruntime/cpu_and_mobile/cpu-int4-kld-block-128 \\
      --revision da1453100cf3ff33ef56d17983fc7a8648706db6 --backend cpu \\
      --task short-chat --context-tokens 2048 --runs 4 \\
      --output results/raw/<campaign>/<cell>.jsonl

scripts/bench_matrix_mac.sh runs it for every `mac onnxruntime-genai` row of a cells file.
Install onnxruntime-genai==0.17.1, onnxruntime==1.30.0, onnxruntime-ep-webgpu==0.4.0,
huggingface_hub, onnx and jsonschema in a private venv and run this script with that venv's
python. The model is a published GenAI folder (genai_config.json + model.onnx + tokenizer):
--model-id + --file (the folder's path in the repo) + --revision resolve it through the HF
cache (snapshot_download of that folder only); --model-dir names a local folder instead. The
WebGPU arm registers the plugin EP and runs the folder whose genai_config names the webgpu
provider. model.quantization is the folder's entry in models/ortgenai-recipes.json (read from
its model.onnx by scripts/ortgenai_recipe.py); an unregistered folder is refused.

Regime (methodology/fairness-rules.md cold-warm-split; the yardstick's --runs N): the engine
process loads the model and the tokenizer once and generates --runs times from the same
prompt, each generation on a new Generator (GenAI allocates the KV cache for max_length
when a generator is created, so every run allocates its own). Run 1 is the process's first
generation: coldRun true, conditions.regime "cold (first generation in the process)". Runs
2..N: coldRun false, "warm (generation k of N in one process)"; the dashboards headline the
median of the warm runs on the Mac, as for every other Mac arm. --runs 1 is one cold run.
firstEver (--first-ever) marks run 1 only.

Records: --output <cell>.jsonl gets one compact JSON line per run (build_summary reads
results/raw/<campaign>/*.jsonl), written when the engine process has exited; the process's
harness log and engine report (.worker.json) and each run's decoded text go to
<campaign dir>/ortgenai-logs/. A run that fails stays a failed record; the runs after a
run that ended the engine process are not attempted (no record; the runner's gate reads
SHORT), as when a yardstick run throws.
Text: a long-context-* run carries conditions.textCheck = android/bench/parsers.text_integrity
of its decoded text (the screen the Android LiteRT-LM context-prompt launches carry); a
short-chat run is screened like every Apple arm, by the runner's post-capture gate
(cell_gate.degenerate on outputSample).

Telemetry: the engine process gets ORT_DISABLE_TELEMETRY=1 in its environment before
onnxruntime_genai is imported, and calls disable_telemetry_events(). --telemetry on drops
both; it exists only for the telemetry comparison and its records are evidence, not
measurements.

Timing, the cut points of upstream benchmark/c model_benchmark:
  prefill  = wall clock of Generator.append_tokens(prompt) (prompt forward pass + logits)
  TTFT     = append_tokens + the first generate_next_token (greedy pick from the prefill logits)
  decode   = tokens 2..N / the summed wall clock of their generate_next_token calls
Generation stops at EOS (is_done) or the task's output budget; no min_length.
Memory: per run, the parent samples the engine process's phys_footprint every 100 ms
(proc_pid_rusage RUSAGE_INFO_V4) from the run's generator creation to its last token, MiB
(bytes / 2^20), the Apple BenchmarkRunner basis (its window: after the load, the
generation). GPU identity per run: the GPU time the engine process accrued during that
run's generation (IOKit AGXDeviceUserClient AppUsage of its pid).
The worker and the parent hand over on stdin / stdout around every generation (READY k,
GO, DONE k, then NEXT or EXIT), so the parent's host snapshots, GPU-time reads, sampler
windows and the --pause between runs stay outside the timed region.

Staging: the engine loads a copy of the folder in a temporary dir (every file an APFS
clone of its real file, a hard link where cloning fails; removed when the cell ends) when
--overlay is given, or when the folder keeps its weights in model.onnx.data behind links
(the HF cache's snapshot links; onnxruntime 1.30.0 refuses external data whose real path
leaves the model's directory, "External data path escapes model directory"). Otherwise
it loads the folder in place. The HF cache is never written.
--overlay <JSON object>: merged into the folder's genai_config.json in the copy (a dict
merges key by key, any other value — provider_options, a number — replaces), e.g.
'{"model": {"decoder": {"session_options": {"intra_op_num_threads": 12}}}}'. The record
carries it verbatim (conditions.genaiConfigOverlay); model.quantization stays the label
of the folder's model.onnx (the overlay changes the session, not the weights). Lever
runs only: a dashboard cell runs the engine default.
"""
import os

# Any onnxruntime import in this (parent) process must find telemetry off: the engine
# libraries ship the 1DS SDK, ON by default, and an import without this variable writes
# to its store (r2b, 2026-10-07: a helper that imported onnxruntime in its parent). The
# worker's environment is built per run below (off, or on for the comparison runs only:
# ORTGENAI_TELEMETRY_COMPARISON=1 marks such a worker, and only it starts without the switch).
if os.environ.get("ORTGENAI_TELEMETRY_COMPARISON") != "1":
    os.environ.setdefault("ORT_DISABLE_TELEMETRY", "1")

import argparse  # noqa: E402
import ctypes
import datetime as dt
import difflib
import hashlib
import importlib.metadata
import importlib.util
import json
import math
from pathlib import Path
import plistlib
import re
import resource
import shlex
import shutil
import signal
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import uuid

import ortgenai_recipe

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "android" / "bench"))
from parsers import text_integrity  # noqa: E402  (the Android runner's lexical screen)

STAMP = "ortgenai-mac-v1-2026-10-07"
TASKS = ("short-chat", "long-context-1024-gen256")
VERSIONS = {"onnxruntime-genai": "0.17.1", "onnxruntime": "1.30.0", "onnxruntime-ep-webgpu": "0.4.0"}
RUNTIMES = {"cpu": "onnxruntime-genai-cpu", "webgpu": "onnxruntime-genai-webgpu"}
EPS = {"cpu": "CPUExecutionProvider", "webgpu": "WebGpuExecutionProvider"}
DEVICE_TYPES = {"cpu": "CPU", "webgpu": "WebGPU"}
TELEMETRY_DIR = Path.home() / "Library/Application Support/Microsoft/DeveloperTools/.onnxruntime"
QUIET_LOCK = Path(os.environ.get("QUIET_LOCK") or Path.home() / "code/coreai/_GPU_LOCK")
REGIME_COLD = "cold (first generation in the process)"
REGIME_WARM = "warm (generation {k} of {n} in one process)"
METRIC_DEFINITIONS = (
    "prefill tok/s = promptTokenCount / wall clock of Generator.append_tokens(prompt); "
    "TTFT = append_tokens + the first generate_next_token (greedy pick from the prefill logits, no forward pass); "
    "decode tok/s = (generatedTokenCount - 1) / summed wall clock of generate_next_token calls 2..N "
    "(each = one forward pass + greedy pick); generatedTokenCount counts every picked token, a final EOS included; "
    "stopReason stop = EOS (is_done), length = the output budget, max_length = the KV allocation filled, "
    "no min_length; memory = phys_footprint of the engine process, "
    "100 ms samples from the run's generator creation to its last token, high-water and median, "
    "MiB (bytes / 2^20); each run creates its own generator, and past_present_share_buffer true allocates "
    "the KV cache for max_length = contextTokens when a generator is created, so both memory numbers include it; "
    "regime: one engine process per cell, the model loaded once, run 1 = its first generation (cold), "
    "runs 2..N = later generations of the same prompt in that process (warm)")
MEMORY_BASIS = ("phys_footprint of the engine process (proc_pid_rusage RUSAGE_INFO_V4 ri_phys_footprint) "
                "sampled by the parent every 100 ms from the worker's READY <k> line (model and tokenizer "
                "loaded, run k's generator created) to its DONE <k> line (run k's last token); "
                "MiB = bytes / 2^20")


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def task_input(task):
    budgets = dict(line.split() for line in (REPO / "prompts/text/budgets.tsv").read_text().splitlines()
                   if line.strip() and not line.startswith("#"))
    # The repository prompt unchanged, no system prompt (same as uzu_mac.py).
    prompt = (REPO / f"prompts/text/{task}.txt").read_text().rstrip("\n")
    return prompt, int(budgets[task])


def sh(cmd):
    try:
        return subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ""


# ---------------------------------------------------------------- host facts (macOS APIs)
_libc = ctypes.CDLL("/usr/lib/libSystem.B.dylib", use_errno=True)


class RusageInfoV4(ctypes.Structure):
    _fields_ = [("ri_uuid", ctypes.c_uint8 * 16)] + [(name, ctypes.c_uint64) for name in (
        "ri_user_time", "ri_system_time", "ri_pkg_idle_wkups", "ri_interrupt_wkups", "ri_pageins",
        "ri_wired_size", "ri_resident_size", "ri_phys_footprint", "ri_proc_start_abstime",
        "ri_proc_exit_abstime", "ri_child_user_time", "ri_child_system_time", "ri_child_pkg_idle_wkups",
        "ri_child_interrupt_wkups", "ri_child_pageins", "ri_child_elapsed_abstime", "ri_diskio_bytesread",
        "ri_diskio_byteswritten", "ri_cpu_time_qos_default", "ri_cpu_time_qos_maintenance",
        "ri_cpu_time_qos_background", "ri_cpu_time_qos_utility", "ri_cpu_time_qos_legacy",
        "ri_cpu_time_qos_user_initiated", "ri_cpu_time_qos_user_interactive", "ri_billed_system_time",
        "ri_serviced_system_time", "ri_logical_writes", "ri_lifetime_max_phys_footprint", "ri_instructions",
        "ri_cycles", "ri_billed_energy", "ri_serviced_energy", "ri_interval_max_phys_footprint",
        "ri_runnable_time")]


class ProcFdInfo(ctypes.Structure):
    _fields_ = [("proc_fd", ctypes.c_int32), ("proc_fdtype", ctypes.c_uint32)]


_libc.proc_pid_rusage.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.POINTER(RusageInfoV4)]
_libc.proc_pidinfo.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_uint64, ctypes.c_void_p, ctypes.c_int]
_libc.clonefile.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint32]
RUSAGE_INFO_V4, PROC_PIDLISTFDS, PROX_FDTYPE_SOCKET = 4, 1, 2


def pid_rusage(pid):
    info = RusageInfoV4()
    return info if _libc.proc_pid_rusage(pid, RUSAGE_INFO_V4, ctypes.byref(info)) == 0 else None


def socket_fd_count(pid):
    size = _libc.proc_pidinfo(pid, PROC_PIDLISTFDS, 0, None, 0)
    if size <= 0:
        return None
    buf = (ProcFdInfo * (size // ctypes.sizeof(ProcFdInfo) + 32))()
    size = _libc.proc_pidinfo(pid, PROC_PIDLISTFDS, 0, buf, ctypes.sizeof(buf))
    if size <= 0:
        return None
    return sum(1 for i in range(size // ctypes.sizeof(ProcFdInfo)) if buf[i].proc_fdtype == PROX_FDTYPE_SOCKET)


def gpu_time_ns(pid):
    """Metal GPU time the process accrued so far: sum of AppUsage accumulatedGPUTime over the
    AGXDeviceUserClient objects IOKit lists for this pid (0 = the process opened no GPU client)."""
    try:
        clients = plistlib.loads(subprocess.check_output(["ioreg", "-a", "-r", "-c", "AGXDeviceUserClient"]))
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}
    total, n = 0, 0
    for c in clients or []:
        if str(c.get("IOUserClientCreator", "")).startswith(f"pid {pid},"):
            n += 1
            total += sum(int(u.get("accumulatedGPUTime", 0)) for u in c.get("AppUsage") or [])
    return {"ns": total, "clients": n}


def process_info():
    """NSProcessInfo thermalState and isLowPowerModeEnabled through the Objective-C runtime."""
    objc = ctypes.CDLL("/usr/lib/libobjc.A.dylib")
    ctypes.CDLL("/System/Library/Frameworks/Foundation.framework/Foundation")
    objc.objc_getClass.restype = ctypes.c_void_p
    objc.objc_getClass.argtypes = [ctypes.c_char_p]
    objc.sel_registerName.restype = ctypes.c_void_p
    objc.sel_registerName.argtypes = [ctypes.c_char_p]
    send = ctypes.cast(objc.objc_msgSend, ctypes.c_void_p).value
    send_obj = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(send)
    send_long = ctypes.CFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_void_p)(send)
    send_bool = ctypes.CFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)(send)
    info = send_obj(objc.objc_getClass(b"NSProcessInfo"), objc.sel_registerName(b"processInfo"))
    thermal = send_long(info, objc.sel_registerName(b"thermalState"))
    low_power = send_bool(info, objc.sel_registerName(b"isLowPowerModeEnabled"))
    return ({0: "nominal", 1: "fair", 2: "serious", 3: "critical"}.get(thermal, f"unknown({thermal})"),
            bool(low_power))


def device_info():
    mem = int(sh(["sysctl", "-n", "hw.memsize"]) or 0)
    return {"systemName": "macOS", "modelIdentifier": sh(["sysctl", "-n", "hw.model"]),
            "chip": sh(["sysctl", "-n", "machdep.cpu.brand_string"]),
            "systemVersion": f"Version {sh(['sw_vers', '-productVersion'])} (Build {sh(['sw_vers', '-buildVersion'])})",
            "processorCount": int(sh(["sysctl", "-n", "hw.ncpu"]) or 0),
            "physicalMemoryMB": mem // (1 << 20), "batteryState": "unknown",
            "buildConfiguration": "PyPI wheels (onnxruntime-genai cp314 macosx_12_0_arm64, onnxruntime "
                                  "macosx_14_0_arm64, onnxruntime-ep-webgpu macosx_14_0_universal2)"}


def quiet_window():
    try:
        return QUIET_LOCK.read_text(errors="replace").strip()
    except OSError:
        return ""


def host_snapshot(engine_pid=None):
    """disclose-hw-state: thermal, low power, load and the foreign processes above 20 % CPU
    (this harness and its engine process are not foreign)."""
    thermal, low_power = process_info()
    loads = os.getloadavg()
    others = []
    for line in sh(["ps", "-Ao", "pcpu,pid,comm", "-r"]).splitlines()[1:16]:
        parts = line.split(None, 2)
        try:
            pc, pid = float(parts[0]), int(parts[1])
        except (ValueError, IndexError):
            continue
        if pc >= 20.0 and pid not in (os.getpid(), engine_pid):
            others.append(f"{os.path.basename(parts[2])}:{pc:.0f}%")
    return {"device": device_info(),
            "snapshot": {"thermal": thermal, "lowPowerMode": low_power, "loadAverage": loads[0],
                         "loadAverages": list(loads), "loadSource": "os.getloadavg",
                         "others": others, "quietWindow": quiet_window(),
                         "sampledAt": dt.datetime.now(dt.timezone.utc).isoformat()},
            "source": "sysctl / sw_vers / NSProcessInfo / ps, read by the harness"}


def telemetry_dir_manifest(path):
    """Name, bytes, mtime and sha256 of every file the 1DS SDK keeps in its storage dir."""
    if not path.is_dir():
        return {"exists": False}
    return {"exists": True, "files": {p.name: {"bytes": p.stat().st_size, "mtimeNs": p.stat().st_mtime_ns,
                                               "sha256": sha256(p)}
                                      for p in sorted(path.iterdir()) if p.is_file()}}


def manifest_diff(before, after):
    b, a = before.get("files", {}), after.get("files", {})
    return {"added": sorted(set(a) - set(b)), "removed": sorted(set(b) - set(a)),
            "modified": sorted(k for k in set(a) & set(b) if a[k] != b[k]),
            "dirCreated": not before.get("exists") and after.get("exists", False)}


def engine_libraries():
    root = Path(importlib.util.find_spec("onnxruntime").submodule_search_locations[0]).parent
    libs = {}
    for rel in ("onnxruntime_genai/libonnxruntime-genai.dylib", "onnxruntime_genai/onnxruntime_genai.cpython-314-darwin.so",
                "onnxruntime/capi/libonnxruntime.1.30.0.dylib",
                "onnxruntime_ep_webgpu/libonnxruntime_providers_webgpu.dylib"):
        p = root / rel
        if p.exists():
            libs[rel] = {"sha256": sha256(p), "bytes": p.stat().st_size}
    return libs


def model_identity(model_dir):
    """HF revision and in-repo folder from an HF cache path .../snapshots/<sha>/<folder>."""
    parts = model_dir.parts
    if "snapshots" in parts:
        i = parts.index("snapshots")
        if i + 1 < len(parts) and re.fullmatch(r"[0-9a-f]{40}", parts[i + 1]):
            return parts[i + 1], "/".join(parts[i + 2:])
    return None, model_dir.name


def resolve_folder(model_id, folder, revision, local_only=False):
    """The GenAI folder `folder` of `model_id` at `revision` in the HF cache, downloading only
    that folder's files (snapshot_download allow_patterns). local_only: no network; None when
    the folder is not in the cache."""
    from huggingface_hub import snapshot_download
    try:
        snap = snapshot_download(model_id, revision=revision, allow_patterns=[f"{folder}/*"],
                                 local_files_only=local_only)
    except Exception:
        if local_only:
            return None
        raise
    path = Path(snap) / folder
    if not (path / "genai_config.json").exists() or not (path / "model.onnx").exists():
        if local_only:
            return None
        raise SystemExit(f"{model_id}@{revision}: {folder} has no genai_config.json / model.onnx")
    return path


def deep_merge(base, overlay):
    """genai_config.json with an overlay applied: a dict merges key by key (recursively); any
    other value (a list such as provider_options, a number, a string) replaces the base's."""
    if not isinstance(base, dict) or not isinstance(overlay, dict):
        return overlay
    merged = dict(base)
    for key, value in overlay.items():
        merged[key] = deep_merge(base[key], value) if key in base else value
    return merged


def staging_reason(model_dir, overlay):
    """Why the engine loads a staged copy of the folder instead of the folder itself (None: it
    does not). External data behind links: the HF cache's snapshot entries are links into its
    blob store, and onnxruntime 1.30.0 refuses a model.onnx.data whose real path leaves the
    directory of model.onnx's ("External data path escapes model directory", r4-mac 2026-10-08)."""
    if overlay is not None:
        return "genai_config overlay"
    data = model_dir / "model.onnx.data"
    if data.exists() and ((model_dir / "model.onnx").is_symlink() or data.is_symlink()):
        return "external data behind links"
    return None


def stage_folder(model_dir, overlay, reason):
    """A copy of the GenAI folder for the engine, in a new temporary dir: every file an APFS clone
    (clonefile) of its real file, a hard link where cloning fails, both on the same volume as the
    HF cache and neither writing to it; with an overlay, genai_config.json written with it applied.
    Returns (dir, provenance)."""
    stage = Path(tempfile.mkdtemp(prefix="ortgenai-stage-"))
    files = {}
    try:
        for src in sorted(model_dir.iterdir()):
            real, dst = src.resolve(), stage / src.name
            if real.is_dir():
                raise RuntimeError(f"{src} is a directory; a GenAI folder is flat")
            if src.name == "genai_config.json" and overlay is not None:
                config = deep_merge(json.loads(real.read_text()), overlay)
                dst.write_text(json.dumps(config, indent=4) + "\n")
                files[src.name] = {"method": "written (overlay applied)", "source": str(real), "sha256": sha256(dst)}
                continue
            if _libc.clonefile(os.fsencode(real), os.fsencode(dst), 0) == 0:
                method = "clonefile"
            else:
                err = ctypes.get_errno()
                os.link(real, dst)  # same volume or nothing: no byte copy of the weights
                method = f"hardlink (clonefile errno {err})"
            files[src.name] = {"method": method, "source": str(real), "bytes": dst.stat().st_size}
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    return stage, {"reason": reason, "dir": str(stage), "files": files}


def effective_config(model_dir, overlay):
    """The genai_config the engine reads: the folder's, with --overlay merged in."""
    config = json.loads((model_dir / "genai_config.json").read_text())
    return config if overlay is None else deep_merge(config, overlay)


def threads_condition(config):
    intra = config["model"]["decoder"]["session_options"].get("intra_op_num_threads")
    return "engine default" if intra is None else f"intra_op_num_threads {intra} (genai_config)"


# ---------------------------------------------------------------- engine process
def loaded_images(pattern):
    dyld = ctypes.CDLL("/usr/lib/libSystem.B.dylib")
    dyld._dyld_image_count.restype = ctypes.c_uint32
    dyld._dyld_get_image_name.restype = ctypes.c_char_p
    dyld._dyld_get_image_name.argtypes = [ctypes.c_uint32]
    names = (dyld._dyld_get_image_name(i) for i in range(dyld._dyld_image_count()))
    return sorted({n.decode() for n in names if n and pattern in n.decode()})


def worker(args):
    """One engine process: the model and the tokenizer once, then --runs generations of the same
    prompt, each on a new Generator. READY <k> / DONE <k> on stdout; the parent answers GO, then
    NEXT (another run) or EXIT on stdin, so its reads and the pause stay outside the timed region.
    The result file is rewritten after every run: a process that dies in run k leaves runs
    1..k-1. --timeout bounds the load with run 1, then each later run on its own."""
    signal.alarm(args.timeout)
    payload = {"pid": os.getpid(), "ok": False, "runs": []}

    def save():
        tmp = args.worker_result.with_name(args.worker_result.name + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n")
        tmp.replace(args.worker_result)

    def answer(word):
        line = sys.stdin.readline().strip()
        if line != word:
            raise RuntimeError(f"parent answered {line!r}, expected {word}")

    k = 0
    try:
        if args.telemetry == "off" and os.environ.get("ORT_DISABLE_TELEMETRY") != "1":
            raise RuntimeError("ORT_DISABLE_TELEMETRY=1 missing from the engine environment")
        t = time.perf_counter()
        import onnxruntime_genai as og
        payload["importSeconds"] = time.perf_counter() - t
        if args.telemetry == "off":
            og.disable_telemetry_events()
        payload["genai"] = {"version": og.__version__, "commit": og.__commit__}
        if args.backend == "webgpu":
            import onnxruntime_ep_webgpu as webgpu_ep
            name, lib = webgpu_ep.get_ep_name(), webgpu_ep.get_library_path()
            og.register_execution_provider_library(name, lib)
            payload["registered"] = {"name": name, "library": lib}
            print(f"[harness] register_execution_provider_library({name!r}, {lib!r}) returned", file=sys.stderr, flush=True)
        t = time.perf_counter()
        model = og.Model(og.Config(str(args.model_dir)))
        tokenizer = og.Tokenizer(model)
        payload["loadTimeSeconds"] = time.perf_counter() - t
        payload["deviceType"] = model.device_type
        print(f"[harness] model.device_type = {model.device_type}", file=sys.stderr, flush=True)
        if model.device_type != DEVICE_TYPES[args.backend]:
            raise RuntimeError(f"expected device_type {DEVICE_TYPES[args.backend]}, got {model.device_type}")
        prompt, budget = task_input(args.task)
        templated = tokenizer.apply_chat_template(json.dumps([{"role": "user", "content": prompt}]),
                                                  add_generation_prompt=True)
        ids = tokenizer.encode(templated)
        payload.update(templatedPromptSha256=hashlib.sha256(templated.encode()).hexdigest(),
                       templatedPromptTail=templated[-80:], promptTokenCount=int(len(ids)))
        eos = json.loads((args.model_dir / "genai_config.json").read_text())["model"]["eos_token_id"]
        eos = set(eos if isinstance(eos, list) else [eos])
        for k in range(1, args.runs + 1):
            if k > 1:
                signal.alarm(0)  # the parent's pause is not this run's time
                answer("NEXT")
                signal.alarm(args.timeout)
            # a new generator per run: its KV cache (max_length) is allocated and zero-filled here
            t = time.perf_counter()
            params = og.GeneratorParams(model)
            params.set_search_options(max_length=args.context_tokens, do_sample=False)
            generator = og.Generator(model, params)
            generator_seconds = time.perf_counter() - t
            if k == 1:
                payload["onnxruntimeImages"] = loaded_images("onnxruntime")
            r0 = resource.getrusage(resource.RUSAGE_SELF)
            print(f"READY {k}", flush=True)
            answer("GO")
            t0 = time.perf_counter()
            generator.append_tokens(ids)
            t1 = time.perf_counter()
            steps, tokens = [], []
            while not generator.is_done() and len(tokens) < budget:
                a = time.perf_counter()
                generator.generate_next_token()
                steps.append(time.perf_counter() - a)
                tokens.append(int(generator.get_next_tokens()[0]))
            t_end = time.perf_counter()
            r1 = resource.getrusage(resource.RUSAGE_SELF)
            print(f"DONE {k}", flush=True)
            hit_eos = bool(tokens) and tokens[-1] in eos
            # the repo's stopReason words (stop / length) plus max_length: the KV allocation filled
            payload["runs"].append(dict(
                run=k, generatorSeconds=generator_seconds, prefillSeconds=t1 - t0,
                firstStepSeconds=steps[0] if steps else None, decodeSeconds=sum(steps[1:]),
                generationWallSeconds=t_end - t0, stepSeconds=steps, tokens=tokens,
                generatedTokenCount=len(tokens), hitEos=hit_eos, sequenceLength=int(generator.token_count()),
                stopReason="stop" if hit_eos else ("length" if len(tokens) >= budget else "max_length"),
                cpuSecondsDuringGeneration=(r1.ru_utime - r0.ru_utime) + (r1.ru_stime - r0.ru_stime),
                text=tokenizer.decode(tokens[:-1] if hit_eos else tokens)))
            save()
            del generator, params  # this run's KV cache goes before the next run allocates its own
        signal.alarm(0)
        answer("EXIT")
        payload["ok"] = True
    except Exception as e:
        payload["error"] = f"{type(e).__name__}: {e}"
        payload["errorRun"] = k
        traceback.print_exc()
    save()
    return 0 if payload["ok"] else 1


# ---------------------------------------------------------------- parent side of one cell
class Sampler(threading.Thread):
    """Every 100 ms from spawn to exit: socket fds of the engine process (whole life) and its
    phys_footprint (kept only inside a run's READY..DONE window, one list per run)."""

    def __init__(self, pid):
        super().__init__(daemon=True)
        self.pid, self.window, self.stop, self.lock = pid, None, threading.Event(), threading.Lock()
        self.socket_max, self.socket_first, self.lifetime_max = 0, None, None
        self.start_time = time.monotonic()

    def read(self):
        info = pid_rusage(self.pid)
        if info is None:
            return None
        with self.lock:
            if self.window is not None:
                self.window.append(info.ri_phys_footprint)
            self.lifetime_max = info.ri_lifetime_max_phys_footprint
        return info

    def begin(self):
        """A run's window opens: the samples from here to end() are that run's."""
        with self.lock:
            self.window = []
        self.read()

    def end(self):
        self.read()
        with self.lock:
            samples, self.window = self.window or [], None
        return samples

    def run(self):
        while not self.stop.is_set():
            if self.read() is None:
                break
            sockets = socket_fd_count(self.pid)
            if sockets:
                self.socket_max = max(self.socket_max, sockets)
                if self.socket_first is None:
                    self.socket_first = {"atSeconds": time.monotonic() - self.start_time,
                                         "lsof": sh(["lsof", "-nP", "-a", "-p", str(self.pid)]).splitlines()[-40:]}
            self.stop.wait(0.1)


class LsofWatch(threading.Thread):
    """Evidence only: `lsof -nP -i -a -p <pid>` every 0.5 s while the engine process lives."""

    def __init__(self, pid, path):
        super().__init__(daemon=True)
        self.pid, self.path, self.stop, self.polls, self.max_entries = pid, path, threading.Event(), 0, 0

    def run(self):
        start = time.monotonic()
        with self.path.open("w") as f:
            f.write(f"# lsof -nP -i -a -p {self.pid} every 0.5 s; one block per poll; entries = output lines after the header\n")
            while not self.stop.is_set():
                if pid_rusage(self.pid) is None:
                    break
                out = subprocess.run(["lsof", "-nP", "-i", "-a", "-p", str(self.pid)], capture_output=True, text=True).stdout
                lines = [ln for ln in out.splitlines() if ln.strip()]
                entries = max(0, len(lines) - 1)
                self.polls += 1
                self.max_entries = max(self.max_entries, entries)
                f.write(f"t={time.monotonic() - start:7.2f}s entries={entries}\n" + "".join(f"  {ln}\n" for ln in lines))
                f.flush()
                self.stop.wait(0.5)
            f.write(f"# polls={self.polls} max_entries={self.max_entries}\n")


def text_verdict(task, text):
    """conditions.textCheck of a long-context-* run: parsers.text_integrity unchanged, the screen
    the Android LiteRT-LM context-prompt launches carry (text-check-rule; the same bar for every
    arm). None for short-chat: the runner's post-capture gate screens outputSample
    (cell_gate.degenerate), as for every Apple arm."""
    return text_integrity(text) if task.startswith("long-context-") else None


def mib(values):
    return [v / (1 << 20) for v in values]


def send(proc, word):
    try:
        proc.stdin.write(word + "\n")
        proc.stdin.flush()
    except BrokenPipeError:
        pass  # the worker has died; its result file and exit code say why


def run_cell(args, prompt, budget, quant, libs):
    """One engine process and its --runs generations: one record per run it attempted, appended
    to --output once the process has exited. True when every run was attempted and is ok."""
    runtime = RUNTIMES[args.backend]
    started = dt.datetime.now(dt.timezone.utc)
    slug = args.model_id.replace("/", "_").replace(".", "_")
    stem = f"{runtime}_{slug}_{args.model_dir.name}_{args.task}_ctx{args.context_tokens}_runs{args.runs}_{started:%Y%m%dT%H%M%S.%fZ}"
    out = args.logs
    log, result_path = out / f"{stem}.log", out / f"{stem}.worker.json"
    worker_args = ["--worker", "--worker-result", str(result_path), "--model-id", args.model_id,
                   "--model-dir", str(args.engine_dir), "--backend", args.backend, "--task", args.task,
                   "--context-tokens", str(args.context_tokens), "--telemetry", args.telemetry,
                   "--runs", str(args.runs), "--timeout", str(args.timeout)]
    cmd = [sys.executable, str(Path(__file__).resolve()), *worker_args]
    env = dict(os.environ, PYTHONUNBUFFERED="1", HF_HUB_OFFLINE="1")
    for key in ("ORT_DISABLE_TELEMETRY", "ORTGENAI_TELEMETRY_COMPARISON", "ORTGENAI_ORT_VERBOSE_LOGGING",
                "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "XAI_API_KEY", "OPENROUTER_API_KEY"):
        env.pop(key, None)
    if args.telemetry == "off":
        env["ORT_DISABLE_TELEMETRY"] = "1"
    else:
        env["ORTGENAI_TELEMETRY_COMPARISON"] = "1"
    if args.ort_verbose:
        env["ORTGENAI_ORT_VERBOSE_LOGGING"] = "1"
    spawn_host = host_snapshot()
    tdir_before = telemetry_dir_manifest(args.telemetry_dir)
    start = time.monotonic()
    runs = {}  # run k -> what the parent read around it
    with log.open("a") as f:
        f.write(f"{args.capture_purpose}\ncommand: {shlex.join(cmd)}\nengine env: ORT_DISABLE_TELEMETRY="
                f"{env.get('ORT_DISABLE_TELEMETRY', '(unset)')} ORTGENAI_ORT_VERBOSE_LOGGING="
                f"{env.get('ORTGENAI_ORT_VERBOSE_LOGGING', '(unset)')}\n")
        f.flush()
        proc = subprocess.Popen(cmd, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=f,
                                text=True, bufsize=1)
        sampler = Sampler(proc.pid)
        sampler.start()
        watch = LsofWatch(proc.pid, out / f"{stem}.lsof.txt") if args.lsof_watch else None
        if watch:
            watch.start()
        segment = start  # run 1's segment starts at the spawn (import and load are its), run k's at NEXT
        for line in proc.stdout:
            f.write(f"[worker stdout] {line}")
            f.flush()
            mark = re.search(r"\b(READY|DONE) (\d+)$", line.strip())
            if not mark:
                continue
            word, k = mark.group(1), int(mark.group(2))
            if word == "READY":  # run k's generator exists; the worker waits for GO
                r = runs.setdefault(k, {"segmentStart": segment})
                r["before"] = host_snapshot(proc.pid)
                r["gpuReady"] = gpu_time_ns(proc.pid)
                info = sampler.read()
                r["afterLoad"] = info.ri_phys_footprint if info else None
                sampler.begin()
                r["timestamp"] = dt.datetime.now(dt.timezone.utc)
                send(proc, "GO")
            elif k in runs:  # DONE k: run k's last token
                r = runs[k]
                r["footprints"] = sampler.end()
                r["lifetimeMax"] = sampler.lifetime_max
                r["gpuDone"] = gpu_time_ns(proc.pid)
                r["after"] = host_snapshot(proc.pid)
                r["elapsed"] = time.monotonic() - r["segmentStart"]
                if k < args.runs:
                    time.sleep(args.pause)
                    segment = time.monotonic()
                    send(proc, "NEXT")
                else:
                    send(proc, "EXIT")
        try:
            rc = proc.wait(timeout=60)
        except subprocess.TimeoutExpired:  # stdout closed, the process still there
            proc.kill()
            rc = proc.wait()
        sampler.stop.set()
        sampler.join(5)
        if watch:
            watch.stop.set()
            watch.join(10)
    process_elapsed = time.monotonic() - start
    tdir_after = telemetry_dir_manifest(args.telemetry_dir)
    exit_host = host_snapshot()
    data = json.loads(result_path.read_text()) if result_path.exists() else {"error": f"worker exit {rc}; no result"}
    reported = {d["run"]: d for d in data.get("runs", [])}
    # the runs the process attempted: run 1 whatever happened (the load is part of it), and every
    # run whose generator it created; the runs after the one that ended it are not attempted
    attempted = sorted(set(runs) | {1})
    diff = manifest_diff(tdir_before, tdir_after)
    telemetry_clean = not (diff["added"] or diff["removed"] or diff["modified"] or diff["dirCreated"])
    gpu_accel = (f"{data['registered']['name']} ({Path(data['registered']['library']).name}, onnxruntime-ep-webgpu "
                 f"{VERSIONS['onnxruntime-ep-webgpu']} plugin EP, registered with register_execution_provider_library; "
                 f"genai device_type {data.get('deviceType')})" if data.get("registered")
                 else "none registered (CPU EP)")
    genai_config_path = args.engine_dir / "genai_config.json"  # the file the engine read
    genai_config = json.loads(genai_config_path.read_text())
    records, texts = [], {}
    for k in attempted:
        r, d = runs.get(k, {}), reported.get(k)  # d None: run k did not finish
        before, after = r.get("before") or spawn_host, r.get("after") or exit_host
        n = d["generatedTokenCount"] if d else 0
        metrics = {"coldRun": k == 1, "firstEver": bool(args.first_ever and k == 1),
                   "contextTokensConfigured": args.context_tokens,
                   "initialThermalState": before["snapshot"]["thermal"], "finalThermalState": after["snapshot"]["thermal"]}
        if d and n > 0:
            prefill, first, decode = d["prefillSeconds"], d["firstStepSeconds"], d["decodeSeconds"]
            metrics.update(promptTokenCount=data["promptTokenCount"], generatedTokenCount=n,
                           promptTokensPerSecond=data["promptTokenCount"] / prefill,
                           firstTokenLatencyMS=(prefill + first) * 1000, prefillMS=prefill * 1000,
                           decodeSeconds=decode, totalGenerationTimeSeconds=d["generationWallSeconds"],
                           generatorSeconds=d["generatorSeconds"], stopReason=d["stopReason"],
                           cpuSecondsDuringGeneration=d["cpuSecondsDuringGeneration"])
            if k == 1:  # the model loads once, before run 1 (a warm run has no load, as in the yardstick)
                metrics["loadTimeSeconds"] = data["loadTimeSeconds"]
            if n > 1 and decode > 0:
                metrics["decodeTokensPerSecond"] = (n - 1) / decode
        if r.get("footprints") and d:  # no window without the run's last token
            mem = mib(r["footprints"])
            metrics.update(memoryPeakDuringDecodeMB=max(mem), memoryMedianMB=statistics.median(mem),
                           memorySampleCount=len(mem))
        if r.get("afterLoad") is not None:
            metrics["memoryAfterLoadMB"] = r["afterLoad"] / (1 << 20)
        lifetime = r.get("lifetimeMax") or sampler.lifetime_max  # the process's high-water by this run's end
        if lifetime is not None:
            metrics["memoryLifetimePeakMB"] = lifetime / (1 << 20)
        g0, g1 = r.get("gpuReady", {}), r.get("gpuDone", {})
        if "ns" in g0 and "ns" in g1:
            metrics.update(gpuMillisecondsDuringGeneration=(g1["ns"] - g0["ns"]) / 1e6, gpuClients=g1["clients"])
        text = d["text"] if d else ""
        verdict = text_verdict(args.task, text)
        text_ok = verdict is None or verdict["status"] == "PASS"
        witness_ok = (args.backend == "cpu" or (data.get("deviceType") == "WebGPU"
                      and any("libonnxruntime_providers_webgpu" in p for p in data.get("onnxruntimeImages") or [])
                      and (metrics.get("gpuMillisecondsDuringGeneration") or 0) > 0))
        numeric = [metrics.get(key) for key in ("promptTokensPerSecond", "decodeTokensPerSecond", "firstTokenLatencyMS",
                                                "memoryPeakDuringDecodeMB", "memoryMedianMB")]
        finite = all(isinstance(v, (int, float)) and math.isfinite(v) and v > 0 for v in numeric)
        # a run that finished stands on its own (as a yardstick record written before a later run
        # throws); the process-wide checks (sockets, the telemetry store) hold for all of them
        ok = (d is not None and finite and 0 < n <= budget and text_ok and witness_ok
              and sampler.socket_max == 0 and (args.telemetry == "on" or telemetry_clean))
        conditions = {
            "contextTokens": args.context_tokens, "contextBudget": args.context_tokens,
            "outputTokenBudget": budget, "maxOutputTokens": budget, "sampler": "greedy",
            "searchOptions": {"max_length": args.context_tokens, "do_sample": False,
                              "overrides": "genai_config search: max_length 40960, do_sample true (temperature 0.6, top_k 20, top_p 0.95)"},
            "pastPresentShareBuffer": genai_config["search"].get("past_present_share_buffer"),
            "chatMode": "single-turn, model chat_template.jinja default (Qwen3 thinking on)", "thinking": True,
            "telemetry": ("off: ORT_DISABLE_TELEMETRY=1 before init + disable_telemetry_events()" if args.telemetry == "off"
                          else "ON (comparison run: neither ORT_DISABLE_TELEMETRY nor disable_telemetry_events)"),
            "metricDefinitions": METRIC_DEFINITIONS, "threads": threads_condition(genai_config),
            "executionProvider": EPS[args.backend], "gpuAccelerator": gpu_accel,
            "providerOptions": genai_config["model"]["decoder"]["session_options"]["provider_options"],
            "ortLogging": "ORTGENAI_ORT_VERBOSE_LOGGING=1 (identity evidence; timing perturbed)" if args.ort_verbose else "engine default (ERROR)",
            "exitCode": rc, "elapsedSeconds": r.get("elapsed", process_elapsed - (r.get("segmentStart", start) - start)),
            "processElapsedSeconds": process_elapsed,
            "warm": k > 1, "regime": REGIME_COLD if k == 1 else REGIME_WARM.format(k=k, n=args.runs),
            "runIndex": k, "runsInProcess": args.runs, "pauseBetweenRunsSeconds": args.pause,
            "thermalInitial": before["snapshot"]["thermal"], "thermalFinal": after["snapshot"]["thermal"],
            "loadAverage": before["snapshot"]["loadAverage"], "capturePurpose": args.capture_purpose,
            "hostQuiet": bool(args.quiet_label) and args.quiet_label in before["snapshot"]["quietWindow"]}
        if args.campaign_note:
            conditions["campaignNote"] = args.campaign_note
        if args.overlay_obj is not None:
            conditions["genaiConfigOverlay"] = args.overlay_obj
        if verdict is not None:
            conditions["textCheck"] = verdict
        rec = {"schemaVersion": 1, "id": str(uuid.uuid4()), "timestamp": (r.get("timestamp") or started).isoformat(),
               "runtime": runtime,
               "engineVersion": f"onnxruntime-genai {VERSIONS['onnxruntime-genai']} + onnxruntime {VERSIONS['onnxruntime']}"
                                + (f" + onnxruntime-ep-webgpu {VERSIONS['onnxruntime-ep-webgpu']}" if args.backend == "webgpu" else ""),
               "engineArtifact": f"libonnxruntime-genai.dylib sha256:{libs['onnxruntime_genai/libonnxruntime-genai.dylib']['sha256']}",
               "model": {"id": args.model_id, **({"hfRevision": args.hf_revision} if args.hf_revision else {}),
                         "quantization": quant, "file": args.folder,
                         "sha256": args.model_sha256, "bytes": args.model_bytes, "files": args.model_files},
               "task": args.task, "device": before["device"], "conditions": conditions, "metrics": metrics,
               "harnessStamp": STAMP, "outputSample": text[:200], "status": "ok" if ok else "failed",
               "provenance": {"rawLog": rel(log), "decodedText": rel(out / f"{stem}_run{k}.decoded.txt"),
                              "workerResult": rel(result_path), "harness": "scripts/ortgenai_mac.py",
                              "campaign": rel(args.campaign_dir), "harnessCommand": shlex.join([sys.executable, *sys.argv]),
                              "command": shlex.join(cmd), "enginePid": proc.pid, "memoryBasis": MEMORY_BASIS,
                              "hostBefore": before, "hostAfter": after, "engineLibraries": libs,
                              "genai": data.get("genai"), "onnxruntimeImages": data.get("onnxruntimeImages"),
                              "gpuTime": {"basis": "IOKit AGXDeviceUserClient AppUsage accumulatedGPUTime of the engine pid "
                                                   "(ioreg -a -r -c AGXDeviceUserClient), read at READY <k> and at DONE <k>",
                                          "afterLoad": g0, "afterGeneration": g1},
                              "sockets": {"basis": "proc_pidinfo PROC_PIDLISTFDS every 100 ms from spawn to exit, "
                                                   "fds of type socket (the whole engine process, every run)",
                                          "max": sampler.socket_max, "first": sampler.socket_first},
                              "lsofWatch": rel(out / f"{stem}.lsof.txt") if watch else None,
                              "telemetryDir": {"path": str(args.telemetry_dir), "diff": diff,
                                               "before": tdir_before, "after": tdir_after},
                              "promptFile": f"prompts/text/{args.task}.txt",
                              "promptSha256": hashlib.sha256(prompt.encode()).hexdigest(),
                              "templatedPromptSha256": data.get("templatedPromptSha256"),
                              "templatedPromptTail": data.get("templatedPromptTail"),
                              "stepMilliseconds": [round(s * 1000, 3) for s in (d or {}).get("stepSeconds", [])],
                              "modelDir": str(args.model_dir),
                              "genaiConfigSha256": sha256(genai_config_path),
                              "recipe": "models/ortgenai-recipes.json (scripts/ortgenai_recipe.py, read from model.onnx)"}}
        if args.staging:
            rec["provenance"]["staging"] = args.staging
        if not ok:
            in_flight = None
            if d is None:
                in_flight = (data.get("error") if data.get("errorRun") in (0, k) else None) or (
                    f"the engine process ended before run {k} finished")
            rec["failureDetail"] = "; ".join(x for x in (
                in_flight, None if (d is not None or rc == 0) else f"exit {rc}",
                None if finite else "nonfinite or missing metric",
                None if text_ok else f"text check {verdict['flags']}",
                None if witness_ok else "WebGPU not witnessed (device_type / plugin image / GPU time)",
                None if sampler.socket_max == 0 else f"socket fds seen: {sampler.socket_max}",
                None if (args.telemetry == "on" or telemetry_clean) else f"telemetry dir changed: {diff}") if x)
        records.append(rec)
        texts[k] = text
    from jsonschema import Draft7Validator, FormatChecker
    validator = Draft7Validator(json.loads((REPO / "schema/result.v1.json").read_text()), format_checker=FormatChecker())
    for rec in records:
        validator.validate(rec)
    with args.output.open("a") as fh:  # one compact line per run (the runner counts lines with "task")
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False, allow_nan=False) + "\n")
    for rec in records:
        k, m = rec["conditions"]["runIndex"], rec["metrics"]
        (out / f"{stem}_run{k}.decoded.txt").write_text(texts[k] + "\n")
        print(f"{rec['status'].upper()} run {k}/{args.runs} {'cold' if k == 1 else 'warm'}: exit={rc} "
              f"prompt={m.get('promptTokenCount')} gen={m.get('generatedTokenCount', 0)} stop={m.get('stopReason')} "
              f"prefill={m.get('promptTokensPerSecond') or 0:.1f} tok/s ttft={m.get('firstTokenLatencyMS') or 0:.1f} ms "
              f"decode={m.get('decodeTokensPerSecond') or 0:.1f} tok/s peak={m.get('memoryPeakDuringDecodeMB') or 0:.0f} MiB "
              f"gpu={m.get('gpuMillisecondsDuringGeneration')} ms sockets={sampler.socket_max} "
              f"telemetry_dir_clean={telemetry_clean} "
              f"text={rec['conditions']['textCheck']['status'] if 'textCheck' in rec['conditions'] else 'gate (outputSample)'}"
              f" -> {args.output.name}", flush=True)
    all_ok = all(rec["status"] == "ok" for rec in records)
    if len(attempted) < args.runs:
        print(f"FAIL runs {len(attempted) + 1}..{args.runs} not attempted: the engine process (exit {rc}) "
              f"ended in run {attempted[-1]}", flush=True)
    elif rc != 0 and all_ok:
        print(f"FAIL the engine process exited {rc} after its last run", flush=True)
    return len(attempted) == args.runs and rc == 0 and all_ok


def rel(path):
    try:
        return str(Path(path).resolve().relative_to(REPO))
    except ValueError:
        return str(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model-id", required=True, help="HF repo id, e.g. onnx-community/Qwen3-0.6B-ONNX")
    ap.add_argument("--file", help="the GenAI folder's path inside the repo (cells file=), resolved through "
                                   "the HF cache at --revision; only that folder is downloaded")
    ap.add_argument("--revision", help="HF commit of the repo (cells revision=); required with --file")
    ap.add_argument("--model-dir", type=Path, help="a local GenAI folder instead of --file (an HF cache path "
                                                   "keeps its revision and folder)")
    ap.add_argument("--backend", choices=("cpu", "webgpu"), required=True)
    ap.add_argument("--task", choices=TASKS, default="short-chat")
    ap.add_argument("--runs", type=int, default=1,
                    help="generations in one engine process: run 1 cold, runs 2..N warm (the yardstick's --runs)")
    ap.add_argument("--context-tokens", type=int, default=2048, help="search max_length = the KV allocation")
    ap.add_argument("--output", type=Path, help="the cell's JSONL: one record per run is appended")
    ap.add_argument("--campaign-dir", type=Path,
                    help="campaign dir; the process's logs go to its ortgenai-logs/ (default: the --output file's dir)")
    ap.add_argument("--smoke", metavar="NOTE", help="a smoke capture: conditions.capturePurpose smoke and NOTE "
                                                    "as conditions.campaignNote (default: measurement, no note)")
    ap.add_argument("--pause", type=float, default=0.0,
                    help="seconds between two runs, the engine process idle (default 0: back to back, as the "
                         "yardstick's runs)")
    ap.add_argument("--timeout", type=int, default=900,
                    help="seconds the import and model load with run 1 may take, and each later run")
    ap.add_argument("--telemetry", choices=("off", "on"), default="off",
                    help="on = comparison evidence only: the engine keeps its default telemetry")
    ap.add_argument("--ort-verbose", action="store_true",
                    help="ORTGENAI_ORT_VERBOSE_LOGGING=1: EP registration and node placement in the log; timing perturbed")
    ap.add_argument("--lsof-watch", action="store_true", help="evidence: lsof -i of the engine process every 0.5 s")
    ap.add_argument("--telemetry-dir", type=Path, default=TELEMETRY_DIR)
    ap.add_argument("--first-ever", action="store_true",
                    help="run 1 is the first run of this (model, backend) on this device (engine/shader cache build)")
    ap.add_argument("--quiet-label", default="",
                    help="label of the quiet_hold window this run is inside; conditions.hostQuiet = the lock names it")
    ap.add_argument("--overlay", metavar="JSON",
                    help="a JSON object merged into the folder's genai_config.json in a staged copy (dicts merge, "
                         "other values replace), recorded as conditions.genaiConfigOverlay; lever runs only")
    ap.add_argument("--describe-quant", action="store_true",
                    help="print the folder's recipe facts (scripts/ortgenai_recipe.py describe) and exit")
    ap.add_argument("--dry-run", action="store_true", help="print the planned runs; no download, no engine")
    ap.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--worker-result", type=Path, help=argparse.SUPPRESS)
    args = ap.parse_args()
    if args.worker:
        args.model_dir = args.model_dir.resolve()
        return worker(args)
    if bool(args.file) == bool(args.model_dir):
        ap.error("name the folder with --file (+ --revision) or with --model-dir, one of the two")
    if args.file and not re.fullmatch(r"[0-9a-f]{40}", args.revision or ""):
        ap.error("--file needs --revision <the 40-hex HF commit> (cells revision=)")
    if args.runs < 1 or args.pause < 0 or args.context_tokens < 1:
        ap.error("runs and context-tokens must be positive, pause nonnegative")
    args.overlay_obj = None
    if args.overlay is not None:
        try:
            args.overlay_obj = json.loads(args.overlay)
        except json.JSONDecodeError as e:
            ap.error(f"--overlay is not JSON: {e}")
        if not isinstance(args.overlay_obj, dict) or not args.overlay_obj:
            ap.error("--overlay must be a non-empty JSON object")
    prompt, budget = task_input(args.task)
    if args.model_dir:
        args.model_dir = args.model_dir.resolve()
        cached_revision, args.folder = model_identity(args.model_dir)
        args.hf_revision = args.revision or cached_revision
    else:
        args.hf_revision, args.folder = args.revision, args.file.strip("/")
        args.model_dir = resolve_folder(args.model_id, args.folder, args.hf_revision, local_only=args.dry_run)
    if args.describe_quant:
        if args.model_dir is None:
            ap.error(f"{args.folder} is not in the HF cache")
        print(json.dumps(ortgenai_recipe.describe(str(args.model_dir)), indent=1))
        return 0
    args.capture_purpose = ("evidence only: telemetry ON comparison run, numbers discarded" if args.telemetry == "on"
                            else "evidence only: ORT verbose logging (EP identity), timing perturbed" if args.ort_verbose
                            else "smoke" if args.smoke is not None else "measurement")
    args.campaign_note = args.smoke or ""
    if args.dry_run:
        if args.model_dir is None:
            where = f"not in the HF cache yet; the first run downloads {args.folder} at {args.hf_revision[:12]}"
            quant = "looked up at the first run (models/ortgenai-recipes.json)"
        else:
            where = str(args.model_dir)
            entry = ortgenai_recipe.lookup(args.model_id, args.folder, sha256(args.model_dir / "model.onnx"))
            quant = entry["label"] if entry else "NOT REGISTERED, the run is refused: " + ortgenai_recipe.register_command(
                args.model_dir, args.model_id, args.folder, args.hf_revision)
        print(f"{RUNTIMES[args.backend]} {args.model_id} {args.folder}@{(args.hf_revision or '?')[:12]} ({where})")
        for index in range(1, args.runs + 1):
            regime = REGIME_COLD if index == 1 else REGIME_WARM.format(k=index, n=args.runs)
            step = ("engine process starts, model load, new generator" if index == 1
                    else f"pause {args.pause} s, new generator in the same process")
            print(f"  run {index}/{args.runs}: {regime}: {step}; task {args.task} budget {budget}; "
                  f"max_length {args.context_tokens}; greedy; telemetry {args.telemetry}; {args.capture_purpose}")
        print(f"  quantization: {quant}")
        if args.overlay_obj is not None:
            print(f"  overlay: {json.dumps(args.overlay_obj)}")
        reason = staging_reason(args.model_dir, args.overlay_obj) if args.model_dir is not None else None
        if reason:  # stage for real (clones, no engine), show what the engine would read, remove it
            stage, staging = stage_folder(args.model_dir, args.overlay_obj, reason)
            try:
                config = json.loads((stage / "genai_config.json").read_text())
                print(f"  staged copy ({reason}): {stage}")
                for name, info in staging["files"].items():
                    print(f"    {name}: {info['method']} <- {info['source']}")
                original = json.dumps(json.loads((args.model_dir / "genai_config.json").read_text()), indent=4)
                diff = list(difflib.unified_diff(original.splitlines(), json.dumps(config, indent=4).splitlines(),
                                                 "genai_config.json (folder)", "genai_config.json (staged)", lineterm=""))
                print("  genai_config.json diff (both re-serialized with indent 4):")
                print("\n".join(f"    {line}" for line in diff) if diff else "    (none)")
                providers = config["model"]["decoder"]["session_options"]["provider_options"]
                print(f"  engine reads: provider_options {json.dumps(providers)}; threads {threads_condition(config)}; "
                      f"past_present_share_buffer {config['search'].get('past_present_share_buffer')}")
            finally:
                shutil.rmtree(stage, ignore_errors=True)
                print(f"  staged copy removed: {not stage.exists()}")
        else:
            print("  engine reads the folder in place (no overlay, no external data behind links)")
        return 0
    for package, version in VERSIONS.items():
        observed = importlib.metadata.version(package)
        if observed != version:
            ap.error(f"expected {package} {version}, observed {observed}")
    providers = effective_config(args.model_dir, args.overlay_obj)["model"]["decoder"]["session_options"]["provider_options"]
    if (args.backend == "webgpu") != any("webgpu" in p for p in providers):
        ap.error(f"--backend {args.backend} does not match the provider_options the engine would read {providers} "
                 "(the folder's, or the --overlay's)")
    onnx_path = args.model_dir / "model.onnx"
    args.model_sha256 = sha256(onnx_path)
    entry = ortgenai_recipe.lookup(args.model_id, args.folder, args.model_sha256)
    if not entry:
        ap.error(f"{args.model_id} {args.folder} (model.onnx sha256 {args.model_sha256[:12]}) has no recipe label in "
                 "models/ortgenai-recipes.json (quant-label-rule) - register it: "
                 + ortgenai_recipe.register_command(args.model_dir, args.model_id, args.folder, args.hf_revision))
    quant = entry["label"]
    if args.output is None:
        ap.error("--output <cell.jsonl> is required")
    args.output = args.output.resolve()
    args.campaign_dir = (args.campaign_dir or args.output.parent).resolve()
    args.logs = args.campaign_dir / "ortgenai-logs"
    args.logs.mkdir(parents=True, exist_ok=True)
    args.model_files = ortgenai_recipe.folder_files(str(args.model_dir))
    # the weights the engine loads: model.onnx plus its external data file where the folder has one
    args.model_bytes = sum(args.model_files[n]["bytes"] for n in ("model.onnx", "model.onnx.data") if n in args.model_files)
    libs = engine_libraries()
    reason = staging_reason(args.model_dir, args.overlay_obj)
    stage, args.staging = stage_folder(args.model_dir, args.overlay_obj, reason) if reason else (None, None)
    args.engine_dir = stage or args.model_dir
    try:
        return 0 if run_cell(args, prompt, budget, quant, libs) else 1
    finally:
        if stage:
            shutil.rmtree(stage, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
