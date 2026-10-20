# Dashboard cells v1 — the text-only model set (prepared 2026-09-05)

The initial cell set for the competitive dashboard kick-off on 2026-09-07:
the five text-only models the LiteRT team named on 2026-09-04, across the
three engines that publish an artifact for every one of them, on Android,
iPhone and Mac. One command per platform re-measures it. This page is the
cell table, the bundle inventory (what exists, what is missing), the
competitor-arm status including a first look at Mirai, and the open
questions for the LiteRT team.

Cells file: `matrices/dashboard-text-v1.cells` (v1: 45 cells, 5 models × 3
arms × 3 platforms; v2 since 2026-09-08 adds the Core AI arm on iPhone and
Mac — 10 rows, of which the 4 Gemma 4 rows are `exclude=` with their reason —
see "Core AI arm (v2)" below; validated by `scripts/validate_cells.py`).

```bash
./bench matrix matrices/dashboard-text-v1.cells --platform android   # Galaxy S26 or Pixel 8a (BENCH_ANDROID_SERIAL)
./bench matrix matrices/dashboard-text-v1.cells --platform iphone    # iPhone 17 Pro (BENCH_UDID)
./bench matrix matrices/dashboard-text-v1.cells --platform mac       # Mac M4 Max
```

## Model set

| Model | In v1 | Note |
|---|---|---|
| Gemma 4 E2B | yes | measured before on LiteRT (all platforms); MLX and llama.cpp rows are new |
| Gemma 4 E4B | yes | never measured in this repo on any arm |
| Qwen3 0.6B | yes | the anchor model; measured on every arm that had rows |
| Qwen3 1.7B | yes | litert-community has shipped an INT8 `.litertlm` since 2026-06-25 and the dynamic INT4 wi4b32 GPU build since 2026-08-05; the catalog carried only our own conversion until today's entry |
| Qwen3 4B | yes | LiteRT measured on iPhone (2026-08-19, thermally noisy); everything else new |
| Qwen3.5 | placeholder, disabled | held by the LiteRT team ("not all changes landed/validated"); litert-community repos refreshed 2026-09-04 (0.8B/2B int8, 4B int8 + mixed_int4) |
| LFM2.5 | placeholder, disabled | same hold; litert-community LFM2.5-1.2B-Instruct ships int4 / int4_gpu / int8 |

Task: `short-chat`, the cross-arm standard cell (same prompt and token budget
on every arm). The 1024-prefill / 256-decode / ctx-2048 column the LiteRT
team benchmarks with (`long-context-1024-gen256`, methodology
`agreed-protocol-gemma4.md`) is the natural second task and was not in v1 —
open question 3 below; the Mac leg of a deeper column (p≈2K / g=256, three
KV allocations) was measured 2026-09-18, section "Long-context column".
Since 2026-10-06 the weekly set carries it: section "Second task in the
weekly set".

## Cell table

Recipes differ per arm by design and travel in every row
(`quant-per-arm-rule`, `quant-label-rule`): LiteRT Gemma 4 is Google's wNa8o8
mobile schema (a co-designed weights+runtime package, non-transferable);
LiteRT Qwen3 0.6B/4B are TorchAO mixed INT4; LiteRT Qwen3 1.7B is dynamic
INT4 block-32 (the GPU-graph build) with the INT8 file on CPU; MLX is 4-bit
(Gemma 4: the QAT OptiQ builds, the catalog's cross-runtime build); llama.cpp
is unsloth Q4_K_M (PTQ — Google's own QAT GGUF is unloadable as shipped,
verified 2026-07-18, catalog comment).

### Android — Galaxy S26 / Pixel 8a (two LiteRT cells per model: cpu, gpu; llama.cpp = official CPU-only binary)

| Model | LiteRT-LM file (cpu / gpu) | llama.cpp GGUF | rows so far (both devices) |
|---|---|---|---|
| Qwen3 0.6B | `Qwen3-0.6B_dynamic_wi4b32_afp32.litertlm` (both; `qwen3_0_6b_mixed_int4.litertlm` until 2026-10-19, section "Qwen3 0.6B LiteRT-LM file (2026-10-19)") | `Qwen3-0.6B-Q4_K_M.gguf` (session anchor) | all three |
| Qwen3 1.7B | `Qwen3_1.7B.litertlm` (INT8) / `Qwen3-1.7B_dynamic_wi4b32_afp32.litertlm` | `Qwen3-1.7B-Q4_K_M.gguf` | none |
| Gemma 4 E2B | `gemma-4-E2B-it.litertlm` (both) | `gemma-4-E2B-it-Q4_K_M.gguf` | LiteRT gpu |
| Qwen3 4B | `qwen3_4b_mixed_int4.litertlm` (both) | `Qwen3-4B-Q4_K_M.gguf` | none |
| Gemma 4 E4B | `gemma-4-E4B-it.litertlm` (both) | `gemma-4-E4B-it-Q4_K_M.gguf` | none |

### iPhone 17 Pro and Mac M4 Max (same ids on both; LiteRT and llama.cpp on Metal, MLX on Metal; Core AI on the GPU engine since v2)

Thought-channel note (2026-09-10): `.litertlm` bundles whose header declares a `thought`
channel (litert-community's `Qwen3-1.7B_dynamic_wi4b32_afp32`, the 0.6B wi4b32 file, every
litert-torch-main export) stream their thinking on that channel. Until 2026-09-10 the Apple
LiteRT adapter capped only the visible answer, so those rows decoded several hundred hidden
tokens against the 128-token budget (the 2026-09-08 Mac row of Qwen3-1.7B: 579 tokens,
TTFT 2.2 s) and a capped run's rate was computed over a window that held them. The adapter
now counts channel text like plain content, so every arm is capped at the same total budget
and TTFT means the first generated token on every arm; rows captured before that date under
this id keep their recorded values and are read with this note.

| Model | LiteRT-LM | MLX | llama.cpp | Core AI (v2, own export) | rows so far (iPhone / Mac), v1 arms |
|---|---|---|---|---|---|
| Qwen3 0.6B | `litert-community/Qwen3-0.6B/dynamic_wi4b32_afp32` (`litert-community/Qwen3-0.6B` until 2026-10-19 and for the LiteRT-LM session anchor, section "Qwen3 0.6B LiteRT-LM file (2026-10-19)") | `mlx-community/Qwen3-0.6B-4bit` (session anchor) | `unsloth/Qwen3-0.6B-GGUF/Q4_K_M` (new catalog entry) | `core-ai/qwen3-0.6b-4bit-gpu` — INT4 dynamic, macOS-27-era export (the 26-era one decodes garbage; below) | LiteRT, MLX / LiteRT, MLX |
| Qwen3 1.7B | `litert-community/Qwen3-1.7B` (new catalog entry) | `mlx-community/Qwen3-1.7B-4bit` | `unsloth/Qwen3-1.7B-GGUF/Q4_K_M` (new catalog entry) | `core-ai/qwen3-1.7b-gpu` — INT4 dynamic | none |
| Gemma 4 E2B | `litert-community/gemma-4-E2B-it-litert-lm` | `mlx-community/gemma-4-e2b-it-qat-OptiQ-4bit` | `unsloth/gemma-4-E2B-it-GGUF/Q4_K_M` | `core-ai/gemma4-e2b-gpu` — `exclude=ple-bundle-needs-unpublished-engine-patch` | LiteRT / LiteRT |
| Qwen3 4B | `litert-community/Qwen3-4B` | `mlx-community/Qwen3-4B-4bit` | `unsloth/Qwen3-4B-GGUF/Q4_K_M` | `core-ai/qwen3-4b-gpu` — INT4 dynamic | LiteRT / none |
| Gemma 4 E4B | `litert-community/gemma-4-E4B-it-litert-lm` | `mlx-community/gemma-4-e4b-it-qat-OptiQ-4bit` | `unsloth/gemma-4-E4B-it-GGUF/Q4_K_M` | `core-ai/gemma4-e4b-gpu` — `exclude=ple-bundle-needs-unpublished-engine-patch` | none |

11 of the 45 cells already have rows in this repo; the other 34 run for the
first time on Monday, and that first run is their gate (a cell that fails
stays in the table as an `exclude=` row with the reason — `failed-runs-stay`).

## Bundle inventory (checked live on Hugging Face, 2026-09-05)

Every cell has a published artifact. Nothing needs converting. The one gap
the catalog used to carry — "litert-community has no Qwen3 1.7B" — was a
stale comment, not a missing artifact: the repo has existed since 2026-06-25
(INT8) and gained the wi4b32 GPU build on 2026-08-05; today's entry closes it.

| Arm | Artifact | Size | On the bench host now |
|---|---|---|---|
| LiteRT-LM | `gemma-4-E2B-it.litertlm` | 2.59 GB | yes — sha256 identical to HF; the repo head moved on 08-07 and 08-31 (added `-gpu` and Tensor G6 variants) but this file is unchanged since the pinned 07-10 revision |
| LiteRT-LM | `gemma-4-E4B-it.litertlm` | 3.66 GB | no |
| LiteRT-LM | `qwen3_0_6b_mixed_int4.litertlm` | 0.50 GB | no (evicted by a cache clean-up; measured before) |
| LiteRT-LM | `Qwen3-1.7B_dynamic_wi4b32_afp32.litertlm` / `Qwen3_1.7B.litertlm` | 0.98 / 2.06 GB | no |
| LiteRT-LM | `qwen3_4b_mixed_int4.litertlm` | 2.66 GB | no |
| llama.cpp | `Qwen3-0.6B-Q4_K_M.gguf` | 0.40 GB | yes |
| llama.cpp | Qwen3 1.7B / 4B, Gemma 4 E2B / E4B `Q4_K_M.gguf` | 1.11 / 2.50 / 3.11 / 4.98 GB | no |
| MLX | Qwen3 0.6B / 1.7B / 4B `-4bit` | 0.34 / 0.97 / 2.26 GB | no (Apple runners download on first use) |
| MLX | Gemma 4 E2B / E4B `-qat-OptiQ-4bit` | 4.27 / 6.52 GB text weights (+0.95 GB vision file each) | no |

The host cache feeds the Android pushes (about 22 GB to fetch for both
Android arms); the Apple runners download into their own caches on first
use (about 14 GB of MLX weights plus the LiteRT and GGUF files again). Disk
free on the host today: 276 GB.

Harness changes that came with this set (same commit): the three catalog
entries above, a display name for Qwen3 4B, and the cells file. The catalog
preflight against the currently built yardstick (built 2026-09-01) flags
exactly the three new ids — expected until the Apple binaries are rebuilt.

## Before the first run

1. Rebuild the Apple binaries so the catalog entries exist: `bootstrap.sh`
   then `scripts/build_yardstick_mac.sh` for the Mac, the iOS app through
   Xcode (signing and the increased-memory entitlements are GUI steps).
2. Pre-fetch the Android artifacts into the host cache; a multi-GB download
   inside a thermal session is wasted cooldown.
3. Keep the phones attached and, on the iPhone, Auto-Lock off: a locked
   phone refuses the headless launch (it cost the E4B LiteRT cell on
   2026-09-05). Set `BENCH_UDID` (`./bench doctor` warns that 7 devices are
   visible). Check the sibling lanes' device holds before starting.
4. Storage is the binding constraint on phones, not memory: the full set
   needs about 28 GB on an Android device (models plus LiteRT's XNNPACK
   caches) and about 35 GB of app storage on the iPhone (staged files plus
   in-app MLX downloads); the split Android cells files exist for that. The
   4B-class models themselves fit the 8 GB Pixel 8a on every arm (2026-09-05;
   not in the 2026-10-07 sitting — section "Per-device exclusion").
5. Budget about half a day per platform including downloads; cooldowns
   dominate (300 s before every Gemma 4 and 4B cell).

## First pass (2026-09-05)

The set has been run end to end on all four devices the same day: the Galaxy S26, the Mac M4 Max, the Pixel 8a, and 14 of 15 cells on the iPhone 17 Pro. S26 (campaign
`results/raw/2026-09-05-dashboard-v1-android/`): 15 cells × 3 runs, every
run at thermal nominal, no gate flags, no failures — including the
first-ever rows for Gemma 4 E4B and Qwen3 1.7B on any arm, and the first
Gemma 4 CPU rows. The 4B-class cells fit: Qwen3 4B and Gemma 4 E4B hold
5.4–5.9 GB resident on the CPU arms of this 12 GB phone, which is the number
to hold against the 8 GB Pixel 8a on Monday.

The Mac M4 Max pass followed the same morning (campaign
`results/raw/2026-09-05-dashboard-v1-mac/`): 15 cells × 4 runs (anchor 3),
every run at thermal nominal, all 15 first-time Mac cells ran including the
6.5 GB OptiQ E4B build. One gate retry: the llama.cpp Qwen3 0.6B capture
spread 12% on its first attempt, was quarantined as `.jsonl.attempt1`, and
the retry stands. Prefill figures from the short-chat prompt (about 21
tokens) are dominated by fixed overhead and are not the card-comparable
prefill number — that is the 1024-token task (open question 3).

iPhone 17 Pro, same afternoon (campaign `results/raw/2026-09-05-dashboard-v1-ios/`):
12 of the 15 cells, 4 runs each (anchor 3), plus two of the three E4B cells in an
evening fill-in (below). The phone sat at thermal "fair"
while charging, the state this device reports when plugged in a warm room
(devices/iphone-17-pro.md); the MLX anchor read 179 tok/s, the same value
as the newest all-nominal anchor (2026-09-04), so the session is admissible
under that device's rule, and every capture carries its `HOT` gate note
(quarantined first capture in `device-jsonl-flagged/`, retry kept). The
three Gemma 4 E4B cells did not produce rows: the LiteRT launch was refused
because the phone was locked at that moment, the MLX cell failed with "No
space left on device" while fetching the 7.5 GB OptiQ E4B repo (the phone's
storage was full after the day's staging and downloads), and the llama.cpp
cell's app process died during model load with the storage still full — not
established as a memory ceiling. A fill-in attempt for the E4B cells at
14:50 lost the device connection before its anchor ran (aborted, noted in
`2026-09-05-dashboard-v1-ios-e4b/`). A second fill-in in the evening
(`2026-09-05-dashboard-v1-ios-e4b2/`, own anchor at nominal, 177–179 tok/s)
captured the LiteRT and llama.cpp E4B cells — both gate-retried, the LiteRT
capture spreading 34% on its first attempt and its retry crossing into fair —
while the MLX E4B cell failed again with "No space left on device" after
fetching 40% of the 7.5 GB repo. On 2026-09-06, with storage freed, a fourth
fill-in (`2026-09-06-dashboard-v1-ios-e4b4/`, anchor nominal) completed the
fetch and then lost the app to a SIGKILL during model load: the 6.5 GB of
OptiQ E4B text weights do not fit the app's memory on this phone. That row now
carries `exclude=app-killed-at-model-load-sigkill` in the cells file; the
smaller `mlx-community/gemma-4-e4b-it-4bit` build (5.1 GB) is the candidate
for an iPhone MLX E4B row (open question 6). The LiteRT E4B retake in the same
session ran hot again (both captures HOT, retry kept at 14–15 tok/s in fair),
so the phone's E4B LiteRT figure is a fair-state number until a cooler sitting.

Pixel 8a, afternoon and evening, as three sessions because the phone had
14–21 GB free and the full set needs about 28 GB on the device
(campaigns `2026-09-05-dashboard-v1-pixel8a-a2-android/`, `-b1-android/`,
`-b2-android/`, cells files `dashboard-text-v1-android-{a,b1,b2}.cells`,
each with its own anchor; my pushes were removed between sessions): all 15
cells, 3 runs each, every run at thermal nominal, no gate flags. Both
4B-class models fit the 8 GB phone on every arm, so the memory-risk cells
listed above became ordinary rows. A first attempt at 12:07 was aborted: a sibling lane's
benchmark was running on the phone at the same time (its quarantined
captures and note stay in `2026-09-05-dashboard-v1-pixel8a-a-android/`);
the phone is now shared through that lane's hold file (`device-busy` note
in the operating memory).

