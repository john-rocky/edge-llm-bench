# Phi

Microsoft's Phi family.

## Variants in scope

| Model | Params | Best fit |
|-------|-------:|----------|
| Phi-3.5-mini-instruct-4bit | 3.8B | strong general baseline |

## Notes

- Phi 3.5 uses `<|end|>` as an extra stop token — make sure the runtime's stop-token set is configured.
- Tokenizer chat template is supported in `swift-transformers`.
