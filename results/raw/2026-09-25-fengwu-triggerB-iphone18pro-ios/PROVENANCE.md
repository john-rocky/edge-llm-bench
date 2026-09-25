# 2026-09-25 — Fengwu "iOS numbers from OSS", trigger B: the v0.17.x Swift package + the 1dadd00c iOS Metal dylib on the iPhone 18 Pro

Question (standup handoff `2026-09-18-fengwu-ios-xcframework-followup.md`, trigger B): when the
edge-llm-bench iOS app is built on the released LiteRT-LM Swift package and
`libLiteRtMetalAccelerator.dylib` from LiteRT-LM `main@1dadd00c` (the prebuilt with the fused
FA2 prefill kernel, `flash_prefill_sdpa`) is placed in the app's `Frameworks/`, does the runtime
register the dylib (`Dynamically loaded GPU accelerator(libLiteRtMetalAccelerator.dylib) registered`)
or its built-in accelerator (`Statically linked GPU accelerator registered`)? The answer decides
whether the composite files (`p1024_{06b,4b}_12flags`) can be measured on an iPhone before Google
ships an xcframework built from a newer LiteRT.

## Device

iPhone 18 Pro (`iPhone19,2`), iOS 27.0 (24A437), devicectl `C7A74909-7573-5A0F-9201-F7D03DC811EF`,
UDID `00008160-000038CA02C00036`, USB. First measurement of any kind on this phone (a new column;
the promise text of 2026-09-18 said "iPhone 17 Pro" — the 18 Pro is the bench iPhone from
2026-09-25 by owner decision). The phone was registered in the team provisioning profile on
2026-09-25 17:45 JST (profile `9fc6ef49-…`, after the owner signed the developer account into
Xcode 27.0 RC); before that every install failed with `ApplicationVerificationFailed`.

## The package and the framework binary

- `ios/BenchmarkApp/Vendored/LiteRT-LM.v0170` = LiteRT-LM tag `v0.17.0` (`e9fd8c53`, 2026-09-09
  "Update LiteRT-LM Swift package to v0.17.0"), with the lane's `swift/Benchmark.swift`
  `maxNumTokens` patch (`Vendored-patches/0001-benchmark-maxNumTokens.patch`). Its
  `Package.swift` binaryTarget `CLiteRTLM.xcframework.zip@v0.17.0` checksum
  `c94fc12aa0403cb47208e419cc3bfe258214ea17035f7a63c16de536869f2186` — the same checksum the
  `v0.17.1` tag's `Package.swift` carries (read from GitHub 2026-09-25 14:1x JST) and the same
  121,798,772-byte asset on both GitHub releases (v0.17.0 2026-09-09, v0.17.1 2026-09-16): the
  handoff's "v0.17.1 package" and this checkout are the same framework bytes. No release after
  v0.17.1 on 2026-09-25 (trigger A not fired).
