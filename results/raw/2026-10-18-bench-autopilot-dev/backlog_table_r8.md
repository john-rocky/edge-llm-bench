# backlog 69 dir — session_check (r8: pin-drift, protocol-off) の dry-run (読むだけ; commit / 削除 / 移動なし)

main tree (`~/code/edge-llm-bench`) の `git status --porcelain results/raw` の untracked 行が挙げる 69 dir
(90 untracked lines at 02:44 and again at 03:05, main tree HEAD f6958509) に r8 の `scripts/session_check.py` (worktree `bench-autopilot`) を main tree の path で一度に
掛けた結果。列は `backlog_table.md` (r1) と同じ + 「r1 の verdict」(r1 の表に無い dir は —)。理由列は
allow-list で許された規則を除く規則 id。「人が読む」= 返事の sample を人が読む cell 数。

時間: `python3 scripts/session_check.py <69 dirs> --json --markdown -q`: real 6.36 user 4.78 sys 0.88 (03:05:36 JST, in a cooldown of the night job)

| dir | 種類 | verdict | r1 の verdict | 理由 (規則 id) | tracked / untracked | ledger の行 | 人が読む | 備考 |
|---|---|---|---|---|---|---|---|---|
| `2026-09-10-ddp-apk-sm-s942q-qwen3-gpu-android` | DDP | **HOLD** | HOLD | not-job | 0 / 1 | — | 0 | DDP: not a dashboard job campaign; a person reviews it (the job-session rules do not cover it) |
| `2026-09-15-ddp-http-caiman-35-wrapper` | DDP | **HOLD** | HOLD | not-job | 0 / 14 | — | 0 | DDP: not a dashboard job campaign; a person reviews it (the job-session rules do not cover it) |
| `2026-09-17-ddp-litert-lm-caiman-35` | DDP | **FAIL** | FAIL | logcat-unscrubbed, not-job | 64 / 4 | — | 0 | ddp-session/session-944b220b/litert-lm-pixel-9-pro/execution-a7408d24-b565-432c-8834-b755a206bc57/logcat.txt (untracked): the execution-level logcat.txt stays … |
| `2026-09-18-ddp-litertlm-prebuilt-caiman-35` | DDP | **FAIL** | FAIL | big-file, logcat-unscrubbed, not-job | 0 / 25 | — | 0 | ddp-session/session-a9ec9593/litertlm-prebuilt-pixel-9-pro/execution-49d5d542-52ab-4ee4-8342-84f0e0de9978/logcat.txt (untracked): the execution-level logcat.tx… |
| `2026-09-19-ddp-litertlm-newdir-caiman-35` | DDP | **FAIL** | FAIL | logcat-unscrubbed, not-job | 0 / 16 | — | 0 | ddp-session/session-aba54d60/litertlm-newdir-pixel-9-pro/execution-813c32be-69d9-44b6-aa57-ab05c156011c/logcat.txt (untracked): the execution-level logcat.txt … |
| `2026-09-20-qwen3-06b-reupload-aar0170-pixel8a-succ-gpu` | hand run | **HOLD** | HOLD | not-job | 0 / 1 | — | 0 | hand run: not a dashboard job campaign; a person reviews it (the job-session rules do not cover it) |
| `2026-09-25-dashboard-v1-s26-anchor-android` | job anchor | **PASS** | PASS | — | 0 / 14 | 2026-09-25 02:00:03 s26 OK (ok) exit 0 | 2 |  |
| `2026-09-25-dashboard-v1-s26-android` | job payload | **HOLD** | HOLD | reply-off-task | 0 / 98 | 2026-09-25 02:00:03 s26 OK (ok) exit 0 | 15 | litert-lm-gpu litert-community/Qwen3-1.7B short-chat (v0.16.0): 3 of 3 replies name none of the prompt's subject terms (sample: '</think> The word "explain" me… |
| `2026-09-26-dashboard-v1-s26-anchor-android` | job anchor | **PASS** | PASS | — | 0 / 14 | 2026-09-26 02:00:04 s26 OK (ok) exit 0 | 2 |  |
| `2026-09-26-dashboard-v1-s26-android` | job payload | **HOLD** | HOLD | reply-off-task | 0 / 92 | 2026-09-26 02:00:04 s26 OK (ok) exit 0 | 15 | litert-lm-gpu litert-community/Qwen3-1.7B short-chat (v0.16.0): 3 of 3 replies name none of the prompt's subject terms (sample: '</think> The word "explain" me… |
| `2026-09-27-dashboard-v1-s26-anchor-android` | job anchor | **PASS** | PASS | — | 0 / 14 | 2026-09-27 02:00:06 s26 OK (ok) exit 0 | 2 |  |
| `2026-09-27-dashboard-v1-s26-android` | job payload | **HOLD** | HOLD | reply-off-task | 0 / 92 | 2026-09-27 02:00:06 s26 OK (ok) exit 0 | 15 | litert-lm-gpu litert-community/Qwen3-1.7B short-chat (v0.16.0): 3 of 3 replies name none of the prompt's subject terms (sample: '</think> The word "explain" me… |
| `2026-09-28-dashboard-v1-s26-anchor-android` | job anchor | **PASS** | PASS | — | 0 / 14 | 2026-09-28 02:00:05 s26 OK (ok) exit 0 | 2 |  |
| `2026-09-28-dashboard-v1-s26-android` | job payload | **HOLD** | HOLD | reply-off-task | 0 / 92 | 2026-09-28 02:00:05 s26 OK (ok) exit 0 | 15 | litert-lm-gpu litert-community/Qwen3-1.7B short-chat (v0.16.0): 3 of 3 replies name none of the prompt's subject terms (sample: '</think> The word "explain" me… |
| `2026-09-29-dashboard-v1-s26-a-android` | job payload | **HOLD** | HOLD | reply-off-task | 0 / 56 | 2026-09-29 02:00:03 s26 OK (ok) exit 0 | 9 | litert-lm-gpu litert-community/Qwen3-1.7B short-chat (v0.16.0): 3 of 3 replies name none of the prompt's subject terms (sample: '</think> The word "explain" me… |
| `2026-09-29-dashboard-v1-s26-anchor-android` | job anchor | **PASS** | PASS | — | 0 / 14 | 2026-09-29 02:00:03 s26 OK (ok) exit 0 | 2 |  |
| `2026-09-29-dashboard-v1-s26-b1-android` | job payload | **PASS** | PASS | — | 0 / 26 | 2026-09-29 02:00:03 s26 OK (ok) exit 0 | 4 |  |
| `2026-09-29-dashboard-v1-s26-b2-android` | job payload | **PASS** | PASS | — | 0 / 26 | 2026-09-29 02:00:03 s26 OK (ok) exit 0 | 4 |  |
| `2026-09-30-dashboard-v1-m4max-anchor-mac` | job anchor | **PASS** | PASS | — | 0 / 5 | 2026-09-30 02:00:05 m4max OK (ok) exit 0 | 2 |  |
| `2026-09-30-dashboard-v1-m4max-mac` | job payload | **HOLD** | HOLD | user-name (allowed: failures) | 0 / 25 | 2026-09-30 02:00:05 m4max OK (ok) exit 0 | 18 | the account name in a path in 1 files (replace it by USER): session_provenance.txt (untracked) |
| `2026-10-02-dashboard-v1-pixel8a-anchor-android` | job anchor | **PASS** | PASS | — | 0 / 14 | 2026-10-02 02:00:05 pixel8a OK (ok) exit 0 | 2 |  |
| `2026-10-02-dashboard-v1-pixel8a-android` | job payload | **HOLD** | HOLD | flagged, reply-off-task | 0 / 124 | 2026-10-02 02:00:05 pixel8a OK (ok) exit 0 | 15 | GATE_FAIL llama.cpp unsloth/Qwen3-4B-GGUF short-chat first='COLLAPSE 28' retry='LEVEL 20' (retry kept; ⚠ downstream) |
| `2026-10-05-dashboard-v1-m4max-anchor-mac` | job anchor | **PASS** | PASS | — | 0 / 6 | 2026-10-05 02:00:05 m4max OK (ok) exit 0 | 2 |  |
| `2026-10-05-dashboard-v1-m4max-mac` | job payload | **HOLD** | HOLD | user-name (allowed: failures) | 0 / 29 | 2026-10-05 02:00:05 m4max OK (ok) exit 0 | 18 | the account name in a path in 1 files (replace it by USER): session_provenance.txt (untracked) |
| `2026-10-05-dashboard-v1-s26-a-android` | job payload | **HOLD** | HOLD | reply-off-task | 0 / 56 | 2026-10-05 05:30:03 s26 OK (ok) exit 0 | 9 | litert-lm-gpu litert-community/Qwen3-1.7B short-chat (v0.16.0): 3 of 3 replies name none of the prompt's subject terms (sample: '</think> The word "explain" me… |
| `2026-10-05-dashboard-v1-s26-anchor-android` | job anchor | **PASS** | PASS | — | 0 / 14 | 2026-10-05 05:30:03 s26 OK (ok) exit 0 | 2 |  |
| `2026-10-05-dashboard-v1-s26-b1-android` | job payload | **PASS** | PASS | — | 0 / 26 | 2026-10-05 05:30:03 s26 OK (ok) exit 0 | 4 |  |
| `2026-10-05-dashboard-v1-s26-b2-android` | job payload | **PASS** | PASS | — | 0 / 26 | 2026-10-05 05:30:03 s26 OK (ok) exit 0 | 4 |  |
| `2026-10-07-dashboard-v1-pixel8a-b1-android` | job payload | **FAIL** | FAIL | not-admitted, partial, runner-exit | 0 / 2 | 2026-10-07 03:14:18 pixel8a ABORTED (aborted) exit 4 | 0 | admitted false (COMPLETED): anchor-short |
| `2026-10-07-dashboard-v1-pixel8a-b1r-anchor-android` | job anchor | **PASS** | PASS | — | 0 / 14 | 2026-10-07 12:39:16 pixel8a OK (ok) exit 0 | 2 |  |
| `2026-10-07-dashboard-v1-pixel8a-b1r-android` | job payload | **HOLD** | HOLD | partial, runner-exit | 0 / 10 | 2026-10-07 12:39:16 pixel8a OK (ok) exit 0 | 2 | runner_exit 1 |
| `2026-10-07-dashboard-v1-pixel8a-b1r2-anchor-android` | job anchor | **HOLD** | HOLD | pair-incomplete | 0 / 14 | — | 2 | no payload dir names this anchor phase (the sitting stopped after admission?) |
| `2026-10-07-dashboard-v1-pixel8a-b1r2-android` | job payload | **FAIL** | FAIL | session-missing | 0 / 30 | — | 6 | no SESSION.json: the job never closed this sitting (killed, or still running) |
| `2026-10-07-dashboard-v1-pixel8a-b2-android` | job payload | **FAIL** | FAIL | not-admitted, partial, runner-exit | 0 / 2 | 2026-10-07 03:14:18 pixel8a ABORTED (aborted) exit 4 | 0 | admitted false (COMPLETED): anchor-short |
| `2026-10-08-dashboard-v1-iphone18pro-anchor-ios` | job anchor | **PASS** | PASS | — | 0 / 13 | 2026-10-08 05:30:05 iphone18pro OK (ok) exit 0 | 2 |  |
| `2026-10-08-dashboard-v1-iphone18pro-ios` | job payload | **HOLD** | HOLD | partial, reply-empty, reply-off-task | 0 / 179 | 2026-10-08 05:30:05 iphone18pro OK (ok) exit 0 | 28 | 28 of 31 cells with records (SESSION.json) |
| `2026-10-11-dashboard-v1-s26-a-android` | job payload | **HOLD** | HOLD | failures, reply-off-task, text-fail | 0 / 166 | 2026-10-11 02:00:05 s26 OK (ok) exit 0 | 18 | litert-lm litert-community/Qwen3-1.7B long-context-1024-gen256 rc=1 (cell records in the dir: 12) |
| `2026-10-11-dashboard-v1-s26-anchor-android` | job anchor | **PASS** | PASS | — | 0 / 14 | 2026-10-11 02:00:05 s26 OK (ok) exit 0 | 2 |  |
| `2026-10-11-dashboard-v1-s26-b1-android` | job payload | **PASS** | PASS | — | 0 / 63 | 2026-10-11 02:00:05 s26 OK (ok) exit 0 | 7 |  |
| `2026-10-11-dashboard-v1-s26-b2-android` | job payload | **PASS** | PASS | — | 0 / 63 | 2026-10-11 02:00:05 s26 OK (ok) exit 0 | 7 |  |
| `2026-10-11-dashboard-v1-s26-npu-android` | job payload | **PASS** | PASS | — | 0 / 99 | 2026-10-11 02:00:05 s26 OK (ok) exit 0 | 11 |  |
| `2026-10-11-dashboard-v1-s26-ort-android` | job payload | **PASS** | PASS | — | 0 / 27 | 2026-10-11 02:00:05 s26 OK (ok) exit 0 | 3 |  |
| `2026-10-11-s26-gallery-vs-binary` | hand run | **HOLD** | HOLD | not-job | 229 / 19 | — | 0 | hand run: not a dashboard job campaign; a person reviews it (the job-session rules do not cover it) |
| `2026-10-11-s26-perfetto` | hand run | **FAIL** | FAIL | big-file, not-job | 14 / 10 | — | 0 | traces/Q5.perfetto-trace (3.0 MB, untracked): model weights, a raw trace or an engine binary |
| `2026-10-12-dashboard-v1-m4max-anchor-mac` | job anchor | **PASS** | HOLD | — | 0 / 5 | 2026-10-12 05:30:10 m4max OK (ok) exit 0 | 2 |  |
| `2026-10-12-dashboard-v1-m4max-mac` | job payload | **HOLD** | HOLD | reply-empty, reply-off-task, user-name (allowed: failures) | 0 / 306 | 2026-10-12 05:30:10 m4max OK (ok) exit 0 | 57 | the account name in a path in 139 files (replace it by USER): onnxruntime-genai_onnx-community_Qwen3-0_6B-ONNX_short-chat_cpu_ctx2048_2be570e0c290.jsonl (untra… |
| `2026-10-13-dashboard-v1-pixel8a-a-android` | job payload | **FAIL** | HOLD | failures, pin-drift, reply-off-task, text-fail | 0 / 166 | 2026-10-13 02:00:05 pixel8a OK (ok) exit 0 | 18 | android litert-lm-cpu: stamps v0.16.0 x27; the newest LiteRT-LM release a platform's pin names on 2026-10-13: v0.18.0 (environment.lock.json arms.litert-lm.mac… |
| `2026-10-13-dashboard-v1-pixel8a-anchor-android` | job anchor | **FAIL** | PASS | pin-drift | 0 / 14 | 2026-10-13 02:00:05 pixel8a OK (ok) exit 0 | 2 | android litert-lm-gpu: stamps v0.16.0 x3; the newest LiteRT-LM release a platform's pin names on 2026-10-13: v0.18.0 (environment.lock.json arms.litert-lm.mac.… |
| `2026-10-13-dashboard-v1-pixel8a-b1-android` | job payload | **HOLD** | HOLD | partial | 0 / 9 | 2026-10-13 02:00:05 pixel8a OK (ok) exit 0 | 1 | 1 of 7 cells with records (SESSION.json) |
| `2026-10-13-dashboard-v1-pixel8a-b2-android` | job payload | **HOLD** | HOLD | partial | 0 / 9 | 2026-10-13 02:00:05 pixel8a OK (ok) exit 0 | 1 | 1 of 7 cells with records (SESSION.json) |
| `2026-10-14-dashboard-v1-s26-a-android` | job payload | **FAIL** | HOLD | failures, pin-drift, prompt-newtag, prompt-tokens, reply-off-task, text-fail | 0 / 166 | — | 18 | android litert-lm-cpu: stamps v0.16.0 x27; the newest LiteRT-LM release a platform's pin names on 2026-10-14: v0.18.0 (environment.lock.json arms.litert-lm.mac… |
| `2026-10-14-dashboard-v1-s26-anchor-android` | job anchor | **FAIL** | PASS | pin-drift | 0 / 14 | — | 2 | android litert-lm-gpu: stamps v0.16.0 x3; the newest LiteRT-LM release a platform's pin names on 2026-10-14: v0.18.0 (environment.lock.json arms.litert-lm.mac.… |
| `2026-10-14-dashboard-v1-s26-b1-android` | job payload | **FAIL** | HOLD | failures, pin-drift, prompt-tokens, reply-empty, reply-off-task, text-fail | 0 / 64 | — | 7 | android litert-lm-cpu: stamps v0.16.0 x9; the newest LiteRT-LM release a platform's pin names on 2026-10-14: v0.18.0 (environment.lock.json arms.litert-lm.mac.… |
| `2026-10-14-dashboard-v1-s26-b2-android` | job payload | **FAIL** | PASS | pin-drift | 0 / 63 | — | 7 | android litert-lm-cpu: stamps v0.16.0 x9; the newest LiteRT-LM release a platform's pin names on 2026-10-14: v0.18.0 (environment.lock.json arms.litert-lm.mac.… |
| `2026-10-14-dashboard-v1-s26-ort-android` | job payload | **FAIL** | FAIL | session-missing | 0 / 1 | — | 0 | no SESSION.json: the job never closed this sitting (killed, or still running) |
| `2026-10-15-dashboard-v1-iphone18pro-anchor-ios` | job anchor | **FAIL** | PASS | pin-drift | 0 / 13 | 2026-10-15 05:30:04 iphone18pro OK (ok) exit 0 | 2 | ios litert-lm: stamps v0.16.0 x3; the newest LiteRT-LM release a platform's pin names on 2026-10-15: v0.18.0 (environment.lock.json arms.litert-lm.mac.tag sinc… |
| `2026-10-15-dashboard-v1-iphone18pro-ios` | job payload | **FAIL** | FAIL | not-admitted, partial, pin-drift, reply-empty, reply-off-task | 0 / 225 | 2026-10-15 05:30:04 iphone18pro OK (ok) exit 0 | 34 | ios litert-lm: stamps v0.16.0 x40; the newest LiteRT-LM release a platform's pin names on 2026-10-15: v0.18.0 (environment.lock.json arms.litert-lm.mac.tag sin… |
| `2026-10-15-dashboard-v1-iphone18pro-r2-anchor-ios` | job anchor | **FAIL** | PASS | pin-drift | 0 / 13 | 2026-10-15 05:30:04 iphone18pro OK (ok) exit 0 | 2 | ios litert-lm: stamps v0.16.0 x3; the newest LiteRT-LM release a platform's pin names on 2026-10-15: v0.18.0 (environment.lock.json arms.litert-lm.mac.tag sinc… |
| `2026-10-15-dashboard-v1-iphone18pro-r2-ios` | job payload | **FAIL** | HOLD | partial, pin-drift, reply-empty, reply-off-task | 0 / 221 | 2026-10-15 05:30:04 iphone18pro OK (ok) exit 0 | 34 | ios litert-lm: stamps v0.16.0 x40; the newest LiteRT-LM release a platform's pin names on 2026-10-15: v0.18.0 (environment.lock.json arms.litert-lm.mac.tag sin… |
| `2026-10-16-dashboard-v1-m4max-anchor-mac` | job anchor | **FAIL** | FAIL | not-admitted | 0 / 5 | 2026-10-16 02:00:06 m4max TIMEOUT (timeout) exit 6 | 2 | admitted false (ABORTED): anchor-collapse |
| `2026-10-16-dashboard-v1-m4max-r2-anchor-mac` | job anchor | **PASS** | HOLD | — | 0 / 5 | 2026-10-16 02:00:06 m4max TIMEOUT (timeout) exit 6 | 2 |  |
| `2026-10-16-dashboard-v1-m4max-r2-mac` | job payload | **HOLD** | HOLD | partial, prompt-newtag, reply-empty, reply-off-task, user-name, verdict (allowed: failures) | 0 / 316 | 2026-10-16 02:00:06 m4max TIMEOUT (timeout) exit 6 | 44 | the account name in a path in 137 files (replace it by USER): executorch_own-export_Qwen3-1_7B-ET1_5_1-mlx-4w-emb8-ctx2048_long-context-1024-gen256_mlx_ctx2048… |
| `2026-10-17-dashboard-v1-iphone18pro-anchor-ios` | job anchor | **FAIL** | PASS | pin-drift | 0 / 13 | 2026-10-17 05:30:05 iphone18pro OK (ok) exit 0 | 2 | ios litert-lm: stamps v0.16.0 x3; the newest LiteRT-LM release a platform's pin names on 2026-10-17: v0.18.0 (environment.lock.json arms.litert-lm.mac.tag sinc… |
| `2026-10-17-dashboard-v1-iphone18pro-ios` | job payload | **FAIL** | FAIL | not-admitted, partial, pin-drift, reply-empty, reply-off-task | 0 / 229 | 2026-10-17 05:30:05 iphone18pro OK (ok) exit 0 | 34 | ios litert-lm: stamps v0.16.0 x40; the newest LiteRT-LM release a platform's pin names on 2026-10-17: v0.18.0 (environment.lock.json arms.litert-lm.mac.tag sin… |
| `2026-10-17-dashboard-v1-iphone18pro-r2-anchor-ios` | job anchor | **FAIL** | PASS | pin-drift | 0 / 13 | 2026-10-17 05:30:05 iphone18pro OK (ok) exit 0 | 2 | ios litert-lm: stamps v0.16.0 x3; the newest LiteRT-LM release a platform's pin names on 2026-10-17: v0.18.0 (environment.lock.json arms.litert-lm.mac.tag sinc… |
| `2026-10-17-dashboard-v1-iphone18pro-r2-ios` | job payload | **FAIL** | HOLD | partial, pin-drift, reply-empty, reply-off-task | 0 / 216 | 2026-10-17 05:30:05 iphone18pro OK (ok) exit 0 | 34 | ios litert-lm: stamps v0.16.0 x40; the newest LiteRT-LM release a platform's pin names on 2026-10-17: v0.18.0 (environment.lock.json arms.litert-lm.mac.tag sin… |
| `2026-10-17-iphone17pro-aa-i1-stopped-0155-ios` | job (stopped) | **FAIL** | FAIL | stopped-sitting | 0 / 20 | — | 0 | the quarantine of a stopped sitting (-stopped- in the name): kept on disk, never committed |
| `2026-10-19-dashboard-v1-m4max-anchor-mac` | job anchor | **HOLD** | — | pair-incomplete | 0 / 5 | — | 2 | 記録の時点で夜の job が計測中の sitting (02:00 の Mac)。no payload dir names this anchor phase (the sitting stopped after admission?) |
| `2026-10-19-dashboard-v1-m4max-mac` | job payload | **FAIL** | — | prompt-newtag, reply-off-task, session-missing, user-name | 0 / 141 | — | 25 | 記録の時点で夜の job が計測中の sitting (02:00 の Mac)。the account name in a path in 62 files (replace it by USER): executorch_own-export_Qwen3-1_7B-ET1_5_1-mlx-4w-emb8-ctx2… |

集計: PASS 22 / HOLD 22 / FAIL 25 (計 69 dir)。r1 の表 (77 dir): PASS 27 / HOLD 28 / FAIL 22。

- DDP: PASS 0 / HOLD 2 / FAIL 3
- hand run: PASS 0 / HOLD 2 / FAIL 1
- job (stopped): PASS 0 / HOLD 0 / FAIL 1
- job anchor: PASS 14 / HOLD 2 / FAIL 7
- job payload: PASS 8 / HOLD 16 / FAIL 13

規則ごとの dir 数 (allow-list 後): reply-off-task 19, pin-drift 14, partial 11, not-job 8, reply-empty 8, user-name 5, not-admitted 5, text-fail 4, failures 4, logcat-unscrubbed 3, runner-exit 3, session-missing 3, prompt-newtag 3, big-file 2, pair-incomplete 2, prompt-tokens 2, flagged 1, verdict 1, stopped-sitting 1

## r1 の verdict から変わった dir (全部)

- `2026-10-12-dashboard-v1-m4max-anchor-mac`: HOLD → PASS — 新規則の外 (新規則なしでも PASS: —)
- `2026-10-13-dashboard-v1-pixel8a-a-android`: HOLD → FAIL — 新規則 (pin-drift)
- `2026-10-13-dashboard-v1-pixel8a-anchor-android`: PASS → FAIL — 新規則 (pin-drift)
- `2026-10-14-dashboard-v1-s26-a-android`: HOLD → FAIL — 新規則 (pin-drift)
- `2026-10-14-dashboard-v1-s26-anchor-android`: PASS → FAIL — 新規則 (pin-drift)
- `2026-10-14-dashboard-v1-s26-b1-android`: HOLD → FAIL — 新規則 (pin-drift)
- `2026-10-14-dashboard-v1-s26-b2-android`: PASS → FAIL — 新規則 (pin-drift)
- `2026-10-15-dashboard-v1-iphone18pro-anchor-ios`: PASS → FAIL — 新規則 (pin-drift)
- `2026-10-15-dashboard-v1-iphone18pro-r2-anchor-ios`: PASS → FAIL — 新規則 (pin-drift)
- `2026-10-15-dashboard-v1-iphone18pro-r2-ios`: HOLD → FAIL — 新規則 (pin-drift)
- `2026-10-16-dashboard-v1-m4max-r2-anchor-mac`: HOLD → PASS — 新規則の外 (新規則なしでも PASS: —)
- `2026-10-17-dashboard-v1-iphone18pro-anchor-ios`: PASS → FAIL — 新規則 (pin-drift)
- `2026-10-17-dashboard-v1-iphone18pro-r2-anchor-ios`: PASS → FAIL — 新規則 (pin-drift)
- `2026-10-17-dashboard-v1-iphone18pro-r2-ios`: HOLD → FAIL — 新規則 (pin-drift)

r1 の表にあって今の backlog に無い dir: 10 (`2026-10-16-dashboard-v1-s26-0180-s10-ddp-m1q-36-android`, `2026-10-16-dashboard-v1-s26-0180-s11-ddp-m1q-36-android`, `2026-10-16-dashboard-v1-s26-0180-s12-ddp-m1q-36-android`, `2026-10-16-dashboard-v1-s26-0180-s13-ddp-m1q-36-android`, `2026-10-16-dashboard-v1-s26-0180-s14-ddp-m1q-36-android`, `2026-10-16-dashboard-v1-s26-0180-s15-ddp-m1q-36-android`, `2026-10-16-dashboard-v1-s26-0180-s16-ddp-m1q-36-android`, `2026-10-16-dashboard-v1-s26-0180-s3-ddp-m1q-36-android`, `2026-10-16-dashboard-v1-s26-0180-s4-ddp-m1q-36-android`, `2026-10-16-dashboard-v1-s26-0180-s9-ddp-m1q-36-android`)

r1 の表に無かった dir: 2 (`2026-10-19-dashboard-v1-m4max-anchor-mac` HOLD, `2026-10-19-dashboard-v1-m4max-mac` FAIL)

## launch の「FAIL になるべき」集合との突き合わせ

- 一致: `2026-10-13-dashboard-v1-pixel8a-a-android` FAIL pin-drift
- 一致: `2026-10-14-dashboard-v1-s26-a-android` FAIL pin-drift
- 一致: `2026-10-14-dashboard-v1-s26-b1-android` FAIL pin-drift
- 一致: `2026-10-14-dashboard-v1-s26-b2-android` FAIL pin-drift
- 一致: `2026-10-14-dashboard-v1-s26-anchor-android` FAIL pin-drift
- 一致: `2026-10-15-dashboard-v1-iphone18pro-ios` FAIL pin-drift
- 一致: `2026-10-15-dashboard-v1-iphone18pro-r2-ios` FAIL pin-drift
- 一致: `2026-10-17-dashboard-v1-iphone18pro-ios` FAIL pin-drift
- 一致: `2026-10-17-dashboard-v1-iphone18pro-r2-ios` FAIL pin-drift
- 一致: `2026-10-17-dashboard-v1-iphone18pro-anchor-ios` FAIL pin-drift
- 一致: `2026-10-17-dashboard-v1-iphone18pro-r2-anchor-ios` FAIL pin-drift
- 過: `2026-10-13-dashboard-v1-pixel8a-anchor-android` FAIL pin-drift — android litert-lm-gpu: stamps v0.16.0 x3; the newest LiteRT-LM release a platform's pin names on 2026-10-13: v0.18.0 (e…
- 過: `2026-10-15-dashboard-v1-iphone18pro-anchor-ios` FAIL pin-drift — ios litert-lm: stamps v0.16.0 x3; the newest LiteRT-LM release a platform's pin names on 2026-10-15: v0.18.0 (environme…
- 過: `2026-10-15-dashboard-v1-iphone18pro-r2-anchor-ios` FAIL pin-drift — ios litert-lm: stamps v0.16.0 x3; the newest LiteRT-LM release a platform's pin names on 2026-10-15: v0.18.0 (environme…

「FAIL になってはいけない物」に新規則の finding: なし (backlog で該当する dir 48)

