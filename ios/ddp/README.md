# ios/ddp — the bench app's LiteRT-LM rows on a Developer Device Platform iPhone

[Developer Device Platform](https://docs.cloud.google.com/developer-device-platform/device-run/ios) (DDP)
runs iOS as XCTest. This directory builds the lab build of the bench app with an XCTest, submits one
session per cell with `gcloud beta device-run sessions submit xctest`, and writes the app's own records
the way the attached-iPhone runner (`scripts/bench_matrix_iphone.sh`) does.

## What is built

`ios/BenchmarkApp/project-ddp.yml` (`xcodegen generate --spec project-ddp.yml` writes
`BenchmarkApp-ddp.xcodeproj`): the app target `BenchmarkAppDDP` with the LiteRT-LM arm only and an iOS
18.0 floor, and the test target `BenchmarkAppDDPTests` hosted by it. The test
(`Tests/DDP/DDPBenchmarkTests.swift`) reads `Documents/yardstick_args.json`, a JSON array of the words
the attached-iPhone runner passes to the app after `--`, and runs the app's headless path once in the
app's process (`HeadlessAutoRun.specFromLaunchArgs` → `HeadlessRun.runAll` in
`Sources/BenchmarkApp.swift`, the code the app runs for `--yardstick-autorun`). It writes
`Documents/results/*.json` (the app's records, unchanged) and `Documents/out/`: `console.txt` (the
process's stdout and stderr during the run), `records.txt` (the records the run added) and
`yardstick.done` (the exit code). The test fails when the run ends with a code other than 0 or adds
fewer records than `--runs`.

```bash
# Vendored/LiteRT-LM: the tag's checkout + the maxNumTokens patch (scripts/bootstrap.sh step 3)
GIT_LFS_SKIP_SMUDGE=1 git clone --depth 1 --branch v0.18.0 https://github.com/google-ai-edge/LiteRT-LM.git ios/BenchmarkApp/Vendored/LiteRT-LM
git -C ios/BenchmarkApp/Vendored/LiteRT-LM apply "$PWD/ios/BenchmarkApp/patches/litert-lm-swift-benchmark-maxnumtokens.patch"
DEVELOPMENT_TEAM=<team id> BUNDLE_ID=<app id> DEVELOPER_DIR=/Applications/Xcode.app ios/ddp/build_xctest.sh
```

`build_xctest.sh` runs `xcodebuild build-for-testing` (Release, `generic/platform=iOS`) into
`ios/ddp/out/build` and zips `Release-iphoneos/`, the `.xctestrun` manifest and `BUILD_INFO` (the
LiteRT-LM version and artifact the app carries, the Xcode, the commit and the tree of
`ios/BenchmarkApp` as built) into `ios/ddp/out/BenchmarkApp-ddp-xctest.zip`. The app needs the two
memory entitlements of `BenchmarkApp.entitlements` for the 2-2.6 GB models, so `BUNDLE_ID` must be an
App ID whose provisioning profile carries them (a wildcard profile does not). The lab's default Xcode
is 26.2; build with Xcode 26 (the project resolves with it: no MLX package), which needs its iOS
platform component installed (`xcodebuild -downloadPlatform iOS`). The lab re-signs the app.

## What is submitted

```bash
ios/ddp/run_ddp_ios_lm.py --device iphone16pro-18-3 --model-id litert-community/Qwen3-1.7B --backend gpu --dry-run
ios/ddp/run_ddp_ios_lm.py --device iphone16pro-18-3 --model-id litert-community/Qwen3-1.7B --backend gpu
```

One call is one cell and one session: one device, one job, `--runs` runs in one process (run 1 cold,
runs 2 to N warm, as one launch of the app on the attached iPhone). The model ids are `models.json`'s
(the app's catalog ids; `selftest.py` compares them with `ModelCatalog.swift`).

| flag | value |
|---|---|
| `--test` | the archive, uploaded once to `<bucket>/automation/inputs/edge-llm-bench/ios-xctest/<sha256>/` |
| `--other-files-to-push` | the model from `<bucket>/automation/inputs/edge-llm-bench/models/<sha256>/<file>` (uploaded from the local HF cache when missing) to `<app>:/Documents/models/litert-lm/<org>__<repo>/<file>`; the argv file to `<app>:/Documents/yardstick_args.json` |
| `--paths-to-pull` | `<app>:/Documents/results`, `<app>:/Documents/out` |
| `--xctest-timeout` | 15m for gpu, 30m for cpu (`--timeout`); the lab takes 1m to 1h, preparation and cleanup not included |
| `--xcode-version` | `xcode-26-2` (`gcloud beta device-run software-versions list`) |
| `--labels` | harness, campaign, runtime, model, task, backend, deviceid, engine, run (the session is found by `run`) |

`--dry-run` prints the plan and the command and runs nothing. `--collect <session id>` waits for a
session submitted earlier and writes it; `--records-only results/raw/<campaign>/ddp/<session id>`
writes the records again from what was pulled, with no network. Exit status: 0 passed and written,
2 bad inputs, 3 gcloud missing or failed, 4 the job did not pass, 5 passed with no record, 130
interrupted.

## Where the records go

| path | content |
|---|---|
| `results/raw/<campaign>/device-jsonl/<record>.json` | the app's record, plus `device.ddp` (catalog id, name, OS) and `conditions.ddp` (session, job, execution, timeout, Xcode, result, run index, model object and sha256, the archive's sha256 and `BUILD_INFO`, the argv) |
| `results/raw/<campaign>/console_<runtime>_<model>_<task>.txt` | the run's console, one header per session (the attached-iPhone runner's file name) |
| `results/raw/<campaign>/ddp/<session>/` | `plan.json`, `ddp_session.json`, `args.json`, `console.txt`, `records.txt`, `yardstick.done` |
| `results/raw/<campaign>/ddp-raw/<session>/` | the pulled tree as the lab returned it, with its `system.log` and `junit.xml` (gitignored) |

Before a commit, the home directory in `ddp/<session>/plan.json` (the argv file, the campaign directory and the argv push source are absolute host paths there) is written as `~`, and `ddp-raw/` stays out: the lab's `system.log` is the unit's whole syslog, with its UDID, MAC and IP addresses and Wi-Fi network names.

`scripts/build_summary.py` reads `device-jsonl/` and names the device `<modelIdentifier> (DDP <catalog
id>)`, so a lab unit never pools with an attached phone.

The records are gated as the attached-iPhone runner gates its own (`scripts/cell_gate.py`): the four first
captures of 2026-10-16 (`results/raw/2026-10-16-ddp-iphone16pro-18-3-ios/`) are HOT, so they sit in
`device-jsonl-flagged/` with `FLAGGED.txt`, outside the summary, until a retake.

`selftest.py` runs without a device or the network: the dry runs, a stand-in gcloud for the billed
path and its failure exits, `--records-only`, and the summary's device column.
