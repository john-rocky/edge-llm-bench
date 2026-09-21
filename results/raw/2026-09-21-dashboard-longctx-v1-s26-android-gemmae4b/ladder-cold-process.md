# 2026-09-21-dashboard-longctx-v1-s26-android-gemmae4b — long-context-2048-gen256, regime cold-process (median [min–max] over rounds)

Selected rounds: 1,2,3,4,5; admission remains the session reviewer's decision.


## llama.cpp — unsloth/gemma-4-E4B-it-GGUF

| arm | model | file / recipe | ctx | prompt tok | out tok (short / unknown) | prefill tok/s | TTFT ms | decode tok/s | peak RSS | Δ from smallest ctx | thermal | flags |
|---|---|---|---:|---:|---|---|---|---|---|---:|---|---|
| llama.cpp | unsloth/gemma-4-E4B-it-GGUF | unsloth_gemma-4-E4B-it-GGUF_gemma-4-E4B-it-Q4_K_M.gguf / Q4_K_M | 2304 | None | — (0 / 5) | 12.4 [10.0–14.7] n=5 | — | 8.3 [6.6–8.5] n=5 | 6042.1 [5675.7–6378.5] n=5 | +0.0% | nominal |  |
| llama.cpp | unsloth/gemma-4-E4B-it-GGUF | unsloth_gemma-4-E4B-it-GGUF_gemma-4-E4B-it-Q4_K_M.gguf / Q4_K_M | 4096 | None | — (0 / 5) | 12.3 [11.2–12.4] n=5 | — | 8.4 [7.7–8.5] n=5 | 6154.2 [5942.4–6610.2] n=5 | +1.2% | nominal |  |
| llama.cpp | unsloth/gemma-4-E4B-it-GGUF | unsloth_gemma-4-E4B-it-GGUF_gemma-4-E4B-it-Q4_K_M.gguf / Q4_K_M | 8192 | None | — (0 / 5) | 11.9 [10.3–12.5] n=5 | — | 8.4 [8.3–8.4] n=5 | 6470.0 [6107.6–6727.5] n=5 | +1.2% | nominal |  |

RSS basis: sampled launch VmHWM, MiB

Δ 2304→4096 (ratio of decode medians): +1.2%

Δ 2304→8192 (ratio of decode medians): +1.2%

csv: results/raw/2026-09-21-dashboard-longctx-v1-s26-android-gemmae4b/ladder-cold-process.csv
