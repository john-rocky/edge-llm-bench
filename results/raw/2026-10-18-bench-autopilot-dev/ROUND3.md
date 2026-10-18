# ROUND3 — autopilot post-sitting step (worker edge-llm-bench-wt-autopilot-55 [527e21], Opus 5.5, started 2026-10-18 20:17 JST)

Supervisor: edge-llm-bench-55 [4f120b]. cwd ~/code/edge-llm-bench-wt-autopilot, branch bench-autopilot, HEAD 79b6448b at start. Mac only, no device. Launch: ~/code/standup/launch/2026-10-18-autopilot-post-opus-r3.md

## 結果

`scripts/dashboard_post.py <campaign dir>... [--dry-run] [--switch SWITCH] [--page-out DIR] [--no-page-commit] [--allow-subset]` を書き、`scripts/dashboard_job.py` の `main()` の ledger 行の後に繋いだ。exit 0 の sitting が SESSION.json を書いた dir 群に対して、名前の掃除 → checker → 全 dir PASS なら 1 commit (dir と、HEAD + dir から作り直した results/summary) → P の build と check 4 本 → switch (全 OFF の間は LEDGER2 に「するはずだった」行)。

- selftest: `scripts/dashboard_post_selftest.py` 38 checks exit 0 (受け入れ (i)-(viii) と、page check FAIL / --allow-subset / --dry-run / lock / commit 済み dir の再 post / usage)。`dashboard_job_selftest.py` に post の位置の case (4 checks、計 58) exit 0。`session_check_selftest.py` (34) exit 0。CI (`data-pipeline.yml`) に 1 step。
- CI の予行: `git clone --depth 1 --branch bench-autopilot` + `env -i` + python 3.11.13 で selftest 3 本とも exit 0、py_compile OK、build_summary の後 results/summary 差分なし。
- 本物の試験: 一時 branch `autopilot-post-test` (`bench-autopilot` f3d5fae6 から) に TEST PAIR を `cp -R` (diff -r で同一) → commit `c258edd8` 1 本 (79 file = anchor 14 + b2 63 + results/summary 2)、summary 4739 -> 4772 lines、P の build と check 4 本 全 exit 0 (render_check 48.8 s、post 全体 53.7 s)、P の working tree と HEAD は不変、LEDGER2 に 1 行、`git status --porcelain` は K の 4 file だけ。`bench-autopilot` に戻した (一時 branch は残した)。
- JOB: worktree での `dashboard_job.py m4max --dry-run` は doctor FAIL (worktree に vendored engines と yardstick がない) で exit 5 = post 行は出ない (exit 0 の時だけ組む作り、下に code を引用)。dry run の post 行は selftest が fake の phone で pin した。
- commit: `f3d5fae6` (code・docs・switch・CI、8 path) と、この ROUND3.md の commit (file の中に自分の hash は書けないので、hash は監督への報告に書く)。push していない。switch は全 false のまま。

## 設計

```
dashboard_job.py main()
  attempt(): preflight, hold, phase A, admission, phase B, close (SESSION.json), hold released
             -> (code, reason, last dir, the dirs with SESSION.json — dry run: the dirs it would create)
  ledger line (logs/dashboard-job/ledger.tsv), "=== done" line
  post_sitting(code, dirs, dry): code == EXIT_OK and dirs?  no -> nothing
        | yes: dry run -> print "post: $ <python> scripts/dashboard_post.py <dirs>" only
        |      else    -> subprocess (cwd ROOT, output into the job log, timeout 3600 s), one line "post exit N"
        v
dashboard_post.py main()       resolve() (dirs of one checkout, results/raw/<c>), load_switch(), take_lock() (.post.lock)
  post()
    scrub()            /Users/<n>, /home/<n>, -Users-<n>-, _bazel_<n>, "<n> staff" -> USER (text files; JSON = names-only)
    check()            session_check.py <dirs> --json -q --user <n>
    waive_subset()     --allow-subset only: pair-incomplete (payload) / reference-uncommitted of the same sitting
    verdict_of()       any dir not PASS -> write_reviews() (REVIEW.md in each dir), exit 1
    git_busy() branch_of()    MERGE_HEAD / rebase-merge / rebase-apply / CHERRY_PICK_HEAD / REVERT_HEAD, detached -> held
    remove_reviews()   a REVIEW.md this step wrote earlier
    build_tree()       temp index = HEAD + dirs -> checkout-index -> tree/scripts/build_summary.py -> summary into the temp index
    sitting_facts() commit_message()   one line; REFUSED_WORDS (the hook's claude|anthropic) -> held
    commit_index()     run_hooks() (pre-commit, commit-msg via git hook run) -> commit-tree -> update-ref <branch> <new> <head>
                       (moved -> build_tree again, 3 tries) -> git reset -q -- <dirs> results/summary
    copy_summary()     the CLAUDE.md recipe's cp into the checkout
    page_step()        <P>/build.py --out-dir <page-out> with EDGE_LLM_BENCH = the exported tree; 4 checks --dist <page-out>
    page_commit()      P clean (tracked) -> dist/ := build -> temp index -> commit_index() (undo() on failure)
    push() x2, publish()   switch on: fetch, ff check, every commit in origin/main..sha is in LEDGER2 -> push <sha>:main
  write_ledger()       LEDGER2 = logs/dashboard-job/autopilot-ledger.tsv
```

