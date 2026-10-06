# 2026-10-07 — LiteRT-LM on DDP Galaxy S25 Ultra (pa3q-35), five models, cpu and gpu, CLI defaults (two cpu rows at max_num_tokens 2048)

## Purpose

LiteRT-LM numbers for the public litert-community bundles on a Developer Device Platform (DDP) Galaxy S25 Ultra
(device id `pa3q-35`), taken with LiteRT-LM's own benchmark binary at the defaults of `litert benchmark --ddp`.
Single runtime; nothing here compares runtimes. The numbers are in `table.md`.

## What ran

- Device: `pa3q-35`, product `SM-S938U1 (pa3q)`, Android 15. The id is a pool: the sessions landed on two firmware
  builds, `S938U1UEU1AYB3` (the cpu sessions except the Gemma 4 E2B re-run, and Qwen3-4B gpu) and `S938U1UEU2AYD9`
  (the other gpu sessions and the Gemma 4 E2B cpu re-run); each session's `provenance.txt` has its build.
- CLI: `litert-cli-nightly 0.3.0.dev20261006` in a fresh venv (Python 3.13). One line per session:
  `LITERT_GCP_PROJECT=<project> litert benchmark <bundle>.litertlm --ddp --device pa3q-35 --cpu|--gpu`.
- Binary: `gs://litert/binaries/latest/android_arm64/litert_lm/litert_lm_advanced_main`,
  sha256 `adac974bea147273b5bc64232d808905667eee69587161368146680df92e2d06` in every session's `provenance.txt`
  (the bucket object is dated 2026-09-18), with the shared libraries of that directory (sha256 in `provenance.txt`).
- Defaults, read back from each session: `--benchmark=true --benchmark_prefill_tokens=1024 --benchmark_decode_tokens=256
  --max_num_tokens=1280 --num_iterations=5 --report_peak_memory_footprint=true`; the log shows `number_of_threads: 4`
  on cpu and `GPU OpenCL` on gpu. The two Gemma 4 cpu rows ran with `--max-num-tokens 2048` instead
  (`--max_num_tokens=2048` in their `provenance.txt`), every other flag as above.
