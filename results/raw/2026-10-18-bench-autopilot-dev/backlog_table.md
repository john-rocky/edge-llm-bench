# backlog 77 dir — session_check の dry-run (読むだけ; commit / 削除 / 移動なし)

main tree (`~/code/edge-llm-bench`) の `git status --porcelain results/raw` が挙げる 77 dir に
`scripts/session_check.py` を一度に掛けた結果 (2026-10-18, worktree `bench-autopilot` の checker, main tree の path)。
verdict の意味と規則 id は `docs/session-check-v1.md`。理由列は allow-list で許された規則を除く規則 id。
「人が読む」= 返事の sample を 1 cell 1 つ人が読む cell 数 (sample の本文は JSON 側)。

時間: `python3 scripts/session_check.py <77 dirs> --json --markdown -q: 10.65s user 0.91s system 93% cpu 12.345 total`

| dir | 種類 | verdict | 理由 (規則 id) | tracked / untracked | ledger の行 | 人が読む | 備考 |
|---|---|---|---|---|---|---|---|
| `2026-09-10-ddp-apk-sm-s942q-qwen3-gpu-android` | DDP | **HOLD** | not-job | 0 / 1 | — | 0 | DDP: not a dashboard job campaign; a person reviews it (the job-session rules do not cover it) |
| `2026-09-15-ddp-http-caiman-35-wrapper` | DDP | **HOLD** | not-job | 0 / 14 | — | 0 | DDP: not a dashboard job campaign; a person reviews it (the job-session rules do not cover it) |
| `2026-09-17-ddp-litert-lm-caiman-35` | DDP | **FAIL** | logcat-unscrubbed, not-job | 64 / 4 | — | 0 | commit 済みの dir。untracked の残り: ddp-session/session-944b220b/litert-lm-pixel-9-pro/execution-a7408d24-b565-432c-8834-b755a206bc57/logcat.txt, rehearsal-pixel8a-v2/output/cp |
| `2026-09-18-ddp-litertlm-prebuilt-caiman-35` | DDP | **FAIL** | big-file, logcat-unscrubbed, not-job | 0 / 25 | — | 0 | ddp-session/session-a9ec9593/litertlm-prebuilt-pixel-9-pro/execution-49d5d542-52ab-4ee4-8342-84f0e0de9978/logc… |
| `2026-09-19-ddp-litertlm-newdir-caiman-35` | DDP | **FAIL** | logcat-unscrubbed, not-job | 0 / 16 | — | 0 | ddp-session/session-aba54d60/litertlm-newdir-pixel-9-pro/execution-813c32be-69d9-44b6-aa57-ab05c156011c/logcat… |
| `2026-09-20-qwen3-06b-reupload-aar0170-pixel8a-succ-gpu` | hand run | **HOLD** | not-job | 0 / 1 | — | 0 | hand run: not a dashboard job campaign; a person reviews it (the job-session rules do not cover it) |
| `2026-09-25-dashboard-v1-s26-anchor-android` | job anchor | **PASS** | — | 0 / 14 | 2026-09-25 02:00:03 s26 OK (ok) exit 0 | 2 |  |
| `2026-09-25-dashboard-v1-s26-android` | job payload | **HOLD** | reply-off-task | 0 / 98 | 2026-09-25 02:00:03 s26 OK (ok) exit 0 | 15 | litert-lm-gpu litert-community/Qwen3-1.7B short-chat (v0.16.0): 3 of 3 replies name none of the prompt's subje… |
| `2026-09-26-dashboard-v1-s26-anchor-android` | job anchor | **PASS** | — | 0 / 14 | 2026-09-26 02:00:04 s26 OK (ok) exit 0 | 2 |  |
| `2026-09-26-dashboard-v1-s26-android` | job payload | **HOLD** | reply-off-task | 0 / 92 | 2026-09-26 02:00:04 s26 OK (ok) exit 0 | 15 | litert-lm-gpu litert-community/Qwen3-1.7B short-chat (v0.16.0): 3 of 3 replies name none of the prompt's subje… |
| `2026-09-27-dashboard-v1-s26-anchor-android` | job anchor | **PASS** | — | 0 / 14 | 2026-09-27 02:00:06 s26 OK (ok) exit 0 | 2 |  |
| `2026-09-27-dashboard-v1-s26-android` | job payload | **HOLD** | reply-off-task | 0 / 92 | 2026-09-27 02:00:06 s26 OK (ok) exit 0 | 15 | litert-lm-gpu litert-community/Qwen3-1.7B short-chat (v0.16.0): 3 of 3 replies name none of the prompt's subje… |
| `2026-09-28-dashboard-v1-s26-anchor-android` | job anchor | **PASS** | — | 0 / 14 | 2026-09-28 02:00:05 s26 OK (ok) exit 0 | 2 |  |
| `2026-09-28-dashboard-v1-s26-android` | job payload | **HOLD** | reply-off-task | 0 / 92 | 2026-09-28 02:00:05 s26 OK (ok) exit 0 | 15 | litert-lm-gpu litert-community/Qwen3-1.7B short-chat (v0.16.0): 3 of 3 replies name none of the prompt's subje… |
| `2026-09-29-dashboard-v1-s26-a-android` | job payload | **HOLD** | reply-off-task | 0 / 56 | 2026-09-29 02:00:03 s26 OK (ok) exit 0 | 9 | litert-lm-gpu litert-community/Qwen3-1.7B short-chat (v0.16.0): 3 of 3 replies name none of the prompt's subje… |
| `2026-09-29-dashboard-v1-s26-anchor-android` | job anchor | **PASS** | — | 0 / 14 | 2026-09-29 02:00:03 s26 OK (ok) exit 0 | 2 |  |
| `2026-09-29-dashboard-v1-s26-b1-android` | job payload | **PASS** | — | 0 / 26 | 2026-09-29 02:00:03 s26 OK (ok) exit 0 | 4 |  |
| `2026-09-29-dashboard-v1-s26-b2-android` | job payload | **PASS** | — | 0 / 26 | 2026-09-29 02:00:03 s26 OK (ok) exit 0 | 4 |  |
| `2026-09-30-dashboard-v1-m4max-anchor-mac` | job anchor | **PASS** | — | 0 / 5 | 2026-09-30 02:00:05 m4max OK (ok) exit 0 | 2 |  |
| `2026-09-30-dashboard-v1-m4max-mac` | job payload | **HOLD** | user-name (allow-list: failures) | 0 / 25 | 2026-09-30 02:00:05 m4max OK (ok) exit 0 | 18 | the account name in a path in 1 files (replace it by USER): session_provenance.txt (untracked) |
| `2026-10-02-dashboard-v1-pixel8a-anchor-android` | job anchor | **PASS** | — | 0 / 14 | 2026-10-02 02:00:05 pixel8a OK (ok) exit 0 | 2 |  |
| `2026-10-02-dashboard-v1-pixel8a-android` | job payload | **HOLD** | flagged, reply-off-task | 0 / 124 | 2026-10-02 02:00:05 pixel8a OK (ok) exit 0 | 15 | GATE_FAIL llama.cpp unsloth/Qwen3-4B-GGUF short-chat first='COLLAPSE 28' retry='LEVEL 20' (retry kept; ⚠ downs… |
| `2026-10-05-dashboard-v1-m4max-anchor-mac` | job anchor | **PASS** | — | 0 / 6 | 2026-10-05 02:00:05 m4max OK (ok) exit 0 | 2 |  |
| `2026-10-05-dashboard-v1-m4max-mac` | job payload | **HOLD** | user-name (allow-list: failures) | 0 / 29 | 2026-10-05 02:00:05 m4max OK (ok) exit 0 | 18 | the account name in a path in 1 files (replace it by USER): session_provenance.txt (untracked) |
| `2026-10-05-dashboard-v1-s26-a-android` | job payload | **HOLD** | reply-off-task | 0 / 56 | 2026-10-05 05:30:03 s26 OK (ok) exit 0 | 9 | litert-lm-gpu litert-community/Qwen3-1.7B short-chat (v0.16.0): 3 of 3 replies name none of the prompt's subje… |
| `2026-10-05-dashboard-v1-s26-anchor-android` | job anchor | **PASS** | — | 0 / 14 | 2026-10-05 05:30:03 s26 OK (ok) exit 0 | 2 |  |
| `2026-10-05-dashboard-v1-s26-b1-android` | job payload | **PASS** | — | 0 / 26 | 2026-10-05 05:30:03 s26 OK (ok) exit 0 | 4 |  |
| `2026-10-05-dashboard-v1-s26-b2-android` | job payload | **PASS** | — | 0 / 26 | 2026-10-05 05:30:03 s26 OK (ok) exit 0 | 4 |  |
| `2026-10-07-dashboard-v1-pixel8a-b1-android` | job payload | **FAIL** | not-admitted, partial, runner-exit | 0 / 2 | 2026-10-07 03:14:18 pixel8a ABORTED (aborted) exit 4 | 0 | admitted false (COMPLETED): anchor-short |
| `2026-10-07-dashboard-v1-pixel8a-b1r-anchor-android` | job anchor | **PASS** | — | 0 / 14 | 2026-10-07 12:39:16 pixel8a OK (ok) exit 0 | 2 |  |
| `2026-10-07-dashboard-v1-pixel8a-b1r-android` | job payload | **HOLD** | partial, runner-exit | 0 / 10 | 2026-10-07 12:39:16 pixel8a OK (ok) exit 0 | 2 | runner_exit 1 |
| `2026-10-07-dashboard-v1-pixel8a-b1r2-anchor-android` | job anchor | **HOLD** | pair-incomplete | 0 / 14 | — | 2 | no payload dir names this anchor phase (the sitting stopped after admission?) |
| `2026-10-07-dashboard-v1-pixel8a-b1r2-android` | job payload | **FAIL** | session-missing | 0 / 30 | — | 6 | no SESSION.json: the job never closed this sitting (killed, or still running) |
| `2026-10-07-dashboard-v1-pixel8a-b2-android` | job payload | **FAIL** | not-admitted, partial, runner-exit | 0 / 2 | 2026-10-07 03:14:18 pixel8a ABORTED (aborted) exit 4 | 0 | admitted false (COMPLETED): anchor-short |
| `2026-10-08-dashboard-v1-iphone18pro-anchor-ios` | job anchor | **PASS** | — | 0 / 13 | 2026-10-08 05:30:05 iphone18pro OK (ok) exit 0 | 2 |  |
| `2026-10-08-dashboard-v1-iphone18pro-ios` | job payload | **HOLD** | partial, reply-empty, reply-off-task | 0 / 179 | 2026-10-08 05:30:05 iphone18pro OK (ok) exit 0 | 28 | 28 of 31 cells with records (SESSION.json) |
| `2026-10-11-dashboard-v1-s26-a-android` | job payload | **HOLD** | failures, reply-off-task, text-fail | 0 / 166 | 2026-10-11 02:00:05 s26 OK (ok) exit 0 | 18 | litert-lm litert-community/Qwen3-1.7B long-context-1024-gen256 rc=1 (cell records in the dir: 12) |
| `2026-10-11-dashboard-v1-s26-anchor-android` | job anchor | **PASS** | — | 0 / 14 | 2026-10-11 02:00:05 s26 OK (ok) exit 0 | 2 |  |
| `2026-10-11-dashboard-v1-s26-b1-android` | job payload | **PASS** | — | 0 / 63 | 2026-10-11 02:00:05 s26 OK (ok) exit 0 | 7 |  |
| `2026-10-11-dashboard-v1-s26-b2-android` | job payload | **PASS** | — | 0 / 63 | 2026-10-11 02:00:05 s26 OK (ok) exit 0 | 7 |  |
| `2026-10-11-dashboard-v1-s26-npu-android` | job payload | **PASS** | — | 0 / 99 | 2026-10-11 02:00:05 s26 OK (ok) exit 0 | 11 |  |
| `2026-10-11-dashboard-v1-s26-ort-android` | job payload | **PASS** | — | 0 / 27 | 2026-10-11 02:00:05 s26 OK (ok) exit 0 | 3 |  |
| `2026-10-11-s26-gallery-vs-binary` | hand run | **HOLD** | not-job | 229 / 19 | — | 0 | commit 済みの dir。untracked の残り: gallery/E2B-gpu-1.attempt1.driver.log, gallery/E2B-gpu-1.attempt2.driver.log, gallery/E2B-gpu-1.driver.attempt3.log and 16 more |
| `2026-10-11-s26-perfetto` | hand run | **FAIL** | big-file, not-job | 14 / 10 | — | 0 | commit 済みの dir。untracked の残り: traces/E2B-gpu-1.perfetto-trace, traces/P1.perfetto-trace, traces/P2.perfetto-trace and 7 more |
| `2026-10-12-dashboard-v1-m4max-anchor-mac` | job anchor | **HOLD** | engine-stamp | 0 / 5 | 2026-10-12 05:30:10 m4max OK (ok) exit 0 | 2 | mac litert-lm: stamps v0.18.0 x3; registry v0.16.0 (environment.lock.json arms.litert-lm.default_tag at c3f33f… |
| `2026-10-12-dashboard-v1-m4max-mac` | job payload | **HOLD** | engine-stamp, reply-empty, reply-off-task, user-name (allow-list: failures) | 0 / 306 | 2026-10-12 05:30:10 m4max OK (ok) exit 0 | 57 | the account name in a path in 139 files (replace it by USER): onnxruntime-genai_onnx-community_Qwen3-0_6B-ONNX… |
| `2026-10-13-dashboard-v1-pixel8a-a-android` | job payload | **HOLD** | failures, reply-off-task, text-fail | 0 / 166 | 2026-10-13 02:00:05 pixel8a OK (ok) exit 0 | 18 | litert-lm litert-community/Qwen3-1.7B long-context-1024-gen256 rc=1 (cell records in the dir: 12) |
| `2026-10-13-dashboard-v1-pixel8a-anchor-android` | job anchor | **PASS** | — | 0 / 14 | 2026-10-13 02:00:05 pixel8a OK (ok) exit 0 | 2 |  |
| `2026-10-13-dashboard-v1-pixel8a-b1-android` | job payload | **HOLD** | partial | 0 / 9 | 2026-10-13 02:00:05 pixel8a OK (ok) exit 0 | 1 | 1 of 7 cells with records (SESSION.json) |
| `2026-10-13-dashboard-v1-pixel8a-b2-android` | job payload | **HOLD** | partial | 0 / 9 | 2026-10-13 02:00:05 pixel8a OK (ok) exit 0 | 1 | 1 of 7 cells with records (SESSION.json) |
| `2026-10-14-dashboard-v1-s26-a-android` | job payload | **HOLD** | failures, prompt-newtag, prompt-tokens, reply-off-task, text-fail | 0 / 166 | — | 18 | litert-lm litert-community/Qwen3-1.7B long-context-1024-gen256 rc=1 (cell records in the dir: 12) |
| `2026-10-14-dashboard-v1-s26-anchor-android` | job anchor | **PASS** | — | 0 / 14 | — | 2 |  |
| `2026-10-14-dashboard-v1-s26-b1-android` | job payload | **HOLD** | failures, prompt-tokens, reply-empty, reply-off-task, text-fail | 0 / 64 | — | 7 | litert-lm litert-community/Qwen3-4B long-context-1024-gen256 rc=1 (cell records in the dir: 12) |
| `2026-10-14-dashboard-v1-s26-b2-android` | job payload | **PASS** | — | 0 / 63 | — | 7 |  |
| `2026-10-14-dashboard-v1-s26-ort-android` | job payload | **FAIL** | session-missing | 0 / 1 | — | 0 | no SESSION.json: the job never closed this sitting (killed, or still running) |
| `2026-10-15-dashboard-v1-iphone18pro-anchor-ios` | job anchor | **PASS** | — | 0 / 13 | 2026-10-15 05:30:04 iphone18pro OK (ok) exit 0 | 2 |  |
| `2026-10-15-dashboard-v1-iphone18pro-ios` | job payload | **FAIL** | not-admitted, partial, reply-empty, reply-off-task | 0 / 225 | 2026-10-15 05:30:04 iphone18pro OK (ok) exit 0 | 34 | admitted false (COMPLETED): anchor-short |
| `2026-10-15-dashboard-v1-iphone18pro-r2-anchor-ios` | job anchor | **PASS** | — | 0 / 13 | 2026-10-15 05:30:04 iphone18pro OK (ok) exit 0 | 2 |  |
| `2026-10-15-dashboard-v1-iphone18pro-r2-ios` | job payload | **HOLD** | partial, reply-empty, reply-off-task | 0 / 221 | 2026-10-15 05:30:04 iphone18pro OK (ok) exit 0 | 34 | 34 of 37 cells with records (SESSION.json) |
| `2026-10-16-dashboard-v1-m4max-anchor-mac` | job anchor | **FAIL** | engine-stamp, not-admitted | 0 / 5 | 2026-10-16 02:00:06 m4max TIMEOUT (timeout) exit 6 | 2 | admitted false (ABORTED): anchor-collapse |
| `2026-10-16-dashboard-v1-m4max-r2-anchor-mac` | job anchor | **HOLD** | engine-stamp | 0 / 5 | 2026-10-16 02:00:06 m4max TIMEOUT (timeout) exit 6 | 2 | mac litert-lm: stamps v0.18.0 x3; registry v0.16.0 (environment.lock.json arms.litert-lm.default_tag at d33ffa… |
| `2026-10-16-dashboard-v1-m4max-r2-mac` | job payload | **HOLD** | engine-stamp, partial, prompt-newtag, reply-empty, reply-off-task, user-name, verdict (allow-list: failures) | 0 / 316 | 2026-10-16 02:00:06 m4max TIMEOUT (timeout) exit 6 | 44 | the account name in a path in 137 files (replace it by USER): executorch_own-export_Qwen3-1_7B-ET1_5_1-mlx-4w-… |
| `2026-10-16-dashboard-v1-s26-0180-s10-ddp-m1q-36-android` | DDP | **FAIL** | big-file-size, logcat-unscrubbed, not-job | 33 / 1 | — | 0 | commit 済み (d6077c6b)。残りは execution-level logcat.txt だけ (untracked) |
| `2026-10-16-dashboard-v1-s26-0180-s11-ddp-m1q-36-android` | DDP | **FAIL** | big-file-size, logcat-unscrubbed, not-job | 42 / 1 | — | 0 | commit 済み (d6077c6b)。残りは execution-level logcat.txt だけ (untracked) |
| `2026-10-16-dashboard-v1-s26-0180-s12-ddp-m1q-36-android` | DDP | **FAIL** | big-file-size, logcat-unscrubbed, not-job | 42 / 1 | — | 0 | commit 済み (d6077c6b)。残りは execution-level logcat.txt だけ (untracked) |
| `2026-10-16-dashboard-v1-s26-0180-s13-ddp-m1q-36-android` | DDP | **FAIL** | logcat-unscrubbed, not-job | 33 / 1 | — | 0 | commit 済み (d6077c6b)。残りは execution-level logcat.txt だけ (untracked) |
| `2026-10-16-dashboard-v1-s26-0180-s14-ddp-m1q-36-android` | DDP | **FAIL** | big-file-size, logcat-unscrubbed, not-job | 33 / 1 | — | 0 | commit 済み (d6077c6b)。残りは execution-level logcat.txt だけ (untracked) |
| `2026-10-16-dashboard-v1-s26-0180-s15-ddp-m1q-36-android` | DDP | **FAIL** | logcat-unscrubbed, not-job | 42 / 1 | — | 0 | commit 済み (d6077c6b)。残りは execution-level logcat.txt だけ (untracked) |
| `2026-10-16-dashboard-v1-s26-0180-s16-ddp-m1q-36-android` | DDP | **FAIL** | big-file-size, logcat-unscrubbed, not-job | 42 / 1 | — | 0 | commit 済み (d6077c6b)。残りは execution-level logcat.txt だけ (untracked) |
| `2026-10-16-dashboard-v1-s26-0180-s3-ddp-m1q-36-android` | DDP | **FAIL** | logcat-unscrubbed, not-job | 59 / 2 | — | 0 | commit 済み (d6077c6b)。残りは execution-level logcat.txt だけ (untracked) |
| `2026-10-16-dashboard-v1-s26-0180-s4-ddp-m1q-36-android` | DDP | **FAIL** | logcat-unscrubbed, not-job | 77 / 2 | — | 0 | commit 済み (d6077c6b)。残りは execution-level logcat.txt だけ (untracked) |
| `2026-10-16-dashboard-v1-s26-0180-s9-ddp-m1q-36-android` | DDP | **FAIL** | big-file-size, logcat-unscrubbed, not-job | 33 / 1 | — | 0 | commit 済み (d6077c6b)。残りは execution-level logcat.txt だけ (untracked) |
| `2026-10-17-dashboard-v1-iphone18pro-anchor-ios` | job anchor | **PASS** | — | 0 / 13 | 2026-10-17 05:30:05 iphone18pro OK (ok) exit 0 | 2 |  |
| `2026-10-17-dashboard-v1-iphone18pro-ios` | job payload | **FAIL** | not-admitted, partial, reply-empty, reply-off-task | 0 / 229 | 2026-10-17 05:30:05 iphone18pro OK (ok) exit 0 | 34 | admitted false (COMPLETED): anchor-short |
| `2026-10-17-dashboard-v1-iphone18pro-r2-anchor-ios` | job anchor | **PASS** | — | 0 / 13 | 2026-10-17 05:30:05 iphone18pro OK (ok) exit 0 | 2 |  |
| `2026-10-17-dashboard-v1-iphone18pro-r2-ios` | job payload | **HOLD** | partial, reply-empty, reply-off-task | 0 / 216 | 2026-10-17 05:30:05 iphone18pro OK (ok) exit 0 | 34 | 34 of 37 cells with records (SESSION.json) |
| `2026-10-17-iphone17pro-aa-i1-stopped-0155-ios` | job payload (stopped) | **FAIL** | stopped-sitting | 0 / 20 | — | 0 | the quarantine of a stopped sitting (-stopped- in the name): kept on disk, never committed |

集計: PASS 27 / HOLD 28 / FAIL 22 (計 77 dir)

- DDP: PASS 0 / HOLD 2 / FAIL 13
- hand run: PASS 0 / HOLD 2 / FAIL 1
- job anchor: PASS 18 / HOLD 3 / FAIL 1
- job payload: PASS 9 / HOLD 21 / FAIL 6
- job payload (stopped): PASS 0 / HOLD 0 / FAIL 1

規則ごとの dir 数 (allow-list 後): not-job 18, reply-off-task 18, logcat-unscrubbed 13, partial 11, reply-empty 8, big-file-size 6, not-admitted 5, engine-stamp 5, user-name 4, failures 4, text-fail 4, runner-exit 3, big-file 2, session-missing 2, prompt-tokens 2, prompt-newtag 2, flagged 1, pair-incomplete 1, verdict 1, stopped-sitting 1

