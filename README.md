# edge-llm-bench

A neutral, reproducible benchmark harness for local LLM engines on real
devices — built to run continuously, not as one-off campaigns.

- **Engines**: LiteRT-LM, llama.cpp, MLX, Apple Core AI, Cactus — every pin
  lives in `environment.lock.json`
- **Devices**: Mac Studio (M4 Max), iPhone 17 Pro, Pixel 8a, Galaxy S26 —
  one schema (`schema/result.v1.json`), one accumulation layer, one
  leaderboard

![LiteRT-LM v0.16.0 release-regression verdicts — one bar per scored cell, anchor-normalized where cross-session](docs/charts/v0160_regression_verdicts.png)

This repo is shared as a **harness**. The pipeline, every raw capture record,
and the machine-readable regression verdicts ship here — but the repo does
not publish cross-runtime standings. Render your own locally any time from
the shipped raw:

```bash
python3 scripts/build_summary.py && python3 scripts/render_leaderboard.py
# -> LEADERBOARD.md (local, gitignored)
```

## The loop

```bash
./bench release-watch        # upstream releases vs environment.lock.json pins
./bench matrix  matrices/apple-warm-matrix.cells
./bench regress matrices/release-regression-litert.cells \
    --engine litert-lm --version v0.16.0 --baseline engine:v0.15.0
```

Adding a model is one line in a cells file. This exact line is behind the
Pixel 8a LFM2.5 gpu rows:

```
android litert-lm litert-community/LFM2.5-1.2B-Instruct short-chat backend=gpu file=LFM2.5-1.2B-Instruct_int4_gpu.litertlm
```

Every run emits schema-v1 JSON per record plus its raw console log
(`results/raw/<campaign>/`) — a number without a stored report is not a
measurement. `results/summary/*.csv` is the derived accumulation layer; a
local `LEADERBOARD.md` renders from it (`scripts/render_leaderboard.py`);
regression verdicts persist as machine-readable JSON under
`results/regression-reports/`. CI keeps all of it consistent.

**Operating manual** — release regressions, adding a model / arm / device,
what stays manual and why: [`docs/OPERATIONS.md`](docs/OPERATIONS.md).

## Setup

Reading needs none: every raw record (`results/raw/`) and the regression
verdicts ship in the repo, and the standings render locally from them (one
command, above). To measure, start with

```bash
./bench doctor        # says exactly what is missing, with the fix command
```

**Mac lane** — the shortest path to a first number (~45 min first time,
measured 2026-08-26: 37 min bootstrap on a contended machine — expect
~20–30 min solo — plus a 4-min build, then seconds to measure;
`docs/first-run-rehearsal-2026-08-26.md`):

```bash
brew install xcodegen coreutils
ios/BenchmarkApp/scripts/bootstrap.sh      # vendored engines — the long step
scripts/build_yardstick_mac.sh             # full-flavor CLI build
./bench matrix matrices/deepseek-r1-1.5b-crossarm.cells --platform mac
```