Two reading notes for the Android rows, both properties of the harness, not
of the engines: run 1 of a fresh (model, backend) is the engine-cache build
and is stamped `firstEver` (summaries here drop it); and the memory column
is VmRSS, which does not count the GPU arm's buffers — the LiteRT GPU rows'
resident figures are not comparable with the CPU arms' (methodology
`android.md`). The Android llama.cpp rows run at `n_ctx` 4096, the lane's
standing setting, while the LiteRT rows run at each bundle's default context
— both recorded per run (`conditions.contextTokens`); decode on a
150-token conversation is not expected to move with it, the resident memory
column does (an inference, not measured here). The litert-community card's
own S26 figure for the Qwen3 1.7B GPU file (40.5 tok/s, 205-token prompt,
`litert_lm_advanced_main`) sits above this cell's 33.7 — a different
protocol; a card-comparable number is the 1024-token task's to produce.
Every S26 cell that had an earlier row (the anchor and the three Qwen3 0.6B
cells) reproduces its 2026-08-25 value within a few percent, so the session
is not a drift outlier.

Mac reading note: every llama.cpp cell on the Mac completes its four runs
and writes its records, then the yardstick process aborts at exit inside
llama.cpp b8999's Metal teardown (`ggml_metal_rsets_free` → `ggml_abort`,
crash reports of 2026-09-05). The runner records that exit code as `FAIL`
in `FAILURES.txt`; the rows stand (`failed-runs-stay`) and the gate verdicts
are unaffected. It is a harness/engine exit-path defect to chase, not a
measurement.

Per-cell medians are in `results/summary/device-runs.csv` (campaigns
`2026-09-05-dashboard-v1-android` and `-mac`); cross-runtime standings
render locally (`LEADERBOARD.md`) and are not published in this repo by
design.

## Competitor arms

| Arm | Platforms | In v1 | Status |
|---|---|---|---|
| LiteRT-LM | Android, iPhone, Mac | yes | v0.18.0 on Android since 2026-10-15 (v0.16.0 until the 2026-10-14 sittings) and on the Mac since 2026-10-11; the iPhone 18 Pro's pinned app build stays on v0.16.0; pinned in `android/engine-pins.json` `android_pins` / `environment.lock.json`; Android binary built from source at the tag — releases ship none |
| MLX (`mlx-swift-lm` @ 60bd0d7) | iPhone, Mac | yes | Gemma 4 loads only at the 2026-07-06 re-upload revision of the mlx-community repos, which is HF main today |
| llama.cpp b8999 | Android, iPhone, Mac | yes | Android: official CPU-only binary; the NPU (Hexagon) and Adreno GPU (OpenCL) rows run the release's official Snapdragon asset as a side build — section "NPU and Android GPU rows" below; Apple: arm wired, no rows in this repo yet |
| Core AI (Apple) | iPhone, Mac | v2 (2026-09-08) | own exports, side-loaded; Qwen3 0.6B/1.7B/4B rows active, the Gemma 4 rows `exclude=` because their per-layer-embedding bundles need the unpublished engine patch — "Core AI arm (v2)" below |
| Core AI stock (`core-ai-ane`) | iPhone, Mac | separate cells (v3, 2026-10-08) | Apple's exports on the Neural Engine, all five models; wired, not measured yet — "Core AI arm (v3)" below |
| Mirai (uzu) | Mac | separate cells | wired on Mac 2026-09-24, smoke only; [docs/uzu-arm-v1.md](uzu-arm-v1.md) |
| ONNX Runtime GenAI | Mac (CPU, WebGPU), Android (CPU) | separate cells | wired 2026-10-07, not measured yet; "ONNX Runtime GenAI arm (v1, 2026-10-07)" below |

## Core AI arm (v3, 2026-10-08): the stock arm

A second Core AI arm runs Apple's own toolchain end to end: bundles made by Apple's export pipeline
(apple/coreai-models `bd3c539`, unchanged, each model's default recipe, context 2048), which include
Gemma 4 E2B / E4B since #332 moved their per-layer embeddings to `auxiliary_assets`, run by Apple's
static-shape engine through `llm-runner`'s call sequence on the Neural Engine (no public option
picks another compute unit). Rows `core-ai core-ai/<model>-stock-ctx2048 … backend=ane` stamp
`core-ai-ane` and never pool with the own-export rows below (`core-ai`), which stay as they are. Its
cells are their own files, `matrices/dashboard-coreai-v1-{ios,mac}.cells` (the 1K text task and the
protocol 1024/256 — Apple's `llm-benchmark` measurement — beside the same model's LiteRT-LM rows, one
sitting for both), not the weekly file yet. Pins, recipes, definitions, staging and disclosure:
[docs/coreai-arm-v1.md](coreai-arm-v1.md).

## Core AI arm (v2, 2026-09-08)

### Why v1 left it out

- The v1 rule for an arm was "a published artifact for every model in the
  set". Apple ships no Core AI bundle for any of the five; the bundles were
  our own exports, and only the Qwen3 0.6B one was staged on the phone
  (measured 2026-08-26). Gemma 4 E2B/E4B additionally need
  `EngineOptions.staticInputBuffers`, which is not in Apple's released
  `coreai-models` (0.1.0, 0.2.0): they run only on our patched engine
  (`COREAI_STATIC_INPUTS`, `methodology/core-ai-arm-provenance.md`), so that
  half of the arm was not independently reproducible — the
  `environment.lock.json` caveat.
- On the Mac the harness had no protocol-identical Core AI path at all: the
  only wrapper was Apple's external `llm-benchmark` binary
  (`scripts/coreai_mac_wrapper.sh`), which runs its own synthetic
  prefill/decode with its own timing and no `--context-tokens`. A number
  from it could not sit in the same short-chat table as the other arms, and
  the importer says so in every record's provenance note.
- The recurring job was sized as one device per firing with a person
  reviewing each morning; a fourth arm whose rows would mostly fail at load
  (nothing staged) adds review lines without adding measurements.

### What changed for v2

- The Qwen3 exports are published and fetchable by a third party:
  `mlboydaisuke/qwen3-0.6b-CoreAI-official` (`macos/`, the macOS-27-era
  re-export — see the finding below), `mlboydaisuke/qwen3-4b-CoreAI-official`
  (`macos/`), and for 1.7B the phone bundle
  (`mlboydaisuke/qwen3-1.7b-CoreAI-official` `ios-gpu/`, an h18p compile);
  the Mac 1.7B row runs a local 2026-08-18 export that is not published yet
  (its `main.hash` and byte size go to every session's
  `session_provenance.txt`, and `models/artifact-bytes.json` names it).
- Finding while staging (2026-09-08): the macOS-26-era 0.6B export behind
  the catalog id `core-ai/qwen3-0.6b-gpu` — the bundle the phone's
  2026-08-26 rows ran, `main.hash` `17cfae91…` — decodes garbage on the
  `coreai-models` 0.2.0 engine: every run's `outputSample` is
  `[nodeelehandlinghandling…`, on the phone in August and on the Mac today
  (1127 tok/s warm — the speed of degenerate generation, not a measurement).
  The 27-era re-export of the same 4-bit dynamic recipe (`macos/`,
  `main.hash` `9752caf7…`) decodes coherent text at 538 tok/s on the Mac, and
  a local 2026-08-17 export at 314 tok/s; the card's "2.2× slower" was the
  price of correctness. The dashboard rows therefore use a new catalog id,
  `core-ai/qwen3-0.6b-4bit-gpu` ("INT4 (dynamic, 4bit; macOS-27-era
  export)", folder `qwen3_0_6b_4bit_gpu`), on both platforms; the old id
  stays in the catalog with the note so the August rows keep their identity,
  and those rows should be read as not valid. The 1.7B and 4B exports decode
  coherent text (checked the same way).
- The Mac yardstick now links `CoreAILM` and runs `CoreAIRuntime` — the
  same adapter the iOS app ships, the same prompt, token budget, cooldowns,
  gate and record as every other arm (`ios/BenchmarkApp/project.yml`
  yardstick target; `scripts/bench_matrix_mac.sh` sends core-ai prompt
  tasks through yardstick and keeps the `llm-benchmark` wrapper for
  `native-benchmark-*` cells only). No record-schema change: the row is a
  `core-ai` row like the 2026-08-26 iPhone rows.
- Bundles are side-loaded once and stay (Mac: `~/.cache/edge-llm-bench/CoreAIModels/`,
  or `BENCH_COREAI_MODELS_DIR` — a local directory outside iCloud Drive, since
  evicted files fail to open headlessly (docs/OPERATIONS.md, Known limits); phone: the app's
  `Documents/CoreAIModels/<folder>/`), the staging recipe is below. A bundle
  that is not staged renders "not yet measured" (the Mac runner logs
  `SKIPPED … reason=coreai-bundle-not-staged`), never a number.
- The Gemma 4 rows stay in the file as
  `exclude=ple-bundle-needs-unpublished-engine-patch`. The reason is the
  datum (`failed-runs-stay`); when Apple publishes the static-input API or
  the patch lands upstream, the two rows per platform flip to active with
  no redesign of the set.
- The table gained a bandwidth-utilization column (`bw`, `scripts/render_dashboard.py`):
  decode tok/s × bytes per token ÷ the device's memory-bandwidth ceiling.
  Ceilings are cited per device in `devices/memory-bandwidth.json` (Mac
  Studio: Apple's 546 GB/s; Galaxy S26: 84.8 GB/s derived from Qualcomm's
  "LP-DDR5x up to 5300 MHz" and marked `~`; iPhone 17 Pro: a 76.8 GB/s
  estimate from a third-party LPDDR5X-9600 figure, marked `~`; Pixel 8a: no
  citable figure, so n/a). Bytes per token come from
  `models/artifact-bytes.json` (`scripts/artifact_bytes.py --refresh` reads
  whole-artifact sizes from the Hub): the artifact's weight bytes minus the
  tables a decode step gathers instead of streams — Gemma 4's per-layer
  embedding table (1.6–3.0 GB of every Gemma 4 artifact: `per_layer_token_embd`
  in the GGUF, `embed_tokens_per_layer` in the MLX safetensors, the
  `per_layer_embedder` section of the `.litertlm`), a LiteRT bundle's separate
  int8 input-embedding table, and its audio/vision/drafter sections
  (`scripts/artifact_streamed_bytes.py` reads the containers; the numbers and
  the rule per entry are in the registry). Tied embeddings stay counted as
  the LM head. Without that subtraction the Gemma 4 rows read above 100%.
  An own-export arm next to published-artifact arms is readable only when the
  recipe is visible in the number: a 4-bit and an 8-bit artifact of one model
  are different byte counts, and the column shows that instead of hiding it
  in tok/s. It is an estimate, never a bus counter and never a ranking.

### First v2 session (Mac Studio, 2026-09-08)

Run through the recurring job (`./bench dashboard-job m4max --once`,
campaigns `2026-09-08-dashboard-v1-m4max-anchor-mac` and
`2026-09-08-dashboard-v1-m4max-mac`), admitted on its anchor (nominal, 1.045
of the newest admitted session's anchor; the payload's own anchor 0.959 of
the probe), 18 of 18 active cells with records, 4 runs each (anchor 3), every
run at thermal nominal, 1 h 04 min from anchor to close. The three Core AI
cells ran like any other arm: coherent output (the `DEGENERATE` gate passed
on every cell), warm spreads of 1.5 / 1.1 / 0.5 %, and the bundle identity
of each in `session_provenance.txt`. Their warm medians and bandwidth
readings, single-arm facts: Qwen3 0.6B 533.6 tok/s (bw 32.8 %), Qwen3 1.7B
310.9 tok/s (55.1 %), Qwen3 4B 158.9 tok/s (65.9 %). Notes the session
carries: the five llama.cpp cells recorded their runs and then aborted at
exit as before (`FAILURES.txt`, the b8999 Metal-teardown defect; rows
stand), and the LiteRT Gemma 4 E4B cell was gate-retried on a 30 % warm
spread and its retry kept at 41.9 % (`FLAGGED.txt`, ⚠ in the table): in
both captures one warm run of four stalled (70 and 58 tok/s against 100,
with the p95 inter-token latency doubled) while the other runs matched the
2026-09-05 session's 100 tok/s. This was the first sitting run side by side
with a phone sitting (the Pixel 8a's, on the host over adb, pushing the 5 GB
E4B GGUF during those minutes); whether that host-side traffic caused the
stalls is not established — the same cell had no stall on 2026-09-05 with
nothing running alongside. A targeted retake (anchor + that cell) in a quiet
window is the design's remedy if it recurs.

The iPhone's first automatic firing (2026-09-09 05:30) ran the v2 file with
the old app and no Core AI folders staged: the 0.6B cell failed with
`not_in_catalog` (the installed app predates the new id), and the 1.7B / 4B
cells fell in the window after the phone stopped accepting launches at 06:42
(`docs/dashboard-recurring-job-v1.md` §8, the two gaps). The app has since
been rebuilt from the command line with the two memory entitlements
(`xcodebuild … -allowProvisioningUpdates DEVELOPMENT_TEAM=… PRODUCT_BUNDLE_IDENTIFIER=com.daisukemajima.llmbench`,
`.build/dd-ios`). It was installed and the three folders staged over USB on
2026-09-09 13:30 (the upgrade kept the app's data container; 0.6B 27 s,
1.7B 37 s, 4B 152 s), and a functional launch of the 0.6B cell decoded
coherent text at thermal nominal — so the phone's three Core AI rows can run
at its next sitting.

Retakes of the lost cells on 2026-09-09 (campaigns
`…-iphone17pro-retake-*` 13:47–14:33 and `…-retake2-*` 16:13–17:17, both
stopped by hand at a cell boundary when the owner went out; both admitted on
their anchor) recorded the Core AI 0.6B (the new id) with coherent output at
169 tok/s warm, and found two things: the published 1.7B phone bundle
(`mlboydaisuke/qwen3-1.7b-CoreAI-official` `ios-gpu/`) fails to load with
`unsupportedEngineVariant("Variant 'coreai-pipelined' incompatible with
model structure")` — it is not the pipelined-engine structure the catalog id
forces, so the phone's `qwen3_1_7b_gpu` folder is being replaced by an h18p
compile of the same 2026-08-18 export the Mac row runs (one export, both
platforms); and the MLX Gemma 4 E2B repo is no longer on the phone (freed
on 2026-09-06) and its in-app download stalled at 0 % for 35 minutes, so it
will be staged over USB from the host's Hub cache instead. The remaining
cells are listed in `matrices/retakes/2026-09-09-iphone17pro-remaining-3.cells`.
To finish the retake from any session, with the phone on USB and idle:

```bash
UDID=A6F3E849-1947-5202-9AD1-9C881CA58EEF; APP=com.daisukemajima.llmbench
# 1. the 1.7B phone bundle = h18p compile of the Mac row's export (replaces the HF ios-gpu folder)
xcrun devicectl device copy to --device $UDID --domain-type appDataContainer --domain-identifier $APP \
  --source ~/bench-coreai-staging/ready/qwen3_1_7b_gpu_from-mac-export --destination Documents/CoreAIModels/qwen3_1_7b_gpu
# 2. the MLX Gemma 4 E2B repo from the host's Hub cache (HFDownloader short-circuits on a non-empty dir)
xcrun devicectl device copy to --device $UDID --domain-type appDataContainer --domain-identifier $APP \
  --source ~/.cache/huggingface/hub/models--mlx-community--gemma-4-e2b-it-qat-OptiQ-4bit/snapshots/b7a34a6d76bbebebe700ffe68b57c97a4e3c3622 \
  --destination Documents/models/mlx-swift/mlx-community__gemma-4-e2b-it-qat-OptiQ-4bit
# 3. the remaining 9 cells + anchor, as their own admitted session (about 2 h)
./bench dashboard-job iphone17pro --once --cells matrices/retakes/2026-09-09-iphone17pro-remaining-3.cells --suffix=retake3
```

(`devicectl` copies are serialized, one at a time; the snapshot dir holds symlinks into
`blobs/`, which `copy to` follows.)

### Bundles per row

