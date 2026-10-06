# 2026-10-06-dashboard-longctx1024-v1-iphone18pro-c2-ios — notes

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
ios litert-lm litert-community/gemma-4-E2B-it-litert-lm long-context-1024-gen256 cooldown=300 context-tokens=2048
ios mlx-swift mlx-community/gemma-4-e2b-it-qat-OptiQ-4bit long-context-1024-gen256 cooldown=300
ios llama.cpp unsloth/gemma-4-E2B-it-GGUF/Q4_K_M long-context-1024-gen256 cooldown=300 context-tokens=2048
```

Hold 13:21:04–13:46:02 JST, CELL_TIMEOUT 1200 (from this campaign on: a launch
stalled for 20 min is ended; finished runs are on the phone either way).

1. LiteRT Gemma 4 E2B: first capture HOT (74.6c / 78.2 / 77.0 / 40.0, run 4 started
   `fair`) -> quarantined, 240 s, re-run: HOT again (78.3c / 78.1 / 77.9 / 42.7, run 4
   started `fair`) -> the re-run is kept and FLAGGED.txt says so.
2. MLX Gemma 4 E2B: the model was downloaded on the phone at this launch (first use);
   the four runs are steady (48.9c / 51.9 / 51.9 / 51.9).
