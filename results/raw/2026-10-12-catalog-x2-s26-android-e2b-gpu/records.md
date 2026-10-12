# Per-record table

Every stored record, launch order. pooled = what longctx_ab_report.py and spread.md read (◇ = a CPU-cap-only flag on an accelerator arm, kept and marked).

| round | launch | iteration | regime | arm | model | allocation | prompt tok | output tok | decode tok/s | prefill tok/s | TTFT ms | first-ever | thermal | flags | CPU ceiling fall % | pooled |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | 1 | cold-process | llama.cpp | Qwen3-0.6B-GGUF | 4096 |  |  | 105.8 | 390.4 |  | False | 0->0 |  | 0.0 | anchor |
| 1 | 2 | 1 | cold | litert-lm-gpu | gemma-4-E2B-it-litert-lm | 2304 | 1654 | 256 | 24.94 | 2949.02 | 600.0 | True | 0->0 | cpu-capped | 39.3 | no |
| 1 | 2 | 2 | warm | litert-lm-gpu | gemma-4-E2B-it-litert-lm | 2304 | 1654 | 256 | 25.76 | 2838.12 | 620.0 | False | 0->0 | ◇cpu-capped | 39.3 | yes |
| 1 | 3 | 1 | cold | litert-lm-gpu | gemma-4-E2B-it-litert-lm | 4096 | 1654 | 256 | 25.22 | 2539.73 | 690.0 | True | 0->0 | cpu-capped | 34.0 | no |
| 1 | 3 | 2 | warm | litert-lm-gpu | gemma-4-E2B-it-litert-lm | 4096 | 1654 | 256 | 25.78 | 2519.62 | 700.0 | False | 0->0 | ◇cpu-capped | 34.0 | yes |
| 1 | 4 | 1 | cold | litert-lm-gpu | gemma-4-E2B-it-litert-lm | 8192 | 1654 | 256 | 25.9 | 1947.65 | 890.0 | False | 0->0 | ◇cpu-capped | 34.0 | yes |
| 1 | 4 | 2 | warm | litert-lm-gpu | gemma-4-E2B-it-litert-lm | 8192 | 1654 | 256 | 25.18 | 1966.73 | 880.0 | False | 0->0 | ◇cpu-capped | 34.0 | yes |
| 2 | 5 | 1 | cold | litert-lm-gpu | gemma-4-E2B-it-litert-lm | 8192 | 1654 | 256 | 27.02 | 1677.8 | 1020.0 | False | 0->0 | ◇cpu-capped | 39.3 | yes |
| 2 | 5 | 2 | warm | litert-lm-gpu | gemma-4-E2B-it-litert-lm | 8192 | 1654 | 256 | 25.28 | 1970.25 | 880.0 | False | 0->0 | ◇cpu-capped | 39.3 | yes |
| 2 | 6 | 1 | cold | litert-lm-gpu | gemma-4-E2B-it-litert-lm | 4096 | 1654 | 256 | 25.29 | 2490.18 | 700.0 | False | 0->0 | ◇cpu-capped | 34.0 | yes |
| 2 | 6 | 2 | warm | litert-lm-gpu | gemma-4-E2B-it-litert-lm | 4096 | 1654 | 256 | 25.84 | 2500.62 | 700.0 | False | 0->0 | ◇cpu-capped | 34.0 | yes |
| 2 | 7 | 1 | cold | litert-lm-gpu | gemma-4-E2B-it-litert-lm | 2304 | 1654 | 256 | 25.61 | 2917.19 | 610.0 | False | 0->0 | ◇cpu-capped | 34.0 | yes |
| 2 | 7 | 2 | warm | litert-lm-gpu | gemma-4-E2B-it-litert-lm | 2304 | 1654 | 256 | 25.52 | 2854.8 | 620.0 | False | 0->0 | ◇cpu-capped | 34.0 | yes |
| 2 | 8 | 1 | cold-process | llama.cpp | Qwen3-0.6B-GGUF | 4096 |  |  | 107.2 | 182.3 |  | False | 0->0 | cpu-capped | 2.0 | anchor |
| 3 | 9 | 1 | cold-process | llama.cpp | Qwen3-0.6B-GGUF | 4096 |  |  | 90.4 | 313.8 |  | False | 0->0 |  | 0.0 | anchor |
| 3 | 10 | 1 | cold | litert-lm-gpu | gemma-4-E2B-it-litert-lm | 2304 | 1654 | 256 | 25.62 | 2880.4 | 610.0 | False | 0->0 | ◇cpu-capped | 34.0 | yes |
| 3 | 10 | 2 | warm | litert-lm-gpu | gemma-4-E2B-it-litert-lm | 2304 | 1654 | 256 | 25.84 | 2820.21 | 630.0 | False | 0->0 | ◇cpu-capped | 34.0 | yes |
| 3 | 11 | 1 | cold | litert-lm-gpu | gemma-4-E2B-it-litert-lm | 4096 | 1654 | 256 | 25.79 | 2467.8 | 710.0 | False | 0->0 | ◇cpu-capped | 39.3 | yes |
| 3 | 11 | 2 | warm | litert-lm-gpu | gemma-4-E2B-it-litert-lm | 4096 | 1654 | 256 | 28.33 | 2576.42 | 680.0 | False | 0->0 | ◇cpu-capped | 39.3 | yes |
| 3 | 12 | 1 | cold | litert-lm-gpu | gemma-4-E2B-it-litert-lm | 8192 | 1654 | 256 | 25.15 | 1985.64 | 870.0 | False | 0->0 | ◇cpu-capped | 39.3 | yes |
| 3 | 12 | 2 | warm | litert-lm-gpu | gemma-4-E2B-it-litert-lm | 8192 | 1654 | 256 | 25.36 | 1972.46 | 880.0 | False | 0->0 | ◇cpu-capped | 39.3 | yes |
| 4 | 13 | 1 | cold | litert-lm-gpu | gemma-4-E2B-it-litert-lm | 8192 | 1654 | 256 | 24.65 | 1995.24 | 870.0 | False | 0->0 | ◇cpu-capped | 39.3 | yes |
| 4 | 13 | 2 | warm | litert-lm-gpu | gemma-4-E2B-it-litert-lm | 8192 | 1654 | 256 | 25.17 | 1950.16 | 890.0 | False | 0->0 | ◇cpu-capped | 39.3 | yes |
| 4 | 14 | 1 | cold | litert-lm-gpu | gemma-4-E2B-it-litert-lm | 4096 | 1654 | 256 | 26.15 | 2515.58 | 700.0 | False | 0->0 | ◇cpu-capped | 34.0 | yes |
| 4 | 14 | 2 | warm | litert-lm-gpu | gemma-4-E2B-it-litert-lm | 4096 | 1654 | 256 | 25.69 | 2518.35 | 700.0 | False | 0->0 | ◇cpu-capped | 34.0 | yes |
| 4 | 15 | 1 | cold | litert-lm-gpu | gemma-4-E2B-it-litert-lm | 2304 | 1654 | 256 | 25.78 | 2885.87 | 610.0 | False | 0->0 | ◇cpu-capped | 39.3 | yes |
| 4 | 15 | 2 | warm | litert-lm-gpu | gemma-4-E2B-it-litert-lm | 2304 | 1654 | 256 | 25.28 | 2851.49 | 620.0 | False | 0->0 | ◇cpu-capped | 39.3 | yes |
| 4 | 16 | 1 | cold-process | llama.cpp | Qwen3-0.6B-GGUF | 4096 |  |  | 106.0 | 366.9 |  | False | 0->0 |  | 0.0 | anchor |
| 5 | 17 | 1 | cold-process | llama.cpp | Qwen3-0.6B-GGUF | 4096 |  |  | 107.6 | 345.1 |  | False | 0->0 |  | 0.0 | anchor |
| 5 | 18 | 1 | cold | litert-lm-gpu | gemma-4-E2B-it-litert-lm | 2304 | 1654 | 256 | 25.77 | 2903.02 | 610.0 | False | 0->0 | ◇cpu-capped | 34.0 | yes |
| 5 | 18 | 2 | warm | litert-lm-gpu | gemma-4-E2B-it-litert-lm | 2304 | 1654 | 256 | 25.5 | 2863.83 | 620.0 | False | 0->0 | ◇cpu-capped | 34.0 | yes |
| 5 | 19 | 1 | cold | litert-lm-gpu | gemma-4-E2B-it-litert-lm | 4096 | 1654 | 256 | 25.88 | 2524.65 | 690.0 | False | 0->0 | ◇cpu-capped | 39.3 | yes |
| 5 | 19 | 2 | warm | litert-lm-gpu | gemma-4-E2B-it-litert-lm | 4096 | 1654 | 256 | 25.85 | 2503.49 | 700.0 | False | 0->0 | ◇cpu-capped | 39.3 | yes |
| 5 | 20 | 1 | cold | litert-lm-gpu | gemma-4-E2B-it-litert-lm | 8192 | 1654 | 256 | 25.4 | 1994.01 | 870.0 | False | 0->0 | ◇cpu-capped | 39.3 | yes |
| 5 | 20 | 2 | warm | litert-lm-gpu | gemma-4-E2B-it-litert-lm | 8192 | 1654 | 256 | 25.47 | 2005.0 | 860.0 | False | 0->0 | ◇cpu-capped | 39.3 | yes |
| 6 | 21 | 1 | cold | litert-lm-gpu | gemma-4-E2B-it-litert-lm | 8192 | 1654 | 256 | 25.6 | 1973.41 | 880.0 | False | 0->0 | ◇cpu-capped | 34.0 | yes |
| 6 | 21 | 2 | warm | litert-lm-gpu | gemma-4-E2B-it-litert-lm | 8192 | 1654 | 256 | 25.49 | 1982.86 | 870.0 | False | 0->0 | ◇cpu-capped | 34.0 | yes |
| 6 | 22 | 1 | cold | litert-lm-gpu | gemma-4-E2B-it-litert-lm | 4096 | 1654 | 256 | 25.58 | 2510.56 | 700.0 | False | 0->0 | ◇cpu-capped | 34.0 | yes |
| 6 | 22 | 2 | warm | litert-lm-gpu | gemma-4-E2B-it-litert-lm | 4096 | 1654 | 256 | 25.62 | 2512.25 | 700.0 | False | 0->0 | ◇cpu-capped | 34.0 | yes |
| 6 | 23 | 1 | cold | litert-lm-gpu | gemma-4-E2B-it-litert-lm | 2304 | 1654 | 256 | 26.26 | 2877.71 | 610.0 | False | 0->0 | ◇cpu-capped | 39.3 | yes |
| 6 | 23 | 2 | warm | litert-lm-gpu | gemma-4-E2B-it-litert-lm | 2304 | 1654 | 256 | 27.75 | 2832.04 | 620.0 | False | 0->0 | ◇cpu-capped | 39.3 | yes |
| 6 | 24 | 1 | cold-process | llama.cpp | Qwen3-0.6B-GGUF | 4096 |  |  | 90.4 | 306.7 |  | False | 0->0 |  | 0.0 | anchor |
