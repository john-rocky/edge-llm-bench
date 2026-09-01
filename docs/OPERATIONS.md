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

- Thinking-template bundles whose assistant-history re-render is not a
  byte-prefix extension of the live render (litert-community Qwen3-0.6B
  int4: an empty `<think></think>` pair only in the live render) cannot
  hold a multi-turn conversation at all — turn 2 dies with `INTERNAL: The
  new rendered template string does not start with the previous...`. The
  endurance row records it as `status=crash`; that row is the datum, not a
  capture bug. → LiteRT-LM #3443.
- A bundle's real context ceiling can sit below the accepted
  `maxNumTokens` (gemma-4-E2B: 2048 under a 4096 request) and there is no
  API to query it; the harness's kv-wall rollover absorbs the resulting
  mid-conversation `FAILED_PRECONDITION`. → #3444.
- Structured think-prefix bundles (granite-4.2-3b): history re-render keeps
  the pre-opened `<think>` unclosed and drops the thought, so coherence
  collapses silently at ANY turn cap — verified with the cap-1024 probe and
  `yardstick debug-render`. → #3445.
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
4. External-binary arms (own CLI, own timing): copy the Core AI pattern —
   wrapper script + importer emitting schema v1 with the comparability caveat
   in provenance (`scripts/coreai_mac_wrapper.sh` /
   `scripts/import_coreai_llm_benchmark.py`).
5. Quality arm: a `--which` case in `scripts/parity_gsm8k.py`.

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

- **Core AI arm is best-effort**: PLE models (Gemma-4 E2B/E4B) need the
  unpublished `COREAI_STATIC_INPUTS` engine patch; a clean clone reports
  `unsupported`. The Mac external `llm-benchmark` rows are not
  protocol-identical (own timing, no context budget) and say so in provenance.
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
