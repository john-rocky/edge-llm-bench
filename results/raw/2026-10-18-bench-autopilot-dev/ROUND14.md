# ROUND14 — MLX Gemma 4 file fairness (OptiQ-4bit vs 4bit vs qat-mobile, Mac) — worker edge-llm-bench-wt-autopilot-q06-10 [ef4fd0] (Opus 5.5), started 2026-10-19 10:22 JST

Supervisor: edge-llm-bench-55 [4f120b]. Worktree `~/code/edge-llm-bench-wt-autopilot-q06`, branch `mlx-gemma4-file` (from 13af3b4e; main is 9ecb354c = +1 backlog post).

## 経過
- 10:22 ListAgents (this session = edge-llm-bench-wt-autopilot-q06-10 [ef4fd0]); HEAD 13af3b4e, tree clean. r13 (edge-llm-bench-wt-autopilot-tmpl-b1 [24da3a], worktree -tmpl, branch llama-chat-template) started 10:17; its ROUND13.md has no build yet.
- 10:23–10:30 下見: Hub API / card / config / commits の 6 bundle、HF cache、mlx-swift-lm 60bd0d7 の load 経路(BaseConfiguration は `quantization` だけを読む、loadWeights は verify .all)。4 bundle の download を開始(hf download、yardstick と同じ patterns *.safetensors *.json *.jinja)。
- 10:31 qat-mobile E2B の load probe(quiet_hold 2 s、`.build/dd-mac` yardstick = mlx-swift-lm 60bd0d7): loadFailed "Unhandled keys [input_activation_scale, output_activation_scale, weight_scale] … per_layer_projection" = 停止条件(形式)。監督へ 1 通。
- 10:32 qat-mobile E4B の load probe: loadFailed "Mismatched parameter language_model.lm_head.weight … Actual [262144, 640], expected [262144, 2560]"。10:33 監督へ停止条件の 1 通(判断 2 点: qat-mobile 行の扱い、級に PTQ 4bit を含めるか)。次 = download の残り(4bit E4B)、cells の下書きと validate、監督の返事待ち。
- 10:3x 監督の判断(10:3x 受信): (a) qat-mobile 2 行は exclude=、load 失敗の出力 2 本は campaign dir の NOTES-qat-mobile-load.txt、(b) 級 = QAT、PTQ 4bit は測って表に載せ page には使わない = page は OptiQ 据え置き。10:33:51 download 4 本済(sha256 は Hub の lfs.sha256 と 9 file 一致)。cells `matrices/mlx-gemma4-file-mac.cells` 作成、validate PASS(--require-anchor、--catalog = `.build/dd-mac` の yardstick list --json)。次 = 監督へ「Mac 側 PASS、端末待ち」。
- 10:4x 監督の go(YS = `.build/dd-mac`、runner だけ、CAMPAIGN=2026-10-19-mlx-gemma4-file-mac)。go の時点で GPU lock は r13 の yardstick build(`r13-yardstick-tmpl-build timing pid 28192 since 10:39:00`、xcodebuild + swift-frontend 2 本 100 %、load 16)= 私の quiet_hold は flock で build の窓の終わりを待ってから計測に入る形で 10:41 に起動(build と計測は重ならない)。NOTES-qat-mobile-load.txt と host_load.log(30 s ごと)を窓の中で campaign dir に置く。
- 10:41:10 窓を取得(wait 0 s: r13 の build の窓は 10:41 より前に閉じていた、xcodebuild なし)。sitting 開始時の host: StorageManagementService 約 80 % CPU(06:05 から 4 h 36 min 生存 = page の 10-19 rebuilt sitting 06:10–09:55 の間もいた)、ApplicationsStorageExtension 約 90 %、Chrome renderer 65 %、load 9.1; thermal は記録なし(pmset)。止めずに host_load.log(30 s ごと)に残す。
- 10:41–10:49 anchor(Qwen3 0.6B 4bit short-chat runs 3): 1 回目 warm 497.66 / 527.58 = SPREAD 5.8 → quarantine(.attempt1)、180 s 後の再実行 warm 450.80 / 553.34 = SPREAD 20.4 → GATE_FAIL(retry kept、FLAGGED.txt)。page の anchor(rebuilt 06:10)は warm 533.91 / 555.78 と 549.45 / 555.74。
- 10:49–10:50 E2B OptiQ 1K: cold 150.06、warm 151.02 / 150.92 / 151.03(spread 0.07 %)、prefill warm 7119 / 7129 / 7034、peak during decode 5246 MB、rev 6bf302fd、prompt 1107。page(rebuilt)は warm 150.64 = +0.25 %。次 = E2B 4bit(10:54 頃)。
- 10:54–10:55 E2B 4bit(PTQ)1K: cold 178.70、warm 178.68 / 178.80 / 178.47、prefill warm 7125 / 7085 / 7168、peak during decode 3654 MB、rev 23876752、prompt 1107(OptiQ と同じ)、label "INT4 (PTQ)"。返事は 4 回とも "The provided text is placeholder "Lorem Ipsum" text and does not contain any spe…" = lorem を断る(OptiQ E2B は課題に答える)。OptiQ の text weights は cache の 3 snapshot で同じ blob(E2B fd6e9b68…、E4B 1f36fca9… / c9e780e2…)= 10-18 の改版は vision sidecar の移動だけ。次 = E4B 4bit(11:00 頃)。
- 10:59–11:03 E4B 4bit 1K: 1 回目の launch は run 4 が 92.27(他は 112.16 / 112.14、prefill は無傷)= SPREAD 17.7 → 隔離(.attempt1)、180 s 後の再実行が行: cold 112.17、warm 111.97 / 112.05 / 111.79、label "Q4"、返事は lorem を断る。
- 11:08 E4B OptiQ 1K: 4 run とも返事は lorem を断る(text-fail、下の表)= rate は記録に残るが数字としては使わない。11:08:18 SITTING-END rc 0、窓の解放 1628 s。
- 11:1x 集計: session_check は HOLD(not-job = 手で走らせた dir、user-name = 私の host_load.log の account 名 → USER に置換)、text_screen.json は書かれない(screen は job campaign だけ)= reply_rules を各 run に当てて判定(scratch tools/screen.py)。scratch の木(REPO の index + この dir)で build_summary → render_leaderboard.arm_row。MAIN の results/summary は 11:10:37 に別 session の in-tree 再生成(私の 19 行を含む)で変わっていた = 11:12 に `git checkout -- results/summary` で戻した。docs の節、cells の header を書いた。
- 11:22 commit 342e6b0e、全 cells の validate OK、round close の 5 節、lint。次 = ROUND14 の hash 追記の commit、監督へ round close の 1 通。

