# The second billed session from Linux, 2026-10-16: `session-b1179d6d` on `akita-35`

The same container, clone and venv as round 2's session, with the fixed `android/ddp/run_ddp.py` (commit 8e4ddad4;
sha256 e19903a0… in the clone = the worktree's, `linux/12-selftest-fix.log`) and the same huggingface_hub 2.2.0 cache
(the model's blob still named `blobs/41/4194181f…`, its bytes 2a72330b…, `linux/13-dryrun-fix.log`). Every value below
is copied from the file named beside it; the spans in seconds are end minus start of the same file's timestamps.
Campaign dir: `results/raw/2026-10-16-ddp-linux-first-run-b-akita-35-android/` (C below). A different lab unit and a
different sitting from round 2's session, so the two sessions' numbers are not set side by side here.

- Command (as dev in the container, from the clone, in the venv of README step 1; `linux/steps/r2b-session-b.sh`):
  `./bench matrix matrices/ddp-first-run.cells --ddp akita-35 --campaign 2026-10-16-ddp-linux-first-run-b-akita-35 --project litert-edge-portal --bucket gs://litert-edge-portal-devicerun`
- Start 16:17:59 JST, end 16:23:59 JST, 360 s, exit 0 (`linux/steps.tsv` row `session-b`, `linux/14-session-b.log`);
  the selftest of the same bytes passed first in the container and on the Mac (76 checks each, steps
  `selftest-final`, `mac-selftest-final`).
- Uploads: **0**. The driver printed `in bucket:` for all 12 inputs (the 9 engine files, the model under
  `automation/inputs/edge-llm-bench/models/2a72330b504a6596d53a2c00923c57173b10f1b83e6a541213ffec08d1fc5de8/Qwen3-1.7B_dynamic_wi4b32_afp32.litertlm`,
  the prompt, the wrapper) and no `uploading` line. gcloud's own log files written during the run (27): 14
  `gcloud.auth.print-access-token`, 12 `gcloud.storage.ls`, 1 `gcloud.storage.cp`, and that one is the pull
  (`-R`, source `gs://litert-edge-portal-devicerun/automation/sessions/session-b1179d6d`, destination the campaign's
  `ddp/`) (`linux/14-session-b.log`).
- The plan and the request key the model `models/2a72330b…/` (C `ddp/plan-1.json`: `sha256` 2a72330b…, 977,184,032
  bytes, no `uncached`; C `ddp/request-1.json`: the push path above). The unit's own `sha256sum` of the pushed model:
  2a72330b… (C `…/ddp-out/provenance.txt`).
- The POST: operation `createTime` 2026-10-16T07:18:10.019Z (C `ddp/operation-create-1.json`); 11 polls `not done`
  before the operation was done (`linux/14-session-b.log`).

## Session report (C `ddp/session-1.json`)

| level | name | result | start (UTC) | end (UTC) | seconds |
|---|---|---|---|---|---|
| session | `session-b1179d6d` | PASSED | 2026-10-16T07:18:12.502Z | 2026-10-16T07:23:34.621Z | 322.119 |
| job | `j01-gpu-Qwen3-1-7B-short-chat` | PASSED | 2026-10-16T07:18:14.563Z | 2026-10-16T07:23:31.160Z | 316.597 |
| execution | `execution-669be17d-451b-43d0-8aa0-a37b599c2fd1` | PASSED | 2026-10-16T07:19:30.266Z | 2026-10-16T07:23:29.295Z | 239.029 |

The wrapper's clock (C `…/ddp-out/wrapper.log`, epoch seconds): start 1792135195, run 1 1792135197-1792135239 (exit
0), cooldown 120 s, run 2 1792135359-1792135395 (exit 0). The thermal gate and the CPU-cap wait each waited 0 s before
both runs, Thermal Status 0 at the start and the end of both (`run<i>.state`).

## Records (C `app-path-android/`)

