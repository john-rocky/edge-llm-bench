# Gemma 3 1B IT int4 on DDP Galaxy S25 Ultra (pa3q-35), cpu, three sessions, two cycles in each process (warm-shape round) — 2026-10-09

Purpose: the morning's six sessions (`../2026-10-09-ddp-s25ultra-gemma3-1b/table-aligned.md`) ran one cycle per
process. This round runs the same cpu cell with two cycles in each process, so that a cycle measured after a warm-up
cycle *in the same process* exists: the first process starts cold (no caches), its cycle 1 writes the XNNPACK cache,
its cycle 2 is the same-process warm measurement; the measured process starts with the cache present and runs cycles
1 and 2 the same way. No pause is inserted between the cycles: the benchmark binary has no flag for one
(`runtime/engine/shared_flags.cc`: the benchmark flags are benchmark_prefill_tokens, benchmark_decode_tokens,
num_iterations; the iteration loop in `litert_lm_lib.cc` runs back to back).

Bundle, CLI, binary, device pool and arguments as the morning: litert-community/Gemma3-1B-IT
`gemma3-1b-it-int4.litertlm` (sha256 `1325ae366d31950f137c9c357b9fa89448b176d76998180c08ceaca78bba98be`,
584,417,280 bytes), litert-cli-nightly 0.3.0.dev20261006 (the same venv), binary
`gs://litert/binaries/latest/android_arm64/litert_lm/litert_lm_advanced_main` (sha256 adac974b…2d06 in every
provenance.txt), `--cpu --num-iterations 2 --warmup-runs 0 --max-num-tokens 4096`, the rest at the CLI defaults
(prefill 1024 / decode 256). One change to the harness: the CLI appends `--num_iterations=1` to its first (warm-up)
process unconditionally (`litert_cli/commands/benchmark/ddp.py`, `_LM_WARMUP_ARGS`; `--num-iterations` reaches the
measured process only), so the three sessions ran through `tools/litert_warm2.py`, the CLI with that constant set to
`--num_iterations=2`. Everything else in the run script is the CLI's own; both processes' arguments are in
`provenance.txt` (the measured process's `args:` line) and in the binary's settings dump in the logcat. The first
process writes no metrics file, so its two cycles are read from its two BenchmarkInfo blocks in the logcat; the
measured process's two cycles are the two `metrics {}` blocks of metrics.pb (cross-checked against its logcat blocks:
equal). Three sessions, 20:44–20:53 JST, each PASSED at the first try, both processes exit 0, no error line, 4 threads.

The first table is the one to quote: per process and cycle the median over the three sessions with [min–max]. The
row "first, cycle 2" is the same-process warm measurement after a cold start. The other side's numbers are not in
this file.

| backend | process | cycle | n | prefill tok/s median [min–max] | decode tok/s | TTFT s | init ms | peak mem MB | sessions | device builds |
|---|---|---|---:|---|---|---|---|---|---|---|
| cpu | first (cold start, no caches) | cycle 1 | 3 | 378.0 [374.2–384.9] | 56.13 [55.66–56.71] | 2.730 [2.680–2.750] | 1510 [1495–1543] | 1595.5 [1561.4–1637.1] | session-9a740c14, session-aa0cf5c4, session-ade1379f | S938U1UEU1AYB3, S938U1UES5AYH2, S938U1UEU2AYD9 |
| cpu | first (cold start, no caches) | cycle 2 (same process, after cycle 1) | 3 | 351.8 [338.8–366.7] | 55.02 [54.89–56.47] | 2.930 [2.810–3.040] | 1510 [1495–1543] | 1595.7 [1561.6–1637.3] | session-9a740c14, session-aa0cf5c4, session-ade1379f | S938U1UEU1AYB3, S938U1UES5AYH2, S938U1UEU2AYD9 |
| cpu | measured (caches present) | cycle 1 | 3 | 332.3 [323.6–350.0] | 54.00 [53.90–54.78] | 3.100 [2.945–3.183] | 317 [314–322] | 1176.3 [1175.8–1176.8] | session-9a740c14, session-aa0cf5c4, session-ade1379f | S938U1UEU1AYB3, S938U1UES5AYH2, S938U1UEU2AYD9 |
| cpu | measured (caches present) | cycle 2 (same process, after cycle 1) | 3 | 310.5 [229.5–322.7] | 53.39 [46.28–53.97] | 3.316 [3.192–4.483] | 317 [314–322] | 1176.6 [1176.1–1177.0] | session-9a740c14, session-aa0cf5c4, session-ade1379f | S938U1UEU1AYB3, S938U1UES5AYH2, S938U1UEU2AYD9 |

