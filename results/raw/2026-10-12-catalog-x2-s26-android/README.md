# 2026-10-12 — Catalog X2 on the Galaxy S26: LiteRT-LM GPU decode across the allocated KV at a constant 256-token answer (Gemma 4 E4B, E2B), and a per-op profile of the CPU path across the allocation (Gemma 4 E2B)

Status: closed. Four holds of the shared phone, 06:12–08:48 JST (no reboot). E2B GPU ladder: 6 of 6 rounds. E4B GPU
ladder: two sittings of 4 complete rounds each (6 asked; the hold deadline came first, see Conditions), read side by
side and never pooled. CPU per-op profile: allocations 2304 / 4096 / 8192 (the planned 1280 is refused by the
engine). Every number below comes from the stored records; every table names the records it reads.

## What this answers

Catalog row X2 (`litert-knowledge/06-recommendations/op-level-catalog.md`) kept two cells open on the S26 after
catalog K5's S26 leg (2026-09-20..24):

- (a) the GPU decode change across `max_num_tokens` 2304 / 4096 / 8192 **at a constant 256-token answer**. In the
  2026-09-24 GPU re-take (`results/raw/2026-09-24-dashboard-longctx-v1-s26-android-gpu-retake/`) E4B refused the
  lorem prompt in 50–61 tokens and E2B stopped at 93 tokens at 8192, so those rates were taken over different
  answer lengths.
- (b) a per-op profile of the CPU (XNNPACK) path naming the op whose time grows with the allocated KV length.

## Protocol

### (a) GPU ladders

- Task `long-context-2048-gen256-noref` (new, Android only): the same 27 `[i]`-tagged lorem blocks as
  `long-context-2048-gen256`, then this tail (`scripts/gen_task_prompts.py` `NOREF_TAIL`):

  > The numbered blocks above are filler text and carry no information; do not summarize or evaluate them. From your
  > own knowledge, list 25 distinct things on-device AI lets a phone do that a cloud model cannot. Number every item
  > and give each one two full sentences of explanation. Do not stop early.

  `prompts/text/long-context-2048-gen256-noref.txt`: 7,822 bytes, sha256
  3e3f17a3941f25300adc2097db767582bbae95ef6ba46fc498588e4d0317b392; 1,654 prompt tokens as the engine counts them
  (every record); budget 256 (`prompts/text/budgets.tsv`).
- Prompt probe (n = 1, never pooled): `matrices/catalog-x2-s26-prompt-probe.cells` (E4B gpu 2304, 8192) and
  `…-prompt-probe-e2b.cells` (E2B gpu 8192); PASS = both iterations 254–256 generated tokens, coherent on-task
  text, 0 × `Invalid decode`. All three passed with 256 / 256 tokens:
  `../2026-10-12-catalog-x2-s26-android-prompt-probe/`.
