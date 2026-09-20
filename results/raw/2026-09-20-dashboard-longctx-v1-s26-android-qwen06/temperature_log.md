# Per-launch temperature and round wakefulness

One row per launch; both iterations share launch telemetry. Wakefulness comes only from round_state.jsonl, never inferred from the generic screen label. All captured rounds are retained.

| round | launch | arm | allocation | C start | C end | thermal start | thermal end | non-nominal after gate | round mWakefulness | launch s | sampled peak RSS MiB | selected round |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | llama.cpp | 4096 | 30.9 | 30.9 | 0 | 0 | False | Awake | 2.1 | 1251.78125 | True |
| 1 | 2 | litert-lm-cpu | 2304 | 31.4 | 34.0 | 0 | 0 | False | Awake | 38.7 | 1760.7265625 | True |
| 1 | 3 | litert-lm-cpu | 4096 | 34.8 | 37.0 | 0 | 0 | False | Awake | 66.9 | 2641.69140625 | True |
| 1 | 4 | litert-lm-cpu | 8192 | 37.7 | 40.6 | 0 | 2 | False | Awake | 139.6 | 4654.53515625 | True |
| 1 | 5 | llama.cpp | 2304 | 37.2 | 39.2 | 0 | 1 | False | Awake | 85.9 | 1084.30859375 | True |
| 1 | 6 | llama.cpp | 4096 | 37.5 | 39.1 | 0 | 1 | False | Awake | 88.0 | 1283.85546875 | True |
| 1 | 7 | llama.cpp | 8192 | 37.4 | 39.2 | 0 | 1 | False | Awake | 88.0 | 1729.60546875 | True |
| 2 | 8 | llama.cpp | 8192 | 37.2 | 39.1 | 0 | 1 | False | Awake | 88.0 | 1729.91015625 | True |
| 2 | 9 | llama.cpp | 4096 | 37.2 | 39.3 | 0 | 1 | False | Awake | 87.5 | 1283.81640625 | True |
| 2 | 10 | llama.cpp | 2304 | 37.2 | 39.1 | 0 | 1 | False | Awake | 86.4 | 1084.23828125 | True |
| 2 | 11 | litert-lm-cpu | 8192 | 37.5 | 41.6 | 0 | 2 | False | Awake | 141.3 | 4643.53515625 | True |
| 2 | 12 | litert-lm-cpu | 4096 | 37.5 | 40.8 | 0 | 2 | False | Awake | 71.7 | 2641.12890625 | True |
| 2 | 13 | litert-lm-cpu | 2304 | 37.6 | 39.9 | 0 | 1 | False | Awake | 43.0 | 1760.19921875 | True |
| 2 | 14 | llama.cpp | 4096 | 37.5 | 37.4 | 0 | 0 | False | Awake | 2.6 | 1251.3984375 | True |
| 3 | 15 | llama.cpp | 4096 | 37.5 | 37.5 | 0 | 0 | False | Awake | 2.6 | 1251.671875 | True |
| 3 | 16 | litert-lm-cpu | 2304 | 37.4 | 39.1 | 0 | 1 | False | Awake | 44.0 | 1760.03125 | True |
| 3 | 17 | litert-lm-cpu | 4096 | 37.3 | 40.3 | 0 | 1 | False | Awake | 72.2 | 2641.3359375 | True |
| 3 | 18 | litert-lm-cpu | 8192 | 37.2 | 41.6 | 0 | 2 | False | Awake | 142.9 | 4654.05078125 | True |
| 3 | 19 | llama.cpp | 2304 | 37.3 | 39.4 | 0 | 1 | False | Awake | 89.0 | 1084.28515625 | True |
| 3 | 20 | llama.cpp | 4096 | 37.4 | 39.5 | 0 | 1 | False | Awake | 85.9 | 1283.87890625 | True |
| 3 | 21 | llama.cpp | 8192 | 37.8 | 39.4 | 0 | 1 | False | Awake | 86.4 | 1729.66796875 | True |
| 4 | 22 | llama.cpp | 8192 | 37.6 | 39.5 | 0 | 1 | False | Awake | 84.8 | 1729.9765625 | True |
| 4 | 23 | llama.cpp | 4096 | 37.5 | 39.5 | 0 | 1 | False | Awake | 85.9 | 1283.84375 | True |
| 4 | 24 | llama.cpp | 2304 | 37.5 | 39.5 | 0 | 1 | False | Awake | 85.4 | 1084.484375 | True |
| 4 | 25 | litert-lm-cpu | 8192 | 37.7 | 41.6 | 0 | 2 | False | Awake | 146.6 | 4602.2265625 | True |
| 4 | 26 | litert-lm-cpu | 4096 | 37.7 | 40.2 | 0 | 2 | False | Awake | 72.2 | 2640.90625 | True |
| 4 | 27 | litert-lm-cpu | 2304 | 37.6 | 39.8 | 0 | 1 | False | Awake | 43.5 | 1760.3046875 | True |
| 4 | 28 | llama.cpp | 4096 | 37.5 | 37.5 | 0 | 0 | False | Awake | 2.1 | 1251.02734375 | True |
| 5 | 29 | llama.cpp | 4096 | 37.7 | 37.7 | 0 | 0 | False | Awake | 2.6 | 1251.234375 | True |
| 5 | 30 | litert-lm-cpu | 2304 | 37.6 | 38.5 | 0 | 1 | False | Awake | 43.5 | 1760.4453125 | True |
| 5 | 31 | litert-lm-cpu | 4096 | 37.4 | 40.5 | 0 | 1 | False | Awake | 71.7 | 2642.09765625 | True |
| 5 | 32 | litert-lm-cpu | 8192 | 37.8 | 41.5 | 0 | 2 | False | Awake | 145.2 | 4655.7109375 | True |
| 5 | 33 | llama.cpp | 2304 | 37.4 | 39.4 | 0 | 1 | False | Awake | 87.5 | 1083.83203125 | True |
| 5 | 34 | llama.cpp | 4096 | 37.6 | 39.7 | 0 | 1 | False | Awake | 85.9 | 1283.61328125 | True |
| 5 | 35 | llama.cpp | 8192 | 37.5 | 39.5 | 0 | 1 | False | Awake | 85.9 | 1729.69140625 | True |
| 6 | 36 | llama.cpp | 8192 | 37.5 | 39.3 | 0 | 1 | False | Awake | 87.4 | 1729.6171875 | True |
| 6 | 37 | llama.cpp | 4096 | 37.6 | 39.5 | 0 | 1 | False | Awake | 85.9 | 1283.3984375 | True |
| 6 | 38 | llama.cpp | 2304 | 37.6 | 39.6 | 0 | 1 | False | Awake | 86.9 | 1084.02734375 | True |
| 6 | 39 | litert-lm-cpu | 8192 | 37.5 | 41.4 | 0 | 2 | False | Awake | 146.7 | 4653.890625 | True |
| 6 | 40 | litert-lm-cpu | 4096 | 37.6 | 40.6 | 0 | 1 | False | Awake | 72.2 | 2639.67578125 | True |
| 6 | 41 | litert-lm-cpu | 2304 | 37.4 | 39.3 | 0 | 1 | False | Awake | 43.0 | 1759.2109375 | True |
| 6 | 42 | llama.cpp | 4096 | 37.6 | 37.6 | 0 | 0 | False | Awake | 2.6 | 1251.359375 | True |
| 7 | 43 | llama.cpp | 4096 | 37.6 | 37.6 | 0 | 0 | False | Awake | 2.6 | 1251.45703125 | False |
| 7 | 44 | litert-lm-cpu | 2304 | 37.7 | 39.3 | 0 | 1 | False | Awake | 45.1 | 1758.9453125 | False |
| 7 | 45 | litert-lm-cpu | 4096 | 37.4 | 40.5 | 0 | 1 | False | Awake | 71.7 | 2640.11328125 | False |