launch の手順から変えた所 (理由は「訂正」):
1. commit は `git commit -F <msg> -- <dirs> results/summary` ではなく、検査した temp index の tree を `git commit-tree` し、`git update-ref` で HEAD を比較交換する。効果は pathspec commit と同じ (他 lane の staged / untracked / unstaged はそのまま、selftest (i))。違いは窓がない事: summary を作った後に他 lane が commit しても (CAS が失敗して作り直す)、別の sitting の `bench matrix` が disk の results/summary を書き換えても (commit は working tree を読まない)、検査していない tree は commit に入らない。hook は `git hook run` で pre-commit と commit-msg を同じ index に対して回す。
2. summary の元の index は checkout の index ではなく「HEAD + この dir」の temp index (`GIT_INDEX_FILE`)。checkout の index には他 lane の staged file が入り得る (selftest は他 lane の staged record で確かめた: summary に入らない)。
3. P は `EDGE_LLM_BENCH=<REPO root>` ではなく、commit の tree の export (build_tree の tree) から作る。main tree の disk には他 lane の未 commit の変更 (matrices / scripts) があり得る = 「the page from the bench at <sha>」が言葉どおりになるのは export の方 (memory の manual-admission-reads-disk-summary の「one clean tree at the commit the page names」と同じ)。
4. `--allow-subset` の意味 (TEST PAIR は単独では PASS しない、「訂正」1 行目)。

## selftest の出力の末尾

```
--- --allow-subset: a sitting's dirs left out are named; a payload without its anchor still holds
  ok  a payload alone (its anchor phase neither committed nor given): held
  ok  anchor + one payload without --allow-subset: held (pair-incomplete, reference-uncommitted)
  ok  with --allow-subset: the anchor and that payload committed, the other payload not (exit 0)
  ok  the message names the left-out dir and what it is to the committed ones
--- the lock: one post at a time
  ok  lock held: exit 1, busy: another post holds logs/dashboard-job/.post.lock (pid 4242)
--- dirs already committed: nothing to commit, exit 0
  ok  exit 0: nothing to commit: the dirs and the summary are in HEAD already
--- usage
  ok  a path that is not a directory: exit 2 (got 2)
  ok  at the end: the other lane's staged record still staged, its untracked files untracked, its edit unstaged (all there)

selftest OK
```

受け入れ 1 の対応 (同じ出力の上の方): (i) 「the commit carries the sitting's 8 files and the summary, nothing else」「the other lane's staged record still staged, its untracked files untracked, its edit unstaged」/ (ii) 「one line in the results commits' form」「no word the commit-msg hook refuses」/ (iii) 「the committed summary holds the sitting's records and none of the other lane's (staged or untracked)」「the page was built from the commit's tree」/ (iv) 「switch off: neither remote moved, nothing published」「the ledger says what would have been pushed and published」/ (v) 「push_bench on: the bench remote is at HEAD」「push_page on」「publish on: the publish script ran once」「push_bench on with another lane's local commit in between: refused」/ (vi) 「exit 1, HEAD unchanged, the ledger line says held」「REVIEW.md in each dir」/ (vii) 「MERGE_HEAD present: exit 1, no commit」/ (viii) 「the JSON record: every number as it was」「the text file: the path, the scratchpad form and the ls owner column read USER」「the binary file left byte for byte」。

`dashboard_job_selftest.py` の追加 case:

