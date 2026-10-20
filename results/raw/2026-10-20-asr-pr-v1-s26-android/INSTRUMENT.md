# What the benchmark build changes (asr-pr-v1)

The measured app is the PR branch `speech-recognition-tdt-decode-stop` of google-ai-edge/litert-samples
(upstream main `e3be1469` + `67415211` + `fb3fb51f`; `LOCK.json` `pr_branch`) with one benchmark
commit on top (branch `asr-bench-s26-pr`, `8b9f5590`; `instrument.patch` =
`git diff fb3fb51f 8b9f5590 -- samples/litert/speech_recognition`). The PR branch's own files —
`TdtDecoder.kt`, `SpeechRecognizer.kt`, `AudioSource.kt`, `MainActivity.kt` and every other file of
the app's pipeline — are not touched by the benchmark commit except `LiteRtRunner.kt` (below).

The benchmark commit:

- `app/build.gradle.kts`: `applicationIdSuffix = ".prcheck"` (installs beside any other build of the
  app); `BuildConfig.LITERT_VERSION = "2.3.0"` (the version of the app's two LiteRT dependencies,
  which stay as the PR branch has them: `litert:2.3.0`, `litert-gpu:2.3.0`); `keepDebugSymbols` for
  the native libraries (shipped byte for byte); the `bench` build type (`initWith(release)` + the
  debug signing key: not debuggable, no minify) and `testBuildType = "bench"`; `buildConfig = true`;
  `src/benchShared/java` for the JVM tests and the instrumented test; the sherpa-onnx v1.13.8 release
  AAR (as in asr-burst-v1 / asr-fix-v1; AsrBenchTest's sherpa engine uses it, no run of this round
  does); the `:litert_npu_runtime_libraries:runtime_strings` dependency removed.
- `settings.gradle.kts`: the `litert_npu_runtime_libraries` modules (not in the repository) are not
  included.
- `app/src/main/assets/model_metadata.json`: an entry `parakeet-tdt-0.6b-v3-30s` for the 30 s export
  of the same model (`mlboydaisuke/Parakeet-TDT-0.6B-v3-LiteRT`, 30 s window, 3000 mel frames).
- `LiteRtRunner.kt`: `CpuOptions(numThreads = 4)` for every accelerator (asr-litert-app-v1's change;
  the app sets no thread count).
- `app/src/bench/`: `BenchFrontActivity` (shown over the keyguard) and its manifest entry.
- `app/src/androidTest/…/AsrBenchTest.kt`: MainActivity's file path on the PR branch copied with timing
  hooks and without the UI — FileAudioSource (30 s windows, 2 s overlap) → MelSpectroProcessor →
  LiteRtRunner + TdtDecoder → LevenshteinTokenMerger in the activity's three coroutines, the decoder
  built as MainActivity builds it (`TdtDecoder(model, config)`), each window's `getNumOfValidSamples`
  handed on with its features and `recognize(features, numOfValidSamples)` called as the activity
  calls it. Per window it records the valid samples, their feature frames (floor(v / 160), for the
  record) and the largest time index of a token the decoder emitted. asr-burst-v1's burst pacing,
  retake rule, front window and top-app check are unchanged.
- `app/src/benchShared/…/bench/BenchIo.kt`, `Burst.kt` and their JVM tests (asr-burst-v1's).

## Compiled code under instrumentation

As in asr-burst-v1 / asr-fix-v1: under `am instrument` ART logs a `ClassLoaderContext … mismatch` for
the app's odex and runs the Kotlin / Java code on its JIT; each process transcribes W first, outside
the timing.
