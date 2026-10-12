# 2026-10-12-catalog-x2-s26-android-e4b-gpu-retake — long-context-2048-gen256-noref, regime first-ever (median [min–max] over rounds)

Selected rounds: 1,2,3,4; admission remains the session reviewer's decision.

First-ever cache-build observations only; these are not engine-speed estimates.


## litert-lm-gpu — litert-community/gemma-4-E4B-it-litert-lm

| arm | model | file / recipe | ctx | prompt tok | out tok (short / unknown) | prefill tok/s | TTFT ms | decode tok/s | peak RSS | Δ from smallest ctx | thermal | flags |
|---|---|---|---:|---:|---|---|---|---|---|---:|---|---|
| litert-lm-gpu | litert-community/gemma-4-E4B-it-litert-lm | litert-community_gemma-4-E4B-it-litert-lm_gemma-4-E4B-it.litertlm / wNa8o8 (int2/int4/int8 + int8 activations, QAT) | 2304 | 1654 | 256 [256–256] n=1 (0 / 0) | 912.4 [912.4–912.4] n=1 | 1880 [1880–1880] n=1 | 14.6 [14.6–14.6] n=1 | 917.3 [917.3–917.3] n=1 | +0.0% | nominal | ◇cpu-capped 1/1 records, ceiling fall ≤ 58.3 % |
| litert-lm-gpu | litert-community/gemma-4-E4B-it-litert-lm | litert-community_gemma-4-E4B-it-litert-lm_gemma-4-E4B-it.litertlm / wNa8o8 (int2/int4/int8 + int8 activations, QAT) | 4096 | 1654 | 256 [256–256] n=1 (0 / 0) | 1018.5 [1018.5–1018.5] n=1 | 1690 [1690–1690] n=1 | 14.8 [14.8–14.8] n=1 | 1119.4 [1119.4–1119.4] n=1 | +0.8% | nominal | ◇cpu-capped 1/1 records, ceiling fall ≤ 58.3 % |
| litert-lm-gpu | litert-community/gemma-4-E4B-it-litert-lm | litert-community_gemma-4-E4B-it-litert-lm_gemma-4-E4B-it.litertlm / wNa8o8 (int2/int4/int8 + int8 activations, QAT) | 8192 | 1654 | 256 [256–256] n=1 (0 / 0) | 882.2 [882.2–882.2] n=1 | 1940 [1940–1940] n=1 | 14.5 [14.5–14.5] n=1 | 1235.2 [1235.2–1235.2] n=1 | -1.0% | nominal | ◇cpu-capped 1/1 records, ceiling fall ≤ 58.3 % |

RSS basis: sampled launch VmHWM, MiB

Δ 2304→4096 (ratio of decode medians): +0.8%

Δ 2304→8192 (ratio of decode medians): -1.0%

csv: results/raw/2026-10-12-catalog-x2-s26-android-e4b-gpu-retake/ladder-first-ever.csv
