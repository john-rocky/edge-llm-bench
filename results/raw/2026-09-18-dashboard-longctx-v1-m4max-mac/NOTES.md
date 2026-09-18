# 2026-09-18 — Dashboard long-context column, Mac leg: LiteRT-LM cpu / gpu and llama.cpp at prefill ≈2K / decode 256, three KV allocations

One-line result: at a fixed filled length (≈1,990 Qwen3 / ≈1,640 Gemma-4 prompt tokens + 256 output) the LiteRT-LM decode on
this Mac falls with the **allocated** KV (`maxNumTokens`) on **both** backends — the Metal-backed GPU arm by 9–18 % and the
XNNPACK CPU arm by 21–60 % from 2,304 to 8,192 — on every dashboard bundle whose KV is allocated at run time; the one bundle
whose KV is fixed at export (Qwen3-1.7B dynamic INT8) is flat, and the llama.cpp control arm is flat on all five models
(±3 %). This is catalog row K5 (XNNPACK attention batch-matmul over the allocated KV, measured on gemma-3-270m CPU only)
extended to the dashboard's models and, new, to the GPU arm (X2's open cell "does GPU decode also track the allocated
length?" — on the Mac, yes).

## What was measured

- Cells: `matrices/dashboard-longctx-v1.cells` (39 runnable + 4 `exclude=` rows + the session anchor). Task
  `long-context-2048-gen256` (new, `BenchmarkTask.swift`): the forced-output long-context prompt at 27 filler blocks —
  1,986 Qwen3 / 1,637 Gemma-4 tokens as tokenized by the engines (`promptTokenCount`), 256-token output budget, greedy.
- Arms: `litert-lm` = the Metal-backed GPU delegate of the LiteRT-LM v0.16.0 Swift package (the accelerator registry
  prints `GPU WebGPU`), `litert-lm-cpu` = the same package's XNNPACK CPU backend (new `yardstick --litert-backend cpu`,
  stamped `runtime: litert-lm-cpu` as on Android), `llama.cpp` = the b8999 xcframework (Metal). Engine pins unchanged
  (`engineVersion` v0.16.0 / b8999 on every record).
