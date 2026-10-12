# Per-launch conditions

One row per launch (both iterations of a LiteRT launch share it). Battery °C and thermal status from the record; mWakefulness from round_state.jsonl; CPU ceiling = lowest scaling_max_freq / cpuinfo_max_freq MHz the sampler read per policy.

| round | launch | arm | model | allocation | °C start | °C end | thermal start | thermal end | gate timed out | round mWakefulness | screen | launch s | peak RSS MiB | CPU ceiling | protocolFlags |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | llama.cpp | Qwen3-0.6B-GGUF | 4096 | 35.9 | 35.7 | 0 | 0 | False | Dozing | Dozing | 2.6 | 1251.4 | policy0 3628.8/3628.8, policy6 4742.4/4742.4 |  |
| 1 | 2 | litert-lm-gpu | gemma-4-E4B-it-litert-lm | 2304 | 34.9 | 38.0 | 0 | 1 | False | Dozing | Dozing | 48.4 | 917.3 | policy0 1996.8/3628.8, policy6 1977.6/4742.4 | cpu-capped |
| 1 | 3 | litert-lm-gpu | gemma-4-E4B-it-litert-lm | 4096 | 36.8 | 39.4 | 0 | 1 | False | Dozing | Dozing | 48.3 | 1119.4 | policy0 1996.8/3628.8, policy6 1977.6/4742.4 | cpu-capped |
| 1 | 4 | litert-lm-gpu | gemma-4-E4B-it-litert-lm | 8192 | 37.3 | 40.2 | 0 | 1 | False | Dozing | Dozing | 48.3 | 1235.2 | policy0 1996.8/3628.8, policy6 1977.6/4742.4 | cpu-capped |
| 2 | 5 | litert-lm-gpu | gemma-4-E4B-it-litert-lm | 8192 | 37.2 | 40.3 | 0 | 1 | False | Dozing | Dozing | 50.2 | 1072.3 | policy0 1996.8/3628.8, policy6 1977.6/4742.4 | cpu-capped |
| 2 | 6 | litert-lm-gpu | gemma-4-E4B-it-litert-lm | 4096 | 37.2 | 40.8 | 0 | 2 | False | Dozing | Dozing | 47.2 | 1112.1 | policy0 1785.6/3628.8, policy6 1747.2/4742.4 | cpu-capped |
| 2 | 7 | litert-lm-gpu | gemma-4-E4B-it-litert-lm | 2304 | 37.3 | 40.3 | 0 | 2 | False | Dozing | Dozing | 46.3 | 951.8 | policy0 1996.8/3628.8, policy6 1977.6/4742.4 | cpu-capped |
| 2 | 8 | llama.cpp | Qwen3-0.6B-GGUF | 4096 | 37.5 | 37.5 | 0 | 0 | False | Dozing | Dozing | 2.6 | 1215.1 | policy0 3628.8/3628.8, policy6 4608/4742.4 | cpu-capped |
| 3 | 9 | llama.cpp | Qwen3-0.6B-GGUF | 4096 | 37.1 | 37.1 | 0 | 0 | False | Dozing | Dozing | 2.6 | 1252.0 | policy0 3628.8/3628.8, policy6 4742.4/4742.4 |  |
| 3 | 10 | litert-lm-gpu | gemma-4-E4B-it-litert-lm | 2304 | 36.9 | 39.8 | 0 | 1 | False | Dozing | Dozing | 43.5 | 952.8 | policy0 1996.8/3628.8, policy6 1977.6/4742.4 | cpu-capped |
| 3 | 11 | litert-lm-gpu | gemma-4-E4B-it-litert-lm | 4096 | 37.6 | 40.1 | 0 | 2 | False | Dozing | Dozing | 43.1 | 1034.0 | policy0 1996.8/3628.8, policy6 1977.6/4742.4 | cpu-capped |
| 3 | 12 | litert-lm-gpu | gemma-4-E4B-it-litert-lm | 8192 | 37.5 | 40.7 | 0 | 2 | False | Dozing | Dozing | 45.8 | 1005.7 | policy0 1900.8/3628.8, policy6 1862.4/4742.4 | cpu-capped |
| 4 | 13 | litert-lm-gpu | gemma-4-E4B-it-litert-lm | 8192 | 37.4 | 40.7 | 0 | 2 | False | Dozing | Dozing | 44.4 | 1194.4 | policy0 1785.6/3628.8, policy6 1747.2/4742.4 | cpu-capped |
| 4 | 14 | litert-lm-gpu | gemma-4-E4B-it-litert-lm | 4096 | 37.5 | 40.4 | 0 | 2 | False | Dozing | Dozing | 45.0 | 1068.8 | policy0 1785.6/3628.8, policy6 1747.2/4742.4 | cpu-capped |
| 4 | 15 | litert-lm-gpu | gemma-4-E4B-it-litert-lm | 2304 | 37.5 | 41.0 | 0 | 2 | False | Dozing | Dozing | 45.6 | 1013.4 | policy0 1785.6/3628.8, policy6 1747.2/4742.4 | cpu-capped |
| 4 | 16 | llama.cpp | Qwen3-0.6B-GGUF | 4096 | 37.4 | 37.4 | 0 | 0 | False | Dozing | Dozing | 2.6 | 1246.5 | policy0 3628.8/3628.8, policy6 4512/4742.4 | cpu-capped |
| 5 | 17 | llama.cpp | Qwen3-0.6B-GGUF | 4096 | 37.1 | 37.1 | 0 | 0 | False | Dozing | Dozing | 2.6 | 1252.2 | policy0 3628.8/3628.8, policy6 4742.4/4742.4 |  |
| 5 | 18 | litert-lm-gpu | gemma-4-E4B-it-litert-lm | 2304 | 37.0 | 40.1 | 0 | 1 | False | Dozing | Dozing | 44.1 | 857.0 | policy0 1996.8/3628.8, policy6 1977.6/4742.4 | cpu-capped |
| 5 | 19 | litert-lm-gpu | gemma-4-E4B-it-litert-lm | 4096 | 37.0 | 37.0 | 0 | 0 | False | Dozing | Dozing | 1.6 | 4.2 | policy0 3628.8/3628.8, policy6 4742.4/4742.4 | benchmark-iteration-count-0-expected-2,engine-exit-124,text-empty-or-degenerate,text-off-task-screen |
