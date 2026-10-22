# asr-sigbuf-v1 — Galaxy S26 (SM-S942Q, SM8850): the speech_recognition sample's TdtDecoder on its own buffers

Definition: `docs/asr-sigbuf-v1.md`. The check build and what it adds: `INSTRUMENT.md`. Versions and
hashes: `LOCK.json`. Each section below states one check's facts, per build.

## Conditions

- Phone: Galaxy S26 `RFGL80R6A6H` (SM-S942Q, SM8850, Android 16, SDK 36), on USB power, the bench
  build's `BenchFrontActivity` in front during every `SigbufBenchTest` / `SigbufDecoderTest` run (the
  process in the top-app cpuset, CPUs 0-7).
- The change, in two forms (one commit on litert-samples main `367816da` each; the check builds of
  each form are built from the same check-build commit on top of main and on top of the change):
  - **form 1** (`9ca8adad`, `TdtDecoder.kt` blob `ecee3baa`): every signature on its own buffers on
    every accelerator. Runs `f1-*`.
  - **form 2** (`035a442e`, tree `40fba1f7`, `TdtDecoder.kt` blob `7ebe0efc`, `MainActivity.kt` blob `fd555ba1`;
    the commit to send, `b6beaafb`, has the same tree and the final message):
    `TdtDecoder(separateBuffers)`, which MainActivity sets on the NPU only; the CPU and GPU keep
    upstream main's shared buffers. Runs `f2-*`. Each run's header names `tdt_separate_buffers`.
  - main = upstream main's `TdtDecoder.kt` (blob `683e118c`), the same check build.
- Runtime: the app's LiteRT 2.3.0 + litert-gpu 2.3.0 on the CPU / GPU; on the NPU LiteRT 2.2.0 with the
  Qualcomm runtime of the LiteRT v2.2.0 release (`litert_npu_runtime_libraries.zip`,
  qualcomm_runtime_v81) and QAIRT 2.47.0's HTP libraries in the APK (the LiteRT v2.3.0 release carries
  no NPU runtime archive). Accelerator options as `LiteRtRunner` sets them (GPU FP32, NPU
  HIGH_PERFORMANCE).
- Files (Hub revision, bytes = the Hub's LFS sha256, read back on the phone after the copy):
  `litert-community/parakeet-tdt-0.6b-v3`@3ce205aa `…_5s_i8_stateful.tflite` (614,261,072 B,
  `334745b8…`), `…_5s_f32_stateful_Qualcomm_SM8850.tflite` (1,275,526,880 B, `e9edabe4…`),
  `…_5s_f32_stateful.tflite` (2,421,888,688 B, `8c1f06a9…`); `litert-community/parakeet-tdt_ctc-0.6b-ja`
  @1a2b23be `…_5s_i8.tflite` (607,908,368 B, `6ab11f31…`) and its `tokenizer.json`;
  `nvidia/parakeet-tdt-0.6b-v3`@541d1f99 `tokenizer.json`.
- Model I/O (`model_io.py`): the three v3 files have `encode` [1, 128, 500] → [1, 1024, 63], `decode`
  (tokens [1, 4]) → logits [1, 63, 4, 8198] and `decode_1` (token [1, 1]) → [1, 63, 1, 8198], LSTM
  states [2, 1, 640] × 2. The ja file has `encode` [1, 80, 500] → [1, 1024, 63] and `decode` (tokens
  [1, 64]) → [1, 63, 64, 3078], no `decode_1`.
- Set: LibriSpeech test-clean (`hf-audio/open-asr-leaderboard`@de79e57a, `tools/omni-eval/prep_librispeech.py`):
  S32 = rows 0, 32, 64, …; F20 = its first 20 rows (chain `c0741a6f…`, 311.815 s); W = `1995-1836-0004`
  (`SET-*.json`). The ja runs take the same English audio.
- Logs: `<tag>.log.txt` is each test's own log tap (complete for E / F and memory-handle / 6004 lines;
  counts in the run's end line or JSON). `<tag>.logcat.log` is what the phone's log still held after the
  run; in the three NPU app-path copies the per-step `Graph qnn_partition_N execution finished` lines
  are left out and counted at the end of the file (the full logs stay outside the record).
- `compare-f1.json` / `compare-f2.json` (`tools/asr-sigbuf/compare.py summary`): the identity, decoder-only
  and NPU-path facts per form, and each build's decode times.

## Hold 1 — form 1 (`f1-*`), 12:35:16–13:01:56 JST

Setup (`f1-setup.log`): the three debug APKs, the files read back on the phone (sha256 = the lock),
the bench + test APKs over them; `/data` free 110,619,828 kB before, 104,262,752 kB after.

The app's path (`SigbufBenchTest`, F20 after W, the v3 entry; per run 20 rows, 100 windows, no
error, no window capped; v3 runs wait before each row until every cpufreq ceiling is at its maximum):

