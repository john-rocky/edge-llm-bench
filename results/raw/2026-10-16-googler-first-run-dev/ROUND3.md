# D3S4 Googler first run — round 3 (Opus 5.5; supervisor `edge-llm-bench-6b [6eedda]`)

Scope: S4 = the own skill's DDP section (`skills/run-edge-llm-bench/SKILL.md`, `skills/README.md`), five Watch-for
bullets in litert-samples `skills/benchmark-on-ddp/SKILL.md` (a new worktree, one commit, not pushed) and the Draft PR
body (EN, with a JA copy for the user), the Cloudtop steps (`K/CLOUDTOP_STEPS.md`) and the reply materials
(`K/REPLY_MATERIALS.md`). No terminal on a phone, no DDP session, nothing billed; the network was read only (two
`git fetch`). Launch: `2026-10-16-D3S4-opus-r3.md`. K = this directory; this round's own files are in `K/r3/`.

## 経過

- 2026-10-16 16:39:34 JST start; HEAD fa032eb2, untracked = the supervisor's LANE.md / colima logs and the two
  campaigns' execution `logcat.txt` (left as they are). Read: LANE.md, ROUND1.md, ROUND2.md, ROUND2b.md,
  LINUX_FIRST_RUN.md, r2/session.md, r2b/session-b.md, the own SKILL.md (177 lines) and skills/README.md,
  ddp-integration.md 395-461, OPERATIONS.md 235-350, devices.json, scrub.py 1-60, fairness-rules.md cpu-cap-rule
  (149-179), CLAUDE.md:39, the D6 draft (A / B), the D6 handoff §6, litert-samples' upstream SKILL.md (85 lines) and
  README, the litert-team and plain-writing skills, the earlier Cloudtop note, README 1-60 / 96-230.
- 16:40:24 `git -C ~/code/litert-samples fetch upstream main`: upstream/main = 2166c0f9 (2026-10-15), unchanged from
  the lane's read; its Watch for = the three bullets of 2026-10-14 (no stop).
- 16:40:30 LiteRT-CLI `fetch origin`: main 9a14848 -> 59d612e (2026-10-12); `litert_cli/commands/benchmark/ddp.py`
  on it: `prompt` 0 hits in the whole benchmark package, the LM args fixed (526-553), the pushes = the bundle + the
  binary directory (556-587, 625) -> bullet (v) holds (no stop). Facts re-read from the records: the smoke request
  13 args -> `argc: 18` (provenance.txt:14); the slice jobs' start spread 0.048 s / 0.018 s, 8 serials per id, no
  serial in `session-1.json`; every m1q-36 `run<i>.state` (24) `cpucap_caps= policy0 3187200/3628800 policy6
  3398400/4742400`, akita-35's 24 empty.
