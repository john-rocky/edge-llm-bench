# K/MATRIX.md — Qwen3-1.7B GPU short-chat on DDP lab phones: LiteRT-LM main@HEAD (main-16ab54914) and v0.18.0, akita-35 and m1q-36

Values only. Each row is one DDP session = one job on one lab unit: its own sitting, pooled with no other row. Rows by `K/r2/matrix.py` (2026-10-16 15:54 JST): the main-16ab54914 rows from the records of `results/raw/2026-10-16-ddp-buildref-<id>-android/` through `scripts/build_summary.build_device()` in a temp tree (`results/summary/` on disk untouched); the v0.18.0 rows = the committed `results/summary/device-runs.csv` rows (HEAD ebe86aa) of `results/raw/2026-10-15-ddp-slice-<id>-android/`. Pooled = `render_leaderboard.arm_row` of each row's own runs: run 1 (firstEver) is outside the pool, and every Android run is a cold process, so the decode value is `cold_median`.

| cell | engine (label, commit) | device (id, ro.product.model, serial) | session | run 1: decode / prefill tok/s, peak MB, flags | run 2 | run 3 | pooled (arm_row): decode cold_median (n) / prefill median / peak MB median (n) / capped counted |
|---|---|---|---|---|---|---|---|
| Qwen3-1.7B GPU short-chat (wi4b32, runs=3) | main-16ab54914 (16ab5491492f21722aea7b6440ecb797c2e25031) | akita-35, Pixel 8a, 45231JEKB16401 | session-733dfb76 | 20.13 / 102.85†, 2173.4, gpuCache not-loaded, firstEver | 20.42 / 102.57†, 2168.5, gpuCache loaded | 20.46 / 102.7†, 2161.9, gpuCache loaded | 20.44 (2) / 102.63† / 2165.2 (2) / 0 |
| Qwen3-1.7B GPU short-chat (wi4b32, runs=3) | v0.18.0 (tag commit b2f686e2ed4718fb84ec398a61dd59ca0f0aff27) | akita-35, Pixel 8a, 45231JEKB16117 | session-d5585b53 | 19.42 / 28.23, 2178.2, gpuCache not-loaded, firstEver | 20.33 / 28.18, 2175.8, gpuCache loaded | 20.03 / 27.56, 2169.4, gpuCache loaded | 20.18 (2) / 27.87 / 2172.6 (2) / 0 |
| Qwen3-1.7B GPU short-chat (wi4b32, runs=3) | main-16ab54914 (16ab5491492f21722aea7b6440ecb797c2e25031) | m1q-36, SM-S942U1, RFGL319PCKN | session-0214b9f1 | 36.7 / 364.25†, 882.9, cpu-capped, cpu-capped-at-start, gpuCache not-loaded, firstEver | 37.47 / 364.19†, 1035.3, cpu-capped, cpu-capped-at-start, gpuCache loaded | 37.71 / 341.12†, 1035.1, cpu-capped, cpu-capped-at-start, gpuCache loaded | 37.59 (2) / 352.65† / 1035.2 (2) / 2 (max fall 53 %) |
| Qwen3-1.7B GPU short-chat (wi4b32, runs=3) | v0.18.0 (tag commit b2f686e2ed4718fb84ec398a61dd59ca0f0aff27) | m1q-36, SM-S942U1, RFGL319P5HN | session-9002dfea | 37.44 / 80.95, 977.3, cpu-capped, cpu-capped-at-start, gpuCache not-loaded, firstEver | 38.19 / 84.35, 1036.1, cpu-capped, cpu-capped-at-start, gpuCache loaded | 37.89 / 82.42, 1036.1, cpu-capped, cpu-capped-at-start, gpuCache loaded | 38.04 (2) / 83.38 / 1036.1 (2) / 2 (max fall 43.7 %) |

Every row ran on its own unit: akita-35 main-16ab54914 on serial 45231JEKB16401 and v0.18.0 on 45231JEKB16117; m1q-36 main-16ab54914 on RFGL319PCKN and v0.18.0 on RFGL319P5HN (`conditions.ddp.serial`; build fingerprints the same within an id: akita `BP1A.250405.007.B1/13240308`, m1q `BP4A.251205.006/S942U1UEU1AZAD`).

† The record's `metrics.promptTokensPerSecond` (summary `prefill_tps`; `android/bench/parsers.py` `parse_litert` keeps the last `Prefill Speed` and sums the `Prefill Turn` token counts): main-16ab54914 prints two prefill turns per run, so its value is turn 2's rate (133 tokens on akita-35, 150 on m1q-36) and its `promptTokenCount` 152 / 169; v0.18.0 prints one turn (19 tokens). Turn 1 of every run is in the table below.

## BenchmarkInfo turns per run (`ddp-out/run<i>.engine.txt`; `K/r2/turns.py` → `K/r2/turns.md`)

