# ONNX Runtime GenAI — arm v1

## What the arm runs

[ONNX Runtime GenAI](https://github.com/microsoft/onnxruntime-genai) (the
`onnxruntime-genai` runtime of the cells grammar) on the published GenAI folders
of `onnx-community/Qwen3-{0.6B,1.7B,4B}-ONNX`, the dashboard's two text tasks
(`short-chat`, budget 128; `long-context-1024-gen256`, budget 256) at
`context-tokens=2048`. Cells: `matrices/dashboard-ortgenai-v1.cells`.

| platform | arm (`runtime` in the records) | execution provider | driver |
|---|---|---|---|
| Mac | `onnxruntime-genai-cpu` | CPU EP | `scripts/ortgenai_mac.py` |
| Mac | `onnxruntime-genai-webgpu` | WebGPU plugin EP (`onnxruntime-ep-webgpu`, Dawn on Metal) | `scripts/ortgenai_mac.py` |
| Android | `onnxruntime-genai-cpu` | CPU EP | `android/bench/run_cell.py` + `ortgenai_run` |
| iPhone | `onnxruntime-genai-cpu` | CPU EP | not wired yet (rows disabled) |

`backend=` is arm identity, as for LiteRT-LM. The regime is each platform's (see
"Regime" below): warm runs headline on the Mac, cold on Android. Gemma 4 E2B / E4B rows stay in
the cells file as `exclude=no-published-genai-model-official-builder-routes-gemma4-to-moe`:
no published GenAI folder for them, and the official model builder routes Gemma
4 to its MoE path (the lane's check, 2026-10-07).

Not run in v1: the Android and iPhone GPU / NPU. The release AAR and XCFramework
are CPU builds and the published folders are CPU, WebGPU and CUDA builds; the
lane found no published route for them (not verified beyond that check).

## Pins and sources

- Mac: PyPI `onnxruntime-genai==0.17.1` (commit 83de55a1), `onnxruntime==1.30.0`,
  `onnxruntime-ep-webgpu==0.4.0`, Python 3.14, in a private venv
  (`ORTGENAI_PYTHON`, default `~/.venvs/ortgenai-0.17.1/bin/python`; it also needs
  `huggingface_hub`, `onnx` and `jsonschema`). The driver refuses any other
  installed version and records every engine library's sha256
  (`provenance.engineLibraries`); `engineArtifact` = the GenAI dylib's sha256.
- Android: the release `onnxruntime-genai-android-0.17.0.aar`
  (`libonnxruntime-genai.so`, and `libmat.so`, the telemetry SDK it links) and
  Maven `com.microsoft.onnxruntime:onnxruntime-android:1.30.0`
  (`libonnxruntime.so`, which the AAR does not ship: GenAI dlopens it from
  `ORT_LIB_PATH`), both fetched by sha256 in `android/ortgenai/build_android.sh`,
  which also builds the harness driver `ortgenai_run` and the upstream
  `model_benchmark`. Pins: `android/engine-pins.json` "onnxruntime-genai"
  "0.17.0" — `ortgenai_run` and the three libraries are the witness; a library
  that is not the pin's stamps `unknown`. Device layout: `android/README.md`.
- iPhone: the release `onnxruntime-genai-ios-0.17.0.zip` (XCFramework,
  ios-arm64; sha256 in `environment.lock.json`), for the round that wires the app.
- Models: each repo at its own commit "Add optimized models for ORT GenAI (#3)"
  (2026-04-20, authors Xenova and kvaishnavi):
  0.6B `da1453100cf3ff33ef56d17983fc7a8648706db6`, 1.7B
  `cc6a06a21d614e9b8e92a6adfab1074d4e7d2438`, 4B
  `98ddba15d05dede4435afb63f13280abcdbc2a48` (cells `revision=`). Folders:
  `onnxruntime/cpu_and_mobile/cpu-int4-kld-block-128` (CPU) and
  `onnxruntime/webgpu/webgpu-int4-kld-block-32` (WebGPU); the 4B folders keep the
  weights in `model.onnx.data`. Only the folder a cell names is fetched
  (`snapshot_download` with that folder's pattern).

## Recipe

`model.quantization` is read from the folder's `model.onnx`, never typed:
`scripts/ortgenai_recipe.py` reads the MatMulNBits / GatherBlockQuantized
attributes (bits, block size, accuracy level), the dtypes of their scales and
zero points, the KV and logits dtypes and the folder's `config.json`
quantization block, and `--register` writes the label into
`models/ortgenai-recipes.json`, keyed by (model id, folder, `model.onnx`
sha256). Both drivers look the label up there and refuse a folder without an
entry, printing the command that registers it. Registered so far: the two 0.6B
folders; the 1.7B and 4B entries are written when those folders are first
fetched.

"int4" alone would be wrong (quant-label-rule): the 0.6B CPU folder has 197
MatMulNBits, 92 int4 and 105 int8 (per-layer int8 overrides as published),
block 128, asymmetric uint8 zero points, fp32 scales, accuracy_level 4, an int8
block-128 GatherBlockQuantized embedding, fp32 activations and KV; the WebGPU
folder 91 int4 / 106 int8, block 32, fp16 scales, an int8 block-32 embedding,
fp16 activations and KV. The two folders are different recipes, so the CPU and
WebGPU arms do not run the same weights.

## Regime

The arm runs the regime of the other arms on each platform
(`methodology/fairness-rules.md` cold-warm-split: a table that compares engines
holds the regime fixed).

- Mac: one engine process per cell, as `yardstick run --runs N`. It loads the
  model and the tokenizer once and generates the cell's `runs=` times (4 by
  default) from the same prompt, back to back (`--pause`, the runner's
  `ORTGENAI_PAUSE`, default 0), each generation on a new generator, so each run
  allocates its own KV cache. Run 1 is the process's first generation: `coldRun`
  true, `conditions.regime` "cold (first generation in the process)". Runs 2..N:
  `coldRun` false, "warm (generation k of N in one process)". The dashboards
  headline the median of the warm runs, as for every Mac arm; run 1 stays a
  record, reported apart. Every run's record carries its own prefill, TTFT,
  decode and memory (its own generation window) and `conditions.runIndex`;
  `firstEver` marks run 1 only. A run that fails stays a failed record; the runs
  after one that ended the engine process are not attempted (no record), as when
  a yardstick run throws.
- Android: every run is a fresh `ortgenai_run` process (cold), as for every
  Android arm (`methodology/android.md`).

Until 2026-10-08 the Mac driver ran one process per run, so every Mac record is
cold: the 2026-10-07 smoke and wiring-smoke campaigns. Those records have no
warm run, so a Mac table reads their cells as "records without a decode figure".

## Timing and memory

The cut points of upstream `benchmark/c` `model_benchmark`, on every platform:
prefill tok/s = prompt tokens / the wall clock of `AppendTokenSequences`
(Python `append_tokens`); TTFT = that plus the first `GenerateNextToken` (a
greedy pick from the prefill logits); decode tok/s = (generated tokens − 1) /
the summed wall clock of the later `GenerateNextToken` calls. Generation stops
at EOS or the task's budget — no `min_length` (`model_benchmark` sets
`min_length` = prompt + generation length, a forced-length tool; the text-task
cells need a run that stops the way every other arm's does, hence the harness
driver `ortgenai_run` on Android). Greedy (`do_sample` false), the folder's
`chat_template.jinja` as one user turn, no system prompt (Qwen3 thinking on),
`max_length` = `context-tokens`. The definitions travel in every record
(`conditions.metricDefinitions`); stopReason `stop` = EOS, `length` = the budget.

