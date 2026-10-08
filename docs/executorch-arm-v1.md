# ExecuTorch on Android and Mac — arm v1

## What the arm runs

ExecuTorch's own C++ runner for the model's family, built from the tagged source and
unpatched (official-sdk rule): `llama_main` (`examples/models/llama`, `TextLLMRunner`) for
Qwen 3, `gemma4_e2e_runner` (`examples/models/gemma4`) for Gemma 4, on the XNNPACK CPU
backend. One runner process per run. The runner is picked from the model
(`android/bench/parsers.py` `executorch_runner_for`), and the recipe.json beside the `.pte`
must name the same exporter; a cells row never names it.

The models are **own exports**: the ExecuTorch source tree's own exporters and example
recipes, run by us. They are not published ExecuTorch artifacts, and the arm never mixes
them with published `.pte` files. The arm id is `executorch-<backend>` on every platform
(`executorch-xnnpack`; `executorch-mlx` on the Mac has cells since 2026-10-08, see "GPU
delegates on the Mac"; `vulkan` / `qnn` on Android and `metal` / `coreml` on the Mac are reserved
names, nothing runs on them yet).

Cells: `matrices/dashboard-executorch-v1-android.cells`, `matrices/dashboard-executorch-v1-mac.cells`
(the dashboard model set: Qwen3 0.6B / 1.7B / 4B, Gemma 4 E2B / E4B × short-chat and the 1K text
task). Runners: `android/bench/run_cell.py --runtime executorch` (through
`android/bench/run_campaign.py`), `scripts/executorch_mac.py` (through
`scripts/bench_matrix_mac.sh`). The iPhone rows (`matrices/dashboard-executorch-v1-ios.cells`)
run in a second build of the iPhone app with ExecuTorch's Swift package linked (section "iPhone").

## Pins and artifact provenance

- Engine source: tag `v1.5.1` (`3b60683923245cf472b7323426920e15623ba361`, 2026-09-18). The
  tree must sit in a directory named exactly `executorch` (v1.5.1 `CMakeLists.txt` stops
  otherwise, pytorch/executorch#6475). Registry: `environment.lock.json` `arms.executorch`
  (Mac runner sha256s) and `android/engine-pins.json` `executorch.v1.5.1` (Android).
- Android build (`android/scripts/build_executorch_llama_main.sh`): the llama README "Step 4",
  two CMake stages, NDK r28c, `android-23`, Release, XNNPACK with the optimized, quantized and
  LLM kernels, ET_LOG on through the posix PAL (stderr). One directory per backend:
  `android/bin/executorch-v1.5.1/` (XNNPACK) and `android/bin/executorch-v1.5.1-vulkan/`, each
  with `BUILD_INFO.json` and `SHA256SUMS`. Push a directory by hand, as the other engines are
  pushed: `adb push android/bin/executorch-v1.5.1 /data/local/tmp/llmbench/`. The runner stamps
  `engineVersion` from the on-device binary's sha256 (`<runner>_sha256` for the XNNPACK build,
  `<runner>_<backend>_sha256` for another); an unmatched binary stamps `unknown (…)`.
  `gemma4_e2e_runner` is built for Android by the same script since 2026-10-08 (the tag's
  `examples/models/gemma4` runner sources with the CMake list under
  `scripts/executorch/gemma4_runner/`, the same tag and options as `llama_main`) and pinned
  beside it. The Android matrix driver is `android/scripts/executorch_matrix_android.sh`
  (one model per queued hold, the cells file's rows one at a time, the `.pte` pushed for
  the slot and removed after it; the phone's launch mask, hold files and campaign name come
  from its entry in `ops/dashboard-v1/schedule.json`, `--plan` prints them).
- The driver's skin gate: before each unit it reads `dumpsys thermalservice` and waits until the
  `SKIN` value of the "Current temperatures from HAL" block is at most `SKIN_MAX_C` (the sensor's
  first hot throttling threshold in the same dump minus 2.0 °C, 36.0 on the Galaxy S26; 36.0 when
  the dump has none), for up to `SKIN_WAIT` (900 s). A unit still above it is not started and the
  window goes back; three such windows in a row stop the driver. The "Cached temperatures" block
  holds the value of the HAL's last throttling-status change, not the temperature now (on the S26
  it reads 37.9 °C whenever the status is 0), so it is logged beside the current value and gates
  only with `SKIN_SOURCE=cached`. `<state_dir>/skin_gate.tsv` has one row per gate (both readings,
  the threshold, the seconds waited, the result). `LAUNCH_PROBES` (e.g. `3 10`) reads the whole
  thermal dump and every policy's `scaling_cur_freq` / `scaling_max_freq` that many seconds after
  each launch's adb shell starts (two adb shells per launch; the campaign's `LAUNCH_PROBES.txt`
  names the units that had them).
