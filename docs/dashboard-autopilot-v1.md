# Dashboard autopilot v1 — what follows a sitting: check, commit, page

Status: written 2026-10-18 (stage 2 of the bench-autopilot lane); the switch is off (nothing is
pushed or published). Code: `scripts/dashboard_post.py`; selftest
`scripts/dashboard_post_selftest.py` (CI, data pipeline); switch `ops/autopilot/switch.json`;
ledger `logs/dashboard-job/autopilot-ledger.tsv`. Validation record:
`results/raw/2026-10-18-bench-autopilot-dev/ROUND3.md`. The checker it runs:
`docs/session-check-v1.md`. The job it follows: `docs/dashboard-recurring-job-v1.md`.

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
  page_commit()     dist/ := the checked build, committed in the page repo the same way
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
| `note` | the scrub count, held reasons, `--allow-subset`, errors |

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

## 7. Not covered

- A red point of the page (a regression) is not acted on here. The regression response (stage 3a
  of the lane, planned: a retake, then a bisect and an issue draft) would take its trigger after
  `page_step()`, from the committed summary and the page build's `regression.json`
  (`results/raw/2026-10-18-bench-autopilot-dev/ROUND3.md`, 提案).
- A `.gz` log and other binary files are not scrubbed (the checker does not read them either).
- The job's dry run prints the post command only after a preflight that passes; on a host whose
  `bench doctor` fails the sitting exits 5 before it (the selftest pins the line with a fake phone).
