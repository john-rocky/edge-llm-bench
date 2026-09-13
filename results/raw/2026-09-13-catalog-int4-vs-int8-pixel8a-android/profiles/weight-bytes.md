# Weight bytes per decode token (static, from the bundle)

Read off the `decode` signature of each `.litertlm` with `weight_bytes.py` (beside this file;
`ai_edge_litert` schema): every constant tensor an op consumes, deduplicated by buffer, plus the
scale / zero-point tensors a blockwise-int4 weight references through its quantization details
(they are not op inputs, so a plain input walk misses them). A table read only by
`EMBEDDING_LOOKUP` / `GATHER` is one row per token, not a stream, and is listed apart; a table the
lm-head `FULLY_CONNECTED` also reads (the tied wi4b32 builds) is counted in full. "streamed" is the
bytes-per-token figure the rate rows are set against: streamed MB × decode tok/s = effective GB/s
(weights-over-time, the 2026-07-07 follow-up-4 convention of the Mac K1 row; no DRAM counters).

| file | decode ops | constants total MB | gather-only MB | **streamed MB/token** | of which blockwise scales MB |
|---|---|---|---|---|---|
| `Qwen3-0.6B_dynamic_wi4b32_afp32.litertlm` | 936 | 335.5 | 0.0 | **335.5** | 37.2 |
| `Qwen3-1.7B_dynamic_wi4b32_afp32.litertlm` | 936 | 968.2 | 0.0 | **968.2** | 107.5 |
| `Qwen3_1.7B.litertlm` | 1244 | 1720.9 | 0.0 | **1720.9** | 0.0 |
| `qwen3_0_6b_mixed_int4.litertlm` | 1312 | 491.1 | 155.6 | **335.5** | 37.2 |

- `Qwen3_1.7B.litertlm` (dynamic_wi8_afp32): 197 int8 FULLY_CONNECTED weights, the 311.2 MB
  `[151936, 2048]` lm-head included; the token embedding is external to the graph (tensor names
  say `external_emb`), so no gather table appears. No blockwise side tensors.
- `Qwen3-1.7B_dynamic_wi4b32_afp32.litertlm`: 112 int4 weights + 112 fp16 block-32 scale tensors;
  the `[151936, 2048]` int4 table (155.6 MB + 19.4 MB scales) is read by `EMBEDDING_LOOKUP` and by
  the lm-head `FULLY_CONNECTED`, so it is streamed. int4/int8 bytes per token: 968.2 / 1720.9 = 0.563.
- `qwen3_0_6b_mixed_int4.litertlm`: int4 linears + int4 lm-head (77.8 MB) with fp16 scales; the
  155.6 MB int8 embedding table is gather-only and excluded.
- `Qwen3-0.6B_dynamic_wi4b32_afp32.litertlm`: tied int4 table read by the lm-head; the same
  335.5 MB per token as the mixed build — the 0.6B pair differs in graph and recipe, not in bytes.

Zero-point tensors: none referenced (symmetric blockwise). Per-channel int8 scales live inline in
the tensor's quantization parameters (a few KB per matrix) and are not counted.

Generated 2026-09-13 from the host HF cache blobs (sha256 66064a4e…, 2eeffef7…, b1baab46…, e3e29010…).
Raw walker output: `weight-bytes-*.json`.