| field | run 1 | run 2 |
|---|---|---|
| record | `litert-lm-gpu_litert-community_Qwen3-1.7B_short-chat_2026-10-16T07-19-56_run1.json` | `litert-lm-gpu_litert-community_Qwen3-1.7B_short-chat_2026-10-16T07-22-39_run2.json` |
| timestamp | 2026-10-16T07:19:56Z | 2026-10-16T07:22:39Z |
| runtime | litert-lm-gpu | litert-lm-gpu |
| engineVersion | v0.18.0 | v0.18.0 |
| engineArtifact | 54832c4992f932aec76e85be546b63dcb1e2820236d76c8f38d66c0ecc62774a | 54832c4992f932aec76e85be546b63dcb1e2820236d76c8f38d66c0ecc62774a |
| model.file | litert-community_Qwen3-1.7B_Qwen3-1.7B_dynamic_wi4b32_afp32.litertlm | litert-community_Qwen3-1.7B_Qwen3-1.7B_dynamic_wi4b32_afp32.litertlm |
| model.sha256 | 2a72330b504a6596d53a2c00923c57173b10f1b83e6a541213ffec08d1fc5de8 | 2a72330b504a6596d53a2c00923c57173b10f1b83e6a541213ffec08d1fc5de8 |
| provenance.modelShaSource | device | device |
| provenance.ddpMissing | (absent) | (absent) |
| device.modelIdentifier / systemVersion / securityPatch / soc | Pixel 8a / 15 / 2025-04-05 / Tensor G3 | Pixel 8a / 15 / 2025-04-05 / Tensor G3 |
| conditions.ddp.sessionId / runIndex | session-b1179d6d / 1 | session-b1179d6d / 2 |
| conditions.ddp.serial | 45231JEKB13059 | 45231JEKB13059 |
| conditions.ddp.buildFingerprint | google/akita/akita:15/BP1A.250405.007.B1/13240308:user/release-keys | google/akita/akita:15/BP1A.250405.007.B1/13240308:user/release-keys |
| conditions.ddp.resultType | PASSED | PASSED |
| conditions.exitCode | 0 | 0 |
| conditions.elapsedSeconds | 42.1 | 36.2 |
| conditions.engineCache | `{"xnnpackWeightCache": "absent", "gpuCache": "not-loaded"}` | `{"xnnpackWeightCache": "absent", "gpuCache": "loaded"}` |
| conditions.protocolFlags | `[]` | `[]` |
| conditions.thermalRawStatus -> Final | 0 -> 0 | 0 -> 0 |
| conditions.thermalGateTimedOut | false | false |
| conditions.batteryTemperatureInitialC -> FinalC | 29.7 -> 29.7 | 30.4 -> 30.6 |
| conditions.cpuMaxFreqMHz (min / hw per policy) | policy0 1704 / 1704, policy4 2367 / 2367, policy8 2914 / 2914 | policy0 1704 / 1704, policy4 2367 / 2367, policy8 2914 / 2914 |
| conditions.cpuAffinity | taskset f0 | taskset f0 |
| conditions.screen | on-usb | on-usb |
| metrics.decodeTokensPerSecond | 20.31 | 19.52 |
| metrics.promptTokensPerSecond | 28.0 | 27.24 |
| metrics.firstTokenLatencyMS | 730.0 | 750.0 |
| metrics.promptTokenCount / generatedTokenCount | 19 / 526 | 19 / 526 |
| metrics.memoryMedianResidentMB / PeakResidentMB | 2196.79296875 / 2196.9453125 | 2176.0 / 2176.09765625 |
| metrics.coldRun | true | true |
| metrics.firstEver | true | (absent) |
| metrics.harnessStamp | 2026-08-android-cli-v1+ddp-route-c | 2026-08-android-cli-v1+ddp-route-c |

## The runbook's checks (docs/OPERATIONS.md, "Run cells on DDP", step 5)

- Session, job and execution `PASSED`; no `ddp/error-<n>.json`; `app-path-android/` holds 2 records (1 job x 2 runs)
  and no `FAILURES.txt`; `SKIPPED.txt` is empty (0 bytes).
- `engineVersion` v0.18.0 = `android/engine-pins.json` `android_pins` `litert-lm`; no `provenance.ddpMissing`;
  `model.sha256` = the unit's `sha256sum` (`modelShaSource` device) = the plan's key = the Hub's LFS sha256.
- `conditions.protocolFlags` `[]` in both runs: every policy's ceiling at its hardware maximum, so both rows pool
  (cpu-cap-rule).
- The reply text (`run<i>.engine.txt`, between `input_prompt:` and `BenchmarkInfo:`): 514 B, the same bytes in both runs.
- Scrub (C `ddp/scrub.json`): 3 files, `mac` 2 (`run1_logcat.txt` 1, the execution's `logcat.txt` 1,
  `run2_logcat.txt` 0); after it the two per-run logcats carry no private IPv4, no MAC and no IPv6 address, and their
  only keyword hits are `onetimeinitializer` (the substring `imei`, 2 in run 1). The execution's `logcat.txt` is left
  out of the commit (on disk only), as in round 2.
