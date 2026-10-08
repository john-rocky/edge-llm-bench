# 2026-10-09 session anchor for the ONNX Runtime GenAI 4B WebGPU retake, Mac Studio M4 Max (round r4-mac)

The two rows of `matrices/anchors.cells` (MLX `mlx-community/Qwen3-0.6B-4bit` and LiteRT-LM
`litert-community/Qwen3-0.6B`, short-chat, 3 runs each), run first in the Mac quiet window `ortgenai-r4-mac-retake`
(2026-10-09 02:25:37–02:37:33 JST; this campaign 02:26:18–02:26:56), before
`../2026-10-09-dashboard-ortgenai-v1-m4max-retake-mac`.

- yardstick and pins: the same binary and `engine-pins-dd-mac-v0160.json` as
  `../2026-10-08-dashboard-ortgenai-v1-m4max-anchor-mac` (its NOTES.md: LiteRT-LM v0.16.0, mlx-swift-lm 60bd0d78…).
- Machine state: the Xcode GUI app used about half a CPU core (42.1 % at 02:26); mediaanalysisd was stopped
  (state T, 0 % CPU) by another session; load1 4.8 at 02:26.
