# Endurance methodology — multi-turn sessions measured in the tens of minutes

Task C (`sustained-generation`) answers "does one 512-token reply degrade?".
This protocol answers the question a chat app actually lives with: **what
happens to the 40th turn of a conversation the process has been holding for
half an hour** — decode decay, memory creep, degeneracy onset, or death.

Task id: `endurance-chat-<N>m` (standing cell: `endurance-chat-30m`; a `-2m`
smoke variant exists for harness checks). Implementation:
`EnduranceChatTask` / `EnduranceSession` / `MediaPipeRuntime.enduranceChat`;
baseline cells: `matrices/endurance-mac.cells`.

## Scenario

One engine process. One model load. Then a scripted multi-turn chat until the
wall clock (measured from the start of turn 1) passes N minutes:

- **Turns** cycle through the fixed 12-prompt script in
  `prompts/endurance-chat.md` — short factual turns, follow-ups that reference
  earlier turns (so the accumulated KV is genuinely attended to), and periodic
  summarize-everything turns that sweep the full context.
- **One conversation, accumulating KV.** Turn K+1 continues the conversation
  of turn K; per-turn prefill is the delta, not the history.
- **Context budget** is fixed per cell (`--context-tokens`, baseline 4096 for
  every model — same-budget). When the next turn would not fit
  (`getTokenCount()` + prompt estimate + output cap + margin > budget), the
  conversation is **rolled over**: disposed and recreated, a full re-prefill
  from empty KV. Rollovers are counted and flagged per turn — the chat-app
  behavior, recorded, never a silently widened budget. Rollover also makes the
  session exercise *both* leak classes: KV growth within a conversation and
  conversation create/destroy cycles across it.
- **Per-turn output cap 256 tokens**, enforced natively (LiteRT-LM
  `maxOutputTokens`, v0.16+), so the engine's per-turn decode counters cover
  exactly the measured tokens — no post-cap drain. Sampling is Task C's chat
  configuration: temperature 0.7, topP 0.9, topK 40.
- **Watchdog**: no stream event for 180 s, or a turn exceeding 600 s, cancels
  the conversation and ends the session as `hang`. A thrown turn ends it as
  `crash`. Three consecutive turns streaming no text end it as `empty-output`.
  All of these keep their record and their partial series (failed-runs-stay).

LiteRT-LM only for now — the loop needs a persistent conversation, a native
per-call cap, and per-turn engine counters, which the cross-runtime
`LLMRuntime.generate` surface deliberately does not expose (same precedent as
`--litert-native-benchmark`). This lane produces **no cross-runtime rows**.

## What is recorded

Two files per cell, both raw (stored-report-rule):

1. `<cell>.turns.ndjson` — one line per turn, **written as the turn
   completes** (a crash at turn 37 leaves turns 1–36 on disk): engine
   prefill/decode token counts and rates for that turn, wall TTFT and
   wall-clock decode rate, KV occupancy after the turn, `phys_footprint` /
   resident after the turn (memory.md basis), thermal state, stop reason,
   rollover flag, degeneracy flag, output head.
2. `<cell>.jsonl` — one schema-v1 session record (`schemaVersion`, engine
   pins, device snapshot, the standard memory/thermal fields sampled over the
   whole session) plus the additive `endurance` object with the derived
   verdicts. `metrics.decodeTokensPerSecond` is the **median of per-turn
   engine decode rates**.

## Derived verdicts (computed at capture time, within one session only)

- **Decay** — median per-turn decode tok/s of turns starting in the first
  5 minutes vs turns starting in the last 5 minutes;
  `decodeDecayPercent = (first − last) / first × 100`. Only emitted when the
  session outlasted two disjoint windows.
- **Memory gradient** — least-squares slope of after-turn `phys_footprint`
  against turn index (`memorySlopeMBPerTurn`) and against minutes. The
  leak-class signal is a persistent positive slope that survives rollovers; a
  sawtooth that resets at rollover is KV, not a leak — read the sidecar series
  before naming a cause (refute-first).
