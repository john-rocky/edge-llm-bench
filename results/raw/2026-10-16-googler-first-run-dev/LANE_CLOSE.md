speed ladder: N/A: not a conversion lane (the lane measured a route passing and one session's records, no form to ship); `K/SPEED_LADDER.md` is not made (supervisor 2026-10-16)
/litert-data: N/A: LiteRT was neither shipped nor measured for compat here (no gate JSON, no litert-compat device-run row); the DDP records are bench records (`results/raw/2026-10-16-ddp-linux-first-run-{,b-}akita-35-android/`) and the summary

# D3S4 Googler first run on Linux + DDP skill — lane close (round 4, Opus 5.5, 2026-10-16)

Lane: README "Run the Android cells on a Developer Device Platform phone" run as written from a clean Ubuntu 24.04
container (no adb, no phone) to billed Device Run sessions on `akita-35`, the holes it found fixed, and the DDP
section of the own skill plus five Watch for notes for litert-samples (S4). Rounds r1, r2, r2b, r3 on branch
`googler-first-run` (worktree `~/code/edge-llm-bench-wt-googler`); this round (r4) measured nothing, ran no device and
no session, and changed no README, docs, skill or cells. K = this directory. Round notes: `ROUND4.md`.

## 知見 (one fact per line: source round first, evidence last)

Sources: r1 = `ROUND1.md`, r2 = `ROUND2.md`, r2b = `ROUND2b.md`, r3 = `ROUND3.md`, r4 = `ROUND4.md`, LANE = the
supervisor's lane record (`K/LANE.md`, uncommitted; the supervisor moves it to the handoffs). Paths under `K/` are in
this directory; other paths are the repo's.

### 訂正 (launch premise -> what the files say)

- r1: LANE D1's container `--memory 12g` does not fit colima's VM (7.738 GiB): the container ran with 6g (`Memory=6442450944`) — `K/linux/01-admin.log`
- r1: the README names no gcloud install route; the one used is https://docs.cloud.google.com/sdk/docs/install, "Debian/Ubuntu" (https://cloud.google.com/sdk/docs/install answers 301 to it) — `K/linux/steps/15-gcloud-install.sh`
- r1: a plain `docker cp` of the Mac's `~/.config/gcloud` would carry 203 MB of command logs and the application-default credentials file; the copy is a tar stream without both (22 entries in the container) — `K/linux/run_steps.sh` `h_gcloud_copy`, `K/linux/02-gcloud.log`
- r1: the bucket's input prefix lists 5 entries, not 4 (one prefix belongs to another route and is redacted in the log) — `K/linux/02-gcloud.log`
- r1: the round's own premise "the base image has no procps" was wrong: ubuntu:24.04 has pgrep and ps — `K/linux/01-admin.log`
- LANE: the selftest's fixed `v0.18.0` string was already gone on main (3f15f1e: `android/ddp/selftest.py:62` reads the pin); only two fixture file names keep the tag, as recorded files should — LANE §0.1
- r2: the launch named r1's pre-amend commit (9a80ef7); HEAD was c153f1d (r1 amended its commit after the launch was written) — `git reflog`, `K/ROUND2.md` 訂正
- r2: 0 uploads were expected and 1 happened: the model (977,184,032 B) went up again under `models/4194181f…/`, because huggingface_hub 2.2.0 names the cache blob by the Hub's xet hash and `run_ddp.model_file` took any 64-hex blob name for the sha256 (`android/ddp/run_ddp.py:190-191` at 26ef70a4); the records were right (the unit's own sha256sum, 2a72330b…) — `K/linux/10-session.log`, `K/r2/session.md`
- r2: `--platform ddp` in `scripts/doctor.py` alone was not enough: `bench`'s own `doctor` subcommand limits `--platform` to its runners' names — `bench:204-205`
- r2: the launch's 15-30 min for the billed run: 432 s from the command to the records (session 327.016 s; the thermal gate waited 0 s and 1 s) — `K/r2/session.md`
- r2: besides `gcloud auth login`, not exercised: `gcloud services enable` (the API was on), the 8-job billed run, the source build, `fetch_llama_android.sh`, a gated model — `K/LINUX_FIRST_RUN.md` "Not exercised here"
- r2: r2's logs `08-doctor-ddp.log`, `09-dryrun-before-session.log`, `10-session.log` share their numbers with r1's `08-offline.log`, `09-versions.log`, `10-verify-readme.log` (nothing overwritten) — `K/linux/`
- r2b: the size guard's own `model_info(files_metadata=True)` answer carries the file's LFS sha256 on its sibling in both huggingface_hub 1.8.0 and 2.2.0, so the fix makes one Hub call, not a second `get_paths_info` — `K/r2b/hub-probe-mac.log`, `K/r2b/hub-probe-container.log`
- r2b: huggingface_hub 2.2.0 keeps the blob in a store shared by all repos (`hub/blobs/<2 hex>/<xet hash>`), not under the repo's folder; the selftest's fake cache copies that layout — `K/r2b/hub-probe-container.log`, `K/linux/13-dryrun-fix.log`
- r2b: the driver's `uploadBytes` is the candidates' total printed before the bucket check ("existence not checked"), not the bytes sent; 0 uploads is proved by 12 `in bucket:` lines, no `uploading` line and gcloud's own logs with one `storage cp` (the pull) — `K/linux/14-session-b.log`
- r2b: the commit split moved (the fix and the pre-session proofs in 8e4ddad4, the campaign and the record in fa032eb2), because LINUX_FIRST_RUN.md names the fix's hash, which a file cannot do inside the same commit — `git log`
- r3: `firstEver` is set on every run up to the job's first clean one (`android/ddp/record.py:292-295`), not on run 1 only; the skill says a later run can rebuild a cache, which `firstEver` does not show — `skills/run-edge-llm-bench/SKILL.md:174-175`
- r3: the driver prints no `PASSED` line (per run `run i/2 OK`, then `campaign dir:`; the result is in `ddp/session-1.json`), and the two Linux sessions took 432 s and 360 s; the Cloudtop text says 6 to 7 min plus up to 10 min per thermal gate — `K/linux/14-session-b.log:41-45`, `K/CLOUDTOP_STEPS.md` step 6
- r3: the D6 draft's lowered-ceiling bullet ended "say so in the row", which the skill's own "Never edit a row by hand" rules out, and LiteRT-CLI's run scripts read no cpufreq file: the bullet gives the reading and what it means for a CPU number — litert-samples `skills/benchmark-on-ddp/SKILL.md:82-83` (edfe9307), LiteRT-CLI `litert_cli/commands/benchmark/ddp.py:84-150`, `:196-232`
- r3: the Cloudtop steps needed a main with this branch (`./bench doctor --platform ddp`, 76 selftest checks) while GitHub main was 0efecb0, so step 4 names the `invalid choice: 'ddp'` case — `K/CLOUDTOP_STEPS.md` step 4
- r4: PR #3 was merged into main at 2026-10-16 18:36:53 JST by rebase (main ca63a893, whose tree is the branch's 3042ec56): the six commits carry new hashes on main (c153f1d8 -> f811d624, a6c20593 -> c5ef7507, 26ef70a4 -> 1eec49f4, 8e4ddad4 -> 5cc6bf97, fa032eb2 -> 1c01475b, 3042ec56 -> ca63a893), so the skill section, the quickstart and `--platform ddp` are on main and the Cloudtop step 4 fallback no longer applies — `gh pr view 3`, `git log 0efecb01..origin/main`, `git diff --quiet HEAD origin/main`
- r4: the launch's skill-cell note said "push waits for GO" and named files by `K/`: the note says the section is on main (PR #3) and names the K files by their repo path, and the ref is the main URL with the section's anchor, which `assets.py check` can read — `~/code/standup/tools/assets/assets.jsonl` row `edge-llm-bench-ddp-backend`
- r4: the lane memory index was 10,209 B in 63 lines before this round, not 10.7 KB — `wc -c MEMORY.md`
- r4: r2's trap "the Mac doctor runs `adb shell sha256sum` on every authorized phone" is wider than the code: `check_android` hashes three files on one phone only (`BENCH_ANDROID_SERIAL`, or the single attached one) and, with two or more attached and no serial, stops before any `adb shell` — `scripts/doctor.py:192-222`

