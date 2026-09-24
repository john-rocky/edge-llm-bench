# Per-cell decode spread

First-ever is separate. n=1 cannot establish repeatability. Min/max rounds identify the extrema, not a causal diagnosis. No rounds are automatically discarded.

| arm | model | file | allocation | regime | n | (max-min)/median % | above 10% | min rounds | max rounds |
|---|---|---|---|---|---|---|---|---|---|
| litert-lm-gpu | litert-community/gemma-4-E2B-it-litert-lm | litert-community_gemma-4-E2B-it-litert-lm_gemma-4-E2B-it.litertlm | 2304 | cold | 6 | 13.432551039877886 | True | [2] | [3] |
| litert-lm-gpu | litert-community/gemma-4-E2B-it-litert-lm | litert-community_gemma-4-E2B-it-litert-lm_gemma-4-E2B-it.litertlm | 2304 | warm | 6 | 5.703349282296645 | False | [2] | [4] |
| litert-lm-gpu | litert-community/gemma-4-E2B-it-litert-lm | litert-community_gemma-4-E2B-it-litert-lm_gemma-4-E2B-it.litertlm | 4096 | cold | 6 | 6.615006615006615 | False | [2] | [1] |
| litert-lm-gpu | litert-community/gemma-4-E2B-it-litert-lm | litert-community_gemma-4-E2B-it-litert-lm_gemma-4-E2B-it.litertlm | 4096 | warm | 6 | 15.588290136117845 | True | [2] | [5] |
| litert-lm-gpu | litert-community/gemma-4-E2B-it-litert-lm | litert-community_gemma-4-E2B-it-litert-lm_gemma-4-E2B-it.litertlm | 8192 | cold | 6 | 23.92961876832845 | True | [2] | [6] |
| litert-lm-gpu | litert-community/gemma-4-E2B-it-litert-lm | litert-community_gemma-4-E2B-it-litert-lm_gemma-4-E2B-it.litertlm | 8192 | warm | 6 | 3.4963661363189966 | False | [4] | [6] |
| litert-lm-gpu | litert-community/gemma-4-E4B-it-litert-lm | litert-community_gemma-4-E4B-it-litert-lm_gemma-4-E4B-it.litertlm | 2304 | cold | 6 | 11.914323962516729 | True | [5] | [1] |
| litert-lm-gpu | litert-community/gemma-4-E4B-it-litert-lm | litert-community_gemma-4-E4B-it-litert-lm_gemma-4-E4B-it.litertlm | 2304 | warm | 6 | 6.1724253606172415 | False | [3] | [2] |
| litert-lm-gpu | litert-community/gemma-4-E4B-it-litert-lm | litert-community_gemma-4-E4B-it-litert-lm_gemma-4-E4B-it.litertlm | 4096 | cold | 6 | 9.283276450511941 | False | [5] | [6] |
| litert-lm-gpu | litert-community/gemma-4-E4B-it-litert-lm | litert-community_gemma-4-E4B-it-litert-lm_gemma-4-E4B-it.litertlm | 4096 | warm | 6 | 4.32871153195807 | False | [1] | [2] |
| litert-lm-gpu | litert-community/gemma-4-E4B-it-litert-lm | litert-community_gemma-4-E4B-it-litert-lm_gemma-4-E4B-it.litertlm | 8192 | cold | 6 | 6.184118060435704 | False | [5] | [1] |
| litert-lm-gpu | litert-community/gemma-4-E4B-it-litert-lm | litert-community_gemma-4-E4B-it-litert-lm_gemma-4-E4B-it.litertlm | 8192 | warm | 6 | 5.534417156693179 | False | [2] | [1] |
