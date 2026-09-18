# 2026-09-18-dashboard-longctx-v1-m4max-mac — long-context-2048-gen256, regime cold (median [min–max] over rounds)

| arm | model | ctx | prompt tok | out tok (short stops) | prefill tok/s | TTFT ms | decode tok/s | Δ decode vs smallest ctx | peak thermal |
|---|---|---:|---:|---|---|---|---|---:|---|
| litert-lm | litert-community/Qwen3-0.6B/dynamic_wi4b32_afp32 | 2304 | 1986 | 256 [256–256] n=8 (0) | 7091.9 [6535.9–7641.3] n=8 | 338 [307–351] n=8 | 291.3 [289.4–293.3] n=8 | +0.0% | nominal |
| litert-lm | litert-community/Qwen3-0.6B/dynamic_wi4b32_afp32 | 4096 | 1986 | 256 [256–256] n=8 (0) | 5768.4 [5682.9–6526.1] n=8 | 390 [350–396] n=8 | 284.4 [282.9–286.8] n=8 | -2.4% | nominal |
| litert-lm | litert-community/Qwen3-0.6B/dynamic_wi4b32_afp32 | 8192 | 1986 | 256 [256–256] n=8 (0) | 4597.5 [4353.3–4816.3] n=8 | 484 [460–503] n=8 | 238.1 [236.7–241.0] n=8 | -18.3% | nominal |
| litert-lm | litert-community/Qwen3-1.7B | 2304 | 1986 | 256 [256–256] n=8 (0) | 3375.6 [3074.0–3702.0] n=8 | 642 [585–696] n=8 | 204.8 [202.3–207.0] n=8 | +0.0% | nominal |
| litert-lm | litert-community/Qwen3-1.7B | 4096 | 1986 | 256 [256–256] n=8 (0) | 3113.6 [2868.3–3414.6] n=8 | 693 [630–742] n=8 | 202.6 [201.9–203.9] n=8 | -1.0% | nominal |
| litert-lm | litert-community/Qwen3-1.7B | 8192 | 1986 | 256 [256–256] n=8 (0) | 2679.6 [2483.2–2888.1] n=8 | 798 [741–854] n=8 | 177.8 [176.6–179.0] n=8 | -13.2% | nominal |
| litert-lm | litert-community/gemma-4-E2B-it-litert-lm | 2304 | 1637 | 77 [77–77] n=8 (8) | 6664.1 [6046.7–6736.6] n=8 | 266 [263–447] n=8 | 151.8 [116.1–153.1] n=8 | +0.0% | nominal |
| litert-lm | litert-community/gemma-4-E2B-it-litert-lm | 4096 | 1637 | 256 [256–256] n=8 (0) | 6248.3 [5766.2–6292.4] n=8 | 283 [280–463] n=8 | 153.2 [143.0–155.4] n=8 | +0.9% | nominal |
| litert-lm | litert-community/gemma-4-E2B-it-litert-lm | 8192 | 1637 | 93 [93–93] n=8 (8) | 5417.7 [3265.6–5474.4] n=8 | 323 [320–679] n=8 | 134.0 [102.8–136.1] n=8 | -11.7% | nominal |
| litert-lm | litert-community/gemma-4-E4B-it-litert-lm | 2304 | 1637 | 256 [256–256] n=8 (0) | 2061.4 [1871.1–2078.7] n=8 | 816 [808–1250] n=8 | 96.4 [94.9–97.2] n=8 | +0.0% | nominal |
| litert-lm | litert-community/gemma-4-E4B-it-litert-lm | 4096 | 1637 | 256 [256–256] n=8 (0) | 1980.0 [1821.8–1991.7] n=8 | 849 [843–1272] n=8 | 96.5 [96.1–97.2] n=8 | +0.2% | nominal |
| litert-lm | litert-community/gemma-4-E4B-it-litert-lm | 8192 | 1637 | 256 [256–256] n=8 (0) | 1813.6 [1695.5–1823.9] n=8 | 926 [921–1326] n=8 | 88.2 [71.7–88.9] n=8 | -8.5% | nominal |
| litert-lm-cpu | litert-community/Qwen3-0.6B/dynamic_wi4b32_afp32 | 2304 | 1986 | 256 [256–256] n=8 (0) | 511.6 [479.5–513.1] n=8 | 4027 [4014–4323] n=8 | 45.0 [43.9–45.9] n=8 | +0.0% | nominal |
| litert-lm-cpu | litert-community/Qwen3-0.6B/dynamic_wi4b32_afp32 | 4096 | 1986 | 256 [256–256] n=8 (0) | 388.0 [386.4–389.0] n=8 | 5287 [5270–5311] n=8 | 33.9 [33.2–34.8] n=8 | -24.5% | nominal |
| litert-lm-cpu | litert-community/Qwen3-0.6B/dynamic_wi4b32_afp32 | 8192 | 1986 | 256 [256–256] n=8 (0) | 252.6 [242.7–256.6] n=8 | 8106 [7979–8465] n=8 | 18.1 [17.8–18.8] n=8 | -59.8% | nominal |
| litert-lm-cpu | litert-community/Qwen3-1.7B/int8 | 2304 | 1986 | 256 [256–256] n=8 (0) | 563.9 [479.2–579.9] n=8 | 3594 [3495–4342] n=8 | 28.7 [28.4–33.2] n=8 | +0.0% | nominal |
| litert-lm-cpu | litert-community/Qwen3-1.7B/int8 | 4096 | 1986 | 256 [256–256] n=8 (0) | 564.3 [559.9–604.4] n=8 | 3590 [3358–3621] n=8 | 28.5 [28.2–29.8] n=8 | -0.7% | nominal |
| litert-lm-cpu | litert-community/Qwen3-1.7B/int8 | 8192 | 1986 | 256 [256–256] n=8 (0) | 528.2 [479.2–575.6] n=8 | 3920 [3521–4338] n=8 | 28.6 [28.2–28.9] n=8 | -0.3% | nominal |
| litert-lm-cpu | litert-community/gemma-4-E2B-it-litert-lm | 2304 | 1637 | 256 [256–256] n=8 (0) | 637.8 [568.6–663.3] n=8 | 2683 [2521–3134] n=8 | 50.5 [48.8–51.6] n=8 | +0.0% | nominal |
| litert-lm-cpu | litert-community/gemma-4-E2B-it-litert-lm | 4096 | 1637 | 256 [256–256] n=8 (0) | 555.2 [552.7–560.4] n=8 | 3018 [2990–3032] n=8 | 46.6 [46.3–46.9] n=8 | -7.8% | nominal |
| litert-lm-cpu | litert-community/gemma-4-E2B-it-litert-lm | 8192 | 1637 | 256 [256–256] n=8 (0) | 413.5 [399.6–415.7] n=8 | 4098 [4076–4432] n=8 | 39.2 [39.1–39.3] n=8 | -22.5% | nominal |
| litert-lm-cpu | litert-community/gemma-4-E4B-it-litert-lm | 2304 | 1637 | 256 [256–256] n=8 (0) | 234.3 [216.1–237.0] n=8 | 7075 [6997–8056] n=8 | 33.4 [32.5–33.5] n=8 | +0.0% | nominal |
| litert-lm-cpu | litert-community/gemma-4-E4B-it-litert-lm | 4096 | 1637 | 256 [256–256] n=8 (0) | 211.4 [210.3–213.9] n=8 | 7864 [7772–7904] n=8 | 31.2 [31.0–31.3] n=8 | -6.4% | nominal |
| litert-lm-cpu | litert-community/gemma-4-E4B-it-litert-lm | 8192 | 1637 | 256 [256–256] n=8 (0) | 175.5 [173.9–177.7] n=8 | 9584 [9465–9675] n=8 | 26.5 [26.4–26.5] n=8 | -20.6% | nominal |
| llama.cpp | unsloth/Qwen3-0.6B-GGUF/Q4_K_M | 2304 | 1986 | 256 [256–256] n=8 (0) | 11591.7 [11506.8–11734.6] n=8 | 235 [233–236] n=8 | 305.1 [299.0–321.2] n=8 | +0.0% | nominal |
| llama.cpp | unsloth/Qwen3-0.6B-GGUF/Q4_K_M | 4096 | 1986 | 256 [256–256] n=8 (0) | 11609.3 [11382.7–11732.3] n=8 | 236 [233–240] n=8 | 305.9 [300.3–309.7] n=8 | +0.3% | nominal |
| llama.cpp | unsloth/Qwen3-0.6B-GGUF/Q4_K_M | 8192 | 1986 | 256 [256–256] n=8 (0) | 11533.3 [11387.2–11730.7] n=8 | 240 [235–241] n=8 | 301.2 [299.1–310.3] n=8 | -1.3% | nominal |
| llama.cpp | unsloth/Qwen3-1.7B-GGUF/Q4_K_M | 2304 | 1986 | 256 [256–256] n=8 (0) | 4982.0 [4944.0–4999.4] n=8 | 532 [531–536] n=8 | 193.7 [190.8–197.6] n=8 | +0.0% | nominal |
| llama.cpp | unsloth/Qwen3-1.7B-GGUF/Q4_K_M | 4096 | 1986 | 256 [256–256] n=8 (0) | 4976.5 [4951.1–4988.9] n=8 | 533 [532–536] n=8 | 194.8 [190.8–197.3] n=8 | +0.6% | nominal |
| llama.cpp | unsloth/Qwen3-1.7B-GGUF/Q4_K_M | 8192 | 1986 | 256 [256–256] n=8 (0) | 4980.8 [4853.0–5027.0] n=8 | 534 [531–546] n=8 | 194.1 [190.8–198.0] n=8 | +0.2% | nominal |
| llama.cpp | unsloth/Qwen3-4B-GGUF/Q4_K_M | 2304 | 1986 | 256 [256–256] n=8 (0) | 2009.5 [1962.4–2019.0] n=8 | 1329 [1323–1360] n=8 | 103.6 [102.9–104.7] n=8 | +0.0% | nominal |
| llama.cpp | unsloth/Qwen3-4B-GGUF/Q4_K_M | 4096 | 1986 | 256 [256–256] n=8 (0) | 2017.6 [2000.5–2020.7] n=8 | 1325 [1323–1336] n=8 | 103.6 [102.0–105.0] n=8 | -0.1% | nominal |
| llama.cpp | unsloth/Qwen3-4B-GGUF/Q4_K_M | 8192 | 1986 | 256 [256–256] n=8 (0) | 2013.5 [2002.7–2021.2] n=8 | 1329 [1325–1336] n=8 | 103.9 [102.6–104.9] n=8 | +0.3% | nominal |
| llama.cpp | unsloth/gemma-4-E2B-it-GGUF/Q4_K_M | 2304 | 1629 | 256 [256–256] n=8 (0) | 2986.3 [1353.3–2998.1] n=8 | 602 [600–1258] n=8 | 137.9 [131.5–141.1] n=8 | +0.0% | nominal |
| llama.cpp | unsloth/gemma-4-E2B-it-GGUF/Q4_K_M | 4096 | 1629 | 256 [256–256] n=8 (0) | 2992.1 [2952.9–3009.4] n=8 | 602 [598–608] n=8 | 136.0 [134.4–140.8] n=8 | -1.4% | nominal |
| llama.cpp | unsloth/gemma-4-E2B-it-GGUF/Q4_K_M | 8192 | 1629 | 256 [256–256] n=8 (0) | 2974.1 [2948.6–3001.1] n=8 | 606 [599–609] n=8 | 137.6 [136.4–140.3] n=8 | -0.3% | nominal |
| llama.cpp | unsloth/gemma-4-E4B-it-GGUF/Q4_K_M | 2304 | 1629 | 256 [256–256] n=8 (0) | 1533.7 [1078.2–1544.2] n=8 | 1156 [1149–1605] n=8 | 86.1 [84.7–88.0] n=8 | +0.0% | nominal |
| llama.cpp | unsloth/gemma-4-E4B-it-GGUF/Q4_K_M | 4096 | 1629 | 256 [256–256] n=8 (0) | 1538.9 [1530.3–1546.1] n=8 | 1154 [1148–1160] n=8 | 87.2 [86.4–89.5] n=8 | +1.3% | nominal |
| llama.cpp | unsloth/gemma-4-E4B-it-GGUF/Q4_K_M | 8192 | 1629 | 256 [256–256] n=8 (0) | 1540.0 [1532.9–1546.4] n=8 | 1153 [1149–1158] n=8 | 87.1 [85.5–88.3] n=8 | +1.1% | nominal |

csv: results/raw/2026-09-18-dashboard-longctx-v1-m4max-mac/ladder-cold.csv
