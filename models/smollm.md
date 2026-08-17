# SmolLM

HuggingFace's small-model family. The smallest models that still feel like a chat assistant.

## Variants in scope

| Model | Params | Best fit |
|-------|-------:|----------|
| SmolLM-135M-Instruct-4bit | 135M | smallest practical instruct model |
| SmolLM3-3B-4bit | 3B | a strong 3B baseline |

## Notes

- SmolLM-135M is interesting as a "what if the model was the size of a sticker" baseline.
- SmolLM3-3B has long-context support and benefits from quantized KV cache on iPhone.
