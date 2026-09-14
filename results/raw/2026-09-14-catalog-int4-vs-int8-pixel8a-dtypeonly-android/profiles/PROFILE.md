# Per-op profile (LiteRT-LM `--enable_profiling`)

Wall ms per decode step from the unprofiled control run; op sums per recorded decode step from the
profiled run, grouped into weight GEMV / attention+KV / transfer / other; "unprof." is the part of
the wall the profiled ops do not cover. A profiled run's rate is never a speed row. A backend that
lists its own delegate node (LITERT_METAL) is a container around its kernels: it stays out of the sums
and is reported in the reading.

```
tag                                                          be     wall steps op-sum   gemv attn+kv  xfer  other unprof. launch/step
…-wi4b32-gpuflags_Qwen3-1.7B_wi4b32_gpuflags_128x256_ctx1024 gpu    93.9   256   67.6   54.6     3.2   5.8    4.1    26.3         795
…3-1.7B-wi8-gpuflags_Qwen3-1.7B_wi8_gpuflags_128x256_ctx1024 gpu   115.6   256   95.3   82.4     3.0   5.9    3.9    20.3         795
```

## Readings

- `litert-local_Qwen3-1.7B-wi4b32-gpuflags_Qwen3-1.7B_wi4b32_gpuflags_128x256_ctx1024` gpu: gemv is 81% of the profiled op time; 26.3 of the 93.9 ms step is outside the profiled ops; 795 launches per step; profiled run decoded 0.3 tok/s against the control's 10.7 (the gap is the profiler's own cost; never a speed row)
- `litert-local_Qwen3-1.7B-wi8-gpuflags_Qwen3-1.7B_wi8_gpuflags_128x256_ctx1024` gpu: gemv is 86% of the profiled op time; 20.3 of the 115.6 ms step is outside the profiled ops; 795 launches per step; profiled run decoded 0.3 tok/s against the control's 8.7 (the gap is the profiler's own cost; never a speed row)

Runtime: https://github.com/google-ai-edge/litert ; engine: https://github.com/google-ai-edge/LiteRT-LM
