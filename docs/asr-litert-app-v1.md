# ASR through the LiteRT sample app's own pipeline, v1 (2026-10-19)

Task id `asr-litert-app-v1`: parakeet-tdt-0.6b-v3 on a phone, run the way the LiteRT SDK sample app
(`google-ai-edge/litert-samples`, `samples/litert/speech_recognition`) transcribes a file. First
capture: `results/raw/2026-10-19-asr-litert-app-v1-s26-android/` (NOTES.md has the numbers).

**Instrument.** The app at upstream `d15f8ae9` plus benchmark commits (branch `asr-bench-s26`;
`instrument.patch` in the record). The instrumented test `AsrBenchTest` runs MainActivity's file
path copied with timing hooks and no UI — FileAudioSource (window = the model's `inputMilliseconds`,
2 s overlap) → MelSpectroProcessor (jLibrosa) → LiteRtRunner + TdtDecoder → LevenshteinTokenMerger,
in the activity's coroutines and channels — over a manifest of 16 kHz WAVs, one process per run,
the model built once as `preparePipeline` builds it; the transcript is the text the activity shows
at the end. App changes: `CpuOptions(numThreads = 4)` for every accelerator, a 30 s metadata entry,
LiteRT 2.2.0 with the Qualcomm runtime (`qualcomm_runtime_v81`, QAIRT 2.47) packed from `jniLibs`.
Model files and WAVs are copied into the app's internal files dir with `run-as` (no download; the app
cannot read what adb puts in its external files dir). GPU precision and NPU HTP mode are the app's
defaults (FP32, HIGH_PERFORMANCE). Driver: `tools/asr-litert-app/run_app_s26.sh` (cool start,
probes, `am instrument`, 10 min stall watchdog with restart, planned stop, resume as a `-p2` part).

**Set.** LibriSpeech test-clean (`hf-audio/open-asr-leaderboard`, `tools/omni-eval/prep_librispeech.py`);
S4 = manifest rows 0, 4, 8, … (655 utterances, 4875.8 s, WAV chain `c83c07ed…`, SET-S4.json).

**Metrics.** Per utterance: wall seconds from opening the WAV to the merger taking the last token,
per window mel / encode / decode ms and tokens. RTF = Σ wall ÷ Σ audio over utterances without an
error (load excluded), RTFx = 1 / RTF, median utterance RTF; a run whose CPU ceiling fell more than
15 % gives no speed number (fairness-rules §13). WER = `tools/omni-eval/score.py` (leaderboard
normalizer, corpus WER, S / D / I). Load = the LiteRtRunner constructor (CompiledModel.create +
buffers); cold = first process of a model and accelerator after the copy. Memory = VmHWM of the
instrumentation process (= the app process). Heat and CPU ceilings: probes at start and end, the
process's own sampler every second.

**Record.** `<arm>-litert-<cpu|gpu|npu>-<5s|30s>-<set>.jsonl` (header, a row per utterance, footer with
VmHWM, CPU ceilings and the model / WAV / native-library sha256), `.vmhwm.log`, `.load-logcat.txt` +
`.logcat.log` (what LiteRT logged about accelerators), `.cmd`, `.events.tsv`, probes;
`summary/<tag>.score.json` + `.summary.json` (`tools/asr-litert-app/summarize.py`, which joins a
`-p2` part); `LOCK.json`, `INSTRUMENT.md`, `SHA256SUMS`.
