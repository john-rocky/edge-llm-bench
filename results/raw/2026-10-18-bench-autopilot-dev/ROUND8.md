# Round r8 — team rules in the session checker (pin-drift, protocol-off) + the post's commit-message guard — worker `edge-llm-bench-wt-autopilot-a4 [43e38b]` (Opus 5.5), started 2026-10-19 02:40 JST

Supervisor: `edge-llm-bench-55 [4f120b]`. cwd ~/code/edge-llm-bench-wt-autopilot, branch bench-autopilot, HEAD 9ab1556e at start. Mac only: no adb, no devicectl, no gcloud, no docker, no build; the night job measured this Mac the whole round (02:00 firing, `logs/dashboard-job/2026-10-19-m4max.log` of the main tree).

## 結果 (要約)

- CHECK に FAIL の規則 2 本: `pin-drift` (LiteRT-LM の cell が、その sitting の日にどこかの platform の pin が指す最新の release より古い) と `protocol-off` (LiteRT-LM の headline cell が合意 protocol から外れる: context 2048、protocol cell はさらに prompt 1024 / generated 256)。allow-list でこの 2 本を許す行は読み込み時に exit 2。POST: 生成 message に `%` か順位の語があれば commit せず ledger 行 + exit 1 (REVIEW.md なし)、通れば `message guard: … OK` の行。
- (a) selftest 5 本 exit 0: session_check 39 → 49 (+10)、dashboard_post 48 → 51 (+3)、dashboard_job 89、regression_watch 50、autopilot 58。
- (b) commit 済み 116 dir: PASS 87 / HOLD 28 / FAIL 1、変更前の checker と全 dir・全 finding が同一 (新規則の finding 0)。launch の「FAIL になるべき」11 dir (名指し 8 + 「+ anchor」の 3) は 1 つも commit されていない (全部 main tree の backlog) → (c) で突き合わせ。
- (c) backlog 69 dir: PASS 22 / HOLD 22 / FAIL 25、pin-drift 14 dir = launch の集合 11 dir と一致 + anchor 3 dir (過、理由つき)、不足 0。「FAIL になってはいけない物」に新規則の finding 0。protocol-off は (b) (c) とも 0。
- (d) POST の dry run (S26 0180 s8a の対、scratch clone): exit 0、message に `%` と順位の語なし、guard の OK 行。
- (e) (b) 116 dir 10.54 s、(c) 69 dir 6.36 s (r1: 77 dir 12.3 s; 枠 3 分)。
- 監督の追加 (03:0x、user の決定 10-19): LOCK に `arms.litert-lm.ios` (v0.18.0 since 2026-10-19)、`registry_pin()` が iPhone の LiteRT-LM をその block で読む、selftest 2 case、docs。
- 前提の食い違い 1 件を自分で直した: POST の anchor の句 `ratio <R> vs <reference>` は guard に掛かる (attached phone の sitting 全部が止まる) → `ratio <R> to reference <reference>`。数字は変わらない。

## 下見

- `date` 02:40:03 JST (launch は 03:0x)。HEAD 9ab1556e = launch どおり、status clean。main tree の HEAD は f6958509 (9ab1556e の子 1 本、docs/OPERATIONS.md、02:31:59)。
- selftest (変更前、全部 exit 0): `session_check_selftest.py` 39 checks、`dashboard_post_selftest.py` 48、`dashboard_job_selftest.py` 89、`regression_watch_selftest.py` 50、`autopilot_selftest.py` 58 (`BENCH_ANDROID_BIN_DIR=~/code/edge-llm-bench/android/bin`)。
- 変更前の checker で基準を取った: commit 済み 116 dir PASS 87 / HOLD 28 / FAIL 1 (10.67 s)。
- `~/code/coreai/_GPU_LOCK` は空 (timing の window なし)。夜の job は Mac で計測中。

## 仕様の確定

### platform ごとに読んだ field と accessor

| 何 | Android (run_cell.py の record) | iPhone / Mac (yardstick; native は app-path-native/ に import) | checker が使う物 |
|---|---|---|---|
| context | `conditions.contextTokens` (cell に context-tokens= があれば int、無ければ文字列 `bundle-default`) | `metrics.contextTokensConfigured` | `build_summary.context_tokens_of(d, m)` = summary の `context_tokens` 列と同じ (contextTokensConfigured、無ければ conditions.contextTokens; 数字の文字列はそのまま、`bundle-default` は None)。checker は int に揃えて 2048 と比べ、None は「context なし」= off |
| prompt | `metrics.promptTokenCount` | 同じ | protocol cell だけ = 1024 |
| generated | `metrics.generatedTokenCount` | 同じ | protocol cell だけ = 256 |
| engine | `engineVersion` | 同じ | release tag = `v?\d+\.\d+(\.\d+)?` の fullmatch。数値の tuple で比べる |

