# Iteration 2 vs iteration 1 of the Android 1K launches (stored records, 2026-10-20)

## What a launch is

The dashboard's Android LiteRT-LM CPU and GPU rows of the 1K text task (`long-context-1024-gen256`)
run one `litert_lm_advanced_main` process per launch, with the task's prompt file and these flags
(`android/bench/run_cell.py` lines 686-694, `docs/dashboard-cells-v1.md` lines 598-605; the zero
token counts keep the real prompt):

```
./litert_lm_advanced_main --backend=<cpu|gpu> --model_path=<model> --input_prompt_file=<prompt>
  --max_num_tokens=2048 --max_output_tokens=256 --num_iterations=2 --async=false --benchmark
  --benchmark_prefill_tokens=0 --benchmark_decode_tokens=0 --use_session=false
```

One launch writes two records: iteration 1 is the first Conversation of the fresh process (`coldRun`
true), iteration 2 a fresh Conversation on the engine that process has already loaded (`coldRun`
false) (`run_cell.py` line 1562, `docs/dashboard-cells-v1.md` lines 624-626). The first launch per
model and backend on a phone builds the engine caches and is marked `firstEver` (`run_cell.py` lines
1439-1440); every later launch starts with the model file and the caches already on the phone. The
two iterations run back to back: the binary has no flag for a pause between them, and its iteration
loop inserts none (`results/raw/2026-10-09-ddp-s25ultra-gemma3-1b-warm/NOTES.md` lines 22-24).
Thermal state and the CPU clock-ceiling flag are read per launch, so both records of a launch carry
the same values (`run_cell.py` lines 1553-1561).

## How the pairs were formed

`tools/iteration_pairs.pl` reads `results/summary/device-runs.csv`, keeps the Android
`litert-lm-cpu` and `litert-lm-gpu` records of the 1K text task, and pairs the two records of each
launch by their shared timestamp. It drops the cache-build launches (`first_ever`, 59 here),
launches without a prefill rate in both records (0) and launches whose prompt came out under 1,000
tokens (0 here; a chat template that dropped the user turn leaves 8 or 9 prompt tokens). 124 pairs
remain. The table below was printed from the summary as committed at `e9c1d2bb` (2026-10-20 02:37
JST). The summary is rebuilt from the committed campaigns at every results commit, so a later run
prints that day's table:

```
perl tools/iteration_pairs.pl results/summary/device-runs.csv
# this table: git show e9c1d2bb:results/summary/device-runs.csv > /tmp/summary.csv && perl tools/iteration_pairs.pl /tmp/summary.csv
```

Each row is one device, arm, model and LiteRT-LM version; the token columns read iteration 1 /
iteration 2, and `cpu_capped` lists the values found among the row's launches: `true` when a CPU
the engine ran on sat below its hardware clock maximum at some read during the launch, `false`
when the ceilings were read and none did, `-` when they were not read (Android records before
2026-10-07; `scripts/build_summary.py` lines 185-189, `methodology/fairness-rules.md` §13). It does
not show how far a ceiling fell.

## The table

