# 2026-10-17 — Catalog X2 on the iPhone 18 Pro: LiteRT-LM decode and prefill across the allocated KV at a constant 256-token answer, Gemma 4 E2B / E4B on the Metal GPU and on the XNNPACK CPU

Status: closed. Six holds of the bench iPhone (iPhone 18 Pro, A20 Pro), 19:44 JST 2026-10-17 – 00:57 JST 2026-10-18, no
reboot. GPU ladders: E2B 6 of 6 rounds, E4B 6 of 6 rounds. CPU ladders: E2B 5 complete rounds (+ two cells of round 6),
E4B two sittings read side by side and never pooled (sitting 1: 2 complete rounds + two cells of round 3; sitting 2: 3
complete rounds + two cells of round 4). Every number below comes from the stored records (`device-jsonl/` of the sitting named in each table);
every table names its readout file. Per-op profile: **not taken on iOS** (the app has no profiling flag;
`./bench profile` is the Android route) — the ladders answer the decode / prefill question only.

## What this answers

Catalog row X2 (`litert-knowledge/06-recommendations/op-level-catalog.md`) kept one cell open after the S26 leg closed
on 2026-10-12: **the iPhone, both backends** — does LiteRT-LM decode at a fixed filled length track the *allocated* KV
(`maxNumTokens` 2304 / 4096 / 8192) on the phone's Metal GPU and on its XNNPACK CPU, as it does on the Mac (both arms,
`results/raw/2026-09-18-dashboard-longctx-v1-m4max-mac/NOTES.md`) and does not on the S26's OpenCL GPU
(`results/raw/2026-10-12-catalog-x2-s26-android/README.md`)? Same comparison form as those two legs: one filled prompt,
a 256-token answer, three allocations, paired rounds, cold and warm read apart.

## Protocol

- Device: iPhone 18 Pro (iPhone19,2, A20 Pro; UDID 00008160-000038CA02C00036, devicectl id C7A74909-…), iOS 27.2
  (24B5099f), wired USB to the bench Mac, unlocked (Auto-Lock Never), external power connected; the battery sat at its
  80 % charge limit throughout (`battery-start.json` / `battery-end.json` of each sitting: `BatteryCurrentCapacity`
  80, `ExternalConnected` true, `BatteryIsCharging` false; the records stamp `batteryState: charging`, `batteryLevel`
  0.8). The bench iPhone by the device policy (the 17 Pro is the user's daily phone and was not attached); this is the
  18 Pro's own column in the catalog, not a continuation of the 17 Pro rows.
- App: `ios/BenchmarkApp` (BenchmarkApp, bundle `com.example.CoreMLLLMChat` 0.2.0, Release, team MFN25KNUGJ, the two
  increased-memory entitlements), built from this commit's `Sources/` in the build tree `.build/dd-ios-0180-18pro/src`
  (the 2026-10-15 tree's layout: `Vendored/LiteRT-LM` = the v0.18.0 tag with `Vendored-patches/0001`, `coreai-models`
  = bd3c539; main binary sha256 2eb5cafd7c1f943d…); installed 19:44:41 over the phone's previous build (the v0.16.0
  app the dashboard job measured that morning, `../2026-10-17-dashboard-v1-iphone18pro-ios/`). Every record stamps
  `engineVersion v0.18.0`, `engineArtifact CLiteRTLM.xcframework.zip@v0.18.0 sha256:d765b995…`,
  `buildConfiguration Release`; the embedded `CLiteRTLM` framework's LC_UUID 8B273118-4378-385E-9C99-F71DD8ED7642 is the
  xcframework's ios-arm64 slice.