- The framework's `ios-arm64/CLiteRTLM.framework/CLiteRTLM` binary: 60,466,448 B, sha256
  `892798555f337315aa89f2f405e3e3b41d68de9d977b15c7d4a4fd3fa637684c` (from
  `.build/dd-mac-0170/SourcePackages/artifacts`, the 2026-09-11 resolution of the same package;
  the iOS build resolves the same zip). Its strings carry both registration paths of LiteRT's
  `gpu_registry.cc` ("Statically linked GPU accelerator registered.", "Attempting to load GPU
  accelerator(%s).", "Dynamically loaded GPU accelerator(%s) registered.") and the leaf name
  `libLiteRtMetalAccelerator.dylib`; no `flash_prefill_sdpa` (the 08-27-generation kernels,
  `LITERT_REF = 9fe5be45`).
- Registration order in LiteRT (`litert/runtime/accelerators/gpu_registry.cc`, read at
  `~/code/LiteRT` 233d09a8): (1) an accelerator handle passed as an environment option,
  (2) `LiteRtStaticLinkedAcceleratorGpuDef` when non-null — set by a static initializer in
  `ml_drift_metal_accelerator.cc` whenever the Metal accelerator is compiled into the binary,
  (3) only then the dynamic loop over `<runtime library dir>/libLiteRtMetalAccelerator.dylib`
  (leaf name when no dir is set — LiteRT-LM sets none). The OSS bazel tree links no static
  accelerator (`//runtime/executor:default_static_gpu_accelerator` is empty), the release
  framework carries the Metal delegate inside ("Created a Metal device." and the kernel names are
  in the binary). The 2026-09-09 iPhone 17 Pro console of the v0.16.0 build already shows
  `[gpu_registry.cc:87] Statically linked GPU accelerator registered.`
  (`results/raw/2026-09-09-dashboard-v1-iphone17pro-ios/console_litert-lm_litert-community_Qwen3-0_6B_short-chat.txt`).

## The dylib

`~/code/litert-lm-1dadd00c-wt/prebuilt/ios_arm64/libLiteRtMetalAccelerator.dylib`: 12,655,904 B,
sha256 `2cbff000e8ea5dce3ae7fdd2465558508834e6e4debd8f0568c2f4120fd5f6a6` (LFS object of
LiteRT-LM `1dadd00c`), Mach-O arm64, install name `@rpath/libLiteRtMetalAccelerator.dylib`, links
only system frameworks (Metal, Foundation, CoreFoundation, libc++, libobjc, libSystem), exports
`_LiteRtAcceleratorImpl`, unsigned in the repo. (For comparison, `main@66058c82` ships a newer
one: 12,658,376 B, `12b51bbdb7ca7511af1e901f1d514d49d9a5513c47bf51ba761b123536a1a3c7`.)

## How the app was built

The shared checkout carries another session's uncommitted `project.pbxproj` (the Xcode GUI signing
edits: team `MFN25KNUGJ`, bundle id `com.example.CoreMLLLMChat`; sha256 before
`798beea743c3259653de1888d6104401f35b8f52fe965af45947920032e1d09e`), so xcodegen was not run.
Instead an untracked copy `ios/BenchmarkApp/BenchmarkApp-v0170.xcodeproj` (git-excluded) points
its LiteRT-LM package reference at `Vendored-v0170/LiteRT-LM`, a copy of `Vendored/LiteRT-LM.v0170`
under a directory named `LiteRT-LM` (SwiftPM derives a local package's identity from the directory
name and refused `litert-lm.v0170` against the resolved graph's `litert-lm`), and its schemes'
`ReferencedContainer` renamed to the copy. Build: `xcodebuild -project … -scheme BenchmarkApp
-configuration Release -destination "platform=iOS,id=00008160-000038CA02C00036" -derivedDataPath
.build/dd-ios-0170 -skipPackagePluginValidation -skipMacroValidation -allowProvisioningUpdates
-allowProvisioningDeviceRegistration ARCHS=arm64 ONLY_ACTIVE_ARCH=YES build` (the package
checkouts were seeded from `.build/dd-mac-0170/SourcePackages` because a fresh clone of the
executorch package timed out on the network). Log: `logs/xcodebuild_ios0170.log`.

The dylib was copied into the built app's `Frameworks/` next to `CLiteRTLM.framework` and signed
with the app's identity (`codesign --force --sign <identity> --preserve-metadata=entitlements`),
then the app itself re-signed; installed with `xcrun devicectl device install app`.

## Model and cell

`litert-local/qwen3-0.6b-wi4b32-gpuopt11` = `p1024_06b_11flags/model.litertlm` (the published
11-flag export, 341,736,912 B, sha256 `bd68576899304644dc391e7d9c1bfa5d6f25a6795b4812d9afe08cb7ae4560e9`,
archive copy `/Volumes/HD-SGDA/archive/litertlm-convert/qwen3_gpuopt_work/out/p1024_06b_11flags/`),
side-loaded to `Documents/models/litert-lm/litert-local__Qwen3-0.6B-wi4b32-gpuopt11/model.litertlm`;
one `short-chat` cell through `scripts/bench_matrix_iphone.sh` (runs=1, the log line is the
measurement; the decode number is not admitted anywhere).

## Result — the framework registers its built-in accelerator; the dylib beside the app is never consulted

Console of the cell (`console_litert-lm_litert-local_qwen3-0_6b-wi4b32-gpuopt11_short-chat.txt`,
18:04:22 JST; the 9-flag control `…gpuopt9…` at 18:05:15 is identical in this respect):

    INFO: [environment.cc:36] Creating LiteRT environment with options
    WARNING: [npu_registry.cc:34] NPU accelerator could not be loaded and registered: kLiteRtStatusErrorInvalidArgument.
    INFO: [accelerator_registry.cc:54] RegisterAccelerator: ptr=0x1058138a0, name=GPU Metal
    INFO: [gpu_registry.cc:109] Statically linked GPU accelerator registered.

three times per launch (every `Environment::Create`), and no `Attempting to load GPU
accelerator(…)` line anywhere: with the released v0.17.x framework the dynamic branch is
never reached, so `libLiteRtMetalAccelerator.dylib` next to the app (signed, in
`Frameworks/`) is dead weight. Trigger B is negative — the composite files cannot meet the
1dadd00c kernels on an iPhone through the OSS Swift package until Google ships an
xcframework whose built-in accelerator is built from a newer LiteRT (trigger A), or
through an OSS bazel build of the C API that links no static accelerator (the
`ios/AsrBench` instrument of the same day shows the dynamic path working on this phone:
`Attempting to load GPU accelerator(libLiteRtMetalAccelerator.dylib).` →
`Dynamically loaded GPU accelerator(libLiteRtMetalAccelerator.dylib) registered.`).

The cell itself reported `YARDSTICK_RUN_FAIL … FAILED_PRECONDITION: Chosen prefill work
group size exceeds available state entries (672).` for both bundles. That is the
instrument's context sizing, not the kernels: the app sizes the KV cache to ≈ prompt +
output for `short-chat` (the log shows the magic number 32771 rewritten to 672 in 482 /
623 tensors), and the export's `prefill_1024` signature needs at least 1,024 entries; the
Mac numbers of 2026-09-18 ran the CLI at `--max_num_tokens` 1,280 and 32,000. A re-run with
`context-tokens=1280` (the app's `--context-tokens`) is the control that shows the framework's
own kernels running these files — see the addendum below when it has run. Nothing from this
directory is a speed number and nothing is admitted to any summary
(`device-jsonl/` stays empty; `SKIPPED.txt` / `summary.md` are the runner's own).

## Addendum 18:15–18:21 JST — the `context-tokens=1280` control (records in `controls/`, deliberately outside `device-jsonl/` so the summary builder never pools them; single cold runs, not measurements)

With the app's KV sized to 1,280 entries both bundles load and run on the framework's
built-in (08-27 generation) Metal kernels: the 9-flag file (`p1024_06b_9flags`,
`eaa73f7e…`) decodes coherent text ("Okay, the user wants to understand on-device AI in
simple terms…") at 174 tok/s decode on the one cold run (a first run that started at
thermal `fair` after the ASR sitting read 174 tok/s too and was quarantined by the gate;
both kept in `controls/`); the 11-flag file (`p1024_06b_11flags`, `bd685768…`, the two
composites `odml.sdpa_transposed` + `odml.qkv_norm_rope` on top) reports 212 tok/s but
decodes garbage ("kếasurableoubtedly rolesentialstag ByVal更是客户提供…") — the rate is void
(benchmark-mode-needs-a-text-check), and it is the iPhone counterpart of the Mac finding that
the composite kernels of the v0.17.0 generation do not run these files correctly (on the Mac
the OSS v0.17.0 GPU path refused the kernels; the built-in iOS accelerator runs them and
produces wrong text). So on the released framework the composite files have no valid iPhone
number at all, and the 12-flag files (which need the fused prefill kernel) were not staged.
Consoles: `console_…gpuopt9…` / `console_…gpuopt11…` (appended per launch), records
`controls/*.json` (the `short-chat` prompt, 19 prompt tokens, 128 generated).
