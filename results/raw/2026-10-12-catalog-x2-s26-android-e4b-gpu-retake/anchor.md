# Anchor admission

llama.cpp b8999 Qwen3-0.6B Q4_K_M short-chat, once per round; reference 105.6 tok/s (results/raw/2026-09-14-dashboard-v1-s26-android/SESSION.json, anchor median); 5 % rule.

| round | decode tok/s | protocolFlags |
|---|---|---|
| 1 | 106.8 |  |
| 2 | 107.5 | cpu-capped |
| 3 | 106.8 |  |
| 4 | 107.5 | cpu-capped |

median 107.15 over 4 rounds = 1.015 of the reference: admitted