- Ladders, one session per model and sitting: `matrices/catalog-x2-s26-e2b-gpu.cells`,
  `matrices/catalog-x2-s26-e4b-gpu.cells` = the S26 anchor (llama.cpp b8999 Qwen3-0.6B Q4_K_M short-chat, once per
  round) + LiteRT-LM gpu × 2304 / 4096 / 8192. One launch per cell per round, the whole order reversed on even
  rounds. Each LiteRT launch = `litert_lm_advanced_main` v0.16.0 (sha256 e5de2d9054695632…, the
  `android/engine-pins.json` pin; every record's witness)
  `--backend=gpu --input_prompt_file=… --max_num_tokens=<alloc> --max_output_tokens=256 --num_iterations=2 --async=false --benchmark --benchmark_prefill_tokens=0 --benchmark_decode_tokens=0 --use_session=false`:
  iteration 1 = cold, iteration 2 = warm (one engine, a fresh Conversation each). Engine-default sampler.
- Env: `ROUNDS=6 COOLDOWN=30 THERMAL_WAIT=600 BENCH_CPU_MASK= BENCH_ANDROID_SERIAL=RFGL80R6A6H BENCH_SITTING=1
  BENCH_DRIVER_START_EPOCH=<hold start> BENCH_SESSION_DEADLINE=<hold start + 2400>` (E4B sitting 2: + 2520);
  drivers under `nice -n 19`.
- Holds (`s2_npu_sweep/.device_hold`, one keeper each): 1 = 06:12:38–06:51:04 (probes 06:13–06:19, E2B ladder
  06:20:04–06:50:45); 2 = 06:51:22–07:31:34 (E4B sitting 1, 06:51:38–07:31:22); 3 = 07:31:35–07:46:05 (CPU profile,
  07:31:51–07:45:26); 4 = 08:06:24–08:48:33 (E4B sitting 2, 08:07:03–08:48:24).
- Screen off for every GPU hold (`stay_on_while_plugged_in 0`, `input keyevent 223`, `mWakefulness` Dozing), as in
  the 2026-09-24 re-take; restored at the end (`device-state/SCREEN.md`). Every GPU ladder record reads `Dozing`.
- Files: `gemma-4-E4B-it.litertlm` (3,659,530,240 B, sha256
  0b2a8980ce155fd97673d8e820b4d29d9c7d99b8fa6806f425d969b145bd52e0) and `gemma-4-E2B-it.litertlm`
  (2,588,147,712 B, sha256 181938105e0eefd105961417e8da75903eacda102c4fce9ce90f50b97139a63c), the standard
  litert-community files (wNa8o8), the bytes of the K5 leg.
- Admission: anchor median within 5 % of the admitted 2026-09-14 S26 reference, 105.6 tok/s
  (`results/raw/2026-09-14-dashboard-v1-s26-android/SESSION.json`).
- Acceptance per model: ≥ 5 complete rounds; every LiteRT record 254–256 output tokens; 0 × `Invalid decode`;
  warm cell spread (max/min − 1) ≤ 15 %, else the cell is owed a re-take.

### (b) CPU per-op profile

- `android/bench/run_profile.py matrices/catalog-x2-s26-cpu-profile.cells --max-num-tokens 1280,4096,8192`, then the
  same with `--max-num-tokens 2304` (1280 is refused, below): Gemma 4 E2B, `native-benchmark-1024x256` (prefill 1024 /
  decode 256, as K5's own profile), one unprofiled control + one `--enable_profiling` twin per allocation; env
  `BENCH_ANDROID_SERIAL=RFGL80R6A6H BENCH_CPU_MASK= COOLDOWN=60 THERMAL_WAIT=600`. Controls in
  `profiles/controls-ctx<N>/` (outside the summary layer); a profiled run's rate is never a speed row. Screen Dozing.
- Readout: `scripts/profile/profile_report.py profiles` → `profiles/PROFILE.md`, `profile-table.csv`;
  `tools/prof_ctx_ladder.py profiles --out profiles/ctx-ladder.md` → per Run Order node type (the XNNPACK kernel
  string with its dtypes) the ms per recorded decode step at each allocation, the ratio, the group totals, the GEMV
  clock witness (flat ≤ 10 % or moved) and the CPU clock ceiling of each run.
- KV tensors of the bundle: `tools/kv_inputs.py <bundle>` (static read of the `.litertlm`'s `tf_lite_prefill_decode`
  section, nothing executed) → `profiles/kv-inputs.txt`.

## Results

### (a) Gemma 4 E2B, GPU, hold 1 — `../2026-10-12-catalog-x2-s26-android-e2b-gpu/` (6 of 6 rounds, 42 records)

Median [min–max] over rounds, tok/s; spread = max/min − 1; Δ = change of the median from 2304.

| regime | metric | ctx 2304 | ctx 4096 | ctx 8192 | Δ 2304→4096 | Δ 2304→8192 |
|---|---|---|---|---|---:|---:|
| warm | decode | 25.6 [25.3–27.8] n=6, 9.8 % | 25.8 [25.6–28.3] n=6, 10.6 % | 25.3 [25.2–25.5] n=6, 1.3 % | +0.7 % | −1.2 % |
| cold | decode | 25.8 [25.6–26.3] n=5, 2.5 % | 25.8 [25.3–26.1] n=5, 3.4 % | 25.5 [24.6–27.0] n=6, 9.6 % | +0.1 % | −1.0 % |
| warm | prefill | 2845 [2820–2864] | 2515 [2501–2576] | 1971 [1950–2005] | −11.6 % | −30.7 % |
| cold | prefill | 2886 [2878–2917] | 2511 [2468–2525] | 1980 [1678–1995] | −13.0 % | −31.4 % |

Cold n = 5 at 2304 and 4096: round 1 there was the allocation's first run on this phone (`firstEver`: 24.94, 25.22;
kept apart). Every LiteRT record: 1,654 prompt tokens, 256 output tokens, lexical screen PASS, 0 × `Invalid decode`;
one text per allocation (numbered lists on the asked topic, cut at the budget). Anchor 105.8 / 107.2 / 90.4 / 106.0 /
107.6 / 90.4, median 105.9 = 1.003 of the reference: admitted. Thermal status 0 at the start and end of all 24
launches; battery 35.1–37.0 °C.

### (a) Gemma 4 E4B, GPU — two sittings side by side (never pooled)

Sitting 1 = `../2026-10-12-catalog-x2-s26-android-e4b-gpu/` (hold 2, rounds 1–4 of 6, 31 records); sitting 2 =
`../2026-10-12-catalog-x2-s26-android-e4b-gpu-retake/` (hold 4, rounds 1–4 of 6, 33 records; its `README.md`,
`rounds.md`). Decode tok/s median [min–max], n, spread, Δ from the sitting's own 2304.

| regime | ctx | sitting 1 | sitting 2 |
|---|---:|---|---|
| warm | 2304 | 14.9 [13.4–15.4] n=4, 14.6 % | 15.1 [13.2–15.4] n=4, **16.4 % (over the bar)** |
| warm | 4096 | 15.0 [14.7–15.2] n=4, 3.2 %, +0.4 % | 14.8 [13.7–14.9] n=4, 9.3 %, −2.5 % |
| warm | 8192 | not read: 12.9 [11.0–14.4], **31.2 %** | 14.5 [13.9–14.6] n=4, 4.6 %, −4.0 % |
| cold | 2304 | 15.0 [14.6–15.6] n=4, 6.8 % | 15.1 [14.9–15.4] n=3, 3.8 % |
| cold | 4096 | 15.1 [14.7–15.1] n=3, 2.8 %, +0.7 % | 15.1 [14.8–15.6] n=3, 5.4 %, +0.3 % |
| cold | 8192 | 14.2 [14.1–14.7] n=4, 4.0 %, −5.0 % | 14.5 [14.2–15.2] n=3, 7.2 %, −3.9 % |
| warm prefill | 2304 / 4096 / 8192 | 1076 / 1017 / 869 (−5.6 / −19.3 %) | 1078 / 1010 / 875 (−6.3 / −18.8 %) |
| cold prefill | 2304 / 4096 / 8192 | 1088 / 1018 / 815 (−6.4 / −25.1 %) | 1106 / 1029 / 768 (−7.0 / −30.6 %) |

First-ever cold iterations, kept apart: sitting 1 at 4096 (14.55; the first two allocations had run in the probe),
sitting 2 at all three (14.64 / 14.76 / 14.50). Every record of the complete rounds: 1,654 prompt / 256 output
tokens, lexical screen PASS, 0 × `Invalid decode`; one text per allocation, byte-identical across the two sittings
and the probe. Sitting 1's warm 8192 cell spreads 31 % (three of its four launches ended at thermal status 2; the warm
iteration is the second answer of the hottest launches); sitting 2's warm 2304 cell spreads 16.4 %, its low value
(13.22) one of round 4's three launches, which all ended at status 2 with the policy6 (cpus 6–7) ceiling at 1747.2 MHz. Anchors:
sitting 1 106.2 / 103.9 / 104.9 / 109.5, median 105.55 = 1.000; sitting 2 106.8 / 107.5 / 106.8 / 107.5, median
107.15 = 1.015 — both admitted. The 24 E4B launches of the complete rounds all started at status 0 and ended at 1 (12)
or 2 (12); the 8 anchors 0 → 0; battery 34.9–41.1 °C.

