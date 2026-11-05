# LiteRT-LM v0.19.0 on Windows: notes from building and running it

Machine: MSI Stealth 16 AI+ (Core Ultra 9 386H, RTX 5080 Laptop, Intel AI Boost), Windows 11, tag v0.19.0 (83ce6067f),
Gemma 4 E2B. The benchmark rows run through this repo ([README.md](README.md)), and their records are in
[`results/raw/2026-11-05-windows`](../results/raw/2026-11-05-windows). The thread, affinity, wheel and
graphics-preference runs were one-off, not schema records; their logs and commands are in
[`results/raw/2026-11-05-windows-ladder`](../results/raw/2026-11-05-windows-ladder).

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

4. **On this hybrid CPU the default thread count is not the fastest for decode.** With `gemma-4-E2B-it.litertlm`, a
   20-token prompt and 128 tokens out, a fresh process's first conversation, two or three runs per count, one evening (JST):

   | started | threads | decode tok/s |
   |---|---|---|
   | 20:32 to 20:45 | 4 (the tool's default) | 19.5 to 20.2 |
   | | 6 | 17.5 to 17.7 |
   | | 8 | 12.0 to 12.1 |
   | | 12 | 8.9 |
   | | 16 | 6.3 to 6.8 |
   | 21:25 to 21:28 | 1 | 15.0 |
   | | 2 | 22.5 to 23.3 |
   | | 3 | 21.9 to 22.5 |
   | 21:29 to 21:56 | 4 again, eight runs including the benchmark rows | 20.5 to 21.0 |

   The second conversation's prefill peaks at 6 threads. At 21:55 to 21:58, pinned to the four P cores (process affinity
   mask `F`; logical processors 0 to 3 are the higher efficiency class in `GetSystemCpuSetInformation`), 2 threads gave
   25.4, 3 threads 25.9 and 4 threads 24.0, against 21.0 unpinned at 4 threads. The pin at 4 threads took the second
   conversation's prefill from 59.9 to 69.0 and left the first prefill where it was (50.0 and 49.3). A Windows process
   (`WorkloadsSessionHost`) held about 0.9 core throughout. It was not stopped, and the cause is not established.

5. **`--backend=npu` on a file with no compiled graphs runs on the CPU and exits 0.** The log says
   `No compiler plugin found`, then creates the XNNPACK delegate. Only the log tells it from an NPU run.

What worked as it should: the static GPU accelerator built from source runs at the wheel's rates (warm decode median
152.5 tok/s with 128 tokens out, the wheel 151.3 with 573; warm prefill 1294 and 1261).
`gemma-4-E2B-it_intel_PTL.litertlm` runs on the NPU from the source build: three partitions on the NPU as in the wheel, warm
decode 52.4 tok/s, the wheel 52.6.
