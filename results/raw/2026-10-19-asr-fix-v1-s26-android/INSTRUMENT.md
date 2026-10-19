# The instrument: what the decoder-fix build changes in the sample app, and why

App: `google-ai-edge/litert-samples` `samples/litert/speech_recognition/AndroidApp` at upstream
`d15f8ae9`, plus the sustained-run benchmark commits `89f0c45e` + `289d4672` (asr-litert-app-v1:
`CpuOptions(numThreads = 4)`, the 30 s entry, LiteRT 2.2.0 with the Qualcomm runtime in the APK,
`AsrBenchTest`), the burst commits `ddbb14c7` + `5f23093f` (asr-burst-v1: the sherpa-onnx AAR, burst
pacing, the `bench` build type, `BenchFrontActivity`), plus this round's commit `6885e170` on branch
`asr-bench-s26-fix` (not pushed). `instrument.patch` =
`git diff 5f23093f -- samples/litert/speech_recognition` (this round's change only, 8 files).
Definition of the task: `docs/asr-fix-v1.md`. Versions and hashes: `LOCK.json`.

## Not changed

FileAudioSource, MelSpectroProcessor (jLibrosa), LevenshteinTokenMerger, HuggingfaceTokenizer,
ModelMetadataManager, `model_metadata.json` and MainActivity are as in `5f23093f`; so are the window
(30 s), the overlap (2 s), the merger, the mel, the model file and its encoder and decoder
signatures, the burst pacing, the front window and the bench build route of asr-burst-v1. With
`tdt_fix=false` the decoder runs the loop it ran before (below) and the test calls the recognizer as
MainActivity does.

## Changed

(a) The loop, moved. `TdtDecoder.decode`'s greedy loop is now `TdtGreedyLoop.decode`, a function that
drives the decoder network through two calls: `run(stateful, tokenIds)` (write the token ids into
decode's or decode_1's input, run that signature, read its logits) and `adoptStates()` (swap the
input and output LSTM state buffers). TdtDecoder implements the two with its CompiledModel buffers
as before and zeroes the states at the start of each window as before. With the default arguments
(time limit = maxTimeIndex, no symbol cap) the function is the old loop. JVM test
`TdtGreedyLoopTest`: a line-for-line copy of the old loop (5f23093f = upstream d15f8ae9, last changed
by 8a32fa03) on a fake model is the reference; over 1440 random decodes (maxTimeIndex 1 / 7 / 63 /
375, 1 / 2 / 4 token slots, with and without decode_1, three blank / zero-duration mixes, a different
prediction at every run, time index and slot) the function yields the same (token, time) pairs and
makes the same network calls (signature, token ids, state buffer) in the same order. Two deliberate
breaks of the function (adopting the states on a blank too; reading slot 0 instead of the token's
slot) each fail 3 of the 12 tests (mutation check before the commit).

(b) The fix, behind `TdtDecoder(fixDecodeLoop = true)` (default false). As NeMo's greedy TDT decoding
does: (1) when the recognizer is told that the first n feature frames of the window carry audio, the
loop stops before time index min(maxTimeIndex, ceil(n / 8) + 4) (FastConformer encodes n frames to
ceil(n / 8); 4 frames of margin, the 2026-09-25 omni patch 06's value) instead of decoding the
zero-padded rest of the window; (2) after 10 non-blank tokens at one encoder frame the loop moves to
the next frame (a non-blank token with duration 0 does not advance the loop; without a cap it can
repeat without end: the test's `upstreamLoopNeverEnds_onARepeatedZeroDurationToken`). The end marker
keeps the timestamp maxTimeIndex (the merger shifts the next window's timestamps by it).

(c) How the decoder learns n: an argument added to the interfaces, with default implementations
that ignore it — `SpeechRecognizer.recognize(features, validFeatureFrames)` and
`LiteRtRunner.Decoder.decode(buffers, validFeatureFrames)`; the one-argument `recognize` passes
`ALL_FRAMES` (-1, every frame). Reading n from the features was not possible on the file path:
FileAudioSource hands every window over as a full `samplesPerInterval` buffer (480,000 samples for
30 s) and fills the part after the audio with exact 0.0f, so MelSpectroProcessor's
`validFrames = rawSpeech.size / hopLength` is 3000 for every window and its normalization runs over
all 3000 frames, the padded ones included; no feature frame is written as 0.0. So the count comes
from the raw window: `AsrBenchTest`'s preprocessing coroutine counts v = the samples up to and
including the last non-zero one (`bench/ValidLength.kt`, before the mel; outside `mel_ms`, inside the
utterance time) and n = floor(v / 160), and hands both on with the features through the channel
(a `Window`). A full window has v = 480,000, n = 3000 and decodes every frame. With `tdt_fix=true` the
recognition coroutine calls `recognize(features, n)`; with `tdt_fix=false` it calls
`recognize(features)` (MainActivity's call) and the decoder ignores the count.

(d) Records. Header: `tdt_fix`, `tdt_decoder`, `tdt_max_symbols_per_step`, `tdt_time_limit` (the
rule), `hop_length`. Each utterance row (and the warm-up row): per window `window_valid_samples` (v),
`window_valid_frames` (n), `window_decode_frames` (the time index the loop stopped before; 375 =
every frame of the 30 s export), `window_decode_steps` (network runs), `window_capped_frames` (frames
the cap moved past), from `TdtGreedyLoop.Stats` after the window's token sequence ended.

(e) `applicationIdSuffix = ".burstfix"`: the burst build (`….asr.burst`, asr-burst-v1) and the
sustained build (`….asr`, asr-litert-app-v1) stay installed on the same phone between their rounds'
sittings; this build never replaces their APKs or files. Test package `….asr.burstfix.test`.

## Compiled code under instrumentation

`cmd package compile -m speed -f` compiles both packages, but under `am instrument` the test APK
joins the app's class path, the class loader context no longer matches the one the code was
compiled for, and ART does not use the app's or the test's compiled code (asr-burst-v1, 2026-10-19
16:15: ART's "ClassLoaderContext … mismatch" lines in the load log, `oat_files_mapped` = the two
`base.vdex` only). The app's Kotlin / Java (FileAudioSource, jLibrosa's mel, TdtGreedyLoop, the
merger) then run on ART's JIT of a non-debuggable build; every run transcribes W before the timed
rows, and the summary lists the first and last 10 rows' per-window mel / encode / decode ms
(`warm_check`). Measured as it is (the lane's choice, LANE §0 amendment 5).

## What a number covers

As in asr-burst-v1 (`docs/asr-burst-v1.md`): utterance time = from opening the WAV to the merger
taking the last token (`SystemClock.elapsedRealtimeNanos`); wait = from the end of the previous
utterance to the start of this one; load = the LiteRtRunner constructor (CompiledModel.create, the
decoder's and the runner's buffers); memory = VmHWM of the app process (the instrumentation process:
ART, the test runner, the front window, the engine); identity = the runtime's own lines in the app
process (`<tag>.load-logcat.txt`) and the native libraries it mapped (footer `native_libs_loaded`,
`native_libs`). Decode frames = `window_decode_frames` above.
