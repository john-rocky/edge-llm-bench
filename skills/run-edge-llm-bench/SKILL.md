---
name: run-edge-llm-bench
description: Measure a LiteRT-LM bundle's prefill and decode speed, resident memory and thermal state on a connected Android phone or a Mac with edge-llm-bench, ad hoc - write the cells, run them, read the stored record. Use when asked to measure a .litertlm bundle on a real device now, to measure a bundle that is not published yet (side-loaded file), to repeat a measurement at a newer LiteRT-LM build, or to trace a quoted number back to its raw record. iPhone cells use the same file once the app is installed (a GUI signing step).
---

# Run edge-llm-bench ad hoc

An ad-hoc measurement is done when three things hold, in this order:

1. every run has a **stored record** - a JSON record plus its raw console log
   under `results/raw/<campaign>/` (a number without a stored report is not a
   measurement),
2. the runs **agree**: thermal state nominal at start, trial spread within a
   few percent, no gate flag on the capture,
3. the record **names** the device, the engine version it observed, the
   quantization label and the token budget - a rate without those compares
   to nothing.

Vocabulary: a **cell** is one platform x runtime x model x task plus options
such as the backend; a **campaign** is one invocation's record directory; numbers
compare only inside one sitting, or across sittings through a repeated control
cell (the **anchor**).

## Loop

**0. Preflight.** From the repo root:

```bash
./bench doctor
```

Every FAIL prints the command that fixes it. First-time setup: ~15 min for the
Android lane (prebuilt engine binaries on the releases page, an adb-authorized
phone), ~45 min for the Mac lane (`ios/BenchmarkApp/scripts/bootstrap.sh`, then
`scripts/build_yardstick_mac.sh`), half a day for the iPhone (Xcode signing, two
increased-memory entitlements, GUI only). Plugging devices, signing, the room's
thermal environment and moving an engine pin stay human steps.

**1. Write the cells.** One line per cell, grammar in `matrices/README.md`:

```
<platform> <runtime> <model-id> <task> [key=value ...]
```