- Task `long-context-2048-gen256-noref`, new to the Swift catalog in this commit (`LongContextTask.norefTail`): the
  same 27 `[i]`-tagged lorem blocks as `long-context-2048-gen256`, then the tail of `scripts/gen_task_prompts.py`
  `NOREF_TAIL` ("The numbered blocks above are filler text … From your own knowledge, list 25 distinct things …").
  Byte-identical to `prompts/text/long-context-2048-gen256-noref.txt` (7,822 bytes, sha256 3e3f17a3941f25300adc2097…,
  checked by compiling the task source alone on the Mac, `tools/prompt-hash-check/`, 2026-10-17 19:40); 1,654 prompt tokens as the engine counts them (every
  record, the S26 leg's count); budget 256 (`prompts/text/budgets.tsv`).
- Output cap: `output-cap=engine` (new cell key, this commit: `--litert-output-cap engine` →
  `MediaPipeRuntime.engineOutputCap`): the engine stops at 256 through `sendMessageStream(maxOutputTokens:)`, as the
  Android CLI's `--max_output_tokens=256` did on the S26, and the record's decode rate is the engine's counter over
  exactly those 256 tokens (`decodeTokensPerSecondWallClock` is stored beside it; they agree within 0.5 % on every
  warm record). The dashboard's iOS cells keep the default (`drain`: the app caps the stream at 256 chunks and drains
  the engine to its context bound or EOS); that path would have decoded thousands of uncounted tokens between run 1 and
  run 2 of a launch at an 8,192-token allocation, so the ladder does not use it. Default sampler of the task
  (temperature 0, topP 1, topK 40).
- Backends: `backend=gpu` = the Metal GPU accelerator (every launch log: `RegisterAccelerator: … name=GPU Metal`,
  `YARDSTICK_METAL_DEVICE name=Apple A20 Pro GPU`), records `runtime: litert-lm`; `backend=cpu` = XNNPACK
  (`XNNPACK CPU accelerator registered`, `Created TensorFlow Lite XNNPACK delegate for CPU`), records
  `runtime: litert-lm-cpu`. Standard Gemma files (`gemma-4-E2B-it.litertlm`, `gemma-4-E4B-it.litertlm`, wNa8o8), in
  the app container since 2026-09-03 / 09-21 (`modelRevision` b3ca0d2f… / 2eee7ac3…).
- Launch = one app process per cell per round: `--runs 2` (run 1 cold = the engine load and the first Conversation, run
  2 warm = a fresh Conversation on the same engine), `--context-tokens <alloc>` → `maxNumTokens`. Cells:
  `matrices/catalog-x2-iphone18pro-{e2b-gpu,e4b-gpu,e2b-cpu,e4b-cpu}.cells`. Driver `tools/round_driver.sh` (the
  iPhone matrix runner has no round mode): every cell once per round, the order reversed on even rounds, the house
  anchor (`matrices/anchors.cells`: mlx-swift Qwen3-0.6B-4bit short-chat, runs 3) at the head and the tail of each
  sitting; cooldown 60 s between launches, +60 s after a launch that ended `fair`, +300 s after `serious`; no capture
  gate, no retry, no quarantine — every record stays and the tables show every round. Holds through the shared
  `.iphone_hold` (`tools/with_hold.sh`, ≤ 45 min each, deadline = start + 43 min; a launch that would end after it is
  not started, `DEADLINE.txt`).
- Prompt probe (n = 1 per model, never pooled): `matrices/catalog-x2-iphone18pro-prompt-probe.cells`, E4B and E2B GPU
  at 8192 with `--purge-engine-cache` (the phone's `tmp/` held the Metal program / weight caches the v0.16.0 build had
  written, keyed on the model file only; this build wrote its own first). Both PASS: 256 / 256 tokens, 1,654 prompt
  tokens, a numbered list on the asked topic (`../2026-10-17-catalog-x2-iphone18pro-ios-prompt-probe/text_check.md`).
- Admission: the anchor's warm median against the newest admitted dashboard session of this phone,
  `../2026-10-17-dashboard-v1-iphone18pro-r2-ios/SESSION.json` (223.0 tok/s), 5 % rule; the anchor's three 128-token
  runs finish inside one second and the app names a record by its UTC second, so a head or tail anchor keeps 2 of its
  3 records (as in the dashboard sittings).
