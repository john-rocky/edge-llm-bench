# Per-launch temperature and round wakefulness

One row per launch; both iterations share launch telemetry. Wakefulness comes only from round_state.jsonl, never inferred from the generic screen label. All captured rounds are retained.

| round | launch | arm | allocation | C start | C end | thermal start | thermal end | non-nominal after gate | round mWakefulness | launch s | sampled peak RSS MiB | selected round |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | llama.cpp | 4096 | 31.6 | 31.6 | 0 | 0 | False | Awake | 2.1 | 1251.58203125 | True |
| 1 | 2 | litert-lm-cpu | 2304 | 31.8 | 35.9 | 0 | 0 | False | Awake | 67.1 | 3663.57421875 | True |
| 1 | 3 | litert-lm-cpu | 4096 | 35.9 | 37.8 | 0 | 1 | False | Awake | 78.5 | 4652.8515625 | True |
| 1 | 4 | litert-lm-gpu | 2304 | 36.7 | 36.7 | 0 | 0 | False | Awake | 16.6 | 802.9140625 | True |
| 1 | 5 | litert-lm-gpu | 4096 | 38.5 | 37.7 | 0 | 1 | False | Awake | 16.0 | 847.68359375 | True |
| 1 | 6 | litert-lm-gpu | 8192 | 37.6 | 38.5 | 0 | 1 | False | Awake | 18.1 | 1192.3671875 | True |
| 1 | 7 | llama.cpp | 2304 | 36.8 | 41.4 | 0 | 2 | False | Awake | 151.9 | 5675.66796875 | True |
| 1 | 8 | llama.cpp | 4096 | 37.2 | 40.0 | 0 | 2 | False | Awake | 171.6 | 6610.171875 | True |
| 1 | 9 | llama.cpp | 8192 | 37.6 | 39.8 | 0 | 2 | False | Awake | 182.3 | 6727.51953125 | True |
| 2 | 10 | llama.cpp | 8192 | 37.5 | 39.8 | 0 | 1 | False | Awake | 195.2 | 6473.72265625 | True |
| 2 | 11 | llama.cpp | 4096 | 37.2 | 39.7 | 0 | 2 | False | Awake | 168.5 | 6161.2265625 | True |
| 2 | 12 | llama.cpp | 2304 | 37.1 | 40.2 | 0 | 2 | False | Awake | 190.9 | 6294.4453125 | True |
| 2 | 13 | litert-lm-gpu | 8192 | 37.1 | 38.6 | 0 | 1 | False | Awake | 18.7 | 1048.4140625 | True |
| 2 | 14 | litert-lm-gpu | 4096 | 37.2 | 37.2 | 0 | 1 | False | Awake | 20.8 | 1055.8671875 | True |
| 2 | 15 | litert-lm-gpu | 2304 | 37.3 | 36.9 | 0 | 1 | False | Awake | 19.7 | 898.3828125 | True |
| 2 | 16 | litert-lm-cpu | 4096 | 37.2 | 39.8 | 0 | 1 | False | Awake | 82.7 | 4588.3203125 | True |
| 2 | 17 | litert-lm-cpu | 2304 | 37.4 | 39.8 | 0 | 1 | False | Awake | 71.8 | 4307.953125 | True |
| 2 | 18 | llama.cpp | 4096 | 37.2 | 37.2 | 0 | 0 | False | Awake | 2.1 | 1251.28125 | True |
| 3 | 19 | llama.cpp | 4096 | 37.2 | 37.2 | 0 | 0 | False | Awake | 2.1 | 1251.96875 | True |
| 3 | 20 | litert-lm-cpu | 2304 | 36.8 | 39.6 | 0 | 1 | False | Awake | 70.8 | 3929.515625 | True |
| 3 | 21 | litert-lm-cpu | 4096 | 37.1 | 40.2 | 0 | 1 | False | Awake | 83.2 | 5638.53515625 | True |
| 3 | 22 | litert-lm-gpu | 2304 | 37.0 | 38.0 | 0 | 0 | False | Awake | 17.1 | 965.1015625 | True |
| 3 | 23 | litert-lm-gpu | 4096 | 38.2 | 38.6 | 0 | 1 | False | Awake | 25.6 | 902.50390625 | True |
| 3 | 24 | litert-lm-gpu | 8192 | 37.1 | 37.5 | 0 | 1 | False | Awake | 18.6 | 1045.87890625 | True |
| 3 | 25 | llama.cpp | 2304 | 37.0 | 40.2 | 0 | 1 | False | Awake | 169.0 | 5729.46484375 | True |
| 3 | 26 | llama.cpp | 4096 | 37.1 | 40.5 | 0 | 2 | False | Awake | 166.9 | 6072.30078125 | True |
| 3 | 27 | llama.cpp | 8192 | 37.3 | 40.7 | 0 | 2 | False | Awake | 166.5 | 6469.98828125 | True |
| 4 | 28 | llama.cpp | 8192 | 37.1 | 40.6 | 0 | 2 | False | Awake | 168.5 | 6448.11328125 | True |
| 4 | 29 | llama.cpp | 4096 | 37.4 | 41.3 | 0 | 2 | False | Awake | 171.8 | 5942.35546875 | True |
| 4 | 30 | llama.cpp | 2304 | 37.2 | 40.7 | 0 | 2 | False | Awake | 167.0 | 6042.0859375 | True |
| 4 | 31 | litert-lm-gpu | 8192 | 37.2 | 37.2 | 0 | 1 | False | Awake | 16.6 | 1158.1875 | True |
| 4 | 32 | litert-lm-gpu | 4096 | 37.4 | 37.2 | 0 | 0 | False | Awake | 16.0 | 923.87890625 | True |
| 4 | 33 | litert-lm-gpu | 2304 | 37.0 | 38.2 | 0 | 1 | False | Awake | 19.2 | 882.18359375 | True |
| 4 | 34 | litert-lm-cpu | 4096 | 36.8 | 39.6 | 0 | 1 | False | Awake | 85.2 | 4348.6171875 | True |
| 4 | 35 | litert-lm-cpu | 2304 | 37.3 | 40.0 | 0 | 2 | False | Awake | 71.3 | 4336.765625 | True |
| 4 | 36 | llama.cpp | 4096 | 37.2 | 37.2 | 0 | 0 | False | Awake | 2.1 | 1251.6484375 | True |
| 5 | 37 | llama.cpp | 4096 | 37.2 | 37.2 | 0 | 0 | False | Awake | 2.6 | 1252.1171875 | True |
| 5 | 38 | litert-lm-cpu | 2304 | 37.1 | 40.0 | 0 | 1 | False | Awake | 72.8 | 4002.421875 | True |
| 5 | 39 | litert-lm-cpu | 4096 | 37.1 | 39.9 | 0 | 2 | False | Awake | 80.6 | 5634.87890625 | True |
| 5 | 40 | litert-lm-gpu | 2304 | 37.3 | 37.1 | 0 | 0 | False | Awake | 16.5 | 966.5859375 | True |
| 5 | 41 | litert-lm-gpu | 4096 | 37.0 | 37.0 | 0 | 0 | False | Awake | 16.7 | 1018.9296875 | True |
| 5 | 42 | litert-lm-gpu | 8192 | 37.7 | 37.7 | 0 | 0 | False | Awake | 17.7 | 1121.2265625 | True |
| 5 | 43 | llama.cpp | 2304 | 37.2 | 39.8 | 0 | 1 | False | Awake | 209.5 | 6378.5 | True |
| 5 | 44 | llama.cpp | 4096 | 37.3 | 40.5 | 0 | 2 | False | Awake | 194.7 | 6154.2265625 | True |
| 5 | 45 | llama.cpp | 8192 | 37.2 | 40.4 | 0 | 2 | False | Awake | 187.0 | 6107.60546875 | True |