| device | arm | model | engine version | pairs | prefill it1 median | prefill it2 median | prefill it2/it1 median [min-max] | decode it2/it1 median | prompt / gen tokens | cpu_capped |
|---|---|---|---|---:|---:|---:|---|---:|---|---|
| Pixel 8a (DDP akita-35) | litert-lm-cpu | litert-community/Qwen3-1.7B | v0.18.0 | 2 | 85.7 | 76.0 | 0.89 [0.88-0.89] | 0.98 | 1338/1338 / 256/256 | false |
| Pixel 8a (DDP akita-35) | litert-lm-cpu | litert-community/gemma-4-E2B-it-litert-lm | v0.18.0 | 2 | 186.2 | 155.5 | 0.84 [0.82-0.85] | 0.70 | 1106/1106 / 256/256 | true |
| Pixel 8a (DDP akita-35) | litert-lm-gpu | litert-community/Qwen3-1.7B | v0.18.0 | 2 | 238.7 | 240.2 | 1.01 [1.00-1.01] | 1.05 | 1338/1338 / 256/256 | false |
| Pixel 8a (DDP akita-35) | litert-lm-gpu | litert-community/gemma-4-E2B-it-litert-lm | v0.18.0 | 2 | 1067.3 | 1086.2 | 1.02 [1.01-1.02] | 1.07 | 1106/1106 / 256/256 | false |
| Pixel 8a | litert-lm-cpu | litert-community/Qwen3-0.6B/dynamic_wi4b32_afp32_r0805meta018 | v0.18.0 | 2 | 101.9 | 96.9 | 0.95 [0.94-0.97] | 0.86 | 1338/1338 / 256/256 | true |
| Pixel 8a | litert-lm-cpu | litert-community/Qwen3-0.6B | v0.16.0 | 2 | 102.3 | 80.5 | 0.79 [0.59-0.98] | 0.78 | 1339/1339 / 256/256 | - |
| Pixel 8a | litert-lm-cpu | litert-community/Qwen3-0.6B | v0.18.0 | 5 | 96.9 | 93.8 | 0.96 [0.93-1.07] | 0.87 | 1338/1338 / 256/256 | false;true |
| Pixel 8a | litert-lm-cpu | litert-community/Qwen3-1.7B | v0.16.0 | 2 | 64.3 | 42.0 | 0.65 [0.65-0.66] | 0.76 | 1338/1338 / 256/256 | - |
| Pixel 8a | litert-lm-cpu | litert-community/Qwen3-1.7B | v0.18.0 | 5 | 69.9 | 36.8 | 0.51 [0.46-0.81] | 0.64 | 1338/1338 / 256/256 | true |
| Pixel 8a | litert-lm-cpu | litert-community/gemma-4-E2B-it-litert-lm | v0.16.0 | 2 | 132.1 | 162.1 | 1.23 [1.18-1.28] | 1.07 | 1106/1106 / 256/256 | - |
| Pixel 8a | litert-lm-cpu | litert-community/gemma-4-E2B-it-litert-lm | v0.18.0 | 2 | 172.1 | 171.1 | 0.99 [0.98-1.01] | 0.99 | 1106/1106 / 256/256 | false |
| Pixel 8a | litert-lm-gpu | litert-community/Qwen3-0.6B/dynamic_wi4b32_afp32_r0805meta018 | v0.18.0 | 2 | 562.3 | 574.1 | 1.02 [1.02-1.02] | 1.17 | 1338/1338 / 256/256 | false |
| Pixel 8a | litert-lm-gpu | litert-community/Qwen3-0.6B | v0.16.0 | 2 | 477.9 | 486.7 | 1.02 [1.02-1.02] | 1.00 | 1339/1339 / 256/256 | - |
| Pixel 8a | litert-lm-gpu | litert-community/Qwen3-0.6B | v0.18.0 | 5 | 549.4 | 562.8 | 1.03 [1.02-1.03] | 1.05 | 1338/1338 / 256/256 | false |
| Pixel 8a | litert-lm-gpu | litert-community/Qwen3-1.7B | v0.16.0 | 2 | 237.7 | 240.1 | 1.01 [1.01-1.01] | 1.00 | 1338/1338 / 200/256 | - |
| Pixel 8a | litert-lm-gpu | litert-community/Qwen3-1.7B | v0.18.0 | 2 | 233.5 | 234.2 | 1.00 [1.00-1.00] | 1.11 | 1338/1338 / 256/256 | false;true |
| Pixel 8a | litert-lm-gpu | litert-community/gemma-4-E2B-it-litert-lm | v0.16.0 | 2 | 737.7 | 1035.3 | 1.63 [1.03-2.23] | 1.02 | 1106/1106 / 256/256 | - |
| Pixel 8a | litert-lm-gpu | litert-community/gemma-4-E2B-it-litert-lm | v0.18.0 | 2 | 1010.7 | 1039.0 | 1.03 [1.02-1.03] | 1.05 | 1106/1106 / 256/256 | false |
| SM-S942Q | litert-lm-cpu | litert-community/Qwen3-0.6B | v0.16.0 | 2 | 247.8 | 214.2 | 0.86 [0.86-0.87] | 0.85 | 1339/1339 / 256/256 | - |
| SM-S942Q | litert-lm-cpu | litert-community/Qwen3-0.6B | v0.18.0 | 2 | 326.4 | 214.5 | 0.66 [0.65-0.66] | 0.80 | 1338/1338 / 256/256 | true |
| SM-S942Q | litert-lm-cpu | litert-community/Qwen3-1.7B | v0.16.0 | 2 | 258.8 | 217.1 | 0.84 [0.81-0.87] | 0.98 | 1338/1338 / 256/256 | - |
| SM-S942Q | litert-lm-cpu | litert-community/Qwen3-4B | v0.16.0 | 4 | 43.1 | 39.0 | 0.85 [0.76-0.99] | 1.00 | 1339/1339 / 256/256 | -;true |
| SM-S942Q | litert-lm-cpu | litert-community/gemma-4-E2B-it-litert-lm | v0.16.0 | 2 | 400.3 | 302.2 | 0.75 [0.71-0.80] | 0.81 | 1106/1106 / 256/256 | - |
| SM-S942Q | litert-lm-cpu | litert-community/gemma-4-E2B-it-litert-lm | v0.18.0 | 2 | 422.4 | 268.5 | 0.64 [0.63-0.64] | 0.73 | 1106/1106 / 256/256 | true |
| SM-S942Q | litert-lm-cpu | litert-community/gemma-4-E4B-it-litert-lm | v0.16.0 | 6 | 125.0 | 94.9 | 0.75 [0.68-0.80] | 1.06 | 1106/1106 / 106/106 | -;true |
| SM-S942Q | litert-lm-gpu | litert-community/Qwen3-0.6B | v0.16.0 | 2 | 1631.2 | 1639.9 | 1.01 [1.00-1.01] | 0.96 | 1339/1339 / 256/256 | - |
| SM-S942Q | litert-lm-gpu | litert-community/Qwen3-0.6B | v0.18.0 | 5 | 1888.8 | 1913.2 | 1.01 [1.01-1.02] | 1.06 | 1338/1338 / 256/256 | true |
| SM-S942Q | litert-lm-gpu | litert-community/Qwen3-1.7B | v0.16.0 | 2 | 975.3 | 983.1 | 1.01 [1.00-1.02] | 1.01 | 1338/1338 / 116/256 | - |
| SM-S942Q | litert-lm-gpu | litert-community/Qwen3-4B | v0.16.0 | 4 | 324.0 | 319.9 | 0.99 [0.58-0.99] | 0.96 | 1339/1339 / 256/256 | -;true |
| SM-S942Q | litert-lm-gpu | litert-community/gemma-4-E2B-it-litert-lm | v0.16.0 | 2 | 2570.4 | 3353.3 | 1.43 [1.01-1.85] | 0.93 | 1106/1106 / 256/256 | - |
| SM-S942Q | litert-lm-gpu | litert-community/gemma-4-E2B-it-litert-lm | v0.18.0 | 2 | 3400.5 | 3357.8 | 0.99 [0.98-1.00] | 1.04 | 1106/1106 / 256/256 | true |
| SM-S942Q | litert-lm-gpu | litert-community/gemma-4-E4B-it-litert-lm | v0.16.0 | 6 | 1025.4 | 1231.6 | 1.16 [0.90-1.37] | 0.97 | 1106/1106 / 256/256 | -;true |
| SM-S942U1 (DDP m1q-36) | litert-lm-cpu | litert-community/Qwen3-1.7B | v0.18.0 | 6 | 276.0 | 276.9 | 1.01 [0.76-1.09] | 0.98 | 1338/1338 / 256/256 | true |
| SM-S942U1 (DDP m1q-36) | litert-lm-cpu | litert-community/Qwen3-4B | v0.18.0 | 4 | 52.5 | 47.2 | 0.92 [0.88-0.94] | 0.99 | 1338/1338 / 256/256 | true |
| SM-S942U1 (DDP m1q-36) | litert-lm-cpu | litert-community/gemma-4-E2B-it-litert-lm | v0.18.0 | 4 | 364.1 | 382.3 | 1.05 [1.04-1.08] | 0.99 | 1106/1106 / 256/256 | true |
| SM-S942U1 (DDP m1q-36) | litert-lm-cpu | litert-community/gemma-4-E4B-it-litert-lm | v0.18.0 | 4 | 134.7 | 97.1 | 0.72 [0.71-0.73] | 0.94 | 1106/1106 / 106/106 | true |
| SM-S942U1 (DDP m1q-36) | litert-lm-gpu | litert-community/Qwen3-1.7B | v0.18.0 | 6 | 808.7 | 826.2 | 1.02 [1.00-1.03] | 1.05 | 1338/1338 / 256/256 | true |
| SM-S942U1 (DDP m1q-36) | litert-lm-gpu | litert-community/Qwen3-4B | v0.18.0 | 4 | 278.2 | 279.1 | 1.00 [0.99-1.01] | 1.03 | 1338/1338 / 256/256 | true |
| SM-S942U1 (DDP m1q-36) | litert-lm-gpu | litert-community/gemma-4-E2B-it-litert-lm | v0.18.0 | 4 | 2703.1 | 2825.2 | 1.05 [1.01-1.11] | 1.04 | 1106/1106 / 256/256 | true |
| SM-S942U1 (DDP m1q-36) | litert-lm-gpu | litert-community/gemma-4-E4B-it-litert-lm | v0.18.0 | 4 | 1020.9 | 1042.8 | 1.02 [1.00-1.05] | 1.03 | 1106/1106 / 256/256 | true |

