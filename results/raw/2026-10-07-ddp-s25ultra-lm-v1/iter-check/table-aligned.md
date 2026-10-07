# Gemma 4 E2B on DDP Galaxy S25 Ultra (pa3q-35) at the LiteRT team's allocation: `--max-num-tokens 4096`, one cycle — 2026-10-08 02:37–02:58 JST

Why: the team's Kotlin `DeviceBenchmarkTest` runs this bundle with prefill 1024 / decode 256 and sets no max token count,
so the engine takes its default (the bundle's metadata limit if it carries one, else 4096); its first number is one cold
run (no cache files), its second a run after a warm-up and a 10 s pause in the same process. This repo's DDP rows
(`table.md`, `table-iter.md`) are at the CLI default `--max_num_tokens=1280`, and the benchmark binary picks 1280 on
its own when the flag is absent (round 4, `../s26-cycle-drop/round4-maxtokens/`), so 4096 is passed explicitly here.
Two billed sessions, one per backend, `--num-iterations 1 --warmup-runs 0 --max-num-tokens 4096`, every other flag at
the CLI default (prefill 1024, decode 256). Same CLI (litert-cli-nightly 0.3.0.dev20261006, the morning's venv), bundle
(sha256 18193810…a63c) and binary (adac974b…2d06; both in each `provenance.txt`). `--warmup-runs 0` only sets which
iterations the CLI's printed medians leave out and is not among the binary's arguments (args row below).

Two processes per session, as always with this CLI: the first starts without cache files, runs one cycle and writes the
caches (the shape of the team's first, cold number); the measured process starts with those caches and runs its one
cycle (near the team's second number, without the 10 s pause and without a warm-up cycle in the same process). Values
from `metrics.pb.txt` (measured process) and the process log (first process).

| backend | process | prefill tok/s | decode tok/s | TTFT s | init ms | peak mem MB | max_tokens (settings dump) | session | device build | date (device clock) |
|---|---|---:|---:|---:|---:|---:|---:|---|---|---|
| gpu | first (no caches, cold) | 2710.0 | 45.11 | 0.400 | 5720 | 746.6 | 4096 | session-e60522b0 | S938U1UEU2AYD9_OYM2AYD9 | Wed Oct  7 10:46:53 PDT 2026 |
| gpu | measured (caches present), cycle 1 | 2996.2 | 44.70 | 0.364 | 2263 | 725.3 | 4096 | session-e60522b0 | S938U1UEU2AYD9_OYM2AYD9 | Wed Oct  7 10:46:53 PDT 2026 |
| cpu | first (no caches, cold) | 339.1 | 35.36 | 3.050 | 2413 | 2606.2 | 4096 | session-c3c1094e | S938U1UEU1AYB3_OYM1AYB3 | Wed Oct  7 10:54:35 PDT 2026 |
| cpu | measured (caches present), cycle 1 | 313.5 | 35.10 | 3.294 | 228 | 2503.9 | 4096 | session-c3c1094e | S938U1UEU1AYB3_OYM1AYB3 | Wed Oct  7 10:54:35 PDT 2026 |

| backend | session | exits | args |
|---|---|---|---|
| gpu | session-e60522b0 | warm-up 0, measured 0 | `--backend=gpu --model_path=/data/local/tmp/litert-cli/gemma-4-E2B-it.litertlm --benchmark=true --benchmark_prefill_tokens=1024 --benchmark_decode_tokens=256 --max_num_tokens=4096 --num_iterations=1 --report_peak_memory_footprint=true --metric_proto_file_path=/data/local/tmp/litert-cli/metrics.pb` |
| cpu | session-c3c1094e | warm-up 0, measured 0 | `--backend=cpu --model_path=/data/local/tmp/litert-cli/gemma-4-E2B-it.litertlm --benchmark=true --benchmark_prefill_tokens=1024 --benchmark_decode_tokens=256 --max_num_tokens=4096 --num_iterations=1 --report_peak_memory_footprint=true --metric_proto_file_path=/data/local/tmp/litert-cli/metrics.pb` |

- session-e60522b0 (gpu): metrics.pb holds 1 iteration(s); 2 process(es) of the binary in the log, 0 error line(s) (Failed to / Invalid decode / INTERNAL / FATAL); log says GPU OpenCL.
- session-c3c1094e (cpu): metrics.pb holds 1 iteration(s); 2 process(es) of the binary in the log, 0 error line(s) (Failed to / Invalid decode / INTERNAL / FATAL); log says CpuAccelerator (XNNPACK), number_of_threads 4.

Reading (what the two sessions report; the team's numbers are not written here, the brief lines them up):

- gpu at 4096: 2710.0 tok/s prefill cold, 2996.2 with the caches; decode 45.11 and 44.70; TTFT 0.400 and 0.364 s;
  init 5720 and 2263 ms; peak memory 746.6 and 725.3 MB. Against the 1280 sessions of 2026-10-07 (first process
  3526–3775, measured first cycle 3689 / 3417; `table-iter.md`) the 4096 prefill is lower by a fifth to a quarter (measured −19 %, cold −23 to −28 %), about the size
  of the 1280 → 4096 step measured on the S26 in round 4 (−20 %); decode is at the one-cycle level of those sessions
  (45–47).
- cpu at 4096: 339.1 tok/s prefill cold, 313.5 with the caches; decode 35.36 and 35.10; TTFT 3.05 and 3.29 s; init 2413
  and 228 ms; peak memory 2606 and 2504 MB; `number_of_threads: 4`. The 2048 session of 2026-10-07 (session-52983393,
  5 iterations) read 387.7 / 39.89 in its first process and 252.0 / 27.57 as the median of iterations 2–5; one cycle
  at 4096 is between those. The bundle does not allocate on cpu at 1280 (`table.md`), so no 1280 cpu comparison exists.
- The two sessions landed on the pool's two firmware builds (gpu on S938U1UEU2AYD9, cpu on S938U1UEU1AYB3), as the
  2026-10-07 sessions did. Both processes exit 0 in both sessions; no error line from the binary; `max_tokens: 4096` in
  every settings dump. No temperature or screen state exists for the pool.

Files: `ddp-session/session-e60522b0/gpu-pa3q-35/` and `ddp-session/session-c3c1094e/cpu-pa3q-35/` (`metrics.pb`,
`metrics.pb.txt` = `protoc --decode litert.lm.proto.LitertLmMetricsList` with the LiteRT-LM v0.17.0 protos,
`provenance.txt` as pulled, `logcat-process.txt` = the binary's two processes' lines), `run-log-aligned.txt` (every
command with its output, including the removal of the round's two uploaded input dirs from the project bucket;
inputs back to 11,680,278,877 bytes, session outputs kept), `sessions-aligned.tsv`, `tools/` (as run, USER for the
user name). Not rows of `table.md` or `results/summary`; not added to any leaderboard data.
