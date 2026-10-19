# ROUND16 — MLX Gemma 4 page rows: QAT (OptiQ) + PTQ (4bit) (worker edge-llm-bench-wt-autopilot-q06-e1 [dda0ab], Opus 5.5, started 2026-10-19 11:52 JST)

Supervisor: edge-llm-bench-55 [4f120b] (K/LANE.md first line). Branch `mlx-ptq-rows` in `~/code/edge-llm-bench-wt-autopilot-q06`, from main at 80a36462.

## 経過

- 11:52 launch read; ListAgents (self = edge-llm-bench-wt-autopilot-q06-e1 [dda0ab], supervisor present, busy); HEAD 80a36462, tree clean. Next: survey (step 1).
- 11:53–12:00 下見: cells の行番号、LOGICAL_MODELS、render_dashboard の行の名前の付け方、P の build.py / check / dist/cells.json、catalog(MAIN = SIDE、cmp 一致)、app の MLX の読み先(swift-huggingface の HubCache)。
- 12:00–12:05 cells 2 本に PTQ 行 12 本(text-v1 8、longctx1024 4)と header、LOGICAL_MODELS に 3 行、`matrices/mlx-gemma4-file-ios.cells` を作成。validate 3 本 PASS、全 147 file PASS。
- 12:05–12:09 render_dashboard(--check と 3 file の render)、test_render_rules、leaderboard の generate、selftest 5 本、Android selftest 3 本、py_compile。`android/bench/test_longctx1024.py` だけ FAIL(1K の対の数 64 を書き込んだ assert、今は 68)= launch の書く範囲の外 → patch を K/tools に用意(下の「CI の下稽古」)。P を私の branch に向けて scratchpad に build、P の check PASS。
- 12:09–12:14 docs の節、転送 script と dry run(PASS)。
- 12:14 18 Pro の llama.cpp retake が終わった(ledger 12:14:22 OK)。hold は空(holder none、queue 空)。転送も計測も監督の go の後(launch 手順 8)= まだ端末に触れていない。次 = commit、監督へ「Mac 側 PASS、端末待ち」。
- 12:17:19 commit a71f1b5a、12:17:32 ca5321c9(hash の追記。その行に 12:18 と書いたのは clock を読む前の誤り、ここで直した)。次 = 監督へ「Mac 側 PASS、端末待ち」、go を待つ。(12:24 の履歴の書き換えの後の hash は「commit」節)
- 12:18 監督へ「Mac 側 PASS、端末待ち」の 1 通(手順 1〜7 の結果、test の patch をどう当てるかの問い、P の名前の件)。次 = go を待つ(端末には触れない、enqueue もしない)。
- 12:19–12:21 手順 8 の driver `K/tools/r16_step8.sh`(keeper → enqueue + wait → 転送 → release → 待ち行列に keeper が居なければ MAIN から job、job は自分の session で nohup)。転送の copy の上限を 1 本 20 分に(2 本で 45 分の枠に収まる)。
- 12:2x 監督の返事: (1) test の 64 → 68 は branch で commit(同じ理由の 1 行の comment)、merge は r15 → r16 の順で監督、(2) P の名前は P 側の変更が要る = `K/p-mlx-row-name.patch` を用意(当てるのは監督)、(3) go は 0.6B smoke の後の 1 通、それまで enqueue しない。
- 12:21 test を直して 13 tests OK。次 = commit、P の patch。
- 12:21:35 commit(test、driver、経過)。12:22–12:24 P の名前の patch の下見(P の HEAD 1f45083 を scratchpad に git archive)。途中で ROUND16 の render の抜粋に runtime を並べた数字が入っていたのに気づき、12:24 に履歴を書き換えた(「commit」節)。
- 12:2x 監督の go: 0.6B smoke は済み、18 Pro は空き。転送は今から、job は cells file が main に入ってから(test の commit が入ったら「commit 済み」の 1 通、監督が merge して返す)。12:25 driver を push / job の 2 部に分けた。次 = commit、「commit 済み」、push を起動。
- 12:25:30 commit d9613c0a、監督へ「commit 済み」。12:26:06 転送 1 回目: hold を取得(keeper pid 51951、待ち 0 s、18 Pro は空き、`.iphone_hold` は 17 Pro の AA lane が 12:23:30 から持つ = 別の phone)、端末は接続・unlock。12:26:09 最初の copy で FAIL(devicectl が snapshot の symlink を link のまま送り「File paths cannot contain '..'」、罠の節)、端末側は変化なし、hold は即 release。直し = file ごとに Mac の blob を送り先の名前で送る。1 回目の listing で、端末の OptiQ E2B は 6bf302fd の 11 file とも blob が Mac と同じ size。
- 12:29 merge 6378a790(監督: test の twins は私の 4 対 + 監督の iOS 0.6B cpu 対 = 69、監督が解決)。2 回目を quiet_hold で r17 の Mac の窓(12:26:51 から)の後ろに置き、監督へ判断を 2 点(r17 の窓の中で転送するか、job の check_holds が共有 `.iphone_hold` を device 欄を見ずに busy と読む件)。
- 12:3x 監督: 転送は r17 の窓の中で走らせてよい(build と runs=1 の smoke、page の数字ではない)。12:31 quiet_hold の待ちを止め、**r17 の窓の中で転送**(2 回目): 12:31:41 hold 取得(keeper pid 83796、待ち 0 s)、E2B の model.safetensors 3.55 GB は 12:31:44–12:33:40。次 = E4B 5.15 GB、size の照合、release、job。
- 12:3x 監督: check_holds は main 1940f4a8 で別 device を名指す hold を読み飛ばす = job を起動してよい(転送の後、keeper から `--hold-held-by` か release してから)。
- 12:22–12:35 P の名前の patch(下の節)。r17 が 12:35:09 から P の render_check の窓を持つので、AA の比較と render_check は窓の後。
- 12:36:30 転送 2 回目が完了: 2 bundle とも 16 file が端末で Mac と同じ size、refs/main 40 bytes(「転送の結果」)、hold を返した(枠 4 分 49 秒)。
- 12:36:48 MAIN から job を起動(driver の job 部、自分の session で nohup)→ 12:36:49 `BUSY: bench_matrix_iphone.sh is running` exit 3(停止条件の 2 回のうち 1 回目)。走っていたのは 17 Pro の AA lane の runner(keeper_ios.sh measure i5 45、pid 83996、12:31:42 から → bench matrix anchors.cells → bench_matrix_iphone.sh pid 84481)。preflight の pgrep は host 全体を見る。12:37 監督へ判断を 1 通(待つか、runner の判定を device ごとにするか)。次 = 指示を待つ、job は起動しない。
- 12:3x 監督: (1) runner の判定は device ごとにする(監督が直す、2 回目の起動は次の 1 通の後)、(2) P の名前の v1 は group を割って MLX を比べる相手から外す = 目的に反する → group の鍵はそのまま、級は棒 / artifact の label だけに(できなければ名前の patch は無し)。
- 12:40–12:44 Mac の窓が空いた間に P の v2 を作って確かめた(「P の名前の patch」): patch なし / v2 とも P の 4 つの check が PASS(render_check は自分の窓 r16-p-render-check で 52–55 s ずつ 3 回: なし PASS、v2 は 11 FAIL → render_check の名前の規則を直して PASS)。
- 12:4x 監督: main 8fe22207 で runner の判定は device ごと = 2 回目の起動の許可。12:45:12 job 起動(log は追記、`--- attempt 2` の行のあと): 17 Pro の runner と `.iphone_hold` は「別の phone」と読まれ、preflight ok、hold 取得、anchor の phase。Monitor(cell の始まり、load、判定、失敗、終了の行)。12:47 P の patch を v2 で上書き、`git -C P apply --check` OK。次 = commit、監督へ v2 の 1 通、sitting の終わりを待つ。

