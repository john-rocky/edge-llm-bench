# 2026-10-07-dashboard-longctx1024-v1-iphone18pro-c2-ios — notes

Chunk 2 of 4 of the 2026-10-07 iPhone 18 Pro sitting of the 1024 / 256 task-prompt set (task
`long-context-1024-gen256`, cells `matrices/dashboard-longctx1024-v1.cells`, ios section): iPhone19,2, iOS 27.2 beta
build 24B5099f, devicectl `C7A74909-7573-5A0F-9201-F7D03DC811EF`, UDID `00008160-000038CA02C00036`, USB, charging;
app `com.example.CoreMLLLMChat` 0.2.0 (1), BenchmarkApp Release build of commit 3be68d7 installed 2026-10-07 02:48 JST.
Engines stamped in the records: LiteRT-LM v0.16.0 (`CLiteRTLM.xcframework.zip@v0.16.0 sha256:4e0f683d…`),
llama.cpp b8999, mlx-swift 60bd0d78. Hand-run, no SESSION.json; the split, the command and the defaults are in
`2026-10-07-dashboard-longctx1024-v1-iphone18pro-c1-ios/NOTES.md` (CELL_TIMEOUT 1200).

Cells of this campaign (verbatim rows of the cells file):

```
ios litert-lm litert-community/gemma-4-E2B-it-litert-lm long-context-1024-gen256 cooldown=300 context-tokens=2048
ios mlx-swift mlx-community/gemma-4-e2b-it-qat-OptiQ-4bit long-context-1024-gen256 cooldown=300
ios llama.cpp unsloth/gemma-4-E2B-it-GGUF/Q4_K_M long-context-1024-gen256 cooldown=300 context-tokens=2048
```

Hold 06:57:30–07:14:49 JST (300 s after chunk 1's hold was returned at 06:52:30), runner 06:57:30–07:14:47.

1. LiteRT Gemma 4 E2B: first capture HOT nominal,nominal,nominal,fair (75.76c / 78.94 / 78.93 / 47.51 tok/s; run 3
   ended fair, run 4 started fair) -> quarantined in device-jsonl-flagged/, 240 s, re-run once: HOT
   nominal,nominal,nominal,fair again (79.18c / 78.98 / 78.99 / 48.13; run 4 TTFT 1,201 ms against 736-762) ->
   GATE_FAIL, the re-run is kept (FLAGGED.txt). Its warm median includes the fair run 4. The same shape as on
   2026-10-06.
2. MLX Gemma 4 E2B and llama.cpp Gemma 4 E2B passed the gate (four runs nominal -> nominal each).
3. Prompt tokens: 1,106 (LiteRT) / 1,107 (MLX) / 1,098 (llama.cpp); every run generated 256 tokens. Outputs: MLX and
   llama.cpp list on-task items; LiteRT answers that the provided text is placeholder text and declines the list (the
   same reply as on 2026-10-06), a coherent sentence, not a repetition loop.
