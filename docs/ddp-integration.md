# Evaluating HF LiteRT models on the Developer Device Platform (DDP)

*Written 2026-09-09 against the DDP docs dated 2026-09-03 (Preview). Nothing here has run on DDP yet; every claim about the platform is from its documentation, and every claim about this harness is from the code in this repo.*

**Goal (as asked by the LiteRT team):** evaluate the `.litertlm` files published under `litert-community` automatically on real devices, publish the numbers, and link each number back to the DDP run that produced it.

## What DDP offers, as documented

| surface | what it is | what it means for this harness |
|---|---|---|
| Device Catalog | 213 device rows (`gcloud beta device-run devices list`): Pixel 8a `akita-34/35`, Pixel 9 `tokay-34/35/36`, Pixel 10 Pro `blazer-36`, Pixel 11 `cubs-37`, Galaxy S24 `e1q-34/36`, S25 `pa1q-36`, S26 `m1q-36`, foldables, tablets | the same phones this repo already measures (Pixel 8a, Galaxy S26) exist there, so rows are comparable with the local ones |
| Device Run | batch: `gcloud beta device-run sessions submit instrumentation --device <ids> --apps app.apk --test test.apk`; multiple devices per session, uniform / smart sharding, `--async`; results land in `gs://<project>/automation/sessions/<session-id>/` with a Cloud Console URL | the CLI (`sessions submit instrumentation`) takes an **Android instrumentation-test APK only** — the native `litert_lm_main` / `litert_lm_advanced_main` binaries this harness pushes over adb cannot be submitted through it as-is. The API contract bundled with the SDK (`devicerun_v1alpha_messages.py`) also defines `androidNativeBinary` and `iosXcTest` job actions; no gcloud command drives them yet (checked 2026-09-10) |
| Device Streaming | interactive ADB to a remote physical device; the open-source agent skill `developer-device-platform-basics` reserves, extends and forwards adb from a Python venv | this harness's Android lane runs unchanged over it (`BENCH_ANDROID_SERIAL` → the forwarded device) |
| Platform | Preview, Android only (iOS "coming soon"); billed to the Google Cloud project; APIs `devicerun`, `devicestreaming`, `testing` | iPhone rows stay local for now; someone's project pays per device-minute |

## Two routes

**Route A — Device Streaming + the existing harness (first numbers in days).**
`android/bench/run_cell.py` already does everything except the device reservation: it pushes the model and the pinned `litert_lm_advanced_main` (`android/engine-pins.json`), runs `--benchmark` on `--backend cpu|gpu`, parses prefill / decode / TTFT / init / peak RSS into `schema/result.v1.json`, and records the raw log. Over Streaming the only change is the serial. Limits: one interactive session per device, extended by hand (the skill exposes "extend by 30 minutes"), no sharding, no batch API — a way to validate that the numbers match the local ones, not the way to run 100 repos nightly.

**Route B — Device Run with a benchmark test APK (the durable one).**
One instrumentation-test APK, `litertlm-bench-test`, parameterized by instrumentation args `(hf_repo, file, backend, runtime_version, prompt_set)`:

1. downloads the `.litertlm` from the Hub onto the device (HF token for gated repos passed as a test arg, never baked in);
2. creates the LiteRT-LM engine through the Kotlin API on the requested backend and runs the same measurement this harness makes natively — prefill and decode tok/s at a fixed prompt length, TTFT, init time, peak RSS — plus the 8-question correctness gate (a model that generates garbage at 40 tok/s must fail, not rank);
3. writes one `result.v1.json` per cell into the test's output directory, which Device Run collects into the session bucket.

An outer job (GitHub Actions on a schedule, or Cloud Run) then: lists the org's repos and their `.litertlm` files; submits one session per (device set × repo), with the session name carrying the repo id; waits; pulls the JSON from the bucket; and writes the rows into each card the way the card lines in this repo's sibling tooling already do — device · runtime version · backend · number · date — with the DDP session's console URL closing the line as the citation ("link back to DDP"). Org-owned cards can be committed directly by the org; anyone else's get a Hub PR.

