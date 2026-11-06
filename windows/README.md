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

The host needs an OpenSSH server whose default shell is Windows PowerShell (`DefaultShell` under
`HKLM:\SOFTWARE\OpenSSH`, set to `C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe`) and a key login from the
Mac: the executor calls `ssh <host>` for each step and each poll. The session the server gives is session 0; Direct3D 12,
Vulkan and the Intel NPU all work from it, and a process started through WMI outlives the connection, which is how the
build and the job run.

For the build, the host needs what the build script's header lists: Visual Studio 2022 or its Build Tools with the C++
workload, Git for Windows with LFS, Python 3.13 for all users, Bazelisk, a JDK with `JAVA_HOME`, LongPathsEnabled, and an
elevated shell or Developer Mode for symlinks. `./bench doctor` has no Windows lane. The build script checks for MSVC,
Git Bash, Python 3.13 (`C:\Program Files\Python313`), `JAVA_HOME` and Bazelisk before anything else and stops at the
first one missing, with `ERROR: <what>` as the log's last line; Git LFS, LongPathsEnabled and the symlink right are not
among those checks. They read on the host as:

```powershell
git lfs version
(Get-ItemProperty HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem).LongPathsEnabled
([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
```

Expected, in order: a `git-lfs/<version>` line, `1`, and `True` (an elevated shell, which has the symlink right;
Developer Mode is the header's other way to it). The administrator's SSH session on the 2026-11-06 PC printed all three.

On the host, `<root>` holds the engines, the jobs and their logs, and `<models>` the model files. The executor's defaults
are `%USERPROFILE%\bench` and `%USERPROFILE%\models`; `BENCH_WINDOWS_ROOT` and `BENCH_WINDOWS_MODEL_DIR` name others.
The LiteRT-LM rows run the build in `<root>\engines\litert`. `<host>` is the SSH host (`BENCH_WINDOWS_SSH_HOST`,
default `winpc`) and `<yours>` a name of yours for your build. The `powershell` blocks run on the host
(`ssh <host> '<line>'` runs one from the Mac), the `bash` ones on the Mac from the repo root.

1. Fetch the DirectX shader compiler on the host. With neither `dxcompiler.dll` nor `dxil.dll` beside the tool, Dawn's
   Direct3D 12 backend does not create a device, and the tag's prebuilt DLLs have neither; the rows run with both. The PyPI
   wheel `litert-lm-api` of the tag's version carries them (0.19.0 for v0.19.0; their sha256s are in
   `windows/engine-pins.json`):

   ```powershell
   & "C:\Program Files\Python313\python.exe" -m pip download litert-lm-api==0.19.0 --no-deps -d C:\src\wheel
   tar.exe -xf C:\src\wheel\litert_lm_api-0.19.0-py3-none-win_amd64.whl -C C:\src\wheel
   ```

   The two DLLs are then in `C:\src\wheel\litert_lm`, the build's `-DxcDir`.

2. Build the engine on the host. LiteRT-LM has no Windows release asset, so the build is the host's own: a full compile
   took 49 min on a 16-core laptop (2026-11-05, the external repositories already fetched by an attempt that had
   failed), 14 min for a later one in a new output base on the same PC (2026-11-06). The script clones LiteRT-LM into
   `-Src` when it is not there. Copy the script over from the Mac and start it through WMI, so that the build outlives
   the SSH session:

   ```bash
   scp windows/build_litert_lm.ps1 <host>:C:/src/build_litert_lm.ps1
   ssh <host> 'Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = "powershell -NoProfile -ExecutionPolicy Bypass -File C:\src\build_litert_lm.ps1 -Tag v0.19.0 -Label v0.19.0-<yours> -Src C:\src\LiteRT-LM -OutputBase C:\bzl -EngineDir <root>\engines\litert -DxcDir C:\src\wheel\litert_lm -Log C:\src\build.log" }'
   ssh <host> 'Get-Content C:\src\build.log -Tail 3'
   ```

   `ReturnValue` 0 means PowerShell started; the log's first line follows within seconds, and no log after a minute
   means the script's path in the command line is not there (PowerShell started and exited at once; a wrong `-Src`,
   `-OutputBase` or `-EngineDir` still writes a log). Step 4 can run while it builds. The log ends with
   `staged <EngineDir>, exe sha256 <sha>` or with `ERROR: <why>`, and the script stops its Bazel server after the build.
   When the build dies with `Server terminated abruptly`, read Microsoft Defender below. Give each build a label of its
   own: two builds of the same commit and flags came out the same size and 9 bytes apart (one GPU run of the second
   matched the row), so their sha256s differ. A record names the label in `conditions.engineBuild` and the build's
   version in `engineVersion`, and the executor starts no job when the sha256s of the tool and DLLs on the host do not
   match the label's entry (Run). `windows/engine-pins.json` lists one LiteRT-LM build, `v0.19.0`, the one the
   dashboard's rows ran. For your own, copy the entry the script wrote beside the tool to the Mac (`<root>` with forward
   slashes here) and point `BENCH_EXTRA_PINS` at it:

   ```bash
   scp <host>:<root>/engines/litert/pins.json pins-v0.19.0-<yours>.json
   ```