開いた record: S26 0180 s8a の native (`conditions.contextTokens` 2048 / 1024 / 256)、DDP 10-18 (1K = `conditions.contextTokens` 2048、short-chat = `bundle-default`)、main tree の 10-19 Mac sitting の Gemma 4 E2B (1K = `contextTokensConfigured` 2048、short-chat = 672 = 規則の外)。commit 済み summary の LiteRT-LM headline 行で 2048 / 1024 / 256 でない物は 08-17..09-11 の hand run だけ (下の訂正)。

### newest(day) の表 (日付の区間 → newest)

| sitting の日 | checker が読む registry (`registry_at`: 最初の record の時刻以前の最新 commit) | 候補 | newest |
|---|---|---|---|
| 〜 2026-10-11 | a984c5aa / c3f33fc3 / bfa6e4d3 (10-08..10-09) | default_tag v0.16.0、android `tag_built` v0.16.0 (since なし) | **v0.16.0** |
| 2026-10-12 〜 10-14 | 同上 + mac block (dad937b1 の物を `REGISTERED_LATER` が足す、since 10-12) | + mac v0.18.0 | **v0.18.0** (mac since 2026-10-12, registered at dad937b1) |
| 2026-10-15 〜 10-18 | d33ffa53 (10-15 00:30) / dad937b1 (10-18 22:38) | + android v0.18.0 since 10-15、PINS `android_pins.litert-lm` v0.18.0 | **v0.18.0** (mac; android) |
| 2026-10-19 〜 | この round の commit (`arms.litert-lm.ios`) | + ios v0.18.0 since 10-19 | **v0.18.0** |

PINS と LOCK の android block は d33ffa53 と dad937b1 で同じ v0.18.0 = 「違ったら高い方 + note」の note はどこにも出ない (selftest は note の分岐を通らない; 下の提案)。

### 決めた事と根拠

1. **PINS は LOCK の android block の since から数える** (仕様 1 は「PINS の最大」)。PINS には since がなく、`_doc` が「lock の android block が mirror」と書く。selftest の合成 dir と CI の shallow clone は record の時刻 = 今なので HEAD の registry を読む: since なしで数えると 2026-10-11 の sitting でも newest = v0.18.0 になり、既存 case「since の前日は PASS」が割れる。実データでは PINS の `android_pins` 自体が d33ffa53 (10-15 00:30) より前に無いので、どちらの読みでも同じ答え。違う時は高い方を Android の pin にし、LOCK の block の since を使う (note を出す)。
2. **対象の runtime** は 2 本とも `litert-lm` / `litert-lm-cpu` / `litert-lm-gpu`。`registry_pin()` が side build と答える物 (`litert-lm-npu`) は外す。`litertlm-android:0.17.0` (2 つの DDP hand run の Maven artifact) は release tag の定義に合わない = note。
3. **対象の dir** は既存の record 規則と同じ: job anchor / job payload / job payload (ddp)。hand run と SESSION.json のない DDP は `not-job` のまま (record 規則は走らない)。10-16 の S26 DDP split 10 dir もこれ (commit 済み、新規則の finding 0)。
4. **protocol-off** は cell ごとに 1 finding、外れた値と run 数 (`3 of 4 runs off … : context 1056 x1; prompt 1023 x1; generated 128 x1`)。context の欄の値が無い・`bundle-default` の run も off (PROTO「contextTokensConfigured が null の結果は card と比べられない」)。1K の text task は context だけ (generated は EOS で短い run がある、prompt は tokenizer の数 1106 / 1338)。
5. **pin-drift** は (platform, runtime) ごとに 1 finding、detail に stamp の内訳・newest・それを決めた block と since・registry の commit。新しすぎる stamp (`v9.9.9`) は FAIL にしない (engine-stamp の HOLD のまま)。
6. **guard** は REFUSED_WORDS の後、message を log に出した後 (止まった時に人が文を読める)。REVIEW.md は書かない (`hold_message`)、ledger 行は main() の既存の書き込み、exit 1。dry run でも同じく止まる。止まる経路は実データでは SESSION.json の `reason` (ratio のない anchor の時にそのまま入る) と FAILURES.txt の行; どちらも今の repo に該当なし (FAILURES.txt を grep、job の reason の文面を読んだ)。
7. **anchor の句** `vs` → `to reference` (下の訂正)。memory「No asking when results are unaffected」(数字を変えない) により監督に聞かずに直した。

## 結果

### (a) selftest

