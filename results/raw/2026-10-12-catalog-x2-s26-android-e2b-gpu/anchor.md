# Anchor admission

llama.cpp b8999 Qwen3-0.6B Q4_K_M short-chat, once per round; reference 105.6 tok/s (results/raw/2026-09-14-dashboard-v1-s26-android/SESSION.json, anchor median); 5 % rule.

| round | decode tok/s | protocolFlags |
|---|---|---|
| 1 | 105.8 |  |
| 2 | 107.2 | cpu-capped |
| 3 | 90.4 |  |
| 4 | 106.0 |  |
| 5 | 107.6 |  |
| 6 | 90.4 |  |

median 105.90 over 6 rounds = 1.003 of the reference: admitted
