# asr-qnn-v1 — sherpa-onnx on the Qualcomm NPU (QNN HTP), Galaxy S26

What one arm of the 2026-10-19 speech-recognition sitting measures: sherpa-onnx with its Qualcomm NPU backend and
k2-fsa's prebuilt QNN context binary of NVIDIA's parakeet-ctc-0.6b, on a Galaxy S26 (SM8850). Raw records:
`results/raw/2026-10-19-asr-qnn-v1-s26-android/`. Tools: `tools/asr-qnn/`.

- **Runtime**: sherpa-onnx v1.13.8 (tag commit 11afbd00) built from source with `SHERPA_ONNX_ENABLE_QNN=ON
  SHERPA_ONNX_ENABLE_BINARY=ON ./build-android-arm64-v8a.sh` (`tools/asr-qnn/build.sh`; platform android-24, see
  LOCK.json). The release has no QNN executables. onnxruntime 1.28.2 is linked but the model graph runs through the
  QNN API (`sherpa-onnx/csrc/qnn`): the HTP backend `libQnnHtp.so`, the context loaded with `libQnnSystem.so`.
- **QNN SDK**: QAIRT 2.40.0.251030 (build id 251030114326_189385), the version the context binary was made with
  (the release notes and the build id inside `model.bin`). The phone gets `libQnnHtp`, `libQnnHtpPrepare`,
  `libQnnSystem`, `libQnnHtpV81Stub` (lib/aarch64-android) and `libQnnHtpV81Skel` (hexagon-v81/unsigned);
  `ADSP_LIBRARY_PATH` names their directory. They are not committed (Qualcomm's license).
- **Model**: `sherpa-onnx-qnn-SM8850-binary-parakeet-ctc-0.6b-30s` (release `asr-models-qnn-binary`): a context
  binary for SM8850 (HTP v81) with a fixed input of 3000 frames (30 s, 80 mel bins). Quantization (k2-fsa's export
  workflow): QNN post-training quantization with calibration inputs, 8-bit weights (the converter's default),
  16-bit activations, 32-bit bias. An input shorter than 30 s is padded with zeros after the feature
  normalization; a longer one is truncated to 3000 frames and sherpa prints `Truncate it to 3000 frames`.
  Decoding: CTC greedy search on the CPU. `--num-threads=4` is passed; the QNN path does not read it.
- **Sets**: LibriSpeech test-clean as in asr-sherpa-v1: S4 = every 4th manifest row (655 utterances, 4875.78 s,
  chain c83c07ed…), S32 = every 32nd row (82 utterances, every 8th row of S4; `SET-S32.json`), W = manifest row 1
  (`1995-1836-0004`, 33.91 s), outside both, the warm-up.
- **Burst form (S32)**: `tools/asr-qnn/burst_driver.cc`, one process: the recognizer built once, W once outside the
  timing, then each utterance after a wait of at least 0.5 s and until every cpufreq policy's `scaling_max_freq`
  equals its `cpuinfo_max_freq` (read every 200 ms, at most 120 s); the ceilings are read every 100 ms while it
  runs; an utterance during which one fell more than 15 % is run once more after they are back and 5 s, and past
  the line again it is excluded (counted). asr-burst-v1's rule, the same numbers. processing seconds = ReadWave →
  CreateStream → AcceptWaveform (features) → DecodeStream (normalization, the QNN graph, greedy search) →
  GetResult. RTF_burst = Σ processing seconds / Σ audio seconds over the counted utterances.
- **Sustained form (S4)**: `sherpa-onnx-offline-parallel --provider=qnn … --batch-size=1 --nj=1 --wav-scp=<W + S4>`,
  one process, asr-sherpa-v1's timing (the phone's clock on stderr lines). WER: the Open ASR Leaderboard normalizer,
  corpus WER (`tools/omni-eval/score.py` through `tools/asr-qnn/run_score.py`). Its RTF is an NPU arm's: a run whose
  CPU ceilings fell counts, marked with the largest fall (`methodology/fairness-rules.md`, cpu-cap-rule).
- **Load**: the `OfflineRecognizer` constructor (QNN backend and device, the context from the binary, the graph):
  cold = the first process after the push, warm = a later process. **Memory**: the process's VmHWM.
- **Not measured**: energy (manual cells).
