| runtime | model | task | cold (run1) | warm (med r2-4) | n | thermal |
|---|---|---|---|---|---|---|
| core-ai | core-ai/qwen3-0.6b-4bit-gpu | short-chat | 240.7 | 234.6 | 4 | nominal |
| core-ai | core-ai/qwen3-1.7b-gpu | short-chat | 99.0 | 99.1 | 4 | nominal |
| litert-lm | litert-community/Qwen3-0.6B/dynamic_int8 | long-context-1024-gen256 | 46.6 | 46.3 | 4 | fair,nominal |
| litert-lm | litert-community/Qwen3-0.6B/dynamic_int8 | short-chat | 46.5 | 46.7 | 4 | nominal |
| litert-lm | litert-community/Qwen3-1.7B | long-context-1024-gen256 | 72.7 | 72.8 | 4 | nominal |
| litert-lm | litert-community/Qwen3-1.7B | short-chat | 82.1 | 81.7 | 4 | nominal |
| litert-lm | litert-community/gemma-4-E4B-it-litert-lm | long-context-1024-gen256 | 39.5 | 20.7 | 4 | fair,nominal |
| litert-lm | litert-community/gemma-4-E4B-it-litert-lm | short-chat | 40.9 | 33.2 | 4 | nominal,serious |
| litert-lm-cpu | litert-community/Qwen3-0.6B/dynamic_wi4b32_afp32 | long-context-1024-gen256 | 52.2 | 49.5 | 4 | fair,nominal |
| litert-lm-cpu | litert-community/Qwen3-0.6B/dynamic_wi4b32_afp32 | short-chat | 88.0 | 89.2 | 4 | nominal |
| llama.cpp | unsloth/Qwen3-0.6B-GGUF/Q4_K_M | long-context-1024-gen256 | 148.2 | 148.0 | 4 | nominal |
| llama.cpp | unsloth/Qwen3-0.6B-GGUF/Q4_K_M | short-chat | 189.3 | 183.5 | 4 | nominal |
| llama.cpp | unsloth/Qwen3-1.7B-GGUF/Q4_K_M | long-context-1024-gen256 | 64.2 | 64.2 | 4 | nominal |
| llama.cpp | unsloth/Qwen3-1.7B-GGUF/Q4_K_M | short-chat | 82.8 | 71.9 | 4 | nominal |
| llama.cpp | unsloth/gemma-4-E4B-it-GGUF/Q4_K_M | long-context-1024-gen256 | 29.2 | 29.3 | 4 | nominal |
| llama.cpp | unsloth/gemma-4-E4B-it-GGUF/Q4_K_M | short-chat | 29.6 | 29.4 | 4 | nominal |
| mlx-swift | mlx-community/Qwen3-0.6B-4bit | long-context-1024-gen256 | 174.7 | 175.2 | 4 | nominal |
| mlx-swift | mlx-community/Qwen3-0.6B-4bit | short-chat | 233.2 | 221.2 | 3 | nominal |
| mlx-swift | mlx-community/Qwen3-1.7B-4bit | long-context-1024-gen256 | 86.7 | 86.9 | 4 | nominal |
| mlx-swift | mlx-community/Qwen3-1.7B-4bit | short-chat | 101.6 | 101.6 | 4 | nominal |
| mlx-swift | mlx-community/gemma-4-e4b-it-4bit | long-context-1024-gen256 | 36.9 | 36.9 | 4 | nominal |
| mlx-swift | mlx-community/gemma-4-e4b-it-4bit | short-chat | 37.8 | 38.1 | 4 | nominal |
| onnxruntime-genai-cpu | onnx-community/Qwen3-0.6B-ONNX | long-context-1024-gen256 | 63.7 | 59.4 | 4 | nominal |
| onnxruntime-genai-cpu | onnx-community/Qwen3-0.6B-ONNX | short-chat | 140.1 | 128.2 | 4 | nominal |
| onnxruntime-genai-cpu | onnx-community/Qwen3-1.7B-ONNX | long-context-1024-gen256 | 32.0 | 24.6 | 4 | fair |
| onnxruntime-genai-cpu | onnx-community/Qwen3-1.7B-ONNX | short-chat | 51.7 | 47.7 | 4 | nominal |