### 罠と袋小路

- r1: ubuntu:24.04 ships user `ubuntu` at uid 1000, so `useradd -u 1000 dev` fails ("UID 1000 is not unique"): `userdel -r ubuntu` first — `K/linux/01-admin.log`
- r1: on a stock ubuntu:24.04, `python3 -m venv` needs the `python3-venv` package ("ensurepip is not available"), and pip outside a venv stops with `externally-managed-environment` (PEP 668); README step 1 and docs/OPERATIONS.md now give the venv form and the package — `K/linux/01-admin.log`, `K/linux/11-verify-docs.log`
- r1: the release asset `litert-lm-v0.18.0-android-arm64.tar.gz` was packed by macOS tar: GNU tar prints 11 `LIBARCHIVE.xattr.com.apple.provenance` warnings and leaves 10 `._*` files beside the 9 engine files (harmless: the driver names its files, `sha256sum -c` passes); `ls | wc -l` hides them, `ls -A` counts them — `K/linux/03-clone-asset.log`, `K/LINUX_FIRST_RUN.md` finding 1
- r1: a step already running is not stopped when another lane's window opens (gcloud-install ran 12 s into one); `quiet_wait.py` before every step keeps the overlap to one step — `K/linux/quiet_wait.log`, `K/linux/steps.tsv`
- r1: every absolute path in an edge-llm-bench checkout holds the word `bench`, which the quiet-window hook reads: light Python checks ran with paths relative to the worktree root, the container steps only through the driver — `K/ROUND1.md` 罠
- r1: `bench` echoes `$ <command>` after `doctor`'s output when stdout goes to a file (block buffering: `matrix --ddp` sets line buffering, `doctor` does not); cosmetic, not changed — `K/linux/04-doctor.log`, `K/LINUX_FIRST_RUN.md` finding 5
- r1 / r2b / r3: zsh in the Bash tool: `"$U[^ ]*"` is an array subscript, `echo ====` a command lookup, `for f in $FILES` loops once (memory `zsh-bash-tool-traps`) — `K/ROUND1.md`, `K/ROUND2b.md`, `K/ROUND3.md` 罠
- r1 / r2 / r3: one Bash call's `cd` moved the session's cwd (into a campaign dir, into `K/linux`): absolute paths only — `K/ROUND1.md`, `K/ROUND2.md`, `K/ROUND3.md` 罠
- r2: editing a driver script while its bash runs it can make bash read shifted lines (bash reads the file by offset): `pgrep -fl '[r]un_steps.sh'` before every edit of a driver, or new phases in a new file — `K/ROUND2.md` 罠 (15:3x)
- r2: a 64-hex HF cache blob name is not a sha256 under huggingface_hub 2.x (it is the xet hash): hash the bytes or read the Hub's LFS sha256 — `K/linux/10-session.log`, memory `hub-bytes-need-lfs-sha-check`
- r2: `awk -F,` on `results/summary/device-runs.csv` reads the wrong column (quoted fields hold commas): grep the device string or use a CSV reader — `K/ROUND2.md` 罠
- r2: the keyword scan `imei` hits `com.google.android.onetimeinitializer`: read each hit before calling a logcat dirty — `K/r2/session.md`
- r2: `sudo apt install <pkg>` without `-y` asks and stops without a terminal: the throwaway check fed `yes |` so the README phrase stayed verbatim — `K/linux/steps/99-fresh-venv.sh`
- r2b: a command the quiet-window hook refuses runs none of its parts: a `mkdir -p` that shared a command with a Python probe never ran, and the driver had no log directory until 16:11; directories go in a command of their own before a driver starts — `K/ROUND2b.md` 罠
- r2b / r4: the hook judges command text, not load (`python3 -m py_compile` passed once and was refused later; `python3 -c` passed and `python3 <script path>` was refused in r2b; `python3 -c` reading assets.jsonl was refused in r4): every Python run goes behind `quiet_wait.py` or into a driver — `K/ROUND2b.md` 罠, `K/ROUND4.md` 経過
- r2b: a test-only change after both selftest runs (the fake cache's layout) meant both ran again: read the real layout (the container probe) before writing a fake — `K/ROUND2b.md` 罠
- r2b: `model_file` sets `HF_HUB_OFFLINE=1` in the process on a dry run, so an in-process test call leaks it into later checks: wrap it in `patch.dict(os.environ)` — `android/ddp/selftest.py` section 1c
- r3: the lab-identifier grep hits the names of the kinds (the two Wi-Fi acronyms) as well as values: the bullet names the kinds in words, and the patterns live only in `K/r3/grep.txt`, which is left out of its own scan — `K/r3/grep.txt`
- r3: the `[` blank check hits README.md:145's TAG line (Python subscripts): read the hit; a README line that ran is never rewritten to pass a grep — `K/r3/grep.txt`
- r3: a Mac home path went into `K/r3/pr-body.md`: grep the user name over every new K file before the commit — `K/ROUND3.md` 罠
- r3 / LANE: r3's turn ended after its reading phase (16:4x) and sat idle until the user typed 続けて at 18:17, and the supervisor's backup wait watched only for the round-close heading, so 1.5 h passed unseen; the supervisor now subscribes to the worker's idle notice right after each launch — `K/ROUND3.md` 経過, LANE §3 18:18
- r3: nothing was written to ROUND3.md for the first 1 h 40 min: the first 経過 line goes in before the reading starts — `K/ROUND3.md` 罠
- LANE: Docker Desktop's GUI did not start (twice: `com.docker.backend` killed 4 s after `open -a Docker` with "exit status 150", the GUI's "opening tray: starting electron: sending file descriptors: broken pipe"); colima from Homebrew gave a Docker daemon in about 3 min (`brew install colima`, `colima start --cpu 4 --memory 8 --disk 60`, context `colima`) — LANE §0.2 and D7, `K/colima-start.log`
- LANE: the quiet-window hook treats `docker run` / `docker exec` as heavy (`~/code/standup/tools/hooks/guard_quiet_window.py:34`): the container steps ran from one host-side driver, each step behind `quiet_wait.py` — LANE D8, `K/linux/run_steps.sh`
- LANE: the hook refused a `cat >> LANE.md` heredoc whose body held Python and bench words while another lane's window was open: notes go through the Edit tool (memory `mac-quiet-window-leaks`) — LANE §3 15:2x

