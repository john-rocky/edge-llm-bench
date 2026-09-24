# 2026-09-24-dashboard-longctx-v1-s26-android-gpu-retake — long-context-2048-gen256, regime warm (median [min–max] over rounds)

Selected rounds: 1,2,3,4,5,6; admission remains the session reviewer's decision.


## litert-lm-gpu — litert-community/gemma-4-E2B-it-litert-lm

| arm | model | file / recipe | ctx | prompt tok | out tok (short / unknown) | prefill tok/s | TTFT ms | decode tok/s | peak RSS | Δ from smallest ctx | thermal | flags |
|---|---|---|---:|---:|---|---|---|---|---|---:|---|---|
| litert-lm-gpu | litert-community/gemma-4-E2B-it-litert-lm | litert-community_gemma-4-E2B-it-litert-lm_gemma-4-E2B-it.litertlm / wNa8o8 (int2/int4/int8 + int8 activations, QAT) | 2304 | 1637 | 256 [256–256] n=6 (0 / 0) | 2837.0 [2823.7–2924.5] n=6 | 615 [600–620] n=6 | 26.1 [25.7–27.1] n=6 | 825.1 [768.5–843.1] n=6 | +0.0% | nominal |  |
| litert-lm-gpu | litert-community/gemma-4-E2B-it-litert-lm | litert-community_gemma-4-E2B-it-litert-lm_gemma-4-E2B-it.litertlm / wNa8o8 (int2/int4/int8 + int8 activations, QAT) | 4096 | 1637 | 256 [256–256] n=6 (0 / 0) | 2495.3 [2476.2–2552.6] n=6 | 690 [680–700] n=6 | 26.8 [25.6–29.8] n=6 | 852.4 [788.9–859.9] n=6 | +2.6% | nominal |  |
| litert-lm-gpu | litert-community/gemma-4-E2B-it-litert-lm | litert-community_gemma-4-E2B-it-litert-lm_gemma-4-E2B-it.litertlm / wNa8o8 (int2/int4/int8 + int8 activations, QAT) | 8192 | 1637 | 93 [93–93] n=6 (6 / 0) | 1961.5 [1957.3–1988.4] n=6 | 870 [860–880] n=6 | 25.5 [25.1–26.0] n=6 | 838.9 [740.4–860.2] n=6 | -2.6% | nominal |  |

RSS basis: sampled launch VmHWM, MiB

Δ 2304→4096 (ratio of decode medians): +2.6%

Δ 2304→8192 (ratio of decode medians): -2.6%

## litert-lm-gpu — litert-community/gemma-4-E4B-it-litert-lm

| arm | model | file / recipe | ctx | prompt tok | out tok (short / unknown) | prefill tok/s | TTFT ms | decode tok/s | peak RSS | Δ from smallest ctx | thermal | flags |
|---|---|---|---:|---:|---|---|---|---|---|---:|---|---|
| litert-lm-gpu | litert-community/gemma-4-E4B-it-litert-lm | litert-community_gemma-4-E4B-it-litert-lm_gemma-4-E4B-it.litertlm / wNa8o8 (int2/int4/int8 + int8 activations, QAT) | 2304 | 1637 | 61 [61–61] n=6 (6 / 0) | 1073.1 [1071.8–1080.4] n=6 | 1590 [1580–1600] n=6 | 14.9 [14.7–15.6] n=6 | 859.4 [829.7–1018.8] n=6 | +0.0% | nominal |  |
| litert-lm-gpu | litert-community/gemma-4-E4B-it-litert-lm | litert-community_gemma-4-E4B-it-litert-lm_gemma-4-E4B-it.litertlm / wNa8o8 (int2/int4/int8 + int8 activations, QAT) | 4096 | 1637 | 57 [57–57] n=6 (6 / 0) | 1002.7 [954.5–1008.6] n=6 | 1700 [1690–1780] n=6 | 14.8 [14.7–15.3] n=6 | 967.2 [865.0–1080.5] n=6 | -0.8% | nominal |  |
| litert-lm-gpu | litert-community/gemma-4-E4B-it-litert-lm | litert-community_gemma-4-E4B-it-litert-lm_gemma-4-E4B-it.litertlm / wNa8o8 (int2/int4/int8 + int8 activations, QAT) | 8192 | 1637 | 50 [50–50] n=6 (6 / 0) | 865.3 [845.6–867.5] n=6 | 1960 [1960–2010] n=6 | 14.5 [14.4–15.2] n=6 | 1025.2 [962.6–1197.8] n=6 | -3.0% | nominal |  |

RSS basis: sampled launch VmHWM, MiB

Δ 2304→4096 (ratio of decode medians): -0.8%

Δ 2304→8192 (ratio of decode medians): -3.0%

csv: results/raw/2026-09-24-dashboard-longctx-v1-s26-android-gpu-retake/ladder-warm.csv
