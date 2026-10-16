速度梯子: なし(変換 lane ではない: 測ったのは harness の経路の確認で、形の選択は無い = `K/SPEED_LADDER.md` は作らず、speed_ladder_lint は回さない; 監督 2026-10-16、D6 lane と同じ扱い)
/litert-data: 回さない(LiteRT を出荷・計測した lane ではない: gate JSON も litert-compat の device-run 行も無い; DDP の record は bench の record = `results/raw/2026-10-16-ddp-buildref-{akita-35,m1q-36,m1q-36-b}-android/`、`results/raw/2026-10-16-ddp-iphone16pro-18-3-ios/` と summary)

# D2D1 lane close — LiteRT-LM for Android from a git ref (D2) + the LiteRT-LM rows on a DDP iPhone through XCTest (D1) (round 7, Opus 5.5, 2026-10-16)

Rounds r1-r6 on branch `build-from-ref` (worktree `~/code/edge-llm-bench-wt-buildref`); this round measured nothing, ran no device and no session, and changed no code, docs, skill or cells. K = this directory. Round notes: `ROUND7.md`. The lane's findings (98 lines: 訂正 31, 罠と袋小路 42, op と delegate の観察 25) are in the handoff `~/code/standup/handoffs/2026-10-16-D2D1-ddp-build-ref-iphone-lm.md` §6, not repeated here.

## public 反映

Every tool this lane added is already in this public repo (`android/scripts/build_litert_lm_main.sh` `LITERTLM_REF`, `android/scripts/pins_add.py`, `bench matrix --ddp --engine-build`, `ios/ddp/`, the `latest_session` rule, docs). Two skill texts remain; the wording is in `K/r7/public-reflection-draft.md` (each fact with its source). Commit, push and PR are the supervisor's after the user's GO.

| # | file | where | what | route | assets cell |
|---|---|---|---|---|---|
| 1 | `skills/run-edge-llm-bench/SKILL.md` (this repo, 216 lines at 424564f9) | line 3 (description); after line 175 (a bullet in "Lab phones without adb"); after line 179 (a paragraph and a bullet before "## Symptoms"); lines 211-216 ("Tested on") | the `--engine-build <label>` route from a git ref (with the two-prefill-turn check), the DDP iPhone route (`ios/ddp/build_xctest.sh`, `run_ddp_ios_lm.py`, one session = one unit, the thermal wait, the home gate and the retake), the seven sessions | a commit on this repo (own skill), after GO | `edge-llm-bench-build-ref` / `edge-llm-bench-ddp-ios` skill = todo |
| 2 | litert-samples `skills/benchmark-on-ddp/SKILL.md` (worktree `~/code/litert-samples-ddp-skill-wt`, branch `skills-benchmark-on-ddp-lab-notes`, edfe9307, not pushed) | after lines 82-83 ("Some lab units start with lowered CPU clock ceilings.") | one Watch for bullet: an iPhone lab unit starts in the thermal state it is in (the first captures HOT, the wait before run 1, three retakes still HOT by run 4); that repo's `benchmark/ios` XCTest has no thermal wait | /litert-team, the same Draft PR as the five lab notes, after GO | — |

## diff 一覧

### lane memory (`~/.claude/projects/-Users-USER-code-edge-llm-bench/memory/`; bytes after the memory hook stamped each file's metadata)

