# edge-llm-bench

A neutral, reproducible benchmark harness for local LLM engines on real
devices — built to run continuously, not as one-off campaigns.

- **Engines**: LiteRT-LM, llama.cpp, MLX, Apple Core AI, Cactus (per-arm
  status in `environment.lock.json`)
- **Platforms**: macOS, iOS (iPhone), Android — one schema
  (`schema/result.v1.json`), one accumulation layer, one leaderboard
- **Rules as code**: budget/mode mismatches refuse to score, wide-spread
  cells are thrown out, cross-session deltas only count through session
  anchors (`methodology/fairness-rules.md`)

## The loop

```bash
./bench release-watch        # upstream releases vs environment.lock.json pins
./bench matrix  matrices/apple-warm-matrix.cells
./bench regress matrices/release-regression-litert.cells \
    --engine litert-lm --version v0.16.0 --baseline engine:v0.15.0
```

Every run emits schema-v1 JSON per record plus its raw console log
(`results/raw/<campaign>/`); `results/summary/*.csv` is the derived
accumulation layer; [`LEADERBOARD.md`](LEADERBOARD.md) renders from it;
regression verdicts persist under `results/regression-reports/`. CI keeps
all of it consistent.

**Operating manual** — release regressions, adding a model / arm / device,
what stays manual and why: [`docs/OPERATIONS.md`](docs/OPERATIONS.md).

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

## Per-arm honesty notes (read before comparing)

- Quantization is part of every row — arms run their own best available
  build, which is only a fair comparison when the recipe is visible. Gemma-4
  `.litertlm` is the wNa8o8 mobile schema, not uniform int4.
- The Core AI arm is best-effort: Gemma-4-class PLE models need an
  unpublished engine patch (`COREAI_STATIC_INPUTS`); a clean clone reports
  `unsupported`.
- Energy cells are manual by design (battery-delta needs the cable out).
- Android has no warm regime in v1 and no TTFT on llama-cli; every disclosed
  deviation is in `methodology/android.md`.

License: MIT.
