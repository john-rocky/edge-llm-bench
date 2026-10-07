#!/usr/bin/env python3
"""Mac ONNX Runtime GenAI cells: one fresh engine process per run, one schema-v1 JSON per run.

Prototype (2026-10-07, r1 smoke). Install onnxruntime-genai==0.17.1, onnxruntime==1.30.0
and onnxruntime-ep-webgpu==0.4.0 in a private venv and run this script with that venv's
python. The model is a published GenAI folder (genai_config.json + model.onnx + tokenizer)
passed as an absolute --model-dir; the WebGPU arm registers the plugin EP and uses the
folder whose genai_config names the webgpu provider.

Telemetry: the engine process gets ORT_DISABLE_TELEMETRY=1 in its environment before
onnxruntime_genai is imported, and calls disable_telemetry_events(). --telemetry on drops
both; it exists only for the telemetry comparison and its records are evidence, not
measurements.

Timing, the cut points of upstream benchmark/c model_benchmark:
  prefill  = wall clock of Generator.append_tokens(prompt) (prompt forward pass + logits)
  TTFT     = append_tokens + the first generate_next_token (greedy pick from the prefill logits)
  decode   = tokens 2..N / the summed wall clock of their generate_next_token calls
Generation stops at EOS (is_done) or the task's output budget; no min_length.
Memory: the parent samples the engine process's phys_footprint every 100 ms
(proc_pid_rusage RUSAGE_INFO_V4) from after the model load to the last token, MiB
(bytes / 2^20), the Apple BenchmarkRunner basis. GPU identity per run: the GPU time the
engine process accrued during generation (IOKit AGXDeviceUserClient AppUsage of its pid).
"""
import argparse
import ctypes
import datetime as dt
import hashlib
import importlib.metadata
import importlib.util
import json
import math
import os
from pathlib import Path
import plistlib
import re
import resource
import shlex
import signal
import statistics
import subprocess
import sys
import threading
import time
import traceback
import uuid

from cell_gate import degenerate

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "android" / "bench"))
from parsers import text_integrity  # noqa: E402  (the Android runner's lexical screen)

STAMP = "ortgenai-mac-v0-2026-10-07"
TASKS = ("short-chat", "long-context-1024-gen256")
VERSIONS = {"onnxruntime-genai": "0.17.1", "onnxruntime": "1.30.0", "onnxruntime-ep-webgpu": "0.4.0"}
RUNTIMES = {"cpu": "onnxruntime-genai-cpu", "webgpu": "onnxruntime-genai-webgpu"}
EPS = {"cpu": "CPUExecutionProvider", "webgpu": "WebGpuExecutionProvider"}
DEVICE_TYPES = {"cpu": "CPU", "webgpu": "WebGPU"}
TELEMETRY_DIR = Path.home() / "Library/Application Support/Microsoft/DeveloperTools/.onnxruntime"
QUIET_LOCK = Path(os.environ.get("QUIET_LOCK") or Path.home() / "code/coreai/_GPU_LOCK")
# Exact recipes read from model.onnx with --describe-quant (MatMulNBits / GatherBlockQuantized
# attributes, scale and KV dtypes) plus config.json and the Hub commit; never a bit count alone.
QUANT_LABELS = {
    ("onnx-community/Qwen3-0.6B-ONNX", "onnxruntime/cpu_and_mobile/cpu-int4-kld-block-128"):
        "int4 + int8 mixed MatMulNBits (92 int4 / 105 int8 of 197; per-layer int8 overrides as published), "
        "block 128, asymmetric uint8 zero points, fp32 scales, accuracy_level 4; int8 block-128 "
        "GatherBlockQuantized embedding; fp32 activations and KV (onnx-community "
        "cpu-int4-kld-block-128, Olive 0.11.0.dev0 + ORT GenAI model builder, PR #3 2026-04-20)",
    ("onnx-community/Qwen3-0.6B-ONNX", "onnxruntime/webgpu/webgpu-int4-kld-block-32"):
        "int4 + int8 mixed MatMulNBits (91 int4 / 106 int8 of 197; per-layer int8 overrides as published), "
        "block 32, asymmetric uint8 zero points, fp16 scales, accuracy_level 4; int8 block-32 "
        "GatherBlockQuantized embedding; fp16 activations and KV (onnx-community "
        "webgpu-int4-kld-block-32, Olive 0.11.0.dev0 + ORT GenAI model builder, PR #3 2026-04-20)",
}
METRIC_DEFINITIONS = (
    "prefill tok/s = promptTokenCount / wall clock of Generator.append_tokens(prompt); "
    "TTFT = append_tokens + the first generate_next_token (greedy pick from the prefill logits, no forward pass); "
    "decode tok/s = (generatedTokenCount - 1) / summed wall clock of generate_next_token calls 2..N "
    "(each = one forward pass + greedy pick); generatedTokenCount counts every picked token, a final EOS included; "
    "stop = EOS (is_done) or the output budget, no min_length; memory = phys_footprint of the engine process, "
    "100 ms samples from after model load and generator creation to the last token, high-water and median, "
    "MiB (bytes / 2^20); past_present_share_buffer true allocates the KV cache for max_length = contextTokens "
    "when the generator is created, so both memory numbers include it")
