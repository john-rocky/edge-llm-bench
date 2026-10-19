# 2026-10-19 asr-sherpa v1: Galaxy S26 (SM-S942Q, SM8850, Android 16), sherpa-onnx v1.13.8, parakeet-tdt-0.6b-v3 int8, CPU, 4 threads

Definition: `docs/asr-sherpa-v1.md`. Tools: `tools/asr-sherpa/`. One hold of the phone, 13:21:26 to 13:47:49 JST.

## Result (S4, 655 utterances, 4875.78 s)

| run | start: battery / Thermal Status / HAL AP / clock ceilings | end | WER | S / D / I | RTF (median per utterance) | lowest ceiling during the run | VmHWM | load |
|---|---|---|---|---|---|---|---|---|
| retake (`a1-sherpa-cpu-int8-S4.*`) | 35.8 °C / 0 / 36.5 °C / both at max | 42.3 °C / 2 / 48.7 °C | 2.22 % | 213 / 42 / 36 of 13,117 words | 0.0678 (0.0761), cpu-capped | policy6 1497.6 of 4742.4 MHz (−68.4 %), policy0 1555.2 of 3628.8 MHz (−57.1 %) | 1,274,588 kB | 1.101 s |
| attempt 1 (`*.attempt1`) | 35.9 °C / 0 / 40.8 °C / policy6 −18.6 %, policy0 −6.3 % | 41.5 °C / 2 / 47.5 °C | 2.22 % | 213 / 42 / 36 | 0.0655 (0.0711), cpu-capped | the same: −68.4 % / −57.1 % | 1,275,028 kB | 1.165 s |

