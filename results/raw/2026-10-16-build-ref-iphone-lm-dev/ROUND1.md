# D2 round 1 — build LiteRT-LM Android from a git ref: script, pins_add, `--engine-build`, selftest, docs (no device, no billing, no bazel)

Opus 5.5, launch `~/code/standup/launch/2026-10-16-D2D1-opus-r1.md`; supervisor `edge-llm-bench-8d [7abce4]`; worktree `~/code/edge-llm-bench-wt-buildref` (branch `build-from-ref`, HEAD 0efecb0 at the start). K = this dir.

## 経過

- 14:46 start; read the launch in full.
- 14:57 premises read (K/LANE.md, CLAUDE.md, build script, engine-pins.json, run_ddp.py, record.witness, run_cell 205-305, selftest.py in full, bench, android/README.md, README.md DDP section, docs/ddp-integration.md Route C, docs/OPERATIONS.md DDP runbook, data-pipeline.yml, T1c kit, lane and ~/code memories, D6 handoff §6, the quiet-window hook and quiet_wait.py). The Mac quiet window is held by another lane since 14:49 (`_GPU_LOCK` timing label, pid alive): code edits go on, every run goes behind quiet_wait.py. Next: step 1, android/scripts/pins_add.py.
- 15:01 step 1 done: android/scripts/pins_add.py (755, stdlib), a scratch run on stand-in files: dry run, add, the second add refused (rc 2), --replace, bad label, a label with a newline, no litert_lm_main + an LFS pointer named together, an empty dir, `--pins /dev/stdout` (not read: EACCES on macOS, said on stderr; the entry printed). Next: step 2, build_litert_lm_main.sh.
- 15:05 step 2 done: build_litert_lm_main.sh takes LITERTLM_REF (sha / branch / pr/N; a tag named there builds as LITERTLM_TAG), LITERTLM_DRY_RUN=1, writes 2 + n lines of SHA256SUMS and BUILD_INFO, calls pins_add.py (the embedded python is gone); `bash -n` passes under /bin/bash 3.2.57. Scratch dry runs: main, pr/4015, short shas 16ab549 / b7c40ea81 (tips), a tag via LITERTLM_REF, an annotated tag (v0.9.0: the peeled commit), refs/heads/main, an unknown branch (rc 1), both variables (rc 1); `~/.cache/apple-silicon-llm-bench/` unchanged, no android/bin. Next: step 3, `--engine-build` in run_ddp.py and bench.
- 15:10 steps 3-4 written: run_ddp.py `--engine-build <label>` (plan's tag, the label regex, `engine_files` names pins_add.py, `--records-only` refuses it, docstring (c)); bench: added lines only (usage, the non-ddp refusal, the pass-through, the argument); selftest section 1c (16 checks: pins_add on a temp copy of the pins, plan / witness with that copy, bench, py_compile + bash -n, the build script's dry run against a stand-in git); data-pipeline.yml line 83. The four python files parse under CPython 3.11.13 (the runner's version). Next: step 5 dry runs (behind quiet_wait where python runs), then step 6 selftest.
- 15:11 step 5 (a)-(e): r1/dryrun-{main,sha,pr,tag,both}.txt run directly (bash and git ls-remote only; the window had closed: lock empty, holder pid gone). Labels main-16ab54914 / main-ee3661364 / pr4015-8a4d77a20 / v0.18.0; (e) rc 1 naming both variables; r1/dryrun-nothing-made.txt: the cache dir's entries identical before and after, no android/bin. Next: the python batch.
- 15:13-15:14 the batch behind quiet_wait.py (waited 0 s): (f) rc 2 naming litert_lm_main, the kit's files and `shasum -c` identical before and after; (g) 9 of 9 sha256 = the v0.18.0 pin; (h) 8 jobs / 1 session / engine v0.18.0, the only difference from the run without the flag is the driver's command line; (i) rc 1 naming pins_add.py; selftest of HEAD (git archive copy) 73 checks rc 0, of the worktree 90 checks rc 0; android/engine-pins.json sha256 the same before and after; results/summary untouched. Next: step 7 docs.
- 15:17 step 7 docs written (android/README.md "Build from head or a PR", docs/ddp-integration.md bullet, docs/OPERATIONS.md bullet, README.md step 2 sentence); the added doc lines hold no ranking word, and `git diff` no home path (the scrub rule of BUILD_INFO rewritten as `/(Users|home)/` so the diff holds no literal one). The build script gained a python3 check before a real build. Next: the final selftest + a CI rehearsal (Python 3.11, huggingface_hub stubbed), behind quiet_wait.
- 15:17-15:18 on the final code, behind quiet_wait.py (waited 0 s): r1/selftest.txt 90 checks rc 0 (Python 3.14.6); r1/selftest-ci-rehearsal.txt 90 checks rc 0 (CPython 3.11.13, a huggingface_hub stub on PYTHONPATH that raises ModuleNotFoundError: the runner's conditions); r1/selftest-existing-checks.txt: the 73 check lines of HEAD's run = the worktree's less section 1c (5 lines differ in printed values only: temp paths, and deviceMinutes 936.0 in HEAD's run and 622.6 in the worktree's, because the git-archive copy has no results/raw for elapsed_basis). Next: round close, lint, commit, report (round close before the commit, so the committed ROUND1.md carries it; the commit hash goes in the report).

## 結果(受け入れ基準)

| 基準 | 結果 | file |
|---|---|---|
| 5 dry runs: labels, (e) exit 1 naming both, nothing cloned / fetched / built | main-16ab54914, main-ee3661364, pr4015-8a4d77a20, v0.18.0; (e) rc 1 `LITERTLM_TAG=y and LITERTLM_REF=x are both set`; cache entries identical, no android/bin | r1/dryrun-{main,sha,pr,tag,both}.txt, r1/dryrun-nothing-made.txt |
| (f) T1c kit refused by name, kit unchanged | rc 2 `no litert_lm_main`; files, sizes, mtimes and `shasum -c` (8 OK, as CHECK.txt) identical | r1/pins-add-t1c.txt, r1/pins-add-t1c-kit-unchanged.txt |
| (g) 9 sha256 = the v0.18.0 pin | 9 of 9 equal; the dry run against the default pins says `the same sha256 for all 9 files` | r1/pins-add-v0180.txt, r1/pins-add-v0180.log |
| (h) 8 jobs, 1 session, engine v0.18.0, diff only the flag | rc 0, `"jobs": 8, "sessions": 1, "engine": "v0.18.0"`; the diff with the run without the flag = the driver's command line only | r1/dryrun-ddp-v0180.txt, r1/dryrun-ddp-v0180.diff |
| (i) a label without an entry stops naming pins_add | rc 1 `android/engine-pins.json has no litert-lm main-ee3661364 entry — android/scripts/pins_add.py main-ee3661364 <dir>/main-ee3661364 writes it from the build's files` | r1/dryrun-ddp-missing.txt |
| selftest rc 0, checks > 73 | 73 -> 90 (17 added), rc 0; CI rehearsal 90 rc 0 | r1/selftest.txt, r1/selftest-ci-rehearsal.txt |
| pins and android_pins unchanged | android/engine-pins.json sha256 407bc78f… before and after; not in `git status` | r1/pins-unchanged.txt |
| docs: no ranking word in added lines, no home path or user name in `git diff` | 0 and 0 (67 added doc lines) | `git diff` |

## 分岐(launch が選ばせた所、指示の文から離れた所)

- selftest (iv): both forms. A subprocess reads the real pins (`run_cell.load_pins` refuses BENCH_TEST_PINS outside the FAKESELF serial: android/bench/run_cell.py 233-244), so `bench … --engine-build <pinned tag>` shows the driver started with the flag and the summary's engine, and `--engine-build main-012345678` shows the stop naming pins_add.py. The stand-in label's own plan is checked in process with `run_cell.load_pins` patched (ii).
- selftest (vi), not in the launch's (i)-(v): build_litert_lm_main.sh's dry run against a stand-in git (refs from a file): 7 ref forms -> label and commit, 2 refusals, only `git ls-remote` called, bazelisk never, nothing made under HOME or android/bin. It runs on the CI runner (no network, no NDK, no bazel).
- pins_add.py: a write keeps the file's own ending (no trailing newline today) instead of adding one (訂正 3); `--dry-run` with a label the file already holds prints the entry, rc 0, and says on stderr that a write needs --replace (the refusal is the write's); `--replace` writes the entry over wholesale, as the embedded python did, and names on stderr the old entry's keys that are gone (v0.18.0's `note` would be); it also refuses a pins file that json.dump(indent=2) would not write back as it is (the B-4 invariant), warns when another entry has the same tool sha256 (the witness takes the first match), and exits 1 on an I/O error.
- build_litert_lm_main.sh: fetches `refs/heads/<branch>`, `refs/pull/<N>/head` or the full sha, then stops if HEAD is not the sha ls-remote gave (a ref that moved in between); a short sha is resolved before the fetch (訂正 4); a tag named in LITERTLM_REF builds as LITERTLM_TAG; a `refs/heads/` prefix is dropped; a branch label turns every character outside `[A-Za-z0-9._-]` (not only `/`) into `-`; the `.so` set and git-lfs pointers are checked before bazel (pins_add.py checks again after); python3 is checked before a real build; BUILD_INFO also has `bazelisk=`; the bazel invocation (flags, targets) is the old one, now printed by the dry run through `run_in`; the default tag stays v0.17.0 ("今の既定 tag") while android_pins is v0.18.0.
- run_ddp.py: `engine_files` also stops on an entry without both tool sha256 (e.g. the NPU side build main-20260821-selfbuilt), and `--records-only` refuses `--engine-build`.
- The launch's (g) command line is used as written; its stdout is the JSON alone, stderr and the comparison are in r1/pins-add-v0180.log.

