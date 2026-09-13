# Agent skills

Each skill is a self-contained `SKILL.md` playbook an agent can load to operate
this harness without prior knowledge of the repo. Same format as the skills in
[google-ai-edge/litert-samples](https://github.com/google-ai-edge/litert-samples/tree/main/skills).

## Available skills

* [`run-edge-llm-bench/`](run-edge-llm-bench/) — Measure a
  [LiteRT-LM](https://github.com/google-ai-edge/LiteRT-LM) bundle on a
  connected Android phone or a Mac, ad hoc: write the cells, run them, read the
  stored record; side-load a bundle that is not published yet, or measure a
  build newer than the pin; profile the decode step per op on Android
  (`./bench profile`, [`docs/profiling-subcommand-design.md`](../docs/profiling-subcommand-design.md)).

* [`profile-litert-lm-system/`](profile-litert-lm-system/) — Profile a
  LiteRT-LM run at the system level when the per-op table leaves the question
  open: Android `simpleperf` (whole process, attached during decode, dwarf
  callers) and Instruments via `xcrun xctrace` on a Mac or, over USB, on an
  iPhone running the harness app (Metal System Trace occupancy, Time Profiler
  self time), each paired with an unprofiled control
  and stored beside the run under `profiles/system/`.

## Installing

Point your agent at the directory, or copy (or symlink) `skills/<name>/` into
the agent's skills folder (Claude Code: `.claude/skills/<name>/`).
