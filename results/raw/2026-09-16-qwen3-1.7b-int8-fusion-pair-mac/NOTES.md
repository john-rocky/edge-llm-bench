# Does QKV / gate-up fusion cost the int8 weight matmuls on the Mac's Metal path the way it does on the phones? — M4 Max, LiteRT-LM v0.17.0, 2026-09-16 08:14–08:22 JST

**No: on Metal the fused file's weight matmuls are faster.** The 113 fused `fc1x1_int8_weights` nodes take 4.37 ms per decode step
where the published file's 197 unfused ones take 5.05, for the same 1,720.9 MB (341 → 394 GB/s). On the Pixel 8a's Mali the same
two files went 44.9 → 77.2 ms (38 → 22 GB/s; `../2026-09-14-catalog-int4-vs-int8-pixel8a-dtypeonly-norope-android/NOTES.md`,
reading 3) and on the S26's Adreno 26.9 → 30.9. Same caveat as on the phones: the pair is the published CPU-recipe file against a
GPU-graph export, so the files differ in more than fusion (KV path, mask, rope form); the weight-matmul rows are like-for-like
(same matrices, same bytes), the whole-model numbers are not. One run per cell, machine in use — a shares-and-ratio sitting, not a
speed row.

## Per-op pair (`litert_lm_advanced_main` 128x256, max_num_tokens 1024, Metal; 256/257 steps recorded)

| file | control decode tok/s | wall ms/step | op sum | weight matmuls (fc1x1 rows) | attention FCs (`fully_connected`) | attn+KV | other | launches/step |
|---|---|---|---|---|---|---|---|---|
| unfused, published `Qwen3_1.7B.litertlm` (66064a4e…) | 98.65 | 10.14 | 10.12 | **5.05** (85 + 56 + 28 + 28 nodes) | — (attention runs as `batched_mat_mul_as_fc`, 0.94, in attn+KV) | 3.49 | 1.58 | 1,008 |
| fused, `Qwen3-1.7B_wi8_gpuflags_norope.litertlm` (6080fa06…) | 150.13 | 6.66 | 6.97 | **4.37** (57 + 56 nodes) | 0.34 (56 nodes; `prof_table` groups them as gemv, so the gemv family reads 4.71) | 0.99 | 1.27 | 1,012 |

Per node, decode phase: unfused `fc1x1_int8_weights` 1.509 ms/step over 85 nodes, `-> add` 1.380 / 56, `-> sigmoid -> mul` 1.135 / 28,
`-> mul` 1.024 / 28; fused `fc1x1_int8_weights` 3.110 / 57, `-> add` 1.263 / 56. Slice nodes (`strided_slice` and its fused
variants): unfused 0.22 ms/step, fused 0.59. The 56 `fully_connected` nodes of the fused graph are the attention matmuls (the
unfused graph runs them as 56 `batched_mat_mul_as_fc` nodes); the harness's gemv group counts them on the fused side only, on the
Mac (0.34 ms) and on the phones (Pixel 8a 2.39 ms of the 79.6 "GEMV family" of 2026-09-14) — the weight-matmul comparison above
uses the `fc1x1` rows only.

## Reading

1. **Fusion helps the int8 weight matmuls on Metal (−13 %) and hurts them on Mali (+72 % on the fc1x1 rows) and mildly on Adreno
   (+15 %).** The split nodes are cheap on all three (Mac 0.22 → 0.59 ms/step; Pixel 8a 0.7 → 2.5); on the phones the cost sits
   inside the fused `fc1x1_int8_weights` kernels themselves.
2. Whole model on Metal, 98.65 → 150.13 tok/s: as on the phones, mostly the KV path (attn+KV 3.49 → 0.99 ms/step, the
   `dynamic_update_slice` ×112 of the CPU-recipe graph against the cache-update composite) plus the 0.7 ms of weight matmuls.
3. Prefill of the 128-token benchmark prompt goes the other way on the fused file (530 vs 1,709 tok/s) — the fixed 1024-wide
   prefill signature of the export, as on the Pixel 8a (2026-09-14, sitting 2). Not pursued here.

Not measured: the one-flag pair (the same GPU-graph export with fusion off) on any device; a second run; the int4 files.
