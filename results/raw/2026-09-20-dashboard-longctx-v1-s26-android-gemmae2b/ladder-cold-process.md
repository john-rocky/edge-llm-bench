# 2026-09-20-dashboard-longctx-v1-s26-android-gemmae2b — long-context-2048-gen256, regime cold-process (median [min–max] over rounds)

Selected rounds: 1,2,3,4,5; admission remains the session reviewer's decision.


## llama.cpp — unsloth/gemma-4-E2B-it-GGUF

| arm | model | file / recipe | ctx | prompt tok | out tok (short / unknown) | prefill tok/s | TTFT ms | decode tok/s | peak RSS | Δ from smallest ctx | thermal | flags |
|---|---|---|---:|---:|---|---|---|---|---|---:|---|---|
| llama.cpp | unsloth/gemma-4-E2B-it-GGUF | unsloth_gemma-4-E2B-it-GGUF_gemma-4-E2B-it-Q4_K_M.gguf / Q4_K_M | 2304 | None | — (0 / 5) | 17.9 [16.8–18.5] n=5 | — | 14.2 [12.0–14.3] n=5 | 4224.8 [3551.8–4509.2] n=5 | +0.0% | nominal |  |
| llama.cpp | unsloth/gemma-4-E2B-it-GGUF | unsloth_gemma-4-E2B-it-GGUF_gemma-4-E2B-it-Q4_K_M.gguf / Q4_K_M | 4096 | None | — (0 / 5) | 18.3 [18.2–19.8] n=5 | — | 14.3 [13.9–14.7] n=5 | 4133.8 [3938.8–4523.3] n=5 | +0.7% | nominal |  |
| llama.cpp | unsloth/gemma-4-E2B-it-GGUF | unsloth_gemma-4-E2B-it-GGUF_gemma-4-E2B-it-Q4_K_M.gguf / Q4_K_M | 8192 | None | — (0 / 5) | 18.4 [18.3–18.5] n=5 | — | 14.4 [14.3–14.4] n=5 | 4230.6 [4016.5–4555.7] n=5 | +1.4% | nominal |  |

RSS basis: sampled launch VmHWM, MiB

Δ 2304→4096 (ratio of decode medians): +0.7%

Δ 2304→8192 (ratio of decode medians): +1.4%

csv: results/raw/2026-09-20-dashboard-longctx-v1-s26-android-gemmae2b/ladder-cold-process.csv