- Allocation ladder per (arm, model): `context-tokens=` 2304 (= prompt + output, the minimal one, the ynnpack A/B's
  "P2048 / max_tokens 2304"), 4096 (the analogue of the LiteRT team's ctx-2048 column for p=1024/g=256), 8192. On LiteRT-LM
  it is `maxNumTokens` (KV pre-allocation); on llama.cpp `n_ctx` (KV allocated at n_ctx, attention over the filled length).
- Shape: `ROUNDS=8 RUNS=2 BASE_COOLDOWN=10` on the Mac runner's new round mode — every cell once per round, one process of
  2 runs per launch (run 1 cold, run 2 warm), order reversed on even rounds, 10 s between launches; 8 rounds 05:15–09:01.
  Numbers below are the warm run's median [min–max] over the 8 rounds; the cold run's ladder (`ladder-cold.md`) reads the
  same within 1 point on every LiteRT cell.
- Host: Mac Studio M4 Max 128 GB (Mac16,9), macOS 27.0 (26A5416b). Not idle: other agent sessions and a Chrome renderer;
  load 2.4–5.3 at round starts (`host_load.log`), every record thermal-nominal start to end. Admission: the MLX Qwen3-0.6B
  short-chat anchor ran once per round — warm median 527 tok/s over 16 runs [512–557], 0.985 of the 2026-09-14 reference
  (535) — admitted under the dashboard's 5 % rule. Because each allocation pair sits next to its partner in every round,
  the Δ columns are within-round comparisons; the absolute rates carry the usual 16–25 % cross-session drift.

## Decode at depth, warm, tok/s (median [min–max], n=8) — one ladder per arm; `ladder-warm.md` has prefill, TTFT and the cold regime

LiteRT-LM, GPU backend (`litert-lm`):

| model (file) | ctx 2304 | ctx 4096 | ctx 8192 | Δ 2304→4096 | Δ 2304→8192 |
|---|---|---|---|---:|---:|
| Qwen3-0.6B, dynamic wi4b32 (GPU build) | 290.4 [289.1–294.0] | 284.5 [283.3–288.8] | 238.0 [236.5–241.0] | −2.0 % | **−18.0 %** |
| Qwen3-1.7B, dynamic wi4b32 (GPU build) | 204.8 [203.8–206.7] | 202.2 [201.1–203.9] | 177.4 [176.3–178.9] | −1.2 % | **−13.4 %** |
| Gemma 4 E2B, wNa8o8 | 155.5 [154.4–156.9] ‡ | 155.0 [154.5–156.4] | 137.4 [136.7–138.9] ‡ | −0.4 % | **−11.6 %** |
| Gemma 4 E4B, wNa8o8 | 96.9 [86.4–97.9] | 96.7 [96.0–97.3] | 88.6 [88.0–89.0] | −0.3 % | **−8.6 %** |

LiteRT-LM, CPU backend (`litert-lm-cpu`, XNNPACK):

| model (file) | ctx 2304 | ctx 4096 | ctx 8192 | Δ 2304→4096 | Δ 2304→8192 |
|---|---|---|---|---:|---:|
| Qwen3-0.6B, dynamic wi4b32 (GPU build) | 45.1 [43.7–47.0] | 34.0 [33.1–35.3] | 18.1 [17.9–18.8] | **−24.6 %** | **−59.8 %** |
| Qwen3-1.7B, dynamic INT8 (`Qwen3_1.7B.litertlm`) | 28.5 [28.0–29.1] | 28.6 [28.3–29.0] | 28.7 [28.2–29.7] | +0.5 % | +1.0 % |
| Gemma 4 E2B, wNa8o8 | 50.6 [50.4–50.6] | 46.6 [46.4–48.0] | 39.2 [39.1–39.3] | **−7.9 %** | **−22.5 %** |
| Gemma 4 E4B, wNa8o8 | 33.4 [33.0–33.7] | 31.3 [31.0–31.3] | 26.5 [26.5–26.6] | **−6.4 %** | **−20.5 %** |

llama.cpp (Metal, b8999) — the control arm, KV allocated at `n_ctx`, attention over the filled length:

| model (file) | ctx 2304 | ctx 4096 | ctx 8192 | Δ 2304→4096 | Δ 2304→8192 |
|---|---|---|---|---:|---:|
| Qwen3-0.6B Q4_K_M | 297.9 [292.9–312.9] | 298.3 [292.8–305.1] | 307.7 [296.0–312.8] | +0.1 % | +3.3 % |
| Qwen3-1.7B Q4_K_M | 193.3 [188.8–198.0] | 194.4 [190.5–197.2] | 194.1 [191.2–197.6] | +0.6 % | +0.4 % |
| Qwen3-4B Q4_K_M | 103.2 [102.8–104.6] | 104.2 [102.2–105.1] | 103.4 [103.1–104.1] | +0.9 % | +0.2 % |
| Gemma 4 E2B Q4_K_M | 139.1 [135.9–141.5] | 138.9 [136.3–140.9] | 137.7 [135.3–141.2] | −0.1 % | −1.0 % |
| Gemma 4 E4B Q4_K_M | 86.3 [85.3–87.8] | 86.8 [86.0–88.1] | 87.2 [86.0–87.7] | +0.6 % | +1.1 % |

(Per-arm ladders on purpose: the public repo carries single-arm facts; the cross-arm standing is read locally.)

‡ Gemma 4 E2B on the GPU arm answers the forced-output prompt in 77 tokens at ctx 2304 and 93 at ctx 8192 (EOS, all
16 runs each), but fills the 256 budget at 4096 — greedy output differs with `maxNumTokens` on that path (numerics, not
sampling); its decode rate is the engine's counter over those tokens. On the CPU arm the same bundle produces 256 at every
allocation. Not investigated further here.

Prefill follows the same shape on LiteRT-LM (warm medians, tok/s, 2304 → 8192): GPU Qwen3-0.6B 7,697 → 4,924 (−36 %),
Qwen3-1.7B 3,712 → 2,921 (−21 %), E2B 6,714 → 5,515 (−18 %), E4B 2,053 → 1,810 (−12 %); CPU Qwen3-0.6B 527 → 262 (−50 %),
E2B 654 → 416 (−36 %), E4B 230 → 178 (−23 %), Qwen3-1.7B INT8 575 → 574 (flat); llama.cpp within ±2 % on all five.

## Reading

1. **The allocated-KV cost is not CPU-only.** K5 was measured on the XNNPACK CPU path (gemma-3-270m, four devices) and K17 on
   the S26 found the Android GPU flat at 384–32,771 tokens. On this Mac the Metal-backed GPU delegate of the v0.16.0 Swift
   package loses 9–18 % of decode and 12–36 % of prefill from 2,304 to 8,192 allocated tokens at the same filled length — on
   all four bundles that allocate at run time. Smaller than the CPU's 21–60 %, and invisible at 4,096 (≤ 2 %) where the CPU
   already pays 6–25 %.
2. **Which bundles pay is an export property, not a model property.** Qwen3-1.7B dynamic INT8 (the litert-community file
   of 2026-06-25) is flat on CPU in rate and in resident memory (peak RSS 2,903 → 2,910 MB across the ladder), while the
   wi4b32 GPU-build files and both Gemma 4 bundles grow with the allocation (0.6B wi4b32 CPU 2,050 → 5,346 MB; E4B CPU
   4,300 → 11,303 MB): the INT8 bundle's KV is sized at export and `maxNumTokens` does not resize it. Whether its decode
   beyond that size is valid is not established here (see the exclusions below for what that failure looks like); the
   session records only that the rate does not move.
3. **llama.cpp is the control**: KV is allocated at `n_ctx` but attention runs over the filled length, and every model
   reads flat within its own round-to-round spread (±3 %). So the effect is the runtime's, not the host's.
4. Between the same two allocations the CPU arm's Δ on the dashboard bundles (−22 % E2B, −21 % E4B, −60 % 0.6B wi4b32 at
   2304→8192) brackets the K5 gemma-3-270m figure on this host (−35 % at 1280→4096); the 0.6B wi4b32 file, the same export
   spelling as the S26 sweep in K17 (94.9 → 52.9 → 15.4 tok/s at 384 / 1024 / 4096), pays the most.

