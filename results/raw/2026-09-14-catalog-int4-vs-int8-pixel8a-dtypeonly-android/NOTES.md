# Catalog X1 / K1 follow-up on the Pixel 8a GPU — a DTYPE-ONLY int8 / int4 pair, sitting 1 (2026-09-14)

The 2026-09-13 pair (`results/raw/2026-09-13-catalog-int4-vs-int8-pixel8a-android/NOTES.md`) compared the
published CPU-recipe INT8 file with the published GPU-graph wi4b32 file, so its whole-model difference mixed the
attention/KV graph into the weight dtype. Today's pair is one litert-torch main (6d4c622) export of Qwen3-1.7B per
recipe with every other flag identical (fused qkv / gate_up, `odml.rope` + `odml.cache_update` composites, bool
mask, fixed prefill 1024, cache 4096 through the 4099 magic number, header max_num_tokens 4096) —
`dynamic_wi8_afp32` vs `dynamic_wi4b32_afp32`; the two TFLite graphs differ only in the FULLY_CONNECTED weight
dtype (inventories and export record: litertlm-convert `qwen3_gpuopt_work/2026-09-14-int8-int4-dtypeonly.md`,
`evidence/ops_dtypeonly_*.txt`). Static weight bytes per token are the same two figures as on 2026-09-13:
1720.9 MB (int8) / 968.2 MB (int4). Same runtime and method as 2026-09-13: LiteRT-LM v0.16.0 pinned binary, GPU
backend (ML Drift, OpenCL on Mali), rebooted first (uptime 11.3 h), `run_session.py` beside this file (anchors as
their own campaign, admission by `scripts/dashboard_job.admit` — now the engine-version-matched reference,
e306445: ratio 1.059 vs the newest b8999 session; payload re-judged 1.069), thermal gate on (every run nominal),
runs=3 interleaved per round, 07:54–09:14. Cells: `matrices/catalog-int4-vs-int8-pixel8a-dtypeonly.cells`, profile
pair `…-dtypeonly-profile.cells`.

**Prediction written before the sitting** (handoff item 1): with the graph held constant, the int8 file decodes
about 12 % faster than the int4 file on this phone (the 2026-09-13 GEMV difference, 11.8 ms/step, on an equal
attention/KV graph). **Outcome: the opposite** — see the profile pair; and the int8 file's text is garbage on this
path, which is what sitting 2 (`…-dtypeonly-norope-android`) fixes.

## Speed rows (short-chat, GPU, the bundle's template default = thinking on)

| file | weight MB / token | decode tok/s | runs | generated tokens | text |
|---|---|---|---|---|---|
| wi8 `Qwen3-1.7B_wi8_gpuflags.litertlm` (`litert-local/Qwen3-1.7B-wi8-gpuflags`) | 1720.9 | — (not a measurement) | 7.05 (cache build), 6.40, 6.42 | **5** in every run | `</think>.setVertical-align-center` then a stop |
| wi4b32 `Qwen3-1.7B_wi4b32_gpuflags.litertlm` (`litert-local/Qwen3-1.7B-wi4b32-gpuflags`) | 968.2 | **10.41** | 10.41 (cache build), 10.41, 10.57 | 129 | fluent, **off-prompt**: `</think>` then "The word **"explain"** means to describe…" — the same sentence the published wi4b32 file produced here on 2026-09-13 (and on the Galaxy S26) |

The wi4b32 row is the 2026-09-13 published-file number again (10.47) — same graph family, same kernels.

## Per-op pair (`./bench profile`, 128x256, max_num_tokens 1024, GPU; 256/256 steps recorded on both)

The native benchmark forces 128 prefill + 256 decode tokens whatever the model emits, so the op timings are those of
the two graphs even where the text is wrong.

| file | control tok/s | wall ms/step | weight GEMV ms/step | attn+KV | xfer | other | unprofiled | launches/step | GEMV GB/s |
|---|---|---|---|---|---|---|---|---|---|
| wi8 | 8.65 | 115.6 | **82.4** | 3.0 | 5.9 | 3.9 | 20.3 | 795 | **20.9** |
| wi4b32 | 10.65 | 93.9 | **54.6** | 3.2 | 5.8 | 4.1 | 26.3 | 795 | **17.7** |

