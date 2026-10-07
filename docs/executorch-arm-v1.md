# ExecuTorch on Mac — arm v1 (draft, 2026-10-07)

Status: **draft** from round r1 of the dashboard ExecuTorch lane. Every number
below is a smoke check, not a measurement. The runner (`scripts/executorch_mac.py`),
the cells and the Android / iPhone arms come in later rounds.

## What the arm runs

ExecuTorch's own C++ example runner `llama_main` (examples/models/llama,
`TextLLMRunner`), built from the tagged source with the repository's preset,
on the XNNPACK CPU backend. One process per run. The prompt is the repository's
text prompt rendered once on the host with the model's chat template, handed
to `--prompt_file`; sampling is greedy (`--temperature 0`).

The models are **own exports**: the ExecuTorch source tree's example recipe,
run by us. They are not published ExecuTorch artifacts, and the arm never mixes
them with published `.pte` files.

## Pins and artifact provenance

- Engine source: tag `v1.5.1` (`3b60683923245cf472b7323426920e15623ba361`,
  2026-09-18). The tree must sit in a directory named exactly `executorch`
  (v1.5.1 `CMakeLists.txt` stops otherwise, pytorch/executorch#6475).
- Build (`scripts/executorch/build_llama_main_mac.sh`), as the llama README
  "Step 3": `cmake --workflow --preset llm-release`, then
  `cmake --workflow --preset llama-release` in `examples/models/llama`. The
  preset turns on XNNPACK, the optimized, quantized and LLM kernels and, on
  Darwin, Core ML and the torchao kernels; `CMAKE_BUILD_TYPE=Release`. A
  Release build compiles ExecuTorch's log out, so the binary prints only the
  generated text and the stats line. A second build of the same source with
  `EXECUTORCH_ENABLE_LOGGING=ON` is a witness only (thread pool size, the
  metadata the runner read); it produces no number.
- Export venv: CPython 3.12, `executorch==1.5.1` (PyPI wheel),
  `torch==2.14.0` (the wheel does not depend on torch; 2.14.0 is the tag's
  `torch_pin.py`), `torchao==0.18.0`, `transformers==5.0.0rc1` (the tag's
  `requirements-examples.txt`, used here only for the chat template).
  The wheel's export sources are byte-identical to the tag's tree.
- Export (`scripts/executorch/export_qwen3.py`): `convert_weights.py` of the
  tree turns the HF snapshot into a Meta-format checkpoint, then
  `python -m executorch.extension.llm.export.export_llm --config
  examples/models/qwen3/config/qwen3_xnnpack_q8da4w.yaml` (unchanged) with
  `base.model_class`, `base.params`, `base.checkpoint` and
  `export.output_name`. Each `.pte` has a `<name>.recipe.json` beside it:
  ExecuTorch version and commit, the config yaml and params json verbatim,
  the checkpoint's HF revision and file hashes, the commands, the `.pte`
  sha256 and size, the host.

## Recipes

| Model id | Recipe label (`model.quantization`) |
|---|---|
| `own-export/Qwen3-0.6B-ET1.5.1-xnnpack-8da4w-emb8-ctx2048` | 8da4w: int8 dynamic per-token asymmetric activations x int4 symmetric weights, group 128, HQQ scale-only (every Linear incl. lm_head); embedding int8 per-row (embedding_byte); fp32 compute and KV cache; own export, ExecuTorch 1.5.1 |

The group size comes from the export code, not the yaml: the yaml sets no
`group_size`, and v1.5.1 `quantize.py` uses 128 for `8da4w` when none is
given. The context is fixed at export: `max_seq_length` = `max_context_length`
= 2048, so the KV cache is allocated for 2048 tokens on every run
(`conditions.contextTokens` = 2048). Prefill takes up to 2047 tokens in one
call (dynamic token dimension).

## Record fields and task contract

| Field | Meaning |
|---|---|
| `runtime`, `engineVersion`, `engineArtifact` | `executorch-xnnpack`, `v1.5.1`, `llama_main` sha256 |
| `promptTokensPerSecond` | prompt_tokens / (prompt_eval_end_ms − inference_start_ms) × 1000 — **prefill includes tokenization** (the runner starts the clock, then encodes) |
| `firstTokenLatencyMS` | first_token_ms − inference_start_ms (the same window) |
| `decodeTokensPerSecond` | generated_tokens / (inference_end_ms − prompt_eval_end_ms) × 1000; generated_tokens counts the decode loop, the reply has one more token |
| `memoryPeakResidentMB` | process RSS high-water, `ru_maxrss` bytes / 2^20 (MiB); includes model load |
| `coldRun` | true: one generation in a fresh process; false: `--warmup` ran the same prompt once in the process first and the second generation is measured |
| `conditions.textCheck` | `android/bench/parsers.text_integrity` over the generated text |

The runner is not patched (official-sdk): the definitions above are
ExecuTorch's own `Stats` (`extension/llm/runner/stats.h`), recomputed from its
timestamps, which are whole milliseconds.

## Status (2026-10-07)

Smoke only; no number here is a measurement. Round r1 exported Qwen3 0.6B
and ran `scripts/executorch/smoke_r1_mac.sh` on a Mac Studio (Mac16,9, M4 Max:
12 performance + 4 efficiency cores, 128 GB, macOS 27.0) inside a measurement
window: short-chat and long-context-1024-gen256, three cold and three warm
launches each. All twelve exited normally, every stats line recomputed from
its timestamps, and every generated text passed
`android/bench/parsers.text_integrity`. Greedy decoding was deterministic:
each task produced byte-identical text across launches and regimes. With
Qwen3's default thinking mode, both budgets end inside `<think>`.

Facts the runner (round r4) must carry:

- `--cpu_threads -1` (the default) sizes the thread pool at 16 on this chip:
  v1.5.1's cpuinfo heuristic counts no efficiency core on the M4 Max
  (logging build: `Number of efficient cores 0`). A cell either passes
  `--cpu_threads` or records the heuristic's value.
- The Release binary prints no ExecuTorch log line, so the thread count and
  the metadata the runner read come from the logging build; ExecuTorch's own
  RSS log reads 0 on macOS, so RSS comes from the wrapper's `rusage`.
- Model load (outside every rate's window) usually took about a quarter of a
  second, and occasionally seconds longer when the model and tokenizer were
  read again from the external volume they sit on (cause not established).
  The record keeps load time and launch wall time apart from the rates.
- The long-context prompt is 1338 tokens with the Qwen3 tokenizer (the task
  name's 1024 is nominal), 19 for short-chat.
