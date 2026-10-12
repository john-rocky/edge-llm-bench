# 2026-10-12-catalog-x2-s26-android-e4b-gpu — long-context-2048-gen256-noref, regime cold (median [min–max] over rounds)

Selected rounds: 1,2,3,4; admission remains the session reviewer's decision.


## litert-lm-gpu — litert-community/gemma-4-E4B-it-litert-lm

| arm | model | file / recipe | ctx | prompt tok | out tok (short / unknown) | prefill tok/s | TTFT ms | decode tok/s | peak RSS | Δ from smallest ctx | thermal | flags |
|---|---|---|---:|---:|---|---|---|---|---|---:|---|---|
| litert-lm-gpu | litert-community/gemma-4-E4B-it-litert-lm | litert-community_gemma-4-E4B-it-litert-lm_gemma-4-E4B-it.litertlm / wNa8o8 (int2/int4/int8 + int8 activations, QAT) | 2304 | 1654 | 256 [256–256] n=4 (0 / 0) | 1087.5 [978.1–1096.6] n=4 | 1585 [1580–1760] n=4 | 15.0 [14.6–15.6] n=4 | 961.7 [923.4–1006.4] n=4 | +0.0% | nominal | ◇cpu-capped 4/4 records, ceiling fall ≤ 63.2 % |
| litert-lm-gpu | litert-community/gemma-4-E4B-it-litert-lm | litert-community_gemma-4-E4B-it-litert-lm_gemma-4-E4B-it.litertlm / wNa8o8 (int2/int4/int8 + int8 activations, QAT) | 4096 | 1654 | 256 [256–256] n=3 (0 / 0) | 1017.5 [901.0–1022.1] n=3 | 1690 [1680–1900] n=3 | 15.1 [14.7–15.1] n=3 | 954.7 [876.0–1018.9] n=3 | +0.7% | nominal | ◇cpu-capped 3/3 records, ceiling fall ≤ 63.2 % |
| litert-lm-gpu | litert-community/gemma-4-E4B-it-litert-lm | litert-community_gemma-4-E4B-it-litert-lm_gemma-4-E4B-it.litertlm / wNa8o8 (int2/int4/int8 + int8 activations, QAT) | 8192 | 1654 | 256 [256–256] n=4 (0 / 0) | 814.9 [745.7–883.7] n=4 | 2110 [1940–2290] n=4 | 14.2 [14.1–14.7] n=4 | 1034.3 [961.4–1194.4] n=4 | -5.0% | nominal | ◇cpu-capped 4/4 records, ceiling fall ≤ 63.2 % |

RSS basis: sampled launch VmHWM, MiB

Δ 2304→4096 (ratio of decode medians): +0.7%

Δ 2304→8192 (ratio of decode medians): -5.0%

csv: results/raw/2026-10-12-catalog-x2-s26-android-e4b-gpu/ladder-cold.csv
