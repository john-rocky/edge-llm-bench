#!/usr/bin/env python3
"""Device-free end-to-end selftest of the Android lane (CI: android-driver-selftest).

Runs run_campaign.py -> run_cell.py -> parsers against a fake `adb` whose
device state lives in a temp dir, so CI and a fresh clone verify the whole
capture path — record shape, firstEver labelling via the on-device marker,
witness stamping, capture gate + quarantine + retry, the endurance
session path (streaming turn sidecar, host-derived decay/slope/degeneracy
verdicts, failed-runs-stay), the default text check of context-prompt
launches (text-check-rule), exclude-on= per device, a phone lost under a
running engine (the launch fails, never re-run), and the CPU frequency cap read
per run (cpu-cap-rule: the flag, the pre-launch wait, the summary column and
arm_row's pool), and the executorch arm (the runner of the model's family on a
staged own export: inputs pushed, the runner's stderr read apart from its stdout, its stats
recomputed, the record and its summary row; the Mac writer's record from a stored launch) — with no phone attached. The fake scripts ENGINE OUTPUT and
sysfs reads, never verdicts: the gate, the text screen, the cap rule and the
endurance derivations judge real records.

  python3 android/bench/selftest.py     # exit 0 = pass; temp dirs kept on failure

Captures go under the selftest's own temp dir (BENCH_RAW_ROOT), never into
results/raw — build_summary globs that tree unconditionally, so a leaked fake
row would pool into the real accumulation layer.
"""
import csv
import glob
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

FAKE_ADB = '''#!/usr/bin/env python3
import hashlib, json, os, re, shutil, sys

STATE = %(state)r
DEV = "/data/local/tmp/llmbench"
# the reply a two-iteration launch prints before each BenchmarkInfo: on task
# unless the test wrote STATE/off_task
ON_TASK = %(on_task)r
OFF_TASK = %(off_task)r
# a llama.cpp side build's llama-bench console on -dev HTP0 (the S26 smoke's, verbatim)
BENCH_HTP0 = %(bench_htp0)r
# a side build's device lines per --device, the forms of the S26 smoke's -lv 4 launches
SIDE_LINES = %(side_lines)r
# the LiteRT-LM NPU build's lines before its reply (the forms of its S26 runs)
NPU_LINES = %(npu_lines)r


def mp(p):
    return p.replace(DEV, os.path.join(STATE, "dev"))


# the Pixel 8a's cpufreq policies: name, cpuinfo_max_freq (kHz), related_cpus
POLICIES = [("policy0", 1704000, "0 1 2 3"), ("policy4", 2367000, "4 5 6 7"), ("policy8", 2914000, "8")]


def probe_caps():
    """{policy: scaling_max_freq kHz} the phone holds now: STATE/cpu_probe.json while the
    test keeps a cap there, else every policy at its hardware maximum."""
    p = os.path.join(STATE, "cpu_probe.json")
    return json.load(open(p)) if os.path.exists(p) else {}


def cpu_launch():
    """This launch's sampler script (STATE/cpu_runs.json, one entry per engine launch,
    consumed like schedule.json): {"ticks": [{policy: kHz}, ...], "allowed": [list, ...]};
    no entry = the probe's caps on every tick, Cpus_allowed_list 4-7 (taskset f0)."""
    p = os.path.join(STATE, "cpu_runs.json")
    q = json.load(open(p)) if os.path.exists(p) else []
    run = q.pop(0) if q else {}
    json.dump(q, open(p, "w"))
    return run


def side_build_lines(cmd):
    """A llama.cpp side build's device lines for this launch: STATE/side_lines.json (one
    list per launch, consumed like schedule.json) while the test scripts them, else the
    lines of the device the command names. A GPU launch writes a program into the build's
    OpenCL cache dir when it holds none, as the engine does on its first launch."""
    p = os.path.join(STATE, "side_lines.json")
    q = json.load(open(p)) if os.path.exists(p) else []
    lines = q.pop(0) if q else None
    if os.path.exists(p):
        json.dump(q, open(p, "w"))
    device = re.search(r"--device (\\S+)", cmd).group(1)
    cache = re.search(r"GGML_OPENCL_KERNEL_CACHE_DIR=(\\S+)", cmd)
    if device == "GPUOpenCL" and cache:
        d = mp(cache.group(1))
        os.makedirs(d, exist_ok=True)
        if not any(f.endswith(".clbin") for f in os.listdir(d)):
            open(os.path.join(d, "0123456789abcdef.clbin"), "w").close()
    return SIDE_LINES[device] if lines is None else lines


def npu_lines():
    """The LiteRT-LM NPU build's lines for this launch: STATE/npu_lines.json (one list per
    launch, consumed like schedule.json; null = the default) while the test scripts them,
    else NPU_LINES."""
    p = os.path.join(STATE, "npu_lines.json")
    q = json.load(open(p)) if os.path.exists(p) else []
    lines = q.pop(0) if q else None
    if os.path.exists(p):
        json.dump(q, open(p, "w"))
    return NPU_LINES if lines is None else lines


def side_chat_reply(cmd):
    """The chat tool's echo of the prompt (cli-ui.h: "> " and the first 500 bytes) and its
    reply, a -lv 4 log line in the middle of it as on the phone."""
    prompt = open(mp(re.search(r" -f (\\S+)", cmd).group(1))).read()
    shown = prompt if len(prompt) <= 500 else prompt[:500] + " ... (truncated)"
    reply = OFF_TASK if os.path.exists(os.path.join(STATE, "off_task")) else ON_TASK
    head, tail = reply[:60], reply[60:]
    return ["", "> " + shown, "", "[Start thinking]", "", head,
            "0.03.650.151 I slot print_timing: id  0 | task 0 |        eval time =    1737.24 ms /   128 tokens",
            tail, ""]


def et_engine(cmd):
    """An ExecuTorch runner launch (sh -c 'exec ./executorch-<tag>/<runner> ... 2>err'): the
    next STATE/et_launches.json entry's stdout to stdout and its stderr into the file the
    command sends the runner's stderr to, as on the phone. Every file the command names must
    be on the device, else the runner fails as it would there."""
    p = os.path.join(STATE, "et_launches.json")
    q = json.load(open(p)) if os.path.exists(p) else []
    launch = q.pop(0) if q else {}
    json.dump(q, open(p, "w"))
    err = re.search(r"2>(\\S+?)'", cmd).group(1)
    needed = [m.group(1) for m in re.finditer(r"--(?:model_path|tokenizer_path|prompt_file)=(\\S+)", cmd)]
    needed.append(DEV + "/" + re.search(r"exec \\./(\\S+)", cmd).group(1))
    missing = [n for n in needed if not os.path.exists(mp(n))]
    if missing or not launch:
        open(mp(err), "w").write("E 00:00:00.000001 executorch:fake] missing " + " ".join(missing) + "\\n")
        return 1
    sys.stdout.write(open(launch["stdout"]).read())
    open(mp(err), "w").write(open(launch["stderr"]).read())
    return 0


def engine(cmd):
    with open(os.path.join(STATE, "engine_cmds"), "a") as fh:
        fh.write(cmd.split(" >", 1)[0] + "\\n")
    sched = os.path.join(STATE, "schedule.json")
    q = json.load(open(sched))
    d = q.pop(0) if q else 20.0
    json.dump(q, open(sched, "w"))
    cpu = cpu_launch() if "CPUPOLICY" in cmd else None
    if cpu is not None:
        for name, hw, cpus in POLICIES:
            print("CPUPOLICY %%s %%d %%s" %% (name, hw, cpus))
    # the sampler's reads, only for the fields the runner's grep asks for
    # (status order: VmHWM before VmRSS); VmHWM rises 600000 -> 640000 kB
    for k, hwm in enumerate((600000, 610000, 640000)):
        if "VmHWM" in cmd:
            print("VmHWM:\\t  %%d kB" %% hwm)
        if "VmRSS" in cmd:
            print("VmRSS:\\t  520000 kB")
        if "Cpus_allowed_list" in cmd:
            allowed = (cpu or {}).get("allowed") or ["4-7"]
            print("Cpus_allowed_list:\\t" + allowed[min(k, len(allowed) - 1)])
        if cpu is not None:
            ticks = cpu.get("ticks") or [{}]
            tick = dict(probe_caps(), **ticks[min(k, len(ticks) - 1)])
            print("CPUMAX " + " ".join(str(tick.get(name, hw)) for name, hw, _ in POLICIES))
    print("===ENGINE_OUTPUT===")
    side = DEV + "/engines/" in cmd
    if side and "/bin/llama-bench " in cmd:
        sys.stdout.write(BENCH_HTP0)
    elif "./llama-cli" in cmd or (side and "/bin/llama-cli " in cmd):
        if side:
            for line in side_build_lines(cmd) + side_chat_reply(cmd):
                print(line)
        print("[ Prompt: 200.0 t/s | Generation: %%s t/s ]" %% d)
    elif side and "/litert_lm_advanced_main " in cmd and "--backend=npu" in cmd:
        # the LiteRT-LM NPU build with --benchmark on the real prompt, --async=false: its
        # lines, the profile-summary warnings a benchmark launch logs before the reply (with
        # their trace blocks), the reply in one piece, then BenchmarkInfo
        reply = OFF_TASK if os.path.exists(os.path.join(STATE, "off_task")) else ON_TASK
        for line in npu_lines():
            print(line)
        print("I0000 00:00:1787447197.907884   26280 litert_lm_lib.cc:868] Running single-turn conversation")
        for stage, line_no in (("prefill", 572), ("decode", 786)):
            print("W0000 00:00:1787447197.923067   26280 tasks.cc:%%d] Failed to get %%s profile summary: "
                  "UNIMPLEMENTED: GetProfileSummary not implemented for backend: LiteRT NPU Compiled Model"
                  %% (line_no, stage))
            print("=== Source Location Trace: ===")
            print("./runtime/executor/llm_executor_base.h:233")
            print("")
        print("[thought] " + reply[:70] + "[/thought]")
        print(reply[70:])
        print("BenchmarkInfo:")
        print("  Time to first token: 0.05 s")
        print("    Prefill Turn 1: Processed 18 tokens in 9.1ms duration.")
        print("      Prefill Speed: 1978.02 tokens/sec.")
        print("    Decode Turn 1: Processed 128 tokens in 1.2s duration.")
        print("      Decode Speed: %%s tokens/sec." %% d)
        print("INFO: [accelerator_registry.cc:43] DestroyAccelerator: ptr=0xb400007b8f206890, name=NpuAccelerator")
    elif "./litert_lm_advanced_main" in cmd and "--num_iterations=2" in cmd:
        ctx = re.search(r"--max_num_tokens=(\\d+)", cmd).group(1)
        print("max_tokens: " + ctx)
        reply = OFF_TASK if os.path.exists(os.path.join(STATE, "off_task")) else ON_TASK
        # the 1024 task's prompt is 1,339 tokens (fits ctx 2048 with the 256 budget)
        prompt = 1339 if "long-context-1024-gen256" in cmd else 1986
        for count, rate in ((256, d), (93, d + 0.25)):
            print("I0000 00:00:1.000000 1 litert_lm_lib.cc:868] Running single-turn conversation")
            print(reply)
            print("BenchmarkInfo:")
            print("Prefill Turn 1: Processed %%d tokens in 1s duration." %% prompt)
            print("Decode Turn 1: Processed %%d tokens" %% count)
            print("Time to first token: 1.2 s")
            print("Prefill Speed: %%d.0 tokens/sec" %% prompt)
            print("Decode Speed: %%s tokens/sec" %% rate)
    elif "exec ./executorch-" in cmd:
        print("EXIT_CODE=%%d" %% et_engine(cmd))
        return 0
    else:
        print("Prefill Turn 1: Processed 21 tokens in 100.00ms duration.")
        print("Decode Turn 1: Processed 128 tokens")
        print("Time to first token: 0.42 s")
        print("Prefill Speed: 210.0 tokens/sec")
        print("Decode Speed: %%s tokens/sec" %% d)
    print("EXIT_CODE=0")
    return 0


def endurance(cmd):
    # Scripted DRIVER OUTPUT (never verdicts): the host harness derives
    # decay/slope/degeneracy from these lines exactly as from a real driver.
    spec = json.load(open(os.path.join(STATE, "endurance_script.json")))
    print("ENDURANCE_LOAD " + json.dumps(spec.get("load", {"loadSeconds": 1.5})))
    for t in spec["turns"]:
        print("ENDURANCE_TURN " + json.dumps(t))
    if spec.get("session") is not None:
        print("ENDURANCE_SESSION " + json.dumps(spec["session"]))
    return spec.get("exit", 0)


def lost(flag):
    """The phone leaves the bus under this one command (STATE/<flag> set by the test,
    consumed here): adb ends with an error and no output, as when the Pixel 8a rebooted
    under a running engine (2026-10-07 15:58)."""
    p = os.path.join(STATE, flag)
    if not os.path.exists(p):
        return False
    os.remove(p)
    sys.stderr.write("adb: device offline\\n")
    return True


def shell(cmd):
    # "./" = actually running the driver; a bare mention (sha256sum for the
    # witness stamp) must fall through to the real handlers
    if "./litert_lm_endurance_main" in cmd:
        return endurance(cmd)
    if cmd.startswith("tail "):
        p = mp(cmd.split()[-1])
        if os.path.exists(p):
            sys.stdout.write(open(p).read()[-8192:])
        return 0
    if cmd.startswith("getprop"):
        print({"ro.product.model": "FakePhone",
               "ro.build.version.release": "16",
               "ro.build.version.security_patch": "2026-08-05",
               "ro.soc.model": "FakeSoC",
               "ro.product.device": "fake"}.get(cmd.split()[1], ""))
        return 0
    if "dumpsys thermalservice" in cmd:
        if lost("drop_probe"):
            return 1
        print("Thermal Status: 0")
        return 0
    if "dumpsys battery" in cmd:
        print("  level: 100\\n  status: 2\\n  USB powered: true\\n  temperature: 316")
        return 0
    if "dumpsys power" in cmd:
        # screen state; a campaign changes it by writing STATE/wakefulness
        p = os.path.join(STATE, "wakefulness")
        print("  mWakefulness=" + (open(p).read().strip() if os.path.exists(p) else "Awake"))
        return 0
    if cmd == "settings get global stay_on_while_plugged_in":
        print("0")
        return 0
    if "CPUFREQ" in cmd and "===ENGINE_OUTPUT===" not in cmd:
        # the runner's pre-launch cap probe: name, hardware maximum, cap, CPUs
        caps = probe_caps()
        for name, hw, cpus in POLICIES:
            print("CPUFREQ %%s %%d %%d %%s" %% (name, hw, caps.get(name, hw), cpus))
        return 0
    if "===ENGINE_OUTPUT===" in cmd:
        with open(os.path.join(STATE, "engine_calls"), "a") as fh:
            fh.write("engine shell\\n")
        if lost("drop_engine"):
            return 1
        return engine(cmd)
    if cmd.startswith("sha256sum"):
        # every device path named; a stand-in for a real engine file holds the sha256sum
        # the phone would print for it ("sha256=<hex>": the side build's pinned files)
        status = 0
        for arg in cmd.split()[1:]:
            if not arg.startswith(DEV):
                continue
            p = mp(arg)
            if not os.path.exists(p):
                print("sha256sum: " + arg + ": No such file or directory")
                status = 1
                continue
            data = open(p, "rb").read()
            digest = data[7:71].decode() if data.startswith(b"sha256=") else hashlib.sha256(data).hexdigest()
            print(digest + "  " + arg)
        return 0 if "|| true" in cmd else status
    if cmd.startswith("stat -c %%s"):
        p = mp(cmd.split()[-1])
        if not os.path.exists(p):
            print("stat: " + p + ": No such file or directory")
            return 1
        print(os.path.getsize(p))
        return 0
    if cmd.startswith("ls ") and "echo present" in cmd:
        # every `ls <path>` of the && chain must find something (a glob may name it)
        import glob as _g
        paths = [seg.split()[1] for seg in cmd.split("&&") if seg.strip().startswith("ls ")]
        print("present" if all(_g.glob(mp(p)) for p in paths) else "absent")
        return 0
    if cmd.startswith("mkdir -p") and "touch" in cmd:
        mk, touch = cmd.split("&&")
        os.makedirs(mp(mk.split()[-1]), exist_ok=True)
        open(mp(touch.split()[-1]), "w").close()
        return 0
    if cmd.startswith("mkdir"):
        os.makedirs(mp(cmd.split()[-1]), exist_ok=True)
        return 0
    if cmd.startswith("rm -f "):
        import glob as _g
        for pat in cmd.split()[2:]:
            for p in _g.glob(mp(pat)):
                os.remove(p)
        return 0
    if cmd.startswith("cat ") and "; rm -f " in cmd:
        # executorch: the runner's stderr file, read and removed after a launch
        p = mp(cmd.split()[1])
        if os.path.exists(p):
            sys.stdout.write(open(p).read())
            os.remove(p)
        return 0
    sys.stderr.write("fake-adb: unhandled shell: " + cmd + "\\n")
    return 1


def main(argv):
    if argv and argv[0] == "-s":
        argv = argv[2:]
    if not argv:
        return 0
    if argv[0] == "wait-for-device":
        return 0
    if argv[0] == "get-serialno":
        print("FAKESELF")
        return 0
    if argv[0] == "push":
        dst = mp(argv[2])
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(argv[1], dst)
        print("1 file pushed")
        return 0
    if argv[0] == "shell":
        return shell(" ".join(argv[1:]))
    if argv[0] == "exec-out":  # streaming path (endurance driver)
        return shell(" ".join(argv[1:]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
'''