Memory: on the Mac, the engine process's `phys_footprint` sampled every 100 ms
from the run's generator creation to its last token (high-water and median, MiB),
the Apple BenchmarkRunner basis; on Android, the runner's VmRSS /
VmHWM sampler of the engine process (`rssBasis`). Both folders set
`past_present_share_buffer`, so GenAI allocates the KV cache for the whole
`max_length` when the generator is created (zero-filled on the CPU): the memory
figures include a 2048-token KV cache whatever the prompt. On the Mac CPU 1K
cell, `max_length` 40960 (the folder's own default) instead of 2048 raised the
peak by 8,516 MiB, the computed size of the fp32 KV for the extra 38,912 tokens
(8,512 MiB) — which is why every row pins `context-tokens=2048`.

## Telemetry

The official builds ship the 1DS telemetry SDK, on by default — in the GenAI
library and, on the Mac, in the ONNX Runtime library and the WebGPU plugin as
well. `ORT_DISABLE_TELEMETRY=1` in the environment before the engine
initialises keeps the uploader, the events and the device id off for the
process; the drivers set it for every engine process and also call the API
switch (`disable_telemetry_events()` / `OgaSetTelemetryEnabled(false)`), and
`ortgenai_run` refuses to start without it. On the Mac, each record carries the
evidence: the engine process's socket fds every 100 ms (none) and the SDK's
store (`~/Library/Application Support/Microsoft/DeveloperTools/.onnxruntime/`)
before and after the run (unchanged); a run that changes either fails. On
Android, `conditions.engineSockets` counts the engine's sockets by kind (unix /
inet). The one telemetry-on comparison run (2026-10-07, evidence only) created
`onnxruntime-genai.db{,-shm,-wal}` in that store and appended to
`onnxruntime.db-wal`: a short process queues its events there, and the next
process that runs with telemetry on may send them. Any process that imports
`onnxruntime` without the variable counts as such a process, so
`scripts/ortgenai_mac.py` sets it for its own process before any import.