Device set to start with (one per tier): Pixel 8a (`akita-35`, 8 GB, Mali), Pixel 10 Pro (`blazer-36`), Galaxy S26 (`m1q-36`, Adreno). Re-run policy: every `litert-lm` release (this repo's `release-watch` already detects them) and every new file on a repo.

**Route C — the HTTP API with a native binary** (the DDP team's own example, 2026-09-11): the session REST resource with an `androidNativeBinary` job action and push/pull device actions — the route the team asked us to try first. Run on 2026-09-13, CPU and GPU; the section before "Next step".

## What already exists in this repo for Route B

- `schema/result.v1.json` — the record shape; `scripts/build_summary.py` / `render_leaderboard.py` consume it.
- `android/bench/parsers.py` — parsing of the native benchmark output; the APK's Kotlin measurement should emit the same fields so the parsers and the summary layer stay shared.
- `android/engine-pins.json` — the version-pin discipline: the APK bundles one `litertlm-android` version per build and reports it in every record.
- `methodology/android.md` — what is and is not comparable across runs (no warm regime on Android, TTFT caveats).

## Open questions (for whoever owns the GCP project)

- **Cost attribution.** The web docs describe a bucket path and a Console link per session; the CLI itself (`gcloud beta device-run sessions submit instrumentation --help`, SDK 579.0.0, read 2026-09-10) exposes `--labels=[KEY=VALUE,...]` "user-defined key-value labels to attach to the session". So a per-session label exists at the API level; whether it reaches the billing export is still unverified. The fallback stays the naming convention (`campaign=<repo>--<file>--<device>` in the test options) plus the bucket path.
- **Which project pays.** The APK and the job are project-agnostic; a first session on a personal project costs a few device-minutes and shows the real result shape.
- **Correctness beyond the gate.** GSM8K-class parity runs are minutes per model on a phone; they fit Device Run's sharding, but the budget decides whether they are nightly or per-release.

## Route C with LiteRT-LM: `litert_lm_advanced_main --benchmark` through a wrapper script (2026-09-17)

Run once on `caiman-35` (Pixel 9 Pro), `session-944b220b`, PASSED; everything is in
`results/raw/2026-09-17-ddp-litert-lm-caiman-35/` (`NOTES.md`, `request.json`, `litert_lm_harness.sh`,
`run_session.sh`, the pulled `output/` directory). The shape:

- **Binary.** LiteRT-LM's releases ship no Android binary, so the session pushes this repo's own build of
  `litert_lm_advanced_main` at the v0.17.0 tag plus the seven GPU `.so` files (GitHub release
  `android-litert-lm-v0.17.0`, hashes in `android/engine-pins.json`) from our bucket. The wrapper hashes them on the
  device into `provenance.txt`, so the row's witness is on-device, as in the adb lane. When a prebuilt lands next to the
  LiteRT binaries in `gs://litert/binaries/…`, only the nine `gcsInputFile` paths change.
- **Wrapper.** The job's `androidNativeBinary` is `litert_lm_harness.sh` (`#!/system/bin/sh`, the DDP team's
  `multi_benchmark_harness.sh` shape): one binary invocation per entry in `--runs=cpu,gpu,cpu,gpu`, each run's stdout to
  `output/<run>.log`, its exit code to `<run>.exit`, `--metric_proto_file_path=output/metrics_<run>.pb`
  (`litert.lm.proto.LitertLmMetricsList`, decode with `runtime/proto/litert_lm_metrics.proto` + `engine.proto` from
  the tag), a per-run `logcat -d`, and a 30 s cooldown between runs. The pushed binary arrives without the execute bit
  (the wrapper `chmod 755`s it). The wrapper always exits 0 so the pull step runs; the per-run exit codes are in the
  files. Flags it does not know are passed to the binary unchanged.
- **Session body.** `session-cpu-gpu-wrapper.json`'s layout: files pushed flat into `/data/local/tmp/`,
  `androidPullFiles` on `/data/local/tmp/output`, `androidLogcat`, `executionTimeout` raised to 1200 s (the default is
  5 min; range 1–60 min per the API reference), `labels` on the job (accepted, echoed back in the report). The session
  took 214 s end to end, the execution 152 s.
- **What comes back.** The same `BenchmarkInfo` block `run_cell.py` parses (`Prefill Speed`, `Decode Speed`, `Time to
  first token`, `Init Phases`), once per run, plus the proto with the same values. On the Pixel 9 Pro the first GPU run
  spent 7.0 s in init converting the weights (Mali: `Weights preparation on Gpu is disabled`) and the second run 1.2 s
  (it found the serialized cache); prefill and decode are timed after init.
- **What it does not check.** `--benchmark` never reads the generated text. The `gemma-3-270m-it` q8 bundle's GPU output
  is empty on the Galaxy S26 with v0.16.0 and v0.17.0 (card: "GPU acceleration is WIP"; upstream LiteRT-LM#3280, and
  `--force_f32` / `--sampler_backend=cpu` do not change it), so its GPU rows are the path's throughput, not a usable
  speed — the correctness gate that the APK route runs has no counterpart on this path yet.
  Not a leaderboard row: no `result.v1` record is written from this directory.

## Route B prototype: `android/ddp-bench` (built 2026-09-10)

**Status.** The APK pair builds on the Mac against `litertlm-android` 0.17.0 (AGP 8.7.3, Kotlin 2.4.0, Gradle 8.14.4 — the combination the sibling `litertlm-release-gate` harness already proved on this AAR). Local pass-through: **done twice, Galaxy S26, 2026-09-10** (below). DDP: **one session run, `session-cc6509d5` on `m1q-36` (Galaxy S26), PASSED, 2026-09-10 11:05–11:11 JST** — the same APK pair, the same arguments; its rows are filed in `results/raw/2026-09-10-ddp-m1q-36/` and compared with the local unit at the end of this section. The Device Run API was enabled on `litert-edge-portal` the same morning (it had been `SERVICE_DISABLED`).

**What the test does** (`android/ddp-bench/app/src/androidTest/.../LitertlmBenchTest.kt`, one JUnit test, `am instrument` arguments in `android/ddp-bench/README.md`):

1. **Model.** Downloads `<hf_repo>/<hf_file>` at `<hf_revision>` onto the device (token to huggingface.co only; redirects followed by hand so the CDN never sees it) and sha256s it; the record stamps `model.hfRevision` with the commit the Hub served (`X-Repo-Commit`), `model.sha256`, and `model.sourceUrl`. `model_path` skips the download (adb push / `--other-files-to-push`).
2. **Gate.** `prompts/correctness-gate-8.jsonl` (beside the project): eight trivially easy questions — capital of France, 2+3, sky color, days in a week, opposite of hot, our planet, "thank you" in Spanish, 10 vs 100 — each in a fresh conversation, greedy sampling (`topK=1, topP=1.0, temperature=0.0`), 32-token cap. Every answer is scored for *form* (non-empty, no leaked control token such as `<start_of_turn>`, has a letter or digit, no token repeated 3+ times in a row, no repetition loop) and for *correctness* (regex). **The bar follows the model's size class** (owner decision 2026-09-10, after the first run below): sub-1B models pass when form is ok on every answer and at least 3/8 are correct — a coherence bar, because a 270M-class model legitimately misses arithmetic and facts; 1B-and-up (or a size the name does not state and `model_params` does not give) keep the original knowledge bar, 6/8 correct. The class is parsed from the repo/file name (`270m`, `0.6B`, `E2B`, `1.5B`) and recorded in the gate JSON with the rule applied. Fails → the JUnit test fails → the DDP job is red; the records are still written. The gate's engine is also what builds the on-disk engine caches, so no speed run is a cache build (the native lane's `firstEver` marker scheme is reused: a marker file after the first clean exit).
3. **Speed.** `runs` × (fresh `Engine` → `initialize()` → one `Conversation` with the task budget → `sendMessage(prompt)` → `getBenchmarkInfo()`), `ExperimentalFlags.enableBenchmark = true`. The prompt and the budget are the repo's `prompts/text/short-chat.txt` / `budgets.tsv`, copied into the test assets at build time (never retyped). Sampler: engine default, exactly like the native `litert_lm_main` row (which has no sampler flags). `task=native-benchmark-<P>x<D>` uses the Kotlin `benchmark()` instead (fixed token counts).
4. **Record.** One `schema/result.v1.json` per run + its raw log (BenchmarkInfo, reply text, RSS series, thermal before/after) under `/sdcard/Android/data/io.github.johnrocky.edgellmbench/files/edge-llm-bench/<campaign>/app-path-android/`, plus `gate_*.json`. Metrics use the native lane's names (`decodeTokensPerSecond`, `promptTokensPerSecond`, `firstTokenLatencyMS`, `promptTokenCount`, `generatedTokenCount`, `memoryMedianResidentMB`) plus `engineInitMS`, `decodeTokensPerSecondWallClock` (generated ÷ (generate wall − TTFT)) and `memoryPeakResidentMB` (VmHWM). `runtime` is `litert-lm-<backend>` (the arm), `engineVersion` is `litertlm-android:<v>`, `engineArtifact` the resolved AAR's sha256 — both generated at build time from the classpath (`engine-pin.json` asset), the witness rather than the request. `harnessStamp: 2026-09-android-ddp-apk-v1`. A record whose embedded gate verdict is FAIL is quarantined at pull time as `<name>.json.gate-fail` — on disk as audit trail, outside the summary's `*.json` glob — so a fast engine with empty output can never rank (the GPU sitting below is the case that made this a rule).

**Disclosed differences from the native Android lane** (all in `conditions` of every record):

| | native `run_cell.py` | this APK |
|---|---|---|
| engine | bazel-built `litert_lm_main` at a tag | the Maven AAR (`engineArtifact` = AAR sha256) |
| process | fresh process per run | fresh `Engine` per run inside one instrumentation process (`engineLifecycle`) |
| CPU affinity | `taskset f0` (Pixel 8a) / none (S26) | none — an app cannot taskset itself (`cpuAffinity`) |
| memory | driver samples the engine process's VmRSS | the instrumentation process's own VmRSS (engine + ART + test framework; `memoryBasis`) |
| output cap | `--max_output_tokens` ignored by v0.16.0 (441+ tokens) | `ConversationConfig.maxOutputToken` (honoured or not, the record carries `generatedTokenCount`) |
| thermal / battery | `dumpsys` over adb | `PowerManager.currentThermalStatus` (same 0–6 scale, same names) / `ACTION_BATTERY_CHANGED` |

Rows from the two harnesses therefore share `runtime`, `model`, `task` and the metric names, and differ in `harness_stamp` and `engine_version` — compare them as two instruments on one phone, never pool them.

### Local pass-through (one adb device)

```bash
android/ddp-bench/run_local.sh                    # gemma-3-270m-it q8 from the Hub, gate, 3 runs, 60 s cooldown
android/ddp-bench/run_local.sh --backend gpu      # same, GPU backend
android/ddp-bench/run_local.sh --model ~/models/x.litertlm --repo some/repo --file x.litertlm
```

The script: refuses a phone another driver holds; builds; installs both APKs; runs `am instrument -w -r` with the same argument names DDP gets; pulls the records into `results/raw/<date>-ddp-apk-<device>-android/app-path-android/` beside `logcat-process.txt` (the device log scoped to the test process — the native LiteRT-LM lines live there) and `am_instrument.txt`; checks every record with the accumulation layer's own loader (`platform_of == android`, required keys). Exit 0 = test passed and records pulled; 1 = the test failed (gate or a run) — the records and logs are still pulled; 2 = no device / held device / build failure. Then `python3 scripts/build_summary.py` folds the rows into `results/summary/device-runs.csv` (`platform=android`, `harness_stamp=2026-09-android-ddp-apk-v1`).

#### First pass-through: Galaxy S26, 2026-09-10 08:56–08:59 JST (`results/raw/2026-09-10-ddp-apk-sm-s942q-android/`)

The whole chain ran once, unattended, in 2 min 20 s: the phone downloaded the 304 MB `gemma3-270m-it-q8.litertlm` from the Hub in 11 s (Hub commit `9d209327…` stamped into `model.hfRevision`), the gate ran, three speed runs wrote three records, the runner pulled them and the loader accepted them. The transcript, trimmed:

```
[ddp-bench] device=SM-S942Q (RFGL80R6A6H) campaign=2026-09-10-ddp-apk-sm-s942q-android backend=cpu runs=3
[ddp-bench] am instrument ... (08:56:29)
INSTRUMENTATION_STATUS: ... test=measure
...
java.lang.AssertionError: correctness gate FAIL: 5/8 (threshold 6) - the model does not rank. gate=FAIL runs_ok=3/3 decode_tok_s=50.62,47.82,50.11 out=/storage/emulated/0/Android/data/io.github.johnrocky.edgellmbench/files/edge-llm-bench/...
FAILURES!!!
Tests run: 1,  Failures: 1
INSTRUMENTATION_CODE: -1
[ddp-bench] records: 4 under results/raw/2026-09-10-ddp-apk-sm-s942q-android/app-path-android/
[device] GATE FAIL 5/8 (threshold 6)
[device] run 1/3 OK decode=50.62 tok/s prefill=377.451963339978 ttft_ms=72.74169025 gen=44 thermal=nominal->nominal firstEver=false
[device] run 2/3 OK decode=47.82 tok/s prefill=300.3959128011946 ttft_ms=87.49173975000001 gen=44 thermal=nominal->nominal firstEver=false
[device] run 3/3 OK decode=50.11 tok/s prefill=333.9571820472567 ttft_ms=79.84466875 gen=44 thermal=nominal->nominal firstEver=false
[device] SUMMARY gate=FAIL runs_ok=3/3 decode_tok_s=50.62,47.82,50.11 out=...
  litert-lm-cpu_litert-community_gemma-3-270m-it_short-chat_2026-09-09T23-56-47.540_run1.json: decode=50.62... prefill=377.45... ttft_ms=72.74 gen=44 rss_mb=702 gate=FAIL firstEver=None
  litert-lm-cpu_litert-community_gemma-3-270m-it_short-chat_2026-09-09T23-57-48.725_run2.json: decode=47.81... prefill=300.39... ttft_ms=87.49 gen=44 rss_mb=703 gate=FAIL firstEver=None
  litert-lm-cpu_litert-community_gemma-3-270m-it_short-chat_2026-09-09T23-58-50.045_run3.json: decode=50.10... prefill=333.95... ttft_ms=79.84 gen=44 rss_mb=703 gate=FAIL firstEver=None
[ddp-bench] 3 record(s) pass the result.v1 shape check (platform=android)
```

Speed rows (CPU, engine-default sampler, 20-token prompt, 128-token cap, thermal 0→0, USB power, no other driver on the phone):

| run | decode tok/s | prefill tok/s | TTFT ms | generated | engine init ms | resident median MB |
|---|---|---|---|---|---|---|
| 1 | 50.62 | 377.5 | 72.7 | 44 | 420 | 702 |
| 2 | 47.82 | 300.4 | 87.5 | 44 | 557 | 703 |
| 3 | 50.11 | 334.0 | 79.8 | 44 | 578 | 703 |

The model stopped at its own EOS at 44 tokens each time and the three replies are byte-identical (deterministic per engine default, as on the native lane). No run was a cache build (`firstEver` absent — the gate's engine ran first). Memory is the instrumentation process (engine + ART runtime); the native lane's number for the same model would be the engine process alone.

**Gate: FAIL 5/8, and the three misses are the model's, not the APK's.** Greedy, 32-token cap: capital→"Paris" ✓, 2+3→"2" ✗, sky→"Blue" ✓, days in a week→"1" ✗, opposite of hot→"Cold" ✓, our planet→"Mars" ✗, thank-you in Spanish→"Gracias." ✓, 10 vs 100→"100" ✓. The JUnit test failed by design and every record still carries `quality.gate` (these three records were later quarantined as `*.json.gate-fail` under the rule adopted the same day; the gate2 re-run below carries the same numbers under the size-class bar). Cross-check (`mac-cli-crosscheck.txt` in the campaign dir): the official `litert-lm` CLI 0.17.0 on the Mac, same artifact (sha256 verified), same greedy settings, returns exactly the same eight strings. So (a) the APK's conversation path reproduces the reference implementation on a different platform, and (b) the 6/8 threshold — fixed before any model ran — conflated *knowledge* (an addition, a count, a fact) with what the gate exists for, *garbage detection*. The threshold was not touched after seeing this.

**Owner decision needed before the DDP session:**

1. *Keep the gate as is.* gemma-3-270m-it q8 stays red; the DDP smoke session would use a canary that passes (none has been tried yet), or run with `gate=false` for the pipe test only.
2. *Redefine the gate as the coherence check it was meant to be* (recommended): keep the eight questions and the greedy setting, score every answer for *form* (non-empty, one short line, no leaked template/control tokens, not a single token repeated) and for *correctness*, and FAIL when form fails on any question or correctness falls below a floor a broken bundle cannot reach (e.g. 3/8). On this evidence the 270M model would pass (8/8 form, 5/8 correct), and a tokenizer/template/quantization failure — empty output, `<start_of_turn>` echoes, token loops — would still fail. That is a change of definition, made once, not a per-model tune.

### Submitting the same APK to DDP (owner runs these; the project pays per device-minute)

Flags are from `gcloud beta device-run sessions submit instrumentation --help` (SDK 579.0.0, beta 2026.07.31); steps 1–4 ran for real on 2026-09-10 (transcripts inline), the rest is filled in from the first session's result below.

1. **Enable the API** (once per project; the project is billing-enabled — `gcloud billing projects describe` says so):
   ```bash
   gcloud services enable devicerun.googleapis.com --project litert-edge-portal
   # Operation "operations/acat.p2-..." finished successfully.   (2026-09-10; devices list worked right after)
   ```
2. **Find the device ids** (free, read-only):
   ```bash
   gcloud beta device-run devices list --project litert-edge-portal --format=json | head -60   # learn the field names once
   gcloud beta device-run devices list --project litert-edge-portal --format=json \
     | python3 -c "import sys,json; [print(d.get('name'), d.get('displayName')) for d in json.load(sys.stdin) if any(k in json.dumps(d) for k in ('akita','m1q','blazer'))]"
   ```
   Expected: rows whose ids match the catalog names in the table at the top (`akita-35` = Pixel 8a, `m1q-36` = Galaxy S26, `blazer-36` = Pixel 10 Pro). The catalog names every device under `projects/<p>/locations/global/devices/<id>` (265 rows on 2026-09-10; Pixel 8a `akita-34`/`akita-35`, Galaxy S26 `m1q-36`, Pixel 10 Pro `blazer-36`, Pixel 11 `cubs-37`), so `--location global` is the value.
3. **Build** the two APKs (README) — or reuse the ones the local pass-through used, so the DDP row and the local row come from one binary (`engineArtifact` will prove it).
4. **Submit one session** on one device, the same arguments as the local run:
   ```bash
   CAMPAIGN=$(date +%F)-ddp-m1q-36
   gcloud beta device-run sessions submit instrumentation \
     --project litert-edge-portal --location global \
     --device m1q-36 \
     --apps  android/ddp-bench/app/build/outputs/apk/debug/app-debug.apk \
     --test  android/ddp-bench/app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk \
     --instrumentation-timeout 30m \
     --additional-test-options backend=cpu,runs=3,cooldown_s=60,campaign=$CAMPAIGN,hf_token=$(cat ~/.cache/huggingface/token) \
     --paths-to-pull /sdcard/Android/data/io.github.johnrocky.edgellmbench/files/edge-llm-bench \
     --labels harness=edge-llm-bench,repo=litert-community--gemma-3-270m-it,device=m1q-36 \
     --async
   ```
   - `--instrumentation-timeout` defaults to **5 m**; the cap is **3 h** in gcloud ≥ 580.0.0 (raised 2026-08-11 per the SDK release notes — the 579.0.0 CLI these sessions ran from still printed `1m` to `1h`, and the first Chat note to the DDP team quoted that stale 1 h; corrected there the same day). A 300 MB download + gate + 3 runs with 60 s cooldowns needs ~10 min on a 270M model, so 30 m.
   - `hf_token` in the test options is stored with the session's inputs (`gs://<bucket>/automation/inputs/...`). The alternative that keeps the token off the platform is `--other-files-to-push=<local .litertlm>=/data/local/tmp/edge-llm-bench/gemma3-270m-it-q8.litertlm` plus `model_path=/data/local/tmp/edge-llm-bench/gemma3-270m-it-q8.litertlm` in the options — **whether the pushed file is readable by the app on a DDP device is unverified** (locally the runner chmods it 644 in a 755 dir, which works).
   - Local APK paths are uploaded to the bucket by the CLI (`gs://litert-edge-portal-devicerun` is created if `--bucket-name` is absent).
   - Observed 2026-09-10 (first real submission; both APKs were local paths, uploaded by the CLI):
     ```
     Using the default GCS bucket [gs://litert-edge-portal-devicerun] for input and result files. Will create the bucket if it does not exist.
     Uploading [android/ddp-bench/app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk].
     Uploading [android/ddp-bench/app/build/outputs/apk/debug/app-debug.apk].
     Initiated long-running operation [operation-1789005921494-...] to create session.
     Creating session [session-cc6509d5] in location [global].
     Result files will be stored at [https://console.cloud.google.com/storage/browser/litert-edge-portal-devicerun/automation/sessions/session-cc6509d5/].
     ```
     `describe` then prints `Session [session-cc6509d5] status is [RUNNING].` (not JSON, even with `--format=json`).
5. **Wait and read the verdict**:
   ```bash
   gcloud beta device-run sessions list     --project litert-edge-portal --location global
   gcloud beta device-run sessions describe <session-id> --project litert-edge-portal --location global
   ```
   Observed: `describe` prints `Session [session-cc6509d5] status is [RUNNING].` / `Job status: 1 running` while it runs (about 6 min for this APK: upload, allocation, an 87 s model download on the lab's network, a 213 s test, artifact collection), then
   ```
   Session [session-cc6509d5] finished with result [PASSED].
   Result files are stored at [https://console.cloud.google.com/storage/browser/litert-edge-portal-devicerun/automation/sessions/session-cc6509d5/].
   JOB NAME  EXECUTION NAME  EXECUTION RESULT
   job-000   execution-000   PASSED
   ```
   PASSED = the JUnit test's own assertions held (gate passed, every run produced a decode rate); a FAIL still leaves the records in the bucket.
6. **Pull the records** into a campaign dir, exactly where the local runner puts them (as run on 2026-09-10):
   ```bash
   C=results/raw/$CAMPAIGN; mkdir -p $C/ddp-session $C/app-path-android
   gsutil -m -q cp -r gs://litert-edge-portal-devicerun/automation/sessions/<session-id>/ $C/ddp-session/
   mv "$(find $C/ddp-session -type d -name app-path-android)"/* $C/app-path-android/ && rm -r $C/ddp-session/*/job-000/execution-000/artifacts   # one copy: the summary globs every app-path*/
   # the lab logcat is 3+ MB of the whole device: keep the test process's lines only
   L=$(find $C/ddp-session -name logcat.txt); PID=$(grep -m1 EDGE_LLM_BENCH "$L" | awk '{print $3}')
   awk -v p="$PID" '$3==p' "$L" > $C/app-path-android/logcat-process.txt && rm "$L"
   python3 scripts/build_summary.py
   grep "$CAMPAIGN" results/summary/device-runs.csv
   ```
   Observed layout: `sessions/<id>/job-000/junit.xml`, `job-000/execution-000/{junit.xml,instrument.log,logcat.txt}` and the pulled directory under `execution-000/artifacts/sdcard/Android/data/io.github.johnrocky.edgellmbench/files/edge-llm-bench/<campaign>/app-path-android/` with the same file names the test wrote. The lab's logcat clock is US Pacific.
7. **Compare with the local row** — same APK, same arguments, a different physical unit in a different room. Observed 2026-09-10 (CPU, gemma-3-270m-it q8, 20-token prompt, 44 generated tokens every run, thermal 0→0 on both):

   | | local `SM-S942Q` (JP unit, patch 2026-06-05), 11:02 JST | DDP `m1q-36` = `SM-S942U1` (US unit, patch 2026-01-01), 11:08 JST |
   |---|---|---|
   | gate | PASS, form 8/8, correct 5/8, same 8 answers | PASS, form 8/8, correct 5/8, same 8 answers |
   | decode tok/s (3 runs) | 50.55 / 48.52 / 48.06 | 48.37 / 48.07 / 48.41 |
   | prefill tok/s | 340 / 303 / 279 | 346 / 308 / 295 |
   | TTFT ms | 79 / 87 / 92 | 79 / 86 / 89 |
   | engine init ms | 447 / 671 / 613 | 564 / 549 / 570 |
   | resident median MB | 698–700 | 702–703 |
   | model download | already on the device (11 s the first time, Wi-Fi) | 87 s, lab network |

   Same shape, same verdict; read it as two units, never as a delta (devices drift 16–25 % between sittings; `CLAUDE.md`). The session's Console URL is the DDP row's citation (in the campaign's `NOTES.md`).

   **GPU backend (local S26 only, 2026-09-10 11:40–11:46):** the first attempt failed at the first message with "Can not find OpenCL library on this device" — Android 12+ hides vendor libraries from an app unless the manifest declares them (`<uses-native-library android:name="libOpenCL.so" …>`; fixed, three names, `required=false`). With the fix the GPU backend runs: 1537/1537 decode nodes on the OpenCL delegate, decode 66.5 / 67.0 / 66.7 tok/s, TTFT 44 ms — **and every answer was empty**, 128 tokens to the cap. The gate failed it (form 0/8: "empty"), the records are quarantined, and the cross-check settles whose fault it is: the native `litert_lm_main` v0.16.0 on the same phone and file, `--backend=gpu`, also emits only `<pad>` tokens (4076 of them at 41.9 tok/s), and the model card says "Gemma3 270M via LiteRT-LM with GPU acceleration is WIP". The q8 bundle is CPU-only; the APK's GPU path is not the problem. Records: `results/raw/2026-09-10-ddp-apk-sm-s942q-gpu-android/` and `…-gpu2-android/` (with `native-gpu-crosscheck/`).

**Settled by the first session (2026-09-10):** the lab device has outbound internet (Hub download with the token in the test options), `--paths-to-pull` on the app's external files dir works and keeps the file names, `--location` is `global`, `--labels` is accepted, local APK paths are uploaded by the CLI. **Still unverified:** a GPU row on DDP with a bundle its card publishes for GPU (locally the GPU backend runs; this 270M q8 bundle is CPU-only by its own card and produced empty output on both engines), whether `--labels` reaches the billing export, and what one session costs (billing data was not yet visible the same day). The HF token travelled in `--additional-test-options`; it appears in no pulled file (checked before committing) but is visible in the session's metadata to anyone with project access — rotate it if that matters, or use `--other-files-to-push` + `model_path` (untested on DDP).

## Route C — the HTTP API with the public native benchmark binary (run 2026-09-13, CPU and GPU)

*Charlie Xu's example on the Collaborations Doc (tab "DDP Integration", added 2026-09-11): one REST session whose job runs Google's public LiteRT `benchmark_model` binary on a lab phone, with the model pushed from our own bucket and the two result files pulled back. No `gcloud device-run` command is involved — the CLI only mints the access token, so its version does not matter here. The [LiteRT-LM](https://github.com/google-ai-edge/LiteRT-LM) native binary is not on this path yet (Charlie, 2026-09-10: "NPU and LiteRT-LM requires more work"), so the model is a `.tflite`.*

**Inputs — both in GCS before the request.** The binary is the one the Doc's footnote describes as the open-sourced Android benchmark binary of the LiteRT benchmark page (https://developers.google.com/edge/litert/next/benchmark#download-prebuilt): `gs://litert/binaries/2.2.0/android_arm64/benchmark_model`, 8,020,656 bytes, created 2026-09-10 21:14 UTC, readable without credentials (an unauthenticated `HEAD` over `storage.googleapis.com` answers 200); the same directory holds `run_model`, the two numerics checkers, and the accelerator and compiler-plugin `.so` files. The page's own download links resolve to `gs://litert/binaries/latest/android_arm64/benchmark_model`, a different object (8,053,552 bytes, created 2026-08-12), so `2.2.0` is a release-pinned copy and `latest` is not an alias of it — for a row that must be reproducible, the pinned path is the one to cite. The model is `mobilenet_v2.tflite` from `litert-community/MobileNet-v2` (Hub commit `a847f8dd`, 14,079,072 bytes, sha256 `9e3d5575…b09e6dd`), copied into the project's existing Device Run bucket:

```bash
gsutil ls -L gs://litert/binaries/2.2.0/android_arm64/benchmark_model
curl -sL -o mobilenet_v2.tflite https://huggingface.co/litert-community/MobileNet-v2/resolve/a847f8dd803c5471b44e57fed3be772c0d382214/mobilenet_v2.tflite
shasum -a 256 mobilenet_v2.tflite
gsutil cp mobilenet_v2.tflite gs://litert-edge-portal-devicerun/automation/inputs/2026-09-13_http-route/mobilenet_v2.tflite
```

**The arguments, checked on the same tool before any device-minute.** The example's five flags ran on the Mac with the `macos_arm64` build of the same 2.2.0 binary and the same model:

```bash
curl -sL -o benchmark_model_mac https://storage.googleapis.com/litert/binaries/2.2.0/macos_arm64/benchmark_model && chmod +x benchmark_model_mac
./benchmark_model_mac --graph=mobilenet_v2.tflite --num_threads=4 --export_model_runtime_info=true --model_runtime_info_output_file=runtime_info.pb --result_file_path=results.pb
protoc --proto_path=android/ddp-bench/http --decode=tflite.tools.benchmark.BenchmarkResult benchmark_result.proto < results.pb
```

Observed (2026-09-13; a flag check, not a measurement — its numbers are not comparable with the phone's below): it completes in about 1.5 s of wall time and writes both files. First line after `STARTING!`: `WARN: Unconsumed cmdline flags: --export_model_runtime_info=true` — the CompiledModel benchmark writes the runtime info whenever `--model_runtime_info_output_file` is set ([`litert/tools/benchmark_litert_model.cc`](https://github.com/google-ai-edge/litert/blob/main/litert/tools/benchmark_litert_model.cc) in the LiteRT repo), and the `export_model_runtime_info` switch belongs to the Interpreter-API benchmark (`tflite/tools/benchmark/benchmark_tflite_model.cc`); harmless, the file is written either way. Then the `BENCHMARK RESULTS` block on stdout (init, warm-up, inference avg/min/max/std, throughput, init and overall footprint), `runtime_info.pb` (119,070 bytes) and `results.pb` (79 bytes). `results.pb` is a `tflite.tools.benchmark.BenchmarkResult` (`android/ddp-bench/http/benchmark_result.proto`, copied from the LiteRT repo): `latency_metrics` in ms (avg, min, max, stddev, median, p5, p95, init, first inference, average warm-up), `memory_metrics` (init and overall footprint in kB, plus a peak in MB that neither run could read), `misc_metrics` (model size MB, run counts, throughput MB/s). So the numbers exist twice, on stdout and in `results.pb`, and the example pulls only the file.

**The request body** — `android/ddp-bench/http/session-benchmark_model.json`, the Doc's JSON with our bucket, our file name, and four labels added (labels do not affect execution and come back in the job report). The device is the example's `pa3q-35` (catalog entry read the same day, kept as `device-pa3q-35.json` in the campaign directory: Galaxy S25 Ultra, Samsung, OS version 35, availability HIGH, capacity HIGH). `executionTimeout` is left at its default of 5 min (range 1–60 min per the API reference).

```json
{
  "sessionConfig": {
    "displayName": "benchmark-model-test",
    "outputDirectoryConfig": {
      "gcsOutputDirectory": {
        "path": "gs://litert-edge-portal-devicerun/automation/sessions"
      }
    },
    "jobConfigs": [
      {
        "displayName": "run-benchmark",
        "action": {
          "androidNativeBinary": {
            "androidNativeBinary": {
              "gcsInputFile": {
                "path": "gs://litert/binaries/2.2.0/android_arm64/benchmark_model"
              }
            },
            "args": [
              "--graph=/data/local/tmp/mobilenet_v2.tflite",
              "--num_threads=4",
              "--export_model_runtime_info=true",
              "--model_runtime_info_output_file=/data/local/tmp/runtime_info.pb",
              "--result_file_path=/data/local/tmp/results.pb"
            ]
          }
        },
        "allocationConfig": {
          "deviceConfigs": [
            {
              "requirement": {
                "deviceId": "pa3q-35"
              },
              "actions": [
                {
                  "androidPushFiles": {
                    "fileConfigs": [
                      {
                        "sourceFile": {
                          "gcsInputFile": {
                            "path": "gs://litert-edge-portal-devicerun/automation/inputs/2026-09-13_http-route/mobilenet_v2.tflite"
                          }
                        },
                        "destinationPath": "/data/local/tmp/mobilenet_v2.tflite"
                      }
                    ]
                  }
                },
                {
                  "androidPullFiles": {
                    "paths": [
                      "/data/local/tmp/runtime_info.pb",
                      "/data/local/tmp/results.pb"
                    ]
                  }
                },
                {
                  "androidLogcat": {}
                }
              ]
            }
          ]
        },
        "labels": {
          "harness": "edge-llm-bench",
          "route": "http-native-binary",
          "model": "litert-community--MobileNet-v2",
          "device": "pa3q-35"
        }
      }
    ]
  }
}
```

**Submit, wait, pull** (REST only; the owner runs these — the project pays per device-minute):

```bash
TOKEN=$(gcloud auth print-access-token)
C=results/raw/2026-09-13-ddp-http-pa3q-35; mkdir -p $C
curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d @android/ddp-bench/http/session-benchmark_model.json https://devicerun.googleapis.com/v1alpha/projects/litert-edge-portal/locations/global/sessions | tee $C/operation-create.json
```

Before the request, the same token was used for two read-only calls — `GET …/sessions` (returned `session-cc6509d5`, PASSED) and `GET …/devices/pa3q-35` — so the endpoint, the token's scope and the JSON path were exercised before any session existed. The `POST` answered in about a second (2026-09-13 15:40:19 JST) with the long-running Operation the reference describes; the session id is in `metadata.target`:

```json
{
  "name": "projects/litert-edge-portal/locations/global/operations/operation-1789281619081-65b57974efa2a-a16bbf5b-9536940f",
  "metadata": {
    "@type": "type.googleapis.com/google.cloud.devicerun.v1alpha.OperationMetadata",
    "createTime": "2026-09-13T06:40:19.306520906Z",
    "target": "projects/litert-edge-portal/locations/global/sessions/session-e1d64576",
    "verb": "create",
    "requestedCancellation": false,
    "apiVersion": "v1alpha"
  },
  "done": false
}
```

```bash
OP=$(python3 -c 'import json; print(json.load(open("results/raw/2026-09-13-ddp-http-pa3q-35/operation-create.json"))["name"])')
until curl -s -H "Authorization: Bearer $TOKEN" https://devicerun.googleapis.com/v1alpha/$OP | tee $C/operation.json | grep -q '"done": true'; do sleep 30; done
S=$(python3 -c 'import json; print(json.load(open("results/raw/2026-09-13-ddp-http-pa3q-35/operation.json"))["metadata"]["target"].split("/")[-1])')
curl -s -H "Authorization: Bearer $TOKEN" https://devicerun.googleapis.com/v1alpha/projects/litert-edge-portal/locations/global/sessions/$S | tee $C/session.json | python3 -c 'import sys,json; r=json.load(sys.stdin)["sessionReport"]; print(r["result"], r["startTime"], r["endTime"]); [print(f["gcsOutputFile"]["path"]) for j in r["jobReports"] for e in j["executionReports"] for f in e["outputFiles"]]'
mkdir -p $C/ddp-session && gsutil -m -q cp -r gs://litert-edge-portal-devicerun/automation/sessions/$S/ $C/ddp-session/
find $C/ddp-session -type f | sort
protoc --proto_path=android/ddp-bench/http --decode=tflite.tools.benchmark.BenchmarkResult benchmark_result.proto < $(find $C/ddp-session -name results.pb)
```

**Observed (2026-09-13 15:40–15:42 JST; records in `results/raw/2026-09-13-ddp-http-pa3q-35/`).** The Operation's own `endTime` is 60 s after its `createTime` (06:40:19.3 → 06:41:18.9 UTC); the 30-second poll saw `done: true` on its third call, 85 s after the POST. The finished Operation carries the whole `Session` in `response` — the separate `GET …/sessions/$S` is a convenience, not a need. Session report: **PASSED**; session 06:40:22–06:41:04 UTC (42 s), its one execution 06:40:51–06:41:00 (9 s), and inside it the binary's own log lines span 1.5 s (logcat 23:40:52.889–23:40:54.401, the lab's US-Pacific clock). The allocated unit is the requested `pa3q-35`: Galaxy S25 Ultra on OS version 35 per the catalog entry, model code `SM-S938UZKAXAA` in the device log (`device-identity.txt` beside the process log). The bucket holds exactly three files: `run-benchmark/execution-<uuid>/logcat.txt`, and under `…/artifacts/data/local/tmp/` the pulled `results.pb` (80 bytes) and `runtime_info.pb` (119,070 bytes) — the job directory is named after the job's `displayName` and the execution after its id, where the instrumentation session had `job-000/execution-000`. **The binary's stdout is not stored**: no `instrument.log` counterpart, no `junit.xml`. The `BENCHMARK RESULTS` block is still readable, because this benchmark logs through the Android logger as well as stdout — the same lines sit in `logcat.txt` under the tags `tflite` and `litert` for the binary's pid (kept as `logcat-process.txt`, 41 lines; the 214 KB whole-device log was dropped after the two lines naming the model were copied out). Numbers (CPU, XNNPACK, 70/70 nodes delegated, 4 threads): init 7.65 ms, first inference 6.68 ms, warm-up avg 3.71 ms (135 runs), inference avg 2.92 ms (343 runs; min 2.76, max 4.73, std 0.22), throughput 196.78 MB/s, init footprint 30.43 MB, overall 39.11 MB — identical between the decoded `results.pb` (`results.pb.txt` beside it) and the logcat block. The unconsumed-flag warning reproduced on the phone (`W tflite : Unconsumed cmdline flags: --export_model_runtime_info=true`). One trap on our side, not the platform's: `gsutil cp -r` of the session prefix needs the destination directory to exist (the first pull failed with "Destination URL must name a directory, bucket, or bucket subdirectory"); the block above carries the `mkdir -p`. This campaign directory has no `app-path-android/` and no `result.v1` record, so the summary layer ignores it: it is a plumbing record, not a leaderboard row.

**GPU on the same route (second session, 16:43–16:45 JST; records in `results/raw/2026-09-13-ddp-http-pa3q-35-gpu/`).** The Doc heads its example "for CPU/GPU request" and the JSON itself has no GPU flag, so the GPU body is the CPU body with one argument added, `--use_gpu=true` (`android/ddp-bench/http/session-benchmark_model-gpu.json`; the display names and a `backend=gpu` label are the only other differences). Two read-only checks first: the `macos_arm64` build answers the flag with `[gpu_registry.cc:87] Statically linked GPU accelerator registered` and a Metal device, no dylib beside it; and the `android_arm64` binary pushed over adb to the local Galaxy S26 (probed free: empty lock file, no benchmark process on the phone, daytime) prints the same registration line, then `Loaded OpenCL library with dlopen` and `Replacing 70 out of 70 node(s) with delegate (LITERT_CL)` — so the public binary carries the GPU accelerator statically and the accelerator `.so` files in the bucket are not needed for it, nor is `LD_LIBRARY_PATH`. On DDP, `session-233c4731` on `pa3q-35`: **PASSED**; operation `endTime` 62 s after `createTime`, the poll's third call 66 s after the POST; session 07:44:03–07:44:43 UTC (40 s), its execution 8 s. The same three files came back (`logcat.txt` 203,728 bytes, `results.pb` 80, `runtime_info.pb` 119,383). The binary's logcat lines (pid 12740, kept as `logcat-process.txt`) show the same unconsumed-flag warning, `Statically linked GPU accelerator registered`, `Loaded OpenCL library with dlopen`, `Created OpenCL device from provided device id and platform id`, and 70/70 nodes on `LITERT_CL`. Numbers: init 515.86 ms, first inference 5.84 ms, warm-up avg 0.98 ms (509 runs), inference avg 0.95 ms (1053 runs; min 0.92, max 1.28, std 0.02), throughput 604.75 MB/s, footprint 94.57 MB init and overall (96,840 kB) — `results.pb.txt` and the logcat block agree. The CPU and GPU sessions are two separate sessions on the lab's `pa3q-35` pool, each a single run of the tool's own loop; they are the platform's behaviour on the two backends, not a standing.

**What this route settles.** The Doc's example runs as written from a project with the Device Run API enabled and one bucket; the only gcloud involvement is the access token, so an outer job can be a plain HTTP client with a service-account token — create, poll the operation, read the output paths from the session report, fetch them from GCS. The public binary is usable directly as `gcsInputFile` at a pinned version, no copy into our bucket. Labels round-trip into the job report. The pull action preserves device paths under `artifacts/`. GPU needs one flag and nothing pushed beside the binary. For a 14 MB model the operation is done about 60 s after the POST, and the files were on this Mac two minutes after it.

**What it does not.** Stdout: a binary that only prints its numbers — LiteRT-LM's `litert_lm_main --benchmark` prints its `BenchmarkInfo` to stdout, which is what this repo's Android lane captures (`android/bench/run_cell.py`) — would leave nothing behind on this path unless it writes to a file under a pulled path (or logs through the Android logger, which is what saved the block here). NPU: not tried (the compiler-plugin and dispatch `.so` files for Qualcomm and Google Tensor sit in the same public directory; the `androidNativeBinary` action has `envVars` for an `LD_LIBRARY_PATH` if a binary needs libraries beside it). The LiteRT-LM binary itself: not on this path yet. Cost: still not visible in billing on the day.

### Route C as a CLI target: `litert benchmark --ddp` (LiteRT-CLI #83, 2026-09-16; merged as #85 on 2026-09-17)

The HTTP route above is now wrapped as a `--ddp` target in LiteRT-CLI (https://github.com/google-ai-edge/LiteRT-CLI/pull/83, merged, reverted for the internal import and re-landed unchanged as https://github.com/google-ai-edge/LiteRT-CLI/pull/85 on 2026-09-17; `litert_cli/commands/benchmark/ddp.py`): one session per run with one `androidNativeBinary` job per device, the model pushed from `gs://<bucket>/litert-cli/inputs/`, outputs pulled to `~/.cache/litert-cli/ddp/<session>/<job>/`. Verified from `litert-edge-portal` on 2026-09-16 (record: `~/code/standup/drafts/2026-09-16-litert-cli-ddp-pr.run-log.txt`):

- **One session may carry several jobs**: `session-fff9643f` ran `cpu-caiman-35` and `cpu-pa3q-35` in parallel, both PASSED (the Doc examples were one job per session).
- **`androidPushFiles` creates a nested destination directory**: pushing to `/data/local/tmp/litert-cli/<model>` worked without a prior mkdir; the binary wrote `results.pb` and `runtime_info.pb` there and `androidPullFiles` returned them.
- **Session and job `displayName` must match `^[A-Za-z0-9][A-Za-z0-9-_ ]*$`, at most 63 bytes** (REST reference); job labels are free-form up to 16 entries and 1024-byte values.
- The default bucket `<project>-devicerun` is the name `gcloud beta device-run` prints as its default (2026-09-10 above); the CLI uses `litert-cli/inputs` and `litert-cli/sessions` prefixes in it.

**In the nightly package (checked 2026-09-19: the client path without a session first, then one real session; log `~/code/standup/drafts/2026-09-19-litert-cli-nightly-ddp.run-log.txt`):**

- Version: `litert-cli-nightly 0.3.0.dev20260918` (PyPI upload 2026-09-18 14:09 UTC, built by the repo's nightly workflow from main `6a175dcc`, which contains the #85 merge `def71221`); its `ddp.py` and `cli.py` are byte-identical to main, and the package's own `ddp_test.py` passes (37 tests). The previous nightly, `0.3.0.dev20260917`, was built from the #83 merge before the revert and already carried the target.
- Command: in a fresh venv (`uv venv --python=3.13 --seed .venv-nightly && source .venv-nightly/bin/activate && pip install litert-cli-nightly`), `litert benchmark --help` lists `--ddp`, `--device/--devices`, `--gcp-project`, `--gcp-bucket`, `--timeout` and the two DDP examples; then `DEVICE_RUN_ENDPOINT=https://devicerun.googleapis.com/v1nonexistent litert benchmark models/mobilenet/mobilenet_v2.tflite --ddp --device caiman-35 --gcp-project litert-edge-portal` (the model from `litert download litert-community/MobileNet-v2 --file mobilenet_v2.tflite --output models/mobilenet`, Hub commit `48e55de4`, 13,975,904 bytes — a newer file than the 09-13 one above) — the bogus API path makes the submit fail before any device is allocated, so the client path up to the submit runs without a device-minute (polling and result download did not run).
- Output: `Ensuring GCS bucket 'gs://litert-edge-portal-devicerun' exists for project 'litert-edge-portal'...` → `Uploading local model 'models/mobilenet/mobilenet_v2.tflite' to gs://litert-edge-portal-devicerun/litert-cli/inputs/litert-cli-benchmark-000fabc8/...` (the object landed, 13,975,904 bytes; removed afterwards) → `Fetching GCP access token...` → `Submitting 'cpu' benchmark session 'litert-cli-benchmark-000fabc8' to DDP (Project: litert-edge-portal, Devices: caiman-35, Binary: gs://litert/binaries/2.2.0/android_arm64/benchmark_model)...` → `Error: Failed to submit benchmark: 404 Not Found`, exit 1. The same command without the environment variable — the README's real run, one session on `caiman-35`, billed to the project — then ran once (owner decision, 06:09 JST): `session-ce215032`, job `cpu-caiman-35` PASSED, exit 0, the three output files (`logcat.txt`, `results.pb`, `runtime_info.pb`) pulled to `~/.cache/litert-cli/ddp/session-ce215032/cpu-caiman-35/` by 06:10:51 JST; the benchmark lines the CLI prints from the logcat: XNNPACK, 70/70 nodes delegated, init 8.24 ms, inference avg 10.02 ms (100 runs; min 9.34, max 10.61), footprint 30.52 / 38.37 MB — a plumbing record of the published package, not a leaderboard row.

## Route C as `bench matrix --ddp` (2026-10-15)

`./bench matrix <cells> --ddp <device id>` runs the Android LiteRT-LM rows of a cells file on a DDP lab phone through Route C: this repo's request body, a static wrapper script as the job's `androidNativeBinary`, and this repo's LiteRT-LM build at the pinned tag. No adb and no attached phone are involved; the host uploads, posts, polls and pulls. Code: `android/ddp/` — `run_ddp.py` (the driver), `ddp_cell.sh` (the wrapper), `record.py` (the records), `scrub.py` (logcat hygiene), `devices.json` (the id registry), `selftest.py` (the whole path against a fake gcloud and a fake Device Run server, no network; it needs the pinned engine files). Design and the build rounds: `results/raw/2026-10-15-ddp-backend-dev/` (`DESIGN.md`, `ROUND1.md`–`ROUND4.md`). The runbook is in `docs/OPERATIONS.md` ("Run cells on DDP").

**Command and options.**

```bash
./bench matrix matrices/dashboard-text-v1.cells --ddp akita-35 --dry-run    # the plan; no gcloud, no network
./bench matrix matrices/dashboard-text-v1.cells --ddp akita-35 \
    --campaign <name> --project <Cloud project> --bucket gs://<bucket>     # billed: uploads, sessions, records
```

- `--ddp <device id>`: a DDP catalog id listed in `android/ddp/devices.json` (`akita-34` / `akita-35` Pixel 8a, `m1q-36` Galaxy S26, `caiman-34` / `caiman-35` Pixel 9 Pro, `pa3q-35` / `pa3q-36` Galaxy S25 Ultra, `pa1q-36` Galaxy S25; run so far: `akita-35`, `m1q-36`). Its `scheduleKey` names the `ops/dashboard-v1/schedule.json` device whose `exclude-on=` rows and CPU mask apply (akita → `pixel8a`, mask `f0`; m1q → `s26`, no mask; `null` → no mask, and every row that carries an `exclude-on=` is skipped). Its `cpucapWaitSeconds` is the wrapper's CPU-cap wait before each run (absent: 300 s, the attached-phone route's `CPUCAP_WAIT`; `m1q-36`: 0).
- `--campaign <name>`: the campaign dir is `results/raw/<name>-android/` (default name `<date>-ddp-<id>`); a dir that already holds records is refused.
- `--dry-run`: every skipped row with its reason, every job (args, labels, pushes with bytes and sha256, timeouts, the estimate), every session's request body and the upload candidates as JSON lines, then one table; no subprocess, no network. A model that is not in the local Hugging Face cache is listed as `"uncached"`, with no sha256 yet.
- `--project` / `--bucket`: the Cloud project the sessions are created in, and the `gs://` bucket for the inputs and the session outputs. The defaults in `android/ddp/run_ddp.py` are this repo's own (`litert-edge-portal`, `gs://litert-edge-portal-devicerun`), so anyone else passes both.
- `BENCH_ANDROID_BIN_DIR` (default `android/bin`): the directory that holds `<tag>/` with the engine files; the attached-phone route reads the same variable.
- `--engine-build <label>`: every row runs the LiteRT-LM build of the `android/engine-pins.json` entry `litert-lm.<label>` instead of `android_pins`' tag (the key is the build's label, e.g. `main-<sha9>` or `pr<N>-<sha9>`). The engine files come from `$BENCH_ANDROID_BIN_DIR/<label>/`, each checked against that entry before anything is pushed, and go to the bucket as `engines/litert-lm/<label>/<sha256>/<name>`; the plan's `engineTag` and every job's `engine` label are the label; the records' witness matches the unit's sha256 against every entry, so `engineVersion` is the label. A label without an entry stops the plan, naming `android/scripts/pins_add.py`. `android/scripts/build_litert_lm_main.sh` with `LITERTLM_REF=<sha | branch | pr/N>` writes such a build and its entry; `pins_add.py` registers one built elsewhere (`android/README.md`, "Build from head or a PR"). `android_pins` is not changed. A row with its own `engine-build=` is still skipped (`side-build-not-wired-on-ddp`). The rows of a label never take a standing cell: when a cell holds version tags and labels, the leaderboard and the dashboard keep the newest version tag's session (`render_leaderboard.latest_session`), and the label's rows stay in `results/summary/`.
- Called by path, the driver takes more: `android/ddp/run_ddp.py <cells> --device <id> --campaign <name>-android [--jobs-per-session 1..8, default 8] [--job-timeout 60..10800 s, default 3600] [--resume <operation name>] [--poll-seconds 30]`, and `android/ddp/run_ddp.py --records-only results/raw/<campaign>` writes a campaign's records again from what its sessions pulled (no network). `--resume` polls that operation instead of POSTing its session, then submits the plan's later sessions as usual. `bench` runs `scripts/build_summary.py` and `scripts/render_leaderboard.py` after a billed run, as for every matrix.

**Rows, jobs, sessions.** `run_campaign.parse_cells`, android rows only (mac and ios rows print a skip line). A row is skipped, with its reason printed and in `app-path-android/SKIPPED.txt`, when its runtime is not `litert-lm` (`runtime-not-wired-on-ddp`: the llama.cpp rows need their own build pushed, which is not wired), when it is `exclude=` / `manual=`, when it is a side build (`backend=npu` or `engine-build=`: `side-build-not-wired-on-ddp`), when it is an anchor (`no-session-anchor-on-ddp`), or when its `exclude-on=` names the id's schedule key. One kept row is one job: `runs=` engine launches (default 3) on one lab unit. A session carries at most 8 jobs; sessions are submitted one after another. `matrices/dashboard-text-v1.cells` makes 8 jobs in 1 session on `akita-35` (22 rows skipped) and 16 jobs in 2 sessions on `m1q-36` (14 skipped): `results/raw/2026-10-15-ddp-backend-dev/dry-run/`.

**What is pushed.** Per job, `androidPushFiles` with 11 files (the API allows 50): the 9 engine files of the tag that `android/engine-pins.json` `android_pins` names (`litert_lm_main`, `litert_lm_advanced_main` and the 7 GPU `.so` files), each checked against that tag's pins entry before anything else (on a mismatch nothing is pushed); the model, as the Hugging Face Hub serves it (the host's HF cache blob, hashed on the host: huggingface_hub 1.8.0 names the blob by the file's LFS sha256, 2.2.0 by its xet hash when the Hub stores the file with Xet; a billed run downloads it if needed and checks its size against the Hub's and its sha256 against the Hub's LFS sha256); the task's prompt file (`prompts/text/<task>.txt`). The wrapper `android/ddp/ddp_cell.sh` is the job's binary. Every input is content-addressed in the bucket, `<bucket>/automation/inputs/edge-llm-bench/{engines/litert-lm/<tag>/<sha256>/<name>, models/<sha256>/<file>, prompts/<sha256>/<task>.txt, wrapper/<sha256>/ddp_cell.sh}`; a billed run uploads only the objects `gcloud storage ls` does not find, and the driver deletes nothing. On the unit the layout is the attached-phone route's: the engine files flat in `/data/local/tmp/llmbench/`, the model in `models/<org>_<repo>_<file>`, the prompt in `prompts/<task>.txt`. The job pulls one path, `/data/local/tmp/llmbench/ddp-out` (the API allows 10), and the unit's logcat (`androidLogcat`).

**What the wrapper does on the unit.** `ddp_cell.sh` (`#!/system/bin/sh`) runs the job's launches one after another. First it sets the execute bit on both tools (a pushed binary arrives without it) and writes `provenance.txt`: seven `getprop` values (model, device, build fingerprint, serial, Android version, security patch, SoC), `uname -a`, where `taskset` and `timeout` are, argc and every argv element, and the `sha256sum` of the engine files, the model and the prompt as they sit on the unit. Before each run: the cooldown (the row's `cooldown=`, else `COOLDOWN`, 120 s; none before run 1), the thermal gate (`Thermal Status: 0`, polled every 30 s for at most `THERMAL_WAIT`, 600 s; a timeout is recorded and the run starts), the CPU-cap wait (every cpufreq policy's `scaling_max_freq` back at its `cpuinfo_max_freq`, polled every 10 s for at most the id's `cpucapWaitSeconds`; a timeout is recorded as `cpu-capped-at-start`), the start state (`dumpsys battery`, `dumpsys thermalservice`, `mWakefulness`, `stay_on_while_plugged_in`) and `logcat -c`. The run is `run_cell.sampler_shell`, the string the attached-phone route's `run_once` sends over adb, built here from the job's args (`android/ddp/selftest.py` compares the two byte for byte for every planned job): the engine command of `run_cell.engine_command` behind the schedule key's `taskset` mask and `timeout -k 5 <s>`, sampling VmRSS / VmHWM / `Cpus_allowed_list` every 0.5 s and the CPU ceilings. After it: the exit code, the engine's output file, `logcat -d` and the end state. The per-run timeout is min(1800, (executionTimeout − cooldowns − 120) / runs) s. With `--budget` (executionTimeout − 120 s) the wrapper starts no run whose cooldown and timeout no longer fit in what is left (`run<i>.skipped` says so) and shortens a gate wait to what fits. The wrapper always exits 0, so the pull step runs. The platform splits a job argument at its spaces: the 13 args of a short-chat job arrived as 18 argv elements (`argc: 18` in the smoke session's `provenance.txt`), so `--command=` goes last and the wrapper joins every element after it with one space, which gives the same command whether the element arrives whole or split; the driver refuses a command or an env value with a character outside `[A-Za-z0-9_./=:,+-]` (and a space in the env value).

**What comes back.** `<campaign>/ddp/` holds, per session, `request-<n>.json`, `operation-create-<n>.json`, `operation-<n>.json` (rewritten at every poll, 30 s apart), `session-<n>.json` and `plan-<n>.json`, and the pulled `ddp/<session id>/<job displayName>/execution-<id>/`: the execution's `logcat.txt` and `artifacts/data/local/tmp/llmbench/ddp-out/` with `provenance.txt`, `wrapper.log` and, per run, `run<i>.state`, `run<i>.log` (the sampler's stdout: the samples, the engine's output, `EXIT_CODE=`), `run<i>.err`, `run<i>.exit`, `run<i>.engine.txt`, `run<i>_logcat.txt`. `android/ddp/record.py` writes one `schema/result.v1.json` record per run into `app-path-android/` (two per run for a 1K cell: iteration 1 cold, iteration 2 warm) with the attached-phone record's keys plus:

- `conditions.ddp`: session, job and execution ids, job and execution start and end times, the catalog id and schedule key, the unit's build fingerprint, serial and product, the job's executionTimeout, the execution's resultType, the run's index in the job;
- `device.ddp`: catalog id, build fingerprint, serial;
- `conditions.engineCache`, read from the run's raw log: `xnnpackWeightCache` is `built` (a `weight cache build for` line), `loaded` (`weight cache loaded from`) or `absent`; `gpuCache` is, on a GPU run, `loaded` (an `Initialized InferenceContext from serialized data` line) or `not-loaded` (no such line), and `absent` on a CPU run;
- `provenance.ddpSessionDir`, `provenance.wrapper`, `provenance.wrapperSha256`; `metrics.harnessStamp` `2026-08-android-cli-v1+ddp-route-c`.

A value the unit did not give stays null with its reason in `provenance.ddpMissing`. The witness is the sha256 the wrapper read on the unit, matched against `android/engine-pins.json` (the launched tool and every `.so`), as on the attached-phone route. Every job starts on a clean unit, so `firstEver` marks run 1 of every job (and any later run until the job's first clean exit); a later run that rebuilt a cache shows it in `conditions.engineCache`. Record ids and `conditions.launchID` are uuid5s of session / job / execution / run, so `--records-only` writes the same files again. `scripts/build_summary.py` names a DDP row's device `<ro.product.model> (DDP <id>)` (`Pixel 8a (DDP akita-35)`, `SM-S942U1 (DDP m1q-36)`), so `render_leaderboard.arm_row` never pools it with an attached phone's rows, and the local `DASHBOARD.md` (`./bench dashboard`) shows the DDP unit as a column of its own after the schedule's phones.

Hygiene: right after the pull, `android/ddp/scrub.py` replaces the lab network's identifiers in every pulled logcat (`run<i>_logcat.txt` and the execution's `logcat.txt`), by the rules at the top of that file: SSIDs, SSID / BSSID hashes, global, unique-local and link-local IPv6 addresses, six-pair MACs (Samsung's star-masked form included), Samsung's three-octet BSSID parts, private IPv4 addresses (10/8, 172.16/12, 192.168/16), and 10+-digit runs on a line that names an iccid, imei or imsi. Left as pulled: Android's placeholder MAC `02:00:00:00:00:00` and the 4-digit `iccid=` fragments in the Samsung logs. The original bytes go to `<campaign>/ddp-raw/<the same path>` (gitignored, never committed) and the counts per file to `ddp/scrub.json`. No number is read from a logcat (the records read `run<i>.log`, `run<i>.state` and `provenance.txt`). The campaigns of 2026-10-15 commit the per-run logcats and leave the execution-level `logcat.txt` (the whole unit's log) out.

**What differs from an attached-phone row.** The engine files, the command and its flags, the prompt, the CPU mask and the sampler are the same; the physical unit, its temperature and clock caps, and the cache state are not, and each is recorded.

| | attached phone (`android/bench/run_campaign.py`) | DDP (`bench matrix --ddp`) |
|---|---|---|
| unit | one phone; its serial is in `ops/dashboard-v1/schedule.json`, not in the record | an id is a pool: each job gets a unit, and the 8 jobs of one session ran on 8 units at once (2026-10-15, both ids); build fingerprint and serial in every record |
| session anchor | anchor rows run first; the dashboard job admits a sitting against the last admitted session's anchor | none: anchor rows are skipped, and a DDP row pools only with the rows of its own campaign (`render_leaderboard.latest_session`) |
| battery temperature, thermal-gate result | in the extended records (1K cells, round mode) | in every record |
| engine cache | `firstEver` from an on-device marker | `firstEver` on run 1 of each job, plus `conditions.engineCache` per run |
| runtimes | every Android arm of `android/README.md`, side builds included | the flat LiteRT-LM build only; llama.cpp rows are skipped (`runtime-not-wired-on-ddp`), and so are side builds |
| summary `device` | `<ro.product.model>` | `<ro.product.model> (DDP <id>)` |

**Limits.** The API contract bundled with the SDK (`googlecloudsdk/generated_clients/apis/devicerun/v1alpha/devicerun_v1alpha_messages.py`, SDK 587.0.0): `executionTimeout` default 5 min, range 1 min to 3 h; `args` at most 100; `androidPushFiles` at most 50 files; `androidPullFiles` at most 10 paths; job labels at most 16 (key ≤ 32 B, value ≤ 1024 B); displayName at most 63 B. The driver's own caps: 60 min per job by default (`--job-timeout`, any value in the API's range accepted) and 8 jobs per session; each job carries 10 labels (harness, campaign, cell, runtime, model, task, backend, device key, device id, engine).

**Cost.** The session report (`ddp/session-<n>.json`, also in the finished operation's `response`) gives every job's and every execution's `startTime` / `endTime`: a job's span includes its pushes, an execution's span is the wrapper's run. The device time a session used is read there; what a device-minute costs is in the project's billing.

**Smoke, 2026-10-15** (`results/raw/2026-10-15-ddp-smoke-akita-35-android/`). `session-5f9e1050` on `akita-35`, one Pixel 8a unit, one job (Qwen3-1.7B, CPU, short chat, 2 runs): PASSED, exit 0 in both runs. The session took 1354 s, the execution 1170 s, which holds the 120 s cooldown and a 600 s thermal gate before run 2 that timed out at Thermal Status 1. Both runs carry `cpu-capped` with the engine CPUs' ceiling 69.9 % below the hardware maximum, so neither pools. Run 1 built the XNNPACK weight cache, run 2 loaded it.

**Slice, 2026-10-15** (`results/raw/2026-10-15-ddp-slice-akita-35-android/`, `results/raw/2026-10-15-ddp-slice-m1q-36-android/`; per-run notes in `results/raw/2026-10-15-ddp-backend-dev/ROUND3.md`). The 8 LiteRT-LM v0.18.0 cells of Qwen3-1.7B and Gemma 4 E2B (short chat and the 1K text task, CPU and GPU, `runs=3`) as one session per id: `session-d5585b53` on `akita-35` and `session-9002dfea` on `m1q-36`. Each session's 8 jobs started within 0.05 s of each other on 8 units (8 serials per id, one build per id: Pixel 8a `BP1A.250405.007.B1`; `SM-S942U1` on Android 16, `BP4A.251205.006`). All 16 jobs PASSED, all 48 runs exited 0, 36 records per id. Session wall time: 2241 s (`akita-35`), 1821 s (`m1q-36`); the executions summed to 6625 s and 11658 s. Every `m1q-36` run started with the CPU ceilings below the hardware maximum (policy0 3187 / 3629 MHz, policy6 3398 / 4742 MHz), the 300 s wait timed out before each of its 24 runs, and every one of its 36 records carries `cpu-capped` and `cpu-capped-at-start` (`android/ddp/devices.json` has given `m1q-36` a 0 s wait since). On `akita-35` 9 records carry `cpu-capped` (the Qwen3-1.7B CPU short-chat job and the Gemma 4 E2B CPU 1K job), none at the start, and the Gemma 4 E2B CPU 1K job started runs 2 and 3 after thermal gates that timed out at Thermal Status 1; the `m1q-36` units stayed at Thermal Status 0. Of the 32 runs after a job's first, 7 CPU runs logged an XNNPACK weight-cache build (`xnnpackWeightCache` `built`) and 1 GPU run logged no `Initialized InferenceContext from serialized data` line (`gpuCache` `not-loaded`).

**The CLI target, `litert benchmark --ddp`** (the section above). For a `.litertlm` bundle the LiteRT-CLI target runs Google's published `litert_lm_advanced_main` (`gs://litert/binaries/latest/android_arm64/litert_lm/`) with a fixed argument set, `--backend`, `--model_path`, `--benchmark=true`, `--benchmark_prefill_tokens`, `--benchmark_decode_tokens`, `--max_num_tokens`, `--num_iterations`, `--metric_proto_file_path`, in one process per job after removing the caches beside the bundle (`litert_cli/commands/benchmark/ddp.py` of litert-cli 0.2.1, PyPI 2026-09-23). That is the shape of this repo's `native-benchmark-<P>x<D>` cells (forced token counts, no chat template), so for those cells it is a second route, with a different binary from the pinned tag this repo pushes. It has no way to push a prompt file, so the prompt-task cells (`short-chat`, `long-context-1024-gen256`) run on DDP through `bench matrix --ddp` only.

## The LiteRT-LM rows on a DDP iPhone (`ios/ddp`, 2026-10-16)

DDP runs iOS as XCTest (`gcloud beta device-run sessions submit xctest`), so the iPhone rows take the shape of litert-samples' `benchmark/ios`: the app is the host of an XCTest target, and the lab installs a `build-for-testing` archive. What runs inside is this repo's iPhone app on its headless path, the code `--yardstick-autorun` runs on the attached iPhone (`HeadlessAutoRun.specFromLaunchArgs` → `HeadlessRun.runAll` → `BenchmarkRunner` → `ResultStore`), so the records are the app's own schema-v1 records; no measurement code is new. Code and flags: `ios/ddp/README.md`; design and the build rounds: `results/raw/2026-10-16-build-ref-iphone-lm-dev/` (`DESIGN-D1.md`, `ROUND3.md`, `ROUND4.md`).

- **Archive.** `ios/BenchmarkApp/project-ddp.yml` (xcodegen → `BenchmarkApp-ddp.xcodeproj`) builds the app with the LiteRT-LM arm only (LiteRT-LM v0.18.0, iOS 18.0 floor) and the test target `BenchmarkAppDDPTests`. `ios/ddp/build_xctest.sh` runs `xcodebuild build-for-testing` (Release, `generic/platform=iOS`) and zips `Release-iphoneos/`, the `.xctestrun` manifest and `BUILD_INFO` (the LiteRT-LM version and artifact the app carries, the Xcode, the commit and the tree of `ios/BenchmarkApp` as built) into `ios/ddp/out/BenchmarkApp-ddp-xctest.zip`.
- **Submit.** `ios/ddp/run_ddp_ios_lm.py --device iphone16pro-18-3 --model-id <id> --backend gpu|cpu [--dry-run]`: one cell is one session, one device and one job, with `--runs` runs in one process (run 1 cold, runs 2 to N warm, as one launch of the app on the attached iPhone). The archive goes to the bucket once (content-addressed); the model is pushed from the bucket to `<app>:/Documents/models/litert-lm/<org>__<repo>/<file>` and the app's argv, as a JSON array, to `<app>:/Documents/yardstick_args.json`; the test reads it and runs the headless path once.
- **Pull.** `<app>:/Documents/results` (the app's records) and `<app>:/Documents/out` (`console.txt`, the process's stdout and stderr during the run; `records.txt`, the records this run added; `yardstick.done`, the exit code).
- **Records.** `results/raw/<campaign>/device-jsonl/`: the app's record plus `device.ddp` (catalog id, display name, OS) and `conditions.ddp` (session, job and execution ids and times, `xctestTimeout`, `xcodeVersion`, `resultType`, `runIndex`, the model object and sha256, the archive's sha256 and `BUILD_INFO`, the argv). `scripts/build_summary.py` names the device `<modelIdentifier> (DDP <catalog id>)` (`iPhone17,1 (DDP iphone16pro-18-3)`), so a lab unit never pools with an attached iPhone. The console goes to `<campaign>/console_<runtime>_<model>_<task>.txt` (the attached-iPhone runner's name); the lab's `system.log` (the unit's whole syslog) and `junit.xml` go to the gitignored `ddp-raw/`, and `plan.json` carries the home directory as `~`.
- **Limits.** `--xctest-timeout` 1 min to 1 h, without the device preparation and cleanup (the driver sets 15 min for GPU and 30 min for CPU); one session = one device type × one job; a pushed source is local or `gs://` (2.59 GB pushed and loaded, 2026-10-16). The lab re-signs the app: whether the app keeps its two memory entitlements (increased memory limit, extended virtual addressing) is not visible in the outputs; the 2.59 GB Gemma 4 E2B file loaded and ran on GPU and CPU. The archive must be signed with an App ID whose provisioning profile carries those entitlements: the archive of 2026-10-16 carries the attached bench app's App ID (`com.example.CoreMLLLMChat`), so it is never installed on the attached iPhone; a dedicated App ID needs a person with the Apple account in Xcode. `environment.lock.json` has no iOS v0.18.0 entry yet (the attached iPhone rows are v0.16.0, a different engine: never pooled); adding it is a person's decision.

**Sessions, 2026-10-16** (`results/raw/2026-10-16-ddp-iphone16pro-18-3-ios/`). LiteRT-LM v0.18.0 short chat, `runs=4`, on `iphone16pro-18-3` (iPhone 16 Pro; the units report iPhone17,1 and iOS 18.3.2), Xcode `xcode-26-2`, one session per cell: `session-70a0e2dc-9c0f-4232-babf-77a7c15ceb49` (Qwen3-1.7B, GPU), `session-71bd2279-fb3e-4bd8-8a61-c6583dad3bf5` (Qwen3-1.7B int8, CPU), `session-2af96355-979f-444b-a3ba-9259d5863dd4` (Gemma 4 E2B, GPU), `session-869a5c6a-46ff-45c5-83a8-6d511476e383` (Gemma 4 E2B, CPU). All four PASSED, each on its own unit, with 4 records each (16). The sessions took 8.6, 20.0, 14.7 and 15.7 min from creation to end, of which the test itself 185, 622, 156 and 270 s and the device preparation before it (the install and the push of 0.98, 2.06, 2.59 and 2.59 GB) 304, 559, 700 and 654 s. Both GPU consoles register the Metal accelerator (`RegisterAccelerator … name=GPU Metal`, `YARDSTICK_METAL_DEVICE name=Apple A18 Pro GPU`). The units did not start every run at the nominal thermal state (`initialThermalState`: Qwen3-1.7B int8 CPU at serious from run 1, Gemma 4 E2B GPU at fair from run 1 and serious from run 3, Gemma 4 E2B CPU at fair from run 3, Qwen3-1.7B GPU at fair in run 4), and the attached-iPhone runner's gate (`scripts/cell_gate.py`, `--ok-thermal nominal`) calls each of the four first captures HOT: as that runner does with a HOT first capture, their records sit in `device-jsonl-flagged/` with one `FLAGGED.txt` line per cell and are not in `results/summary/`. A retake with a thermal wait before run 1 comes next.

## Next step

The HTTP route (Route C) is the shape to build the standing job on — a session per (device × model) from an HTTP client, results as pulled files — and the APK route stays the advanced case for what a native binary cannot do (the Hub download on the device, the correctness gate). For `.tflite` models it works today on CPU and GPU, and LiteRT-LM runs on it as well (the section below); what LiteRT-LM still lacks on that path is a public Android binary. The APK pipe is proven end to end on one model and one device. What remains is the outer job from "Two routes": one session per (device set × repo) on a schedule, the rows written into each card with the session URL as the citation. Before that: a GPU session with a GPU-published bundle (the 270M q8 is CPU-only by its card; the APK's GPU path runs), a billion-class model through the same gate (the 6/8 bar has not been exercised on DDP), and the token question above.
