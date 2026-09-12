# Per-op profile (LiteRT-LM `--enable_profiling`)

Wall ms per decode step from the unprofiled control run; op sums per recorded decode step from the
profiled run, grouped into weight GEMV / attention+KV / transfer / other; "unprof." is the part of
the wall the profiled ops do not cover. A profiled run's rate is never a speed row.

```
tag                                                          be     wall steps op-sum   gemv attn+kv  xfer  other unprof. launch/step
gemma4e2b                                                    cpu    21.0   131   19.7   15.8     3.1   0.0    0.8     1.3        3982
gemma4e2b                                                    gpu    37.0   256   17.7   14.5     0.3   1.1    1.7    19.3        1289
qwen25_1_5b_q8                                               cpu    36.8   256   35.3   22.7    12.3   0.0    0.3     1.5        1644
qwen25_1_5b_q8                                               gpu    48.3   256   33.8   24.8     5.5   2.0    1.5    14.6        1160
qwen3_0_6b                                                   cpu    32.1   225   35.4    8.3    26.7   0.0    0.4    -3.3        2316
qwen3_0_6b                                                   gpu    16.7   256    9.9    7.5     0.6   0.8    1.0     6.8         856
qwen3_0_6b_wi4b32                                            cpu    18.9   218   16.3    5.4    10.5   0.0    0.3     2.6        2388
qwen3_0_6b_wi4b32                                            gpu    18.2   256    9.5    7.0     0.7   0.9    0.9     8.7         795
```

## Readings

- `gemma4e2b` cpu: gemv is 81% of the profiled op time; 1.3 of the 21.0 ms step is outside the profiled ops; 3982 launches per step; profiled run decoded 39.1 tok/s against the control's 47.6 (the gap is the profiler's own cost; never a speed row)
- `gemma4e2b` gpu: gemv is 82% of the profiled op time; 19.3 of the 37.0 ms step is outside the profiled ops; 1289 launches per step; profiled run decoded 13.3 tok/s against the control's 27.0 (the gap is the profiler's own cost; never a speed row)
- `qwen25_1_5b_q8` cpu: gemv is 64% of the profiled op time; 1.5 of the 36.8 ms step is outside the profiled ops; 1644 launches per step; profiled run decoded 27.4 tok/s against the control's 27.2 (the gap is the profiler's own cost; never a speed row)
- `qwen25_1_5b_q8` gpu: gemv is 74% of the profiled op time; 14.6 of the 48.3 ms step is outside the profiled ops; 1160 launches per step; profiled run decoded 10.4 tok/s against the control's 20.7 (the gap is the profiler's own cost; never a speed row)
- `qwen3_0_6b` cpu: attn+kv is 75% of the profiled op time; profiled op time exceeds the 32.1 ms wall by 3.3 ms (profiler cost inside the op times); 2316 launches per step; profiled run decoded 23.7 tok/s against the control's 31.1 (the gap is the profiler's own cost; never a speed row)
- `qwen3_0_6b` gpu: gemv is 76% of the profiled op time; 6.8 of the 16.7 ms step is outside the profiled ops; 856 launches per step; profiled run decoded 26.0 tok/s against the control's 59.8 (the gap is the profiler's own cost; never a speed row)
- `qwen3_0_6b_wi4b32` cpu: attn+kv is 65% of the profiled op time; 2.6 of the 18.9 ms step is outside the profiled ops; 2388 launches per step; profiled run decoded 54.0 tok/s against the control's 52.9 (the gap is the profiler's own cost; never a speed row)
- `qwen3_0_6b_wi4b32` gpu: gemv is 74% of the profiled op time; 8.7 of the 18.2 ms step is outside the profiled ops; 795 launches per step; profiled run decoded 25.8 tok/s against the control's 55.0 (the gap is the profiler's own cost; never a speed row)

## cpu vs gpu per node type: `gemma4e2b`

