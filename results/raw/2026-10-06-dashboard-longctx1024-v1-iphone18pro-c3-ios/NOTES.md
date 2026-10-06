# 2026-10-06-dashboard-longctx1024-v1-iphone18pro-c3-ios — notes

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
ios mlx-swift mlx-community/Qwen3-4B-4bit long-context-1024-gen256 cooldown=300
ios litert-lm litert-community/Qwen3-4B long-context-1024-gen256 cooldown=300 context-tokens=2048
ios llama.cpp unsloth/Qwen3-4B-GGUF/Q4_K_M long-context-1024-gen256 cooldown=300 context-tokens=2048
```

Hold 13:51:04–14:26:41 JST, CELL_TIMEOUT 1200.

1. LiteRT Qwen3-4B: first capture HOT (34.2c / 22.0 / 19.9 / 20.5; runs 3–4 started
   `fair`) -> quarantined, 240 s, re-run: HOT (34.2c / 24.2 / 21.9 / 20.9; `fair` ->
   `serious`) -> kept with FLAGGED.txt. The decode rate falls from run 1 within the
   cell; the kept warm median is a throttled value. The runner then waited
   SERIOUS_COOLDOWN 600 s on top of the 300 s cell cooldown before llama.cpp.
2. llama.cpp (34.6c / 34.6 / 34.8 / 34.7) and MLX (40.3c / 40.2 / 40.2 / 40.2) Qwen3-4B
   stayed `nominal` in all four runs.
