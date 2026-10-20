# The instrument: what the NPU check build changes in the sample app, and why

App: `google-ai-edge/litert-samples` `samples/litert/speech_recognition/AndroidApp` at upstream
`d15f8ae9`, plus the benchmark commits of asr-litert-app-v1 (`89f0c45e` + `289d4672`), asr-burst-v1
(`ddbb14c7` + `5f23093f`) and asr-fix-v1 (`6885e170`: `TdtGreedyLoop`, `TdtDecoder(fixDecodeLoop)`),
plus this round's commit on branch `asr-bench-s26-npu` (not pushed; `LOCK.json` app.bench_commit).
`instrument.patch` = `git diff 6885e170 50dfe1d8 -- samples/litert/speech_recognition` (this round's change
only). Definition of the task: `docs/asr-npu-v1.md`. Versions and hashes: `LOCK.json`.

## Not changed

FileAudioSource, MelSpectroProcessor (jLibrosa), CtcDecoder, LevenshteinTokenMerger,
HuggingfaceTokenizer, ModelMetadataManager, `model_metadata.json`, LiteRtRunner and MainActivity are
as in `6885e170`; so are the 5 s windows and their 2 s overlap, the decoder loop with and without
`tdt_fix`, the bench build type and `BenchFrontActivity`. With `tdt_buffers=shared` (the default)
`TdtDecoder` uses its buffers as the app does.

## Changed

(a) Package: `applicationIdSuffix ".npucheck"`, so the build installs beside the earlier rounds'
builds (`….asr`, `.burst`, `.burstfix`) without replacing their APKs or files.

(b) `TdtDecoder(separateSignatureBuffers = true)` (default false), run argument
`tdt_buffers=separate`. The app's decoder hands its buffers across signatures: decode_1 reads and
writes the LSTM states in decode's state buffers, and after each non-blank stateful step the input
and output state buffers swap roles (`adoptStates`); decode and decode_1 both take the encoder's
output buffer. The separate form gives each signature only buffers created for it
(`createInputBuffers(signature)` / `createOutputBuffers(signature)`), keeps every buffer in one role,
and copies instead: per window the encoder output into decode's and decode_1's own input 0 and
zero states into decode's state inputs; at `adoptStates` the state outputs of the last run (decode's
or decode_1's) into decode_1's state inputs. The token sequence it decodes is the shared form's
(the same network inputs at every step); the CPU pair c-cpu-shared / c-cpu-separate checks that on
the phone.

(c) `AsrBenchTest`: `model_file` (a model file under the files dir in place of the entry's own; the
run stops if it is missing, so the app never downloads a different file) and `tdt_buffers`
(shared / separate); both are written to the header. With two instrumented test classes in the APK,
the driver names the class (`-e class`).

(d) `NpuCompareTest` (new, androidTest): one .tflite file on the CPU or the NPU with the options
`LiteRtRunner` builds (CPU in the accelerator set, 4 CPU threads, HTP HIGH_PERFORMANCE on the NPU,
`Environment.create(BuiltinNpuAcceleratorProvider(context))` on the NPU), fixed input files through
`encode` (twice, compared bit for bit), and for the TDT model `decode` / `decode_1` once on given
encoder outputs with zero states; every output written as raw float32 with its statistics and the
buffer types LiteRT asks for (`getInputBufferRequirements` / `getOutputBufferRequirements`). It uses
nothing of the app but `BenchFrontActivity` (in front during the run).

(e) `MelDumpTest` (new, JVM, skipped unless `-Pnpucheck.melDump=<job file>`; `build.gradle.kts`
passes the property to the test JVM): writes the encoder input the app builds for every 5 s window
of a WAV (FileAudioSource → MelSpectroProcessor → `LiteRtRunner.padOrTruncateFeatures`) as raw
float32, with per window the samples up to the last non-zero one and the share of 10 ms frames under
−40 dBFS. These files are B's inputs; they are made on the Mac (the JVM's float maths, not ART's) and
are the same bytes for the CPU and the NPU run.

## Outside git

`app/src/main/jniLibs/arm64-v8a/` (the Qualcomm runtime: LiteRT v2.2.0's qualcomm_runtime_v81
dispatch and compiler plugin libraries and QAIRT 2.47.0's HTP libraries, 10 files; QAIRT licence: in
an APK only) and `app/libs/` (the jLibrosa jar and the sherpa-onnx AAR the build still bundles; no
check of this round loads sherpa-onnx). Their hashes: `LOCK.json`.