| Row | Bundle (engine `coreai-pipelined`, dynamic export) | Weight bytes | On the Mac | On the iPhone |
|---|---|---|---|---|
| `core-ai/qwen3-0.6b-4bit-gpu` | `mlboydaisuke/qwen3-0.6b-CoreAI-official` `macos/qwen3_0_6b_4bit_dynamic.aimodel` (the 27-era re-export, `main.hash` `9752caf7…`; "INT4 (dynamic, 4bit; macOS-27-era export)") | 335,678,144 | `~/Documents/CoreAIModels/qwen3_0_6b_4bit_gpu/`, AOT h16c | not staged — an h18p compile of the same `.aimodel`; the folder on the phone (`qwen3_0_6b_gpu`) is the retired macOS-26-era export that decodes garbage |
| `core-ai/qwen3-1.7b-gpu` | Mac: local export `~/code/coreai/coreai-models/exports/qwen3_17b_gpu_dyn` (2026-08-18, `main.hash` `5f58dce7…`); phone: `mlboydaisuke/qwen3-1.7b-CoreAI-official` `ios-gpu/qwen3_1_7b_dynamic.h18p.aimodelc` | 968,606,951 (Mac export) | `qwen3_1_7b_gpu/`, AOT h16c | not staged — a human step |
| `core-ai/qwen3-4b-gpu` | `mlboydaisuke/qwen3-4b-CoreAI-official` `macos/qwen3_4b_4bit_dynamic.aimodel` (compiled 2026-06-11) | 2,263,457,254 | `qwen3_4b_gpu/`, AOT h16c | not staged — needs an h18p compile of the same export (about 1.6× the Mac size on device) |
| `core-ai/gemma4-e2b-gpu`, `core-ai/gemma4-e4b-gpu` | `mlboydaisuke/gemma-4-E2B-CoreAI`, `-E4B-CoreAI` (`_tbl` decode graph + PLE tables) | — | excluded | excluded |

### Staging recipe

Mac (once; the folders persist across sessions; `xcrun coreai-build` is in
the Metal toolchain of the Xcode 27 beta):

```bash
D=~/.cache/edge-llm-bench/CoreAIModels; mkdir -p $D   # local, outside iCloud Drive
# 0.6B and 4B from the Hub (the `macos/` folders), 1.7B from the local export
hf download mlboydaisuke/qwen3-0.6b-CoreAI-official --include "macos/*"
hf download mlboydaisuke/qwen3-4b-CoreAI-official   --include "macos/*"
# per bundle: <folder>/{metadata.json, <name>.aimodel/, tokenizer/}, then
xcrun coreai-build compile $D/<folder>/<name>.aimodel --output $D/<folder> \
    --platform macOS --preferred-compute gpu --architecture h16c
# and point metadata.json "assets.main" at <name>.h16c.aimodelc
```

iPhone (a human step, USB — a multi-GB push over Wi-Fi dies; the app id is
the one in `ops/dashboard-v1/schedule.json`):

```bash
xcrun devicectl device copy to --device <udid> --domain-type appDataContainer \
    --domain-identifier <app> --source <folder> --destination Documents/CoreAIModels/<folder>
```

The 1.7B phone bundle is the published `ios-gpu/` folder as is; the 0.6B and
4B ones are `xcrun coreai-build compile … --platform iOS --preferred-compute
gpu --architecture h18p` of the `macos/` exports with `assets.main` repointed.
All three folders were prepared on the bench host on 2026-09-08 under
`~/bench-coreai-staging/ready/{qwen3_0_6b_4bit_gpu,qwen3_1_7b_gpu,qwen3_4b_gpu}`
(the same layout the 2026-08-26 staging used), so staging is one `copy to`
per folder over USB. Until a folder is staged its row fails at load on the
phone and stays in the table as the datum.

### Mirai precheck (github.com/trymirai, 30 minutes on 2026-09-05)

Facts, read from the repositories and model cards:

- Engine `uzu`: Rust, MIT, about 1.7k stars, weekly releases (0.5.23 on
  2026-09-03). Backends `metal` and `cpu`; targets macOS and iOS; Windows,
  Linux and wasm marked "in progress"; no Android target (the site says
  "Soon").
- Bindings for Swift, Python and TypeScript. A Homebrew CLI (`mirai`) with a
  `bench` subcommand (model path, task file, output path — the task format
  is not documented in the README) and an OpenAI-compatible server.
- Own model format. The converter `lalamo` (Python/JAX, MIT) carries specs
  for Gemma 4 E2B/E4B and their `-it` variants and for Qwen3 0.6B / 1.7B /
  4B / 8B / 14B, so the v1 set is convertible in principle.
- Published artifacts (Hugging Face org `trymirai`, 25 models): Qwen3.5
  0.8B–9B, Qwen3.6/3.8 27B and the LFM2.5 family, each in an "M" (4-bit
  asymmetric integer, group 32, Hadamard rotations) and an "L" quantization.
  Nothing for Gemma 4 or Qwen3.
- Model cards carry the base model's license (Apache-2.0 for the Qwen ones).

What a Mirai column would take: artifacts for the five models (convert with
`lalamo` ourselves as disclosed own-conversion rows, or ask Mirai to
publish), a new arm (Mac first through the CLI, the external-binary pattern
Core AI uses; iPhone through the Swift package), and a check of what `bench`
actually measures before any of its numbers sit next to ours. Apple-only, so
no Android column. Row status: investigate.

## Long-context column, Mac leg (2026-09-18)

Open question 3 ("second task") measured on the Mac for the five models, on
LiteRT-LM cpu / LiteRT-LM gpu / llama.cpp, at prefill ≈2K / decode 256, with
the KV allocation as a third axis — cells file `matrices/dashboard-longctx-v1.cells`,
campaign `results/raw/2026-09-18-dashboard-longctx-v1-m4max-mac/` (NOTES.md
there has the full table, the cold regime and the probe evidence).

- Task `long-context-2048-gen256`: the forced-output long-context prompt at
  27 filler blocks — 1,986 Qwen3 / 1,637 Gemma-4 tokens as the engines count
  them — with a 256-token budget. The p=1024/g=256 protocol cell stays as it is;
  this is the deeper column beside it.
- Allocation ladder `context-tokens=` 2304 / 4096 / 8192 per (arm, model):
  LiteRT-LM `maxNumTokens`, llama.cpp `n_ctx`. Round mode on the Mac runner
  (`ROUNDS=8 RUNS=2`, order reversed on even rounds) so each allocation is
  measured next to its partners in every round; warm median of 8, every run
  thermal-nominal, session anchor 0.985 of the 09-14 reference.
- The Mac now has a `litert-lm-cpu` arm (`yardstick --litert-backend cpu`,
  `backend=cpu` on a mac litert-lm row) with the same record spelling as
  Android; the LiteRT 1.7B CPU row uses the card's CPU file (dynamic INT8,
  catalog id `litert-community/Qwen3-1.7B/int8`), the GPU row the wi4b32 build.

What the column says, per arm — the change of decode at depth when only the
allocation moves, 2304 → 4096 → 8192 (warm median of 8; absolute rates are in
the campaign's per-arm ladders):

| arm | Qwen3-0.6B | Qwen3-1.7B | Qwen3-4B | Gemma 4 E2B | Gemma 4 E4B |
|---|---|---|---|---|---|
| LiteRT-LM gpu (Metal-backed) | −2 % / −18 % (wi4b32 file) | −1 % / −13 % | — (see below) | −0 % / −12 % | −0 % / −9 % |
| LiteRT-LM cpu (XNNPACK) | −25 % / −60 % (wi4b32 file) | +1 % / +1 % (INT8 file) | — | −8 % / −22 % | −6 % / −21 % |
| llama.cpp (Metal) | +0 % / +3 % | +1 % / +0 % | +1 % / +0 % | −0 % / −1 % | +1 % / +1 % |

Reading (single-arm facts; the cross-arm standing stays local):

- LiteRT-LM decode at a fixed filled length falls with the *allocated* KV on
  both backends of this Mac — catalog row K5 (measured on gemma-3-270m CPU)
  holds on the dashboard bundles, and the GPU arm pays too (X2's open cell);
  at 4,096 the GPU is within 2 % of 2,304 while the CPU already loses 6–25 %.
  Prefill follows the same shape (GPU −12 to −36 %, CPU −23 to −50 % at 8,192).
- Which bundle pays is an export property: the Qwen3-1.7B dynamic INT8 file
  is flat in rate and in resident memory across the ladder (its KV is sized at
  export; `maxNumTokens` does not resize it), the wi4b32 and Gemma 4 bundles
  grow with the allocation.
- llama.cpp is flat on all five (±3 %): attention over the filled length.
- The dashboard's Qwen3-0.6B / Qwen3-4B LiteRT files (`mixed_int4`) are
  `exclude=` rows: a 2,048-entry KV (`Prefill input length exceeds available
  state entries (remaining capacity: 2048)`), and a `maxNumTokens` above it
  is neither clamped nor refused — at 8,192 the run reports a normal-looking
  270 tok/s while the engine logs 10,666 "Invalid decode and sample result"
  warnings. The 0.6B row runs the repo's wi4b32 file (a different recipe,
  disclosed in the id); 4B has no runnable published LiteRT file for this
  task. That is open question 7 below.
- Gemma 4 E2B on the GPU arm stops at 77 / 93 tokens (EOS) at 2,304 / 8,192
  and fills 256 at 4,096 — greedy output differs with `maxNumTokens` on that
  path; recorded, not investigated.

Android and iPhone legs of the same column: not yet (devices off adb since
09-15; the iPhone needs the `--litert-backend` plumbing in the app driver).

### Long-context column, S26 leg: the two open cells (2026-10-12)

The S26 leg (`results/raw/2026-09-2*-dashboard-longctx-v1-s26-android-*`) left
two LiteRT-LM cells open; both were measured on 2026-10-12 with v0.16.0
`litert_lm_advanced_main`, screen off, no reboot
(`results/raw/2026-10-12-catalog-x2-s26-android/README.md`):

- GPU decode at a constant answer length. Under `long-context-2048-gen256`
  Gemma 4 E4B refused the lorem blocks in 50–61 tokens and E2B stopped at 93
  tokens at 8,192, so the new task `long-context-2048-gen256-noref` keeps the
  27 blocks with a tail that calls them filler: every answer is 256 tokens,
  0 `Invalid decode`. From 2,304 to 8,192, E2B decode stays within ±1.2 %
  (warm 25.6 / 25.8 / 25.3 tok/s, 6 rounds); E4B is within 3 % at 4,096 and
  3.9–5.0 % lower at 8,192 (cold, two sittings of 4 rounds, never pooled).
  Prefill falls 31 % (E2B) and 19 % (E4B) at 8,192.
- CPU per-op profile (E2B, `--enable_profiling`, prefill 1,024 / decode 256):
  the attention batch matmul `Batch Matrix Multiply (NC, F32, QC8W)` over the
  rank-4 INT8 KV cache grows 4.73 → 6.55 → 16.98 ms per decode step at
  2,304 / 4,096 / 8,192, with Softmax, `SELECT_V2` and the INT8 `Convert`
  beside it; the weight GEMVs stay flat to 4,096. `--max_num_tokens=1280`
  with the 1,024-token prefill is refused at prepare (exit 13).
- Every GPU launch is `cpu-capped` and pools, marked ◇ (fairness rules §13;
  `scripts/longctx_ab_report.py` keeps such records since this lane); the
  three sittings' anchors were admitted (1.003 / 1.000 / 1.015).

## Second task in the weekly set: p1024 / d256 / ctx 2048 (2026-10-06)

Open question 3 is answered for the weekly job: since 2026-10-06 every sitting
measures the protocol cell `long-context-1024-gen256` beside `short-chat`
(owner decision 2026-10-06; the device time it adds was accepted the same
morning).

Rows. Every active `short-chat` row on LiteRT-LM, llama.cpp and MLX has one
`long-context-1024-gen256` twin with the same model id, `backend=`, `file=` and
`cooldown=`, placed after its model block's short-chat rows, in the same arm
order: 45 rows, 15 per platform. A twin carries no `anchor=` / `runs=` — the
session anchor stays the short-chat cell, and the 0.6B anchor model's 1024 row
is an ordinary payload row (on Android it sits in storage half a, where that
model's file is pushed). An `exclude=` short-chat row keeps its reason on the
twin (iPhone MLX Gemma 4 E4B, `app-killed-at-model-load-sigkill`:
failed-runs-stay). Core AI has no 1024 rows. The Android storage halves
(`dashboard-text-v1-android-{a,b1,b2}.cells`) carry the same lines as the
parent, each model's 1024 rows in the half that pushes its files. The
1024-only files `matrices/dashboard-longctx1024-v1.cells` (Mac + iPhone) and
`matrices/dashboard-longctx1024-v1-android-{a,b1,b2}.cells` hold the same
1024 lines with the session anchors in front, for a sitting that measures only
the second task (`./bench dashboard-job <device> --cells <file>`);
`android/bench/test_longctx1024.py` pins that the two sets carry identical
lines.

The task. `prompts/text/long-context-1024-gen256.txt`: 18 lorem blocks plus
the forced-output tail, byte-identical to the Swift task
(`LongContextTask`, `forceLongOutput`): about 1,339 Qwen3 / 1,106 Gemma 4
tokens with the chat template (the count is the engine's; each record's
`promptTokenCount` is the ground truth); output budget 256 (`budgets.tsv`).
The same text goes to every arm. Since 2026-10-19 the tail is the 2K ladder's
`-noref` sentence, under the same id and budget: "1K task tail (2026-10-19)"
below.

`context-tokens=2048` on every LiteRT-LM and llama.cpp row: the agreed
protocol's context (`methodology/agreed-protocol-gemma4.md`: prefill 1024,
decode 256, context forced to 2048 for Gemma 4; the set uses the same
allocation for the Qwen3 rows, so one column is one allocation) —
LiteRT-LM `maxNumTokens`, llama.cpp `n_ctx`. On Android the option also
selects the engine path: a prompt task with `context-tokens=` runs
`litert_lm_advanced_main --max_num_tokens=2048 --max_output_tokens=256
--num_iterations=2` (`run_cell.context_prompt`), the only v0.16.0 path that
applies an output budget at all: the plain `litert_lm_main` the short-chat
rows run accepts both flags (they are shared flag definitions) but never
reads them (v0.16.0 `runtime/engine/litert_lm_main.cc`). Without the option
the 256-token budget would not hold. The `mixed_int4` Qwen3 bundles'
2,048-entry KV (open question 7) holds 1,339 + 256 tokens; the Qwen3-1.7B
INT8 file sizes its KV at export,
so `maxNumTokens` does not resize it, and its record's allocation witness
echoes the requested value (the S26 2,048-task sitting of 2026-09-23 read
2,304 / 4,096 / 8,192 at those three settings) — the witness is the setting,
not the cache size.

MLX rows carry no `context-tokens=`. The yardstick's `MLXRuntime` has no
`prepareContext` (the `LLMRuntime` default is a no-op) and passes no KV
limit to `GenerateParameters`, so mlx-swift-lm grows its cache with the
sequence; the option would change only the record's `contextTokensConfigured`,
which on an MLX row is the runner's estimate (prompt characters / 3 + 16 +
budget + 512), not an allocation.

Reading the Android rows. One launch writes two records, iteration 1 (cold)
and iteration 2 (warm, a fresh Conversation on the loaded engine); the
Android headline regime stays cold. On this path the S26 GPU logs of
2026-09-20 all carry `GPU sampler unavailable. Falling back to CPU sampling`
(the sampler libraries do not load under `advanced_main`), so the GPU arm's
1024 decode includes CPU-side sampling; whether its short-chat launches on
the plain main sample on the GPU is not checked here. The first
1024 launch of a bundle and backend on a phone is a cache build (`firstEver`:
the context-prompt marker is keyed on the engine artifact and the
allocation) and drops out of the summaries like every cache build. The gate:
until 2026-10-06 the Android runner counted records, not launches — it
judged the newest three records (one and a half launches) and, on a flag,
quarantined three of the six, so the retry would have stood beside half of
the capture it replaced (found offline, before the weekly set carried such
a cell); `run_campaign.py` now quarantines both records of every
launch and judges the cold records (`cell_gate.py --basis cold`), and
`test_longctx1024.py` pins both. Whether the context-prompt path writes
engine caches of its own beside the bundles is not measured; the per-half
footprint the job logs at the first such sitting is.

