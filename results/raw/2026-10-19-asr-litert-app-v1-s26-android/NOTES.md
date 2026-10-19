# 2026-10-19 parakeet-tdt-0.6b-v3 through the LiteRT sample app — Galaxy S26 (SM-S942Q, SM8850, Android 16)

Definition: `docs/asr-litert-app-v1.md`. What was changed in the app and what each number covers:
`INSTRUMENT.md` (+ `instrument.patch`). Versions and hashes: `LOCK.json`. Set: `SET-S4.json`.

## Conditions

- Phone: Galaxy S26 RFGL80R6A6H, USB-connected, screen kept on (`svc power stayon usb`), the test run
  headless through `am instrument` (no activity in front). In every run the process could use CPUs
  0-5 only (its `Cpus_allowed_list`; CPUs 6-7 = cpufreq policy6 were outside its cpuset).
- Files on the phone: the model files and the WAV set in the app's internal files dir, copied with
  `run-as` (`setup.log`; the app could not read the WAVs adb had put in its external files dir,
  `setup.log.attempt1`).
- App: litert-samples `speech_recognition` at `d15f8ae9` + benchmark commit (LOCK.json `app`), debug
  build, LiteRT 2.2.0 (`litert-2.2.0.aar`), Qualcomm runtime `qualcomm_runtime_v81` + QAIRT 2.47.0 in
  the APK. CPU threads 4 (`CpuOptions`), GPU precision FP32 and NPU HTP mode HIGH_PERFORMANCE (the
  app's defaults for this model).
- Models: `litert-community/parakeet-tdt-0.6b-v3`@3ce205aa `parakeet_tdt_0.6b_v3_5s_i8_stateful.tflite`
  (CPU, GPU) and `parakeet_tdt_0.6b_v3_5s_f32_stateful_Qualcomm_SM8850.tflite` (NPU, AOT);
  `mlboydaisuke/Parakeet-TDT-0.6B-v3-LiteRT`@af580dff `parakeet_tdt_0.6b_v3_30s_i8_stateful.tflite`.
- Set: LibriSpeech test-clean S4 (655 utterances, 4875.8 s), one process per run, manifest order.
- Each run starts cool (battery ≤ 36.0 °C, thermal status 0, every CPU ceiling at its maximum, at most
  15 min of waiting; only `l1-…-warm3` started at the limit, battery 36.2 °C); `<tag>.probe-before.json`
  / `-after.json` hold the device state, `<tag>.cmd` the commands.

## Results

| arm | form | S4 WER % (S / D / I) | transcribed | speed | load cold / warm ms | VmHWM kB |
|---|---|---|---|---|---|---|
| L1 | CPU, 5 s window (`5s_i8_stateful`) | 15.42 (283 / 1661 / 79) | 654 / 655 (1 app exception) | no number: CPU ceiling −50.8 % | 1,393.6 / 996.8, 1,051.0 | 1,778,316 |
| L4 | CPU, 30 s window (`30s_i8_stateful`) | 2.86 (215 / 51 / 109) | 655 / 655 (2 processes) | no number: CPU ceiling −57.1 % | 1,526.0 / 1,471.0 | 2,105,360 |
| L3 | NPU, 5 s window (`5s_f32_stateful_Qualcomm_SM8850`, AOT) | — | 0: decoder loops at frame 0 | — | 878.8 / 599.6 | 1,780,504 (first process) |
| L2 | GPU, 5 s window | not measured | | | | |
| L5 | GPU, 30 s window | not measured | | | | |

### L1 — CPU, 5 s window (`l1-litert-cpu-5s-*`)

- **WER 15.42 %** on S4 (S 283 / D 1661 / I 79 of 13,117 reference words; `summary/l1-litert-cpu-5s-S4.score.json`).
  654 of 655 utterances transcribed, 1 failed inside the app (below), no crash, no hang.
  Of the 882 windows after the first one of an utterance, 348 (39.5 %) returned no token; the 5 s
  standalone windows are the cause (the model's own behaviour on short windows,
  `../2026-09-25-omni-asr-wer-v1-m4max-mac/NOTES.md` §2).
- **Speed: no number** (fairness-rules §13). The process ran on CPUs 0-5 (its `Cpus_allowed_list`;
  policy0, hardware maximum 3,628,800 kHz). Their ceiling fell to 3,513,600 kHz 6 s into the run,
  2,227,200 at 30 s and 1,785,600 (−50.8 %) from about 4 min until the end (`.vmhwm.log`): the
  run's own load lowered it. The wall times stay in the JSONL and the summary; they are not a speed
  number of this record. Not retaken: a cap the run's own load raises returns in a retake.
- Load: 1,393.6 ms cold (the first process after the model was copied in = the 10-utterance check
  `spread10`), 996.8 ms and 1,051.0 ms warm (the S4 process, `warm3`). VmHWM 1,778,316 kB (S4).
- Heat (S4): battery 35.8 → 41.0 °C, thermal status 0 → 1 (probes); policy6 (CPUs 6-7, outside the
  process's CPUs) fell from 4,742,400 to 1,747,200 kHz as well.
- Accelerator (`.load-logcat.txt`): `XNNPACK CPU accelerator registered`; `Replacing 1643 out of 1790
  node(s) with delegate (TfLiteXNNPackDelegate) node, yielding 249 partitions for subgraph 0
  (encode)`, decode 161 / 163 nodes, decode_1 61 / 63.
- Per window (medians, under the cap): mel 352 ms, encode 120 ms, decode 152 ms. The app is the debug
  build (ART runs it from the APK with the JIT: `dexopt: [status=run-from-apk]` in the `.cmd`).
- The failed utterance: `3575-170457-0025` (9.205 s, 3 windows). Window 2 emitted 443 tokens
  (its decode took 1,746 ms; windows 1 and 3: 29 and 21 tokens); at the end of that window the app's
  merger threw `java.lang.IllegalArgumentException: Requested element count -60 is less than zero.`
  at `LevenshteinTokenMerger.mergeTimestamps(LevenshteinTokenMerger.kt:244)`
  (`currentWordTimestamps.drop(...)`), called from `getConfirmedAndUnconfirmedTextAtEndOfSequence`
  (`:127`) — where the app shows its "Transcription error" toast. The row is scored as an empty
  hypothesis. TdtDecoder has no cap on symbols per frame (a non-blank token with duration 0 does not
  advance the frame index), the shape of the 09-25 decoder hang; that this window is that case is
  not verified. Recorded, not fixed.
- The 10-utterance check (`spread10`: S4 rows 0, 65, …, 585, 34.95 s down to 2.71 s): WER 14.9 %,
  no empty hypothesis, ceiling −3.2 %.

### L4 — CPU, 30 s window (`l4-litert-cpu-30s-S4`, `…-S4-p2`)

- **WER 2.86 %** on S4 (S 215 / D 51 / I 109 of 13,117 reference words; `summary/l4-litert-cpu-30s-S4.score.json`).
  655 of 655 transcribed, no failure, no hang; 1 empty hypothesis (`237-134500-0025`, 1.63 s, "oh emil").
- **Two processes, joined**: the run was stopped at the 45 min hold limit (16:00:15) after 545
  utterances (last: `260-123440-0005`) and resumed in the next hold after that utterance
  (`-p2`, 110 utterances). Each utterance is independent (the decoder state is reset at every
  window, the merger per file), so the WER is computed over the joined rows
  (`summarize.py <part 1> <part 2> --tag l4-litert-cpu-30s-S4`). At the stop the driver read the
  stopped app as a crash and relaunched it for 16 s; that relaunch's rows (a false `crash` row for
  `121-121726-0005`, a header, 2 utterances) are kept only in `l4-litert-cpu-30s-S4.jsonl.as-pulled`,
  and part 2 redid those utterances (`l4-litert-cpu-30s-S4.events.tsv` notes).
- Errors by length: clips under 5 s carry 81 of the 109 insertions (272 utterances, 2,483 words); the
  typical case is a made-up tail after the real words, decoded over the zero-padded rest of the
  30 s window (e.g. `7176-92135-0010`, 2.2 s: "ham to be or not to be" + "honest and i am not sure if
  you are not going to be able to do that", 17 insertions). The app has no stop at the last frame
  that carries audio: the decoder walked 246,750 encoder frames, of which 61,326 (24.9 %) carry
  audio (summary: `encoder_frames_with_audio` / `encoder_frames_walked`).
- **Speed: no number** (fairness-rules §13): the CPU ceiling of the process's CPUs (0-5) fell to
  1,555,200 kHz at its lowest in part 1 (−57.1 %) and 1,996,800 kHz in part 2 (−45.0 %). Per window
  (medians): mel 1,846 ms, encode 727 ms, decode 1,605 ms. Each decoder step outputs logits for all 375 frames × 4 token slots
  (`decode` signature output `[1, 375, 4, 8198]`) and the app reads that whole buffer back at
  every step.
- Load: 1,526.0 ms cold (part 1); 1,471.0 ms for part 2, whose header says `cold` but which was the
  third process of this model on the CPU = a warm load. VmHWM 2,105,360 kB (part 1).
- Accelerator: `XNNPACK CPU accelerator registered`; encode 1691 / 1838 nodes to XNNPACK in 249
  partitions, decode 161 / 163, decode_1 61 / 63.

### L3 — NPU, 5 s window, AOT for SM8850 (`l3-litert-npu-5s-smoke3`): not measurable as the app ships (the decoder hangs)

- The NPU path loads: `NPU accelerator registered`, LiteRT's Qualcomm dispatch library loaded from
  the app's native library dir, `Replacing 1 out of 1 node(s) with delegate (DispatchDelegate)` for
  encode, decode and decode_1, `QnnContext_createFromBinary done successfully`; load 878.8 ms (first
  process) and 599.6 ms (second), HTP mode HIGH_PERFORMANCE (`.load-logcat.txt`).
- It does not transcribe: the first utterance (`4507-16021-0047`) produced no row in 10 min and the
  watchdog restarted the process after it (`hang` row); the second process stalled the same way on
  the next utterance (`2094-142345-0008`) and was stopped at 18:19:53. In the live process the app's merger logged
  `decode: tokenId=0, timestamp=0` every ~12 ms (24,284 lines in the buffer) while the NPU ran
  `decode_1` (QNN `qnn_partition_2`) again and again: the decoder emits token 0 with duration 0 and
  never leaves frame 0 (TdtDecoder has no cap on symbols per frame). In the log the driver kept of
  the two processes (`.logcat.log`; the per-step lines are trimmed, their counts on its last line)
  `qnn_partition_2` (decode_1) finished 26,135 and 26,615 times, each run with its buffers
  registered and released again (`QnnMem_register` / `QnnMem_deRegister` ≈ 4 each per run), while
  the encode and decode partitions finished 5 times each. Whether the NPU's outputs are wrong from the first window
  or turn degenerate later is not verified (the log buffer held only the last minutes;
  `.loop-excerpt.txt`). No WER, no speed.

### L2 (GPU, 5 s) and L5 (GPU, 30 s)

- L2: not measured — the 5 s window form, so its word errors carry the same standalone-window
  behaviour as L1; the lane did not spend phone time on it.
- L5: not measured — the lane decides on the 30 s GPU form from a separate speed run first.