```
gemma4e2b cpu: nodes 1432; prefill turn (128, 429.148073); decode turn (256, 6552.472341); speeds {'Prefill': 298.27, 'Decode': 39.07}; profiled sum decode 2154 ms, prefill 786 ms
gemma4e2b gpu: nodes 2343; prefill turn (128, 103.275729); decode turn (256, 19215.603378); speeds {'Prefill': 1239.4, 'Decode': 13.32}; profiled sum decode 4532 ms, prefill 48 ms

=== gemma4e2b decode: ms summed over the turn (256 decode steps / all prefill calls); (n nodes) ===
node type                               cpu ms    gpu ms  gpu/cpu  nodes cpu/gpu
Fully Connected GEMM                    1757.7       0.0     0.00  12/0
fc1x1_int4_weights -> quantize_and         0.0    1595.1      n/a  0/145
fc1x1_int2_weights -> quantize_and         0.0    1271.8      n/a  0/60
fc1x1_int2_weights -> mul -> tanh          0.0     408.8      n/a  0/1
Batch Matrix Multiply GEMM               316.7       0.0     0.00  3/0
UploadOrBindTensorBuffer                   0.0     264.7      n/a  0/1
fc1x1_int8_weights -> quantize_and         0.0     234.2      n/a  0/71
fc1x1_int8_weights                         0.0     196.6      n/a  0/70
rms_normalization -> mul -> add            0.0      71.7      n/a  0/70
rms_normalization -> mul -> quanti         0.0      71.7      n/a  0/70
mul -> quantize_and_dequantize             0.0      47.4      n/a  0/35
Convert                                   46.2       0.0     0.00  20/0
mul                                        0.0      45.1      n/a  0/153
reshape -> quantize_and_dequantize         0.0      42.5      n/a  0/71
rms_normalization -> mul                   0.0      39.4      n/a  0/66
rms_normalization -> mul -> add ->         0.0      30.5      n/a  0/36
softmax                                    0.0      30.5      n/a  0/35
strided_slice                              0.0      29.2      n/a  0/100
DownloadGpuMemoryToTensorBufferGpu         0.0      28.2      n/a  0/1
select_v2 -> maximum -> minimum            0.0      20.5      n/a  0/35

=== gemma4e2b prefill: ms summed over the turn (256 decode steps / all prefill calls); (n nodes) ===
node type                               cpu ms    gpu ms  gpu/cpu  nodes cpu/gpu
Fully Connected GEMM                     564.2       0.0     0.00  18/0
Batch Matrix Multiply GEMM                91.3       0.0     0.00  3/0
SLICE                                     50.8       0.0     0.00  200/0
SELECT_V2                                 29.8       0.0     0.00  98/0
convolution_int8 -> dequantize_to_         0.0      14.6      n/a  0/129
DYNAMIC_UPDATE_SLICE                      14.3       0.0     0.00  100/0
weights_convert_uint4_to_int8              0.0      11.5      n/a  0/100
Multiply                                   8.9       0.0     0.00  88/0
UploadOrBindTensorBuffer                   0.0       5.9      n/a  0/1
Convert                                    5.2       0.0     0.00  38/0
FILL                                       4.2       0.0     0.00  40/0
TanH                                       3.4       0.0     0.00  1/0
Softmax                                    3.3       0.0     0.00  1/0
quantize_float16_to_uint8c16               0.0       2.6      n/a  0/129
ApproxGELU                                 2.1       0.0     0.00  2/0
mul                                        0.0       1.5      n/a  0/90
CONCATENATION                              1.3       0.0     0.00  84/0
Add                                        1.3       0.0     0.00  35/0
NOT_EQUAL                                  1.2       0.0     0.00  8/0
reshape -> quantize_and_dequantize         0.0       0.9      n/a  0/59
```

## cpu vs gpu per node type: `qwen25_1_5b_q8`

