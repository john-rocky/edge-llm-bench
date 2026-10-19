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
- 12:19:41 the supervisor merged it into MAIN main (8b898cff; MAIN's checkout on main, clean, LLAMA_THINKING_OFF_FLAGS in run_cell.py,
  the six cells files present). 12:2x go.
- 12:20:17 Pixel 8a hold (keeper pid 69968, queue empty, no holder) → job `pixel8a … --suffix llama-thinkoff --once --hold-held-by 69968`
  (log line: "hold kept by keeper pid 69968 (not acquired / not released by the job)"; thermal status 0; 23.1 GB free), anchor phase.
- 12:20:20 S26 hold (keeper pid 70305, queue empty, no holder) → job `s26 … -s26-e2b.cells --suffix llama-thinkoff-e2b --once
  --hold-held-by 70305` (thermal status 0; 25.0 GB free), anchor phase. Both chains detached (nohup, scratchpad `tools/sitting_r15.sh`).
- 12:30:58 S26 e2b: anchor phase exit 0, admission ADMITTED (anchor nominal, ratio 0.953 vs reference b11721); payload (the file) starts.
- 12:34:59 Pixel 8a: anchor phase exit 0 (14.7 min), admission ADMITTED (anchor nominal, ratio 1.001 vs reference b11721); payload starts.
- 12:35–12:38:01 Pixel 8a off the bus: the payload's first adb call (`run_campaign.py` wait_nominal → `device_probe.thermal_status`,
  `adb -s 4C131JEKB15210 shell dumpsys thermalservice`) read `adb: device '4C131JEKB15210' not found` (one retry, then a Traceback),
  runner exit 1, 0 records, `SESSION.json` admitted=false reason anchor-short, job `=== done: ABORTED (aborted) exit 4`; no post. Keeper
  released the hold 12:38:01. 12:38:35: the Pixel is in neither `adb devices` nor ioreg IOUSB (the S26 and the iPhone are) = off USB
  (unplugged, powered off or rebooting). SendMessage (device incident). adb not restarted: the S26 sitting runs under its hold. A 10-min
  ioreg watch started. First exit 3–6 of the stop condition.
- 12:49:00 the Pixel 8a still absent from ioreg after 10 min: a person has to replug it / check its power. Push notification to the
  user, one line to the supervisor; a 29-min ioreg watch for its return. The S26 e2b sitting runs on (anchor row 3 runs done 12:35, all
  marked cpu-capped on policy6, cpus 6-7, min 3859–4262 / 4742 MHz).
- 12:51 S26 e2b round 1 read: E2B short-chat (03:42:26Z) thinking off, the right reply, `[Start thinking]` 0 — but the caps fell during
  the run (policy0 3628.8 → 2227.2, policy6 4742.4 → 2227.2 MHz; thermal nominal → light), decode 1.0 tok/s (this morning's thinking-on
  sitting: 28.3–28.6), prefill 75.7 (77.4–86.4), elapsed 125.2 s; E2B 1K (03:50:10Z) decode 15.8 (16.3–17.2), caps down to 1785.6 /
  1747.2 MHz. Both cpu-capped >15 %. Not the change: the anchor rows (command unchanged) 98–110 tok/s, the probes at normal rates.
  SendMessage (the flat rows will likely pool into no number; continuing as planned).
- 12:5x supervisor: the flat E2B sitting runs to its end, the next sitting does not start; suspicion: the kwargs (jinja path) slow the
  flat build's llama-cli (the 1.0 tok/s is more than a 2227 MHz cap explains). Do an A/B in an S26 hold (≤ 20 min): the same cell with /
  without the kwargs back to back, llama-cli's own timing lines; side E2B → side E4B after the asr lane's slots, flat E4B at night
  (20:00–01:30) or left to the 02:00 S26 weekly.