## 下見(10:23–10:40)
- 6 bundle(Hub API、card、config、commits、2026-10-19 10:23 JST に読んだ。DL = Hub API の `downloads` = 30 日):

| bundle (mlx-community/…) | Hub main | card / config の量子化 | 級 | safetensors bytes | DL 30 日 |
|---|---|---|---|---|---|
| gemma-4-e2b-it-qat-OptiQ-4bit | 6bf302fd(10-18 改版) | QAT base(gemma-4-E2B-it-qat-q4_0-unquantized)、mlx-optiq の per-layer 4 / 8 bit(8 bit 144、4 bit 132)、g64、5.24 bpw | QAT | 5,222,073,830(重み 4,270,441,092 + vision sidecar 951,632,738) | 956 |
| gemma-4-e4b-it-qat-OptiQ-4bit | a78078f4(10-18 改版) | QAT base、8 bit 221、4 bit 122、g64、5.17 bpw | QAT | 7,478,790,516 | 2,475 |
| gemma-4-e2b-it-4bit | 23876752 | google/gemma-4-E2B-it の mlx_vlm.convert、uniform 4 bit affine g64 | PTQ | 3,550,670,554 | 24,394 |
| gemma-4-e4b-it-4bit | 475b9088 | google/gemma-4-E4B-it の同じ変換 | PTQ | 5,146,800,534 | 31,114 |
| gemma-4-E2B-it-qat-mobile | 0548ff6d | card は frontmatter だけ(84 B)。config は `quantization_config` だけ: quant_method gemma、per-channel 2 / 4 / 8 bit(layer 15–34 の MLP は 2 bit = tensor の形で確認)、静的な input / output activation scale | QAT mobile schema(名前と形から) | 2,398,140,572 | 19,670 |
| gemma-4-E4B-it-qat-mobile | 65982052 | 同じ形式(MLP は全層 4 bit、lm_head と embedding は 2 bit) | 同上 | 3,455,955,670 | 15,219 |

