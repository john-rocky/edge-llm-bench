# Per-cell decode spread

First-ever is separate. n=1 cannot establish repeatability. Min/max rounds identify the extrema, not a causal diagnosis. No rounds are automatically discarded.

| arm | model | file | allocation | regime | n | (max-min)/median % | above 10% | min rounds | max rounds |
|---|---|---|---|---|---|---|---|---|---|
| litert-lm-cpu | litert-community/Qwen3-1.7B | litert-community_Qwen3-1.7B_Qwen3_1.7B.litertlm | 2304 | cold | 6 | 2.795031055900617 | False | [1] | [6] |
| litert-lm-cpu | litert-community/Qwen3-1.7B | litert-community_Qwen3-1.7B_Qwen3_1.7B.litertlm | 2304 | warm | 6 | 3.8585209003215373 | False | [2] | [1] |
| litert-lm-cpu | litert-community/Qwen3-1.7B | litert-community_Qwen3-1.7B_Qwen3_1.7B.litertlm | 4096 | cold | 6 | 2.051282051282062 | False | [4] | [6] |
| litert-lm-cpu | litert-community/Qwen3-1.7B | litert-community_Qwen3-1.7B_Qwen3_1.7B.litertlm | 4096 | warm | 6 | 1.6051364365971148 | False | [4] | [1, 5] |
| litert-lm-cpu | litert-community/Qwen3-1.7B | litert-community_Qwen3-1.7B_Qwen3_1.7B.litertlm | 8192 | cold | 6 | 2.6666666666666643 | False | [2] | [4] |
| litert-lm-cpu | litert-community/Qwen3-1.7B | litert-community_Qwen3-1.7B_Qwen3_1.7B.litertlm | 8192 | warm | 6 | 1.9251336898395692 | False | [2] | [4] |
| llama.cpp | unsloth/Qwen3-1.7B-GGUF | unsloth_Qwen3-1.7B-GGUF_Qwen3-1.7B-Q4_K_M.gguf | 2304 | cold-process | 6 | 1.9607843137254832 | False | [1, 2, 3, 5] | [6] |
| llama.cpp | unsloth/Qwen3-1.7B-GGUF | unsloth_Qwen3-1.7B-GGUF_Qwen3-1.7B-Q4_K_M.gguf | 4096 | cold-process | 6 | 3.2362459546925573 | False | [3] | [4] |
| llama.cpp | unsloth/Qwen3-1.7B-GGUF | unsloth_Qwen3-1.7B-GGUF_Qwen3-1.7B-Q4_K_M.gguf | 8192 | cold-process | 6 | 2.580645161290325 | False | [6] | [1] |