## 下見(11:53–12:00)

- `date` 11:52:30 JST、HEAD 80a36462(main は f9f3dced = +3 commit、どれもこの round の file に触れない)。
- 行番号(launch の通り): `matrices/dashboard-text-v1.cells` l.144 / 148(ios e2b short-chat / 1K)、l.166 / 170(ios e4b、exclude=app-killed-at-model-load-sigkill)、l.231 / 237(mac e2b)、l.257 / 263(mac e4b); `matrices/dashboard-longctx1024-v1.cells` l.35 / 45(mac)、l.68 / 74(ios、e4b は exclude)。`scripts/bench_common.py` l.40 OptiQ e2b、l.46 / 47 generic。
- 行の名前の付け方(bench): `render_dashboard.model_row` は LOGICAL_MODELS の名前から括弧を外す。`load_cells` は 1 つの arm の 2 artifact が同じ model 行に来るとき、両方に括弧つきの名前を戻す(CQ4 の前例)。= PTQ 行を足すと bench の表では MLX の 2 行が "(QAT OptiQ)" / "(PTQ 4bit)" の名前で出て、LiteRT-LM と llama.cpp は "Gemma 4 E2B" / "Gemma 4 E4B" の行に残る。
- P(`~/code/litert-bench-dashboard`、読むだけ)の cell の key: build.py `load_cell_defs` = (platform, arm, model_id, task, ctx, file)、check の key = (device, arm, model_id, task)。model_id で分かれる = PTQ 行は別 cell。P は text-v1 を short-chat だけ、longctx1024 を 1K だけ読む(CELL_FILES)。`dist/cells.json` の MLX Gemma 4 cell(今): 例 `iPhone19,2 mlx-swift "Gemma 4 E2B" mlx-community/gemma-4-e2b-it-qat-OptiQ-4bit long-context-1024-gen256 ctx '2523' GPU measured 52.20 (2026-10-19-dashboard-v1-iphone18pro-ios)`、E4B OptiQ は iPhone で excluded、Mac の 1K は text-fail。`meta.planned_runtimes` = [](MLX は計測済みの runtime、変更なし)。
- P の行の名前: `make_cell` は `"model": model_row(d["model_id"])`(build.py l.565)= 括弧が外れる。PTQ の cell も page では "Gemma 4 E2B" / "Gemma 4 E4B" の group に入り、QAT / PTQ は artifact(model id、hover と inspector)でしか分からない(下の「P の build」で確認)。
- catalog: `ios/BenchmarkApp/Sources/Models/ModelCatalog.swift`(MAIN と SIDE は cmp で一致): l.178 `gemma-4-e2b-it-4bit`("Gemma 4 E2B (PTQ 4-bit)"、"INT4 (PTQ)")、l.190 OptiQ e2b、l.208 `gemma-4-e4b-it-4bit`("Gemma 4 E4B (4-bit)"、"Q4")、l.220 OptiQ e4b。l.174–176 の comment は「PTQ を cross-runtime table に使わない」= この決定より前の文(提案 3)。
- app の MLX の読み先: SIDE の `MLXBridges.swift` → `HubClient.default.downloadSnapshot(of:revision: "main", matching:)`、patterns = mlx-swift-lm 60bd0d7 の `["*.safetensors", "*.json", "*.jinja"]`。swift-huggingface b7219594 の `downloadFile` は最初に `HubCache.cachedFilePath`(refs/main → `snapshots/<rev>/<file>` の有無、symlink でも通常 file でも可)を見て、あれば network に出ない。`listFiles(main)` だけは online で呼ぶ(落ちれば refs/main の snapshot に戻る)。= refs/main と snapshot dir を送れば download しない。
- 18 Pro の app は OptiQ E2B を持つ(host 側の証拠): 10-19 の週次の console(`results/raw/2026-10-19-dashboard-v1-iphone18pro-ios/console_mlx-swift_…OptiQ-4bit_short-chat.txt`、04:13)が `[HubBridge] downloaded to …/Library/Caches/huggingface/hub/models--mlx-community--gemma-4-e2b-it-qat-OptiQ-4bit/snapshots/6bf302fd…`、`load complete in 2.79s`。端末の `device info files` は転送の hold の中で取る(端末は 12:14 まで llama.cpp の retake で同じ app を測っていた)。
- Mac の HF cache: 4bit e2b refs/main 23876752…(snapshot 8 file)、4bit e4b 475b9088…(8 file)、OptiQ e2b 6bf302fd…(11 file)。

