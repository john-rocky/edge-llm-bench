# Per-launch temperature and round wakefulness

One row per launch; both iterations share launch telemetry. Wakefulness comes only from round_state.jsonl, never inferred from the generic screen label. All captured rounds are retained.

| round | launch | arm | allocation | C start | C end | thermal start | thermal end | non-nominal after gate | round mWakefulness | launch s | sampled peak RSS MiB | selected round |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | llama.cpp | 4096 | 31.2 | 31.2 | 0 | 0 | False | Awake | 2.1 | 1251.85546875 | True |
| 1 | 2 | litert-lm-cpu | 2304 | 31.5 | 34.0 | 0 | 0 | False | Awake | 26.7 | 2044.73828125 | True |
| 1 | 3 | litert-lm-cpu | 4096 | 34.0 | 35.6 | 0 | 0 | False | Awake | 31.9 | 2819.70703125 | True |
| 1 | 4 | litert-lm-cpu | 8192 | 35.5 | 36.2 | 0 | 0 | False | Awake | 49.0 | 4954.82421875 | True |
| 1 | 5 | litert-lm-gpu | 2304 | 36.4 | 36.4 | 0 | 0 | False | Awake | 23.9 | 793.6015625 | True |
| 1 | 6 | litert-lm-gpu | 4096 | 36.6 | 36.6 | 0 | 0 | False | Awake | 23.4 | 752.21484375 | True |
| 1 | 7 | litert-lm-gpu | 8192 | 37.7 | 36.9 | 0 | 0 | False | Awake | 15.6 | 840.8125 | True |
| 1 | 8 | llama.cpp | 2304 | 37.3 | 38.8 | 0 | 1 | False | Awake | 117.9 | 3551.80078125 | True |
| 1 | 9 | llama.cpp | 4096 | 37.0 | 39.1 | 0 | 1 | False | Awake | 103.8 | 3938.83984375 | True |
| 1 | 10 | llama.cpp | 8192 | 37.1 | 39.5 | 0 | 1 | False | Awake | 111.2 | 4016.54296875 | True |
| 2 | 11 | llama.cpp | 8192 | 37.7 | 40.1 | 0 | 1 | False | Awake | 110.2 | 4555.234375 | True |
| 2 | 12 | llama.cpp | 4096 | 37.4 | 39.7 | 0 | 1 | False | Awake | 109.2 | 4523.31640625 | True |
| 2 | 13 | llama.cpp | 2304 | 38.0 | 40.1 | 0 | 1 | False | Awake | 109.2 | 4509.18359375 | True |
| 2 | 14 | litert-lm-gpu | 8192 | 37.6 | 37.6 | 0 | 0 | False | Awake | 12.0 | 828.96875 | True |
| 2 | 15 | litert-lm-gpu | 4096 | 37.9 | 37.9 | 0 | 1 | False | Awake | 27.6 | 865.85546875 | True |
| 2 | 16 | litert-lm-gpu | 2304 | 37.2 | 37.2 | 0 | 1 | False | Awake | 26.0 | 855.46875 | True |
| 2 | 17 | litert-lm-cpu | 8192 | 37.5 | 39.2 | 0 | 1 | False | Awake | 52.7 | 5038.859375 | True |
| 2 | 18 | litert-lm-cpu | 4096 | 37.4 | 37.8 | 0 | 1 | False | Awake | 36.6 | 2782.58984375 | True |
| 2 | 19 | litert-lm-cpu | 2304 | 37.5 | 37.1 | 0 | 1 | False | Awake | 29.4 | 2127.05859375 | True |
| 2 | 20 | llama.cpp | 4096 | 37.5 | 37.5 | 0 | 0 | False | Awake | 2.1 | 1251.66796875 | True |
| 3 | 21 | llama.cpp | 4096 | 37.2 | 37.2 | 0 | 0 | False | Awake | 2.6 | 1252.14453125 | True |
| 3 | 22 | litert-lm-cpu | 2304 | 37.1 | 38.7 | 0 | 1 | False | Awake | 33.0 | 2220.97265625 | True |
| 3 | 23 | litert-lm-cpu | 4096 | 37.4 | 39.0 | 0 | 1 | False | Awake | 38.7 | 2883.16015625 | True |
| 3 | 24 | litert-lm-cpu | 8192 | 37.5 | 39.7 | 0 | 1 | False | Awake | 52.2 | 4466.609375 | True |
| 3 | 25 | litert-lm-gpu | 2304 | 37.3 | 38.5 | 0 | 0 | False | Awake | 23.4 | 814.2109375 | True |
| 3 | 26 | litert-lm-gpu | 4096 | 38.5 | 39.0 | 0 | 1 | False | Awake | 28.6 | 865.58203125 | True |
| 3 | 27 | litert-lm-gpu | 8192 | 37.3 | 37.3 | 0 | 0 | False | Awake | 13.6 | 872.73828125 | True |
| 3 | 28 | llama.cpp | 2304 | 38.4 | 39.8 | 0 | 1 | False | Awake | 125.8 | 4224.80078125 | True |
| 3 | 29 | llama.cpp | 4096 | 37.4 | 39.8 | 0 | 1 | False | Awake | 110.8 | 4182.4296875 | True |
| 3 | 30 | llama.cpp | 8192 | 37.4 | 40.2 | 0 | 1 | False | Awake | 109.2 | 4230.57421875 | True |
| 4 | 31 | llama.cpp | 8192 | 37.4 | 40.0 | 0 | 1 | False | Awake | 109.7 | 4087.63671875 | True |
| 4 | 32 | llama.cpp | 4096 | 37.3 | 40.3 | 0 | 1 | False | Awake | 110.2 | 3968.56640625 | True |
| 4 | 33 | llama.cpp | 2304 | 37.4 | 40.2 | 0 | 1 | False | Awake | 109.7 | 4361.6328125 | True |
| 4 | 34 | litert-lm-gpu | 8192 | 37.5 | 38.0 | 0 | 0 | False | Awake | 11.9 | 811.4921875 | True |
| 4 | 35 | litert-lm-gpu | 4096 | 38.1 | 38.8 | 0 | 0 | False | Awake | 31.2 | 814.640625 | True |
| 4 | 36 | litert-lm-gpu | 2304 | 38.4 | 39.1 | 0 | 1 | False | Awake | 22.9 | 804.01171875 | True |
| 4 | 37 | litert-lm-cpu | 8192 | 37.4 | 39.8 | 0 | 1 | False | Awake | 52.2 | 4844.296875 | True |
| 4 | 38 | litert-lm-cpu | 4096 | 37.2 | 38.9 | 0 | 1 | False | Awake | 35.6 | 2824.3203125 | True |
| 4 | 39 | litert-lm-cpu | 2304 | 37.1 | 38.6 | 0 | 1 | False | Awake | 29.4 | 2127.3203125 | True |
| 4 | 40 | llama.cpp | 4096 | 37.2 | 37.2 | 0 | 0 | False | Awake | 2.1 | 1251.78125 | True |
| 5 | 41 | llama.cpp | 4096 | 37.1 | 37.1 | 0 | 0 | False | Awake | 2.1 | 1251.96875 | True |
| 5 | 42 | litert-lm-cpu | 2304 | 37.0 | 38.5 | 0 | 1 | False | Awake | 29.9 | 2122.4296875 | True |
| 5 | 43 | litert-lm-cpu | 4096 | 37.0 | 38.9 | 0 | 1 | False | Awake | 37.6 | 2913.9140625 | True |
| 5 | 44 | litert-lm-cpu | 8192 | 37.3 | 39.4 | 0 | 1 | False | Awake | 53.7 | 4730.80859375 | True |
| 5 | 45 | litert-lm-gpu | 2304 | 37.2 | 38.3 | 0 | 0 | False | Awake | 25.7 | 814.70703125 | True |
| 5 | 46 | litert-lm-gpu | 4096 | 38.0 | 38.7 | 0 | 0 | False | Awake | 24.0 | 833.625 | True |
| 5 | 47 | litert-lm-gpu | 8192 | 37.2 | 37.4 | 0 | 0 | False | Awake | 13.7 | 869.33203125 | True |
| 5 | 48 | llama.cpp | 2304 | 37.7 | 39.8 | 0 | 1 | False | Awake | 116.5 | 3723.8515625 | True |
| 5 | 49 | llama.cpp | 4096 | 37.3 | 39.6 | 0 | 1 | False | Awake | 110.7 | 4133.75 | True |
| 5 | 50 | llama.cpp | 8192 | 37.6 | 40.2 | 0 | 1 | False | Awake | 109.7 | 4555.6796875 | True |
| 6 | 51 | llama.cpp | 8192 | 37.3 | 39.6 | 0 | 1 | False | Awake | 111.8 | 4556.15625 | False |
| 6 | 52 | llama.cpp | 4096 | 37.4 | 39.8 | 0 | 1 | False | Awake | 108.7 | 4424.203125 | False |
| 6 | 53 | llama.cpp | 2304 | 37.2 | 39.5 | 0 | 1 | False | Awake | 108.6 | 4464.265625 | False |
| 6 | 54 | litert-lm-gpu | 8192 | 37.4 | 37.0 | 0 | 0 | False | Awake | 14.6 | 868.2109375 | False |
| 6 | 55 | litert-lm-gpu | 4096 | 38.0 | 37.9 | 0 | 0 | False | Awake | 28.5 | 834.84375 | False |
| 6 | 56 | litert-lm-gpu | 2304 | 37.1 | 37.6 | 0 | 0 | False | Awake | 26.0 | 834.83203125 | False |
| 6 | 57 | litert-lm-cpu | 8192 | 38.4 | 38.9 | 0 | 1 | False | Awake | 56.9 | 4965.18359375 | False |
| 6 | 58 | litert-lm-cpu | 4096 | 37.3 | 38.4 | 0 | 1 | False | Awake | 35.0 | 2824.3828125 | False |
| 6 | 59 | litert-lm-cpu | 2304 | 37.4 | 37.8 | 0 | 1 | False | Awake | 28.8 | 2122.13671875 | False |
