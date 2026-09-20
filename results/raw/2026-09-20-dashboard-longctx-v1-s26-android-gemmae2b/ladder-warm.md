# 2026-09-20-dashboard-longctx-v1-s26-android-gemmae2b — long-context-2048-gen256, regime warm (median [min–max] over rounds)

Selected rounds: 1,2,3,4,5; admission remains the session reviewer's decision.


## litert-lm-cpu — litert-community/gemma-4-E2B-it-litert-lm

| arm | model | file / recipe | ctx | prompt tok | out tok (short / unknown) | prefill tok/s | TTFT ms | decode tok/s | peak RSS | Δ from smallest ctx | thermal | flags |
|---|---|---|---:|---:|---|---|---|---|---|---:|---|---|
| litert-lm-cpu | litert-community/gemma-4-E2B-it-litert-lm | litert-community_gemma-4-E2B-it-litert-lm_gemma-4-E2B-it.litertlm / wNa8o8 (int2/int4/int8 + int8 activations, QAT) | 2304 | 1637 | 256 [256–256] n=5 (0 / 0) | 243.5 [237.6–292.9] n=5 | 6760 [5620–6930] n=5 | 24.2 [23.8–28.3] n=5 | 2127.1 [2044.7–2221.0] n=5 | +0.0% | nominal |  |
| litert-lm-cpu | litert-community/gemma-4-E2B-it-litert-lm | litert-community_gemma-4-E2B-it-litert-lm_gemma-4-E2B-it.litertlm / wNa8o8 (int2/int4/int8 + int8 activations, QAT) | 4096 | 1637 | 256 [256–256] n=5 (0 / 0) | 193.7 [188.4–228.2] n=5 | 8500 [7220–8740] n=5 | 21.4 [20.8–23.6] n=5 | 2824.3 [2782.6–2913.9] n=5 | -11.4% | nominal |  |
| litert-lm-cpu | litert-community/gemma-4-E2B-it-litert-lm | litert-community_gemma-4-E2B-it-litert-lm_gemma-4-E2B-it.litertlm / wNa8o8 (int2/int4/int8 + int8 activations, QAT) | 8192 | 1637 | 256 [256–256] n=5 (0 / 0) | 131.3 [125.8–148.7] n=5 | 12530 [11060–13070] n=5 | 16.1 [16.1–17.9] n=5 | 4844.3 [4466.6–5038.9] n=5 | -33.5% | nominal |  |

RSS basis: sampled launch VmHWM, MiB

Δ 2304→4096 (ratio of decode medians): -11.4%

Δ 2304→8192 (ratio of decode medians): -33.5%

## litert-lm-gpu — litert-community/gemma-4-E2B-it-litert-lm

| arm | model | file / recipe | ctx | prompt tok | out tok (short / unknown) | prefill tok/s | TTFT ms | decode tok/s | peak RSS | Δ from smallest ctx | thermal | flags |
|---|---|---|---:|---:|---|---|---|---|---|---:|---|---|
| litert-lm-gpu | litert-community/gemma-4-E2B-it-litert-lm | litert-community_gemma-4-E2B-it-litert-lm_gemma-4-E2B-it.litertlm / wNa8o8 (int2/int4/int8 + int8 activations, QAT) | 2304 | 1637 | 256 [256–256] n=5 (0 / 0) | 2905.7 [2814.5–2909.9] n=5 | 600 [600–630] n=5 | 26.0 [21.9–29.2] n=5 | 814.2 [793.6–855.5] n=5 | +0.0% | nominal |  |
| litert-lm-gpu | litert-community/gemma-4-E2B-it-litert-lm | litert-community_gemma-4-E2B-it-litert-lm_gemma-4-E2B-it.litertlm / wNa8o8 (int2/int4/int8 + int8 activations, QAT) | 4096 | 1637 | 256 [256–256] n=5 (0 / 0) | 2550.0 [1779.9–2572.9] n=5 | 680 [670–980] n=5 | 26.0 [16.1–26.1] n=5 | 833.6 [752.2–865.9] n=5 | -0.0% | nominal |  |
| litert-lm-gpu | litert-community/gemma-4-E2B-it-litert-lm | litert-community_gemma-4-E2B-it-litert-lm_gemma-4-E2B-it.litertlm / wNa8o8 (int2/int4/int8 + int8 activations, QAT) | 8192 | 1637 | 93 [93–93] n=5 (5 / 0) | 1972.0 [1957.8–1995.5] n=5 | 870 [860–880] n=5 | 25.0 [24.2–25.2] n=5 | 840.8 [811.5–872.7] n=5 | -4.1% | nominal |  |

RSS basis: sampled launch VmHWM, MiB

Δ 2304→4096 (ratio of decode medians): -0.0%

Δ 2304→8192 (ratio of decode medians): -4.1%

csv: results/raw/2026-09-20-dashboard-longctx-v1-s26-android-gemmae2b/ladder-warm.csv
