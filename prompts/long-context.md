# Task B — Long-context prefill

A fixed 2,000-token prompt. Output: 64 tokens.

## Generation procedure

The 2K prompt is generated deterministically inside the app from a Lorem-ipsum-like seed plus a final instruction. Identical bytes for every runtime so the comparison is fair. The exact text and seed are written into the result JSON.

Why generated rather than copy-pasted: avoids licensing concerns and makes it trivial to extend to 4K / 8K variants.

## Optional 4K variant

Runs only if the runtime/model claims context >= 4096. Otherwise reported as `unsupported`.

## What this measures

- Prefill tok/s — prompt-processing throughput, dominated by KV cache construction
- TTFT — TTFT for long prompts is usually 90%+ prefill
- Decode tok/s post-prefill — should match Task A's decode rate; if it doesn't, the runtime is doing something pathological with the long context

## Sampling

Greedy. We don't care about the output quality here, only the latency curve.
