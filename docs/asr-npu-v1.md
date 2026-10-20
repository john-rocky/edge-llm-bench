# asr-npu-v1 — where the speech_recognition sample app's NPU text goes wrong on the Galaxy S26 (SM8850)

Why: through the sample app on the S26's NPU, the TDT model's decoder repeats token 0 with duration
0 and later fails in QNN (`Failed to find memHandle`), and the CTC model's text is empty or `t`
(asr-litert-app-v1 L3, asr-burst-v1 B-L6, asr-fix-v1 b-l3f). These checks separate the app's own
code from the AOT model files and their execution on the NPU. Runtime: LiteRT 2.2.0 with the
Qualcomm runtime of the LiteRT v2.2.0 release (qualcomm_runtime_v81) and QAIRT 2.47.0 (the v2.3.0
release has no NPU runtime archive).

- **Files** (`tools/asr-npu/stage_models.sh`, bytes = the Hub's LFS sha256): parakeet-tdt-0.6b-v3
  @3ce205aa `…_5s_f32_stateful.tflite` (CPU) and `…_5s_f32_stateful_Qualcomm_SM8850.tflite` (NPU);
  parakeet-ctc-0.6b @e3c5b655 `…_5s_f32.tflite` (CPU), `…_5s_i8.tflite` (CPU, the app's entry) and
  `…_5s_f32_Qualcomm_SM8850.tflite` (NPU).
- **B, the encoder (and the TDT decoder) alone** (`NpuCompareTest`, LiteRT's Kotlin API only, the
  options `LiteRtRunner` builds): fixed encoder inputs = the app's own features (`MelDumpTest`:
  FileAudioSource, 5 s windows with 2 s overlap → MelSpectroProcessor → pad / truncate, written on the
  Mac) of three windows of S32's first utterance `4507-16021-0047`: its first, its middle, and the one
  with the largest share of 10 ms frames under −40 dBFS among the rest. Each runs through `encode` on
  the CPU (f32 file) and on the NPU (AOT file), twice (repeats compared bit for bit); the TDT
  decoder's `decode` (tokens [blank, 0, 0, 0]) and `decode_1` (token [blank]) run once with zero
  LSTM states on the CPU's encoder output on both sides, and on each side's own. Per output: max |Δ|,
  mean |Δ|, cosine, NaN / Inf; CTC: the per-frame argmax agreement and the tokens the app's decoder
  would read; TDT: per-frame cosine, the token / duration argmax agreement of decode. A window
  **differs** when cosine < 0.99 (a non-finite NPU value counts as differing) or, for CTC, the argmax
  agrees on fewer than 90 % of the frames (set before the runs; `tools/asr-npu/compare.py`).
- **A, the app's CTC path on the CPU** (`AsrBenchTest`, `parakeet-ctc-0.6b` entry, `model_file` for
  the f32 file): S32's first 20 rows (F20), int8 and f32. WER < 20 % = the app's CTC path is right.
- **C, the TDT decoder's buffers** (`AsrBenchTest`, `tdt_fix=true`): the app's buffers
  (`tdt_buffers=shared`: decode_1 runs on decode's LSTM state buffers, swapped between input and
  output, both signatures take the encoder's output buffer) against `tdt_buffers=separate`
  (`TdtDecoder(separateSignatureBuffers = true)`: every signature on its own buffers, the encoder
  output and the states copied), S32's first 10 rows (F10) on the NPU; on the CPU (f32 stateful file)
  the separate form's text is checked against the shared form's.
- **The decoder alone** (`DecoderBufferTest`, a second hold): the app's `TdtDecoder` (tdt_fix) on
  B's CPU encoder outputs written into the encode signature's output buffer, three passes over the
  four files, on the CPU (f32 file, the token reference) and on the NPU with the app's buffers (with
  and without an encode run before each window) and with `tdt_buffers=separate`
  (`tools/asr-npu/decoder_compare.sh`: errors per run, token ids per window against the CPU's).
- **Harness.** The `bench` build of litert-samples speech_recognition (package `….npucheck`,
  `INSTRUMENT.md`), `BenchFrontActivity` in front (`require_top_app=false`: nothing is timed), W =
  `1995-1836-0004` once per AsrBenchTest process outside the scoring, WER by
  `tools/omni-eval/score.py` (Open ASR Leaderboard normalizer, corpus). No speed is read here.
- **Records.** `results/raw/2026-10-20-asr-npu-v1-s26-android/`: B `b-*.json` (each run's report),
  `b-compare.json`, `.load-logcat.txt`, `.logcat.log`; A / C `<tag>.jsonl`, `.load-logcat.txt`,
  `.logcat.log`, `.tokens.log` (NPU), `.events.tsv`, `.cmd`, probes; `summary/`, `SET-*.json`,
  `LOCK.json`, `setup.log`, `INSTRUMENT.md`, `instrument.patch`, `NOTES.md`, `SHA256SUMS`. The raw
  float outputs stay out of the record. Driver: `tools/asr-npu/`.