| run | start–end | tokens | decode median ms | encode median ms | load ms | battery °C / thermal |
|---|---|---|---|---|---|---|
| f1-v3-cpu-main-r1 | 12:37:30–12:39:57 | 1550 | 71.86 | 58.82 | 860.5 | 33.1→35.0 / 0→0 |
| f1-v3-cpu-fix-r1 | 12:39:57–12:42:52 | 1550 | 70.84 | 58.82 | 913.9 | 35.0→36.1 / 0→0 |
| f1-v3-cpu-main-r2 | 12:42:53–12:46:09 | 1550 | 70.95 | 58.77 | 575.1 | 36.1→36.4 / 0→0 |
| f1-v3-cpu-fix-r2 | 12:46:10–12:49:43 | 1550 | 69.89 | 58.87 | 574.2 | 36.4→36.5 / 0→0 |
| f1-v3-gpu-main-r1 | 12:49:43–12:51:46 | 1585 | 312.50 | 0.36 | 5971.8 | 36.5→38.6 / 0→1 |
| f1-v3-gpu-fix-r1 | 12:51:46–12:53:08 | 1585 | 322.66 | 0.36 | 5868.5 | 38.6→40.5 / 1→1 |
| f1-v3-gpu-main-r2 | 12:53:09–12:55:29 | 1585 | 316.89 | 0.39 | 5975.7 | 40.5→40.9 / 1→2 |
| f1-v3-gpu-fix-r2 | 12:55:30–12:58:15 | 1585 | 326.12 | 0.38 | 5968.0 | 40.9→41.0 / 2→2 |

- Identity: on the CPU and on the GPU every window of the four runs has the same token ids and time
  indices (main-r1 against fix-r1, main-r2 and fix-r2).
- Pooled per build (two runs, 200 windows each): CPU main 70.99 ms, fix 70.14 ms; GPU main 313.55 ms,
  fix 323.49 ms. Every fix run started right after the main run of its pair (battery and thermal state
  per run in the table).
