# Leaderboard — current standings per platform

Neutral, reproducible standings for local LLM runtimes on-device. Every number
carries its recipe (quantization + engine build): arms run at their own best
available build, which is only a fair comparison when the recipe is visible.
Method and rules: `methodology/fairness-rules.md`. Raw records: `results/`.
Regenerate: `python3 scripts/build_summary.py && python3 scripts/render_leaderboard.py`.

<!-- BEGIN GENERATED: scripts/render_leaderboard.py -->

Generated from `results/summary/*.csv` (latest capture 2026-08-27) by `scripts/render_leaderboard.py` — do not edit inside the markers.

Headline task: **short-chat**, warm = median of same-session warm runs (cold-warm-split); other tasks and full history: RESULTS.md. Rows sort by warm decode; the recipe (quantization, engine build) is part of every row — a faster number under a different recipe is a different deployment profile, not a win.

† = quantization label carries the audited in-place correction (Gemma-4 `.litertlm` is the wNa8o8 mobile schema; early rows recorded "INT4 (QAT)" — quant-label-rule). mem MB = phys_footprint on Apple rows, RSS on Android rows (no footprint equivalent; methodology/android.md).

## mac

### Mac Studio (M4 Max)

**Qwen 3 0.6B**

| runtime | artifact | quant | engine | warm tok/s | cold tok/s | prefill tok/s | TTFT ms | mem MB | GSM8K | captured |
|---|---|---|---|---|---|---|---|---|---|---|
| mlx-swift | `mlx-community/Qwen3-0.6B-4bit` | Q4 | 60bd0d7880c82980f9481f8be78862e9b63c58a3 | 502.4 | 491.6 | 1988.5 | 10.0 | 657.6 | — | 2026-08-27 |
| litert-lm | `litert-community/Qwen3-0.6B` | INT4 (mixed, blockwise gs32) | v0.16.0 | 309.9 | 311.3 | 566.9 | 59.0 | 795.4 | — | 2026-08-17 |

<details><summary>single-arm cells (no cross-runtime comparison)</summary>

| model | runtime | artifact | quant | engine | warm tok/s | cold tok/s | captured |
|---|---|---|---|---|---|---|---|
| Gemma 4 E2B | litert-lm | `litert-community/gemma-4-E2B-it-litert-lm` | wNa8o8 (int2/int4/int8 + int8 activations, QAT) | v0.16.0 | 156.0 | 128.9 | 2026-08-17 |
| litert-community/DeepSeek-R1-Distill-Qwen-1.5B | litert-lm | `litert-community/DeepSeek-R1-Distill-Qwen-1.5B` | INT8 | v0.16.0 | 77.7 | 78.7 | 2026-08-18 |
| litert-community/LFM2.5-1.2B-Instruct | litert-lm | `litert-community/LFM2.5-1.2B-Instruct` | int4_gpu (litert-community descriptor) | v0.16.0 | 325.8 | 335.2 | 2026-08-27 |
| litert-community/MiniCPM5-1B | litert-lm | `litert-community/MiniCPM5-1B` | wi4b32_wi8_afp32 (gpu-opt) | v0.16.0 | 123.2 | 122.6 | 2026-08-27 |
| mlx-community/DeepSeek-R1-Distill-Qwen-1.5B-4bit | mlx-swift | `mlx-community/DeepSeek-R1-Distill-Qwen-1.5B-4bit` | Q4 | 60bd0d7880c82980f9481f8be78862e9b63c58a3 | 146.2 | 145.9 | 2026-08-17 |
| mlx-community/LFM2.5-1.2B-Instruct-4bit | mlx-swift | `mlx-community/LFM2.5-1.2B-Instruct-4bit` | Q4 | 60bd0d7880c82980f9481f8be78862e9b63c58a3 | 518.4 | 516.7 | 2026-08-27 |
| mlx-community/MiniCPM5-1B-4bit | mlx-swift | `mlx-community/MiniCPM5-1B-4bit` | Q4 | 60bd0d7880c82980f9481f8be78862e9b63c58a3 | 540.8 | 528.0 | 2026-08-27 |

