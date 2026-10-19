# The instrument: what the burst build changes in the sample app, and why

App: `google-ai-edge/litert-samples` `samples/litert/speech_recognition/AndroidApp` at upstream
`d15f8ae9`, plus the sustained-run benchmark commits `89f0c45e` + `289d4672` (branch `asr-bench-s26`;
what they change is written in `results/raw/2026-10-19-asr-litert-app-v1-s26-android/INSTRUMENT.md`
on branch `asr-litert-app`: `CpuOptions(numThreads = 4)`, the 30 s entry, LiteRT 2.2.0 with the
Qualcomm runtime in the APK, `AsrBenchTest`), plus this round's commits `ddbb14c7` + `5f23093f` on
branch `asr-bench-s26-burst` (not pushed). `instrument.patch` =
`git diff 289d4672 5f23093f -- samples/litert/speech_recognition` (this round's change only).
Definition of the task: `docs/asr-burst-v1.md`. Versions and hashes: `LOCK.json`.

## Not changed (the pipeline)

FileAudioSource, MelSpectroProcessor (jLibrosa), LiteRtRunner (with the sustained runs' one line,
`CpuOptions(numThreads = 4)`), TdtDecoder, LevenshteinTokenMerger, HuggingfaceTokenizer,
ModelMetadataManager, `model_metadata.json` and MainActivity are as in `289d4672`; `AsrBenchTest`'s
copy of MainActivity's file path (`processFileAudio`, `transcribeAudio`, the three coroutines and
channels) is unchanged. The LiteRT arms run that path; the window, overlap, merger, decoder and mel
are the app's.

## Changed

