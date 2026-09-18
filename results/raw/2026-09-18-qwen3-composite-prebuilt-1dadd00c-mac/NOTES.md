# 2026-09-18 — Qwen3 GPU-composite bundles on the prebuilt Metal dylib from LiteRT-LM main 1dadd00c, plus the prefill-SDPA export: long-context prefill +45 % (0.6B) / +35 % (4B), decode unchanged

One-line result: the prebuilt `libLiteRtMetalAccelerator.dylib` that LiteRT-LM `main` carries since `1dadd00c` (2026-09-17, built from
LiteRT `0da36b31`, which includes the fused FlashAttention-2 prefill kernel `89116780`) runs the two published composite bundles exactly
as the 09-17 prebuilt did (same speed within 0.4 %, zero shape mismatches), and a re-export of the same 11-flag command with
`--use_sdpa_composite_for_prefill=True` (litert-torch main `731ef0a`) raises prefill at 31,744 tokens from 1,407 to 2,043 tok/s on
Qwen3-0.6B (+45 %) and from 478 to 644 on Qwen3-4B (+35 %), with zero shape mismatches, correct output, and decode unchanged
(within 1 %). At 1,024 tokens the prefill gain is +19 % / +7 %. The same new exports on the 09-17 dylib (one LiteRT commit before the
kernel) produce garbage text with no shape mismatch and no error — consistent with the GQA query-packing mismatch Fengwu described, though the mechanism is not
established from this side — so the new files need the new prebuilt, and that failure is the closest thing to a positive control that
the new kernel is what runs the prefill composite.
Provenance (host, binary, the three dylibs, ancestry of the pin, exporter commits, models, flags): `PROVENANCE.md`. The decision rule
written before the run: `PREREG.md`. Every command with load and other-process samples: `logs/runlog.txt`; per leg: `logs/driver.log`.

## Numbers — same binary, Mac Studio M4 Max, `--num_iterations=3`, `--disable_cache=true`, one process at a time

