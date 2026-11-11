| runtime | model | task | cold (run1) | warm (med r2-4) | n | thermal |
|---|---|---|---|---|---|---|
| core-ai | core-ai/qwen3-4b-gpu | short-chat | 41.9 | 41.8 | 4 | nominal |
| litert-lm | litert-community/Qwen3-4B | long-context-1024-gen256 | 35.2 | 19.8 | 4 | fair,nominal |
| litert-lm | litert-community/Qwen3-4B | short-chat | 37.9 | 21.4 | 4 | fair,nominal |
| litert-lm | litert-community/gemma-4-E2B-it-litert-lm | long-context-1024-gen256 | 87.3 | 87.4 | 4 | nominal |
| litert-lm | litert-community/gemma-4-E2B-it-litert-lm | short-chat | 86.7 | 90.8 | 4 | nominal |
| llama.cpp | unsloth/Qwen3-4B-GGUF/Q4_K_M | long-context-1024-gen256 | 33.7 | 33.9 | 4 | nominal |
| llama.cpp | unsloth/Qwen3-4B-GGUF/Q4_K_M | short-chat | 37.1 | 37.0 | 4 | nominal |
| llama.cpp | unsloth/gemma-4-E2B-it-GGUF/Q4_K_M | long-context-1024-gen256 | 58.3 | 58.2 | 4 | nominal |
| llama.cpp | unsloth/gemma-4-E2B-it-GGUF/Q4_K_M | short-chat | 59.3 | 50.2 | 4 | nominal |
| mlx-swift | mlx-community/Qwen3-0.6B-4bit | short-chat | 239.3 | 221.2 | 3 | nominal |
| mlx-swift | mlx-community/Qwen3-4B-4bit | long-context-1024-gen256 | 40.2 | 40.2 | 4 | nominal |
| mlx-swift | mlx-community/Qwen3-4B-4bit | short-chat | 45.3 | 45.3 | 4 | nominal |
| mlx-swift | mlx-community/gemma-4-e2b-it-4bit | long-context-1024-gen256 | 68.9 | 68.7 | 4 | nominal |
| mlx-swift | mlx-community/gemma-4-e2b-it-4bit | short-chat | 71.8 | 71.5 | 4 | nominal |
| mlx-swift | mlx-community/gemma-4-e2b-it-qat-OptiQ-4bit | long-context-1024-gen256 | 52.3 | 52.3 | 4 | nominal |
| mlx-swift | mlx-community/gemma-4-e2b-it-qat-OptiQ-4bit | short-chat | 53.9 | 54.1 | 4 | nominal |
| onnxruntime-genai-cpu | onnx-community/Qwen3-4B-ONNX | long-context-1024-gen256 | 14.4 | 8.9 | 4 | fair,nominal,serious |
| onnxruntime-genai-cpu | onnx-community/Qwen3-4B-ONNX | short-chat | 15.7 | 19.9 | 4 | nominal |