- 12:56 the S26 queue: holder = this e2b sitting; 1 asr_sherpa_s26 (12:39), 2 asr_litert_s26 (12:41, edge-llm-bench-c0, ~45 min), both
  keepers waiting. Queued the A/B (`autopilot_r15_ab`, keeper 14552, 3rd; scratchpad `tools/ab_r15.sh`: flat b11721, the runner's
  flags + `-lv 4`, order kw / none / none / kw, each launch after the caps are back at the hardware max and thermal status 0, up to
  240 s). The chain stopper (scratchpad `tools/stop_chain_r15.sh`) kills the chain's #2 queue waiter (`autopilot_r15_text_e4b`, which
  queues behind all three) the moment it appears; the chain then exits through its own cleanup.
- 12:57 round 2 of the e2b sitting: E2B short-chat with the kwargs (03:55:20Z) decode 29.1 tok/s in 7.2 s (prefill 77.6; caps min 3302.4 /
  3648 MHz, thermal nominal → nominal; `[Start thinking]` 0) = this morning's thinking-on 28.3–28.6. SendMessage: the kwargs do not slow
  the flat build; the A/B stays queued unless the supervisor drops it.
- 12:58 supervisor: the A/B dropped (the queue is shared, time is short); order side E2B → side E4B (queue order), flat E4B last, 20+ min
  after the previous sitting and only when cool, else at night (20:00–01:30); one line in ROUND15 on how the gate treated round 1's
  1.0 tok/s run. 12:58:46 the A/B left the queue (its waiter killed; the script released nothing, dequeued itself).
- 12:59:36 a new chain (scratchpad `tools/sitting2_r15.sh`): side E2B (queued 3rd, behind asr_sherpa_s26 and asr_litert_s26), then side
  E4B, then flat E4B as `autopilot_r15_text_e4b_late` with the cool rule (20 min after the previous sitting; in the hold thermal status 0
  and every policy at its hardware max, polled 30 s up to 10 min; not cool = release, SITTING_DEFER). SendMessage: the order runs past
  the launch's 3-hour stop (14:44) — extend, or stop at 14:44 and hand the detached chain over.
- 13:0x supervisor: (1) — the round is extended (waiting in the shared queue is not a stop); run the chain to its end; round close by
  17:00 at the latest, with handoff lines (commands as they are; a live nohup chain's pid and how to stop it) for what remains then
  (a flat E4B moved to the night, the Pixel 8a re-measure if the phone is not back); a post HOLD = one line to the supervisor.
- 13:20:17 S26 flat E2B done: OK exit 0 (admitted, COMPLETED; ratio 0.936); post 13:20:17–13:21:21 PASS ×2, commit 721ee21e. 13:21:22 the old
  chain's #2 waiter (`autopilot_r15_text_e4b`) killed by the stopper, the chain exited through its cleanup (SITTING_FAIL #2 rc=143,
  queue entry gone). 13:21:26 asr_sherpa_s26 took the S26; queue: asr_litert_s26, then autopilot_r15_side_e2b. 13:18 the Pixel 8a still
  absent from ioreg (next watch armed).
- 13:42:52 the Pixel 8a back in ioreg and adb (transport 13; not rebooted: uptime 327236 s; awake, no keyguard, AC powered, 73 %, 27.3 C,
  thermal status 0, the GGUFs on the phone; Pixel queue empty). 13:43:23 Pixel hold (keeper 98147) → job `pixel8a … --suffix
  llama-thinkoff-r2 --once --hold-held-by 98147` (a new campaign name: the aborted one stays as it is), anchor phase.
- 13:55:12 Pixel r2: anchor phase exit 0 (11.8 min), admission ADMITTED (ratio 1.003 vs reference b11721); payload starts.
- 14:00 the S26: asr_litert_s26 holds it since 13:47:51 (asr_sherpa 13:21:26–13:47); autopilot_r15_side_e2b first in line, keeper waiting.
- 14:13 Pixel r2 round 1: E2B 1K run 1 decode 5.0 tok/s, thermal nominal → light, policy4 min 1065 / 2367 MHz (cpu-capped; this morning's
  thinking-on 1K: 8.2–8.4, cpu-capped too).
