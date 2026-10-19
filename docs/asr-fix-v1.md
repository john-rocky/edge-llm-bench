# asr-fix-v1 — the speech_recognition sample app with its TDT decoder loop fixed (30 s windows; the NPU entry's 5 s)

Why: the sample app's `TdtDecoder` decodes every encoder frame of a window, the zero-padded tail of
a short window included (375 frames for the 30 s export), and has no cap on the tokens emitted at
one frame (a non-blank token with duration 0 does not advance the loop). NeMo bounds the decoding
by the encoded length and caps the symbols per frame (max_symbols 10).

- **The fix** (`TdtDecoder(fixDecodeLoop = true)`, run argument `tdt_fix=true`; default false = the
  app's loop): per window, v = the samples up to the last non-zero one (FileAudioSource fills the
  rest of a short window with exact zeros), n = floor(v / 160) feature frames, and the loop stops
  before encoder frame min(maxTimeIndex, ceil(n / 8) + 4); after 10 non-blank tokens at one encoder
  frame it moves to the next. The windows, their overlap, the merger, the mel, the models and their
  encoder and decoder are the app's (the 30 s entry: 30 s windows, 2 s overlap; the NPU entry: 5 s
  windows). `INSTRUMENT.md` lists the change; `instrument.patch` is the diff.
- **Set.** LibriSpeech test-clean (WAV chain `c703709c…`). **S4** = rows 0, 4, 8, … = 655
  utterances, 4875.776 s (chain `c83c07ed…`). **S32** = rows 0, 32, 64, … = 82 utterances, 626.36 s
  (chain `6ccb9d3c…`), the burst set. **S16** = rows 0, 16, 32, … = 164 utterances (chain
  `a9b9e3b3…`; its first 20 rows = the control below). **W** = row 1 `1995-1836-0004`, the warm-up,
  outside all three.
- **Harness.** asr-burst-v1's (`docs/asr-burst-v1.md`): the instrumented test `AsrBenchTest` of the
  `bench` build (not debuggable, `cmd package compile -m speed`), `BenchFrontActivity` in front and
  the run stopped before the load unless the process is the resumed top app, the model built once
  per process, W once outside the timing, the utterances in manifest order.
- **Runs.** `l4f` = CPU, tdt_fix true, S4 back to back (sustained). `b-l4f` / `b-l5f` = CPU / GPU,
  tdt_fix true, S32 under the burst pacing and cap rule of asr-burst-v1. `b-l3f` = NPU, the app's
  5 s entry (its file compiled ahead of time for SM8850), tdt_fix true, burst: S32 only after its
  first 10 rows (`smoke10`) pass a text gate set before the run (WER ≤ 36.25 % over those rows).
  `b-l4` = CPU, tdt_fix false, the first 20 rows of S16, burst: the control that this build without
  the fix gives the text the app's decoder gave in earlier rounds.
- **Numbers.** WER (Open ASR Leaderboard normalizer, corpus, `tools/omni-eval/score.py`), S / D / I,
  empty hypotheses, the rows with an error (from S4); RTF_burst, the median utterance RTF, the
  excluded rows and the waits (from S32); a sustained CPU run whose engine CPUs' ceiling fell more
  than 15 % has no RTF (`cpu-cap-rule`); load cold / warm; VmHWM of the process; per window the
  frames decoded (`window_decode_frames`), the network runs and the frames the cap moved past; the
  first and last 10 rows' per-window mel / encode / decode ms (the app's Kotlin / Java run on ART's
  JIT under instrumentation, timed after W).
- **Records.** `results/raw/2026-10-19-asr-fix-v1-s26-android/`: `<tag>.jsonl` (header, warm-up,
  one row per utterance, footer), `.vmhwm.log`, `.ceil.log` (burst runs), `.cpufreq-host.tsv`,
  `.load-logcat.txt`, `.logcat.log`, `.events.tsv`, `.cmd`, probes, `.tokens.log` (the NPU smoke's
  decoder tokens), `summary/`, `LOCK.json`, `SET-*.json`, `setup*.log`, `INSTRUMENT.md`,
  `NOTES.md`, `SHA256SUMS`. Driver: `tools/asr-fix/`.
