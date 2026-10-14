# LiteRT-LM console fixtures (android/bench/selftest.py)

LiteRT-LM v0.18.0's console output for the parser checks of `android/bench/parsers.py`
(the forms per path and release: its module doc). Excerpts from `===ENGINE_OUTPUT===` to
the end of the stored launch log, verbatim; not measurements of record.

| file | what |
|---|---|
| `pixel8a-v0.18.0-gpu-qwen3-0.6b-long-context-1024-gen256.console.txt` | Pixel 8a, 2026-10-14 16:36 UTC, `litert_lm_advanced_main` v0.18.0 (`--num_iterations=2 --benchmark --benchmark_prefill_tokens=0`), GPU, litert-community/Qwen3-0.6B `qwen3_0_6b_mixed_int4`, the 1K text task at `--max_num_tokens=2048`: two `BenchmarkInfo:` on glog lines, the `Captured model output:` echo before each, the `Aggregated BenchmarkInfo` block after the second. The bundle's chat template dropped the user turn under v0.18.0 (9 prompt tokens, an off-task reply), so this is a parser fixture, not a valid 1K run. Source log sha256 70fbaf25…fc61b in `results/raw/2026-10-15-dashboard-v1-pixel8a-0180-p2b-android/app-path-android/` |
| `pixel8a-v0.18.0-gpu-qwen3-0.6b-short-chat.console.txt` | the same phone, 16:04 UTC, `litert_lm_main` v0.18.0, GPU, the same bundle, short-chat: one column-zero `BenchmarkInfo:` (the user turn dropped here too). Source log sha256 d7342818…9ff5c in `results/raw/2026-10-15-dashboard-v1-pixel8a-0180-p1-android/app-path-android/` |
| `synthetic-v0.18.0-gpu-native-benchmark-1024x256.console.txt` | synthetic: the protocol path's form as `runtime/engine/litert_lm_lib.cc` v0.18.0 prints it (one glog-prefixed `BenchmarkInfo:`, no reply, no aggregate), made-up values; replace with a measured log |
