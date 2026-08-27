# edge-llm-bench — agent operating notes

Neutral, reproducible standing benchmark for local LLM engines on real
devices. "Neutral" and "reproducible" are load-bearing: breaking the rules
below produces *wrong-looking-right* numbers, which is worse than an error.

## Commands (all non-interactive, exit codes are meaningful)

```bash
./bench doctor            # preflight; every FAIL prints its fix command; exit 1 on failure
./bench release-watch     # upstream releases vs environment.lock.json pins
./bench matrix  <cells>   # capture -> summary -> LEADERBOARD; exit 2 if zero cells matched
./bench regress <cells> --engine <arm> --version <v> --baseline <sel>   # exit 1 = REGRESSION somewhere
```

First-time setup and honest per-lane durations: README "Setup" (Mac ~45 min,
Android ~15 min, iPhone half a day + GUI signing). Runbooks:
`docs/OPERATIONS.md`. What breaks from a clean clone and why:
`docs/first-run-rehearsal-2026-08-26.md`.

## Machine-readable surfaces (prefer these over parsing prose)

- `schema/result.v1.json` — every run record's shape; raw records in
  `results/raw/<campaign>/` (a number without a stored report is not a
  measurement).
- `results/summary/*.csv` — derived accumulation layer (regenerate, never edit).
- `results/regression-reports/*/verdicts.json` — machine-readable verdicts.
- `environment.lock.json` / `android/engine-pins.json` — pin registry; rows
  stamp the *observed* engine (witness) which may differ from the registry.

## Rules that produce wrong numbers when broken (slugs cited in code)

Full text: `methodology/fairness-rules.md`. The five working rules:
`quant-per-arm-rule` (recipe visible in every row), `quant-label-rule`
("int4" is not a spec; Gemma-4 `.litertlm` = wNa8o8, non-transferable),
`budget-mode-rule` (never mix budgets/modes across arms),
`spread-rule` (wide trial spread ⇒ throw out, re-run),
`stored-report-rule`.

## Hard constraints for agents

- **Never pool numbers across capture sessions.** Devices drift 16-25%
  between sittings; cross-session deltas only count through session anchors.
  `render_leaderboard.arm_row` is the one aggregation — charts import it;
  do not write a second one.
- **Generated files are generated.** LEADERBOARD.md between its markers,
  `results/summary/*`, `docs/charts/*.png` (only via
  `scripts/generate_charts.py` — never hand-draw a numbers figure).
- **Cross-runtime standings stay LOCAL (2026-08-27, owner decision).** The
  public repo is shared as a harness only: LEADERBOARD.md and the comparison
  charts (crossarm_table / demo_models_table / pixel8a_model_demo) are
  gitignored — render locally, never commit or re-add them. Single-runtime
  regression charts (v0160_regression_verdicts.png) are the committed
  exception. Cross-runtime speed comparison is published for Gemma-4 only,
  and in the archive repo, not here.
- **Quarantined captures stay on disk.** `*.jsonl.attempt1` /
  `device-jsonl-flagged/` are audit trail, not garbage.
- **Builds**: `bootstrap.sh` then `build_yardstick_mac.sh`; derived data is
  repo-local (`.build/dd-mac`). Wipe it when the vendored LiteRT-LM tag
  changes — stale module state produces bogus "cannot find in scope" errors.
- **litert cells can hang ~10 min at teardown** — runners wrap with
  gtimeout; keep `CELL_TIMEOUT` generous, the on-disk runs are already safe.
- The mac runner refuses to start while a heavy export pipeline runs
  (unified-memory contention) — that guard is correct; don't bypass it.

## Where a human is required (do not try to automate)

Plugging/unplugging devices (energy cells are `manual=1` by design), iPhone
signing + the two increased-memory entitlements (Xcode GUI only), device
thermal environment, and pin-bump decisions (release-watch informs, a person
decides).
