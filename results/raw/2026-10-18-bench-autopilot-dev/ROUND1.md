# ROUND1 — session checker (Opus 5.5, edge-llm-bench-wt-autopilot-2b [9fbf04], started 2026-10-18 19:31 JST)

Supervisor: edge-llm-bench-55 [4f120b]. Launch: ~/code/standup/launch/2026-10-18-autopilot-session-check-opus-r1.md

## 結果

`scripts/session_check.py <campaign dir>... [--json] [--markdown]` を書いた。夜の job の campaign dir を、212 本の
results/raw commit で人が確かめてきた点で PASS / HOLD / FAIL に分ける (exit 0 = 全 PASS / 1 = HOLD か FAIL / 2 = 使い方)。
規則 30 本 (表は 28 行、reply-* の 3 本を 1 行)、全部に出典の commit hash (`docs/session-check-v1.md`)。allow-list 25 行 (`ops/session-check/allow-list.tsv`、全行 hash つき)。

- (a) commit 済みの job session 88 dir: PASS 77 (指摘なし 39、allow-list で 38)、HOLD 11 (追加した commit の message が理由を書いていない = 下の「訂正」)、FAIL 0。
- (b) 既知の悪い dir 11: 全部 launch の書いた verdict (下の表)。
- (c) backlog 77 dir: PASS 27 / HOLD 28 / FAIL 22 → `K/backlog_table.md` (77 行)。12.3 s。
- (d) `scripts/session_check_selftest.py` 34 checks exit 0 (python 3.14 / 3.12 / 3.11)、`dashboard_job_selftest.py` も exit 0。CI に 1 step。
- commit: 下の「commit」節。push していない。

## 規則の表 (要約。全文と出典は docs/session-check-v1.md)

| id | 判定 | 出典 (commit) | 読む物 | 通る条件 |
|---|---|---|---|---|
| not-admitted | FAIL | 046c4dab, e3010721, 0efecb01 | SESSION.json admitted | admitted が false でない (TIMEOUT payload の anchor-short で dir に primary anchor の run が 2 本以上ある時は未判定 = verdict の HOLD) |
| session-missing | FAIL | 046c4dab, e998c56c | SESSION.json、job log の `--campaign` | job が作った dir に SESSION.json がある |
| stopped-sitting | FAIL | e3010721 | dir 名 | `-stopped-` を含まない |
| logcat-unscrubbed | FAIL | f231ad66, 0186dcd5, d6077c6b | DDP の logcat | execution-level logcat.txt が commit に乗らない、他の logcat に scrub.py が置き換える物が残っていない |
| big-file | FAIL | ca5dfe6e, 73620406, f3db1b23 | 拡張子、ELF / Mach-O の magic | 重み・trace・engine binary が commit に乗らない |
| secret | FAIL | c32f4705 | commit に乗る file の本文 | 認証情報の形がない |
| pair-broken | FAIL | e998c56c, 936c5ca3 | payload の anchor_phase | anchor phase の dir があり admitted |
| verdict | HOLD | 046c4dab, 84364fc1 | verdict | TIMEOUT / DEVICE でない |
| partial | HOLD | 65a36964, 69131de8, 178f0750 | cells_with_records / cells_expected | 全 cell に record |
| runner-exit | HOLD | 90c96a11 | runner_exit | 0 (124 は verdict) |
| failures | HOLD | 046c4dab, 936c5ca3, 178f0750 | FAILURES.txt | 行がない (Mac llama.cpp の teardown abort は allow-list、c7b60c2b) |
| flagged | HOLD | 046c4dab (§5 表), b6ddcb2c | FLAGGED.txt | LEVEL / DEGENERATE / GATE_ERROR / 書式外の行がない (HOT / SPREAD / DEAD / COLLAPSE は note: ⚠ で描かれる) |
| text-fail | HOLD | c6498ccd, edab6ed9 | conditions.textCheck | FAIL の run がない |
| engine-stamp | HOLD | edab6ed9, 0efecb01, d6077c6b, e3010721 | engineVersion、sitting 時点の pin registry (git log) | arm ごとに stamp 1 つで registry の pin |
| prompt-tokens | HOLD | edab6ed9, d6077c6b, e3010721 | promptTokenCount、HEAD の results/summary | 同じ platform・build・arm・model・task の commit 済み最頻値と同じ (同じ sitting は除く) |
| prompt-newtag | HOLD | edab6ed9 | 同上 | その build の履歴がない時、他 build の最頻値の 10 % 以内 (履歴の build 間差は最大 5 %、prompt が届かない時は 55 %) |
| reply-empty / reply-loop / reply-off-task | HOLD | e3010721, edab6ed9, 6dbaa099 | 返事 (outputSample / decoded.txt / engine log) | parsers.text_integrity と cell_gate.degenerate が何も立てない (runner の text check がない cell だけ) |
| gen-budget | HOLD | 8bd4cd71, b6ddcb2c | generatedTokenCount vs budget | budget を超えない |
| invalid-decode | HOLD | aaf64c5e, ee240588 | invalidDecodeCount、log | 0 |
| model-sha-source | HOLD | f41b3661, 0efecb01, d6077c6b | Android record の modelShaSource | f41b3661 以降は device |
| debug-build | HOLD | 5ad10ba8 | buildConfiguration | Debug でない |
| raw-log-missing | HOLD | ca5dfe6e, 0a6717bd | provenance.rawLog | log がある |
| record-unreadable | HOLD | c32f4705, 43fe4ffb | record file | parse できる |
| pair-incomplete | HOLD | e998c56c, 936c5ca3, 422983c7 | anchor_phase 両向き、git index | 対の片方が commit 済みか同じ check の中 |
| reference-uncommitted | HOLD | 0684f014, 422983c7 | admission の reference | commit 済みか同じ check の中 |
| user-name | HOLD | d25a9985, 8208edff, dde2149e, ceeaa362, af2c8b42 | commit に乗る file の本文 | `/Users/<name>` などの形がない (秘密ではない、FAIL にしない) |
| big-file-size | HOLD | 114a32e8 (と git ls-tree の最大 4,961,673 B) | 大きさ | 5 MB 以下 |
| not-job | HOLD | 046c4dab, 46235e36 | 種類 | job の campaign |

