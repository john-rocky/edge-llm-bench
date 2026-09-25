# ASR word error rate through LiteRT-LM's OmniEngine, v1 (2026-09-25)

Task id `omni-asr-wer-librispeech-v1`. The question this answers: what does a
litert-community ASR bundle score on an Open ASR Leaderboard set when it is run
the way an app will run it — through `OmniEngine` (LiteRT-LM `omni/`), the
unified C++ API behind the coming Kotlin and Swift ASR/TTS APIs. The number is
therefore a property of the bundle *and* the engine's streaming path (fixed
windows, overlap, text merger), which is what an app ships. First capture:
`results/raw/2026-09-25-omni-asr-wer-v1-m4max-mac/` and
`…-s26-android/` (NOTES.md there has the numbers; this page is the definition).

## What is measured

**Word error rate** on one Open ASR Leaderboard set, scored the leaderboard's
way: the leaderboard's `EnglishTextNormalizer` on reference and hypothesis,
then corpus-level WER (`jiwer` over the whole set = `evaluate`'s `wer`), in
percent. **RTFx** = audio seconds / engine wall seconds, model load excluded,
one utterance per session (session creation is reported separately). The
leaderboard's own numbers for the source models (its H200 runs of the reference
implementations, `scripts/data/en_shortform.csv`) are the comparison column.

## The sets

`hf-audio/open-asr-leaderboard`, config `librispeech`, splits `test.clean`
(2620 utterances, 5.403 h) and `test.other` (2939 utterances, 5.342 h), the
parquet files as published. `tools/omni-eval/prep_librispeech.py` unpacks each
to 16 kHz mono PCM16 WAV plus `manifest.jsonl` (id, path, raw reference text,
seconds) and `manifest.tsv` (the runner's input); `SET.json` pins the utterance
count, total seconds and a sha256 chain over the WAVs.

## The instrument

`tools/omni-eval/omni_eval_runner.cc`, built inside a LiteRT-LM checkout as
`//omni:omni_eval_runner` (`tools/omni-eval/omni.BUILD.patch`). Per utterance
it does what an app does with the API: `OmniEngine::Create(model_name, {backend,
cache_dir, num_threads})` once, then `CreateSession(PushInputSource)`, push
`AudioInputMetadata{16000, 1}`, the whole file as one `AudioInput`, `EndOfInput`,
call `ProcessNext()` until `OutOfRange`, then `Flush()`. The transcript is every
non-empty `confirmed_text` joined by spaces, exactly what `omni/asr/asr_runner.cc`
prints. `--push_chunk_ms` pushes the audio in small pieces instead (the streaming
shape) and `--reuse_session` keeps one session and calls `Reset()` between
utterances; both gave byte-identical transcripts on the probes, so v1 uses the
defaults. A `Flush()` that returns NOT_FOUND ("Deque has no output available")
means nothing was pending and is recorded as `flush_empty`, not as an error
(`asr_runner` ignores it too).

The engine's own defaults decide the protocol and are not overridden: window =
the bundle's export window from `omni/asr/model_metadata.json` (parakeet 5 s,
whisper 30 s), overlap 0.4, `timestamp` merger, 4 threads, GPU precision fp32
(`AsrEngineConfig`). Models and tokenizers are the files the metadata names,
staged as `<cache_dir>/<model_name>.tflite` and `<model_name>_tokenizer.json`
(OmniEngine does not download).

Engine: LiteRT-LM `main@66058c82` (2026-09-25, the commit that split
`AudioInput`/`AudioInputMetadata`), built with bazel 7.6.1. On macOS the
`//omni:omni_engine` target does not build at that commit — its TTS dependency
pulls espeak-ng, whose `speech.h` includes `<endian.h>`; the two-target split in
`tools/omni-eval/espeak_ng.BUILD.macos.patch` (compat include dir for the C
sources only) is what the Mac binary carries. The Android binary is the same
source with NDK r28, no patch needed.

## Reference arm

`tools/omni-eval/ref_whisper.py` runs `openai-whisper` `tiny` (the multilingual
model the litert-community `whisper-tiny` bundle was exported from; the
leaderboard lists only `tiny.en`) greedy, fp32, CPU, on the same WAVs and writes
the same record shape, so the bundle's number has a same-model, same-scorer
reference next to the leaderboard's `tiny.en` row.

## Record shape

One JSONL per cell: a header (model, backend, threads, load seconds), one line
per utterance (`id`, `text`, `audio_seconds`, `processing_seconds`,
`session_create_seconds`, `outputs`, `flush_empty`, `error`), a footer (totals,
RTFx, peak RSS). `tools/omni-eval/score.py` turns a cell plus its manifest into
the summary JSON (WER, S/D/I, reference words, RTFx, empty hypotheses) and a
per-utterance details JSONL (normalized ref/hyp, S/D/I, seconds), which is what
the length buckets and the worst-utterance lists in NOTES.md are computed from.

## Minimal reproduction of the window drop

`tools/omni-eval/make_pieces.py` cuts LibriSpeech test-clean utterance
4507-16021-0047 (34.955 s) into its seven 5-second windows and a few shifted
windows; running each piece alone through `asr_runner` shows which windows the
engine returns empty for (NOTES.md has the table). No WAV is committed; the
utterance is in the public dataset.

## Not covered in v1

- Other leaderboard sets (AMI, Earnings22, GigaSpeech, SPGISpeech, TED-LIUM,
  VoxPopuli, Common Voice) — the harness takes any config of the same parquet
  layout.
- The other four ASR bundles the engine knows (parakeet-ctc-0.6b, moonshine-tiny,
  qwen3-asr-0.6b, tinygemma-asr).
- NPU rows; the engine's `ProcessAsync` path (v1 uses `ProcessNext`).
- iPhone (no released engine for iOS yet).
