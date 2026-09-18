Pre-session probes, 2026-09-18 05:01-05:12 (yardstick built 05:00 from this tree, v0.16.0 pin), one launch each,
`--runs 2`. `.jsonl.probe` = the records (suffix keeps them out of build_summary's `*.jsonl` glob — probes are
not session rows); `.log` = full yardstick stderr. What each one established:

| tag | cell | result |
|---|---|---|
| p1 | Qwen3-0.6B wi4b32, litert cpu, ctx 4096 | runs; `runtime: litert-lm-cpu` stamped; prompt 1,986 tokens; decode 34 tok/s (log not kept — first probe ran without one) |
| p2 | same file, litert gpu, ctx 4096 | runs; decode 284 |
| p3 | Gemma 4 E2B, litert gpu, ctx 8192 | runs; prompt 1,637 tokens; the model answers in 93 tokens and stops (EOS) — the forced-output tail does not hold Gemma 4 to 256 |
| p4 | Qwen3-0.6B Q4_K_M, llama.cpp, ctx 2304 | both records written, then the known Metal teardown abort (`GGML_ASSERT([rsets->data count] == 0)`, rc 134) — records valid |
| p5 | Qwen3-0.6B mixed_int4 (the dashboard file), litert gpu, ctx 2304 | runs, 0 engine warnings, 270 tok/s; prompt 1,987 + 256 output = 2,243 > the bundle's 2,048 KV entries (p9) — whether the last 195 steps read a valid KV is not established |
| p6 | Qwen3-1.7B dynamic INT8, litert cpu, ctx 2304 | runs (new catalog id `litert-community/Qwen3-1.7B/int8`); decode 28 |
| p7 | Qwen3-0.6B mixed_int4, litert gpu, ctx 8192 | runs to a normal-looking 270 tok/s while the engine logs 10,666 × "Invalid decode and sample result. The sampled token is casted to 0 to avoid crash." — a rate that is not a measurement |
| p8 / p8b | Qwen3-0.6B mixed_int4, litert cpu, ctx 8192 / 2304 | run, 0 warnings, 35.2 / 35.1 tok/s — the CPU decode does not move with context-tokens on this file (its KV is fixed at export) |
| p9 | Qwen3-0.6B mixed_int4, litert gpu, the ~2.7K-token `long-context` task, ctx 4096 | fails: `FAILED_PRECONDITION: Prefill input length exceeds available state entries (remaining capacity: 2048)` — the bundle's KV is 2,048 entries whatever `maxNumTokens` says |
| p10 | Gemma 4 E4B, litert cpu, ctx 2304 | runs; prompt 1,637; prefill 225 tok/s, decode 33 |

Consequence for the cells file: the mixed_int4 Qwen3 0.6B / 4B rows are `exclude=` (reason slug in the row); the
0.6B ladder runs the wi4b32 file; 4B LiteRT has no runnable published file for this task.
