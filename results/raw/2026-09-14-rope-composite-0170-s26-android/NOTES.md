# Does the `odml.rope` word-order defect of the v0.16.0 Android GPU path survive into LiteRT-LM 0.17.0? — Galaxy S26, 2026-09-14 14:50–15:08

**No, not on this phone.** On the v0.17.0 Android GPU path the published `litert-community/Qwen3-1.7B` GPU build
(`Qwen3-1.7B_dynamic_wi4b32_afp32.litertlm`, sha256 `2eeffef7…`, `odml.rope` ×55) answers the short-chat prompt
with thinking, and so do the four 2026-09-14 dtype-only exports (rope composite on / rope inlined, int8 / int4).
The same files swapped back to v0.16.0 on the same phone the same hour repeat the 2026-09-13 off-prompt sentence.
Two independent 0.17.0 runtimes agree: the OSS `litert_lm_main` (android_arm64 source build at the tag) and the
`litertlm-android` 0.17.0 Maven AAR (through the Route B APK). Nothing to file upstream from this sitting; the
defect is a property of the v0.16.0 pin this bench measured on 2026-09-13/14.

Not measured: the Pixel 8a (Mali) on 0.17.0 — the phone was off the adb bus all afternoon (`adb devices` and
`system_profiler SPUSBDataType` both empty for it), so the Mali leg of this question is still open. The 0.6B
published GPU build was not run either. One prompt, one run per cell — a correctness sitting, not a speed one.

## Cells (all `diag/`, short-chat "Explain what on-device AI means in simple terms.", engine-default sampling, thinking as the bundle declares it, unmasked CPU, one process at a time under the S26 hold)

| # | engine (on-device binary, sha-verified against `android/engine-pins.json`) | backend | file (sha256 prefix) | answer | gen tokens | decode tok/s | delegate |
|---|---|---|---|---|---|---|---|
| 1 | v0.17.0 CLI | GPU | published `Qwen3-1.7B_dynamic_wi4b32_afp32` (`2eeffef7`) | **on-topic** — "On-device AI is like having a smart computer that can think and make decisions right on your phone…" | 536 | 39.9 | 994/994, 994/994, 936/936 LITERT_CL |
| 2 | v0.17.0 CLI | CPU | same | on-topic — "On-device AI is like having a smart computer chip in your phone or tablet…" | 681 | 10.92 | XNNPACK 711/994, 647/936 |
| 3 | v0.17.0 CLI | GPU | `Qwen3-1.7B_wi4b32_gpuflags` (`914ca239`, rope composite) | on-topic — "On-device AI is like having a smart assistant that works on your phone…" | 620 | 38.53 | 1022/1022, 936/936 |
| 4 | v0.17.0 CLI | GPU | `Qwen3-1.7B_wi8_gpuflags` (`9ce338e4`, rope composite) | on-topic — "On-device AI means that the artificial intelligence (AI) works directly on your device…" | 839 | 22.79 | 1022/1022, 936/936 |
| 5 | v0.17.0 CLI | GPU | `Qwen3-1.7B_wi4b32_gpuflags_norope` (`5e761950`) | on-topic — "On-device AI is like having a smart computer in your pocket!…" | 534 | 38.73 | 1364/1364, 1277/1277 |
| 6 | v0.17.0 CLI | GPU | `Qwen3-1.7B_wi8_gpuflags_norope` (`6080fa06`) | on-topic — "On-device AI means that the artificial intelligence (AI) models and their processing happen directly on the device…" | 909 | 25.58 | 1364/1364, 1277/1277 |
| 7 | **v0.16.0 CLI (control, same hour)** | GPU | published `Qwen3-1.7B_dynamic_wi4b32_afp32` (`2eeffef7`) | **off-prompt** — `</think>` then "The word "explain" means to provide a clear and logical description of something…" (the 2026-09-13 text, 3/3 runs then) | 58 | 27.05 | 994/994, 994/994, 936/936 |
| 8 | **v0.16.0 CLI (control, same hour)** | GPU | `Qwen3-1.7B_wi8_gpuflags` (`9ce338e4`, rope composite) | **off-prompt** — `</think>` then ""Explain" means to make something clear or understandable…" | 90 | 21.9 | 1022/1022, 936/936 |
| 9 | litertlm-android 0.17.0 AAR (Route B APK, `engineArtifact` = AAR sha256 `28aa6bc4…`) | GPU | published `Qwen3-1.7B_dynamic_wi4b32_afp32` (`2eeffef7`) | on-topic thinking — `<thought>Okay, the user is asking for a simple explanation of what on-device AI is…` (cut by the 128-token budget inside the thought) | 128 | 33.43 | 994/994, 994/994, 936/936 |
| 10 | litertlm-android 0.17.0 AAR | CPU | same | on-topic thinking — `<thought>Okay, the user is asking me to explain what on-device AI means in simple terms…` | 128 | 5.66 | XNNPACK 711/994, 647/936 |

Records: `diag/litert-lm-<backend>_litert-local_Qwen3-1.7B-<id>-e0170|e0160_short-chat_*_run1.{json,log}` (cells 1–8,
`engineVersion` stamped from the on-device sha), `diag/apk/{gpu,cpu}/` (cells 9–10: record + `.log` with the reply
between `=== reply ===` markers + `logcat-process.txt` + `am_instrument.txt`), `diag/driver.log` (cells 1–6 + the
first APK pass), `diag/driver_control_v0160.log` (7–8), `diag/driver_apk.log` (9–10), `diag/run_0170.py` (the driver).

