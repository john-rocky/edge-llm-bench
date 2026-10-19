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

## 2×2 の準備(監督の追加、13:5x)

| | 8/5 の LlmMetadata(template 8414150f) | 今の LlmMetadata(template a3c5d805) |
|---|---|---|
| 8/5 の graph(5376142457df7611) | (a) = Hub 8414150f の file そのまま、sha256 e3e29010… | (b) = 候補、e6bf25c0… |
| 9/21 の graph(082dd282972f7ddd) | (c) = a3c5d805 の file に 8414150f の LlmMetadata を re-pack: PASS、`CAND/diag/Qwen3-0.6B_dynamic_wi4b32_afp32.r0921meta0805.litertlm`、sha256 **8368cfa34c0414e626078704b7c8e319f3b3325c36cc261bdea4f2736d13552d**、344,671,744 B(LlmMetadata section = IN の 41d5368e…、他 3 section = CUR と raw identical) | (d) = 今の file、03e7da1e… |

2 つの LlmMetadata の差は `jinja_prompt_template` だけ(`llm_model_type` は両方 qwen3、他の field も同じ)。iPhone の枠で: (b) の install の後、
GPU short-chat を 1 launch ずつ (d) → (b) → (a) → (c)、(a)(c) は (b) の id の場所に (b) の名前で置く(置く度に copy back して sha256)、
`--purge-engine-cache` を毎回(GPU の cache の鍵は file の名前・mtime・size、(a) と (b) は名前も size も同じ)、最後に (b) を戻して sha256。
(a)(c) の record は端末に残るが、sitting は自分の開始より新しい record だけを pull する(`bench_matrix_iphone.sh` `pull_new`)= どの campaign にも入らない。