- 14:29:06 S26 hold (keeper 42286) after the asr lane's slots → job side E2B (`--suffix llama-thinkoff-side-e2b`; thermal status 0, 17.7 GB
  free; the side build on the phone), anchor phase.
- 14:41:05 S26 side E2B: anchor phase exit 0 (12 min), admission ADMITTED (ratio 1.040 vs reference b11721); payload starts. Pixel r2:
  round 2 of 3 complete (~14:38).
- 15:00:11 Pixel r2 done: OK exit 0; post 15:00:11–15:00:12 HOLD: the anchor dir `reference-uncommitted` (its admission reference is the
  aborted sitting's anchor dir `2026-10-19-dashboard-v1-pixel8a-llama-thinkoff-anchor-android`, admitted but never committed: that sitting
  never reached a post), the payload dir PASS; REVIEW.md in both dirs; nothing committed. One line to the supervisor (commit the old
  anchor dir, then re-post). Pixel hold released by the chain (r18 uses the phone next). A Mac quiet window (coreai `_GPU_LOCK`,
  ci-rehearsal timing pid 56582, since 14:58:31) made the PreToolUse hook refuse a python3 read: grep only until it closes.
- 15:02–15:04 the supervisor committed the aborted sitting's anchor dir (afffb3f9, "the anchor phase only") and re-posted r2: PASS ×2,
  commit 2b4b6f37.
- 15:17:21 S26 side E2B done: OK exit 0; post 15:17:21–15:18:21 PASS ×2, bench commit c9fa1590, page commit 00bbbeab (local); post exit 1
  = push_bench refused ("origin/main ec2798fd is not an ancestor of c9fa1590"): ec2798fd is the supervisor's LANE.md commit on top of
  c9fa1590, pushed first (a race, c9fa1590 is in origin through it). One line to the supervisor. 15:18:21 the chain queued side E4B.
- 15:19 the S26 back to the asr lane (asr_litert_s26 since 15:18:24, ~45 min; asr_burst_s26 ~45 min queued at 15:01 ahead of side E4B):
  side E4B expected near 16:50, after the round-close deadline (17:00) = handoff. Live chain: bash 42283, keeper 52905, waiter 52958.
- 15:21 round-close lint PASS on the draft; SPEED_LADDER r15 rows 5–11 added.
- 16:01 asr_burst_s26 took the S26 (asr_litert 15:18–16:01); side E4B first in line; the asr lane queued three more and another lane one
  behind it (16:40). 16:40 round close: `[Start thinking]` counted per campaign, handoff written (the live chain 42283 runs side E4B and,
  later, flat E4B), lint, the round-close commit, the message to the supervisor.

## 計測の結果
Job route from MAIN (8b898cff), BENCH_SITTING=1, each phone's hold taken by a keeper through the shared queue and handed to the job with
`--hold-held-by`. `[Start thinking]` counted in every Gemma 4 run log the campaign holds (quarantined runs included).

