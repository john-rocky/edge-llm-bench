# ROUND17 — 1K task tail → the noref sentence on every arm, prompt version marked — worker edge-llm-bench-wt-autopilot-tmpl-a8 [ed27cf] (Opus 5.5), started 2026-10-19 11:54 JST

Supervisor: edge-llm-bench-55 [4f120b]. Worktree `~/code/edge-llm-bench-wt-autopilot-tmpl`, branch `task1k-noref-tail` (from 80a36462).
REPO = the worktree, MAIN = `~/code/edge-llm-bench`, SIDE = `MAIN/.build/dd-ios-0180-18pro/src/ios/BenchmarkApp`, K = this dir,
P = `~/code/litert-bench-dashboard` (read only).

**Result**: the 1K cross-arm task `long-context-1024-gen256` now ends with the 2K ladder's `-noref` sentence on every arm (one Swift
constant, the generator, the file: diff = the tail line; same id, 18 blocks, budget 256). Every record of a versioned task carries
`conditions.promptVersion` (1K `noref-2026-10-19`, 2K noref `noref-2026-10-12`): Apple through `RunConditions`, Android / DDP / the Mac
Python drivers from `prompts/text/versions.tsv`; the summary has `prompt_version`; the checker keys its prompt-token history by it; the
watch and the page (P patch) compare a point only with points of its own version, so the break is marked and never red. A stale
ExecuTorch render is refused. Mac smoke on the yardstick built from SIDE (`.build/dd-mac-noref`): llama.cpp Gemma 4 E4B, MLX OptiQ E4B,
LiteRT-LM Gemma 4 E2B and llama.cpp Qwen3 1.7B all answer the task and run to 256 tokens (+17 prompt tokens each); the iPhone app is built
from SIDE into `.build/dd-ios-noref` (not installed). All 14 selftests green; the P patch applies to P c06e5a4 and passes P's
check_regression and render_check on a real export with and without a synthetic break. Merge, dd-mac switch, install, the ExecuTorch
re-render and the flip date are the supervisor's.

## 下見 (11:55–12:02)
- 11:54 JST, REPO `task1k-noref-tail` at 80a36462, clean. REPO `ios/BenchmarkApp/Sources` and `apple/YardstickCLI/Sources` = SIDE
  (`diff -rq`), `project.yml` and the pbxproj REPO = SIDE; SIDE / MAIN `Vendored/engine-pins.json` sha256 `f9f0c846…`.
- The prompt today: `LongContextTask.swift` 1K = `forceLongOutput` branch ("Using the passage above as context, list 25 …", l.87–89),
  18 blocks (`targetTokens 1024 / tokensPerBlock 55`); `norefTail` l.46–49 (2K noref, `BenchmarkTask.swift` l.53–54). The forceLongOutput
  branch also serves `long-context-2048-gen256` (27 blocks), which keeps it.
- `prompts/text/long-context-1024-gen256.txt`: 5,219 bytes, sha256 `f64fb5151d79d1dd…`, 21 lines, last line = the passage tail, no final
  newline; unchanged since the carve-out (git log: one commit, ca5dfe6e 2026-08-17). `budgets.tsv`: short-chat 128, the three long tasks 256.
  `long-context-2048-gen256-noref.txt` first committed 2026-10-12 (ee240588, catalog X2 S26); `norefTail` in Swift since 1798483f (records
  2026-10-17).
- Who reads the 1K file: Android `run_cell.push_prompt` (pushes it each launch; the hash check only under STRICT_SMOKE), the DDP plan
  (`run_ddp.py` l.291, content-addressed push) whose records `android/ddp/record.py` builds (l.314 conditions) — the DDP weekly
  (`dashboard-ddp-v1-android-s26.cells`) runs the 1K task on 10 rows; `ortgenai_mac.py` / `uzu_mac.py` `task_input`; ExecuTorch:
  `gemma4_e2e_runner` reads the file, `llama_main` a render made once on the host (`<pte stem>.prompts/<task>.chat.txt`,
  `scripts/executorch/make_prompts.py`): the six Mac Qwen3 renders in `MAIN/models/executorch/` carry `sourceSha256 f64fb515…`, and
  `executorch_inputs` checked only `renderedSha256` (a stale render would run the old text unnoticed). The DDP APK (`android/ddp-bench`)
  runs `short-chat` (an asset copied at build time) and `native-benchmark-*` only: no 1K prompt in it (`LitertlmBenchTest.kt` l.70–73).
