# System profile (Instruments / xctrace, on the phone) — iPhone 17 Pro, 2026-09-13 08:3x–08:4x JST

Bundle: `litert-community/Qwen3-0.6B` (the mixed_int4 file); the harness's iPhone
app (`com.example.CoreMLLLMChat`, BenchmarkApp, display name "iOS LLM Bench")
launched headless by `xcrun devicectl device process launch ... --yardstick-autorun`
with the engine's own benchmark (`--litert-native-benchmark 128x1024
--context-tokens 2048`), LiteRT-LM v0.16.0 vendored; iOS 27.0; Xcode 27.0. The
recorder runs on the Mac and attaches over USB (`xctrace record --device <udid>
--attach <pid>`, pid from `devicectl device info processes`); it ends itself when
the app exits. One run per row, 20 s apart; the app prints the record to the
console (`YARDSTICK_NATIVE_OK ...`) — the stored `.log` files.

## Rates (the traced rows are never speed rows)

| row | file | init s | decode tok/s |
|---|---|---:|---:|
| control | `qwen3-0.6b_128x1024_ctx2048_ctrl.log` | 9.81 | 106.1 |
| Metal System Trace attached | `..._mst.log`, summary `..._mst_gpu-intervals.txt` | 1.58 | 102.4 |
| Time Profiler attached | `..._tp.log`, summary `..._tp_time-profile.txt` | 2.37 | 109.8 |

The control was the first launch after an idle hour (init 9.8 s; the two later
launches 1.6–2.4 s), so its rate is the cold one; the traced rows sit within
±4 % of it and 7 % of each other — one run each, the ordinary spread of this
phone, not a tracing cost that can be read off three runs. The `.trace` bundles
were deleted after the exports (a bundle stores the process environment).

## GPU (Metal System Trace, `metal-gpu-intervals`)

Over the 8.48 s the recorder saw (about 870 of the 1024 tokens): 7,614 Compute
intervals from the app covering 91.8 % of that window; the other rows are
backboardd (196 intervals, 0.2 %) and a widget. Gaps between the app's
intervals: 55 µs median, 2.0 ms at p90, 25 ms at most — wider than the Mac's
(1 µs / 16 µs / 1.8 ms) on the same bundle and shape. About 9 intervals per
decoded token. Occupancy is command-buffer time on the GPU timeline, not
shader-core utilisation (no GPU counters recorded).

## CPU (Time Profiler, `time-profile`, 1 ms samples, the app only)

8,906 samples; 96 % on one thread (`execution_thread`).

| self % | symbol [binary] |
|---:|---|
| 92.4 | `litert::ml_drift::GpuBackendMetal::WaitForCompletion()` [CLiteRTLM] |
| 1.7 | an unsymbolicated kernel entry [libsystem_kernel.dylib] |
| 1.7 | `AGX::*` encoder / compute-context calls [AGXMetalG18P, the Metal driver] |
| 0.7 | `IOKit` |

Reading: on the phone the engine's Metal backend (`ml_drift`, not the WebGPU
path the Mac build uses) spends the CPU side inside `WaitForCompletion` —
the execution thread is on-CPU waiting for the GPU, so the CPU tables carry no
model math and no submission cost to speak of; the decode is bounded by the
GPU intervals and the gaps between them. One bundle, one phone, one version:
an input to a re-test, not a property of the runtime.
