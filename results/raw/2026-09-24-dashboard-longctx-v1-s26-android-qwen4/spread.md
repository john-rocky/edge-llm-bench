# Per-cell decode spread

First-ever is separate. n=1 cannot establish repeatability. Min/max rounds identify the extrema, not a causal diagnosis. No rounds are automatically discarded.

| arm | model | file | allocation | regime | n | (max-min)/median % | above 10% | min rounds | max rounds |
|---|---|---|---|---|---|---|---|---|---|
| llama.cpp | unsloth/Qwen3-4B-GGUF | unsloth_Qwen3-4B-GGUF_Qwen3-4B-Q4_K_M.gguf | 2304 | cold-process | 5 | 5.333333333333326 | False | [4, 5] | [2] |
| llama.cpp | unsloth/Qwen3-4B-GGUF | unsloth_Qwen3-4B-GGUF_Qwen3-4B-Q4_K_M.gguf | 4096 | cold-process | 5 | 3.9999999999999973 | False | [5] | [1, 2, 3] |
| llama.cpp | unsloth/Qwen3-4B-GGUF | unsloth_Qwen3-4B-GGUF_Qwen3-4B-Q4_K_M.gguf | 8192 | cold-process | 5 | 4.054054054054052 | False | [5] | [1, 2] |
