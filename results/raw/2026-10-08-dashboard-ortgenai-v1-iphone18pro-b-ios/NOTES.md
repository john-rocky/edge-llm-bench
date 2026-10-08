# 2026-10-08-dashboard-ortgenai-v1-iphone18pro-b-ios — notes

ONNX Runtime GenAI arm (`onnxruntime-genai-cpu`) on the iPhone 18 Pro, Qwen3 1.7B: the two ios rows of
`matrices/dashboard-ortgenai-v1.cells` for it, verbatim:

```
ios onnxruntime-genai onnx-community/Qwen3-1.7B-ONNX short-chat backend=cpu file=onnxruntime/cpu_and_mobile/cpu-int4-kld-block-128 revision=cc6a06a21d614e9b8e92a6adfab1074d4e7d2438 context-tokens=2048
ios onnxruntime-genai onnx-community/Qwen3-1.7B-ONNX long-context-1024-gen256 backend=cpu file=onnxruntime/cpu_and_mobile/cpu-int4-kld-block-128 revision=cc6a06a21d614e9b8e92a6adfab1074d4e7d2438 context-tokens=2048
```

Same phone, app build, engine, telemetry setting and anchors as
`2026-10-08-dashboard-ortgenai-v1-iphone18pro-a-ios` (see its NOTES.md); the app was installed again at
the start of this hold (17:29:24). The app fetched the folder (1.42 GB) at commit cc6a06a21d61 in a smoke
launch (one short-chat run, 17:29:24–17:31:00, not a record here). Command:
`CAMPAIGN=2026-10-08-dashboard-ortgenai-v1-iphone18pro-b-ios BENCH_UDID=00008160-000038CA02C00036
APP=com.example.CoreMLLLMChat CELL_TIMEOUT=1200 scripts/bench_matrix_iphone.sh run r5-b.cells`
(17:33:31–17:42:29).

- short-chat: gate OK.
- long-context-1024-gen256: HOT in both captures. The first: run 3 ended at thermal state fair, run 4
  started fair and ended serious (moved to `device-jsonl-flagged/`); the runner waited its 240 s (its
  600 s wait applies when a run starts serious) and the retry's four runs all started fair, run 4 again
  ending serious — kept, `FLAGGED.txt`. Warm decode fell with the heat (28.7 → 22.0 tok/s in the retry).
  The greedy text closes its thinking and starts the numbered list when the budget ends; the four kept
  runs are byte-identical.

A record's `generatedTokenCount` counts the tokens from the second on (the first is on the TTFT side) —
docs/ortgenai-arm-v1.md "iPhone".
