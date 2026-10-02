# Day-0 kit — allocated KV / NPU dynamic cache (LiteRT-LM main 5e3bd6377), v1

Prepared 2026-10-02 (v0.17.1 still the latest tag; 5e3bd6377 is 199 commits ahead of
it on `main`). Fires on the day a LiteRT-LM release carries
[5e3bd6377](https://github.com/google-ai-edge/LiteRT-LM/commit/5e3bd637758fb0ae2dcbd85fb028f1b609dbee3e)
"Grow the NPU dynamic KV cache on demand during prefill and decode" (2026-09-26).
Three parts: ① re-measure the long-context column on the new tag with its stored
sittings as the baseline, ② one NPU cell that decides whether the `cache_length` 896
recommendation (litert-torch PR #1226, LiteRT-LM #3508) still applies, ③ the follow-up
comments. Nothing here touches a phone before the day; the S26 and the iPhones are not
used in preparation.

## What the commit actually changes (read 2026-10-02, the premise the plan line got wrong)

| fact | where it is read |
|---|---|
| The diff touches 7 files, all in the NPU executor: `runtime/executor/llm_litert_npu_compiled_model_executor.{cc,h}`, `runtime/executor/npu/llm_litert_npu_{dynamism,kv_cache,mask}.*`. **No CPU or GPU executor file changes.** | `gh api repos/google-ai-edge/LiteRT-LM/commits/5e3bd6377` |
| Growth applies only when `NpuDynamismHelper::HasDynamicKVCache()` is true: a `kv_cache_k` / `kv_cache_v` / `kv_cache_c` signature input with a `-1` dimension. A static NPU bundle keeps its export-time cache length. | `runtime/executor/npu/llm_litert_npu_dynamism.cc` L48–72 |
| `HasDynamicKVCache()` is a stub returning `false` unless `LITERT_ENABLE_FABRIC_INTEGRATION` is defined. No BUILD file in the public tree defines it; LiteRT's `config_setting` for it is referenced only inside a google-only commented block (`litert/runtime/BUILD` L584–623). The `#if` branch itself needs only OSS LiteRT cc APIs (`CompiledModel::ResizeInputTensor` exists in `litert/cc/litert_compiled_model.h`). | `llm_litert_npu_dynamism.cc` L204–208; LiteRT `litert/runtime/BUILD` L39–42 |
| Defaults keep today's behaviour: initial size 0 = allocate the full `max_num_tokens` up front. `LITERT_LM_NPU_DYNAMIC_KV_CACHE_INITIAL_SIZE` and `LITERT_LM_NPU_DYNAMIC_KV_CACHE_GROWTH_STEP` (default 512) are environment variables, "for now" (TODO b/565760564). | the diff, `GetDynamicKvCacheInitialSize` |
| Over-max requests on the dynamic path are refused: `InvalidArgumentError("Required tokens (N) exceeds max_num_tokens (M).")`. | the diff, `GrowDynamicKVCache` |
| The public `npu_export` (litert-torch main 775c418, 2026-10-02) has no dynamic-KV option — the only dynamic-cache flag is `enable_gpu_dynamic_cache` (GPU). Its bundles fix `cache_length` in the graph shapes. | `litert_torch/generative/export_hf/{export.py,core/exportable_module_config.py}` |

Consequences for the three parts:

- **①** is not "the numbers go stale on day 0". The CPU (XNNPACK) and GPU allocated-KV cost
  in `results/raw/2026-09-18-dashboard-longctx-v1-m4max-mac` and the five S26 sittings
  is untouched by this commit. The re-measure is still worth one sitting per device on
  a new tag (the column is published in #2568 and any runtime change can move it), and
  the kit below makes it one command — but the honest expectation is "unchanged", and
  the day-0 trigger for the CPU/GPU column is any release, not this commit specifically.
- **②** needs three gates before a cell is worth running (a tag with the commit, a
  binary whose dynamism helper is compiled in, a bundle with a `-1` KV dimension).
  Today none of the three is met; the preflight script prints which.
- The `cache_length` 896 line of #1226 is a compile-time property of the exported
  graph (the prefill mask's ADD operand, `2 B × (H_q / H_kv) × P × (C + P)` > 1 MiB).
  Dynamic growth can only change that reading if the dynamic graph's mask operand
  follows the *current* capacity rather than `max_num_tokens` — which is exactly what
  the ② cell measures.

## ① Long-context column re-measure — one command per leg

```
scripts/longctx_day0.sh <leg> <tag> [--check-only] [--baseline <campaign-substr>]
  leg = mac | s26-gemmae2b | s26-qwen06 | s26-gemmae4b | s26-qwen17 | s26-qwen4 | s26-gpu-retake
```

What it does, in order: precondition check (the staged engine is the tag:
`ios/BenchmarkApp/scripts/bootstrap.sh` `LITERTLM_TAG` for the Mac, `android/bin/<tag>/` +
an `android/engine-pins.json` entry for the S26; no other driver or dashboard job on
the host; cells validate) → the capture with the stored sitting's exact protocol (Mac:
`ROUNDS=8 RUNS=2 BASE_COOLDOWN=10`; S26: `ROUNDS=8 COOLDOWN=30 THERMAL_WAIT=600
BENCH_CPU_MASK= BENCH_ANDROID_SERIAL=RFGL80R6A6H`, the cells files' own headers) into
`results/raw/<date>-dashboard-longctx-v1-<leg>-day0-<tag>/` → `regression_report.py`
(verdicts, anchor-normalized across sittings; exit 1 = REGRESSION) →
`longctx_ladder_diff.py` (the allocation ladder, baseline vs candidate, written next to
the records as `ladder-vs-<baseline>.{md,csv}`).

`--check-only` runs the preconditions and prints the capture line without touching a
device. Run on 2026-10-02: `mac v0.17.1` fails on the bootstrap tag (v0.16.0 staged),
`s26-gemmae2b v0.17.0` passes every check.

Two readers were fixed for this (both 2026-10-02):

- `scripts/build_summary.py` now reads the Android allocation
  (`conditions.contextTokens`, written by `android/bench/run_cell.py`) into
  `context_tokens`; before, every Android long-context row was blank there and the
  S26 ladder's three allocations pooled into one derived cell. 560 non-ladder rows
  also gain their real value (llama.cpp short-chat cells carry `context-tokens=4096`;
  two endurance rows 2048 / 4096; profile controls 1024) — one cell is split by it
  (`SM-S942Q litert-lm-gpu gemma-4-E2B short-chat`: 15 rows blank, 1 endurance row
  at 2048), which is the truth of those records.
- `scripts/regression_diff.py` joins cells on `context_tokens` as well (printed as
  `ctx2304`); anchors match on every other key component. Pre-existing keys are
  unchanged (empty component).

How to read the ladder table: the column's question is within-session — "does decode
at a fixed filled length fall with the allocated length?" — so compare each side's
**Δ vs smallest ctx**; the raw candidate/baseline tok/s is cross-session and
informational (16–25 % drift; CLAUDE.md). The verdict lines come from the regression
report. Aggregation is `render_leaderboard.arm_row` (the repo's one aggregation).

Stored baselines the script maps to (warm median unless noted; `NOTES.md` of each):

| leg | sitting | LiteRT-LM CPU decode 2304 → 4096 → 8192 | GPU | control (llama.cpp) |
|---|---|---|---|---|
| mac | 2026-09-18-…-m4max-mac (v0.16.0 Swift pkg) | Qwen3-0.6B wi4b32 45.1 / 34.0 / 18.1 (−60 %); E2B 50.6 / 46.6 / 39.2 (−22 %); E4B 33.4 / 31.3 / 26.5 (−21 %); Qwen3-1.7B INT8 28.5 / 28.6 / 28.7 (flat) | Metal: 0.6B −18 %, 1.7B −13 %, E2B −12 %, E4B −9 % at 8192 | flat ±3 % |
| s26-gemmae2b | 2026-09-20 sitting 1 (v0.16.0 advanced_main) | −11 % / −33 % | OpenCL decode flat (re-take 09-24), prefill −31 % | flat +1 % |
| s26-qwen06 | 2026-09-20 sitting 2 | 20.0 / 11.3 / 5.1 (−43 % / −74 %) | GPU excluded (garbage text at 2K prefill) | flat −1 % |
| s26-gemmae4b | 2026-09-21 sitting 3 | 14.5 → 13.0 at 4096 (−11 %); 8192 not run (RAM) | flat on cold; prefill −19 % | flat +1 % |
| s26-qwen17 | 2026-09-23/24 sitting 4 | 9.3 / 9.3 / 9.4 (flat, INT8 export) | — | flat +1.3 % |
| s26-qwen4 | 2026-09-24 sitting 5 | no LiteRT row (mixed_int4 = 2,048-entry KV, excluded) | — | 7.5 / 7.5 / 7.4 |
| s26-gpu-retake | 2026-09-24 | — | E2B 26.1 / 26.8 / 25.5, E4B 14.9 / 14.8 / 14.5 (±3 %) | — |

Before the Mac leg: bump `LITERTLM_TAG`, `bootstrap.sh`, `scripts/build_yardstick_mac.sh`
(wipe `.build/dd-mac` when the vendored tag changes), and stage the Mac CLI *without*
the WebGPU dylibs if the Metal arm is what is being compared (the 09-18 arm registered
`GPU WebGPU` — the accelerator line of the log is the arm's identity). Before an S26
leg: `LITERTLM_TAG=<tag> android/scripts/build_litert_lm_main.sh`, push per
`android/README.md`, add the observed sha256s to `android/engine-pins.json`; read
`logs/dashboard-job/ledger.tsv` and the sibling hold first — the night job owns the
device on its night.

## ② The one NPU cell, and the number that decides

Preflight (no device, no model):

```
scripts/npu_dynamic_kv_preflight.sh <tag> [android/bin/<tag>/litert_lm_advanced_main]
```

| gate | what it checks | 2026-10-02 result (v0.17.1, v0.17.0 binary) |
|---|---|---|
| 1 | 5e3bd6377 no longer ahead of the tag on `main` | FAIL (position 199 ahead) |
| 2 | the binary carries the literal `LITERT_LM_NPU_DYNAMIC_KV_CACHE_INITIAL_SIZE` | FAIL |
| 3 | the binary carries `ResizeInputTensor failed for` (only inside the `#if LITERT_ENABLE_FABRIC_INTEGRATION` branch of `llm_litert_npu_dynamism.cc`) — without it no bundle is ever dynamic | FAIL |
| 4 | a bundle whose `prefill_*`/`decode` signature has a `kv_cache_*` input with a `-1` dim (`inspect_bundle.py … \| grep -E 'kv_cache_[kvc].*-1'`) | none exists: `npu_export` cannot produce one; the published Qualcomm bundles are AOT with fixed caches |

Gate 3 is the one a release will not flip by itself: our Android binaries come from
`android/scripts/build_litert_lm_main.sh` (OSS bazel), where the define is off. On the
day, build the tag twice — as pinned, and once with
`--copt=-DLITERT_ENABLE_FABRIC_INTEGRATION` appended to the bazel line — and run the
preflight on the second binary. Whether the Qualcomm dispatch accepts the resized
signatures at JIT is not established anywhere public; the cell below is the first
time it would be tried here. If gate 4 stays unmet (no dynamic bundle from any
source), the answer to "is 896 still needed?" is **yes, by construction** — the growth
code never runs for a static graph — and no phone time is spent.

The cell (only when all four gates pass) — two arms on the same new prompt row, same
sitting, the `#3508` chunk-probe harness (`litertlm-convert/npu_g270_ship/3508_chunk_probe`):

```
# 1. a prompt row that forces growth across the line: rows a–i are ≤ 245 tokens (2 chunks) and
#    never leave an initial size of 512 — add row j to make_prompts.py: filler A + B + A again,
#    then the question, ≈ 560–620 Gemma-3 tokens = 5 chunks of 128 (20 questions as the other rows)
python3 make_prompts.py <gemma3 tokenizer dir> prompts    # regenerates a–i byte-identical, adds j_01..j_20
# 2. a wrapper so the harness's device loop runs the binary with the two variables set
#    (--extra is appended to the CLI line; environment is not forwarded)
cat > <stage>/bin/litert_lm_advanced_main_dyn <<'SH'
#!/system/bin/sh
export LITERT_LM_NPU_DYNAMIC_KV_CACHE_INITIAL_SIZE=512 LITERT_LM_NPU_DYNAMIC_KV_CACHE_GROWTH_STEP=512
exec "$(dirname "$0")/litert_lm_advanced_main" "$@"
SH
# 3. the two arms (S26, SM8850 / V81, QAIRT 2.47 libs as FINDINGS.md), 20 prompts each
P3508_STAGE=<stage> python3 run_probe.py run g270_dyn_i512_j <dynamic gemma-3-270m-it bundle> npu /data/local/tmp/litertlm_npu/jit \
  --bin ../litert_lm_advanced_main_dyn --rows j --maxtok 96 --extra "--max_num_tokens=2048"
P3508_STAGE=<stage> python3 run_probe.py run g270_c896_j     g270_c896_srq.litertlm             npu /data/local/tmp/litertlm_npu/jit \
  --bin ../litert_lm_advanced_main     --rows j --maxtok 96      # static control, the 09-08 bundle
```

Row j makes prefill grow 512 → 1024 during the request (`GrowDynamicKVCache` is called
once per `Prefill()` with `current_step_ + ids.size()`): at a capacity of 1024 the
static mask operand is 1.125 MiB (over the line); the same prompt on the static
`cache_length` 896 control is the day's reference. Required log evidence in every
dynamic run: one `Dynamic KV cache grown from 512 to 1024` line and `DispatchDelegate`
on `prefill_128` (the graph ran on the HTP, not XNNPACK); in the control, no growth line.

Decision, both arms scored by the 09-08 scorer (on-topic = the question survives
prefill; the 09-08 static pair on row b was 896 → 18/20, 1024 → 2/20):

| dynamic (row j) vs static-896 control (row j) | reading | consequence |
|---|---|---|
| dynamic ≥ control − 2 and control ≥ 15/20 | the grown graph at capacity 1024 does not hit the 1 MiB line | the 896 recommendation is scoped to **static exports** in #1226 and #3508; for dynamic bundles the line moves to "initial size, not `max_num_tokens`" |
| dynamic ≤ 2/20 and control ≥ 15/20 | the line is hit at the grown capacity exactly as for a static 1024 graph | 896 stands for every bundle; dynamic growth only lets a prompt ≤ initial size stay under the line |
| anything else | not decided (control itself failing = the row, not the line) | re-run with rows j + b and the thermal log; do not post |

Both outcomes are posted as one sentence in #1226 (draft C below) — the numbers above
are the only ones a reader needs. For a 16-query-head model (Qwen3-0.6B) the question
is moot either way: its mask operand is 2 copies, 0.56 MiB at 1024 (own #3508 comment,
2026-10-02), and its NPU garbage has a different cause (litert-torch#1290).

## ③ Follow-up comments (drafts, GO after the day's numbers)

Drafted by an Opus 5.5 subagent, checked here (litert-tone + litert-team §1.5/§2;
ledger `~/code/standup/state/opus-draft-ledger.md`):
`~/code/standup/drafts/2026-10-02-npu-dynamic-kv-day0/comments.{opus,post,facts}.md`
— A = LiteRT-LM #2568 (re-run table + the S26 CPU baseline, never posted there), B =
LiteRT-LM #3444 (re-verification of the three probes p9 / p7 / p5 against the two
clamp/error fixes 91a926c16 + dc911c3db, also unreleased today), C = litert-torch PR
#1226 (scope line, with the ② result or "not run"). All day-0 values are `[…]`
placeholders; the lint passed on the template with the facts table of 2026-10-02 and
must be re-run on the filled text (claims = the final sentences).

## Day-0 run order (one sitting; GO list at the end)

1. `gh release view <tag> --repo google-ai-edge/LiteRT-LM` → `scripts/npu_dynamic_kv_preflight.sh <tag>` (gate 1), and confirm 91a926c16 / dc911c3db are in the tag too (`gh api …/compare/<tag>...main`).
2. Builds: Android `android/scripts/build_litert_lm_main.sh` at the tag (pinned) + the `-DLITERT_ENABLE_FABRIC_INTEGRATION` variant; Mac bootstrap + yardstick. Preflight gates 2–3 on both Android binaries.
3. `scripts/longctx_day0.sh mac <tag>` (≈4 h, Mac idle). In parallel on the S26 only if the night job's ledger shows the device free: `scripts/longctx_day0.sh s26-gemmae2b <tag>` first (the sitting with both backends), the other S26 legs on following days.
4. #3444 probes p9 / p7 / p5 on the Mac GPU path (`results/raw/2026-09-18-dashboard-longctx-v1-m4max-mac/probe-evidence/`, same commands, new tag).
5. ② only if gate 4 is met (a dynamic bundle exists) — otherwise write "not run" in draft C.
6. Fill the three drafts, regenerate `comments.facts.md` from the final sentences, lint, GO.

GO is needed for: posting A / B / C; committing the day-0 campaign dirs + summary
(rebuilt from the git index); any pin bump (`environment.lock.json`,
`android/engine-pins.json`) — release-watch informs, a person decides.
