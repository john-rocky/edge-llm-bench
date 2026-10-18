# Operations — running this repo as a standing benchmark

The runbooks a team needs to operate this repo continuously: release
regressions, adding models/arms/devices, and the parts that stay manual. The
measurement rules live in `methodology/fairness-rules.md` (11 rules + the
working-rule slug table); this file is only *how to run the machine*.

## The core loop

```
./bench doctor               # preflight: what is missing, with the fix command
./bench release-watch        # upstream releases vs environment.lock.json pins
./bench matrix  <cells>      # standing matrix -> summary -> RESULTS -> LEADERBOARD
./bench regress <cells> --engine <arm> --version <v> --baseline <selector>
./bench profile <cells> --campaign <name>   # LiteRT-LM per-op profile pairs (Android) -> profiles/PROFILE.md
```

`doctor` exists so a run never dies mid-capture on a missing tool, binary, or
device — every failure it reports comes with the command that fixes it. A
`matrix` invocation whose platform filter matches zero cells now refuses
loudly instead of rebuilding the summary and looking like a capture.

- Cell files: `matrices/*.cells` (grammar: `matrices/README.md`). CI validates
  them (`cells-valid`).
- Everything a run produces is a schema-v1 JSON under `results/raw/<campaign>/`
  plus its console log — a number without a stored report is not a measurement
  (stored-report-rule).
- `results/summary/*.csv` is the derived accumulation layer (CI: `summary-fresh`);
  `LEADERBOARD.md` renders from it (CI: `leaderboard-check`).
- Regression verdicts persist under `results/regression-reports/<date>-<engine>-<ver>/`
  (report.md + verdicts.json + invocation.txt) and flatten into
  `results/summary/history.csv`.

## Runbook: an engine shipped a release (worked example: LiteRT-LM v0.16.0)

