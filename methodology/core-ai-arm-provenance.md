# Core AI arm — provenance and reproduction

The Core AI arm has three classes of rows, and the difference matters for how you read (and
reproduce) them. Classes 1 and 2 are our own exports on the GPU engine (arm `core-ai`); class 3
(since 2026-10-08) is Apple's own exports on Apple's stock path (arm `core-ai-ane`).

## Class 1 — stock rows (every non-PLE model)

Built against **Apple's released `coreai-models` Swift package** (pinned 0.2.0), no
modifications. A clean clone of this repo builds and runs these rows as-is: `bootstrap.sh`
fetches vendored deps, the package resolves from `Vendored/coreai-models` (a stock checkout
or symlink to one). Models side-load to `Documents/CoreAIModels/<folder>/` (the exports are
published under `huggingface.co/mlboydaisuke/*-CoreAI`).

## Class 2 — patched-engine rows: Gemma-4 E2B/E4B, labelled "patched engine (reference)"

These are our own Gemma-4 exports, and their per-layer embeddings (PLE) need two engine
features that are **not in Apple's released package** (absent from 0.1.0 and 0.2.0). (Apple's
own pipeline now exports Gemma 4, and its engine runs those bundles unpatched since
apple/coreai-models #332: class 3 below. This class stays as the own-export reference.)
The two features:

- `EngineOptions.staticInputBuffers` / `StaticInputBuffer` — bind the mmap'd PLE table
  (`ple/embed_per_layer.i8` + `.scale.f32`) as static graph inputs for the `_tbl` in-graph
  gather path;
- `EngineOptions.perTokenInputProvider` — the host-side per-token PLE row provider path.

Everything else about the row is the **standard public path**: `EngineFactory.createEngine`
→ `engine.generate`, the same app, task, and protocol as every other arm. (An earlier note
claiming these rows needed a "low-level PreparedModel runner" was a misdiagnosis — the crash
it described was this app calling `warmup(queryLength: 8)` on an S=1-only graph, fixed in
the app.)

### Exact reproduction

1. Clone Apple's engine and apply the patch (published in this repo):

   ```bash
   git clone https://github.com/apple/coreai-models
   cd coreai-models
   git checkout 938d0b8          # the upstream commit the patch is based on
   patch -p1 < ../apple-silicon-llm-bench/patches/coreai-models-938d0b8-gemma4-ple.diff
   ```

2. Point the app at the patched engine and enable the gated code path:

   ```bash
   ln -sfn /path/to/patched/coreai-models ios/BenchmarkApp/Vendored/coreai-models
   xcodebuild ... SWIFT_ACTIVE_COMPILATION_CONDITIONS='$(inherited) COREAI_STATIC_INPUTS' build
   ```

   Build with a **fresh DerivedData path**. With the flag off (the default), a clean clone
   still builds and PLE models report `unsupported` instead of breaking the build.

3. Get the bundle: `huggingface.co/mlboydaisuke/gemma-4-E2B-CoreAI`
   (`gpu-pipelined-b2/gemma4_e2b_qat_decode_int4lin_tbl_aotc_h18p/`, ~2 GB; our export from
   `google/gemma-4-E2B-it-qat-q4_0-unquantized` — weights verified bit-exact against the
   official checkpoint). Side-load it, together with a `ple/` subfolder holding
   `embed_per_layer.i8` + `embed_per_layer.scale.f32` (~2.2 GB), to:

   ```
   Documents/CoreAIModels/gemma4_e2b_gpu/
   ```

4. Three integration gotchas, all already handled in this repo but listed so a port
   doesn't rediscover them:
   - **never call `engine.warmup` on a PLE bundle** (S=1-only graph → uncatchable
     binary-layer fatal; the first S=1 generate step is the warmup);
   - the bundle's `tokenizer_config.json` must carry an inlined `chat_template`
     (gemma-4 ships it as a separate `chat_template.jinja`, which swift-transformers does
     not read; without it prompts raw-encode and generation degenerates to turn markers —
     the published HF bundles already include the fix);
   - `COREAI_CHUNK_THRESHOLD=1` must be in the process environment early
     (set in `BenchmarkApp.init`, gated to gemma4 core-ai launches).