### (b) CPU per-op, Gemma 4 E2B, ms per recorded decode step (`profiles/ctx-ladder.md`; 131 of 256 steps recorded per run)

| node type (Run Order string) | 2304 | 4096 | 8192 | × 4096/2304 | × 8192/2304 |
|---|---:|---:|---:|---:|---:|
| `Delegate/Batch Matrix Multiply (NC, F32, QC8W) GEMM` (attention, 4 decode rows) | 4.73 | 6.55 | 16.98 | 1.38 | 3.59 |
| `Delegate/Softmax (NC, F32)` | 0.14 | 0.21 | 0.67 | 1.50 | 4.75 |
| `SELECT_V2` (70 nodes) | 0.32 | 0.49 | 1.29 | 1.53 | 4.05 |
| `Delegate/Convert (NC, QS8, QC8)` | 0.50 | 0.81 | 1.99 | 1.61 | 3.98 |
| `DYNAMIC_UPDATE_SLICE` (58 nodes) | 0.11 | 0.14 | 0.26 | 1.30 | 2.46 |
| GEMV group (`Fully Connected` QC2W / QC4W / QC8W) — clock witness | 17.25 | 16.67 | 23.80 | 0.97 | 1.38 |
| batch matmul / GEMV | 0.27 | 0.39 | 0.71 | | |
| attention + KV group / GEMV | 0.32 | 0.45 | 0.78 | | |
| control wall ms per step (unprofiled, 1000 / control decode) | 26.4 | 30.5 | 48.7 | 1.16 | 1.84 |

