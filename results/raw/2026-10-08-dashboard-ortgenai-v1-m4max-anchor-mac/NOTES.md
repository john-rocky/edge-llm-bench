# 2026-10-08 session anchor for the ONNX Runtime GenAI dashboard cells, Mac Studio M4 Max (round r4-mac)

The two rows of `matrices/anchors.cells` (MLX `mlx-community/Qwen3-0.6B-4bit` and LiteRT-LM
`litert-community/Qwen3-0.6B`, short-chat, 3 runs each), run first in the Mac quiet window of the sitting
(lock label `ortgenai-r4-mac-1 ortgenai-r4-mac-2`, 2026-10-08 23:33:41 – 2026-10-09 00:07:47 JST; this campaign
23:34:22–23:34:59), before `../2026-10-08-dashboard-ortgenai-v1-m4max-1-mac` and
`../2026-10-08-dashboard-ortgenai-v1-m4max-2-mac`.

- yardstick: a Release build of this repository's yardstick (`.build/dd-mac`, built 2026-09-18) with LiteRT-LM
  v0.16.0 (its libCLiteRTLM_mac.dylib = the one in the official CLiteRTLM_mac.xcframework.zip v0.16.0,
  sha256 3ae6c876…) and mlx-swift-lm 60bd0d78…. `engine-pins-dd-mac-v0160.json` here = the pins file the run read
  (BENCH_ENGINE_PINS_FILE), stamped from the v0.16.0 tree the binary was built from: the checkout's
  `Vendored/engine-pins.json` had already moved to v0.18.0, which this binary does not carry.
- Machine state: the Xcode GUI app used about half a CPU core through the window (61.4 % at 23:34);
  mediaanalysisd was stopped (state T, 0 % CPU) by another session before the window; load1 6.1 at 23:34.
  The window's quiet bar: see `../2026-10-08-dashboard-ortgenai-v1-m4max-1-mac/NOTES.md`.
