# 2026-09-26 vision-language response time v1 — Galaxy S26 leg: numbers and findings

Definition: `docs/vl-response-v1.md` (section "Android leg"). Identities (CLI build, GPU
libraries, model files, image, phone): `PROVENANCE.md`. Records: one JSONL per cell, three
process launches each; the engine's stderr stream and the stdout (reply) of every launch are
under `logs/`, the driver's log is `runlog.txt` (= `logs/driver_sitting1.log`). Same engine
commit, image, prompt, budget and CLI flags as the Mac leg (`../2026-09-24-vl-response-v1-m4max-mac/`),
the CLI built for `android_arm64`.

Sitting: driver 09:47:40–10:26:56 JST (bundle pushes and on-phone sha256 checks
09:47:41–09:50:57, first launch 09:50:57), 12 cells × 3 launches = 36 records, no re-take, no
`.attempt1`. Session anchor right before it, 09:35:43–09:46:15
(`../2026-09-26-vl-response-v1-s26-anchor-android/`): llama.cpp b8999 Qwen3-0.6B-GGUF
short-chat decode 108.0 / 107.0 / 110.7 tok/s, median 108.0 against the reference 106.3
(n = 6, `2026-09-24-dashboard-longctx-v1-s26-android-gpu-retake`), ratio 1.016 — ADMITTED
under the dashboard's rule (`scripts/dashboard_job.py` `admit()`; `SESSION.json` here and in
the anchor dir).

Protocol: 45 s between launches; 90 s before cells 2–6 and 60 s before cells 7–12 (the
`cooldown=60` of the LFM2.5-VL-1.6B, Qwen2-VL-2B and Gemma 4 rows). Gate before every launch:
thermal status 0 and battery ≤ 36.0 °C; it never had to wait. Thermal status was nominal
before and after all 36 launches; battery 30.9–35.0 °C, charging over USB at 94–95 %. No CPU
frequency cap before any launch. After 11 launches the driver read `scaling_max_freq` below
`cpuinfo_max_freq` on at least one policy (LFM2.5-VL-1.6B GPU launch 1, all six Qwen2-VL-2B
launches, the three Gemma 4 CPU launches, Gemma 4 GPU launch 1); the record keeps the flag
(`provenance.deviceAfter.cpuFreqCapped`), not the value, and every next launch started uncapped.

**Screen: off.** All 36 launches ran with `provenance.deviceBefore.wakefulness = "Dozing"`
and `stay_on_while_plugged_in = 0`. The device page's protocol says screen on
(`devices/galaxy-s26.md`), and the records' `conditions.screen: "on-usb"` is that protocol
text, which the driver stamped without reading the phone. The records stay as written; the
driver now stamps the measured state (`off-usb (mWakefulness=…)`). The anchor records carry
no screen reading either (`on-usb` is `android/bench/run_cell.py`'s fallback string); the
first reading after them, at 09:47:40, was Dozing. The anchor admitted the sitting at ratio 1.016.

## The table (LiteRT-LM `main@1dadd00c` `litert_lm_advanced_main`, one 1024×682 CC0 photo + "Describe this image in one sentence.", ≤ 64 output tokens)

Response s = host arrival of the engine's request marker (stderr) → host arrival of the last
reply byte (stdout), both over the same adb connection: vision encoder + prefill + decode.
**Median of 3 launches, range in brackets**; every other column is the median of the same
launches. TTFT = the engine's own time to first token (prefill + the first sampled token; the
vision encoder is outside it, finding 4). Vision encoder ms = BenchmarkInfo `Mark Durations` →
`vision_executor`: from the record's `vlMarkDurationsMS`, or from the stderr log where marked
"(log)" — values of 1 s and more print in seconds (`1.730355468s`), which the driver's parser
did not read at the time of the sitting. Load s = phone clock from exec to the request marker.
Peak RSS = `VmHWM` polled every 0.5 s; the OpenCL arm's GPU heap is not in it.

