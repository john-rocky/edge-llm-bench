# Per-cell decode spread

First-ever is separate. n=1 cannot establish repeatability. Min/max rounds identify the extrema, not a causal diagnosis. No rounds are automatically discarded.

| arm | model | file | allocation | regime | n | (max-min)/median % | above 10% | min rounds | max rounds |
|---|---|---|---|---|---|---|---|---|---|
| litert-lm-cpu | litert-community/Qwen3-0.6B | litert-community_Qwen3-0.6B_Qwen3-0.6B_dynamic_wi4b32_afp32.litertlm | 2304 | cold | 6 | 16.010854816824963 | True | [3] | [1] |
| litert-lm-cpu | litert-community/Qwen3-0.6B | litert-community_Qwen3-0.6B_Qwen3-0.6B_dynamic_wi4b32_afp32.litertlm | 2304 | warm | 6 | 9.767092411720506 | False | [4] | [1] |
| litert-lm-cpu | litert-community/Qwen3-0.6B | litert-community_Qwen3-0.6B_Qwen3-0.6B_dynamic_wi4b32_afp32.litertlm | 4096 | cold | 5 | 3.231292517006809 | False | [6] | [2] |
| litert-lm-cpu | litert-community/Qwen3-0.6B | litert-community_Qwen3-0.6B_Qwen3-0.6B_dynamic_wi4b32_afp32.litertlm | 4096 | first-ever | 1 | 0.0 | False | [1] | [1] |
| litert-lm-cpu | litert-community/Qwen3-0.6B | litert-community_Qwen3-0.6B_Qwen3-0.6B_dynamic_wi4b32_afp32.litertlm | 4096 | warm | 6 | 10.71744906997342 | True | [2] | [1] |
| litert-lm-cpu | litert-community/Qwen3-0.6B | litert-community_Qwen3-0.6B_Qwen3-0.6B_dynamic_wi4b32_afp32.litertlm | 8192 | cold | 6 | 3.5623409669211195 | False | [4] | [1] |
| litert-lm-cpu | litert-community/Qwen3-0.6B | litert-community_Qwen3-0.6B_Qwen3-0.6B_dynamic_wi4b32_afp32.litertlm | 8192 | warm | 6 | 12.865497076023393 | True | [6] | [1] |
| llama.cpp | unsloth/Qwen3-0.6B-GGUF | unsloth_Qwen3-0.6B-GGUF_Qwen3-0.6B-Q4_K_M.gguf | 2304 | cold-process | 6 | 2.375296912114014 | False | [6] | [4] |
| llama.cpp | unsloth/Qwen3-0.6B-GGUF | unsloth_Qwen3-0.6B-GGUF_Qwen3-0.6B-Q4_K_M.gguf | 4096 | cold-process | 6 | 2.3980815347721824 | False | [4, 5] | [3] |
| llama.cpp | unsloth/Qwen3-0.6B-GGUF | unsloth_Qwen3-0.6B-GGUF_Qwen3-0.6B-Q4_K_M.gguf | 8192 | cold-process | 6 | 1.9093078758949982 | False | [1, 2, 4] | [5] |
