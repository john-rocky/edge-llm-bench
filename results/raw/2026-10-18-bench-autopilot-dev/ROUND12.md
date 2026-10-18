# Round r12 — session checker selftest independent of the registry state (which platform's LiteRT-LM pin is newest) — worker `edge-llm-bench-wt-autopilot-eb [b00548]` (Opus 5.5), started 2026-10-19 04:34 JST

Supervisor: `edge-llm-bench-55 [4f120b]`. cwd ~/code/edge-llm-bench-wt-autopilot, branch bench-autopilot at main 07b339a6 (reset by the supervisor before the launch). Mac only: no adb, no devicectl, no build; the night job measures on this Mac during the round.

## 結果 (要約)

- `scripts/session_check_selftest.py` は registry のどの platform が遅れていても通る形になった (5b11ac48): generic な case は llama.cpp の cell、protocol-off だけ LEADER (pin が最新の platform、出力の先頭に理由 1 行)、lab unit は Android が遅れたら NPU の side build、全 case が「期待の外の規則が無い」を verdict の前に確かめる。
- (a) 今の lock で exit 0 (58 ok)。(b) registry の 11 形 (launch の 2 形を含む、Android 遅れ・default_tag 先・Android だけ・過去の lock 3 本) で全部 exit 0。(c) 3 本 exit 0。(d) data-pipeline の 19 step を Python 3.11 で exit 0。case は減っていない (`ok(` 50 → 51、全 section が走る registry で 60 check)。
- 夜の job の Mac の cell との重なり 3 回 (経過に時刻と数字): ① 検証の full clone 11 本 (3.7 GB、通常優先度) が llama.cpp Gemma 4 E4B short-chat の retry と (05:04 に監督へ報告 → retake なし: 今夜の Mac sitting は engine-stamp で止まり、今日手で測り直す)、② sparse の検証が cooldown を越えて MLX OptiQ E4B 1K と、③ cooldown を 300 s と決め打ちした runner の初版で (c) が ONNX Runtime GenAI の 3 cell と (②③ は background 優先度、同じ sitting なので別送りはしていない)。(d) は直した runner で全 step が cooldown の中。

## 下見

- `date` 2026-10-19 04:34:24 JST、HEAD 07b339a6 (= main)、tree clean。
- 今の lock (0b38a1f2 から): `arms.litert-lm` default_tag v0.16.0、mac v0.16.0 (since 2026-09-18)、ios v0.18.0 (since 2026-10-19)、android v0.18.0 (since 2026-10-15)、`android_pins.litert-lm` v0.18.0。NEWEST (2099 = since が全部過去) = v0.18.0。
- `python3 scripts/session_check_selftest.py` (HEAD): exit 1、47 ok / 11 FAIL / 1 skip (Mac の pin の section: mac の block が default_tag と同じ tag)。最後まで走る (TypeError なし)。落ちた 11 本 (どれも 2099 の Mac の LiteRT-LM Qwen3 1.7B cell が v0.16.0 を stamp → v0.18.0 より古い → pin-drift FAIL):
  1. `exit 0 when every dir passes (got 1)`
  2. `2099-01-01-dashboard-v1-m4max-mac: PASS (['pin-drift'])`
  3. `partial: HOLD (['partial', 'pin-drift'])`
  4. `verdict: HOLD (['pin-drift', 'verdict'])`
  5. `prompt-tokens: HOLD (['pin-drift', 'prompt-tokens'])`
  6. `gen-budget: HOLD (['gen-budget', 'pin-drift'])`
  7. `a FAILURES line, a LEVEL retry and the account name in a path: HOLD (['failures', 'flagged', 'pin-drift', 'user-name'])`
  8. `three allow-listed findings: PASS, still listed with their commit (['failures', 'flagged', 'pin-drift', 'user-name'])`
  9. `each names the allowing commit`
  10. `the same two checked together: PASS`
  11. `MLX's 1K text cell at 2523, llama-bench's protocol cell without a context, the LiteRT-LM context ladder at 4096 and the short-chat cells: no protocol-off, PASS (['pin-drift'])`
