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
`agreed-protocol-gemma4.md`) is the natural second task and is not in v1 —
open question 3 below.

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
   4B-class models themselves fit the 8 GB Pixel 8a on every arm.
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
| llama.cpp b8999 | Android, iPhone, Mac | yes | Android: official CPU-only binary (GPU needs a custom NDK build); Apple: arm wired, no rows in this repo yet |
| Core AI (Apple) | iPhone, Mac | v2 (2026-09-08) | own exports, side-loaded; Qwen3 0.6B/1.7B/4B rows active, the Gemma 4 rows `exclude=` because their per-layer-embedding bundles need the unpublished engine patch — "Core AI arm (v2)" below |
| Mirai (`uzu`) | Mac, iPhone; Android "Soon" | investigate | below |

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
- Bundles are side-loaded once and stay (Mac: `~/Documents/CoreAIModels/`,
  or `BENCH_COREAI_MODELS_DIR`; phone: the app's
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
D=~/Documents/CoreAIModels; mkdir -p $D
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

## Open questions for the LiteRT team

1. Qwen3 LiteRT artifacts per backend. 0.6B rows use `qwen3_0_6b_mixed_int4`
   (continuity with the existing rows and anchors); the repo now also ships
   `Qwen3-0.6B_dynamic_wi4b32_afp32` (the GPU-graph build, 0.33 GB). 1.7B
   follows the card: wi4b32 on GPU, INT8 on CPU. Preference?
2. The Gemma 4 `-gpu.litertlm` variants published 2026-08-07 (E2B 2.0 GB, E4B
   2.97 GB) are undocumented on the cards; the GPU rows keep the standard
   files. Should they switch?
3. Second task: add the 1024/256/ctx-2048 column for every arm?
4. Devices: the cells file is device-agnostic; which lab devices map to the
   Android and iPhone rows?
5. Go signal for Qwen3.5 / LFM2.5 — the placeholder rows are ready to
   uncomment (Apple-side LiteRT catalog entries for Qwen3.5 still to add).
6. iPhone MLX E4B: the QAT OptiQ build (6.5 GB) is killed at load on the
   iPhone 17 Pro; use the 5.1 GB PTQ 4-bit build for that one row (a different
   recipe from the Mac's MLX row, disclosed), or leave the cell as the finding?