```
--- post: a sitting that exits 0 hands the campaign dirs it wrote SESSION.json in to scripts/dashboard_post.py after its ledger line (a dry run prints the command); any other exit hands none
  ok  a dry-run sitting that exits 0: one post command after its done line, over the anchor phase and the half it would create (the skipped side-build file has no dir)
  ok  the phone not attached (exit 5): no post command
  ok  post_sitting builds the command for exit 0 with dirs only (aborted, timeout, device, busy, config: none)
  ok  a run (not dry) whose post fails: one line with its exit, the sitting's exit unchanged
```

## 本物の試験

```
git checkout -b autopilot-post-test            # from bench-autopilot f3d5fae6
cp -R ~/code/edge-llm-bench/results/raw/2026-10-14-dashboard-v1-s26-{anchor,b2}-android results/raw/   # diff -r: identical (14 / 63 files)
python3 scripts/dashboard_post.py results/raw/2026-10-14-dashboard-v1-s26-anchor-android \
  results/raw/2026-10-14-dashboard-v1-s26-b2-android --allow-subset --page-out <scratchpad>/r3/real/page --no-page-commit
#  (switch = ops/autopilot/switch.json, all false, page_repo ~/code/litert-bench-dashboard); exit 0, 20:55:05-20:55:59
git checkout bench-autopilot
```

(先に `--dry-run` を同じ引数で 1 回: exit 0、同じ message を印字、HEAD・ledger・file は不変。)

### (a) commit `c258edd8ad5adb635dad2fca7b77da3ed3793a33` (parent f3d5fae6、author / committer john-rocky <rockyshikoku@gmail.com>)

message 全文 (1 行):

```
results 2026-10-14 Galaxy S26 (SM-S942Q), litert-lm-cpu: v0.16.0, litert-lm-gpu: v0.16.0, llama.cpp: b8999: 7/7 cells of matrices/dashboard-text-v1-android-b2.cells in one dashboard-job sitting 02:00–09:07 JST (anchor admitted at ratio 1.019 vs 2026-10-12-catalog-x2-s26-android-e4b-gpu-retake, thermal nominal; the payload's own anchor rows at 0.985); text check 12/12; cpu-capped counted 9/33, past the line 15; FAILURES: none; not in this commit (--allow-subset): 2026-10-14-dashboard-v1-s26-b1-android (the admission reference of 2026-10-14-dashboard-v1-s26-b2-android); results/summary rebuilt from the git index (4739 -> 4772 lines)
```

`git show --stat` の要点: `79 files changed, 20152 insertions(+), 1 deletion(-)` — results/raw/2026-10-14-dashboard-v1-s26-anchor-android 14 file、results/raw/2026-10-14-dashboard-v1-s26-b2-android 63 file、results/summary/device-runs.csv、results/summary/README.md。それ以外の path なし。

### (b) summary

- device-runs.csv 4739 -> 4772 lines (+33 = anchor 6 record + b2 27 record)。
- `git diff --stat HEAD~1 -- results/summary`: `README.md | 2 +-`、`device-runs.csv | 33 +`、`2 files changed, 34 insertions(+), 1 deletion(-)` (README の行は「4738 → 4771 per-run device records」)。
- CI の summary-fresh 相当: c258edd8 を `git archive` で展開して build_summary.py → results/summary の 4 file すべて HEAD と同一。

### (c) P の build と check 4 本 (`EDGE_LLM_BENCH` = commit の tree の export、`--dist <page-out>`)

| check | exit | 秒 | 要点 |
|---|---|---|---|
| build.py | 0 | 0.2 | wrote index.html, cells.csv, cells.json, regression.json, regression.csv, aa.json, aa.csv |
| check_against_bench_dashboard | 0 | 1.2 | PASS (long-context ladders 71 cells equal、protocol cells 54 equal、0 unexplained) |
| check_regression | 0 | 0.1 | PASS |
| check_aa | 0 | 0.3 | PASS |
| render_check | 0 | 48.8 | PASS (headless Chrome 155.0.8059.80、screenshot 7 枚、「the page file names no local account or home path (found 0)」) |

FAIL なし。launch が挙げた「worktree の summary と main の disk summary の違い」は、build も 4 本も同じ export を読むので起きない。比較のため commit 前に HEAD 79b6448b の export でも同じ 5 本を回し全 PASS (render_check 48 s) だった。P の `git status --porcelain` (`?? .DS_Store`) と HEAD (8100b64) は試験の前後で同じ。`--no-page-commit` なので P の commit はない。commit していたら message はこうなった (同じ関数で生成):

```
dist: the page from the bench at c258edd8 — the 2026-10-14 Galaxy S26 (SM-S942Q) dashboard-job sitting 02:00–09:07 JST committed there; cells.csv 4 rows added, 4 removed (550 rows); checks: check_against_bench_dashboard, check_regression, check_aa, render_check PASS
```