| command | 前 | 後 | exit |
|---|---|---|---|
| `python3 scripts/session_check_selftest.py` | 39 | 49 (worktree では commit 前 47 + skip 1: iOS の 2 case は commit された LOCK を読む; LOCK を commit した scratch clone で 49 / skip 0; commit 後の結果は経過の最終行) | 0 |
| `python3 scripts/dashboard_post_selftest.py` | 48 | 51 | 0 |
| `python3 scripts/dashboard_job_selftest.py` | 89 | 89 | 0 |
| `python3 scripts/regression_watch_selftest.py` | 50 | 50 | 0 |
| `BENCH_ANDROID_BIN_DIR=~/code/edge-llm-bench/android/bin python3 scripts/autopilot_selftest.py` | 58 | 58 | 0 |

新 case (session_check +10): pin-drift = iPhone の v0.16.0 × newest v0.18.0 で FAIL (1 finding、detail に newest と block) / その anchor phase は PASS / 最初の新しい pin の since の前日 (2026-10-11) は出ない / release tag でない stamp (`main@1dadd00c`) は note (engine-stamp の HOLD だけ); iOS block = since の日 (2026-10-19) に v0.18.0 なら engine-stamp も pin-drift もなし / 前日 (2026-10-18) に default_tag v0.16.0 なら engine-stamp なし・pin-drift FAIL; protocol-off = native の context 1056・prompt 1023・decode 128 と text の context 672 で FAIL (cell ごとに 1 つ、計 2) / MLX の text 2523・llama-bench の context なし・LiteRT-LM の梯子 4096・short-chat は finding なし (PASS); allow-list = pin-drift の行・protocol-off の行で exit 2 (2 case)。既存 case の変更 1: Mac block の since 後に default_tag を stamp する Mac sitting は HOLD → FAIL (engine-stamp に pin-drift が加わる; 判定の追加であって既存規則の変更ではない)。前日 case は「pin-drift なし」も確かめる。
dashboard_post +3: PASS の message に `%` も順位の語もなく guard の OK 行 / anchor の reason に `3% faster than` を入れた sitting: 全 dir PASS のまま exit 1、HEAD 不変、ledger の note `held: the generated message carries a percentage or a standing word (%, faster, than) …`、REVIEW.md なし / 同じ sitting の `--dry-run` も exit 1。既存の DDP message の case に `STANDING_WORDS` が掛からない事を足した。
変更した 2 本の selftest は python 3.11.13 (uv、CI と同じ minor) と 3.12.13 でも selftest OK。py_compile は 3.10.13 でも通る。CI (`.github/workflows/data-pipeline.yml`) は変更なし (両方を既に回す)。

### (b) commit 済み sitting 全部

`K/committed_check_r8.md` (116 行、列: dir / 種類 / verdict / r8 前 / r1 (a) / 規則 id / 新規則の finding)。

- 集計: PASS 87 / HOLD 28 / FAIL 1。r8 前の checker (02:45 の基準) と verdict が違う dir 0、新規則以外の finding も全 dir で同一。新規則の finding 0 (pin-drift 0、protocol-off 0)。
- r1 の (a) (commit 済みの -dashboard-v1- job sitting 88 dir) は r1 と同じ PASS 77 / HOLD 11 / FAIL 0、HOLD の 11 dir も同じ。r1 の後に増えた dir は 1 (`2026-10-18-dashboard-v1-s26-ddp-m1q-36-android`、PASS)。
- 新しく FAIL になった dir: なし。今の FAIL 1 = `2026-09-27-tts-rtf-v1-s26-anchor-android` (hand run、not-admitted + not-job、r1 の (b) の既知の悪い dir、r8 前から FAIL)。
- launch の「FAIL になるべき」集合との突き合わせ (b): 11 dir (名指し 8 + 「+ anchor」の 3) のどれも commit 済みではない → (b) では一致・過不足とも 0、(c) で行う。
- 「FAIL になってはいけない物」で commit 済みの物: Pixel 8a 0180 10-15 の 32 dir、S26 0180 10-15 の 12 dir、S26 DDP 10-18、iPhone 17 Pro 0180 AA 10-17 の 2 dir、10-11 以前の commit 済み全部 → 新規則の finding 0。S26 0180 ddp 10-16 の 10 split は SESSION.json を持たない (この集合の外) ので別に掛けた: 全部 HOLD not-job、新規則の finding 0。

### (c) backlog

`K/backlog_table_r8.md` (69 行、`backlog_table.md` の列 + 「r1 の verdict」)。main tree の `git status --porcelain results/raw` は 02:44 と 03:05 で同じ 90 untracked 行 = 69 dir。

