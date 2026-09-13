# Per-op profile (LiteRT-LM `--enable_profiling`)

Wall ms per decode step from the unprofiled control run; op sums per recorded decode step from the
profiled run, grouped into weight GEMV / attention+KV / transfer / other; "unprof." is the part of
the wall the profiled ops do not cover. A profiled run's rate is never a speed row. A backend that
lists its own delegate node (LITERT_METAL) is a container around its kernels: it stays out of the sums
and is reported in the reading.

```
tag                                                          be     wall steps op-sum   gemv attn+kv  xfer  other unprof. launch/step
…_Qwen3-1.7B_Qwen3-1.7B_dynamic_wi4b32_afp32_128x256_ctx1024 gpu    94.4   256   74.2   56.7     5.7   5.4    6.4    20.3         795
litert-local_Qwen3-1.7B-int8_Qwen3_1.7B_128x256_ctx1024      gpu   130.0   256  112.9   44.9    56.1   7.7    4.2    17.2         939
```

## Readings

- `litert-community_Qwen3-1.7B_Qwen3-1.7B_dynamic_wi4b32_afp32_128x256_ctx1024` gpu: gemv is 76% of the profiled op time; 20.3 of the 94.4 ms step is outside the profiled ops; 795 launches per step; profiled run decoded 4.5 tok/s against the control's 10.6 (the gap is the profiler's own cost; never a speed row)
- `litert-local_Qwen3-1.7B-int8_Qwen3_1.7B_128x256_ctx1024` gpu: attn+kv is 50% of the profiled op time; 17.2 of the 130.0 ms step is outside the profiled ops; 939 launches per step; profiled run decoded 0.2 tok/s against the control's 7.7 (the gap is the profiler's own cost; never a speed row)

Runtime: https://github.com/google-ai-edge/litert ; engine: https://github.com/google-ai-edge/LiteRT-LM
