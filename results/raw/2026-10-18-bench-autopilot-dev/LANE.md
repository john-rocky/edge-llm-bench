# bench-autopilot — supervisor's lane record (Fable 5.1, edge-llm-bench-55 [4f120b], started 2026-10-18 19:14 JST)

Goal (user 2026-10-18, via code-2d): nobody does anything by hand, and when LiteRT-LM gets slower on one of the bench
devices the team page carries the point next morning with a re-measurement, the candidate cause (LiteRT-LM commit range,
per-op profile where a device gives one) and an issue draft; a Googler runs the same flow on DDP with one command.

Stages: 0 iPhone 17 Pro out of auto (done) / 1 session checker / 2 job -> checker -> commit -> summary -> page, switch OFF /
3 regression response (re-measure, bisect via PR #4 build-from-ref, profile, issue draft) / 4 D6 DDP weekly slot / 5 Googler one command.

Worktree: ~/code/edge-llm-bench-wt-autopilot, branch bench-autopilot (from main). K = this directory. Main tree is the night
job's; merges into main only after a dry run passes; stage explicit paths only.

## Premise corrections (read 19:1x-19:3x)
- The 17 Pro udid in schedule.json was the CoreDevice id; iphone_attached never matched; auto reported "not available to
  devicectl" at every 05:30 firing since at least 2026-10-10 (logs/dashboard-job/*-auto.log). The 10-17 03:45 sitting was
  the AA lane's by-hand run with a corrected copy (.dashboard/0180_aa_20261014/device/ios/schedule-17pro.json).
- The main tree's schedule.json carried an uncommitted removal of the Pixel 8a reboot_before block (10-17 01:51, owner's
  words): committed on main as d4f6794c so the file is clean to merge.
- backlog: `git status --porcelain results/raw` = 100 lines = 77 dirs; 68 carry -dashboard-v1-; 10 of those (10-16 DDP
  s3..s16) are committed with execution-level logcat.txt leftovers, so 58 dashboard dirs are wholly uncommitted.
- Kimish 09-28 row ("continuous runs + re-run-with-profiling") not found in state/knowledge by grep: unverified. Found
  instead Kimish 09-14 23:01 "exactly the kind of automated profiling diagnosis we should aim to have" (knowledge l.1199).

## Stage 0 (supervisor, no Opus round: a one-commit config change)
- 7c0edbc2 on main (ff from bench-autopilot): iphone17pro `auto: false` (state by-hand), udid = devicectl UDID, selftest
  case, docs §3 / §9 / reboot paragraph. Dry run from the worktree: `iphone17pro  by-hand  auto: false, by hand only; last
  admitted 2026-10-17 04:11`; selftest OK (worktree and main tree).

## Stage 1 — round r1 (Opus 5.5): scripts/session_check.py
- launch: ~/code/standup/launch/2026-10-18-autopilot-session-check-opus-r1.md
- 19:31 r1 launched (cmux workspace:359, worker edge-llm-bench-wt-autopilot-2b [9fbf04]); idle notice subscribed.

## Stage 3b — round r2 (Opus 5.5, parallel, DDP only): scripts/engine_bisect.py
- worktree ~/code/edge-llm-bench-wt-autopilot-bisect, branch bench-autopilot-bisect from origin/build-from-ref c4ed5da3
  (PR #4 head: build_litert_lm_main.sh LITERTLM_REF, pins_add.py, bench matrix --ddp --engine-build). K2 = its
  results/raw/2026-10-18-bench-autopilot-bisect-dev/. launch: ~/code/standup/launch/2026-10-18-autopilot-bisect-opus-r2.md
- 19:38 r2 launched (workspace:360, worker edge-llm-bench-wt-autopilot-bisect-b2 [0f4832]); idle notice subscribed.
- Facts behind the launch: a DDP run log carries the reply text (10-16 s3 GPU log line 187) and `Prefill Turn 1: Processed 19
  tokens`; DDP records carry no outputSample; run_ddp.py takes --engine-build <label>; build script clones per label with
  --depth 1 (cold bazel each time) -> the round uses one bisect clone; local toolchain: bazelisk, NDK 28/29; warm clone
  ~/.cache/apple-silicon-llm-bench/litert-lm-v0.17.0 (2.5 GB, deep history) has 8cd9c91e and 96b4819c.
- Cost gate: the first billed DDP session waits for the supervisor's go after "Mac 側 PASS" (selftest, dry run, one real build,
  estimate); cap 10 sessions. The 09-17 by-hand bisect took 7 probes in ~30 min on a warm clone.