MEMORY_BASIS = ("phys_footprint of the engine process (proc_pid_rusage RUSAGE_INFO_V4 ri_phys_footprint) "
                "sampled by the parent every 100 ms from the worker's LOADED line (model, tokenizer and "
                "generator created) to its DONE line (last token); MiB = bytes / 2^20")


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


def host_snapshot():
    """disclose-hw-state: thermal, low power, load and the foreign processes above 20 % CPU."""
    thermal, low_power = process_info()
    loads = os.getloadavg()
    others = []
    for line in sh(["ps", "-Ao", "pcpu,pid,comm", "-r"]).splitlines()[1:16]:
        parts = line.split(None, 2)
        try:
            pc, pid = float(parts[0]), int(parts[1])
        except (ValueError, IndexError):
            continue
        if pc >= 20.0 and pid != os.getpid():
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


def describe_quant(model_dir):
    """The facts a quantization label is built from, read from model.onnx (needs the onnx package)."""
    import collections
    import onnx
    from onnx import helper
    m = onnx.load(str(model_dir / "model.onnx"), load_external_data=False)
    inits = {i.name: i for i in m.graph.initializer}
    combos = collections.Counter()
    for n in m.graph.node:
        if n.op_type in ("MatMulNBits", "GatherBlockQuantized"):
            a = {x.name: helper.get_attribute_value(x) for x in n.attribute}
            scale = inits.get(n.input[2]) if len(n.input) > 2 else None
            combos[(n.op_type, a.get("bits"), a.get("block_size"), a.get("accuracy_level"),
                    "zero points" if len(n.input) > 3 and n.input[3] else "no zero points",
                    onnx.TensorProto.DataType.Name(scale.data_type) if scale is not None else "?")] += 1
    kv = next((onnx.TensorProto.DataType.Name(i.type.tensor_type.elem_type) for i in m.graph.input
               if i.name.startswith("past_key_values")), None)
    return {"producer": m.producer_name, "opsets": {o.domain or "ai.onnx": o.version for o in m.opset_import},
            "metadata": {p.key: p.value for p in m.metadata_props}, "nodes": len(m.graph.node),
            "quantizedOps": [{"op": k[0], "bits": k[1], "blockSize": k[2], "accuracyLevel": k[3],
                              "zeroPoints": k[4], "scaleType": k[5], "count": c} for k, c in sorted(combos.items(), key=str)],
            "kvType": kv}


# ---------------------------------------------------------------- engine process
def loaded_images(pattern):
    dyld = ctypes.CDLL("/usr/lib/libSystem.B.dylib")
    dyld._dyld_image_count.restype = ctypes.c_uint32
    dyld._dyld_get_image_name.restype = ctypes.c_char_p
    dyld._dyld_get_image_name.argtypes = [ctypes.c_uint32]
    names = (dyld._dyld_get_image_name(i) for i in range(dyld._dyld_image_count()))
    return sorted({n.decode() for n in names if n and pattern in n.decode()})


