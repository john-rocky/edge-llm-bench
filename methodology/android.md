# Android measurement semantics — what transfers from the Apple lane and what does not

The Android column shares the schema (result.v1), the accumulation layer, the
regression differ, and the fairness rules. The measurement *mechanics* differ;
every difference below is disclosed here once so tables don't have to.

## Arms

| arm | recorded runtime | acquisition | backend |
|---|---|---|---|
| LiteRT-LM | `litert-lm-cpu` / `litert-lm-gpu` / `litert-lm-npu` | per-release bazel+NDK source build (`android/scripts/build_litert_lm_main.sh`) — releases ship no Android binary (verified v0.14–v0.16); upstream build bug + fix flag: google-ai-edge/LiteRT-LM#3247 | cpu, gpu (ML Drift .so set). NPU (`litert-lm-npu`, Galaxy S26): an own runtime build with the Qualcomm dispatch libraries (a side build, cells `engine-build=`) and an own SM8850 export (Qwen3 0.6B only), hardware KV-cache update off; a launch counts only when the engine's own lines show the NPU chosen, registered and dispatched to; the other models `exclude=` with the reason — `docs/dashboard-cells-v1.md` "LiteRT-LM on the NPU" |
| llama.cpp | `llama.cpp` (CPU) / `llama.cpp-npu` / `llama.cpp-gpu` | official release artifact `llama-<tag>-bin-android-arm64.tar.gz`, same tag as the Apple arm (official-sdk rule) | CPU: the official `android-arm64` artifact at the pinned tag. NPU and GPU on Snapdragon phones (`llama.cpp-npu` / `llama.cpp-gpu`): the release's official `android-arm64-snapdragon` artifact as a side build (cells `engine-build=`), Hexagon HTP / Adreno OpenCL, run with the official wrapper's settings; a launch counts only when the engine's own lines show the device — `docs/dashboard-cells-v1.md` "NPU and Android GPU rows" |
| MLX / Core AI | — | Apple-only; render as n/a | |
| Cactus | — | phase 2 slot (`environment.lock.json` `arms.cactus.android: planned`) | |

Backend is part of arm identity (`litert-lm-gpu` vs `litert-lm-cpu`) because the
regression join key has no backend column — same convention as Core AI's
`-ane`/`-gpu` model ids on iOS.

The Maven `litertlm-android` AAR is the *official* Android artifact but exposes
only the Kotlin API (no CLI): using it means an instrumented APK harness. That
is the official-sdk-rule tension for this arm, recorded as a phase-2 option;
v1 measures the same engine through `litert_lm_main`.

## Regimes

- One engine process per run = **cold** by this repo's definition (fresh
  process, caches on disk). The very first run per (model, backend) builds the
  ML Drift / OpenCL caches → labelled `firstEver`, reported separately, never
  as the engine's speed (cold-warm-split). Detection is automatic: a marker
  file on the device (`markers/<artifact>.<backend>.cachebuilt`, written after
  the first clean exit) — the caches live on the device, so host state cannot
  know whether this (model, backend) already compiled there. litert-lm, and
  the chat launches of the llama.cpp GPU side build (its OpenCL program cache:
  `markers/<artifact>.llama.cpp-gpu.<engine sha>.cachebuilt`, and a build whose
  cache directory holds no program reads as not built); the pinned CPU
  llama.cpp build and llama.cpp on the NPU keep no persistent compile cache
  (LiteRT-LM on the NPU keeps litert-lm's marker until a device run shows
  whether its AOT bundle builds anything). `firstEver` rows stay in raw
  and in `device-runs.csv`, and are excluded from every metric pool
  (leaderboard `arm_row`, `regression_diff` cells). One-time cold-start
  behavior, verified on the S26 2026-08-31: a device whose caches predate
  the marker scheme labels its next run 1 firstEver anyway — conservative
  (one clean run leaves the pool once per (model, backend)), never the
  reverse (a cache build never pools as speed).