# Scripted replies of the fake two-iteration engine (context-prompt cells): the
# runner's text check (parsers.text_integrity, on by default) passes the first
# and flags the second text-off-task-screen — the engine output is scripted, the
# verdict is the real screen's.
ON_TASK = ("Running on-device AI means the phone answers without a network: replies stay "
           "local, private data never leaves the handset, and the assistant keeps working "
           "offline on a plane or in a tunnel.")
OFF_TASK = ("Please share the document you want summarised and the questions you have about "
            "it, and I will answer each of them in order with short explanations.")

# A llama.cpp side build's consoles, the forms of the 2026-10-07 Galaxy S26 smoke of
# b11469-snapdragon (Qwen3 0.6B Q4_K_M; the launch logs are outside this repo, in the lane's
# round notes): llama-bench -o json on HTP0, verbatim from its first line to the JSON's
# end — the Hexagon registry's "FASTRPC_GET_DOMAINS[0]" line comes before the array — and
# the chat tool's device lines at -lv 4 per device, timestamp prefixes included.
BENCH_HTP0 = """ggml_opencl: selected platform: 'QUALCOMM Snapdragon(TM)'

ggml_opencl: device: 'QUALCOMM Adreno(TM) 840 (OpenCL 3.0 Adreno(TM) 840)'
ggml_opencl: default device: 'QUALCOMM Adreno(TM) 840 (OpenCL 3.0 Adreno(TM) 840)'
ggml-hex: Loading driver libcdsprpc.so
ggml-hex: FASTRPC_GET_DOMAINS[0]: type 1 id 1000 name 'nsp1000' status 1 instance-id 0
ggml-hex: using CDSP domain: instance-id 0 id 1000 name 'nsp1000'
ggml-hex: Hexagon backend (experimental) : allocating new registry : ndev 1
ggml-hex: Hexagon Arch version v81, DMA64 enabled
ggml-hex: device 0: HTP0 (phys=0, virt=0, domain=nsp1000:1000)
[
  {
    "build_commit": "ad2156533",
    "build_number": 11469,
    "cpu_info": "CPU",
    "gpu_info": "QUALCOMM Adreno(TM) 840, Hexagon",
    "backends": "OpenCL,HTP",
    "model_filename": "/data/local/tmp/llmbench/models/unsloth_Qwen3-0.6B-GGUF_Qwen3-0.6B-Q4_K_M.gguf",
    "model_type": "qwen3 0.6B Q4_K - Medium",
    "model_size": 390753280,
    "model_n_params": 596049920,
    "n_batch": 2048,
    "n_ubatch": 512,
    "n_threads": 4,
    "cpu_mask": "0x0",
    "cpu_strict": false,
    "poll": 50,
    "type_k": "f16",
    "type_v": "f16",
    "n_gpu_layers": 99,
    "n_cpu_moe": 0,
    "split_mode": "layer",
    "main_gpu": 0,
    "no_kv_offload": false,
    "flash_attn": -1,
    "devices": "HTP0",
    "tensor_split": "0.00",
    "tensor_buft_overrides": "none",
    "load_mode": "auto",
    "lazy_mode": "auto",
    "embeddings": false,
    "no_op_offload": 0,
    "no_host": false,
    "repack": true,
    "fit_target": 0,
    "fit_min_ctx": 0,
    "n_prompt": 1024,
    "n_gen": 0,
    "n_depth": 0,
    "test_time": "2026-10-07T13:22:48Z",
    "avg_ns": 244490000,
    "stddev_ns": 6713945,
    "avg_ts": 4190.935295,
    "stddev_ts": 119.484661,
    "samples_ns": [ 232482552, 247277500, 247561406, 247672552, 247455990 ],
    "samples_ts": [ 4404.63, 4141.1, 4136.35, 4134.49, 4138.11 ]
  },
  {
    "build_commit": "ad2156533",
    "build_number": 11469,
    "cpu_info": "CPU",
    "gpu_info": "QUALCOMM Adreno(TM) 840, Hexagon",
    "backends": "OpenCL,HTP",
    "model_filename": "/data/local/tmp/llmbench/models/unsloth_Qwen3-0.6B-GGUF_Qwen3-0.6B-Q4_K_M.gguf",
    "model_type": "qwen3 0.6B Q4_K - Medium",
    "model_size": 390753280,
    "model_n_params": 596049920,
    "n_batch": 2048,
    "n_ubatch": 512,
    "n_threads": 4,
    "cpu_mask": "0x0",
    "cpu_strict": false,
    "poll": 50,
    "type_k": "f16",
    "type_v": "f16",
    "n_gpu_layers": 99,
    "n_cpu_moe": 0,
    "split_mode": "layer",
    "main_gpu": 0,
    "no_kv_offload": false,
    "flash_attn": -1,
    "devices": "HTP0",
    "tensor_split": "0.00",
    "tensor_buft_overrides": "none",
    "load_mode": "auto",
    "lazy_mode": "auto",
    "embeddings": false,
    "no_op_offload": 0,
    "no_host": false,
    "repack": true,
    "fit_target": 0,
    "fit_min_ctx": 0,
    "n_prompt": 0,
    "n_gen": 256,
    "n_depth": 0,
    "test_time": "2026-10-07T13:22:49Z",
    "avg_ns": 3316229592,
    "stddev_ns": 15315119,
    "avg_ts": 77.197416,
    "stddev_ts": 0.355374,
    "samples_ns": [ 3312565207, 3306181666, 3320475363, 3340468957, 3301456769 ],
    "samples_ts": [ 77.2815, 77.4307, 77.0974, 76.6359, 77.5415 ]
  }
]
"""
SIDE_LINES = {
    "HTP0": [
        "0.00.029.081 I ggml_opencl: selected platform: 'QUALCOMM Snapdragon(TM)'",
        "0.00.030.004 I ",
        "ggml_opencl: device: 'QUALCOMM Adreno(TM) 840 (OpenCL 3.0 Adreno(TM) 840)'",
        "0.00.032.064 I ggml-hex: FASTRPC_GET_DOMAINS[0]: type 1 id 1000 name 'nsp1000' status 1 instance-id 0",
        "0.00.032.096 I ggml-hex: Hexagon Arch version v81, DMA64 enabled",
        "0.00.032.097 I ggml-hex: device 0: HTP0 (phys=0, virt=0, domain=nsp1000:1000)",
        "0.00.439.366 I llama_prepare_model_devices: using device HTP0 (Hexagon) (unknown id) - 0 MiB free",
        "0.00.573.759 I load_tensors: offloaded 29/29 layers to GPU",
        "0.00.573.762 I load_tensors:          CPU model buffer size =   121.71 MiB",
        "0.00.573.763 I load_tensors:         HTP0 model buffer size =   406.58 MiB",
    ],
    "GPUOpenCL": [
        "0.00.025.781 I ggml_opencl: selected platform: 'QUALCOMM Snapdragon(TM)'",
        "0.00.026.571 I ",
        "ggml_opencl: device: 'QUALCOMM Adreno(TM) 840 (OpenCL 3.0 Adreno(TM) 840)'",
        "0.00.028.445 I ggml-hex: Hexagon Arch version v81, DMA64 enabled",
        "0.00.444.410 I llama_prepare_model_devices: using device GPUOpenCL (QUALCOMM Adreno(TM) 840) (unknown id) - 4537 MiB free",
        "0.00.546.924 I ggml_opencl: kernel cache enabled at '/data/local/tmp/llmbench/engines/b11469-snapdragon/clcache'",
        "0.18.287.803 I load_tensors: offloaded 29/29 layers to GPU",
        "0.18.287.808 I load_tensors:          CPU model buffer size =   121.71 MiB",
        "0.18.287.810 I load_tensors:       OpenCL model buffer size =   372.75 MiB",
        "0.19.671.103 I ggml_opencl: OpenCL driver: OpenCL 3.0 QUALCOMM build: 0842.19.8 Compiler E031.50.19.18",
    ],
}
# The LiteRT-LM NPU build's console before its reply: the forms of the self-built
# litert_lm_advanced_main (LiteRT-LM main of 2026-08-21) on the Galaxy S26 — the settings echo
# of its runs with the hardware KV-cache update off (2026-09-08), the registry, dispatch and
# DispatchDelegate lines of its AOT benchmark runs (2026-08-23), both on Gemma 3 270M bundles
# (the lane's logs, outside this repo) — with this model and the runner's engines dir in the
# paths. LiteRT logs the NPU's registration failure for every environment after the first
# one: a healthy run has it.
NPU_ENG = "/data/local/tmp/llmbench/engines/main-20260821-selfbuilt"
NPU_LINES = [
    "WARNING: All log messages before absl::InitializeLog() is called are written to STDERR",
    "I0000 00:00:1787447197.028690   26280 litert_lm_lib.cc:499] Choose backend: npu",
    "I0000 00:00:1787447197.028842   26280 litert_lm_lib.cc:652] executor_settings: backend: NPU",
    "backend_config:",
    "enable_neon_for_npu_greedy_sampling: true",
    "use_hw_masking_for_npu: true",
    "use_hw_cache_update_for_npu: false",
    "enable_npu_debug_logging: false",
    "",
    "max_tokens: 0",
    "litert_dispatch_lib_dir: " + NPU_ENG,
    "model_assets: model_path: /data/local/tmp/llmbench/models/Qwen_Qwen3-0.6B_model_qualcomm_SM8850.litertlm",
    "INFO: [environment.cc:36] Creating LiteRT environment with options",
    "INFO: [accelerator_registry.cc:54] RegisterAccelerator: ptr=0xb400007b8f206890, name=NpuAccelerator",
    "INFO: [npu_registry.cc:30] NPU accelerator registered.",
    "WARNING: [gpu_registry.cc:131] GPU accelerator could not be loaded and registered.",
    "INFO: [accelerator_registry.cc:54] RegisterAccelerator: ptr=0xb400007b8f2064d0, name=CpuAccelerator",
    "INFO: [cpu_registry.cc:75] XNNPACK CPU accelerator registered.",
    "INFO: [environment.cc:36] Creating LiteRT environment with options",
    "WARNING: [npu_registry.cc:34] NPU accelerator could not be loaded and registered: "
    "kLiteRtStatusErrorInvalidArgument.",
    'I0000 00:00:1787447197.035488   26280 llm_litert_npu_compiled_model_executor.cc:1892] Detected NPU '
    'prefill size: 128 (signature "prefill_128").',
    "INFO: [litert_dispatch.cc:159] Loading shared library: " + NPU_ENG + "/libLiteRtDispatch_Qualcomm.so",
    "INFO: [common.h:160] ",
    "",
    "+------------------------------------------+",
    "|              ::qnn::Options              |",
    "+------------------------------------------+",
    "[GENERAL]",
    "  LogLevel                 : Off(0)",
    "  BackendType              : Htp(2)",
    "VERBOSE: Replacing 1 out of 1 node(s) with delegate (DispatchDelegate) node, yielding 1 partitions "
    "for subgraph 0 (prefill_128).",
    "INFO: [context_binary_info.cc:112] Found qnn graph: qnn_partition_0",
    "INFO: [litert_dispatch_device_context.cc:248] Creating new QNN context for bytecode 0x797af997b0 "
    "(size 282300416)",
    "VERBOSE: Replacing 1 out of 1 node(s) with delegate (DispatchDelegate) node, yielding 1 partitions "
    "for subgraph 1 (decode).",
    "INFO: [litert_dispatch_device_context.cc:243] Reusing cached QNN context for bytecode 0x797af997b0 "
    "(size 282300416)",
    "I0000 00:00:1787447197.907000   26280 litert_lm_lib.cc:856] Creating conversation",
]
# what the runner keeps of them: conditions.backendRegistered of a LiteRT-LM NPU launch
NPU_REGISTERED = [
    "Choose backend: npu", "executor_settings: backend: NPU", "use_hw_cache_update_for_npu: false",
    "litert_dispatch_lib_dir: " + NPU_ENG, "RegisterAccelerator: ptr=<addr>, name=NpuAccelerator",
    "NPU accelerator registered.", "Loading shared library: " + NPU_ENG + "/libLiteRtDispatch_Qualcomm.so",
    "BackendType : Htp(2)",
    "Replacing 1 out of 1 node(s) with delegate (DispatchDelegate) node, yielding 1 partitions for "
    "subgraph 0 (prefill_128).",
    "Creating new QNN context for bytecode <addr> (size 282300416)",
    "Replacing 1 out of 1 node(s) with delegate (DispatchDelegate) node, yielding 1 partitions for "
    "subgraph 1 (decode)."]
# The key layout of a CPU llama.cpp record (no backend=) as the runner wrote it at 3d5655c,
# before the side builds: top-level keys and one level below, in order — a legacy cell, and
# a round-mode launch. The side-build wiring must not move a key of the CPU arm.
CPU_LLAMA_KEYS = {
    "legacy": "schemaVersion id runtime engineVersion engineArtifact model.id model.quantization "
              "model.file model.sha256 task timestamp device.modelIdentifier device.systemName "
              "device.systemVersion device.securityPatch device.soc device.product device.batteryLevel "
              "device.batteryState conditions.sampler conditions.cpuAffinity conditions.cpusAllowedList "
              "conditions.cpuMaxFreqMHz conditions.contextTokens conditions.chatMode "
              "conditions.thermalRawStatus conditions.thermalRawStatusFinal conditions.screen "
              "conditions.screenSource conditions.stayOnWhilePluggedIn conditions.elapsedSeconds "
              "conditions.exitCode metrics.promptTokensPerSecond metrics.decodeTokensPerSecond "
              "metrics.coldRun metrics.harnessStamp metrics.initialThermalState metrics.finalThermalState "
              "metrics.memoryMedianResidentMB metrics.memoryPeakResidentMB provenance.rawLog "
              "provenance.harness provenance.rssBasis".split(),
    "round": "schemaVersion id runtime engineVersion engineArtifact model.id model.quantization "
             "model.file model.sha256 task timestamp device.modelIdentifier device.systemName "
             "device.systemVersion device.securityPatch device.soc device.product device.batteryLevel "
             "device.batteryState conditions.sampler conditions.cpuAffinity conditions.cpusAllowedList "
             "conditions.cpuMaxFreqMHz conditions.contextTokens conditions.chatMode "
             "conditions.thermalRawStatus conditions.thermalRawStatusFinal conditions.screen "
             "conditions.screenSource conditions.elapsedSeconds conditions.exitCode conditions.roundIndex "
             "conditions.launchIndex conditions.launchID conditions.elapsedScope "
             "conditions.stateAndMemoryScope conditions.batteryTemperatureInitialC "
             "conditions.batteryTemperatureFinalC conditions.batteryLevelFinal conditions.thermalGateTimedOut "
             "conditions.thermalGateTimeoutNonNominal conditions.initialThermalNonNominal "
             "conditions.outputTokenBudget conditions.engineCommand conditions.invalidDecodeCount "
             "conditions.protocolFlags conditions.iterationIndex conditions.regime "
             "metrics.promptTokensPerSecond metrics.decodeTokensPerSecond metrics.coldRun "
             "metrics.harnessStamp metrics.initialThermalState metrics.finalThermalState "
             "metrics.memoryMedianResidentMB metrics.memoryPeakResidentMB provenance.rawLog "
             "provenance.harness provenance.rssBasis".split(),
}


def key_layout(rec):
    """A record's keys, top level and one level below, in order ("conditions.screen")."""
    out = []
    for k, v in rec.items():
        out += [f"{k}.{sub}" for sub in v] if isinstance(v, dict) else [k]
    return out

