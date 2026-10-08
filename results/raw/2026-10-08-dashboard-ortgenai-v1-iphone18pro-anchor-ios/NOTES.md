# 2026-10-08-dashboard-ortgenai-v1-iphone18pro-anchor-ios — notes

The session anchors of the iPhone 18 Pro sitting of the ONNX Runtime GenAI arm (campaigns
`2026-10-08-dashboard-ortgenai-v1-iphone18pro-{a,b,c}-ios`): the ios rows of `matrices/anchors.cells`
(MLX and LiteRT-LM, Qwen3 0.6B short-chat, runs 3), 17:17:42–17:19:42 JST, both cells gate OK.

Phone: iPhone 18 Pro (iPhone19,2), iOS 27.2 (24B5099f), UDID `00008160-000038CA02C00036`, USB.
App `com.example.CoreMLLLMChat` 0.2.0 (1): the BenchmarkApp Release build of commit a9fa7b5
(branch ortgenai-arm; its iOS sources are ddd7e42's), main binary sha256 `4b95fa387c3fb277…`, installed
at 17:14:46 JST. The anchors' engines in it are the pinned ones the phone's installed build carries:
LiteRT-LM v0.16.0 (`CLiteRTLM.xcframework.zip@v0.16.0 sha256:4e0f683d…`; the embedded framework is
byte-identical, signature aside, to the pinned build's) and mlx-swift 60bd0d78. After the sitting the
phone's pinned build (main binary sha256 `6564d5b7…`) was installed again (18:27:22 JST).

Not a dashboard-job sitting: no SESSION.json. Command, inside the iPhone hold:
`CAMPAIGN=2026-10-08-dashboard-ortgenai-v1-iphone18pro-anchor-ios BENCH_UDID=00008160-000038CA02C00036
APP=com.example.CoreMLLLMChat CELL_TIMEOUT=1200 scripts/bench_matrix_iphone.sh run matrices/anchors.cells`
(BASE_COOLDOWN 100, THERMAL_COOLDOWN 240, SERIOUS_COOLDOWN 600 defaults). The ORT 0.6B smoke launch that
fetched the model folder (one short-chat run, not a record here) ended 150 s before the first anchor.
