# Dashboard autopilot v1 — what follows a sitting: check, commit, page

Status: written 2026-10-18 (stage 2 of the bench-autopilot lane; stage 3a, the regression
response, the same day: §8; stage 4, the Developer Device Platform weekly slot, the same day: §9;
the team-protocol rules in the checker and the message guard, 2026-10-19: §11; the text screen for
the Mac and iPhone, the same day: §12);
the push and publish keys of the switch are off (nothing is pushed or published). Code:
`scripts/dashboard_post.py`, `scripts/regression_watch.py`; selftests
`scripts/dashboard_post_selftest.py`, `scripts/regression_watch_selftest.py` (CI, data
pipeline); switch `ops/autopilot/switch.json`; the page's regression rule as copied
`ops/autopilot/regression-watch.json`; ledger `logs/dashboard-job/autopilot-ledger.tsv`.
Validation records: `results/raw/2026-10-18-bench-autopilot-dev/ROUND3.md` (the post step),
`ROUND4.md` (the regression response), `ROUND5.md` (the DDP weekly slot). The checker it runs: `docs/session-check-v1.md`. The job it
follows: `docs/dashboard-recurring-job-v1.md`.

```bash
python3 scripts/dashboard_post.py results/raw/<campaign>... [--dry-run] [--switch <file>]
        [--page-out <dir>] [--no-page-commit] [--allow-subset]
#   exit 0 = committed (or nothing new to commit) and every later step as the switch allows
#   exit 1 = held (nothing committed), or a step after the commit failed (the ledger says which)
#   exit 2 = usage (not a campaign dir, dirs of two checkouts, an unreadable switch)
```

The dirs' checkout is the repo it commits to. `scripts/dashboard_job.py` runs it by itself after
a sitting that exits 0; a person runs it the same way over any sitting's dirs.

## 1. The flow

```
dashboard_job.py main()
  attempt(): preflight, hold, phase A, admission, phase B, close (SESSION.json), hold released
  ledger line (logs/dashboard-job/ledger.tsv), "=== done" line
  post_sitting(): exit 0 and dirs with SESSION.json?  -- no -->  nothing more
        | yes: python3 scripts/dashboard_post.py <dirs>       (its output in the job log)
        v
dashboard_post.py main()                       one at a time (logs/dashboard-job/.post.lock)
  scrub()           /Users/<name> ... -> USER in the dirs' text files
  check()           scripts/session_check.py <dirs> --json   -- any dir not PASS -->
                                                  REVIEW.md in each dir, ledger line, exit 1
                    (it writes text_screen.json in a dir with Mac / iPhone text cells, §12;
                    --dry-run: --no-text-screen)
  git_busy()        MERGE_HEAD / rebase-merge / rebase-apply / CHERRY_PICK_HEAD / REVERT_HEAD,
                    detached HEAD                               -- busy --> held, exit 1
  build_tree()      temp index = HEAD + the dirs -> exported tree -> its build_summary.py
                    -> results/summary into the temp index
  commit_message()  one line, generated; REFUSED_WORDS checked, then STANDING_WORDS ('%', vs,
                    faster, slower, than, beats, leads, outperforms) -- one found --> held, exit 1
  commit_index()    pre-commit + commit-msg hooks, commit-tree, update-ref compare-and-swap
                    (HEAD moved meanwhile -> build again on the new HEAD, three tries);
                    the checkout's index takes the new HEAD's entries for those paths only
  page_step()       <page repo>/build.py with EDGE_LLM_BENCH = the exported tree, into
                    --page-out; then its four checks with --dist  -- a check FAIL -->
                    the bench commit stands, no page commit, exit 1
  number_changes()  the page committed before vs this build's cells.csv: the cells that had a
                    number and have none now (and the reverse) -> the ledger note, the page message
  page_commit()     dist/ := the checked build, committed in the page repo the same way
  red_step()        the tree's own scripts/regression_watch.py --respond <dirs> (§8): the
                    sitting's red points -> retakes, a retake sitting's verdict -> a bisect request;
                    --compare the build's regression.json; its phrase -> the ledger note, never the exit
  push() publish()  each only when its switch is true; off: "would …" in the ledger
  write_ledger()    one line per post
```

## 2. Rules

- **One sitting, one commit.** A post commits the campaign dirs of one sitting (its anchor phase,
  its payloads, its extra files) and `results/summary`, nothing else, in one commit; at most one
  page commit follows. A dir is never committed in pieces.
- **Every dir PASS, or nothing.** The default takes a sitting whole: `session_check.py`'s pair
  rules hold an anchor phase whose payload is neither committed nor given (`pair-incomplete`)
  and a dir whose admission reference is neither (`reference-uncommitted`). HOLD or FAIL in any
  dir = no commit for any of them.
- **`--allow-subset`** (by hand): the dirs given are part of a sitting whose other dirs stay out
  (a HOLD payload beside PASS ones). It lets through exactly two links to a left-out dir of the
  same sitting (`<date>-dashboard-v1-<device key>-…`): an anchor phase's other payloads, and an
  admission reference. The message names each left-out dir and what it is. A payload without its
  anchor phase still holds; so does every other finding. The job never passes it.
