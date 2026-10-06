# 2026-10-07-dashboard-protocol1024-v1-iphone18pro-ios — notes

Protocol rows = LiteRT-LM's own `benchmark()` entry point: prefill forced to exactly 1024 tokens with no prompt,
decode 256, context 2048 (`methodology/agreed-protocol-gemma4.md`), task `native-benchmark-1024x256`, rows 20-24 of
`matrices/dashboard-protocol1024-v1.cells` (`ios litert-lm <model> native-benchmark-1024x256 [cooldown=300]
context-tokens=2048`), on the **iPhone 18 Pro** (`iPhone19,2`, iOS 27.2 beta, build 24B5099f, on USB).

App: `com.example.CoreMLLLMChat` 0.2.0 (1) as installed on 2026-10-07 02:48:08 JST (container
`57E85F96-000D-446E-9AF0-EE872D16D536`, the same at the start of this sitting = not reinstalled since): the
BenchmarkApp Release build of commit 3be68d7, whose bundled `engine-pins.json` pins LiteRT-LM v0.16.0
(`CLiteRTLM.xcframework.zip@v0.16.0 sha256:4e0f683d…`, the same artifact as `environment.lock.json`). The
LiteRT-LM records the same app wrote in the 1K task-prompt sitting right after this one
(`2026-10-07-dashboard-longctx1024-v1-iphone18pro-c{1..4}-ios`) stamp that engine. Harness `2026-07-30-agreed-protocol-r4`.

The iPhone runner has no native entry point (`scripts/bench_matrix_iphone.sh` passes the task id as `--task`), so the
launches were driven directly, one launch per call:

    xcrun devicectl device process launch --console --terminate-existing --device 00008160-000038CA02C00036 \
      com.example.CoreMLLLMChat -- --yardstick-autorun --runtime litert-lm --model-id <id> \
      --litert-native-benchmark 1024x256 --context-tokens 2048

No `--runs` = one `benchmark()` call per process (the app prints `run=1 runs=1 cold=1`): every launch is a cold
measurement (fresh process, engine built by the call, on-disk caches present). Four launches per model, in cells-file
order; between launches the row's cooldown (300 s for Gemma 4 E2B / Qwen3-4B / Gemma 4 E4B, the runner default 100 s
for Qwen3-0.6B / Qwen3-1.7B). The phone was held (`~/code/coreai/ondevice/.device_hold`) per model group:
Qwen3-0.6B + Qwen3-1.7B 05:12:11-05:24:54, Gemma 4 E2B 05:29:54-05:45:23, Qwen3-4B 05:50:23-06:06:41,
Gemma 4 E4B 06:11:41-06:27:40 JST, at least 300 s without the hold between groups.