- Two processes per session (the CLI's run script): the first starts without cache files, runs one prefill and one
  decode and writes the caches beside the bundle (XNNPACK weight cache on cpu, ML Drift program and weight caches on
  gpu); the second, measured process runs the five iterations and writes `metrics.pb`.
- Bundles: the six files below, from the local Hugging Face cache; each equals the Hub's `lfs.sha256` on `main`
  (checked before the first session, `tools/hubsha.py`), and each session's `provenance.txt` has the sha256 of the
  file on the phone.

| repo | file | Hub revision | sha256 |
|---|---|---|---|
| litert-community/Qwen3-0.6B | qwen3_0_6b_mixed_int4.litertlm | a3c5d805 | 7900eb4e…22c1 |
| litert-community/Qwen3-1.7B | Qwen3_1.7B.litertlm | 73fbc3fe | 66064a4e…861c |
| litert-community/Qwen3-1.7B | Qwen3-1.7B_dynamic_wi4b32_afp32.litertlm | 73fbc3fe | 2eeffef7…918b |
| litert-community/Qwen3-4B | qwen3_4b_mixed_int4.litertlm | 84cc5a35 | f0794bc7…a18e |
| litert-community/gemma-4-E2B-it-litert-lm | gemma-4-E2B-it.litertlm | b3ca0d2f | 18193810…a63c |
| litert-community/gemma-4-E4B-it-litert-lm | gemma-4-E4B-it.litertlm | 2eee7ac3 | 0b2a8980…52e0 |

## Sessions

Twelve sessions on 2026-10-07 (JST), one at a time, in the order of `sessions.tsv` (finish time, label, backend, attempt,
session id, CLI session name, CLI exit code), plus one session of 2026-09-30 that is reused.

| cell | session | result |
|---|---|---|
| Qwen3-0.6B cpu | session-a7c5ae10 | row |
| Qwen3-0.6B gpu | session-10701be8 (2026-09-30, reused) | row |
| Qwen3-1.7B cpu (Qwen3_1.7B.litertlm) | session-75cdf64a | row |
| Qwen3-1.7B gpu (Qwen3-1.7B_dynamic_wi4b32_afp32.litertlm) | session-83804732 | no number: template error, job ERROR |
| Qwen3-1.7B gpu (Qwen3_1.7B.litertlm) | session-965ba2f4 | row (the cell's one retry, with the repo's other file) |
| Qwen3-4B cpu | session-fb63c76d | row |
| Qwen3-4B gpu | session-981d881c | row |
| Gemma 4 E2B cpu, max_num_tokens 1280 | session-aecaca6b | no number: job PASSED, no prefill or decode turn |
| Gemma 4 E2B cpu, max_num_tokens 2048 | session-52983393 | row |
| Gemma 4 E2B gpu | session-0d1cde8d | row |
| Gemma 4 E4B cpu, max_num_tokens 1280 | session-565fe3f9 | no number: job PASSED, no prefill or decode turn |
| Gemma 4 E4B cpu, max_num_tokens 2048 | session-e0cf5e62 | row |
| Gemma 4 E4B gpu | session-e06d4f0b | row |

Reuse of session-10701be8 (Qwen3-0.6B gpu, 2026-09-30, litert-cli-nightly 0.3.0.dev20260929): the `litert_cli`
package of 0.3.0.dev20260929 and 0.3.0.dev20261006 is byte-identical (`diff -rq` of the two wheels), and the binary,
library and bundle sha256 in its `provenance.txt` equal today's.

The 2026-09-30 cpu session of the same bundle (session-0f3c1363) is kept in `ddp-session/` and in
`collected/session-0f3c1363-not-in-table.jsonl` and is not the table's row: its iterations 2–5 spread 27 % in prefill
and 24 % in decode, so the cell was run again. Today's session spreads 52 % and 12 %. The two sessions' medians are
206.9 and 273.7 tok/s prefill, 6.90 and 8.12 tok/s decode; they are two sittings and are not pooled.

## What to read with the numbers

- Benchmark mode feeds a fixed count of tokens and decodes a fixed count; it prints no text, so none of these rows
  has a text check (`text-check-rule` cannot be applied). Every process log was searched for `Invalid decode` (none)
  and for error lines; the measured sessions have none beyond libEGL's `call to OpenGL ES API with no current
  context` on gpu.
- A job that DDP reports PASSED, with exit 0 in both processes and a `metrics.pb`, can hold no measurement: the two
  Gemma 4 cpu sessions did. `collect_lm.py` rejects them ("no LitertLmMetrics with a prefill turn").
- cpu rows move inside a session and between sessions: iterations 2–5 spread 3–52 % in prefill and 0.3–26 % in decode
  (Gemma 4 E4B is the tight one: 3 % and 0.3 %).
  gpu decode spreads 0.8–5 %. gpu prefill spreads 1–7 %, except Qwen3-4B (19 %, the last iteration) and Gemma 4 E2B
  (22 %).
- Gemma 4 E2B gpu steps down inside the session: the first process reports 3657.7 tok/s prefill and 44.62 tok/s
  decode, the measured process 3380 → 2418 → 1978 → 2015 → 2026 prefill and 30.7 → 26.6 → 26.3 → 26.4 → 26.3 decode.
  The table's median (2020.1 / 26.36) is the later level. The cause was not looked into.
- Qwen3-1.7B cpu prefill does the same (169.7 in the first process, then 150 → 105 → 118 → 105 → 105), and so do
  the Gemma 4 cpu rows (E2B 387.7, then 364 → 221 → 282 → 279 → 225; E4B 138.7, then 131 → 81 → 81 → 83 → 83).
- The two Gemma 4 cpu rows are at `max_num_tokens` 2048 and every other row at 1280. On cpu the allocated context
  length is part of the condition, so these two rows are not the same condition as the other cpu rows.
- `init ms` in the table is the measured process, which starts with the caches present. The first process's init
  (no caches) and its one prefill and decode are in the last block of `table.md`, read from the log.
- The phone's state is not controlled: no temperature, battery or thermal reading is taken, the lab picks the phone.

## Sessions without a number

- Qwen3-1.7B gpu, `Qwen3-1.7B_dynamic_wi4b32_afp32.litertlm`: the first process stops with `Failed to apply
  template: invalid operation: tried to use + operator on unsupported types string and sequence (in template:32)`.
  Line 32 of that bundle's chat template is `'<|im_start|>' + message.role + '\n' + message.content + …`; the other
  three Qwen3 bundles share one template whose line 32 adds a `content` variable instead (`tools/tmpl.py` reads the
  template out of each file). Not retried with the same file. The repo's other file, `Qwen3_1.7B.litertlm`, ran on
  gpu (session-965ba2f4).
- Gemma 4 E2B cpu and Gemma 4 E4B cpu at the default `--max_num_tokens=1280`: `dynamic_update_slice.cc:68
  SizeOfDimension(update, i) <= SizeOfDimension(operand, i) was not true. Node number 1164 (DYNAMIC_UPDATE_SLICE)
  failed to prepare.` (1830 for E4B), then `Failed to allocate tensors`, on subgraph `prefill_1024`, in the first
  process and in each of the five iterations. Not retried with the same flags.
  The same binary (sha256 adac974b…) on a Galaxy S26 over adb shows which token settings run (`s26-repro/`, one
  process and one iteration each, caches removed first): with 1024 prefill tokens, `max_num_tokens` 1280 and 1281
  fail the same way and 1536, 2048 and 4096 run; with `max_num_tokens` 1280, 512 and 128 prefill tokens run. E4B:
  1024 / 1280 fails, 1024 / 2048 runs. The two cells were then run on DDP with `--max-num-tokens 2048`
  (session-52983393, session-e0cf5e62), the value this repo's `native-benchmark-1024x256` task is run at
  (`matrices/dashboard-protocol1024-v1*.cells`, `context-tokens=2048`).
  Where between 1281 and 1536 the limit sits, and why, was not looked into.

## Files

- `ddp-session/<session>/<backend>-pa3q-35/`: `metrics.pb` (as pulled), `metrics.pb.txt` (`protoc --decode
  litert.lm.proto.LitertLmMetricsList`, protos at LiteRT-LM v0.17.0), `provenance.txt` (as pulled),
  `logcat-process.txt` (the logcat lines of the binary's two processes; the full logcat stays in
  `gs://<project bucket>/litert-cli/sessions/<session>/` and in `~/.cache/litert-cli/ddp/`).
- `collected/sessions.jsonl`: `collect_lm.py`'s rows, one per cell with a number (its `measurements-lm.jsonl`,
  renamed). `collected/first-process.jsonl`: `tools/gather.py`'s read of each first process.
  The rows sit one directory down on purpose: `scripts/build_summary.py` reads `results/raw/<campaign>/*.jsonl` as
  run records, and these are not run records.
- `table.md`: `tools/mktable.py` over the rows, plus the sessions without a number and the S26 setting test.
- `s26-repro/`: the Galaxy S26 setting test: `steps.log` (the script's step lines; battery lines of `dumpsys` that
  the script's temperature read pulled in are filtered out), `<bundle>-p<prefill>-n<max>.log` (each process's
  output without the per-node `Replacing … node(s)` and `XNNPack weight cache` lines), `helpfull.txt`.
- `run-log.txt`: every command with its output. `sessions.tsv`: the twelve sessions in order.
- `tools/`: the scripts as run (scratch paths left as they were; the user name is replaced by USER and the gcloud
  account by ACCOUNT in `run-log.txt`, `sessions.tsv` and `tools/`, no other byte changed).

## Not in results/summary

These sessions are not imported into `results/summary/device-runs.csv`: a row there is one run of a prompt task with
decoded text, and these are medians of a benchmark-mode loop without text.