- On the GPU the encode call returns in 0.4 ms and the encoder's GPU time falls into the decode time
  (the decoder's first read waits for it), for both builds.

The decoder alone (`SigbufDecoderTest`, asr-npu-v1's four CPU encoder outputs, three passes = 12
windows, an encode run on zeros before each window):

- `f1-dec-cpu-f32-fix` (the f32 stateful file on the CPU, form 1's TdtDecoder): no error; 23 / 16 / 17
  / 0 tokens per window, every window ended. `f1-dec-cpu-f32-main` (main's TdtDecoder): the same token
  ids in 12 of 12 windows.
- `f1-dec-npu-fix` (the SM8850 file on the NPU, form 1's TdtDecoder): no error in 12 windows; the token
  ids of every window equal to `f1-dec-cpu-f32-fix`'s (12 of 12); the log tap counts no `Failed to find
  memHandle` line, no 6004, 16 `QnnMem_register started`, 16 `QnnMem_deRegister started`, 324
  finished graph executions; 13 E lines, all at start-up.
- `f1-dec-npu-main` (main's TdtDecoder on the same NPU build): 12 of 12 windows fail with
  `LiteRtException: Failed to invoke the compiled model` (the first window after 23 tokens, the
  others at their first step); the log tap counts 32 `Failed to find memHandle` lines and 36 lines with
  error 6004; the failed graph executions are `qnn_partition_2` (decode_1) once, in the first window,
  and `qnn_partition_1` (decode) eleven times, at the first step of each later window.

The NPU entry through the app's path (`SigbufBenchTest`, S32's first 3 rows, 630 tokens per window):

- `f1-v3-npu-app-fix`: no error in 3 rows; all 26 windows reach the 630-token stop (token 0 from the
  first step: the NPU encoder output is NaN, LiteRT#11038); the texts are empty; the log tap counts no
  `Failed to find memHandle` line and no 6004; a done marker, no crash buffer.
- `f1-v3-npu-app-main` (main's TdtDecoder): no error in 3 rows (the same 26 capped windows); the log tap
  counts 20 `Failed to find memHandle` lines (with `Cannot find memHandle` / `Failed to get context
  from memHandle`, near the end of the third row) and 65,106 `QnnMem_register started` /
  `QnnMem_deRegister started` each.
- Cleanup (`f1-cleanup.log`): the `.npu` pair uninstalled; `/data` free 104,274,760 → 108,035,972 kB.

## Hold 2 — form 2 (`f2-*`), 14:09:49–14:28:11 JST

The `.main` / `.fix` bench + test APKs of form 2 over the installed ones (`f2-hold2-update-apks.log`),
the `.npu` package set up again (`f2-hold2-setup.log`).

| run | start–end | separateBuffers | tokens | decode median ms | encode median ms | load ms | battery °C / thermal |
|---|---|---|---|---|---|---|---|
| f2-v3-cpu-main-r1 | 14:11:34–14:13:58 | (main) | 1550 | 69.13 | 58.13 | 1044.4 | 31.1→33.6 / 0→0 |
| f2-v3-cpu-fix-r1 | 14:13:59–14:16:07 | false | 1550 | 68.61 | 58.77 | 1000.5 | 33.6→35.2 / 0→0 |
| f2-v3-gpu-main-r1 | 14:16:07–14:17:44 | (main) | 1585 | 291.96 | 0.36 | 5950.6 | 35.2→38.2 / 0→1 |
| f2-v3-gpu-fix-r1 | 14:17:45–14:19:01 | false | 1585 | 316.77 | 0.36 | 5781.1 | 38.2→40.0 / 1→1 |
| f2-ja-cpu-main-r1 | 14:20:14–14:24:04 | (main) | 1386 | 1681.04 | 132.30 | 1740.1 | 41.2→41.2 / 2→2 |
| f2-ja-cpu-fix-r1 | 14:24:05–14:28:07 | false | 1386 | 1774.20 | 132.93 | 1728.3 | 41.2→41.4 / 2→2 |

- Identity: v3 on the CPU and on the GPU, 100 of 100 windows with the same token ids and time indices.
  ja on the CPU (98 windows): the same token ids in every window; both builds stop the same row,
  `1188-133604-0002`, after its fourth window with the same exception in the app's
  LevenshteinTokenMerger (`IllegalArgumentException: Requested element count -1 is less than zero.`
  at `LevenshteinTokenMerger.mergeTimestamps`, LevenshteinTokenMerger.kt:244; the stack is in each
  run's `.log.txt`), with the same tokens and text before it.
- On the GPU form 2's fix build runs main's code path (separateBuffers false); its run started right after
  the main run (battery and thermal state in the table).
- `f2-dec-cpu-f32-fix` (separateBuffers false): no error, 23 / 16 / 17 / 0 tokens per window.
  `f2-dec-npu-fix` (separateBuffers true): no error in 12 windows; the token ids of every window equal
  to `f2-dec-cpu-f32-fix`'s (12 of 12); no `Failed to find memHandle` line, no 6004, 16 / 16 QnnMem
  registrations / deregistrations, 324 finished graph executions, 13 E lines at start-up.
- `f2-v3-npu-app-fix` (separateBuffers true): no error in 3 rows; all 26 windows reach the 630-token
  stop; texts empty; no `Failed to find memHandle` line, no 6004; a done marker, no crash buffer.
- The sitting compared each fix run with its main run as it went and stopped at the ja CPU pair (its
  rule then counted any row with an error as a difference); the ja GPU pair had not run. Cleanup
  (`f2-hold2-cleanup.log`): the six packages uninstalled; `/data` free 104,195,980 → 110,472,032 kB.

## Hold 3 — form 2: MainActivity's own decoder and the ja GPU pair, 15:23:30–15:32:52 JST

The check build with `SigbufMainActivityTest` (commit `53031ee0` on form 2; `f2-hold3-mainact-setup.log`:
the v3 files into `.fix`, the SM8850 file into `.npu`, read back on the phone), then form 2's `.main`
/ `.fix` APKs with the ja files (`f2-hold3-setup.log`).

- `f2-mainact-npu` (`.sigbufcheck.npu`, LiteRT 2.2.0; header: `MainActivity.kt` blob `fd555ba1`,
  `TdtDecoder.kt` blob `7ebe0efc`, MainActivity RESUMED): MainActivity's `preparePipeline` loaded the
  v3 entry on the NPU in 605 ms; its LiteRtRunner holds a `TdtDecoder` with `separateBuffers` true.
  `4507-16021-0047` through the activity's own objects: 11 windows, each read up to the 630-token stop,
  no error, empty text; the log tap counts no `Failed to find memHandle` line, no 6004, 13 E lines at
  start-up, 6,941 finished graph executions; a done marker, no crash buffer.
- `f2-mainact-fix` (`.sigbufcheck.fix`, LiteRT 2.3.0): loaded on the CPU in 1,006 ms and on the GPU in
  6,406 ms; both `TdtDecoder`s with `separateBuffers` false. The same WAV: 11 windows, each sequence
  ended, no error, the English text ("Yesterday you were trembling for a health that is dear to
  you, …"), tokens per window 23 / 0 / 0 / 24 / 0 / 16 / 0 / 18 / 22 / 17 / 17 on both.

| run | start–end | separateBuffers | tokens | decode median ms | encode median ms | load ms | battery °C / thermal |
|---|---|---|---|---|---|---|---|
| f2-ja-gpu-main-r1 | 15:25:38–15:29:13 | (main) | 1351 | 1703.50 | 0.47 | 6470.8 | 33.3→37.2 / 0→0 |
| f2-ja-gpu-fix-r1 | 15:29:14–15:32:49 | false | 1351 | 1646.36 | 0.40 | 10738.2 | 37.2→40.6 / 0→2 |

- Identity: ja on the GPU, 100 of 100 windows with the same token ids and time indices, no error.
- Cleanup (`f2-hold3-cleanup.log`): the six packages uninstalled, none left; `/data` free
  107,161,220 → 110,534,876 kB. The stay-awake setting back to its value before the round (2).
