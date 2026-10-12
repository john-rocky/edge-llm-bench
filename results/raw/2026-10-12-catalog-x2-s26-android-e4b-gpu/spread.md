# Per-cell decode spread

Rounds 1,2,3,4; the records the ladder pools (first-ever and flagged runs out; a CPU-cap-only flag on an accelerator arm stays in, ◇ in records.md). Acceptance bar: max/min - 1 <= 15 % per warm cell, else the cell is owed a re-take.

| model | allocation | regime | n | median | min (round) | max (round) | max/min - 1 % | (max-min)/median % | <= 15 % |
|---|---|---|---|---|---|---|---|---|---|
| gemma-4-E4B-it-litert-lm | 2304 | cold | 4 | 15.00 | 14.61 (4) | 15.61 (3) | 6.8 | 6.7 | yes |
| gemma-4-E4B-it-litert-lm | 2304 | warm | 4 | 14.89 | 13.45 (2) | 15.42 (1) | 14.6 | 13.2 | yes |
| gemma-4-E4B-it-litert-lm | 4096 | cold | 3 | 15.11 | 14.70 (3) | 15.11 (4) | 2.8 | 2.7 | yes |
| gemma-4-E4B-it-litert-lm | 4096 | warm | 4 | 14.96 | 14.71 (1) | 15.18 (2) | 3.2 | 3.1 | yes |
| gemma-4-E4B-it-litert-lm | 8192 | cold | 4 | 14.25 | 14.14 (3) | 14.70 (4) | 4.0 | 3.9 | yes |
| gemma-4-E4B-it-litert-lm | 8192 | warm | 4 | 12.92 | 11.01 (3) | 14.45 (2) | 31.2 | 26.6 | NO |