Controls (unprofiled, benchmark mode, never speed rows): 37.9 / 32.7 / 20.6 tok/s, all `cpu-capped`, thermal status 0
at start and end; profiled runs 27.8 / 26.3 / 16.9. The CPU clock: every profiled run's ceilings fell to 2227.2 MHz on
both clusters (of 3628.8 / 4742.4) and sat at that floor for 19 % / 12 % / 51 % of the sampler's 0.5-s ticks (2304 /
4096 / 8192); the controls fell to 2227.2 (2304, 8192) and 2496.0 / 2438.4 MHz (4096).

KV cache read by the batch matmul (`profiles/kv-inputs.txt`, the decode signature of the E2B bundle): 15 `kv_cache_k`
inputs [1, 1, L, 256] (12 layers) or [1, 1, L, 512] (layers 4, 9, 14) and 15 `kv_cache_v` inputs [1, 1, 256, L] or
[1, 1, 512, L] — rank 4, INT8, one scale per tensor; L is stored as 32003, the export's placeholder the engine rewrites
to `--max_num_tokens` at load. The `mask` input is [1, 1, 1, L] BOOL. prefill_1024 / prefill_128 / verify carry the
same cache shapes.

Not run: `--max_num_tokens=1280` (the planned smallest size) with this bundle's 1024-token prefill stops before the
first token on the v0.16.0 CPU path — `dynamic_update_slice.cc:70 SizeOfDimension(update, i) <= SizeOfDimension(operand,
i) was not true`, `Node number 1164 (DYNAMIC_UPDATE_SLICE) failed to prepare`, `Failed to allocate tensors`, exit 13,
twice (`profiles/controls-ctx1280/`, `profiles/FAILURES.txt`); 2304, the smallest allocation of the K5 S26 ladders,
was taken in its place. The optional Qwen3-0.6B wi4b32 pair (`matrices/catalog-x2-s26-cpu-profile-qwen06.cells`, not
committed) did not run (hold time).

## Reading (measured facts, one per line)