- mlx-swift で読める形か: OptiQ と 4bit は config に `quantization`(group_size 64、bits 4、mode affine; OptiQ は per-layer の上書きつき)= 読める(OptiQ は page の行、4bit は catalog の既存 entry)。qat-mobile は `quantization` が無く、mlx-swift-lm 60bd0d7 の BaseConfiguration は `quantization` しか読まない → 実際に load して失敗(10:31 / 10:32、campaign dir の NOTES-qat-mobile-load.txt)。
- r13 の catalog: 10:18 時点で未変更。4bit × 2 は main の catalog に既にある(ModelCatalog.swift l.170 "INT4 (PTQ)"、l.200 "Q4")。qat-mobile は catalog に無い(CLI は catalog に無い HF id も合成して走る: Yardstick.swift resolveModel)。
- HF cache: OptiQ × 2 は 10-18 版で cache 済(02:00 の sitting が落とした)。4bit E2B は config.json だけ、4bit E4B と qat-mobile × 2 は無し → `hf download`(yardstick と同じ patterns)で 4 本 14.6 GB、10:29–10:33:51。cache の safetensors 9 本の sha256 を bytes から計算し、Hub の lfs.sha256 と全部一致。
- chat template: 4bit は 17,336 B(元の版)、OptiQ と qat-mobile は 18,569 B(Google canonical 2026-07-09)。どちらも thinking は既定で off(4bit: `enable_thinking is defined and enable_thinking`、OptiQ: `enable_thinking | default(false)`)。yardstick は enable_thinking を渡さない = 両方 thinking なし(budget-mode-rule)。prompt token は 4 bundle とも 1,107。

## cells
`matrices/mlx-gemma4-file-mac.cells`: Mac の session anchor 行(dashboard-text-v1.cells l.204)、1K × 4(text-v1 l.237 / l.263 と同じ option、cooldown=300 runs=4; 順は E2B OptiQ → 4bit、E4B 4bit → OptiQ の交互)、qat-mobile 2 行は `exclude=quant-method-gemma-mobile-schema-not-loadable-by-mlx-swift-lm-60bd0d7`。validate PASS(--require-anchor、--catalog = `.build/dd-mac` の yardstick list --json)。

## 計測の表
Mac Studio(M4 Max)、2026-10-19 10:41–11:08 JST、campaign `MAIN/results/raw/2026-10-19-mlx-gemma4-file-mac/`(未 commit、監督が stored report として commit)、yardstick `.build/dd-mac`(mlx-swift-lm 60bd0d78)。数字は render_leaderboard.arm_row(scratch の summary): warm = run 2〜4 の中央値、prefill と peak は 4 run の中央値(peak = memoryPeakDuringDecodeMB)。download を含む run は無い(4 bundle とも sitting の前に cache 済、blob の日付は全部 10:33:50 以前)。

| cell | 級 | warm decode tok/s(n、spread) | cold(run 1) | prefill tok/s | peak MB | text screen(reply_rules) | 保存された返事(冒頭 200 字) | record の label | Hub rev |
|---|---|---|---|---|---|---|---|---|---|
| E2B OptiQ | QAT | 151.02(3、0.07 %) | 150.06 | 7,076 | 5,246 | PASS 4 / 4 | 25 項目のリストを始める | INT4 (QAT, OptiQ) | 6bf302fd |
| E2B 4bit | PTQ | 178.68(3、0.18 %) | 178.70 | 7,105 | 3,653 | PASS 4 / 4 | lorem だと言って断る | INT4 (PTQ) | 23876752 |
| E2B qat-mobile | QAT mobile schema | load できない(NOTES) | | | | | | | 0548ff6d |
| E4B 4bit | PTQ | 111.97(3、0.23 %; 1 回目の launch は SPREAD 17.7 で隔離) | 112.17 | 2,283 | 5,403 | PASS 4 / 4 | 断る | Q4 | 475b9088 |
| E4B OptiQ | QAT | text-fail(数字なし) | — | — | — | FAIL 4 / 4(reply-off-task) | 断る | INT4 (QAT, OptiQ) | a78078f4 |
| E4B qat-mobile | QAT mobile schema | load できない(NOTES) | | | | | | | 65982052 |
| anchor Qwen3 0.6B 4bit short-chat | — | 502.07(2、20.4 % = GATE_FAIL) | 559.15 | 1,839 | 664 | PASS 3 / 3 | — | Q4 | 73e3e38d |

