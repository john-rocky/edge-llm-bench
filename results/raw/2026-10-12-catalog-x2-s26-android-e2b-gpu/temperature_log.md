# Per-launch conditions

One row per launch (both iterations of a LiteRT launch share it). Battery °C and thermal status from the record; mWakefulness from round_state.jsonl; CPU ceiling = lowest scaling_max_freq / cpuinfo_max_freq MHz the sampler read per policy.

| round | launch | arm | model | allocation | °C start | °C end | thermal start | thermal end | gate timed out | round mWakefulness | screen | launch s | peak RSS MiB | CPU ceiling | protocolFlags |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | llama.cpp | Qwen3-0.6B-GGUF | 4096 | 35.4 | 35.4 | 0 | 0 | False | Dozing | Dozing | 2.6 | 1252.0 | policy0 3628.8/3628.8, policy6 4742.4/4742.4 |  |
| 1 | 2 | litert-lm-gpu | gemma-4-E2B-it-litert-lm | 2304 | 35.1 | 36.1 | 0 | 0 | False | Dozing | Dozing | 26.7 | 846.2 | policy0 2899.2/3628.8, policy6 2880/4742.4 | cpu-capped |
| 1 | 3 | litert-lm-gpu | gemma-4-E2B-it-litert-lm | 4096 | 35.7 | 36.3 | 0 | 0 | False | Dozing | Dozing | 28.2 | 855.9 | policy0 3187.2/3628.8, policy6 3129.6/4742.4 | cpu-capped |
| 1 | 4 | litert-lm-gpu | gemma-4-E2B-it-litert-lm | 8192 | 35.9 | 36.1 | 0 | 0 | False | Dozing | Dozing | 24.6 | 868.8 | policy0 3187.2/3628.8, policy6 3129.6/4742.4 | cpu-capped |
| 2 | 5 | litert-lm-gpu | gemma-4-E2B-it-litert-lm | 8192 | 35.7 | 36.3 | 0 | 0 | False | Dozing | Dozing | 28.1 | 879.9 | policy0 2899.2/3628.8, policy6 2880/4742.4 | cpu-capped |
| 2 | 6 | litert-lm-gpu | gemma-4-E2B-it-litert-lm | 4096 | 35.8 | 36.3 | 0 | 0 | False | Dozing | Dozing | 28.2 | 830.0 | policy0 3187.2/3628.8, policy6 3129.6/4742.4 | cpu-capped |
| 2 | 7 | litert-lm-gpu | gemma-4-E2B-it-litert-lm | 2304 | 36.1 | 36.9 | 0 | 0 | False | Dozing | Dozing | 28.2 | 812.7 | policy0 3187.2/3628.8, policy6 3129.6/4742.4 | cpu-capped |
| 2 | 8 | llama.cpp | Qwen3-0.6B-GGUF | 4096 | 36.0 | 36.0 | 0 | 0 | False | Dozing | Dozing | 2.6 | 1251.6 | policy0 3628.8/3628.8, policy6 4646.4/4742.4 | cpu-capped |
| 3 | 9 | llama.cpp | Qwen3-0.6B-GGUF | 4096 | 35.9 | 35.7 | 0 | 0 | False | Dozing | Dozing | 3.1 | 1251.9 | policy0 3628.8/3628.8, policy6 4742.4/4742.4 |  |
| 3 | 10 | litert-lm-gpu | gemma-4-E2B-it-litert-lm | 2304 | 35.8 | 36.4 | 0 | 0 | False | Dozing | Dozing | 24.1 | 786.3 | policy0 3187.2/3628.8, policy6 3129.6/4742.4 | cpu-capped |
| 3 | 11 | litert-lm-gpu | gemma-4-E2B-it-litert-lm | 4096 | 36.1 | 37.0 | 0 | 0 | False | Dozing | Dozing | 23.4 | 807.7 | policy0 2899.2/3628.8, policy6 2880/4742.4 | cpu-capped |
| 3 | 12 | litert-lm-gpu | gemma-4-E2B-it-litert-lm | 8192 | 36.0 | 36.5 | 0 | 0 | False | Dozing | Dozing | 28.7 | 859.7 | policy0 2899.2/3628.8, policy6 2880/4742.4 | cpu-capped |
| 4 | 13 | litert-lm-gpu | gemma-4-E2B-it-litert-lm | 8192 | 35.8 | 36.5 | 0 | 0 | False | Dozing | Dozing | 29.2 | 870.2 | policy0 2899.2/3628.8, policy6 2880/4742.4 | cpu-capped |
| 4 | 14 | litert-lm-gpu | gemma-4-E2B-it-litert-lm | 4096 | 36.1 | 36.6 | 0 | 0 | False | Dozing | Dozing | 27.8 | 835.7 | policy0 3187.2/3628.8, policy6 3129.6/4742.4 | cpu-capped |
| 4 | 15 | litert-lm-gpu | gemma-4-E2B-it-litert-lm | 2304 | 36.1 | 36.8 | 0 | 0 | False | Dozing | Dozing | 28.2 | 816.0 | policy0 2899.2/3628.8, policy6 2880/4742.4 | cpu-capped |
| 4 | 16 | llama.cpp | Qwen3-0.6B-GGUF | 4096 | 36.1 | 36.1 | 0 | 0 | False | Dozing | Dozing | 2.7 | 1251.4 | policy0 3628.8/3628.8, policy6 4742.4/4742.4 |  |
| 5 | 17 | llama.cpp | Qwen3-0.6B-GGUF | 4096 | 35.9 | 35.8 | 0 | 0 | False | Dozing | Dozing | 2.6 | 1251.7 | policy0 3628.8/3628.8, policy6 4742.4/4742.4 |  |
| 5 | 18 | litert-lm-gpu | gemma-4-E2B-it-litert-lm | 2304 | 35.8 | 36.9 | 0 | 0 | False | Dozing | Dozing | 27.7 | 785.9 | policy0 3187.2/3628.8, policy6 3129.6/4742.4 | cpu-capped |
| 5 | 19 | litert-lm-gpu | gemma-4-E2B-it-litert-lm | 4096 | 36.0 | 36.5 | 0 | 0 | False | Dozing | Dozing | 28.2 | 795.6 | policy0 2899.2/3628.8, policy6 2880/4742.4 | cpu-capped |
| 5 | 20 | litert-lm-gpu | gemma-4-E2B-it-litert-lm | 8192 | 36.1 | 36.6 | 0 | 0 | False | Dozing | Dozing | 28.7 | 843.8 | policy0 2899.2/3628.8, policy6 2880/4742.4 | cpu-capped |
| 6 | 21 | litert-lm-gpu | gemma-4-E2B-it-litert-lm | 8192 | 36.0 | 36.8 | 0 | 0 | False | Dozing | Dozing | 24.6 | 814.7 | policy0 3187.2/3628.8, policy6 3129.6/4742.4 | cpu-capped |
| 6 | 22 | litert-lm-gpu | gemma-4-E2B-it-litert-lm | 4096 | 35.9 | 36.4 | 0 | 0 | False | Dozing | Dozing | 24.2 | 765.3 | policy0 3187.2/3628.8, policy6 3129.6/4742.4 | cpu-capped |
| 6 | 23 | litert-lm-gpu | gemma-4-E2B-it-litert-lm | 2304 | 36.0 | 36.7 | 0 | 0 | False | Dozing | Dozing | 27.1 | 775.0 | policy0 2899.2/3628.8, policy6 2880/4742.4 | cpu-capped |
| 6 | 24 | llama.cpp | Qwen3-0.6B-GGUF | 4096 | 36.3 | 36.3 | 0 | 0 | False | Dozing | Dozing | 3.1 | 1249.6 | policy0 3628.8/3628.8, policy6 4742.4/4742.4 |  |
