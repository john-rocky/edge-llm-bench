# 2026-09-23-dashboard-longctx-v1-s26-android-qwen17-retake — long-context-2048-gen256, regime warm (median [min–max] over rounds)

Selected rounds: 1,2,3,4,5,6; admission remains the session reviewer's decision.


## litert-lm-cpu — litert-community/Qwen3-1.7B

| arm | model | file / recipe | ctx | prompt tok | out tok (short / unknown) | prefill tok/s | TTFT ms | decode tok/s | peak RSS | Δ from smallest ctx | thermal | flags |
|---|---|---|---:|---:|---|---|---|---|---|---:|---|---|
| litert-lm-cpu | litert-community/Qwen3-1.7B | litert-community_Qwen3-1.7B_Qwen3_1.7B.litertlm / INT8 (dynamic_wi8_afp32: int8 weights, FP32 act; CPU-recipe file) | 2304 | 1986 | 256 [256–256] n=6 (0 / 0) | 210.0 [207.8–214.1] n=6 | 9565 [9380–9670] n=6 | 9.3 [9.2–9.6] n=6 | 2867.4 [2754.9–2868.5] n=6 | +0.0% | nominal |  |
| litert-lm-cpu | litert-community/Qwen3-1.7B | litert-community_Qwen3-1.7B_Qwen3_1.7B.litertlm / INT8 (dynamic_wi8_afp32: int8 weights, FP32 act; CPU-recipe file) | 4096 | 1986 | 256 [256–256] n=6 (0 / 0) | 210.6 [206.9–212.3] n=6 | 9535 [9460–9710] n=6 | 9.3 [9.2–9.4] n=6 | 2867.4 [2864.1–3126.5] n=6 | +0.2% | nominal |  |
| litert-lm-cpu | litert-community/Qwen3-1.7B | litert-community_Qwen3-1.7B_Qwen3_1.7B.litertlm / INT8 (dynamic_wi8_afp32: int8 weights, FP32 act; CPU-recipe file) | 8192 | 1986 | 256 [256–256] n=6 (0 / 0) | 209.5 [208.4–212.0] n=6 | 9585 [9470–9640] n=6 | 9.3 [9.2–9.4] n=6 | 2868.3 [2865.7–3132.6] n=6 | +0.2% | nominal |  |

RSS basis: sampled launch VmHWM, MiB

Δ 2304→4096 (ratio of decode medians): +0.2%

Δ 2304→8192 (ratio of decode medians): +0.2%

csv: results/raw/2026-09-23-dashboard-longctx-v1-s26-android-qwen17-retake/ladder-warm.csv
