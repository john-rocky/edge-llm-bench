| runtime | model | task | cold (run1) | warm (med r2-4) | n | thermal |
|---|---|---|---|---|---|---|
| core-ai-ane | core-ai/gemma4-e2b-stock-ctx2048 | long-context-1024-gen256 | 46.1 | 47.0 | 3 | fair |
| core-ai-ane | core-ai/qwen3-0.6b-stock-ctx2048 | long-context-1024-gen256 | 65.0 | 64.9 | 3 | nominal |
| core-ai-ane | core-ai/qwen3-4b-stock-ctx2048 | long-context-1024-gen256 | 21.3 | 21.2 | 3 | fair |
| litert-lm | litert-community/Qwen3-0.6B | long-context-1024-gen256 | 98.0 | 94.6 | 3 | nominal |
| litert-lm | litert-community/Qwen3-0.6B | short-chat | 125.6 | 124.7 | 3 | fair |
| litert-lm | litert-community/Qwen3-1.7B | long-context-1024-gen256 | 48.1 | 41.4 | 3 | fair |
| litert-lm | litert-community/gemma-4-E2B-it-litert-lm | long-context-1024-gen256 | 57.5 | 45.5 | 3 | fair |
| mlx-swift | mlx-community/Qwen3-0.6B-4bit | short-chat | 180.6 | 179.5 | 3 | fair |