- Acceptance per cell as on the S26: ≥ 5 complete rounds (met by the GPU ladders and E2B CPU; E4B CPU did not reach
  it — its two sittings stand side by side), every record 256 output tokens, warm spread ≤ 15 %.

## Results

Decode and prefill tok/s = median [min–max] over rounds; spread = max/min − 1; Δ = the median against the same arm's
2304. "cold" = run 1 of each launch, "warm" = run 2. A **first-ever** cold record (the allocation's first launch of the
sitting whose model load took > 2× the cell's median load time) is kept apart; the warm record of that launch stays.

### Gemma 4 E2B, GPU (Metal) — hold 2, 19:47–20:11, 6 of 6 rounds — `../2026-10-17-catalog-x2-iphone18pro-ios-e2b-gpu/ladder.md`

| regime | metric | ctx 2304 | ctx 4096 | ctx 8192 | Δ 2304→4096 | Δ 2304→8192 |
|---|---|---|---|---|---:|---:|
| warm | decode | 84.7 [84.6–84.8] n=6, 0.2 % | 82.7 [82.6–82.9] n=6, 0.4 % | 76.9 [76.8–76.9] n=6, 0.2 % | −2.3 % | −9.3 % |
| cold | decode | 84.7 [84.7–84.8] n=5, 0.1 % | 82.9 [82.8–83.0] n=5, 0.1 % | 76.8 [76.8–76.9] n=6, 0.2 % | −2.2 % | −9.4 % |
| warm | prefill | 4571 [4549–4665] | 3882 [3871–3917] | 2966 [2942–2980] | −15.1 % | −35.1 % |
| cold | prefill | 4621 [4596–4647] | 3940 [3929–3957] | 2986 [2983–3004] | −14.7 % | −35.4 % |
| warm | TTFT ms | 394 | 459 | 592 | | |

Cold n = 5 at 2304 and 4096: round 1 was the allocation's first launch on this build (first-ever: 80.6 / 80.0 tok/s,
load 1.42 / 1.43 s against 0.45 s afterwards, resident peak 1,490 MiB against ≈ 705; the probe had run 8192). All 20
launches `nominal` at start and end. Every record 1,654 prompt / 256 output tokens, stop `length`, text screen PASS.
Resident peak (warm, median) 715 / 720 / 729 MiB. Anchor warm 222.5, 222.8 (head), 221.2, 221.7 (tail): median 222.1
= 0.996 of the reference, admitted.

### Gemma 4 E4B, GPU (Metal) — hold 3, 20:11–20:52, 6 of 6 rounds — `../2026-10-17-catalog-x2-iphone18pro-ios-e4b-gpu/ladder.md`

| regime | metric | ctx 2304 | ctx 4096 | ctx 8192 | Δ 2304→4096 | Δ 2304→8192 |
|---|---|---|---|---|---:|---:|
| warm | decode | 38.5 [38.4–38.6] n=6, 0.3 % | 37.9 [37.9–37.9] n=6, 0.2 % | 36.9 [36.9–37.0] n=6, 0.2 % | −1.7 % | −4.1 % |
| cold | decode | 35.5 [35.4–38.4] n=5, 8.5 % | 37.5 [37.0–37.8] n=5, 2.2 % | 35.4 [33.5–36.8] n=6, 9.9 % | (+5.4 %) | (−0.3 %) |
| warm | prefill | 1707 [1702–1717] | 1548 [1540–1550] | 1313 [1310–1321] | −9.3 % | −23.1 % |
| cold | prefill | 1491 [1319–1710] | 1497 [1482–1568] | 1238 [1122–1294] | | |
| warm | TTFT ms | 1032 | 1132 | 1324 | | |