- **No valid speed number.** In both runs the CPU clock ceilings fell far past the 15 % line of `cpu-cap-rule`, so the RTF is not a measurement under the repo's rule (`methodology/fairness-rules.md` §13: a CPU arm's run past the line pools into no number). The capped values stay in the records as conditions; the retake was the one re-run the protocol allows. The retake started after a 390 s cooldown with both ceilings at their hardware maximum and the HAL AP sensor at 36.5 °C. About 10 s into the decoding (30 s into the process, after the binary's two 10 s sleeps and the load) the ceilings stood at 2496.0 / 2438.4 MHz (policy0 / policy6), 10 s later at 1996.8 / 1977.6 MHz, and at 1555.2 / 1497.6 MHz at the end, with AP at 48.7 °C. The run's own load drives the fall, which matches the earlier Galaxy S26 sittings described in §13.
- **WER 2.22 %** (corpus, Open ASR Leaderboard normalizer), no empty hypothesis, no stalled file. The two runs' raw outputs (`*.stdout.log`) are byte-identical, timestamps and log-probs included.
- **Peak memory**: VmHWM 1,274,588 kB (retake), 1,275,028 kB (attempt 1). It rises during the run: 1,221,016 kB after the first files, 1,272,664 kB at the end of attempt 1. Threads: 11.
- **Model load** (the binary's `recognizer init time`): cold 0.982 s (`a1-sherpa-cpu-int8-smoke`, the first process after the push), warm 1.050 s (`a1-sherpa-cpu-int8-warm`, a one-file process right after attempt 1, on the hot phone with its ceilings down). The S4 processes' own: 1.165 s (attempt 1), 1.101 s (retake). Process walls are reference values only (they include the binary's two 10 s sleeps): smoke 26.7 s, S4 343.1 s / 354.2 s.
- Timing cross-check: the stamped spans sum to 330.42 s (retake) and 319.25 s (attempt 1). The binary's own `Elapsed seconds`, 331.172 s and 320.005 s, also includes W's timed decode. The small difference points to no stall and no suspend of the phone.
- HANG: none. Uptime ran on through the hold (no reboot).

## Conditions

- Phone: SM-S942Q, Android 16 (build BP4A.251205.006.S942QOPS1AZH9, patch 2026-08-05), USB powered and not charging (battery status 4, 79 % at the start), screen awake (`stay_on_while_plugged_in` 15). The hold was taken right after another lane's sitting on the same phone: battery 35.2 °C, HAL AP 36.5 °C, both ceilings at their maximum (`probe-hold-start.json`).
- Runtime: sherpa-onnx v1.13.8 (`sherpa-onnx-version`: Git SHA1 11afbd00, onnxruntime 1.28.2), release asset `sherpa-onnx-v1.13.8-android-aarch64-termux-static.tar.bz2`, binary `sherpa-onnx-offline-parallel`, unmodified. The ONNX Runtime in the binary is 1.28.2, build info git-commit-id 33ca96282. The app build's jniLibs `libonnxruntime.so` (`sherpa-onnx-v1.13.8-android.tar.bz2`) reports the same version and commit (`LOCK.json` `onnxruntime`).
- The termux binaries list `libc++_shared.so` in DT_NEEDED. A stock Android shell does not have it, and no v1.13.8 Android asset ships it. Without it the binary stops with `CANNOT LINK EXECUTABLE "./bin/sherpa-onnx-offline-parallel": library "libc++_shared.so" not found: needed by main executable` (`sherpa-onnx-offline-parallel.nolib.txt`). The Android NDK 28.2.13676358 aarch64 `libc++_shared.so` (sha256 ab4e6c71…, `LOCK.json` `cxx_runtime`) sits in `asr-sherpa/lib/` and is passed with `LD_LIBRARY_PATH` (the binary's RUNPATH `$ORIGIN/../lib` resolves the same file).
- Model: `sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8` (release `asr-models`, updated 2025-08-16): `encoder.int8.onnx`, `decoder.int8.onnx`, `joiner.int8.onnx`, `tokens.txt`. Every pushed file was read back with `sha256sum` on the phone, and the S4 WAVs were hashed there as one chain, c83c07ed… (`SHA256SUMS`).
- Command (`*.cmd`): `--model-type=nemo_transducer --num-threads=4 --decoding-method=greedy_search --batch-size=1 --nj=1 --wav-scp=<[W] + S4>`, with the feature settings left to the binary. `Cpus_allowed_list` 0-7, no affinity set. W = `1995-1836-0004` (manifest row 1, not in S4); its transcript is in each JSONL footer (`warmup`).
- Timing definition (also in each JSONL footer): processing_seconds = the phone's `$EPOCHREALTIME` stamp of the stderr line naming the file minus the stamp of the previous file's `----` line. The span covers reading the file, its feature extraction and its decode; model load is excluded. The binary's own `Elapsed seconds` and RTF line are kept in the footer and not used, since that RTF counts W's seconds twice in its denominator.

## Smoke runs and the plain binary

- `a1-sherpa-cpu-int8-smoke`: W plus the first 3 S4 files with the A1 command. All transcripts were non-empty. Processing took 1.17 / 1.08 / 1.03 s for 34.96 / 31.65 / 30.04 s of audio (the ceilings were 28.3 % down by the end of the 26 s process).
- `a1-sherpa-offline-batch3-smoke`: the plain `sherpa-onnx-offline` (it decodes all its files in one padded batch) on the same 3 files with the same `lib/`. Load 0.966 s, VmHWM 1,651,276 kB. Its 3 transcripts carry the same words as the parallel binary's. Two differ in punctuation only: 4507-16021-0047 "money the day after, to morrow" against "money the day after to morrow", and 121-123859-0002 "tyranny?" against "tyranny,".

## Kept in the record from the way here

- `a1-sherpa-cpu-int8-smoke.*.attempt1`: the first smoke used a FIFO for the stderr stamps. `mkfifo` is denied under `/data/local/tmp` on this phone ("Permission denied"), so the binary's stderr went to a plain file that the runner then removed. That process's stderr, including its load line, is lost; its stdout (the texts) is kept. `device_run.sh` now pipes stderr into the stamper. The model was pushed again before the second smoke, so that the second smoke is again the first process after a push.
- The adb client of the launch call does not return while the nohup'ed runner lives. Both smokes' launch calls returned when the run ended; the S4 launch calls were cut by the driver's 30 s timeout, and the runs went on under nohup.
- The battery temperature file the sampler reads (`/sys/class/power_supply/battery/temp`) is not readable for the shell user, so the samples' battery column is empty. The probes carry the battery temperature (dumpsys).

## Not run

- The full test-clean set (2620 utterances): after the retake the hold had about 19 min left, with the phone at 42.3 °C and Thermal Status 2. The protocol starts the full set only with 22 min or more left after the expected cooldown.
- Energy (energy cells are manual).

## Files

`a1-sherpa-cpu-int8-S4.jsonl` (header, 655 utterance lines, footer) with its raw `.stdout.log` / `.stderr.log` (stamped) / `.vmhwm.log` / `.cmd` / `.exit` / `.scp` / `.cpus` / `.pid` / `.rc` / `.runner.log` / `.done`; the same for attempt 1 (`*.attempt1`), the two smokes and the warm process; `summary/a1-S4.score.json` (and `.attempt1`) from `score.py`; `probe-*.json`; `SHA256SUMS`; `LOCK.json`; `SET-S4.json`; `*.help.txt`, `sherpa-onnx-offline-parallel.nolib.txt`, `sherpa-onnx-version.txt`; `progress.log`.
