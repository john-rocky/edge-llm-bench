# 2026-10-08 ONNX Runtime GenAI dashboard cells, Mac Studio M4 Max — Qwen3 4B (round r4-mac, window 2)

The four Mac rows of `matrices/dashboard-ortgenai-v1.cells` for Qwen3 4B (short-chat and long-context-1024-gen256,
the CPU EP and the WebGPU plugin EP, context-tokens 2048, the rows' 300 s cooldown), through
`./bench matrix <cells> --platform mac`: one engine process per cell, run 1 cold and runs 2–4 warm, engine-default
threads. Same window and session anchor as `../2026-10-08-dashboard-ortgenai-v1-m4max-1-mac` (its NOTES.md has the
machine, the window's quiet bar, the engine and the folders); this campaign ran 2026-10-08 23:48:29 –
2026-10-09 00:07:47 JST, after a 300 s cooldown that followed window 1. onnx-community/Qwen3-4B-ONNX @98ddba15.

- Machine state: the Xcode GUI app used about half a CPU core (56.8 % at 23:48, 48.8 % at 00:07); mediaanalysisd
  was stopped (state T, 0 % CPU) by another session; load1 4.1 at 23:48.

## Cells

| model | task | backend | records ok / all | warm median decode tok/s (n, spread) | warm prefill tok/s | warm TTFT ms | cold decode / prefill / TTFT | peak MiB | GPU ms (warm median) | gate |
|---|---|---|---|---|---|---|---|---|---|---|
| Qwen3-4B | long-context-1024-gen256 | cpu | 4 / 4 | 49.9 (3, 0.6 %) | 193.9 | 6,899.6 | 49.5 / 196.1 / 6,824.5 | 4,791 | 0 | ok |
| Qwen3-4B | long-context-1024-gen256 | webgpu | 0 / 1 | — (0, — %) | — | — | — / — / — | — | — | FAILURES.txt: RuntimeError: External data path validation failed for initializer: model.embed_tokens.qwe |
| Qwen3-4B | short-chat | cpu | 4 / 4 | 64.0 (3, 1.2 %) | 208.1 | 91.4 | 63.9 / 175.5 / 108.4 | 3,521 | 0 | first capture quarantined (.attempt1) |
| Qwen3-4B | short-chat | webgpu | 0 / 1 | — (0, — %) | — | — | — / — / — | — | — | FAILURES.txt: RuntimeError: External data path validation failed for initializer: model.embed_tokens.qwe |

- 4B CPU short-chat: SPREAD 5.7 % in the first capture (quarantined as `*.jsonl.attempt1`); the retry's spread 1.2 %.
- The two WebGPU cells failed in run 1 (engine exit 1, runs 2–4 not attempted, FAILURES.txt; `failureDetail`:
  "RuntimeError: External data path validation failed for initializer: model.embed_tokens.qweight. Error: External
  data path escapes model directory"). In the local Hugging Face cache this folder's `model.onnx` and
  `model.onnx.data` were links into two different directories of the cache's shared blob store, and onnxruntime
  1.30.0 refuses external data outside the real directory of the model file; the CPU folder's two files were plain
  files and loaded. The two files were replaced by same-content copies (APFS clones, sha256 unchanged) on
  2026-10-09 at 00:55 and the two cells were retaken in `../2026-10-09-dashboard-ortgenai-v1-m4max-retake-mac` with
  their own session anchor. The failed records stay here (failed-runs-stay).

## Text, read by a person

The greedy text is identical across the four runs of each CPU cell. short-chat: on the question (Qwen3 thinking).
long-context: on the task, the thinking drafts items 1–2 of the list with their explanations.
