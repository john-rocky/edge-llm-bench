# 2026-09-20 — Dashboard long-context column, Galaxy S26 leg, sitting 2 (Qwen3-0.6B, dynamic wi4b32): LiteRT-LM cpu and llama.cpp at prefill ≈2K / decode 256, three KV allocations

One-line result: at a fixed filled length (1,986 prompt tokens + 256 output) the LiteRT-LM **CPU** decode of the wi4b32
file on the S26 falls with the **allocated** KV (`--max_num_tokens`) — warm median 20.0 → 11.3 → 5.1 tok/s at 2,304 / 4,096 /
8,192 (−43 % / −74 %), the same in every one of the six rounds — and the llama.cpp control is flat (−1 %). The LiteRT-LM GPU
ladder of this file is excluded on the S26 (garbage text at this prompt, below). Instrument, protocol and the reasons for
them: `results/raw/2026-09-20-dashboard-longctx-v1-s26-android-gemmae2b/NOTES.md` (sitting 1); this note lists only what
differs.

## What was measured

- Cells: `matrices/dashboard-longctx-v1-android-s26-qwen06.cells` — the S26 anchor + LiteRT-LM cpu × 3 + llama.cpp × 3 = 7
  launches per round (the five `exclude=` rows are in `SKIPPED.txt`). Task `long-context-2048-gen256`; `promptTokenCount`
  1,986 and 256 output tokens on all 36 LiteRT records of the complete rounds — the Mac leg's count for Qwen3.
- Files: LiteRT-LM `Qwen3-0.6B_dynamic_wi4b32_afp32.litertlm` (the litert-community GPU-graph build, 32,771-token cache; a
  different recipe from the dashboard's `mixed_int4` file, which carries a 2,048-entry KV and cannot run this task —
  quant-label-rule, as on the Mac); llama.cpp `Qwen3-0.6B-Q4_K_M.gguf`. Engines LiteRT-LM v0.16.0 / llama.cpp b8999, witnesses
  equal to `android/engine-pins.json`. Same capture code state as sitting 1.
- Shape: `ROUNDS=8 COOLDOWN=30 THERMAL_WAIT=600 BENCH_CPU_MASK=`, 20:45–23:05 JST, **6 complete rounds** (42 launches, 60
  records); the 150-minute driver cap cut round 7, whose 5 records are kept in `incomplete-round7/`, outside every table. No
  restart, no single-cell retry. LiteRT launches = 2 iterations (cold, warm) through `litert_lm_advanced_main`; the log of
  every launch prints `max_tokens:` equal to the row's allocation; 0 × `Invalid decode`.
- Text check (`text_check.md`): every LiteRT record is coherent on-task Qwen3 thinking text that fills the 256 budget (the
  same two texts at all three allocations — cold and warm differ from each other, not across allocations).
