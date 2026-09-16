# 2026-09-17 — Qwen3 GPU-composite bundles on the prebuilt Metal dylib from LiteRT-LM main (PR #3605 / 4453b286): both fixes land; decode +34 % / +19 % at 1,024 prefill, no change at 31,744

One-line result: the prebuilt `libLiteRtMetalAccelerator.dylib` merged into LiteRT-LM `main` on 2026-09-16 (commit `4453b286`, built
from LiteRT `1901301f`) loads both composite bundles with **zero shape mismatches** and correct output, on the same v0.17.0-tag
`litert_lm_advanced_main` that logged 28 / 108 mismatches and emitted token salad with the v0.17.0 dylib on 09-11 and 09-16. With the
two composites active, decode at 1,024 prefill rises 263 → 354 tok/s (Qwen3-0.6B) and 112 → 133 (Qwen3-4B); at 31,744 prefill
neither prefill nor decode moves (within 4 %). The bundles without the composites read the same on the new dylib as on the release
one. Provenance (host, binary, both dylibs, ancestry of the pin, models, flags): `PROVENANCE.md`. Every command: `logs/runlog.txt`.

## Numbers — same binary, Mac Studio M4 Max, `--num_iterations=3`, `--disable_cache=true`

Pooled median of all iterations across the processes (per-process medians in parentheses); prefill tok/s = `Prefill Speed`,
decode tok/s = `Decode Speed` (256 tokens after the prefill), TTFT = `Time to first token`. New dylib = `dcd3c3ef…` (4453b286),
release = v0.17.0 `ac988ae2…`. Two processes per cell; the release control's second process at 31,744 was run after the fact audit
(the 4B control's first process read 41.4 / 39.0 / 44.6 tok/s decode, its second 44.6 / 44.9 / 44.7). Raw: `logs/SUMMARY_benchmarks.txt`, per leg `logs/*_b1k.log`, `logs/*_b31k.log`.

| bundle (published 09-11) | dylib | 31,744 / 256 (`--max_num_tokens=32768`): prefill · decode · TTFT | 1,024 / 256 (`1280`): prefill · decode |
|---|---|---:|---:|
| Qwen3-0.6B, composites on (`bd685768…`) | new | 1,392 (1,392 / 1,393) · 69.6 (69.5 / 70.2) · 22.8 s | 9,889 (9,889 / 9,892) · 353.8 (355.8 / 353.6) |
| Qwen3-0.6B, composites off (`eaa73f7e…`) | new | 1,383 (1,383 / 1,382) · 70.4 (70.4 / 70.5) · 23.0 s | 9,556 (9,557 / 9,556) · 263.5 (262.5 / 263.9) |
| Qwen3-0.6B, composites off | release | 1,389 (1,387 / 1,390) · 70.3 (70.3 / 70.3) · 22.9 s | 9,550 (9,574 / 9,541) · 262.4 (262.4 / 262.4) |
| Qwen3-4B, composites on (`6edb8266…`) | new | 472 (473 / 468) · 45.8 (47.1 / 44.5) · 67.4 s | 1,676 (1,676 / 1,676) · 133.4 (133.3 / 133.4) |
| Qwen3-4B, composites off (`c65779e9…`) | new | 473 (474 / 472) · 44.2 (44.4 / 44.0) · 67.1 s | 1,662 (1,662 / 1,662) · 112.0 (112.1 / 112.0) |
| Qwen3-4B, composites off | release | 472 (468 / 476) · 44.6 (41.4 / 44.7) · 67.3 s | 1,660 (1,661 / 1,660) · 111.6 (112.0 / 111.4) |

Reading: at 1,024 the composites raise decode by 34 % (0.6B, 263.5 → 353.8) and 19 % (4B, 112.0 → 133.4) and prefill by 3.5 % / 0.8 %;
at 31,744 the on/off pairs differ by ≤ 0.7 % in prefill and by −1 % (0.6B) / +4 % (4B) in decode, i.e. nothing outside the
run-to-run spread (the 4B composite decode read 47.1 in one process and 44.5 in the other). The dylib swap alone leaves the
bundles without the composites unchanged (new vs release: ≤ 1 % in every cell of both configs on pooled medians; the largest
gap is the 4B 31,744 decode, 44.18 vs 44.63 — there the release control's first process read 41.4 / 39.0 / 44.6 and its second,
run 15 min later under lighter load (1-min load 3.7 vs 6.9–7.9 for the batch), 44.6 / 44.9 / 44.7, so per process that one cell
spreads up to 7 %). Against the 09-16 rows on the release dylib
(0.6B 1,364 / 1,379 · 68.1 / 67.7 at 31,744, 9,316 / 9,459 · 246.0 / 249.6 at 1,024; 4B 471 / 471 · 43.5 / 44.0, 1,645 / 1,638 ·
105.8 / 108.0) today's release rows sit 1–6 % higher at 1,024 — host load differs between the two days (09-16 had an iPhone
session running from this Mac), which is why every comparison here is same-session. Fengwu's M4 Pro reference for the composite
bundles after the kernel fixes, 0.6B 1,061 and 4B 329 tok/s prefill at 31,744, is a different chip (273 GB/s vs 546); the rows above
are this Mac's numbers, not a comparison with his. The prefill gains he describes for the fused FlashAttention-2 kernel
(`89116780`, +40–50 %) are not in this dylib by design (it stops one commit before), so the 31,744 rows are this Mac's "before"
for that.

