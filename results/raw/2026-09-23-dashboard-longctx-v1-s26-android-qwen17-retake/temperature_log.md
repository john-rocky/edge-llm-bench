# Per-launch temperature and round wakefulness

One row per launch; both iterations share launch telemetry. Wakefulness comes only from round_state.jsonl, never inferred from the generic screen label. All captured rounds are retained.

| round | launch | arm | allocation | C start | C end | thermal start | thermal end | non-nominal after gate | round mWakefulness | launch s | sampled peak RSS MiB | selected round |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | llama.cpp | 4096 | 35.6 | 35.6 | 0 | 0 | False | Dozing | 2.6 | 1252.19921875 | True |
| 1 | 2 | litert-lm-cpu | 2304 | 35.8 | 40.0 | 0 | 1 | False | Dozing | 71.2 | 2754.91796875 | True |
| 1 | 3 | litert-lm-cpu | 4096 | 37.4 | 41.2 | 0 | 2 | False | Dozing | 71.2 | 2872.60546875 | True |
| 1 | 4 | litert-lm-cpu | 8192 | 37.7 | 41.6 | 0 | 2 | False | Dozing | 70.9 | 2872.80859375 | True |
| 1 | 5 | llama.cpp | 2304 | 37.7 | 40.2 | 0 | 1 | False | Dozing | 100.8 | 2458.9140625 | True |
| 1 | 6 | llama.cpp | 4096 | 37.4 | 39.8 | 0 | 1 | False | Dozing | 100.8 | 2656.75390625 | True |
| 1 | 7 | llama.cpp | 8192 | 37.5 | 39.7 | 0 | 1 | False | Dozing | 100.2 | 3116.5078125 | True |
| 2 | 8 | llama.cpp | 8192 | 37.8 | 39.8 | 0 | 1 | False | Dozing | 100.2 | 3116.48828125 | True |
| 2 | 9 | llama.cpp | 4096 | 37.8 | 40.0 | 0 | 1 | False | Dozing | 100.3 | 2656.35546875 | True |
| 2 | 10 | llama.cpp | 2304 | 37.9 | 40.0 | 0 | 1 | False | Dozing | 107.0 | 2459.32421875 | True |
| 2 | 11 | litert-lm-cpu | 8192 | 37.8 | 40.7 | 0 | 2 | False | Dozing | 72.9 | 2866.1328125 | True |
| 2 | 12 | litert-lm-cpu | 4096 | 38.2 | 41.6 | 0 | 2 | False | Dozing | 71.3 | 2865.03125 | True |
| 2 | 13 | litert-lm-cpu | 2304 | 37.8 | 41.3 | 0 | 2 | False | Dozing | 71.8 | 2863.01953125 | True |
| 2 | 14 | llama.cpp | 4096 | 37.8 | 37.8 | 0 | 0 | False | Dozing | 2.6 | 1251.80078125 | True |
| 3 | 15 | llama.cpp | 4096 | 37.8 | 37.8 | 0 | 0 | False | Dozing | 2.6 | 1252.0390625 | True |
| 3 | 16 | litert-lm-cpu | 2304 | 37.7 | 41.4 | 0 | 2 | False | Dozing | 71.9 | 2867.828125 | True |
| 3 | 17 | litert-lm-cpu | 4096 | 37.7 | 41.3 | 0 | 2 | False | Dozing | 71.3 | 2864.1015625 | True |
| 3 | 18 | litert-lm-cpu | 8192 | 37.5 | 40.8 | 0 | 2 | False | Dozing | 70.9 | 2868.3125 | True |
| 3 | 19 | llama.cpp | 2304 | 37.6 | 39.5 | 0 | 1 | False | Dozing | 99.8 | 2458.94140625 | True |
| 3 | 20 | llama.cpp | 4096 | 37.8 | 40.0 | 0 | 1 | False | Dozing | 100.8 | 2656.421875 | True |
| 3 | 21 | llama.cpp | 8192 | 37.5 | 39.8 | 0 | 1 | False | Dozing | 100.8 | 3116.6484375 | True |
| 4 | 22 | llama.cpp | 8192 | 37.7 | 39.8 | 0 | 1 | False | Dozing | 100.2 | 3115.86328125 | True |
| 4 | 23 | llama.cpp | 4096 | 38.0 | 39.8 | 0 | 1 | False | Dozing | 99.7 | 2655.8125 | True |
| 4 | 24 | llama.cpp | 2304 | 38.1 | 40.2 | 0 | 1 | False | Dozing | 99.7 | 2458.375 | True |
| 4 | 25 | litert-lm-cpu | 8192 | 37.7 | 41.1 | 0 | 2 | False | Dozing | 73.8 | 3132.5546875 | True |
| 4 | 26 | litert-lm-cpu | 4096 | 37.6 | 41.7 | 0 | 2 | False | Dozing | 74.4 | 3126.515625 | True |
| 4 | 27 | litert-lm-cpu | 2304 | 37.6 | 41.2 | 0 | 2 | False | Dozing | 71.8 | 2868.453125 | True |
| 4 | 28 | llama.cpp | 4096 | 37.6 | 37.6 | 0 | 0 | False | Dozing | 2.6 | 1251.16796875 | True |
| 5 | 29 | llama.cpp | 4096 | 37.6 | 37.5 | 0 | 0 | False | Dozing | 2.6 | 1250.98828125 | True |
| 5 | 30 | litert-lm-cpu | 2304 | 37.4 | 41.2 | 0 | 2 | False | Dozing | 71.8 | 2868.4140625 | True |
| 5 | 31 | litert-lm-cpu | 4096 | 37.4 | 41.3 | 0 | 2 | False | Dozing | 70.7 | 2868.453125 | True |
| 5 | 32 | litert-lm-cpu | 8192 | 37.5 | 41.5 | 0 | 2 | False | Dozing | 70.8 | 2868.34765625 | True |
| 5 | 33 | llama.cpp | 2304 | 37.6 | 39.8 | 0 | 1 | False | Dozing | 100.8 | 2458.00390625 | True |
| 5 | 34 | llama.cpp | 4096 | 37.9 | 39.7 | 0 | 1 | False | Dozing | 101.3 | 2655.453125 | True |
| 5 | 35 | llama.cpp | 8192 | 37.9 | 40.0 | 0 | 1 | False | Dozing | 100.7 | 3115.640625 | True |
| 6 | 36 | llama.cpp | 8192 | 37.5 | 39.7 | 0 | 1 | False | Dozing | 100.8 | 3115.61328125 | True |
| 6 | 37 | llama.cpp | 4096 | 37.7 | 39.7 | 0 | 1 | False | Dozing | 100.3 | 2655.39453125 | True |
| 6 | 38 | llama.cpp | 2304 | 37.8 | 39.5 | 0 | 1 | False | Dozing | 100.8 | 2457.8203125 | True |
| 6 | 39 | litert-lm-cpu | 8192 | 37.3 | 41.2 | 0 | 2 | False | Dozing | 71.8 | 2865.6953125 | True |
| 6 | 40 | litert-lm-cpu | 4096 | 37.7 | 40.9 | 0 | 2 | False | Dozing | 70.8 | 2866.33203125 | True |
| 6 | 41 | litert-lm-cpu | 2304 | 37.9 | 40.5 | 0 | 2 | False | Dozing | 70.3 | 2866.9140625 | True |
| 6 | 42 | llama.cpp | 4096 | 38.0 | 38.0 | 0 | 0 | False | Dozing | 2.1 | 1251.2578125 | True |