変わる 4 cell は Galaxy S26 の Gemma 4 E4B の CPU arm (下の「op と delegate の観察」)。

### (d) LEDGER2 (worktree の `logs/dashboard-job/autopilot-ledger.tsv`、列 = started / ended / dirs / check / bench_commit / summary_lines / page / page_commit / push_bench / push_page / publish / note)

```
2026-10-18 20:55:05	2026-10-18 20:55:59	2026-10-14-dashboard-v1-s26-anchor-android 2026-10-14-dashboard-v1-s26-b2-android	2026-10-14-dashboard-v1-s26-anchor-android=PASS 2026-10-14-dashboard-v1-s26-b2-android=PASS	c258edd8ad5adb635dad2fca7b77da3ed3793a33	4739 -> 4772	build 0 0.2s; check_against_bench_dashboard 0 1.2s; check_regression 0 0.1s; check_aa 0 0.3s; render_check 0 48.8s		would push bench d9762f2c..c258edd8 (6 commits, 5 not made by this step)	no page commit to push	nothing to publish (no page committed by this step)	page: built and checked in /private/tmp/claude-501/-Users-USER-code-edge-llm-bench-wt-autopilot/23735949-447e-4021-86ff-49ab8546b41b/scratchpad/r3/real/page, not committed (--no-page-commit)
```

(note の path の account 名はこの file では USER に置き換えた。ledger は gitignored の logs/ の下で、元の行は名前のまま。) `would push bench` の 5 本は origin/main d9762f2c に無い d4f6794c / 7c0edbc2 / f132add5 / 79b6448b / f3d5fae6: switch を ON にしても、この branch では push を断る (この step が作った commit ではない)。

### (e) `git status --porcelain` (試験の後、autopilot-post-test の上)

```
?? results/raw/2026-10-18-bench-autopilot-dev/LANE.md
?? results/raw/2026-10-18-bench-autopilot-dev/ROUND3.md
?? results/raw/2026-10-18-bench-autopilot-dev/launch-r3.draft.md
?? results/raw/2026-10-18-bench-autopilot-dev/launch-r4.draft.md
```

K 以外は空。`git checkout bench-autopilot` の後も同じ 4 行 (results/raw に 2026-10-14-dashboard-v1-s26 の dir はなし、device-runs.csv は 4739 行に戻った)。一時 branch `autopilot-post-test` (c258edd8) は残した。

## JOB の接続

diff の要点 (`scripts/dashboard_job.py`、f3d5fae6):
- `attempt()` の戻りに 4 つ目 = その sitting が SESSION.json を書いた dir (`created` のうち SESSION.json がある物; dry run は作るはずの dir = `planned`)。既存の 3 つ (code / reason / 最後の dir) の意味は同じ。return は 3 箇所とも 4 値。selftest の `plan()` の unpack だけ合わせた。
- `main()`: 各 attempt の前に `sitting = []`、`code, reason, camp, sitting = attempt(...)`。ledger 行と `=== done` 行の後で `post_sitting(code, sitting, args.dry_run)`、`return code` は前と同じ値。
- `post_sitting()`: `code != EXIT_OK or not dirs` → None (何もしない)。dry run は印字だけ。それ以外は subprocess (cwd ROOT、出力は job log、timeout `POST_TIMEOUT_S` 3600)、`post exit N (…) — the sitting's exit 0 stands` の 1 行。exit code も ledger 行も変えない。
- 冒頭の docstring の「What the job never does: commit, push, …」を直した。

呼び出しの位置 (`scripts/dashboard_job.py:1470-1478`):

```python
        ledger({"started": started, "ended": ended, "device": key or "auto", "campaign": camp or "",
                "verdict": VERDICT_NAME.get(code, str(code)), "reason": reason,
                "exit": code, "minutes": round((time.time() - t0) / 60, 1),
                "attempt": attempt_no})
    log(f"=== done: {VERDICT_NAME.get(code, code)} ({reason}) exit {code}")
    # after the ledger line and outside the hold (attempt() released it): the sitting's
    # campaign dirs to the post step; nothing it does changes `code` or the line above
    post_sitting(code, sitting, args.dry_run)
    return code
```

`scripts/dashboard_job.py:888-892`:

```python
    if code != EXIT_OK or not dirs:
        return None
    cmd = [PY, POST] + list(dirs)
    log("post: $ " + " ".join(cmd) + ("   [dry-run: printed, not run]" if dry else ""))
    if dry:
```

