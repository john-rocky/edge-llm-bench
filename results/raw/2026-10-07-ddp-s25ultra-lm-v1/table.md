# LiteRT-LM on DDP Galaxy S25 Ultra (pa3q-35), CLI defaults (two cpu rows at max_num_tokens 2048) — 2026-10-07

One row per (model file, backend): one `litert benchmark <bundle>.litertlm --ddp --device pa3q-35 --cpu|--gpu` session
(litert-cli-nightly, LiteRT-LM's `litert_lm_advanced_main` from `gs://litert/binaries/latest/android_arm64/litert_lm/`,
benchmark mode: 1024 prefill tokens, 256 decode tokens, 5 iterations in the measured process). `--max_num_tokens` is
the CLI default 1280, except the two Gemma 4 cpu rows, which ran with `--max-num-tokens 2048`: at 1280 those two
bundles do not allocate on cpu (below). The tokens column says which row ran at which value; a 1280 row and a 2048 row
are different conditions.
Rates are the median over iterations 2–5 (`collect_lm.py`, google-ai-edge/litert-samples `benchmark/driver` at 17e5db06);
init is the measured process's one engine creation, with the cache files the first process wrote; peak memory is the
binary's `peak_mem_mb`. Benchmark mode decodes no text, so no row has a text check. Rows: `collected/sessions.jsonl`.

| model | file | backend | prefill tok/s | decode tok/s | TTFT s | init ms | peak mem MB | tokens (prefill / decode / max) | iterations | session |
|---|---|---|---:|---:|---:|---:|---:|---|---|---|
| litert-community/Qwen3-0.6B | qwen3_0_6b_mixed_int4.litertlm | cpu | 273.7 | 8.12 | 3.867 | 316 | 2902.5 | 1024 / 256 / 1280 | 5 (1 warm-up) | session-a7c5ae10 |
| litert-community/Qwen3-0.6B | qwen3_0_6b_mixed_int4.litertlm | gpu (OpenCL) | 1832.8 | 70.06 | 0.573 | 2539 | 617.9 | 1024 / 256 / 1280 | 5 (1 warm-up) | session-10701be8 |
| litert-community/Qwen3-1.7B | Qwen3_1.7B.litertlm | cpu | 105.4 | 11.39 | 9.803 | 321 | 2827.6 | 1024 / 256 / 1280 | 5 (1 warm-up) | session-75cdf64a |
| litert-community/Qwen3-1.7B | Qwen3_1.7B.litertlm | gpu (OpenCL) | 596.4 | 17.68 | 1.773 | 4276 | 839.8 | 1024 / 256 / 1280 | 5 (1 warm-up) | session-965ba2f4 |
| litert-community/Qwen3-4B | qwen3_4b_mixed_int4.litertlm | cpu | 45.3 | 5.63 | 22.805 | 3017 | 7336.6 | 1024 / 256 / 1280 | 5 (1 warm-up) | session-fb63c76d |
| litert-community/Qwen3-4B | qwen3_4b_mixed_int4.litertlm | gpu (OpenCL) | 330.0 | 18.00 | 3.159 | 13818 | 1578.5 | 1024 / 256 / 1280 | 5 (1 warm-up) | session-981d881c |
| litert-community/gemma-4-E2B-it-litert-lm | gemma-4-E2B-it.litertlm | cpu | 252.0 | 27.57 | 4.147 | 226 | 1853.7 | 1024 / 256 / 2048 | 5 (1 warm-up) | session-52983393 |
| litert-community/gemma-4-E2B-it-litert-lm | gemma-4-E2B-it.litertlm | gpu (OpenCL) | 2020.1 | 26.36 | 0.545 | 2510 | 692.6 | 1024 / 256 / 1280 | 5 (1 warm-up) | session-0d1cde8d |
| litert-community/gemma-4-E4B-it-litert-lm | gemma-4-E4B-it.litertlm | cpu | 81.8 | 16.60 | 12.578 | 337 | 3886.6 | 1024 / 256 / 2048 | 5 (1 warm-up) | session-e0cf5e62 |
| litert-community/gemma-4-E4B-it-litert-lm | gemma-4-E4B-it.litertlm | gpu (OpenCL) | 1355.8 | 21.41 | 0.802 | 5164 | 894.8 | 1024 / 256 / 1280 | 5 (1 warm-up) | session-e06d4f0b |

