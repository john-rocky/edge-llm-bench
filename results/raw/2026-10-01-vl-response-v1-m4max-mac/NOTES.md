# 2026-10-01 vision-language response time v1 — Mac leg, InternVL3-1B and Qwen2-VL-2B: numbers and findings

Definition: `docs/vl-response-v1.md`. Identities (engine build, dylibs, model files, image, host):
`PROVENANCE.md`. Records: one JSONL per cell (three process launches each), engine stderr and the
reply per launch under `logs/`. Session 19:24:48–19:29:04 JST; anchor (MLX Qwen3-0.6B short-chat)
warm median 552.6 tok/s, 0.988 of the 2026-09-24 VL leg's anchor (not throttled). These are the
two rows that were SKIPPED on 2026-09-24 (bundle not staged); the other four models' rows are in
`results/raw/2026-09-24-vl-response-v1-m4max-mac/NOTES.md`. The two sittings are separate
sessions: read rows across them through their anchors, never as one pool.

## The table (LiteRT-LM `main@1dadd00c` `litert_lm_advanced_main`, one 1024×682 CC0 photo + "Describe this image in one sentence.", ≤ 64 output tokens)

Columns as on 2026-09-24. Response s = request marker → last reply byte (vision encoder + prefill +
decode), **median of 3 launches, range in brackets**. TTFT = the engine's own time to first token
(prefill of the image + prompt tokens plus the first sampled token; it does not include the vision
encoder). Vision enc ms = BenchmarkInfo `Mark Durations` → `vision_executor` (`vlMarkDurationsMS`),
median. Load s and peak RSS: median over the three launches. GPU arm = LiteRT's WebGPU accelerator
(Dawn on Metal), as on 2026-09-24 (`conditions.gpuAccelerator`).

| model (litert-community) | file | arm | response s | TTFT s | vision enc ms | prefill tok @ tok/s | decode tok @ tok/s | load s | peak RSS MB | text check |
|---|---|---|---|---|---|---|---|---|---|---|
| InternVL3-1B | `InternVL3-1B.litertlm` | litert-lm-cpu | **1.000** [0.991–1.025] | 0.44 | 328 | 311 @ 736 | 19 @ 78.7 | 0.18 | 1,036 | passes ("The image shows a close-up of a tabby cat lying on a dark fabric surface.", byte-identical ×3) |
| InternVL3-1B | same | litert-lm-gpu | — | — | — | — | — | — | — | **FAILS** at vision-encoder compile (exit 13, ×3): `BROADCAST_TO: Operation is not supported.` + `GATHER_ND: Operation is not supported.` → `Some ops are not accelerated` |
| Qwen2-VL-2B | `Qwen2-VL-2B.litertlm` | litert-lm-cpu | **4.557** [4.548–4.560] | 2.42 | 1,711 | 605 @ 254 | 14 @ 31.1 | 0.57 | 3,061 | passes ("A gray and white cat is lying on a dark gray couch.", ×3) |
| Qwen2-VL-2B | same | litert-lm-gpu | **1.070** [1.061–1.719] | 0.32 | 593 | 605 @ 1,951 | 19 @ 115.5 | 1.00 | 1,154 | passes ("A cute tabby cat is lying on a gray couch, looking up at the camera.", ×3) |

Recipes (`model.quantization`, from each repo's `litertlm_manifest.json`): InternVL3-1B — decoder
Qwen2.5-0.5B int4 blockwise-32 OCTAV, int8 embedding (externalized), vision encoder + pixel-shuffle
+ MLP projector int8; Qwen2-VL-2B — decoder int4 blockwise-32 OCTAV, vision encoder int8, adapter
int8, int8 externalized embedder.

Check: vision enc + prefill + decode equals the response seconds minus 5.6–7.7 ms in all 9 passing
launches (and in the 2 probe launches), as on 2026-09-24 (6–9 ms; catalog X29).

Spread: both CPU cells repeat within ±3 % (InternVL3-1B launch 3 +2.5 %). The Qwen2-VL GPU cell's launch 1 is +61 % (1.719 vs
1.061 / 1.070); finding 3. Foreign load: InternVL3-1B GPU launches had `mds_stores` 88 %,
`duetexpertd` 22–63 % and `spindump` 90 % around them (the cell fails at compile either way);
Qwen2-VL GPU launches 2–3 ran next to a Chrome renderer at 80–86 % and Chrome at 22–24 %; every
other launch saw no foreign process ≥ 20 %. Thermal nominal and no CPU speed limit at every launch.

