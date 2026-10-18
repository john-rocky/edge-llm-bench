# Round r5 — D6 DDP weekly slot (stage 4) — worker `edge-llm-bench-wt-autopilot-c1 [c82e21]` (Opus 5.5), started 2026-10-18 22:00 JST

Supervisor: `edge-llm-bench-55 [4f120b]`. cwd ~/code/edge-llm-bench-wt-autopilot, branch bench-autopilot, HEAD 53b9ba1d at start. Launch: the r5 prompt pasted into this tab (~/code/standup/launch/2026-10-18-autopilot-ddp-slot-opus-r5.md per LANE.md). Added by the supervisor at 22:0x (SendMessage): environment.lock.json `arms.litert-lm.mac`, session_check `registry_pin` for the Mac, and a re-check of the committed 88 dirs and the main tree's Mac backlog dirs.

## 下見

- `date` 22:00:16 (round start), 22:10:36 (doctor); `df -g ~`: 598 GB available of 1858.
- `BENCH_ANDROID_BIN_DIR=~/code/edge-llm-bench/android/bin ./bench doctor --platform ddp`: `ok gcloud` (~/google-cloud-sdk/bin/gcloud), `ok gcloud sign-in`, `ok huggingface_hub 1.8.0`, `ok ddp engine files v0.18.0: 9 files = android/engine-pins.json, in ~/code/edge-llm-bench/android/bin/v0.18.0`, `ready`. The worktree has no `android/bin` (the main tree's is read through BENCH_ANDROID_BIN_DIR).
- `gcloud auth list`: one credentialed account, active (the address not copied here). Google Cloud SDK 587.0.0; python 3.14.6.
- `android/ddp/devices.json` m1q-36: `{"scheduleKey": "s26", "display": "Galaxy S26", "product": "m1q", "cpucapWaitSeconds": 0}`, `_note`: no cap wait (D14): in the 2026-10-15 slice (session-9002dfea, 8 SM-S942U1 units) all 24 runs started with policy0 at 3187/3629 MHz and policy6 at 3398/4742 MHz; the 300 s wait timed out before every run (2 h of device time); every record carries cpu-capped-at-start.
- The 10 DDP dirs of 2026-10-16 (`results/raw/2026-10-16-dashboard-v1-s26-0180-s{3,4,9..16}-ddp-m1q-36-android`, commit d6077c6b): no SESSION.json in any (a by-hand `bench matrix --ddp`, not a job sitting; the checker reads them as kind `DDP` -> `not-job` HOLD today), 54 records (s3 6, s4 12, s9 3, s10 3, s11 6, s12 6, s13 3, s14 3, s15 6, s16 6), no ledger line. One Device Run session each, every job PASSED. From ddp/session-1.json (createTime -> sessionReport.endTime; device-min = the executions' start -> end):

| slot | session | rows | created -> ended (UTC) | wall min | device-min | records |
|---|---|---|---|---|---|---|
| s3 | session-b6ed03e6 | Qwen3 1.7B short-chat cpu + gpu | 09:24:57 -> 09:36:56 | 12.0 | 15.2 (cpu 9.4, gpu 5.8) | 6 |
| s4 | session-46a207b2 | Qwen3 1.7B 1K cpu + gpu | 09:37:50 -> 09:48:07 | 10.3 | 14.2 (7.9, 6.3) | 12 |
| s9 | session-7bbb3e56 | Qwen3 4B short-chat cpu | 09:24:57 -> 09:46:02 | 21.1 | 17.8 | 3 |
| s10 | session-58e76ce1 | Qwen3 4B short-chat gpu | 09:55:34 -> 10:13:02 | 17.5 | 15.2 | 3 |
| s11 | session-cdff597f | Qwen3 4B 1K cpu | 10:13:35 -> 10:39:22 | 25.8 | 22.9 | 6 |
| s12 | session-37d1326b | Qwen3 4B 1K gpu | 10:40:01 -> 10:56:48 | 16.8 | 14.2 | 6 |
| s13 | session-b3612616 | Gemma 4 E4B short-chat cpu | 09:29:04 -> 09:47:43 | 18.7 | 13.9 | 3 |
| s14 | session-033e47cf | Gemma 4 E4B short-chat gpu | 09:48:43 -> 10:04:16 | 15.6 | 12.8 | 3 |
| s15 | session-f2457188 | Gemma 4 E4B 1K cpu | 10:05:09 -> 10:20:51 | 15.7 | 12.6 | 6 |
| s16 | session-7d97f990 | Gemma 4 E4B 1K gpu | 10:21:37 -> 10:37:04 | 15.5 | 12.5 | 6 |

  Total 151.4 device-min for 12 jobs; three streams ran side by side (s3-s4, s9-s12, s13-s16): 09:24:57 -> 10:56:48 UTC = 92 min wall. The two jobs of one session started in the same second (s3: 09:25:03.411 / .416): a session's jobs run side by side on several units.
- The summary's rows of those dirs: device `SM-S942U1 (DDP m1q-36)` (build_summary's lab-unit string = P's STAND_IN key), engine v0.18.0, `cpu_capped` true on every row, cpu_cap_drop_pct 55.5-68.4 on the CPU rows (past the 15 % line: no number) and 28.3-58.3 on the GPU rows (an exempt arm: pooled, marked); prompt tokens Qwen3 short-chat 19, Gemma 4 short-chat 20, 1K 1338 (Qwen3) / 1106 (Gemma 4); text check PASS on every 1K row (short-chat rows carry none).
- The weekly set's Android LiteRT-LM rows: 20 in matrices/dashboard-text-v1.cells (lines 60-61, 63-64, 67-68, 70-71, 76-77, 79-80, 84-85, 87-88, 92-93, 95-96), the same 20 byte for byte in the split files a + b1 + b2 (diff: identical). The DDP plan over them (`bench matrix … --ddp m1q-36 --dry-run`): 16 jobs in 2 sessions, 4 skipped (the Qwen3 0.6B rows' exclude-on=pixel8a,s26), 17 upload candidates 12.09 GB, no model uncached in the local HF cache; run_ddp's own estimate 622.6 device-min (8 jobs at its 600 s default: "no local run at v0.18.0" — it leaves DDP records out of its basis).
- Every model blob of the plan (by sha256) was pushed by an earlier committed DDP plan: Qwen3_1.7B 362ec1c9 (10-15 slices, 5 plans), Qwen3-1.7B_dynamic_wi4b32 2a72330b (5), gemma-4-E2B-it 18193810 (10-15 slices on akita-35 and m1q-36), qwen3_4b_mixed_int4 569fe029 (10-16 s9-s12), gemma-4-E4B-it 0b2a8980 (10-16 s13-s16).
- The supervisor's addition, read: the Mac backlog dirs of 10-12 / 10-16 in the main tree are 5, not 4 (all untracked): `2026-10-12-dashboard-v1-m4max-anchor-mac` (admitted, 3 LiteRT-LM records), `2026-10-12-dashboard-v1-m4max-mac` (admitted, 40), `2026-10-16-dashboard-v1-m4max-anchor-mac` (ABORTED anchor-collapse, 3), `2026-10-16-dashboard-v1-m4max-r2-anchor-mac` (admitted, 3), `2026-10-16-dashboard-v1-m4max-r2-mac` (TIMEOUT anchor-short, 68); every LiteRT-LM record stamps `v0.18.0` / `CLiteRTLM_mac.xcframework.zip@v0.18.0`. The committed summary's Mac LiteRT-LM rows read v0.16.0 through 2026-10-09. The main tree's vendored `ios/BenchmarkApp/Vendored/LiteRT-LM/Package.swift` (not tracked) points both binaryTargets at releases/download/v0.18.0 (lines 39, 46). iPhone 18 Pro (iPhone19,2) records: v0.16.0 on 10-08, 10-15 (+ r2), 10-17 (+ r2) (main tree, untracked). The committed iPhone 17 Pro (iPhone18,1) sitting `2026-10-17-dashboard-v1-iphone17pro-0180-aa-i1{-anchor,}-ios` stamps v0.18.0 (21 records). Committed dashboard dirs: 111, of them 88 with SESSION.json.

## 設計

```
schedule.json devices.s26-ddp  {platform ddp, display "Galaxy S26 (DDP m1q-36)", identifier "SM-S942U1 (DDP m1q-36)"
                                (build_summary's lab-unit device string = P's STAND_IN key), ddp_id m1q-36,
                                cells matrices/dashboard-ddp-v1-android-s26.cells, expected_hours 1.5, timeout_hours 5}
switch.json                    + ddp_weekly true, ddp_max_sessions 16 (push / publish keys unchanged, all false)

dashboard_job.py main()
  explicit `s26-ddp`  -> device lock -> ddp_slot()                      (no retake, no busy poll, one attempt)
  auto                -> the attached device as before (resolve_device: a ddp entry is state "ddp", never ranked)
                      -> its ledger line, done line, post
                      -> release that device's lock -> ddp_after()      (unless --no-ddp)
  ddp_after()   per ddp entry: ddp_due() -> `ddp: <key> (<display>): <due | done this week | off | tried … | by hand>`
                due -> its device lock -> ddp_slot()
  ddp_due()     not due: auto false / switch.ddp_weekly not true / an admitted session since Monday (device_sessions)
                / ddp_tried(): a sitting since Monday whose SESSION.json ran Device Run sessions and is not admitted
  ddp_slot()    ddp_sitting() -> ledger line -> done line -> post_sitting(+ post_args: --post-page-out, --no-page-commit)
  ddp_sitting() switch on -> the dir holds no sitting already (else --suffix) -> ddp_doctor() (doctor.check_ddp alone)
                -> ddp_plan() (`bench matrix <cells> --ddp <id> --dry-run`: jobs, sessions, skips, uploads, uncached)
                -> sessions <= ddp_max_sessions (else CONFIG, nothing started)
                -> run_matrix(ddp=<id>): gtimeout timeout_hours `bench matrix <cells> --ddp <id> --campaign <date>-dashboard-v1-<key>-<id>`
                -> ddp_facts() (ddp/session-<n>.json: session ids, jobs, device-min) + the summary's rows of the campaign and identifier
                -> SESSION.json {phase payload, platform ddp, admitted = records written, reason DDP_REASON, anchor null,
                   cells_expected = the plan's jobs, cells_with_records, ddp {id, sessions, jobs, device_minutes, results, plan}}
                -> render_dashboard; exit 0 / 6 timeout / 5 no record
session_check.py   kind_of: a DDP dir with the job's SESSION.json = "job payload (ddp)" -> the job-session rules;
                   check_pair n/a (a note), the lab unit's caps a note; check_files treats it as DDP (logcat rules)
                   registry_at / registry_pin: arms.litert-lm.mac (REGISTERED_LATER, block_applies on sitting_day =
                   the campaign name's date) for the Mac, default_tag for the iPhones (supervisor's addition)
dashboard_post.py  sitting_facts + device_text / ddp_text: a lab unit's sitting named in the commit and page messages
regression_watch   unchanged: page_rows already leaves out the stand-in device's rows (no DDP series, docs "later")
```

Places that depart from the launch (reasons in 訂正): the preflight runs doctor.py's check_ddp alone, not `bench doctor --platform ddp` whole; "超えたら sitting を切る" = the plan's sessions over the cap start nothing (run_ddp has no partial run); one billed attempt a week (a sitting that ran sessions and was not admitted ends the week's slot too); the code was committed before the real sitting (dad937b1, f36512ae) so the post's commit sits on the code that made it; dashboard_post.py changed (its messages named a DDP sitting "anchor phase ? committed before").

## Mac 側 PASS

(a) selftests, python 3.14.6 in the worktree and python 3.11.13 under `env -i` on a shallow clone of dad937b1 (the CI job's steps: validate_cells over matrices/*.cells and --require-anchor, build_summary + `git diff --exit-code results/summary/`, render_leaderboard, `render_dashboard.py --check`, test_render_rules, test_import_native_benchmark, the four selftests, android/bench/selftest.py, android/ddp/selftest.py with the main tree's engine files, py_compile, bash -n): every step exit 0. `dashboard_job_selftest.py` 86 checks (60 + 26: the lab unit no candidate, auto --dry-run's order (the attached sitting, its post, then `ddp:`, the unit's bench matrix --ddp line and post), timeout_hours, the plan logged, a firing with no device, --no-ddp, switch off by auto and by hand, the explicit key, the cap, the doctor FAIL, ddp_due (due / done / tried / off / by hand), ddp_tried, a sitting against a fake bench in a temp ROOT: SESSION.json, ddp facts with nanosecond times, cells, the ledger line, the post with --page-out / --no-page-commit, the same-day refusal, a sitting with no record: DEVICE and no post; a gcloud trap first on PATH never called), `session_check_selftest.py` 37 (+ the DDP job sitting PASS with the pair rules n/a, its execution-level logcat FAIL and partial HOLD; the Mac block: after since stamping default_tag HOLD naming arms.litert-lm.mac, the day before since PASS — skipped while the lock change was uncommitted, run after dad937b1), `dashboard_post_selftest.py` 45 (+ the DDP commit and page messages), `regression_watch_selftest.py` 50.

(b) `BENCH_ANDROID_BIN_DIR=~/code/edge-llm-bench/android/bin python3 scripts/dashboard_job.py s26-ddp --dry-run --once` (22:35, an adb and an xcrun trap first on PATH: neither called), exit 0:

```
=== slot s26-ddp (Galaxy S26 (DDP m1q-36), DDP m1q-36) campaign 2026-10-18-dashboard-v1-s26-ddp-m1q-36 [dry-run]
doctor (check_ddp): ready
  OK    gcloud  ~/google-cloud-sdk/bin/gcloud
  OK    gcloud sign-in
  OK    huggingface_hub  1.8.0
  OK    ddp engine files  v0.18.0: 9 files = android/engine-pins.json, in ~/code/edge-llm-bench/android/bin/v0.18.0
ddp plan: 16 jobs in 2 Device Run sessions on m1q-36 (engine v0.18.0), 4 rows skipped; 17 upload candidates, 12.09 GB (the run uploads what the bucket lacks); run_ddp's estimate 622.6 device-min; cap 16 sessions (ops/autopilot/switch.json ddp_max_sessions)
  ddp skip: litert-lm-cpu litert-community/Qwen3-0.6B short-chat: hub-bundle-chat-template-predates-litert-lm-018-prompt-dropped-issue-3688 (exclude-on s26)
  (… the gpu short-chat and the two 1K Qwen3 0.6B rows, the same reason)
plan:
$ gtimeout --kill-after=60 18000 ~/code/edge-llm-bench-wt-autopilot/bench matrix matrices/dashboard-ddp-v1-android-s26.cells --ddp m1q-36 --campaign 2026-10-18-dashboard-v1-s26-ddp-m1q-36   env:
  SESSION.json would read admitted true once the sitting writes records (ddp lab unit: no session anchor; each run carries its cap marks and the text check), anchor null, ddp {id, sessions, jobs, device_minutes}
=== done: OK (ok) exit 0
post: $ …/python3.14 ~/code/edge-llm-bench-wt-autopilot/scripts/dashboard_post.py results/raw/2026-10-18-dashboard-v1-s26-ddp-m1q-36-android   [dry-run: printed, not run]
```

  Session 1 = jobs 1-8 (Qwen3 1.7B and Gemma 4 E2B: short-chat and 1K, cpu and gpu), session 2 = jobs 9-16 (Qwen3 4B, Gemma 4 E4B); runs=3 each, executionTimeout 3600 s per job (run_ddp's default: `bench matrix --ddp` passes no --job-timeout).

(c) `PATH=<scratchpad>/r5/fakebin:<scratchpad>/r5/trapbin:$PATH python3 scripts/dashboard_job.py auto --dry-run` (22:35, the fake adb lists the S26 and the Pixel 8a; xcrun trapped): the real schedule, exit 5 (the Mac's own preflight: no yardstick in the worktree), then the lab unit's line:

```
auto @ 2026-10-18 22:35 (week of Mon 2026-10-12):
  m4max        candidate  last admitted 2026-10-06 21:52
  s26          done       admitted 2026-10-15 22:03 results/raw/2026-10-15-dashboard-v1-s26-0180-s8b-android
  pixel8a      done       admitted 2026-10-15 19:32 results/raw/2026-10-15-dashboard-v1-pixel8a-0180-p4-rt-android
  iphone17pro  by-hand    auto: false, by hand only; last admitted 2026-10-17 04:11
  iphone18pro  waiting    outside its window 05:00-08:00; never measured
  s26-ddp      ddp        lab unit, decided after the attached device's sitting; last admitted 2026-10-16 19:55
  -> m4max
=== slot m4max (Mac Studio (M4 Max), mac) attempt 1 … DEVICE: bench doctor --platform mac FAILED: (no Vendored engines, no yardstick in this worktree)
  -> no device to measure now
=== done: DEVICE (m4max: …) exit 5
ddp: s26-ddp (Galaxy S26 (DDP m1q-36)): done this week: admitted 2026-10-16 19:55 results/raw/2026-10-16-dashboard-v1-s26-0180-s12-ddp-m1q-36-android
```

  The same with `--schedule <scratchpad>/r5/schedule-ddp-due.json` (the entry's identifier changed so the unit reads never measured): after `=== done: DEVICE … exit 5`: `ddp: s26-ddp (Galaxy S26 (DDP m1q-36)): due: never measured, none since Mon 2026-10-12`, `ddp: s26-ddp: its sitting starts now (log 2026-10-18-s26-ddp.log)`, the sitting's lines as in (b), `=== done: OK (ok) exit 0`, its post line, `ddp: s26-ddp: OK, exit 0`. The one xcrun call the trap caught (`xcrun devicectl list devices`) is the Mac sitting's own preflight (`bench doctor --platform mac`, unchanged code), not the DDP path.

(d) The real sitting's estimate: 2 Device Run sessions (cap 16), 16 jobs, 48 runs, 72 records expected (8 short-chat jobs x 3, 8 1K jobs x 3 x 2 iterations). Device time from the 2026-10-16 records: the 12 jobs of Qwen3 1.7B / 4B and Gemma 4 E4B took 151.4 device-min there; Gemma 4 E2B's 4 jobs have no DDP run yet (by Gemma 4 E4B's 12.5-13.9 min a job, at most about 56) -> about 190-210 device-min (run_ddp's own estimate 622.6 leaves DDP records out of its basis). Wall: the jobs of one session ran side by side on 10-16 -> about 15-25 min for session 1 and 25-35 for session 2 when the pool has free units, about 1 h with the host's pull, scrub, records and summary; up to about 3.5 h if the units run one job at a time (timeout_hours 5). Upload: none — the 17 objects are in the bucket (`gcloud storage ls` each, read only, 22:3x); download: none — each model's local blob sha256 equals the Hub main's LFS sha256 (huggingface_hub HfApi.model_info, metadata only): Qwen3-1.7B_dynamic_wi4b32_afp32 2a72330b, Qwen3_1.7B 362ec1c9, qwen3_4b_mixed_int4 569fe029, gemma-4-E2B-it 18193810, gemma-4-E4B-it 0b2a8980.

Checker on the real records (copies of the ten 2026-10-16 DDP dirs with a job SESSION.json, the committed summary as history): kind `job payload (ddp)`, the 1K dirs PASS, every short-chat dir HOLD on `gen-budget` (536-1039 generated, budget 128). The attached route's short-chat records carry no budget (S26 s5a 566, s5b 660, Pixel 8a p3a-r2 790 generated): the rule meets only the DDP route's records, which name the budget they pass (`--max_output_tokens=128`, ignored by litert_lm_main: b6ddcb2c on v0.16.0, the same on v0.18.0). d6077c6b's message does not state it (no basis there). dad937b1's message states it with the numbers; the allow-list line citing dad937b1 is in the working tree, uncommitted, for the supervisor's word: with it the ten copies read PASS 10.

## 監督の追加: Mac の LiteRT-LM pin と再検証

- environment.lock.json `arms.litert-lm.mac = {"tag": "v0.18.0", "since": "2026-10-12", "note": …}` (dad937b1). session_check: the Mac's LiteRT-LM reads that block for a sitting on or after its since day (the campaign name's date); the iPhones read default_tag; a block registered after the fact is taken from the newest registry into the registry of the sitting's day (REGISTERED_LATER), and the finding that reads it names the commit it came from (f36512ae). Selftest: the base Mac cases now stamp the Mac pin; a Mac sitting after since stamping default_tag HOLDs naming arms.litert-lm.mac, the day before since PASSes.
- Re-check (22:41): the checker of 53b9ba1d in a clone at 53b9ba1d against the checker of f36512ae over a clone at dad937b1, over the 88 committed dashboard dirs with SESSION.json and the main tree's Mac dirs of 2026-10-12 / 10-16 (five, not four: the first 10-16 anchor ABORTED anchor-collapse is the fifth) copied into both clones: PASS 77 / HOLD 15 / FAIL 1 -> PASS 79 / HOLD 13 / FAIL 1 of 93, 3.0 s each. Every committed dir identical in verdict and findings; the five Mac dirs lose their engine-stamp finding:

| dir | 53b9ba1d | f36512ae |
|---|---|---|
| `2026-10-12-dashboard-v1-m4max-anchor-mac` | HOLD (engine-stamp) | PASS |
| `2026-10-12-dashboard-v1-m4max-mac` | HOLD (engine-stamp, reply-empty, reply-off-task, user-name) | HOLD (reply-empty, reply-off-task, user-name) |
| `2026-10-16-dashboard-v1-m4max-anchor-mac` | FAIL (engine-stamp, not-admitted) | FAIL (not-admitted) |
| `2026-10-16-dashboard-v1-m4max-r2-anchor-mac` | HOLD (engine-stamp) | PASS |
| `2026-10-16-dashboard-v1-m4max-r2-mac` | HOLD (engine-stamp, partial, prompt-newtag, reply-empty, reply-off-task, user-name, verdict) | HOLD (partial, prompt-newtag, reply-empty, reply-off-task, user-name, verdict) |

  The 2026-10-17 iPhone 17 Pro AA pair (committed, stamps v0.18.0) stays PASS through its allow-list line (e3010721); the 10-12 payload and the 10-16 r2 pair still HOLD on their other rules (the 10-16 Mac r2 Qwen3 replies ROUND1 named).

## 本物の sitting の結果

- Command (22:46:21, the supervisor's go of 22:45): `BENCH_ANDROID_BIN_DIR=~/code/edge-llm-bench/android/bin python3
  scripts/dashboard_job.py s26-ddp --once --post-page-out <scratchpad>/r5/page --no-page-commit` (worktree, branch
  bench-autopilot at 63ec5615). Log `logs/dashboard-job/2026-10-18-s26-ddp.log`.
- The sitting: check_ddp ready; plan 16 jobs / 2 sessions / 4 skipped (cap 16); 17 inputs found in the bucket (nothing
  uploaded, nothing downloaded); session 1 `session-03ab291b` 22:46:46-23:02:05 JST (15.3 min, its 8 jobs started
  together at 22:46:52 once 8 units were free: "4 pending, 4 running" at 22:49, "8 running" at 22:50), 76.1 device-min;
  session 2 `session-e314180b` 23:02-23:28 JST, 116.9 device-min; 16 of 16 jobs PASSED, 48 runs, 72 records; 193.0
  device-min in all (the estimate said 190-210; run_ddp's own 622.6). bench matrix exit 0 at 23:29:13.
- SESSION.json (`results/raw/2026-10-18-dashboard-v1-s26-ddp-m1q-36-android/SESSION.json`): phase payload, platform ddp,
  admitted true, verdict COMPLETED, reason `ddp lab unit: no session anchor; each run carries its cap marks and the text
  check`, anchor null, runner_exit 0, cells_expected 16, cells_with_records 16, `ddp: {id m1q-36, sessions
  [session-03ab291b, session-e314180b], jobs 16, device_minutes 193.0, results {PASSED: 16}, plan {sessions 2, jobs 16,
  device_minutes_estimate 622.6}}`, skipped: the 4 Qwen3 0.6B lines. Job ledger: `2026-10-18 22:46:21  2026-10-18
  23:29:13  s26-ddp  results/raw/2026-10-18-dashboard-v1-s26-ddp-m1q-36-android  OK  ok  0  42.9  1`.
- The post (23:29:13-23:29:21): HELD, exit 1, nothing committed. The checker: FAIL — `logcat-unscrubbed` x16 (every
  execution-level `ddp/<session>/<job>/execution-<id>/logcat.txt`: "the execution-level logcat.txt stays out of every
  commit"), `big-file-size` x10 (the same files, 5.2-12.1 MB); the 8 short-chat `gen-budget` findings excused by the
  allow-list line of 63ec5615 (dad937b1). No other finding. REVIEW.md in the dir; autopilot ledger: `…=FAIL … held: …
  FAIL (rules: big-file-size, logcat-unscrubbed); a sitting is committed whole or not at all`. Reported to the
  supervisor as the stop condition (23:30).
- The supervisor's decision (23:3x): `.gitignore` keeps `results/raw/*/ddp/*/*/execution-*/logcat.txt` out (with the
  reason in its comment), a post selftest case, the post again by hand (no new billing), the sitting's records and
  SESSION.json untouched. 6e3d5908 (.gitignore + the post selftest case; tested first on a scratch clone with a copy of
  the dir: 16 ignored, 501 files left, the checker PASS).
- The post again, 23:33:44-23:34:45: `python3 scripts/dashboard_post.py
  results/raw/2026-10-18-dashboard-v1-s26-ddp-m1q-36-android --page-out <scratchpad>/r5/page/<dir> --no-page-commit`.
  - checker: **PASS** (`job payload (ddp)`); the 10 `big-file-size` HOLDs went with the ignored files (no finding left
    but the 8 excused `gen-budget`); scrub: 0 files (no account name in the dir).
  - commit **0c82ff22** on bench-autopilot (author john-rocky <rockyshikoku@gmail.com>, the commit-msg hook passed):
    `results 2026-10-18 Galaxy S26 lab units on the Developer Device Platform (DDP m1q-36, SM-S942U1, 16 units),
    litert-lm-cpu: v0.18.0, litert-lm-gpu: v0.18.0: 16/16 cells of matrices/dashboard-ddp-v1-android-s26.cells in one
    dashboard-job sitting 22:46–23:29 JST (2 Device Run sessions session-03ab291b, session-e314180b, 16 jobs, 193.0
    device-min; no session anchor: a lab unit's runs carry their own cap marks and text check); text check 48/48;
    cpu-capped counted 36/72 (litert-lm-gpu 36), past the line 36 (litert-lm-cpu 36; a lab unit starts capped: no
    number); FAILURES: none; SKIPPED: 4 lines; results/summary rebuilt from the git index (4739 -> 4811 lines)`.
    `git show --stat`: 503 files, 351858 insertions (the dir: 72 records, 48 run logcats, the raw logs and decoded
    texts, ddp/ plans, requests, operations, session reports, provenance, scrub.json, SESSION.json, SKIPPED.txt;
    results/summary/device-runs.csv +72 rows and README.md); 0 execution-level logcats (the 16 stay on disk, ignored,
    beside the ignored ddp-raw/).
  - summary: 4739 -> 4811 lines (+72 = the sitting's 72 records).
  - P's build and its four checks into the scratchpad (P not written: `?? .DS_Store` only, HEAD 8100b64): build 0
    (0.2 s), check_against_bench_dashboard PASS (1.2 s), **check_regression FAIL (2)** (0.1 s), check_aa PASS (0.2 s),
    render_check PASS (48.3 s). The check's whole output (8 lines):

```
regression (this check's loop): 29 series, 78 sittings (64 shown), red points decode 1 / prefill 6 / memory 1, regime changes 4; 9 excluded
  regression.json: 29 series, 78 points compared on every field (numbers to 2 decimals) and the meta; 0 mismatches
  regression.csv: 78 rows compared with their JSON points, column by column; 0 mismatches
  cells.json: 24 newest points equal their cell on 15 fields and are shown, 3 series of cells not measured have no point, 9 excluded cells listed; 2 mismatches
  planned devices: Pixel 11 (no identifier, no number, no series); 0 mismatches
  FAIL cells.json SM-S942Q litert-lm-gpu litert-community/gemma-4-E2B-it-litert-lm long-context-1024-gen256 2048 gemma-4-E2B-it.litertlm: no point of the cell's campaign 2026-10-18-dashboard-v1-s26-ddp-m1q-36-android
  FAIL cells.json SM-S942Q litert-lm-gpu litert-community/gemma-4-E2B-it-litert-lm short-chat gemma-4-E2B-it.litertlm: no point of the cell's campaign 2026-10-18-dashboard-v1-s26-ddp-m1q-36-android
FAIL (2)
```

    Why: P's `check_cells` (tools/check_regression.py l.335-369) wants, for every Regression series, a point of its
    cell's campaign. The Galaxy S26 GPU Gemma 4 E2B cells (short chat, 1K) now take tonight's lab-unit sitting as their
    newest (build.py STAND_IN, a GPU arm), while the Regression section drops stand-in rows (build.py l.1254) and
    follows the phone's own sittings: no point of that campaign. Gemma 4 E2B is one of the Regression section's two
    models; the 2026-10-16 DDP sittings (Qwen3 1.7B / 4B, Gemma 4 E4B) touched none of its cells, so the page never met
    this before. A page-side question (P is read only here); see 提案 10.
  - page number changes: `cells with a number before and none now: 0, the reverse: 0`; red: `page and bench agree (8
    red points); no red point in this sitting (8 on the page)` (the lab unit's rows are no red point).
  - switch: `would push bench d9762f2c..0c82ff22 (16 commits, 15 not made by this step)`, no page commit to push,
    nothing to publish. post exit 1 (a page check failed; the bench commit stands).
- Autopilot ledger (LEDGER2), two lines for the dir: 23:29:13 `…=FAIL` held (above) and
  `2026-10-18 23:33:44  2026-10-18 23:34:45  2026-10-18-dashboard-v1-s26-ddp-m1q-36-android  …=PASS
  0c82ff2265580bb4ece034d65ce42489f23e9c4f  4739 -> 4811  build 0 0.2s; check_against_bench_dashboard 0 1.2s;
  check_regression 1 0.1s; check_aa 0 0.2s; render_check 0 48.3s — FAIL check_regression  (no page commit)  would push
  bench d9762f2c..0c82ff22 (16 commits, 15 not made by this step)  no page commit to push  nothing to publish (…)  page
  cells: …: 0, the reverse: 0; page: not committed (a check failed; the bench commit stands); red: page and bench
  agree (8 red points); no red point in this sitting (8 on the page)`.
- After it (23:36, the 6-day window applied): `PATH=<scratchpad>/r5/fakebin:<scratchpad>/r5/trapbin:$PATH python3
  scripts/dashboard_job.py auto --dry-run` -> `ddp: s26-ddp (Galaxy S26 (DDP m1q-36)): done: admitted 2026-10-18 23:24
  results/raw/2026-10-18-dashboard-v1-s26-ddp-m1q-36-android, within 6 days` (the report line: `s26-ddp  ddp  lab
  unit, decided after the attached device's sitting; last admitted 2026-10-18 23:24`).

## 受け入れ基準

1. selftests: on 79d9526c `dashboard_job_selftest.py` 89 (the ddp cases and the 6-day window included),
   `session_check_selftest.py` 39, `dashboard_post_selftest.py` 48, `regression_watch_selftest.py` 50, all exit 0; the
   CI rehearsal on a shallow clone of 79d9526c (python 3.11.13, `env -i`): every CI step exit 0 (validate_cells both,
   build_summary + `git diff --exit-code results/summary/`, render_leaderboard, render_dashboard --check,
   test_render_rules, test_import_native_benchmark, the four selftests, android/bench/selftest.py,
   android/ddp/selftest.py with the main tree's engine files, py_compile, bash -n). Met.
2. The two dry runs as in Mac 側 PASS (b) and (c). Met.
3. The real sitting: SESSION.json admitted true with its ddp numbers; checker **PASS** (after the `.gitignore` line the
   supervisor decided; the first post FAILed on the executions' own logcats, reported as the stop condition); one post
   commit 0c82ff22 naming DDP, the lab units and the caps; summary +72; LEDGER2 two lines (the held one and the
   committed one); 2 sessions (cap 16). P's four checks: 3 PASS, **check_regression FAIL (2)** with its output and
   reason above. Met except check_regression.
4. Docs: autopilot §9 (+ §3, §7, status), job doc §3, ddp-integration, the skill (2 bullets); and session-check-v1.md.
   `git status --porcelain` empty but K (after this file's commit). Met.

## commit

On bench-autopilot, explicit paths, no attribution line, nothing pushed: **dad937b1** (the slot: schedule, cells
file, switch, JOB, CHECK, POST, three selftests, environment.lock.json arms.litert-lm.mac), **f36512ae** (the
later-registered block's note only where it is read), **63ec5615** (the gen-budget allow-list line), **6e3d5908**
(.gitignore: the executions' own logcats; the post selftest case), **0c82ff22** (the post's: the sitting's dir and
the summary), **79d9526c** (the 6-day window, docs 5), and this file's commit (its hash in the report).

## 提案

1. **Stage 5 — the Googler's one command.** `./bench autopilot --ddp <id> --project <p> --bucket gs://<b> [--cells <file>]`
   = this round's lab-unit sitting with their project and bucket (`ddp_sitting` passes neither today: `bench matrix
   --ddp` takes `--project` / `--bucket`, the job would read them from the entry or flags) + `session_check.py` on
   the dir (`--json` / `--markdown` into the output dir) + the page data from the bench's own
   `scripts/render_dashboard.py` (its cells, not P) + `regression_watch.py` without `--compare`, over a series of
   the lab unit's own (the unit as a device of `ops/autopilot/regression-watch.json`, bench-only), `--respond
   --state-dir <their dir>`. No commit (the post's commit and page steps are this repo's owner's), one output dir:
   the campaign dir, SESSION.json, the check, the cells, the red list. From a clean clone it needs gcloud signed
   in, python >= 3.10 with huggingface_hub, and the engine files (README DDP section, step 2); the Linux container
   route of `results/raw/2026-10-16-googler-first-run-dev/LANE_CLOSE.md` is the rehearsal. When they run it weekly,
   `ddp_weekly` here goes false.
2. **The whole `bench doctor` touches phones.** Every platform's checks run (WARN when not required): `adb
   devices`, `xcrun devicectl list devices`, and with exactly one Android phone attached `adb -s <serial> shell
   sha256sum …` on it. The Mac sitting's preflight (`preflight_mac` -> `bench doctor --platform mac`) does that
   at every Mac firing, so a Mac sitting starting while a phone is measured by another firing, the other phone
   unplugged, shells into the measured phone. A `--only` (the required platforms alone) in doctor.py, used by the
   job's preflights, closes it; this round's DDP path calls `check_ddp` alone.
3. **gen-budget sees one route.** The attached route's short-chat records name no budget (`outputTokenBudget`
   absent; `run_cell.py` writes it only on some paths), the DDP route's name the one litert_lm_main ignores: the
   rule fires on DDP only (63ec5615 excuses it). Either both routes name the budget they pass and the rule excuses
   `litert_lm_main` short-chat everywhere with b6ddcb2c, or the records name a budget only when the engine honors it.
4. **run_ddp's estimate leaves DDP records out of its basis** (`elapsed_basis` skips `device.ddp`): 622.6
   device-min for a set that took about 200 on 10-16. Reading the same id's DDP records first would make the
   estimate usable as a cap in device-minutes (the switch caps sessions today).
5. **A killed sitting keeps billing.** `timeout_hours` kills the host side; a session already posted runs on and
   stays in the bucket. The job could resume it (`run_ddp.py --resume <operation>` from
   `ddp/operation-create-<n>.json`) at the next firing instead of a new sitting.
6. **The auto firing's exit code is the attached part's**; the lab unit's result is its own ledger line and the
   `ddp: <key>: <verdict>, exit <n>` line. launchd's log shows only the first; a morning brief reads the ledger.
7. **The `bench dashboard-job` wrapper forwards none of `--no-ddp`, `--post-page-out`, `--no-page-commit`,
   `--no-retake`** (only `--dry-run --once --cells --suffix`): add them there (ROUND4 提案 5).
8. **The CPU jobs cost about half the device time and give no page number** (the m1q-36 units start capped:
   55-68 % drops on 10-16). They keep the text check and the record of the cap; a GPU-only DDP file would halve
   the weekly cost. The owner's call.
9. **A ledger reason with newlines, latent.** `preflight_mac`'s `NotReady("bench doctor --platform mac FAILED:\n" + out)`
   would put the doctor's whole output, newlines and all, into the TSV's reason field at a real firing whose Mac
   doctor fails (the auto dry run's done line shows that text; the main tree's ledger has no such row yet: 109
   lines, every one 9 fields). The DDP path's reasons go through `one_line()`; the same for the Mac's would keep
   the ledger one line per sitting.
10. **The page's check_regression and a lab unit on a Regression model.** STAND_IN lets the lab unit's GPU rows be a
   Galaxy S26 cell's newest sitting, while the Regression section follows the phone's own sittings; for Gemma 4 E2B
   (a Regression model) the two disagree and `check_regression` fails, so the post leaves the page uncommitted
   whenever the lab unit's sitting is newer than the phone's own. In the page repo: either the check reads a stand-in
   cell against the phone's own newest point (cells.json `stand_in` set -> look for the newest point of the series
   instead of the cell's campaign), or STAND_IN does not apply to the Regression section's cells (a lab unit stands in
   for the other models' cells only). On the bench side the alternative is a DDP file without the Regression models'
   rows (Gemma 4 E2B; Qwen3 0.6B is excluded on s26 already), which gives up the lab unit's E2B data. The owner's call
   with the page's lane; until then the nights with a lab-unit sitting newer than the S26's own keep the page as it was
   (the bench commit stands, the ledger says FAIL check_regression).
11. **A job sitting's dir now holds ignored files** (the executions' logcats, ddp-raw/): about 240 MB per DDP sitting on
   the host (ddp/ 125 MB before the ignore, ddp-raw/ 116 MB); the bench never deletes them (audit trail). A host disk
   check before the weekly slot, or a retention note in docs/OPERATIONS.md, when they add up.

## 訂正

- launch (2)「preflight(`./bench doctor --platform ddp` …)」→ the whole doctor runs every platform's checks (WARN when not required): `xcrun devicectl list devices`, `adb devices`, and with one Android phone attached `adb -s <serial> shell sha256sum …` on it; the DDP preflight runs doctor.py `check_ddp` alone (the checks `--platform ddp` requires). Evidence: scripts/doctor.py check_iphone l.171, check_android l.197-221; scripts/dashboard_job.py ddp_doctor.
- launch header「adb も devicectl も打たない」with 下見's `./bench doctor --platform ddp` → that doctor (as the launch asked) and the first s26-ddp dry run (22:32, before the preflight change) ran the real `adb devices` and `xcrun devicectl list devices` once each (listing only: two phones attached, so no shell), and the first auto dry run's Mac preflight (`bench doctor --platform mac`, unchanged code; adb was the fake) ran `xcrun devicectl list devices`; from 22:35 an xcrun trap caught it (`<scratchpad>/r5/trap-calls.txt`). Evidence: `<scratchpad>/r5/dry-auto.txt` (first run), scripts/doctor.py.
- launch (5)「1 session 45 分以内 = job-timeout の既定」→ run_ddp's `--job-timeout` default is 3600 s per job (executionTimeout), `bench matrix --ddp` passes none, a session has no timeout of its own (its jobs run side by side), and the sitting's bound is timeout_hours (5). Evidence: android/ddp/run_ddp.py main, bench do_ddp.
- launch (5)「`--switch` に scratchpad の copy を渡し `page_repo` を空に」→ with no page_repo the post skips the build and the four checks (page_step "skipped: no page repo"); the job got `--post-page-out` / `--no-page-commit` to pass `--page-out` / `--no-page-commit` through, P unwritten. Evidence: scripts/dashboard_post.py page_step; `?? .DS_Store` only in P.
- launch (2)「pending の週次判定は他の device と同じ = Monday から」→ changed by the supervisor during the sitting to a rolling window: no admitted session of the unit in the last `interval_days` (6). Evidence: 79d9526c.
- launch (1)「超えたら sitting を切る」→ the plan's sessions are counted before any is posted and a plan over the cap starts nothing (exit 2); run_ddp has no partial run. Evidence: scripts/dashboard_job.py ddp_sitting.
- launch (4)「DDP の sitting の post は他と同じ」, POST outside the commit list → the post's messages named a DDP sitting "(anchor phase ? committed before)" and "Galaxy S26 (DDP m1q-36) (SM-S942U1 (DDP m1q-36))": device_text / ddp_text and per-arm caps (dad937b1). Evidence: dashboard_post.py anchor_text at 53b9ba1d.
- acceptance 3「allow-list に入れる根拠の commit(d6077c6b)」→ d6077c6b's message does not give the gen-budget reason; the line (63ec5615) cites dad937b1, whose message gives it with b6ddcb2c and the numbers. Evidence: `git show -s d6077c6b`, ops/session-check/allow-list.tsv.
- acceptance 3「LEDGER2 1 行」→ two lines for the dir: the post held at 23:29 (FAIL on the executions' own logcats) and committed at 23:34. Evidence: logs/dashboard-job/autopilot-ledger.tsv.
- acceptance 3「P の check 4 本 PASS」→ check_regression FAILs on the Galaxy S26 GPU Gemma 4 E2B cells (their newest sitting is the lab unit's stand-in, the Regression section has no point of it); 3 of 4 PASS. Evidence: `<scratchpad>/r5/page/2026-10-18-dashboard-v1-s26-ddp-m1q-36-android/checks/check_regression.out`.
- the commit list (launch 6) → also .gitignore (the supervisor's decision), ops/session-check/allow-list.tsv, environment.lock.json (the supervisor's addition), scripts/dashboard_post.py and docs/session-check-v1.md (the rules the round changed). Evidence: the commits listed above.
- supervisor's addition「main tree の backlog の Mac dir(2026-10-12 / 10-16 の 4 dir)」→ five (the first 10-16 anchor, ABORTED anchor-collapse); 「10-12 anchor が PASS に、他は不変」→ the 10-16 r2 anchor also turns PASS (engine-stamp was its only finding). Evidence: the re-check table above.
- supervisor's addition「registry_pin: mac は arms.litert-lm.mac.tag があればそれ」→ the checker reads the registry as committed at the sitting's first record, so a block committed on 10-18 never reaches a 10-12 sitting; the block's `since` and REGISTERED_LATER (taken from the newest registry for a sitting on or after since, by the campaign name's date). Evidence: scripts/session_check.py registry_at.
- my own design (dad937b1) → no step kept the executions' own logcat.txt out of the commit, so the first post held; the `.gitignore` line (6e3d5908) is the rule people applied by hand in d6077c6b. Evidence: the held REVIEW.md quoted above.

## 罠と袋小路

- zsh does not split an unquoted variable: `for d in $dirs` handed 93 dir names to the checker as one argument (exit 2 "not a directory"): pass lists through a file and python, or `${(f)dirs}`.
- The checker selftest read environment.lock.json from disk while the checker reads the registry from git history: with the lock change uncommitted the Mac PASS case held and the allow-list check raised a TypeError; the selftest now reads the registry files as committed (HEAD), and the Mac `since` case runs once the block is committed (skipped before).
- A `since` date against records' UTC times: the 2026-10-12 Mac sitting's first record is 2026-10-11T17:00:08Z (02:00 JST); compare with the campaign name's local date (sitting_day), the same on any host.
- Default arguments are bound at definition (`load_switch(path=SWITCH)`, `ddp_tried(root=ROOT)`): a selftest that patches the module global is ignored; read the global at call time.
- An in-process `main()` that takes a device lock keeps its flock (per open file description, refused to a second open in the same process): release `.job.lock.<key>` between non-dry runs in a selftest.
- The selftest's host-driver cases leave `dj.pgrep` returning a busy driver for FAKE-S: reset it before later dry runs. `gtimeout` is the macOS coreutils name; CI has none: a non-dry selftest sitting puts a fake one on PATH.
- session_check.py imports dashboard_job.py: a module the post's checker imports is not edited during a live sitting (built and tested in a scratch clone, applied after the post).
- POST commit_message: a lambda named `arms` shadowed the message's own `arms` string (caught in the diff before any run): name helpers apart from the message's locals.
- A DDP dir after the sitting holds about 240 MB (ddp/ 125 MB before the ignore, ddp-raw/ 116 MB): the executions' own logcats are 5-12 MB each and fail the checker; they stay on disk, ignored since 6e3d5908.

## op と delegate の観察

- Measured from the 72 records and 48 run logs of `results/raw/2026-10-18-dashboard-v1-s26-ddp-m1q-36-android/` (0c82ff22); nothing else measured.
- Engine stamp: `engineVersion` v0.18.0 on 72 of 72 (36 litert-lm-cpu, 36 litert-lm-gpu); the model sha taken on the unit (`modelShaSource` device) on every record.
- Cap marks: `cpu-capped` and `cpu-capped-at-start` on 72 of 72 (cpucapWaitSeconds 0 for m1q-36); the summary's cpu_cap_drop_pct: CPU rows 28.3-68.4 %, GPU rows 28.3-53.0 % (the CPU rows past the 15 % line give no number, the GPU rows count marked).
- Accelerator registration: every run log (24 CPU, 24 GPU) has `RegisterAccelerator: … name=LiteRT GPU` and `… name=CpuAccelerator`; the registration lines do not tell the CPU arm from the GPU arm here (the command's `--backend` does). No line with "fall back" / "fallback" in any run log.
- Text check: the 1K task 48 of 48 PASS; the short-chat records carry none; the checker's reply proxies found no empty, looping or off-task reply.
- Prompt tokens: Qwen3 short chat 19, 1K 1338; Gemma 4 short chat 20, 1K 1106 — the 2026-10-16 counts. Generated tokens on short chat past the 128 budget the route passes: 536-1039 (litert_lm_main ignores `--max_output_tokens`).
- Engine caches (`conditions.engineCache`): CPU XNNPACK weight cache built 12 / loaded 24; GPU cache loaded 20 / not-loaded 16 (`firstEver` on run 1 of each of the 16 jobs; which later GPU runs loaded none: 未確認).
- Units: 16 serials, one build fingerprint `samsung/m1quew/m1q:16/BP4A.251205.006/S942U1UEU1AZAD_OYM1AZAD:user/release-keys`; the two sessions' 8 jobs each started in the same second (13:46:52Z, 14:02:59Z).

## 使った環境

- Mac Studio M4 Max (Mac16,9), macOS 27.0 (26A428); python 3.14.6 (homebrew) for every run; python 3.11.13 (uv) under `env -i HOME=… PATH=<python3.11>:/usr/bin:/bin` for the two CI rehearsals; huggingface_hub 1.8.0; Google Cloud SDK 587.0.0 (alpha / beta 2026.09.25); git 2.54.0 (Apple Git-157).
- DDP: project litert-edge-portal, bucket gs://litert-edge-portal-devicerun (run_ddp.py's defaults), pool m1q-36 (SM-S942U1, the units and fingerprint above), engine files v0.18.0 from the main tree's android/bin/v0.18.0 (BENCH_ANDROID_BIN_DIR, read only).
- Hold: none (a lab unit, no device of this host). No adb or devicectl to a phone's shell; the listings named in 訂正.
- Network: GCS (17 object listings, the two sessions' pulls), the Device Run API (2 sessions), the Hugging Face API (metadata of 5 models; no download), no upload.
- main tree read only (the five Mac dirs copied out, the engine files, the ledger read); P read only (its build.py and four checks run on the commit's tree into the scratchpad; P's tree `?? .DS_Store` only, HEAD 8100b64); the bisect worktree not touched.

## 残した file

- Committed on bench-autopilot (keep): dad937b1, f36512ae, 63ec5615, 6e3d5908, 0c82ff22 (`results/raw/2026-10-18-dashboard-v1-s26-ddp-m1q-36-android/` + results/summary), 79d9526c; this file's commit.
- In the committed DDP dir, ignored (keep: audit trail, never committed): the 16 executions' own `ddp/<session>/<job>/execution-<id>/logcat.txt` and `ddp-raw/` (the pre-scrub originals, 116 MB).
- Worktree `logs/dashboard-job/` (ignored): `2026-10-18-s26-ddp.log` (the sitting's log; the dry runs appended), `2026-10-18-auto.log` (the auto dry runs), `ledger.tsv` (+1: s26-ddp OK), `autopilot-ledger.tsv` (+2: held, committed), `.job.lock.s26-ddp`, the red step's `retakes.json` / `bisect-requests.json` (unchanged content) — keep the ledgers; the logs [消してよい].
- Scratchpad `/private/tmp/claude-501/-Users-USER-code-edge-llm-bench-wt-autopilot/33c7eaf2-bb8d-4e59-8aa1-ebc8ffe0d6c6/scratchpad/r5/` [消してよい, all]: `page/2026-10-18-dashboard-v1-s26-ddp-m1q-36-android/` (P's build of 0c82ff22, `checks/*.out`, the screenshots), `ddp-dryrun.txt`, `dry-*.txt`, `real-sitting.out`, `repost.out`, `fakebin/` + `fakeadb/` (the fake adb), `trapbin/` + `trap-calls.txt`, `schedule-ddp-due.json`, `realddp/` (copies of the 2026-10-16 DDP dirs with a synthetic SESSION.json, the checker runs), `recheck/` (the 53b9ba1d and dad937b1 clones with the five Mac dirs, old/new/new2 JSON), `six/` (the 6-day clone), `gi/` (the .gitignore test clone), `ci-clone/`, `ci-clone2/`, `ci-bin/`, `bucket-objects.txt`, `committed-dash-dirs.txt`, `ddp_times.py`, `commit*-msg.txt`, the selftest outputs.

## 経過
- 22:00 round start (ListAgents: this tab = edge-llm-bench-wt-autopilot-c1 [c82e21]); read LANE.md, ROUND4, JOB, POST, CHECK, WATCH, run_ddp, bench, doctor, P build.py STAND_IN / load_rows (read only)
- 22:0x supervisor's addition received (environment.lock.json arms.litert-lm.mac, registry_pin, re-check table)
- 22:12 下見 written; matrices/dashboard-ddp-v1-android-s26.cells written (validate OK, the 20 rows identical to the weekly set's); next: schedule entry, switch keys, JOB ddp platform, CHECK kind + registry_pin, POST message, selftests
- 22:33-22:36 dry runs (b) and (c) (adb and xcrun trapped); the DDP preflight changed to doctor.py check_ddp alone after the whole doctor was seen listing `adb devices` / `xcrun devicectl list devices` (and shelling into a single attached phone)
- 22:37 bucket: 17 of 17 objects present; Hub: 5 of 5 model blobs equal to main's LFS sha256 (metadata only)
- 22:38 dad937b1 committed (code, 10 explicit paths); CI rehearsal on a shallow clone of dad937b1 (python 3.11.13, env -i): every step exit 0
- 22:41 re-check of the 88 + 5 dirs; f36512ae (the later-registered block's note only where it is read); gen-budget allow-list line drafted (uncommitted)
- 22:43 Mac 側 PASS written; next: SendMessage "Mac 側 PASS、端末待ち", wait for go
- 22:45 go received (supervisor: allow-list line with the go; the command as proposed; add the lab unit's 6-day rule during the sitting, dashboard_post.py / session_check.py untouched until the post ends); 63ec5615 committed (the gen-budget allow-list line)
- 22:46:21 the real sitting started: `BENCH_ANDROID_BIN_DIR=~/code/edge-llm-bench/android/bin python3 scripts/dashboard_job.py s26-ddp --once --post-page-out <scratchpad>/r5/page --no-page-commit` (log logs/dashboard-job/2026-10-18-s26-ddp.log); check_ddp ready, plan 16 jobs / 2 sessions / cap 16; next: the 6-day rule in a scratch clone while the sessions run
- 22:46:46 Device Run session 1 = session-03ab291b posted (operation-1792331206580-65e1da0e35aef-1c472f90-cf1c9c84; 17 inputs found in the bucket, nothing uploaded); 22:49 its operation reads "Job status: 4 pending, 4 running" (four free units in the pool)
- 22:47-22:52 the 6-day window built and tested in a scratch clone of 63ec5615 (job selftest 89 checks; applied to the worktree after the post, since session_check imports dashboard_job); docs: autopilot §9 (+ §3 switch keys, §7, status), job doc §3 (paragraph + table row), ddp-integration (the weekly slot), the skill (2 bullets), session-check doc (the DDP kind, the Mac block, the gen-budget line)
- 23:02:05 session 1 (session-03ab291b) done: 22:46:46 -> 23:02:05 JST (15.3 min), 8 of 8 jobs PASSED, all 8 started at 22:46:52 (8 units side by side once they were free), 76.1 device-min (Qwen3 1.7B cpu sc 10.3 / gpu sc 5.8 / cpu 1K 8.0 / gpu 1K 5.5; Gemma 4 E2B 11.8 / 11.8 / 11.5 / 11.4); 32 logcats scrubbed (ssid 332, ip6 90, mac 308, mac-part 264, ip 206)
- 23:02 Device Run session 2 posted (operation-1792332173673-65e1dda880361-e0749cfe-549c5651)
- 23:29:13 the sitting closed: bench matrix exit 0; SESSION.json admitted=True verdict=COMPLETED; 2 Device Run sessions (session-03ab291b, session-e314180b), 16 jobs PASSED, 193.0 device-min, 16 of 16 cells with records; job ledger: s26-ddp OK exit 0, 42.9 min
- 23:29:21 the post HELD (exit 1): the checker FAILs the dir — logcat-unscrubbed x16 (every execution-level ddp/<session>/<job>/execution-<id>/logcat.txt, the whole unit's log; scrubbed, its original in the ignored ddp-raw/) and big-file-size x10 (the same files, 5.2-12.1 MB); the 8 gen-budget findings excused by 63ec5615 (dad937b1); nothing committed, REVIEW.md in the dir, the page not built; the disk summary is bench matrix's rebuild (uncommitted). Stop condition (the real sitting's checker FAIL): reported to the supervisor, waiting
- 23:30-23:33 (between the clock readings 23:30:29 and 23:33:44) the supervisor's decision received (the .gitignore line, a post selftest case, the post again, then the 6-day window and the docs, then the round close)
- 23:33 6e3d5908 committed (.gitignore + the post selftest case; post selftest 48 checks); 23:33:44-23:34:45 the post again: checker PASS, commit 0c82ff22 (summary 4739 -> 4811), P build + checks: 3 PASS, check_regression FAIL (2: the S26 GPU Gemma 4 E2B cells' stand-in campaign has no Regression point), red: page and bench agree
- 23:36 the 6-day window applied from the scratch clone (3 files unchanged since 63ec5615); selftests 89 / 39 / 48 / 50; `auto --dry-run` (fake adb): `ddp: s26-ddp (…): done: admitted 2026-10-18 23:24 …, within 6 days`
- 23:37 79d9526c committed (the 6-day window + docs 5); 23:38 CI rehearsal on a shallow clone of 79d9526c: every step exit 0
- 23:39 the round close written; next: round_close_lint, this file's commit, the report
