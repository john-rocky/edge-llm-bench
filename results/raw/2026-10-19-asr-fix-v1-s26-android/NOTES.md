# 2026-10-19 asr-fix-v1 — Galaxy S26, the speech_recognition sample app with its TDT decoder loop fixed: CPU with 30 s windows, an NPU smoke with 5 s windows

Definition: `docs/asr-fix-v1.md`. The change to the app: `INSTRUMENT.md`, `instrument.patch`. Versions
and hashes: `LOCK.json`. Sets: `SET-S4.json`, `SET-S16.json`, `SET-S32.json`. Driver:
`tools/asr-fix/run_fix_s26.sh`.

## Conditions

- Phone: Galaxy S26 SM-S942Q (RFGL80R6A6H), SM8850, Android 16, on USB power, the screen kept on
  (`svc power stayon usb`, the setting put back after the sitting), under the shared S26 hold
  (keeper `asr_fix_s26`).
- App: package `com.google.ai.edge.examples.asr.burstfix`, the `bench` build type (not debuggable,
  `cmd package compile -m speed -f` after install), LiteRT 2.2.0. CPU = 4 threads, the app's 30 s
  entry, model `mlboydaisuke/Parakeet-TDT-0.6B-v3-LiteRT@af580dff`
  `parakeet_tdt_0.6b_v3_30s_i8_stateful.tflite` (629,689,824 B, sha256 `378935f8…`). NPU =
  `Accelerator.NPU`, the app's 5 s entry `parakeet-tdt-0.6b-v3`, HTP performance mode
  HIGH_PERFORMANCE (the entry's setting), model `litert-community/parakeet-tdt-0.6b-v3@3ce205aa`
  `parakeet_tdt_0.6b_v3_5s_f32_stateful_Qualcomm_SM8850.tflite` (compiled ahead of time for SM8850,
  1,275,526,880 B, sha256 `e9edabe4…`; on the phone `files/parakeet-tdt-0.6b-v3/model_npu.tflite`),
  the Qualcomm runtime libraries inside the APK (`LOCK.json`). Tokenizer for both
  `nvidia/parakeet-tdt-0.6b-v3@541d1f99` `tokenizer.json` (sha256 `bd321b09…`). No GPU run.
- In front: `BenchFrontActivity` (shown over the keyguard); a run whose process is not the resumed
  top app stops before the load.
- Before each run: battery ≤ 36.0 °C, thermal status 0 and every CPU ceiling at its maximum, waited
  for at most 15 minutes (`cool`).
- Not measured: energy.

## Sittings

Three holds of the S26 on 2026-10-19 (JST): 18:20:34–19:01:50 (setup, the control, l4f's first
494 rows), 21:56:36–22:34:31 (the NPU model added, b-l3f smoke10, l4f's other 161 rows),
23:02:36–23:23:19 (b-l4f). No reboot between them (uptime 329,573 s at the first hold, 346,495 s
at the third). The phone was warm from earlier sittings at the first two holds (CPU ceilings −45 %
to −66 %, thermal status 1–2); each run's `cool` line is in its `.cmd`.

## Results

Every run below: BenchFrontActivity resumed and the process in `4:cpuset:/top-app` with
`Cpus_allowed_list` 0-7 from the load to the last row (`processes[].process_state` and the
sampler, `.vmhwm.log`; its first line in each process, before the front window, reads
`4:cpuset:/foreground` 0-5), `debuggable` false, dexopt `speed/cmdline` for the app and the test,
no `.odex` mapped (`oat_files_mapped`: the two `base.vdex`, and in three of the five processes —
not the first one after each install — also the app's `cache/oat_primary/arm64/base.art`), and
ART's `ClassLoaderContext … mismatch` lines in every run's load log (INSTRUMENT.md, "Compiled code
under instrumentation"). WER = the Open ASR Leaderboard normalizer, corpus WER
(`tools/omni-eval/score.py`). Per-run summaries: `summary/<tag>.summary.json` (and `.score.json`).

### Control: CPU, 30 s window, tdt_fix false (`b-l4-litert-cpu-30s-off-first20`)

- The first 20 rows of S16 under the burst pacing, one process (cold load 945.8 ms; `cool` ok after
  406 s). 20 rows, no error, none retaken or excluded. Waits: median 18.66 s, max 36.44 s, no
  timeout. Fall during an utterance at most 8.5 %.
- Text: identical to asr-litert-app-v1's `l4-litert-cpu-30s-S4` on all 20 ids, and to
  asr-burst-v1's `b-l4-litert-cpu-30s-S32` on the 10 of them it has (the line set before the run:
  18 of 20). With `tdt_fix=false` this build gives the text the app's decoder gave in those records.
- Decoder: every window (21) decoded all 375 frames; no frame capped; no empty hypothesis.
- Per window (median): mel 605.3 ms, encode 261.9 ms, decode 844.8 ms. Σ processing 35.761 s over
  377.46 s of audio; WER over the 20 rows 0.41 % (S / D / I 3 / 0 / 1 over 974 words). VmHWM
  2,087,700 kB.

### l4f: CPU, 30 s window, tdt_fix true, S4 back to back (`l4f-litert-cpu-30s-fix-S4`)

- S4 in two processes: the first 494 rows (stopped at a sitting's deadline, no footer; warm load
  590.9 ms), then the other 161 in the next sitting (`start_after` `6829-68769-0014`, the `.resume1`
  probes; warm load 924.6 ms). 655 of 655 rows, none with an error.
- **WER 2.20 %** (S / D / I 210 / 53 / 26 over 13,117 words). **1 empty hypothesis**:
  `237-134500-0025` (1.63 s; v = 26,080 samples, n = 163, 25 encoder frames decoded, 16 network
  runs, no error).
- Clocks: the engine CPUs' ceiling fell 63.2 % (policy6; policy0 50.8 %) during the run, so this
  CPU run has **no RTF** (`cpu-cap-rule`). Σ processing 1746.7 s over 4875.8 s of audio, kept as
  recorded; per window (median, under those ceilings): mel 1455.4 ms, encode 520.4 ms, decode
  594.4 ms.
- Decoder: 658 windows. The 655 shorter than 30 s stopped before frame 375; the 3 that decoded all
  375 frames are the full first windows of the three utterances longer than 30 s (v = 480,000,
  480,000 and 479,990). Decoded frames per window: mean 97.06, median 76.5; network runs per window:
  mean 41.85; no frame capped.
- Registration (`.load-logcat.txt`, both processes): `XNNPACK CPU accelerator registered`; XNNPACK
  took encode 1691 / 1838 nodes (249 partitions), decode 161 / 163, decode_1 61 / 63, and the three
  `odml.group_norm` subgraphs 14 / 14. The NPU registry logs `could not be loaded and registered`
  and the GPU accelerator library registers; the model is compiled for the CPU (`accelerator=cpu`,
  the XNNPACK lines).
- VmHWM 2,100,332 kB (first process, sampler) and 2,097,300 kB (second, end). W: 2.825 s and
  2.919 s.
- Text against asr-litert-app-v1's L4 S4 (`l4-litert-cpu-30s-S4` + `-p2`, the app's decoder, the
  same ids): 479 of 655 identical (416 / 545 and 63 / 110); the first differences are listed in the
  summary's `text_checks`.

### b-l4f: CPU, 30 s window, tdt_fix true, S32 burst (`b-l4f-litert-cpu-30s-fix-S32`)

- S32 in one process (warm load 990.5 ms; `cool` ok after 62 s). 82 rows, all counted; 2 retaken
  (first attempts fell 28.3 % and 16.2 %, the retakes 14.2 % and 2.8 %, the same text), none
  excluded. **RTF_burst 0.15585** = 97.617 s / 626.36 s; median utterance RTF 0.1963.
- Waits: median 10.79 s, max 35.42 s, sum 960.8 s, no timeout. Fall during an utterance: first
  attempts median 2.8 %; counted attempts at most 14.2 %.
- Per window (median): mel 586.5 ms, encode 264.3 ms, decode 277.4 ms.
- Decoder: 83 windows; 82 stopped before frame 375 (the full first window of `4507-16021-0047`
  decoded all 375). Decoded frames per window: mean 98.86, median 78; network runs: mean 42.89; no
  frame capped.
- Registration: as l4f. VmHWM 2,085,564 kB. W 2.858 s.
- Text: identical to `l4f-litert-cpu-30s-fix-S4` on all 82 ids; against asr-burst-v1's
  `b-l4-litert-cpu-30s-S32` (the app's decoder) 55 of 82 identical. WER over S32: 1.59 % (S / D / I
  21 / 5 / 1 over 1,695 words), no empty hypothesis.

### The JIT after W (CPU, 30 s, tdt_fix true)

Per-window medians (ms) of the run's first 10 utterances (the longest) and its last 10 (the
shortest, one window each), each process warmed by W; decode also per network run:

| run | windows first / last | mel first / last | encode first / last | decode first / last | decode per network run first / last |
|---|---|---|---|---|---|
| l4f (S4, ceilings fallen) | 13 / 10 | 1275.5 / 1425.1 | 445.6 / 501.6 | 1370.6 / 261.1 | 10.43 / 25.98 |
| b-l4f (S32, burst) | 11 / 10 | 591.1 / 578.5 | 263.7 / 266.4 | 634.8 / 154.5 | 6.34 / 12.18 |

The fixed decoder's work per window follows the window's audio (the first ten are 23.7–35.0 s in
l4f and 14.2–35.0 s in b-l4f, the last ten 1.6–2.0 s and 2.0–2.8 s); the decode time per network
run is higher on those short windows (not traced). l4f's first and last ten ran in different
processes and sittings, under fallen ceilings.

### b-l3f: NPU, 5 s window, tdt_fix true (`b-l3f-litert-npu-5s-fix-smoke10`): the gate fails, S32 not run

- The NPU model and its tokenizer were added to the app's files dir before the run
  (`setup-models.log`; phone-side sha256 matched). One process, cold load 1,014.5 ms; `cool` did
  not reach its line within 15 minutes and the run started anyway (battery 38.2 °C, thermal
  status 1).
- Registration (`.load-logcat.txt`): `RegisterAccelerator … name=NpuAccelerator`,
  `NPU accelerator registered`, `libLiteRtDispatch_Qualcomm.so` loaded from the app's library dir,
  QNN graphs `qnn_partition_0` / `_1` / `_2` loaded, and `Replacing 1 out of 1 node(s) with
  delegate (DispatchDelegate) node` for encode, decode and decode_1. The Qualcomm `fastrpc` layer
  logs error lines at the load (`open_shell failed for domain 3`, log watchers `Permission
  denied`); the graphs then ran (below).
- W, first 5 s window: every decoder step gave token 0 with duration 0; after 10 of them at one
  frame the cap moved to the next, so the window ended after 63 × 10 = 630 steps (`.tokens.log`:
  `tokenId=0` ten times at each timestamp 0–62, then the end marker at 63; `.logcat.log`: QNN ran
  `qnn_partition_0` once, `qnn_partition_1` 4 times and `qnn_partition_2` 626 times, with
  `QnnMem_register` / `QnnMem_deRegister` lines, status 0, between the runs). Second window: the
  encoder (`qnn_partition_0`) and one `qnn_partition_1` run finished (token 0); the dispatch layer
  deregistered memory handles (status 0); the next `qnn_partition_1` run failed: QNN
  `Failed to find memHandle 0x6`, `Failed to get HTP memHandle info for tensor`,
  `graphExecuteRpcMemWrite failed for inputs`, `Graph qnn_partition_1 failed in execution with err
  6004`, then LiteRT `Failed to invoke the compiled model` (W's row carries the error; `.logcat.log`).
- The 10 rows: in each, `qnn_partition_0` finished and the first `qnn_partition_1` run failed the
  same way; every row has the error `LiteRtException: Failed to invoke the compiled model`. WER
  100 % against the gate's line of 36.25 % (set before the run), so the S32 run was not started.
  Not traced: how the app's decoder, which swaps its LSTM state buffers between the `decode` and
  `decode_1` signatures, meets the dispatch layer's QNN memory registration.
- VmHWM 1,501,500 kB.

### b-l5f: GPU, 30 s window, tdt_fix true: not run

Defined in the driver and `docs/asr-fix-v1.md`; left out by the lane's decision during the sitting
(the driver refused it through `.build/asr-fix/STOP_ARMS`, exit 7, after b-l4f).