## What moved, and what did not

- Same phone (SM-S942Q, Android 16, patch 2026-06-05, SM8850), same files by sha256, same prompt file, same harness
  command line (`run_cell.py … --runs 1`), fresh on-device copy and fresh ML Drift / XNNPACK caches for every cell
  (each bundle pushed under a new `litert-local/…-e0170` or `…-e0160` id, removed with its caches after its cell, so
  the v0.16.0 lane's own copies and caches were never read or written). The one variable between cells 1/4 and
  7/8 is the engine binary + its `.so` set: `v0.17.0` (`litert_lm_main` sha256 `9a3f5abd…`, vendoring LiteRT
  `9fe5be45564c868408e6514c8aabb83e211a0911`) vs `v0.16.0` (`37d6b9d6…`, LiteRT `0ff28117f1cb5556d0e015bf80b773f74e2bee51`).
- The CPU backend answers on both engines (cell 2 here; v0.16.0 CPU on the Pixel in the sitting-1 `diag/`), so the
  files are right and the difference is in the GPU path of the older build.
- What is not established: which LiteRT / ML Drift change between the two pins made the difference (not bisected),
  the engine-default sampler being identical across the two versions (both records say `engine-default`; the
  v0.16.0 output is the same 58-token text across four runs on this file (three on 2026-09-13, cell 7), the v0.17.0 thought channel is coherent and
  on-topic — sampling cannot produce the difference in either direction, but it was not pinned), and the Mali path.

## Engine provenance (0.17.0)

- **The v0.17.0 GitHub release ships no Android binary** (assets 2026-09-09: `CLiteRTLM.xcframework.zip`,
  `CLiteRTLM_mac.xcframework.zip`, `litert_lm_main.macos_arm64`) — the handoff's "release android_arm64 binary" did
  not exist. So: `LITERTLM_TAG=v0.17.0 android/scripts/build_litert_lm_main.sh` (bazel 7.6.1 via bazelisk, NDK
  29.0.13113456, `--config=android_arm64 --enable_platform_specific_config`, ~7 min on the M4 Max from the existing
  `~/.cache/apple-silicon-llm-bench/litert-lm-v0.17.0` clone at `git describe` = `v0.17.0`, commit 945edf3) →
  `android/bin/v0.17.0/` = `litert_lm_main` + `litert_lm_advanced_main` + the 7 `.so` from the tag's
  `prebuilt/android_arm64/` (Git LFS; byte-identical to the checkout's files). Pins entry added to
  `android/engine-pins.json` by the script. Build log: session scratchpad `build_v0170_android.log` (not kept).
- Swapped into `/data/local/tmp/llmbench/` for cells 1–6 (binary + `.so` set, every sha256 verified against the
  pins after the push) and swapped back to v0.16.0 before the APK cells and the controls (verified the same way;
  `37d6b9d6…` on the device at close). `run_cell.py` stamps `engineVersion` from the on-device sha, so the records
  carry the version that measured them, not the newest pin.
- The AAR witness is the Route B APK built 2026-09-10 (`android/ddp-bench/app/build/outputs/`, `engine-pin.json`
  asset = litertlm-android 0.17.0, AAR sha256 `28aa6bc4…`), installed by `run_local.sh --no-build`.

## Traps met

- **Extension-less bundle path**: the first pass pushed the published file under its HF-cache blob name (the
  `realpath` of the snapshot symlink, no `.litertlm`), and the 0.17.0 engine died at load with
  `INVALID_ARGUMENT: Unsupported or unknown file format` (`file_format_util.cc:91`) — 0.17.0 decides the format by
  the path extension. Kept as `diag/attempt1/` + `diag/driver.attempt1.log`; the driver now pushes the symlink
  path.
- **APK record label**: `run_local.sh --model` without `--repo/--file` leaves the record's `model.id` at the
  default `litert-community/gemma-3-270m-it` next to the Qwen3 sha256 (`model_path` wins over the download, the
  repo args only label). First APK pass kept under `diag/attempt1/apk_mislabeled/` (same texts); cells 9–10 are the
  relabeled re-run.
- **`--max_output_tokens` and the thought channel**: the 0.17.0 CLI does not print the thought channel at all (the
  v0.16.0 CLI printed `</think>`), and neither CLI counts it against the 128 budget (536–909 generated tokens for
  the thinking cells); the Kotlin API counts it (128 on the dot, the reply cut inside `<thought>`). Handoff item 9.
- **`pkill -f litert_lm_main` inside `adb shell "…"`** kills the shell running the command line (its own args
  match) — use `pkill -x`.
- The CPU frequency cap on this phone moved during the sitting (cpu0 `scaling_max_freq` 3628800 at 14:51 →
  2745600 → 2227200 → 1996800 by 15:05; `cpuinfo_max_freq` 3628800 throughout; 5 thermal-gate waits at "light"),
  as on the 12:xx sitting. Irrelevant to a text-correctness verdict; the tok/s in the table are not comparable
  across sessions (and diag rows never enter the summary).

## Device state at close

v0.16.0 engine restored and sha-verified; every `…-e0170` / `…-e0160` copy, cache and marker removed; the APK's
`/data/local/tmp/edge-llm-bench/` back to the MiniCPM5 file that was there; hold released (`.device_hold.s26`
removed); 80 GB free.
