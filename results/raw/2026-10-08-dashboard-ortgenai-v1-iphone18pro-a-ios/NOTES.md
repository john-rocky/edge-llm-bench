# 2026-10-08-dashboard-ortgenai-v1-iphone18pro-a-ios — notes

ONNX Runtime GenAI arm (`onnxruntime-genai-cpu`) on the iPhone 18 Pro, Qwen3 0.6B: the two ios rows of
`matrices/dashboard-ortgenai-v1.cells` for it, verbatim:

```
ios onnxruntime-genai onnx-community/Qwen3-0.6B-ONNX short-chat backend=cpu file=onnxruntime/cpu_and_mobile/cpu-int4-kld-block-128 revision=da1453100cf3ff33ef56d17983fc7a8648706db6 context-tokens=2048
ios onnxruntime-genai onnx-community/Qwen3-0.6B-ONNX long-context-1024-gen256 backend=cpu file=onnxruntime/cpu_and_mobile/cpu-int4-kld-block-128 revision=da1453100cf3ff33ef56d17983fc7a8648706db6 context-tokens=2048
```

Phone: iPhone 18 Pro (iPhone19,2), iOS 27.2 (24B5099f), UDID `00008160-000038CA02C00036`, USB.
App `com.example.CoreMLLLMChat` 0.2.0 (1): the BenchmarkApp Release build of commit a9fa7b5 (branch
ortgenai-arm; its iOS sources are ddd7e42's), main binary sha256 `4b95fa387c3fb277…`, installed at
17:14:46 JST. Engine: `onnxruntime-genai 0.17.0 (release ios xcframework)` (CPU EP, engine-default
threads; the framework's own ONNX Runtime reports 1.26.0), telemetry off (`ORT_DISABLE_TELEMETRY=1`
before the first model + `OgaSetTelemetryEnabled(false)`; the app container's `Library/Application
Support` held only `coreai-cache` before and after, no `Microsoft/DeveloperTools/.onnxruntime` store).
Session anchors: `2026-10-08-dashboard-ortgenai-v1-iphone18pro-anchor-ios` (17:17:42–17:19:42).

The app fetched the folder at commit da1453100cf3 into its hub cache in a smoke launch before the anchors
(one short-chat run, 17:14:46–17:15:12, not a record of this campaign); every record's `modelRevision` is
that commit. Command, inside the iPhone hold: `CAMPAIGN=2026-10-08-dashboard-ortgenai-v1-iphone18pro-a-ios
BENCH_UDID=00008160-000038CA02C00036 APP=com.example.CoreMLLLMChat CELL_TIMEOUT=1200
scripts/bench_matrix_iphone.sh run r5-a.cells` (runs 4: run 1 cold, runs 2–4 warm; 17:21:22–17:28:36).

- short-chat: gate OK.
- long-context-1024-gen256: the first capture's warm spread was 8.5 % (moved to
  `device-jsonl-flagged/`), the runner's one retry 7.7 % — kept, `FLAGGED.txt`. Every run of both captures
  started and ended at thermal state nominal; decode fell 2.5–4 % from each run to the next in both
  (64.9 → 58.0 and 64.7 → 58.2 tok/s), prefill likewise. The greedy text ends in a repeated sentence over
  its second half (the 0.6B 1K loop of the other platforms); the four kept runs are byte-identical.

Each console file carries one `YARDSTICK_NOTE ortgenai_load` per launch and `ortgenai_run` /
`ortgenai_text` per generation (prompt and picked tokens, generator / prefill / first-pick / decode ms,
the templated prompt's sha256, the decoded text). A record's `generatedTokenCount` counts the tokens from
the second on (127 / 255 at the budget; the first is on the TTFT side) — docs/ortgenai-arm-v1.md "iPhone".
