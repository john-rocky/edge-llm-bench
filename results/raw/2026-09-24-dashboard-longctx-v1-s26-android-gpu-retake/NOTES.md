# 2026-09-24 — Dashboard long-context column, Galaxy S26 leg, GPU re-take (spread-rule): Gemma 4 E2B and E4B on LiteRT-LM gpu at prefill 1,637, KV allocations 2304 / 4096 / 8192, 6 paired rounds

One-line result: re-measured in their own session, both Gemma 4 GPU ladders read flat with the allocated KV within ±3 % on
the warm iteration — E2B 26.1 / 26.8 / 25.5 tok/s (+2.6 % / −2.6 %), E4B 14.9 / 14.8 / 14.5 (−0.8 % / −3.0 %) — with warm cell
spreads of 3–6 % (one 16 % cell), where sitting 1 had left E2B's 2,304 / 4,096 warm cells at 28 % / 39 % and sitting 3 E4B's
4,096 warm cell at 52 %. The original sittings' reading (the S26 OpenCL GPU decode does not fall with the allocation while
its prefill does) stands, now on tight cells. GPU prefill falls as before: E2B 2,837 → 2,495 → 1,962 tok/s (−31 %), E4B
1,073 → 1,003 → 865 (−19 %).

## What was measured

- Cells: `matrices/dashboard-longctx-v1-android-s26-gpu-retake.cells` — the S26 anchor + E2B gpu × 3 + E4B gpu × 3 = 7 launches
  per round; CPU and control arms not repeated. Files `gemma-4-E2B-it.litertlm` / `gemma-4-E4B-it.litertlm` (wNa8o8),
  LiteRT-LM v0.16.0 `litert_lm_advanced_main` (witness = pin), same capture code as sittings 1–5; instrument and protocol:
  `results/raw/2026-09-20-dashboard-longctx-v1-s26-android-gemmae2b/NOTES.md`.
- Shape: `ROUNDS=8 COOLDOWN=30 THERMAL_WAIT=600 BENCH_CPU_MASK=`, 12:40–13:51 JST, **6 complete rounds** (42 launches, 78
  records); the no-new-round cutoff (minute 75 of a 90-minute cap) stopped round 7 before it started. The phone came in at
  thermal status 2 from another lane's GPU work and the gate waited it down to 0 before launch 1; every launch started at 0
  and **none ended above status 1** (battery 37.1–38.9 °C) — GPU launches are short (14–27 s). Screen off (`Dozing`) at
  every round; `stay_on_while_plugged_in=0`.
- Text: 1,637 prompt tokens on all 72 LiteRT records; E2B answers 256 / 256 / 93 tokens and E4B 61 / 57 / 50 at 2,304 / 4,096 /
  8,192, identical in every round (the same EOS behaviour as sittings 1 and 3: E2B's 8,192 answer and all E4B answers stop
  early — the E4B answer is the placeholder-prompt refusal). 0 × `Invalid decode`. GPU sampler fallback lines present as
  before.
- Admission: anchor 107.0 / 109.2 / 106.9 / 105.6 / 105.7 / 103.0 tok/s — median 106.3, 1.007 of the 2026-09-14 S26 reference —
  admitted under the 5 % rule. All six rounds kept. This campaign is never pooled with sittings 1 / 3: it is read beside them.

## Decode, tok/s (median [min–max] over the 6 rounds) — `ladder-warm|cold.md` / `.csv` have prefill, TTFT, RSS

| model (answer length) | regime | ctx 2304 | ctx 4096 | ctx 8192 | Δ 2304→4096 | Δ 2304→8192 |
|---|---|---|---|---|---:|---:|
| Gemma 4 E2B (256 / 256 / 93) | warm | 26.1 [25.7–27.1] | 26.8 [25.6–29.8] † | 25.5 [25.1–26.0] | +2.6 % | −2.6 % |
| Gemma 4 E2B | cold | 26.2 [25.2–28.8] | 26.5 [25.1–26.9] | 25.6 [25.0–31.2] ‡ | +1.0 % | −2.4 % |
| Gemma 4 E4B (61 / 57 / 50) | warm | 14.9 [14.7–15.6] | 14.8 [14.7–15.3] | 14.5 [14.4–15.2] | −0.8 % | −3.0 % |
| Gemma 4 E4B | cold | 14.9 [14.5–16.3] | 14.7 [14.5–15.8] | 14.2 [14.1–15.0] | −1.9 % | −4.8 % |

† one high round (29.8 in round 5; the other five 25.6–27.1). ‡ two high rounds (29.6, 31.2) on a 93-token answer. The
outliers of this session are all *high* single rounds; sitting 1's were low ones. Medians are unaffected either way.

Beside the originals (warm decode, median): E2B sitting 1 (2026-09-20) 26.0 / 26.0 / 25.0, re-take 26.1 / 26.8 / 25.5;
E4B sitting 3 (2026-09-21) 15.1 / 11.9 / 14.8, re-take 14.9 / 14.8 / 14.5 — the 11.9 of sitting 3 was the 52 %-spread cell,
its re-take reads 14.8 with a 4 % spread. (Cross-session numbers are compared here only through their anchors, 1.005–1.007
of the same reference; the within-session Δ is the reading.)

## Reading

The S26's OpenCL GPU decode of both Gemma 4 bundles is flat across 2,304 / 4,096 / 8,192 allocated tokens at a fixed filled
length (±3 % warm, on six paired rounds each), while GPU prefill falls with the allocation (−19 % to −31 % at 8,192) and,
per sittings 1–3, the XNNPACK CPU decode of the same bundles falls 11–33 %. The Mac leg's Metal-backed GPU lost 9–18 % of
decode on these bundles; the Android GPU path does not show that cost. What remains open on the GPU side is only the
answer-length caveat (E4B's 50–61-token refusal, E2B's 93 tokens at 8,192): a Δ at a constant 256-token answer would need a
prompt the models do not refuse or cut short.

## Files

`app-path-android/` — 78 records (13 per round × 6), one log per launch, decoded text per LiteRT iteration, ledgers,
`session_provenance.txt`; `ladder-warm|cold.md/.csv` — from
`python3 scripts/longctx_ab_report.py results/raw/2026-09-24-dashboard-longctx-v1-s26-android-gpu-retake --regime <r> --rounds 1,2,3,4,5,6`;
`temperature_log.md`, `spread.md`, `spread_rounds.md`, `text_check.md`.
