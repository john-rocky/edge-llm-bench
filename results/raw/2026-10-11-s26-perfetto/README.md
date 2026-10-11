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

Gallery app sessions: see the table in `../2026-10-11-s26-gallery-vs-binary/` once they ran (the app needs the phone
unlocked; a later sitting if not in this one).
