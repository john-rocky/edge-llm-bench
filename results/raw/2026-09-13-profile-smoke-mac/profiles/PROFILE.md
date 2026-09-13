# Per-op profile (LiteRT-LM `--enable_profiling`)

Wall ms per decode step from the unprofiled control run; op sums per recorded decode step from the
profiled run, grouped into weight GEMV / attention+KV / transfer / other; "unprof." is the part of
the wall the profiled ops do not cover. A profiled run's rate is never a speed row. A backend that
lists its own delegate node (LITERT_METAL) is a container around its kernels: it stays out of the sums
and is reported in the reading.

```
tag                                                          be     wall steps op-sum   gemv attn+kv  xfer  other unprof. launch/step
…-community_Qwen3-0.6B_qwen3_0_6b_mixed_int4_128x256_ctx1024 cpu    11.5   225   10.0    4.2     5.1   0.0    0.6     1.6        2316
…-community_Qwen3-0.6B_qwen3_0_6b_mixed_int4_128x256_ctx1024 gpu     4.6   256    5.4    3.0     0.8   0.0    1.6    -0.9         854
```

## Readings

- `litert-community_Qwen3-0.6B_qwen3_0_6b_mixed_int4_128x256_ctx1024` cpu: attn+kv is 51% of the profiled op time; 1.6 of the 11.5 ms step is outside the profiled ops; 2316 launches per step; profiled run decoded 40.1 tok/s against the control's 86.7 (the gap is the profiler's own cost; never a speed row)
- `litert-community_Qwen3-0.6B_qwen3_0_6b_mixed_int4_128x256_ctx1024` gpu: gemv is 55% of the profiled op time; profiled op time exceeds the 4.6 ms wall by 0.9 ms (profiler cost inside the op times); 854 launches per step; the delegate's own node reads 21.6 ms per step under profiling (a container around the kernels above, kept out of the sums); profiled run decoded 42.4 tok/s against the control's 219.0 (the gap is the profiler's own cost; never a speed row)

## Incomplete pairs

- litert-community_Qwen3-0.6B_qwen3_0_6b_mixed_int4_128x256_ctx1024-webgpu gpu: profiled run failed (exit 13) - not tabulated
- litert-community_Qwen3-0.6B_qwen3_0_6b_mixed_int4_128x256_ctx1024-webgpu-v0170 gpu: profiled run failed (exit 13) - not tabulated

## cpu vs gpu per node type: `litert-community_Qwen3-0.6B_qwen3_0_6b_mixed_int4_128x256_ctx1024`

```
litert-community_Qwen3-0.6B_qwen3_0_6b_mixed_int4_128x256_ctx1024 cpu: nodes 1327; prefill turn (128, 418.883625); decode turn (256, 6381.577499999999); speeds {'Prefill': 305.57, 'Decode': 40.12}; profiled sum decode 1606 ms, prefill 1004 ms
litert-community_Qwen3-0.6B_qwen3_0_6b_mixed_int4_128x256_ctx1024 gpu: nodes 1993; prefill turn (128, 111.934292); decode turn (256, 6039.196); speeds {'Prefill': 1143.53, 'Decode': 42.39}; profiled sum decode 6920 ms, prefill 150 ms

=== litert-community_Qwen3-0.6B_qwen3_0_6b_mixed_int4_128x256_ctx1024 decode: ms summed over the turn (256 decode steps / all prefill calls); (n nodes) ===
node type                               cpu ms    gpu ms  gpu/cpu  nodes cpu/gpu
LITERT_METAL                               0.0    5532.9      n/a  0/1
Fully Connected GEMM                     942.6       0.0     0.00  7/0
Batch Matrix Multiply GEMM               451.6       0.0     0.00  1/0
fc1x1_int4_weights                         0.0     291.8      n/a  0/85
fc1x1_int4_weights -> add                  0.0     170.0      n/a  0/56
rms_normalization -> mul                   0.0     154.4      n/a  0/113
fully_connected                            0.0     144.6      n/a  0/56
reshape                                    0.0      85.5      n/a  0/85
fc1x1_int4_weights -> mul                  0.0      81.9      n/a  0/28
fc1x1_int4_weights -> sigmoid -> m         0.0      81.2      n/a  0/28
Softmax                                   62.7       0.0     0.00  1/0
Static Reshape                            51.1       0.0     0.00  9/0
softmax                                    0.0      50.2      n/a  0/28
mul                                        0.0      43.8      n/a  0/57
strided_slice                              0.0      43.8      n/a  0/57
concat_channels -> mul -> add              0.0      43.0      n/a  0/56
strided_slice -> mul                       0.0      43.0      n/a  0/56
Slice                                     36.7       0.0     0.00  4/0
Mean Squared Reduce2                      30.2       0.0     0.00  4/0
reshape -> add                             0.0      29.4      n/a  0/28

=== litert-community_Qwen3-0.6B_qwen3_0_6b_mixed_int4_128x256_ctx1024 prefill: ms summed over the turn (256 decode steps / all prefill calls); (n nodes) ===
node type                               cpu ms    gpu ms  gpu/cpu  nodes cpu/gpu
SLICE                                    533.8       0.0     0.00  169/0
Fully Connected GEMM                     237.0       0.0     0.00  11/0
LITERT_METAL                               0.0     110.2      n/a  0/1
PAD                                       77.4       0.0     0.00  55/0
DYNAMIC_UPDATE_SLICE                      72.4       0.0     0.00  112/0
Softmax                                   26.6       0.0     0.00  1/0
Static Reshape                            15.2       0.0     0.00  19/0
Add                                        9.7       0.0     0.00  18/0
Multiply                                   8.4       0.0     0.00  40/0
convolution -> add                         0.0       7.9      n/a  0/54
convolution                                0.0       7.2      n/a  0/137
Batch Matrix Multiply GEMM                 7.0       0.0     0.00  1/0
reshape -> add                             0.0       7.0      n/a  0/27
Slice                                      4.7       0.0     0.00  10/0
convolution -> mul                         0.0       3.9      n/a  0/27
convolution -> sigmoid -> mul              0.0       3.9      n/a  0/27
Sigmoid                                    3.2       0.0     0.00  1/0
weights_convert_uint4_to_float16           0.0       2.9      n/a  0/191
Transpose Transpose                        2.9       0.0     0.00  9/0
Mean Squared Reduce2                       2.7       0.0     0.00  9/0
```

Runtime: https://github.com/google-ai-edge/litert ; engine: https://github.com/google-ai-edge/LiteRT-LM