- Mac build (`scripts/executorch/build_llama_main_mac.sh`): `cmake --workflow --preset
  llm-release`, then `cmake --workflow --preset llama-release` in `examples/models/llama`
  (Release; ET_LOG compiled out; the preset also builds Core ML and the torchao kernels,
  XNNPACK with KleidiAI); `gemma4_e2e_runner` from `examples/models/gemma4` in the same
  `cmake-out`. Copy both runners to `.build/executorch-v1.5.1/` (or point
  `ET_MAC_RUNNER_DIR` at a directory holding them); `scripts/executorch_mac.py` stamps
  `engineVersion` from the binary's sha256 against the lock.
- Export venv: CPython 3.12, `executorch==1.5.1` (PyPI wheel; its export sources are
  byte-identical to the tag's tree), `torch==2.14.0` (the tag's `torch_pin.py`),
  `torchao==0.18.0`, `transformers==5.0.0rc1`.
- Qwen 3 (`scripts/executorch/export_qwen3.py`): the tree's `convert_weights.py`, then
  `python -m executorch.extension.llm.export.export_llm --config
  examples/models/qwen3/config/qwen3_xnnpack_q8da4w.yaml` (unchanged) with `base.model_class`,
  `base.params`, `base.checkpoint` and `export.output_name`.
- Gemma 4: `examples/models/gemma4/export_gemma4.py --quantize 8da4w+emb8 --max_seq_len 2048
  --no-audio --no-vision [--variant e4b]` (text decoder only).
- Each `.pte` has a `<name>.recipe.json` beside it: ExecuTorch version and commit, the config
  verbatim, the checkpoint's HF revision and file hashes, the commands, the `.pte` sha256 and
  size, the tokenizer it was exported with, the host. The runners refuse an artifact whose
  sha256, tokenizer or recipe facts disagree with it.

## Recipes

| Cells `recipe=` | Runner | Record label (`model.quantization`) |
|---|---|---|
| `et1.5.1-xnnpack-8da4w-g128-emb8` | `llama_main` | 8da4w: int8 dynamic per-token asymmetric activations x int4 symmetric weights, group 128, HQQ scale-only (every Linear incl. lm_head); embedding int8 per-row (embedding_byte); fp32 compute and KV cache; own export, ExecuTorch 1.5.1 |
| `et1.5.1-gemma4-xnnpack-8da4w-g128-emb8` | `gemma4_e2e_runner` | 8da4w+emb8 (export_gemma4.py): int8 dynamic activations x int4 weights, group 128, HQQ scale-only on the Linear layers (a Linear whose input width is not a multiple of 128 stays unquantized); embeddings int8 per-row; fp32 compute and KV cache; text decoder only; own export, ExecuTorch 1.5.1 |
| `et1.5.1-mlx-4w-g128-emb8` | `llama_main` (MLX build) | 4w: int4 symmetric weight-only, group 128, HQQ scale-only (every Linear incl. lm_head), fp32 activations; embedding int8 per-row (embedding_byte, outside the delegate); fp32 compute and KV cache; MLX delegate; own export, ExecuTorch 1.5.1 |
| `et1.5.1-vulkan-8da4w-g128-emb8` | `llama_main` (Vulkan build) | 8da4w: int8 dynamic per-token asymmetric activations x int4 symmetric weights, group 128, HQQ scale-only (every Linear incl. lm_head); embedding int8 per-row (embedding_byte, outside the delegate); fp32 compute and KV cache; Vulkan delegate; own export, ExecuTorch 1.5.1 |

