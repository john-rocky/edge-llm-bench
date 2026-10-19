# ROUND15 — Android llama.cpp arm: Gemma 4 thinking off, Qwen3 the template's default — worker edge-llm-bench-wt-llama-bc [6ce474] (Opus 5.5), started 2026-10-19 11:44 JST

Supervisor: edge-llm-bench-55 [4f120b]. Worktree `~/code/edge-llm-bench-wt-llama`, branch `android-llama-thinking` (from e7e3f25e;
HEAD at start faea764e). REPO = the worktree, MAIN = `~/code/edge-llm-bench`, K = this dir, RUNNER = `REPO/android/bench/run_cell.py`.

## 下見
- 11:44:12 JST. REPO `android-llama-thinking` at faea764e, tree clean. Running at 11:47 (ps): MAIN's 18 Pro sitting (`dashboard_job.py
  iphone18pro`, `dashboard-llama-b11721-ios.cells`) and Mac sitting (`dashboard_job.py m4max`, `dashboard-llama-b11721-mac.cells`); no
  driver on either phone; neither hold file exists (`.device_hold`, `.device_hold.pixel8a`); adb lists 4C131JEKB15210 (Pixel 8a, usb 3-1)
  and RFGL80R6A6H (S26, usb 8-3.2).
- RUNNER (HEAD faea764e): l.699–701 = the side build's chat line (`{engine_dir}/bin/llama-cli -lv 4 -m … -t 6 -c … -f … -n … --temp 0
  --top-p 1 -st -ngl 99 -fa on -ub 1024 --device …`), l.711–713 = the flat build's (`./llama-cli -m … -t 4 -c … -f … -n … --temp 0 --top-p 1
  -st`), l.1448–1450 = `conditions.chatMode` "single-turn template default (-st)" on every llama.cpp prompt row (flat and side). The
  command goes to the phone as one string inside `sampler_shell` (`adb shell <string>`, mksh parses it); the one argument the runner
  already quotes for that shell is executorch's (`shlex.quote`). Family checks by name exist once: `parsers.executorch_runner_for(model_dev)`
  reads the device path's basename, which is `<model id with / -> _>_<file>` (`ensure_model`, `planned_command`, the dry-run plan).
- The phones' llama-cli (11:4x, `--help | grep -n -iE 'reasoning|chat-template-kwargs|jinja'`):
  - Pixel 8a flat, `version: 0.7.0-dev (build 11721, commit ff5a23376)`: l.492 `--chat-template-kwargs STRING` ("must be a valid json
    object string"), l.495 `--jinja, --no-jinja … (default: enabled)`, l.497 `--reasoning-format FORMAT … (default: auto)`, l.505 `-rea,
    --reasoning [on|off|auto] … default: 'auto' (detect from template)`, l.508 `--reasoning-effort LEVEL`, l.513 `--reasoning-budget N …
    -1 for unrestricted, 0 for immediate end … (default: -1)`.
  - S26 flat: the same build line (b11721 ff5a23376), the same help lines (492 / 495 / 497 / 505 / 508 / 513).
  - S26 side build `engines/b11469-snapdragon/bin` (`LD_LIBRARY_PATH=../lib:.`), `version: 0.6.0-dev (build 11469, commit ad2156533)`:
    l.485 `--chat-template-kwargs`, l.488 `--jinja` (default enabled), l.490 `--reasoning-format`, l.498 `-rea, --reasoning [on|off|auto]`
    (default auto), l.501 `--reasoning-effort`, l.506 `--reasoning-budget N` (default -1).
- Evidence the arm thought: `MAIN/results/raw/2026-10-19-dashboard-v1-pixel8a-llama-b11721-android/app-path-android/
  llama.cpp_unsloth_gemma-4-E2B-it-GGUF_short-chat_2026-10-19T01-15-22.457636_run1.log` l.116 `> Explain what on-device AI means in simple
  terms.`, l.118 `[Start thinking]`, then "Here's a thinking process that leads to the suggested explanation: 1. **Deconstruct the
  Request:** …" until the 128-token budget ran out mid-list (l.130 `[ Prompt: 32.5 t/s | Generation: 14.1 t/s ]`): no answer in the
  budget. Its record: `conditions.chatMode` "single-turn template default (-st)", no `thinking`, no `outputSample`. The side build (b11469)
  too: every one of the 24 S26 side-build Gemma 4 short-chat logs in MAIN (`2026-10-08-dashboard-npu-v1-s26-gemmae2b-chat-android`,
  `…-gemmae4b-short-android`, `2026-10-11-dashboard-v1-s26-npu-android`; npu and gpu, E2B and E4B) holds one `[Start thinking]`.
- Readers of `conditions.thinking`: `scripts/build_summary.py` (quality rows only), `scripts/regression_diff.py` (gsm8k quality pairs
  only). No speed reader: adding the key changes no number. `conditions.chatMode` is not in the schema; `thinking` is (boolean or
  "template-default", r13).

## RUNNER の diff の要点
- `LLAMA_THINKING_OFF_FLAGS` = `--chat-template-kwargs '{"enable_thinking":false}'` (the JSON through `shlex.quote`, the quoting the runner
  already uses for executorch's argument: one word for the phone's mksh; no space inside).
- `llama_thinking_off(model)`: `"gemma-4" in os.path.basename(model).lower()`. engine_command gets the device path, whose basename starts
  with the model id (`<model id with / -> _>_<file>`), so the command and the record decide from the same string (the executorch family
  check reads the same basename). A bare model id works too (selftest: `unsloth/Gemma-4-E4B-it-GGUF` True, Qwen3 / Gemma 3 False).
- engine_command: the flat line ends `… --temp 0 --top-p 1 -st --chat-template-kwargs '{"enable_thinking":false}'` for Gemma 4; the side
  build's carries it after `-st`, before `-ngl 99 -fa on -ub 1024 --device …`. Every other family's line is byte-identical to before
  (llama-bench rows untouched). planned_command (dry run, DDP plan) and the side build's `engineCommand` follow from the same function.
- record: `llama_chat_conditions(model_dev)` puts `chatMode` and `thinking` together where `chatMode` was (llama.cpp, not native-):
  Gemma 4 `"single-turn, GGUF template, enable_thinking=false (-st --chat-template-kwargs)"` / `false`; the rest `"single-turn template
  default (-st)"` (as before) / `"template-default"`. `thinking` is the schema's key (r13: boolean or "template-default").
