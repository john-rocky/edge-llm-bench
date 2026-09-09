# Evaluating HF LiteRT models on the Developer Device Platform (DDP)

*Written 2026-09-09 against the DDP docs dated 2026-09-03 (Preview). Nothing here has run on DDP yet; every claim about the platform is from its documentation, and every claim about this harness is from the code in this repo.*

**Goal (as asked by the LiteRT team):** evaluate the `.litertlm` files published under `litert-community` automatically on real devices, publish the numbers, and link each number back to the DDP run that produced it.

## What DDP offers, as documented

| surface | what it is | what it means for this harness |
|---|---|---|
| Device Catalog | 213 device rows (`gcloud beta device-run devices list`): Pixel 8a `akita-34/35`, Pixel 9 `tokay-34/35/36`, Pixel 10 Pro `blazer-36`, Pixel 11 `cubs-37`, Galaxy S24 `e1q-34/36`, S25 `pa1q-36`, S26 `m1q-36`, foldables, tablets | the same phones this repo already measures (Pixel 8a, Galaxy S26) exist there, so rows are comparable with the local ones |
| Device Run | batch: `gcloud beta device-run sessions submit instrumentation --device <ids> --apps app.apk --test test.apk`; multiple devices per session, uniform / smart sharding, `--async`; results land in `gs://<project>/automation/sessions/<session-id>/` with a Cloud Console URL | takes an **Android instrumentation-test APK only** — the native `litert_lm_advanced_main` binary this harness pushes over adb cannot be submitted as-is |
| Device Streaming | interactive ADB to a remote physical device; the open-source agent skill `developer-device-platform-basics` reserves, extends and forwards adb from a Python venv | this harness's Android lane runs unchanged over it (`BENCH_ANDROID_SERIAL` → the forwarded device) |
| Platform | Preview, Android only (iOS "coming soon"); billed to the Google Cloud project; APIs `devicerun`, `devicestreaming`, `testing` | iPhone rows stay local for now; someone's project pays per device-minute |

## Two routes

**Route A — Device Streaming + the existing harness (first numbers in days).**
`android/bench/run_cell.py` already does everything except the device reservation: it pushes the model and the pinned `litert_lm_advanced_main` (`android/engine-pins.json`), runs `--benchmark` on `--backend cpu|gpu`, parses prefill / decode / TTFT / init / peak RSS into `schema/result.v1.json`, and records the raw log. Over Streaming the only change is the serial. Limits: one interactive session per device, extended by hand (the skill exposes "extend by 30 minutes"), no sharding, no batch API — a way to validate that the numbers match the local ones, not the way to run 100 repos nightly.

**Route B — Device Run with a benchmark test APK (the durable one).**
One instrumentation-test APK, `litertlm-bench-test`, parameterized by instrumentation args `(hf_repo, file, backend, runtime_version, prompt_set)`:

1. downloads the `.litertlm` from the Hub onto the device (HF token for gated repos passed as a test arg, never baked in);
2. creates the LiteRT-LM engine through the Kotlin API on the requested backend and runs the same measurement this harness makes natively — prefill and decode tok/s at a fixed prompt length, TTFT, init time, peak RSS — plus the 8-question correctness gate (a model that generates garbage at 40 tok/s must fail, not rank);
3. writes one `result.v1.json` per cell into the test's output directory, which Device Run collects into the session bucket.

An outer job (GitHub Actions on a schedule, or Cloud Run) then: lists the org's repos and their `.litertlm` files; submits one session per (device set × repo), with the session name carrying the repo id; waits; pulls the JSON from the bucket; and writes the rows into each card the way the card lines in this repo's sibling tooling already do — device · runtime version · backend · number · date — with the DDP session's console URL closing the line as the citation ("link back to DDP"). Org-owned cards can be committed directly by the org; anyone else's get a Hub PR.

Device set to start with (one per tier): Pixel 8a (`akita-35`, 8 GB, Mali), Pixel 10 Pro (`blazer-36`), Galaxy S26 (`m1q-36`, Adreno). Re-run policy: every `litert-lm` release (this repo's `release-watch` already detects them) and every new file on a repo.

## What already exists in this repo for Route B

- `schema/result.v1.json` — the record shape; `scripts/build_summary.py` / `render_leaderboard.py` consume it.
- `android/bench/parsers.py` — parsing of the native benchmark output; the APK's Kotlin measurement should emit the same fields so the parsers and the summary layer stay shared.
- `android/engine-pins.json` — the version-pin discipline: the APK bundles one `litertlm-android` version per build and reports it in every record.
- `methodology/android.md` — what is and is not comparable across runs (no warm regime on Android, TTFT caveats).

## Open questions (for whoever owns the GCP project)

- **Cost attribution.** The docs describe a bucket path and a Console link per session, not a label or tag; the fallback is a naming convention (`<repo>--<file>--<device>`) plus the bucket path. Whether Device Run sessions accept Cloud labels is not documented.
- **Which project pays.** The APK and the job are project-agnostic; a first session on a personal project costs a few device-minutes and shows the real result shape.
- **Correctness beyond the gate.** GSM8K-class parity runs are minutes per model on a phone; they fit Device Run's sharding, but the budget decides whether they are nightly or per-release.

## Next step

Build the test APK prototype (Kotlin, `litertlm-android` 0.17.0, one model) and run it locally with `adb shell am instrument` on a Galaxy S26 until it emits a `result.v1.json` that `build_summary.py` accepts; then submit the same APK to one DDP session and compare the two rows.