## Exclusions and what they are evidence of (`probe-evidence/README.md`)

- The dashboard's Qwen3-0.6B and Qwen3-4B LiteRT files (`mixed_int4`) carry a 2,048-entry KV: `FAILED_PRECONDITION:
  Prefill input length exceeds available state entries (remaining capacity: 2048)` when the prompt alone is longer (probe
  p9, the ~2.7K `long-context` task — the same failure the 2026-09-10 cells hit). At this task the prompt fits but prompt +
  output (2,243) does not, and `maxNumTokens` above the exported KV is neither clamped nor refused: at 8,192 the GPU run
  finished at a normal-looking 270 tok/s while the engine printed 10,666 × `Invalid decode and sample result. The sampled
  token is casted to 0 to avoid crash.` (p7); at 2,304 it printed nothing and whether the last 195 steps read a valid KV
  is not established (p5). Those four cells are `exclude=` in the cells file with the reason slug; the 0.6B ladder above
  runs the repo's other published file (dynamic wi4b32, 32,771-token cache — a different recipe, disclosed), and Qwen3-4B
  has no runnable published LiteRT file for this task. A rate from a run that logs `Invalid decode` is not a measurement.
- `FAILURES.txt` lists all 120 llama.cpp launches: every one is the known Metal teardown abort
  (`GGML_ASSERT([rsets->data count] == 0)`, rc 134) after both records were appended — 16 records per llama.cpp cell,
  same as every other cell (`ls *.jsonl | xargs grep -c '"task"'`). Records stand; the FAIL lines are the exit code.

## Harness changes made for this session (all in this commit)

- `long-context-2048-gen256` task (`ios/BenchmarkApp/Sources/Benchmark/BenchmarkTask.swift`; `LongContextTask` gained an
  explicit `blocks:` override because the nominal 55 tokens/block under-counts real tokenizers).
- `yardstick run --litert-backend cpu|gpu` (`apple/YardstickCLI/Sources/Yardstick.swift`, `MediaPipeRuntime` takes a
  `backend:`; records stamp `runtime: litert-lm-cpu` for the CPU arm via a new `LLMRuntime.recordRuntimeLabel`).
- Catalog id `litert-community/Qwen3-1.7B/int8` (the card's CPU file) beside the wi4b32 GPU entry.
- Mac runner (`scripts/bench_matrix_mac.sh`): `backend=` forwarded, capture file keyed on `backend=` / `context-tokens=`,
  `ROUNDS=N` round mode (gate off, host load logged per round), `gtimeout` around each launch.
- `validate_cells.py` (task id; `backend=` on mac litert-lm rows; cell identity includes context-tokens),
  `render_dashboard.py` (`litert-lm-cpu` arm on mac), `matrices/README.md`, `scripts/longctx_ab_report.py` (this table).
- Built with `xcodebuild` directly (no `xcodegen generate`: another session's uncommitted `project.pbxproj` edits stay
  untouched, sha256 verified before/after); derived data `.build/dd-mac`, still the v0.16.0 pin.

## Files

`ladder-warm.md` / `ladder-cold.md` (+ `.csv`) — the two regimes from `scripts/longctx_ab_report.py`; `*.jsonl` — 16
records per cell (2 per round × 8); `host_load.log`; `session_provenance.txt`; `probe-evidence/`; driver log
`logs/longctx/2026-09-18-m4max.log`.

## Cross-check with the engine's own `--benchmark` (exact 2048 / 256 tokens), 09:02–09:15 — `cli-crosscheck/`

Same host, right after the session, one process per (file, backend, allocation) × two passes (forward, then reversed
order), `--num_iterations=3` each, `--disable_cache=true`: CPU = the c363e172 XNNPACK build the K5 rows were measured
with (ynnpack_work `bin/mac/litert_lm_advanced_main.no_ynnpack`), GPU = the v0.17.0-tag CLI with ONLY the WebGPU
accelerator dylibs beside it (`sha256.txt`; the registry logs `GPU WebGPU`, the same delegate family as the Swift package).
`max_tokens:` in every settings dump equals the requested allocation; 0 `Invalid decode` lines in all 30 logs. Decode tok/s,
median of 6 [min–max]:

| backend | file | 2304 | 4096 | 8192 | yardstick warm medians (above) |
|---|---|---|---|---|---|
| cpu | Qwen3-0.6B wi4b32 | 44.3 [43.9–44.9] | 33.9 [33.7–34.9] | 18.0 [17.9–18.4] | 45.1 / 34.0 / 18.1 |
| cpu | Gemma 4 E2B | 50.4 [40.3–50.7] | 46.5 [37.5–46.6] | 39.1 [32.4–39.2] | 50.6 / 46.6 / 39.2 |
| cpu | Qwen3-1.7B dynamic INT8 | 29.3 [26.3–34.7] | 29.5 [25.8–34.4] | 34.4 [30.8–34.8] | 28.5 / 28.6 / 28.7 |
| gpu (WebGPU, 0.17.0 CLI) | Qwen3-0.6B wi4b32 | 292.8 [170.2–293.1] | 285.3 [281.6–288.4] | 238.4 [233.0–238.8] | 290.4 / 284.5 / 238.0 |
| gpu (WebGPU, 0.17.0 CLI) | Gemma 4 E2B | 158.3 [151.3–159.9] | 156.9 [156.3–157.5] | 139.6 [139.2–140.1] | 155.5 / 155.0 / 137.4 |

Every ladder that falls in the yardstick falls the same way here, within 2 % of the yardstick medians on both backends, with
exact token counts and no prompt — so the effect is the engine's, not the prompt task's or the Swift wrapper's. The INT8
1.7B file is the noisy one on the CLI (per-iteration 26–35 tok/s, a bimodal spread the yardstick runs did not show) and
does not fall with the allocation there either. The lone 170.2 in the 0.6B GPU 2304 cell is the first iteration of the
first process (cold shader build under `--disable_cache`), as in the 09-17 runs.