</details>

## ios

### iPhone 17 Pro

**Qwen 3 0.6B**

| runtime | artifact | quant | engine | warm tok/s | cold tok/s | prefill tok/s | TTFT ms | mem MB | GSM8K | captured |
|---|---|---|---|---|---|---|---|---|---|---|
| mlx-swift | `mlx-community/Qwen3-0.6B-4bit` | Q4 | 60bd0d7880c82980f9481f8be78862e9b63c58a3 | 178.8 | 178.7 | 533.6 | 37.0 | 488.2 | — | 2026-08-26 |
| core-ai | `core-ai/qwen3-0.6b-gpu` | INT4 (dynamic, macOS-26-era export) | 0.2.0+static-inputs-patch | 147.4 | 152.3 | 954.1 | 23.0 | 180.2 | — | 2026-08-26 |
| litert-lm | `litert-community/Qwen3-0.6B` | INT4 (mixed, blockwise gs32) | v0.16.0 | 121.6 | 120.6 | 183.9 | 151.5 | 465.4 | — | 2026-08-26 |

<details><summary>single-arm cells (no cross-runtime comparison)</summary>

| model | runtime | artifact | quant | engine | warm tok/s | cold tok/s | captured |
|---|---|---|---|---|---|---|---|
| Gemma 4 E2B | litert-lm | `litert-community/gemma-4-E2B-it-litert-lm` | wNa8o8 (int2/int4/int8 + int8 activations, QAT) | v0.16.0 | 51.0 | 55.4 | 2026-08-19 |
| core-ai/lfm2.5-1.2b-gpu | core-ai | `core-ai/lfm2.5-1.2b-gpu` | int8hu block32 sym (untied head) | 0.2.0+static-inputs-patch | 45.5 | 45.7 | 2026-08-26 |
| core-ai/minicpm5-1b-gpu | core-ai | `core-ai/minicpm5-1b-gpu` | INT8 (sym, dynamic) | 0.2.0+static-inputs-patch | 72.1 | 72.2 | 2026-08-26 |
| litert-community/DeepSeek-R1-Distill-Qwen-1.5B | litert-lm | `litert-community/DeepSeek-R1-Distill-Qwen-1.5B` | INT8 | v0.16.0 | 26.7 | 31.2 | 2026-08-24 |
| litert-community/LFM2.5-1.2B-Instruct | litert-lm | `litert-community/LFM2.5-1.2B-Instruct` | int4_gpu (litert-community descriptor) | v0.16.0 | 69.5 | 69.9 | 2026-08-26 |
| litert-community/MiniCPM5-1B | litert-lm | `litert-community/MiniCPM5-1B` | wi4b32_wi8_afp32 (gpu-opt) | v0.16.0 | 34.2 | 36.2 | 2026-08-26 |
| litert-community/Qwen3-4B | litert-lm | `litert-community/Qwen3-4B` | INT4 (mixed, blockwise gs32) | v0.16.0 | 16.1 | 23.1 | 2026-08-19 |

</details>

**Structural exclusions** (failed-runs-stay — the row exists, the reason is the datum):

- `core-ai core-ai/phi-4-mini-gpu short-chat` — partial-rotary-unsupported
- `core-ai core-ai/qwen3-0.6b-ane short-chat` — invoke-fail-staticshape-logitsinference
- `core-ai core-ai/qwen3-1.7b-ane short-chat` — invoke-fail-bd71203

## android

### Pixel 8a

**Qwen 3 0.6B**