def worker(args):
    """One engine lifetime. LOADED / DONE on stdout; the parent answers GO / EXIT on stdin, so its
    GPU-time reads and sampler start/stop stay outside the timed region."""
    signal.alarm(args.timeout)
    payload = {"pid": os.getpid(), "ok": False}
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
        params = og.GeneratorParams(model)
        params.set_search_options(max_length=args.context_tokens, do_sample=False)
        generator = og.Generator(model, params)
        payload["onnxruntimeImages"] = loaded_images("onnxruntime")
        eos = json.loads((args.model_dir / "genai_config.json").read_text())["model"]["eos_token_id"]
        eos = set(eos if isinstance(eos, list) else [eos])
        r0 = resource.getrusage(resource.RUSAGE_SELF)
        print("LOADED", flush=True)
        if sys.stdin.readline().strip() != "GO":
            raise RuntimeError("parent did not answer GO")
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
        print("DONE", flush=True)
        if sys.stdin.readline().strip() != "EXIT":
            raise RuntimeError("parent did not answer EXIT")
        hit_eos = bool(tokens) and tokens[-1] in eos
        payload.update(prefillSeconds=t1 - t0, firstStepSeconds=steps[0] if steps else None,
                       decodeSeconds=sum(steps[1:]), generationWallSeconds=t_end - t0,
                       stepSeconds=steps, tokens=tokens, generatedTokenCount=len(tokens), hitEos=hit_eos,
                       sequenceLength=int(generator.token_count()),
                       stopReason="eos" if hit_eos else ("length" if len(tokens) >= budget else "max_length"),
                       cpuSecondsDuringGeneration=(r1.ru_utime - r0.ru_utime) + (r1.ru_stime - r0.ru_stime),
                       text=tokenizer.decode(tokens[:-1] if hit_eos else tokens))
        payload["ok"] = True
    except Exception as e:
        payload["error"] = f"{type(e).__name__}: {e}"
        traceback.print_exc()
    args.worker_result.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n")
    return 0 if payload["ok"] else 1


# ---------------------------------------------------------------- parent side of one run
class Sampler(threading.Thread):
    """Every 100 ms from spawn to exit: socket fds of the engine process (whole life) and its
    phys_footprint (kept only inside the LOADED..DONE window)."""

    def __init__(self, pid):
        super().__init__(daemon=True)
        self.pid, self.window, self.stop = pid, False, threading.Event()
        self.footprints, self.socket_max, self.socket_first, self.lifetime_max = [], 0, None, None
        self.start_time = time.monotonic()

    def read(self):
        info = pid_rusage(self.pid)
        if info is None:
            return None
        if self.window:
            self.footprints.append(info.ri_phys_footprint)
        self.lifetime_max = info.ri_lifetime_max_phys_footprint
        return info

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


def text_verdict(text):
    verdict = text_integrity(text)
    flags = list(verdict["flags"])
    if degenerate(text[:200], 0.5):
        flags.append("text-degenerate-6gram")
    if "\ufffd" in text:
        flags.append("text-replacement-character")
    verdict.update(flags=flags, status="FAIL" if flags else "PASS",
                   method=("android/bench/parsers.text_integrity lexical screen + cell_gate.degenerate "
                           "(first 200 characters, 6-gram ratio < 0.5) + U+FFFD; full text retained for review"))
    return verdict


def mib(values):
    return [v / (1 << 20) for v in values]


