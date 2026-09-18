# ASR real-time factor, v1 — the first non-LLM task family (2026-09-19)

Task id `asr-rtf-librispeech-82s`; cells `matrices/asr-rtf-v1.cells`; driver
`scripts/asr_rtf_mac.py` (dispatched by `scripts/bench_matrix_mac.sh` for every
`asr-rtf-*` row, so `./bench matrix matrices/asr-rtf-v1.cells --platform mac`
is the whole entry point). First capture:
`results/raw/2026-09-19-asr-rtf-v1-m4max-mac/` (NOTES.md there has the numbers;
this page is the definition).

## What is measured

**Real-time factor** = seconds the engine spends transcribing / seconds of
audio (0.05 = twenty times faster than real time). The number is the engine's
whole streaming loop over one 82.335 s stream — chunking, feature extraction,
encoder, decoder, text merging — with model load and compile excluded and
reported separately (`loadTimeSeconds`). Each run is a fresh process
(`coldRun: true`); three runs per cell; the OS file cache is warm from run 2.

**Text check.** A rate whose transcript nobody read is not a measurement
(benchmark-mode-needs-a-text-check), so every record carries the transcript
and its word error rate against the LibriSpeech reference after the
manifest's normalization (lower-case, hyphen → space, `[a-z0-9']` only, no
number expansion). WER here is a sanity gate on the protocol, **not** an
accuracy leaderboard: the set is ten utterances of one speaker, and the
engine's text merger moves the WER by ±20 points (see "Protocol" below).

## The audio set

`evaldata/asr/librispeech-dev-clean-1272-82s/`: ten utterances of LibriSpeech
dev-clean speaker 1272 (chapters 128104 / 135031 / 141231; CC BY 4.0), 16 kHz
mono 16-bit WAV, 1.6–29.4 s each, 82.335 s total. `manifest.json` pins every
file's sha256, duration and reference text, and the stream order. The driver
concatenates them (no inserted silence) into `.build/asr-audio/<set>.wav`,
verifies the parts against the manifest first, and stamps the stream's sha256
into every record. English only in v1; a multilingual set is a v2 question.

## The instrument

LiteRT-LM's own ASR engine, `omni/asr/` on `main` — the C++ engine behind the
Kotlin ASR API (PR #3672, open on 2026-09-19) — through its CLI
`//omni/asr:asr_runner`. This is the only path that runs all four
litert-community ASR artifacts with the decoders they were exported for:

| model | file the engine's `model_metadata.json` names | decoder (engine) | window |
|---|---|---|---|
| `litert-community/moonshine-tiny` | `moonshine_tiny_5s_i8.tflite` | stateless greedy, no KV cache | 5 s |
| `litert-community/whisper-tiny` | `whisper_tiny_30s_i8.tflite` | stateless greedy (lazy second compile on the first chunk) | 30 s |
| `litert-community/parakeet-tdt-0.6b-v3` | `parakeet_tdt_0.6b_v3_5s_i8_stateful.tflite` | TDT with state buffers | 5 s |
| `litert-community/Qwen3-ASR-0.6B` | `qwen3_asr_0.6b_5s_i8.litertlm` | audio encoder (CompiledModel) + Qwen3 LM through `LiteRtLmRunner` | 5 s |

No released tag has this: v0.17.0 / v0.17.1 carry `6343fd39` (ASR on GPU) but
not `c9b1ba54` (.litertlm decoder, 2026-09-03), `007e7c76` (audio LMs,
2026-09-04) or `12fae71e` (embedded metadata, 2026-09-09). v1 therefore builds
`main` at `1dadd00c` (2026-09-17, the commit whose prebuilt Metal accelerator
the 2026-09-18 Qwen3 session already identified) and stamps
`engineVersion: main@1dadd00c` — a bump for measurement, the pin in
`environment.lock.json` untouched (bump-engine-for-comparison).

Build and stage (Mac, ~3.5 min with bazel 7.6.1 via bazelisk; the worktree
must have the macOS Metal dylib pulled from LFS):

```bash
cd ~/code/litert-lm-1dadd00c-wt            # git worktree add --detach … 1dadd00c
git lfs pull origin --include="prebuilt/macos_arm64/libLiteRtMetalAccelerator.dylib"
bazel build //omni/asr:asr_runner          # .bazelrc: -c opt, macos config
D=~/code/edge-llm-bench/.build/asr-runner-1dadd00c && mkdir -p $D
cp bazel-bin/omni/asr/asr_runner omni/asr/model_metadata.json prebuilt/macos_arm64/libLiteRtMetalAccelerator.dylib $D/
echo "main@1dadd00c" > $D/ENGINE_VERSION   # stamped as engineVersion
```

Models and tokenizers go through the HF cache (`hf download <repo> <file>`);
the runner wants each tokenizer at `<ASR_MODEL_DIR>/<model_name>_tokenizer.json`
(`.build/asr-models/` by default; the driver records the sha256 of every file
it hands the engine, and warns when the runner would have to `curl` one).
The GPU rows need `libLiteRtMetalAccelerator.dylib` in the runner dir
(`DYLD_LIBRARY_PATH`); the engine logs `RegisterAccelerator … name=GPU Metal`
and `delegate_metal.mm … Created a Metal device` when it took it.

