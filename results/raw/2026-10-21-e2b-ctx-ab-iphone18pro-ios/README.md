# 2026-10-21 — Gemma 4 E2B on the iPhone 18 Pro GPU: LiteRT-LM v0.18.0's `benchmark()` at 1024 / 256 with four KV allocations (1312, 2048, 4096, 8192), one sitting

Status: closed. Two holds of the bench iPhone (iPhone 18 Pro, A20 Pro), 14:01:29–14:35:32 and 14:35:47–15:04:05 JST, no
reboot, no install. Every number below comes from the records in `app-path-native/` (imported from the console's
`YARDSTICK_NATIVE_OK` lines by `scripts/import_native_benchmark.py --schema-v1`) and the console itself. A hand-run
experiment, not a weekly sitting (the campaign name carries no `dashboard`).

## What this answers

How much the KV allocation (`maxNumTokens`) alone moves `benchmark()`'s prefill and decode for Gemma 4 E2B on the
iPhone GPU at the protocol's 1024 / 256. Background: upstream `benchmark()` no longer derives the KV size from
prefill + decode (google-ai-edge/LiteRT-LM eae7821a, 2026-10-19); with `maxNumTokens` unset, E2B (whose
`.litertlm` metadata carries no `max_num_tokens`) gets the engine default 4096
(`runtime/engine/engine_settings.cc`, the `GetMaxNumTokens() == 0` branch); v0.18.0's Swift helper used
prefill + decode + 32 = 1312; this repo's protocol rows and the model card use 2048
(`methodology/agreed-protocol-gemma4.md`).

## Protocol

- Device: iPhone 18 Pro (iPhone19,2; UDID 00008160-000038CA02C00036), iOS 27.2 (24B5099f), wired USB, unlocked; the
  battery at its 80 % charge limit throughout, not charging (battery registry at the start, between the holds and at
  the end: `CurrentCapacity` 80, `ExternalConnected` true, `IsCharging` false; the app stamps `batteryState: charging`).
- App: BenchmarkApp `com.example.CoreMLLLMChat` 0.2.0, Release, the bench pin (main binary sha256 50eaab37…,
  installed 2026-10-21 07:09 and untouched since); records stamp `engineVersion v0.18.0`,
  `engineArtifact CLiteRTLM.xcframework.zip@v0.18.0 sha256:d765b995…`; the vendored `benchmark()` takes
  `maxNumTokens` (`ios/BenchmarkApp/Vendored-patches/0001-benchmark-maxNumTokens.patch`), and `--context-tokens N`
  passes N (`ios/BenchmarkApp/Sources/BenchmarkApp.swift`, `runNativeBenchmark`). Model
  `litert-community/gemma-4-E2B-it-litert-lm` `gemma-4-E2B-it.litertlm` (revision b3ca0d2f), GPU = Metal (every
  launch: `RegisterAccelerator … name=GPU Metal`, `YARDSTICK_METAL_DEVICE name=Apple A20 Pro GPU`).
