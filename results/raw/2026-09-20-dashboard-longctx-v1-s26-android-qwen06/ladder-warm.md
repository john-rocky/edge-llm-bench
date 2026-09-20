# 2026-09-20-dashboard-longctx-v1-s26-android-qwen06 — long-context-2048-gen256, regime warm (median [min–max] over rounds)

Selected rounds: 1,2,3,4,5,6; admission remains the session reviewer's decision.


## litert-lm-cpu — litert-community/Qwen3-0.6B

| arm | model | file / recipe | ctx | prompt tok | out tok (short / unknown) | prefill tok/s | TTFT ms | decode tok/s | peak RSS | Δ from smallest ctx | thermal | flags |
|---|---|---|---:|---:|---|---|---|---|---|---:|---|---|
| litert-lm-cpu | litert-community/Qwen3-0.6B | litert-community_Qwen3-0.6B_Qwen3-0.6B_dynamic_wi4b32_afp32.litertlm / INT4 (dynamic, block-32 weights, FP32 act; GPU-graph build 2026-08-04) | 2304 | 1986 | 256 [256–256] n=6 (0 / 0) | 178.3 [176.4–223.1] n=6 | 11185 [8950–11310] n=6 | 20.0 [19.8–21.7] n=6 | 1760.3 [1759.2–1760.7] n=6 | +0.0% | nominal |  |
| litert-lm-cpu | litert-community/Qwen3-0.6B | litert-community_Qwen3-0.6B_Qwen3-0.6B_dynamic_wi4b32_afp32.litertlm / INT4 (dynamic, block-32 weights, FP32 act; GPU-graph build 2026-08-04) | 4096 | 1986 | 256 [256–256] n=6 (0 / 0) | 124.0 [123.2–137.2] n=6 | 16110 [14550–16210] n=6 | 11.3 [11.2–12.4] n=6 | 2641.2 [2639.7–2642.1] n=6 | -43.5% | nominal |  |
| litert-lm-cpu | litert-community/Qwen3-0.6B | litert-community_Qwen3-0.6B_Qwen3-0.6B_dynamic_wi4b32_afp32.litertlm / INT4 (dynamic, block-32 weights, FP32 act; GPU-graph build 2026-08-04) | 8192 | 1986 | 256 [256–256] n=6 (0 / 0) | 69.6 [66.8–76.5] n=6 | 28765 [26130–29930] n=6 | 5.1 [5.0–5.7] n=6 | 4654.0 [4602.2–4655.7] n=6 | -74.3% | nominal |  |

RSS basis: sampled launch VmHWM, MiB

Δ 2304→4096 (ratio of decode medians): -43.5%

Δ 2304→8192 (ratio of decode medians): -74.3%

csv: results/raw/2026-09-20-dashboard-longctx-v1-s26-android-qwen06/ladder-warm.csv
