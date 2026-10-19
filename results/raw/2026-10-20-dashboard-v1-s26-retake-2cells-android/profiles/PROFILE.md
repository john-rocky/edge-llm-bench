# Per-op profile (LiteRT-LM `--enable_profiling`)

Wall ms per decode step from the unprofiled control run; op sums per recorded decode step from the
profiled run, grouped into weight GEMV / attention+KV / transfer / other; "unprof." is the part of
the wall the profiled ops do not cover. A profiled run's rate is never a speed row. A backend that
lists its own delegate node (LITERT_METAL) is a container around its kernels: it stays out of the sums
and is reported in the reading.

```
tag                                                          be     wall steps op-sum   gemv attn+kv  xfer  other unprof. launch/step
…community_Qwen3-0.6B_qwen3_0_6b_mixed_int4_1024x256_ctx2048 gpu    14.7   257   11.4    9.3     0.5   0.8    0.8     3.4         654
```

## Readings

- `litert-community_Qwen3-0.6B_qwen3_0_6b_mixed_int4_1024x256_ctx2048` gpu: gemv is 82% of the profiled op time; 3.4 of the 14.7 ms step is outside the profiled ops; 654 launches per step; profiled run decoded 29.3 tok/s against the control's 67.9 (the gap is the profiler's own cost; never a speed row)

Runtime: https://github.com/google-ai-edge/litert ; engine: https://github.com/google-ai-edge/LiteRT-LM