- E2B GPU decode at a constant 256-token answer stays within ±1.2 % from 2304 to 8192 (warm +0.7 / −1.2 %, cold
  +0.1 / −1.0 %).
- E4B GPU decode is within ±3 % at 4096 (cold +0.7 / +0.3 %, warm +0.4 / −2.5 %) and 3.9–5.0 % lower at 8192 (cold,
  both sittings; warm −4.0 % in sitting 2), about the size of the cold cells' spread (2.8–7.2 %).
- GPU prefill falls with the allocation: E2B −11.6 / −30.7 % (warm, 4096 / 8192), E4B −5.6 / −19.3 % and
  −6.3 / −18.8 % (warm, sittings 1 and 2).
- Every ladder answer is 256 tokens with 0 `Invalid decode`; the text depends on the allocation only (one per
  allocation, the same in both E4B sittings and the probe).
- On the CPU path the attention batch matmul `Batch Matrix Multiply (NC, F32, QC8W)` (F32 activations against the
  INT8 cache) grows × 1.38 at 4096 and × 3.59 at 8192; Softmax (F32, × 4.75), the mask's `SELECT_V2` (× 4.05), the
  INT8 conversion `Convert (NC, QS8, QC8)` (× 3.98) and the cache write `DYNAMIC_UPDATE_SLICE` (× 2.46) grow beside it.
- The GEMV group is the clock witness: flat from 2304 to 4096 (−3.4 %, batch matmul × 1.38 over the same clock), +38 %
  at 8192, where the profiled run sat at the 2227.2 MHz floor for half its ticks, so 8192 is read as the ratio: batch
  matmul / GEMV 0.27 → 0.39 → 0.71.
- The cache the batch matmul reads is 30 rank-4 INT8 tensors whose sequence axis is the allocation.
- `--max_num_tokens=1280` (= the 1,024-token prefill + 256) is refused at prepare on the v0.16.0 CPU path (exit 13).
- Every GPU launch was `cpu-capped`: the engine CPUs' ceilings fell 34–39 % (E2B) and 58–63 % (E4B) during the launch,
  screen Dozing, thermal status 0 at the start; a GPU arm's capped run pools, marked ◇
  (`methodology/fairness-rules.md` §13), which `scripts/longctx_ab_report.py` does since this lane (it used to drop
  every flagged record's rates).
- Anchors: the E2B sitting's rounds 3 and 6 read 90.4 (uncapped, status 0; not explained); the other twelve anchors of
  the three ladder sittings read 103.9–109.5.
- The four holds' drivers ran on the Mac while the Mac's own dashboard sitting `2026-10-12-dashboard-v1-m4max-mac`
  measured (05:30:11–08:34:06; hold 4 overlapped it until 08:34).

## Not measured

- File-cache-cold rows: they need a reboot, and this lane rebooted nothing (`device-state/UPTIME.txt`). "Cold" here
  is the first answer of a fresh engine process with the bundle in the page cache.
- An E4B sitting of ≥ 5 complete rounds (two sittings of 4, see Conditions); the per-op profile of the GPU path; the
  Qwen3-0.6B wi4b32 profile pair.

## Conditions

Thermal, battery °C, screen, CPU clock ceiling per launch: each campaign's `temperature_log.md`; sitting 2 also per
round and launch in `rounds.md`. Anchors: `anchor.md`; spreads: `spread.md`; per-record table: `records.md|csv`;
text: `text_check.md`. Device state at the head and tail of every hold: `device-state/` (`UPTIME.txt` =
`/proc/uptime` at each: 162,247 → 171,593 s over the eight reads, monotonic = no reboot).

E4B rounds took 6–12 min (`rounds.md`; sitting 1 by the same script): a launch (≈ 45 s, two 256-token answers) ended at thermal status 1 or 2 and the
thermal gate waited for status 0 (30–121 s) before the next launch, so the hold deadline (start + 40 / 42 min) stopped
both sittings in round 5. Round 5 of each sitting is outside every table; in sitting 2 its launch 19 cleared the gate
10 s before the deadline and was cut by the deadline's `timeout` after 1.6 s (exit 124, `app-path-android/FAILURES.txt`;
not an engine failure).