- **No warm regime in v1**: the CLIs have no in-process repeat for prompt tasks
  (`--multi_turns` is interactive). Android cells therefore compare against
  Apple **cold** rows only. llama-bench (`native-benchmark-*` task) repeats
  in-process and is recorded `coldRun=false`; litert `--benchmark` is a fresh
  process (`coldRun=true`) — the two native rows are different regimes and the
  join key already separates them.

## Metrics — measured vs absent (absent stays absent)

| metric | litert_lm_main | llama-cli | llama-bench |
|---|---|---|---|
| decode / prefill tok/s | engine-reported | engine-reported | engine-reported (avg_ts) |
| TTFT | engine-reported (excludes init, like iOS loadTime split) | **absent** | **absent** |
| memory | driver RSS sampler (`/proc/<pid>/status` VmRSS, 0.5 s, median) → `memoryMedianResidentMB`; `memoryMedianMB` (phys_footprint) has **no Android equivalent — never fabricated**. The device buffers of a GPU or NPU arm (ML Drift / OpenCL / HTP0 / Qualcomm NPU memory) sit outside the process RSS; a side build's records (llama.cpp, LiteRT-LM on the NPU) say so in `provenance.rssBasis` | same | same |
| energy | manual only (batterystats delta, unplugged) — phase 2 protocol, owner-triggered | same | same |

## Conditions pinned per run

- `taskset f0` (big cores; upstream's own recommendation) — in `conditions.cpuAffinity`.
  That is the launch mask; an engine may set its own affinity (LiteRT-LM: cpu4-8 on the
  Pixel 8a, `devices/pixel-8a.md`), so the sampler also reads the engine's
  `Cpus_allowed_list` during the run and the record keeps the last read in
  `conditions.cpusAllowedList` (since 2026-10-07).
- Thermal: `dumpsys thermalservice` status int; 0 → `"nominal"` so the repo's
  nominal gate works unchanged; the raw int rides along in
  `conditions.thermalRawStatus`. Gate: wait for status 0 up to `THERMAL_WAIT`
  (default 600 s), run anyway after timeout and record it (`THERMAL_GATE.txt`).
- CPU frequency cap (cpu-cap-rule, `fairness-rules.md` §13): status 0 does not mean
  the clock is free — a charging Pixel 8a held cpu4-7 at 1418-2130 MHz of 2367 during
  runs with the status at 0 (2026-10-07). Before each launch `run_cell.py` waits up to
  `CPUCAP_WAIT` (default 300 s) for every cpufreq policy's `scaling_max_freq` to be back at
  `cpuinfo_max_freq` (`cpu-capped-at-start` and a `THERMAL_GATE.txt` line when it is not);
  during the launch the sampler reads every policy's `scaling_max_freq` with the RSS, the
  record keeps each policy's lowest read (`conditions.cpuMaxFreqMHz`, min / hw / cpus in
  MHz), and a run during which a policy of the engine's CPUs sat below its hardware
  maximum is flagged `cpu-capped`. It pools into no number when that ceiling fell more
  than 15 % (summary `cpu_cap_drop_pct` above `render_leaderboard.CPU_CAP_MAX_DROP_PCT`),
  and pools, marked, when it fell less.
- Battery level/state from `dumpsys battery` (disclose-hw-state).
- Screen: benches run with USB attached. The screen state is read from the
  phone before every launch (`dumpsys power`, `mWakefulness`) and stamped in
  `conditions.screen`: `on-usb` when `Awake`, otherwise
  `off-usb (mWakefulness=…)`, with `conditions.screenSource: "measured"` (a
  long-context sitting stamps its own per-round read instead, `"env"`) and
  the "Stay awake" setting beside it (`conditions.stayOnWhilePluggedIn`). On
  and off are both admissible for the speed cells (the display is not used);
  the anchor decides the session. Until 2026-09-26 `run_cell.py`,
  `endurance_cell.py` and `run_profile.py` wrote a fixed `on-usb` outside
  sitting mode — not a reading. Energy cells will run unplugged by hand;
  speed cells accept the USB-attached state exactly like the iPhone
  plugged-speed protocol.
