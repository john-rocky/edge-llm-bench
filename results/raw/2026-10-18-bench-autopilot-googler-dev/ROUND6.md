# ROUND6 — stage 5: the Googler's one command (`./bench autopilot --ddp <id>`) — worker edge-llm-bench-wt-autopilot-googler-5c [dd676c] (Opus 5.5)

Launch: ~/code/standup/launch/2026-10-18-autopilot-googler-opus-r6.md. Supervisor: edge-llm-bench-55 [4f120b].
Started 2026-10-18 22:47 JST (`date`), branch `bench-autopilot-googler` at f36512ae.

## 下見

- `date` 22:47:06 JST (start); `df -g ~`: 595 GB available of 1858.
- `colima status`: not running -> `colima start --cpu 4 --memory 8 --disk 60`: rc 0 in 133 s (22:59:45 -> 23:01:58,
  `K3/linux/00-colima-start.log`); colima 0.10.3, context `colima`, Docker server 29.5.2, VM Ubuntu 24.04.4 LTS,
  4 CPUs, 7.74 GiB. `docker ps -a`: no container (D3's `elb-googler-first-run` is gone; only the image
  `ubuntu:24.04` 534baea6a22c is left, the digest D3 ran).
- The measurement-window lock `~/code/coreai/_GPU_LOCK` is empty at 22:5x (no window open).
- D3's host driver `results/raw/2026-10-16-googler-first-run-dev/linux/run_steps.sh`: one `step <name> <log> <fatal>
  <cmd>` per container step, each behind `quiet_wait.py --max-wait 21600`, steps.tsv (start, end, seconds, rc),
  STOPPED_AT / FAILED_STEPS / run_steps.done; phases main (pull, run --memory 6g, apt-base, user, apt-python,
  gcloud-install, venv, gcloud-copy, gcloud project + token, clone + release asset, doctor, selftest, dry runs,
  offline, versions), verify, r2-*, r2b-*; host functions h_gcloud_copy (tar of `~/.config/gcloud` without
  `logs/` and the ADC file), h_copy_into_clone, h_mac. Traps from its LANE_CLOSE: ubuntu:24.04 has user `ubuntu`
  at uid 1000 (userdel first); `python3-venv` before `python3 -m venv`; the release asset carries macOS `._*`
  files (harmless); a driver edited while bash runs it reads shifted lines; the hook reads command text (every
  absolute path here holds `bench`); `docker run` / `docker exec` only from the driver behind quiet_wait.
- Host `PATH=<adb + xcrun traps>:$PATH BENCH_ANDROID_BIN_DIR=~/code/edge-llm-bench/android/bin ./bench doctor
  --platform ddp` (23:05): exit 0 `ready`; `ok gcloud`, `ok gcloud sign-in`, `ok huggingface_hub 1.8.0`, `ok ddp
  engine files v0.18.0: 9 files = android/engine-pins.json, in ~/code/edge-llm-bench/android/bin/v0.18.0`;
  python 3.14. The whole doctor ran `adb devices` and `xcrun devicectl list devices`: both went to the traps
  (no phone reached; `warn devicectl`, `warn Android device`).
- Host HF cache (huggingface_hub 1.8.0): `models--litert-community--Qwen3-1.7B/refs/main` = 79bf0667…,
  `snapshots/79bf0667…/Qwen3-1.7B_dynamic_wi4b32_afp32.litertlm` -> `../../blobs/2a72330b…` (977,184,032 B, the
  Hub main's LFS sha256 r5 read at 22:3x). D3's container wrote the same file under huggingface_hub 2.2.0 as
  `hub/blobs/41/4194181f…` (the xet hash) with the snapshot link beside the repo folder
  (`results/raw/2026-10-16-googler-first-run-dev/r2b/hub-probe-container.log`).
- Read for the design (read only): JOB `scripts/dashboard_job.py` (ddp_doctor, ddp_plan, ddp_sitting, ddp_slot,
  post_sitting, run_matrix, load_switch), POST `scripts/dashboard_post.py` (post, page_step, red_step, main),
  WATCH `scripts/regression_watch.py` (page_rows, compute, respond, bisect_command, main), CHECK
  `scripts/session_check.py` (kind_of, check_session, find_ledger), `scripts/render_dashboard.py`,
  `scripts/doctor.py` check_ddp, `android/ddp/run_ddp.py` (main, model_file), the four selftests and
  `android/ddp/selftest.py` (FAKE_GCLOUD, FakeDeviceRun), README DDP section, skill "Lab phones without adb",
  r5's `ROUND5.md` (wt-autopilot), `scripts/engine_bisect.py` on bench-autopilot-bisect.

## 設計

```
bench autopilot --ddp <id> [--project p] [--bucket gs://b] [--cells f] [--runs N] [--suffix s] [--dry-run] [--no-commit]
  -> scripts/autopilot.py main()                       (bench: the subcommand, --flag=value passed through)
  lab_unit()   schedule.json entry with ddp_id <id> (m1q-36 -> s26-ddp), else made from android/ddp/devices.json:
               key <scheduleKey>-ddp (product without one; akita-35 -> pixel8a-ddp: the campaign
               <date>-dashboard-v1-pixel8a-ddp-akita-35-android keeps "-ddp-", the glob of 63ec5615's allow-list line),
               identifier = the summary's device string for the id (Pixel 8a (DDP akita-35)), else the catalog display,
               cells = --cells | matrices/dashboard-ddp-v1-android-<scheduleKey>.cells if it exists | matrices/ddp-first-run.cells
  dj.load_switch() (the cap), dj.device_lock(key), dj.open_log(key)          [real run only for the last two]
  gtimeout_note()  no gtimeout on PATH -> logs/autopilot/bin/gtimeout -> GNU timeout, first on PATH
  BENCH_DDP_PROJECT / BENCH_DDP_BUCKET := --project / --bucket   (bench matrix --ddp reads them when its flags are absent)
  job_overrides(dry, cap):  dj.load_switch -> (True, cap)    dj.ddp_doctor -> doctor_offline (dry only)
                            dj.ddp_sitting -> kept as is, its result noted    dj.post_sitting -> hands nothing over
  1 dj.ddp_slot()          the job's own: check_ddp, ddp_plan (cap), run_matrix (gtimeout bench matrix --ddp), SESSION.json,
                           render_dashboard, ledger line, done line
  2 dp.main(dirs)          in process, dp.post wrapped to keep its ledger row; --no-commit = dp.main(["--dry-run", ...])
  3 render_dashboard.py    subprocess; the rows of .dashboard/dashboard-v1.csv whose campaign is this sitting (f1ca3618)
  4 regression_watch.py    subprocess, --json/--markdown into logs/autopilot/<campaign>/ (dry run: stdout only)
  5 rw.load_state()        retakes.json / bisect-requests.json pending entries, each request's command, the tool's presence
  screen()                 one screen -> stdout, the job log, logs/autopilot/<campaign>/summary.txt
  exit: the sitting's when not 0; else the post's (0 / 1 / 2); a dry run 0
```

Reused, not copied: `dashboard_job.ddp_slot` / `ddp_sitting` / `ddp_plan` / `ddp_doctor` / `run_matrix` / `ledger` /
`device_lock` / `open_log` / `load_rows` / `load_switch`, `dashboard_post.main` / `post` / `load_switch` / `ACTION` /
`branch_of`, `regression_watch.load_state` / `BISECT_TOOL`, `doctor.check_ddp`. Written here: the lab-unit entry, the
gtimeout link, the offline doctor (check_ddp in process with `doctor.subprocess` swapped so the one `gcloud auth
print-access-token` is not started and its line reads SKIP; any other command would read as failed), the screen.
Changed outside the new files: `bench` only (the subcommand; `matrix --ddp` reads BENCH_DDP_PROJECT / BENCH_DDP_BUCKET).

Departures from the launch, with the reason:
- `ddp_weekly` is not read (r5's rule: a by-hand sitting refuses when it is false). It is the bench host's nightly slot
  and goes false "once a Googler runs the set" — the day this command becomes the route, the Googler's checkout would
  refuse. `ddp_max_sessions` still caps. The supervisor accepted it with the go (23:4x).
- The dry run runs no doctor sign-in (`gcloud auth print-access-token` can refresh the token over the network) and
  computes the red points (local files, read only); the launch's "network なし" is held to "no gcloud / network call".
- The code is committed before the container steps (b910eb2f, 704a7c4d), so the container's clone is a commit and the
  post's commit sits on the code that made it (r5 did the same); the round's K3 commit comes last.
- `--suffix` added (the job's "a second one today takes --suffix" would be a dead end without it).
- docs section number 10: r5's §9 (stage 4, the weekly slot) is on bench-autopilot, uncommitted there at 22:4x; both
  append at the end of the doc, a rebase joins them.

## Mac 側: selftest の末尾

`BENCH_ANDROID_BIN_DIR=~/code/edge-llm-bench/android/bin python3 scripts/autopilot_selftest.py` (python 3.14; 4.6 s; as of
7edc798d, whose HOLD sitting fails the text check — at b910eb2f it decoded past the budget, see 罠と袋小路):

```
--- 1. the dry run through the real chain on this checkout, network commands trapped
  ok  exit 0 (got 0)
  ok  no gcloud, adb, xcrun or curl ran (the traps first on PATH recorded nothing)
  ok  two commands started: the plan's bench matrix … --dry-run and regression_watch.py (…)
  … (18 checks in section 1)
  ok  nothing written under logs/ or results/raw/ (0 files differ)
--- 2. bench matrix --ddp --dry-run reads BENCH_DDP_PROJECT / BENCH_DDP_BUCKET
  ok  the plan's summary names the environment's project and bucket ({… 'project': 'env-project', 'bucket': 'gs://env-bucket' …})
  ok  a --project flag wins over the environment
  ok  no trapped command ran
--- 3. the lab unit, the default cells, --runs
  ok  m1q-36: schedule.json's entry s26-ddp (s26-ddp, matrices/dashboard-ddp-v1-android-s26.cells)
  ok  akita-35: key pixel8a-ddp, the summary's identifier, matrices/ddp-first-run.cells (pixel8a-ddp, Pixel 8a (DDP akita-35))
  ok  an unknown id: exit 2 (2)
--- 4. sittings against a fake bench in a temp git checkout
  ok  a PASS sitting: exit 0 (got 0)
  ok  the switch's ddp_weekly false does not stop a run by hand; its cap is read
  ok  no gtimeout on PATH: the timeout found there linked as logs/autopilot/bin/gtimeout
  ok  the plan, then the run: both bench matrix --ddp calls handed project p-1 and bucket gs://b-1 (…)
  ok  SESSION.json: admitted, key pix-ddp, the summary's identifier, the default cells, 1 of 1 cells (…)
  ok  the post's one commit: the sitting's dir and the summary (7 files)
  … (the one screen's 17 lines: check PASS, commit, summary, page skipped: no build.py in <tmp>/no-page-repo, table,
     red, requests, the retake, the missing engine_bisect.py line, the bisect command, the log line)
  ok  a second sitting the same day without --suffix: exit 2, the suffix named (2)
  ok  --no-commit on fake-36 (schedule.json's sam-ddp): the check PASS, no commit, exit 0 (0)
  ok  a HOLD (the text check failed): exit 1, no commit, REVIEW.md, the rule and what a person does (1)
  ok  --runs 1: a copy of the cells file with runs=1, one record (logs/autopilot/cells/ddp-first-run-runs1.cells, 1 records)
  ok  a sitting that wrote no record: exit 5, the reason and the next step (5)
  ok  no gcloud, adb, xcrun or curl call in any sitting

autopilot selftest OK (58 checks)
```

The same under python 3.12 with `PYTHONPATH=<a huggingface_hub that raises ModuleNotFoundError>` (CI's condition): 58
ok, exit 0. The existing selftests on this checkout after the change: `dashboard_job_selftest.py` exit 0 (6 s),
`session_check_selftest.py` 0 (2 s), `dashboard_post_selftest.py` 0 (12 s), `regression_watch_selftest.py` 0 (3 s),
`android/ddp/selftest.py` 0 (35 s, 76 checks). CI: one step after the regression response's in the job
android-driver-selftest, `BENCH_ANDROID_BIN_DIR="$RUNNER_TEMP/android-bin" python scripts/autopilot_selftest.py`.

## dry run (host)

`PATH=<gcloud, adb, xcrun traps>:$PATH BENCH_ANDROID_BIN_DIR=~/code/edge-llm-bench/android/bin ./bench autopilot --ddp
akita-35 --dry-run --project litert-edge-portal --bucket gs://litert-edge-portal-devicerun` (23:17, `K3/host-dryrun.log`,
the account name -> USER): exit 0, 0 trapped calls.

```
[2026-10-18 23:17:48] autopilot: lab unit Pixel 8a (DDP akita-35), key pixel8a-ddp, cells matrices/ddp-first-run.cells, project litert-edge-portal, bucket gs://litert-edge-portal-devicerun [dry-run: no network, nothing billed]
[2026-10-18 23:17:48] autopilot: steps: 1 sitting -> 2 post (scrub, check, local commit) -> 3 table -> 4 red points -> 5 requests
[2026-10-18 23:17:48] autopilot: no schedule.json entry for akita-35: key pixel8a-ddp made here
[2026-10-18 23:17:48] autopilot: switch: ddp_max_sessions 16 caps the plan (ops/autopilot/switch.json); its ddp_weekly (true) is the bench host's nightly slot, not read by a run by hand
[2026-10-18 23:17:48] === slot pixel8a-ddp (Pixel 8a (DDP akita-35), DDP akita-35) campaign 2026-10-18-dashboard-v1-pixel8a-ddp-akita-35 [dry-run]
[2026-10-18 23:17:48] doctor (check_ddp): ready
[2026-10-18 23:17:48]   OK    gcloud  <scratchpad>/trapbin/gcloud
[2026-10-18 23:17:48]   SKIP  gcloud sign-in  not checked in a dry run: gcloud auth print-access-token can refresh the token over the network (the run checks it first)
[2026-10-18 23:17:48]   OK    huggingface_hub  1.8.0
[2026-10-18 23:17:48]   OK    ddp engine files  v0.18.0: 9 files = android/engine-pins.json, in /Users/USER/code/edge-llm-bench/android/bin/v0.18.0
[2026-10-18 23:17:49] ddp plan: 1 jobs in 1 Device Run sessions on akita-35 (engine v0.18.0), 0 rows skipped; 12 upload candidates, 1.13 GB (the run uploads what the bucket lacks); run_ddp's estimate 9.0 device-min; cap 16 sessions (ops/autopilot/switch.json ddp_max_sessions)
[2026-10-18 23:17:49] plan:
[2026-10-18 23:17:49] $ gtimeout --kill-after=60 21600 /Users/USER/code/edge-llm-bench-wt-autopilot-googler/bench matrix matrices/ddp-first-run.cells --ddp akita-35 --campaign 2026-10-18-dashboard-v1-pixel8a-ddp-akita-35   env: 
[2026-10-18 23:17:49]   SESSION.json would read admitted true once the sitting writes records (ddp lab unit: no session anchor; each run carries its cap marks and the text check), anchor null, ddp {id, sessions, jobs, device_minutes}
[2026-10-18 23:17:49] === done: OK (ok) exit 0
[2026-10-18 23:17:49] autopilot: 2 post: printed in the summary below (the dir does not exist in a dry run)
[2026-10-18 23:17:49] autopilot: 3 table: scripts/render_dashboard.py
[2026-10-18 23:17:49] autopilot: 4 red: scripts/regression_watch.py
[2026-10-18 23:17:49] autopilot: 5 requests: logs/dashboard-job/retakes.json, bisect-requests.json

=== autopilot: Pixel 8a (DDP akita-35), key pixel8a-ddp [dry-run: nothing billed, nothing written]
sitting   OK — results/raw/2026-10-18-dashboard-v1-pixel8a-ddp-akita-35-android
post      would run scripts/dashboard_post.py over the dir: the scrub, scripts/session_check.py, a local commit of the dir + results/summary from the git index when it passes
          page would build /Users/USER/code/litert-bench-dashboard/build.py and run its four checks; push_bench / push_page / publish off / off / off
table     would render DASHBOARD.md and .dashboard/ (scripts/render_dashboard.py; local, gitignored)
red       regression: 29 series, 78 sittings (64 shown), red points decode 1 / prefill 6 / memory 1, regime changes 4
          8 red points, 0 of them this sitting's (a lab unit's rows make no series of the page's rule)
requests  retakes pending 0, bisect requests pending 0 (logs/dashboard-job/retakes.json, logs/dashboard-job/bisect-requests.json)
          scripts/engine_bisect.py is not in this checkout: it comes after PR #4 (LiteRT-LM Android builds from a git ref), with the bisect commit on top of it
next      the run, billed to litert-edge-portal: ./bench autopilot --ddp akita-35 --project litert-edge-portal --bucket gs://litert-edge-portal-devicerun
```

The red line is the page's own count (ROUND4 of the lane: 8 red points, 29 series, 78 sittings, 64 shown).

## dry run (container)

Driver `K3/linux/run_steps.sh main` (23:27:41 -> 23:33:22 JST, every step rc 0, `K3/linux/steps.tsv`; quiet_wait 0 s
before each step): container `elb-autopilot-googler` from the local `ubuntu:24.04` (534baea6…, not pulled again),
`--memory 6g`; D3's base steps (apt 58 s + 40 s, user, the gcloud CLI 589.0.0 by Google's apt route 72 s), README step
1's venv line (huggingface_hub 2.2.0, 20 s), the gcloud sign-in copied by tar (22 entries, no logs/ and no ADC file),
project set, `TOKEN_OK` (`02-venv-gcloud.log`); the branch from a bundle of this checkout (37,408,813 B, tip 704a7c4d;
the clone's HEAD = 704a7c4d, status clean, `03-clone-asset.log`); README step 2's block without its clone line (the
release asset v0.18.0 in 106 s, `sha256sum -c` 9 OK, 10 `._*` files beside them as D3 saw); git identity: with none set
`git commit-tree` stops, rc 128, "fatal: unable to auto-detect email address (got 'dev@85f82a346b8d.(none)')" — then
`dev (container) <dev@container.invalid>`; the model's cache entry copied from the host (refs/main 79bf0667…, the
snapshot link, the blob 2a72330b…, 977,184,032 B, 3 s, `04-hf-cache.log`): huggingface_hub 2.2.0 finds it offline,
sha256 of the bytes 2a72330b…, and its `dry_run` (one metadata request) reads `will_download False, is_cached True` —
nothing is downloaded from the Hub; `./bench doctor --platform ddp` `ready` (gcloud /usr/bin/gcloud, sign-in ok,
huggingface_hub 2.2.0, the 9 engine files; adb, xcrun, gtimeout none — `05-doctor.log`); the selftests with the system
python 3.12.3 and no huggingface_hub (CI's condition, `06-selftests.log`): autopilot 58 checks, dashboard_job,
session_check, dashboard_post, regression_watch, android/ddp 76 checks — every one exit 0, 23 s in all.

`60-dryrun.sh` (`07-dryrun.log`): README's block, verbatim, then the two placeholders filled:

```
## README.md, the autopilot block as written:
./bench autopilot --ddp akita-35 --dry-run --project <your project> --bucket gs://<your bucket>
## run, the two placeholders filled:
./bench autopilot --ddp akita-35 --dry-run --project litert-edge-portal --bucket gs://litert-edge-portal-devicerun
[14:33:21 UTC] autopilot: lab unit Pixel 8a (DDP akita-35), key pixel8a-ddp, cells matrices/ddp-first-run.cells, project litert-edge-portal, bucket gs://litert-edge-portal-devicerun [dry-run: no network, nothing billed]
[…] autopilot: steps: 1 sitting -> 2 post (scrub, check, local commit) -> 3 table -> 4 red points -> 5 requests
[…] autopilot: gtimeout: none on PATH; GNU timeout /usr/bin/timeout under that name (logs/autopilot/bin/gtimeout, linked by the run)
[…] doctor (check_ddp): ready   (OK gcloud /usr/bin/gcloud; SKIP gcloud sign-in not checked in a dry run; OK huggingface_hub 2.2.0; OK ddp engine files v0.18.0)
[…] ddp plan: 1 jobs in 1 Device Run sessions on akita-35 (engine v0.18.0), 0 rows skipped; 12 upload candidates, 1.13 GB …; run_ddp's estimate 9.0 device-min; cap 16 sessions
[…] $ gtimeout --kill-after=60 21600 /home/dev/edge-llm-bench/bench matrix matrices/ddp-first-run.cells --ddp akita-35 --campaign 2026-10-18-dashboard-v1-pixel8a-ddp-akita-35   env:
=== autopilot: Pixel 8a (DDP akita-35), key pixel8a-ddp [dry-run: nothing billed, nothing written]
sitting   OK — results/raw/2026-10-18-dashboard-v1-pixel8a-ddp-akita-35-android
post      would run scripts/dashboard_post.py over the dir: the scrub, scripts/session_check.py, a local commit of the dir + results/summary from the git index when it passes
          page skipped: no build.py in /home/dev/code/litert-bench-dashboard; push_bench / push_page / publish off / off / off
table     would render DASHBOARD.md and .dashboard/ (scripts/render_dashboard.py; local, gitignored)
red       regression: 29 series, 78 sittings (64 shown), red points decode 1 / prefill 6 / memory 1, regime changes 4
          8 red points, 0 of them this sitting's (a lab unit's rows make no series of the page's rule)
requests  retakes pending 0, bisect requests pending 0 (logs/dashboard-job/retakes.json, logs/dashboard-job/bisect-requests.json)
          scripts/engine_bisect.py is not in this checkout: it comes after PR #4 (LiteRT-LM Android builds from a git ref), with the bisect commit on top of it
next      the run, billed to litert-edge-portal: ./bench autopilot --ddp akita-35 --project litert-edge-portal --bucket gs://litert-edge-portal-devicerun
## dry run exit=0; gcloud log files before/after 5/5; results/raw entries 320/320; files under logs/ 0/0; git status --porcelain lines 0/0
```

The same steps and lines as the host's; the differences: the gtimeout line (Linux), the page line (no page repo: one
line), the paths. Versions (`08-versions.log`): Ubuntu 24.04.5 LTS aarch64, kernel 6.8.0-117, Python 3.12.3, git 2.43.0,
GNU tar 1.35, Google Cloud SDK 589.0.0.

## Mac 側 PASS

(a) selftests exit 0: `scripts/autopilot_selftest.py` 58 checks (Mac python 3.14; python 3.12 with huggingface_hub
blocked; the container's system python 3.12.3 without it), and the existing four (dashboard_job, session_check,
dashboard_post, regression_watch) plus `android/ddp/selftest.py` (76) on the Mac and in the container. CI: one step
(b910eb2f).
(b) the host dry run: exit 0, 0 calls to the gcloud / adb / xcrun traps (above, `K3/host-dryrun.log`).
(c) the container dry run: README's line as written with the placeholders filled, the same step list, exit 0, gcloud's
log files 5/5, nothing written; nothing billed (no gcloud command at all).
(d) the real one, `./bench autopilot --ddp akita-35 --cells matrices/ddp-first-run.cells --project litert-edge-portal
--bucket gs://litert-edge-portal-devicerun` in the container: 1 Device Run session, 1 job of 2 runs on akita-35 (the
plan); D3's two sessions of this row took 432 s and 360 s from the command to the records, so about 7 min plus the post,
the table and the red points (seconds); upload none (the plan's 12 objects are all in the bucket: `gcloud storage ls`
each, read only, 23:2x JST); download none (huggingface_hub's dry_run: `will_download False`). The expected check: HOLD
on `gen-budget` (both of D3's sessions of this row generated 526 tokens under the 128 budget), because the allow-list
line that excuses it (r5's 63ec5615, dir glob `*-dashboard-v1-*-ddp-*-android`, which this campaign name matches) is on
bench-autopilot, not on this branch: no commit, REVIEW.md in the dir, the screen names the rule and what a person does
(the launch's other passing form). With 63ec5615 cherry-picked into the container's clone only (the host branch
untouched), the same run should PASS and commit, and the commit goes into `K3/` as a bundle.

## 本物 1 本の結果

### r1 — the job FAILED on the unit; kept as evidence (the HOLD / FAIL form)

`70-session.sh` in the container (clone = 7edc798d + 85e90e21, 63ec5615 applied): `./bench autopilot --ddp akita-35
--cells matrices/ddp-first-run.cells --project litert-edge-portal --bucket gs://litert-edge-portal-devicerun`,
14:38:52 -> 14:42:13 UTC (201 s), exit 1 (`K3/linux/10-session.log`; the job's log `K3/linux/container-r1-*`).

- The sitting: check_ddp ready (sign-in ok), the plan 1 job / 1 session, 12 `in bucket:` lines, nothing uploaded,
  `session-4b783529` (operation-1792334341069-65e1e5bb7db72-0f0acc69-22d0fb4d) on unit `45231JEKB09089` (akita,
  BP1A.250405.007.B1; D3's two sessions ran on 45231JEKB09198 and 45231JEKB13059). Run 1 OK (decode 20.24 tok/s,
  thermal nominal -> nominal, 44 s); the wrapper's log then ends at `cooldown 120 s` (epoch 1792334482 = 14:41:22Z);
  the execution ended 14:41:46.543Z, `resultType FAILED`, cause `NATIVE_EXECUTABLE_FAILED` ("The native executable
  exited with a non-zero exit code", type CUSTOMER); run 2: "no run log pulled — no record". 1.5 device-min. The
  job's 18 args, the wrapper (sha256 8e2880f6…) and the engine are byte for byte those of D3's two sessions of this
  row, which ran both runs. The execution logcat has no kill line after 14:41:22Z (lowmemorykiller killed five apps
  at 07:40:54 local, during run 1's load). Why the wrapper exited non-zero in the cooldown: 未確認.
- gcloud during the run (its own logs): 10 `auth print-access-token`, 12 `storage ls`, 1 `storage cp` (the pull).
- The check: FAIL — `logcat-unscrubbed` (the execution's own `logcat.txt` was untracked and not ignored on this branch:
  r5's 6e3d5908 .gitignore line is on bench-autopilot), HOLD `failures` (FAILURES.txt: `result=FAILED clean=1/2`), HOLD
  `runner-exit` (`runner_exit 1`); `gen-budget` (526 > 128) excused by 63ec5615's line. No commit; REVIEW.md in the dir.
- The one screen (`logs/autopilot/<campaign>/summary.txt`):

```
=== autopilot: Pixel 8a (DDP akita-35), key pixel8a-ddp
sitting   OK (ok; bench matrix --ddp exit 1) — results/raw/2026-10-18-dashboard-v1-pixel8a-ddp-akita-35-android
          Device Run sessions session-4b783529; 1 jobs {'FAILED': 1}, 1.5 device-min; 1 of 1 cells with records
check     FAIL (rules: failures, logcat-unscrubbed, runner-exit)
commit    none (held: a sitting is committed whole or not at all)
summary   results/summary/device-runs.csv 4740 lines on disk (bench matrix rebuilt it from this checkout's results/raw; not committed)
table     wrote DASHBOARD.md and .dashboard/dashboard-v1.{csv,json}: 144 measured of 299 device-cells, 84 stale
          this sitting's cells on it: no-decode 1
          litert-lm-gpu Qwen 3 1.7B short-chat: no-decode
red       regression: 29 series, 78 sittings (64 shown), red points decode 1 / prefill 6 / memory 1, regime changes 4
          8 red points, 0 of them this sitting's (a lab unit's rows make no series of the page's rule)
requests  retakes pending 0, bisect requests pending 0 (logs/dashboard-job/retakes.json, logs/dashboard-job/bisect-requests.json)
          scripts/engine_bisect.py is not in this checkout: it comes after PR #4 (LiteRT-LM Android builds from a git ref), with the bisect commit on top of it
log       logs/dashboard-job/2026-10-18-pixel8a-ddp.log; logs/autopilot/2026-10-18-dashboard-v1-pixel8a-ddp-akita-35-android/ (summary.txt, post.txt, red.json, red.md)
next      failures: read FAILURES.txt and the cell's log: re-run the cell, or commit by hand with the reason
next      logcat-unscrubbed: scrub the logcat (android/ddp/scrub.py), keep execution-level logcat.txt out, post again
next      runner-exit: read the job log's tail for the runner's exit before calling the sitting clean
next      read results/raw/2026-10-18-dashboard-v1-pixel8a-ddp-akita-35-android/REVIEW.md (each finding and what a person does), then post again: python3 scripts/dashboard_post.py results/raw/2026-10-18-dashboard-v1-pixel8a-ddp-akita-35-android
next      results/summary/ on disk holds this sitting's rows: `git checkout -- results/summary` gives HEAD's back
```

  The sitting line reads OK because the job's own rule admits a lab unit's sitting that wrote a record (1 of 1 cells:
  run 1); the check holds it. The table's "no-decode" is the bench's own status for a cell whose one run is its
  firstEver cache-build run (left out of every number). The dir stays in the container's clone, uncommitted; a tar of
  it without `ddp-raw/` is `K3/container-campaign-r1.tar` (untracked).
- Asked the supervisor (23:4x): retake (2) with `--suffix r2` and 6e3d5908 applied in the clone too.

### r2 — the retake: PASS, committed in the container's clone

The supervisor's go (23:5x): (2). `35-update2.sh`: r5's 6e3d5908 applied in the clone only (88d41b29; the r1 dir's
execution `logcat.txt` now reads `.gitignore:67:results/raw/*/ddp/*/*/execution-*/logcat.txt`). `71-session-r2.sh`:
the same command with `--suffix r2`, 14:47:20 -> 14:52:49 UTC (329 s), exit 0 (`K3/linux/13-session-r2.log`).

- The sitting: check_ddp ready, the plan 1 job / 1 session, 12 `in bucket:` lines, nothing uploaded,
  `session-f53347c2`, 1 job PASSED, 3.7 device-min, on unit 45231JEKB13059 (D3's session b's unit). gcloud during
  the run: 14 `auth print-access-token`, 12 `storage ls`, 1 `storage cp` (the pull of `automation/sessions/session-f53347c2`).
- The check: PASS (kind job payload (ddp); gen-budget 526 > 128 excused by 63ec5615's line; the execution logcat
  ignored by 6e3d5908's).
- The one screen (`logs/autopilot/2026-10-18-dashboard-v1-pixel8a-ddp-akita-35-r2-android/summary.txt`, copied to
  `K3/linux/container-r2-autopilot-out/`):

```
=== autopilot: Pixel 8a (DDP akita-35), key pixel8a-ddp
sitting   OK — results/raw/2026-10-18-dashboard-v1-pixel8a-ddp-akita-35-r2-android
          Device Run sessions session-f53347c2; 1 jobs {'PASSED': 1}, 3.7 device-min; 1 of 1 cells with records
check     PASS
commit    9e310521b24f on bench-autopilot-googler (local), push: would push: no origin/main to push onto
summary   results/summary/device-runs.csv 4739 -> 4741 lines (the commit)
page      skipped: no build.py in /home/dev/code/litert-bench-dashboard
post red  no red point in this sitting (8 on the page)
table     wrote DASHBOARD.md and .dashboard/dashboard-v1.{csv,json}: 145 measured of 299 device-cells, 84 stale
          this sitting's cells on it: measured 1
          litert-lm-gpu Qwen 3 1.7B short-chat: measured, decode 19.8 tok/s (n=1)
red       regression: 29 series, 78 sittings (64 shown), red points decode 1 / prefill 6 / memory 1, regime changes 4
          8 red points, 0 of them this sitting's (a lab unit's rows make no series of the page's rule)
requests  retakes pending 0, bisect requests pending 0 (logs/dashboard-job/retakes.json, logs/dashboard-job/bisect-requests.json)
          scripts/engine_bisect.py is not in this checkout: it comes after PR #4 (LiteRT-LM Android builds from a git ref), with the bisect commit on top of it
log       logs/dashboard-job/2026-10-18-pixel8a-ddp.log; logs/autopilot/2026-10-18-dashboard-v1-pixel8a-ddp-akita-35-r2-android/ (summary.txt, post.txt, red.json, red.md)
next      the commit is local: git show --stat 9e310521b24f
```

- The commit (`git log -1 --stat` in the clone, `K3/linux/11-after.log`): 9e310521 by `dev (container)
  <dev@container.invalid>`, on top of 88d41b29 (6e3d5908 applied) and 85e90e21 (63ec5615 applied) over the host
  branch's 7edc798d; 28 files, 3805 insertions, 1 deletion: the dir's SESSION.json, SKIPPED.txt, the two records and
  their raw logs, `ddp/` (operation-1, operation-create-1, plan-1, request-1, scrub.json, session-1) and the pulled
  `ddp-out/` files (provenance, run<i>.engine.txt / .err / .exit / .log / .state, run<i>_logcat.txt scrubbed,
  wrapper.log), and `results/summary/device-runs.csv` (+2 rows) and `README.md`; no `ddp-raw/`, no execution
  `logcat.txt`. Its message (generated by the post, one line):

  `results 2026-10-18 Pixel 8a lab units on the Developer Device Platform (DDP akita-35, Pixel 8a, 1 unit),
  litert-lm-gpu: v0.18.0: 1/1 cells of matrices/ddp-first-run.cells in one dashboard-job sitting 14:47–14:52 UTC (1
  Device Run session session-f53347c2, 1 jobs, 3.7 device-min; no session anchor: a lab unit's runs carry their own cap
  marks and text check); text check 0/0 (no run carries one); cpu-capped counted 0/2 (none), past the line 0 (none; a
  lab unit starts capped: no number); FAILURES: none; results/summary rebuilt from the git index (4739 -> 4741 lines)`
- Out of the container: `git bundle create /tmp/autopilot-commit.bundle 7edc798d..bench-autopilot-googler` (verify ok:
  requires 7edc798d, holds 85e90e21, 88d41b29, 9e310521) -> `K3/autopilot-commit-r2.bundle` (40,595 B, sha256
  97b8c3f2…, untracked); on the host `git fetch K3/autopilot-commit-r2.bundle bench-autopilot-googler` -> FETCH_HEAD
  9e310521; no branch moved (the host branch stays at 7edc798d). To read it: `git log -1 --stat FETCH_HEAD`, or
  `git fetch <bundle> bench-autopilot-googler:refs/remotes/container/r2` in a clone.
- The r1 dir stays in the container's clone untracked (`git status`: `?? results/raw/2026-10-18-dashboard-v1-pixel8a-
  ddp-akita-35-android/`); `K3/container-campaign-r1.tar` holds it without `ddp-raw/` (33 members, 378,880 B).

Acceptance: (1) selftests exit 0, the CI step (b910eb2f); (2) the host's and the container's dry runs print the same
steps and call no network command; (3) r1 = the HOLD / FAIL form (the reasons and the next steps on the screen, exit
1), r2 = sitting -> check -> commit -> summary -> table -> red -> the screen, exit 0, one session each (two by the
supervisor's go); (4) the three docs, README's command typed in the container as written (placeholders filled);
(5) `git status --porcelain` empty outside K3 after the round's commit; the container stopped, not removed.

## docs の diff の要点

- README "Run the Android cells on a Developer Device Platform phone": after step 8, "**One command: the autopilot.**"
  (what it does after the billed sessions, the dry-run command in a bash block, `--no-commit`, `--cells`, the default
  cells, the git identity, what is left out on a host of one's own, the design pointer). 704a7c4d.
- `skills/run-edge-llm-bench/SKILL.md` "Lab phones without adb": one paragraph (the command, `--dry-run` first, what
  it does, `--no-commit`, §10). 704a7c4d.
- `docs/dashboard-autopilot-v1.md` §10 "Stage 5: the one command on a host with no phone": the command and its exit
  codes, the flow by function, the five departures from the job, what the host needs, what is left out (704a7c4d); the
  paragraph "From a clean Ubuntu 24.04 container" (this round's commit).
- `bench`: the module doc (the autopilot lines; `matrix --ddp`'s project / bucket from the environment). b910eb2f.

## commit hash

On `bench-autopilot-googler` (not pushed): b910eb2f (bench autopilot: `bench`, `scripts/autopilot.py`,
`scripts/autopilot_selftest.py`, the CI step), 704a7c4d (README, skill, docs §10), f1ca3618 (the screen's table line:
this sitting's cells only), 7edc798d (the selftest's HOLD sitting: a text-check FAIL), then this round's record (K3:
`ROUND6.md`, `host-dryrun.log`, `linux/`; the docs §10 rehearsal paragraph) in the commit that adds this file. In the
container's clone only: 85e90e21 (63ec5615 applied), 88d41b29 (6e3d5908 applied), 9e310521 (the post's commit of r2):
`K3/autopilot-commit-r2.bundle`.

## 提案

For the lane close (the holes left, then the material for the text to a Googler).

1. **An id with no row yet gets a guessed identifier.** The summary names a unit's records "<ro.product.model> (DDP
   <id>)"; for an id no record has named, `lab_unit` takes devices.json's display. A Pixel's display is its model name
   (akita-35: "Pixel 8a" both); a Galaxy's is not (m1q-36: display "Galaxy S26", records "SM-S942U1"; pa3q-35 /
   pa3q-36 / pa1q-36 have no record yet, their model names 未確認), so such a unit's first sitting would write records
   the job then counts as none (`cells_with_records 0`, admitted false, exit 5). The
   fix is the job's: `ddp_sitting` reads the identifier from the campaign's own rows (a few lines in
   `dashboard_job.py`), or devices.json gains each id's model name. Today: akita-35 and m1q-36 are exact.
2. **The terminal is quiet during the run.** `run_matrix` sends `bench matrix --ddp`'s output to the job log only; the
   screen says where the log is, then nothing until the sessions end (201 s and 329 s here, about 90 min for m1q-36's
   weekly file). A `--follow` that tails the job log, or the post's output already on the terminal, would do.
3. **`bench doctor --platform ddp` says nothing about gtimeout on Linux** (its gtimeout line is the iPhone check's, a
   warning "brew install coreutils"); the job needs it for the DDP sitting and only the autopilot covers it (the link).
   The DDP check could name `timeout` as Linux's form, and `run_matrix` could take whichever is on PATH.
4. **The default cells of m1q-36 is the weekly file** (16 jobs, 2 sessions, about 3.2 device-hours), by the launch's
   rule. A Googler's first `--ddp m1q-36` would bill all of it; `matrices/ddp-first-run.cells` as the default for a run
   by hand, with the weekly file behind `--cells`, is the cheaper start. The owner's call.
5. **Merging.** This branch rebases onto bench-autopilot after r5's close (its tip 4b8bceaf at 23:5x): docs §9 (r5,
   79d9526c) and §10 (here) both append at the end of `docs/dashboard-autopilot-v1.md`, and 79d9526c also edits
   `skills/run-edge-llm-bench/SKILL.md` (8 lines; a likely conflict beside this round's paragraph); its
   `scripts/dashboard_job.py` hunks touch ddp_tried, ddp_due, ddp_after and add ddp_window — none of the functions
   `scripts/autopilot.py` calls or wraps; 63ec5615 and 6e3d5908 are on bench-autopilot already, so the container's
   applied copies are never merged; after the rebase a DDP sitting's commit needs nothing applied by hand.
6. **Material for the text to a Googler** (facts checked here):
   - The command: `./bench autopilot --ddp akita-35 --dry-run --project <your project> --bucket gs://<your bucket>`,
     then the same without `--dry-run` (README "One command: the autopilot").
   - Left out on their host: the private team page, any push (the commit stays in their checkout), retakes (the bench
     host's attached phones), the bisect (`scripts/engine_bisect.py` needs PR #4 and the bisect commit).
   - Three prerequisites: (1) gcloud signed in, and a project of their own with the Device Run API enabled and a bucket
     in it (in litert-edge-portal only the owner's account can create sessions, D3's LANE); (2) python3 >= 3.10 with
     `huggingface_hub` and the pinned engine files (README step 2: a 40.6 MB release asset); (3) git's `user.name` and
     `user.email` set (on a host without them the post's commit stops: "unable to auto-detect email address").
   - Their first billed run uploads what their bucket lacks: the 12 inputs of the first-run row, 1.13 GB (the dry run
     lists them).

## 経過
- 22:47 started; ListAgents read; next: 下見.
- 22:59-23:02 colima started (133 s); 23:05 host doctor ready; next: design and `scripts/autopilot.py`.
- 23:16 `scripts/autopilot.py`, `scripts/autopilot_selftest.py`, `bench` written; selftest 58 checks exit 0 (python
  3.14; and 3.12 with huggingface_hub blocked); 23:17 host dry run exit 0, 0 trapped calls; the four selftests and
  `android/ddp/selftest.py` exit 0; 23:2x b910eb2f (code), 704a7c4d (README, skill, docs §10); next: the container.
- 23:2x the plan's 12 upload candidates: all in the bucket (`gcloud storage ls`, read only).
- 23:27-23:33 container main phase, every step rc 0 (dry run from README's line exit 0, gcloud logs 5/5); 23:3x Mac 側
  PASS written; next: SendMessage, wait for the go.
- 23:3x SendMessage「Mac 側 PASS、端末待ち」; while waiting, the table line read the unit's whole column (30 rows of
  Pixel 8a (DDP akita-35), 22 missing): f1ca3618 lists this sitting's cells only.
- 23:4x go from the supervisor: decision (2), 63ec5615 applied in the container's clone only; ddp_weekly not read is
  accepted. 23:37 update phase: the clone's selftest failed 1 of 58 — its HOLD case (gen-budget) passed and committed
  under 63ec5615's line; 7edc798d makes the HOLD case a text-check FAIL; 23:38 update again: clone = 7edc798d + 85e90e21
  (63ec5615 applied, committer dev (container)), selftest 58 ok. Next: the billed run (phase session).
- 23:38:52 JST (14:38:52 UTC) the billed sitting started in the container (`run_steps.sh session`); check_ddp ready; the
  plan 1 job / 1 session; 12 `in bucket:` lines, nothing uploaded; Device Run session 1 posted:
  operation-1792334341069-65e1e5bb7db72-0f0acc69-22d0fb4d. Next: wait for the end line (Monitor), then phase after.
- 23:42:13 r1 ended: session-4b783529, job FAILED (NATIVE_EXECUTABLE_FAILED in the cooldown before run 2), check FAIL
  (logcat-unscrubbed, failures, runner-exit), no commit, exit 1; 23:4x SendMessage (the retake is the supervisor's
  call); 23:4x go: (2), `--suffix r2`, 6e3d5908 in the clone too, the r1 dir kept as evidence.
- 23:47:10 r1 after phase: its bundle held only the applied 63ec5615 (the after step compared HEAD with the bundle
  base, not with the HEAD before the sitting): removed; 80-after.sh compares with the pre-sitting HEAD from then on.
  23:47:11 update2 (88d41b29). 23:47:20 r2 started (session-f53347c2). 23:52:49 r2 ended: PASS, committed 9e310521,
  exit 0. 23:53:32 r1 tar (no ddp-raw), r2 after: the bundle out, `git fetch` -> FETCH_HEAD 9e310521, no branch moved.
- 23:56 the container stopped (Exited 137, `sleep infinity` as PID 1); K3 scrubbed (the account name -> USER, the
  scratchpad path -> `<scratchpad>`, colima's VM address); docs §10's rehearsal paragraph. Next: round close, commit, lint.

## 訂正

- bisect: the launch's "この branch に無ければ「PR #4 の branch が要る」" — `scripts/engine_bisect.py` is on
  `bench-autopilot-bisect` (e3295a15), which is built on PR #4's branch `build-from-ref` (an ancestor of it); PR #4's
  files do not include the tool — `gh pr view 4 --json files`, `git merge-base --is-ancestor build-from-ref bench-autopilot-bisect`
- (d) "job 2": the first-run row is 1 job of 2 runs (the plan: "1 jobs in 1 Device Run sessions"; the row's `runs=2`)
  — `K3/host-dryrun.log`
- "1 session は 45 分以内 = 既定の job-timeout": run_ddp's `--job-timeout` default is 3600 s (`android/ddp/run_ddp.py:579`);
  the job's host-side gtimeout for a made entry is 21600 s (timeout_hours default 6) — `K3/host-dryrun.log`
- "段 4 の `dashboard_job.py` の platform ddp と同じ関数を呼ぶ": as they are they cannot carry a Googler's run —
  `ddp_sitting` refuses when `ddp_weekly` is false (`scripts/dashboard_job.py:1424-1427`), its plan and run pass no
  `--project` / `--bucket` (`:1295`, `:628-629`), `run_matrix` calls `gtimeout` (`:628`; Linux has `timeout`), its doctor
  runs `gcloud auth print-access-token` in a dry run too (`:1284-1287`, `scripts/doctor.py:248-250`): four wrappers in
  `scripts/autopilot.py`
- "`./bench doctor --platform ddp`(host)": the whole doctor runs `adb devices` and `xcrun devicectl list devices`
  (check_android / check_iphone run for every platform, WARN when not required) — trapped, `K3/ROUND6.md` 下見
- "page は … 飛ばして 1 行": the post already does it (`scripts/dashboard_post.py:690-693`); no code was needed
- The real run's commit needed two lines this branch lacks: r5's 63ec5615 (the DDP short-chat gen-budget allow-list
  line) and 6e3d5908 (`.gitignore`: an execution's own `logcat.txt`); without them a DDP sitting here HOLDs on
  gen-budget and FAILs on logcat-unscrubbed — `K3/linux/11-after.log` (r1's REVIEW.md); applied in the container's
  clone only, by the supervisor's go
- "README の command が container で打った物と一字一句同じ": the README line carries `<your project>` /
  `gs://<your bucket>`; the container ran it verbatim with those two filled — `K3/linux/07-dryrun.log`
- D3's container `elb-googler-first-run` is gone (`docker ps -a` empty, only its image left), so the model's Hugging
  Face cache entry came from the host's cache — `K3/ROUND6.md` 下見, `K3/linux/04-hf-cache.log`

## 罠と袋小路

- `dashboard_job.sh(cwd=ROOT)` and `load_rows(path=SUMMARY_CSV)` bind their defaults at import: patching `dj.ROOT` /
  `dj.SUMMARY_CSV` moves neither; patch `load_rows` itself, and let a fake `bench` resolve its cells against its own dir
  (`sh` runs it with the real ROOT as cwd) — `scripts/autopilot_selftest.py`
- A selftest's HOLD built on gen-budget passes once 63ec5615's allow-list line is in the tree (CI after the rebase):
  hold on a rule no allow-list line excuses (a text-check FAIL) — 7edc798d (found when the container's clone ran the
  selftest with the line applied)
- render_dashboard gives a lab unit's column every weekly cell (Pixel 8a (DDP akita-35): 30 rows, 22 missing): list a
  sitting's cells by its campaign, not by its device — f1ca3618
- macOS git invents an identity (user@host.local) when none is set; a container (hostname without a domain) does not:
  `git commit-tree` "unable to auto-detect email address", rc 128 — set user.name / user.email before the post
  (`K3/linux/03-clone-asset.log`)
- huggingface_hub 2.2.0 finds a 1.8.0-layout cache entry through its snapshot link: copy refs/main, the snapshot link
  and the blob (bsdtar `-n` with the member paths keeps the repo folder's other snapshots, blobs and 1.7 GB engine caches
  out), then `hf_hub_download(dry_run=True)` says `will_download` before anything is billed — `K3/linux/04-hf-cache.log`
- `docker exec` without `-i` passes no stdin: a `python3 - <<EOF` probe prints nothing and exits 0 (reads as success)
- zsh: `echo ======` is a command lookup ("===== not found") and ends the Bash call there (memory zsh-bash-tool-traps)
- An after step that compares HEAD with the bundle base reads commits applied in the clone as the post's: compare
  with the HEAD right before the sitting — `K3/linux/steps/80-after.sh` (r1's misnamed bundle removed, 経過 23:47)
- A driver's file is left alone while its bash runs it (D3: shifted lines); the step scripts are copied into the
  container at each phase's start, so a step script may change between phases, never the driver during one
- f-strings before Python 3.12 (CI 3.11) take no quote of their own kind inside `{}`: a variable — `scripts/autopilot.py` screen()
- The Bash tool refuses a foreground `sleep N; cmd`: a run_in_background until-loop, or read at once
- Reads by `docker exec` (logs, the session report) went from the Bash tool while the window lock was empty; the
  launch's rule puts `docker exec` in the driver behind quiet_wait: from here on, reads go through `docker cp` (allowed
  by the hook) or a driver step

## op と delegate の観察

- r2 (session-f53347c2, unit 45231JEKB13059, akita BP1A.250405.007.B1): engine stamp v0.18.0 on both records;
  `conditions.protocolFlags` [] (no cap mark: a GPU job on akita-35); thermal 0 -> 0 in both runs; run 1 firstEver,
  `engineCache.gpuCache` not-loaded, decode 20.16 tok/s; run 2 gpuCache loaded ("Initialized InferenceContext from
  serialized data", twice), decode 19.8 tok/s; the table's number is run 2's (n=1, run 1 left out as the cache
  build); 526 tokens generated in each run under `--max_output_tokens=128` (`outputTokenBudget` 128, excused by
  63ec5615's line), 19 prompt tokens; no `textCheck` (a short-chat record carries none); the checker's reply proxies
  passed (PASS) — the records and `run<i>.engine.txt` in FETCH_HEAD
- The GPU delegate, both runs: LITERT_CL took every node in one partition per subgraph (prefill_128 994 / 994,
  prefill_1024 994 / 994, decode 936 / 936); "Weights preparation on Gpu is disabled for PowerVR, Broadcom, Mali
  GPUs"; "NPU accelerator could not be loaded and registered: kLiteRtStatusErrorNotFound"; RegisterAccelerator LiteRT
  GPU and CpuAccelerator
- r1 (session-4b783529, unit 45231JEKB09089): run 1 decode 20.24 tok/s, firstEver, gpuCache not-loaded, 526
  generated, 19 prompt, thermal 0 -> 0; lowmemorykiller killed five apps (oom_score_adj 955-965) at 07:40:54 local,
  during run 1's load; the execution ended `NATIVE_EXECUTABLE_FAILED` 24 s into the 120 s cooldown, with no kill line
  in its logcat after the run; the wrapper's own exit cause: 未確認
- 未確認: whether r1's run-1 decode (20.24) and r2's (20.16 / 19.8) differ beyond run-to-run noise (one unit each,
  firstEver runs; not compared)

## 使った環境

- Host: Mac Studio, macOS (Darwin 27.0.0); python 3.14 (Homebrew; selftests), 3.12 (the CI rehearsal); huggingface_hub
  1.8.0; Google Cloud SDK 587.0.0; `BENCH_ANDROID_BIN_DIR` = the main tree's `android/bin` (v0.18.0); no phone touched
  (adb and xcrun trapped for the doctor and the dry run)
- colima 0.10.3 (started this round, 133 s; context colima), its VM Ubuntu 24.04.4 LTS, 4 CPUs, 7.74 GiB, kernel
  6.8.0-117-generic; Docker server 29.5.2, client 28.3.2
- Container `elb-autopilot-googler`: `ubuntu:24.04` (sha256:534baea6…eb55, not pulled again), `--memory 6g`; Ubuntu
  24.04.5 LTS aarch64; Python 3.12.3, pip 24.0, huggingface_hub 2.2.0 (venv `~/elb-venv`), git 2.43.0, GNU tar 1.35, curl
  8.5.0, bash 5.2.21, Google Cloud SDK 589.0.0; the Mac's gcloud sign-in copied by tar (no logs/, no ADC file); git
  identity `dev (container) <dev@container.invalid>`
- DDP: id akita-35 (Pixel 8a pool), project litert-edge-portal, bucket gs://litert-edge-portal-devicerun; 2 sessions:
  session-4b783529 (unit 45231JEKB09089, FAILED, 1.5 device-min), session-f53347c2 (unit 45231JEKB13059, PASSED, 3.7
  device-min); nothing uploaded; LiteRT-LM v0.18.0 (release asset android-litert-lm-v0.18.0, 40.6 MB)
- Hold: none (a lab unit has no hold file); the measurement-window lock was empty throughout (quiet_wait 0 s before
  every step, `K3/linux/quiet_wait.log`)

## 残した file

- Committed with this record: `K3/ROUND6.md`; `K3/host-dryrun.log` (the host dry run); `K3/linux/run_steps.sh` and
  `K3/linux/steps/*.sh` (the driver and its 19 step scripts); `K3/linux/*.log` (each step's output), `steps.tsv`,
  `run_steps-*.out`, `quiet_wait.log`; `K3/linux/container-r1-*` and `container-r2-*` (the container's job log and two
  ledgers, the autopilot output dirs: summary.txt, post.txt, red.json, red.md); the docs §10 paragraph
- Untracked in K3, not committed: `K3/autopilot-commit-r2.bundle` (the clone's 85e90e21, 88d41b29, 9e310521; 消してよい
  once read), `K3/container-campaign-r1.tar` (r1's dir without ddp-raw/; 消してよい once read), `K3/linux/run_steps.done`
  (the driver's last end line; 消してよい), `K3/LANE.md` (the supervisor's)
- The container `elb-autopilot-googler`, stopped, not removed (the clone at 9e310521 with r1's dir untracked and its
  REVIEW.md, the model's cache entry 977 MB, the venv): `docker rm` 消してよい once read; colima still running (the
  supervisor stops it)
- Host repo: FETCH_HEAD = 9e310521 (the bundle's objects in the shared object store, unreferenced); no branch or ref
  made or moved
- Scratchpad (`<scratchpad>`): repo.bundle (37 MB), the two patches, the traps, the selftest outputs: 消してよい
- Nothing under the worktree's `logs/` (the dry runs and the selftest wrote none)