1. `./bench release-watch` — confirms the drift (v0.15.0 pinned, v0.16.0 out).
2. Bump the pin where the arm is acquired:
   - iOS/Mac: `LITERTLM_TAG` in `ios/BenchmarkApp/scripts/bootstrap.sh`, then
     rebuild the app (`bootstrap.sh` + the xcodebuild command in `CLAUDE.md`)
     and the Mac CLI (`scripts/build_yardstick_mac.sh`) **on real hardware** —
     there is no CI build (hosted runners lack the required Xcode).
   - Android: `LITERTLM_TAG=v0.16.0 android/scripts/build_litert_lm_main.sh`
     (it writes the tag's `android/engine-pins.json` entry), then
     `android/scripts/deploy_litert_lm_android.sh <tag> <serial> --reset-caches` on every
     phone: it pushes the two tools and the seven `.so` files to the flat
     `/data/local/tmp/llmbench/`, compares the phone's sha256 of all nine with the pin
     (exit 1 on any mismatch) and deletes the bundles' engine caches with their firstEver
     markers; `--check` later compares without pushing. Bump the tag in
     `android/engine-pins.json` `android_pins` (what `BENCH_SITTING=1`'s pin check expects)
     and `environment.lock.json` `arms.litert-lm.android`. Then attach `android/bin/<tag>/` (+ a full
     SHA256SUMS) to a GitHub release `android-litert-lm-<tag>` — upstream
     ships no Android binary, so the release asset is what lets anyone else
     skip the bazel+NDK build.
   - Before the first sitting on the new tag, run one launch of each Android
     runner path (short chat, the 1024-token text task, the 1024/256 protocol
     pair) on one phone, add its console to `android/bench/testdata/litert-lm/`
     with a selftest case, and read its `Prefill Turn 1` line against the
     prompt's token count. v0.18.0 printed `BenchmarkInfo:` on a glog-prefixed
     line and added an `Aggregated BenchmarkInfo` block, which the parser of
     the previous version read as zero iterations on the 1024-token task: null
     token counts, an empty text and a failed text check (fixed in 8874bce).
   - llama.cpp (worked example 2026-10-19, b8999 -> b11721). Upstream publishes two kinds
     of release: the b-builds (GitHub prereleases, several a day, with the binaries) and
     versioned releases with notes and no binaries (v0.7.0 on 2026-10-15 is the commit of
     b11669; its one asset, `nightly-tag.txt`, says so). `./bench release-watch` reads the
     newest b-build that carries the xcframework, android-arm64 and macos-arm64 assets
     (`scripts/release_watch.py` `latest_with_assets`); `releases/latest` would name the
     versioned one. Pin that b-build:
     - Registry: `environment.lock.json` `arms.llama.cpp` (tag, `since`, the artifacts and their
       sha256, the replaced pin under `previous`, which `scripts/session_check.py` reads for a
       sitting before `since`; a platform block `mac` / `ios` with its own `since` for each
       build that moves on its own day, as `arms.litert-lm` has: on 2026-10-19 the Mac moved
       with its yardstick build and the iPhones stayed on b8999 until the 18 Pro's app was
       installed), `android/engine-pins.json` `android_pins`, and the default tag in
       `ios/BenchmarkApp/scripts/bootstrap.sh` and `android/scripts/fetch_llama_android.sh`.
     - iPhone / Mac: unzip the release's `llama-<tag>-xcframework.zip` (it holds
       `build-apple/llama.xcframework`) into `ios/BenchmarkApp/Vendored/llama.xcframework`, the
       old one renamed to `llama.xcframework.<old tag>`, and write the tag into
       `Vendored/llama.xcframework.tag`: `stamp_engine_pins.sh` reads only that sidecar, so a
       side build tree with its own copy of the file (`.build/dd-ios-0180-18pro/src`) needs it
       too. Then `scripts/build_yardstick_mac.sh` and the app build; records stamp
       `engineVersion <tag>`, `engineArtifact llama-<tag>-xcframework.zip`. The stamp is the
       pins file the build's pre-build script wrote into its own tree, not the binary: read
       what the binary loads (`otool -L`, `DYLD_PRINT_LIBRARIES=1 yardstick version`, the
       loaded dylib's sha256) before a registry line. On 2026-10-19 the main tree's
       `CoreAIRuntime.swift` did not compile against its `Vendored/coreai-models` (0.2.0), so
       the b11721 yardstick was built from the iPhone 18 Pro's side tree
       (`.build/dd-ios-0180-18pro/src`, Core AI stock 1.0.0-10-gbd3c539) into
       `.build/dd-mac-b11721`; its records stamp from that tree's `Vendored/engine-pins.json`
       (`BENCH_ENGINE_PINS_FILE`).
     - Android: `LLAMA_TAG=<tag> android/scripts/fetch_llama_android.sh` pins the tools and their
       libs (`so_files`), then push the tools and every `.so` to each phone's flat dir and read
       the witness line (`android/README.md`, "Push runtime to the device"). From b10903 on the
       tools are 7 KB launchers (b11721's byte-identical to b10903's): the witness tells the
       builds apart by the libs, and a lib left from the old build stamps `unknown`.
     - Re-measure the arm's weekly rows through the job route: the session anchor row and the
       arm's rows of the weekly set, byte-identical (`matrices/dashboard-llama-<tag>-{mac,ios,android}.cells`).
       The Android session anchor is the llama.cpp row, so a phone's first sitting on the new
       build has no same-build reference (`dashboard_job.admit`: admitted when nominal).
   - ONNX Runtime GenAI: Android = the versions and sha256s at the top of
     `android/ortgenai/build_android.sh`, then push `android/bin/ortgenai-<version>/`
     to `/data/local/tmp/llmbench/ortgenai/` per `android/README.md` ("ONNX Runtime
     GenAI") and add its `android/engine-pins.json` entry; Mac = a venv with the new
     pip versions (`ORTGENAI_PYTHON`) and `VERSIONS` in `scripts/ortgenai_mac.py`,
     which refuses any other installed version (`docs/ortgenai-arm-v1.md`).
   - Record artifact sha256s in `environment.lock.json` (the registry); the
     build stamps the *observed* pins into every row (the witness) — if they
     disagree, the row is telling you the truth.
3. Speed/regression capture:
   `./bench regress matrices/release-regression-litert.cells --engine litert-lm --version v0.16.0 --baseline campaign:<last-litert-campaign>`
   - Anchors run first; cross-session verdicts are anchor-normalized
     (`--anchors matrices/anchors.cells` is applied automatically). An anchor
     whose runtime is the engine under test is marked CONFOUNDED — that is why
     `anchors.cells` carries a non-litert anchor per platform.
   - Exit 1 = REGRESSION somewhere; read the report dir before believing or
     disbelieving it (UNRELIABLE = spread too wide, throw out and re-run).
4. Quality gate (absolute, not anchor-relative):
   bump the instrument pin in `tools/litert-mac-verify/Package.swift`, rebuild
   it, then run `scripts/parity_gsm8k.py --which int4 --n 100` for the pinned
   checkpoints and diff with `scripts/regression_diff.py quality
   --candidate-dir <fresh reports>` (>2-3 pt drop at n=100 is real;
   budget/mode mismatches refuse to score — budget-mode-rule). The archive
   repo's `./reproduce mac gsm8k-e2b-yardstick --regress` wraps the same flow
   with the published Gemma-4 baselines.
5. Commit the new campaign dir + regression report + regenerated summary/
   RESULTS/LEADERBOARD. CI holds it all together.

## Runbook: run an endurance baseline (Mac, LiteRT-LM)

Protocol: `methodology/endurance.md` (30-min multi-turn sessions; decay,
memory slope, per-turn degeneracy; LiteRT-LM only, no cross-runtime rows).

1. `./bench doctor --platform mac`; machine must be quiet (the runner's
   heavy-pipeline guard is necessary but not sufficient for a 30-min session
   — check `top` yourself).
2. Optional power trace: start the `sudo powermetrics` sidecar from
   endurance.md *before* the campaign (root; runners never assume it).
3. `CAMPAIGN=<date>-mac-litert-endurance ./scripts/bench_matrix_mac.sh run
   matrices/endurance-mac.cells` — each cell is ONE session (`runs=1`,
   enforced by validate_cells; sessions are never pooled). Expect ~2 h for
   the three-model baseline including cooldowns.
4. Per cell the campaign dir gets `<cell>.jsonl` (one schema-v1 session
   record, `endurance` block carries the verdicts) plus
   `<cell>.turns.ndjson` (per-turn series, written as turns complete — a
   crash keeps its evidence). The cell gate applies: HOT quarantines and
   re-runs once; a crash/hang session exits 1 and lands in FAILURES.txt
   while its record stands (failed-runs-stay).
5. Read verdicts from the session records (`endurance.status`,
   `decodeDecayPercent`, `memorySlopeMBPerTurn`, `degenerateTurnCount`);
   read the sidecar series before naming a cause — a sawtooth that resets at
   rollover is KV, not a leak.

Known structural findings (2026-09-01 baseline, v0.16.0 — all four filed
upstream; evidence in the campaign's records + `diagnostics/`):

- Bundles whose embedded template renders assistant history differently
  depending on position cannot hold a multi-turn conversation at all —
  turn 2 dies with `INTERNAL: The new rendered template string does not
  start with the previous...` (litert-community Qwen3-0.6B
  `qwen3_0_6b_mixed_int4`: the stock Hugging Face Qwen3 template renders
  the trailing assistant turn with a `<think>` block that disappears once
  the next user message is appended; the engine compares two history
  renders, not the live prompt). The endurance row records it as
  `status=crash`; that row is the datum, not a capture bug. → LiteRT-LM
  #3443 (root cause + same-weights fix posted 2026-09-02).
- A bundle's real context ceiling can sit below the accepted
  `maxNumTokens` (gemma-4-E2B: 2048 under a 4096 request) and there is no
  API to query it; the harness's kv-wall rollover absorbs the resulting
  mid-conversation `FAILED_PRECONDITION`. → #3444.
- Structured think-prefix bundles (granite-4.2-3b): history re-render keeps
  the pre-opened `<think>` unclosed and drops the thought, so coherence
  collapses silently at ANY turn cap — verified with the cap-1024 probe and
  `yardstick debug-render`. → #3445. Reproduced on Android (S26, gpu,
  2026-09-01 baseline): degenerate from turn 2, 32 of 46 turns, history
  growing ~29 KV tokens/turn — the collapse is in the shared template
  layer, not a macOS-path artifact.
- ~1 MB of footprint is retained per conversation rollover (gemma, 197
  cycles → +198 MB/30 min). → #3446.

## Runbook: run an endurance baseline (Android, Galaxy S26)

Protocol: `methodology/endurance.md` (Android section — same task, script,
cap, and budgets as the Mac baseline; VmRSS memory basis, host-sampled
thermal).

1. Build + push the harness driver once per tag:
   `android/scripts/build_litert_lm_endurance.sh`, then push
   `android/bin/<tag>/litert_lm_endurance_main` next to the engine binaries
   (`android/README.md`, Endurance section). The pins entry gains the binary
   AND driver-source sha256 (registry/witness).
2. On a fresh (model, backend): run one short-chat cell first so the
   engine-cache build doesn't ride the 30-minute session (it would be
   labelled `firstEver` honestly, but the session is better spent measured).
3. `CAMPAIGN=<date>-s26-endurance BENCH_CPU_MASK= python3
   android/bench/run_campaign.py matrices/endurance-android.cells` —
   `BENCH_CPU_MASK=` because the S26 runs unmasked (devices/galaxy-s26.md).
   Each cell is ONE session; expect ~1.5 h for the two-model baseline
   including cooldowns. USB stays attached; don't touch the phone
   mid-session (a USB renegotiation kills the stream — the partial series
   stays on disk, but the session is over).
4. Per cell: `<cell>.json` (schema-v1, `endurance` block carries the
   verdicts), `<cell>.turns.ndjson` (written as turns complete), raw log.
   A crash/hang session exits 1 into FAILURES.txt while its record stands
   (failed-runs-stay). The cell gate applies as usual.
5. Read verdicts like the Mac baseline (`endurance.status`,
   `decodeDecayPercent`, `memorySlopeMBPerTurn` — resident basis on
   Android, `memorySlopeBasis` says so), and read the sidecar series before
   naming a cause: the ramp-vs-leak, one-token-turn, and rollover-cost
   traps from the Mac baseline apply unchanged (endurance.md, "Reading the
   series").

## Runbook: the dashboard recurring job (each device once a week, first free device first)

Design, cadence, device choice, admission and rerun rules:
`docs/dashboard-recurring-job-v1.md`. Config: `ops/dashboard-v1/schedule.json`.

```
./bench dashboard-job auto [--dry-run]                       # what launchd runs at 02:00 and 05:30 every night
./bench dashboard-job <m4max|s26|pixel8a|iphone17pro> [--dry-run] [--once]   # that device, regardless of the week
./bench dashboard                       # re-render DASHBOARD.md (local) any time
```

One invocation is one sitting on one device. `auto` chooses it: among the
devices with no admitted dashboard session since Monday 00:00 local, the
attached, unheld ones — the iPhone only in its 05:00–08:00 window after 4 h
without a record, the Mac only while no heavy export pipeline runs — oldest
last-admitted session first (never measured = oldest). A candidate whose
preflight says busy or not ready is passed over for the next one; when every
pending device is busy the firing polls (15 min, up to 2 h) and chooses
again; nothing pending exits 0 with no ledger line. `--dry-run` prints the
choice with every device's state and the chosen device's plan, and is the way
to see what tonight's firing would do.

The sitting: preflight (attached, unlocked, not held by a sibling lane, no
foreign engine process, storage, host runner idle) → on a phone whose
schedule entry carries `reboot_before` (the Pixel 8a), a reboot under the
hold when its uptime is past the limit, with memory figures logged before
and after → the session anchors as a short campaign → admission of the sitting against the newest admitted
session's anchor on the same engine build (none: first session on that build, admitted;
the build-blind choice stays in `SESSION.json` as `reference_any_version`) → the dashboard cells (or the storage halves, rotating
pushed copies out between them) → `SESSION.json` in every campaign dir it
created → `logs/dashboard-job/ledger.tsv` → dashboard re-rendered. Exit 0
admitted, 3 busy, 4 aborted at admission (retried once), 5 device needs a
human, 6 timeout. A firing whose pending devices are all held or detached
leaves a ledger line under device `auto` with the reasons; the decision log
is `logs/dashboard-job/<date>-auto.log`, the sitting's `<date>-<device>.log`.
One sitting per device (`.job.lock.<device>`): a second run on a device
being measured exits 3, while sittings on different devices may run side by
side (a phone sitting is only adb traffic on the host); `auto` serializes
its choice with `.choose.lock` so two autos never pick the same device.

Core AI cells (v2 of the cells file) need their bundles side-loaded before
a sitting — Mac under `~/.cache/edge-llm-bench/CoreAIModels/<folder>/`
(`BENCH_COREAI_MODELS_DIR`; a local directory outside iCloud Drive, see Known
limits), phone under the app's `Documents/CoreAIModels/<folder>/` (recipe:
`docs/dashboard-cells-v1.md`, "Core AI arm (v2)"). The job does not stage: a missing folder is a `SKIPPED`
line on the Mac and a failed cell on the phone, never a refused sitting.

The job never commits or pushes: review the new campaign dir(s) and the
regenerated `results/summary/` the next morning and commit them with a
message that states what ran and what reproduced (public text carries no
cross-runtime ordering). Rebuild the summary from the committed tree only:
a campaign pushed without its summary rebuild turns the data-pipeline CI red
(2026-09-13, six runs in a row), and a rebuild inside a checkout that holds
another session's uncommitted campaign dirs bakes their rows into the CSV
and fails the same CI job on the next push (2026-09-18, seven runs in a row:
8 rows from three uncommitted 2026-09-12 smoke dirs). `build_summary.py`
reads the disk, not git, so rebuild from an export of the index: stage the
campaign dirs you are about to commit by explicit path, check
`git diff --cached --name-only` lists only your paths, then run
`d=$(mktemp -d) && git checkout-index -a --prefix="$d/" && python3 "$d/scripts/build_summary.py" && cp "$d"/results/summary/* results/summary/ && rm -rf "$d"`
and commit the summary together with those dirs. The export holds HEAD plus
what is staged and nothing untracked; it needs no clean tree. The same rule
covers every commit that touches `results/summary/`, hand-run campaigns
included. Read `FLAGGED.txt` for `DEGENERATE` before trusting
a new arm's rate: the cell gate flags a capture whose output is a repetition
loop (an engine can report a fast rate while generating garbage — seen on
2026-09-08), and such a cell is never retried, only marked. The launchd template that fires `auto` is
`ops/dashboard-v1/com.edge-llm-bench.dashboard-v1.plist.template`; enabling
it is an owner step, documented in the template header. To change the firing
times, edit `schedule.json` `slots` and the template together, re-render the
plist and `launchctl bootout` + `bootstrap` it (the running agent keeps the
old times until then).

## Runbook: run cells on DDP (a lab phone, no adb)

What the route pushes, runs and records, and how its rows differ from an
attached phone's: `docs/ddp-integration.md`, "Route C as `bench matrix --ddp`".
One `--ddp <id>` invocation turns the cells file's Android LiteRT-LM rows into
Device Run sessions of at most 8 jobs on that catalog id; a session is billed
to the Cloud project it runs in.

Prerequisites (the host never talks to a phone, so no adb and no gtimeout;
a Linux host such as a Cloudtop or gLinux machine has what the route calls;
the first session from a Linux host, an Ubuntu 24.04 container with no adb,
ran on 2026-10-16: `results/raw/2026-10-16-ddp-linux-first-run-akita-35-android/`):

- gcloud, signed in (`gcloud auth login`); the driver calls only
  `gcloud auth print-access-token`, `gcloud storage ls` and `gcloud storage cp`
  (no `beta` component; listing the catalog with
  `gcloud beta device-run devices list` needs it).
- An account that can create Device Run sessions in the project (the API
  enabled once: `gcloud services enable devicerun.googleapis.com --project <p>`)
  and read and write the bucket. The sessions so far used the project's own
  Device Run bucket (`gs://<project>-devicerun`, the name `gcloud beta device-run`
  creates); a bucket outside the session's project is untried.
- python3 >= 3.10 with `huggingface_hub`, in a venv as README step 1 has it
  (`python3 -m venv ~/elb-venv && . ~/elb-venv/bin/activate && pip install huggingface_hub`;
  outside a venv, Ubuntu 24.04's pip stops with `externally-managed-environment`);
  a gated Hub repo needs a token on the host. `./bench doctor --platform ddp`
  checks the python version, gcloud and its sign-in, `huggingface_hub` and the
  9 engine files below (not the project's API or the bucket).
- The pinned LiteRT-LM Android files in `android/bin/<tag>/` (the tag is
  `android/engine-pins.json` `android_pins`), or in `$BENCH_ANDROID_BIN_DIR/<tag>/`:
  the release asset `android-litert-lm-<tag>` ("Engine acquisition" in
  `android/README.md`) or a source build. The driver checks all 9 files against
  the pins before it uploads anything.

1. **Dry run.**
   `./bench matrix <cells> --ddp <id> --dry-run --project <p> --bucket gs://<b>`.
   Read the skipped rows and their reasons, then per job the cell, `runs`,
   the cooldown, `executionTimeout` (3600 s by default), the per-run timeout,
   the pushes (bytes, sha256, bucket object) and the estimate, then per
   session the request body. The summary line's `deviceMinutes` is a sum over
   the jobs: the platform runs a session's jobs side by side (8 units at once
   on 2026-10-15), so the wall time is near the longest job, not the sum.
   On a fresh host the models show `"uncached"`; the billed run downloads them.
2. **GO.** The project owner approves the spend before anything is posted:
   how many sessions (one POST each), how many jobs, `executionTimeout` per
   job, and the bytes to upload (`uploadBytes`; objects already in the bucket
   are not uploaded again).
3. **Billed run.** Drivers for two ids may run side by side; start the
   second once the first has posted (the first's uploads are then in the
   bucket, so the second uploads nothing twice):
   ```bash
   mkdir -p ~/ddp-logs
   nohup "$PWD/bench" matrix <cells> --ddp <id> --campaign <date>-ddp-<id> \
       --project <p> --bucket gs://<b> > ~/ddp-logs/<date>-ddp-<id>.log 2>&1 &
   ```
   The campaign dir is `results/raw/<date>-ddp-<id>-android/`. `bench` starts
   the driver by its full path, so `pgrep -f "$PWD/android/ddp/run_ddp.py"`
   finds this checkout's driver (a bare `bench matrix` pattern also matches
   other lanes' drivers). The exit code is 0 when every run is clean, 1 when a
   run is not (`app-path-android/FAILURES.txt`) or the driver stopped on an
   error it prints (a sha mismatch; a 4xx answer, kept in `ddp/error-<n>.json`),
   2 when it refused to start (no android rows in the file, or the campaign
   dir already holds records).
4. **Poll and resume.** The driver polls the operation every 30 s and logs
   "not done" until the session ends (`ddp/operation-<n>.json` is rewritten at
   each poll), then pulls and writes the records. If the driver stops while a
   session runs, poll that session without a second POST:
   `android/ddp/run_ddp.py <cells> --device <id> --campaign <date>-ddp-<id>-android --project <p> --bucket gs://<b> --resume <operation name>`
   (the name is in `ddp/operation-create-<n>.json`). It polls, pulls and
   records that session, then submits the plan's later sessions as usual (they
   are billed), and appends the skip lines to `SKIPPED.txt` once more.
   `android/ddp/run_ddp.py --records-only results/raw/<campaign>` writes the
   records again from what was pulled, with no network.
5. **Read the outputs.** `ddp/session-<n>.json`: the session, every job and
   every execution `PASSED`; no `ddp/error-<n>.json`; `app-path-android/` holds
   jobs × runs records (× 2 for a 1K cell) and no `FAILURES.txt`. In the
   records: `engineVersion` is the pins tag, not `unknown (…)` (the witness);
   `model.sha256` is the plan's; no `provenance.ddpMissing`;
   `conditions.ddp.serial` / `buildFingerprint` name the unit of each job;
   `conditions.protocolFlags` (`cpu-capped`, `cpu-capped-at-start`) and the
   summary's `cpu_cap_drop_pct` say whether a run pools (cpu-cap-rule);
   `conditions.thermalRawStatus` → `thermalRawStatusFinal` and
   `thermalGateTimedOut`; `conditions.engineCache` for every run after a
   job's first; a 1K record's `conditions.textCheck`, and a short-chat raw
   log's reply text (the rate never reads it).
6. **Summary from the git index.** `bench` rebuilt `results/summary/` from
   this checkout's disk; put it back (`git checkout -- results/summary`),
   stage the campaign dir by its path without the execution-level
   `logcat.txt` files (the unit's whole log, 0.3–14.5 MB each on 2026-10-15;
   the campaigns so far keep them on disk and in the bucket only):
   `git add -- <campaign dir> ':(exclude)<campaign dir>/ddp/*/logcat.txt'`
   (the per-run `run<i>_logcat.txt` files stay staged); check that
   `git diff --cached --name-only` lists only that dir, then rebuild the
   summary from the index as in `CLAUDE.md`
   (`d=$(mktemp -d) && git checkout-index -a --prefix="$d/" && python3 "$d/scripts/build_summary.py" && cp "$d"/results/summary/* results/summary/ && rm -rf "$d"`)
   and stage `results/summary/`. The new rows carry the device
   `<model> (DDP <id>)`.
7. **Hygiene.** `ddp/scrub.json` counts what `android/ddp/scrub.py` replaced
   in each pulled logcat (SSIDs, hashes, IPv6, MACs, BSSID parts, private IPv4,
   SIM / device ids); the original bytes are in `<campaign dir>/ddp-raw/`,
   which `.gitignore` keeps out: never `git add -f` it. The staged files carry
   no host user name (`git grep -l --cached "$(basename "$HOME")" -- <campaign dir>`
   prints nothing).
8. **Commit** the campaign dir and `results/summary/` by explicit path (never
   `git add -A`), with a message that states what ran and what reproduced and
   no ordering of runtimes or devices.

Measured (2026-10-15, `results/raw/2026-10-15-ddp-backend-dev/ROUND2.md`,
`ROUND3.md`): the smoke session (1 job of 2 runs on `akita-35`) took 22.6 min,
of which 2.9 min of pushes and a 10-min thermal gate before run 2; the slice
sessions (8 jobs of 3 runs each, side by side) took 37 min on `akita-35` and
30 min on `m1q-36`, with 110 and 194 device-minutes in their executions (the
`m1q-36` figure holds 24 CPU-cap waits of 300 s, since set to 0 s for that id).
From the POST to the records on disk: 24 min (smoke), 38 min (both slice
sessions). Uploads: 2.21 GB the first time (12 objects), 3.57 GB more for the
slice's two new models and its prompt; the second slice driver found all 15
objects in the bucket and uploaded nothing.

Cost: the device time is in the session report's job and execution
`startTime` / `endTime` (`ddp/session-<n>.json`); what a device-minute costs is
in the project's billing. The session's output folder in the Cloud Console is
`https://console.cloud.google.com/storage/browser/<bucket>/automation/sessions/<session id>/`.

A person decides: the GO for every billed session, a pin bump and the release
asset that goes with it (the driver pushes the tag `android_pins` names, and
only after the sha check), and any cleanup of the bucket (the driver never
deletes; inputs stay under `automation/inputs/edge-llm-bench/`, session
outputs under `automation/sessions/`).

## Runbook: add a model

1. Speed axis: add a `ModelInfo` per runtime to
   `ios/BenchmarkApp/Sources/Models/ModelCatalog.swift` (id, hfRepoId,
   quantization label — quant-per-arm-rule; the label is part of the result).
   Side-loaded artifacts (`hfRepoId: ""`) need a staging step and `local=1` in
   cells.
2. Display identity: if several orgs ship the same logical model, add a
   pattern to `LOGICAL_MODELS` in `scripts/bench_common.py` (order matters —
   builds that must not pool, like QAT-vs-PTQ, get distinct patterns).
3. Cells: add rows to the relevant `matrices/*.cells`; interleave arms within
   the model block; give >=3B models `cooldown=300`. Run
   `python3 scripts/validate_cells.py` (CI does too).
4. Quality axis (optional per model): run `scripts/parity_gsm8k.py` per arm
   with `GSM8K_MODEL_ID=<catalog id>` and `GSM8K_QUANT=<label>` so the report
   carries the join key (quality<->speed joins on model_id + runtime +
   thinking). Validate answer extraction on a few items first — chat-template
   and thinking-mode defaults differ per arm (budget-mode-rule; checklist in
   the knowledge repo).
5. Android: the cells line IS the registration (HF repo id + `file=` for GGUF
   quant choice). Nothing else to edit. `file=` also accepts a LOCAL PATH for
   side-loaded artifacts (a conversion not published on HF): the driver pushes
   the file directly. The model id in the cell stays the row's identity either
   way.
6. No published `.litertlm` for the model you want (today true for the
   LFM2.5 / MiniCPM class — litert-community has no conversion)? Convert it
   yourself (the litert-samples conversion skills document the recipe), then
   either publish the artifact or side-load it: iOS via the staging step,
   Android via `file=<local path>`. The leaderboard cell stays honestly empty
   until an artifact exists — that emptiness is itself the datum.

## Runbook: add an engine arm

1. Swift adapter (`LLMRuntime` + `RuntimeKind` case) — see
   `.github/ISSUE_TEMPLATE/wire-new-runtime.md` and `ios/BenchmarkApp/README.md`.
2. Pin it: `environment.lock.json` arms entry + vendored acquisition in
   `bootstrap.sh` + `stamp_engine_pins.sh` picks it up for row stamping.
3. Cells + `matrices/README.md` runtime list + `scripts/validate_cells.py`
   RUNTIMES set.
4. External-binary arms (own CLI, own timing): copy the Core AI
   native-benchmark pattern — wrapper script + importer emitting schema v1
   with the comparability caveat in provenance
   (`scripts/coreai_mac_wrapper.sh` / `scripts/import_coreai_llm_benchmark.py`).
   Prefer the in-harness adapter whenever the SDK links into yardstick (the
   Core AI prompt-task rows moved that way on 2026-09-08): same protocol,
   same record, no caveat.
   Worked example of an arm with its own driver on every platform: ONNX Runtime GenAI
   (`docs/ortgenai-arm-v1.md`) — `scripts/ortgenai_mac.py` on the Mac (own venv,
   `ORTGENAI_PYTHON`), `run_cell.py --runtime onnxruntime-genai` on Android with its
   runtime dir pushed per `android/README.md` ("ONNX Runtime GenAI"), the pins in
   `android/engine-pins.json`, and each model folder's recipe label registered in
   `models/ortgenai-recipes.json` (`scripts/ortgenai_recipe.py --register`).
5. Register what the arm loads in `models/artifact-bytes.json`
   (`scripts/artifact_bytes.py --refresh`) so its rows get the `bw util`
   column; a new device needs its ceiling in `devices/memory-bandwidth.json`
   with the citation, or an explicit null.
6. Quality arm: a `--which` case in `scripts/parity_gsm8k.py`.

## Runbook: add a device

- `devices/<name>.md` (soc, RAM, access, power/screen policy).
- iPhone: `BENCH_UDID` env for the runner; the app id needs the
  increased-memory entitlements (multi-GB models do not fit without them).
- Android: adb-authorize; `BENCH_ANDROID_SERIAL` selects among several.
- `DEVICE_DISPLAY` in `scripts/bench_common.py` for rendering.
- Never average across device classes (same-device-class rule); a new device
  is a new row space, and its first sessions establish its own anchors.

## What stays manual, and why

| step | why it cannot be automated |
|---|---|
| energy cells (`manual=1`) | unplug discipline: battery-delta needs the cable out, <=90% charge, Auto-Lock off — physically a human step |
| iOS/Mac builds | Xcode 27 beta is not on hosted runners; owner hardware builds + signs |
| device staging (side-loaded bundles) | artifacts live outside HF; `copy_to` steps per campaign |
| pin bumps | a version bump is a decision, not an event — release-watch tells you, you decide |

## Known limits an operator must not discover the hard way

- **Core AI bundles must live outside iCloud Drive.** `~/Documents` (and
  `~/Desktop`) are iCloud-synced on the bench host; a file iCloud has evicted
  is dataless, and a process that opens it headlessly gets `EDEADLK` (errno 11,
  surfaced by the engine as "malformed metadata.json … couldn't be opened").
  The 2026-09-21 and 09-22 Mac sittings lost all three Core AI cells this way
  after the 2026-09-19 disk cleanup evicted the bundle folders and moved the
  weights to the archive HDD behind symlinks. Since 2026-09-25 the runner's
  default `BENCH_COREAI_MODELS_DIR` is `~/.cache/edge-llm-bench/CoreAIModels`
  (a full local copy, no symlinks); a disk cleanup must leave that folder
  alone — the weekly job reads it.
- **A phone is shared with other lanes.** Before any Android capture, check
  the campaign flock, the conversion lane's hold file
  (`~/code/litertlm-convert/community_accel_work/s2_npu_sweep/.device_hold.<device>`),
  and the phone's own process list for a foreign `litert_lm*`/`llama*`; a
  concurrent benchmark reads as a collapsed anchor (0.4-2.7 tok/s for 31,
  2026-09-05) and contaminates the other lane too. Take the hold file for
  the campaign and release it after.
- **adb can lose a phone that re-enumerated on USB.** After a power or hub
  blip the phone is back in `ioreg -p IOUSB` but not in `adb devices`, and
  the adb server does not recover on its own (Pixel 8a, 2026-09-08 anchor
  probe: invisible for over two minutes). `adb kill-server && adb start-server`
  brings it back at once, but the restart refuses connections for about a
  second ("cannot connect to daemon"): a `run_cell.py` probing adb at that
  instant dies with a traceback and that cell is lost (the probe's LiteRT
  anchor lost its third run this way; the campaign moved on and the gate
  and admission judged the real records). Restart only between cells or
  after the current cell has already failed — a cooldown is a safe moment.
  Absent from `ioreg` too = physically disconnected; a human plugs it in. The Galaxy S26 left
  the adb bus the same way at the end of the 2026-09-14 02:00 dashboard
  sitting (between 04:45 and 04:53, 2 h 45 min in): the runner's thermal wait
  raised `device not found`, `bench matrix` exited 1, the 15 cells already had
  records and the job still closed COMPLETED / admitted — read the job log's
  tail, not only the ledger, before calling a sitting clean.
- **A launch that loses the phone is a failed launch (since 2026-10-07).** `device_probe.adb` still re-runs probes, pushes and pulls after `adb wait-for-device`, with one line in the campaign log (`adb retry after device loss: <command>`), but never the engine shell (`run_cell.run_once`, retries=1): that launch ends with a traceback and no record, the campaign lists it in `FAILURES.txt`, and the cell is a run short (the gate's SHORT, never re-run). Before, a phone that rebooted under a running engine had the shell replayed on the rebooted phone, and the replay's record read as one run (Pixel 8a, 2026-10-07 15:58).
- **A run under a CPU frequency cap deeper than 15 % is not a measurement (since 2026-10-07, the line since 2026-10-08, cpu-cap-rule).** Before each launch `run_cell.py` waits up to `CPUCAP_WAIT` s (default 300) for every cpufreq policy's `scaling_max_freq` to be back at `cpuinfo_max_freq`, then runs anyway (`cpu-capped-at-start`); a run during which a policy of the engine's CPUs sat below its hardware maximum carries `cpu-capped` (`conditions.cpuMaxFreqMHz`, one line in `THERMAL_GATE.txt`) and the record stays. The summary's `cpu_cap_drop_pct` says how far the engine CPUs' ceiling fell: above `render_leaderboard.CPU_CAP_MAX_DROP_PCT` (15) no number pools the run, and a cell left with none reads "no valid run (cpu-capped >15 % …)"; at or below it the run pools and the number carries "◇ cpu-capped ≤15 % (k of N runs)". A charging Pixel 8a capped cpu4-7 at 1418-2130 MHz mid-run with the thermal status at 0 (2026-10-07); the Galaxy S26 (not charging) capped every CPU launch of its 2026-10-08 ONNX Runtime GenAI sitting whose load lasted beyond about 3 s, and that day's capped runs fell 3-19 % on short-chat and 19-58 % on the 1K task (`methodology/fairness-rules.md` §13).
- **Phone storage, not memory, bounds the dashboard set.** The full 15-cell
  Android set needs about 28 GB on the device (pushed models plus LiteRT's
  XNNPACK caches at 0.6-0.8x the model size); `matrices/dashboard-text-v1-android-{a,b,b1,b2}.cells`
  split it for a phone with less free space. The iPhone needs about 35 GB
  of app storage for the same set (staged files plus in-app MLX downloads);
  a full disk fails a cell with "No space left on device" and can kill the
  app during a load that would otherwise fit. Deleting pushed bundles to make
  room leaves their `markers/*.cachebuilt` files behind: since 2026-09-07 the
  driver drops an artifact's markers whenever it actually (re)pushes it, so
  the rebuilt cache's run 1 is labelled `firstEver` again instead of pooling
  as speed (`android/bench/run_cell.py`, selftest campaign B2).
- **Headless iPhone cells need the phone unlocked for every launch**
  (Auto-Lock Never): a locked phone refuses `devicectl process launch`
  ("device was not, or could not be, unlocked"), and a phone that goes
  offline mid-cell leaves a record with an impossible decode figure — check
  `device-jsonl` against the console before trusting a lone record. Stage
  large artifacts headlessly with
  `xcrun devicectl device copy to --domain-type appDataContainer --domain-identifier <app> --source <file> --destination Documents/models/<runtime>/<org__repo>/<primaryFile>`
  (HFDownloader short-circuits on a non-empty model directory; about 22 MB/s).
- **`mlx-community/gemma-4-e4b-it-qat-OptiQ-4bit` does not load on the iPhone 17 Pro**: the
  7.5 GB repo downloads, then the app is SIGKILLed while loading its 6.5 GB of
  text weights (2026-09-06). The iOS row carries `exclude=app-killed-at-model-load-sigkill`.
- **Mac llama.cpp cells abort at exit, after their runs.** Every llama.cpp
  cell on the Mac completes and records its runs, then yardstick aborts in
  llama.cpp's Metal teardown (`ggml_metal_rsets_free` -> `ggml_abort`, from
  `ggml_metal_device_free` in a static destructor during `exit`): b8999, and
  b11721 the same (2026-10-19 smoke, crash reports
  `yardstick-2026-10-19-060022.ips` / `-060518.ips`); the runner writes `FAIL`
  to FAILURES.txt by exit code. The rows stand.
- **Short-chat prefill is not comparable across arms.** On a ~20-token prompt
  the prefill figure is dominated by fixed per-call overhead and ranks the
  arms differently from decode; the 1024-token task is the prefill
  instrument (methodology/agreed-protocol-gemma4.md).

- **Core AI arm**: PLE models (Gemma-4 E2B/E4B) need the unpublished
  `COREAI_STATIC_INPUTS` engine patch; a clean clone reports `unsupported`
  and the dashboard rows are `exclude=`. Qwen3 rows run through yardstick's
  `CoreAIRuntime` on the Mac (since 2026-09-08) and the app on the phone —
  bundles are side-loaded (`BENCH_COREAI_MODELS_DIR`, default
  `~/.cache/edge-llm-bench/CoreAIModels/<folder>/`; staging recipe in
  `docs/dashboard-cells-v1.md`), and the Mac runner logs a not-staged bundle
  as `SKIPPED … coreai-bundle-not-staged`. The external `llm-benchmark`
  wrapper serves only `native-benchmark-*` cells; those rows are not
  protocol-identical (own timing, no context budget) and say so in provenance.
  Building the Mac yardstick with `CoreAILM` needs the Xcode 27 beta as the
  selected developer dir (stable Xcode has no CoreAI framework in its SDK).
- **GSM8K beyond the LiteRT arm still shells to external checkouts**
  (`environment.lock.json` → `external_instruments_not_yet_in_repo`).
- **Cross-session device drift is 16-25%** (iphone-session-variance): never
  compare absolute numbers across sittings without anchors; the differ
  enforces this (INFO-ONLY / anchor-normalized).
- **HOT and wide-spread captures auto-retry once** (`scripts/cell_gate.py`,
  wired into the mac and iPhone runners): the flagged capture is quarantined
  in raw (mac: `<cell>.jsonl.attempt1`; iPhone: `device-jsonl-flagged/` —
  kept for audit, outside build_summary's globs, never pooled into the
  session median) and the cell re-runs after a real cooldown. A flagged
  retry stands, with a `FLAGGED.txt` note; SHORT (crash/timeout) never
  retries — failed-runs-stay owns that path. The Android runner is wired
  too (quarantine: `*.json.attempt1` beside the record): its cold-only
  regime can never trip the 5% warm-spread bar, so the gate's COLLAPSE
  verdict fires instead — slowest cold decode under half the cold median,
  the contended-device signature (cold trials legitimately spread 15-30%).
  The differ still marks wide cells UNRELIABLE at scoring time.
- **litert cells can stall ~10 min at teardown** — the iPhone runner's
  gtimeout is load-bearing; keep `CELL_TIMEOUT=3600` for litert cells.
- **The SPM-built Mac yardstick silently lacks four runtimes** — matrix
  runners refuse the `spm-lite` flavor; always build via
  `scripts/build_yardstick_mac.sh`.
- **Android has no warm regime in v1** and no TTFT on llama-cli; every
  deviation is listed in `methodology/android.md`.
- **Android `conditions.screen` is a reading only since 2026-09-26**: the runners read `mWakefulness` before every launch (`on-usb` / `off-usb (mWakefulness=…)`, `conditions.screenSource`); an older row without `screenSource` that says `on-usb` carries a fixed string.
