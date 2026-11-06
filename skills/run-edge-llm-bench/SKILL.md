---
name: run-edge-llm-bench
description: Measure a LiteRT-LM bundle's prefill and decode speed, resident memory and thermal state on a connected Android phone or a Mac, on a Developer Device Platform lab phone with no adb, or on a Windows PC over SSH, with edge-llm-bench, ad hoc - write the cells, run them, read the stored record. Use when asked to measure a .litertlm bundle on a real device now, to measure a bundle that is not published yet (side-loaded file), to repeat a measurement at a newer LiteRT-LM build, or to trace a quoted number back to its raw record. iPhone cells use the same file once the app is installed (a GUI signing step).
---

# Run edge-llm-bench ad hoc

An ad-hoc measurement is done when three things hold, in this order:

1. every run has a **stored record** - a JSON record plus its raw console log
   under `results/raw/<campaign>/` (a number without a stored report is not a
   measurement),
2. the runs **agree**: thermal state nominal at start (on Windows: `quietGate`
   `quiet`), decode trial spread within a few percent ((max - min) / median of one
   regime's runs; the harness's checks flag past 5 %), no gate flag on the capture,
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

Every FAIL prints the command that fixes it; with two phones attached it says
`2 devices — set BENCH_ANDROID_SERIAL`, and the runner reads that variable.
First-time setup: ~15 min for the Android lane (prebuilt engine binaries on the
releases page, an adb-authorized phone), ~45 min for the Mac lane (`ios/BenchmarkApp/scripts/bootstrap.sh`,
then `scripts/build_yardstick_mac.sh`), half a day for the iPhone (Xcode signing,
two increased-memory entitlements, GUI only); on a Windows PC the engine build alone takes 14 to 49 min, and
doctor has no Windows lane (its section below). Plugging, signing, thermal environment and pin moves stay human.

**1. Write the cells.** One line per cell, grammar in `matrices/README.md`:

```
<platform> <runtime> <model-id> <task> [key=value ...]
```

