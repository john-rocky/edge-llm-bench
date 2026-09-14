# Per-op profile (LiteRT-LM `--enable_profiling`)

Wall ms per decode step from the unprofiled control run; op sums per recorded decode step from the
profiled run, grouped into weight GEMV / attention+KV / transfer / other; "unprof." is the part of
the wall the profiled ops do not cover. A profiled run's rate is never a speed row. A backend that
lists its own delegate node (LITERT_METAL) is a container around its kernels: it stays out of the sums
and is reported in the reading.

```
tag                                                          be     wall steps op-sum   gemv attn+kv  xfer  other unprof. launch/step
…gs-norope_Qwen3-1.7B_wi4b32_gpuflags_norope_128x256_ctx1024 gpu    35.4   256   22.2   19.0     0.9   1.2    1.1    13.2         969
…flags-norope_Qwen3-1.7B_wi8_gpuflags_norope_128x256_ctx1024 gpu    44.7   256   34.6   30.9     1.1   1.1    1.5    10.0         969
```

## Readings

- `litert-local_Qwen3-1.7B-wi4b32-gpuflags-norope_Qwen3-1.7B_wi4b32_gpuflags_norope_128x256_ctx1024` gpu: gemv is 86% of the profiled op time; 13.2 of the 35.4 ms step is outside the profiled ops; 969 launches per step; profiled run decoded 15.0 tok/s against the control's 28.2 (the gap is the profiler's own cost; never a speed row)
- `litert-local_Qwen3-1.7B-wi8-gpuflags-norope_Qwen3-1.7B_wi8_gpuflags_norope_128x256_ctx1024` gpu: gemv is 89% of the profiled op time; 10.0 of the 44.7 ms step is outside the profiled ops; 969 launches per step; profiled run decoded 10.7 tok/s against the control's 22.4 (the gap is the profiler's own cost; never a speed row)

Runtime: https://github.com/google-ai-edge/litert ; engine: https://github.com/google-ai-edge/LiteRT-LM
