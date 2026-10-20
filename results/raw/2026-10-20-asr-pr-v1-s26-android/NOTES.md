# 2026-10-20 asr-pr-v1 — Galaxy S26, the speech_recognition sample app's TDT decoder change as a branch on upstream main (LiteRT 2.3.0): CPU with 30 s windows

Definition: `docs/asr-pr-v1.md`. The app: the PR branch and the benchmark commit on top
(`INSTRUMENT.md`, `instrument.patch`). Versions and hashes: `LOCK.json`. Sets: `SET-S32.json`,
`SET-edge.json`. Driver: `tools/asr-pr/run_pr_s26.sh`.

## Conditions

- Phone: Galaxy S26 SM-S942Q (RFGL80R6A6H), SM8850, Android 16, on USB power, the screen kept on
  (`svc power stayon usb`, the setting put back after the sitting), under the shared S26 hold
  (keeper `asr_pr_s26`).
- App: google-ai-edge/litert-samples `speech_recognition`, branch `speech-recognition-tdt-decode-stop`
  (upstream `e3be1469` + `67415211` + `fb3fb51f`, tree `6389b2c4…`) with the benchmark commit
  `8b9f5590` (branch `asr-bench-s26-pr`): package `com.google.ai.edge.examples.asr.prcheck`, the
  `bench` build type (not debuggable, `cmd package compile -m speed -f` after install). LiteRT 2.3.0
  and litert-gpu 2.3.0 as the app pins them: in the APK `libLiteRt.so` = `litert-2.3.0.aar`,
  `libLiteRtClGlAccelerator.so` = `litert-gpu-2.3.0.aar`, `liblitert_jni.so` = `litert-api-2.3.0.aar`,
  byte for byte (`LOCK.json` `native_libs_in_bench_apk`). CPU = 4 threads (`CpuOptions`).
