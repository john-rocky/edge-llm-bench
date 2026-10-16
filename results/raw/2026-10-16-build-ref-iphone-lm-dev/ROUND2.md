# D2 round 2 — LiteRT-LM main@HEAD built for Android from its git ref, selftest, DDP akita-35 / m1q-36 Qwen3-1.7B GPU short-chat (one cell each), K/MATRIX.md

Opus 5.5, launch `~/code/standup/launch/2026-10-16-D2D1-opus-r2.md`; supervisor `edge-llm-bench-8d [7abce4]`; worktree `~/code/edge-llm-bench-wt-buildref` (branch `build-from-ref`, HEAD ebe86aa at the start). K = this dir.

## 経過

- 15:23 start; read the launch in full.
- 15:24 premises read: K/LANE.md, K/ROUND1.md, android/scripts/build_litert_lm_main.sh, android/scripts/pins_add.py, android/ddp/run_ddp.py (`--engine-build` in `plan` and `main`), android/ddp/record.py (`witness`, `records_for_execution`), bench `do_ddp` / `postprocess`, android/README.md "Build from head or a PR", docs/OPERATIONS.md "Runbook: run cells on DDP", CLAUDE.md, the 10-15 records of the cell (akita-35 session-d5585b53, m1q-36 session-9002dfea), D6 handoff §6 / §7, the four lane memories and the two ~/code memories, quiet_wait.py. Next: step 1.
- 15:25 step 1: K/r2/head.txt = 16ab5491492f21722aea7b6440ecb797c2e25031 (git ls-remote 15:25:07, HEAD = refs/heads/main). The Mac window was held by another lane (timing label since 15:18:36, holder pid alive): the build went behind quiet_wait.py (`--max-wait 21600`) at 15:25:15 and started after 15 s; one background wait on K/r2/build.log (the launch's grep plus `gave up` and the quiet_wait pid's exit). Label main-16ab54914, commit = head.txt's. Next: step 2, then the build's end.
- 15:25 step 2: android/bin/v0.18.0 -> ~/code/edge-llm-bench/android/bin/v0.18.0 (symlink; android/bin/ is gitignored, `git check-ignore` .gitignore:61). Next: the build's end; meanwhile K/r2/cell.cells, K/r2/check_prov.py, the matrix script.
- 15:27 build: fetch end 15:25:45 (.git/FETCH_HEAD), checkout with the LFS smudge end 15:26:08 (.git/index), bazel 7.6.1 (the checkout's .bazelversion) with NDK 29.0.13113456 running; prebuilt/android_arm64 holds 7 .so (the v0.18.0 names) = SHA256SUMS will have 9 lines. Next: the build's end.
- 15:30 step 1 done: `== done:` (BUILD_INFO built=06:30:13Z = 15:30:13 JST). Clone 38 s (quiet_wait released 15:25:30 → fetch end 15:25:45 → checkout with the LFS smudge 15:26:08), bazel 244 s (`INFO: Elapsed time: 244.367s, Critical Path: 66.37s`, `4390 total actions`, 3276 local processes), copies + SHA256SUMS + BUILD_INFO + pins_add.py under 1 s. android/bin/main-16ab54914/ = 9 files + SHA256SUMS (9 lines, `shasum -c` 9 OK) + BUILD_INFO (commit = head.txt's; no line with a home path or the user name); android/engine-pins.json +16 lines = the entry main-16ab54914 only, android_pins.litert-lm v0.18.0 at HEAD and in the worktree, the file still ends without a newline — K/r2/build-out.txt. K/r2/build.log: home → `~`, the user name → `USER` (no `USER` before; 19 lines). Next: step 3 selftest.
- 15:32 incident (another lane's window): `tokreship-b1-gpu-Qwen3.5-2B_int8-tokv timing pid 38709 since 15:26:23` opened while the bazel build ran (started 15:25:30 behind quiet_wait.py, which looks once, at the start); the lock was empty at 15:29:53, with the load average at 103.49 / 50.37 / 29.70 (the build; another lane's gradle build at 215 % CPU too). That window's numbers ran under the build's load → one message to the supervisor. A pause guard for the bazel server tree (scratch `bazel_yield.py`) was written but not started: the build had ended.
- 15:33 step 3 done: `BENCH_ANDROID_BIN_DIR=<worktree>/android/bin ./android/ddp/selftest.py` (v0.18.0 symlink + main-16ab54914) rc 0, `ddp selftest OK (90 checks)` = r1's 90 (lock empty at 15:32:21) — K/r2/selftest.txt. Next: step 4 dry runs.
- 15:33 step 4 done: K/r2/dryrun-{akita-35,m1q-36}.txt rc 0 each: 1 job in 1 session, `labels.engine` main-16ab54914, the 9 engine pushes at `engines/litert-lm/main-16ab54914/<sha256>/<name>` (155,844,608 bytes), upload candidates 12 objects / 1,133,037,954 bytes = the 9 engine objects + the model (`models/2a72330b…`, 977,184,032), the prompt (`prompts/870aafb9…`, 48) and the wrapper (`wrapper/8e2880f6…`, 9,266), the last three the 10-15 slice's objects; args as on 10-15 except m1q-36 `--cpucap_wait=0` (10-15: 300; android/ddp/devices.json D14). The Hub's main (79bf0667, lastModified 2026-10-11) still has the file at 2a72330b… (= the cache's refs/main). Next: step 5.
- 15:34 step 5: the akita-35 driver started (nohup `$PWD/bench matrix … --ddp akita-35 --engine-build main-16ab54914 --campaign 2026-10-16-ddp-buildref-akita-35`, log K/r2/logs/akita-35.log); one background wait for its `session 1: operation` line. Next: the m1q-36 driver after that line.
- 15:35 akita-35 posted: the 9 engine objects uploaded (155,844,608 bytes), model / prompt / wrapper `in bucket`; operation `operation-1792132514074-65def5de4501f-b4c798dd-24781c29` created 06:35:14Z, session **session-733dfb76** (ddp/operation-create-1.json). 15:35:55 the m1q-36 driver started the same way (log K/r2/logs/m1q-36.log); one background wait for its POST. Next: the m1q-36 POST, then one wait for both drivers' end.
- 15:36 m1q-36 posted: all 12 objects `in bucket` (nothing uploaded twice); operation `operation-1792132564666-65def60e84a3c-9403e682-b39c2cd9` created 06:36:04Z, session **session-0214b9f1**. One background wait until both `bench` processes exit (their pids, not `pgrep -f <path>`: the waiting shell's own command line holds the path; the bench pid also covers the postprocess that rebuilds results/summary on disk). Next: step 6 record checks.
- 15:44 step 5 done (both `bench` processes exited by 15:44:53; a foreground wait on their pids kept this session awake): akita-35 session-733dfb76 PASSED (session 06:35:17Z-06:44:20Z), job j01 e8357a23 PASSED, execution b8a5425d PASSED (its directory is `execution-cbbaef9b-…`: the execution's id and displayName differ; record.py takes the directory from the report's output paths); runs 1-3 OK, decode 20.13 / 20.42 / 20.46, thermal nominal → nominal. m1q-36 session-0214b9f1 PASSED (06:36:07Z-06:43:29Z), job 8f8a6606 PASSED, execution 7d3a8982 PASSED; runs 1-3 OK, decode 36.7 / 37.47 / 37.71, every run `cpu-capped` (policy0 3187.2 / 3628.8, policy6 3398.4 / 4742.4 MHz; run 3 2227.2 on both). Scrub: akita-35 4 files (ssid 8, mac 9, ip 27), m1q-36 4 files (ip6 12, mac 51, mac-part 14). `git checkout -- results/summary` (bench's postprocess had rebuilt README.md and device-runs.csv from disk) and the rendered LEADERBOARD.md (untracked, gitignored) removed. Next: step 6.
- 15:45 step 6 (part): the Mac window was held again (`tokreship-b1-gpu-Qwen3.5-4B_mixed_int4-8q` since 15:41:27; bench's own postprocess ran inside it at 15:44 for seconds): check_prov.py, log_lines.py, matrix.py (and later reply_tokens.py) queued as one batch behind quiet_wait.py (15:45:40). Read directly meanwhile: the replies (akita-35 English, on-topic, identical in runs 1-3; m1q-36 on-topic but in **Portuguese**, identical in runs 1-3; v0.18.0 on 10-15: English on both ids) and the BenchmarkInfo blocks: main@HEAD has **two prefill turns** (19 tokens, then 133 on akita-35 / 150 on m1q-36), decode 650 / 849 tokens, `TextToTokenIds Turns (Total 0 turns)`; v0.18.0 one 19-token turn, decode 526 / 536. Next: the batch's outputs.
- 15:55 step 6 done (the batch ran 15:54:56-57 after 555 s of waiting through three windows of the same lanes): K/r2/record-check.txt `ALL OK`, rc 0: 3 records per campaign, `engineVersion` main-16ab54914, `engineArtifact` 320bee39d3ec… (= the entry's `litert_lm_main_sha256`), `conditions.ddp` session / job / execution / serial / fingerprint present, provenance.txt 9 of 9 sha256 = the entry on both units, model 2a72330b… and prompt 870aafb9… on the units, no FAILURES.txt, no `ddpMissing`, `gpuCache` not-loaded in run 1 and loaded in runs 2-3 on both, replies on-topic (m1q-36: Portuguese). K/r2/log-lines.txt (delegate, registration, E / F, Invalid decode, cache lines of all 12 runs), K/r2/reply-tokens.txt (turn 2 = the printed reply + 3 tokens on both units). Next: step 7.
- 15:57 step 7 done: K/r2/matrix.py → the arm_row rows (temp tree in the scratchpad; results/summary on disk untouched), K/r2/turns.py → K/r2/turns.md, K/MATRIX.md (4 rows, the turn table, notes; no ranking word, no difference). Next: step 8.
- 15:58 hygiene: K/r2/logs/*.log home → `~`, user name → `USER`; no file under K/r2, K/ROUND2.md or K/MATRIX.md holds a home path or the user name. Per-run logcat replacements (ddp/scrub.json): akita-35 runs 1-3 0 / 7 / 1, m1q-36 25 / 9 / 3; the execution logcat.txt (36 and 40 replaced) stays out of the commit. Next: round close, then step 8.
- 16:02 step 8: round close written and linted (PASS) first; staged by explicit paths (android/engine-pins.json, K/ROUND2.md, K/MATRIX.md, K/r2, the two campaign dirs with `':(exclude)results/raw/2026-10-16-ddp-buildref-*-android/ddp/*/*/*/logcat.txt'`): 88 files, K/LANE.md, the two execution logcat.txt and ddp-raw/ not staged. `git diff --cached` grep of the launch's address / home / user-name shapes: every hit holds Android's `02:00:00:00:00:00` (0 lines without it); no private IPv4 (10/8, 172.16/12, 192.168/16), no compressed IPv6, keyword (ssid / bssid / iccid / imei) lines hold counts only. Summary from the git index (CLAUDE.md's command, lock empty at 16:01:40): device-runs.csv 4483 -> 4489 lines (+6 = the six records), README.md count line 4482 -> 4488 records; `git add results/summary` → 90 files staged, all on this round's paths. Next: the commit (hash in the report), the report.

## 結果(受け入れ基準)

| 基準 | 結果 | file |
|---|---|---|
| android/bin/main-16ab54914/: 9 files + SHA256SUMS (9 lines) + BUILD_INFO | 9 files, SHA256SUMS 9 lines (`shasum -c` 9 OK), BUILD_INFO commit 16ab5491492f21722aea7b6440ecb797c2e25031 = K/r2/head.txt, no home path or user name | K/r2/build-out.txt |
| 所要時間 (clone, bazel) | clone 38 s (15:25:30 → 15:26:08, fetch 15 s + checkout with the LFS smudge 23 s), bazel 244.367 s (4390 actions) | K/r2/build.log, 経過 15:30 |
| android/engine-pins.json: only `litert-lm.main-16ab54914` | +16 lines, 0 removed; android_pins.litert-lm v0.18.0 at HEAD and in the worktree; still no trailing newline | K/r2/build-out.txt |
| selftest rc 0, checks = r1 | rc 0, 90 checks (r1 90) | K/r2/selftest.txt |
| DDP 2 sessions PASSED, 3 runs exit 0 each | session-733dfb76 (akita-35) PASSED, execution 405.922 s; session-0214b9f1 (m1q-36) PASSED, execution 353.875 s; exitCode 0 in all 6 runs | K/r2/record-check.txt |
| records 3 each: engineVersion, engineArtifact, provenance 9 sha, conditions.ddp, decode | `ALL OK`: main-16ab54914, 320bee39d3ec…, 9/9 on both units, ids present, decode 20.13 / 20.42 / 20.46 and 36.7 / 37.47 / 37.71 | K/r2/record-check.txt |
| replies 3 each on-topic | on-topic 6 of 6: akita-35 English; m1q-36 Portuguese (the same text in runs 1-3) | K/r2/record-check.txt, K/MATRIX.md |
| K/MATRIX.md: 4 rows, pooled = arm_row, no difference / ranking word | 4 rows + the turn table; grep of ranking words 0 (the only `%` = arm_row's cap fall of one row) | K/MATRIX.md |
| commit: campaign dirs + pins + K + summary from the index; no execution logcat; lab ids 0 | see 経過 (step 8) and the report | — |

## 分岐(launch の文から離れた所)

- 手順 8(a): `git checkout -- results/summary LEADERBOARD.md` fails as a whole (LEADERBOARD.md is untracked and gitignored) → `git checkout -- results/summary` alone right after the drivers ended (15:44), and the rendered LEADERBOARD.md removed (訂正 4).
- The waits: the build's grep also matches `gave up` and ends when the quiet_wait pid exits (訂正 7); the DDP wait is on the two `bench` pids, not `pgrep -f "$PWD/android/ddp/run_ddp.py"` (訂正 9); the DDP end was also awaited in the foreground (lane memory campaign-completion-is-on-disk: a background notice does not wake an idle session).
- Steps 6-7's Mac-side python ran as one batch behind quiet_wait.py (D6 r4's form): other lanes' windows were open from 15:41 to 15:54.
- K/r2/check_prov.py covers all of step 6's record items in one report (session report, provenance vs pins, record fields, flags, cache, replies), not only the provenance lines; its `engineArtifact` test reads the launched tool's field (short-chat: `litert_lm_main`).
- K/MATRIX.md has a second table (the BenchmarkInfo turns per run) and notes beside the launch's columns: the record's prefill of main-16ab54914 is turn 2's rate (訂正 6).
- K/r2/reply_tokens.py and K/r2/turns.py (not in the launch) count the printed reply with the cached Qwen3 tokenizer, to test what turn 2 is.
- Round close written before the commit, so the committed ROUND2.md carries it (r1's order); the commit hash is in the report.
- The clone's idle bazel server was shut down after the build (`bazelisk shutdown`; output base and clone kept).
- One message to the supervisor at 15:3x: the build overlapped another lane's window (連絡 (2)).

## 未

- What main-16ab54914 prefills in its second turn: not in the log (the size = the printed reply + 3 tokens on both units).
- Whether the Portuguese reply of main-16ab54914 on m1q-36 recurs on another S26 unit or another seed: one unit, and runs 1-3 print the same text (one sample).
- The harness reading of a two-turn BenchmarkInfo (`parse_litert` keeps the last prefill turn's rate and sums the turns' tokens): a supervisor decision; a pin bump to a build that prints two turns would change what `prefill_tps` means on every Android LiteRT-LM short-chat row.
- The summary surfaces: with the main-16ab54914 rows in results/summary, `render_leaderboard.latest_session` (the engines are not all version tags → the newest session) takes them for the DDP akita-35 / m1q-36 Qwen3-1.7B GPU short-chat cell of LEADERBOARD and the dashboard once pushed — a supervisor decision before any push (this commit is local).

## 訂正

- launch「bazel の output base は `~/.cache/bazel/`」→ macOS では `/private/var/tmp/_bazel_<user>/`(この build は `…/df8023c203a2224503c3baa2076657e0`; `~/.cache/bazel` は無い)— K/r2/build.log の DEBUG 行、`ls ~/.cache/bazel`
- launch「disk は 392 GB 空き」→ 15:24 に 334 GiB 空き — `df -h ~`
- launch「bazel の初回 build は cold で 10〜20 分 + clone(LFS の .so 7 本 ≈ 73 MB)」→ clone 38 s(LFS は全 platform の prebuilt を引いた: .git 706 MB、android_arm64 の 7 本は 69 MB)、bazel 244 s・4390 action(T1c main@b7c40ea81 は 3213)。output base は新規で、短かった理由は未確認 — K/r2/build.log、`du -sh`
- launch 手順 8(a)`git checkout -- results/summary LEADERBOARD.md` → LEADERBOARD.md は追跡されていない(.gitignore:67 `/LEADERBOARD.md`)ので pathspec が合わず command ごと失敗する → results/summary だけを戻した — `git ls-files LEADERBOARD.md`(0 行)、`git check-ignore -v LEADERBOARD.md`
- launch 手順 6「`metrics.prefillTokensPerSecond`」→ record の key は `metrics.promptTokensPerSecond`(summary の `prefill_tps`)— android/bench/parsers.py 82 行、scripts/build_summary.py 334 行
- launch の前提「record の prefill は v0.18.0 と同じ量」→ main-16ab54914 は BenchmarkInfo に prefill turn を 2 つ出し(19 token、次に 133 / 150 token)、`parse_litert` は最後の `Prefill Speed` を取り token 数を足す = main の record の `promptTokensPerSecond` は turn 2 の値、`promptTokenCount` は 152 / 169 — K/MATRIX.md、K/r2/turns.md、android/bench/parsers.py 72-91 行
- launch の待ち `until grep -q -E '^== done:|ERROR|FAILED|exit 75'` → quiet_wait.py は期限切れで「gave up after N s, command not run」と書き、`exit 75` の文字は出ない(期限切れでは待ちが終わらない)→ `gave up` と pid の生存を足した — ~/code/standup/tools/quiet/quiet_wait.py 82 行
- launch「bazel build は quiet_wait の形で背景に」→ quiet_wait は開始時に 1 回だけ見る: 他 lane の窓 `tokreship-b1-gpu-Qwen3.5-2B_int8-tokv`(15:26:23〜、遅くとも 15:29:53 まで)が build の開始 53 s 後に開き、build(load average 103)はその中で走り続けた。lane memory mac-quiet-window-leaks が既に「窓を先に取る」と書いていた。監督の以後の規則 = quiet_hold.py — K/LANE.md §3 15:3x、K/r2/build.log 1〜2 行
- launch の待ち `until ! pgrep -f "$PWD/android/ddp/run_ddp.py"` → 待つ shell 自身の command 行がその path を含み(自己一致)、bench の postprocess は run_ddp.py の終了後に走る → 2 本の bench の pid で待った — lane memory zsh-bash-tool-traps(self-matching pgrep)
- launch の返事の 3 分類(on-topic / empty / garbled)→ m1q-36 の main-16ab54914 は内容は on-topic だがポルトガル語(3 run 同文)。3 分類では on-topic とし、言語を併記した — K/r2/record-check.txt、ddp-out/run{1,2,3}.engine.txt

## 罠と袋小路

- quiet_wait.py は開始時に 1 回だけ窓を見る: 重い背景 job(bazel 4 分、load 103)が 53 s 後に開いた他 lane の窓の中で走り続けた → 重い Mac job は quiet_hold.py で窓を取ってから(監督の規則 15:3x〜)。bazel の server は job の process group の外の daemon なので quiet_yield.py の killpg では止まらない(pid の木を SIGSTOP する guard を scratch に書いたが、build が先に終わり使っていない)
- bench の postprocess(build_summary + render_leaderboard、約 4500 record)は driver の起動の後に開いた他 lane の窓(15:41:27〜)の中で 15:44 に数秒走った → driver を窓の外で起動しても postprocess は窓に入りうる(数秒の CPU。影響は未確認)
- `git checkout -- <追跡 path> <未追跡 path>` は未追跡の pathspec 1 つで全体が失敗し、何も戻さない
- `pgrep -f <path>` は、その path を command 行に持つ待ちの shell 自身に当たる → pid で待つ
- home path の grep は、その grep を説明する文(home の prefix を字面で書いた行)にも当たる → 規則は字面を書かずに説明する(build-out.txt と ROUND2.md の 2 行を書き直した)
- build の後も bazel の server が idle で残る(RSS 352 MB、既定 3 h で終了)→ clone の中で `bazelisk shutdown`(output base は残る)
- `bazelisk version` を checkout の外で打つと 9.3.0 が答える(r1 の罠のまま)。BUILD_INFO は checkout の中で読む = 7.6.1
- execution の id と displayName は違うことがある(akita-35: id b8a5425d、dir `execution-cbbaef9b-…`)→ dir は `execution-<id>` で探さず、report の output path から(record.py はそうしている)
- 返事の keyword 判定(on-device / AI)はポルトガル語の答えも on-topic にする → keyword ではなく本文を読む
- 15:25 の lock の読みを head.txt への redirect と同じ command に入れた(hook は止めなかった)。D6 r3 では止まった例がある → lock の読みは単独の command で

## op と delegate の観察

- 4 job の run 1(K/r2/log-lines.txt; 新 2 job と 10-15 の同 cell 2 job): GPU delegate `LITERT_CL` が prefill_128 994/994・prefill_1024 994/994・decode 936/936、各 1 partition(両 engine、両 id)。`RegisterAccelerator` は run ごとに LiteRT GPU ×3・CpuAccelerator ×3、`NPU accelerator could not be loaded and registered: kLiteRtStatusErrorNotFound` ×3。engine の E / F 行 0、`Invalid decode` 0(12 run 全部)
- GPU の program cache(12 run): run 1 は「Initializing OpenCL-based API from serialized data」×3 で「Initialized InferenceContext from serialized data」0(record: gpuCache not-loaded)、run 2・3 は両方 ×3(loaded)。Init Executor ms: akita-35 main 16042.93 / 7229.36 / 6306.83、v0.18.0 15144.76 / 7142.58 / 6291.00; m1q-36 main 8234.51 / 6115.54 / 5958.77、v0.18.0 8071.24 / 6059.35 / 5858.56
- akita-35(Mali)は両 engine の全 run に「Weights preparation on Gpu is disabled for PowerVR, Broadcom, Mali GPUs …」、m1q-36(Adreno)は 0
- run 1 の log の出所(file.cc の名)の集合は両 engine で同じ(両 id)。動いたのは行番号だけ(gpu_registry.cc 127→130、delegate_kernel.cc 979→1017、compiled_model.cc 829→874、cpu_registry.cc 75→73 など)
- BenchmarkInfo: main-16ab54914 は prefill turn 2 つ(19 token、次に akita-35 133 / m1q-36 150 token)と `TextToTokenIds Turns (Total 0 turns)`、v0.18.0 は prefill turn 1 つ(19 token)と 19 token の TextToTokenIds turn 1 つ。turn 2 の token 数 = 表示された返事の Qwen3 token 数 + 3(130 + 3、147 + 3; K/r2/reply-tokens.txt)。その turn に何を prefill しているかは log に無い(未確認)。TTFT は両 engine で akita-35 0.72〜0.74 s、m1q-36 0.25〜0.26 s
- decode token 数: main 650(akita-35)/ 849(m1q-36)、v0.18.0 526 / 536。表示された返事は 130 / 147、99 / 118 token。`--max_output_tokens=128` はどちらの engine も止めない(10-15 と同じ)。各 job の 3 run は同じ文を出す
- 返事: main-16ab54914 は m1q-36 でポルトガル語(on-topic)、他の 3 job は英語
- 新 6 run の engine の exit 0、thermal nominal → nominal(6 run)。m1q-36 の 3 run は cpu-capped + cpu-capped-at-start(policy0 3187.2 / 3628.8、policy6 3398.4 / 4742.4 MHz; run 3 は両方 2227.2)、akita-35 の 3 run は上限の低下なし(1704 / 2367 / 2914)
- logcat(run ごと): lmkd の kill は akita-35 main 21 / 22 / 3、v0.18.0 22 / 12 / 0; m1q-36 は両 engine で 0(run 1 の lmkd「Reclaim」main 35、v0.18.0 23)。m1q-36 の GPU 名の E 行は `E Adreno-AppProfiles: QSPM AIDL service doesn't exist` が両 engine で run ごとに 1 行。litert / tflite の E / F 行 0
- fp16 / fp32 の差、delegate から外れた op の fallback、compile の失敗: 測っていない(どの log にも LITERT_CL 以外の partition は無い)

## 使った環境

- Mac arm64、macOS 27.0(Darwin 27.0.0)。worktree `~/code/edge-llm-bench-wt-buildref`、branch build-from-ref、HEAD ebe86aa(commit 前)。手元の端末なし、adb なし、hold なし
- python3 3.14.6(Homebrew)、huggingface_hub 1.8.0、tokenizers 0.22.2(返事の token 数; tokenizer = HF cache の Qwen/Qwen3-1.7B `tokenizer.json`、offline)
- git 2.54.0(Apple Git-157)、git-lfs 3.7.1、gh(read: compare API)、Google Cloud SDK 587.0.0(account rockyshikoku@gmail.com、project litert-edge-portal、bucket gs://litert-edge-portal-devicerun; driver の呼びは auth print-access-token と storage ls / cp)
- bazelisk 1.29.0 → bazel 7.6.1(checkout の `.bazelversion`)、Android NDK 29.0.13113456(`~/Library/Android/sdk/ndk` の最新; 28.2.13676358 もある)
- LiteRT-LM main 16ab5491492f(2026-10-15T22:43:05-07:00「Add self-contained C++ SpanishG2p for Kokoro TTS (es).」)= label main-16ab54914。比較の v0.18.0 = b2f686e2e(`~/code/edge-llm-bench/android/bin/v0.18.0` を symlink で読んだ)
- DDP: akita-35 session-733dfb76(Pixel 8a、serial 45231JEKB16401、`google/akita/akita:15/BP1A.250405.007.B1/13240308:user/release-keys`)、m1q-36 session-0214b9f1(SM-S942U1、serial RFGL319PCKN、`samsung/m1quew/m1q:16/BP4A.251205.006/S942U1UEU1AZAD_OYM1AZAD:user/release-keys`)
- Mac の計測窓: build は quiet_wait.py の後ろ(待ち 15 s)、手順 6〜7 の batch も quiet_wait.py の後ろ(待ち 555 s)。quiet_hold は使っていない

## 残した file

- K/ROUND2.md(この file)、K/MATRIX.md(表)
- K/r2/head.txt(15:25 の upstream HEAD)、K/r2/build.log(build の log; home → `~`、user 名 → `USER`)、K/r2/build-out.txt(ls、SHA256SUMS、`shasum -c`、BUILD_INFO、pins の diff)
- K/r2/selftest.txt(90 checks rc 0)、K/r2/cell.cells(1 cell)、K/r2/dryrun-{akita-35,m1q-36}.txt(dry run)、K/r2/logs/{akita-35,m1q-36}.log(課金 run の driver の log)
- K/r2/check_prov.py → K/r2/record-check.txt、K/r2/log_lines.py → K/r2/log-lines.txt、K/r2/reply_tokens.py → K/r2/reply-tokens.txt、K/r2/turns.py → K/r2/turns.md、K/r2/matrix.py(→ MATRIX の行)、K/r2/compare.txt(v0.18.0 と main の commit の比較、GitHub API)
- results/raw/2026-10-16-ddp-buildref-{akita-35,m1q-36}-android/(execution の logcat.txt 抜きで commit; `ddp-raw/` は gitignore で disk に残る)
- android/engine-pins.json の entry main-16ab54914(commit)
- android/bin/main-16ab54914/(gitignore; 残す = r3 以降)、android/bin/v0.18.0(symlink、gitignore; 消してよい)
- `~/.cache/apple-silicon-llm-bench/litert-lm-main-16ab54914`(clone、.git 706 MB)と bazel の output base `/private/var/tmp/_bazel_<user>/df8023c2…`: 残す(再 build の cache)
- bucket: `gs://litert-edge-portal-devicerun/automation/inputs/edge-llm-bench/engines/litert-lm/main-16ab54914/…`(9 object、155,844,608 bytes)と `automation/sessions/session-733dfb76`・`session-0214b9f1`(driver は消さない)
- scratch(session の scratchpad: bazel_yield.py、r2_batch.sh、batch の log、check-*-v0180.txt、matrix-rows.md、pid の file): 消してよい
- K/LANE.md は監督の file(stage しない)
