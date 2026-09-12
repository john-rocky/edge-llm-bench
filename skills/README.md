# Agent skills

Each skill is a self-contained `SKILL.md` playbook an agent can load to operate
this harness without prior knowledge of the repo. Same format as the skills in
[google-ai-edge/litert-samples](https://github.com/google-ai-edge/litert-samples/tree/main/skills).

## Available skills

* [`run-edge-llm-bench/`](run-edge-llm-bench/) — Measure a
  [LiteRT-LM](https://github.com/google-ai-edge/LiteRT-LM) bundle on a
  connected Android phone or a Mac, ad hoc: write the cells, run them, read the
  stored record; side-load a bundle that is not published yet, or measure a
  build newer than the pin.

## Planned

* Operator profiling as part of a run (`./bench profile`) — design:
  [`docs/profiling-subcommand-design.md`](../docs/profiling-subcommand-design.md).
* System profiling (Android `simpleperf`, Instruments on Apple devices) — after
  operator profiling is in.

## Installing

Point your agent at the directory, or copy (or symlink) `skills/<name>/` into
the agent's skills folder (Claude Code: `.claude/skills/<name>/`).
