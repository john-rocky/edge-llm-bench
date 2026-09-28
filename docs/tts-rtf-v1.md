# TTS real-time factor, v1 — the third non-LLM task family (2026-09-24)

Task id `tts-rtf-libri1272-2sent`; cells `matrices/tts-rtf-v1.cells`; driver
`scripts/tts_rtf_mac.py` + `scripts/tts_rtf_worker.py` (dispatched by
`scripts/bench_matrix_mac.sh` for every `tts-rtf-*` row, so
`./bench matrix matrices/tts-rtf-v1.cells --platform mac` is the whole entry
point). First capture: `results/raw/2026-09-24-tts-rtf-v1-m4max-mac/` (NOTES.md
there has the numbers; this page is the definition).

## What is measured

**Real-time factor** = seconds the pipeline spends synthesizing / seconds of
audio it produced (0.5 = twice as fast as real time; 2 = half real time). The
numerator (`ttsSynthesisSeconds`) is the wall clock of the reference pipeline's
`synthesize()` call — prompt prefill, the talker decode loop, the MTP inner
loops, codec decoding and the host glue between them — with model load and
graph compilation excluded and reported separately (`loadTimeSeconds`). Each
run is a fresh process (`coldRun: true`); three runs per cell. The pipeline's
own stage clocks (`ttsPrefillSeconds` / `ttsTalkerSeconds` / `ttsMtpSeconds` /
`ttsCodecSeconds`) and its own RTF (`ttsPipelineRealTimeFactor`, stage clocks /
audio — the number the model card quotes) ride along.

**Audio check.** A rate whose output nobody listened to is not a measurement
(benchmark-mode-needs-a-text-check, third face). Every record carries the
output's round trip: the 24 kHz WAV, resampled to 16 kHz PCM16 with macOS
`afconvert`, transcribed by the asr-rtf-v1 instrument (LiteRT-LM `omni/asr`
`asr_runner` at `main@1dadd00c`, CPU, the engine defaults) with the first
staged of two models that passed their own text check on this speaker's real
recordings — `parakeet-tdt-0.6b-v3` i8 stateful (WER 0.197) or `whisper-tiny`
i8 (0.372 over the 82 s stream; a ~10 s clip is one 30 s window, no merges) —
and scored against the input text with the ASR set's normalization
(`ttsRoundTripWordErrorRate`); `provenance.roundTripAsr` names the model,
file and sha256 used. The manifest's bar is 0.5:
above it `ttsAudioCheck` is `fail` and the rate is "throughput only". The WAVs
themselves are stored beside the records (`audio/`), sha256 in the record, so
a person can listen.

## The text

`evaldata/tts/libri1272-2sent/manifest.json`: two LibriSpeech dev-clean
reference sentences of speaker 1272 (utterances 1272-135031-0003 and
1272-141231-0011, already pinned as ASR references in
`evaldata/asr/librispeech-dev-clean-1272-82s/`; CC BY 4.0), re-cased and
punctuated as a TTS prompt — 27 words, English:

> The little girl had been asleep, but she heard the raps and opened the door.
> The other voice snapped with a harsh urgency, clearly used to command.

## The instrument

There is no LiteRT-LM engine path for a public TTS bundle yet: `omni/tts/` on
`main` (Kokoro and Qwen3-TTS stages, 2026-09) expects file layouts that are
not on the Hub — `kokoro_acoustic.tflite` + `voices/*.bin`, and for Qwen3-TTS
`text_embedding.tflite` / `mtp_embedding.tflite` + `voices/demo_speaker.bin` —
and ships no CLI (`asr_runner` is the only `cc_binary` under `omni/`).
`litert-community/Kokoro-82M` is a three-graph export whose host steps live in
a torch reference (free-text sample "in progress" per its card);
`litert-community/Qwen3-TTS-12Hz-0.6B-Base` ships **with** a complete public
Python reference pipeline. v1 therefore measures Qwen3-TTS through that
pipeline:

- **Pipeline**: `qwen3_tts_pipeline.py` from `john-rocky/litert-samples`,
  `compiled_model_api/text_to_speech_lm/python`, branch `qwen3-tts-sample` at
  commit `a1f5edf3948e9575824bf6ea568fc90ad6a8fef0` (2026-07-11), fetched into
  `.build/qwen3-tts-sample-a1f5edf/` (`COMMIT` there; sha256 of the module in
  every record). The worker imports it unchanged and calls it the way the
  sample's `synthesize.py` does.