- **Degeneracy** — per turn, on thought + visible text, using the
  litertlm-convert `verify_quality.degenerate()` rules verbatim (looping
  5-grams ≥3, unique-word ratio < 0.30, character collapse, special-token
  spam). The record carries the count and first offending turn; the sidecar
  carries the per-turn flags and output heads.
- **Completion** — `completed | crash | hang | empty-output`.

## Fairness rules, applied to endurance

- **same-budget** — same turn script, same per-turn cap, same context budget
  for every model and engine version under comparison. Never compare cells
  whose cap or budget differ.
- **cold-warm-split** — a session is one fresh process (`coldRun: true`);
  there is no warm regime. Turn 1 carries the cold-start penalty; the decay
  windows compare minutes 0–5 against the end, both inside the same process.
  Start sessions at `nominal` (the cell gate flags HOT and re-runs once).
- **quant-per-arm / quant-label** — the catalog recipe string rides every row
  (e.g. granite-4.2-3b is `int4 BOCTAV4 (block32, int8 embedder)`, not
  "int4").
- **Thinking models** are disclosed (catalog entry + cells comment): their
  turns spend the cap on the thought channel, so their tok/s is not
  answer-throughput-comparable with non-thinking models at the same cap.
- **spread-rule** — within-session turn spread is the instrument here (a wide
  first-window spread means a contended machine: throw the session out and
  re-run). **Sessions are never pooled**: one session = one record; a
  cross-session delta only counts through the usual session anchors
  (`iphone-session-variance`), and `runs=1` is enforced in the cells.
- **failed-runs-stay** — crash/hang/empty sessions keep row, record, and
  partial series; the CLI exits 1 so the runner logs the failure too.

## Power (Mac, optional)

`powermetrics` needs root; runners cannot assume it. When an operator wants
the power/throttle trace, start a sidecar **before** the campaign in a
separate terminal:

```
sudo powermetrics -i 5000 --samplers cpu_power,gpu_power,thermal \
  -o results/raw/<campaign>/powermetrics.txt
```

and stop it after. The trace is disclosure (disclose-hw-state), not a
per-token energy figure; iOS energy stays on the battery-tick basis
(energy.md). Sessions without the sidecar simply record no power — never a
fabricated number.

## Reading the series — traps the first baseline already hit (2026-09-01)

- **The first minutes are a ramp, not a leak.** granite-4.2-3b's footprint
  climbed 2,419 → 4,057 MB inside the first two minutes (the 4096-token KV
  working set paging in) and then moved +21 MB over the remaining 28 — the
  whole-session least-squares slope (0.08 MB/turn) told the truth, the
  first-vs-last-turn delta (+1,659 MB) did not. Judge slope on the
  post-ramp region.
- **A one-token turn evades the degeneracy heuristic** (it needs ≥10 words),
  and a session of them never trips `empty-output` (which needs *zero*
  chunks). granite spent whole multi-minute stretches emitting exactly one
  token per turn at KV > ~2000 — the deepest collapse in the session, and
  its `degenerate` flags read *false*. Read `decodeTokens`/`chunkCount`
  alongside the flag: median decode tokens ≈ 1 is the collapse, whatever
  the flag says.
- **Rollover-attributed memory is its own column.** gemma-4-E2B grew
  +1.0 MB *per conversation rollover* on average (197 rollovers → +198 MB
  across 30 min; plain turns netted −51 MB). Attribute footprint deltas to
  rollover vs plain turns before calling a slope a leak — and a persistent
  per-rollover cost IS the leak-class signal, at the conversation
  granularity rather than the turn one.

## Reading a baseline

A healthy session: decay within a few percent, memory slope ≈ 0 after the
first few turns (allocator warm-up), zero degenerate turns, `completed`.
Anything else is a finding: reduce it to a minimal repro (shortest turn count
that reproduces, plain `yardstick run` command) before drafting an issue, and
compare thought-channel vs plain models before blaming the engine
(refute-first).
