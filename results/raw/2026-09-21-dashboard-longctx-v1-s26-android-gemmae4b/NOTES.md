# 2026-09-21 — Dashboard long-context column, Galaxy S26 leg, sitting 3 (Gemma 4 E4B): LiteRT-LM cpu / gpu and llama.cpp at prefill ≈2K / decode ≤256, KV allocations 2304 / 4096 (/ 8192 on GPU and control)

One-line result: at a fixed filled length (1,637 prompt tokens) the LiteRT-LM **CPU** decode of Gemma 4 E4B on the S26 falls
with the allocated KV from 2,304 to 4,096 — warm median 14.5 → 13.0 tok/s (−11 %), cold 14.3 → 12.1 (−15 %), the same
direction in every round (the 8,192 CPU cell is not run: RAM) — the **GPU** decode reads flat on the cold iteration
(15.5 / 15.1 / 15.3, −3 % / −1 %) with a warm iteration too noisy to read (below), and the llama.cpp control is flat (+1 %).
Instrument, protocol and the reasons for them: `results/raw/2026-09-20-dashboard-longctx-v1-s26-android-gemmae2b/NOTES.md`
(sitting 1); this note lists only what differs.

## What was measured

- Cells: `matrices/dashboard-longctx-v1-android-s26-gemmae4b.cells` — the S26 anchor + LiteRT-LM cpu × 2 + LiteRT-LM gpu × 3
  + llama.cpp × 3 = 9 launches per round. The CPU 8,192 row is `exclude=s26-ram-e4b-cpu-8192-mac-rss-over-60pct` (the Mac
  leg's CPU peak RSS at 8,192 was 11.3 GB against this phone's 11.4 GB; not attempted). `promptTokenCount` 1,637 on all 52
  LiteRT records; CPU outputs 256 tokens.
- Files: LiteRT-LM `gemma-4-E4B-it.litertlm` (wNa8o8) on both backends; llama.cpp `gemma-4-E4B-it-Q4_K_M.gguf`. Engines
  v0.16.0 / b8999, witnesses equal to the pins. Same capture code state as sittings 1 and 2.
- GPU text probe first: one GPU launch at 2,304 in `results/raw/2026-09-21-dashboard-longctx-v1-s26-android-e4b-gpuprobe/`
  read coherent, so the GPU ladder ran. **E4B answers this prompt on the GPU with a refusal** — "the provided text is a list
  of placeholder Lorem ipsum … I cannot generate a list" — in **61 / 57 / 50 tokens at 2,304 / 4,096 / 8,192**, the same
  count in every round (EOS; the answer's wording shifts with `maxNumTokens`, as E2B's did at 8,192). On the CPU the same
  bundle fills the 256 budget at both allocations. The GPU decode rates below are over 50–61 tokens, not 256.
- Shape: `ROUNDS=8 COOLDOWN=30 THERMAL_WAIT=600 BENCH_CPU_MASK=`, 09:26–11:51 JST, **5 complete rounds** (45 launches, 70
  records); the no-new-round cutoff (minute 150 of a 170-minute cap) stopped round 6 before it started — nothing incomplete.
  No restart, no single-cell retry. 0 × `Invalid decode`.
- Conditions: screen on, `stay_on_while_plugged_in=15` (as in sittings 1–2). Every launch started at thermal status 0;
  battery 31.6–41.4 °C. The E4B **control launches are the long ones** (llama-cli prefill 12 tok/s → 150–195 s per launch):
  12 of 15 ended at thermal status 2, as did one CPU 2,304 and one CPU 4,096 launch; every LiteRT GPU launch ended at 0 or 1
  (`temperature_log.md`).
- Admission: anchor 106.1 / 107.5 / 102.8 / 107.0 / 102.4 tok/s — median 106.1, 1.005 of the 2026-09-14 S26 reference —
  admitted under the 5 % rule. All five rounds kept.

## Decode at depth, tok/s (median [min–max] over the 5 rounds) — one ladder per arm; `ladder-*.md` / `.csv` have prefill, TTFT, RSS

LiteRT-LM, CPU backend (`litert-lm-cpu`, XNNPACK), 256-token answers:

| regime | ctx 2304 | ctx 4096 | ctx 8192 | Δ 2304→4096 |
|---|---|---|---|---:|
| warm (iteration 2) | 14.5 [14.5–15.0] | 13.0 [12.8–13.1] | not run (RAM) | **−10.9 %** |
| cold (iteration 1) † | 14.3 [13.6–14.5] | 12.1 [11.7–12.3] | not run (RAM) | **−15.2 %** |

