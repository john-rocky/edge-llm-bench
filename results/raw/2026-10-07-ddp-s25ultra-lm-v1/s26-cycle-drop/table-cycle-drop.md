# Gemma 4 E2B gpu: where the second cycle's decode drop comes from — the same binary on a Galaxy S26 with a 1 s thermal and clock log (2026-10-07, 16:09–16:15 JST)

Why: on the DDP Galaxy S25 Ultra pool (pa3q-35) the measured process of this cell reports 45–47 tok/s decode in its
first prefill + decode cycle and less in every later cycle (2 iterations: 45.43 → 33.85; 5 iterations: 30.71 → 26.61 →
26.3; `iter-check/table-iter.md`), while prefill does not fall between cycles 1 and 2. The pool gives no temperature or
clock. The same binary and bundle on a Galaxy S26 (SM-S942Q, SoC SM8850 per `ro.soc.model`, Android 16, build S942QOPS1AZH9), over adb, with the
phone's thermal zones and GPU clock read once a second, separates "the phone got hot" from "something inside the
process". One run per setting; nothing here is a measurement.

What ran (`tools/s26_cycle_drop.sh`, `steps.log`): the S26 under the shared hold (16:09:57–16:14:46 JST), battery 79 %,
battery zone 32.0 °C at the start; `litert_lm_advanced_main` sha256 adac974b…2d06 (the DDP sessions' binary, pushed
with its six libraries, 76,740,936 bytes in 1 s) and `gemma-4-E2B-it.litertlm` sha256 18193810…a63c (the copy already
on the phone); every process `--backend=gpu --benchmark=true --benchmark_prefill_tokens=1024 --benchmark_decode_tokens=256
--max_num_tokens=1280 --report_peak_memory_footprint=true --num_iterations=<n>` (the DDP sessions' arguments). The
binary's log says `GPU OpenCL` (`A0.stdout.txt`: `RegisterAccelerator: … name=GPU OpenCL`).

| setting | what | gap before it |
|---|---|---|
| A0 | one process, `--num_iterations=1`, no cache files (writes the two ML Drift caches; = the DDP "first process") | — |
| A | one process, `--num_iterations=3`, caches present (= the DDP "measured process" at 3 cycles) | 0 s after A0 |
| B1, B2, B3 | three processes, `--num_iterations=1` each, caches present | 0 s after A, 0 s between them |
| C | A again | 180 s rest after B3 |

Thermal log (`thermal.tsv`, one row per second on the phone): the zones `battery`, `sys-therm-0`, `ac`, `ddr`, the
sixteen `cpu-*` and the eleven `gpuss-*` zones of `/sys/class/thermal` (m°C), `clock_mhz` and `gpu_busy_percentage` of
`/sys/class/kgsl/kgsl-3d0`, and `scaling_cur_freq` of cpu0 / cpu2 / cpu6 / cpu7. Which zone is the skin sensor is not
established; `sys-therm-0` is the one that moves slowest.

## Every cycle (`tools/make_table.py` over the process logs and `thermal.tsv`)

Values from the BenchmarkInfo block the binary logs after each cycle; "cycle end" is the device clock of its
`Decode Speed` line; the thermal columns are the thermal row nearest that second; the last column is the maximum
`gpuss-*` temperature and the range of the GPU clock over the cycle's seconds (the last second can include idle).

| setting | process pid | cycle | prefill tok/s | decode tok/s | decode turn s | TTFT s | init ms | peak mem MB | cycle end (device clock) | battery °C | sys-therm-0 °C | cpu max °C | gpu max °C | ddr °C | gpu MHz | gpu busy % | cpu7 MHz | during cycle: gpu max °C / gpu MHz min–max |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| A0 | 6589 | 1 | 3459.77 | 43.83 | 5.841152186 | 0.32 | 6104.80 | 566.629 | 10-07 16:10:21.984 | 33.3 | 41.6 | 64.1 | 74.0 | 70.9 | 1300 | 94 | 2112 | 74.0 / 1300–1300 |
| A | 8218 | 1 | 3874.45 | 43.82 | 5.841818748 | 0.29 | 2700.78 | 612.332 | 10-07 16:10:31.763 | 34.6 | 43.7 | 59.0 | 65.1 | 64.0 | 1100 | 93 | 883 | 71.7 / 1100–1300 |
| A | 8218 | 2 | 3759.47 | 25.53 | 10.026521663 | 0.31 | 2700.78 | 612.332 | 10-07 16:10:42.111 | 35.6 | 45.6 | 68.3 | 75.6 | 74.4 | 1300 | 99 | 883 | 75.6 / 1050–1300 |
| A | 8218 | 3 | 3860.98 | 23.85 | 10.734064475 | 0.31 | 2700.78 | 612.332 | 10-07 16:10:53.116 | 36.8 | 47.9 | 80.2 | 67.8 | 73.6 | 222 | 0 | 3648 | 77.9 / 222–1300 |
| B1 | 9534 | 1 | 4104.34 | 45.47 | 5.630378748 | 0.27 | 2245.72 | 691.492 | 10-07 16:11:02.206 | 37.8 | 48.5 | 67.9 | 70.2 | 76.8 | 1300 | 0 | 3648 | 80.6 / 1300–1300 |
| B2 | 9859 | 1 | 4157.72 | 45.99 | 5.567017133 | 0.27 | 2125.86 | 618.07 | 10-07 16:11:10.719 | 38.7 | 49.4 | 77.9 | 69.4 | 73.6 | 222 | 0 | 883 | 81.8 / 222–1300 |
| B3 | 10228 | 1 | 4147.28 | 46.24 | 5.536612445 | 0.27 | 2267.85 | 688.137 | 10-07 16:11:19.419 | 38.7 | 50.2 | 69.0 | 67.1 | 69.8 | 222 | 0 | 883 | 83.0 / 222–1300 |
| C | 17294 | 1 | 4161.49 | 43.31 | 5.911078852 | 0.27 | 2231.58 | 688.758 | 10-07 16:14:28.419 | 35.4 | 42.3 | 70.2 | 79.9 | 77.9 | 1300 | 96 | 2112 | 79.9 / 1300–1300 |
| C | 17294 | 2 | 4160.43 | 39.45 | 6.48973781 | 0.27 | 2231.58 | 688.758 | 10-07 16:14:35.198 | 36.7 | 45.0 | 57.5 | 60.1 | 58.9 | 826 | 0 | 2112 | 79.9 / 826–1300 |
| C | 17294 | 3 | 3177.06 | 36.66 | 6.983296559 | 0.35 | 2231.58 | 688.758 | 10-07 16:14:42.536 | 36.7 | 45.4 | 59.0 | 54.3 | 55.0 | 222 | 0 | 2112 | 60.8 / 222–826 |

Per-second rows of the three windows (device clock; `cpu-0-0-0`, `cpu-1-0-0`, `gpuss-4`, `ddr` in °C; the rest as logged):

| time | battery | sys-therm-0 | cpu-0-0-0 | cpu-1-0-0 | gpuss-4 | ddr | GPU MHz | GPU busy % | cpu7 kHz | what was running |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 16:10:10 | 32.3 | 38.0 | 54.8 | 50.4 | 43.0 | 45.3 | 222 | 0 | 4185600 | A0 |
| 16:10:11 | 32.3 | 38.3 | 68.3 | 69.0 | 48.8 | 54.6 | 1300 | 0 | 4185600 | A0 |
| 16:10:12 | 32.3 | 38.7 | 62.1 | 74.4 | 49.6 | 54.6 | 222 | 0 | 4185600 | A0 |
| 16:10:13 | 32.3 | 39.0 | 56.0 | 72.9 | 49.2 | 55.4 | 222 | 0 | 3763200 | A0 |
| 16:10:15 | 32.3 | 39.5 | 62.5 | 54.3 | 48.0 | 51.9 | 1300 | 0 | 3763200 | A0 |
| 16:10:16 | 32.3 | 39.8 | 56.7 | 60.1 | 64.3 | 58.5 | 1300 | 0 | 2112000 | A0 |
| 16:10:17 | 32.3 | 40.1 | 56.3 | 57.7 | 70.2 | 67.1 | 1300 | 0 | 2112000 | A0 |
| 16:10:18 | 33.3 | 40.5 | 56.3 | 58.5 | 71.3 | 68.6 | 1300 | 95 | 2112000 | A0 |
| 16:10:20 | 33.3 | 41.0 | 56.3 | 58.9 | 72.1 | 69.0 | 1300 | 96 | 883200 | A0 |
| 16:10:21 | 33.3 | 41.6 | 59.8 | 61.2 | 74.0 | 70.9 | 1300 | 94 | 2112000 | A0 |
| 16:10:22 | 33.3 | 42.2 | 56.0 | 56.2 | 54.3 | 56.6 | 222 | 0 | 2112000 | A0 |
| 16:10:23 | 33.3 | 42.7 | 56.3 | 53.1 | 51.9 | 53.9 | 1300 | 61 | 2112000 | A cycle 1 |
| 16:10:25 | 33.3 | 43.0 | 53.6 | 55.4 | 52.3 | 56.2 | 1300 | 0 | 2668800 | A cycle 1 |
| 16:10:26 | 33.3 | 43.2 | 55.6 | 54.6 | 62.8 | 55.8 | 1300 | 0 | 2112000 | A cycle 1 |
| 16:10:27 | 33.3 | 43.2 | 56.3 | 58.5 | 71.7 | 67.8 | 1300 | 86 | 883200 | A cycle 1 |
| 16:10:28 | 33.3 | 43.3 | 56.0 | 57.7 | 67.4 | 65.5 | 1200 | 92 | 883200 | A cycle 1 |
| 16:10:30 | 34.6 | 43.5 | 56.0 | 58.1 | 65.5 | 64.7 | 1100 | 93 | 883200 | A cycle 1 |
| 16:10:31 | 34.6 | 43.7 | 55.6 | 57.7 | 65.1 | 64.0 | 1100 | 93 | 883200 | A cycle 1 |
| 16:10:32 | 34.6 | 43.9 | 56.0 | 57.7 | 65.9 | 64.7 | 1100 | 91 | 883200 | A cycle 2 |
| 16:10:33 | 34.6 | 44.1 | 58.3 | 59.3 | 65.9 | 66.3 | 1100 | 94 | 1977600 | A cycle 2 |
| 16:10:35 | 34.6 | 44.3 | 58.7 | 59.7 | 64.3 | 65.5 | 1100 | 97 | 883200 | A cycle 2 |
| 16:10:36 | 34.6 | 44.4 | 58.7 | 59.3 | 64.0 | 65.5 | 1050 | 99 | 883200 | A cycle 2 |
| 16:10:37 | 34.6 | 44.6 | 60.2 | 60.8 | 72.5 | 69.8 | 1300 | 99 | 883200 | A cycle 2 |
| 16:10:39 | 35.6 | 44.8 | 59.8 | 61.6 | 71.7 | 70.9 | 1300 | 99 | 883200 | A cycle 2 |
| 16:10:40 | 35.6 | 45.0 | 61.7 | 62.8 | 72.9 | 71.7 | 1300 | 99 | 883200 | A cycle 2 |
| 16:10:41 | 35.6 | 45.3 | 61.4 | 62.8 | 73.3 | 72.5 | 1300 | 99 | 883200 | A cycle 2 |
| 16:10:42 | 35.6 | 45.6 | 62.1 | 64.3 | 75.6 | 74.4 | 1300 | 99 | 883200 | A cycle 2 |
| 16:10:44 | 35.6 | 45.9 | 62.5 | 64.0 | 75.2 | 74.0 | 1300 | 99 | 883200 | A cycle 3 |
| 16:10:45 | 35.6 | 46.2 | 62.5 | 64.0 | 75.2 | 73.6 | 1300 | 99 | 883200 | A cycle 3 |
| 16:10:46 | 35.6 | 46.5 | 65.2 | 66.7 | 75.2 | 75.2 | 1300 | 99 | 883200 | A cycle 3 |
| 16:10:48 | 35.6 | 46.8 | 64.1 | 65.5 | 76.0 | 75.2 | 1300 | 99 | 883200 | A cycle 3 |
| 16:10:49 | 35.6 | 47.1 | 65.2 | 65.9 | 77.5 | 75.6 | 1300 | 99 | 883200 | A cycle 3 |
| 16:10:50 | 36.8 | 47.4 | 65.2 | 65.9 | 77.1 | 75.6 | 1300 | 99 | 883200 | A cycle 3 |
| 16:10:51 | 36.8 | 47.6 | 65.6 | 67.1 | 77.1 | 76.4 | 1300 | 99 | 883200 | A cycle 3 |
| 16:10:53 | 36.8 | 47.9 | 64.5 | 73.3 | 67.4 | 73.6 | 222 | 0 | 3648000 | A cycle 3 |
| 16:10:54 | 36.8 | 48.2 | 66.4 | 64.7 | 58.5 | 62.4 | 1300 | 0 | 883200 | B1 |
| 16:10:55 | 36.8 | 48.3 | 59.0 | 59.7 | 63.6 | 67.1 | 1300 | 0 | 883200 | B1 |
| 16:10:56 | 36.8 | 48.3 | 62.9 | 66.3 | 75.2 | 71.7 | 1300 | 90 | 883200 | B1 |
| 16:10:58 | 36.8 | 48.1 | 61.7 | 64.3 | 79.1 | 74.8 | 1300 | 92 | 883200 | B1 |
| 16:10:59 | 36.8 | 48.1 | 62.5 | 65.1 | 79.5 | 75.6 | 1300 | 93 | 883200 | B1 |
| 16:11:00 | 37.8 | 48.3 | 62.5 | 65.5 | 80.6 | 76.4 | 1300 | 92 | 883200 | B1 |
| 16:11:02 | 37.8 | 48.5 | 62.9 | 65.9 | 69.8 | 76.8 | 1300 | 0 | 3648000 | B1 |
| 16:11:03 | 37.8 | 48.7 | 66.4 | 79.1 | 60.1 | 62.8 | 1300 | 0 | 4742400 | B2 |
| 16:11:04 | 37.8 | 48.8 | 61.4 | 69.4 | 60.8 | 66.7 | 1300 | 0 | 3648000 | B2 |
| 16:11:05 | 37.8 | 48.9 | 66.4 | 67.1 | 77.9 | 75.6 | 1300 | 90 | 2112000 | B2 |
| 16:11:06 | 37.8 | 48.9 | 64.5 | 67.1 | 81.0 | 77.1 | 1300 | 96 | 883200 | B2 |
| 16:11:08 | 37.8 | 49.0 | 64.1 | 67.1 | 81.4 | 77.1 | 1300 | 94 | 883200 | B2 |
| 16:11:09 | 37.8 | 49.2 | 64.1 | 67.1 | 81.8 | 77.5 | 1300 | 91 | 883200 | B2 |
| 16:11:10 | 38.7 | 49.4 | 67.9 | 77.9 | 67.8 | 73.6 | 222 | 0 | 883200 | B2 |
| 16:11:12 | 38.7 | 49.6 | 68.7 | 67.8 | 60.8 | 64.3 | 1300 | 0 | 4608000 | B3 |
| 16:11:13 | 38.7 | 49.7 | 62.9 | 69.4 | 61.2 | 67.1 | 1300 | 16 | 3648000 | B3 |
| 16:11:14 | 38.7 | 49.8 | 65.2 | 67.1 | 78.7 | 75.6 | 1300 | 87 | 2112000 | B3 |
| 16:11:15 | 38.7 | 49.8 | 64.5 | 67.1 | 82.2 | 77.5 | 1300 | 96 | 883200 | B3 |
| 16:11:16 | 38.7 | 49.8 | 64.5 | 67.4 | 81.4 | 77.9 | 1300 | 94 | 883200 | B3 |
| 16:11:18 | 38.7 | 50.0 | 65.2 | 67.8 | 83.0 | 78.7 | 1300 | 91 | 883200 | B3 |
| 16:11:19 | 38.7 | 50.2 | 64.5 | 69.0 | 66.3 | 69.8 | 222 | 0 | 883200 | B3 |
| 16:11:20 | 39.5 | 50.4 | 58.3 | 57.4 | 57.0 | 58.5 | 222 | 0 | 883200 | after B3 |
| 16:11:22 | 39.5 | 50.4 | 56.0 | 54.3 | 53.9 | 54.6 | 222 | 0 | 883200 | after B3 |
| 16:14:17 | 35.4 | 38.2 | 65.6 | 59.7 | 43.0 | 44.9 | 578 | 0 | 2227200 | end of the rest |
| 16:14:18 | 35.4 | 38.4 | 50.5 | 44.9 | 43.0 | 45.3 | 422 | 0 | 2112000 | end of the rest |
| 16:14:20 | 35.4 | 38.6 | 51.7 | 55.0 | 42.6 | 44.2 | 222 | 0 | 4185600 | C cycle 1 |
| 16:14:21 | 35.4 | 38.8 | 54.8 | 49.2 | 50.0 | 50.4 | 1300 | 6 | 2112000 | C cycle 1 |
| 16:14:22 | 35.4 | 39.1 | 52.9 | 53.5 | 57.0 | 67.1 | 1300 | 0 | 4185600 | C cycle 1 |
| 16:14:23 | 35.4 | 39.4 | 53.2 | 55.8 | 68.2 | 65.1 | 1300 | 95 | 2112000 | C cycle 1 |
| 16:14:24 | 35.4 | 39.9 | 53.6 | 57.0 | 70.5 | 66.7 | 1300 | 93 | 883200 | C cycle 1 |
| 16:14:26 | 35.4 | 40.6 | 71.4 | 86.8 | 75.2 | 76.0 | 1300 | 94 | 2112000 | C cycle 1 |
| 16:14:27 | 35.4 | 41.4 | 62.1 | 63.2 | 74.4 | 72.5 | 1300 | 95 | 3648000 | C cycle 1 |
| 16:14:28 | 35.4 | 42.3 | 66.4 | 67.1 | 79.9 | 77.9 | 1300 | 96 | 2112000 | C cycle 1 |
| 16:14:29 | 35.4 | 43.2 | 60.6 | 61.6 | 66.3 | 66.7 | 902 | 96 | 883200 | C cycle 2 |
| 16:14:31 | 35.4 | 43.9 | 56.7 | 57.4 | 62.4 | 62.4 | 902 | 94 | 883200 | C cycle 2 |
| 16:14:32 | 35.4 | 44.5 | 55.6 | 56.2 | 60.5 | 60.5 | 902 | 0 | 883200 | C cycle 2 |
| 16:14:33 | 35.4 | 44.8 | 55.2 | 55.0 | 60.5 | 59.3 | 902 | 93 | 883200 | C cycle 2 |
| 16:14:35 | 36.7 | 45.0 | 55.2 | 55.4 | 57.7 | 58.9 | 826 | 0 | 2112000 | C cycle 2 |
| 16:14:36 | 36.7 | 45.2 | 54.4 | 54.6 | 58.9 | 58.9 | 826 | 91 | 883200 | C cycle 3 |
| 16:14:37 | 36.7 | 45.3 | 53.6 | 54.3 | 58.9 | 58.1 | 826 | 94 | 883200 | C cycle 3 |
| 16:14:38 | 36.7 | 45.3 | 53.6 | 53.5 | 58.1 | 57.7 | 826 | 93 | 883200 | C cycle 3 |
| 16:14:40 | 36.7 | 45.3 | 53.6 | 53.5 | 58.5 | 57.7 | 826 | 0 | 883200 | C cycle 3 |
| 16:14:41 | 36.7 | 45.3 | 61.0 | 62.0 | 60.1 | 60.8 | 726 | 94 | 2112000 | C cycle 3 |
| 16:14:42 | 36.7 | 45.4 | 58.3 | 55.8 | 53.5 | 55.0 | 222 | 0 | 2112000 | C cycle 3 |

## What the six runs show

- The drop is inside a process, not in the phone. In one process the second and third cycles decode slower than the
  first (A: 43.82 → 25.53 → 23.85; C: 43.31 → 39.45 → 36.66), with prefill unchanged between cycles 1 and 2 (A 3874 →
  3759 → 3861; C 4161 → 4160 → 3177) and TTFT unchanged (0.29–0.31 s; 0.27–0.35 s). Three new processes started back to
  back on the hotter phone (B1–B3, `sys-therm-0` 48–50 °C, `gpuss-*` up to 83 °C, 0 s between them) each report their
  one cycle at 45.47, 45.99, 46.24, the level of a first cycle.
- Heat does not produce the drop. B ran at the highest temperatures of the sitting and stayed at 45–46. A's second
  cycle ran at `gpuss-*` 66–76 °C and C's first cycle at up to 80 °C with the same 43 tok/s.
- The GPU clock does not produce A's drop. During A's cycle 2 the clock read 1100 → 1050 → 1300 MHz with the GPU
  99 % busy, during A's cycle 3 1300 MHz and 99 % busy, and the decode turn took 10.0 s and 10.7 s for 256 tokens
  against 5.8 s in cycle 1: the GPU was at full clock and fully busy and produced tokens at 58 % of cycle 1's rate.
  In C the clock did fall (1300 MHz in cycle 1, 902 → 826 MHz in cycles 2–3, after `gpuss-4` reached 79.9 °C at the
  end of cycle 1) and the decode fell less (43.3 → 39.5 → 36.7), so C's cycles 2–3 carry a clock reduction on top of
  whatever the in-process effect is; A's do not.
- The CPU does not separate the cases: cpu7 sat at 883,200 kHz during the decode of A's cycles 1–3 and of B1–B3 alike.
- The size of the in-process drop differs between the two 3-cycle runs on the same phone, 20 s apart in state
  (A −42 % at cycle 2, C −9 % at cycle 2), and between the DDP sessions (−25 % at cycle 2 of the 2-iteration session;
  the 5-iteration session's measured process was at 30.71 already in cycle 1). What sets the size is not established.
- No error line from the binary in any of the six processes (`Failed to`, `Invalid decode`, `INTERNAL`, `FATAL`: 0 in
  the process lines); all exit 0; peak memory 686 MB at the end of A's cycle 1 and 2, 784 MB at the end of cycle 3.

So: the decode drop after the first cycle of a `--num_iterations > 1` process is reproduced on the S26 with the DDP
binary and bundle; it is not the phone's temperature and, in A, not the GPU clock; a new process on the hot phone
starts at the first-cycle level. What inside the process changes after the first conversation is not visible in the
log (below).

## What the log says between two cycles (step 5: the lines, not a reading)

The binary logs nothing about the KV cache, token counts or a reset between cycles. Between A's cycle 1 and cycle 2
(pid 8218, `A.logcat-process.txt`) every line is:

```
10-07 16:10:31.763  8218  8218 I native  : I0000 00:00:1791357031.763486    8218 litert_lm_lib.cc:477] Peak private footprint: 686.082MB.
10-07 16:10:31.763  8218  8218 I native  : I0000 00:00:1791357031.763642    8218 litert_lm_lib.cc:865] Creating conversation
10-07 16:10:31.766  8218  8218 W native  : W0000 00:00:1791357031.766309    8218 mel_filterbank.cc:137] Missing 10 bands  starting at 0 in mel-frequency design. Perhaps too many channels or not enough frequency resolution in spectrum.
10-07 16:10:31.766  8218  8218 I native  : I0000 00:00:1791357031.766596    8218 litert_lm_lib.cc:877] Running single-turn conversation
```

The same four lines sit between cycles 2 and 3, and between the cycles of C and of the DDP sessions
(`iter-check/ddp-session/session-6587db64/gpu-pa3q-35/logcat-process.txt`). The engine is created once per process
(one `Creating engine`, one `Init Executor` value repeated in every cycle's block: 2695.65 ms in A); each cycle is a
new conversation on that engine. The only lines of the process that mention the cache or the token limit are the
settings dump at start:

```
10-07 16:10:22.937  8218  8218 I native  : max_tokens: 1280
10-07 16:10:22.937  8218  8218 I native  : clear_kv_cache_before_prefill: true
```

and the per-cycle turn lines:

```
10-07 16:10:31.749  8218  8218 I native  :     Prefill Turn 1: Processed 1024 tokens in 264.295677ms duration.
10-07 16:10:31.749  8218  8218 I native  :     Decode Turn 1: Processed 256 tokens in 5.841818748s duration.
10-07 16:10:42.068  8218  8218 I native  :     Prefill Turn 1: Processed 1024 tokens in 272.378958ms duration.
10-07 16:10:42.068  8218  8218 I native  :     Decode Turn 1: Processed 256 tokens in 10.026521663s duration.
10-07 16:10:53.114  8218  8218 I native  :     Prefill Turn 1: Processed 1024 tokens in 265.217656ms duration.
10-07 16:10:53.114  8218  8218 I native  :     Decode Turn 1: Processed 256 tokens in 10.734064475s duration.
```

`--helpfull` (`../s26-repro/helpfull.txt`) describes `clear_kv_cache_before_prefill` as "If true, clear kv cache
before the first prefill step"; whether and how the KV cache is reset between conversations of one benchmark process
is not in the log and not in the help text.

## Files

`steps.log` (the script's lines, JST), `<setting>.logcat-process.txt` (the logcat lines of that process only),
`<setting>.stdout.txt` (the process's own output, without the per-node `Replacing … node(s)` lines),
`metrics-<setting>.pb` (as written by `--metric_proto_file_path`), `thermal.tsv`, `tools/` (the scripts as run; the
user name replaced by USER). The S26's work directory was removed at the end; the hold was returned at 16:14:46 JST.
Not in `table.md`, not in `results/summary`.

## Rounds 2 and 3 (16:30–16:45 JST, user 16:2x「両方よろしく」): the two flag candidates, and five control runs on the quiet phone

Round 2 (`round2-flags/`): three settings on the same phone, same binary and bundle, each = a cache-writing
1-iteration process then a 3-iteration process 0 s later (the shape of A0 + A), 180 s rest between settings.
E = the round-1 arguments again (control); D = E + `--sampler_backend=cpu`; F = E with `--max_num_tokens=2048`.
Round 3 (`round3-control5/`): the round-1 arguments only, one cache-writing process then five 3-iteration processes
60 s apart, with the screen state (`dumpsys power` `mWakefulness`) logged before each.

| setting | arguments beyond the common ones | cycle 1 | cycle 2 | cycle 3 | GPU MHz / busy % in cycles 2–3 | screen |
|---|---|---|---|---|---|---|
| E0 / E | `--max_num_tokens=1280` (control) | 44.70 (3492) / 45.10 (3921) | 47.64 (3879) | 47.42 (3690) | 1200–1300 / 91–92 | dozing |
| D0 / D | `--max_num_tokens=1280 --sampler_backend=cpu` | 44.56 (3952) / 45.16 (3938) | 44.76 (3648) | 44.83 (3815) | 1300 / 83–86 | dozing |
| F0 / F | `--max_num_tokens=2048` | 44.83 (3704) / 45.16 (3716) | 47.73 (3480) | 47.72 (3636) | 1300 / 91–92 | dozing |
| G0 | `--max_num_tokens=1280` (cache-writing) | 45.67 (3441) | — | — | — | dozing |
| G1 | `--max_num_tokens=1280` | 44.30 (3778) | 47.29 (3772) | 46.97 (3692) | 1300 / 91–92 | dozing |
| G2 | 〃 | 44.99 (3358) | 47.26 (3918) | 47.23 (3642) | 1300 / 91–92 | dozing |
| G3 | 〃 | 45.03 (3969) | 47.25 (3669) | 47.45 (3629) | 1300 / 90–91 | dozing |
| G4 | 〃 | 45.03 (4024) | 47.57 (3711) | 47.74 (4044) | 1300 / 90–92 | dozing |
| G5 | 〃 | 45.48 (3919) | 47.75 (3762) | 47.56 (3734) | 1300 / 91–92 | dozing |

(decode tok/s, prefill in brackets; every cycle with its thermal row: `round2-flags/` and `round3-control5/` through
`tools/make_table.py`.) The binary does not echo `--sampler_backend` in its settings dump; D's GPU busy of 83–86 %
against 91–92 % in every other 3-cycle process is the only sign in the record that the sampler moved. F's dump says
`max_tokens: 2048`.

What this adds:

- On the quiet phone the drop does not occur: eight 3-cycle processes (E, D, F, G1–G5) report 44.3–45.5 in cycle 1
  and 44.8–47.8 in cycles 2–3, GPU at 1300 MHz and 90–92 % busy (83–86 % with the CPU sampler). The second cycle is
  slightly faster than the first in seven of the eight.
- So D and F separate nothing: the control did not drop either. The sampler backend and the KV allocation are not
  shown to matter, and not shown not to.
- The two processes that did drop (A −42 %, C −9 %, round 1) ran while another session was driving the phone's
  screen without the hold: from 16:00 to 16:28 JST SurfaceFlinger logged a screenshot of the foreground app
  `android.template/.ui.MainActivity` two to seven times a minute (`Capture layer list`), with touch events
  (`Touch Boost … choose 120.00 Hz`) and the app redrawing (`VRI[MainActivity]`); the screen was on (`previousDisplayState
  = ON` at 16:10:09, `animateScreenStateChange: target=ON` at 16:14:19). None of that appears in any round-2 or round-3
  window (0 screenshots, 0 touches, 0 redraws; screen dozing). Per round-1 window (lines of the whole logcat window):

| window | decode | screen-state lines | touch | screenshot | app redraws (VRI) |
|---|---|---:|---:|---:|---:|
| A (3 cycles) | 43.8 → 25.5 → 23.9 | 2 | 1 | 1 | 65 |
| B1 | 45.5 | 0 | 0 | 0 | 0 |
| B2 | 46.0 | 1 | 1 | 1 | 71 |
| B3 | 46.2 | 0 | 0 | 0 | 1 |
| C (3 cycles) | 43.3 → 39.5 → 36.7 | 67 | 0 | 2 | 28 |

  The slow cycles coincide with the other session's screen activity in A and C and the quiet windows B1 and B3 are
  fast; B2 is fast with the same activity in its window, so the activity is a lead, not an established cause. The
  signature of the slow cycles — GPU at full clock and 99 % busy, 91–92 % when fast, prefill and TTFT intact — fits a
  second GPU client better than throttling, and the compositor is one.
- For the DDP pool the same reading applies as a hypothesis only: the measured process's later cycles were slower on
  three sessions, the pool gives no screen state, and whether anything else ran on the pool device during the
  measured process is not known.

Files: `round2-flags/` and `round3-control5/` (each: `steps.log`, `<setting>.logcat-process.txt`,
`<setting>.stdout.txt`, `metrics-<setting>.pb`, `thermal.tsv`, `tools/`). The hold was returned at 16:38:10 and
16:45:26 JST; the device dir removed each time.
