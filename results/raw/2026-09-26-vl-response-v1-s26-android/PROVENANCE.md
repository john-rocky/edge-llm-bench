# 2026-09-26 vision-language response time, v1 — Galaxy S26 leg

Task family: `docs/vl-response-v1.md` (section "Android leg"); cells: the `android` rows of
`matrices/vl-response-v1.cells`; driver: `scripts/vl_response_android.py
matrices/vl-response-v1.cells --campaign 2026-09-26-vl-response-v1-s26`, serial `RFGL80R6A6H`,
`--pause 45 --base-cooldown 90 --timeout 900` (the defaults; `session_provenance.txt`),
09:47:40–10:26:56 JST. Numbers and findings: `NOTES.md`. Every launch's stderr stream and
stdout are under `logs/`; the driver's log is `runlog.txt` (copy: `logs/driver_sitting1.log`).
`FAILURES.txt` lists the three GPU cells whose launches all failed (they stay in the table as
FAIL rows). `SESSION.json` is the payload half of the dashboard-rule session record.

## Device

Samsung Galaxy S26 `SM-S942Q` (`m1q`, SoC `SM8850`), Android 16, security patch 2026-06-05,
adb serial `RFGL80R6A6H`, USB, charging (battery 94–95 %, `batteryState: charging` in every
record). **Screen off**: `mWakefulness = Dozing` before all 36 launches and
`stay_on_while_plugged_in = 0` (`provenance.deviceBefore`), while the device page's protocol
says screen on and the records' `conditions.screen` carries that protocol text (`on-usb`),
not a reading — NOTES.md "Screen: off"; the anchor admitted the sitting at ratio 1.016. No CPU
frequency cap before any launch (`scaling_max_freq` = `cpuinfo_max_freq` on both cpufreq
policies: 3,628,800 and 4,742,400 kHz); after 11 launches the flag read capped (list in
NOTES.md). No `taskset`. Gate before every launch: thermal status 0 and battery ≤ 36.0 °C
(`dumpsys thermalservice` / `dumpsys battery`); it never waited. Battery temperature and
thermal status before and after each launch are in `metrics.batteryTemp{Initial,Final}C` and
`provenance.deviceBefore/After`.

The phone's shared hold (the bench host's cross-lane protocol, `docs/OPERATIONS.md`, "A phone
is shared with other lanes") was held by this lane from before the anchor to after the last
launch (holder pid 5529, `vltts-rtf-s26-vl-leg`), so no other lane's driver used the phone.
The hold file is rewritten by the next holder; these two values come from the session's own
notes, not from a stored copy.

## Instrument

LiteRT-LM `main` at `1dadd00c2a2363f275e713cfebab5fa9b96c6226` (2026-09-17 15:50 -0700,
"Update dependencies of litert_lm") — the same commit as the Mac leg and the asr-rtf-v1
runner (`~/code/litert-lm-1dadd00c-wt`), built for the phone:
`ANDROID_NDK_HOME=~/Library/Android/sdk/ndk/28.2.13676358 bazelisk build --config=android_arm64
--enable_platform_specific_config //runtime/engine:litert_lm_advanced_main`, bazel 7.6.1,
started 2026-09-26 09:20:15 JST, elapsed 119 s, 3,140 actions, exit 0
(`logs/bazel_litert_lm_advanced_main_android.log`). GPU libraries = the LFS objects of
`prebuilt/android_arm64/` at the same commit, the same files as the asr-rtf-v1 S26 leg. The
engine loads `libLiteRtGpuAccelerator.so` from `LD_LIBRARY_PATH` (log: `Attempting to load GPU
accelerator(libLiteRtGpuAccelerator.so)`, `Dynamically loaded GPU accelerator … registered`,
`Created OpenCL device`, `Replacing N out of N node(s) with delegate (LITERT_CL)`).

Staged dir `.build/litert-lm-advanced-main-1dadd00c-android/`. Its `ENGINE_VERSION` (line 1 is
stamped as `engineVersion`, line 2 goes into `engineArtifact`):