## 未

なし(この round の手順 1-9 は全部済み。r2 の build は GO 待ち)

## 訂正

- launch「upstream main HEAD = ee36613643」-> 15:0x は 16ab5491492f(PR #4013 が 2026-10-16 05:43:21Z = 14:43 JST に merge、その head = 新しい main HEAD)。(a) の label は main-16ab54914、(b) は sha 指定なので main-ee3661364 のまま — r1/dryrun-main.txt、`gh pr view 4013 -R google-ai-edge/LiteRT-LM --json state,mergedAt,headRefOid`
- launch「open PR の例 #4013」-> merge 済みで open でない。(c) は open の #4015(head 8a4d77a20)— r1/dryrun-pr.txt、`gh pr list -R google-ai-edge/LiteRT-LM --state open --limit 3`
- launch 手順 1「json.dump(indent=2) + 末尾改行」-> android/engine-pins.json は末尾改行なし(`tail -c 1` = `}`)、他の書き手 2 本も改行なしで書く(android/scripts/build_litert_lm_endurance.sh 85 行、android/scripts/fetch_llama_android.sh 83 行)。改行を足すと最初の write で entry 以外の byte(EOF)が変わり、後の 2 本と行き来する -> pins_add.py は file の末尾をそのまま保つ(selftest 1c の 2 本目が「entry を除くと元の byte と同一」を見る)— android/scripts/pins_add.py `write`
- launch 手順 2「40 桁未満の sha は fetch で解決、7 桁以上を受ける」-> git fetch の <src> は ref か「fully spelled hex object name」だけ(git-fetch(1)、`git help -m fetch` の <refspec> 節)= 短い sha は fetch できない -> fetch の前に解決: ref の先端(git ls-remote; LiteRT-LM は 4112 ref、main の commit は全部どれかの refs/pull/N/head の先端)、無ければ GitHub の commits API。7 桁以上を受ける点は launch どおり — android/scripts/build_litert_lm_main.sh、scratch の dry run(16ab549、b7c40ea81 は ref の先端として解決)
- launch 手順 2「SHA256SUMS は 9 行」-> 行数は 2 +(checkout の prebuilt/android_arm64/*.so の数)。v0.18.0 は 7 本で 9 行、main@HEAD の本数は r2 の clone まで未確認 — android/scripts/build_litert_lm_main.sh の SHA256SUMS 行
- launch (g)「`--pins /dev/stdout`」-> macOS では file に redirect した /dev/stdout は読みで開けない(`os.path.isfile` True、open は EACCES)。pins_add.py の dry run は「not read」を stderr に出して entry を印字する(rc 0)。既存 entry との照合は既定 --pins の dry run で取った — r1/pins-add-v0180.log
- 監督の 15:0x の訂正(K/LANE.md は stage しない、K の中は絶対 path を `~`)に従った。r1 の file は全部 home を `~`、user 名を `USER` に置換して確認(置換対象は `~` だけ、`USER` は 0 件)— r1/*、home path と user 名の grep 0 件

## 罠と袋小路

- macOS の /bin/bash 3.2.57(ここでは `#!/usr/bin/env bash` が最初に当たる)は `"${VAR:-…}"` の既定値の中の apostrophe を quote と読み、100 行以上後で「unexpected EOF while looking for matching `"'」を出す(179 行の `(the tag's commit…)` が 287 行の error)。`bash -n` を先頭 N 行ずつにかけて二分で特定、約 10 分 -> `${:-}` の既定値に apostrophe を書かない
- `bazelisk --version` を bazel の checkout の外で打つと最新の bazel を引く(bazelisk の cache の 9.3.0 が答えた、新しい download は無し)。build の版は checkout の `.bazelversion`(T1b の commit で 7.6.1)-> BUILD_INFO の版は build 後に checkout の中で `bazelisk version` から読む
- `git ls-remote <url> refs/tags/X` は annotated tag では tag object の sha だけを出す。commit は `refs/tags/X^{}` を明示した時だけ出る(v0.9.0: e515431 が tag object、991ef53 が commit; v0.18.0 は lightweight)-> 両方渡して `^{}` を優先
- python の `re.match(r"^…$")` は末尾の改行 1 つを通す(`$` は "\n" の前にも当たる)-> label の検査は fullmatch(pins_add.py、run_ddp.py)。scratch で "ok\nx" が rc 2
- launch の home path の grep(`git diff` に対する)は、BUILD_INFO から home path を消す sed 規則そのものに当たる -> 規則を ERE の `/(Users|home)/` で書いた
- dry run の command 行を `printf '%q'` で出すと正確だが読めない(`\<git\ describe\ …`)-> 要る所だけ single quote で囲む quote_args
- 14:49 に他 lane が計測窓を開けた(timing label、holder pid 生存)。code は書き続け、python を走らせる物は全部 quiet_wait.py の後ろに置いた。15:10 には lock が空、2 回とも待ち 0 s
- 1 回の Bash 呼び出しの `cd <K>` が session の cwd を K に動かした(D6 §6 の罠をもう一度踏んだ、15:2x)-> すぐ worktree に戻し、以後は絶対 path だけ
- HEAD と worktree の selftest の check 行は 5 行が値だけ違う: temp path と deviceMinutes(git archive の copy には results/raw が無く elapsed_basis が既定 600 s になる)。check の結果は 73 本とも同じ — r1/selftest-existing-checks.txt

## op と delegate の観察

なし(端末なし。この round は何も測っていない)

## 使った環境

- Mac(arm64、Darwin 27.0.0)、端末なし、hold なし。worktree `~/code/edge-llm-bench-wt-buildref`、branch build-from-ref、HEAD 0efecb0(round 中は commit 前)
- python3 3.14.6(/opt/homebrew の python@3.14)、huggingface_hub 1.8.0; CPython 3.11.13(uv の managed python、3.11 での parse と CI rehearsal だけ)
- git 2.54.0(Apple Git-157)、git-lfs 3.7.1(global の filter.lfs あり)、/bin/bash 3.2.57、Google Cloud SDK 587.0.0(呼んでいない)、gh(read だけ: pr list / pr view / api)、curl(GitHub commits API の read を 2 回)
- bazelisk(/opt/homebrew/bin、build は走らせていない)、NDK 28.2.13676358 と 29.0.13113456(script は 29.0.13113456 を選ぶ)
- pinned binary は main checkout の `~/code/edge-llm-bench/android/bin/v0.18.0/` を BENCH_ANDROID_BIN_DIR で読んだだけ

## 残した file

- code と文書(commit): android/scripts/pins_add.py(新規、755)、android/scripts/build_litert_lm_main.sh、android/ddp/run_ddp.py、android/ddp/selftest.py、bench、android/README.md、docs/ddp-integration.md、docs/OPERATIONS.md、README.md、.github/workflows/data-pipeline.yml
- K/ROUND1.md(この file)
- K/r1/dryrun-{main,sha,pr,tag,both}.txt = (a)-(e); K/r1/dryrun-nothing-made.txt = その後の cache dir と android/bin
- K/r1/pins-add-t1c.txt、K/r1/pins-add-t1c-kit-unchanged.txt = (f)
- K/r1/pins-add-v0180.txt(entry の JSON だけ)、K/r1/pins-add-v0180.log(stderr、既定 pins での dry run、9 sha の照合)= (g)
- K/r1/dryrun-ddp-v0180.txt、K/r1/dryrun-ddp-v0180.diff = (h)(diff の相手 = `--engine-build` なしの同じ dry run、93 KB のほぼ同文なので commit 前に消した: repo を小さく)
- K/r1/dryrun-ddp-missing.txt = (i)
- K/r1/selftest.txt = 最終の selftest; K/r1/selftest-ci-rehearsal.txt = 3.11 + huggingface_hub なし; K/r1/selftest-existing-checks.txt = 既存 73 本の比較(HEAD の run の全文は commit 前に消した: 本数、差の行、1c の 17 本はこの file にある)
- K/r1/pins-unchanged.txt = android/engine-pins.json の sha256 の前後
- K/LANE.md は監督の file(stage しない)
- scratch(session の scratchpad: 試験 script、stub、log、HEAD の archive copy)は報告の前に消す(消してよい)
