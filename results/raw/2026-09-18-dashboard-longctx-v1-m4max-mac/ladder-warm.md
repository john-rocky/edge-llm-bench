# 2026-09-18-dashboard-longctx-v1-m4max-mac — long-context-2048-gen256, regime warm (median [min–max] over rounds)

| arm | model | ctx | prompt tok | out tok (short stops) | prefill tok/s | TTFT ms | decode tok/s | Δ decode vs smallest ctx | peak thermal |
|---|---|---:|---:|---|---|---|---|---:|---|
| litert-lm | litert-community/Qwen3-0.6B/dynamic_wi4b32_afp32 | 2304 | 1986 | 256 [256–256] n=8 (0) | 7696.8 [7581.8–7838.4] n=8 | 293 [285–301] n=8 | 290.4 [289.1–294.0] n=8 | +0.0% | nominal |
| litert-lm | litert-community/Qwen3-0.6B/dynamic_wi4b32_afp32 | 4096 | 1986 | 256 [256–256] n=8 (0) | 6557.8 [6469.4–6659.4] n=8 | 340 [328–343] n=8 | 284.5 [283.3–288.8] n=8 | -2.0% | nominal |
| litert-lm | litert-community/Qwen3-0.6B/dynamic_wi4b32_afp32 | 8192 | 1986 | 256 [256–256] n=8 (0) | 4923.9 [4882.9–5011.0] n=8 | 442 [432–448] n=8 | 238.0 [236.5–241.0] n=8 | -18.0% | nominal |
| litert-lm | litert-community/Qwen3-1.7B | 2304 | 1986 | 256 [256–256] n=8 (0) | 3712.4 [3678.8–3731.0] n=8 | 571 [568–581] n=8 | 204.8 [203.8–206.7] n=8 | +0.0% | nominal |
| litert-lm | litert-community/Qwen3-1.7B | 4096 | 1986 | 256 [256–256] n=8 (0) | 3431.1 [3383.3–3445.7] n=8 | 617 [612–632] n=8 | 202.2 [201.1–203.9] n=8 | -1.2% | nominal |
| litert-lm | litert-community/Qwen3-1.7B | 8192 | 1986 | 256 [256–256] n=8 (0) | 2920.7 [2897.9–2940.8] n=8 | 720 [714–729] n=8 | 177.4 [176.3–178.9] n=8 | -13.4% | nominal |
| litert-lm | litert-community/gemma-4-E2B-it-litert-lm | 2304 | 1637 | 77 [77–77] n=8 (8) | 6713.9 [6614.2–6956.9] n=8 | 260 [245–265] n=8 | 155.5 [154.4–156.9] n=8 | +0.0% | nominal |
| litert-lm | litert-community/gemma-4-E2B-it-litert-lm | 4096 | 1637 | 256 [256–256] n=8 (0) | 6177.4 [6077.0–6311.7] n=8 | 281 [272–287] n=8 | 155.0 [154.5–156.4] n=8 | -0.4% | nominal |
| litert-lm | litert-community/gemma-4-E2B-it-litert-lm | 8192 | 1637 | 93 [93–93] n=8 (8) | 5514.5 [5388.7–5633.4] n=8 | 314 [304–322] n=8 | 137.4 [136.7–138.9] n=8 | -11.6% | nominal |
| litert-lm | litert-community/gemma-4-E4B-it-litert-lm | 2304 | 1637 | 256 [256–256] n=8 (0) | 2053.3 [1972.1–2076.4] n=8 | 815 [804–865] n=8 | 96.9 [86.4–97.9] n=8 | +0.0% | nominal |
| litert-lm | litert-community/gemma-4-E4B-it-litert-lm | 4096 | 1637 | 256 [256–256] n=8 (0) | 1971.7 [1953.2–2011.8] n=8 | 850 [828–862] n=8 | 96.7 [96.0–97.3] n=8 | -0.3% | nominal |
| litert-lm | litert-community/gemma-4-E4B-it-litert-lm | 8192 | 1637 | 256 [256–256] n=8 (0) | 1809.7 [1804.7–1833.1] n=8 | 924 [908–929] n=8 | 88.6 [88.0–89.0] n=8 | -8.6% | nominal |
| litert-lm-cpu | litert-community/Qwen3-0.6B/dynamic_wi4b32_afp32 | 2304 | 1986 | 256 [256–256] n=8 (0) | 527.2 [521.8–531.1] n=8 | 3856 [3827–3891] n=8 | 45.1 [43.7–47.0] n=8 | +0.0% | nominal |
| litert-lm-cpu | litert-community/Qwen3-0.6B/dynamic_wi4b32_afp32 | 4096 | 1986 | 256 [256–256] n=8 (0) | 398.4 [389.7–400.8] n=8 | 5098 [5065–5208] n=8 | 34.0 [33.1–35.3] n=8 | -24.6% | nominal |
| litert-lm-cpu | litert-community/Qwen3-0.6B/dynamic_wi4b32_afp32 | 8192 | 1986 | 256 [256–256] n=8 (0) | 262.3 [256.4–263.3] n=8 | 7766 [7722–7944] n=8 | 18.1 [17.9–18.8] n=8 | -59.8% | nominal |
| litert-lm-cpu | litert-community/Qwen3-1.7B/int8 | 2304 | 1986 | 256 [256–256] n=8 (0) | 574.5 [570.4–609.7] n=8 | 3518 [3314–3544] n=8 | 28.5 [28.0–29.1] n=8 | +0.0% | nominal |
| litert-lm-cpu | litert-community/Qwen3-1.7B/int8 | 4096 | 1986 | 256 [256–256] n=8 (0) | 573.1 [570.1–577.3] n=8 | 3528 [3501–3545] n=8 | 28.6 [28.3–29.0] n=8 | +0.5% | nominal |
| litert-lm-cpu | litert-community/Qwen3-1.7B/int8 | 8192 | 1986 | 256 [256–256] n=8 (0) | 573.5 [568.9–578.7] n=8 | 3524 [3491–3553] n=8 | 28.7 [28.2–29.7] n=8 | +1.0% | nominal |
| litert-lm-cpu | litert-community/gemma-4-E2B-it-litert-lm | 2304 | 1637 | 256 [256–256] n=8 (0) | 654.4 [618.3–660.4] n=8 | 2528 [2504–2676] n=8 | 50.6 [50.4–50.6] n=8 | +0.0% | nominal |
| litert-lm-cpu | litert-community/gemma-4-E2B-it-litert-lm | 4096 | 1637 | 256 [256–256] n=8 (0) | 552.7 [550.0–564.7] n=8 | 2990 [2926–3004] n=8 | 46.6 [46.4–48.0] n=8 | -7.9% | nominal |
| litert-lm-cpu | litert-community/gemma-4-E2B-it-litert-lm | 8192 | 1637 | 256 [256–256] n=8 (0) | 415.9 [414.8–426.5] n=8 | 3970 [3869–3979] n=8 | 39.2 [39.1–39.3] n=8 | -22.5% | nominal |
| litert-lm-cpu | litert-community/gemma-4-E4B-it-litert-lm | 2304 | 1637 | 256 [256–256] n=8 (0) | 229.7 [228.2–230.8] n=8 | 7166 [7126–7214] n=8 | 33.4 [33.0–33.7] n=8 | +0.0% | nominal |
| litert-lm-cpu | litert-community/gemma-4-E4B-it-litert-lm | 4096 | 1637 | 256 [256–256] n=8 (0) | 210.0 [209.3–210.9] n=8 | 7836 [7803–7859] n=8 | 31.3 [31.0–31.3] n=8 | -6.4% | nominal |
| litert-lm-cpu | litert-community/gemma-4-E4B-it-litert-lm | 8192 | 1637 | 256 [256–256] n=8 (0) | 177.6 [176.5–178.3] n=8 | 9264 [9225–9320] n=8 | 26.5 [26.5–26.6] n=8 | -20.5% | nominal |
| llama.cpp | unsloth/Qwen3-0.6B-GGUF/Q4_K_M | 2304 | 1986 | 256 [256–256] n=8 (0) | 11895.0 [11664.8–12026.0] n=8 | 240 [231–244] n=8 | 297.9 [292.9–312.9] n=8 | +0.0% | nominal |
| llama.cpp | unsloth/Qwen3-0.6B-GGUF/Q4_K_M | 4096 | 1986 | 256 [256–256] n=8 (0) | 11916.7 [11211.6–12020.8] n=8 | 246 [237–257] n=8 | 298.3 [292.8–305.1] n=8 | +0.1% | nominal |
| llama.cpp | unsloth/Qwen3-0.6B-GGUF/Q4_K_M | 8192 | 1986 | 256 [256–256] n=8 (0) | 12015.6 [11849.5–12132.6] n=8 | 253 [232–264] n=8 | 307.7 [296.0–312.8] n=8 | +3.3% | nominal |
| llama.cpp | unsloth/Qwen3-1.7B-GGUF/Q4_K_M | 2304 | 1986 | 256 [256–256] n=8 (0) | 4977.7 [4938.3–5086.1] n=8 | 538 [531–542] n=8 | 193.3 [188.8–198.0] n=8 | +0.0% | nominal |
| llama.cpp | unsloth/Qwen3-1.7B-GGUF/Q4_K_M | 4096 | 1986 | 256 [256–256] n=8 (0) | 5015.2 [4984.9–5054.4] n=8 | 542 [529–546] n=8 | 194.4 [190.5–197.2] n=8 | +0.6% | nominal |
| llama.cpp | unsloth/Qwen3-1.7B-GGUF/Q4_K_M | 8192 | 1986 | 256 [256–256] n=8 (0) | 5047.8 [5029.5–5063.5] n=8 | 550 [532–552] n=8 | 194.1 [191.2–197.6] n=8 | +0.4% | nominal |
| llama.cpp | unsloth/Qwen3-4B-GGUF/Q4_K_M | 2304 | 1986 | 256 [256–256] n=8 (0) | 2015.5 [1996.9–2027.6] n=8 | 1336 [1320–1345] n=8 | 103.2 [102.8–104.6] n=8 | +0.0% | nominal |
| llama.cpp | unsloth/Qwen3-4B-GGUF/Q4_K_M | 4096 | 1986 | 256 [256–256] n=8 (0) | 2020.8 [1988.7–2026.9] n=8 | 1338 [1324–1361] n=8 | 104.2 [102.2–105.1] n=8 | +0.9% | nominal |
| llama.cpp | unsloth/Qwen3-4B-GGUF/Q4_K_M | 8192 | 1986 | 256 [256–256] n=8 (0) | 2019.2 [2000.0–2024.4] n=8 | 1346 [1333–1361] n=8 | 103.4 [103.1–104.1] n=8 | +0.2% | nominal |
| llama.cpp | unsloth/gemma-4-E2B-it-GGUF/Q4_K_M | 2304 | 1629 | 256 [256–256] n=8 (0) | 2987.6 [2961.5–3028.6] n=8 | 608 [596–614] n=8 | 139.1 [135.9–141.5] n=8 | +0.0% | nominal |
| llama.cpp | unsloth/gemma-4-E2B-it-GGUF/Q4_K_M | 4096 | 1629 | 256 [256–256] n=8 (0) | 2981.1 [2966.2–3003.2] n=8 | 611 [604–614] n=8 | 138.9 [136.3–140.9] n=8 | -0.1% | nominal |
| llama.cpp | unsloth/gemma-4-E2B-it-GGUF/Q4_K_M | 8192 | 1629 | 256 [256–256] n=8 (0) | 2973.0 [2938.9–3033.2] n=8 | 614 [594–619] n=8 | 137.7 [135.3–141.2] n=8 | -1.0% | nominal |
| llama.cpp | unsloth/gemma-4-E4B-it-GGUF/Q4_K_M | 2304 | 1629 | 256 [256–256] n=8 (0) | 1537.9 [1531.2–1541.8] n=8 | 1163 [1159–1167] n=8 | 86.3 [85.3–87.8] n=8 | +0.0% | nominal |
| llama.cpp | unsloth/gemma-4-E4B-it-GGUF/Q4_K_M | 4096 | 1629 | 256 [256–256] n=8 (0) | 1536.6 [1534.5–1543.0] n=8 | 1166 [1161–1167] n=8 | 86.8 [86.0–88.1] n=8 | +0.6% | nominal |
| llama.cpp | unsloth/gemma-4-E4B-it-GGUF/Q4_K_M | 8192 | 1629 | 256 [256–256] n=8 (0) | 1546.9 [1535.5–1553.4] n=8 | 1159 [1146–1170] n=8 | 87.2 [86.0–87.7] n=8 | +1.1% | nominal |

csv: results/raw/2026-09-18-dashboard-longctx-v1-m4max-mac/ladder-warm.csv