Host side: the drivers ran under `nice -n 19`; the host's share of a phone launch is the bundle's sha256 (2.6 / 3.7 GB,
one core for a few seconds) and the adb I/O; nothing else of this lane ran on the Mac.

## Reproduction

From the repository root:

```bash
python3 scripts/gen_task_prompts.py   # writes prompts/text/*.txt incl. long-context-2048-gen256-noref.txt (byte-identical)
ROUNDS=6 python3 android/bench/run_campaign.py matrices/catalog-x2-s26-e4b-gpu.cells --dry-run
T=results/raw/2026-10-12-catalog-x2-s26-android/tools
C=results/raw/2026-10-12-catalog-x2-s26-android-e4b-gpu        # rounds 1,2,3,4; e2b-gpu: 1,2,3,4,5,6; e4b-gpu-retake: 1,2,3,4
for regime in warm cold first-ever; do
  python3 scripts/longctx_ab_report.py $C --task long-context-2048-gen256-noref --regime $regime --rounds 1,2,3,4 \
    --csv $C/ladder-$regime.csv > $C/ladder-$regime.md
done
python3 $T/text_check.py $C
python3 $T/session_tables.py $C --rounds 1,2,3,4
python3 $T/round_table.py results/raw/2026-10-12-catalog-x2-s26-android-e4b-gpu-retake \
  --log results/raw/2026-10-12-catalog-x2-s26-android-e4b-gpu-retake/driver.log
python3 scripts/profile/profile_report.py results/raw/2026-10-12-catalog-x2-s26-android/profiles
python3 $T/prof_ctx_ladder.py results/raw/2026-10-12-catalog-x2-s26-android/profiles \
  --out results/raw/2026-10-12-catalog-x2-s26-android/profiles/ctx-ladder.md
python3 $T/kv_inputs.py <gemma-4-E2B-it.litertlm>   # needs the litert_lm_builder + ai_edge_litert wheels
```

Re-run on 2026-10-12 (r3), these reproduce the stored tables: the ladders, spreads, anchors, temperature, record and
text tables of the three ladder dirs, `rounds.md`, and `ctx-ladder.md` (two zero-growth rows can trade places: a sort
tie). The e2b-gpu and e4b-gpu dirs carry no `ladder-first-ever.md` (their first-ever iterations are listed in
`records.md`).

## File map

- `README.md` — this file.
- `tools/prof_ctx_ladder.py`, `tools/text_check.py`, `tools/session_tables.py`, `tools/round_table.py`,
  `tools/kv_inputs.py` — the readout scripts (`prof_ctx_ladder.py` checked offline against the K5 M4 Max profile sums
  of `results/raw/2026-09-11-catalog-x13-s26-android/profiles/context-sweep-4devices-2026-09-02/prof_m4`;
  `text_check.py` reproduces the columns of the 2026-09-24 re-take's `text_check.md`).
- `device-state/` — `hold<1-4>-<start|end>.txt`, `UPTIME.txt`, `SCREEN.md`.
- `profiles/` — the CPU per-op pairs, `PROFILE.md`, `profile-table.csv`, `ctx-ladder.md`, `kv-inputs.txt`,
  `FAILURES.txt`, `controls-ctx{1280,2304,4096,8192}/`.
- `../2026-10-12-catalog-x2-s26-android-prompt-probe/` — the n = 1 probes (`probe-records/`, never pooled).
- `../2026-10-12-catalog-x2-s26-android-e2b-gpu/`, `../2026-10-12-catalog-x2-s26-android-e4b-gpu/`,
  `../2026-10-12-catalog-x2-s26-android-e4b-gpu-retake/` — the ladders (`app-path-android/`, `ladder-*.md|csv`,
  `text_check.md`, `temperature_log.md`, `spread.md`, `anchor.md`, `records.md|csv`; sitting 2 also `README.md`,
  `rounds.md`, `driver.log`).
