# Gemma 4 E2B gpu on DDP Galaxy S25 Ultra (pa3q-35): the same cell at --num-iterations 1, 2 and 5 — 2026-10-07

Why: the morning session of this cell (session-0d1cde8d, `--num-iterations` 5, the CLI default) reports 44.62 tok/s
decode in the first process and 30.71 → 26.61 → 26.26 → 26.39 → 26.33 over the measured process's five iterations, so
the table's median (26.36) is the lower level. Two more sessions of the same cell, with `--num-iterations 1` and
`--num-iterations 2` and every other flag at the CLI default, show what one and two cycles report.

Same bundle (`gemma-4-E2B-it.litertlm`, sha256 18193810…a63c in every provenance.txt), same CLI
(litert-cli-nightly 0.3.0.dev20261006, the morning's venv), same binary (`litert_lm_advanced_main` sha256 adac974b…2d06
from `gs://litert/binaries/latest/android_arm64/litert_lm/`, bucket object dated 2026-09-18), `--ddp --device pa3q-35
--gpu`. The 1-iteration session also carries `--warmup-runs 0`: without it the CLI refuses the pair locally
("--warmup-runs (1) must be smaller than --num-iterations (1)", before any upload); for a bundle that flag only sets
how many leading iterations the CLI's printed medians leave out and is not among the binary's arguments (the args row
below). Every value is read from `metrics.pb` (measured process) and the process log (first process), not from the
CLI's printed median.

One line per prefill + decode cycle. The first process starts without cache files and runs one cycle (its values are
in the log only; the CLI gives it `--num_iterations=1` and no metrics file); the measured process starts with the
caches the first process wrote and runs `--num_iterations` cycles into `metrics.pb`. init is "Init Total" of the
process; peak mem is the process's peak so far at the end of the cycle.

| --num-iterations | process | iteration | prefill tok/s | decode tok/s | TTFT s | init ms | peak mem MB | session | device build | date (device clock) |
|---:|---|---:|---:|---:|---:|---:|---:|---|---|---|
| 1 | first (no caches) | 1 | 3526.0 | 46.97 | 0.310 | 5500 | 719.6 | session-a6aea7f8 | S938U1UEU2AYD9_OYM2AYD9 | Tue Oct  6 20:42:36 PDT 2026 |
| 1 | measured (caches present) | 1 | 3688.8 | 46.17 | 0.299 | 2373 | 692.5 | session-a6aea7f8 | S938U1UEU2AYD9_OYM2AYD9 | Tue Oct  6 20:42:36 PDT 2026 |
| 2 | first (no caches) | 1 | 3774.7 | 45.47 | 0.290 | 5797 | 720.9 | session-6587db64 | S938U1UEU1AYB3_OYM1AYB3 | Tue Oct  6 20:49:50 PDT 2026 |
| 2 | measured (caches present) | 1 | 3416.9 | 45.43 | 0.322 | 2302 | 691.1 | session-6587db64 | S938U1UEU1AYB3_OYM1AYB3 | Tue Oct  6 20:49:50 PDT 2026 |
| 2 | measured (caches present) | 2 | 3681.7 | 33.85 | 0.308 | 2302 | 691.8 | session-6587db64 | S938U1UEU1AYB3_OYM1AYB3 | Tue Oct  6 20:49:50 PDT 2026 |
| 5 | first (no caches) | 1 | 3657.7 | 44.62 | 0.300 | 5935 | 720.1 | session-0d1cde8d | S938U1UEU2AYD9_OYM2AYD9 | Tue Oct  6 09:15:32 PDT 2026 |
| 5 | measured (caches present) | 1 | 3380.2 | 30.71 | 0.336 | 2510 | 690.5 | session-0d1cde8d | S938U1UEU2AYD9_OYM2AYD9 | Tue Oct  6 09:15:32 PDT 2026 |
| 5 | measured (caches present) | 2 | 2417.9 | 26.61 | 0.461 | 2510 | 692.6 | session-0d1cde8d | S938U1UEU2AYD9_OYM2AYD9 | Tue Oct  6 09:15:32 PDT 2026 |
| 5 | measured (caches present) | 3 | 1977.5 | 26.26 | 0.556 | 2510 | 692.6 | session-0d1cde8d | S938U1UEU2AYD9_OYM2AYD9 | Tue Oct  6 09:15:32 PDT 2026 |
| 5 | measured (caches present) | 4 | 2014.6 | 26.39 | 0.546 | 2510 | 692.6 | session-0d1cde8d | S938U1UEU2AYD9_OYM2AYD9 | Tue Oct  6 09:15:32 PDT 2026 |
| 5 | measured (caches present) | 5 | 2025.6 | 26.33 | 0.544 | 2510 | 692.6 | session-0d1cde8d | S938U1UEU2AYD9_OYM2AYD9 | Tue Oct  6 09:15:32 PDT 2026 |