Per node (decode phase): `fc1x1_int8_weights` 57 × 1.031 ms + `-> add` 56 × 0.399 against `fc1x1_int4_weights`
57 × 0.697 + `-> add` 56 × 0.239. Attention/KV 3.0 vs 3.2 ms, launches 795 on both — the graph is the same.

## Reading

1. **Same graph: int4 wins on Mali, in absolute GEMV time and whole-model.** 54.6 vs 82.4 ms/step in the GEMV
   family, 93.9 vs 115.6 ms/step wall (+23 % decode at ctx 1024); the per-byte penalty of int4 over int8 is
   **1.18×** (17.7 vs 20.9 GB/s), not the 2.24× of 2026-09-13. The 2026-09-13 int8 figure (44.9 ms/step, 38.3 GB/s)
   was the published CPU-recipe file's 197 unfused `fc1x1_int8_weights` nodes at 0.16–0.33 ms each; the fused int8
   matrices of the GPU-graph file (`[12288,2048]` gate_up, `[4096,2048]` qkv) run at 1.03 ms per node, while the int4
   kernel is unchanged between the fused files (0.697 vs 0.675 ms/node). So "int4 GEMV loses in absolute time on
   Mali" (K1, 2026-09-13) was a property of comparing unfused int8 against fused int4, not of the dtype; on the same
   graph Mali reads like Adreno (int4 ahead, small per-byte penalty). Sitting 2 re-measures on a pair whose text is
   right.
2. **The int8 file collapses on this runtime's GPU path, and the cause is the `odml.rope` composite** — established
   in `diag/` (records, console logs, `run_diag.py`; one GPU run per variant, thermal-gated, under the hold):
   the same wi8 bundle on `--backend=cpu` answers on-topic (614 tokens); dropping `fuse_gate_up`, `fuse_qkv`,
   `use_bool_mask` or the dynamic cache one at a time leaves the 5-token collapse; dropping `apply_gpu_composites`
   gives blank lines to the 4077-token limit; externalizing the embedder gives fluent off-prompt text to the same
   limit; dropping **`use_rope_composite`** (rope inlined) gives an on-topic answer (632 tokens, 8.37 tok/s), and the
   int4 twin re-exported the same way answers on-topic too (670 tokens, 10.11 tok/s). The published wi4b32 file
   (`odml.rope` ×55) and today's rope-composite int4 twin answer the off-prompt sentence on this phone and on the
   S26; the published CPU-recipe INT8 file (inline rope) and the 0.6B wi4b32 file on the Pixel **CPU** (2026-09-11)
   answer on-topic. On the Mac 0.17.0 (WebGPU and CPU) every one of these files thinks and answers on-topic
   (litertlm-convert `qwen3_gpuopt_work/evidence/thinkon_*`). So: on the LiteRT-LM v0.16.0 Android GPU path
   (ML Drift, OpenCL; Mali and Adreno) the `odml.rope` composite does not apply the positions the graph intends —
   the model behaves as if the prompt had no word order (thinking skipped, fluent, off-prompt), and int8 weights
   turn that into an early stop. The 2026-09-13 GPU-graph rows (`Qwen3-1.7B_dynamic_wi4b32_afp32`,
   `Qwen3-0.6B_dynamic_wi4b32_afp32`) were decoding under this defect: their op timings stand (same kernels, same
   shapes), their texts were off-prompt. Not measured: whether the 0.17.0 Android GPU path still has it.
3. `generatedTokenCount` is not comparable across these rows: bundles that declare a `thought` channel (every
   litert-torch main export and the published GPU build) are not capped at the 128-token budget by
   `litert_lm_main --max_output_tokens` when they think (632–670 tokens for the rope-inlined files, 4077 = the
   context limit for the two never-stopping variants), while the rope-composite files skip thinking and stop at
   129–144. The rates are per token either way.

Sitting 2, same day, same method, rope inlined in both files:
`results/raw/2026-09-14-catalog-int4-vs-int8-pixel8a-dtypeonly-norope-android/NOTES.md`.
