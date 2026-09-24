# Per-launch temperature and round wakefulness

One row per launch; both iterations share launch telemetry. Wakefulness comes only from round_state.jsonl, never inferred from the generic screen label. All captured rounds are retained.

| round | launch | arm | allocation | C start | C end | thermal start | thermal end | non-nominal after gate | round mWakefulness | launch s | sampled peak RSS MiB | selected round |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | llama.cpp | 4096 | 37.6 | 37.6 | 0 | 0 | False | Dozing | 2.6 | 1251.7421875 | True |
| 1 | 2 | litert-lm-gpu | 2304 | 37.9 | 38.7 | 0 | 0 | False | Dozing | 24.4 | 814.68359375 | True |
| 1 | 3 | litert-lm-gpu | 4096 | 37.7 | 38.3 | 0 | 0 | False | Dozing | 23.4 | 833.30078125 | True |
| 1 | 4 | litert-lm-gpu | 8192 | 37.9 | 37.9 | 0 | 0 | False | Dozing | 12.0 | 835.78125 | True |
| 1 | 5 | litert-lm-gpu | 2304 | 38.5 | 38.9 | 0 | 1 | False | Dozing | 17.7 | 829.7265625 | True |
| 1 | 6 | litert-lm-gpu | 4096 | 37.7 | 37.9 | 0 | 0 | False | Dozing | 16.7 | 943.3515625 | True |
| 1 | 7 | litert-lm-gpu | 8192 | 37.7 | 37.8 | 0 | 1 | False | Dozing | 16.6 | 1155.44921875 | True |
| 2 | 8 | litert-lm-gpu | 8192 | 37.3 | 37.5 | 0 | 0 | False | Dozing | 17.3 | 962.56640625 | True |
| 2 | 9 | litert-lm-gpu | 4096 | 38.5 | 38.9 | 0 | 1 | False | Dozing | 17.8 | 991.0 | True |
| 2 | 10 | litert-lm-gpu | 2304 | 37.4 | 38.1 | 0 | 1 | False | Dozing | 20.3 | 861.70703125 | True |
| 2 | 11 | litert-lm-gpu | 8192 | 37.7 | 37.2 | 0 | 0 | False | Dozing | 12.6 | 829.19921875 | True |
| 2 | 12 | litert-lm-gpu | 4096 | 37.8 | 37.9 | 0 | 0 | False | Dozing | 28.7 | 855.94921875 | True |
| 2 | 13 | litert-lm-gpu | 2304 | 38.6 | 38.1 | 0 | 1 | False | Dozing | 30.3 | 837.1171875 | True |
| 2 | 14 | llama.cpp | 4096 | 37.4 | 37.4 | 0 | 0 | False | Dozing | 2.1 | 1251.74609375 | True |
| 3 | 15 | llama.cpp | 4096 | 37.3 | 37.3 | 0 | 0 | False | Dozing | 2.6 | 1252.0703125 | True |
| 3 | 16 | litert-lm-gpu | 2304 | 37.2 | 37.0 | 0 | 0 | False | Dozing | 23.0 | 808.421875 | True |
| 3 | 17 | litert-lm-gpu | 4096 | 38.2 | 37.7 | 0 | 0 | False | Dozing | 28.7 | 788.890625 | True |
| 3 | 18 | litert-lm-gpu | 8192 | 38.9 | 38.1 | 0 | 0 | False | Dozing | 18.7 | 860.203125 | True |
| 3 | 19 | litert-lm-gpu | 2304 | 38.4 | 38.0 | 0 | 1 | False | Dozing | 24.0 | 857.10546875 | True |
| 3 | 20 | litert-lm-gpu | 4096 | 37.5 | 37.9 | 0 | 0 | False | Dozing | 21.4 | 1080.484375 | True |
| 3 | 21 | litert-lm-gpu | 8192 | 37.1 | 37.1 | 0 | 0 | False | Dozing | 21.3 | 1197.80078125 | True |
| 4 | 22 | litert-lm-gpu | 8192 | 38.1 | 38.1 | 0 | 1 | False | Dozing | 18.3 | 1042.078125 | True |
| 4 | 23 | litert-lm-gpu | 4096 | 37.6 | 37.2 | 0 | 0 | False | Dozing | 16.7 | 1003.8125 | True |
| 4 | 24 | litert-lm-gpu | 2304 | 37.6 | 38.2 | 0 | 0 | False | Dozing | 16.7 | 886.7265625 | True |
| 4 | 25 | litert-lm-gpu | 8192 | 37.3 | 37.3 | 0 | 0 | False | Dozing | 12.1 | 740.36328125 | True |
| 4 | 26 | litert-lm-gpu | 4096 | 38.2 | 37.8 | 0 | 1 | False | Dozing | 27.6 | 852.6640625 | True |
| 4 | 27 | litert-lm-gpu | 2304 | 37.7 | 37.7 | 0 | 0 | False | Dozing | 26.6 | 835.53515625 | True |
| 4 | 28 | llama.cpp | 4096 | 37.3 | 37.3 | 0 | 0 | False | Dozing | 2.6 | 1249.69921875 | True |
| 5 | 29 | llama.cpp | 4096 | 37.3 | 37.3 | 0 | 0 | False | Dozing | 2.6 | 1252.203125 | True |
| 5 | 30 | litert-lm-gpu | 2304 | 37.4 | 37.3 | 0 | 0 | False | Dozing | 23.0 | 768.46484375 | True |
| 5 | 31 | litert-lm-gpu | 4096 | 38.7 | 38.0 | 0 | 1 | False | Dozing | 29.2 | 852.23046875 | True |
| 5 | 32 | litert-lm-gpu | 8192 | 37.7 | 37.5 | 0 | 0 | False | Dozing | 15.6 | 842.02734375 | True |
| 5 | 33 | litert-lm-gpu | 2304 | 38.1 | 38.1 | 0 | 1 | False | Dozing | 17.3 | 831.99609375 | True |
| 5 | 34 | litert-lm-gpu | 4096 | 37.3 | 37.3 | 0 | 0 | False | Dozing | 16.7 | 865.046875 | True |
| 5 | 35 | litert-lm-gpu | 8192 | 37.7 | 37.6 | 0 | 1 | False | Dozing | 21.4 | 999.92578125 | True |
| 6 | 36 | litert-lm-gpu | 8192 | 37.8 | 38.2 | 0 | 1 | False | Dozing | 20.3 | 1008.375 | True |
| 6 | 37 | litert-lm-gpu | 4096 | 37.7 | 38.9 | 0 | 1 | False | Dozing | 20.8 | 935.21875 | True |
| 6 | 38 | litert-lm-gpu | 2304 | 37.6 | 37.6 | 0 | 1 | False | Dozing | 21.3 | 1018.81640625 | True |
| 6 | 39 | litert-lm-gpu | 8192 | 37.9 | 37.9 | 0 | 0 | False | Dozing | 15.5 | 849.3671875 | True |
| 6 | 40 | litert-lm-gpu | 4096 | 38.6 | 38.4 | 0 | 1 | False | Dozing | 29.7 | 859.8984375 | True |
| 6 | 41 | litert-lm-gpu | 2304 | 37.9 | 38.3 | 0 | 1 | False | Dozing | 26.2 | 843.12890625 | True |
| 6 | 42 | llama.cpp | 4096 | 37.8 | 37.8 | 0 | 0 | False | Dozing | 2.6 | 1248.05859375 | True |