## Protocol (stamped in every record's `conditions`)

All four are the runner's own defaults; changing any one is a new task id,
never a silent override (budget-mode-rule):

| condition | value | note |
|---|---|---|
| `asrChunkMilliseconds` | the model's export window (5000; whisper 30000) | fixed-shape graphs: the last chunk is zero-padded |
| `asrOverlapRatio` | 0.4 | consecutive chunks overlap 40 %, so the engine processes ≈1.7× the audio — the cost is in the RTF |
| `asrTextMerger` | `timestamp` | the merger reconciles the overlaps; it is model-sensitive (below) |
| `asrNumThreads` | 4 | LiteRT CPU threads; the GPU rows keep 4 for the CPU-side stages |
| GPU precision | fp32 | `AsrEngine` sets `GpuOptions::Precision::kFp32`; not a flag |

**The merger moves the text, not the time.** On the 2026-09-19 probes (CPU,
full stream) the `timestamp` merger duplicated overlap text for Moonshine
(WER 0.44, 52 insertions; `levenshtein` 0.245) and the `levenshtein` merger
dropped text for Whisper (0.48 vs 0.37 default); Parakeet moved 0.01.
Processing time was identical under both. v1 keeps the engine default and
reports WER next to every RTF; a merger comparison is a separate cell set.
Overlap 0 cuts Moonshine's RTF from 0.047 to 0.027 — the 1.7× is the protocol,
and it is what the Kotlin API's default session would pay.

## Record shape

`schema/result.v1.json` with the `asr*` metric and condition keys added
2026-09-19. `runtime` is `litert-lm-cpu` / `litert-lm-gpu` (backend = arm
identity, as on Android; they never pool). `model.quantization` says what the
file name says and no more (quant-label-rule): Moonshine's card documents
"f32 encoder + dynamic-range int8 decoder"; the other three cards have no
recipe text. `provenance` carries the stream sha256, the metadata json sha256,
model and tokenizer sha256, the exact command, the host's load / thermal /
foreign-process snapshot before and after, and the stderr log path
(`logs/<slug>_run<N>.stderr.log` in the campaign dir).

## Android leg (Galaxy S26, 2026-09-19)

The same runner built for the phone — `bazelisk build --config=android_arm64
--enable_platform_specific_config //omni/asr:asr_runner` in the same worktree with
NDK r28 (`ANDROID_NDK_HOME`; ~2 min) — plus the GPU accelerator `.so` files from
`prebuilt/android_arm64/` (LFS; `libLiteRtGpuAccelerator.so` is the ML Drift OpenCL
path the log names `LiteRT GPU`), staged in `.build/asr-runner-1dadd00c-android/`
with `ENGINE_VERSION` and `SHA256SUMS` like the Mac dir. `scripts/asr_rtf_android.py
matrices/asr-rtf-v1.cells --campaign <name>` (serial from `BENCH_ANDROID_SERIAL`) is
its own mini-runner: it pushes runner, libraries, models, tokenizers and the stream
WAV to `/data/local/tmp/edge-llm-bench/asr/`, verifies each model's sha256 on the
phone, gates every launch on thermal status 0 and a battery temperature ≤ 36 °C
(the S26 warms 2–4 °C over a cell while charging), waits 45 s between launches
and 90 s between cells (at 5 s the S26's CPU cells drifted +12–27 % from launch 1
to 3; at 45 s they repeat within ±1 %), and writes the same record shape into
`results/raw/<campaign>-android/`. Timing there is device-clock:
`$EPOCHREALTIME` before exec and the runner's absl timestamps for `Starting` /
`Finished`, so adb latency is not in `loadTimeSeconds` or
`asrProcessingSeconds`; first-text latency is host-side arrival. No LLM session
anchor runs on the phone in v1 (first session of the family there); the battery
temperature, thermal status and CPU frequency caps before and after every launch
are in the record instead. First capture: `results/raw/2026-09-19-asr-rtf-v1-s26-android/`
(NOTES.md there: on this phone the OpenCL path is slower than the CPU for all four
models, moonshine's Metal drift does not reproduce on Adreno, and the Qwen3-ASR
`.litertlm` GPU path returns no text there either).

## Not covered in v1

- iPhone leg: no released engine yet (the Kotlin API PR #3672 does not help iOS;
  a device build of the runner through the Swift package is the route).
- Other ASR arms (whisper.cpp, MLX Whisper, Core ML / Speech framework): the
  task is defined on the stream + reference, so any arm that reads a WAV and
  prints text can join; none is wired.
- The f32 files (the NPU AOT source) as a second recipe per model.
- Per-utterance latency (one launch per file) — the stream number amortizes the
  fixed windows; short utterances pay the whole 5 s / 30 s window.