「人が 1 cell 1 sample を読む」: `--markdown` の末尾に cell ごとの返事 1 つ、表に cell 数 (`K/backlog_table.md` の「人が読む」列)。自動 PASS はこれを読まない。

## (a) commit 済みの job session (worktree の 88 dir: payload 45 + anchor 43)

PASS 77 / HOLD 11 / FAIL 0。allow-list 25 行は全部使われた (38 dir を PASS に)。HOLD 11 は全部「訂正」に 1 行ずつ。
1 本の規則が 10 % を超えて落とした dir のうち理由の立たない物はない (reply-off-task は allow-list 前 37 dir、うち 32 は commit が理由を書いている。残り 5 = 5.7 %)。

## (b) 既知の悪い dir (main tree の path)

| dir | verdict | 理由 (規則 id) |
|---|---|---|
| 2026-09-27-tts-rtf-v1-s26-anchor-android | FAIL | not-admitted (NOT_ADMITTED: anchor-collapse …), not-job |
| 2026-10-07-dashboard-v1-pixel8a-b1-android | FAIL | not-admitted (anchor-short), partial, runner-exit |
| 2026-10-07-dashboard-v1-pixel8a-b2-android | FAIL | not-admitted (anchor-short), partial, runner-exit |
| 2026-10-15-dashboard-v1-iphone18pro-ios | FAIL | not-admitted (anchor-short), partial, reply-empty, reply-off-task (+ pair-incomplete: anchor を同じ check に入れていない) |
| 2026-10-16-dashboard-v1-m4max-anchor-mac | FAIL | not-admitted (ABORTED: anchor-collapse), engine-stamp |
| 2026-10-16-dashboard-v1-m4max-r2-mac | HOLD | verdict (TIMEOUT; SESSION.json の admitted false (anchor-short) は再ビルドされなかった summary 上の再判定 = 未判定、dir に primary anchor の run 2 本), engine-stamp, partial, prompt-newtag, reply-empty, reply-off-task, user-name |
| 2026-10-17-dashboard-v1-iphone18pro-ios | FAIL | not-admitted (anchor-short), partial, reply-empty, reply-off-task |
| 2026-10-17-iphone17pro-aa-i1-stopped-0155-ios | FAIL | stopped-sitting |
| 2026-10-07-dashboard-v1-pixel8a-b1r2-android | FAIL | session-missing (SESSION.json なし) |
| 2026-10-14-dashboard-v1-s26-ort-android | FAIL | session-missing (SESSION.json なし) |
| 2026-09-17-ddp-litert-lm-caiman-35 | FAIL | logcat-unscrubbed: `ddp-session/session-944b220b/litert-lm-pixel-9-pro/execution-a7408d24-…/logcat.txt` (untracked, execution-level)、`rehearsal-pixel8a-v2/output/gpu_logcat.txt` (untracked, ip6 7)、`rehearsal-pixel8a-flat/output/gpu_logcat.txt` (tracked, mac 2); not-job |

