# Per-cell decode spread

First-ever is separate. n=1 cannot establish repeatability. Min/max rounds identify the extrema, not a causal diagnosis. No rounds are automatically discarded.

| arm | model | file | allocation | regime | n | (max-min)/median % | above 10% | min rounds | max rounds |
|---|---|---|---|---|---|---|---|---|---|
| litert-lm-cpu | litert-community/gemma-4-E2B-it-litert-lm | litert-community_gemma-4-E2B-it-litert-lm_gemma-4-E2B-it.litertlm | 2304 | cold | 4 | 14.08019589837772 | True | [3] | [4] |
| litert-lm-cpu | litert-community/gemma-4-E2B-it-litert-lm | litert-community_gemma-4-E2B-it-litert-lm_gemma-4-E2B-it.litertlm | 2304 | first-ever | 1 | 0.0 | False | [1] | [1] |
| litert-lm-cpu | litert-community/gemma-4-E2B-it-litert-lm | litert-community_gemma-4-E2B-it-litert-lm_gemma-4-E2B-it.litertlm | 2304 | warm | 5 | 18.53537443111295 | True | [3] | [1] |
| litert-lm-cpu | litert-community/gemma-4-E2B-it-litert-lm | litert-community_gemma-4-E2B-it-litert-lm_gemma-4-E2B-it.litertlm | 4096 | cold | 4 | 5.189775367931835 | False | [5] | [4] |
| litert-lm-cpu | litert-community/gemma-4-E2B-it-litert-lm | litert-community_gemma-4-E2B-it-litert-lm_gemma-4-E2B-it.litertlm | 4096 | first-ever | 1 | 0.0 | False | [1] | [1] |
| litert-lm-cpu | litert-community/gemma-4-E2B-it-litert-lm | litert-community_gemma-4-E2B-it-litert-lm_gemma-4-E2B-it.litertlm | 4096 | warm | 5 | 12.885154061624657 | True | [2] | [1] |
| litert-lm-cpu | litert-community/gemma-4-E2B-it-litert-lm | litert-community_gemma-4-E2B-it-litert-lm_gemma-4-E2B-it.litertlm | 8192 | cold | 4 | 5.652680652680646 | False | [4] | [5] |
| litert-lm-cpu | litert-community/gemma-4-E2B-it-litert-lm | litert-community_gemma-4-E2B-it-litert-lm_gemma-4-E2B-it.litertlm | 8192 | first-ever | 1 | 0.0 | False | [1] | [1] |
| litert-lm-cpu | litert-community/gemma-4-E2B-it-litert-lm | litert-community_gemma-4-E2B-it-litert-lm_gemma-4-E2B-it.litertlm | 8192 | warm | 5 | 11.256218905472652 | True | [4] | [1] |
| litert-lm-gpu | litert-community/gemma-4-E2B-it-litert-lm | litert-community_gemma-4-E2B-it-litert-lm_gemma-4-E2B-it.litertlm | 2304 | cold | 5 | 2.0558572536850175 | False | [5] | [3] |
| litert-lm-gpu | litert-community/gemma-4-E2B-it-litert-lm | litert-community_gemma-4-E2B-it-litert-lm_gemma-4-E2B-it.litertlm | 2304 | warm | 5 | 27.9293123319247 | True | [5] | [4] |
| litert-lm-gpu | litert-community/gemma-4-E2B-it-litert-lm | litert-community_gemma-4-E2B-it-litert-lm_gemma-4-E2B-it.litertlm | 4096 | cold | 4 | 5.7736720554272525 | False | [4] | [5] |
| litert-lm-gpu | litert-community/gemma-4-E2B-it-litert-lm | litert-community_gemma-4-E2B-it-litert-lm_gemma-4-E2B-it.litertlm | 4096 | first-ever | 1 | 0.0 | False | [1] | [1] |
| litert-lm-gpu | litert-community/gemma-4-E2B-it-litert-lm | litert-community_gemma-4-E2B-it-litert-lm_gemma-4-E2B-it.litertlm | 4096 | warm | 5 | 38.585703305149885 | True | [4] | [1] |
| litert-lm-gpu | litert-community/gemma-4-E2B-it-litert-lm | litert-community_gemma-4-E2B-it-litert-lm_gemma-4-E2B-it.litertlm | 8192 | cold | 4 | 18.439201451905635 | True | [3] | [2] |
| litert-lm-gpu | litert-community/gemma-4-E2B-it-litert-lm | litert-community_gemma-4-E2B-it-litert-lm_gemma-4-E2B-it.litertlm | 8192 | first-ever | 1 | 0.0 | False | [1] | [1] |
| litert-lm-gpu | litert-community/gemma-4-E2B-it-litert-lm | litert-community_gemma-4-E2B-it-litert-lm_gemma-4-E2B-it.litertlm | 8192 | warm | 5 | 4.164997997597113 | False | [5] | [1] |
| llama.cpp | unsloth/gemma-4-E2B-it-GGUF | unsloth_gemma-4-E2B-it-GGUF_gemma-4-E2B-it-Q4_K_M.gguf | 2304 | cold-process | 5 | 16.197183098591555 | True | [1] | [2, 4] |
| llama.cpp | unsloth/gemma-4-E2B-it-GGUF | unsloth_gemma-4-E2B-it-GGUF_gemma-4-E2B-it-Q4_K_M.gguf | 4096 | cold-process | 5 | 5.594405594405587 | False | [2] | [1] |
| llama.cpp | unsloth/gemma-4-E2B-it-GGUF | unsloth_gemma-4-E2B-it-GGUF_gemma-4-E2B-it-Q4_K_M.gguf | 8192 | cold-process | 5 | 0.694444444444442 | False | [4] | [1, 2, 3, 5] |
