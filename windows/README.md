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

TensorRT Edge-LLM has no row in this column; its build notes on Windows x64 are in
[tensorrt-edge-llm-windows-notes](https://github.com/john-rocky/tensorrt-edge-llm-windows-notes).

## Setup

The host needs an OpenSSH server whose default shell is Windows PowerShell (`DefaultShell` under
`HKLM:\SOFTWARE\OpenSSH`, set to `C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe`) and a key login from the
Mac: the executor calls `ssh <host>` for each step and waits for the job through one session it holds open until the
job ends. The session the server gives is session 0; Direct3D 12,
Vulkan and the Intel NPU all work from it, and a process started through WMI outlives the connection, which is how the
build and the job run. By default the job sets each engine process it starts to High QoS, the level Windows gives an
app in the foreground and in focus, so its runs are measured with Windows' power throttling off for the engine; what
the job did for each run is in its record (Run, `conditions.engineQos`; records from before `-EngineQos` lack the
key). The job runs from an SSH session while the PC's desktop is locked; an engine started from the desktop has not
been measured.

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

   The Hub's sha256 and size of each file in one repo, read on the Mac (the command reads
   `litert-community/gemma-4-E2B-it-litert-lm`; put another repo's id in its place for the other files). The Gemma 4
   E2B rows' files are in that repo and `unsloth/gemma-4-E2B-it-GGUF`; the Gemma 4 E4B rows' in
   `litert-community/gemma-4-E4B-it-litert-lm` and `unsloth/gemma-4-E4B-it-GGUF`; the Qwen3 rows' in
   `litert-community/Qwen3-0.6B`, `litert-community/Qwen3-1.7B` and `litert-community/Qwen3-4B` (LiteRT-LM) and
   `unsloth/Qwen3-0.6B-GGUF`, `-1.7B-GGUF` and `-4B-GGUF` (llama.cpp); the cells file names each row's file with
   `file=`:

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
    --model-file llama.cpp:unsloth/gemma-4-E2B-it-GGUF=gemma-4-E2B-it-Q4_K_M.gguf:3106738272 \
    --model-file litert-lm:litert-community/Qwen3-0.6B=Qwen3-0.6B_dynamic_wi4b32_afp32.litertlm:343490560 \
    --model-file litert-lm:litert-community/Qwen3-1.7B=Qwen3_1.7B.litertlm:1754890240 \
    --model-file litert-lm:litert-community/Qwen3-1.7B=Qwen3-1.7B_dynamic_wi4b32_afp32.litertlm:977184032 \
    --model-file litert-lm:litert-community/Qwen3-4B=qwen3_4b_mixed_int4.litertlm:2272935936 \
    --model-file llama.cpp:unsloth/Qwen3-0.6B-GGUF=Qwen3-0.6B-Q4_K_M.gguf:396705472 \
    --model-file llama.cpp:unsloth/Qwen3-1.7B-GGUF=Qwen3-1.7B-Q4_K_M.gguf:1107409472 \
    --model-file llama.cpp:unsloth/Qwen3-4B-GGUF=Qwen3-4B-Q4_K_M.gguf:2497281312 \
    --model-file litert-lm:litert-community/gemma-4-E4B-it-litert-lm=gemma-4-E4B-it.litertlm:3659530240 \
    --model-file llama.cpp:unsloth/gemma-4-E4B-it-GGUF=gemma-4-E4B-it-Q4_K_M.gguf:4977171584
python3 scripts/build_summary.py
python3 scripts/render_dashboard.py --cells matrices/dashboard-windows-v1.cells
```

This runs the dashboard's whole Windows column and needs every file its `--model-file` lines name in `<models>`; a job
whose model file is missing stops before its first run. For one cell, the skill has the block
(`skills/run-edge-llm-bench/SKILL.md`, "A Windows PC over SSH"), with how to read the records. They land in
`results/raw/<campaign>/`: one `.jsonl` per row with a line per record, the generated texts in `decoded/`, the host's
logs in `host-logs/<invocation>/`.

The llama.cpp rows need no step on the host. The executor downloads the zips `windows/engine-pins.json` pins into
`windows/bin` on the Mac (`BENCH_WINDOWS_BIN_DIR` names another dir), checks each zip's size and sha256, and expands them
on the host into `<root>\engines\llama-cpu`, `<root>\engines\llama-gpu` (the Vulkan asset) and `<root>\engines\llama-cuda`
(the CUDA asset, with the CUDA runtime zip of the same release expanded into the same dir). It skips a dir whose
`llama-cli.exe` and every DLL the registry lists for the label already have the registry's sha256s, and stops with
`error: ...` when any of them still differs after the copy. A record names the label in `engineVersion` only when the
files in the run's dir matched it (`unknown (<files> unmatched in <label>)` otherwise).

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
`Intel(R) ` and `(TM)`, and the discrete GPU, which the GPU rows without `adapter=` run on (the NVIDIA one), without
`NVIDIA GeForce ` and its last word `GPU`; the Intel GPU's line is not used. An `adapter=igpu` row runs on the same PC and
carries the same string: its arm says which GPU. On the 2026-11-05 PC the rule gives
`Stealth 16 AI+ B3WI (Core Ultra 9 386H / RTX 5080 Laptop)`; a PC of the same model and parts gives the same string. The
rule is written for the one PC the lane has run, an Intel CPU with an NVIDIA GPU: on other parts, choose one string of
the same form and keep it for every sitting of that PC. Unset, it is the `Win32_ComputerSystem` model alone, which names
neither the CPU nor the GPU. The executor does not rebuild `results/summary/`; the `build_summary.py` line does.

A stopped job picks up again with `BENCH_WINDOWS_INVOCATION=<invocation>` and keeps the runs it has.

While the job runs, the executor waits for it through one SSH session: a PowerShell loop on the host reads `job.log` and
`job.done` in the job's log dir every 5 s (two file reads, no WMI), sends `job.log`'s new lines, which the executor
prints as `host: ...`, sends a keep-alive line (`ALIVE`) after 60 s without one, and ends when `job.done` appears. The
executor closes a session that sends nothing for 180 s; a session that ends before `job.done` is opened again 30 s later
and goes on from the next line of `job.log`. When none of the loop's lines has come for 600 s, the executor stops with
`error: host unreachable for 600 s` and exit 1, and the job goes on on the host for `BENCH_WINDOWS_INVOCATION` to pick
up. The executor's own SSH connections are those that stage the job, the wait's session (one, unless it drops) and the
copy of the logs.

On a host shared with other work, `BENCH_WINDOWS_BUSY_FILE` (a path on the host) and `BENCH_WINDOWS_BUSY_LABEL` (default
`windows-job`) name a marker file. At its start and before each run, the job waits while the file holds another label
(one read a minute), takes it over once it is 120 min old, and writes `<label> <time>` into it; at its end it removes the
file if the text still starts with `<label> `. A marker that already starts with `<label> ` counts as the job's own. The
executor copies the logs back after the job has removed it; the copy reads files and measures nothing. To hold the
marker past the job, wait until the file is absent, write `<label> <time>` into it yourself with a label of yours (not
`windows-job`, which a job run with the default label takes for its own), rewrite it within every 120 min (a job takes
an older one over), leave the two variables unset, and remove it at the end.

Each record also carries two reads the job took on the host around its engine process: the SSH connections that
reached the host meanwhile (`conditions.sshConnections`) and the logical processors' counters over it
(`conditions.hostCpu`); nothing in the harness judges either. `conditions.sshConnections` holds the SSH connections the
host's sshd accepted from the run's start to its end: their number (`accepted`) and each one's second into the run
(`atSeconds`), read after the run from the host's `OpenSSH/Operational` event log, where OpenSSH writes one `Accepted`
event per connection; a session opened before the run and still open during it is not counted. The executor's wait
is such a session, opened before the job's first run, so a run with no other SSH client counts none; a wait session
opened again after a drop counts in the run it falls in. The log is circular (1 MiB: about
7 h of this PC's SSH traffic on 2026-11-07) and is read right after each run; a run whose start the log no longer
reaches by then (it turned over or was cleared during the run), or a run on a host whose log cannot be read, gets
`accepted: null` and the reason.

`conditions.hostCpu` holds, for each logical processor and for `_Total`, the share of time it was busy with any process
(`busyPercent`, the `Processor Information` counter `% Processor Time`) and its performance against what Windows calls
the processor's nominal performance (`performancePercent`, `% Processor Performance`, which can read over 100), both
averaged over the run from reads right before the engine starts and right after it exits (`seconds` apart). It also
holds the lowest `% Performance Limit` (`performanceLimitPercent`) of the reads after the first (one every 5 s while
the engine runs, and the one after it exits) and the `Performance Limit Flags` any of the reads held
(`performanceLimitFlags`, OR-ed, only where not 0); `limitReads` says how many reads were taken and is left out when
fewer than two were, in which case both come from the read after the engine exits. Every iteration record of a run
carries the run's values. `host.json` lists each logical processor's efficiency class, core, last-level cache index
(`llc`: processors with the same index share that cache) and `maxMhz` (`cpuSets`), by which to read the keys of
`hostCpu`. Records from the sittings up to `2026-11-07-windows-igpu` carry neither key: the job read neither then.

Right after the job finds a run's engine process, it sets that process to High QoS (`SetProcessInformation`,
`ProcessPowerThrottling`: `ControlMask` `PROCESS_POWER_THROTTLING_EXECUTION_SPEED`, `StateMask` 0) and reads the value
back (the state before the set is not read); the value belongs to that process and ends with it. Without it, Windows'
own heuristics pick the level of the engine, a process with no window that the job starts through `cmd.exe`, the job
itself started by the executor through WMI. `BENCH_WINDOWS_ENGINE_QOS` (the job's `-EngineQos`) is `on` by default;
`off` sets nothing, as the job did before `-EngineQos`, and `alt` sets it on every other run of a row (runs 1, 3, ... of
rows `r00`, `r02`, ... and runs 2, 4, ... of the other rows, the `rNN` of the host logs, so that each row holds both
states). Each record carries what the job did (`conditions.engineQos`): `mode`; `state` (`high`; `none` when the mode
set nothing for that run; `no-pid` when the job found no engine process, so nothing was set; `error` when a step
failed); the `error` key (the failed call and Windows' error code, `Add-Type:` and the compiler's message when
`Add-Type` could not compile the call's code, or an exception's message); `engineStartToSetSeconds`, from the engine
process's start to the set; and the masks read back (`readBack`; a `high` whose read back failed carries `error` in its
place). Nothing in the harness judges it. Records from the sittings that ran the job before `-EngineQos` lack the key.

Each run's host log (`host-logs/<invocation>/r<NN>_run<N>.json`) also holds the NVIDIA GPU's state, one `nvidia-smi`
read each (name, driver, P-state, temperature, graphics and memory clocks, power, utilization, memory used), taken
before the engine starts (`before.gpu`, which the record carries as `conditions.hostBefore.gpu`) and after it exits
(`gpuAfter`, read after the run's CPU, top-process and SSH-log reads, a second or more later), on every row. On a GPU
row (an `adapter=igpu` one too) the job waits 2 s after `before.gpu` before it starts the engine (the job's
`-AfterGpuReadSeconds`, default 2, which the executor does not set); each run's host log holds the seconds measured from
that read's end to the run's start, when the job launches the engine (`gpuReadToStartSeconds`; on a CPU row, the same
span with no wait). The sittings before `2026-11-07-windows-gpuwait-on-a1` and the `2026-11-07-windows-gpuwait-off-*`
ones ran the job without the wait; their host logs lack the key (Reproducibility). While
the engine runs the job takes none, unless `BENCH_WINDOWS_GPU_SAMPLE_SECONDS=N` asks for one every N s on a GPU row (an
`adapter=igpu` one too): `gpuSamples`, with each read's start and end in seconds from the run's start in
`gpuSampleWindows`. Each run's host log names the N it ran with (`gpuSampleSeconds`) and when the engine's process
started (`engineStartSeconds`). The job's loop, which reads the engine's peak memory about every 500 ms and the CPU
counters every 5 s, stops while each read runs (36 to 77 ms in most reads of the `2026-11-07-windows-gpuread-on-*`
sittings, up to 0.86 s). The harness checks none of these values, and graphics clocks no GPU runs at appear among them
(up to 41767 MHz in the committed 2026-11-05 host logs). The sittings up to `2026-11-07-windows-wait-session-2` ran a
job that took one every 5 s while a GPU row's engine ran (none for a run of about 5 s), and their host logs have neither
`gpuSampleWindows` nor `engineStartSeconds`.

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
- **Two GPUs.** A LiteRT-LM GPU row takes the discrete one, and the record keeps and checks LiteRT-LM's
  `Selected adapter:` line, because the flag is not what picks it. `--preferred_device_substr=Intel` still selected the
  NVIDIA GPU: the value reaches the delegate's options, nothing on the WebGPU path reads it at this tag's litert pin, and
  ml_drift's `webgpu/environment.cc` asks Dawn by a power preference that comes from the GPU priority. Windows' per-app
  graphics preference does move it: `GpuPreference=1;` under `HKCU:\Software\Microsoft\DirectX\UserGpuPreferences`, with
  the tool's path as the value's name, selected `Intel(R) Graphics`. The `adapter=igpu` rows (arm `litert-lm-gpu-igpu`)
  use that. `run_job.ps1` sets the value right before each of their runs and removes it right after, in a `finally`,
  and writes both to `job.log`. It stops the job when the value cannot be removed: a value left on the exe would move
  every later run of it, the discrete GPU's rows included. Every LiteRT-LM run first removes a value it finds on the
  tool (a job stopped mid-run leaves one). The engine's GPU caches beside a model
  (`<file>_<n>_<n>_mldrift_program_cache.bin` and `..._mldrift_weight_cache.bin`) carry no adapter in their names. The
  job removes them before a run on a different adapter from the one that wrote them; that run compiles and writes them
  again and is recorded as the cache build (`firstEver`). At the job's end it removes the caches the integrated GPU's
  runs wrote. Each GPU record keeps the adapter its log selected (`conditions.gpuAdapter`) and the preference value it
  ran under (`conditions.gpuPreference`). A run whose log names the other GPU, or an `adapter=igpu` run without its
  value, is flagged `backend-not-registered` and not counted. Before each `adapter=igpu` run the job's quiet gate also
  waits until the use of every GPU engine on the host sums under 10 % (`-QuietGpuEnginePercent`): the NVIDIA memory
  reading does not see the integrated GPU. The Vulkan llama.cpp takes `GGML_VK_VISIBLE_DEVICES`. The CUDA llama.cpp
  needs no variable: the NVIDIA GPU is the host's only CUDA device
  (`ggml_cuda_init: found 1 CUDA devices`, then `using device CUDA0 (NVIDIA GeForce RTX 5080 Laptop GPU)`), and the
  asset carries no other GPU backend.
- **The CUDA asset.** b11721 publishes two Windows x64 CUDA assets, built with CUDA 12.4 and with CUDA 13.4, and a CUDA
  runtime zip for each (`cudart-llama-bin-win-cuda-<version>-x64.zip`, with the `cudart64`, `cublas64` and `cublasLt64`
  DLLs). The `llama.cpp-cuda` row runs 13.4 with its runtime zip, both pinned in `windows/engine-pins.json`. The host has
  no CUDA toolkit; the NVIDIA driver (591.74 here) and the runtime zip are what the row needs. 13.4's `ggml-cuda.dll`
  carries kernels compiled for the RTX 5080's compute capability 12.0 (its log reads
  `CUDA : ARCHS = 750,800,860,890,900,1200,1210`). 12.4's carries compiled kernels for 8.6 and 8.9 only and PTX for 5.0
  to 9.0 (`ARCHS = 500,610,700,750,800,860,890,900`); that PTX the driver compiles for the GPU the first time a process
  loads it, and keeps the result in its own cache (`%APPDATA%\NVIDIA\ComputeCache`, which the job does not remove). In
  two runs by hand on this PC (not records), 12.4's first run took 200 s, its warm-up 1 min 48 s and its 20-token prompt
  87 s, with new files landing in that cache meanwhile; its second run took 4 s in all.
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
  tag did not run with a tool built from the tag's source in any of the three combinations tried. With the LiteRT runtime
  built from source (a default-link-mode build with the default branch of `runtime/executor:default_static_gpu_accelerator`
  emptied, which `build_litert_lm.ps1` has no switch for, or `--define=litert_runtime_link_mode=dynamic` with the
  `libLiteRt.dll` that build makes), the DLL registers, selects the adapter and stops with an access violation inside the
  DLL at offset `0x58b811` (`0xc0000005`: nine of nine runs on the NVIDIA GPU on 2026-11-05, three of three across both
  GPUs on 2026-11-07). With the tag's prebuilt `libLiteRt.dll` next to the dynamic-mode tool, the run gets past that point
  and stops before printing any text, with `0xc0000409` in `ucrtbase.dll` (one of one on the NVIDIA GPU, two of two on the
  Intel GPU). The dynamic-mode tool runs on both GPUs with the accelerator DLL built in the same build; the rows do not
  use it.
- **The NPU file is per SoC.** `backend=npu` rows name the bundle of their SoC with `file=` and take no
  `context-tokens=`: the bundle's KV cache is fixed at export.
- **The Qwen3 rows.** They load the files the Android rows of `matrices/dashboard-text-v1.cells` load, under the same
  catalog ids. None of the three repos (`litert-community/Qwen3-0.6B`, `-1.7B`, `-4B`) lists an Intel bundle (read
  2026-11-07), so the Qwen3 blocks have no `backend=npu` row. Three of their four LiteRT-LM files were replaced on the
  Hub under the same names on 2026-10-31 (`Qwen3-0.6B_dynamic_wi4b32_afp32.litertlm`, `Qwen3_1.7B.litertlm`,
  `qwen3_4b_mixed_int4.litertlm`; the cards: new LiteRT Torch exports with GPU composite ops and external weights). The
  runner labels a file by its name, and the names did not change, so by name alone a record would carry the earlier
  content's label. A record of one of those files from that UTC date on takes the replacement's recipe label from
  `REPLACED_FILE_LABELS` in `scripts/bench_common.py` instead, the table the summary corrects the Android rows of the
  same files with; the summary applies it to the Windows rows too.
- **The Gemma 4 E4B rows.** They load the files the Android rows of `matrices/dashboard-text-v1.cells` load, under the
  same catalog ids: `gemma-4-E4B-it.litertlm` on both LiteRT-LM rows (as the E2B block does with its file) and
  `gemma-4-E4B-it-Q4_K_M.gguf` on the three llama.cpp rows, which run with thinking off like the E2B GGUF
  (`--chat-template-kwargs`). `litert-community/gemma-4-E4B-it-litert-lm` lists no Intel bundle (read 2026-11-07), so
  the block has no `backend=npu` row. Both files were replaced on the Hub under the same names before these rows were
  added: the `.litertlm` on 2026-05-04 (its card asks anyone who downloaded it before 2026-05-05 to download it again
  for speculative decoding), the GGUF on 2026-05-04 and 2026-07-17 (commits titled as chat template updates). The
  sittings ran the content the Hub served on 2026-11-07, each file's sha256 checked on the host against the Hub's
  before the first run. The `.litertlm`'s label (`wNa8o8`) is the one the 2026-07-17 audit set for Gemma 4 `.litertlm`
  bundles (`corrected_quant` in `scripts/bench_common.py`), after this file's replacement, and the GGUF's is the
  `Q4_K_M` of its name, so `REPLACED_FILE_LABELS` has no row for them.

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

Two more sittings, `2026-11-06-windows-cuda-s1` and `2026-11-06-windows-cuda`, ran the column with the CUDA row added,
back to back at 00:02 and 00:19 JST on 2026-11-07 (2026-11-06 in UTC, the date of the records' `timestamp` and of their
names). Their `host.json` lists the seven sittings' 133 engine files unchanged plus the 54 of
`<root>\engines\llama-cuda` (187 in all); the model files and the invocation were the same, and every run was clean and
quiet. From the first to the second, the cold decode median moved by -1.0 % on `litert-lm-cpu`, -0.7 % on
`litert-lm-npu`, +1.9 % on `llama.cpp-gpu` and +0.4 % on `llama.cpp-cuda` (cold spreads 4.26 and 0.58 %, 1.08 and
0.11 %, 2.16 and 3.34 %, 0.34 and 1.69 %). `litert-lm-gpu` read `out` in the first (13.88 %) and `llama.cpp` in both
(21.07 and 16.26 %), so those two rows have no change figure. During both sittings SSH sessions opened on the host about
17 times a minute (the host's `OpenSSH/Operational` log): two of them a minute were the executor's own poll (one every
30 s), the rest other SSH clients. In the llama.cpp CPU row, whose 16 threads (llama-cli's default here, "CPU threads"
above) take every logical CPU, the three runs during which three or four sessions opened read 9 to 19 % below the mean
of the three with two or none: six runs, a correlation, the cause not established. Keep other SSH clients off the host
during a sitting.

Two more sittings, `2026-11-07-windows-qwen3-s1` and `2026-11-07-windows-qwen3`, ran the column with the Qwen3 rows added
(21 rows, 63 runs each), back to back at 02:56 and 03:57 JST on 2026-11-07 (2026-11-06 in UTC, the date of the records'
`timestamp`). Their `host.json` lists the CUDA sittings' 187 engine files unchanged; the sha256 of the ten model files,
read on the host before the first, equal the Hub's; the invocation was the Run section's, and every run was clean and
quiet. From the first to the second, the cold decode median of the 16 rows counted in both moved by -3.6 to +3.3 %
(Gemma 4 E2B's `litert-lm-gpu` -3.6 %, Qwen3 4B's `llama.cpp-gpu` +3.3 %, the other 14 within 2.3 %). Five rows read
`out` in one of the two: in the first, Qwen3 0.6B's `llama.cpp-cuda` (7.29 %) and Gemma 4 E2B's `llama.cpp` (11.63 %);
in the second, Qwen3 0.6B's `litert-lm-cpu` (5.40 %) and `llama.cpp` (12.61 %) and Qwen3 1.7B's `llama.cpp` (5.22 %).
Against the second CUDA sitting, which started 3 h 38 min before the second of these the same night, Gemma 4 E2B's rows
moved by +5.1 % (`litert-lm-cpu`), -4.9 % (`litert-lm-gpu`), +0.7 % (`litert-lm-npu`), -2.7 % (`llama.cpp-gpu`) and
-1.0 % (`llama.cpp-cuda`); `llama.cpp` read `out` in the CUDA sitting. During both sittings SSH sessions opened on the
host about twice a minute (the host's `OpenSSH/Operational` log), the executor's own poll, plus one every 5 minutes from
a reachability check on the driving machine. Beyond those, the minute each sitting's job was staged (02:56 and 03:57)
had 14 and 12 sessions in all, one opened at 04:09 to rewrite the marker file (see Run), and one at 04:46 came from the
driving machine by a process not identified. In 78 of the 126 runs no session opened, in 38 one did, and in ten
LiteRT-LM CPU runs of 19 to 133 s two to six did.

Two more sittings, `2026-11-07-windows-e4b-s1` and `2026-11-07-windows-e4b`, ran the column with the Gemma 4 E4B rows
added (26 rows, 78 runs each), back to back at 06:51 and 08:10 JST on 2026-11-07 (in UTC, the date of the records'
`timestamp`, 2026-11-06 until 09:00 JST and 2026-11-07 for the second's last 38 records). Their `host.json` lists the
Qwen3 sittings' 187 engine files unchanged; the sha256 of the twelve model files, read on the host before the first,
equal the Hub's; the invocation was the Run section's, and every run was clean and quiet. From the first to the second,
the cold decode median of the 21 rows counted in both moved by -2.5 to +3.7 % (Gemma 4 E4B's `litert-lm-gpu` -2.5 %,
Qwen3 0.6B's `litert-lm-cpu` +3.7 %, the other 19 within 3.1 %). Five rows read `out` in one or both: in the first,
Gemma 4 E2B's `litert-lm-gpu` (5.91 %) and Qwen3 1.7B's `llama.cpp` (10.67 %); in the second, Qwen3 0.6B's
`llama.cpp-cuda` (6.18 %) and `llama.cpp` (12.26 %); in both, Gemma 4 E4B's `llama.cpp` (11.17 and 12.83 %), whose
first run read 9.0 to 13.2 % above each of its other two in each sitting. Against the second Qwen3 sitting, which
started 4 h 13 min before the second of these, the 17 rows counted in both (the other four read `out` in one or both)
moved by -1.0 to +4.6 % (Gemma 4 E2B's `litert-lm-gpu` +4.6 %, the other 16 within 2.5 %). During both sittings SSH
sessions opened on the host about twice a minute, the executor's own poll, plus one every 5 minutes from the
reachability check. Beyond those, the minute each sitting's job was staged (06:51 and 08:10) had 13 sessions each, and
one opened at 08:14 to rewrite the marker file. In 97 of the 156 runs no session opened, in 47 one did, and in twelve
LiteRT-LM runs of 27 to 135 s two to five did.

Two more sittings, `2026-11-07-windows-igpu-s1` and `2026-11-07-windows-igpu`, ran the five `adapter=igpu` rows alone
(a cells file of those five lines, 15 runs each), back to back at 13:26 and 13:43 JST on 2026-11-07. Their `host.json`
lists the E4B sittings' 187 engine files unchanged, the five model files' sha256 (read on the host beforehand) equal
the Hub's, and every run was clean and quiet. Every record's `gpuAdapter` and every run's `Selected adapter:` line show
`Intel(R) Graphics` with `adapterType=Integrated GPU`; every `gpuPreference` reads `GpuPreference=1;`. Each job removed
the preference value after every run and, at its end, the ten cache files its runs wrote. From the first to the second,
the cold decode median moved by +0.2 % on Qwen3 1.7B (cold spreads 0.18 and 0.52 %), -1.0 % on Qwen3 4B (3.83 and
1.96 %) and +14.9 % on Gemma 4 E2B (0.27 and 0.03 %); what moved the E2B row is not established. Qwen3 0.6B read `out`
in both (36.16 and 60.32 %), Gemma 4 E4B in the second (7.06 %). SSH sessions opened about twice a minute (the
executor's poll) plus one every 5 minutes: none during 11 of the 30 runs, one during 17, two during the other two.

Four more sittings ran Gemma 4 E2B's five rows (a cells file of those five lines, 15 runs each) back to back at 16:17,
16:32, 16:46 and 17:02 JST on 2026-11-07, alternating the executor's two ways of waiting for the job:
`2026-11-07-windows-wait-poll-1` and `2026-11-07-windows-wait-poll-2` with its earlier wait, a new SSH connection every
30 s that read `job.log` and `job.done`, and `2026-11-07-windows-wait-session-1` and `2026-11-07-windows-wait-session-2`
with the one session of the Run section. Their `host.json` lists the `adapter=igpu` sittings' 187 engine files
unchanged, and every run was clean and quiet. In the two poll sittings the executor opened 39 and 41 SSH connections, 5
and 6 of them during runs. In the two session sittings it opened 10 each, none during a run: nine before the first run,
which stage and start the job and open the wait's session, and one after the last, which copies the logs. The wait's
session stayed open until the job ended (816 and 786 s), and its loop's process used 0.69 and 0.64 s of CPU. The other
sessions that opened during a run, one in each of the first, second and fourth sittings, came from the reachability
check. The cold decode medians of `litert-lm-cpu` and `litert-lm-npu`, counted in all four sittings, and of `llama.cpp`,
counted in the last three, each stayed within 2.2 %. Where the wait changed from one sitting to the next they moved by
-0.93 to +1.91 %, and between the two sittings of the same wait by +0.97 to +2.16 %. In the first sitting a connection
of the poll opened 5.3 s into `llama.cpp`'s second run of 6.8 s, which read 5.5 % below the mean of the sitting's other
two and put the row's cold spread at 6.17 % (`out`); the other eleven `llama.cpp` runs, none with a connection, lay
within 2.5 % of one another. The GPU rows read `out` with either wait: `litert-lm-gpu` in the second and third sittings
(8.26 and 12.28 %), `llama.cpp-gpu` in the first, second and fourth (12.15, 10.82 and 12.61 %). Of `llama.cpp-gpu`'s
second and third runs, the three that took about 4.2 s, ending before the job's first reading inside a run at 5 s (the
CPU counters, and `nvidia-smi` on a GPU row), read 9.0 to 14.0 % above the five that took about 6.3 s, each with one
such reading; what makes the difference is not established.

Four more sittings ran Gemma 4 E2B's four GPU rows (a cells file of those four lines, 20 runs each) back to back at
18:17, 18:37, 18:54 and 19:12 JST on 2026-11-07, alternating the job's NVIDIA reads while a GPU row's engine ran:
`2026-11-07-windows-gpuread-on-1` and `2026-11-07-windows-gpuread-on-2` with one every 5 s, the job's default until
then, and `2026-11-07-windows-gpuread-off-1` and `2026-11-07-windows-gpuread-off-2` with none
(`BENCH_WINDOWS_GPU_SAMPLE_SECONDS=0`). Their `host.json` lists the same 187 engine files as the
`2026-11-07-windows-wait-*` sittings above, and every run was clean and quiet. The on sittings took 31 and 24 reads
inside runs: 48 of the 55 took 36 to 77 ms (`gpuSampleWindows`), five 82 to 388 ms, and the two longest 0.86 s, each in
a row's first run. No read fell inside the cold conversation's decode of a counted `litert-lm-gpu` or `llama.cpp-gpu`
run (the closest two, both `llama.cpp-gpu`'s, started 0.03 and 0.04 s after the decode's last line, on the engine log's
clock); `litert-lm-gpu-igpu`'s 5 s read fell inside its cold prefill in all eight counted runs and its 10 s read within
the last 0.3 s of its cold decode in five; `llama.cpp-cuda`'s runs all ended before 5 s, so neither of its arms took
one, and it read `out` in the first sitting (10.10 %). Where the reads changed from one sitting to the next, the cold
decode medians of the rows whose cold spread stayed within 5 % in both sittings moved by -1.34 to +2.17 %, and between
the two sittings of the same arm by -1.11 to +0.82 %; `llama.cpp-cuda`, with no read in either arm (the control), moved
by -0.12 and +0.94 % where the reads changed. `litert-lm-gpu-igpu` read 2.17 % higher in `-off-1` than in `-on-1` and
1.34 % lower in `-on-2` than in `-off-1`, and `-off-2` reads `out` (13.02 %), its median 3.02 % below that of `-on-2`.
Of `llama.cpp-gpu`'s counted runs, the 14 that took 5.7 to 8.4 s, seven with a read and seven without, lay within 3.2 %
of one another; of the two that ended before 5 s, neither with a read, the one of 4.2 s (in `-on-2`) read 12.8 % above
their median and the one of 4.7 s (in `-off-1`) 1.4 % above it. So the `nvidia-smi` read at 5 s is not what sets the
4.2 s runs of the `2026-11-07-windows-wait-*` sittings apart; the CPU counter read at 5 s stayed in both arms and is not
tested here. `litert-lm-gpu`'s warm decode median (the median of its five runs' second conversations, run 1's included)
read 2.64 % higher in `-off-1` than in `-on-1`, 3.27 % lower in `-on-2` than in `-off-1` and 3.66 % higher in `-off-2`
than in `-on-2`, against -0.71 and +0.27 % between the two sittings of the same arm (over runs 2 to 5 alone +1.81, -3.09
and +2.53 %, against -1.34 and -0.64 %), though in those runs each read started 0.13 to 0.25 s after the engine logged
that conversation's output, the decode's end (in `-on-1`'s run 1, the row's first process, one fell inside it); what
makes that difference is not established. Since then the job takes no read while the engine runs unless asked (Run).

Eight more sittings ran two of Gemma 4 E2B's GPU rows at a time (a cells file of those two lines, runs=5, 10 runs
each) in four back-to-back pairs on 2026-11-08 JST (2026-11-07 in UTC, the date of the records' `timestamp` and of
their names). Each pair is one off sitting, of the job as of commit 54a835f8, which starts the engine with no wait
after the read before a GPU row's run (`before.gpu`), and one on sitting, of the job that waits 2 s after that read
before it starts the engine (Run): `litert-lm-gpu` and `llama.cpp-gpu` in `2026-11-07-windows-gpuwait-off-a1` and
`-on-a1` at 01:47 and 01:56, then in `-on-a2` and `-off-a2` at 03:58 and 04:07; `litert-lm-gpu-igpu` and
`llama.cpp-cuda` in `-off-b1` and `-on-b1` at 06:04 and 06:13, then in `-on-b2` and `-off-b2` at 06:50 and 07:00.
Their `host.json` lists the same 187 engine files as the `2026-11-07-windows-gpuread-*` sittings, every run was clean
and quiet, and no run took a GPU read while its engine ran. In the on sittings every run's `gpuReadToStartSeconds`
reads 1.996 to 2.080 s on the NVIDIA rows and 2.372 to 2.477 s on `litert-lm-gpu-igpu`, whose job also reads Windows'
GPU Engine counters and sets the tool's GPU preference in that time; the off sittings' host logs have no such key. One
SSH connection opened during a run, 1.4 s into `-on-a1`'s fourth `litert-lm-gpu` run, from the driving machine's
reachability check (one every 5 minutes).

Against the off sitting of its pair, the on sitting read `litert-lm-gpu`'s cold decode median 24.7 and 27.2 % lower
and its warm decode median 8.1 and 4.4 % higher, all four sittings `out` (cold spreads 34.74 and 27.25 % off, 11.62
and 10.90 % on); `llama.cpp-cuda`'s cold decode median 13.6 and 11.1 % lower (cold spreads 7.24 and 1.11 % off, the
first `out`, 2.63 and 3.26 % on); `llama.cpp-gpu`'s cold decode median 2.7 % lower and 0.4 % higher (cold spreads
4.81 and 3.29 % off, 1.65 and 1.77 % on); and `litert-lm-gpu-igpu`'s 1.6 and 3.6 % lower, all four sittings `out`
(cold spreads 17.00 and 26.25 % off, 11.73 and 12.82 % on). The cold prefill medians read lower in every pair: 27.9
and 32.4 % on `litert-lm-gpu`, 4.1 and 10.8 % on `llama.cpp-gpu`, 14.8 and 10.1 % on `litert-lm-gpu-igpu`, and 46.8
and 48.0 % on `llama.cpp-cuda`. Each of `llama.cpp-cuda`'s eight counted runs in the off sittings read its cold
decode above each of the eight in the on sittings. In each of its two off sittings one of `litert-lm-gpu`'s four
counted runs read its cold decode 29.0 and 25.8 % below the median of the other three, in each the run whose engine's
`Selected adapter:` line came latest after its first log line (1.54 and 0.87 s, against 0.46 to 0.51 s in the other
six); in the on sittings that line came at 1.20 to 1.27 s in all eight counted runs. In each of its two off sittings
one of `llama.cpp-gpu`'s four counted runs read its cold prefill 64.0 and 74.9 % above the median of the other three;
in the on sittings none read it more than 5.0 % above its sitting's median. Since then the job waits 2 s after the
read before it starts a GPU row's engine (Run).

Two more sittings ran Gemma 4 E2B's `litert-lm-gpu` row alone (a cells file of that one line, runs=5) with the job's
2 s wait: `2026-11-08-windows-gpuwait-on-c1` and `2026-11-08-windows-gpuwait-on-c2`, at 12:08 and 12:18 JST on
2026-11-08, with five runs of the same engine and model outside the job between them (diagnostic runs, not records).
`BENCH_WINDOWS_MODEL_DIR` named a folder of its own that held the column's model file by a second path (an NTFS hard
link to the file in the default model folder, `%USERPROFILE%\models`: the same file, so the same bytes), so that the
job's cache purge and the runs' cache writes touched only that folder. Each job removed the model's two GPU cache files
it found there (12 and 742 MB) before its first run; in each sitting run 1 started with none and wrote them (its host
log's `gpuCacheWrite` reads true), and runs 2 to 5 started with them in place (false). Their `host.json` lists the
same 187 engine files as the `2026-11-07-windows-gpuwait-*` sittings, every run was clean and quiet, no run took a GPU
read while its engine ran, no SSH connection opened during a run (`sshConnections`), and every run's
`gpuReadToStartSeconds` reads 1.996 to 2.041 s.
`litert-lm-gpu` read `out` in both (cold spreads 11.04 and 6.04 %): the cold decode of 128 tokens took 1.506 to 1.678 s
in the first sitting's four counted runs and 1.494 to 1.587 s in the second's, and in all eight the engine's `Selected
adapter:` line came 1.21 to 1.30 s after its first log line (1.20 to 1.27 s in `-on-a1` and `-on-a2`). Its warm decode
medians (the five runs' second conversations, run 1's included) lay 0.05 % apart, with warm spreads of 8.51 and
12.10 %. All four sittings of this row with the wait read `out` (cold spreads 11.62, 10.90, 11.04 and 6.04 %); what
moves its cold decode from run to run with the wait is not established.

Five more sittings each ran one model's four GPU rows of the column (a cells file of that model's four GPU lines of
`matrices/dashboard-windows-v1.cells`, runs=3, 12 runs each) with the job's 2 s wait, on 2026-11-08 JST:
`2026-11-08-windows-gpu-q06` (Qwen3 0.6B) at 14:57, `-q17` (Qwen3 1.7B) at 16:00, `-e2b` (Gemma 4 E2B) at 16:12, `-q4b`
(Qwen3 4B) at 16:51 and `-e4b` (Gemma 4 E4B) at 17:58; since then each of the column's 20 GPU cells shows one of them.
As in `-on-c1` and `-on-c2`, `BENCH_WINDOWS_MODEL_DIR` named a folder of its own that held the ten model files of these
rows by a second path (NTFS hard links to the files in `%USERPROFILE%\models`); the ten files' sha256, read on the
machine after the first sitting, equal the ones the Hub lists for them. Their `host.json` lists the same 187 engine
files as `-on-c2`, every run was clean and quiet, no run took a GPU read while its engine ran, and every run's
`gpuReadToStartSeconds` reads 1.997 to 2.044 s on the NVIDIA rows and 2.369 to 2.404 s on `litert-lm-gpu-igpu`. In each
sitting run 1 of each LiteRT-LM row started without the model's GPU cache files and wrote them (`gpuCacheWrite` true;
before the `litert-lm-gpu-igpu` row's run 1 the job removed the two the NVIDIA row had written, `gpuCachePurge`, and at
the job's end the two that row wrote), and runs 2 and 3 started with them in place (false). Three SSH connections opened
during runs, each from the driving machine's reachability check (one every 5 minutes): 10.6 s into `-q4b`'s second
`litert-lm-gpu-igpu` run, 3.9 s into its first `llama.cpp-cuda` run (the row's first process, not counted) and 0.4 s
before the job launched the engine of `-e4b`'s second `llama.cpp-gpu` run (`atSeconds` -0.4; the record counts it). Each
of the two counted runs read the lower cold decode of its row's two counted runs, and both rows read `out`; the four
other cells that read `out` (below) had no connection in their runs, so whether a connection moved a run is not
established.

The sitting the column's cell showed before these was, for the Qwen3 and Gemma 4 E4B cells, `2026-11-07-windows-e4b`
(`2026-11-07-windows-igpu` on `litert-lm-gpu-igpu`), a day earlier and without the wait, and for Gemma 4 E2B `-on-c2` on
`litert-lm-gpu` (with the wait, about four hours earlier), `-off-a2` on `llama.cpp-gpu` and `-off-b2` on
`litert-lm-gpu-igpu` and `llama.cpp-cuda` (without it, about 12 and 9 hours earlier). Against it, the cold decode median
moved by -12.07 to +0.30 % in the 11 cells whose cold spreads stayed within 5 % in both: on `litert-lm-gpu` by -3.45,
+0.30 and +0.24 % (Qwen3 1.7B, Qwen3 4B, Gemma 4 E4B), on `litert-lm-gpu-igpu` by -0.51 % (Qwen3 1.7B), on
`llama.cpp-gpu` by -1.26, -11.96 and -0.30 % (Qwen3 0.6B, Qwen3 1.7B, Gemma 4 E2B) and on `llama.cpp-cuda` by -2.08,
-12.07, -5.93 and -2.14 % (Qwen3 1.7B, Gemma 4 E2B, Qwen3 4B, Gemma 4 E4B). Six cells read `out` in the new sittings:
Qwen3 0.6B's `litert-lm-gpu` (cold spread 21.59 %) and `llama.cpp-cuda` (5.87 %), Qwen3 4B's `litert-lm-gpu-igpu` (12.02
%) and `llama.cpp-gpu` (20.39 %), and Gemma 4 E4B's `litert-lm-gpu-igpu` (9.29 %) and `llama.cpp-gpu` (18.04 %); five
had read `out` in the sitting before: Qwen3 0.6B's `litert-lm-gpu-igpu` and `llama.cpp-cuda`, Gemma 4 E2B's
`litert-lm-gpu` and `litert-lm-gpu-igpu`, and Gemma 4 E4B's `litert-lm-gpu-igpu` (two cells, Qwen3 0.6B's
`llama.cpp-cuda` and Gemma 4 E4B's `litert-lm-gpu-igpu`, read `out` in both). The cold prefill medians, which the spread
rule does not gate, moved by -47.27 to +29.70 % over the 20 cells. The wait alone can make a GPU row's later sitting
read lower on the same machine (the eight `2026-11-07-windows-gpuwait-*` sittings above); how much of each difference
the wait, the day or anything else made is not established.

Three more sittings retook, once each, the six cells that read `out` in those five, under a rule set before they ran:
one retake per cell, runs=3, and the retake becomes the cell's latest sitting whatever its spread reads, with no second
retake on its spread. Each ran only one model's two `out` rows (a cells file of those two lines of
`matrices/dashboard-windows-v1.cells`, in that order, 6 runs and 9 records), so each `litert-lm-gpu-igpu` row ran first
in its sitting, where in the five it ran after the model's `litert-lm-gpu` row. They ran with the job's 2 s wait, on
2026-11-09 JST: `2026-11-08-windows-gpu-q06-r2` (Qwen3 0.6B's `litert-lm-gpu` and `llama.cpp-cuda`) at 00:15 and
`-q4b-r2` (Qwen3 4B's `litert-lm-gpu-igpu` and `llama.cpp-gpu`) at 00:20 in one hold of the machine, and `-e4b-r2`
(Gemma 4 E4B's `litert-lm-gpu-igpu` and `llama.cpp-gpu`) at 01:34 in a second, there being less time left in the first
hold than that sitting needed (each is named for the UTC date of its records). As in the five, `BENCH_WINDOWS_MODEL_DIR`
named a folder of its own that held the six model files of these rows by a second path, and their sha256, read on the
machine at the start of each hold, equal the ones the Hub lists for them. Their `host.json` lists the same 187 engine
files as `-on-c2`, every run was clean and quiet, no run took a GPU read while its engine ran, and every run's
`gpuReadToStartSeconds` reads 1.998 to 2.040 s on the NVIDIA rows and 2.373 to 2.442 s on `litert-lm-gpu-igpu`. Run 1 of
each LiteRT-LM row started without the model's GPU cache files and wrote them, and runs 2 and 3 started with them in
place. Two SSH connections opened during runs, both from the driving machine's reachability check (one every 5 minutes):
30.1 s into `-q4b-r2`'s second `litert-lm-gpu-igpu` run and 8.9 s into `-e4b-r2`'s third; the first of these runs read
the lower cold decode of its row's two counted runs, the second the higher.

| cell | cold spread, the earlier sitting | cold spread, the retake |
|---|---|---|
| Qwen3 0.6B `litert-lm-gpu` | 21.59 % | 1.08 % |
| Qwen3 0.6B `llama.cpp-cuda` | 5.87 % | 1.80 % |
| Qwen3 4B `litert-lm-gpu-igpu` | 12.02 % | 10.38 % |
| Qwen3 4B `llama.cpp-gpu` | 20.39 % | 22.88 % |
| Gemma 4 E4B `litert-lm-gpu-igpu` | 9.29 % | 3.69 % |
| Gemma 4 E4B `llama.cpp-gpu` | 18.04 % | 0.00 % |

Four of the six read within 5 % in the retake, and the column shows their retake without the column's spread mark;
Qwen3 4B's two cells read `out` again, and the column shows their retake with it (`⚠ N%`, N the cold spread). Since
every one of these cells read `out` in its earlier sitting, no change of a cold decode median is given against it (as
above, a median is compared only where both sittings stayed within 5 %). The cold prefill medians, which the spread
rule does not gate, moved by -32.90 to +30.77 % against the earlier sittings.