| runtime | artifact | quant | engine | warm tok/s | cold tok/s | prefill tok/s | TTFT ms | mem MB | GSM8K | captured |
|---|---|---|---|---|---|---|---|---|---|---|
| llama.cpp | `unsloth/Qwen3-0.6B-GGUF` | Q4_K_M | b8999 | — | 26.7 | 156.7 | — | 1252.1 | — | 2026-08-27 |
| litert-lm-gpu | `litert-community/Qwen3-0.6B` | INT4 (mixed, blockwise gs32) | v0.16.0 | — | 15.2 | 41.5 | 550.0 | 764.6 | — | 2026-08-17 |
| litert-lm-cpu | `litert-community/Qwen3-0.6B` | INT4 (mixed, blockwise gs32) | v0.16.0 | — | 15.3 | 9.8 | 2110.0 | 1250.1 | — | 2026-08-17 |

**litert-community/DeepSeek-R1-Distill-Qwen-1.5B**

| runtime | artifact | quant | engine | warm tok/s | cold tok/s | prefill tok/s | TTFT ms | mem MB | GSM8K | captured |
|---|---|---|---|---|---|---|---|---|---|---|
| litert-lm-gpu | `litert-community/DeepSeek-R1-Distill-Qwen-1.5B` | INT8 | v0.16.0 | — | 7.2 | 31.1 | 690.0 | 2508.8 | — | 2026-08-18 |
| litert-lm-cpu | `litert-community/DeepSeek-R1-Distill-Qwen-1.5B` | INT8 | v0.16.0 | — | 8.6 | 9.1 | 1870.0 | 1904.4 | — | 2026-08-18 |

**litert-community/LFM2.5-1.2B-Instruct**

| runtime | artifact | quant | engine | warm tok/s | cold tok/s | prefill tok/s | TTFT ms | mem MB | GSM8K | captured |
|---|---|---|---|---|---|---|---|---|---|---|
| litert-lm-gpu | `litert-community/LFM2.5-1.2B-Instruct` | int4_gpu (litert-community descriptor) | v0.16.0 | — | 19.1 | 72.6 | 340.0 | 1584.0 | — | 2026-08-18 |
| litert-lm-cpu | `litert-community/LFM2.5-1.2B-Instruct` | int4 (litert-community descriptor) | v0.16.0 | — | 18.3 | 11.0 | 1970.0 | 898.2 | — | 2026-08-18 |

**litert-community/MiniCPM5-1B**

| runtime | artifact | quant | engine | warm tok/s | cold tok/s | prefill tok/s | TTFT ms | mem MB | GSM8K | captured |
|---|---|---|---|---|---|---|---|---|---|---|
| litert-lm-gpu | `litert-community/MiniCPM5-1B` | wi4b32_wi8_afp32 (gpu-opt) | v0.16.0 | — | 12.7 | 48.5 | 500.0 | 1178.7 | — | 2026-08-18 |
| litert-lm-cpu | `litert-community/MiniCPM5-1B` | wi4b32_wi8_afp32 | v0.16.0 | — | 22.3 | 11.3 | 1940.0 | 886.0 | — | 2026-08-18 |

<details><summary>single-arm cells (no cross-runtime comparison)</summary>

| model | runtime | artifact | quant | engine | warm tok/s | cold tok/s | captured |
|---|---|---|---|---|---|---|---|
| Gemma 4 E2B | litert-lm-gpu | `litert-community/gemma-4-E2B-it-litert-lm` | wNa8o8 (int2/int4/int8 + int8 activations, QAT) | v0.16.0 | — | 8.4 | 2026-08-17 |
| LiquidAI/LFM2.5-1.2B-Instruct-GGUF | llama.cpp | `LiquidAI/LFM2.5-1.2B-Instruct-GGUF` | Q4_K_M | b8999 | — | 21.1 | 2026-08-27 |
| bartowski/DeepSeek-R1-Distill-Qwen-1.5B-GGUF | llama.cpp | `bartowski/DeepSeek-R1-Distill-Qwen-1.5B-GGUF` | Q4_K_M | b8999 | — | 9.2 | 2026-08-18 |
| openbmb/MiniCPM5-1B-GGUF | llama.cpp | `openbmb/MiniCPM5-1B-GGUF` | Q4_K_M | b8999 | — | 20.7 | 2026-08-27 |

</details>

### Galaxy S26

