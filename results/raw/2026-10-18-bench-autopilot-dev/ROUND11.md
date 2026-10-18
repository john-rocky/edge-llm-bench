worker: edge-llm-bench-wt-autopilot-q06-02 [c45722] (Opus 5.5, effort max); supervisor: edge-llm-bench-55 [4f120b]

# Round 11 — Qwen3 0.6B LiteRT-LM page cells: from `qwen3_0_6b_mixed_int4.litertlm` to `Qwen3-0.6B_dynamic_wi4b32_afp32.litertlm`

## 下見

- `date` 2026-10-19 05:17:45 JST; worktree `~/code/edge-llm-bench-wt-autopilot-q06`, branch `qwen06-bundle`,
  HEAD 8dae71e6 (= main at launch), tree clean.
- Apple catalog `ios/BenchmarkApp/Sources/Models/ModelCatalog.swift`: REPO, MAIN and SIDE byte-identical
  (sha256 bec69a57…478969e, 91,850 B; read 05:17 and again 06:03).
- Android label table has the new file (`android/bench/run_cell.py` l.1591 `ANDROID_QUANT_LABELS`).
- Three premises did not hold (section 訂正 1-3); one message to the supervisor at 05:25, decisions at 05:3x:
  - D1: drop `exclude-on=pixel8a,s26:hub-bundle-chat-template-predates-litert-lm-018-prompt-dropped-issue-3688` from
    the moved rows (its reason names the old bundle).
  - D2: move the Android LiteRT-LM anchor rows to the new file too (they share the page cell's key). Condition read
    and quoted: `scripts/dashboard_job.py` l.712-714 "the primary anchor is a non-litert arm (the engine most often
    under test); its runtime's own anchor is recorded alongside, not gating" + `cells.sort(key=lambda c:
    c["runtime"] == "litert-lm")`; l.758 `primary = anchors[0]`; l.815 `p = details["anchors"][0]`, and every
    admission branch (anchor-short / anchor-collapse / anchor-thermal / nominal) reads `p` only;
    `scripts/session_check.py` `own_anchor_runs` (l.903-925) reads `cells[0]` too. On Android `anchors.cells` has
    litert-lm (l.14) and llama.cpp (l.15): after the sort the primary is llama.cpp. Holds.
  - D3: catalog untouched; the 12 Apple page rows move to the existing id
    `litert-community/Qwen3-0.6B/dynamic_wi4b32_afp32`; the Apple anchors keep `litert-community/Qwen3-0.6B`.

## 替える・据え置くの表

Source: `git show HEAD:<file> | grep -n litert-lm | grep -i 'qwen3-0\.6b\|qwen3_0_6b'` over every tracked
`matrices/*.cells` = 47 files; 12 changed, 35 kept. Line numbers are HEAD's.

| file | 行 | 判断 | 理由 |
|---|---|---|---|
| `anchors.cells` | 14 | file= 替えた | D2 (Android LiteRT-LM anchor; shares the GPU short-chat page key) |
| `anchors.cells` | 9, 12 | 据え置き | iPhone / Mac LiteRT-LM anchors (D3: catalog id unchanged) |
| `dashboard-text-v1.cells` | 60, 61, 63, 64 | file= 替えた, exclude-on 削除 | Android page rows (D1) |
| `dashboard-text-v1.cells` | 121, 125, 200, 206 | id → `/dynamic_wi4b32_afp32` | iPhone / Mac page rows (D3) |
| `dashboard-text-v1-android-a.cells` | 11, 12, 14, 15 | file= 替えた, exclude-on 削除 | storage half A, byte-identical to the parent |
| `dashboard-longctx1024-v1-android-a.cells` | 15 | file= 替えた | anchor row (D2) |
| `dashboard-longctx1024-v1-android-a.cells` | 18, 19 | file= 替えた, exclude-on 削除 | the team page's Android 1K source |
| `dashboard-longctx1024-v1-android-b1.cells` | 15 | file= 替えた | anchor row only (D2) |
| `dashboard-longctx1024-v1-android-b2.cells` | 15 | file= 替えた | anchor row only (D2) |
| `dashboard-protocol1024-v1-android.cells` | 9 | file= 替えた | anchor row (D2) |
| `dashboard-protocol1024-v1-android.cells` | 12, 13 | file= 替えた | protocol page rows (they never carried exclude-on) |
| `dashboard-ddp-v1-android-s26.cells` | 21-24; header l.15-16 | file= 替えた, exclude-on 削除; header rewritten | DDP mirror of the text rows (its header said the route skips them) |
| `dashboard-longctx1024-v1.cells` | 20, 57 | id 替えた | Mac / iPhone 1K page rows (D3) |
| `dashboard-longctx1024-v1.cells` | 18, 55 | 据え置き | anchors |
| `dashboard-protocol1024-v1.cells` | 11, 20 | id 替えた | Mac / iPhone protocol page rows (D3) |
| `dashboard-protocol1024-v1.cells` | 10, 19 | 据え置き | anchors |
| `dashboard-coreai-v1-mac.cells` | 41, 42 | id 替えた | same keys as the 1K / protocol files (its header) |
| `dashboard-coreai-v1-mac.cells` | 36 | 据え置き | anchor |
| `dashboard-coreai-v1-ios.cells` | 44, 45 | id 替えた | same keys as the 1K / protocol files |
| `dashboard-coreai-v1-ios.cells` | 39 | 据え置き | anchor |
| `dashboard-aa-v1-ios.cells` 17; `-i1` … `-i9` 9 | | 据え置き | iPhone anchor row only |
| `dashboard-longctx-v1-android-s26.cells`, `-qwen06.cells` | 24-31 | 据え置き | 2K ladder: 26-31 already the new file; 24-25 are `exclude=bundle-kv-2048…` rows of the old file |
| `dashboard-longctx-v1-android-s26-gpudiag.cells` 5; `-smoke.cells` 6-9 | | 据え置き | ladder diagnostics, already the new file (`../models/` path) |
| `dashboard-longctx-v1.cells` | 53-60 | 据え置き | Mac 2K ladder: 55-60 already the new id; 53-54 `exclude=` |
| `dashboard-0180-pixel8a-p1` 12-13, `-p2a` 12, `-p2b` 12; `dashboard-0180-s26-s1` 12-13, `-s2` 12-13 | | 据え置き | dated one-off splits |
| `catalog-int4-vs-int8-android` 48-49, `-pixel8a` 16-17; `catalog-x13-gpu-vs-cpu-pixel8a` 38-39, 46-47, `-s26` 33-34, 41-42 | | 据え置き | dated catalog comparisons |
| `qwen3-gpu-flags-2026-09-10.cells` | 38-44, 48-53, 57-62 | 据え置き | dated |
| `release-regression-litert.cells` | 13, 19, 24, 25 | 据え置き | its baseline campaigns ran the old file (提案 6) |
| `android-first-session.cells` | 8, 12 | 据え置き | a new device's first session, not weekly (提案 5) |
| `apple-warm-matrix.cells` 9; `endurance-mac.cells` 18 | | 据え置き | not page cells |
| `minicpm5-2b-crossarm` 23, `-iphone-cold` 12, `-iphone` 12 | | 据え置き | anchor rows of dated lanes |
| `ad-hoc-example.cells` 2-3; `profile-example-android.cells` 2-3 | | 据え置き | examples |
| `dashboard-npu-litert-v1-android-s26.cells` | 27, 28 | 据え置き | another model (`Qwen/Qwen3-0.6B` own NPU export) |

Other step-1 hits: `ModelCatalog.swift` l.554-562 (`litert-community/Qwen3-0.6B`, mixed INT4) and l.571-580
(`litert-community/Qwen3-0.6B/dynamic_wi4b32_afp32`): unchanged (D3). `run_cell.py` l.1582 / l.1591: read only.
`docs/dashboard-cells-v1.md`: l.58 and l.78 (cell tables) and open question 1 updated, new section
"Qwen3 0.6B LiteRT-LM file (2026-10-19)"; the other hits are dated history. Validate: every row of the
12 changed files and both new files reads `OK`.

## catalog の diff(REPO と SIDE)

なし: D3 で catalog は触らない。REPO と SIDE は 06:03 にも sha256 bec69a57…478969e(MAIN と同一)、`diff` は空。
SIDE への書き込みなし。r9 の build に載せる物なし。

## 測り直しの cells 2 本と監督が打つ command

- `matrices/dashboard-q06-dynamic-android.cells`: the session anchor row of `dashboard-text-v1-android-a.cells`
  (llama.cpp), then 6 rows copied byte for byte from their weekly source (short-chat from `dashboard-text-v1.cells`,
  1K from `dashboard-longctx1024-v1-android-a.cells`, protocol from `dashboard-protocol1024-v1-android.cells`;
  the script asserted the 1K rows equal `dashboard-text-v1.cells`' too). No 4B-class row = same file on both phones.
  - `python3 scripts/dashboard_job.py s26 --cells matrices/dashboard-q06-dynamic-android.cells --suffix q06-dynamic --once`
  - `python3 scripts/dashboard_job.py pixel8a --cells matrices/dashboard-q06-dynamic-android.cells --suffix q06-dynamic --once`
- `matrices/dashboard-q06-dynamic-ios.cells`: the iPhone anchor row of `dashboard-text-v1.cells` (mlx-swift),
  then short-chat (`dashboard-text-v1.cells`), 1K (`dashboard-longctx1024-v1.cells`) and protocol
  (`dashboard-protocol1024-v1.cells`) under the new id, the task rows first (`bench_matrix_iphone.sh`
  `native_import` takes the campaign's task record of the same arm and model as `--like`).
  - `python3 scripts/dashboard_job.py iphone18pro --cells matrices/dashboard-q06-dynamic-ios.cells --suffix q06-dynamic --once`
  - the keeper route of `docs/dashboard-recurring-job-v1.md` §2 adds `--hold-held-by <keeper pid>` (and
    `BENCH_SITTING=1` on Android); `--suffix` gets its leading dash from the job (l.978).
- Mac: no file (launch). See 提案 2: the 05:30 firing took the Mac with MAIN's old cells.

## 18 Pro に新 file を置く path と source

`Documents/models/litert-lm/litert-community__Qwen3-0.6B/Qwen3-0.6B_dynamic_wi4b32_afp32.litertlm` in the app's
container (beside `qwen3_0_6b_mixed_int4.litertlm`, which the iPhone anchor still uses: keep it) ← Mac
`~/.cache/huggingface/hub/models--litert-community--Qwen3-0.6B/blobs/03e7da1eb1108b50dffaa9bb52cc7bcbad2eb0c66ca990267f480c1e545d2856`
(= `snapshots/e6687177e00897731e7716267eebd4eba0dde7c2/Qwen3-0.6B_dynamic_wi4b32_afp32.litertlm`, refs/main
e6687177; sha256 of the bytes = the blob name; 344,671,744 B). Why: both catalog ids share hfRepoId
`litert-community/Qwen3-0.6B`, and `HFDownloader.snapshot` (l.13-20) returns that directory without a download
while it holds any file.

## 確認の出力

- label: `ANDROID_QUANT_LABELS['Qwen3-0.6B_dynamic_wi4b32_afp32.litertlm']` and
  `guess_quant('/data/local/tmp/llmbench/models/litert-community_Qwen3-0.6B_Qwen3-0.6B_dynamic_wi4b32_afp32.litertlm')`
  both print `INT4 (dynamic, block-32 weights, FP32 act; GPU-graph build 2026-08-04)`.
- `python3 scripts/validate_cells.py matrices/*.cells`: 141 × `OK`, exit 0; `--require-anchor
  matrices/release-regression-*.cells matrices/anchors.cells`: exit 0; both new files with `--require-anchor`: OK.
- `python3 android/bench/selftest.py`: 245 ok, `selftest OK`, exit 0 (05:40:51-05:46:57, the final cells).
- CI step list (`.github/workflows/data-pipeline.yml`), all exit 0 on the final tree unless noted:
  validate (above); `build_summary.py` in a copy, `results/summary/*` 0 of 4 differ from HEAD; `render_leaderboard.py`;
  `render_dashboard.py --check` (299 device-cells from 138 file cells); `test_render_rules.py`;
  `test_import_native_benchmark.py`; `android/bench/test_longctx1024.py`; `android/ddp/selftest.py` 76 checks;
  `dashboard_job_selftest.py` 89; `dashboard_post_selftest.py` 54; `regression_watch_selftest.py` 50;
  `autopilot_selftest.py` 58; `py_compile`. `session_check_selftest.py` 47 ok / 11 FAIL = the same FAIL lines as a
  clean copy of HEAD 8dae71e6 (pin-drift, ROUND10 提案 1; fixed on main per the supervisor) — not this round's.
- Two selftests read the real cells and needed this round's counts (supervisor's go each time):
  `scripts/regression_watch_selftest.py` l.76 (its ANCHORS android row mirrors `matrices/anchors.cells`; HEAD 50/0,
  tree before the fix 49/1 on l.383 "a retake row identical to an anchor row is written once", after 50/0);
  `android/ddp/selftest.py` l.164, l.176-177, l.388 (counts planned from `dashboard-text-v1.cells`: akita-35
  12 jobs / 2 sessions / 8 exclude-on skips, m1q-36 20 / 3 / 0, caiman-35 12 / 2 and 8 key-unknown skips,
  (12 + 20) × 2 = 64 wrapper strings; HEAD 76/76, before the fix 69/76, after 76/76).
- Probe numbers in the docs, read from the records themselves
  (`MAIN/results/raw/2026-10-19-probe-q06-s26-android-android/app-path-android/*_run1.json` and `.log`):
  wi4b32 decode 76.52 tok/s, peak resident 860.96 MB, `Prefill Turn 1: Processed 19 tokens in 98.422344ms`;
  `Qwen3-0.6B.litertlm` 25.74, 753.27 MB, `19 tokens in 181.833646ms`.

## commit

One commit on `qwen06-bundle` with explicit paths (this file included): `git log -1 --format=%h --
results/raw/2026-10-18-bench-autopilot-dev/ROUND11.md`; the hash is in the round-close message. No push, no merge.

## 提案

1. Page and series key: add the artifact file to the cell key of `render_dashboard.build`, the team page's
   `build.py` (l.645 cells, l.1282 regression series) and the regression watch, and mark a file change in a
   series the way `engine_changed` marks an engine change. Until then a regression pair across 2026-10-19 that
   normalizes through the Android LiteRT-LM anchor compares two files.
2. Mac: the 05:30 firing took the Mac from MAIN (`dashboard_job.py auto` pid 12802 →
   `bench_matrix_mac.sh run matrices/dashboard-text-v1.cells` pid 13391), so its Mac 0.6B LiteRT-LM rows run the old
   id. After the merge the new id's Mac cells stay empty until another Mac sitting, and once this sitting is
   admitted the auto job skips the Mac until Monday. A file of the same shape would cover it: the Mac anchor row of
   `dashboard-text-v1.cells` (l.204 after this commit), its rows l.205 and l.211, and
   `dashboard-protocol1024-v1.cells` l.16.
3. Pixel 8a time: its 2026-10-15 slot sittings took 36.1 min (`0180-p1`: anchors + two short-chat rows) and 31.9 min
   (`0180-p2b`: anchors + one 1K row) in MAIN's `logs/dashboard-job/ledger.tsv`, so the 6-row file is about one and a half
   hours there, over the 45-minute slot size of §2. If the slot size applies, split it in three (short-chat / 1K /
   protocol), each with the anchor row.
4. Text: Android short-chat launches carry no text check (`run_cell.py` l.1488-1496) and the probe read the
   prompt-token count only. The 1K GPU row is the first reading of this file's 1K text on the S26 GPU; its 2K
   rows are `exclude=s26-gpu-garbage-text-at-2k-prefill` (v0.16.0) and the 1.7B sibling failed at 1K (open
   question 8). A failure shows as text-fail, not a rate.
5. `android-first-session.cells` l.8 / l.12 mirror the Android anchor and a CPU row on the old file: move them the
   same way before the next new Android device.
6. `release-regression-litert.cells` keeps the old file (rows 13, 19, 24, 25) so the next release pass compares
   like with like; move it after a pass whose baseline ran the new file.
7. The probe dir `results/raw/2026-10-19-probe-q06-s26-android-android/` is on MAIN's disk and not on main
   (`git log main -- <dir>` empty at 254c1c85); the new docs section cites its numbers: commit it with the merge, or
   the table loses its stored report.
8. `~/code/standup/knowledge/runtime-hazards.md` row `pre-018-template-drops-user-turn` says the page's chat cells
   of the file are excluded (bench 0ee7a28); after the merge the page cells left the file (knowledge is outside
   this round).
9. The DDP selftest counts and the regression-watch anchor fixture restate the current cells by hand; deriving them
   from `dashboard-text-v1.cells` / `anchors.cells` would let the next cells change pass without a selftest edit.

## 経過

- 05:17 launch read, ListAgents, `date`, HEAD.
- 05:25 step 1 grep done; three premise conflicts (exclude-on on the Android rows, the Android anchor sharing the
  page key, the Apple anchors following the catalog id); one message to the supervisor.
- 05:3x decisions D1 / D2 / D3; D2's condition read in `dashboard_job.py` (above).
- 05:3x rows swapped by a script asserting the per-file counts (Android 21 rows, Apple 12); the two re-measurement
  files written from the swapped source rows; validate 141 OK.
- 05:36-05:48 checks at `taskpolicy -b`: regression_watch 49/1 and ddp 69/76 traced to D2 / D1 (clean HEAD copies
  pass), the fixes tried in scratch copies; two messages, both approved.
- 05:55-06:0x docs (two), the fixes applied, the CI steps not yet run on the final tree run in a copy (QUIET_OK=1,
  light python, inside r9's window).
- 06:0x this file, round-close lint, commit.

## 訂正

- The launch kept the moved rows' other options ("他の option は不変"), but 12 Android rows carried
  `exclude-on=pixel8a,s26:…issue-3688`, which skips them on the S26 and the Pixel 8a and shows "excluded" on the
  page before any number (`render_dashboard.py` l.398, team page `build.py` l.583) → D1.
- "anchor 行は据え置き" and step 3: the Apple anchors carry no `file=`, so a catalog edit would have moved them too
  (`anchors.cells` l.9, l.12; admission keys rows by runtime, model id, task: `dashboard_job.py` l.760-773) → D3.
- The Android anchor row is the GPU short-chat page cell's key, and the page selects rows without the file
  (`render_dashboard.py` l.359, team page `build.py` l.645) → D2.
- `dashboard-text-v1-android-{b,b1,b2}.cells` have no Qwen3 0.6B LiteRT-LM row; `dashboard-longctx1024-v1-android-
  {b1,b2}.cells` hold only the anchor row; `dashboard-aa-v1-ios*.cells` only the iPhone anchor row.
- The 2K ladders (`dashboard-longctx-v1-android-s26*.cells`, `dashboard-longctx-v1.cells`) already ran the new file
  / id in their measured rows; their old-file rows are `exclude=` rows.
- "0.18.0 の engine 自身の行は Android と iOS で Processed 9 tokens": committed records carry the line on Android
  only (Pixel 8a `2026-10-15-…-0180-p1`, `-p2b`, `-p7-anchor`; all seven S26 anchors phases since 10-15, 3 of 3
  each); no committed iPhone log has it: iOS unverified.
- Catalog wording in step 3 ("…; GPU-graph build", onDiskSizeMB 329) differs from the existing entry of this file
  ("…; GPU-graph build 2026-08-04" = the Android label, onDiskSizeMB 344 = 344,671,744 B in decimal MB; 329 is MiB):
  moot under D3, recorded for a later catalog edit.
- "Mac は今日の週次の手動 sitting が全 cell を測る": the 05:30 firing took the Mac with MAIN's old cells (提案 2).
- The launch's file list did not include the two selftests that read the real cells
  (`scripts/regression_watch_selftest.py`, `android/ddp/selftest.py`); added with the supervisor's go.

## 罠と袋小路

- zsh does not split an unquoted `$F` into words: `validate_cells.py $F` got one long path (FileNotFoundError).
  Pass the list through `xargs` or a file.
- The quiet-window hook matches the command text, not what runs: a command that only wrote a script naming
  `render_leaderboard` / `build_summary` was refused inside r9's `r9-yardstick-b11721-build timing` hold. Write
  such scripts with the editor tool; run only light python with `QUIET_OK=1`.
- A cells edit that touches an anchor row or an `exclude-on=` breaks CI selftests that restate the cells by hand
  (`regression_watch_selftest.py` ANCHORS, `android/ddp/selftest.py` plan counts). Run the data-pipeline steps on
  a copy before the commit; compare against a `git checkout-index` copy of HEAD to tell new failures from old.
- `android/bench/selftest.py` takes about 6 minutes at background QoS (101 s in ROUND10 at normal priority): not
  "seconds" inside a measurement window.

## op と delegate の観察

なし: no device run in this round (no adb, no devicectl). The only rates in this file are the supervisor's probe,
read back from its records.

## 使った環境

- Mac host only, no venv: `~/.pyenv/shims/python3` = Python 3.14.6; `taskpolicy -b` for every check.
- No device, no hold, no queue. Ran beside the night job's Mac sitting (05:30 firing, pid 12802 → 13391; checks
  05:36-05:48 at background QoS) and, from 05:57:59, r9's quiet hold (pid 4930; 05:59:42-06:01:48 the remaining CI
  steps, light python with `QUIET_OK=1`, as the launch allows).
- Hashed one 344 MB blob of the Hub cache (`shasum -a 256`, about a second).

## 残した file

- Committed: the 12 changed `matrices/*.cells`, `matrices/dashboard-q06-dynamic-android.cells` and
  `matrices/dashboard-q06-dynamic-ios.cells` (the re-measurement), `docs/dashboard-cells-v1.md`,
  `docs/dashboard-recurring-job-v1.md`, `scripts/regression_watch_selftest.py`, `android/ddp/selftest.py`, this file.
- Scratch (session scratchpad, deletable): `q06_swap.py` (the row swap with per-file counts), `q06_remeasure.py` (the two
  files from their source rows), `ci_rest.sh` (the remaining CI steps), `checks/` (every check's output). The three
  repository copies (`headcopy.*`, `fixcopy.*`, `final.*`, about 1 GB) are deleted after the commit.
- MAIN: nothing written (no SIDE write under D3).