```
main@1dadd00c
LiteRT-LM main 2026-09-17 15:50 -0700 (Update dependencies of litert_lm); bazelisk build --config=android_arm64 --enable_platform_specific_config //runtime/engine:litert_lm_advanced_main; bazel 7.6.1, NDK 28.2.13676358, Xcode 27.0 host, 2026-09-26 09:20-09:22 JST; GPU .so files = prebuilt/android_arm64/ LFS objects at the same commit
```

On the phone everything sits under `/data/local/tmp/edge-llm-bench/vl/` (`bin/`, `models/`,
`images/`, `cache/`). `SHA256SUMS` here = the staged dir's, plus the image:

| file | sha256 | bytes |
|---|---|---|
| `litert_lm_advanced_main` (android_arm64) | `8d1329e95d89a909c7d400929767c880893da421b553c8c7a87401e879eed7d8` | 40,363,000 |
| `libLiteRtGpuAccelerator.so` | `88e716f4ff79970b377597fb4207e930dc4905bc23ddb08479cc3f317627274a` | 3,400,496 |
| `libLiteRtOpenClAccelerator.so` | `d9dd64c36f6e18661588e71cf6bad5860598e6ccd3a56dfb304c517f89ac609e` | 3,171,112 |
| `libLiteRtWebGpuAccelerator.so` / `libwebgpu_dawn.so` | `2777c137…` / `97772bf2…` | 3,203,888 / 19,695,320 |
| `libLiteRtTopKOpenClSampler.so` / `libLiteRtTopKWebGpuSampler.so` | `8e69e7d0…` / `23d584c4…` | 11,819,152 / 11,804,264 |
| `libGemmaModelConstraintProvider.so` | `f2aa38ce…` | 19,606,552 |
| `cat_couch_1024.jpg` | `cca087e6606460a43e6a1b025180b0da855577708946a983b4a07a20e2a7be59` | 325,221 |