| model (litert-community) | file | arm | response s | TTFT s | vision encoder ms | prefill tok @ tok/s | decode tok @ tok/s | load s | peak RSS MB | text check |
|---|---|---|---|---|---|---|---|---|---|---|
| SmolVLM2-500M | `SmolVLM2-500M.litertlm` | litert-lm-cpu | **1.470** [1.464–1.756] | 0.29 | 292 | 82 @ 294.9 | 64 (cap) @ 72.4 | 1.224 | 875 | passes ("A close-up photograph of a tabby kitten, lying on a dark fabric surface…", runs to the cap) |
| SmolVLM2-500M | same | litert-lm-gpu (OpenCL) | **1.465** [1.447–1.563] | 0.09 | 200 | 82 @ 1115.9 | 64 (cap) @ 54.5 | 2.400 | 468 | passes (same first sentence as the CPU reply, then "…is lying on its side, its eyes wide open…") |
| LFM2.5-VL-450M | `LFM2.5-VL-450M_int4_fixB.litertlm` | litert-lm-cpu | **0.996** [0.986–1.001] | 0.50 | 281 | 276 @ 571.4 | 15 @ 71.4 | 1.324 | 926 | passes ("A kitten is laying on a couch with its eyes wide open.") |
| LFM2.5-VL-450M | same | litert-lm-gpu | — | — | — | — | — | — | — | **FAILS** at vision-encoder compile (exit 13, ×3): `RESIZE_BILINEAR: Expected 1 runtime input tensor(s), but node has 0 runtime input(s).` → `Some ops are not accelerated` |
| InternVL3-1B | `InternVL3-1B.litertlm` | litert-lm-cpu | **1.490** [1.476–1.515] | 0.64 | 558 | 311 @ 495.4 | 19 @ 68.1 | 0.621 | 1,003 | passes ("The image shows a close-up of a tabby cat lying on a dark fabric surface.") |
| InternVL3-1B | same | litert-lm-gpu | — | — | — | — | — | — | — | **FAILS** at vision-encoder compile (exit 13, ×3): `BROADCAST_TO: Operation is not supported.` + `GATHER_ND: Operation is not supported.` → `Some ops are not accelerated` |
| LFM2.5-VL-1.6B | `LFM2.5-VL-1.6B_int4_fixB.litertlm` | litert-lm-cpu | **2.698** [2.577–2.768] | 1.42 | 836 | 276 @ 200.4 | 9 @ 25.5 | 4.396 | 1,835 | passes ("A cat is laying on a couch.") |
| LFM2.5-VL-1.6B | same | litert-lm-gpu | — | — | — | — | — | — | — | **FAILS**, the same `RESIZE_BILINEAR` compile error as the 450M (exit 13, ×3) |
| Qwen2-VL-2B | `Qwen2-VL-2B.litertlm` | litert-lm-cpu | **8.178** [8.093–8.571] | 3.68 | 3,640 (log) | 605 @ 167.6 | 14 @ 15.4 | 2.200 | 3,011 | passes ("A gray and white cat is lying on a dark gray couch.") |
| Qwen2-VL-2B | same | litert-lm-gpu | **7.511** [7.435–7.553] | 0.97 | 5,670 (log) | 605 @ 661.0 | 17 @ 18.4 | 7.135 | 1,033 | passes ("A cute gray and white tabby cat is lying on a dark gray couch.") |
| Gemma 4 E2B it | `gemma-4-E2B-it.litertlm` (wNa8o8) | litert-lm-cpu | **3.347** [3.196–3.942] | 1.04 | 1,583 (log) | 280 @ 276.8 | 24 @ 31.7 | 0.631 | 3,158 | passes ("A close-up photograph captures the captivating, intense gaze of a tabby cat resting on a dark, textured surface.") |
| Gemma 4 E2B it | same | litert-lm-gpu | **1.573** [1.547–1.582] | 0.21 | 477 | 280 @ 1652.3 | 25 @ 28.5 | 3.659 | 888 | passes ("…captivating eyes and soft fur of a tabby kitten resting on a dark, textured surface.") |

The "(log)" values per launch: Qwen2-VL-2B CPU 3,660 / 3,625 / 3,640 ms, GPU 5,695 / 5,556 /
5,670 ms; Gemma 4 CPU 1,730 / 1,449 / 1,583 ms (the `- vision_executor:` line near the end of
each `*.stderr.log`).

Spread: seven of the nine passing cells repeat within max/min 1.081. In SmolVLM2 CPU (1.199)
and Gemma 4 CPU (1.233) launch 1 alone is out; launches 2–3 agree within 0.4 % and 4.7 %, and
the medians stand (finding 8).

## Findings

1. **SmolVLM2-500M produces text on the OpenCL path.** All three GPU launches reply with a
   description that passes the text check. On the Mac the same bundle and engine commit
   return 64 × `<|endoftext|>` on the Mac CLI's GPU path (WebGPU via Dawn on Metal; Mac NOTES finding 2); that failure does not
   reproduce on Adreno.
