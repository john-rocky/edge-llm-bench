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

<!-- third ladder of the lane: round r16 (the MLX Gemma 4 PTQ rows beside the QAT OptiQ rows, the iPhone 18 Pro's first sitting); a bench lane keeps one file per round topic, the conversion-lane lint does not apply -->

# SPEED_LADDER — Gemma 4 E2B / E4B → MLX (mlx-swift) on the iPhone 18 Pro: the page's two MLX rows (QAT OptiQ, PTQ 4bit)

runtime: mlx-swift (mlx-swift-lm 60bd0d7880c82980f9481f8be78862e9b63c58a3), the bench app com.example.CoreMLLLMChat (the 2026-10-19 13:12 build: record names to the fraction of a second)
model: mlx-community/gemma-4-e2b-it-qat-OptiQ-4bit, gemma-4-e2b-it-4bit, gemma-4-e4b-it-4bit (gemma-4-e4b-it-qat-OptiQ-4bit: the weekly rows' exclude=)
device: iPhone 18 Pro (iPhone19,2), iOS 27.2, 11,555 MB; the 4bit bundles copied over USB into the app's Hub cache (no Wi-Fi download)
parity bar: the text screen (session_check reply_rules on every run) and a person's read of one stored reply per cell; the class is shown in the row's name (owner decision 2026-10-19 via code-2d)

Round r16 (2026-10-19). One job-route sitting, campaign `2026-10-19-dashboard-v1-iphone18pro-mlx-ptq-r3-ios` (anchor phase admitted at ratio 1.003),
payload 13:37:53–14:15:30 JST, cooldown 300 s between cells, 4 runs a cell. Metric = render_leaderboard.arm_row's warm decode median (runs 2–4).
Full table: ROUND16.md "計測の表". The post step held the sitting (its admission reference is uncommitted), so the rows are on disk, not committed yet.

## 梯子(ladder — 1 行 = 1 form。測った形は全部残す。ship = 出荷する形)
| # | form | backend | device | workload | metric | parity | status | evidence | ship |
|---|---|---|---|---|---|---|---|---|---|
| 1 | E2B qat-OptiQ-4bit (QAT, Hub 6bf302fd) | gpu | iPhone 18 Pro | p1107/d256 | 52.09 tok/s (n 3, spread 0.0 %), prefill 4,505, peak 5,028 MB | PASS 4/4; the reply starts the list | measured | MAIN results/raw/2026-10-19-dashboard-v1-iphone18pro-mlx-ptq-r3-ios | ship (QAT row) |
| 2 | E2B 4bit (PTQ, Hub 23876752) | gpu | iPhone 18 Pro | p1107/d256 | 68.19 tok/s (n 3, spread 1.7 %), prefill 4,874, peak 3,413 MB | PASS 4/4 (screen); the reply declines the lorem passage | measured | same dir | ship (PTQ row) |
| 3 | E4B 4bit (PTQ, Hub 475b9088) | gpu | iPhone 18 Pro | p1107/d256 | 36.80 tok/s (n 3, spread 0.6 %), prefill 1,462, peak 5,139 MB | PASS 4/4 (screen); the reply declines the lorem passage | measured | same dir | ship (PTQ row) |
| 4 | E4B qat-OptiQ-4bit (QAT, 6.5 GB text weights) | gpu | iPhone 18 Pro | p1107/d256 | — | — | not run: the weekly rows' exclude=app-killed-at-model-load-sigkill (iPhone 17 Pro, 2026-09-06) | matrices/dashboard-text-v1.cells | — |
| 5 | E2B qat-OptiQ-4bit (QAT) | gpu | iPhone 18 Pro | short-chat p21/d128 | 54.73 tok/s (n 3, spread 0.1 %), prefill 344, peak 4,631 MB | PASS 4/4 | measured | same dir | ship (QAT row) |
| 6 | E2B 4bit (PTQ) | gpu | iPhone 18 Pro | short-chat p21/d128 | 71.35 tok/s (n 3, spread 0.1 %), prefill 379, peak 3,039 MB | PASS 4/4 | measured | same dir | ship (PTQ row) |
| 7 | E4B 4bit (PTQ) | gpu | iPhone 18 Pro | short-chat p21/d128 | 38.17 tok/s (n 3, spread 0.3 %; the first capture SPREAD 17.0, quarantined), prefill 177, peak 4,583 MB | PASS 4/4 | measured | same dir | ship (PTQ row) |

## レバー(levers — 試すべき手を全部。1 行 = 1 手。n-a は「この model には当てはまらない」理由つき)
| lever | status | result / reason | evidence |
|---|---|---|---|
| quant | measured | QAT OptiQ (4 / 8 bit mixed) vs PTQ 4bit (uniform 4 bit) in one sitting: PTQ decodes E2B 68.19 vs 52.09 (1K) and 71.35 vs 54.73 (short-chat), peak lower (3,413 vs 5,028 MB); both are page rows by decision | ROUND16.md 計測の表 |
| memory fit | measured | the E4B PTQ build (5.1 GB of safetensors) loads on the 18 Pro, peak 5,139 MB of 11,555; the E4B OptiQ build (6.5 GB of text weights) stays excluded | ROUND16.md |
| staging | measured | the 4bit bundles copied over USB into the app's Hub cache (refs/main + snapshots/<rev>/, one devicectl copy per file): load 1.2–1.9 s, no download | ROUND16.md 転送の結果 |
| precision | n-a: the app has no MLX dtype option; each bundle fixes its dtypes | - | ROUND14.md |
| shape | n-a: the task's fixed prompt and budget | - | - |
| npu-path | n-a: MLX runs on the Apple GPU only | - | - |
| state | n-a: mlx-swift-lm's default KV cache | - | ROUND14.md |

## 例外(exception — 同じ device + workload でもっと速い形を出荷しないときだけ理由。無ければ「なし」)
なし(owner decision 2026-10-19: the QAT and the PTQ forms both ship, as the model's two MLX rows with the class in the name)

## 残り(remaining — まだ試していないレバーと見込み。無ければ「なし」。1 件でも書けば lint は HOLD)
なし

<!-- fourth ladder of the lane: round r15 (the Android llama.cpp arm's Gemma 4 thinking mode); a bench lane keeps one file per round topic, the conversion-lane lint does not apply -->

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

---

<!-- ladder of round r18 (the Qwen3 0.6B dynamic INT4 file: the current Hub file beside a local candidate with the 2026-08-05 graph); a bench lane keeps one file per round topic, the conversion-lane lint does not apply -->

# SPEED_LADDER — Qwen3 0.6B dynamic INT4 (litert-community/Qwen3-0.6B) on LiteRT-LM v0.18.0: the current file (2026-09-21 graph) or the 2026-08-05 graph with the current LlmMetadata

runtime: litert (LiteRT-LM v0.18.0: the Mac yardstick .build/dd-mac-q06cand, the iPhone app b714ce21…, the Android flat binaries)
model: Qwen3-0.6B_dynamic_wi4b32_afp32.litertlm (Hub a3c5d805, sha256 03e7da1e…) and the local candidate Qwen3-0.6B_dynamic_wi4b32_afp32.r0805meta018.litertlm (sha256 e6bf25c0…, not on the Hub)
device: Mac Studio M4 Max (Mac16,9) macOS 27.0; iPhone 18 Pro (iPhone19,2) iOS 27.2; Pixel 8a (akita) Android 16; the Galaxy S26 not measured (the supervisor's decision: its numbers would not change the reading)
parity bar: the text check (the Android runner's; the session_check text screen on the Mac and the iPhone) and the owner's rule: the candidate replaces the Hub file only if its same-sitting decode and prefill stay within −3 % of the current file on every device and backend

Round r18 (2026-10-19). One sitting per device and cells file (matrices/q06-candidate-*.cells), the two files alternating row by row.
Workload = long-context-1024-gen256 (prompt 1,338 tokens, 256 decoded, ctx 2048). Metric = render_leaderboard.arm_row: the warm decode
median on the Mac and the iPhone (runs 2–4), the cold median on Android (each launch's first run), prefill on the same regime. Short-chat
and the native 1024x256 rows: ROUND18.md "計測の表". Verdict: not replaced (slower on the Pixel 8a GPU).

## 梯子(ladder — 1 行 = 1 form。測った形は全部残す。ship = 出荷する形)
| # | form | backend | device | workload | metric | parity | status | evidence | ship |
|---|---|---|---|---|---|---|---|---|---|
| 1 | current file (2026-09-21 graph: odml.swiglu, prefill logits) | gpu | M4 Max | p1338/d256 | 314.9 tok/s (n 3), prefill 7,342 | PASS 4/4 (screen) | measured | ../2026-10-19-dashboard-v1-m4max-q06cand-mac/ (main) | ship |
| 2 | candidate (2026-08-05 graph + current LlmMetadata) | gpu | M4 Max | p1338/d256 | 310.4 tok/s (−1.4 %), prefill 7,441 (+1.4 %) | PASS 4/4 | measured | same | |
| 3 | current file | cpu | M4 Max | p1338/d256 | 47.8 tok/s, prefill 525.9 | PASS 4/4 | measured | same | ship |
| 4 | candidate | cpu | M4 Max | p1338/d256 | 48.2 tok/s (+0.7 %), prefill 543.0 (+3.3 %) | PASS 4/4 | measured | same | |
| 5 | current file | gpu | iPhone 18 Pro | p1338/d256 | — | — | no-go: the Metal engine is not created ("half4 half4(res)_final", 9 compile-error lines a launch, the 2026-09-21 graph whatever the LlmMetadata) | r18-iphone-2x2/console_d_graph0921_meta018.txt, console_c_graph0921_meta0805.txt | |
| 6 | candidate | gpu | iPhone 18 Pro | p1338/d256 | 142.5 tok/s (n 3), prefill 3,477.5 | PASS 4/4 | measured | ../2026-10-19-dashboard-v1-iphone18pro-q06cand-ios/ (main) | |
| 7 | current file | cpu | iPhone 18 Pro | p1338/d256 | 50.1 tok/s (spread 45.8 %, heat), prefill 402.3 | PASS 4/4 | measured | same | ship |
| 8 | candidate | cpu | iPhone 18 Pro | p1338/d256 | 49.7 tok/s (−0.7 %, spread 44.5 %), prefill 415.8 (+3.4 %) | PASS 4/4 | measured | same | |
| 9 | current file | gpu | Pixel 8a | p1338/d256 | 30.6 tok/s cold (all iterations 31.59), prefill 554.5 | PASS 6/6 | measured | ../2026-10-19-dashboard-v1-pixel8a-q06cand-gpu-android/ (main) | ship |
| 10 | candidate | gpu | Pixel 8a | p1338/d256 | 25.7 tok/s cold (−15.8 %; all iterations 27.36 = −13.4 %), prefill 573.9 (+3.5 %) | PASS 5/5 | measured | same | |
| 11 | current file | cpu | Pixel 8a | p1338/d256 | no number: every run capped 40–55 % (cpu-cap-rule) | PASS 6/6 | measured | ../2026-10-19-dashboard-v1-pixel8a-q06cand-cpu-android/ (main) | |
| 12 | candidate | cpu | Pixel 8a | p1338/d256 | no number: every run capped 40–55 % (cpu-cap-rule) | PASS 5/5 | measured | same | |

## レバー(levers — 試すべき手を全部。1 行 = 1 手。n-a は「この model には当てはまらない」理由つき)
| lever | status | result / reason | evidence |
|---|---|---|---|
| graph (the export) | measured | the 2026-08-05 graph (no odml.swiglu, no logits on the prefill signatures, decode 936 ops against 830) builds the iPhone 18 Pro's Metal engine where the 2026-09-21 graph does not; it decodes 13–22 % slower on the Pixel 8a GPU, −1.4 to −2.5 % on the Mac GPU, within −1 % on the iPhone CPU; why the Pixel GPU is slower is unverified | ROUND18.md "2×2 の結果", "計測の表" |
| LlmMetadata (the chat template) | measured | no part in the iPhone GPU failure (the 2×2: the 2026-09-21 graph fails with either metadata, the 2026-08-05 graph builds with either); the 2026-08-05 template fails the first turn on 0.18.0 (content parts), the current one answers | r18-iphone-2x2/ |
| quant | n-a: both files carry the same recipe (INT4 block-32 FC weights, the same FC inventory) | - | ROUND18.md "候補の作り方" |
| precision | n-a: no dtype option in this comparison; each backend's default activation type | - | - |
| shape | n-a: the protocol's fixed tasks (19-token chat, 1,338-token 1K, forced 1024 / 256) | - | - |
| npu-path | n-a: no NPU row for this file in this round | - | - |
| state | n-a: one fresh conversation per run | - | - |

## 例外(exception — 同じ device + workload でもっと速い形を出荷しないときだけ理由。無ければ「なし」)
- iPhone 18 Pro GPU: row 6 (the candidate) is the only form that runs and is not shipped: the owner's rule keeps one Hub file for every
  device, and the candidate is slower on the Pixel 8a GPU (rows 9–10); an iOS-only file or a card note is the supervisor's next step.
- Mac CPU row 4 (+0.7 %): inside the run-to-run spread (2.7 %), not shipped for the same rule.

## 残り(remaining — まだ試していないレバーと見込み。無ければ「なし」。1 件でも書けば lint は HOLD)
- the cause of the Pixel 8a GPU slowdown: an export of the 2026-09-21 recipe without the odml.swiglu composite, A/B on the Pixel 8a and the
  iPhone GPU (does the iPhone failure follow the composite, and does the Pixel speed); outside this round (the supervisor's call).
- the Galaxy S26 (Adreno GPU, CPU): not measured by decision; the Pixel 8a CPU pair again on a cool phone if its numbers are wanted.

---

<!-- ladder of round r17 (the 1K task's tail); a bench lane keeps one file per round topic, the conversion-lane lint does not apply -->

# SPEED_LADDER — the 1K cross-arm task on the noref tail (round r17)

runtime: llama.cpp b11721 (Apple adapter, jinja), mlx-swift (mlx-swift-lm 60bd0d78), LiteRT-LM v0.18.0 (Mac yardstick)
model: unsloth gemma-4-E4B-it / Qwen3-1.7B GGUFs Q4_K_M, mlx-community/gemma-4-e4b-it-qat-OptiQ-4bit, litert-community/gemma-4-E2B-it-litert-lm
device: Mac Studio M4 Max (Mac16,9), macOS 27.0 (26A428), yardstick `.build/dd-mac-noref` (sha256 7ad3f33c…, built 12:28 from the side tree)
parity bar: every arm gets the same text (prompts/text/long-context-1024-gen256.txt = the Swift task, byte for byte); the reply answers the
task (the list, no refusal) and runs to the 256-token budget

This round changed the task's text, not an engine. The smoke is one launch per cell (runs=1, 30 s cooldowns, one quiet hold, 2026-10-19
12:28–12:30 JST): a prompt check, not a session. Its rates are in the records and are not used or set side by side here (the public repo
carries no cross-runtime standings).

## 梯子(ladder — 1 行 = 1 form。測った形は全部残す。ship = 出荷する形)
| # | form | backend | device | workload | metric | parity | status | evidence | ship |
|---|---|---|---|---|---|---|---|---|---|
| 1 | llama.cpp Gemma 4 E4B (jinja, thinking false), noref tail | gpu (Metal) | Mac M4 Max | 1K, noref tail | 1,123 prompt tok, 256 generated (rate not used) | PASS: "Here are 25 distinct things …" (passage tail: 1,106 tok, declined in 86) | measured | MAIN results/raw/2026-10-19-noref-tail-probe-mac/ | ship |
| 2 | MLX gemma-4-e4b-it-qat-OptiQ-4bit, noref tail | gpu | Mac M4 Max | 1K, noref tail | 1,124 prompt tok, 256 generated (rate not used) | PASS: "Here are 25 distinct things …" (passage tail: 1,107 tok, declined) | measured | same dir | ship |
| 3 | LiteRT-LM gemma-4-E2B-it, noref tail | gpu (WebGPU) | Mac M4 Max | 1K, noref tail, ctx 2048 | 1,123 prompt tok, 256 generated (rate not used) | PASS: "Here are 25 distinct things …" (passage tail: 1,106 tok, opened "The provided text is placeholder …") | measured | same dir | ship |
| 4 | llama.cpp Qwen3 1.7B (jinja, template default), noref tail | gpu (Metal) | Mac M4 Max | 1K, noref tail | 1,355 prompt tok, 256 generated (rate not used) | PASS: `<think>` on the task, as on the passage tail (1,338 tok) | measured | same dir | ship |
| 5 | the passage tail (until 2026-10-19), the same four cells | as above | Mac M4 Max | 1K, passage tail | 1,106 / 1,107 / 1,106 / 1,338 prompt tok | FAIL on Gemma 4: the replies decline the lorem passage or call it placeholder text; Qwen3 answers | measured | ../2026-10-19-dashboard-v1-m4max-llama-b11721-mac, ../2026-10-19-mlx-gemma4-file-mac, ../2026-10-19-dashboard-v1-m4max-0180-rebuilt-mac | |

## レバー(levers — 試すべき手を全部。1 行 = 1 手。n-a は「この model には当てはまらない」理由つき)
| lever | status | result / reason | evidence |
|---|---|---|---|
| prompt tail | measured | the noref sentence vs the passage sentence: +17 prompt tokens on the Gemma 4 and Qwen3 vocabularies, every Gemma 4 reply on the task | ROUND17.md smoke |
| quant | n-a: this round does not change a file or an engine | — | — |
| precision | n-a: same | — | — |
| shape | n-a: the budget (prompt ~1,024, decode 256, ctx 2048) is unchanged by decision | — | — |
| npu-path | n-a: the Mac arms have none here | — | — |
| state | n-a: one fresh conversation per run, unchanged | — | — |

## 例外(exception — 同じ device + workload でもっと速い形を出荷しないときだけ理由。無ければ「なし」)
- Row 5 (the passage tail) is not shipped whatever its rates: on Gemma 4 its replies decline the task, so the column timed refusals on some
  arms and lists on others.

## 残り(remaining — まだ試していないレバーと見込み。無ければ「なし」。1 件でも書けば lint は HOLD)
なし
