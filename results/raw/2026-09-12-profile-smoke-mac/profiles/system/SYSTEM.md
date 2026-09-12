# System profile (Instruments / xctrace) — Mac Studio M4 Max, 2026-09-12 19:58–19:59 JST

Bundle: `litert-community/Qwen3-0.6B` (the mixed_int4 file); the harness's Mac
runner `yardstick` (`.build/dd-mac/Build/Products/Release/yardstick`, flavor=full)
with LiteRT-LM v0.16.0 vendored, running the engine's own benchmark through the
C API (`--litert-native-benchmark 128x1024 --context-tokens 2048`, decode on the
WebGPU/Metal backend); macOS 27.0, Xcode 27.0 (`xctrace version 27.0 (27A5237l)`);
one run per row, 20 s between runs, host load average 3.5–6 across the session
(a browser tab at ~150 % CPU that we do not control). 128x1024 is the shape of
every row below: at 128x256 the run is over before the recorder is on — tried
once at the end (`qwen3-0.6b_128x256_ctx1024_attachtest.*`, 296.5 tok/s), and
the trace held no row from `yardstick`, only 32 WindowServer intervals.

`xctrace record --launch` was tried first (Metal System Trace and Time Profiler,
09-12 19:41–19:53): the launched `yardstick` printed its first line and never
loaded the model, sat idle until the time limit and was SIGKILLed; the trace
held no GPU work from it. Not a missing environment (`env -i` runs fine).
`--attach <pid>` to a `yardstick` started from the shell records normally and
ends itself when the process exits ("Target app exited, ending recording").

## Rates (the traced rows are never speed rows)

| row | file | decode tok/s |
|---|---|---:|
| control | `qwen3-0.6b_128x1024_ctx2048_ctrl.jsonl` / `.log` | 299.6 |
| Metal System Trace attached | `..._mst.jsonl` / `.log`, summary `..._mst_gpu-intervals.txt` | 299.3 |
| Time Profiler attached | `..._tp.jsonl` / `.log`, summary `..._tp_time-profile.txt` | 297.1 |

Attaching either template moved the decode rate by under 1 %. The `.trace`
bundles (125 MB and 17 MB) and the exported tables (`*.xml`) stay local
(gitignored); the two `.txt` summaries are the stored reading.

## GPU (Metal System Trace, `metal-gpu-intervals` table)

Over the 2.49 s the recorder saw of the decode (about 745 of the 1024 tokens):
9,022 intervals on the Compute channel from `yardstick` (the only other rows are
300 WindowServer intervals and 15 from an unnamed process), covering 99.7 % of
that window (union of the intervals, so overlaps count once); the gaps between
consecutive intervals are 1 µs at the median, 16 µs at p90, 1.8 ms at most.
About 12 GPU intervals per decoded token. "Occupancy" here is command-buffer
time on the GPU timeline, not shader-core utilisation — the trace was recorded
without GPU counters.

## CPU (Time Profiler, `time-profile` table, 1 ms samples, `yardstick` only)

3,183 samples over the window; 80 % on one thread (`execution_thread`), 4–5 %
each on two workers, the main thread 0.1 %.

| self % | binary / symbol |
|---:|---|
| 38.9 | `libCLiteRTLM_mac.dylib` — `dawn::RefCounted::*`, `dawn::native::ExecutionQueueBase::UpdateCompletedSerial*`, `dawn::native::EventManager::ProcessPollEvents`, `DeviceMutex::Lock`, mutex stubs |
| 22.4 | `libsystem_pthread.dylib` — `pthread_mutex_lock` 9.0, `pthread_mutex_unlock` 6.0, `pthread_cond_broadcast` 1.8 |
| 7.8 | `libsystem_kernel.dylib` — `mach_absolute_time` 3.7, `mach_msg2_trap` |
| 7.0 | unsymbolicated (`0x1a3bc40dd`, `0x1a3bc40fd`) |
| 6.6 | `libsystem_malloc.dylib` |
| 5.4 | `IOKit` — `iokit_user_client_trap` (the GPU submission path) |
| 3.0 | `AGXMetalG16X` (the Metal driver) |

Reading: with the GPU timeline full and the CPU side made of WebGPU (Dawn)
bookkeeping, locking and submission rather than model math, this capture is a
GPU-bound decode; a change that shortens the GPU intervals would move the rate,
a change on the CPU side would not. `yardstick` frames are our harness's, not
the engine's; the same `xctrace` recipe applies to any LiteRT-LM host process.
One bundle, one machine, one version: inputs to a re-test, not properties of
the runtime.
