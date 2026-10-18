# ROUND 4 — regression response (stage 3a): bench-side red, retake, bisect request — worker edge-llm-bench-wt-autopilot-42 [114f6d] (Opus 5.5), started 2026-10-18 21:05 JST

Supervisor: edge-llm-bench-55 [4f120b]. cwd ~/code/edge-llm-bench-wt-autopilot, branch bench-autopilot, HEAD fb9bdbe4 at start. Mac only, no device: no adb or devicectl reached a phone (the job's dry runs ran with a fake adb on PATH, see 訂正). Launch: ~/code/standup/launch/2026-10-18-autopilot-regression-opus-r4.md

## 結果

- `scripts/regression_watch.py` computes the team page's red points in the bench with the page's own rule; `ops/autopilot/regression-watch.json` = the page's constants, read out of P's `build.py` module at 8100b64 (read only), each with its build.py line in `_doc`. Acceptance 1: `--compare ~/code/litert-bench-dashboard/dist/regression.json` exit 0 on HEAD's summary and on e3010721's: the same 8 red points, series 29 / 29, sittings 78 / 78, shown 64 / 64; between the two summaries 0 points added, 0 removed.
- retake (JOB): a device's pending retakes run as one sitting before its weekly set over `logs/dashboard-job/retake-<date>-<device>.cells` (the platform's anchor rows + the retake rows byte for byte), suffix `retake-<slug>`; `auto` takes a device with a pending retake first, and a device whose weekly set is done for its retake only; a retake sitting is not the week's session. Acceptance 3 printed below.
- red segment (POST): after the page, the commit tree's own `regression_watch.py --respond <dirs>`: the sitting's red points -> retakes; a retake sitting's verdict -> a bisect request + an EN/JA draft; `--compare` against the page build (`red: mismatch` in the ledger note). The page's number changes (cells with a number before and none now) in the ledger note and the page message.
- On real data (no commit): an export of d639ce96 + the 2026-10-14 Galaxy S26 anchor + b2 pair copied from the main tree, P's build into the scratchpad: `red: page and bench agree (8 red points); no red point in this sitting (8 on the page)`; number changes `cells with a number before and none now: 4 (cpu-capped 4), the reverse: 0` = the four Gemma 4 E4B CPU cells ROUND3 named (提案 2 there).
- selftests: `regression_watch_selftest.py` 50 checks (new, CI step), `dashboard_job_selftest.py` 60, `dashboard_post_selftest.py` 43, `session_check_selftest.py` 34 — all exit 0 on python 3.14.6 and on 3.11.13 under `env -i`; the CI rehearsal on a shallow clone of 44f19f9c: the four selftests, py_compile of every script, build_summary + `git diff --exit-code results/summary` and validate_cells all pass.
- commits on `bench-autopilot` (explicit paths, no attribution line, the commit-msg hook passed): `d639ce96` (10 paths: scripts/regression_watch.py, scripts/regression_watch_selftest.py, ops/autopilot/regression-watch.json, scripts/dashboard_job.py, scripts/dashboard_job_selftest.py, scripts/dashboard_post.py, scripts/dashboard_post_selftest.py, docs/dashboard-autopilot-v1.md, docs/dashboard-recurring-job-v1.md, .github/workflows/data-pipeline.yml), `44f19f9c` (2 paths: the number-changes cell key, below), and this ROUND4.md's commit (its hash goes in the report). Nothing pushed; the switch is all false as before.

## 設計

