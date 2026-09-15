control decode 142.52 tok/s (wall 7.02 ms/step); profiled decode 39.67 tok/s; recorded steps 257; profiled op sum 7.27 ms/step; container {'LITERT_METAL': 23.58}
groups (ms/step, share of op sum): gemv 5.19 (71%), attn+kv 0.90 (12%), other 1.18 (16%)
node type                                 ms/step  share  group   nodes
fc1x1_int4_weights                          1.363  18.7%  gemv    127
fc1x1_int4_weights -> add                   1.355  18.6%  gemv    84
fc1x1_int4_weights -> sigmoid -> m          0.918  12.6%  gemv    42
fc1x1_int4_weights -> mul                   0.917  12.6%  gemv    42
fully_connected                             0.634   8.7%  gemv    84
reshape                                     0.506   7.0%  other   169
rms_normalization -> mul                    0.350   4.8%  other   85
softmax                                     0.210   2.9%  attn+kv 42
mul                                         0.171   2.4%  other   85
reshape -> add_values_to_cache              0.169   2.3%  attn+kv 42
strided_slice                               0.168   2.3%  attn+kv 84
strided_slice -> mul                        0.168   2.3%  attn+kv 84
select_v2 -> maximum -> minimum             0.126   1.7%  other   42
concat_channels -> mul -> add -> m          0.089   1.2%  attn+kv 42
concat_channels -> mul -> add               0.084   1.2%  attn+kv 42
copy                                        0.016   0.2%  other   8
concat_batch                                0.010   0.1%  attn+kv 2
embedding_lookup                            0.006   0.1%  other   1
cast                                        0.004   0.1%  other   2
concat_height -> not_equal                  0.004   0.1%  attn+kv 1
concat_channels                             0.002   0.0%  attn+kv 1
cos                                         0.002   0.0%  other   1
sin                                         0.002   0.0%  other   1
