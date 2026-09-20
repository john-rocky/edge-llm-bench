# 2026-09-20-dashboard-longctx-v1-s26-android-qwen06 — long-context-2048-gen256, regime first-ever (median [min–max] over rounds)

Selected rounds: 1,2,3,4,5,6; admission remains the session reviewer's decision.

First-ever cache-build observations only; these are not engine-speed estimates.


## litert-lm-cpu — litert-community/Qwen3-0.6B

| arm | model | file / recipe | ctx | prompt tok | out tok (short / unknown) | prefill tok/s | TTFT ms | decode tok/s | peak RSS | Δ from smallest ctx | thermal | flags |
|---|---|---|---:|---:|---|---|---|---|---|---:|---|---|
| litert-lm-cpu | litert-community/Qwen3-0.6B | litert-community_Qwen3-0.6B_Qwen3-0.6B_dynamic_wi4b32_afp32.litertlm / INT4 (dynamic, block-32 weights, FP32 act; GPU-graph build 2026-08-04) | 4096 | 1986 | 256 [256–256] n=1 (0 / 0) | 194.3 [194.3–194.3] n=1 | 10300 [10300–10300] n=1 | 12.6 [12.6–12.6] n=1 | 2641.7 [2641.7–2641.7] n=1 | +0.0% | nominal |  |

RSS basis: sampled launch VmHWM, MiB

csv: results/raw/2026-09-20-dashboard-longctx-v1-s26-android-qwen06/ladder-first-ever.csv
