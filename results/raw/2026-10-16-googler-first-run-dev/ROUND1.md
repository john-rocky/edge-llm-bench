# D3S4 Googler first run — round 1 (Opus 5.5; supervisor `edge-llm-bench-6b [6eedda]`)

Scope: Linux (Docker `ubuntu:24.04` on colima) clean clone -> the README section "Run the Android cells on a
Developer Device Platform phone" step by step as user `dev` -> `android/ddp/selftest.py` exit 0 -> `--dry-run`
(no session, no billing, no phone). Launch: `2026-10-16-D3S4-opus-r1.md`. K = this directory. Container steps:
`K/linux/run_steps.sh` (each step after `quiet_wait.py`), logs `K/linux/*.log`, one row per step in
`K/linux/steps.tsv`; the Googler-readable record is `K/LINUX_FIRST_RUN.md`. Other lanes' measurement windows are
named "another lane's window" here (their labels are not this repo's).

## 経過

- 2026-10-16 14:51:40 JST read the launch's files (LANE.md, CLAUDE.md, README 1-300, android/README, OPERATIONS
  239-339, selftest 1-80 / 1150-1198, data-pipeline.yml, doctor.py, bench 1-130, run_ddp.py 1-400 / 550-655,
  matrices/README, D6 handoff §6 罠). Next: Docker check.
- 14:52:29 the Mac's measurement lock held another lane's window (pid 40881, since 14:49:30).
- 14:57:14 step 1 done: `K/linux/00-docker-info.txt` (context colima, client 28.3.2, server 29.5.2, Ubuntu 24.04.4 LTS
  VM, aarch64, 4 CPUs, MemTotal 8308289536 B; no container, no image in the VM).
- 14:59:27 the window closed. CI on main 0efecb0 (run 38745464632, ubuntu-latest x86_64, Python 3.11, no
  huggingface_hub): `ddp selftest OK (73 checks)` = the reference count for the container.