The labels state what the export code and its recipe.json establish (`parsers.EXECUTORCH_RECIPES`
lists the recipe.json facts each label is checked against). Qwen 3: the yaml sets no
`group_size`, and v1.5.1 `quantize.py` uses 128 for `8da4w` when none is given (export log
`block_size=(1, 128)`). Gemma 4: `quant_utils.apply_linear_quantization` passes group 128 and
`skip_incompatible_shapes` to `extension/llm/export/quantize.py`, whose `8da4w` is torchao's
`Int8DynamicActivationIntxWeightConfig` with `hqq_scale_only`. The KV cache is allocated at
export for 2048 tokens on every run (`max_context_length` = 2048; Gemma 4 `--max_seq_len 2048`).

Staged exports read for this page (the rest: the recipe.json beside each `.pte` is the record):

| Model id | `.pte` sha256 | Checkpoint |
|---|---|---|
| `own-export/Qwen3-0.6B-ET1.5.1-xnnpack-8da4w-emb8-ctx2048` | `2517e337fbe6da0850a9bc1dfbe015690def3aedc362534429744735e9e110a3` | Qwen/Qwen3-0.6B `c1899de289a04d12100db370d81485cdf75e47ca` |
| `own-export/gemma-4-E2B-it-ET1.5.1-xnnpack-8da4w-emb8-ctx2048` | `f1db0147579216e39dad7c747ebc9331fb44b9165330805ee2bb12a1a213f384` | google/gemma-4-E2B-it `3e22461f65e89153144f8adb70e3b8c2cc9845a7` |
| `own-export/Qwen3-0.6B-ET1.5.1-mlx-4w-emb8-ctx2048` | `4d1777e5954e46fd129d7374db11797499b43395ede79dba83325d3f7930bd03` | Qwen/Qwen3-0.6B `c1899de289a04d12100db370d81485cdf75e47ca` |
| `own-export/Qwen3-0.6B-ET1.5.1-vulkan-8da4w-emb8-ctx2048` | `3b4bc033998c254ea797c0919e218509fec9a4bb989ff0d87d40263df0d1a0c2` | Qwen/Qwen3-0.6B `c1899de289a04d12100db370d81485cdf75e47ca` |

## Record fields and definitions

The runners are not patched: the numbers are each runner's own statistics, recomputed from
its own clock where it prints one. `provenance.definitions` carries the runner's definitions
verbatim; they differ between the two runners.

`llama_main` (`extension/llm/runner/stats.h`, the `PyTorchObserver` line):

```
prefill tok/s = prompt_tokens / (prompt_eval_end_ms - inference_start_ms) * 1000. The window opens before the runner tokenizes the prompt (TextLLMRunner::generate sets inference_start_ms, then encodes), so prefill includes tokenization.
TTFT ms = first_token_ms - inference_start_ms = the same window (first_token_ms is taken when prefill returns, before the first token is decoded to text).
decode tok/s = generated_tokens / (inference_end_ms - prompt_eval_end_ms) * 1000, generated_tokens = tokens of the decode loop; the reply has one more token, the one prefill sampled.
cold = one generation in a fresh llama_main process (no --warmup). warm = llama_main --warmup: one unmeasured generation of the same prompt and max_new_tokens in the same process, stats and KV position reset, the second generation measured.
Clock: integer milliseconds (extension/llm/runner/util.h time_in_ms).
```

`gemma4_e2e_runner` (`runner/gemma4_stats.h`, the "Gemma 4 Performance Report" on stderr):

```
prefill tok/s = prompt tokens / prefill ms * 1000, prefill = the one text_decoder forward over the prompt (Gemma4Runner::generate_text opens the window after it has tokenized the prompt, so prefill excludes tokenization).
TTFT ms = the same prefill window (Gemma4Stats::time_to_first_token_ms, text only).
decode tok/s = generated tokens / generation ms * 1000, generation = from after the first token is sampled from the prefill logits to the end of the decode loop (Gemma4Runner::decode_loop); generated tokens = every token of the reply, the prefill-sampled one included, so the window holds one forward pass fewer than the count.
cold = one generation in a fresh gemma4_e2e_runner process; the runner has no warmup option, so there is no warm regime.
Clock: std::chrono::steady_clock; the report prints ms with one decimal under 1 s and seconds with two decimals from 1 s on (10 ms resolution).
```

