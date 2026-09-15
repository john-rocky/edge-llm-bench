control decode 112.13 tok/s (wall 8.92 ms/step); profiled decode 34.31 tok/s; recorded steps 257; profiled op sum 9.23 ms/step; container {'LITERT_METAL': 27.39}
groups (ms/step, share of op sum): gemv 7.14 (77%), attn+kv 0.90 (10%), other 1.19 (13%)
node type                                 ms/step  share  group   nodes
fc1x1_int8_weights -> add                   1.915  20.7%  gemv    84
fc1x1_int8_weights                          1.617  17.5%  gemv    127
fc1x1_int8_weights -> mul                   1.496  16.2%  gemv    42
fc1x1_int8_weights -> sigmoid -> m          1.477  16.0%  gemv    42
fully_connected                             0.637   6.9%  gemv    84
reshape                                     0.506   5.5%  other   169
rms_normalization -> mul                    0.356   3.9%  other   85
softmax                                     0.210   2.3%  attn+kv 42
mul                                         0.170   1.8%  other   85
strided_slice                               0.169   1.8%  attn+kv 84
strided_slice -> mul                        0.168   1.8%  attn+kv 84
reshape -> add_values_to_cache              0.168   1.8%  attn+kv 42
select_v2 -> maximum -> minimum             0.126   1.4%  other   42
concat_channels -> mul -> add -> m          0.087   0.9%  attn+kv 42
concat_channels -> mul -> add               0.084   0.9%  attn+kv 42
copy                                        0.016   0.2%  other   8
concat_batch                                0.010   0.1%  attn+kv 2
embedding_lookup                            0.005   0.1%  other   1
cast                                        0.005   0.1%  other   2
concat_height -> not_equal                  0.004   0.0%  attn+kv 1
concat_channels                             0.003   0.0%  attn+kv 1
cos                                         0.002   0.0%  other   1
sin                                         0.002   0.0%  other   1