- 集計: PASS 22 / HOLD 22 / FAIL 25 (r1 の表 77 dir: 27 / 28 / 22)。
- r1 から verdict が変わった dir (14、全部名指しは表の後の節): pin-drift で 12 (`2026-10-13-dashboard-v1-pixel8a-a` HOLD→FAIL、`-pixel8a-anchor` PASS→FAIL、`2026-10-14-dashboard-v1-s26-a` HOLD→FAIL、`-s26-anchor` PASS→FAIL、`-s26-b1` HOLD→FAIL、`-s26-b2` PASS→FAIL、`2026-10-15-dashboard-v1-iphone18pro-anchor` / `-r2-anchor` PASS→FAIL、`-iphone18pro-r2` HOLD→FAIL、`2026-10-17-dashboard-v1-iphone18pro-anchor` / `-r2-anchor` PASS→FAIL、`-iphone18pro-r2` HOLD→FAIL)、新規則の外で 2 (`2026-10-12-dashboard-v1-m4max-anchor-mac` と `2026-10-16-dashboard-v1-m4max-r2-anchor-mac` が HOLD→PASS: r1 の engine-stamp (registry v0.16.0) が Mac block (f36512ae / dad937b1) で消えた)。`2026-10-15` と `2026-10-17` の `-iphone18pro-ios` は r1 から FAIL (not-admitted) のまま、pin-drift が加わった。
- r1 の表にあって今の backlog に無い dir 10 = 10-16 の S26 DDP split (execution-level logcat.txt が 6e3d5908 の .gitignore 行で ignored になり untracked 行が消えた; (b) で別に掛けた)。r1 に無かった dir 2 = 10-19 の Mac sitting (記録の時点で計測中: payload は SESSION.json なし = session-missing)。
- launch の「FAIL になるべき」集合との突き合わせ (1 行ずつ):
  - 一致 (11): `2026-10-13-dashboard-v1-pixel8a-a-android`、`2026-10-14-dashboard-v1-s26-{a,b1,b2,anchor}-android`、`2026-10-15-dashboard-v1-iphone18pro{,-r2}-ios`、`2026-10-17-dashboard-v1-iphone18pro{,-r2}-ios`、`2026-10-17-dashboard-v1-iphone18pro{,-r2}-anchor-ios` — 全部 FAIL pin-drift。
  - 過 `2026-10-13-dashboard-v1-pixel8a-anchor-android`: anchor の cell が LiteRT-LM GPU Qwen3 0.6B (`matrices/anchors.cells` の android 行) で v0.16.0 x3、10-13 の newest は v0.18.0 (mac since 10-12)。規則どおり。
  - 過 `2026-10-15-dashboard-v1-iphone18pro-anchor-ios`、`2026-10-15-dashboard-v1-iphone18pro-r2-anchor-ios`: anchor の cell が LiteRT-LM Qwen3 0.6B (`anchors.cells` の ios 行) で v0.16.0 x3。launch は 10-14 と 10-17 にだけ「+ anchor」と書いた。規則どおり。
  - 不足: なし。
- 「FAIL になってはいけない物」(backlog 側 48 dir: 10-11 以前の全部、Mac 10-12 の 2 dir、Mac 10-16 r2 の 2 dir): 新規則の finding 0。

### (d) POST の dry run

形: commit 済み dir に `--dry-run` を掛けると message の前に「nothing to commit」で返る (下の訂正) ので、scratch clone (この worktree を `git clone --shared --no-checkout`、`read-tree HEAD`、対を `git rm --cached` して scratch commit 1 本、対の dir を untracked で置く) の中で、この worktree の POST を走らせた。夜の job の cooldown 中、`taskpolicy -b`。

```
cd <scratch clone> && TMPDIR=<scratchpad>/posttmp taskpolicy -b python3 ~/code/edge-llm-bench-wt-autopilot/scripts/dashboard_post.py \
  results/raw/2026-10-15-dashboard-v1-s26-0180-s8a-anchor-android results/raw/2026-10-15-dashboard-v1-s26-0180-s8a-android \
  --dry-run --no-page-commit --switch ~/code/edge-llm-bench-wt-autopilot/ops/autopilot/switch.json
# exit 0, real 20.44 s (user 2.99, sys 9.46: HEAD + dirs の書き出しが大半)
```

生成 message の全文 (1 行):

```
results 2026-10-15 Galaxy S26 (SM-S942Q), litert-lm-cpu: v0.18.0, litert-lm-gpu: v0.18.0, llama.cpp: b8999: 2/2 cells of matrices/dashboard-0180-s26-s8a.cells in one dashboard-job sitting 21:01–21:32 JST (anchor admitted at ratio 1.045 to reference 2026-10-15-dashboard-v1-s26-0180-s7-android, thermal nominal; the payload's own anchor rows at 0.983); text check 0/0 (no run carries one); cpu-capped counted 4/12, past the line 3; FAILURES: none; results/summary rebuilt from the git index (4811 -> 4811 lines)
```