- page の OptiQ(参考、team page の cells.csv 10:22 build = 10-19 の Mac weekly rebuilt、同じ yardstick と同じ重み): E2B 1K warm 150.64(n 3、spread 0.34)、prefill 6,980、peak 5,243.78 → 今回 151.02(+0.25 %)。E4B 1K は text-fail 4 / 4 → 今回も同じ。比べるのは同じ sitting の中が本筋(上の表)。
- text の読み: prompt は lorem ipsum の 18 段落のあと「上の文章を文脈として 25 項目を挙げよ」。保存された返事(record は 200 字まで)では、課題に答え始めるのは E2B OptiQ だけで、他の 3 つは lorem を理由に断る。screen は字面の判定なので、4bit の 2 つは断りながら話題の語(device、cloud model、on-device AI)を含むので PASS、E4B OptiQ は含まないので FAIL。
- spread の 2 件(anchor の warm 450.80、E4B 4bit 1 回目の run 4 = 92.27)はどちらも 1 run だけ約 18 % 低く、prefill は無傷。host_load.log に StorageManagementService(1 core 前後、ずっと)、Chrome の renderer、WallpaperAerialsExtension。原因は未確認。gate が E4B 4bit を隔離して再実行し、再実行はきれい(0.23 %)。anchor は GATE_FAIL のまま(FLAGGED.txt)= この dir の session 間比較は anchor を通さない。

## 決定と規則
- 規則(監督 2026-10-19、docs/dashboard-cells-v1.md「MLX Gemma 4 file (2026-10-19)」): page の MLX Gemma 4 の file は QAT 級(page の比較相手 = LiteRT-LM の Gemma 4 bundle = wNa8o8 QAT と同じ級)。pin の mlx-swift-lm で load でき、1K の返事が text check を通る QAT bundle のうち、同じ sitting の warm decode(arm_row の中央値)が最速の物。5 % 以内の 2 つは 30 日 DL(Hub API `downloads`、sitting の日に読む)が多い方。PTQ は表に載せて候補にしない(catalog: E2B の GSM8K は PTQ 78 %、QAT 87 %)。load できない bundle は error つきで表に残す。
- 当てはめ: QAT で load できるのは OptiQ だけ(qat-mobile は load できない)→ E2B も E4B も OptiQ のまま = 測って据え置き。5 % と DL の段は使われない(候補 1 つ)。E2B は数字を持ち、E4B の 1K は text-fail の印のまま(model が lorem の塊を断る、engine の不具合ではない)。PTQ 4bit は測った(E2B 178.68、E4B 111.97、peak は E2B 3,653 / E4B 5,403 MB)が級が違うので page に使わない。
- cells の変更: なし(dashboard-*.cells の OptiQ 行はそのまま; `grep -n 'gemma-4-e[24]b-it-qat-OptiQ' matrices/dashboard-*.cells` の 12 行 = text-v1 8、longctx1024-v1 4)。docs に節を追加。

## commit
- 342e6b0e(branch `mlx-gemma4-file`、push / merge なし): cells file、docs の節、ROUND14、SPEED_LADDER。この hash の追記は次の 1 commit(ROUND14 だけ)。
- CI と同じ `scripts/validate_cells.py matrices/*.cells` = 146 file OK。round_close_lint PASS。speed_ladder_lint は `runtime:` 欄だけで FAIL(mlx-swift は lint の変換 runtime の一覧に無い、SPEED_LADDER の例外に記載)。

## 提案
1. この dir を commit する前に: session_check は手で走らせた dir に text screen をかけない → text_screen.json が無いまま summary に入ると text_check が空 = arm_row が E4B OptiQ の run を pool する(scratch で確認: text_checked_n 0、warm が数字になる)。page の cell は最新の session を取る(render_leaderboard.latest_session)ので、commit で E4B OptiQ 1K が text-fail から数字に変わりうる(team page の build.py の絞り込みは未確認)。案: session_check が hand run にも screen をかける、またはこの dir を session として page の経路から外す。
2. text screen の穴: lorem を断る返事でも話題の語を含めば PASS(E2B / E4B 4bit)。1K prompt の末尾を noref 型(long-context-2048-gen256-noref のように「上は filler」と書く)にするか、parsers.text_integrity に「placeholder / lorem … cannot」型の断りを足す。どちらも method の変更 = owner の判断。
3. mlx-swift-lm の pin bump(release-watch の drift 60bd0d78 → 378f2449)を別 round で: 新しい版が quant_method gemma を読めれば qat-mobile(LiteRT-LM の file と同じ schema の形)を同じ cells で測り、QAT 級の候補にする。まず 1 launch ずつ load の probe。
4. 18 Pro(13:00 の週次の後、別 round): cells は ios の anchor 行(`ios mlx-swift mlx-community/Qwen3-0.6B-4bit short-chat anchor=1 runs=3`)+ `ios mlx-swift mlx-community/gemma-4-e2b-it-qat-OptiQ-4bit long-context-1024-gen256 cooldown=300 runs=4`、同じ形の e2b-it-4bit、e4b-it-4bit、e4b-it-qat-OptiQ-4bit(text-v1 の iOS 行と同じく `exclude=app-killed-at-model-load-sigkill`)、qat-mobile 2 行は exclude=。Hub 改版の後の最初の launch は config.json 欠けで落ちる(罠の節)ので、app 側で先に 1 launch 落としてから測る。OptiQ を残す理由: QAT 級で load できる唯一の物(Mac と同じ)。

