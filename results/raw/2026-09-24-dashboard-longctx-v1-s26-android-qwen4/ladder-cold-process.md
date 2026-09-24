# 2026-09-24-dashboard-longctx-v1-s26-android-qwen4 — long-context-2048-gen256, regime cold-process (median [min–max] over rounds)

Selected rounds: 1,2,3,4,5; admission remains the session reviewer's decision.


## llama.cpp — unsloth/Qwen3-4B-GGUF

| arm | model | file / recipe | ctx | prompt tok | out tok (short / unknown) | prefill tok/s | TTFT ms | decode tok/s | peak RSS | Δ from smallest ctx | thermal | flags |
|---|---|---|---:|---:|---|---|---|---|---|---:|---|---|
| llama.cpp | unsloth/Qwen3-4B-GGUF | unsloth_Qwen3-4B-GGUF_Qwen3-4B-Q4_K_M.gguf / Q4_K_M | 2304 | None | — (0 / 5) | 8.8 [8.6–8.9] n=5 | — | 7.5 [7.2–7.6] n=5 | 5206.7 [4711.6–5207.3] n=5 | +0.0% | nominal |  |
| llama.cpp | unsloth/Qwen3-4B-GGUF | unsloth_Qwen3-4B-GGUF_Qwen3-4B-Q4_K_M.gguf / Q4_K_M | 4096 | None | — (0 / 5) | 8.8 [8.7–8.9] n=5 | — | 7.5 [7.2–7.5] n=5 | 5454.4 [5440.3–5457.0] n=5 | +0.0% | nominal |  |
| llama.cpp | unsloth/Qwen3-4B-GGUF | unsloth_Qwen3-4B-GGUF_Qwen3-4B-Q4_K_M.gguf / Q4_K_M | 8192 | None | — (0 / 5) | 8.9 [8.8–8.9] n=5 | — | 7.4 [7.2–7.5] n=5 | 6034.9 [6021.0–6037.2] n=5 | -1.3% | nominal |  |

RSS basis: sampled launch VmHWM, MiB

Δ 2304→4096 (ratio of decode medians): +0.0%

Δ 2304→8192 (ratio of decode medians): -1.3%

csv: results/raw/2026-09-24-dashboard-longctx-v1-s26-android-qwen4/ladder-cold-process.csv
