# Endurance chat — turn script

The fixed 12-prompt cycle every `endurance-chat-<N>m` session runs
(`EnduranceChatTask.turnPrompts` is the source of truth; this file is the
rationale). Protocol: `methodology/endurance.md`.

```
 1. Let's talk about running language models on phones. In two or three
    sentences, what is the biggest engineering constraint?
 2. Which matters more for the experience you just described: prefill speed or
    decode speed? Answer briefly and say why.
 3. Give me a concrete example with a model around 2B parameters.
 4. Summarize our conversation so far in one short paragraph.
 5. Now switch topics: explain KV cache growth during a long chat, in a few
    sentences.
 6. How does quantization interact with the problem you just explained? Keep
    it brief.
 7. Earlier you named an engineering constraint. Does quantization help with
    that one too? A short answer is fine.
 8. Write a four-line rhyming poem about a phone getting warm while it thinks.
 9. In one sentence each, name three ways a chat app can shorten its context
    when the conversation gets long.
10. Which of those three would you pick for a low-RAM device, and why? Two
    sentences.
11. Summarize everything we have discussed in this whole conversation in one
    short paragraph.
12. Ask me one good follow-up question about on-device AI, then answer it
    yourself in two sentences.
```

- Sampling: `temperature 0.7 / topP 0.9 / topK 40` (Task C's chat
  configuration, not greedy — greedy hits cycles that misrepresent real chat).
- Per-turn output cap: 256 tokens, enforced natively.
- Turns 2, 7, 10 are follow-ups that only make sense against earlier turns —
  they force attention over the accumulated KV rather than letting each turn
  be effectively independent.
- Turns 4 and 11 are full-context sweeps (summarize everything), the heaviest
  read of the conversation state.
- Turn 8 (verse) breaks topic monotony so the degeneracy check sees varied
  output shapes, and gives repetition-collapse a place to show early.
- Prompts are all ≤ ~50 tokens so per-turn prefill stays dominated by the
  conversation delta, not the script.

Why deterministic and identical for every model: the script is part of the
measurement contract (same-budget). Changing a prompt changes the task — bump
the task id, don't edit in place.
