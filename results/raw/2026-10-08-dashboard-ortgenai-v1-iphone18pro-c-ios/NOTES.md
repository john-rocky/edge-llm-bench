# 2026-10-08-dashboard-ortgenai-v1-iphone18pro-c-ios — notes

ONNX Runtime GenAI arm (`onnxruntime-genai-cpu`) on the iPhone 18 Pro, Qwen3 4B: the two ios rows of
`matrices/dashboard-ortgenai-v1.cells` for it, verbatim:

```
ios onnxruntime-genai onnx-community/Qwen3-4B-ONNX short-chat backend=cpu cooldown=300 file=onnxruntime/cpu_and_mobile/cpu-int4-kld-block-128 revision=98ddba15d05dede4435afb63f13280abcdbc2a48 context-tokens=2048
ios onnxruntime-genai onnx-community/Qwen3-4B-ONNX long-context-1024-gen256 backend=cpu cooldown=300 file=onnxruntime/cpu_and_mobile/cpu-int4-kld-block-128 revision=98ddba15d05dede4435afb63f13280abcdbc2a48 context-tokens=2048
```

Same phone, app build, engine, telemetry setting and anchors as
`2026-10-08-dashboard-ortgenai-v1-iphone18pro-a-ios` (see its NOTES.md). The hold started after a 12-minute
rest following `…-b-ios` (whose last run ended at thermal state serious); the app was installed again
(17:54:56) and fetched the folder (2.90 GB, `model.onnx` + `model.onnx.data`) at commit 98ddba15d05d in a
smoke launch (one short-chat run, 17:54:56–17:56:53, not a record here). Command:
`CAMPAIGN=2026-10-08-dashboard-ortgenai-v1-iphone18pro-c-ios BENCH_UDID=00008160-000038CA02C00036
APP=com.example.CoreMLLLMChat CELL_TIMEOUT=1200 scripts/bench_matrix_iphone.sh run r5-c.cells`
(17:59:23–18:27:19). After it the phone's pinned build (main binary sha256 `6564d5b7…`, LiteRT-LM v0.16.0)
was installed again (18:27:22).

- short-chat: the first capture's warm spread was 5.1 % (moved to `device-jsonl-flagged/`); the retry
  passed the gate and stands.
- long-context-1024-gen256: HOT in both captures (initial states nominal,nominal,serious,serious; after the
  runner's 600 s wait nominal,fair,serious,serious) — the retry is kept, `FLAGGED.txt`. Run 1 of the retry
  went nominal → fair; warm decode at serious read 9.5–8.9 tok/s against run 1's 14.4. The greedy text
  drafts items 1–2 of the list inside its thinking when the budget ends; the four kept runs are
  byte-identical.

A record's `generatedTokenCount` counts the tokens from the second on (the first is on the TTFT side) —
docs/ortgenai-arm-v1.md "iPhone".
