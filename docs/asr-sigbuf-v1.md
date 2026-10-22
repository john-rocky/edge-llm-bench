# asr-sigbuf-v1 — the speech_recognition sample's TdtDecoder on its own buffers, run on the Galaxy S26

Why: the sample's `TdtDecoder` runs `decode_1` on `decode`'s LSTM state buffers, swaps the input and
output state buffers after each emitted token, and hands the encode signature's output buffer to both
decode signatures. On the S26 NPU (SM8850) decoder runs then fail with QNN's `Failed to find memHandle`
/ err 6004 (asr-npu-v1, the decoder-only runs). The change, one commit on litert-samples main 367816da,
runs each signature on the buffers created for it and copies the encoder output and the LSTM states,
in two forms: form 1 (`9ca8adad`, `TdtDecoder.kt` only) on every accelerator; form 2 (`035a442e`)
`TdtDecoder(separateBuffers)`, which MainActivity sets on the NPU only (one line of `MainActivity.kt`),
upstream main's shared buffers on the CPU and GPU. The commit to send, `b6beaafb`, carries form 2's tree
(`40fba1f7`) with the final message. Run names start with `f1-` / `f2-`.

- **Builds** (`tools/asr-sigbuf/build_apks.sh`): litert-samples branches `sigbufcheck-main` (upstream
  main + the check build) and `sigbufcheck` (the change + the same check build), differing only in the
  change's files. `.sigbufcheck.main` / `.sigbufcheck.fix` on the app's LiteRT 2.3.0 + litert-gpu 2.3.0;
  `.sigbufcheck.npu` on LiteRT 2.2.0 with the Qualcomm runtime of the v2.2.0 release (qualcomm_runtime_v81)
  and QAIRT 2.47.0's HTP libraries (the v2.3.0 release has no NPU runtime archive), from either branch.
  Every run's header names the built `TdtDecoder.kt` blob and, for form 2, `separateBuffers`.
- **Files** (`tools/asr-sigbuf/stage_models.sh`, bytes = the Hub's LFS sha256): `parakeet-tdt-0.6b-v3`
  @3ce205aa (`…_5s_i8_stateful.tflite` CPU / GPU, `…_5s_f32_stateful_Qualcomm_SM8850.tflite` NPU,
  `…_5s_f32_stateful.tflite` for the decoder-only CPU runs), `parakeet-tdt_ctc-0.6b-ja` @1a2b23be.
- **The app's path** (`SigbufBenchTest`): MainActivity's file steps one after the other per window
  (FileAudioSource 5 s / 2 s overlap → MelSpectroProcessor → `LiteRtRunner.recognize` → TdtDecoder's
  token sequence → LevenshteinTokenMerger); per window the token ids, time indices and mel / encode /
  decode times (decode = the time inside the sequence's iterator). LibriSpeech test-clean S32's first
  20 rows after the warm-up row W; main and fix alternate in one sitting (form 1: v3 main, fix, main,
  fix; form 2: one pair per entry and backend); v3 rows wait until every cpufreq ceiling is back.
  **Identity**: every window's token ids equal between the two builds; a row that stops with an error
  counts as equal only when both builds stop at the same window with the same message after the same
  token ids (written into the round's lines before the ja GPU pair ran).
- **The decoder alone** (`SigbufDecoderTest`): TdtDecoder on asr-npu-v1's four CPU encoder outputs, three
  passes = 12 windows, the f32 file on the CPU and the SM8850 file on the NPU.
- **The NPU entry through the app's path**: S32's first 3 rows on the SM8850 file, each window read up
  to 630 tokens (TdtDecoder has no per-frame cap; the NPU encoder's NaN output, LiteRT#11038, keeps it
  on token 0).
- **MainActivity's own decoder** (`SigbufMainActivityTest`, form 2): MainActivity loads v3 through its
  own `preparePipeline` (the test fills its selectors); the test reads the TdtDecoder it built and its
  `separateBuffers` (reflection) and takes one WAV through the activity's own objects.
- **Logs**: each test reads its own process's log while it runs (`SigbufIo.LogcatTap`): E / F lines and
  memory-handle / 6004 lines kept, QNN registrations, deregistrations and graph executions counted.
- `tools/asr-sigbuf/compare.py summary <record> f1-|f2-` → `compare-f1.json` / `compare-f2.json`.
