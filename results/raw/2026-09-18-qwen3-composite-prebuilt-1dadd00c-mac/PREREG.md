# Pre-registration — 2026-09-18 Qwen3 re-run on the LiteRT-LM main 1dadd00c prebuilt (written 08:2x JST, before any leg ran)

Claim under test (Fengwu, 07:54 JST): with the new prebuilt and an export carrying `--use_sdpa_composite_for_prefill=True`, "we shall have new prefill performance".

Arms (all on the same v0.17.0-tag `litert_lm_advanced_main`, GPU-serial, one process at a time, `--disable_cache=true`, 3 iterations, 2 processes per cell):
- A = 12-flag export (11-flag command + the prefill flag, litert-torch main 731ef0a) on the 1dadd00c dylib — the arm.
- C = the published 09-11 11-flag file on the 1dadd00c dylib — same dylib, no prefill composite (decode composite only).
- D = the published 11-flag file on the 09-17 dylib (4453b286) — the same-session control for the dylib swap.
- E = the published 9-flag file on both dylibs — the no-composite graph, regression check of the new dylib.
- F = the 12-flag export on the 09-17 dylib — text run, and one 31,744 process if the text run is clean.

Gates that must pass before a number is quoted:
1. Op inventory (exit 6 otherwise): the 12-flag files carry 28 (0.6B) / 36 (4B) `odml.sdpa_transposed` in `prefill_1024` where the published files carry 0; decode 28/36 in both; every other row identical.
2. The first leg (published 11-flag 0.6B, new dylib, text run) exits 0 with 0 `Shape mismatch` (exit 3 otherwise); every leg is counted pass/fail on the same two conditions and the counts are printed at the end.
3. Text runs of the 12-flag files answer the passage (railway / 1879); 8Q on Metal for the 12-flag files is not below their 11-flag counterparts on the same dylib. A lower score is reported in the body as a correctness regression tied to the flag, whatever the speed says.
4. Two processes per cell in every quoted cell (checked in the summary before the table is written); a cell with EXIT_CODE=124 prints "timed out" and is left out of the reply with one clause.

Decision rule for "the fused prefill lands here": the prefill tok/s at 31,744 of A exceeds C on the same dylib with non-overlapping per-process medians (both A processes above both C processes), and D reads the same as the 09-17 record within the 09-17 spread (≤ 4 %); the % is quoted from pooled medians with the per-process values beside it. Otherwise the body says "no gain outside the run-to-run spread" with the same numbers. The 1,024 config is reported the same way. Decode is reported, not claimed.

Not a claim: what the kernel does internally; any comparison with Fengwu's M4 Pro numbers; the 09-11 "447".
