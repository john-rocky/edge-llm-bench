# ROUND18 — Qwen3 0.6B dynamic INT4 candidate: the 2026-08-05 graph + the 0.18.0 LlmMetadata, measured beside the current file (worker edge-llm-bench-wt-autopilot-4f [42a8b4], Opus 5.5, started 2026-10-19 13:25 JST)

Supervisor: edge-llm-bench-55 [4f120b] (K/LANE.md first line). Branch `q06-candidate` in `~/code/edge-llm-bench-wt-autopilot`, from main at ddc2f290.

## 経過

- 13:25 launch read; ListAgents (self = edge-llm-bench-wt-autopilot-4f [42a8b4], supervisor edge-llm-bench-55 [4f120b] present, busy); HEAD ddc2f290, tree clean. Next: survey (step 1).
- 13:25–13:30 下見: Hub の履歴と file の lfs.sha256、iPhone の console、re-pack の道具、catalog / HFDownloader / MediaPipeRuntime の model の解決、run_cell.py の local path の形。
- 13:30 8414150f の file を CAND/in に download(sha256 = Hub の lfs.sha256)。13:31–13:33 identity 自己 test 2 本(PASS)、describe 2 本、graph の inventory 2 本、re-pack(PASS)。13:33–13:35 Mac probe(候補と今の file、run_all.sh、quiet_wait 0 s)。次 = catalog / Android の label / cells / build。
- 13:38–13:47 catalog の entry(REPO = SIDE、cmp 一致)、Android の label、selftest の C6、cells 4 本(Android は GPU / CPU に分割: 下の「cells」)、validate PASS、CI の手順を全部(下の「CI の下稽古」)。docs の節。
- 13:4x 監督の追加 1 件(2×2 の iPhone GPU の engine 作成の smoke: graph 8/5 / 9/21 × LlmMetadata 8/5 / 今)。(c) の re-pack を Mac で(PASS)、4 launch は go の後の iPhone の枠に入れた(`K/tools/r18_step7.sh ios-push`)。
- 13:50:39–13:52:33 build(自分の quiet_hold 114 s): Mac yardstick と iPhone app、どちらも BUILD SUCCEEDED、r17 の 4 file は戻した(sha256 一致)。
- 13:56 Mac の side-load に候補を置いた(sha256 一致)。13:56:33–13:57:53 Mac smoke(自分の quiet_hold 100 s、4 launch)。端末にはまだ触れていない(3 台とも他の lane の sitting 中: iPhone = r16 の mlx-ptq-r3、S26 = asr lane、Pixel 8a = r15 の llama-thinkoff-r2; Pixel 8a は USB に戻っている)。次 = commit、監督へ「Mac 側 PASS、端末待ち」。
- 14:0x commit 4f46adf7(明示 path 16 file: catalog、run_cell.py、selftest.py、docs、cells 4 本、ROUND18、K/tools の r18_* 7 本)と、この行の commit。次 = 監督へ「Mac 側 PASS、端末待ち」、go を待つ(端末には触れない、enqueue もしない)。
- 14:00 監督へ「Mac 側 PASS、端末待ち」。14:01 監督の go(merge f7bfbeb5 = main の HEAD、候補の sha256 を監督も計算して一致)。順: Mac は今(監督の CI の下稽古の後 = 14:05 以降)、iPhone は r16 の sitting → 監督の `q06-int8-r2` の後、S26 は queue、Pixel 8a は r15 の `llama-thinkoff-r2` の後。「primaryFile が無ければ失敗する」直しは提案に 1 行。
- 14:02 iPhone の枠に throwaway launch を足した(memory: install の後の最初の launch は scene-create の watchdog に殺される)と、枠の record の build configuration の確認。
- 14:02–14:03 chain を 4 本、run_in_background で: Mac(14:05:30 以降 かつ python の selftest が無い時に `r18_step7.sh mac-job`)、iPhone(ledger に `-q06-int8-r2-ios` の行 → `ios-push` → `ios-job`)、S26(`android s26 gpu` → `android s26 cpu`; 14:03:16 keeper 2718 が queue に、前は asr lane の hold と r15 の side_e2b)、Pixel 8a(`android pixel8a gpu` → `cpu`; 14:03:24 keeper 3289、前は r15 の hold)。
- 14:04 環境の節のために `adb -s <S26/Pixel> shell getprop ro.build.version.release` を 1 回ずつ打った(どちらも Android 16)。両方とも他の lane の hold の中だった
  = 読むだけの 1 行でも keeper の規則の外。以後、端末の値は hold の中か record から読む。
- 14:05:37 Mac の job が始まってすぐ exit 3(BUSY、ledger の行なし、sitting なし): hf-to-litertlm の lane の `scripts/convert.py Qwen/Qwen3-1.7B` が
  動いていた(子 process が CPU 105 %、6 GB)= Mac の runner の heavy guard(正しい、迂回しない)。14:0x 次は job 自身の `dashboard_job.mac_guard()` を
  import して 60 s ごとに読み、2 回続けて free の時だけ job を起こす chain にした(続けて BUSY で 2 回目の exit 3 を出さないため)。その時点は `verify_lock.py`(同じ lane)。
- 14:06–14:30 Mac の guard は BUSY のまま: hf-to-litertlm の lane の `scripts/verify_refs.sh`(参照 model 3 つ = Qwen3-1.7B、SmolLM2-1.7B、Gemma 4 E2B の
  convert → verify_lock → check を順に、quiet_wait から起動、窓は持たない)。14:29–14:30 free を 2 回 → 14:30:35 Mac の job(attempt 1、campaign
  `2026-10-19-dashboard-v1-m4max-q06cand`)、14:30:37 job が窓を取って anchors の phase。
- 14:47:44 Mac の job exit 0(ledger OK、17.2 分: anchors の phase 14:30:37–14:31:17 = ADMITTED ratio 1.004、payload 14:31:17–14:47:44 = COMPLETED)。
  post = HOLD `partial`(9 of 11 cells with records): 2 つの native 行は capture に `YARDSTICK_NATIVE_OK` の行(4 launch ずつ)だけで schema の record が無い
  (Mac の runner は native を import しない; iPhone の runner はする; 10-06 の Mac の protocol は `import_native_benchmark.py --schema-v1` で手で
  `app-path-native/` に)。2 つの dir は MAIN に未 commit のまま(REVIEW.md 付き)。監督へ 1 通(HOLD の理由)。表は native の行を `K/tools/r18_table.py`
  の中で行にして arm_row に通す。14:47:44 から他の lane(litert-cli-hf-run smoke3)が窓を持つ = python の table は quiet_wait の後。
- 14:5x 監督の指示で Mac の native 2 行を `import_native_benchmark.py --schema-v1` で MAIN の campaign の `app-path-native/` に(8 record)、NOTES.md を同じ dir に
  (`K/tools/r18_mac_native_import.sh`、quiet_wait 経由で 14:55:32 に)。監督が allow-list(56749863)と commit(e6b98c14)。表の Mac の節を書いた。
- 14:57:35 監督の `q06-int8-r2-ios` の行(OK)。14:57:46 iPhone の枠: keeper 55827 が hold を取る(queue は空)、端末は attached / unlocked。14:58:09 候補を
  side-load の dir に copy、copy back の sha256 e6bf25c0… が一致。r18 app を install。14:58:15 throwaway launch(MLX、RUN_OK 1)。14:58:16–14:59:09 2×2 の 4 launch
  (上の「2×2 の結果」)。14:59:31 候補を戻して sha256 一致。枠の record は 2 つとも Release。14:59:40 hold を返した(約 2 分)。枠の端末の dir の前後の
  一覧 = `K/r18-iphone-2x2/ios-push.log`(litert-community__Qwen3-0.6B/ の 3 file は触れていない)。
- 14:59:40 iPhone の job が始まった(job が hold を取る、campaign `2026-10-19-dashboard-v1-iphone18pro-q06cand`)。端末は 14:58 に thermal serious だった
  = anchor が nominal でなければ admission は「5 % 以内」の規則で読まれる。15:00:13 Pixel 8a の hold を keeper 3289 が取った(r15 の sitting の後)= Pixel の GPU の sitting。
