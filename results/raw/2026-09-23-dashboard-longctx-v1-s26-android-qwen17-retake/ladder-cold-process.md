# 2026-09-23-dashboard-longctx-v1-s26-android-qwen17-retake — long-context-2048-gen256, regime cold-process (median [min–max] over rounds)

Selected rounds: 1,2,3,4,5,6; admission remains the session reviewer's decision.


## llama.cpp — unsloth/Qwen3-1.7B-GGUF

| arm | model | file / recipe | ctx | prompt tok | out tok (short / unknown) | prefill tok/s | TTFT ms | decode tok/s | peak RSS | Δ from smallest ctx | thermal | flags |
|---|---|---|---:|---:|---|---|---|---|---|---:|---|---|
| llama.cpp | unsloth/Qwen3-1.7B-GGUF | unsloth_Qwen3-1.7B-GGUF_Qwen3-1.7B-Q4_K_M.gguf / Q4_K_M | 2304 | None | — (0 / 6) | 24.2 [22.6–24.5] n=6 | — | 15.3 [15.3–15.6] n=6 | 2458.6 [2457.8–2459.3] n=6 | +0.0% | nominal |  |
| llama.cpp | unsloth/Qwen3-1.7B-GGUF | unsloth_Qwen3-1.7B-GGUF_Qwen3-1.7B-Q4_K_M.gguf / Q4_K_M | 4096 | None | — (0 / 6) | 24.4 [24.1–24.5] n=6 | — | 15.4 [15.3–15.8] n=6 | 2656.1 [2655.4–2656.8] n=6 | +1.0% | nominal |  |
| llama.cpp | unsloth/Qwen3-1.7B-GGUF | unsloth_Qwen3-1.7B-GGUF_Qwen3-1.7B-Q4_K_M.gguf / Q4_K_M | 8192 | None | — (0 / 6) | 24.4 [24.2–24.5] n=6 | — | 15.5 [15.2–15.6] n=6 | 3116.2 [3115.6–3116.6] n=6 | +1.3% | nominal |  |

RSS basis: sampled launch VmHWM, MiB

Δ 2304→4096 (ratio of decode medians): +1.0%

Δ 2304→8192 (ratio of decode medians): +1.3%

csv: results/raw/2026-09-23-dashboard-longctx-v1-s26-android-qwen17-retake/ladder-cold-process.csv
