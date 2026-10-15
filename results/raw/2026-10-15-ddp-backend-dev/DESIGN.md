# D6 DDP backend — design (round 1)

`bench matrix <cells> --ddp <device id> [--campaign NAME] [--dry-run]` → `android/ddp/run_ddp.py` (Route C:
own request body + static wrapper `android/ddp/ddp_cell.sh` + own LiteRT-LM build). Decisions D1–D11:
`LANE.md` §1. API facts: SDK 587.0.0 `devicerun_v1alpha_messages.py` (line numbers below).

## Files

| file | role |
|---|---|
| `android/ddp/devices.json` | DDP id → schedule key (pixel8a / s26 / null), display, product (D8) |
| `android/ddp/ddp_cell.sh` | the job's `androidNativeBinary`: N runs of one cell, run_once's sampler shell per run |
| `android/ddp/run_ddp.py` | cells → jobs → sessions; dry-run plan; upload, POST, poll, pull, records |
| `android/ddp/record.py` | pulled `ddp-out/` + session report → result.v1 records |
| `android/ddp/selftest.py` | fake gcloud + fake REST + fake bucket; host run of the wrapper; summary in temp |
| `android/bench/run_cell.py` | `sampler_shell()` taken out of `run_once` (D9); `cpu_conditions(console, mask=None)` |
| `android/bench/run_campaign.py` | `skip_on_device(..., key=None)`: exclude-on by schedule key |
| `scripts/build_summary.py` | `device` column of a record with `device.ddp` (D5) |
| `bench` | `matrix --ddp <id> [--dry-run]` |

## cell → job → session (D6, D7, D8)

- Rows: `run_campaign.parse_cells`, android only. Skip reasons, first match wins, printed and in `SKIPPED.txt`:
  runtime ≠ litert-lm (`runtime-not-wired-on-ddp`; llama.cpp needs its b8999 build pushed) → `exclude=` / `manual=`
  → backend=npu / engine-build= (`side-build-not-wired-on-ddp`) → `anchor=1` (`no-session-anchor-on-ddp`, D6) →
  `exclude-on=` naming the id's schedule key (`skip_on_device(device_key=…)`, logged with the key) → on an id
  without a key, any `exclude-on=` (`ddp-device-key-unknown`).
