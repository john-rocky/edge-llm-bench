# D3S4 Googler first run — round 2 (Opus 5.5; supervisor `edge-llm-bench-6b [6eedda]`)

Scope: from the r1 container (`elb-googler-first-run`, user `dev`), one billed Device Run session on `akita-35`
(`matrices/ddp-first-run.cells` = Qwen3-1.7B GPU short chat, 2 runs) -> the records into this worktree with the summary
rebuilt from the git index -> `K/LINUX_FIRST_RUN.md` completed -> a README quickstart -> `bench doctor --platform ddp`
-> two commits (not pushed). Launch: `2026-10-16-D3S4-opus-r2.md`. K = this directory. Container steps run through
`K/linux/run_steps.sh` (each after `quiet_wait.py`), logs in `K/linux/`, the session's numbers in `K/r2/session.md`.
Other lanes' measurement windows are named "another lane's window" here.

## 経過

- 2026-10-16 15:21:44 JST read the launch's files (LANE.md, ROUND1.md, LINUX_FIRST_RUN.md, run_steps.sh and the step
  scripts, CLAUDE.md, README 1-200, OPERATIONS 230-349, ddp-integration 395-461, run_ddp.py 1-60 / 140-172 /
  229-250 / 400-470 / 565-600, scrub.py 1-40, doctor.py, bench 70-95 / 195-235, the smoke campaign's
  `ddp/session-1.json` and run-2 record, D6 handoff §6). HEAD c153f1d (r1's commit after its amend; the launch's
  9a80ef7 is the pre-amend object). Next: `docker start`, the r2 driver phases.
- 15:28:54 another lane's window open (since 15:26:23; the one before it since 15:18:36): every container step waits
  in `quiet_wait.py`.
- 15:29:53 `docker start elb-googler-first-run` -> `Up`; colima running (context `colima`). Driver phases `r2-dry` /
  `r2-session` added to `K/linux/run_steps.sh`, step scripts `91-before-session.sh`, `92-dryrun-before-session.sh`,
  `95-session.sh` (`bash -n` clean).
- 15:30:03 phase r2-dry done (`K/linux/09-dryrun-before-session.log`): the clone's README.md, android/README.md and
  `matrices/ddp-first-run.cells` = the worktree HEAD's (sha256), clone HEAD 0efecb0 + those 3 paths, TOKEN_OK,
  `android/bin/v0.18.0` 20 entries (10 without `._*`), HF cache empty, no campaign dir; dry run exit 0: 1 job / 1
  session / 0 skipped, `"uncached": ["Qwen3-1.7B_dynamic_wi4b32_afp32.litertlm"]`, estimate 541 s (9.0
  device-minutes), 12 upload candidates 152,882,610 B; gcloud log files 9 / 9. Next: the session.
- 15:30:43 phase r2-session started (`nohup quiet_wait.py -- bash K/linux/run_steps.sh r2-session`; window closed,
  waited 0 s); the waiter `until [ -f K/linux/run_steps.done ]` in the background. Session id: pending (POST after the
  model download). Next: doctor, quickstart and docs drafted while it runs.
- 15:32:55 the driver downloaded the model, found the 9 engine files, the prompt and the wrapper in the bucket, uploaded
  one object (the model, 977,184,032 B, under `models/4194181f…/`, not the `models/2a72330b…/` object the D6 runs left),
  POSTed, and polls (`not done` every 30 s). Cause read at once: the Hub's `paths-info` for the file gives
  `lfs.oid` 2a72330b… and `xetHash` 4194181f…, last commit 2026-10-11 (unchanged since D6); the container's
  huggingface_hub 2.2.0 names the cache blob by the xet hash (`blobs/41/4194181f…`), and `run_ddp.model_file` takes a
  64-hex blob name as the sha256 (`android/ddp/run_ddp.py:190-191`). Next: doctor scripts while the session runs.
- 15:3x while the session ran I added the r2-after phase to `K/linux/run_steps.sh`, which the running driver (bash,
  inside its `case`) was still reading; I put the file back byte for byte at once (`git diff` = the r2-dry / r2-session
  additions only, 8307 B) before its step returned, so bash read nothing new. The phase goes in after the driver exits.
- 15:37:55 phase r2-session done: step `session` rc 0, 432 s (15:30:43-15:37:55); `session-17997931` PASSED (session
  327.016 s, job 322.500 s, execution 228.518 s); 2 records, no `FAILURES.txt`, no `ddp/error-*.json`, `SKIPPED.txt`
  empty; scrub 3 files (ip6 16, mac 2). 15:38:41 `docker cp` of the campaign dir into `results/raw/` (744 KB).
