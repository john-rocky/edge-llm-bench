# 2026-10-19 parakeet-tdt-0.6b-v3, one utterance at a time at full CPU clocks — Galaxy S26 (SM-S942Q, SM8850, Android 16)

Definition: `docs/asr-burst-v1.md`. What was changed in the app and what each number covers:
`INSTRUMENT.md` (+ `instrument.patch`). Versions and hashes: `LOCK.json`. Set: `SET-S16.json`.
Each arm below is reported on its own; the records carry no comparison between them.

## Conditions

- Phone: Galaxy S26 RFGL80R6A6H, USB-connected, screen kept on (`svc power stayon usb`), the benchmark
  build's window (`BenchFrontActivity`, shown over the keyguard) in front for the whole run; each
  record's header says whether it was resumed and where the process ran (`Cpus_allowed_list`,
  cpuset), each row where the utterance started.
- App: litert-samples `speech_recognition` at `d15f8ae9` + the benchmark commits (LOCK.json `app`),
  build type `bench` (release settings, not debuggable, debug key), compiled with
  `cmd package compile -m speed -f` (the compiler filter in every header). The AOT code is not used:
  ART discards both odex files at process start (`ClassLoaderContext … mismatch` in each
  `<tag>.load-logcat.txt`; the instrumentation puts the test APK on the app's class path), and the
  process maps only the two `base.vdex` (header `oat_files_mapped`). The Kotlin / Java parts run on
  the JIT (not debuggable), warmed up by W before the timed utterances; see each LiteRT arm's
  first / last 10 utterances below. LiteRT 2.2.0 with the
  Qualcomm runtime `qualcomm_runtime_v81` + QAIRT 2.47.0 in the APK; sherpa-onnx v1.13.8's release
  AAR (ONNX Runtime 1.28.2). CPU threads 4 on every arm (LiteRT `CpuOptions`, sherpa-onnx
  `numThreads`); GPU precision FP32 and NPU HTP mode HIGH_PERFORMANCE (the app's defaults for this
  model).
- Models: `litert-community/parakeet-tdt-0.6b-v3`@3ce205aa `parakeet_tdt_0.6b_v3_5s_i8_stateful.tflite`
  (CPU, GPU) and `parakeet_tdt_0.6b_v3_5s_f32_stateful_Qualcomm_SM8850.tflite` (NPU, AOT);
  `mlboydaisuke/Parakeet-TDT-0.6B-v3-LiteRT`@af580dff `parakeet_tdt_0.6b_v3_30s_i8_stateful.tflite`;
  k2-fsa `sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8` (encoder / decoder / joiner int8, tokens);
  for the CTC arm `litert-community/parakeet-ctc-0.6b`@e3c5b655
  `parakeet_ctc_0.6b_5s_f32_Qualcomm_SM8850.tflite` (NPU, AOT) with `nvidia/parakeet-ctc-0.6b`@ad09ba1c
  `tokenizer.json` (the app's `parakeet-ctc-0.6b` entry). The CTC arm has no S4 sustained run, so
  its WER is S16's (164 utterances); the other arms' WER is in the S4 records.
- Set: LibriSpeech test-clean S32 (82 utterances, 626.4 s; `SET-S32.json`), the warm-up utterance W
  once per process before it, manifest order, one process per run (a run stopped at the end of a
  sitting continues in a later process from its first utterance without a row; its records say so).
  The first set was S16 (164 utterances, `SET-S16.json`); at about 18 s per utterance (waits and
  retakes included) it did not fit a 45 min sitting, and the set became S32, every other row of S16.
  The sherpa-onnx arm's first S16 run (`b-a1-sherpa-cpu-S16.*`) was stopped after 12 utterances; its
  6 rows of S32 count, each processed after W in a warm process, and `b-a1-sherpa-cpu-S32` starts
  after them.
- Each run starts cool (battery ≤ 36.0 °C, thermal status 0, every CPU ceiling at its maximum, at
  most 15 min of waiting); each utterance starts at full ceilings (the burst rule of the
  definition); `<tag>.probe-before.json` / `-after.json` hold the device state.

## Results

Every run below: BenchFrontActivity resumed, the process in `4:cpuset:/top-app` with
`Cpus_allowed_list` 0-7 from the load to the last row (each row's cpuset and CPUs), `debuggable`
false, dexopt `speed/cmdline` for the app and the test, the odex not loaded (above). Per-arm
summaries: `summary/<tag>.summary.json` (and `.score.json`).

### sherpa-onnx v1.13.8 AAR, CPU, 4 threads (B-A1: `b-a1-sherpa-cpu-*`)

- S32 = the S16 run's first 6 rows of S32 (`b-a1-sherpa-cpu-S16`, stopped after 12 rows when the set
  changed) + `b-a1-sherpa-cpu-S32` (76 rows, started after `3575-170457-0026`); every row after W in
  a warm process. 82 rows: 81 counted, 1 excluded (its retake still fell 23.1 %), 5 retaken.
- RTF_burst 0.03188 = 19.505 s of processing over 611.73 s of audio (the 81 counted rows;
  `summary/b-a1-sherpa-cpu-S32.summary.json`), median utterance RTF 0.03197.
- Waits before an utterance: median 0.504 s, max 35.5 s, sum 240.9 s, no timeout. The ceiling's
  fall during a first attempt: median 0.0 %, past 15 % in 5 of 82 (at most 18.6 %); the falls were on
  policy6 (cpu 6-7).
- Stages, median per utterance: `decode` (encoder + TDT greedy search) 187.0 ms, `accept_waveform`
  (features) 8.2 ms, `readWave` 1.6 ms, `createStream` and `getResult` under 0.2 ms; Σ decode
  19.0 s of the 19.5 s.
- Load: cold 1118.9 ms (the first process after install, `b-a1-sherpa-cpu-smoke10`), warm
  1093.7 / 1116.4 / 1116.4 / 1115.5 ms (the S16, S32, warm1 and cfg1 processes).
- VmHWM (sampler and end): 1,887,816 kB for the S16 run, which decoded S32's longest utterance
  (34.955 s); 1,646,844 kB for the S32 run (its longest 16.1 s after W); 1,900,484 kB for the 10-row
  smoke; 1,865,460 kB for warm1 (W + the 34.955 s row). The processes that decoded the 34.955 s row
  peaked at 1.86-1.90 GB, the one that did not at 1.65 GB.
- Text against the CLI arm's S4 run (asr-sherpa-v1, `sherpa-onnx-offline-parallel`, same model and
  ONNX Runtime): 79 of 82 rows identical; 3 differ in one word each — `5105-28241-0001` "Count" /
  "count", `1284-1180-0017` "At" / "at", `5639-40744-0015` "Rodolfo," / "Rodolpho," (this run / the
  CLI). The cause was not traced. WER over S32 (a reference; the lane's WER is S4's): 1.59 %.
- Runtime witnesses: `VersionInfo` = sherpa-onnx 1.13.8, Git 11afbd00, ONNX Runtime 1.28.2; the
  process mapped `libonnxruntime.so` and `libsherpa-onnx-jni.so` only (no LiteRT library).

### LiteRT GPU, 30 s window, FP32 (B-L5: `b-l5-litert-gpu-30s-*`)

- S32 in one process: 82 rows, all counted, none retaken or excluded. RTF_burst 0.32032 = 200.637 s of
  processing over 626.36 s of audio; median utterance RTF 0.41062.
- Waits: median 21.9 s, max 77.2 s, sum 1889.8 s, every utterance over 1 s, no timeout. The fall
  during an utterance: median 4.9 %, at most 11.7 %; the ceilings fell after each utterance and the
  next one waited for them.
- Per window (median): mel 601.9 ms, `recognize()` (encode) 0.66 ms, decode 1760.2 ms. On this path
  `recognize()` returns before the encoder's GPU work is read back; the time shows in the decoder's
  first reads (the cause not traced further).
- Registration (`b-l5-litert-gpu-30s-S32.load-logcat.txt`): `RegisterAccelerator … name=LiteRT GPU`
  (`libLiteRtClGlAccelerator.so`), encode 1838 / 1838, decode 163 / 163 and decode_1 63 / 63 nodes
  on the `LITERT_CL` delegate (one partition each). The process mapped `libLiteRt.so`,
  `libLiteRtClGlAccelerator.so`, `liblitert_jni.so`, `libtokenizer_jni.so`.
- Load: cold 7469.4 ms, warm 7412.1 ms (warm1, a later sitting). Both processes logged the
  delegate's `Initializing OpenCL-based API from graph` for the three signatures and no program
  cache line.
- VmHWM 1,926,184 kB (end and sampler).
- WER over S32 (a reference; no S4 sustained run of this arm exists in asr-litert-app-v1): 1.47 %
  (S / D / I 18 / 6 / 1 of 1695 words).

### LiteRT CPU, 30 s window, int8 (B-L4: `b-l4-litert-cpu-30s-*`)

- S32 in two processes: the first 46 rows (stopped at a sitting's deadline, no footer), then the
  other 36 in a later sitting (`start_after` `8463-294828-0029`; the `.resume1` probes). 82 rows,
  all counted, none retaken or excluded. RTF_burst 0.21022 = 131.674 s / 626.36 s; median utterance
  RTF 0.2692.
- Waits: median 15.6 s, max 39.1 s, sum 1355.5 s. Fall during an utterance: median 2.0 %, at most
  8.5 %.
- Per window (median): mel 596.0 ms, encode 261.3 ms, decode 710.2 ms.
- Registration: `XNNPACK CPU accelerator registered`; XNNPACK took encode 1691 / 1838 nodes (249
  partitions), decode 161 / 163, decode_1 61 / 63.
- Load: cold 954.4 ms (first process), warm 804.9 ms (the resumed process), 585.8 ms (warm1; an
  earlier warm1, 585.3 ms, is kept as `.attempt1`). VmHWM 2,093,932 kB (first process, sampler) and
  2,097,436 kB (second, end).
- Text against the asr-litert-app-v1 L4 S4 sustained run: the 69 rows that run has are identical;
  13 S32 ids are not in it. WER over S32 (a reference): 1.95 %.

### LiteRT NPU, 5 s window, parakeet-ctc-0.6b (B-L6: `b-l6-litert-npu-ctc-5s-*`): runs, transcribes nothing usable

- The app's own `parakeet-ctc-0.6b` entry (CTC decoder, the transposed mel), its SM8850 AOT file on
  the NPU. **The text check fails, so the run is not a measurement** (methodology/fairness-rules.md
  §12): of the 82 rows 44 are empty and the other 38 read `t`; every 5 s window decoded to 1-3 tokens;
  W read `t` too; WER over S32 100.0 %. The run logged no error (no QNN or LiteRT error line, no
  failed row). The cause was not traced: the same entry's int8 model on the CPU was not run through
  the app, which would separate the NPU file and its execution from the app's CTC path. The numbers
  below are the run's, kept as recorded.
- S32 in one process: 82 rows, none retaken or excluded by the burst rule. Σ 23.369 s of processing
  over 626.36 s of audio (0.03731); median utterance 0.03771.
- Waits: median 0.50 s, max 19.7 s, sum 118.0 s. Fall during an utterance: median 0.0 %, at most
  4.9 %.
- Per window (median): mel 95.0 ms, `recognize()` (encoder on the NPU) 38.2 ms, CTC decode 0.65 ms.
- Registration (`b-l6-litert-npu-ctc-5s-smoke3.load-logcat.txt`, the same in the S32 run):
  `RegisterAccelerator … name=NpuAccelerator`, `NPU accelerator registered`, LiteRT's
  `libLiteRtDispatch_Qualcomm.so` loaded from the app's library dir, the QNN HTP backend, and
  `Replacing 1 out of 1 node(s) with delegate (DispatchDelegate) node`. The Qualcomm `fastrpc` layer
  logs a few `Permission denied` lines (log watchers, `open_shell`); the runs went on.
- Load: cold 887.6 ms (smoke3, the first process of this model), warm 862.6 ms (S32), 356.5 ms
  (warm1). VmHWM 1,512,804 kB (S32), 1,725,860 kB (warm1; one row after W).
- No S4 sustained run exists for this model; its WER is S32's: 100.0 %.

### LiteRT CPU, 5 s window, int8 (B-L1: `b-l1-litert-cpu-5s-*`)

- S32 in one process: 82 rows, all counted, none retaken or excluded. RTF_burst 0.05604 =
  35.100 s / 626.36 s; median utterance RTF 0.05703.
- Waits: median 0.504 s, max 40.9 s, sum 350.5 s. Fall during an utterance: median 0.0 %, at most
  14.2 %.
- Per window (median): mel 124.1 ms, encode 52.6 ms, decode 55.7 ms; 51 windows decoded to no
  token.
- Registration: `XNNPACK CPU accelerator registered`; XNNPACK took encode 1643 / 1790 nodes (249
  partitions), decode 161 / 163, decode_1 61 / 63.
- Load: cold 971.5 ms, warm 570.7 ms (warm1). VmHWM 1,555,704 kB.
- Text against the asr-litert-app-v1 L1 S4 sustained run: 82 of 82 identical. WER over S32 (a
  reference): 15.28 %.

### LiteRT GPU, 5 s window, FP32 (B-L2: `b-l2-litert-gpu-5s-*`)

- S32 in one process: 82 rows, all counted, none retaken or excluded. RTF_burst 0.12247 =
  76.713 s / 626.36 s; median utterance RTF 0.12494.
- Waits: median 0.502 s, max 4.1 s, sum 44.8 s. Fall during an utterance: median 0.0 %, at most 2.0 %.
- Per window (median): mel 121.3 ms, `recognize()` 0.57 ms, decode 315.1 ms (as in B-L5, the
  encoder's GPU time shows in the decoder's first reads); 46 windows decoded to no token.
- Registration: `RegisterAccelerator … name=LiteRT GPU`; encode 1790 / 1790, decode 163 / 163,
  decode_1 63 / 63 nodes on `LITERT_CL`.
- Load: cold 5863.6 ms, warm 5790.8 ms (warm1; the same OpenCL initialization from the graph in
  both). VmHWM 1,635,480 kB. The battery went from 35.8 °C to 40.4 °C over the run (thermal status
  0 → 1).
- No S4 sustained run of this arm exists in asr-litert-app-v1: no text check. WER over S32 (a
  reference): 13.98 %.

### The JIT after W (LiteRT arms)

Per-window medians (ms) of the set's first 10 utterances (the longest: 195.1 s, 63 windows of 5 s or
11 of 30 s) and its last 10 (the shortest: 24.2 s, one window each), each process warmed by W:

| arm | mel first / last | encode first / last | decode first / last |
|---|---|---|---|
| B-L1 CPU 5 s | 127.7 / 114.3 | 52.2 / 58.9 | 63.9 / 41.3 |
| B-L2 GPU 5 s | 112.3 / 136.5 | 0.58 / 0.69 | 358.1 / 270.9 |
| B-L4 CPU 30 s | 606.3 / 593.3 | 263.7 / 261.4 | 851.3 / 642.0 |
| B-L5 GPU 30 s | 607.8 / 596.8 | 0.75 / 0.68 | 2012.5 / 1584.9 |
| B-L6 NPU 5 s CTC | 92.9 / 114.8 | 37.5 / 39.0 | 0.66 / 0.61 |

From the first ten to the last ten, the mel step (jLibrosa, Java on the JIT) moves by −10.5 % (B-L1),
+21.6 % (B-L2), −2.2 % (B-L4), −1.8 % (B-L5) and +23.6 % (B-L6), and the encoder step by +12.7 %,
+19.3 %, −0.9 %, −9.9 % (0.07 ms) and +3.9 %: no common direction. The decode step is shorter on the
last ten's windows in every arm (not traced; those windows hold the shortest utterances).

### LiteRT NPU, 5 s window, TDT (B-L3): not run

The asr-litert-app-v1 sitting's NPU smoke (`results/raw/2026-10-19-asr-litert-app-v1-s26-android/
l3-litert-npu-5s-smoke3.*` and its NOTES) loaded the NPU path and then wrote no row in 10 min on its
first utterance; the restarted process stalled the same way on the next one, the merger logging
`decode: tokenId=0, timestamp=0` about every 12 ms: the decoder emits token 0 with duration 0 and
never leaves frame 0 (the app's `TdtDecoder` has no cap on symbols per frame). This build has the
same decoder, so the arm was not run.
