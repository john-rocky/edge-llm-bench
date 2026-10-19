# SPEED_LADDER — llama.cpp arm (Mac / iPhone), the GGUF chat-template change of round r13

runtime: llama.cpp (Apple adapter `LlamaCppRuntime`, the Mac yardstick and the iPhone app)
model: unsloth Gemma 4 E2B / E4B and Qwen3 0.6B / 1.7B GGUFs, Q4_K_M
device: Mac Studio M4 Max (Mac16,9), macOS 27.0 (26A428), llama.cpp b11721 (xcframework, Metal), yardstick `.build/dd-mac-tmpl`
parity bar: the prompt = the GGUF's own chat template as Python jinja2 renders it (byte for byte), thinking as the other arms run it
(methodology/fairness-rules.md §1); the reply on the task (no "[Item" skeleton, the task's words)

This round changed the prompt the arm builds, not the engine. Every speed below is a smoke: one launch per cell, runs=1, 30 s
cooldowns, in one quiet hold (2026-10-19 11:09–11:11 JST) — not a session, not comparable with the page's sessions.

## 梯子(ladder — 1 行 = 1 form。測った形は全部残す。ship = 出荷する形)
| # | form | backend | device | workload | metric | parity | status | evidence | ship |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Qwen3 0.6B, jinja render, thinking template-default | gpu (Metal) | Mac M4 Max | short-chat, 19 prompt tok | decode 379.2 tok/s, prefill 3369 tok/s, TTFT 20 ms | PASS: render = jinja2; `<think>` reply as before | measured | MAIN results/raw/2026-10-19-llama-template-probe-mac/ | ship |
| 2 | Qwen3 1.7B, jinja render, thinking template-default | gpu (Metal) | Mac M4 Max | 1K, 1338 prompt tok | decode 164.7 tok/s, prefill 5053 tok/s, TTFT 353 ms | PASS: render = jinja2; `<think>` reply as before | measured | same dir | ship |
| 3 | Gemma 4 E2B, jinja render, thinking false | gpu (Metal) | Mac M4 Max | 1K, 1106 prompt tok | decode 144.6 tok/s, prefill 3012 tok/s, TTFT 420 ms, 256 tok | PASS: render = jinja2; on-task reply | measured | same dir | ship |
| 4 | Gemma 4 E4B, jinja render, thinking false | gpu (Metal) | Mac M4 Max | short-chat, 20 prompt tok | decode 92.1 tok/s, prefill 1699 tok/s, TTFT 68 ms | PASS: render = jinja2; on-task reply | measured | same dir | ship |
| 5 | Gemma 4 E4B, jinja render, thinking false | gpu (Metal) | Mac M4 Max | 1K, 1106 prompt tok | decode 84.9 tok/s over 86 tok (EOS), prefill 1562 tok/s, TTFT 798 ms | PASS on the template (no skeleton; = llama-cli greedy word for word); the reply declines the lorem task | measured | same dir; ROUND13.md "llama-cli greedy" | ship |
| 6 | Gemma 4 E4B, bare prompt (before 2026-10-19, reference) | gpu (Metal) | Mac M4 Max | 1K, 1098 prompt tok | decode 90.7 tok/s over 256 tok (the "[Item n]" skeleton) | FAIL: no chat template | measured | MAIN results/raw/2026-10-19-dashboard-v1-m4max-0180-rebuilt-mac/ | |

## レバー(levers — 試すべき手を全部。1 行 = 1 手。n-a は「この model には当てはまらない」理由つき)
| lever | status | result / reason | evidence |
|---|---|---|---|
| chat template path | measured | jinja (the GGUF's template) vs built-in set vs bare: Gemma 4 E4B 1K 1106 vs (not in the set) vs 1098 prompt tokens; Qwen3 jinja = built-in, 19 / 1338 | ROUND13.md 下見 / smoke |
| thinking | measured | Gemma 4 thinking false (= the template's default) vs true: 20 / 1106 vs 27 / 1113 prompt tokens (reference counts); the arm runs false, as LiteRT-LM / MLX | ROUND13.md 下見 |
| quant | n-a: this round does not change the file or the engine | — | — |
| precision | n-a: same | — | — |
| shape | n-a: same | — | — |
| npu-path | n-a: llama.cpp on Apple has no NPU path | — | — |
| state | n-a: one fresh conversation per run, unchanged | — | — |

## 例外(exception — 同じ device + workload でもっと速い形を出荷しないときだけ理由。無ければ「なし」)
- row 6 (bare) decodes faster over its 256 tokens than row 5 over 86, and is not shipped: without the chat template it is not a measurement
  (fairness-rules §1); the two rows are different answers, not two forms of one.

## 残り(remaining — まだ試していないレバーと見込み。無ければ「なし」。1 件でも書けば lint は HOLD)
なし

---

<!-- second ladder of the lane: round r14 (the MLX Gemma 4 file); a bench lane keeps one file per round topic, the conversion-lane lint does not apply -->

# SPEED_LADDER — Gemma 4 E2B / E4B → MLX (mlx-swift): which mlx-community file the page runs

runtime: mlx-swift (mlx-swift-lm 60bd0d7880c82980f9481f8be78862e9b63c58a3, mlx-swift 0bb916c67f4b9e5c682cbe02a42c701c93ab5021)
model: mlx-community/gemma-4-{e2b,e4b}-it-qat-OptiQ-4bit, gemma-4-{e2b,e4b}-it-4bit, gemma-4-{E2B,E4B}-it-qat-mobile
device: Mac Studio (M4 Max, Mac16,9), macOS 27.0 (26A428), yardstick .build/dd-mac (2026-10-19 05:59)
parity bar: the 1K task's text check (session_check reply_rules on every run; a person reads one stored reply per cell) and the page's class rule (QAT)

Round r14 (2026-10-19). One sitting 10:41–11:08 JST, campaign `2026-10-19-mlx-gemma4-file-mac` (stored report in the main
checkout's results/raw, committed by the supervisor). Workload = long-context-1024-gen256 (prompt 1,107 tokens, 256 decoded).
Metric = render_leaderboard.arm_row's warm decode median (runs 2–4). Full table and the decision: ROUND14.md "計測の表", docs/dashboard-cells-v1.md "MLX Gemma 4 file (2026-10-19)".

## 梯子(ladder — 1 行 = 1 form。測った形は全部残す。ship = 出荷する形)
| # | form | backend | device | workload | metric | parity | status | evidence | ship |
|---|---|---|---|---|---|---|---|---|---|
| 1 | E2B qat-OptiQ-4bit: QAT base, mlx-optiq 4 / 8 bit per layer, g64, 5.24 bpw (Hub 6bf302fd) | gpu | M4 Max | p1107/d256 | 151.02 tok/s (n 3, spread 0.07 %), prefill 7,076, peak 5,246 MB | PASS 4/4 (screen); the reply starts the list | measured | ROUND14.md; ../2026-10-19-mlx-gemma4-file-mac/mlx-swift_mlx-community_gemma-4-e2b-it-qat-OptiQ-4bit_long-context-1024-gen256.jsonl | ship |
| 2 | E2B 4bit: PTQ, mlx_vlm.convert of google/gemma-4-E2B-it, uniform 4 bit g64 (Hub 23876752) | gpu | M4 Max | p1107/d256 | 178.68 tok/s (n 3, spread 0.18 %), prefill 7,105, peak 3,653 MB | PASS 4/4 (screen); the stored reply declines the lorem passage | measured | ROUND14.md; ../2026-10-19-mlx-gemma4-file-mac/mlx-swift_mlx-community_gemma-4-e2b-it-4bit_long-context-1024-gen256.jsonl | |
| 3 | E2B qat-mobile: Google mobile schema, quant_method gemma, per-channel 2 / 4 / 8 bit + static activation scales (Hub 0548ff6d) | gpu | M4 Max | p1107/d256 | — | — | no-go: loadFailed "Unhandled keys [input_activation_scale, output_activation_scale, weight_scale] … per_layer_projection" (mlx-swift-lm reads `quantization` only) | ROUND14.md; ../2026-10-19-mlx-gemma4-file-mac/NOTES-qat-mobile-load.txt | |
| 4 | E4B qat-OptiQ-4bit: QAT base, 4 / 8 bit per layer, g64, 5.17 bpw (Hub a78078f4) | gpu | M4 Max | p1107/d256 | text-fail: no number | FAIL 4/4 reply-off-task (the reply declines the lorem passage) | measured | ROUND14.md; ../2026-10-19-mlx-gemma4-file-mac/mlx-swift_mlx-community_gemma-4-e4b-it-qat-OptiQ-4bit_long-context-1024-gen256.jsonl | |
| 5 | E4B 4bit: PTQ, uniform 4 bit g64 (Hub 475b9088) | gpu | M4 Max | p1107/d256 | 111.97 tok/s (n 3, spread 0.23 %; the first launch SPREAD 17.7, quarantined), prefill 2,283, peak 5,403 MB | PASS 4/4 (screen); the stored reply declines | measured | ROUND14.md; ../2026-10-19-mlx-gemma4-file-mac/mlx-swift_mlx-community_gemma-4-e4b-it-4bit_long-context-1024-gen256.jsonl | |
| 6 | E4B qat-mobile: same format as row 3 (Hub 65982052) | gpu | M4 Max | p1107/d256 | — | — | no-go: loadFailed "Mismatched parameter language_model.lm_head.weight … Actual [262144, 640], expected [262144, 2560]" | ROUND14.md; ../2026-10-19-mlx-gemma4-file-mac/NOTES-qat-mobile-load.txt | |

## レバー(levers — 試すべき手を全部。1 行 = 1 手。n-a は「この model には当てはまらない」理由つき)
| lever | status | result / reason | evidence |
|---|---|---|---|
| quant | measured | the file is the lever: QAT OptiQ (4 / 8 bit mixed) and PTQ 4bit (uniform 4 bit) both load; in one sitting PTQ decodes E2B 178.68 and E4B 111.97 tok/s with lower peak memory, prefill about equal; the mobile schema does not load | ROUND14.md |
| precision | n-a: the yardstick has no MLX dtype option; each bundle fixes its dtypes | - | ROUND14.md |
| shape | n-a: the task is the protocol's fixed p1107 / d256 | - | ROUND14.md |
| npu-path | n-a: MLX runs on the Apple GPU only | - | ROUND14.md |
| state | n-a: mlx-swift-lm's default KV cache; OptiQ's kv_config.json (per-layer KV precision) is not read by mlx-swift-lm 60bd0d7 (no reference in its Libraries) | - | ROUND14.md |
| runtime version | blocked: a newer mlx-swift-lm (release-watch drift 60bd0d78 → 378f2449) may read quant_method gemma; the pin bump is its own round | - | ROUND14.md |

## 例外(exception — 同じ device + workload でもっと速い形を出荷しないときだけ理由。無ければ「なし」)
- Row 2 (E2B PTQ 4bit) decodes faster than the shipped row 1 in the same sitting and is not shipped: it is PTQ, and the page's rule
  takes the QAT class (the class of the page's comparison partner, the LiteRT-LM Gemma 4 bundles); its stored reply also declines
  the task.
- E4B: no form passes the bar. Row 4 (OptiQ, the only QAT form that loads) stays the page's file and its cell shows text-fail, no
  number; row 5 (PTQ 4bit) is not shipped for the class, and its stored reply declines the task like row 4's.
- The ladder lint's runtime list (litert | coreai | executorch | onnxruntime-genai) has no mlx-swift: this file records a bench
  round's file choice, not a conversion lane, and its FAIL on the `runtime:` header is expected.

## 残り(remaining — まだ試していないレバーと見込み。無ければ「なし」。1 件でも書けば lint は HOLD)
- runtime version: bump mlx-swift-lm and probe the qat-mobile bundles (one launch each); if they load, measure them with
  matrices/mlx-gemma4-file-mac.cells as QAT-class candidates.
- iPhone 18 Pro: the same procedure in its own sitting after the 13:00 weekly.

---

<!-- third ladder of the lane: round r15 (the Android llama.cpp arm's Gemma 4 thinking mode); a bench lane keeps one file per round topic, the conversion-lane lint does not apply -->

# SPEED_LADDER — llama.cpp arm (Android), Gemma 4 thinking off (round r15)

runtime: llama.cpp `llama-cli` (flat b11721 ff5a23376 on both phones, CPU, `-t 4`; the S26's Snapdragon side build b11469-snapdragon
ad2156533, `-ngl 99 --device HTP0 / GPUOpenCL`), driven by `android/bench/run_cell.py`
model: unsloth Gemma 4 E2B / E4B GGUF Q4_K_M (Qwen3 0.6B / 1.7B for the anchor and the unchanged-family check)
device: Pixel 8a 4C131JEKB15210 (Tensor G3, Android 16, mask f0), Galaxy S26 RFGL80R6A6H (SM8850, Android 16, no mask)
parity bar: thinking as the other arms run it (Gemma 4 off, Qwen3 the template's default; methodology/fairness-rules.md §1): no
`[Start thinking]` in a Gemma 4 run log, a reply on the task

This round changes the mode the arm runs, not the engine or the file. The probe rows are one launch each (runs=1, by hand under a
keeper hold, 2026-10-19 12:03–12:05 JST), not a session: their speeds are not comparable with the page's sessions.

## 梯子(ladder — 1 行 = 1 form。測った形は全部残す。ship = 出荷する形)
| # | form | backend | device | workload | metric | parity | status | evidence | ship |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Gemma 4 E2B, `-st`, thinking on (llama-cli's default; before 2026-10-19, reference) | cpu (flat b11721) | Pixel 8a | short-chat | decode 14.1 tok/s, prefill 32.5 tok/s (one run of the 10-19 sitting) | FAIL: `[Start thinking]`, the 128-token budget spent inside the thought | measured | MAIN results/raw/2026-10-19-dashboard-v1-pixel8a-llama-b11721-android/ (01-15-22 run) | |
| 2 | Gemma 4 E2B, `-st --chat-template-kwargs '{"enable_thinking":false}'` | cpu (flat b11721) | Pixel 8a | short-chat | decode 14.0 tok/s, prefill 26.5 tok/s (probe, 1 launch) | PASS: no `[Start thinking]`, a direct answer | measured | REPO results/raw/2026-10-19-probe-thinkoff-pixel8a-android/ (not committed) | ship |
| 3 | Qwen3 1.7B, `-st` (unchanged family check) | cpu (flat b11721) | Pixel 8a | short-chat | decode 21.2 tok/s, prefill 53.8 tok/s (probe, 1 launch) | PASS: `[Start thinking]` as on every arm (template default) | measured | same dir | ship |
| 4 | Gemma 4 E2B, side build, `-st --chat-template-kwargs '{"enable_thinking":false}' -ngl 99 -fa on -ub 1024` | npu (HTP0, b11469) | Galaxy S26 | short-chat | decode 29.9 tok/s, prefill 123.5 tok/s (probe, 1 launch, cpu-capped mark) | PASS: no `[Start thinking]`, a direct answer, text check PASS | measured | REPO results/raw/2026-10-19-probe-thinkoff-s26-side-android/ (not committed) | ship |
| 5 | Gemma 4 E2B, flat, thinking on (reference: the 10-19 05:52 b11721 sitting) | cpu (flat b11721) | Galaxy S26 | short-chat / 1K | short-chat 28.3 / 28.6 / 28.5, 1K 17.2 / 16.3 / 16.3 (all cpu-capped) | FAIL: `[Start thinking]` in every log | measured | MAIN results/raw/2026-10-19-dashboard-v1-s26-llama-b11721-android/ | |
| 6 | Gemma 4 E2B, flat, thinking off (job sitting) | cpu (flat b11721) | Galaxy S26 | short-chat | 28.9 / 28.7 / 28.8 after the gate's COLLAPSE re-run (quarantined 1.0 / 29.1 / 28.3); all cpu-capped >15 % | PASS: 0 `[Start thinking]` in 6 logs | measured, no page number (cpu-cap-rule) | MAIN results/raw/2026-10-19-dashboard-v1-s26-llama-thinkoff-e2b-android/ (721ee21e) | ship |
| 7 | Gemma 4 E2B, flat, thinking off (job sitting) | cpu (flat b11721) | Galaxy S26 | 1K | 15.8 / 16.0 / 16.4; all cpu-capped (caps down to 1785.6 / 1747.2 MHz) | PASS: 0 `[Start thinking]` in 3 logs | measured, no page number | same dir | ship |
| 8 | Gemma 4 E2B, flat, thinking off (job sitting, r2) | cpu (flat b11721) | Pixel 8a | short-chat | 12.8 / 13.0 / 13.2 after a COLLAPSE re-run (quarantined 12.3 / 13.1 / 8.4); page 13.1 (n=2); thinking-on reference 13.9 | PASS: 0 `[Start thinking]` | measured | MAIN results/raw/2026-10-19-dashboard-v1-pixel8a-llama-thinkoff-r2-android/ (2b4b6f37) | ship |
| 9 | Gemma 4 E2B, flat, thinking off (job sitting, r2) | cpu (flat b11721) | Pixel 8a | 1K | 5.0 / 5.8 / 7.9, all cpu-capped (policy4 down to 1065 / 2367 MHz); thinking-on reference 8.2–8.4 (capped) | PASS: 0 `[Start thinking]` | measured, no page number | same dir | ship |
| 10 | Gemma 4 E2B, side build, thinking off (job sitting) | npu (HTP0, b11469) | Galaxy S26 | short-chat | 28.9 / 29.9 / 30.3 → page 29.9 (n=3); thinking-on reference (10-11) page 28.3 | PASS: 0 `[Start thinking]`, text check PASS ×3 | measured | MAIN results/raw/2026-10-19-dashboard-v1-s26-llama-thinkoff-side-e2b-android/ (c9fa1590) | ship |
| 11 | Gemma 4 E2B, side build, thinking off (job sitting) | gpu (OpenCL, b11469) | Galaxy S26 | short-chat | 26.3 / 27.0 / 27.4 → page 26.65 (n=2); thinking-on reference (10-11) page 21.6 | PASS: 0 `[Start thinking]`, text check PASS ×3 | measured | same dir | ship |

## レバー(levers — 試すべき手を全部。1 行 = 1 手。n-a は「この model には当てはまらない」理由つき)
| lever | status | result / reason | evidence |
|---|---|---|---|
| thinking | measured | Gemma 4 off through the template variable (`--chat-template-kwargs '{"enable_thinking":false}'`): llama-cli takes it on b11721 and b11469 (rows 2, 4); the arm runs off, as LiteRT-LM / MLX / the Apple llama.cpp adapter | ROUND15.md probe |
| thinking switch | not tried | `-rea, --reasoning off` (in the b11721 / b11469 help, default auto) would be llama-cli's own switch; the template variable was kept because it is the one the Apple adapter passes (one mechanism on every llama.cpp row) | ROUND15.md 下見 |
| quant | n-a: this round does not change the file or the engine | — | — |
| precision | n-a: same | — | — |
| shape | n-a: same | — | — |
| npu-path | n-a: the side build's npu / gpu rows keep their build and flags; only the template variable is added | — | — |
| state | n-a: one single-turn process per run, unchanged | — | — |

## 例外(exception — 同じ device + workload でもっと速い形を出荷しないときだけ理由。無ければ「なし」)
- Row 1 (thinking on) decodes at the same rate as row 2 within one launch's noise and is not shipped: it runs another mode than every
  other arm (budget-mode-rule); it is a reference, not a candidate.

## 残り(remaining — まだ試していないレバーと見込み。無ければ「なし」。1 件でも書けば lint は HOLD)
- the S26's side E4B (npu / gpu short-chat) and flat E4B (short-chat, 1K) sittings: queued behind the asr lane at the round's close
  (ROUND15 handoff); expected: the same mode change, E4B's own speeds.
- the S26 llama.cpp CPU arm's cpu-cap: every flat Gemma 4 run of 10-19 (thinking on and off) is capped above 15 % on the S26 (policy6,
  cores 6-7, unmasked `-t 4`), so these page cells carry no number; a mask that keeps the four threads in policy0 (e.g. 0x0f) is untested
  (an owner decision: the S26's mask is "" since 2026-08-25).
