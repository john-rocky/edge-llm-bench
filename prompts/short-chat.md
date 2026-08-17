# Task A — Short chat

```
Explain what on-device AI means in simple terms.
```

- Output budget: 128 tokens
- Sampling: greedy (`temperature: 0.0`) for reproducibility
- Stop tokens: model's natural EOS + any model-specific extras (`<end_of_turn>`, `<|end|>`, etc.)

## What this measures

- TTFT — first-impression latency
- Decode tok/s — steady-state generation rate
- Total time — what the user perceives as "how long until I can read the answer"

## Why this prompt

Short, neutral, generates well-formed prose for any model that has any chat capability. Avoids math, code, and tool-use, which would over-specialize the test toward specific models.
