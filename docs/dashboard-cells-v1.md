# Dashboard cells v1 — the text-only model set (prepared 2026-09-05)

The initial cell set for the competitive dashboard kick-off on 2026-09-07:
the five text-only models the LiteRT team named on 2026-09-04, across the
three engines that publish an artifact for every one of them, on Android,
iPhone and Mac. One command per platform re-measures it. This page is the
cell table, the bundle inventory (what exists, what is missing), the
competitor-arm status including a first look at Mirai, and the open
questions for the LiteRT team.

Cells file: `matrices/dashboard-text-v1.cells` (45 cells: 5 models × 3 arms
× 3 platforms; validated by `scripts/validate_cells.py`).

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

### iPhone 17 Pro and Mac M4 Max (same ids on both; LiteRT and llama.cpp on Metal, MLX on Metal)

| Model | LiteRT-LM | MLX | llama.cpp | rows so far (iPhone / Mac) |
|---|---|---|---|---|
| Qwen3 0.6B | `litert-community/Qwen3-0.6B` | `mlx-community/Qwen3-0.6B-4bit` (session anchor) | `unsloth/Qwen3-0.6B-GGUF/Q4_K_M` (new catalog entry) | LiteRT, MLX / LiteRT, MLX |
| Qwen3 1.7B | `litert-community/Qwen3-1.7B` (new catalog entry) | `mlx-community/Qwen3-1.7B-4bit` | `unsloth/Qwen3-1.7B-GGUF/Q4_K_M` (new catalog entry) | none |
| Gemma 4 E2B | `litert-community/gemma-4-E2B-it-litert-lm` | `mlx-community/gemma-4-e2b-it-qat-OptiQ-4bit` | `unsloth/gemma-4-E2B-it-GGUF/Q4_K_M` | LiteRT / LiteRT |
| Qwen3 4B | `litert-community/Qwen3-4B` | `mlx-community/Qwen3-4B-4bit` | `unsloth/Qwen3-4B-GGUF/Q4_K_M` | LiteRT / none |
| Gemma 4 E4B | `litert-community/gemma-4-E4B-it-litert-lm` | `mlx-community/gemma-4-e4b-it-qat-OptiQ-4bit` | `unsloth/gemma-4-E4B-it-GGUF/Q4_K_M` | none |

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

The set has been run end to end on all four devices the same day: the Galaxy S26, the Mac M4 Max, the Pixel 8a, and 12 of 15 cells on the iPhone 17 Pro. S26 (campaign
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
12 of the 15 cells, 4 runs each (anchor 3). The phone sat at thermal "fair"
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
`2026-09-05-dashboard-v1-ios-e4b/`).

Pixel 8a, afternoon and evening, as three sessions because the phone had
14–21 GB free and the full set needs about 28 GB on the device
(campaigns `2026-09-05-dashboard-v1-pixel8a-a2-android/`, `-b1-android/`,
`-b2-android/`, cells files `dashboard-text-v1-android-{a,b1,b2}.cells`,
each with its own anchor; my pushes were removed between sessions): all 15
cells, 3 runs each, every run at thermal nominal, no gate flags. Both
4B-class models fit the 8 GB phone on every arm — Qwen3 4B at 4–7 tok/s,
Gemma 4 E4B at 5–8 tok/s — so the memory-risk cells listed above became
ordinary rows. A first attempt at 12:07 was aborted: a sibling lane's
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
The S26 ordering on Qwen3 0.6B (llama.cpp CPU 106, LiteRT GPU 54, LiteRT
CPU 25 tok/s) reproduces the 2026-08-25 session (104 / 52 / 28) within a
few percent.

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
| Core AI (Apple) | iPhone, Mac | no | side-loaded own exports; Qwen3 0.6B measured 2026-08-26, the 1.7B/4B bundles are not staged; the Gemma 4 bundles need an unpublished engine patch, so that arm is not independently reproducible (`environment.lock.json` caveat) |
| Mirai (`uzu`) | Mac, iPhone; Android "Soon" | investigate | below |

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
