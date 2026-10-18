# commit 済み sitting 全部 — session_check (r8: pin-drift, protocol-off) の dry-run

`git ls-files 'results/raw/*/SESSION.json'` の dir (worktree `bench-autopilot`, HEAD 9ab1556e) に
r8 の `scripts/session_check.py` を一度に掛けた結果 (読むだけ)。「r8 前」= 同じ dir に HEAD の checker
(この round の変更前) を掛けた verdict。「r1 (a)」= ROUND1 の (a) (commit 済みの -dashboard-v1- job
sitting 88 dir; HOLD 11 は ROUND1.md 訂正に名指し、他は PASS)。理由列は allow-list 後の規則 id。

時間: `python3 scripts/session_check.py <116 dirs> --json --markdown -q`: real 10.54 user 8.92 sys 1.03 (03:05:25 JST, in a cooldown of the night job)

| dir | 種類 | verdict | r8 前 | r1 (a) | 規則 id | 新規則の finding |
|---|---|---|---|---|---|---|
| `2026-09-08-dashboard-v1-m4max-anchor-mac` | job anchor | **PASS** | PASS | PASS | — | なし |
| `2026-09-08-dashboard-v1-m4max-mac` | job payload | **HOLD** | HOLD | HOLD | gen-budget (allowed: failures) | なし |
| `2026-09-08-dashboard-v1-pixel8a-a-android` | job payload | **HOLD** | HOLD | HOLD | reply-off-task | なし |
| `2026-09-08-dashboard-v1-pixel8a-anchor-android` | job anchor | **PASS** | PASS | PASS | — (allowed: failures) | なし |
| `2026-09-08-dashboard-v1-pixel8a-b1-android` | job payload | **PASS** | PASS | PASS | — | なし |
| `2026-09-08-dashboard-v1-pixel8a-b2-android` | job payload | **PASS** | PASS | PASS | — | なし |
| `2026-09-08-dashboard-v1-s26-anchor-android` | job anchor | **PASS** | PASS | PASS | — | なし |
| `2026-09-08-dashboard-v1-s26-android` | job payload | **HOLD** | HOLD | HOLD | reply-off-task | なし |
| `2026-09-09-dashboard-v1-iphone17pro-anchor-ios` | job anchor | **PASS** | PASS | PASS | — | なし |
| `2026-09-09-dashboard-v1-iphone17pro-ios` | job payload | **PASS** | PASS | PASS | — (allowed: partial) | なし |
| `2026-09-09-dashboard-v1-iphone17pro-retake-anchor-ios` | job anchor | **PASS** | PASS | PASS | — | なし |
| `2026-09-09-dashboard-v1-iphone17pro-retake-ios` | job payload | **HOLD** | HOLD | HOLD | gen-budget (allowed: partial, runner-exit) | なし |
| `2026-09-09-dashboard-v1-iphone17pro-retake2-anchor-ios` | job anchor | **PASS** | PASS | PASS | — | なし |
| `2026-09-09-dashboard-v1-iphone17pro-retake2-ios` | job payload | **PASS** | PASS | PASS | — (allowed: partial, runner-exit) | なし |
| `2026-09-09-dashboard-v1-pixel8a-anchor-android` | job anchor | **PASS** | PASS | PASS | — | なし |
| `2026-09-09-dashboard-v1-pixel8a-android` | job payload | **PASS** | PASS | PASS | — | なし |
| `2026-09-09-dashboard-v1-pixel8a-reboot-anchor-android` | job anchor | **PASS** | PASS | PASS | — | なし |
| `2026-09-09-dashboard-v1-pixel8a-reboot-android` | job payload | **PASS** | PASS | PASS | — | なし |
| `2026-09-11-catalog-x13-pixel8a-anchor-android` | job anchor | **PASS** | PASS | — | — | なし |
| `2026-09-11-catalog-x13-pixel8a-android` | job payload | **HOLD** | HOLD | — | reply-off-task | なし |
| `2026-09-11-catalog-x13-s26-anchor-android` | job anchor | **PASS** | PASS | — | — | なし |
| `2026-09-11-catalog-x13-s26-android` | job payload | **HOLD** | HOLD | — | reply-off-task | なし |
| `2026-09-13-catalog-int4-vs-int8-pixel8a-anchor-android` | job anchor | **PASS** | PASS | — | — | なし |
| `2026-09-13-catalog-int4-vs-int8-pixel8a-android` | job payload | **HOLD** | HOLD | — | reply-loop, reply-off-task | なし |
| `2026-09-13-catalog-int4-vs-int8-s26-anchor-android` | job anchor | **PASS** | PASS | — | — | なし |
| `2026-09-13-catalog-int4-vs-int8-s26-android` | job payload | **HOLD** | HOLD | — | reply-off-task | なし |
| `2026-09-14-catalog-int4-vs-int8-pixel8a-dtypeonly-anchor-android` | job anchor | **PASS** | PASS | — | — | なし |
| `2026-09-14-catalog-int4-vs-int8-pixel8a-dtypeonly-android` | job payload | **HOLD** | HOLD | — | reply-empty, reply-off-task | なし |
| `2026-09-14-catalog-int4-vs-int8-pixel8a-dtypeonly-norope-anchor-android` | job anchor | **PASS** | PASS | — | — | なし |
| `2026-09-14-catalog-int4-vs-int8-pixel8a-dtypeonly-norope-android` | job payload | **PASS** | PASS | — | — | なし |
| `2026-09-14-catalog-int4-vs-int8-s26-dtypeonly-anchor-android` | job anchor | **PASS** | PASS | — | — | なし |
| `2026-09-14-catalog-int4-vs-int8-s26-dtypeonly-android` | job payload | **PASS** | PASS | — | — | なし |
| `2026-09-14-dashboard-v1-m4max-anchor-mac` | job anchor | **PASS** | PASS | PASS | — | なし |
| `2026-09-14-dashboard-v1-m4max-mac` | job payload | **PASS** | PASS | PASS | — (allowed: failures) | なし |
| `2026-09-14-dashboard-v1-s26-anchor-android` | job anchor | **PASS** | PASS | PASS | — | なし |
| `2026-09-14-dashboard-v1-s26-android` | job payload | **HOLD** | HOLD | HOLD | reply-off-task (allowed: runner-exit) | なし |
| `2026-09-21-dashboard-v1-m4max-anchor-mac` | job anchor | **PASS** | PASS | PASS | — | なし |
| `2026-09-21-dashboard-v1-m4max-mac` | job payload | **PASS** | PASS | PASS | — (allowed: failures, partial) | なし |
| `2026-09-22-dashboard-v1-m4max-anchor-mac` | job anchor | **PASS** | PASS | PASS | — | なし |
| `2026-09-22-dashboard-v1-m4max-mac` | job payload | **PASS** | PASS | PASS | — (allowed: failures, partial) | なし |
| `2026-09-26-vl-response-v1-s26-anchor-android` | hand run | **HOLD** | HOLD | — | not-job | なし |
| `2026-09-26-vl-response-v1-s26-android` | hand run | **HOLD** | HOLD | — | not-job | なし |
| `2026-09-27-tts-rtf-v1-s26-anchor-android` | hand run | **FAIL** | FAIL | — | not-admitted, not-job | なし |
| `2026-09-27-tts-rtf-v1-s26-anchor-retake-android` | hand run | **HOLD** | HOLD | — | not-job | なし |
| `2026-09-27-tts-rtf-v1-s26-android` | hand run | **HOLD** | HOLD | — | not-job | なし |
| `2026-09-29-tts-rtf-fast-s26-anchor-android` | hand run | **HOLD** | HOLD | — | not-job | なし |
| `2026-09-29-tts-rtf-fast-s26-anchor-retake-android` | hand run | **HOLD** | HOLD | — | not-job | なし |
| `2026-09-29-tts-rtf-fast-s26-android` | hand run | **HOLD** | HOLD | — | not-job | なし |
| `2026-10-06-dashboard-v1-m4max-longctx1024-anchor-mac` | job anchor | **HOLD** | HOLD | HOLD | reference-uncommitted | なし |
| `2026-10-06-dashboard-v1-m4max-longctx1024-mac` | job payload | **HOLD** | HOLD | HOLD | reply-empty, reply-off-task (allowed: failures) | なし |
| `2026-10-06-dashboard-v1-m4max-protocol1024-anchor-mac` | job anchor | **PASS** | PASS | PASS | — | なし |
| `2026-10-06-dashboard-v1-m4max-protocol1024-mac` | job payload | **PASS** | PASS | PASS | — (allowed: partial) | なし |
| `2026-10-07-dashboard-v1-pixel8a-a-android` | job payload | **HOLD** | HOLD | HOLD | failures, reply-off-task, text-fail (allowed: failures, partial, runner-exit) | なし |
| `2026-10-07-dashboard-v1-pixel8a-anchor-android` | job anchor | **HOLD** | HOLD | HOLD | reference-uncommitted | なし |
| `2026-10-08-dashboard-coreai-v1-iphone18pro-ios` | hand run | **HOLD** | HOLD | — | not-job | なし |
| `2026-10-08-dashboard-coreai-v1-m4max-mac` | hand run | **HOLD** | HOLD | — | not-job, record-unreadable | なし |
| `2026-10-09-dashboard-coreai-v1-iphone17pro-ios` | hand run | **HOLD** | HOLD | — | not-job | なし |
| `2026-10-09-dashboard-coreai-v1-iphone18pro-retry-ios` | hand run | **HOLD** | HOLD | — | not-job | なし |
| `2026-10-09-dashboard-coreai-v1-m4max-anchor-retake-mac` | hand run | **HOLD** | HOLD | — | not-job | なし |
| `2026-10-15-dashboard-v1-pixel8a-0180-p1-anchor-android` | job anchor | **HOLD** | HOLD | HOLD | reference-uncommitted (allowed: reply-off-task) | なし |
| `2026-10-15-dashboard-v1-pixel8a-0180-p1-android` | job payload | **PASS** | PASS | PASS | — (allowed: prompt-newtag, reply-off-task) | なし |
| `2026-10-15-dashboard-v1-pixel8a-0180-p2b-anchor-android` | job anchor | **PASS** | PASS | PASS | — (allowed: reply-off-task) | なし |
| `2026-10-15-dashboard-v1-pixel8a-0180-p2b-android` | job payload | **PASS** | PASS | PASS | — (allowed: failures, text-fail) | なし |
| `2026-10-15-dashboard-v1-pixel8a-0180-p3a-anchor-android` | job anchor | **PASS** | PASS | PASS | — (allowed: reply-off-task) | なし |
| `2026-10-15-dashboard-v1-pixel8a-0180-p3a-android` | job payload | **PASS** | PASS | PASS | — (allowed: prompt-tokens, reply-off-task) | なし |
| `2026-10-15-dashboard-v1-pixel8a-0180-p3a-r2-anchor-android` | job anchor | **PASS** | PASS | PASS | — (allowed: reply-off-task) | なし |
| `2026-10-15-dashboard-v1-pixel8a-0180-p3a-r2-android` | job payload | **PASS** | PASS | PASS | — | なし |
| `2026-10-15-dashboard-v1-pixel8a-0180-p3a-rt-anchor-android` | job anchor | **PASS** | PASS | PASS | — (allowed: reply-off-task) | なし |
| `2026-10-15-dashboard-v1-pixel8a-0180-p3a-rt-android` | job payload | **PASS** | PASS | PASS | — | なし |
| `2026-10-15-dashboard-v1-pixel8a-0180-p3b-anchor-android` | job anchor | **PASS** | PASS | PASS | — (allowed: reply-off-task) | なし |
| `2026-10-15-dashboard-v1-pixel8a-0180-p3b-android` | job payload | **PASS** | PASS | PASS | — (allowed: failures, reply-off-task) | なし |
| `2026-10-15-dashboard-v1-pixel8a-0180-p3b-r2-anchor-android` | job anchor | **PASS** | PASS | PASS | — (allowed: reply-off-task) | なし |
| `2026-10-15-dashboard-v1-pixel8a-0180-p3b-r2-android` | job payload | **PASS** | PASS | PASS | — | なし |
| `2026-10-15-dashboard-v1-pixel8a-0180-p4-anchor-android` | job anchor | **PASS** | PASS | PASS | — (allowed: reply-off-task) | なし |
| `2026-10-15-dashboard-v1-pixel8a-0180-p4-android` | job payload | **PASS** | PASS | PASS | — | なし |
| `2026-10-15-dashboard-v1-pixel8a-0180-p4-rt-anchor-android` | job anchor | **PASS** | PASS | PASS | — (allowed: reply-off-task) | なし |
| `2026-10-15-dashboard-v1-pixel8a-0180-p4-rt-android` | job payload | **PASS** | PASS | PASS | — | なし |
| `2026-10-15-dashboard-v1-pixel8a-0180-p5-anchor-android` | job anchor | **PASS** | PASS | PASS | — (allowed: reply-off-task) | なし |
| `2026-10-15-dashboard-v1-pixel8a-0180-p5-android` | job payload | **PASS** | PASS | PASS | — | なし |
| `2026-10-15-dashboard-v1-pixel8a-0180-p6a-anchor-android` | job anchor | **PASS** | PASS | PASS | — (allowed: reply-off-task) | なし |
| `2026-10-15-dashboard-v1-pixel8a-0180-p6a-android` | job payload | **PASS** | PASS | PASS | — | なし |
| `2026-10-15-dashboard-v1-pixel8a-0180-p6b-anchor-android` | job anchor | **PASS** | PASS | PASS | — (allowed: reply-off-task) | なし |
| `2026-10-15-dashboard-v1-pixel8a-0180-p6b-android` | job payload | **PASS** | PASS | PASS | — | なし |
| `2026-10-15-dashboard-v1-pixel8a-0180-p7-anchor-android` | job anchor | **PASS** | PASS | PASS | — (allowed: reply-off-task) | なし |
| `2026-10-15-dashboard-v1-pixel8a-0180-p7-android` | job payload | **PASS** | PASS | PASS | — | なし |
| `2026-10-15-dashboard-v1-pixel8a-0180-p8-anchor-android` | job anchor | **PASS** | PASS | PASS | — (allowed: reply-off-task) | なし |
| `2026-10-15-dashboard-v1-pixel8a-0180-p8-android` | job payload | **PASS** | PASS | PASS | — | なし |
| `2026-10-15-dashboard-v1-pixel8a-0180-p9a-anchor-android` | job anchor | **PASS** | PASS | PASS | — (allowed: reply-off-task) | なし |
| `2026-10-15-dashboard-v1-pixel8a-0180-p9a-android` | job payload | **PASS** | PASS | PASS | — | なし |
| `2026-10-15-dashboard-v1-pixel8a-0180-p9b-anchor-android` | job anchor | **PASS** | PASS | PASS | — (allowed: reply-off-task) | なし |
| `2026-10-15-dashboard-v1-pixel8a-0180-p9b-android` | job payload | **PASS** | PASS | PASS | — | なし |
| `2026-10-15-dashboard-v1-pixel8a-ortgenai-A-anchor-android` | job anchor | **PASS** | PASS | PASS | — (allowed: reply-off-task) | なし |
| `2026-10-15-dashboard-v1-pixel8a-ortgenai-A-android` | job payload | **PASS** | PASS | PASS | — | なし |
| `2026-10-15-dashboard-v1-pixel8a-ortgenai-B-anchor-android` | job anchor | **PASS** | PASS | PASS | — (allowed: reply-off-task) | なし |
| `2026-10-15-dashboard-v1-pixel8a-ortgenai-B-android` | job payload | **PASS** | PASS | PASS | — | なし |
| `2026-10-15-dashboard-v1-pixel8a-ortgenai-B-r2-anchor-android` | job anchor | **PASS** | PASS | PASS | — (allowed: reply-off-task) | なし |
| `2026-10-15-dashboard-v1-pixel8a-ortgenai-B-r2-android` | job payload | **PASS** | PASS | PASS | — | なし |
| `2026-10-15-dashboard-v1-pixel8a-ortgenai-C-anchor-android` | job anchor | **PASS** | PASS | PASS | — (allowed: reply-off-task) | なし |
| `2026-10-15-dashboard-v1-pixel8a-ortgenai-C-android` | job payload | **PASS** | PASS | PASS | — | なし |
| `2026-10-15-dashboard-v1-pixel8a-ortgenai-C-r2-anchor-android` | job anchor | **PASS** | PASS | PASS | — (allowed: reply-off-task) | なし |
| `2026-10-15-dashboard-v1-pixel8a-ortgenai-C-r2-android` | job payload | **PASS** | PASS | PASS | — | なし |
| `2026-10-15-dashboard-v1-s26-0180-s5a-anchor-android` | job anchor | **HOLD** | HOLD | HOLD | reference-uncommitted (allowed: reply-off-task) | なし |
| `2026-10-15-dashboard-v1-s26-0180-s5a-android` | job payload | **PASS** | PASS | PASS | — | なし |
| `2026-10-15-dashboard-v1-s26-0180-s5b-anchor-android` | job anchor | **PASS** | PASS | PASS | — (allowed: reply-off-task) | なし |
| `2026-10-15-dashboard-v1-s26-0180-s5b-android` | job payload | **PASS** | PASS | PASS | — | なし |
| `2026-10-15-dashboard-v1-s26-0180-s6-anchor-android` | job anchor | **PASS** | PASS | PASS | — (allowed: reply-off-task) | なし |
| `2026-10-15-dashboard-v1-s26-0180-s6-android` | job payload | **PASS** | PASS | PASS | — | なし |
| `2026-10-15-dashboard-v1-s26-0180-s7-anchor-android` | job anchor | **PASS** | PASS | PASS | — (allowed: reply-off-task) | なし |
| `2026-10-15-dashboard-v1-s26-0180-s7-android` | job payload | **PASS** | PASS | PASS | — | なし |
| `2026-10-15-dashboard-v1-s26-0180-s8a-anchor-android` | job anchor | **PASS** | PASS | PASS | — (allowed: reply-off-task) | なし |
| `2026-10-15-dashboard-v1-s26-0180-s8a-android` | job payload | **PASS** | PASS | PASS | — | なし |
| `2026-10-15-dashboard-v1-s26-0180-s8b-anchor-android` | job anchor | **PASS** | PASS | PASS | — (allowed: reply-off-task) | なし |
| `2026-10-15-dashboard-v1-s26-0180-s8b-android` | job payload | **PASS** | PASS | PASS | — | なし |
| `2026-10-17-dashboard-v1-iphone17pro-0180-aa-i1-anchor-ios` | job anchor | **PASS** | PASS | PASS | — (allowed: engine-stamp, prompt-newtag, reply-off-task) | なし |
| `2026-10-17-dashboard-v1-iphone17pro-0180-aa-i1-ios` | job payload | **PASS** | PASS | PASS | — (allowed: engine-stamp, prompt-newtag, reply-off-task) | なし |
| `2026-10-18-dashboard-v1-s26-ddp-m1q-36-android` | job payload (ddp) | **PASS** | PASS | — | — (allowed: gen-budget) | なし |

集計: PASS 87 / HOLD 28 / FAIL 1 (計 116 dir)。r8 前の checker: PASS 87 / HOLD 28 / FAIL 1。

- hand run: PASS 0 / HOLD 12 / FAIL 1 (13)
- job anchor: PASS 46 / HOLD 4 / FAIL 0 (50)
- job payload: PASS 40 / HOLD 12 / FAIL 0 (52)
- job payload (ddp): PASS 1 / HOLD 0 / FAIL 0 (1)

新規則の finding がある dir: 0。r8 前と verdict が変わった dir: 0 (なし)。新規則以外の finding は r8 前と全 dir で同一: yes。

## r1 の (a) との差

r1 (a) の 88 dir: r1 は PASS 77 / HOLD 11 / FAIL 0、今 PASS 77 / HOLD 11 / FAIL 0。verdict が r1 と違う dir: 0。

今 FAIL の dir (全 1): `2026-09-27-tts-rtf-v1-s26-anchor-android` (hand run; not-admitted, not-job; r1 (a) の外; r8 前 FAIL; 新規則の finding なし)

