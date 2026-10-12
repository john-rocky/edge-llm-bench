# Per-cell decode spread

Rounds 1,2,3,4,5,6; the records the ladder pools (first-ever and flagged runs out; a CPU-cap-only flag on an accelerator arm stays in, ◇ in records.md). Acceptance bar: max/min - 1 <= 15 % per warm cell, else the cell is owed a re-take.

| model | allocation | regime | n | median | min (round) | max (round) | max/min - 1 % | (max-min)/median % | <= 15 % |
|---|---|---|---|---|---|---|---|---|---|
| gemma-4-E2B-it-litert-lm | 2304 | cold | 5 | 25.77 | 25.61 (2) | 26.26 (6) | 2.5 | 2.5 | yes |
| gemma-4-E2B-it-litert-lm | 2304 | warm | 6 | 25.64 | 25.28 (4) | 27.75 (6) | 9.8 | 9.6 | yes |
| gemma-4-E2B-it-litert-lm | 4096 | cold | 5 | 25.79 | 25.29 (2) | 26.15 (4) | 3.4 | 3.3 | yes |
| gemma-4-E2B-it-litert-lm | 4096 | warm | 6 | 25.81 | 25.62 (6) | 28.33 (3) | 10.6 | 10.5 | yes |
| gemma-4-E2B-it-litert-lm | 8192 | cold | 6 | 25.50 | 24.65 (4) | 27.02 (2) | 9.6 | 9.3 | yes |
| gemma-4-E2B-it-litert-lm | 8192 | warm | 6 | 25.32 | 25.17 (4) | 25.49 (6) | 1.3 | 1.3 | yes |