`platform` is `android` | `mac` | `ios` | `windows`; `runtime` here is `litert-lm`;
`model-id` is the Hugging Face repo; `task` is `short-chat` (~20-token prompt;
the Mac and iPhone runners cap generation at 128 tokens, while the Android
CLI at v0.16.0 ignores the cap and runs to the model's own stop, so read
`metrics.generatedTokenCount` - disclosed in `methodology/android.md`),
`long-context-1024-gen256`, or `native-benchmark-<P>x<D>` (the engine's own synthetic benchmark). Android
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
grep -h -o '"decodeTokensPerSecond": *[0-9.]*' results/raw/2026-09-12-skill-smoke-mac/*.jsonl
```

(A Mac native-benchmark cell writes one `YARDSTICK_NATIVE_OK ...` text line
instead.) Fields that matter: `metrics.decodeTokensPerSecond`, `promptTokensPerSecond`,
`memoryMedianResidentMB`, `initialThermalState`, `firstEver` (a cache-building
run is labelled, never pooled as speed; Android `coldRun` is always `true`); `engineVersion` +
`engineArtifact` (on Android the binary found on the device, by sha256);
`model.quantization` (Android adds `model.sha256`); the context budget in
`conditions.contextTokens` (Android) or `metrics.contextTokensConfigured` (Mac).
Every run is also a row in `results/summary/device-runs.csv` (regenerated - never edit):

```bash
python3 -c "import csv; [print(r['device'], r['runtime'], r['model_id'], r['task'], r['decode_tps'], r['thermal_initial']) for r in csv.DictReader(open('results/summary/device-runs.csv')) if '2026-09-12-skill-smoke' in r['campaign']]"
```

Read `FLAGGED.txt`, `FAILURES.txt` and `SKIPPED.txt` beside the records first (the Windows lane writes none: see its
section).

**5. Compare only through a control.** A device drifts 16-25% between
sittings, so today's number and last week's are not a delta. To compare with
an earlier campaign, add that platform's `anchor=1` line from `matrices/anchors.cells` and run
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
/ other, launches per step. A profiled rate is never a speed row. `./bench profile`
drives Android; the Mac pair, run directly from the CLI built at the tag, is in
`docs/profiling-subcommand-design.md` (Coverage: which Mac GPU accelerator profiles).

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

## Lab phones without adb (Developer Device Platform)

The Android LiteRT-LM cells also run on a DDP lab phone, billed to your Cloud
project, with no phone attached. Read the dry run (one job per cell, at most 8
per session, the pushes, an estimate) before the billed run:

```bash
./bench matrix matrices/ddp-first-run.cells --ddp akita-35 --dry-run --project <your project> --bucket gs://<your bucket>
./bench matrix matrices/ddp-first-run.cells --ddp akita-35 --campaign <name> --project <your project> --bucket gs://<your bucket>
```

The host needs gcloud signed in, a project with the Device Run API enabled and
a bucket you can write, python3 >= 3.10 with `huggingface_hub`, and the pinned
engine files (README DDP section, step 2). `./bench doctor --platform ddp`
checks gcloud, its sign-in, `huggingface_hub` and the 9 engine files; the README
"Quickstart: the Android cells on a DDP lab phone" lists the whole route.

One command does the run and what follows it: `./bench autopilot --ddp <id> --project <p> --bucket gs://<b>`
(`--dry-run` first: no network) runs the nightly job's lab-unit sitting, checks it, commits it locally when
every rule passes (`REVIEW.md` otherwise; `--no-commit` stops at the check), renders `DASHBOARD.md`, prints
the red points and pending requests, and ends on one screen of next steps (`docs/dashboard-autopilot-v1.md` §10).

- **One job is one lab unit and a sitting of its own.** A session's jobs start
  together on different units (`conditions.ddp.serial`); DDP has no anchor, and
  the summary names the device `<model> (DDP <id>)`, so these rows never pool
  with an attached phone's.
- **Read the cap marks.** `conditions.protocolFlags` carries `cpu-capped` (an
  engine CPU's ceiling sat below its hardware maximum) and `cpu-capped-at-start`;
  the summary's `cpu_cap_drop_pct` is the fall. A CPU-arm run past 15 % pools
  into no number (cpu-cap-rule); a GPU-arm run pools with its mark. The wait
  before each run is per id: `cpucapWaitSeconds` in `android/ddp/devices.json`.
- **Fields only a DDP record carries:** `device.ddp` and `conditions.ddp`
  (session, job and execution ids, build fingerprint, serial),
  `conditions.engineCache` (what the engine caches did in that run; a later run
  can rebuild one, which `firstEver` does not show), `provenance.ddpSessionDir`.
- **Pulled logcats carry the lab network's identifiers.** The driver replaces
  them at pull time (originals in the campaign's gitignored `ddp-raw/`); leave
  the execution-level `logcat.txt` out of the commit. Runbook:
  `docs/OPERATIONS.md`, "Runbook: run cells on DDP (a lab phone, no adb)".
- **The dashboard job has a weekly DDP slot.** `ops/dashboard-v1/schedule.json`
  device `s26-ddp` runs the weekly set's LiteRT-LM rows on `m1q-36` after the
  night's attached sitting, at most once in 6 days, with no person in the loop
  (`python3 scripts/dashboard_job.py s26-ddp --dry-run` prints the plan;
  `docs/dashboard-autopilot-v1.md` §9).
- **The switch.** `ops/autopilot/switch.json` `ddp_weekly` turns that slot on and
  `ddp_max_sessions` caps one sitting's sessions; set `ddp_weekly` false when you
  run the weekly DDP set on your side, so the two do not both bill it.

## A Windows PC over SSH

`windows/README.md` is the setup. The PC needs an OpenSSH server with PowerShell as its shell and a key login from the
Mac, the DirectX shader compiler from the PyPI wheel, the engine built on the PC under a label of its own
(`windows/build_litert_lm.ps1`, 14 to 49 min; LiteRT-LM has no Windows release asset) and the model files in one dir,
checked against the Hub. `./bench doctor` has no Windows lane; the build script checks for MSVC, Git Bash, Python 3.13,
a JDK and Bazelisk first (not Git LFS, LongPathsEnabled or the symlink right its header also lists; the README's Setup
has the lines that read them). Windows cells do not go through `./bench matrix`:

```bash
cat > /tmp/one-windows.cells <<'EOF'
windows litert-lm litert-community/gemma-4-E2B-it-litert-lm short-chat backend=gpu file=gemma-4-E2B-it.litertlm context-tokens=2048 runs=3
EOF
python3 scripts/validate_cells.py /tmp/one-windows.cells
BENCH_WINDOWS_SSH_HOST=<host> BENCH_WINDOWS_ROOT='<root>' BENCH_WINDOWS_MODEL_DIR='<models>' \
BENCH_WINDOWS_DEVICE_MODEL='<model> (<CPU> / <GPU>)' BENCH_EXTRA_PINS=pins-v0.19.0-<yours>.json \
python3 scripts/windows_ssh_executor.py /tmp/one-windows.cells \
    --campaign <date>-windows-<what> --litert-label v0.19.0-<yours> \
    --model-file litert-lm:litert-community/gemma-4-E2B-it-litert-lm=gemma-4-E2B-it.litertlm:2588147712
python3 scripts/build_summary.py
python3 -c "import glob, json; [print(c['regime'], m.get('firstEver', False), m.get('decodeTokensPerSecond'), m.get('promptTokensPerSecond'), c.get('hostBefore', {}).get('quietGate'), c['protocolFlags']) for f in sorted(glob.glob('results/raw/<date>-windows-<what>/*.jsonl')) for r in map(json.loads, open(f)) for m, c in [(r['metrics'], r['conditions'])]]"
python3 -c "import glob, json, statistics; [print(f.split('/')[-1], g, d, 'spread %.2f %%' % ((max(d) - min(d)) / statistics.median(d) * 100)) for f in sorted(glob.glob('results/raw/<date>-windows-<what>/*.jsonl')) for g in ('cold', 'warm', 'cold-process') for d in [[r['metrics']['decodeTokensPerSecond'] for r in map(json.loads, open(f)) if r['conditions']['regime'] == g and not r['metrics'].get('firstEver') and r['metrics'].get('decodeTokensPerSecond')]] if d]"
```

`<host>` (default `winpc`), `<root>`, `<models>`, the label and its `pins.json` are the ones the README's setup made;
`<what>` is a word of yours. `BENCH_WINDOWS_DEVICE_MODEL` becomes the summary's `device` as written: build it by the
README's rule (Run) from the host's own names, which come from
`ssh <host> '(Get-CimInstance Win32_ComputerSystem).Model; (Get-CimInstance Win32_Processor).Name; (Get-CimInstance Win32_VideoController).Name'`.
While the job runs, the executor prints the host's log as `host: ...` lines. On 2026-11-06 the three runs took 2 min
on the host, after a wait of at most 30 min for a quiet one (total CPU under 25 %, NVIDIA memory in use under 800 MiB).

Exit 0 means every run is clean (`== 3/3 runs clean`); it does not look at the spread, which only the block's last
line prints. Exit 1 means a run is not - its record carries the reason in
`conditions.protocolFlags`, `conditions.exitCode` and `conditions.textCheck` - or the job failed on the host
(`== job: FAILED <why>`, also in `host-logs/<invocation>/job.log`; a model file missing from `<models>` stops it before
its first run), or the executor refused before the job (`error: ...` on stderr, no record). Exit 2 means nothing ran:
the arguments or the plan failed (a usage line or `ERROR: ...` on stderr), or that invocation's records are written
already. The Windows lane writes no `FLAGGED.txt`, `FAILURES.txt` or `SKIPPED.txt`, and the executor does not rebuild
`results/summary/`; the `build_summary.py` line does. The last two lines print each record's regime, `firstEver`,
decode and prefill rates (tok/s), `quietGate` and flags, then, per regime, the decode rates of every record but run
1's cold one (the cache build), with their spread. The second line does not drop a flagged run's records: on exit 1,
read the flags in the first line before the spread.

- **The label names the build.** `--litert-label v0.19.0` names the one build `windows/engine-pins.json` lists. Another
  build, even of the same commit, has come out with a sha256 of its own (four full builds of `83ce6067f` on one PC,
  2026-11-05 to 11-06, four sha256s): pass its own label and point `BENCH_EXTRA_PINS` at the `pins.json` the build
  script wrote beside the tool. Before the
  job is staged, the executor stops with `error: ...` and exit 1 when the label is in neither registry or the files in
  `<root>\engines\litert` are not that label's build.
- **`backend=` picks the arm, and `file=` has to fit it.** `cpu` and `gpu` take `gemma-4-E2B-it.litertlm`, `npu` takes
  the bundle of the PC's SoC and no `context-tokens=`. The GPU row checks that the log's `Selected adapter:` line names
  NVIDIA; a run on any other adapter carries `backend-not-registered`.
- **Each LiteRT-LM run is a cold and a warm record.** One process holds two conversations (`metrics.coldRun`). A new
  invocation (the executor started without `BENCH_WINDOWS_INVOCATION`) removes the engine's caches, so `firstEver`
  marks run 1's cold record, the cache build, and `runs=3` leaves two cold records and three warm ones to read. Read the
  two regimes apart. Decode agrees within a few percent; the GPU row's 20-token cold prefill does not (15.6 to 21.0
  tok/s in the admitted cold records of 2026-11-05), and on the GPU a fresh process's first prefill is far slower than
  its second.
- **A wide decode spread is a sitting to throw out.** A regime's spread is (max - min) / median of its decode rates
  over the records that count (run 1's cold record, the cache build, does not). The bar is 5 %: the page marks a row past
  `SPREAD_FLAG` (`scripts/render_leaderboard.py`), and `scripts/cell_gate.py`, the gate other lanes run after a
  capture, holds their warm decode to it (the Windows lane runs none). A regime past it does not agree (`spread-rule`,
  the table at the top of `methodology/fairness-rules.md`): do not quote it. The page's Windows rows read the cold
  median, so a cold spread past 5 % means running the cell again under a new `--campaign` (the same name with `-r2`,
  then `-r3`). The same `--campaign` appends the new records to the old `.jsonl`, and the two sittings do not pool.
  Rename the thrown-out sitting's `.jsonl` to `.jsonl.attempt1`: the summary reads `*.jsonl` only, and the repo keeps
  such a file as the audit trail.
- **A Windows record has no thermal state.** The start condition is each run's `conditions.hostBefore.quietGate`:
  `quiet`, or `timeout` when the run started on a host that never went quiet. `hostBefore` carries the CPU, the top
  processes and the GPU before the run, `hostAfter` the CPU and the top processes after it; the GPU after and during
  the run is in the host log, `host-logs/<invocation>/r<NN>_run<N>.json` (`gpuAfter`, and `gpuSamples` every 5 s of a
  GPU run, none for a run of about 5 s).

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
  by every `./bench matrix` run, and on Windows by `scripts/build_summary.py`;
  commit raw records and the regenerated summary together.
- **Other engines the harness runs are outside this skill**, except as the anchor.

## Output layout

```
results/raw/<campaign>-android/app-path-android/<arm>_<model>_<task>_<timestamp>_run<N>.json  (+ .log)
results/raw/<campaign>-mac/<runtime>_<model>_<task>.jsonl   FAILURES.txt  SKIPPED.txt  session_provenance.txt
results/raw/<campaign>/<arm>_<model>_<task>.jsonl            host-logs/<invocation>/  decoded/   (Windows)
results/raw/<campaign>-android/profiles/                     <tag>_<backend>_{prof,ctrl}.log  .prof.json  PROFILE.md  profile-table.csv  SKIPPED.txt  FAILURES.txt
results/summary/device-runs.csv                              one row per run, regenerated
results/regression-reports/<date>-<engine>-<version>/        report.md  verdicts.json  invocation.txt
```

Tested on: Pixel 8a (Android 16, LiteRT-LM v0.16.0 pinned binary, cpu and gpu) and a
Mac Studio M4 Max (macOS 27, v0.16.0 vendored), 2026-09-12. DDP lab phones, v0.18.0
pinned binary: `akita-35` (Pixel 8a) and `m1q-36` (Galaxy S26), cpu and gpu,
`session-d5585b53` and `session-9002dfea` from a Mac, 2026-10-15; `akita-35`, gpu,
`session-17997931` and `session-b1179d6d` from an Ubuntu 24.04 container with no adb,
2026-10-16. [LiteRT-LM](https://github.com/google-ai-edge/LiteRT-LM) on [LiteRT](https://github.com/google-ai-edge/litert).
