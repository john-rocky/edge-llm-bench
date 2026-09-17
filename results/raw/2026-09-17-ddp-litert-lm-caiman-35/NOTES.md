# 2026-09-17 — LiteRT-LM `litert_lm_advanced_main --benchmark` on `caiman-35` (Pixel 9 Pro) through Device Run, CPU and GPU, two runs each

Session `session-944b220b`, project `litert-edge-portal`, location `global`, created by
`POST https://devicerun.googleapis.com/v1alpha/projects/litert-edge-portal/locations/global/sessions`
with `request.json` as the body. Submitted 2026-09-17 15:10:38 JST by the Mac's clock (run log; the operation's
`createTime` is 06:10:39.88Z = 15:10:39.9 JST) and its `endTime` is 228 s later; the 30-second poll reported "not
done" eight times and saw `done: true` on its ninth call (15:14:51 JST); result **PASSED**, every run's exit code 0.
Session 06:10:42–06:14:16 UTC (214 s); job 06:10:44–06:14:15 (211 s, the leading 56 s before the execution hold the
pushes); execution 06:11:40–06:14:12 (152 s = 4 s before the first run's first log line + 130 s of runs and cooldowns,
of which the four binary invocations took 38.6 s and the three cooldowns 30 s each + 18 s of logcat and pull). Console:
https://console.cloud.google.com/storage/browser/litert-edge-portal-devicerun/automation/sessions/session-944b220b/
Commands and observed output: `standup/drafts/2026-09-17-litert-lm-on-ddp.run-log.txt`.

## What ran

- Job action `androidNativeBinary` = `litert_lm_harness.sh` (this directory; the shape of litert-samples
  `benchmark/multi_benchmark_harness.sh`, the DDP team's example: one binary invocation per entry in `--runs`, stdout
  kept per run), args
  `--runs=cpu,gpu,cpu,gpu --dir=/data/local/tmp --model=gemma3-270m-it-q8.litertlm --output_dir=/data/local/tmp/output
  --prefill_tokens=128 --decode_tokens=256 --max_num_tokens=1024 --cooldown=30`, `executionTimeout` 1200 s.
  Device actions: push the binary, the seven `.so` files and the model into `/data/local/tmp/`, pull
  `/data/local/tmp/output`, logcat. The wrapper's own stdout (its `Executing:` lines) is not stored on this path, as
  in the 09-15 run: the per-run command line below is the wrapper plus the args above, corroborated by the flag dump
  each run prints at start (`max_tokens: 1024`, `number_of_threads: 4`, `is_benchmark: true`) and by the protos.
- Binary: **this repo's own build** of `litert_lm_advanced_main` at LiteRT-LM tag v0.17.0, taken from this repo's
  GitHub release `john-rocky/edge-llm-bench` `android-litert-lm-v0.17.0` (archive sha256 `155edb1c…`); the upstream
  LiteRT-LM v0.17.0 release carries no Android binary (two xcframeworks and a macOS CLI). The wrapper hashes the
  files on the device (`provenance.txt`): `litert_lm_advanced_main` `3e87acfb…`, the `.so` set and the model all equal
  to `android/engine-pins.json` `litert-lm.v0.17.0` and the Hub's LFS sha256 (`757e9119…`).
