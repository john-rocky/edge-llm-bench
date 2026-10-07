# 2026-10-07 ONNX Runtime GenAI smoke, Mac Studio M4 Max

Smoke of the prototype driver `scripts/ortgenai_mac.py`, not a dashboard measurement.
Mac Studio M4 Max (Mac16,9, macOS 27.0 build 26A428), 2026-10-07 22:33:42–22:34:39 JST,
inside the Mac quiet window `ortgenai-r1` (the lock named the window for every run:
`conditions.hostQuiet` true). One fresh engine process per run, one schema-v1 JSON per run at
the campaign root. `scripts/build_summary.py` reads `.json` records only under `app-path*/` and
`device-jsonl/`, so these records stay out of `results/summary/`.

## Engine and model

- pip `onnxruntime-genai==0.17.1` (commit 83de55a1), `onnxruntime==1.30.0`,
  `onnxruntime-ep-webgpu==0.4.0`, Python 3.14.6. Library hashes: `provenance.engineLibraries`
  of every record; `engineArtifact` = `libonnxruntime-genai.dylib` sha256 36ad4673…f036.
- `onnx-community/Qwen3-0.6B-ONNX` at revision da1453100cf3ff33ef56d17983fc7a8648706db6
  (2026-04-20, "Add optimized models for ORT GenAI (#3)"): CPU arm
  `onnxruntime/cpu_and_mobile/cpu-int4-kld-block-128` (model.onnx sha256 35fe3432…a957),
  WebGPU arm `onnxruntime/webgpu/webgpu-int4-kld-block-32` (model.onnx sha256 5e9fb386…909a),
  both equal to the Hub's lfs.sha256. The quantization string of each record is read from its
  model.onnx (`scripts/ortgenai_mac.py --describe-quant`): 197 MatMulNBits, int4 and int8 mixed
  (CPU folder 92 / 105, WebGPU folder 91 / 106), block 128 / 32, asymmetric, accuracy_level 4,
  int8 GatherBlockQuantized embedding, fp32 / fp16 activations and KV.
- Search options: max_length 2048 (the KV allocation: past_present_share_buffer is true),
  do_sample false; genai_config's own search block (max_length 40960, sampling) is overridden.
  The prompt goes through the model's chat_template.jinja as one user turn, Qwen3 thinking on.

## Runs

| cell | runs | record files |
|---|---|---|
| CPU short-chat (budget 128) | 3 | `onnxruntime-genai-cpu_*_short-chat_ctx2048_run{1,2,3}_*.json` |
| CPU long-context-1024-gen256 (budget 256) | 2 | `onnxruntime-genai-cpu_*_long-context-1024-gen256_ctx2048_run{1,2}_*.json` |
| WebGPU short-chat | 3 | `onnxruntime-genai-webgpu_*_short-chat_ctx2048_run{1,2,3}_*.json` |
| WebGPU long-context-1024-gen256 | 2 | `onnxruntime-genai-webgpu_*_long-context-1024-gen256_ctx2048_run{1,2}_*.json` |

Every run generated its full budget (`stopReason` length) and passed the automated text screen.
Beside each record: `.log` (harness and engine stderr), `.decoded.txt`, `.worker.json` (the
engine process's own report: per-step times, token ids).

## Text, read by a person

- short-chat, both backends: on the question (thinking about on-device AI; the CPU text closes
  `</think>` and starts the answer within 128 tokens). Greedy output is identical across the
  runs of a cell.
- long-context-1024-gen256, WebGPU: on the task; closes `</think>` and starts the numbered list.
- long-context-1024-gen256, CPU: on the task, but the thinking turns into a repetition loop in
  its last ~70 tokens (one sentence three times in a row, near-duplicates before it). The
  automated screen (`android/bench/parsers.text_integrity` + `cell_gate.degenerate` on the first
  200 characters) passes it; read as text, these two runs count as throughput only.

## What each record proves about the run

- Telemetry off: the engine process starts with `ORT_DISABLE_TELEMETRY=1` and calls
  `disable_telemetry_events()`; `provenance.sockets` (socket fds of the engine process every
  100 ms: none) and `provenance.telemetryDir` (the 1DS storage dir before and after the run:
  no file added or changed).
- GPU arm identity: `metrics.gpuMillisecondsDuringGeneration` (the Metal GPU time IOKit charged
  to the engine process from the worker's LOADED line to its last token; 0 on every CPU run),
  `provenance.onnxruntimeImages` (the WebGPU plugin dylib loaded) and the log's
  `model.device_type = WebGPU`. The runs keep the engine's default log level: with
  `ORTGENAI_ORT_VERBOSE_LOGGING=1` the WebGPU EP logs every program launch, about 520 lines per
  generated token, which changes the timing.
- Memory: `memoryPeakDuringDecodeMB` / `memoryMedianMB` = phys_footprint of the engine process,
  100 ms samples from after the generator is created to the last token, MiB.