dry run (`python3 scripts/dashboard_job.py m4max --dry-run 2>&1 | tail -30`、20:47、worktree) の末尾:

```
FAIL  Vendored engines        missing llama.xcframework, Anemll, LiteRT-LM, CoreML-LLM, coreai-models — run ios/BenchmarkApp/scripts/bootstrap.sh
FAIL  mac yardstick           no binary at /Users/USER/code/edge-llm-bench-wt-autopilot/.build/dd-mac/Build/Products/Release/yardstick — run scripts/build_yardstick_mac.sh (~15-30 min first time)
...
2 failure(s)
...
) exit 5
```

最後の行は `[…] === done: DEVICE (bench doctor --platform mac FAILED: …) exit 5`。preflight_mac の doctor FAIL → NotReady → code 5 → `post_sitting` は `code != EXIT_OK` で何も組まない = post 行なし。worktree には vendored engines と yardstick の build がない (main tree の job が使う物)。exit 0 の dry run で post 行が done 行の後に 1 本出る事は、`dashboard_job_selftest.py` が fake の S26 で確かめた (上の 4 checks、post 行 = `… scripts/dashboard_post.py results/raw/<date>-dashboard-v1-s26-anchor-android results/raw/<date>-dashboard-v1-s26-h1-android   [dry-run: printed, not run]`)。

## commit

- `f3d5fae6` (branch `bench-autopilot`、明示 path 8: scripts/dashboard_post.py、scripts/dashboard_post_selftest.py、scripts/dashboard_job.py、scripts/dashboard_job_selftest.py、ops/autopilot/switch.json、docs/dashboard-autopilot-v1.md、docs/dashboard-recurring-job-v1.md、.github/workflows/data-pipeline.yml)。帰属行なし、"claude" の語なし (hook も通過)。
- この ROUND3.md の commit (`bench-autopilot`、明示 path 1)。hash は監督への報告に書く。
- `c258edd8` は一時 branch `autopilot-post-test` の上だけ (試験の commit、merge しない)。push なし。

## 提案

1. **段 3a の接続 = `red` segment**: `post()` の `page_step()` の後、`push()` の前に `red_step(tree, page_out, facts, row)` を置く。入力は commit の tree の `results/summary/device-runs.csv` (bench 側で P の規則 = 同じ regime、前の shown point に対する vs_prev が -SPREAD_FLAG より下) と、page を作った時は `<page-out>/regression.json` の red の集合 (一致しなければ ledger に `red: mismatch`)。この sitting の device の点だけを見る (新しい点 = この sitting の行)。red がある時: retake の cells file (anchor 行 + その cell の行、docs §5 targeted retake) を `ops/autopilot/retakes.json` に積む → 次の `auto` が週の set の前にその device の retake を回す。LEDGER2 に `red` 列 (`red 1: <device> <arm> <model> <task> <metric> −7.2 % vs 10-07 → retake queued`)。P が無い環境でも bench 側の計算だけで動く (P は照合だけ)。
2. **HOLD でない「数字の消える」commit を知らせる**: 本物の試験の sitting は checker PASS だが、commit すると P の Galaxy S26 Gemma 4 E4B CPU の 4 cell が、10-06 と 09-14 の sitting の数字のある cell から「cpu-capped >15 %、数字なし」になる (最新の sitting が cell を決める規則どおり)。cpu-capped は checker では note (render の規則が扱う) なので PASS のまま。page の commit message か LEDGER2 に「measured → no number の cell 数」を出す (`page_message` に status の変化を数える) と、夜の commit で数字が消えたことが朝に分かる。消すか残すかの規則は owner の判断。
3. **CLAUDE.md の「the job never commits」** (`The dashboard recurring job is live` の段落の「let a person review SESSION.json and commit; the job never commits」) と **docs/session-check-v1.md 冒頭の「not yet wired into the job」「The dashboard job … never commits」** は、この round の commit 対象外なので直していない。main に merge する時に一緒に直す。
4. **checker の finding に構造化した dir 名を**: `--allow-subset` は session_check.py の detail の文 (`payload <dir> is neither committed nor in this set` と `admission reference <dir> is …`) を正規表現で読む。文が変わると waive が効かなくなる (安全側 = HOLD、selftest が CI で落ちて気づく)。checker が finding に `"dir": <name>` を足せば文を読まずに済む (checker の変更 = この round では禁止)。
5. **`.gz` log と binary の名前**: 掃除も checker も text file だけ。人の掃除は gzip log を解いて置き換え、`gzip -n` で戻した (8208edff)。job の dir に .gz が出る runner があるなら checker に足す。
6. **`--allow-subset` は「穴」を作る**: TEST PAIR を commit すると b2 の admission reference (b1) が record に無い (ROUND1 の reference-uncommitted 4 dir と同じ形)。夜の job は使わない (既定は sitting 丸ごと)。人が使う時は、reference の dir を先に commit できない理由を message に書く運用 (今は message が left-out の dir を名指すだけ)。
7. **switch を ON にする日の前提**: main tree の `main` は origin/main より 1 本先 (7c0edbc2、未 push) で、job の checkout は origin より遅れる事がある (docs §7.6)。post の push は「origin/main..sha が全部この step の commit」の時だけなので、その日の最初の post は断る。ON の前に人が main を origin に揃える (worktree で rebase、`<sha>:main` で push)。
8. **P の README の「disk copy」**: autopilot の page は commit の tree から作る (HOLD の sitting は人が commit するまで page に出ない)。P の README の「From results/summary/device-runs.csv (the disk copy, which includes sittings not yet committed …)」に autopilot の page の入力を 1 文足す (P への書き込み = この round では禁止)。
9. **REVIEW.md の扱い**: HOLD の dir の中に残る。人が手で commit する時に、残す (review の記録) か消すかを決めていない。docs/dashboard-autopilot-v1.md §5 に一行の規則を足す (提案: 手 commit では消し、理由は message に)。

