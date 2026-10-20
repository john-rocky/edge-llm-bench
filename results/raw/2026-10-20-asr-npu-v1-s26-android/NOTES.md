# asr-npu-v1 — Galaxy S26 (SM-S942Q, SM8850): the speech_recognition sample app's NPU text, taken apart

Definition: `docs/asr-npu-v1.md`. The app build and what it changes: `INSTRUMENT.md`,
`instrument.patch`. Versions and hashes: `LOCK.json`. Each section below states one check's facts.

## Conditions

- Phone: Galaxy S26 `RFGL80R6A6H` (SM-S942Q, SM8850, Android 16), on USB power, the bench build's
  `BenchFrontActivity` in front during every run (`require_top_app=false`: nothing here is timed).
- Runtime: LiteRT 2.2.0 (Maven `litert` 2.2.0 → `litert-api` 2.2.0); NPU = the Qualcomm runtime of
  the LiteRT v2.2.0 release (`litert_npu_runtime_libraries.zip`, qualcomm_runtime_v81:
  `libLiteRtDispatch_Qualcomm.so`) with QAIRT 2.47.0's HTP libraries in the APK. The LiteRT v2.3.0
  release carries no NPU runtime archive, so the runtime stays at 2.2.0. NPU options as the app sets
  them: HTP performance mode HIGH_PERFORMANCE, CPU in the accelerator set, 4 CPU threads.
- Files (Hub revision, bytes = the Hub's LFS sha256, checked on the phone after the copy):
  `litert-community/parakeet-tdt-0.6b-v3`@3ce205aa `parakeet_tdt_0.6b_v3_5s_f32_stateful.tflite`
  (2,421,888,688 B, `8c1f06a9…`) and `…_5s_f32_stateful_Qualcomm_SM8850.tflite` (1,275,526,880 B,
  `e9edabe4…`); `litert-community/parakeet-ctc-0.6b`@e3c5b655 `parakeet_ctc_0.6b_5s_f32.tflite`
  (2,348,753,728 B, `8b4c970a…`), `parakeet_ctc_0.6b_5s_i8.tflite` (596,365,072 B, `3d0799f6…`) and
  `parakeet_ctc_0.6b_5s_f32_Qualcomm_SM8850.tflite` (1,210,738,160 B, `30e431db…`); tokenizers
  `nvidia/parakeet-tdt-0.6b-v3`@541d1f99 and `nvidia/parakeet-ctc-0.6b`@ad09ba1c `tokenizer.json`.
- Set: LibriSpeech test-clean (`hf-audio/open-asr-leaderboard`@de79e57a parquet, unpacked by
  `tools/omni-eval/prep_librispeech.py`). S32 = rows 0, 32, 64, …; F20 / F10 = its first 20 / 10
  rows; W = `1995-1836-0004` (`SET-*.json`).
- Sitting: one hold, 12:01:41–12:12:02 JST (`setup.log`, the probes): setup (the seven files copied
  into the app's files dir with run-as and read back with sha256, the B inputs, F20 + W), then the
  ten runs in the order below. Battery 33.7 °C / thermal status 0 at the first run, 41.7 °C / 2 at
  the last. Every run had `BenchFrontActivity` RESUMED and the process in the top-app cpuset.

## B — `encode` alone, the AOT file on the NPU and the f32 file on the CPU (`b-*.json`, `b-compare.json`)

Inputs (`b-inputs.json`): MelDumpTest's encoder inputs of `4507-16021-0047` (S32's first utterance,
11 windows of 5 s with 2 s overlap) picked by the rule set before the runs: window 1 (index 0),
window 6 (index 5, the middle) and window 11 (index 10, the largest share of 10 ms frames under
−40 dBFS among the rest, 57.4 %); and an all-zero input of the same size (outside the line). The
same bytes went to both files (input sha256 in each report). Each input ran twice on the same
buffers.

- `b-tdt-npu` (`…_5s_f32_stateful_Qualcomm_SM8850.tflite`, load 866.4 ms): `encode` output_0
  `[1, 1024, 63]` = 64,512 NaN of 64,512 for each of the four inputs; the two runs bit-identical;
  `encode` 42.8–45.3 ms. The load log: `NPU accelerator registered`, `Replacing 1 out of 1 node(s)
  with delegate (DispatchDelegate)` for encode, decode and decode_1, and `Context binary (2.44.0) is
  older than the current SDK (2.47.0)`. Buffer requirements of every I/O: `[FastRpc, DmaBuf]`.
- `b-tdt-cpu` (`…_5s_f32_stateful.tflite`, load 2054.7 ms): `encode` output_0 has no NaN or Inf for
  any input (largest |x| 0.13–0.18); the two runs bit-identical.
- Against `b-tdt-cpu`'s output of the same input, the line's verdict for `b-tdt-npu`: the three
  windows differ (a non-finite NPU value counts as differing); the all-zero input too.
- `decode` / `decode_1` of the same AOT file on the NPU, fed `b-tdt-cpu`'s encoder outputs (tokens
  `[8192, 0, 0, 0]` / `[8192]`, zero LSTM states): logits with no NaN; per frame of token slot 0
  the token argmax and the duration argmax equal `b-tdt-cpu`'s on 63 of 63 frames for all four
  inputs, both signatures; cosine over all logits 0.938–0.988 (`decode`) and 0.931–0.991
  (`decode_1`), largest |Δ| 34.3–35.0; cosine of the LSTM state outputs ≥ 0.9999995.
