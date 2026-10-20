# asr-pr-v1 — the speech_recognition sample app's TDT decoder fix as a change on upstream main (LiteRT 2.3.0), run on the Galaxy S26

Why: asr-fix-v1 ran the two decoder changes behind a run argument on LiteRT 2.2.0. A pull request
puts them into the app's default path on upstream main, which pins LiteRT 2.3.0 and litert-gpu 2.3.0
(ead3948d); this runs that branch on the phone through the app's own pipeline.

- **The change** (google-ai-edge/litert-samples, branch `speech-recognition-tdt-decode-stop`, two
  commits on upstream e3be1469, `LOCK.json` `pr_branch`): (1) TdtDecoder's greedy loop moves into
  `TdtDecoder.greedyDecode` so that JVM tests can run it, unchanged; (2) with each window's features
  the pipeline passes `getNumOfValidSamples` (the samples up to the last non-zero one; FileAudioSource
  fills the rest of a short window with exact zeros) through `SpeechRecognizer.recognize(features,
  numOfValidSamples)`, and TdtDecoder stops before encoder frame min(maxTimeIndex, ceil(n / 8) + 4),
  n = floor(v / 160); after 10 non-blank tokens with duration 0 at one encoder frame it moves to the
  next. No switch: it is the app's default. The windows, their overlap, the merger, the mel and the
  models are the app's.
- **Build.** The PR branch plus one benchmark commit (branch `asr-bench-s26-pr`; `INSTRUMENT.md`,
  `instrument.patch`): asr-burst-v1's `bench` build type (not debuggable, `cmd package compile -m
  speed`), `BenchFrontActivity`, `AsrBenchTest` (MainActivity's file path at the PR head, timed), the
  30 s entry of the same model in `model_metadata.json`, 4 CPU threads, package `….prcheck`. LiteRT
  2.3.0 + litert-gpu 2.3.0 as the app pins them; the libraries in the APK are matched to those AARs.
- **Set.** LibriSpeech test-clean (WAV chain `c703709c…`). **S32** = rows 0, 32, 64, … = 82
  utterances, 626.36 s (chain `6ccb9d3c…`). **W** = row 1 `1995-1836-0004`, the warm-up, outside S32.
  **edge2** = `silence-2s` (32,000 zero samples) and `clip-0p8s` (W's first 12,800 samples), no
  reference text (`SET-edge.json`).
- **Runs.** `b-l4p` = CPU, 30 s windows, S32 under asr-burst-v1's burst pacing and retake rule.
  `e-l4p` = CPU, 30 s windows, edge2, back to back. `b-l5p` = GPU (FP32, the entry's setting), S32
  burst, when the sitting has room.
- **Lines set before the run.** b-l4p's text against asr-fix-v1's `b-l4f-litert-cpu-30s-fix-S32` (the
  same decoder change, LiteRT 2.2.0) on the same 82 ids: at least 78 identical, and WER at most 2.5 %.
  e-l4p: both rows end without an error. RTF_burst is recorded as this build's number; it is not set
  against asr-fix-v1's, which ran in another sitting.
- **Numbers.** WER (Open ASR Leaderboard normalizer, corpus, `tools/omni-eval/score.py`), S / D / I,
  empty hypotheses, the rows with an error; RTF_burst, the median utterance RTF, the excluded and
  retaken rows and the waits; load cold / warm; VmHWM; per window the valid samples, their feature
  frames, the time limit they give and the last time index the decoder emitted a token at.
- **Records.** `results/raw/2026-10-20-asr-pr-v1-s26-android/`: `<tag>.jsonl` (header, warm-up, one
  row per utterance, footer), `.vmhwm.log`, `.ceil.log`, `.cpufreq-host.tsv`, `.load-logcat.txt`,
  `.logcat.log`, `.events.tsv`, `.cmd`, probes, `summary/`, `LOCK.json`, `SET-*.json`,
  `setup.log`, `INSTRUMENT.md`, `NOTES.md`, `SHA256SUMS`. Driver: `tools/asr-pr/`.
