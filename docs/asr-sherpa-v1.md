# ASR on a phone CPU through sherpa-onnx, v1 (2026-10-19)

Task id `asr-sherpa-librispeech-v1`. The question this answers: what sherpa-onnx's own Android release binary does with NeMo parakeet-tdt-0.6b-v3 (int8) on the Galaxy S26 CPU (speed, word error rate, peak memory, model load) on a fixed LibriSpeech subset. First capture: `results/raw/2026-10-19-asr-sherpa-v1-s26-android/` (NOTES.md there has the numbers; this page is the definition). Tools: `tools/asr-sherpa/`.

## The set

LibriSpeech test-clean from `hf-audio/open-asr-leaderboard` (config `librispeech`, split `test.clean`; parquet LFS sha256 `e576cf31…`), unpacked by `tools/omni-eval/prep_librispeech.py` to 16 kHz mono PCM16 WAV: 2620 utterances, 19,452.48 s, WAV sha256 chain `c703709c…` (the 2026-09-25 omni-asr-wer set). **S4** = the rows of `manifest.tsv` at index 0, 4, 8, … (every 4th row from the first; the parquet runs from the longest utterance down, so S4 spans the length range): 655 utterances, 4875.78 s, chain `c83c07ed…`. `fetch_set.sh` + `make_subset.py` rebuild both and print the chains; `SET-S4.json` pins them.

## The arm

- sherpa-onnx v1.13.8 (tag commit `11afbd00`), release asset `sherpa-onnx-v1.13.8-android-aarch64-termux-static.tar.bz2` (sherpa-onnx and ONNX Runtime linked in statically, bionic libc), binary `sherpa-onnx-offline-parallel`. Model: release `asr-models` asset `sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8.tar.bz2` (encoder / decoder / joiner `*.int8.onnx` + `tokens.txt`). `fetch.sh` checks both against GitHub's asset digests and writes `LOCK.json`. The termux binaries need `libc++_shared.so` (DT_NEEDED), which a stock Android shell lacks and no v1.13.8 Android asset ships: the Android NDK's aarch64 copy goes to `lib/` on the phone and is passed with `LD_LIBRARY_PATH` (`LOCK.json` `cxx_runtime`; the binary is unmodified).
- Command: `--encoder= --decoder= --joiner= --tokens= --model-type=nemo_transducer --num-threads=4 --decoding-method=greedy_search --batch-size=1 --nj=1 --wav-scp=<list>`. Feature settings are left to the binary (the NeMo recognizer takes them from the model's metadata). One process, the model loaded once, one file per `DecodeStreams` call, in list order.
- Why `-parallel`: `sherpa-onnx-offline` builds a stream for every file it is given and then calls `DecodeStreams` once; the NeMo transducer path pads all of them into one encoder batch.
- The list is [W] + S4, W = manifest row 1 (`1995-1836-0004`, not in S4). The binary decodes its first file once, untimed, before its timed loop, and the start of the first timed decode is not visible from outside; W takes both. W's transcript stays in the log and the footer and is not scored.

## What is measured

- **RTF** = Σ processing seconds / Σ audio seconds over the scored utterances (model load excluded), RTFx = 1 / RTF, and the median of per-utterance RTF. An utterance's processing seconds = the phone's `$EPOCHREALTIME` stamp of the stderr line naming the file minus the stamp of the previous file's `----` line (`device_run.sh` stamps each stderr line as it arrives; stderr is unbuffered). The span covers reading the file, its feature extraction and its decode. The binary's own `Elapsed seconds` and RTF line stay in the footer and are not used: they sum whole milliseconds per file and count W.
- **WER**: `tools/omni-eval/score.py` run through `tools/asr-sherpa/run_score.py`: the Open ASR Leaderboard's `EnglishTextNormalizer` on both sides, corpus WER, with S / D / I.
- **Peak memory**: the process's `VmHWM`, read every second from `/proc/<pid>/status` on the phone (with `VmRSS`, `Threads`, each cpufreq policy's `scaling_max_freq` and the battery temperature).
- **Load**: the binary's `recognizer init time`. Cold = the first process after the push, warm = a later one-file process. The process wall around the exec is a reference value only (it includes the binary's two 10 s sleeps).
- Conditions: before each run, battery ≤ 36.0 °C and Thermal Status 0 (15 min at most); `probe.sh` before and after (battery, Thermal Status and the "Current temperatures from HAL" block, cpufreq per policy, MemAvailable, uptime, screen). A run during which a policy's ceiling fell more than 15 % below its hardware maximum is discarded and run once more (`cpu-cap-rule`); before that re-run the driver also waits up to 300 s for every ceiling to return to its maximum (`CPUCAP_WAIT`, as the repo's Android runner does). A file whose output stalls for 10 min is killed and listed in `<tag>.hangs`, and the run resumes after it.

## Record shape

`<tag>.jsonl`: a header (model, runtime, threads, command, load), one line per scored utterance (`id`, `text`, `audio_seconds`, `processing_seconds`), a footer (totals, RTF, median, the warm-up file, each process's load / `Elapsed seconds` / wall, VmHWM, the sampled clock ceilings, hangs). Next to it: the raw `<tag>.{stdout,stderr,vmhwm}.log`, `.cmd`, `.exit`, `.scp`, `probe-*.json`, `SHA256SUMS` (read back on the phone), `LOCK.json`, `SET-S4.json`, and `summary/<tag>.score.json` from `score.py`.

## Not covered in v1

Other sets and the other ASR models sherpa-onnx ships; its streaming (online) recognizers; the QNN provider and any NPU or GPU path; energy (energy cells are manual).
