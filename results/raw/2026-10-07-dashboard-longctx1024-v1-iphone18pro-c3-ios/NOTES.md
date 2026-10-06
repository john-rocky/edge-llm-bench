# 2026-10-07-dashboard-longctx1024-v1-iphone18pro-c3-ios — notes

Chunk 3 of 4 of the 2026-10-07 iPhone 18 Pro sitting of the 1024 / 256 task-prompt set (task
`long-context-1024-gen256`, cells `matrices/dashboard-longctx1024-v1.cells`, ios section): iPhone19,2, iOS 27.2 beta
build 24B5099f, devicectl `C7A74909-7573-5A0F-9201-F7D03DC811EF`, UDID `00008160-000038CA02C00036`, USB, charging;
app `com.example.CoreMLLLMChat` 0.2.0 (1), BenchmarkApp Release build of commit 3be68d7 installed 2026-10-07 02:48 JST.
Engines stamped in the records: LiteRT-LM v0.16.0 (`CLiteRTLM.xcframework.zip@v0.16.0 sha256:4e0f683d…`),
llama.cpp b8999, mlx-swift 60bd0d78. Hand-run, no SESSION.json; the split, the command and the defaults are in
`2026-10-07-dashboard-longctx1024-v1-iphone18pro-c1-ios/NOTES.md` (CELL_TIMEOUT 1200).

Cells of this campaign (verbatim rows of the cells file):

```
ios mlx-swift mlx-community/Qwen3-4B-4bit long-context-1024-gen256 cooldown=300
ios litert-lm litert-community/Qwen3-4B long-context-1024-gen256 cooldown=300 context-tokens=2048
ios llama.cpp unsloth/Qwen3-4B-GGUF/Q4_K_M long-context-1024-gen256 cooldown=300 context-tokens=2048
```

Hold 07:19:50–07:51:11 JST (300 s after chunk 2's hold was returned at 07:14:49), runner 07:19:50–07:51:09.

1. MLX Qwen3-4B passed the gate (40.4c / 40.3 / 40.3 / 40.3 tok/s, nominal throughout).
2. LiteRT Qwen3-4B: first capture HOT nominal,nominal,fair,fair (34.46c / 26.03 / 20.47 / 20.71; run 2 ended fair, TTFT
   6.5 s -> 14.2 s) -> quarantined in device-jsonl-flagged/, 240 s, re-run once: HOT nominal,nominal,serious,serious
   (34.55c / 23.76 / 17.19 / 18.76; run 2 ended serious, TTFT 6.5 s -> 17.3 s, prefill 208 -> 78 tok/s) ->
   GATE_FAIL, the re-run is kept (FLAGGED.txt). Its warm median (18.8) is a throttled value. Because the capture saw
   `serious`, the runner paused SERIOUS_COOLDOWN 600 s on top of the 300 s cooldown before the next cell.
3. llama.cpp Qwen3-4B passed the gate (34.6c / 34.7 / 34.8 / 34.8, nominal throughout).
4. Prompt tokens: 1,338 (MLX, llama.cpp) / 1,339 (LiteRT); every run generated 256 tokens; outputs are on-task text.
