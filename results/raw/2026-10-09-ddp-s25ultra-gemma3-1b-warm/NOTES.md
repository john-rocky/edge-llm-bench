# 2026-10-09 — Gemma 3 1B IT int4 on DDP Galaxy S25 Ultra (pa3q-35), cpu, two cycles in each process (warm-shape round)

Follow-up to the morning's six one-cycle sessions (`../2026-10-09-ddp-s25ultra-gemma3-1b/`). The question was whether a
cpu cycle measured right after a warm-up cycle in the same process reports a different decode rate than a single cold
or cached cycle. Three billed cpu sessions on the Developer Device Platform (DDP) pool `pa3q-35`, 20:44–20:53 JST,
same bundle (litert-community `gemma3-1b-it-int4.litertlm`, sha256 1325ae36…98be, 584,417,280 bytes, verified against
the Hub API before the round), same CLI (litert-cli-nightly 0.3.0.dev20261006, the morning's venv), same binary (bucket
latest, sha256 adac974b…2d06 in every provenance.txt), `--cpu --num-iterations 2 --warmup-runs 0 --max-num-tokens
4096`, prefill 1024 / decode 256 at the defaults. Every session PASSED at the first try; both processes exit 0 in all
three, no error line, 4 threads, max_tokens 4096 in every args row and settings dump.

What was found before the round, and how it was handled: the CLI's device-side run script appends `--num_iterations=1`
to the first (warm-up) process unconditionally (`litert_cli/commands/benchmark/ddp.py`, `_LM_WARMUP_ARGS`), and
`--num-iterations` reaches only the measured process; `LITERT_DISABLE_MODEL_CACHES` does not apply to a .litertlm
bundle. With the stock CLI the row "cold start, then a second cycle in the same process" cannot exist. The three
sessions therefore ran through `tools/litert_warm2.py`: the CLI with that one constant set to `--num_iterations=2`
(the run script's dry output is in `run-log.txt`; the first process's second BenchmarkInfo block in every logcat
confirms it ran two cycles). Nothing else was changed. The first process writes no metrics file (the CLI passes an
empty `--metric_proto_file_path`), so its cycles come from the logcat; the measured process's cycles come from
metrics.pb (two `metrics {}` blocks, equal to its logcat blocks).

Not aligned: the pause between the warm-up cycle and the measured cycle. The benchmark binary has no flag for one (the
public `runtime/engine/shared_flags.cc` carries benchmark_prefill_tokens, benchmark_decode_tokens and num_iterations;
the iteration loop in `litert_lm_lib.cc` runs the cycles back to back), so none was inserted.

Result in one line (this side only): a second cycle in the same process after a cold start moves cpu decode by −2.0 %
(56.13 → 55.02 tok/s at the median of three sessions) and prefill by −6.9 % (378.0 → 351.8); the cold cycle itself
repeats the morning's cold row within 1 %. The numbers, per-session rows and the checks are in `table-aligned.md`.

Single runtime, one model, one backend: nothing here compares runtimes, and nothing is added to the leaderboard data (no
run record in the result.v1 shape; `results/summary/` is unchanged). The three uploaded input dirs were removed from the
project bucket after the round (inputs back to 11,680,278,877 bytes; session outputs stay).
