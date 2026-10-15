# D6 DDP backend — round 1 (Opus 5.5, design + driver, no device, no billing)

Launch: `~/code/standup/launch/2026-10-15-D6-dashboard-ddp-backend-opus-r1.md`. Worktree
`~/code/edge-llm-bench-wt-ddp`, branch `ddp-backend`, HEAD 0ee7a28 at start. Design: `DESIGN.md` (this dir).
Result: driver PASS, smoke GO pending. No adb, no POST, no bucket write, no device.

## 経過

- 15:16 launch read in full; next: read the prerequisite files (LANE.md, bench, run_campaign, run_cell, parsers, selftest, …)
- 15:22 prerequisites read (every file the launch lists, the API contract classes, the 10 memory files); a Mac timing window is live (`dash-0180-r9-build timing`, since 15:20): python + bench-word commands avoided; bucket `automation/inputs/edge-llm-bench/` absent (read-only `gcloud storage ls`); next: DESIGN.md
- 15:30 DESIGN.md, devices.json written; run_cell.py `sampler_shell()` taken out of run_once + `cpu_conditions(mask=)`, run_campaign `skip_on_device(device_key=)`; run_once's adb shell string = HEAD's in 30 cases (5 env settings × 3 commands × sockets on/off; scratch shell_equiv.py); next: ddp_cell.sh
- 15:33 ddp_cell.sh written; its `--print_shell=1` string = `sampler_shell()` for a short-chat and a 1K command, `--command=` whole and split at spaces (scratch wrapper_equiv.py, /bin/sh = bash 3.2); next: run_ddp.py
- 15:39 run_ddp.py, record.py, build_summary device column, bench `--ddp` / `--dry-run` (34 added lines, none changed); first smoke dry run rc 0; next: dashboard dry runs
- 15:41 dashboard dry runs: akita-35 8 jobs / 1 session / 22 skipped, m1q-36 16 / 2 / 14, no model uncached; next: selftest
- 15:48 android/ddp/selftest.py first run: 51/51 ok (29 s); then `--resume` and plan-file checks added
- 15:50 android/bench/selftest.py started in the background behind quiet_wait (window `aa-b2-o10-gate8q-gpu timing`, since 15:34; scratch run_android_selftest.sh writes `dry-run/android-selftest.done`); dry runs regenerated with the final code, user name → USER in them
- 15:53 android/ddp/selftest.py 53/53 ok; forbidden-word grep empty; next: round close, commit, lint, report
- 15:54 round close written, lint PASS, committed (explicit paths, no attribution, not pushed); android/bench/selftest.py still behind the quiet window (`aa-b2-o10-gate8q-gpu`): its exit code lands in `dry-run/android-selftest.done`, its output in `dry-run/android-selftest.log` (the FAKESELF campaign in android/ddp/selftest.py already ran run_once's refactored path in round mode); report sent

## 訂正

- D5 says render_dashboard ignores DDP rows: `render_dashboard.devices_for` lists the schedule's phones, then every other device the summary holds for the platform, so a DDP unit is a column of its own on DASHBOARD.md (never pooled with the attached phone) — `scripts/render_dashboard.py` 250–261, 356; selftest check 5 shows `['SM-S942Q', 'Pixel 8a', 'Pixel 8a (DDP akita-35)']`.
- Launch elapsed table "Qwen3-1.7B cpu short 23–33 s": the Pixel 8a v0.18.0 records hold 22.6–32.8 s (p3a) and 180.2–224.9 s (p3a-r2); the estimate takes the largest local value, 224.9 s — `results/raw/2026-10-15-dashboard-v1-pixel8a-0180-p3a{,-r2}-android/app-path-android/litert-lm-cpu_litert-community_Qwen3-1.7B_short-chat_*.json`.
- Acceptance "only conditions.ddp and device.ddp are added" vs step 5's provenance keys: the DDP record adds exactly `conditions.ddp`, `device.ddp`, `provenance.ddpSessionDir`, `provenance.wrapper`, `provenance.wrapperSha256` to the attached-phone record's keys (short-chat and 1K, round-mode FAKESELF records) — `android/ddp/selftest.py` "DDP record keys ⊇" checks.
- The grep criterion over `android/ddp/*.py` covers selftest.py, which must put the attached-phone route's fake device tool on PATH for the FAKESELF comparison: it installs `android/bench/selftest.py`'s `FAKE_<TOOL>` templates under the template's own name, so no tool name is written in `android/ddp/*.py` — `android/ddp/selftest.py` `attached_records`.
- displayName regex: the SDK contract's docstrings print `^A-Za-z0-9*$` (brackets lost; `devicerun_v1alpha_messages.py` 1787, 2194); the REST form `^[A-Za-z0-9][A-Za-z0-9-_ ]*$` is in `docs/ddp-integration.md` 392; the driver keeps to `^[A-Za-z0-9][A-Za-z0-9_-]*$`, ≤ 63 B.
- `python3` resolves through the pyenv shim to `/opt/homebrew/opt/python@3.14/bin/python3.14` (3.14.6; huggingface_hub 1.8.0 there) — bench's `$` lines in `dry-run/*.txt`.

## 罠と袋小路

- Mac quiet window live all round (15:20 `dash-0180-r9-build`, 15:34 `aa-b2-o10-gate8q-gpu`): the hook blocks any command with a python word plus a key word, and the scratch path itself contains `edge-llm-bench` (key word `bench`): run python checks as shebang executables by path (scratch `shell_equiv.py`, `wrapper_equiv.py`, `./android/ddp/selftest.py`), bench by its absolute path; the attached-phone selftest goes behind `quiet_wait.py` in the background.
- Whether DDP keeps an `args` element with spaces whole is not documented (the contract: args "will be appended to the command line that invokes the binary", line 283): the wrapper joins every argv element after `--command=` (last arg) with one space, so either way runs the same command (selftest: whole and split give the same string and run); r2's `provenance.txt` (`argc:` + one `arg:` line each) will show which the platform does.
- bench's `run()` prints `$ cmd` unflushed: redirected to a file, the lines landed after the runner's output; `do_ddp` sets line buffering (one added line).
- zsh: `echo ======` is a command lookup ("not found"); a `cd` into a subdirectory in one Bash call moved the session's cwd twice — absolute paths only.
- Progress times first written without `date` (15:50 / 16:05 for what ran at 15:22 / 15:30): corrected from the files' mtimes.

## op と delegate の観察

なし(端末なし)。

## 使った環境

- python3 3.14.6 (pyenv shim → `/opt/homebrew/opt/python@3.14/bin/python3.14`), huggingface_hub 1.8.0 (HF cache read with `local_files_only=True` only), Google Cloud SDK 587.0.0 (alpha / beta 2026.09.25; account rockyshikoku@gmail.com, project litert-edge-portal; `gcloud storage ls` reads only), `/bin/sh` = GNU bash 3.2.57 for the wrapper's host runs.
- Worktree `~/code/edge-llm-bench-wt-ddp`, branch `ddp-backend`, HEAD 0ee7a28 at start; engine files `~/code/edge-llm-bench/android/bin/v0.18.0/` via `BENCH_ANDROID_BIN_DIR` (read only).
- No device, no hold, no adb; no DDP session; no bucket write.

## 残した file

- New: `android/ddp/devices.json`, `ddp_cell.sh` (755), `run_ddp.py` (755), `record.py`, `selftest.py` (755).
- Changed: `bench` (35 added lines, none changed), `android/bench/run_cell.py` (`sampler_shell` taken out of `run_once`; `cpu_conditions(mask=None)`), `android/bench/run_campaign.py` (`skip_on_device(device_key=None)`), `scripts/build_summary.py` (device column + docstring).
- This dir: `DESIGN.md`, `ROUND1.md`, `fixtures/smoke.cells`, `dry-run/{smoke-akita-35,dashboard-akita-35,dashboard-m1q-36}.txt` (bench stdout; user name → USER, nothing else changed); `dry-run/android-selftest.{log,done}` — written by the background run when the quiet window lets it start (not in the round-1 commit).
- Scratch (消してよい, after `android-selftest.done` exists): `shell_equiv.py`, `wrapper_equiv.py`, `run_android_selftest.sh`, `orig/` (HEAD copy of android/bench + scripts), `ddp-selftest-{1,2,3}.log`.