- 16:4x-18:17 idle: the turn stopped after the reading; the user's 「続けて」 at 18:17 resumed it (訂正 1).
- 18:17:29 next: the own skill section, frontmatter, Tested on, skills/README.md.
- 18:2x (the supervisor's 18:2x message) done: every read above, both fetches, ROUND3.md; now: writing the own skill
  section (cpu-cap facts read in `scripts/render_leaderboard.py`:60 / 75 / 136-146); nothing waits on a window or a
  lock. Then litert-samples worktree + 5 bullets, pr-body, CLOUDTOP_STEPS, REPLY_MATERIALS, grep, commit, close.
- 18:20 own skill: the section `## Lab phones without adb (Developer Device Platform)` between "The two ad-hoc cases"
  and "Symptoms" (34 lines, SKILL.md:146-179), the frontmatter phrase, the Tested on sentence (4 DDP sessions),
  skills/README.md's bullet; `python3 scripts/validate_cells.py matrices/ddp-first-run.cells` -> `OK`, rc 0.
- 18:20:35 litert-samples: path and branch free (no local branch, no `origin` head), no upstream PR touching the
  skill's Watch for (the one own benchmark-on-ddp PR, #396, merged 2026-10-07); `worktree add -b
  skills-benchmark-on-ddp-lab-notes ~/code/litert-samples-ddp-skill-wt upstream/main` = 2166c0f9.
- 18:22 5 bullets after "DDP device names come from the matrix" (SKILL.md:80-89, 2 lines each); `git diff --numstat`
  10 / 0, 1 file; the step-6 greps on the added lines: 0 except the lab-identifier pattern on one line that named the
  two Wi-Fi identifier kinds by their acronyms (a kind, not a value) -> reworded to "Wi-Fi network names and their
  hashes, access-point and device MAC addresses" -> 0. Commit edfe9307 (author and committer john-rocky <rockyshikoku@gmail.com>, no attribution line), not pushed.
- 18:23-18:28 `K/r3/litert-cli-ddp-check.md`, `K/r3/pr-body.md` (EN + JA), `K/CLOUDTOP_STEPS.md` (60 lines, 6 steps),
  `K/REPLY_MATERIALS.md`; the Mac home path in pr-body.md -> `~`. Next: the greps into `K/r3/grep.txt`, the commit.
- 18:30:15 greps (`K/r3/grep.txt`): 0 everywhere but two hits, both read and kept: the skill's cpu-cap threshold (the
  cpu-cap-rule's line, not a difference) and the Cloudtop text's TAG line (README.md:145 byte for byte; its `[` are
  Python subscripts, not a blank). Before that: this file's own notes named the Wi-Fi kinds by acronym (reworded).
  The Cloudtop step 1 lost a `cd ~ &&` prefix that did not run (README.md:144 as is, "from your home directory").
- 18:31 round close written (below); the skill's billed command carries `--campaign <name>`: every billed run so far
  had one (r2, r2b, the D6 sessions), and a second run on one day without it is refused (the default campaign dir
  already holds records). Next: lint, the commit by explicit path (the commit that carries this file), the report.

## S4-B: the public source of each bullet (litert-samples SKILL.md:80-89 at edfe9307)

Paths are edge-llm-bench's, all on GitHub main 0efecb0 (`git cat-file -e origin/main:<path>`, 18:2x), unless named.

1. Jobs at once, one unit each (SKILL.md:80-81): `results/raw/2026-10-15-ddp-slice-akita-35-android/ddp/session-1.json`
   and `…-slice-m1q-36-android/ddp/session-1.json`, key `jobReports[].startTime` (8 jobs; spread 0.048 s and 0.018 s;
   a job report's keys are displayName, endTime, executionReports, id, labels, result, startTime, status: no serial);
   each job's `…/ddp-out/provenance.txt:6` `ro.serialno` (8 values per id, 16 files); `docs/ddp-integration.md:441`.
2. Lowered CPU ceilings (SKILL.md:82-83): `results/raw/2026-10-15-ddp-slice-m1q-36-android/ddp/session-9002dfea/*/
   execution-*/artifacts/data/local/tmp/llmbench/ddp-out/run<i>.state:6` `cpucap_caps= policy0 3187200/3628800
   policy6 3398400/4742400` (24 of 24 files), the akita-35 slice's 24 `run<i>.state:6` empty;
   `android/ddp/devices.json:5-6`; `docs/ddp-integration.md:454`.
3. Arguments split at spaces (SKILL.md:84-85): `results/raw/2026-10-15-ddp-smoke-akita-35-android/ddp/request-1.json`
   `jobConfigs[0].action.androidNativeBinary.args` (13; the 13th holds 5 spaces) and the job's
   `…/ddp-out/provenance.txt:14` `argc: 18` (the 18 elements at :15-32); `docs/ddp-integration.md:424`.
4. Lab identifiers in pulled logcats (SKILL.md:86-87): `android/ddp/scrub.py:11-23` (the rules); each 2026-10-15
   campaign's `ddp/scrub.json` (over the three campaigns every kind of the rules was counted except `id`);
   `docs/ddp-integration.md:435`.
5. Prompt runs outside the CLI's target (SKILL.md:88-89): LiteRT-CLI main 59d612e
   `litert_cli/commands/benchmark/ddp.py:526-553`, `:556-587`, `:625`, `:1192-1223` (`K/r3/litert-cli-ddp-check.md`);
   edge-llm-bench `docs/ddp-integration.md:422` (the prompt file pushed per job) and `:456`.

## 訂正

- 1. The 2-hour stop: the clock read 1 h 38 min at 18:17 while about 10 min had been worked; the turn stopped after the
  reading (16:4x) and stayed idle until the user's 「続けて」 at 18:17, so the round went on — 経過 16:4x-18:17.
- 2. "(5) `firstEver` は run 1 だけ": `android/ddp/record.py:292-295` sets `firstEver` on every run up to the job's
  first clean one (run 1 when all goes well); the skill says "a later run can rebuild one, which `firstEver` does not
  show" instead — `skills/run-edge-llm-bench/SKILL.md:174-175`.
- 3. Step 6's "15〜30 分で `PASSED`": the driver prints no `PASSED` line (per run `run i/2 OK`, then `campaign dir:`;
  the result is in `ddp/session-1.json`), and the two Linux sessions took 432 s and 360 s from the command to the
  records; the text says 6 to 7 min plus up to 10 min per thermal gate — `linux/14-session-b.log:41-45`,
  `r2/session.md`, `r2b/session-b.md`.
- 4. The launch's blank check (no `[` in the Cloudtop text) against its own step 2 (the TAG line): README.md:145 holds the Python
  subscripts `["android_pins"]["litert-lm"]`, so the check reads 1 hit, kept verbatim (not a blank) — `r3/grep.txt`.
- 5. Bullet (iv)'s kinds as the launch lists them (the two Wi-Fi acronyms, MAC, address) against the lab-identifier
  grep (= 0): the bullet names the kinds in words
  ("Wi-Fi network names and their hashes, access-point and device MAC addresses, private IPv4 and IPv6 addresses") —
  litert-samples `skills/benchmark-on-ddp/SKILL.md:86-87`.
- 6. Bullet (ii) of the D6 draft ends "and say so in the row", which the skill's next bullet ("Never edit a row by
  hand") rules out, and the CLI's run scripts read no cpufreq file (LiteRT-CLI `ddp.py:84-150`, `:196-232`): the
  bullet gives the reading and what it means for a CPU number — litert-samples SKILL.md:82-83.
- 7. The Cloudtop steps need main with this branch's commits (`./bench doctor --platform ddp`, 76 selftest checks);
  GitHub main is 0efecb0 (fetch 18:2x), which has neither: step 4's "if it stops" names the `invalid choice: 'ddp'`
  case — `CLOUDTOP_STEPS.md` step 4.

## 罠と袋小路

- The lab-identifier grep hits the names of the kinds (the two Wi-Fi acronyms) as well as values: once in the skill
  bullet, once in this file's notes -> name the kinds in words; keep the patterns themselves only in `r3/grep.txt`,
  which is left out of its own scan (it quotes them) — this round, 18:22 / 18:30.
- The `[` blank check hits README.md:145's TAG line (Python subscripts) -> read the hit; never rewrite a README line
  that ran to pass a grep (check 10) — `r3/grep.txt`.
- A path with the Mac home (`/Users/<name>/…`) went into `r3/pr-body.md` for the worktree -> `~/…`; grep the user name
  over every new K file before the commit — this round, 18:28.
- One Bash call's `cd` moved the session's cwd into `K/linux` (18:2x; the D6 trap again) -> absolute paths only.
- zsh: `echo ======` -> "not found" (16:39; the D6 trap) -> printf.
- Nothing was written to this file for the first 1 h 40 min (the reading, then the idle gap), so the supervisor saw no
  file at 18:2x -> write the first 経過 line before the reading starts, then one line per step.

## op と delegate の観察

なし: this round measured nothing (no session, no device). The facts the new texts carry were re-read from committed
records (the S4-B section above) and from LiteRT-CLI main (`r3/litert-cli-ddp-check.md`); none is new.

## 使った環境

- edge-llm-bench worktree `~/code/edge-llm-bench-wt-googler`, branch `googler-first-run`, HEAD fa032eb2 before this
  round's commit; `origin/main` 0efecb0 (fetch 18:2x); the Mac's Python 3.14.6, git 2.54.0, gh (PR list, read only).
- litert-samples worktree `~/code/litert-samples-ddp-skill-wt`, branch `skills-benchmark-on-ddp-lab-notes` (tracks
  upstream/main), base upstream/main 2166c0f9 (fetch 16:40:24), HEAD edfe9307; `~/code/litert-samples` read only.
- LiteRT-CLI: origin/main 59d612e (fetch 16:40:30 in `~/Downloads/litert-upstream/LiteRT-CLI-tflite-cache-wt`, read
  with `git show`; its checkout untouched).
- DDP session: なし. The container `elb-googler-first-run` was not started this round.

## 残した file

- The edge-llm-bench commit that carries this file (by explicit path, not pushed): `skills/run-edge-llm-bench/SKILL.md`
  (the DDP section, frontmatter, Tested on), `skills/README.md` (the bullet's phrase), and in K: `ROUND3.md` (this file),
  `CLOUDTOP_STEPS.md` (the steps the user runs on the Cloudtop; the brief session moves them into its Doc),
  `REPLY_MATERIALS.md` (facts and two sentences, EN / JA), `r3/pr-body.md` (the Draft PR's title and EN body, JA copy),
  `r3/litert-cli-ddp-check.md` (LiteRT-CLI main, file:line), `r3/grep.txt` (the step-6 greps and the reading of hits).
- litert-samples: worktree `~/code/litert-samples-ddp-skill-wt` and branch `skills-benchmark-on-ddp-lab-notes` with
  commit edfe9307 (1 file, +10); push and `gh pr create --draft` are the supervisor's after GO.
- Scratchpad `r3_grep.sh` (the grep driver): 消してよい, removed at the end of the round.
- `K/LANE.md`, `K/colima-install.log`, `K/colima-start.log`, the two campaigns' execution `logcat.txt`: untouched,
  uncommitted (the supervisor's and the audit trail).