Display. When the numbers exist, the 1024 cells sit beside the short-chat
cells as a second workload, not as a replacement. Today
`scripts/render_dashboard.py` puts one cell per model and arm in the grid —
the first task in file order, short-chat — and lists the 1024 cells only in
the per-cell detail table, without a task column; the renderer change is a
separate one.

Device time per weekly sitting (estimates, not measurements, 2026-10-06;
`ops/dashboard-v1/schedule.json` carries the last column until the first
sittings with the second task replace it):

| device | last sitting, minutes | 1024 cells | added, minutes | sitting, hours | `expected_hours` / `timeout_hours` (was) |
|---|---|---|---|---|---|
| Mac Studio (M4 Max) | 79 (2026-10-05) | 15 | 51, measured: the 15 cells of the 2026-10-06 1024-only sitting, cooldowns included | 2.2 | 2.2 / 4 (1.5 / 4) |
| Galaxy S26, three storage halves | 252 (2026-10-05) | 15 (a 9, b1 3, b2 3) | 224 (a 103, b1 64, b2 57); 288 with one gate retry per half and 10 % for thermal waits | 7.9 (9.0) | 7.9 / 15 (3.5 / 6) |
| Pixel 8a, one session (halves when storage is short) | 337 (2026-10-02) | 15 | 328 (a 130, b1 106, b2 93); 491 if every llama.cpp cell is gate-retried once, as four of five were on 2026-10-02, plus 10 % for thermal waits | 11.1 (13.8) | 11.1 / 18 (4.5 / 7) |
| iPhone 17 Pro, iPhone 18 Pro | about 150 (the set with every cell HOT-retried, recurring-job §3) | 14 (+1 `exclude=`) | 65 with every run nominal; 135 with every cell HOT-retried, as a plugged phone in a warm room does | 4.8 | 4.8 / 8 (2.5 / 5; the 18 Pro entry is new) |

How the numbers were made. Android: one launch = load + prefill + decode,
with the rates at depth from the S26's stored `long-context-2048-gen256`
launches at `context-tokens=2304` (the shorter 1024 prompt shortens prefill
accordingly; two iterations per LiteRT launch) and the load left over from
those launches' elapsed time; the cells with no such launch (LiteRT GPU
Qwen3, LiteRT CPU Qwen3-4B) take the load from their 2026-10-05 short-chat
launch and the short-chat decode × 0.9 (GPU) or × 0.75 (CPU) at depth with a
stated prefill rate; the Pixel 8a scales the S26 rates by its own
short-chat rates per cell. One run = cooldown (120 or 300 s) + launch + 2 s.
A launch comes to 15–193 s on the S26 and 53–792 s on the Pixel 8a (llama.cpp
Qwen3-4B, under the 1,800 s launch timeout). iPhone: the Mac's measured run
times × the iPhone/Mac short-chat decode ratio ÷ 0.6 for throttling, the
runner's cooldowns (100 or 300 s), and 240 s plus a re-run per HOT retry.
Timeout = 1.5 × the estimate, rounded up to the hour. A phone that runs in
storage halves gets `timeout_hours` / 3 per half from the job
(`scripts/dashboard_job.py`, `attempt`), so its total is set by the longest
half: S26 half a ≈ 190 min → 15 h, Pixel 8a half a ≈ 230 min → 18 h.

What it does to the week: a phone sitting that starts at 02:00 now runs into
the morning (S26, about 10:00) or the afternoon (Pixel 8a, about 13:00),
holds the device hold for all of it, and absorbs the 05:30 firing — launchd
starts no second instance — so an iPhone's 05:30 slot moves to a night
without a phone sitting.

## Per-device exclusion (2026-10-07)

`exclude-on=<device key>[,<key>…]:<reason>` keeps a row in the file and takes
it out only on the devices it names by their `ops/dashboard-v1/schedule.json`
key: the Android runner skips it on the phone whose serial that key carries
(`SKIPPED.txt`: `CELL_SKIP <cell> exclude-on=<key> reason=<reason>`) and runs
it everywhere else, and both dashboards (`scripts/render_dashboard.py` and the
team page, through `render_dashboard.exclusion`) show the reason in that
device's cell; `exclude=` stays the every-device form, and `validate_cells.py`
fails a key the schedule does not have, a key of another platform, a
non-Android row (the Mac and iPhone runners do not read the option), an anchor
row and a row that also carries `exclude=`. The Pixel 8a's Qwen3-4B and Gemma 4
E4B rows carry `exclude-on=pixel8a:pixel8a-8gb-4b-class-does-not-fit-swap-thrash`
on every arm and task (short-chat, `long-context-1024-gen256`,
`native-benchmark-1024x256`; owner decision 2026-10-07): in the 2026-10-07 b1r2
sitting the LiteRT-LM CPU Qwen3-4B 1K launch held 3.26 GB in swap beside 3.9 GB
resident, the phone's 3.9 GB zram was full (44 kB free) with 1.6 GB available,
and in the 52 minutes since its boot the phone had read 34.6 GB from flash and
swapped out 17.7 GB; that cell's first launch of the sitting ran into the
1,800 s launch timeout with no record, and llama.cpp Qwen3-4B short-chat read
0.8 tok/s twice where the 2026-09-05 and 09-08 sittings read 6.1–6.8. A rate
taken in that state measures the phone's memory, not the engine. Gemma 4 E4B
(3.66 GB `.litertlm`, 4.98 GB GGUF, both larger than the 4B files) goes with
it; no memory reading of it was taken, and its llama.cpp short-chat on this
phone has read from 0.9 to 5.4 tok/s across four sittings (2026-09-05 to
09-09). The LiteRT-LM GPU Qwen3-4B short-chat of the same sitting held its
September level (6.9 / 7.4 against 6.6–6.7); the row goes as a whole because
the phone's memory state, not one arm, moved. The records stay in raw for
audit; Qwen3 0.6B / 1.7B and Gemma 4 E2B keep running on the Pixel 8a, and
every row keeps running on the Galaxy S26. Source: the lane's round notes
`~/code/standup/drafts/2026-10-06-dashboard-first-tab-attachments/ROUND-m5.md`
(outside this repo) and that sitting's records.

## CPU frequency cap line (2026-10-08)

A cell's runs on Android carry `cpu-capped` when the clock ceiling of a CPU the engine ran on
fell below its hardware maximum during the run (since 2026-10-07,
`methodology/fairness-rules.md` §13 cpu-cap-rule). Since 2026-10-08 (owner decision) the depth
decides the pool: a run whose ceiling fell at most 15 % (summary `cpu_cap_drop_pct`, the line
`render_leaderboard.CPU_CAP_MAX_DROP_PCT`) pools, and the cell's number carries
`◇ cpu-capped ≤15 % (k of N runs)`; a run past it stays out, and a cell left with no other
run reads `— (no valid run: cpu-capped >15 % (k of N runs))`. The detail table's
`cpu capped >15 %` and `cpu capped, counted` columns count both kinds (`—` = caps not read,
records before 2026-10-07). The Android NPU and GPU arms count a capped run at any fall
(the next section's "CPU cap"). Rendered before and after the line from the same records (every
`matrices/dashboard-*.cells` file), four Galaxy S26 cells of the 2026-10-08 sittings moved:
the ONNX Runtime GenAI Qwen3 1.7B short-chat cell and the ExecuTorch Qwen3 1.7B and Gemma 4
E2B short-chat cells now have a number (3, 3 and 2 of 3 runs within the line, 4.9-14.2 %),
and the LiteRT-LM GPU Qwen3 0.6B short-chat anchor pools its run 1 (2.8 %; its three runs
then spread 5.3 %, ⚠). Every 1K cell of those sittings stays without a valid run, as does the
ONNX Runtime GenAI Qwen3 4B short-chat cell (18.6 %). No other cell of any file moved. The
Pixel 8a's capped launches of 2026-10-07 are quarantined files (`*.json.quarantine-cpu-cap`)
and move nothing.

## NPU and Android GPU rows (Galaxy S26, 2026-10-07)

Arms. `llama.cpp-npu` runs llama.cpp on the Hexagon NPU (`--device HTP0`) and
`llama.cpp-gpu` on the Adreno GPU through OpenCL (`--device GPUOpenCL`), both
from the release's official Snapdragon asset; `litert-lm-npu` is LiteRT-LM on
the NPU through the Qualcomm dispatch. A cells row without `backend=` stays
the CPU arm `llama.cpp` (the pinned b8999) and runs exactly as before; the
three new arms are cells of their own (the dashboards key a cell on the
arm), so they displace no existing row.

Build and witness. `llama-b11469-bin-android-arm64-snapdragon.tar.gz` (release
b11469, 2026-10-07, a prerelease; sha256 `669e18399eb9…e310f065`, equal to the
release's published digest) unpacks to `bin/` (7 KB launchers) and `lib/` (the
engine: libllama, the ggml CPU / OpenCL / Hexagon backends, the v73–v81 HTP
libraries). `LLAMA_FLAVOR=snapdragon LLAMA_TAG=b11469
android/scripts/fetch_llama_android.sh` pins it in `android/engine-pins.json` as
`b11469-snapdragon`: the sha256 of `llama-cli`, `llama-bench` and seven libs
(`so_files`: libggml-hexagon, libggml-htp-v81, libggml-opencl, libggml-cpu,
libllama, libllama-cli-impl, libllama-bench-impl). On the phone it lives in
`/data/local/tmp/llmbench/engines/b11469-snapdragon/{bin,lib}`, never in the
flat directory of the pinned CPU build, whose libraries carry the same names
(`android/README.md`, "Side builds"). A cells row names it with
`engine-build=b11469-snapdragon`; the witness matches the tool's sha256 and
then every pinned lib on the phone, and any mismatch stamps `unknown (…)`
with the lib named. Records carry `engineVersion: b11469-snapdragon`,
`engineArtifact` = the tool's sha256 and `conditions.engineBuild`.

Pin. `environment.lock.json` stays at b8999 and the CPU arm keeps it.
`b11469-snapdragon` is a standing side build for the NPU and GPU arms, not a
one-off comparison build (the b10903 witness entry is one of those); moving
the lock's pin is a separate decision.

Settings. The side build runs with the official wrapper's defaults (b11469
`scripts/snapdragon/run.py`: the settings the vendor intends), not the bare
binaries': the chat tool `-ngl 99 -fa on -ub 1024 -t 6`; llama-bench `-t 6`,
with `-ub 1024` on the NPU only and flash attention left at llama-bench's auto;
`GGML_HEXAGON_OPPOLL=1` on every run and `GGML_HEXAGON_DEVICES=HTP0` on the NPU.
Added here: `-ngl 99` on llama-bench too (every layer on the device, which is
what the arm says), an OpenCL program cache per build
(`GGML_OPENCL_KERNEL_CACHE_DIR=<build>/clcache`; left unset, b11469 keeps one
cache for every build under `$TMPDIR/llama.cpp/cl-cache`), and `-lv 4` before
`--device` on the chat tool (below). Records stamp `conditions.threads`,
`flashAttn`, `ubatch`, `hexagonOpPoll`, `nGpuLayers`, `ggmlDevice` and the
whole `engineCommand`. The CPU arm keeps `-t 4` and its command. The first
device smoke of the build (2026-10-07) ran the binaries' bare defaults, one
launch per form; the rows use the wrapper's.

Quantization. The same unsloth Q4_K_M GGUF files as the CPU arm's rows (the
OpenCL and Hexagon backends of b11469 run Q4_K, Q5_K and Q6_K tensors).

Registration lines. A launch counts as the arm's only when the engine says it
ran on the device. The chat tool: its `using device <device>` line, a model
buffer of that device (`HTP0` / `OpenCL model buffer size = …`) and
`offloaded N/N layers` — b11469's llama-cli prints them only at `-lv 4` set
before `--device` (it logs errors only by default, ggml and llama INFO lines
sit at verbosity 4 in its logger, and it loads the backends while it parses
`--device`). llama-bench silences llama's log: its JSON's `devices`,
`n_gpu_layers` and `backends` (with `gpu_info`, `flash_attn`, `n_ubatch`) are
the witness; the build registers both backends on every run, so `backends`
alone says nothing. The lines go to `conditions.backendRegistered`. A launch
without them — none, another device's, fewer than all layers — is flagged
`backend-not-registered`, stays in raw, is a failed launch (`FAILURES.txt`)
and pools into no number (`results/summary/device-runs.csv` column
`backend_registered` false; `render_leaderboard.arm_row`).

Text check. The chat tool's reply (after its echo of the prompt, with the
`-lv 4` log lines taken out) goes through the same text check as the LiteRT-LM
1K rows (text-check-rule, `methodology/fairness-rules.md` §12). The CPU arm is
not text-checked, as before.

Memory. `memoryMedianResidentMB` / `memoryPeakResidentMB` are the host
process's VmRSS / VmHWM; the device's buffers (weights, KV cache and compute
in HTP0 or OpenCL memory) are outside them, and the records' `rssBasis` says
so. On the 2026-10-07 smoke (Qwen3 0.6B short-chat, lane notes outside this
repo) the NPU launch's VmHWM was 217 MiB while llama.cpp's own breakdown put
880 MiB in HTP0 (406 weights, 448 KV, 26 compute).

Cache build (GPU). The first chat launch on a build's empty OpenCL program
cache compiles the programs at load (17.7 s on that smoke; 0.04 s from the
cache on the next launch) and is labelled `firstEver` like LiteRT-LM's GPU
cache builds: one marker per (model, arm, build), and a cache directory
without a program relabels the next launch whatever the markers say.
llama-bench compiles at load as well but times after its own warmup run, so
its launches are not labelled. The NPU keeps no compile cache.

