# 2026-10-06-dashboard-v1-m4max-protocol1024-mac — notes

Protocol rows = LiteRT-LM's own `benchmark()` entry point: prefill forced to exactly 1024 tokens
with no prompt, decode 256, context 2048 (`methodology/agreed-protocol-gemma4.md`), task
`native-benchmark-1024x256`, on the **Mac Studio M4 Max** (`Mac16,9`, macOS 27.0 26A428).
yardstick flavor=full, harness `2026-07-30-agreed-protocol-r4`, vendored LiteRT-LM v0.16.0
(`CLiteRTLM_mac.xcframework.zip@v0.16.0 sha256:3ae6c876…`), GPU backend (the yardstick default),
`--litert-native-benchmark 1024x256 --context-tokens 2048`.

One sitting inside one quiet window (`~/code/coreai/_GPU_LOCK` through `quiet_hold.py`):

1. the dashboard job, `./bench dashboard-job m4max --once --cells
   matrices/dashboard-protocol1024-v1.cells --suffix protocol1024`: anchor phase
   `2026-10-06-dashboard-v1-m4max-protocol1024-anchor-mac` admitted, then this payload campaign
   (`SESSION.json`) = the two session anchors (short-chat, runs=3) and the five native rows, one
   launch each;
2. 300 s later, `ROUNDS=3 ./bench matrix <the five native rows of the cells file> --platform mac
   --campaign 2026-10-06-dashboard-v1-m4max-protocol1024` (round mode: order reversed on round 2,
   gate off) = three more launches per native row into the same capture files.

Each native row therefore holds **4 launches**, each one process with its own engine init. The
native path ignores `--runs` and writes no schema-v1 record: `<cell>.jsonl` holds one
`YARDSTICK_NATIVE_OK` line per launch (the stored report; `build_summary.py` skips non-JSON
lines, and `cell_gate.py` reads such a file as `SHORT 0`, which the Mac runner never retries).
`app-path-native/` holds the same lines as schema-v1 records, written by
`scripts/import_native_benchmark.py --schema-v1`: `timestamp` = the launch's start from the
runner's `CELL` line; `device`, `engineVersion` / `engineArtifact` and `model` copied from the same
model's LiteRT-LM record of `2026-10-06-dashboard-v1-m4max-longctx1024-mac` (same yardstick binary
and catalog; `initialThermalState` dropped — the native path does not read it); `metrics` = only
what the line carries (prefill / decode tok/s, TTFT, init seconds, token counts, context) plus
`coldRun: true`; `conditions.launchIndex` = the line's position in `<cell>.jsonl`.
`SESSION.json`'s `cells_with_records` (anchors only) was written before the import.
render_dashboard reads the Mac regime as warm, so these cold-only cells render as no-decode there.

Times (JST): quiet window 20:41:26–21:52:14; anchor phase 20:41:27–20:42:04 (admitted, ratio 0.995 against
the 2026-10-05 reference); payload 20:42:05–20:58:59 (`SESSION.json`: admitted, ratio 0.988, the five
native rows one launch each); the three extra rounds 21:04:00–21:52:14 (`session_provenance.txt`,
`host_load.log`). The anchors ran only in the job phases.

First-ever: the GPU program cache of Qwen3-1.7B, Gemma 4 E2B and Gemma 4 E4B
(`$TMPDIR/<file>_<mtime>_<size>_mldrift_program_cache.bin`, the native path's `cacheDir`) was written
during launch 1 of each (file mtime 20:43:44 / 20:48:47 / 20:58:55 = inside that launch) and not by
any of the 15 later launches, and launch 1's engine init was the longest of the four — so those three
records carry `metrics.firstEver: true` (fairness-rules §2: the cache build is never the engine's
speed). The Qwen3-0.6B and Qwen3-4B caches were not written in this sitting (mtimes 2026-10-05 02:03
and 2026-10-06 13:08); their launch 1 stays a cold launch.
Prefill across launches falls into two levels for Qwen3-0.6B, Qwen3-1.7B and Gemma 4 E2B with no
cache write in between (round 2, which ran the models largest first): the per-launch values below
show it. Cause not established.

LiteRT-LM native launches (records in `app-path-native/`; decode / prefill in tok/s):

| model | launch | start (UTC) | decode tok/s | prefill tok/s | TTFT ms | init s | firstEver |
|---|---|---|---|---|---|---|---|
| Qwen3-0.6B | 1 | 2026-10-06T11:43:11Z | 264.20 | 6686 | 156.9 | 0.56 |  |
| Qwen3-0.6B | 2 | 2026-10-06T12:04:00Z | 295.06 | 6707 | 156.1 | 0.57 |  |
| Qwen3-0.6B | 3 | 2026-10-06T12:35:57Z | 293.52 | 4144 | 250.5 | 0.53 |  |
| Qwen3-0.6B | 4 | 2026-10-06T12:36:29Z | 299.40 | 6862 | 152.6 | 0.57 |  |
| Qwen3-1.7B | 1 | 2026-10-06T11:43:43Z | 212.29 | 2776 | 373.6 | 1.67 | yes |
| Qwen3-1.7B | 2 | 2026-10-06T12:04:32Z | 211.14 | 3862 | 269.9 | 1.11 |  |
| Qwen3-1.7B | 3 | 2026-10-06T12:35:25Z | 214.18 | 2769 | 374.5 | 1.07 |  |
| Qwen3-1.7B | 4 | 2026-10-06T12:37:01Z | 213.75 | 3911 | 266.5 | 1.07 |  |
| Qwen3-4B | 1 | 2026-10-06T11:53:49Z | 109.58 | 786 | 1311.8 | 2.73 |  |
| Qwen3-4B | 2 | 2026-10-06T12:14:36Z | 110.51 | 1358 | 762.9 | 2.01 |  |
| Qwen3-4B | 3 | 2026-10-06T12:29:48Z | 112.75 | 1375 | 753.7 | 2.05 |  |
| Qwen3-4B | 4 | 2026-10-06T12:47:06Z | 111.45 | 1358 | 762.9 | 2.07 |  |
| gemma-4-E2B-it-litert-lm | 1 | 2026-10-06T11:48:46Z | 144.82 | 6113 | 174.4 | 1.50 | yes |
| gemma-4-E2B-it-litert-lm | 2 | 2026-10-06T12:09:34Z | 159.53 | 8023 | 133.9 | 0.54 |  |
| gemma-4-E2B-it-litert-lm | 3 | 2026-10-06T12:34:52Z | 146.75 | 6045 | 176.2 | 0.93 |  |
| gemma-4-E2B-it-litert-lm | 4 | 2026-10-06T12:42:03Z | 160.09 | 8023 | 133.9 | 0.54 |  |
| gemma-4-E4B-it-litert-lm | 1 | 2026-10-06T11:58:54Z | 87.75 | 2096 | 500.0 | 2.12 | yes |
| gemma-4-E4B-it-litert-lm | 2 | 2026-10-06T12:19:41Z | 100.33 | 2581 | 406.7 | 0.74 |  |
| gemma-4-E4B-it-litert-lm | 3 | 2026-10-06T12:24:44Z | 100.57 | 2590 | 405.3 | 0.75 |  |
| gemma-4-E4B-it-litert-lm | 4 | 2026-10-06T12:52:10Z | 99.53 | 2566 | 409.1 | 0.77 |  |
