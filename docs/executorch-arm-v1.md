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
(`executorch-xnnpack`; `vulkan` / `qnn` on Android and `mlx` / `metal` / `coreml` on the Mac
are reserved names, nothing runs on them yet).

Cells: `matrices/dashboard-executorch-v1-android.cells`, `matrices/dashboard-executorch-v1-mac.cells`
(the dashboard model set: Qwen3 0.6B / 1.7B / 4B, Gemma 4 E2B / E4B × short-chat and the 1K text
task). Runners: `android/bench/run_cell.py --runtime executorch` (through
`android/bench/run_campaign.py`), `scripts/executorch_mac.py` (through
`scripts/bench_matrix_mac.sh`). The iPhone arm is not wired.

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
  beside it; the Galaxy S26 matrix driver is `android/scripts/executorch_matrix_s26.sh`
  (one model per queued hold, the cells file's rows one at a time, the `.pte` pushed for
  the slot and removed after it).
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
| `conditions.cpuThreads`, `cpuThreadsPolicy` | `--cpu_threads` is never passed: the engine's heuristic (cpuinfo `get_num_performant_cores`); the Android build logs the pool size (8 on the Galaxy S26). The Mac stock build logs nothing; a logging build of the same source read 16 on the M4 Max (it counts no efficiency core) |
| `conditions.textCheck` | `android/bench/parsers.text_integrity` over the runner's text (llama_main: stdout after the prompt echo, cut before the stats line; gemma4_e2e_runner: stdout); a FAIL pools into no number |
| `conditions.protocolFlags` | `echo-mismatch`, `stats-rate-mismatch` (a printed rate the recomputation does not reproduce), `prompt-token-count-mismatch` (llama_main against the host tokenizer's count), `output-budget-exceeded`, `context-budget-exceeded`, `allocation-witness-mismatch`, and Android's `cpu-capped` |
| `provenance.statsLine` / `statsReport` | the runner's statistics verbatim |
| `provenance.recipe`, `recipeSha256`, `recipeAlias`, `promptFile`, `promptSha256`, `tokenizerSha256` | the inputs of the run |

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
- Own exports, not published artifacts; the label says so.
- Prefill includes tokenization with `llama_main` and excludes it with `gemma4_e2e_runner`.
- Vulkan, QNN and the Mac GPU backends are not measured.
- The Android weekly sitting (`BENCH_SITTING=1`) refuses executorch at the pin check (the sitting
  expects the litert-lm / llama.cpp pins): adding ExecuTorch to the weekly job is a later step.
- Name an ExecuTorch sitting `<date>-dashboard-executorch-…`: the team dashboard
  (litert-bench-dashboard) reads only campaigns whose name contains `dashboard`.

## Status (2026-10-08)

Wired, not measured. Round r1 exported Qwen3 0.6B and smoke-ran the Mac `llama_main`; round r2
built the Android runner and smoke-ran it on a Galaxy S26; round r3 exported Gemma 4 E2B and ran
it with `gemma4_e2e_runner` on the Mac (`llama_main --method_name text_decoder` exits 1 on that
export). No number from those smokes is a measurement. The runners' output of those smokes is
the parser fixture (`android/bench/testdata/executorch/`), and `android/bench/selftest.py` runs
the Android path end to end on it with no phone.

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
