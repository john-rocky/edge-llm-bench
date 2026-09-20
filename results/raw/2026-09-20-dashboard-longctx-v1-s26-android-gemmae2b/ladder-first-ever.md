# 2026-09-20-dashboard-longctx-v1-s26-android-gemmae2b — long-context-2048-gen256, regime first-ever (median [min–max] over rounds)

Selected rounds: 1,2,3,4,5; admission remains the session reviewer's decision.

First-ever cache-build observations only; these are not engine-speed estimates.


## litert-lm-cpu — litert-community/gemma-4-E2B-it-litert-lm

| arm | model | file / recipe | ctx | prompt tok | out tok (short / unknown) | prefill tok/s | TTFT ms | decode tok/s | peak RSS | Δ from smallest ctx | thermal | flags |
|---|---|---|---:|---:|---|---|---|---|---|---:|---|---|
| litert-lm-cpu | litert-community/gemma-4-E2B-it-litert-lm | litert-community_gemma-4-E2B-it-litert-lm_gemma-4-E2B-it.litertlm / wNa8o8 (int2/int4/int8 + int8 activations, QAT) | 2304 | 1637 | 256 [256–256] n=1 (0 / 0) | 396.2 [396.2–396.2] n=1 | 4160 [4160–4160] n=1 | 35.1 [35.1–35.1] n=1 | 2044.7 [2044.7–2044.7] n=1 | +0.0% | nominal |  |
| litert-lm-cpu | litert-community/gemma-4-E2B-it-litert-lm | litert-community_gemma-4-E2B-it-litert-lm_gemma-4-E2B-it.litertlm / wNa8o8 (int2/int4/int8 + int8 activations, QAT) | 4096 | 1637 | 256 [256–256] n=1 (0 / 0) | 356.3 [356.3–356.3] n=1 | 4630 [4630–4630] n=1 | 30.6 [30.6–30.6] n=1 | 2819.7 [2819.7–2819.7] n=1 | -13.0% | nominal |  |
| litert-lm-cpu | litert-community/gemma-4-E2B-it-litert-lm | litert-community_gemma-4-E2B-it-litert-lm_gemma-4-E2B-it.litertlm / wNa8o8 (int2/int4/int8 + int8 activations, QAT) | 8192 | 1637 | 256 [256–256] n=1 (0 / 0) | 224.9 [224.9–224.9] n=1 | 7340 [7340–7340] n=1 | 17.1 [17.1–17.1] n=1 | 4954.8 [4954.8–4954.8] n=1 | -51.4% | nominal |  |

RSS basis: sampled launch VmHWM, MiB

Δ 2304→4096 (ratio of decode medians): -13.0%

Δ 2304→8192 (ratio of decode medians): -51.4%

## litert-lm-gpu — litert-community/gemma-4-E2B-it-litert-lm

| arm | model | file / recipe | ctx | prompt tok | out tok (short / unknown) | prefill tok/s | TTFT ms | decode tok/s | peak RSS | Δ from smallest ctx | thermal | flags |
|---|---|---|---:|---:|---|---|---|---|---|---:|---|---|
| litert-lm-gpu | litert-community/gemma-4-E2B-it-litert-lm | litert-community_gemma-4-E2B-it-litert-lm_gemma-4-E2B-it.litertlm / wNa8o8 (int2/int4/int8 + int8 activations, QAT) | 4096 | 1637 | 256 [256–256] n=1 (0 / 0) | 2548.7 [2548.7–2548.7] n=1 | 680 [680–680] n=1 | 26.8 [26.8–26.8] n=1 | 752.2 [752.2–752.2] n=1 | +0.0% | nominal |  |
| litert-lm-gpu | litert-community/gemma-4-E2B-it-litert-lm | litert-community_gemma-4-E2B-it-litert-lm_gemma-4-E2B-it.litertlm / wNa8o8 (int2/int4/int8 + int8 activations, QAT) | 8192 | 1637 | 93 [93–93] n=1 (1 / 0) | 1959.5 [1959.5–1959.5] n=1 | 880 [880–880] n=1 | 25.1 [25.1–25.1] n=1 | 840.8 [840.8–840.8] n=1 | -6.3% | nominal |  |

RSS basis: sampled launch VmHWM, MiB

csv: results/raw/2026-09-20-dashboard-longctx-v1-s26-android-gemmae2b/ladder-first-ever.csv