- 通っていたのに pin の規則を「ついでに」持っていた dir (HEAD の selftest が残した temp tree を checker で読み直した、`scratchpad/old_dirs.json`): pin-drift — 2099-04-01 (not-admitted)、2099-04-02 (session-missing)、2099-04-04 (big-file・secret)、2099-05-02 (pair-broken)、2099-08-03 (protocol-off): 期待は `rule in rules(r)` で、verdict はどちらでも FAIL なので見えなかった。engine-stamp — 2099-08-01 の iPhone の OLD の case (iPhone の pin v0.18.0 ≠ OLD v0.16.0、assert していない)。

## 決めた形

- **generic な case は llama.cpp**: `payload_dir` の既定 cell = llama.cpp `unsloth/Qwen3-1.7B-GGUF/Q4_K_M` short-chat、stamp は `LLAMA` (lock の `arms.llama.cpp.tag`、b8999)。履歴の `old-{i}-mac` 3 行も llama.cpp (Mac、`LLAMA`、19 token)。prompt-tokens と gen-budget の HOLD case、SESSION.json の無い dir も llama.cpp。根拠: CHECK の `check_cell_counts` (prompt-tokens / prompt-newtag) と `check_cell_text` (gen-budget) は arm を問わず全 cell に走る (`check_records`)。llama.cpp の registry pin は全 platform で 1 つの tag (`registry_pin`) なので、この cell は LiteRT-LM の pin を読まない = どの registry でも engine-stamp も pin-drift も鳴らない。LEADER の判定にも依らない。
- **LEADER** (import 時に committed の lock と pins file から計算、CHECK の関数は呼ばない。`pin_of` = `registry_pin` の LiteRT-LM の枝、`newest` = `newest_litert` を selftest の側で書き直したもの): Mac → iPhone → Android の順に、2099 (since が全部過去) の pin が `newest()` と同じ release の最初の platform。どれも違う時 (default_tag が全 platform の block より新しい = Apple の pin bump の後、rebuild の前) は、最初の since の前日に Apple の platform が default_tag を読むので (lock に android block がある時、その日の newest も default_tag) その日の Mac。それでも決まらなければ selftest は 1 行で FAIL する (since の無い block しか無い registry だけ。今の lock の block は全部 since を持つ)。理由は出力の先頭に 1 行: `--- LEADER, the platform of the LiteRT-LM-only cases: ios: its pin arms.litert-lm.ios.tag v0.18.0 is the newest LiteRT-LM release a platform's pin names on the 2099 dirs; Mac v0.16.0, iPhone v0.18.0, Android v0.18.0, default_tag v0.16.0`。
  - LEADER の record の形: mac = Mac の anchor + payload (MLX と cell)、ios = iPhone の anchor + payload (`IOS_DEVICE`)、android = lab unit の job sitting (DDP 形、litert-lm-gpu、`conditions.contextTokens`、`provenance.modelShaSource` device、返事は record に無い)。dir 名 `<日>-dashboard-v1-<device>-<po|pl>-<mac|ios|android>`。
  - LEADER に置いた case: protocol-off の FAIL case (protocol cell と 1K text cell) と、protocol-off の PASS case の LiteRT-LM context ladder。PASS case の MLX 2523 と llama-bench (context なし) は Mac の対のまま。根拠: protocol-off (`check_cell_protocol`) は LITERT_RUNTIMES の cell しか読まない = LiteRT-LM の pin を読む cell でしか作れない唯一の非 pin の規則。
