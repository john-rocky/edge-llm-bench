# 2026-09-16 Qwen3 GPU-composite bundles vs the Metal accelerator dylib — Mac, LiteRT-LM v0.17.0

Context: Fengwu Yao (LiteRT, Chat DM "HF Model GPU optimization", 2026-09-16 09:45 JST) confirmed that the two composite
load failures of 09-11 (0.6B `flash_decode_sdpa` shape mismatch ×28, 4B `qkv_norm_rope` ×72 + `flash_decode_sdpa` ×36)
are the LiteRT commit v0.17.0 vendors (`9fe5be45`, 08-27) predating the kernel commits `428d2792` (09-01) and
`e7135510` (09-03), and asked for a rebuild of `prebuilt/macos_arm64/libLiteRtMetalAccelerator.dylib` at LiteRT
`761d99cb` (09-05) plus two benchmark configs. This directory records (1) why that dylib cannot be built from the OSS
LiteRT tree, and (2) the two configs measured on what the public runtime has today.

- Host: Mac Studio M4 Max 128 GB (Mac16,9), macOS 27.0 (Darwin 27.0.0). Not idle: another session drives an iPhone from
  this Mac; `ioreg` GPU "Device Utilization %" sampled 3× before each leg is in `logs/runlog.txt` (0–99 %, bursts from
  WindowServer/other apps), load average 4–6. Accepted on control speed: the 9-flag 1,024/256 decode rates (0.6B 244–257,
  4B 105–108 tok/s) match the 09-11 readings on this path (243 / 103 with `litert_lm_main`); no strict quiet gate.
- Binary: `litert_lm_advanced_main` built from the LiteRT-LM v0.17.0 tag (worktree `~/code/litert-lm-0170-mac`,
  `bazel build //runtime/engine:litert_lm_advanced_main`, bazel 7.6.1, Xcode 27.0; built 2026-09-16 03:25 JST for the
  MiniCPM5 profile run), sha256 `56137e57554be93532d7b84f03717ab275af6b105dd47134d7bfdaca68d52910`. Its `--helpfull` has
  no `--use_metal`; the accelerator is selected by the run dir: binary + `libGemmaModelConstraintProvider.dylib`
  (`8f89bc92…`) + `libLiteRtTopKMetalSampler.dylib` (`a60e9a6e…`) + ONE `libLiteRtMetalAccelerator.dylib`, no WebGPU
  dylib, `DYLD_LIBRARY_PATH` = that dir → registry logs `RegisterAccelerator … name=GPU Metal`, `Dynamically loaded GPU
  accelerator(libLiteRtMetalAccelerator.dylib) registered`, `delegate_metal.mm:89 Created a Metal device` (every log).
- Accelerator dylibs: `run-release` = LiteRT-LM v0.17.0 `prebuilt/macos_arm64/libLiteRtMetalAccelerator.dylib`, sha256
  `ac988ae23d4c185f30e5f080f2a317964ec2869783929d04a9f36f1b488189ff`, 11,486,320 B (the same LFS object LiteRT-LM main
  still carries); `run-prebuilt0813` = `macos_arm64/libLiteRtMetalAccelerator.dylib` from
  `https://storage.googleapis.com/litert/binaries/latest/litert_prebuilts.zip` (Last-Modified 2026-08-12, entries dated
  08-13), sha256 `096574cbc65eaf64b583c41505ce3d7780a0277c8cd2b9abe0bb4bfeab351956`, 11,399,984 B — the archive the OSS
  LiteRT build itself consumes (`litert/build_common/special_rule.bzl`, `third_party/litert_prebuilts/workspace.bzl`).
- Models (APFS clones of `litertlm-convert/qwen3_gpuopt_work/out/p1024_*`, the files published on 2026-09-11 to
  mlboydaisuke/Qwen3-{0.6B,4B}-LiteRT-gpu-composites; fixed `prefill_1024`, cache 32771, `LlmMetadataProto` override with
  `max_num_tokens 4096`; fresh dirs, no mldrift caches, `--disable_cache=true` everywhere): see `sha256.txt`.
- Build attempts (`build/`): LiteRT worktree `~/code/LiteRT-761d99cb` at `761d99cb90e20c67efcb3fe1119a60c92381bd1a`,
  bazel 7.7.0 (bazelisk 1.29.0), Xcode 27.0 RC (27A266a), `configure.py` with the macOS CI env
  (`PYTHON_BIN_PATH`, `TF_NEED_CUDA=0`, `TF_NEED_ROCM=0`, `TF_SET_ANDROID_WORKSPACE=0`, `CC_OPT_FLAGS=-Wno-sign-compare`).
  1: `-c opt --config=darwin_arm64` → `Config value 'darwin_arm64' is not defined in any .rc file` (4 s).
  2: `-c opt --config=macos_arm64` → analysis: `ml_drift_delegate/delegate/BUILD:941: no such package 'tools/build_defs/swift'`
  (`aspect_hints = ["//tools/build_defs/swift:no_module"]`; 5 sites; the package does not exist in OSS) (67 s).
  3: same + stub `tools/build_defs/swift/BUILD` (`tools_build_defs_swift_BUILD.stub`) → analysis: `WORKSPACE:402-408`
  `http_archive(name = "ml_drift", strip_prefix = "ml-drift-main")` has no `url` → `At least one of url and urls must be
  provided` for `@ml_drift//ml_drift/common/task:tensor_desc` (0.1 s). Same block at LiteRT origin/main `4ff1d3f57`;
  `github.com/google-ai-edge/ml-drift` 404. The OSS accelerator targets are excluded from LiteRT's own macOS CI
  (`.github/workflows/macos-arm64.yml`: `-//litert/runtime/accelerators/gpu/...`).
- Flags (Fengwu's two configs verbatim minus `--use_metal`; `leg.sh`): `b1k` = `--backend=gpu --disable_cache=true
  --benchmark=true --num_iterations=3 --max_num_tokens=1280 --benchmark_prefill_tokens=1024 --benchmark_decode_tokens=256`;
  `b31k` = same with `--max_num_tokens=32768 --benchmark_prefill_tokens=31744` (the runtime rewrites the bundle's
  32771 cache axis to 32768: `magic_number_utils.cc:120 … target_number=32768`); `run` = `--input_prompt=<996-token
  passage> /no_think --max_num_tokens=4096 --disable_cache=true` (text check); 8Q gate = `gate8q_adv.py` (one process per
  question, `/no_think`, same 8 questions/regexes as `qwen3_gpuopt_work/gate8q_cli.py`). Every command: `logs/runlog.txt`.
- Void rows: the 11-flag bundles on the release dylib load with the 09-11 shape mismatches (28 / 108) and emit token
  salad; their tok/s are recorded for the record only and are not measurements.