Pooled median of the 6 iterations of two processes per cell (per-process medians in parentheses); prefill tok/s = `Prefill Speed`,
decode tok/s = `Decode Speed` (256 tokens after the prefill), TTFT = `Time to first token`. Dylibs: 1dadd00c = `49df4fd5…` (today's),
4453b286 = `dcd3c3ef…` (09-17, the same-session control). "12 flags" = the published 11-flag command + `--use_sdpa_composite_for_prefill=True`
(litert-torch `731ef0a`); "11 flags" = the files published 2026-09-11 (litert-torch `6d4c622`); "11 flags @1e2d37f" = the published
command re-exported from litert-torch `1e2d37f` (the flag-only control: the same exporter drift as the 12-flag files, no prefill
composite); "9 flags" = the published files without the two composites. Raw: `logs/SUMMARY_benchmarks.txt` (per iteration),
`logs/pooled.txt` (this table), per leg `logs/*_b1k.log`, `logs/*_b31k.log`.

| bundle | dylib | 31,744 / 256 (`--max_num_tokens=32768`): prefill · decode · TTFT | 1,024 / 256 (`1280`): prefill · decode |
|---|---|---:|---:|
| Qwen3-0.6B, 12 flags (`29ae7cf1…`) | 1dadd00c | **2,043** (2,043 / 2,044) · 69.8 (69.7 / 69.9) · 15.6 s | **11,708** (11,704 / 11,736) · 348.3 (350.8 / 346.2) |
| Qwen3-0.6B, 11 flags (`bd685768…`) | 1dadd00c | 1,407 (1,408 / 1,407) · 70.5 (70.4 / 70.6) · 22.6 s | 9,863 (9,928 / 9,798) · 350.8 (351.2 / 349.6) |
| Qwen3-0.6B, 11 flags | 4453b286 | 1,409 (1,407 / 1,409) · 70.3 (69.9 / 70.8) · 22.6 s | 9,902 (9,866 / 9,938) · 352.1 (349.4 / 352.7) |
| Qwen3-0.6B, 11 flags @1e2d37f (`6f775622…`) | 1dadd00c | 1,411 (1,411 / 1,412) · 69.5 (69.1 / 69.9) · 22.5 s | 9,918 (9,916 / 9,919) · 350.3 (350.1 / 350.5) |
| Qwen3-0.6B, 9 flags (`eaa73f7e…`) | 1dadd00c | 1,400 (1,400 / 1,401) · 71.5 (71.4 / 71.5) · 22.7 s | 9,602 (9,603 / 9,601) · 264.5 (264.4 / 264.5) |
| Qwen3-0.6B, 9 flags | 4453b286 | 1,399 (1,400 / 1,397) · 71.3 (71.4 / 70.6) · 22.7 s | 9,618 (9,619 / 9,617) · 262.6 (263.0 / 261.4) |
| Qwen3-4B, 12 flags (`d406b866…`) | 1dadd00c | **644** (644 / 644) · 48.2 (48.2 / 47.8) · 49.3 s | **1,802** (1,800 / 1,806) · 132.8 (132.6 / 133.4) |
| Qwen3-4B, 11 flags (`6edb8266…`) | 1dadd00c | 478 (480 / 477) · 47.9 (48.1 / 47.6) · 66.5 s | 1,683 (1,683 / 1,684) · 132.9 (132.8 / 133.7) |
| Qwen3-4B, 11 flags | 4453b286 | 479 (479 / 473) · 48.0 (48.0 / 46.9) · 66.3 s | 1,686 (1,686 / 1,686) · 133.6 (133.5 / 133.9) |
| Qwen3-4B, 11 flags @1e2d37f (`afbe011b…`) | 1dadd00c | 478 (479 / 474) · 47.9 (48.1 / 47.5) · 66.5 s | 1,686 (1,686 / 1,686) · 133.4 (132.5 / 133.6) |
| Qwen3-4B, 9 flags (`c65779e9…`) | 1dadd00c | 477 (479 / 473) · 44.6 (45.2 / 43.8) · 66.6 s | 1,670 (1,670 / 1,671) · 112.2 (112.0 / 112.7) |
| Qwen3-4B, 9 flags | 4453b286 | 475 (480 / 464) · 44.0 (45.2 / 42.9) · 66.9 s | 1,670 (1,668 / 1,672) · 112.5 (112.2 / 112.7) |
| Qwen3-0.6B, 12 flags — **wrong output, void** | 4453b286 | 1,880 · 67.3 · 16.9 s (one process) | — |
| Qwen3-4B, 12 flags — **wrong output, void** | 4453b286 | 604 · 46.9 · 52.4 s (one process) | — |

Reading, against the rule pre-registered in `PREREG.md`:
- (a) **The prefill gain is real and non-overlapping.** At 31,744 the 12-flag arm's two processes read 2,043 / 2,044 (0.6B) and 644 / 644
  (4B) against 1,408 / 1,407 and 480 / 477 for the published files on the same dylib: +45.2 % and +34.8 % on pooled medians, no overlap
  between any A/B process of the arm and the control. At 1,024: 11,708 vs 9,863 (+18.7 %) and 1,802 vs 1,683 (+7.0 %), also non-overlapping.
  Against the flag-only control (11 flags @1e2d37f, same exporter drift) the numbers are the same: +44.8 % / +34.8 % / +18.0 % / +6.9 %.
- (b) **Decode does not move** with the prefill composite: −1.0 % / +0.7 % at 31,744, −0.7 % / −0.1 % at 1,024 (the decode graph of the 12-flag
  file is op-for-op identical to the 1e2d37f control; the composites' decode gain over the 9-flag files is the 09-17 result again: 351 vs 264,
  133 vs 112 at 1,024).
- (c) **The dylib swap changes nothing for the published files**: 11-flag 1dadd00c vs 4453b286 within 0.4 % in every prefill cell and 1.3 %
  in decode; 9-flag within 0.3 % / 1.4 %. The exporter drift alone (11 flags @1e2d37f vs the published 11-flag file, both on 1dadd00c)
  is within 0.6 % (prefill) and 1.5 % (decode).
- (d) TTFT at 31,744 drops 22.6 → 15.6 s (0.6B) and 66.5 → 49.3 s (4B) — prefill time only; the decode of 256 tokens is unchanged.
- Host: idle at the start (the other session's 8-round matrix and the leaderboard session's benchmark_model had ended; both sessions
  held further launches until this run's "done"). From 10:2x the leaderboard session ran a DDP upload driver (python, network; agreed
  as non-compute) during the B round: the B-round legs of the 4B published/control files read 1–3 % below their A-round in prefill
  (ctl_4b_11 472.7 vs 479.2; ctl_4b_9 463.8 vs 479.8) and up to 5 % in decode (ctl_4b_9 42.9 vs 45.2), while the 12-flag arm's B process
  equals its A (643.9 / 643.9). `logs/runlog.txt` samples 1-min load, GPU utilization and any process above 20 % CPU before every leg:
  `other=[none]` on every leg. The arm-vs-control deltas are 10–30× that spread.
- Fengwu's own numbers ("+40–50 %" for the fused prefill at long context; the 09-17 note's M4 Pro references 0.6B 1,061 / 4B 329 at 31,744)
  are a different chip (273 GB/s vs 546); the rows above are this Mac's numbers, not a comparison with his.

