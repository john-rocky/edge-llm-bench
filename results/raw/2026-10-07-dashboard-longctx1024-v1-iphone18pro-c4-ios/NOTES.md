# 2026-10-07-dashboard-longctx1024-v1-iphone18pro-c4-ios — notes

Chunk 4 of 4 of the 2026-10-07 iPhone 18 Pro sitting of the 1024 / 256 task-prompt set (task
`long-context-1024-gen256`, cells `matrices/dashboard-longctx1024-v1.cells`, ios section): iPhone19,2, iOS 27.2 beta
build 24B5099f, devicectl `C7A74909-7573-5A0F-9201-F7D03DC811EF`, UDID `00008160-000038CA02C00036`, USB, charging;
app `com.example.CoreMLLLMChat` 0.2.0 (1), BenchmarkApp Release build of commit 3be68d7 installed 2026-10-07 02:48 JST.
Engines stamped in the records: LiteRT-LM v0.16.0 (`CLiteRTLM.xcframework.zip@v0.16.0 sha256:4e0f683d…`),
llama.cpp b8999. Hand-run, no SESSION.json; the split, the command and the defaults are in
`2026-10-07-dashboard-longctx1024-v1-iphone18pro-c1-ios/NOTES.md` (CELL_TIMEOUT 1200).

Cells of this campaign (verbatim rows of the cells file):

```
ios litert-lm litert-community/gemma-4-E4B-it-litert-lm long-context-1024-gen256 cooldown=300 context-tokens=2048
ios mlx-swift mlx-community/gemma-4-e4b-it-qat-OptiQ-4bit long-context-1024-gen256 cooldown=300 exclude=app-killed-at-model-load-sigkill
ios llama.cpp unsloth/gemma-4-E4B-it-GGUF/Q4_K_M long-context-1024-gen256 cooldown=300 context-tokens=2048
```

Hold 07:56:11–08:22:36 JST (300 s after chunk 3's hold was returned at 07:51:11), runner 07:56:11–08:22:34.

1. LiteRT Gemma 4 E4B: first capture HOT nominal,nominal,fair,fair (33.37c / 32.08 / 19.91 / 20.06 tok/s; run 2 ended
   fair) -> quarantined in device-jsonl-flagged/, 240 s, re-run once: HOT nominal,nominal,serious,serious (34.04c /
   32.49 / 16.84 / 18.96; run 2 ended serious, TTFT 2.7 s -> 7.5 s) -> GATE_FAIL, the re-run is kept (FLAGGED.txt).
   Its warm median (19.0) is a throttled value. After the `serious` capture the runner paused SERIOUS_COOLDOWN 600 s on
   top of the 300 s cooldown before the next cell.
2. MLX Gemma 4 E4B: not run, `exclude=app-killed-at-model-load-sigkill` (SKIPPED.txt), as in the cells file.
3. llama.cpp Gemma 4 E4B passed the gate (30.6c / 30.4 / 30.7 / 31.0, nominal throughout).
4. Prompt tokens: 1,106 (LiteRT) / 1,098 (llama.cpp); every run generated 256 tokens. Outputs: LiteRT answers that the
   provided text is placeholder text (a coherent sentence, the same reply as on 2026-10-06); llama.cpp prints
   "1. [Item 1] 2. [Item 2] 3. [Item 3] …" in all four runs — a placeholder list, not on-task text (the same as on
   2026-10-06 on this phone and on the Mac; the gate's DEGENERATE check does not fire on it).
