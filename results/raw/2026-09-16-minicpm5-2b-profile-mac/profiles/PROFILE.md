# Per-op profile (LiteRT-LM `--enable_profiling`)

Wall ms per decode step from the unprofiled control run; op sums per recorded decode step from the
profiled run, grouped into weight GEMV / attention+KV / transfer / other; "unprof." is the part of
the wall the profiled ops do not cover. A profiled run's rate is never a speed row. A backend that
lists its own delegate node (LITERT_METAL) is a container around its kernels: it stays out of the sums
and is reported in the reading.

```
tag                                                          be     wall steps op-sum   gemv attn+kv  xfer  other unprof. launch/step
litert-community_MiniCPM5-2B_int4_128x256_ctx1024            gpu    11.1   256   10.8    4.8     4.2   0.0    1.7     0.4        1237
litert-community_MiniCPM5-2B_int4_128x256_ctx1024-run2       gpu    11.0   256   11.0    4.9     4.2   0.0    1.8    -0.0        1237
litert-community_MiniCPM5-2B_int8_128x256_ctx1024            gpu    13.7   256   13.6    6.8     4.9   0.0    1.8     0.2        1237
litert-community_MiniCPM5-2B_int8_128x256_ctx1024-run2       gpu    13.4   256   13.5    6.8     4.9   0.0    1.9    -0.1        1237
…ert-community_MiniCPM5-2B_readme-int4b32-cl_128x256_ctx1024 gpu     7.0   257    7.3    5.2     0.9   0.0    1.2    -0.3        1113
litert-community_MiniCPM5-2B_readme-int8_128x256_ctx1024     gpu     8.9   257    9.2    7.1     0.9   0.0    1.2    -0.3        1113
```

## Readings

- `litert-community_MiniCPM5-2B_int4_128x256_ctx1024` gpu: gemv is 45% of the profiled op time; 0.4 of the 11.1 ms step is outside the profiled ops; 1237 launches per step; the delegate's own node reads 31.6 ms per step under profiling (a container around the kernels above, kept out of the sums); profiled run decoded 29.0 tok/s against the control's 89.7 (the gap is the profiler's own cost; never a speed row)
- `litert-community_MiniCPM5-2B_int4_128x256_ctx1024-run2` gpu: gemv is 45% of the profiled op time; profiled op time exceeds the 11.0 ms wall by 0.0 ms (profiler cost inside the op times); 1237 launches per step; the delegate's own node reads 32.2 ms per step under profiling (a container around the kernels above, kept out of the sums); profiled run decoded 28.6 tok/s against the control's 91.3 (the gap is the profiler's own cost; never a speed row)
- `litert-community_MiniCPM5-2B_int8_128x256_ctx1024` gpu: gemv is 50% of the profiled op time; 0.2 of the 13.7 ms step is outside the profiled ops; 1237 launches per step; the delegate's own node reads 37.9 ms per step under profiling (a container around the kernels above, kept out of the sums); profiled run decoded 24.5 tok/s against the control's 72.9 (the gap is the profiler's own cost; never a speed row)
- `litert-community_MiniCPM5-2B_int8_128x256_ctx1024-run2` gpu: gemv is 50% of the profiled op time; profiled op time exceeds the 13.4 ms wall by 0.1 ms (profiler cost inside the op times); 1237 launches per step; the delegate's own node reads 38.6 ms per step under profiling (a container around the kernels above, kept out of the sums); profiled run decoded 24.1 tok/s against the control's 74.5 (the gap is the profiler's own cost; never a speed row)
- `litert-community_MiniCPM5-2B_readme-int4b32-cl_128x256_ctx1024` gpu: gemv is 71% of the profiled op time; profiled op time exceeds the 7.0 ms wall by 0.3 ms (profiler cost inside the op times); 1113 launches per step; the delegate's own node reads 23.6 ms per step under profiling (a container around the kernels above, kept out of the sums); profiled run decoded 39.7 tok/s against the control's 142.5 (the gap is the profiler's own cost; never a speed row)
- `litert-community_MiniCPM5-2B_readme-int8_128x256_ctx1024` gpu: gemv is 77% of the profiled op time; profiled op time exceeds the 8.9 ms wall by 0.3 ms (profiler cost inside the op times); 1113 launches per step; the delegate's own node reads 27.4 ms per step under profiling (a container around the kernels above, kept out of the sums); profiled run decoded 34.3 tok/s against the control's 112.1 (the gap is the profiler's own cost; never a speed row)

Runtime: https://github.com/google-ai-edge/litert ; engine: https://github.com/google-ai-edge/LiteRT-LM