- Checker: `session_check.history_index` keys `(platform, engine, runtime, model, task, model_file)` from `HEAD:results/summary/device-runs.csv`;
  `check_cell_counts` compares the cell's counts with that history (l.1189–1240). `reply_rules` → `parsers.text_integrity`, whose
  off-task screen is a fixed regex (`on.device|phone|local|cloud|offline|privacy|\bai\b`, parsers.py l.177), not the prompt file: the new tail
  asks the same subject.
- Watch: `regression_watch.build_series` sets `engine_changed` (l.311) as a mark only — red is `pct < -SPREAD_FLAG` whatever the engine;
  `regime_changed` is the one that cuts the comparison (earlier points of the other regime are skipped). P: `build.py` l.1239–1350
  builds `regression.json` (the same two marks), `regression_csv_text` l.1430, the page JS `regVsPrev` l.4243–4253, the chart's line break
  on `regime_changed` l.4397 / l.4426, aria l.4490, tooltip l.4570; `check_regression.py` restates it walking forward (l.186–206);
  `render_check.py` checks the words, data attributes and paths (l.1308–1316, 1380, 1416, 1524).
- CI `data-pipeline.yml` `summary-fresh`: `build_summary.py` then `git diff --exit-code results/summary/` — a new column needs the rebuilt
  summary in the same commit.

