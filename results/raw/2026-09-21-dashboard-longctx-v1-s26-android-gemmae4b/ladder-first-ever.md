# 2026-09-21-dashboard-longctx-v1-s26-android-gemmae4b — long-context-2048-gen256, regime first-ever (median [min–max] over rounds)

Selected rounds: 1,2,3,4,5; admission remains the session reviewer's decision.

First-ever cache-build observations only; these are not engine-speed estimates.


## litert-lm-cpu — litert-community/gemma-4-E4B-it-litert-lm

| arm | model | file / recipe | ctx | prompt tok | out tok (short / unknown) | prefill tok/s | TTFT ms | decode tok/s | peak RSS | Δ from smallest ctx | thermal | flags |
|---|---|---|---:|---:|---|---|---|---|---|---:|---|---|
| litert-lm-cpu | litert-community/gemma-4-E4B-it-litert-lm | litert-community_gemma-4-E4B-it-litert-lm_gemma-4-E4B-it.litertlm / wNa8o8 (int2/int4/int8 + int8 activations, QAT) | 2304 | 1637 | 256 [256–256] n=1 (0 / 0) | 128.9 [128.9–128.9] n=1 | 12770 [12770–12770] n=1 | 14.5 [14.5–14.5] n=1 | 3663.6 [3663.6–3663.6] n=1 | +0.0% | nominal |  |
| litert-lm-cpu | litert-community/gemma-4-E4B-it-litert-lm | litert-community_gemma-4-E4B-it-litert-lm_gemma-4-E4B-it.litertlm / wNa8o8 (int2/int4/int8 + int8 activations, QAT) | 4096 | 1637 | 256 [256–256] n=1 (0 / 0) | 101.2 [101.2–101.2] n=1 | 16260 [16260–16260] n=1 | 12.4 [12.4–12.4] n=1 | 4652.9 [4652.9–4652.9] n=1 | -14.4% | nominal |  |

RSS basis: sampled launch VmHWM, MiB

Δ 2304→4096 (ratio of decode medians): -14.4%

## litert-lm-gpu — litert-community/gemma-4-E4B-it-litert-lm

| arm | model | file / recipe | ctx | prompt tok | out tok (short / unknown) | prefill tok/s | TTFT ms | decode tok/s | peak RSS | Δ from smallest ctx | thermal | flags |
|---|---|---|---:|---:|---|---|---|---|---|---:|---|---|
| litert-lm-gpu | litert-community/gemma-4-E4B-it-litert-lm | litert-community_gemma-4-E4B-it-litert-lm_gemma-4-E4B-it.litertlm / wNa8o8 (int2/int4/int8 + int8 activations, QAT) | 4096 | 1637 | 57 [57–57] n=1 (1 / 0) | 991.7 [991.7–991.7] n=1 | 1720 [1720–1720] n=1 | 15.2 [15.2–15.2] n=1 | 847.7 [847.7–847.7] n=1 | +0.0% | nominal |  |
| litert-lm-gpu | litert-community/gemma-4-E4B-it-litert-lm | litert-community_gemma-4-E4B-it-litert-lm_gemma-4-E4B-it.litertlm / wNa8o8 (int2/int4/int8 + int8 activations, QAT) | 8192 | 1637 | 50 [50–50] n=1 (1 / 0) | 766.0 [766.0–766.0] n=1 | 2200 [2200–2200] n=1 | 15.9 [15.9–15.9] n=1 | 1192.4 [1192.4–1192.4] n=1 | +4.3% | nominal |  |

RSS basis: sampled launch VmHWM, MiB

csv: results/raw/2026-09-21-dashboard-longctx-v1-s26-android-gemmae4b/ladder-first-ever.csv