| Field | Meaning |
|---|---|
| `runtime`, `engineVersion`, `engineArtifact` | `executorch-<backend>`; the tag whose pin holds the runner binary's sha256; the sha256 (Mac: `<runner> sha256:<hex>`) |
| `metrics.promptTokensPerSecond`, `decodeTokensPerSecond`, `firstTokenLatencyMS` | the definitions above; a rate whose window is 0 ms stays absent |
| `metrics.promptTokenCount`, `generatedTokenCount` | the runner's counts (llama_main: the decode loop's, the reply has one more; gemma4_e2e_runner: the reply's) |
| `metrics.loadTimeSeconds` | the runner's model load, outside every rate's window |
| `metrics.memoryPeakResidentMB` | Mac: `os.wait4` ru_maxrss of the runner process / 2^20 (MiB, load included). Android: the larger of the sampler's VmHWM reads (`provenance.rssBasis`) and the runner's own peak, `memoryPeakEngineReportedMB` (llama_main: ru_maxrss at the end of generation; gemma4_e2e_runner: its largest VmRSS read per decode step) — a launch can end between two 0.5 s reads |
| `metrics.coldRun`, `conditions.warm` | run 1 of a Mac cell and every Android run: cold; Mac runs 2..N (llama_main `--warmup`): warm |
| `conditions.contextTokens` / `contextBudget`, `contextSource` | 2048; Android llama_main: the runner's own log (`Metadata: get_max_context_len`), else the recipe.json (Gemma 4's `.pte` has no metadata method; its KV cache buffers were read as `[1, 1, 2048, …]` when the export was inspected) |
| `conditions.chatMode`, `thinkingPolicy` | llama_main: the prompt rendered once on the host with the model's chat template (HF `apply_chat_template(add_generation_prompt=True)`, template defaults: Qwen 3 thinks); gemma4_e2e_runner: the repository prompt as `--prompt`, the runner's built-in turn template, no thinking control |
| `conditions.cpuThreads`, `cpuThreadsPolicy` | `--cpu_threads` is never passed: the engine's heuristic (cpuinfo `get_num_performant_cores`); the Android build logs the pool size (8 on the Galaxy S26, 9 on the Pixel 8a: on both phones the log shows the per-CPU `midr_el1` fallback of `extension/threadpool/cpuinfo_utils.cpp`, whose efficiency-core list (A520 / A53 / A55 / A57) has no A510). The Mac stock build logs nothing; a logging build of the same source read 16 on the M4 Max (it counts no efficiency core) |
| `conditions.textCheck` | `android/bench/parsers.text_integrity` over the runner's text (llama_main: stdout after the prompt echo, cut before the stats line; gemma4_e2e_runner: stdout); a FAIL pools into no number |
| `conditions.protocolFlags` | `echo-mismatch`, `stats-rate-mismatch` (a printed rate the recomputation does not reproduce), `prompt-token-count-mismatch` (llama_main against the host tokenizer's count), `output-budget-exceeded`, `context-budget-exceeded`, `allocation-witness-mismatch`, and Android's `cpu-capped` |
| `provenance.statsLine` / `statsReport` | the runner's statistics verbatim |
| `provenance.recipe`, `recipeSha256`, `recipeAlias`, `promptFile`, `promptSha256`, `tokenizerSha256` | the inputs of the run |

## GPU delegates on the Mac (round r7-gpu, 2026-10-08)

The same Qwen 3 yaml is lowered to another delegate by export_llm overrides:
`scripts/executorch/export_qwen3.py --set KEY=VALUE` appends them after the yaml and the
recipe.json keeps them (`config_overrides` verbatim, `export_args` typed; the cells' `recipe=`
alias checks `export_args`, a key it maps to None must not be overridden). `export_llama_lib`
takes its XNNPACK branch first, so every such export turns `backend.xnnpack.enabled` off.
Identity is what the artifact and the binary carry, not a log line: the `.pte`'s delegate
(`scripts/executorch/pte_inspect.py`: delegate id and call count, the operators left outside)
and the backend ids compiled into the runner.

- **MLX** (arm `executorch-mlx`, Apple GPU). Export: `--set backend.xnnpack.enabled=false --set
  ++backend.mlx.enabled=true --set quantization.qmode=4w --set ++quantization.group_size=128`.
  The yaml's 8da4w does not lower: the MLX partitioner has no handler for its dynamic
  activation quantization (`torchao.choose_qparams_affine` / `quantize_affine` /
  `dequantize_affine`, 197 each on Qwen3 0.6B) and `to_executorch` stops at `Missing out
  variants: {'torchao::quantize_affine', 'torchao::choose_qparams_affine',
  'torchao::dequantize_affine'}`. So the MLX recipe is weight-only int4 (`4w` = torchao
  `IntxWeightOnlyConfig`, symmetric, `hqq_scale_only`, every Linear); group 128 is set because
  `4w` defaults to 256. The `.pte`'s `forward` is one `MLXBackend` call; the yaml's embedding
  quantization (`embedding_byte`) stays outside it on the CPU kernels. Runner:
  `scripts/executorch/build_llama_main_mac_mlx.sh` (`cmake --preset mlx-release` into
  `cmake-out-mlx`, then `examples/models/llama` with the `llama-mlx` preset's cache; the MLX
  submodule at the tag's pin 1f8e74e3 = MLX v0.32.2, built by the delegate with
  `MLX_METAL_JIT=ON`), copied with `mlx.metallib` to `.build/executorch-v1.5.1-mlx/`; its
  sha256 is `arms.executorch.mac.backends.mlx` in `environment.lock.json`. The binary carries the
  `MLXBackend` id and no XNNPACK. With the JIT, a kernel outside the small metallib is compiled
  from source the first time a process uses it, inside run 1 (cold). The numbers are the same
  `llama_main` statistics (`PyTorchObserver`, the definitions above) and the same parser.
- **Metal** (`executorch-metal`): no route for Qwen 3 in v1.5.1. `export_llm` has no Metal
  backend (`backend.metal` stops at `ConfigKeyError: Key 'metal' not in 'BackendConfig'`); the
  tag's Metal LLM exporters are model-specific (`examples/models/qwen3_5_moe`, `voxtral*`,
  `whisper`, `parakeet`, …) or optimum-executorch's `--recipe metal`; and `llama_main` never
  links `metal_backend` (`examples/models/llama/CMakeLists.txt`; the Makefile has no
  `llama-metal`).
