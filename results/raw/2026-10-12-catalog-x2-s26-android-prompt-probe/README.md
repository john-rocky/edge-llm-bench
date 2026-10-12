# 2026-10-12 — prompt probe for task long-context-2048-gen256-noref (catalog X2, Galaxy S26 RFGL80R6A6H)

n = 1 instrument check, never pooled: the records live in `probe-records/`, outside the summary layer
(`build_summary.py` reads `app-path*/` only). Purpose: before any ladder record exists, show that the new tail
(`scripts/gen_task_prompts.py` `NOREF_TAIL`, tail A of the lane design) makes both Gemma 4 bundles answer the full
256-token budget on the S26 GPU at the allocations where the old tail stopped short (E4B refused in 50–61 tokens at
every allocation, E2B stopped at 93 at 8192; `../2026-09-24-dashboard-longctx-v1-s26-android-gpu-retake/text_check.md`).

PASS bar: both iterations of each launch generate 254–256 tokens, the decoded text is coherent and on task (read in
full), the log has 0 × `Invalid decode`.

| launch (hold 1, screen off) | allocation | prompt tok | output tok cold / warm | Invalid decode | decode tok/s cold / warm | verdict |
|---|---:|---:|---|---:|---|---|
| E4B gpu, 06:13–06:16 JST (bundle pushed first, 100.6 s) | 2304 | 1654 | 256 / 256 | 0 | 15.12 / 15.26 | PASS |
| E4B gpu, 06:16–06:17 | 8192 | 1654 | 256 / 256 | 0 | 15.41 / 14.80 | PASS |
| E2B gpu, 06:18–06:19 (bundle pushed first, 71.9 s) | 8192 | 1654 | 256 / 256 | 0 | 26.65 / 25.04 | PASS |

The texts are numbered lists of on-device capabilities with two sentences per item; E4B's 2304 and 8192 answers part
after item 1 (engine-default sampling), E2B's two iterations are identical. All three launches were the bundle's
first run on this phone (`firstEver`, cache build) and carry `cpu-capped`: the CPU clock ceilings fell step by step
during each launch (E4B to 2227.2 / 2227.2 MHz of 3628.8 / 4742.4; E2B to 3187.2 / 3129.6) at thermal status 0.
Rates here are not measurements of anything; the ladders are in `../2026-10-12-catalog-x2-s26-android-e2b-gpu/` and
`…-e4b-gpu/`. Command (LiteRT-LM v0.16.0 `litert_lm_advanced_main`, witness = pin):

```bash
CAMPAIGN=2026-10-12-catalog-x2-s26-android-prompt-probe ROUNDS=1 COOLDOWN=30 THERMAL_WAIT=600 BENCH_CPU_MASK= \
  BENCH_ANDROID_SERIAL=RFGL80R6A6H nice -n 19 python3 android/bench/run_campaign.py matrices/catalog-x2-s26-prompt-probe.cells
# then the same with matrices/catalog-x2-s26-prompt-probe-e2b.cells; app-path-android/ moved to probe-records/<model>-tailA/ after each
```

Files: `probe-records/e4b-tailA/` (4 records, 2 logs, decoded text per iteration, launch_order.jsonl, THERMAL_GATE.txt),
`probe-records/e2b-tailA/` (2 records, 1 log, …).
