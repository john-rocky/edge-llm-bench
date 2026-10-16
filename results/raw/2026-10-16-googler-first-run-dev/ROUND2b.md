# D3S4 Googler first run — round 2b (Opus 5.5; supervisor `edge-llm-bench-6b [6eedda]`)

Scope: `android/ddp/run_ddp.py` `model_file` takes the sha256 of the model file itself, never the name of the HF cache
blob (huggingface_hub 2.2.0 names a Xet-stored file's blob by its xet hash), and a billed run compares that hash with
the Hub's LFS sha256; a selftest check runs the real `model_file` against a fake cache; the container (huggingface_hub
2.2.0, the xet-named cache of round 2) proves it with a dry run and a second billed session that uploads nothing.
Launch: `2026-10-16-D3S4-opus-r2b.md`. K = this directory. Container steps run through `K/linux/run_steps.sh` (each
after `quiet_wait.py`), logs in `K/linux/`, this round's own files in `K/r2b/`. Other lanes' measurement windows are
named "another lane's window" here.

## 経過

- 2026-10-16 16:04 JST read the launch's files (LANE.md, ROUND2.md, r2/session.md, LINUX_FIRST_RUN.md, run_ddp.py
  1-200 / 229-330 / 399-480 / 565-656, run_cell.py 329-396, selftest.py 1-360 / 700-920 / 1168-1199,
  data-pipeline.yml 40-80, ddp-integration.md 395-460, run_steps.sh and steps 50 / 91-95, the first campaign's
  plan-1.json / request-1.json / records). HEAD 26ef70a4 = origin/main..HEAD 3 commits (c153f1d8, a6c20593,
  26ef70a4); untracked = the supervisor's LANE.md / colima logs and the first campaign's execution `logcat.txt`
  (left as they are). The plan and the request key the model `models/4194181f…/`, both records carry
  2a72330b… (`modelShaSource` device): the premise holds. Shared measurement lock empty. Next: the Hub's answers in
  both huggingface_hub versions, then the fix.
- 16:05 the Mac's huggingface_hub 1.8.0, read once by hand before another lane's window opened (16:05:05): its cache
  blob for the file is `blobs/2a72330b…` (977,184,032 B); `model_info(files_metadata=True)`'s sibling for the file
  gives size 977184032 and `lfs.sha256` 2a72330b… (`BlobLfsInfo`, a dict and a dataclass), `get_paths_info` the same
  LFS sha256 and `xet_hash` 4194181f…. So the size guard's own response already carries the LFS sha256: the fix reads
  it from that sibling (one Hub call, not a second `get_paths_info` call). The saved copy of this probe runs in the
  driver (`r2b/hub-probe-mac.log`).
- 16:07 D9 written (`android/ddp/run_ddp.py` `model_file`: `sha256_file` of the realpath, never the blob's name; on a
  billed run the size guard, then the sibling's `lfs.sha256` against the hash, a mismatch = `SystemExit`; docstring
  per the fact) and D10 (`android/ddp/selftest.py` `check_model_file`, section 1c: a fake cache
  `blobs/<2 hex>/<64 hex that is not the sha256>` behind a snapshot link, a fake `huggingface_hub` module in
  `sys.modules` under `patch.dict`, 3 checks); `py_compile` of both OK; `is_sha256` lines in run_ddp.py: 0
  (run_cell.py and record.py keep theirs). Next: the driver phases.
- 16:10 driver phases `r2b-dry` (Mac probe / selftest / dry run, then `docker start`, the 2 files into the clone,
  the container probe / selftest / blob / dry run) and `r2b-session` (the second session, then `docker cp` out) in
  `K/linux/run_steps.sh` (no driver running: `pgrep`), step files `r2b-hub-probe.py`, `r2b-hub-probe.sh`,
  `r2b-session-b.sh`; `bash -n` clean. 16:10:40 `r2b-dry` launched behind `quiet_wait.py` (another lane's window
  since 16:05:05). Next: docs while it waits.
- 16:11 the Hub's headers for the file (`r2b/hub-headers.log`, a HEAD without the redirect): `x-linked-etag`
  2a72330b…, `x-xet-hash` 4194181f…, `x-linked-size` 977184032, commit 79bf0667; huggingface_hub 1.8.0 names the blob
  by that etag (`file_download.py:1144`, `:1586`), which is why the Mac's cache never showed the gap. `K/r2b/` was
  missing when the driver started (the `mkdir` sat in a command the hook refused): made at 16:11, while the driver
  still waited before its first step. `docs/ddp-integration.md:422` "What is pushed": the cache-blob clause now says
  the file is hashed and what each huggingface_hub version names the blob (1 clause).
