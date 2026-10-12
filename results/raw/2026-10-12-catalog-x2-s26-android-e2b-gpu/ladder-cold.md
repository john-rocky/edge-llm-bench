# 2026-10-12-catalog-x2-s26-android-e2b-gpu — long-context-2048-gen256-noref, regime cold (median [min–max] over rounds)

Selected rounds: 1,2,3,4,5,6; admission remains the session reviewer's decision.


## litert-lm-gpu — litert-community/gemma-4-E2B-it-litert-lm

| arm | model | file / recipe | ctx | prompt tok | out tok (short / unknown) | prefill tok/s | TTFT ms | decode tok/s | peak RSS | Δ from smallest ctx | thermal | flags |
|---|---|---|---:|---:|---|---|---|---|---|---:|---|---|
| litert-lm-gpu | litert-community/gemma-4-E2B-it-litert-lm | litert-community_gemma-4-E2B-it-litert-lm_gemma-4-E2B-it.litertlm / wNa8o8 (int2/int4/int8 + int8 activations, QAT) | 2304 | 1654 | 256 [256–256] n=5 (0 / 0) | 2885.9 [2877.7–2917.2] n=5 | 610 [610–610] n=5 | 25.8 [25.6–26.3] n=5 | 786.3 [775.0–816.0] n=5 | +0.0% | nominal | ◇cpu-capped 5/5 records, ceiling fall ≤ 39.3 % |
| litert-lm-gpu | litert-community/gemma-4-E2B-it-litert-lm | litert-community_gemma-4-E2B-it-litert-lm_gemma-4-E2B-it.litertlm / wNa8o8 (int2/int4/int8 + int8 activations, QAT) | 4096 | 1654 | 256 [256–256] n=5 (0 / 0) | 2510.6 [2467.8–2524.7] n=5 | 700 [690–710] n=5 | 25.8 [25.3–26.1] n=5 | 807.7 [765.3–835.7] n=5 | +0.1% | nominal | ◇cpu-capped 5/5 records, ceiling fall ≤ 39.3 % |
| litert-lm-gpu | litert-community/gemma-4-E2B-it-litert-lm | litert-community_gemma-4-E2B-it-litert-lm_gemma-4-E2B-it.litertlm / wNa8o8 (int2/int4/int8 + int8 activations, QAT) | 8192 | 1654 | 256 [256–256] n=6 (0 / 0) | 1979.5 [1677.8–1995.2] n=6 | 875 [870–1020] n=6 | 25.5 [24.6–27.0] n=6 | 864.2 [814.7–879.9] n=6 | -1.0% | nominal | ◇cpu-capped 6/6 records, ceiling fall ≤ 39.3 % |

RSS basis: sampled launch VmHWM, MiB

Δ 2304→4096 (ratio of decode medians): +0.1%

Δ 2304→8192 (ratio of decode medians): -1.0%

csv: results/raw/2026-10-12-catalog-x2-s26-android-e2b-gpu/ladder-cold.csv
