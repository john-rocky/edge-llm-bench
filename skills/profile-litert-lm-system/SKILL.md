---
name: profile-litert-lm-system
description: Profile a LiteRT-LM benchmark run at the system level - Android simpleperf on a phone, Instruments (xcrun xctrace, Metal System Trace and Time Profiler) on a Mac - paired with an unprofiled control, stored beside the run, and read as top symbols and shared objects, the thread split, and GPU-timeline occupancy. Use when the per-op profile (./bench profile) leaves the question open - time outside the profiled ops, thread-pool behaviour, what the CPU does while the GPU decodes, whether the GPU timeline is full - or when a decode-rate change has no matching change in any op.
---

# Profile a LiteRT-LM run at the system level

A system profile is done when three things hold, in this order:

1. it has a **control**: the byte-identical command without the profiler, in the
   same sitting, both rates written down (a profiled rate is never a speed row),
2. the **reading is stored as text** beside the run - top symbols and shared
   objects, the thread split, GPU occupancy - under `profiles/system/`; the
   `.trace` bundle, `perf.data` and exported tables stay local,
3. every number is tied to **one bundle, one device, one engine version** and
   read as an input to a re-test, never as a property of the runtime.

Vocabulary: the **per-op profile** is the engine's own `--enable_profiling`
table (`./bench profile`, `docs/profiling-subcommand-design.md`); its column
"unprof." is the part of the decode step's wall time that no profiled op covers
- a pointer to look wider, not a quantity of work. **System profiling** samples
the process from outside: which code on which thread, and on Apple the GPU timeline.

## When it is the right tool

- "unprof." is a large share of the step, or the op table sums above the wall;
  the rate moved between builds and the op table did not (pool, driver,
  allocator, sampler); a GPU backend, where the op table shows launches, not
  what the CPU does between them or whether the GPU sits idle.
- Otherwise `./bench profile` answers faster and costs no symbolisation.

## Loop

**0. Preflight.** The bundle and engine are on the device (`./bench doctor`), the
phone is yours (no foreign `litert_lm` process, no other driver), thermal status
nominal, a Mac host not running a heavy pipeline. Two phones attached:
plain `adb` refuses (`more than one device/emulator`) until
`export ANDROID_SERIAL=<serial>` (`./bench` also reads `BENCH_ANDROID_SERIAL`).
`simpleperf` ships in Android (`/system/bin/simpleperf`); the `shell` user gets
user-space samples only (`-e cpu-clock:u`; kernel and driver time is invisible).
The release `litert_lm_advanced_main` carries symbols, `libLiteRtGpuAccelerator.so`
is stripped (offsets). Instruments comes with Xcode (`xcrun xctrace`).

