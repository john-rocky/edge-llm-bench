# 2026-09-24 — Dashboard long-context column, Galaxy S26 leg, sitting 5 (Qwen3-4B): the llama.cpp control ladder only, prefill ≈2K / decode 256, three KV allocations

One-line result: the control arm is flat on the dashboard's largest model too — llama.cpp b8999 `Qwen3-4B-Q4_K_M.gguf` decodes
7.5 / 7.5 / 7.4 tok/s at `n_ctx` 2,304 / 4,096 / 8,192 (−0.0 % / −1.3 %, spread ≤ 5 %) while its resident memory grows with the
allocation (5,207 → 5,454 → 6,035 MiB). No LiteRT-LM row: the only published LiteRT file of this model (`mixed_int4`) carries a
2,048-entry KV and cannot run this task (`exclude=bundle-kv-2048-entries-2k-prefill-plus-256-overruns`, as on the Mac). With
this sitting the S26 leg covers all five dashboard models; instrument, protocol and the reasons for them:
`results/raw/2026-09-20-dashboard-longctx-v1-s26-android-gemmae2b/NOTES.md` (sitting 1).

## What was measured

- Cells: `matrices/dashboard-longctx-v1-android-s26-qwen4.cells` — the S26 anchor + llama.cpp × 3 = 4 launches per round (the
  six LiteRT rows are `exclude=`, listed in `SKIPPED.txt`). `llama-cli -c <n_ctx> … -st`, one generation per process
  (`cold-process`), greedy; the bracket summary gives rates only — no token counts, no TTFT, no text — so the control carries
  no text check, as in sittings 1–4.
- Engines b8999 (witness = pin); same capture code state as sittings 1–4.
- Shape: `ROUNDS=8 COOLDOWN=30 THERMAL_WAIT=600 BENCH_CPU_MASK=`, 10:23–12:17 JST, **5 complete rounds** (20 launches, 20
  records); the no-new-round cutoff (minute 100 of a 120-minute cap) stopped round 6 before it started — nothing incomplete.
  Each control launch ran ≈260 s (4B Q4_K_M prefill of 1,986 tokens at ≈9 tok/s); 14 of 20 launches ended at thermal status 2,
  every launch started at status 0 after the gate; battery 34.1–41.9 °C. Screen on at round 1, off (`Dozing`) from round 2 —
  the owner's "stay awake" setting was off this time.
- Admission: anchor 107.5 / 106.8 / 104.7 / 108.3 / 108.9 tok/s — median 107.5, 1.018 of the 2026-09-14 S26 reference (105.6)
  — admitted under the 5 % rule. All five rounds kept; no cell above 10 % spread.

## Decode at depth, tok/s (median [min–max] over the 5 rounds) — `ladder-cold-process.md` / `.csv` has prefill and RSS

llama.cpp (b8999 `llama-cli -t 4`) — the control arm, `cold-process`:

| model (file) | ctx 2304 | ctx 4096 | ctx 8192 | Δ 2304→4096 | Δ 2304→8192 |
|---|---|---|---|---:|---:|
| Qwen3-4B Q4_K_M | 7.5 [7.2–7.6] | 7.5 [7.2–7.5] | 7.4 [7.2–7.5] | −0.0 % | −1.3 % |

Prefill 8.8 → 8.8 → 8.9 tok/s; peak RSS (sampled VmHWM) 5,207 → 5,454 → 6,035 MiB. (Per-arm ladders on purpose: the public
repo carries single-arm facts.)

## Reading

1. The control reads flat on every dashboard model of this leg (0.6B, 1.7B, E2B, E4B, 4B: within ±1.4 % across 2,304 → 8,192)
   while its KV memory grows with `n_ctx` — the same pattern as the Mac leg's llama.cpp arm. Whatever falls with the allocated
   KV on the LiteRT-LM CPU arm (sittings 1–3) is therefore not the phone's state at a larger allocation.
2. Absolute rates of this cell are the slowest of the column (a 4B decode at ≈7.5 tok/s, 260 s launches); the phone is at
   thermal status 2 for most of every launch's second half, and the rate carries that. Read it as this session's number, not
   as the model's ceiling on the device.

## Files

`app-path-android/` — 20 records (4 per round × 5), one log per launch, ledgers, `session_provenance.txt`, `SKIPPED.txt`;
`ladder-cold-process.md/.csv` — from
`python3 scripts/longctx_ab_report.py results/raw/2026-09-24-dashboard-longctx-v1-s26-android-qwen4 --regime cold-process --rounds 1,2,3,4,5`;
`temperature_log.md`, `spread.md`, `spread_rounds.md`.
