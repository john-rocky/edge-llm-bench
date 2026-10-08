# 2026-10-08-dashboard-executorch-v1-iphone18pro-ios — notes

Hand-run sitting of the ExecuTorch arm's iPhone rows (`matrices/dashboard-executorch-v1-ios.cells`:
Qwen3 0.6B / 1.7B / 4B own exports x `short-chat` and `long-context-1024-gen256`, runs=4 = run 1
cold, runs 2-4 warm; the four Gemma 4 rows are excluded in the cells file and logged to
SKIPPED.txt) on the **iPhone 18 Pro** (iPhone19,2, iOS 27.2 24B5099f, devicectl
`C7A74909-7573-5A0F-9201-F7D03DC811EF`, UDID `00008160-000038CA02C00036`, USB, charging, battery
80 %), app `com.example.CoreMLLLMChat` "iOS LLM Bench" 0.2.0 built from
`ios/BenchmarkApp/project-executorch.yml` (the ExecuTorch build of the app, Release). Engine
stamped in the records: ExecuTorch `v1.5.0` (the prebuilt `swiftpm-1.5.0` xcframeworks at
56cc93a96d5f; there is no 1.5.1 Swift package) running the ExecuTorch 1.5.1 own exports
(docs/executorch-arm-v1.md, "iPhone"). Not a dashboard-job sitting: no SESSION.json, no admission
(first records of this arm on this phone).

The models were side-loaded over USB (15:53-15:56 JST) into the app container,
`Documents/models/executorch/own-export__<model>/`: the `.pte` and Qwen3's `tokenizer.json`.
Byte sizes on the phone equal the host files, whose sha256 equal the recipes' (`pte_sha256`
0.6B `2517e337…`, 1.7B `76b68b2c…`, 4B `3eaddfbb…`; tokenizer `aeb13307…`).

Command: `CAMPAIGN=2026-10-08-dashboard-executorch-v1-iphone18pro-ios
scripts/bench_matrix_iphone.sh run matrices/dashboard-executorch-v1-ios.cells` (RUNS 4,
BASE_COOLDOWN 100 with the cells' cooldown=300 on the 4B rows, THERMAL_COOLDOWN 240,
SERIOUS_COOLDOWN 600, CELL_TIMEOUT 3600 defaults). Device hold 15:50:53-16:58:07 JST, runner
16:18:09-16:57:38 on the Release build.

1. Debug build, quarantined. A first launch (16:02:06-16:02:16, the 0.6B `short-chat` row alone,
   its cells file holding that row verbatim) ran on a **Debug** build of the app: its four records
   say `device.buildConfiguration` "Debug" (the generated scheme's Run action defaults to Debug).
   Under same-build-config they were moved to device-jsonl-flagged/ (FLAGGED.txt), the app was
   rebuilt Release and reinstalled (16:17), and the whole cells file ran from 16:18:09; every kept
   record says "Release". The Debug runs are the first four runs of the 0.6B `short-chat` console
   file.
2. Within-cell decode decline. In four of the six cells decode fell from run to run inside one
   capture, the thermal label mostly staying `nominal`; the capture gate flagged the first
   capture, the runner cooled 240 s and re-ran once, and the retry fell the same way and was
   kept with a GATE_FAIL line (FLAGGED.txt). Decode of runs 1-4 (tok/s), first capture -> kept
   retry:
   - 0.6B `long-context-1024-gen256`: 89.92 / 82.97 / 79.65 / 76.92 (SPREAD 7.6) -> 81.20 / 75.92 /
     72.74 / 69.91 (SPREAD 8.3).
   - 1.7B `long-context-1024-gen256`: 45.30 / 41.72 / 38.97 / 36.27 (SPREAD 14.0) -> 43.94 / 40.61
     / 37.98 / 35.81 (SPREAD 12.6; run 4 ended `fair`).
   - 4B `short-chat`: 31.96 / 28.71 / 27.59 / 26.64 (SPREAD 7.5) -> 32.17 / 29.04 / 27.78 / 26.78
     (SPREAD 8.1).
   - 4B `long-context-1024-gen256`: 20.64 / 17.64 / 16.38 / 14.44 (HOT nominal,nominal,fair,fair;
     run 4 ended `serious`) -> 19.53 / 17.20 / 13.38 / 13.25 (HOT fair,fair,fair,serious). The
     gate reads the runs' initial thermal states only, so the capture that ended `serious` was
     retried after THERMAL_COOLDOWN (240 s), not SERIOUS_COOLDOWN, and the retry started `fair`.
   The 0.6B and 1.7B `short-chat` cells passed (warm spread 0.58 % and 4.44 %).
3. Prompt tokens: the records' `promptTokenCount` is the host tokenizer's count for the rendered
   prompt (19 `short-chat`, 1,338 `long-context-1024-gen256`; `YARDSTICK_NOTE executorch` line of
   every run). The C++ runner's own `PyTorchObserver` line, printed to the same console, reports
   the same counts on the phone for every run.
4. Record file names are UTC seconds. A 0.6B `short-chat` run lasts about 0.94 s; every capture
   still wrote four distinct files (no overwrite). The phone's `Documents/results` holds the same
   44 executorch files as device-jsonl/ (24) + device-jsonl-flagged/ (20).
5. Cross-check from the stored files: every record (24 kept, 20 flagged) equals its run's
   `YARDSTICK_RUN_OK` console line. Against the `PyTorchObserver` line of the same run (the C++
   runner's integer-ms windows, docs/executorch-arm-v1.md "iPhone") the kept records' decode
   differs by at most 0.13 %, prefill by at most 0.76 % and TTFT by -1 to +3 ms, and its prompt /
   generated token counts equal the records' (19 / 127 and 1,338 / 255). Within each cell every
   run (first capture, retry, and for 0.6B `short-chat` the Debug capture) generated the same text,
   byte for byte (greedy; the runner is reset before every run; stop reason `length`), and
   `android/bench/parsers.text_integrity` passes on the full streamed text in the console and on
   the record's 200-character `outputSample`.