## 訂正
- launch「r13 が 4 entry(4bit × 2、qat-mobile × 2)を足した」→ 4bit × 2 は main の catalog に元からある(ios/BenchmarkApp/Sources/Models/ModelCatalog.swift l.170 "INT4 (PTQ)"、l.200 "Q4")。10:18 の時点で r13 の catalog は未変更(K の ROUND13.md、-tmpl worktree の diff は空)。CLI は catalog に無い HF id でも ModelInfo を合成して走る(apple/YardstickCLI/Sources/Yardstick.swift resolveModel)。
- launch「qat-mobile は同じ QAT mobile の系統に見える(未確認 = card を読む)」→ card は frontmatter だけ(84 B)で量子化の記述なし。config の quant_method gemma と tensor の形(per-channel weight_scale + 静的 activation scale)は mobile schema の形。mlx-swift-lm 60bd0d7 では load できない(MAIN の campaign dir の NOTES-qat-mobile-load.txt)。
- launch の規則案「4-bit 系の中の最速」→ 4bit は PTQ(card: google/gemma-4-E*B-it の mlx_vlm.convert)。catalog l.166–168 は PTQ を cross-runtime table に使わないと書く → 監督の判断で級 = QAT(10:3x)。
- launch「`./bench matrix … --campaign 2026-10-19-mlx-gemma4-file-mac`」→ bench は campaign 名に platform を足す(bench do_matrix: CAMPAIGN = f"{campaign}-{token}")= dir が …-mac-mac になる。runner を CAMPAIGN=2026-10-19-mlx-gemma4-file-mac で直に走らせた(監督の go)。
- launch「text screen = session_check.py <campaign dir> の sidecar」→ session_check は job campaign にしか screen をかけない(scripts/session_check.py check_job → screen_out。hand run は not-job だけ)。この dir に text_screen.json は無い。判定は reply_rules を各 run に当てて出した。
- launch の受け入れ基準 1「6 cell とも runs 4 の record」→ qat-mobile 2 行は監督の判断 (a) で exclude。record は無く、load 失敗の出力を NOTES に置いた。
- launch の YS = r13 の `.build/dd-mac-tmpl` → go の時点で未 build のため `.build/dd-mac`(監督の go)。
- 監督の go「GPU lock 空」→ 10:40 の lock は r13 の build(10:39:00 から)。10:41:10 より前に解放され、私の窓は待ち 0 s で取れた(sitting.log)。
- launch「計測の後に MAIN の summary を戻す」→ 私の run は summary を書いていない。11:10:37 に別 session の in-tree 再生成が私の 19 行を MAIN の working tree の summary に入れていた → 11:12 に戻した。

## 罠と袋小路
- `./bench matrix <cells> --campaign X` の dir は `X-<platform>`。…-mac という名にしたいなら `--campaign …`(-mac 抜き)で渡すか、`scripts/bench_matrix_mac.sh run <cells>` を CAMPAIGN=…-mac で走らせる(後者は summary も触らない)。
- `scripts/bench_matrix_mac.sh run --dry-run <cells>` は "unknown option"。flag は file の後: `run <cells> --dry-run`(MAIN に何も書かない)。
- quiet window が開いている間、PreToolUse hook は本文に python の語を含む Bash を止める(heredoc で .py を書くだけでも、自分の窓でも)。script は Write tool で書き、集計は窓が閉じてから。
- session_check は手で走らせた dir に text screen をかけない。返事の判定は session_check の reply_text / reply_rules を records に当てる(読むだけ。scratch の tools/screen.py)。
- OptiQ の 10-18 の Hub 改版の後、02:00 の sitting では bundle ごとの最初の launch が "[HubBridge] downloaded to …/snapshots/<新 sha>" の直後に "Error reading 'config.json' … no such file" で落ちた(logs/dashboard-job/2026-10-19-m4max.log の l.309–313 と l.508–512)。約 20 分後の次の launch で download が終わって走った(blob の日付 03:10:22 / 05:10:24)。今回は `hf download mlx-community/<repo> --include '*.safetensors' '*.json' '*.jinja'`(yardstick と同じ patterns)で先に落として回避した。swift-huggingface の snapshot 側の原因は未確認。
- 1K prompt は lorem 18 段落 +「上の文章を文脈として」→ MLX の Gemma 4 4 build のうち 3 つが断る。字面の screen は、話題の語を含む断りを PASS にする(4bit × 2)。
- e4b 4bit の catalog label は "Q4"(quant-label-rule では仕様にならない)。records にそのまま入る。

