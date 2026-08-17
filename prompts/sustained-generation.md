# Task C — Sustained generation

```
Write a detailed explanation of how local LLM inference works on mobile devices.
```

- Output budget: 512 tokens (optionally 1,024)
- Sampling: `temperature: 0.7`, `topP: 0.9` — typical chat sampling, not greedy
- Stop tokens: model's natural EOS

## What this measures

- Average decode tok/s
- **Minimum** decode tok/s (rolling 5 s window) — exposes thermal throttling
- Speed drop from start to end as a percentage
- Thermal state at the end vs. the start
- Peak memory during the run
- Crash / hang / completion status

## Why temperature 0.7

Greedy sampling can hit cycles or short EOS-quickly behaviors that don't reflect real chat usage. 0.7 / 0.9 is the typical chat configuration and matches what users will actually experience.