- **DDP の lab unit の case**: Android の pin が NEWEST の間は litert-lm-gpu (stamp = `android_pins.litert-lm`)、遅れている時は litert-lm-npu (`registry_pin` = side build: engine-stamp は note、`check_pin_drift` は side build を読まない)。lab unit は Android なので LEADER には動かせない → arm を替える。理由は DDP の section の見出し行に出る。
- **pin の規則自身の case** (`clean(..., pin=True)`、期待は registry から計算): engine-stamp v9.9.9 (Mac の LiteRT-LM、どの pin とも違い、どの release より新しい = registry に依らない、今の形のまま)、pin-drift の OLD (iPhone、期待 = pin-drift ∪ 「OLD ≠ iPhone の pin」なら engine-stamp)、main@1dadd00c (engine-stamp)、Mac の block の section (since 後に default_tag: engine-stamp ∪ 「default_tag < NEWEST」なら pin-drift。since の前日: 「その日の newest > default_tag」なら pin-drift)、iPhone の section (since の日: なし、前日: pin-drift)。
- **`clean(r, expected, pin=False)`**: verdict を数える前に「live な規則 − 期待」が空かを見る。pin の規則がはみ出したら `  stray <dir>: [...] beyond what the case expects (LEADER …; the newest release …)` を出す。pin の case でない case (pin=False) が期待に pin の規則を入れていたら、それ自体を失敗にする (受け入れ基準 2 の機械的な番)。verdict を見る assert 全部 (33 箇所) に掛けた。
- その他: PINS も `committed()` (HEAD) から読む (checker は registry を git から読む; 前は disk の file)。cell の .jsonl 名は Mac の runner の付け方 (`llama_cpp_unsloth_Qwen3-1_7B-GGUF_Q4_K_M_short-chat.jsonl`)。
- case の数: `ok(` の呼び出し 50 → 51 (+1 は LEADER が無い時だけ走る失敗の行)。走る check は、条件付きの section が全部走る registry で 60 (S2・S3・4d5b60b1 = r10 の 60 と同じ)、pin の section の前提が無い registry では skip の行を出して減る (今の lock: 58 + skip 1 = Mac の section の 2 本)。

## 結果

### (a) 今の lock (REPO)

最終の code (5b11ac48) で `python3 scripts/session_check_selftest.py` を REPO で (05:27:57、26.2 s、`taskpolicy -b`、Mac の 300 s の cooldown の中。04:56 の 1 回は self-review の修正前の版):

```
--- LEADER, the platform of the LiteRT-LM-only cases: ios: its pin arms.litert-lm.ios.tag v0.18.0 is the newest LiteRT-LM release a platform's pin names on the 2099 dirs; Mac v0.16.0, iPhone v0.18.0, Android v0.18.0, default_tag v0.16.0
…
  skip  the lock has no arms.litert-lm.mac block with another tag and a since day
…
  ok  a path that is not a directory: exit 2 (got 2)

selftest OK
```

exit 0、58 ok、0 FAIL、0 stray、1 skip。

### (b) registry の 11 形 (scratch の sparse clone で lock / pins を書き換えて commit、`scratchpad/shapes.py`、05:07:53-05:12:48)

S1 = launch の「Mac が最新で iPhone が遅れる」(mac と ios の tag を入れ替え)、S2 = 「全部同じ」(3 platform の block が v0.18.0)。H- は lock と pins file をその commit のものに戻した形。

| 形 | default_tag | mac (since) | ios (since) | android block / pins | LEADER | lab unit の arm | ok | skip | exit |
|---|---|---|---|---|---|---|---|---|---|
| S0 今 | v0.16.0 | v0.16.0 (09-18) | v0.18.0 (10-19) | v0.18.0 / v0.18.0 | ios | gpu | 58 | 1 | 0 |
| S1 Mac 先・iPhone 遅れ | v0.16.0 | v0.18.0 | v0.16.0 | v0.18.0 / v0.18.0 | mac | gpu | 58 | 1 | 0 |
| S2 block 全部同じ | v0.16.0 | v0.18.0 | v0.18.0 | v0.18.0 / v0.18.0 | mac | gpu | 60 | 0 | 0 |
| S2b default も同じ | v0.18.0 | v0.18.0 | v0.18.0 | v0.18.0 / v0.18.0 | mac | gpu | 55 | 3 | 0 |
| S3 Android 遅れ | v0.16.0 | v0.18.0 | v0.18.0 | v0.16.0 / v0.16.0 | mac | npu | 60 | 0 | 0 |
| S4 default_tag だけ先 | v0.19.0 | v0.16.0 | v0.18.0 | v0.18.0 / v0.18.0 | mac (2026-09-17) | npu | 57 | 2 | 0 |
| S5 Android だけ先 (block なし) | v0.16.0 | — | — | v0.18.0 / v0.18.0 | android (DDP 形) | gpu | 56 | 2 | 0 |
| S6 Mac だけ先 | v0.16.0 | v0.19.0 | v0.18.0 | v0.18.0 / v0.18.0 | mac | npu | 58 | 1 | 0 |
| H-d33ffa53 (10-15) | v0.16.0 | — | — | v0.18.0 / v0.18.0 | android (DDP 形) | gpu | 56 | 2 | 0 |
| H-dad937b1 (10-18) | v0.16.0 | v0.18.0 (10-12) | — | v0.18.0 / v0.18.0 | mac | gpu | 58 | 1 | 0 |
| H-4d5b60b1 (10-19 03:17) | v0.16.0 | v0.18.0 (10-12) | v0.18.0 (10-19) | v0.18.0 / v0.18.0 | mac | gpu | 60 | 0 | 0 |

