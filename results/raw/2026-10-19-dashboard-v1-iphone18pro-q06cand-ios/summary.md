| runtime | model | task | cold (run1) | warm (med r2-4) | n | thermal |
|---|---|---|---|---|---|---|
| litert-lm | litert-community/Qwen3-0.6B/dynamic_wi4b32_afp32_r0805meta018 | long-context-1024-gen256 | 142.8 | 142.5 | 4 | nominal |
| litert-lm | litert-community/Qwen3-0.6B/dynamic_wi4b32_afp32_r0805meta018 | short-chat | 181.2 | 180.9 | 4 | nominal |
| litert-lm-cpu | litert-community/Qwen3-0.6B/dynamic_wi4b32_afp32 | long-context-1024-gen256 | 52.4 | 50.1 | 4 | fair,serious |
| litert-lm-cpu | litert-community/Qwen3-0.6B/dynamic_wi4b32_afp32 | short-chat | 87.9 | 87.9 | 4 | nominal |
| litert-lm-cpu | litert-community/Qwen3-0.6B/dynamic_wi4b32_afp32_r0805meta018 | long-context-1024-gen256 | 51.8 | 49.7 | 4 | fair |
| litert-lm-cpu | litert-community/Qwen3-0.6B/dynamic_wi4b32_afp32_r0805meta018 | short-chat | 87.4 | 87.0 | 4 | nominal |
| mlx-swift | mlx-community/Qwen3-0.6B-4bit | short-chat | 222.1 | 221.9 | 3 | nominal |