- **Vulkan** (`executorch-vulkan`, Android): exported on the Mac with `--set
  backend.xnnpack.enabled=false --set ++backend.vulkan.enabled=true`, the yaml's 8da4w as it
  is (the Linear layers become `et_vk.linear_dq8ca_q4gsw`). The `.pte`'s `forward` is one
  `VulkanBackend` call with `embedding_byte` outside. It runs on the Android Vulkan build
  (`android/bin/executorch-v1.5.1-vulkan/`), not on the Mac.
- Gemma 4: `export_gemma4.py` lowers to XNNPACK only, so the Mac MLX rows of Gemma 4 are
  excluded (`gemma4-exporter-has-no-mlx-path`).

## Inputs and staging

`ET_MODEL_DIR` (default `models/executorch`) holds, per model: `<name>.pte`,
`<name>.recipe.json`, the tokenizer the recipe.json names, and — for `llama_main` — the prompts
rendered once with the model's chat template:

```bash
<python with transformers> scripts/executorch/make_prompts.py \
  --snapshot <recipe.json checkpoint.snapshot> --suffix chat \
  --out-dir models/executorch/<name>.prompts
```

The runner checks that `prompts.json` was rendered from the checkpoint's revision and that the
prompt file still has the rendered sha256. On Android the `.pte`, the tokenizer and the rendered
prompt are pushed beside each other under `/data/local/tmp/llmbench/models/` (the prompt and the
tokenizer by sha256). The runner's stderr goes to a file of its own and is read after the launch:
one stream would put a log line into the text (`llama_main` logs right after printing the first
token). The stored log keeps it after `===ENGINE_STDERR===`.

## Regime and disclosure

- Mac: run 1 cold, runs 2..N warm (`llama_main --warmup`); the Mac headline is warm.
  `gemma4_e2e_runner` has no warmup, so the Mac Gemma 4 rows are excluded with that reason.
  Android: cold only, one fresh process per run, as the other Android arms.
  iPhone: run 1 cold (the model loads in the app process), runs 2..N warm in the same process,
  the runner's KV position reset before every run.
- Own exports, not published artifacts; the label says so.
- Prefill includes tokenization with `llama_main` and excludes it with `gemma4_e2e_runner`.
- Vulkan, QNN and the Mac GPU backends are not measured.
- Pixel 8a: the launches run under `taskset f0` (cpus 4-7, the phone's device env in
  `devices/pixel-8a.md`, as the llama.cpp arm) and the runner keeps that mask
  (`conditions.cpusAllowedList` 4-7), so `llama_main`'s 9 threads share four cores. The phone
  is rebooted before a sitting when its uptime is over 2 h (`reboot_before` in
  `ops/dashboard-v1/schedule.json`), and the Qwen3-4B and Gemma 4 E4B rows are
  `exclude-on=pixel8a`.
