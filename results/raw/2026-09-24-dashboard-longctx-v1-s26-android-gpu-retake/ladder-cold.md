# 2026-09-24-dashboard-longctx-v1-s26-android-gpu-retake — long-context-2048-gen256, regime cold (median [min–max] over rounds)

Selected rounds: 1,2,3,4,5,6; admission remains the session reviewer's decision.


## litert-lm-gpu — litert-community/gemma-4-E2B-it-litert-lm

| arm | model | file / recipe | ctx | prompt tok | out tok (short / unknown) | prefill tok/s | TTFT ms | decode tok/s | peak RSS | Δ from smallest ctx | thermal | flags |
|---|---|---|---:|---:|---|---|---|---|---|---:|---|---|
| litert-lm-gpu | litert-community/gemma-4-E2B-it-litert-lm | litert-community_gemma-4-E2B-it-litert-lm_gemma-4-E2B-it.litertlm / wNa8o8 (int2/int4/int8 + int8 activations, QAT) | 2304 | 1637 | 256 [256–256] n=6 (0 / 0) | 2843.0 [2401.0–2944.9] n=6 | 615 [600–720] n=6 | 26.2 [25.2–28.8] n=6 | 825.1 [768.5–843.1] n=6 | +0.0% | nominal |  |
| litert-lm-gpu | litert-community/gemma-4-E2B-it-litert-lm | litert-community_gemma-4-E2B-it-litert-lm_gemma-4-E2B-it.litertlm / wNa8o8 (int2/int4/int8 + int8 activations, QAT) | 4096 | 1637 | 256 [256–256] n=6 (0 / 0) | 2465.4 [2310.0–2555.7] n=6 | 700 [680–750] n=6 | 26.5 [25.1–26.9] n=6 | 852.4 [788.9–859.9] n=6 | +1.0% | nominal |  |
| litert-lm-gpu | litert-community/gemma-4-E2B-it-litert-lm | litert-community_gemma-4-E2B-it-litert-lm_gemma-4-E2B-it.litertlm / wNa8o8 (int2/int4/int8 + int8 activations, QAT) | 8192 | 1637 | 93 [93–93] n=6 (6 / 0) | 1819.4 [1456.5–1985.5] n=6 | 940 [860–1160] n=6 | 25.6 [25.0–31.2] n=6 | 838.9 [740.4–860.2] n=6 | -2.4% | nominal |  |

RSS basis: sampled launch VmHWM, MiB

Δ 2304→4096 (ratio of decode medians): +1.0%

Δ 2304→8192 (ratio of decode medians): -2.4%

## litert-lm-gpu — litert-community/gemma-4-E4B-it-litert-lm

| arm | model | file / recipe | ctx | prompt tok | out tok (short / unknown) | prefill tok/s | TTFT ms | decode tok/s | peak RSS | Δ from smallest ctx | thermal | flags |
|---|---|---|---:|---:|---|---|---|---|---|---:|---|---|
| litert-lm-gpu | litert-community/gemma-4-E4B-it-litert-lm | litert-community_gemma-4-E4B-it-litert-lm_gemma-4-E4B-it.litertlm / wNa8o8 (int2/int4/int8 + int8 activations, QAT) | 2304 | 1637 | 61 [61–61] n=6 (6 / 0) | 1071.9 [893.7–1102.5] n=6 | 1600 [1550–1890] n=6 | 14.9 [14.5–16.3] n=6 | 859.4 [829.7–1018.8] n=6 | +0.0% | nominal |  |
| litert-lm-gpu | litert-community/gemma-4-E4B-it-litert-lm | litert-community_gemma-4-E4B-it-litert-lm_gemma-4-E4B-it.litertlm / wNa8o8 (int2/int4/int8 + int8 activations, QAT) | 4096 | 1637 | 57 [57–57] n=6 (6 / 0) | 1000.6 [892.8–1019.3] n=6 | 1700 [1680–1900] n=6 | 14.7 [14.5–15.8] n=6 | 967.2 [865.0–1080.5] n=6 | -1.9% | nominal |  |
| litert-lm-gpu | litert-community/gemma-4-E4B-it-litert-lm | litert-community_gemma-4-E4B-it-litert-lm_gemma-4-E4B-it.litertlm / wNa8o8 (int2/int4/int8 + int8 activations, QAT) | 8192 | 1637 | 50 [50–50] n=6 (6 / 0) | 863.0 [849.6–869.6] n=6 | 1965 [1950–2000] n=6 | 14.2 [14.1–15.0] n=6 | 1025.2 [962.6–1197.8] n=6 | -4.8% | nominal |  |

RSS basis: sampled launch VmHWM, MiB

Δ 2304→4096 (ratio of decode medians): -1.9%

Δ 2304→8192 (ratio of decode medians): -4.8%

csv: results/raw/2026-09-24-dashboard-longctx-v1-s26-android-gpu-retake/ladder-cold.csv