## Text check

A `long-context-*` run carries `conditions.textCheck` =
`android/bench/parsers.text_integrity` of its decoded text, the screen the
LiteRT-LM context-prompt launches carry; a short-chat run is screened like every
Apple arm, by the runner's post-capture gate (`cell_gate.degenerate` on
`outputSample`). The bar is the same for every arm and is not raised for this
one. A reader should know one thing it does not catch: on the CPU folder the
0.6B model's greedy 1K thinking ends in a loop of one or two sentences over its
last ~70 tokens (read on the Mac and on the Galaxy S26, 2026-10-07); the screen
passes it, so those cells are throughput figures whose text loops near the budget.

## WebGPU identity (Mac)

Each WebGPU record carries `model.device_type` WebGPU from the engine, the
plugin dylib among the process's loaded images (`provenance.onnxruntimeImages`)
and the Metal GPU time the engine process accrued during generation
(`metrics.gpuMillisecondsDuringGeneration`, IOKit per pid). ONNX Runtime's own
EP registration and node-placement lines need `ORTGENAI_ORT_VERBOSE_LOGGING=1`,
which logs every program launch (about 520 lines per token) and changes the
timing, so they are taken in separate identity runs (`--ort-verbose`), never in
a measured one: 340 of 346 nodes on the WebGPU EP, the attention-mask subgraph's
six on the CPU (2026-10-07).

## Run one cell

```bash
# Mac (the venv above); one cell of the cells file, or the whole Mac set
~/.venvs/ortgenai-0.17.1/bin/python scripts/ortgenai_mac.py --model-id onnx-community/Qwen3-0.6B-ONNX \
  --file onnxruntime/cpu_and_mobile/cpu-int4-kld-block-128 \
  --revision da1453100cf3ff33ef56d17983fc7a8648706db6 --backend cpu --task short-chat \
  --context-tokens 2048 --runs 4 --output results/raw/<campaign>/<cell>.jsonl
./bench matrix matrices/dashboard-ortgenai-v1.cells --platform mac
scripts/bench_matrix_mac.sh run matrices/dashboard-ortgenai-v1.cells --dry-run   # the plan, no engine

# Android (runtime dir pushed per android/README.md)
BENCH_CPU_MASK= ./bench matrix matrices/dashboard-ortgenai-v1.cells --platform android

# a new folder: register its recipe first (reads model.onnx; the Hub commit for the note)
~/.venvs/ortgenai-0.17.1/bin/python scripts/ortgenai_recipe.py <folder in the HF cache> \
  --model-id onnx-community/Qwen3-1.7B-ONNX --folder onnxruntime/cpu_and_mobile/cpu-int4-kld-block-128 \
  --revision cc6a06a21d614e9b8e92a6adfab1074d4e7d2438 --register
```

`ORTGENAI_SMOKE=<note>` stamps a Mac run as a smoke instead of a measurement;
`--dry-run` on the driver shows each run, the folder's cache state and its label.

## Status (2026-10-08)

Wired on the Mac and Android: cells, both drivers, the records' shape, the
summary, the bench table and the team page (not measured until a sitting
records the cells). Every number so far is a smoke (the Mac 2026-10-07 runs and
the wiring smoke, the Mac 2026-10-08 warm-regime smoke — one engine process, run 1
cold and runs 2-4 warm — and the Galaxy S26 driver smoke), none a dashboard
measurement.
Open: the 1.7B / 4B recipe entries; the protocol rows (`model_benchmark` on
Android, a Mac entry); the iPhone adapter; `streamed_bytes` for the six folders
in `models/artifact-bytes.json` (the int8 embedding table is gathered per token,
not streamed, and is still counted, so this arm's bandwidth column reads high);
the weekly file (an owner decision).