- Sampler: litert_lm_main exposes **no temperature/top-p flags** →
  `conditions.sampler: "engine-default"`. This is a disclosed same-budget-rule
  deviation; llama-cli runs `--temp 0 --top-p 1` (greedy) like the Apple arms.
- Decode span: **litert_lm_main v0.16.0 ignores `--max_output_tokens`** — the
  driver passes the 128-token task budget and the engine still runs to the
  model's own stop (probe 2026-08-27, Pixel 8a: `--max_output_tokens=128` →
  441 generated tokens; raw in
  `results/raw/2026-08-27-audit-probes-android/probe-litert-cap/`). llama-cli
  honors `-n 128`, so Android llama↔litert rows compare a 128-token decode
  against a 441–1037-token one (per-run counts in every litert record). The
  asymmetry is disclosed rather than corrected because (a) no working cap
  exists on that binary and (b) the litert decode rates it produces reproduce
  within ~1% across sessions — the longer span is not visibly moving them.
  The engine-default generations are deterministic per (model, backend), so
  the span is stable run to run.
- Prompts: byte-identical to the Swift tasks via committed `prompts/text/*.txt`
  (`scripts/gen_task_prompts.py`).

## Quality axis

No on-device GSM8K in v1. Quality is a property of (artifact, runtime
numerics); the Mac instrument measures each checkpoint once, and Android rows
link by artifact `sha256` recorded per run. **Caveat that must travel with any
quality claim**: the Mac yardstick exercises macOS kernels, not Mali/Tensor
kernels — cross-device numerical parity is assumed, not verified. Phase-2
mitigation: a 25-question on-device spot check through
`--input_prompt_file` to test the assumption cheaply.

## Session discipline

Anchors first, payload interleaved per round (interleave-arms), ≥120 s
cooldown — between cells AND between the runs inside a multi-run cell
(`run_cell.py --cooldown`, passed by the campaign runner). Publish every
round. Cross-session comparisons only through anchors
(`regression_diff.py --anchors`), same as Apple.

Capture gate (mac/iPhone parity, `scripts/cell_gate.py`): every completed
cell is judged; HOT / DEAD / COLLAPSE quarantines the capture in raw
(`*.json.attempt1`) and re-runs the cell ONCE after `GATE_COOLDOWN`
(default 180 s) — anchors immediately (a contended anchor poisons every
anchor-normalized verdict of the session), payload cells after their last
round. The retry is a consecutive block, disclosed in
`session_provenance.txt` because it deviates from per-round interleaving.
A flagged retry stands with a `FLAGGED.txt` note; SHORT never retries
(failed-runs-stay). The whole path runs device-free in CI:
`android/bench/selftest.py` (fake adb, scripted engine output, real gate).

Text check (text-check-rule, `methodology/fairness-rules.md` §12): every
context-prompt launch — a LiteRT-LM prompt task with `context-tokens=`,
`litert_lm_advanced_main --num_iterations=2` — has its decoded text checked by
default since 2026-10-06 (`BENCH_TEXT_CHECK=0` turns it off; before, only the
sittings that set `BENCH_TEXT_CHECK=1` were checked, so the weekly job's 1024
cells were not). `run_cell.py` cuts each iteration's reply from the console at
the turn boundary, stores it beside the record (`*.decoded.txt`, sha256 in
`conditions.textOutputSHA256`) and screens it with `parsers.text_integrity`
(empty or degenerate, off the task's subject, repetition loop); the verdict is
`conditions.textCheck`, its flags join `protocolFlags`. A FAIL launch keeps
both records, the text and the log, is listed in `FAILURES.txt`, and never
triggers the gate's re-run (a re-run reproduces it); `build_summary.py` writes
the verdict as `text_check` and `render_leaderboard.arm_row` keeps FAIL runs
out of every number. The plain `litert_lm_main` short-chat launch and
llama-cli store no decoded text and are not checked.