## op と delegate の観察
- MLX(Metal GPU)だけで、op / delegate / fallback の観察は無い。fp16 と fp32 の差: 測っていない。
- load 失敗の文(mlx-swift-lm 60bd0d7、mlx-swift 0bb916c6): E2B qat-mobile = `Unhandled keys ["input_activation_scale", "output_activation_scale", "weight_scale"] in language_model.model.layers.0.per_layer_projection`、E4B qat-mobile = `Mismatched parameter language_model.lm_head.weight … Actual [262144, 640], expected [262144, 2560]`。
- 同じ sitting で PTQ 4bit は decode が高く(E2B 178.68 / 151.02、E4B 111.97 / OptiQ は text-fail)、prefill はほぼ同じ(E2B 7,105 / 7,076、E4B 2,283 / 2,275)、peak は低い(E2B 3,653 / 5,246 MB)。decode だけが違う理由(1 token あたりに読む重みの bytes か)は未確認。
- mlx-swift-lm 60bd0d7 は OptiQ の kv_config.json(per-layer の KV 精度)を読まない(Libraries に参照なし)= OptiQ も既定の KV cache で走った。
- OptiQ の index は 10-18 版から optiq_vision.safetensors を登録する → mlx-swift-lm は index の file を全部読み、Gemma 4 の sanitize が vision / audio の key を捨てる。

## 使った環境
- Mac Studio(M4 Max、Mac16,9、128 GB)、macOS 27.0(26A428)。yardstick `MAIN/.build/dd-mac`(2026-10-19 05:59 build、flavor full、harness 2026-07-30-agreed-protocol-r4)、mlx-swift-lm 60bd0d7880c82980f9481f8be78862e9b63c58a3、mlx-swift 0bb916c67f4b9e5c682cbe02a42c701c93ab5021、BENCH_ENGINE_PINS_FILE = runner の既定(MAIN の ios/BenchmarkApp/Vendored/engine-pins.json、18 Pro の side tree の物と cmp で一致)。
- download: hf CLI(huggingface_hub 0.36.2、pyenv shim)。集計: python3 3.14(Homebrew)、jq。venv なし。
- quiet window: 計測 10:41:10–11:08:18(quiet_hold "r14 mlx-gemma4-file"、1628 s)、probe 10:31:10(2 s)と 10:32:37(1 s)。phone は触らない、hold なし。

## 残した file
- REPO(commit): `matrices/mlx-gemma4-file-mac.cells`(この sitting の cells; qat-mobile 行は exclude=)、`docs/dashboard-cells-v1.md`(節「MLX Gemma 4 file (2026-10-19)」)、K の `ROUND14.md`、K の `SPEED_LADDER.md`(新規)。
- MAIN(未 commit、監督が stored report として commit): `results/raw/2026-10-19-mlx-gemma4-file-mac/` = records 5 本 + gate の隔離 2 本(.attempt1)、FLAGGED.txt、SKIPPED.txt、session_provenance.txt、host_load.log(account 名は USER に置換)、NOTES-qat-mobile-load.txt。text_screen.json は無い(提案 1)。
- HF cache(`~/.cache/huggingface/hub`): 新しく落とした 4 bundle 14.6 GB。qat-mobile × 2(5.9 GB)= 消してよい(新しい mlx-swift-lm の probe まで不要)。4bit × 2(8.7 GB)= 消してよい(PTQ 行を測り直す時だけ要る)。
- scratchpad(この session): hub の metadata、probe の log、tools(dl4.sh、sitting.sh、analyze.sh、table.py、screen.py、shacheck.py)、sumbuild/(scratch の summary の木)= 消してよい。
