# Catalog X1 / K1 follow-up on the Pixel 8a GPU — the DTYPE-ONLY int8 / int4 pair, sitting 2: rope inlined (2026-09-14)

Same day, same method and runtime as sitting 1 (`results/raw/2026-09-14-catalog-int4-vs-int8-pixel8a-dtypeonly-android/NOTES.md`:
LiteRT-LM v0.16.0 pinned binary, GPU backend = ML Drift OpenCL on Mali, `run_session.py` beside this file, anchors as
their own campaign, admission by the engine-version-matched `scripts/dashboard_job.admit`, thermal gate, runs=3
interleaved), one change applied to BOTH files: `use_rope_composite` off, so the rope is plain ops instead of the
`odml.rope` composite that sitting 1's bisect named as the reason the int8 file decoded five garbage tokens and the
int4 file (and the published wi4b32 build) answered off-prompt on this runtime's GPU path. Everything else is
identical: one litert-torch main (6d4c622) export per recipe, fused qkv / gate_up, `odml.cache_update`, bool mask,
fixed prefill 1024, cache 4096 (magic 4099, header 4096); the two TFLite graphs (`prefill_1024` 1364 ops / `decode`
1277 ops) differ only in the FULLY_CONNECTED weight dtype; static weight bytes per token 1720.9 MB (int8) / 968.2 MB
(int4), as before. Export record and sha256: litertlm-convert `qwen3_gpuopt_work/2026-09-14-int8-int4-dtypeonly.md`.
Phone rebooted first (uptime 2.2 h), anchors ADMITTED at ratio 0.916 vs the newest b8999 session, payload re-judged
1.121, every run thermal nominal, 10:05–11:14. Cells `matrices/catalog-int4-vs-int8-pixel8a-dtypeonly-norope.cells`,
profile pair `…-norope-profile.cells`.

**Both files now answer the prompt on this phone's GPU** (thinking on, as shipped): int8 "**On-device AI** means using
a device's own resources to process data, instead of sending it to a cloud or server…"; int4 "On-device AI is like
having a smart computer that does its own thinking and learning…". No gate flag.

## Speed rows (short-chat, GPU, median of the warm runs, cache-building run out — all three listed)

| file | weight MB / token | decode tok/s | runs | prefill tok/s | TTFT s | generated tokens | effective GB/s |
|---|---|---|---|---|---|---|---|
| int8 `Qwen3-1.7B_wi8_gpuflags_norope.litertlm` (`litert-local/Qwen3-1.7B-wi8-gpuflags-norope`) | 1720.9 | **8.30** | 8.46 (cache build), 8.27, 8.32 | 12.3 | 1.67 | 632 | 14.3 |
| int4 `Qwen3-1.7B_wi4b32_gpuflags_norope.litertlm` (`litert-local/Qwen3-1.7B-wi4b32-gpuflags-norope`) | 968.2 | **10.27** | 10.38 (cache build), 10.29, 10.25 | 4.9 | 4.00 | 670 | 9.9 |

Prefill goes the other way: the 19-token prompt through the fixed `prefill_1024` signature takes 1.67 s on the int8
file and 4.00 s on the int4 file (the int4 prefill runs the fused matrices as `convolution(conv_generic)` over the
1024-wide signature). Generated tokens include the thinking; the runtime does not cap the `thought` channel at the
128-token budget.

## Per-op pair (`./bench profile`, 128x256, max_num_tokens 1024, GPU; 256/256 steps recorded on both)

| file | control tok/s | wall ms/step | weight GEMV ms/step | attn+KV | xfer | other | unprofiled | launches/step | GEMV GB/s (static MB / GEMV ms) |
|---|---|---|---|---|---|---|---|---|---|
| int8 | 8.64 | 115.7 | **79.6** | 4.9 | 5.4 | 6.7 | 19.1 | 969 | **21.6** |
| int4 | 10.53 | 95.0 | **52.2** | 3.6 | 5.6 | 4.5 | 29.1 | 969 | **18.5** |

Per node (decode phase): `fc1x1_int8_weights` 57 × 0.953 ms + `-> add` 56 × 0.409 against `fc1x1_int4_weights`
57 × 0.671 + `-> add` 56 × 0.225. 969 launches per step on both (the inlined rope adds 174 small launches over the
composite graph's 795; attention/KV 3.6–4.9 ms). Sitting 1's rope-composite graphs read the same (int8 82.4 / int4
54.6 ms/step), so the rope composite changed the text, not the GEMV time.

## Reading (this pair supersedes the 2026-09-13 Pixel 8a reading of K1 / X1)

1. **Same graph, same phone: int4 wins.** GEMV family 52.2 vs 79.6 ms/step (int4 reads 56 % of the bytes in 66 % of
   the time), whole model 95.0 vs 115.7 ms/step at ctx 1024 (+22 % decode) and 10.27 vs 8.30 tok/s on short-chat at
   the 4096 context (+24 %). The per-byte penalty of the int4 kernel over the int8 kernel is **1.17×** (18.5 vs 21.6
   GB/s) — the Adreno-class figure (1.22× on the S26), not the 2.24× read on 2026-09-13.
2. **What the 2026-09-13 2.24× was.** That pair set the published CPU-recipe INT8 file (197 unfused
   `fc1x1_int8_weights` at 0.16–0.33 ms/node, 44.9 ms/step, 38.3 GB/s) against the fused int4 GPU build. On this
   delegate the int8 kernel is far less efficient on the fused shapes (`[12288,2048]` gate_up, `[4096,2048]` qkv:
   0.95–1.03 ms/node, 21–22 GB/s) while the int4 kernel reads the same in both int4 files (0.67–0.70 ms/node, 17–18 GB/s) — both of which are
   fused, the published wi4b32 build included, so no unfused int4 file has been measured (corrected 2026-09-15; the
   earlier wording "the same fused or not" claimed a pair that does not exist).
   So "int4 GEMV loses in absolute time on Mali" was the fusion, not the dtype; the dtype-only answer on Mali is
   the same as on Adreno: int4 ahead, small per-byte penalty. The prediction in the handoff (int8 ~12 % faster
   once the graph is equal) fails, and K1's "Metal magnitude on Mali" line is withdrawn for the Pixel 8a.
3. **Fusion costs int8 on this delegate.** Between the published unfused int8 file and this fused int8 file the
   GEMV family goes 44.9 → 79.6 ms/step for the same 1720.9 MB — an unfused int8 export would very likely be the
   faster int8 file on Mali (not measured as a pair; the 2026-09-13 unfused row is the evidence).
4. The whole-model gain of the published wi4b32 file over the published INT8 file on 2026-09-13 (7.53 → 10.47) was
   the attention/KV graph (56.1 → 5.7 ms/step) plus, it turns out, a GEMV loss that the fusion — not the dtype —
   explains; a fused-int8 GPU-graph file is slower than the unfused one it replaced.
5. The `odml.rope` defect on the v0.16.0 Android GPU path (sitting 1's NOTES.md, `diag/`) means every 2026-09-13
   GPU-graph row (published wi4b32 1.7B and 0.6B) was decoding off-prompt text; their timings stand, their texts did
   not answer. The 0.17.0 Android GPU path does not have it — measured 2026-09-14 on the Galaxy S26 (Adreno) with the
   OSS v0.17.0 CLI and the 0.17.0 AAR, v0.16.0 re-run the same hour as the control
   (`results/raw/2026-09-14-rope-composite-0170-s26-android/`); the Pixel 8a (Mali) 0.17.0 leg is not measured.