## 設計
- **Version names** (`prompts/text/versions.tsv` = `gen_task_prompts.VERSIONS` = the Swift tasks' `promptVersion`): `long-context-1024-gen256`
  → `noref-2026-10-19`; `long-context-2048-gen256-noref` → `noref-2026-10-12` (the day its text first ran, catalog X2 S26; its text is
  unchanged, so its records before carry no version and the same text); every other task: none. A record without the key = the text the
  task id was born with.
- **One constant**: the 1K catalog entry takes `tail: LongContextTask.norefTail` (as the 2K noref does); the `forceLongOutput` branch
  stays for `long-context-2048-gen256`. The generator: `long_context(1024, True, tail=NOREF_TAIL)`.
- **Record** (`conditions.promptVersion`, string): Apple — `BenchmarkTask.promptVersion` (protocol, default nil) → `RunConditions.record(runtime
  conditions, promptVersion:)` in `BenchmarkRunner` (nil when neither: an unversioned task on a runtime that reports nothing keeps having no
  `conditions`); Android `run_cell.prompt_version(task)` from versions.tsv for every prompt task; DDP: `run_ddp` puts it in the job,
  `record.py` writes it (a job planned before carries none = the old text it pushed); Mac Python drivers from versions.tsv. Schema:
  `conditions.promptVersion` string.
- **ExecuTorch guard**: `executorch_inputs` refuses a llama_main render whose `prompts.json` `sourceSha256` is not the sha256 of
  `prompts/text/<task>.txt` now, with the re-render command (the existing revision check's form).
- **Summary**: `prompt_version` after `task` (`build_summary.prompt_version_of`), empty when the record names none; README text in
  `build_summary.main`; `test_render_rules.FIELDS`.
- **Checker key**: `history_index` adds `prompt_version`; `check_cell_counts` matches it beside `model_file` (`prompt_version_of` from
  build_summary): a new version has no history → the existing "prompt history: none for <cell> at prompt version <v>" note, never a HOLD
  against the old text.
- **Watch and page** (the regime form, supervisor 12:0x): a point's `prompt` = its rows' prompt_version ('' = first text; two versions in one
  sitting joined by '+', equal to no single version). Per metric, the comparison set is the earlier points with a value **of the same
  prompt version** (then, on decode, of the same regime). `prompt_changed` = the nearest earlier point with a value is of another version,
  `prev_prompt` = that version. So the first point on the new text has `pct` null (never red, no retake); a back-out (A, B, A) compares the
  last A with the first A, marked. `judge` refuses a retake whose previous point ran another version. Outputs: `meta.prompt_changes`,
  `prompt_breaks[]`, the console / markdown line "prompt none -> noref-2026-10-19 (not compared)".
- **P patch** (`K/p-prompt-version.patch`, 4 files): `build.py` — `regression_prompt`, the same cut, `vs_prev.prompt_changed / prev_prompt`,
  `vs_first` within the version, the rules text, `regression.csv` column `prompt_version`, the build line's "prompt changes N"; page JS —
  `regVsPrev` "prompt changed, not compared", `regPromptText` "prompt changed from the previous point (none → noref-2026-10-19): not
  compared", the line broken at the change, `data-prompt-changed`, the aria-label reasons, the tooltip ("prompt <v>", "not compared:"), the
  status line "N points not compared (prompt none → noref-2026-10-19)", the section notes; `check_regression.py` — the walk-forward with the
  version in the key, the point's `prompt`, the CSV column; `render_check.py` — the words, the attribute, the paths, the status line;
  README — the fields and the rule.

## diff の要点
- Swift (REPO = SIDE, `cmp` per file): `BenchmarkTask.promptVersion` (protocol + default nil), `LongContextTask.promptVersion` (init
  parameter), the 1K and 2K noref catalog entries, `RunConditions.promptVersion` + `RunConditions.record`, `BenchmarkRunner` one argument.
  No project file, no new source file.
- `prompts/text/long-context-1024-gen256.txt` 5,219 → 5,311 bytes, sha256 `f64fb515…` → `740112dbbb11f873ec6c905fab30be30b431acff09d78d38c815b02a83f753fe`;
  the tail line = the 2K noref file's last line (`diff`); 18 `[n]` blocks. New `prompts/text/versions.tsv` (2 lines).
- Drivers: `run_cell.prompt_version` (+ the record), `run_ddp` job `promptVersion` → `record.py`, `ortgenai_mac` / `uzu_mac` /
  `executorch_mac` `prompt_version`; `parsers.executorch_inputs` source-sha guard.
- Summary / checker / watch: as in 設計. `results/summary/` rebuilt from the index export (5,988 rows; the CSV without `prompt_version`
  = HEAD's byte for byte; README +6 lines).
- Docs: `docs/dashboard-cells-v1.md` "1K task tail (2026-10-19)" (decision, why, the two tails with sizes and shas, the version mark and
  its readers, the smoke's token table, the flip, the back-out) and a pointer in "Second task in the weekly set".

## selftest の末尾 (12:15–12:24, nice 19; logs in the scratchpad `logs/*.1.txt`)
| test | rc | last line |
|---|---|---|
| py_compile scripts/ android/bench/ android/ddp/ bench | 0 | — |
| validate_cells matrices/*.cells; --require-anchor release-regression + anchors | 0 / 0 | OK matrices/vl-response-v1.cells / OK matrices/anchors.cells |
| android/bench/test_longctx1024.py | 0 | OK (13 tests; the prompt test reads `norefTail` and the version from Swift, the generator, versions.tsv and `run_cell`) |
| android/bench/test_longctx.py | 0 | run 1/1 OK decode=31.0 thermal=light->light |
| scripts/test_render_rules.py | 0 | OK (the header with `prompt_version`) |
| scripts/test_import_native_benchmark.py | 0 | OK |
| scripts/session_check_selftest.py | 0 | selftest OK (+2: a new version reads no history, a record without one is held to the old) |
| scripts/regression_watch_selftest.py | 0 | selftest OK (+5 in (a'): the cut, the next point red within the version, the count and listing, judge, the console) |
| scripts/dashboard_post_selftest.py | 0 | selftest OK |
| scripts/dashboard_job_selftest.py | 0 | selftest OK |
| android/bench/selftest.py | 0 | selftest OK (250 ok; +2: a stale render refused with the re-render line, taken again once current) |
| android/ddp/selftest.py (BENCH_ANDROID_BIN_DIR = MAIN/android/bin) | 0 | ddp selftest OK (76 checks) |
| scripts/autopilot_selftest.py | 0 | autopilot selftest OK (58 checks) |

## build の行
- Mac (SIDE → `MAIN/.build/dd-mac-noref`, fresh derived data, SourcePackages an APFS clone of `dd-ios-0180-18pro/SourcePackages`; r13's
  line): `xcodebuild -project BenchmarkApp.xcodeproj -scheme yardstick -configuration Release -destination "platform=macOS,arch=arm64"
  -derivedDataPath MAIN/.build/dd-mac-noref -onlyUsePackageVersionsFromResolvedFile -skipPackagePluginValidation -skipMacroValidation
  ARCHS=arm64 ONLY_ACTIVE_ARCH=YES build` — BUILD SUCCEEDED 12:26:51–12:28:32. `yardstick` sha256
  **7ad3f33c11185e950e58e3469a1870a3df04e169f01aad9322af548110b16d19**; `libCLiteRTLM_mac.dylib` 9526db9e… (= v0.18.0); `llama.framework`
  UUID **843E7D68** (= b11721, = the job's dd-mac); `yardstick version`: flavor=full harness=2026-07-30-agreed-protocol-r4; the binary
  holds `noref-2026-10-19`, `noref-2026-10-12`, the noref tail and the passage tail (the 2K ladder's) once each.
- iPhone (SIDE → `MAIN/.build/dd-ios-noref`, fresh derived data, the same seed; r9 / r13's line with that derived data path):
  `xcodebuild build -project BenchmarkApp.xcodeproj -scheme BenchmarkApp -configuration Release -destination generic/platform=iOS
  -derivedDataPath MAIN/.build/dd-ios-noref -allowProvisioningUpdates -allowProvisioningDeviceRegistration -skipPackagePluginValidation
  -skipMacroValidation DEVELOPMENT_TEAM=MFN25KNUGJ PRODUCT_BUNDLE_IDENTIFIER=com.example.CoreMLLLMChat` — BUILD SUCCEEDED
  12:30:36–12:32:08. `BenchmarkApp.app` main binary sha256 **909cf80c3675b442cab1b26bb0606c0c7b1e0495203a0507ed7002ae4e1b990e**;
  `llama.framework` UUID 6226C23F, `CLiteRTLM.framework` UUID 8B273118 (both = the supervisor's 11:33 app in dd-ios-0180-18pro, which stays
  untouched: sha 1fddd7e2…); bundle pins litert-lm v0.18.0 (`CLiteRTLM.xcframework.zip@v0.18.0`), llama.cpp b11721, core-ai
  1.0.0-10-gbd3c539; `com.example.CoreMLLLMChat`, team MFN25KNUGJ; the noref strings in the binary. Not installed.
- Pins: SIDE's and MAIN's `Vendored/engine-pins.json` sha256 `f9f0c846…` before = after both builds.
- Warnings in the touched files: none (the build logs' only warning lines are in the vendored LiteRT-LM Swift package).

## smoke の表
`MAIN/results/raw/2026-10-19-noref-tail-probe-mac/` (not committed), 12:28:35–12:30:33, MAIN's Mac runner called directly
(`DD_MAC=MAIN/.build/dd-mac-noref`, `BENCH_ENGINE_PINS_FILE` = SIDE's pins), cells = the weekly rows with runs=1 cooldown=30
(scratchpad `probe/noref-tail-probe-mac.cells`, validate OK). Every record: `conditions.promptVersion` `noref-2026-10-19`,
`device.buildConfiguration` Release, the schema validates (jsonschema 4.26.0, scratchpad `tools/schema_check_r17.py`). Before = the same
cell's records in today's sittings (llama.cpp: `2026-10-19-dashboard-v1-m4max-llama-b11721-mac`, 4 runs; MLX: `2026-10-19-mlx-gemma4-file-mac`;
LiteRT-LM: `2026-10-19-dashboard-v1-m4max-0180-rebuilt-mac`). Rates are in the records and not used (a prompt check).

| arm × model | prompt tok before → after | generated before → after | reply, first 90 chars (after) | reply before (first chars) |
|---|---|---|---|---|
| llama.cpp b11721 Gemma 4 E4B (jinja / false) | 1106 → **1123** | 86 (stop) → 256 | `Here are 25 distinct things on-device AI lets a phone do that a cloud model cannot:\n\n1. **Real-time Voice Transcription …` | `I am sorry, but the passage you provided is placeholder "Lorem ipsum" text. …` |
| MLX gemma-4-e4b-it-qat-OptiQ-4bit | 1107 → **1124** | 256 → 256 | `Here are 25 distinct things on-device AI lets a phone do that a cloud model cannot:\n\n1. **Real-time Voice Transcription Offline:** …` | `As a Large Language Model, I must inform you that the provided text is a block of repetitive "Lorem Ipsum" …` |
| LiteRT-LM v0.18.0 gemma-4-E2B-it (ctx 2048) | 1106 → **1123** | 256 → 256 | `Here are 25 distinct things on-device AI lets a phone do that a cloud model cannot:\n\n1. **Real-time, low-latency voice commands:** …` | `The provided text is placeholder "Lorem ipsum" text and does not contain any information …` |
| llama.cpp b11721 Qwen3 1.7B (jinja / template-default) | 1338 → **1355** | 256 → 256 | `<think>\nOkay, the user wants me to list 25 distinct things that on-device AI can do that a cloud model can't. …` | `<think>\nOkay, the user wants me to list 25 distinct things …` |

- `FAILURES.txt` lists both llama.cpp cells: each launch aborts after its record (`Abort trap: 6`); the E4B launch's crash report
  `yardstick-2026-10-19-122849.ips` = `ggml_abort` ← `ggml_metal_rsets_free` ← `ggml_metal_device_free` ← the device `unique_ptr`
  destructor (r9 / r13's teardown abort on b11721); the Qwen3 launch left no crash report of its own (unverified which frame; the console
  tail is the same).
- ExecuTorch on the staged files (REPO's `executorch_mac.py --dry-run`, `--model-dir MAIN/models/executorch`, Qwen3 0.6B XNNPACK): 1K → rc 75
  "NOT STAGED … long-context-1024-gen256.chat.txt was rendered from another prompts/text/long-context-1024-gen256.txt (prompts.json
  sourceSha256 f64fb515…, the file now 740112db…); re-render: …"; short-chat → rc 0, the planned command. The six re-renders into the
  scratchpad (`~/code/executorch-convert/.venv-et151/bin/python`, transformers 5.0.0rc1 = the staged renders'): 1K hostPromptTokens
  1338 → **1355** on all six (0.6B / 1.7B / 4B × XNNPACK / MLX; = the llama.cpp Qwen3 count), renderedSha256 `360771899cd1…` → `e8cfb3f021c4…`;
  short-chat unchanged (19, `9d2fe60da55b…`).

## P の patch の検査 (12:33–12:3x)
`K/p-prompt-version.patch` (591 lines; README, build.py, tools/check_regression.py, tools/render_check.py), made in a scratchpad clone of
P at 6eaf7f9; `git -C P apply --check` OK on P 1f45083 and again on c06e5a4 (P's commits since 6eaf7f9 touch `dist/` only). On an export of
this branch's index with its summary rebuilt there (scratchpad `tools/p_test_r17.sh`):
- P unpatched (c06e5a4) and patched build against the plain export: `cells.json` identical; `regression.json` identical but for the new
  fields (`prompt`, `prompt_changed`, `prev_prompt`) and the rules text; `regression.csv` identical but for the `prompt_version` column
  (every value empty); the build line "37 series, 151 sittings (107 shown), red points decode 5 / prefill 10 / memory 7, regime changes 2,
  prompt changes 0".
- A copy of the export with the Galaxy S26's 2026-10-19 Qwen3 0.6B LiteRT-LM GPU 1K rows marked `noref-2026-10-19` (6 rows): that point
  has `prompt_changed` on decode, prefill and memory, `pct` null, not red; red memory points 7 → 6 (the one it had vs 2026-10-06 is no longer
  a comparison); "prompt changes 1".
- `tools/check_regression.py` PASS on both builds; the bench's `regression_watch.py --compare` equal on both (red 22 / 22 and 21 / 21,
  series 37, points 151, shown 107); the bench console line "prompt  SM-S942Q | Qwen 3 0.6B | long-context-1024-gen256 | GPU |
  2026-10-19-dashboard-v1-s26-q06-dynamic-android | prompt none -> noref-2026-10-19 (not compared)".
- `tools/render_check.py` (headless Chrome, quiet hold "r17 P render_check" 12:35:09–12:36:56): plain build PASS (70 ok lines); the build
  with the break PASS (70 ok lines, console errors 0), its default selection reading "No point more than 5 % worse than the one before it
  on Decode Speed (tok/s) — Qwen 3 0.6B, text task 1K/256: 5 lines, 8 points (2 lines with one point only). 1 point not compared (prompt
  none → noref-2026-10-19)." with the S26 tile's GPU line broken at the point, its `data-prompt-changed` and the aria-label words checked
  against `regression.json`.

## 経過
- 11:54 ListAgents (this session = edge-llm-bench-wt-autopilot-tmpl-a8 [ed27cf]); HEAD 80a36462, tree clean. Supervisor present (busy).
- 11:55–12:02 下見: LongContextTask / BenchmarkTask / gen_task_prompts / the two prompt tests / run_cell push_prompt / run_ddp + record.py
  / the ExecuTorch prompt path / ortgenai_mac / uzu_mac / session_check history key / regression_watch / build_summary / P build.py,
  check_regression, render_check / CI data-pipeline. Two files outside the write list are needed (DDP record.py, parsers.py ExecuTorch
  guard); 12:02 SendMessage to the supervisor (one message, with the design notes). Next: the in-range changes while waiting.
- 12:0x supervisor: GO for record.py and parsers.py (same commit); the four design notes accepted (prompt_changed in the regime_changed
  form, P patch with build.py, device-runs.csv rebuilt from the index in the same commit, 2K noref = noref-2026-10-12); the six ET
  re-renders at the flip are the supervisor's (command in this file). Next: Swift, schema, prompts, drivers, summary, checker, watch.
- 12:03–12:13 code: Swift (4 files, REPO then SIDE after checking SIDE = HEAD for each; Sources REPO = SIDE again), schema, generator +
  versions.tsv + the 1K file (diff = the tail line), test_longctx1024, run_cell / ortgenai_mac / uzu_mac / executorch_mac / run_ddp +
  record.py stamps, the parsers.py guard + its selftest case, build_summary prompt_version, test_render_rules header, session_check key +
  2 selftest cases (green), regression_watch prompt cut + (a') selftest (green). Next: the P patch, the remaining selftests, docs.
- 12:14–12:26 P patch in a scratchpad clone of P (build.py regression + page JS, check_regression, render_check, README; `git apply
  --check` OK on P 1f45083, whose two commits since 6eaf7f9 touch dist/ only); docs section (smoke numbers to come); all 14 selftests
  green at nice 19 (summary in the scratchpad logs). The Mac job's llama.cpp retake ended 12:17:28 (ledger; post steps 12:18 / 12:22),
  lock empty, no runner at 12:26. Next: the window (Mac build into dd-mac-noref, smoke, iPhone build into dd-ios-noref, ET guard on
  the staged files + re-render into the scratchpad, schema).
- 12:26:51–12:32:30 window "r17 noref-tail window" (quiet_hold, 339 s, waited 0 s): Mac build 12:26:51–12:28:32 BUILD SUCCEEDED; smoke
  12:28:35–12:30:33 (4 cells, all on the new tail: prompt +17 tokens, 256 generated, every reply answers the task; the two llama.cpp
  launches abort at teardown after their record = FAILURES.txt); iPhone build into dd-ios-noref 12:30:36–12:32:08 BUILD SUCCEEDED (the
  11:33 app in dd-ios-0180-18pro untouched, sha 1fddd7e2…); ET: the 1K render of the staged Qwen3 0.6B refused (rc 75, the re-render
  line), short-chat passes; the six re-renders into the scratchpad 1338 → 1355; schema: all four records valid; pins f9f0c846 before =
  after. MAIN's disk summary was rebuilt in-tree at 12:30:58 by another process (MAIN HEAD moved to 394c2d83: r16 merged 12:28:44) and
  took this smoke dir's 4 rows (`grep -c noref-tail-probe` = 4); not mine, not reverted (MAIN is read only here; summary commits go
  through the index). Next: stage, the summary from the index, the P end-to-end test, the ladder, round close.
- 12:33 staged by explicit path; the summary rebuilt in an export of the index (5,988 rows; = HEAD without the new column); the P build
  test (nice 19): the first synthetic break (the iPhone 18 Pro's 0.6B 1K rows) showed no change — that series has no point; moved to the
  S26 GPU series: prompt changes 1, check_regression PASS, the bench's --compare equal, plain export identical between P c06e5a4 and the
  patched build but for the new fields. 12:35:09–12:36:56 quiet hold for render_check: PASS on both builds. 12:3x the third ladder in
  SPEED_LADDER.md (no rates side by side: public repo), this file. Next: round close, lint, commit, the merge preview, the message.

## 監督が打つ物 (the flip, together and between sittings)
1. **merge** `task1k-noref-tail` into main; `results/summary/device-runs.csv` conflicts on every row (main added rows since 80a36462, this
   branch added a column): take either side, then rebuild `results/summary/` from the merged index (the checkout-index procedure) and run the CI
   steps.
2. **P**: `git -C ~/code/litert-bench-dashboard apply ~/code/edge-llm-bench/results/raw/2026-10-18-bench-autopilot-dev/p-prompt-version.patch`
   (after the merge, the file is in MAIN), then the page build and its four checks; the bench's `scripts/regression_watch.py --compare
   ~/code/litert-bench-dashboard/dist/regression.json` must read equal. Without the patch, the page compares across the break and the
   bench does not (the first sitting on the new text could be red on the page only).
3. **dd-mac**: `.build/dd-mac` → `.build/dd-mac-noref` (yardstick sha256 `7ad3f33c…`, `libCLiteRTLM_mac.dylib` 9526db9e…, llama 843E7D68;
   keep the current dd-mac — the 11:34 template-fix build — under another name to back out).
4. **install** on the 18 Pro: `xcrun devicectl device install app --device 00008160-000038CA02C00036
   ~/code/edge-llm-bench/.build/dd-ios-noref/Build/Products/Release-iphoneos/BenchmarkApp.app` (main binary `909cf80c…`, = the 11:33 app
   plus this change: the same frameworks); record 1 of the next sitting must read `device.buildConfiguration` Release and, on a 1K row,
   `conditions.promptVersion` `noref-2026-10-19`. Back out: the 11:33 app in `dd-ios-0180-18pro` (sha `1fddd7e2…`).
5. **ExecuTorch re-render** in the merged MAIN (the six Mac Qwen3 rows refuse until then):
   `cd ~/code/edge-llm-bench && for n in Qwen3-0.6B-ET1.5.1-xnnpack-8da4w-emb8-ctx2048 Qwen3-0.6B-ET1.5.1-mlx-4w-emb8-ctx2048 Qwen3-1.7B-ET1.5.1-xnnpack-8da4w-emb8-ctx2048 Qwen3-1.7B-ET1.5.1-mlx-4w-emb8-ctx2048 Qwen3-4B-ET1.5.1-xnnpack-8da4w-emb8-ctx2048 Qwen3-4B-ET1.5.1-mlx-4w-emb8-ctx2048; do ~/code/executorch-convert/.venv-et151/bin/python scripts/executorch/make_prompts.py --snapshot "$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["checkpoint"]["snapshot"])' models/executorch/$n.recipe.json)" --suffix chat --out-dir models/executorch/$n.prompts; done`
   — expected: each prints `long-context-1024-gen256: 1355 prompt tokens` (the scratchpad run, `et/rerender/`), short-chat 19 as before.
6. Android, DDP, the Mac ONNX Runtime GenAI and uzu drivers: nothing to install (they read the merged checkout's prompt file and
   versions.tsv; a DDP plan made before the merge pushes the old file and stamps no version).
7. **SIDE** carries the four Swift files since 12:05: any SIDE build before the flip ships the new tail (its records marked). To build
   without it, restore those files in SIDE from main.

## 提案
1. `docs/session-check-v1.md` l.91 (`prompt-tokens`, column "source"): "the committed summary (`model_file` since 2026-10-19 …; `prompt_version`
   since 2026-10-19: the history of another text of the task is not read)" — the key changed in this round; the doc is outside this
   round's write list.
2. `docs/executorch-arm-v1.md` l.203: "The runner checks that `prompts.json` was rendered from the checkpoint's revision and from the
   repository prompt as it is now (`sourceSha256`), and that the prompt file still has the rendered sha256" — same reason.
3. The iPhone 17 Pro's tree (`.build/dd-ios-0180-17pro/src`) still builds the passage tail; before its next 1K sitting it needs the same
   four-file diff (check its Sources against REPO first), else its 1K records stay unversioned on the old text (honest, but off the new
   series).
4. P's cross-arm table compares each LiteRT-LM cell with other runtimes' latest cells; during the transition a compared cell can be on the
   other text. A mark like `stale` when the two cells' prompt versions differ (P's `make_cell` reads the rows' `prompt_version`) — a round
   in P.
5. A sitting whose cell holds two versions (a merge during an Android sitting) is never compared by the watch (`a+b` equals no version),
   but `arm_row` pools its runs on the page. A checker rule (`prompt-version-mixed`, HOLD) would keep such a dir from the autopilot's
   commit; not added here (a new rule and its doc).
6. After the flip, every 1K cell's first sitting reads "prompt history: none … at prompt version noref-2026-10-19" in the checker's notes
   (expected); the page shows "N points not compared (prompt none → noref-2026-10-19)" on each 1K selection for one week.

## 訂正
- The Mac's llama.cpp retake ended at 12:17:28, not about 13:00 (`MAIN/logs/dashboard-job/ledger.tsv`); the window was free from 12:26.
- The off-task reply screen does not read the prompt file: it is a fixed regex in `android/bench/parsers.py` l.177 (`text_integrity`);
  the new tail asks the same subject, so it needs no change.
- `engine_changed` does not keep a point from red: it is a mark only (`scripts/regression_watch.py` l.307–311, P `build.py` l.1335–1340);
  the red-free break is the `regime_changed` form, which the supervisor accepted at 12:0x.
- The page's regression data and words come from P's `build.py` (l.1239–1350, the JS l.4243–4573), not only `check_regression.py` /
  `render_check.py`: the patch carries build.py and README too.
- `results/summary/README.md` is written by `build_summary.main`, and CI `summary-fresh` (`.github/workflows/data-pipeline.yml` l.21–31)
  needs `device-runs.csv` rebuilt in the same commit: both are committed, from the index.
- The 2K noref text first ran on 2026-10-12 (ee240588, catalog X2 S26); 2026-10-17 is its Swift addition (1798483f): named
  `noref-2026-10-12`.
- DDP records are built in `android/ddp/record.py`, and the stale-render guard belongs in `android/bench/parsers.py` (both outside the
  launch's write list; supervisor GO 12:0x). The DDP APK runs `short-chat` and `native-benchmark-*` only (`android/ddp-bench/app/src/androidTest/kotlin/io/github/johnrocky/edgellmbench/LitertlmBenchTest.kt`
  l.70–73): no 1K prompt in it.
- Building the iPhone app into `dd-ios-0180-18pro` (r13's path) would have replaced the supervisor's 11:33 app awaiting install: built into
  `.build/dd-ios-noref`, so MAIN gained that dir beside `.build/dd-mac-noref` and the smoke dir.
- `scripts/gen_task_prompts.py` said "A tail change is a new task id once a record carries this one"; the decision keeps the id and marks
  the version: the comment is rewritten.

## 罠と袋小路
- The PreToolUse hook blocks `python3 -` heredocs, and a `cat >> file <<EOF` whose text names a runtime, while any quiet window is open —
  your own too: during a window edit files with the Edit / Write tools (or prefix `QUIET_OK=1` as the holder).
- `pgrep -f bench_matrix_mac.sh` inside a shell whose command line holds that name matches itself: `pgrep -f '[b]ench_matrix_mac\.sh'`.
- A synthetic version break shows nothing on a series whose marked point has no value (no point at all for the iPhone 18 Pro's 0.6B 1K
  series; a text-fail or cpu-capped point carries no value): mark a series with two measured, shown points (S26 GPU here).
- ExecuTorch `llama_main` prompts are rendered once on the host: after a prompt change, `make_prompts.py` again (since this round the cell
  refuses with that line instead of running the old text).
- MAIN's disk summary is rebuilt in-tree by other processes and takes uncommitted smoke dirs (this one's 4 rows at 12:30:58): never
  commit it from disk; rebuild from the index.
- After a Bash / python edit, the Edit tool reports "modified on disk since you last read it": `git diff` the file before trusting it
  (here it held only this round's edits).
- The harness blocks `sleep N; check`: wait on a Monitor that prints the log's end line.

## op と delegate の観察
- Not an op / delegate round: the task's text changed, no engine or backend. Measured: llama.cpp b11721 Metal runs both smoke cells to
  their record, then each launch aborts at teardown (`yardstick-2026-10-19-122849.ips`: `ggml_abort` ← `ggml_metal_rsets_free` ←
  `ggml_metal_device_free` ← the device `unique_ptr` destructor; the Qwen3 launch left no report: its frame unverified), as in r9 / r13.
  LiteRT-LM v0.18.0 on the Mac registered and destroyed `CpuAccelerator` and `GPU WebGPU` (the run's console tail). Fallback counts,
  fp16 / fp32 differences: none measured (なし).

## 使った環境
- Mac Studio M4 Max (Mac16,9), macOS 27.0 (26A428); Xcode 27.0 (27A266a, `Xcode-27.0.0-RC.app`), Swift 6.4; no phone touched (no adb /
  devicectl), no device hold.
- Engines in the builds: LiteRT-LM v0.18.0 (`libCLiteRTLM_mac.dylib` 9526db9e…; iOS `CLiteRTLM` 8B273118), llama.cpp b11721 (macOS
  843E7D68, ios-arm64 6226C23F), mlx-swift-lm 60bd0d78; SIDE / MAIN pins f9f0c846….
- Python 3.14.6 (system; selftests at nice 19); jsonschema 4.26.0 from `~/.venvs/ortgenai-0.17.1`; transformers 5.0.0rc1 in
  `~/code/executorch-convert/.venv-et151` (the re-render); Google Chrome 155.0.8059.80 headless (P render_check).
- Mac quiet holds: "r17 noref-tail window" 12:26:51–12:32:30 (339 s), "r17 P render_check" 12:35:09–12:36:56 (107 s).

## 残した file
- REPO commit (branch `task1k-noref-tail`): the Swift four, schema, prompts (the 1K file, versions.tsv), the generator, the drivers
  (run_cell, run_ddp, record.py, ortgenai_mac, uzu_mac, executorch_mac), parsers.py, build_summary, session_check, regression_watch, the
  selftests and tests, `results/summary/` (from the index), `docs/dashboard-cells-v1.md`, K `ROUND17.md`, K `p-prompt-version.patch`
  (for the supervisor to apply to P), K `SPEED_LADDER.md` (third ladder).
- `MAIN/.build/dd-mac-noref/` (the Mac yardstick for the switch) and `MAIN/.build/dd-ios-noref/` (the iPhone app for the install): keep until
  the flip uses them or the change is backed out.
- SIDE's four Swift files (= REPO's; SIDE is untracked).
- `MAIN/results/raw/2026-10-19-noref-tail-probe-mac/` (the smoke: 4 records, FAILURES.txt = the teardown aborts, SKIPPED.txt empty,
  session_provenance.txt; not committed; its rows enter every in-tree rebuild of MAIN's summary: 消してよい after review).
- Scratchpad (消してよい): `tools/` (window_r17.sh, ios_build_r17_inner.sh, et_rerender_r17.sh, schema_check_r17.py, selftests_r17.sh,
  p_test_r17.sh), `probe/` (the smoke cells), `et/` (the dry runs; `rerender/` = the six re-rendered prompt dirs, what the flip's step 5
  writes), `logs/`, `p-clone/` (P with the patch, uncommitted), `p-orig/` (P c06e5a4), `bench-export/` and `bench-export-break/` (index
  exports), `pdist/` (three P builds with their screenshots), `head-device-runs.csv`.
