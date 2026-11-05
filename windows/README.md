# Windows lane

Runs the `windows` rows of a cells file on a Windows PC reached over SSH, one fresh engine process per run, and
writes the same `schema/result.v1.json` records as the other lanes.

| file | what it does |
|---|---|
| `scripts/run_windows_matrix.py` | plans the rows, verifies the pinned llama.cpp assets, writes the records from the host's logs |
| `scripts/windows_ssh_executor.py` | the SSH transport: stages the job, starts it detached, waits, pulls the logs |
| `windows/run_job.ps1` | the host side: runs the job, samples peak memory and the GPU, records the host's load before and after each run |
| `windows/build_litert_lm.ps1` | builds LiteRT-LM from a tag and stages it with its registry entry |
| `windows/engine-pins.json` | the registry: the llama.cpp release assets, the LiteRT-LM builds |
| `matrices/dashboard-windows-v1.cells` | the rows of the dashboard's Windows column |
| `windows/NOTES-v0.19.0.md` | what building and running v0.19.0 on one PC showed, with the numbers and logs |

## Setup

The host needs an OpenSSH server with PowerShell as its default shell. The session the server gives is session 0;
Direct3D 12, Vulkan and the Intel NPU all work from it, and a process started through WMI outlives the connection,
which is how the job runs.

