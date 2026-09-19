# Per-op profile (LiteRT-LM `--enable_profiling`)

Wall ms per decode step from the unprofiled control run; op sums per recorded decode step from the
profiled run, grouped into weight GEMV / attention+KV / transfer / other; "unprof." is the part of
the wall the profiled ops do not cover. A profiled run's rate is never a speed row.

```
tag                                                          be     wall steps op-sum   gemv attn+kv  xfer  other unprof. launch/step
…-community_Qwen3-0.6B_qwen3_0_6b_mixed_int4_128x256_ctx1024 cpu    61.3   225   54.8   17.1    36.4   0.0    1.2     6.5        2316
…-community_Qwen3-0.6B_qwen3_0_6b_mixed_int4_128x256_ctx1024 gpu    65.1   256   48.3   31.3     4.6   4.5    7.8    16.8         856
```

## Readings

- `litert-community_Qwen3-0.6B_qwen3_0_6b_mixed_int4_128x256_ctx1024` cpu: attn+kv is 66% of the profiled op time; 6.5 of the 61.3 ms step is outside the profiled ops; 2316 launches per step; profiled run decoded 15.4 tok/s against the control's 16.3 (the gap is the profiler's own cost; never a speed row)
- `litert-community_Qwen3-0.6B_qwen3_0_6b_mixed_int4_128x256_ctx1024` gpu: gemv is 65% of the profiled op time; 16.8 of the 65.1 ms step is outside the profiled ops; 856 launches per step; profiled run decoded 5.8 tok/s against the control's 15.4 (the gap is the profiler's own cost; never a speed row)

## cpu vs gpu per node type: `litert-community_Qwen3-0.6B_qwen3_0_6b_mixed_int4_128x256_ctx1024`

```
litert-community_Qwen3-0.6B_qwen3_0_6b_mixed_int4_128x256_ctx1024 cpu: nodes 1327; prefill turn (128, 1996.850749); decode turn (256, 16653.891406); speeds {'Prefill': 64.1, 'Decode': 15.37}; profiled sum decode 5703 ms, prefill 8413 ms
litert-community_Qwen3-0.6B_qwen3_0_6b_mixed_int4_128x256_ctx1024 gpu: nodes 2022; prefill turn (128, 943.018108); decode turn (256, 44209.077862); speeds {'Prefill': 135.73, 'Decode': 5.79}; profiled sum decode 12353 ms, prefill 479 ms

=== litert-community_Qwen3-0.6B_qwen3_0_6b_mixed_int4_128x256_ctx1024 decode: ms summed over the turn (256 decode steps / all prefill calls); (n nodes) ===
node type                               cpu ms    gpu ms  gpu/cpu  nodes cpu/gpu
Fully Connected GEMM                    3816.5       0.0     0.00  7/0
fc1x1_int4_weights                         0.0    3027.7      n/a  0/85
fc1x1_int4_weights -> add                  0.0    1953.5      n/a  0/56
Batch Matrix Multiply GEMM              1480.3       0.0     0.00  1/0
fc1x1_int4_weights -> sigmoid -> m         0.0    1128.7      n/a  0/28
fc1x1_int4_weights -> mul                  0.0    1090.3      n/a  0/28
UploadOrBindTensorBuffer                   0.0     979.2      n/a  0/1
fully_connected                            0.0     821.8      n/a  0/56
rms_normalization -> mul                   0.0     625.2      n/a  0/113
softmax                                    0.0     527.9      n/a  0/28
reshape                                    0.0     447.5      n/a  0/85
reshape -> maximum -> minimum              0.0     233.0      n/a  0/28
reshape -> add                             0.0     211.7      n/a  0/28
mul                                        0.0     198.9      n/a  0/57
concat_channels -> mul -> add              0.0     191.7      n/a  0/56
add_values_to_cache                        0.0     178.7      n/a  0/28
Softmax                                  175.6       0.0     0.00  1/0
DownloadGpuMemoryToTensorBufferGpu         0.0     175.6      n/a  0/1
strided_slice -> mul                       0.0     141.6      n/a  0/56
reshape -> transpose -> reshape            0.0     130.3      n/a  0/28

=== litert-community_Qwen3-0.6B_qwen3_0_6b_mixed_int4_128x256_ctx1024 prefill: ms summed over the turn (256 decode steps / all prefill calls); (n nodes) ===
node type                               cpu ms    gpu ms  gpu/cpu  nodes cpu/gpu
SLICE                                   5977.3       0.0     0.00  169/0
Fully Connected GEMM                     985.0       0.0     0.00  11/0
DYNAMIC_UPDATE_SLICE                     543.9       0.0     0.00  112/0
PAD                                      339.4       0.0     0.00  55/0
Softmax                                  146.0       0.0     0.00  1/0
Static Reshape                           131.8       0.0     0.00  19/0
Batch Matrix Multiply GEMM               109.2       0.0     0.00  1/0
convolution -> add                         0.0     100.7      n/a  0/54
convolution                                0.0      89.6      n/a  0/137
Add                                       55.7       0.0     0.00  18/0
softmax                                    0.0      48.6      n/a  0/54
reshape -> maximum -> minimum              0.0      45.5      n/a  0/27
convolution -> mul                         0.0      45.0      n/a  0/27
convolution -> sigmoid -> mul              0.0      42.4      n/a  0/27
reshape -> add                             0.0      31.1      n/a  0/27
weights_convert_uint4_to_float16           0.0      29.3      n/a  0/191
Multiply                                  27.7       0.0     0.00  40/0
CONCATENATION                             19.6       0.0     0.00  224/0
Sigmoid                                   17.3       0.0     0.00  1/0
Transpose Transpose                       12.8       0.0     0.00  9/0
```

Runtime: https://github.com/google-ai-edge/litert ; engine: https://github.com/google-ai-edge/LiteRT-LM