**Qwen 3 0.6B**

| runtime | artifact | quant | engine | warm tok/s | cold tok/s | prefill tok/s | TTFT ms | mem MB | GSM8K | captured |
|---|---|---|---|---|---|---|---|---|---|---|
| llama.cpp | `unsloth/Qwen3-0.6B-GGUF` | Q4_K_M | b8999 | — | 109.7 | 253.9 | — | 1251.6 | — | 2026-08-25 |
| litert-lm-gpu | `litert-community/Qwen3-0.6B` | INT4 (mixed, blockwise gs32) | v0.16.0 | — | 54.4 | 153.1 | 150.0 | 550.6 | — | 2026-08-25 |
| litert-lm-cpu | `litert-community/Qwen3-0.6B` | INT4 (mixed, blockwise gs32) | v0.16.0 | — | 27.7 | 23.8 | 870.0 | 2022.6 | — | 2026-08-25 |

**litert-community/DeepSeek-R1-Distill-Qwen-1.5B**

| runtime | artifact | quant | engine | warm tok/s | cold tok/s | prefill tok/s | TTFT ms | mem MB | GSM8K | captured |
|---|---|---|---|---|---|---|---|---|---|---|
| litert-lm-gpu | `litert-community/DeepSeek-R1-Distill-Qwen-1.5B` | INT8 | v0.16.0 | — | 22.9 | 101.5 | 200.0 | 558.2 | — | 2026-08-25 |
| litert-lm-cpu | `litert-community/DeepSeek-R1-Distill-Qwen-1.5B` | INT8 | v0.16.0 | — | 26.0 | 25.5 | 670.0 | 1950.3 | — | 2026-08-25 |

**litert-community/LFM2.5-1.2B-Instruct**

| runtime | artifact | quant | engine | warm tok/s | cold tok/s | prefill tok/s | TTFT ms | mem MB | GSM8K | captured |
|---|---|---|---|---|---|---|---|---|---|---|
| litert-lm-gpu | `litert-community/LFM2.5-1.2B-Instruct` | int4_gpu (litert-community descriptor) | v0.16.0 | — | 45.6 | 184.9 | 140.0 | 477.4 | — | 2026-08-25 |
| litert-lm-cpu | `litert-community/LFM2.5-1.2B-Instruct` | int4 (litert-community descriptor) | v0.16.0 | — | 51.2 | 23.4 | 920.0 | 284.3 | — | 2026-08-25 |

**litert-community/MiniCPM5-1B**

| runtime | artifact | quant | engine | warm tok/s | cold tok/s | prefill tok/s | TTFT ms | mem MB | GSM8K | captured |
|---|---|---|---|---|---|---|---|---|---|---|
| litert-lm-gpu | `litert-community/MiniCPM5-1B` | wi4b32_wi8_afp32 (gpu-opt) | v0.16.0 | — | 54.5 | 218.8 | 110.0 | 364.2 | — | 2026-08-25 |
| litert-lm-cpu | `litert-community/MiniCPM5-1B` | wi4b32_wi8_afp32 | v0.16.0 | — | 30.4 | 34.8 | 590.0 | 1047.3 | — | 2026-08-25 |

<details><summary>single-arm cells (no cross-runtime comparison)</summary>

| model | runtime | artifact | quant | engine | warm tok/s | cold tok/s | captured |
|---|---|---|---|---|---|---|---|
| Gemma 4 E2B | litert-lm-gpu | `litert-community/gemma-4-E2B-it-litert-lm` | wNa8o8 (int2/int4/int8 + int8 activations, QAT) | v0.16.0 | — | 27.8 | 2026-08-25 |
| bartowski/DeepSeek-R1-Distill-Qwen-1.5B-GGUF | llama.cpp | `bartowski/DeepSeek-R1-Distill-Qwen-1.5B-GGUF` | Q4_K_M | b8999 | — | 46.2 | 2026-08-25 |

</details>

<!-- END GENERATED: scripts/render_leaderboard.py -->
