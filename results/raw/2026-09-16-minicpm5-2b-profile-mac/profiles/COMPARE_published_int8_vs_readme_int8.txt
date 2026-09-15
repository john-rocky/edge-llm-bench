ctrl decode: run1 72.86 tok/s, run2 112.13 tok/s; prof decode 24.51 / 34.31; steps 256 / 257
op sum ms/step: run1 13.56, run2 9.23
  gemv     run1   6.83 (50.4%)  run2   7.14 (77.4%)
  attn+kv  run1   4.90 (36.1%)  run2   0.90 ( 9.8%)
  other    run1   1.83 (13.5%)  run2   1.19 (12.9%)
node type                                 run1 ms  run2 ms  run1 %  run2 %
dynamic_update_slice                        2.947    0.000   21.7%    0.0%
fc1x1_int8_weights -> add                   2.015    1.915   14.9%   20.7%
fc1x1_int8_weights                          1.650    1.617   12.2%   17.5%
fc1x1_int8_weights -> sigmoid -> m          1.636    1.477   12.1%   16.0%
fc1x1_int8_weights -> mul                   1.530    1.496   11.3%   16.2%
reshape                                     1.243    0.506    9.2%    5.5%
fully_connected                             0.000    0.637    0.0%    6.9%
batched_mat_mul_as_fc                       0.617    0.000    4.5%    0.0%
batched_mat_mul_as_fc -> add -> ma          0.538    0.000    4.0%    0.0%
rms_normalization -> mul                    0.384    0.356    2.8%    3.9%
softmax                                     0.253    0.210    1.9%    2.3%
mul                                         0.175    0.170    1.3%    1.8%
strided_slice                               0.169    0.169    1.2%    1.8%
reshape -> add_values_to_cache              0.000    0.168    0.0%    1.8%