Every launch (exact line in each record's `provenance.command`), through `adb -s RFGL80R6A6H shell`:

```
cd /data/local/tmp/edge-llm-bench/vl/bin && export LD_LIBRARY_PATH=/data/local/tmp/edge-llm-bench/vl/bin \
  && echo T0=$EPOCHREALTIME >&2 && ./litert_lm_advanced_main --backend=<cpu|gpu> --vision_backend=<same> \
  --model_path=/data/local/tmp/edge-llm-bench/vl/models/<file> \
  --input_prompt='Describe this image in one sentence. [image:/data/local/tmp/edge-llm-bench/vl/images/cat_couch_1024.jpg]' \
  --benchmark --max_output_tokens=64 --cache_dir=/data/local/tmp/edge-llm-bench/vl/cache/<file>; \
  echo EXIT=$? T1=$EPOCHREALTIME >&2
```

Streams and clocks: `adb shell` (shell protocol v2) delivers the phone process's stdout and
stderr as two streams, so the reply (stdout) and the engine log (stderr) are read as on the
Mac. `vlResponseSeconds` and `vlFirstTokenHostSeconds` are host arrival times of the request
marker (stderr) and of the last / first reply byte (stdout); both travel the same USB
connection, so the delta carries adb jitter (milliseconds) but no offset. `loadTimeSeconds`
and `totalWallSeconds` are phone-clock differences (`$EPOCHREALTIME` echoed before exec and
after exit, the absl timestamp of the request marker), so adb start-up is not in them. TTFT,
prefill, decode, init phases and marks come from `--benchmark`'s BenchmarkInfo. The OpenCL
loader prints `INFO: Loaded OpenCL library with dlopen.` on stdout; the driver strips such
log lines from the reply and from the first-byte clock (the raw stdout is in `logs/`).
`memoryPeakResidentMB` = `VmHWM` of the process polled through adb every 0.5 s (host memory
only).

## Models (`model.sha256` = `provenance.remoteModelSha256` in all 36 records)

| repo | file | sha256 (= the Hub's LFS sha256) | bytes | where it came from | `hfRevision` |
|---|---|---|---|---|---|
| `litert-community/SmolVLM2-500M` | `SmolVLM2-500M.litertlm` | `b808b328…60ad0` | 360,822,960 | the Mac leg's verified copy in `.build/vl-models/`, checked against `HF_SHA256SUMS` | `local` |
| `litert-community/LFM2.5-VL-450M` | `LFM2.5-VL-450M_int4_fixB.litertlm` | `6854cd96…bf6033` | 406,817,104 | same | `local` |
| `litert-community/InternVL3-1B` | `InternVL3-1B.litertlm` | `7cf87c35…fd1284a` | 737,314,160 | HF cache, downloaded 2026-09-26 09:20–09:22 JST | `1750633f` |
| `litert-community/LFM2.5-VL-1.6B` | `LFM2.5-VL-1.6B_int4_fixB.litertlm` | `79ca9db8…bd565c` | 1,298,139,472 | `.build/vl-models/`, as the 450M | `local` |
| `litert-community/Qwen2-VL-2B` | `Qwen2-VL-2B.litertlm` | `cf481776…49066b` | 1,783,424,544 | HF cache, downloaded 2026-09-26 09:22–09:28 JST | `5a03c859` |
| `litert-community/gemma-4-E2B-it-litert-lm` | `gemma-4-E2B-it.litertlm` | `18193810…9a63c` | 2,588,147,712 | HF cache snapshot `b3ca0d2f` (the dashboard's file) | `b3ca0d2f` |

The driver pushed each bundle with `adb push` and re-hashed it on the phone (`sha256sum`)
before the first launch; the host and phone sha256 agree for every record, and all six equal
the Hub API's LFS sha256 (`../2026-09-24-vl-response-v1-m4max-mac/HF_SHA256SUMS`). The recipe
line in `model.quantization` comes from each repo's `litertlm_manifest.json` in the HF cache;
the manifests are byte-identical to the ones the Mac leg read, and the Gemma 4 file carries the
lane's stated wNa8o8 recipe (quant-label-rule).

## Image

`evaldata/vl/cc0-cat-couch-1024/cat_couch_1024.jpg` (sha256 `cca087e6…a7be59`, 1024 × 682,
325,221 bytes; provenance in the Mac leg's PROVENANCE.md "Fixture"). The driver checks it
against `manifest.json` on the host and again with `sha256sum` on the phone.

## Anchor campaign

`../2026-09-26-vl-response-v1-s26-anchor-android/`: `./bench matrix matrices/anchors.cells
--platform android --campaign 2026-09-26-vl-response-v1-s26-anchor`, session start 09:35:31,
launches 09:35:43–09:46:15, same phone. Primary cell llama.cpp b8999
`unsloth/Qwen3-0.6B-GGUF` Q4_K_M short-chat: decode 108.0 / 107.0 / 110.7 tok/s, median
108.0, reference 106.3 (n = 6, `2026-09-24-dashboard-longctx-v1-s26-android-gpu-retake`),
ratio 1.016, thermal nominal → ADMITTED by `scripts/dashboard_job.py` `admit()`. The
secondary cell (litert-lm-gpu Qwen3-0.6B, v0.16.0) is in the same `SESSION.json` (ratio 1.090
to its own reference). `SESSION.json` there (phase `anchor`, verdict `ADMITTED`) and here
(phase `payload`, verdict `COMPLETED`, `admitted: true`) were written after the sitting from
those records.

## Driver smoke (not a measurement)

Before the sitting the driver was smoke-tested on the same phone with the SmolVLM2 cells:
`results/raw/local-vl-smoke-s26-android/` (gitignored by the `local-*` rule, never cited as a
number). The SmolVLM2 XNNPACK weight caches were already on the phone when the smoke started
(its CPU launch loaded them), and SmolVLM2 CPU launch 1 of the sitting loaded the same files
(NOTES.md finding 8).
