# Galaxy S26 (SM-S942Q, Android 16): Perfetto traces of LiteRT-LM benchmark processes — 2026-10-11

Traces of the `litert_lm_advanced_main` processes of `../2026-10-11-s26-gallery-vs-binary/` (the bucket binary of
2026-09-18, sha256 `adac974b…2d06`, prefill 1,024 / decode 256 / `--max_num_tokens=4096`, one cycle per process), one
cold and one cached process per bundle, plus the Gallery app sessions of the same folder when they ran. Config:
`tools/llm_trace.pbtxt` (ftrace sched + cpu/gpu frequency + cpu idle, process stats 1 s, sys stats, battery 1 s,
main and system log buffers); started with `perfetto --detach=<tag>` 2 s before the process and stopped with
`--attach=<tag> --stop` right after it. Summaries: `tools/summarize_trace.py` → `summaries/<tag>.json` (the window = the
process's first to last scheduled slice). The `.perfetto-trace` files stay on the measuring machine (2.8–7.6 MB each,
`traces/`, not committed); every number below comes out of them with the queries in the script.

Two things this phone's kernel did not put into the trace: `thermal/thermal_temperature` and
`power/cpu_frequency_limits` events (both tracepoints exist under `/sys/kernel/tracing/events/`, neither produced an
event). Temperatures and clock ceilings therefore come from the 1-second sampler beside each process
(`../2026-10-11-s26-gallery-vs-binary/binary/<tag>.sample.csv`).

## Binary processes (12:18–12:21 JST, phone cooled to 33 °C before P1, screen off)

| trace | process | window s | process CPU s / all CPU s in the window | cpu0–5 mean MHz (share at 3,628.8) | cpu6–7 mean MHz (share at 4,742.4) | GPU mean MHz (share at 1,300) | other processes with CPU time |
|---|---|---:|---|---|---|---|---|
| P1 | gemma-4-E2B-it gpu, cold | 12.8 | 8.79 / 13.38 | 2,242 (42 %) | 883 (idle floor, 0 %) | 1,300 (100 %) | kgsl_hwsched 1.47, gmu_f2h 0.83, traced_probes 0.29, system_server 0.19 |
| P2 | gemma-4-E2B-it gpu, cached | 8.7 | 4.60 / 8.76 | 1,496 (11 %) | 883 (0 %) | 1,289 (99 %) | kgsl_hwsched 1.50, gmu_f2h 0.83, traced_probes 0.44 |
| P3 | gemma3-1b-it-int4 cpu, cold | 8.9 | 23.85 / 25.23 | 3,544 (79 %) | 3,131 (43 %) | — | traced_probes 0.26, kworker 0.10 |
| P4 | gemma3-1b-it-int4 cpu, cached | 9.3 | 24.01 / 25.44 | 3,525 (73 %) | 3,096 (34 %) | — | traced_probes 0.32, kworker 0.11 |

Reading, within these four traces only:
- The GPU processes run on the six small/medium cores; the two big cores stay at their 883 MHz floor for the whole
  window, the GPU holds its top step the whole time, and the other processes with CPU time are the GPU driver's
  kernel threads. Cold against cached differs in the process's own CPU time (8.8 s against 4.6 s) — the engine log
  inside the trace places four "Initializing OpenCL-based API from serialized data" steps at 1.8 / 3.2 / 4.7 / 5.6 s
  in the cold process, and four "Initialized InferenceContext from serialized data" steps between 1.7 and 2.3 s in
  the cached one.
- The CPU processes own 95 % of all CPU time in their windows (nothing else of note runs), and the big cores are
  capped during the run: their ceiling falls from 4,742 to 3,974 / 3,859 MHz (sampler) while the cpu-0-0-0 zone rises
  from 36 °C to 86–87 °C within the 9-second run; the small cores keep 3,629 MHz for 73–79 % of the window.

## Afternoon, screen on (the Gallery sessions 15:20–15:58 JST and the binary pairs Q1–Q5 16:01–16:13 JST)

The second sitting kept the screen on (the Gallery app needs it) and cooled the phone to 36–37 °C before each process
or session. Windows: a binary trace's window is still the process's first to last scheduled slice; the Gallery
session's window runs from the engine's first log line of the session ("Creating LiteRT environment") to the last
scheduled slice of the engine's executor threads (three threads named `execution_threa`, one per run), because the app
process outlives the runs (`summarize_trace.py --thread execution_threa --from-log "Creating LiteRT environment"`).