## cells の diff

`matrices/dashboard-text-v1.cells`(+19 / −4): header l.46–48(決定、日付、戻し方)、iPhone 節の comment l.109–111 と E4B の comment l.169–170 を決定に合わせた。PTQ 行(新しい行番号):

| platform | model | short-chat | long-context-1024-gen256 |
|---|---|---|---|
| ios | E2B | l.148(OptiQ l.147 の直後) | l.153(OptiQ l.152 の直後) |
| ios | E4B | l.172(OptiQ l.171、exclude のまま) | l.177(OptiQ l.176、exclude のまま) |
| mac | E2B | l.239(l.238 の直後) | l.246(l.245 の直後) |
| mac | E4B | l.267(l.266 の直後) | l.274(l.273 の直後) |

`matrices/dashboard-longctx1024-v1.cells`(+7): header l.19–21、PTQ 行 l.39(mac e2b)、l.50(mac e4b)、l.74(ios e2b)、l.81(ios e4b、exclude なし)。option は全部 OptiQ 行と同じ `cooldown=300`(iOS E4B だけ OptiQ 行の exclude= を付けない)。anchors は触らない。

`matrices/mlx-gemma4-file-ios.cells`(新規): anchor 行(text-v1 l.128 = `dashboard-llama-b11721-ios.cells` の最初の行と byte で同じ)、1K の OptiQ e2b / 4bit e2b / 4bit e4b、short-chat の同じ 3 本。7 行とも text-v1 の行と byte で同じ(grep -xF で確認)。