- Model: the app's `parakeet-tdt-0.6b-v3-30s` entry (benchmark commit) =
  `mlboydaisuke/Parakeet-TDT-0.6B-v3-LiteRT@af580dff` `parakeet_tdt_0.6b_v3_30s_i8_stateful.tflite`
  (629,689,824 B, sha256 `378935f8…`, the Hub's LFS sha256), tokenizer
  `nvidia/parakeet-tdt-0.6b-v3@541d1f99` `tokenizer.json` (sha256 `bd321b09…`); 30 s windows, 2 s
  overlap (the app's file path).
- Decoder: the PR's `TdtDecoder` (no switch): each window stops before encoder frame
  min(375, ceil(n / 8) + 4), n = floor(v / 160), v = the window's samples up to its last non-zero
  one (`getNumOfValidSamples`, passed by the pipeline as MainActivity passes it); at most 10
  non-blank tokens with duration 0 at one encoder frame.
- In front: `BenchFrontActivity` (shown over the keyguard); a run whose process is not the resumed
  top app stops before the load.
- Before each run: battery ≤ 36.0 °C, thermal status 0 and every CPU ceiling at its maximum, waited
  for at most 15 minutes (`cool`).
- Not measured: energy.

## Sittings

One hold of the S26 on 2026-10-20 (JST): 13:00:02–13:28:47 (setup, e-l4p, b-l4p). At the hold the
phone was warm from the sitting before it (battery 42.1 °C, thermal status 2, CPU ceilings −50.8 %
and −63.2 %; uptime 396,742 s); e-l4p's `cool` reached its line after 652 s, b-l4p's after 83 s
(each run's `.cmd`).

## Results

Both runs: BenchFrontActivity resumed and the process in `4:cpuset:/top-app` with
`Cpus_allowed_list` 0-7 from the load to the last row (`processes[].process_state` and the sampler,
`.vmhwm.log`; its first line in each process, before the front window, reads
`4:cpuset:/foreground` 0-5), `debuggable` false, dexopt `speed/cmdline` for the app and the test,
and ART's `ClassLoaderContext … mismatch` lines in the load logs (INSTRUMENT.md, "Compiled code
under instrumentation"). WER = the Open ASR Leaderboard normalizer, corpus WER
(`tools/omni-eval/score.py`). Per-run summaries: `summary/<tag>.summary.json` (and `.score.json`).

### e-l4p: CPU, 30 s window, the edge inputs (`e-l4p-litert-cpu-30s-pr-edge2`)

- One process (cold load 576.7 ms; W 2.755 s). 2 rows, **no error**.
- `silence-2s` (32,000 zero samples): v = 0, n = 0, time limit 4; no token (text empty); per window
  mel 559.8 ms, encode 268.0 ms, decode 20.4 ms.
- `clip-0p8s` (W's first 12,800 samples): v = 12,800, n = 80, time limit 14; no token (text empty);
  mel 590.4 ms, encode 272.7 ms, decode 156.0 ms.
- W (the warm-up, two windows): v = 480,000 and 94,557, n = 3000 and 590, last token at time index
  372 and 72 (limits 375 and 78).
- VmHWM 2,104,172 kB. This run checks that the edge inputs end without an error; its times are not
  a number of this record (the summary's `sustained` block is the tool's default for pace none).

### b-l4p: CPU, 30 s window, S32 burst (`b-l4p-litert-cpu-30s-pr-S32`)

- S32 in one process (warm load 574.2 ms; W 2.758 s; launched 13:13:00, done 13:28:42). 82 rows,
  no error, all counted; 1 retaken (`4507-16021-0047`: the first attempt fell 28.3 %, the retake
  10.1 %, the same text), none excluded. **RTF_burst 0.1551** = 97.147 s / 626.36 s; median
  utterance RTF 0.19976.
- Waits: median 14.04 s, max 33.03 s, sum 770.4 s, no timeout. Fall during an utterance: first
  attempts median 2.8 %; counted attempts at most 11.7 %.
- **WER 1.59 %** (S / D / I 21 / 5 / 1 over 1,695 words), no empty hypothesis.
- Text: identical to asr-fix-v1's `b-l4f-litert-cpu-30s-fix-S32` (the same decoder change on LiteRT
  2.2.0, behind its run argument) on all 82 ids (82 exact). The lines set before the run: at least
  78 of 82 identical, WER at most 2.5 %.
- Decoder: 83 windows; 82 stopped before time index 375 (the full first window of
  `4507-16021-0047` decoded all 375). Time limit per window (computed from the recorded n): mean
  98.86, median 78. No window has a token at or past its limit.
- Per window (median): mel 586.6 ms, encode 263.7 ms, decode 277.1 ms. First 10 rows (the longest,
  11 windows) / last 10 (the shortest, one window each): mel 600.9 / 573.7 ms, encode 265.1 /
  262.8 ms, decode 602.4 / 160.7 ms.
- VmHWM 2,088,352 kB. The lowest CPU ceilings the sampler saw during the run (waits included):
  policy0 −20.1 %, policy6 −39.3 %.

### Registration (both runs, `.load-logcat.txt`)

`RegisterAccelerator … name=CpuAccelerator`, `XNNPACK CPU accelerator registered`; XNNPACK took
encode 1691 / 1838 nodes (249 partitions), decode 161 / 163, decode_1 61 / 63, and 120
`odml.group_norm` subgraphs 14 / 14. The GPU accelerator library registers (`Dynamically loaded GPU
accelerator(libLiteRtClGlAccelerator.so) registered`, `RegisterAccelerator … name=LiteRT GPU`); the
NPU registry logs `could not be loaded and registered: kLiteRtStatusErrorNotFound` (no NPU runtime
in this APK). The model is compiled for the CPU.

### b-l5p: GPU, 30 s window: not run

Defined in the driver and `docs/asr-pr-v1.md`; the sitting had 12 minutes left after b-l4p, not
enough for an S32 run.
