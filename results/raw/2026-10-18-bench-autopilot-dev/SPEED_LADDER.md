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
