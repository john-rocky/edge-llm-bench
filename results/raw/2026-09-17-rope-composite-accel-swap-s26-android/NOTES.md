# Which change between LiteRT-LM v0.16.0 and v0.17.0 fixed the `odml.rope` off-prompt answer on the Android GPU path? — Galaxy S26, 2026-09-17 05:05–05:37 JST

Follow-up to `results/raw/2026-09-14-rope-composite-0170-s26-android/` (the published `litert-community/Qwen3-1.7B`
GPU build, `Qwen3-1.7B_dynamic_wi4b32_afp32.litertlm` sha256 `2eeffef7…`, `odml.rope` ×55, answers off the prompt on
the v0.16.0 Android GPU path and on-topic on 0.17.0). Same phone (SM-S942Q, Android 16, SM8850), same file, same
prompt ("Explain what on-device AI means in simple terms."), same harness (`run_cell.py … --runs 1`), one engine
process at a time under the owned device hold, thermal-gated, engine-default sampling, thinking as the bundle
declares it, GPU backend only. One run per cell — a correctness sitting: the two answers are a fixed pair of texts
(the "explain" definition vs an on-device-AI explanation) that repeated identically across every probe here and on
2026-09-13/14, so one run decides a cell.

**Verdict: the first LiteRT-LM commit that answers on topic is `96b4819c3a5e275f689951e93d376e65ca5c69e1`
(2026-08-07, "Update dependencies of litert_lm"); its parent `fa814c1b` still answers off the prompt.** That commit
changes no LiteRT-LM source: it moves the LiteRT that LiteRT-LM builds against from `0ff28117` to `b0f6c120` (51
LiteRT commits, linear on LiteRT main — GitHub compare), bumps `TENSORFLOW_REF` and pins `rules_ml_toolchain` back
to an older version, and replaces every prebuilt under `prebuilt/` (android_arm64: `libLiteRtGpuAccelerator.so`
`1287e5ae…` → `9d7ae75e…`, plus the OpenCL/WebGPU accelerators, the two TopK samplers and dawn). **The two halves
cannot be separated from outside**: a runtime built at one LiteRT with the accelerator `.so` of the other does not
load the accelerator in either direction (the split cells below, and the v0.16.0/v0.17.0 mixes in phase 1), and the
accelerator's source (ML Drift) is not in the OSS tree (litertlm-convert `qwen3_gpuopt_work/FINDINGS.md` §15). The
other two changes in the commit are excluded: the parent built with only `TENSORFLOW_REF` and `rules_ml_toolchain`
changed (LiteRT and the `.so` set left old) still answers off the prompt ("Exclusion" below). So the outside answer
is: one of LiteRT `0ff28117..b0f6c120`, or the accelerator build that shipped with it.

Not measured: the Pixel 8a (Mali) — not on the adb bus today; the flag bisect of 2026-09-14 was on that phone, so
the Mali side of the same question is open. Only the published wi4b32 GPU build was probed (the 09-14 sitting showed
the same verdicts for the int8 export and the 0.6B build on the two release engines).

## What the v0.16.0 → v0.17.0 change is made of (read from the LiteRT-LM repo)

- LiteRT-LM source: 153 commits `v0.16.0..v0.17.0` (linear, no merges). The v0.16.0 tag (`924e79c9`) sits on a
  release branch: 3 commits (README, Swift package, a Linux-ARM64 bazelrc flag) over the main-line merge base
  `8cd9c91e` (2026-08-06); same `prebuilt/` set and same `LITERT_REF`. The tested 0.17.0 binary was built at
  `945edf3` (2026-08-29; the `--branch v0.17.0` clone of 2026-09-09) — the tag now points at `e9fd8c53`
  (2026-09-09, "Update LiteRT-LM Swift package to v0.17.0", one commit on top). Main line merge base → `945edf3`
  = 152 commits.
- The LiteRT it builds against (`WORKSPACE` `LITERT_REF`): `0ff28117` (08-03) → `b0f6c120` (08-07, at `96b4819c`) →
  `174302bb` (08-25, at `3dc788a4`) → `9fe5be45` (08-27, at `a2491105`). Linear on LiteRT main (GitHub compare:
  305 commits `0ff28117...9fe5be45`, behind 0; 51 for `0ff28117...b0f6c120`).
- The GPU accelerator: `prebuilt/android_arm64/libLiteRtGpuAccelerator.so` and six siblings (Git LFS), loaded at run
  time (`gpu_registry.cc: Dynamically loaded GPU accelerator(libLiteRtGpuAccelerator.so) registered`). The pointers
  moved at the same three "Update dependencies of litert_lm" commits — four accelerator versions across the range
  (GpuAccelerator sha256 `1287e5ae…` / `9d7ae75e…` / `60c45f6c…` / `da48520a…`). ML Drift's source is not in the OSS
  tree (the `@ml_drift` `http_archive` in LiteRT's `WORKSPACE` has no url; OSS LiteRT consumes the accelerator as a
  prebuilt), so the accelerator half cannot be bisected below those binaries from outside.
