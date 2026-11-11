# LiteRT-LM v0.19.0 on Windows: notes from building and running it

Machine: MSI Stealth 16 AI+ (Core Ultra 9 386H, RTX 5080 Laptop, Intel AI Boost), Windows 11, tag v0.19.0 (83ce6067f),
Gemma 4 E2B. The benchmark rows run through this repo ([README.md](README.md)), and their records are in
[`results/raw/2026-11-05-windows`](../results/raw/2026-11-05-windows). The thread, affinity, wheel and
graphics-preference runs were one-off, not schema records; their logs and commands are in
[`results/raw/2026-11-05-windows-ladder`](../results/raw/2026-11-05-windows-ladder), and the logs behind item 4's table
are in [`results/raw/2026-11-11-windows-threads-qos`](../results/raw/2026-11-11-windows-threads-qos).

1. **The build stops on a Japanese Windows.** MSVC reads the BOM-less UTF-8 sources in code page 932, and
   `stablehlo_reduce_window.cc` fails with `C4430`. `--copt=/utf-8 --host_copt=/utf-8` fixes it; `.bazelrc` has neither.
   A string literal elsewhere could change with no error, so the flag belongs on every action.

2. **The build doc's DirectX note points nowhere.** `docs/getting-started/build-and-run.md` says the GPU needs
   DirectXShaderCompiler and links to `README.md#windows_gpu`, which the README at v0.19.0 does not have. With neither DLL
   beside the tool, Dawn's D3D12 backend stops at `DynamicLib.Open: dxcompiler.dll Windows Error: 87`.
   `prebuilt/windows_x86_64` has neither. Copying `dxcompiler.dll` and `dxil.dll` from the PyPI wheel `litert-lm-api` 0.19.0
   made the GPU run.

3. **`--preferred_device_substr=Intel` leaves the WebGPU path on the NVIDIA GPU, with no message.** The log echoes the
   value and it reaches the delegate's options, but nothing on the WebGPU path reads it in the litert source this tag pins
   (`dcb657e8a`). The environment is created with `use_low_power` from the GPU priority (the log says `use_low_power=0`),
   and ml_drift's `webgpu/environment.cc` asks Dawn by that power preference. Windows' per-app graphics preference (the
   registry value `GpuPreference=1;` under `UserGpuPreferences`) does move it to `Intel(R) Graphics`. This was tried with
   one value on Direct3D 12 only. The low-priority setting (`gpu_context_low_priority`, which the tool has no flag for) has
   not been tried.

4. **With High QoS on, no thread count tried on this hybrid CPU was as much as 3 % faster for decode than the tool's
   default of 4.** Measured in one sitting on 2026-11-11 (12:56 to 13:11 JST) through the benchmark job, which set High
   QoS (the level Windows gives an app in the foreground and in focus) on each engine process
   ([README.md](README.md), Setup and Run), with MSI Center's scenario reading Balanced before and after it. With
   `gemma-4-E2B-it.litertlm`, a 20-token prompt and 128 tokens out, each run a fresh process with two conversations,
   three runs per count, one in each of three rounds with the counts in a different order, after one uncounted warm-up
   run. Rates in tok/s, the median of the three runs with the lowest and highest in brackets:

   | threads | decode, first conversation | prefill, first conversation | prefill, second conversation |
   |---|---|---|---|
   | 1 | 15.29 (15.12 to 15.29) | 20.64 (20.57 to 20.67) | 23.07 (23.05 to 23.08) |
   | 2 | 25.92 (25.80 to 26.10) | 36.12 (35.84 to 36.65) | 43.71 (43.62 to 44.18) |
   | 3 | 29.70 (29.59 to 29.80) | 45.92 (45.87 to 46.88) | 58.28 (55.07 to 58.41) |
   | 4 (the tool's default) | 29.20 (29.06 to 29.30) | 53.05 (52.60 to 53.56) | 68.23 (67.63 to 68.92) |
   | 6 | 26.20 (26.10 to 26.28) | 58.97 (58.70 to 59.62) | 85.30 (85.30 to 86.07) |

   All three runs at 3 threads decoded above all three at 4, by 1.7 % at the median. The rule set before the sitting
   calls a count faster only when its median is at least 3 % above the default's
   ([the folder's README](../results/raw/2026-11-11-windows-threads-qos/README.md), last paragraph), so it does not rank
   the two. 1, 2 and 6 threads decoded slower than 4. In both conversations every run at 6 threads, the largest count
   tried, prefilled above every run at the other counts.

   The rest of this item was measured on 2026-11-05, before the job set High QoS (from commit 1289e714, 2026-11-09), by
   a hand-written script unless said otherwise. The counts above 6 and the runs pinned to the P cores have not been
   measured again, and these numbers compare only with each other. With the same file and flags, two or three runs per
   count, a fresh process's first conversation decoded at 19.45 to 20.24 tok/s at 4 threads, 17.48 to 17.66 at 6, 12.03
   to 12.06 at 8, 8.89 to 8.93 at 12 and 6.30 to 6.84 at 16, and the second conversation's prefill peaked at 6. Later
   that evening 2 threads gave 22.54 to 23.30 and 3 threads 21.93 to 22.47, against 20.48 to 21.00 at 4 in the eight
   runs that followed (six of them the benchmark rows', which the job started, then without High QoS; their records are
   in [`results/raw/2026-11-05-windows-s1`](../results/raw/2026-11-05-windows-s1) and
   [`results/raw/2026-11-05-windows`](../results/raw/2026-11-05-windows)); the 2026-11-11 sitting did not keep that
   order: there 2 threads decoded below 4. At 21:55 to 21:58, pinned to the four P cores (process affinity mask `F`;
   logical processors 0 to 3 are the higher efficiency class in `GetSystemCpuSetInformation`), the means of two runs
   were 25.4 at 2 threads, 25.9 at 3 and 24.0 at 4, against 21.0 unpinned at 4. The pin at 4 threads took the second
   conversation's prefill from 59.9 to 69.0 and left the first prefill where it was (50.0 and 49.3), means of the same
   runs.

   The two sets of runs differ in more than High QoS: among other things in what started them (a hand-written script
   for most of the 2026-11-05 runs, the job for all of the 2026-11-11 ones), in the order and number of runs, in the
   time of day, and in a Windows update between them. What moved the numbers is not established.

5. **`--backend=npu` on a file with no compiled graphs runs on the CPU and exits 0.** The log says
   `No compiler plugin found`, then creates the XNNPACK delegate. Only the log tells it from an NPU run.

What worked as it should: the static GPU accelerator built from source runs at the wheel's rates (warm decode median
152.5 tok/s with 128 tokens out, the wheel 151.3 with 573; warm prefill 1294 and 1261).
`gemma-4-E2B-it_intel_PTL.litertlm` runs on the NPU from the source build: three partitions on the NPU as in the wheel, warm
decode 52.4 tok/s, the wheel 52.6.
