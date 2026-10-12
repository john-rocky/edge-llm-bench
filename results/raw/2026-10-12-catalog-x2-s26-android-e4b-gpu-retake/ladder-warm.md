# 2026-10-12-catalog-x2-s26-android-e4b-gpu-retake — long-context-2048-gen256-noref, regime warm (median [min–max] over rounds)

Selected rounds: 1,2,3,4; admission remains the session reviewer's decision.


## litert-lm-gpu — litert-community/gemma-4-E4B-it-litert-lm

| arm | model | file / recipe | ctx | prompt tok | out tok (short / unknown) | prefill tok/s | TTFT ms | decode tok/s | peak RSS | Δ from smallest ctx | thermal | flags |
|---|---|---|---:|---:|---|---|---|---|---|---:|---|---|
| litert-lm-gpu | litert-community/gemma-4-E4B-it-litert-lm | litert-community_gemma-4-E4B-it-litert-lm_gemma-4-E4B-it.litertlm / wNa8o8 (int2/int4/int8 + int8 activations, QAT) | 2304 | 1654 | 256 [256–256] n=4 (0 / 0) | 1077.9 [1031.5–1091.7] n=4 | 1600 [1580–1680] n=4 | 15.1 [13.2–15.4] n=4 | 952.3 [917.3–1013.4] n=4 | +0.0% | nominal | ◇cpu-capped 4/4 records, ceiling fall ≤ 63.2 % |
| litert-lm-gpu | litert-community/gemma-4-E4B-it-litert-lm | litert-community_gemma-4-E4B-it-litert-lm_gemma-4-E4B-it.litertlm / wNa8o8 (int2/int4/int8 + int8 activations, QAT) | 4096 | 1654 | 256 [256–256] n=4 (0 / 0) | 1009.9 [1003.8–1015.4] n=4 | 1710 [1700–1720] n=4 | 14.8 [13.7–14.9] n=4 | 1090.5 [1034.0–1119.4] n=4 | -2.5% | nominal | ◇cpu-capped 4/4 records, ceiling fall ≤ 63.2 % |
| litert-lm-gpu | litert-community/gemma-4-E4B-it-litert-lm | litert-community_gemma-4-E4B-it-litert-lm_gemma-4-E4B-it.litertlm / wNa8o8 (int2/int4/int8 + int8 activations, QAT) | 8192 | 1654 | 256 [256–256] n=4 (0 / 0) | 875.0 [874.0–888.4] n=4 | 1960 [1930–1960] n=4 | 14.5 [13.9–14.6] n=4 | 1133.3 [1005.7–1235.2] n=4 | -4.0% | nominal | ◇cpu-capped 4/4 records, ceiling fall ≤ 63.2 % |

RSS basis: sampled launch VmHWM, MiB

Δ 2304→4096 (ratio of decode medians): -2.5%

Δ 2304→8192 (ratio of decode medians): -4.0%

csv: results/raw/2026-10-12-catalog-x2-s26-android-e4b-gpu-retake/ladder-warm.csv