- 15:01:14 next: the step scripts `K/linux/steps/*.sh` and the driver `K/linux/run_steps.sh`.
- 15:0x supervisor correction (message): the step-10 commit leaves out `K/LANE.md`, `K/colima-install.log`,
  `K/colima-start.log` (Mac user name and other lanes' paths; the supervisor moves them at lane close).
- 15:05:31 written: `matrices/ddp-first-run.cells` (`scripts/validate_cells.py` OK on the worktree), 15 step scripts,
  the driver (`bash -n` clean; README 126-130 and 114 embedded byte for byte, checked with diff / grep -F).
  Another lane's window opened 15:03:12 (pid 2564).
- 15:05:38 driver started (`nohup quiet_wait.py --max-wait 21600 -- bash K/linux/run_steps.sh main`, pid 16007; every
  step waits for the window again). Next: README fixes drafted while it waits.
- 15:05-15:07 drafted the README fixes in the worktree: README.md step 2 gets the selftest block (fix (a)),
  android/README.md "Engine acquisition" the `$TAG` lines (fix (c); `diff` = README 127-130 byte for byte) +
  `K/linux/steps/90-verify-readme.sh` (runs the changed lines as the fixed files print them).
- 15:07:53 the window closed (driver waited 135 s); pull 6 s (`ubuntu@sha256:534baea6...eb55`, created 2026-09-18),
  run, apt-base 16 s, user (`useradd -u 1000` refused: the image's user `ubuntu` holds uid 1000 -> `userdel -r ubuntu`),
  venv probe (`python3 -m venv` rc 1, "ensurepip is not available ... apt install python3.12-venv"), apt-python,
  pip probe (`python3 -m pip install huggingface_hub` rc 1, externally-managed-environment), gcloud-install 18 s
  (google-cloud-cli 589.0.0-0). The base image already has pgrep / ps (my premise "procps is missing" was wrong).
- 15:08:39 another lane's window opened (pid 30370) while gcloud-install (started 15:08:33) ran: that step overlapped
  the window by 12 s (a step in flight is not stopped; the next one waits, 60 s here).
- 15:09:51-15:10:40 README step 1 venv 5 s (huggingface_hub 2.2.0), gcloud copy + `config set project` + TOKEN_OK +
  bucket ls 2 s, step 2 clone + asset 7 s (HEAD 0efecb0, v0.18.0, 9 sha256 OK; 11 GNU tar warnings + 10 `._*` files),
  doctor exit 0 `ready`, selftest exit 0 `ddp selftest OK (73 checks)` 17 s, dry runs: dashboard 8 jobs / 1 session /
  22 skipped / 3 uncached exit 0, first-run 1 / 1 / 0 / 1 uncached exit 0 (gcloud log files 5 -> 5), offline probe
  (network disconnected) selftest + both dry runs exit 0, versions. `phase main done` 15:10:40, no failed step.
- 15:12:30 verify phase (the fixed README.md and android/README.md copied into the clone, sha256 = worktree):
  README step 2's new block -> 73 checks exit 0; android/README fast path in a fresh dir exit 0, files = step 2's.
  `phase verify done` 15:12:50.
- 15:16:52 extra check (after quiet_wait.py): google-cloud-cli / python3 / git packages are arm64 (`K/linux/09-versions.log`).
- 15:18:26 `K/LINUX_FIRST_RUN.md` written; logs cleaned (user name -> USER, other lanes' labels, one bucket prefix
  that is not this route's). Next: round close, commit, container stop, report.
- 15:19 round close written (`round_close_lint.sh` PASS), hygiene greps clean (no user name, token value, account,
  credential file name or other lanes' label in the staged files; 0 ranking words in the added lines); committed by
  explicit path (the commit that carries this file; LANE.md and the colima logs left out), not pushed.
- 15:20:53 `docker stop elb-googler-first-run` -> `Exited (137)` (`sleep infinity` as PID 1 ignores SIGTERM, so
  docker kills it after the grace period; the container's filesystem stays for r2's `docker start`). colima left running.

## 訂正

- The launch says 起動 15:0x; the round's first `date` was 14:51:40 (the launch was readable before 15:00) — this file, line 1 of 経過.
- LANE.md D1 says `--memory 12g`; the VM has 7.738 GiB and the launch says 6g: the container runs with 6g (`Memory=6442450944`) — `K/linux/01-admin.log`.
- "README が指す公式の入れ方" — the README names no gcloud install route (README.md:100-121 at 0efecb0); the route used is https://docs.cloud.google.com/sdk/docs/install (https://cloud.google.com/sdk/docs/install answers 301 to it), "Debian/Ubuntu", newer distributions — `K/linux/steps/15-gcloud-install.sh`.
- The launch's `useradd -m -u 1000 -s /bin/bash dev` fails on ubuntu:24.04 (`useradd: UID 1000 is not unique`): the image ships user `ubuntu` at uid 1000; `userdel -r ubuntu` first — `K/linux/01-admin.log`.
- The launch's `docker cp ~/.config/gcloud …` would carry 203 MB of the Mac's gcloud command logs and the application-default credentials file; the copy is a tar stream without both (20 entries, 70 KB) — `K/linux/run_steps.sh` `h_gcloud_copy`, `K/linux/02-gcloud.log`.
- The bucket's input prefix lists 5 entries, not the 4 the launch names (`engines/ models/ prompts/ wrapper/` + one prefix that is not this route's, redacted in the log) — `K/linux/02-gcloud.log`.
- `ls android/bin/v0.18.0/` = 10 files as the launch says, but the directory holds 20 entries on Linux: 10 AppleDouble `._*` files (163 B each) come out of the asset, with 11 `LIBARCHIVE.xattr.com.apple.provenance` warnings from GNU tar — `K/linux/03-clone-asset.log`.
- The launch's expectations held: HEAD 0efecb0, selftest exit 0 (73 checks), doctor stops at `warn adb` and checks no gcloud / engine file, dashboard 8 / 1 / 22 (llama.cpp 10 + exclude-on 12), first-run 1 / 1, models `"uncached"` — `K/linux/04-doctor.log` … `07-dryrun-first-run.log`.

## 罠と袋小路

- ubuntu:24.04 already has user `ubuntu` at uid 1000: `useradd -u 1000` fails; `userdel -r ubuntu` (it prints "mail spool not found" and succeeds), then `useradd` — `K/linux/01-admin.log`.
- Stock ubuntu:24.04: `python3 -m venv` fails without `python3-venv` ("ensurepip is not available"), and pip outside a venv stops with `externally-managed-environment` (PEP 668); docs/OPERATIONS.md:261 prints exactly that pip form for the DDP route — `K/linux/01-admin.log`.
- The release asset was packed by macOS tar: on Linux expect 11 `Ignoring unknown extended header keyword 'LIBARCHIVE.xattr.com.apple.provenance'` lines and 10 `._*` files in `android/bin/<tag>/`; harmless (the driver names its 9 files). `ls | wc -l` hides them: count with `ls -A` — `K/linux/03-clone-asset.log`.
- My own premise "the base image has no procps" was wrong (pgrep / ps are there); the apt line's `procps` was a no-op — `K/linux/01-admin.log` "before install".
- A step already running is not stopped when another lane's window opens (gcloud-install ran 12 s into one); `quiet_wait.py` before every step keeps the overlap to one step — `K/linux/quiet_wait.log`, `K/linux/steps.tsv`.
- zsh: `"$U[^ ]*"` inside a double-quoted pattern is an array subscript ("bad math expression") -> `${U}`; and one Bash call's `cd` moved the session's cwd again (D6 trap) -> absolute paths only — this round, 15:17.
- The hook reads the bench keyword in an absolute worktree path: light checks on the Mac (`scripts/validate_cells.py`) ran with paths relative to the worktree root; container steps only through the driver.
- `bench`'s `$ <command>` echo lands after the tool's output for `doctor` in a file (stdout block-buffered; `do_ddp` sets line buffering, `doctor` does not); cosmetic — `K/linux/04-doctor.log`.

## op と delegate の観察

This lane = the environment and DDP observations; no device ran, so no op, delegate or fallback was observed (未測定).

- Linux lacked (stock ubuntu:24.04, aarch64): sudo, git, curl, gpg, python3 (pgrep / ps present), then `python3-venv` (ensurepip) and a pip that installs outside a venv; with them in place no README command line stopped — `K/linux/01-admin.log`, `K/LINUX_FIRST_RUN.md` table 2.
- selftest: 73 checks in 17 s on 4 aarch64 CPUs (CI's x86_64 runner: the same 73); passes with the container's network disconnected — `K/linux/05-selftest.log`, `K/linux/08-offline.log`.
- dry runs: dashboard 8 jobs / 1 session / 22 skipped (10 `runtime-not-wired-on-ddp`, 8 + 4 `exclude-on=pixel8a`), 3 models uncached (`LocalEntryNotFoundError`), 15 upload candidates 152,887,829 B, 153.5 device-minutes estimated; first-run 1 / 1 / 0, 12 candidates 152,882,610 B, 541 s = 9.0 device-minutes estimated (basis: max of 6 local Pixel 8a runs at v0.18.0); no gcloud invocation (its log-file count 5 -> 5), no campaign dir (results/raw 297 -> 297) — `K/linux/06-dryrun-dashboard.log`, `K/linux/07-dryrun-first-run.log`.
- `./bench doctor` on Linux: exit 0, `ready`, 7 warn (Mac / iPhone / adb tools), nothing about gcloud, the 9 engine files or huggingface_hub — `K/linux/04-doctor.log`.
- DDP job failure text and cap marks: なし (no session in this round).

## 使った環境

- Docker image `ubuntu:24.04` = `ubuntu@sha256:534baea6a22c03a63003dbc8dbe78fe34bc0d7e595d9a9dc9834884ff530eb55` (linux/arm64, created 2026-09-18T21:23:13Z; container `/etc/os-release` Ubuntu 24.04.5 LTS), container `elb-googler-first-run` `--memory 6g`.
- colima 0.10.3 (lima 2.2.1), VM Ubuntu 24.04.4 LTS kernel 6.8.0-117-generic aarch64, 4 CPUs, 8,308,289,536 B; Docker server 29.5.2, client 28.3.2, context `colima`.
- Python 3.12.3, pip 24.0, huggingface_hub 2.2.0 (venv `~/elb-venv`), Google Cloud SDK 589.0.0 (google-cloud-cli 589.0.0-0 arm64), git 2.43.0, GNU tar 1.35, sh = dash.
- Clone `/home/dev/edge-llm-bench` at 0efecb019c8d (+ the fixed README.md / android/README.md and `matrices/ddp-first-run.cells` copied in).
- DDP session id: なし.

## 残した file

- `matrices/ddp-first-run.cells` (new), `README.md` (step 2 selftest block), `android/README.md` (Engine acquisition `$TAG`): the change set (committed).
- `K/ROUND1.md` (this file), `K/LINUX_FIRST_RUN.md` (the record a Googler reads): committed.
- `K/linux/00-docker-info.txt`, `01-admin.log`, `02-venv.log`, `02-gcloud.log`, `03-clone-asset.log`, `04-doctor.log`, `05-selftest.log`, `06-dryrun-dashboard.log`, `07-dryrun-first-run.log`, `08-offline.log`, `09-versions.log`, `10-verify-readme.log`, `steps.tsv`, `quiet_wait.log`, `run_steps.out`, `run_steps-verify.out`: the evidence (committed).
- `K/linux/run_steps.sh` (paths rewritten to `$HOME` after the runs, same paths), `K/linux/steps/*.sh` (16 step scripts; `10-apt-base.sh`'s comment corrected after the run, commands unchanged): committed; r2 reuses the driver (`START_AT` / `ONLY`).
- `K/linux/run_steps.done`: the waiter's marker, deleted before the commit (消してよい).
- Container `elb-googler-first-run` (stopped at round end; the clone, the venv, the gcloud sign-in copy) and the `ubuntu:24.04` image in the colima VM: r2 continues with `docker start`; 消してよい at lane close (D2).
- `K/LANE.md`, `K/colima-install.log`, `K/colima-start.log`: the supervisor's files, left uncommitted (correction 15:0x).
- Scratchpad: unused.