## Correctness on the new dylib

- Text runs (`logs/new_*_run.log`, the 996-token passage + `/no_think`): all eight bundles exit 0, `Shape mismatch` 0, `Validation error` 0,
  `name=GPU Metal`, `Created a Metal device`, `cache_dir: :nocache`; every answer names four industries and the 1879 railway
  (`logs/*_answer.txt`; the 12-flag answers differ in wording from the 11-flag ones — a different prefill graph, not a byte-identical one).
- 8-question gate on Metal (`scripts/gate8q_adv.py`, one process per question, `/no_think`; `logs/gate8q_new_*.json`): **Qwen3-4B 12 flags
  8/8, Qwen3-4B 11 flags 8/8, Qwen3-0.6B 11 flags 7/8** (rhyme → "violets.", as on 09-17), **Qwen3-0.6B 12 flags 6/8**: the same rhyme
  miss ("violets") plus "What is the capital of Japan?" answered "东京." — Tokyo in Chinese script, which the regex (`tokyo`) counts as a
  miss. The flag-only control (11 flags @1e2d37f, no prefill composite) on Metal: 7/8 — the rhyme miss only, capital → "The capital of Japan is
  Tokyo." (`logs/gate8q_new_06b_11n.json`). The 12-flag file on the CPU path (`--backend=cpu`, XNNPACK, the composites decomposed;
  `scripts/gate8q_adv_backend.py`, `logs/gate8q_cpu_06b_12.json`): 7/8 — capital → "The capital of Japan is Hachioji.", rhyme → "violets
  are blue." (27–85 s per question: the decomposed composites). On 09-17 the published 11-flag 0.6B file missed the same capital prompt on
  the CPU path ("Hachioji.") and passed it on Metal; the rhyme prompt wanders on both 0.6B files on every path. So the capital prompt is a marginal greedy pick of
  this 0.6B int4 file on every path (Hachioji on CPU for both graphs, Tokyo / 东京 on Metal), and the one token that moves with the
  prefill composite on Metal (Tokyo → 东京, the same city in Chinese script) cannot be separated from that margin by a one-process greedy run
  — the fused prefill kernel's numerics (fp16 activations on the GPU path) are the only thing that differs between the two Metal rows.
  It is reported as 6/8 vs 7/8, not hidden behind the regex. No run logs a mismatch or an error. Per `PREREG.md` §3 the 6/8 vs 7/8 is stated in
  the reply as such, with what the control runs showed.