## Stored per-round environment probes

| round | probe start JST | probe end JST | mWakefulness | stay_on_while_plugged_in | MemAvailable KiB | battery °C | thermal status before gate | lane CPU samples |
|---|---|---|---|---|---|---|---|---|
| 1 | 09:25:49.392772 | 09:25:51.011361 | Awake | 15 | 7319560 | 31.7 | 0 | com.mlboydaisuke.edgezoo.qa: 0.0, 0.0 % |
| 2 | 09:49:33.528531 | 09:49:35.231928 | Awake | 15 | 7610532 | 39.8 | 2 | com.mlboydaisuke.edgezoo.qa: 0.0, 0.0 % |
| 3 | 10:22:16.731366 | 10:22:18.312956 | Awake | 15 | 7418360 | 37.2 | 0 | com.mlboydaisuke.edgezoo.qa: 0.0, 0.0 % |
| 4 | 10:49:09.833708 | 10:49:11.551673 | Awake | 15 | 7822908 | 40.7 | 2 | com.mlboydaisuke.edgezoo.qa: 0.0, 0.0 % |
| 5 | 11:22:59.725187 | 11:23:01.305115 | Awake | 15 | 7288568 | 37.2 | 0 | com.mlboydaisuke.edgezoo.qa: 0.0, 0.0 % |

The first sample precedes sitting launch 1; later read-only samples follow each round-state entry during the existing 30-second cooldown. Round-start thermal status is measured before the gate. Engine start/end status remains in the per-launch table. No setting, display or foreign process was changed. Raw commands and timestamps: `results/r10/round_environment.jsonl`; raw evidence: `logs/r10/roundNN_*.stdout`.
