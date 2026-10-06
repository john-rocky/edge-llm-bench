# 2026-10-06-dashboard-longctx1024-v1-iphone18pro-c1-ios — notes

Hand-run sitting of the 1024 / 256 set (task `long-context-1024-gen256`, cells
`matrices/dashboard-longctx1024-v1.cells`, ios section) on the **iPhone 18 Pro**
(iPhone19,2, iOS 27.0 24A437, devicectl `C7A74909-7573-5A0F-9201-F7D03DC811EF`,
UDID `00008160-000038CA02C00036`, USB, charging), app `com.example.CoreMLLLMChat`
"iOS LLM Bench" 0.2.0 (BenchmarkApp). Engines stamped in the records: LiteRT-LM
v0.16.0 (`CLiteRTLM.xcframework.zip@v0.16.0`), llama.cpp b8999, mlx-swift 60bd0d78.
Not a dashboard-job sitting: no SESSION.json, no admission (first records of this
set on this phone). The ios rows were split by model into four campaigns so that
each device hold stayed under 45 minutes (`-c1` anchors + Qwen3-0.6B + Qwen3-1.7B,
`-c2` Gemma 4 E2B, `-c3` Qwen3-4B, `-c4` Gemma 4 E4B); anchors ran in `-c1` only.
The runner skips the cooldown before a campaign's first cell, so each campaign
started at least 300 s (the first cell's cooldown) after the previous one ended.
Command: `BENCH_UDID=00008160-000038CA02C00036 APP=com.example.CoreMLLLMChat
./bench matrix <chunk cells> --platform iphone --campaign
2026-10-06-dashboard-longctx1024-v1-iphone18pro-<cN>` (RUNS 4, BASE_COOLDOWN 100,
THERMAL_COOLDOWN 240, SERIOUS_COOLDOWN 600 defaults).

Cells of this campaign (verbatim rows of the cells file):

```
ios mlx-swift mlx-community/Qwen3-0.6B-4bit short-chat anchor=1 runs=3
ios litert-lm litert-community/Qwen3-0.6B short-chat anchor=1 runs=3
ios mlx-swift mlx-community/Qwen3-0.6B-4bit long-context-1024-gen256
ios litert-lm litert-community/Qwen3-0.6B long-context-1024-gen256 context-tokens=2048
ios llama.cpp unsloth/Qwen3-0.6B-GGUF/Q4_K_M long-context-1024-gen256 context-tokens=2048
ios mlx-swift mlx-community/Qwen3-1.7B-4bit long-context-1024-gen256
ios litert-lm litert-community/Qwen3-1.7B long-context-1024-gen256 context-tokens=2048
ios llama.cpp unsloth/Qwen3-1.7B-GGUF/Q4_K_M long-context-1024-gen256 context-tokens=2048
```

Hold 12:40:18–13:16:04 JST, runner 12:42:07–13:15:51, CELL_TIMEOUT 3600.

1. MLX Qwen3-0.6B short-chat anchor: the console shows three YARDSTICK_RUN_OK runs
   (230.06 / 224.62 / 223.60 tok/s) but two records reached the phone's
   Documents/results: the app names a record by its UTC second
   (`…_2026-10-06T03-42-22Z.json`) and two 128-token runs finished inside one
   second, so run 2 overwrote run 1 (cold). Gate verdict SHORT 2 (not retried).
2. LiteRT Qwen3-1.7B: first capture SPREAD 37.0 (68.8c / 68.8 / 68.7 / 43.4, run 4
   ended `fair`) -> quarantined in device-jsonl-flagged/, 240 s, re-run. The re-run
   wrote runs 1–3 (68.6c / 68.5 / 68.5; run 3 ended `fair`) and then printed nothing
   from 13:01 to 13:13 while the app process stayed alive and no run-4 file appeared
   on the phone; the launch was ended by hand at 13:13 (SIGTERM to the runner's
   gtimeout; "App terminated due to signal 15"). The cell keeps the re-run's three
   records (gate SHORT 3, no GATE_FAIL line).