## Stored per-round environment probes

| round | probe start JST | probe end JST | mWakefulness | stay_on_while_plugged_in | MemAvailable KiB | battery °C | thermal status before gate | lane CPU samples |
|---|---|---|---|---|---|---|---|---|
| 1 | 20:45:36.819988 | 20:45:38.438952 | Awake | 15 | 5528084 | 31.0 | 0 | com.mlboydaisuke.edgezoo.qa: 0.0, 0.0 % |
| 2 | 21:02:34.613584 | 21:02:36.329930 | Awake | 15 | 6412196 | 39.2 | 1 | com.mlboydaisuke.edgezoo.qa: 0.0, 0.0 % |
| 3 | 21:28:25.493334 | 21:28:27.162327 | Awake | 15 | 6324684 | 37.4 | 0 | com.mlboydaisuke.edgezoo.qa: 0.0, 0.0 % |
| 4 | 21:51:18.778279 | 21:51:20.444420 | Awake | 15 | 6448428 | 39.4 | 1 | com.mlboydaisuke.edgezoo.qa: 0.0, 0.0 % |
| 5 | 22:16:39.088765 | 22:16:40.728155 | Awake | 15 | 6612724 | 37.5 | 0 | com.mlboydaisuke.edgezoo.qa: 0.0, 0.0 % |
| 6 | 22:39:01.032558 | 22:39:02.706615 | Awake | 15 | 6709844 | 39.5 | 1 | com.mlboydaisuke.edgezoo.qa: 0.0, 0.0 % |
| 7 | 23:05:27.034316 | 23:05:28.699911 | Awake | 15 | 6521552 | 37.6 | 0 | com.mlboydaisuke.edgezoo.qa: 0.0, 0.0 % |

These read-only probes were collected before launch 1, then immediately after each round-state entry during the existing 30-second cooldown. A round-start status of 1 precedes the thermal gate; every engine launch started at 0. No settings or display changes were made. Full ps/top/power/memory evidence: `logs/r9/roundNN_*.stdout`; commands and timestamps: `results/r9/round_environment.jsonl`; parsed audit: `results/r9/round_environment_audit.json`. Only cached edgezoo.qa was present in the lane-name samples, at 0.0% CPU in both samples each round. No foreign process was stopped.