## Stored per-round environment probes

| round | probe start JST | probe end JST | mWakefulness | stay_on_while_plugged_in | MemAvailable KiB | battery °C | thermal before gate | lane CPU samples % |
|---|---|---|---|---|---|---|---|---|
| 1 | 2026-09-24T12:39:19.980199 | 2026-09-24T12:39:21.609680 | Dozing | 0 | 7099632 | 38.0 | 1 | no lane process |
| 2 | 2026-09-24T12:58:06.079367 | 2026-09-24T12:58:07.702417 | Dozing | 0 | 7211932 | 37.8 | 1 | no lane process |
| 3 | 2026-09-24T13:09:20.562930 | 2026-09-24T13:09:22.143609 | Dozing | 0 | 7484056 | 37.4 | 0 | no lane process |
| 4 | 2026-09-24T13:17:45.490348 | 2026-09-24T13:17:47.253732 | Dozing | 0 | 7711368 | 38.2 | 0 | no lane process |
| 5 | 2026-09-24T13:29:49.621951 | 2026-09-24T13:29:51.185076 | Dozing | 0 | 7446608 | 37.3 | 0 | no lane process |
| 6 | 2026-09-24T13:39:28.621304 | 2026-09-24T13:39:30.183725 | Dozing | 0 | 7670016 | 37.6 | 1 | no lane process |

Round 1 was sampled before launch 1. Later samples follow round-state entries during the existing cooldown. Probe thermal status precedes the launch gate. No display, setting or foreign process was changed. Raw paths are retained in results/r16/round_environment_audit.json.
