| runtime | model | task | cold (run1) | warm (med r2-4) | n | thermal |
|---|---|---|---|---|---|---|
| litert-lm | litert-community/Qwen3-0.6B/dynamic_int8 | long-context-1024-gen256 | 46.3 | 46.1 | 4 | fair,nominal |
| litert-lm | litert-community/gemma-4-E4B-it-litert-lm | short-chat | 40.8 | 34.3 | 4 | fair,nominal |
| litert-lm-cpu | litert-community/Qwen3-0.6B/dynamic_wi4b32_afp32 | long-context-1024-gen256 | 51.8 | 50.1 | 4 | fair,nominal |
| mlx-swift | mlx-community/Qwen3-0.6B-4bit | short-chat | 221.8 | 220.9 | 3 | nominal |