- One job = one cell = `runs=` launches on one lab unit (default 3, run_campaign's default); one session per ≤ 8
  jobs (`--jobs-per-session`), sessions submitted one after another.
- `matrices/dashboard-text-v1.cells` (30 android rows): akita-35 (pixel8a) → 8 jobs, 1 session, skip 22 (llama.cpp
  10, exclude-on 12); m1q-36 (s26) → 16 jobs, 2 sessions, skip 14 (llama.cpp 10, exclude-on 4).
- executionTimeout = `--job-timeout` 3600 s (lane cap; API "Default value: 5 min. Range: [1 min, 3 hours]",
  line 292). Wrapper per-run timeout = min(1800, (executionTimeout − cooldown × (runs − 1) − 120) / runs);
  `--budget` = executionTimeout − 120: the wrapper starts no run (and no cooldown or gate wait) that would end past it.
- Estimate per job (dry run): E × runs × 1.5 + cooldown × (runs − 1) + 300, E = the largest `elapsedSeconds` of the
  cell's local records at the pinned tag on the schedule key's phone (else any Android phone at the tag, else 600).

## Wrapper `ddp_cell.sh` (D1–D4, D9, D10)

- `#!/system/bin/sh`, no arrays, no `local`; always exits 0 (run exit codes in `run<i>.exit`).
- Args: `--runs --cooldown --mask=<hex|none> --env --binname --dir --output_dir --timeout --thermal_wait=600
  --cpucap_wait=300 --budget --cell` and `--command=<engine_command() core>` LAST: the API says args "will be
  appended to the command line that invokes the binary" (line 283), so the wrapper joins every argv element after
  `--command=` with one space — the same core whether the platform keeps the element whole or splits it at spaces.
  run_ddp.py refuses a command or env with a character outside `[A-Za-z0-9_./=:,+-]` (and a space in env).
- Start: `chmod 755` both binaries → `provenance.txt` (date, 7 getprop values, `uname -a`, `command -v taskset`,
  `command -v timeout`, argc and every argv element, `sha256sum` of the 9 engine files, the model, the prompt).
- Run i = 1..N: cooldown (i > 1) → thermal gate (`Thermal Status:` 0, ≤ thermal_wait, 30 s polls; timeout
  recorded) → cpu cap wait (`policy*/scaling_max_freq` vs `cpuinfo_max_freq`, ≤ cpucap_wait, 10 s polls) →
  `logcat -c` → `run<i>.state` start (epoch, `dumpsys battery`, mWakefulness, stay_on_while_plugged_in, thermal) →
  `sh -c "<sampler shell>" > run<i>.log 2> run<i>.err` → `run<i>.exit`, `run<i>.engine.txt` (= run_out.txt),
  `run<i>_logcat.txt` → `run<i>.state` end (epoch, battery, thermal).
- Sampler shell = `run_cell.sampler_shell(cmd, binname, f"{DEV_DIR}/run_out.txt", env, taskset_prefix,
  timeout_prefix, sockets=False)` with taskset_prefix `taskset <mask> ` (D3) and timeout_prefix
  `timeout -k 5 <t> `: run_once calls the same function (D9); the wrapper builds the string from its args and
  `--print_shell=1` prints it; the selftest checks it byte-equal to `sampler_shell()` for every planned job (D2).
- Device layout (D4): `/data/local/tmp/llmbench/` = 9 engine files flat, `models/<repo>_<file>`,
  `prompts/<task>.txt`; output `/data/local/tmp/llmbench/ddp-out/` (pulled).

## Push list and bucket (content-addressed, nothing deleted: D11)

- Engine: `<BENCH_ANDROID_BIN_DIR>/<android_pins tag>/` 9 files, each sha256 checked against
  `android/engine-pins.json` (tool fields + `so_files`) before anything else; SHA256SUMS is not read.
- Model: `hf_hub_download(local_files_only=True)` in a dry run (sha = blob name), normal download + Hub size
  check + sha256 in a real run. Prompt: `prompts/text/<task>.txt`. Wrapper: `android/ddp/ddp_cell.sh`.
- `gs://litert-edge-portal-devicerun/automation/inputs/edge-llm-bench/{engines/litert-lm/<tag>/<sha256>/<name>,
  models/<sha256>/<file>, prompts/<sha256>/<task>.txt, wrapper/<sha256>/ddp_cell.sh}`; real run: `gcloud storage
  ls <object>` per object, `gcloud storage cp` the missing ones only.
- Per job: androidPushFiles 11 (limit 50, line 382), androidPullFiles 1 (`.../ddp-out`, limit 10, line 370),
  androidLogcat; the wrapper is `androidNativeBinary.gcsInputFile`.

## Request (09-17 shape; field names checked against the contract by the selftest)

`sessionConfig {displayName, outputDirectoryConfig.gcsOutputDirectory.path = gs://<bucket>/automation/sessions,
jobConfigs[] {displayName, action.androidNativeBinary {androidNativeBinary.gcsInputFile.path, args (≤ 100, line
284), executionTimeout "<s>s"}, allocationConfig.deviceConfigs[] {requirement.deviceId, actions[push, pull,
logcat]} (one action per type, line 1000), labels}}`. displayName ≤ 63 B, `^[A-Za-z0-9][A-Za-z0-9_-]*$` (the
contract's docstring prints the regex without its brackets, lines 1787 / 2194; docs/ddp-integration.md 392 has
the REST form). Labels ≤ 16 (line 1775): harness, campaign, cell, runtime, model, task, backend, devicekey,
deviceid, engine — values lowercased to `[a-z0-9_-]`, ≤ 63 B (the 09-17 request wrote `litert-lm-v0-17-0-own-build`).
REST: `POST {endpoint}/projects/<p>/locations/global/sessions`, token `gcloud auth print-access-token`, poll
`GET {endpoint}/<operation>` every 30 s (`ddp/operation-<n>.json` rewritten), `GET …/sessions/<id>`,
`gcloud storage cp -r gs://<bucket>/automation/sessions/<id> <campaign>/ddp/`; 4xx → body verbatim in
`ddp/error-<n>.json`, stop. Jobs may hold several executions (RetrySettings, line 2122): one record set per execution.

## Record (`record.py`) vs the adb record

- Key set = run_cell.py 1406–1473 extended form (roundIndex / launchIndex null, launchID per launch, iteration
  rows for 1K) + `conditions.ddp {sessionId, jobId, executionId, deviceId, deviceKey, buildFingerprint, serial,
  product, jobStartTime, jobEndTime, executionStartTime, executionEndTime, executionTimeout, resultType, runIndex}`
  + `device.ddp {deviceId, buildFingerprint, serial}` + `provenance.{ddpSessionDir, wrapper, wrapperSha256}`.
- From the device: getprop → `device.*`; battery / thermal / screen per run from `run<i>.state` (device_probe's
  regexes and vocabulary); `conditions.cpuAffinity` = the applied mask; cpu reads = `cpu_conditions(console,
  mask)`; metrics = `parse_litert` / `context_prompt_results`; text check = `context_prompt_texts` +
  `text_integrity` (1K), `.decoded.txt` beside; `rawLog` = copy of `run<i>.log`.
- Witness: provenance sha of the launched tool → pins tag (`run_cell.pin_key` field) and every `so_files` entry
  must match, else `unknown (…)` in observed_engine's wording; `model.sha256` = provenance sha, `modelShaSource`
  "device". `harnessStamp` = `2026-08-android-cli-v1+ddp-route-c`.
- firstEver (D10, the adb marker rule on a clean unit): every run until the first clean exit; run 1 always.
- Absent value → null, reason in `provenance.ddpMissing` (never estimated). Filename `<stem>_<UTC start>_run<i>
  [_iter<k>].json`, stamp `%Y-%m-%dT%H-%M-%S` (the wrapper's epoch seconds; no sub-second digits invented);
  `timestamp` = the run's start (run_cell stamps a record when it writes it, after the run).

## Summary (D5)

`build_summary.build_device`: `device` = `"<modelIdentifier> (DDP <deviceId>)"` when the record has `device.ddp`;
`render_leaderboard` / `render_dashboard` untouched — `(platform, device)` tree keys differ from the attached
phone's, so `arm_row` never pools them; `render_dashboard.devices_for` (250–261) lists the schedule's phones and
then every other device of the summary, so a DDP unit shows as a column of its own (not ignored, never pooled).
