# 2026-10-12-catalog-x2-s26-android-e2b-gpu — long-context-2048-gen256-noref, regime warm (median [min–max] over rounds)

Selected rounds: 1,2,3,4,5,6; admission remains the session reviewer's decision.


## litert-lm-gpu — litert-community/gemma-4-E2B-it-litert-lm

| arm | model | file / recipe | ctx | prompt tok | out tok (short / unknown) | prefill tok/s | TTFT ms | decode tok/s | peak RSS | Δ from smallest ctx | thermal | flags |
|---|---|---|---:|---:|---|---|---|---|---|---:|---|---|
| litert-lm-gpu | litert-community/gemma-4-E2B-it-litert-lm | litert-community_gemma-4-E2B-it-litert-lm_gemma-4-E2B-it.litertlm / wNa8o8 (int2/int4/int8 + int8 activations, QAT) | 2304 | 1654 | 256 [256–256] n=6 (0 / 0) | 2844.8 [2820.2–2863.8] n=6 | 620 [620–630] n=6 | 25.6 [25.3–27.8] n=6 | 799.5 [775.0–846.2] n=6 | +0.0% | nominal | ◇cpu-capped 6/6 records, ceiling fall ≤ 39.3 % |
| litert-lm-gpu | litert-community/gemma-4-E2B-it-litert-lm | litert-community_gemma-4-E2B-it-litert-lm_gemma-4-E2B-it.litertlm / wNa8o8 (int2/int4/int8 + int8 activations, QAT) | 4096 | 1654 | 256 [256–256] n=6 (0 / 0) | 2515.3 [2500.6–2576.4] n=6 | 700 [680–700] n=6 | 25.8 [25.6–28.3] n=6 | 818.8 [765.3–855.9] n=6 | +0.7% | nominal | ◇cpu-capped 6/6 records, ceiling fall ≤ 39.3 % |
| litert-lm-gpu | litert-community/gemma-4-E2B-it-litert-lm | litert-community_gemma-4-E2B-it-litert-lm_gemma-4-E2B-it.litertlm / wNa8o8 (int2/int4/int8 + int8 activations, QAT) | 8192 | 1654 | 256 [256–256] n=6 (0 / 0) | 1971.4 [1950.2–2005.0] n=6 | 880 [860–890] n=6 | 25.3 [25.2–25.5] n=6 | 864.2 [814.7–879.9] n=6 | -1.2% | nominal | ◇cpu-capped 6/6 records, ceiling fall ≤ 39.3 % |

RSS basis: sampled launch VmHWM, MiB

Δ 2304→4096 (ratio of decode medians): +0.7%

Δ 2304→8192 (ratio of decode medians): -1.2%

csv: results/raw/2026-10-12-catalog-x2-s26-android-e2b-gpu/ladder-warm.csv
