# Round r10 — text screen sidecar for the Mac and iPhone (text_screen.json → summary text_check → page text-fail) — worker `edge-llm-bench-wt-autopilot-38 [53949d]` (Opus 5.5), started 2026-10-19 03:40 JST

Supervisor: `edge-llm-bench-55 [4f120b]`. cwd ~/code/edge-llm-bench-wt-autopilot, branch bench-autopilot, reset to main 9288dd34 at start (the branch's a73d7c67 was an ancestor of main; `git reset --hard main`). Mac only: no adb, no devicectl, no gcloud, no docker, no build; the night job measures this Mac, the S26 and the iPhone 18 Pro during the round.

## 結果 (要約)

- **CHECK** (`scripts/session_check.py`): Mac / iPhone の text cell (`short-chat`, `long-context-*`) で record に runner の `conditions.textCheck` が無い物は、返事 proxy (`reply-empty` / `reply-loop` / `reply-off-task`) の判定を run ごと (record id) に `<dir>/text_screen.json` へ書く。落ちた cell は note (HOLD にしない)。内容が同じなら触らない。`--no-text-screen` = 何も書かず、書いた時と同じ判定 (note に「not written」)。Android は変えない (sidecar なし、reply-* は HOLD)。
- **SUMMARY** (`scripts/build_summary.py`): `conditions.textCheck` の無い record の `text_check` を同じ campaign dir の sidecar から埋める (`FAIL:<rules>` / `PASS:screen` / 名前の無い run は空)。P の build はそのまま `text-fail:` を出す (P 側の変更なし)。
- **POST** (`scripts/dashboard_post.py`): `--dry-run` は checker に `--no-text-screen`、本番は checker が書いた sidecar を dir ごと commit、message に `text screen: none` / `text screen: <n> cells text-fail (<arm> <model> <task> <k>/<n> runs, …)`。
- (a) selftest 5 本 exit 0: session_check 49 → 60、dashboard_post 51 → 54、dashboard_job 89、regression_watch 50、autopilot 58。test_render_rules OK、android/bench/selftest.py 245 OK、py_compile OK。
- (b) 10-12 の Mac の対 (scratch clone で `.set-aside` を戻す): sidecar = payload 39 cell のうち FAIL 2 (llama.cpp Gemma 4 E4B GGUF 1K: reply-empty + reply-off-task 4/4、MLX Gemma 4 E4B OptiQ 1K: reply-off-task 4/4)、他 37 と anchor の 2 cell は PASS。summary: その 8 run が `FAIL:…`、対の他の screen 済み 153 run が `PASS:screen`、対の外の行は全部 byte 同一。P の cells.csv: Mac16,9 のその 2 cell が `text-fail:text check failed: … (4 of 4 runs)`、decode なし (前は 2026-10-06 の 87.13 / 92.29 tok/s が数字で出ていた)。他の変化は Mac16,9 の 34 cell の `text_checked_n` 0 → 3/4 だけ。P の check: against_bench_dashboard PASS / check_regression FAIL (2) / check_aa PASS — regression の 2 件は S26 の lab-unit stand-in の 2 cell で、main 9288dd34 の bench でも同じ 2 件 (r10 と無関係、提案 7)。
- (c) commit 済み 118 dir (`--no-text-screen`、何も書かない): PASS 89 → 90 / HOLD 28 → 27 / FAIL 1 → 1。verdict が変わったのは `2026-10-06-dashboard-v1-m4max-longctx1024-mac` (HOLD → PASS、live finding が reply-* 3 件だけ) の 1 dir。他の規則の finding は全 dir・全件で不変。
- (d) POST の dry run (10-12 の対を HEAD から外した clone): exit 0、message に `text screen: 2 cells text-fail (…)`、`%` も順位の語も無し、guard の OK 行、sidecar は書かれていない。
- (e) (c) 118 dir 11.60 s (変更前 11.29 s)。
- 監督の知らせ (main に 0b38a1f2: Mac の LiteRT-LM pin を v0.16.0 に戻した) の後、main 0b38a1f2 + この branch の merge で手順を回し直した: 対は HOLD / HOLD (`engine-stamp` だけ、監督の書いたとおり)、sidecar・summary・P の cells.csv は byte 同一。**main@0b38a1f2 では session_check_selftest が r10 の前から落ちる** (Mac の合成 sitting の LiteRT-LM cell が pin-drift、10 FAIL の後 l.307 で TypeError)。r10 の text screen の case は LiteRT-LM の pin を読まない形 (llama.cpp cell) にして、l.307 は例外でなく FAIL を数える形にした (15b7866e)。merge 後に残る 11 FAIL は既存の generic case (直し方は監督の判断: 提案 1)。

## 下見

- `date` 03:40:20 JST。HEAD a73d7c67 (main 9288dd34 の祖先、tree clean) → `git reset --hard main` で 9288dd34。
- selftest (変更前、全部 exit 0): `session_check_selftest.py` 49、`dashboard_post_selftest.py` 51、`dashboard_job_selftest.py` 89、`regression_watch_selftest.py` 50、`autopilot_selftest.py` 58 (`BENCH_ANDROID_BIN_DIR=~/code/edge-llm-bench/android/bin`)、`test_render_rules.py` OK。hook は軽い python を止めなかった (`QUIET_OK` 不要)。
- 変更前の checker: commit 済み 118 dir (`git ls-files 'results/raw/*/SESSION.json'`; r8 の 116 + 8ac9b8bb の 10-12 の対) PASS 89 / HOLD 28 / FAIL 1、11.29 s。
- データ: 対象になる record (Mac / iPhone の text task、runner の textCheck なし) は commit 済みで 714 本 (mac 575、ios 139)、全部に `id`。同じ cell key で context か quantization が混ざる cell は 0 → cell key + record id で run を指せる (停止条件「cell key が作れない形」に当たらない)。
- Apple の summary 行で `text_check` が既にあるのは Mac の executorch-mlx 56、executorch-xnnpack 56、onnxruntime-genai-cpu 24、onnxruntime-genai-webgpu 25 (その runner の check)。その record の cell は screen しない (cell に 1 本でも textCheck があれば runner の判定)。

## 仕様の確定

### `text_screen.json` (schema `text-screen.v1`)

```json
{"schema": "text-screen.v1",
 "written_at": "2026-10-19T04:22:2x+09:00",
 "written_by": "scripts/session_check.py 77a3fdd0",
 "about": "scripts/session_check.py's text screen of this dir's Mac / iPhone text cells without a runner text check: …",
 "rules": ["reply-empty", "reply-loop", "reply-off-task"],
 "cells": {"<runtime> <model id> <task> (<engineVersion>)": {
     "verdict": "FAIL", "rules": ["reply-off-task"], "runs": 4, "runs_off": 4,
     "detail": "4 of 4 replies name none of the prompt's subject terms (sample: '…')",
     "sample": "<the first non-empty reply, 160 chars>",
     "run_rules": {"<record id>": ["reply-off-task"], "…": []}}}}
```

- **cell key** = `build_summary.cell_key_of` = `session_check.cell_of` (定義は 1 つ、2 本が import)。`run_rules` は screen した run を全部 record id で名指す (`[]` = 通った)。`verdict` は 1 本でも off なら FAIL (前の HOLD と同じ引き金)、`runs_off` がその本数。
- **note の文**: pool に入る run (firstEver 以外) が全部 off → `screened text-fail: <cell> (<rules>): the page shows the cell as text-fail`。一部 → `…: <k> of <n> runs, which the page leaves out of the cell's number`。書かなかった時 (`--no-text-screen`) は末尾に ` (text_screen.json not written: --no-text-screen)`。
- **summary の値**: record の textCheck が先 (Android と、runner の check を持つ Mac の arm はそのまま)。無ければ sidecar の cell → record id で `FAIL:<rules>` / `PASS:screen`、名前が無ければ空。
- **message の句**: screen した cell がある sitting だけに `; text screen: none` か `; text screen: <n> cells text-fail (<arm> <model> <task> <k>/<n> runs, …)` (`text check …` の後)。anchor と payload の同じ cell は 1 つにまとめる。Android の sitting には句を付けない (runner の `text check k/N` がある)。

### launch に無かった事の決め (根拠)

1. **判定は run ごと** (launch の schema は cell ごとの verdict だけ): fairness-rules §12 の単位は run (「A run whose decoded text fails the text check is not a measurement」)、`render_leaderboard.arm_row` は FAIL の run を pool から外し、cell が text-fail になるのは pool が空になった時だけ、Android の runner も iteration ごとに `textCheck` を書く (`android/bench/run_cell.py`)。cell 単位で全 run を FAIL にすると 4 本中 1 本の空返事で数字が消え、Android と別の規則になる。→ launch の field はそのまま、cell に `run_rules` を足した。
2. **既定は書く、`--no-text-screen` は書かずに同じ判定**: launch の「既定 on?」に on と答えた。PASS = 「そのまま commit してよい」が既定の実行で成り立つ (PASS と出た時には file が dir にある)。POST の dry-run と (c) は「書いたらどうなるか」の判定が要る。他の checkout の dir (MAIN の backlog など) を見る時は `--no-text-screen` (docs に書いた)。
3. **HOLD に残す時**: file を書けない (OSError) か、落ちた run に record id が無い → その cell は reply-* finding のまま (file がその run を運ばない = page に印が付かない)。
4. **書く dir**: checker が record の規則を読む job の kind (anchor / payload)。DDP は Android なので書かない。hand run / dev / stopped には書かない。
5. **「内容が同じ」**: `schema`, `about`, `rules`, `cells` を比べる (`written_at` / `written_by` だけの違いでは書き直さず mtime も動かない)。screen する cell が無くなった dir の自分の file (schema `text-screen.v1`) は消す。
6. **allow-list の reply-* 行**: Mac / iPhone の cell には当たる finding が無くなる。e3010721 の行は Android の v0.18.0 sitting にだけ効き続ける (docs に 1 文)。
7. **results/summary/README.md**: launch の 2 文は SUMMARY が書く README の段 → CI の summary-fresh が commit と作り直しを比べるので、index から作り直した README を同じ commit に入れた (device-runs.csv は byte 同一: commit 済みの sidecar はまだ無い)。

## 結果

### (a) selftest (この worktree、04:06-04:08)

| selftest | 変更前 | 変更後 | 増減 |
|---|---|---|---|
| `scripts/session_check_selftest.py` | 49 | 60 | +15 (text screen: sidecar の中身、note と PASS、触らない再実行、allow-list 行が当たらない、`--no-text-screen` で書かない・would rewrite・書き直し、1/4 の cell、書けない dir と id の無い run は HOLD、summary の読み 3、iPhone、Android lab unit の off-task は HOLD のまま); −4 (Mac の reply-off-task / reply-loop の HOLD 2 case: note に変わった) |
| `scripts/dashboard_post_selftest.py` | 51 | 54 | +3 (off-task の cell を持つ sitting: dry-run は書かず句を出す、commit に両 dir の sidecar、message の句); 既存の (ii) の文に `text screen: none`、dry-run と (i) に sidecar の確認 |
| `scripts/dashboard_job_selftest.py` | 89 | 89 | 0 |
| `scripts/regression_watch_selftest.py` | 50 | 50 | 0 |
| `scripts/autopilot_selftest.py` | 58 | 58 | 0 |
| `scripts/test_render_rules.py` | OK | OK | 0 (summary の `text_check` 列の 3 値の test はそのまま通る) |
| `android/bench/selftest.py` | — | 245 ok, selftest OK (101 s) | 0 (`build_summary.build_device` を patch した root で回す case が通る) |
| `python3 -m py_compile scripts/*.py android/bench/*.py android/ddp/*.py` | — | OK | |

全部 exit 0。CI (`.github/workflows/data-pipeline.yml`) は変更なし: selftest の step が `session_check_selftest.py` / `dashboard_post_selftest.py` をそのまま回すので増えた case が乗る。summary-fresh は作り直した README を commit したので通る。

main 0b38a1f2 + この branch の merge (scratch clone、04:22): session_check 47 ok / 11 FAIL / 1 skip (FAIL は全部 r10 前からの generic case、r10 の 15 は通る)、post 54 / job 89 / regression 50 / autopilot 58 は exit 0。main 0b38a1f2 そのもの (r10 なし) は session_check が 10 FAIL の後 l.307 の TypeError で止まる (提案 1)。

### (b) 10-12 の Mac の対 (scratch clone、下の「適用手順」をそのまま)

2 回回した: ① この branch の clone (= main 9288dd34 + 77a3fdd0、04:10-04:12) ② main 0b38a1f2 の clone にこの branch を merge (04:22)。sidecar・summary・P の cells.csv は ① と ② で同じ (`written_at` 以外 byte 同一)。違いは checker の verdict だけ: ① PASS / PASS、② HOLD / HOLD (`engine-stamp`: `mac litert-lm: stamps v0.18.0 x3` (anchor) / `x40` (payload); `registry v0.16.0 (environment.lock.json arms.litert-lm.mac.tag (since 2026-09-18, registered at 0b38a1f2)`) = 0b38a1f2 による、r10 と無関係。どちらも failures の 12 行は c7b60c2b の行で許可 (8ac9b8bb の行を消した後も)。

**sidecar** (②):

`2026-10-12-dashboard-v1-m4max-anchor-mac/text_screen.json` (2 cells; written_by `scripts/session_check.py 77a3fdd0`):

| cell | verdict | rules | runs | runs_off |
|---|---|---|---|---|
| `litert-lm litert-community/Qwen3-0.6B short-chat (v0.18.0)` | PASS | — | 3 | 0 |
| `mlx-swift mlx-community/Qwen3-0.6B-4bit short-chat (60bd0d7880c82980f9481f8be78862e9b63c58a3)` | PASS | — | 3 | 0 |

`2026-10-12-dashboard-v1-m4max-mac/text_screen.json` (39 cells; written_by `scripts/session_check.py 77a3fdd0`):

| cell | verdict | rules | runs | runs_off |
|---|---|---|---|---|
| `core-ai core-ai/qwen3-0.6b-4bit-gpu short-chat (0.2.0+static-inputs-patch)` | PASS | — | 4 | 0 |
| `core-ai core-ai/qwen3-1.7b-gpu short-chat (0.2.0+static-inputs-patch)` | PASS | — | 4 | 0 |
| `core-ai core-ai/qwen3-4b-gpu short-chat (0.2.0+static-inputs-patch)` | PASS | — | 4 | 0 |
| `litert-lm litert-community/Qwen3-0.6B long-context-1024-gen256 (v0.18.0)` | PASS | — | 4 | 0 |
| `litert-lm litert-community/Qwen3-0.6B short-chat (v0.18.0)` | PASS | — | 4 | 0 |
| `litert-lm litert-community/Qwen3-1.7B long-context-1024-gen256 (v0.18.0)` | PASS | — | 4 | 0 |
| `litert-lm litert-community/Qwen3-1.7B short-chat (v0.18.0)` | PASS | — | 4 | 0 |
| `litert-lm litert-community/Qwen3-4B long-context-1024-gen256 (v0.18.0)` | PASS | — | 4 | 0 |
| `litert-lm litert-community/Qwen3-4B short-chat (v0.18.0)` | PASS | — | 4 | 0 |
| `litert-lm litert-community/gemma-4-E2B-it-litert-lm long-context-1024-gen256 (v0.18.0)` | PASS | — | 4 | 0 |
| `litert-lm litert-community/gemma-4-E2B-it-litert-lm short-chat (v0.18.0)` | PASS | — | 4 | 0 |
| `litert-lm litert-community/gemma-4-E4B-it-litert-lm long-context-1024-gen256 (v0.18.0)` | PASS | — | 4 | 0 |
| `litert-lm litert-community/gemma-4-E4B-it-litert-lm short-chat (v0.18.0)` | PASS | — | 4 | 0 |
| `llama.cpp unsloth/Qwen3-0.6B-GGUF/Q4_K_M long-context-1024-gen256 (b8999)` | PASS | — | 4 | 0 |
| `llama.cpp unsloth/Qwen3-0.6B-GGUF/Q4_K_M short-chat (b8999)` | PASS | — | 4 | 0 |
| `llama.cpp unsloth/Qwen3-1.7B-GGUF/Q4_K_M long-context-1024-gen256 (b8999)` | PASS | — | 4 | 0 |
| `llama.cpp unsloth/Qwen3-1.7B-GGUF/Q4_K_M short-chat (b8999)` | PASS | — | 4 | 0 |
| `llama.cpp unsloth/Qwen3-4B-GGUF/Q4_K_M long-context-1024-gen256 (b8999)` | PASS | — | 4 | 0 |
| `llama.cpp unsloth/Qwen3-4B-GGUF/Q4_K_M short-chat (b8999)` | PASS | — | 4 | 0 |
| `llama.cpp unsloth/gemma-4-E2B-it-GGUF/Q4_K_M long-context-1024-gen256 (b8999)` | PASS | — | 4 | 0 |
| `llama.cpp unsloth/gemma-4-E2B-it-GGUF/Q4_K_M short-chat (b8999)` | PASS | — | 4 | 0 |
| `llama.cpp unsloth/gemma-4-E4B-it-GGUF/Q4_K_M long-context-1024-gen256 (b8999)` | **FAIL** | reply-empty, reply-off-task | 4 | 4 |
| `llama.cpp unsloth/gemma-4-E4B-it-GGUF/Q4_K_M short-chat (b8999)` | PASS | — | 4 | 0 |
| `mlx-swift mlx-community/Qwen3-0.6B-4bit long-context-1024-gen256 (60bd0d7880c82980f9481f8be78862e9b63c58a3)` | PASS | — | 4 | 0 |
| `mlx-swift mlx-community/Qwen3-0.6B-4bit short-chat (60bd0d7880c82980f9481f8be78862e9b63c58a3)` | PASS | — | 3 | 0 |
| `mlx-swift mlx-community/Qwen3-1.7B-4bit long-context-1024-gen256 (60bd0d7880c82980f9481f8be78862e9b63c58a3)` | PASS | — | 4 | 0 |
| `mlx-swift mlx-community/Qwen3-1.7B-4bit short-chat (60bd0d7880c82980f9481f8be78862e9b63c58a3)` | PASS | — | 4 | 0 |
| `mlx-swift mlx-community/Qwen3-4B-4bit long-context-1024-gen256 (60bd0d7880c82980f9481f8be78862e9b63c58a3)` | PASS | — | 4 | 0 |
| `mlx-swift mlx-community/Qwen3-4B-4bit short-chat (60bd0d7880c82980f9481f8be78862e9b63c58a3)` | PASS | — | 4 | 0 |
| `mlx-swift mlx-community/gemma-4-e2b-it-qat-OptiQ-4bit long-context-1024-gen256 (60bd0d7880c82980f9481f8be78862e9b63c58a3)` | PASS | — | 4 | 0 |
| `mlx-swift mlx-community/gemma-4-e2b-it-qat-OptiQ-4bit short-chat (60bd0d7880c82980f9481f8be78862e9b63c58a3)` | PASS | — | 4 | 0 |
| `mlx-swift mlx-community/gemma-4-e4b-it-qat-OptiQ-4bit long-context-1024-gen256 (60bd0d7880c82980f9481f8be78862e9b63c58a3)` | **FAIL** | reply-off-task | 4 | 4 |
| `mlx-swift mlx-community/gemma-4-e4b-it-qat-OptiQ-4bit short-chat (60bd0d7880c82980f9481f8be78862e9b63c58a3)` | PASS | — | 4 | 0 |
| `onnxruntime-genai-cpu onnx-community/Qwen3-0.6B-ONNX short-chat (onnxruntime-genai 0.17.1 + onnxruntime 1.30.0)` | PASS | — | 4 | 0 |
| `onnxruntime-genai-cpu onnx-community/Qwen3-1.7B-ONNX short-chat (onnxruntime-genai 0.17.1 + onnxruntime 1.30.0)` | PASS | — | 4 | 0 |
| `onnxruntime-genai-cpu onnx-community/Qwen3-4B-ONNX short-chat (onnxruntime-genai 0.17.1 + onnxruntime 1.30.0)` | PASS | — | 4 | 0 |
| `onnxruntime-genai-webgpu onnx-community/Qwen3-0.6B-ONNX short-chat (onnxruntime-genai 0.17.1 + onnxruntime 1.30.0 + onnxruntime-ep-webgpu 0.4.0)` | PASS | — | 4 | 0 |
| `onnxruntime-genai-webgpu onnx-community/Qwen3-1.7B-ONNX short-chat (onnxruntime-genai 0.17.1 + onnxruntime 1.30.0 + onnxruntime-ep-webgpu 0.4.0)` | PASS | — | 4 | 0 |
| `onnxruntime-genai-webgpu onnx-community/Qwen3-4B-ONNX short-chat (onnxruntime-genai 0.17.1 + onnxruntime 1.30.0 + onnxruntime-ep-webgpu 0.4.0)` | PASS | — | 4 | 0 |

<details><summary>anchor の text_screen.json 全文</summary>

```json
{
 "schema": "text-screen.v1",
 "written_at": "2026-10-19T04:22:04+09:00",
 "written_by": "scripts/session_check.py 77a3fdd0",
 "about": "scripts/session_check.py's text screen of this dir's Mac / iPhone text cells without a runner text check: the reply proxies per run (run_rules, by record id; [] = passed), read by scripts/build_summary.py into results/summary text_check (docs/session-check-v1.md)",
 "rules": [
  "reply-empty",
  "reply-loop",
  "reply-off-task"
 ],
 "cells": {
  "litert-lm litert-community/Qwen3-0.6B short-chat (v0.18.0)": {
   "verdict": "PASS",
   "rules": [],
   "runs": 3,
   "runs_off": 0,
   "detail": "3 of 3 replies pass the screen",
   "sample": "<think> Okay, the user wants an explanation of on-device AI in simple terms. Let me start by recalling what on-device AI is. From what I remember, it's a type …",
   "run_rules": {
    "187D6F48-E8ED-4C99-A5EA-C9637ACDB0BE": [],
    "6DE94D2A-B09F-422C-A3E3-A9F96735D257": [],
    "FADB1A88-1F7B-4405-819D-4211DED53FD1": []
   }
  },
  "mlx-swift mlx-community/Qwen3-0.6B-4bit short-chat (60bd0d7880c82980f9481f8be78862e9b63c58a3)": {
   "verdict": "PASS",
   "rules": [],
   "runs": 3,
   "runs_off": 0,
   "detail": "3 of 3 replies pass the screen",
   "sample": "<think> Okay, the user is asking for an explanation of on-device AI in simple terms. Let me start by breaking down what on-device AI refers to. From what I rem…",
   "run_rules": {
    "2DD68E48-C88C-4F00-A801-A7702E74B188": [],
    "41D0D350-3620-4AD2-8E10-FC95D5E6AF90": [],
    "60C1CD44-0E1F-48B6-9AB2-D6BC5AC22925": []
   }
  }
 }
}
```

</details>

<details><summary>payload の text_screen.json 全文</summary>

```json
{
 "schema": "text-screen.v1",
 "written_at": "2026-10-19T04:22:04+09:00",
 "written_by": "scripts/session_check.py 77a3fdd0",
 "about": "scripts/session_check.py's text screen of this dir's Mac / iPhone text cells without a runner text check: the reply proxies per run (run_rules, by record id; [] = passed), read by scripts/build_summary.py into results/summary text_check (docs/session-check-v1.md)",
 "rules": [
  "reply-empty",
  "reply-loop",
  "reply-off-task"
 ],
 "cells": {
  "core-ai core-ai/qwen3-0.6b-4bit-gpu short-chat (0.2.0+static-inputs-patch)": {
   "verdict": "PASS",
   "rules": [],
   "runs": 4,
   "runs_off": 0,
   "detail": "4 of 4 replies pass the screen",
   "sample": "<think> Okay, the user wants to understand on-device AI in simple terms. Let me start by breaking down what on-device AI is. From what I remember, AI is a big …",
   "run_rules": {
    "495C0658-E544-42F8-8193-37FD2D8ABFAB": [],
    "717261EF-0F30-4317-B872-5D26B77037AC": [],
    "C877FEF2-C8F0-49D9-AAFB-C68607AFC824": [],
    "D0987690-373E-4356-93DB-5503A6C77635": []
   }
  },
  "core-ai core-ai/qwen3-1.7b-gpu short-chat (0.2.0+static-inputs-patch)": {
   "verdict": "PASS",
   "rules": [],
   "runs": 4,
   "runs_off": 0,
   "detail": "4 of 4 replies pass the screen",
   "sample": "<think> Okay, the user is asking for an explanation of what on-device AI means in simple terms. Let me start by recalling what on-device AI is. I know that AI …",
   "run_rules": {
    "1187C310-4491-4EB1-9442-CCEEBDDD7EAE": [],
    "5A966481-5B91-4D5E-9F15-F432466F3863": [],
    "6BC862CA-48E8-4074-8144-C1296766334D": [],
    "B8C45BE2-4057-428A-B3F3-3ED8DCA54563": []
   }
  },
  "core-ai core-ai/qwen3-4b-gpu short-chat (0.2.0+static-inputs-patch)": {
   "verdict": "PASS",
   "rules": [],
   "runs": 4,
   "runs_off": 0,
   "detail": "4 of 4 replies pass the screen",
   "sample": "<think> Okay, the user is asking for an explanation of \"on-device AI\" in simple terms. Let me start by recalling what I know about on-device AI. From what I re…",
   "run_rules": {
    "0D3130E1-8778-4C18-BFE8-2B57AA3EECF3": [],
    "CB244642-DD5B-4532-A0F1-D7273A164B26": [],
    "D0E02B5E-EC58-4651-B7DA-B1309A201A9C": [],
    "FFA39205-F893-4991-8587-9C2A66DDED61": []
   }
  },
  "litert-lm litert-community/Qwen3-0.6B long-context-1024-gen256 (v0.18.0)": {
   "verdict": "PASS",
   "rules": [],
   "runs": 4,
   "runs_off": 0,
   "detail": "4 of 4 replies pass the screen",
   "sample": "<think> Okay, let's tackle this. The user wants me to list 25 distinct things that a phone can do using-device AI, comparing them to what a cloud model can do.…",
   "run_rules": {
    "1832A55D-1130-4994-BED2-03B1583E49A5": [],
    "2929D1D0-C261-4F66-9D15-1B22F1E555D6": [],
    "921362D4-AA66-4C38-B094-DB82AD4FDBA4": [],
    "BBE8037F-3F2B-4597-BE1C-B8B18B282D1B": []
   }
  },
  "litert-lm litert-community/Qwen3-0.6B short-chat (v0.18.0)": {
   "verdict": "PASS",
   "rules": [],
   "runs": 4,
   "runs_off": 0,
   "detail": "4 of 4 replies pass the screen",
   "sample": "<think> Okay, the user wants an explanation of on-device AI in simple terms. Let me start by recalling what on-device AI is. From what I remember, it's a type …",
   "run_rules": {
    "0A99331E-3B67-4EFF-89BF-810A9138E05E": [],
    "652DB840-8A79-4113-A920-E617678068C9": [],
    "98B3EBC5-64A3-4DC8-9556-3F38BC996A26": [],
    "ACE5D712-B4FC-4C4E-9D46-C2EFE041CB47": []
   }
  },
  "litert-lm litert-community/Qwen3-1.7B long-context-1024-gen256 (v0.18.0)": {
   "verdict": "PASS",
   "rules": [],
   "runs": 4,
   "runs_off": 0,
   "detail": "4 of 4 replies pass the screen",
   "sample": "Okay, the user wants me to list 25 distinct things that on-device AI lets a phone do that a cloud model can't. And each item needs two full sentences explainin…",
   "run_rules": {
    "52579D24-239A-4A12-9A91-3470D55D68C5": [],
    "619CCAB0-042C-401C-A65A-1A1B149CC7CD": [],
    "8B3B76B1-8B40-4987-A160-E77C4B17CF61": [],
    "A87870B3-C8FD-4459-B99D-08E80B63E763": []
   }
  },
  "litert-lm litert-community/Qwen3-1.7B short-chat (v0.18.0)": {
   "verdict": "PASS",
   "rules": [],
   "runs": 4,
   "runs_off": 0,
   "detail": "4 of 4 replies pass the screen",
   "sample": "Okay, the user is asking for a simple explanation of what on-device AI means. Let me start by recalling what on-device AI is. I know that AI refers to machines…",
   "run_rules": {
    "BB8BC370-4F9B-4DC0-B42F-7FCC9A144531": [],
    "C55AFC4F-F0FD-4051-B0DC-31A752CDEAAC": [],
    "C6B83674-A716-4214-8DA3-E37A4AA567F2": [],
    "D3EF353D-266D-4119-9095-E3BDA091EC69": []
   }
  },
  "litert-lm litert-community/Qwen3-4B long-context-1024-gen256 (v0.18.0)": {
   "verdict": "PASS",
   "rules": [],
   "runs": 4,
   "runs_off": 0,
   "detail": "4 of 4 replies pass the screen",
   "sample": "<think> Okay, the user wants me to list 25 distinct things that on-device AI on a phone can do that a cloud model can't. Let me start by recalling what I know …",
   "run_rules": {
    "8A0D887C-314D-4C35-85D9-6E00D0C684C0": [],
    "AEF4E71E-0441-4DCE-AE47-147DC1D280E5": [],
    "BDECCFF7-F040-4C66-A39F-8966FADFCDE5": [],
    "DCFCF19B-9C2F-4866-BA52-8662B57E6B43": []
   }
  },
  "litert-lm litert-community/Qwen3-4B short-chat (v0.18.0)": {
   "verdict": "PASS",
   "rules": [],
   "runs": 4,
   "runs_off": 0,
   "detail": "4 of 4 replies pass the screen",
   "sample": "<think> Okay, the user is asking for an explanation of on-device AI in simple terms. Let me start by recalling what on-device AI is. From what I know, it's whe…",
   "run_rules": {
    "0D406A89-8955-459F-A48F-3EE7EA37B05F": [],
    "15E326D2-6229-473A-801F-3BDF4D1F984E": [],
    "77AB800B-1AC0-4384-B357-2BC236025D4F": [],
    "FD2C5B62-0D53-48C9-B8FC-39CA4DFB968E": []
   }
  },
  "litert-lm litert-community/gemma-4-E2B-it-litert-lm long-context-1024-gen256 (v0.18.0)": {
   "verdict": "PASS",
   "rules": [],
   "runs": 4,
   "runs_off": 0,
   "detail": "4 of 4 replies pass the screen",
   "sample": "The provided text is placeholder \"Lorem ipsum\" text and does not contain any information about on-device AI versus cloud models. Therefore, I cannot answer you…",
   "run_rules": {
    "68EF1CDD-29A6-45A7-88E4-2118B8517859": [],
    "BCBD6DB8-C616-4BE0-8AC0-782BC2F29CBB": [],
    "C52D8A25-0ACE-4A12-9655-5B448815DD1D": [],
    "C7335B08-829C-489F-B06E-9FEE2AB55532": []
   }
  },
  "litert-lm litert-community/gemma-4-E2B-it-litert-lm short-chat (v0.18.0)": {
   "verdict": "PASS",
   "rules": [],
   "runs": 4,
   "runs_off": 0,
   "detail": "4 of 4 replies pass the screen",
   "sample": "Imagine a computer or a device (like your smartphone, a smart watch, or a camera) having a little bit of **smart thinking built right into itself**, instead of…",
   "run_rules": {
    "40CD5A8B-E13C-46A2-BAC7-23AFDC1AA63B": [],
    "47C7BCA8-743B-4BF8-8B47-BCB091777544": [],
    "5BE0908A-A3A6-4C23-805A-22B8E9BA4981": [],
    "BD268829-0BAB-471B-806D-71FDFF96990D": []
   }
  },
  "litert-lm litert-community/gemma-4-E4B-it-litert-lm long-context-1024-gen256 (v0.18.0)": {
   "verdict": "PASS",
   "rules": [],
   "runs": 4,
   "runs_off": 0,
   "detail": "4 of 4 replies pass the screen",
   "sample": "I cannot fulfill this request because the provided text is a repetitive block of \"Lorem ipsum\" placeholder text. It contains no information about on-device AI,…",
   "run_rules": {
    "06ECEA91-CA49-4E32-B8C1-030084F9F850": [],
    "80E3D93B-4EE1-48EA-8A8A-7CE58A58446B": [],
    "C0ABCA33-48AA-4C43-9BB5-416F4932AC9B": [],
    "DE3546E9-F13C-4B6D-9A1C-A25E3C1EC0B9": []
   }
  },
  "litert-lm litert-community/gemma-4-E4B-it-litert-lm short-chat (v0.18.0)": {
   "verdict": "PASS",
   "rules": [],
   "runs": 4,
   "runs_off": 0,
   "detail": "4 of 4 replies pass the screen",
   "sample": "Imagine you have a smart device, like your smartphone or a smart speaker. **On-device AI** simply means that the \"brain\" (the Artificial Intelligence) that mak…",
   "run_rules": {
    "6B3F4DF6-CF39-4BA8-8501-B379892CCC20": [],
    "9BFC95C8-4749-471F-A681-DBD9BCEBF201": [],
    "BC6F50D7-D998-4109-9C40-3E6A22714AB5": [],
    "C2E4F1A9-D8CA-435F-BDF5-C436D9A10F05": []
   }
  },
  "llama.cpp unsloth/Qwen3-0.6B-GGUF/Q4_K_M long-context-1024-gen256 (b8999)": {
   "verdict": "PASS",
   "rules": [],
   "runs": 4,
   "runs_off": 0,
   "detail": "4 of 4 replies pass the screen",
   "sample": "<think> Okay, let's tackle this query. The user provided a list of 17 passages, each starting with \"Lorem ipsum...\" and repeating the same content. They want m…",
   "run_rules": {
    "0F005627-C548-47E0-BEDB-2B0F03648801": [],
    "13349BB7-92F6-4D28-A609-4FAAB8F5C3EF": [],
    "8BB4ABF4-68F4-4F09-93CD-969F01A60134": [],
    "C7F7C12B-2D78-41C8-BE67-2D664955FADF": []
   }
  },
  "llama.cpp unsloth/Qwen3-0.6B-GGUF/Q4_K_M short-chat (b8999)": {
   "verdict": "PASS",
   "rules": [],
   "runs": 4,
   "runs_off": 0,
   "detail": "4 of 4 replies pass the screen",
   "sample": "<think> Okay, the user is asking for an explanation of on-device AI in simple terms. Let me start by recalling what on-device AI refers to. From what I remembe…",
   "run_rules": {
    "3EC8F772-D949-4756-ADF5-1FC97B2DC9F8": [],
    "A9C59AD8-54DC-4922-859D-F28B7C30877F": [],
    "BB3B8DB7-ECC7-46FC-833E-F631303E13F6": [],
    "F2EA1D75-F3F4-475A-AA85-F93985217310": []
   }
  },
  "llama.cpp unsloth/Qwen3-1.7B-GGUF/Q4_K_M long-context-1024-gen256 (b8999)": {
   "verdict": "PASS",
   "rules": [],
   "runs": 4,
   "runs_off": 0,
   "detail": "4 of 4 replies pass the screen",
   "sample": "<think> Okay, the user wants me to list 25 distinct things that on-device AI can do that a cloud model can't. Each item needs two full sentences explaining why…",
   "run_rules": {
    "60CCE970-088F-4DE7-B287-A479CD349935": [],
    "93B9ECD2-D3AC-4FF4-A049-EF026B4F11F8": [],
    "C739DCA4-3272-4807-93F0-AB1767B9FBF3": [],
    "EF95656E-25A7-4922-BCD3-A9ACA48AE329": []
   }
  },
  "llama.cpp unsloth/Qwen3-1.7B-GGUF/Q4_K_M short-chat (b8999)": {
   "verdict": "PASS",
   "rules": [],
   "runs": 4,
   "runs_off": 0,
   "detail": "4 of 4 replies pass the screen",
   "sample": "<think> Okay, the user wants to know what on-device AI means in simple terms. Let me start by breaking down the key components. On-device AI refers to AI model…",
   "run_rules": {
    "44F5E318-98D1-48F1-8F92-2811860A9B84": [],
    "831FAA03-C7E9-4E0E-BEB3-A0AF2B7AB7F2": [],
    "D7EE014C-9586-493C-B915-6574DE6C0B8B": [],
    "D90C12B6-399B-4B6D-BBDD-72B4AC56631D": []
   }
  },
  "llama.cpp unsloth/Qwen3-4B-GGUF/Q4_K_M long-context-1024-gen256 (b8999)": {
   "verdict": "PASS",
   "rules": [],
   "runs": 4,
   "runs_off": 0,
   "detail": "4 of 4 replies pass the screen",
   "sample": "<think> Okay, the user wants me to list 25 distinct things that on-device AI can do on a phone that a cloud model can't. Let me start by recalling what on-devi…",
   "run_rules": {
    "3EDF33A5-B855-464A-A8F5-C18433B6BD12": [],
    "61D384BF-BFC5-4A95-B141-68DA7969D89A": [],
    "626333C7-F05A-4D86-920C-86DE2DC9B466": [],
    "62C7A953-8704-4016-855F-387E178749DC": []
   }
  },
  "llama.cpp unsloth/Qwen3-4B-GGUF/Q4_K_M short-chat (b8999)": {
   "verdict": "PASS",
   "rules": [],
   "runs": 4,
   "runs_off": 0,
   "detail": "4 of 4 replies pass the screen",
   "sample": "<think> Okay, the user is asking me to explain what on-device AI means in simple terms. Let me start by recalling what I know about on-device AI. From what I r…",
   "run_rules": {
    "5293C36D-D72F-457E-96AB-BBB3EDF123B0": [],
    "65A19ABA-64AF-4FA8-B2E2-C2A142EE7725": [],
    "8909E65B-46DD-4FFA-B5BE-E56819CC6757": [],
    "C586898E-DB9F-40BC-A879-E12FED6FB2DC": []
   }
  },
  "llama.cpp unsloth/gemma-4-E2B-it-GGUF/Q4_K_M long-context-1024-gen256 (b8999)": {
   "verdict": "PASS",
   "rules": [],
   "runs": 4,
   "runs_off": 0,
   "detail": "4 of 4 replies pass the screen",
   "sample": "1. **On-Device Image Recognition for real-time object identification.** This capability allows the phone to instantly identify objects in the camera feed witho…",
   "run_rules": {
    "0E8C323E-F5E1-45AD-BA21-9F73926A622D": [],
    "4DC2EBEF-4DDC-4303-AC20-31F8249D7CB9": [],
    "6CB38C21-072D-438D-9E0E-02FBF0708AA3": [],
    "F893265F-F514-442E-80E0-1B29E9AA5E89": []
   }
  },
  "llama.cpp unsloth/gemma-4-E2B-it-GGUF/Q4_K_M short-chat (b8999)": {
   "verdict": "PASS",
   "rules": [],
   "runs": 4,
   "runs_off": 0,
   "detail": "4 of 4 replies pass the screen",
   "sample": "--- ### On-Device AI Explained Simply Imagine you have a super-smart assistant, like Siri or Google Assistant, but instead of sending all your conversations to…",
   "run_rules": {
    "316BBF72-8061-4E10-B004-E7F2A223363C": [],
    "34FFB0E8-1985-4D82-AAB6-EFDC2B161F89": [],
    "928BB9E3-F0C6-4F73-BDED-D96259A36B58": [],
    "BB429653-7476-4DEE-9DCB-8E335E6E122E": []
   }
  },
  "llama.cpp unsloth/gemma-4-E4B-it-GGUF/Q4_K_M long-context-1024-gen256 (b8999)": {
   "verdict": "FAIL",
   "rules": [
    "reply-empty",
    "reply-off-task"
   ],
   "runs": 4,
   "runs_off": 4,
   "detail": "4 of 4 replies empty or near-empty; 4 of 4 replies name none of the prompt's subject terms (sample: '1. [Item 1] 2. [Item 2] 3. [Item 3] 4. [Item 4] 5. [Item 5]…')",
   "sample": "1. [Item 1] 2. [Item 2] 3. [Item 3] 4. [Item 4] 5. [Item 5] 6. [Item 6] 7. [Item 7] 8. [Item 8] 9. [Item 9] 10. [Item 10] 11. [Item 11] 12. [Item 12] 13. [Item…",
   "run_rules": {
    "1F6C9FB0-BADF-47C6-B844-7A02FB31A567": [
     "reply-empty",
     "reply-off-task"
    ],
    "7FE60BDD-E3F1-445C-9984-4969C621E09B": [
     "reply-empty",
     "reply-off-task"
    ],
    "BA92D2B1-784B-479E-819F-94BABF454A43": [
     "reply-empty",
     "reply-off-task"
    ],
    "D66C513C-1679-4F77-8D44-828C222525FF": [
     "reply-empty",
     "reply-off-task"
    ]
   }
  },
  "llama.cpp unsloth/gemma-4-E4B-it-GGUF/Q4_K_M short-chat (b8999)": {
   "verdict": "PASS",
   "rules": [],
   "runs": 4,
   "runs_off": 0,
   "detail": "4 of 4 replies pass the screen",
   "sample": "**Think of it like this:** Instead of sending your data to a big, powerful computer far away (like a cloud server) to do a task, you are running the \"brain\" ri…",
   "run_rules": {
    "3AE51BC7-3BE0-40DD-B0FE-1608D04F570D": [],
    "BEDE391F-D58A-47E5-BD81-D984A45D996A": [],
    "C7AF359F-93C2-450D-A61D-40E7E0139074": [],
    "E30EB53D-3EDA-4631-B3BF-A3555CE66BAF": []
   }
  },
  "mlx-swift mlx-community/Qwen3-0.6B-4bit long-context-1024-gen256 (60bd0d7880c82980f9481f8be78862e9b63c58a3)": {
   "verdict": "PASS",
   "rules": [],
   "runs": 4,
   "runs_off": 0,
   "detail": "4 of 4 replies pass the screen",
   "sample": "<think> Okay, let's tackle this query. The user wants me to list 25 distinct things on-device AI that a phone can do a cloud model can't. Each item needs two f…",
   "run_rules": {
    "1133929C-4EE4-4DBD-81B5-32EAE73C6948": [],
    "33A6A24C-68AB-4CAD-93C3-9D34294D29E2": [],
    "57AF5C4B-A04C-4766-BC90-7953EFA86AAA": [],
    "58994556-45E5-4424-B86B-F82E2DD1C3EE": []
   }
  },
  "mlx-swift mlx-community/Qwen3-0.6B-4bit short-chat (60bd0d7880c82980f9481f8be78862e9b63c58a3)": {
   "verdict": "PASS",
   "rules": [],
   "runs": 3,
   "runs_off": 0,
   "detail": "3 of 3 replies pass the screen",
   "sample": "<think> Okay, the user is asking for an explanation of on-device AI in simple terms. Let me start by breaking down what on-device AI refers to. From what I rem…",
   "run_rules": {
    "03E6FD64-5297-4651-8278-AF99F8380587": [],
    "3937D55B-F11F-4FAD-BD53-947E00028911": [],
    "51EFA901-F17C-4E60-82A7-8FCA53AB96C8": []
   }
  },
  "mlx-swift mlx-community/Qwen3-1.7B-4bit long-context-1024-gen256 (60bd0d7880c82980f9481f8be78862e9b63c58a3)": {
   "verdict": "PASS",
   "rules": [],
   "runs": 4,
   "runs_off": 0,
   "detail": "4 of 4 replies pass the screen",
   "sample": "<think> Okay, the user wants a list of 25 things that on-device AI can do on a phone that a cloud model can't. Let me think about each one. First, real-time pr…",
   "run_rules": {
    "074F3C35-6B3F-4A35-A8C2-6521F7DC72AF": [],
    "3C0355D4-D549-4CC9-A965-8F210072E280": [],
    "3D27FEFE-B42E-41ED-A69C-270A0D11D8EE": [],
    "4823A30E-ADE8-4D1E-BE70-090AE8687F30": []
   }
  },
  "mlx-swift mlx-community/Qwen3-1.7B-4bit short-chat (60bd0d7880c82980f9481f8be78862e9b63c58a3)": {
   "verdict": "PASS",
   "rules": [],
   "runs": 4,
   "runs_off": 0,
   "detail": "4 of 4 replies pass the screen",
   "sample": "<think> Okay, the user is asking about what on-device AI means in simple terms. Let me start by breaking down the key components here. On-device AI refers to p…",
   "run_rules": {
    "21133EDE-0032-439E-A4BA-DF8970B979A2": [],
    "AFF771C7-A099-4E6F-967C-05956B8F7E2A": [],
    "D6F8FAFB-990F-4CAE-BA6D-8F610D188727": [],
    "F367A8F7-198C-4A21-A6A4-31031ED9B503": []
   }
  },
  "mlx-swift mlx-community/Qwen3-4B-4bit long-context-1024-gen256 (60bd0d7880c82980f9481f8be78862e9b63c58a3)": {
   "verdict": "PASS",
   "rules": [],
   "runs": 4,
   "runs_off": 0,
   "detail": "4 of 4 replies pass the screen",
   "sample": "<think> Okay, the user wants me to list 25 distinct things that on-device AI can do on a phone that a cloud model can't. Let me start by understanding the diff…",
   "run_rules": {
    "151CCF05-E82E-492D-A088-22E893C1DBFC": [],
    "563569EA-0ADA-406A-8A1C-58C9A88CB65E": [],
    "70823A33-5B21-456A-8892-4730E1704B5B": [],
    "98384409-ADBA-493A-8D68-5FB942DE025B": []
   }
  },
  "mlx-swift mlx-community/Qwen3-4B-4bit short-chat (60bd0d7880c82980f9481f8be78862e9b63c58a3)": {
   "verdict": "PASS",
   "rules": [],
   "runs": 4,
   "runs_off": 0,
   "detail": "4 of 4 replies pass the screen",
   "sample": "<think> Okay, the user is asking for an explanation of on-device AI in simple terms. Let me start by recalling what on-device AI is. From what I know, it's whe…",
   "run_rules": {
    "14AD402E-DFFB-4938-9A41-5DD6C1856967": [],
    "61318312-4B2B-4ED4-AB37-9E5E670447EB": [],
    "7695B1C0-6C7D-4ACE-A395-A35007852F68": [],
    "81F678C2-4DEE-4623-8B22-7E0E31830F35": []
   }
  },
  "mlx-swift mlx-community/gemma-4-e2b-it-qat-OptiQ-4bit long-context-1024-gen256 (60bd0d7880c82980f9481f8be78862e9b63c58a3)": {
   "verdict": "PASS",
   "rules": [],
   "runs": 4,
   "runs_off": 0,
   "detail": "4 of 4 replies pass the screen",
   "sample": "Here are 25 distinct things an on-device AI can do on a phone that a cloud model cannot, based on the general capabilities of modern mobile AI: 1. **Real-time,…",
   "run_rules": {
    "138F9308-1B10-440E-8F01-5357EFAC012E": [],
    "45ECC8D5-2B77-4F10-9533-827FA521DBF0": [],
    "9F02E1B2-7A0A-4919-86CC-6B08A675AEF5": [],
    "EA68B6DA-02C6-4800-A717-EB92495C7469": []
   }
  },
  "mlx-swift mlx-community/gemma-4-e2b-it-qat-OptiQ-4bit short-chat (60bd0d7880c82980f9481f8be78862e9b63c58a3)": {
   "verdict": "PASS",
   "rules": [],
   "runs": 4,
   "runs_off": 0,
   "detail": "4 of 4 replies pass the screen",
   "sample": "Imagine you have a smart device, like your smartphone, a smart speaker, or even a smart camera. **On-device AI** simply means that the \"brain\" or the \"intellig…",
   "run_rules": {
    "5F7DE0F4-5AD3-4109-B69A-63F91F55C38F": [],
    "747EE58F-04FD-4C5B-90C8-54D36F662C8A": [],
    "9A86A911-E6C5-44A3-9596-BF34928EA392": [],
    "EC6577C4-5B0A-421E-9667-AEFC94EDCE82": []
   }
  },
  "mlx-swift mlx-community/gemma-4-e4b-it-qat-OptiQ-4bit long-context-1024-gen256 (60bd0d7880c82980f9481f8be78862e9b63c58a3)": {
   "verdict": "FAIL",
   "rules": [
    "reply-off-task"
   ],
   "runs": 4,
   "runs_off": 4,
   "detail": "4 of 4 replies name none of the prompt's subject terms (sample: 'As a Large Language Model, I must inform you that the provi…')",
   "sample": "As a Large Language Model, I must inform you that the provided text is a block of repetitive \"Lorem Ipsum\" placeholder text. It contains no meaningful informat…",
   "run_rules": {
    "2BED38F8-FE2A-4D49-8099-DE3B0E149F7B": [
     "reply-off-task"
    ],
    "42219A3D-449D-401F-AB39-A612FEB12200": [
     "reply-off-task"
    ],
    "90CAB924-28B1-4396-9A97-F4E3B4680B16": [
     "reply-off-task"
    ],
    "BE177D55-59F3-4EC3-845F-20D010C3578C": [
     "reply-off-task"
    ]
   }
  },
  "mlx-swift mlx-community/gemma-4-e4b-it-qat-OptiQ-4bit short-chat (60bd0d7880c82980f9481f8be78862e9b63c58a3)": {
   "verdict": "PASS",
   "rules": [],
   "runs": 4,
   "runs_off": 0,
   "detail": "4 of 4 replies pass the screen",
   "sample": "Imagine you have a super-smart assistant, but instead of that assistant needing to constantly call a giant, powerful computer in the cloud (like Google's serve…",
   "run_rules": {
    "24B571DE-CC86-4001-BA7B-E9A5E6CE59E9": [],
    "2A7A0C49-F70E-47A0-AF2D-482F5D6E5F61": [],
    "6F6B104E-DCF3-4494-AC01-86FD2D2EE6E4": [],
    "9652ADB0-E972-47DB-A938-6E2CC03EF4E2": []
   }
  },
  "onnxruntime-genai-cpu onnx-community/Qwen3-0.6B-ONNX short-chat (onnxruntime-genai 0.17.1 + onnxruntime 1.30.0)": {
   "verdict": "PASS",
   "rules": [],
   "runs": 4,
   "runs_off": 0,
   "detail": "4 of 4 replies pass the screen",
   "sample": "<think> Okay, the user is asking for a simple explanation of what on-device AI means. Let me start by breaking down the term. On-device AI refers to AI systems…",
   "run_rules": {
    "230597c8-b852-4aec-82e7-9209ce5eaf18": [],
    "7fb55af0-ddb9-4ebf-a39a-bc268d3edf01": [],
    "93f1b907-c8fe-4ddd-b11a-64d8a6131ed7": [],
    "d71e7730-3866-488a-8ea7-f441265124d3": []
   }
  },
  "onnxruntime-genai-cpu onnx-community/Qwen3-1.7B-ONNX short-chat (onnxruntime-genai 0.17.1 + onnxruntime 1.30.0)": {
   "verdict": "PASS",
   "rules": [],
   "runs": 4,
   "runs_off": 0,
   "detail": "4 of 4 replies pass the screen",
   "sample": "<think> Okay, the user wants me to explain what on-device AI means in simple terms. Let me break this down. First, I need to define what on-device AI is. On-de…",
   "run_rules": {
    "1398010f-3905-4828-bf38-27ceadbc2e6e": [],
    "62898a0a-a379-4f9b-b9f8-37a581071e1a": [],
    "d78151a6-00bb-45eb-b6e6-f916ea89c454": [],
    "dcc87d92-35cd-42b5-a6ea-fdd51b713ef7": []
   }
  },
  "onnxruntime-genai-cpu onnx-community/Qwen3-4B-ONNX short-chat (onnxruntime-genai 0.17.1 + onnxruntime 1.30.0)": {
   "verdict": "PASS",
   "rules": [],
   "runs": 4,
   "runs_off": 0,
   "detail": "4 of 4 replies pass the screen",
   "sample": "<think> Okay, the user is asking for an explanation of on-device AI in simple terms. Let me start by recalling what on-device AI means. So, on-device AI refers…",
   "run_rules": {
    "2236bf47-f64e-403c-927b-ae468b475100": [],
    "72e9d9d0-e9eb-4a2f-ba2b-b7b06ad5ed2c": [],
    "8cd5c0e3-0a8b-4b65-afc2-5888de37600b": [],
    "dec081ba-ff20-4e6c-81b7-38ec7d1390dc": []
   }
  },
  "onnxruntime-genai-webgpu onnx-community/Qwen3-0.6B-ONNX short-chat (onnxruntime-genai 0.17.1 + onnxruntime 1.30.0 + onnxruntime-ep-webgpu 0.4.0)": {
   "verdict": "PASS",
   "rules": [],
   "runs": 4,
   "runs_off": 0,
   "detail": "4 of 4 replies pass the screen",
   "sample": "<think> Okay, the user is asking for an explanation of on-device AI in simple terms. Let me start by recalling what I know about AI and on-device AI. On-device…",
   "run_rules": {
    "3ca43d36-6e66-4f07-85b0-46085c478a32": [],
    "9e8c0e04-bddb-42a0-b493-48e1454ed9f7": [],
    "aaf17aa2-f72a-43f8-89b3-1a707b85d6d8": [],
    "b2dbce0b-0825-4985-98e7-e3788e547681": []
   }
  },
  "onnxruntime-genai-webgpu onnx-community/Qwen3-1.7B-ONNX short-chat (onnxruntime-genai 0.17.1 + onnxruntime 1.30.0 + onnxruntime-ep-webgpu 0.4.0)": {
   "verdict": "PASS",
   "rules": [],
   "runs": 4,
   "runs_off": 0,
   "detail": "4 of 4 replies pass the screen",
   "sample": "<think> Okay, the user wants an explanation of on-device AI in simple terms. Let me break this down. First, I need to define what on-device AI is. Maybe start …",
   "run_rules": {
    "067d7fab-62ca-4c1a-8523-9499b93615d4": [],
    "29604f01-ffa0-44a7-a2e4-61ad70b4a494": [],
    "71fb1929-c4b5-4e2d-a44b-e8b91e45d0b6": [],
    "b0ef866a-6849-4f4e-8837-28e9ef69d611": []
   }
  },
  "onnxruntime-genai-webgpu onnx-community/Qwen3-4B-ONNX short-chat (onnxruntime-genai 0.17.1 + onnxruntime 1.30.0 + onnxruntime-ep-webgpu 0.4.0)": {
   "verdict": "PASS",
   "rules": [],
   "runs": 4,
   "runs_off": 0,
   "detail": "4 of 4 replies pass the screen",
   "sample": "<think> Okay, the user wants me to explain what on-device AI means in simple terms. Let me start by recalling what on-device AI is. From what I remember, on-de…",
   "run_rules": {
    "41315241-43df-46fe-b045-7bb6f5e4e1a5": [],
    "5e875bd5-8ae2-4f78-994f-0f890a0cad8e": [],
    "8cea797c-9ad7-4e4a-b8c8-e28c55721d0b": [],
    "acd08c47-ebdc-4658-9464-39a768f43c96": []
   }
  }
 }
}
```

</details>

**summary** (`results/summary/device-runs.csv`、index から作り直し、5036 → 5044 行): 対の外の行は全行 byte 同一。対の中は前の全行 (text_check を除いて同じ) + 戻した 8 run。対の `text_check`: `PASS:screen` 153、`PASS` 72 (runner の check)、`FAIL:reply-off-task` 4、`FAIL:reply-empty,reply-off-task` 4。その 2 cell の行 (source の先頭、runtime、model、task、context、cold、firstEver、decode_tps、text_check):

```
mlx-swift_mlx-community_gemma-4-e4b-it-qat-OptiQ-4bit_long-c | mlx-swift | mlx-community/gemma-4-e4b-it-qat-OptiQ-4bit | long-context-1024-gen256 | 2523 | True  |  | 91.56906430201349 | FAIL:reply-off-task
mlx-swift_mlx-community_gemma-4-e4b-it-qat-OptiQ-4bit_long-c | mlx-swift | mlx-community/gemma-4-e4b-it-qat-OptiQ-4bit | long-context-1024-gen256 | 2523 | False |  | 91.13109457362077 | FAIL:reply-off-task
mlx-swift_mlx-community_gemma-4-e4b-it-qat-OptiQ-4bit_long-c | mlx-swift | mlx-community/gemma-4-e4b-it-qat-OptiQ-4bit | long-context-1024-gen256 | 2523 | False |  | 90.80110174815545 | FAIL:reply-off-task
mlx-swift_mlx-community_gemma-4-e4b-it-qat-OptiQ-4bit_long-c | mlx-swift | mlx-community/gemma-4-e4b-it-qat-OptiQ-4bit | long-context-1024-gen256 | 2523 | False |  | 87.9129930252432  | FAIL:reply-off-task
llama_cpp_unsloth_gemma-4-E4B-it-GGUF_Q4_K_M_long-context-10 | llama.cpp | unsloth/gemma-4-E4B-it-GGUF/Q4_K_M | long-context-1024-gen256 | 2048 | True  |  | 86.8291963101172  | FAIL:reply-empty,reply-off-task
llama_cpp_unsloth_gemma-4-E4B-it-GGUF_Q4_K_M_long-context-10 | llama.cpp | unsloth/gemma-4-E4B-it-GGUF/Q4_K_M | long-context-1024-gen256 | 2048 | False |  | 86.73308679812608 | FAIL:reply-empty,reply-off-task
llama_cpp_unsloth_gemma-4-E4B-it-GGUF_Q4_K_M_long-context-10 | llama.cpp | unsloth/gemma-4-E4B-it-GGUF/Q4_K_M | long-context-1024-gen256 | 2048 | False |  | 86.51749961192728 | FAIL:reply-empty,reply-off-task
llama_cpp_unsloth_gemma-4-E4B-it-GGUF_Q4_K_M_long-context-10 | llama.cpp | unsloth/gemma-4-E4B-it-GGUF/Q4_K_M | long-context-1024-gen256 | 2048 | False |  | 86.25586556401845 | FAIL:reply-empty,reply-off-task
```

**P** (`EDGE_LLM_BENCH=<clone> python3 ~/code/litert-bench-dashboard/build.py --out-dir <scratch>`、P の file は無変更) の cells.csv、その 2 行 (device, arm, model_id, task, status, decode_tps, campaign, text_fail_n, text_checked_n, n):

```
Mac16,9,llama.cpp,unsloth/gemma-4-E4B-it-GGUF/Q4_K_M,long-context-1024-gen256,text-fail:text check failed: reply-empty, reply-off-task (4 of 4 runs),,2026-10-12-dashboard-v1-m4max-mac,4,4,0
Mac16,9,mlx-swift,mlx-community/gemma-4-e4b-it-qat-OptiQ-4bit,long-context-1024-gen256,text-fail:text check failed: reply-off-task (4 of 4 runs),,2026-10-12-dashboard-v1-m4max-mac,4,4,0
```

手順の前の build (同じ clone、04:10) では同じ 2 cell が `measured`、decode 87.13 / 92.29 tok/s、campaign `2026-10-06-dashboard-v1-m4max-longctx1024-mac`、`text_checked_n` 0 (10-06 の dir の返事も同じ骨組みと拒否文: その 4 + 4 run を同じ proxy で読んで 4/4 off)。前後の cells.csv の差 (550 cell): status が変わったのはこの 2 cell だけ、他は Mac16,9 の 34 cell の `text_checked_n` 0 → 3/4 だけ (10-12 の対が最新の session の cell)。

**P の check 3 本** (`--dist <scratch>`、`render_check.py` は回していない) の末尾:

```
check_against_bench_dashboard: … protocol cells (native-benchmark-1024x256): 54 equal by the protocol rule …
                               PASS
check_regression:  cells.json: 24 newest points equal their cell on 15 fields and are shown, 3 series of cells not measured have no point, 9 excluded cells listed; 2 mismatches
                   FAIL cells.json SM-S942Q litert-lm-gpu litert-community/gemma-4-E2B-it-litert-lm long-context-1024-gen256 2048 gemma-4-E2B-it.litertlm: no point of the cell's campaign 2026-10-18-dashboard-v1-s26-ddp-m1q-36-android
                   FAIL cells.json SM-S942Q litert-lm-gpu litert-community/gemma-4-E2B-it-litert-lm short-chat gemma-4-E2B-it.litertlm: no point of the cell's campaign 2026-10-18-dashboard-v1-s26-ddp-m1q-36-android
                   FAIL (2)
check_aa:          aa: 23 models (6 new cards), 4 devices (SM-S942Q, Pixel 8a, iPhone18,1, Mac16,9), 634 rows … PASS
```

check_regression の 2 件は手順の前の build (77a3fdd0) でも、main 9288dd34 の bench (r10 なし) から作った build でも同じ 2 件 (9288dd34 と 77a3fdd0 の cells.csv は byte 同一)。r10 と無関係。

### (c) commit 済み 118 dir (`--no-text-screen`、この worktree の lock、04:08)

| | 変更前 (03:44) | 変更後 |
|---|---|---|
| PASS | 89 | 90 |
| HOLD | 28 | 27 |
| FAIL | 1 | 1 |
| 時間 | 11.29 s | 11.60 s |
| 書いた file | — | 0 (`find results/raw -name text_screen.json` 空) |

- verdict が変わった dir: `2026-10-06-dashboard-v1-m4max-longctx1024-mac` HOLD → PASS だけ。変更前の live finding は `reply-empty` (llama.cpp Gemma 4 E4B GGUF 1K、4/4) と `reply-off-task` 2 件 (同じ cell と MLX Gemma 4 E4B OptiQ 1K、4/4) だけだった。
- reply-* が note になった dir は 3 つ: 上の 10-06 Mac と、iPhone 17 Pro の `2026-10-17-dashboard-v1-iphone17pro-0180-aa-i1-anchor-ios` / `-aa-i1-ios` (LiteRT-LM Qwen3 0.6B short-chat v0.18.0、3/3 と 6/6 off-task; 今まで e3010721 の行で許可 = verdict は PASS のまま)。
- 他の規則の finding: 全 118 dir で (rule, detail, 許可した commit) の多重集合が変更前と同じ。Android の reply-* finding (Pixel 8a / S26 の LiteRT-LM GPU Qwen3 1.7B / 0.6B short-chat など) も全件同じ。
- r8 の `committed_check_r8.md` (116 dir PASS 87 / HOLD 28 / FAIL 1) との関係: 変更前の 118 dir = r8 の 116 + 10-12 の対 (PASS / PASS) で 89 / 28 / 1、数が合う。
- この 118 dir で sidecar が書かれるのは 22 dir (157 cell)、そのうち text-fail の cell を持つのは上の 3 dir。

この (c) はこの worktree の lock (0b38a1f2 の前) で回した。main の lock では Mac の 10-12 / 10-16 / 10-19 に `engine-stamp` HOLD が足される (監督の知らせ、r10 と無関係)。

### (d) POST の dry run (04:13:43-04:14:08)

clone (この branch) で 10-12 の対を `git rm -r --cached` + scratch commit で HEAD から外し、disk に untracked で置き、`.set-aside` 2 本を戻した。`TMPDIR=<scratch> taskpolicy -b python3 scripts/dashboard_post.py <anchor> <payload> --dry-run --no-page-commit` → exit 0、両 dir に text_screen.json は無いまま。出力 (抜粋、path は伏せた):

```
[2026-10-19 04:13:49] post: check: PASS  2026-10-12-dashboard-v1-m4max-anchor-mac  (job anchor)
[2026-10-19 04:13:49] post: check:         text screen: would write text_screen.json (2 cells, 0 text-fail)
[2026-10-19 04:13:49] post: check: PASS  2026-10-12-dashboard-v1-m4max-mac  (job payload)
[2026-10-19 04:13:49] post: check:         text screen: would write text_screen.json (39 cells, 2 text-fail: llama.cpp unsloth/gemma-4-E4B-it-GGUF/Q4_K_M long-context-1024-gen256 (b8999) 4/4, mlx-swift mlx-community/gemma-4-e4b-it-qat-OptiQ-4bit long-context-1024-gen256 (60bd0d7880c82980f9481f8be78862e9b63c58a3) 4/4)
[2026-10-19 04:13:49] post: check: PASS 2  HOLD 0  FAIL 0  of 2
[2026-10-19 04:14:03] post: message: results 2026-10-12 Mac Studio (M4 Max) (Mac16,9), core-ai: 0.2.0+static-inputs-patch, executorch-mlx: v1.5.1, executorch-xnnpack: v1.5.1, litert-lm: v0.18.0, llama.cpp: b8999, mlx-swift: 60bd0d7880c82980f9481f8be78862e9b63c58a3, onnxruntime-genai-cpu: onnxruntime-genai 0.17.1 + onnxruntime 1.30.0, onnxruntime-genai-webgpu: onnxruntime-genai 0.17.1 + onnxruntime 1.30.0 + onnxruntime-ep-webgpu 0.4.0: 57/57 cells of matrices/dashboard-text-v1.cells in one dashboard-job sitting 05:30–08:34 JST (anchor admitted at ratio 1.000 to reference 2026-10-12-dashboard-v1-m4max-mac, thermal nominal; the payload's own anchor rows at 1.000); text check 72/72; text screen: 2 cells text-fail (llama.cpp unsloth/gemma-4-E4B-it-GGUF/Q4_K_M long-context-1024-gen256 4/4 runs, mlx-swift mlx-community/gemma-4-e4b-it-qat-OptiQ-4bit long-context-1024-gen256 4/4 runs); cpu-capped counted 0/233, past the line 0; FAILURES: FAIL llama.cpp unsloth/Qwen3-0.6B-GGUF/Q4_K_M short-chat round=1; FAIL llama.cpp unsloth/Qwen3-0.6B-GGUF/Q4_K_M long-context-1024-gen256 ctx=2048 round=1 and 10 more; gate retries kept: 3 (FLAGGED.txt); SKIPPED: 20 lines; results/summary rebuilt from the git index (5036 -> 5044 lines)
[2026-10-19 04:14:03] post: message guard: no '%' and no standing word (vs, faster, slower, than, beats, leads, outperforms): OK
[2026-10-19 04:14:03] post: would build ~/code/litert-bench-dashboard/build.py into <scratch>/postd/logs/dashboard-job/autopilot-page and run its four checks
[2026-10-19 04:14:08] post: exit 0; …  (the red segment's dry-run notes left out here; nothing written)
```

message 全文:

```
results 2026-10-12 Mac Studio (M4 Max) (Mac16,9), core-ai: 0.2.0+static-inputs-patch, executorch-mlx: v1.5.1, executorch-xnnpack: v1.5.1, litert-lm: v0.18.0, llama.cpp: b8999, mlx-swift: 60bd0d7880c82980f9481f8be78862e9b63c58a3, onnxruntime-genai-cpu: onnxruntime-genai 0.17.1 + onnxruntime 1.30.0, onnxruntime-genai-webgpu: onnxruntime-genai 0.17.1 + onnxruntime 1.30.0 + onnxruntime-ep-webgpu 0.4.0: 57/57 cells of matrices/dashboard-text-v1.cells in one dashboard-job sitting 05:30–08:34 JST (anchor admitted at ratio 1.000 to reference 2026-10-12-dashboard-v1-m4max-mac, thermal nominal; the payload's own anchor rows at 1.000); text check 72/72; text screen: 2 cells text-fail (llama.cpp unsloth/gemma-4-E4B-it-GGUF/Q4_K_M long-context-1024-gen256 4/4 runs, mlx-swift mlx-community/gemma-4-e4b-it-qat-OptiQ-4bit long-context-1024-gen256 4/4 runs); cpu-capped counted 0/233, past the line 0; FAILURES: FAIL llama.cpp unsloth/Qwen3-0.6B-GGUF/Q4_K_M short-chat round=1; FAIL llama.cpp unsloth/Qwen3-0.6B-GGUF/Q4_K_M long-context-1024-gen256 ctx=2048 round=1 and 10 more; gate retries kept: 3 (FLAGGED.txt); SKIPPED: 20 lines; results/summary rebuilt from the git index (5036 -> 5044 lines)
```

`%` も順位の語 (vs, faster, slower, than, beats, leads, outperforms) も無い (guard の正規表現で 0 件)、commit-msg hook が断る語も無い。

### (e) 時間

(c) の 118 dir: 11.60 s (変更前 11.29 s; r8 は 116 dir 10.54 s)。1 回ずつの比較で、差 0.31 s の内訳は分けていない (枠 3 分)。

## 10-12 の対への適用手順 (監督が MAIN で、この branch を merge した後)

前提: main に 77a3fdd0 と 15b7866e が入っている (merge)。post が走っていない時に回す (`logs/dashboard-job/.post.lock` を誰も持っていない、夜の job の sitting が終わっている): post も手順も `results/summary` を index から作って commit するので、間に post の commit が入るとこの commit の summary からその sitting の行が抜ける。`git diff --cached --name-only` が空 (他の lane の staged が無い) こと: 空でなければ止める (summary の作り直しは index を丸ごと書き出すので、他の lane の staged file が summary に入る)。

```bash
cd ~/code/edge-llm-bench
# step 5: the 2026-10-12 Mac pair's two set-aside cells back as records, marked by the text screen.
# Run from the checkout's top (main, after the merge of bench-autopilot). zsh or bash.
A=results/raw/2026-10-12-dashboard-v1-m4max-anchor-mac
R=results/raw/2026-10-12-dashboard-v1-m4max-mac
L=llama_cpp_unsloth_gemma-4-E4B-it-GGUF_Q4_K_M_long-context-1024-gen256_ctx2048.jsonl
M=mlx-swift_mlx-community_gemma-4-e4b-it-qat-OptiQ-4bit_long-context-1024-gen256.jsonl
echo "0. staged before (must be empty):"; git diff --cached --name-only
git mv "$R/$L.set-aside" "$R/$L"
git mv "$R/$M.set-aside" "$R/$M"
echo "2. the checker (writes text_screen.json in both dirs):"
python3 scripts/session_check.py "$A" "$R" -q
echo "3. the allow-list line of 8ac9b8bb out (its reason no longer holds; c7b60c2b's line excuses the failures line):"
python3 -c 'p = "ops/session-check/allow-list.tsv"; L = open(p).read().splitlines(True); open(p, "w").writelines(x for x in L if "\t8ac9b8bb\t" not in x)'
git diff --stat -- ops/session-check/allow-list.tsv
python3 scripts/session_check.py "$A" "$R" -q
git add -- "$A/text_screen.json" "$R/text_screen.json" ops/session-check/allow-list.tsv
echo "4. staged (the 2 renames, the 2 files, the allow-list):"; git diff --cached --name-status
d=$(mktemp -d) && git checkout-index -a --prefix="$d/" && python3 "$d/scripts/build_summary.py" && cp "$d"/results/summary/* results/summary/ && rm -rf "$d"
git add -- results/summary
echo "5. staged with the summary:"; git diff --cached --stat | tail -3
git commit -F <下の message の file> -- "$A/text_screen.json" "$R/text_screen.json" "$R/$L" "$R/$L.set-aside" "$R/$M" "$R/$M.set-aside" ops/session-check/allow-list.tsv results/summary
```

期待値 (main 0b38a1f2 + この branch の scratch clone で上をそのまま回した結果):

- 0: 何も出ない。
- 2 と 3 の後の checker: `HOLD 2026-10-12-dashboard-v1-m4max-anchor-mac (job anchor) engine-stamp` / `text screen: written text_screen.json (2 cells, 0 text-fail)`、`HOLD 2026-10-12-dashboard-v1-m4max-mac (job payload) engine-stamp` / `text screen: written text_screen.json (39 cells, 2 text-fail: llama.cpp unsloth/gemma-4-E4B-it-GGUF/Q4_K_M long-context-1024-gen256 (b8999) 4/4, mlx-swift mlx-community/gemma-4-e4b-it-qat-OptiQ-4bit long-context-1024-gen256 (60bd0d7880c82980f9481f8be78862e9b63c58a3) 4/4)`; 2 回目は `unchanged`。HOLD は `engine-stamp` だけ (0b38a1f2 の後の正しい状態)、failures の 12 行は c7b60c2b の行で許可。0b38a1f2 の前の lock なら PASS / PASS。
- 3: allow-list の 1 行が消える (`1 file changed, 1 deletion(-)`)。8ac9b8bb の行の理由「the cell's records were set aside by hand」が戻した後は成り立たないので、消すのを勧める。消しても消さなくても verdict は同じ (その failures 行には先に c7b60c2b の行が当たる)。
- 4: `M ops/session-check/allow-list.tsv`、`A $A/text_screen.json`、`R100` 2 本 (.set-aside → .jsonl)、`A $R/text_screen.json`。
- 5 の後: `results/summary/README.md` 2 行 (行数)、`device-runs.csv` (5036 → 5044 行)、commit は 7 file。pathspec の commit は、他の lane の staged file を staged のまま残す (scratch clone で stand-in の staged file を置いて確かめた; tree は index の commit と同じ)。
- P (MAIN から build): Mac16,9 の 2 cell が上の 2 行。cells.csv の差は (b) と同じ 36 行。

message の文案 (guard の正規表現で 0 件):

```
results/raw/2026-10-12-dashboard-v1-m4max{-anchor,}-mac: the two cells set aside by hand in 8ac9b8bb are records again (llama.cpp unsloth/gemma-4-E4B-it-GGUF/Q4_K_M and mlx-swift mlx-community/gemma-4-e4b-it-qat-OptiQ-4bit, long-context-1024-gen256, 4 runs each), marked by the session checker's text screen (77a3fdd0): text_screen.json in both dirs (the payload's 39 text cells, 2 text-fail: reply-empty + reply-off-task and reply-off-task, 4 of 4 runs each; the anchor's 2 cells pass), so results/summary reads FAIL:<rules> on those 8 runs and PASS:screen on the sitting's other 153 screened runs, and the page shows the two Mac Studio cells as text-fail with no decode number where their 2026-10-06 rows stood; ops/session-check/allow-list.tsv loses the 8ac9b8bb line (the records are no longer set aside; the failures line of that cell is excused by the c7b60c2b line); session_check.py reads HOLD / HOLD on engine-stamp alone (the dirs' LiteRT-LM records stamp v0.18.0, the Mac pin is v0.16.0 since 0b38a1f2; nothing in this commit touches those records); results/summary rebuilt from the git index (5036 -> 5044 lines)
```

## commit

- `77a3fdd0` (bench-autopilot, 04:09:38): `scripts/session_check.py`, `scripts/build_summary.py`, `scripts/dashboard_post.py`, `scripts/session_check_selftest.py`, `scripts/dashboard_post_selftest.py`, `docs/session-check-v1.md`, `docs/dashboard-autopilot-v1.md`, `methodology/fairness-rules.md`, `results/summary/README.md` (index から作り直し)。
- `15b7866e` (04:21:53): `scripts/session_check_selftest.py` (text screen の case を llama.cpp cell に、l.307 を例外にしない)。
- この file の commit (下の round close の後)。
- 帰属行なし、`claude` の語なし、明示 path だけ、push も merge もしていない。

## 提案

1. **main@0b38a1f2 の session_check_selftest (CI の data-pipeline が赤)**: 0b38a1f2 だけで 10 FAIL の後 l.307 で TypeError (r10 の前から)。原因: generic な case の Mac の合成 sitting (2099 年付け) が LiteRT-LM cell を lock の `arms.litert-lm.mac.tag` (v0.16.0) で stamp し、Android / iPhone の v0.18.0 (since 10-15 / 10-19) より古い → pin-drift FAIL。新しい lock では「Mac の LiteRT-LM cell を持つ clean な 2099 の sitting」は作れない (pin と stamp を合わせれば pin-drift、新しい release を stamp すれば engine-stamp)。r10 の 15 本は LiteRT-LM の pin を読まない形にした (15b7866e)。残り 11 本の直し方: (i) generic な Mac fixture から LiteRT-LM cell を外す (MLX + llama.cpp; pin の section は自分で日付と stamp を作っている) — 私ならこれ、lock が動くたびに壊れる所が無くなる; (ii) generic な fixture の日付を「Mac の pin より新しい pin の最初の since の前日」に lock から計算する; (iii) fixture 用の registry (checker に差し替え口が要る)。
2. **merge の時刻と今夜の post**: post は MAIN の checker を使う。merge の後の post から screen が効く。今夜の Mac (`2026-10-19-dashboard-v1-m4max`、計測中) は `engine-stamp` で HOLD のまま (0b38a1f2)、screen は llama.cpp E4B 1K / MLX E4B OptiQ 1K の返事を印に変えるだけ。iPhone 18 Pro (2026-10-19、計測中) は anchor の LiteRT-LM Qwen3 0.6B short-chat が今 3/3 off-task (`--no-text-screen` で読んだ、e3010721 の bundle template) → merge 前の post なら e3010721 の行で許可 = その run は数字のまま summary に入る (page に出るのは page が作り直された時: 今は check_regression で止まる、提案 7)、merge 後なら text-fail の印 (LiteRT-LM 自身の cell)。iPhone 18 Pro の llama.cpp E4B 1K も同じ (下の 4)。
3. **Android との非対称**: Android の LiteRT-LM cpu / gpu short-chat と llama.cpp CPU の launch は runner が text check しない (`run_cell.py`)。同じ Qwen3 0.6B v0.18.0 short-chat が iPhone / Mac では text-fail、Android では数字になる。checker はその Android の返事を既に読んでいる (reply-* HOLD、e3010721 で許可)。案: runner の textCheck が無い Android の cell にも sidecar を書く (runner の check がある cell は今までどおり runner が正)。launch の「Android は書かない」に従って今回は入れていない。
4. **iPhone の同じ cell**: iPhone 18 Pro の llama.cpp Gemma 4 E4B GGUF 1K は MAIN の disk の job sitting 5 本 (10-08、10-15、10-15-r2、10-17、10-17-r2; どれも未 commit) で全部 4/4 off (`--no-text-screen` で読んだ、同じ「1. [Item 1] …」)。page の今の数字 30.71 tok/s は `2026-10-07-dashboard-longctx1024-v1-iphone18pro-c4-ios` (commit 済み、kind hand run = screen の外) の 4 run で、その返事も 4/4 同じ骨組み (同じ proxy で読んだ)。Mac (10-06 と 10-12) と iPhone で同じ arm・同じ model・同じ task が同じ形で落ちる = 原因は engine と prompt / chat template の組の側らしい (未確認)。案: (i) hand run の dir にも sidecar を書ける口 (例: `--text-screen-any-kind`) を作り、その dir に足す commit; (ii) 原因が構造なら cells の `exclude-on=` で理由を datum にする。MLX の Gemma 4 E4B OptiQ は iPhone では `excluded:app-killed-at-model-load-sigkill` で同じ cell は無い。
5. **commit 済みの他の dir**: 22 dir (157 cell) に sidecar が無い。足すと page が変わるのは iPhone 17 Pro の LiteRT-LM Qwen3 0.6B short-chat (今 131.03 tok/s、`…-0180-aa-i1-ios`、6/6 off-task) の 1 cell (10-06 Mac の 2 cell は手順の後 10-12 の session が上に来る)。足すかどうかは監督 / owner の判断。
6. **regression watch**: `regression_value` は status `measured` しか読まないので、「数字 → text-fail」は赤にならず series の点が消えるだけ。POST の `number_changes` が ledger と page の message に `cells with a number before and none now: <k> (text-fail <k>)` と書くので朝の目には入る。案: LiteRT-LM の cell が measured → text-fail に変わったら赤相当 (engine か bundle の text の欠陥の合図: v0.18.0 の Qwen3 0.6B template が例) として retake の対象にする。他の runtime の cell は今の regression の series に無いので対象外。
7. **P 側** (P の file は変えていない): (a) check_regression の既存の 2 件 (S26 の LiteRT-LM GPU Gemma 4 E2B の 2 cell、stand-in の campaign `2026-10-18-dashboard-v1-s26-ddp-m1q-36-android` に regression の点が無い): 次の post の page step はここで止まる (bench の commit は立つ、page は commit されない、exit 1)。check か series のどちらを直すかは P の判断 (原因は check の文以上は未確認)。(b) text-fail の文言 (Mac / iPhone は checker の screen):

```diff
--- build.py (gapReason)
-    if (textFail(c)) return "Every run of the session that could give this cell's number failed the decoded-text check " +
-      "(text-check-rule, methodology/fairness-rules.md §12), so it has none; the runs stay in raw.";
+    if (textFail(c)) return "Every run of the session that could give this cell's number failed the decoded-text check " +
+      "(text-check-rule, methodology/fairness-rules.md §12; on Android the runner's check, on the Mac and iPhone the " +
+      "bench's session-checker screen of the stored reply, text_screen.json), so it has none; the runs stay in raw.";
--- build.py (the "Aggregation." line of the method)
-… runs whose decoded text failed the text check (text-check-rule, methodology/fairness-rules.md §12: an engine reports a rate whatever it decoded; …
+… runs whose decoded text failed the text check (text-check-rule, methodology/fairness-rules.md §12: an engine reports a rate whatever it decoded; on the Mac and iPhone, whose runners check no text, the bench's session checker screens each run's stored reply into text_screen.json; …
```

8. `render_check.py` は回していない (Mac の 2026-10-19 の ledger 行がまだ無い: 04:14 に `bench matrix … --campaign 2026-10-19-dashboard-v1-m4max` が走っている)。P を MAIN から作り直す時は Mac の行が出てから。

## 経過

- 03:40 `date` read, ListAgents (this session = edge-llm-bench-wt-autopilot-38 [53949d]), `git reset --hard main` (a73d7c67 → 9288dd34, tree clean before). Next: read CHECK / SUMMARY / POST / P build.
- 03:44 baseline: selftests 49 / 51 / 89 / 50 / 58 + test_render_rules OK (all exit 0); the current checker over the 118 committed job dirs PASS 89 / HOLD 28 / FAIL 1, 11.29 s. 714 screened Mac/iPhone records, every one with an id; no cell key mixes contexts or quantizations.
- 03:57 build_summary.py (cell_key_of, text_screen_of, text_check_of) and session_check.py (reply_rules, screen_out, --text-screen/--no-text-screen) written; smoke in a scratch clone of main with the two .set-aside files restored: sidecar 39 cells / 2 text-fail (4/4 each), payload PASS; summary FAIL:… on the 8 runs, PASS:screen on 153; P build (scratch out) → both Mac16,9 cells `text-fail:` with no decode. Next: POST, selftests, docs.
- 04:06-04:08 POST・selftest 2 本・docs 3 本を書いた。(a) 60 / 54 / 89 / 50 / 58 + test_render_rules + py_compile、android/bench/selftest.py 245 OK (04:08:38)。
- 04:08 (c) 118 dir `--no-text-screen` 11.60 s: PASS 90 / HOLD 27 / FAIL 1、何も書いていない。
- 04:09:38 commit 77a3fdd0 (9 path)。次: (b) の scratch clone。
- 04:10-04:12 (b) ① clone (この branch): P の前 build、手順、commit、後 build、check 3 本 (check_regression FAIL 2 → 9288dd34 の build でも同じと確認、04:12)。
- 04:13:43-04:14:08 (d) POST の dry run (`taskpolicy -b`、夜の job は Mac・S26・iPhone 18 Pro で計測中)。
- 04:1x 監督の知らせ (0b38a1f2) を受け取った。04:18 main 0b38a1f2 の clone で session_check_selftest が落ちることを確認 (10 FAIL + TypeError)、merge で r10 の case も落ちる (15 FAIL)。r10 の case を llama.cpp cell に、l.307 を例外にしない形に → この tree 60 OK、merge 後 47 / 11 FAIL (既存) / 1 skip。04:21:53 commit 15b7866e。
- 04:22 (b) ② main 0b38a1f2 + この branch の merge で手順を回し直し: HOLD / HOLD (`engine-stamp` だけ)、sidecar・summary・cells.csv は ① と同じ。P の check 3 本は ① と同じ。
- 04:24 iPhone の 22 job dir を MAIN の disk から `--no-text-screen` で読んだ (提案 2・4)。04:2x この file。

## 訂正

- launch「commit 済み 116 dir」→ 118 dir (r8 の 116 + 8ac9b8bb で commit された 10-12 の対)。`git ls-files 'results/raw/*/SESSION.json'`。
- launch「Mac と iPhone の record には `conditions.textCheck` が無い (summary の mac / ios 行の text_check は全部空)」→ Mac の executorch-mlx 56、executorch-xnnpack 56、onnxruntime-genai-cpu 24、onnxruntime-genai-webgpu 25 行は runner の check を持つ (`results/summary/device-runs.csv`)。その cell は screen しない。
- launch の commit path の一覧に `results/summary/README.md` が無い → 仕様 2 の 2 文は build_summary.py が書く README の段なので、index から作り直した README を 77a3fdd0 に入れた (CI の summary-fresh)。device-runs.csv は byte 同一。
- launch (b)「scratch clone (MAIN の HEAD から)」→ MAIN の HEAD は途中で 0b38a1f2 に進んだ (Mac の LiteRT-LM pin v0.16.0)。① この branch の clone と ② main 0b38a1f2 + この branch で 2 回回した。verdict 以外は同じ。
- launch (a)「selftest 全部 exit 0」→ この worktree では全部 0。main 0b38a1f2 の上では session_check_selftest が r10 の前から落ちる (提案 1)。
- launch 背景「P の check 4 本」→ check_regression は今の main の bench で既に FAIL (2) (S26 の lab-unit stand-in の 2 cell)、r10 の前から (`<scratch>/r10/page_main/`, 9288dd34)。

## 罠と袋小路

- zsh は `$dirs` (改行区切りの変数) を単語に割らない → checker に 1 つの引数で渡って usage (exit 2)。118 dir の一覧は `bash -c '…'` の中で渡した (memory の zsh の罠と同じ)。
- zsh で `echo ======` は `=` 展開で「===== not found」になり、`;` の後の command が走らない。区切り行は `echo "---"` か `print`。
- summary の行の比較で (source, timestamp) を key にすると 89 本が重なる (1 本の .jsonl に秒が同じ record) → 偽の「他の列の差」が出る。行の多重集合で比べる。
- P の check を、P を build した時とは別の状態の bench (`EDGE_LLM_BENCH`) に向けると text_checked_n の偽の差が出る (手順の前の build を手順の後の clone で check した)。build と check は同じ bench の状態で回す (手順の前用に別の clone を作った)。
- `git clone --shared` の scratch clone の中では `git config user.email` を clone の local に置いた (scratch の commit 用)。
- selftest の fixture が lock を git HEAD から読む作りなので、main の lock が動くと Mac の LiteRT-LM cell を持つ合成 sitting は全部 pin-drift になる。新しい case は LiteRT-LM の pin を読まない arm で作る。

## op と delegate の観察

なし (端末も GPU / NPU も使っていない。速度も backend も測っていない。`K/SPEED_LADDER.md` は対象外)。

## 使った環境

- Mac Studio (M4 Max)、macOS (Darwin 27.0.0)、python3 3.14.6 (`~/.pyenv/shims/python3`)。venv なし、標準 library だけ。git の worktree `~/code/edge-llm-bench-wt-autopilot` (branch bench-autopilot)、scratch clone は `git clone --shared`。
- device は使っていない (adb / devicectl / gcloud / docker なし)、hold なし。夜の job は Mac (2026-10-19-dashboard-v1-m4max)・S26・iPhone 18 Pro で計測中だった。重い物は回していない (POST の dry run は `taskpolicy -b`)。`render_check.py` は回していない。
- P (`~/code/litert-bench-dashboard`, HEAD 8100b64) は読むだけ、build の出力は scratch。P の working tree は前からある untracked `.DS_Store` だけ (触っていない)。

## 残した file

この round が作った物:

- `results/raw/2026-10-18-bench-autopilot-dev/ROUND10.md` (この file、commit する)。
- `<scratch>/r10/` = `/private/tmp/claude-501/-Users-USER-code-edge-llm-bench-wt-autopilot/67679779-b964-40da-b948-78abe32ad584/scratchpad/r10/` (全部消してよい):
  - `reh/` (346 MB、clone ①: 手順の commit 32f72215 が載っている) — 消してよい。
  - `reh2/` (clone ②: main 0b38a1f2 + この branch の merge + 手順の commit eed02049) — 消してよい。
  - `page_before/`, `page_after/`, `page_after2/`, `page_main/` (P の build と check の出力) — 消してよい。
  - `baseline/`, `after/` (selftest の log、(c) の JSON) — 消してよい。
  - `step5.sh`, `step5_message.txt` (上の手順と文案の元)、`postd.log` ((d) の log)、`ios_main.json` (iPhone の 22 dir の読み)、`*_check*.json|md`、`commit*.txt` — 消してよい。
- MAIN と P には何も書いていない。この worktree の `results/raw` に text_screen.json は無い ((c) は `--no-text-screen`)。
