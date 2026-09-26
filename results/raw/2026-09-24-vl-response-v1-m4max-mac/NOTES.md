# 2026-09-24 vision-language response time v1 — Mac leg, first cell: numbers and findings

Definition: `docs/vl-response-v1.md`. Identities (engine build, dylibs, model files, image, host):
`PROVENANCE.md`. Records: one JSONL per cell (three process launches each), engine stderr and
the reply per launch under `logs/`. Session 13:21:34–13:32:52 JST plus the Gemma 4 re-take
14:01:19–14:02:53; anchor (MLX Qwen3-0.6B short-chat) warm 559.6 tok/s, 2 % above the 527–550
band of the last five Mac sessions (not throttled).

## The table (LiteRT-LM `main@1dadd00c` `litert_lm_advanced_main`, one 1024×682 CC0 photo + "Describe this image in one sentence.", ≤ 64 output tokens)

Response s = request marker → last reply byte (image encoding + prefill + decode), **median of 3
launches, range in brackets**. TTFT = the engine's own time to first token. Prefill tokens =
image tokens + prompt; decode tokens = what the model produced before end-of-turn or the cap.

| model (litert-community) | file | arm | response s | TTFT s | prefill tok @ tok/s | decode tok @ tok/s | load s | peak RSS MB | text check |
|---|---|---|---|---|---|---|---|---|---|
| SmolVLM2-500M | `SmolVLM2-500M.litertlm` | litert-lm-cpu | **0.975** [0.972–0.991] | 0.19 | 82 @ 465 | 64 (cap) @ 95.5 | 0.16 | 830 | passes ("A close-up photograph of a tabby kitten, lying on a dark fabric surface…", runs to the 64-token cap) |
| SmolVLM2-500M | same | litert-lm-gpu | 0.149 [0.148–0.740] | 0.00 | 82 @ 46,000 | 64 @ 759 | 0.47 | 255 | **FAILS** — 64 × `<|endoftext|>` on all three launches; the rates are not a measurement |
| LFM2.5-VL-450M | `LFM2.5-VL-450M_int4_fixB.litertlm` | litert-lm-cpu | **0.599** [0.586–0.673] | 0.33 | 276 @ 870 | 15 @ 105 | 0.34 | 962 | passes ("A kitten is laying on a couch with its eyes wide open.", byte-identical ×3) |
| LFM2.5-VL-450M | same | litert-lm-gpu | — | — | — | — | — | — | **FAILS** at vision-encoder compile (exit 13, ×3): `RESIZE_BILINEAR … not supported by GPU delegate` → `Some ops are not accelerated` |
| LFM2.5-VL-1.6B | `LFM2.5-VL-1.6B_int4_fixB.litertlm` | litert-lm-cpu | **1.586** [1.583–1.590] | 0.97 | 276 @ 290 | 9 @ 44.9 | 1.05 | 1,868 | passes ("A cat is laying on a couch.", ×3) |
| LFM2.5-VL-1.6B | same | litert-lm-gpu | — | — | — | — | — | — | **FAILS**, same compile error as the 450M |
| Gemma 4 E2B it | `gemma-4-E2B-it.litertlm` (wNa8o8) | litert-lm-cpu | **1.961** [1.936–2.862] | 0.65 | 280 @ 446 | 24 @ 41.7 | 0.23 | 3,137 | passes ("…intense gaze of a tabby cat resting on a dark, textured surface.", ×3) |
| Gemma 4 E2B it | same | litert-lm-gpu (Metal) | **0.413** [0.402–0.654] | 0.07 | 280 @ 4,380 | 24 @ 141 | 0.50 | 775 | passes ("…captivating eyes and fur of a tabby kitten resting on a dark, textured surface.", ×3) |
| InternVL3-1B, Qwen2-VL-2B | — | both | SKIPPED | | | | | | bundle not staged (`SKIPPED.txt`; PROVENANCE.md "Models") |

Reading: the three LFM / Gemma CPU rows carry the same 276–280 image+prompt tokens, so their
TTFT column is the vision-encoder + prefill cost of one image on the CPU (0.33 s → 0.97 s → 0.65 s
for 0.45 B → 1.6 B → Gemma 4 E2B); SmolVLM2's 64 image tokens make its 0.19 s. The response
column additionally depends on how much each model chose to say (9 to 64 tokens) — compare
TTFT and the per-token rates before the response seconds.