- edit (rewritten, not appended) `mac-quiet-window-leaks.md` (2043 B): candidate (a) — a job of minutes (a build, a simulator test) runs under `quiet_hold.py`, quiet_wait only for jobs of seconds; the Why names the r2 bazel overlap.
- edit `build-yardstick-skips-xcodegen-when-pbxproj-dirty.md` (1965 B): candidate (c) — the committed projects are xcodegen output listing each file; a new `Sources/` file is in none of them until every spec is regenerated (or the code goes into a file they compile, under `#if`). MEMORY.md title now "Committed xcodeproj = xcodegen output".
- edit `ddp-job-is-its-own-unit.md` (2027 B): candidate (d), with r6's result — an iPhone session is one job on one unit; a unit may start fair / serious, the harness waits for nominal before run 1, a cell can still turn fair later → gate as the attached runner (HOT first capture flagged, one retake).
- edit `xcodeproj-copy-for-a-second-package-version.md` (2024 B; 2307 B before = over the 2 KB bar): not in the launch's list — r3 found that the embedded CLiteRTLM is re-signed, so its bytes and sha256 never equal the xcframework's, while the file said "check size/sha"; the proof is now LC_UUID (`dwarfdump --uuid`) against the `ios-arm64` slice. Condensed to fit, no fact dropped.
- new `xcode-ios-build-needs-platform-component.md` (1808 B): candidate (b) — an Xcode builds for iOS only with its own platform component; without that Xcode's simulator runtime even `generic/platform=iOS` fails; `simctl runtime match list`, then `xcodebuild -downloadPlatform iOS`.
- new `litertlm-main-two-prefill-turns.md` (1712 B): candidate (f) — main@16ab5491 prints two prefill turns and `parse_litert` keeps the last, so a label build's `prefill_tps` is another quantity; count the turns before comparing, pick the parser's turn before a pin bump.
- `MEMORY.md`: the four hooks above rewritten, two lines added; 10,363 → 10,611 bytes, 64 → 66 lines. The index was already over the global ≤ 10 KB before this round (other lanes' lines; not trimmed here).
- not written: (e) `git fetch` takes only a ref or a full object name — the one place this lane fetches by sha (`build_litert_lm_main.sh`) resolves short shas itself, and a hand fetch fails at once with git's message, so no session's behaviour changes; the fact is in handoff §6 (r1). (g) the `latest_session` rule — the repo records it (docstring, selftest 5b, docs). Considered and left in §6 only: the bash 3.2 apostrophe trap (`bash -n` finds it), the `cd` that moves the cwd (the Bash tool's own text says so), the keyword on-topic check (the existing `benchmark-mode-needs-a-text-check` already says to read the text).

### handoff

- `~/code/standup/handoffs/2026-10-16-D2D1-ddp-build-ref-iphone-lm.md` §6「知見」: a legend line + `### 訂正(前提 → 現物)` 31 lines, `### 罠と袋小路` 42, `### op と delegate の観察` 25 (every line: the source round first, the evidence path last) + `### §7 への追記案` 3 lines (the signing certificate's end 2026-10-26, the untried waiting path of the thermal gate, CI `bash -n` without `ios/ddp/*.sh`). §0-§5 and §7 not touched.

### litert-compat

- なし(/litert-data は回さない)。

### deleted intermediates (= `K/d2d1_deleted_paths.txt`)

- 9 paths, 31,354 files, 2,270,019,260 bytes: `ios/ddp/out/build/` (r6's derived data, 653 MB) and `ios/ddp/out/build-sim/` (r3's, 804 MB), the symlink `android/bin/v0.18.0` (its target in the main checkout untouched, 10 files), the scratchpads of the r2-r6 sessions (131 KB to 449 MB each; full xcodebuild logs, temp trees of the git index, the unzipped archive, stubs) and this round's three scratch files. The empty scratchpads of the other sessions (0 bytes) left as they are.

### kept, with the reason

- `ios/ddp/out/BenchmarkApp-ddp-xctest.zip` (46,932,194 B, sha256 490241422f3e…): the archive every retake record names (`conditions.ddp.archiveSha256`, checked again: one value in the 16 records).
- `android/bin/main-16ab54914/` (gitignored, 152,220 KiB): the files the pins entry `litert-lm.main-16ab54914` names; the only copy on this Mac. A selftest in this worktree now needs `BENCH_ANDROID_BIN_DIR` pointing at a dir with `v0.18.0/` (the main checkout's `android/bin`), since the symlink is gone.
- `ios/BenchmarkApp/Vendored/LiteRT-LM` (gitignored, 747,492 KiB; v0.18.0 + the maxNumTokens patch): needed to rebuild the archive.
- `~/.cache/apple-silicon-llm-bench/litert-lm-main-16ab54914` (clone, 1,812,172 KiB) and the bazel output base `/private/var/tmp/_bazel_USER/df8023c2…` (7,443,504 KiB): the label build's rebuild cache.
- `results/raw/*/ddp-raw/` of the four campaigns (gitignored): the pulled logs' original bytes (audit trail, the `--records-only` source).
- `results/raw/2026-10-16-ddp-iphone16pro-18-3-ios/device-jsonl-flagged/`: the quarantined first captures (audit trail).
- the three execution-level `logcat.txt` (untracked): never committed (the lab network's identifiers), kept as the `--records-only` source.
- the iOS 26.1 simulator runtime (system-wide, r3's download): Xcode 26.1.1 needs it for any iOS build; `xcrun simctl runtime delete 8DD12F84-508A-43C9-8DB5-6F025249FED6` removes it.
- bucket objects (the label's engine files, the two archives, the sessions' outputs): remote, content-addressed; the drivers delete nothing.

### git (before this round's commit)

- `git status --short`: `K/LANE.md` (the supervisor's, not staged), this round's `K/ROUND7.md`, `K/LANE_CLOSE.md`, `K/d2d1_deleted_paths.txt`, `K/r7/` (the commit), and the three execution-level `logcat.txt` of `results/raw/2026-10-16-ddp-buildref-{akita-35,m1q-36,m1q-36-b}-android/ddp/*/*/execution-*/` (untracked by rule since r2). Nothing modified, nothing staged.
- branch `build-from-ref` HEAD 424564f9 (r6's commit after its amend; was 96e088d1 before 21:09:51); origin/main d6077c6b, `git rev-list --count HEAD..origin/main` = 0 (fetch 21:4x). `origin/main..HEAD` (6), newest first:
  - 424564f9 ios/ddp: the lab harness waits before run 1 until the unit's thermal state is nominal … (r6)
  - 19c5d80d render_leaderboard.latest_session: a cell that holds version tags and labels keeps its tag rows first … (r5)
  - c57c17b8 results 2026-10-16 DDP iPhone 16 Pro (iphone16pro-18-3), LiteRT-LM v0.18.0 through the lab XCTest build … (r4)
  - a60cdb82 ios: the bench app's LiteRT-LM rows on a Developer Device Platform iPhone through XCTest, Mac side … (r3)
  - 81a86209 results 2026-10-16 DDP akita-35 / m1q-36, LiteRT-LM main@16ab54914 … (r2)
  - 0a999b8f android: build LiteRT-LM for Android from a git ref and run it on DDP by its label … (r1)
- this round adds one commit on top (the lane close record; its hash is in the report).

## Open (not decided here)

- push of `build-from-ref` + the Draft PR (`K/r5/PR_BODY.md`, `K/r5/PR_TITLE.txt`): the user's GO.
- the knowledge line in `~/code/standup/knowledge/litert.md` (the supervisor), then the assets cells: `assets.py lint` (read only, 21:4x) = `HOLD edge-llm-bench-build-ref [tool] 2/6 done` and `HOLD edge-llm-bench-ddp-ios [tool] 2/6 done` (repo hold, skill todo, article hold, knowledge todo).
- handoff §6 "§7 への追記案": the MFN25KNUGJ Apple Development certificate ends 2026-10-26 05:59:49 GMT (a rebuilt archive needs it renewed first); the thermal gate's waiting path has not run on a lab unit; CI's `bash -n` line lacks `ios/ddp/*.sh`.
- the memory index is 10,611 bytes, over the global ≤ 10 KB (it was 10,363 before this round): a trim of other lanes' hooks is a separate pass.
