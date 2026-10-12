# 2026-10-12-catalog-x2-s26-android-e4b-gpu-retake — long-context-2048-gen256-noref, regime cold (median [min–max] over rounds)

Selected rounds: 1,2,3,4; admission remains the session reviewer's decision.


## litert-lm-gpu — litert-community/gemma-4-E4B-it-litert-lm

| arm | model | file / recipe | ctx | prompt tok | out tok (short / unknown) | prefill tok/s | TTFT ms | decode tok/s | peak RSS | Δ from smallest ctx | thermal | flags |
|---|---|---|---:|---:|---|---|---|---|---|---:|---|---|
| litert-lm-gpu | litert-community/gemma-4-E4B-it-litert-lm | litert-community_gemma-4-E4B-it-litert-lm_gemma-4-E4B-it.litertlm / wNa8o8 (int2/int4/int8 + int8 activations, QAT) | 2304 | 1654 | 256 [256–256] n=3 (0 / 0) | 1106.1 [1103.3–1121.0] n=3 | 1560 [1540–1570] n=3 | 15.1 [14.9–15.4] n=3 | 952.8 [951.8–1013.4] n=3 | +0.0% | nominal | ◇cpu-capped 3/3 records, ceiling fall ≤ 63.2 % |
| litert-lm-gpu | litert-community/gemma-4-E4B-it-litert-lm | litert-community_gemma-4-E4B-it-litert-lm_gemma-4-E4B-it.litertlm / wNa8o8 (int2/int4/int8 + int8 activations, QAT) | 4096 | 1654 | 256 [256–256] n=3 (0 / 0) | 1029.0 [1020.5–1033.0] n=3 | 1670 [1670–1690] n=3 | 15.1 [14.8–15.6] n=3 | 1068.8 [1034.0–1112.1] n=3 | +0.3% | nominal | ◇cpu-capped 3/3 records, ceiling fall ≤ 63.2 % |
| litert-lm-gpu | litert-community/gemma-4-E4B-it-litert-lm | litert-community_gemma-4-E4B-it-litert-lm_gemma-4-E4B-it.litertlm / wNa8o8 (int2/int4/int8 + int8 activations, QAT) | 8192 | 1654 | 256 [256–256] n=3 (0 / 0) | 768.0 [756.7–889.3] n=3 | 2220 [1930–2260] n=3 | 14.5 [14.2–15.2] n=3 | 1072.3 [1005.7–1194.4] n=3 | -3.9% | nominal | ◇cpu-capped 3/3 records, ceiling fall ≤ 63.2 % |

RSS basis: sampled launch VmHWM, MiB

Δ 2304→4096 (ratio of decode medians): +0.3%

Δ 2304→8192 (ratio of decode medians): -3.9%

csv: results/raw/2026-10-12-catalog-x2-s26-android-e4b-gpu-retake/ladder-cold.csv