- selftest (`android/bench/selftest.py`): campaign T (Gemma 4 E2B flat, Qwen3 0.6B flat, Gemma 4 E2B side build npu) checks the three
  shell lines (kwargs on both Gemma 4 lines, `shlex.split` gives `{"enable_thinking":false}` as one word, Qwen3 ends `-st`), the
  records' `chatMode` / `thinking` and the side build's `engineCommand`, the `--dry-run` plan, and the family check. `CPU_LLAMA_KEYS`
  (3d5655c's layout) gains `conditions.thinking` after `conditions.chatMode` (comment says so). `android/bench/test_longctx1024.py`
  (supervisor GO 12:0x): the 1K llama.cpp rows' expected line gains the kwargs for the gemma-4 model ids.

## probe の出力
Pixel 8a (4C131JEKB15210, flat b11721 ff5a23376, mask f0, AC powered, battery 78 %, 29.4 C), REPO's runner,
`run_cell.py --runtime llama.cpp --model-id <id> --file <gguf> --task short-chat --runs 1 --out REPO/results/raw/2026-10-19-probe-thinkoff-pixel8a-android`;
hold 12:03:52–12:04:31 (keeper pid 70665, queue_cli wait, released by hold_cli):
- Gemma 4 E2B (`…_short-chat_2026-10-19T03-04-16.049245_run1.log`): console `run 1/1 OK decode=14.0 thermal=nominal->nominal`;
  `[Start thinking]` 0; l.105 `build      : b11721-ff5a23376`, l.119 `> Explain what on-device AI means in simple terms.`, then the reply
  "Imagine you have a really smart assistant, like a personal helper, but instead of sending all your information to a giant computer in
  the cloud … **the smart assistant lives right on your device** … **On-device AI simply means running the "smart" part of the AI directly
  on that device, instead of needing to constantly talk to the internet.**" (cut by the 128-token budget mid-analogy), l.133 `[ Prompt:
  26.5 t/s | Generation: 14.0 t/s ]`, l.137 `EXIT_CODE=0`. Record: `chatMode` "single-turn, GGUF template, enable_thinking=false (-st
  --chat-template-kwargs)", `thinking` false, engineVersion b11721, model sha256 740185b2… (= r13's E2B blob).
- Qwen3 1.7B (`…_short-chat_2026-10-19T03-04-31.609015_run1.log`): `run 1/1 OK decode=21.2`; `[Start thinking]` 1 (l.85), then "Okay,
  the user wants to know what on-device AI means in simple terms. …" (as before); l.93 `[ Prompt: 53.8 t/s | Generation: 21.2 t/s ]`,
  l.97 `EXIT_CODE=0`. Record: `chatMode` "single-turn template default (-st)", `thinking` "template-default".

S26 side build (RFGL80R6A6H, `engines/b11469-snapdragon`, b11469 ad2156533, backend npu, mask none, USB powered, battery 79 %, 28.4 C;
supervisor GO 12:0x), `--backend npu --engine-build b11469-snapdragon`, out `REPO/results/raw/2026-10-19-probe-thinkoff-s26-side-android`;
hold 12:05:14–12:05:27 (keeper pid 90872):
- Gemma 4 E2B (`llama.cpp-npu_…_short-chat_2026-10-19T03-05-27.019876_run1.log`): `run 1/1 OK decode=29.9`; `[Start thinking]` 0;
  l.172 `using device HTP0 (Hexagon)`, l.251 `offloaded 36/36 layers to GPU`, l.349 `build      : b11469-ad2156533`, l.363 the prompt
  echo, reply (decoded text) "Imagine you have a really smart assistant, … **the smarts are actually living right on your device.** **On-device
  AI simply means running the Artificial Intelligence directly on your phone, computer, or smart device, …**", l.388 `[ Prompt: 123.5 t/s |
  Generation: 29.9 t/s ]`, l.392 `EXIT_CODE=0`. Record: textCheck PASS, `thinking` false, engineVersion b11469-snapdragon, `engineCommand`
  ends `-st --chat-template-kwargs '{"enable_thinking":false}' -ngl 99 -fa on -ub 1024 --device HTP0`; protocolFlags `cpu-capped` (policy6
  min 4396.8 / 4742.4 MHz, cpus 6-7; THERMAL_GATE.txt) — a probe, its number is not used.

Verdict: Gemma 4 E2B short-chat thinks no more on either build (no `[Start thinking]`, a direct answer to the task, `run 1/1 OK`,
EXIT_CODE=0); llama-cli takes the kwargs on b11721 and b11469; Qwen3 1.7B thinks as before.

## cells
Supervisor's choice (12:2x, option C): one model per S26 sitting (each about 50–60 min), the Pixel 8a one sitting (~60 min). Every file's
first row is the Android anchor row (= `dashboard-llama-b11721-android.cells` l.20).
- Pixel 8a `matrices/dashboard-llama-thinkoff-android.cells`: anchor + `dashboard-text-v1-android-a.cells` l.28, l.31 (E2B short-chat, 1K) +
  `dashboard-text-v1-android-b2.cells` l.16, l.19 (E4B, exclude-on=pixel8a: skipped on the Pixel; dry run shows the two skips).
- S26, in this order: `matrices/dashboard-llama-thinkoff-s26-e2b.cells` (anchor + text-v1-a l.28, l.31), `-s26-e4b.cells` (anchor +
  text-v1-b2 l.16, l.19), `-s26-side-e2b.cells` (anchor + `dashboard-npu-v1-android-s26-short.cells` l.23, 24: npu / gpu),
  `-s26-side-e4b.cells` (anchor + the same file's l.29, 30).
- `matrices/dashboard-llama-thinkoff-ladder-android.cells` (a list): the anchor row + `dashboard-npu-v1-android-s26.cells` l.29, 30, 39, 40
  (side build 1K, page cells, by hand) + `dashboard-longctx-v1-android-s26.cells` l.54–56, 76–78 (2K ladder, round mode). Not listed:
  the protocol rows (llama-bench), the longctx1024 Gemma 4 rows (= the text-v1 1K rows).
- `run_campaign.py --dry-run` (no device call; ROUNDS=1) on the Pixel file, `-s26-e2b` and `-s26-side-e4b`: the anchor ends `-st`, every
  Gemma 4 line carries the kwargs (flat; side `… -st --chat-template-kwargs '{"enable_thinking":false}' -ngl 99 -fa on -ub 1024 --device
  HTP0` / `GPUOpenCL`), the Pixel skips the two E4B rows.
- Every row compared with its source line by `sed -n` (all SAME). Page cells from P `dist/cells.json` (11:13): S26 llama.cpp E2B / E4B
  short-chat and 1K (b11721 10-18, cpu-capped), Pixel 8a E2B short-chat (13.9, thinking on) and 1K (cpu-capped), S26 llama.cpp-npu / -gpu
  E2B / E4B short-chat (10-11), E2B 1K (10-08), E4B 1K (not measured), S26 2K ladder E2B / E4B × 3 contexts (b8999, 09-20 / 21).

## selftest・validate の末尾
- `nice -n 19 python3 android/bench/selftest.py`: 253 ok, 0 FAIL, last lines `  ok  long-context device-free unit checks` / `selftest OK`;
  the new lines: `ok  campaign T exits 0 (got 0)`, `ok  thinking: Gemma 4 hands the template enable_thinking=false, one shell word (flat and
  side build); Qwen3 hands nothing: […]`, `ok  thinking: conditions.chatMode / thinking per family, …`, `ok  thinking: --dry-run plans the
  flag per family: […]`, `ok  thinking: the family check reads 'gemma-4' in any case, …`, and `ok  CPU llama.cpp legacy records: the key
  layout of 3d5655c (got [])` / `… round-mode records …`.
- `python3 android/bench/test_longctx1024.py`: `Ran 13 tests in 0.256s` / `OK` (before the expected-line edit: FAILED (failures=1) on the
  Gemma 4 E2B row).
- `python3 -m py_compile android/bench/run_cell.py android/bench/selftest.py android/bench/test_longctx1024.py`: OK.
- `python3 scripts/validate_cells.py --require-anchor` on the six committed cells files (Pixel, four S26, ladder): `OK` ×6, `validate rc=0`;
  `validate_cells.py matrices/*.cells` rc 0.
- The other data-pipeline.yml steps (nice 19): validate_cells matrices/*.cells OK; --require-anchor release-regression + anchors OK;
  `android/ddp/selftest.py` "ddp selftest OK (76 checks)" (BENCH_ANDROID_BIN_DIR = an APFS clone of MAIN's android/bin/v0.18.0);
  dashboard_job / session_check / dashboard_post / regression_watch selftests "selftest OK"; autopilot "autopilot selftest OK (58
  checks)"; test_render_rules OK; test_import_native_benchmark OK; py_compile scripts/*.py android/bench/*.py android/ddp/*.py bench OK;
  bash -n OK. Not run: render_leaderboard / render_dashboard --check / build_summary (they read results, which this round does not change).

## 経過
- 11:44 ListAgents (this session = edge-llm-bench-wt-llama-bc [6ce474]); HEAD faea764e, tree clean.
- 11:4x 下見: ROUND13, RUNNER l.600–800 / 850–1080 / 1200–1240 / 1420–1535, parsers (no thinking handling in parse_llama_cli /
  llama_cli_reply), the cells sources, the schema; holds and drivers (none on the phones); the help of the three llama-cli builds; the
  evidence logs.
- 11:5x RUNNER + selftest edits; selftest 253 ok (11:53:58–11:55:49, nice 19). Cells files 3 (rows byte-checked against their sources),
  validate --require-anchor OK. Page cells from P `dist/cells.json` (S26 side-build 1K rows are page cells: listed in the 3rd file).
- 11:5x–12:01 every CI step of data-pipeline.yml (scratchpad `tools/ci_steps.sh`, nice 19): all rc 0 except
  `android/bench/test_longctx1024.py` (it pins the Gemma 4 1K llama-cli line byte for byte; outside the write range). Docs 2 written.
- 12:03 SendMessage: GO request for test_longctx1024.py + premise corrections 2 + the S26 side-build probe. 12:03:52 Pixel 8a hold
  acquired (keeper pid 70665, queue empty, no holder before), probe launch 1 (Gemma 4 E2B short-chat).
- 12:0x supervisor: GO for test_longctx1024.py (same commit) and for the S26 side-build launch. test_longctx1024.py edited: 13 tests OK.
- 12:04:31 Pixel 8a probe done, hold released (2 launches, both PASS as planned). 12:05:14–12:05:27 S26 hold (keeper pid 90872), side-build
  probe launch PASS, hold released. Neither hold file left behind.
- 12:0x supervisor: step 7 through a keeper (`queue_cli.py wait <hold> autopilot_r15_<text|side> <keeper pid>`, then the job with
  `--hold-held-by <keeper pid>`), one slot ≤ 45 min, the asr lane (edge-llm-bench-c0) shares the S26 queue today.
- 12:1x estimate from this morning's job logs: a sitting = the job's anchor phase (`matrices/anchors.cells`: Pixel 12 min, S26 ~10.5 min) +
  the file (anchor row + 3 rounds); a Gemma 4 launch 5.5–7.5 min with its 300 s cooldown → Pixel ~55–60, S26 flat ~90, S26 side ~80 min.
  SendMessage: the three options (keep the files: 2 long S26 slots; one Gemma 4 row per sitting; two rows per sitting).
- 12:1x supervisor: option C — S26 four sittings of one model each (flat E2B → flat E4B → side E2B → side E4B, alternating with the asr
  lane through the queue, no front), the Pixel 8a the current file. Four S26 files written (rows byte-checked, validate OK, dry runs);
  the 4-row `…-s26-side.cells` is superseded: a removal of it was stopped by the tool's safety check (it came in one command with a
  `bash -c` script), so it stays untracked and out of the commit (残した file: 消してよい).
- 12:1x commit (explicit paths), then the "Mac 側 PASS、端末待ち" message.
