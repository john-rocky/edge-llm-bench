# ddp-bench — the Route B instrumentation-test APK (LiteRT-LM via the Maven AAR)

One Android instrumentation test that downloads a `.litertlm` from the Hugging Face Hub, runs the
8-question correctness gate, measures the repo's `short-chat` task N times through the official
`litertlm-android` Kotlin API, and writes one `schema/result.v1.json` record per run where adb or the
Developer Device Platform (DDP) can pull it. Design, DDP submission runbook and what is still
unverified: `docs/ddp-integration.md`.

Everything the native Android lane discloses (`methodology/android.md`) is disclosed here the same
way, in the record: the AAR is the engine (`engineVersion: litertlm-android:<v>`, `engineArtifact`
= the resolved AAR's sha256, both generated at build time from the classpath, never typed), the
prompt and budget are copied from `prompts/text/` at build time, the sampler is the engine default
for the speed runs and greedy for the gate, and memory is the instrumentation process's VmRSS.

## Build (host Mac: JDK 17, Android SDK; Gradle/AGP/Kotlin download themselves)

```bash
cd android/ddp-bench
JAVA_HOME=/Library/Java/JavaVirtualMachines/temurin-17.jdk/Contents/Home \
  ./gradlew --no-daemon :app:assembleDebug :app:assembleDebugAndroidTest
# app/build/outputs/apk/debug/app-debug.apk                      (the "app": no Activity, INTERNET only)
# app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk (the test)
```

`-PlitertlmVersion=0.16.1` builds against another AAR; the consumer Kotlin floor follows the AAR's
metadata version (0.17.0 needs Kotlin 2.4, pinned in `build.gradle.kts`).

## Run on a local phone

```bash
android/ddp-bench/run_local.sh                       # download gemma-3-270m-it q8 on the phone, gate, 3 runs
android/ddp-bench/run_local.sh --model ~/models/x.litertlm --backend gpu --runs 3 --cooldown 120
```

The script refuses to start on a phone another driver holds, installs both APKs, runs
`am instrument` with the same argument names DDP gets, pulls the records into
`results/raw/<campaign>/app-path-android/` beside `logcat-process.txt` (the device log scoped to the test process, where the native LiteRT-LM lines are) and
`am_instrument.txt`, and checks each record against the accumulation layer's loader.

## Instrumentation arguments (`-e key value` locally, `--additional-test-options=key=value` on DDP)

| key | default | meaning |
|---|---|---|
| `hf_repo` / `hf_file` / `hf_revision` | `litert-community/gemma-3-270m-it` / `gemma3-270m-it-q8.litertlm` / `main` | what to download; the record stamps the commit the Hub served (`model.hfRevision`) and the file's sha256 |
| `hf_token` | — | gated repos; sent to huggingface.co only, never to the CDN, never in the APK |
| `model_path` | — | skip the download, use a file already on the device (world-readable, e.g. `/data/local/tmp/...`) |
| `backend` | `cpu` | `cpu` or `gpu`; arm identity (`runtime: litert-lm-<backend>`) |
| `task` | `short-chat` | or `native-benchmark-<P>x<D>` (the Kotlin `benchmark()`: fixed prefill/decode token counts) |
| `runs` / `cooldown_s` | `3` / `60` | fresh `Engine` per run; seconds between runs |
| `max_output_tokens` | task budget (`prompts/text/budgets.tsv`) | `ConversationConfig.maxOutputToken`; the record carries the real generated count |
| `gate` | `true` | run the 8-question gate first (`prompts/correctness-gate-8.jsonl`); the bar follows the size class: sub-1B = form ok on every answer + ≥3/8 correct, 1B+ (or size unknown) = ≥6/8 correct |
| `model_params` | parsed from the repo/file name (`270m`, `0.6B`, `E2B`…) | override when the name does not state the size; picks the gate's size class |
| `campaign` | `ddp-apk` | output subdirectory + `provenance.campaign` |
| `context_tokens` | bundle default | `EngineConfig.maxNumTokens` |

## Output on the device

`/sdcard/Android/data/io.github.johnrocky.edgellmbench/files/edge-llm-bench/<campaign>/app-path-android/`
— `litert-lm-<backend>_<repo>_<task>_<stamp>_run<i>.json` + `.log` per run, `gate_*.json` once. The
test FAILS (JUnit) when the gate fails or a run has no decode rate; the records stay (failed-runs-stay).