CPU cap. The 15 % line of the cpu-cap-rule does not apply to these arms
(owner decision 2026-10-08, `methodology/fairness-rules.md` §13, "The
accelerator arms"): `render_leaderboard.CPU_CAP_EXEMPT_ARMS` = `llama.cpp-npu`,
`llama.cpp-gpu`, `litert-lm-npu`, `litert-lm-gpu`, `executorch-vulkan`,
`executorch-qnn`, the arms whose engine places the model on the NPU or the GPU.
The runner reads and flags the caps as on every arm; a flagged run pools,
counted, whatever the fall, and the number carries `◇ cpu-capped, counted
(accelerator arm), max drop D % (k of N runs)`, D the largest
`cpu_cap_drop_pct` among those runs. On the S26 an NPU load took both
clusters' ceilings down 9-16 s into a launch (`devices/galaxy-s26.md`): with
the line alone, the Qwen3 1.7B 1K cells and the protocol cells of the
2026-10-08 sitting had no valid run. The session anchor (the llama.cpp CPU
arm) keeps the line.

LiteRT-LM on the NPU. One model has a bundle: this repo's own export of Qwen3
0.6B for SM8850, run on this repo's own build of the runtime with the hardware
KV-cache update off — three disclosures every record of the row carries
(subsection "LiteRT-LM on the NPU" below). The other four models have no
SM8850 bundle, published or exported:
`exclude=no-sm8850-npu-bundle-published-or-exported`.

Cells, all Galaxy S26 only (the Pixel 8a has neither a Hexagon NPU nor an
Adreno GPU), each starting with the weekly session anchor (the llama.cpp CPU
arm on Qwen3 0.6B): `matrices/dashboard-npu-v1-android-s26.cells` (short-chat
and `long-context-1024-gen256` at `context-tokens=2048`, five models × npu /
gpu, the weekly files' cooldowns), `matrices/dashboard-npu-protocol1024-v1-android-s26.cells`
(`native-benchmark-1024x256`, five models × npu / gpu) and
`matrices/dashboard-npu-litert-v1-android-s26.cells` (the LiteRT-LM NPU row:
short-chat on Qwen3 0.6B; its 1K row and the other models' rows excluded). The
weekly job measures the short-chat rows only, since 2026-10-09 ("NPU and Android
GPU rows in the weekly set" below); the 1K rows, the protocol file and the
LiteRT-LM NPU row stay by-hand.

### LiteRT-LM on the NPU (arm `litert-lm-npu`, runner wired 2026-10-08)

Bundle. `model_qualcomm_SM8850.litertlm`, 783,864,161 bytes, sha256
`f8909326639011c6123126c06c4f7d205857b1915c8b49de6844522fe5d211f2`,
side-loaded by local path: litert-torch's `npu_export` pipeline of 2026-08-21
on `Qwen/Qwen3-0.6B` — stages 1–3 on the Mac (export with int8 weights,
`dynamic_wi8_afp32`; calibration on 3 prompts × 8 decode steps; static-range
quantization with 16-bit activations), stage 4 compiled ahead of time for
SM8850 in a Linux container (that compile's own log is not kept). Prefill signature 128 and a KV cache
of 1,024 tokens, both fixed at export. Its metadata section is that day's
static-range build's byte for byte; the same day's re-calibrated build (10
prompts × 32 steps) is another file and not this row's. The quantizer's log
also says "Forcing a16w4 per-tensor for Hadamard rotation FC ops"; whether
this graph has such ops is unverified. No SM8850 bundle of these models is
published. `model.quantization` names the export by its sha256
(`android/bench/run_cell.py` `OWN_NPU_BUNDLES`: `npu_export` names every
output `model_qualcomm_<SoC>.litertlm`, whatever the model and recipe, so the
name says nothing); `conditions.contextTokens` is `aot-fixed-1024` (no
`--max_num_tokens`: the bundle's cache is fixed). A file the table does not
know keeps quantization `unrecorded` and `aot-fixed (cache length unrecorded)`.

Runtime. A source build of `litert_lm_advanced_main` from a shallow clone of
LiteRT-LM `main` on 2026-08-21 JST (main at or before `b12c62c7`: it carries
`e3feda9e`, not `90f42140`), 39,908,888 bytes, md5
`ca629242e622c3547a64ac6629f104cb`, with the Qualcomm dispatch library from
the same build (its LiteRT revision is not recorded), the QNN libraries of
QAIRT 2.47.0.260601 and the V81 skel beside it. The official v0.16.1 Android
binary could not be paired with a dispatch library (the LiteRT v2.2.0 release
`.so` fails its runtime-version check; 2026-09-08). On the phone the build sits
flat in `/data/local/tmp/llmbench/engines/main-20260821-selfbuilt/` (the skel
in `dsp/`; `android/README.md`, "Side builds"), and cells name it
`engine-build=main-20260821-selfbuilt`. The witness reads the tool and six
libs (`libLiteRtDispatch_Qualcomm.so`, `libGemmaModelConstraintProvider.so`,
`libQnnHtp.so`, `libQnnSystem.so`, `libQnnHtpV81Stub.so`,
`dsp/libQnnHtpV81Skel.so`) against `android/engine-pins.json` `litert-lm` →
`main-20260821-selfbuilt`. That entry is written from the phone's files on the
first device run (the binary has no host copy); until then the records stamp
`unknown (…)`, and a sitting stops such a cell before it launches. Records
carry `engineVersion` = that key, `engineArtifact` = the tool's sha256 and
`conditions.engineBuild`.

Command (`conditions.engineCommand`, whole):
`LD_LIBRARY_PATH=<build> ADSP_LIBRARY_PATH="<build>/dsp;/system/lib/rfsa/adsp;/vendor/lib/rfsa/adsp;/dsp"
<build>/litert_lm_advanced_main --backend=npu --model_path=<bundle>
--input_prompt_file=<prompt> --max_output_tokens=<budget> --async=false
--benchmark --benchmark_prefill_tokens=0 --benchmark_decode_tokens=0
--use_hw_cache_update_for_npu=false --litert_dispatch_lib_dir=<build>`.
`--benchmark` with no synthetic token counts keeps the real prompt and prints
BenchmarkInfo; without it this binary prints no rate (LiteRT-LM `main`
`runtime/engine/litert_lm_lib.cc`: the reply is printed whenever
`benchmark_prefill_tokens` is 0, BenchmarkInfo only under `--benchmark`). The
hardware KV-cache update is off: with it on, this bundle's output is broken on
the S26 (google-ai-edge/litert-torch#1290). `conditions.hwCacheUpdateForNpu`
is the engine's own echo of that setting. The other NPU switches keep their
defaults.

Registration lines. `conditions.backendRegistered` carries the engine's own
lines: `Choose backend: npu`; the settings echo (`executor_settings: backend:
NPU`, `use_hw_cache_update_for_npu`, `litert_dispatch_lib_dir`); the NPU
accelerator's registration (`RegisterAccelerator: … name=NpuAccelerator`,
`NPU accelerator registered.`); the dispatch library loaded; QNN's
`BackendType`; each subgraph the dispatch delegate took (`Replacing … with
delegate (DispatchDelegate) …`); the QNN contexts created; addresses read as
`<addr>`. A launch counts as the arm's when it chose the npu backend,
registered the NPU and the dispatch delegate took at least one subgraph — a
bundle with nothing compiled for this NPU registers it and runs on XNNPACK.
Anything less is flagged `backend-not-registered`: kept in raw, a failed
launch (`FAILURES.txt`), pooled into no number. LiteRT logs "NPU accelerator
could not be loaded and registered" for each environment after the first, on
healthy runs too, so that warning is not read.

Text check. The reply — after the engine's "Running single-turn conversation"
line, up to BenchmarkInfo, the engine's log lines taken out, from `[thought]`
on when the reply has a thinking channel — goes through the same text check as
the 1K rows (text-check-rule). The LiteRT-LM CPU and GPU short-chat rows stay
unchecked, as before.

Memory and cache build. Memory is the host process's VmRSS / VmHWM; the NPU's
buffers are outside them, and `rssBasis` says so. The first launch per device
and bundle is labelled `firstEver` by LiteRT-LM's marker, as on the CPU and
GPU; whether an AOT bundle builds anything on its first launch is for the
first device run to show.

Tasks. A prompt task on the bundle's own cache only: the runner and
`scripts/validate_cells.py` refuse `context-tokens=`, `native-benchmark-*` and
`endurance-*` on this arm. Short-chat on Qwen3 0.6B is the row; its 1K text
task is `exclude=aot-cache-length-1024` (the prompt alone is 1,339 tokens on
LiteRT-LM's Qwen3 0.6B, against a 1,024-token cache).

## ONNX Runtime GenAI arm (v1, 2026-10-07)

`matrices/dashboard-ortgenai-v1.cells`: Qwen3 0.6B / 1.7B / 4B on the onnx-community GenAI folders
(`file=` the folder, `revision=` each repo's commit), short-chat and the 1K text task at
`context-tokens=2048`; arms `onnxruntime-genai-cpu` (Mac, Android) and `onnxruntime-genai-webgpu`
(Mac). Gemma 4 E2B / E4B rows are `exclude=` with their reason, the Pixel 8a's Qwen3-4B rows carry
the 4B-class `exclude-on=`, the iPhone rows are in the weekly set since 2026-10-09 (the pinned
build carries the adapter), and there is no anchor row (the weekly file is an owner decision). The regime is the platform's: on the
Mac one engine process per cell (run 1 cold, runs 2..N warm, the warm median headlines, as
`yardstick run --runs N`), on Android a fresh process per run (cold). Drivers, pins, recipe
labels, regime, timing, memory and telemetry: [docs/ortgenai-arm-v1.md](ortgenai-arm-v1.md).

## ONNX Runtime GenAI arm in the weekly set (2026-10-09)

Since 2026-10-09 (owner GO) the Mac block of `dashboard-text-v1.cells` ends with the 12 Qwen3
rows of `matrices/dashboard-ortgenai-v1.cells` (0.6B / 1.7B / 4B, short-chat and the 1K text
task at `context-tokens=2048`, the CPU EP and the WebGPU plugin EP, the engine default; one
engine process per cell, run 1 cold, runs 2-4 warm). The Galaxy S26 measures only the two
Qwen3 short-chat cells (0.6B, 1.7B), from `matrices/dashboard-ortgenai-v1-android-ort.cells`
through `devices.s26.extra_cells` in `ops/dashboard-v1/schedule.json` (the file starts with the session anchor row, the llama.cpp Qwen3 0.6B short-chat cell, as every Android half does: the job re-judges each payload session by the anchor records inside it): its 1K cells and the 4B
cell ran under a CPU clock cap deeper than the 15 % line in every launch of the 2026-10-08
sitting (cpu-cap-rule; the prefill cost is upstream, microsoft/onnxruntime#33196), so they stay
by-hand until a release carries the fix. An `extra_cells` file runs after the set as its own
tagged session (`-ort`), whole-set or halves alike, with its own `timeout_hours`; the Pixel 8a
has no such entry (never measured there). The Mac sitting grows by about 35 minutes (the
2026-10-08 sitting: 34 minutes for the 12 cells and their anchors; `expected_hours` 3.2 → 3.8),
the S26 sitting by about 15 minutes (`expected_hours` 7.9 → 8.2).

The iPhone rows are in the weekly set since 2026-10-09 too: the iPhone section of
`dashboard-text-v1.cells` ends with the six Qwen3 rows of the same file (CPU EP, the release
XCFramework 0.17.0 through the app's adapter, the engine default; one app launch per cell, run 1
cold, runs 2-4 warm), and `dashboard-longctx1024-v1.cells` carries their three 1K twins. The night
job installs nothing, so they waited for the iPhone 18 Pro's pinned app build to carry the adapter:
that build was rebuilt from main on 2026-10-09 (its provenance: `docs/dashboard-recurring-job-v1.md`
§3). The iPhone 18 Pro sitting grows by about one hour (the 2026-10-08 by-hand sitting: three
holds, 59.5 minutes, for the six cells with each model's first fetch, four gate retakes and one
pair of anchors; `expected_hours` 4.8 → 5.8, `timeout_hours` 8 → 9). Both iPhones read the same file: an app built before the adapter
(2026-10-08) ends these launches at "unknown runtime" with no record — a SHORT cell, not retried,
after its cooldown.

## NPU and Android GPU rows in the weekly set (2026-10-09)

Since 2026-10-09 (owner GO) the Galaxy S26's weekly sitting ends with the short-chat rows of
`matrices/dashboard-npu-v1-android-s26.cells`: `matrices/dashboard-npu-v1-android-s26-short.cells`
holds the session anchor and those ten rows (five models × `llama.cpp-npu` / `llama.cpp-gpu`, the
side build `b11469-snapdragon`), byte-identical to the plan file, which stays the file the rows
come from and the team page reads. It runs through `devices.s26.extra_cells` in
`ops/dashboard-v1/schedule.json` as its own session (`-npu`) after the ONNX Runtime one, and only
while the side build is on the phone (`/data/local/tmp/llmbench/engines/b11469-snapdragon`,
`android/README.md` "Side builds"); without it the job skips the session and runs the rest of the
sitting (`docs/dashboard-recurring-job-v1.md` §3, "Per-device extra files").

Why short-chat only. On the 2026-10-08 sitting a short-chat launch of these arms raised the
battery −0.1 to +1.6 °C, a 1K launch of Qwen3 4B or Gemma 4 E2B +0.4 to +4.1 °C, and a llama-bench
1024/256 launch of Qwen3 1.7B +4.7 / +6.4 °C (NPU / GPU); at 120 s cooldowns one llama-bench
launch of Qwen3 1.7B took the battery from 34.0 to 40.4 °C, and four 1K launches of Qwen3 4B from
32.5 to 38.9 °C. The job has no battery-temperature stop (the runner waits up to 600 s for thermal
status 0 before a launch, then runs), so those cells stay by-hand sittings with their own cooling.

Time, from that sitting's records (the job runs the default campaign mode: the anchor's three
runs first, 120 s apart, then three rounds over the ten cells, each launch after its row's
cooldown — 120 s for Qwen3 0.6B / 1.7B, 300 s for Gemma 4 E2B, Qwen3 4B, Gemma 4 E4B). Cooldowns:
2 × 120 + 3 × (4 × 120 + 6 × 300) = 7,080 s. Launches: the wall time from one record to the next
less the cooldown (the launch and the runner's work around it), median per cell, NPU / GPU —
Qwen3 0.6B 6 / 9 s, 1.7B 9 / 14, Gemma 4 E2B 14 / 18, Qwen3 4B 17 / 22, Gemma 4 E4B 21 / 26; the
anchor 4 — 156 s a round, 480 s in all. About 126 minutes, 2.1 h (2.2 with one gate retry: 180 s,
then the cell's three runs 120 s apart); no model push (the storage halves have just pushed the
five files). `expected_hours` 8.2 → 10.3 for the S26, the session's own `timeout_hours` 4
(1.5 × 2.1, rounded up); a sitting that starts at 02:00 ends about 12:20.

Storage: `min_free_gb` 7 is the room to push back the GGUF files a rotation between the halves can
take away (Qwen3 1.7B, Gemma 4 E2B, Qwen3 4B: 6.6 GB as the job counts space, KiB / 10⁶, from the
phone's `models/` listing of 2026-10-08), not the session's 11.8 GB footprint (the five files): a
floor above what the halves leave free (13.9 GB after them on 2026-10-05) would rotate their
LiteRT bundles and caches out every week (job doc §3).

Expected each week, from the job's code path (not yet seen in a weekly session): the GPU's first
Qwen3 4B and Gemma 4 E4B launch is labelled `firstEver` and pools into no number (n 2 of 3). The
rotation before half a deletes halves b1 / b2's copies with their markers, the halves push those
files again, and a re-push drops the file's markers too (`run_cell.push_verified`); the GPU marker
is per model, while the OpenCL program cache it stands for is per build (`engines/<tag>/clcache`,
which the rotation leaves alone). A marker per build is the open fix.

## ExecuTorch arm in the weekly set, Mac leg (2026-10-08)

Since 2026-10-08 (owner GO) the Mac blocks of `dashboard-text-v1.cells` and
`dashboard-longctx1024-v1.cells` end with the ExecuTorch rows of
`matrices/dashboard-executorch-v1-mac.cells`: our own exports of the dashboard models with
ExecuTorch v1.5.1's own exporters (not published artifacts; `docs/executorch-arm-v1.md`), the
arm `executorch-xnnpack` (8da4w, group 128, embedding int8) and `executorch-mlx` (the MLX
delegate, Qwen 3 at 4w group 128 — another recipe, stated per row), short-chat and the 1K
text task at `context-tokens=2048`, the Mac runner's regime (run 1 cold, runs 2-4 warm through
`llama_main --warmup`). 12 rows run; the 8 Gemma 4 rows are `exclude=` with their reasons
(the XNNPACK runner `gemma4_e2e_runner` has no warm regime; the exporter has no MLX path).
The Mac sitting grows by about one hour (`expected_hours` 2.2 → 3.2, `timeout_hours` 4 → 5,
`ops/dashboard-v1/schedule.json`; derivation in the lane's round record, two measured sittings
of 36 and 22 minutes). The Android and iPhone ExecuTorch rows are not in the weekly set: the
Android rows wait on the Galaxy S26's CPU cap line and on keeping the runner directory on the
phones; the iPhone rows need the ExecuTorch build of the app, which replaces the Core AI build
under the same bundle id, so they are by-hand sittings only.

## Protocol cells: the headline regime (2026-10-08)

A `native-benchmark-<P>x<D>` cell is one launch of an engine's own benchmark entry: its first
call cold, the calls after it warm (LiteRT-LM `benchmark()` calls 2..N of a `--runs N` launch;
the Core AI stock arm's trials 1..N, the ones `llm-benchmark` averages; llama-bench's in-process
repeats, all recorded warm). Since 2026-10-08 such a cell headlines the agreed protocol's regime
(`methodology/agreed-protocol-gemma4.md`: warm for the side-by-side, cold reported separately as
first use) on every platform and for every arm: the warm median wherever the session has warm
runs, with the session's cold first-call median beside it (`cold_tps`), and the cold median only
where the session has none — the LiteRT-LM protocol sittings before 2026-10-08 made one call per
launch. The text tasks keep their platform's regime (warm on the Apple lanes, cold on Android).
One rule for this repo's dashboard table and the team page: `scripts/render_dashboard.py`
`headline_regime` (its detail table gives the cold value; a grid cell that reads another regime
than its device's header says `(cold)` / `(warm)`), followed by the team page's `make_cell`.
Before this, the bench table read protocol cells by the platform's regime (an Apple cell with
cold runs only showed no number, an Android llama-bench cell likewise) and the team page by
"cold where the cold pool has runs".

## Artificial Analysis set on the iPhone 17 Pro (2026-10-15)

`matrices/dashboard-aa-v1-ios.cells` measures the 23 models of Artificial Analysis's mobile benchmark
that have a `.litertlm` in litert-community, on the iPhone 17 Pro: the phone Artificial Analysis
measures on, so the rows sit on the same hardware as its published llama.cpp numbers (its own
numbers, never pooled with these). Engine = LiteRT-LM v0.18.0 on the Metal GPU, in a separate build
of the app (bundle id `com.daisukemajima.llmbench`) beside the phone's other bench builds; regime =
the protocol row (`native-benchmark-1024x256`, prefill 1024, decode 256, context 2048, four
`benchmark()` calls in one launch, call 1 cold), each preceded by a two-run `short-chat` row of the
same model: the task record the native importer needs (`--like`) and the reply text of that bundle
on this engine. One file per repo, named by `ModelCatalog.liteRTLM` (the int4 file where the repo
has one); the two gated repos (Gemma 3 270M, Llama 3.2 3B) are side-loaded, since the app holds no
Hub token. The set runs as nine slot files (`dashboard-aa-v1-ios-i1` … `-i9`, each estimated under 45 minutes,
Gemma 4 E2B and E4B first) through `scripts/dashboard_job.py iphone17pro --cells <slot>`, with the
models fetched beforehand; Gemma 4 12B (a 6.88 GB file) is run, and a load that does not fit the
app's memory stays as that cell's record.

## llama.cpp on b11721 (2026-10-19)

The llama.cpp pin moved from b8999 to b11721 on every platform (owner decision 2026-10-19: the
comparison arms are measured on their current release too; `environment.lock.json` `arms.llama.cpp`,
`android/engine-pins.json`). The re-measure runs from three cells files, each holding its platform's
session anchor row and the weekly set's ten llama.cpp rows (short-chat and the 1K text task of the five
models), byte-identical to their sources: `matrices/dashboard-llama-b11721-mac.cells` and
`-ios.cells` (`matrices/dashboard-text-v1.cells`), `-android.cells` (the a / b1 / b2 halves; its first row
is the Android session anchor, a llama.cpp row, and the Pixel 8a skips the 4B-class rows by their
exclude-on, as in the weekly set). Each runs as one job-route sitting per device
(`docs/dashboard-recurring-job-v1.md` section 2). The Apple builds stamp the xcframework's tag sidecar;
on Android, where b11721's CPU tools are the same 7 KB launchers as b10903's, the witness also matches
the libraries the pin lists (`so_files`) in the flat directory, and a phone holding another build's
libraries stamps `unknown`.

## Qwen3 0.6B LiteRT-LM file (2026-10-19)

Since 2026-10-19 the page's Qwen3 0.6B LiteRT-LM rows (short-chat, `long-context-1024-gen256` and
`native-benchmark-1024x256`, CPU and GPU, every platform) run `Qwen3-0.6B_dynamic_wi4b32_afp32.litertlm`
from litert-community/Qwen3-0.6B: dynamic INT4 weights in blocks of 32, FP32 activations, the GPU-graph
build (Hub blob sha256 `03e7da1e…2856`, 344,671,744 B, hashed from the bytes in the Mac's Hub cache).
Until then they ran `qwen3_0_6b_mixed_int4.litertlm` (sha256 `7900eb4e…22c1`). That file's embedded chat
template predates LiteRT-LM 0.18, and on v0.18.0 the engine drops the user turn: its own log reads
`Prefill Turn 1: Processed 9 tokens` whatever the prompt (the 2026-10-15 Pixel 8a `0180-p1` / `p2b`
dirs; all seven S26 anchors phases since, 3 of 3 launches each, the last
`2026-10-19-dashboard-v1-s26-0180-protocol8-anchor-android`), the same mechanism as
google-ai-edge/LiteRT-LM#3688. The 2026-10-15 exclusion of that file's Android
chat rows (`exclude-on=pixel8a,s26:hub-bundle-chat-template-predates-litert-lm-018-prompt-dropped-issue-3688`,
0ee7a28f) is resolved by the new file: the moved rows no longer carry it.

Two candidates were probed on the Galaxy S26, GPU short-chat, one launch each (2026-10-19 05:10 and
05:13 JST, `results/raw/2026-10-19-probe-q06-s26-android-android/`): a check that the prompt arrives,
not a session.

| File | `Prefill Turn 1` | decode tok/s | prefill tok/s (that line) | peak resident MB |
|---|---|---|---|---|
| `Qwen3-0.6B_dynamic_wi4b32_afp32.litertlm` | 19 tokens in 98.4 ms | 76.5 | 193 | 861 |
| `Qwen3-0.6B.litertlm` (dynamic INT8) | 19 tokens in 181.8 ms | 25.7 | 104 | 753 |

The rows took the wi4b32 file: it keeps them at INT4 and is the family of the Qwen3 1.7B GPU row's
`Qwen3-1.7B_dynamic_wi4b32_afp32.litertlm`.

- Android (Galaxy S26, Pixel 8a, the DDP lab units): only `file=` changed. The model id stays
  `litert-community/Qwen3-0.6B`, since the runner fetches `hf_hub_download(model_id, file)` and the id
  is the Hub repo; the quantization label is `android/bench/run_cell.py` `ANDROID_QUANT_LABELS`'s "INT4
  (dynamic, block-32 weights, FP32 act; GPU-graph build 2026-08-04)". Rows in `dashboard-text-v1.cells`,
  `dashboard-text-v1-android-a.cells`, `dashboard-longctx1024-v1-android-a.cells`,
  `dashboard-protocol1024-v1-android.cells` and `dashboard-ddp-v1-android-s26.cells`.
- The Android LiteRT-LM session anchor moved with them (`anchors.cells` and the `anchor=1` rows of the
  1K and protocol files). A page cell and its series select rows by device, arm, model id, task and
  context, not by file (`scripts/render_dashboard.py` `build`, the team page's `build.py`), so an anchor
  on the old file would put that file's number into the GPU short-chat page cell whenever an anchors
  phase is newer than that cell's payload, and the series would alternate between two files. The
  LiteRT-LM anchor does not gate admission: `dashboard_job.anchor_cells` sorts the non-litert arm first
  and `admit()` judges that one only. A regression pair across 2026-10-19 that is normalized through the
  Android LiteRT-LM anchor (a llama.cpp bump on Android) compares two files.
- DDP: the four rows now run on m1q-36 too, so the weekly DDP slot grows from 16 jobs in 2 sessions to
  20 jobs in 3 (at most 8 jobs a session). The two GPU rows give page numbers; the two CPU rows give
  none, as the lab units hold their CPU clock ceilings below the cpu-cap-rule line (the file's header).
- Mac and iPhone: the rows name a catalog id, not a file. The catalog already had
  `litert-community/Qwen3-0.6B/dynamic_wi4b32_afp32` for this file (`ModelCatalog.swift`; label "INT4
  (dynamic, block-32 weights, FP32 act; GPU-graph build 2026-08-04)", the Android label's string; the Mac
  long-context ladder's id since 2026-09-18), and the 12 page rows moved to it:
  `dashboard-text-v1.cells` 4, `dashboard-longctx1024-v1.cells` 2, `dashboard-protocol1024-v1.cells` 2,
  `dashboard-coreai-v1-mac.cells` 2, `dashboard-coreai-v1-ios.cells` 2. The catalog is unchanged, so
  neither the app nor the yardstick needs a rebuild. The Mac and iPhone LiteRT-LM anchors keep
  `litert-community/Qwen3-0.6B` (the mixed INT4 file), a key apart from the page rows. A page cell under
  the new id stays empty until that id's first session: the old id's sessions belong to another key.
  Both ids share hfRepoId `litert-community/Qwen3-0.6B`, so the app looks for either file in
  `Documents/models/litert-lm/litert-community__Qwen3-0.6B/` and downloads nothing while that directory
  holds a file (`HFDownloader.snapshot`): on a phone that ran the old file, put
  `Qwen3-0.6B_dynamic_wi4b32_afp32.litertlm` there before the first sitting.
- Text: the Android runner checks the decoded text of the 1K rows, not of short-chat (`run_cell.py`,
  text-check-rule). This file's text failed on the S26 GPU at the 2K prefill
  (`exclude=s26-gpu-garbage-text-at-2k-prefill` in `dashboard-longctx-v1-android-s26.cells`, v0.16.0),
  and its 1.7B sibling at the 1K prefill (open question 8); a 1K GPU row that fails the same way shows as
  text-fail, not as a rate. The probe read the prompt-token count only.
- Unchanged: the Mac and iPhone LiteRT-LM anchors (above), the dated one-off files (`dashboard-0180-*`,
  `catalog-*`), the 2K ladders (their measured 0.6B rows already ran the wi4b32 file; their mixed INT4
  rows are `exclude=` rows for its 2,048-entry KV), `release-regression-litert.cells` (its baseline
  campaigns ran the old file), `android-first-session.cells`, `apple-warm-matrix.cells`,
  `endurance-mac.cells` and the examples.

The re-measurement takes the release-triggered pass's route (`docs/dashboard-recurring-job-v1.md`
section 2): `matrices/dashboard-q06-dynamic-android.cells` (Galaxy S26, Pixel 8a) and
`matrices/dashboard-q06-dynamic-ios.cells` (iPhone), each the session anchor row and the moved rows
byte for byte; the Mac's next sitting of these files measures the new id. If litert-community publishes
a re-export of the mixed INT4 file, one v0.18.0 launch's `Prefill Turn 1` line shows whether the user
turn arrives; moving back is the same edit in reverse and a re-measurement.

### iOS from 2026-10-19 12:2x: the INT8 bundle on the GPU, the INT4 bundle on the CPU

On the iPhone 18 Pro the dynamic INT4 bundle fails at engine creation on the Metal GPU under LiteRT-LM v0.18.0
(`Failed to create engine … Failed to modify graph with delegate`, 4 of 4 launches in three tasks,
`results/raw/2026-10-19-dashboard-v1-iphone18pro-q06-dynamic-ios/`; the same bytes load on the Mac's Metal GPU and on
Android's OpenCL GPU the same day; hazard `ios-metal-dynamic-int4-engine-fails`, issue draft pending the owner's GO). With
the mixed-INT4 bundle dropping the user turn on 0.18.0 (#3688), no INT4 Qwen3 0.6B bundle runs on the iPhone's GPU. Smokes
of 12:22 (short-chat, 19 prompt tokens, one launch each): the repo's dynamic INT8 bundle `Qwen3-0.6B.litertlm`
(`dynamic_int8`, LlmMetadata for 0.18.0 since 2026-10-12) on the GPU 46.5 tok/s decode, 158 prefill, 1,515 MB peak; the
dynamic INT4 bundle on the CPU 88.3 tok/s decode, 64.5 prefill, 505 MB peak.

Rows from 2026-10-19 12:2x: every iOS LiteRT-LM row of the Qwen3 0.6B (the anchors, the weekly set, the 1K ladder, the
protocol cell, the Core AI file's reference rows) runs `dynamic_int8` on the GPU (the arm the page's LiteRT-LM column
shows; the recipe label says INT8), and the weekly set gains a `backend=cpu` pair on the dynamic INT4 bundle (arm
`litert-lm-cpu`, as Android shows its CPU arm) so the 4-bit class stays measurable on the phone. Neither row claims the
other's class: the quantization travels in the row (quant-per-arm-rule). The Mac and Android rows keep the INT4 bundle.
First values: `matrices/dashboard-q06-int8-ios.cells`, one sitting on 2026-10-19. Revert = the ios rows back to
`dynamic_wi4b32_afp32`, the cpu pair out. Owner's items: whether the iPhone page should carry the INT8 row at all while
the other arms are 4-bit, and the issue to the LiteRT-LM team.

## Qwen3 0.6B candidate (2026-10-19)

A local candidate for the iPhone Metal failure above, measured beside the current file in one sitting per device (owner
decision 2026-10-19 via code-2d). Nothing is uploaded and no page row moves: the candidate's rows live in their own cells
files, under their own model id.

- The candidate = the dynamic INT4 file's 2026-08-05 revision (litert-community/Qwen3-0.6B at 8414150f, hvt4's export,
  sha256 `e3e29010…76cf`, 344,437,808 B; the bundle's creation timestamp is 2026-08-04T21:11Z) with the current file's
  LlmMetadata (Hub a3c5d805: the same fields but for `jinja_prompt_template`, which is LiteRT-LM's content-parts Qwen3
  template), put in by a metadata-only re-pack with litert-lm-builder 0.18.0
  (`~/code/litertlm-convert/team_repack_20261012/tools/repack_metadata.py`, PASS): ExecutorMetadata, the HF tokenizer and
  the TFLite graph are byte-identical to the 2026-08-05 file, the LlmMetadata section is byte-identical to the current
  file's, the header's format version is the 0.18.0 builder's 1.7.0 (both Hub files carry 1.6.0). File
  `Qwen3-0.6B_dynamic_wi4b32_afp32.r0805meta018.litertlm`, sha256 `e6bf25c0cf7e1a09d19fc6ad716072bb5b8ac96a0eca75075a69f7ce8c1a8f91`,
  344,437,808 B, kept outside every repo in `~/.cache/edge-llm-bench/litert-candidates/out/`.
- The graphs: both have the signatures prefill_128 / prefill_1024 / decode, a 32,771-entry KV cache in 28 layers, a bool
  mask and INT4 block-32 FC weights, so the current LlmMetadata (max_num_tokens 4096) fits the old graph unchanged. The
  2026-08-05 graph has no `odml.swiglu` composite (the current one has 28 per signature) and its prefill signatures output
  no logits; both carry `odml.rope`, `odml.rms_norm`, `odml.runtime_bmm` and `odml.cache_update`.
- Apple: catalog id `litert-community/Qwen3-0.6B/dynamic_wi4b32_afp32_r0805meta018` (label "INT4 (dynamic, block-32
  weights, FP32 act; 2026-08-05 graph, 0.18.0 metadata, local candidate)"), side-loaded into
  `Documents/models/litert-lm/litert-local__Qwen3-0.6B-r0805meta018/`. Its hfRepoId is a litert-local one, not the Hub
  repo: `HFDownloader.snapshot` returns `Documents/models/litert-lm/litert-community__Qwen3-0.6B/` for every entry of the
  repo as soon as that directory holds a file, and `MediaPipeRuntime.locateModelFile` falls back to another `.litertlm`
  there when an entry's primaryFile is missing. On the Mac that directory is empty and the repo's entries read the hub
  cache (their records' `modelRevision`), so a candidate copied into it would move the Mac's 0.6B rows, the anchor
  included, onto the candidate, and the candidate's records would carry the hub cache's revision. Records of a
  side-loaded bundle carry no revision; the catalog comment and this section hold its sha256.
- Android: the candidate's rows name the Apple catalog's id as their model id and give `file=` as the host path (`local=1`);
  `android/bench/run_cell.py` pushes a host path as it is (sha256-verified, the record's `model.sha256`) and
  `ANDROID_QUANT_LABELS` holds the label above for the file's name. Its own model id keeps the candidate apart from the
  current file (`litert-community/Qwen3-0.6B` + `file=`): the leaderboard groups by runtime and model id, and the job's
  `cells_with_records` by arm, model id and task.
- Cells: `matrices/q06-candidate-ios.cells`, `matrices/q06-candidate-mac.cells`, `matrices/q06-candidate-android-gpu.cells`
  and `matrices/q06-candidate-android-cpu.cells`: each the platform's session anchor row of `dashboard-text-v1.cells`,
  then the current file and the candidate in pairs with the same options (GPU short-chat, 1K, native 1024x256; CPU
  short-chat, 1K), the current file's rows byte-identical to their page source. Android is split by backend so each
  sitting stays within an hour (the morning's six-row file of the same model took 57 min on the S26 and 63 min on the
  Pixel 8a); each pair sits in one sitting. The Mac sitting runs the yardstick built with the entry
  (`DD_MAC=.build/dd-mac-q06cand`).
- Reading (owner's rule): the candidate replaces the Hub file only if it is not slower anywhere (same-sitting warm decode
  and prefill within −3 % of the current file on every device and backend) and both pass the text check; then a Hub PR
  goes to a GO request. If it is slower somewhere it does not replace the file: an iOS-only file or a card note instead.
  On the iPhone GPU the first question is whether the engine builds at all. Results: the lane's round record
  (`results/raw/2026-10-18-bench-autopilot-dev/ROUND18.md`).

## llama.cpp Gemma 4 rows before 2026-10-19 ran without the chat template (Mac and iPhone)

Every llama.cpp Gemma 4 row the Mac and the iPhones measured before 2026-10-19 (E2B and E4B; short-chat,
the 1K task and the Mac 2K ladder) is a bare-prompt run: the GGUFs' template is outside llama.cpp's
built-in set, and the adapter then sent the prompt without it (methodology/fairness-rules.md §1). Their
prompt-token counts show it: 12 for short-chat and 1,098 for `long-context-1024-gen256` (1,629 on the
2K ladder), where the LiteRT-LM Gemma 4 bundles read 20 and 1,106. On the Mac the text screen failed
only the E4B 1K replies, which continue the prompt's list as `1. [Item 1] 2. [Item 2] …` (text-fail on
the page); the E2B and short-chat replies passed it as continuations that happen to read like answers,
and are bare runs all the same. The iPhone rows carry no screen verdict: the 18 Pro's E4B 1K replies are
the same skeleton (`results/raw/2026-10-06-dashboard-longctx1024-v1-iphone18pro-c4-ios/`), and its page
number stands until the re-measure. Since 2026-10-19 the adapter renders the GGUF's own template
(Gemma 4 with `enable_thinking: false`, as LiteRT-LM and MLX answer) and every llama.cpp record carries
`conditions.chatTemplate` and `conditions.thinking`; the Qwen3 rows' prompt does not change (the
built-in chatml and the rendered template are the same text). The rebuilt yardstick (`.build/dd-mac-tmpl`)
and iPhone app re-measure the Gemma 4 rows with the rest of `matrices/dashboard-llama-b11721-mac.cells`
and `-ios.cells`, one job-route sitting per device; the page shows each cell's latest admitted session, so
that sitting replaces the bare rows. The Mac 2K ladder's llama.cpp Gemma 4 rows (`dashboard-longctx-v1.cells`)
are not in those files.

## Android llama.cpp Gemma 4 thinking (2026-10-19)

Every Android llama.cpp Gemma 4 prompt-task row before 2026-10-19 ran with thinking on, where every
other arm runs Gemma 4 off (methodology/fairness-rules.md §1, `budget-mode-rule`). `llama-cli … -st`
hands a template that can think `enable_thinking = true` unless told otherwise (b11721 and b11469 help:
`--reasoning` defaults to `auto`, "detect from template"), and the Gemma 4 GGUF template's own default
(off) never applied. Every stored Gemma 4 short-chat and `long-context-1024-gen256` run log from
2026-10-05 to 2026-10-19 holds one `[Start thinking]`: 76 on the flat build (S26 and Pixel 8a, b8999 and
b11721) and 30 on the S26's b11469-snapdragon side build (`llama.cpp-npu` / `llama.cpp-gpu`). On short-chat the 128-token budget can run out inside the thought:
the Pixel 8a's E2B reply of 2026-10-19 is "Here's a thinking process that leads to the suggested
explanation: …" with no answer in the budget. The flat build's records hold no prompt-token count and no
reply text (the reply is in the run log), so the page did not show it. Qwen3 thinks on every arm (the
template's default) and its rows do not change; llama-bench rows (`native-benchmark-1024x256`) have no
prompt and no chat template and do not change either.

The fix (`android/bench/run_cell.py`, `LLAMA_THINKING_OFF_FLAGS`): a Gemma 4 GGUF row — `gemma-4` in the
model id or file, any case — runs `llama-cli … -st --chat-template-kwargs '{"enable_thinking":false}'`,
on the flat build and on the side build, the template variable the Apple llama.cpp adapter passes. Every
llama.cpp prompt record now says which: `conditions.thinking` `false` (Gemma 4) or `"template-default"`
(the rest), and `conditions.chatMode` "single-turn, GGUF template, enable_thinking=false (-st
--chat-template-kwargs)" or, as before, "single-turn template default (-st)".

Cells re-measured, page cells first, one job-route sitting per file: the Pixel 8a's E2B short-chat and
1K from `matrices/dashboard-llama-thinkoff-android.cells` (its E4B rows keep their exclude-on); the
S26's from four files of one model each, so that each sitting fits a slot of the S26 queue the phone
shares with other lanes: `-s26-e2b` and `-s26-e4b` (llama.cpp, short-chat and 1K), `-s26-side-e2b` and
`-s26-side-e4b` (`llama.cpp-npu` / `llama.cpp-gpu` short-chat), all `matrices/dashboard-llama-thinkoff-*.cells`
with the Android anchor row first. `matrices/dashboard-llama-thinkoff-ladder-android.cells` lists the
rest: the side build's E2B / E4B 1K rows (page cells, by hand as in the weekly set) and the S26's 2K
ladder (round mode). The page shows each cell's latest admitted session, so the first admitted sitting
after the fix gives these cells their new value; until then they show the thinking-on numbers.

## MLX Gemma 4 file (2026-10-19)

The page's MLX Gemma 4 rows (the Mac and iPhone short-chat and `long-context-1024-gen256` rows of
`matrices/dashboard-text-v1.cells` and the 1K rows of `dashboard-longctx1024-v1.cells`) run
`mlx-community/gemma-4-{e2b,e4b}-it-qat-OptiQ-4bit`; the team pointed on 2026-10-19 to the mlx-community
bundles with far more downloads, `gemma-4-{e2b,e4b}-it-4bit` and `gemma-4-{E2B,E4B}-it-qat-mobile`. The three
families were measured on the Mac in one sitting and the file follows the rule below. Download counts and
bytes are listed for the record; they are not read as speed.

Rule. The page's MLX Gemma 4 file is of the QAT class, the class of the page's comparison partner (the
LiteRT-LM Gemma 4 bundles, Google's wNa8o8 QAT mobile schema). Among the QAT bundles that the pinned
mlx-swift-lm loads and whose 1K replies pass the text check (text-check-rule; on the Mac, the session
checker's text screen), the page takes the one with the fastest warm decode on `long-context-1024-gen256` in
one sitting (`render_leaderboard.arm_row`'s warm median). Two within 5 % of each other go to the one with more
30-day downloads (the Hub API's `downloads`, read on the day of the sitting). A PTQ build is the page's second MLX
row, not a candidate for this one: its class is in the row's name (subsection "2 rows from 2026-10-19" below). A
bundle the pinned runtime cannot load stays in the table with its error.
(Until 2026-10-19 11:4x the rule read: "A PTQ build is measured for the table and is no candidate
(`ModelCatalog.swift`: the E2B PTQ build scored 78 % and the QAT build 87 % on GSM8K, n = 100).")

The bundles (Hub main and the 30-day downloads as read 2026-10-19 10:23 JST; bytes = every `*.safetensors` file
the yardstick downloads, each one's sha256 hashed from the bytes in the Mac's Hub cache and equal to the Hub's
`lfs.sha256`):

| Bundle (`mlx-community/…`) | Hub main | Quantization (the card; the config where the card says nothing) | Class | safetensors bytes | downloads, 30 days |
|---|---|---|---|---|---|
| `gemma-4-e2b-it-qat-OptiQ-4bit` | `6bf302fd` | QAT base `google/gemma-4-E2B-it-qat-q4_0-unquantized`; mlx-optiq per layer, 144 components at 8 bit and 132 at 4 bit, group 64, 5.24 bits per weight | QAT | 5,222,073,830 (weights 4,270,441,092, vision sidecar 951,632,738) | 956 |
| `gemma-4-e4b-it-qat-OptiQ-4bit` | `a78078f4` | QAT base `google/gemma-4-E4B-it-qat-q4_0-unquantized`; 221 components at 8 bit and 122 at 4 bit, group 64, 5.17 bits per weight | QAT | 7,478,790,516 (weights 6,522,439,186, vision sidecar 956,351,330) | 2,475 |
| `gemma-4-e2b-it-4bit` | `23876752` | `mlx_vlm.convert` of `google/gemma-4-E2B-it`, uniform 4 bit affine, group 64 | PTQ | 3,550,670,554 | 24,394 |
| `gemma-4-e4b-it-4bit` | `475b9088` | `mlx_vlm.convert` of `google/gemma-4-E4B-it`, uniform 4 bit affine, group 64 | PTQ | 5,146,800,534 | 31,114 |
| `gemma-4-E2B-it-qat-mobile` | `0548ff6d` | the card states none; config `quantization_config`, quant_method `gemma`: per-channel weights at 2 / 4 / 8 bit (MLP of layers 15–34 at 2 bit) with static input and output activation scales | QAT, mobile schema (by name and format) | 2,398,140,572 | 19,670 |
| `gemma-4-E4B-it-qat-mobile` | `65982052` | the same format (every MLP at 4 bit, lm_head and embeddings at 2 bit) | QAT, mobile schema (by name and format) | 3,455,955,670 | 15,219 |

The sitting: Mac Studio (M4 Max), 2026-10-19 10:41–11:08 JST, `results/raw/2026-10-19-mlx-gemma4-file-mac/`,
cells `matrices/mlx-gemma4-file-mac.cells` (the Mac session anchor row, then the four loadable bundles'
`long-context-1024-gen256` rows with the weekly rows' options, `cooldown=300 runs=4`; the qat-mobile rows are
`exclude=`), on the yardstick of the 2026-10-19 Mac weekly (`.build/dd-mac`, mlx-swift-lm `60bd0d78`).

| Bundle | warm decode tok/s (n, spread) | cold | prefill tok/s | peak footprint MB | text screen | the stored reply (its first 200 characters), read |
|---|---|---|---|---|---|---|
| E2B OptiQ (QAT) | 151.02 (3, 0.07 %) | 150.06 | 7,076 | 5,246 | PASS, 4 of 4 | lists the 25 items |
| E2B 4bit (PTQ) | 178.68 (3, 0.18 %) | 178.70 | 7,105 | 3,653 | PASS, 4 of 4 | declines: the passage is placeholder text |
| E2B qat-mobile | does not load | | | | | |
| E4B 4bit (PTQ) | 111.97 (3, 0.23 %) | 112.17 | 2,283 | 5,403 | PASS, 4 of 4 | declines |
| E4B OptiQ (QAT) | text-fail, no number | — | — | — | FAIL, 4 of 4 (reply-off-task) | declines |
| E4B qat-mobile | does not load | | | | | |

Prefill and peak are `arm_row`'s medians over the four runs (peak = `memoryPeakDuringDecodeMB`); a run that
fails the text check enters no column (text-check-rule).

- qat-mobile: mlx-swift-lm `60bd0d78` reads the `quantization` key of `config.json` only. These bundles carry
  `quantization_config` alone, so no layer is quantized before the weights are applied, and
  `Module.update(verify: .all)` rejects them: E2B `Unhandled keys ["input_activation_scale",
  "output_activation_scale", "weight_scale"]`, E4B `Mismatched parameter language_model.lm_head.weight … Actual
  [262144, 640], expected [262144, 2560]` (one launch each, `NOTES-qat-mobile-load.txt` in the campaign dir).
  The format matches the schema the LiteRT-LM Gemma 4 entry describes; whether it is the same checkpoint is
  unverified (the cards are empty).
- Text: the prompt asks for the list "using the passage above as context" after 18 lorem-ipsum blocks
  (`prompts/text/long-context-1024-gen256.txt`). The stored replies of three of the four bundles open by
  declining it (the records keep 200 characters of the 256-token reply); E2B OptiQ's starts the list.
  The screen is lexical (the session checker's `reply_rules` on each run's stored reply): the two 4bit replies
  name the subject while they decline and pass; E4B OptiQ's names none and fails, as in the 2026-10-19 Mac
  weekly. A hand-run dir gets no `text_screen.json` from the checker (the screen runs on job campaigns).
- E2B OptiQ read 151.02 here and 150.64 in the 2026-10-19 Mac weekly, on the same yardstick and the same
  weights: OptiQ's 2026-10-18 Hub revision moved the bf16 vision sidecar (`optiq_vision.safetensors`) to the
  repo root and registered it in the index; the text weights did not change (E2B: one blob, sha256
  `fd6e9b68…`, in the cached July, September and October revisions; E4B: the same two blobs in the September
  and October ones). The yardstick's `*.safetensors` pattern downloads the sidecar (about
  0.95 GB a bundle); the Gemma 4 loader drops its vision and audio keys. mlx-swift-lm does not read OptiQ's
  `kv_config.json` (per-layer KV precision).
- Host: two single-run dips kept their prefill (the anchor's warm run 450.80 beside 553.34; run 4 of E4B
  4bit's first launch at 92.27 beside 112.1). The gate quarantined that launch and its re-run is the row; the
  anchor row is GATE_FAIL (SPREAD 20.4, `FLAGGED.txt`), so cross-session comparisons of this dir do not go
  through it. `host_load.log` in the dir lists the busiest processes every 30 s (StorageManagementService at
  about one core throughout, Google Chrome renderers, WallpaperAerialsExtension); the cause of the dips is
  unverified.

Decision: the page keeps OptiQ for both models, measured and kept. It is the only QAT bundle that loads, so the
5 % and download steps did not come into play. The E2B rows keep their number; the E4B 1K cell keeps its
text-fail mark (the model declines the lorem passage, not an engine fault). No cells file changed for these rows.
The PTQ 4bit rows above are the speed of that class; since 2026-10-19 they are the page's second MLX row (below;
this paragraph first said "the rule keeps them off the page"). If a newer mlx-swift-lm loads
`quant_method: gemma` (`./bench release-watch` lists mlx-swift-lm drift), the qat-mobile rows of
`matrices/mlx-gemma4-file-mac.cells` lose their `exclude=` and run as candidates of the QAT class, in the
schema of the LiteRT-LM file. The iPhone leg is the same procedure in its own sitting.

### 2 rows from 2026-10-19 (owner decision via code-2d)

Decision (2026-10-19 11:4x, code-2d for the owner): the page's MLX Gemma 4 has two rows per model and platform, the
QAT OptiQ row the rule above picks and the PTQ row `mlx-community/gemma-4-{e2b,e4b}-it-4bit`, each with its class in
its name. Why:

- The page's llama.cpp Gemma 4 rows run a PTQ file too (unsloth `Q4_K_M`; Google's QAT GGUF does not load as shipped,
  `matrices/dashboard-text-v1.cells`, the note above the Android Gemma 4 E2B rows).
- The PTQ bundles are the ones people download: 24,394 (E2B) and 31,114 (E4B) downloads in 30 days, against OptiQ's
  956 and 2,475, about 25 and 13 times as many (the bundle table above, read 2026-10-19 10:23 JST).
- The speed a developer gets from MLX's most downloaded Gemma 4 builds is not left off the page; the class
  difference shows in the name instead of in a missing row.

Rows: in `matrices/dashboard-text-v1.cells` (short-chat and `long-context-1024-gen256`) and
`matrices/dashboard-longctx1024-v1.cells` (`long-context-1024-gen256`), every Mac and iPhone OptiQ row has the PTQ row
right after it, with the same options. The iPhone E4B PTQ rows carry no `exclude=` (the OptiQ E4B rows keep
`exclude=app-killed-at-model-load-sigkill`): their first sitting shows whether the phone loads 5.1 GB of weights.
Each Apple sitting gains four cells at `cooldown=300`.

Names (`scripts/bench_common.py` `LOGICAL_MODELS`, before the generic Gemma 4 patterns): `Gemma 4 E2B (QAT OptiQ)`,
`Gemma 4 E2B (PTQ 4bit)`, `Gemma 4 E4B (QAT OptiQ)`, `Gemma 4 E4B (PTQ 4bit)`. In the bench's table
(`scripts/render_dashboard.py`) they are the MLX rows' labels: two artifacts of one arm share a model row, so
`load_cells` gives both their full names, as for the CQ4 lineages; the LiteRT-LM and llama.cpp cells stay on the
`Gemma 4 E2B` / `Gemma 4 E4B` rows.

Undo: remove the PTQ rows from the two cells files. The names can stay; they label the PTQ ids only and keep the
E4B OptiQ build apart from the generic pattern, as the E2B one has been.

Numbers so far: the Mac's PTQ figures are the table above (one hand-run sitting,
`results/raw/2026-10-19-mlx-gemma4-file-mac/`). The page reads the weekly sittings, so its Mac PTQ cells read "not
measured" until the Mac's next weekly sitting runs the new rows. The iPhone 18 Pro's first PTQ sitting ran through
the job route with `matrices/mlx-gemma4-file-ios.cells` (the session anchor row, then the E2B OptiQ, E2B 4bit and
E4B 4bit rows of both tasks, byte-identical to the weekly rows) on 2026-10-19 13:15–14:15 JST, campaign
`results/raw/2026-10-19-dashboard-v1-iphone18pro-mlx-ptq-r3-ios/` (anchor phase `…-mlx-ptq-r3-anchor-ios/`; `-r3`:
the two earlier starts stopped before any payload cell). Every cell has its records: the E4B PTQ build loads on the
phone (peak footprint about 5.1 GB), so its iPhone rows carry no `exclude=`. The PTQ 1K replies decline the lorem
passage, as on the Mac. The two 4bit bundles were copied over USB from the Mac's Hub cache into the app's own Hub
cache first, so no cell downloaded over Wi-Fi: the app's MLX loader (swift-huggingface `HubClient`) reads
`Library/Caches/huggingface/hub/models--mlx-community--<repo>/refs/main` and `snapshots/<rev>/` in the app's container.
`devicectl device copy to` sends a snapshot directory's symlinks as links and refuses their `../../blobs/` targets
("File paths cannot contain '..'"), so each file goes in its own copy, the blob under the file's name.

## iPhone 17 Pro, Artificial Analysis slots: two models that do not run as chat (2026-10-19)

Slots `matrices/dashboard-aa-v1-ios-i*.cells`, LiteRT-LM v0.18.0 on the Metal GPU of the iPhone 17 Pro
(A19 Pro), bench app built from this repo at 93961ee6:

- `litert-community/gemma-3-270m-it` (`gemma3-270m-it-q8.litertlm`): the short-chat reply is empty. Each run
  decodes to the context limit (652 tokens after a 20-token prompt, `ctx=672`) and no visible text reaches the
  stream (time to first visible token 0, wall rate 0), 2 of 2 runs in both 2026-10-19 sittings of slot i5. The
  row's short-chat rate is therefore no chat rate (session checker `gen-budget`, text screen `reply-empty`);
  its native 1024/256 cell is a forced-length decode and reads no text.
- `litert-community/LFM2.5-1.2B-Instruct` (`LFM2.5-1.2B-Instruct_int4_gpu.litertlm`): the engine is not
  created, 2 of 2 launches: the Metal delegate's generated shader does not compile ("implicit conversions
  between vector types ('half4' ... and 'float4' ...) are not permitted"), DYNAMIC_UPDATE_SLICE then fails
  to prepare on the CPU, and the engine reports "Failed to modify graph with delegate". Its cells record the
  failure.
- 2026-10-20, slot i6 again (the same build): `LFM2.5-1.2B-Instruct` fails the same way in short chat (2 of 2),
  while the same file's native `benchmark()` runs on the GPU, 4 of 4 (1024 / 256 at context 2048: prefill
  2,275–2,298 tok/s after the cold launch's 1,372, decode 72.8–74.2 tok/s). The native import takes its record
  shape from a task record of the same model (`--like`), so that cell stays NATIVE_IMPORT_PENDING, without a record.
- `litert-community/MiniCPM5-1B` (`minicpm_wi4b32_wi8_afp32_gpu_opt.litertlm`, Hub revision d417eaa3): the native
  1024/256 cell cannot run with this file. The launch stops at its first run with "Input token ids are too long.
  Exceeding the maximum number of tokens allowed: 1024 >= 1024" (the cell asks for context 2048). Its short chat
  runs, at 24 prompt tokens where v0.16.0 read 20: the file's LlmMetadata for LiteRT-LM 0.18.0 (Hub commit
  d417eaa3, 2026-10-10, weights unchanged) ends the generation prompt with an empty think block
  (`<think>\n\n</think>\n\n`) when thinking is off, and v0.18.0 renders that template. The 4 extra tokens match it,
  and the reply is on topic (text screen PASS).

## 1K task tail (2026-10-19)

Decision (code-2d, 2026-10-19 11:4x, under the owner's rule that what the team's purpose decides is done
without asking: the task is the team's own instrument): the cross-arm 1K task `long-context-1024-gen256` keeps its id, its 18 lorem blocks, its
budget (a prompt of about 1,024 tokens, decode 256, context 2048) and every cells row, and its tail
becomes the 2K ladder's `-noref` sentence on every arm at once. The protocol cell
(`native-benchmark-1024x256`: forced prefill, no prompt) does not change.

Why. The task is the house's instrument for the arms with no forced-prefill entry point, and its old
tail asked the model to use the lorem blocks. With the model's own chat template applied, Gemma 4
declines them: llama.cpp b11721 E2B and E4B (1,106 prompt tokens) and MLX OptiQ E4B, 4bit E2B and
4bit E4B answer that the passage is placeholder text (`results/raw/2026-10-19-llama-template-probe-mac/`,
"MLX Gemma 4 file (2026-10-19)" above), so the column timed the decode of a refusal on some arms and
of a list on others. The `-noref` tail calls the blocks filler and asks for the same list from the
model's own knowledge; on the Galaxy S26 GPU both Gemma 4 bundles then filled the 256-token budget
(catalog X2, `results/raw/2026-10-12-catalog-x2-s26-android/`). The fix is the same for every arm.

| | tail (after the 18 blocks and a blank line) | `prompts/text/long-context-1024-gen256.txt` |
|---|---|---|
| until 2026-10-19 | "Using the passage above as context, list 25 distinct things on-device AI lets a phone do that a cloud model cannot. Number every item and give each one two full sentences of explanation. Do not stop early." | 5,219 bytes, sha256 `f64fb515…` |
| from 2026-10-19 | "The numbered blocks above are filler text and carry no information; do not summarize or evaluate them. From your own knowledge, list 25 distinct things on-device AI lets a phone do that a cloud model cannot. Number every item and give each one two full sentences of explanation. Do not stop early." (`LongContextTask.norefTail` = `NOREF_TAIL` in `scripts/gen_task_prompts.py`) | 5,311 bytes, sha256 `740112db…` |

The version mark. A text change under one id breaks the series, so every record says which text it
ran: `conditions.promptVersion` = `noref-2026-10-19` on the 1K records from the new text on, no key
on the records before. The Apple records get it from `BenchmarkTask.promptVersion` through
`RunConditions` (`BenchmarkRunner`); the Android runner, the DDP records and the Mac ONNX Runtime GenAI,
uzu and ExecuTorch drivers from `prompts/text/versions.tsv`, which the generator writes with the prompt
files. `long-context-2048-gen256-noref` is named `noref-2026-10-12`, its text since its first records
(catalog X2): its records before 2026-10-19 carry no version and the same text. `results/summary/device-runs.csv`
carries the version as `prompt_version` (after `task`; empty where the record names none). Readers:
- the session checker keys the prompt-token history by it, beside `model_file`: the first sitting on the
  new text reads "prompt history: none … at prompt version noref-2026-10-19", a note, not a HOLD against
  the old text's counts;
- `scripts/regression_watch.py` and the team page (`build.py`, `tools/check_regression.py`,
  `tools/render_check.py` in the page repo) compare a point only with points of its own version, as decode
  compares only within its regime: the first point on the new text is compared with nothing
  (`prompt_changed`, "prompt changed from the previous point (none → noref-2026-10-19): not compared", the
  line broken there), so the change never reads as a regression and queues no retake; later sittings compare
  among themselves. A retake whose previous point ran another version is not judged;
- `./bench regress` (`scripts/regression_diff.py`) joins device cells on (device, runtime, model, task, prompt version,
  context, cold / warm): a baseline on one text and a candidate on the other do not join, so the release-regression
  matrix's 1K rows give no verdict across the change (the "no common cells" list names the versions);
- ExecuTorch's `llama_main` reads a prompt rendered once on the host with the model's chat template
  (`<pte stem>.prompts/<task>.chat.txt`, `scripts/executorch/make_prompts.py`); `parsers.executorch_inputs`
  refuses a render whose `prompts.json` `sourceSha256` is not the repository file's and prints the re-render
  command, so a stale render never runs the old text under the new version.

Prompt tokens on the new text (Mac Studio M4 Max, the yardstick rebuilt with the change, one launch per cell,
2026-10-19 12:28–12:30 JST; a prompt check, its speeds are not used; the dir stays out of the summary). The old
tail's counts and replies are those cells' records in the same day's sittings: llama.cpp from
`2026-10-19-dashboard-v1-m4max-llama-b11721-mac`, MLX from `2026-10-19-mlx-gemma4-file-mac`, LiteRT-LM from
`2026-10-19-dashboard-v1-m4max-0180-rebuilt-mac` (the stored reply keeps 200 characters).

| Cell | prompt tokens, old tail → new | generated (budget 256), old → new | the stored reply on the new tail |
|---|---|---|---|
| llama.cpp b11721, `unsloth/gemma-4-E4B-it-GGUF` Q4_K_M (jinja, thinking false) | 1,106 → 1,123 | 86 (stopped: "I am sorry, but the passage you provided is placeholder …") → 256 | "Here are 25 distinct things on-device AI lets a phone do that a cloud model cannot: 1. **Real-time Voice Transcription without Latency:** …" |
| MLX, `gemma-4-e4b-it-qat-OptiQ-4bit` | 1,107 → 1,124 | 256 (opens "… the provided text is a block of repetitive "Lorem Ipsum" …") → 256 | "Here are 25 distinct things on-device AI lets a phone do that a cloud model cannot: 1. **Real-time Voice Transcription Offline:** …" |
| LiteRT-LM v0.18.0, `gemma-4-E2B-it-litert-lm` | 1,106 → 1,123 | 256 (opens "The provided text is placeholder "Lorem ipsum" text …") → 256 | "Here are 25 distinct things on-device AI lets a phone do that a cloud model cannot: 1. **Real-time, low-latency voice commands:** …" |
| llama.cpp b11721, `unsloth/Qwen3-1.7B-GGUF` Q4_K_M (jinja, thinking: the template's default, on) | 1,338 → 1,355 | 256 → 256 | "<think> Okay, the user wants me to list 25 distinct things that on-device AI can do that a cloud model can't. …" |

Every record carries `conditions.promptVersion` `noref-2026-10-19`; the new tail adds 17 tokens on both vocabularies
(92 bytes). The two llama.cpp launches end in the known Metal teardown abort after their record (`FAILURES.txt`).

The flip. The merge, the Mac yardstick switch (`.build/dd-mac`), the iPhone install and the re-render of the
six Mac ExecuTorch Qwen3 prompts happen together, between sittings: the Android, DDP and Mac Python drivers read
the prompt file from the checkout and the yardstick and the app build the text into the binary, so a Mac
sitting on the merged checkout and the old yardstick would run ONNX Runtime GenAI and ExecuTorch on the new text
and the yardstick arms on the old one. Each record's version still names what it ran. Date: 2026-10-20, merge 40e2aec6; the rebuilt yardstick and app
follow it once the Mac measurement window is free (the lane record, `results/raw/2026-10-18-bench-autopilot-dev/LANE.md`).

Back out: give the 1K task back its old tail and no version (the generator's `PROMPTS` entry without
`tail=NOREF_TAIL` and its `VERSIONS` line removed; the Swift definition without `tail:` and `promptVersion:`),
regenerate with `python3 scripts/gen_task_prompts.py`, rebuild the yardstick and the app, re-render the
ExecuTorch prompts. Records then carry no version and compare again with the records before 2026-10-19 (the
same text); the page marks the break back.

## Open questions for the LiteRT team

1. Qwen3 LiteRT artifacts per backend. 0.6B rows used `qwen3_0_6b_mixed_int4`
   (continuity with the existing rows and anchors) until 2026-10-19; since then
   they run `Qwen3-0.6B_dynamic_wi4b32_afp32` (the GPU-graph build, 0.33 GB) on
   both backends (section "Qwen3 0.6B LiteRT-LM file (2026-10-19)"). 1.7B
   follows the card: wi4b32 on GPU, INT8 on CPU. Preference?
2. The Gemma 4 `-gpu.litertlm` variants published 2026-08-07 (E2B 2.0 GB, E4B
   2.97 GB) are undocumented on the cards; the GPU rows keep the standard
   files. Should they switch?
3. Second task: add the 1024/256/ctx-2048 column for every arm? (In the
   weekly set since 2026-10-06 for LiteRT-LM, llama.cpp and MLX — section
   "Second task in the weekly set".)
4. Devices: the cells file is device-agnostic; which lab devices map to the
   Android and iPhone rows?
5. Go signal for Qwen3.5 / LFM2.5 — the placeholder rows are ready to
   uncomment (Apple-side LiteRT catalog entries for Qwen3.5 still to add).
6. iPhone MLX E4B: the QAT OptiQ build (6.5 GB) is killed at load on the
   iPhone 17 Pro; use the 5.1 GB PTQ 4-bit build for that one row (a different
   recipe from the Mac's MLX row, disclosed), or leave the cell as the finding?
   (2026-10-19: both — the OptiQ row stays with its reason and the PTQ row runs beside it on every Apple
   device; section "MLX Gemma 4 file (2026-10-19)".)
7. Long-context cells on the `mixed_int4` Qwen3 files: their 2,048-entry KV
   cannot hold a 2K prompt plus a 256-token reply, and `maxNumTokens` above
   the exported size runs with invalid decode results instead of an error
   (2026-09-18 Mac leg above). For the long-context column, should the 0.6B
   and 4B LiteRT rows switch to a wider-cache file (the wi4b32 build exists
   for 0.6B only), or is a larger-cache `mixed_int4` export planned?
8. Qwen3-1.7B on the Galaxy S26 GPU at the 1K prefill (2026-10-06). The GPU
   row's file, `Qwen3-1.7B_dynamic_wi4b32_afp32.litertlm`, failed the text
   check on every iteration of its three `long-context-1024-gen256` launches
   (prompt 1,338 tokens, `--max_num_tokens=2048`, LiteRT-LM v0.16.0
   `litert_lm_advanced_main`; hand-run round-mode campaign
   `results/raw/2026-10-06-dashboard-longctx1024-v1-s26-a2-android/`,
   `NOTES.md`): `text-off-task-screen` — fluent text that never takes up the
   question (the cold iteration stops after 116 tokens, the warm one runs the
   256-token budget), no `Invalid decode` line. The CPU row of the same
   sitting (INT8 `Qwen3_1.7B.litertlm`) stays on the task. The same GPU file
   fails at the 2K prefill too, where it decoded 256 newline tokens
   (`exclude=s26-gpu-garbage-text-at-2k-prefill` in
   `matrices/dashboard-longctx-v1-android-s26.cells`): the same kind of
   finding, now at 1K. The cells file stays as it is — the rate leaves the
   dashboard through the text-check-rule (`methodology/fairness-rules.md`
   §12), the records stay in raw. Is the wi4b32 file expected to answer a
   prompt of about 1.3K tokens on the Android GPU with v0.16.0, and is there
   a file or a setting the GPU row should use instead?