全部 0 FAIL・0 stray。skip は前提の無い pin の section だけ (Mac の block が default_tag と同じ / default_tag より新しい pin が無い / ios の block が NEWEST でない)。S4 の LEADER の行: `mac: its pin arms.litert-lm.default_tag v0.19.0 is the newest LiteRT-LM release a platform's pin names on 2026-09-17 (on the 2099 dirs no platform's pin is the newest release, v0.19.0)`。

### (c) 触らない selftest 3 本 (REPO、`python3` = 3.14.6、`taskpolicy -b`、05:19:20-05:21:01)

```
c-dashboard_post_selftest: start 05:19:20, 63.8 s, exit 0, last: selftest OK
c-dashboard_job_selftest: start 05:20:24, 26.6 s, exit 0, last: selftest OK
c-regression_watch_selftest: start 05:20:51, 10.1 s, exit 0, last: selftest OK
```

3 本とも exit 0。ただし Mac の cooldown の中だけで回すつもりが、runner (`scratchpad/in_cooldowns.py` の初版) が「cooldown は 300 s」と決め打ちしていた: ONNX Runtime GenAI の cell は cooldown 30 s で、3 本は Qwen3-0.6B の cpu short-chat (05:19:49 開始)、webgpu short-chat (05:20:24)、cpu 1K (05:20:59) の 3 cell と重なった (background 優先度)。経過に記録、runner は直した (下の (d) はその版)。

### (d) data-pipeline.yml と同じ command 列 (REPO、05:27:57-05:36:48)

CI と同じ順。`python` / `python3` = uv の cpython 3.11.13 (CI の 3.11、huggingface_hub なし)。release asset の取得の step の代わりに `BENCH_ANDROID_BIN_DIR` = MAIN の `android/bin` (v0.18.0 を含む、読むだけ)。各 step は `taskpolicy -b` で、Mac の cooldown の window に収まる時だけ起こした (runner の行の「inside the window」= その step の間に `=== CELL` 行が出ていない)。

