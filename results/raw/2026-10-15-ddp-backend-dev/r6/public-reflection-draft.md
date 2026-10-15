# D6 DDP backend — public reflection draft (round 6, lane close)

Draft only: no other repo touched, nothing pushed. Placement, wording and timing are the supervisor's and the
user's (a Draft PR or a commit after the user's GO; the code blocks below ran on 2026-10-15 from a Mac through
the smoke and slice sessions, `ROUND2.md` / `ROUND3.md`). Every fact below is from this lane's records; no
DDP-to-attached-phone figure belongs in any of these texts.

## A. own repo — `skills/run-edge-llm-bench/SKILL.md` (edge-llm-bench, same PR as `ddp-backend` or right after it)

Where: a new section between "## The two ad-hoc cases" and "## Symptoms"; the frontmatter `description` gains
"or on a Developer Device Platform lab phone with no adb"; "Tested on" gains the DDP line. Draft text:

```markdown
## Lab phones without adb (Developer Device Platform)

The same Android LiteRT-LM cells run on a DDP lab phone, billed to your Cloud project:

    ./bench matrix <cells> --ddp <device id> --dry-run
    ./bench matrix <cells> --ddp <device id> --project <project> --bucket gs://<bucket>

Read the dry run first: one job per cell, at most 8 jobs per session, the pushes and the per-job
estimate. Runbook: `docs/OPERATIONS.md` "Runbook: run cells on DDP (a lab phone, no adb)".

- One job is one lab unit and its own sitting: the jobs of a session start together on different
  units (`conditions.ddp.serial`), so two cells of one session are two phones. There is no anchor on
  DDP, and the summary names the device `<model> (DDP <id>)`, so its rows never pool with an
  attached phone's.
- Some lab units start with lowered CPU clock ceilings; such runs carry `cpu-capped-at-start`, and the
  wait per id is `cpucapWaitSeconds` in `android/ddp/devices.json`.
- The record says what the engine caches did in each run (`conditions.engineCache`); `firstEver`
  marks only run 1.
- Pulled logcats carry the lab network's identifiers: the driver replaces them at pull time (originals
  in the gitignored `<campaign>/ddp-raw/`); the execution-level `logcat.txt` stays out of the commit.
```

Facts behind it: `docs/OPERATIONS.md` (runbook), `docs/ddp-integration.md` "Route C as `bench matrix --ddp`
(2026-10-15)", `android/ddp/devices.json`, `android/ddp/scrub.py`, `ROUND3.md` (parallel jobs, capped units),
`ROUND4.md` (engineCache, scrub). The assets row's `skill` cell (hold) could point here once it lands and has
had its blind run.

## B. litert-samples — `skills/benchmark-on-ddp/SKILL.md` (google-ai-edge/litert-samples, Draft PR through /litert-team after the user's GO)

This skill is the one about DDP; the launch's candidate `skills/on-device-verification` is about CompiledModel
parity of converted models (section C). Where: "## Watch for", four bullets after "DDP device names come from
the matrix". Draft text:

```markdown
- **A session's jobs run at once, each on its own lab unit.** Two jobs of one session are two phones
  (the session report names only the device id; `getprop ro.serialno` in the job tells the units
  apart); compare runs inside one job, and treat a row from another job as another sitting.
- **Some lab units start with lowered CPU clock ceilings** (on 2026-10-15 every SM-S942U1 unit of
  m1q-36, from before the first run): compare `scaling_max_freq` with `cpuinfo_max_freq` at the start
  of a CPU job, and say so in the row.
- **Job arguments are split at spaces.** An argument that holds spaces reaches the binary as several;
  a wrapper of your own takes the command line last and joins it, or passes no spaces.
- **Pulled logcats carry the lab network's identifiers** (SSID, BSSID, MAC, addresses): keep them
  out of a public commit, or replace those strings first.
```

Optional fifth bullet (the user decides; it names the user's own harness):

```markdown
- **A LiteRT-LM cell with a real prompt file** (chat template, text check) is outside this CLI's DDP
  target (fixed benchmark flags, no prompt push); edge-llm-bench's `bench matrix <cells> --ddp <id>`
  runs those cells with its own build.
```

Facts behind it: `ROUND2.md` (`argc: 18` for 13 request args), `ROUND3.md` (8 jobs on 8 units at once; the
m1q-36 ceilings), the slice's `ddp/session-1.json` (`deviceId` only, no serial; the serials come from the
wrapper's `provenance.txt`), `docs/ddp-integration.md` (Route C), litert-cli 0.2.1 `ddp.py` (fixed `.litertlm` flags,
no prompt push; `docs/ddp-integration.md`). The upstream file read for placement: `git show
upstream/main:skills/benchmark-on-ddp/SKILL.md` (litert-samples upstream/main 2026-10-14, 85 lines).

## C. litert-samples — `skills/on-device-verification/SKILL.md`: none

Its loop is the parity of a converted `.tflite` through CompiledModel (reference dumps, host CPU / GPU, the
device's residency line). This lane measured LiteRT-LM benchmark cells on DDP and verified nothing about parity
or residency there, so there is no checked sentence to add.

## D. hf-to-litertlm (tool, docs, AGENTS.md Route row, llms.txt): none

Not a conversion lane: no converter step, recipe or Route changed (`~/code/litertlm-convert/CLAUDE.md` curation
filter); the DDP route is a measurement backend of edge-llm-bench.

## E. `~/code/standup/knowledge/litert.md`: one line (written in round 6)

The pointer line for the next session that looks for the DDP backend: the command, the three sessions, the
record fields, the scrub, the handoff and `LANE_CLOSE.md`.
