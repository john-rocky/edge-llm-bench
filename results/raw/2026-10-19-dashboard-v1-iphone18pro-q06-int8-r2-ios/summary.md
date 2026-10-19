| runtime | model | task | cold (run1) | warm (med r2-4) | n | thermal |
|---|---|---|---|---|---|---|
| litert-lm | litert-community/Qwen3-0.6B/dynamic_int8 | long-context-1024-gen256 | 46.6 | 46.3 | 4 | nominal |
| litert-lm | litert-community/Qwen3-0.6B/dynamic_int8 | short-chat | 46.6 | 46.7 | 4 | nominal |
| litert-lm-cpu | litert-community/Qwen3-0.6B/dynamic_wi4b32_afp32 | long-context-1024-gen256 | 50.6 | 47.9 | 4 | fair,serious |
| litert-lm-cpu | litert-community/Qwen3-0.6B/dynamic_wi4b32_afp32 | short-chat | 87.3 | 87.1 | 4 | nominal |
| mlx-swift | mlx-community/Qwen3-0.6B-4bit | short-chat | 230.2 | 221.7 | 3 | nominal |
