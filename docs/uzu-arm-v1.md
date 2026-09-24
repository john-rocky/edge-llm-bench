# Mirai (uzu) on Mac — arm v1

## What the arm runs

The Mac Python SDK driver runs the repository's text prompts in one fresh
engine process per run and stores schema-v1 JSONL, decoded text and raw logs.
Dashboard models are **own exports** through lalamo; they are not Mirai releases.
Cells: `matrices/dashboard-uzu-v1-mac.cells`. Android is absent; iPhone is deferred.

## Pins and artifact provenance

- Engine: official PyPI wheel `uzu==0.5.30`, upstream tag `0.5.30`
  (`6dc66029a7f3a2d35d8f7ee8cd7632ada4cc439e`). Each worker verifies the
  installed version and records the native extension's SHA256.
- Converter: [lalamo](https://github.com/trymirai/lalamo) at
  `d1cfe68e9b0cee64705b83e4bde1bf650a01cb1a`, frozen `uv.lock`, CPU extra.
  This older pin was chosen because `7ae34f15` writes a quantization-parameter
  layout that uzu 0.5.30 does not read. Each record carries the engine version and converter commit.
- `tools/uzu-lalamo-source-spec` selects mlx-community checkpoint origins
  through lalamo's plugin interface and pins checkpoint/tokenizer revisions.
  The built-in 0.6B MLX spec targets a different Qwen-hosted gs128 file;
  the selected mlx-community configs declare affine 4-bit weights, gs64.
- `scripts/uzu_prepare_lalamo.py` adapts known ungated Qwen3 and Gemma E2B
  metadata to the SDK reader: QKVG names become QKV, absent gates become null,
  and unsupported reasoning metadata is removed. Tensor payload bytes and
  absolute offsets, tokenizer and stored Jinja template are preserved and
  verified. Added `encoding.json` selects the SDK's bundled family protocol;
  this does not establish that the SDK executes the stored Jinja template.
  Keep raw exports and adapter reports with prepared files. Neither upstream
  source is patched. Source/export numerical parity remains untested.

## Recipes

| Cell recipe alias | Exact record label |
|---|---|
| `lalamo-d1cfe68e-bfloat16-default` | `lalamo bfloat16 (default), lalamo@d1cfe68e9b0cee64705b83e4bde1bf650a01cb1a` |
| `lalamo-d1cfe68e-qwen3-0.6b-mlx-affine-4bit-gs64` | `lalamo@d1cfe68e9b0cee64705b83e4bde1bf650a01cb1a import of mlx-community Qwen3-0.6B-4bit, MLX affine 4-bit gs64` |
| `lalamo-d1cfe68e-qwen3-1.7b-mlx-affine-4bit-gs64` | `lalamo@d1cfe68e9b0cee64705b83e4bde1bf650a01cb1a import of mlx-community Qwen3-1.7B-4bit, MLX affine 4-bit gs64` |
| `lalamo-d1cfe68e-qwen3-4b-mlx-affine-4bit-gs64` | `lalamo@d1cfe68e9b0cee64705b83e4bde1bf650a01cb1a import of mlx-community Qwen3-4B-4bit, MLX affine 4-bit gs64` |

The default route prints `loading floating-point weights as bfloat16` and
exports BF16 matrices with F32 normalization tensors. The MLX route imports
already-quantized weights with packed U8 storage, BF16 scales/biases and F32
normalization tensors. It does not quantize the bf16 checkpoint.

[Mirai's model card](https://huggingface.co/trymirai/Qwen3.5-0.8B-M) describes
Mirai-M as asymmetric 4-bit weights and zero points, bfloat16 scales, groups
of 32, block-diagonal random Hadamard transforms, PTQ and quantization-aware
distillation. The pinned lalamo CLI has no quantizer option; its compressed
modules import existing weights. We cannot reproduce Mirai-M with this
converter. The own-export recipes above are separate from Mirai-M.
Published `trymirai/Qwen3.5-0.8B-M` and `trymirai/Qwen3.5-4B-M` cells retain
that publisher label and are **non-dashboard reference models**.

## Record fields and task contract

`short-chat` uses the unchanged prompt and a 128-token total output cap.
`long-context-2048-gen256` uses 256 and requires `--context-tokens` for KV
allocation. Both use `with_token_limit` and `SamplingMethod.Greedy()`.
`thinking=off` sets SDK `ReasoningEffort.Disabled` without system-prompt text;
answer and reasoning channels are stored and counted against the same cap.

| Field | Meaning |
|---|---|
| `runtime`, `engineVersion` | `uzu`, observed `uzu 0.5.30` |
| `decodeTokensPerSecond`, `prefillTokensPerSecond` | SDK rates; smoke diagnostics only |
| `firstTokenLatencyMS`, token counts | SDK first-token seconds × 1,000; SDK input/output tokens |
| `memoryPeakAllocatedMB` | SDK `memory_used_bytes` / 1,000,000: Metal `current_allocated_size` high-water, updated on allocations in the engine context |
| `memoryPeakResidentMB` | Process RSS high-water / 1,000,000 from a fresh wrapper's single SDK child, `RUSAGE_CHILDREN.ru_maxrss` (bytes on macOS); includes model load/download |
| `conditions.hostQuiet`, `loadAverage` | False for these smokes; `--sample-load` samples live load before/after each worker |
| `decodedText`, `textCheck`, `provenance` | Full text; nonempty/replacement-character/repetition checks; raw SDK/RSS logs, host snapshot, prompt hash and artifact SHA256 manifest |

Metal allocations are distinct from RSS and `phys_footprint`; raw byte
counters stay in SDK/RSS sidecars. Text coherence needs human review.
Optional SDK joules are raw data, not a validated energy result.

## Status (2026-09-24)

Every number so far is **smoke only on a non-quiet host**: Mac Studio M4 Max
128 GB, macOS 27.0 / Xcode 27 RC. Qwen3 MLX 0.6B/1.7B/4B and bf16 0.6B/1.7B
produced coherent English. Some answers reach the token cap; coherence does
not establish factual quality. The published 0.8B reference passed; 4B is untested.
Gemma E2B bf16 passed a smoke check; Qwen3-4B bf16 remains pending.
Gemma E4B bf16 is deferred for size. Gemma E2B/E4B 4-bit specs are absent:
those slots need a supported pre-quantized source/importer or documented
upstream quantizer. Pending rows retain `exclude=` reasons in the cells file.
The first admitted session needs a quiet host. Long-context, numerical parity
and warm-session gates remain open; captures from separate sessions are not pooled.

## Run one cell

Stage the prepared export under `UZU_MODEL_DIR`; `file=` is relative to it.
`local=1` skips HF catalog preflight for a side-loaded export. Install the
pinned SDK and `jsonschema` in a venv; provide device/snapshot objects in
`UZU_HOST_INFO`. `UZU_CACHE_DIR` contains the harness's private caches.

```bash
export UZU_PYTHON="$PWD/.venv-uzu/bin/python" UZU_MODEL_DIR="$PWD/models/uzu"
export UZU_CACHE_DIR="$PWD/.cache/uzu" UZU_HOST_INFO="$PWD/host.json"
"$UZU_PYTHON" scripts/uzu_mac.py --model-path "$UZU_MODEL_DIR/Qwen3-0.6B-lalamo-d1cfe68e-bfloat16-uzu0.5.30-sdk" \
  --recipe lalamo-d1cfe68e-bfloat16-default --sdk-store normal --task short-chat --thinking off \
  --runs 1 --pause 0 --host-info "$UZU_HOST_INFO" --sample-load --output results/raw/local-uzu-smoke/uzu.jsonl
```

Add `--dry-run` to inspect the engine call. Matrix rows dispatch through
`bench_matrix_mac.sh`. Registry models use the SDK downloader and must reach
`Downloaded` before local execution; cloud execution is refused. The default
SDK store is private; `--sdk-store normal` uses its usual home model store.
Exports, venvs and caches are local artifacts, excluded from source control.