| trace | process / session | window s | process CPU s / all CPU s in the window | cpu0–5 clock (trace) mean MHz (share at 3,628.8) | cpu6–7 clock (trace) mean MHz (share at 4,742.4) | GPU mean MHz (share at 1,300) | other processes with CPU time |
|---|---|---:|---|---|---|---|---|
| E2B-gpu-1 | Gallery 1.0.20 session, gemma-4-E2B-it GPU, 3 runs (run 1 cold, runs 2–3 cached) | 26.2 | 14.83 / 35.00 | 1,817 (4 %) | 1,907 (12 %) | 1,119 (74 %) | kgsl_hwsched 4.47, gmu_f2h 2.08, traced_probes 2.06, surfaceflinger 1.41, kswapd0 0.97, display composer 0.80, system_server 0.78 |
| Q1 | binary, gemma-4-E2B-it gpu, cold | 10.0 | 6.10 / 10.52 | 1,061 (1 %) | 2,216 (29 %) | 1,300 (100 %) | kgsl_hwsched 1.57, gmu_f2h 0.79, traced_probes 0.30, kcompactd0 0.15, kgsl-events 0.13 |
| Q2 | binary, gemma-4-E2B-it gpu, cached | 7.2 | 3.48 / 7.23 | 1,175 (1 %) | 1,416 (9 %) | 1,300 (100 %) | kgsl_hwsched 1.44, gmu_f2h 0.74, traced_probes 0.29 |
| Q3 | binary, gemma3-1b-it-int4 cpu, cold (weight cache built) | 8.1 | 24.08 / 26.40 | 3,073 (25 %) | 4,224 (44 %) | — | traced_probes 0.30, kswapd0 0.29, system_server 0.16 |
| Q4 | binary, gemma3-1b-it-int4 cpu, cached ("weight cache loaded from") | 6.6 | 23.81 / 25.54 | 3,318 (37 %) | 4,259 (38 %) | — | traced_probes 0.33, com.google.android.gms 0.10, system_server 0.09 |
| Q5 | binary, gemma3-1b-it-int4 cpu, cached ("weight cache loaded from") | 6.6 | 23.81 / 25.67 | 3,373 (65 %) | 4,382 (36 %) | — | traced_probes 0.41, system_server 0.13 |

Engine log lines inside these traces (offsets from the window start): Q1's four "Initializing OpenCL-based API from
serialized data" at 1.5 / 2.3 / 3.2 / 3.7 s; Q2's eight "serialized data" lines (four Initializing + four
"Initialized InferenceContext from serialized data") between 1.3 and 1.7 s; the Gallery session's run 1 at 1.8 / 2.6 /
3.5 / 4.0 s (Initializing only), run 2's "Initialized InferenceContext" lines at 11.9–12.2 s, run 3's at 19.6–20.0 s;
Q3's weight-cache build lines and Q4 / Q5's "weight cache loaded from" at 0.2 s. The clock ceilings and zone
temperatures of the same processes are in the sampler files (`../2026-10-11-s26-gallery-vs-binary/binary-pass3/*.sample.csv`,
`gallery/*.sample.csv`; the tables there carry the minima of the ceilings and the zone maxima).

Two cautions. (1) No trace exists for a Gallery CPU session: the G3-cpu-1 session's `perfetto --detach` was refused
because five earlier sessions were still open — the morning's `--attach=<tag> --stop` calls had not ended P1–P4's
sessions (their files kept growing after the pull; the pulled files hold the runs), and E2B-gpu-1's was open too. A
second `--attach --stop` from a fresh shell ended them; after every stop, read `perfetto --query` and expect an empty
session table (the service allows five per uid). (2) The E2B-gpu-1 trace file on the measuring machine is the first
two minutes of that session's recording (44 MB), pulled while the session was still open; its window above ends at the
last executor slice, 26 s in.

Trace files (`traces/`, on the measuring machine): P1 7.6 MB, P2 7.2 MB, P3 2.8 MB, P4 2.8 MB, Q1 6.9 MB, Q2 7.0 MB,
Q3 3.3 MB, Q4 2.6 MB, Q5 3.0 MB, E2B-gpu-1 44 MB.
