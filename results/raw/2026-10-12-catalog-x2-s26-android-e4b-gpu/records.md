# Per-record table

Every stored record, launch order. pooled = what longctx_ab_report.py and spread.md read (◇ = a CPU-cap-only flag on an accelerator arm, kept and marked).

| round | launch | iteration | regime | arm | model | allocation | prompt tok | output tok | decode tok/s | prefill tok/s | TTFT ms | first-ever | thermal | flags | CPU ceiling fall % | pooled |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | 1 | cold-process | llama.cpp | Qwen3-0.6B-GGUF | 4096 |  |  | 106.2 | 354.4 |  | False | 0->0 |  | 0.0 | anchor |
| 1 | 2 | 1 | cold | litert-lm-gpu | gemma-4-E4B-it-litert-lm | 2304 | 1654 | 256 | 14.97 | 1087.46 | 1590.0 | False | 0->1 | ◇cpu-capped | 58.3 | yes |
| 1 | 2 | 2 | warm | litert-lm-gpu | gemma-4-E4B-it-litert-lm | 2304 | 1654 | 256 | 15.42 | 1073.53 | 1610.0 | False | 0->1 | ◇cpu-capped | 58.3 | yes |
| 1 | 3 | 1 | cold | litert-lm-gpu | gemma-4-E4B-it-litert-lm | 4096 | 1654 | 256 | 14.55 | 854.39 | 2000.0 | True | 0->1 | cpu-capped | 58.3 | no |
| 1 | 3 | 2 | warm | litert-lm-gpu | gemma-4-E4B-it-litert-lm | 4096 | 1654 | 256 | 14.71 | 1018.51 | 1690.0 | False | 0->1 | ◇cpu-capped | 58.3 | yes |
| 1 | 4 | 1 | cold | litert-lm-gpu | gemma-4-E4B-it-litert-lm | 8192 | 1654 | 256 | 14.19 | 871.26 | 1970.0 | False | 0->2 | ◇cpu-capped | 63.2 | yes |
| 1 | 4 | 2 | warm | litert-lm-gpu | gemma-4-E4B-it-litert-lm | 8192 | 1654 | 256 | 13.23 | 874.25 | 1970.0 | False | 0->2 | ◇cpu-capped | 63.2 | yes |
| 2 | 5 | 1 | cold | litert-lm-gpu | gemma-4-E4B-it-litert-lm | 8192 | 1654 | 256 | 14.31 | 745.7 | 2290.0 | False | 0->1 | ◇cpu-capped | 58.3 | yes |
| 2 | 5 | 2 | warm | litert-lm-gpu | gemma-4-E4B-it-litert-lm | 8192 | 1654 | 256 | 14.45 | 853.86 | 2009.9999999999998 | False | 0->1 | ◇cpu-capped | 58.3 | yes |
| 2 | 6 | 1 | cold | litert-lm-gpu | gemma-4-E4B-it-litert-lm | 4096 | 1654 | 256 | 15.11 | 1022.09 | 1680.0 | False | 0->1 | ◇cpu-capped | 58.3 | yes |
| 2 | 6 | 2 | warm | litert-lm-gpu | gemma-4-E4B-it-litert-lm | 4096 | 1654 | 256 | 15.18 | 1016.27 | 1690.0 | False | 0->1 | ◇cpu-capped | 58.3 | yes |
| 2 | 7 | 1 | cold | litert-lm-gpu | gemma-4-E4B-it-litert-lm | 2304 | 1654 | 256 | 15.04 | 978.12 | 1760.0 | False | 0->2 | ◇cpu-capped | 63.2 | yes |
| 2 | 7 | 2 | warm | litert-lm-gpu | gemma-4-E4B-it-litert-lm | 2304 | 1654 | 256 | 13.45 | 1090.8 | 1590.0 | False | 0->2 | ◇cpu-capped | 63.2 | yes |
| 2 | 8 | 1 | cold-process | llama.cpp | Qwen3-0.6B-GGUF | 4096 |  |  | 103.9 | 210.8 |  | False | 0->0 | cpu-capped | 2.8 | anchor |
| 3 | 9 | 1 | cold-process | llama.cpp | Qwen3-0.6B-GGUF | 4096 |  |  | 104.9 | 294.3 |  | False | 0->0 | cpu-capped | 7.3 | anchor |
| 3 | 10 | 1 | cold | litert-lm-gpu | gemma-4-E4B-it-litert-lm | 2304 | 1654 | 256 | 15.61 | 1087.55 | 1580.0 | False | 0->1 | ◇cpu-capped | 58.3 | yes |
| 3 | 10 | 2 | warm | litert-lm-gpu | gemma-4-E4B-it-litert-lm | 2304 | 1654 | 256 | 14.86 | 1047.27 | 1650.0 | False | 0->1 | ◇cpu-capped | 58.3 | yes |
| 3 | 11 | 1 | cold | litert-lm-gpu | gemma-4-E4B-it-litert-lm | 4096 | 1654 | 256 | 14.7 | 1017.45 | 1690.0 | False | 0->2 | ◇cpu-capped | 63.2 | yes |
| 3 | 11 | 2 | warm | litert-lm-gpu | gemma-4-E4B-it-litert-lm | 4096 | 1654 | 256 | 14.86 | 1008.48 | 1710.0 | False | 0->2 | ◇cpu-capped | 63.2 | yes |
| 3 | 12 | 1 | cold | litert-lm-gpu | gemma-4-E4B-it-litert-lm | 8192 | 1654 | 256 | 14.14 | 883.73 | 1940.0 | False | 0->2 | ◇cpu-capped | 63.2 | yes |
| 3 | 12 | 2 | warm | litert-lm-gpu | gemma-4-E4B-it-litert-lm | 8192 | 1654 | 256 | 11.01 | 874.31 | 1980.0 | False | 0->2 | ◇cpu-capped | 63.2 | yes |
| 4 | 13 | 1 | cold | litert-lm-gpu | gemma-4-E4B-it-litert-lm | 8192 | 1654 | 256 | 14.7 | 758.59 | 2250.0 | False | 0->2 | ◇cpu-capped | 63.2 | yes |
| 4 | 13 | 2 | warm | litert-lm-gpu | gemma-4-E4B-it-litert-lm | 8192 | 1654 | 256 | 12.61 | 863.52 | 1990.0 | False | 0->2 | ◇cpu-capped | 63.2 | yes |
| 4 | 14 | 1 | cold | litert-lm-gpu | gemma-4-E4B-it-litert-lm | 4096 | 1654 | 256 | 15.11 | 900.97 | 1900.0 | False | 0->1 | ◇cpu-capped | 58.3 | yes |
| 4 | 14 | 2 | warm | litert-lm-gpu | gemma-4-E4B-it-litert-lm | 4096 | 1654 | 256 | 15.05 | 1016.69 | 1690.0 | False | 0->1 | ◇cpu-capped | 58.3 | yes |
| 4 | 15 | 1 | cold | litert-lm-gpu | gemma-4-E4B-it-litert-lm | 2304 | 1654 | 256 | 14.61 | 1096.58 | 1580.0 | False | 0->1 | ◇cpu-capped | 58.3 | yes |
| 4 | 15 | 2 | warm | litert-lm-gpu | gemma-4-E4B-it-litert-lm | 2304 | 1654 | 256 | 14.93 | 1079.14 | 1600.0 | False | 0->1 | ◇cpu-capped | 58.3 | yes |
| 4 | 16 | 1 | cold-process | llama.cpp | Qwen3-0.6B-GGUF | 4096 |  |  | 109.5 | 291.0 |  | False | 0->0 | cpu-capped | 2.0 | anchor |
| 5 | 17 | 1 | cold-process | llama.cpp | Qwen3-0.6B-GGUF | 4096 |  |  | 107.5 | 332.4 |  | False | 0->0 | cpu-capped | 2.0 | anchor |
| 5 | 18 | 1 | cold | litert-lm-gpu | gemma-4-E4B-it-litert-lm | 2304 | 1654 | 256 | 14.81 | 1107.69 | 1560.0 | False | 0->1 | ◇cpu-capped | 58.3 | yes |
| 5 | 18 | 2 | warm | litert-lm-gpu | gemma-4-E4B-it-litert-lm | 2304 | 1654 | 256 | 14.97 | 1080.76 | 1600.0 | False | 0->1 | ◇cpu-capped | 58.3 | yes |
