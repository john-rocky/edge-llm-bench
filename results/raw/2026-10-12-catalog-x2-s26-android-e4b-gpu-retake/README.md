# Catalog X2, Galaxy S26: Gemma 4 E4B GPU ladder, second sitting (2026-10-12, 08:07–08:48 JST)

The second sitting of the E4B leg of catalog X2's S26 cell: LiteRT-LM v0.16.0 on the OpenCL GPU, a filled
≈2K-token prompt (task `long-context-2048-gen256-noref`, 1,654 prompt tokens) answered with a constant
256-token answer, at allocated KV 2304 / 4096 / 8192 (`--max_num_tokens`). The first sitting is
`../2026-10-12-catalog-x2-s26-android-e4b-gpu/` (06:51–07:31, four complete rounds). The two sittings are read
side by side and never pooled: devices drift between sittings, and each sitting carries its own anchor.

**PARTIAL: 4 complete rounds of the 6 asked.** Round 5 stopped at the session deadline (hold start + 2,520 s):
launch 17 (anchor) and 18 (E4B 2304) are stored, launch 19 (E4B 4096) is a failed launch (see Exclusions).

## Protocol and environment

- Device: Galaxy S26 SM-S942Q (RFGL80R6A6H, SM8850, Android 16), USB, no CPU mask. One hold of the shared phone
  (`s2_npu_sweep/.device_hold`), 08:06:24–08:48:33. No reboot: `/proc/uptime` 169,082 s at the hold's head,
  171,592 s at its end (`../2026-10-12-catalog-x2-s26-android/device-state/hold4-{start,end}.txt`, `UPTIME.txt`).
- Engine: `litert_lm_advanced_main` v0.16.0 (sha256 e5de2d90…, the `android/engine-pins.json` pin; every record's
  witness), the flat engine directory's eight v0.16.0 files and llama-cli hashed equal to the pins at the hold's head
  and end. Bundle: `litert-community/gemma-4-E4B-it-litert-lm` `gemma-4-E4B-it.litertlm` (wNa8o8, sha256 0b2a8980ce…,
  3,659,530,240 B; the same bytes as the first sitting), pushed by the harness at the first E4B launch.
- Launch: `--backend=gpu --input_prompt_file=… --max_num_tokens=<2304|4096|8192> --max_output_tokens=256
  --num_iterations=2 --async=false --benchmark --benchmark_prefill_tokens=0 --benchmark_decode_tokens=0
  --use_session=false`: one engine per launch, two Conversations in it (iteration 1 = cold, 2 = warm),
  engine-default sampler.