- Conditions: screen on and `stay_on_while_plugged_in=15` for the whole session (the state sitting 1's rounds 2–5 ran in).
  Every launch **started** at thermal status 0 (gate), battery 30.9–41.6 °C. **Every CPU 8,192 launch ended at thermal status
  2 (moderate)** after ≈145 s of work, as did two of the six CPU 4,096 launches; all other launches ended at 0 or 1
  (`temperature_log.md`). See reading 2.
- Admission: anchor 104.6 / 104.2 / 101.3 / 105.2 / 103.0 / 103.4 tok/s — median 103.8, 0.983 of the 2026-09-14 S26 reference
  (105.6) — admitted under the 5 % rule. All six rounds kept. Round 1 is the coolest round and holds the maximum of every
  LiteRT cell (the three cells at 10–13 % spread in `spread.md` are round 1 against the rest); the medians do not move
  without it.

## Decode at depth, tok/s (median [min–max] over the 6 rounds) — one ladder per arm; `ladder-*.md` / `.csv` have prefill, TTFT, RSS

LiteRT-LM, CPU backend (`litert-lm-cpu`, XNNPACK):

| regime | ctx 2304 | ctx 4096 | ctx 8192 | Δ 2304→4096 | Δ 2304→8192 |
|---|---|---|---|---:|---:|
| warm (iteration 2) | 20.0 [19.8–21.7] | 11.3 [11.2–12.4] | 5.1 [5.0–5.7] | **−43.5 %** | **−74.3 %** |
| cold (iteration 1) | 22.1 [21.2–24.7] | 11.8 [11.6–12.0] † | 5.9 [5.8–6.0] | **−46.8 %** | **−73.3 %** |

† n=5: round 1 at 4,096 was the first-ever run of that cache key (12.6) and is kept apart in `ladder-first-ever.md`.

Prefill (warm) 178 → 124 → 70 tok/s (−30 % / −61 %); TTFT 11.2 → 16.1 → 28.8 s; peak RSS (sampled VmHWM) 1,760 → 2,641 →
4,654 MiB.

llama.cpp (b8999 `llama-cli -t 4`) — the control arm, `cold-process`:

| model (file) | ctx 2304 | ctx 4096 | ctx 8192 | Δ 2304→4096 | Δ 2304→8192 |
|---|---|---|---|---:|---:|
| Qwen3-0.6B Q4_K_M | 21.1 [20.7–21.2] | 20.9 [20.6–21.1] | 20.9 [20.9–21.3] | −1.0 % | −0.5 % |

(Per-arm ladders on purpose: the public repo carries single-arm facts.)

## Reading

1. **This file pays the most for the allocated KV, on the S26 as on the Mac.** −43 % at 4,096 and −74 % at 8,192; the Mac
   leg read −25 % / −60 % for the same file, and catalog row K17's S26 sweep of this export spelling read 94.9 → 52.9 → 15.4
   tok/s at 384 / 1,024 / 4,096 with an empty cache. Resident memory grows with the allocation (1.7 → 4.5 GiB).
2. **Heat does not explain the ladder.** The 8,192 launches are the longest (≈145 s) and end at thermal status 2, so the
   warm iteration there runs on a hotter phone than any other cell. The cold iteration — the first minute of a launch that
   started at status 0 — reads the same Δ within two points (−73 % against −74 %), the 4,096 cell already loses 43–47 % while
   ending at status 0–1 in four rounds of six, and the n=1 instrument smoke of the same day read 25.0 → 6.3 tok/s on a
   phone that started at 34.9 °C. The absolute 8,192 warm rate is the one number here that carries a thermal share.
3. **llama.cpp is the control**: flat within 1 %, with a 2 % round-to-round spread, across the same session and the same
   heat history — the fall is the runtime's.

## Exclusions

- LiteRT-LM GPU, all three allocations: `exclude=s26-gpu-garbage-text-at-2k-prefill`. Evidence:
  `results/raw/2026-09-20-dashboard-longctx-v1-s26-android-smoke/` (this file, this prompt, S26 GPU: 256 tokens of `]` /
  `]].` at a normal-looking rate, 0 × `Invalid decode`) and `…-gpudiag/`.
- The dashboard's `mixed_int4` file: `exclude=bundle-kv-2048-entries-2k-prefill-plus-256-overruns`, as on the Mac.

## Files

`app-path-android/` — 60 records (10 per round × 6), one log per launch, decoded text per LiteRT iteration, the launch and
round ledgers, `session_provenance.txt`, `SKIPPED.txt`; `incomplete-round7/`; `ladder-warm|cold|cold-process|first-ever.md/.csv`
— from `python3 scripts/longctx_ab_report.py results/raw/2026-09-20-dashboard-longctx-v1-s26-android-qwen06 --regime <r> --rounds 1,2,3,4,5,6`;
`temperature_log.md`, `spread.md`, `spread_rounds.md`, `text_check.md`. `THERMAL_GATE.txt`'s line is the wait the session
deadline cut short at 23:12; the launch after it did not run (`SITTING_STOP.txt`).