- The same two signatures on the NPU fed `b-tdt-npu`'s own encoder outputs: all logits NaN
  (2,065,896 and 516,474 values); the state outputs finite. Read the way the app reads them
  (Kotlin `maxByOrNull`, where NaN compares greater than any number): token 0 and duration 0 at 63
  of 63 frames for all four inputs.
- `b-ctc-npu` (`parakeet_ctc_0.6b_5s_f32_Qualcomm_SM8850.tflite`, load 835.2 ms): `encode` output_0
  `[1, 63, 1025]` NaN: window 1 64,575 / 64,575, window 6 64,534 (41 finite values, −59,072 to
  62,336), window 11 64,575, zeros 64,539 (36 finite, −62,912 to 56,704); the two runs
  bit-identical; per-frame argmax (NaN read as −∞) equal to `b-ctc-cpu`'s on 0 of 63 frames for
  each input. Read the way `CtcDecoder` reads them, the NPU windows give `<unk>`, `▁t <unk>`,
  `<unk>` and `<unk> ▁t <unk>`; the CPU's give the words of the utterance for the three windows (window 1: `▁yesterday
  ▁you ▁were ▁trembling ▁for ▁a ▁health …`) and only blanks for the zeros. The same load-log lines as the TDT file (context
  binary 2.44.0).
- `b-ctc-cpu` (`parakeet_ctc_0.6b_5s_f32.tflite`, load 2136.6 ms): no NaN or Inf (values −7.31 to
  169.33); the two runs bit-identical.
- VmHWM: 4,979,120 / 1,440,436 / 4,742,732 / 1,318,540 kB (tdt-cpu / tdt-npu / ctc-cpu / ctc-npu).

## A — the app's CTC path on the CPU (`a-ctc-*-first20`)

- `a-ctc-i8-first20`: the `parakeet-ctc-0.6b` entry's own file (5 s int8), F20: 20 rows, no error,
  no empty text; WER 2.53 % (S / D / I 14 / 4 / 3 of 830 words); load 1343.9 ms; VmHWM
  1,410,320 kB.
- `a-ctc-f32-first20`: the same entry with `model_file` = the 5 s f32 file (sha256 8b4c970a… read
  on the phone after the run): 20 rows, no error, no empty text; WER 2.41 % (13 / 4 / 3 of 830);
  17 of 20 texts identical to the int8 run's; load 1446.1 ms; VmHWM 4,790,244 kB.

## C — the TDT decoder's buffers (`c-*-smoke10`, `tdt_fix=true`, F10)

- `c-npu-shared-smoke10` (the app's buffers): every row has the error `LiteRtException: Failed to
  invoke the compiled model` (10 of 10), and W too. W's first window ran 630 decoder steps (token 0
  at every step, the symbol cap moving past all 63 frames); its second window and the first window
  of every row failed. The kept log (`.logcat.log`, per-step lines trimmed with their counts; the
  full log stays outside the record) has `QnnDsp <E> Failed to find memHandle 0x6`,
  `Failed to get HTP memHandle info for tensor`, `graphExecuteRpcMemWrite failed for inputs` and
  `Graph qnn_partition_1 failed in execution with err 6004`; over the run the full log counts 21
  `Failed to find memHandle` lines (handles 0x2, 0x4, 0x5, 0x6, 0x7; 0x6 in 12), 643 finished graph executions (qnn_partition_0 / _1 / _2 = 12 / 5 /
  626), 11 failed ones, 1,202 `QnnMem_register started` and 1,251 `QnnMem_deRegister started`.
- `c-npu-separate-smoke10` (`tdt_buffers=separate`): no error in any row or in W; no
  `Failed to find memHandle` and no `E qnn` / `E litert` line. All ten texts empty (WER 100 %,
  0 / 499 / 0): every window ran up to 630 decoder steps with token 0 (mean 607.0 steps per window;
  the kept `.tokens.log` counts `tokenId=0` 45,069 times and the end marker 74 times). The full log
  counts 45,144 finished graph executions (74 / 296 / 44,774), no failed one, 8
  `QnnMem_register started` and 8 `QnnMem_deRegister started`.
- `c-cpu-shared-smoke10` / `c-cpu-separate-smoke10` (the 5 s f32 stateful file on the CPU through
  `model_file`): 10 rows each, no error; the ten texts identical between the two (W's too); WER
  24.65 % each (11 / 112 / 0 of 499); 30.70 decoder runs per window each.
- For reference, the asr-litert-app-v1 L1 run (CPU, the 5 s int8 file, the app's decoder) over the
  same ten ids: WER 26.25 % (`summary/runs.json`).

## The decoder alone with a finite encoder output (`d-*`, a second hold)

A second hold, 14:11:53–14:12:43 JST (`setup-decoder.log`, `cleanup.log`): the bench test APK
rebuilt with `DecoderBufferTest` (app commit 01140858, test APK sha256 21201e67…; the app APK on the
phone unchanged), then four runs, then the round's packages uninstalled. `DecoderBufferTest` runs the
app's `TdtDecoder` (tdt_fix on) without the encoder: before each window it writes an encoder output
read from a file into the encode signature's output buffer (the buffer `LiteRtRunner` hands the
decoder) and decodes from it. The four files are `b-tdt-cpu`'s encoder outputs (windows 1, 6, 11
and the all-zero input, f32 file on the CPU: no NaN); each run decodes them three times in order,
12 windows (`d-compare.json`).

- `d-cpu-shared` (the 5 s f32 stateful file on the CPU, the app's buffers): no error in 12 windows;
  23, 16, 17 and 0 tokens per window, in 28, 32, 28 and 16 decoder steps.
- `d-npu-shared` (the SM8850 AOT file on the NPU, the app's buffers, the encode signature run on an
  all-zero input before each window as the app runs it, then its output buffer overwritten): every
  window has the error `LiteRtException: Failed to invoke the compiled model` (12 of 12). The first
  window emitted 23 tokens, identical to `d-cpu-shared`'s, and failed at decoder step 26 of 28;
  every later window failed at its first decoder step.
- `d-npu-shared-noenc` (the same without the encode run): the same, 12 of 12, the first window's 23
  tokens identical, failure at step 26, then at the first step.
- `d-npu-separate` (the same file, `tdt_buffers=separate`, encode run as in `d-npu-shared`): no
  error in 12 windows; the token ids of every window identical to `d-cpu-shared`'s (12 of 12),
  in the same numbers of decoder steps; 119–145 ms per window.
- The kept logs of the four runs (`d-*.logcat.log`) hold none of the app process's lines: each
  process ended (2–4 s) before the driver's first poll read its pid, so the filter dropped them;
  the QNN lines of these runs are not in the record. Since then the driver takes the pid from the
  test's report. The same holds for `b-tdt-npu` / `b-ctc-npu`'s `.logcat.log`; their
  `.load-logcat.txt` (written by the test itself after the load) has the load lines.
- Cleanup (`cleanup.log`): `….npucheck.test`, `….npucheck`, `….prcheck.test` and `….prcheck`
  uninstalled (Success × 4; the last two are the same lane's asr-pr round's); `/data` free
  16,194,464 kB before, 24,982,356 kB after.
