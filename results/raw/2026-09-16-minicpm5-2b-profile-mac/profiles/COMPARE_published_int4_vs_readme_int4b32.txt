ctrl decode: run1 89.69 tok/s, run2 142.52 tok/s; prof decode 28.98 / 39.67; steps 256 / 257
op sum ms/step: run1 10.76, run2 7.27
  gemv     run1   4.85 (45.1%)  run2   5.19 (71.3%)
  attn+kv  run1   4.20 (39.1%)  run2   0.90 (12.4%)
  other    run1   1.71 (15.9%)  run2   1.18 (16.3%)
node type                                 run1 ms  run2 ms  run1 %  run2 %
dynamic_update_slice                        2.613    0.000   24.3%    0.0%
fc1x1_int4_weights -> add                   1.405    1.355   13.1%   18.6%
fc1x1_int4_weights                          1.390    1.363   12.9%   18.7%
reshape                                     1.165    0.506   10.8%    7.0%
fc1x1_int4_weights -> sigmoid -> m          1.122    0.918   10.4%   12.6%
fc1x1_int4_weights -> mul                   0.931    0.917    8.7%   12.6%
fully_connected                             0.000    0.634    0.0%    8.7%
batched_mat_mul_as_fc                       0.436    0.000    4.1%    0.0%
batched_mat_mul_as_fc -> add -> ma          0.374    0.000    3.5%    0.0%
rms_normalization -> mul                    0.341    0.350    3.2%    4.8%
softmax                                     0.252    0.210    2.3%    2.9%
mul                                         0.170    0.171    1.6%    2.4%
reshape -> add_values_to_cache              0.000    0.169    0.0%    2.3%
strided_slice                               0.168    0.168    1.6%    2.3%