pairs 124; launches dropped: first_ever 59, incomplete 0, prompt under 1,000 tokens 0

## Reading

- CPU on the two attached phones (`SM-S942Q` = Galaxy S26, and `Pixel 8a`; `(DDP …)` rows are
  Developer Device Platform pool phones): 14 rows, 7 per phone. The median prefill ratio is below 1
  in 12 of them, 0.51 to 0.96; the other two are 0.99 (Pixel 8a, Gemma 4 E2B, v0.18.0) and 1.23
  (Pixel 8a, Gemma 4 E2B, v0.16.0). All 7 Galaxy S26 rows are below 1 (0.64 to 0.86; its v0.18.0
  rows are the lowest, 0.64 and 0.66). The median decode ratio on these 14 rows runs from 0.64 to
  1.07.
- GPU on the attached phones: 14 rows, 11 of them between 0.99 and 1.03; the other three are above
  1: 1.16 (Galaxy S26, Gemma 4 E4B, v0.16.0), 1.43 (Galaxy S26, Gemma 4 E2B, v0.16.0) and 1.63
  (Pixel 8a, Gemma 4 E2B, v0.16.0). In the last two rows one of the two launches prefilled
  iteration 1 at about half of iteration 2 (Galaxy S26, 2026-10-06 07:46 UTC: 1,799 then 3,329
  tok/s; Pixel 8a, 2026-10-06 22:33 UTC: 462 then 1,032) and the other launch read both iterations
  alike.
