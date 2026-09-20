# Android lane — adb-driven CLI benchmarks (Pixel 8a first)

Engines with Android support: **LiteRT-LM** (cpu/gpu) and **llama.cpp** (cpu).
MLX and Core AI are Apple-only (n/a rows); Cactus is a phase-2 slot.
Measurement semantics and every disclosed difference from the Apple lane:
`methodology/android.md`. Device notes: `devices/pixel-8a.md`.

## Prerequisites (one-time, host Mac)

- `adb` (Android platform-tools), device with USB debugging authorized
- `bazelisk` (`brew install bazelisk`) — respects the checkout's `.bazelversion`
- Android NDK r28b+ (Android Studio SDK manager); auto-detected under
  `~/Library/Android/sdk/ndk`, or set `ANDROID_NDK_HOME`
- `python3 -m pip install huggingface_hub` (model downloads; gated repos need
  `huggingface-cli login`)

## Engine acquisition

Fast path — no build, no bazel/NDK (prebuilt at the pinned tag, hashes match
the lockfile):

```bash
mkdir -p android/bin
curl -L https://github.com/john-rocky/edge-llm-bench/releases/download/android-litert-lm-v0.17.0/litert-lm-v0.17.0-android-arm64.tar.gz \
  | tar xz -C android/bin && mv android/bin/litert-lm-v0.17.0-android-arm64 android/bin/v0.17.0
android/scripts/fetch_llama_android.sh                         # official b8999 android tar
```

Per-release source build (what produced that archive; needed for tags with no
release asset):

```bash
LITERTLM_TAG=v0.17.0 android/scripts/build_litert_lm_main.sh   # bazel source build, 10-20 min first time
```

