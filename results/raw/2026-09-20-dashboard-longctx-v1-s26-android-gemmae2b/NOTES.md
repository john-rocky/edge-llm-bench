# 2026-09-20 — Dashboard long-context column, Galaxy S26 leg, sitting 1 (Gemma 4 E2B): LiteRT-LM cpu / gpu and llama.cpp at prefill ≈2K / decode 256, three KV allocations

One-line result: at a fixed filled length (1,637 prompt tokens + up to 256 output) the LiteRT-LM **CPU** decode on the S26
falls with the **allocated** KV (`--max_num_tokens`) — warm median −11 % at 4,096 and −33 % at 8,192 against 2,304, in every
one of the five rounds — while the LiteRT-LM **GPU** decode on the same bundle shows no fall beyond its round-to-round spread
(−4 % at 8,192, with the caveats below) and the llama.cpp control is flat (+1 %). GPU prefill does fall with the allocation
(−12 % / −32 %). This is the Android counterpart of `results/raw/2026-09-18-dashboard-longctx-v1-m4max-mac/NOTES.md` for one
of the five dashboard models; the other four sittings are not run yet.

## What was measured

- Cells: `matrices/dashboard-longctx-v1-android-s26-gemmae2b.cells` (the per-model slice of
  `dashboard-longctx-v1-android-s26.cells`): the S26 session anchor + LiteRT-LM cpu × 3 + LiteRT-LM gpu × 3 + llama.cpp × 3
  = 10 launches per round. Task `long-context-2048-gen256`, now generated for Android too
  (`prompts/text/long-context-2048-gen256.txt`, 27 filler blocks + the forced-output tail, 7,730 bytes, byte-identical to
  the Swift task's text). `promptTokenCount` is 1,637 on all LiteRT records — the same count as on the Mac.
- Device: Galaxy S26 (SM-S942Q, RFGL80R6A6H), USB. `BENCH_CPU_MASK=` (no affinity), as in the other S26 sessions.
- Files: LiteRT-LM `gemma-4-E2B-it.litertlm` (wNa8o8, non-transferable label) on both backends; llama.cpp
  `gemma-4-E2B-it-Q4_K_M.gguf`. Engines: LiteRT-LM v0.16.0, llama.cpp b8999 — every record's witness matches
  `android/engine-pins.json` (binaries and libraries on the phone were hashed before the session, not re-pushed).
- **Instrument change on Android (why this session could not use the dashboard's prompt path).** The v0.16.0 plain
  `litert_lm_main` defines neither `max_num_tokens` nor `max_output_tokens` (`runtime/engine/litert_lm_main.cc`: default
  `EngineSettings` and `SessionConfig`, no such flags), so `context-tokens=` on an Android prompt task was forwarded but
  could not change the allocation. No stored Android record claims such an allocation: all 394 plain-main v0.16.0 prompt
  records in `results/raw/*android*` say `bundle-default`. Prompt tasks that carry `context-tokens=` now run through the
  same tag's `litert_lm_advanced_main` (already hash-pinned, already used for `native-benchmark-*`):
  `--input_prompt_file=… --max_num_tokens=<alloc> --max_output_tokens=256 --num_iterations=2 --async=false --benchmark
  --benchmark_prefill_tokens=0 --benchmark_decode_tokens=0 --use_session=false`. Iteration 1 = cold, iteration 2 = warm (one
  engine, a fresh Conversation each — the Mac leg's `RUNS=2`). The Conversation path applies the chat template. Sampling is
  the engine default (no sampler flags exist), disclosed in `conditions.sampler`. Every launch log prints its setting
  (`max_tokens: 2304 | 4096 | 8192`) and the record stores it as `allocationWitnessTokens`; 0 × `Invalid decode` in all logs.
- llama.cpp control: the dashboard's Android path, `llama-cli -c <alloc> … -st`, one generation per process, regime
  `cold-process`. It has no warm partner on Android (the bracket summary gives rates only — no token counts, no TTFT). It is
  read inside its own regime only.
- Shape: `ROUNDS=8 COOLDOWN=30 THERMAL_WAIT=600` in the Android runner's new round mode — every cell once per round, the
  three allocations of an arm adjacent, full order reversed on even rounds, anchor once per round, gate auto-retry off, the
  thermal gate (wait for status 0) before every launch. The driver had a 150-minute cap: **5 complete rounds**
  (50 launches, 80 records, 11:59–14:00 JST); round 6 was cut by the cap before its anchor and its 15 records are kept in
  `incomplete-round6/`, outside every table. No restart, no single-cell retry. Every launch started at thermal status 0;
  37 of 59 ended at status 1 (light). Battery 31.2–40.3 °C (`temperature_log.md`).
- Text check on every LiteRT record (`text_check.md`; the decoded text of each iteration is stored beside its log): all
  on-task and coherent. CPU answers fill the 256 budget at every allocation. GPU answers fill it at 2,304 and 4,096 and stop
  on EOS after **93 tokens at 8,192** in all five rounds — the answer differs with `maxNumTokens` (engine-default sampling), the same
  observation as the Mac leg's GPU ‡ note. The GPU 8,192 decode rate is therefore over 93 tokens, not 256.
- Conditions to read the numbers with: the screen was on for the whole session (`mWakefulness=Awake` at every round start,
  `round_state.jsonl`), and the owner switched the developer option "stay awake" on by hand between the starts of round 1
  and round 2. Round 1 is also the coolest round. Every GPU log carries the engine's
  `GPU sampler unavailable. Falling back to CPU sampling` (the TopK sampler libraries do not load under `advanced_main`:
  `cannot locate symbol "kLiteRtRuntimeBuiltin"`), so GPU decode here includes CPU-side sampling.
- Admission: the anchor (llama.cpp Qwen3-0.6B Q4_K_M short-chat, once per round) read 106.2 / 106.9 / 105.3 / 106.3 / 107.8
  tok/s — median 106.3, 1.007 of the admitted 2026-09-14 S26 reference (105.6,
  `results/raw/2026-09-14-dashboard-v1-s26-android/SESSION.json`) — admitted under the dashboard's 5 % rule. Each allocation
  sits next to its partners in every round, so the Δ columns are within-round comparisons.

## Decode at depth, tok/s (median [min–max] over the 5 rounds) — one ladder per arm; `ladder-*.md` / `.csv` have prefill, TTFT, RSS

LiteRT-LM, CPU backend (`litert-lm-cpu`, XNNPACK), warm:

| model (file) | ctx 2304 | ctx 4096 | ctx 8192 | Δ 2304→4096 | Δ 2304→8192 |
|---|---|---|---|---:|---:|
| Gemma 4 E2B, wNa8o8 | 24.2 [23.8–28.3] | 21.4 [20.8–23.6] | 16.1 [16.1–17.9] | **−11.4 %** | **−33.5 %** |

Per round (2304 → 8192): 28.3 → 17.9, 24.0 → 16.1, 23.8 → 16.1, 24.2 → 16.1, 24.9 → 16.1 — −32 to −37 % in each. The cold
iteration reads 32.7 / 25.8 / 17.2 (n=4; round 1 is the first-ever run of the new cache key and is kept apart in
`ladder-first-ever.md`), −21 % / −47 %. Peak RSS (sampled VmHWM) 2,127 → 2,824 → 4,844 MiB.

LiteRT-LM, GPU backend (`litert-lm-gpu`, OpenCL), warm:

| model (file) | ctx 2304 | ctx 4096 | ctx 8192 | Δ 2304→4096 | Δ 2304→8192 |
|---|---|---|---|---:|---:|
| Gemma 4 E2B, wNa8o8 | 26.0 [21.9–29.2] † | 26.0 [16.1–26.1] † | 25.0 [24.2–25.2] ‡ | −0.0 % | −4.1 % |

† outlying rounds (2304: 21.9 in round 5 and 29.2 in round 4, the other three 26.0; 4096: 16.1 in round 4, the other four
25.9–26.1). Spread 28 % / 39 %: under the spread-rule these two cells are owed a re-take; the medians are reported, not
claimed as precise. ‡ 93-token answers. The cold iteration reads 25.8 / 26.0 / 27.6. Prefill (warm) 2,906 → 2,550 → 1,972
tok/s (−12 % / −32 %); TTFT 600 → 680 → 870 ms. Peak RSS 814 → 834 → 841 MiB (host-side; GPU memory is not in VmHWM).

llama.cpp (b8999 `llama-cli -t 4`) — the control arm, `cold-process`:

| model (file) | ctx 2304 | ctx 4096 | ctx 8192 | Δ 2304→4096 | Δ 2304→8192 |
|---|---|---|---|---:|---:|
| Gemma 4 E2B Q4_K_M | 14.2 [12.0–14.3] | 14.3 [13.9–14.7] | 14.4 [14.3–14.4] | +0.7 % | +1.4 % |

(Per-arm ladders on purpose: the public repo carries single-arm facts.)

Re-take (2026-09-24, `results/raw/2026-09-24-dashboard-longctx-v1-s26-android-gpu-retake/`): the GPU ladder measured again in its
own session of 6 paired rounds reads warm 26.1 / 26.8 / 25.5 tok/s (+2.6 % / −2.6 %) with 6 % / 16 % / 3 % spreads — the two
cells owed a re-take above are settled there; the reading (no fall beyond spread) is unchanged.

## Reading

1. **The CPU arm pays for the allocated KV on the S26 as it does on the Mac.** Same bundle, same prompt, same 256 output
   tokens: −11 % at 4,096 and −33 % at 8,192 warm (−21 % / −47 % cold), in every round. The Mac leg read −8 % / −22 % for
   this bundle; catalog row K5 (gemma-3-270m, `--benchmark`) read −43 % on the S26 at 1,280 → 4,096. Resident memory grows
   with the allocation here too (2.1 → 4.8 GiB).
2. **The GPU decode does not show the Mac's fall.** Warm decode is 26.0 / 26.0 / 25.0. The −4 % at 8,192 is inside what this
   session can resolve: two of the three cells have an outlying round, and the 8,192 answers are 93 tokens long, so that
   rate is taken at a shallower average depth. On the Mac the Metal-backed delegate lost 12 % on this bundle. K17's S26
   sweep read the OpenCL GPU flat with an empty cache; this session repeats that reading with a filled ≈1.6K-token prompt.
   GPU **prefill** does track the allocation (−12 % / −32 %), as on the Mac (−18 % at 8,192).
3. **llama.cpp is the control**: flat within ±1.4 %, so the CPU arm's fall is the runtime's, not the phone's state during
   the session.
4. What this sitting does not establish: a precise GPU Δ (re-take owed on two cells; an output of equal length at all three
   allocations would need a prompt whose greedy answer does not change with `maxNumTokens`), anything about the other four
   dashboard models, and which op moves on the CPU path on this bundle (no profile was taken).

## Exclusions and what they are evidence of

- The dashboard's Qwen3-0.6B / Qwen3-4B `mixed_int4` files carry a 2,048-entry KV and are `exclude=` for this task exactly
  as on the Mac (`bundle-kv-2048-entries-2k-prefill-plus-256-overruns`; evidence in the Mac leg's `probe-evidence/`).
- **Qwen3 wi4b32 GPU builds, long prompt, S26 GPU: text is garbage, so their GPU ladders are excluded**
  (`exclude=s26-gpu-garbage-text-at-2k-prefill` in the qwen06 / qwen17 cells). Instrument smoke,
  `results/raw/2026-09-20-dashboard-longctx-v1-s26-android-smoke/`: `Qwen3-0.6B_dynamic_wi4b32_afp32.litertlm`, 1,986-token
  prompt, GPU, allocations 2,304 and 8,192, cold and warm — 256 tokens of `]` / `]].` repeated, 0 alphanumeric characters,
  at a normal-looking 39–43 tok/s and with 0 × `Invalid decode`. GPU diagnostic,
  `results/raw/2026-09-20-dashboard-longctx-v1-s26-android-gpudiag/`: the same file with the 19-token short-chat prompt
  answers in readable English; `Qwen3-1.7B_dynamic_wi4b32_afp32.litertlm` with the long prompt returns 256 newline tokens;
  Gemma 4 E2B with the long prompt answers the task. The CPU backend on the 0.6B file with the same long prompt produces
  coherent on-task text. A rate from a run whose text is garbage is not a measurement; the only signal was the decoded
  text. (Both probe campaigns are n=1 instrument checks: their records live under `probe-records/`, outside the summary
  layer, and are never pooled.)
- RAM: `s26-ram-e4b-cpu-8192-mac-rss-over-60pct` in the E4B cells is inherited from the Mac leg's CPU peak RSS (11.3 GB)
  against the phone's 11.4 GB — a planning exclusion, not an observed Android OOM.

## Harness changes made for this leg (same commit series)

- `long-context-2048-gen256` on Android (`scripts/gen_task_prompts.py` block override, `prompts/text/`, `budgets.tsv`,
  `validate_cells.py`).
- `android/bench/run_cell.py`: prompt tasks with `context-tokens=` use `litert_lm_advanced_main` with two iterations; one
  record per iteration (`regime`, `iterationIndex`), allocation witness, `Invalid decode` count, decoded text + text screen,
  battery °C start / end, capture names keyed on backend + allocation + file. Cells without `context-tokens=` and the
  `native-benchmark-*` tasks build byte-identical commands to before (`android/bench/test_longctx.py`).
- `android/bench/run_campaign.py`: opt-in `ROUNDS=N` round mode (reversal on even rounds, anchor per round, no gate retry),
  `--dry-run` launch plan, per-round wakefulness, session deadline that stops at a launch boundary.
- `android/bench/parsers.py`: per-iteration split of the advanced_main benchmark blocks (never summed).
- `scripts/longctx_ab_report.py`: reads Android records, keeps cold / warm / cold-process / first-ever apart, peak RSS
  column, explicit round selection.
- `THERMAL_GATE.txt`'s single line (`gate timeout after 600s … ran anyway`) is the inherited wording for the wait that the
  session deadline cut short at 14:26:36; launch 60 did not run (`SITTING_STOP.txt`, `launch_order.jsonl`).

## Files

`app-path-android/` — 80 records (16 per round × 5), one log per launch, decoded text per LiteRT iteration,
`launch_order.jsonl`, `round_state.jsonl`, `round_completion.jsonl`, `session_provenance.txt`; `incomplete-round6/` — the
15 records and logs of the cut round; `ladder-warm|cold|cold-process|first-ever.md/.csv` — from
`python3 scripts/longctx_ab_report.py results/raw/2026-09-20-dashboard-longctx-v1-s26-android-gemmae2b --regime <r> --rounds 1,2,3,4,5`;
`temperature_log.md`, `spread.md`, `spread_rounds.md`, `text_check.md`.