- **Runtime**: `ai-edge-litert` 2.1.6 `CompiledModel`, CPU / XNNPACK, in a
  pinned venv (`.build/tts-venv`; `pip freeze` in every record). Record
  `runtime` is `litert-cpu`; `engineVersion` is
  `ai-edge-litert 2.1.6 + qwen3-tts-sample@a1f5edf`.
- **Model files** (`.build/tts-models/Qwen3-TTS-12Hz-0.6B-Base/`): the repo's
  default set — `talker_int4.tflite` (blockwise-32 OCTAV int4), `mtp_fp32.tflite`,
  `codec_decoder_fp32.tflite`, `tokenizer.json`, `tables/*` (host-side
  embedding tables), `voices/demo_speaker.npy` — each verified against the
  Hub's LFS sha256 (`HF_SHA256SUMS`; `provenance.hfLfsSha256Verified`).

Stage:

```bash
python3.12 -m venv .build/tts-venv && .build/tts-venv/bin/pip install "ai-edge-litert==2.1.6" numpy tokenizers soundfile huggingface_hub
D=.build/qwen3-tts-sample-a1f5edf && mkdir -p $D && for f in synthesize.py qwen3_tts_pipeline.py requirements.txt; do
  gh api -H 'Accept: application/vnd.github.raw' "repos/john-rocky/litert-samples/contents/compiled_model_api/text_to_speech_lm/python/$f?ref=a1f5edf3948e9575824bf6ea568fc90ad6a8fef0" > $D/$f; done
echo a1f5edf3948e9575824bf6ea568fc90ad6a8fef0 > $D/COMMIT
hf download litert-community/Qwen3-TTS-12Hz-0.6B-Base --include talker_int4.tflite mtp_fp32.tflite codec_decoder_fp32.tflite tokenizer.json 'tables/*' 'voices/*' --local-dir .build/tts-models/Qwen3-TTS-12Hz-0.6B-Base
# + HF_SHA256SUMS there ("sha256  path" from the Hub API); the asr-rtf-v1 runner + parakeet file for the round trip
```

## Protocol (stamped in every record's `conditions`)

All of them are the sample's own defaults; changing one is a new task id
(budget-mode-rule):

| condition | value | note |
|---|---|---|
| graphs | `talker_int4` + `mtp_fp32` + `codec_decoder_fp32` | the sample's `_DEFAULT_FILES`; the fast graphs (`mtp_folded_int8`, `codec_partA/B`) are a second recipe row on the Android leg since 2026-09-29 ("Fast-graph recipe row" below); the Python sample at `a1f5edf` has no fast path, so the Mac leg runs the default set only |
| threads | 8 (talker / codec), 1 (MTP) | the sample's `--threads` default and the pipeline's fixed MTP thread count |
| sampler | sampling, top-k 50, temperature 0.9, repetition penalty 1.05 | pipeline defaults; **seed fixed to 1** so launches are comparable (the sample leaves it unseeded) |
| frame cap | 512 (≈ 41 s) | pipeline default |
| voice | `voices/demo_speaker.npy` | the repo's bundled x-vector |
| language | `english` | explicit, not `auto` |

## Record shape

`schema/result.v1.json` with the `tts*` condition and metric keys added
2026-09-24. `model.quantization` states the talker recipe from the card and
the fp32 MTP / codec; `provenance` carries every model file's sha256 and its
Hub verification, the pipeline commit and module sha256, the venv freeze, the
WAV paths and sha256, the round-trip ASR command, the host snapshot before
and after, and the stderr log path.

## Android leg (2026-09-27)

