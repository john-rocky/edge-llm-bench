# 2026-09-18 Qwen3 GPU-composite bundles + the prefill-SDPA export on the prebuilt Metal accelerator dylib from LiteRT-LM main 1dadd00c — Mac, LiteRT-LM v0.17.0 CLI

Context: Fengwu Yao (LiteRT, Chat DM "HF Model GPU optimization", 2026-09-18 07:54 JST): "There is a new prebuilt checked in,
feel free to use it, we shall have new prefill performance, and we need `use_sdpa_composite_for_prefill` flag when doing the
export." This directory records that dylib's identity, the two re-exports made with that flag, and the same two benchmark
configs as `2026-09-17-qwen3-composite-dylib-4453b286-mac/`, on the new dylib and on the 09-17 dylib (control), on the same
binary, the same host.

- Host: Mac Studio M4 Max 128 GB (Mac16,9), macOS 27.0 (26A428, Darwin 27.0.0). Idle at the start of the run (09:32 JST: the other session's
  8-round yardstick matrix and the leaderboard session's benchmark_model had ended at 09:15 / 09:19, and both sessions held further
  launches until this run's "done" at 10:53); from 10:2x the leaderboard session ran a DDP upload driver (python, network only) during
  the B round. 1-min load, GPU utilization (3 samples) and any process above 20 % CPU are sampled before every leg into
  `logs/runlog.txt`: `other=[none]` on all 62 legs; load 2.9–7.1.
- Binary: `litert_lm_advanced_main` built from the LiteRT-LM v0.17.0 tag (worktree `~/code/litert-lm-0170-mac`, built
  2026-09-16 03:25 JST), sha256 `56137e57554be93532d7b84f03717ab275af6b105dd47134d7bfdaca68d52910` — unchanged from 09-16/09-17.
  Metal is selected by the run dir (no `--use_metal` in the OSS 0.17.0 CLI): binary + `libGemmaModelConstraintProvider.dylib`
  (`8f89bc92…`) + `libLiteRtTopKMetalSampler.dylib` (`a60e9a6e…`, both from the v0.17.0 release) + ONE
  `libLiteRtMetalAccelerator.dylib`, no WebGPU dylib, `DYLD_LIBRARY_PATH` = that dir → every log reads
  `RegisterAccelerator … name=GPU Metal`, `Dynamically loaded GPU accelerator(libLiteRtMetalAccelerator.dylib) registered`,
  `delegate_metal.mm:89 Created a Metal device`, `cache_dir: :nocache`.
- Accelerator dylibs (`sha256.txt`):
  `run-1dadd00c/libLiteRtMetalAccelerator.dylib` = the LFS object LiteRT-LM `main` carries since `1dadd00c` (Fengwu Yao,
  2026-09-17 15:50 -0700, "Update dependencies of litert_lm"; `WORKSPACE` `LITERT_REF = 0da36b31`, UPDATED 2026-09-17), pulled
  with `GIT_LFS_SKIP_SMUDGE=1 git worktree add --detach ~/code/litert-lm-1dadd00c-wt 1dadd00c` then
  `git lfs pull origin --include="prebuilt/macos_arm64/libLiteRtMetalAccelerator.dylib"` (origin =
  https://github.com/google-ai-edge/litert-lm.git): sha256 `49df4fd58976d981bdb338a7fe8b6ad26424cacbc632d135b6f79b4eb6ee0ed9`,
  16,535,552 B, Mach-O arm64, codesign identifier `build_ml_drift_metal_accelerator_dylib`; `otool -L` lists the same seven
  dependencies as the two earlier dylibs; `strings` carries the 4453b286 dylib's kernel/composite names plus exactly one new
  name, `flash_prefill_sdpa` (with the class name `FusedFlashAttentionPrefillOp`) (`logs/strings_*.txt`). The same commit also moved the LFS pointers of `libLiteRt.dylib` and
  `libLiteRtTopKMetalSampler.dylib` (not used here: the run dir keeps the v0.17.0 sampler, so the accelerator is the only
  changed component between the run dirs); `libGemmaModelConstraintProvider.dylib` is unchanged.
  `run-4453b286/libLiteRtMetalAccelerator.dylib` = the 09-17 prebuilt (LiteRT-LM `4453b286`, LiteRT `1901301f`), sha256
  `dcd3c3ef5e475daa04a32151c1c8bffb31df7095a9633d8200679a7e2167b21a`, 16,483,888 B (identity recorded in the 09-17 directory).
  `run-release/libLiteRtMetalAccelerator.dylib` = v0.17.0 (`ac988ae2…`, 11,486,320 B) — present, not used in today's legs.
- LiteRT ancestry of the new pin (`~/code/LiteRT`, `git fetch origin main`, `git merge-base --is-ancestor`): `0da36b31` =
  2026-09-17 13:55 -0700 (merge of PR #9905); `428d2792` (09-01, sdpa), `e7135510` (09-03, QkvNormRope dynamic head
  attributes), `761d99cb` (09-05), `1901301f` (09-15, the 4453b286 pin) AND `89116780` (fused FlashAttention-2 prefill kernel,
  2026-09-15 15:19 -0700) are all ancestors — 35 commits from `1901301f` to `0da36b31`, among them `1b7a2c23` (short_conv_step
  fusion), `c4acb188` (GPU accelerator Maven target), `876bb8d5` (Metal xcframework fix).
- Exporter and the flag (`~/code/litert-torch-main`, `git fetch upstream main`, upstream = google-ai-edge/litert-torch):
  `use_sdpa_composite_for_prefill` was introduced by `9f8a33f` (Fengwu Yao, 2026-08-31, "Optimize sdpa op."); it is read from
  `extra_kwargs` in `LiteRTExportableModuleForDecoderOnlyLMPrefill.forward` (`core/exportable_module.py`) and sets
  `use_sdpa_composite=True` for the prefill signature, so `odml.sdpa_transposed` composites are emitted there too (the published
  09-11 files have the composite only in `decode`: prefill_1024 574 ops / 0 sdpa composites, decode 372 ops / 28 for 0.6B; 734 / 0
  and 476 / 36 for 4B). The exporter change the FA2 kernel needs is `75370b9` (Fengwu Yao, 2026-09-15, "Skip query head
  packing when using SDPA composite.", `experimental/composites/sdpa.py`). Neither is in `6d4c622` (2026-09-08), the checkout that
  produced the published files. Export today = upstream `main` at `731ef0a` (Weiyi Wang, 2026-09-17 14:31 -0700, "Fix cache update
  in sliding window ring buffer attention"; also the commit that lets plain `use_sdpa_composite` reach the prefill signature),
  detached worktree `~/code/litert-torch-0918-wt`, venv `~/venvs/ltmain0918` = python 3.14.6 + the lane's pinned requirements
  (`qwen3_gpuopt_work/venv_requirements.txt`: ai-edge-quantizer 0.9.0, litert-converter 0.4.0, litert-lm-builder 0.16.1, torch
  2.13.0, transformers 5.14.1 — the same pins as the venv behind the published files) + `pip install --no-deps -e` of the worktree.
  So the only component that moves against the published files is litert-torch `6d4c622` → `731ef0a`; the op-inventory gate
  (`scripts/inventory_gate.py`, `logs/ops_*.txt`) checks that nothing but the prefill SDPA composites changed. The PyPI nightly
  `litert-torch-nightly 0.10.0.dev20260917` carries the flag and `75370b9` (its files match `main` at `1e2d37f`); not used.
- Models: `models/p1024_{06b,4b}_{11flags,9flags}` = APFS clones of the files published 2026-09-11 to
  mlboydaisuke/Qwen3-{0.6B,4B}-LiteRT-gpu-composites (sha256 identical to the 09-16/09-17 runs, `sha256.txt`);
  `models/p1024_{06b,4b}_12flags` = today's exports: the 09-11 11-flag command (his 09-11 command: the 11 flags minus
  `--enable_gpu_dynamic_prefill`, plus `--litert_lm_llm_metadata_override=<LiteRT-LM v0.17.0 models/qwen3/LlmMetadataProto.pbtext>`,
  sha256 `202c21d1…`) + `--use_sdpa_composite_for_prefill=True` (`qwen3_gpuopt_work/chain_p1024_12flags.sh` →
  `export_variant.sh`; export logs `logs/export_p1024_*_12flags.log`, inventories `logs/ops_p1024_*_12flags.txt`). Fresh dirs,
  no caches, `--disable_cache=true` everywhere (`cache_dir: :nocache` in every log; no file other than `model.litertlm` beside a
  bundle after the run).
- Flags (`scripts/leg.sh`, unchanged from 09-16/09-17 except the added `gtimeout 1800` and the two informational modes): `b1k` =
  `--backend=gpu --disable_cache=true --benchmark=true --num_iterations=3 --max_num_tokens=1280 --benchmark_prefill_tokens=1024
  --benchmark_decode_tokens=256`; `b31k` = same with `--max_num_tokens=32768 --benchmark_prefill_tokens=31744`; `run` =
  `--input_prompt=<996-token passage> /no_think --max_num_tokens=4096 --disable_cache=true` (text check); `runv` / `runp` = `run`
  + `--min_log_severity=0` / `--enable_profiling=true` (one informational leg each); 8Q gate = `scripts/gate8q_adv.py` (one process
  per question, `/no_think`, same 8 questions/regexes as `qwen3_gpuopt_work/gate8q_cli.py`). Driver: `scripts/run_all.sh`
  (GPU-serial: compatibility leg → text runs → b1k A/B new/09-17 → b31k A/B → 8Q gates → the 12-flag files on the 09-17 dylib);
  `scripts/orchestrate.sh` runs the exports, the inventory gate and the driver in one go. Pre-registered decision rule:
  `PREREG.md`. Every command with its timestamp, GPU-utilization samples, load and any other >20 % process: `logs/runlog.txt`;
  per-leg summaries: `logs/driver.log`.
- iOS (not measured here; for Fengwu's 08:32 follow-up "it would be nice to have the iOS numbers from oss as well"): the same commit's
  `prebuilt/ios_arm64/libLiteRtMetalAccelerator.dylib` (LFS pull from the 1dadd00c worktree: sha256
  `2cbff000e8ea5dce3ae7fdd2465558508834e6e4debd8f0568c2f4120fd5f6a6`, 12,655,904 B, Mach-O arm64) carries the same kernel/composite
  names as the macOS dylib including `flash_prefill_sdpa` (with the class name `FusedFlashAttentionPrefillOp`); the OSS Swift package (`Package.swift` at 1dadd00c) pulls the binary
  `CLiteRTLM.xcframework.zip` from the v0.17.1 release, so an iPhone measurement would be the same drop-in as on the Mac (release
  runtime + this accelerator dylib). Sizing facts for the two configs on a phone, from the op inventory: the KV cache of the 0.6B
  export is FLOAT32[1, 8, 32771, 128] ×2 ×28 layers = 7.52 GB at the 32k cache length (the runtime resizes it to `--max_num_tokens`,
  so the 1,024 config needs 0.29 GB); the 4B file's single TFLite section is 2,268,553,328 B (loads on an iPhone 17 Pro only with the
  increased-memory-limit entitlement — a 4.24 GB section loaded that way on 2026-09-07).
- iOS, checked further before answering Fengwu's 08:32 follow-up (no device run): the v0.17.1 release's `CLiteRTLM.xcframework.zip`
  (sha256 `c94fc12aa0403cb47208e419cc3bfe258214ea17035f7a63c16de536869f2186`, 121,798,772 B; the OSS Swift package at 1dadd00c pins it)
  unpacks to an `ios-arm64/CLiteRTLM.framework/CLiteRTLM` binary of 60,466,448 B that carries the Metal accelerator inside (strings:
  `Created a Metal device.`, `GPU Metal`, `Statically linked GPU accelerator registered.`, and also the dlopen strings `Attempting to
  load GPU accelerator(%s).` / `libLiteRtMetalAccelerator.dylib`) with the kernel names of the 08-27 generation (`flash_decode_sdpa`,
  `odml.qkv_norm_rope`, `odml.sdpa_transposed`; no `flash_prefill_sdpa`); the v0.17.1 tag (2026-09-13) pins `LITERT_REF = 9fe5be45`, the
  same as v0.17.0, before `428d2792` / `e7135510` / `89116780`, and its `prebuilt/ios_arm64` accelerator pointer is v0.17.0's
  (`be90cfda…`). The v0.16.0 framework the local iOS benchmark build uses (`.build/dd-ios26`, 44,636,312 B) has neither the composite
  kernel names nor the dlopen strings. Whether the v0.17.1 framework would pick up the 1dadd00c iOS dylib placed beside the app is
  untested (needs an app build with that package and a device run); no iPhone measurement was made today.