def run_once(args, index, prompt, budget, quant, libs):
    runtime = RUNTIMES[args.backend]
    started = dt.datetime.now(dt.timezone.utc)
    slug = args.model_id.replace("/", "_").replace(".", "_")
    stem = f"{runtime}_{slug}_{args.model_dir.name}_{args.task}_ctx{args.context_tokens}_run{index}_{started:%Y%m%dT%H%M%S.%fZ}"
    out = args.out
    log, result_path = out / f"{stem}.log", out / f"{stem}.worker.json"
    worker_args = ["--worker", "--worker-result", str(result_path), "--model-id", args.model_id,
                   "--model-dir", str(args.model_dir), "--backend", args.backend, "--task", args.task,
                   "--context-tokens", str(args.context_tokens), "--telemetry", args.telemetry,
                   "--timeout", str(args.timeout), "--out", str(out)]
    cmd = [sys.executable, str(Path(__file__).resolve()), *worker_args]
    env = dict(os.environ, PYTHONUNBUFFERED="1", HF_HUB_OFFLINE="1")
    for key in ("ORT_DISABLE_TELEMETRY", "ORTGENAI_ORT_VERBOSE_LOGGING", "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
                "GEMINI_API_KEY", "XAI_API_KEY", "OPENROUTER_API_KEY"):
        env.pop(key, None)
    if args.telemetry == "off":
        env["ORT_DISABLE_TELEMETRY"] = "1"
    if args.ort_verbose:
        env["ORTGENAI_ORT_VERBOSE_LOGGING"] = "1"
    before = host_snapshot()
    tdir_before = telemetry_dir_manifest(args.telemetry_dir)
    start = time.monotonic()
    gpu = {}
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
        after_load, done_seen = None, False
        for line in proc.stdout:
            f.write(f"[worker stdout] {line}")
            f.flush()
            if line.strip() == "LOADED":
                gpu["afterLoad"] = gpu_time_ns(proc.pid)
                info = sampler.read()
                after_load = info.ri_phys_footprint if info else None
                sampler.window = True
                sampler.read()
                try:
                    proc.stdin.write("GO\n")
                    proc.stdin.flush()
                except BrokenPipeError:
                    pass  # the worker died after LOADED; its result file says why
            elif line.strip() == "DONE":
                sampler.read()
                sampler.window, done_seen = False, True
                gpu["afterGeneration"] = gpu_time_ns(proc.pid)
                try:
                    proc.stdin.write("EXIT\n")
                    proc.stdin.flush()
                except BrokenPipeError:
                    pass
        rc = proc.wait(timeout=args.timeout + 60)
        sampler.stop.set()
        sampler.join(5)
        if watch:
            watch.stop.set()
            watch.join(10)
    elapsed = time.monotonic() - start
    tdir_after = telemetry_dir_manifest(args.telemetry_dir)
    after = host_snapshot()
    data = json.loads(result_path.read_text()) if result_path.exists() else {"error": f"worker exit {rc}; no result"}
    n = data.get("generatedTokenCount") or 0
    metrics = {"coldRun": True, "firstEver": bool(args.first_ever and index == 1),
               "contextTokensConfigured": args.context_tokens,
               "initialThermalState": before["snapshot"]["thermal"], "finalThermalState": after["snapshot"]["thermal"]}
    if data.get("ok") and n > 0:
        prefill, first, decode = data["prefillSeconds"], data["firstStepSeconds"], data["decodeSeconds"]
        metrics.update(promptTokenCount=data["promptTokenCount"], generatedTokenCount=n,
                       promptTokensPerSecond=data["promptTokenCount"] / prefill,
                       firstTokenLatencyMS=(prefill + first) * 1000, prefillMS=prefill * 1000,
                       decodeSeconds=decode, totalGenerationTimeSeconds=data["generationWallSeconds"],
                       loadTimeSeconds=data["loadTimeSeconds"], stopReason=data["stopReason"],
                       cpuSecondsDuringGeneration=data["cpuSecondsDuringGeneration"])
        if n > 1 and decode > 0:
            metrics["decodeTokensPerSecond"] = (n - 1) / decode
    if sampler.footprints and done_seen:  # no window without a last token
        mem = mib(sampler.footprints)
        metrics.update(memoryPeakDuringDecodeMB=max(mem), memoryMedianMB=statistics.median(mem),
                       memorySampleCount=len(mem))
    if after_load is not None:
        metrics["memoryAfterLoadMB"] = after_load / (1 << 20)
    if sampler.lifetime_max is not None:
        metrics["memoryLifetimePeakMB"] = sampler.lifetime_max / (1 << 20)
    g0, g1 = gpu.get("afterLoad", {}), gpu.get("afterGeneration", {})
    if "ns" in g0 and "ns" in g1:
        metrics.update(gpuMillisecondsDuringGeneration=(g1["ns"] - g0["ns"]) / 1e6, gpuClients=g1["clients"])
    text = data.get("text", "")
    verdict = text_verdict(text)
    witness_ok = (args.backend == "cpu" or (data.get("deviceType") == "WebGPU"
                  and any("libonnxruntime_providers_webgpu" in p for p in data.get("onnxruntimeImages", []))
                  and (metrics.get("gpuMillisecondsDuringGeneration") or 0) > 0))
    numeric = [metrics.get(k) for k in ("promptTokensPerSecond", "decodeTokensPerSecond", "firstTokenLatencyMS",
                                        "memoryPeakDuringDecodeMB", "memoryMedianMB")]
    finite = all(isinstance(v, (int, float)) and math.isfinite(v) and v > 0 for v in numeric)
    diff = manifest_diff(tdir_before, tdir_after)
    telemetry_clean = not (diff["added"] or diff["removed"] or diff["modified"] or diff["dirCreated"])
    ok = (data.get("ok") and rc == 0 and finite and 0 < n <= budget and verdict["status"] == "PASS"
          and witness_ok and sampler.socket_max == 0 and (args.telemetry == "on" or telemetry_clean))
    gpu_accel = (f"{data['registered']['name']} ({Path(data['registered']['library']).name}, onnxruntime-ep-webgpu "
                 f"{VERSIONS['onnxruntime-ep-webgpu']} plugin EP, registered with register_execution_provider_library; "
                 f"genai device_type {data.get('deviceType')})" if data.get("registered")
                 else "none registered (CPU EP)")
    conditions = {
        "contextTokens": args.context_tokens, "contextBudget": args.context_tokens,
        "outputTokenBudget": budget, "maxOutputTokens": budget, "sampler": "greedy",
        "searchOptions": {"max_length": args.context_tokens, "do_sample": False,
                          "overrides": "genai_config search: max_length 40960, do_sample true (temperature 0.6, top_k 20, top_p 0.95)"},
        "pastPresentShareBuffer": json.loads((args.model_dir / "genai_config.json").read_text())["search"].get("past_present_share_buffer"),
        "chatMode": "single-turn, model chat_template.jinja default (Qwen3 thinking on)", "thinking": True,
        "telemetry": ("off: ORT_DISABLE_TELEMETRY=1 before init + disable_telemetry_events()" if args.telemetry == "off"
                      else "ON (comparison run: neither ORT_DISABLE_TELEMETRY nor disable_telemetry_events)"),
        "metricDefinitions": METRIC_DEFINITIONS, "threads": "engine default",
        "executionProvider": EPS[args.backend], "gpuAccelerator": gpu_accel,
        "providerOptions": json.loads((args.model_dir / "genai_config.json").read_text())["model"]["decoder"]["session_options"]["provider_options"],
        "ortLogging": "ORTGENAI_ORT_VERBOSE_LOGGING=1 (identity evidence; timing perturbed)" if args.ort_verbose else "engine default (ERROR)",
        "exitCode": rc, "elapsedSeconds": elapsed, "warm": False,
        "thermalInitial": before["snapshot"]["thermal"], "thermalFinal": after["snapshot"]["thermal"],
        "loadAverage": before["snapshot"]["loadAverage"], "capturePurpose": args.capture_purpose,
        "hostQuiet": bool(args.quiet_label) and args.quiet_label in before["snapshot"]["quietWindow"],
        "campaignNote": args.campaign_note, "textCheck": verdict}
    rec = {"schemaVersion": 1, "id": str(uuid.uuid4()), "timestamp": started.isoformat(), "runtime": runtime,
           "engineVersion": f"onnxruntime-genai {VERSIONS['onnxruntime-genai']} + onnxruntime {VERSIONS['onnxruntime']}"
                            + (f" + onnxruntime-ep-webgpu {VERSIONS['onnxruntime-ep-webgpu']}" if args.backend == "webgpu" else ""),
           "engineArtifact": f"libonnxruntime-genai.dylib sha256:{libs['onnxruntime_genai/libonnxruntime-genai.dylib']['sha256']}",
           "model": {"id": args.model_id, "hfRevision": args.hf_revision, "quantization": quant, "file": args.folder,
                     "sha256": args.model_sha256, "bytes": args.model_bytes},
           "task": args.task, "device": before["device"], "conditions": conditions, "metrics": metrics,
           "harnessStamp": STAMP, "outputSample": text[:200], "status": "ok" if ok else "failed",
           "provenance": {"rawLog": rel(log), "decodedText": rel(out / f"{stem}.decoded.txt"),
                          "workerResult": rel(result_path), "harness": "scripts/ortgenai_mac.py",
                          "campaign": rel(out), "harnessCommand": shlex.join([sys.executable, *sys.argv]),
                          "command": shlex.join(cmd), "memoryBasis": MEMORY_BASIS,
                          "hostBefore": before, "hostAfter": after, "engineLibraries": libs,
                          "genai": data.get("genai"), "onnxruntimeImages": data.get("onnxruntimeImages"),
                          "gpuTime": {"basis": "IOKit AGXDeviceUserClient AppUsage accumulatedGPUTime of the engine pid "
                                               "(ioreg -a -r -c AGXDeviceUserClient), read at LOADED and at DONE",
                                      "afterLoad": g0, "afterGeneration": g1},
                          "sockets": {"basis": "proc_pidinfo PROC_PIDLISTFDS every 100 ms from spawn to exit, "
                                               "fds of type socket", "max": sampler.socket_max, "first": sampler.socket_first},
                          "lsofWatch": rel(out / f"{stem}.lsof.txt") if watch else None,
                          "telemetryDir": {"path": str(args.telemetry_dir), "diff": diff,
                                           "before": tdir_before, "after": tdir_after},
                          "promptFile": f"prompts/text/{args.task}.txt",
                          "promptSha256": hashlib.sha256(prompt.encode()).hexdigest(),
                          "templatedPromptSha256": data.get("templatedPromptSha256"),
                          "templatedPromptTail": data.get("templatedPromptTail"),
                          "stepMilliseconds": [round(s * 1000, 3) for s in data.get("stepSeconds", [])],
                          "modelDir": str(args.model_dir)}}
    if data.get("error") or not ok:
        rec["failureDetail"] = "; ".join(x for x in (
            data.get("error"), None if rc == 0 else f"exit {rc}", None if finite else "nonfinite or missing metric",
            None if verdict["status"] == "PASS" else f"text check {verdict['flags']}",
            None if witness_ok else "WebGPU not witnessed (device_type / plugin image / GPU time)",
            None if sampler.socket_max == 0 else f"socket fds seen: {sampler.socket_max}",
            None if (args.telemetry == "on" or telemetry_clean) else f"telemetry dir changed: {diff}") if x)
    from jsonschema import Draft7Validator, FormatChecker
    Draft7Validator(json.loads((REPO / "schema/result.v1.json").read_text()), format_checker=FormatChecker()).validate(rec)
    (out / f"{stem}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1, allow_nan=False) + "\n")
    (out / f"{stem}.decoded.txt").write_text(text + "\n")
    print(f"{rec['status'].upper()} run {index}: exit={rc} prompt={metrics.get('promptTokenCount')} gen={n} "
          f"stop={metrics.get('stopReason')} prefill={metrics.get('promptTokensPerSecond') or 0:.1f} tok/s "
          f"ttft={metrics.get('firstTokenLatencyMS') or 0:.1f} ms decode={metrics.get('decodeTokensPerSecond') or 0:.1f} tok/s "
          f"peak={metrics.get('memoryPeakDuringDecodeMB') or 0:.0f} MiB gpu={metrics.get('gpuMillisecondsDuringGeneration')} ms "
          f"sockets={sampler.socket_max} telemetry_dir_clean={telemetry_clean} text={verdict['status']} -> {stem}.json",
          flush=True)
    return rec["status"] == "ok"


def rel(path):
    try:
        return str(Path(path).resolve().relative_to(REPO))
    except ValueError:
        return str(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model-id", required=True, help="HF repo id, e.g. onnx-community/Qwen3-0.6B-ONNX")
    ap.add_argument("--model-dir", type=Path, required=True, help="absolute path of the GenAI folder")
    ap.add_argument("--backend", choices=("cpu", "webgpu"), required=True)
    ap.add_argument("--task", choices=TASKS, default="short-chat")
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--context-tokens", type=int, default=2048, help="search max_length = the KV allocation")
    ap.add_argument("--out", type=Path, required=True, help="campaign dir (records, logs, decoded text)")
    ap.add_argument("--campaign-note", default="")
    ap.add_argument("--quantization", help="exact recipe; default = the QUANT_LABELS entry of (model id, folder)")
    ap.add_argument("--pause", type=float, default=5.0, help="seconds between runs")
    ap.add_argument("--timeout", type=int, default=900)
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
    ap.add_argument("--describe-quant", action="store_true", help="print the model.onnx quantization facts and exit")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--worker-result", type=Path, help=argparse.SUPPRESS)
    args = ap.parse_args()
    args.model_dir = args.model_dir.resolve()
    if args.worker:
        return worker(args)
    if args.describe_quant:
        print(json.dumps(describe_quant(args.model_dir), indent=1))
        return 0
    if args.runs < 1 or args.pause < 0 or args.context_tokens < 1:
        ap.error("runs and context-tokens must be positive, pause nonnegative")
    for package, version in VERSIONS.items():
        observed = importlib.metadata.version(package)
        if observed != version:
            ap.error(f"expected {package} {version}, observed {observed}")
    args.hf_revision, args.folder = model_identity(args.model_dir)
    quant = args.quantization or QUANT_LABELS.get((args.model_id, args.folder))
    if not quant:
        ap.error(f"no quantization label for ({args.model_id}, {args.folder}); read it with --describe-quant "
                 "and pass --quantization")
    if quant.lower() in ("int4", "4bit", "4-bit", "int8"):
        ap.error("quantization must name the recipe, not a bit width (quant-label-rule)")
    providers = json.loads((args.model_dir / "genai_config.json").read_text())["model"]["decoder"]["session_options"]["provider_options"]
    if (args.backend == "webgpu") != any("webgpu" in p for p in providers):
        ap.error(f"--backend {args.backend} does not match the folder's provider_options {providers}")
    args.capture_purpose = ("evidence only: telemetry ON comparison run, numbers discarded" if args.telemetry == "on"
                            else "evidence only: ORT verbose logging (EP identity), timing perturbed" if args.ort_verbose
                            else "smoke")
    prompt, budget = task_input(args.task)
    if args.dry_run:
        for index in range(1, args.runs + 1):
            print(f"run {index}/{args.runs}: fresh engine process; {RUNTIMES[args.backend]}; {args.folder}@{args.hf_revision}; "
                  f"task {args.task} budget {budget}; max_length {args.context_tokens}; greedy; telemetry {args.telemetry}; "
                  f"pause {args.pause if index > 1 else 0} s; quantization: {quant}")
        return 0
    args.out = args.out.resolve()
    args.out.mkdir(parents=True, exist_ok=True)
    onnx_path = args.model_dir / "model.onnx"
    args.model_sha256, args.model_bytes = sha256(onnx_path), onnx_path.stat().st_size
    libs = engine_libraries()
    ok = True
    for index in range(1, args.runs + 1):
        if index > 1:
            time.sleep(args.pause)
        ok = run_once(args, index, prompt, budget, quant, libs) and ok
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