```
qwen25_1_5b_q8 cpu: nodes 330; prefill turn (128, 701.827084); decode turn (256, 9359.326715); speeds {'Prefill': 182.38, 'Decode': 27.35}; profiled sum decode 9046 ms, prefill 674 ms
qwen25_1_5b_q8 gpu: nodes 2679; prefill turn (128, 317.74099); decode turn (256, 24643.987074); speeds {'Prefill': 402.84, 'Decode': 10.39}; profiled sum decode 8641 ms, prefill 151 ms

=== qwen25_1_5b_q8 decode: ms summed over the turn (256 decode steps / all prefill calls); (n nodes) ===
node type                               cpu ms    gpu ms  gpu/cpu  nodes cpu/gpu
Fully Connected GEMM                    5823.5       0.0     0.00  6/0
Batch Matrix Multiply GEMM              3003.4       0.0     0.00  2/0
fc1x1_int8_weights -> add                  0.0    1873.2      n/a  0/56
fc1x1_int8_weights -> mul                  0.0    1588.2      n/a  0/28
fc1x1_int8_weights -> sigmoid -> m         0.0    1574.9      n/a  0/28
fc1x1_int8_weights                         0.0    1315.3      n/a  0/29
dynamic_update_slice                       0.0     791.8      n/a  0/56
UploadOrBindTensorBuffer                   0.0     488.4      n/a  0/1
batched_mat_mul_as_fc                      0.0     466.4      n/a  0/56
reshape                                    0.0     139.3      n/a  0/224
strided_slice                              0.0      70.4      n/a  0/196
DYNAMIC_UPDATE_SLICE                      67.1       0.0     0.00  56/0
Softmax                                   64.5       0.0     0.00  1/0
rms_normalization -> mul                   0.0      58.4      n/a  0/57
mul                                        0.0      55.6      n/a  0/169
reshape -> maximum -> minimum              0.0      50.2      n/a  0/28
softmax                                    0.0      44.8      n/a  0/28
reshape -> add                             0.0      37.1      n/a  0/28
Add                                       28.7       0.0     0.00  10/0
Sigmoid                                   28.7       0.0     0.00  1/0

=== qwen25_1_5b_q8 prefill: ms summed over the turn (256 decode steps / all prefill calls); (n nodes) ===
node type                               cpu ms    gpu ms  gpu/cpu  nodes cpu/gpu
Fully Connected GEMM                     399.0       0.0     0.00  6/0
Batch Matrix Multiply GEMM               182.5       0.0     0.00  2/0
weights_convert_uint8_to_int8              0.0      38.3      n/a  0/136
Softmax                                   31.1       0.0     0.00  1/0
convolution_int8 -> dequantize_to_         0.0      31.1      n/a  0/136
Add                                       27.4       0.0     0.00  11/0
mat_mul_as_convolution                     0.0      20.2      n/a  0/54
softmax                                    0.0      15.6      n/a  0/27
Multiply                                  13.3       0.0     0.00  29/0
reshape -> add                             0.0      10.0      n/a  0/27
reshape -> maximum -> minimum              0.0       9.8      n/a  0/27
Sigmoid                                    7.4       0.0     0.00  1/0
UploadOrBindTensorBuffer                   0.0       6.1      n/a  0/1
transpose                                  0.0       5.2      n/a  0/110
quantize_float16_to_uint8c16               0.0       4.1      n/a  0/136
EMBEDDING_LOOKUP                           4.0       0.0     0.00  1/0
dynamic_update_slice                       0.0       3.1      n/a  0/56
bhwc_as_hwio_float16_to_kOSpatialI         0.0       2.8      n/a  0/54
Slice                                      2.6       0.0     0.00  16/0
Transpose Transpose                        2.0       0.0     0.00  9/0
```

## cpu vs gpu per node type: `qwen3_0_6b`

```
qwen3_0_6b cpu: nodes 1327; prefill turn (128, 1044.74901); decode turn (256, 10798.062184); speeds {'Prefill': 122.52, 'Decode': 23.71}; profiled sum decode 2960 ms, prefill 5851 ms
qwen3_0_6b gpu: nodes 2022; prefill turn (128, 261.624635); decode turn (256, 9842.750048); speeds {'Prefill': 489.25, 'Decode': 26.01}; profiled sum decode 2529 ms, prefill 130 ms

=== qwen3_0_6b decode: ms summed over the turn (256 decode steps / all prefill calls); (n nodes) ===
node type                               cpu ms    gpu ms  gpu/cpu  nodes cpu/gpu
Fully Connected GEMM                    1856.1       0.0     0.00  7/0
Batch Matrix Multiply GEMM              1016.1       0.0     0.00  1/0
fc1x1_int4_weights                         0.0     762.4      n/a  0/85
fc1x1_int4_weights -> add                  0.0     484.1      n/a  0/56
fc1x1_int4_weights -> mul                  0.0     248.1      n/a  0/28
fc1x1_int4_weights -> sigmoid -> m         0.0     242.9      n/a  0/28
UploadOrBindTensorBuffer                   0.0     193.0      n/a  0/1
fully_connected                            0.0     190.7      n/a  0/56
rms_normalization -> mul                   0.0      73.5      n/a  0/113
softmax                                    0.0      48.4      n/a  0/28
reshape                                    0.0      46.6      n/a  0/85
Softmax                                   43.9       0.0     0.00  1/0
reshape -> add                             0.0      37.6      n/a  0/28
concat_channels -> mul -> add              0.0      31.0      n/a  0/56
mul                                        0.0      28.9      n/a  0/57
strided_slice                              0.0      23.6      n/a  0/57
add_values_to_cache                        0.0      22.0      n/a  0/28
strided_slice -> mul                       0.0      21.5      n/a  0/56
reshape -> maximum -> minimum              0.0      21.5      n/a  0/28
Static Reshape                            19.3       0.0     0.00  9/0

=== qwen3_0_6b prefill: ms summed over the turn (256 decode steps / all prefill calls); (n nodes) ===
node type                               cpu ms    gpu ms  gpu/cpu  nodes cpu/gpu
SLICE                                   4579.0       0.0     0.00  169/0
DYNAMIC_UPDATE_SLICE                     399.3       0.0     0.00  112/0
Fully Connected GEMM                     386.2       0.0     0.00  11/0
PAD                                      247.9       0.0     0.00  55/0
Static Reshape                            79.4       0.0     0.00  19/0
Softmax                                   56.4       0.0     0.00  1/0
Add                                       38.2       0.0     0.00  18/0
Batch Matrix Multiply GEMM                24.1       0.0     0.00  1/0
softmax                                    0.0      20.9      n/a  0/54
weights_convert_uint4_to_float16           0.0      18.6      n/a  0/191
convolution -> add                         0.0      15.0      n/a  0/54
convolution                                0.0      14.1      n/a  0/137
reshape -> add                             0.0      13.4      n/a  0/27
reshape -> maximum -> minimum              0.0      13.1      n/a  0/27
Multiply                                  11.0       0.0     0.00  40/0
convolution -> mul                         0.0       8.0      n/a  0/27
convolution -> sigmoid -> mul              0.0       7.8      n/a  0/27
Transpose Transpose                        6.1       0.0     0.00  9/0
Sigmoid                                    6.0       0.0     0.00  1/0
UploadOrBindTensorBuffer                   0.0       5.9      n/a  0/1
```

