# Per-launch temperature and round wakefulness

One row per launch; both iterations share launch telemetry. Wakefulness comes only from round_state.jsonl, never inferred from the generic screen label. All captured rounds are retained.

| round | launch | arm | allocation | C start | C end | thermal start | thermal end | non-nominal after gate | round mWakefulness | launch s | sampled peak RSS MiB | selected round |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | llama.cpp | 4096 | 34.1 | 34.1 | 0 | 0 | False | Awake | 2.1 | 1250.73046875 | True |
| 1 | 2 | llama.cpp | 2304 | 34.2 | 39.3 | 0 | 1 | False | Awake | 263.8 | 5187.79296875 | True |
| 1 | 3 | llama.cpp | 4096 | 37.1 | 40.0 | 0 | 2 | False | Awake | 261.7 | 5447.765625 | True |
| 1 | 4 | llama.cpp | 8192 | 36.9 | 40.4 | 0 | 2 | False | Awake | 260.1 | 6033.8671875 | True |
| 2 | 5 | llama.cpp | 8192 | 37.2 | 41.1 | 0 | 2 | False | Dozing | 262.7 | 6034.85546875 | True |
| 2 | 6 | llama.cpp | 4096 | 37.2 | 40.8 | 0 | 2 | False | Dozing | 261.1 | 5456.55859375 | True |
| 2 | 7 | llama.cpp | 2304 | 37.5 | 40.9 | 0 | 2 | False | Dozing | 260.6 | 5206.68359375 | True |
| 2 | 8 | llama.cpp | 4096 | 37.0 | 37.0 | 0 | 0 | False | Dozing | 2.6 | 1250.84765625 | True |
| 3 | 9 | llama.cpp | 4096 | 36.9 | 36.9 | 0 | 0 | False | Dozing | 2.6 | 1250.76171875 | True |
| 3 | 10 | llama.cpp | 2304 | 36.8 | 40.9 | 0 | 2 | False | Dozing | 268.5 | 4711.6171875 | True |
| 3 | 11 | llama.cpp | 4096 | 37.1 | 40.6 | 0 | 2 | False | Dozing | 261.7 | 5440.2578125 | True |
| 3 | 12 | llama.cpp | 8192 | 37.5 | 41.1 | 0 | 2 | False | Dozing | 261.7 | 6035.94140625 | True |
| 4 | 13 | llama.cpp | 8192 | 37.4 | 41.3 | 0 | 2 | False | Dozing | 262.8 | 6037.19140625 | True |
| 4 | 14 | llama.cpp | 4096 | 37.6 | 41.9 | 0 | 2 | False | Dozing | 264.2 | 5457.00390625 | True |
| 4 | 15 | llama.cpp | 2304 | 37.8 | 41.7 | 0 | 2 | False | Dozing | 270.1 | 5207.32421875 | True |
| 4 | 16 | llama.cpp | 4096 | 37.9 | 37.9 | 0 | 0 | False | Dozing | 2.6 | 1251.3515625 | True |
| 5 | 17 | llama.cpp | 4096 | 37.8 | 37.8 | 0 | 0 | False | Dozing | 2.6 | 1251.19921875 | True |
| 5 | 18 | llama.cpp | 2304 | 37.8 | 41.7 | 0 | 2 | False | Dozing | 266.4 | 5207.1640625 | True |
| 5 | 19 | llama.cpp | 4096 | 38.0 | 41.8 | 0 | 2 | False | Dozing | 267.6 | 5454.390625 | True |
| 5 | 20 | llama.cpp | 8192 | 37.7 | 41.9 | 0 | 2 | False | Dozing | 264.9 | 6020.99609375 | True |


## Stored per-round environment probes

| round | probe start JST | probe end JST | mWakefulness | stay_on_while_plugged_in | MemAvailable KiB | battery °C | thermal before gate | lane CPU samples % |
|---|---|---|---|---|---|---|---|---|
| 1 | 2026-09-24T10:22:11.186042 | 2026-09-24T10:22:13.255322 | Awake | 0 | 7523532 | 34.2 | 0 | no lane process |
| 2 | 2026-09-24T10:41:50.325883 | 2026-09-24T10:41:52.084804 | Dozing | 0 | 7609744 | 40.4 | 2 | no lane process |
| 3 | 2026-09-24T11:05:11.540897 | 2026-09-24T11:05:13.113563 | Dozing | 0 | 7237900 | 37.0 | 0 | no lane process |
| 4 | 2026-09-24T11:24:40.622928 | 2026-09-24T11:24:42.371782 | Dozing | 0 | 7378536 | 41.1 | 2 | no lane process |
| 5 | 2026-09-24T11:54:44.779875 | 2026-09-24T11:54:46.561451 | Dozing | 0 | 7136716 | 37.9 | 0 | no lane process |

Round 1 was sampled before launch 1. Later probes ran during the existing cooldown after each round-state entry. Probe thermal status precedes the launch gate. All raw probe paths and timestamps are in results/r15/round_environment_audit.json. No setting, display or foreign process was changed.
