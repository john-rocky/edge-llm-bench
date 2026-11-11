# The billed session from Linux, 2026-10-16: `session-17997931` on `akita-35`

Every value below is copied from the file named beside it; the spans in seconds are end minus start of the same
file's timestamps. Campaign dir: `results/raw/2026-10-16-ddp-linux-first-run-akita-35-android/` (C below).

- Command (as dev in the container, from the clone, in the venv of README step 1; `linux/steps/95-session.sh`):
  `./bench matrix matrices/ddp-first-run.cells --ddp akita-35 --campaign 2026-10-16-ddp-linux-first-run-akita-35 --project litert-edge-portal --bucket gs://litert-edge-portal-devicerun`
- Start 15:30:43 JST, end 15:37:55 JST, 432 s, exit 0 (`linux/steps.tsv` row `session`, `linux/10-session.log`).
- What the 432 s held (`linux/10-session.log`, C `ddp/operation-create-1.json`, C `ddp/session-1.json`): the model
  download into the empty HF cache, the bucket checks of 12 objects (11 found), one upload (the model, 977,184,032 B),
  the POST (session `createTime` 06:32:05.805 UTC), polls every 30 s, the pull, the scrub, the records and the summary
  of the container's clone.

## Session report (C `ddp/session-1.json`)

| level | name | result | start (UTC) | end (UTC) | seconds |
|---|---|---|---|---|---|
| session | `session-17997931` | PASSED | 2026-10-16T06:32:09.598Z | 2026-10-16T06:37:36.614Z | 327.016 |
| job | `j01-gpu-Qwen3-1-7B-short-chat` | PASSED | 2026-10-16T06:32:12.528Z | 2026-10-16T06:37:35.028Z | 322.500 |
| execution | `execution-fa5d6320-579c-4cc8-91e9-e4eecd8eb2e5` | PASSED | 2026-10-16T06:33:44.233Z | 2026-10-16T06:37:32.751Z | 228.518 |

The wrapper's own clock (C `ddp/session-17997931/…/ddp-out/wrapper.log`, epoch seconds): start 1792132436, run 1
1792132438-1792132480 (exit 0), cooldown 120 s, run 2 1792132601-1792132640 (exit 0). The thermal gate waited 0 s
(run 1) and 1 s (run 2), Thermal Status 0 at the start and the end of both runs (`run<i>.state`). The driver polled
11 times (`not done`) before the operation was done (`linux/10-session.log`).

## Records (C `app-path-android/`)

| field | run 1 | run 2 |
|---|---|---|
| record | `litert-lm-gpu_litert-community_Qwen3-1.7B_short-chat_2026-10-16T06-33-57_run1.json` | `litert-lm-gpu_litert-community_Qwen3-1.7B_short-chat_2026-10-16T06-36-41_run2.json` |
| timestamp | 2026-10-16T06:33:57Z | 2026-10-16T06:36:41Z |
| runtime | litert-lm-gpu | litert-lm-gpu |
| engineVersion | v0.18.0 | v0.18.0 |
| engineArtifact | 54832c4992f932aec76e85be546b63dcb1e2820236d76c8f38d66c0ecc62774a | 54832c4992f932aec76e85be546b63dcb1e2820236d76c8f38d66c0ecc62774a |
| model.file | litert-community_Qwen3-1.7B_Qwen3-1.7B_dynamic_wi4b32_afp32.litertlm | litert-community_Qwen3-1.7B_Qwen3-1.7B_dynamic_wi4b32_afp32.litertlm |
| model.sha256 | 2a72330b504a6596d53a2c00923c57173b10f1b83e6a541213ffec08d1fc5de8 | 2a72330b504a6596d53a2c00923c57173b10f1b83e6a541213ffec08d1fc5de8 |
| provenance.modelShaSource | device | device |
| provenance.ddpMissing | (absent) | (absent) |
| device.modelIdentifier | Pixel 8a | Pixel 8a |
| device Android / patch / SoC | 15 / 2025-04-05 / Tensor G3 | 15 / 2025-04-05 / Tensor G3 |
| conditions.ddp.serial | 45231JEKB09198 | 45231JEKB09198 |
| conditions.ddp.buildFingerprint | google/akita/akita:15/BP1A.250405.007.B1/13240308:user/release-keys | google/akita/akita:15/BP1A.250405.007.B1/13240308:user/release-keys |
| conditions.ddp.resultType | PASSED | PASSED |
| conditions.exitCode | 0 | 0 |
| conditions.elapsedSeconds | 42.7 | 39.0 |
| conditions.engineCache | `{"xnnpackWeightCache": "absent", "gpuCache": "not-loaded"}` | `{"xnnpackWeightCache": "absent", "gpuCache": "loaded"}` |
| conditions.protocolFlags | `[]` | `[]` |
| conditions.thermalRawStatus -> Final | 0 -> 0 | 0 -> 0 |
| conditions.thermalGateTimedOut | false | false |
| conditions.batteryTemperatureInitialC -> FinalC | 27.3 -> 27.4 | 28.2 -> 28.2 |
| conditions.cpuMaxFreqMHz (min / hw per policy) | policy0 1704 / 1704, policy4 2367 / 2367, policy8 2914 / 2914 | policy0 1704 / 1704, policy4 2367 / 2367, policy8 2914 / 2914 |
| conditions.cpuAffinity / cpusAllowedList | taskset f0 / 4-8 | taskset f0 / 4-8 |
| conditions.screen | on-usb | on-usb |
| metrics.decodeTokensPerSecond | 20.16 | 17.79 |
| metrics.promptTokensPerSecond | 28.24 | 27.91 |
| metrics.firstTokenLatencyMS | 720.0 | 740.0 |
| metrics.promptTokenCount / generatedTokenCount | 19 / 526 | 19 / 526 |
| metrics.memoryMedianResidentMB / PeakResidentMB | 2179.31640625 / 2179.5234375 | 2176.97265625 / 2177.84765625 |
| metrics.coldRun | true | true |
| metrics.harnessStamp | 2026-08-android-cli-v1+ddp-route-c | 2026-08-android-cli-v1+ddp-route-c |