- Per run: `LD_LIBRARY_PATH=/data/local/tmp ./litert_lm_advanced_main --backend=<cpu|gpu>
  --model_path=/data/local/tmp/gemma3-270m-it-q8.litertlm --benchmark --benchmark_prefill_tokens=128
  --benchmark_decode_tokens=256 --max_num_tokens=1024 --async=false
  --wait_for_weights_conversion_complete_in_benchmark=true --metric_proto_file_path=<output>/metrics_<run>.pb`
  (the repo's `native-benchmark-128x256` shape, `run_cell.py`; no `taskset`, engine-default 4 threads).
- Model: `litert-community/gemma-3-270m-it` `gemma3-270m-it-q8.litertlm` (304,005,120 B, Hub revision `9d209327…`).
- Device `caiman-35`: Pixel 9 Pro, build `google/caiman/caiman:15/BP1A.250505.005/13277524:user/release-keys`
  (Android 15, kernel 6.1.99), `Thermal Status: 0` before and after every run. GPU path = OpenCL
  (`Loaded OpenCL library with dlopen`, `Created OpenCL device`; `Weights preparation on Gpu is disabled for … Mali
  GPUs`, so the first GPU run converts the weights on the CPU during init).

## Numbers (stdout `BenchmarkInfo`; `metrics_<run>.pb` decodes to the same values)

| run | prefill tok/s (128) | decode tok/s (256) | TTFT s | Init Total s |
|---|---|---|---|---|
| cpu, run 1 | 344.32 | 48.89 | 0.39 | 0.66 |
| cpu, run 2 | 386.51 | 48.07 | 0.35 | 0.67 |
| gpu, run 1 | 517.55 | 26.96 | 0.28 | 7.01 |
| gpu, run 2 | 542.15 | 35.36 | 0.26 | 1.15 |

Each run is a fresh process; run 2 of the GPU found the cache the first run wrote (`Initialized InferenceContext from
serialized data`), which is where its init time went. Prefill, decode and TTFT are timed after init. One session on one
phone; a single sitting, not a standing.

**The GPU rows are throughput only, not a usable-speed row.** `--benchmark` never looks at the generated text, and this
q8 bundle's GPU output is empty: the model card (read 2026-09-17) says "Gemma3 270M via LiteRT-LM with GPU acceleration
is WIP and will be coming soon"; on the Galaxy S26 the native GPU path emitted only `<pad>` tokens with v0.16.0
(`results/raw/2026-09-10-ddp-apk-sm-s942q-gpu2-android/NOTES.md`), and the same check with v0.17.0 `litert_lm_main
--backend=gpu` on 2026-09-17 15:19 (one prompt, "What is the capital of France?") returned no text and decoded 4,075
tokens without an end-of-turn, where the CPU path answered "Paris" in 3 tokens (`s26-text-check/s26-text-{gpu,cpu}.log`).
This is upstream issue google-ai-edge/LiteRT-LM#3280 (open since 2026-08-18: every 270M bundle, both GPU stacks, CPU
fine; recipes and runtime versions ruled out there). No runtime flag changes it either: `--force_f32=true`,
`--sampler_backend=cpu` and both together still run to 4,075 tokens with no text on the S26 with v0.17.0
(`s26-text-check/s26-gpu-*.log`, 2026-09-17 15:31–15:36). Whether the Pixel 9 Pro's GPU output is the same is not
visible from benchmark mode; a GPU-published bundle is what a GPU speed row needs.

Decode the protos with LiteRT-LM v0.17.0's `runtime/proto/litert_lm_metrics.proto` (+ `engine.proto`):
`protoc --proto_path=<litert-lm checkout> --decode=litert.lm.proto.LitertLmMetricsList runtime/proto/litert_lm_metrics.proto < metrics_cpu.pb`.

## Files

- `request.json` — the body as sent; `operation-create.json` — the POST response; `operation.json` — the finished
  operation (embeds the whole `Session`); `session.json` — the session resource after completion.
- `litert_lm_harness.sh` — the wrapper as pushed (gs://…/automation/inputs/2026-09-17_litert-lm/); `run_session.sh` —
  the submit / poll / pull / decode driver used for this session.
- `ddp-session/session-944b220b/litert-lm-pixel-9-pro/execution-a7408d24-…/artifacts/data/local/tmp/output/` — the
  pulled directory as the wrapper wrote it: `cpu.log`, `gpu.log`, `cpu_2.log`, `gpu_2.log` (each run's stdout+stderr),
  `*.exit`, `metrics_*.pb`, `*_logcat.txt` (per-run `logcat -d`), `provenance.txt`; `logcat.txt` beside it is the
  whole-device log from the session.
- `rehearsal-pixel8a/`, `rehearsal-pixel8a-flat/`, `rehearsal-pixel8a-v2/` — the same wrapper run over adb on the local
  Pixel 8a before the session (three dry runs while the script took shape); reference only, a different phone.

## Not a leaderboard row

No `app-path-android/` and no `result.v1` record: `scripts/build_summary.py` ignores this directory. Cross-runtime or
cross-device comparison is out of scope for this directory (one runtime, one device, one sitting).