- **The summary is the commit's own.** `results/summary` is rebuilt by the tree's own
  `scripts/build_summary.py` in an export of HEAD + the dirs (a temp index): never from the
  checkout's disk (other sittings' uncommitted dirs) and never from the checkout's index (another
  lane's staged files). It equals what CI's `summary-fresh` job computes on the commit. The
  rebuilt files are then copied into the checkout (the CLAUDE.md recipe's `cp`), until the next
  `bench matrix` rebuilds them from the disk. A `results/summary` another lane had staged is
  replaced by the committed one.
- **The commit is the tree that was checked.** It is written from the temp index
  (`git commit-tree`), and the branch moves only if it is still at the HEAD the summary was built
  on (`git update-ref <branch> <new> <old>`): another lane's commit in between makes it build
  again, a `bench matrix` rewriting `results/summary` on disk meanwhile cannot reach the commit.
  The effect is `git commit -- <dirs> results/summary` without its window: other lanes' staged
  files stay staged, untracked files untracked, unstaged edits unstaged. The pre-commit and
  commit-msg hooks run as `git commit` runs them (`git hook run`).
- **The message** is one line in the results commits' form: `results <date> <device display>
  (<identifier>), <arm>: <engine stamps>, …: <n>/<N> cells of <cells file>, … in one
  dashboard-job sitting <start>–<end> <tz> (anchor admitted at ratio <R> to reference <reference campaign>,
  thermal <states>; the payload's own anchor rows at <R>); text check <k>/<N>[; text screen: none |
  text screen: <n> cells text-fail (<arm> <model> <task> <k>/<N> runs, …)]; cpu-capped counted
  <k>/<N>, past the line <k>; FAILURES: <lines or none>[; gate retries kept: <k>][; SKIPPED: <k>]
  [; not in this commit (--allow-subset): <dir> (<what it is to the committed dirs>)]; results/summary
  rebuilt from the git index (<A> -> <B> lines)`. An admission with no ratio (the first session on
  a build) reads `anchor admitted: <reason>; thermal <states>`; a sitting with no text check
  (Apple) reads `text check 0/0 (no run carries one)`; the text screen phrase (§12) is there when a
  cell was screened (an Android sitting has none). It states what ran; it orders no runtime
  against another (§6 of the job doc). A message with a word the commit-msg hook refuses is never
  written (held). Nor is one with a percentage or a standing word (`%`, `vs`, `faster`, `slower`,
  `than`, `beats`, `leads`, `outperforms`; case-insensitive): the public repo's text carries no
  standings and no lab-unit-to-attached difference in percent. That hold is the generator's fault,
  not the dirs': one ledger line, exit 1, no `REVIEW.md`; a passing message logs
  `message guard: … OK`. Words reach the message from the records and `SESSION.json` (the
  admission `reason` verbatim when the anchor has no ratio, the `FAILURES.txt` lines), so the
  guard reads the whole line, not only the generator's own words.
- **The name scrub** replaces the account name by `USER` in the forms the checker's `user-name`
  rule reads (`/Users/<name>`, `/home/<name>`, `-Users-<name>-`, `_bazel_<name>`, an `ls` owner
  column), as people did before each commit (d25a9985, 8208edff, dde2149e, ceeaa362). Text files
  only (no NUL in the first 8 KB, under 20 MB, not a symlink), files the commit would carry only;
  a JSON file is rewritten only when it parses to the same values with only those strings changed.
  A binary file keeps the name (the checker does not read binaries either; a gzip log is one).
- **The page is built from the commit.** `build.py` reads `EDGE_LLM_BENCH` = the exported tree,
  so the page names a bench commit and reads that commit's summary, matrices and scripts — not
  the checkout's disk (the page repo's README describes a build from the disk copy, which carries
  sittings not yet committed; a HOLD sitting is not on the autopilot's page until a person
  commits it). Its four checks run on that build (`--dist`). The page repo is written only to
  commit `dist/`, only when every check passes, only when it has no uncommitted change to a
  tracked file (else the page would be its working tree's, not its HEAD's), and a commit that
  does not go through puts `dist/` back. The page repo is optional: no `page_repo` in the switch,
  or no `build.py` there, and the page step is skipped (the bench commit is unchanged).
- **A push carries only this step's commits.** With a push switch on, `origin/main` is fetched
  and the commit is pushed as `<sha>:main` only when `origin/main` is its ancestor and every
  commit between is one the ledger records as this step's (a shared checkout's `main` can hold
  another lane's unpushed commit, and pushing `main` would publish it). Anything else is refused
  and named in the ledger.

## 3. The switch

`ops/autopilot/switch.json` (the push and publish keys committed off):

```json
{"push_bench": false, "push_page": false, "publish": false, "page_repo": "~/code/litert-bench-dashboard",
 "ddp_weekly": true, "ddp_max_sessions": 16}
```

| key | on (`true`) | off (anything else, or no file) |
|---|---|---|
| `push_bench` | `git push origin <bench commit>:main` under the rule above | ledger: `would push bench <origin/main>..<commit> (<n> commits[, <k> not made by this step])` |
| `push_page` | `git -C <page repo> push origin <page commit>:main`, same rule | ledger: `would push page <origin/main>..<commit> (…)` |
| `publish` | `<page repo>/tools/publish_gcs.sh` after a page commit of this post | ledger: `would publish dist/index.html sha256 <…>` |
| `page_repo` | the page repo to build and commit | none: the page step is skipped |
| `ddp_weekly` | the job's weekly Developer Device Platform sitting runs (§9) | no lab-unit sitting, by `auto` or by hand |
| `ddp_max_sessions` | the Device Run sessions one lab-unit sitting may start (its plan's count, before any is billed) | absent or not a whole number: 0, no sitting |

Off is the default. Turning a key on is a person's decision (the owner's), one key at a time;
the ledger's `would …` lines are what each key would have done on the nights before. `ddp_weekly`
is on since 2026-10-18 on the user's word of 2026-10-16 (DDP sessions need no GO each); it goes
off when a Googler runs the weekly DDP set on their side (§9).

## 4. The ledger

`logs/dashboard-job/autopilot-ledger.tsv`, one line per post (a dry run writes none):

| column | holds |
|---|---|
| `started` / `ended` | local time |
| `dirs` | the campaign dirs' names |
| `check` | `<dir>=PASS|HOLD|FAIL` per dir (after the allow-list and `--allow-subset`) |
| `bench_commit` | the commit (empty when held) |
| `summary_lines` | `results/summary/device-runs.csv` lines in HEAD -> in the commit |
| `page` | `build <exit> <s>; <check> <exit> <s>; …` (`— FAIL <check>`), or why it was skipped |
| `page_commit` | the page repo's commit (empty: not committed, the note says why) |
| `push_bench` / `push_page` / `publish` | what was done, refused, or would have been done |
| `note` | the scrub count, held reasons, `--allow-subset`, errors; `page cells: cells with a number before and none now: <n> (<status> <k>, …), the reverse: <m>` (the page repo's committed `dist/cells.csv` against this build's; the same phrase in the page commit's message; it changes no verdict); `red: …` (§8: whether the page build's red points are the bench's, each red point of the sitting and what it became, each retake verdict and request) |

## 5. REVIEW.md

When a post holds, every dir it was given gets a `REVIEW.md` (first line: a mark that it was
written by this step): the verdict, why the sitting was held, the other dirs' verdicts, a table
of the findings still holding (severity, rule id, detail, what a person does) and those excused
(allow-list line, `--allow-subset`), and the command to post again. It names repo-relative paths
only. A later post that commits the dir removes a `REVIEW.md` with that mark first; a person's
own `REVIEW.md` stays. A dir that cannot pass is committed by hand with the reason in the
message, as before, or stays uncommitted.

## 6. Where a person is needed

- A HOLD or FAIL: read the dir's `REVIEW.md` (and `session_check.py --markdown` for one reply per
  cell), then fix and post again, commit by hand with the reason, or leave it on disk. An
  allow-list line goes in only with the commit whose message gives the reason. A `pin-drift` or
  `protocol-off` FAIL takes none: the pin bump and a re-measurement (§11).
- The switch: each key is turned on by a person; nothing else turns it on.
- A refused push: `origin/main` moved, or the checkout's `main` holds another lane's commit —
  rebase in a worktree, or push `<sha>:main` by hand once `git log origin/main..<sha>` lists
  only what should go.
- The page repo with uncommitted changes, a page check FAIL: the page is not committed; the
  build and each check's output stay in `--page-out` (default
  `logs/dashboard-job/autopilot-page/`, cleared at the next post; `checks/<check>.out`).
- Reading one reply per cell: the checker's proxies screen the replies; a PASS never stands for a
  person reading them (`docs/session-check-v1.md`, "A person reads").
- The regression response (§8): running a bisect request and posting its draft (the GO), a retake
  that stays red on the same engine build or ends `unjudged` / `abandoned` / `superseded`, a
  `red: mismatch`.

## 7. Not covered

- The bisect itself and the issue: §8 writes a bisect request and the draft beside it; running the
  request (`scripts/engine_bisect.py`, stage 3b, billed lab sessions) and posting the draft are a
  person's GO. The Developer Device Platform weekly slot (stage 4) is §9; a red point of the lab
  unit and a retake on it are not covered (its rows are no page red point, §9).
- A `.gz` log and other binary files are not scrubbed (the checker does not read them either).
- The job's dry run prints the post command only after a preflight that passes; on a host whose
  `bench doctor` fails the sitting exits 5 before it (the selftest pins the line with a fake phone).

## 8. Stage 3a: the regression response

A red point is the team page's (litert-bench-dashboard `build.py` `build_regression`), computed in
the bench by `scripts/regression_watch.py` with the same rule, so the night that makes it can act on
it without the page.

```bash
python3 scripts/regression_watch.py [--summary <device-runs.csv>] [--compare <page>/dist/regression.json]
        [--json <out>] [--markdown <out>] [--device <key>]
#   exit 0 = computed (with --compare: the same red set); 1 = --compare found a difference; 2 = usage
```

**The rule (the page's).** Per LiteRT-LM cell of the page's devices (Galaxy S26, iPhone 18 Pro,
Mac Studio, Pixel 8a) x models (Qwen 3 0.6B, Gemma 4 E2B) x workloads (the 1K text task, short chat,
the protocol task), from the cells files' definitions (a cell excluded on its device has no series);
the rows of the admitted weekly sittings (`SESSION.json`, a campaign name holding `dashboard`, a lab
unit's stand-in rows out); one point per sitting = `render_leaderboard.arm_row` of that campaign's
rows, read by `render_dashboard.headline_regime`; one point a day (`latest_session` over the day's
rows); per metric (decode, prefill, peak memory) a shown point with a value against the nearest
earlier shown point with a value, on decode of the same regime only, by the page's `diff_pct`;
red = below `-render_leaderboard.SPREAD_FLAG` (5 %). `ops/autopilot/regression-watch.json` holds the
page's constants, read out of `build.py` at 8100b64 with their line numbers; the aggregation, the
regime, the exclusions and the threshold are the bench's own functions, which `build.py` imports.
`--compare` checks the copy: on 2026-10-18 the bench's summary at HEAD and at e3010721 (the commit
the page was built from) give the page's 8 red points, 29 series, 78 sittings and 64 shown
(`results/raw/2026-10-18-bench-autopilot-dev/ROUND4.md`). Every post repeats the check against the
page it just built (`red: mismatch` in the ledger note when they differ; it stops nothing). When
`build.py`'s rule changes, the definitions file and `regression_watch.py` change with it.

**A red point -> a retake.** After the page (`red_step()` in `dashboard_post.py`), the commit's
tree's own `regression_watch.py --respond <the sitting's dirs>` looks at the red points of the
sitting just committed. One that is its cell's newest sitting (the number the page shows now) and
that no retake already covers (the same cell and previous point) becomes one pending entry in
`logs/dashboard-job/retakes.json`: the device key, the cells row byte for byte (the line of the
cells file the red sitting ran, its `SESSION.json` `cells`, else the page definition's file), the
red metrics with their percentage, value, previous campaign and engines, `created`, `status:
pending`. A retake sitting's red points never queue retakes.

**The retake sitting (`dashboard_job.py`).** Before a device's weekly set, its pending retakes run
as one sitting of their own: `logs/dashboard-job/retake-<date>-<device>.cells` = the platform's rows
of `matrices/anchors.cells` byte for byte (the payload re-judges its own anchor rows), then each
retake's row byte for byte (a row of the same cell as an anchor row takes that anchor row's place,
since `validate_cells.py` refuses a cell twice in one file; an identical row is written once); then
`attempt()` as for any sitting (preflight, hold, the anchor phase and admission, the payload,
`SESSION.json` with a `retake` field naming the retakes, the ledger line, the post) with the suffix
`retake-<slug>` (campaigns `<date>-dashboard-v1-<device>-retake-<slug>[-anchor]-<platform>`; the slug
is model, backend and task, or `<n>cells`). Exit 0 marks the retakes `done` with the payload
campaign; a busy exit (3: the device or the Mac measurement window was not free, nothing ran) is
logged and not counted (2026-10-20: two busy windows had abandoned a Mac retake that never ran);
another exit counts an attempt, and two counted attempts mark them `abandoned`; a pending retake older
than seven days is `expired` (the weekly set has re-measured the cell by then), and one whose row has
left the cells file it was queued from is `superseded` and not run (the page's cell is another row
now; 2026-10-20: a retake re-ran the S26 Qwen3 0.6B protocol row on the file the page had left an
hour after the retake was queued, and its point fell in no series).
`auto` takes a device whose weekly set is done when a retake of it is pending (that firing
runs the retake only), and a device with a pending retake before the others; a retake sitting is
not the week's session (its `SESSION.json` names its retakes; a by-hand `--suffix -retake` sitting
counts as before). `--cells` (a run by hand) and `--no-retake` take no retake. The retake sitting's
payload has the device's whole-sitting timeout, as every single-file sitting.