## Findings

1. **InternVL3-1B's GPU row fails on the Mac as on the S26, on the same two ops.** Each GPU launch
   logs `ERROR: Following operations are not supported by GPU delegate: BROADCAST_TO … GATHER_ND`,
   `1307 operations will run on the GPU, and the remaining 13 operations will run on the CPU.`,
   then LiteRT-LM's vision executor ends the engine with `Some ops are not accelerated. Add
   kLiteRtHwAcceleratorCpu to the compilation accelerator set …`
   (`vision_litert_compiled_model_executor.cc:312`; `logs/*InternVL3-1B*gpu_run1.stderr.log`
   lines 126–135). The op count and the two op names equal the S26 OpenCL leg's finding 3
   (`results/raw/2026-09-26-vl-response-v1-s26-android/NOTES.md`), so the refusal is the GPU
   delegate's op coverage on both the WebGPU and the OpenCL path, not one backend's; the engine's
   `kGpu`-only vision compile turns 13 CPU-capable ops into a fatal error, as in the LFM2.5-VL
   rows of 2026-09-24 (finding 1 there). Each of the three GPU launch logs also carries one Dawn
   validation error, `Buffer size (67954944) wrapping host-mapped memory was not aligned to 4096.`
   (line 97, before the vision compile); not followed further.
2. **Qwen2-VL-2B runs on the Mac GPU path end to end, with every stage faster than on the CPU.**
   Vision encoder 1,711 → 593 ms (0.35×), prefill of the 605 image + prompt tokens 254 → 1,951
   tok/s, decode 31.1 → 115.5 tok/s, response 4.557 → 1.070 s; the replies differ (14 vs 19
   tokens, both pass). The bundle's vision executor reports `num_tokens_per_image: 576` on both
   arms. On the S26's OpenCL path the same bundle's vision encoder was slower on the GPU than on
   the CPU (S26 NOTES finding 5, catalog X30); on this Mac's WebGPU path it is not.
3. **The Qwen2-VL GPU cell's launch 1 is slow in the encoder and in decode, and only on a cold cache
   dir.** Launch 1 (the first launch of this bundle on this Mac, `--cache_dir` empty; load 1.95 s,
   `Init Executor` 1,287 ms): vision encoder 771 ms and decode 30.2 tok/s, against 581 / 593 ms
   and 115.5 / 118.1 tok/s in launches 2–3; prefill is the same (1,942 vs 1,951 tok/s). Two more
   launches a minute later with the cache in place (`probes/qwen2vl-gpu-warmcache/`, not a cell)
   both came out like launches 2–3: 1.074 / 1.077 s, decode 118.0 / 115.2 tok/s — the first of
   them next to a Chrome renderer at 90 % and `bird` at 38 %. So the slow launch is the
   first-ever launch, not the first launch of a cell; whether the weight / program cache build or
   the first read of the 1.8 GB file is what costs it is not separated here (both were cold
   together). The median stands; launch 1 is what an app's first VL request after install would
   see. The 2026-09-24 Gemma 4 GPU cell showed a slow launch 1 too (NOTES there, "Spread").
4. **Qwen2-VL-2B is the heaviest per-image prefill of the six models:** 605 tokens (576 image +
   prompt) against 82–311 for the others, so its CPU TTFT (2.42 s) is 2.4 s of a 4.56 s answer,
   and its CPU arm holds 3.1 GB resident (launch 1, with the cache build, 4.6 GB).
5. **InternVL3-1B's CPU row**: vision encoder 328 ms + prefill of 311 tokens 0.42 s + 19 decode
   tokens 0.24 s = 1.00 s per image; load 0.18 s with the cache in place (2.03 s for the launch
   that built it).

Not run this sitting: MiniCPM-V-4 (not downloaded), the Metal accelerator as a separate GPU arm
(a runner dir without the WebGPU dylibs — the S26 leg handoff's item 9), the `int8` recipes,
multi-image.
