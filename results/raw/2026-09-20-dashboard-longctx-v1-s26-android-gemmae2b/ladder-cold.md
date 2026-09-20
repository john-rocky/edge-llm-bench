# 2026-09-20-dashboard-longctx-v1-s26-android-gemmae2b — long-context-2048-gen256, regime cold (median [min–max] over rounds)

Selected rounds: 1,2,3,4,5; admission remains the session reviewer's decision.


## litert-lm-cpu — litert-community/gemma-4-E2B-it-litert-lm

| arm | model | file / recipe | ctx | prompt tok | out tok (short / unknown) | prefill tok/s | TTFT ms | decode tok/s | peak RSS | Δ from smallest ctx | thermal | flags |
|---|---|---|---:|---:|---|---|---|---|---|---:|---|---|
| litert-lm-cpu | litert-community/gemma-4-E2B-it-litert-lm | litert-community_gemma-4-E2B-it-litert-lm_gemma-4-E2B-it.litertlm / wNa8o8 (int2/int4/int8 + int8 activations, QAT) | 2304 | 1637 | 256 [256–256] n=4 (0 / 0) | 431.9 [408.2–437.4] n=4 | 3820 [3770–4040] n=4 | 32.7 [29.7–34.3] n=4 | 2127.2 [2122.4–2221.0] n=4 | +0.0% | nominal |  |
| litert-lm-cpu | litert-community/gemma-4-E2B-it-litert-lm | litert-community_gemma-4-E2B-it-litert-lm_gemma-4-E2B-it.litertlm / wNa8o8 (int2/int4/int8 + int8 activations, QAT) | 4096 | 1637 | 256 [256–256] n=4 (0 / 0) | 345.5 [336.9–358.1] n=4 | 4775 [4610–4900] n=4 | 25.8 [25.7–27.0] n=4 | 2853.7 [2782.6–2913.9] n=4 | -21.0% | nominal |  |
| litert-lm-cpu | litert-community/gemma-4-E2B-it-litert-lm | litert-community_gemma-4-E2B-it-litert-lm_gemma-4-E2B-it.litertlm / wNa8o8 (int2/int4/int8 + int8 activations, QAT) | 8192 | 1637 | 256 [256–256] n=4 (0 / 0) | 218.5 [211.8–226.9] n=4 | 7550 [7270–7790] n=4 | 17.2 [16.8–17.8] n=4 | 4787.6 [4466.6–5038.9] n=4 | -47.5% | nominal |  |

RSS basis: sampled launch VmHWM, MiB

Δ 2304→4096 (ratio of decode medians): -21.0%

Δ 2304→8192 (ratio of decode medians): -47.5%

## litert-lm-gpu — litert-community/gemma-4-E2B-it-litert-lm

| arm | model | file / recipe | ctx | prompt tok | out tok (short / unknown) | prefill tok/s | TTFT ms | decode tok/s | peak RSS | Δ from smallest ctx | thermal | flags |
|---|---|---|---:|---:|---|---|---|---|---|---:|---|---|
| litert-lm-gpu | litert-community/gemma-4-E2B-it-litert-lm | litert-community_gemma-4-E2B-it-litert-lm_gemma-4-E2B-it.litertlm / wNa8o8 (int2/int4/int8 + int8 activations, QAT) | 2304 | 1637 | 256 [256–256] n=5 (0 / 0) | 2883.8 [2787.9–2977.4] n=5 | 610 [590–630] n=5 | 25.8 [25.6–26.1] n=5 | 814.2 [793.6–855.5] n=5 | +0.0% | nominal |  |
| litert-lm-gpu | litert-community/gemma-4-E2B-it-litert-lm | litert-community_gemma-4-E2B-it-litert-lm_gemma-4-E2B-it.litertlm / wNa8o8 (int2/int4/int8 + int8 activations, QAT) | 4096 | 1637 | 256 [256–256] n=4 (0 / 0) | 2484.2 [2241.8–2537.2] n=4 | 695 [680–770] n=4 | 26.0 [24.7–26.2] n=4 | 849.6 [814.6–865.9] n=4 | +0.8% | nominal |  |
| litert-lm-gpu | litert-community/gemma-4-E2B-it-litert-lm | litert-community_gemma-4-E2B-it-litert-lm_gemma-4-E2B-it.litertlm / wNa8o8 (int2/int4/int8 + int8 activations, QAT) | 8192 | 1637 | 93 [93–93] n=4 (4 / 0) | 1824.4 [1451.2–1988.2] n=4 | 940 [860–1160] n=4 | 27.5 [25.3–30.4] n=4 | 849.2 [811.5–872.7] n=4 | +6.9% | nominal |  |

RSS basis: sampled launch VmHWM, MiB

Δ 2304→4096 (ratio of decode medians): +0.8%

Δ 2304→8192 (ratio of decode medians): +6.9%

csv: results/raw/2026-09-20-dashboard-longctx-v1-s26-android-gemmae2b/ladder-cold.csv
