# Gemma 4 E2B gpu: how prefill moves with `--max_num_tokens`, and cold against cached — Galaxy S26, 2026-10-08 02:00–02:08 JST (round 4)

Why: the Kotlin `DeviceBenchmarkTest` of the LiteRT team's table reports 1980 (first, cold) and 2890 (second, after a
warm-up) tok/s prefill for this bundle on the pool's Galaxy S25 Ultra, and does not set a max token count; the DDP row
of this repo (`table.md`, session-0d1cde8d) reports 3689 in its measured process's first cycle at the CLI default
`--max_num_tokens=1280`. This round measures, on the Galaxy S26 (SM-S942Q, SoC SM8850, Android 16), how the same
binary's prefill moves with the allocated context and with the cache files, so that the difference can be read.
One cycle per process, not a measurement of the S26.

What ran (`tools/s26_cycle_drop_4.sh`, `steps.log`): hold 02:00:29–02:07:41 JST; screen `mWakefulness=Dozing` before and
after the runs, 0 screenshot and 0 touch lines in any window; battery 79 %, battery zone 28.9 → 33.6 °C; binary sha256
adac974b…2d06 (pushed, 76,740,936 bytes with its six libraries), bundle sha256 18193810…a63c (the copy on the phone).
Every process: `--backend=gpu --benchmark=true --benchmark_prefill_tokens=1024 --benchmark_decode_tokens=256
--num_iterations=1 --report_peak_memory_footprint=true` plus the setting's argument; 30 s between processes.

| setting | argument | what it stands for |
|---|---|---|
| A | none | the binary left to its default |
| B | `--max_num_tokens=1280` | the DDP sessions' value (the CLI default) |
| C | `--max_num_tokens=4096` | the engine's default size when an app sets nothing and the bundle carries no limit (per the launch note; not verified here) |
| D | none, the two ML Drift cache files removed first | cold start, the shape of the Kotlin test's first run; D1 opened the round and wrote the caches A–C used, D2 closed it |

## Every process (`tools/make_table_maxtokens.py`)

| process | setting | max_tokens (settings dump) | caches at start | prefill tok/s | decode tok/s | TTFT s | init ms | peak mem MB | cycle end (device clock) | battery °C | sys-therm-0 °C | gpu max °C | GPU MHz | GPU busy % |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|
| D1 | no --max_num_tokens, cache files removed first (cold) | 1280 | 0 | 3479.22 | 46.95 | 0.32 | 6809.72 | 733.25 | 10-08 02:00:59.488 | 29.9 | 35.5 | 66.7 | 1300 | 95 |
| A1 | no --max_num_tokens (engine default) | 1280 | 2 | 3965.61 | 45.21 | 0.28 | 2269.91 | 697.336 | 10-08 02:01:38.443 | 30.6 | 35.8 | 46.5 | 222 | 91 |
| B1 | --max_num_tokens=1280 | 1280 | 2 | 3991.13 | 45.36 | 0.28 | 2268.19 | 696.277 | 10-08 02:02:17.448 | 31.0 | 35.9 | 65.5 | 1300 | 91 |
| C1 | --max_num_tokens=4096 | 4096 | 2 | 3195.36 | 45.00 | 0.34 | 6453.86 | 761.238 | 10-08 02:03:00.786 | 31.4 | 36.8 | 67.1 | 1300 | 91 |
| A2 | no --max_num_tokens (engine default) | 1280 | 2 | 3991.40 | 45.43 | 0.28 | 2124.91 | 696.617 | 10-08 02:03:39.678 | 32.0 | 37.2 | 50.4 | 222 | 91 |
| B2 | --max_num_tokens=1280 | 1280 | 2 | 4006.26 | 45.46 | 0.28 | 2179.70 | 691.926 | 10-08 02:04:18.574 | 32.4 | 37.1 | 67.1 | 1300 | 91 |
| C2 | --max_num_tokens=4096 | 4096 | 2 | 3169.90 | 44.78 | 0.35 | 2198.52 | 717.176 | 10-08 02:04:57.656 | 32.6 | 37.6 | 58.5 | 1300 | 91 |
| A3 | no --max_num_tokens (engine default) | 1280 | 2 | 4015.72 | 45.29 | 0.28 | 2097.50 | 691.348 | 10-08 02:05:36.443 | 32.9 | 37.7 | 67.8 | 1300 | 92 |
| B3 | --max_num_tokens=1280 | 1280 | 2 | 3990.50 | 45.67 | 0.28 | 2147.52 | 691.48 | 10-08 02:06:15.221 | 33.1 | 38.0 | 68.6 | 1300 | 91 |
| C3 | --max_num_tokens=4096 | 4096 | 2 | 3216.28 | 45.04 | 0.34 | 2271.78 | 717.348 | 10-08 02:06:54.324 | 33.4 | 38.6 | 50.8 | 222 | 92 |
| D2 | no --max_num_tokens, cache files removed first (cold) | 1280 | 0 | 3995.38 | 45.31 | 0.28 | 6494.07 | 723.941 | 10-08 02:07:37.582 | 33.6 | 39.2 | 58.1 | 1300 | 88 |

