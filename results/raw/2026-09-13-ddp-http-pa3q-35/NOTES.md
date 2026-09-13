# 2026-09-13 — the DDP team's HTTP example, run as written: `benchmark_model` on `pa3q-35`

Session `session-e1d64576`, project `litert-edge-portal`, location `global`, created by a plain
`POST https://devicerun.googleapis.com/v1alpha/projects/litert-edge-portal/locations/global/sessions`
with `request.json` as the body (the only gcloud involvement: `gcloud auth print-access-token`).
Submitted 2026-09-13 15:40:19 JST; the operation's `endTime` is 60 s later (06:41:18.9 UTC), and the
30-second poll saw `done: true` on its third call at 15:41:44 JST; result **PASSED**. Console:
https://console.cloud.google.com/storage/browser/litert-edge-portal-devicerun/automation/sessions/session-e1d64576/
The exact commands, their observed output and the reading: `docs/ddp-integration.md`, section
"Route C".

## What ran

- Job action `androidNativeBinary`: the public `gs://litert/binaries/2.2.0/android_arm64/benchmark_model`
  (8,020,656 bytes, the release-pinned copy of the LiteRT benchmark tool) with the example's five
  flags; device action `androidPushFiles` for `mobilenet_v2.tflite` (`litert-community/MobileNet-v2`,
  Hub commit `a847f8dd`, sha256 `9e3d5575…b09e6dd`, 14,079,072 bytes, from
  `gs://litert-edge-portal-devicerun/automation/inputs/2026-09-13_http-route/`), `androidPullFiles`
  for `/data/local/tmp/runtime_info.pb` and `/data/local/tmp/results.pb`, `androidLogcat`.
- Device `pa3q-35`: Galaxy S25 Ultra, OS version 35 (`device-pa3q-35.json`, the catalog entry read the
  same day); model code `SM-S938UZKAXAA` in the device log (`device-identity.txt`). Session
  06:40:22–06:41:04 UTC (42 s); the execution 06:40:51–06:41:00 (9 s); the binary's log lines span
  1.5 s (logcat 23:40:52.889–54.401, US-Pacific clock).
- CPU, XNNPACK, 70/70 nodes delegated, 4 threads: init 7.65 ms, first inference 6.68 ms, warm-up avg
  3.71 ms (135 runs), inference avg 2.92 ms (343 runs; min 2.76, max 4.73, std 0.22), throughput
  196.78 MB/s, init footprint 30.43 MB, overall 39.11 MB. `results.pb` (decoded in `results.pb.txt`
  with `android/ddp-bench/http/benchmark_result.proto`) and the logcat block agree.

## Files

- `request.json` — the body as sent (copy of `android/ddp-bench/http/session-benchmark_model.json`).
- `operation-create.json` — the POST response; `operation.json` — the finished operation (it embeds
  the whole `Session` in `response`); `session.json` — `GET …/sessions/session-e1d64576`.
- `ddp-session/session-e1d64576/run-benchmark/execution-<uuid>/` — the bucket as pulled:
  `artifacts/data/local/tmp/results.pb` (80 bytes) + `results.pb.txt`, `artifacts/data/local/tmp/runtime_info.pb`
  (119,070 bytes), `logcat-process.txt` (the binary's pid only, 41 lines) and `device-identity.txt`
  (the two lines of the whole-device log that name the model; the 214 KB `logcat.txt` itself was
  dropped). logcat.txt and the two pulled files were the only objects the platform wrote — the
  binary's stdout is not stored.
- `device-pa3q-35.json` — `GET …/devices/pa3q-35`, the catalog entry.

## Not a leaderboard row

No `app-path-android/` and no `result.v1` record: `scripts/build_summary.py` ignores this directory.
It records the platform's behaviour on the HTTP route, not a model's speed for the standings.
