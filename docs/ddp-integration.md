# Evaluating HF LiteRT models on the Developer Device Platform (DDP)

*Written 2026-09-09 against the DDP docs dated 2026-09-03 (Preview). Nothing here has run on DDP yet; every claim about the platform is from its documentation, and every claim about this harness is from the code in this repo.*

**Goal (as asked by the LiteRT team):** evaluate the `.litertlm` files published under `litert-community` automatically on real devices, publish the numbers, and link each number back to the DDP run that produced it.

## What DDP offers, as documented

| surface | what it is | what it means for this harness |
|---|---|---|
| Device Catalog | 213 device rows (`gcloud beta device-run devices list`): Pixel 8a `akita-34/35`, Pixel 9 `tokay-34/35/36`, Pixel 10 Pro `blazer-36`, Pixel 11 `cubs-37`, Galaxy S24 `e1q-34/36`, S25 `pa1q-36`, S26 `m1q-36`, foldables, tablets | the same phones this repo already measures (Pixel 8a, Galaxy S26) exist there, so rows are comparable with the local ones |
| Device Run | batch: `gcloud beta device-run sessions submit instrumentation --device <ids> --apps app.apk --test test.apk`; multiple devices per session, uniform / smart sharding, `--async`; results land in `gs://<project>/automation/sessions/<session-id>/` with a Cloud Console URL | takes an **Android instrumentation-test APK only** — the native `litert_lm_advanced_main` binary this harness pushes over adb cannot be submitted as-is |
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

## What already exists in this repo for Route B

- `schema/result.v1.json` — the record shape; `scripts/build_summary.py` / `render_leaderboard.py` consume it.
- `android/bench/parsers.py` — parsing of the native benchmark output; the APK's Kotlin measurement should emit the same fields so the parsers and the summary layer stay shared.
- `android/engine-pins.json` — the version-pin discipline: the APK bundles one `litertlm-android` version per build and reports it in every record.
- `methodology/android.md` — what is and is not comparable across runs (no warm regime on Android, TTFT caveats).

## Open questions (for whoever owns the GCP project)

- **Cost attribution.** The web docs describe a bucket path and a Console link per session; the CLI itself (`gcloud beta device-run sessions submit instrumentation --help`, SDK 579.0.0, read 2026-09-10) exposes `--labels=[KEY=VALUE,...]` "user-defined key-value labels to attach to the session". So a per-session label exists at the API level; whether it reaches the billing export is still unverified. The fallback stays the naming convention (`campaign=<repo>--<file>--<device>` in the test options) plus the bucket path.
- **Which project pays.** The APK and the job are project-agnostic; a first session on a personal project costs a few device-minutes and shows the real result shape.
- **Correctness beyond the gate.** GSM8K-class parity runs are minutes per model on a phone; they fit Device Run's sharding, but the budget decides whether they are nightly or per-release.

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
   - `--instrumentation-timeout` defaults to **5 m** and caps at 1 h; a 300 MB download + gate + 3 runs with 60 s cooldowns needs ~10 min on a 270M model, so 30 m.
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

## Next step

The pipe is proven end to end on one model and one device. What remains is the outer job from "Two routes": one session per (device set × repo) on a schedule, the rows written into each card with the session URL as the citation. Before that: a GPU session with a GPU-published bundle (the 270M q8 is CPU-only by its card; the APK's GPU path runs), a billion-class model through the same gate (the 6/8 bar has not been exercised on DDP), and the token question above.