### How to read the row

- The label **"patched engine (reference)"** must travel with the number. The engine *path*
  is Apple's standard API surface, but the two `EngineOptions` additions and the export are
  ours — a stock-package user cannot run this model today.
- TTFT is the honest cost of the PLE architecture on this engine: S=1 unbatched prefill
  (~3.7 tok/s; ~5.1 s at a 19-token prompt). Do not quote decode tok/s without it.
- Memory is mmap'd-weights `phys_footprint` (clean pages uncharged) — same caveat as
  llama.cpp; footnote it, don't rank it against wired-memory runtimes.

## Class 3 — stock rows: Apple's exports on Apple's stock path (`core-ai-ane`, since 2026-10-08)

Everything is Apple's, unchanged: the bundles are made by Apple's export pipeline (apple/coreai-models
`bd3c539`, `1.0.0-10-gbd3c539`, each model's default recipe: Gemma 4 E2B / E4B through
`models/gemma4/export.py`, Qwen3 0.6B / 1.7B / 4B through `coreai.llm.export <preset> --platform iOS`,
all at `--max-context-length 2048`), and the engine is that commit's Swift package, driven through
the call sequence of Apple's `llm-runner` (`LanguageModelBundle` → `EngineFactory.createEngine(bundle:)`
→ tokenizer → stop tokens → the default warmup → `engine.generate`). No patch, no `COREAI_*`
variable, no side table. Apple's static-shape engine runs these chunked-static bundles on the Neural
Engine and no public option selects another unit, so the rows stamp `core-ai-ane` and are an arm of
their own; they never pool with classes 1 and 2.

### Exact reproduction

1. `git clone https://github.com/apple/coreai-models && git -C coreai-models checkout bd3c539`, then
   `uv sync` in it (its `uv.lock`).
2. Export, per model (cwd `models/gemma4` for Gemma 4, the repo root for Qwen3):
   `uv run export.py --model google/gemma-4-E2B-it --max-context-length 2048 --output-dir <dir>` /
   `uv run coreai.llm.export qwen3-0.6b --platform iOS --max-context-length 2048 --output-dir <dir>`.
   Apple's export does not reproduce byte for byte; the `<folder>.recipe.json` beside each of this
   repo's exports records the checkpoint revision, the yaml and every file's sha256.
3. Point `ios/BenchmarkApp/Vendored/coreai-models` at the same checkout, build the app or the
   yardstick, stage the bundle as `stock_<model>_ctx2048/` (Mac: `~/.cache/edge-llm-bench/CoreAIModels/`;
   iPhone: the app's `Documents/CoreAIModels/`) and run the cells of
   `matrices/dashboard-coreai-v1-{ios,mac}.cells`.

### How to read the row

- "Apple's export": Apple's pipeline and recipe, run by this repo; not an artifact this repo
  converted or tuned. The recipe label is Apple's (the bundle's `metadata.json` `compression`).
- The compute unit is the engine's choice (the Neural Engine), not a flag of ours.
- Two instruments, as for LiteRT-LM: the 1K text task through the harness, and Apple's
  `llm-benchmark` measurement for the protocol 1024/256 (each with its own definitions). On the Mac
  the memory figure is drawn and not ranked (the Neural Engine's weights are not charged to the
  process's `phys_footprint`).
- Definitions, staging and the disclosures: `docs/coreai-arm-v1.md`.

## Why the arm exists at all

Google evaluates this repo as a neutral cross-runtime benchmark. Dropping the Core AI arm
for Gemma-4 would hide a real capability (the model runs, at competitive quality/memory);
shipping the number unlabelled would overstate what Apple's stock engine does. The labelled
reference row + this provenance doc is the honest middle.
