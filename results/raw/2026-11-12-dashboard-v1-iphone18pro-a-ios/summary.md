| runtime | model | task | cold (run1) | warm (med r2-4) | n | thermal |
|---|---|---|---|---|---|---|
| core-ai | core-ai/qwen3-0.6b-4bit-gpu | short-chat | 244.5 | 237.5 | 4 | nominal |
| core-ai | core-ai/qwen3-1.7b-gpu | short-chat | 97.7 | 97.6 | 4 | nominal |
| litert-lm | litert-community/Qwen3-0.6B/dynamic_int8 | short-chat | 46.5 | 46.6 | 4 | nominal |
| litert-lm | litert-community/Qwen3-1.7B | long-context-1024-gen256 | 72.6 | 72.3 | 4 | nominal |
| litert-lm | litert-community/Qwen3-1.7B | short-chat | 81.5 | 81.4 | 4 | nominal |
| litert-lm-cpu | litert-community/Qwen3-0.6B/dynamic_wi4b32_afp32 | short-chat | 87.3 | 88.6 | 4 | nominal |
| llama.cpp | unsloth/Qwen3-0.6B-GGUF/Q4_K_M | long-context-1024-gen256 | 147.1 | 147.2 | 4 | nominal |
| llama.cpp | unsloth/Qwen3-0.6B-GGUF/Q4_K_M | short-chat | 187.7 | 182.5 | 4 | nominal |
| llama.cpp | unsloth/Qwen3-1.7B-GGUF/Q4_K_M | long-context-1024-gen256 | 64.0 | 63.8 | 4 | nominal |
| llama.cpp | unsloth/Qwen3-1.7B-GGUF/Q4_K_M | short-chat | 82.0 | 71.8 | 4 | nominal |
| llama.cpp | unsloth/gemma-4-E4B-it-GGUF/Q4_K_M | short-chat | 29.2 | 29.3 | 4 | nominal |
| mlx-swift | mlx-community/Qwen3-0.6B-4bit | long-context-1024-gen256 | 173.9 | 174.2 | 4 | nominal |
| mlx-swift | mlx-community/Qwen3-0.6B-4bit | short-chat | 223.6 | 221.7 | 3 | nominal |
| mlx-swift | mlx-community/Qwen3-1.7B-4bit | long-context-1024-gen256 | 85.9 | 86.7 | 4 | nominal |
| mlx-swift | mlx-community/Qwen3-1.7B-4bit | short-chat | 100.9 | 101.3 | 4 | nominal |
| mlx-swift | mlx-community/gemma-4-e4b-it-4bit | short-chat | 37.8 | 38.0 | 4 | nominal |