2. **Both LFM2.5-VL GPU rows fail on Android as on the Mac.** The vision encoder does not
   compile: the GPU delegate rejects a `RESIZE_BILINEAR` with no runtime input ("Expected 1
   runtime input tensor(s), but node has 0"), and the engine stops with "Some ops are not
   accelerated" (`vision_litert_compiled_model_executor.cc:312`). It is the same check and
   the same bundles as on the Mac, where controls located the op in the export (a resize over
   a constant position table; Mac NOTES finding 1). The folded re-export
   (google-ai-edge/litert-torch#1260) has not been run on the S26. The rank-mismatched
   constant ADD that the fold exposes next is computed wrong by the Adreno OpenCL delegate too
   (`../2026-09-26-litert-10231-opencl-control-s26-android/NOTES.md`); through the engine that
   only becomes visible once a folded bundle compiles.
3. **InternVL3-1B's GPU row fails on two ops the GPU delegate does not support**:
   `BROADCAST_TO` and `GATHER_ND` in the vision encoder (exit 13 on 3/3 launches). There is
   no Mac row to compare yet: the bundle was not staged on 2026-09-24 (SKIPPED). It is in the
   HF cache now, so the Mac row is a separate sitting.
4. **TTFT does not include the vision encoder; the response seconds do.** LFM2.5-VL-1.6B CPU:
   TTFT 1.42 s = prefill 1.377 s + one decode step (0.039 s), beside a 0.836 s vision encoder.
   Qwen2-VL-2B GPU: TTFT 0.97 s against a 5.67 s vision encoder. In all 27 passing launches,
   `vision_executor` + prefill + decode equals the response seconds minus 8–26 ms. The vision
   encoder's share of the response seconds runs from 14 % (SmolVLM2 GPU) to 75 % (Qwen2-VL-2B
   GPU). `docs/vl-response-v1.md` and the schema called TTFT "image encoding + prefill"; both
   are corrected, and the Mac NOTES carry an erratum.
5. **Qwen2-VL-2B prefills 605 image + prompt tokens** (276–311 for the other bundles). Its
   vision encoder takes 3,640 ms on the CPU and 5,670 ms on the GPU (1.56×; all 2,119 nodes of
   the encoder graph delegated to OpenCL). On the GPU arm that is 75 % of the 7.51 s; prefill
   goes 3.61 s → 0.92 s and decode 0.91 s → 0.93 s (14 → 17 tokens).
6. **Gemma 4 E2B, CPU → GPU, stage by stage:** vision encoder 1,583 → 477 ms (0.30×), prefill
   276.8 → 1,652.3 tok/s (6.0×), TTFT 1.04 → 0.21 s, decode 31.7 → 28.5 tok/s (0.90×), peak
   RSS 3,158 → 888 MB (host memory only).
7. **Replies repeat exactly.** Each cell's reply is byte-identical across its three launches
   (36/36). The CPU replies of the four models the Mac leg also ran (SmolVLM2, both LFM2.5-VL,
   Gemma 4) are byte-identical to the Mac's CPU replies of 2026-09-24. The GPU replies differ
   from the CPU replies: SmolVLM2 after the first sentence, Qwen2-VL-2B by two added words,
   Gemma 4 in one phrase ("intense gaze of a tabby cat" / "eyes and soft fur of a tabby kitten").
8. **Launch 1 is out in two CPU cells; the cause is not established.** SmolVLM2 CPU launch 1:
   response 1.756 s vs 1.470 / 1.464, vision encoder 391 vs 292 / 291 ms, prefill 201 vs
   296 / 295 tok/s, decode 69.1 vs 72.4 / 72.9 tok/s. Gemma 4 CPU launch 1: response 3.942 s vs
   3.196 / 3.347, vision encoder 1,730 vs 1,449 / 1,583 ms, prefill 255 vs 287 / 277 tok/s,
   decode 21.8 vs 31.7 / 33.0 tok/s. The XNNPACK weight caches do not line up with it: Gemma 4
   launch 1 wrote them and launches 2–3 loaded them, while SmolVLM2 launch 1 loaded existing
   caches and launches 2–3 wrote new ones. In both cells the cache work sits before the
   request marker, inside the load seconds (Gemma 4 launch 1: 3.25 s vs 0.49 / 0.63).

## Not in this sitting

- The folded LFM2.5-VL bundles (litert-torch#1260) on OpenCL; InternVL3-1B and Qwen2-VL-2B
  on the Mac.
- NPU, the `int8` variants, MiniCPM-V-4, a screen-on retake.