## (c) backlog 77 dir

`results/raw/2026-10-18-bench-autopilot-dev/backlog_table.md` (77 行、列: dir / 種類 / verdict / 理由 / tracked・untracked / ledger の行 / 人が読む / 備考)。
集計 PASS 27 / HOLD 28 / FAIL 22。種類別: job anchor 18 / 3 / 1、job payload 9 / 21 / 6、job payload (stopped) 0 / 0 / 1、DDP 0 / 2 / 13、hand run 0 / 2 / 1。
10-16 の DDP 10 dir は「commit 済み (d6077c6b)。残りは execution-level logcat.txt だけ (untracked)」と備考に書いた (FAIL = その logcat を commit しない)。
PASS 27 の内訳: 09-25..10-17 の admitted anchor 18、payload 9 (S26 09-29 / 10-05 / 10-11 の b1・b2、10-11 の npu・ort、10-14 b2)。

## (d) selftest の出力の末尾

```
  ok  the same two checked together: PASS
--- usage
  ok  a path that is not a directory: exit 2 (got 2)

selftest OK
```
34 checks (PASS 1 組、HOLD 規則 10、FAIL 規則 7、allow-list 2、対の欠け 4、exit code)。`python3 scripts/dashboard_job_selftest.py` も selftest OK (54 checks)。
`.github/workflows/data-pipeline.yml` の `python scripts/dashboard_job_selftest.py` の次に 1 step。

## (e) 速さ

`python3 scripts/session_check.py <77 dirs> --json --markdown -q: 10.65s user 0.91s system 93% cpu 12.345 total` (Mac Studio、3 分の枠の 7 %)。

## commit

(下の 2 行目を commit 後に書く)

## 提案

出典の commit がないので規則にしなかった物と、段 2 への接続点。

1. 段 2 の接続: `dashboard_job.attempt()` の close で、作った dir (anchor + payload + extra) に `scripts/session_check.py <dirs> --json logs/dashboard-job/<date>-<device>-check.json` を掛け、dir ごとの verdict を ledger の reason に足す。全 PASS なら明示 path の commit + index からの summary 再生成、HOLD / FAIL は朝の brief に理由の規則 id を出す。exit code (0 / 1) をそのまま分岐に使える。
2. account 名の置き換え (`/Users/<name>` → `/Users/USER`) を job の close でやる: commit 済みの job dir は全部人が置き換えている (user-name が 10-12 / 10-16 Mac で 137-139 file、ORT / ExecuTorch の record が絶対 path を持つ)。今は HOLD。
3. Apple の runner に text check を足す (`conditions.textCheck`): Mac / iPhone の 1K で Gemma 4 E4B が拒否文や `[Item N]` を返しても summary には残らず、この checker の proxy だけが拾う (f80eaae3 の Mac、iPhone 18 Pro 10-08/15/17)。
4. llama-cli の返事の切り出し (`llama_reply`: echo の後の backspace spinner から `[ Prompt:` まで) を `android/bench/parsers.py` に移し、Android llama.cpp CPU arm の text check に使う。
5. 端末の (DDP でない) logcat の scrub: 09-17 dir の tracked `rehearsal-pixel8a-flat/output/gpu_logcat.txt` に MAC 2 件 (991157b3)。DDP 以外の logcat を決める commit がない。
6. iOS console の bundle id の個人名: ea6fc29 で一度置き換え、e3010721 で再び commit。決めた commit がないので規則にしていない。
7. cells_with_records を dir の record から数え直す (cells file が repo にある時): 43fe4ffb の allow-list 行 (native import 後) が要らなくなる。
8. allow-list の hash が repo にあるかの確認 (`git cat-file -e`、shallow clone では飛ばす)。

