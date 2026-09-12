# Per-op profile (LiteRT-LM `--enable_profiling`)

Wall ms per decode step from the unprofiled control run; op sums per recorded decode step from the
profiled run, grouped into weight GEMV / attention+KV / transfer / other; "unprof." is the part of
the wall the profiled ops do not cover. A profiled run's rate is never a speed row.

```
tag                                                          be     wall steps op-sum   gemv attn+kv  xfer  other unprof. launch/step
…ity_gemma-4-E2B-it-litert-lm_gemma-4-E2B-it_128x256_ctx1024 gpu   115.9   256   81.1   58.9     3.7   5.4   13.1    34.8        1300
```

## Readings

- `litert-community_gemma-4-E2B-it-litert-lm_gemma-4-E2B-it_128x256_ctx1024` gpu: gemv is 73% of the profiled op time; 34.8 of the 115.9 ms step is outside the profiled ops; 1300 launches per step; profiled run decoded 3.5 tok/s against the control's 8.6 (the gap is the profiler's own cost; never a speed row)

Runtime: https://github.com/google-ai-edge/litert ; engine: https://github.com/google-ai-edge/LiteRT-LM
