# Galaxy S26 (SM-S942Q): the Google AI Edge Gallery app's benchmark beside the LiteRT-LM benchmark binary — plan, 2026-10-11

Question: on one phone, in one sitting, what does the Gallery app's Benchmark screen read for the two bundles of the
2026-10-10 line-ups (Gemma 4 E2B on GPU, Gemma 3 1B int4 on CPU) at prefill 1,024 / decode 256, and what does the
public `litert_lm_advanced_main` read for the same files at the same token counts in cold and cached processes?

## The two sides

| side | build | what one "cold" number is | what one "cached" number is | max tokens |
|---|---|---|---|---|
| Gallery 1.0.20 (`com.google.ai.edge.gallery`, litertlm-android 0.18.0) Benchmark screen | release APK `ai-edge-gallery-sm8850.apk` of 2026-10-06 | run 1 of a session: a new engine in a fresh app process, an empty per-session cache dir (`BenchmarkViewModel.kt`: `cacheDir/benchmark_<ts>`), `benchmark(prefillTokens, decodeTokens)` | runs 2..N of the same session: a new engine in the same process, the cache files run 1 wrote | not set by the app; `EngineSettings::CreateDefault` (`kotlin/.../jni/litertlm.cc` `nativeCreateBenchmark`); read from the engine's log |
| `litert_lm_advanced_main`, `gs://litert/binaries/latest/android_arm64/litert_lm/` (object dated 2026-09-18, sha256 `adac974b…2d06`) | the binary of the 2026-10-07/09 pool sessions and of `2026-10-10-s26-reboot-cold` | a process started with no cache files next to the model | a new process with the cache files the previous one wrote | `--max_num_tokens=4096` |

Both sides: `--benchmark_prefill_tokens=1024 --benchmark_decode_tokens=256` / prefill 1,024, decode 256; one cycle
per engine (`--num_iterations=1` / one `benchmark()` call per run); the same bundle bytes (sha256 read back on the
phone): `gemma-4-E2B-it.litertlm` 2,588,147,712 bytes `18193810…a63c` (the Gallery allowlist's commit
6e5c4f1e… is this file), `gemma3-1b-it-int4.litertlm` 584,417,280 bytes `1325ae36…98be` (allowlist commit
42d538a9…). The Gallery's own allowlist caps Gemma3-1B-IT at max tokens 1,024, which disables the screen's run
button at 1,024 + 256; the app reads an override list from `/data/local/tmp/model_allowlist_test.json` first
(`ModelManagerViewModel.kt`), so the 1.0.20 list with that one value set to 4,096 is placed there for the sitting and
removed afterwards (`tools/model_allowlist_test.json`; the diff against the published 1_0_20.json is that one line).
The model files are placed where the app's downloader writes them (`<external files>/<normalized name>/<commit>/<file>`)
instead of being downloaded over Wi-Fi; the app checks only the file's presence (`checkIfModelDownloaded`).

## Sequence (one hold on the phone, screen on for the app, nothing else running on it)

1. `tools/gallery_bench.py prepare`: APK 1.0.18 → 1.0.20 (`adb install -r -g`, settings kept), model files, override list.
2. Gallery sessions, each = app start → Models → the model's menu → Benchmark → accelerator, 1024 / 256 / 3 runs →
   Continue; the app is force-stopped between sessions: E2B GPU ×2, E2B CPU ×1, G3 CPU ×2, G3 GPU ×1. One Perfetto
   trace during the first E2B GPU session and the first G3 CPU session.
3. `tools/binary_runs.sh`: the bucket binary, same files, same token counts: E2B gpu cold / cached ×2 each, G3 cpu
   cold / cached ×2 each, 30 s between processes; Perfetto traces of one cold and one cached process per bundle.
4. `tools/gallery_bench.py cleanup` (override list and the placed model files removed; the APK stays at 1.0.20),
   `binary_runs.sh cleanup`; then the #3577 leg (`../2026-10-11-s26-3577-v0180/`); hold released.

Values from the Gallery come from its results viewer (two decimals, at the avg / min / max aggregations; with three
runs the middle value is 3·avg − min − max) and from the engine's log lines in logcat where it prints them; values from
the binary come from its stdout lines (`Prefill Speed`, `Decode Speed`, `Time To First Token`, `Init Total`,
`Peak private footprint`) and `metrics-<tag>.pb`. A 1-second sampler (`<tag>.sample.csv`: CPU policy 0 / 6 current and
max clock, GPU clock and busy %, thermal zones gpuss-0, cpu-0-0-0, cpu-1-0-0, battery, sys-therm-0) runs beside every
binary process; the Perfetto traces (`../2026-10-11-s26-perfetto/`) hold the same for the app sessions.
Not rows of `results/summary`; not added to any leaderboard data.