```
d01-validate_cells: start 05:28:23, 1.0 s, exit 0, inside the window, last: OK matrices/vl-response-v1.cells
d02-validate_cells-anchor: start 05:28:24, 1.0 s, exit 0, inside the window, last: OK matrices/anchors.cells
d03-build_summary: start 05:28:26, 3.0 s, exit 0, inside the window, last: wrote …/results/summary/README.md
d04-summary-git-diff: start 05:28:29, 1.0 s, exit 0, inside the window, last:
d05-render_leaderboard: start 05:28:30, 1.0 s, exit 0, inside the window, last: LEADERBOARD.md changed: the local copy restored
d06-render_dashboard-check: start 05:28:31, 2.0 s, exit 0, inside the window, last: rendered 299 device-cells from 138 file cells into …/dashboard-check-af6md77v
d07-test_render_rules: start 05:28:33, 1.0 s, exit 0, inside the window, last: OK
d08-test_import_native_benchmark: start 05:28:34, 2.0 s, exit 0, inside the window, last: OK
d09-android-bench-selftest: start 05:28:36, 143.0 s, exit 0, inside the window, last: selftest OK
d10-android-test_longctx1024: start 05:30:59, 1.0 s, exit 0, inside the window, last: OK
d12-ddp-selftest: start 05:33:13, 48.3 s, exit 0, inside the window, last: ddp selftest OK (76 checks)
d13-dashboard_job_selftest: start 05:34:01, 8.1 s, exit 0, inside the window, last: selftest OK
d14-session_check_selftest: start 05:34:09, 20.1 s, exit 0, inside the window, last: selftest OK
d15-dashboard_post_selftest: start 05:34:30, 59.4 s, exit 0, inside the window, last: selftest OK
d16-regression_watch_selftest: start 05:36:29, 4.0 s, exit 0, inside the window, last: selftest OK
d17-autopilot_selftest: start 05:36:34, 11.1 s, exit 0, inside the window, last: autopilot selftest OK (58 checks)
d18-py_compile: start 05:36:45, 2.0 s, exit 0, inside the window, last:
d19-bash-n: start 05:36:47, 1.0 s, exit 0, inside the window, last:
done 05:36:48
```

19 step 全部 exit 0 (d11 = asset の取得は上の置き換え)。d14 (3.11): 58 ok、0 FAIL、1 skip、0 stray、LEADER ios。d04: `git diff --exit-code results/summary/` は差なし (build_summary は REPO の disk から作り直したが、REPO の無視された file = `ddp-raw/` と execution 階層の logcat は record を持たない = index から作るのと同じ)。d05: render_leaderboard が書いた LEADERBOARD.md は REPO にあった local の版と違ったので、前に取った写しに戻した (gitignore の local の file、`cp -p`)。(d) の前後で REPO の `git status --porcelain --ignored` は同一。

## commit

- 5b11ac48 `scripts/session_check_selftest.py` (318 行追加 / 121 行削除)。明示 path、帰属行なし。push / merge していない。

## 提案

1. **CHECK の `newest_litert` と default_tag (別 round)**: default_tag は Mac と iPhone の block が両方効いている日でも候補に入る。runbook の順 (bootstrap.sh の `LITERTLM_TAG` と default_tag を上げてから Mac / iPhone を rebuild) で新しい release に上げると、rebuild までの間は default_tag を走らせている platform が無いのに、全 platform の LiteRT-LM cell が pin-drift で FAIL する (S4 の形)。selftest は「最初の since の前日の Mac」で protocol-off を作れるようにしたが、checker の側は「default_tag はそれを読む platform (その日に block が効いていない Mac / iPhone) がある時だけ数える」が筋かもしれない。判断は監督 / owner。
2. **prompt-newtag の case が selftest に無い** (launch の (2) に名前がある)。LEADER の上に 1 本足せる: 同じ build の履歴なし・別 build (OLD) の履歴が 10 % 超離れる → HOLD prompt-newtag、10 % 以内 → note。今回は目的 (registry に依らない) の外なので入れていない。
3. **iPhone の pin の section** は ios の block が NEWEST の時だけ走る (S1・dad937b1 では skip)。Mac の section と同じく期待を registry から計算すれば、ios の tag が default_tag と違う registry ならいつでも走らせられる。
4. **CI の条件の通し**: (d) は Python 3.11.13 (uv の cpython、huggingface_hub なし) で回した。release asset の download は回さず、`BENCH_ANDROID_BIN_DIR` = MAIN の `android/bin` (読むだけ) にした: asset の取得の行は通していない。

## 経過