- 16:11:55-16:13:00 (a gap between other lanes' windows, after 75 s of waiting): `r2b-dry`'s first six steps rc 0.
  Mac (huggingface_hub 1.8.0): probe as above (`r2b/hub-probe-mac.log`); selftest `ddp selftest OK (76 checks)` exit 0
  in 42 s, the 3 new checks `ok` (`r2b/mac-selftest.log`); README step 3's dry run by the absolute path of `bench`:
  exit 0, the model's push `sha256` 2a72330b…, `object` `…/models/2a72330b…/Qwen3-1.7B_dynamic_wi4b32_afp32.litertlm`,
  `"uncached": []` (`r2b/mac-dryrun.log`). Container: `docker start`, the 2 files copied (sha256 worktree = clone:
  run_ddp.py e19903a0…, selftest.py 97e407a8…); its huggingface_hub 2.2.0 keeps the blob in a shared store
  `~/.cache/huggingface/hub/blobs/41/4194181f…` (not under the repo's folder) and gives the same `lfs.sha256`
  2a72330b… on the sibling (`BlobLfsInfo`) and in paths-info (`r2b/hub-probe-container.log`); selftest exit 0, 76
  checks, 19 s (`linux/12-selftest-fix.log`). The blob and dry-run steps wait for the next gap (another lane's window
  since 16:12:52).
- 16:14 the selftest's fake cache moved to 2.2.0's real layout (the blob in `hub/blobs/<2 hex>/<xet hash>`, the
  snapshot under `hub/models--…/snapshots/`): a test-only change after both selftest runs, so both run again on the
  final bytes before the session (fatal steps at the head of `r2b-session`).
- 16:16:15-16:16:17 the last two `r2b-dry` steps after the window closed (phase done, no failed step): the container's
  cache still links the snapshot to `blobs/41/4194181f…` and the bytes hash to 2a72330b…, 977,184,032 B
  (`linux/13-dryrun-fix.log`, step `model-blob-fix`); README step 3's dry run on `matrices/ddp-first-run.cells`
  with the fixed driver: exit 0, 1 job / 1 session / 0 skipped, the model's push `sha256` 2a72330b…, `object`
  `automation/inputs/edge-llm-bench/models/2a72330b…/Qwen3-1.7B_dynamic_wi4b32_afp32.litertlm`, `"uncached": []`
  (r2's run here: `"uncached"` before the download, the key `models/4194181f…/` in the billed run); `models/2a72330b`
  3 times in the log (push, request, upload candidates), `models/4194181f` 0 times; gcloud log files 43 / 43,
  `results/raw` entries 298 / 298 (step `dryrun-fix`). Next: the session phase.
- 16:16:56 `r2b-session` started detached (`nohup quiet_wait.py -- bash K/linux/run_steps.sh r2b-session`), the
  waiter `until [ -f K/linux/run_steps.done ]` in the background: the final bytes into the clone, the selftest in the
  container and on the Mac (both fatal), then the session (campaign `2026-10-16-ddp-linux-first-run-b-akita-35`) and
  the copy out. Session id: pending. Next: LINUX_FIRST_RUN.md's finding while it runs.
- 16:16:54-16:17:59 (no wait) the final bytes (run_ddp.py e19903a0…, selftest.py c81b46a6…; sha256 worktree = clone):
  container selftest 76 checks exit 0 in 19 s, Mac selftest 76 checks exit 0 in 45 s, 0 `FAIL` lines in either
  (`linux/12-selftest-fix.log`, `r2b/mac-selftest.log`; the word's other hits are `FAILURES.txt` in check texts).
- 16:17:59-16:23:59 step `session-b` rc 0, 360 s: `session-b1179d6d` PASSED (session 322.119 s, job 316.597 s,
  execution 239.029 s); the driver printed `in bucket:` for all 12 inputs, the model under `models/2a72330b…/`, and no
  `uploading` line; gcloud's log files of the run: 14 `auth print-access-token`, 12 `storage ls`, 1 `storage cp` = the
  pull of `automation/sessions/session-b1179d6d` (`linux/14-session-b.log`). 16:23:59 the campaign dir copied out
  (29 files, 784 KB). Records: 2, `model.sha256` 2a72330b… (`modelShaSource` device), no `FAILURES.txt`, no
  `ddp/error-*.json`, `SKIPPED.txt` empty; plan / request key `models/2a72330b…/` (`r2b/session-b.md`).
- 16:25 hygiene of the campaign dir (user name 0, token words 0, e-mail 0; the per-run logcats after the driver's
  scrub: private IPv4 0, MAC 0, IPv6 0, keyword hits only `onetimeinitializer`); lock labels in
  `linux/quiet_wait.log` and `linux/run_steps-r2b.out` -> `<another lane's window>`; the round's files: user name 0,
  other lanes' labels 0, e-mail 0, token words only selftest.py's existing `Bearer fake-token-0001` fixtures.
- 16:26 commit (a) `8e4ddad4` by explicit path (14 files, +663 / -12: the fix, the selftest, the docs clause, the
  pre-session proofs; ranking words 0 in the added lines; `%` only in format strings; author and committer
  rockyshikoku@gmail.com, no attribution line). 16:26:16 `docker stop elb-googler-first-run` -> `Exited (137)`
  (kept). Next: the summary from the index.
- 16:27 the campaign dir staged by the exclude pathspec: 25 paths, all in it, execution `logcat.txt` 0, `ddp-raw/` 0,
  per-run logcats 2. 16:27:32-16:27:33 `results/summary/` rebuilt from the git index behind `quiet_wait.py` (temp
  tree in the scratchpad): `device-runs.csv` 4485 -> 4487 lines, the 2 new rows `Pixel 8a (DDP akita-35)`;
  `results/summary/README.md` 4484 -> 4486 records. `r2b/session-b.md` written; LINUX_FIRST_RUN.md: finding 6 (the
  fix in 8e4ddad4, the second session, 0 uploads), a round 2b bullet, the intro's file list, the log hygiene
  sentence. Next: the round close, lint, commit (b).
- 16:3x round close written below; `round_close_lint.sh` PASS; commit (b) first as `b1ad604b` (34 files, +4231 /
  -13; ranking words in the added lines only a logcat line, a Hub warning and this file's own "ranking words 0").
  Next: the selftest the way CI runs it, which until then rested on reading the code (no `huggingface_hub` import).
- 16:31-16:37:26 phase `r2b-ci` (345 s in `quiet_wait.py` behind another lane's window): the committed bytes into the
  clone (sha256 = the worktree's), then `/usr/bin/python3 android/ddp/selftest.py` with the container's system Python
  3.12.3, `huggingface_hub` not importable: `ddp selftest OK (76 checks)`, exit 0, 17 s, section 1c's 3 checks `ok`
  (`linux/15-selftest-no-hub.log`). 16:37:50 `docker stop` -> `Exited (137)`. Commit (b) amended with this step (the
  driver phase, its step file and log, the driver logs' new rows, these lines) = the commit that carries this file,
  by explicit path, not pushed. Next: the report.

## 訂正

- "Hub の paths-info(`HfApi().get_paths_info(model_id, [filename])` の `lfs.sha256`)": the size guard's own
  `model_info(files_metadata=True)` answer carries the same LFS sha256 on the file's sibling (`BlobLfsInfo.sha256`)
  in both huggingface_hub 1.8.0 and 2.2.0, so the fix reads it there, one Hub call instead of two; `get_paths_info`
  gives the same value — `r2b/hub-probe-mac.log`, `r2b/hub-probe-container.log`.
- The HF cache form of D10 (`models--…/snapshots/<rev>/<file>` -> `../../blobs/<64 hex>`): huggingface_hub 2.2.0
  keeps the blob in a shared store `hub/blobs/<2 hex>/<xet hash>`, outside the repo's folder; the selftest's fake
  cache uses that layout — `r2b/hub-probe-container.log`, `linux/13-dryrun-fix.log` (step `model-blob-fix`).
- "upload 0 本(… / `uploadBytes` 0 の行)": `uploadBytes` in the driver's JSON line is the total of the upload
  candidates, printed before the bucket is checked (1,130,066,642 B in this session too, "existence not checked"),
  not what was sent; the proof of 0 uploads is 12 `in bucket:` lines, 0 `uploading` lines, and gcloud's own logs
  with no `storage cp` but the pull — `linux/14-session-b.log`.
- Commit split: the launch put ROUND2b.md and the K files in (a) and the campaign + summary in (b); LINUX_FIRST_RUN.md's
  finding names the fix's commit hash, which a file cannot do inside that same commit, so (a) = the fix, the selftest,
  the docs clause and the pre-session proofs (8e4ddad4), and (b) = the campaign, the summary and the round's record
  (this file, LINUX_FIRST_RUN.md, `r2b/session-b.md`, the session's driver logs) — `git log`.

## 罠と袋小路

- A command the quiet-window hook refuses runs none of its parts: the `mkdir -p K/r2b` that shared a command with a
  Python probe never ran, and the driver's first steps would have had no directory for their logs (made at 16:11,
  while the driver still waited) -> create directories in a command of their own before starting a driver — this
  round, 16:05 / 16:11.
- The hook judges the command text, not the load: `python3 -m py_compile` passed at 16:07 and was refused at 16:14
  (another lane's window both times), `python3 -c '<read a JSON>'` passed, `python3 <script path>` was refused -> put
  every Python run behind `quiet_wait.py` or inside the driver instead of guessing — this round.
- A test-only change after both selftest runs (the fake cache's layout, 16:14) meant both selftests ran again ->
  read the real layout (the container probe) before writing the fake — this round, about 1 min of rework.
- `model_file` sets `HF_HUB_OFFLINE=1` in the process on a dry run; an in-process call in a test leaks it to the
  later checks -> wrap it in `patch.dict(os.environ)`, as section 1c does — `android/ddp/selftest.py`.
- zsh: `for f in $FILES` over a space-separated string loops once (one "File name too long" argument), and
  `echo ====` fails (`=cmd` expansion) -> `bash -c` or an array; quote the `=` — this round, 16:2x.
- The driver's `uploadBytes` is the candidates' total, not the bytes sent (訂正 above) -> count the `uploading`
  lines, or gcloud's `Running [gcloud.storage.cp]` lines in `~/.config/gcloud/logs` written during the run.

## op と delegate の観察(環境と DDP の観察)

- huggingface_hub and the cache blob: 1.8.0 (the Mac) names it `models--litert-community--Qwen3-1.7B/blobs/2a72330b…`
  = the Hub's `x-linked-etag` (the LFS sha256; `file_download.py:1144`, `:1586`); 2.2.0 (the container) names it
  `hub/blobs/41/4194181f…` = the Hub's `x-xet-hash`, in a store shared by all repos; in both the bytes hash to
  2a72330b…, 977,184,032 B. The Hub (HEAD, no redirect): 302, `x-repo-commit` 79bf0667, `x-linked-size` 977184032 —
  `r2b/hub-headers.log`, `r2b/hub-probe-*.log`.
- Hashing on a dry run: the dry-run steps that hash the 977,184,032 B file took 1 s on the Mac and 1 s in the
  container (whole seconds of the step's clock); the billed run's own hash and Hub call were not timed (未測定).
- DDP job failure text: none (session, job and execution PASSED; no `ddp/error-*.json`).
- Cap marks: none (`protocolFlags` `[]` both runs, every policy's ceiling at its hardware maximum); the thermal gate
  and the CPU-cap wait waited 0 s before both runs; Thermal Status 0 -> 0 — `run<i>.state`, the records.
- engineCache: run 1 `gpuCache` `not-loaded` (3 `Initializing OpenCL-based API from serialized data`, no
  `Initialized InferenceContext from serialized data`, Init Executor 14360.58 ms), run 2 `loaded` (3 of each line,
  7077.98 ms); `xnnpackWeightCache` `absent` both — `run<i>.engine.txt`.
- GPU delegate: `LITERT_CL` takes every node in one partition per subgraph (prefill_128 994 / 994, prefill_1024
  994 / 994, decode 936 / 936) in both runs; `Weights preparation on Gpu is disabled for PowerVR, Broadcom, Mali
  GPUs …`; `NPU accelerator could not be loaded and registered: kLiteRtStatusErrorNotFound` x3; no E / F engine line.
- The unit: Pixel 8a, serial 45231JEKB13059, build BP1A.250405.007.B1 (not round 2's unit); lowmemorykiller `Kill`
  lines in the per-run logcats: 10 (run 1), 22 (run 2); the engine exits 0 in both.
- 526 generated tokens in both runs under `--max_output_tokens=128`, the reply 514 B and the same bytes in both runs;
  why the count passes the budget is 未確認.
- gcloud during the session (its own log files, 27): 14 `auth print-access-token`, 12 `storage ls`, 1 `storage cp`
  (the pull).

## 使った環境

- Container `elb-googler-first-run` from `ubuntu:24.04` = `ubuntu@sha256:534baea6…eb55` (Ubuntu 24.04.5 LTS, arm64),
  colima 0.10.3 (VM Ubuntu 24.04.4, 4 CPUs, 7.7 GiB), Docker server 29.5.2, client 28.3.2 (r1 / r2's record, the same
  container).
- In the container: Python 3.12.3 (venv `~/elb-venv`), huggingface_hub 2.2.0 (`r2b/hub-probe-container.log`),
  hf-xet 1.7.0 and Google Cloud SDK 589.0.0 (round 2's record; not read again this round); for CI's setup the system
  `/usr/bin/python3` 3.12.3 without huggingface_hub (`linux/15-selftest-no-hub.log`).
- On the Mac: Python 3.14.6 (pyenv shim -> Homebrew), huggingface_hub 1.8.0 (`r2b/hub-probe-mac.log`), the main
  checkout's `android/bin/v0.18.0` for the selftest and the dry run; gcloud not run on the Mac this round.
- DDP: `session-b1179d6d` on `akita-35` in project `litert-edge-portal` (unit Pixel 8a, Android 15
  `BP1A.250405.007.B1`, serial 45231JEKB13059); LiteRT-LM v0.18.0 (android_pins); model `litert-community/Qwen3-1.7B`
  `Qwen3-1.7B_dynamic_wi4b32_afp32.litertlm` (Hub commit 79bf0667).

## 残した file

- Commit (a) `8e4ddad4`: `android/ddp/run_ddp.py` (`model_file`), `android/ddp/selftest.py` (section 1c, 3 checks),
  `docs/ddp-integration.md` (1 clause); in K: `r2b/hub-probe-mac.log`, `r2b/hub-probe-container.log`,
  `r2b/hub-headers.log`, `r2b/mac-selftest.log`, `r2b/mac-dryrun.log`, `linux/12-selftest-fix.log`,
  `linux/13-dryrun-fix.log`, `linux/run_steps.sh` (the r2b phases), `linux/steps/r2b-hub-probe.py`,
  `linux/steps/r2b-hub-probe.sh`, `linux/steps/r2b-session-b.sh`.
- Commit (b), the commit that carries this file: `results/raw/2026-10-16-ddp-linux-first-run-b-akita-35-android/`
  (25 files: records, raw logs, `ddp/` reports, the per-run logcats), `results/summary/` (rebuilt from the git
  index), and in K: `ROUND2b.md` (this file), `LINUX_FIRST_RUN.md`, `r2b/session-b.md`, `linux/14-session-b.log`,
  `linux/15-selftest-no-hub.log`, `linux/steps/r2b-selftest-no-hub.sh`, `linux/run_steps.sh` (its `r2b-ci` phase),
  `linux/steps.tsv` and `linux/quiet_wait.log` (the r2b rows), `linux/run_steps-r2b.out`.
- On disk only in the second campaign dir: `ddp-raw/` (gitignored, the unscrubbed logcats) and the execution's
  `logcat.txt` (not staged); both stay as the audit trail.
- `K/linux/run_steps.done`: the waiter's marker, deleted (消してよい).
- Container `elb-googler-first-run`, stopped 16:37:50 (`Exited (137)`): the clone with the fixed files copied in, the
  second campaign dir, the venv, the gcloud sign-in copy, the model in the HF cache (消してよい at lane close).
- Bucket `gs://litert-edge-portal-devicerun`: no new input object (0 uploads); the session's outputs under
  `automation/sessions/session-b1179d6d/`; round 2's duplicate `automation/inputs/edge-llm-bench/models/4194181f…/`
  object stays (the driver deletes nothing; the owner's call).
- Scratchpad (`probe/hub_probe.py`, `session_b_table.py`, `hygiene.sh`, `summary_from_index.sh`, the commit
  messages): 消してよい, removed at the end of the round.
- `K/LANE.md`, `K/colima-install.log`, `K/colima-start.log`: the supervisor's, untouched and uncommitted.
