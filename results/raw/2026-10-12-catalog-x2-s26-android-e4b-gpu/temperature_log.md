# Per-launch conditions

One row per launch (both iterations of a LiteRT launch share it). Battery °C and thermal status from the record; mWakefulness from round_state.jsonl; CPU ceiling = lowest scaling_max_freq / cpuinfo_max_freq MHz the sampler read per policy.

| round | launch | arm | model | allocation | °C start | °C end | thermal start | thermal end | gate timed out | round mWakefulness | screen | launch s | peak RSS MiB | CPU ceiling | protocolFlags |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | llama.cpp | Qwen3-0.6B-GGUF | 4096 | 35.7 | 35.5 | 0 | 0 | False | Dozing | Dozing | 2.6 | 1251.4 | policy0 3628.8/3628.8, policy6 4742.4/4742.4 |  |
| 1 | 2 | litert-lm-gpu | gemma-4-E4B-it-litert-lm | 2304 | 35.5 | 38.7 | 0 | 1 | False | Dozing | Dozing | 42.8 | 923.6 | policy0 1996.8/3628.8, policy6 1977.6/4742.4 | cpu-capped |
| 1 | 3 | litert-lm-gpu | gemma-4-E4B-it-litert-lm | 4096 | 36.7 | 39.9 | 0 | 1 | False | Dozing | Dozing | 49.7 | 744.0 | policy0 1996.8/3628.8, policy6 1977.6/4742.4 | cpu-capped |
| 1 | 4 | litert-lm-gpu | gemma-4-E4B-it-litert-lm | 8192 | 37.5 | 40.7 | 0 | 2 | False | Dozing | Dozing | 47.9 | 1194.4 | policy0 1785.6/3628.8, policy6 1747.2/4742.4 | cpu-capped |
| 2 | 5 | litert-lm-gpu | gemma-4-E4B-it-litert-lm | 8192 | 37.2 | 40.0 | 0 | 1 | False | Dozing | Dozing | 46.7 | 986.9 | policy0 1996.8/3628.8, policy6 1977.6/4742.4 | cpu-capped |
| 2 | 6 | litert-lm-gpu | gemma-4-E4B-it-litert-lm | 4096 | 37.1 | 40.3 | 0 | 1 | False | Dozing | Dozing | 47.4 | 1018.9 | policy0 1996.8/3628.8, policy6 1977.6/4742.4 | cpu-capped |
| 2 | 7 | litert-lm-gpu | gemma-4-E4B-it-litert-lm | 2304 | 37.4 | 40.9 | 0 | 2 | False | Dozing | Dozing | 50.1 | 923.4 | policy0 1785.6/3628.8, policy6 1747.2/4742.4 | cpu-capped |
| 2 | 8 | llama.cpp | Qwen3-0.6B-GGUF | 4096 | 37.4 | 37.4 | 0 | 0 | False | Dozing | Dozing | 2.6 | 1251.6 | policy0 3628.8/3628.8, policy6 4608/4742.4 | cpu-capped |
| 3 | 9 | llama.cpp | Qwen3-0.6B-GGUF | 4096 | 37.1 | 37.1 | 0 | 0 | False | Dozing | Dozing | 2.6 | 1251.8 | policy0 3628.8/3628.8, policy6 4396.8/4742.4 | cpu-capped |
| 3 | 10 | litert-lm-gpu | gemma-4-E4B-it-litert-lm | 2304 | 37.0 | 40.4 | 0 | 1 | False | Dozing | Dozing | 43.1 | 999.7 | policy0 1996.8/3628.8, policy6 1977.6/4742.4 | cpu-capped |
| 3 | 11 | litert-lm-gpu | gemma-4-E4B-it-litert-lm | 4096 | 37.0 | 40.2 | 0 | 2 | False | Dozing | Dozing | 47.3 | 954.7 | policy0 1785.6/3628.8, policy6 1747.2/4742.4 | cpu-capped |
| 3 | 12 | litert-lm-gpu | gemma-4-E4B-it-litert-lm | 8192 | 37.5 | 41.1 | 0 | 2 | False | Dozing | Dozing | 54.2 | 1081.6 | policy0 1785.6/3628.8, policy6 1747.2/4742.4 | cpu-capped |
| 4 | 13 | litert-lm-gpu | gemma-4-E4B-it-litert-lm | 8192 | 37.5 | 40.7 | 0 | 2 | False | Dozing | Dozing | 49.5 | 961.4 | policy0 1785.6/3628.8, policy6 1747.2/4742.4 | cpu-capped |
| 4 | 14 | litert-lm-gpu | gemma-4-E4B-it-litert-lm | 4096 | 37.2 | 40.6 | 0 | 1 | False | Dozing | Dozing | 44.0 | 876.0 | policy0 1996.8/3628.8, policy6 1977.6/4742.4 | cpu-capped |
| 4 | 15 | litert-lm-gpu | gemma-4-E4B-it-litert-lm | 2304 | 37.3 | 40.4 | 0 | 1 | False | Dozing | Dozing | 44.2 | 1006.4 | policy0 1996.8/3628.8, policy6 1977.6/4742.4 | cpu-capped |
| 4 | 16 | llama.cpp | Qwen3-0.6B-GGUF | 4096 | 37.4 | 37.4 | 0 | 0 | False | Dozing | Dozing | 2.6 | 1251.7 | policy0 3628.8/3628.8, policy6 4646.4/4742.4 | cpu-capped |
| 5 | 17 | llama.cpp | Qwen3-0.6B-GGUF | 4096 | 37.1 | 37.1 | 0 | 0 | False | Dozing | Dozing | 2.6 | 1252.0 | policy0 3628.8/3628.8, policy6 4646.4/4742.4 | cpu-capped |
| 5 | 18 | litert-lm-gpu | gemma-4-E4B-it-litert-lm | 2304 | 37.0 | 40.0 | 0 | 1 | False | Dozing | Dozing | 43.7 | 917.8 | policy0 1996.8/3628.8, policy6 1977.6/4742.4 | cpu-capped |