- 15:39 records read (`K/r2/session.md`): engineVersion v0.18.0, model.sha256 2a72330b… (modelShaSource device), no
  ddpMissing, serial 45231JEKB09198, protocolFlags `[]`, engineCache gpuCache not-loaded -> loaded, thermal 0 -> 0.
  15:39:5x the signal "DDP 1 session PASSED(Linux)" sent to the supervisor. Next: hygiene, stage, summary from the index.
- 15:40 hygiene on the campaign dir (user name 0, token words 0, e-mail 0; the per-run logcats after the scrub: no
  private IPv4, MAC, IPv6, keyword hits only `onetimeinitializer`); staged by the exclude pathspec: 25 paths, all in
  the campaign dir, execution `logcat.txt` 0, per-run logcats 2, `ddp-raw/` 0. 15:40:34-15:40:38 summary rebuilt from
  the git index (behind `quiet_wait.py`; temp tree in the scratchpad): `device-runs.csv` 4483 -> 4485 lines, the 2
  new rows `Pixel 8a (DDP akita-35)`; `results/summary/README.md` 1 line (4482 -> 4484 records).
- 15:42 `K/r2/session.md` written; commit (a) `a6c2059` (27 files: the campaign dir + `results/summary/`; ranking
  words 0 in the added lines; no attribution line). README quickstart (8 bullets; the clone line and the asset block
  byte for byte step 2's) and the OPERATIONS Linux line written.
- 15:44:02 phase r2-after started (model blob sha, doctor before / after and its failure paths, the Mac doctor, the
  changed doc lines in the container, a throwaway ubuntu:24.04 for the `python3-venv` phrase). Next: LINUX_FIRST_RUN.md.
- 15:44:16 the driver waits in `quiet_wait.py` (another lane's window since 15:41:27). LINUX_FIRST_RUN.md rewritten
  meanwhile (billed-run rows, Totals, findings 2-4 fixed, finding 6, Not exercised, line numbers of this commit);
  the doctor and round-2 probe cells wait for r2-after's logs.
- 15:55:52 phase r2-after done after 660 s in `quiet_wait.py` (two other lanes' windows), every step rc 0: the model
  blob `blobs/41/4194181f…` holds bytes of sha256 2a72330b…; `./bench doctor` before / after: 0 lines removed or
  changed, 4 added; `--platform ddp` exit 0 with 4 `ok`, the 5 failure paths exit 1 with their fix, the signed-out
  case without `--platform` warn / exit 0 (`K/linux/08-doctor-ddp.log`); the Mac: exit 0, the 4 DDP lines `ok`
  (huggingface_hub 1.8.0, the main checkout's engine files; adb kept off PATH) (`K/doctor-ddp-mac.log`); the
  quickstart's doctor and selftest (73 checks) exit 0, README's `sudo apt install python3-venv` exit 0, and on a
  throwaway ubuntu:24.04 the venv line rc 1 -> apt rc 0 (4 packages) -> venv line rc 0 without python3-pip
  (`K/linux/11-verify-docs.log`).
- 15:58 LINUX_FIRST_RUN.md completed from those logs; `K/linux/run_steps-r2.out` redacted as r1's (Mac home ->
  `USER`, lock labels -> `<another lane's window>`); README.md, docs/OPERATIONS.md, bench and scripts/doctor.py on
  disk = the bytes verified in the container (sha256). Next: commit (b), `docker stop`, lint, report.
- 15:59 hygiene on commit (b)'s 24 staged paths (1268 added lines: ranking words 0, user name 0, token words 0,
  e-mail 0, other lanes' labels 0, `%` only in format strings and tool output); committed by explicit path (the
  commit that carries this file; first as 0a02ba0, amended with these last lines as r1 did), not pushed.
  15:59:41 `docker stop elb-googler-first-run` -> `Exited (137)` (kept for the next round). colima left running.
  Next: lint, the report.

## 訂正

- The launch's "HEAD 9a80ef7 = r1 の commit": HEAD is c153f1d, r1's commit after an amend (+5 lines in ROUND1.md;
  9a80ef7 is on no branch) — `git reflog`, the supervisor's message 15:2x.
- "push = … model (bucket に既にある = upload は 0 のはず)": the run uploaded 1 object, the model (977,184,032 B), under
  `models/4194181f…/`: huggingface_hub 2.2.0 names the cache blob by the Hub's xetHash and `run_ddp.model_file` takes
  that 64-hex name for the sha256 (`android/ddp/run_ddp.py:190-191`); the bytes are the 2a72330b… file (the unit's
  sha256sum) — `K/linux/10-session.log`, Hub `paths-info`, `K/r2/session.md`.
- "`--platform` の choices に `ddp`" (in doctor.py) is not enough: `bench`'s own `doctor` subcommand limits
  `--platform` to `list(RUNNERS)` (mac / iphone / android), so `./bench doctor --platform ddp` needed `bench:205` too,
  a file outside the launch's list (one line) — `bench:204-205`.
- "見積 15〜30 分": 432 s from the command to the records (session 327.016 s); the gate waited 0 s / 1 s at Thermal
  Status 0, the two GPU runs took 42.7 s / 39.0 s — `K/r2/session.md`.
- "Not exercised here (`gcloud auth login` だけが残る)": `gcloud services enable` was not run either (the project has
  the API on), nor the 8-job billed run (forbidden this round), the source build, `fetch_llama_android.sh` and a gated
  model — `K/LINUX_FIRST_RUN.md` "Not exercised here".
- The launch's log names `08-doctor-ddp.log`, `09-dryrun-before-session.log`, `10-session.log` share their numbers
  with r1's `08-offline.log`, `09-versions.log`, `10-verify-readme.log` (no file overwritten) — `K/linux/`.

## 罠と袋小路

- Editing a driver script while its bash runs it: bash reads the script file by offset, so lines added above its
  current place shift what it reads once the running `case` ends (it could run a half line or an old phase's step).
  I added the r2-after phase to `K/linux/run_steps.sh` during the session, put the file back byte for byte before
  the step returned, and re-added the phase after the driver exited -> `pgrep -fl '[r]un_steps.sh'` before every edit
  of a driver, or a new file for new phases — this round, 15:3x.
- huggingface_hub 2.x (2.2.0, with hf-xet 1.7.0) lays the cache out as `blobs/<2 hex>/<name>` and names a Xet-stored
  file's blob by its xet hash, a 64-hex string that is not the sha256 of the bytes -> never take a blob name for a
  sha256; hash the bytes or read the Hub's `lfs.oid` (memory hub-bytes-need-lfs-sha-check) — `K/linux/10-session.log`.
- `bench doctor --platform` is validated twice, by `bench`'s subparser and by `scripts/doctor.py`'s: a new platform
  needs both — `bench:205`, `scripts/doctor.py` `main`.
- One Bash call's `cd` moved the session's cwd again (into the campaign dir, 15:39; the D6 trap) -> absolute paths,
  `cd` back at once.
- `awk -F,` on `results/summary/device-runs.csv` reads the wrong column (quoted fields hold commas) -> grep the
  device string or read it with a CSV reader — this round, 15:40.
- The keyword scan `imei` hits `com.google.android.onetimeinitializer` (a substring); read each hit before calling a
  logcat dirty — `K/r2/session.md`.
- `sudo apt install <pkg>` without `-y` asks Y/n and stops without a terminal: the throwaway check fed `yes |` so the
  README phrase stayed verbatim — `K/linux/steps/99-fresh-venv.sh`.
- The Mac doctor's android check runs `adb shell sha256sum` on every authorized phone: run it with the platform-tools
  directory off PATH when no phone may be touched (its devicectl line still lists the paired iPhones) —
  `K/doctor-ddp-mac.log`.
- Other lanes' windows: 0 s of waiting before the session, 660 s before r2-after (two windows back to back) — the
  waits stay outside the step durations — `K/linux/run_steps-r2.out`.

## op と delegate の観察

- GPU arm, LiteRT-LM v0.18.0 on a lab Pixel 8a (Mali): the OpenCL delegate `LITERT_CL` takes every node in one
  partition per subgraph, prefill_128 994/994, prefill_1024 994/994, decode 936/936, in both runs — `run<i>.engine.txt`.
- GPU program cache: run 1 logs `Initializing OpenCL-based API from serialized data` x3 and no `Initialized
  InferenceContext from serialized data` (Init Executor 14364.11 ms, engineCache `not-loaded`); run 2 logs both x3
  (7177.90 ms, `loaded`) — `run<i>.engine.txt`, the records.
- Both runs: `Weights preparation on Gpu is disabled for PowerVR, Broadcom, Mali GPUs …`; `NPU accelerator could not
  be loaded and registered: kLiteRtStatusErrorNotFound` x3; no E / F engine line; exit 0.
- lowmemorykiller in the per-run logcats: 19 kills (run 1), 27 (run 2); the engine exits 0 in both.
- Generated tokens 526 in both runs under `--max_output_tokens=128`, with a 514 B reply that is the same bytes in both
  runs; why the count passes the budget is 未確認 (D6 saw 526 / 536 for this GPU file).
- Cap marks: none (`protocolFlags` `[]`, every policy's ceiling at its hardware maximum before both runs); Thermal
  Status 0 -> 0; the gate waited 0 s / 1 s.
- DDP job failure text: none (session, job and execution PASSED; no `ddp/error-*.json`).
- Linux, this round: the README path needed nothing beyond r1's table 1; a stock ubuntu:24.04 needs the
  `python3-venv` package for the venv line (4 packages, python3-pip not needed); fp16 / fp32 numerics, fallback ops
  and compile failures: 未測定.

## 使った環境

- Container `elb-googler-first-run` from `ubuntu:24.04` = `ubuntu@sha256:534baea6…eb55` (Ubuntu 24.04.5 LTS, arm64);
  a throwaway container of the same image for `99-fresh-venv.sh`; colima 0.10.3 (VM Ubuntu 24.04.4, 4 CPUs, 7.7 GiB),
  Docker server 29.5.2, client 28.3.2.
- In the container: Python 3.12.3 (venv `~/elb-venv`), huggingface_hub 2.2.0, hf-xet 1.7.0, Google Cloud SDK 589.0.0.
- On the Mac (the doctor run, the summary rebuild, git): Python 3.14.6 (pyenv shim -> Homebrew), huggingface_hub
  1.8.0, Google Cloud SDK 587.0.0, git 2.54.0.
- DDP: `session-17997931` on `akita-35` in project `litert-edge-portal` (unit Pixel 8a, Android 15
  `BP1A.250405.007.B1`, serial 45231JEKB09198); LiteRT-LM v0.18.0 (android_pins); model
  `litert-community/Qwen3-1.7B` `Qwen3-1.7B_dynamic_wi4b32_afp32.litertlm` (Hub snapshot 79bf0667, the file's last
  commit 87603f0f of 2026-10-11).

## 残した file

- Commit (a) `a6c2059`: `results/raw/2026-10-16-ddp-linux-first-run-akita-35-android/` (25 files: records, raw logs,
  `ddp/` reports, the per-run logcats) and `results/summary/` (rebuilt from the git index).
- On disk only in that campaign dir: `ddp-raw/` (gitignored, the unscrubbed logcats) and the execution's `logcat.txt`
  (not staged); both stay as the audit trail.
- Commit (b), the commit that carries this file: `README.md` (quickstart, the `python3-venv` phrase), `docs/OPERATIONS.md` (the Linux session, the venv
  line and the doctor sentence), `bench` (1 line), `scripts/doctor.py` (`check_ddp`), and in K: `ROUND2.md` (this
  file), `LINUX_FIRST_RUN.md`, `r2/session.md`, `doctor-ddp-mac.log`, `linux/08-doctor-ddp.log`,
  `linux/09-dryrun-before-session.log`, `linux/10-session.log`, `linux/11-verify-docs.log`, `linux/run_steps-r2.out`,
  `linux/run_steps.sh` (the r2 phases), `linux/steps.tsv` and `linux/quiet_wait.log` (the r2 rows),
  `linux/steps/91,92,93,95,96,97,98,99-*.sh`.
- `K/linux/run_steps.done`: the waiter's marker, deleted before the commit (消してよい).
- Container `elb-googler-first-run`, stopped 15:59:41 (`Exited (137)`): the clone with this change's files copied in, the venv, the gcloud
  sign-in copy, the model in the HF cache (977 MB), the campaign dir with `ddp-raw/`, `~/doctor-before.txt` and
  `~/doctor-after.txt` (消してよい at lane close).
- Bucket `gs://litert-edge-portal-devicerun`: the new object `automation/inputs/edge-llm-bench/models/4194181f…/
  Qwen3-1.7B_dynamic_wi4b32_afp32.litertlm` (977,184,032 B, the same bytes as `models/2a72330b…/`) and the session's
  outputs; nothing deleted (the launch forbids `gcloud storage rm`; whether to remove the duplicate is the owner's).
- Scratchpad (`session_table.py`, `summary_from_index.sh`, `wait_done.sh`, the commit messages, the Hub answers):
  消してよい, removed at the end of the round.
- `K/LANE.md`, `K/colima-install.log`, `K/colima-start.log`: the supervisor's, untouched and uncommitted.
