# Per-op profile (LiteRT-LM `--enable_profiling`)

Wall ms per decode step from the unprofiled control run; op sums per recorded decode step from the
profiled run, grouped into weight GEMV / attention+KV / transfer / other; "unprof." is the part of
the wall the profiled ops do not cover. A profiled run's rate is never a speed row. A backend that
lists its own delegate node (LITERT_METAL) is a container around its kernels: it stays out of the sums
and is reported in the reading.

```
tag                                                          be     wall steps op-sum   gemv attn+kv  xfer  other unprof. launch/step
litert-community_MiniCPM5-2B_int4_128x256_ctx1024            gpu    11.1   256   10.8    4.8     4.2   0.0    1.7     0.4        1237
litert-community_MiniCPM5-2B_int8_128x256_ctx1024            gpu    13.7   256   13.6    6.8     4.9   0.0    1.8     0.2        1237
```

## Readings

- `litert-community_MiniCPM5-2B_int4_128x256_ctx1024` gpu: gemv is 45% of the profiled op time; 0.4 of the 11.1 ms step is outside the profiled ops; 1237 launches per step; the delegate's own node reads 31.6 ms per step under profiling (a container around the kernels above, kept out of the sums); profiled run decoded 29.0 tok/s against the control's 89.7 (the gap is the profiler's own cost; never a speed row)
- `litert-community_MiniCPM5-2B_int8_128x256_ctx1024` gpu: gemv is 50% of the profiled op time; 0.2 of the 13.7 ms step is outside the profiled ops; 1237 launches per step; the delegate's own node reads 37.9 ms per step under profiling (a container around the kernels above, kept out of the sums); profiled run decoded 24.5 tok/s against the control's 72.9 (the gap is the profiler's own cost; never a speed row)

Runtime: https://github.com/google-ai-edge/litert ; engine: https://github.com/google-ai-edge/LiteRT-LM

## Decode step, per node type (ms per step, share of the profiled op sum; from NODES_int8.txt / NODES_int4.txt)

```
--- int8
control decode 72.86 tok/s (wall 13.72 ms/step); profiled decode 24.51 tok/s; recorded steps 256; profiled op sum 13.56 ms/step; container {'LITERT_METAL': 37.93}
groups (ms/step, share of op sum): gemv 6.83 (50%), attn+kv 4.90 (36%), other 1.83 (13%)
node type                                 ms/step  share  group   nodes
dynamic_update_slice                        2.947  21.7%  attn+kv 84
fc1x1_int8_weights -> add                   2.015  14.9%  gemv    84
fc1x1_int8_weights                          1.650  12.2%  gemv    127
fc1x1_int8_weights -> sigmoid -> m          1.636  12.1%  gemv    42
fc1x1_int8_weights -> mul                   1.530  11.3%  gemv    42
reshape                                     1.243   9.2%  other   294
batched_mat_mul_as_fc                       0.617   4.5%  attn+kv 43
batched_mat_mul_as_fc -> add -> ma          0.538   4.0%  attn+kv 41
rms_normalization -> mul                    0.384   2.8%  other   85
softmax                                     0.253   1.9%  attn+kv 42
mul                                         0.175   1.3%  other   85
--- int4
control decode 89.69 tok/s (wall 11.15 ms/step); profiled decode 28.98 tok/s; recorded steps 256; profiled op sum 10.76 ms/step; container {'LITERT_METAL': 31.61}
groups (ms/step, share of op sum): gemv 4.85 (45%), attn+kv 4.20 (39%), other 1.71 (16%)
node type                                 ms/step  share  group   nodes
dynamic_update_slice                        2.613  24.3%  attn+kv 84
fc1x1_int4_weights -> add                   1.405  13.1%  gemv    84
fc1x1_int4_weights                          1.390  12.9%  gemv    127
reshape                                     1.165  10.8%  other   294
fc1x1_int4_weights -> sigmoid -> m          1.122  10.4%  gemv    42
fc1x1_int4_weights -> mul                   0.931   8.7%  gemv    42
batched_mat_mul_as_fc                       0.436   4.1%  attn+kv 43
batched_mat_mul_as_fc -> add -> ma          0.374   3.5%  attn+kv 41
rms_normalization -> mul                    0.341   3.2%  other   85
softmax                                     0.252   2.3%  attn+kv 42
mul                                         0.170   1.6%  other   85
```
