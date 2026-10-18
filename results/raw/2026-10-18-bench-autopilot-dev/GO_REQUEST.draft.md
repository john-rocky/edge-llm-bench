# GO 依頼(下書き、r5 / r6 の後に数字を確定) — bench 自動化(夜の job → 自動レビュー・commit → page → 回帰の再測と原因候補)

## 今できている事(main に入った物 = local commit のみ、push は未)
- 段 0: iPhone 17 Pro は auto の対象外(`auto: false`、手動の道は残る)。
- 段 1: `scripts/session_check.py` = campaign dir を PASS / HOLD / FAIL(規則 30 本、全部に出典の commit hash、allow-list 25 行)。commit 済みの job session 88 dir: PASS 77 / HOLD 11(過去の commit が理由を書いていない物)/ FAIL 0。
- 段 2: `scripts/dashboard_post.py` = sitting の後に自動で: 名前の掃除 → checker → 全 dir PASS なら 1 commit(dir + git index から作り直した results/summary)→ private page の build + check 4 本 → push / publish は `ops/autopilot/switch.json`(全 false)。OFF の間は `logs/dashboard-job/autopilot-ledger.tsv` に「するはずだった差分」。今夜の firing から動く。
- 段 3a: `scripts/regression_watch.py` = page と同じ規則で赤を bench 側で計算(今の data で page と一致: 赤 8 点)。赤がその cell の最新 sitting なら次の firing で再測(retake sitting、週次 set の前)。再測後も赤で engine build が違えば bisect の要求 file + 下書きの骨。
- 段 3b(PR #4 の branch 上): `scripts/engine_bisect.py` = 09-17 の手動 bisect を DDP の S26 で自動再現 → 96b4819c(session 10、48 分)。issue 下書き EN / JA は local。
- 段 4: DDP の週次枠 `s26-ddp`(Galaxy S26 の lab 個体 m1q-36、hold も anchor も無し、attached device の sitting の後に走る、6 日に 1 回、switch `ddp_weekly` true)。今夜の本番 1 本 = 2 session・16/16 job・193 device-min・43 分 → checker PASS → post が自動で commit(0c82ff22、503 file、summary +72 行)。page の check 4 本のうち check_regression だけ FAIL(下の P の件)。
- 段 5: (r6 の結果をここに)

## GO (a) 常設: checker を通った session は自動で commit・push・publish
- 中身: `ops/autopilot/switch.json` の push_bench / push_page / publish を true にする。以後、毎晩 PASS の sitting → local commit → `git push origin main`(bench)→ page の rebuild + check 4 本 → P の dist commit → push → GCS の 7 object → 翌朝 page に載る。HOLD / FAIL の sitting は commit されず、dir の REVIEW.md と ledger に理由。
- 前提(ON の前に 1 回): main を origin に揃える(今 main は origin より 11 commit 先 = 今日の lane の commit。post の push は「origin/main..HEAD が全部 post 自身の commit」の時だけ押す = 人の未 push commit があるとその晩は押さず ledger に書く)。
- 条件つき GO の例: 「push_bench だけ ON、publish は人が」なども可(項目ごとの switch)。

## GO (b) backlog 77 dir(表: results/raw/2026-10-18-bench-autopilot-dev/backlog_table.md)
| class | dir 数 | 中身 | 推奨 |
|---|---|---|---|
| PASS | 27 | anchor 18 + payload 9(S26 09-29 / 10-05 / 10-11 の b1・b2、10-11 npu・ort、10-14 b2) | GO → post step で sitting ごとに commit(対の片方が HOLD の half は `--allow-subset`) |
| HOLD 衛生だけ(user-name) | 2 | Mac 09-30 / 10-05 | post の掃除で PASS になる → (b) の GO に含めてよい |
| HOLD 既知の欠陥だけ(reply-off-task) | 6 | S26 09-25 / 26 / 27 / 28 / 29-a / 10-05-a: Qwen3 1.7B GPU v0.16.0 が「explain という語」を説明する(odml.rope、0.17 で修正; 09-08 / 09-14 の S26 は人が同じ状態で commit 済み) | your call: allow-list に 1 行(hash = 欠陥を記録した commit)で commit するか、未 commit のまま(page にその週の S26 の点が出ない) |
| HOLD 混在 | 14 | partial / failures / text-fail / prompt-tokens / engine-stamp(Mac の lock が v0.16.0 のまま = registry の直し)など | 人が 1 dir ずつ(次の一手: dir ごとの推奨表を作る) |
| FAIL | 22 | refused 6、停止 1、SESSION.json なし 2、logcat 未 scrub 13(10-16 DDP の execution-level logcat.txt の残り 10 を含む = disk に置くだけ) | commit しない |

## P(private page)側の 1 件(GO というより次の一手の確認)
- `tools/check_regression.py` は「Regression の系列には cell の campaign の点がある」事を要求するが、S26 の Gemma 4 E2B GPU の 2 cell は今夜から lab 個体の stand-in が最新 = Regression の系列(phone 自身の sitting だけ)に点が無い → check FAIL(2)= post は bench を commit し、page の commit を止める(ledger に理由)。直し方は 2 つ: (a) check で stand-in の cell は phone 自身の最新点と照合する(check の修正だけ、page の見え方は不変)/ (b) Regression 対象の 2 model では stand-in を使わない(page の規則の変更)。推奨 (a)。どちらも P の変更 = 次の publish の GO に含める。

## GO (c) 1 件ずつ
- issue の投稿: bisect の ISSUE.en.md / ISSUE.ja.md は道具の汎用形(境界と再現 command)。09-17 の結論は group thread に投稿済みで、GitHub issue は内部アクセス後の起票で合意済み → 今は投稿しない(推奨)。
- PR #4 を Ready for review: 段 3b の道具は PR #4 の branch 上 = main に入れるには PR #4 が先。Kimish / SF の返事待ちのまま(10-17)。
- 新しい事実(報告先は your call): Hub の `litert-community/Qwen3-1.7B` の 10-11 の版(chat template の差し替え)は、0.18 より前の engine(8 月の build と v0.17.0 の binary)で user の文を落とす(Prefill 8 token = 空の user turn; v0.18.0 では 19 token)。card の注記か upstream への報告の候補。

## 通知(GO 不要の事実)
- Pixel 8a の `reboot_before` を外す変更(10-17 の他 lane の未 commit)を d4f6794c として commit した。
- DDP の週次枠(r5)は switch `ddp_weekly` で入る(user 10-16「DDP は GO 不要」に沿って既定 ON の予定; OFF にする語 1 つで止まる)。