Process exit codes and the binary's arguments, from each session's provenance.txt:

| --num-iterations | session | exits | args |
|---:|---|---|---|
| 1 | session-a6aea7f8 | warm-up 0, measured 0 | `--backend=gpu --model_path=/data/local/tmp/litert-cli/gemma-4-E2B-it.litertlm --benchmark=true --benchmark_prefill_tokens=1024 --benchmark_decode_tokens=256 --max_num_tokens=1280 --num_iterations=1 --report_peak_memory_footprint=true --metric_proto_file_path=/data/local/tmp/litert-cli/metrics.pb` |
| 2 | session-6587db64 | warm-up 0, measured 0 | `--backend=gpu --model_path=/data/local/tmp/litert-cli/gemma-4-E2B-it.litertlm --benchmark=true --benchmark_prefill_tokens=1024 --benchmark_decode_tokens=256 --max_num_tokens=1280 --num_iterations=2 --report_peak_memory_footprint=true --metric_proto_file_path=/data/local/tmp/litert-cli/metrics.pb` |
| 5 | session-0d1cde8d | warm-up 0, measured 0 | `--backend=gpu --model_path=/data/local/tmp/litert-cli/gemma-4-E2B-it.litertlm --benchmark=true --benchmark_prefill_tokens=1024 --benchmark_decode_tokens=256 --max_num_tokens=1280 --num_iterations=5 --report_peak_memory_footprint=true --metric_proto_file_path=/data/local/tmp/litert-cli/metrics.pb` |

- session-a6aea7f8 (--num-iterations 1): metrics.pb holds 1 iteration(s); the log has 2 process(es) of the binary, 0 error line(s) (Failed to / Invalid decode / INTERNAL / FATAL).
- session-6587db64 (--num-iterations 2): metrics.pb holds 2 iteration(s); the log has 2 process(es) of the binary, 0 error line(s) (Failed to / Invalid decode / INTERNAL / FATAL).
- session-0d1cde8d (--num-iterations 5): metrics.pb holds 5 iteration(s); the log has 2 process(es) of the binary, 0 error line(s) (Failed to / Invalid decode / INTERNAL / FATAL).

Reading (what the three sessions show; no cause was looked into):

- The first process, which runs one cycle without caches, reports 45–47 tok/s decode in all three sessions
  (46.97, 45.47, 44.62) and 3526–3775 tok/s prefill.
- A measured process's first cycle reports 46.17 (1-iteration session) and 45.43 (2-iteration session) tok/s decode;
  in the 5-iteration session it reported 30.71.
- In the 2-iteration session the second cycle is 33.85 tok/s decode, 25 % under its first cycle; prefill does not
  drop between the two (3416.9 → 3681.7). In the 5-iteration session cycles 2–5 sit at 26.3–26.6 tok/s decode and
  1978–2418 tok/s prefill.
- So a one-cycle number of this cell is 46–47 tok/s decode from either process; a second cycle in the same process
  is lower (33.85 here, 26.61 in the morning); the morning's measured process was lower already in its first cycle.
  Which of these the phone's state, the pool's two firmware builds (the 2-iteration session landed on
  S938U1UEU1AYB3, the other two on S938U1UEU2AYD9) or the cycle count explains is not established by three sessions.
- The pool gives no temperature, battery or thermal reading; the time between sessions is the DDP queue's.

Files: `ddp-session/<session>/gpu-pa3q-35/` (`metrics.pb` as pulled, `metrics.pb.txt` = `protoc --decode
litert.lm.proto.LitertLmMetricsList` with LiteRT-LM v0.17.0 protos, `provenance.txt` as pulled, `logcat-process.txt` =
the logcat lines of the binary's two processes); `collected/sessions-iter.jsonl` = `collect_lm.py` (litert-samples
benchmark/driver 17e5db06) over the two sessions: the 1-iteration job is FAILED by the script ("1 iteration(s), none
beyond the 1 warm-up"), the 2-iteration job gives one row whose "median" is its single post-warm-up cycle (33.85);
`run-log-iter.txt` = every command with its output; `sessions-iter.tsv` = the attempts in order (the first line is the
locally refused attempt, no session); `tools/` = the scripts as run. The campaign's `table.md` and
`collected/sessions.jsonl` are unchanged; these two sessions are not rows there and not in `results/summary`.