**The verdict -> a bisect request.** The post of a retake sitting judges each retake: the retake
payload's point on each red metric against the red point's own previous point (the page's
`diff_pct` and threshold). On the red point's UTC day the retake is the page's shown point and this
is its `vs_prev`; on a later day the page compares the retake with the red point itself, which a
regression that stays passes, so the retake is judged against the point before the red one.
`red-stays`, `cleared` or `unjudged` (no value: the retake's status, a regime change) goes into the
entry. Red stays and the engine build differs from the previous point's -> one pending entry in
`logs/dashboard-job/bisect-requests.json`: the device, the row, `good` = the previous point's engine
label, `bad` = the retake's, `verdict` = `speed:decode<=-5%` or `speed:prefill<=-5%`
(`engine_bisect.py`'s form; memory has no verdict there), `route` = the lab unit of the phone's
model on the Developer Device Platform (Galaxy S26 `ddp:m1q-36`, Pixel 8a `ddp:akita-35`; the
iPhone and the Mac `none`), and, when `scripts/engine_bisect.py` is in the tree (stage 3b, branch
`bench-autopilot-bisect`), the command with `--good/--bad/--cells/--row/--verdict/--route`; without
it the request says `tooling not on this branch` and stays. A Galaxy S26 CPU row carries a note:
the m1q-36 lab units started every 2026-10-15 run with a CPU ceiling below the cpu-cap line
(`android/ddp/devices.json`), so a CPU verdict there may give no number. Beside each request,
`logs/dashboard-job/regression-<date>-<slug>.md`: the issue draft's skeleton in English and
Japanese (the two points and the retake's number, their sittings and engine labels, the row, the
command that re-measures it, the bisect command or why there is none, the profile). Red stays on
the same engine build -> no request (not an engine change; the ledger note says so).

**The per-op profile.** A retake row that is an Android LiteRT-LM CPU or GPU native-benchmark row
adds `./bench profile <the retake cells file> --campaign <the payload campaign>` after the payload,
inside the same sitting and hold: a control run and its `--enable_profiling` twin into the payload
campaign's `profiles/` (`android/bench/run_profile.py`, `docs/profiling-subcommand-design.md`; the
control's record is an ordinary speed run of the sitting, the twin's never is; the file's other
rows go to `profiles/SKIPPED.txt`); `SESSION.json` `profile` holds its exit. No profile elsewhere,
one reason each: a text task (the profile is `litert_lm_advanced_main --benchmark
--enable_profiling`, the native-benchmark rows' binary); the iPhone (no CLI on the phone, and the
app's C API path has no profiling call); the Mac (the harness's runner goes through the C API; the
pair runs by hand with the built CLI); the Developer Device Platform (`run_profile.py` drives an
attached phone over adb); the NPU side build (no route covers it). The wiring is in place and
printed by a dry run; it has not run on a phone yet (2026-10-18).

**In the morning.** The ledger note of the night's post: `red: page and bench agree (<n> red
points)` or `red: mismatch …`, then one phrase per red point of the sitting (`retake <id> queued`,
`not its cell's newest sitting`, `retake <id> (pending) covers it`), per retake verdict (`retake
<id>: red-stays (decode -7.10 % vs <campaign>)`) and per request (`bisect request <id>: v0.16.0 ->
v0.18.0, speed:decode<=-5%, route ddp:m1q-36 (tooling not on this branch …)`); `page cells: …` as
§4. The state files and drafts are local (`logs/` is ignored); the retake sittings' campaigns are
committed as any sitting's.

**Where a person is needed.** Running a bisect request (billed lab sessions: the GO, after a look at
the route and the row); posting a draft (the GO); a retake that stays red on the same engine build,
an `unjudged`, `abandoned` or `superseded` retake (read the sittings); `red: mismatch` (the page's rule moved:
bring `ops/autopilot/regression-watch.json` and `regression_watch.py` to `build.py` again, then
`--compare` until it says equal).

## 9. Stage 4: the Developer Device Platform weekly slot

The weekly set's Android LiteRT-LM rows also run about once a week (at most once in six days) on Google's lab Galaxy S26 units, with
no person in the loop up to the page's input (the commit): `ops/dashboard-v1/schedule.json` device
`s26-ddp` (platform `ddp`, pool `m1q-36` of SM-S942U1 phones, `android/ddp/devices.json`), cells
`matrices/dashboard-ddp-v1-android-s26.cells` = the 20 `android litert-lm` rows of
`matrices/dashboard-text-v1.cells` byte for byte (the four Qwen3 0.6B rows are skipped on s26 by
their `exclude-on`, as on the attached phone), run by `bench matrix <cells> --ddp m1q-36`
(`android/ddp/run_ddp.py`: one row = one job of `runs=` launches on one unit, at most 8 jobs a
Device Run session, the jobs of a session side by side on several units; 16 jobs = 2 sessions).

```bash
python3 scripts/dashboard_job.py s26-ddp [--dry-run] [--once] [--suffix <s>] [--post-page-out <dir>] [--no-page-commit]
python3 scripts/dashboard_job.py auto [--no-ddp]      # the lab unit after the attached device's sitting
```

**When.** At either firing, after the attached device's sitting (its ledger line and post), or at a
firing with no device to measure: a lab unit uses no device of this host, so it never takes the
firing's one device and never waits for one (`ddp: …` lines in the auto log; the sitting's own log
is `<date>-s26-ddp.log`). At most once in the entry's `interval_days` (6): an admitted session of the
unit that ended in the last 6 days means not due, and so does a sitting in them that ran Device Run
sessions and was not admitted (one billed attempt a window; the next is a person's, by hand). A
rolling window, not the attached devices' Monday week: a sitting on a Sunday night is not repeated
by the Monday 02:00 firing (the supervisor's change of 2026-10-18; the first real sitting ran on a
Sunday night); the next one comes at the first firing at least six days after it, after that
firing's attached sitting, so the slot recurs every six to seven days. `--no-ddp` skips it at a firing;
`dashboard_job.py s26-ddp` runs it by hand (no week check, as for any explicit key; a second sitting
the same day takes `--suffix`).

**The switch.** `ddp_weekly` true turns the slot on (the user's word of 2026-10-16: the DDP sessions
need no GO each). When a Googler runs the weekly DDP set on their side (stage 5's one command), set
it false: the slot stops, by `auto` and by hand. `ddp_max_sessions` (16) caps the sitting: the plan
of `bench matrix --ddp --dry-run` (no gcloud, no network) counts the Device Run sessions before
anything is billed, and a plan over the cap starts nothing (exit 2).

**The sitting.** No hold, no reboot, no anchor phase. Preflight: `scripts/doctor.py`'s `check_ddp`
alone (gcloud on PATH and signed in, huggingface_hub, the pinned engine files in
`BENCH_ANDROID_BIN_DIR`, else `android/bin`) — not the whole `bench doctor`, which lists `adb
devices` and `xcrun devicectl list devices` and, with one Android phone attached, runs `adb -s
<serial> shell sha256sum` on it, a phone another sitting may be measuring. Then the plan, then
`gtimeout timeout_hours bench matrix <cells> --ddp m1q-36 --campaign
<date>-dashboard-v1-s26-ddp-m1q-36` (uploads what the bucket lacks, runs the sessions one after
another, pulls, scrubs the logcats, writes the records, rebuilds the summary), then `SESSION.json`
in `results/raw/<date>-dashboard-v1-s26-ddp-m1q-36-android/`: `platform: ddp`, `admitted: true` when
the sitting wrote records, reason `ddp lab unit: no session anchor; each run carries its cap marks
and the text check`, `anchor: null`, `cells_expected` = the plan's jobs, `ddp: {id, sessions, jobs,
device_minutes, results, plan}`; then the ledger line and the post. Exit 5 when nothing was recorded
(the platform refused: auth, quota, no unit; `SESSION.json` says `no record` when the dir exists),
6 at the timeout. `timeout_hours` (5) bounds the host side only: a session already posted keeps
running on the platform and its output stays in the bucket (`run_ddp.py --resume <operation>` with
the name in `ddp/operation-create-<n>.json` pulls it).

**No anchor, what it means.** Nothing compares the sitting with an earlier one before it is
admitted (each job may land on another unit and firmware build, and DDP has no session anchor): each
run stands on its own marks — `cpu-capped` / `cpu-capped-at-start` with the clock ceilings it read,
the text check on the 1K task, the unit's build fingerprint and serial (`device.ddp`,
`conditions.ddp`). The summary names the device `SM-S942U1 (DDP m1q-36)`, so these rows never pool
with the attached Galaxy S26's.

**The checker.** A DDP dir with the job's `SESSION.json` is kind `job payload (ddp)`: the
job-session rules (verdict, runner exit, partial against the plan's jobs, FAILURES, the text check,
the engine stamp against `android_pins`, prompt tokens against the committed history, the reply
proxies, the model hashed on the unit), the pair rules n/a, the caps a note; the logcat rules as for
every DDP dir (an execution-level `logcat.txt` fails). A DDP dir without one (a run by hand, the
2026-10-16 pass) stays `not-job`. The DDP short-chat records name the budget the route passes
(`--max_output_tokens=128`, `conditions.outputTokenBudget`) and `litert_lm_main` decodes past it
(b6ddcb2c on v0.16.0, the same on v0.18.0); the attached route's records name none, so `gen-budget`
meets the DDP short-chat cells only (ROUND5).

**The page.** The page's `STAND_IN` puts the lab unit's GPU rows into the Galaxy S26 panel's GPU
cells while its sitting is the newest (marked lab, the unit on hover); its CPU rows never stand in:
the lab units hold their CPU clock ceilings below the cpu-cap line from the start (`android/ddp/devices.json`),
so the CPU jobs are recorded and give no number. The page's Regression section follows the phone's
own sittings and `regression_watch.py` the same (stand-in rows out): a DDP sitting makes no red
point and queues no retake. A series of the lab unit's own (the unit as a device of the definitions,
no `--compare`) is later; a red point there would route its bisect to the same pool (`ddp:m1q-36`).

**Cost.** About 190-210 device-minutes a week (2026-10-16: 12 of the 16 jobs took 151.4; Gemma 4
E2B's 4 jobs had not run on DDP), about an hour of wall time when the pool has free units.

**The first sitting, 2026-10-18** (`results/raw/2026-10-18-bench-autopilot-dev/ROUND5.md`). By hand
(`dashboard_job.py s26-ddp --once`, the page built into a scratch dir, not committed): 2 Device Run
sessions (`session-03ab291b` 15.3 min, `session-e314180b` 25.2 min; the 8 jobs of each started together
once 8 units were free), 16 jobs PASSED, 193.0 device-min, 72 records on 16 units of one build
fingerprint, 42.9 min for the sitting. The first post held: every execution's own `logcat.txt` (the
unit's whole log) was in the dir, which the checker fails (`logcat-unscrubbed`) and people had kept out
by hand; `.gitignore` keeps them out since (6e3d5908), and the post again committed the dir and the
summary rebuilt from the git index (0c82ff22, 4739 -> 4811 lines). The page built from that commit
passed three of its four checks; `check_regression` failed on the Galaxy S26 GPU Gemma 4 E2B cells
(short chat, the 1K task): their newest sitting is now the lab unit's (STAND_IN), and the Regression
section, which follows the phone's own sittings, has no point of that campaign. Gemma 4 E2B is one of
the Regression section's two models, which no earlier DDP sitting on the page covered. Until the page
settles it (its check reading a stand-in cell against the phone's own newest point, or no stand-in for
the Regression section's cells), a lab-unit sitting newer than the phone's own fails that check, and the
post leaves the page uncommitted (the bench commit stands; the ledger says `FAIL check_regression`).

## 10. Stage 5: the one command on a host with no phone

A Googler's workstation (gLinux or gMac: no adb, no phone, a Cloud project of their own) runs a
Developer Device Platform lab unit's sitting and what follows it as the bench host's nightly job
does, with one command (§9, the job's weekly lab-unit slot, is stage 4; this command calls its code).

```bash
./bench autopilot --ddp <id> [--project <p>] [--bucket gs://<b>] [--cells <file>] [--runs N]
        [--suffix S] [--dry-run] [--no-commit]
#   exit 0 = committed (or nothing new), or a dry run whose plan holds; 1 = the check held, or a
#   step after the commit failed; else the sitting's own exit (2 config, 3 a sitting already
#   running on the key, 5 not ready or no record, 6 timeout)
```

```
autopilot.py main()
  lab_unit()    schedule.json's entry whose ddp_id is <id> (s26-ddp for m1q-36), else one made from
                android/ddp/devices.json: key <scheduleKey>-ddp (the product without one), identifier =
                the device string the summary gives the id's rows, "<ro.product.model> (DDP <id>)"
                (no row yet: the catalog's display, a guess where the unit's model name differs), cells
                = --cells, else matrices/dashboard-ddp-v1-android-<scheduleKey>.cells when it exists,
                else matrices/ddp-first-run.cells; --runs N: a copy with runs=N (logs/autopilot/cells/)
  1 sitting     dashboard_job.ddp_slot(): check_ddp, the plan within ddp_max_sessions, bench matrix
                --ddp, SESSION.json, the ledger line; its log logs/dashboard-job/<date>-<key>.log
  2 post        dashboard_post.main() over the sitting's dir, in this process (its row on the screen,
                its output in logs/autopilot/<campaign>/post.txt)
  3 table       scripts/render_dashboard.py -> DASHBOARD.md, .dashboard/ (this unit's cells listed)
  4 red         scripts/regression_watch.py --json --markdown (no --compare: no page on the host)
  5 requests    logs/dashboard-job/retakes.json, bisect-requests.json: the pending entries, each
                request's engine_bisect.py command or why it has none, whether the tool is here
  one screen    printed, at the end of the job log, logs/autopilot/<campaign>/summary.txt
```

**Where it departs from the job.** Each is a wrapper in `scripts/autopilot.py` around the job's
functions (`job_overrides`); `scripts/dashboard_job.py` is unchanged.

- The switch's `ddp_weekly` is not read: it turns the bench host's nightly lab-unit slot on and off
  and goes false once a Googler runs the DDP set on their side, the day this command is the route; a
  run by hand is its own go. `ddp_max_sessions` still caps the plan before anything is billed.
- `--project` / `--bucket` reach `bench matrix --ddp` as `BENCH_DDP_PROJECT` / `BENCH_DDP_BUCKET`:
  the job's plan and run pass neither flag, and `bench matrix --ddp` reads the variables when its
  flags are absent (the plan's summary line names the project and bucket it uses).
- A host without `gtimeout` (GNU coreutils' name on macOS; Linux calls it `timeout`) gets GNU
  timeout under the job's name, `logs/autopilot/bin/gtimeout`, first on PATH.
- `--dry-run` calls no network and bills nothing: the doctor's DDP checks run in process without
  `gcloud auth print-access-token`, which can refresh the token over the network (its line reads
  `SKIP gcloud sign-in not checked in a dry run`; the run checks it before the plan); the plan reads
  the local Hugging Face cache only; the post and the table are printed, not run; the red points are
  computed from local files; nothing is written but a `--runs` copy.
- `--no-commit` runs the post's own `--dry-run` over the sitting: the check and the message it would
  commit; nothing is scrubbed, committed or written.

**What the host needs.** README "Run the Android cells on a Developer Device Platform phone", steps
1 and 2 (gcloud signed in, a project with the Device Run API enabled and a bucket in it, python3 >=
3.10 with `huggingface_hub`, the pinned engine files), and git's `user.name` and `user.email`, which
the post's commit is made with.

**Left out on a host of its own.**

- The private team page: the post builds it only where the switch's `page_repo` holds a `build.py`;
  elsewhere its line reads `skipped: no build.py in <dir>`.
- Any push or publish: the switch's keys are all off, so the commit stays local.
- Retakes: a red point's retake is a sitting of the bench host's attached phone, run by its job.
- The bisect: a request's command runs `scripts/engine_bisect.py` (stage 3b, branch
  `bench-autopilot-bisect`, on top of PR #4's LiteRT-LM Android builds from a git ref); without the
  tool in the checkout the screen says so.
- Red points of the sitting itself: a lab unit's rows make no series of the page's rule (m1q-36's
  are the page's stand-in rows, which its regression leaves out; akita-35's device is not one of
  the page's devices), so the red points are the page's, from the attached phones' sittings.

**From a clean Ubuntu 24.04 container** (2026-10-18, colima's `ubuntu:24.04`, aarch64; record
`results/raw/2026-10-18-bench-autopilot-googler-dev/ROUND6.md`): README steps 1 and 2 (the gcloud CLI by Google's apt
route, the venv, the release asset), this branch cloned from a bundle of a checkout (GitHub does not hold the
branch), git's identity set (without it `git commit-tree` stops: "unable to auto-detect email address"), the model's
Hugging Face cache entry copied in (huggingface_hub 2.2.0 read the 1.8.0 layout and downloaded nothing);
`./bench doctor --platform ddp` ready; the selftests with the system python3 and no `huggingface_hub`; the README line
above as the dry run (no gcloud command); then two billed sittings on `akita-35`, with bench-autopilot's gen-budget
allow-list line (63ec5615) and its `.gitignore` line for an execution's own `logcat.txt` (6e3d5908) applied in the
clone: the first's job FAILED on its unit before its second run (held FAIL, nothing committed; why the run stopped is
not known from the pulled files), the second PASSED, was committed in the clone and came out as a bundle.

## 11. Team-protocol rules (2026-10-19)

Two of the checker's rules (`docs/session-check-v1.md`, "Rules") carry the team's measurement rules.
Either finding makes the dir FAIL: the post commits nothing of the sitting (§2), so none of its cells
reaches the page through this step.

- **`pin-drift`**: a LiteRT-LM cell (`litert-lm`, `litert-lm-cpu`, `litert-lm-gpu`) whose records
  stamp a release older than the newest one a platform's pin names on the sitting's day:
  `environment.lock.json` `arms.litert-lm.default_tag`, its platform blocks from their `since` days
  (the Mac's v0.18.0 since 2026-10-12, Android's v0.18.0 since 2026-10-15, the iPhones' v0.18.0
  since 2026-10-19), and `android/engine-pins.json`. On the page such a cell reads as the device's
  speed while it is the older release's: the lock's `arms.litert-lm.android.note` records the Galaxy
  S26 Gemma 4 E2B GPU protocol cell at 25.9 tok/s decode on v0.16.0 and 44–47 on 0.18-era builds,
  same phone and file.
- **`protocol-off`**: a LiteRT-LM headline cell off the agreed protocol
  (`methodology/agreed-protocol-gemma4.md`, "The spec"): the protocol cell
  `native-benchmark-1024x256` with a context other than 2048, a prompt other than 1024 or a decode
  other than 256 tokens, or the overview workload `long-context-1024-gen256` with a context other
  than 2048; a run with no recorded context counts as off.

**The fix** is the pin bump and a re-measurement: the bump is a person's decision (release-watch
informs, CLAUDE.md); a sitting whose LiteRT-LM records stamp the newest pinned release passes the
rule. An off-protocol cell is measured again at the protocol. Neither rule takes an allow-list line
(`session_check.py` exits 2 on one). The FAILed dirs stay on disk, uncommitted (a post writes its
`REVIEW.md` in them).

**Cells already on the page.** The rule judges a sitting by the pins of its own day, at commit time;
it does not reach into committed records. The committed iPhone 18 Pro LiteRT-LM rows of
2026-10-06..09 stamp v0.16.0 and were taken before any platform's pin moved, so a cell whose newest
sitting is one of them keeps its committed number; whether the page marks or leaves out a cell whose
release is older than another platform's current pin is the page repo's decision, not this step's.

**The iPhone 18 Pro's weekly sitting.** Its app stamped v0.16.0 through 2026-10-17 (`default_tag`,
which the iPhones read before their block): those sittings pass `engine-stamp` and FAIL `pin-drift`
(the 2026-10-15 and 2026-10-17 sittings on the main checkout's disk read so). The lock's
`arms.litert-lm.ios` (v0.18.0 since 2026-10-19, the app rebuilt on v0.18.0, registered that day) is
its pin from 2026-10-19 on: `engine-stamp` and `pin-drift` read a sitting of that day or later against
v0.18.0. `default_tag` stays v0.16.0, so the earlier sittings read as before. The block counts for a
sitting whose first record is newer than the commit that carries it (the checker reads the registry
as committed then); unlike the Mac's block it is not taken back to earlier commits.

**The message guard** (§2) is the same rule set's third part, in the post: a generated commit
message with a percentage or a standing word is never committed.

Validation record: `results/raw/2026-10-18-bench-autopilot-dev/ROUND8.md` (the committed sittings,
the backlog on the main checkout, the selftests).

## 12. Text screen for the Mac and iPhone (2026-10-19)

**Why.** The Mac and iPhone runners write no text check, so a run whose reply was broken reached the
page as a plain decode number. The 2026-10-12 Mac sitting had two such cells (the llama.cpp Gemma 4
E4B GGUF 1K-task replies were the prompt's own numbered skeleton, the MLX Gemma 4 E4B OptiQ ones
refused the lorem blocks, 4 of 4 runs each); their records were set aside by hand (8ac9b8bb), which
left the page with those cells' older numbers. The team's review the same day: a number that
disappears from the page instead of being marked leaves the page's comparisons one-sided without saying
why. A broken run is to be marked, not dropped.

**What is written.** The checker (`docs/session-check-v1.md`, "The text screen") writes
`text_screen.json` in each job dir with Mac / iPhone text cells whose records carry no runner text
check: the `reply-*` proxies' verdict per run, by record id. The post's real run writes it and the
commit carries it with the dir (`build_tree` adds the dir whole); the summary rebuilt in the
commit's tree reads it into `text_check` (`FAIL:<rules>`, `PASS:screen`); the page shows a cell whose
runs all failed as `text-fail` with the reason, as it does an Android cell, and a cell with some runs
failed keeps a number from the others. The checker's `reply-*` finding on such a cell is a note, so
the screen does not hold the sitting; the message says `text screen: none`, or names the text-fail
cells with their runs off. `--dry-run` writes no file and prints what it would.

**Android differs.** Its runner checks the stored decoded text at capture time and writes
`conditions.textCheck` into the record; the checker leaves those cells alone, writes no
`text_screen.json` for an Android dir, and an Android cell the runner did not check still holds on
`reply-*`.

**What a person reads** is unchanged: the screen is lexical (PASS means on the subject, not
correct), and the checker's markdown lists one reply per cell. A cell that is text-fail by the screen
while a person reads the reply as a good answer is a defect of the screen (fairness-rules §12), fixed
in its code (`android/bench/parsers.text_integrity`, `scripts/cell_gate.degenerate`), never a reason to
quote the rate.

Validation record: `results/raw/2026-10-18-bench-autopilot-dev/ROUND10.md`.
