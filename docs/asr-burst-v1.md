# asr-burst-v1 — speech recognition one utterance at a time, each started at full CPU clocks

Why: on the Galaxy S26 a CPU load of more than about 3 s lowers the CPU ceilings
(`methodology/fairness-rules.md` §13), so a sustained run over hundreds of utterances measures the
phone's thermal cap more than the recognizer. A burst run starts every utterance at full ceilings
and keeps only the utterances during which no ceiling fell more than 15 %.

- **Set.** LibriSpeech test-clean (the asr-sherpa-v1 / asr-litert-app-v1 expansion, 2620 utterances,
  WAV chain `c703709c…`). **S32** = the manifest rows at index 0, 32, 64, … = 82 utterances,
  626.36 s, every other row of S16 (`SET-S32.json`: WAV chain `6ccb9d3c…`). S16 = rows 0, 16, 32, …
  (164 utterances, chain `a9b9e3b3…`) was the first set; at about 18 s per utterance with the waits
  and retakes it did not fit a 45 min sitting. **W** = row 1 `1995-1836-0004` (33.91 s, outside
  S4, S16 and S32), the warm-up.
- **Harness.** The instrumented test `AsrBenchTest` of the litert-samples `speech_recognition`
  benchmark build (`INSTRUMENT.md`): engine `litert` = the app's own file pipeline, engine `sherpa` =
  sherpa-onnx's release AAR through its Kotlin API. The app is the `bench` build type (not
  debuggable, `cmd package compile -m speed`); its window `BenchFrontActivity` (shown over the
  keyguard) is in front, and a run whose process is not the resumed top app stops before the load.
- **Process.** Build the model once (load, ms; cold = the first process after install / push, warm =
  a later one), transcribe W once outside the timing, then S16 in manifest order, one utterance at a
  time.
- **Pacing.** Before each utterance: at least 0.5 s after the previous one ended and every cpufreq
  policy's `scaling_max_freq` back at its `cpuinfo_max_freq` (read every 200 ms, at most 120 s, then
  start anyway and mark the row). The wait is recorded.
- **Time.** Per utterance, `SystemClock.elapsedRealtimeNanos` from reading the WAV to the last text
  (LiteRT: the app's file path; sherpa: `readWave` → `createStream` → `acceptWaveform` → `decode` →
  `getResult`).
- **Cap.** Every policy's ceiling is read every 100 ms while the utterance runs; fall = max over the
  policies of (1 − min / hw) × 100. Past 15 %: once more after the ceilings are back and 5 s; still
  past 15 %: the utterance is excluded and counted. The same rule for every arm, CPU, GPU or NPU.
- **Numbers.** RTF_burst = Σ processing seconds / Σ audio seconds over the counted utterances; the
  median utterance RTF; the excluded count; the waits; load cold / warm; VmHWM of the process (end
  and 1 s sampler). WER is taken from the S4 sustained runs; S16's WER is listed as a reference.
- **Text check.** Each utterance's text against the same utterance of the arm's S4 sustained run
  (sherpa: the CLI arm asr-sherpa-v1), identical or not. The parakeet-ctc-0.6b NPU arm has no S4
  sustained run: its WER is S16's.
- **Records.** `results/raw/2026-10-19-asr-burst-v1-s26-android/`: `<tag>.jsonl` (header, warm-up,
  one row per utterance with its waits, ceilings and attempts, footer), `.ceil.log`, `.vmhwm.log`,
  `.load-logcat.txt`, probes, `summary/`, `LOCK.json`, `NOTES.md`. Driver: `tools/asr-burst/`.