- `cpu_capped` on the attached phones' CPU rows: the ceilings were read in 8 of the 14 rows (every
  v0.18.0 row, and the two v0.16.0 rows with launches after 2026-10-07, Galaxy S26 Qwen3-4B and
  Gemma 4 E4B). 7 of those 8 include launches marked `true`, and in 4 every launch is (Pixel 8a
  Qwen3-0.6B dynamic and Qwen3-1.7B, Galaxy S26 Qwen3-0.6B and Gemma 4 E2B, all v0.18.0); the row
  with no launch marked is Pixel 8a Gemma 4 E2B v0.18.0. The other 6 rows read `-`.
- Pool phones: the Galaxy S26 pool (`SM-S942U1`, `m1q-36`) reads 1.01, 0.92, 1.05 and 0.72 on CPU
  (Qwen3-1.7B, Qwen3-4B, Gemma 4 E2B, Gemma 4 E4B), and every one of its launches started with the
  CPU clock ceiling already below its maximum (every record carries `cpu-capped-at-start`;
  `android/ddp/devices.json` note on `m1q-36` for 2026-10-15, `docs/ddp-integration.md` line 456 for
  2026-10-18). The Pixel 8a pool (`akita-35`) reads 0.89 (no launch marked) and 0.84 on CPU, 1.01
  and 1.02 on GPU.
- Rows hold 2 to 6 pairs. Prompts are 1,106 tokens (Gemma 4) or 1,338 / 1,339 (Qwen3). Both
  iterations generate 256 tokens except in the Gemma 4 E4B CPU rows (106 in both), Pixel 8a GPU
  Qwen3-1.7B v0.16.0 (200 / 256) and Galaxy S26 GPU Qwen3-1.7B v0.16.0 (116 / 256).
- No cause is established. Thermal state and the CPU clock-ceiling flag are recorded per launch,
  not per iteration, and the two iterations run back to back with no pause, so nothing in the
  table separates running second from anything else that changes during a launch.

## Related

- Galaxy S25 Ultra pool, 2026-10-09: three CPU sessions of Gemma 3 1B int4 through the LiteRT CLI,
  forced 1024-token prefill and 256-token decode, `--num-iterations 2`. In the process that starts
  with the caches present, iteration 1 prefilled at 332.3 tok/s (median of 3, 323.6-350.0) and
  iteration 2 at 310.5 (229.5-322.7) ([table-aligned.md](https://github.com/john-rocky/edge-llm-bench/blob/main/results/raw/2026-10-09-ddp-s25ultra-gemma3-1b-warm/table-aligned.md),
  first table, rows "measured (caches present)").
- Galaxy S25 Ultra pool, 2026-10-08: the Gemma 4 E2B sessions ran `--num-iterations 1 --warmup-runs 0
  --max-num-tokens 4096`. The CLI's first process builds the caches and the measured process runs
  one iteration with them present, so their prefill is the first prefill of a fresh process
  (`results/raw/2026-10-07-ddp-s25ultra-lm-v1/NOTES.md` line 219).
- The dashboard's forced-1024 rows (`native-benchmark-1024x256`) pass no `--num_iterations`, so
  each launch runs one iteration, the flag's default (`run_cell.py` lines 676-684;
  `runtime/engine/shared_flags.cc` in LiteRT-LM).
- The dashboard's Android numbers today: decode is the median of the iteration 1 records
  (`scripts/render_dashboard.py` line 80, `REGIME` android = cold); prefill is the median over both
  iterations' records (`scripts/render_leaderboard.py` lines 197-198 and 228), iteration 2 of the
  cache-build launch included, as that record carries no `firstEver` (`run_cell.py` lines 1563-1564).
