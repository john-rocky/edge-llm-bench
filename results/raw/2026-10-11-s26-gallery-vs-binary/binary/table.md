| tag | backend / bundle | process | prefill tok/s | decode tok/s | TTFT s | init ms | peak private MB | max_tokens | policy0 max during run (min, MHz of 3,628.8) | policy6 max during run (min, MHz of 4,742.4) | GPU max MHz | cpu-0-0-0 zone first → max °C | gpuss-0 zone first → max °C |
|---|---|---|---:|---:|---:|---:|---:|---:|---|---|---:|---|---|
| G1 | gpu / gemma-4-E2B-it.litertlm | cold | 3040.00 | 44.90 | 0.36 | 6927.04 | 765.848 | 4096 | 3628.8 | 4742.4 | 1300 | 33.9 → 50.5 | 32.5 → 59.7 |
| G2 | gpu / gemma-4-E2B-it.litertlm | cached | 2895.32 | 44.53 | 0.38 | 2296.51 | 729.512 | 4096 | 3628.8 | 4742.4 | 1300 | 36.6 → 50.2 | 35.2 → 60.8 |
| G3 | gpu / gemma-4-E2B-it.litertlm | cold | 3100.92 | 44.94 | 0.35 | 6610.60 | 765.426 | 4096 | 3628.8 | 4742.4 | 1300 | 36.6 → 54.8 | 34.9 → 60.8 |
| G4 | gpu / gemma-4-E2B-it.litertlm | cached | 3182.65 | 44.96 | 0.34 | 2287.52 | 728.293 | 4096 | 3628.8 | 4742.4 | 1300 | 35.9 → 50.2 | 35.2 → 60.5 |
| P1 | gpu / gemma-4-E2B-it.litertlm | cold (traced) | 3211.90 | 45.12 | 0.34 | 6643.08 | 760.496 | 4096 | 3628.8 | 4742.4 | 1300 | 34.7 → 53.2 | 33.3 → 59.7 |
| P2 | gpu / gemma-4-E2B-it.litertlm | cached (traced) | 3200.81 | 44.95 | 0.34 | 2309.78 | 718.477 | 4096 | 3628.8 | 4742.4 | 1300 | 35.9 → 49.0 | 34.5 → 59.7 |
| C1 | cpu / gemma3-1b-it-int4.litertlm | cold | 800.84 | 50.40 | 1.30 | 2986.76 | 1378.06 | 4096 | 3187.2 | 3398.4 | 222 | 37.8 → 86.9 | 36.0 → 56.2 |
| C2 | cpu / gemma3-1b-it-int4.litertlm | cached | 946.49 | 50.82 | 1.10 | 547.61 | 1230.05 | 4096 | 3302.4 | 3648.0 | 222 | 38.2 → 84.5 | 36.8 → 55.8 |
| C3 | cpu / gemma3-1b-it-int4.litertlm | cold | 981.74 | 47.48 | 1.06 | 1817.44 | 1378.02 | 4096 | 2899.2 | 2880.0 | 222 | 39.0 → 83.4 | 38.0 → 55.4 |
| C4 | cpu / gemma3-1b-it-int4.litertlm | cached | 953.82 | 50.98 | 1.09 | 539.64 | 1230.38 | 4096 | 3513.6 | 3974.4 | 222 | 40.1 → 87.2 | 38.4 → 58.1 |
| P3 | cpu / gemma3-1b-it-int4.litertlm | cold (traced) | 952.90 | 52.07 | 1.09 | 3241.35 | 1376.21 | 4096 | 3513.6 | 3974.4 | 222 | 36.3 → 85.7 | 35.2 → 55.4 |
| P4 | cpu / gemma3-1b-it-int4.litertlm | cached (traced) | 959.31 | 51.20 | 1.09 | 3289.51 | 1376.79 | 4096 | 3398.4 | 3859.2 | 222 | 37.0 → 86.9 | 36.4 → 56.6 |

Notes. One cycle per process (`--num_iterations=1`); values from the binary's stdout (`<tag>.stdout.txt`), the clock
ceilings and zone temperatures from the 1-second sampler beside the process (`<tag>.sample.csv`: columns = epoch s,
uptime s, policy0 cur / max kHz, policy6 cur / max kHz, GPU MHz, GPU busy %, then thermal zones gpuss-0, cpu-0-0-0,
cpu-1-0-0, battery, sys-therm-0 in m°C). Screen off (dozing) throughout; nothing else of the measurement's running on
the phone (the traces of P1–P4 list every other process with CPU time: `../../2026-10-11-s26-perfetto/`). G1–G4 and
C1–C4 ran at 12:03–12:09 JST right after a 2-hour nightly job on the same phone (zones 37–40 °C at start); P1–P4 at
12:18–12:21 after cooling to 33 °C. The CPU runs cap the big cores within the run on both occasions (policy6 ceiling
2,880–3,974 MHz of 4,742 while the cpu-0-0-0 zone climbs to 83–87 °C in under 10 s); the GPU runs show no cap.
P4 is not a cached process in effect: its log shows a weight-cache *build* ("XNNPack weight cache build for …", 80
"written to" lines) instead of the "weight cache loaded from" line that C2 and C4 show, and its init (3,290 ms) equals
the cold processes' — the cache-file name it computed differs from the one P3 wrote (see `P3.stdout.txt` /
`P4.stdout.txt`); the cached CPU numbers of this sitting are C2 and C4.