## Design notes for the remaining stages (supervisor, 19:5x; to become launches r3-r5)
- Stage 2 (job -> checker -> commit -> summary -> page; switch OFF): a post-sitting step outside the hold, after the ledger
  line, in scripts/dashboard_post.py (also runnable by hand over any campaign dirs): session_check PASS -> `git add -- <dirs>
  && git commit -- <dirs>` by pathspec in the main tree (other lanes' staged work untouched; refuse when a merge or rebase is
  in progress) with a generated message (device, engine stamps, cells n, anchor ratio, text k/N, FAILURES, duration; no
  "claude") -> results/summary rebuilt from the git index (CLAUDE.md recipe) and committed with the dirs -> P rebuilt
  (EDGE_LLM_BENCH=<main tree> python3 build.py) + the four checks -> `git -C P add dist && commit` -> push bench / push P /
  publish_gcs behind ops/autopilot/switch.json (push false, publish false); while OFF, the would-have-pushed diff goes to
  logs/dashboard-job/autopilot-ledger.tsv (bench sha range, P sha range, dist sha256). HOLD / FAIL -> nothing committed, one
  ledger line, the reasons in the campaign dir (REVIEW.md). Never changes the job's exit code or its ledger line.
  Acceptance: dry run over one backlog PASS pair; selftest with a temp git repo + fake P; a real local run on the worktree
  branch over the 10-17 iphone18pro-r2 pair.
- Stage 3a (regression response): the trigger computed in the bench from device-runs.csv with P's rule (vs_prev of a shown
  point below -SPREAD_FLAG, same regime, per REGRESSION_DEVICES x models x tasks x metrics) and verified equal to P's
  dist/regression.json red set; a red point -> a retake cells file (anchor rows + the red cell's row byte-identical,
  docs §5 "targeted retake") queued in ops/autopilot/retakes.json; `auto` runs a device's pending retake before its weekly
  set (short sitting, own campaign suffix). Red stays and engine_changed -> engine_bisect.py (stage 3b) between the two
  points' engine labels on DDP (S26 / Pixel 8a lab unit), profile where a route exists (run_profile.py on a local phone in
  a night hold; none on DDP), issue draft EN + JA local (post = GO). Acceptance = r2's reproduction.
- Stage 4 (D6 DDP weekly slot): schedule.json gains a DDP device entry (platform ddp, unit m1q-36, weekly, no hold, no
  anchor: DDP has no anchor; admission rule = cpu-cap marks + text check), the job's `auto` may take it any firing (no
  device needed); "a Googler runs it -> our slot stops" as a switch in the entry.
