# Gemma 4 E2B on DDP Galaxy S25 Ultra (pa3q-35) at the LiteRT team's allocation: `--max-num-tokens 4096`, one cycle, three sessions per backend — 2026-10-08 02:37–03:53 JST

Why: the team's Kotlin `DeviceBenchmarkTest` runs this bundle with prefill 1024 / decode 256 and sets no max token count,
so the engine takes its default (the bundle's metadata limit if it carries one, else 4096); its first number is one cold
run (no cache files), its second a run after a warm-up and a 10 s pause in the same process. This repo's DDP rows
(`table.md`, `table-iter.md`) are at the CLI default `--max_num_tokens=1280`, and the benchmark binary picks 1280 on
its own when the flag is absent (round 4, `../s26-cycle-drop/round4-maxtokens/`), so 4096 is passed explicitly here.
Six billed sessions, three per backend (round 5: one each, 02:37–02:58; round 6: two more each in the order gpu, cpu,
gpu, cpu, 03:19–03:53), `--num-iterations 1 --warmup-runs 0 --max-num-tokens 4096`, every other flag at the CLI default
(prefill 1024, decode 256). Same CLI (litert-cli-nightly 0.3.0.dev20261006, the morning's venv), bundle (sha256
18193810…a63c) and binary (adac974b…2d06; both in each `provenance.txt`). `--warmup-runs 0` only sets which iterations
the CLI's printed medians leave out and is not among the binary's arguments.

Two processes per session, as always with this CLI: the first starts without cache files, runs one cycle and writes the
caches (the shape of the team's first, cold number); the measured process starts with those caches and runs its one
cycle (near the team's second number, without the 10 s pause and without a warm-up cycle in the same process). Values
from `metrics.pb.txt` (measured process) and the process log (first process). Every session passed at the first try.

## Every session (`tools/mktable_aligned_n.py`)

| backend | session | process | prefill tok/s | decode tok/s | TTFT s | init ms | peak mem MB | device build | date (device clock) |
|---|---|---|---:|---:|---:|---:|---:|---|---|
| gpu | session-e60522b0 | first (no caches, cold) | 2710.0 | 45.11 | 0.400 | 5720 | 746.6 | S938U1UEU2AYD9_OYM2AYD9 | Wed Oct  7 10:46:53 PDT 2026 |
| gpu | session-e60522b0 | measured (caches present) | 2996.2 | 44.70 | 0.364 | 2263 | 725.3 | S938U1UEU2AYD9_OYM2AYD9 | Wed Oct  7 10:46:53 PDT 2026 |
| gpu | session-76bb31e7 | first (no caches, cold) | 2937.3 | 45.57 | 0.370 | 5711 | 747.7 | S938U1UEU2AYD9_OYM2AYD9 | Wed Oct  7 11:25:56 PDT 2026 |
| gpu | session-76bb31e7 | measured (caches present) | 3027.8 | 43.96 | 0.361 | 2460 | 720.8 | S938U1UEU2AYD9_OYM2AYD9 | Wed Oct  7 11:25:56 PDT 2026 |
| gpu | session-93c1148a | first (no caches, cold) | 2798.6 | 44.70 | 0.390 | 5746 | 746.8 | S938U1UEU2AYD9_OYM2AYD9 | Wed Oct  7 11:42:54 PDT 2026 |
| gpu | session-93c1148a | measured (caches present) | 2914.0 | 47.07 | 0.373 | 2346 | 725.1 | S938U1UEU2AYD9_OYM2AYD9 | Wed Oct  7 11:42:54 PDT 2026 |
| cpu | session-c3c1094e | first (no caches, cold) | 339.1 | 35.36 | 3.050 | 2413 | 2606.2 | S938U1UEU1AYB3_OYM1AYB3 | Wed Oct  7 10:54:35 PDT 2026 |
| cpu | session-c3c1094e | measured (caches present) | 313.5 | 35.10 | 3.294 | 228 | 2503.9 | S938U1UEU1AYB3_OYM1AYB3 | Wed Oct  7 10:54:35 PDT 2026 |
| cpu | session-20550b6d | first (no caches, cold) | 329.3 | 34.91 | 3.140 | 2153 | 2606.2 | S938U1UEU2AYD9_OYM2AYD9 | Wed Oct  7 11:35:09 PDT 2026 |
| cpu | session-20550b6d | measured (caches present) | 305.2 | 34.03 | 3.385 | 232 | 2504.2 | S938U1UEU2AYD9_OYM2AYD9 | Wed Oct  7 11:35:09 PDT 2026 |
| cpu | session-ca7670c5 | first (no caches, cold) | 326.4 | 34.65 | 3.170 | 2379 | 2606.2 | S938U1UEU1AYB3_OYM1AYB3 | Wed Oct  7 11:51:50 PDT 2026 |
| cpu | session-ca7670c5 | measured (caches present) | 305.3 | 34.20 | 3.383 | 256 | 2505.7 | S938U1UEU1AYB3_OYM1AYB3 | Wed Oct  7 11:51:50 PDT 2026 |

| backend | process | n | prefill median (each) | prefill spread | decode median (each) | decode spread | TTFT median s | init median ms | peak mem median MB |
|---|---|---:|---|---:|---|---:|---:|---:|---:|
| gpu | first (cold) | 3 | 2798.6 (2710.0, 2937.3, 2798.6) | 8.4% | 45.11 (45.11, 45.57, 44.70) | 1.9% | 0.390 | 5720 | 746.8 |
| gpu | measured (cached) | 3 | 2996.2 (2996.2, 3027.8, 2914.0) | 3.9% | 44.70 (44.70, 43.96, 47.07) | 7.1% | 0.364 | 2346 | 725.1 |
| cpu | first (cold) | 3 | 329.3 (339.1, 329.3, 326.4) | 3.9% | 34.91 (35.36, 34.91, 34.65) | 2.0% | 3.140 | 2379 | 2606.2 |
| cpu | measured (cached) | 3 | 305.3 (313.5, 305.2, 305.3) | 2.7% | 34.20 (35.10, 34.03, 34.20) | 3.2% | 3.383 | 232 | 2504.2 |

| backend | session | exits | max_num_tokens (args / settings dump) | error lines | threads |
|---|---|---|---|---:|---|
| gpu | session-e60522b0 | warm-up 0, measured 0 | 4096 / 4096 | 0 | - |
| gpu | session-76bb31e7 | warm-up 0, measured 0 | 4096 / 4096 | 0 | - |
| gpu | session-93c1148a | warm-up 0, measured 0 | 4096 / 4096 | 0 | - |
| cpu | session-c3c1094e | warm-up 0, measured 0 | 4096 / 4096 | 0 | 4 |
| cpu | session-20550b6d | warm-up 0, measured 0 | 4096 / 4096 | 0 | 4 |
| cpu | session-ca7670c5 | warm-up 0, measured 0 | 4096 / 4096 | 0 | 4 |

## Reading (the numbers only; the team's numbers are not written here, the brief lines them up)

- gpu, cold (first process, no caches), three sessions: prefill 2710.0, 2937.3, 2798.6 tok/s, median 2798.6, spread
  8.4 %; decode 44.70–45.57 (median 45.11, spread 1.9 %); TTFT 0.37–0.40 s; init 5711–5746 ms; peak memory 746.6–747.7 MB.
- gpu, cached (measured process): prefill 2996.2, 3027.8, 2914.0, median 2996.2, spread 3.9 %; decode 43.96–47.07
  (median 44.70, spread 7.1 %); TTFT 0.361–0.373 s; init 2263–2460 ms; peak memory 720.8–725.3 MB. The cached prefill
  is above the cold one in every session (by 3–11 %).
- cpu, cold: prefill 326.4–339.1, median 329.3, spread 3.9 %; decode 34.65–35.36 (median 34.91); TTFT 3.05–3.17 s;
  init 2153–2413 ms; peak memory 2606.2 MB in all three. cpu, cached: prefill 305.2–313.5, median 305.3, spread 2.7 %;
  decode 34.03–35.10 (median 34.20); TTFT 3.29–3.39 s; init 228–256 ms; peak memory 2503.9–2505.7 MB. On cpu the cached
  process's prefill is below the cold one in every session (by 6–8 %); `number_of_threads: 4` in every cpu process.
- Against the 1280 sessions of 2026-10-07 (`table-iter.md`: first process 3526–3775, measured first cycle 3689 / 3417)
  the gpu prefill at 4096 is lower by a fifth to a quarter (cached median −19 %, cold median −24 %), about the size of
  the 1280 → 4096 step measured on the S26 in round 4 (−20 %); gpu decode stays at the one-cycle level of those
  sessions (44–47). The bundle does not allocate on cpu at 1280 (`table.md`), so no 1280 cpu comparison exists; the 2048
  cpu session of 2026-10-07 (session-52983393) read 387.7 / 39.89 in its first process and 252.0 / 27.57 as the median
  of iterations 2–5.
- All six sessions: both processes exit 0, no error line from the binary (Failed to / Invalid decode / INTERNAL / FATAL),
  `--max_num_tokens=4096` in the args and `max_tokens: 4096` in every settings dump. The gpu sessions all landed on
  firmware S938U1UEU2AYD9, the cpu sessions on S938U1UEU1AYB3 twice and S938U1UEU2AYD9 once. No temperature or screen
  state exists for the pool.

Files: `ddp-session/<session>/<backend>-pa3q-35/` for the six sessions (`metrics.pb`, `metrics.pb.txt` = `protoc
--decode litert.lm.proto.LitertLmMetricsList` with the LiteRT-LM v0.17.0 protos, `provenance.txt` as pulled,
`logcat-process.txt` = the binary's two processes' lines), `run-log-aligned.txt` (every command with its output,
including the removal of each round's uploaded input dirs from the project bucket; inputs back to 11,680,278,877 bytes
after each round, session outputs kept), `sessions-aligned.tsv` (the six sessions in order), `tools/` (as run, USER for
the user name). Not rows of `table.md` or `results/summary`; not added to any leaderboard data.
