| tag | backend / bundle | process | prefill tok/s | decode tok/s | TTFT s | init ms | peak private MB | max_tokens | policy0 ceiling min (MHz of 3,628.8) | policy6 ceiling min (MHz of 4,742.4) | GPU max MHz | cpu-0-0-0 zone first → max °C | gpuss-0 zone first → max °C | XNNPACK cache |
|---|---|---|---:|---:|---:|---:|---:|---:|---|---|---:|---|---|---|
| Q1 | gpu / gemma-4-E2B-it.litertlm | cold (traced) | 2807.74 | 46.02 | 0.39 | 4371.81 | 762.887 | 4096 | 3398.4 | 3763.2 | 1300 | 39.3 → 65.2 | 36.8 → 65.5 | — |
| Q2 | gpu / gemma-4-E2B-it.litertlm | cached (traced) | 3360.60 | 46.20 | 0.33 | 1791.32 | 729.570 | 4096 | 3628.8 | 4512.0 | 1300 | 37.0 → 52.1 | 36.4 → 64.7 | — |
| Q3 | cpu / gemma3-1b-it-int4.litertlm | cold (traced) | 830.94 | 47.20 | 1.25 | 1818.45 | 1378.140 | 4096 | 2899.2 | 2880.0 | 222 | 40.1 → 85.3 | 37.6 → 57.7 | built |
| Q4 | cpu / gemma3-1b-it-int4.litertlm | cached (traced) | 972.08 | 50.59 | 1.07 | 264.16 | 1230.770 | 4096 | 3302.4 | 3648.0 | 222 | 38.6 → 83.8 | 36.4 → 55.8 | loaded |
| Q5 | cpu / gemma3-1b-it-int4.litertlm | cached (traced) | 979.45 | 50.24 | 1.07 | 251.58 | 1230.500 | 4096 | 3398.4 | 3859.2 | 222 | 38.6 → 87.6 | 36.4 → 57.0 | loaded |

Notes. Pass 3 = the same binary (bucket object of 2026-09-18, sha256 read back on the phone), the same files and
arguments as `../binary/` (prefill 1,024 / decode 256 / `--max_num_tokens=4096`, one cycle per process), run in the
same sitting as the Gallery sessions of `../gallery/` with the **screen on** (`svc power stayon usb`, `mWakefulness=Awake`
at every START line of `steps.log`) and a cool-down to ≤ 36 °C (max of gpuss-0 / cpu-0-0-0 / cpu-1-0-0, at most 150 s;
every process started at the 150 s limit, 36.6–37.6 °C). Q5 is a second cached CPU process, planned in case Q4
rebuilt its weight cache the way P4 did in the morning; both Q4 and Q5 show "weight cache loaded from". All five
processes were traced (`../../2026-10-11-s26-perfetto/`). The morning's processes in `../binary/` ran with the screen
off. Sampler columns as in `../binary/table.md`.