- LiteRT-LM releases ship **no Android binary** (verified v0.14–v0.17: v0.17.0's assets are two xcframeworks +
  `litert_lm_main.macos_arm64`, checked 2026-09-14), so this
  is a per-release source build into `android/bin/<tag>/` (binary + GPU `.so`
  set). On a macOS host the build needs `--enable_platform_specific_config`
  (encoded in the script; upstream google-ai-edge/LiteRT-LM#3247).
- llama.cpp ships an official `android-arm64` artifact at the same `b8999` tag
  the Apple arm pins — no build (official-sdk rule). CPU-only.
- Both record sha256 pins in `android/engine-pins.json`; every result row
  carries `engineVersion`/`engineArtifact` from there.

## Push runtime to the device

```bash
adb shell mkdir -p /data/local/tmp/llmbench
adb push android/bin/v0.17.0/litert_lm_main /data/local/tmp/llmbench/
adb push android/bin/v0.17.0/*.so /data/local/tmp/llmbench/        # GPU backend
adb push android/bin/llama-b8999/llama-cli /data/local/tmp/llmbench/
adb push android/bin/llama-b8999/llama-bench /data/local/tmp/llmbench/
adb push android/bin/llama-b8999/*.so /data/local/tmp/llmbench/    # shared-lib build
adb shell chmod +x /data/local/tmp/llmbench/litert_lm_main /data/local/tmp/llmbench/llama-*
```

Models are HF-downloaded on the host and pushed on first use by the driver.

## Run

```bash
# one cell
python3 android/bench/run_cell.py --runtime litert-lm --backend gpu \
    --model-id litert-community/Qwen3-0.6B --task short-chat --runs 3 \
    --out results/raw/$(date +%F)-android-smoke/app-path-android

# a cells file (anchors first, interleaved rounds, thermal gate)
CAMPAIGN=$(date +%F)-android python3 android/bench/run_campaign.py \
    matrices/release-regression-litert.cells

# or the top-level driver (runs mac/iphone/android lanes that appear in the file)
./bench matrix matrices/release-regression-litert.cells --platform android
```

Records land as schema-v1 JSON under `results/raw/<campaign>/app-path-android/`
(the `app-path*` glob build_summary.py already reads) with the raw console log
next to each record (stored-report-rule). `python3 scripts/build_summary.py`
then folds them into `results/summary/device-runs.csv` with `platform=android`,
and the leaderboard renders the android section automatically.

The campaign runner applies the full session discipline unattended: thermal
gate, ≥`COOLDOWN` between runs, one-driver-per-device lock, capture gate with
quarantine + one retry (`methodology/android.md`), and automatic `firstEver`
labelling of engine-cache-build runs via an on-device marker. Verify the whole
driver with no phone attached:

```bash
python3 android/bench/selftest.py      # fake adb; CI runs this on every push
```

## Allocated-context prompt rounds

The S26 long-context cells opt into a separate round mode:

```bash
ROUNDS=2 COOLDOWN=30 THERMAL_WAIT=600 BENCH_CPU_MASK= BENCH_ANDROID_SERIAL=RFGL80R6A6H python3 android/bench/run_campaign.py matrices/dashboard-longctx-v1-android-s26-qwen06.cells --dry-run
```

The dry-run only prints JSON launch plans and exclusions; it does not probe a
device, acquire a lock, download, or write a campaign. Actual captures need a
fresh campaign and an explicit serial. Choose the per-model cells for separate
sittings; do not pool sittings or split allocation partners across them.
Every cell launches once per round, the whole order reverses on even rounds,
the anchor appears once per round, and automatic gate retries are disabled.
The round-mode cooldown is COOLDOWN (30 s for this leg), without the legacy
per-row 120/300 s overrides; the nominal thermal gate remains in place.

LiteRT prompt tasks with explicit context-tokens use advanced_main, with two
fresh Conversations in one engine. Benchmark logging is enabled with both
synthetic token counts zero, preserving the real templated prompt and native
output cap. Iteration records are cold and warm, have separate counters, and
share their launch log, elapsed time, RSS and start/end device-state samples.
The v0.16.0 CLI has no sampler-parameter flags, so sampling stays labelled
engine-default. Missing/mismatched max_tokens witnesses, incomplete iterations
and Invalid-decode messages are flagged. Plain prompt tasks without explicit
context and all native-benchmark command strings retain their old paths.
Upstream v0.16.0 benchmark mode also sets SingleThreadedExecution in the engine
settings; this does not specify the CPU kernel thread-pool size.

The llama.cpp control uses the existing single-turn llama-cli command and
records cold-process, with no warm partner. Run longctx_ab_report.py separately
with --regime cold, warm, or cold-process; Android files are loaded only from
the selected campaign's app-path-android directory. Quarantines are excluded,
protocol-invalid rates are suppressed, and non-nominal starts remain visible
for the session reviewer's admission. No per-iteration temperature or memory is inferred
from the per-launch samples.

## Endurance sessions (endurance-chat-<N>m)

30-minute multi-turn chat sessions — one engine process, one conversation
whose KV accumulates, rollover instead of silent widening, per-turn
decode/memory/thermal/degeneracy series (`methodology/endurance.md`,
Android section). The stock CLIs cannot run this (one message per process /
interactive-only `--multi_turns`), so the lane ships a harness driver built
against the pinned tag:

```bash
android/scripts/build_litert_lm_endurance.sh          # bazel; ~10-20 min cold
adb push android/bin/v0.16.0/litert_lm_endurance_main /data/local/tmp/llmbench/
adb shell chmod +x /data/local/tmp/llmbench/litert_lm_endurance_main
CAMPAIGN=$(date +%F)-s26-endurance BENCH_CPU_MASK= \
  python3 android/bench/run_campaign.py matrices/endurance-android.cells
```

Each cell is ONE session (runs=1; sessions are never pooled). Per cell the
campaign dir gets the schema-v1 record, a `.turns.ndjson` per-turn sidecar
written as turns complete (a crash keeps its evidence), and the raw console
log. The selftest covers this path too — the endurance wiring is proven in
CI on every push, no phone attached.