- iPhone: the ExecuTorch 1.5.0 runtime (the newest release Swift package) runs the 1.5.1 exports;
  the prompt token count is the host tokenizer's, and the times are the adapter's wall clock.
- The weekly job runs the Mac rows since 2026-10-08 (section "Weekly job"); the Android and
  iPhone rows are by-hand sittings.
- Name an ExecuTorch sitting `<date>-dashboard-executorch-…`: the team dashboard
  (litert-bench-dashboard) reads only campaigns whose name contains `dashboard`.

## iPhone

The app runs the own exports through ExecuTorch's Swift `TextRunner`
(`extension/llm/apple/ExecuTorchLLM`, the binding over the C++ `TextLLMRunner` that `llama_main`
drives) on the XNNPACK delegate (`ios/BenchmarkApp/Sources/Runtimes/ExecuTorchRuntime.swift`).
Core AI and the ExecuTorch package cannot share the app target (both emit
`include/module.modulemap` into the products directory), so this arm is a second build of the
same app: `ios/BenchmarkApp/project-executorch.yml` is `project.yml` without Core AI and with the
ExecuTorch products; the target, scheme, bundle id and every other arm are `project.yml`'s. It
replaces the Core AI build on the phone for the sittings that run
`matrices/dashboard-executorch-v1-ios.cells`.

```bash
cd ios/BenchmarkApp && xcodegen generate --spec project-executorch.yml   # BenchmarkApp-executorch.xcodeproj
xcodebuild build -project BenchmarkApp-executorch.xcodeproj -scheme BenchmarkApp -configuration Release \
  -destination 'generic/platform=iOS' -derivedDataPath <dir> -skipPackagePluginValidation \
  -skipMacroValidation CODE_SIGNING_ALLOWED=NO    # unsigned compile check; the install is signed in Xcode
```

- Engine: ExecuTorch **1.5.0**. There is no 1.5.1 Swift package (no `swiftpm-1.5.1` branch); the
  project pins the head of `swiftpm-1.5.0` by revision (`56cc93a96d5f`, prebuilt xcframeworks
  fetched by the checksums in its `Package.swift`). Between the tags v1.5.0 and v1.5.1 no runtime,
  kernel, XNNPACK, program-format or LLM-runner source changed (Arm / Cortex-M / NXP backends,
  export passes, a threadpool getter). The build phase "Stamp engine pins" adds the `executorch`
  pin read from the resolved package, so records carry `engineVersion` `v1.5.0` and
  `engineArtifact` `executorch SwiftPM 56cc93a96d5f: executorch_llm-1.5.0.zip sha256:…` (the
  checksum of every zip the target links). The record's `runtime` is `executorch-xnnpack`.
- Linkage: the archives that register the backend, the kernels and the prim ops
  (`executorch`, `backend_xnnpack`, `kernels_llm`, `kernels_optimized`, `kernels_quantized`) are
  force-loaded, as the ExecuTorch iOS docs' "Linkage" section asks: with `-ObjC` alone none of
  their registrations links and every `.pte` fails at load.
- Prompt: the adapter renders Qwen 3's chat template for one user turn
  (`<|im_start|>user\n{prompt}<|im_end|>\n<|im_start|>assistant\n`, the template's defaults, so
  the model thinks), byte for byte the prompt the Mac and Android runners read from
  `<name>.prompts/<task>.chat.txt`.
- Prompt tokens: the binding reports no statistics. The count is the host tokenizer's for the
  rendered prompt (`prompts.json` `hostPromptTokens`: 19 short-chat, 1,338 for the 1K task), keyed
  in `ExecuTorchModelSpec` by the rendered prompt's sha256; a prompt not listed records 0 and no
  prefill rate. Every run prints `YARDSTICK_NOTE executorch template=… prompt_sha256=…
  prompt_tokens=… prompt_tokens_source=…` to the console the iPhone runner stores beside the
  records. The C++ runner also prints its `PyTorchObserver` statistics line to the app's stdout,
  so the same console holds the runner's own token counts and timestamps.