1. Build the engine on the host (about 50 min the first time on a 16-core laptop; the script's header lists the tools):

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File build_litert_lm.ps1 -Tag v0.19.0 -Label v0.19.0 `
       -Src C:\src\LiteRT-LM -OutputBase C:\bzl -EngineDir C:\Users\me\bench\engines\litert -DxcDir <dir>
   ```

   LiteRT-LM has no Windows release asset, so the build is the host's own. `windows/engine-pins.json` lists builds by
   label, and a record names its label only when the sha256s of the tool and DLLs on the host match that entry; otherwise
   it says `unknown`. For a build the file does not list, point `BENCH_EXTRA_PINS` at the `pins.json` the script writes.
   A rebuild needs its own label: two builds of the same commit and flags came out the same size and 9 bytes apart, so
   their sha256s differ. One GPU run of the second matched the row.

2. For the NPU row, copy the OpenVINO runtime that build fetched to `<root>\engines\openvino`:
   `<OutputBase>\external\intel_openvino\openvino\runtime\bin\intel64\Release\*` and the non-debug DLLs of
   `...\runtime\3rdparty\tbb\bin`. The dispatch finds it on `PATH`, which the executor sets for that row only.

3. Put the model files in one dir on the host and hash them against the Hub's `lfs.sha256`.

## Run

```bash
BENCH_WINDOWS_ROOT='C:\Users\me\bench' BENCH_WINDOWS_MODEL_DIR='C:\Users\me\models' \
BENCH_WINDOWS_DEVICE_MODEL='<model> (<CPU> / <GPU>)' BENCH_WINDOWS_VK_DEVICES=0 \
python3 scripts/windows_ssh_executor.py matrices/dashboard-windows-v1.cells --campaign <date>-windows \
    --litert-label v0.19.0 \
    --model-file litert-lm:litert-community/gemma-4-E2B-it-litert-lm=gemma-4-E2B-it.litertlm:2588147712 \
    --model-file litert-lm:litert-community/gemma-4-E2B-it-litert-lm=gemma-4-E2B-it_intel_PTL.litertlm:2948333568 \
    --model-file llama.cpp:unsloth/gemma-4-E2B-it-GGUF=gemma-4-E2B-it-Q4_K_M.gguf:3106738272
python3 scripts/build_summary.py
python3 scripts/render_dashboard.py --cells matrices/dashboard-windows-v1.cells
```

A stopped job picks up again with `BENCH_WINDOWS_INVOCATION=<invocation>` and keeps the runs it has. On a host shared
with other work, `BENCH_WINDOWS_BUSY_FILE` and `BENCH_WINDOWS_BUSY_LABEL` name a marker the job waits on and holds.

## What a Windows machine does differently

- **System code page.** MSVC reads BOM-less UTF-8 sources in the system code page. On a Japanese Windows (932) the
  build stops in litert's `stablehlo_reduce_window.cc` with `C4430`, and a string literal elsewhere could change with no
  error, so the build script passes `/utf-8` to every action.
- **DirectX shader compiler.** With neither `dxcompiler.dll` nor `dxil.dll` beside the tool, Dawn's D3D12 backend does not
  create a device (`DynamicLib.Open: dxcompiler.dll Windows Error: 87`). The tag's `prebuilt/windows_x86_64` has neither,
  and the README note its build doc links to is not there; the PyPI wheel `litert-lm-api` carries both (`-DxcDir`).
- **Two GPUs.** The rows take the discrete one, and the record keeps and checks LiteRT-LM's `Selected adapter:` line,
  because the flag is not what picks it. `--preferred_device_substr=Intel` still selected the NVIDIA GPU: the value
  reaches the delegate's options, nothing on the WebGPU path reads it at this tag's litert pin, and ml_drift's
  `webgpu/environment.cc` asks Dawn by a power preference that comes from the GPU priority. Windows' per-app graphics
  preference does move it: `GpuPreference=1;` under `HKCU:\Software\Microsoft\DirectX\UserGpuPreferences`, with the
  tool's path as the value's name, selected `Intel(R) Graphics`. The rows do not use that. The Vulkan llama.cpp takes
  `GGML_VK_VISIBLE_DEVICES`.
- **CPU threads.** The rows pass no thread flag, as on the Mac (Android's llama.cpp rows pass `-t 4` to fit their core
  mask), so each engine runs its default: LiteRT-LM's is 4 and the record states it; llama-cli's was 16 on this 16-core
  CPU, where the Vulkan row's log prints it. On this hybrid CPU (4 P cores, 12 others) LiteRT-LM's decode rate is best at
  2 to 3 threads and falls at every count from there up to 16, while its second-conversation prefill rate peaks at 6.
  Placement is part of it: the same 4 threads under a process affinity on the P cores gained about 15 % on decode and on
  that prefill, and nothing on the first prefill. A Windows process (`WorkloadsSessionHost`) held about 0.9 core through
  these runs, and the cause of the fall is not established. More threads are not a faster row here: measure a count
  before passing one.
- **YNNPACK.** `--enable_ynnpack=true` is refused by the tag's Windows build (`the YNNPACK accelerator is not registered
  or linked`), and `--define=litert_enable_ynnpack=true` does not build with MSVC: its dependency slinky stops at
  `slinky/base/arithmetic.h` with `C2665` on `__builtin_add_overflow`.
- **NPU without a bundle.** `--backend=npu` on the file without compiled graphs does not reach the NPU: the tool logs
  `No compiler plugin found` and creates an XNNPACK delegate for CPU. The row's `file=` has to be the SoC's bundle.
- **`gemma-4-E2B-it-gpu.litertlm`.** Its decoder section is `tf_lite_artisan_text_decoder`, which selects the engine
  `GPU_ARTISAN`. The tag's open source has no such executor, so a build from source stops at
  `NOT_FOUND: No available engine for backend: GPU_ARTISAN`. The GPU row measures `gemma-4-E2B-it.litertlm`.
- **The GPU accelerator is the one built from source.** It runs, and it is the form Google's PyPI wheel carries (its log
  says `Statically linked GPU accelerator registered`). `prebuilt/windows_x86_64/libLiteRtWebGpuAccelerator.dll` of the
  tag did not run in the one way tried: loaded by a tool of the same tag built in the default link mode without the static
  accelerator, it registers, selects the NVIDIA adapter and stops with an access violation inside the DLL (`0xc0000005`,
  nine runs of nine). The Intel GPU and `--define=litert_runtime_link_mode=dynamic` have not been tried.
- **The NPU file is per SoC.** `backend=npu` rows name the bundle of their SoC with `file=` and take no
  `context-tokens=`: the bundle's KV cache is fixed at export.