| backend | session | process | cycle | prefill tok/s | decode tok/s | TTFT s | init ms | peak mem MB | device build | date (device clock) |
|---|---|---|---|---:|---:|---:|---:|---:|---|---|
| cpu | session-9a740c14 | first (cold start, no caches) | 1 | 378.0 | 55.66 | 2.730 | 1543 | 1561.4 | S938U1UEU1AYB3 | Fri Oct  9 04:46:11 PDT 2026 |
| cpu | session-9a740c14 | first (cold start, no caches) | 2 | 351.8 | 55.02 | 2.930 | 1543 | 1561.6 | S938U1UEU1AYB3 | Fri Oct  9 04:46:11 PDT 2026 |
| cpu | session-9a740c14 | measured (caches present) | 1 | 332.3 | 54.78 | 3.100 | 317 | 1176.3 | S938U1UEU1AYB3 | Fri Oct  9 04:46:11 PDT 2026 |
| cpu | session-9a740c14 | measured (caches present) | 2 | 322.7 | 53.97 | 3.192 | 317 | 1176.6 | S938U1UEU1AYB3 | Fri Oct  9 04:46:11 PDT 2026 |
| cpu | session-aa0cf5c4 | first (cold start, no caches) | 1 | 374.2 | 56.13 | 2.750 | 1495 | 1595.5 | S938U1UES5AYH2 | Fri Oct  9 04:49:11 PDT 2026 |
| cpu | session-aa0cf5c4 | first (cold start, no caches) | 2 | 338.8 | 54.89 | 3.040 | 1495 | 1595.7 | S938U1UES5AYH2 | Fri Oct  9 04:49:11 PDT 2026 |
| cpu | session-aa0cf5c4 | measured (caches present) | 1 | 323.6 | 54.00 | 3.183 | 322 | 1176.8 | S938U1UES5AYH2 | Fri Oct  9 04:49:11 PDT 2026 |
| cpu | session-aa0cf5c4 | measured (caches present) | 2 | 310.5 | 53.39 | 3.316 | 322 | 1177.0 | S938U1UES5AYH2 | Fri Oct  9 04:49:11 PDT 2026 |
| cpu | session-ade1379f | first (cold start, no caches) | 1 | 384.9 | 56.71 | 2.680 | 1510 | 1637.1 | S938U1UEU2AYD9 | Fri Oct  9 04:52:18 PDT 2026 |
| cpu | session-ade1379f | first (cold start, no caches) | 2 | 366.7 | 56.47 | 2.810 | 1510 | 1637.3 | S938U1UEU2AYD9 | Fri Oct  9 04:52:18 PDT 2026 |
| cpu | session-ade1379f | measured (caches present) | 1 | 350.0 | 53.90 | 2.945 | 314 | 1175.8 | S938U1UEU2AYD9 | Fri Oct  9 04:52:18 PDT 2026 |
| cpu | session-ade1379f | measured (caches present) | 2 | 229.5 | 46.28 | 4.483 | 314 | 1176.1 | S938U1UEU2AYD9 | Fri Oct  9 04:52:18 PDT 2026 |

