# 2026-10-07-dashboard-longctx1024-v1-iphone18pro-c1-ios — notes

Hand-run sitting of the 1024 / 256 task-prompt set (task `long-context-1024-gen256`, cells
`matrices/dashboard-longctx1024-v1.cells`, ios section), the second on the **iPhone 18 Pro** and the first on
iOS 27.2 (iPhone19,2, iOS 27.2 beta build 24B5099f, devicectl `C7A74909-7573-5A0F-9201-F7D03DC811EF`,
UDID `00008160-000038CA02C00036`, USB, charging). App `com.example.CoreMLLLMChat` "iOS LLM Bench" 0.2.0 (1),
the BenchmarkApp Release build installed 2026-10-07 02:48 JST (commit 3be68d7; not reinstalled since). Engines
stamped in the records: LiteRT-LM v0.16.0 (`CLiteRTLM.xcframework.zip@v0.16.0 sha256:4e0f683d…`), llama.cpp b8999,
mlx-swift 60bd0d78. Not a dashboard-job sitting: no SESSION.json, no admission. The ios rows were split by model
into four campaigns, as in the 2026-10-06 sitting, so that each device hold stayed under 45 minutes (`-c1` anchors
+ Qwen3-0.6B + Qwen3-1.7B, `-c2` Gemma 4 E2B, `-c3` Qwen3-4B, `-c4` Gemma 4 E4B); anchors ran in `-c1` only. The
runner skips the cooldown before a campaign's first cell, so each campaign started at least 300 s after the
previous hold on the phone ended (this one: the hold of the protocol-row launches of
`2026-10-07-dashboard-protocol1024-v1-iphone18pro-ios` was returned at 06:27:40 JST, its last launch ended 06:27:36).
Command: `BENCH_UDID=00008160-000038CA02C00036 APP=com.example.CoreMLLLMChat CELL_TIMEOUT=1200 ./bench matrix
<chunk cells> --platform iphone --campaign 2026-10-07-dashboard-longctx1024-v1-iphone18pro-<cN>` (RUNS 4,
BASE_COOLDOWN 100, THERMAL_COOLDOWN 240, SERIOUS_COOLDOWN 600 defaults).

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

Hold 06:32:40–06:52:30 JST, runner 06:32:41–06:52:28, CELL_TIMEOUT 1200.

1. MLX Qwen3-0.6B short-chat anchor: three YARDSTICK_RUN_OK runs in the console, two records on the phone — the
   app names a record by its UTC second and two 128-token runs finished inside one second (the same as on
   2026-10-06). Gate verdict SHORT 2 (not retried); the cell has no cold run.
2. LiteRT Qwen3-1.7B: first capture SPREAD 27.0 (68.86c / 68.69 / 68.82 / 50.30 tok/s; run 4 started nominal and
   ended fair) -> quarantined in device-jsonl-flagged/, 240 s, re-run once: SPREAD 39.1 (68.85c / 66.45 / 68.61 /
   42.65; run 4 nominal -> fair, TTFT 4,000 ms against 2,254-2,528) -> GATE_FAIL, the re-run is kept (FLAGGED.txt).
3. Every other cell passed the gate. Prompt tokens: 1,338 (MLX, llama.cpp, LiteRT 1.7B) / 1,339 (LiteRT 0.6B); every
   1024 run generated 256 tokens; the anchors 128. Outputs are on-task text (`outputSample`).
