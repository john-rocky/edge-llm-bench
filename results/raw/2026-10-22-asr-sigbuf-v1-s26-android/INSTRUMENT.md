# The instrument: the check build of the TdtDecoder change, and what it adds to the sample app

App: `google-ai-edge/litert-samples` `samples/litert/speech_recognition/AndroidApp` at upstream main
`367816da`. The change under test is one commit on top of it (branch
`speech-recognition-tdt-separate-buffers`; not pushed), in two forms: form 1 `9ca8adad` (`TdtDecoder.kt`
only, the copies on every accelerator) and form 2 `035a442e` (`TdtDecoder(separateBuffers)` and the one
line of `MainActivity.kt` that sets it on the NPU; tree `40fba1f7`, the tree of the commit to send,
`b6beaafb`, which differs only in its message). The check build is one more commit, applied
unchanged on top of main (branch `sigbufcheck-main`) and on top of the change (branch `sigbufcheck`),
so the two APKs of a pair differ only in the change's files; every run's header names the git blob of
the `TdtDecoder.kt` its APK was built from (`tdt_decoder_blob`: `683e118c` = main, `ecee3baa` = form 1,
`7ebe0efc` = form 2). The check-build commit was revised twice, each time before the APKs of the next
hold were built (`LOCK.json` apk_sets: the commit of each set): for form 2 it builds TdtDecoder as
MainActivity does (`SigbufIo.tdtDecoder`, (h)); for hold 3 it adds `SigbufMainActivityTest` ((i)).
`instrument.patch` = the last revision (form 2's branch, `git format-patch`). Definition of the task:
`docs/asr-sigbuf-v1.md`. Versions and hashes: `LOCK.json`.

## Not changed

FileAudioSource, MelSpectroProcessor (jLibrosa), LevenshteinTokenMerger, HuggingfaceTokenizer,
ModelMetadataManager, `model_metadata.json`, LiteRtRunner (its accelerator options, its default
CPU thread count) and MainActivity are upstream main's; so are the 5 s windows and their 2 s overlap.
`TdtDecoder.kt` is main's in `.sigbufcheck.main` / npu-main and the change's in `.sigbufcheck.fix` /
npu-fix.

## Changed by the check build

(a) Packages: `-Psigbufcheck.suffix` sets `applicationIdSuffix` (`.sigbufcheck.main`,
`.sigbufcheck.fix`, `.sigbufcheck.npu`), so the builds install side by side without replacing
another build's APK or files.

(b) LiteRT: the app's `litert` 2.3.0 + `litert-gpu` 2.3.0 by default; with `-Psigbufcheck.npuLibs`
`litert` 2.2.0 (its AAR carries the GPU accelerator) and the ten Qualcomm runtime files packaged from
that directory (`LOCK.json` npu_runtime_libs). `settings.gradle.kts` drops the
`litert_npu_runtime_libraries` modules (not in the repository; main's build cannot resolve them), and
`app/build.gradle.kts` drops the `runtime_strings` dependency with them.

(c) The bench build type (release settings, so the app is not debuggable; signed with the debug key,
so the androidTest APK can instrument it and it installs over the debug build whose `run-as` put the
files into the app's files dir), `testBuildType = "bench"`, `keepDebugSymbols` (libraries packaged
byte for byte), `BuildConfig.LITERT_VERSION` and `BuildConfig.TDT_DECODER_BLOB`.

(d) `BenchFrontActivity` (bench build type only): a window the tests keep in front, so the process
runs in the top-app cpuset; it loads nothing.

(e) `SigbufBenchTest` (androidTest): MainActivity.preparePipeline for a `-tdt` entry and
MainActivity.processFileAudio's steps, one after the other per window on the test thread (the
activity overlaps them in three coroutines; the tokens are the same, the times do not overlap). Per
window: the token ids and time indices the decoder yields, whether the sequence ended, and the mel,
encode (`recognize()`) and decode (the time inside the token sequence's iterator calls) times; per
row the text the merger builds (what the activity would show), errors, thermal status. `max_tokens`
stops reading a window's sequence (the window is marked `capped`). `pace ceiling` waits before each
row until every cpufreq policy's ceiling is back at its maximum (at least 0.5 s, at most 60 s).
Model files are read from the files dir only (the remote URLs are emptied: a missing file stops the
run).

(f) `SigbufDecoderTest` (androidTest): `LiteRtRunner` builds the model as the app does (the decoder
factory hands the test the `CompiledModel` and the `TdtDecoder`); per window an encode run on an
all-zero input into encode output buffers of the test's own, the file's encoder output written into
that buffer, then `TdtDecoder.decode` from it. `model_file` replaces the entry's file (the f32 file
on the CPU).

(g) `SigbufIo.LogcatTap`: each test reads `logcat -v threadtime --pid=<its pid>` while it runs and
keeps every E / F line and every line naming a memory handle or 6004 (`<tag>.log.txt`); it counts
all lines, E lines, `Failed to find memHandle`, 6004, `QnnMem_register started`,
`QnnMem_deRegister started` and `QnnGraph_execute done` (the run's end line / JSON `log`).

(h) `SigbufIo.tdtDecoder` (form 2's check build): the TdtDecoder MainActivity builds for the
accelerator. On the change's branch the test finds TdtDecoder's three-argument constructor (reflection)
and passes `separateBuffers = (accelerator == NPU)`, the rule of form 2's `MainActivity.kt`; on main's
branch there is no such constructor and the test builds `TdtDecoder(model, config)`, as main's
MainActivity does. The header's `tdt_separate_buffers` says which (null = main).

(i) `SigbufMainActivityTest` (hold 3): MainActivity itself builds the decoder. The test launches
MainActivity, writes the entry and the backend into its `model_selector` / `backend_selector` and
calls its private `preparePipeline` through reflection (what picking an item calls), waits until the
activity's `speechRecognizer` is a new one, and reads `LiteRtRunner.decoder` and its `separateBuffers`
through reflection; the activity's own speech recognizer, audio preprocessor and tokenizer then take
WAV files through MainActivity's file steps. MainActivity uses the entry's own config (remote URLs
kept): the test stops before the activity is asked to load when one of the entry's files is missing
from the files dir. `BuildConfig.MAIN_ACTIVITY_BLOB` names the built `MainActivity.kt`.