guard の行と前後:

```
[2026-10-19 03:05:44] post: check: PASS 2  HOLD 0  FAIL 0  of 2
[2026-10-19 03:05:57] post: message: results 2026-10-15 Galaxy S26 (SM-S942Q), … (上の全文)
[2026-10-19 03:05:57] post: message guard: no '%' and no standing word (vs, faster, slower, than, beats, leads, outperforms): OK
[2026-10-19 03:05:57] post: would build ~/code/litert-bench-dashboard/build.py into <scratch clone>/logs/dashboard-job/autopilot-page and run its four checks
[2026-10-19 03:05:58] post: red: no red point in this sitting (8 on the page) (dry-run: nothing written)
[2026-10-19 03:06:02] post: exit 0; red: no red point in this sitting (8 on the page) (dry-run: nothing written); dry-run: nothing written
```

`4811 -> 4811 lines`: scratch commit は対の dir だけを外し、HEAD の summary (対の行を含む) は残したので、作り直した summary と同じ行数。red の段の log 行 (`prefill -12.00 % vs …`) は regression_watch の出力で job log にだけ出る (commit message ではない)。

### (e) 時間

- (b) `python3 scripts/session_check.py <116 dirs> --json --markdown -q`: real 10.54 s (user 8.92, sys 1.03)、03:05:25。
- (c) `python3 scripts/session_check.py <69 dirs> --json --markdown -q`: real 6.36 s (user 4.78, sys 0.88)、03:05:36。
- r1: 77 dir 12.3 s。どちらも 3 分の枠の 6 % 以下。

## 監督の追加 (03:0x、SendMessage; user の決定 2026-10-19、監督経由)

- (1) `environment.lock.json` `arms.litert-lm.ios` = `{"tag": "v0.18.0", "since": "2026-10-19", "note": …}` (note は監督の文のまま)。`default_tag` は v0.16.0 のまま。
- (2) `registry_pin()`: platform `ios` の `litert-lm` / `litert-lm-cpu` は `arms.litert-lm.ios` を mac block と同じ `block_applies(block, day)` で読む (mac と ios の分岐を 1 つにした; mac の文言は同じ)。`REGISTERED_LATER` には入れない。
- (3) `newest_litert()` は `LITERT_PIN_BLOCKS = ("mac", "android", "ios")` を列挙 = ios block は自動で入る (確認: 10-19 以降の newest は v0.18.0 のまま、(b) (c) の答えは変わらない)。
- (4) selftest 2 case (上の (a))。(5) docs/session-check-v1.md の engine-stamp 行 (source と reads) と pin-drift 行、docs/dashboard-autopilot-v1.md §11 の iPhone の段。
- 効き方: checker は registry を「sitting の最初の record の時刻以前の最新 commit」で読む。ios block を持つ commit の committer 時刻より前に始まった 10-19 の iPhone sitting は default_tag を読む (v0.18.0 の stamp に engine-stamp HOLD)。fast-forward の merge なら時刻はこの round の commit のまま、rebase で作り直すと新しい時刻になる (提案 3)。

## commit

(経過の最終行に hash)

## 提案

1. **page に既に載っている古い release の cell** (今は iPhone 18 Pro の 10-06..09 の LiteRT-LM 行 = v0.16.0): page の build が bench commit の LOCK / PINS で同じ `newest_litert()` を計算し、cell の newest sitting の stamp がそれより古ければ `cpu-capped` と同じ並びの状態 (例 `release-behind: v0.16.0 < v0.18.0`) で数字を出さないか印を付ける。端末自身の series (regression) には残す。決めるのは page repo。
2. **他の runtime に広げるなら読む物**: llama.cpp = `arms.llama.cpp.tag` と PINS `android_pins.llama.cpp` (今は両方 b8999; side build `engine-build=` は外す)、ONNX Runtime GenAI = Mac の `arms.onnxruntime-genai.mac.packages` と Android の release_zip / AAR の版、ExecuTorch = `arms.executorch.tag`。MLX は revision (commit) で release tag がない = 比べられない (note)。protocol-off を広げるなら llama.cpp の 1K task の `context_tokens` (deviation 5 で llama.cpp は `--context-tokens` を守る) が候補、MLX は強制できない (deviation 5) ので外のまま。
3. **ios block と REGISTERED_LATER**: merge を rebase でやるなら `("litert-lm", "ios")` を `REGISTERED_LATER` に足すと、merge 前に始まった 10-19 の iPhone sitting も v0.18.0 で読める。監督の指定どおり今は入れていない。
4. **LOCK の mac block の note** は「The iPhones stay on default_tag」と書いたまま (10-18 まで正しい)。次に LOCK を触る時に 1 文。
5. **PINS と LOCK の android が違う時の note** の分岐は実データでも selftest でも通っていない (両方 v0.18.0)。次に Android の pin を動かす commit で一度読む。
6. 夜の job の Mac で LiteRT-LM GPU の Gemma 4 E2B cell が 2 回とも初回 SPREAD (下の op の節)。この lane の外。

