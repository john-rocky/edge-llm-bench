# The instrument: what was changed in the sample app, and why

App: `google-ai-edge/litert-samples` `samples/litert/speech_recognition/AndroidApp` at upstream
`d15f8ae9` (2026-10-16; the app's last upstream change is `ead3948d`, 2026-10-14, LiteRT 2.3.0 +
litert-gpu). Benchmark commits `89f0c45e` + `289d4672` on branch `asr-bench-s26` (not pushed);
`instrument.patch` = `git diff d15f8ae9 289d4672 -- samples/litert/speech_recognition`.
Definition of the task: `docs/asr-litert-app-v1.md`.

## Not changed (the pipeline)

FileAudioSource, MelSpectroProcessor (jLibrosa), LiteRtRunner's model / accelerator / GPU / NPU
setup, TdtDecoder, LevenshteinTokenMerger, HuggingfaceTokenizer, ModelMetadataManager and the
5 s `parakeet-tdt-0.6b-v3` entry are byte-for-byte upstream, except the one line in (a). The window
is the entry's `inputMilliseconds`, the overlap is MainActivity's `FILE_AUDIO_CHUNK_OVERLAP_DURATION`
(2 s), the merger runs with `FILE_MAX_LEVENSHTEIN_DISTANCE` (5) and its other defaults. What the app
does by default is measured as it is, including:

- GPU precision FP32 and constant-tensor sharing: `ModelConfigJson.gpuEnforceFloat32` and
  `gpuShareConstantTensors` default to true and the parakeet entry sets neither.
- NPU HTP performance mode HIGH_PERFORMANCE: `npuHighPerformance` defaults to true.
- No stop at the last frame that carries audio: a 30 s window over a short clip is decoded over the
  zero-padded tail (results/raw/2026-09-25-omni-asr-wer-v1-m4max-mac/NOTES.md §2).
- No cap on symbols per frame in TdtDecoder: a frame can emit tokens without advancing; the
  driver's 10 min stall watchdog restarts the process after the stuck utterance.
- Each window is decoded on its own (TdtDecoder resets the LSTM state at every window).

## Changed

(a) Threads. `LiteRtRunner` sets `options.cpuOptions = CompiledModel.CpuOptions(numThreads = 4)`
for every accelerator (the CPU arm and the CPU fallback of the GPU / NPU arms). Upstream sets no
CPU options; read in LiteRT's source (main at v2.2.0-341), the XNNPACK default is
`TfLiteXNNPackDelegateOptionsDefault()` = `num_threads` 0, no thread pool (in the 2.2.0 release
binary: not checked).

(b) Model files. The driver pushes the four files and copies them into the app's own files dir
with `run-as` (debug APK): `files/parakeet-tdt-0.6b-v3/{model.tflite, model_npu.tflite,
tokenizer.json}`, `files/parakeet-tdt-0.6b-v3-30s/{model.tflite, tokenizer.json}`, the paths
ModelMetadataManager derives. `openOrDownloadFileInternal` finds them and skips the download; no
code change. The sha256 of each copy is read back on the phone (setup.log). The WAV set (2620 files
+ `manifest-device.tsv`) is unpacked the same way into `files/sets/test-clean` with run-as: the
first setup put it in the app's external files dir with adb, where the app could not open it
(`EACCES`; files and directories adb creates there belong to `shell`, `setup.log.attempt1`).

(c) A `parakeet-tdt-0.6b-v3-30s` entry in `model_metadata.json`: the 30 s export of the same model
(`mlboydaisuke/Parakeet-TDT-0.6B-v3-LiteRT`, `parakeet_tdt_0.6b_v3_30s_i8_stateful.tflite`),
`inputMilliseconds` 30000, mel 512 / 128 / `nFrames` 3000 / preemphasis 0.97, start token 8192 —
the 5 s entry's values with the 30 s window. No NPU file (no AOT build exists for it).

(d) NPU runtime and build. LiteRT 2.2.0 instead of 2.3.0 (`-Plitert.version`, default 2.2.0): the
Qualcomm runtime libraries come from the LiteRT v2.2.0 release (`qualcomm_runtime_v81` + QAIRT
2.47.0; v2.3.0 publishes none), so the runtime matches them; 2.2.0 carries its GPU accelerator in
the main AAR (`litert-gpu` only from 2.3.0). The ten Qualcomm `.so` go to
`app/src/main/jniLibs/arm64-v8a` (git-ignored upstream; sha256 = `kev_work/npu/libs/SHA256SUMS`,
LOCK.json) with `useLegacyPackaging` (upstream) and `keepDebugSymbols` (no strip). The
`:litert_npu_runtime_libraries:*` includes and the `runtime_strings` dependency are removed: those
modules are not in the repository (upstream's settings.gradle.kts points to a Google Developers
blog post for installing them; the upstream tree as checked out was not built here).

(e) Measurement. `AsrBenchTest` (androidTest) copies MainActivity's `preparePipeline`,
`processFileAudio`, `transcribeAudio` and the three `schedule*` coroutines (same dispatchers, same
`Channel.BUFFERED` channels) instead of moving them into a shared class, so the app's own sources
stay as they are. Differences from the activity, all outside the timed pipeline or neutral to it:
the WAV is opened with `FileInputStream` instead of `ContentResolver.openInputStream`; the
`withContext(Dispatchers.Main) { updateTranscriptionUI(...) }` hop per decoded token is replaced
by `TranscriptAccumulator` (the text the view would show at the end), so UI drawing is not in the
wall time; the token loop uses the sequence's iterator explicitly to time the decoder separately
from the channel; each file runs in `runBlocking(Dispatchers.IO)` instead of
`lifecycleScope.launch(Dispatchers.IO)`. `BenchIo` (manifest, S4 stride, resume, JSONL rows) is
shared by the JVM tests (`BenchIoTest`) and the instrumented test through a `benchShared` source
directory. `buildConfig` + `LITERT_VERSION` put the requested LiteRT version in the header; the
footer hashes the native libraries the process actually loaded from (`nativeLibraryDir`).

## What a number covers

- Utterance wall: from opening the WAV to the merger taking the last token, on
  `SystemClock.elapsedRealtimeNanos`; per window: mel (`process()`), encode (`recognize()`, which
  runs the encoder), decode (time inside the token sequence's `hasNext()` / `next()`).
- Load: the LiteRtRunner constructor (CompiledModel.create with the accelerators, then the decoder's
  and the runner's buffers); the tokenizer and the mel processor are timed apart.
- Memory: VmHWM of the instrumentation process, which is the app process (ART, the test runner and
  the app together), plus a 1 s sampler of VmRSS / VmHWM.
- Accelerator identity: the lines LiteRT logs in the app process — `<tag>.load-logcat.txt` (the
  test's own `logcat -d --pid` right after the model was built, before the merger's per-token debug
  lines wrap the log buffer) and `<tag>.logcat.log` (the driver's filtered copy of the device log).
