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

1. **The LFM2.5-VL vision encoder does not compile on Metal at this commit.** Both `_int4_fixB`
   bundles (450M, 1.6B) fail in `VisionLiteRtCompiledModelExecutor` before any token: the GPU
   delegate rejects one `RESIZE_BILINEAR` ("Expected 1 runtime input tensor(s), but node has 0") and
   two more ops, and the vision executor compiles with the GPU accelerator only, so "Some ops are
   not accelerated" is fatal (`logs/…LFM2_5-VL-450M…gpu_run1.stderr.log`; the 1.6B also logs a
   Metal buffer-alignment validation error). The card's "GPU with litert-lm ≥ 0.16.0
   (macOS/Android OpenCL)" was measured through the pip CLI, whose vision backend may not have
   been the GPU; here the protocol is arm identity (vision on the same backend as the text model),
   so the row is a FAIL, not a CPU-vision fallback. A `--vision_backend=cpu --backend=gpu` probe
   is the diagnosis to run next, not a cell.
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
the published sha256, so they were not used), MiniCPM-V-4 (4.2 GB, not downloaded), the GPU
arms with a CPU vision encoder (a probe, see finding 1), the `int8` recipes, multi-image.
