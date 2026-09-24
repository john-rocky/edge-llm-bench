# 2026-09-23/24 — Dashboard long-context column, Galaxy S26 leg, sitting 4 (Qwen3-1.7B, dynamic INT8 CPU file): LiteRT-LM cpu and llama.cpp at prefill ≈2K / decode 256, three KV allocations

One-line result: the export whose KV is sized at export does not pay for `maxNumTokens` on the S26 either — LiteRT-LM CPU decode
of `Qwen3_1.7B.litertlm` (dynamic INT8) reads 9.3 / 9.3 / 9.4 tok/s warm and 9.7 / 9.8 / 9.8 cold at 2,304 / 4,096 / 8,192
(+0.2 % / +0.9 %), with resident memory flat (2,867 → 2,867 → 2,868 MiB) and the llama.cpp control flat (+1.3 %) — the same
reading as this file's Mac ladder (28.5 / 28.6 / 28.7, RSS 2,903 → 2,910). Instrument, protocol and the reasons for them:
`results/raw/2026-09-20-dashboard-longctx-v1-s26-android-gemmae2b/NOTES.md` (sitting 1); this note lists only what differs.

## What was measured

- Cells: `matrices/dashboard-longctx-v1-android-s26-qwen17.cells` — the S26 anchor + LiteRT-LM cpu × 3 + llama.cpp × 3 = 7
  launches per round (the GPU ladder is `exclude=s26-gpu-garbage-text-at-2k-prefill`: the wi4b32 GPU build of this model
  returned 256 newline tokens at this prompt in the 2026-09-20 diagnostic). `promptTokenCount` 1,986 and 256 output tokens
  on all 36 LiteRT records; every decoded text coherent on-task Qwen3 thinking (`text_check.md`).
- Files: LiteRT-LM `Qwen3_1.7B.litertlm` — the card's CPU file, dynamic INT8 (`dynamic_wi8_afp32`), the same per-backend split
  as the Android dashboard rows and the Mac leg (`litert-community/Qwen3-1.7B/int8`); llama.cpp `Qwen3-1.7B-Q4_K_M.gguf`.
  Engines v0.16.0 / b8999, witnesses equal to the pins; same capture code state as sittings 1–3.
- Shape: `ROUNDS=8 COOLDOWN=30 THERMAL_WAIT=600 BENCH_CPU_MASK=`, 23:51–02:15 JST, **6 complete rounds** (42 launches, 60
  records, ≈24 min per round); the no-new-round cutoff (minute 125) stopped round 7 before it started — nothing incomplete.
  No restart, no single-cell retry. 0 × `Invalid decode`. A first attempt the same evening (campaign `…-qwen17`, 2 complete
  rounds) was stopped at a launch boundary at 02:14 JST on 2026-09-23 because another lane needed the phone; it is archived
  in the run directory, never pooled, and read the same shape (warm 9.15 / 8.83 / 8.86).
- Conditions: **screen off** this time (`mWakefulness=Dozing` at every round start; `stay_on_while_plugged_in=0`) — sittings
  1–3 ran with the screen on. Every launch started at thermal status 0; battery 35.6–41.7 °C. **All 17 LiteRT CPU launches
  after the first ended at thermal status 2** (each ≈71 s regardless of allocation); the control launches ended at 0 or 1.
  Not a confound for the ladder question: the three allocations sit next to each other in every round, and the cold
  iteration (first 30 s of a status-0 launch) reads the same flat line.
- Admission: anchor 106.4 / 108.3 / 105.5 / 107.5 / 109.2 / 109.5 tok/s — median 107.9, 1.022 of the 2026-09-14 S26 reference
  (105.6) — admitted under the 5 % rule. All six rounds kept; largest cell spread 4 %.

## Decode at depth, tok/s (median [min–max] over the 6 rounds) — `ladder-*.md` / `.csv` have prefill, TTFT, RSS

LiteRT-LM, CPU backend (`litert-lm-cpu`, XNNPACK), dynamic INT8 file:

| regime | ctx 2304 | ctx 4096 | ctx 8192 | Δ 2304→4096 | Δ 2304→8192 |
|---|---|---|---|---:|---:|
| warm (iteration 2) | 9.3 [9.2–9.6] | 9.3 [9.2–9.4] | 9.4 [9.2–9.4] | +0.2 % | +0.2 % |
| cold (iteration 1) | 9.7 [9.6–9.8] | 9.8 [9.6–9.8] | 9.8 [9.6–9.9] | +0.9 % | +0.9 % |

Prefill (warm) 210 → 211 → 210 tok/s; TTFT 9.6 → 9.5 → 9.6 s; peak RSS (sampled VmHWM) 2,867 → 2,867 → 2,868 MiB; launch
wall-clock ≈71 s at every allocation.

llama.cpp (b8999 `llama-cli -t 4`) — the control arm, `cold-process`:

| model (file) | ctx 2304 | ctx 4096 | ctx 8192 | Δ 2304→4096 | Δ 2304→8192 |
|---|---|---|---|---:|---:|
| Qwen3-1.7B Q4_K_M | 15.3 [15.3–15.6] | 15.4 [15.3–15.8] | 15.5 [15.2–15.6] | +1.0 % | +1.3 % |

(Peak RSS of the control does grow with `n_ctx`, 2,459 → 2,656 → 3,116 MiB — llama.cpp allocates its KV at `n_ctx` and
attends over the filled length.) (Per-arm ladders on purpose: the public repo carries single-arm facts.)

## Reading

1. **Which bundles pay is an export property — confirmed on the S26.** The three bundles whose KV is allocated at run time
   (E2B, E4B, the 0.6B wi4b32 build; sittings 1–3) lose 11–74 % of CPU decode between 2,304 and 8,192 and grow 0.7–3 GiB of
   resident memory; this INT8 export moves by under 1 % in rate, memory and wall-clock across the same ladder, exactly as
   on the Mac. `maxNumTokens` does not resize a KV that was sized at export. Whether decode beyond that exported size is
   valid is, as on the Mac, not established here (the 1,986 + 256 tokens of this task fit; see K19 for what an overrun looks
   like).
2. The control is flat and its memory grows with `n_ctx`, the mirror image of the INT8 file (rate flat, memory flat) —
   two different reasons for the same flat rate, both visible in the records.
3. With sitting 4 the S26 leg has the dashboard's four LiteRT-runnable models; only the Qwen3-4B control ladder (no runnable
   LiteRT file) is left, plus the GPU re-takes noted in sittings 1 and 3.

## Files

`app-path-android/` — 60 records (10 per round × 6), one log per launch, decoded text per LiteRT iteration, ledgers,
`session_provenance.txt`, `SKIPPED.txt`; `ladder-warm|cold|cold-process.md/.csv` (no first-ever records: every cache key was
warm from the stopped first attempt) — from `python3 scripts/longctx_ab_report.py results/raw/2026-09-23-dashboard-longctx-v1-s26-android-qwen17-retake --regime <r> --rounds 1,2,3,4,5,6`;
`temperature_log.md`, `spread.md`, `spread_rounds.md`, `text_check.md`.
