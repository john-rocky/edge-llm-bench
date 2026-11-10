# Background

## How records are kept

Every run emits schema-v1 JSON per record plus its raw console log
(`results/raw/<campaign>/`) — a number without a stored report is not a
measurement. `results/summary/*.csv` is the derived accumulation layer; a
local `LEADERBOARD.md` renders from it (`scripts/render_leaderboard.py`);
regression verdicts persist as machine-readable JSON under
`results/regression-reports/`. CI keeps all of it consistent.

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

Full rules, cited by slug from the code: [`methodology/fairness-rules.md`](../methodology/fairness-rules.md).

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
[`methodology/endurance.md`](../methodology/endurance.md). Lanes: Mac
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