- Driver (the first sitting's protocol, unchanged):

  ```
  CAMPAIGN=2026-10-12-catalog-x2-s26-android-e4b-gpu-retake ROUNDS=6 COOLDOWN=30 THERMAL_WAIT=600 BENCH_CPU_MASK= \
  BENCH_ANDROID_SERIAL=RFGL80R6A6H BENCH_SITTING=1 BENCH_DRIVER_START_EPOCH=1791759984 \
  BENCH_SESSION_DEADLINE=1791762504 nice -n 19 python3 android/bench/run_campaign.py matrices/catalog-x2-s26-e4b-gpu.cells
  ```

  Round order: odd rounds anchor → 2304 → 4096 → 8192, even rounds reversed. Before each launch: cooldown 30 s,
  the thermal gate (status 0, up to 600 s, bounded by the deadline), run_cell's CPU-cap gate (up to 300 s).
- Anchor: llama.cpp b8999 Qwen3-0.6B Q4_K_M short-chat once per round, against the 2026-09-14 S26 reference
  105.6 tok/s (5 % rule).
- Screen: off for the whole sitting (`stay_on_while_plugged_in 0`, KEYCODE_SLEEP; every record `conditions.screen`
  Dozing, every round's mWakefulness Dozing). Restored to stay_on 15 / Awake after the sitting.
- Start: the hold's head read Thermal Status 0 with HAL Current BAT 36.2 / SKIN 37.0 / AP 38.1 °C and capped CPU
  ceilings (policy0 3302.4 / 3628.8, policy6 3648.0 / 4742.4 MHz; the previous holder had just released). After the
  screen went off, the cool-start check (Thermal Status 0 and HAL Current BAT ≤ 36.0 °C) passed at its first read,
  08:06:57: BAT 35.9, SKIN 36.8, AP 38.3 °C. run_cell's CPU-cap gate still found the ceilings capped before the first
  launch (the anchor) and waited ≈10 s; that launch ran uncapped.

## Results (rounds 1–4)

Decode tok/s, median [min–max] over rounds; spread = max/min − 1. Every pooled record is 256 output tokens.
Cold excludes each allocation's first launch (firstEver: the engine builds its caches; the marker is per
allocation, so all three cold iterations of round 1 are apart, n = 3).

| allocation | warm decode | n | warm spread | cold decode | n | cold spread | first-ever (round 1, cold) |
|---:|---|---:|---:|---|---:|---:|---:|
| 2304 | 15.1 [13.2–15.4] | 4 | 16.4 % (owed) | 15.1 [14.9–15.4] | 3 | 3.8 % | 14.6 |
| 4096 | 14.8 [13.7–14.9] | 4 | 9.3 % | 15.1 [14.8–15.6] | 3 | 5.4 % | 14.8 |
| 8192 | 14.5 [13.9–14.6] | 4 | 4.6 % | 14.5 [14.2–15.2] | 3 | 7.2 % | 14.5 |

- Change of the decode median from 2304: warm −2.5 % (4096), −4.0 % (8192); cold +0.3 %, −3.9 %.
- Prefill tok/s medians: warm 1077.9 / 1009.9 / 875.0, cold 1106.1 / 1029.0 / 768.0 (2304 / 4096 / 8192).
- The 2304 warm cell's spread is above the 15 % bar: it is owed a re-take. Its 13.22 is round 4's; the three
  lowest warm values of the sitting (13.22 / 13.66 / 13.93) are the three E4B launches of round 4, each of which
  ended at thermal status 2 with the policy6 ceiling down to 1747.2 MHz (`rounds.md`). That is an observation,
  not an established cause.
- Anchor: 106.8 / 107.5 / 106.8 / 107.5 tok/s, median 107.15 = 1.015 of the reference: admitted (`anchor.md`).

Tables: `ladder-warm.md|csv`, `ladder-cold.md|csv`, `ladder-first-ever.md|csv` (scripts/longctx_ab_report.py),
`spread.md`, `anchor.md`, `temperature_log.md`, `records.md|csv`, `text_check.md`, `rounds.md`.

## Thermal and CPU ceilings

- Every E4B launch started at thermal status 0 and ended at status 1 (5 of the 12 in rounds 1–4) or 2 (7 of 12);
  battery 34.9–37.6 °C at the start, 38.0–41.0 °C at the end. Every GPU record of a complete launch carries `cpu-capped` (◇: pooled on an
  accelerator arm, as `render_leaderboard.CPU_CAP_EXEMPT_ARMS`); the sampler's lowest ceilings per launch were
  policy0 1785.6–1996.8 / 3628.8 and policy6 1747.2–1977.6 / 4742.4 MHz.
- Rounds took 7.5 / 11.1 / 7.2 / 11.1 min. The waits before launches (beyond the 30 s cooldown) summed to
  210 / 401 / 180 / 411 s per round, nearly all at the thermal gate (30–121 s after a launch that ended at status
  1–2); round 1 also holds the 3.66 GB push (≈100 s). Per-launch rows: `rounds.md`.

## Text

All 26 records of complete launches hold 256 tokens, the lexical screen PASS, 0 `Invalid decode` lines. The
decoded text is identical within each allocation (SHA-256 7c8fcf25… at 2304, 131fe348… at 4096, 3f23c1e8… at 8192)
and identical to the first sitting's text at the same allocation: a numbered list of things on-device AI does,
two sentences per item, cut at 256 tokens inside item 5 (8192) — on task, coherent (`text_check.md`).

## Exclusions

- Round 5 (incomplete) is outside every table above.
- Launch 19 (round 5, E4B 4096): the thermal gate passed at 08:48:14, ten seconds before the deadline; run_cell
  bounds the engine with `timeout` at the remaining time minus 8 s, so the engine was killed after 1.6 s (exit 124).
  Its two records carry `engine-exit-124`, `benchmark-iteration-count-0-expected-2`, `text-empty-or-degenerate`;
  `app-path-android/FAILURES.txt` lists it (rc=1). Not a measurement.
- The three round-1 cold iterations are firstEver (cache build), reported apart in `ladder-first-ever.md`.

## Reproduce the tables

From the repository root:

```
C=results/raw/2026-10-12-catalog-x2-s26-android-e4b-gpu-retake
T=results/raw/2026-10-12-catalog-x2-s26-android/tools
for regime in warm cold first-ever; do
  python3 scripts/longctx_ab_report.py $C --task long-context-2048-gen256-noref --regime $regime --rounds 1,2,3,4 \
    --csv $C/ladder-$regime.csv > $C/ladder-$regime.md
done
python3 $T/text_check.py $C                      # text_check.md
python3 $T/session_tables.py $C --rounds 1,2,3,4  # temperature_log.md, spread.md, anchor.md, records.md|csv
python3 $T/round_table.py $C --log $C/driver.log  # rounds.md
```

`driver.log` is the driver's own output for the sitting (home path replaced by `/Users/USER/`); `round_table.py` reads
its `=== <cell> (HH:MM:SS)` lines to split each wait into the thermal gate and the rest. Re-run on 2026-10-12, these
commands reproduce every table here byte for byte.
