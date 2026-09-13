# Catalog X1 / K1 on the Pixel 8a GPU (Mali) — int4 vs int8 weight GEMV (2026-09-13)

The Pixel copy of the Galaxy S26 sitting run earlier the same day
(`results/raw/2026-09-13-catalog-int4-vs-int8-s26-android/NOTES.md`): same four files, same cells
(`matrices/catalog-int4-vs-int8-pixel8a.cells`), same profile pair, LiteRT-LM v0.16.0 pinned binary,
GPU backend (ML Drift, OpenCL on Mali). Phone rebooted first (uptime 54 h > 2 h), BENCH_CPU_MASK=f0
for the llama.cpp anchor, thermal gate on: every run started nominal; the 1.7B INT8 runs ended
light/moderate and the gate waited 12–18 min after each. Sitting 20:37–22:40, admitted on its anchors.

**Admission note.** The anchor phase read ratio 0.513 against "the newest admitted session with this
cell" — that reference (`2026-09-11-minicpm5-2b-crossarm-pixel8a-android`, another lane) ran the
llama.cpp anchor on a newer build, b10903 (55.0 tok/s), where the pin b8999 reads 22–31 in every other
Pixel session (today 28.2; the last b8999 session, `2026-09-11-catalog-x13-pixel8a-android`, 29.7 →
0.95). Same mask, same conditions; the secondary LiteRT GPU anchor read 1.023. The phone was sound;
the admission compared two engine builds. `dashboard_job.admit` does not match the reference on
engine version — a weakness to fix in the job, not in these rows. The payload re-judge is 0.965
against today's own anchor phase.

## Speed rows (short-chat, GPU, median of the runs `arm_row` keeps — cache-building run out)

| file | weight MB / token (static) | decode tok/s | runs | prefill tok/s | effective GB/s |
|---|---|---|---|---|---|
| Qwen3-1.7B INT8 (`Qwen3_1.7B.litertlm`, dynamic_wi8_afp32, `litert-local/Qwen3-1.7B-int8`) | 1720.9 | **7.53** | 7.66 (cache build), 7.37, 7.69 | 34.2 | 13.0 |
| Qwen3-1.7B `Qwen3-1.7B_dynamic_wi4b32_afp32.litertlm` | 968.2 | **10.47** | 10.40, 10.57, 10.47 | 27.8 | 10.1 |
| Qwen3-0.6B `qwen3_0_6b_mixed_int4.litertlm` | 335.5 | **15.23** | 15.51, 15.16, 15.23 | 41.7 | 5.1 |
| Qwen3-0.6B `Qwen3-0.6B_dynamic_wi4b32_afp32.litertlm` | 335.5 | **14.99** | 14.91, 14.99, 15.57 | 55.2 | 5.0 |

## Per-op pair (`./bench profile`, 128x256, max_num_tokens 1024, GPU; 256/256 steps, no dropped events)

| file | control tok/s | wall ms/step | weight GEMV ms/step | attn+KV | xfer | other | unprofiled | launches/step | GEMV GB/s |
|---|---|---|---|---|---|---|---|---|---|
| 1.7B INT8 | 7.69 | 130.0 | **44.9** | 56.1 | 7.7 | 4.2 | 17.2 | 939 | **38.3** |
| 1.7B wi4b32 | 10.59 | 94.4 | **56.7** | 5.7 | 5.4 | 6.4 | 20.3 | 795 | **17.1** |

Per node: `fc1x1_int8_weights` 0.162 ms avg (85 nodes) / `-> add` 0.237 against `fc1x1_int4_weights`
0.675 ms avg (57 nodes) / `-> add` 0.280 — on Mali the int4 kernel's plain node is 4× the int8 node's
time for the same matrix shapes. The profiler's host cost differs wildly between the twins (profiled
decode 0.18 tok/s for INT8 — 24 min for 256 steps — against 4.55 for wi4b32), but the op sums per step
(112.9 and 74.2 ms) both sit inside their control's wall (130.0 / 94.4 ms), so the op times are the
delegate's own timers, not the host stall; the ratio between the rows is the comparable quantity.

## Reading

1. **On Mali the int4 GEMV loses in absolute time, exactly as on Metal.** 56.7 vs 44.9 ms per step
   while reading 56% of the bytes: per-byte penalty **2.24×** (38.3 vs 17.1 GB/s), the same magnitude
   as the M4 Max (2.2×, K1) — and the opposite of the Galaxy S26's Adreno, where the same pair gave
   1.22× and an absolute win for int4 (18.5 vs 26.9 ms). The K1 penalty is therefore not a
   WebGPU/Metal peculiarity; it is the property of two of the three GPU paths measured, and Adreno's
   OpenCL int4 kernel is the exception.
2. **The whole-model gain of the wi4b32 file on this phone (7.53 → 10.47) is entirely the graph.**
   attention + KV 56.1 → 5.7 ms/step (the INT8 file's CPU-recipe `dynamic_update_slice` ×112 and
   `batched_mat_mul_as_fc` on the GPU vs the GPU build's cache composites) pays for the GEMV loss
   (+11.8 ms) twice over. An int8 file exported with the GPU graph flags would, by these numbers,
   decode faster than the wi4b32 file on the Pixel 8a.
3. **The 0.6B pair** (identical bytes, 335.5 MB) is a tie here (15.23 vs 14.99), where the S26 gave
   the GPU build +10%.
4. Effective whole-token bandwidth on the Pixel 8a GPU is 5–13 GB/s; the GEMV family alone reaches
   17–38 GB/s under profiling. Weights-over-time; no DRAM counters.

Not settled here: the DeepSeek q8 / int4-gs32 pair (the K1 artifacts) on Android, and the int8 file
with the GPU graph flags that would hold the attention/KV graph constant.