† n=4: round 1 is the first-ever run of each cache key (14.5 / 12.4), kept apart in `ladder-first-ever.md`. Prefill (warm)
79 → 71 tok/s; peak RSS (sampled VmHWM) 4,002 → 4,653 MiB.

LiteRT-LM, GPU backend (`litert-lm-gpu`, OpenCL), 61 / 57 / 50-token answers:

| regime | ctx 2304 | ctx 4096 | ctx 8192 | Δ 2304→4096 | Δ 2304→8192 |
|---|---|---|---|---:|---:|
| cold (iteration 1) † | 15.5 [15.2–16.9] | 15.1 [14.7–15.5] | 15.3 [14.7–15.4] | −2.9 % | −1.4 % |
| warm (iteration 2) ‡ | 15.1 [12.5–15.4] | 11.9 [9.7–15.9] | 14.8 [13.8–15.3] | −21.1 % | −2.3 % |

† n=5 / 4 / 4 (first-ever apart). ‡ The warm GPU iteration is the noisy one this time: 4,096 reads 15.9 / 11.2 / 9.7 / 15.6 /
11.9 across the rounds (52 % spread), 2,304 has two low rounds (12.5, 13.6). Over a 57-token answer a few hundred
milliseconds of GPU clock change move the rate by a third; under the spread-rule these two cells are owed a re-take and the
warm Δ is not read. Prefill (cold) 1,056 → 1,018 → 800 tok/s (−4 % / −24 %); host-side peak RSS 898 → 971 → 1,085 MiB.

llama.cpp (b8999 `llama-cli -t 4`) — the control arm, `cold-process`, 256-token answers:

| model (file) | ctx 2304 | ctx 4096 | ctx 8192 | Δ 2304→4096 | Δ 2304→8192 |
|---|---|---|---|---:|---:|
| Gemma 4 E4B Q4_K_M | 8.3 [6.6–8.5] | 8.4 [7.7–8.5] | 8.4 [8.3–8.4] | +1.2 % | +1.2 % |

(2,304 has two low rounds — 7.7 in round 1 and 6.6 in round 5, 23 % spread — the other three read 8.3–8.5; the control
launches of every allocation end at thermal status 2 in most rounds.) (Per-arm ladders on purpose: the public repo carries single-arm facts.)

Re-take (2026-09-24, `results/raw/2026-09-24-dashboard-longctx-v1-s26-android-gpu-retake/`): the GPU ladder measured again in its
own session of 6 paired rounds reads warm 14.9 / 14.8 / 14.5 tok/s (−0.8 % / −3.0 %) with 4–6 % spreads — the 52 %-spread warm
4,096 cell above (11.9) is settled there at 14.8; the reading (flat) is unchanged.

## Reading

1. **CPU: the allocated-KV cost is there at 4,096** (−11 % warm, −15 % cold, every round), the Mac leg's E4B CPU read −6 %
   at the same step and −21 % at 8,192; the 8,192 step could not be taken on this phone's RAM. Resident memory 4.0 → 4.7 GiB.
2. **GPU: flat on the cold ladder, unreadable on the warm one.** The cold iteration — five or four rounds within 5–11 % —
   reads −3 % / −1 %, the same picture as E2B's GPU (−0 % / −4 %) and K17's empty-cache S26 sweep; GPU prefill falls with
   the allocation (−24 % at 8,192), as it did for E2B (−32 %) and on the Mac. What this bundle adds is a caveat, not a
   number: a 50–61-token answer makes the per-record rate fragile, and the warm 4,096 cell's 52 % spread is that fragility.
   A GPU Δ for E4B at the 256-token length needs a prompt the model does not refuse.
3. **llama.cpp is the control**: flat within 1.2 %, across launches that end hotter than any LiteRT launch of the session.

## Files

`app-path-android/` — 70 records (14 per round × 5), one log per launch, decoded text per LiteRT iteration, ledgers,
`session_provenance.txt`, `SKIPPED.txt`; `ladder-warm|cold|cold-process|first-ever.md/.csv` — from
`python3 scripts/longctx_ab_report.py results/raw/2026-09-21-dashboard-longctx-v1-s26-android-gemmae4b --regime <r> --rounds 1,2,3,4,5`;
`temperature_log.md`, `spread.md`, `spread_rounds.md`, `text_check.md`; the probe campaign's `README.md`.