The warm rows are the reading; the cold rows spread 8.5–9.9 % at 2304 and 8192 (their Δ is in brackets, not read): the
cold run follows the 3.4 GB model load and its rate moved with the phone's thermal state (`fair` from launch 7 on, the
third launch of round 2; 14 of 20 launches ended `fair`, none `serious`), while the warm run of the same launch did not
(37.9 at 4096 under `nominal` and under `fair`). First-ever: 2304 round 1 (36.5, load 5.35 s, resident 2,905 MiB) and
4096 round 1 (34.3, 4.79 s, 2,490 MiB); the probe had run 8192 (load 0.84 s in round 1). Every record 1,654 / 256
tokens, stop `length`, text screen PASS. Anchor 221.3, 221.6 / 220.2, 219.6: median 220.8 = 0.990, admitted.

### Gemma 4 E2B, CPU (XNNPACK) — hold 4, 20:52–21:35, rounds 1–5 complete — `../2026-10-17-catalog-x2-iphone18pro-ios-e2b-cpu/ladder.md` (`--rounds 1,2,3,4,5`)

| regime | metric | ctx 2304 | ctx 4096 | ctx 8192 | Δ 2304→4096 | Δ 2304→8192 |
|---|---|---|---|---|---:|---:|
| warm | decode | 32.6 [32.6–32.9] n=5, 1.1 % | 30.0 [29.9–30.1] n=5, 0.7 % | 25.7 [25.6–25.8] n=5, 0.6 % | −7.9 % | −21.1 % |
| cold | decode | 33.3 [33.2–33.4] n=4, 0.4 % | 30.6 [30.5–30.7] n=5, 0.8 % | 26.1 [26.0–26.1] n=5, 0.5 % | −8.2 % | −21.6 % |
| warm | prefill | 753 [749–762] | 601 [600–604] | 414 [410–415] | −20.2 % | −45.0 % |
| cold | prefill | 801 [799–802] | 637 [635–638] | 434 [432–435] | −20.5 % | −45.8 % |
| warm | TTFT ms | 2270 | 2830 | 4083 | | |
| warm | resident peak MiB | 1684 | 1900 | 2436 | +216 | +752 |

Round 6 ran 8192 (26.1 cold / 25.7 warm) and 4096 (30.6 / 30.0) and its 2304 launch was not started (deadline,
`DEADLINE.txt`); those four records are in `records.md`, outside the table. First-ever: 2304 round 1 (32.7, load
1.61 s, resident 2,508 MiB). 16 of 19 launches ended `fair` (from launch 5 on), none `serious`; the warm spreads stayed
≤ 1.1 %. Every record 1,654 / 256 tokens, stop `length`, text screen PASS. Anchor 219.9 / 220.7, 220.8: median 220.7
= 0.990, admitted.

### Gemma 4 E4B, CPU (XNNPACK) — two sittings side by side (never pooled)