3. For the NPU row (the CPU and GPU rows skip this step), copy the OpenVINO runtime that build fetched to
   `<root>\engines\openvino`: `<OutputBase>\external\intel_openvino\openvino\runtime\bin\intel64\Release\*` and the
   non-debug DLLs of `...\runtime\3rdparty\tbb\bin`. The dispatch finds it on `PATH`, which the executor sets for that
   row only.

4. Put the model files in `<models>` on the host and check each against the sha256 the Hub lists for it (`lfs.oid` in
   the listing below); this step needs nothing from steps 1 to 3 and can run while the build does. The repos are not
   gated, so no token is needed:

   ```powershell
   curl.exe -sSL --fail --create-dirs -o <models>\gemma-4-E2B-it.litertlm https://huggingface.co/litert-community/gemma-4-E2B-it-litert-lm/resolve/main/gemma-4-E2B-it.litertlm
   (Get-FileHash -Algorithm SHA256 <models>\gemma-4-E2B-it.litertlm).Hash.ToLower()
   ```

   The Hub's sha256 and size of each file in one repo, read on the Mac (the GGUF of the llama.cpp rows is in
   `unsloth/gemma-4-E2B-it-GGUF`):

   ```bash
   curl -s https://huggingface.co/api/models/litert-community/gemma-4-E2B-it-litert-lm/tree/main | python3 -c 'import json, sys; [print(f["lfs"]["oid"], f["size"], f["path"]) for f in json.load(sys.stdin) if "lfs" in f]'
   ```

## Run

```bash
BENCH_WINDOWS_SSH_HOST=<host> BENCH_WINDOWS_ROOT='<root>' BENCH_WINDOWS_MODEL_DIR='<models>' \
BENCH_WINDOWS_DEVICE_MODEL='<model> (<CPU> / <GPU>)' BENCH_WINDOWS_VK_DEVICES=0 \
BENCH_EXTRA_PINS=pins-v0.19.0-<yours>.json \
python3 scripts/windows_ssh_executor.py matrices/dashboard-windows-v1.cells --campaign <date>-windows \
    --litert-label v0.19.0-<yours> \
    --model-file litert-lm:litert-community/gemma-4-E2B-it-litert-lm=gemma-4-E2B-it.litertlm:2588147712 \
    --model-file litert-lm:litert-community/gemma-4-E2B-it-litert-lm=gemma-4-E2B-it_intel_PTL.litertlm:2948333568 \
    --model-file llama.cpp:unsloth/gemma-4-E2B-it-GGUF=gemma-4-E2B-it-Q4_K_M.gguf:3106738272
python3 scripts/build_summary.py
python3 scripts/render_dashboard.py --cells matrices/dashboard-windows-v1.cells
```

This runs the dashboard's whole Windows column and needs every file its `--model-file` lines name in `<models>`; a job
whose model file is missing stops before its first run. For one cell, the skill has the block
(`skills/run-edge-llm-bench/SKILL.md`, "A Windows PC over SSH"), with how to read the records. They land in
`results/raw/<campaign>/`: one `.jsonl` per row with a line per record, the generated texts in `decoded/`, the host's
logs in `host-logs/<invocation>/`.