- Stage 5 (Googler's one command): `./bench autopilot --ddp <id> --project --bucket` = the DDP sitting + checker + the
  page data (cells.csv / regression.json of the bench's own render_dashboard, not P) in one run from a clean clone; test
  from the Linux container route of results/raw/2026-10-16-googler-first-run-dev/LANE_CLOSE.md.
- 20:2x r1 closed: f132add5 (checker, 30 rules, allow-list 25 lines, selftest 34 checks, CI step, docs) + 79b6448b (ROUND1).
  Supervisor's recomputation (own run of the checker): committed 88 dirs PASS 77 / HOLD 11 / FAIL 0; backlog 77 PASS 27 /
  HOLD 28 / FAIL 22 in 13.4 s; gen-budget HOLD opened (2026-09-08 m4max Qwen3 1.7B: 579 generated tokens, budget 128,
  maxOutputTokens absent in the record). Findings to carry: the lock's litert-lm default_tag v0.16.0 while the Mac
  yardstick stamps v0.18.0 since 10-12 (registry stale -> engine-stamp HOLD on 5 Mac dirs); 10-16 Mac r2 Qwen3 1.7B / 4B
  prompt 8 tokens and off-task replies; 4 committed anchors reference uncommitted backlog sittings; a committed 09-17
  rehearsal logcat holds 2 MACs (991157b3). r1 tab closed (workspace:359).
- 20:17 r3 launched (post-sitting pipeline; launch ~/code/standup/launch/2026-10-18-autopilot-post-opus-r3.md)
- r3 worker = edge-llm-bench-wt-autopilot-55 [527e21] (workspace:361); idle notice subscribed 20:17
- 20:45 r2: Mac 側 PASS verified (probe build 8cd9c91e: litert_lm_main 92fc7a63 = 09-17 driver log, GPU .so 1287e5ae; selftest 70/70; dry-run 152 commits, first probe cd3ef227 as on 09-17). go sent: --max-sessions 14 (endpoints 2 + <=8 probes + margin), commit = records + summary rebuilt from the git index in the bisect worktree (option A).
- 20:46 note: r2's ROUND2 経過 stamps 20:52 / 21:00 / 21:05 while the Mac clock read 20:45 at the go — the worker wrote times without reading date (carry as a correction at close; the launch asked for date before writing). r2 busy after the go (ListAgents 20:45).
- 21:00 r2 BISECT_STOP: both endpoints bad on the Hub's current file (snapshot 79bf0667, blob 2a72330b, template change 2026-10-09): Prefill Turn 1 = 8 tokens on 8cd9c91e and 945edf3 (= v0.17.0 binary) = the user turn dropped; 09-17 used blob 2eeffef7 (snapshot 73fbc3fe, in the local HF cache). Decision: option A — run_ddp.py gets revision= pass-through (write range widened), rerun with revision=73fbc3fe; the stopped campaign stays as evidence. Finding to carry: the current Hub file empties the user turn on engines <= v0.17.0 (card / upstream report candidate, GO).
- 21:00 correction to r2's reading: the template change is Hub commit 87603f0f dated 2026-10-11 ("Update LlmMetadata for litert-lm 0.18.0: chat template with content parts"), main = 79bf0667 (2026-10-11 "Add quality tests"); the 09-17 file is snapshot 73fbc3fe (2026-08-31). Verified: 8 tokens on both probes (run logs), 19 tokens on the 10-16 v0.18.0 run of the same row on the same unit.
- 21:1x r3 closed: f3d5fae6 (scripts/dashboard_post.py + selftest 38 checks, the job's post_sitting hook after the ledger
  line outside the hold, ops/autopilot/switch.json all false, docs) + 9215953b (ROUND3). Supervisor's checks: the three
  selftests OK (worktree and main tree); `dashboard_job.py s26 --dry-run --once` and `pixel8a` print the post command after
  the done line and run nothing; the real test commit c258edd8 on branch autopilot-post-test (10-14 S26 anchor + b2: 79
  files, summary 4739 -> 4772, P build + 4 checks PASS, render_check 48.8 s) read; its message is in the results commits'
  form. Design decisions accepted: --allow-subset (two rules, same sitting only), commit-tree + update-ref CAS from a
  temp index (HEAD + dirs), the page built from the committed tree's export. Carried to r4: the page-diff count
  (measured -> no number cells) in LEDGER2 and the page message. r3 tab closed (workspace:361).
- 21:2x stages 0-2 merged into main by ff (f7fec9fe: + the agent note and checker doc wording; then one more wording commit);
  selftests in main OK; switch all false; tonight's 02:00 / 05:30 firing runs the post step after a sitting that exits 0
  (local commit only). main is ahead of origin/main (push = GO).
- 21:05 r4 launched (regression response; launch ~/code/standup/launch/2026-10-18-autopilot-regression-opus-r4.md; HEAD fb9bdbe4)
- 21:19 r2 rerun with revision=73fbc3fe: endpoints reproduce 09-17 (8cd9c91e bad 'The word explain means…', 945edf3 good 'On-device AI is like…'; sessions 4/14). Then 3 builds failed in a row: stale sentencepiece headers in the shared bazel output base (931ae69 2026-08-19 moved BUILD.sentencepiece src; the 945edf3 build left sentencepiece_model.pb.h / sentencepiece.pb.h under bin/external/sentencepiece/, older commits pick them up = the 09-17 cd3ef227 'stale-header error'). Approved: delete the named generated external header and retry once (no bazel clean), resume the same campaign from cd3ef227 with the endpoints kept, build-failure skips retried (superseded rows kept).
- 21:58 r4 closed (d639ce96 + 44f19f9c + 53b9ba1d): regression_watch --compare equal to the page (8 red, 29 series, 78 sittings, 64 shown; my own run 0.15 s), four selftests OK; retake-first auto only when logs/dashboard-job/retakes.json has pending entries (none today). Merged into main by ff; selftests in main OK. r4 tab closed (workspace:362).
- 22:00 r5 launched (D6 DDP weekly slot; launch ~/code/standup/launch/2026-10-18-autopilot-ddp-slot-opus-r5.md; HEAD 53b9ba1d)
- 22:00 r2 bisect FOUND (bisect.json status found): firstGood 96b4819c3a5e275f689951e93d376e65ca5c69e1 (2026-08-07 'Update dependencies of litert_lm'), lastBad fa814c1b; change = WORKSPACE LITERT_REF 0ff28117 -> b0f6c120 + TENSORFLOW_REF + the 6 android .so (GPU 1287e5ae -> 9d7ae75e); 10 sessions, 8 builds (461 s), sessions 2020 s, total 2892 s; probes cd3ef227 / a719d96f / 5636ec58 / 172ab84d good, 0407a450 bad, a3d29dc1 / 96b4819c good, fa814c1b bad = the 09-17 by-hand table reproduced on the DDP S26 lab units. r5 worker = edge-llm-bench-wt-autopilot-c1 [c82e21] (workspace:363).
- 22:03 r2 closed: e3295a15 on bench-autopilot-bisect (engine_bisect.py + selftest 83, BUILD LITERTLM_LOCAL_CHECKOUT, run_ddp.py revision=, docs/engine-bisect-v1.md, two campaigns incl. the stopped first try, pins main-* 10 entries, summary from the index 4566 -> 4578). Supervisor's checks: lint PASS, no forbidden words in the commit or the issue drafts, selftest 83/83, no binary in the commit; the android/ddp selftest needs BENCH_ANDROID_BIN_DIR here (worktree has no android/bin/v0.18.0). Residue kept for now: bisect clone 2.1 G, bazel output base 7.0 G, android/bin/main-* 1.5 G (ignored; pins reference them) — lane close decides. r2 tab closed (workspace:360). The branch waits for PR #4 (GO) before any merge into main.
- 22:07 registry finding: environment.lock.json arms.litert-lm.default_tag v0.16.0 is stale for the Mac (yardstick stamps v0.18.0 since 10-12; vendored Package.swift = v0.18.0 both targets) while the iPhone 18 Pro's pinned app stamps v0.16.0; the checker reads default_tag for mac and ios -> a false engine-stamp HOLD on tonight's Mac sitting. Sent to r5 (editing the checker): lock mac block + registry_pin per platform + re-verification table.
- 22:44 r5 Mac 側 PASS read (dad937b1 + f36512ae; dry run 16 jobs / 2 sessions / 4 skips; selftests job 86 / checker 37 / post 45 / watch 50; lock mac block done, re-verification: only the 5 Mac engine-stamp findings changed). go sent: real DDP sitting (~200 device-min, est. 1-3.5 h), gen-budget allow-list line for the DDP route approved (litert_lm_main ignores --max_output_tokens, b6ddcb2c), DDP pending rule -> 'no admitted DDP sitting in the last 6 days' to avoid a repeat at Monday 02:00.
- 22:47 r6 launched in a third worktree ~/code/edge-llm-bench-wt-autopilot-googler (branch bench-autopilot-googler from f36512ae; workspace:364): ./bench autopilot one command, container rehearsal (colima), one billed akita-35 run after go. Rebase onto bench-autopilot after r5 closes.
- 23:31 r5 real DDP sitting OK (2 sessions, 16/16 jobs PASSED, 193.0 device-min, 22:46-23:29, all v0.18.0, cpu-capped, 1K text check PASS, prompt tokens as 10-16); post HOLD: checker FAIL logcat-unscrubbed x16 = the execution-level logcat.txt (5-12 MB, untracked; humans kept them out by hand on 10-16) + big-file-size x10 on the same files. Approved: .gitignore results/raw/*/ddp/*/*/execution-*/logcat.txt (rule = the by-hand practice), selftest case, rerun the post (no new billing), then the 6-day rule + docs.
- 23:35 r6 Mac 側 PASS read (b910eb2f + 704a7c4d: scripts/autopilot.py + selftest 58 (needs BENCH_ANDROID_BIN_DIR like android/ddp/selftest.py; CI sets it), host and container dry runs equal, no network calls, README/skill/docs §10). go sent: one billed akita-35 run from the container with 63ec5615 cherry-picked into the container clone (option 2); the autopilot does not read ddp_weekly (the Googler's command is not gated by the host's switch) — accepted.
- 23:43 r5 closed (dad937b1 f36512ae 63ec5615 6e3d5908 0c82ff22 79d9526c 4b8bceaf): the DDP weekly slot ran for real (2 sessions, 16/16 jobs, 193 device-min, 42.9 min) and the post step committed it by itself (0c82ff22: 503 files, summary 4739 -> 4811, message names DDP / 16 units / cap split) after the .gitignore rule for execution-level logcat.txt; P checks 3/4 PASS, check_regression FAIL (2): the S26 Gemma 4 E2B GPU cells' newest sitting is the lab-unit stand-in while the Regression series follow the phone's own sittings (check_regression.py l.369 expects a point of the cell's campaign) = a P check fix for the GO letter; lock arms.litert-lm.mac + registry_pin per platform (88 committed dirs unchanged, 5 Mac dirs lose engine-stamp); DDP pending = no admitted DDP sitting in 6 days. Supervisor: lint PASS, 4 selftests OK, commit 0c82ff22 carries no execution-level logcat. Merged into main (ff); r5 tab closed (workspace:363).
- 23:5x main ff to 4b8bceaf (stages 0-4). The first ff attempt aborted: the main tree's results/summary/{README.md,device-runs.csv}
  carried another lane's disk rebuild (+2059 rows = the uncommitted backlog dirs; the index is the truth, CLAUDE.md) and
  0c82ff22 changes those files; reverted the two files to the index (`git checkout -- results/summary/...`, regenerable) and
  merged. Four selftests OK in main; switch now carries ddp_weekly true / ddp_max_sessions 16 (push / publish still false);
  the next DDP weekly sitting is due 6 days after 2026-10-18 23:24. main is 18 commits ahead of origin/main (push = GO).
- 23:45 r6 real run: akita-35 unit 45231JEKB09089, run 1 OK (decode 20.24), the wrapper exited non-zero 24 s into the cooldown (NATIVE_EXECUTABLE_FAILED, cause unverified), run 2 not reached; checker FAIL (execution-level logcat not ignored on that branch: 6e3d5908 missing) + HOLD failures/runner-exit; the autopilot finished with the HOLD form (summary, red 8 = page, requests). Approved one retake session (--suffix r2) with 6e3d5908 cherry-picked in the container clone.
- 00:0x r6 closed (b910eb2f 704a7c4d f1ca3618 7edc798d a8d6c810, rebased onto bench-autopilot as 14cdba05..eee9dfdb after one
  doc conflict resolved by keeping §9 and §10): `./bench autopilot --ddp <id>` from a clean Ubuntu container: r1 session
  4b783529 FAILED on the unit during the cooldown (cause unverified) -> HOLD form shown; r2 session f53347c2 PASSED, 3.7
  device-min, checker PASS, commit 9e310521 in the container clone (bundle in K3), summary 4739 -> 4741, red 8 = page.
  Supervisor: lint PASS, 5 commits clean, bundle verifies, autopilot selftest 58 OK (needs BENCH_ANDROID_BIN_DIR as the DDP
  selftest does; CI sets it). r6 tab closed (workspace:364); container stopped, colima still up (stop after the lane close).
- 00:0x date-boundary flake found and fixed: regression_watch_selftest's "done this week" row was 40 min before the real
  clock and fell into the previous week between Monday 00:00 and 00:40 (3 checks failed in every tree at 00:02) -> stamped
  no earlier than one minute into the week (c688d3dd). Stages 0-5 all on main: eee9dfdb, 24 commits ahead of origin/main;
  five selftests OK in main; switch: push / publish false, ddp_weekly true.
- Open for the GO letter: P's check_regression needs the stand-in rule (a P change) before the page can be committed by
  the post step on nights when the lab unit's sitting is the S26 Gemma 4 E2B GPU cells' newest.
- 00:5x correction: the r6 commits on main are 7bcf856c..eee9dfdb (the rebase of b910eb2f..a8d6c810); 14cdba05 written at 00:0x was a mid-rebase hash, not a main ancestor. Lane close r7 = cca803b4 (K + K3) and 53f0f226 (K2/LANE.md on bench-autopilot-bisect); handoff ~/code/standup/handoffs/2026-10-19-bench-autopilot.md; 34 intermediate paths (17.3 GB) deleted per K/bench_autopilot_deleted_paths.txt; the three worktrees stay (their ignored ddp-raw / execution logcats are moved into the main tree before any worktree remove).
