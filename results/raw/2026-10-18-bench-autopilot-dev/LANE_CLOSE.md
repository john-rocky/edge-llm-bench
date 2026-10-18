速度梯子: N/A(bench lane で変換 lane ではない: 形の選択も ship 行も無く、数字は page の規則の中 = `K/SPEED_LADDER.md` は作らず、speed_ladder_lint は回さない)
/litert-data: N/A(LiteRT を出荷も compat 計測もしていない: gate JSON も litert-compat の device-run 行も無い。DDP の record は bench の record = campaign dir と results/summary)

# bench-autopilot lane close — the night job's follow-up made automatic, stages 0-5 (round r7, Opus 5.5, 2026-10-19)

Rounds r1-r6 (2026-10-18 19:31 - 2026-10-19 00:0x) on branches `bench-autopilot` (this worktree; stages 0-5 are on main at eee9dfdb, local), `bench-autopilot-bisect` (stage 3b, e3295a15, on PR #4's `build-from-ref`) and `bench-autopilot-googler` (stage 5, rebased onto main). This round measured nothing, ran no device, no session and no selftest, and changed no code, docs, skill or cells. K = this directory, K2 = `~/code/edge-llm-bench-wt-autopilot-bisect/results/raw/2026-10-18-bench-autopilot-bisect-dev/`, K3 = `results/raw/2026-10-18-bench-autopilot-googler-dev/`. Round notes: `ROUND7.md`. The lane's findings (168 lines: 訂正 61, 罠と袋小路 52, op と delegate の観察 24, 提案 31) are in the handoff `~/code/standup/handoffs/2026-10-19-bench-autopilot.md` §6, not repeated here.

## public 反映

Done by the rounds (all on main, local, waiting for the push GO):

| what | file | round, commit |
|---|---|---|
| the DDP section's "One command: the autopilot" paragraph and its dry-run line | `README.md` ("Run the Android cells on a Developer Device Platform phone") | r6, 0b2e28ea (704a7c4d) |
| "Lab phones without adb": the weekly slot `s26-ddp` and the switch (2 bullets), the one command (1 paragraph) | `skills/run-edge-llm-bench/SKILL.md` | r5 79d9526c, r6 0b2e28ea |
| the checker's rules, each with its source commit; the DDP kind, the Mac block, the gen-budget line | `docs/session-check-v1.md` | r1 f132add5, r5 dad937b1 / 79d9526c, the supervisor f7fec9fe |
| the post step (§1-§7), the regression response (§8), the DDP weekly slot (§9), the one command (§10) | `docs/dashboard-autopilot-v1.md` | r3 f3d5fae6, r4 d639ce96, r5 79d9526c, r6 0b2e28ea / eee9dfdb |
| the job's post hook, retake sitting, DDP slot | `docs/dashboard-recurring-job-v1.md` | r3, r4, r5 |
| the weekly slot paragraph | `docs/ddp-integration.md` | r5 79d9526c |
| the bisect tool (range, probe, verdicts, stops, limits, the revision pin, the stale-header retry) | `docs/engine-bisect-v1.md` | r2 e3295a15 (bisect branch: arrives with PR #4) |

Left (wording below; commit / push / PR are the supervisor's after the user's GO):

1. litert-samples `skills/benchmark-on-ddp/SKILL.md` (worktree `~/code/litert-samples-ddp-skill-wt`, branch `skills-benchmark-on-ddp-lab-notes` at edfe9307, not pushed): **none now.** Its routes run `litert benchmark --ddp` with the CLI's fixed benchmark flags (no prompt file, no chat template, no `--max_output_tokens`), so this lane's template / revision and budget findings do not reach its reader; the lab-unit facts this lane met (a session's jobs on separate units, capped CPU ceilings, arguments split at spaces, logcat identifiers, LiteRT-LM real prompts through edge-llm-bench) are already its Watch for lines (lines 80-89 at edfe9307). After PR #4 and stage 3b reach main, one clause could extend the edge-llm-bench bullet (lines 88-89): "… runs those with its own LiteRT-LM build, and its `scripts/engine_bisect.py` finds the LiteRT-LM commit at which one such row changes, one Device Run session per probe." Route: /litert-team, the same Draft PR as the lab notes.
2. This repo's `skills/run-edge-llm-bench/SKILL.md`, after PR #4 and stage 3b merge: one paragraph in "Lab phones without adb": "**Find the LiteRT-LM commit behind a change.** `python3 scripts/engine_bisect.py --good <ref> --bad <ref> --cells <file> --row <n> --verdict 'text:contains=<words>' --route ddp:<id> --dry-run` prints the range and the first probes; without `--dry-run` each probe is one billed session. Pin the row's model with `--row-option revision=<Hub commit>` when the range is older than the Hub file (`docs/engine-bisect-v1.md`)." Assets cell: `edge-llm-bench-autopilot` skill (hold).

## diff 一覧

### lane memory (`~/.claude/projects/-Users-USER-code-edge-llm-bench/memory/`; bytes after the memory hook stamped each file's metadata)

- new `pin-registry-is-per-platform.md` (1947 B): candidate (e) — the checker reads each platform's LiteRT-LM pin as committed at the sitting (Android `android_pins`, before 2026-10-15 the lock's `tag_built`; Mac the lock's `arms.litert-lm.mac` with `since`; iPhone `default_tag`); a build that moves without its registry line holds every sitting, and since 2026-10-18 a HOLD means no night commit.
- edit `manual-admission-reads-disk-summary.md` (1994 → 2004 B): candidate (a) — commit a sitting through `scripts/dashboard_post.py` (HEAD + the dirs in a temp index, the summary from that tree, commit-tree + update-ref CAS), the index may hold another lane's staged files; the import-time defaults now name `load_switch` and `sh(cwd=ROOT)` beside `load_rows` (r5 and r6 hit them). Condensed: the standup admit-helper path and "after a SIGTERM it can land later" dropped.
- edit `litertlm-main-two-prefill-turns.md` (2016 → 2043 B): candidate (c) — the Hub's Qwen3-1.7B since 2026-10-11 (87603f0f) gives 8 of 19 tokens on v0.16.0, v0.17.0 and the August main builds; a bisect or an old-engine comparison pins `revision=` (run_ddp honours it since e3295a15). Condensed: the parser path detail.
- edit `night-job-reads-host-drivers-as-busy.md` (2042 → 2044 B): candidate (f) — the dry run's phone calls listed (adb devices, then shell: ps, thermalservice, cpufreq, df, ls), `bench doctor` lists both platforms and shells into a single attached Android phone, the DDP preflight calls `check_ddp` alone; no-phone work puts the selftest's FAKE_ADB and an xcrun trap first on PATH.
- edit `ddp-logcat-carries-lab-network-ids.md` (1741 → 2027 B): candidate (g) — `.gitignore` keeps the execution-level `logcat.txt` out since 6e3d5908 (one campaign level; nested probe dirs carry their own), a tar or copy carries it past the ignore (this round), the ignored originals exist in one checkout and `git worktree remove` deletes them without asking (this round, checked on git 2.54.0). The `:(exclude)` staging line it replaces is no longer needed.
- edit `ci-selftest-runs-without-mac-extras.md` (1866 → 2040 B): candidate (h) — a fixture stamped N minutes before now falls into last week from Monday 00:00 to 00:N (c688d3dd).
- edit `iphone-15-off-limits.md` (2044 → 2038 B): candidate (i) — the 17 Pro's schedule entry is `auto: false` (7c0edbc2); a schedule `udid` is the UDID (a CoreDevice id never matches). Condensed to fit with the hook's metadata: dropped `scripts/bench_matrix_iphone.sh` defaulting to the 18 Pro, the DDP iPhone catalog list (16 Pro, SE 3 ×2), "a new phone is a new column", the AA-column sentence of the body (it stays in the description) and one Related link.
- `MEMORY.md`: the 6 hooks above rewritten and one line added; 6 other hooks shortened without changing what they say (secrets-get-a-risk-brief-first, ort-android-gqa-flash-l2-zero, ort-external-data-behind-links, ort-model-benchmark-is-forced-length, name-scrub-is-hygiene-only, gallery-app-benchmark-drive) so the index stays within 10 KiB: 10,200 → 10,236 bytes, 70 → 71 lines; 69 entries = 69 files, every `[[link]]` of the touched files resolves.
- not written: (b) DDP records alone carry the budget and `litert_lm_main` ignores it — the allow-list line 63ec5615 covers every DDP dashboard campaign name the job and the autopilot make (`*-dashboard-v1-*-ddp-*-android`) and the finding names it, so no session's behaviour changes; in handoff §6 (r5 op, r5 提案). (d) bazel's stale generated headers after 931ae69 — `engine_bisect.py` removes the named files and retries by itself, a per-label build without `LITERTLM_LOCAL_CHECKOUT` gets its own clone and output base, and `docs/engine-bisect-v1.md` lines 60-61 hold it; in handoff §6 (r2). Left in §6 only, as generic or self-revealing: the commit-msg hook refusing "CLAUDE.md" (its error says so), `GIT_OPTIONAL_LOCKS=0` for a read-only repo, `docker exec` without `-i`, a container's missing git identity (README's prerequisite now), the HF cache copy into a container.

### handoff

- `~/code/standup/handoffs/2026-10-19-bench-autopilot.md` (new, 65 KB): §0 事実 / §1 設計 / §2 数字 / §3 GO log / §4 訂正(→ §6) / §5 返信の材料(Googler 向け EN 6 行、Kimish / Tenghui の事実 9 行)/ §6 知見(訂正 61、罠と袋小路 52、op と delegate の観察 24、提案 31; 行頭 = 出所 round、末尾 = 証拠 path)/ §7 残り(16 項目)。

### litert-compat

- なし(/litert-data は回さない)。

### deleted intermediates (= `K/bench_autopilot_deleted_paths.txt`)

- 34 paths, 494,684 files, 17,278,038,561 bytes (≈ 17.3 GB): the bisect clone `~/.cache/apple-silicon-llm-bench/litert-lm-bisect` (2.21 GB) and its bazel output base `/private/var/tmp/_bazel_USER/b8acf263…` (6.73 GB; DO_NOT_BUILD_HERE named the clone, the md5 of the clone's path is the dir name, `server/` held no pid or socket; 222 read-only entries made writable first), the 11 `android/bin/main-*` build dirs of the bisect worktree (1.66 GB, gitignored, real dirs), six round scratchpads (r1 3.8 MB, r2 0.2 MB, r3 0.90 GB, r4 0.61 GB, r5 2.18 GB, r6 38 MB), the container `elb-autopilot-googler` (≈ 2.94 GB writable layer, docker's rounded figure), 12 test files in this worktree's `logs/dashboard-job/` (51 KB: four dry-run logs, four locks, the fake retake's cells and two empty state files, the autopilot ledger after its rows were copied below), the temp branch `autopilot-post-test` (c258edd8ad5adb635dad2fca7b77da3ed3793a33), and this round's own scratch files (1.5 MB, deleted last).

### kept, with the reason

- The three worktrees: the supervisor removes them after the merge. **Before `git worktree remove`** (it deletes ignored files without asking — checked on a scratch repo, git 2.54.0), move the ignored evidence into the main tree: this worktree's `results/raw/2026-10-18-dashboard-v1-s26-ddp-m1q-36-android/ddp-raw/` (119,056 KB) and its 16 `ddp/*/*/execution-*/logcat.txt` (87,604 KB), `K3/ddp-raw/` (812 KB), and the bisect worktree's 12 probes' `ddp-raw/` and execution logcats (8,820 KB, after its branch is merged).
- `K3/ddp-raw/container-campaign-r1.full.tar` (378,880 B, the r1 tar as r6 made it, 33 members; ignored): the committed `K3/container-campaign-r1.tar` is the same minus the execution-level `logcat.txt` (32 members, 216,576 B), which no commit carries.
- `K3/ddp-raw/container-r2/` (ignored): the r2 sitting's `ddp-raw/` (3 originals, 18 MAC addresses replaced in the scrubbed copies) and its scrubbed execution logcat, copied out of the container before `docker rm` (they existed nowhere else on this host).
- `logs/dashboard-job/ledger.tsv` and `logs/dashboard-job/2026-10-18-s26-ddp.log` (this worktree, ignored): the job ledger line and the job log of r5's billed sitting; the line is quoted in `ROUND5.md` §本物の sitting. They go with the worktree.
- The committed campaign dirs and the records in K / K2 / K3.
- Other lanes' and the pins' clones under `~/.cache/apple-silicon-llm-bench/` (litert-lm-v0.16.0, -v0.17.0, -v0.18.0, -main-20261016), the other five bazel output bases, bazel's install base and cache: not this lane's.
- The docker image `ubuntu:24.04` (534baea6a22c, D3's pull of 2026-10-16) and colima (running; the supervisor stops it).
- `FETCH_HEAD` of the googler worktree (9e310521, the bundle's objects in the shared store, unreferenced): git's own; the bundle in K3 holds the commits.
- Python `__pycache__/`, `DASHBOARD.md`, `.dashboard/`, `LEADERBOARD.md` in the worktrees (ignored, regenerated by every selftest and render; they go with the worktrees).
- Bucket objects and the Device Run sessions' outputs (remote; the drivers delete nothing).

### git

- Before this round's commit: this worktree had `K/LANE.md`, `K/GO_REQUEST.draft.md`, `K/launch-r3/r4/r6/r7*.draft.md` (the supervisor's), `K/LANE_CLOSE.md`, `K/ROUND7.md`, `K/bench_autopilot_deleted_paths.txt` (this round's) and the four K3 files untracked; nothing modified, nothing staged. The googler worktree: empty after the move. The bisect worktree: `K2/LANE.md` only.
- The four K3 files (`LANE.md`, `autopilot-commit-r2.bundle`, `container-campaign-r1.tar`, `linux/run_steps.done`) were in the googler worktree's K3, not this one's; moved here (the tar rebuilt, above) so they commit on `bench-autopilot`. The bundle verifies (`git bundle verify`: requires 7edc798d, head 9e310521).
- `launch-r7-lane-close.draft.md`: the account name in the memory dir's slug replaced by USER (the only occurrence in the committed files).
- Commits: `bench-autopilot-bisect` 53f0f226 (`K2/LANE.md`, explicit path); `bench-autopilot` = this round's one commit on eee9dfdb (the K and K3 files above, explicit paths; its hash is in the report). No attribution line, no push. main = eee9dfdb, origin/main d9762f2c (`git ls-remote`, 00:1x), 24 commits ahead before this commit.

## Open (not decided here)

- `docs/engine-bisect-v1.md`: one line "the android/bin/<label> dirs are rebuildable from the pins entry" (each `litert-lm.main-<sha9>` entry keeps `requested_tag` = the full sha and every file's sha256; `main-0252c01ea` had none) — an edit on the bisect branch after PR #4, not made here.
- The rest = handoff §7: P's check_regression with a lab-unit stand-in cell, PR #4 and the stage 3b merge, the backlog GO (the table is r1's checker), the switch-ON prerequisites (the 24-commit push, the page check), the adb route of the bisect, the profile wiring, retakes run for real 0 times, the cause of r6's `NATIVE_EXECUTABLE_FAILED`, r2's time stamps written before reading the clock, the ignored evidence before the worktrees go, the identifier of a DDP id with no record yet, the assets row, colima.

## worktree の logs/dashboard-job/autopilot-ledger.tsv(gitignored、消す前に写した全行、account 名は USER)

```
started	ended	dirs	check	bench_commit	summary_lines	page	page_commit	push_bench	push_page	publish	note
2026-10-18 20:55:05	2026-10-18 20:55:59	2026-10-14-dashboard-v1-s26-anchor-android 2026-10-14-dashboard-v1-s26-b2-android	2026-10-14-dashboard-v1-s26-anchor-android=PASS 2026-10-14-dashboard-v1-s26-b2-android=PASS	c258edd8ad5adb635dad2fca7b77da3ed3793a33	4739 -> 4772	build 0 0.2s; check_against_bench_dashboard 0 1.2s; check_regression 0 0.1s; check_aa 0 0.3s; render_check 0 48.8s		would push bench d9762f2c..c258edd8 (6 commits, 5 not made by this step)	no page commit to push	nothing to publish (no page committed by this step)	page: built and checked in /private/tmp/claude-501/-Users-USER-code-edge-llm-bench-wt-autopilot/23735949-447e-4021-86ff-49ab8546b41b/scratchpad/r3/real/page, not committed (--no-page-commit)
2026-10-18 23:29:13	2026-10-18 23:29:21	2026-10-18-dashboard-v1-s26-ddp-m1q-36-android	2026-10-18-dashboard-v1-s26-ddp-m1q-36-android=FAIL								held: 2026-10-18-dashboard-v1-s26-ddp-m1q-36-android FAIL (rules: big-file-size, logcat-unscrubbed); a sitting is committed whole or not at all
2026-10-18 23:33:44	2026-10-18 23:34:45	2026-10-18-dashboard-v1-s26-ddp-m1q-36-android	2026-10-18-dashboard-v1-s26-ddp-m1q-36-android=PASS	0c82ff2265580bb4ece034d65ce42489f23e9c4f	4739 -> 4811	build 0 0.2s; check_against_bench_dashboard 0 1.2s; check_regression 1 0.1s; check_aa 0 0.2s; render_check 0 48.3s — FAIL check_regression		would push bench d9762f2c..0c82ff22 (16 commits, 15 not made by this step)	no page commit to push	nothing to publish (no page committed by this step)	page cells: cells with a number before and none now: 0, the reverse: 0; page: not committed (a check failed; the bench commit stands); red: page and bench agree (8 red points); no red point in this sitting (8 on the page)
```

The first row is r3's test commit on the temp branch `autopilot-post-test` (c258edd8, deleted in this round), the other two are r5's real DDP sitting (held on the executions' own logcats, then committed as 0c82ff22 after 6e3d5908).
