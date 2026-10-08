# Core AI on iPhone and Mac — stock arm v1

## What the arm runs

Apple's Core AI engine as Apple's own tools run it: bundles made by Apple's export pipeline
(apple/coreai-models at the pin below, unchanged, each model's default recipe, context 2048),
loaded and generated through the call sequence of Apple's `llm-runner` (`LanguageModelBundle` →
`EngineFactory.createEngine(bundle:)` → tokenizer → stop tokens → the default warmup →
`engine.generate`, greedy). That is the stock path of the harness's `CoreAIRuntime`
(`ios/BenchmarkApp/Sources/Runtimes/CoreAIRuntime.swift` 42–48, `loadStock` /
`runGenerateStock`): it sets no `COREAI_*` variable, binds no side table and skips no warmup.
The same Swift file runs in the iPhone app and in the Mac CLI (yardstick).

The export decides the engine. Apple's iOS exports are chunked-static bundles, and the runner
specializes them for the Neural Engine (`ModelStructure.specializationOptions` = `.neuralEngine`
in apple/coreai-models); naming the GPU engine instead ends after the load with `Unknown variant
Variant 'coreai-pipelined' incompatible with model structure`. No public option picks the compute
unit, so the arm is the Neural Engine on both platforms: arm id `core-ai-ane`, stamped when the
stock path loaded a `StaticShapeEngine` (`CoreAIRuntime.recordRuntimeLabel`, 97–108). The Mac runs
the same iOS bundles (one export per model for both platforms); macOS also specializes them for
the Neural Engine. A Core AI load that falls back to the GPU does not say so in a cached run's log,
so a smoke reads the GPU's utilization during generation (0 % = the Neural Engine).

The arm's rows are `core-ai <id> <task> backend=ane`: `backend=ane` is arm identity only (the
runners pass nothing for it; `scripts/validate_cells.py` requires it with a stock id and refuses it
without one). Ids: `core-ai/<model>-stock-ctx2048` for Qwen3 0.6B / 1.7B / 4B and Gemma 4 E2B / E4B;
bundle folders `stock_<model>_ctx2048` (`CoreAIRuntime.bundleSpec`, the stock path's folder prefix
`stock_`). The own-export Core AI rows of `matrices/dashboard-text-v1.cells` (arm `core-ai`, the
GPU engine, "Core AI arm (v2)" in `docs/dashboard-cells-v1.md`) are a different arm and never pool
with these.