## The runbook's checks (docs/OPERATIONS.md, "Run cells on DDP", step 5)

- Session, job and execution `PASSED`; no `ddp/error-<n>.json`; `app-path-android/` holds 2 records (1 job x 2 runs)
  and no `FAILURES.txt`; `SKIPPED.txt` is empty (0 rows skipped).
- `engineVersion` v0.18.0 = `android/engine-pins.json` `android_pins` `litert-lm` (not `unknown (…)`); the unit's
  sha256 of the 9 engine files (C `…/ddp-out/provenance.txt`) are the pinned ones.
- `model.sha256` 2a72330b… is the sha256 the wrapper read on the unit (`provenance.txt`), = the Hub's `lfs.oid` for
  the file (`paths-info`, last commit 2026-10-11). The plan and the request carry 4194181f… for the model, the Hub's
  `xetHash` of the same file: the name huggingface_hub 2.2.0 gave the cache blob (`linux/10-session.log`, step
  `model-blob`), which `android/ddp/run_ddp.py` takes for the sha256 (lines 190-191). So the bucket now holds the same
  977,184,032 B under `models/4194181f…/` too; nothing was overwritten.
- No `provenance.ddpMissing`; `conditions.ddp.serial` and `buildFingerprint` name the unit (one unit, both runs).
- `conditions.protocolFlags` `[]`: no CPU ceiling below the hardware maximum in either run (the policies above), so
  both rows pool (cpu-cap-rule).
- Thermal Status 0 at the start and the end of both runs; the gate waited 0 s and 1 s, no timeout.
- `conditions.engineCache`: run 1 `gpuCache` `not-loaded` (a fresh unit), run 2 `loaded`; the engine's own lines
  (`run<i>.engine.txt`): Init Executor 14364.11 ms (run 1) and 7177.90 ms (run 2).
- The reply text (`run<i>.engine.txt`, between `input_prompt:` and `BenchmarkInfo:`): 514 B, the same bytes in both
  runs, an English answer to the prompt `Explain what on-device AI means in simple terms.`
- Scrub (C `ddp/scrub.json`): `run1_logcat.txt` 0, `run2_logcat.txt` 8 (ip6), the execution's `logcat.txt` 10 (ip6 8,
  mac 2); the two per-run logcats carry no private IPv4, no MAC other than Android's placeholders, no IPv6 address,
  and their only keyword hits are `onetimeinitializer` (the substring `imei`), checked after the scrub.
- Summary (rebuilt from the git index): `results/summary/device-runs.csv` 4483 -> 4485 lines, the 2 new rows with the
  device `Pixel 8a (DDP akita-35)`; `results/summary/README.md` 4482 -> 4484 records.
