| runtime | model | task | cold (run1) | warm (med r2-4) | n | thermal |
|---|---|---|---|---|---|---|
| core-ai | core-ai/qwen3-4b-gpu | short-chat | 40.6 | 41.3 | 4 | nominal |
| litert-lm | litert-community/Qwen3-4B | long-context-1024-gen256 | 36.5 | 20.4 | 4 | fair,nominal |
| litert-lm | litert-community/Qwen3-4B | short-chat | 40.4 | 23.9 | 4 | fair,nominal |
| litert-lm | litert-community/gemma-4-E2B-it-litert-lm | short-chat | 86.8 | 90.7 | 4 | nominal |
| llama.cpp | unsloth/Qwen3-4B-GGUF/Q4_K_M | long-context-1024-gen256 | 33.6 | 33.8 | 4 | nominal |
| llama.cpp | unsloth/Qwen3-4B-GGUF/Q4_K_M | short-chat | 38.4 | 36.9 | 4 | nominal |
| llama.cpp | unsloth/gemma-4-E2B-it-GGUF/Q4_K_M | long-context-1024-gen256 | 58.4 | 57.7 | 4 | nominal |
| llama.cpp | unsloth/gemma-4-E2B-it-GGUF/Q4_K_M | short-chat | 56.5 | 58.6 | 4 | nominal |
| mlx-swift | mlx-community/Qwen3-0.6B-4bit | short-chat | 239.0 | 220.9 | 3 | nominal |
| mlx-swift | mlx-community/Qwen3-4B-4bit | long-context-1024-gen256 | 40.3 | 40.2 | 4 | nominal |
| mlx-swift | mlx-community/Qwen3-4B-4bit | short-chat | 45.4 | 45.3 | 4 | nominal |
| mlx-swift | mlx-community/gemma-4-e2b-it-4bit | long-context-1024-gen256 | 68.7 | 68.5 | 4 | nominal |
| mlx-swift | mlx-community/gemma-4-e2b-it-4bit | short-chat | 70.6 | 70.5 | 4 | nominal |
| mlx-swift | mlx-community/gemma-4-e2b-it-qat-OptiQ-4bit | long-context-1024-gen256 | 50.6 | 52.4 | 4 | nominal |
| mlx-swift | mlx-community/gemma-4-e2b-it-qat-OptiQ-4bit | short-chat | 52.2 | 54.0 | 4 | nominal |
| onnxruntime-genai-cpu | onnx-community/Qwen3-4B-ONNX | long-context-1024-gen256 | 14.5 | 9.1 | 4 | fair,nominal,serious |
| onnxruntime-genai-cpu | onnx-community/Qwen3-4B-ONNX | short-chat | 22.8 | 20.3 | 4 | nominal |
