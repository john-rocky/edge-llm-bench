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
| graphs | `talker_int4` + `mtp_fp32` + `codec_decoder_fp32` | the sample's `_DEFAULT_FILES`; the fast graphs (`mtp_folded_int8`, `codec_partA/B`) are a later branch and a second recipe row, not v1 |
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

## Not covered in v1

- Kokoro-82M (LiteRT three-graph export): the host steps (hn-NSF source STFT,
  iSTFT overlap-add, G2P) exist only in the torch reference today; when the
  free-text sample lands it joins as a second model with the same task id.
- Sopro v2 turbo, Kitten TTS nano, Matcha-TTS (litert-community): each has a
  different host pipeline; none is wired.
- The `talker_fp32` recipe row, greedy decoding, other voices / languages.
- GPU: the pipeline is CPU (the card's Mac GPU note: a 2.2.0 GPU-only
  CompiledModel crashes on macOS; 2.1.6 is what the venv pins anyway).
- Phones: the Android sample app runs the same graphs, but without a
  scriptable host loop; no leg yet.
