# Operator profiling as a `bench` subcommand — design (v0, 2026-09-12)

Goal: a run can carry LiteRT-LM's per-op profile next to its speed record, so
an agent that measured a bundle can also see where the decode step goes -
without the profile ever changing the speed number. Everything under "today"
was run; everything under "next" was not.

## Today (verified)

- **The flag.** `litert_lm_advanced_main --enable_profiling` -
  [shared_flags.cc](https://github.com/google-ai-edge/LiteRT-LM/blob/main/runtime/engine/shared_flags.cc)
  ("Enable per-op profiling.", present at v0.16.0 and v0.17.0). The profile is
  the LiteRT per-op table (`Profile Summary` / `Run Order`: node type, avg ms,
  %, times called, name) appended to `BenchmarkInfo`. CPU rows are mostly
  builtin ops plus `Delegate/` partitions; GPU rows are all `Delegate/<kernel>`.
- **The captures.** Galaxy S26, the pinned v0.16.0 `litert_lm_advanced_main`
  (`android/engine-pins.json`), 2026-09-11, four bundles x cpu/gpu: round 1
  the plain `--benchmark` control runs, round 2 the profiled runs (p128 /
  d256, `--max_num_tokens=1024`, thermal-gated, alternating backends):
  `results/raw/2026-09-11-catalog-x13-s26-android/profiles/` - the driver
  (`prof_drive.sh`), the logs, and a `max_num_tokens` sweep under
  `context-sweep/`.
- **The parsers**, in the same directory:
  - `prof_table.py <dir> <tag>...` - one row per model x backend: wall ms/step
    from the *control* run, profiled op-sum per recorded decode step grouped
    into weight GEMV / attention+KV / transfer / other, the unprofiled
    remainder, launches per step.
  - `prof_cmp.py <dir> <tag>` - cpu vs gpu per node type, prefill vs decode
    split by times-called.
  - `graph_slices.py <bundle.litertlm>` - static walk of the bundle's graphs:
    slice / dynamic-update-slice / gather / concat ops and the bytes of their
    largest input per decode step (needs the `ai_edge_litert` wheel).

## Two facts that shape the design

1. **Profiling changes the number.** On the S26 the profiled run decoded well
   below its control on the GPU (26.0 vs 59.8 tok/s Qwen3-0.6B mixed_int4,
   13.3 vs 27.0 Gemma 4 E2B, 10.4 vs 20.7 Qwen2.5-1.5B q8) and between 24%
   below and 2% above on the CPU. The profiled run's rate is never a benchmark
   row; the wall-time budget the ops are compared against comes from the
   control run.
2. **The CPU profiler buffer drops events.** Three of the four CPU runs log one
   `Dropping ProfileBuffer event` (Qwen2.5-1.5B q8: none); 131-256 of the 256
   decode steps were recorded (Qwen3-0.6B 225, its wi4b32 build 218, Gemma 4
   E2B 131, Qwen2.5 q8 256). Op sums are normalized per *recorded* step
   (`prof_table.py` reads the step count off the rows).

## Design: `./bench profile <cells> --platform android --campaign NAME`

- Input: a cells file; only `litert-lm` cells with a `native-benchmark-<P>x<D>`
  task are eligible (the `litert_lm_advanced_main` path, the binary the flag
  belongs to). Other cells are listed in `SKIPPED.txt` with the reason.
- Per cell, one **pair**: the control run - a normal capture whose record lands
  in `app-path-android/` as a speed row - then the profiled twin with
  `--enable_profiling`, whose log and record go to
  `<campaign>/profiles/<slug>.prof.log` and `.prof.json`. The profiled record
  carries `conditions.profiling=true` and `provenance.controlRecord=<id>`, and
  lives outside `app-path*/`, so `build_summary.py` never counts it as speed.
  Thermal gate, cooldown and the device lock as in `matrix`.
- After the pairs: `scripts/profile/prof_table.py` over `profiles/` writes
  `profiles/PROFILE.md` and `profile-table.csv`; `prof_cmp.py` runs for every
  model that has both backends. `graph_slices.py` runs on the host against the
  bundle in the Hugging Face cache and appends the static op counts.
- Exit 0 = every pair has a control and a profile; 1 = a pair is incomplete (a
  profile without its control is kept on disk and marked, never summarized).
- `--max-num-tokens A,B,C` repeats the pair per context size (the 09-11 sweep:
  384 / 1024 / 4096 / 32771). Above 8192 on a phone the subcommand refuses
  unless `--allow-large-context`: the 32771 GPU run rebooted the S26.
- Code moves, no new grammar: the three parsers to `scripts/profile/` with a
  test over the stored 09-11 logs; `run_cell.py` gains a `--enable-profiling`
  flag and the `profiles/` output path; `bench` gains the subcommand.

## Coverage

| device / route | state |
|---|---|
| Galaxy S26, v0.16.0, cpu and gpu | captured by hand 2026-09-11 (the four bundles above) |
| Pixel 8a | not tried; same binary, same path |
| Mac | not tried. The harness's Mac path is the yardstick over the C API, which at v0.17.0 has benchmark getters (TTFT, init time, per-turn tokens/sec) but no profiling setter and no profile-summary getter. Two routes: (a) a native macOS bazel build of `litert_lm_advanced_main` (upstream's "Deploy to MacOS" section of build-and-run.md builds the plain binary with `bazel build //runtime/engine:litert_lm_main`; the advanced target is defined beside it in `runtime/engine/BUILD`) - CLI parity with Android; (b) an upstream C API addition, `litert_lm_engine_settings_enable_profiling` + `litert_lm_benchmark_info_get_profile_summary` - `BenchmarkInfo` already carries the summary and the executor already has `StartProfiling`, so the yardstick and the iPhone app would get it through the existing benchmark path. I can send (b) as a PR if it is wanted |
| iPhone | route (b) only - no CLI on the device |

## What the parser surfaces (example, one phone)

S26, v0.16.0, Qwen3-0.6B mixed_int4, p128 / d256, `max_num_tokens=1024`:
the CPU decode step is 32.1 ms wall; the profiled ops sum to 35.4 ms per
recorded step (above the wall: the profiler's own cost sits inside the op
times), 26.7 ms of it in attention+KV nodes, 2316 launches per step. The
GPU decode step is 16.7 ms wall; profiled kernels sum to 9.9 ms (7.5 weight
GEMV, 0.6 attention+KV, 856 launches), 6.8 ms outside the profiled kernels.
The context sweep on the same phone (one bundle, four sizes, one run each)
showed the CPU decode step growing with `max_num_tokens` while the GPU step
did not. These are observations from one device and one version - inputs to a
re-test, not properties of the runtime.

## Next, in order

1. Parsers to `scripts/profile/` with the stored-log test.
2. `./bench profile` for Android (the pair, the record fields, the tables).
3. The Pixel 8a pair set, then the Mac route decision.
4. System profiling (Kimish's third point): nothing in the repo yet. Candidates
   on the hosts we have: Android `simpleperf` (ships in the NDK), Instruments
   on macOS (`xcrun xctrace list templates` lists `Metal System Trace` on
   Xcode 27). A skill follows once a capture has been run and read.

Runtime: [LiteRT](https://github.com/google-ai-edge/litert);
engine: [LiteRT-LM](https://github.com/google-ai-edge/LiteRT-LM).