- 15:11:07 iPhone の anchor の phase が ADMITTED(「non-nominal start (fair) admitted: anchor within 5% of the newest all-nominal session」; anchor の
  dynamic_int8 の 1 回目は HOT fair → 240 s の冷却の後の取り直しが OK)。payload 15:11–15:54: 今の file の GPU の 3 cell は record なし(SHORT 0 = engine の作成で失敗)、
  候補の GPU と両方の CPU は record あり。
- 15:18:22 S26 の hold を keeper 2718 が取ったが、job が exit 3(BUSY「CPU frequency capped (charge/thermal throttle): 2668/4742 MHz」= r15 の side E2B の
  sitting 14:29–15:17 の直後、ledger の行に campaign なし)。chain は exit 3 で止まり、S26 は asr lane へ。その後、job の前に冷えを待つ形を足そうとしていた所で
  user が中断(15:2x)。以後、user の指示を待つ間は新しい操作をしなかった(monitor で読むだけ)。
- 15:54:52 iPhone の job exit 0(ledger OK、55.2 分)、post は HOLD `partial`(4 of 7: 今の file の GPU の 3 cell の record が無い = 見込みどおり; iPhone では
  GPU と CPU の行が (arm, model, task) の鍵で重なるので 7)。監督が post した(bench commit 2e0ebb0c、allow-list 9f7676af)。
- 16:08:59 Pixel 8a の GPU の job exit 0(ledger OK、68.8 分 = launch の 1 枠 60 分を超えた)。16:10:06 Pixel 8a の CPU の脚が hold を取り(keeper 47743)、
  job の preflight は通った(BUSY なし)。16:21:44 anchor ADMITTED(nominal、ratio 1.047)、payload へ。
- 16:4x 監督の指示: S26 の 2 本(GPU → CPU)を queue の末尾に入れ直す(front は使わない、順は 20 時台の見込み)、hold の後に冷えの確認(thermal status 0 かつ
  cpufreq の cap なし、30 s ごとに最大 10 分 = r15 の `sitting2_r15.sh` の `cool_now`)、冷えなければ hold を返して queue に入れ直し、経過に 1 行。
  `K/tools/r18_s26_cool.sh`(新しい file: 走っている Pixel の chain が読む `r18_step7.sh` は書き換えない; bash は実行中の script を読み進めるため)。
  16:47:53 S26 の GPU の脚が queue の末尾に(keeper 56429; 前は r15 の side_e4b の hold、asr lane の 4 本、rn-litert-r2a-s26)。
- 16:5x Pixel 8a の GPU の表を読んだ: 候補の decode が −16〜−22 %(cap と熱では説明できない)。監督へ 1 通(規則の「どこかで遅い」の枝)。
- 16:5x 監督の判断: 置き換えない側で確定、S26 の 2 本は止める(S26 の数は判断を変えない)、Pixel 8a の CPU は終わらせる。1K の集計の違い(監督の単純な中央値
  31.59 → 27.36 = −13.4 %、私の arm_row の cold = 各 launch の 1 回目だけ)を表に 1 行。16:53:07 S26 の queue の待ち(pid 56469)を止めた → driver の
  cleanup が queue の行を消し keeper 56429 を止めた(driver の最後の行「queue wait gave up after 4 h」は wait の失敗の時の決まり文句で、実際は私が止めた)。
  S26 の hold(r15 の side_e4b)には触れていない(`device_hold.release` は pid が合う時だけ消す)。S26 の sitting は 0 本。
- 16:5x 表と結論の 1 行、提案、round close の節を書いた。Mac の side-load の copy と候補の Mac の cache、identity の bundle 2 本を消した(候補は CAND/out に残る)。
- 17:04:49 Pixel 8a の CPU の job exit 0(ledger OK、54.7 分)、post の check は両 dir とも PASS で job が commit(3583b968; その後の段で post exit 1 = commit は済み)。
  CPU の上限が 35〜55 % 下がった run ばかりで、cpu-cap-rule により CPU の cell は数なし。17:05:53 hold を返した。Pixel の chain は終わり。r18 の端末の作業はこれで全部。

## 下見(13:25–13:37)

