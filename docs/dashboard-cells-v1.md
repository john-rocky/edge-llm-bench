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
| Qwen3 0.6B | `qwen3_0_6b_mixed_int4.litertlm` (both) | `Qwen3-0.6B-Q4_K_M.gguf` (session anchor) | all three |
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
| Qwen3 0.6B | `litert-community/Qwen3-0.6B` | `mlx-community/Qwen3-0.6B-4bit` (session anchor) | `unsloth/Qwen3-0.6B-GGUF/Q4_K_M` (new catalog entry) | `core-ai/qwen3-0.6b-4bit-gpu` — INT4 dynamic, macOS-27-era export (the 26-era one decodes garbage; below) | LiteRT, MLX / LiteRT, MLX |
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
| LiteRT-LM v0.16.0 | Android, iPhone, Mac | yes | pinned (`environment.lock.json`); Android binary built from source at the tag — releases ship none |
| MLX (`mlx-swift-lm` @ 60bd0d7) | iPhone, Mac | yes | Gemma 4 loads only at the 2026-07-06 re-upload revision of the mlx-community repos, which is HF main today |
| llama.cpp b8999 | Android, iPhone, Mac | yes | Android: official CPU-only binary; the NPU (Hexagon) and Adreno GPU (OpenCL) rows run the release's official Snapdragon asset as a side build — section "NPU and Android GPU rows" below; Apple: arm wired, no rows in this repo yet |
| Core AI (Apple) | iPhone, Mac | v2 (2026-09-08) | own exports, side-loaded; Qwen3 0.6B/1.7B/4B rows active, the Gemma 4 rows `exclude=` because their per-layer-embedding bundles need the unpublished engine patch — "Core AI arm (v2)" below |
| Mirai (uzu) | Mac | separate cells | wired on Mac 2026-09-24, smoke only; [docs/uzu-arm-v1.md](uzu-arm-v1.md) |
| ONNX Runtime GenAI | Mac (CPU, WebGPU), Android (CPU) | separate cells | wired 2026-10-07, not measured yet; "ONNX Runtime GenAI arm (v1, 2026-10-07)" below |

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
The same text goes to every arm.

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
short-chat on Qwen3 0.6B; its 1K row and the other models' rows excluded). They
are not in the weekly job's schedule; putting them there is a separate
decision.

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
the 4B-class `exclude-on=`, the iPhone rows are disabled until the app has the runtime, and there
is no anchor row (the weekly file is an owner decision). Every run is one engine process, so its
cells headline the cold median on the Mac too. Drivers, pins, recipe labels, timing, memory and
telemetry: [docs/ortgenai-arm-v1.md](ortgenai-arm-v1.md).

## Open questions for the LiteRT team

1. Qwen3 LiteRT artifacts per backend. 0.6B rows use `qwen3_0_6b_mixed_int4`
   (continuity with the existing rows and anchors); the repo now also ships
   `Qwen3-0.6B_dynamic_wi4b32_afp32` (the GPU-graph build, 0.33 GB). 1.7B
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