`--litert-label` names the build the LiteRT-LM rows run: your own label with `BENCH_EXTRA_PINS`, or `v0.19.0` on the host
whose build `windows/engine-pins.json` lists. Before the job is staged, the executor stops with `error: ...` and exit 1
when the label is in neither registry or when the files in `<root>\engines\litert` are not that label's build. After the
job it exits 1 when a run is not clean (its record's `conditions.exitCode`, `textCheck` or `protocolFlags` says why),
when the job failed on the host, or when fewer runs came back than the cells file plans
(`== N of M planned runs did not run on the host`): on 2026-11-06 Windows Update restarted the PC one run into a
sitting, and the stopped job's `job.done` still read `OK`. Retake such a sitting under a new `--campaign`, because the
same campaign appends to its records.
`BENCH_WINDOWS_DEVICE_MODEL` is the record's `device.modelIdentifier`, which the summary's `device` column carries as
written: it names the hardware, as the other lanes' model codes do (`SM-S942Q`, `Mac16,9`), and another spelling is
another device there. Build it from the host's own names
(`ssh <host> '(Get-CimInstance Win32_ComputerSystem).Model; (Get-CimInstance Win32_Processor).Name; (Get-CimInstance Win32_VideoController).Name'`),
by the rule the 2026-11-05 rows followed: `<Win32_ComputerSystem model> (<CPU> / <GPU>)`, the CPU's name without
`Intel(R) ` and `(TM)`, and the GPU the rows run on (the NVIDIA one) without `NVIDIA GeForce ` and its last word `GPU`;
the Intel GPU's line is not used. On the 2026-11-05 PC the rule gives
`Stealth 16 AI+ B3WI (Core Ultra 9 386H / RTX 5080 Laptop)`; a PC of the same model and parts gives the same string. The
rule is written for the one PC the lane has run, an Intel CPU with an NVIDIA GPU: on other parts, choose one string of
the same form and keep it for every sitting of that PC. Unset, it is the `Win32_ComputerSystem` model alone, which names
neither the CPU nor the GPU. The executor does not rebuild `results/summary/`; the `build_summary.py` line does.

A stopped job picks up again with `BENCH_WINDOWS_INVOCATION=<invocation>` and keeps the runs it has.

On a host shared with other work, `BENCH_WINDOWS_BUSY_FILE` (a path on the host) and `BENCH_WINDOWS_BUSY_LABEL` (default
`windows-job`) name a marker file. At its start and before each run, the job waits while the file holds another label
(one read a minute), takes it over once it is 120 min old, and writes `<label> <time>` into it; at its end it removes the
file if the text still starts with `<label> `. A marker that already starts with `<label> ` counts as the job's own. The
executor copies the logs back after the job has removed it; the copy reads files and measures nothing. To hold the
marker past the job, wait until the file is absent, write `<label> <time>` into it yourself with a label of yours (not
`windows-job`, which a job run with the default label takes for its own), rewrite it within every 120 min (a job takes
an older one over), leave the two variables unset, and remove it at the end.

## What a Windows machine does differently

- **System code page.** MSVC reads BOM-less UTF-8 sources in the system code page. On a Japanese Windows (932) the
  build stops in litert's `stablehlo_reduce_window.cc` with `C4430`, and a string literal elsewhere could change with no
  error, so the build script passes `/utf-8` to every action.
- **Microsoft Defender and Bazel's Java.** On 2026-11-06 Defender stopped the Bazel server 90 s into a build on a new
  output base, while Bazel unpacked the external repositories. It reported `Behavior:Win32/RansomJav.AB!MTB` on the JDK
  that Bazel bundles (`%USERPROFILE%\_bazel_%USERNAME%\install\<hash>\embedded_tools\jdk\bin\java.exe`), stopped the
  process, left the file in place and quarantined nothing. The same Bazel had built on this PC the day before. Bazel
  prints only `Server terminated abruptly (error code: 2, error message: 'Stream removed')`; the event log
  `Microsoft-Windows-Windows Defender/Operational` has the reason (events 1116 and 1117). The build went through after
  adding both `Add-MpPreference -ExclusionProcess <that java.exe>` and
  `Add-MpPreference -ExclusionPath <output base>,<source dir>`, with no detection in the three builds that followed.
  `Remove-MpPreference` with the same values undoes them. A new Bazel version installs under a new `<hash>` dir, so the
  process exclusion has to be added again. The exclusions are the fix for that stop, not a setup step: a build that is
  not stopped needs neither.
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
  mask), so each engine runs its default: LiteRT-LM's is 4, which the CPU row's record states (`conditions.threads`; the GPU
  and NPU rows' logs print no count, so theirs read `engine default`); llama-cli's was 16 on this 16-core CPU, where
  the Vulkan row's log prints it. On this hybrid CPU (4 P cores, 12 others) LiteRT-LM's decode rate is best at
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

## Reproducibility

The column was measured in seven sittings on the one PC: two back to back on 2026-11-05 (21:29 and 21:42 JST) and five
on 2026-11-06 (17:18, 18:39, 18:55, 21:32 and 21:46). Each ran `matrices/dashboard-windows-v1.cells` through the
invocation of the Run section, with the same engine files (each sitting's `host.json` lists the sha256 of every `.exe`
and `.dll` in the engine folders under `<root>\engines`: 133 files, equal in all seven) and the same model files (sha256
equal to the Hub's), on AC power with Windows' balanced plan, with no LiteRT-LM cache present at its start (the job
removes any it finds; the 21:29 and 17:18 sittings found none), and every run clean (exit 0, text check passed, no
protocol flag) and quiet (`hostBefore.quietGate`: before the run, the host's CPU read under 25 % in three reads a second
apart and NVIDIA memory in use under 800 MiB). Each sitting stands alone (`render_leaderboard.arm_row` per campaign).
The figures below are the change of a row's cold decode median from one sitting to another, the later sitting against
the earlier. `n` is the cold runs a sitting counts: 2, and 3 on the llama.cpp CPU row (run 1 of the other rows is the
row's first process in the sitting, `firstEver`, and is not counted). A row whose cold spread ((max - min) / median)
passes 5 % in a sitting is not counted there (the spread rule) and reads `out`.

Windows Update restarted the PC for KB5127648 after the 17:18 sitting: it initiated the restart at 17:29, before that
sitting's last run (with `TiWorker` in the run's `hostBefore.topProcesses`), the PC restarted three times between 17:31
and 17:35, and the update reported installed at 17:36: build 26200.6899 to 26200.9711, with the same GPU and NPU
drivers. `device.systemVersion` names that build from the 18:39 sitting on.

The two pairs taken at the same hour, a day apart (the four differences: each 2026-11-06 sitting of the pair against
each 2026-11-05 sitting):

| row | n | same night, 2026-11-05 | same night, 2026-11-06 | the 2026-11-06 pair against the 2026-11-05 pair, four differences | cold spread of the four sittings (21:29, 21:42, 21:32, 21:46) |
|---|---|---|---|---|---|
| `litert-lm-cpu` | 2 | -0.7 % | 0.0 % | -13.0 to -13.7 % | 0.91, 1.74, 1.28, 1.55 % |
| `litert-lm-gpu` | 2 | +1.8 % | out | out | 3.75, 2.08, 5.09, 5.89 % |
| `litert-lm-npu` | 2 | +0.2 % | +0.1 % | +1.7 to +2.0 % | 0.44, 1.03, 0.51, 0.21 % |
| `llama.cpp` | 3 | -0.6 % | -0.5 % | +5.1 to +6.2 % | 0.28, 1.69, 0.27, 3.21 % |
| `llama.cpp-gpu` | 2 | -0.3 % | +1.8 % | -18.6 to -20.3 % | 0.21, 0.37, 0.39, 3.61 % |

The other three 2026-11-06 sittings, each against 2026-11-05 21:42:

| row | 17:18, before the restart | 18:39 | 18:55 |
|---|---|---|---|
| `litert-lm-cpu` | +28.4 % | -14.1 % | -12.5 % |
| `litert-lm-gpu` | -0.5 % | -11.0 % | out |
| `litert-lm-npu` | +0.2 % | +2.6 % | +3.0 % |
| `llama.cpp` | out | out | +6.8 % |
| `llama.cpp-gpu` | out | -20.3 % | -20.7 % |

Two sittings taken back to back agreed within 2 % on every counted row, on both days. A day apart at the same hour, four
of the five rows moved by more than their own pair's same-night differences and by more than any of the four sittings'
spreads, each in one direction, from -20 % to +6 %. The GPU row's spread passed 5 % in three of the four sittings after
the update, and the eight cold runs after run 1 in those four sittings each read lower than each of the four in the
2026-11-05 sittings. Within 2026-11-06, the pair at 18:39 and 18:55 and the pair at 21:32 and 21:46 agreed within 3 % on
each row counted in all four of those sittings. What moved the rows is not established: the 17:18 sitting, taken before
the restart, read +28.4 % on the LiteRT-LM CPU row against 2026-11-05 21:42. In that sitting both llama.cpp rows read
`out`, with `OneDriveSetup` and `TiWorker` near one core in those runs' `hostBefore.topProcesses`. The cold prefill
rate, which the tables leave out, moved as well: in the four sittings after the update, seven of the eight
`llama.cpp-gpu` runs after run 1 read 35.9 to 52.0 % below the lowest of that row's four on 2026-11-05 (the eighth read
2.6 % above their highest), and all eight `litert-lm-cpu` runs read 10.6 to 13.2 % above that row's highest, while its
decode fell. Peak memory (`arm_row`'s median for the sitting) stayed within 2.4 % of either 2026-11-05 sitting on the
LiteRT-LM GPU row and within 0.3 % on the other rows, in every sitting. So on this PC a row's figure from one sitting
did not carry to a sitting taken on another day: set figures side by side only within one sitting, or across sittings
taken back to back.