`platform` is `android` | `mac` | `ios`; `runtime` here is `litert-lm`;
`model-id` is the Hugging Face repo; `task` is `short-chat` (~20-token prompt;
the Mac and iPhone runners cap generation at 128 tokens, while the Android
CLI at v0.16.0 ignores the cap and runs to the model's own stop, so read
`metrics.generatedTokenCount` - disclosed in `methodology/android.md`),
`long-context-1024-gen256`, or
`native-benchmark-<P>x<D>` (the engine's own synthetic benchmark). Android
LiteRT-LM cells need `backend=cpu|gpu` and, when the repo holds several
bundles, `file=<name>`. The committed example, one cell per platform:

```
mac litert-lm litert-community/Qwen3-0.6B short-chat runs=3
android litert-lm litert-community/Qwen3-0.6B short-chat runs=3 backend=gpu file=qwen3_0_6b_mixed_int4.litertlm
```

Validate before running - CI does the same for every file under `matrices/`:

```bash
python3 scripts/validate_cells.py matrices/ad-hoc-example.cells
```

**2. Make sure the device is yours.** One driver per device: the Android
runner takes a per-device lock, but a foreign engine process on the phone
(`adb shell ps -A | grep litert_lm`) or another host's driver still corrupts
both captures; a Mac under a heavy export pipeline refuses to start.

**3. Run.** `--platform` filters the file to one runner; `--campaign` names the
record directory (`<campaign>-<platform>` under `results/raw/`):

```bash
./bench matrix matrices/ad-hoc-example.cells --platform android --campaign 2026-09-12-skill-smoke
./bench matrix matrices/ad-hoc-example.cells --platform mac --campaign 2026-09-12-skill-smoke
```

Anchor cells run first; on Android the payload cells interleave per round and
the thermal gate waits for a nominal phone before every run; every runner
cools down between cells (Android also between runs) and quarantines a capture
that starts hot, spreads wide or collapses, then re-runs it once. Exit 2 = the
file failed validation or matched no cells for that platform (`error: no cells
for platform(s) [...] — nothing was measured`). A failed cell keeps exit 0: it
is listed in `FAILURES.txt` beside the records, which stand - read that first.

**4. Read the record, not the console.** Android records are one JSON per run
beside its log; Mac records are one `.jsonl` per cell with one line per run:

```bash
grep -h -o '"decodeTokensPerSecond": *[0-9.]*' results/raw/2026-09-12-skill-smoke-android/app-path-android/*.json
grep -h -o '"decodeTokensPerSecond":[0-9.]*' results/raw/2026-09-12-skill-smoke-mac/*.jsonl
```

Fields that matter: `metrics.decodeTokensPerSecond`, `promptTokensPerSecond`,
`memoryMedianResidentMB`, `initialThermalState`, `coldRun` / `firstEver` (a
cache-building run is labelled, never pooled as speed); `engineVersion` +
`engineArtifact` (on Android the binary found on the device, by sha256);
`model.quantization` (Android adds `model.sha256`); the context budget in
`conditions.contextTokens` (Android) or `metrics.contextTokensConfigured` (Mac).
Every run is also a row in `results/summary/device-runs.csv` (regenerated - never edit):

```bash
python3 -c "import csv; [print(r['device'], r['runtime'], r['model_id'], r['task'], r['decode_tps'], r['thermal_initial']) for r in csv.DictReader(open('results/summary/device-runs.csv')) if '2026-09-12-skill-smoke' in r['campaign']]"
```

Read `FLAGGED.txt`, `FAILURES.txt` and `SKIPPED.txt` beside the records first.

**5. Compare only through a control.** A device drifts 16-25% between
sittings, so today's number and last week's are not a delta. To compare with
an earlier campaign, add that platform's `anchor=1` line from
`matrices/anchors.cells` and run
`./bench regress <cells> --engine litert-lm --version <label> --baseline campaign:<earlier>`.
Verdicts land in `results/regression-reports/<date>-litert-lm-<label>/verdicts.json`:
`OK`, `IMPROVED`, `REGRESSION`, `UNRELIABLE` (spread too wide - re-run, never
average) or `INFO-ONLY` (no anchor, or too few runs); a different budget is a
different task and never joins. An anchor measured by the engine under test
is excluded, so the anchor's runtime differs from LiteRT-LM by design and its
binary must be on the device too (`android/README.md`). Exit 1 = REGRESSION.

**6. Profile the decode step (Android).** Per LiteRT-LM `native-benchmark-<P>x<D>`
cell: a control capture, the same command with `--enable_profiling`, one table:

```bash
./bench profile matrices/profile-example-android.cells --campaign 2026-09-12-profile-smoke
```

Read `results/raw/<campaign>-android/profiles/PROFILE.md`: wall ms per decode
step from the control, profiled op time as weight GEMV / attention+KV / transfer
/ other, launches per step. A profiled rate is never a speed row (`docs/profiling-subcommand-design.md`).

## The two ad-hoc cases

- **A bundle that is not published.** Give it its own id under `litert-local/`
  and point `file=` at the local path; the driver pushes the file, and the id
  is the row's identity (a second file under a published id would pool with it):
  `android litert-lm litert-local/<name> short-chat backend=gpu local=1 file=/abs/path/<bundle>.litertlm`
- **A build newer than the pin.** Build at the tag (`android/README.md`,
  "Per-release source build"), push it, run as usual. The record stamps the
  sha256 found on the device; an unregistered binary reads
  `unknown (on-device litert_lm_main sha unmatched in android/engine-pins.json)`
  - register it in `android/engine-pins.json` so the row names its tag. The
  pin in `environment.lock.json` stays; moving it is a decision.

## Symptoms

| What you see | What it is, what to do |
|---|---|
| exit 2, `nothing was measured` | `--platform` does not match the file's platform tokens, or validation failed; nothing ran |
| `gate: COLLAPSE` then a re-run | a contended device (another process on it). The first capture is kept as `*.json.attempt1` / `*.jsonl.attempt1` and noted in `session_provenance.txt` - audit trail, never pooled; `FLAGGED.txt` appears when the retry is flagged too |
| `DEGENERATE` in `FLAGGED.txt` (Mac and iPhone runners; Android CLI records carry no `outputSample`, so the gate cannot judge them) | the output is a repetition loop; the engine reported a rate while generating garbage - never read it as a speed, never retry |
| a LiteRT-LM cell finished its runs but the process lingers ~10 min | a teardown stall in the engine; the records are already on disk (the iPhone runner wraps cells in `gtimeout`, `CELL_TIMEOUT=3600`) |

## Watch for

- **Never pool numbers across sessions** (deltas count only through the
  anchor) and **never mix budgets or modes across arms** (token cap, context
  size and thinking mode are part of the task id; a mismatch never joins).
- **The quantization label travels with the row** ("int4" is not a spec; the
  record carries the exact label) and **failed runs stay** with their reason.
- **Generated files are generated.** `results/summary/*` is rebuilt from raw
  by every run; commit raw records and the regenerated summary together.
- **Other engines the harness runs are outside this skill**, except as the anchor.

## Output layout

```
results/raw/<campaign>-android/app-path-android/<arm>_<model>_<task>_<timestamp>_run<N>.json  (+ .log)
results/raw/<campaign>-mac/<runtime>_<model>_<task>.jsonl   FAILURES.txt  SKIPPED.txt  session_provenance.txt
results/raw/<campaign>-android/profiles/                     <tag>_<backend>_{prof,ctrl}.log  .prof.json  PROFILE.md  profile-table.csv  SKIPPED.txt  FAILURES.txt
results/summary/device-runs.csv                              one row per run, regenerated
results/regression-reports/<date>-<engine>-<version>/        report.md  verdicts.json  invocation.txt
```

Tested on: Pixel 8a (Android 16, LiteRT-LM v0.16.0 pinned binary, cpu and gpu) and a
Mac Studio M4 Max (macOS 27, v0.16.0 vendored), 2026-09-12. [LiteRT-LM](https://github.com/google-ai-edge/LiteRT-LM) on [LiteRT](https://github.com/google-ai-edge/litert).
