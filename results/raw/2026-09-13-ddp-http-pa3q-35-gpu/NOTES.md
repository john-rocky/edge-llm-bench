# 2026-09-13 — the DDP team's HTTP example with `--use_gpu=true`: `benchmark_model` on `pa3q-35`, GPU

Session `session-233c4731`, project `litert-edge-portal`, location `global`, created by the same
`POST …/sessions` as the CPU session (`../2026-09-13-ddp-http-pa3q-35/`), with `request.json` as the
body: the CPU body plus one argument, `--use_gpu=true`, different display names, and a `backend=gpu`
label. Submitted 2026-09-13 16:43:58 JST; the operation's `endTime` is 62 s after its `createTime`
(07:45:01.96 UTC); the 30-second poll saw `done: true` on its third call at 16:45:04 JST; result
**PASSED**. Console:
https://console.cloud.google.com/storage/browser/litert-edge-portal-devicerun/automation/sessions/session-233c4731/
Commands, observed output and the reading: `docs/ddp-integration.md`, section "Route C", paragraph
"GPU on the same route".

## What ran

- The public `gs://litert/binaries/2.2.0/android_arm64/benchmark_model` (unchanged), the same
  `mobilenet_v2.tflite` from the project bucket, the example's flags plus `--use_gpu=true`. Nothing
  pushed beside the binary: it carries the GPU accelerator statically (`gpu_registry.cc:87`) and loads
  the phone's OpenCL itself (`Loaded OpenCL library with dlopen`); 70/70 nodes on the `LITERT_CL`
  delegate. The same was checked beforehand on the local Galaxy S26 over adb and on the macOS build
  (Metal) — run log beside the drafts in the standup tree.
- Device `pa3q-35`: Galaxy S25 Ultra, OS version 35 (`device-pa3q-35.json`, the catalog entry). This
  execution's device log carries no line naming the model, so which physical unit of the `pa3q-35` pool
  ran is not recorded (the CPU session's log did name `SM-S938UZKAXAA`). Session 07:44:03–07:44:43 UTC
  (40 s); the execution 07:44:31.9–07:44:39.8 (8 s).
- GPU, 4 CPU threads requested (`--num_threads=4` stays in the example's flags): init 515.86 ms,
  first inference 5.84 ms, warm-up avg 0.98 ms (509 runs), inference avg 0.95 ms (1053 runs; min 0.92,
  max 1.28, std 0.02), throughput 604.75 MB/s, footprint 94.57 MB init and overall (96,840 kB).
  `results.pb.txt` and the logcat block agree.

## Files

- `request.json` — the body as sent (copy of `android/ddp-bench/http/session-benchmark_model-gpu.json`).
- `operation-create.json`, `operation.json` (embeds the whole `Session`), `session.json`,
  `device-pa3q-35.json` (copy of the catalog entry read the same day).
- `ddp-session/session-233c4731/run-benchmark-gpu/execution-<uuid>/` — the bucket as pulled:
  `artifacts/data/local/tmp/results.pb` (80 bytes) + `results.pb.txt`, `artifacts/data/local/tmp/runtime_info.pb`
  (119,383 bytes), and `logcat-process.txt` (the binary's pid 12740 only, 73 lines; the 203,728-byte whole-device
  `logcat.txt` was dropped). logcat.txt and the two pulled files were the only objects the platform
  wrote — the binary's stdout is not stored.

## Not a leaderboard row

No `app-path-android/` and no `result.v1` record: `scripts/build_summary.py` ignores this directory.
Read it beside the CPU session as the platform's behaviour on the two backends, not as a standing.
