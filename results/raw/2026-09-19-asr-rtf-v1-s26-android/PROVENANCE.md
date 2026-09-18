# 2026-09-19 ASR real-time factor, v1 — Galaxy S26 leg

Task family: `docs/asr-rtf-v1.md`; cells: the `android` rows of `matrices/asr-rtf-v1.cells`;
driver: `scripts/asr_rtf_android.py matrices/asr-rtf-v1.cells --campaign 2026-09-19-asr-rtf-v1-s26`
(sitting 1, 07:00:55–07:31:15 JST, all eight cells) and the same with `--backend cpu --pause 45
--base-cooldown 90` (sitting 2, 07:33:51–07:45:30, the four CPU cells; sitting 1's CPU captures
kept as `*_cpu.jsonl.attempt1`). Numbers and findings: `NOTES.md`. Every launch's merged
stdout/stderr stream is under `logs/`; the driver's own logs are `logs/driver_sitting1.log` /
`logs/driver_cpu_retake.log` and `runlog.txt`.

## Device

Samsung Galaxy S26 `SM-S942Q` (`m1q`, SoC `SM8850`), Android 16, security patch 2026-06-05,
adb serial `RFGL80R6A6H`, USB, screen on, charging over USB (battery 100 %, status full),
no CPU frequency cap (`scaling_max_freq` = `cpuinfo_max_freq`: 3,628,800 kHz × 6, 4,742,400 kHz × 2),
no `taskset`. Hand-over from the Qwen3-TTS session at 06:59 (its phone work ended 06:27, its
sample app force-stopped): battery 32.6 °C, thermal status 0. Gate before every launch:
thermal status 0 and battery ≤ 36.0 °C (`dumpsys thermalservice` / `dumpsys battery`), waits
logged; the temperatures before and after each launch are in `metrics.batteryTemp{Initial,Final}C`
and `provenance.deviceBefore/After`. No other adb client used the phone (checked before the
session; the sibling session confirmed by message it would not touch it).

## Instrument

The same LiteRT-LM `main` commit as the Mac leg, `1dadd00c2a2363f275e713cfebab5fa9b96c6226`
(`~/code/litert-lm-1dadd00c-wt`), built for the phone:
`ANDROID_NDK_HOME=~/Library/Android/sdk/ndk/28.2.13676358 bazelisk build --config=android_arm64
--enable_platform_specific_config //omni/asr:asr_runner`, bazel 7.6.1, 06:53:44–06:55:44 JST,
2,980 actions, exit 0 (`logs/bazel_asr_runner_android.log`). GPU libraries = the LFS objects of
`prebuilt/android_arm64/` at the same commit (`git lfs pull origin --include="prebuilt/android_arm64/*"`);
the engine loads `libLiteRtGpuAccelerator.so` (log: `RegisterAccelerator … name=LiteRT GPU`,
`Loaded OpenCL library with dlopen`, `Created OpenCL device`, `Initializing OpenCL-based API from graph`).

Staged on the phone under `/data/local/tmp/edge-llm-bench/asr/` (`bin/`, `models/`, `audio/`);
`SHA256SUMS` (copied here) is the run dir's:

| file | sha256 | bytes |
|---|---|---|
| `asr_runner` (ELF aarch64, PIE, not stripped) | `3a34eda23885ccfb7d8b741b2644c3436b8bf228336abdec4b4acce2645545d7` | 33,715,152 |
| `libLiteRtGpuAccelerator.so` | `88e716f4ff79970b377597fb4207e930dc4905bc23ddb08479cc3f317627274a` | 3,400,496 |
| `libLiteRtOpenClAccelerator.so` | `d9dd64c36f6e18661588e71cf6bad5860598e6ccd3a56dfb304c517f89ac609e` | 3,171,112 |
| `libLiteRtWebGpuAccelerator.so` / `libwebgpu_dawn.so` | `2777c137…` / `97772bf2…` | 3,203,888 / 19,695,320 |
| `libLiteRtTopKOpenClSampler.so` / `libLiteRtTopKWebGpuSampler.so` | `8e69e7d0…` / `23d584c4…` | 11,819,152 / 11,804,264 |
| `libGemmaModelConstraintProvider.so` | `f2aa38ce…` | 19,606,552 |
| `model_metadata.json` | `960747e5fe316e25fc1cfca378377c2131c763d92996b590ae5e524b5e5e6be1` | 3,575 |

Every launch (exact line in each record's `provenance.command`):
`cd …/bin && export LD_LIBRARY_PATH=…/bin && echo T0=$EPOCHREALTIME && ./asr_runner --model_name <name>
--metadata_path …/bin/model_metadata.json --model_path …/models/<file> --cache_dir …/models
--backend cpu|gpu --num_threads 4 --overlap_ratio 0.4 --text_merger_type timestamp
--audio_path …/audio/librispeech-dev-clean-1272-82s.wav 2>&1; echo EXIT=$? T1=$EPOCHREALTIME`.
`loadTimeSeconds` = `Starting` absl timestamp − T0, `asrProcessingSeconds` = `Finished` − `Starting`
(phone clock, µs); `asrFirstTextLatencyMS` = host-side arrival; `memoryPeakResidentMB` = `VmHWM`
polled through adb every 0.5 s.

## Models and audio

The same four files and tokenizers as the Mac leg (sha256 in `../2026-09-19-asr-rtf-v1-m4max-mac/PROVENANCE.md`),
pushed with `adb push` and re-hashed on the phone (`sha256sum`, `provenance.remoteModelSha256` = host sha256
for every cell). Stream: `librispeech-dev-clean-1272-82s.wav`, 1,317,359 frames, sha256 `052852e6cfea…`,
built by the driver from `evaldata/asr/librispeech-dev-clean-1272-82s/`.