Cells: `matrices/dashboard-coreai-v1-ios.cells`, `matrices/dashboard-coreai-v1-mac.cells` (the
dashboard model set × the 1K text task and the protocol 1024/256, each model's Core AI rows next to
the same model's LiteRT-LM rows, so both arms run in one sitting on one build and one OS). Runners:
`scripts/bench_matrix_iphone.sh` (the app, `--yardstick-autorun`) and `scripts/bench_matrix_mac.sh`
(the yardstick), both through `./bench matrix`.

## Pins and artifact provenance

- Engine and exporter: apple/coreai-models `bd3c539540c1f9aa96675079b38810f51845653c`
  (`git describe` `1.0.0-10-gbd3c539`, 2026-10-07, "Unify stop-token resolution across text and VLM
  adapters (#269)"), unchanged. `ios/BenchmarkApp/Vendored/coreai-models` points at a checkout of
  that commit (Vendored/ is git-ignored; a symlink or a worktree); the app and the yardstick link
  its `CoreAILM` package. Registry: `environment.lock.json` `arms.coreai-models.stock-v1` (the
  0.2.0 block above it is the own-export arm's).
- `ios/BenchmarkApp/scripts/stamp_engine_pins.sh` records the checkout as `git describe --tags
  --dirty`, so a record's `engineVersion` reads `1.0.0-10-gbd3c539` and would end in `-dirty` had
  the checkout carried a local change.
- #332 ("Move Gemma 4 PLE sidecar to auxiliary_assets in metadata.json") changed both sides: the
  Gemma 4 export writes its per-layer-embedding table as `auxiliary_assets.per_layer_embeddings`
  (a `.safetensors` beside the `.aimodel`), and the runner checks only `assets` with
  `AIModelAsset.isValid`. A bundle exported before #332 (the table under `assets`) fails that
  check on this pin; every bundle of this arm is a bd3c539 export.
- Exports: Gemma 4 = `models/gemma4/export.py --model google/gemma-4-E<n>B-it
  --max-context-length 2048` (its default compression config `4bit_palettized.yaml`,
  `export.py` 71); Qwen3 = `coreai.llm.export qwen3-<size> --platform iOS --max-context-length 2048`
  (the iOS registry preset's compression config, `python/src/coreai_models/model_registry.py`
  314–354). The iOS default context is 4096 (`_constants.py` 39), so 2048 is passed. The export's
  context ladder for 2048 is [1024, 2048] (`export.py` `context_ladder`).
- Each export folder has `<folder>.recipe.json` beside it: the exporter's commit, describe and
  `uv.lock` sha256, the command verbatim, the checkpoint's HF repo and revision (read from the
  export log's resolve-cache lines), the recipe yaml verbatim with its sha256, `metadata.json`'s
  sha256 and `compression`, every file's sha256 and the bundle's bytes, the host. The Mac runner
  writes the staged bundle's bytes, auxiliary assets and that recipe's sha256 to the session's
  `session_provenance.txt` (`coreai_stock_provenance`).
- The LiteRT-LM rows of the same cells run the dashboard's pin, v0.16.0 (`environment.lock.json`
  `arms.litert-lm`; `Vendored/LiteRT-LM` with the local `maxNumTokens` pass-through in
  `swift/Benchmark.swift`, so `--context-tokens` reaches `benchmark()`).

## Recipes

The quantization is Apple's default per model; the record's label (`model.quantization`) is the
catalog's (`ios/BenchmarkApp/Sources/Models/ModelCatalog.swift`, the stock entries), and
`metadata.json`'s `compression` is the export's own name for it.

| Model id | Export recipe (Apple's default) | `metadata.json` `compression` | Record label |
|---|---|---|---|
| `core-ai/gemma4-e2b-stock-ctx2048` | `models/gemma4/4bit_palettized.yaml`: 4-bit k-means palettization, group 32; PLE gate / projection 8-bit; per-layer model projection uncompressed; embedding and PLE tables int8 | `4bit_palettized` | 4bit_palettized (4bit_palettized.yaml: …) |
| `core-ai/gemma4-e4b-stock-ctx2048` | the same yaml | r2 | 4bit_palettized (4bit_palettized.yaml: …) |
| `core-ai/qwen3-0.6b-stock-ctx2048` | `models/qwen3/qwen3_0_6b_mixed_4bit_8bit.yaml`; embedding int8 | r2 | mixed 4-bit/8-bit palettized (…) |
| `core-ai/qwen3-1.7b-stock-ctx2048` | `models/qwen3/qwen3_1_7b_6bit.yaml`; embedding int8 (the iOS `LoadEmbeddings` default `embedding_table_dtype=torch.int8`; the yaml leaves the embedding out) | r2 | 6-bit palettized (…) |
| `core-ai/qwen3-4b-stock-ctx2048` | `models/qwen3/qwen3_4b_mixed_4bit_8bit.yaml`; embedding int8 | r2 | mixed 4-bit/8-bit palettized (…) |

"r2" = filled from the round r2 exports' `metadata.json` when they are registered. The recipes
differ from the LiteRT-LM bundles' (quant-per-arm-rule): a row compares deployment profiles, and
the label travels with it.

## Record fields and definitions

Two instruments, as for the LiteRT-LM arm. Their rows never pool: the task id says which one
(`long-context-1024-gen256` or `native-benchmark-1024x256`).

**The 1K text task (`long-context-1024-gen256`, the harness).** The same prompt, budget and record
as every arm (`BenchmarkRunner`). The columns the dashboards read (`results/summary`
`decode_tps` / `prefill_tps`, `scripts/build_summary.py`) are the record's
`decodeTokensPerSecond` / `promptTokensPerSecond`, which the runner takes from the runtime's own
counts and times (`ios/BenchmarkApp/Sources/Benchmark/BenchmarkRunner.swift` 252–257, 324–327):

```
decodeTokensPerSecond = generationTokenCount / generateTime   (BenchmarkRunner.swift 324-326)
promptTokensPerSecond = promptTokenCount / promptTime          (BenchmarkRunner.swift 327)
On the stock path (CoreAIRuntime.swift runGenerateStock):
  promptTokenCount     = the prompt's token ids after the model's chat template (590, 681)
  promptTime           = first token's arrival - the engine.generate call (597, 677-678)
  generationTokenCount = every token the engine yielded, the first one and a stop token included
                         (615 appends each arrival before the stop check at 618; 682)
  generateTime         = end of the stream loop - first token's arrival (631, 679)
firstTokenLatencyMS    = first streamed chunk - the runner's generate call, x 1000
                         (BenchmarkRunner.swift 191, 233-234, 317): it includes the chat-template
                         tokenization and engine.reset (CoreAIRuntime.swift 590, 593), which
                         promptTime does not
```

Audit columns, the harness's own clock over what it received (`BenchmarkRunner.swift` 266–269,
332–335): `decodeTokensPerSecondWallClock` = (streamed chunks − 1) ÷ (last chunk − first chunk),
`promptTokensPerSecondWallClock` = prompt tokens ÷ (first chunk − the generate call). Regime:
run 1 of a launch is cold (the first generate after the load), runs 2..N warm; the headline is the
warm median, as for every Apple arm. `contextTokensConfigured` / `recordedContextTokens` is the
bundle's `language.max_context_length` (`CoreAIRuntime.recordedContextTokens`, 84–93): the export
fixes the KV allocation, `--context-tokens` does not resize it, and a forced value that differs is
said in a `YARDSTICK_WARN` line. Memory: `memoryPeakDuringDecodeMB` / `memoryMedianMB` =
`phys_footprint` sampled from after the load to the end of generation (`BenchmarkRunner.swift` 184,
291–296; `MemoryMonitor.swift` 16–29), as for every Apple arm.

**The protocol 1024/256 (`native-benchmark-1024x256`, Apple's `llm-benchmark` measurement).**
`--coreai-native-benchmark 1024x256` runs `CoreAIRuntime.nativeBenchmarkStock` (827–884), the
measurement of Apple's `llm-benchmark` (BenchmarkMain.swift) on the stock path: a synthetic prompt
of 1024 token ids (seed 0, 852–853), greedy, one warmup trial and `--runs` timed trials, each trial
a pause, `engine.reset`, then one `engine.generate` of 256 tokens with no stop check
(`benchmarkTrial`, 716–751, BenchmarkMain.swift `runTrial` line for line):

```
prompt tok/s     = 1024 / promptTime, promptTime = first token's arrival - the generate call (737-748)
generation tok/s = (tokens - 1) / genTime, genTime = first token's arrival -> end of the stream:
                   255 / (seconds after the first token) at 256 tokens (747-750)
TTFT ms          = promptTime x 1000
cold = trial 0, the warmup trial: the first generate on the engine after the load, which
       llm-benchmark times and leaves out of its mean (861-874); warm = trials 1..N (877-883)
memory / thermal = phys_footprint and the thermal state sampled across each trial (758-791)
```

The app and the yardstick print one `YARDSTICK_NATIVE_OK runtime=core-ai trial=<i> cold=<0|1>`
line per trial (`CoreAINativeBenchmark.line`, 1048–1056); `scripts/import_native_benchmark.py
--schema-v1` lifts them into records (`promptTokensPerSecond`, `decodeTokensPerSecond`,
`firstTokenLatencyMS`, `decodeSeconds`, `coldRun`, `conditions.trial`). `prepare_cached=0` on a
line says this launch's load specialized the bundle (`PreparedModel.isCached`, 472, read before the
load), and the importer marks that launch's first record `firstEver` (fairness rule 2: a cache
build is never the engine's speed).

**The LiteRT-LM rows of the same cells** use LiteRT-LM's own `benchmark()` for the protocol
(`--litert-native-benchmark 1024x256 --context-tokens 2048`; `MediaPipeRuntime.nativeBenchmark`,
185–209): the engine's `BenchmarkInfo`, on the engine's clock — prefill tok/s = the prefill turn's
tokens ÷ its duration, decode tok/s = the decode turn's tokens ÷ its duration, TTFT = the prefill
turn + one decode step (LiteRT-LM v0.16.0 `runtime/engine/io_types.cc` 287–300, 326–345,
347–357). `--runs N` = N `benchmark()` calls in one process, each building a new engine: call 1
cold, calls 2..N warm (only the process and the on-disk caches are warm;
`ios/BenchmarkApp/Sources/BenchmarkApp.swift` 621–685). The two protocol instruments count
differently (decode tokens ÷ decode turn against (tokens − 1) ÷ the time after the first token; an
engine clock against the app's), and so does each against the text task: compare a protocol row
with a protocol row, and read the definitions with the number.

## Inputs and staging

- Exports live on the export volume, one folder per id plus its `recipe.json`; `models/coreai` in
  the checkout is a symlink to that directory (untracked).
- Mac: each folder is copied to the internal disk before a sitting,
  `~/.cache/edge-llm-bench/CoreAIModels/<folder>/` (`BENCH_COREAI_MODELS_DIR`; local, outside
  iCloud Drive). A row whose folder is missing logs `SKIPPED … coreai-bundle-not-staged`.
- iPhone: the app's `Documents/CoreAIModels/<folder>/`, copied over USB (`xcrun devicectl device
  copy to --domain-type appDataContainer`); a multi-GB copy over Wi-Fi dies.
- Specialization: the first load of a bundle specializes it for the Neural Engine on that device
  (seconds on the Mac, minutes on a phone; `YARDSTICK_COREAI_PREPARE cached=0`) and caches it under
  the OS build and the executable's name (Mac: `~/Library/Caches/coreai-cache/<OS build>/<binary
  name>/<main.hash>/…`; iPhone: the app container's `Library/Caches/coreai-cache/…`). A Mac
  yardstick rebuilt under the same name can find the previous build's entry and fail its first
  function load (`[warmup] nilError`): run a byte-identical copy under a new name, or delete that
  entry. On a phone, a cached load that is killed (memory high-water) or fails is not proof that
  the bundle cannot run: delete only that bundle's entry and specialize again once.
- Stop tokens: the tokenizer's EOS and `tokenizer_config.json`'s `eot_token` (Apple's runner set),
  united with `metadata.json`'s `eos_token_ids`; each run's `YARDSTICK_COREAI_STOP` line lists both.
- The prompt is the repository's text-task prompt through the model's chat template
  (`PromptUtils.maybeApplyTokenizerChatTemplate`): Apple's Swift template puts one more token
  (a newline after `<bos>`) into a Gemma 4 prompt than the Hugging Face template.

## Regime and disclosure

- Apple's exports, not artifacts this repo trained or converted: the bundles are runs of Apple's
  pipeline at the pin, unchanged, and the recipe.json beside each is its record. An export does
  not reproduce byte for byte (the same checkpoint and yaml gave a `main.mlirb` of another size
  and content, and a PLE header with its keys in another order), so a bundle's identity is its
  recipe.json's sha256s and its `main.hash`, not the commit and checkpoint alone.
- Gemma 4 E4B on the 1K text task ends its reply at its own end of turn (token 106), at 58
  generated tokens in the 2026-10-06 comparison on the d30b086 export — a refusal of the lorem
  text, the same text on the Mac and the iPhone. The row is measured as it is (not excluded): its
  record's generated-token count says so, and the 256-token decode of that model is the protocol
  row's.
- Mac memory is drawn and not ranked: on the Neural Engine path the weights are not charged to
  the process's `phys_footprint` (a 4-bit and an unpalettized export of the same model peak at
  about the same footprint), so the figure does not compare with the GPU arms' figures. The
  iPhone figure is the same `phys_footprint` window as every Apple arm's and ranks with them.
- The phones run beta builds of iOS 27: their numbers stay on the internal page, never in a
  public repo, card or post.
- The weekly job does not run these cells yet (an owner decision; the arm joins a weekly file
  only after its first sittings).
- Name a sitting `<date>-dashboard-coreai-v1-<device>`: the team dashboard reads only campaigns
  whose name contains `dashboard`.

## Status (2026-10-08)

Wired, not measured. Round r1 built the app and the yardstick on the pin, exported Gemma 4 E2B
with Apple's pipeline, and ran one smoke on the Mac Studio M4 Max (not a measurement, not a
sitting): the bundle loaded on `StaticShapeEngine`, the text task decoded the same text the
comparison lane's d30b086 export did (byte for byte), the GPU stayed idle during generation, the
records stamped `core-ai-ane` and `1.0.0-10-gbd3c539`, and the protocol lines imported as
schema-v1 records. No dashboard sitting has run on either platform.

## Run one cell

```bash
# Mac (the bundle staged under ~/.cache/edge-llm-bench/CoreAIModels/<folder>/)
YS=.build/dd-mac/Build/Products/Release/yardstick
$YS run --runtime core-ai --model-id core-ai/gemma4-e2b-stock-ctx2048 --task long-context-1024-gen256 \
  --runs 4 --context-tokens 2048 --output results/raw/<campaign>/<task cell>.jsonl
$YS run --runtime core-ai --model-id core-ai/gemma4-e2b-stock-ctx2048 --task short-chat --runs 4 \
  --context-tokens 2048 --coreai-native-benchmark 1024x256 --output results/raw/<campaign>/<native cell>.jsonl
python3 scripts/import_native_benchmark.py --schema-v1 results/raw/<campaign>/<native cell>.jsonl \
  --out results/raw/<campaign>/app-path-native --like results/raw/<campaign>/<task cell>.jsonl \
  --launch-times <each launch's UTC start> --device Mac16,9 \
  --instrument "core-ai llm-benchmark measurement (CoreAIRuntime.nativeBenchmarkStock) via yardstick --coreai-native-benchmark"
# iPhone (the bundle in Documents/CoreAIModels/<folder>/; the runner imports the native lines itself)
xcrun devicectl device process launch --console --terminate-existing --device <udid> <app id> -- \
  --yardstick-autorun --runtime core-ai --model-id core-ai/gemma4-e2b-stock-ctx2048 \
  --task short-chat --runs 3 --context-tokens 2048 --coreai-native-benchmark 1024x256
```

`--like` is a record of the same arm, model and device from the same sitting (the importer refuses
a LiteRT-LM record for Core AI lines and the reverse); `--launch-times` takes one UTC start per
launch (the Mac runner's `CELL` line; the iPhone runner writes `<console>.launch_times`). Matrix
rows: `./bench matrix matrices/dashboard-coreai-v1-<ios|mac>.cells --platform <iphone|mac>
--campaign <date>-dashboard-coreai-v1-<device>`; `scripts/bench_matrix_mac.sh run <cells>
--dry-run` and `DRY_RUN=1 scripts/bench_matrix_iphone.sh run <cells>` print every launch with no
device call.