```
dashboard_job.py main()
  [auto] resolve_device(..., retakes=regression_watch.pending_counts(logs/dashboard-job),
                        skip=regression_watch.retake_sitting_dirs())
         a device with a pending retake: a candidate even when its weekly set is done (weekly_done),
         ranked first; device_sessions() skips the autopilot's retake sittings (SESSION.json `retake`)
  retake_sitting(schedule, key, dev, args)              (not with --cells / --no-retake; once per device per firing)
    regression_watch.pending_retakes()                  pending, oldest first; > 7 days -> expired
    regression_watch.write_retake_cells()               retake-<date>-<key>.cells (retake_cells_text)
    regression_watch.profile_plan()                     ./bench profile for an android CPU/GPU native-benchmark row
    attempt(rargs: cells=<generated>, suffix=retake-<slug>, retake={ids, cells_file, rows}, profile)
       phase A anchors -> admission -> phase B run_matrix(<generated>) [-> run_profile()] -> SESSION.json (+retake, +profile)
    regression_watch.finish_retakes()                   exit 0 -> done (+ campaign); else attempt counted, 2 -> abandoned
    ledger line (reason "retake <ids>: …"), "=== retake done", post_sitting()  -> the post judges it
  then the weekly set as before (skipped when auto chose the device for its retake only)

dashboard_post.py post()   ... commit_index() -> copy_summary()
  page_step()               build + 4 checks
  number_changes()          P HEAD:dist/cells.csv vs <page-out>/cells.csv -> note "page cells: …" and page_message()
  page_commit()
  red_step()                <tree>/scripts/regression_watch.py --root <tree> --respond <dirs>
                              --state-dir <checkout>/logs/dashboard-job --json <tmp> [--compare <page-out>/regression.json] [--dry-run]
                            -> note "red: …" (never the exit code; errors are the phrase)
  push() publish() write_ledger()

regression_watch.py
  compute()       load_admission(root) + page_rows() (= build.py load_rows + stand_in_rows) + cell_defs() (= load_cell_defs)
                  + regression_devices() + build_series() (= build_regression) -> series, red_points()
  compare()       red sets (device, arm, model id, task, ctx, file, campaign, metric), pct to 2 decimals, series / points / shown counts
  respond()       not a retake sitting: red points of the sitting that are their cell's newest -> retakes.json (row_for(): the
                  SESSION.json cells file's line, else the definition's) unless a retake covers the same cell + previous point;
                  a retake sitting: judge() each retake against the red point's own previous point -> red-stays / cleared /
                  unjudged; red-stays on another engine -> bisect-requests.json (bisect_command()) + regression-<date>-<slug>.md (draft_text())
```

Places that depart from the launch (reasons in 訂正): the retake row takes the place of an anchor row of the same cell; the retake is judged against the red point's previous point, not by the page's vs_prev of the retake; `auto` makes a done device a candidate for its retake (else "the next firing" would be next week); several pending retakes of a device run as one sitting (`retake-<n>cells`).

## 受け入れ 1 の表と差

