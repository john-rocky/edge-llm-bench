# 2026-11-21-dashboard-v1-m4max-qwen38-27b-s3-mac — notes

One dashboard-job sitting on the Mac Studio M4 Max (`Mac16,9`) and, inside the same Mac measurement window, the
protocol launches of the Qwen3.8-27B file published in litert-community/Qwen3.8-27B (`Qwen3.8-27B_wi4b32_32k.litertlm`,
Hub commit 392f105a) on the GPU, run by the CLI of a LiteRT-LM main 5dcf0602 build. The cells file
`matrices/qwen38-27b-main-mac.cells` gives the build, the file and the form; this is its "Sitting 3".

This sitting holds the row: 3 launches, each one process (coldRun true, firstEver false: every launch read the GPU
caches built before the first sitting's window, their sizes and times beside the model the same before and after each
launch).

| launch | start (UTC) | verdict | prefill tok/s | decode tok/s | TTFT s | resident set B | peak memory footprint B | cmux in the samples (%) |
|---|---|---|---|---|---|---|---|---|
| 1 (its retake) | 09:22:09 | retaken-clean | 206.24 | 25.82 | 5.00 | 2,879,635,456 | 3,745,287,408 | 26, 20, 19, 29 |
| 2 | 09:27:41 | clean | 205.96 | 25.81 | 5.01 | 2,896,445,440 | 3,757,165,808 | 22, 33, 20, 27 |
| 3 | 09:33:14 | clean | 176.75 | 25.46 | 5.83 | 2,888,007,680 | 3,713,961,296 | 37, 54, 41, 33, 46 |

- The row as the page reads it (`render_leaderboard.arm_row`; one call per launch, so the cold median): decode 25.81
  tok/s, spread 1.39 % (the line, `render_leaderboard.SPREAD_FLAG`, is 5 %); prefill 205.96 tok/s (arm_row reports no
  spread for prefill; its spread formula gives 14.3 %); TTFT 5.01 s; peak resident 2,754.2 MB. `scripts/cell_gate.py`'s
  COLLAPSE test on the cold decodes reads 98.6 % (its line is 50 %).
- Not counted: launch 1's first try, 09:16:33 UTC, superseded (`.json.attempt1`).
- Prefill ran at one of two levels in all 13 protocol launches of this file and build on 2026-11-21: about 206 tok/s
  (205.88-206.36, TTFT 5.00-5.01 s, decode 25.66-25.91) or about 176 tok/s (176.12-176.75, TTFT 5.83-5.85 s, decode
  25.46-25.63). The cause is not known. Per window:

  | launches | about 206 | about 176 |
  |---|---|---|
  | before the first window (16:40 local, one launch) | 1 | 0 |
  | sitting 1, 2026-11-21-dashboard-v1-m4max-qwen38-27b-mac (5 tries) | 4 | 1: launch 1, try 1 |
  | outside the windows (17:32 local, one launch) | 0 | 1 |
  | sitting 2, 2026-11-21-dashboard-v1-m4max-qwen38-27b-s2-mac (2 tries) | 1 | 1: launch 1, try 1 |
  | this sitting (4 tries) | 2 | 2: launch 1, try 1; launch 3 |

  Launch 3 of this sitting ran at the lower level with no process overlapping it in the sampler, so the level is not
  tied to a launch's place in a sitting.
- The sampler reads cmux as it reads WindowServer (`sys=`, never an overlap), as in sitting 2.
- The window opened at 18:14:58 local after 13 readings of the sampler outside it (60 s, every 5 s) showed no process
  above 30 % but cmux and WindowServer, and no Docker VM process ran. The quiet gate before each
  launch waited out its 20-21 s without 10 s free of another process above 30 %; the sampler decided each verdict.
  `pmset -g therm` before and after every try: no thermal warning recorded.
- The sitting: anchor phase `2026-11-21-dashboard-v1-m4max-qwen38-27b-s3-anchor-mac` (ADMITTED, ratio 0.993 against
  sitting 2's payload); this payload COMPLETED, ratio 0.977 against its anchor phase. `scripts/dashboard_job.py`
  `admit()` judges an anchor against the newest admitted session of the same device and engine build in the summary
  the job's own run rebuilt from disk, uncommitted dirs included: sitting 2's anchor phase was judged against sitting
  1's payload, and sitting 1's against `2026-11-15-dashboard-v1-m4max-a-mac`. `scripts/session_check.py` passes the six dirs of sittings 1-3 as one set
  (PASS 6 of 6, no finding). The job ran through the local wrapper sitting 1's NOTES describes.
- Engine: `cli/engine/` (SHA256SUMS: `litert_lm_advanced_main` 8b08c7d4b6ce…, otool -L, BUILD_INFO.txt). Every try
  registered `name=GPU WebGPU` with "Statically linked GPU accelerator registered." and allocated the KV for 2,048
  tokens (`magic_number=32771, target_number=2048`). The records stamp `engineVersion` main-5dcf06020, the tag of the
  Android side build of the same commit.
- Files: `app-path-cli/` = the four tries as schema-v1 records (`scripts/import_litert_cli.py`; three `.json`, one
  `.json.attempt1`). In `cli/`, the account name in paths reads USER and the window's lock label `<window>`.
