# 2026-09-20-dashboard-longctx-v1-s26-android-gpudiag

GPU text diagnostic for the S26 long-context leg (2026-09-20, `matrices/dashboard-longctx-v1-android-s26-gpudiag.cells`, four GPU launches at allocation 2304): Qwen3-0.6B wi4b32 short-chat (readable), Gemma 4 E2B short-chat and long prompt (readable, on-task), Qwen3-1.7B wi4b32 long prompt (256 newline tokens).

n=1 instrument checks, never pooled into a session: the records live under `probe-records/` (outside the summary layer) with one log per launch and the decoded text of every LiteRT iteration. Reading and consequences (the `exclude=s26-gpu-garbage-text-at-2k-prefill` rows): `results/raw/2026-09-20-dashboard-longctx-v1-s26-android-gemmae2b/NOTES.md`.
