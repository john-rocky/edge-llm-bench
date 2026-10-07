# Android lane — adb-driven CLI benchmarks (Pixel 8a first)

Engines with Android support: **LiteRT-LM** (cpu/gpu; on the Galaxy S26 also npu,
from this repo's own runtime build) and **llama.cpp** (cpu; on Snapdragon phones also
npu and gpu, from the release's official Snapdragon asset) — "Side builds" below —
and **ONNX Runtime GenAI** (cpu, the official release AAR — "ONNX Runtime GenAI"
below). MLX and Core AI are Apple-only (n/a rows); Cactus is a phase-2 slot.
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

## Side builds (llama.cpp on the NPU and the Adreno GPU, LiteRT-LM on the NPU)

The `llama.cpp-npu` / `llama.cpp-gpu` rows (cells `backend=npu|gpu
engine-build=<tag>`) run llama.cpp's official Snapdragon release asset from a
directory of its own on the phone, `/data/local/tmp/llmbench/engines/<tag>/{bin,lib}`
— never the flat directory above, where the pinned CPU build's libraries carry
the same names. `<tag>` is the build's key in `android/engine-pins.json`.

```bash
LLAMA_FLAVOR=snapdragon LLAMA_TAG=b11469 android/scripts/fetch_llama_android.sh
#   -> android/bin/llama-b11469-snapdragon/{bin,lib}, pin "b11469-snapdragon"
E=/data/local/tmp/llmbench/engines/b11469-snapdragon
adb shell mkdir -p $E/bin $E/lib
adb push android/bin/llama-b11469-snapdragon/bin/llama-cli android/bin/llama-b11469-snapdragon/bin/llama-bench $E/bin/
adb push android/bin/llama-b11469-snapdragon/lib/*.so $E/lib/
adb shell chmod +x $E/bin/llama-cli $E/bin/llama-bench
```

Push every `.so`: the 7 KB launchers load the engine from `lib/` with no
RUNPATH (`llama-cli` alone needs eleven of them, `libllama-server-impl.so` and
`libmtmd.so` among them), and the runner sets `LD_LIBRARY_PATH` and
`ADSP_LIBRARY_PATH` to `$E/lib`. The OpenCL program cache goes to `$E/clcache`
on the first GPU chat launch, which the runner labels `firstEver`; pushing the
build again into an emptied directory relabels the next one. The witness reads
`$E/bin/<tool>` and the pinned libs in `$E/lib/` (a lib that is not the pin's
stamps `unknown`), and a cell whose `engines/<tag>` is not on the phone stops
before any launch. Settings, device lines and disclosures:
`docs/dashboard-cells-v1.md` "NPU and Android GPU rows".

LiteRT-LM on the NPU (`litert-lm-npu`, cells `backend=npu engine-build=<tag>`)
is a side build too: a LiteRT-LM runtime build with the Qualcomm dispatch and
QNN libraries, flat in `/data/local/tmp/llmbench/engines/<tag>/`, the Hexagon
skel in `dsp/`. `main-20260821-selfbuilt` is this repo's own build
(`docs/dashboard-cells-v1.md` "LiteRT-LM on the NPU"); its binary has no host
copy and sits on the Galaxy S26 in `/data/local/tmp/litertlm_npu/`, its
libraries come from the same build's deploy directory (`$R` below):

```bash
E=/data/local/tmp/llmbench/engines/main-20260821-selfbuilt
adb shell mkdir -p $E/dsp
adb shell cp /data/local/tmp/litertlm_npu/litert_lm_advanced_main $E/
adb shell chmod +x $E/litert_lm_advanced_main
adb push $R/libLiteRtDispatch_Qualcomm.so $R/libGemmaModelConstraintProvider.so $E/
adb push $R/qnn/aarch64-android/libQnnHtp.so $R/qnn/aarch64-android/libQnnSystem.so \
    $R/qnn/aarch64-android/libQnnHtpV81Stub.so $E/
adb push $R/qnn/hexagon-v81/libQnnHtpV81Skel.so $E/dsp/
adb shell sha256sum $E/litert_lm_advanced_main $E/*.so $E/dsp/*.so
#   -> android/engine-pins.json "litert-lm": {"main-20260821-selfbuilt": {
#        "litert_lm_advanced_main_sha256": …, "so_files": {"libLiteRtDispatch_Qualcomm.so": …,
#        …, "dsp/libQnnHtpV81Skel.so": …}}}
```

The runner sets `LD_LIBRARY_PATH=$E` and
`ADSP_LIBRARY_PATH="$E/dsp;/system/lib/rfsa/adsp;/vendor/lib/rfsa/adsp;/dsp"`
and passes `--litert_dispatch_lib_dir=$E`; the witness reads
`$E/litert_lm_advanced_main` and the libs its pin lists, under the names the
pin gives them (`dsp/…` for the skel). Until the pin is written, the records
stamp `unknown (…)` and a sitting stops the cell before it launches.

## ONNX Runtime GenAI (the `onnxruntime-genai-cpu` rows)

The official onnxruntime-genai 0.17.0 release AAR is CPU-only and ships no
`libonnxruntime.so` (GenAI dlopens it from `ORT_LIB_PATH`), so its runtime dir on
the phone, `/data/local/tmp/llmbench/ortgenai/`, holds the AAR's
`libonnxruntime-genai.so` and `libmat.so`, Maven onnxruntime-android 1.30.0's
`libonnxruntime.so`, the harness driver `ortgenai_run`
(`android/ortgenai/ortgenai_run.cpp`: one generation per process, the model
folder's chat template, greedy, EOS or the budget) and the upstream
`model_benchmark`. `android/ortgenai/build_android.sh` fetches both AARs and the
upstream sources by sha256 and builds into `android/bin/ortgenai-0.17.0/`
(gitignored; `MANIFEST.txt`).

```bash
android/ortgenai/build_android.sh                  # NDK; -> android/bin/ortgenai-0.17.0/
O=/data/local/tmp/llmbench/ortgenai
adb shell mkdir -p $O
adb push android/bin/ortgenai-0.17.0/libonnxruntime-genai.so android/bin/ortgenai-0.17.0/libmat.so \
    android/bin/ortgenai-0.17.0/libonnxruntime.so android/bin/ortgenai-0.17.0/ortgenai_run \
    android/bin/ortgenai-0.17.0/model_benchmark $O/
adb shell chmod +x $O/ortgenai_run $O/model_benchmark
```

The witness reads `$O/ortgenai_run` and the three libraries beside it against
`android/engine-pins.json` "onnxruntime-genai" "0.17.0" (a library that is not the
pin's stamps `unknown`), and the runner starts the engine with
`LD_LIBRARY_PATH=$O ORT_LIB_PATH=$O/libonnxruntime.so ORT_DISABLE_TELEMETRY=1`
(`ortgenai_run` refuses to run without the last one). The model is a GenAI folder
(cells `file=` + `revision=`): the runner fetches that folder into the host's HF
cache, pushes it file by file to `/data/local/tmp/llmbench/models/<repo>_<folder
name>/` and removes it when `run_cell.py` ends, or when the campaign ends under
`run_campaign.py` (`BENCH_ORTGENAI_KEEP_MODEL=1` keeps it). Its recipe label comes
from `models/ortgenai-recipes.json`; a folder without an entry is refused before
any push. `docs/ortgenai-arm-v1.md`.

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
