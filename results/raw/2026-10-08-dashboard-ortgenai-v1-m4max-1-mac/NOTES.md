# 2026-10-08 ONNX Runtime GenAI dashboard cells, Mac Studio M4 Max — Qwen3 0.6B / 1.7B (round r4-mac, window 1)

The eight Mac rows of `matrices/dashboard-ortgenai-v1.cells` for Qwen3 0.6B and 1.7B (short-chat and
long-context-1024-gen256, the CPU EP and the WebGPU plugin EP, context-tokens 2048), through
`./bench matrix <cells> --platform mac` (`scripts/bench_matrix_mac.sh` → `scripts/ortgenai_mac.py`): one engine
process per cell, run 1 cold and runs 2–4 warm, engine-default threads, the runner's 30 s cooldown between cells.
Session anchor: `../2026-10-08-dashboard-ortgenai-v1-m4max-anchor-mac`, run first in the same window.
The Qwen3 4B cells: `../2026-10-08-dashboard-ortgenai-v1-m4max-2-mac` (same window, after a 300 s cooldown).

## Machine and window

- Mac Studio M4 Max (Mac16,9, 16 CPUs, 128 GB), macOS 27.0 (26A428).
- One Mac quiet window held both ORT campaigns of the sitting: lock label `ortgenai-r4-mac-1 ortgenai-r4-mac-2`,
  2026-10-08 23:33:41 – 2026-10-09 00:07:47 JST. This campaign ran 23:35:30–23:43:28; `conditions.hostQuiet` is
  true and `provenance.hostBefore.snapshot.quietWindow` names the window in every record.
- Machine state: the Xcode GUI app (one process, open since 10:44 that day) used about half a CPU core through
  the window (48.8–61.4 % at 23:34, 23:48 and 00:07); mediaanalysisd was stopped (state T, 0 % CPU) by another
  session before the window; load1 6.1 at the window's start. The quiet bar of this sitting left the Xcode
  process out and counted another process as busy only at ≥ 50 % CPU in two samples 20 s apart (with the lock
  empty, load1 ≤ 8 and no other capture process, three polls in a row).

## Engine and models

- pip onnxruntime-genai 0.17.1 (commit 83de55a1), onnxruntime 1.30.0, onnxruntime-ep-webgpu 0.4.0, Python 3.14.6;
  `engineArtifact` = libonnxruntime-genai.dylib sha256 36ad4673…f036. Telemetry off in every run
  (ORT_DISABLE_TELEMETRY=1 before init + disable_telemetry_events(); the telemetry dir unchanged).
- onnx-community/Qwen3-0.6B-ONNX @da145310 and onnx-community/Qwen3-1.7B-ONNX @cc6a06a2: CPU =
  `onnxruntime/cpu_and_mobile/cpu-int4-kld-block-128`, WebGPU = `onnxruntime/webgpu/webgpu-int4-kld-block-32`;
  `model.quantization` in every record = the label registered in `models/ortgenai-recipes.json`.
- WebGPU witness in every WebGPU run: the plugin EP library is loaded (`provenance.onnxruntimeImages`) and the
  GPU time during the generation is above 0 (`metrics.gpuMillisecondsDuringGeneration`); 0 in every CPU run.

## Cells

| model | task | backend | records ok / all | warm median decode tok/s (n, spread) | warm prefill tok/s | warm TTFT ms | cold decode / prefill / TTFT | peak MiB | GPU ms (warm median) | gate |
|---|---|---|---|---|---|---|---|---|---|---|
| Qwen3-0.6B | long-context-1024-gen256 | cpu | 4 / 4 | 162.1 (3, 2.9 %) | 937.7 | 1,427.0 | 163.1 / 905.9 / 1,477.0 | 2,250 | 0 | ok |
| Qwen3-0.6B | long-context-1024-gen256 | webgpu | 4 / 4 | 172.9 (3, 0.9 %) | 4,279.5 | 312.7 | 171.9 / 3,985.7 / 335.8 | 2,420 | 1,661 | ok |
| Qwen3-0.6B | short-chat | cpu | 4 / 4 | 259.3 (3, 5.1 %) | 1,119.4 | 17.1 | 267.2 / 1,001.2 / 19.1 | 1,255 | 0 | first capture quarantined (.attempt1); FLAGGED: first='SPREAD 5.1' retry='SPREAD 5.1' (retry kept; ⚠ downstream) |
| Qwen3-0.6B | short-chat | webgpu | 4 / 4 | 207.0 (3, 1.4 %) | 875.6 | 21.8 | 203.6 / 467.7 / 40.7 | 1,196 | 591 | ok |
| Qwen3-1.7B | long-context-1024-gen256 | cpu | 4 / 4 | 100.2 (3, 0.8 %) | 452.7 | 2,955.8 | 98.8 / 442.0 / 3,027.3 | 3,719 | 0 | ok |
| Qwen3-1.7B | long-context-1024-gen256 | webgpu | 4 / 4 | 123.2 (3, 0.3 %) | 2,315.4 | 577.9 | 122.4 / 2,214.9 / 604.2 | 3,492 | 2,503 | ok |
| Qwen3-1.7B | short-chat | cpu | 4 / 4 | 128.2 (3, 4.3 %) | 494.9 | 38.5 | 129.7 / 467.7 / 40.7 | 2,567 | 0 | ok |
| Qwen3-1.7B | short-chat | webgpu | 4 / 4 | 138.4 (3, 0.2 %) | 528.2 | 36.0 | 137.5 / 362.0 / 52.6 | 2,236 | 902 | ok |

The 0.6B CPU short-chat cell read SPREAD 5.1 % in both captures: the first is quarantined (`*.jsonl.attempt1`),
the retry is kept and marked in FLAGGED.txt. Beside each cell's records: `ortgenai-logs/` (`.log` = harness and
engine stderr, `.decoded.txt` per run, `.worker.json` = the engine process's own report).

## Text, read by a person

The greedy text is identical across the four runs of every cell.

- short-chat, all four cells: on the question (Qwen3 thinking; the 0.6B CPU cell closes it and starts the answer).
- 0.6B CPU long-context: on the task, then the thinking ends in an exact repetition loop ("I need to make sure
  that each item is distinct …" three times) — it passes the automated screen and fails the read.
- 0.6B WebGPU long-context: on the task, closes the thinking and starts the list (items 1–2).
- 1.7B CPU long-context: on the task, closes the thinking and starts the list (items 1–3).
- 1.7B WebGPU long-context: on the task, the thinking restates its first step ("identify the 25 distinct
  things") four times and does not reach the list within 256 tokens — it passes the automated screen and fails
  the read.