## 経過

- 02:40 ListAgents (this tab = edge-llm-bench-wt-autopilot-a4 [43e38b], supervisor edge-llm-bench-55 [4f120b] busy); `date` 02:40:03 JST; HEAD 9ab1556e, status clean. Next: read CHECK, POST, the selftests, docs, LOCK, PINS, PROTO.
- 02:41-02:49 read CHECK, its selftest, docs/session-check-v1.md, POST (message, guard spot, post()), its selftest, LOCK `arms.litert-lm`, PINS, PROTO, `build_summary.context_tokens_of`, `dashboard_job.reference_note`, the autopilot doc. Found: the post's anchor phrase is `anchor admitted at ratio <R> vs <reference>` (POST `anchor_text`; ROUND3's real message has it; the post selftest pins it) = the guard as specified holds every attached-phone sitting with a reference. Baseline with the unchanged checker (scratchpad): 116 committed dirs PASS 87 / HOLD 28 / FAIL 1 in 10.67 s (02:45:11-02:45:22); MAIN backlog = 90 untracked lines = 69 dirs (MAIN HEAD f6958509; the 10-19 Mac sitting is running in two of them). Selftests before any change (02:48:23-02:48:54), all exit 0: session_check 39 checks, dashboard_post 48, dashboard_job 89, regression_watch 50, autopilot 58. `~/code/coreai/_GPU_LOCK` empty (no timing window). Next: CHECK (pin-drift, protocol-off, allow-list), then its selftest.
- 02:49-02:54 CHECK: `newest_litert`, `release_of`, `as_count`, `check_pin_drift`, `check_cell_protocol`, FAIL_RULES + NO_ALLOW_RULES, the allow-list refusal, the docstring. Run over the 116 committed dirs (02:52:15-02:52:26): no change at all (PASS 87 / HOLD 28 / FAIL 1; every finding identical to the baseline's). Over the 69 backlog dirs (MAIN paths, 02:53:12-02:53:18): PASS 22 / HOLD 22 / FAIL 25; pin-drift in 14 dirs, protocol-off nowhere. Found: the launch's "FAIL になるべき commit 済み sitting" are all untracked in MAIN; the 10-16 S26 DDP splits are committed without SESSION.json (kind DDP, record rules n/a: 0 new findings). Next: the checker's selftest cases.
- 02:54-03:00 CHECK selftest +8 (iOS cases came later); POST: `STANDING_WORDS`, `hold_message` (no REVIEW.md), the guard's OK line, ACTION rows for the two rules, `anchor_text` "vs" → "to reference"; POST selftest +3; docs (session-check-v1 rows / top / allow-list; autopilot §1, §2, §6, §11). Selftests 02:59:23-02:59:54: 47 / 51 / 89 / 50 / 58, all exit 0; the two changed ones also under python 3.11.13 and 3.12.13 (03:00-03:01). Next: (b) (c) (d) in a cooldown of the night job.
- 03:01:58-03:01:59 scratch clone for (d) (`git clone --shared --no-checkout`, `read-tree HEAD`, the s8a pair `git rm --cached` + one scratch commit there, the pair copied in untracked); `run_bcd.sh` in the background: waits for the night log's `=== cooldown` line, then (b), (c) at normal priority and (d) under `taskpolicy -b`. Table generator written and tried on the 02:5x outputs.
- 03:05:25-03:06:02 (b) (c) (d) ran in the cooldown after the night job's 03:01:25 cell (its retry ended 03:05:21): (b) 116 dirs 10.54 s, (c) the same 69 dirs 6.36 s, (d) exit 0 in 20.44 s. Night job read (records, read only): the Mac's LiteRT-LM Gemma 4 E2B cells tripped SPREAD 32.2 (02:42:42 short chat) and 18.4 (03:01:25 1K) on their first attempts and kept their retries; none of my commands ran during those runs (my runs: 02:45:11-22, 02:48:23-54, 02:52:15-26, 02:53:12-18, 02:59:23-54, 03:00-03:01 before the 03:01:25 cell, 03:01:58-59 after its last run at 03:01:53; the gate lines and the record times are in the night log and the sitting's jsonl). Next: the tables.
- 03:06-03:10 the supervisor's addition arrived (iOS block, user's decision 2026-10-19): LOCK `arms.litert-lm.ios`, `registry_pin()`, selftest 2 cases, docs. The checker and its selftest read the lock from git, so the iOS cases print `skip` in this worktree until the commit; in a scratch clone with the edit committed (`git clone --shared --no-checkout` + `checkout HEAD -- scripts android ops matrices methodology docs environment.lock.json .gitignore`, this round's files copied in, one scratch commit at 03:10:40): selftest OK, 49 checks, 0 skips. (b) re-run with the iOS-aware checker (03:11:3x, in the cooldown after a 03:10:21 MLX cell that failed to load): identical to 03:05. Selftests 03:12:04-03:12:35 (after checking the night log read `=== cooldown`): 47 + 1 skip / 51 / 89 / 50 / 58, all exit 0. Next: ROUND8, the tables into K, the commit.

## 訂正

- launch「起動 2026-10-19 03:0x JST」→ `date` は 02:40:03 (ROUND8 の経過の 1 行目)。
- launch (b)「新規則で FAIL になるべき commit 済み sitting」(10-13 Pixel 8a a、10-14 S26 a / b1 / b2 + anchor、10-15 / 10-17 iPhone 18 Pro + r2 + anchor) → どれも commit されていない: 全部 main tree の untracked (`git ls-files 'results/raw/*/SESSION.json'` に無い; `git -C ~/code/edge-llm-bench status --porcelain results/raw` に有る)。突き合わせは (c) でした。
- launch「r1 は 88、今は増えている」→ `git ls-files 'results/raw/*/SESSION.json'` の dir は今 116、r1 の commit f132add5 の時点で 115 (`git ls-tree -r --name-only f132add5`)。r1 の 88 = その中の -dashboard-v1- job sitting (ROUND1 の訂正 1 行目)。r1 の後に増えた dir は `2026-10-18-dashboard-v1-s26-ddp-m1q-36-android` だけ。
- launch (c)「untracked dir(今 90)」→ 90 は untracked の行数、dir は 69 (`2026-10-11-s26-gallery-vs-binary` が 19 行、`2026-09-17-ddp-litert-lm-caiman-35` が 4 行)。他に ` M` 1 行 (main tree の K/LANE.md)。
- launch 背景「POST の commit_message() … 今の message は通る」→ 通るのは DDP の message (0c82ff22) だけ。attached phone の sitting で anchor に reference と ratio がある時は `anchor admitted at ratio <R> vs <reference>` (POST `anchor_text`; ROUND3 の c258edd8 の message にある; post selftest が pin していた) = 指定の guard で止まる。`ratio <R> to reference <reference>` に変え、selftest と docs/dashboard-autopilot-v1.md §2 も合わせた。
- launch (d)「commit 済みの PASS の対(例 `…-pixel8a-0180-p1{-anchor,}-android`)に `--dry-run`」→ 2 点が成り立たない: p1 の anchor は HOLD reference-uncommitted (参照 `2026-10-13-dashboard-v1-pixel8a-b2-android` は main tree の untracked; ROUND1 の訂正、今回の (b) の表)、かつ commit 済みの dir では POST が message を作る前に「nothing to commit」で返る (POST `post()`: `git diff --cached --quiet` → return 0)。S26 0180 s8a の対 (PASS、reference の s7 は commit 済み) を scratch clone で走らせた。
- launch 背景「long-context-1024-gen256 = context_tokens 2048(android 386 行、ios 163、mac 80 = 全部)」→ HEAD の summary の LiteRT-LM の行は android 276 (全部 2048)、ios 79 (2048 が 63、2523 が 16)、mac 120 (2048 が 40、2523 が 80)。2523 の 96 行は hand run (`2026-08-17-mac-litert-v0160`、`2026-08-19-iphone-litert-v0160`、`2026-09-10-qwen3-gpu-flags-*`、`2026-09-11-minicpm5-2b-crossarm-v0170-mac`)。job sitting の行は全部 2048 (protocol-off 0)。
- launch 背景「native-benchmark-1024x256 = 2048 / 1024 / 256(android 42 …)= 全部」→ LiteRT-LM の android は 45 行、うち 3 行 (`2026-08-17-android-litert-v0160`、hand run) は context なし。
- launch 仕様 1「newest(day) = default_tag、block、PINS の最大」→ PINS は LOCK の android block の since から数えた (仕様の確定 1; selftest の合成 dir と shallow clone は HEAD の registry を読むため)。実データの答えは同じ。
- launch「触ってよい範囲」に LOCK なし → 監督の追加 (03:0x、user の決定) で `environment.lock.json` に `arms.litert-lm.ios` を書いた。note の「installed 2026-10-19」は監督の工程 = この round では未確認。

## 罠と袋小路

- zsh: `git show $c:environment.lock.json` は `$c:e` を拡張子の修飾子と読み `nvironment.lock.json` を探す → `"${c}:environment.lock.json"`。`grep --include=*.py` は glob が先に展開されて「no matches found」→ `--include='*.py'`。
- checker も selftest も LOCK を git から読む (`registry_at` = commit の履歴、selftest は `git show HEAD:environment.lock.json`): working tree の LOCK の編集は commit するまで見えない (iOS の 2 case は `skip`)。commit 前に確かめるには scratch clone に編集を 1 commit してそこで selftest (4.1 MB、`checkout HEAD -- scripts android ops matrices methodology docs environment.lock.json .gitignore`)。
- commit 済みの dir に POST の `--dry-run` を掛けても message は出ない (nothing to commit が先)。`git clone --shared --no-checkout` → `read-tree HEAD` → 対を `rm --cached` → scratch commit → 対を cp、で 20 s。main tree の .git は alternates で読むだけ。
- 夜の job と重ならないように: 数秒を超える物は job log の最終行が `=== cooldown` の時に走らせる (`run_bcd.sh` は待ってから走る作り)。job の gate (SPREAD) の retry は 180 s 後なので、gate の行の直後も避ける。
- `cd` を含む Bash 呼び出しの後は session の cwd が戻される (「Shell cwd was reset」): 絶対 path で書く。
- 監督の追加の文に「同日登録 = REGISTERED_LATER に入れない」とあり、checker は registry を commit の時刻で読む: merge を rebase でやると時刻が新しくなり、それより前に始まった 10-19 の iPhone sitting は ios block を読まない (提案 3)。

## op と delegate の観察

- なし (計測なし; この round は端末にも Mac の engine にも触れていない)。
- 読んだ物だけ (計測ではない): main tree の 10-19 Mac sitting の LiteRT-LM v0.18.0 Gemma 4 E2B GPU cell の record。short chat の初回 4 run の decode 136.2 (cold) / 110.1 / 162.2 / 161.6 tok/s → SPREAD 32.2、retry 134.3 / 160.6 / 161.3 / 160.6 を keep。1K (ctx 2048) の初回 140.3 / 158.4 / 158.4 / 129.2 → SPREAD 18.4、retry 137.2 / 155.9 / 155.9 / 154.1 を keep。低い 1 run の原因は未確認 (その run の間にこの round の command は走っていない: 経過の時刻)。

## 使った環境

- Mac Studio M4 Max (Mac16,9)、macOS 27.0 (26A428)。python 3.14.6 (homebrew; checker、POST、selftest、table 生成)、3.12.13 (homebrew) と 3.11.13 (uv) で変更した selftest 2 本、3.10.13 (pyenv) で py_compile。git 2.54.0 (Apple Git-157)。`taskpolicy -b` (d のみ)。venv なし、package の install なし。
- 端末なし、hold なし、adb / devicectl / gcloud / docker なし、network なし。`~/code/coreai/_GPU_LOCK` は空。夜の job が Mac を 02:00 から計測中 (この round の間ずっと)。
- 書いた所: この worktree (下の commit の path) と session の scratchpad だけ。main tree と P は読むだけ (main tree の `git status` / `log`、job log、10-19 sitting の record と FLAGGED.txt; P は POST の dry run が `build.py` の有無を見ただけ)。

## 残した file

- `K/ROUND8.md` (この file)、`K/committed_check_r8.md` ((b) の 116 行の表と集計)、`K/backlog_table_r8.md` ((c) の 69 行の表と突き合わせ) — commit。
- 変更した code / docs / LOCK: `scripts/session_check.py`、`scripts/session_check_selftest.py`、`scripts/dashboard_post.py`、`scripts/dashboard_post_selftest.py`、`docs/session-check-v1.md`、`docs/dashboard-autopilot-v1.md`、`environment.lock.json` — commit。
- session の scratchpad (git の外): check の JSON / markdown / out (`committed_before|after|r8|r8b`、`backlog_after|r8`、`ddp1016_after`)、selftest の出力、`run_bcd.sh`、`make_tables.py`、`diffcheck.py`、`bcd.status`、`d_dryrun.out` [消してよい]; scratch clone 2 つ `postclone/`、`stclone/` と `posttmp/` [消してよい: round の最後に消す]。
