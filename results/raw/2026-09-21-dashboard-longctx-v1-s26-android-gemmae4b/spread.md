# Per-cell decode spread

First-ever is separate. n=1 cannot establish repeatability. Min/max rounds identify the extrema, not a causal diagnosis. No rounds are automatically discarded.

| arm | model | file | allocation | regime | n | (max-min)/median % | above 10% | min rounds | max rounds |
|---|---|---|---|---|---|---|---|---|---|
| litert-lm-cpu | litert-community/gemma-4-E4B-it-litert-lm | litert-community_gemma-4-E4B-it-litert-lm_gemma-4-E4B-it.litertlm | 2304 | cold | 4 | 6.453875833041038 | False | [5] | [4] |
| litert-lm-cpu | litert-community/gemma-4-E4B-it-litert-lm | litert-community_gemma-4-E4B-it-litert-lm_gemma-4-E4B-it.litertlm | 2304 | first-ever | 1 | 0.0 | False | [1] | [1] |
| litert-lm-cpu | litert-community/gemma-4-E4B-it-litert-lm | litert-community_gemma-4-E4B-it-litert-lm_gemma-4-E4B-it.litertlm | 2304 | warm | 5 | 3.4411562284927735 | False | [5] | [1] |
| litert-lm-cpu | litert-community/gemma-4-E4B-it-litert-lm | litert-community_gemma-4-E4B-it-litert-lm_gemma-4-E4B-it.litertlm | 4096 | cold | 4 | 5.626810095159286 | False | [4] | [5] |
| litert-lm-cpu | litert-community/gemma-4-E4B-it-litert-lm | litert-community_gemma-4-E4B-it-litert-lm_gemma-4-E4B-it.litertlm | 4096 | first-ever | 1 | 0.0 | False | [1] | [1] |
| litert-lm-cpu | litert-community/gemma-4-E4B-it-litert-lm | litert-community_gemma-4-E4B-it-litert-lm_gemma-4-E4B-it.litertlm | 4096 | warm | 5 | 2.0077220077220064 | False | [4] | [1] |
| litert-lm-gpu | litert-community/gemma-4-E4B-it-litert-lm | litert-community_gemma-4-E4B-it-litert-lm_gemma-4-E4B-it.litertlm | 2304 | cold | 5 | 11.340206185567009 | True | [1] | [5] |
| litert-lm-gpu | litert-community/gemma-4-E4B-it-litert-lm | litert-community_gemma-4-E4B-it-litert-lm_gemma-4-E4B-it.litertlm | 2304 | warm | 5 | 19.085487077534797 | True | [3] | [5] |
| litert-lm-gpu | litert-community/gemma-4-E4B-it-litert-lm | litert-community_gemma-4-E4B-it-litert-lm_gemma-4-E4B-it.litertlm | 4096 | cold | 4 | 5.242203052422025 | False | [5] | [2] |
| litert-lm-gpu | litert-community/gemma-4-E4B-it-litert-lm | litert-community_gemma-4-E4B-it-litert-lm_gemma-4-E4B-it.litertlm | 4096 | first-ever | 1 | 0.0 | False | [1] | [1] |
| litert-lm-gpu | litert-community/gemma-4-E4B-it-litert-lm | litert-community_gemma-4-E4B-it-litert-lm_gemma-4-E4B-it.litertlm | 4096 | warm | 5 | 51.97313182199833 | True | [3] | [1] |
| litert-lm-gpu | litert-community/gemma-4-E4B-it-litert-lm | litert-community_gemma-4-E4B-it-litert-lm_gemma-4-E4B-it.litertlm | 8192 | cold | 4 | 4.248366013071898 | False | [5] | [2] |
| litert-lm-gpu | litert-community/gemma-4-E4B-it-litert-lm | litert-community_gemma-4-E4B-it-litert-lm_gemma-4-E4B-it.litertlm | 8192 | first-ever | 1 | 0.0 | False | [1] | [1] |
| litert-lm-gpu | litert-community/gemma-4-E4B-it-litert-lm | litert-community_gemma-4-E4B-it-litert-lm_gemma-4-E4B-it.litertlm | 8192 | warm | 5 | 10.644067796610171 | True | [5] | [3] |
| llama.cpp | unsloth/gemma-4-E4B-it-GGUF | unsloth_gemma-4-E4B-it-GGUF_gemma-4-E4B-it-Q4_K_M.gguf | 2304 | cold-process | 5 | 22.89156626506024 | True | [5] | [2, 3] |
| llama.cpp | unsloth/gemma-4-E4B-it-GGUF | unsloth_gemma-4-E4B-it-GGUF_gemma-4-E4B-it-Q4_K_M.gguf | 4096 | cold-process | 5 | 9.523809523809522 | False | [4] | [3] |
| llama.cpp | unsloth/gemma-4-E4B-it-GGUF | unsloth_gemma-4-E4B-it-GGUF_gemma-4-E4B-it-Q4_K_M.gguf | 8192 | cold-process | 5 | 1.1904761904761862 | False | [3, 4] | [1, 2, 5] |