## cpu vs gpu per node type: `qwen3_0_6b_wi4b32`

```
qwen3_0_6b_wi4b32 cpu: nodes 1257; prefill turn (128, 394.156562); decode turn (256, 4738.287862); speeds {'Prefill': 324.74, 'Decode': 54.03}; profiled sum decode 3393 ms, prefill 449 ms
qwen3_0_6b_wi4b32 gpu: nodes 1737; prefill turn (128, 136.640468); decode turn (256, 9923.984892); speeds {'Prefill': 936.76, 'Decode': 25.8}; profiled sum decode 2430 ms, prefill 66 ms

=== qwen3_0_6b_wi4b32 decode: ms summed over the turn (256 decode steps / all prefill calls); (n nodes) ===
node type                               cpu ms    gpu ms  gpu/cpu  nodes cpu/gpu
Batch Matrix Multiply GEMM              2164.8       0.0     0.00  2/0
Fully Connected GEMM                    1167.6       0.0     0.00  4/0
fc1x1_int4_weights                         0.0    1158.1      n/a  0/57
fc1x1_int4_weights -> add                  0.0     459.5      n/a  0/56
UploadOrBindTensorBuffer                   0.0     203.5      n/a  0/1
fully_connected                            0.0     186.1      n/a  0/56
reshape                                    0.0     104.4      n/a  0/197
rms_normalization -> mul                   0.0      72.4      n/a  0/113
strided_slice                              0.0      57.3      n/a  0/112
softmax                                    0.0      35.8      n/a  0/28
select_v2 -> maximum -> minimum            0.0      32.0      n/a  0/28
SplitRoPEConcat                            0.0      21.5      n/a  0/28
SplitRoPEConcat -> mul                     0.0      21.5      n/a  0/28
mul                                        0.0      21.5      n/a  0/28
add_values_to_cache                        0.0      20.2      n/a  0/28
Add                                       18.2       0.0     0.00  12/0
Softmax                                   18.2       0.0     0.00  1/0
DownloadGpuMemoryToTensorBufferGpu         0.0      16.9      n/a  0/1
strided_slice -> sigmoid -> mul            0.0      14.3      n/a  0/28
Slice                                     11.7       0.0     0.00  9/0

=== qwen3_0_6b_wi4b32 prefill: ms summed over the turn (256 decode steps / all prefill calls); (n nodes) ===
node type                               cpu ms    gpu ms  gpu/cpu  nodes cpu/gpu
Fully Connected GEMM                     179.2       0.0     0.00  6/0
DYNAMIC_UPDATE_SLICE                     104.8       0.0     0.00  112/0
SELECT_V2                                 58.5       0.0     0.00  55/0
Batch Matrix Multiply GEMM                56.2       0.0     0.00  2/0
weights_convert_uint4_to_float16           0.0      18.7      n/a  0/109
convolution                                0.0      15.6      n/a  0/109
Softmax                                   12.9       0.0     0.00  1/0
Add                                       11.3       0.0     0.00  26/0
convolution -> add                         0.0       9.5      n/a  0/54
UploadOrBindTensorBuffer                   0.0       5.8      n/a  0/1
Slice                                      5.8       0.0     0.00  22/0
Transpose Transpose                        4.8       0.0     0.00  19/0
Multiply                                   4.7       0.0     0.00  148/0
softmax                                    0.0       3.9      n/a  0/27
Static Reshape                             3.7       0.0     0.00  134/0
select_v2 -> maximum -> minimum            0.0       3.2      n/a  0/27
Sigmoid                                    2.5       0.0     0.00  1/0
rms_normalization -> mul                   0.0       2.4      n/a  0/110
strided_slice                              0.0       1.0      n/a  0/111
Copy                                       1.0       0.0     0.00  8/0
```

Runtime: https://github.com/google-ai-edge/litert ; engine: https://github.com/google-ai-edge/LiteRT-LM
