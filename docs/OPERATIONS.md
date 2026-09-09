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
   - Android: `LITERTLM_TAG=v0.16.0 android/scripts/build_litert_lm_main.sh`,
     push per `android/README.md`. Then attach `android/bin/<tag>/` (+ a full
     SHA256SUMS) to a GitHub release `android-litert-lm-<tag>` — upstream
     ships no Android binary, so the release asset is what lets anyone else
     skip the bazel+NDK build.
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
session's anchor → the dashboard cells (or the storage halves, rotating
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
a sitting — Mac under `~/Documents/CoreAIModels/<folder>/`, phone under the
app's `Documents/CoreAIModels/<folder>/` (recipe: `docs/dashboard-cells-v1.md`,
"Core AI arm (v2)"). The job does not stage: a missing folder is a `SKIPPED`
line on the Mac and a failed cell on the phone, never a refused sitting.

The job never commits or pushes: review the new campaign dir(s) and the
regenerated `results/summary/` the next morning and commit them with a
message that states what ran and what reproduced (public text carries no
cross-runtime ordering). Read `FLAGGED.txt` for `DEGENERATE` before trusting
a new arm's rate: the cell gate flags a capture whose output is a repetition
loop (an engine can report a fast rate while generating garbage — seen on
2026-09-08), and such a cell is never retried, only marked. The launchd template that fires `auto` is
`ops/dashboard-v1/com.edge-llm-bench.dashboard-v1.plist.template`; enabling
it is an owner step, documented in the template header. To change the firing
times, edit `schedule.json` `slots` and the template together, re-render the
plist and `launchctl bootout` + `bootstrap` it (the running agent keeps the
old times until then).

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
  Absent from `ioreg` too = physically disconnected; a human plugs it in.
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
  llama b8999's Metal teardown (`ggml_metal_rsets_free` -> `ggml_abort`);
  the runner writes `FAIL` to FAILURES.txt by exit code. The rows stand.
- **Short-chat prefill is not comparable across arms.** On a ~20-token prompt
  the prefill figure is dominated by fixed per-call overhead and ranks the
  arms differently from decode; the 1024-token task is the prefill
  instrument (methodology/agreed-protocol-gemma4.md).

- **Core AI arm**: PLE models (Gemma-4 E2B/E4B) need the unpublished
  `COREAI_STATIC_INPUTS` engine patch; a clean clone reports `unsupported`
  and the dashboard rows are `exclude=`. Qwen3 rows run through yardstick's
  `CoreAIRuntime` on the Mac (since 2026-09-08) and the app on the phone —
  bundles are side-loaded (`BENCH_COREAI_MODELS_DIR`, default
  `~/Documents/CoreAIModels/<folder>/`; staging recipe in
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