Per-iteration values and spread (max/min - 1 over the iterations after the warm-up one):

| model | backend | prefill tok/s per iteration | spread | decode tok/s per iteration | spread | session date (device clock) | device build |
|---|---|---|---:|---|---:|---|---|
| Qwen3-0.6B | cpu | 288.6, 212.4, 323.2, 267.9, 279.4 | 52.1% | 8.67, 7.95, 8.86, 7.90, 8.29 | 12.1% | Tue Oct  6 08:56:56 PDT 2026 | SM-S938U1 (pa3q), S938U1UEU1AYB3_OYM1AYB3 |
| Qwen3-0.6B | gpu | 1844.8, 1842.9, 1828.8, 1836.9, 1823.5 | 1.1% | 69.20, 69.94, 71.55, 70.19, 69.84 | 2.4% | Tue Sep 29 19:20:23 PDT 2026 | SM-S938U1 (pa3q), S938U1UEU2AYD9_OYM2AYD9 |
| Qwen3-1.7B | cpu | 150.2, 105.5, 118.3, 105.4, 104.9 | 12.8% | 12.36, 11.43, 11.26, 11.34, 11.73 | 4.1% | Tue Oct  6 08:45:52 PDT 2026 | SM-S938U1 (pa3q), S938U1UEU1AYB3_OYM1AYB3 |
| Qwen3-1.7B | gpu | 601.9, 598.2, 599.4, 594.6, 560.7 | 6.9% | 17.50, 17.78, 17.78, 17.57, 17.51 | 1.6% | Tue Oct  6 10:06:29 PDT 2026 | SM-S938U1 (pa3q), S938U1UEU2AYD9_OYM2AYD9 |
| Qwen3-4B | cpu | 39.6, 49.3, 41.2, 44.1, 46.4 | 19.7% | 4.25, 4.88, 5.58, 6.13, 5.69 | 25.5% | Tue Oct  6 09:24:24 PDT 2026 | SM-S938U1 (pa3q), S938U1UEU1AYB3_OYM1AYB3 |
| Qwen3-4B | gpu | 340.6, 330.4, 330.2, 329.7, 277.7 | 19.0% | 17.77, 18.27, 18.32, 17.73, 17.45 | 5.0% | Tue Oct  6 09:40:07 PDT 2026 | SM-S938U1 (pa3q), S938U1UEU1AYB3_OYM1AYB3 |
| gemma-4-E2B-it-litert-lm | cpu | 363.9, 221.2, 281.9, 279.1, 225.0 | 27.5% | 30.34, 26.52, 30.77, 28.63, 26.51 | 16.1% | Tue Oct  6 10:47:55 PDT 2026 | SM-S938U1 (pa3q), S938U1UEU2AYD9_OYM2AYD9 |
| gemma-4-E2B-it-litert-lm | gpu | 3380.2, 2417.9, 1977.5, 2014.6, 2025.6 | 22.3% | 30.71, 26.61, 26.25, 26.39, 26.33 | 1.3% | Tue Oct  6 09:15:32 PDT 2026 | SM-S938U1 (pa3q), S938U1UEU2AYD9_OYM2AYD9 |
| gemma-4-E4B-it-litert-lm | cpu | 131.2, 80.8, 80.9, 82.8, 83.3 | 3.1% | 17.66, 16.62, 16.56, 16.58, 16.62 | 0.3% | Tue Oct  6 10:59:29 PDT 2026 | SM-S938U1 (pa3q), S938U1UEU1AYB3_OYM1AYB3 |
| gemma-4-E4B-it-litert-lm | gpu | 1375.0, 1358.3, 1362.6, 1353.2, 1342.7 | 1.5% | 20.98, 21.42, 21.41, 21.41, 21.25 | 0.8% | Tue Oct  6 09:58:59 PDT 2026 | SM-S938U1 (pa3q), S938U1UEU2AYD9_OYM2AYD9 |

