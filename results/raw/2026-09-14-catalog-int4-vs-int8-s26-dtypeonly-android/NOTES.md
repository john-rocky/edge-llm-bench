# Catalog X1 / K1 follow-up on the Galaxy S26 GPU — the DTYPE-ONLY int8 / int4 pair, rope inlined (2026-09-14)

The Adreno copy of the Pixel 8a sitting 2 (`results/raw/2026-09-14-catalog-int4-vs-int8-pixel8a-dtypeonly-norope-android/NOTES.md`):
the same two bundles — one litert-torch main (6d4c622) export of Qwen3-1.7B per recipe with every other flag identical
(fused qkv / gate_up, `odml.cache_update`, bool mask, fixed prefill 1024, cache 4096 via the 4099 magic number, rope
inlined), `dynamic_wi8_afp32` vs `dynamic_wi4b32_afp32`; TFLite graphs differ only in the FULLY_CONNECTED weight dtype;
static weight bytes per token 1720.9 MB (int8) / 968.2 MB (int4); sha256 in litertlm-convert
`qwen3_gpuopt_work/2026-09-14-int8-int4-dtypeonly.md`. Same method and runtime as the 2026-09-13 S26 sitting: LiteRT-LM
v0.16.0 pinned binary, GPU backend (ML Drift, OpenCL on Adreno), unmasked, `run_session.py` beside this file (anchors
as their own campaign, admission by the engine-version-matched `scripts/dashboard_job.admit`, thermal gate), runs=3
interleaved per round, 12:03–12:43. No reboot rule on this phone: uptime 2 d 19 h at start (the phone had left the adb
bus at the end of the 02:00 dashboard sitting and was re-plugged at 12:01). Anchors ADMITTED at ratio 1.000 vs the
newest b8999 session, payload re-judged 1.004; every run thermal nominal (SKIN 37.9 °C at start, status 0 throughout).
Cells `matrices/catalog-int4-vs-int8-s26-dtypeonly.cells`, profile pair `…-s26-dtypeonly-profile.cells`.

**CPU frequency cap, read by hand:** `scaling_max_freq` equalled `cpuinfo_max_freq` (3.63 / 4.74 GHz) at 12:02 and at
12:12 after the anchor phase; at 12:42, after the profile pair, both clusters read 2.23 GHz (the charge/thermal cap this
phone applies after heavy legs, `devices/galaxy-s26.md`). When it engaged between 12:12 and 12:42 is not known. The two
files ran interleaved, so the dtype comparison inside this sitting stands; comparisons of these rows with other sessions
(the 2026-09-13 published-file rows) carry that caveat. A retake with the cap checked before each leg is the fix if a
cross-session number is ever quoted from here.

**Both files answer the prompt** (thinking on, as shipped): int8 "On-device AI means that the artificial intelligence
(AI) models and their processing happen directly on the device you're using…"; int4 "On-device AI is like having a smart
computer in your pocket!…". No gate flag.

## Speed rows (short-chat, GPU, median of the warm runs, cache-building run out — all three listed)

| file | weight MB / token | decode tok/s | runs | prefill tok/s | TTFT s | generated tokens | effective GB/s |
|---|---|---|---|---|---|---|---|
| int8 `Qwen3-1.7B_wi8_gpuflags_norope.litertlm` (`litert-local/Qwen3-1.7B-wi8-gpuflags-norope`) | 1720.9 | **19.56** | 20.86 (cache build), 19.59, 19.52 | 27.4 | 0.74 | 909 | 33.7 |
| int4 `Qwen3-1.7B_wi4b32_gpuflags_norope.litertlm` (`litert-local/Qwen3-1.7B-wi4b32-gpuflags-norope`) | 968.2 | **26.03** | 26.55 (cache build), 24.72, 27.34 | 19.2 | 1.03 | 534 | 25.2 |

Generated tokens include the thinking (the runtime does not cap the `thought` channel at the 128-token budget); the
rates are per token.

## Per-op pair (`./bench profile`, 128x256, max_num_tokens 1024, GPU; 256/256 steps recorded on both)

| file | control tok/s | wall ms/step | weight GEMV ms/step | attn+KV | xfer | other | unprofiled | launches/step | GEMV GB/s (static MB / GEMV ms) |
|---|---|---|---|---|---|---|---|---|---|
| int8 | 22.39 | 44.7 | **30.9** | 1.1 | 1.1 | 1.5 | 10.0 | 969 | **55.6** |
| int4 | 28.23 | 35.4 | **19.1** | 0.9 | 1.2 | 1.1 | 13.2 | 969 | **50.8** |

Per node (decode phase): `fc1x1_int8_weights` 57 × 0.377 ms + `-> add` 56 × 0.153 against `fc1x1_int4_weights`
57 × 0.230 + `-> add` 56 × 0.092. Prefill of the 128-token benchmark prompt: int8 166 tok/s (TTFT 0.81 s), int4 262
(0.53 s).

## Reading

1. **Same graph on Adreno: int4 ahead, per-byte penalty 1.09×** (50.8 vs 55.6 GB/s in the GEMV family) — GEMV 19.1
   vs 30.9 ms/step (int4 reads 56 % of the bytes in 62 % of the time), whole model 35.4 vs 44.7 ms/step at ctx 1024
   (+26 % decode) and 26.03 vs 19.56 tok/s on short-chat (+33 %). The 2026-09-13 cross-graph pair on this phone read
   1.22× with int4 ahead; the direction holds and the penalty is smaller once the graph is equal.
2. **Fusion costs the int8 kernel here too, but mildly.** The published unfused int8 file's GEMV family was 26.9
   ms/step (64.0 GB/s) on 2026-09-13; the fused int8 matrices of this file take 30.9 (55.6 GB/s), +15 % for the same
   bytes, where the Pixel 8a's Mali went 44.9 → 79.6 (+77 %). The int4 kernel reads the same across the int4 files compared here on both phones
   (S26 18.5 → 19.1, Pixel 54.6/56.7 → 52.2), but every one of them is fused — the published wi4b32 build fuses
   QKV and gate/up too — so no unfused int4 file has been measured and the fusion cost of the int4 kernel is not known
   (corrected 2026-09-15; the earlier wording "the same fused or not" claimed a pair that does not exist). So the three GPU paths now read the same way on a dtype-only pair:
   int4 ahead in absolute GEMV time with a per-byte penalty of 1.09× (Adreno) / 1.17× (Mali) — the 2.2× of Metal (K1)
   stays the outlier, and the 2026-09-13 "Mali is Metal-like" line is withdrawn.
3. The rope-inlined int4 file's short-chat 26.03 is below the published `odml.rope` wi4b32 build's 33.63 of
   2026-09-13 on this phone; at ctx 1024 the profile controls are 28.23 vs 29.25 (−3 %, the inlined rope adds 174
   launches per step, unprofiled 13.2 vs 12.9 ms). The rest of the short-chat gap is not attributed: the published
   file's rows were off-prompt 144-token generations (sitting 1's rope-composite defect, Pixel NOTES.md), these are
   534-token on-topic ones, and the frequency cap above may have applied. Not a dtype question; not pursued here.