- Launch = one app process: `--litert-native-benchmark 1024x256 --runs 4 --native-cool-wait 60 --litert-backend gpu
  --context-tokens N`: four `benchmark()` calls, each after a 60 s pause (every pause ended nominal), call 1 = cold,
  calls 2–4 = warm (same process and on-disk caches; `benchmark()` builds a new engine per call). 300 s between
  launches. Order 2048 → 4096 → 2048 (hold 1, `matrices/e2b-ctx-ab-ios.cells` + `matrices/e2b-ctx-ab-ios-repeat.cells`),
  1312 → 8192 → 2048 (hold 2, `matrices/e2b-ctx-ab-ios-more.cells` + the repeat file): every other allocation sits
  between two 2048 launches. Hold 1 starts with the iOS session anchor (`matrices/anchors.cells` line 18) and one E2B
  short-chat run (the importer's `--like` record and a text check).
- Drivers: `scripts/bench_matrix_iphone.sh` under the phone's hold, `device-state/hold1.log`, `device-state/hold2.log`.

## Results

Warm = the median of calls 2–4 of the launch; spread = (max − min) / median of those three. Every call started and
ended `nominal`; every record 1024 prefill / 256 decode tokens.

| launch | `maxNumTokens` | warm prefill tok/s (calls 2–4) | warm decode tok/s (calls 2–4) | spread prefill / decode | cold call prefill / decode | warm phys_footprint peak MB |
|---:|---:|---|---|---|---|---:|
| 1 | 2048 | **6,092.7** (6,112.7, 6,051.9, 6,092.7) | **86.91** (86.91, 86.89, 86.91) | 1.0 % / 0.0 % | 4,990.5 / 80.34 | 385 |
| 2 | 4096 | **5,069.1** (5,041.5, 5,069.6, 5,069.1) | **84.75** (84.75, 84.44, 84.75) | 0.6 % / 0.4 % | 4,798.6 / 84.46 * | 541 |
| 3 | 2048 | **6,048.4** (6,078.3, 6,048.4, 6,031.5) | **86.85** (86.85, 86.88, 86.55) | 0.8 % / 0.4 % | 5,357.1 / 86.79 | 386 |
| 4 | 1312 | **6,470.9** (6,470.9, 6,435.9, 6,477.6) | **87.40** (87.39, 87.44, 87.40) | 0.6 % / 0.1 % | 6,463.9 / 86.46 * | 344 |
| 5 | 8192 | **3,784.1** (3,784.1, 3,773.0, 3,849.1) | **78.78** (78.78, 78.80, 78.68) | 2.0 % / 0.2 % | 3,774.1 / 78.88 * | 832 |
| 6 | 2048 | **6,135.0** (6,135.0, 6,131.8, 6,172.0) | **86.80** (86.89, 86.65, 86.80) | 0.7 % / 0.3 % | 4,981.9 / 80.21 | 385 |

\* The cold call of the 4096, 1312 and 8192 launches built that allocation's GPU programs (no "Initialized
InferenceContext from serialized data" line, load 4.78 / 2.99 / 4.68 s against 0.85–0.90 s for every warm call); the
2048 launches read the cache in every call. Cold calls are not used below.

Against the mean of the three 2048 launches (6,092.0 prefill / 86.85 decode; each launch within 0.8 % of it):

| `maxNumTokens` | prefill | decode |
|---:|---:|---:|
| 1312 | +6.2 % | +0.6 % |
| 4096 | −16.8 % | −2.4 % |
| 8192 | −37.9 % | −9.3 % |

The 18 Pro's 2026-10-17 task-path ladder (`../2026-10-17-catalog-x2-iphone18pro-ios/README.md`, 1,654-token prompt,
256-token answer) moved the same way: warm prefill −15.1 % / −35.1 % and decode −2.3 % / −9.3 % at 4096 / 8192
against 2304.

Session anchor (mlx-swift Qwen3-0.6B-4bit short-chat, runs 3): 222.5 / 221.4 / 221.9 tok/s, all nominal; warm median
221.7 = 0.996 of the phone's newest admitted anchor (`../2026-10-19-dashboard-v1-iphone18pro-q06cand-anchor-ios/SESSION.json`,
222.56). E2B short-chat (GPU, 1 run): 85.2 tok/s decode, 20 prompt / 128 output tokens, an on-topic answer.

## Files

- `console_litert-lm_…_native-benchmark-1024x256.txt` — all six protocol launches (one console per arm, model and
  task; each `YARDSTICK_BEGIN native_benchmark` line names its `context_tokens`), `….launch_times`, `native_launches.tsv`.
- `app-path-native/native_…_{1..24}.json` — the 24 calls, numbered in console order (launch `n` = calls 4n−3..4n);
  `metrics.contextTokensConfigured` carries the allocation.
- `device-jsonl/` — the anchor's 3 records and the E2B short-chat record (the `--like` of every import).
- `device-state/hold{1,2}.log` — the keepers' logs (hold JSON, phone checks, runner output).