`python3 scripts/regression_watch.py --compare ~/code/litert-bench-dashboard/dist/regression.json` (HEAD fb9bdbe4 = main's HEAD then, 21:28; again at 44f19f9c at 21:54, the same two lines): exit 0.

```
regression: 29 series, 78 sittings (64 shown), red points decode 1 / prefill 6 / memory 1, regime changes 4
compare with ~/code/litert-bench-dashboard/dist/regression.json: equal (red bench 8, page 8; series 29 / 29, points 78 / 78, shown 64 / 64)
```

| device | model | task | backend | campaign | metric | pct | engine_changed |
|---|---|---|---|---|---|---|---|
| SM-S942Q | Gemma 4 E2B | short-chat | CPU | 2026-09-08-dashboard-v1-s26-android | prefill | -12.00 | false (v0.16.0 -> v0.16.0) |
| Mac16,9 | Qwen 3 0.6B | short-chat | GPU | 2026-10-06-dashboard-v1-m4max-protocol1024-mac | prefill | -6.01 | false |
| Mac16,9 | Gemma 4 E2B | short-chat | GPU | 2026-09-14-dashboard-v1-m4max-mac | prefill | -37.25 | false |
| Mac16,9 | Gemma 4 E2B | short-chat | GPU | 2026-09-21-dashboard-v1-m4max-mac | mem | -24.71 | false |
| Pixel 8a | Gemma 4 E2B | short-chat | CPU | 2026-09-08-dashboard-v1-pixel8a-a-android | prefill | -19.82 | false |
| Pixel 8a | Gemma 4 E2B | short-chat | CPU | 2026-10-07-dashboard-v1-pixel8a-a-android | decode | -9.30 | false |
| Pixel 8a | Gemma 4 E2B | short-chat | GPU | 2026-09-08-dashboard-v1-pixel8a-a-android | prefill | -9.97 | false |
| Pixel 8a | Gemma 4 E2B | short-chat | GPU | 2026-10-07-dashboard-v1-pixel8a-a-android | prefill | -9.92 | false |

- `--summary <scratchpad>/r4/e3010721-device-runs.csv` (`git show e3010721:results/summary/device-runs.csv`, 4565 lines): exit 0, the same line and table. HEAD's summary (4739 lines) vs e3010721's: points added 0, removed 0, red set identical — the only summary change in between is 1798483f (the catalog-x2 iPhone 18 Pro campaign, 174 rows, a name without "dashboard").
- Cross-check: P's own build.py on HEAD into the scratchpad (`EDGE_LLM_BENCH=<worktree>`, `--out-dir <scratchpad>`) prints `regression: 29 series, 78 sittings (64 shown), red points decode 1 / prefill 6 / memory 1, regime changes 4` and writes a regression.json byte-identical to P's committed dist (cmp). P's working tree and HEAD (8100b64) unchanged (`?? .DS_Store` only).
- All 8 red points are not their cell's newest sitting (`--respond` would queue none; on the 10-07 Pixel 8a pair the dry run printed `red not queued (not its cell's newest sitting)` twice).

## selftest の末尾

`scripts/regression_watch_selftest.py` (shallow clone of 44f19f9c, python 3.11.13, `env -i`):

```
--- (d) a retake still red on another engine -> one bisect request; the same engine or back within the line -> none
  ok  on a later UTC day the page compares the retake with the red point itself (-0.3 %, not red)
  ok  the retake judged against the red point's previous point 2026-09-08-dashboard-v1-s26-android: red stays (red-stays)
  ok  one bisect request: good v0.16.0, bad v0.18.0, verdict speed:decode<=-5%, route ddp:m1q-36 (2026-09-16-s26-gemma4e2b-cpu-short-chat)
  ok  scripts/engine_bisect.py not in the tree: 'tooling not on this branch' logged, the request kept, no command
  ok  the retake carries its verdict
  ok  a retake sitting's red point queues no retake
  ok  with scripts/engine_bisect.py in the tree: the command (--good/--bad/--cells/--row/--verdict/--route): python3 scripts/engine_bisect.py --good v0.16.0 --bad 1dadd00c --cells matrices/st-text.cells --row 3 --verdict 'speed:decode<=-5%' --route ddp:m1q-36
  ok  the Mac: route none, no command (no route: the bisect runs on a Developer Device Platform lab phone (Android only))
  ok  a memory verdict: no command (engine_bisect.py has no mem verdict (decode or prefill only))
  ok  red stays on the same engine: no request (red-stays; retake 2026-09-16-s26-gemma4e2b-cpu-short-chat: red stays on the same engine (v0.16.0): no)
  ok  back within the line: no request (cleared; retake 2026-09-16-s26-gemma4e2b-cpu-short-chat: cleared (decode -0.11 % vs 2026-09-08-dash)
--- (e) the draft beside the request
  ok  EN and JA, the two points and the retake's number, the row, the command that re-measures it
  ok  no refused word in the draft (none)

selftest OK
```

The acceptance 2 items in the same output: (a) `threshold: -4.90 % is not red`, `threshold: -5.05 % vs the nearest earlier shown point is red`, `engine_changed: v0.16.0 -> v0.18.0 true, v0.16.0 -> v0.16.0 false`, `left out: the refused sitting, the catalog campaign, the lab unit's 3 stand-in rows`, `one point a day: the morning sitting (-15 %) hidden and never red, the evening one shown (-0.5 %)`, `regime: the protocol cell's warm sitting is never compared with its cold one`, `peak memory 1000 -> 1060 MB: -5.66 %, red`, `--compare, the same red set: exit 0`, `--compare, one red point fewer on the page: exit 1, the difference named`; (b) `one pending retake`, `its row is line 3 of the cells file the red sitting ran, byte for byte (spaces and comment kept)`, `exit 0 -> done with its campaign; a sitting that does not admit -> pending, abandoned after two`; (c) `alpha done this week with a pending retake: chosen before beta's weekly set`, `beta's retake sitting this week (SESSION.json names retakes) is not its weekly session`, `dry run: the retake sitting's anchor and its bench matrix line (…-retake-<slug>) before the weekly set's`, `the generated cells file: the android anchor rows byte for byte, then the retake row`, `auto, the weekly set done this week and a retake pending: the firing runs the retake sitting only`, `an unreadable retakes.json: one WARN line, no retake, the weekly set as before`; (d), (e) above. `dashboard_job_selftest.py` adds `beta done this week, 2 retakes pending: chosen before alpha's weekly set` and `beta's retake sitting this week is not its weekly session`; `dashboard_post_selftest.py` adds the red segment (dry run passes `--dry-run` on, a mismatch reads `red: mismatch` with exit 0) and the number changes (incl. `a cell is its context only on a ladder`).

## 受け入れ 3 の印字

`PATH=<scratchpad>/r4/fakebin:$PATH python3 scripts/dashboard_job.py s26 --dry-run --once`, the real `ops/dashboard-v1/schedule.json`, the worktree's `logs/dashboard-job/retakes.json` holding one fake pending entry written by hand (id `2026-10-18-s26-gemma4e2b-cpu-short-chat`, row = `matrices/dashboard-text-v1-android-a.cells` line 22, a note saying it is fake). The S26's three hold files were absent and no host driver ran (read before). Run at 21:39 and again at 21:52 on 44f19f9c (the same lines). exit 0:

```
=== retake: 1 pending for s26 (2026-10-18-s26-gemma4e2b-cpu-short-chat): one sitting over logs/dashboard-job/retake-2026-10-18-s26.cells before the weekly set [dry-run]
retake profile: none: the per-op profile comes from the native-benchmark rows' binary (litert_lm_advanced_main --enable_profiling); these retakes are text-task rows
=== slot s26 (Galaxy S26, android) attempt 1 campaign base 2026-10-18-dashboard-v1-s26-retake-gemma4e2b-cpu-short-chat [dry-run]
$ gtimeout --kill-after=60 2700 ~/code/edge-llm-bench-wt-autopilot/bench matrix matrices/anchors.cells --platform android --campaign 2026-10-18-dashboard-v1-s26-retake-gemma4e2b-cpu-short-chat-anchor   env: BENCH_ANDROID_SERIAL=… BENCH_CPU_MASK=…
$ gtimeout --kill-after=60 54000 ~/code/edge-llm-bench-wt-autopilot/bench matrix logs/dashboard-job/retake-2026-10-18-s26.cells --platform android --campaign 2026-10-18-dashboard-v1-s26-retake-gemma4e2b-cpu-short-chat   env: BENCH_ANDROID_SERIAL=… BENCH_CPU_MASK=…
=== retake done: OK (ok) exit 0
post: $ /opt/homebrew/opt/python@3.14/bin/python3.14 ~/code/edge-llm-bench-wt-autopilot/scripts/dashboard_post.py results/raw/2026-10-18-dashboard-v1-s26-retake-gemma4e2b-cpu-short-chat-anchor-android results/raw/2026-10-18-dashboard-v1-s26-retake-gemma4e2b-cpu-short-chat-android   [dry-run: printed, not run]
=== slot s26 (Galaxy S26, android) attempt 1 campaign base 2026-10-18-dashboard-v1-s26 [dry-run]
$ gtimeout --kill-after=60 2700 ~/code/edge-llm-bench-wt-autopilot/bench matrix matrices/anchors.cells --platform android --campaign 2026-10-18-dashboard-v1-s26-anchor   env: …
$ gtimeout --kill-after=60 54000 ~/code/edge-llm-bench-wt-autopilot/bench matrix matrices/dashboard-text-v1.cells --platform android --campaign 2026-10-18-dashboard-v1-s26   env: …
$ gtimeout --kill-after=60 3600 ~/code/edge-llm-bench-wt-autopilot/bench matrix matrices/dashboard-ortgenai-v1-android-ort.cells --platform android --campaign 2026-10-18-dashboard-v1-s26-ort   env: …
$ gtimeout --kill-after=60 14400 ~/code/edge-llm-bench-wt-autopilot/bench matrix matrices/dashboard-npu-v1-android-s26-short.cells --platform android --campaign 2026-10-18-dashboard-v1-s26-npu   env: …
=== done: OK (ok) exit 0
post: $ … scripts/dashboard_post.py results/raw/2026-10-18-dashboard-v1-s26-anchor-android results/raw/2026-10-18-dashboard-v1-s26-android results/raw/2026-10-18-dashboard-v1-s26-ort-android …
```

(timestamps, the preflight lines and the env values cut; the fake adb reports 60 GB free, so the plan is the whole set rather than the halves.) The generated file, validate_cells `OK`:

```
# generated by scripts/dashboard_job.py: a retake sitting of the autopilot (docs/dashboard-autopilot-v1.md section 8); not a committed matrix
# the android rows of matrices/anchors.cells, then each retake's row byte for byte from the cells file its red sitting ran
# 2026-10-18-s26-gemma4e2b-cpu-short-chat: Gemma 4 E2B CPU short-chat on SM-S942Q, red decode -9.30 % vs FAKE-prev-dashboard-v1-s26-a-android in FAKE-dashboard-v1-s26-a-android (matrices/dashboard-text-v1-android-a.cells line 22)
android litert-lm litert-community/Qwen3-0.6B short-chat anchor=1 runs=3 backend=gpu file=qwen3_0_6b_mixed_int4.litertlm
android llama.cpp unsloth/Qwen3-0.6B-GGUF short-chat anchor=1 runs=3 file=Qwen3-0.6B-Q4_K_M.gguf
android litert-lm litert-community/gemma-4-E2B-it-litert-lm short-chat backend=cpu cooldown=300 file=gemma-4-E2B-it.litertlm
```

(`diff` against `grep '^android ' matrices/anchors.cells` + `sed -n 22p matrices/dashboard-text-v1-android-a.cells`: identical.) With `retakes.json` emptied (`{"retakes": []}`): exit 0, 12 lines, `grep -c retake` = 0 — the weekly set's lines only.

## commit

- `d639ce96` — the code, the definitions, docs (autopilot §8 + §1/§4/§6/§7, job doc §3/§5/§6), the CI step (10 explicit paths).
- `44f19f9c` — the page's number changes key a cell without cells.csv's recorded context (only a ladder keeps it): before it, the real-data count read 3, the S26 llama.cpp Gemma 4 E4B short-chat cell (context 4096 at 09-14, none at 10-14) counted as two cells (2 paths).
- this ROUND4.md (1 path), hash in the report. Nothing pushed.

## 提案

1. **Stage 4 (the DDP weekly slot) — where it plugs in.** (a) schedule.json: an entry `{"platform": "ddp", "unit": "m1q-36", "auto": true, "billed": true}` → `PLATFORM_TOKEN["ddp"] = "android"` (campaign suffix), `PREFLIGHT["ddp"]` = gcloud auth / project / bucket, no adb, no hold (`hold` absent), `resolve_device` treats it as always attached; (b) `attempt()`: no phase A and no `admit()` (DDP has no anchor); the payload is `bench matrix <cells> --ddp <unit>`, SESSION.json `admitted` by the DDP rule of LANE.md (cpu-cap marks + the text check); (c) the retake sitting on a DDP entry = the generated file without anchor rows (`retake_cells_text` with no platform anchors); (d) the red rule: the page's Regression section skips stand-in rows (build.py l.1254), so a DDP sitting never makes a page red point; a DDP watch needs its own series (device `SM-S942U1 (DDP m1q-36)`) in the definitions file as a bench-only entry, with no `--compare` against the page; (e) a DDP red's bisect request routes to the same unit (`ddp:m1q-36`) and engine_bisect.py can run it as is; (f) billing: a switch key (`ddp_weekly`, default false) in ops/autopilot/switch.json beside the push keys, and the entry's "a Googler runs it -> our slot stops" switch.
2. **Stage 5 (the Googler's one command).** `./bench autopilot --ddp <id> --project <p> --bucket <b>` = the stage-4 sitting + `session_check.py` + the bench's own page data (render_dashboard's cells, not P) + `regression_watch.py` without `--compare` (the definitions file travels with the repo; nothing reads P) + `--respond --state-dir <their dir>`: one output dir with the cells, the red list, retakes and requests. From a clean clone: regression_watch needs only results/summary, matrices, SESSION.json and ops/ (selftest runs in CI with none of the Mac extras).
3. **The retake sitting's payload timeout** is the device's whole-sitting timeout (S26: 54000 s in the dry run) like every `--cells` sitting: a `retake_timeout_hours` (2 h) in schedule.json keeps a hung retake from holding the device into the next firings.
4. **A red on a cell the retake sitting did not target** (e.g. an anchor cell) is logged, never retaken (the launch's "a retake sitting's red = the second time" read literally); the next weekly sitting then compares against that slow point and the drop can pass as the new level. Either let such a point queue one retake, or mark it `needs a person` in the ledger note.
5. **`--no-retake` through `./bench dashboard-job`**: the `bench` wrapper passes only `--dry-run --once --cells --suffix` (not in this round's commit list); add the flag there.
6. **The copy of the page's rule outside the post.** The nightly `--compare` runs only where the post builds the page (switch `page_repo`). If P's `dist/regression.json` meta carried the constants machine-readably (cell files with tasks and device sets, backend map, stand-in map), `regression_watch.py` could check its copy against any built page without reading P's code.
7. **The state files are local** (`logs/` is ignored): a lost main-tree logs dir loses pending retakes (the retake sitting's SESSION.json keeps ids and rows) and requests. A request is a single-runtime fact (two LiteRT-LM builds on one device); a `REQUEST.json` in the retake payload dir would put it in the record with the sittings it names.
8. **The S26 CPU arm cannot be bisected on m1q-36** (every 2026-10-15 lab run started with policy6 at 3398 of 4742 MHz, android/ddp/devices.json): stage 3b's `adb:<serial>` route (named and refused in engine_bisect.py v1) is the route for a CPU red on the bench S26; the request carries the note today.
9. **Boundary**: the page's red is `pct < -5.0` (strict), engine_bisect.py's speed verdict is "5 % or more below" (inclusive); at exactly -5.00 % they read differently (one value in a thousand runs; noted, not changed).

## 経過

- 21:05 ListAgents (self = edge-llm-bench-wt-autopilot-42 [114f6d]; supervisor edge-llm-bench-55 [4f120b] present, busy). Next: read LANE.md, ROUND1/3, launch-r4.draft.md, P build_regression.
- 21:13 read: LANE.md, launch-r4.draft.md, ROUND3.md; P build.py (constants 81-355, load_rows / stand_in_rows / load_cell_defs / headline / headline_status / diff_pct / build_regression 1239-1360, main), P tools/check_regression.py (its own loop); render_dashboard / render_leaderboard; JOB attempt / resolve_device / main / post_sitting; POST post() / page_step; run_profile.py + `./bench profile` + docs/profiling-subcommand-design.md; engine_bisect.py CLI (bisect worktree, read only); session_check load_records (profiles/ is not read as records). P dist/regression.json: 29 series, 8 red, built from bench e3010721 (summary_rows 4564). Next: scripts/regression_watch.py + ops/autopilot/regression-watch.json, then acceptance 1.
- 21:28 ops/autopilot/regression-watch.json (P constants read out of P's build module at 8100b64, read only, PYTHONDONTWRITEBYTECODE) + scripts/regression_watch.py (compute / compare / respond / the job's helpers). Acceptance 1: `--compare dist/regression.json` exit 0 on HEAD's summary and on e3010721's (8 red, series 29, sittings 78, shown 64; points added at HEAD 0, removed 0); P's own build.py on HEAD into the scratchpad prints the same regression line and writes a regression.json byte-identical to P's dist. Next: dashboard_job.py retake sitting, then the post's red segment.
- 21:38 dashboard_job.py: retake_sitting() before the weekly set, resolve_device takes a done device with a pending retake first, device_sessions skips the autopilot's retake sittings, run_profile for an android native-benchmark retake row, --no-retake; dashboard_post.py: red_step() after the page (the tree's own regression_watch.py, --compare the page build), number_changes() into the ledger note and the page message. Selftests: regression_watch_selftest (new) OK, dashboard_job_selftest OK (+2 checks), dashboard_post_selftest OK (+4 checks), session_check_selftest OK. Next: acceptance 3 (the s26 dry run with a fake adb on PATH), a dry run of the red segment on real data, docs, CI step.
- 21:47 acceptance 3 run (21:39, fake adb on PATH: no adb or devicectl reached the phones); review of the diff found and fixed: a busy retake re-chosen after the poll would have run a done device's weekly set, auto --cells / --no-retake still chose done devices for retakes, an unreadable retakes.json would have stopped the weekly set, two retakes of one cell, red-step errors as exceptions; selftests (4) OK on python 3.14 and on 3.11.13 under env -i, py_compile 3.11 OK; committed d639ce96 (10 explicit paths). Next: the red segment and the page's number changes on real data (an export of d639ce96 + the 2026-10-14 S26 pair copied from the main tree, P's build into the scratchpad), then ROUND4.md.
- 21:52 real data: `red: page and bench agree (8 red points); no red point in this sitting`; the number changes read 3 where ROUND3 named 4 → the cell key (cells.csv's recorded context) fixed, 4 (cpu-capped 4); committed 44f19f9c; CI rehearsal on a shallow clone of 44f19f9c passes; acceptance 3 re-run on 44f19f9c (the same lines). Next: this file, round_close_lint, the commit, the report.
- 21:54 ROUND4.md written; acceptance 1 re-run at 44f19f9c (exit 0, the same lines); next: round_close_lint, the commit of this file, the report.

## 訂正

- launch header「`dashboard_job.py` の dry run … doctor が `adb devices` / `devicectl list devices` の一覧を 1 回打つ、phone への shell なし」→ an Android device's dry run calls no doctor; `preflight_android` runs `adb devices` and then `adb -s <serial> shell` (`ps -A | grep`, `dumpsys thermalservice`, the cpufreq ceilings, `df -k /data`, `ls` of the side-build tools) in a dry run too. Acceptance 3 ran with a fake adb first on PATH (dashboard_job_selftest.py's FAKE_ADB, the S26 serial in its device list): no real adb or devicectl was run in this round. Evidence: `scripts/dashboard_job.py` preflight_android, android_state, android_free_gb, android_side_builds_missing.
- launch (2)「生成 cells file = anchors.cells のその platform の行 + retake の行」→ `validate_cells.py` refuses a cell twice in one file (`duplicate cell`), so `bench matrix` would refuse a retake of a cell that is also an anchor row (the Mac / iPhone LiteRT-LM Qwen3 0.6B short-chat: `mac litert-lm litert-community/Qwen3-0.6B short-chat` in dashboard-text-v1.cells and `… short-chat anchor=1 runs=3` in anchors.cells): the retake row takes that anchor row's place (the primary anchor is the non-LiteRT one and still gates); an identical row is written once. Evidence: `scripts/validate_cells.py` validate_file (duplicate cell), `<scratchpad>/r4/mac-collision.cells` validate OK.
- launch (3)「retake sitting の赤 = 2 回目 → (4) へ」(red by the page's rule) → the page's vs_prev of a retake on a later UTC day than the red point compares it with the red point itself, so a drop that stays reads about 0 %: the retake is judged against the red point's own previous point (same diff_pct and threshold; on the same UTC day this is the page's vs_prev). Evidence: regression_watch_selftest (d) `on a later UTC day the page compares the retake with the red point itself (-0.3 %, not red)` / `red stays`.
- launch (2)「`auto` の week に 1 回の判定は週次 set の物」with the title's「次の firing で再測」→ the existing `auto` never takes a device whose weekly set is done, so a retake found at a sitting's post would wait for next week: a done device with a pending retake is a candidate for the retake only, and devices with a pending retake go first. Evidence: `scripts/dashboard_job.py` resolve_device (before: `entry.update(state="done", …); continue`).
- launch「P の定数(REGRESSION_DEVICES / MODELS / TASKS / METRICS、350〜355 行)」→ the rule also reads CELL_FILES (l.104-143), OPTIONAL_CELL_FILES, RUNTIME (l.191-231), BACKEND (l.254-306), STAND_IN (l.177-180), METRICS' better (l.311-316), PANELS' platforms (l.159-165) and build.py's own headline / headline_status / regression_value / diff_pct; all are P's constants or code and every data input is the bench's (summary, SESSION.json, matrices, schedule.json), so the stop condition did not apply. Evidence: `ops/autopilot/regression-watch.json` `_doc`.
- launch (4)「verdict = `speed:<metric><=-5%`」→ engine_bisect.py accepts `speed:decode|prefill<=-N%` only (SPEED_SPEC), and its probe_row refuses rows with anchor= / exclude= / exclude-on= / manual= / engine-build= and backend=npu: a memory red or such a row gets a request without a command (the reason in `why_no_command`). Evidence: ~/code/edge-llm-bench-wt-autopilot-bisect/scripts/engine_bisect.py parse_verdict, probe_row.
- launch acceptance 1「e3010721 の後の commit があるので差が出うる」→ no difference: the only summary change after e3010721 is 1798483f (catalog-x2, 174 rows, no "dashboard" in the campaign name); points added 0, removed 0. Evidence: `<scratchpad>/r4/acc1-head.json`, `acc1-e301.json`.
- launch (6)「数字のある cell が数字なしに変わった cell 数」→ keyed by cells.csv's context column, one cell splits in two (that column is the pooled runs' recorded allocation for a cell whose definition names none): keyed by device / arm / model id / task / file, and context on a ladder only (44f19f9c); on the 10-14 S26 pair 3 → 4. Evidence: `<scratchpad>/r4/real/page/cells.csv` vs P HEAD:dist/cells.csv.

## 罠と袋小路

- Times written before reading `date` (three times: 21:44 for 21:13 and 21:55 for 21:28 in 経過, 22:0x for 21:54 in 受け入れ 1; all corrected in place): read `date` in a call of its own before any line that carries a time.
- `git status` in a repo that is read-only to the round (P) moved P's .git dir mtime (21:17:39) with the index file unchanged — a lock file made and removed, 未確認 which (git's optional index refresh is the likely one): `GIT_OPTIONAL_LOCKS=0 git status` for read-only repos.
- Reading P's constants by importing build.py writes `__pycache__` unless `PYTHONDONTWRITEBYTECODE=1` is set before the interpreter starts (build.py's own `sys.dont_write_bytecode` comes after its import): with it, P's `__pycache__` stayed as it was (Oct 7).
- `pgrep -fl '…dashboard_job.py…'` by hand matched another agent session whose prompt text names the script; the job's own `pgrep()` skips argv[0] = claude, so its preflight is not fooled.
- cells.csv `context_tokens` is the pooled runs' recorded allocation for a cell whose definition names none (P make_cell `ctx = d["ctx"] or kv`; empty when no run pools): not part of a cell's identity except on a ladder.
- Scripted edits (`python - <<EOF` with str.replace and an assert per edit) failed twice: the doc's flow block (the old string's column spacing differed; nothing written) and a selftest string holding `\n` (one escaping level too many; the same script had already written dashboard_post.py, as intended): copy whitespace from the file (`sed 's/ /·/g'`) and use the Edit tool for strings holding `\n`.
- `resolve_device` returns three values (my first selftest addition unpacked two: ValueError).
- tok/s at one decimal in the draft made -5.05 % read off 9.0 vs 9.5: two decimals for a rate.
- A shell redirect wrote three files to /tmp (x_a/x_b1/x_b2.txt, the cells-row check); removed at once: redirects go to the scratchpad.

## op と delegate の観察

- なし(計測なし)。以下は records と page の build を読んで気づいた事。
- The page's 8 red points: none is its cell's newest sitting and none is engine_changed (v0.16.0 -> v0.16.0 for all 8), so none would have queued a retake or a bisect request; 6 are prefill, 1 decode (Pixel 8a Gemma 4 E2B CPU short-chat 2026-10-07, -9.30 %), 1 peak memory (Mac Studio Gemma 4 E2B GPU short-chat 2026-09-21, -24.71 %).
- The Mac Qwen 3 0.6B short-chat red point (2026-10-06, prefill -6.01 %) comes from the protocol sitting's anchor row (`matrices/dashboard-protocol1024-v1.cells` line 10, `anchor=1 runs=3`); that cell's newest sitting is `2026-10-09-dashboard-coreai-v1-m4max-anchor-retake-mac`, a Core AI lane's anchor retake whose name holds "dashboard".
- The cells' newest sittings at HEAD: Galaxy S26 Gemma 4 E2B CPU short-chat `2026-10-15-dashboard-v1-s26-0180-s5a-android`, Pixel 8a Gemma 4 E2B CPU / GPU short-chat `2026-10-15-dashboard-v1-pixel8a-0180-p6a-android` / `-p6b-android` (the v0.18.0 pass; latest_session takes the newest engine tag first).
- On the 10-14 Galaxy S26 pair the page loses the number of 4 Gemma 4 E4B CPU cells (litert-lm-cpu short-chat and 1K, llama.cpp short-chat and 1K: cpu-capped >15 %), as ROUND3 read; the llama.cpp short-chat cell's context column reads 4096 from its 09-14 sitting and nothing from the 10-14 one (no run pooled).
- Engine labels in the summary's LiteRT-LM rows: v0.15.0 / v0.16.0 / v0.17.0 / v0.17.1 / v0.18.0, `main@1dadd00c` (with and without a build note), `main@66058c82 (…)`, `main-20260821-selfbuilt`, `litertlm-android:0.17.0`; `bisect_ref()` resolves the tags and `main@<sha>` / `main-<sha>` and leaves the others without a ref (未確認: which tag `litertlm-android:0.17.0` is built from).

## 使った環境

- macOS 27.0 (Mac Studio M4 Max); python 3.14.6 (homebrew, `/opt/homebrew/opt/python@3.14`) for the runs, python 3.11.13 (uv) under `env -i HOME=… PATH=/usr/bin:/bin` for the CI rehearsal; standard library only.
- git 2.54.0 (Apple Git-157); commit-msg hook `~/code/standup/tools/git-hooks/commit-msg` passed both commits.
- hold なし。端末への操作なし: the job's dry runs used a fake adb (`<scratchpad>/r4/fakebin/adb`) first on PATH; no real adb, devicectl or doctor ran. The S26 hold files were read (absent); the Android runner's lock probe `/tmp/edge-llm-bench-android-RFGL80R6A6H.lock` was opened by the dry runs' preflight as every dry run does (0 bytes, 21:39 / 21:52).
- network なし. main tree read only (ls, `git ls-files`, the source of `cp -R` of the 10-14 S26 pair into the scratchpad); P read only (its build.py run into the scratchpad, `git show HEAD:dist/cells.csv`, status with GIT_OPTIONAL_LOCKS=0 after 21:17); the bisect worktree read only (engine_bisect.py's CLI and verdict / row rules).

## 残した file

- `scripts/regression_watch.py`, `scripts/regression_watch_selftest.py`, `ops/autopilot/regression-watch.json` (new) and the changed `scripts/dashboard_job.py`, `scripts/dashboard_job_selftest.py`, `scripts/dashboard_post.py`, `scripts/dashboard_post_selftest.py`, `docs/dashboard-autopilot-v1.md`, `docs/dashboard-recurring-job-v1.md`, `.github/workflows/data-pipeline.yml` — d639ce96, 44f19f9c.
- `results/raw/2026-10-18-bench-autopilot-dev/ROUND4.md` (this file) — committed next.
- worktree `logs/dashboard-job/` (ignored): `retakes.json` (now `{"retakes": []}`, the fake entry of acceptance 3 removed; its copy `<scratchpad>/r4/acc3-fake-retakes.json`) [消してよい]; `retake-2026-10-18-s26.cells` (the generated file of the fake retake) [消してよい]; `2026-10-18-s26.log` (the four dry runs appended) [消してよい]; `.regression.lock` [消してよい].
- scratchpad `/private/tmp/claude-501/-Users-USER-code-edge-llm-bench-wt-autopilot/46ea375c-5be7-4f96-ae30-34abc590f2be/scratchpad/r4/`: `acc1-*` + `e3010721-device-runs.csv` + `pbuild-head/` (acceptance 1 and P's build on HEAD), `p_constants.json` (the constants read out of P), `fakebin/` + `fakeadb/` (the fake adb), `acc3-*` / `acc3b-*` (acceptance 3 outputs, the generated cells file, the fake entry), `mac-collision.cells`, `real/` (the export of d639ce96 + the 10-14 S26 pair, its page build, the red step's state), `ci-clone/` + `ci-*.out` + `py311-*.out` (CI rehearsal), `keep_selftest.py`, `doc_autopilot_s8.md`, `commit1-msg.txt`, `commit2-msg.txt`, the selftest outputs — all [消してよい].
