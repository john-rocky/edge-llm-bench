# 2026-10-09-iphone18pro-pin-check-ios — notes

A check, not a measurement campaign (no "dashboard" in the name; the records carry no capture-purpose field
on iOS, so this note says it: smoke). It checks the iPhone 18 Pro's new pinned app build — the one the
weekly job measures — before it replaces the build of 2026-10-07: each runtime loads and prints on-task
text, and the two session anchors land where the 2026-10-08 anchors did.

Phone: iPhone 18 Pro (iPhone19,2), iOS 27.2 (24B5099f), UDID `00008160-000038CA02C00036`, USB.
App `com.example.CoreMLLLMChat` 0.2.0 (1): the BenchmarkApp Release build of bench 50ab482 (iOS sources as
of c05d183), main binary sha256 `042df03a447cde76dab7d7f8bc6bf218536a3ce15af57e9235772ecac8f4f1a7`; engine
pins LiteRT-LM v0.16.0, core-ai 1.0.0-10-gbd3c539, mlx-swift 60bd0d78…, llama.cpp b8999, cactus 1ace6d78,
onnxruntime-genai 0.17.0 (release ios xcframework). Provenance: `docs/dashboard-recurring-job-v1.md` §3.

Commands, inside the iPhone hold (`BENCH_UDID=00008160-000038CA02C00036 APP=com.example.CoreMLLLMChat
CAMPAIGN=2026-10-09-iphone18pro-pin-check-ios scripts/bench_matrix_iphone.sh run <cells>`, BASE_COOLDOWN 100,
THERMAL_COOLDOWN 240, SERIOUS_COOLDOWN 600 defaults), one call per cells file, 100 s between them:

| JST | cells (rows verbatim) | result |
|---|---|---|
| 21:34:36 | `matrices/anchors.cells` (ios: MLX and LiteRT-LM Qwen3 0.6B short-chat, anchor=1 runs=3) | MLX 224.57 / 222.84 / 223.57 tok/s, LiteRT-LM 168.84 / 169.38 / 169.34, gate OK, nominal |
| 21:38:16 | `ios onnxruntime-genai onnx-community/Qwen3-0.6B-ONNX short-chat backend=cpu file=onnxruntime/cpu_and_mobile/cpu-int4-kld-block-128 revision=da1453100cf3ff33ef56d17983fc7a8648706db6 context-tokens=2048` (matrices/dashboard-ortgenai-v1.cells) | 140.44 / 139.77 / 136.58 / 135.16 tok/s, gate OK, nominal |
| 21:40:07 | `ios core-ai core-ai/gemma4-e2b-stock-ctx2048 short-chat backend=ane cooldown=300 context-tokens=2048 runs=3` | no record: `Model load failed: [warmup] nilError` in all three runs |
| 22:00:39, 22:19:41 | `ios core-ai core-ai/gemma4-e4b-stock-ctx2048 short-chat backend=ane cooldown=300 context-tokens=2048 runs=3` | no record: the same error, both calls (the console holds both) |

The anchors' warm medians against `2026-10-08-dashboard-ortgenai-v1-iphone18pro-anchor-ios` (another app build
with the same anchor engines): MLX 223.20 tok/s (2026-10-08: 221.89), LiteRT-LM 169.36 (169.49). The three loading
runtimes' first 200 characters of output answer the short-chat prompt; the ONNX Runtime GenAI launch's
templated prompt sha256 (`9d2fe60d…`) is the one of the 2026-10-08 sitting.

Core AI: neither Gemma 4 bundle loaded, and the build the Core AI arm measured them with on 2026-10-08/09
(main binary `38092491…`, the same Core AI engine) failed the same way on the same phone the same evening (one
launch each of E2B and E4B, not records here). The device log of those loads shows the app reading an entry
of its specialization cache (`received a model already specialized in the cache`) and the Neural Engine
daemon finding no compiled program behind it (`No model at modelFilePath … existsInCache=0`, then `Model load
failed`). Why the compiled programs are gone was not established.

The phone kept the new build (installed 22:21:54 JST).