## 経過
- 19:31 started; ListAgents read (this session = edge-llm-bench-wt-autopilot-2b [9fbf04]); next: read the 212 results/raw commits and the docs.
- 19:43 read: 212 commit messages, job doc §1-§9, fairness-rules, build_summary / render_leaderboard / render_dashboard / dashboard_job / cell_gate / parsers / scrub, schema; surveyed the 88 committed SESSION.json dirs (records, FAILURES / FLAGGED / THERMAL_GATE / SKIPPED) and the 77 backlog dirs (git status, size, SESSION.json, ledger); next: prototype scripts/session_check.py and run it over the 88.
- 19:52 first draft over the 88: PASS 39 / HOLD 49; reply-off-task hit 37 dirs — read the samples: real (the Qwen3 0.6B v0.18.0 anchor rows answer a hallucinated question; Qwen3 1.7B GPU v0.16.0 answers about the word "explain"), not an extraction bug; next: allow-list from the adding commits.
- 19:57 allow-list (25 lines): (a) PASS 77 / HOLD 11, the 11 not explained by their adding commit → 訂正; backlog first pass 12 s; fixed my own false hits (llama-cli spinner + truncated echo read as a loop, a README "not committed" about traces/ read as a stopped sitting, ORT's buildConfiguration string read as Debug); account name made HOLD (hygiene, not a secret); binaries by magic made FAIL.
- 20:03 (b) all as expected; selftest written, PASS; next: docs/session-check-v1.md, the backlog table, the CI step, the commit.
- 20:10 review pass over the checker (Android registry before android_pins, Invalid decode counted once per log), every rule row given a commit hash (33 hashes, all resolve), selftests on python 3.11 / 3.12 / 3.14, backlog table written; next: commit, shallow-clone CI rehearsal, round close.

## 訂正
- launch「payload 54 dir + anchor dir」→ SESSION.json を持つ commit 済み -dashboard-v1- dir は payload 45 + anchor 43 = 88 (111 dir 中; 残り 23 = 09-05 first pass 11、10-07 llama retake 2、10-16 DDP 10)。証拠: `git ls-files results/raw | grep -- -dashboard-v1-`。
- launch「Qwen3 0.6B の anchor 行 … commit e3010721 / 1798483f」→ 1798483f の message は 9 token に触れていない。allow-list は e3010721 (と仕組みの edab6ed9) を引いた。
- (a) 2026-09-08-dashboard-v1-m4max-mac gen-budget: 6dbaa099 は書いていない (LiteRT-LM Qwen3 1.7B が 128 の上限に 579 token、thought channel)。説明は後の 8bd4cd71 → 過去の commit に穴。規則は残す。
- (a) 2026-09-09-dashboard-v1-iphone17pro-retake-ios gen-budget: 69131de8 も同じ (492 > 128)、8bd4cd71 で後から説明 → 過去の commit に穴。
- (a) 2026-09-08-dashboard-v1-pixel8a-a-android reply-off-task: 936c5ca3 は書いていない。Qwen3 1.7B GPU (wi4b32) v0.16.0 が 3 / 3 で「explain という語」の説明を返す (09-13 に見つかった odml.rope の語順の欠陥、adfbddbe / 7c565a8d / e53285bf) → 過去の commit に穴。
- (a) 2026-09-08-dashboard-v1-s26-android reply-off-task: e998c56c、同じ → 過去の commit に穴。
- (a) 2026-09-14-dashboard-v1-s26-android reply-off-task: 90c96a11 (欠陥が見つかった翌日の commit)、同じ → 過去の commit に穴。
- (a) 2026-10-07-dashboard-v1-pixel8a-a-android reply-off-task + text-fail + failures: 46235e36 は Qwen3 1.7B GPU short-chat の同じ欠陥も、1K の text check FAIL 6 / 6 (rc=1 x3、docs/dashboard-cells-v1.md 未決 8、S26 側は f80eaae3 が書いた) も書いていない → 過去の commit に穴。
- (a) 2026-10-06-dashboard-v1-m4max-longctx1024-mac reply-off-task / reply-empty: f80eaae3 は書いていない。Gemma 4 E4B 1K で MLX が lorem の prompt を拒否、llama.cpp が `[Item N]` を 256 token、どちらも 4 / 4 (Mac に text check はない) → 過去の commit に穴。
- (a) reference-uncommitted 4 dir: 2026-10-06-dashboard-v1-m4max-longctx1024-anchor-mac (f80eaae3、参照 2026-10-05-dashboard-v1-m4max-mac)、2026-10-07-dashboard-v1-pixel8a-anchor-android (46235e36、参照 2026-10-02-dashboard-v1-pixel8a-android)、2026-10-15-dashboard-v1-pixel8a-0180-p1-anchor-android (edab6ed9、参照 2026-10-13-dashboard-v1-pixel8a-b2-android)、2026-10-15-dashboard-v1-s26-0180-s5a-anchor-android (0efecb01、参照 2026-10-14-dashboard-v1-s26-b2-android): admission の参照が main tree の未 commit dir にしかない (0684f014 と同じ形) → 過去の commit に穴。backlog の参照 dir を commit すれば閉じる。
- 2026-09-17-ddp-litert-lm-caiman-35: launch が挙げた untracked の execution-level logcat.txt に加え、commit 済み (991157b3) の `rehearsal-pixel8a-flat/output/gpu_logcat.txt` に MAC 2 件が残る。証拠: K/backlog_table.md の当該行、`android/ddp/scrub.py` の scrub_text。
- 2026-10-16-dashboard-v1-m4max-r2-mac の admitted false は、TIMEOUT で殺された bench matrix が summary を作り直さず、job の payload 再判定が行 0 で anchor-short にした物 (SESSION.json の anchors n 0、dir には mlx anchor の record がある)。launch の期待どおり HOLD (verdict) にした。
- 2026-10-14 の S26 sitting には ledger の行がない: ORT の extra file の thermal 待ちの途中で終わった (logs/dashboard-job/2026-10-14-s26.log の末尾 09:07:30 hold released)。ort dir は session_provenance.txt 1 つだけ。

## 罠と袋小路
- zsh で `git show $c:android/…` は `$c:a` の修飾子 (絶対 path) に化ける: `${c}:` か python で読む。`echo =====` も `=` 展開で落ちる。
- llama-cli b8999 の log は prompt の echo (500 byte で `... (truncated)`) の後に backspace の spinner が入る: `parsers.llama_cli_reply` を prompt なしで使うと echo の続きと spinner を返事として読み、1K の返事が全部「繰り返し」に見えた。spinner の後から切る (`llama_reply`)。
- README の「not committed」で stopped dir を見分けると、commit 済みの hand-run dir (perfetto: 「traces/, not committed」) まで FAIL になった: 名前 (`-stopped-`) だけで見る。
- Mac ORT の record の `device.buildConfiguration` は "PyPI wheels (onnxruntime…)" という説明文: `!= Release` で見ると全部 Debug 扱いになる。"debug" を含む時だけ。
- `android_pins` は d33ffa53 (2026-10-15) から。それより前の Android の pin は `environment.lock.json` arms.litert-lm.android.tag_built (ORT は release_aar の URL)。今の registry で過去の sitting を見ると v0.16.0 の sitting が全部 HOLD になる: sitting 時点の commit を git log で選ぶ。
- job の SESSION.json の cells_with_records は close 時点の disk summary から数える: 後から import した native record (43fe4ffb) は数に入らない。
- hand の sitting も `dashboard-job-session.v1` の SESSION.json を書く (`job` の文が違う): schema だけで job dir とは決められない。
- 自分の selftest の引数の渡し方の誤り (`over=` を二重に包んだ) で HOLD 2 件が出なかった: 失敗した run の temp dir は消した。

## op と delegate の観察
- なし (計測なし)。以下は record を読んで気づいた事。
- Mac の yardstick は 2026-10-12 から LiteRT-LM v0.18.0 を stamp する (10-12 / 10-16 の 5 dir、anchor 含む)。`environment.lock.json` arms.litert-lm.default_tag は v0.16.0 のまま → engine-stamp HOLD。
- Mac LiteRT-LM v0.18.0 の Qwen3 1.7B / 4B は 10-12 は prompt 19 / 20 token、10-16 (r2) は 8 token、返事は問いと無関係 (4B は中国語)。Android の template 不一致 (docs §4) と同じ形。原因は未確認。
- Qwen3 0.6B LiteRT-LM v0.18.0 は prompt 9 token、返事は架空の問いへの答え (commit 済み 30 dir: anchor 28、p1 payload、iPhone 17 Pro AA payload)。
- Qwen3 1.7B GPU (wi4b32) v0.16.0 Android の short-chat は「explain という語」の説明を返す: commit 済み 4 dir、backlog 9 dir (09-25 .. 10-13)。backlog の 10-14 S26 a も同じ規則に当たるが、こちらは prompt 8 token (Hub の新 template) の方。
- Gemma 4 E4B の 1K: llama.cpp が `[Item N]` の並び (Mac 10-06 commit 済み・10-12 backlog、iPhone 18 Pro 10-08 / 15 / 17)、MLX が拒否文 (Mac 10-06・10-12・10-16)。Mac 10-06 の LiteRT-LM も拒否文 64 token だが on-device AI の語を含むので screen は通る (proxy の限界)。
- 2026-10-02 Pixel 8a: llama.cpp Qwen3 4B / Gemma 4 E4B short-chat の retry が LEVEL 20 / 18 (first COLLAPSE 28 / 22)。
- 2026-10-14 S26: Qwen3 1.7B / 4B が v0.16.0 で 8 token (Hub の新 template、docs §4 が書いた通り)、1K は text check FAIL。

## 使った環境
- macOS 27.0 (Mac Studio M4 Max)、python 3.14.6 (homebrew) で実行、selftest は 3.12.12 (homebrew) と 3.11.13 (uv の既存 install) でも実行。標準 library だけ (checker は repo の build_summary / cell_gate / dashboard_job / render_leaderboard / android/bench/parsers / android/ddp/scrub を import)。git 2.x。
- hold なし、端末 (adb / devicectl) なし、network なし。main tree は読むだけ (git status / ls-files / show / log と file の読み出し)。

## 残した file
- `scripts/session_check.py` — checker (commit する)。
- `scripts/session_check_selftest.py` — CI の selftest (commit する)。
- `docs/session-check-v1.md` — 規則の表と出典 (commit する)。
- `ops/session-check/allow-list.tsv` — 25 行 (commit する)。
- `.github/workflows/data-pipeline.yml` — 1 step 追加 (commit する)。
- `results/raw/2026-10-18-bench-autopilot-dev/ROUND1.md` (この file)、`backlog_table.md` (commit する)。
- scratchpad (`/private/tmp/claude-501/-Users-USER-code-edge-llm-bench-wt-autopilot/b16ecbda-ffc6-452b-8e36-70ad3e617f11/scratchpad/`): runs/*.json・*.txt・*.md (a / b / c の生出力)、survey/*.py、make_table.py、rawlog.txt — 消してよい [消してよい]。