| row | run | prefill turns: tokens in ms = tok/s | decode: tokens = tok/s | TTFT s | Init Executor ms | printed reply: Qwen3 tokens, first words |
|---|---|---|---|---|---|---|
| akita-35 main-16ab54914 | 1 | turn 1: 19 in 670.86 = 28.32; turn 2: 133 in 1293.08 = 102.85 | 650 = 20.13 | 0.72 | 16042.93 | 130, "On-device AI means using small, powerful …" |
| akita-35 main-16ab54914 | 2 | turn 1: 19 in 681.28 = 27.89; turn 2: 133 in 1296.72 = 102.57 | 650 = 20.42 | 0.73 | 7229.36 | 130, "On-device AI means using small, powerful …" |
| akita-35 main-16ab54914 | 3 | turn 1: 19 in 678.33 = 28.01; turn 2: 133 in 1295.01 = 102.7 | 650 = 20.46 | 0.73 | 6306.83 | 130, "On-device AI means using small, powerful …" |
| akita-35 v0.18.0 | 1 | turn 1: 19 in 673.01 = 28.23 | 526 = 19.42 | 0.72 | 15144.76 | 99, "On-device AI is like having a …" |
| akita-35 v0.18.0 | 2 | turn 1: 19 in 674.19 = 28.18 | 526 = 20.33 | 0.72 | 7142.58 | 99, "On-device AI is like having a …" |
| akita-35 v0.18.0 | 3 | turn 1: 19 in 689.47 = 27.56 | 526 = 20.03 | 0.74 | 6291.00 | 99, "On-device AI is like having a …" |
| m1q-36 main-16ab54914 | 1 | turn 1: 19 in 227.85 = 83.39; turn 2: 150 in 411.81 = 364.25 | 849 = 36.7 | 0.26 | 8234.51 | 147, "On-device AI é quando o computador …" |
| m1q-36 main-16ab54914 | 2 | turn 1: 19 in 228.6 = 83.12; turn 2: 150 in 411.87 = 364.19 | 849 = 37.47 | 0.26 | 6115.54 | 147, "On-device AI é quando o computador …" |
| m1q-36 main-16ab54914 | 3 | turn 1: 19 in 226.44 = 83.91; turn 2: 150 in 439.73 = 341.12 | 849 = 37.71 | 0.25 | 5958.77 | 147, "On-device AI é quando o computador …" |
| m1q-36 v0.18.0 | 1 | turn 1: 19 in 234.71 = 80.95 | 536 = 37.44 | 0.26 | 8071.24 | 118, "On-device AI is like having a …" |
| m1q-36 v0.18.0 | 2 | turn 1: 19 in 225.24 = 84.35 | 536 = 38.19 | 0.25 | 6059.35 | 118, "On-device AI is like having a …" |
| m1q-36 v0.18.0 | 3 | turn 1: 19 in 230.52 = 82.42 | 536 = 37.89 | 0.26 | 5858.56 | 118, "On-device AI is like having a …" |

## Notes

- Turn 2 of main-16ab54914 has the printed reply's Qwen3 token count plus 3 on both units (130 + 3 = 133, 147 + 3 = 150; `K/r2/reply-tokens.txt`, tokenizer = the cached `Qwen/Qwen3-1.7B` `tokenizer.json`). What the engine prefills in that turn is not in the log (unverified). main-16ab54914 also prints `TextToTokenIds Turns (Total 0 turns)`; v0.18.0 prints one 19-token TextToTokenIds turn.
- The decode rates are over 650 (akita-35) and 849 (m1q-36) tokens on main-16ab54914 and 526 / 536 on v0.18.0; the printed replies hold 130 / 147 and 99 / 118 of them. `--max_output_tokens=128` stops neither engine (as on 10-15, D6 handoff §6).
- Replies (prompt `prompts/text/short-chat.txt`, "Explain what on-device AI means in simple terms."): main-16ab54914 answers in English on akita-35 and in Portuguese on m1q-36 (on-topic, the same text in runs 1-3); v0.18.0 answers in English on both ids (the same text in runs 1-3).
- Engines: v0.18.0 = tag commit b2f686e2e (2026-10-06); main-16ab54914 = 16ab5491492f (2026-10-15T22:43:05-07:00). The two have diverged: main holds 180 commits after the merge base b8a4e4c81, v0.18.0 holds 4 release-branch commits main does not (`K/r2/compare.txt`, GitHub compare API).
- The same inputs in all four rows: model `Qwen3-1.7B_dynamic_wi4b32_afp32.litertlm` sha256 2a72330b… (977,184,032 bytes), prompt sha256 870aafb9…, wrapper `android/ddp/ddp_cell.sh` sha256 8e2880f6…, command `./litert_lm_main --backend=gpu --model_path=… --input_prompt_file=… --max_output_tokens=128 --async=false`, runs=3, cooldown 120 s, `--timeout=1080`, `--thermal_wait=600`. One run condition is not the same: m1q-36's CPU-cap wait before each run was 300 s on 10-15 (`--cpucap_wait=300`, timed out before every run) and 0 s now (`android/ddp/devices.json` D14); akita-35's is 300 s in both.
- m1q-36 runs carry `cpu-capped` and `cpu-capped-at-start` on both engines; litert-lm-gpu is a `CPU_CAP_EXEMPT_ARMS` arm, so they pool, counted, with the largest fall among the pooled runs (main-16ab54914 run 3: policy6 2227.2 / 4742.4 MHz; v0.18.0 run 2: policy6 2668.8 / 4742.4 MHz).
- Raw-log structure, run 1 of each row (`K/r2/log-lines.txt`): GPU delegate `LITERT_CL` 994/994 (prefill_128), 994/994 (prefill_1024), 936/936 (decode), 1 partition each; `RegisterAccelerator` LiteRT GPU ×3 and CpuAccelerator ×3; NPU-not-found warnings ×3; E / F lines 0; `Invalid decode` 0; the same set of log sources in both engines (only their line numbers moved).