(a) sherpa-onnx engine. The release AAR `sherpa-onnx-1.13.8.aar` (k2-fsa/sherpa-onnx v1.13.8 asset,
50,129,134 B, sha256 `633c2432…` = the release's digest) sits in `app/libs/` (not in git) and is an
app dependency, `implementation(files("libs/sherpa-onnx-1.13.8.aar"))`, as an Android app ships it:
its classes and its four arm64 libraries (`libonnxruntime.so` = ONNX Runtime 1.28.2, git commit
33ca962, and `libsherpa-onnx-{jni,c-api,cxx-api}.so`) go into the app APK. No library name collides
with the app's fourteen, so no `pickFirst` was needed; the AAR's libraries need no
`libc++_shared.so` (their DT_NEEDED: libc, libm, libdl, liblog, libandroid and each other). The four
are byte-identical to the jniLibs of `sherpa-onnx-v1.13.8-android.tar.bz2` that the CLI arm's record
lists (`results/raw/2026-10-19-asr-sherpa-v1-s26-android/LOCK.json` on branch `asr-sherpa`).
`AsrBenchTest`'s engine `sherpa` builds
`OfflineRecognizer(config = OfflineRecognizerConfig(featConfig = FeatureConfig(sampleRate = 16000,
featureDim = 80), modelConfig = OfflineModelConfig(transducer = encoder / decoder / joiner
*.int8.onnx, tokens = tokens.txt, numThreads = 4, provider = "cpu", modelType = "nemo_transducer"),
decodingMethod = "greedy_search"))` and leaves every other field at the Kotlin API's default. Per
utterance: `WaveReader.readWave` (sherpa-onnx's own WAV reader) → `createStream` →
`acceptWaveform` (the features are computed here) → `decode` (encoder and TDT greedy search) →
`getResult`; the stream is released after the time is taken. The stage times are in each row
(`stage_ms`).

The CLI arm's config (`sherpa-onnx-offline-parallel`, its stderr line `OfflineRecognizerConfig(…)`)
against the app's: the Kotlin API carries only `sampleRate`, `featureDim` and `dither` of the
feature config; the JNI leaves `low_freq` 20, `high_freq` -400, `normalize_samples` true and
`snip_edges` false at the C++ defaults, the values the CLI printed; the NeMo transducer's `PostInit`
then sets the feature options from the model's metadata in both. The C++ config the app's JNI
built, printed by the one-utterance run with `sherpa_debug=true` (`b-a1-sherpa-cpu-cfg1.load-logcat.txt`;
reassembled from its 128-character pieces into `b-a1-sherpa-cpu-cfg1.config-app.txt`), against the
CLI arm's `OfflineRecognizerConfig(…)` line: 94 fields each, the same fields; the feature config,
the three model files (by name), tokens, `num_threads` 4, `provider` cpu, `model_type`
nemo_transducer, `decoding_method` greedy_search, `max_active_paths`, the hotword, LM and blank
settings are equal. Eight fields differ, none read on this path (a NeMo transducer without
hotwords): `debug` (true in that run only; false in every measured run), `modeling_unit` "" (CLI
"cjkchar"; read only to encode hotwords), Whisper `language` "en" / `tail_paddings` 1000 (CLI "" /
-1), SenseVoice `language` "" / `use_itn` true (CLI "auto" / false), Canary `src_lang` /
`tgt_lang` "en" (CLI ""): the Kotlin API's defaults.

(b) Burst pacing (`pace=burst`, `bench/Burst.kt`, JVM tests `BurstTest`): after the load, the
warm-up utterance W once (outside the timing, its text kept in a `warmup` row); before each
utterance a wait of at least 0.5 s after the previous one ended and until every cpufreq policy's
`scaling_max_freq` equals its `cpuinfo_max_freq` (read every 200 ms, at most 120 s, then start anyway
and mark `wait_timed_out`); while it runs every policy's ceiling is read every 100 ms (plus once at
its start and end); the fall = max over the policies of (1 − min / hw) × 100, one decimal. An
utterance past 15 % runs once more after the ceilings are back and 5 s; the last attempt's row is
written (the first attempt's time, fall and text under `retake`), and a last attempt still past
15 % is `excluded` from RTF_burst. Every policy counts, whichever CPUs the process may use; the fall
over the policies of the process's CPUs is kept beside it (`cap_drop_engine_cpus_pct`).

(c) In front. With `foreground=front` the test starts `BenchFrontActivity` (`ActivityScenario.launch`)
before the load and closes it after the footer: an activity of the bench build type only
(`src/bench/`), in the app's own process, declared `showWhenLocked` / `turnScreenOn` (and set so in
`onCreate`) so it is shown and resumed over the phone's keyguard, `FLAG_KEEP_SCREEN_ON`, one static
line of text, no model. A resumed activity makes its process the top app: the test then waits (at
most 3 s) for `/proc/self/cgroup` to show the `top-app` cpuset. With `require_top_app=true` (every
measured run) a run whose activity is not resumed or whose process is not in `top-app` stops before
the load (a header and a footer with `aborted`), so every arm is measured in the same place. The
header records the activity's state, the keyguard and the screen, and `Cpus_allowed_list` with the
cgroup lines at the start, after the activity and after the load; each row records
`Cpus_allowed_list` and the cpuset at its start, the 1 s sampler both. (`foreground=main` starts
MainActivity instead; its `onCreate` builds the UI and loads no model. Not used in these runs.)

(d) The measured build. Build type `bench` = the release settings (not debuggable, no minify)
signed with the debug key, and `testBuildType = "bench"`. Route on the phone: the debug build of the
same package and key first, whose `run-as` copies the models and WAVs into the app's files dir;
then the bench build installed over it with `adb install -r` (the data stays), the bench test APK,
and `cmd package compile -m speed -f` for both packages. The compiler filter of both
(`dumpsys package`) is read before every run and copied into the header (`dexopt_app`,
`dexopt_test`), with `debuggable` (ApplicationInfo) and the oat / vdex files the process mapped.
**What runs:** not debuggable (`debuggable` false in every header), but the AOT code is not used.
Both packages compile to `speed`, and at process start ART discards both odex files because their
class-loader context does not match the instrumented process's: the instrumentation puts the test
APK on the app's class path. The log lines, in every `<tag>.load-logcat.txt`:
`ClassLoaderContext shared library size mismatch`, `ClassLoaderContext classpath size mismatch`,
`ClassLoaderContext parent mismatch`. The header's `oat_files_mapped` lists the two `base.vdex` and
no odex. So the app's Kotlin / Java (jLibrosa's mel, TdtDecoder's loop, the merger; the sherpa
engine's thin wrapper) runs on ART's JIT, not debuggable, warmed by W before the timed utterances;
the native code (LiteRT, XNNPACK, the Qualcomm runtime, ONNX Runtime) is what it is in any build.
`NOTES.md` has, per LiteRT arm, the per-window mel / encode / decode medians of the set's first and
last 10 utterances.

(e) `applicationIdSuffix = ".burst"`: the sustained-run build (package
`com.google.ai.edge.examples.asr`) stays installed on the same phone between that round's sittings;
installing this build over it would have changed its APK between them. The test package is
`com.google.ai.edge.examples.asr.burst.test`.

## What a number covers

- Utterance time: LiteRT = from opening the WAV to the merger taking the last token (the sustained
  runs' span, with the per-window mel / encode / decode times); sherpa = from `readWave` to
  `getResult`. `SystemClock.elapsedRealtimeNanos`.
- Wait: from the end of the previous utterance (its last attempt) to the start of this one.
- Load: the LiteRtRunner constructor (CompiledModel.create with its accelerators, the decoder's and
  the runner's buffers) / the OfflineRecognizer constructor (its first use loads
  `libsherpa-onnx-jni.so` and `libonnxruntime.so`; newFromFile = the three ONNX Runtime sessions,
  tokens, config).
- Memory: VmHWM of the instrumentation process = the app process (ART, the test runner, MainActivity
  in front, the engine), at the end and from the 1 s sampler.
- Identity: the runtime's own lines in the app process (`<tag>.load-logcat.txt`, the test's
  `logcat -d --pid` right after the load; `<tag>.logcat.log`, the driver's filtered copy) and the
  native libraries the process mapped (footer `native_libs_loaded`) with the sha256 of every library
  in the app's library dir (footer `native_libs`).