## 経過

- 20:17 started; ListAgents read (this session = edge-llm-bench-wt-autopilot-55 [527e21]); next: read LANE.md / ROUND1.md / launch-r3.draft.md, dashboard_job.py, session_check.py, P.
- 20:40 read: job main()/attempt(), checker (rules, JSON, user-name forms), P build/checks/publish, the commit-msg hook, past results and dist commit subjects, the name-scrub commits d25a9985..ceeaa362. Baseline on a clean export of HEAD 79b6448b (temp index, 1.4 s, 293 MB): build_summary unchanged, P build + check_against_bench_dashboard / check_regression / check_aa / render_check all PASS (render_check 48 s), P status unchanged. TEST PAIR checked alone in the main tree: HOLD both (pair-incomplete / reference-uncommitted, a and b1 not in the set) → --allow-subset design (訂正). next: write scripts/dashboard_post.py.
- 20:55 scripts/dashboard_post.py + selftest (38 checks OK), dashboard_job.py hookup + selftest case (OK), session_check_selftest OK, py_compile OK; job dry run m4max from the worktree: doctor FAIL (no vendored engines / yardstick in the worktree) → exit 5, no post line (expected; that doctor run listed devices once: `xcrun devicectl list devices`, `adb devices`); docs, switch, CI step; committed f3d5fae6 (8 paths). next: the real test on autopilot-post-test.
- 20:56 real test: dry run exit 0 (nothing written), real run exit 0 → c258edd8 (79 files), summary 4739 -> 4772, P build + 4 checks PASS (render_check 48.8 s), P unchanged, LEDGER2 1 row, status = K only; CI summary-fresh equivalent on c258edd8: identical; back on bench-autopilot. next: CI rehearsal on a shallow clone.
- 20:58 CI rehearsal (shallow clone, env -i, python 3.11.13): 3 selftests exit 0, py_compile OK, summary unchanged. next: ROUND3.md, round_close_lint, commit, report.
- 21:01 ROUND3.md written (the record names f3d5fae6 and c258edd8; its own commit's hash goes into the report); round_close_lint: `PASS round close: /Users/USER/code/edge-llm-bench-wt-autopilot/results/raw/2026-10-18-bench-autopilot-dev/ROUND3.md`; next: the commit of this file by explicit path, then the one message to the supervisor.

## 訂正

- launch「TEST PAIR … backlog で両方 PASS」→ 2 dir だけで check すると両方 HOLD: anchor は `pair-incomplete` (payload 2026-10-14-dashboard-v1-s26-a-android と -b1-android が commit 済みでも set の中でもない)、b2 は `reference-uncommitted` (admission reference が -b1-android)。backlog の PASS は 77 dir を一度に check した結果 (a と b1 が「同じ check の中」)。worktree に 2 dir だけ cp した時は anchor PASS / b2 HOLD (reference-uncommitted)。そのため `--allow-subset` は「同じ sitting (`<date>-dashboard-v1-<device key>-`) の left-out dir を指す pair-incomplete (payload) と reference-uncommitted だけを通し、message に名指す」にした。payload の anchor phase が無い時はそのまま HOLD。証拠: 4 dir を一度に check すると anchor / b2 PASS、a / b1 HOLD (この round の 20:3x の実行)、`scripts/session_check.py` check_pair。
- launch 手順 3「`git checkout-index -a`(index = staged の dir を含む)」→ checkout の index には他 lane の staged file も入る (CLAUDE.md の手順は「`git diff --cached --name-only` が自分の path だけ」を前提にしている)。HEAD + この dir の temp index から作った。証拠: selftest (iii) の他 lane の staged record。
- launch 手順 3「`git commit -F <msg> -- <dirs> results/summary`」→ pathspec commit は commit の時点の working tree を読む: 夜は sitting が device ごとに並んで走り、別の sitting の `bench matrix` の最後の build_summary が disk の results/summary を書き換え得る。また summary を作った後に他 lane が commit すると、親が変わり summary がその commit の行を欠く。検査した tree を commit-tree し、update-ref の比較交換で HEAD を動かした (効果は同じ、窓なし)。証拠: `scripts/dashboard_post.py` commit_index、selftest (i)。
- launch 手順 5「`EDGE_LLM_BENCH=<REPO root>`」→ main tree の disk は commit と違い得る (他 lane の未 commit の matrices / scripts、その sitting の後の bench matrix の summary)。P は commit の tree の export から作った。証拠: memory manual-admission-reads-disk-summary「give all three one clean tree at the commit the page names」、P の README 74 行目 (disk copy を読む前提)。
- launch 停止条件・禁止「adb も devicectl も打たない」と受け入れ 3 の `dashboard_job.py m4max --dry-run` → この dry run は preflight で `bench doctor --platform mac` を回し、doctor は `xcrun devicectl list devices` と `adb devices` (一覧だけ) を打つ。1 回だけ実行した (20:47)。phone への shell / launch はない (Android は device が 2 台で BENCH_ANDROID_SERIAL がなく、`adb devices` の後で止まる)。証拠: `scripts/doctor.py:171`、`:197-202`。
- launch「名前の掃除 = `/Users/<account>` → `/Users/USER`」→ checker の user-name 規則は 5 つの形 (`/Users/<n>`、`/home/<n>`、`-Users-<n>-`、`_bazel_<n>`、ls の owner 列) を読む。`/Users/` だけでは scratchpad の形 (`-Users-<n>-`) の dir が HOLD のまま残る。人の掃除 (d25a9985) も同じ 4 形 + ls 列だった。5 形を置き換えた。証拠: `scripts/session_check.py` check_files、d25a9985 の message。
- launch の message の型「text check <k>/<N>」→ Apple の record は textCheck を持たない。`text check 0/0 (no run carries one)` と書いた (型どおり、0/0 の意味を括弧で)。

## 罠と袋小路

- zsh で `$(git ...)` の出力を `.strip()` した status の 1 行目は先頭の空白を失う (` M README.md` → `M README.md`): selftest の status 比較は strip しない (最初の run で 3 checks が落ちた、自分の selftest の誤り)。
- `--user ""` は checker の user-name 規則を切る (`make_context` が "" と "USER" を None にする)。dry run は「掃除が全部置き換えるなら」この形で checker を読む。`if user:` で flag を落とすと checker の既定 (`getpass.getuser()`) に戻り、規則が切れない (1 回目の実装の誤り)。
- `git -C <top> --work-tree=<tree> add -- results/summary` を temp index (`GIT_INDEX_FILE`) で打つと、export した tree の file を index に足せる (summary を checkout に写す前に commit の tree が決まる)。
- `git update-ref refs/heads/<b> <new> <old>` は old が違うと `cannot lock ref … is at X but expected Y` で exit 128: これが比較交換。`git hook run --ignore-missing commit-msg -- <file>` は init.templateDir の hook も回す (scratch の repo で「claude」を含む message が拒まれるのを確かめた)。古い git (exit 129) は REFUSED_WORDS の自己検査だけになる。
- commit message に「CLAUDE.md」と書くと commit-msg hook (claude|anthropic、大小無視) に拒まれる: code commit の message からは外した (docs の本文には書いてよい)。
- selftest の `--allow-subset` の sitting で anchor に dict の reference を渡し、anchor の reference-uncommitted が `\S+` に合わず HOLD になった (自分の selftest の誤り、anchor には文字列の reference だけ)。
- P の check は `--dist` の dir にだけ書く (render_check の screenshot も)。build.py と check を `PYTHONDONTWRITEBYTECODE=1` で回すと P の `__pycache__` も増えない。page の build は 0.2 s、check の時間はほぼ render_check (48-49 s)。

## op と delegate の観察

- なし (計測なし)。以下は TEST PAIR の record と P の check の出力を読んで気づいた事。
- 2026-10-14 Galaxy S26 b2 (07:15-09:07 JST; record の file 名の時刻は UTC 22:15-00:07): 27 run のうち cpu-capped 24。cpu-cap-rule で litert-lm-cpu 9 / 9 と llama.cpp 6 / 9 が 15 % の線を越え (数字なし)、litert-lm-gpu の 8 は accelerator arm なので数える (◇)。SESSION.json の thermal_gate の CPU ceiling は policy0 1785.6-2227.2 / 3628.8 MHz、policy6 1747.2-4646.4 / 4742.4 MHz (読んだ record は thermal status 0、screen on-usb)。
- その結果、この sitting を commit すると P の Galaxy S26 Gemma 4 E4B の CPU 4 cell (litert-lm-cpu short-chat / 1K、llama.cpp short-chat / 1K) が、09-14 と 10-06 の sitting の数字のある cell (同じ v0.16.0 / b8999) から「cpu-capped >15 % (2-5 of 2-5 runs)、数字なし」に変わる (「提案」2)。
- 10-14 の S26 anchor の admission reference は dashboard の sitting ではなく 2026-10-12-catalog-x2-s26-android-e4b-gpu-retake (同じ device・同じ build b8999 の最新の admitted session = catalog の campaign)。admit() は campaign の種類を問わない (memory の manual-admission-reads-disk-summary と同じ)。
- 10-14 b2 の record は LiteRT-LM v0.16.0 (litert-lm-cpu / -gpu) と llama.cpp b8999 を stamp する (S26 の v0.18.0 は 10-15 の release-triggered pass から)。

## 使った環境

- macOS 27.0 (Mac Studio M4 Max)、python 3.14.6 (homebrew `/opt/homebrew/opt/python@3.14`) で実行、CI の予行は python 3.11.13 (uv の既存 install) + `env -i`。標準 library だけ。
- git 2.54.0 (Apple Git-157)、hook = `~/code/standup/tools/git-hooks/commit-msg` (common dir の hooks/ と ~/.git-template の symlink)。
- headless Chrome: Google Chrome 155.0.8059.80 (P の render_check、`/Applications/Google Chrome.app`)。
- hold なし。端末への操作なし (doctor の device 一覧 `xcrun devicectl list devices` / `adb devices` が 1 回、「訂正」)。network なし (fetch / push なし)。main tree は読むだけ (git status / ls-files / show / log、file の読み出しと cp の元)。P は読むだけ (build / check は `--out-dir` / `--dist` を scratchpad に)。

## 残した file

- `scripts/dashboard_post.py`、`scripts/dashboard_post_selftest.py`、`scripts/dashboard_job.py`、`scripts/dashboard_job_selftest.py`、`ops/autopilot/switch.json`、`docs/dashboard-autopilot-v1.md`、`docs/dashboard-recurring-job-v1.md`、`.github/workflows/data-pipeline.yml` — f3d5fae6 で commit。
- `results/raw/2026-10-18-bench-autopilot-dev/ROUND3.md` (この file) — commit する。
- 一時 branch `autopilot-post-test` (c258edd8 = 本物の試験の commit) — 監督が読む。読んだら消してよい [消してよい: `git branch -D autopilot-post-test`]。
- worktree の `logs/dashboard-job/autopilot-ledger.tsv` (試験の 1 行、gitignored)、`logs/dashboard-job/.post.lock`、`logs/dashboard-job/2026-10-18-m4max.log` (受け入れ 3 の dry run) [消してよい]。
- scratchpad `/private/tmp/claude-501/-Users-USER-code-edge-llm-bench-wt-autopilot/23735949-447e-4021-86ff-49ab8546b41b/scratchpad/r3/`: `real/` (post.out = 本物の試験の出力全文、page/ = page の build と checks/*.out、commit-message.txt、ci/ = summary-fresh 相当の展開、p-status-before.txt ほか)、`base/` (HEAD 79b6448b の export と baseline の page / check 出力)、`ci-clone/` と `ci-*.out` (CI の予行)、`dryrun.out`、`gitexp/` (commit-tree / update-ref の予備実験)、`review_demo.py`、`commit1.txt`、`testpair-main.json` — 全部 [消してよい]。