### 環境と DDP の観察

- r1: a stock ubuntu:24.04 (arm64) lacked sudo, git, curl, gpg and python3 (pgrep and ps were there), then `python3-venv` and a pip that installs outside a venv; with those in place no README command line stopped — `K/linux/01-admin.log`, `K/LINUX_FIRST_RUN.md` tables 1 and 2
- r1: the container: Ubuntu 24.04.5 LTS (`ubuntu@sha256:534baea6…eb55`), Python 3.12.3, pip 24.0, huggingface_hub 2.2.0, Google Cloud SDK 589.0.0, git 2.43.0, GNU tar 1.35, `/bin/sh` = dash; colima 0.10.3 (lima 2.2.1), VM Ubuntu 24.04.4 with 4 CPUs and 7.7 GiB, Docker server 29.5.2, client 28.3.2 — `K/LINUX_FIRST_RUN.md` "Environment", `K/linux/00-docker-info.txt`
- r1: the selftest ran 73 checks in 17 s on 4 aarch64 CPUs, the count of CI's x86_64 runner, and passed with the container's network disconnected — `K/linux/05-selftest.log`, `K/linux/08-offline.log`
- r1: the launch's counts held: HEAD 0efecb0, doctor stopping at `warn adb`, the dashboard dry run 8 jobs / 1 session / 22 skipped (10 `runtime-not-wired-on-ddp`, 8 + 4 `exclude-on=pixel8a`), first-run 1 / 1 / 0, the models `"uncached"` — `K/linux/04-doctor.log` to `K/linux/07-dryrun-first-run.log`
- r1: the dry runs call no gcloud (its log files 5 before and after) and write no campaign directory; first-run: 12 upload candidates, 152,882,610 B, an estimate of 541 s = 9.0 device-minutes (basis: the max of 6 local Pixel 8a runs at v0.18.0); dashboard: 153.5 device-minutes — `K/linux/06-dryrun-dashboard.log`, `K/linux/07-dryrun-first-run.log`
- r1: `./bench doctor` on Linux before the fix: exit 0 `ready` with 7 warnings and nothing about gcloud, the engine files or huggingface_hub (its huggingface_hub line sat behind the adb check) — `K/linux/04-doctor.log`
- r2: `./bench doctor --platform ddp` after the fix: 4 `ok` lines; before / after = 4 added lines, 0 changed; its 5 failure paths each exit 1 with one `FAIL` line and the fix; without `--platform` the signed-out case is a warning, exit 0 — `K/linux/08-doctor-ddp.log`
- r2: `session-17997931` on akita-35 PASSED (session 327.016 s, job 322.500 s, execution 228.518 s), 432 s from the command to the records, 2 records stamping v0.18.0 and model sha256 2a72330b… (read on the unit), `protocolFlags` `[]`, Thermal Status 0 -> 0 — `K/r2/session.md`
- r2b: `session-b1179d6d` on akita-35 PASSED (session 322.119 s, job 316.597 s, execution 239.029 s), 360 s from the command to the records, 0 uploads, on another lab unit than r2's — `K/r2b/session-b.md`
- r2 / r2b: the GPU delegate `LITERT_CL` took every node in one partition per subgraph (prefill_128 994 / 994, prefill_1024 994 / 994, decode 936 / 936) in all four runs; "Weights preparation on Gpu is disabled for PowerVR, Broadcom, Mali GPUs"; "NPU accelerator could not be loaded and registered" x3; no E or F engine line — `run<i>.engine.txt` in both campaign dirs
- r2 / r2b: the GPU program cache: run 1 `not-loaded` (Init Executor 14364.11 ms, 14360.58 ms), run 2 `loaded` (7177.90 ms, 7077.98 ms); `xnnpackWeightCache` `absent` in all four — the records' `conditions.engineCache`, `run<i>.engine.txt`
- r2 / r2b / r4: 526 generated tokens in every run under `--max_output_tokens=128`, the reply 514 B and the same bytes in all four runs (r4 hashed the text between `input_prompt:` and `BenchmarkInfo:` in both sessions' `run<i>.engine.txt`: one sha256); why the count passes the budget is 未確認 (D6 saw 526 and 536 for this file) — `K/r2/session.md`, `K/r2b/session-b.md`, `K/ROUND4.md` 経過
- r2 / r2b: lowmemorykiller `Kill` lines in the per-run logcats (19 and 27, 10 and 22) while the engine exited 0 — `K/ROUND2.md`, `K/ROUND2b.md` op
- r2b: huggingface_hub 1.8.0 (the Mac) names the cache blob by the Hub's `x-linked-etag` (the LFS sha256; `file_download.py:1144`, `:1586`), 2.2.0 (the container) by `x-xet-hash` in the shared store; the bytes are the same, 2a72330b…, 977,184,032 B — `K/r2b/hub-headers.log`, `K/r2b/hub-probe-mac.log`, `K/r2b/hub-probe-container.log`
- r2b: hashing the 977 MB model on a dry run took about 1 s on the Mac and in the container (the step clock); the billed run's hash and Hub call were not timed — `K/r2b/mac-dryrun.log`, `K/linux/13-dryrun-fix.log`
- r2b: gcloud during a billed session (its own log files): 14 `auth print-access-token`, 12 `storage ls`, 1 `storage cp` (the pull) — `K/linux/14-session-b.log`
- r2b: the selftest passes with the container's system python3 and no huggingface_hub (CI's setup): 76 checks in 17 s — `K/linux/15-selftest-no-hub.log`
- r2: other lanes' measurement windows held the container steps 0 s before the session and 660 s before r2's checks; the waits stay outside the step durations — `K/linux/run_steps-r2.out`, `K/linux/quiet_wait.log`
- r3: LiteRT-CLI main 59d612e (2026-10-12) still runs a `.litertlm` bundle's DDP job with fixed benchmark flags and pushes no prompt (`litert_cli/commands/benchmark/ddp.py:526-553`, `:556-587`, `:625`) — `K/r3/litert-cli-ddp-check.md`
- r3: litert-samples upstream main 2166c0f9: `skills/benchmark-on-ddp` has three Watch for bullets, and no open upstream PR touches them (the last, #396, merged 2026-10-07) — `K/ROUND3.md` 経過 16:40, 18:20
- r3: re-read from committed records: a session's 8 jobs start within 0.048 s and 0.018 s on 8 units per id; the smoke request's 13 args arrive as `argc: 18`; every m1q-36 run state of the 2026-10-15 slice reads `cpucap_caps= policy0 3187200/3628800 policy6 3398400/4742400`, akita-35's are empty — `K/ROUND3.md` "S4-B"
- LANE: only the project owner's account can create Device Run sessions in project litert-edge-portal today (IAM read 15:2x); another account needs a grant (roles/editor) or a project of its own — LANE §3 15:2x, `K/CLOUDTOP_STEPS.md` step 6
- LANE: `litert-community/Qwen3-1.7B` is not gated; the first run needs no Hugging Face token — LANE §0.4
- LANE: CI run 38879453248 on the pushed branch: 5 jobs green, the DDP selftest step 1 min 17 s on the x86_64 runner — LANE §3 18:19

## public 反映

D6's lane close proposed the own skill section and the litert-samples Watch for bullets; this lane wrote both.

| target | what | state |
|---|---|---|
| own repo `skills/run-edge-llm-bench/SKILL.md`, `skills/README.md` | the section "Lab phones without adb (Developer Device Platform)": the dry run and the billed run, what the host needs and what `./bench doctor --platform ddp` checks, one job = one lab unit, the cap marks, the fields only a DDP record carries, the logcat scrub; the description and Tested on (four DDP sessions) | done in r3 (3042ec56); on GitHub main since PR #3 (ca63a893). The assets row's `skill` cell stays `todo` until a blind run |
| own repo README, docs, doctor, driver | README quickstart (8 bullets), the selftest step that closes README step 2, `python3-venv` in step 1, docs/OPERATIONS.md's venv form and Linux line, `./bench doctor --platform ddp`, android/README.md's tag from `android/engine-pins.json`, `run_ddp.model_file` hashing the file and selftest section 1c (76 checks), `matrices/ddp-first-run.cells` | done in r1-r2b; on main since PR #3 (CI run 38879453248 green on the branch) |
| litert-samples `skills/benchmark-on-ddp/SKILL.md` | five Watch for bullets (lines 80-89: a session's jobs at once on separate units, lowered CPU ceilings on some units, job args split at spaces, pulled logcats carry the lab network's identifiers, a LiteRT-LM run with a real prompt file is outside the CLI's DDP target); the Draft PR body, EN with a JA copy, in `K/r3/pr-body.md` | committed edfe9307 on branch `skills-benchmark-on-ddp-lab-notes` (worktree `~/code/litert-samples-ddp-skill-wt`, base upstream/main 2166c0f9), not pushed: push and `gh pr create --draft` wait for the user's GO (the supervisor's) |
| litert-samples `skills/on-device-verification`, `litert-conversion-workflow` | none: this lane checked no conversion and no parity | — |
| hf-to-litertlm (tools, docs, AGENTS.md Route row, llms.txt) | none: not a conversion lane | — |
| `~/code/standup/knowledge/litert.md` | one line (below) | done in this round, staged |
| the first-run steps for a Linux workstation | `K/CLOUDTOP_STEPS.md` (six steps, each with its expected output and what to do when it stops) | the brief session moves them into its Doc (the user pastes) |
| the reply | `K/REPLY_MATERIALS.md` (facts with their sources, two sentences EN / JA) | the user decides; nothing sent |

## lane memory (rules and traps only)

Dir `~/.claude/projects/-Users-USER-code-edge-llm-bench/memory/` (the main checkout's slug).

- new `docker-desktop-down-use-colima.md` (2,009 B, feedback; launch candidate (a)): when Docker Desktop will not start, `brew install colima` + `colima start --cpu 4 --memory 8 --disk 60` gives a daemon in about 2 min; the VM's memory is set at start; `docker ps -a` lists one context only (check both before calling a container an orphan); the hook blocks `docker run` / `docker exec`, so container steps go in a host-side driver behind `quiet_wait.py`; `Exited (137)` of a `sleep infinity` container is normal; who stops or uninstalls colima. It leaves out what the ~/code side's `docker-vm-memory-stop-containers` says (stop containers at round end) and links it.
- edited `hub-bytes-need-lfs-sha-check.md` (1,927 -> 2,014 B, folded, not appended): + an HF cache blob's name is no sha256 (huggingface_hub 1.8.0 names it by the LFS sha256, 2.x a Xet-stored file by its xet hash in a shared `hub/blobs/<2 hex>/` store), the run_ddp case and its fix (main 5cc6bf97), "hash the bytes, never trust a name"; trimmed to fit: the archive dir names, the PLE sidecar example, the device-busy link.
- `MEMORY.md`: 10,209 -> 10,363 B, 63 -> 64 lines: + 1 line (the new file, a short hook), 1 hook rewritten (the edited file); no other line touched. The index was over the 10 KB bar before this round and stays over it.

Not written (one line each):
- (b) "the DDP Linux first run passes the README as written / where it stopped": the stops were fixed in README, docs and doctor, and the run is `K/LINUX_FIRST_RUN.md`: the repo records it.
- (c) "an assets skill cell without a blind run is todo": `~/code/standup/tools/assets/README.md` already says it ("one blind run by an agent that did not write it").
- a driver script edited while bash runs it (r2): general bash behaviour, caught inside the round; nothing specific to this repo.
- a command the hook refuses runs none of its parts (r2b): the denial says the command did not run, and `mac-quiet-window-leaks` already says the hook reads whole commands.
- absolute paths here hold the word `bench` (r1): `mac-quiet-window-leaks` already names paths among what the hook reads.
- the worker's idle notice and the first 経過 line (r3, LANE): the supervisor's procedure, which belongs in skill opus-rounds; LANE §3 18:18 records it.
- `uploadBytes` is the candidates' total (r2b): the driver's own line says "existence not checked".
- the Mac doctor touching phones (r2): the code touches at most one phone with three short `sha256sum` calls (r4 訂正); not a six-week trap.
- ubuntu:24.04's uid 1000, `python3-venv`, PEP 668 (r1): README, docs/OPERATIONS.md and `K/LINUX_FIRST_RUN.md` carry them.
- the release asset's macOS metadata (r1): harmless; its fix is a packing change at the next pin bump (open item below), recorded as `K/LINUX_FIRST_RUN.md` finding 1.
- 526 generated tokens under a 128-token budget (r2, r2b): 未確認, not a rule.

## diff 一覧

Memory: new `docker-desktop-down-use-colima.md`, edited `hub-bytes-need-lfs-sha-check.md`, `MEMORY.md` + 1 line and 1
hook rewritten (the section above).

Assets row `edge-llm-bench-ddp-backend` (`~/code/standup/tools/assets/assets.py set`, behind `quiet_wait.py`: it waited
630 s for two other lanes' windows and ran at 18:56:55 JST):
- `skill`: hold -> **todo**, ref `https://github.com/john-rocky/edge-llm-bench/blob/main/skills/run-edge-llm-bench/SKILL.md#lab-phones-without-adb-developer-device-platform`
  (HTTP 200; main's file holds the heading once), note "section added 2026-10-16 in edge-llm-bench (lane D3S4 r3), on
  main since PR #3 merged it (rebase, ca63a893); blind run pending (an agent that did not write it runs the section
  cold); litert-samples Draft PR body in edge-llm-bench results/raw/2026-10-16-googler-first-run-dev/r3/pr-body.md
  (litert-samples branch skills-benchmark-on-ddp-lab-notes, commit edfe9307, not pushed; GO first)".
- `article`: stays **hold**; the note gains "; reply material: edge-llm-bench
  results/raw/2026-10-16-googler-first-run-dev/REPLY_MATERIALS.md (Linux first run)".
- `set` x2 and `render`: rc 0 each, `rendered … state/assets.md (103 lines, 98 open) and … knowledge/assets-ledger.md
  (118 rows)`. The three ledger files differ from their pre-run copies and from standup HEAD in this row only
  (assets.jsonl 1 line, state/assets.md 1 line, assets-ledger.md 2 lines).
- Lint, exit **3** (HOLD, as expected: a todo cell and a hold cell remain):
  `HOLD edge-llm-bench-ddp-backend [tool] 4/6 done — open: skill=todo(section added 2026-10-16 in edge-llm-bench (lane D), article=hold(user decides; the share is the dashboard thread (r)`
  `     next: ` (the row's `next` is empty; this round changed cells through `set` only).

Knowledge: `~/code/standup/knowledge/litert.md` + 1 line at the end (line 58, "- 2026-10-16 edge-llm-bench Googler
first run on Linux (lane D3S4): …"), `git diff --numstat` 1 / 0.

Staged in `~/code/standup` by this round, not committed (the supervisor commits them with the handoff):
`knowledge/litert.md`, `tools/assets/assets.jsonl`, `state/assets.md`, `knowledge/assets-ledger.md`
(`git diff --cached --name-only` = these four; nothing else was staged there).

Deleted (`K/googler_first_run_deleted_paths.txt`): the container `elb-googler-first-run` (writable layer 2.769 GB: the
clone, the venv, the HF cache with the 977 MB model, the gcloud sign-in copy, the apt packages), removed 18:49:51 after
the carry-out check (`K/linux/` 55 of 55 files tracked; both campaign dirs in the container byte-identical to this
tree's, 25 files each tracked; the environment's versions in `K/LINUX_FIRST_RUN.md`); this round's scratchpad. The
earlier rounds' scratchpads were already empty.

Kept, with the reason:
- image `ubuntu:24.04` (534baea6a22c, 141 MB): small, and the launch keeps it.
- colima and its VM (running, context `colima`): `colima stop` is the supervisor's; `brew uninstall colima lima` only on
  the user's word.
- each campaign's `ddp-raw/` (3 files each, gitignored): the logcats before the scrub = the originals.
- each campaign's execution-level `logcat.txt` (untracked, scrubbed in place): out of every commit; the audit trail.
- the bucket's objects, the duplicate `models/4194181f…/` (977,184,032 B) among them: the driver deletes nothing; the
  owner decides (LANE D11).
- litert-samples worktree `~/code/litert-samples-ddp-skill-wt` and its branch: the Draft PR's head, waiting for the GO.
- `K/LANE.md`, `K/colima-install.log`, `K/colima-start.log`: the supervisor's, uncommitted.
- the Mac's HF cache: other lanes' blobs, not touched.

Worktree commits (`git log --oneline origin/main..HEAD` after `git fetch origin main`; main carries the first six as
rebased copies, see 知見 r4):
- c153f1d8 README DDP section gets a selftest step after the clone, android/README.md engine acquisition … (r1)
- a6c20593 results 2026-10-16 DDP akita-35 driven from a Linux host: one Device Run session (session-17997931) … (r2)
- 26ef70a4 README gets a quickstart for the Android cells on a DDP lab phone … (r2)
- 8e4ddad4 android/ddp/run_ddp.py model_file keys the model by the sha256 of its bytes … (r2b)
- fa032eb2 results 2026-10-16 DDP akita-35 driven from the Linux host again, after the model sha fix … (r2b)
- 3042ec56 skills/run-edge-llm-bench gets a section on DDP lab phones without adb … (r3)
- this round's commit, which carries this file (K files only: LANE_CLOSE.md, ROUND4.md, googler_first_run_deleted_paths.txt)

litert-samples worktree commit: edfe9307 `skills/benchmark-on-ddp: add five Watch for notes on lab units, job
arguments, pulled logcats and LiteRT-LM prompt runs` (1 file, +10 / -0; worktree clean), not pushed.

litert-compat: no commit (no `/litert-data`). Handoff: written by the supervisor (`handoffs/2026-10-16-D3S4-googler-first-run-ddp-skill.md`);
its §知見 takes the 知見 section above.

## Open for the supervisor (not decided here)

- This round's commit sits on `googler-first-run`, which main already took by rebase (PR #3): it needs its own push and
  PR, or a cherry-pick onto main (the trees are equal up to it).
- The assets row: `next` is empty; the `tests` note still says 73 checks (76 since main 5cc6bf97); `dir` names the D6
  worktree.
- android/README.md:37 still names `LITERTLM_TAG=v0.17.0` in the source-build line (not run in this lane, left as it is).
- The release asset's macOS metadata (finding 1): a repack with `COPYFILE_DISABLE=1 tar --no-mac-metadata --no-xattrs`
  at the next pin bump (a proposal; this Mac's tar took the same flags in r1's gcloud copy).
- 526 generated tokens under `--max_output_tokens=128` (four runs in two sessions here, and D6): 未確認.
- `colima stop`; the litert-samples Draft PR (push and `gh pr create --draft` after the user's GO); the bucket's
  duplicate model object.
