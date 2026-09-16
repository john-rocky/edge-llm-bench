# 2026-09-17 Qwen3 GPU-composite bundles on the new prebuilt Metal accelerator dylib (LiteRT-LM main 4453b286) — Mac, LiteRT-LM v0.17.0 CLI

Context: Fengwu Yao (LiteRT, Chat DM "HF Model GPU optimization", 2026-09-17 02:29 JST) pointed at the prebuilt
`prebuilt/macos_arm64/libLiteRtMetalAccelerator.dylib` merged into LiteRT-LM `main` by PR #3605 (commit `4453b286`,
"Update dependencies of litert_lm", 2026-09-15 19:01 -0700; `WORKSPACE` `LITERT_REF = 1901301f`, UPDATED 2026-09-15), to be
pulled with `git lfs pull --include=...` and dropped beside `litert_lm_advanced_main`. This directory records that dylib's
identity and the same two benchmark configs as `2026-09-16-qwen3-composite-dylib-761d99cb-mac/`, now on both dylibs, on the
same four bundles, the same binary, the same host.

- Host: Mac Studio M4 Max 128 GB (Mac16,9), macOS 27.0 (26A428, Darwin 27.0.0). Not idle: other sessions on this Mac
  (load average 7.45 at driver start; `ioreg` GPU "Device Utilization %" sampled 3× before each leg is in `logs/runlog.txt`).
  Accepted on control speed: the release-dylib legs of the bundles without the two composites are re-run today next to the
  new-dylib legs (A/B interleaved), so every comparison is same-session; no strict quiet gate.
- Binary: `litert_lm_advanced_main` built from the LiteRT-LM v0.17.0 tag (worktree `~/code/litert-lm-0170-mac`, built
  2026-09-16 03:25 JST), sha256 `56137e57554be93532d7b84f03717ab275af6b105dd47134d7bfdaca68d52910` — unchanged from 09-16.
  Metal is selected by the run dir (no `--use_metal` in the OSS 0.17.0 CLI): binary + `libGemmaModelConstraintProvider.dylib`
  (`8f89bc92…`) + `libLiteRtTopKMetalSampler.dylib` (`a60e9a6e…`) + ONE `libLiteRtMetalAccelerator.dylib`, no WebGPU dylib,
  `DYLD_LIBRARY_PATH` = that dir → every log reads `RegisterAccelerator … name=GPU Metal`, `Dynamically loaded GPU
  accelerator(libLiteRtMetalAccelerator.dylib) registered`, `delegate_metal.mm:89 Created a Metal device`.
- Accelerator dylibs (`sha256.txt`):
  `run-4453b286/libLiteRtMetalAccelerator.dylib` = the LFS object LiteRT-LM `main` carries since `4453b286`
  (`GIT_LFS_SKIP_SMUDGE=1 git worktree add --detach ~/code/litert-lm-4453b286-wt 4453b286`, then
  `git lfs pull origin --include="prebuilt/macos_arm64/libLiteRtMetalAccelerator.dylib"`, origin =
  https://github.com/google-ai-edge/litert-lm.git), sha256 `dcd3c3ef5e475daa04a32151c1c8bffb31df7095a9633d8200679a7e2167b21a`,
  16,483,888 B, Mach-O arm64, codesign identifier `build_ml_drift_metal_accelerator_dylib`; `otool -L` lists the same seven
  dependencies as the release dylib; `strings` carries the same three kernel names (`flash_decode_sdpa`, `odml.qkv_norm_rope`,
  `odml.sdpa_transposed`). The LFS pointer for this path last changed on 08-27 (`a2491105`, `ac988ae2…`, 11,486,320 B).
  `run-release/libLiteRtMetalAccelerator.dylib` = LiteRT-LM v0.17.0 `prebuilt/macos_arm64/` (`~/code/litert-lm-0170-mac`,
  untouched), sha256 `ac988ae23d4c185f30e5f080f2a317964ec2869783929d04a9f36f1b488189ff`, 11,486,320 B.
- LiteRT ancestry of the pin (`~/code/LiteRT`, `git fetch origin main`, `git merge-base --is-ancestor`): `1901301f` =
  2026-09-15 14:17 -0700 "Internal changes only."; `428d2792` (09-01, sdpa), `e7135510` (09-03, QkvNormRope dynamic head
  attributes) and `761d99cb` (09-05) are ancestors; `89116780` (fused FlashAttention-2 prefill kernel, 09-15 15:19 -0700) is
  the next commit after `1901301f` on main and is NOT an ancestor — as Fengwu's note says.
- Models: APFS clones of `litertlm-convert/qwen3_gpuopt_work/out/p1024_*` (the files published 2026-09-11 to
  mlboydaisuke/Qwen3-{0.6B,4B}-LiteRT-gpu-composites; sha256 identical to the 09-16 run, see `sha256.txt`); "11 flags" =
  with `--use_sdpa_composite` and `--use_qkv_norm_rope_composite`, "9 flags" = the same export without those two. Fresh
  dirs, no mldrift caches, `--disable_cache=true` everywhere.
- Flags (`scripts/leg.sh`, unchanged from 09-16): `b1k` = `--backend=gpu --disable_cache=true --benchmark=true
  --num_iterations=3 --max_num_tokens=1280 --benchmark_prefill_tokens=1024 --benchmark_decode_tokens=256`; `b31k` = same with
  `--max_num_tokens=32768 --benchmark_prefill_tokens=31744`; `run` = `--input_prompt=<996-token passage> /no_think
  --max_num_tokens=4096 --disable_cache=true` (text check); 8Q gate = `scripts/gate8q_adv.py` (one process per question,
  `/no_think`, same 8 questions/regexes as `qwen3_gpuopt_work/gate8q_cli.py`). Driver: `scripts/run_all.sh` (GPU-serial: text
  runs → b1k A/B interleaved new/release → b31k → gates). Every command with its timestamp, GPU-utilization samples and load:
  `logs/runlog.txt`; per-leg summaries: `logs/driver.log`.
