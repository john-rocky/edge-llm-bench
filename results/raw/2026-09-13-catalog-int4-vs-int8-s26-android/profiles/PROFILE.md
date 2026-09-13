# Per-op profile (LiteRT-LM `--enable_profiling`)

Wall ms per decode step from the unprofiled control run; op sums per recorded decode step from the
profiled run, grouped into weight GEMV / attention+KV / transfer / other; "unprof." is the part of
the wall the profiled ops do not cover. A profiled run's rate is never a speed row. A backend that
lists its own delegate node (LITERT_METAL) is a container around its kernels: it stays out of the sums
and is reported in the reading.

```
tag                                                          be     wall steps op-sum   gemv attn+kv  xfer  other unprof. launch/step
…_Qwen3-1.7B_Qwen3-1.7B_dynamic_wi4b32_afp32_128x256_ctx1024 gpu    34.2   256   21.3   18.5     0.7   1.1    1.0    12.9         795
litert-local_Qwen3-1.7B-int8_Qwen3_1.7B_128x256_ctx1024      gpu    66.0   256   52.2   26.9    22.7   1.5    1.2    13.8         939
```

## Readings

- `litert-community_Qwen3-1.7B_Qwen3-1.7B_dynamic_wi4b32_afp32_128x256_ctx1024` gpu: gemv is 87% of the profiled op time; 12.9 of the 34.2 ms step is outside the profiled ops; 795 launches per step; profiled run decoded 16.1 tok/s against the control's 29.2 (the gap is the profiler's own cost; never a speed row)
- `litert-local_Qwen3-1.7B-int8_Qwen3_1.7B_128x256_ctx1024` gpu: gemv is 51% of the profiled op time; 13.8 of the 66.0 ms step is outside the profiled ops; 939 launches per step; profiled run decoded 7.8 tok/s against the control's 15.2 (the gap is the profiler's own cost; never a speed row)

Runtime: https://github.com/google-ai-edge/litert ; engine: https://github.com/google-ai-edge/LiteRT-LM