| backend | session | exits | --num_iterations (measured args) | BenchmarkInfo blocks first / measured (logcat) | metrics blocks | max_num_tokens (args / settings dump) | backend line | error lines first / measured | threads | bundle sha256 | binary sha256 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| cpu | session-9a740c14 | warm-up 0, measured 0 | 2 | 2 / 2 | 2 | 4096 / 4096 | cpu | 0 / 0 | 4 | 1325ae36… | adac974b… |
| cpu | session-aa0cf5c4 | warm-up 0, measured 0 | 2 | 2 / 2 | 2 | 4096 / 4096 | cpu | 0 / 0 | 4 | 1325ae36… | adac974b… |
| cpu | session-ade1379f | warm-up 0, measured 0 | 2 | 2 / 2 | 2 | 4096 / 4096 | cpu | 0 / 0 | 4 | 1325ae36… | adac974b… |

## Reference: the morning's one-cycle cpu rows (unchanged, copied from `../2026-10-09-ddp-s25ultra-gemma3-1b/table-aligned.md`)

| backend | process | n | prefill tok/s median [min–max] | decode tok/s | TTFT s | init ms | peak mem MB | sessions | device builds |
|---|---|---:|---|---|---|---|---|---|---|
| cpu | first (cold, no caches) | 3 | 381.2 [380.7–383.8] | 56.68 [56.56–56.68] | 2.700 [2.690–2.710] | 1528 [1484–1588] | 1585.9 [1408.7–1591.1] | session-416669e7, session-4afc8fc2, session-b315a4d7 | S938U1UEU2AYD9, S938U1UEU1AYB3, S938U1UEU1AYB3 |
| cpu | measured (cached) | 3 | 365.4 [362.7–368.5] | 56.23 [55.66–56.81] | 2.820 [2.797–2.841] | 302 [296–302] | 1175.0 [1173.5–1176.2] | session-416669e7, session-4afc8fc2, session-b315a4d7 | S938U1UEU2AYD9, S938U1UEU1AYB3, S938U1UEU1AYB3 |

## Reading (this side's numbers only)

- The cold cycle (first process, cycle 1) repeats the morning's cold row: prefill 378.0 against 381.2 (−0.8 %), decode
  56.13 against 56.68 (−1.0 %), init 1510 against 1528 ms. The same-day control holds.
- A second cycle in the same process after a cold start (first process, cycle 2) gives decode 55.02 [54.89–56.47]
  against 56.13 [55.66–56.71] in cycle 1: −2.0 % at the median, inside the morning's cold-to-cached spread. Prefill falls
  more: 351.8 [338.8–366.7] against 378.0, −6.9 %. TTFT 2.93 against 2.73 s. Init and peak memory are per process and do
  not change between the cycles (the same value repeats in both blocks).
- The measured process (cache present, started right after the two-cycle first process) is lower than the morning's
  cached process in both cycles: cycle 1 prefill 332.3 against 365.4 (−9 %), decode 54.00 against 56.23 (−4 %); cycle 2
  310.5 / 53.39. One session (session-ade1379f, device build AYD9) dropped in the measured process's cycle 2 to
  229.5 prefill / 46.28 decode / TTFT 4.48 s, the fourth back-to-back cycle of that job; the other two sessions'
  cycle 2 stayed at 310–323 / 53.4–54.0. Three sessions do not establish the cause (phone state, the pool's firmware
  builds, the back-to-back cycles); no thermal reading exists for the pool.
- The pool answered with three firmware builds this time (AYB3, AYH2, AYD9; the morning saw AYB3 and AYD9). The
  session on AYH2 (session-aa0cf5c4) sits in the middle of the three in every row.
- Not aligned: the pause between the warm-up cycle and the measured cycle. The binary has no flag for it, and none was
  inserted. The cycles here run back to back.

Files: `ddp-session/<session>/cpu-pa3q-35/` (metrics.pb, metrics.pb.txt, provenance.txt, logcat-process.txt),
`sessions.tsv`, `run-log.txt` (every command: pre-flight checks, the wrapper's dry check, the three sessions with the
CLI's output, the bucket cleanup), `tools/` (rl.sh, litert_warm2.py, sess.sh, run-round.sh, gather.py, mktable.py; the
tables above are mktable.py's output, the reference rows are copied from the morning's file).
