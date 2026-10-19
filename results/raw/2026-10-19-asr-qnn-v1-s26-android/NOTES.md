# 2026-10-19 asr-qnn-v1, Galaxy S26 — arm A2: sherpa-onnx v1.13.8 + QNN (HTP), parakeet-ctc-0.6b, 30 s window

Definitions: `docs/asr-qnn-v1.md`. Tools: `tools/asr-qnn/`. Versions and sha256 of every file the phone ran:
`LOCK.json`; the phone's read-back of the pushed files and the two set chains: `SHA256SUMS`. One S26 hold,
17:33:55–17:48:07 JST; the Mac driver's lines: `progress.log`.

## Conditions
- Phone: Galaxy S26 SM-S942Q (RFGL80R6A6H), SM8850, Android 16 (BP4A.251205.006.S942QOPS1AZH9, patch 2026-08-05),
  USB powered, not charging (battery status 4), screen awake (`probe-*.json`).
- Runtime: sherpa-onnx v1.13.8 built from the tag's source (tree at 11afbd00, `tools/asr-qnn/build.sh`; android-24,
  NDK 28.2.13676358, c++_static). Its version strings come from the tag's checked-in `version.cc`:
  `sherpa-onnx-version` prints "Git SHA1: 8c8e275d", "Git date: Thu Sep 10 17:15:24 2026" (`sherpa-onnx-version.txt`).
  onnxruntime 1.28.2 (git 33ca962) is linked; the graph runs through the QNN API.
- QNN: QAIRT 2.40.0.251030 HTP libraries in the run dir's `lib/`, `ADSP_LIBRARY_PATH="<run dir>/lib;"`. At load the
  backend reports build ID v2.40.0.251030114326_189385, QNN core API 2.30.0, backend API 5.40.0, backend id 6
  (`debuginfo.stderr.log`, the plain CLI with `--debug=1`). Mapped after the load in every driver process:
  libQnnHtp.so, libQnnHtpV81Stub.so, libQnnSystem.so, libonnxruntime.so, /vendor/lib64/libcdsprpc.so (header
  `libs_mapped_after_load`). The QNN log's lines on stdout: "QnnDsp <W> Initializing HtpProvider" and
  "QnnDsp <W> m_CFBCallbackInfoObj is not initialized, return emptyList".
- Model: `sherpa-onnx-qnn-SM8850-binary-parakeet-ctc-0.6b-30s` (k2-fsa release asr-models-qnn-binary). Graph input
  `x` [1, 3000, 80] UFIXED_POINT_16 (scale 5.66595e-05, offset -41458), output `log_probs` [1, 375, 1025]
  UFIXED_POINT_16 (scale 0.00215588, offset -65535). Quantization (`quant_recipe` in every JSONL header): QNN
  post-training quantization with calibration inputs, weights 8-bit, activations 16-bit, bias 32-bit. CTC greedy search.
  `--num-threads=4` is passed; the QNN path does not read it.
- Process: started through `adb shell` under nohup (`device_run.sh`); every process: Cpus_allowed_list 0-7, cpuset
  line `4:cpuset:/`, cpu cgroup `/general` (JSONL headers `cpus_allowed` / `cpuset` / `cgroup`, `*.cgroup`, `*.cpus`).
- Sets: S32 (82 utterances, 626.36 s, chain 6ccb9d3c…, `SET-S32.json`), S4 (655, 4875.78 s, chain c83c07ed…,
  `SET-S4.json`); W = 1995-1836-0004 (33.91 s) as every process's warm-up, outside the timing and the scores.
- Thermal gate before each measured run (battery <= 36.0 C and Thermal Status 0, then every cpufreq ceiling at its
  maximum): both runs started without waiting. Battery 35.5 → 35.1 C over the burst run, 35.1 → 35.3 C over the
  sustained run, Thermal Status 0 at every probe, HAL AP 37.3–39.1 C.

## Numbers
| | burst, S32 (`a2-sherpa-qnn-ctc-30s-S32-burst.jsonl`) | sustained, S4 (`a2-sherpa-qnn-ctc-30s-S4.jsonl`) |
|---|---|---|
| utterances | 82 counted, 0 excluded, 0 retaken, 0 errors | 655, 0 missing, 0 hangs |
| RTF (Σ processing s / Σ audio s) | RTF_burst 0.1294 (81.06 / 626.36), RTFx 7.73 | 0.1305 (636.10 / 4875.78), RTFx 7.67 |
| median per-utterance RTF | 0.175 | 0.163 |
| processing s per utterance | 0.707–1.152, median 0.987 | 0.613–1.164 |
| largest ceiling fall | 4.9 % during the first utterance (policy6 4512000 of 4742400 kHz), 2.0 % during two more, none past 15 % | 7.3 % (policy6 4396800 of 4742400 kHz): an NPU arm's capped run, counted, marked |
| pacing waits | sum 44.75 s, median 0.501 s, max 1.908 s, 0 timed out | — |
| WER (leaderboard normalizer, corpus) | 8.55 % on S32 (S/D/I 64/13/68 of 1695 words; reference) | **8.11 %** (S/D/I 474/56/534 of 13,117 words, 0 empty) |
| truncated to 3000 frames | 1: 4507-16021-0047 (3496) | 3: 4507-16021-0047 (3496), 2094-142345-0008 (3165), 121-123859-0002 (3004) |
| VmHWM | 1,283,924 kB | 1,282,076 kB (1 s sampler) |
| load (recognizer constructor) | 642.0 ms (2nd model process) | 0.692 s ("recognizer init time") |

- Load: cold 659.4 ms (`smoke3-cold`, the first process after the push), warm 706.0 ms (`warm1`, the last process).
- Stage medians of the burst run (`stage_ms`): ReadWave 1.87 ms, CreateStream 0.17 ms, AcceptWaveform (features)
  16.66 ms, DecodeStream (normalization, the QNN graph, greedy search) 971.15 ms, GetResult 0.00 ms.
- The 82 S32 texts of the burst run equal the sustained run's texts of the same utterances (82 / 82).
- 361 of the 655 S4 hypotheses carry at least one insertion; hypotheses carry split or repeated word pieces
  (4507-16021-0047: "to tmorrow", "slandererer", "mis tfortune"). Why: not examined in this record.
- Not measured: energy.

## Files
- `a2-sherpa-qnn-ctc-30s-S32-burst.*` (burst, the driver), `a2-sherpa-qnn-ctc-30s-S4.*` (sustained, the CLI;
  `.jsonl` = `tools/asr-qnn/to_jsonl.py` over `.stdout.log` / `.stderr.log`), `smoke3-cold.*` and `warm1.*` (the
  driver, three and one utterances: load and the first look at the HTP), `debuginfo.*`: `.cmd` the command line,
  `.stderr.log` with the phone's clock per line, `.stdout.log` the QNN log (and the CLI's results), `.vmhwm.log` the
  1 s samples (VmHWM, VmRSS, threads, every policy's ceiling), `.ceil.log` every ceiling read of the burst run (a
  `wait` row carries the id of the utterance before that wait, as asr-burst-v1's log does),
  `.cpus` / `.cgroup` / `.exit` / `.rc` / `.pid` / `.done` / `.runner.log`.
- `summary/summary.json` (`tools/asr-qnn/summarize.py`), `summary/*.score.json` (`tools/omni-eval/score.py`).
- `probe-*.json` (hold-start, before / after each run, hold-end), `*.help.txt`, `sherpa-onnx-version.txt`.
- The Mac user name in paths is written `USER`.
