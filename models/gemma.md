# Gemma

Google's Gemma family. Apple-friendly model architectures and active investment in mobile.

## Variants in scope

| Model | Params | Best fit |
|-------|-------:|----------|
| gemma-3-1b-it-qat-4bit | 1B | strong small-model baseline |
| gemma-3n-E2B-it-lm-4bit | E2B effective | LiteRT-LM and CoreML focus |
| gemma-3n-E4B-it-lm-4bit | E4B effective | bigger Gemma 3n |
| gemma-4-e2b-it-4bit | E2B | latest, ANE / GPU fit being investigated |
| gemma-4-e4b-it-4bit | E4B | latest, larger |
| gemma-2-2b-it-4bit | 2B | older but widely supported |

## Notes

- The Gemma 3 / 4 family ships QAT (quantization-aware-trained) 4-bit weights from Google directly — quality is meaningfully better than naive PTQ for the same bit budget.
- Custom EOS tokens (`<end_of_turn>`, `<turn|>`) need to be wired through to the runtime's stop-token set.
