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