Thermal: the line's `thermal_initial` (ProcessInfo.thermalState before the call) decided each launch: a launch not
starting `nominal` would have been set aside and taken once more after 240 s (the runner's gate rule). All 20 launches
started and ended `nominal`; nothing was set aside. Every console line carries prefill_tokens=1024 decode_tokens=256
context_tokens=2048; no `YARDSTICK_FATAL`, no `YARDSTICK_WARN`, no `Invalid decode` line.

Text: benchmark mode decodes no text. The same bundles on the same GPU backend, app, phone and OS decoded the 1K task
prompt in the sitting that followed (`outputSample` of the LiteRT-LM records in
`2026-10-07-dashboard-longctx1024-v1-iphone18pro-c{1..4}-ios`).

Files: `console_litert-lm_litert-community_<model>_native-benchmark-1024x256_ctx2048.txt` = the four launches' console
output in launch order (the stored report); `launches.tsv` = one row per launch (UTC start / end, the line's fields,
the GPU cache files written); `cache_evidence.txt` = the model's `tmp/*_mldrift_{weight,program}_cache.bin` files
(size, modification time) listed with `devicectl device info files` before launch 1 and after every launch;
`app-path-native/` = the schema-v1 records (below); `session_provenance.txt`.

First-ever (fairness-rules §2: the first launch after an install, which builds compilation / weight caches; never the
engine's speed), rule fixed in the round log before the Gemma 4 E2B, Qwen3-4B and Gemma 4 E4B launches were seen:
(i) a launch during which the model's `tmp/*_mldrift_*_cache.bin` was written, or (ii) launch 1 of a model run for the
first time on this app install (the install's LiteRT-LM launches before this sitting, 02:48-03:43 JST by another lane's
round 9 driver, ran only Gemma 4 E2B and Gemma 4 E4B) whose wall time (`wall_s`, the call including engine init) is more than 5 % above the longest of launches
2-4. Marked: Qwen3-0.6B launch 1 (ii: no cache file written, wall 3.649 s against 3.140-3.161 s, init 2.24 s against
1.57-1.61 s, decode 128.98 against 141.29-141.39 tok/s), Qwen3-1.7B launch 1 (i: weight cache rewritten,
init 10.14 s) and Qwen3-4B launch 1 (i: weight cache rewritten, init 18.42 s). Not marked: launch 1 of Gemma 4 E2B and
Gemma 4 E4B also ran with a longer engine init (2.72 / 4.83 s against 1.56-1.59 / 2.11-2.49 s) and so a longer
wall time, with no cache file written and the same decode rate as launches 2-4; they stay cold launches.
The two weight caches rewritten here (Qwen3-1.7B, last written 2026-10-06T03:55:12Z; Qwen3-4B, 04:59:52Z) are the two
written while the phone ran iOS 27.0 (its last 27.0 record: 06:04:01Z; its first 27.2 record: 07:41:54Z); the
Qwen3-0.6B, Gemma 4 E2B and Gemma 4 E4B weight caches, written on 27.2 (12:49:50Z, 13:02:07Z, 15:02:53Z), were kept.
No program cache was written in this sitting. Why the two were rebuilt is not established.

Import (scripts/import_native_benchmark.py at main 1df9480, `--schema-v1`, one call per model, run from the repo root):

    python3 scripts/import_native_benchmark.py --schema-v1 \
      results/raw/2026-10-07-dashboard-protocol1024-v1-iphone18pro-ios/console_litert-lm_litert-community_<model>_native-benchmark-1024x256_ctx2048.txt \
      --out results/raw/2026-10-07-dashboard-protocol1024-v1-iphone18pro-ios/app-path-native \
      --like <a LiteRT-LM long-context-1024-gen256 record of the same model from 2026-10-07-dashboard-longctx1024-v1-iphone18pro-c<n>-ios> \
      --launch-times <the four launch starts, UTC> --instrument "litert-lm native benchmark() via BenchmarkApp --litert-native-benchmark" \
      --device iPhone19,2 [--first-ever 1]

`--like` is a record the same app wrote on the same phone and OS a few minutes later, so `device.systemVersion` (27.2),
`engineVersion` / `engineArtifact` and `model` come from this sitting's own app (a 2026-10-06 record would carry
systemVersion 27.0). Each record: `timestamp` = the launch's start, `metrics` = the line's rates, TTFT, init seconds,
memory, token counts, context, `wallSeconds`, `coldRun: true`, `initialThermalState` / `finalThermalState`
(`nominal`), `firstEver: true` on the three launches above; `conditions` = instrument, launchIndex, run 1 / runs 1.

LiteRT-LM native launches (from `launches.tsv`; the same numbers are in the console lines and the records):

| model | launch | start (UTC) | decode tok/s | prefill tok/s | TTFT ms | init s | wall s | peak MB | thermal start → end | GPU cache written in the launch | firstEver |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Qwen3-0.6B | 1 | 2026-10-06T20:12:13Z | 128.98 | 1762.75 | 588.7 | 2.24 | 3.649 | 640 | nominal → nominal | — | yes |
| Qwen3-0.6B | 2 | 2026-10-06T20:13:58Z | 141.29 | 1766.60 | 586.7 | 1.57 | 3.146 | 640 | nominal → nominal | — |  |
| Qwen3-0.6B | 3 | 2026-10-06T20:15:43Z | 141.37 | 1768.50 | 586.1 | 1.57 | 3.140 | 640 | nominal → nominal | — |  |
| Qwen3-0.6B | 4 | 2026-10-06T20:17:28Z | 141.39 | 1766.67 | 586.7 | 1.61 | 3.161 | 640 | nominal → nominal | — |  |
| Qwen3-1.7B | 1 | 2026-10-06T20:19:13Z | 66.75 | 693.13 | 1492.3 | 10.14 | 10.588 | 1051 | nominal → nominal | weight_cache.bin | yes |
| Qwen3-1.7B | 2 | 2026-10-06T20:21:06Z | 70.49 | 698.37 | 1480.5 | 3.26 | 6.924 | 1146 | nominal → nominal | — |  |
| Qwen3-1.7B | 3 | 2026-10-06T20:22:54Z | 70.51 | 697.73 | 1481.8 | 3.19 | 6.923 | 1146 | nominal → nominal | — |  |
| Qwen3-1.7B | 4 | 2026-10-06T20:24:43Z | 70.55 | 697.62 | 1482.0 | 3.20 | 6.888 | 1146 | nominal → nominal | — |  |
| Gemma 4 E2B | 1 | 2026-10-06T20:29:55Z | 79.88 | 1636.74 | 638.2 | 2.72 | 5.499 | 794 | nominal → nominal | — |  |
| Gemma 4 E2B | 2 | 2026-10-06T20:35:01Z | 79.93 | 1673.39 | 624.4 | 1.59 | 4.886 | 801 | nominal → nominal | — |  |
| Gemma 4 E2B | 3 | 2026-10-06T20:40:08Z | 79.67 | 1670.91 | 625.4 | 1.56 | 4.902 | 801 | nominal → nominal | — |  |
| Gemma 4 E2B | 4 | 2026-10-06T20:45:15Z | 79.87 | 1672.93 | 624.6 | 1.57 | 4.837 | 803 | nominal → nominal | — |  |
| Qwen3-4B | 1 | 2026-10-06T20:50:24Z | 34.17 | 245.44 | 4201.4 | 18.42 | 21.085 | 2099 | nominal → nominal | weight_cache.bin | yes |
| Qwen3-4B | 2 | 2026-10-06T20:55:46Z | 34.45 | 245.94 | 4192.7 | 6.35 | 14.982 | 1349 | nominal → nominal | — |  |
| Qwen3-4B | 3 | 2026-10-06T21:01:03Z | 34.44 | 246.10 | 4189.9 | 6.47 | 15.039 | 1335 | nominal → nominal | — |  |
| Qwen3-4B | 4 | 2026-10-06T21:06:20Z | 34.44 | 245.06 | 4207.5 | 6.36 | 15.012 | 1369 | nominal → nominal | — |  |
| Gemma 4 E4B | 1 | 2026-10-06T21:11:42Z | 34.30 | 444.13 | 2334.8 | 4.83 | 12.449 | 972 | nominal → nominal | — |  |
| Gemma 4 E4B | 2 | 2026-10-06T21:16:56Z | 34.25 | 447.27 | 2318.6 | 2.13 | 11.088 | 987 | nominal → nominal | — |  |
| Gemma 4 E4B | 3 | 2026-10-06T21:22:09Z | 34.26 | 447.50 | 2317.4 | 2.11 | 11.137 | 986 | nominal → nominal | — |  |
| Gemma 4 E4B | 4 | 2026-10-06T21:27:23Z | 34.24 | 447.69 | 2316.5 | 2.49 | 11.255 | 986 | nominal → nominal | — |  |

Per model, through `render_leaderboard.arm_row` (the one aggregation; firstEver launches out of every pool) on a summary
built from the git index plus this round's five campaign dirs (`git checkout-index -a` into a temp tree,
`scripts/build_summary.py`, 3,296 rows): every record is `coldRun: true`, so the cold median is the row's decode figure.
`render_dashboard.py --cells matrices/dashboard-protocol1024-v1.cells` shows these five cells as `no-decode` (the
iPhone headline regime is warm and there are no warm records); its prefill / TTFT / memory columns equal the ones below.

| model | cold median decode tok/s | cold spread % | n | firstEver (left out) | prefill median tok/s | TTFT median ms | memory median MB | peak median MB | thermal at start |
|---|---|---|---|---|---|---|---|---|---|
| Qwen3-0.6B | 141.37 | 0.1 | 3 | 1 | 1,767 | 587 | 569 | 640 | nominal |
| Qwen3-1.7B | 70.51 | 0.1 | 3 | 1 | 698 | 1,482 | 868 | 1,146 | nominal |
| Gemma 4 E2B | 79.88 | 0.3 | 4 | 0 | 1,672 | 625 | 780 | 801 | nominal |
| Qwen3-4B | 34.44 | 0.0 | 3 | 1 | 246 | 4,193 | 1,136 | 1,349 | nominal |
| Gemma 4 E4B | 34.25 | 0.2 | 4 | 0 | 447 | 2,318 | 923 | 986 | nominal |
