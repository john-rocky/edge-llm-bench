# Catalog X1 / K1 on the Galaxy S26 GPU — int4 vs int8 weight GEMV (2026-09-13)

Question (op-level-catalog §4 X1): the M4 Max Metal path pays a 2.2× per-byte penalty on the
int4×int8 blockwise-gs32 weight GEMV (K1). Does the Android GPU (ML Drift, OpenCL, LiteRT-LM
v0.16.0 pinned binary) show it too?

One sitting, 18:18–19:09, thermal-gated, every run nominal, interleaved per round, runs=3 per cell;
admitted on its anchors (anchor phase ratio 0.973, payload re-judge 0.998 against
`2026-09-13-catalog-int4-vs-int8-s26-anchor-android`), the way the dashboard job judges a sitting
(`run_session.py`, `driver.log` beside this file). Cells: `matrices/catalog-int4-vs-int8-android.cells`,
profile pair `matrices/catalog-int4-vs-int8-android-profile.cells`.

## Speed rows (short-chat, GPU backend, median of the runs `arm_row` keeps — the cache-building
## run out; all three listed)

| file | weight MB / token (static) | decode tok/s | runs | prefill tok/s | effective GB/s (MB×tok/s) |
|---|---|---|---|---|---|
| Qwen3-1.7B `Qwen3_1.7B.litertlm` INT8 (dynamic_wi8_afp32; the card's CPU file, run on the GPU as `litert-local/Qwen3-1.7B-int8`) | 1720.9 | **15.15** | 15.19 (cache build), 15.12, 15.18 | 88.8 | 26.1 |
| Qwen3-1.7B `Qwen3-1.7B_dynamic_wi4b32_afp32.litertlm` (the GPU build) | 968.2 | **33.63** | 33.63, 34.31, 32.41 | 103.8 | 32.6 |
| Qwen3-0.6B `qwen3_0_6b_mixed_int4.litertlm` | 335.5 | **52.97** | 48.69, 55.87, 52.97 | 149.7 | 17.8 |
| Qwen3-0.6B `Qwen3-0.6B_dynamic_wi4b32_afp32.litertlm` | 335.5 | **58.20** | 58.20, 58.25, 58.14 | 203.1 | 19.5 |

Weight bytes per token: `profiles/weight-bytes.md` (static walk of each bundle's decode graph,
blockwise scales included, gather-only tables excluded). int4/int8 bytes for the 1.7B pair = 0.563.

## Per-op pair (`./bench profile`, litert_lm_advanced_main 128x256, max_num_tokens 1024, GPU)

`profiles/PROFILE.md`, `profile-table.csv`; wall ms/step from the unprofiled control, op sums per
recorded decode step from the `--enable_profiling` twin (256/256 steps recorded, no dropped events on
either file).

| file | control tok/s | wall ms/step | weight GEMV ms/step | attn+KV | xfer | other | unprofiled | launches/step | GEMV GB/s (static MB / GEMV ms) |
|---|---|---|---|---|---|---|---|---|---|
| 1.7B INT8 | 15.15 | 66.0 | **26.9** | 22.7 | 1.5 | 1.2 | 13.8 | 939 | **64.0** |
| 1.7B wi4b32 | 29.25 | 34.2 | **18.5** | 0.7 | 1.1 | 1.0 | 12.9 | 795 | **52.4** |

GEMV node types: `fc1x1_int8_weights` (85 + 56 `-> add` + 28 `-> mul` + 28 `-> sigmoid -> mul`,
one per matrix, 197 matrices) against `fc1x1_int4_weights` (57 + 56 `-> add`, 112 matrices — the
wi4b32 build fuses QKV and gate/up). Both files' profiled twins decoded at about half their control
(7.8 vs 15.2; 16.1 vs 29.2), so the profiler's cost is the same factor on both and the ratio between
the rows is the comparable quantity; the absolute GB/s figures carry that cost.

## Reading

1. **The per-byte penalty exists on the Adreno/OpenCL path but is small: 1.22×** (64.0 vs 52.4 GB/s
   inside the GEMV family), against 2.2× on Metal (K1). The int4 GEMVs read 56% of the bytes and take
   69% of the time, so at the kernel level int4 is a net win here (18.5 vs 26.9 ms per step), where
   on the M4 Max it was a loss in absolute time.
2. **The whole-model 2.2× (15.15 → 33.63 tok/s) is mostly not the GEMV.** The INT8 file is the CPU
   recipe's graph: on the GPU its attention + KV path costs 22.7 ms per step (`dynamic_update_slice`
   ×112, `batched_mat_mul_as_fc`) where the GPU build's cache composites cost 0.7 ms. GEMV explains
   8.4 of the 31.8 ms difference; attention + KV explains 22.0. A speed-row comparison of these two
   files is therefore a recipe-plus-graph comparison, never a dtype comparison (the cells file says so).
3. **The 0.6B pair streams the same bytes** (335.5 MB per token, both files) and the GPU build is 10%
   faster (58.2 vs 53.0): graph and recipe, not dtype — consistent with the 2026-09-11 pair (56.9 vs 54.4).
4. Effective whole-token bandwidth on this phone's GPU stays at 18–33 GB/s for every file; the GEMV
   family alone reaches 52–64 GB/s under profiling. No DRAM counters; weights-over-time only.

Not settled here: the same pair on the Pixel 8a (Mali) — `matrices/catalog-int4-vs-int8-pixel8a.cells`
carries the rows as `exclude=device-not-attached`; a DeepSeek q8 / int4-gs32 pair (the K1 artifacts)
on Android; and whether an int8 file exported with the GPU graph flags closes the attention gap.