_fails = []


def ok(cond, msg):
    print(("  ok  " if cond else "  FAIL ") + msg)
    if not cond:
        _fails.append(msg)


def run_campaign(env, cells_path):
    return subprocess.call(
        [sys.executable, os.path.join(ROOT, "android", "bench", "run_campaign.py"),
         cells_path], env=env)


def records(out_dir, prefix):
    files = sorted(f for f in glob.glob(os.path.join(out_dir, prefix + "*.json")))
    return [(f, json.load(open(f))) for f in files]


def main():
    tmp = tempfile.mkdtemp(prefix="android-lane-selftest-")
    state = os.path.join(tmp, "state")
    dev = os.path.join(state, "dev")
    bin_dir = os.path.join(tmp, "bin")
    raw_root = os.path.join(tmp, "raw")
    for d in (dev, bin_dir, raw_root):
        os.makedirs(d)

    adb = os.path.join(bin_dir, "adb")
    with open(adb, "w") as fh:
        fh.write(FAKE_ADB % {"state": state, "on_task": ON_TASK, "off_task": OFF_TASK,
                             "bench_htp0": BENCH_HTP0, "side_lines": SIDE_LINES, "npu_lines": NPU_LINES})
    os.chmod(adb, 0o755)

    # fake on-device engine binaries (sha deliberately unmatched in the pins
    # registry -> the witness must stamp "unknown", never a guessed tag)
    for name in ("litert_lm_main", "litert_lm_advanced_main", "litert_lm_endurance_main", "llama-cli"):
        with open(os.path.join(dev, name), "w") as fh:
            fh.write("fake " + name)

    litert_model = os.path.join(tmp, "fake_model.litertlm")
    gguf_model = os.path.join(tmp, "fake.gguf")
    for p in (litert_model, gguf_model):
        with open(p, "w") as fh:
            fh.write("weights of " + os.path.basename(p))

    env = dict(os.environ,
               PATH=bin_dir + os.pathsep + os.environ.get("PATH", ""),
               BENCH_ANDROID_SERIAL="FAKESELF", BENCH_RAW_ROOT=raw_root,
               COOLDOWN="0", THERMAL_WAIT="5", GATE_COOLDOWN="0", CPUCAP_WAIT="1",
               BENCH_TEST_LOCK_DIR=tmp)
    env.pop("ROUNDS", None)  # inherited round mode must not alter legacy fixtures
    env.pop("BENCH_ROUND_WAKEFULNESS", None)  # nor an inherited sitting-mode screen state
    env.pop("BENCH_TEXT_CHECK", None)  # the default (on for context-prompt cells) is under test

    def schedule(vals):
        json.dump(vals, open(os.path.join(state, "schedule.json"), "w"))

    # --- campaign A: anchor (litert, 2 runs) + payload (llama, 2 rounds) ----
    cells_a = os.path.join(tmp, "a.cells")
    with open(cells_a, "w") as fh:
        fh.write(f"android litert-lm fake/model short-chat anchor=1 runs=2 "
                 f"backend=gpu file={litert_model}\n"
                 f"android llama.cpp fake/gguf short-chat runs=2 file={gguf_model}\n")
    schedule([25.0, 24.5, 20.6, 20.1])
    env["CAMPAIGN"] = "selftest-a"
    print("--- campaign A (clean capture, firstEver detection)")
    rc = run_campaign(env, cells_a)
    ok(rc == 0, f"campaign A exits 0 (got {rc})")

    out_a = os.path.join(raw_root, "selftest-a", "app-path-android")
    lit = records(out_a, "litert-lm-gpu_")
    lla = records(out_a, "llama.cpp_")
    ok(len(lit) == 2, f"2 litert records (got {len(lit)})")
    ok(len(lla) == 2, f"2 llama records (got {len(lla)})")
    if len(lit) == 2:
        r1, r2 = lit[0][1], lit[1][1]
        ok(r1["metrics"].get("firstEver") is True, "litert run 1 labelled firstEver")
        ok("firstEver" not in r2["metrics"], "litert run 2 not labelled")
        ok(r1["runtime"] == "litert-lm-gpu", "backend is part of arm identity")
        ok(str(r1["engineVersion"]).startswith("unknown"),
           "unmatched binary sha stamps 'unknown', never a guessed tag")
        want = hashlib.sha256(open(litert_model, "rb").read()).hexdigest()
        ok(r1["model"]["sha256"] == want, "model sha256 is the pushed artifact's")
        ok(r1["metrics"]["decodeTokensPerSecond"] == 25.0, "decode parsed from engine output")
        ok(os.path.exists(os.path.join(out_a, r1["provenance"]["rawLog"])),
           "raw console log stored next to the record (stored-report-rule)")
    # VmHWM is read on every launch, not only under BENCH_STRICT_SMOKE (unset here)
    ok(len(lit + lla) == 4 and all(
        r["metrics"].get("memoryMedianResidentMB") == 520000 / 1024
        and r["metrics"].get("memoryPeakResidentMB") == 640000 / 1024
        and r["metrics"]["memoryPeakResidentMB"] >= r["metrics"]["memoryMedianResidentMB"]
        and "VmHWM" in r["provenance"].get("rssBasis", "") for _, r in lit + lla),
       "memoryPeakResidentMB = largest VmHWM read / 1024 >= the VmRSS median, rssBasis recorded")
    ok(len(lit + lla) == 4 and all(
        r["conditions"].get("screen") == "on-usb" and r["conditions"].get("screenSource") == "measured"
        and r["conditions"].get("stayOnWhilePluggedIn") == "0" for _, r in lit + lla),
       "screen read before every launch: Awake -> on-usb, screenSource measured, Stay awake setting beside it")
    if len(lla) == 2:
        ok(all("firstEver" not in r["metrics"] for _, r in lla),
           "llama.cpp never labelled firstEver (no persistent compile cache)")
        ok(lla[0][1]["metrics"]["decodeTokensPerSecond"] == 20.6, "llama bracket summary parsed")
    marker = glob.glob(os.path.join(dev, "markers", "*.gpu.cachebuilt"))
    ok(len(marker) == 1, "on-device cache marker written after first clean run")
    ok(not os.path.exists(os.path.join(out_a, "FLAGGED.txt")), "clean capture not flagged")

    # --- campaign B: same model again (marker persists) + collapsed round ---
    cells_b = os.path.join(tmp, "b.cells")
    with open(cells_b, "w") as fh:
        fh.write(f"android litert-lm fake/model short-chat runs=2 "
                 f"backend=gpu file={litert_model}\n")
    # rounds 1-2 produce a contended-device signature (5.0 beside 25.0 ->
    # COLLAPSE); the block retry produces a clean pair
    schedule([25.0, 5.0, 24.0, 24.8])
    env["CAMPAIGN"] = "selftest-b"
    print("--- campaign B (COLLAPSE -> quarantine -> retry once)")
    rc = run_campaign(env, cells_b)
    ok(rc == 0, f"campaign B exits 0 (got {rc})")

    out_b = os.path.join(raw_root, "selftest-b", "app-path-android")
    kept = records(out_b, "litert-lm-gpu_")
    quarantined = glob.glob(os.path.join(out_b, "*.json.attempt1"))
    ok(len(kept) == 2, f"retry pair stands as the capture (got {len(kept)})")
    ok(len(quarantined) == 2, f"flagged pair quarantined as .attempt1 (got {len(quarantined)})")
    if len(kept) == 2:
        ok([r["metrics"]["decodeTokensPerSecond"] for _, r in kept] == [24.0, 24.8],
           "kept records are the retry, not the flagged pair")
        ok(all("firstEver" not in r["metrics"] for _, r in kept),
           "marker survives across invocations — no re-label on a warm cache")
    prov = os.path.join(out_b, "session_provenance.txt")
    ok(os.path.exists(prov) and "gate retry" in open(prov).read(),
       "block re-run disclosed in session_provenance.txt")
    ok(not os.path.exists(os.path.join(out_b, "FLAGGED.txt")),
       "clean retry leaves no FLAGGED.txt")

    # --- campaign B2: the bundle was deleted from the device (storage
    # rotation between split sessions) while its marker survived; the
    # re-push must drop the marker so run 1 is labelled firstEver again
    # (Pixel 8a 2026-09-07: markers outlived 7 of their 10 bundles)
    for f in glob.glob(os.path.join(dev, "models", "*fake_model.litertlm*")):
        os.remove(f)
    schedule([25.2, 24.9])
    env["CAMPAIGN"] = "selftest-b2"
    print("--- campaign B2 (bundle deleted on device, marker stale -> re-push relabels firstEver)")
    rc = run_campaign(env, cells_b)
    ok(rc == 0, f"campaign B2 exits 0 (got {rc})")
    out_b2 = os.path.join(raw_root, "selftest-b2", "app-path-android")
    again = records(out_b2, "litert-lm-gpu_")
    ok(len(again) == 2, f"2 records after the re-push (got {len(again)})")
    if len(again) == 2:
        ok(again[0][1]["metrics"].get("firstEver") is True,
           "run 1 after a re-push is labelled firstEver (cache rebuilt, marker invalidated)")
        ok("firstEver" not in again[1][1]["metrics"], "run 2 after the re-push not labelled")

    # --- campaign B3: a collapse the slowest/median test cannot see, then a
    # uniformly slow retry (Pixel 8a 2026-09-08/09: 4.9 then 1.6 / 1.4 in one
    # capture; the block re-run 1.3 / 0.9 / 1.3 after 5.2 / 5.3 / 2.5) ------
    cells_b3 = os.path.join(tmp, "b3.cells")
    with open(cells_b3, "w") as fh:
        fh.write(f"android litert-lm fake/model short-chat runs=3 "
                 f"backend=gpu file={litert_model}\n")
    # rounds: one fast run beside two slow (median 5.0 under half of 25.0 ->
    # COLLAPSE 20); the block retry is uniformly slow (5.1 / 5.0 / 5.2 -> every
    # within-capture test passes, LEVEL 20 of the quarantined 25.0)
    schedule([25.0, 5.0, 5.0, 5.1, 5.0, 5.2])
    env["CAMPAIGN"] = "selftest-b3"
    print("--- campaign B3 (median collapsed beside one fast run -> COLLAPSE; uniformly slow retry -> LEVEL, kept + flagged)")
    rc = run_campaign(env, cells_b3)
    ok(rc == 0, f"campaign B3 exits 0 (got {rc})")
    out_b3 = os.path.join(raw_root, "selftest-b3", "app-path-android")
    kept3 = records(out_b3, "litert-lm-gpu_")
    quarantined3 = glob.glob(os.path.join(out_b3, "*.json.attempt1"))
    ok(len(kept3) == 3, f"retry triple stands as the capture (got {len(kept3)})")
    ok(len(quarantined3) == 3, f"flagged triple quarantined as .attempt1 (got {len(quarantined3)})")
    if len(kept3) == 3:
        ok([r["metrics"]["decodeTokensPerSecond"] for _, r in kept3] == [5.1, 5.0, 5.2],
           "kept records are the retry, not the flagged triple")
    flagged3 = os.path.join(out_b3, "FLAGGED.txt")
    txt3 = open(flagged3).read() if os.path.exists(flagged3) else ""
    ok("first='COLLAPSE 20'" in txt3,
       f"first capture judged COLLAPSE 20 (median 5.0 under half the fastest 25.0): {txt3.strip()!r}")
    ok("retry='LEVEL 20'" in txt3,
       "retry judged LEVEL 20 (median 5.1 of the quarantined un-collapsed 25.0), kept with the flag")

    # --- campaign C: endurance session, completed --------------------------
    # Scripted driver output; the HOST derives the verdicts (decay windows,
    # resident slope, degeneracy counts, medians) — this pins that math and
    # the streaming sidecar path with no phone and no 30-minute wait.
    def turn(i, t, rate, rollover=False, degenerate=False):
        d = {"turn": i, "promptIndex": (i - 1) % 12, "startedAtSeconds": t,
             "rollover": rollover, "ttftMS": 500.0, "wallSeconds": 5.0,
             "chunkCount": 200, "prefillTokens": 30,
             "prefillTokensPerSecond": 60.0, "decodeTokens": 256,
             "decodeTokensPerSecond": rate,
             "decodeTokensPerSecondWallClock": rate * 0.9,
             "kvTokensAfterTurn": 100 * i, "residentAfterTurnMB": 1000.0 + i,
             "stopReason": "length", "degenerate": degenerate,
             "outputHead": "fake output"}
        if rollover:
            d["rolloverReason"] = "budget"
        return d

    spec_c = {
        "load": {"loadSeconds": 1.5},
        # first 300 s window: 20 tok/s; last window: 10 tok/s -> decay 50%;
        # resident 1001..1006 over turns 1..6 -> slope exactly 1.0 MB/turn
        "turns": [turn(1, 0, 20.0), turn(2, 10, 20.0), turn(3, 20, 20.0),
                  turn(4, 650, 10.0, rollover=True),
                  turn(5, 660, 10.0, degenerate=True), turn(6, 700, 10.0)],
        "session": {"status": "completed", "turnsCompleted": 6,
                    "elapsedSeconds": 705.0, "loadSeconds": 1.5,
                    "plannedMinutes": 30, "contextTokens": 1024,
                    "turnCap": 256, "residentFinalMB": 1006.0,
                    "residentPeakMB": 1010.0},
        "exit": 0,
    }
    json.dump(spec_c, open(os.path.join(state, "endurance_script.json"), "w"))
    cells_c = os.path.join(tmp, "c.cells")
    with open(cells_c, "w") as fh:
        fh.write(f"android litert-lm fake/model endurance-chat-30m runs=1 "
                 f"backend=gpu context-tokens=1024 file={litert_model}\n")
    env["CAMPAIGN"] = "selftest-c"
    with open(os.path.join(state, "wakefulness"), "w") as fh:
        fh.write("Dozing")  # screen off: recorded, not refused
    print("--- campaign C (endurance session: sidecar + derived verdicts)")
    rc = run_campaign(env, cells_c)
    ok(rc == 0, f"campaign C exits 0 (got {rc})")

    out_c = os.path.join(raw_root, "selftest-c", "app-path-android")
    erecs = records(out_c, "litert-lm-gpu_fake_model_endurance-chat-30m")
    ok(len(erecs) == 1, f"1 endurance record (got {len(erecs)})")
    if erecs:
        _, r = erecs[0]
        e = r.get("endurance", {})
        ok(e.get("status") == "completed", "endurance.status completed")
        ok(e.get("decodeDecayPercent") == 50.0,
           f"decay derived from window medians (got {e.get('decodeDecayPercent')})")
        ok(abs(e.get("memorySlopeMBPerTurn", 0) - 1.0) < 1e-9,
           f"resident slope 1.0 MB/turn (got {e.get('memorySlopeMBPerTurn')})")
        ok(e.get("memorySlopeBasis") == "resident-vmrss",
           "slope basis disclosed as resident (no fabricated phys_footprint)")
        ok(e.get("conversationRollovers") == 1, "rollover counted")
        ok(e.get("degenerateTurnCount") == 1 and e.get("firstDegenerateTurn") == 5,
           "degeneracy flags lifted from the turn series")
        ok(r["metrics"]["decodeTokensPerSecond"] == 15.0,
           "session decode = median of per-turn engine rates")
        ok(r["metrics"].get("memoryMedianResidentMB") == 1003.5,
           "memoryMedianResidentMB = median of per-turn VmRSS")
        ok("firstEver" not in r["metrics"],
           "marker from campaign A covers endurance too (shared engine cache)")
        ok(str(r["engineVersion"]).startswith("unknown"),
           "endurance binary witness: unmatched sha stamps 'unknown'")
        ok(r["conditions"]["sampler"].startswith("topK40/topP0.9/temp0.7"),
           "driver-set protocol sampler recorded")
        ok(r["conditions"].get("screen") == "off-usb (mWakefulness=Dozing)"
           and r["conditions"].get("screenSource") == "measured",
           f"endurance: a dozing phone is stamped off-usb (got {r['conditions'].get('screen')!r})")
        sidecar = os.path.join(out_c, e.get("turnsSidecar", ""))
        ok(os.path.exists(sidecar), "turns sidecar stored beside the record")
        if os.path.exists(sidecar):
            lines = [json.loads(ln) for ln in open(sidecar) if ln.strip()]
            ok(len(lines) == 6, f"sidecar has all 6 turns (got {len(lines)})")
            ok(all(t.get("thermalState") == "nominal" for t in lines),
               "host stamps thermal state onto every turn line")
        ok(os.path.exists(os.path.join(out_c, r["provenance"]["rawLog"])),
           "endurance raw console log stored (stored-report-rule)")
    ok(not os.path.exists(os.path.join(out_c, "FLAGGED.txt")),
       "clean endurance capture not flagged")

    # --- campaign D: endurance crash mid-session (failed-runs-stay) --------
    spec_d = {
        "turns": [turn(1, 0, 22.0), turn(2, 10, 21.0)],
        "session": {"status": "crash", "turnsCompleted": 2,
                    "elapsedSeconds": 15.0, "loadSeconds": 1.5,
                    "plannedMinutes": 30, "contextTokens": 1024,
                    "turnCap": 256,
                    "failureDetail": "INTERNAL: The new rendered template "
                                     "string does not start with the previous"},
        "exit": 1,
    }
    json.dump(spec_d, open(os.path.join(state, "endurance_script.json"), "w"))
    env["CAMPAIGN"] = "selftest-d"
    print("--- campaign D (endurance crash keeps record + partial series)")
    rc = run_campaign(env, cells_c)
    ok(rc == 0, f"campaign D exits 0 (got {rc})")
    out_d = os.path.join(raw_root, "selftest-d", "app-path-android")
    drecs = records(out_d, "litert-lm-gpu_fake_model_endurance-chat-30m")
    ok(len(drecs) == 1, f"crash session still writes its record (got {len(drecs)})")
    if drecs:
        _, r = drecs[0]
        ok(r["endurance"].get("status") == "crash"
           and "rendered template" in r["endurance"].get("failureDetail", ""),
           "crash status + failure detail on the record")
        sidecar = os.path.join(out_d, r["endurance"].get("turnsSidecar", ""))
        partial = ([json.loads(ln) for ln in open(sidecar) if ln.strip()]
                   if os.path.exists(sidecar) else [])
        ok(len(partial) == 2, f"partial series kept: 2 turns on disk (got {len(partial)})")
    fails_txt = os.path.join(out_d, "FAILURES.txt")
    ok(os.path.exists(fails_txt) and "endurance-chat-30m" in open(fails_txt).read(),
       "failed session logged to FAILURES.txt")
    ok(not glob.glob(os.path.join(out_d, "*.json.attempt1")),
       "a crash session is never quarantine-retried (failed-runs-stay)")

    # --- opt-in long-context round mode, same real driver / fake transport ---
    cells_round = os.path.join(tmp, "round.cells")
    with open(cells_round, "w") as fh:
        fh.write(f"android llama.cpp fake/gguf short-chat anchor=1 file={gguf_model}\n")
        for ctx in (2304, 4096, 8192):
            fh.write(f"android litert-lm fake/model long-context-2048-gen256 backend=gpu "
                     f"context-tokens={ctx} file={litert_model}\n")
    # Wide spread would trigger a legacy retry; round mode must keep the
    # original rounds intact and leave admission to the session reviewer.
    schedule([100.0, 25.0, 25.0, 25.0, 5.0, 5.0, 5.0, 100.0])
    # sitting mode sets BENCH_ROUND_WAKEFULNESS from its per-round dumpsys read
    # (it also pins the engine sha, which the fake binaries cannot match); the
    # fake phone reads Awake again, so the env value must be the one stamped
    os.remove(os.path.join(state, "wakefulness"))
    env.update(CAMPAIGN="selftest-round", ROUNDS="2", BENCH_ROUND_WAKEFULNESS="Dozing")
    print("--- round campaign (2 iterations, reversal, anchor, gate off)")
    rc = run_campaign(env, cells_round)
    ok(rc == 0, f"round campaign exits 0 (got {rc})")
    out_round = os.path.join(raw_root, "selftest-round", "app-path-android")
    pairs = records(out_round, "litert-lm-gpu_")
    controls = records(out_round, "llama.cpp_")
    ok(len(pairs) == 12 and len(controls) == 2, "12 iteration records and 2 cold-process anchors")
    ok(all(r["conditions"]["regime"] == "cold-process" for _, r in controls), "anchor regime stays cold-process")
    grouped = {}
    for _, r in pairs:
        grouped.setdefault(r["conditions"]["launchID"], []).append(r)
    ok(len(grouped) == 6, "6 engine launches produced 12 records")
    for rows in grouped.values():
        rows.sort(key=lambda r: r["conditions"]["iterationIndex"])
        ok([r["metrics"]["generatedTokenCount"] for r in rows] == [256, 93], "per-iteration counts remain separate")
        ok([r["conditions"]["regime"] for r in rows] == ["cold", "warm"], "cold/warm labels per launch")
        ok(all(r["conditions"]["batteryTemperatureInitialC"] == 31.6 for r in rows), "battery temperature is Celsius")
        ok(all(r["metrics"].get("memoryPeakResidentMB") == 640000 / 1024 for r in rows),
           "both iteration records carry the launch's VmHWM peak")
    with open(os.path.join(out_round, "launch_order.jsonl")) as fh:
        order = [json.loads(line) for line in fh]
    ok([d["cell"] for d in order[4:]] == [d["cell"] for d in order[:4]][::-1], "full order reversed, including anchor")
    ok(not glob.glob(os.path.join(out_round, "*.json.attempt1")), "round mode never block-retries wide spread")
    ok(len(pairs + controls) == 14 and all(
        r["conditions"].get("screen") == "Dozing" and r["conditions"].get("screenSource") == "env"
        for _, r in pairs + controls),
       "sitting-mode BENCH_ROUND_WAKEFULNESS wins over the per-launch read (screenSource env)")
    # text check on by default for context-prompt cells (no BENCH_TEXT_CHECK in env)
    ok(len(pairs) == 12 and all(
        r["conditions"].get("textCheck", {}).get("status") == "PASS"
        and open(os.path.join(out_round, r["provenance"]["decodedText"])).read() == ON_TASK
        for _, r in pairs),
       "context-prompt records carry textCheck PASS and their decoded text by default")
    ok(len(controls) == 2 and not any("textCheck" in r["conditions"] for _, r in controls),
       "a llama.cpp launch is not text-checked (no context-prompt path)")
    env.pop("ROUNDS")
    env.pop("BENCH_ROUND_WAKEFULNESS")

    # --- campaign E: the weekly job's shape for a 1024 cell (context-tokens=,
    # no ROUNDS, no BENCH_TEXT_CHECK) with off-task replies: text-check-rule —
    # records, texts and log stay (failed-runs-stay), flagged FAIL; the launch is
    # listed in FAILURES.txt; the gate never re-runs it (a re-run reproduces it)
    cells_e = os.path.join(tmp, "e.cells")
    with open(cells_e, "w") as fh:
        fh.write(f"android litert-lm fake/model long-context-1024-gen256 runs=2 backend=gpu "
                 f"context-tokens=2048 file={litert_model}\n")
    open(os.path.join(state, "off_task"), "w").close()
    schedule([25.0, 25.5])
    env["CAMPAIGN"] = "selftest-e"
    print("--- campaign E (weekly-path 1024 cell, off-task text -> textCheck FAIL, kept, not retried)")
    rc = run_campaign(env, cells_e)
    os.remove(os.path.join(state, "off_task"))
    ok(rc == 0, f"campaign E exits 0 (got {rc})")
    out_e = os.path.join(raw_root, "selftest-e", "app-path-android")
    erecs_e = records(out_e, "litert-lm-gpu_fake_model_long-context-1024-gen256")
    ok(len(erecs_e) == 4, f"2 launches x 2 iteration records kept (got {len(erecs_e)})")
    ok(len(erecs_e) == 4 and all(
        r["conditions"].get("textCheck", {}).get("status") == "FAIL"
        and r["conditions"]["textCheck"]["flags"] == ["text-off-task-screen"]
        and r["conditions"].get("protocolFlags") == ["text-off-task-screen"]
        and r["metrics"].get("decodeTokensPerSecond")
        and open(os.path.join(out_e, r["provenance"]["decodedText"])).read() == OFF_TASK
        for _, r in erecs_e),
       "off-task replies: textCheck FAIL text-off-task-screen (the only flag), rate and text kept")
    fails_e = os.path.join(out_e, "FAILURES.txt")
    ok(os.path.exists(fails_e) and open(fails_e).read().count("long-context-1024-gen256") == 2,
       "both text-failed launches listed in FAILURES.txt")
    ok(not glob.glob(os.path.join(out_e, "*.json.attempt1")),
       "a text-failed capture is never quarantine-retried")

    # --- campaign X: exclude-on=<schedule key>:<reason> skips a row on the device
    # that key names and runs it on every other one (the Pixel 8a's 4B-class rows,
    # 2026-10-07). The serials are the registry's own (ops/dashboard-v1/schedule.json);
    # the fake adb answers whatever serial is set, and the lock goes to the temp dir
    # (BENCH_LOCK_DIR), never to the real /tmp lock of a phone in use.
    registry = json.load(open(os.path.join(ROOT, "ops", "dashboard-v1", "schedule.json")))["devices"]
    cells_x = os.path.join(tmp, "x.cells")
    with open(cells_x, "w") as fh:
        fh.write(f"android llama.cpp fake/gguf short-chat runs=1 file={gguf_model}\n"
                 f"android litert-lm fake/model short-chat runs=1 backend=gpu file={litert_model} "
                 "exclude-on=pixel8a:selftest-does-not-fit\n")
    for key, skips in (("pixel8a", True), ("s26", False)):
        env_x = dict(env, BENCH_ANDROID_SERIAL=registry[key]["serial"], BENCH_LOCK_DIR=tmp,
                     CAMPAIGN=f"selftest-x-{key}")
        env_x.pop("BENCH_TEST_LOCK_DIR")
        schedule([21.0, 22.0])
        print(f"--- campaign X on the {key} serial (exclude-on=pixel8a: "
              f"{'skipped here' if skips else 'runs here'})")
        rc = run_campaign(env_x, cells_x)
        ok(rc == 0, f"campaign X ({key}) exits 0 (got {rc})")
        out_x = os.path.join(raw_root, f"selftest-x-{key}", "app-path-android")
        skip_txt = os.path.join(out_x, "SKIPPED.txt")
        skip_txt = open(skip_txt).read() if os.path.exists(skip_txt) else ""
        lit_x, lla_x = records(out_x, "litert-lm-gpu_"), records(out_x, "llama.cpp_")
        ok(len(lla_x) == 1, f"{key}: the row without exclude-on runs (got {len(lla_x)} records)")
        if skips:
            ok(not lit_x and skip_txt.strip() == "CELL_SKIP litert-lm-gpu fake/model short-chat "
                                                   "exclude-on=pixel8a reason=selftest-does-not-fit",
               f"{key}: the exclude-on row is skipped, SKIPPED.txt names its key and reason: {skip_txt.strip()!r}")
        else:
            ok(len(lit_x) == 1 and not skip_txt,
               f"{key}: the exclude-on row runs on a device it does not name "
               f"(got {len(lit_x)} records, SKIPPED.txt {skip_txt.strip()!r})")

    # --- campaign F: the phone drops off the bus under a running engine. The engine
    # shell is never re-run (2026-10-07: a reboot mid-launch had the shell replayed on
    # the rebooted Pixel 8a, and the replay's record read as one run): that launch fails
    # with no record and is listed in FAILURES.txt, the next launch runs. A probe that
    # loses the phone is still retried, with one line in the campaign log.
    cells_f = os.path.join(tmp, "f.cells")
    with open(cells_f, "w") as fh:
        fh.write(f"android llama.cpp fake/gguf short-chat runs=2 file={gguf_model}\n")
    calls = os.path.join(state, "engine_calls")
    if os.path.exists(calls):
        os.remove(calls)
    for flag in ("drop_probe", "drop_engine"):
        open(os.path.join(state, flag), "w").close()
    schedule([20.0, 20.5])
    env["CAMPAIGN"] = "selftest-f"
    print("--- campaign F (device lost under the first engine shell and the first probe)")
    p = subprocess.run([sys.executable, os.path.join(ROOT, "android", "bench", "run_campaign.py"), cells_f],
                       env=env, capture_output=True, text=True)
    print(p.stdout + p.stderr)
    out_f = os.path.join(raw_root, "selftest-f", "app-path-android")
    lla_f = records(out_f, "llama.cpp_")
    n_calls = len(open(calls).read().splitlines()) if os.path.exists(calls) else 0
    fails_f = os.path.join(out_f, "FAILURES.txt")
    fails_f = open(fails_f).read() if os.path.exists(fails_f) else ""
    retried = [ln for ln in (p.stdout + p.stderr).splitlines() if ln.startswith("adb retry after device loss: ")]
    ok(p.returncode == 0, f"campaign F exits 0 (got {p.returncode})")
    ok(n_calls == 2 and len(lla_f) == 1 and lla_f[0][1]["metrics"]["decodeTokensPerSecond"] == 20.0,
       f"the lost engine shell is not re-run: 2 engine shells for 2 launches (got {n_calls}), "
       f"1 record, the second launch's (got {[r['metrics'].get('decodeTokensPerSecond') for _, r in lla_f]})")
    ok(fails_f.strip() == "llama.cpp fake/gguf short-chat rc=1",
       f"the lost launch is listed in FAILURES.txt: {fails_f.strip()!r}")
    ok(len(retried) == 1 and "dumpsys thermalservice" in retried[0] and "ENGINE_OUTPUT" not in retried[0],
       f"the lost probe is retried, one log line naming it, none for the engine shell: {retried}")
    for flag in ("drop_probe", "drop_engine"):
        if os.path.exists(os.path.join(state, flag)):
            os.remove(os.path.join(state, flag))

    # --- campaign G: no CPU frequency cap (cpu-cap-rule). Every policy's
    # scaling_max_freq stays at its cpuinfo_max_freq through the run: no flag, and
    # the record carries each policy's lowest read beside its hardware maximum.
    cells_g = os.path.join(tmp, "g.cells")
    with open(cells_g, "w") as fh:
        fh.write(f"android llama.cpp fake/gguf short-chat runs=2 file={gguf_model}\n")
    schedule([20.0, 20.4])
    env["CAMPAIGN"] = "selftest-g"
    print("--- campaign G (no CPU cap: no flag, the caps recorded)")
    rc = run_campaign(env, cells_g)
    ok(rc == 0, f"campaign G exits 0 (got {rc})")
    out_g = os.path.join(raw_root, "selftest-g", "app-path-android")
    lla_g = records(out_g, "llama.cpp_")
    uncapped = {"policy0": {"min": 1704, "hw": 1704, "cpus": "0-3"},
                "policy4": {"min": 2367, "hw": 2367, "cpus": "4-7"},
                "policy8": {"min": 2914, "hw": 2914, "cpus": "8"}}
    ok(len(lla_g) == 2 and all(r["conditions"].get("cpuMaxFreqMHz") == uncapped
                               and "protocolFlags" not in r["conditions"] for _, r in lla_g),
       f"uncapped runs: cpuMaxFreqMHz = every policy's min at its hw maximum, no protocolFlags "
       f"(got {[(r['conditions'].get('cpuMaxFreqMHz'), r['conditions'].get('protocolFlags')) for _, r in lla_g]})")
    ok(len(lla_g) == 2 and all(r["conditions"].get("cpusAllowedList") == "4-7"
                               and r["conditions"].get("cpuAffinity") == "taskset f0" for _, r in lla_g),
       f"cpusAllowedList = the engine's Cpus_allowed_list read during the run, beside the launch mask "
       f"(got {[r['conditions'].get('cpusAllowedList') for _, r in lla_g]})")
    ok(not os.path.exists(os.path.join(out_g, "THERMAL_GATE.txt")), "no cap line in THERMAL_GATE.txt")

    # --- campaign H: the charging Pixel 8a of 2026-10-07 (policy4 = the A715 cores the
    # llama.cpp arm runs on, 2367 -> 1418 MHz 20-30 s into a run, thermal status 0).
    # Launch 2 is capped on policy4: flagged cpu-capped, its record and rate kept, the
    # campaign not failed; launch 3 is capped on policy0 only, cores the engine was not
    # allowed on: no flag. Then build_summary and arm_row: the capped run is a row
    # (cpu_capped true) outside the pool. H2: a launch that starts capped waits
    # CPUCAP_WAIT s, runs anyway and carries cpu-capped-at-start beside cpu-capped.
    sum_root = os.path.join(tmp, "sumroot")
    cells_h = os.path.join(tmp, "h.cells")
    with open(cells_h, "w") as fh:
        fh.write(f"android llama.cpp fake/gguf short-chat runs=3 file={gguf_model}\n")
    schedule([20.0, 15.0, 19.5])
    json.dump([{}, {"ticks": [{}, {"policy4": 1418000}, {"policy4": 1572000}]},
               {"ticks": [{}, {"policy0": 1425000}, {}]}], open(os.path.join(state, "cpu_runs.json"), "w"))
    env_h = dict(env, CAMPAIGN="selftest-h", BENCH_RAW_ROOT=os.path.join(sum_root, "results", "raw"))
    print("--- campaign H (policy4 capped in run 2, policy0 in run 3 -> one cpu-capped run, out of arm_row's pool)")
    rc = run_campaign(env_h, cells_h)
    ok(rc == 0, f"campaign H exits 0: a capped run is not a failed run (got {rc})")
    out_h = os.path.join(sum_root, "results", "raw", "selftest-h", "app-path-android")
    lla_h = records(out_h, "llama.cpp_")
    flags_h = [r["conditions"].get("protocolFlags") for _, r in lla_h]
    ok(flags_h == [None, ["cpu-capped"], None],
       f"only the run capped on the engine's cores is flagged cpu-capped (got {flags_h})")
    ok(len(lla_h) == 3
       and lla_h[1][1]["conditions"].get("cpuMaxFreqMHz", {}).get("policy4") == {"min": 1418, "hw": 2367, "cpus": "4-7"}
       and lla_h[2][1]["conditions"].get("cpuMaxFreqMHz", {}).get("policy0") == {"min": 1425, "hw": 1704, "cpus": "0-3"}
       and lla_h[1][1]["metrics"]["decodeTokensPerSecond"] == 15.0,
       "the capped run keeps its record and rate; each run records its policies' lowest cap")
    gate_h = os.path.join(out_h, "THERMAL_GATE.txt")
    gate_h = open(gate_h).read().splitlines() if os.path.exists(gate_h) else []
    ok(len(gate_h) == 1 and gate_h[0].startswith("cpu-capped llama.cpp_fake_gguf_short-chat_")
       and gate_h[0].endswith("policy4 min 1418/2367 MHz (cpus 4-7)")
       and not os.path.exists(os.path.join(out_h, "FAILURES.txt")),
       f"one THERMAL_GATE.txt line for the capped run, nothing in FAILURES.txt: {gate_h}")
    with open(os.path.join(state, "cpu_probe.json"), "w") as fh:
        json.dump({"policy4": 2130000}, fh)
    cells_h2 = os.path.join(tmp, "h2.cells")
    with open(cells_h2, "w") as fh:
        fh.write(f"android llama.cpp fake/gguf short-chat runs=1 file={gguf_model}\n")
    schedule([4.6])
    env_h2 = dict(env_h, CAMPAIGN="selftest-h2")
    print("--- campaign H2 (the cap holds through CPUCAP_WAIT=1 s: run anyway, cpu-capped-at-start)")
    rc = run_campaign(env_h2, cells_h2)
    os.remove(os.path.join(state, "cpu_probe.json"))
    ok(rc == 0, f"campaign H2 exits 0 (got {rc})")
    out_h2 = os.path.join(sum_root, "results", "raw", "selftest-h2", "app-path-android")
    lla_h2 = records(out_h2, "llama.cpp_")
    gate_h2 = os.path.join(out_h2, "THERMAL_GATE.txt")
    gate_h2 = open(gate_h2).read() if os.path.exists(gate_h2) else ""
    ok(len(lla_h2) == 1 and all(r["conditions"].get("protocolFlags") == ["cpu-capped", "cpu-capped-at-start"]
                                for _, r in lla_h2)
       and "cpu cap gate timeout after 1s" in gate_h2 and "ran anyway: policy4 2130/2367 MHz" in gate_h2,
       f"a launch that starts capped waits CPUCAP_WAIT, runs, carries both flags: "
       f"{[r['conditions'].get('protocolFlags') for _, r in lla_h2]} {gate_h2.splitlines()[:1]}")
    # H3: LiteRT-LM widens its own affinity from the launch mask to 4-8 (the X3 core)
    # mid-launch on the Tensor G3: cpusAllowedList is the last read, and a cap on policy8,
    # outside the llama.cpp arm's mask, flags this run
    cells_h3 = os.path.join(tmp, "h3.cells")
    with open(cells_h3, "w") as fh:
        fh.write(f"android litert-lm fake/model short-chat runs=1 backend=gpu file={litert_model}\n")
    schedule([14.8])
    json.dump([{"allowed": ["4-7", "4-8", "4-8"], "ticks": [{}, {}, {"policy8": 2000000}]}],
              open(os.path.join(state, "cpu_runs.json"), "w"))
    env_h3 = dict(env_h, CAMPAIGN="selftest-h3")
    print("--- campaign H3 (LiteRT-LM allowed 4-7 -> 4-8, policy8 capped -> cpu-capped)")
    rc = run_campaign(env_h3, cells_h3)
    ok(rc == 0, f"campaign H3 exits 0 (got {rc})")
    lit_h3 = records(os.path.join(sum_root, "results", "raw", "selftest-h3", "app-path-android"), "litert-lm-gpu_")
    got_h3 = [(r["conditions"].get("cpusAllowedList"), r["conditions"].get("protocolFlags"),
               r["conditions"].get("cpuMaxFreqMHz", {}).get("policy8")) for _, r in lit_h3]
    ok(got_h3 == [("4-8", ["cpu-capped"], {"min": 2000, "hw": 2914, "cpus": "8"})],
       f"LiteRT-LM: cpusAllowedList 4-8 (the last read), policy8 capped -> cpu-capped (got {got_h3})")

    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    from unittest.mock import patch
    import build_summary
    from render_leaderboard import arm_row
    with patch.object(build_summary, "ROOT", sum_root), \
         patch.object(build_summary, "OUT", os.path.join(sum_root, "summary")):
        os.makedirs(build_summary.OUT, exist_ok=True)
        path, _ = build_summary.build_device()
    rows_h = [r for r in csv.DictReader(open(path)) if r["campaign"] == "results/raw/selftest-h"]
    got_h = [(r.get("cpu_capped"), r.get("cpu_max_freq")) for r in rows_h]
    ok(got_h == [("false", "p0 1704/1704 p4 2367/2367 p8 2914/2914"),
                 ("true", "p0 1704/1704 p4 1418/2367 p8 2914/2914"),
                 ("false", "p0 1425/1704 p4 2367/2367 p8 2914/2914")],
       f"summary: cpu_capped false / true / false, cpu_max_freq min/hw per policy (got {got_h})")
    a = arm_row(rows_h)
    got_a = (a["cold_n"], a["cold_median"], a.get("cpu_capped_n"), a.get("cpu_read_n"))
    ok(got_a == (2, 19.75, 1, 3),
       f"arm_row: the capped run is out of the pool, counted (cold_n, cold_median, cpu_capped_n, "
       f"cpu_read_n = {got_a})")

    # --- llama.cpp side builds (2026-10-07): the official Snapdragon asset of b11469 in
    # DEV/engines/b11469-snapdragon/{bin,lib}, run on the Hexagon NPU (llama.cpp-npu) or the
    # Adreno GPU through OpenCL (llama.cpp-gpu). The fake files hold the sha256sum the phone
    # prints for the real ones (the pin's), so the witness matches them through the registry.
    pin = json.load(open(os.path.join(ROOT, "android", "engine-pins.json")))["llama.cpp"]["b11469-snapdragon"]
    eng = os.path.join(dev, "engines", "b11469-snapdragon")
    eng_dev = "/data/local/tmp/llmbench/engines/b11469-snapdragon"
    for sub in ("bin", "lib"):
        os.makedirs(os.path.join(eng, sub))
    for name, digest in [("bin/llama-cli", pin["llama_cli_sha256"]), ("bin/llama-bench", pin["llama_bench_sha256"])] + \
            [(f"lib/{lib}", h) for lib, h in pin["so_files"].items()]:
        with open(os.path.join(eng, name), "w") as fh:
            fh.write("sha256=" + digest)
    side_root = os.path.join(tmp, "side")
    side_raw = os.path.join(side_root, "results", "raw")
    cmds = os.path.join(state, "engine_cmds")
    npu_cell = f"short-chat runs=1 backend=npu engine-build=b11469-snapdragon file={gguf_model}"

    # check 1: an NPU chat launch and an NPU llama-bench launch beside the CPU anchor. Each
    # record is the arm llama.cpp-npu, stamped with the side build by its witness (tool and
    # libs), carries the engine's device lines (backendRegistered: the chat tool's -lv 4
    # lines; llama-bench's JSON fields) and the wrapper's settings, and is not flagged.
    cells_n = os.path.join(tmp, "n.cells")
    with open(cells_n, "w") as fh:
        fh.write(f"android llama.cpp fake/gguf short-chat anchor=1 runs=1 file={gguf_model}\n"
                 f"android llama.cpp fake/gguf {npu_cell}\n"
                 f"android llama.cpp fake/gguf native-benchmark-1024x256 runs=1 backend=npu "
                 f"engine-build=b11469-snapdragon file={gguf_model}\n")
    if os.path.exists(cmds):
        os.remove(cmds)
    schedule([20.0, 73.1, 0.0])
    print("--- campaign N (llama.cpp-npu: chat + llama-bench on the side build, CPU anchor beside)")
    rc = run_campaign(dict(env, CAMPAIGN="selftest-n", BENCH_RAW_ROOT=side_raw), cells_n)
    ok(rc == 0, f"campaign N exits 0 (got {rc})")
    out_n = os.path.join(side_raw, "selftest-n", "app-path-android")
    npu = [r for _, r in records(out_n, "llama.cpp-npu_")]
    chat = [r for r in npu if r["task"] == "short-chat"]
    bench = [r for r in npu if r["task"] == "native-benchmark-1024x256"]
    want_lines = ["ggml_opencl: device: 'QUALCOMM Adreno(TM) 840 (OpenCL 3.0 Adreno(TM) 840)'",
                  "ggml-hex: Hexagon Arch version v81, DMA64 enabled",
                  "llama_prepare_model_devices: using device HTP0 (Hexagon) (unknown id) - 0 MiB free",
                  "load_tensors: offloaded 29/29 layers to GPU",
                  "load_tensors: CPU model buffer size = 121.71 MiB",
                  "load_tensors: HTP0 model buffer size = 406.58 MiB"]
    env_npu = (f"LD_LIBRARY_PATH={eng_dev}/lib ADSP_LIBRARY_PATH={eng_dev}/lib GGML_HEXAGON_DEVICES=HTP0 "
               f"GGML_HEXAGON_OPPOLL=1 GGML_OPENCL_KERNEL_CACHE_DIR={eng_dev}/clcache")
    if len(chat) == 1:
        r = chat[0]
        c = r["conditions"]
        ok((r["runtime"], r["engineVersion"], r["engineArtifact"])
           == ("llama.cpp-npu", "b11469-snapdragon", pin["llama_cli_sha256"]),
           f"npu chat: runtime llama.cpp-npu, engineVersion b11469-snapdragon (tool + 7 libs matched), "
           f"engineArtifact = the pinned llama-cli (got {r['runtime']}, {r['engineVersion']})")
        ok(c.get("backendRegistered") == want_lines and not c.get("protocolFlags"),
           f"npu chat: backendRegistered = the engine's HTP0 lines, prefixes off, not flagged "
           f"(got {c.get('backendRegistered')}, flags {c.get('protocolFlags')})")
        ok((c.get("engineBuild"), c.get("ggmlDevice"), c.get("threads"), c.get("flashAttn"), c.get("ubatch"),
            c.get("hexagonOpPoll"), c.get("nGpuLayers")) == ("b11469-snapdragon", "HTP0", 6, "on", 1024, 1, 99),
           "npu chat: the wrapper's settings stamped (threads 6, flash attention on, ubatch 1024, OPPOLL 1, -ngl 99)")
        cmd_c = c.get("engineCommand", "")
        ok(cmd_c.startswith(env_npu + f" {eng_dev}/bin/llama-cli -lv 4 -m ")
           and cmd_c.index("-lv 4") < cmd_c.index("--device HTP0")
           and " -t 6 -c 4096 " in cmd_c and cmd_c.endswith(" -st -ngl 99 -fa on -ub 1024 --device HTP0"),
           f"npu chat: engineCommand = the side build's env + tool, -lv 4 before --device: {cmd_c!r}")
        text = open(os.path.join(out_n, r["provenance"].get("decodedText", "missing"))).read() \
            if r["provenance"].get("decodedText") else ""
        ok(c.get("textCheck", {}).get("status") == "PASS" and ON_TASK[:60] in text and ON_TASK[60:] in text
           and "print_timing" not in text,
           f"npu chat: the reply is text-checked (PASS), the -lv 4 log line taken out of it: {text!r}")
        ok("firstEver" not in r["metrics"] and r["metrics"].get("decodeTokensPerSecond") == 73.1
           and "the host process only" in r["provenance"]["rssBasis"],
           "npu chat: no cache build on the NPU, decode parsed, rssBasis says the HTP0 buffers are outside RSS")
    else:
        ok(False, f"one npu chat record (got {len(chat)})")
    if len(bench) == 1:
        r = bench[0]
        c = r["conditions"]
        m = r["metrics"]
        ok((r["runtime"], r["engineVersion"], r["engineArtifact"])
           == ("llama.cpp-npu", "b11469-snapdragon", pin["llama_bench_sha256"]),
           f"npu llama-bench: engineArtifact = the pinned llama-bench (got {r['engineVersion']})")
        ok((m.get("promptTokensPerSecond"), m.get("promptTokenCount"), m.get("decodeTokensPerSecond"),
            m.get("generatedTokenCount"), m.get("coldRun")) == (4190.935295, 1024, 77.197416, 256, False),
           f"npu llama-bench: the S26 smoke's console parses (pp1024 and tg256 past the "
           f"FASTRPC_GET_DOMAINS[0] line) (got {m})")
        ok(c.get("backendRegistered") == ['llama-bench json: {"devices": "HTP0", "backends": "OpenCL,HTP", '
                                          '"gpu_info": "QUALCOMM Adreno(TM) 840, Hexagon", "n_gpu_layers": 99, '
                                          '"flash_attn": -1, "n_ubatch": 512}']
           and "protocolFlags" not in c and "textCheck" not in c,
           f"npu llama-bench: backendRegistered = its JSON's device fields, not flagged, no text check "
           f"(got {c.get('backendRegistered')})")
        ok(c.get("engineCommand", "").startswith(env_npu + f" {eng_dev}/bin/llama-bench -m ")
           and c["engineCommand"].endswith(" -t 6 -p 1024 -n 256 -o json -ngl 99 -ub 1024 --device HTP0")
           and (c.get("flashAttn"), c.get("ubatch")) == ("auto (llama-bench default)", 1024),
           f"npu llama-bench: the wrapper's bench flags (-t 6, -ub 1024 on HTP, no -fa): {c.get('engineCommand')!r}")
    else:
        ok(False, f"one npu llama-bench record (got {len(bench)})")
    shells = open(cmds).read().splitlines() if os.path.exists(cmds) else []
    cpu_n = records(out_n, "llama.cpp_")
    ok(len(shells) == 3 and shells[0].startswith("cd /data/local/tmp/llmbench && LD_LIBRARY_PATH=. taskset f0 ./llama-cli -m ")
       and " -t 4 " in shells[0] and all(s.startswith(f"cd /data/local/tmp/llmbench && {env_npu} taskset f0 {eng_dev}/bin/")
                                       for s in shells[1:]),
       f"the CPU anchor still runs the flat pinned build (-t 4), the side build its own dir: {shells}")

    # check 2: a launch whose console does not show the cell's device — none of the device
    # lines (the b11469 chat tool at its default verbosity), another device's lines, or a
    # partial offload — is kept, flagged backend-not-registered, listed in FAILURES.txt, and
    # leaves the pool: summary backend_registered false, out of arm_row; the shown run pools.
    cells_n2 = os.path.join(tmp, "n2.cells")
    with open(cells_n2, "w") as fh:
        fh.write(f"android llama.cpp fake/gguf {npu_cell.replace('runs=1', 'runs=4')}\n")
    partial = [ln.replace("offloaded 29/29", "offloaded 20/29") for ln in SIDE_LINES["HTP0"]]
    json.dump([[], SIDE_LINES["GPUOpenCL"], partial, None], open(os.path.join(state, "side_lines.json"), "w"))
    schedule([70.0, 88.0, 71.0, 73.0])
    print("--- campaign N2 (npu launches without the HTP0 lines: none, the GPU's, 20/29 offloaded; then a shown one)")
    rc = run_campaign(dict(env, CAMPAIGN="selftest-n2", BENCH_RAW_ROOT=side_raw), cells_n2)
    os.remove(os.path.join(state, "side_lines.json"))
    ok(rc == 0, f"campaign N2 exits 0 (got {rc})")
    out_n2 = os.path.join(side_raw, "selftest-n2", "app-path-android")
    n2 = [r for _, r in records(out_n2, "llama.cpp-npu_")]
    got_n2 = [(r["conditions"].get("protocolFlags") or None, r["metrics"].get("decodeTokensPerSecond")) for r in n2]
    ok(got_n2 == [(["backend-not-registered"], 70.0), (["backend-not-registered"], 88.0),
                  (["backend-not-registered"], 71.0), (None, 73.0)],
       f"no device lines / another device's / 20 of 29 layers: flagged backend-not-registered, record and rate "
       f"kept; the run that shows HTP0 is not flagged (got {got_n2})")
    ok(len(n2) == 4 and n2[0]["conditions"].get("backendRegistered") == []
       and any("using device GPUOpenCL" in ln for ln in n2[1]["conditions"].get("backendRegistered", [])),
       "the record carries the lines it had: none, or the other device's")
    fails_n2 = os.path.join(out_n2, "FAILURES.txt")
    fails_n2 = open(fails_n2).read().splitlines() if os.path.exists(fails_n2) else []
    ok(fails_n2 == ["llama.cpp-npu fake/gguf short-chat rc=1"] * 3,
       f"each flagged launch is a failed launch, listed under its arm: {fails_n2}")

    # GPU: the first chat launch on an empty program cache is the cache build (firstEver,
    # marker written); the next is not; a re-pushed build (cache dir emptied, marker kept)
    # builds again and is labelled again
    cells_g4 = os.path.join(tmp, "g4.cells")
    with open(cells_g4, "w") as fh:
        fh.write(f"android llama.cpp fake/gguf short-chat runs=2 backend=gpu engine-build=b11469-snapdragon "
                 f"file={gguf_model}\n")
    schedule([88.5, 88.8])
    print("--- campaign G4 (llama.cpp-gpu: OpenCL program cache built by run 1)")
    rc = run_campaign(dict(env, CAMPAIGN="selftest-g4", BENCH_RAW_ROOT=side_raw), cells_g4)
    ok(rc == 0, f"campaign G4 exits 0 (got {rc})")
    gpu = [r for _, r in records(os.path.join(side_raw, "selftest-g4", "app-path-android"), "llama.cpp-gpu_")]
    ok([r["metrics"].get("firstEver") for r in gpu] == [True, None]
       and all(r["conditions"].get("ggmlDevice") == "GPUOpenCL" and not r["conditions"].get("protocolFlags")
               and "GGML_HEXAGON_DEVICES" not in r["conditions"]["engineCommand"] for r in gpu)
       and glob.glob(os.path.join(dev, "markers", "*.llama.cpp-gpu.*.cachebuilt")),
       f"gpu: run 1 on an empty cache is firstEver, run 2 is not, marker written, no HTP device env "
       f"(got {[r['metrics'].get('firstEver') for r in gpu]})")
    for f in glob.glob(os.path.join(eng, "clcache", "*.clbin")):
        os.remove(f)
    schedule([88.1, 88.6])
    rc = run_campaign(dict(env, CAMPAIGN="selftest-g5", BENCH_RAW_ROOT=side_raw), cells_g4)
    gpu5 = [r for _, r in records(os.path.join(side_raw, "selftest-g5", "app-path-android"), "llama.cpp-gpu_")]
    ok(rc == 0 and [r["metrics"].get("firstEver") for r in gpu5] == [True, None],
       "gpu: an emptied program cache relabels the next launch firstEver even with the marker on the device")

    # the witness reads the libs: a side build whose libggml-hexagon.so is not the pin's
    # stamps 'unknown' with the lib named; a side build that is not on the device stops
    # the cell before any launch (no record, listed in FAILURES.txt)
    hexagon = os.path.join(eng, "lib", "libggml-hexagon.so")
    with open(hexagon, "w") as fh:
        fh.write("sha256=" + "0" * 64)
    cells_w = os.path.join(tmp, "w.cells")
    with open(cells_w, "w") as fh:
        fh.write(f"android llama.cpp fake/gguf {npu_cell}\n"
                 f"android llama.cpp fake/gguf native-benchmark-1024x256 runs=1 backend=npu "
                 f"engine-build=b0-not-pushed file={gguf_model}\n")
    schedule([73.0])
    if os.path.exists(cmds):
        os.remove(cmds)
    print("--- campaign W (a lib that is not the pin's; a side build that is not on the device)")
    rc = run_campaign(dict(env, CAMPAIGN="selftest-w", BENCH_RAW_ROOT=side_raw), cells_w)
    with open(hexagon, "w") as fh:
        fh.write("sha256=" + pin["so_files"]["libggml-hexagon.so"])
    out_w = os.path.join(side_raw, "selftest-w", "app-path-android")
    w = [r for _, r in records(out_w, "llama.cpp-npu_")]
    fails_w = os.path.join(out_w, "FAILURES.txt")
    fails_w = open(fails_w).read().splitlines() if os.path.exists(fails_w) else []
    ok(len(w) == 1 and w[0]["engineVersion"] == "unknown (on-device b11469-snapdragon llama-cli with lib "
                                                 "libggml-hexagon.so unmatched in android/engine-pins.json)",
       f"a lib off the pin stamps 'unknown' and names the lib (got {[r['engineVersion'] for r in w]})")
    ok(fails_w == ["llama.cpp-npu fake/gguf native-benchmark-1024x256 rc=1"]
       and len(open(cmds).read().splitlines()) == 1,
       f"a side build that is not on the device: no launch, no record, one FAILURES.txt line: {fails_w}")

    # the summary and the pool: backend_registered true / false / empty, and arm_row leaves
    # the false runs out (campaign N2: three flagged, one shown -> a pool of one)
    with patch.object(build_summary, "ROOT", side_root), \
         patch.object(build_summary, "OUT", os.path.join(side_root, "summary")):
        os.makedirs(build_summary.OUT, exist_ok=True)
        path, _ = build_summary.build_device()
    side_rows = list(csv.DictReader(open(path)))
    rows_n2 = [r for r in side_rows if r["campaign"] == "results/raw/selftest-n2"]
    ok([r["backend_registered"] for r in rows_n2] == ["false", "false", "false", "true"]
       and {r["backend_registered"] for r in side_rows if r["runtime"] == "llama.cpp"} == {""},
       f"summary: backend_registered false / true on the side build's runs, empty on the CPU arm's "
       f"(got {[r['backend_registered'] for r in rows_n2]})")
    a = arm_row(rows_n2) if rows_n2 else {}  # no rows = a runner that wrote no record: a FAIL, not a crash
    ok((a.get("cold_n"), a.get("cold_median"), a.get("backend_off_n")) == (1, 73.0, 3),
       f"arm_row: the three flagged runs are out of the pool, counted (cold_n, cold_median, backend_off_n = "
       f"{(a.get('cold_n'), a.get('cold_median'), a.get('backend_off_n'))})")

    # check 3: the CPU llama.cpp arm's records keep 3d5655c's key layout — a legacy cell's
    # (campaigns A and N, the latter beside side-build cells) and a round launch's (the round
    # campaign's anchor): nothing of the side-build wiring reaches a row without backend=
    layouts = [key_layout(r) for _, r in lla + cpu_n]
    ok(len(layouts) == 3 and all(k == CPU_LLAMA_KEYS["legacy"] for k in layouts),
       f"CPU llama.cpp legacy records: the key layout of 3d5655c "
       f"(got {[k for k in layouts if k != CPU_LLAMA_KEYS['legacy']][:1]})")
    layouts = [key_layout(r) for _, r in controls]
    ok(len(layouts) == 2 and all(k == CPU_LLAMA_KEYS["round"] for k in layouts),
       f"CPU llama.cpp round-mode records: the key layout of 3d5655c "
       f"(got {[k for k in layouts if k != CPU_LLAMA_KEYS['round']][:1]})")

    # --- LiteRT-LM on the NPU (2026-10-08): a LiteRT-LM runtime build with the Qualcomm
    # dispatch and QNN libraries, flat in DEV/engines/<tag> (the skel in dsp/), an own AOT
    # bundle side-loaded by path. The build's pin is registered on the first device run, so
    # the witness reads a fixture registry here (BENCH_TEST_PINS = the real one + this tag).
    npu_tag = "main-20260821-selfbuilt"
    npu_eng = os.path.join(dev, "engines", npu_tag)
    npu_files = ["litert_lm_advanced_main", "libLiteRtDispatch_Qualcomm.so", "libGemmaModelConstraintProvider.so",
                 "libQnnHtp.so", "libQnnSystem.so", "libQnnHtpV81Stub.so", "dsp/libQnnHtpV81Skel.so"]
    npu_sha = {name: hashlib.sha256(("fixture " + name).encode()).hexdigest() for name in npu_files}
    os.makedirs(os.path.join(npu_eng, "dsp"))
    for name in npu_files:
        with open(os.path.join(npu_eng, name), "w") as fh:
            fh.write("sha256=" + npu_sha[name])
    fixture_pins = json.load(open(os.path.join(ROOT, "android", "engine-pins.json")))
    fixture_pins["litert-lm"][npu_tag] = {"litert_lm_advanced_main_sha256": npu_sha["litert_lm_advanced_main"],
                                          "so_files": {n: npu_sha[n] for n in npu_files[1:]}}
    pins_path = os.path.join(tmp, "engine-pins.fixture.json")
    json.dump(fixture_pins, open(pins_path, "w"))
    npu_bundle = os.path.join(tmp, "npu", "model_qualcomm_SM8850.litertlm")
    os.makedirs(os.path.dirname(npu_bundle))
    with open(npu_bundle, "w") as fh:
        fh.write("weights of an own NPU export")
    npu_cell = f"short-chat backend=npu engine-build={npu_tag} file={npu_bundle}"
    env_l = dict(env, BENCH_TEST_PINS=pins_path)
    model_l = "/data/local/tmp/llmbench/models/Qwen_Qwen3-0.6B_model_qualcomm_SM8850.litertlm"
    env_litert_npu = (f'LD_LIBRARY_PATH={NPU_ENG} '
                      f'ADSP_LIBRARY_PATH="{NPU_ENG}/dsp;/system/lib/rfsa/adsp;/vendor/lib/rfsa/adsp;/dsp"')
    cmd_litert_npu = (f"{NPU_ENG}/litert_lm_advanced_main --backend=npu --model_path={model_l} "
                      "--input_prompt_file=/data/local/tmp/llmbench/prompts/short-chat.txt --max_output_tokens=128 "
                      "--async=false --benchmark --benchmark_prefill_tokens=0 --benchmark_decode_tokens=0 "
                      f"--use_hw_cache_update_for_npu=false --litert_dispatch_lib_dir={NPU_ENG}")

    # check L1: a LiteRT-LM NPU cell's records — the arm litert-lm-npu, stamped with the build
    # by its witness (the tool and six libs, the skel under dsp/), the engine's NPU lines in
    # backendRegistered, the HW cache update off as the engine echoed it, the bundle's fixed
    # cache, the build's env and flags in engineCommand, the reply text-checked with the
    # engine's log lines taken out of it, rssBasis saying the NPU's buffers are outside RSS;
    # the first launch labelled by litert's cache marker. An export the runner cannot name by
    # its sha256 keeps quantization "unrecorded" and an unrecorded cache length.
    cells_l = os.path.join(tmp, "l.cells")
    with open(cells_l, "w") as fh:
        fh.write(f"android litert-lm Qwen/Qwen3-0.6B {npu_cell} runs=2\n")
    if os.path.exists(cmds):
        os.remove(cmds)
    schedule([66.4, 66.9])
    print("--- campaign L (litert-lm-npu: the NPU build's launch, two runs)")
    rc = run_campaign(dict(env_l, CAMPAIGN="selftest-l", BENCH_RAW_ROOT=side_raw), cells_l)
    ok(rc == 0, f"campaign L exits 0 (got {rc})")
    out_l = os.path.join(side_raw, "selftest-l", "app-path-android")
    lnpu = [r for _, r in records(out_l, "litert-lm-npu_")]
    if len(lnpu) == 2:
        r = lnpu[0]
        c = r["conditions"]
        ok((r["runtime"], r["engineVersion"], r["engineArtifact"])
           == ("litert-lm-npu", npu_tag, npu_sha["litert_lm_advanced_main"]),
           f"litert npu: runtime litert-lm-npu, engineVersion {npu_tag} (tool + 6 libs matched, the skel "
           f"under dsp/), engineArtifact = the build's tool (got {r['runtime']}, {r['engineVersion']})")
        ok(c.get("backendRegistered") == NPU_REGISTERED and not c.get("protocolFlags"),
           f"litert npu: backendRegistered = the engine's NPU lines (addresses as <addr>), not flagged "
           f"(got {c.get('backendRegistered')}, flags {c.get('protocolFlags')})")
        ok((c.get("engineBuild"), c.get("hwCacheUpdateForNpu"), c.get("contextTokens"), c.get("sampler"))
           == (npu_tag, False, "aot-fixed (cache length unrecorded)", "engine-default")
           and r["model"]["quantization"] == "unrecorded (artifact name carries no quant label)",
           f"litert npu: engineBuild, hwCacheUpdateForNpu false (the engine's echo), the AOT cache, and an "
           f"unknown export unlabelled (got {c.get('engineBuild')}, {c.get('hwCacheUpdateForNpu')}, "
           f"{c.get('contextTokens')}, {r['model']['quantization']!r})")
        ok(c.get("engineCommand") == f"{env_litert_npu} {cmd_litert_npu}",
           f"litert npu: engineCommand = the build's env + advanced_main with --benchmark on the real prompt, "
           f"the HW cache update off, the build's dispatch dir: {c.get('engineCommand')!r}")
        text = open(os.path.join(out_l, r["provenance"].get("decodedText", "missing"))).read() \
            if r["provenance"].get("decodedText") else ""
        ok(c.get("textCheck", {}).get("status") == "PASS" and text.startswith("[thought] " + ON_TASK[:70])
           and ON_TASK[70:] in text and "profile summary" not in text and "Source Location" not in text,
           f"litert npu: the reply is text-checked (PASS), the engine's log lines taken out of it: {text!r}")
        m = r["metrics"]
        ok((m.get("decodeTokensPerSecond"), m.get("promptTokensPerSecond"), m.get("promptTokenCount"),
            m.get("generatedTokenCount"), m.get("firstTokenLatencyMS"), m.get("coldRun"))
           == (66.4, 1978.02, 18, 128, 50.0, True)
           and r["provenance"]["rssBasis"].endswith("the NPU's buffers (Hexagon, through the Qualcomm dispatch "
                                                    "and QNN) are not in VmRSS / VmHWM"),
           f"litert npu: BenchmarkInfo parsed, rssBasis says the NPU's buffers are outside RSS (got {m})")
        ok([x["metrics"].get("firstEver") for x in lnpu] == [True, None]
           and os.path.exists(os.path.join(dev, "markers", os.path.basename(model_l) + ".npu.cachebuilt")),
           f"litert npu: litert's cache marker: run 1 firstEver, run 2 not "
           f"(got {[x['metrics'].get('firstEver') for x in lnpu]})")
    else:
        ok(False, f"two litert-lm-npu records (got {len(lnpu)})")
    shells = open(cmds).read().splitlines() if os.path.exists(cmds) else []
    ok(len(shells) == 2 and all(s == f"cd /data/local/tmp/llmbench && {env_litert_npu} taskset f0 {cmd_litert_npu}"
                                for s in shells),
       f"litert npu: the engine shell runs the build's own dir and libs: {shells[:1]}")
    ok(not glob.glob(os.path.join(out_l, "FAILURES.txt")), "litert npu: no failed launch")

    # check L2: a launch whose lines do not show the NPU dispatch — none at all, the NPU
    # registered while nothing was dispatched to it (the model on XNNPACK), the dispatch
    # without the NPU's registration — is kept, flagged backend-not-registered, a failed launch
    # (FAILURES.txt), summary backend_registered false and out of arm_row's pool; the shown run
    # pools. A lib off the build's pin (the skel under dsp/) stamps 'unknown' and names it.
    cells_l2 = os.path.join(tmp, "l2.cells")
    with open(cells_l2, "w") as fh:
        fh.write(f"android litert-lm Qwen/Qwen3-0.6B {npu_cell} runs=4\n")
    no_dispatch = [ln for ln in NPU_LINES if "DispatchDelegate" not in ln and "QNN context" not in ln]
    no_register = [ln for ln in NPU_LINES if "name=NpuAccelerator" not in ln and "accelerator registered." not in ln]
    json.dump([[], no_dispatch, no_register, None], open(os.path.join(state, "npu_lines.json"), "w"))
    schedule([70.0, 88.0, 71.0, 73.0])
    print("--- campaign L2 (litert npu launches without the NPU lines: none, registered but not dispatched, "
          "dispatched but not registered; then a shown one)")
    rc = run_campaign(dict(env_l, CAMPAIGN="selftest-l2", BENCH_RAW_ROOT=side_raw), cells_l2)
    os.remove(os.path.join(state, "npu_lines.json"))
    ok(rc == 0, f"campaign L2 exits 0 (got {rc})")
    out_l2 = os.path.join(side_raw, "selftest-l2", "app-path-android")
    l2 = [r for _, r in records(out_l2, "litert-lm-npu_")]
    got_l2 = [(r["conditions"].get("protocolFlags") or None, r["metrics"].get("decodeTokensPerSecond")) for r in l2]
    ok(got_l2 == [(["backend-not-registered"], 70.0), (["backend-not-registered"], 88.0),
                  (["backend-not-registered"], 71.0), (None, 73.0)],
       f"no NPU lines / registered but not dispatched / dispatched but not registered: flagged "
       f"backend-not-registered, record and rate kept; the shown run is not flagged (got {got_l2})")
    ok(len(l2) == 4 and l2[0]["conditions"].get("backendRegistered") == []
       and l2[0]["conditions"].get("hwCacheUpdateForNpu") is None
       and not any("DispatchDelegate" in ln for ln in l2[1]["conditions"].get("backendRegistered", []))
       and "Choose backend: npu" in l2[1]["conditions"].get("backendRegistered", []),
       "the record carries the lines it had (none: no echo either, hwCacheUpdateForNpu null)")
    fails_l2 = os.path.join(out_l2, "FAILURES.txt")
    fails_l2 = open(fails_l2).read().splitlines() if os.path.exists(fails_l2) else []
    ok(fails_l2 == ["litert-lm-npu Qwen/Qwen3-0.6B short-chat rc=1"] * 3,
       f"each flagged launch is a failed launch, listed under its arm: {fails_l2}")
    skel = os.path.join(npu_eng, "dsp", "libQnnHtpV81Skel.so")
    with open(skel, "w") as fh:
        fh.write("sha256=" + "0" * 64)
    cells_l3 = os.path.join(tmp, "l3.cells")
    with open(cells_l3, "w") as fh:
        fh.write(f"android litert-lm Qwen/Qwen3-0.6B {npu_cell} runs=1\n")
    schedule([73.0])
    run_campaign(dict(env_l, CAMPAIGN="selftest-l3", BENCH_RAW_ROOT=side_raw), cells_l3)
    with open(skel, "w") as fh:
        fh.write("sha256=" + npu_sha["dsp/libQnnHtpV81Skel.so"])
    l3 = [r for _, r in records(os.path.join(side_raw, "selftest-l3", "app-path-android"), "litert-lm-npu_")]
    ok(len(l3) == 1 and l3[0]["engineVersion"] == f"unknown (on-device {npu_tag} litert_lm_advanced_main with lib "
                                                  "dsp/libQnnHtpV81Skel.so unmatched in android/engine-pins.json)",
       f"a skel off the build's pin stamps 'unknown' and names it (got {[r['engineVersion'] for r in l3]})")
    with patch.object(build_summary, "ROOT", side_root), \
         patch.object(build_summary, "OUT", os.path.join(side_root, "summary")):
        path, _ = build_summary.build_device()
    rows_l2 = [r for r in csv.DictReader(open(path)) if r["campaign"] == "results/raw/selftest-l2"]
    ok([r["backend_registered"] for r in rows_l2] == ["false", "false", "false", "true"]
       and {r["runtime"] for r in rows_l2} == {"litert-lm-npu"},
       f"summary: backend_registered false / true on the NPU build's runs "
       f"(got {[r['backend_registered'] for r in rows_l2]})")
    a = arm_row(rows_l2) if rows_l2 else {}
    ok((a.get("cold_n"), a.get("cold_median"), a.get("backend_off_n")) == (1, 73.0, 3),
       f"arm_row: the three flagged runs are out of the pool, counted (cold_n, cold_median, backend_off_n = "
       f"{(a.get('cold_n'), a.get('cold_median'), a.get('backend_off_n'))})")
    # the export this arm runs is named by its sha256 (the label and the cache length its export
    # logs give); the reply extraction on the shapes of the build's real consoles
    sys.path.insert(0, os.path.join(ROOT, "android", "bench"))
    import run_cell
    import parsers
    # (getattr: a runner without them is a FAIL line here, not a crash before the checks below)
    own = getattr(run_cell, "own_npu_bundle", None)
    label, ctx = own("f8909326639011c6123126c06c4f7d205857b1915c8b49de6844522fe5d211f2") if own else ("", None)
    ok(ctx == "aot-fixed-1024" and label.startswith("own export, NPU AOT for SM8850: int8 weights")
       and "static-range int16 activations" in label,
       f"own_npu_bundle: the Qwen3 0.6B SM8850 export -> its label and cache (got {label!r}, {ctx!r})")
    litert_reply = getattr(parsers, "litert_reply", lambda text: None)
    jit = ("I0000 00:00:1790871082.995872   23069 litert_lm_lib.cc:868] Running single-turn conversation\n"
           "[1] graph_prepare.cc:208::ERROR:could not create op: q::Select.exe\n"
           "[1] QnnDsp <E> validateNativeOps master op validator ElementWiseSelect_ERROR: [qnn_manager.cc:480] \n"
           "[thought] \nOkay, the user is asking what the capital of France is. I know that France has "
           "many cities, but[/thought]\n"
           "INFO: [accelerator_registry.cc:43] DestroyAccelerator: ptr=0xb4000076b6e130d0, name=CpuAccelerator\n")
    garbage = ("I0000 00:00:1790957228.031559   19740 litert_lm_lib.cc:868] Running single-turn conversation\n"
               "[1] graph_prepare.cc:1772::ERROR:Op 0x4e790000280b preparation failed with err:-1\n"
               "<?\n Philippines Philippines Philippines Philippines Philippines Philippines Philippines\n"
               "INFO: [accelerator_registry.cc:43] DestroyAccelerator: ptr=0xb400006d4380b590, name=CpuAccelerator\n")
    ok(litert_reply(jit) == ("[thought] \nOkay, the user is asking what the capital of France is. "
                             "I know that France has many cities, but[/thought]")
       and litert_reply(garbage) == "<?\n Philippines Philippines Philippines Philippines Philippines "
                                    "Philippines Philippines"
       and parsers.text_integrity(litert_reply(garbage) or "")["status"] == "FAIL"
       and litert_reply("no conversation started") == "",
       "litert_reply on the build's own consoles (no BenchmarkInfo, QNN lines, a thought channel; the "
       "HW-cache-update garbage fails the screen)")

    # the cells grammar of the side builds (validate_cells) and the runner's refusals
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import validate_cells
    grammar = [
        ("android llama.cpp m/g short-chat backend=npu engine-build=b11469-snapdragon file=x.gguf", None),
        ("android llama.cpp m/g native-benchmark-1024x256 backend=gpu engine-build=b11469-snapdragon file=x.gguf", None),
        ("android litert-lm m/l short-chat backend=npu engine-build=main-20260821-selfbuilt file=x.litertlm", None),
        ("android litert-lm m/l long-context-1024-gen256 backend=npu engine-build=main-20260821-selfbuilt "
         "file=x.litertlm context-tokens=2048 exclude=aot-cache-length-1024", None),
        ("android llama.cpp m/g short-chat backend=cpu file=x.gguf", "takes backend=npu|gpu"),
        ("android llama.cpp m/g short-chat backend=npu file=x.gguf", "go together"),
        ("android llama.cpp m/g short-chat engine-build=b11469-snapdragon file=x.gguf", "go together"),
        ("mac litert-lm m/l short-chat backend=npu", "backend=npu is an android"),
        ("android litert-lm m/l short-chat backend=npu file=x.litertlm", "go together"),
        ("android litert-lm m/l short-chat backend=gpu engine-build=main-20260821-selfbuilt file=x.litertlm",
         "go together"),
        ("android litert-lm m/l long-context-1024-gen256 backend=npu engine-build=main-20260821-selfbuilt "
         "file=x.litertlm context-tokens=2048", "no context-tokens="),
        ("android litert-lm m/l native-benchmark-1024x256 backend=npu engine-build=main-20260821-selfbuilt "
         "file=x.litertlm", "no native-benchmark-"),
        ("ios litert-lm m/l short-chat backend=gpu engine-build=main-20260821-selfbuilt",
         "engine-build= is read for android llama.cpp and litert-lm rows only"),
        ("android litert-lm m/l asr-rtf-librispeech-82s backend=npu file=x.litertlm", "asr-rtf-* needs backend=cpu|gpu"),
        ("android llama.cpp m/g short-chat backend=tpu engine-build=b file=x.gguf", "want cpu|gpu|npu"),
    ]
    for line, want in grammar:
        path_v = os.path.join(tmp, "grammar.cells")
        with open(path_v, "w") as fh:
            fh.write(line + "\n")
        errors, _ = validate_cells.validate_file(path_v)
        ok((not errors) if want is None else any(want in e for e in errors),
           f"validate_cells: {line.split(' file=')[0]!r} -> {'valid' if want is None else want!r} (got {errors})")
    path_v = os.path.join(tmp, "grammar.cells")
    with open(path_v, "w") as fh:
        fh.write("android llama.cpp m/g short-chat backend=npu engine-build=a file=x.gguf\n"
                 "android llama.cpp m/g short-chat backend=npu engine-build=b file=x.gguf\n")
    errors, _ = validate_cells.validate_file(path_v)
    ok(any("duplicate cell" in e for e in errors),
       f"validate_cells: one arm on two side builds in one file is a duplicate cell (got {errors})")
    for argv, want in ((["--runtime", "litert-lm", "--backend", "npu"], "pass --backend npu and --engine-build together"),
                       (["--runtime", "litert-lm", "--backend", "gpu", "--engine-build", npu_tag],
                        "pass --backend npu and --engine-build together"),
                       (["--runtime", "litert-lm", "--backend", "npu", "--engine-build", npu_tag,
                         "--context-tokens", "2048"], "no --context-tokens"),
                       (["--runtime", "llama.cpp", "--backend", "cpu"], "without --backend is the CPU arm"),
                       (["--runtime", "llama.cpp", "--backend", "npu"], "pass --backend and --engine-build together"),
                       (["--runtime", "llama.cpp", "--engine-build", "b11469-snapdragon"], "together")):
        # --file: a runner that let the arguments through would push the local fixture to the
        # fake phone, never ask the Hub
        p = subprocess.run([sys.executable, os.path.join(ROOT, "android", "bench", "run_cell.py"), *argv,
                            "--model-id", "m/g", "--file", gguf_model, "--task", "short-chat", "--runs", "1",
                            "--out", os.path.join(tmp, "refused")],
                           env=env, capture_output=True, text=True)
        ok(p.returncode == 2 and want in p.stderr, f"run_cell refuses {' '.join(argv)}: {p.stderr.strip()[-110:]!r}")
    p = subprocess.run([sys.executable, os.path.join(ROOT, "android", "bench", "run_cell.py"), "--runtime", "litert-lm",
                        "--backend", "npu", "--engine-build", npu_tag, "--model-id", "m/l", "--file", npu_bundle,
                        "--task", "short-chat", "--runs", "1", "--out", os.path.join(tmp, "refused"),
                        "--serial", "R3CX40ABCDE"], env=env_l, capture_output=True, text=True)
    ok(p.returncode == 1 and "BENCH_TEST_PINS is only for the FAKESELF selftest fixture" in p.stderr,
       f"run_cell reads a fixture registry for the FAKESELF serial only: {p.stderr.strip()[-90:]!r}")
    p = subprocess.run([sys.executable, os.path.join(ROOT, "android", "bench", "run_campaign.py"), cells_l,
                        "--dry-run"], env=dict(env, ROUNDS="1"), capture_output=True, text=True)
    plan = [json.loads(line) for line in p.stdout.splitlines() if line.startswith("{")]
    ok(p.returncode == 0 and len(plan) == 1
       and plan[0]["cell"].startswith("litert-lm-npu Qwen/Qwen3-0.6B short-chat context-tokens=default ")
       and plan[0]["command"] == f"cd /data/local/tmp/llmbench && {env_litert_npu} taskset f0 {cmd_litert_npu}",
       f"--dry-run plans the LiteRT-LM NPU build's env and command: {[d.get('command', '')[:100] for d in plan]}")
    p = subprocess.run([sys.executable, os.path.join(ROOT, "android", "bench", "run_campaign.py"), cells_n,
                        "--dry-run"], env=dict(env, ROUNDS="1"), capture_output=True, text=True)
    plan = [json.loads(line) for line in p.stdout.splitlines() if line.startswith("{")]
    ok(p.returncode == 0 and [d["cell"].split(" file=")[0] for d in plan] == [
        "llama.cpp fake/gguf short-chat context-tokens=default",
        "llama.cpp-npu fake/gguf short-chat context-tokens=default",
        "llama.cpp-npu fake/gguf native-benchmark-1024x256 context-tokens=default"]
       and plan[0]["command"].startswith("cd /data/local/tmp/llmbench && LD_LIBRARY_PATH=. taskset f0 ./llama-cli ")
       and plan[1]["command"].startswith(f"cd /data/local/tmp/llmbench && {env_npu} taskset f0 {eng_dev}/bin/llama-cli -lv 4 "),
       f"--dry-run plans the side build's env and tool, the CPU arm's flat build: "
       f"{[d.get('command', '')[:90] for d in plan]}")

    # --- executorch: the runner of the model's family (docs/executorch-arm-v1.md). The fake
    # phone replays the Galaxy S26 smoke of 2026-10-07 (android/bench/testdata/executorch:
    # llama_main's stdout, its ET_LOG stderr); the inputs are a staged own export in miniature
    # (a stand-in .pte, its recipe.json, a tokenizer, the rendered prompts the launches read).
    import parsers
    fx = os.path.join(ROOT, "android", "bench", "testdata", "executorch")
    rd = lambda name: open(os.path.join(fx, name), encoding="utf-8").read()
    short = parsers.parse_executorch(rd("s26-short-chat.stdout.txt"), rd("s26-short-chat.stderr.txt"),
                                     rd("short-chat.qwen3-chat.txt"))
    long_ = parsers.parse_executorch(rd("s26-long-context-1024-gen256.stdout.txt"),
                                     rd("s26-long-context-1024-gen256.stderr.txt"),
                                     rd("long-context-1024-gen256.qwen3-chat.txt"))
    ms, ml = short["metrics"], long_["metrics"]
    ok((round(ms["decodeTokensPerSecond"], 1), ms["promptTokenCount"], ms["generatedTokenCount"],
        ms["firstTokenLatencyMS"], round(ml["decodeTokensPerSecond"], 1), ml["promptTokenCount"],
        ml["firstTokenLatencyMS"], short["flags"], long_["flags"]) == (124.5, 19, 127, 57, 31.2, 1338, 1921, [], []),
       f"parse_executorch: the S26 smoke's short-chat decode 124.5 tok/s (127 / 1020 ms), prompt 19, TTFT 57 ms; "
       f"1K decode 31.2, prompt 1338, TTFT 1921; rates recomputed from the stats line's ms agree with its own "
       f"(got {ms} {ml} {short['flags']} {long_['flags']})")
    ok(short["text"].startswith("<think>\nOkay, so the user is asking") and not short["text"].endswith("\n")
       and "PyTorchObserver" not in short["text"] and short["log"].get("cpuThreads") == 8
       and short["log"].get("metadata", {}).get("get_max_context_len") == 2048
       and short["log"].get("rssAfterGenerationMiB") == 1031.214844,
       f"text = stdout after the echo, cut before the stats line; the runner log: 8 threads, "
       f"get_max_context_len 2048, RSS after finishing text generation 1031.214844 MiB (got {short['log']})")
    bad = parsers.parse_executorch(rd("s26-short-chat.stdout.txt"), "", rd("long-context-1024-gen256.qwen3-chat.txt"))
    ok(bad["text"] is None and "echo-mismatch" in bad["flags"],
       f"a stdout whose echo is not the prompt gives no text, flagged echo-mismatch (got {bad['flags']})")
    g4 = parsers.parse_gemma4_runner(rd("mac-gemma-4-E2B-it-short-chat.stdout.txt"),
                                     rd("mac-gemma-4-E2B-it-short-chat.stderr.txt"))
    mg = g4["metrics"]
    ok((mg["promptTokenCount"], mg["generatedTokenCount"], round(mg["decodeTokensPerSecond"], 2),
        round(mg["promptTokensPerSecond"], 1), mg["firstTokenLatencyMS"], g4["flags"])
       == (20, 64, 46.38, 197.4, 101.3, []) and g4["text"].startswith("Imagine a smartphone")
       and g4["statsReport"].startswith("=== Gemma 4 Performance Report ===\n  Model load:"),
       f"parse_gemma4_runner: the report's counts over its printed times (64 / 1.38 s, 20 / 101.3 ms), "
       f"its own rates within the rounding (got {mg} {g4['flags']})")

    et_models = os.path.join(tmp, "etmodels")
    stem = "Qwen3-0.6B-ET1.5.1-xnnpack-8da4w-emb8-ctx2048"
    os.makedirs(os.path.join(et_models, stem + ".prompts"))
    with open(os.path.join(et_models, stem + ".pte"), "w") as fh:
        fh.write("stand-in .pte of " + stem)
    with open(os.path.join(et_models, "tokenizer.json"), "w") as fh:
        fh.write('{"stand-in": "tokenizer.json"}')
    rev = "c1899de289a04d12100db370d81485cdf75e47ca"
    manifest = {"snapshot": f"/hf/models--Qwen--Qwen3-0.6B/snapshots/{rev}", "transformers": "5.0.0rc1",
                "call": "apply_chat_template([{'role': 'user', 'content': <file>}], tokenize=False, "
                        "add_generation_prompt=True)", "tasks": {}}
    for task, tokens in (("short-chat", 19), ("long-context-1024-gen256", 1338)):
        text = rd(f"{task}.qwen3-chat.txt")
        with open(os.path.join(et_models, stem + ".prompts", f"{task}.chat.txt"), "w") as fh:
            fh.write(text)
        manifest["tasks"][task] = {"renderedSha256": hashlib.sha256(text.encode()).hexdigest(),
                                   "hostPromptTokens": tokens}
    json.dump(manifest, open(os.path.join(et_models, stem + ".prompts", "prompts.json"), "w"))
    sha = lambda path: hashlib.sha256(open(path, "rb").read()).hexdigest()
    recipe = {"executorch": "1.5.1", "model_class": "qwen3_0_6b",
              "config_yaml_path": "examples/models/qwen3/config/qwen3_xnnpack_q8da4w.yaml",
              "config_yaml": ("model:\n  dtype_override: fp32\n\nquantization:\n  qmode: 8da4w\n"
                              "  embedding_quantize: 8,0\n\nexport:\n  max_seq_length: 2048\n"
                              "  max_context_length: 2048\n\nbackend:\n  xnnpack:\n    enabled: True\n"),
              "checkpoint": {"hf_repo": "Qwen/Qwen3-0.6B", "revision": rev, "snapshot": manifest["snapshot"]},
              "pte_sha256": sha(os.path.join(et_models, stem + ".pte")),
              "tokenizer": {"file": "/elsewhere/tokenizer.json",
                            "sha256": sha(os.path.join(et_models, "tokenizer.json"))}}
    json.dump(recipe, open(os.path.join(et_models, stem + ".recipe.json"), "w"))
    # the runner is on the phone by hand, as the other engines are; this one reads as the pinned
    # XNNPACK build of v1.5.1 (the fake sha256sum prints the stand-in's sha)
    pinned = json.load(open(os.path.join(ROOT, "android", "engine-pins.json")))["executorch"]["v1.5.1"]
    os.makedirs(os.path.join(dev, "executorch-v1.5.1"))
    with open(os.path.join(dev, "executorch-v1.5.1", "llama_main"), "w") as fh:
        fh.write("sha256=" + pinned["llama_main_sha256"])
    json.dump([{"stdout": os.path.join(fx, f"s26-{t}.stdout.txt"), "stderr": os.path.join(fx, f"s26-{t}.stderr.txt")}
               for t in ("short-chat", "long-context-1024-gen256")], open(os.path.join(state, "et_launches.json"), "w"))
    alias = "et1.5.1-xnnpack-8da4w-g128-emb8"
    cells_et = os.path.join(tmp, "et.cells")
    with open(cells_et, "w") as fh:
        fh.write(f"android executorch own-export/{stem} short-chat backend=xnnpack local=1 file={stem}.pte "
                 f"recipe={alias} runs=1\n"
                 f"android executorch own-export/{stem} long-context-1024-gen256 backend=xnnpack local=1 "
                 f"file={stem}.pte recipe={alias} runs=1 context-tokens=2048\n")
    env_et = dict(env, CAMPAIGN="selftest-et", ET_MODEL_DIR=et_models, BENCH_ANDROID_BIN_DIR=os.path.join(tmp, "etbin"))
    calls = os.path.join(state, "engine_calls")
    n_before = len(open(calls).read().splitlines()) if os.path.exists(calls) else 0
    print("--- campaign ET (executorch-xnnpack: the S26 smoke replayed through run_campaign -> run_cell)")
    rc = run_campaign(env_et, cells_et)
    ok(rc == 0, f"campaign ET exits 0 (got {rc})")
    out_et = os.path.join(raw_root, "selftest-et", "app-path-android")
    recs_et = records(out_et, "executorch-xnnpack_")
    ok(len(recs_et) == 2, f"2 executorch records (got {len(recs_et)})")
    by_task = {r["task"]: r for _, r in recs_et}
    if len(by_task) == 2:
        rs, rl = by_task["short-chat"], by_task["long-context-1024-gen256"]
        label = parsers.EXECUTORCH_RECIPES[alias]["label"]
        ok(all(r["runtime"] == "executorch-xnnpack" and r["engineVersion"] == "v1.5.1"
               and r["engineArtifact"] == pinned["llama_main_sha256"] and r["model"]["quantization"] == label
               and r["model"]["hfRevision"] == rev for r in (rs, rl)),
           "record: arm executorch-xnnpack, the observed runner stamped v1.5.1 by its pinned sha, "
           "model.quantization = the recipe alias's label, hfRevision from the recipe.json")
        ok(round(rs["metrics"]["decodeTokensPerSecond"], 2) == 124.51 and rs["metrics"]["promptTokenCount"] == 19
           and rs["metrics"]["firstTokenLatencyMS"] == 57 and round(rl["metrics"]["decodeTokensPerSecond"], 2) == 31.17
           and rl["metrics"]["promptTokenCount"] == 1338 and rs["metrics"]["coldRun"] is True
           and rs["metrics"]["harnessStamp"] == "2026-08-android-cli-v1+executorch-runner-stats",
           f"metrics recomputed from the replayed stats lines (got {rs['metrics']} / {rl['metrics']})")
        ok(rs["metrics"]["memoryPeakResidentMB"] == 1031.214844 == rs["metrics"]["memoryPeakEngineReportedMB"]
           and "RSS after finishing text generation" in rs["provenance"]["rssBasis"],
           f"memoryPeakResidentMB = the runner's own ru_maxrss when the sampler's VmHWM reads are lower "
           f"(fake 625 MiB < 1031.2) (got {rs['metrics'].get('memoryPeakResidentMB')})")
        ok(all(r["conditions"].get("contextTokens") == r["conditions"].get("contextBudget") == 2048
               and r["conditions"]["contextSource"] == "runner log (Metadata: get_max_context_len)"
               and r["conditions"]["cpuThreads"] == 8 and r["conditions"]["sampler"] == parsers.EXECUTORCH_SAMPLER
               and r["conditions"]["warm"] is False and r["conditions"]["executorchRunner"] == "llama_main"
               for r in (rs, rl)),
           "conditions: the allocation the runner logged (2048), its thread pool (8), greedy, cold")
        ok(all(r["conditions"]["textCheck"]["status"] == "PASS" and not r["conditions"].get("protocolFlags")
               and r["outputSample"].startswith("<think>") for r in (rs, rl))
           and open(os.path.join(out_et, rs["provenance"]["decodedText"])).read() == short["text"],
           "the runner's text is checked (PASS), stored beside the record, its head in outputSample")
        ok(rs["provenance"]["definitions"] == parsers.EXECUTORCH_DEFINITIONS["llama_main"]
           and rs["provenance"]["statsLine"].startswith('PyTorchObserver {"prefill_token_per_sec":333.333')
           and rs["provenance"]["promptSha256"] == manifest["tasks"]["short-chat"]["renderedSha256"]
           and rs["provenance"]["recipe"] == stem + ".recipe.json",
           "provenance: the definitions verbatim, the stats line verbatim, the rendered prompt's sha256, the recipe")
        log = open(os.path.join(out_et, rs["provenance"]["rawLog"])).read()
        ok("===ENGINE_STDERR===" in log and "RSS after finishing text generation" in log.split("===ENGINE_STDERR===")[1]
           and "RSS after" not in log.split("===ENGINE_STDERR===")[0],
           "the stored log keeps the runner's stderr after ===ENGINE_STDERR===, apart from its stdout")
        ok(rl["conditions"]["engineCommand"].startswith("sh -c 'exec ./executorch-v1.5.1/llama_main --model_path=")
           and "--temperature=0 --max_new_tokens=256 2>/data/local/tmp/llmbench/run_err.txt'" in rl["conditions"]["engineCommand"],
           f"the 1K launch's command: the runner through sh -c, its stderr to its own file "
           f"(got {rl['conditions']['engineCommand'][:120]!r})")
    model_dev = os.path.join(dev, "models", f"own-export_{stem}_{stem}")
    ok(open(model_dev + ".short-chat.prompt.txt").read() == rd("short-chat.qwen3-chat.txt")
       and os.path.exists(model_dev + ".tokenizer.json") and not os.path.exists(os.path.join(dev, "run_err.txt")),
       "the rendered prompt and the tokenizer were pushed beside the .pte; the stderr file was read and removed")
    # refusals before any launch: a recipe= the recipe.json contradicts, a runner not on the phone
    with open(cells_et, "w") as fh:
        fh.write(f"android executorch own-export/{stem} short-chat backend=xnnpack local=1 file={stem}.pte "
                 f"recipe=et1.5.1-gemma4-xnnpack-8da4w-g128-emb8 runs=1\n")
    rc_recipe = run_campaign(dict(env_et, CAMPAIGN="selftest-et-recipe"), cells_et)
    os.remove(os.path.join(dev, "executorch-v1.5.1", "llama_main"))
    with open(cells_et, "w") as fh:
        fh.write(f"android executorch own-export/{stem} short-chat backend=xnnpack local=1 file={stem}.pte "
                 f"recipe={alias} runs=1\n")
    p = subprocess.run([sys.executable, os.path.join(ROOT, "android", "bench", "run_cell.py"), "--runtime", "executorch",
                        "--backend", "xnnpack", "--model-id", f"own-export/{stem}", "--file", f"{stem}.pte",
                        "--recipe", alias, "--task", "short-chat", "--runs", "1",
                        "--out", os.path.join(tmp, "et-nobinary")], env=env_et, capture_output=True, text=True)
    n_after = len(open(calls).read().splitlines()) if os.path.exists(calls) else 0
    ok(rc_recipe == 0 and n_after - n_before == 2
       and "FAILURES.txt" in os.listdir(os.path.join(raw_root, "selftest-et-recipe", "app-path-android"))
       and p.returncode != 0 and "is not on the device" in p.stderr
       and "etbin/executorch-v1.5.1 /data/local/tmp/llmbench/" in p.stderr,
       f"a recipe= the recipe.json contradicts and a runner missing on the phone stop before any launch "
       f"(engine shells {n_after - n_before}, {p.stderr.strip()[-120:]!r})")
    p = subprocess.run([sys.executable, os.path.join(ROOT, "android", "bench", "run_cell.py"), "--runtime", "executorch",
                        "--backend", "xnnpack", "--model-id", f"own-export/{stem}", "--file", f"{stem}.pte",
                        "--recipe", alias, "--task", "long-context-1024-gen256", "--out", os.path.join(tmp, "unused"),
                        "--dry-run"], env=dict(env_et, BENCH_CPU_MASK=""), capture_output=True, text=True)
    plan = json.loads(p.stdout) if p.returncode == 0 else {}
    ok(plan.get("command", "").startswith("cd /data/local/tmp/llmbench && LD_LIBRARY_PATH=. sh -c 'exec "
                                          "./executorch-v1.5.1/llama_main --model_path=/data/local/tmp/llmbench/models/")
       and plan.get("contextTokens") == 2048 and len(plan.get("pushes", [])) == 3
       and not os.path.exists(os.path.join(tmp, "unused")),
       f"run_cell --dry-run prints the on-device command and the inputs it would push, with no device call "
       f"(got {p.returncode} {p.stdout[:100]!r} {p.stderr[-200:]!r})")
    # the summary row of an executorch record, and its pool (build_summary, arm_row)
    with patch.object(build_summary, "ROOT", raw_root.rsplit(os.sep + "raw", 1)[0]), \
         patch.object(build_summary, "OUT", os.path.join(tmp, "summary-et")), \
         patch.object(build_summary, "iter_device_records",
                      lambda: [(f, r) for f, r in recs_et]):
        os.makedirs(build_summary.OUT, exist_ok=True)
        path, _ = build_summary.build_device()
    rows_et = list(csv.DictReader(open(path)))
    got = sorted((r["runtime"], r["task"], r["context_tokens"], r["text_check"], r["prompt_tokens"],
                  r["mem_resident_peak_mb"], r["quantization"] == label) for r in rows_et)
    ok(got == [("executorch-xnnpack", "long-context-1024-gen256", "2048", "PASS", "1338", "1034.859375", True),
               ("executorch-xnnpack", "short-chat", "2048", "PASS", "19", "1031.214844", True)]
       and arm_row([r for r in rows_et if r["task"] == "short-chat"])["cold_n"] == 1,
       f"summary rows: arm, allocation, text check, prompt count, peak, label; arm_row pools the cold run (got {got})")
    # the Mac writer builds the same keys from a stored launch (the r1 cold short-chat stdout)
    import executorch_mac
    from types import SimpleNamespace
    inputs = parsers.executorch_inputs(et_models, f"{stem}.pte", "short-chat", alias, ROOT)
    host = {"loadAverage": [2.0, 2.0, 2.0], "cpuSpeedLimit": None, "others": [], "thermal": "nominal"}
    mac = executorch_mac.build_record(
        SimpleNamespace(model_id=f"own-export/{stem}", backend="xnnpack", task="short-chat", context_tokens=None,
                        campaign_dir=os.path.join(tmp, "mac")),
        inputs, 1, True, rd("mac-short-chat-cold-1.stdout.txt"), "", 0, 1256194048, 1.619, host, host,
        {"systemName": "macOS", "modelIdentifier": "Mac16,9"}, ["llama_main"], "61e7e881a4e3e12d38e3d102e01e15119b33395c164229fa21ab351b6a174e0e",
        {k: os.path.join(tmp, "mac", f"x.{k}") for k in ("stdout", "stderr", "log")})
    unchecked = executorch_mac.validate(mac)
    ok(mac["runtime"] == "executorch-xnnpack" and mac["status"] == "ok" and mac["engineVersion"] == "v1.5.1"
       and round(mac["metrics"]["decodeTokensPerSecond"], 2) == 110.63 and mac["metrics"]["memoryPeakResidentMB"] == 1198.0
       and mac["metrics"]["coldRun"] is True and mac["conditions"]["warm"] is False
       and mac["conditions"]["contextTokens"] == 2048 and mac["conditions"]["textCheck"]["status"] == "PASS"
       and mac["provenance"]["definitions"] == parsers.EXECUTORCH_DEFINITIONS["llama_main"],
       f"Mac writer: the r1 cold launch's record (decode 110.63, ru_maxrss 1198.0 MiB, v1.5.1 by the "
       f"lock's sha; schema {'validated' if not unchecked else 'not checked here: ' + unchecked})")

    rc = subprocess.call([sys.executable, os.path.join(ROOT, "android", "bench", "test_longctx.py")])
    ok(rc == 0, "long-context device-free unit checks")
    if _fails:
        print(f"\n{len(_fails)} failure(s); temp dir kept: {tmp}")
        return 1
    shutil.rmtree(tmp)
    print("\nselftest OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