- `date` 13:25:05 JST、HEAD ddc2f290(branch `q06-candidate`、tree clean)。
- Hub(HF API 13:2x、`litert-community/Qwen3-0.6B`): `Qwen3-0.6B_dynamic_wi4b32_afp32.litertlm` は 8414150f(2026-08-05T14:31Z、#4、hvt4)で
  lfs.sha256 `e3e290109da4388d65a17510a0c66af91c8039f52d2c465868dbc43c09a776cf`、344,437,808 B。154c5de0(09-19、snnn001)の時点でも同じ blob
  (last commit = 8414150f): 154c5de0 が変えたのは `qwen3_0_6b_mixed_int4.litertlm` だけ(tree の比較: b1baab46 → 7900eb4e)。a3c5d805(09-21、#6)で
  `03e7da1eb1108b50…`、344,671,744 B(= main e6687177 でも同じ)。この file の履歴は 8414150f → a3c5d805 の 2 つ(訂正 1)。
- HF cache の blob 03e7da1e… を hash して 03e7da1e…(一致)。8414150f の file の bundle の creation_timestamp は 2026-08-04T21:11:40Z、a3c5d805 は
  2026-09-19T22:16:00Z(system metadata、identity の report)。
- iPhone の失敗: `MAIN/results/raw/2026-10-19-dashboard-v1-iphone18pro-q06-dynamic-ios/console_…_long-context-1024-gen256.txt` l.45–92 =
  `delegate_metal.mm:126 Failed to create DelegateKernelLiteRtMetal: … newLibraryWithSource: program_source:30:10: … half4 half4(res)_final;`、
  `args.dst_tensor_buffer[… args.U.cmp_int4_0 …] = half4(res)_final;` → `Failed to initialize kernel` → `Failed to create engine … Failed to modify graph with delegate`(launch の通り)。
- bench の model の解決(読んだ code):
  - Apple: `HFDownloader.snapshot` は `Documents/models/litert-lm/<hfRepoId の / を __>/` が在って空でなければその dir を返し、無ければ HubClient の
    cache に download する。`MediaPipeRuntime.locateModelFile` は primaryFile が無いと、同じ dir の「web / NPU でない最初の .litertlm」、次に任意の
    .litertlm に黙って落ちる。
  - Mac: `~/Documents/models/litert-lm/litert-community__Qwen3-0.6B/` は在るが空 → Mac の 0.6B の cell は hub cache から読む(今日の Mac の record の
    `modelRevision` = e6687177、例 `MAIN/results/raw/2026-10-19-dashboard-v1-m4max-0180-rebuilt-mac/litert-lm_litert-community_Qwen3-0_6B_dynamic_wi4b32_afp32_short-chat.jsonl`)。
  - iPhone: 0.6B の record に `modelRevision` が無い = hub cache に refs/main が無い = `Documents/models/litert-lm/litert-community__Qwen3-0.6B/` に
    side-load された file を読む(`matrices/dashboard-q06-dynamic-ios.cells` の header もそう書く)。
  - → 候補を `hfRepoId = litert-community/Qwen3-0.6B` にして Mac の同名 dir に置くと、その dir が空でなくなり、Mac の 0.6B の全 cell(anchor の
    dynamic_wi4b32_afp32、今夜の job も)が hub cache を離れてその dir を読み、primaryFile の無い cell は候補に黙って落ちる。候補の record も hub cache の
    e6687177 を revision に書く(誤った出所)。→ 候補の hfRepoId は side-load 専用の `litert-local/Qwen3-0.6B-r0805meta018`(catalog の litert-local の前例と
    同じ形)、id は launch の `litert-community/Qwen3-0.6B/dynamic_wi4b32_afp32_r0805meta018` のまま(訂正 2)。
  - Android: `run_cell.ensure_model` は `file=` が host に在る path ならそのまま push する(l.361–367、sha256 で照合、record の `model.sha256` に入る)。
    前例 = `matrices/catalog-int4-vs-int8-*.cells` の `litert-local/… local=1 file=~/…` の行。足りないのは label だけ(guess_quant は file 名の末尾で引く:
    候補の名前は「unrecorded」になる)(訂正 3)。
  - 行の同一性: `render_leaderboard` は (runtime, model_id) で、`dashboard_job.cells_with_records` は (arm, model_id, task) で cell を分ける → Android の
    候補の行も今の file(`litert-community/Qwen3-0.6B` + file=)と別の model id が要る = Apple と同じ `litert-community/Qwen3-0.6B/dynamic_wi4b32_afp32_r0805meta018`。
- 既存の label の食い違い(変えない、提案 2): catalog と `ANDROID_QUANT_LABELS` の今の file の label は「GPU-graph build 2026-08-04」だが、今の bytes
  (a3c5d805)は 2026-09-19T22:16Z の再 export。2026-08-04 の build は候補の graph の方(creation_timestamp 2026-08-04T21:11Z)。

## 候補の作り方と report の要点(13:30–13:33)

道具: `LC/team_repack_20261012/tools/`(読むだけ)を `K/tools/r18_repack.sh` から quiet_wait 経由で(どれも待ち 0 s)。venv = `uv run --no-project --with litert-lm==0.18.0`
(python 3.12.11、litert_lm_builder 0.18.0、protobuf 7.36.2、CLI litert-lm 0.18.0)。置き場 = CAND(どの repo の外)。

1. IN = CAND/in/`Qwen3-0.6B_dynamic_wi4b32_afp32.litertlm`(`hf download … --revision 8414150f2e9dcc82449bcc9c5abc404b399a4d06 --local-dir CAND/in`、
   sha256 e3e29010… = Hub の lfs.sha256、344,437,808 B)。CUR = HF cache の blob 03e7da1e… の APFS clone `CAND/cur/Qwen3-0.6B_dynamic_wi4b32_afp32.a3c5d805.litertlm`
   (snapshot の symlink を渡すと tool は実体の blob 名で拡張子を見て拒む: 罠 1)。
2. `--identity` 自己 test: IN PASS、CUR PASS(どちらも changed none、4 section とも raw identical)。
3. section の比較(identity の report の sha256 の先頭 16 桁):

| section | IN 8414150f | CUR a3c5d805 | 候補 OUT |
|---|---|---|---|
| [0] LlmMetadataProto | 3,321 B 41d5368ed6dd5fe9 | 3,092 B 5af2ce2dac5a7d79 | 3,092 B 5af2ce2dac5a7d79(= CUR と byte で同じ) |
| [1] ExecutorMetadataProto | 3,847 B 63de20d6e8fd094d | 3,847 B 63de20d6e8fd094d | = IN(raw identical) |
| [2] HF_Tokenizer_Zlib | 2,142,162 B 7e610629f8a83c4f(decoded be75606093db2094) | 同じ | = IN(raw identical) |
| [3] TFLiteModel | 342,242,352 B 5376142457df7611 | 342,476,288 B 082dd282972f7ddd | = IN(raw identical) |

   LlmMetadata の 2 つの pbtext の差は `jinja_prompt_template` の 1 行だけ(IN 3,249 B e8302dce… → CUR 3,020 B 0f5642bc…、CUR = LiteRT-LM の content parts の
   Qwen3 template)。他の field は両方同じ: stop_tokens `<|im_end|>`、sampler TOP_P k 20 p 0.95 temperature 0.6、max_num_tokens 4096、llm_model_type qwen3、
   channels thought `<think>\n` / `\n</think>`。
4. graph に結びつく値(`K/tools/r18_graph_inventory.sh` = section を切り出して LC の `qwen3_gpuopt_work/tflite_ops.py`、venv ~/venvs/ltmain1013):
   両方とも signature は prefill_128 / prefill_1024 / decode、KV cache k `FLOAT32[1, 8, 32771, 128]` v `FLOAT32[1, 8, 128, 32771]` ×28、mask BOOL、
   param_tensor INT32[1,1,1,7]、FC は全部 INT4 blockwise(block=32)。LlmMetadata の max_num_tokens 4096 は両方の graph で同じ値 = NEW.pbtext を直す要は無い。
   graph の差: 8414150f には `odml.swiglu` が無い(9/21 は各 signature 28 個; 8/5 は LOGISTIC + MUL)、8/5 の prefill の signature は logits を出さない
   (9/21 は prefill でも logits `FLOAT32[1, 1, 151936]` を出す; そのため 8/5 の prefill は最後の層の o_proj / MLP と LM head が無い = FC 109 対 113)。
   composite の数(decode): 8/5 = rms_norm 113 / rope 56 / runtime_bmm 56 / cache_update 28、9/21 = 同じ + swiglu 28。8/5 の graph にも
   `odml.cache_update` は在る(launch の「SwiGLU と KV-cache update が無い」は 1.7B の card の話; 0.6B の 8/5 の graph で無いのは SwiGLU だけ: 訂正 4)。
5. re-pack: NEW.pbtext = CUR の identity の evidence の `original.LlmMetadataProto.pbtext`(sha256 662580ef…)、
   `r18_repack.sh repack jinja_prompt_template` → **PASS**:
   OUT = CAND/out/`Qwen3-0.6B_dynamic_wi4b32_afp32.r0805meta018.litertlm`、**sha256 `e6bf25c0cf7e1a09d19fc6ad716072bb5b8ac96a0eca75075a69f7ce8c1a8f91`、344,437,808 B**。
   changed fields = [`jinja_prompt_template`](expected の通り)、[1][2][3] raw identical True、system metadata は uuid / creation_timestamp だけ変わる、
   input の sha256 は実行の後も e3e29010…。header の format version 1.6.0 → 1.7.0(0.18.0 の builder が書く版; IN も CUR も 1.6.0)。
   report = CAND/out/`r0805meta018.report.json`(evidence dir 付き)。`describe`(0.18.0)は CUR と同じ capabilities(Max Context Tokens 4096、Text Backends CPU GPU)。

## Mac probe(13:33–13:35)

`K/tools/r18_probe.sh` = LC の `run_all.sh`(describe、`probe_one.py` D A B C E = litert-lm 0.18.0 python API、CPU、max_num_tokens 1024、1 条件 1 process、
各 quiet_wait、続けて `control_017.sh` = 0.17.0 CLI)を bundle の APFS clone に。clone の dir は終わりに消す(.xnnpack_cache)。同じ事を今の file にも。
結果 = CAND/probe/{cand,cur}/run_all/SUMMARY.md と probe_*.json。

| cond | 候補 | 今の file(a3c5d805) |
|---|---|---|
| D 首都 | PASS「Paris」 | PASS「Paris」 |
| A tool | PASS get_weather {location: Paris} | PASS 同じ |
| B think on, budget 300 | keyword FAIL: 300 の予算で thought が切れ、返事は計算の途中(thought の中では「230 + 161 equals 391」に届く) | keyword FAIL: 同じ形(返事は計算の途中) |
| C think off | PASS 391 | PASS 391 |
| E 2 turn の名前 | FAIL: 2 turn 目「I don't have a name」(質問を assistant の名前と読む) | FAIL: 2 turn 目「I'm an AI assistant. What's your name?」(同じ読み違い) |
| 0.17.0 CLI の D | PASS(exit 0、template error 0、Paris) | PASS |

判定: 候補は今の file と同じ所で答え、同じ所で落ちる(B は README の言う予算切れ、E は 0.6B の thinking on で両方とも)。返事は課題に答える(D / A / C)。
python API の log に prefill の token 数の行は出ない(magic number の行だけ): prompt が丸ごと届くかは bench の record の prompt token で見る
(下の「Mac smoke」: 19 token、今の file と同じ)。header 1.7.0 の候補を 0.17.0 の CLI も読んだ。

## bench の繋ぎ方(13:38–13:47)

- catalog(`ios/BenchmarkApp/Sources/Models/ModelCatalog.swift`、REPO と SIDE に同じ diff、cmp 一致; MAIN は監督の merge で):
  `dynamic_int8` の entry の後に 1 つ。id `litert-community/Qwen3-0.6B/dynamic_wi4b32_afp32_r0805meta018`、displayName
  「Qwen3 0.6B (.litertlm, dynamic wi4b32, 2026-08-05 graph + 0.18.0 metadata, local candidate)」、quantization
  「INT4 (dynamic, block-32 weights, FP32 act; 2026-08-05 graph, 0.18.0 metadata, local candidate)」、onDiskSizeMB 344、
  **hfRepoId `litert-local/Qwen3-0.6B-r0805meta018`**(訂正 2 の理由; comment に書いた)、primaryFile `Qwen3-0.6B_dynamic_wi4b32_afp32.r0805meta018.litertlm`。
  側置きの場所 = app / yardstick の `Documents/models/litert-lm/litert-local__Qwen3-0.6B-r0805meta018/`。
- Android(`android/bench/run_cell.py`): `ANDROID_QUANT_LABELS` に候補の file 名 → 上と同じ label の 1 行(quant-label-rule: 同じ artifact に同じ label)。
  local path の push は既存の形のまま(`file=~/…` = host の path を push、`model.sha256` = 端末で照合した sha256)。
  selftest の campaign C6(`android/bench/selftest.py`): 候補の名前の fake file を自分の id + `local=1` + `file=<path>` で 1 run →
  record の model.id / quantization / file / sha256 と端末の copy を照合。
- 結果: `android/bench/selftest.py` = **selftest OK**(ok 255 行、FAIL 0、C6 の 2 行 ok)、`android/bench/test_longctx1024.py` = **13 tests OK**
  (cells 4 本を足した後にもう一度 OK; 1K の対の数の期待値は変わらない)。

## cells(13:4x)

| file | 行 | 内容 |
|---|---|---|
| `matrices/q06-candidate-ios.cells` | 11 | anchor(`dashboard-text-v1.cells` の iPhone anchor と byte で同じ)+ 対 5 つ: GPU short-chat / 1K ctx 2048 / native 1024x256 ctx 2048、CPU short-chat / 1K。今の file の行は `dashboard-q06-dynamic-ios.cells`(GPU)と `dashboard-text-v1.cells`(CPU)と byte で同じ |
| `matrices/q06-candidate-mac.cells` | 11 | 同じ並び。anchor と GPU の今の file の行は `dashboard-text-v1.cells` / `dashboard-protocol1024-v1.cells` と byte で同じ; CPU の対は page に無い行 |
| `matrices/q06-candidate-android-gpu.cells` | 7 | anchor(Android の llama.cpp の行)+ GPU の対 3 つ(short-chat / 1K / native)。今の file の行は `dashboard-text-v1.cells` / `dashboard-protocol1024-v1-android.cells` と byte で同じ |
| `matrices/q06-candidate-android-cpu.cells` | 5 | anchor + CPU の対 2 つ(short-chat / 1K) |

- 候補の行の Android の model id = Apple の catalog id、`local=1 file=~/.cache/edge-llm-bench/litert-candidates/out/Qwen3-0.6B_dynamic_wi4b32_afp32.r0805meta018.litertlm`。
- Android を 2 本に分けた理由(launch の「cells 3 本」との差、訂正 5): 1 枠 ≤ 60 分。今朝の同じ model の 6 行の file
  (`dashboard-q06-dynamic-android.cells`)は S26 で 56.6 分、Pixel 8a で 62.7 分(ledger)、1 行 1 round ≈ 2.2 分(S26)/ 2.5 分(Pixel)× 3 round +
  anchor の phase 約 11〜13 分。10 行の 1 本は 80〜90 分 → GPU 6 行(S26 ≈ 55 分、Pixel ≈ 58 分)と CPU 4 行(≈ 40〜45 分)に分けた。対は同じ sitting の中。
- `validate_cells.py --require-anchor` 4 本 PASS、`--catalog`(r18 の yardstick の `list --json`)で iOS / Mac の 2 本 PASS、`matrices/*.cells` 全部 PASS。

## CI の下稽古(`.github/workflows/data-pipeline.yml` の手順、nice -n 19、13:46–13:49)

`validate_cells.py matrices/*.cells` PASS、`render_dashboard.py --check` rc 0(315 device-cells / 148 file cells)、`test_render_rules.py` OK、
`test_import_native_benchmark.py` OK、`android/bench/selftest.py` OK、`test_longctx1024.py` OK、`dashboard_job_selftest.py` / `session_check_selftest.py` /
`dashboard_post_selftest.py` / `regression_watch_selftest.py` = selftest OK、`android/ddp/selftest.py` = OK(76 checks)と `autopilot_selftest.py` = OK(58 checks)
(どちらも `BENCH_ANDROID_BIN_DIR=MAIN/android/bin`: CI は release asset を展開する; 無いと「android/bin/v0.18.0 missing」で落ちる)、
`py_compile` OK、`bash -n` OK。最初の loop の rc の列は `date` の終了 code を拾っていた(罠 3)ので、各 output の末尾で読み直した。

## build(13:50:39–13:52:33、自分の quiet_hold `r18-q06cand-build` 114 s)

`K/tools/r18_build.sh`: SIDE と MAIN の Sources の差が r17 の 4 file + ModelCatalog.swift だけである事を見てから、r17 の 4 file を退避して MAIN の版を入れ
(build の間の差 = ModelCatalog.swift だけ)、trap で戻す(戻した後の sha256 = 退避の sha256: OK)。pins file(MAIN / SIDE)は前後とも f9f0c846…。

- Mac yardstick: SIDE → `MAIN/.build/dd-mac-q06cand`(SourcePackages = `dd-ios-0180-18pro/SourcePackages` の APFS clone、r13 の行)
  `xcodebuild -project BenchmarkApp.xcodeproj -scheme yardstick -configuration Release -destination "platform=macOS,arch=arm64" -derivedDataPath MAIN/.build/dd-mac-q06cand
  -onlyUsePackageVersionsFromResolvedFile -skipPackagePluginValidation -skipMacroValidation ARCHS=arm64 ONLY_ACTIVE_ARCH=YES build` → BUILD SUCCEEDED 13:50:39–13:52:08。
  `yardstick` sha256 **735120b91e1cc16f9ef14ed0824d3547d344d3bb29f315994d75cabcd63d6f3b**、`yardstick version` = flavor=full harness=2026-07-30-agreed-protocol-r4、
  `libCLiteRTLM_mac.dylib` sha256 9526db9e…(= v0.18.0)UUID 4C4C440A(arm64)、`list --json` の litert-lm に候補の id がある。
- iPhone app: SIDE → `MAIN/.build/dd-ios-0180-18pro`(r13 の行: `xcodebuild build -project BenchmarkApp.xcodeproj -scheme BenchmarkApp -configuration Release
  -destination generic/platform=iOS -derivedDataPath MAIN/.build/dd-ios-0180-18pro -allowProvisioningUpdates -allowProvisioningDeviceRegistration
  -skipPackagePluginValidation -skipMacroValidation DEVELOPMENT_TEAM=MFN25KNUGJ PRODUCT_BUNDLE_IDENTIFIER=com.example.CoreMLLLMChat`)→ BUILD SUCCEEDED 13:52:08–13:52:33。
  `BenchmarkApp.app/BenchmarkApp` sha256 **b714ce21bb3685f5a5e5d773261753f946ade85bf578785e0e40766b7ebebd80**(前 = 12:52 の build、e92d2b4d…、
  `BenchmarkApp.app.r19-1312` として隣に APFS clone)、`CLiteRTLM.framework` UUID 8B273118(= 前)、`llama.framework` UUID 6226C23F(= b11721、= 前)、
  bundle id com.example.CoreMLLLMChat、team MFN25KNUGJ、bundle の pins = litert-lm v0.18.0。候補の id / hfRepoId / file 名の文字列が binary にある。
  1K の末尾は MAIN の版(r17 の `promptVersion` は無い)、記録名の小数秒(ResultStore)は入っている。install は go の後の iPhone の枠で。

## Mac smoke(13:56:33–13:57:53、自分の quiet_hold `r18-q06cand-mac-smoke` 100 s)

`K/tools/r18_mac_smoke.sh`: r18 の yardstick で short-chat 1 launch(runs=1、cold)ずつ、GPU → CPU、今の file → 候補、間 20 s。
record は scratchpad(results/raw に書かない)。配線と prompt token の確認で、速さの数字ではない。

| file | backend | prompt tok | 生成 | stop | modelRevision | 返事の頭 |
|---|---|---|---|---|---|---|
| 今の file | GPU(Metal 上の WebGPU、RegisterAccelerator「GPU WebGPU」) | 19 | 128 | length | e6687177(hub cache) | 「Okay, the user wants to understand on-device AI in simple terms.…」 |
| 候補 | GPU | 19 | 128 | length | なし(side-load) | 同じ文で始まる |
| 今の file | CPU | 19 | 128 | length | e6687177 | 「Okay, the user wants an explanation of on-device AI in simple terms.…」 |
| 候補 | CPU | 19 | 128 | length | なし | 同じ文で始まる |

= prompt が丸ごと届く(19 token = r13 の 0.6B short-chat の 19、今の file と同じ)、返事は課題に答える。候補は side-load の dir から読まれ、今の file は
hub cache から読まれたまま(`~/Documents/models/litert-lm/litert-community__Qwen3-0.6B/` は空のまま)。

## 2×2 の結果(iPhone 18 Pro、Metal GPU、LiteRT-LM v0.18.0 xcframework、r18 app、14:58:16–14:59:09、各 1 launch の short-chat、`--purge-engine-cache`)

| | 8/5 の LlmMetadata(template 8414150f) | 今の LlmMetadata(template a3c5d805) |
|---|---|---|
| **8/5 の graph** | (a) engine **作れた**(Metal delegate の初期化 3 回、compile error なし)。run は template で失敗: `Failed to apply template: invalid operation: tried to use + operator on unsupported types string and sequence (in template:32)` | (b) = 候補: engine **作れた**、run OK: prompt 19 token、128 生成、decode 180.4 tok/s、prefill 685.2、TTFT 76 ms、peak 753 MB(始めの thermal = serious: 直前に監督の 26 分の sitting) |
| **9/21 の graph** | (c) engine **作れない**: (d) と同じ最初のエラー `delegate_metal.mm:126 Failed to create DelegateKernelLiteRtMetal: … program_source:30:10: error: … half4 half4(res)_final;` | (d) = 今の file: engine **作れない**、同じ compile error |

= 失敗は 9/21 の graph について回り、metadata には依らない(c と d が同じ error、a と b がどちらも engine を作る)。8/5 の metadata の template は 0.18.0 の
conversation の content parts を受けない(a の run の失敗)= 候補で metadata を差し替えたのはそのため。console = `K/r18-iphone-2x2/`(下の「残した file」)。
(a)(c) の record は端末の Documents/results に残る(a は RUN_FAIL で record なし、c / d は load で失敗して record なし; b の record は sitting の
開始より古いので、どの campaign にも pull されない)。

## 計測の表

`K/tools/r18_table.py <campaign>`: MAIN の `results/summary/device-runs.csv` の行を cell ごとに `render_leaderboard.arm_row` に通す(集計はこれ 1 つ)。
regime は Mac と iPhone が warm(run 2–4)、Android が cold(全 run が新しい process)。prefill は 2 つ並べる: arm_row の値(pool の全 run、cold 込み = page の数)と、
規則の regime の値(Apple = warm の行だけを arm_row に通した値; Android = arm_row の値)。「遅い」= 規則の regime の decode か prefill が今の file より −3 % を超えて低い。
text check = Android は runner の text check、Apple は session_check の text screen(`text_screen.json`)。Mac の native 行は capture の行を import した record
(`app-path-native/`、監督の allow-list 56749863 と commit e6b98c14)。

### Mac Studio M4 Max(`2026-10-19-dashboard-v1-m4max-q06cand-mac`、14:30:35–14:47:44、anchor ratio 1.004、yardstick dd-mac-q06cand)

| arm | task | file | decode tok/s(n、spread %) | prefill 全 run | prefill warm | peak MB | prompt tok | text | Δ decode | Δ prefill warm | Δ prefill 全 run | 読み |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| GPU | short-chat | 今の file | 355.6(3、1.8) | 830.9 | 834.6 | 663 | 19 | screen PASS 4/4 | | | | |
| GPU | short-chat | 候補 | 350.5(3、2.1) | 784.2 | 852.9 | 655 | 19 | screen PASS 4/4 | −1.4 % | +2.2 % | −5.6 % | 遅くない |
| GPU | 1K ctx 2048 | 今の file | 314.9(3、1.3) | 7,297.2 | 7,342.1 | 958 | 1338 | screen PASS 4/4 | | | | |
| GPU | 1K ctx 2048 | 候補 | 310.4(3、2.7) | 7,457.5 | 7,441.4 | 1,124 | 1338 | screen PASS 4/4 | −1.4 % | +1.4 % | +2.2 % | 遅くない |
| GPU | native 1024x256 ctx 2048 | 今の file | 314.4(3、1.0) | 7,632.4 | 7,668.7 | — | 1024 | —(text 無し) | | | | |
| GPU | native 1024x256 ctx 2048 | 候補 | 306.5(3、1.2) | 7,819.5 | 7,836.7 | — | 1024 | — | −2.5 % | +2.2 % | +2.5 % | 遅くない |
| CPU | short-chat | 今の file | 84.5(3、2.0) | 88.0 | 88.5 | 388 | 19 | screen PASS 4/4 | | | | |
| CPU | short-chat | 候補 | 82.2(3、2.6) | 92.8 | 96.1 | 382 | 19 | screen PASS 4/4 | −2.7 % | +8.6 % | +5.5 % | 遅くない |
| CPU | 1K ctx 2048 | 今の file | 47.8(3、0.7) | 525.8 | 525.9 | 1,453 | 1338 | screen PASS 4/4 | | | | |
| CPU | 1K ctx 2048 | 候補 | 48.2(3、2.7) | 542.2 | 543.0 | 1,445 | 1338 | screen PASS 4/4 | +0.7 % | +3.3 % | +3.1 % | 遅くない |

- GPU short-chat の全 run の prefill の −5.6 % は、候補の run 1(cold)だけで生じた: 候補の prefill 148 tok/s / TTFT 176 ms、今の file は 676 / 77 ms。warm の 3 run
  (852.9 / 906.5 / 715.5 対 877.0 / 827.1 / 834.6)の中央値は +2.2 %。19 token の prefill = 約 20 ms の区間の値。
- GPU の decode は 3 task とも候補が −1.4〜−2.5 %(線の内側)。CPU short-chat の decode は −2.7 %(線の近く)。
- peak: GPU 1K で候補が +17 %(958 → 1,124 MB)、他は ±2 %。
- spread gate: 候補の CPU short-chat(SPREAD 17.3)と CPU 1K(SPREAD 10.1)の 1 回目は退避(`.attempt1`)され、取り直しは gate を通った。
- GPU の program cache: 今の file の分は 06:22 の作成のまま。候補の分は 14:33:46(1K の run 1 = prefill_1024 を初めて使った時)に書かれた。cold の run 1 は warm の数には入らない。

### iPhone 18 Pro(`2026-10-19-dashboard-v1-iphone18pro-q06cand-ios`、15:11–15:54、anchor = fair の始まりで 5 % 以内の規則で admitted、r18 app b714ce21…; bench commit 2e0ebb0c)

| arm | task | file | decode tok/s(n、spread %) | prefill 全 run | prefill warm | peak MB | prompt tok | text | Δ decode | Δ prefill warm | Δ prefill 全 run | 読み |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| GPU | short-chat | 今の file | —(engine が作れない、record なし) | — | — | — | — | — | | | | |
| GPU | short-chat | 候補 | 180.9(3、0.2) | 521.9 | 519.6 | 425 | 19 | screen PASS 4/4 | | | | 候補だけが動く |
| GPU | 1K ctx 2048 | 今の file | —(同じ) | — | — | — | — | — | | | | |
| GPU | 1K ctx 2048 | 候補 | 142.5(3、0.3) | 3,489.1 | 3,477.5 | 645 | 1338 | screen PASS 4/4 | | | | 候補だけが動く |
| GPU | native 1024x256 ctx 2048 | 今の file | —(同じ) | — | — | — | — | — | | | | |
| GPU | native 1024x256 ctx 2048 | 候補 | 150.6(3、0.3) | 3,842.7 | 3,847.2 | 742 | 1024 | — | | | | 候補だけが動く |
| CPU | short-chat | 今の file | 87.9(3、0.1) | 76.9 | 77.3 | 330 | 19 | screen PASS 4/4 | | | | |
| CPU | short-chat | 候補 | 87.0(3、0.4) | 77.8 | 77.9 | 412 | 19 | screen PASS 4/4 | −1.0 % | +0.9 % | +1.2 % | 遅くない |
| CPU | 1K ctx 2048 | 今の file | 50.1(3、45.8) | 409.3 | 402.3 | 1,234 | 1338 | screen PASS 4/4 | | | | |
| CPU | 1K ctx 2048 | 候補 | 49.7(3、44.5) | 422.3 | 415.8 | 1,224 | 1338 | screen PASS 4/4 | −0.7 % | +3.4 % | +3.2 % | 遅くない(両方とも spread が大きい) |

- 今の file の GPU の 3 cell は「SHORT 0」(engine の作成で失敗、2×2 の (d) と同じ compile error)= 「iPhone GPU は動くか」の答え: 候補は動く、今の file は動かない。
- CPU の 1K の spread 45 % は両方の file に同じ形で出る(warm の run が順に落ちる; 熱。memory「iPhone 2B speed needs cold measure」の形)。

### Pixel 8a(GPU = `2026-10-19-dashboard-v1-pixel8a-q06cand-gpu-android`、15:00–16:09、anchor admitted、post PASS = bench commit ac7cc70f; regime cold、firstEver の run は pool の外)

| arm | task | file | decode tok/s(n、spread %) | prefill | peak MB | prompt tok | text | Δ decode | Δ prefill | 読み |
|---|---|---|---|---|---|---|---|---|---|---|
| GPU | short-chat | 今の file | 32.8(3、15.8) | 54.0 | 2,109 | 19 | —(Android は short-chat を見ない) | | | |
| GPU | short-chat | 候補 | 25.4(2、2.7) | 55.3 | 2,104 | 19 | — | **−22.5 %** | +2.4 % | **遅い** |
| GPU | 1K ctx 2048 | 今の file | 30.6(3、1.5) | 554.5 | 1,306 | 1338 | PASS 6 | | | |
| GPU | 1K ctx 2048 | 候補 | 25.7(2、9.7) | 573.9 | 1,299 | 1338 | PASS 5 | **−15.8 %** | +3.5 % | **遅い** |
| GPU | native 1024x256 ctx 2048 | 今の file | 32.1(3、2.7) | 647.7 | 1,262 | 1024 | — | | | |
| GPU | native 1024x256 ctx 2048 | 候補 | 26.9(3、36.5) | 660.5 | 1,259 | 1024 | — | **−16.0 %** | +2.0 % | **遅い** |

- run ごと(decode tok/s): 今の file = short-chat 32.76 / 34.45 / 29.26、1K 30.47・32.78 / 30.56・32.24 / 30.94・32.31(1 launch 2 回)、native 32.08 / 31.22 / 32.1。
  候補 = short-chat 22.56(firstEver)/ 25.05 / 25.73、1K 30.42(firstEver)・31.5 / 26.97・27.36 / 24.47・32.28、native 21.26 / 31.1 / 26.94。
  今の file は 29〜34 に揃い、候補は 21〜32 に散る(候補の速い run は今の file と並ぶ)。
- 見た条件: 全 run で CPU の上限は全 policy が hw の最大(1704 / 2367 / 2914 MHz、cap なし)、thermal raw 0 → 0、affinity taskset f0、peak memory は同じ。
  = cap と熱では説明できない。原因は未確認(8/5 の decode の graph は op 936 対 830、odml.swiglu の composite が無い; それが原因かは確かめていない)。
- short-chat の生成数: 今の file 586、候補 338(Android の short-chat は model 自身の停止まで走る; 返事の長さが違う)。1K と native は 256 で同じ。
- 集計: Android の decode は arm_row の `cold_median`(coldRun True の run だけ)。1K は 1 launch に 2 回まわり、2 回目は coldRun False なので cold の pool に入らない
  = 1K の行は各 launch の 1 回目の中央値(今の file 30.47 / 30.56 / 30.94、候補 26.97 / 24.47; firstEver の 30.42 は外)。全 iteration の単純な中央値
  (firstEver を除く、監督が summary の HEAD から計算)= 31.59 → 27.36(**−13.4 %**)。どちらの集計でも −3 % を超える。

### Pixel 8a CPU(`2026-10-19-dashboard-v1-pixel8a-q06cand-cpu-android`、16:10–17:04、anchor nominal ratio 1.047、post の check は両 dir とも PASS = bench commit 3583b968)

**数なし(cpu-cap-rule)。** GPU の sitting の直後の CPU の sitting で、run ごとの CPU の上限が 35〜55 % 下がった(例 p4 1065〜1418 / 2367 MHz)。
15 % を超える cap の run は pool に入らない = arm_row の pool は今の file の short-chat の 1 run(10.1 tok/s、cap 7.8 %)だけで、他の 3 cell は 0。比べられない。

| task | file | run ごとの decode tok/s(cap の下げ幅) | 備考 |
|---|---|---|---|
| short-chat | 今の file | 10.1(7.8 %)/ 9.12(35.3 %)/ 9.17(40.1 %) | |
| short-chat | 候補 | 10.07(0 %、firstEver)/ 8.82(48.4 %)/ 8.94(48.4 %) | |
| 1K(各 launch の 1 回目) | 今の file | 17.47(40.1 %)/ 17.22(48.4 %)/ 17.19(55.0 %) | text PASS 6 |
| 1K(各 launch の 1 回目) | 候補 | 17.39(40.1 %、firstEver)/ 17.33(55.0 %)/ 17.33(48.4 %) | text PASS 5 |

- 同じ下げ幅の対(診断だけ、規則の数ではない): 1K の 48.4 % で 17.22 対 17.33、55.0 % で 17.19 対 17.33 = 候補が +0.6〜0.8 %。1K の prefill(1 回目)は候補が約 +5 %
  (今の file 93.5〜97.5、候補 101.8〜103.2)。
- 結論は変わらない(GPU で遅い)。Pixel 8a の CPU の数が要るなら、冷えた phone で CPU の file を 1 本(hold の後に r15 の冷えの確認)。

## 2×2 の準備(監督の追加、13:5x)

| | 8/5 の LlmMetadata(template 8414150f) | 今の LlmMetadata(template a3c5d805) |
|---|---|---|
| 8/5 の graph(5376142457df7611) | (a) = Hub 8414150f の file そのまま、sha256 e3e29010… | (b) = 候補、e6bf25c0… |
| 9/21 の graph(082dd282972f7ddd) | (c) = a3c5d805 の file に 8414150f の LlmMetadata を re-pack: PASS、`CAND/diag/Qwen3-0.6B_dynamic_wi4b32_afp32.r0921meta0805.litertlm`、sha256 **8368cfa34c0414e626078704b7c8e319f3b3325c36cc261bdea4f2736d13552d**、344,671,744 B(LlmMetadata section = IN の 41d5368e…、他 3 section = CUR と raw identical) | (d) = 今の file、03e7da1e… |

2 つの LlmMetadata の差は `jinja_prompt_template` だけ(`llm_model_type` は両方 qwen3、他の field も同じ)。iPhone の枠で: (b) の install の後、
GPU short-chat を 1 launch ずつ (d) → (b) → (a) → (c)、(a)(c) は (b) の id の場所に (b) の名前で置く(置く度に copy back して sha256)、
`--purge-engine-cache` を毎回(GPU の cache の鍵は file の名前・mtime・size、(a) と (b) は名前も size も同じ)、最後に (b) を戻して sha256。
(a)(c) の record は端末に残るが、sitting は自分の開始より新しい record だけを pull する(`bench_matrix_iphone.sh` `pull_new`)= どの campaign にも入らない。

## 結論

**置き換えない。Pixel 8a の GPU で decode が 13〜22 % 遅い。iPhone の GPU では候補だけが動く。**(code-2d の規則の 2 つ目の枝 = iOS 用の別 file か card の注記の案へ。
どちらも監督が書く。)遅い原因の見込み(8/5 の graph の decode は op 936 対 830、SwiGLU の composite が無い)は未確認。
Mac は全 cell で −3 % の内側、iPhone の CPU は遅くない、Pixel 8a の CPU は数なし(cpu-cap-rule: GPU の sitting の直後で CPU の上限が 35〜55 % 下がった)、
S26 は測っていない(監督の判断: 数が判断を変えない)。

## commit

- 4f46adf7(catalog、run_cell.py、selftest、cells 4 本、docs、ROUND18、K/tools の r18_* 7 本)、518cb1d5(ROUND18 の commit の行)= 監督の merge f7bfbeb5。
- この節より後の分 = 最後の commit(下の「残した file」と監督への最後の 1 通)。
- MAIN 側(監督): Mac の native の allow-list 56749863 と結果 e6b98c14、iPhone の結果 2e0ebb0c と allow-list 9f7676af。

## 提案

1. `MediaPipeRuntime.locateModelFile` は primaryFile が無い時に別の .litertlm に黙って落ちる。`HFDownloader.snapshot` は repo の dir に file が 1 つでも在ると
   全 entry にその dir を返す。この 2 つが重なると、別の file を測った数がその entry の label で出る(wrong-looking-right)。primaryFile が無ければ失敗にする
   (監督の 14:01 の指示の 1 行)。
2. Mac の runner は native-benchmark の行を import しない(iPhone の runner はする)。そのため job の経路の Mac の sitting は native 行で `partial` の HOLD に
   なる。`import_native_benchmark.py --schema-v1` を Mac の runner に足す(監督の後日の項目)。
3. `dashboard_job.cells_with_records` の鍵は (arm, model, task)。iOS では同じ model の GPU と CPU の行が 1 つの鍵に重なり、CPU の record(`litert-lm-cpu`)は
   その鍵に合わない(iPhone の「4 of 7」)。鍵に backend を入れる(Mac と Android の capture の鍵は既に backend を持つ)。
4. 候補は CAND/out(sha256 e6bf25c0…)にあり、iPhone の app の side-load の dir にも置いてある。iOS 用の別 file を Hub に出すなら、catalog の hfRepoId を
   litert-local から Hub の repo へ移し、primaryFile をその名前に。card の注記なら、今の file が iPhone の Metal GPU で engine を作れない事と、
   動く版(8/5 の graph)の事を書く。
5. Pixel 8a の GPU で遅い原因(未確認)の切り分け: 9/21 の graph から SwiGLU の composite だけを外した export(litert-torch の `use_swiglu_composite` を off)との
   A/B。S26(Adreno)では測っていない。
6. 今の file の label「GPU-graph build 2026-08-04」(catalog と `ANDROID_QUANT_LABELS`)は 8/5 の build を指すが、今の bytes は 09-19 の再 export。
   label を直すと series が分かれる = owner の判断。
7. Pixel 8a の Android の 6 行の file は 63〜69 分かかる(今朝 62.7、今日の GPU 68.8)。1 枠 60 分に収めるなら Pixel では 1 file の litert の行を 5 本までにする。
8. 同じ phone で GPU の file の直後に CPU の file を回すと、CPU の上限が下がったまま測る(今日の Pixel 8a: 35〜55 %、CPU の cell は数なし)。CPU の file は
   冷えの確認(r15 の `cool_now`)の後か、別の時間に。`K/tools/r18_s26_cool.sh` の形を `r18_step7.sh android` の CPU の脚にも入れるなら、同じ dir の
   新しい file にして rename(走っている chain の script を書き換えない)。

## 訂正

1. 「0.6B の file の Hub の履歴 8414150f → 154c5de0 → a3c5d805」: 154c5de0 はこの file に触れていない(`qwen3_0_6b_mixed_int4.litertlm` だけ)。この file の履歴は 8414150f → a3c5d805(HF API の tree の比較、上の「下見」)。
2. 「catalog の hfRepoId は同じ repo」: 同じ repo の id では Mac の 0.6B の全 cell が候補に落ちる(`HFDownloader.swift` の空でない dir の早帰り、`MediaPipeRuntime.swift` `locateModelFile` の落ち先、Mac の record の modelRevision e6687177)→ hfRepoId は `litert-local/Qwen3-0.6B-r0805meta018`(id は launch の通り)。
3. 「Android は Hub に無い file を取れない(local の override が要る)」: `android/bench/run_cell.py` l.361–367 が host の path を既に push する(前例 `matrices/catalog-int4-vs-int8-*.cells`)。足したのは label と selftest だけ。
4. 「(1.7B と違い)0.6B の card は SwiGLU と KV-cache update の composite」: 8/5 の 0.6B の graph にも `odml.cache_update` は在る。8/5 に無いのは `odml.swiglu` だけ(`~/.cache/edge-llm-bench/litert-candidates/graph/in0805.ops.txt`)。
5. 「cells 3 本」: 4 本にした(Android を GPU / CPU に分けた: 1 枠 60 分; 今朝の 6 行の file が S26 56.6 分 / Pixel 8a 62.7 分、`MAIN/logs/dashboard-job/ledger.tsv`)。それでも Pixel 8a の GPU の file は 68.8 分かかった。
6. 「post は job が回す」: Mac の sitting は native 行の import が無いため、iPhone の sitting は今の file の GPU の cell に record が無いため、どちらも `partial` の HOLD(各 dir の REVIEW.md; 監督が allow-list と post)。
7. 「Mac は空き」(13:2x): 14:05–14:30 は hf-to-litertlm の lane の参照 model の変換の batch で Mac の guard が BUSY(ledger 14:05:37 の BUSY の行)。
8. 今の file の label「GPU-graph build 2026-08-04」は 8/5 の build を指すが、今の Hub の bytes は 2026-09-19T22:16Z の再 export(identity の report の system metadata)。

## 罠と袋小路

1. `repack_metadata.py` に HF cache の snapshot の symlink を渡すと、実体の blob 名(拡張子なし)で拒む → `.litertlm` の名前の APFS clone を渡す。
2. zsh: 変数に入れた「script --flag」は 1 語のまま(`render_dashboard.py --check` が 1 つの file 名になった)。`"$(date) rc=$?"` の `$?` は date の終了 code。各 output の末尾を読み直した。
3. quiet window の hook は、自分の窓でも他人の窓でも、開いている間は shell の python を拒む → Edit / jq / `quiet_wait.py` 経由で。
4. `pgrep -f` は他の session の prompt にも当たる → `pgrep -x`、または python の argv[0] に錨を置いた pattern。
5. `android/ddp/selftest.py` と `scripts/autopilot_selftest.py` は `BENCH_ANDROID_BIN_DIR=MAIN/android/bin`(v0.18.0 の親の dir。v0.18.0 そのものでは「…/v0.18.0/v0.18.0 missing」)。
6. Mac の runner は native-benchmark を `YARDSTICK_NATIVE_OK` の行のまま残す → job の post は `partial` → `import_native_benchmark.py --schema-v1 … --model-id <id>`(Mac の行は model を持たない)で `app-path-native/` に。
7. 他の lane の sitting の直後の端末は CPU の上限が下がっている(S26 2668/4742 MHz)→ job が exit 3 で断る。hold を取った後に冷えを確かめてから job(r15 の `cool_now` の形、`K/tools/r18_s26_cool.sh`)。
8. 走っている chain が読んでいる bash の script を書き換えない(bash は読み進めながら実行する)→ 新しい file にするか、同じ dir で rename する。
9. 新しい file の LiteRT-LM の GPU の program cache(`$TMPDIR/<file>_<mtime>_<size>_mldrift_program_cache.bin`)は、1K の run 1 で prefill_1024 の分が書かれる = cold の run 1 は warm の pool の外。
10. `~/Documents` には iCloud の file provider の xattr(detached)が付いている。side-load の file は sitting の前に `ls -lO` で dataless でない事を見る。
11. 自分の不手際: 他の lane の hold の中の 2 台に `adb shell getprop` を打った(読むだけ)→ 端末の値は自分の hold の中か record から読む。

## op と delegate の観察

- iPhone 18 Pro、Metal GPU、LiteRT-LM v0.18.0(`CLiteRTLM.xcframework`、framework UUID 8B273118): 9/21 の graph は delegate の初期化で失敗:
  `delegate_metal.mm:126] Failed to create DelegateKernelLiteRtMetal: INTERNAL: newLibraryWithSource: program_source:30:10: error: cannot initialize a variable of type 'half4' … half4 half4(res)_final;`
  (`args.U.cmp_int4_0` の store、compile error は 1 launch に 9 行)→ `Failed to initialize kernel` → `Failed to modify graph with delegate` → engine の作成が失敗。
  8/5 の LlmMetadata を入れても同じ((c))= graph に付く。8/5 の graph: Metal の delegate の初期化が 3 回(外部 tensor 57 / 57 / 58)、error なし、
  `Metal sampler not available, falling back to statically linked C API`。RegisterAccelerator は「GPU Metal」。
- graph の op(`tflite_ops.py`): decode 936(8/5)対 830(9/21)、`odml.swiglu` 0 対 28(各 signature)、8/5 の prefill の signature は logits を出さない
  (FC 109 対 113、rope 55 対 56)、rms_norm / rope / runtime_bmm / cache_update は両方に在る。FC の weight は両方とも INT4 blockwise(block=32)。
- 8/5 の template(LlmMetadata)は 0.18.0 の conversation の content parts を受けない: `Failed to apply template: invalid operation: tried to use + operator on unsupported types string and sequence (in template:32)`((a) の run)。
- Mac M4 Max: GPU の arm は Metal の上の WebGPU(RegisterAccelerator「GPU WebGPU」、adapter Apple M4 Max metal-3)。
- Pixel 8a の GPU(LiteRT-LM android v0.18.0、OpenCL): 8/5 の graph の decode が 13〜22 % 遅く、run ごとのばらつきが大きい。原因は未確認。
- fp16 と fp32 の差、fallback の件数: 測っていない(未確認)。

## 使った環境

- Mac Studio M4 Max(Mac16,9)、macOS 27.0(26A428)、Xcode 27.0(27A266a)。uv 0.11.19。re-pack / describe / probe = `uv run --no-project --with litert-lm==0.18.0`
  (python 3.12.11、litert-lm 0.18.0、litert-lm-builder 0.18.0、protobuf 7.36.2)、0.17.0 の CLI = `~/.local/bin/litert-lm`(control)、graph の inventory =
  `~/venvs/ltmain1013`(ai-edge-litert-nightly 2.4.0.dev20261011、ai-edge-quantizer-nightly 0.10.0.dev20261013)。huggingface_hub 1.8.0(python)/ hf CLI 0.36.2。
- Mac の yardstick `MAIN/.build/dd-mac-q06cand`(sha256 735120b9…、LiteRT-LM v0.18.0 の dylib 9526db9e…)、pins file f9f0c846…。窓 = 自分の quiet_hold(build、smoke)、
  Mac の sitting は job の窓。
- iPhone 18 Pro(iPhone19,2、UDID 00008160-000038CA02C00036)、iOS 27.2。app = r18 の build(BenchmarkApp sha256 b714ce21…、CLiteRTLM 8B273118、llama 6226C23F、Release)。
  hold `~/code/coreai/ondevice/.device_hold`: 枠は keeper 55827(14:57:46–14:59:40)、sitting は job。
- Pixel 8a(4C131JEKB15210、akita、Android 16)、LiteRT-LM android v0.18.0(flat)。hold `…/s2_npu_sweep/.device_hold.pixel8a`: GPU = keeper 3289(15:00:13–16:10:05)、
  CPU = keeper 47743(16:10:06–)、job は `BENCH_SITTING=1 --hold-held-by`。
- Galaxy S26(RFGL80R6A6H、SM-S942Q、Android 16): sitting なし(15:18:22 の hold で job が exit 3、16:47–16:53 は queue の末尾で待って止めた)。
- 17 Pro には触れていない。

## 残した file

- REPO(branch `q06-candidate`): catalog の entry、`android/bench/run_cell.py` の label、`android/bench/selftest.py` の C6、`matrices/q06-candidate-{ios,mac,android-gpu,android-cpu}.cells`、
  `docs/dashboard-cells-v1.md` の節、`K/ROUND18.md`、`K/SPEED_LADDER.md`(r18 の梯子)、`K/tools/r18_*`(repack、graph inventory、extract_tflite、probe、build、mac_smoke、
  step7 = Mac / iPhone / Android の driver、s26_cool、mac_native_import、table)、`K/r18-iphone-2x2/`(2×2 の console 4 本と枠の log)。
- CAND = `~/.cache/edge-llm-bench/litert-candidates/`(どの repo の外、1.3 GB): `out/`(候補と re-pack の report)= 残す。`in/`(8414150f の file)= 残す(再 re-pack の元)。
  `diag/`(2×2 の (c) と report)= 消してよい。`cur/`(a3c5d805 の APFS clone)= 消してよい。`identity/`(report だけ; identity の bundle 2 本は消した)、
  `describe/`、`graph/`、`meta/`、`probe/` = 証拠、残す。
- MAIN: `.build/dd-mac-q06cand`(候補の entry 入りの Mac yardstick)= 候補の Mac の sitting が要らなくなれば消してよい。
  `.build/dd-ios-0180-18pro/Build/Products/Release-iphoneos/BenchmarkApp.app` = r18 の build(18 Pro に install 済み)、`BenchmarkApp.app.r19-1312` = その前の app(残す)。
  campaign の dir: Mac 2 と iPhone 2 = 監督が commit(e6b98c14、2e0ebb0c)、Pixel 8a GPU 2 と CPU 2 = job の post が commit(ac7cc70f、3583b968)。
- 端末: iPhone の app の `Documents/models/litert-lm/litert-local__Qwen3-0.6B-r0805meta018/`(候補、344 MB)= iOS 用の別 file の判断まで残す(要らなければ消してよい)。
  枠の smoke の record 2 つが app の Documents/results に(どの campaign にも入らない)。Pixel 8a の `/data/local/tmp/llmbench/models/` の候補の copy(+ `.sha256`、
  engine の cache)= 消してよい(次の hold の中で)。
- 消した物: Mac の side-load の copy(`~/Documents/models/litert-lm/litert-local__Qwen3-0.6B-r0805meta018/`、CAND/out の clone)、その GPU / XNNPACK の cache
  (`$TMPDIR`、約 0.9 GB)、identity の bundle 2 本(0.66 GB)、未使用の `K/tools/r18_step7.sh.new`。
- scratchpad(commit しない): build / smoke / 表の出力、端末の枠の log の元。
