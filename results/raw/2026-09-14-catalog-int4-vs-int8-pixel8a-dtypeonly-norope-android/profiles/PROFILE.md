# Per-op profile (LiteRT-LM `--enable_profiling`)

Wall ms per decode step from the unprofiled control run; op sums per recorded decode step from the
profiled run, grouped into weight GEMV / attention+KV / transfer / other; "unprof." is the part of
the wall the profiled ops do not cover. A profiled run's rate is never a speed row. A backend that
lists its own delegate node (LITERT_METAL) is a container around its kernels: it stays out of the sums
and is reported in the reading.

```
tag                                                          be     wall steps op-sum   gemv attn+kv  xfer  other unprof. launch/step
…gs-norope_Qwen3-1.7B_wi4b32_gpuflags_norope_128x256_ctx1024 gpu    95.0   256   65.9   52.2     3.6   5.6    4.5    29.1         969
…flags-norope_Qwen3-1.7B_wi8_gpuflags_norope_128x256_ctx1024 gpu   115.7   256   96.7   79.6     4.9   5.4    6.7    19.1         969
```

## Readings

- `litert-local_Qwen3-1.7B-wi4b32-gpuflags-norope_Qwen3-1.7B_wi4b32_gpuflags_norope_128x256_ctx1024` gpu: gemv is 79% of the profiled op time; 29.1 of the 95.0 ms step is outside the profiled ops; 969 launches per step; profiled run decoded 0.3 tok/s against the control's 10.5 (the gap is the profiler's own cost; never a speed row)
- `litert-local_Qwen3-1.7B-wi8-gpuflags-norope_Qwen3-1.7B_wi8_gpuflags_norope_128x256_ctx1024` gpu: gemv is 82% of the profiled op time; 19.1 of the 115.7 ms step is outside the profiled ops; 969 launches per step; profiled run decoded 3.8 tok/s against the control's 8.6 (the gap is the profiler's own cost; never a speed row)

Runtime: https://github.com/google-ai-edge/litert ; engine: https://github.com/google-ai-edge/LiteRT-LM