Sitting 1 = hold 5, 21:36–22:18, `../2026-10-17-catalog-x2-iphone18pro-ios-e4b-cpu/ladder.md`: rounds 1 and 2
complete, round 3 ran 2304 and 4096 and its 8192 launch was not started (deadline). Four of the ten launches ended
`serious` (every 4096 launch and round 1's 8192) and the driver waited 300 s more after each, so 43 minutes held two
rounds. Sitting 2 = hold 6, 00:08–00:57 (2026-10-18), `../2026-10-17-catalog-x2-iphone18pro-ios-e4b-cpu-s2/ladder.md`.

| regime | ctx | sitting 1 (rounds in the cell) | sitting 2 (rounds in the cell) |
|---|---:|---|---|
| warm | 2304 | 13.7 [13.2–13.8] n=3 (r1–3), 4.2 % | 13.8 [12.7–13.9] n=3 (r1–3), 9.1 % |
| warm | 4096 | 12.1 [11.3–12.1] n=3 (r1–3), 6.8 %, −12.3 % | 12.7 [12.0–13.1] n=4 (r1–4), 9.2 %, −7.7 % |
| warm | 8192 | 11.5 [11.3–11.7] n=2 (r1–2), 4.4 %, −16.3 % | 11.2 [10.4–11.4] n=4 (r1–4), 9.3 %, −18.7 % |
| cold | 2304 | 14.5 [14.4–14.5] n=2 (r2–3), 0.5 % | 14.4 [14.0–14.5] n=3 (r1–3), 3.2 % |
| cold | 4096 | 13.6 [13.5–13.6] n=3 (r1–3), 0.5 %, −6.2 % | 13.7 [13.5–13.8] n=4 (r1–4), 2.0 %, −4.9 % |
| cold | 8192 | 12.0 [11.8–12.3] n=2 (r1–2), 4.0 %, −16.9 % | 12.2 [12.2–12.3] n=4 (r1–4), 1.0 %, −14.9 % |
| warm prefill | 2304 / 4096 / 8192 | 347 / 292 / 217 (−15.8 / −37.4 %) | 347 / 293 / 217 (−15.6 / −37.3 %) |
| cold prefill | 2304 / 4096 / 8192 | 376 / 315 / 222 (−16.3 / −40.8 %) | 373 / 317 / 232 (−14.9 / −37.6 %) |
| warm resident peak MiB | 2304 / 4096 / 8192 | 3208 / 3425 / 4048 | 3207 / 3426 / 4000 |

Sitting 2: rounds 1–3 complete, round 4 ran 8192 and 4096; its 2304 launch and the tail anchor were not started (deadline, `DEADLINE.txt`). Five of its eleven ladder launches ended `serious` (every 8192 launch after the first, and two 4096 / 2304 launches), each followed by the 360 s cooldown. The cold rows are the readable ones in both sittings (spreads 0.5–4 %; the warm run follows a cold run that heated the phone, spreads 4–9 %): cold −6.2 % / −16.9 % (sitting 1) and −4.9 % / −14.9 % (sitting 2) at 4096 / 8192; warm −12.3 % / −16.3 % and −7.7 % / −18.7 %. No first-ever record in sitting 2 (the bundle's pages and caches from sitting 1 were still on the phone). **The hold ran 48.8 minutes, 3.8 over the 45-minute rule**: the driver checked the deadline before a launch, not before a cooldown, so the 360 s cooldown after the last launch (00:51) ran past the 00:51:12 deadline with the phone idle, and the release came at 00:57:02.

Sitting 1's first-ever: 2304 round 1 (14.4, load 2.99 s, resident peak 5,453 MiB — the load of the 3.4 GB bundle
through the CPU path; the later launches of that cell peak at 3,196). Every record of both sittings: 1,654 / 256
tokens, stop `length`, text screen PASS. Anchors: sitting 1 220.1, 219.8 / 221.2, 220.8 (median 220.5 = 0.989);
sitting 2 222.4, 221.5 (head only; the tail anchor fell past the deadline): median 222.0 = 0.995, admitted.

## Reading (measured facts, one per line)

- **On the A20 Pro's Metal GPU, decode at a constant 256-token answer falls with the allocation**: E2B −2.3 % at 4096
  and −9.3 % at 8192 (warm; cold −2.2 / −9.4 %; spreads ≤ 0.4 %), E4B −1.7 % and −4.1 % (warm; spreads ≤ 0.3 %).
  The S26's OpenCL GPU read flat within ±1.2 % (E2B) and within 5 % (E4B) on the same task; the Mac's Metal-backed GPU
  (v0.16.0, drain path) read −11.6 % (E2B) and −8.6 % (E4B) at 8192.
- **The phone's XNNPACK CPU pays as the Mac's does**: E2B −7.9 % / −21.1 % (warm; the Mac −7.9 % / −22.5 %), E4B
  −12.3 % / −16.3 % in sitting 1 (2–3 rounds) and −7.7 % / −18.7 % in sitting 2 (3–4 rounds); cold, the tighter regime on this arm, −6.2 / −16.9 % and −4.9 / −14.9 %.
- GPU prefill falls more than decode: E2B −15 / −35 %, E4B −9 / −23 % (warm); CPU prefill −20 / −45 % (E2B) and
  −16 / −37 % (E4B). TTFT grows accordingly (E2B GPU 394 → 592 ms, E2B CPU 2.3 → 4.1 s).
- The CPU arm's resident peak grows with the allocation (E2B +752 MiB, E4B +840 MiB from 2304 to 8192); the GPU arm's
  does not (E2B 715 → 729 MiB): the KV the CPU path allocates is host memory the sampler sees.
- Every ladder answer is 256 tokens, stop `length`; the first 200 characters are a numbered list on the asked topic
  on every record (`text_check.md` of each sitting); no refusal of the lorem blocks (the reason the `-noref` task
  exists) on this engine.
- The first launch of a model at an allocation on this build loads 3–6× slower and decodes a few per cent slower
  (first-ever, kept apart); the probe's `--purge-engine-cache` launches at 8192 took that cost for the 8192 cells.
- Thermal: the GPU E2B sitting stayed `nominal`; E4B GPU and both CPU ladders ran mostly at `fair` and E4B CPU reached
  `serious` after its 4096 launches. The warm decode of a cell did not move between `nominal` and `fair` launches
  (E4B GPU 4096: 37.9 under both); the E4B GPU cold run did (spread 8.5–9.9 %).
- Anchors: four sittings' warm medians 222.1 / 220.8 / 220.7 / 220.5 / 222.0 against the morning's 223.0
  (0.989–0.996), all admitted.

**K5 on the Apple GPU (the question under X2's iPhone cell).** Yes — on this phone the Metal GPU arm's decode tracks
the allocated KV at a fixed filled length, by −9.3 % (E2B) and −4.1 % (E4B) from 2304 to 8192 with warm spreads under
0.5 %, the same direction and about the size of the Mac's Metal-backed GPU (−11.6 / −8.6 %), and unlike the S26's
OpenCL GPU (flat). The op is not attributed here: iOS has no per-op profile in this harness, so whether the growing
time sits in an attention batch-matmul over the allocated cache (K5's CPU mechanism) or elsewhere is open; the CPU
arm's ladder on the same phone (−21 % E2B, with resident memory growing with the allocation) matches K5's shape.

## Not measured

- The per-op profile of either backend on iOS (no profiling flag in the app; the K5 op attribution stays the S26 / M4
  CPU profiles').
- An E4B CPU sitting of ≥ 5 complete rounds (two sittings of 2–4 rounds, side by side).
- File-cache-cold rows (no reboot; "cold" = run 1 of a fresh process with the bundle in the page cache) and the drain
  path's numbers (the dashboard's), not comparable to these.
- Qwen3 bundles, llama.cpp control ladder on this phone.

## Conditions

Per launch: `launches.tsv` of each sitting (round, launch index, cell, allocation, start / end UTC, exit code, RUN_OK
count, thermal at the first run's start and the last run's end, console file, records pulled); per record: `records.md`
(thermal start / peak / end, battery, resident peak, load time, engine, build); `anchor.md`; `text_check.md`;
`console_r<round>_<nn>_<cell>_ctx<N>.txt` = the launch's whole console (the `YARDSTICK_*` lines, the accelerator
registry, the Metal device). Battery at the head and tail of each sitting: `battery-start.json` / `battery-end.json`.
Hold log: `device-state/hold<1-6>.log` (acquire / release times, every launch line). Screen: on, the app in the
foreground with the idle timer disabled (the app's headless mode), unlike the S26 leg's Dozing screen; the phone sat
at 80 % battery on external power. Host side: the driver ran on the Mac (one `devicectl` per launch, one `copy from`
of the results folder after each); the Mac was not quiet (other agent sessions), nothing of it touches a phone number.

## Corrections to the launch brief

1. The Mac leg's record is `NOTES.md`, not `README.md`.
2. The noref task did not exist in the Swift catalog (Android only); this commit adds it (`LongContextTask.norefTail`,
   byte-identical to the generated prompt file).
3. The app installed on the 18 Pro was a v0.16.0 build (the morning's dashboard records stamp it); the rebuild is the
   repo's current pin, v0.18.0, so this leg is v0.18.0 while the Mac and S26 legs are v0.16.0.
4. The iOS LiteRT task path caps at 256 chunks and then drains the engine to its context bound; the ladder runs with
   the new `output-cap=engine` key (the engine stops at 256, the Android CLI's shape). `validate_cells.py` and
   `scripts/bench_matrix_iphone.sh` gained the key (3 lines each) so the cells reproduce through `./bench matrix`.
5. The CPU cells are two files (E2B, E4B) rather than one, so that each sitting fits a 45-minute hold.
6. `~/code/litert-knowledge` is not a git repository; the catalog write-back proposal is a `diff -u` in
   `catalog-x2-diff.md`, not a `git diff`.
7. Hold 6 was held 48.8 minutes (the rule is 45): the driver's deadline guard sat before a launch, not before a cooldown, and
   the 360 s cooldown after a `serious` launch ran past the deadline with the phone idle. `tools/round_driver.sh` as committed
   ends the sitting instead of sleeping past the deadline (fixed after the fact; the sittings above ran the earlier text).
8. `./bench dashboard-job auto --dry-run` was run once at 19:28 to read the week's state; it writes one line to the
   job's production log (known trap) and measured nothing.

## Reproduction

```bash
python3 scripts/gen_task_prompts.py                       # prompts/text/long-context-2048-gen256-noref.txt, byte-identical to the Swift task
for f in matrices/catalog-x2-iphone18pro-*.cells; do python3 scripts/validate_cells.py $f; done
T=results/raw/2026-10-17-catalog-x2-iphone18pro-ios/tools
# one sitting (the hold is the conversion lane's .iphone_hold; 45 min at most):
$T/with_hold.sh x2-iphone-leg-h2 45 -- env ROUNDS=6 COOLDOWN=60 BENCH_UDID=00008160-000038CA02C00036 \
  APP=com.example.CoreMLLLMChat bash -c "$T/round_driver.sh matrices/catalog-x2-iphone18pro-e2b-gpu.cells <campaign> \$HOLD_DEADLINE"
python3 $T/ladder.py results/raw/2026-10-17-catalog-x2-iphone18pro-ios-e2b-gpu --anchor-ref 222.99        # ladder.md|csv, records.md, text_check.md, anchor.md
python3 $T/ladder.py results/raw/2026-10-17-catalog-x2-iphone18pro-ios-e2b-cpu --anchor-ref 222.99 --rounds 1,2,3,4,5
```

Re-run of the readouts on 2026-10-18 reproduces every table above from the stored records.

## File map

- `README.md` — this file; `catalog-x2-diff.md` — the proposed write-back to the catalog's X2 / K5 rows and summaries
  (not applied).
- `tools/round_driver.sh`, `tools/with_hold.sh`, `tools/ladder.py` — the driver, the hold wrapper, the readout;
  `tools/prompt-hash-check/` — the Swift task's prompt against the generated file.
- `device-state/hold<1-6>.log` — the six holds; `device-state/hold1-install.txt` — the app install.
- `../2026-10-17-catalog-x2-iphone18pro-ios-prompt-probe/` — the n = 1 probes (never pooled).
- `../2026-10-17-catalog-x2-iphone18pro-ios-{e2b-gpu,e4b-gpu,e2b-cpu,e4b-cpu,e4b-cpu-s2}/` — the sittings
  (`device-jsonl/` raw records, `console_*.txt`, `launches.tsv`, `driver.log`, `session_provenance.txt`,
  `battery-*.json`, `ladder.md|csv`, `records.md`, `text_check.md`, `anchor.md`, `DEADLINE.txt` where a launch was
  not started).
