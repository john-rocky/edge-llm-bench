| runtime | model | task | cold (run1) | warm (med r2-4) | n | thermal |
|---|---|---|---|---|---|---|
| core-ai-ane | core-ai/gemma4-e2b-stock-ctx2048 | long-context-1024-gen256 | 68.7 | 68.9 | 3 | nominal |
| core-ai-ane | core-ai/qwen3-0.6b-stock-ctx2048 | long-context-1024-gen256 | 3.8 | 101.4 | 3 | nominal |
| core-ai-ane | core-ai/qwen3-1.7b-stock-ctx2048 | long-context-1024-gen256 | 55.5 | 55.5 | 3 | nominal |
| litert-lm | litert-community/Qwen3-0.6B | long-context-1024-gen256 | 134.5 | 133.9 | 3 | nominal |
| litert-lm | litert-community/Qwen3-0.6B | short-chat | 170.3 | 171.1 | 3 | nominal |
| litert-lm | litert-community/Qwen3-1.7B | long-context-1024-gen256 | 68.4 | 68.5 | 3 | nominal |
| litert-lm | litert-community/Qwen3-4B | long-context-1024-gen256 | 34.3 | 21.2 | 3 | fair,nominal |
| litert-lm | litert-community/gemma-4-E2B-it-litert-lm | long-context-1024-gen256 | 75.0 | 78.6 | 3 | nominal |
| litert-lm | litert-community/gemma-4-E4B-it-litert-lm | long-context-1024-gen256 | 33.9 | 23.7 | 3 | fair,nominal |
| mlx-swift | mlx-community/Qwen3-0.6B-4bit | short-chat | 224.6 | 222.6 | 3 | nominal |
