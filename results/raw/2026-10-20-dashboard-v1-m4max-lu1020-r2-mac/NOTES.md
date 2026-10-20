# 2026-10-20-dashboard-v1-m4max-lu1020-r2-mac — notes

One dashboard-job sitting on the Mac Studio M4 Max (`Mac16,9`), 2026-10-20 15:11:19–15:24:34 JST, cells
`matrices/lu1020-r2-gemma4e2b-protocol-mac.cells`: the Gemma 4 E2B protocol rows (prefill 1024, decode 256, context 2048)
on the GPU and on the CPU, the CPU row preceded by one cache launch (`native-benchmark-128x16`, runs=1), for the
comparison with the Hugging Face card of `litert-community/gemma-4-E2B-it-litert-lm` (rev 41c55696). Anchor phase
`2026-10-20-dashboard-v1-m4max-lu1020-r2-anchor-mac` admitted (ratio 0.998); this dir's own anchor row 0.986.

Yardstick `.build/dd-mac/Build/Products/Release/yardstick` (built 2026-10-19 10:40, sha256 `5579ae3a…`); `otool -L`
`@rpath/libCLiteRTLM_mac.dylib`, the dylib beside it sha256 `9526db9ee35e7eb4…` = the dylib inside the GitHub release
v0.18.0 `CLiteRTLM_mac.xcframework.zip` (zip sha256 `5f6ee68d…` = the vendored Package.swift checksum), fetched and
compared on 2026-10-20. The sitting ran inside one quiet_hold window (`lu1020-r2-mac`); the job took no window of its
own (the window was the hold's) and its post step held the dir (below).

Native rows. The Mac runner writes no schema-v1 record for a `native-benchmark-*` row: `<cell>.jsonl` holds the
`YARDSTICK_NATIVE_OK` lines (the stored report), one launch per row with `--runs 4` (cache launch: `--runs 1`) =
`benchmark()` calls in one process, run 1 cold (`cold=1`). `app-path-native/` holds the same lines as schema-v1
records, written by `scripts/import_native_benchmark.py --schema-v1` after the sitting (2026-10-20 15:4x JST):
`timestamp` = the launch's start from the runner's `CELL` line (GPU 15:18:10 JST = 06:18:10Z, cache launch 06:18:50Z,
CPU 06:23:53Z); `device`, `engineVersion` / `engineArtifact` and `model` copied from the same model's GPU short-chat
record of the same build on this Mac (`--like ../2026-10-19-dashboard-v1-m4max-0180-rebuilt-mac/
litert-lm_litert-community_gemma-4-E2B-it-litert-lm_short-chat.jsonl`, v0.18.0), `--model-id
litert-community/gemma-4-E2B-it-litert-lm` (the Mac CLI's native line names no model); the CPU rows with
`--runtime litert-lm-cpu` (the importer's option of this change: the Mac has no `litert-lm-cpu` record of this model
on v0.18.0 to serve as `--like`); `--device Mac16,9`; `--instrument "litert-lm native benchmark() via yardstick
--litert-native-benchmark"`. The cache launch carries `--first-ever 1` (`firstEver`): it built the XNNPACK weight
cache (`$TMPDIR/gemma-4-E2B-it.litertlm_1788439871_2588147712.xnnpack_cache`, absent before the sitting, written
15:18:52 inside the launch 15:18:50–53, init 3.38 s). `SESSION.json`'s `cells_with_records` was 1 of 4 when the job
wrote it (before the import) and is 4 of 4 now (`native_import` in the file says so).

Caches. GPU: every call logged `Initializing WebGPU-based API from serialized data` and `Initialized InferenceContext
from serialized data` four times = the ML Drift program cache in `$TMPDIR` (written 2026-10-19 07:11, by which build
is not recorded) was read, not built. CPU protocol: the four calls read the cache the cache launch built (init 0.82 s,
then 0.27–0.29 s; the file's mtime stayed 15:18:52); this engine prints no VERBOSE cache line on the Mac. The cache
this sitting created was removed after it (a CPU run's XNNPACK cache slows later GPU runs:
`methodology/agreed-protocol-gemma4.md` "Traps").

Instrument facts. The GPU arm registered `GPU WebGPU` (Dawn), not Metal (`RegisterAccelerator … name=GPU WebGPU` in
every launch's console). The CPU arm runs the engine's default thread count, 4: the Swift wrapper passes none
(`ios/BenchmarkApp/Vendored/LiteRT-LM/swift/Engine.swift`), the C API's default settings set
`CpuConfig::number_of_threads = 4` (`runtime/executor/llm_executor_settings.cc:180`); the Mac engine prints no
settings dump. The Mac CLI's native line carries no memory field (`apple/YardstickCLI/Sources/Yardstick.swift`), so
these records have no memory reading. Speculative decoding is off (the engine's default).

Host load (5 s samples during the window, kept with the lane's notes): a `du` scan of another session ran during the
anchor phase and ended before the payload; during the GPU cell (15:18:10–20) a Chrome renderer read 82.9 % CPU,
during the CPU cell Chrome renderers 75–78 % twice; no builder passed 100 %, no cell was retaken.