## Correctness on the new dylib

- Text runs (`logs/new_*_run.log`, the 996-token passage + `/no_think`): all four bundles exit 0, `Shape mismatch` 0, `Validation
  error` 0, `name=GPU Metal`, `Created a Metal device`. The 4B composite bundle's answer is byte-identical to the 4B bundle without
  the composites (273 B: sawmill → fishing → small brick works → tourism, railway 1879; `logs/new_4b_11_answer.txt` vs
  `logs/new_4b_9_answer.txt`). The two 0.6B files both answer with four industries and the 1879 railway, in different wording
  (`logs/new_06b_*_answer.txt`). On 09-16 with the release dylib the same composite files gave 28 / 108 mismatches and token salad.
- 8-question gate on Metal (`scripts/gate8q_adv.py`, one process per question, `/no_think`; `logs/gate8q_new_*.json`,
  `logs/driver.log`): **Qwen3-4B composites on 8/8, Qwen3-4B composites off 8/8, Qwen3-0.6B composites off 8/8, Qwen3-0.6B
  composites on 7/8** — the rhyme prompt ("Roses are red, violets are ___") returns `violets.`; every other answer is right and no
  run logs a mismatch. CPU path (`--backend=cpu`, XNNPACK, same binary and bundles; `scripts/gate8q_adv_backend.py`, `logs/gate8q_cpu_06b_*.json`): both 0.6B files score 7/8 with the same miss (capital → "Hachioji."; the 09-11 Metal miss on the non-composite file was "Hokkaido.") and both answer the rhyme prompt "violets are blue." — and the 0.6B file without the composites answers the rhyme prompt "green, blue, or white." on Metal (today on the new dylib,
  and on 09-16 on the release dylib: `../2026-09-16-qwen3-composite-dylib-761d99cb-mac/logs/gate8q_rel_06b_9.json`), passing
  only because the check accepts the substring "blue". So the Metal answer to this prompt moves for both 0.6B files and on both
  dylibs: the divergence is not specific to the composite graph or to this dylib. What this run cannot separate is Metal's fp16
  activations from any kernel difference (one greedy process per question, no logit margins). Side note: on the CPU path the composite file takes 30–62 s per question against 3 s for the file without the composites (the composite ops fall back to their decompositions there), which is why these bundles are GPU files.
  For scale: on 09-11 the 0.6B file without the composites scored 7/8 once on Metal (capital → "Hokkaido.") and 8/8 on 09-16; one
  greedy token on a 0.6B int4 file is a signal to record, not a kernel verdict.

## The 09-11 measurement form on the new dylib (`logs/*_promptbench_r*.log`, `scripts/after_driver_promptbench.sh`)

`--benchmark=true --input_prompt=<996-token passage> /no_think --max_num_tokens=4096` (decode over the generated answer, 85–101
tokens; two processes): 0.6B composites on prefill 6,732 / 6,856, decode 297.6 / 323.1; 0.6B composites off 6,684 / 6,628, 217.0 /
210.2 (release dylib 6,632 / 6,554, 195.7 / 207.2); 4B composites on 1,379 / 1,382, 115.2 / 115.0; 4B composites off 1,381 / 1,379,
95.0 / 93.6 (release 1,384 / 1,380, 94.8 / 94.8). This is the form behind the 09-11 table
Fengwu quoted. The "447" (0.6B) and "144" (4B) there were the earlier composite exports of 09-11 running with the mismatched
kernels (wrong output, void; FINDINGS §11–12), not today's `p1024_*` files — the published 0.6B composite file itself read 356
in that state on 09-11, and the 09-11 readings of the published files without the composites (188–198 / 71–95) were voided
because another lane held the GPU (FINDINGS §13). So today's rows are the first valid readings of the published files in this
form, and there is no same-file 09-11 baseline to set them against. Decode lengths: 0.6B composites 101 tokens vs 85 without
(different answers), 4B 91 tokens in every arm. Prefill in this form is 6.6–6.9k on the 0.6B files, versus 9.5–9.9k with `--benchmark_prefill_tokens=1024` — the mode
difference recorded on 09-16.

## What would change the picture

A prebuilt built past `89116780` once the litert-torch exporter change lands (Fengwu: he will update the prebuilts to head then).
The run dirs, the tag-built CLI, the bundles and `scripts/leg.sh` are unchanged; drop the next dylib into a third run dir and
re-run `scripts/run_all.sh`.
