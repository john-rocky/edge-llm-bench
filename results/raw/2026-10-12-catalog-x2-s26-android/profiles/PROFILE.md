# Per-op profile (LiteRT-LM `--enable_profiling`)

Wall ms per decode step from the unprofiled control run; op sums per recorded decode step from the
profiled run, grouped into weight GEMV / attention+KV / transfer / other; "unprof." is the part of
the wall the profiled ops do not cover. A profiled run's rate is never a speed row. A backend that
lists its own delegate node (LITERT_METAL) is a container around its kernels: it stays out of the sums
and is reported in the reading.

```
tag                                                          be     wall steps op-sum   gemv attn+kv  xfer  other unprof. launch/step
…ty_gemma-4-E2B-it-litert-lm_gemma-4-E2B-it_1024x256_ctx2304 cpu    26.4   131   24.1   17.2     5.6   0.0    1.2     2.3        3982
…ty_gemma-4-E2B-it-litert-lm_gemma-4-E2B-it_1024x256_ctx4096 cpu    30.5   131   25.9   16.7     7.4   0.0    1.8     4.7        3982
…ty_gemma-4-E2B-it-litert-lm_gemma-4-E2B-it_1024x256_ctx8192 cpu    48.7   131   46.6   23.8    18.6   0.0    4.1     2.1        3982
```

## Readings

- `litert-community_gemma-4-E2B-it-litert-lm_gemma-4-E2B-it_1024x256_ctx2304` cpu: gemv is 72% of the profiled op time; 2.3 of the 26.4 ms step is outside the profiled ops; 3982 launches per step; profiled run decoded 27.8 tok/s against the control's 37.9 (the gap is the profiler's own cost; never a speed row)
- `litert-community_gemma-4-E2B-it-litert-lm_gemma-4-E2B-it_1024x256_ctx4096` cpu: gemv is 64% of the profiled op time; 4.7 of the 30.5 ms step is outside the profiled ops; 3982 launches per step; profiled run decoded 26.3 tok/s against the control's 32.7 (the gap is the profiler's own cost; never a speed row)
- `litert-community_gemma-4-E2B-it-litert-lm_gemma-4-E2B-it_1024x256_ctx8192` cpu: gemv is 51% of the profiled op time; 2.1 of the 48.7 ms step is outside the profiled ops; 3982 launches per step; profiled run decoded 16.9 tok/s against the control's 20.6 (the gap is the profiler's own cost; never a speed row)

Runtime: https://github.com/google-ai-edge/litert ; engine: https://github.com/google-ai-edge/LiteRT-LM
