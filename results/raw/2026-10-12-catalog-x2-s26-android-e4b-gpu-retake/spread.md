# Per-cell decode spread

Rounds 1,2,3,4; the records the ladder pools (first-ever and flagged runs out; a CPU-cap-only flag on an accelerator arm stays in, ◇ in records.md). Acceptance bar: max/min - 1 <= 15 % per warm cell, else the cell is owed a re-take.

| model | allocation | regime | n | median | min (round) | max (round) | max/min - 1 % | (max-min)/median % | <= 15 % |
|---|---|---|---|---|---|---|---|---|---|
| gemma-4-E4B-it-litert-lm | 2304 | cold | 3 | 15.06 | 14.86 (4) | 15.43 (2) | 3.8 | 3.8 | yes |
| gemma-4-E4B-it-litert-lm | 2304 | warm | 4 | 15.14 | 13.22 (4) | 15.39 (2) | 16.4 | 14.3 | NO |
| gemma-4-E4B-it-litert-lm | 4096 | cold | 3 | 15.11 | 14.78 (3) | 15.58 (2) | 5.4 | 5.3 | yes |
| gemma-4-E4B-it-litert-lm | 4096 | warm | 4 | 14.76 | 13.66 (4) | 14.93 (3) | 9.3 | 8.6 | yes |
| gemma-4-E4B-it-litert-lm | 8192 | cold | 3 | 14.47 | 14.21 (3) | 15.23 (4) | 7.2 | 7.0 | yes |
| gemma-4-E4B-it-litert-lm | 8192 | warm | 4 | 14.54 | 13.93 (4) | 14.57 (1) | 4.6 | 4.4 | yes |