- Context: the KV cache is the export's 2048 tokens (`Config.sequenceLength` = 2048). The app
  records the cell's `context-tokens=` as the run's allocation, so every iPhone row names 2048.
- Gemma 4 is excluded (`exclude=gemma4-no-swift-runner-for-text_decoder-method`): its `.pte` has
  the one method `text_decoder` (three inputs, no metadata methods), which `TextRunner` cannot
  drive, and `gemma4_e2e_runner` has no Swift binding.

The adapter's numbers, beside the `llama_main` definitions above (adapter clock:
`CFAbsoluteTimeGetCurrent`, seconds as a double):

| | iPhone (`TextRunner`) | Mac / Android (`llama_main`) |
|---|---|---|
| prefill window | the `generate` call to the first token callback: tokenization, the prefill, the first sample and its decode to text | `inference_start_ms` to `prompt_eval_end_ms` (tokenization included) |
| prefill tok/s | host prompt tokens / that window | `prompt_tokens` / that window |
| TTFT | the harness's run start to the first streamed chunk | `first_token_ms - inference_start_ms` |
| decode window | the first token callback to `generate` returning | `prompt_eval_end_ms` to `inference_end_ms` |
| decode tokens | token callbacks - 1 (the decode loop; the reply has one more) | `generated_tokens` (the decode loop) |
| stop reason | `length` when the reply reaches the task budget | (the runner logs `Max new tokens N reached!`) |

### Side-load

The catalog rows have no Hub repo behind them: the app reads
`Documents/models/executorch/<model id with "/" as "__">/` and reports a missing file at load (no
download). Copy a folder holding the `.pte` and `tokenizer.json` (copies or hard links), one per
model, over USB:

```bash
APP=com.example.CoreMLLLMChat DEV=<CoreDevice id>   # scripts/bench_matrix_iphone.sh's defaults
M=Qwen3-0.6B-ET1.5.1-xnnpack-8da4w-emb8-ctx2048     # then Qwen3-1.7B-…, Qwen3-4B-…
xcrun devicectl device copy to --device "$DEV" --domain-type appDataContainer \
  --domain-identifier "$APP" --source <folder with $M.pte and tokenizer.json> \
  --destination "Documents/models/executorch/own-export__$M"
```

The three models take about 4.2 GB of app storage (`.pte` 469 + 1,204 + 2,469 MB, `tokenizer.json`
11 MB each). Records are pulled by the iPhone runner as for every other arm
(`Documents/results`).

Before the first sitting, the iPhone runner (`scripts/bench_matrix_iphone.sh`) has to map an
executorch row: it forwards a row's `backend=` as `--litert-backend` for every runtime, which the
app refuses for `xnnpack` (`YARDSTICK_FATAL bad --litert-backend`), and its capture gate looks the
records up by the cells runtime (`executorch_…`) while their files carry the record runtime
(`executorch-xnnpack_…`).

### Install (a person, Xcode)

1. Open `ios/BenchmarkApp/BenchmarkApp-executorch.xcodeproj` (after `scripts/bootstrap.sh` has filled `Vendored/`).
2. Target `BenchmarkApp`, Signing & Capabilities: the team, and the bundle id `com.example.CoreMLLLMChat` (the bench App ID).
3. The two increased-memory entitlements (`BenchmarkApp.entitlements`: increased-memory-limit, extended-virtual-addressing) must be granted by the profile.
4. Scheme `BenchmarkApp`, Run, Build Configuration `Release` (records state it as `device.buildConfiguration`); run it on the bench iPhone, which replaces the Core AI build.
5. Stage the models (above) before the sitting.

## Status (2026-10-08)

