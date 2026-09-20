# 2026-09-20-dashboard-longctx-v1-s26-android-qwen06 — long-context-2048-gen256, regime cold (median [min–max] over rounds)

Selected rounds: 1,2,3,4,5,6; admission remains the session reviewer's decision.


## litert-lm-cpu — litert-community/Qwen3-0.6B

| arm | model | file / recipe | ctx | prompt tok | out tok (short / unknown) | prefill tok/s | TTFT ms | decode tok/s | peak RSS | Δ from smallest ctx | thermal | flags |
|---|---|---|---:|---:|---|---|---|---|---|---:|---|---|
| litert-lm-cpu | litert-community/Qwen3-0.6B | litert-community_Qwen3-0.6B_Qwen3-0.6B_dynamic_wi4b32_afp32.litertlm / INT4 (dynamic, block-32 weights, FP32 act; GPU-graph build 2026-08-04) | 2304 | 1986 | 256 [256–256] n=6 (0 / 0) | 301.5 [274.2–308.4] n=6 | 6630 [6490–7290] n=6 | 22.1 [21.2–24.7] n=6 | 1760.3 [1759.2–1760.7] n=6 | +0.0% | nominal |  |
| litert-lm-cpu | litert-community/Qwen3-0.6B | litert-community_Qwen3-0.6B_Qwen3-0.6B_dynamic_wi4b32_afp32.litertlm / INT4 (dynamic, block-32 weights, FP32 act; GPU-graph build 2026-08-04) | 4096 | 1986 | 256 [256–256] n=5 (0 / 0) | 197.3 [193.9–198.9] n=5 | 10150 [10070–10330] n=5 | 11.8 [11.6–12.0] n=5 | 2641.1 [2639.7–2642.1] n=5 | -46.8% | nominal |  |
| litert-lm-cpu | litert-community/Qwen3-0.6B | litert-community_Qwen3-0.6B_Qwen3-0.6B_dynamic_wi4b32_afp32.litertlm / INT4 (dynamic, block-32 weights, FP32 act; GPU-graph build 2026-08-04) | 8192 | 1986 | 256 [256–256] n=6 (0 / 0) | 97.2 [82.5–98.5] n=6 | 20595 [20330–24230] n=6 | 5.9 [5.8–6.0] n=6 | 4654.0 [4602.2–4655.7] n=6 | -73.3% | nominal |  |

RSS basis: sampled launch VmHWM, MiB

Δ 2304→4096 (ratio of decode medians): -46.8%

Δ 2304→8192 (ratio of decode medians): -73.3%

csv: results/raw/2026-09-20-dashboard-longctx-v1-s26-android-qwen06/ladder-cold.csv