**Android lane** — prebuilt engine binaries are on the
[releases page](https://github.com/john-rocky/edge-llm-bench/releases), so no
bazel/NDK build is needed: `android/README.md` (~15 min with an authorized
device).

**iPhone lane** — the heavy one: building and installing BenchmarkApp needs
Xcode signing plus two increased-memory entitlements that are GUI-only. Plan
half a day the first time; `docs/OPERATIONS.md` has the runbook.

Mac and iPhone captures self-police: a run that starts hot, lands with wide
trial spread, or records no decode at all is quarantined and retried once
automatically (`scripts/cell_gate.py`); what stays flagged is marked ⚠ in the
locally rendered leaderboard and charts, never silently kept. The Android driver's guards are
a thermal-nominal wait and a per-device campaign lock (two interleaved
drivers corrupt both campaigns — measured; `methodology/android.md`); its
post-capture gate is a disclosed phase-2 gap.

## What keeps the numbers honest

- **The recipe is part of every row.** Arms run their own best available
  build; quantization and engine pin sit in the row because a faster number
  under a different recipe is a different deployment profile, not a win.
  "int4" is not a spec — Gemma-4 `.litertlm` is the wNa8o8 mobile schema and
  is labeled as such.
- **Wide trial spread throws the cell out.** Trials that disagree come back
  UNRELIABLE instead of scored.
- **Failed runs stay in the table.** Crashes, OOMs, and unsupported configs
  keep their row; the reason is the datum.
- **Cross-session deltas only count through session anchors.** Devices drift
  between sittings, so every session runs an anchor cell first and deltas
  are normalized through it.
- **Mismatched budgets or modes refuse to score.**

Full rules, cited by slug from the code: [`methodology/fairness-rules.md`](methodology/fairness-rules.md).

## Coverage

**measured** = stored capture sessions in `results/raw/` today. **wired** =
the arm builds at its pinned version but has no stored captures yet. **n/a**
always carries its reason — that is part of the method, not an apology.

| engine | Mac Studio (M4 Max) | iPhone 17 Pro | Pixel 8a | Galaxy S26 |
|---|---|---|---|---|
| LiteRT-LM | measured | measured | measured (cpu, gpu) | measured (cpu, gpu) |
| llama.cpp | wired | wired | measured (cpu) | measured (cpu) |
| MLX | measured | measured | n/a — Apple-only | n/a — Apple-only |
| Core AI | wired (external runner) | measured | n/a — Apple-only | n/a — Apple-only |
| Cactus | n/a — no Mac arm | wired | planned | planned |

- Android LiteRT NPU is n/a on both devices — the NPU path is Early Access
  only (`methodology/android.md`).
- Android llama.cpp is the official CPU release binary at the same tag as
  the Apple arm; GPU would need a custom NDK build and is a disclosed gap.
- Android v1 has no warm regime and no TTFT on llama-cli; every disclosed
  deviation is in `methodology/android.md`.
- Mac Core AI has no rows because the pinned 0.2.0 release does not run on
  the bench Mac's macOS 27 beta (`environment.lock.json`).
- The Core AI arm is best-effort: Gemma-4-class PLE models need an
  unpublished engine patch (`COREAI_STATIC_INPUTS`); a clean clone reports
  `unsupported`. Missing exports stay visible as reasoned rows (DeepSeek-R1
  1.5B: bundle pending export).
- Cactus Android is a phase-2 slot at the pinned commit; until then the
  driver reports the row with its reason.
- Energy cells are manual by design (battery-delta needs the cable out).

## Endurance

Run-once benchmarks answer "how fast is turn 1". A chat app lives with a
different question: what happens to the 40th turn of a conversation the
process has been holding for half an hour. The endurance task
(`endurance-chat-30m`) measures that on real devices — one engine process,
one conversation with accumulating KV, a fixed 12-prompt script, a native
256-token per-turn cap. Every turn is recorded as it completes: engine
decode rate, KV occupancy, memory, thermal state, degeneracy. A crash at
turn 37 keeps turns 1–36 as evidence. When the conversation outgrows its
context budget it rolls over the way a chat app would; the rollover is
counted, never a silently widened budget.

Each session derives four verdicts: decode decay (first 5 minutes vs last
5), memory slope (leak-class detection, rollover-attributed), degeneracy
onset, and completion. Protocol and fairness rules:
[`methodology/endurance.md`](methodology/endurance.md). Lanes: Mac
(`matrices/endurance-mac.cells`) and Android on Galaxy S26
(`matrices/endurance-android.cells`) — the Android lane builds a small
harness driver against the pinned LiteRT-LM tag because no stock CLI can
hold a scripted multi-turn conversation. LiteRT-LM only for now; no
cross-runtime rows. The whole Android path also runs with no phone attached
(`android/bench/selftest.py`, fake adb), so CI proves the wiring on every
push.

This is deliberately the half of the eval story that quality harnesses
don't cover: tools like ai-edge-eval measure what a model answers; this
repo measures what the device and engine do over time. Sustained
performance on real hardware, with the raw per-turn series stored behind
every claim.

## Seed baseline

This repo starts with the 2026-08-17 LiteRT-LM v0.15.0 → v0.16.0 regression
run as its founding baseline: Pixel 8a (Android lane) and Mac Studio M4 Max,
verdicts in `results/regression-reports/`. On the Pixel GPU the release is a
clean pass (decode +0.3%); on the Mac, Qwen3-0.6B decode improved ~14% over
the July v0.13.1 rows (anchor-normalized) and Gemma-4-E2B stayed flat.

## Provenance

The harness was carved out of
[apple-silicon-llm-bench](https://github.com/john-rocky/apple-silicon-llm-bench),
which remains the measurement archive (published campaign tables, full raw
history back to 2026-05, and the `./reproduce` registry mapping each
published table to its pinned command). Numbers in that archive were
measured with the same harness code; this repo is canonical for the harness
going forward.

License: MIT.