Measured on the Mac Studio M4 Max (XNNPACK, Qwen3 0.6B / 1.7B / 4B, both text tasks, campaign
`2026-10-08-dashboard-executorch-v1-m4max-mac`), partially on the Galaxy S26
(`2026-10-08-dashboard-executorch-v1-s26-android`: the Qwen3 0.6B short-chat cell; the phone
capped a CPU the runner ran on in every other launch, so those cells have no valid run) and on
the Pixel 8a (`2026-10-08-dashboard-executorch-v1-pixel8a-android`: the Qwen3 0.6B short-chat
cell; the phone left USB during the 1K unit). The MLX delegate ran a smoke on the Mac
(`2026-10-08-executorch-gpu-smoke-m4max-mac`, not a dashboard sitting). Earlier smokes (round
r1 on the Mac, r2 on the S26, r3's Gemma 4 E2B run with `gemma4_e2e_runner`; `llama_main
--method_name text_decoder` exits 1 on that export) are not measurements. The runners' output of those smokes is
the parser fixture (`android/bench/testdata/executorch/`), and `android/bench/selftest.py` runs
the Android path end to end on it with no phone.

iPhone: round r6-ios built the app with the ExecuTorch package (an unsigned Release compile on
the Mac); it has not run on a phone yet.

## Run one cell

```bash
# Android (a phone with the runner pushed; BENCH_CPU_MASK per devices/*.md)
python3 android/bench/run_cell.py --runtime executorch --backend xnnpack \
  --model-id own-export/Qwen3-0.6B-ET1.5.1-xnnpack-8da4w-emb8-ctx2048 \
  --file Qwen3-0.6B-ET1.5.1-xnnpack-8da4w-emb8-ctx2048.pte --recipe et1.5.1-xnnpack-8da4w-g128-emb8 \
  --task short-chat --runs 3 --out results/raw/<campaign>/app-path-android
# Mac
python3 scripts/executorch_mac.py --model-id own-export/Qwen3-0.6B-ET1.5.1-xnnpack-8da4w-emb8-ctx2048 \
  --file Qwen3-0.6B-ET1.5.1-xnnpack-8da4w-emb8-ctx2048.pte --recipe et1.5.1-xnnpack-8da4w-g128-emb8 \
  --backend xnnpack --task short-chat --runs 4 --output results/raw/<campaign>/<cell>.jsonl
```

Add `--dry-run` to either to print the launch (command, binary, inputs) with no device call and
no run. Matrix rows go through `./bench matrix matrices/dashboard-executorch-v1-<platform>.cells`.

## Weekly job

The recurring job (`./bench dashboard-job`, `docs/dashboard-recurring-job-v1.md`) measures
`matrices/dashboard-text-v1.cells`, or its Android storage halves, and those files do not carry
the ExecuTorch rows: adding them is an owner decision. Once they carry them, a sitting needs:

- Android: the runner directory on the phone (`adb push android/bin/executorch-v1.5.1
  /data/local/tmp/llmbench/`, by hand and left there, as the other engines are). A cell whose
  runner is missing still waits its cooldown in every round (its `.pte` is pushed in the first),
  then stops before the launch (a `FAILURES.txt` line each time): the ten rows cost about 1.9 h of
  the phone for no record. `android/scripts/executorch_matrix_android.sh` removes that directory
  after its window even when it found it there, so a by-hand window between two sittings takes it
  away. Also: the `.pte` files with their recipe.json, tokenizer and rendered prompts under
  `ET_MODEL_DIR` of the checkout the job runs in (each cell pushes its `.pte`; the halves'
  `min_free_gb` has to count them).
- Mac: both runner builds in `.build/executorch-v1.5.1/` and `.build/executorch-v1.5.1-mlx/` of
  that checkout (or `ET_MAC_RUNNER_DIR`; a missing runner is a `SKIPPED` line, not a failure)
  and the `.pte` files under `ET_MODEL_DIR`. Loads from the external volume took 2-10 s longer
  at times; the load is outside every rate.
- `BENCH_SITTING=1` is not set by the job: it marks a by-hand sitting (with `ROUNDS=N`,
  `run_campaign.py`'s round mode). Its pin check before the first launch expects the tag's pin
  per runner and build since 2026-10-08 (`v1.5.1`; `<runner>_sha256` for the XNNPACK build,
  `<runner>_<backend>_sha256` for another); until then every executorch cell stopped there with
  `PIN MISMATCH` (exit 5).
- iPhone: the job cannot run these rows. The bench app is one bundle id
  (`com.example.CoreMLLLMChat`); the ExecuTorch build of it replaces the Core AI build on the
  phone, because one app target cannot link both Swift packages (both emit
  `include/module.modulemap`), and the job never installs an app. So the ExecuTorch iPhone rows run only in a by-hand sitting
  while a person has that build installed. Whoever installs it holds the iPhone's hold file
  (`ops/dashboard-v1/schedule.json`, the phone's `hold`) until the Core AI build is back, so a
  weekly firing passes the phone over instead of measuring the weekly cells on a swapped app. Not
  built, a later option: a second app target with its own bundle id, so both builds stay
  installed side by side.