- LiteRT commits `0ff28117...b0f6c120` whose subject touches the GPU side (no subject mentions rope): "Add ABI
  headers to LiteRT accelerator and dispatch structs" (`5c752aef`), "ml_drift: Hash backend ID and configuration
  options in cache fingerprint" (`089a9497`), "New SDPA composite op implemented with compositing with existing
  ops" (`0093228d`), "Support float32 precision for new SDPA composite op" (`60e524d1`), "Make LiteRT Accelerator
  APIs const-correct" (`6be2d72a`), "Add gpu_module_plugin_test…" (`3cc77c1f`). Listed for the bug report, not as a
  diagnosis — the accelerator binary's own changes are not visible from outside.

## Phase 1 — does the accelerator .so set swap independently of the CLI? No.

`diag/run_swap.py phase1` (driver log `diag/driver_phase1.log`, 05:05–05:07 JST). CLI = `android/bin/<tag>/litert_lm_main`
(sha256 as in `android/engine-pins.json`); ".so set" = the 7 files of `prebuilt/android_arm64/` at that tag; every
push sha256-verified on the device; each cell under a fresh `litert-local/…` id (no shared caches).

| cell | CLI | .so set | accelerator | answer |
|---|---|---|---|---|
| ctrl16 | v0.16.0 (`37d6b9d6…`) | v0.16.0 (Gpu `1287e5ae…`) | registered, 994/994 + 994/994 + 936/936 nodes on `LITERT_CL` | **off the prompt** — `</think>` then "The word "explain" means to provide a clear and logical description of something…" (the 09-13/14 text) |
| cli16-so17 | v0.16.0 | v0.17.0 (Gpu `da48520a…`) | **not loaded** (all five accelerator names tried, "GPU accelerator could not be loaded and registered"; `CpuAccelerator` registered instead) | no run — `llm_litert_compiled_model_executor_factory.cc:200` error at engine creation, exit 134 |
| cli17-so16 | v0.17.0 (`9a3f5abd…`) | v0.16.0 | **not loaded** (same) | no run — same error site, exit 134 |
| ctrl17 | v0.17.0 | v0.17.0 | registered, 994/994 + 994/994 + 936/936 on `LITERT_CL` | **on-topic** — "On-device AI is like having a smart computer that can think and make decisions right on your phone…" |

So a CLI and an accelerator from different versions are not a probe: the accelerator does not register and the GPU
backend never runs. Every bisect probe below is a self-consistent build — `litert_lm_main` built from the LiteRT-LM
source at commit X, run with the 7 prebuilt `.so` of the same commit X (Git LFS).

## Bisect — self-consistent builds on the main line (merge base `8cd9c91e` → `945edf3`)

Build: the `~/.cache/apple-silicon-llm-bench/litert-lm-v0.17.0` clone (history deepened, restored to `945edf3`
afterwards), `git bisect start --term-old=broken --term-new=fixed; git bisect fixed 945edf3; git bisect broken
8cd9c91e`, then `git bisect run` with the judge in `diag/bisect_run.log` (per step: `git lfs pull -I
"prebuilt/android_arm64/*"`, `bazelisk build --config=android_arm64 --enable_platform_specific_config --jobs=8
--local_cpu_resources=8 //runtime/engine:litert_lm_main` — NDK 29.0.13113456, bazel 7.6.1, `--jobs=8` because
another session was measuring on this Mac's GPU at the same time; then `diag/run_swap.py cell-dir` = binary + its 7
`.so` pushed and sha256-verified, one GPU short-chat run). The judge marks *fixed* only on an "on-device AI" answer
with the accelerator registered and all three "Replacing N out of N node(s)" lines, *broken* only on the "explain"
definition with the same GPU lines, anything else *skip*. The first pass masked one build failure (`cd3ef227`,
08-19: a stale-header error after the LiteRT ref changed; the step shipped the previous binary with the new `.so`,
which the judge caught as *skip* because the accelerator did not load) — the step script was fixed to fail loudly
and retry after `bazel clean`, and the bisect was restarted with the two verdicts already established. Logs:
`diag/bisect_run.log` (one line per probe), `diag/bisect_git.log` (`git bisect log`), `diag/driver_bisect_*.log` +
one `…-b-<sha>_…_run1.{json,log}` per probe (`engineVersion` reads "unknown … sha unmatched" for these unpinned
builds; the binary and `.so` sha256 are in the driver log).