| setting | n | prefill tok/s (each) | prefill median | spread (max/min − 1) | decode median | TTFT median s | init median ms |
|---|---:|---|---:|---:|---:|---:|---:|
| A: no --max_num_tokens (engine default) | 3 | 3965.61, 3991.40, 4015.72 | 3991.4 | 1.3% | 45.29 | 0.28 | 2125 |
| B: --max_num_tokens=1280 | 3 | 3991.13, 4006.26, 3990.50 | 3991.1 | 0.4% | 45.46 | 0.28 | 2180 |
| C: --max_num_tokens=4096 | 3 | 3195.36, 3169.90, 3216.28 | 3195.4 | 1.5% | 45.00 | 0.34 | 2272 |
| D: no --max_num_tokens, cache files removed first (cold) | 2 | 3479.22, 3995.38 | 3737.3 | 14.8% | 46.13 | 0.30 | 6652 |

## What the eleven processes show

- **A is not the app's condition.** Without `--max_num_tokens` the binary's settings dump says `max_tokens: 1280` in
  all three A processes and both D processes: in benchmark mode the binary sets the value from the token counts
  (1024 + 256), as its help text says:

```
    --max_num_tokens (Maximum number of tokens or context length to use for LLM
      execution of a graph with dynamic context length. If 0, the maximum
      context length will be determined by some heuristic. On benchmark mode, it
      will be set to one equal to or greater than benchmark_prefill_tokens +
      benchmark_decode_tokens.); default: 0;
```

  So A and B are the same setting here (prefill medians 3991.4 and 3991.1), and the engine default an app gets
  (the bundle's metadata limit, else 4096 per the launch note) is not reached through this binary; C is the stand-in
  for the 4096 case. Whether this bundle's metadata carries a max token count was not read.
- **1280 → 4096: prefill −20 %, decode flat.** B 3991 → C 3195 tok/s median (−19.9 %), spreads 0.4 % and 1.5 %;
  decode 45.46 → 45.00; TTFT 0.28 → 0.34 s; peak memory 691–697 → 717–761 MB.
- **Cold against cached: init ×3, prefill 0–13 %.** The two cold processes (no cache files) initialize in 6810 and
  6494 ms against 2097–2272 ms with the caches, and prefill 3479 (D1, −13 % against A's median) and 3995 (D2, the
  same as cached). Decode 46.95 and 45.31. Two samples; the first process after the push (D1) is the lower one.
- **The caches and 4096.** C1 started with the two cache files D1 had written at 1280 and still initialized in
  6454 ms (as if uncached); C2, C3 and the A and B processes after it initialized in 2097–2272 ms. The cache file
  names carry the bundle's mtime and size, not the token limit (`gemma-4-E2B-it.litertlm_<mtime>_2588147712_mldrift_
  program_cache.bin`, `…_weight_cache.bin`); the file count stayed 2. What the files held after C1 was not read.
- **Reading against the team's two numbers (a hypothesis; the pool's S25 Ultra is a different SoC from this S26, so
  the percentages transfer, not the values):** their second run 2890 against the DDP row's 3689 is −22 %, the size
  of the 1280 → 4096 step measured here (−20 %); their first run 1980 is −46 % against 3689, more than a cold start
  gives here (0–13 %) and more than the 4096 step, so the cold number is not explained by these two factors alone.
  Nothing here says what their harness allocates; that is the question to ask.
- No error line in any process, all exit 0, decode 44.8–47.0 throughout (no later-cycle drop: one cycle per process).

## Files

`steps.log`, `<process>.logcat-process.txt` (the process's logcat lines), `<process>.stdout.txt` (without the per-node
`Replacing … node(s)` lines), `metrics-<process>.pb`, `thermal.tsv` (one row per second: 31 thermal zones, GPU
`clock_mhz` and `gpu_busy_percentage`, four CPU frequencies), `tools/` (the scripts as run; USER for the user name).
Not in `table.md`, not in `results/summary`.