- **The 12-flag exports on the 09-17 dylib** (`4453b286`, LiteRT `1901301f` = one commit before `89116780`; `logs/ctl_*_12_run.log`,
  `logs/ctl_*_12_answer.txt`): exit 0, 0 shape mismatches, 0 errors, and garbage text — 0.6B "ittめめるمق�most中文中文中文…", 4B "ations to
  9000000000…" — where the same files answer the passage on `1dadd00c`. This is consistent with the GQA query-packing mismatch Fengwu named as the reason the 09-17 prebuilt stopped one commit short of
  the fused kernel (an exporter with the packing skip meeting a dylib without the fused prefill kernel — that dylib's `strings` carry no
  prefill SDPA kernel name at all), but the mechanism is not established from this side: the failure is silent and nothing in the log names
  a kernel. It is the operational fact that matters — the new files need the new prebuilt — and the closest thing to positive evidence
  that the new dylib's prefill kernel is what runs the prefill composite: the runtime log names no kernel at any verbosity (`logs/new_06b_12_runv.log` with
  `--min_log_severity=0`, `logs/new_06b_12_runp.log` with `--enable_profiling=true` — neither adds a line naming an op or a kernel; the
  `strings` of the dylib add exactly one name over the 09-17 dylib, `flash_prefill_sdpa` (with the class name `FusedFlashAttentionPrefillOp`), `logs/strings_*.txt`). The one-process 31,744 numbers
  of the wrong-output runs (0.6B 1,880 tok/s, 4B 604) are void and recorded only to show the failure is silent.

## The export: what the flag changes in the graph, and what the exporter drift adds

`--use_sdpa_composite_for_prefill=True` (litert-torch `9f8a33f`, Fengwu Yao, 2026-08-31) is read from `extra_kwargs` in the prefill
exportable module and turns on `use_sdpa_composite` for the prefill signature; the fused-prefill kernel needs the query heads un-packed,
which `75370b9` (2026-09-15, "Skip query head packing when using SDPA composite.") does. Neither commit is in `6d4c622` (2026-09-08), the
exporter behind the published files, so the published files were re-exported from `main` at `731ef0a` (2026-09-17) with the lane's pinned
deps (`PROVENANCE.md`). Op inventories (`logs/ops_*.txt`, `scripts/inventory_gate.py`; three pairs per model, all PASS before any leg ran):

| signature | published 11 flags (`6d4c622`) | 11 flags @`1e2d37f` (control) | 12 flags (`731ef0a`) |
|---|---|---|---|
| prefill_1024 (0.6B / 4B) | 574 / 734 ops; sdpa_transposed 0; runtime_bmm 56 / 72; SOFTMAX 28 / 36; SELECT_V2 28 / 36 | 580 / 740 ops (+1 SUB, +4 SLICE, +1 CONCATENATION); composites as published | 436 / 556 ops; **sdpa_transposed 28 / 36** (13-op impl); runtime_bmm 0; SOFTMAX 0; SELECT_V2 0 |
| decode | 372 / 476 ops; sdpa_transposed 28 / 36 | 378 / 482 (+1 SUB, +4 SLICE, +1 CONCATENATION) | 378 / 482 — op-for-op identical to the control |
| FULLY_CONNECTED weights | INT4 blockwise-32, 5 shapes | identical | identical |
| rms_norm / cache_update / qkv_norm_rope / swiglu | 57 / 28 / 28 / 28 (0.6B), 73 / 36 / 36 / 36 (4B) | identical | identical |

The extra SUB / SLICE / CONCATENATION come from litert-torch `3773402` (2026-09-15, "Internal changes only": the param_tensor
update-length is computed in-graph) — exporter drift shared by the 12-flag files and the control, absent from the published files, and
worth nothing in speed (row (c) above). Two side facts for the record, not for the reply: at `731ef0a` the prefill module also honors
plain `--use_sdpa_composite` (the 2026-09-17 commit "Fix cache update in sliding window ring buffer attention"), so the 11-flag command
alone now emits the prefill composite at head — the explicit flag Fengwu named is what this run passes; and the PyPI nightly
`litert-torch-nightly 0.10.0.dev20260917` (files match `main` at `1e2d37f`) carries the flag and `75370b9`, so the export is
pip-installable without a source checkout (not used here).

## What would change the picture

The published bundles in `mlboydaisuke/Qwen3-{0.6B,4B}-LiteRT-gpu-composites` are the 11-flag files; the 12-flag files exist only in
this run's `models/` (sha256 in `sha256.txt`) and need a prebuilt at or after LiteRT-LM `1dadd00c` — on the v0.17.0 or 09-17 dylibs
they produce garbage silently. Whether to publish them (and how the card states the runtime requirement) is a separate decision.
Phones (Adreno / Mali) are not measured here.