validate: `validate_cells.py matrices/dashboard-text-v1.cells matrices/dashboard-longctx1024-v1.cells` OK / OK、`--require-anchor matrices/mlx-gemma4-file-ios.cells` OK、`matrices/*.cells` 147 file OK。

## 名前の確認(render の出力)

`scripts/bench_common.py` LOGICAL_MODELS(l.41–46、generic の前): `("gemma-4-e2b-it-4bit", "Gemma 4 E2B (PTQ 4bit)")`、`("gemma-4-e4b-it-qat-optiq", "Gemma 4 E4B (QAT OptiQ)")`、`("gemma-4-e4b-it-4bit", "Gemma 4 E4B (PTQ 4bit)")`。summary の model id で新しい pattern に当たるのは `mlx-community/gemma-4-e2b-it-4bit`(4 行)、`…e4b-it-4bit`(4 行)、`…e4b-it-qat-OptiQ-4bit`(52 行)だけ。build_summary は LOGICAL_MODELS を使わない(import は atomic_write と corrected_engine だけ)= summary は変わらない。

`render_dashboard.py --check`: `rendered 311 device-cells from 146 file cells` exit 0。text-v1 を scratchpad に render した grid の行の名前と MLX の欄(抜粋。数字は # に置き換えた: この repo の text は runtime を並べた数字を載せない):

```
Mac Studio (M4 Max) short-chat:
| **Gemma 4 E2B** | LiteRT-LM、llama.cpp ほかの cell | mlx-swift: · |
| **Gemma 4 E2B (QAT OptiQ)** | mlx-swift: # |
| **Gemma 4 E2B (PTQ 4bit)** | mlx-swift: not yet measured |
| **Gemma 4 E4B (QAT OptiQ)** | mlx-swift: # |
| **Gemma 4 E4B (PTQ 4bit)** | mlx-swift: not yet measured |
Mac Studio (M4 Max) long-context-1024-gen256:
| **Gemma 4 E2B (QAT OptiQ)** | mlx-swift: # |
| **Gemma 4 E2B (PTQ 4bit)** | mlx-swift: #(r14 の手の sitting) |
| **Gemma 4 E4B (QAT OptiQ)** | mlx-swift: — (text check failed: reply-off-task (4 of 4 runs)) |
| **Gemma 4 E4B (PTQ 4bit)** | mlx-swift: #(r14 の手の sitting) |
iPhone 18 Pro long-context-1024-gen256:
| **Gemma 4 E2B (QAT OptiQ)** | mlx-swift: # |
| **Gemma 4 E2B (PTQ 4bit)** | mlx-swift: not yet measured |
| **Gemma 4 E4B (QAT OptiQ)** | mlx-swift: — (app-killed-at-model-load-sigkill) |
| **Gemma 4 E4B (PTQ 4bit)** | mlx-swift: not yet measured |
```

(Mac の 1K の PTQ は r14 の手の sitting の record = bench の表は全 session を読む。PTQ 行の bw は n/a: `models/artifact-bytes.json` に 4bit の entry が無い = 提案 4。)longctx1024 の render も同じ名前。`render_leaderboard.generate()`(LEADERBOARD.md は書かずに呼んだ): 586 行、E4B OptiQ が `Gemma 4 E4B (QAT OptiQ)` の見出しに分かれた(E2B OptiQ はもとから分かれている)。`test_render_rules.py` 17 tests OK、`test_import_native_benchmark.py` OK。

## CI の下稽古(`.github/workflows/data-pipeline.yml` の手順、nice -n 19)

- OK: validate(全部と --require-anchor)、render_dashboard --check、test_render_rules、test_import_native_benchmark、session_check_selftest、dashboard_job_selftest、regression_watch_selftest、dashboard_post_selftest、autopilot_selftest(58 checks; CI と同じく pin の Android binary の dir を `BENCH_ANDROID_BIN_DIR` に渡して。渡さないと 12 FAIL = 環境)、android/bench/selftest.py、android/ddp/selftest.py(76 checks)、py_compile 全部。summary-fresh は raw も build_summary も変えていないので対象外。
- FAIL(直した): `android/bench/test_longctx1024.py` `test_every_short_chat_row_has_one_1024_twin` — `AssertionError: 68 != 64`(l.143、1K の対の数を手で書いた assert)。HEAD は 64(iPhone と Mac の MLX が 15 → 17)、それより前の assert(対が 1 本ずつ、option が同じ)は通っている。launch の書く範囲の外なので最初は patch にした(最初の commit の `K/tools/test_longctx1024-ptq-rows.patch`)。監督の指示(12:2x「branch で commit、同じ理由の 1 行の comment つき」; r15 も同じ file の別の行を直したので merge は r15 → r16 の順、監督が行う)で 64 → 68 と comment 1 行を branch に commit し、patch file は消した。この tree で 13 tests OK。

## P の build(私の branch に向けて、scratchpad に。P には書かない)

`EDGE_LLM_BENCH=<this worktree> build.py --out-dir <scratchpad>` exit 0、`tools/check_against_bench_dashboard.py --dist <scratchpad>` = **PASS**: `weekly table: 272 cells equal …, 5 differ because the bench session is not a weekly sitting, 0 unexplained`(5 = Mac の r14 の手の sitting の 4 cell と anchor 1。page は週次の sitting だけ読む)、ladders 71 equal、protocol 54 equal / 86 no-entry / 6 excluded、0 unexplained。

cells.json: 550 → 568(+18、削除 0)= 3 device(iPhone 17 Pro、18 Pro、Mac)× 2 model × 3 task(short-chat、1K、protocol の "no forced-prefill entry")。新しい cell の "model" は全部 `'Gemma 4 E2B'` / `'Gemma 4 E4B'`(model_row)= page の名前には QAT / PTQ が出ない。P の panel の文(`summary_sentence`)は model の group の中の「LiteRT-LM 以外で最も速い cell」と比べる = PTQ の cell が測られると比べる相手の候補に入る(P の code の読み、数字ではない)。

## P の名前の patch(`K/p-mlx-row-name.patch`、当てるのは監督)

監督の指示: (12:2x)code-2d の決定は「行の名前に QAT / PTQ」= P 側の変更が要る。(12:4x)group を割って MLX が Gemma 4 の比べる相手から外れるのは code-2d の目的(PTQ の速さを隠さない = 比べる相手に入る)に反する = group の鍵(model_row)はそのまま、QAT / PTQ の語は棒 / artifact の label だけに。

- 今の版(v2、137 行の diff、build.py + tools/check_aa.py + tools/render_check.py): `git -C ~/code/litert-bench-dashboard apply --check K/p-mlx-row-name.patch` = OK(P の HEAD c06e5a4。1f45083 からの commit は dist だけ = code は同じ)。P には書いていない(写しは `git archive` で scratchpad に)。
  - build.py: `mlx_class(model_id)`(`mlx-community/gemma-4-` の id で `qat-optiq` → "QAT OptiQ"、`-it-4bit` → "PTQ 4bit"、bench の LOGICAL_MODELS の語)を cell の新しい欄 `build` に入れる(cells.json; cells.csv の列は変えない)。`model` は model_row のまま = group は今と同じ。JS の `cellName(c)` = runtime + 級 + " · " + backend("MLX PTQ 4bit · GPU")= tooltip、aria-label、表、inspector、「(compared)」の名前。panel の箱の「Largest gap … vs」にも級(summary_parts.largest.build)。AA の表は MLX の protocol の行の recipe 欄に級を入れる(patch なしだと、同じ「excluded: no forced-prefill entry」の行が MLX の Gemma 4 で 2 本ずつ重なる)。
  - tools/check_aa.py: AA の行の recipe に同じ級(build と同じ規則)。tools/render_check.py: cell の名前を page の cellName と同じ規則で組む `cell_name(c)`(aria-label、At a glance の行、箱の Largest gap、bar の名前の 4 か所)。
- 確かめ(P の写しをこの worktree = PTQ 行と名前の入った bench に向けて build): patch なし / v2 とも check_against_bench_dashboard、check_regression、check_aa、render_check が PASS(render_check は自分の Mac の窓で 55 s)。v2 の render_check は、render_check の名前の規則を直す前は 11 件 FAIL(aria-label と At a glance の名前が「MLX · GPU」のままの期待)= その 4 か所を直して PASS。
- 効き目(patch なし → v2、数字は書かない): MLX の Gemma 4 の 36 cell は `model` が "Gemma 4 E2B" / "Gemma 4 E4B" のまま、`build` が QAT OptiQ / PTQ 4bit(9 cell ずつ)。Apple の panel の group は 5 のまま(Gemma 4 E2B の group の棒: … LiteRT-LM · GPU、llama.cpp · GPU、MLX PTQ 4bit · GPU、MLX QAT OptiQ · GPU …)。panel の文は patch なしと同一(0 本変わる)= PTQ の cell も比べる相手の候補のまま。summary_parts は largest に build の欄が増えた 18 か所だけ。AA の行は 638(patch なしも同じ数、v2 は MLX の 8 行を級で見分ける)。
- 前の版(v1、12:3x): model の名前そのものに級を足した形 = Apple の panel の group が 5 → 9 に割れ、Gemma 4 の group での LiteRT-LM の比べる相手から MLX が外れた(panel の文が 12 本変わる)。監督の判断(目的に反する)で v2 に置き換えた。

## docs の要点(`docs/dashboard-cells-v1.md`)

- 節「MLX Gemma 4 file (2026-10-19)」の Rule: PTQ の文を「A PTQ build is the page's second MLX row, not a candidate for this one: its class is in the row's name」に書き換え、元の文を 1 行残した("(Until 2026-10-19 11:4x the rule read: …)")。Decision の段落の「the rule keeps them off the page」も同じ向きに直し、元の語を括弧で残した。
- 小節「2 rows from 2026-10-19 (owner decision via code-2d)」: 決定、理由 3 つ(llama.cpp も PTQ の unsloth Q4_K_M、30 日 DL は PTQ が 24,394 / 31,114 で OptiQ の 956 / 2,475 の約 25 / 13 倍、MLX で一番落とされている build の速さを page から外さない)、行(2 file、同じ option、iPhone E4B PTQ は exclude なし)、名前 4 つと bench の表での出方、戻し方(PTQ 行を外す、名前は残してよい)、今の数字(Mac は r14 の表、page は週次だけ読むので次の Mac 週次まで not measured)、18 Pro の sitting の cells と campaign 名、bundle の転送先。
- Open question 6(iPhone MLX E4B)に「2026-10-19: both」の 1 行。
- `methodology/fairness-rules.md`: PTQ / QAT / OptiQ の文が無い = 触らない。

## 転送 script の dry run

`K/tools/push_mlx_4bit_18pro.sh --dry-run`(端末に触れない。Hub API だけ読む)、12:14:16、exit 0:

```
OK   gemma-4-e2b-it-4bit 238767527555cb75a05732a84dff5d6ba0dd6809: Hub main = cache refs/main; 8 files match *.safetensors *.json *.jinja, 3,583,086,498 bytes, every one at the Hub's size
OK   gemma-4-e4b-it-4bit 475b9088d29754a3379866cf5aeb6b41acd313c2: Hub main = cache refs/main; 8 files match *.safetensors *.json *.jinja, 5,179,239,349 bytes, every one at the Hub's size
plan (devicectl copy to, device 00008160-000038CA02C00036, app com.example.CoreMLLLMChat; snapshot dir first, then refs/main):
  ~/.cache/huggingface/hub/models--mlx-community--gemma-4-e2b-it-4bit/snapshots/238767527555cb75a05732a84dff5d6ba0dd6809/
    -> Library/Caches/huggingface/hub/models--mlx-community--gemma-4-e2b-it-4bit/snapshots/238767527555cb75a05732a84dff5d6ba0dd6809/
       chat_template.jinja 17336 / config.json 6395 / generation_config.json 208 / model.safetensors 3550670554 /
       model.safetensors.index.json 218323 / processor_config.json 1316 / tokenizer.json 32169626 / tokenizer_config.json 2740
  ~/.cache/huggingface/hub/models--mlx-community--gemma-4-e2b-it-4bit/refs/main (238767527555cb75a05732a84dff5d6ba0dd6809)
    -> Library/Caches/huggingface/hub/models--mlx-community--gemma-4-e2b-it-4bit/refs/main
  ~/.cache/huggingface/hub/models--mlx-community--gemma-4-e4b-it-4bit/snapshots/475b9088d29754a3379866cf5aeb6b41acd313c2/
    -> Library/Caches/huggingface/hub/models--mlx-community--gemma-4-e4b-it-4bit/snapshots/475b9088d29754a3379866cf5aeb6b41acd313c2/
       chat_template.jinja 17336 / config.json 6628 / generation_config.json 208 / model.safetensors 5146800534 /
       model.safetensors.index.json 240961 / processor_config.json 1316 / tokenizer.json 32169626 / tokenizer_config.json 2740
  ~/.cache/huggingface/hub/models--mlx-community--gemma-4-e4b-it-4bit/refs/main (475b9088d29754a3379866cf5aeb6b41acd313c2)
    -> Library/Caches/huggingface/hub/models--mlx-community--gemma-4-e4b-it-4bit/refs/main
  listed only: Library/Caches/huggingface/hub/models--mlx-community--gemma-4-e2b-it-qat-OptiQ-4bit/
dry run: no device call made
```

本番(`--keeper <pid>`)の手順: keeper の pid が hold を持つことを確かめる → 接続と unlock → app の hub dir を一覧(OptiQ e2b の snapshot を Mac の同じ revision と file ごとに比べる)→ snapshot dir、refs/main の順に copy(1 回 30 分まで)→ もう一度一覧して 16 file の size を Mac と比べる。端末側の比較は、devicectl の JSON の形(監督の 03:2x の listing と同じ形)で作った合成の listing で OK / FAIL の両方を確かめた(1 byte 短い file を FAIL にする)。

取り方(go の後): `sleep 2700 &`(keeper、45 分で切れる)→ `queue_cli.py enqueue <hold> r16-push-mlx-4bit edge-llm-bench-55 45` → `queue_cli.py wait <hold> r16-push-mlx-4bit <keeper>`(run_in_background)→ script → `hold_cli.py release <hold> <keeper>` → 待ち行列に keeper が居なければすぐに MAIN から job 経路。

## 転送の結果(手順 8 の前半)

- 1 回目 12:26:06–12:26:09: hold 取得(keeper pid 51951)→ 接続・unlock OK → 最初の `devicectl device copy to`(snapshot dir)が `ERROR: The specified file could not be transferred. (com.apple.dt.CoreDeviceError error 7000) … File paths cannot contain '..'. (com.apple.dt.remoteservices.error error 11007) NSFilePath = ../../blobs/038e39a3…` → FAIL、hold を返した。2 回目の前の listing で 4bit の 2 repo は「refs/main absent; no snapshot」= 1 回目は何も残していない。
- 2 回目 12:31:41–12:36:30(r17 の Mac の窓の中、監督の許可): hold 取得(keeper pid 83796、待ち 0 s)→ file ごとに Mac の blob を送り先の名前で copy(16 file + refs/main 2 本)→ 一覧を取り直して照合:
  ```
  before: models--mlx-community--gemma-4-e2b-it-qat-OptiQ-4bit snapshots/6bf302fd…: 11 entries; the Mac's snapshot of 6bf302fd: 11 files, each one there, its blob (or file) at the Mac's size
          (古い snapshot c6c65725 も残っている: 9 entries、vision の file だけ無い。refs/main は 40 bytes = 週次の console が 6bf302fd から load)
          models--mlx-community--gemma-4-e2b-it-4bit / gemma-4-e4b-it-4bit: refs/main absent; no snapshot
  copy:   e2b model.safetensors 3,550,670,554 bytes 12:31:44–12:33:38(114 s、約 31 MB/s)、e4b model.safetensors 5,146,800,534 bytes 12:33:41–12:36:27(166 s、約 31 MB/s)、残りは 1 本 1 s 前後
  after:  OK   models--mlx-community--gemma-4-e2b-it-4bit snapshots/238767527555cb75a05732a84dff5d6ba0dd6809: 8 files at the Mac's sizes (3,583,086,498 bytes); refs/main 40 bytes
          OK   models--mlx-community--gemma-4-e4b-it-4bit snapshots/475b9088d29754a3379866cf5aeb6b41acd313c2: 8 files at the Mac's sizes (5,179,239,349 bytes); refs/main 40 bytes
  ```
  hold を返した(枠 4 分 49 秒)。app が download せずに読むかは sitting の最初の 4bit の cell の console(`[HubBridge] downloaded to …` までの時間と `[MLX] load complete in …`)で見る。

## 計測の表

(go の後に書く)

## commit

- 7b95e363(branch `mlx-ptq-rows`、push / merge なし、帰属行なし): cells 3 本、bench_common.py、docs、ROUND16、K/tools の転送 script と test の patch。明示 path で stage、`git diff --cached --name-only` は 8 file だけ。
- 2dae1311、27f86ff2: ROUND16 の hash と経過の行。702f7d1d: test の 64 → 68(comment 1 行)、patch file の削除、手順 8 の driver、転送 script の copy の上限。
- 12:24 履歴を書き換えた(私の branch だけ、main にも remote にも入る前): 最初の版の ROUND16 の render の抜粋に、LiteRT-LM と llama.cpp の数字が並ぶ行があった(この repo の text は runtime を並べた数字を載せない)。抜粋を名前と MLX の欄だけ(数字は #)に直して `commit --fixup` + `rebase --autosquash 80a36462` で最初の commit に畳んだ = 旧 a71f1b5a / ca5321c9 / 18bfe2f1 / 737036de → 7b95e363 / 2dae1311 / 27f86ff2 / 702f7d1d(2 本目と 3 本目の commit message の旧 hash はそのまま)。`git log -p 80a36462..HEAD` に旧抜粋の数字は 0 件。`git merge-tree --write-tree main mlx-ptq-rows` は衝突なし(main は r15 の merge 済み)。

## 提案

1. P の page の名前: P は `model_row` で cell に名前を付ける(build.py l.565)ので、PTQ と OptiQ は page ではどちらも "Gemma 4 E2B" の group の MLX の cell になる。名前に QAT / PTQ を出すなら P 側で bench の `load_cells` の `c["model"]`(衝突のときだけ括弧つき)を使う形。P の panel の文は group の中の最速の他 runtime と比べるので、PTQ の cell が入ると比べる相手が変わりうる(P の判断)。
2. `android/bench/test_longctx1024.py` l.143 の 64 → 68(patch は K/tools)。merge の前に当てないと data-pipeline の android-driver-selftest が赤。
3. `ModelCatalog.swift` l.174–176 の comment(PTQ を cross-runtime table に使わない)が決定と食い違う。catalog に触れる round で 1 行直す(build は不要、comment だけ)。`docs/dashboard-recurring-job-v1.md` l.709–711(iPhone MLX E4B は PTQ を選ぶまで exclude)も同じ向きに 1 行。
4. `models/artifact-bytes.json` に 4bit の 2 bundle の entry を足すと PTQ 行の bw の欄が出る(`scripts/artifact_streamed_bytes.py`)。
5. 週次の Apple の sitting は 4 cell 増える(cooldown だけで 20 分)。`ops/dashboard-v1/schedule.json` の expected_hours(Mac 3.8、iPhone 18 Pro 5.8)は次の週次の実測で見直す。
