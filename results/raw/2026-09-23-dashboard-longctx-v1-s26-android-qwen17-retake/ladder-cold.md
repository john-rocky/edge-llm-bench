# 2026-09-23-dashboard-longctx-v1-s26-android-qwen17-retake — long-context-2048-gen256, regime cold (median [min–max] over rounds)

Selected rounds: 1,2,3,4,5,6; admission remains the session reviewer's decision.


## litert-lm-cpu — litert-community/Qwen3-1.7B

| arm | model | file / recipe | ctx | prompt tok | out tok (short / unknown) | prefill tok/s | TTFT ms | decode tok/s | peak RSS | Δ from smallest ctx | thermal | flags |
|---|---|---|---:|---:|---|---|---|---|---|---:|---|---|
| litert-lm-cpu | litert-community/Qwen3-1.7B | litert-community_Qwen3-1.7B_Qwen3_1.7B.litertlm / INT8 (dynamic_wi8_afp32: int8 weights, FP32 act; CPU-recipe file) | 2304 | 1986 | 256 [256–256] n=6 (0 / 0) | 282.2 [263.3–303.9] n=6 | 7140 [6640–7650] n=6 | 9.7 [9.6–9.8] n=6 | 2867.4 [2754.9–2868.5] n=6 | +0.0% | nominal |  |
| litert-lm-cpu | litert-community/Qwen3-1.7B | litert-community_Qwen3-1.7B_Qwen3_1.7B.litertlm / INT8 (dynamic_wi8_afp32: int8 weights, FP32 act; CPU-recipe file) | 4096 | 1986 | 256 [256–256] n=6 (0 / 0) | 293.2 [278.3–295.5] n=6 | 6875 [6820–7240] n=6 | 9.8 [9.6–9.8] n=6 | 2867.4 [2864.1–3126.5] n=6 | +0.9% | nominal |  |
| litert-lm-cpu | litert-community/Qwen3-1.7B | litert-community_Qwen3-1.7B_Qwen3_1.7B.litertlm / INT8 (dynamic_wi8_afp32: int8 weights, FP32 act; CPU-recipe file) | 8192 | 1986 | 256 [256–256] n=6 (0 / 0) | 290.5 [264.0–300.5] n=6 | 6940 [6710–7630] n=6 | 9.8 [9.6–9.9] n=6 | 2868.3 [2865.7–3132.6] n=6 | +0.9% | nominal |  |

RSS basis: sampled launch VmHWM, MiB

Δ 2304→4096 (ratio of decode medians): +0.9%

Δ 2304→8192 (ratio of decode medians): +0.9%

csv: results/raw/2026-09-23-dashboard-longctx-v1-s26-android-qwen17-retake/ladder-cold.csv
