# Anchor admission

llama.cpp b8999 Qwen3-0.6B Q4_K_M short-chat, once per round; reference 105.6 tok/s (results/raw/2026-09-14-dashboard-v1-s26-android/SESSION.json, anchor median); 5 % rule.

| round | decode tok/s | protocolFlags |
|---|---|---|
| 1 | 106.2 |  |
| 2 | 103.9 | cpu-capped |
| 3 | 104.9 | cpu-capped |
| 4 | 109.5 | cpu-capped |

median 105.55 over 4 rounds = 1.000 of the reference: admitted
