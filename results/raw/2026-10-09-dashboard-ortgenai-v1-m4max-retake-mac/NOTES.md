# 2026-10-09 ONNX Runtime GenAI dashboard cells, Mac Studio M4 Max — Qwen3 4B WebGPU retake (round r4-mac)

The two Qwen3 4B WebGPU rows of `matrices/dashboard-ortgenai-v1.cells` (short-chat and long-context-1024-gen256,
context-tokens 2048, cooldown 300 s), retaken after they failed in `../2026-10-08-dashboard-ortgenai-v1-m4max-2-mac`
(its NOTES.md: the Hugging Face cache's links for `model.onnx` / `model.onnx.data`, replaced by same-content copies
at 00:55). Same engine (onnxruntime-genai 0.17.1, onnxruntime 1.30.0, onnxruntime-ep-webgpu 0.4.0), folder
(onnx-community/Qwen3-4B-ONNX @98ddba15, `onnxruntime/webgpu/webgpu-int4-kld-block-32`, model.onnx sha256
bcaf3e1f…, model.onnx.data sha256 18bef605…), driver and runner settings as that campaign. Session anchor:
`../2026-10-09-dashboard-ortgenai-v1-m4max-retake-anchor-mac`, run first in the same window.

## Machine and window

- Mac quiet window `ortgenai-r4-mac-retake`, 2026-10-09 02:25:37–02:37:33 JST (anchor 02:26:18–02:26:56, 300 s
  cooldown, the cells 02:31:56–02:37:33); `conditions.hostQuiet` is true and the window is named in every record.
- Machine state: the Xcode GUI app used about half a CPU core (42.1 % at 02:26, 44.0 % at 02:37); mediaanalysisd
  was stopped (state T, 0 % CPU) by another session; load1 4.8 at 02:26. The quiet bar: as in
  `../2026-10-08-dashboard-ortgenai-v1-m4max-1-mac/NOTES.md`.
- WebGPU witness in every run: the plugin EP library is loaded and the GPU time during the generation is above 0.

## Cells

| model | task | backend | records ok / all | warm median decode tok/s (n, spread) | warm prefill tok/s | warm TTFT ms | cold decode / prefill / TTFT | peak MiB | GPU ms (warm median) | gate |
|---|---|---|---|---|---|---|---|---|---|---|
| Qwen3-4B | long-context-1024-gen256 | webgpu | 4 / 4 | 69.3 (3, 0.1 %) | 1,045.8 | 1,279.5 | 69.2 / 934.9 / 1,431.2 | 5,222 | 4,758 | ok |
| Qwen3-4B | short-chat | webgpu | 4 / 4 | 81.6 (3, 0.3 %) | 286.6 | 66.4 | 81.4 / 218.3 / 87.1 | 3,907 | 1,566 | ok |

No gate fired (no FLAGGED.txt, no FAILURES.txt).

## Text, read by a person

The greedy text is identical across the four runs of each cell. short-chat: on the question (Qwen3 thinking).
long-context: on the task, the thinking drafts items 1–4 of the list with their explanations.
