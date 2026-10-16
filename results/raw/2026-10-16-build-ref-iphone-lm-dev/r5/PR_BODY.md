## Build LiteRT-LM for Android from a git ref and run it on DDP

`android/scripts/build_litert_lm_main.sh` builds a commit, a branch or a pull request's head as well as a tag, into `android/bin/<label>/` (both tools, the GPU `.so` set, `SHA256SUMS`, `BUILD_INFO`), and `android/scripts/pins_add.py` registers the build in `android/engine-pins.json` under its label (`main-<sha9>`, `<branch>-<sha9>` or `pr<N>-<sha9>`). `android_pins` is not changed.
```bash
LITERTLM_REF=pr/<N> android/scripts/build_litert_lm_main.sh    # -> android/bin/pr<N>-<sha9>/; LITERTLM_DRY_RUN=1 prints the label, commit and commands
android/scripts/pins_add.py <label> <dir>/<label>              # a build made elsewhere: its 9 files in <dir>/<label>/
BENCH_ANDROID_BIN_DIR=<dir> ./bench matrix <cells> --ddp <id> --engine-build <label> --project <p> --bucket gs://<b>
```
- `pins_add.py` refuses a missing tool, a directory without a `.so`, a git-lfs pointer file and an existing label (without `--replace`), and keeps every other key byte for byte. With `--engine-build`, every job pushes that entry's files after checking them, and its records stamp `engineVersion` `<label>`.
- `android/ddp/selftest.py` section 1d (17 checks); CI's py_compile line covers `android/scripts/pins_add.py`. Docs: `android/README.md` ("Build from head or a PR"), `docs/ddp-integration.md`, `docs/OPERATIONS.md`, `README.md`.

## The LiteRT-LM rows on a DDP iPhone (`ios/ddp`)

- `ios/BenchmarkApp/project-ddp.yml` (xcodegen → `BenchmarkApp-ddp.xcodeproj`): a lab build of the bench app with the LiteRT-LM arm only (v0.18.0, iOS 18.0 floor) and an XCTest target. The test reads `Documents/yardstick_args.json` and runs the app's own headless path (`--yardstick-autorun`) in the app's process, so the records are the app's schema-v1 records. `Sources/BenchmarkApp.swift` changes by +24 / −1 (the view's run methods move unchanged into `HeadlessRun`); the three existing projects are not touched.
- `ios/ddp/build_xctest.sh` builds the `build-for-testing` Release archive (products, `.xctestrun`, `BUILD_INFO`).
- `ios/ddp/run_ddp_ios_lm.py` submits one `gcloud beta device-run sessions submit xctest` session per cell, pushes the model from the bucket, pulls `Documents/results` and `Documents/out`, and writes the records to `results/raw/<campaign>/device-jsonl/` with `device.ddp` and `conditions.ddp`. It has `--dry-run`, `--collect` and `--records-only`.
- `ios/ddp/selftest.py`: 66 checks, no device, no network; CI's py_compile line covers `ios/ddp/*.py`.
```bash
ios/ddp/run_ddp_ios_lm.py --device iphone16pro-18-3 --model-id litert-community/Qwen3-1.7B --backend gpu --dry-run
```

## A label's rows never take a standing cell

- `render_leaderboard.latest_session` now keeps only the version-tag rows of a cell that holds both version tags and labels, then picks the newest tag's session as before; a cell with labels only keeps timestamp order.
- The leaderboard and the dashboard read every cell through `arm_row`, so a `--engine-build` run stays in `results/summary/` and does not replace the pinned tag's session.
- `android/ddp/selftest.py` section 5b checks three cases through `latest_session`, `arm_row` and `render_dashboard.build`; the file has 96 checks (76 on main).

## Sessions in this branch

All sessions PASSED. The summary was rebuilt from the git index.
- `results/raw/2026-10-16-ddp-buildref-akita-35-android/`: `session-733dfb76` on akita-35 (Pixel 8a), Qwen3-1.7B GPU short chat, 3 runs, `engineVersion` `main-16ab54914` (LiteRT-LM main at 16ab5491492f).
- `results/raw/2026-10-16-ddp-buildref-m1q-36-android/`: `session-0214b9f1` on m1q-36 (SM-S942U1), the same cell and build.
- `results/raw/2026-10-16-ddp-buildref-m1q-36-b-android/`: `session-4b77de16` on m1q-36, the same cell and build on another unit.
- `results/raw/2026-10-16-ddp-iphone16pro-18-3-ios/`: four sessions on iphone16pro-18-3 (iPhone 16 Pro, iOS 18.3.2), LiteRT-LM v0.18.0, short chat, 4 runs each: `session-70a0e2dc-9c0f-4232-babf-77a7c15ceb49` (Qwen3-1.7B GPU), `session-71bd2279-fb3e-4bd8-8a61-c6583dad3bf5` (Qwen3-1.7B int8 CPU), `session-2af96355-979f-444b-a3ba-9259d5863dd4` (Gemma 4 E2B GPU), `session-869a5c6a-46ff-45c5-83a8-6d511476e383` (Gemma 4 E2B CPU). The attached-iPhone runner's thermal gate (`scripts/cell_gate.py`) calls all four first captures HOT, so their 16 records are in `device-jsonl-flagged/` with `FLAGGED.txt` and not in the summary.

## Known limits

- The iPhone archive is signed with the attached bench app's App ID, whose profile carries the two memory entitlements; a dedicated App ID needs the Apple account in Xcode. The lab re-signs the app, and whether the entitlements survive is not visible in the outputs (the 2.59 GB Gemma 4 E2B file loaded and ran on GPU and CPU).
- `environment.lock.json` has no iOS v0.18.0 entry; the attached iPhone rows are v0.16.0.
- LiteRT-LM main at 16ab5491492f prints two prefill turns per run in its BenchmarkInfo: 19 tokens, then the printed reply's token count plus 3. `android/bench/parsers.py` (unchanged) keeps the last turn's rate, so `promptTokensPerSecond` of the `main-16ab54914` records is the second turn's. What that turn prefills is not in the log.
