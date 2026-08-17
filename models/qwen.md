# Qwen

Alibaba's Qwen family. Strong general-purpose models, well-supported across runtimes.

## Variants in scope

| Model | Params | Best fit |
|-------|-------:|----------|
| Qwen3-0.6B-4bit | 0.6B | iPhone default — fast, ~400 MB on disk |
| Qwen3-1.7B-4bit | 1.7B | iPhone Pro, better quality |
| Qwen3-4B-4bit | 4B | iPhone Pro Max, slow but usable |
| Qwen2.5-1.5B-Instruct-4bit | 1.5B | older but very stable |
| Qwen2.5-0.5B-Instruct-4bit | 0.5B | smallest practical chat model |

MLX repos live under `mlx-community/`. GGUF conversions live under `bartowski/` and `unsloth/`.

## Notes

- Qwen3 uses a thinking/non-thinking mode toggle — set `enable_thinking=False` in the chat template for the benchmark prompts (we want comparable wall-clock numbers, not extra reasoning tokens).
- Tokenizer is fast — chat template handling is well-supported in `swift-transformers`.
