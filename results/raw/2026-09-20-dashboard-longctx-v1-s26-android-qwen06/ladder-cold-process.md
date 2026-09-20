# 2026-09-20-dashboard-longctx-v1-s26-android-qwen06 — long-context-2048-gen256, regime cold-process (median [min–max] over rounds)

Selected rounds: 1,2,3,4,5,6; admission remains the session reviewer's decision.


## llama.cpp — unsloth/Qwen3-0.6B-GGUF

| arm | model | file / recipe | ctx | prompt tok | out tok (short / unknown) | prefill tok/s | TTFT ms | decode tok/s | peak RSS | Δ from smallest ctx | thermal | flags |
|---|---|---|---:|---:|---|---|---|---|---|---:|---|---|
| llama.cpp | unsloth/Qwen3-0.6B-GGUF | unsloth_Qwen3-0.6B-GGUF_Qwen3-0.6B-Q4_K_M.gguf / Q4_K_M | 2304 | None | — (0 / 6) | 27.1 [26.2–27.6] n=6 | — | 21.1 [20.7–21.2] n=6 | 1084.3 [1083.8–1084.5] n=6 | +0.0% | nominal |  |
| llama.cpp | unsloth/Qwen3-0.6B-GGUF | unsloth_Qwen3-0.6B-GGUF_Qwen3-0.6B-Q4_K_M.gguf / Q4_K_M | 4096 | None | — (0 / 6) | 27.4 [26.7–27.5] n=6 | — | 20.9 [20.6–21.1] n=6 | 1283.8 [1283.4–1283.9] n=6 | -1.0% | nominal |  |
| llama.cpp | unsloth/Qwen3-0.6B-GGUF | unsloth_Qwen3-0.6B-GGUF_Qwen3-0.6B-Q4_K_M.gguf / Q4_K_M | 8192 | None | — (0 / 6) | 27.0 [26.6–27.8] n=6 | — | 20.9 [20.9–21.3] n=6 | 1729.7 [1729.6–1730.0] n=6 | -0.5% | nominal |  |

RSS basis: sampled launch VmHWM, MiB

Δ 2304→4096 (ratio of decode medians): -1.0%

Δ 2304→8192 (ratio of decode medians): -0.5%

csv: results/raw/2026-09-20-dashboard-longctx-v1-s26-android-qwen06/ladder-cold-process.csv