Same task id, text, graphs, sampler settings, frame cap, voice, language and
audio check; the instrument is the **same sample's own Android app**
(`compiled_model_api/text_to_speech_lm/kotlin_cpu/android` at the same commit
`a1f5edf`, the Kotlin port of `qwen3_tts_pipeline.py` on the LiteRT Kotlin
`CompiledModel` API, CPU / XNNPACK), driven by `scripts/tts_rtf_android.py`
(a mini-runner like the asr / vl legs: `scripts/tts_rtf_android.py
matrices/tts-rtf-v1.cells --campaign <c> --serial <s> --recipes default` writes
`results/raw/<c>-android/` — `--recipes default` since the cells file also holds
the fast-graph row, which an `a1f5edf` build cannot run; the session anchor is the android rows of
`matrices/anchors.cells`, run first, admission by `scripts/dashboard_job.py`
`admit()`). One fresh process per run: an instrumentation harness
(`app/src/androidTest/.../TtsRtfBench.kt`, kept beside the sample — copy and
build steps in `android/tts-rtf/`; `src/main` untouched, its files' sha256 in
every record) does what MainActivity's "Speak"
does — `Qwen3TtsEngine(filesDir)`, then `synthesize(text, language, seed)` —
and writes the 24 kHz PCM16 WAV plus the engine's stage clocks; the host pulls
them and runs the round trip on the Mac with the same asr-rtf-v1 instrument.
First capture: `results/raw/2026-09-27-tts-rtf-v1-s26-android/`.

What the phone leg cannot hold equal, stated in every record:

| | Mac leg | Android leg |
|---|---|---|
| runtime | `ai-edge-litert` 2.1.6 (Python wheel) | `com.google.ai.edge.litert:litert` **2.1.6** AAR — the sample pins 2.1.5; the pin was raised one line in `app/build.gradle.kts` so both legs run the same runtime version (`provenance.litertAar` has the AAR's sha256) |
| threads | 8 talker / 1 MTP / 8 codec (the Python sample's defaults) | **4 talker / 2 MTP / 4 codec** (`Qwen3TtsEngine.load()`, the Android sample's own fixed values; `conditions.ttsThreads` 4, `ttsMtpThreads` 2) |
| tokenizer | `tokenizers` over `tokenizer.json` | the sample's Kotlin byte-level BPE over `vocab.json` + `merges.txt` (the Hub's non-LFS files, verified by git blob sha1); the sample's startup self-test result is `metrics.ttsTokenizerSelfTest` |
| sampler RNG | NumPy `default_rng(seed)` | `java.util.Random(seed)` — same top-k / temperature / repetition penalty, a different draw: the token sequence and the audio are **not byte-comparable** across legs at the same seed; each leg's audio check stands on its own |
| model files | the Hub files under `.build/tts-models`, sha256 on the host | the same Hub files in the app's `filesDir` (pushed by the sample's `install_to_device.sh`); sha256 read **on the phone** (`run-as … sha256sum`) against the Hub API's LFS sha256 |
| memory | `ps rss` of the worker | `VmHWM` of the app process (host poll + the harness's own reading) |
| pause between launches | 5 s | 45 s (the asr-rtf-v1 Android leg's value: S26 CPU cells drifted at 5 s) |

The round trip additionally stores a second opinion in `provenance.roundTripSecondOpinion`
(whisper-tiny i8, one 30 s window): the parakeet 5 s instrument can double a
word at a chunk-overlap seam ("voice snapped with voice snapped with" on the
S26 smoke run), which whisper's single window does not have. The protocol's
number stays parakeet's (`metrics.ttsRoundTripWordErrorRate`); the second
opinion says whether a non-zero WER is the seam or the speech.

## Fast-graph recipe row (Android, 2026-09-29)

The Hub repo also publishes a second set of MTP and codec graphs, which its card
calls the fast graphs, and the sample's branch `qwen3-tts-fast-path` (commit
`50fb1674`, 2026-07-08, "fast MTP + split codec paths (auto-selected when
present)") teaches the Android app to use them. The second android row of `matrices/tts-rtf-v1.cells`
(`recipe=mtp-folded-int8-codec-split`) measures that path; same task id, text,
voice, language, frame cap, talker and audio check as the default row.

- **Build**: `a1f5edf` + a local cherry-pick of `50fb1674` (it applies cleanly;
  the `kotlin_cpu/android` tree then equals `50fb1674`'s), plus the same harness
  and gradle patch as the default row (`android/tts-rtf/README.md`). `50fb1674`
  lives on a local branch only; the record names the cherry-pick's commit and its
  `appTree` (`provenance.pipelineCommitDetail`).
- **What the app does with the files present** (`Qwen3TtsEngine` at `50fb1674`):
  `mtp_folded.tflite` in filesDir → the folded MTP graph (`mtp_folded_int8.tflite`
  on the Hub: all 16 inner steps in one graph, in-graph argmax, **4 threads**, one
  invoke per frame instead of 17); `codec_partB.tflite` present → the split codec
  (`codec_partA` fp32, 4 threads, then `codec_partB` with XNNPACK `FORCE_FP16`,
  `CpuOptions` xnnpack_flags 4, 4 threads). Without those files the same build
  runs the default graphs, so **one build serves both rows**: before every launch
  the driver puts the three fast files in place (fast row) or renames them
  `<name>.parked` (default row).
- **What one launch records about its graphs** (harness `TtsRtfBench.kt`, read
  outside the timed regions): the graph files filesDir held, the engine's own
  selection flags (`mtpFolded`, `codecSplit`, read by reflection) and the graph
  files the process mapped (`/proc/self/maps`) — `provenance.graphSelection`. The
  driver checks all three against the row (`metrics.ttsGraphSelectionCheck`); a
  launch that ran another set is a failed run.
- **The files as read** (flatbuffer constants by dtype, 2026-09-29):
  `mtp_folded_int8.tflite` 229.6 MB holds int8 per-channel weights on 50 tensors
  (110 MB) and 14 fp32 constants of [2048, 1024] (117 MB) — the card calls the
  recipe GPTQ dynamic-int8; `codec_partA.tflite` 163.0 MB and `codec_partB.tflite`
  293.7 MB are fp32 throughout (Part B's fp16 is the runtime flag, not the file).
  Each is verified on the phone against the Hub's LFS sha256, as the default set.
- **What the row changes at once** — stated in every record, not separated: the
  MTP fold, its int8 weights and its thread count (2 → 4); the codec split and
  its fp16 back half; and the residual codebooks, which the folded graph picks by
  argmax (the app feeds it zero noise, `mtpFrameFolded`) while the first codebook
  stays sampled with the seed (`conditions.ttsResidualCodebooks`). The sampled
  trajectory, the frame count and the audio therefore differ from the default
  row's; each row's RTF divides by its own audio seconds and each row carries its
  own round trip.
- **Protocol for a comparison**: both rows in one sitting, interleaved
  (`scripts/tts_rtf_android.py … --interleave --pause 120 --wait-uncapped
  --warmup-rounds 1`: one unmeasured launch per row, then default, fast, default,
  fast, …, one launch each, 120 s before every launch, the launch gate also waits
  until no CPU policy is capped), the session anchor first. The warm-up round is
  there because the first pass without it read its first fast launch 7 % slow
  (spread-rule; the cause was not established); its records are stored as
  `<slug>.jsonl.warmup`, outside the summary. The harness also records the
  process's page faults and CPU seconds across synthesis
  (`metrics.ttsSynthesisMajorFaults` / `ttsSynthesisCpuSeconds`). A ratio between
  the rows counts only within that sitting — on the S26 the default row's RTF moves
  with the phone's temperature more than the fast row's.
- **First capture**: `results/raw/2026-09-29-tts-rtf-fast-s26-android/` (NOTES.md
  there has the numbers).

## Not covered in v1

- Kokoro-82M (LiteRT three-graph export): the host steps (hn-NSF source STFT,
  iSTFT overlap-add, G2P) exist only in the torch reference today; when the
  free-text sample lands it joins as a second model with the same task id.
- Sopro v2 turbo, Kitten TTS nano, Matcha-TTS (litert-community): each has a
  different host pipeline; none is wired.
- The `talker_fp32` recipe row, greedy decoding, other voices / languages.
- The fast graphs on the Mac leg (the Python sample at `a1f5edf` has no fast
  path), and the fast graphs one at a time (the folded MTP alone, the split codec
  alone) — the app selects each by its own file, so a single-change row is
  possible, but none is wired.
- GPU: the pipeline is CPU (the card's Mac GPU note: a 2.2.0 GPU-only
  CompiledModel crashes on macOS; 2.1.6 is what the venv pins anyway).
- iPhone: the sample has no iOS app; no leg.
- Android GPU: the sample's app is CPU-only (`Accelerator.CPU`).