Erratum (2026-09-26): the engine's TTFT does not include the vision encoder, so the first
sentence of the reading above is wrong, and finding 4's per-image cost needs the vision encoder
added to TTFT. TTFT is the prefill of the image + prompt tokens plus the first sampled token.
The vision encoder runs before it on its own clock, BenchmarkInfo `Mark Durations` →
`vision_executor`, which these records do not carry. Medians from each launch's
`logs/*.stderr.log`: SmolVLM2-500M CPU 122.6 ms, LFM2.5-VL-450M CPU 133.1 ms, LFM2.5-VL-1.6B
CPU 429.9 ms, Gemma 4 E2B CPU 748.4 ms (launch 1: 1,030.7 ms), Gemma 4 E2B GPU (Metal) 169.3
ms. The response column does include it: `vision_executor` + prefill + decode equals the
response seconds minus 6–9 ms in all 15 passing launches of these cells. The table's numbers
stand as written (`docs/vl-response-v1.md`; the S26 leg's NOTES.md finding 4).

Spread: the CPU cells repeat within ±1 % except two single launches — LFM 450M launch 1
(+12 %: `Finder` / `Storage` / `cmux` at 20–25 % each at launch) and Gemma 4 CPU launch 1 (+46 %:
a Chrome renderer at 79 % plus five processes at 20–33 %). Gemma 4 GPU launch 1 is +58 % in both
attempts (0.654 / 0.913 vs 0.40): its TTFT is 0.16–0.18 vs 0.07 and prefill 1,600–1,900 vs 4,400
tok/s — the first process after the model is (re)loaded pays a Metal program/warm-up cost the
later launches do not; the median stands, the first-launch number is what a cold app would see.
The Gemma 4 pair was re-taken because the first attempt ran under another session's Xcode build
(`swift-frontend` / `clang` at 100 % on three cores; kept as `.jsonl.attempt1`); the re-take's runs
2–3 agree with the first attempt's clean launches within 3 % on both arms. The host was never
quiet in the strict sense this afternoon (`Storage` extension and Chrome renderer bursts on most
launches; PROVENANCE.md "Host") — every launch's foreign-process list is in its record.

## Findings

1. **The LFM2.5-VL vision encoder does not compile on any GPU delegate, because the export
   carries a `RESIZE_BILINEAR` over a constant tensor** — it is a property of the bundles, not of
   Metal or of this commit. Both `_int4_fixB` files and the stock `LFM2.5-VL-450M_int4` fail the
   same way (`probes/`, four controls, 14:5x JST): text on Metal + vision on the CPU **works**
   (TTFT 0.06 s, "A kitten with brown eyes is laying on a gray couch."), text on the CPU + vision
   on Metal fails identically, so the vision encoder is the single failing component; the released
   pip CLI 0.17.1 reproduces it with `--vision-backend gpu` and, with no vision flag, silently runs
   the vision encoder on the CPU (the bundle's configured value) — which is what the card's macOS
   "GPU" rows and the Android GPU rows measured (litertlm-convert `lfm25vl_work/RESULTS.md`,
   2026-08-13: the same encoder refused the Pixel 8a OpenCL delegate, Mac Metal 2.1.6 and the
   CLiteRTLM-mac runtime; "text-GPU + vision-CPU cascade"). The op: litert-torch's
   `model_ext/lfm2_vl/patch.py` `resize_positional_embeddings` bilinear-interpolates the SigLIP2
   position-embedding table to the fixed 512-pixel patch grid inside the traced graph, so the
   `.tflite` holds a resize whose only input is a constant; the GPU delegate's
   `CheckInputsOutputs` demands one runtime input (`model_builder_helper.cc:218-225`,
   "Expected 1 runtime input tensor(s), but node has 0"), and LiteRT-LM's vision executor compiles
   with `HwAccelerators::kGpu` alone (`vision_litert_compiled_model_executor.cc:259`; the NPU path
   adds `kCpu`), so "Some ops are not accelerated" ends the engine instead of running three ops on
   the CPU. Under this task's arm identity the row is a FAIL; the fix is on the export side
   (constant-fold the resize — the target size is fixed). **Done and verified the same afternoon**
   (`probes/`, second set, 15:1x JST): a litert-torch branch that precomputes the table from the
   loaded weights (john-rocky/litert-torch `lfm2vl-fold-pos-resize`, PR pending) re-exports the
   450M with no `RESIZE_BILINEAR` (634 → 629 ops), the folded torch path equals the unfolded one
   bit for bit, the exported fp32 encoder matches the torch reference at cosine 1.0000000
   (max |diff| 8.4e-4 folded, 4.4e-4 unfolded; the int8 recipe sits at 0.9917 either way), and
   the bundle now **compiles and runs with the vision encoder on Metal** (LiteRT-LM main@1dadd00c
   and the pip CLI 0.17.1 alike; `probes/lfm450m_fold-int8_text-gpu_vision-gpu.stderr.log`,
   `probes/pip0171_lfm450m_fold-int8_text-gpu_vision-gpu.stdout.txt`).
   What it exposes next — bisected the same evening (`probes/metal-bisect/`, prefix graphs rebuilt op by
   op and run on CPU vs Metal through `ai_edge_litert` CompiledModel): the Metal *output* of the
   folded encoder is wrong at **op 1**, the very ADD that adds the folded table — the converter emits
   it as `ADD(runtime [1024, 768], constant [1, 1024, 768])` (it drops the FC's batch dim and pushes
   the reshape into the constant, whatever rank the table has in torch), and the Metal delegate
   computes that rank-mismatched add wrong: cosine 0.818 against the CPU on the two-op prefix, the
   same with `enforce_f32`, while the identical add with a RESHAPE inserted (rank-3 + rank-3), a
   rank-4 pair, or the table fed as a runtime input all agree (1.000000 in fp32). Every later op is
   fine: the full encoder with the table fed as an input matches the CPU at cosine 1.000000 in fp32
   (0.83 under the Python API's default fp16, a precision drift the engine does not show). Proof
   through the engine: the same bundle repacked with that one RESHAPE captions the cat correctly on
   Metal at default settings ("A close up of a kitten with its ears perked up", TTFT 0.05 s) — so
   for LFM2.5-VL on Metal the converter fold plus a delegate fix for the rank-mismatched constant
   ADD is the whole distance. Filed 2026-09-24 15:57 JST: the converter fold as google-ai-edge/litert-torch#1260 and the
   delegate miscompute as google-ai-edge/LiteRT#10231 (repro assets:
   github.com/john-rocky/edge-llm-bench/releases/tag/metal-add-repro-2026-09-24; the script's
   random input reads cosine 0.59, the image input 0.818). A post-export RESHAPE insertion is the
   convert lane's interim for the published bundles.

2. **SmolVLM2-500M on Metal returns only end-of-text tokens** — the same failure the card reports
   for litert-lm 0.15.0, still present on `main@1dadd00c`: the engine runs (TTFT 0.00 s, 46,000
   "tokens/s" prefill, 64 decode steps at 759 tok/s) and prints 64 × `<|endoftext|>`. A textbook
   benchmark-mode number without a text check (benchmark-mode-needs-a-text-check).
3. **Gemma 4 E2B is the one bundle whose GPU arm passes**: 0.41 s per image on Metal vs 1.96 s on
   the CPU, TTFT 0.07 vs 0.65 s, prefill 4,380 vs 446 tok/s, decode 141 vs 42 tok/s; the GPU arm
   also holds 775 MB resident against 3.1 GB on the CPU (weights stay in the GPU heap). Its 280
   image tokens at 1024×682 input (`vision_280` signature; the bundle also carries `vision_70` /
   `vision_140`) are the engine's default `visual_token_budget`.
4. **Reply length drives the response column.** Under the same 64-token budget SmolVLM2 talks to
   the cap (64 tokens), Gemma 4 uses 24, LFM 450M 15 and LFM 1.6B 9 — the 1.6B answers in six words
   and its 1.59 s is 61 % TTFT. Readers who want a per-image cost independent of verbosity should
   take TTFT plus decode tok/s.
5. **Load is small for these bundles** (0.16–1.05 s with a warm XNNPACK weight cache; the first
   launch of each cell pays 0.1–0.4 s more) — the per-image cost, not model load, is the number an
   app feels for a VLM of this size on this Mac.

Not run this sitting: InternVL3-1B and Qwen2-VL-2B (the Hub throttled downloads to ~0.2 MB/s
from this host all afternoon; the archived local copies were earlier exports and did not match
the published sha256, so they were not used), MiniCPM-V-4 (4.2 GB, not downloaded), the `int8`
recipes, multi-image. `probes/` holds the four vision-backend controls and the three pip-CLI
runs behind finding 1 (n=1 each, not cells).