- 04:34 ListAgents (this session = `edge-llm-bench-wt-autopilot-eb [b00548]`), date, HEAD 07b339a6, tree clean. Next: read the selftest and the checker's pin rules, run the selftest under the current lock.
- 04:36 baseline: `session_check_selftest.py` exit 1, 11 FAIL, runs to the end (no TypeError at HEAD). The night job holds the Mac (`bench_matrix_mac.sh run matrices/dashboard-text-v1.cells` since 02:00), the S26 and the iPhone 18 Pro: every selftest run below goes through `taskpolicy -b`.
- 04:50 read CHECK (registry_at, registry_pin, newest_litert, check_records, check_cell_counts / text / protocol, kind_of), docs §2, OPERATIONS runbook, the lock's last four states (d33ffa53 Android only ahead; dad937b1 / 4d5b60b1 Mac ahead; 0b38a1f2 iPhone + Android ahead). Shape decided (below). Next: write SELFTEST.
- 04:56 SELFTEST written; (a) under the current lock: exit 0, 58 ok, 1 skip (04:56:16-21, in the cooldown after the Mac sitting's MLX OptiQ cell failed to load).
- 04:57:15-05:02:00 the 11 registry shapes in scratch clones (`scratchpad/shapes.py`): all exit 0, 0 FAIL, 0 stray. Incident: each clone was a full checkout (346 MB, 12.8k files; 3.7 GB in all, git at normal priority), against the launch's < 100 MB and "nothing heavy": the Mac sitting's `llama.cpp unsloth/gemma-4-E4B-it-GGUF/Q4_K_M short-chat` retry ran inside it (4 runs 05:00:09-05:00:15, decode 90.1 / 82.8 / 88.9 / 88.6, SPREAD 6.9, kept ⚠; its attempt1 before the load 04:56:59-04:57:04: 89.3 / 86.9 / 89.1 / 82.6, SPREAD 7.5). 05:04 reported to the supervisor (SendMessage, case 2). Next: sparse clones only (no results/), delete the 3.7 GB at background priority inside a cooldown, self-review the diff.
- 05:05 supervisor: no retake of that cell (the retry's runs sit in attempt1's band; tonight's Mac sitting is held on engine-stamp anyway and the Mac weekly set is re-measured by hand today after the r9 rebuild); clones sparse, deletion in a cooldown at `taskpolicy -b`, writes besides the selftest within 100 MB. `scratchpad/rm_in_cooldown.sh` started in the background (waits for the sitting's next `=== cooldown` line).
- 05:07 self-review fixes (cell files named as the Mac runner names them, `llama_cpp_…`; the pins file read by its git path; the no-LEADER line names the 2099 pins). Sparse clone smoke test (scripts / android / matrices / ops + root files: 6.8 MB, 308 files, 19 s with the selftest) S0 exit 0, 58 ok. 05:07:53 all 11 shapes again in sparse clones, in the background, inside the cooldown after the LiteRT-LM E4B 1K cell.
- 05:12:48 the 11 sparse shapes: all exit 0, 0 FAIL, 0 stray (75 MB for the 11 clones). It ran past the cooldown (05:05:2x-05:10:23): the Mac's `mlx-swift mlx-community/gemma-4-e4b-it-qat-OptiQ-4bit long-context-1024-gen256` cell ran 05:10:29-05:10:40 beside it (one background-priority selftest + one 6.8 MB clone at a time; its 4 runs 91.92 / 91.49 / 91.70 / 91.78 tok/s, no gate line). The 3.7 GB of full clones deleted 05:10:42-05:11:53 inside the next cooldown (`taskpolicy -b rm`). From here every run goes through `scratchpad/in_cooldowns.py` (a step starts only when its estimate fits the 300 s cooldown whose line appeared last).
- 05:14 (c) queued: the three untouched selftests, `python3`, in REPO, inside the next cooldown.
- 05:21 (c) all exit 0, but overlapped: the runner took every `=== cooldown` line for 300 s and timed a window from when it next looked (after a step), not from the line; the sitting had reached the ONNX Runtime GenAI cells (cooldown 30 s): `dashboard_post_selftest` 05:19:20-05:20:24 beside the Qwen3-0.6B cpu short-chat cell (05:19:49), `dashboard_job_selftest` 05:20:24-05:20:51 beside the webgpu short-chat cell (05:20:24), `regression_watch_selftest` 05:20:51-05:21:01 into the cpu 1K cell (05:20:59); all at background priority. Not sent separately: the supervisor's 05:05 answer covers this sitting (held on engine-stamp, re-measured by hand today). Runner rewritten: reads the log every second while a step runs too, a window = the line's own seconds from the moment the line appears (cooldown or gate), closed by a `=== CELL` line, a step starts only when est + 10 s fits, and each step line says whether a CELL started during it.
- 05:22 commit 5b11ac48 (SELFTEST only). (d) queued with the rewritten runner: the data-pipeline steps in REPO under Python 3.11.13 (uv) as `python`, plus (a) with `python3` first.
- 05:27:57-05:36:48 (a) and (d) ran: 20 steps, every one exit 0 and inside a window (the 300 s cooldown after the ORT Qwen3-1.7B cells, the gate's 180 s before the Qwen3-4B cpu short-chat re-run, the 300 s after it); REPO's `git status --porcelain --ignored` the same before and after, LEADERBOARD.md put back. Next: this file, the lint, the commit, the round close message.

## 訂正

- launch 背景「l.307 付近で `TypeError`」→ HEAD 07b339a6 の selftest は TypeError なしで最後まで走り、11 FAIL で exit 1。TypeError は 0b38a1f2 の時点 (15b7866e の前) の話で、15b7866e が allow-list の case の「each names the allowing commit」を失敗の check に変えている (K/ROUND10.md 提案 1、15b7866e の message)。
- launch (2)「prompt-tokens / prompt-newtag / gen-budget / 履歴の `old-{i}-mac` 行は LiteRT-LM 固有の規則の case」→ CHECK では arm を問わない: `check_records` が全 cell に `check_cell_counts` (prompt-tokens、prompt-newtag) と `check_cell_text` (gen-budget) を回す。LITERT_RUNTIMES しか読まないのは `check_cell_protocol` (protocol-off) と `check_pin_drift` だけ (scripts/session_check.py)。→ それらは llama.cpp に置いた (決めた形)。
- launch (2) の列の prompt-newtag → HEAD の selftest に prompt-newtag の case は無い (`grep prompt-newtag scripts/session_check_selftest.py` = 0 件)。提案 2。
- launch (2)「DDP の case も LEADER で作る」→ lab unit は Android なので、Android が遅れている時に LEADER (Mac / iPhone) へは動かせない。arm を NPU の side build に替えた (S3・S4・S6 で通した)。
- 受け入れ基準 2「明示の 2 case だけ」→ pin の規則を期待に持つ case は pin の section の 6 箇所 (engine-stamp v9.9.9、pin-drift OLD、main@1dadd00c、Mac の block の 2 本、iPhone の block の前日)。全部 pin の規則自身の case で、`pin=True` を付け期待を registry から計算した。それ以外の case は `clean` が pin の規則を期待に入れる事を許さない。HEAD の OLD の case は engine-stamp を assert せずに持っていた (iPhone の pin v0.18.0 ≠ OLD v0.16.0、`scratchpad/old_dirs.json`)。
- launch 背景「generic case 10 本の期待が崩れ」→ 落ちた check は 11 本・9 case (PASS の対 (2 check)、HOLD の 4 case、FAILURES の case、allow-list (2 check)、対の PASS、protocol-off の PASS)。その他に通っている 5 本の check の dir も pin-drift を持っていた (2099-04-01 / 04-02 / 04-04 / 05-02 / 08-03、`rule in rules(r)` で FAIL の verdict が同じだったので見えない、`scratchpad/old_dirs.json`)。
- 点検「disk 見積 < 100 MB」→ 私の最初の検証が 3.7 GB を書いた (full clone 11 本)。前提の差ではなく私の誤り: 罠と袋小路 1。

## 罠と袋小路

- **この repo の full clone は 1 本 346 MB・12.8k file** (results/ が 333 MB)。`git clone --shared` を 11 本で 3.7 GB、4.7 分、git は通常優先度で、計測中の Mac の 1 cell の retry と重なった。selftest の検証は sparse で足りる: `git clone --shared --no-checkout -b <branch> <repo> <dst>` → `git -C <dst> sparse-checkout set --cone scripts android matrices ops` → `git -C <dst> checkout -q <branch>` = 6.8 MB・308 file (root の file は cone で付いてくる)。
- **`taskpolicy -b` を selftest だけに付けても clone・checkout・rm は通常優先度**。step ごとに包む (`scratchpad/in_cooldowns.py` は各 step を `taskpolicy -b` で起こす)。
- **sitting の cooldown は cell ごとに違う**: 多くは 300 s、ONNX Runtime GenAI の cell は 30 s、gate の再測の前は 180 s。window は「その行が書かれた時刻からその行の秒数」で数え、`=== CELL` 行で閉じる。step の合間にだけ log を見る runner は、step 中に書かれた cooldown 行を step の終わりの時刻で数えてしまい、window を長く見積もる (05:19-05:21 の重なり)。
- **registry の形を変えて selftest を回すには scratch clone で commit する**: selftest の `committed()` と checker の `registry_at` はどちらも git から registry を読む。disk の file を書き換えるだけでは効かない。
- zsh: `git show $c:environment.lock.json` は `$c:e` が拡張子の修飾子になり `nvironment.lock.json` を探す → `"${c}:environment.lock.json"`。
- cooldown を待つ watcher (`rm_in_cooldown.sh`) は起動の瞬間に数えた行を「過去」にするので、cooldown が始まった直後に起こすと次の cooldown まで待つ (05:06 に起こして 05:10:42 に消した)。

## op と delegate の観察

なし (端末、GPU / NPU を使っていない。変換も実行時の版の比較もしていない。速度も backend も測っていない = `K/SPEED_LADDER.md` は対象外)。

## 使った環境

- この Mac (macOS 27、Darwin 27.0.0)。端末なし、hold なし、端末の queue に入っていない。夜の job が同じ Mac・S26・iPhone 18 Pro で計測中 (Mac の sitting `2026-10-19-dashboard-v1-m4max-mac`)。
- python3 = Homebrew 3.14.6 ((a)(b)(c))。CI の 3.11 に合わせて (d) は uv の cpython 3.11.13 (`~/.local/share/uv/python/cpython-3.11.13-macos-aarch64-none`、huggingface_hub なし) を `python` / `python3` として PATH の先頭に置いた (`scratchpad/py311bin/` の symlink)。venv なし、stdlib だけ。
- git 2.54.0 (Apple Git-157)。scratch clone は `git clone --shared` (object は MAIN の .git を alternates で読むだけ、commit は clone の側)。
- 04:56 以降の selftest は全部 `taskpolicy -b`。04:35-04:38 の 2 回 (下見) は通常優先度 (Mac は xnnpack の cell の cooldown 中)。

## 残した file

- `scripts/session_check_selftest.py` (5b11ac48): この round の成果物。
- `results/raw/2026-10-18-bench-autopilot-dev/ROUND12.md`: この file。
- scratchpad (この session の作業 dir、repo の外):
  - `shapes.py` — registry の形ごとに sparse clone を作って lock / pins を書き換え commit し、selftest を回す harness。
  - `in_cooldowns.py` — step を Mac の cooldown の中だけで `taskpolicy -b` で回す runner (書き直した版)。`rm_in_cooldown.sh` — cooldown の中で dir を消す watcher。
  - `steps_c.json`・`steps_d.json`・`c_out/`・`d_out/` — (c)(d) の step と各 step の全出力。`status_before_d.txt`・`status_after_d.txt` — (d) の前後の REPO の `git status --porcelain --ignored` (同一)。
  - `b2/` — sparse clone 11 本 (75 MB) **消してよい**。`b2_summary.txt` — (b) の要約。`s0_run1.txt` — 修正前の版の (a)。`old_dirs.json` — HEAD の selftest の dir を checker で読み直した結果。
  - `py311bin/` — 3.11 への symlink 2 本 **消してよい**。`LEADERBOARD.md.bak` — (d) の render_leaderboard の前の REPO の LEADERBOARD.md の写し **消してよい**。
- `/var/folders/…/T/session-check-selftest-*` 2 本 — HEAD の selftest が下見の失敗で残した temp tree **消してよい**。