| order | commit (date, subject) | LITERT_REF | GpuAccelerator | GPU registered / nodes | answer | verdict |
|---|---|---|---|---|---|---|
| 1 | `8cd9c91e` (08-06, merge base of v0.16.0) | `0ff28117` | `1287e5ae…` (= v0.16.0) | yes / 994+994+936 | "The word "explain" means…" | broken — my build reproduces the pinned v0.16.0 binary |
| 2 | `abedc5e3` (08-13, "Consolidate key and value cache buffers…") | `b0f6c120` | `9d7ae75e…` | yes / 994+994+936 | "On-device AI means that the smart things you use…" | fixed |
| 3 | `672cd6ca` (08-10, docs) | `b0f6c120` | `9d7ae75e…` | yes | on-device AI | fixed |
| 4 | `172ab84d` (08-07, "Allow creating EmbeddingLookup…", 3 after the bump) | `b0f6c120` | `9d7ae75e…` | yes | on-device AI | fixed |
| 5 | `0407a450` (08-07, "Refactor TtsEngine…", 3 before the bump) | `0ff28117` | `1287e5ae…` | yes | "The word "explain"…" | broken |
| 6 | `96b4819c` (08-07, "Update dependencies of litert_lm") | `b0f6c120` | `9d7ae75e…` | yes | on-device AI | fixed |
| 7 | `fa814c1b` (08-07, "Introduce two-phase CMake build orchestration", the parent; binary byte-identical to step 5's) | `0ff28117` | `1287e5ae…` | yes | "The word "explain"…" | broken |

`git bisect`: `96b4819c3a5e275f689951e93d376e65ca5c69e1 is the first fixed commit`. Its diff against the parent:
`WORKSPACE` (`LITERT_REF` `0ff28117` → `b0f6c120` with its sha256, `TENSORFLOW_REF` `9e1afa4e` → `9445166b`,
`rules_ml_toolchain` pinned back to `2eddbc59`) and 36 LFS pointers under `prebuilt/` — no other file.

## Split — is it the LiteRT source or the accelerator binary? Not separable from outside.

Two cells with the builds from steps 6 and 7 (no new build), `diag/run_swap.py cell-mix`, `diag/driver_split.log`:

| cell | binary (LiteRT-LM source) | .so set | result |
|---|---|---|---|
| mixA | `96b4819c` build (`fbe7cdcb…`, LiteRT `b0f6c120`) | the parent's (Gpu `1287e5ae…`) | accelerator **not loaded** (all five names tried), `CpuAccelerator` registered, engine creation error, exit 134 |
| mixB | `fa814c1b` build (`aff4b726…`, LiteRT `0ff28117`) | the bump's (Gpu `9d7ae75e…`) | same: not loaded, exit 134 |

A 51-commit LiteRT gap is already enough for the accelerator to refuse the runtime, in both directions. Which of the
two carries the change is therefore a question for a build of the accelerator, i.e. inside.

## Exclusion — the TensorFlow ref and the toolchain pin alone: not the fix.

One more build from the parent `fa814c1b` with its `WORKSPACE` carrying only the other two changes of the bump
commit — `TENSORFLOW_REF` `9e1afa4e` → `9445166b` (with its sha256) and `rules_ml_toolchain` pinned back to
`2eddbc59` — while `LITERT_REF` stays `0ff28117` and the `.so` set stays the old one (`1287e5ae…`). `git diff
fa814c1b -- WORKSPACE` showed exactly those lines (plus the `# UPDATED` comment). Build 186 s, 2,795 actions (the
TensorFlow change rebuilds most of the tree), binary `791713d7…` (differs from the plain parent build `aff4b726…`).
`diag/driver_T3.log`, 08:48 JST, cell `T3-tfref-toolchain-only`:

| binary | .so set | GPU registered / nodes | answer |
|---|---|---|---|
| `fa814c1b` + TF ref + toolchain of the bump (`791713d7…`, LiteRT `0ff28117`) | old (`1287e5ae…`) | yes / 994+994+936 | "The word "explain" means…" — still off the prompt |

So the two non-LiteRT dependency changes do not carry the fix; what remains is the LiteRT range `0ff28117..b0f6c120`
and the accelerator binaries replaced in the same commit — which the split above shows cannot be separated from
outside. The complementary build (the bump with the TensorFlow ref and toolchain reverted) was not needed for that
conclusion and was not run.

## Device state at close

v0.16.0 engine restored after every cell and at close (binary + 7 `.so`, every sha256 matches
`android/engine-pins.json`; `37d6b9d6…` / `1287e5ae…` on the device at 05:37 and again at 08:48 after the exclusion
cell); every `…-<label>` copy, cache and marker removed; hold released. The warm clone is back at `945edf3` with a
clean tree; the per-commit builds live only in the session scratchpad (sha256 in the driver logs).