| sitting | campaign | records (Gemma 4 rows) | decode tok/s (Gemma 4) | `[Start thinking]` | gate / flags | post | page |
|---|---|---|---|---|---|---|---|
| S26 flat E2B (12:20–13:21) | `2026-10-19-dashboard-v1-s26-llama-thinkoff-e2b-android` (+ `-anchor-`; admitted, anchor ratio 0.953 / 0.936) | anchor 3 + E2B short-chat 3 (+ 3 quarantined) + E2B 1K 3 | short-chat 28.9 / 28.7 / 28.8 (quarantined 1.0 / 29.1 / 28.3), 1K 15.8 / 16.0 / 16.4 | 0 in all 9 Gemma 4 logs; thinking false, the new chatMode | COLLAPSE on short-chat after round 3 → quarantine + 180 s + block re-run; every Gemma 4 run cpu-capped (short-chat policy6 min 3129.6–3398.4 / 4742.4 MHz, 1K down to 1785.6 / 1747.2) | PASS ×2, commit 721ee21e ("cells with a number before and none now: 0, the reverse: 0") | S26 llama.cpp E2B short-chat and 1K: this campaign, "cpu-capped >15 % (3 of 3 runs)", no number (as before: the 10-19 05:52 sitting's were cpu-capped too) |
| Pixel 8a (12:20–12:38) | `2026-10-19-dashboard-v1-pixel8a-llama-thinkoff-android` (+ `-anchor-`, admitted 1.001) | 0 (the phone left USB at the payload's first adb call) | — | — | runner exit 1 (adb "device not found"), job exit 4 ABORTED | none (exit ≠ 0) | unchanged (the 10-19 09:45 thinking-on sitting: E2B short-chat 13.9, 1K cpu-capped) |
| Pixel 8a r2 (13:43–15:00) | `2026-10-19-dashboard-v1-pixel8a-llama-thinkoff-r2-android` (+ `-anchor-`; admitted 1.003) | anchor 3 + E2B short-chat 3 (+ 3 quarantined) + E2B 1K 3; E4B rows skipped (exclude-on) | short-chat 12.8 / 13.0 / 13.2 (quarantined 12.3 / 13.1 / 8.4), 1K 5.0 / 5.8 / 7.9 (this morning thinking on: 13.9 median; 8.2–8.4) | 0 in all 9 Gemma 4 logs; thinking false; anchor Qwen3 1 each (template-default) | COLLAPSE on short-chat → block re-run; every Gemma 4 run cpu-capped (policy4 down to 1065 / 2367 MHz on the 1K) | HOLD `reference-uncommitted` on the anchor dir (payload dir PASS); the supervisor committed the aborted sitting's anchor (afffb3f9) and re-posted: PASS ×2, commit 2b4b6f37 | Pixel 8a llama.cpp E2B short-chat 13.1 (n=2, this campaign); 1K "cpu-capped >15 % (3 of 3 runs)", no number |
| S26 side E2B (14:29–15:18) | `2026-10-19-dashboard-v1-s26-llama-thinkoff-side-e2b-android` (+ `-anchor-`; admitted 1.040) | anchor 3 + npu 3 + gpu 3 | npu 28.9 / 29.9 / 30.3, gpu 26.3 / 27.0 / 27.4 (10-11 thinking on, page: npu 28.3, gpu 21.6) | 0 in all 6 logs; thinking false; text check PASS ×6 | cpu-capped marks (the npu / gpu arms pool at any fall) | PASS ×2, commit c9fa1590 (push refused: a race with the supervisor's ec2798fd on top of it) | S26 llama.cpp-npu E2B short-chat 29.9 (n=3), llama.cpp-gpu 26.65 (n=2), this campaign |

- `[Start thinking]` per campaign at the round close (16:40, `grep -c` over every `llama.cpp*gemma-4*.log` of the dir, quarantined runs'
  logs included): S26 flat E2B 9 logs / 0, Pixel 8a r2 9 / 0, S26 side E2B 6 / 0; the aborted Pixel campaign has no Gemma 4 log. The
  anchors' Qwen3 logs keep theirs (template default, 1 per log).
- How the gate treated round 1's 1.0 tok/s run (supervisor's line): after round 3 the capture gate printed `gate: COLLAPSE 4 — quarantine +
  cooldown 180s, re-run once` / `gate retry llama.cpp unsloth/gemma-4-E2B-it-GGUF short-chat verdict=COLLAPSE 4 (block re-run, not
  interleaved)`; the cell's three runs (1.0 / 29.1 / 28.3, all cpu-capped) went to `*.json.attempt1` (kept on disk, out of every pool), the
  block re-run gave 28.9 / 28.7 / 28.8, all three cpu-capped above the 15 % line (policy6 −28 to −34 %), so no number pools: the page cell
  reads "cpu-capped >15 % (3 of 3 runs)" with no number, now from the thinking-off campaign.

## commit
- **627b007b** (branch `android-llama-thinking`, not pushed, not merged by this round; author / committer rockyshikoku@gmail.com, no
  attribution lines): `android/bench/run_cell.py`, `android/bench/selftest.py`, `android/bench/test_longctx1024.py`,
  `methodology/fairness-rules.md`, `docs/dashboard-cells-v1.md`, `matrices/dashboard-llama-thinkoff-android.cells`,
  `…-s26-e2b.cells`, `…-s26-e4b.cells`, `…-s26-side-e2b.cells`, `…-s26-side-e4b.cells`, `…-ladder-android.cells`, K `ROUND15.md`.

## 提案
1. **a mode check in the post step**: `scripts/session_check.py` reads each llama.cpp record's reply from its run log; a Gemma 4 GGUF
   record whose reply opens with `[Start thinking]` while `conditions.thinking` is false (or has no `thinking` key: every Android record
   before 2026-10-19) could HOLD as a mode mismatch, so the page never shows a thinking-on number for a family the other arms run off.
2. **the flat build's reply text**: the side build's records keep the reply (`provenance.decodedText`, text-checked); the flat build's
   records keep nothing but the rate, so this mode change was invisible on the page for two weeks. Storing the flat reply the same way
   (parsers.llama_cli_reply on the console) would let the page and the checker see it.
3. **schema wording**: `schema/result.v1.json` `conditions.thinking` names the Mac / iPhone llama.cpp only; add "Android llama.cpp
   (android/bench/run_cell.py, 2026-10-19): false for Gemma 4 GGUF rows, "template-default" otherwise" (outside this round's write range).
4. **`conditions.chatTemplate` on Android**: the help says `--jinja` is on by default on both builds, so the Android rows render the GGUF's
   own template like the Apple adapter's `jinja`; stamping `chatTemplate: "jinja"` needs one look at a -lv 4 log for the template line
   first (not checked in this round).
5. **the listed rows**: `matrices/dashboard-llama-thinkoff-ladder-android.cells` — the side build's E2B 1K page cells still show the 10-08
   thinking-on numbers (E4B 1K was never measured); the S26 2K ladder too (b8999, 09-20 / 21).

## 訂正
- launch 背景: "`--reasoning-budget` は help に無い(grep 0 件)" — it is there on all three builds (Pixel / S26 flat b11721 l.513, S26 side
  b11469 l.506, default -1), and so is `-rea, --reasoning [on|off|auto]` (default auto, "detect from template"). Evidence: 下見 (the help
  lines). The switch stayed the template variable (supervisor 12:0x: "手は kwargs のまま").
- launch 手順 5: the second file as "anchor + npu-v1-android-s26-short の Gemma 4 の 4 行" and one flat file for both phones — the job's
  sitting (anchor phase 10.5–12 min + the file) made those 80–90 min on the S26 against a 45-min slot; supervisor's option C: four S26
  files of one model each, the Pixel 8a keeps the flat file. Evidence: `MAIN/logs/dashboard-job/2026-10-19-pixel8a-llama-b11721.byhand.out`
  (09:45:24 anchor phase → 09:57:35), the record times of `MAIN/results/raw/2026-10-19-dashboard-v1-s26-llama-b11721-android/`.
- launch 手順 5 the ladder list "protocol1024 / longctx1024 / longctx-v1": the protocol1024 rows are llama-bench (no prompt, no template:
  unchanged by the fix) and the longctx1024 Gemma 4 rows are byte-identical to the text-v1 1K rows (already in the page-cell files); the
  list holds the side build's 1K rows (page cells, by hand per `dashboard-npu-v1-android-s26-short.cells`) and the S26 2K ladder.
  Evidence: P `dist/cells.json` (11:13), the cells files' lines (ROUND15 cells).
- launch 手順 7: the job line without a keeper — the supervisor's 12:0x addition: the keeper takes the hold through the shared queue and
  hands it to the job with `--hold-held-by`.
- launch 受け入れ基準 1 "RUN_OK": no such string in the repo; the runner prints `run 1/1 OK decode=… thermal=…` per run. Read as that line +
  `EXIT_CODE=0` + a record. Evidence: scratchpad `logs/probe-pixel8a.out`.
- write range: `android/bench/test_longctx1024.py` pins the 1K llama-cli line byte for byte (CI step); GO 12:0x, same commit.

## 罠と袋小路
- `rm <file> && bash -c '<script>'` in one Bash call is stopped by the tool's removal safety check (it cannot read the `-c` script), and
  the check forbids re-issuing the removal another way: keep `rm` out of compound commands, or leave the file (the superseded
  `…-s26-side.cells` stays untracked).
- A loop `while read …; done <<< "$PLAN"` around a job that runs adb loses its remaining lines (adb reads stdin): loop over arrays and give
  every child `< /dev/null` (scratchpad `tools/sitting_r15.sh`).
- A keeper `sleep N &` outlives a killed script and keeps a live-owned hold for up to N s; a keeper that polls the script's pid
  (`while kill -0 $$; do sleep 5; done`) dies with it, leaving a dead owner (= a stale hold the next acquirer clears).
- The job's sitting starts with its own anchor phase (`matrices/anchors.cells`, 10.5–12 min on the phones) before the file's anchor row: a
  45-min slot holds the anchor phase, the anchor row and three rounds of one Gemma 4 row (cooldown 300 s), not two.
- zsh in the Bash tool: `echo =====` fails ("(eval):1: ==== not found"), an unmatched glob aborts the command ("no matches found"), and a
  `cd` moves the session's cwd: quote, run loops under `bash -c`, use absolute paths.
- An Android selftest of another worktree (fake adb, temp dir) shows up in `ps` as `run_campaign.py` / `run_cell.py`: read its argv (a
  temp-dir cells path, `fake/gguf`) before calling a phone busy.
- A job whose post commits while another session commits and pushes MAIN on top of that commit reads "push refused: origin/main … is
  not an ancestor of …" and exits 1 with the bench commit already in origin through the other push: read `git log` before calling it a
  failed post (15:18, c9fa1590 under ec2798fd).
- Inside another lane's Mac quiet window the PreToolUse hook refuses any `python3` command, even a JSON read: read records with grep / jq
  (`jq -r '.cells[] | select(…)' dist/cells.json`) until the window closes.
- A sitting stopped by a phone that left USB leaves an admitted anchor dir no post committed; the re-measure's admission takes it as its
  reference, so the re-measure's post holds on `reference-uncommitted` until that dir is committed (the Pixel r2, 15:00).

## op と delegate の観察
- Not an op / delegate round (no conversion, no backend change). Measured on the S26 side build b11469 (Hexagon HTP0, `-ngl 99 -fa on -ub
  1024`): Gemma 4 E2B `offloaded 36/36 layers to GPU`, `using device HTP0 (Hexagon)`, the same device lines with the template variable as
  without. Fallback counts, fp16 / fp32 deltas: none measured (なし).

## 使った環境
- Mac Studio M4 Max (Mac16,9), macOS 27.0 (26A428); Python 3.14.6 (system; no venv); adb on the host (one server, never restarted in
  this round). No build. The Mac's own measurements (the 18 Pro / M4 Max sittings, a coreai quiet window from 14:58) ran beside this
  round: every python selftest ran under `nice -n 19`, the post-14:58 reads used grep / jq (the PreToolUse hook refuses python3 inside
  another lane's quiet window).
- Pixel 8a 4C131JEKB15210 (akita, Tensor G3, Android 16, patch 2026-05-05), flat llama.cpp b11721 ff5a23376 (`llama-cli` version 0.7.0-dev);
  mask f0. Off USB 12:35–13:42 (not rebooted: uptime 327236 s at 13:43; replugged by the user).
- Galaxy S26 RFGL80R6A6H (SM-S942Q, SM8850, Android 16, patch 2026-08-05), flat b11721 ff5a23376 and the side build b11469-snapdragon
  ad2156533 (`engines/b11469-snapdragon`, Hexagon HTP0 / Adreno OpenCL); no mask. Shared queue with the asr lane (edge-llm-bench-c0).
- Holds (all through `queue_cli.py` keepers, released by the scripts): Pixel 12:03:52–12:04:31 (probe, keeper 70665), 12:20:17–12:38:01
  (sitting, keeper 69968), 13:43:23–15:00:12 (r2, keeper 98147); S26 12:05:14–12:05:27 (probe, keeper 90872), 12:20:20–13:21:21 (flat
  E2B, keeper 70305), 14:29:06–15:18:21 (side E2B, keeper 42286), then side E4B / flat E4B by the live chain (handoff).
- MAIN 8b898cff (the merge of 627b007b) for every sitting; the job's post committed 721ee21e (S26 flat E2B), c9fa1590 (S26 side E2B);
  the supervisor committed afffb3f9 + 2b4b6f37 (Pixel). LiteRT-LM binaries for the DDP / autopilot selftests: an APFS clone of MAIN's
  `android/bin/v0.18.0` in the scratchpad.

## 残した file
- Committed (627b007b): `android/bench/run_cell.py`, `android/bench/selftest.py`, `android/bench/test_longctx1024.py`,
  `methodology/fairness-rules.md`, `docs/dashboard-cells-v1.md`, six `matrices/dashboard-llama-thinkoff-*.cells`, K `ROUND15.md`; the
  round-close commit adds this file's later sections and K `SPEED_LADDER.md` (the r15 ladder).
- REPO, untracked: `results/raw/2026-10-19-probe-thinkoff-pixel8a-android/` (2 probe records + logs),
  `results/raw/2026-10-19-probe-thinkoff-s26-side-android/` (1 record, log, decoded text, THERMAL_GATE.txt) — evidence quoted above;
  消してよい after review, never into the summary. The superseded 4-row `matrices/dashboard-llama-thinkoff-s26-side.cells` was gone by
  16:4x (removed by a person); the dropped A/B's empty dir `results/raw/2026-10-19-probe-thinkoff-ab-s26-android/` removed (rmdir).
- MAIN (written by the job route): the campaign dirs `2026-10-19-dashboard-v1-{pixel8a-llama-thinkoff,pixel8a-llama-thinkoff-r2,
  s26-llama-thinkoff-e2b,s26-llama-thinkoff-side-e2b}{,-anchor}-android` (committed) and, from the live chain, `…-s26-llama-thinkoff-side-e4b…`
  / `…-s26-llama-thinkoff-e4b…`; `logs/dashboard-job/2026-10-19-{pixel8a-llama-thinkoff,pixel8a-llama-thinkoff-r2,s26-llama-thinkoff-e2b,
  s26-llama-thinkoff-side-e2b}.byhand.out` (+ side-e4b / e4b later).
- Scratchpad of this session (消してよい once the chain is done): `tools/ci_steps.sh`, `tools/probe_r15.sh`, `tools/sitting_r15.sh`,
  `tools/sitting2_r15.sh` (the live chain's script), `tools/stop_chain_r15.sh`, `tools/ab_r15.sh` (dropped A/B), `tools/check_r15.py`,
  `logs/` (CI, probes, chains), `android-bin/` (APFS clone of MAIN's LiteRT-LM v0.18.0 binaries).

## 引き継ぎ(handoff at the round close, 16:4x)
1. **Live S26 chain** (nohup, outlives this session): bash pid **42283**, started 12:59:36 from this worker's scratchpad
   (`tools/sitting2_r15.sh s26 <side-e2b> <side-e4b> <flat-e4b>:cool`; its lines `SITTING_*` in the scratchpad `logs/sitting2-s26.out`).
   At 16:40: side E2B done; **side E4B** first in the S26 queue (`autopilot_r15_side_e4b`, keeper 52905, waiter 52958) behind
   asr_burst_s26 (holder since 16:01); then **flat E4B** (`autopilot_r15_text_e4b_late`): queued 20 min after side E4B ends, behind
   whatever is queued then (at 16:40: asr_qnn_s26, asr_litert_s26, asr_fix_s26, rn-litert-r2a-s26), and in the hold it checks thermal
   status 0 and no cpufreq cap (every 30 s, up to 10 min) before the job, else releases and prints `SITTING_DEFER`. Each sitting runs
   `BENCH_SITTING=1 python3 scripts/dashboard_job.py s26 --cells matrices/dashboard-llama-thinkoff-s26-side-e4b.cells --suffix
   llama-thinkoff-side-e4b --once --hold-held-by <keeper pid>` (then `-s26-e4b.cells --suffix llama-thinkoff-e4b`) from MAIN; job logs
   `MAIN/logs/dashboard-job/2026-10-19-s26-llama-thinkoff-side-e4b.byhand.out` / `…-e4b.byhand.out`; the post runs inside the job (PASS →
   local commit; HOLD → REVIEW.md in the dir, the job's exit 0 stands).
2. **Stop it cleanly, only between sittings**: `pkill -f 'queue_cli.py wait .*autopilot_r15_side_e4b'` while side E4B waits, or
   `pkill -f 'queue_cli.py wait .*autopilot_r15_text_e4b_late'` while flat E4B waits; during the 20-min pause before flat E4B,
   `kill 42283` (nothing is held then). The chain prints `SITTING_FAIL` / `SITTING_EXIT` and leaves through its own cleanup (dequeue,
   keeper). While a sitting runs (`SITTING_HOLD` printed, no `SITTING_JOB_RC` yet) let the job end: killing 42283 then releases the S26
   under a running job.
3. **Flat E4B by hand** if the chain printed `SITTING_DEFER` or was stopped (night window 20:00–01:30), from MAIN:
   ```
   cd ~/code/edge-llm-bench; H=~/code/litertlm-convert/community_accel_work; HOLD=$H/s2_npu_sweep/.device_hold
   bash -c "while kill -0 $$ 2>/dev/null; do sleep 5; done" & K=$!
   python3 $H/queue_cli.py enqueue $HOLD autopilot_r15_text_e4b_night edge-llm-bench-55 60
   python3 $H/queue_cli.py wait $HOLD autopilot_r15_text_e4b_night $K && BENCH_SITTING=1 python3 scripts/dashboard_job.py s26 --cells matrices/dashboard-llama-thinkoff-s26-e4b.cells --suffix llama-thinkoff-e4b --once --hold-held-by $K
   python3 $H/hold_cli.py release $HOLD $K; kill $K
   ```
   A suffix whose sitting already started and stopped needs a new one (`llama-thinkoff-e4b-r2`), and its admission reference must be
   committed first (the Pixel r2 HOLD of 15:00: `reference-uncommitted`).
4. **After the last sitting**: `grep -c 'Start thinking'` over `MAIN/results/raw/2026-10-19-dashboard-v1-s26-llama-thinkoff-{side-e4b,e4b}-android/app-path-android/llama.cpp*gemma-4*.log`
   (expect 0 each) and the post rows in `MAIN/logs/dashboard-job/autopilot-ledger.tsv`; the SPEED_LADDER r15 rows for E4B.
5. **Not run (the supervisor's decision)**: `matrices/dashboard-llama-thinkoff-ladder-android.cells` — the side build's E2B / E4B 1K
   rows (by hand) and the S26 2K ladder (round mode).
6. **Pixel 8a**: done (r2, commit 2b4b6f37); hold free (r18 next).