Binary: latest/android_arm64/litert_lm/litert_lm_advanced_main, sha256 adac974bea147273b5bc64232d808905667eee69587161368146680df92e2d06

CLI: litert-cli-nightly 0.3.0.dev20261006 (the twelve sessions of 2026-10-07); session-10701be8 ran on 2026-09-30 with 0.3.0.dev20260929, whose `litert_cli` package is byte-identical to 0.3.0.dev20261006.

Bundles (sha256 from each session's provenance.txt):

- Qwen3_1.7B.litertlm 66064a4e9269cb693e124c4e3040bcb8a446b10bca42663896329495add3861c
- gemma-4-E2B-it.litertlm 181938105e0eefd105961417e8da75903eacda102c4fce9ce90f50b97139a63c
- gemma-4-E4B-it.litertlm 0b2a8980ce155fd97673d8e820b4d29d9c7d99b8fa6806f425d969b145bd52e0
- qwen3_0_6b_mixed_int4.litertlm 7900eb4e7362d88c58782c6f9999bb7a129e03544aa98b8f338ea0cc5d8c22c1
- qwen3_4b_mixed_int4.litertlm f0794bc77efeaaf4f7af815f04c483b19b8f2ae4a102cef1b7b760a25848a18e

The first process of each session (it starts without cache files, runs one prefill and one decode, and writes the caches;
read from the log, not from metrics.pb) beside the measured process:

| model | backend | first process: init ms (no caches) | prefill tok/s | decode tok/s | measured process: init ms (caches present) | median prefill tok/s | median decode tok/s |
|---|---|---:|---:|---:|---:|---:|---:|
| Qwen3-0.6B (qwen3_0_6b_mixed_int4.litertlm) | cpu | 403 | 308.7 | 9.64 | 316 | 273.7 | 8.12 |
| Qwen3-0.6B (qwen3_0_6b_mixed_int4.litertlm) | gpu | 3246 | 1842.2 | 65.69 | 2539 | 1832.8 | 70.06 |
| Qwen3-1.7B (Qwen3_1.7B.litertlm) | cpu | 2031 | 169.7 | 11.94 | 321 | 105.4 | 11.39 |
| Qwen3-1.7B (Qwen3_1.7B.litertlm) | gpu | 5651 | 608.8 | 17.24 | 4276 | 596.4 | 17.68 |
| Qwen3-4B (qwen3_4b_mixed_int4.litertlm) | cpu | 3978 | 59.7 | 4.39 | 3017 | 45.3 | 5.63 |
| Qwen3-4B (qwen3_4b_mixed_int4.litertlm) | gpu | 14846 | 347.8 | 17.78 | 13818 | 330.0 | 18.00 |
| gemma-4-E2B-it-litert-lm (gemma-4-E2B-it.litertlm) | cpu | 2194 | 387.7 | 39.89 | 226 | 252.0 | 27.57 |
| gemma-4-E2B-it-litert-lm (gemma-4-E2B-it.litertlm) | gpu | 5935 | 3657.7 | 44.62 | 2510 | 2020.1 | 26.36 |
| gemma-4-E4B-it-litert-lm (gemma-4-E4B-it.litertlm) | cpu | 4827 | 138.7 | 20.15 | 337 | 81.8 | 16.60 |
| gemma-4-E4B-it-litert-lm (gemma-4-E4B-it.litertlm) | gpu | 9469 | 1289.0 | 20.89 | 5164 | 1355.8 | 21.41 |

## Sessions without a number

| model | file | backend | session | what happened |
|---|---|---|---|---|
| litert-community/Qwen3-1.7B | Qwen3-1.7B_dynamic_wi4b32_afp32.litertlm | gpu | session-83804732 | job ERROR, first process exit 13: `Failed to apply template: invalid operation: tried to use + operator on unsupported types string and sequence (in template:32)`. The gpu row above is the repo's other file, Qwen3_1.7B.litertlm. |
| litert-community/gemma-4-E2B-it-litert-lm | gemma-4-E2B-it.litertlm | cpu, `--max_num_tokens=1280` | session-aecaca6b | job PASSED, both processes exit 0, metrics.pb has no prefill or decode turn: `dynamic_update_slice.cc:68 SizeOfDimension(update, i) <= SizeOfDimension(operand, i) was not true. Node number 1164 (DYNAMIC_UPDATE_SLICE) failed to prepare.` on subgraph `prefill_1024`, once per conversation (6 of 6). The cpu row above is session-52983393 at 2048. |
| litert-community/gemma-4-E4B-it-litert-lm | gemma-4-E4B-it.litertlm | cpu, `--max_num_tokens=1280` | session-565fe3f9 | the same as E2B cpu, node number 1830 (6 of 6). The cpu row above is session-e0cf5e62 at 2048. |

## Which token settings run on cpu (Galaxy S26, the same binary, not a measurement)

The same `litert_lm_advanced_main` (sha256 adac974b…) on a Galaxy S26 (SM-S942Q) over adb, one process and one
iteration per line, caches removed before each (`s26-repro/`, `tools/s26_gemma_cpu_repro.sh`). The rates of these
single iterations are not in any table.

| bundle | prefill tokens | max_num_tokens | result |
|---|---:|---:|---|
| gemma-4-E2B-it.litertlm | 1024 | 1280 | DYNAMIC_UPDATE_SLICE failed to prepare, no prefill turn, exit 0 |
| gemma-4-E2B-it.litertlm | 1024 | 1281 | the same failure |
| gemma-4-E2B-it.litertlm | 1024 | 1536 | runs |
| gemma-4-E2B-it.litertlm | 1024 | 2048 | runs |
| gemma-4-E2B-it.litertlm | 1024 | 4096 | runs |
| gemma-4-E2B-it.litertlm | 512 | 1280 | runs |
| gemma-4-E2B-it.litertlm | 128 | 1280 | runs |
| gemma-4-E4B-it.litertlm | 1024 | 1280 | the same failure |
| gemma-4-E4B-it.litertlm | 1024 | 2048 | runs |

## An earlier session of one cell (not pooled, not in the table)

Qwen3-0.6B cpu was also run on 2026-09-30 with the same CLI code, binary, libraries and bundle (session-0f3c1363):

| model | file | backend | prefill tok/s | decode tok/s | TTFT s | init ms | peak mem MB | tokens (prefill / decode / max) | iterations | session |
|---|---|---|---:|---:|---:|---:|---:|---|---|---|
| litert-community/Qwen3-0.6B | qwen3_0_6b_mixed_int4.litertlm | cpu | 206.9 | 6.90 | 5.102 | 531 | 2897.7 | 1024 / 256 / 1280 | 5 (1 warm-up) | session-0f3c1363 |

| model | backend | prefill tok/s per iteration | spread | decode tok/s per iteration | spread | session date (device clock) | device build |
|---|---|---|---:|---|---:|---|---|
| Qwen3-0.6B | cpu | 190.1, 204.3, 209.4, 201.6, 256.6 | 27.3% | 6.62, 6.62, 6.58, 7.18, 8.14 | 23.7% | Tue Sep 29 19:12:42 PDT 2026 | SM-S938U1 (pa3q), S938U1UEU1AYB3_OYM1AYB3 |

