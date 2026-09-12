# Operator profiling as a `bench` subcommand — `./bench profile` (v1, 2026-09-12)

Goal: a run can carry LiteRT-LM's per-op profile next to its speed record, so
an agent that measured a bundle can also see where the decode step goes -
without the profile ever changing the speed number. The command below ran
end to end on the Pixel 8a today (one size per cell); the sweep flag is
implemented but has not been driven through `./bench profile` yet - the
09-11 sizes came from the hand scripts stored with those captures.

## What runs today

```
./bench profile <cells> [--campaign NAME] [--max-num-tokens A,B,C] [--allow-large-context]
```

- **Input.** A cells file; eligible cells are `android litert-lm ...
  native-benchmark-<P>x<D>` (the `litert_lm_advanced_main` path - the binary
  `--enable_profiling` belongs to; `runtime/engine/shared_flags.cc` in
  [LiteRT-LM](https://github.com/google-ai-edge/LiteRT-LM), "Enable per-op
  profiling.", present at v0.16.0 and v0.17.0). Other Android cells go to
  `profiles/SKIPPED.txt` with the reason; lines for other platforms are
  ignored, as in `matrix`. Example: `matrices/profile-example-android.cells`.
- **Per cell, one pair.** The control: one normal `run_cell.py` capture
  (thermal gate, cooldown, capture gate) whose record lands in
  `<campaign>/app-path-android/` as an ordinary speed row; a control that
  turns out to be the engine's cache-building run (`firstEver`) is repeated
  once, since its wall time divides the whole table. Then the profiled twin:
  the same on-device command plus `--enable_profiling`. The twin's console
  log, a copy of the control's log and its record go to `<campaign>/profiles/`
  as `<tag>_<backend>_prof.log`, `<tag>_<backend>_ctrl.log`, `<tag>_<backend>.prof.json`
  (`conditions.profiling=true`, `provenance.controlRecord`); the tag is
  model + bundle file + PxD + context, and an existing pair is never
  overwritten. They live outside `app-path*/`, so `build_summary.py` never
  counts the profiled rate as speed. The one-driver-per-device lock is the
  campaign runner's (`android/bench/run_profile.py` imports `run_cell.py`
  rather than changing it).
- **Then the table.** `scripts/profile/profile_report.py` writes
  `profiles/PROFILE.md` and `profile-table.csv`: per (model, backend) the
  wall ms per decode step from the *control*, the profiled op time per
  recorded decode step grouped into weight GEMV / attention+KV / transfer /
  other, the part of the wall the profiled ops do not cover, launches per
  step, one factual reading per row, and a cpu-vs-gpu node-type comparison
  for every model that has both backends. The parsers `scripts/profile/prof_table.py`
  and `prof_cmp.py` are ports of the scripts stored with the 2026-09-11
  captures and reproduce that table row for row; `graph_slices.py` (a static
  walk of the bundle's graphs, needs the `ai_edge_litert` wheel) is a
  standalone tool.
- **Sweeps.** `--max-num-tokens 1024,4096` repeats the pair per context size,
  with the controls under `profiles/controls-ctx<N>/` so that rows differing
  only in context never pool in the summary (the 09-11 hand sweep: 384 / 1024
  / 4096 / 32771). Above 8192 on a phone the command refuses unless
  `--allow-large-context`: the 32771-token GPU run rebooted the S26.
- **Exit codes.** 0 = every pair complete; 1 = a pair lacks its control or a
  usable profile (the failed twin's log stays on disk, `profiles/FAILURES.txt`
  names it, and the table skips it); 2 = bad cells file, no eligible cell, or
  a refused context size; 3 = another driver holds the device.

## Two facts that shape it

1. **Profiling changes the number.** On the S26 (v0.16.0) the profiled run
   decoded well below its control on the GPU (26.0 vs 59.8 tok/s Qwen3-0.6B
   mixed_int4, 13.3 vs 27.0 Gemma 4 E2B, 10.4 vs 20.7 Qwen2.5-1.5B q8) and
   between 24% below and 2% above on the CPU. So the profiled run's rate is
   never a benchmark row; the wall-time budget the ops are compared against
   comes from the control run.
2. **The CPU profiler buffer drops events.** Three of the four S26 CPU runs
   log one `Dropping ProfileBuffer event` (Qwen2.5-1.5B q8: none); 131-256 of
   the 256 decode steps were recorded (Qwen3-0.6B 225, its wi4b32 build 218,
   Gemma 4 E2B 131, Qwen2.5 q8 256). Op sums are normalized per *recorded*
   step (`prof_table.py` reads the step count off the rows).

## Coverage

| device / route | state |
|---|---|
| Pixel 8a, v0.16.0 pinned binary, cpu and gpu | `./bench profile` end to end, 2026-09-12 (Qwen3-0.6B mixed_int4, 128x256, `max_num_tokens` 1024): `results/raw/2026-09-12-profile-smoke-android/profiles/` |
| Galaxy S26, v0.16.0, cpu and gpu | captured by hand 2026-09-11 with the same command shape (four bundles): `results/raw/2026-09-11-catalog-x13-s26-android/profiles/`; `profile_report.py` runs over that directory as is |
| Mac | not tried. The harness's Mac path is the yardstick over the C API, which at v0.17.0 has benchmark getters (TTFT, init time, per-turn tokens/sec) but no profiling setter and no profile-summary getter. Two routes: (a) a native macOS bazel build of `litert_lm_advanced_main` (upstream's "Deploy to MacOS" section of build-and-run.md builds the plain binary with `bazel build //runtime/engine:litert_lm_main`; the advanced target is defined beside it in `runtime/engine/BUILD`) - CLI parity with Android; (b) an upstream C API addition, `litert_lm_engine_settings_enable_profiling` + `litert_lm_benchmark_info_get_profile_summary` - `BenchmarkInfo` already carries the summary and the executor already has `StartProfiling`, so the yardstick and the iPhone app would get it through the existing benchmark path. I can send (b) as a PR if it is wanted |
| iPhone | route (b) only - no CLI on the device |

## What the table surfaces (example, one phone)

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

1. The Pixel 8a pair set for the rest of the dashboard models, then the Mac
   route decision (a or b above).
2. A fake-adb selftest for `run_profile.py` beside `android/bench/selftest.py`.
3. System profiling: nothing in the repo yet. Candidates on the hosts we
   have: Android `simpleperf` (ships in the NDK), Instruments on macOS
   (`xcrun xctrace list templates` lists `Metal System Trace` on Xcode 27).
   A skill follows once a capture has been run and read.

Runtime: [LiteRT](https://github.com/google-ai-edge/litert);
engine: [LiteRT-LM](https://github.com/google-ai-edge/LiteRT-LM).
