# 2026-09-20-dashboard-longctx-v1-s26-android-smoke

Instrument smoke for the S26 long-context leg (2026-09-20, `matrices/dashboard-longctx-v1-android-s26-smoke.cells`, one round, seven launches): anchor, Qwen3-0.6B `dynamic_wi4b32` on LiteRT-LM cpu / gpu at allocations 2304 and 8192, llama.cpp at 2304 and 8192. It proved the `litert_lm_advanced_main` prompt path (allocation witness, 1,986 prompt tokens, two iterations per launch) and found the GPU text failure: all four GPU records decode to `]` / `]].` repeated.

n=1 instrument checks, never pooled into a session: the records live under `probe-records/` (outside the summary layer) with one log per launch and the decoded text of every LiteRT iteration. Reading and consequences (the `exclude=s26-gpu-garbage-text-at-2k-prefill` rows): `results/raw/2026-09-20-dashboard-longctx-v1-s26-android-gemmae2b/NOTES.md`.
