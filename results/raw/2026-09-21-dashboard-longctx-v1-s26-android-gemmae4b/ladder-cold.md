# 2026-09-21-dashboard-longctx-v1-s26-android-gemmae4b — long-context-2048-gen256, regime cold (median [min–max] over rounds)

Selected rounds: 1,2,3,4,5; admission remains the session reviewer's decision.


## litert-lm-cpu — litert-community/gemma-4-E4B-it-litert-lm

| arm | model | file / recipe | ctx | prompt tok | out tok (short / unknown) | prefill tok/s | TTFT ms | decode tok/s | peak RSS | Δ from smallest ctx | thermal | flags |
|---|---|---|---:|---:|---|---|---|---|---|---:|---|---|
| litert-lm-cpu | litert-community/gemma-4-E4B-it-litert-lm | litert-community_gemma-4-E4B-it-litert-lm_gemma-4-E4B-it.litertlm / wNa8o8 (int2/int4/int8 + int8 activations, QAT) | 2304 | 1637 | 256 [256–256] n=4 (0 / 0) | 116.2 [114.0–118.9] n=4 | 14165 [13840–14430] n=4 | 14.3 [13.6–14.5] n=4 | 4155.2 [3929.5–4336.8] n=4 | +0.0% | nominal |  |
| litert-lm-cpu | litert-community/gemma-4-E4B-it-litert-lm | litert-community_gemma-4-E4B-it-litert-lm_gemma-4-E4B-it.litertlm / wNa8o8 (int2/int4/int8 + int8 activations, QAT) | 4096 | 1637 | 256 [256–256] n=4 (0 / 0) | 94.2 [90.0–105.7] n=4 | 17455 [15580–18270] n=4 | 12.1 [11.7–12.3] n=4 | 5111.6 [4348.6–5638.5] n=4 | -15.2% | nominal |  |

RSS basis: sampled launch VmHWM, MiB

Δ 2304→4096 (ratio of decode medians): -15.2%

## litert-lm-gpu — litert-community/gemma-4-E4B-it-litert-lm

| arm | model | file / recipe | ctx | prompt tok | out tok (short / unknown) | prefill tok/s | TTFT ms | decode tok/s | peak RSS | Δ from smallest ctx | thermal | flags |
|---|---|---|---:|---:|---|---|---|---|---|---:|---|---|
| litert-lm-gpu | litert-community/gemma-4-E4B-it-litert-lm | litert-community_gemma-4-E4B-it-litert-lm_gemma-4-E4B-it.litertlm / wNa8o8 (int2/int4/int8 + int8 activations, QAT) | 2304 | 1637 | 61 [61–61] n=5 (5 / 0) | 1056.1 [920.3–1103.1] n=5 | 1620 [1550–1840] n=5 | 15.5 [15.2–16.9] n=5 | 898.4 [802.9–966.6] n=5 | +0.0% | nominal |  |
| litert-lm-gpu | litert-community/gemma-4-E4B-it-litert-lm | litert-community_gemma-4-E4B-it-litert-lm_gemma-4-E4B-it.litertlm / wNa8o8 (int2/int4/int8 + int8 activations, QAT) | 4096 | 1637 | 57 [57–57] n=4 (4 / 0) | 1017.6 [1001.5–1023.9] n=4 | 1675 [1660–1700] n=4 | 15.1 [14.7–15.5] n=4 | 971.4 [902.5–1055.9] n=4 | -2.9% | nominal |  |
| litert-lm-gpu | litert-community/gemma-4-E4B-it-litert-lm | litert-community_gemma-4-E4B-it-litert-lm_gemma-4-E4B-it.litertlm / wNa8o8 (int2/int4/int8 + int8 activations, QAT) | 8192 | 1637 | 50 [50–50] n=4 (4 / 0) | 800.3 [743.3–878.9] n=4 | 2120 [1930–2270] n=4 | 15.3 [14.7–15.4] n=4 | 1084.8 [1045.9–1158.2] n=4 | -1.4% | nominal |  |

RSS basis: sampled launch VmHWM, MiB

Δ 2304→4096 (ratio of decode medians): -2.9%

Δ 2304→8192 (ratio of decode medians): -1.4%

csv: results/raw/2026-09-21-dashboard-longctx-v1-s26-android-gemmae4b/ladder-cold.csv