## Stored per-round environment probes

| round | probe start JST | probe end JST | mWakefulness | stay_on_while_plugged_in | MemAvailable KiB | battery °C | thermal before gate | lane CPU samples |
|---|---|---|---|---|---|---|---|---|
| 1 | 2026-09-23T23:50:20.700200 | 2026-09-23T23:50:22.355623 | Dozing | 0 | 7389708 | 36.0 | 0 | no lane process |
| 2 | 2026-09-24T00:12:58.242702 | 2026-09-24T00:12:59.996571 | Dozing | 0 | 7422208 | 39.7 | 1 | no lane process |
| 3 | 2026-09-24T00:38:33.913199 | 2026-09-24T00:38:35.514397 | Dozing | 0 | 7128744 | 37.8 | 0 | no lane process |
| 4 | 2026-09-24T01:01:02.964053 | 2026-09-24T01:01:04.618663 | Dozing | 0 | 7069688 | 39.8 | 1 | no lane process |
| 5 | 2026-09-24T01:27:05.015590 | 2026-09-24T01:27:06.556917 | Dozing | 0 | 6834124 | 37.6 | 0 | no lane process |
| 6 | 2026-09-24T01:50:03.855686 | 2026-09-24T01:50:05.528853 | Dozing | 0 | 7018840 | 40.0 | 1 | no lane process |

Round 1 was sampled before launch 1. Later samples follow round-state entries during the existing 30-second cooldown. A nonzero round-probe thermal status precedes the nominal gate; engine start/end statuses are in the launch table. No display, setting or foreign process was changed. Commands/timestamps: results/r13/round_environment.jsonl; raw files: logs/r13/roundNN_*.stdout.
