# Public reflection — draft lines (lane D2D1, round 7)

Two proposals. Nothing here is committed in either skill; the supervisor commits, pushes or opens a PR after the user's GO (the litert-samples one through /litert-team). Every fact carries its source; the commands were run in this lane (sessions named per line).

## 1. Own skill: `skills/run-edge-llm-bench/SKILL.md` (this repo)

Assets: the skill cells of `edge-llm-bench-build-ref` and `edge-llm-bench-ddp-ios` (todo). Base: the file at 424564f9 (216 lines).

### 1a. Frontmatter `description` (line 3)

Replace "to repeat a measurement at a newer LiteRT-LM build," with:

> to repeat a measurement at a newer LiteRT-LM build (a release tag, or any git ref, run on a DDP lab phone),

and append after "(a GUI signing step).":

> DDP lab iPhones run the LiteRT-LM cells through an XCTest archive (`ios/ddp/`).

Sources: `android/README.md` "Build from head or a PR"; `ios/ddp/README.md`.

### 1b. Section "Lab phones without adb (Developer Device Platform)": a bullet after "Fields only a DDP record carries" (after line 175)

> - **A LiteRT-LM build from a git ref.** `LITERTLM_REF=<sha | branch | pr/N> android/scripts/build_litert_lm_main.sh`
>   builds that commit into `android/bin/<label>/` (`main-<sha9>`, `<branch>-<sha9>` or `pr<N>-<sha9>`;
>   `LITERTLM_DRY_RUN=1` prints the label, the commit and every command first) and registers its files'
>   sha256 in `android/engine-pins.json` (`android/scripts/pins_add.py`).
>   `BENCH_ANDROID_BIN_DIR=android/bin ./bench matrix <cells> --ddp <id> --engine-build <label>` runs it. The
>   records stamp the label; the pin stays, and a label's rows never take a standing cell from a tag's. Count
>   the `Prefill Turn` lines of one raw log before comparing prefill: main at 16ab5491 prints two (the prompt,
>   then the reply + 3 tokens) and the record keeps the last.

Sources: `android/README.md` 50-80; `scripts/render_leaderboard.py` `latest_session` docstring; `android/bench/parsers.py` 72-91; `results/raw/2026-10-16-ddp-buildref-akita-35-android/app-path-android/*_run1.log` 350-354; sessions `session-733dfb76` (akita-35), `session-0214b9f1` and `session-4b77de16` (m1q-36), K/r2/turns.md.

### 1c. Same section: a paragraph before "## Symptoms" (after line 179)

> The LiteRT-LM cells also run on a DDP lab iPhone through an XCTest archive of the bench app
> (`ios/ddp/README.md`). Build the archive once with an Xcode the lab runs
> (`DEVELOPMENT_TEAM=<team id> BUNDLE_ID=<app id> DEVELOPER_DIR=<that Xcode> ios/ddp/build_xctest.sh`; the
> App ID's profile must carry the two memory entitlements, and that Xcode needs its iOS platform
> component), then submit one session per cell, dry run first:
>
> ```bash
> ios/ddp/run_ddp_ios_lm.py --device iphone16pro-18-3 --model-id litert-community/Qwen3-1.7B --backend gpu --dry-run --project <your project> --bucket gs://<your bucket>
> ios/ddp/run_ddp_ios_lm.py --device iphone16pro-18-3 --model-id litert-community/Qwen3-1.7B --backend gpu --project <your project> --bucket gs://<your bucket>
> ```
>
> - **One session is one unit, in the thermal state it is in.** The test waits for a nominal thermal state
>   before run 1 (`conditions.ddp.thermalGate*`), and a cell can still turn fair by its last run: gate it as
>   the attached-iPhone runner does (`scripts/cell_gate.py --runs 4`). A HOT first capture moves to
>   `device-jsonl-flagged/` with a `FLAGGED.txt` line and is retaken once; a HOT retake stands with its line.

Sources: `ios/ddp/README.md` 1-60; `ios/ddp/run_ddp_ios_lm.py` `main` (flags 606-626); `ios/BenchmarkApp/SourcesDDP/DDPHarness.swift` `waitForNominalThermal`; `results/raw/2026-10-16-ddp-iphone16pro-18-3-ios/FLAGGED.txt` (7 lines); K/r3/build-1-no-platform.log (the platform component).

### 1d. "Tested on" (lines 211-216): append

> LiteRT-LM main-16ab54914 built from its git ref, gpu: `akita-35` `session-733dfb76`, `m1q-36`
> `session-0214b9f1` and `session-4b77de16`, 2026-10-16. DDP lab iPhone 16 Pro (`iphone16pro-18-3`, iOS 18.3.2),
> v0.18.0 through XCTest, cpu and gpu: `session-9906c909`, `session-f3300117`, `session-f959404e`,
> `session-a04cbc40`, 2026-10-16.

Sources: the records' `conditions.ddp.sessionId` in `results/raw/2026-10-16-ddp-buildref-{akita-35,m1q-36,m1q-36-b}-android/` and `results/raw/2026-10-16-ddp-iphone16pro-18-3-ios/device-jsonl/`.

## 2. litert-samples `skills/benchmark-on-ddp/SKILL.md`: one Watch for bullet

Where: the worktree `~/code/litert-samples-ddp-skill-wt`, branch `skills-benchmark-on-ddp-lab-notes` (edfe9307, the five lab notes, not pushed), after the bullet "Some lab units start with lowered CPU clock ceilings." (lines 82-83). The XCTest of `benchmark/ios` there has no thermal wait (`grep -ci thermal benchmark/ios/Tests/*.mm` = 0). Route: /litert-team, the same Draft PR as the five notes, after the GO.

> - **An iPhone lab unit starts in the thermal state it is in.** Four `iphone16pro-18-3` sessions of 2026-10-16
>   (one unit each; LiteRT-LM v0.18.0 through XCTest) started runs at fair or serious, two of them from
>   run 1 (`ProcessInfo.thermalState`), and a nominal gate called all four HOT. With a wait for nominal before the
>   first run (polled every 30 s, at most 600 s, inside `--xctest-timeout`), four more units read nominal at
>   once, and three of those cells still reached fair or serious by run 4 of 4. Read each run's thermal state
>   with its number, and wait for nominal before run 1.

Sources: `results/raw/2026-10-16-ddp-iphone16pro-18-3-ios/device-jsonl-flagged/*.json` (`metrics.initialThermalState`, r4: sessions 70a0e2dc, 71bd2279, 2af96355, 869a5c6a), `device-jsonl/*.json` (r6: 9906c909, f3300117, f959404e, a04cbc40; `conditions.ddp.thermalGateWaitedSeconds` 0), `FLAGGED.txt` (4 first + 3 retry lines), `ios/BenchmarkApp/SourcesDDP/DDPHarness.swift`.
