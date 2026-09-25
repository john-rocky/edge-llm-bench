# 2026-09-25 ASR real-time factor, v1 — iPhone leg (iPhone 18 Pro): identities

Task family definition: `docs/asr-rtf-v1.md` (the "iPhone leg" section). Cells: the `ios`
rows of `matrices/asr-rtf-v1.cells`, run by `scripts/asr_rtf_iphone.py
matrices/asr-rtf-v1.cells --campaign 2026-09-25-asr-rtf-v1-iphone18pro` in three
invocations of the same sitting (`--only moonshine`, `whisper`, `parakeet` back to back
from 17:48 JST, then `--only Qwen3` after the Fengwu trigger-B cell; `runlog.txt` and
`session_provenance.txt` carry every invocation). Numbers and findings: `NOTES.md`. One JSONL
per cell, one record per app launch; the engine's stderr for every launch under `logs/`
(`*_run<N>.stderr.log`, with the devicectl console beside it).

## Device

iPhone 18 Pro (`iPhone19,2`, "arm64e.x1" as devicectl names the CPU), iOS 27.0 (24A437),
devicectl `C7A74909-7573-5A0F-9201-F7D03DC811EF`, UDID `00008160-000038CA02C00036`, on USB,
charging throughout. First measurement of any kind on this phone (a new column: its rows do
not continue the iPhone 17 Pro's). No lock file exists for the iPhone runner; the probe
list of the device-busy rule was run before the first launch (no sibling driver, no hold
file, the two sibling sessions that could hold a phone answered by message).
`ProcessInfo.thermalState` before and after every launch, the battery level and state and
low-power mode are in every record (`conditions.thermalInitial/Final`, `device.*`).

## Instrument

LiteRT-LM `main` at `66058c82edacb485443ed69724f273c18a7c5b43` (2026-09-24 18:45 -0700,
"Split OmniSession::AudioInput into AudioInput and AudioInputMetadata") — the commit the
2026-09-25 Omni ASR WER session built for the Mac and the S26; worktree
`~/code/litert-lm-asr-ios-wt` (detached, LFS skipped except the iOS Metal dylib).
Between `1dadd00c` (the Mac and Android legs) and this commit `omni/asr/model_metadata.json`
is byte-identical (sha256 `960747e5fe316e25fc1cfca3…` both) and `omni/asr/` changed in the
session plumbing only (OmniSession refactor, a thread pool in `AsrEngine`, ten-line edits in
both text mergers; `git diff --stat 1dadd00c 66058c82 -- omni/asr/`). The rows stamp
`engineVersion: main@66058c82` and are never pooled with the `1dadd00c` rows.

- Static library: `bench_ios/asr_bench_shim.{h,cc}` + `BUILD` (this repo:
  `tools/asr-bench-ios/`), a C function around `AsrEngine::Create` + `FileAudioSource` +
  `CreateSession` + the `ProcessNext`/`Flush` loop of `omni/asr/asr_runner.cc`, with the
  same config assembly (`PopulateConfigFromMetadataJson`, `--model_path` override, merger
  and backend flags) and the same `Starting speech recognition` / `Finished speech
  recognition` log lines. Built with `bazelisk build --config=ios_arm64
  //bench_ios:asr_bench_static` (rules_apple 3.22.0 `apple_static_library`, minimum iOS 17.0,
  bazel 7.6.1, Xcode 27.0 27A266a, `-c opt` from `.bazelrc`; 5,077 actions, 9 min with a warm
  repository cache) → `libasr_bench_static.a` 217,683,616 B. It links
  `//runtime/executor:default_static_gpu_accelerator`, which is empty in the OSS tree, so the
  GPU comes only through the dylib below. The archive carries compiler-rt's
  `InstrProfiling*.o` (the LLVM profile runtime, pulled in by a Rust dependency's
  `profiler_builtins`); no engine object is instrumented, and the runtime's exit-time write
  of `default.profraw` fails in the app sandbox ("LLVM Profile Error … Operation not
  permitted" on every console) with no other effect.
- App: `ios/AsrBench` (ObjC++ shell, `project.yml` → xcodegen 2.44.1, bundle id
  `com.daisukemajima.asrbench`, team `MFN25KNUGJ`, Release, `-ObjC -all_load`), built with
  `xcodebuild -destination "platform=iOS,id=<UDID>" -allowProvisioningUpdates
  -allowProvisioningDeviceRegistration` (derived data `.build/dd-asrbench`). The phone was
  registered in the team profile at 17:45 JST after the owner signed the developer account
  into Xcode (before that: "No Accounts" from xcodebuild and `ApplicationVerificationFailed`
  from `devicectl device install app`). Installed 17:45:4x JST.
- GPU accelerator: `prebuilt/ios_arm64/libLiteRtMetalAccelerator.dylib` at `66058c82`
  (LFS object sha256 `12b51bbdb7ca7511af1e901f1d514d49d9a5513c47bf51ba761b123536a1a3c7`,
  12,658,376 B; the 1dadd00c one is `2cbff000…`, 12,655,904 B), embedded in the app's
  `Frameworks/` and signed with the app's identity. The runtime's `gpu_registry.cc` tries
  `libLiteRtGpuAccelerator.dylib` then `libLiteRtMetalAccelerator.dylib` by bare name; the
  app `chdir`s to `Frameworks/` and `dlopen`s the absolute path first (RTLD_GLOBAL) before
  creating the engine, and the console shows `Attempting to load GPU
  accelerator(libLiteRtMetalAccelerator.dylib).` → `RegisterAccelerator … name=GPU Metal` →
  `Dynamically loaded GPU accelerator(libLiteRtMetalAccelerator.dylib) registered.` →
  `delegate_metal.mm … Created a Metal device.` on every GPU launch
  (`conditions.gpuAcceleratorDylib: "loaded"`). CPU launches do not load it
  (`"not requested"`).
- `Frameworks/BUILD_INFO` (stamped as `engineVersion`) and `Frameworks/SHA256SUMS` list the
  archive, the dylib and `model_metadata.json`; a copy sits in
  `.build/asr-runner-66058c82-ios/`.

## Models, tokenizers, audio

The four litert-community artifacts named by `model_metadata.json`, from the host's HF
cache (revisions and sha256 in every record's `model` and `provenance`): the same files as
the Mac and S26 legs for moonshine (`97abdeea…`), whisper (`6748ac56…`), parakeet
(`334745b8…`) and their tokenizers (`6579793…`, `27fc476b…`, `bd321b09…`); the Qwen3-ASR
`.litertlm` was re-downloaded from the Hub on 2026-09-25 (another lane's disk cleanup had
evicted it; its sha256 is in the record and equals the 09-19 records' `d4444d51…` file if it
matches). Staged with `devicectl device copy to` into the app's data container under
`Documents/asr/models/` (and `Documents/asr/bin/model_metadata.json`,
`Documents/asr/audio/librispeech-dev-clean-1272-82s.wav` — the same 82.335 s stream, sha256
in `session_provenance.txt`). No tokenizer file exists for Qwen3-ASR (the bundle carries it;
the metadata has no `tokenizerUrl`).

## Protocol

The engine defaults, as on the Mac and the S26: chunk = the model's export window
(5,000 ms; whisper 30,000 ms), overlap 0.4, `timestamp` merger, 4 threads, GPU precision
fp32. One app launch per run, three runs per cell, 45 s between launches, 90 s between
cells (parakeet and Qwen3-ASR rows: 60 s from the cells file), the app terminated by the
driver's `--terminate-existing` before each launch. Timing is the phone's monotonic clock
inside the app (`std::chrono::steady_clock`): `loadTimeSeconds` = launch → `Starting`
(argument parsing + `AsrEngine::Create` + `CreateSession`), `asrProcessingSeconds` =
`Starting` → `Finished`, first-text latency = `Starting` → the first confirmed text;
`memoryPeakFootprintMB` / `memoryPeakResidentMB` are the process's `phys_footprint` /
`resident_size` sampled every 100 ms. `hostWallSeconds` is the devicectl round trip and is
not a measurement.
