# Dashboard autopilot v1 — what follows a sitting: check, commit, page

Status: written 2026-10-18 (stage 2 of the bench-autopilot lane; stage 3a, the regression
response, the same day: §8); the switch is off (nothing is pushed or published). Code:
`scripts/dashboard_post.py`, `scripts/regression_watch.py`; selftests
`scripts/dashboard_post_selftest.py`, `scripts/regression_watch_selftest.py` (CI, data
pipeline); switch `ops/autopilot/switch.json`; the page's regression rule as copied
`ops/autopilot/regression-watch.json`; ledger `logs/dashboard-job/autopilot-ledger.tsv`.
Validation records: `results/raw/2026-10-18-bench-autopilot-dev/ROUND3.md` (the post step),
`ROUND4.md` (the regression response). The checker it runs: `docs/session-check-v1.md`. The job it
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
  git_busy()        MERGE_HEAD / rebase-merge / rebase-apply / CHERRY_PICK_HEAD / REVERT_HEAD,
                    detached HEAD                               -- busy --> held, exit 1
  build_tree()      temp index = HEAD + the dirs -> exported tree -> its build_summary.py
                    -> results/summary into the temp index
  commit_message()  one line, generated; REFUSED_WORDS checked
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
  dashboard-job sitting <start>–<end> <tz> (anchor admitted at ratio <R> vs <reference campaign>,
  thermal <states>; the payload's own anchor rows at <R>); text check <k>/<N>; cpu-capped counted
  <k>/<N>, past the line <k>; FAILURES: <lines or none>[; gate retries kept: <k>][; SKIPPED: <k>]
  [; not in this commit (--allow-subset): <dir> (<what it is to the committed dirs>)]; results/summary
  rebuilt from the git index (<A> -> <B> lines)`. An admission with no ratio (the first session on
  a build) reads `anchor admitted: <reason>; thermal <states>`; a sitting with no text check
  (Apple) reads `text check 0/0 (no run carries one)`. It states what ran; it orders no runtime
  against another (§6 of the job doc). A message with a word the commit-msg hook refuses is never
  written (held).
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

`ops/autopilot/switch.json` (committed all off):

```json
{"push_bench": false, "push_page": false, "publish": false, "page_repo": "~/code/litert-bench-dashboard"}
```

| key | on (`true`) | off (anything else, or no file) |
|---|---|---|
| `push_bench` | `git push origin <bench commit>:main` under the rule above | ledger: `would push bench <origin/main>..<commit> (<n> commits[, <k> not made by this step])` |
| `push_page` | `git -C <page repo> push origin <page commit>:main`, same rule | ledger: `would push page <origin/main>..<commit> (…)` |
| `publish` | `<page repo>/tools/publish_gcs.sh` after a page commit of this post | ledger: `would publish dist/index.html sha256 <…>` |
| `page_repo` | the page repo to build and commit | none: the page step is skipped |

Off is the default. Turning a key on is a person's decision (the owner's), one key at a time;
the ledger's `would …` lines are what each key would have done on the nights before.

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
  allow-list line goes in only with the commit whose message gives the reason.
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
  that stays red on the same engine build or ends `unjudged` / `abandoned`, a `red: mismatch`.

## 7. Not covered

- The bisect itself and the issue: §8 writes a bisect request and the draft beside it; running the
  request (`scripts/engine_bisect.py`, stage 3b, billed lab sessions) and posting the draft are a
  person's GO. The Developer Device Platform weekly slot (stage 4) is not in the schedule yet.
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
campaign; another exit counts an attempt, and two sittings that do not admit mark them `abandoned`;
a pending retake older than seven days is `expired` (the weekly set has re-measured the cell by
then). `auto` takes a device whose weekly set is done when a retake of it is pending (that firing
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
an `unjudged` or `abandoned` retake (read the sittings); `red: mismatch` (the page's rule moved:
bring `ops/autopilot/regression-watch.json` and `regression_watch.py` to `build.py` again, then
`--compare` until it says equal).
