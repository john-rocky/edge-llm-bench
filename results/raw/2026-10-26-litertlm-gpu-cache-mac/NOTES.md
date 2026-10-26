# Qwen3.5-0.8B GPU program cache on a Mac: 10 of 12 programs fail to load (LiteRT-LM #4178)

2026-10-26 20:47–20:53 JST, Mac Studio (Apple M4 Max, macOS 27.0 26A428), inside the Mac measurement window.
Python 3.12 in uv venvs with `litert-lm-api==0.18.0`, `litert-lm-api==0.18.1` and `litert-lm-api-nightly==0.19.0.dev20261022`
(PyPI). Model: litert-community/Qwen3.5-0.8B `Qwen3.5-0.8B_int8.litertlm`, revision 0cd9e7a6 (the same bytes as ff11c109, the
revision named in #4178): sha256 `25447e2550082aed6145bbc755ec4da5d535f98f6a0c386865fdae2ccb88aed1`, 964,566,992 bytes.

Per build: an empty cache dir; process 1 makes one call, process 2 makes two calls, each call =
`litert_lm.Benchmark(model, backend=litert_lm.Backend.GPU(), prefill_tokens=1024, decode_tokens=32, max_num_tokens=2048,
cache_dir=<dir>).run()` (`run_one.py`, driver `run_all.sh`). The GPU path on macOS is WebGPU (`Initializing WebGPU-based API`).
`SUMMARY.txt` is `summarize.sh` over `logs/`. The user name in the logs' file listings is replaced by USER.

| build | process 1, s | process 2, calls 1 / 2, s | cache loads failed per call in process 2 | program cache after process 1 → after process 2, bytes |
|---|---|---|---|---|
| 0.18.0 | 49.09 * | 44.81 / 45.98 | 10 of 12 | 539,049,304 → 1,598,383,896 |
| 0.18.1 | 47.25 | 48.96 / 47.25 | 10 of 12 | 539,049,304 → 1,598,383,896 |
| 0.19.0.dev20261022 | 31.96 | 29.80 / 28.82 | 10 of 12 | 539,450,152 → 1,599,599,256 |

s = one `run()` (engine creation, 1,024-token prefill, 32 decoded tokens), by `time.monotonic()` in the process.
Every failure prints `Deserialization failed: DATA_LOSS: Deserialization failed.` with `third_party/ml_drift/webgpu/inference_context.cc:187`.
In each call the first 10 loads fail and the last 2 succeed; the Mac log does not name the subgraphs.
The program cache file grows by about 530 MB per call in process 2 (the weight cache file stays at 751,324,472 bytes).

`s26-v0180-signature-outcomes.txt`: the Galaxy S26 (OpenCL) launch of 2026-10-24 with LiteRT-LM v0.18.0, whose console names
each subgraph: prefill_1024 … prefill_2 (16,775–25,703 delegated nodes) fail at `ml_drift/cl/inference_context.cc:297`,
prefill_1 (2,070 nodes) and decode (2,124 nodes) load. The iPhone 17 Pro (Metal) consoles are linked from #4178.

\* Another lane's SwiftPM clone (git pack indexing, CPU) may have overlapped 20:47:08–20:47:45, the first 37 s of 0.18.0's
process 1 (it started before the window, without the quiet wait; reported by that lane at 21:0x). Only that wall time can be
affected; every later run fell in 20:47:45–20:53:23, when that lane only downloaded (git-lfs, about 1 % CPU). The counts and
file sizes do not depend on CPU load.
