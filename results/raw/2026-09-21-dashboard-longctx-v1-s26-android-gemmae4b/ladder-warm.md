# 2026-09-21-dashboard-longctx-v1-s26-android-gemmae4b — long-context-2048-gen256, regime warm (median [min–max] over rounds)

Selected rounds: 1,2,3,4,5; admission remains the session reviewer's decision.


## litert-lm-cpu — litert-community/gemma-4-E4B-it-litert-lm

| arm | model | file / recipe | ctx | prompt tok | out tok (short / unknown) | prefill tok/s | TTFT ms | decode tok/s | peak RSS | Δ from smallest ctx | thermal | flags |
|---|---|---|---:|---:|---|---|---|---|---|---:|---|---|
| litert-lm-cpu | litert-community/gemma-4-E4B-it-litert-lm | litert-community_gemma-4-E4B-it-litert-lm_gemma-4-E4B-it.litertlm / wNa8o8 (int2/int4/int8 + int8 activations, QAT) | 2304 | 1637 | 256 [256–256] n=5 (0 / 0) | 78.8 [78.3–89.8] n=5 | 20830 [18300–20970] n=5 | 14.5 [14.5–15.0] n=5 | 4002.4 [3663.6–4336.8] n=5 | +0.0% | nominal |  |
| litert-lm-cpu | litert-community/gemma-4-E4B-it-litert-lm | litert-community_gemma-4-E4B-it-litert-lm_gemma-4-E4B-it.litertlm / wNa8o8 (int2/int4/int8 + int8 activations, QAT) | 4096 | 1637 | 256 [256–256] n=5 (0 / 0) | 71.0 [69.9–78.5] n=5 | 23150 [20930–23500] n=5 | 12.9 [12.8–13.1] n=5 | 4652.9 [4348.6–5638.5] n=5 | -10.9% | nominal |  |

RSS basis: sampled launch VmHWM, MiB

Δ 2304→4096 (ratio of decode medians): -10.9%

## litert-lm-gpu — litert-community/gemma-4-E4B-it-litert-lm

| arm | model | file / recipe | ctx | prompt tok | out tok (short / unknown) | prefill tok/s | TTFT ms | decode tok/s | peak RSS | Δ from smallest ctx | thermal | flags |
|---|---|---|---:|---:|---|---|---|---|---|---:|---|---|
| litert-lm-gpu | litert-community/gemma-4-E4B-it-litert-lm | litert-community_gemma-4-E4B-it-litert-lm_gemma-4-E4B-it.litertlm / wNa8o8 (int2/int4/int8 + int8 activations, QAT) | 2304 | 1637 | 61 [61–61] n=5 (5 / 0) | 1084.9 [1022.6–1085.7] n=5 | 1580 [1570–1670] n=5 | 15.1 [12.5–15.4] n=5 | 898.4 [802.9–966.6] n=5 | +0.0% | nominal |  |
| litert-lm-gpu | litert-community/gemma-4-E4B-it-litert-lm | litert-community_gemma-4-E4B-it-litert-lm_gemma-4-E4B-it.litertlm / wNa8o8 (int2/int4/int8 + int8 activations, QAT) | 4096 | 1637 | 57 [57–57] n=5 (5 / 0) | 1000.7 [896.8–1012.8] n=5 | 1740 [1680–1910] n=5 | 11.9 [9.7–15.9] n=5 | 923.9 [847.7–1055.9] n=5 | -21.1% | nominal |  |
| litert-lm-gpu | litert-community/gemma-4-E4B-it-litert-lm | litert-community_gemma-4-E4B-it-litert-lm_gemma-4-E4B-it.litertlm / wNa8o8 (int2/int4/int8 + int8 activations, QAT) | 8192 | 1637 | 50 [50–50] n=5 (5 / 0) | 867.0 [862.7–876.6] n=5 | 1960 [1930–1970] n=5 | 14.8 [13.8–15.3] n=5 | 1121.2 [1045.9–1192.4] n=5 | -2.3% | nominal |  |

RSS basis: sampled launch VmHWM, MiB

Δ 2304→4096 (ratio of decode medians): -21.1%

Δ 2304→8192 (ratio of decode medians): -2.3%

csv: results/raw/2026-09-21-dashboard-longctx-v1-s26-android-gemmae4b/ladder-warm.csv
