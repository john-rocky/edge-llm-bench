# First-time setup

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

**Windows lane** — driven over SSH from another machine; LiteRT-LM has no
Windows release asset, so the engine is built on the host (about 50 min on a
16-core laptop) and llama.cpp comes from the pinned release assets:
`windows/README.md`.

Mac and iPhone captures self-police: a run that starts hot, lands with wide
trial spread, or records no decode at all is quarantined and retried once
automatically (`scripts/cell_gate.py`); what stays flagged is marked ⚠ in the
locally rendered leaderboard and charts, never silently kept. The Android driver's guards are
a thermal-nominal wait and a per-device campaign lock (two interleaved
drivers corrupt both campaigns — measured; `methodology/android.md`); its
post-capture gate is a disclosed phase-2 gap.