**1. Control.** The exact engine command the harness runs for the cell, once, no
profiler (`taskset f0` is the Pixel 8a's mask here; the thread reading holds under it only):

```bash
adb shell "cd /data/local/tmp/llmbench && LD_LIBRARY_PATH=. taskset f0 ./litert_lm_advanced_main --backend=cpu --model_path=/data/local/tmp/llmbench/models/litert-community_Qwen3-0.6B_qwen3_0_6b_mixed_int4.litertlm --benchmark --benchmark_prefill_tokens=128 --benchmark_decode_tokens=256 --async=false --max_num_tokens=1024"
```

**2. Android: sample the whole process, then attach during decode.** The first
form covers load and prefill too and costs the CPU-backend rate 13 % at 1000 Hz;
the second waits for the engine's end-of-prefill line (`tasks.cc:490 Failed to
get prefill profile summary`, both backends, printed when profiling is off) and
samples 8 s of decode for 2-9 % - never a fixed sleep: load took 7 s for a 0.5 GB
bundle and 32 s for a 2.6 GB one on the same phone. Frame-pointer stacks are flat
on this binary (use `dwarf` for callers). First `adb shell pgrep -l litert_lm` must print nothing:

```bash
adb shell "cd /data/local/tmp/llmbench && LD_LIBRARY_PATH=. simpleperf record -o /data/local/tmp/llmbench/perf_cpu.data -e cpu-clock:u -f 1000 --call-graph fp -- taskset f0 ./litert_lm_advanced_main --backend=cpu --model_path=/data/local/tmp/llmbench/models/litert-community_Qwen3-0.6B_qwen3_0_6b_mixed_int4.litertlm --benchmark --benchmark_prefill_tokens=128 --benchmark_decode_tokens=256 --async=false --max_num_tokens=1024"
adb shell "cd /data/local/tmp/llmbench && rm -f /data/local/tmp/llmbench/run_out.txt && LD_LIBRARY_PATH=. taskset f0 ./litert_lm_advanced_main --backend=gpu --model_path=/data/local/tmp/llmbench/models/litert-community_Qwen3-0.6B_qwen3_0_6b_mixed_int4.litertlm --benchmark --benchmark_prefill_tokens=128 --benchmark_decode_tokens=256 --async=false --max_num_tokens=1024 >/data/local/tmp/llmbench/run_out.txt 2>&1 </dev/null & until grep -q 'prefill profile summary' /data/local/tmp/llmbench/run_out.txt 2>/dev/null; do sleep 0.5; done; simpleperf record -o /data/local/tmp/llmbench/perf_gpu_decode_dwarf.data -e cpu-clock:u -f 1000 --call-graph dwarf -p \$(pgrep -n -f litert_lm_advanced_main) --duration 8; wait; cat /data/local/tmp/llmbench/run_out.txt"
```

`--backend=cpu` takes the same commands. Read on the device:

```bash
adb shell "simpleperf report -i /data/local/tmp/llmbench/perf_cpu.data --sort dso,symbol -n --percent-limit 0.5"
adb shell "simpleperf report -i /data/local/tmp/llmbench/perf_cpu.data --sort comm,tid -n"
adb shell "simpleperf report -i /data/local/tmp/llmbench/perf_gpu_decode_dwarf.data --sort dso,symbol -n --percent-limit 0.5"
adb shell "simpleperf report -i /data/local/tmp/llmbench/perf_cpu_decode_dwarf.data -g caller --sort symbol --percent-limit 8"
```

**3. Mac: attach Instruments to the harness's runner.** `xctrace record
--launch` hung the runner before the model loaded (both templates); `--attach`
records normally and stops when the process exits. Use a decode long enough to
attach to (128x1024 here; 128x256 is over before the recorder is on):

```bash
YS=.build/dd-mac/Build/Products/Release/yardstick
OUT=results/raw/2026-09-12-profile-smoke-mac/profiles/system
$YS run --runtime litert-lm --model-id litert-community/Qwen3-0.6B --task short-chat --runs 1 --litert-native-benchmark 128x1024 --context-tokens 2048 --output $OUT/qwen3-0.6b_128x1024_ctx2048_ctrl.jsonl > $OUT/qwen3-0.6b_128x1024_ctx2048_ctrl.log 2>&1
$YS run --runtime litert-lm --model-id litert-community/Qwen3-0.6B --task short-chat --runs 1 --litert-native-benchmark 128x1024 --context-tokens 2048 --output $OUT/qwen3-0.6b_128x1024_ctx2048_mst.jsonl > $OUT/qwen3-0.6b_128x1024_ctx2048_mst.log 2>&1 &
xcrun xctrace record --template 'Metal System Trace' --time-limit 30s --output $OUT/qwen3-0.6b_128x1024_ctx2048_mst.trace --attach $!
xcrun xctrace export --input $OUT/qwen3-0.6b_128x1024_ctx2048_mst.trace --xpath '/trace-toc/run[@number="1"]/data/table[@schema="metal-gpu-intervals"]' --output $OUT/qwen3-0.6b_128x1024_ctx2048_mst_metal-gpu-intervals.xml
python3 scripts/profile/xctrace_tables.py gpu $OUT/qwen3-0.6b_128x1024_ctx2048_mst_metal-gpu-intervals.xml --process yardstick | tee $OUT/qwen3-0.6b_128x1024_ctx2048_mst_gpu-intervals.txt
```

The Time Profiler twin: `--template 'Time Profiler'`, export
`table[@schema="time-profile"]`, summarise with `xctrace_tables.py cpu`. The
`.trace` bundle stores the traced process's whole environment and `xctrace
export --toc` prints it, API keys included: never store `--toc` output, export
tables by `--xpath` only, delete the bundle once the summaries are written.
`xctrace_tables.py gpu` prints intervals / busy / window / occupancy per process
and channel (gaps too when `--process` names one); `cpu` self time per binary,
leaf symbol and thread (`--top 40` here).

**3b. iPhone: the same, through the app.** Launch the harness app headless with
`devicectl`, attach by pid with `--device`; the trace names the process by its
display name, so export and summarise as on the Mac with `--process 'iOS LLM Bench'`:

```bash
DEV=<devicectl id>; XDEV=<xctrace udid>; APP=<the harness app's bundle id, see scripts/bench_matrix_iphone.sh>
OUT=results/raw/2026-09-13-profile-smoke-ios/profiles/system
gtimeout --kill-after=30 600 xcrun devicectl device process launch --console --terminate-existing --device $DEV $APP -- --yardstick-autorun --runtime litert-lm --model-id litert-community/Qwen3-0.6B --task short-chat --runs 1 --litert-native-benchmark 128x1024 --context-tokens 2048 > $OUT/qwen3-0.6b_128x1024_ctx2048_mst.log 2>&1 &
PID=$(xcrun devicectl device info processes --device $DEV | grep BenchmarkApp.app/BenchmarkApp | awk '{print $1}')
xcrun xctrace record --template 'Metal System Trace' --device $XDEV --time-limit 45s --output $OUT/qwen3-0.6b_128x1024_ctx2048_mst.trace --attach $PID
```

**4. Read.** Four questions, in order:

- *What code?* Top self symbols and their shared objects. On the CPU backend
  today: the M=1 int4 GEMM kernel 36 %, the thread-pool worker loop itself
  31 % (waiting, not computing), a weight-packing kernel 7 % inside the decode
  step, `memmove` 7 %. On the GPU backend: 38 % in the (stripped) GPU
  accelerator library, 33 % in the vendor OpenCL driver setting kernel arguments,
  20 % libc mutex and malloc - submission, not math.
- *Which threads?* `--sort comm,tid`: three pool threads and the calling main
  thread at 23-26 % each on the CPU backend; 94 % on one thread plus the
  driver's event thread on the GPU backend. Samples over window x threads x
  rate = the user-space share (65 % and 69 % here); the remainder is kernel or
  waiting, and this tool cannot see it.
- *Who calls it?* The dwarf caller tree: pool worker → `xnn_compute_qp8gemm` →
  the kernel; pool worker → `xnn_compute_batched_packw_gemm_goi` → the packer.
- *Is the GPU busy?* (Mac, iPhone) Compute-channel occupancy over the process's
  own window: 99.7 % on the Mac with 1 µs median gaps and the CPU side in WebGPU
  bookkeeping and locking; 91.8 % on the iPhone with 55 µs gaps and 92 % of the
  CPU samples in the Metal backend's `WaitForCompletion` - GPU-bound both ways.

What a reading points at, as candidates to test on-device, never conclusions: a
large pool-spin share → thread count / core mask; a packing kernel per step →
weight layout at load; a driver-heavy CPU side with an idle GPU → launch count and
batching (the per-op table's launches per step); a full GPU timeline → the kernels themselves, which needs the GPU's own counters, not this skill.

**5. Store.** The control record (a native benchmark's record is one
`YARDSTICK_NATIVE_OK ...` text line, not JSON), the profiled logs, the report `.txt`
files and a `SYSTEM.md` with the rates and the reading, under `results/raw/<campaign>/profiles/system/`
- outside every summary glob, so no profiled rate becomes a speed row.

## Symptoms

| What you see | What it is, what to do |
|---|---|
| `Can't record kernel samples. Please try -e cpu-clock:u` | no kernel access for the `shell` user; use `:u` and say so in the reading |
| `Children` equals `Self` for every symbol in `-g` output | frame-pointer unwinding found no callers on this binary; record with `--call-graph dwarf` |
| `libLiteRtGpuAccelerator.so[+105788]` instead of a name | the release `.so` is stripped; attribution stays at the library level |
| `xctrace record --launch` reaches the time limit, process `SIGKILL`, no GPU rows from it | the launched runner never loaded the model; start it from the shell and `--attach` |
| simpleperf `Samples recorded: 0` from an attached capture | attached before decode (a fixed sleep on a bigger bundle); wait for the end-of-prefill line as in step 2 |
| `--attach` trace holds nothing from the process (only WindowServer rows) | the run ended before the recorder started - seen at 128x256 here; lengthen the decode (`128x1024`) |
| `yardstick: WARNING native benchmark context_tokens=288` and fewer decode tokens than asked | pass `--context-tokens`; the stock default truncates the decode |
| the profiled rate is far below the control | the profiler's own cost (whole-process 1000 Hz on the CPU backend: 13 % here); the control's rate is the number, the profile is the shape |

## Watch for

- **The control is the same command line**, run in the same sitting; a rate
  from a different shape or day is not a control. **Whole-process samples
  include load, cache build and prefill**; attach after load for decode.
- **User-space only on Android**: kernel, driver and off-CPU time are absent;
  a "top symbol" table cannot point there. **GPU occupancy is timeline
  occupancy**, not shader utilisation (no GPU counters recorded).
- **Thermal and drift**: nominal at start, cooldown between rows, one device
  per driver. **The traced Apple process is our runner / app**, so its frames
  are ours; the same recipe applies to any LiteRT-LM host or iOS process.

## Output layout

```
results/raw/<campaign>-android/profiles/system/<tag>_<backend>_ctrl.log  <tag>_<backend>_simpleperf{,-attach,-attach-dwarf}.log  *-report.txt  SYSTEM.md  session_provenance.txt
results/raw/<campaign>-{mac,ios}/profiles/system/<tag>_{ctrl,mst,tp}.log (+ .jsonl on the Mac)  <tag>_mst_gpu-intervals.txt  <tag>_tp_time-profile.txt  SYSTEM.md  session_provenance.txt
local only (gitignored): *.trace/  perf*.data  *.xml
```

Tested on: Pixel 8a (Android 16, LiteRT-LM v0.16.0 pinned binary, cpu and gpu,
simpleperf 1.build.15081906), Mac Studio M4 Max (macOS 27, Xcode 27.0, v0.16.0
vendored) and iPhone 17 Pro (iOS 27, the signed harness app, Instruments over
USB), 2026-09-12/13, Qwen3-0.6B; re-run from this text alone by a second agent
on Gemma 4 E2B on the phone and the Mac (`results/raw/2026-09-12-blind-test-profile-*`).
[LiteRT-LM](https://github.com/google-ai-edge/LiteRT-LM) on [LiteRT](https://github.com/google-ai-edge/litert).
