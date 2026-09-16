# 2026-09-16 — Qwen3 GPU-composite bundles: Fengwu's two benchmark configs on the Mac, and why the 761d99cb Metal dylib could not be built

One-line result: **the Metal accelerator dylib cannot be built from the OSS LiteRT tree at `761d99cb`** (the `@ml_drift`
archive has no source URL and ML Drift is not public; two smaller OSS gaps precede it), so the kernel fixes of 09-01/09-03
are still unreachable on this Mac; Fengwu's two benchmark configs were run on the release v0.17.0 dylib instead, on the
nine-flag bundles (correct output) so that the same commands can be re-run the day a dylib built inside Google arrives.
Provenance (host, binary, dylibs, models, flags, build attempts): `PROVENANCE.md`. Every command: `logs/runlog.txt`.

## Numbers — LiteRT-LM v0.17.0 `litert_lm_advanced_main` + release Metal dylib, Mac Studio M4 Max, `--num_iterations=3`

Two processes per cell (A, B); each cell = median of the 3 iterations inside the process. Prefill tok/s = `Prefill Speed`,
decode tok/s = `Decode Speed` (256 tokens after the prefill), TTFT = `Time to first token`. Raw: `logs/SUMMARY_benchmarks.txt`.

| bundle (published 09-11) | config | prefill tok/s A / B | decode tok/s A / B | TTFT s |
|---|---|---:|---:|---:|
| Qwen3-0.6B, 9 flags (`eaa73f7e…`) | 31,744 / 256, `--max_num_tokens=32768` | 1,364 / 1,379 | 68.1 / 67.7 | 23.2 |
| Qwen3-0.6B, 9 flags | 1,024 / 256, `--max_num_tokens=1280` | 9,316 / 9,459 | 246.0 / 249.6 | 0.11 |
| Qwen3-4B, 9 flags (`c65779e9…`) | 31,744 / 256, 32768 | 471 / 471 | 43.5 / 44.0 | 67.4 |
| Qwen3-4B, 9 flags | 1,024 / 256, 1280 | 1,645 / 1,638 | 105.8 / 108.0 | 0.63 |

Fengwu's M4 Pro reference (his 11-flag bundles, kernels before → after the two commits): 0.6B 704 → 1,061 and 4B 235 → 329
tok/s prefill at 31,744; 0.6B 6,058 at ~1k. The rows above are a different bundle (nine flags: no `sdpa_transposed`, no
`qkv_norm_rope`) on a different chip (M4 Max, 546 GB/s vs the Pro's 273), so they are the protocol check and the
"before" for this Mac, not a comparison with his numbers.

Void rows (11-flag bundles on the release dylib; the same 28 / 108 `gpu_model_builder.cc:3897` shape mismatches as
09-11 and token-salad output, `logs/rel_*_11_run.log`; recorded, not measurements): 0.6B 1,024/256 prefill 9,777,
decode 412.8; 4B 1,644 / 135.8 (`logs/rel_*_11_void_b1k.log`). Fengwu's reading of the 09-11 447 stands: the composite
graph runs faster; the kernels at the v0.17.0 pin execute it wrong.

## Correctness on the release dylib (this binary), `logs/rel_*_run.log`

- 0.6B 9 flags: answers the 996-token passage question (industries in order, railway 1879); 8Q gate: see the gate section.
- 4B 9 flags: sawmill → fishing → brick works → tourism, railway 1879 — correct.
- 0.6B / 4B 11 flags: 28 / 108 shape mismatches at load, mixed-script token salad (0.6B), "closures closures …" (4B).
- `litert_prebuilts.zip` (08-13) dylib on the 11-flag bundles: `14 operations will run on the GPU, and the remaining 560 / 720
  operations will run on the CPU` → `llm_litert_compiled_model_executor.cc:1752` error, exit 2 (`logs/pre0813_*_run.log`);
  that dylib predates even `odml.qkv_norm_rope`.

## What would change the picture

A `libLiteRtMetalAccelerator.dylib` built at LiteRT `761d99cb` (or the ML Drift source archive the WORKSPACE expects). The
run dir, the tag-built CLI, the bundles and `scripts/leg.sh` are unchanged; drop the dylib in `run-761d99cb/` and re-run
`scripts/run_all.sh`. LiteRT head is off the table until the exporter CL Fengwu mentioned lands (fused FA2 prefill kernel
+ old exporter = wrong output without an error).

## 8-question gate (release dylib, this binary; `logs/gate8q_*.json`, `logs/gates_driver.log`)

- Qwen3-0.6B without the two composites: **8/8**. Qwen3-4B without the two composites: **8/8**. Qwen3-0.6B composite bundle:
  **0/8** — every question loads with the 28 `flash_decode_sdpa` mismatches and returns the same token salad.

## The 0.17.1 PyPI release (09-15) on the same bundles — WebGPU path, not a way around (`logs/cli171_*_run.log`)

`litert-lm` 0.17.1 is now an 87 KB CLI wrapper over `litert-lm-api` 0.17.1 (macOS wheel `liblitert-lm.dylib` 69,215,088 B,
sha256 `27826147…`; 0.17.0's was `a07182a7…`). `litert-lm run … --backend gpu` (venv `~/venvs/lt0171run`) registers
`GPU WebGPU`; the composite bundles fail exactly as 0.17.0 did on 09-10: `qkv_norm_rope` WGSL `CreateShaderModule` validation
errors (`var w0_x : f32= …`), 12,421 / 12,424 `Validation error` lines, the 28 / 108 shape mismatches; the bundle without
the two composites answers the passage. So the 0.17.1 runtime still carries the pre-09-01 kernels; nothing public on macOS
has the fixes yet.

## Why 9.3k at 1,024 here vs 6.0–6.9k on 09-11 (`logs/rel_06b_9_promptbench_r*.log`)

Measurement mode, not the binary: the same binary + release dylib with `--benchmark=true --input_prompt=<996-token passage>`
(the 09-11 form) reads 6,530 / 6,731 tok/s prefill on the 0.6B bundle without the two composites (09-11 with `litert_lm_main`:
6,225 / 6,264), while `--benchmark_prefill_tokens=1024` (Fengwu's form: synthetic tokens, 3 iterations in one process)
reads 9,316 / 9,459. Fengwu's "6,058 at ~1k" on the M4 Pro is his composite bundle; which form produced it is not stated.
