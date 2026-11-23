# 2026-11-21-dashboard-v1-m4max-qwen38-27b-s2-mac — notes

One dashboard-job sitting on the Mac Studio M4 Max (`Mac16,9`) and, inside the same Mac measurement window, the
protocol launches of the Qwen3.8-27B file published in litert-community/Qwen3.8-27B (`Qwen3.8-27B_wi4b32_32k.litertlm`,
Hub commit 392f105a) on the GPU, run by the CLI of a LiteRT-LM main 5dcf0602 build. The cells file
`matrices/qwen38-27b-main-mac.cells` gives the build, the file and the form; this is its "Sitting 2".

This sitting holds no number of the 27B. Docker Desktop's CLI plugin (`docker-desktop`), already running
when the window opened, overlapped both tries of the first launch at 70-84 % CPU. With 3 launches planned, the window
could then reach 2 runs at most, so it was stopped at 17:55:07 local, in the cooldown before launch 2. Sitting 3
(`2026-11-21-dashboard-v1-m4max-qwen38-27b-s3-mac`) holds the row.

| try | start (UTC) | overlapped by (sampler) | cmux in the samples (%) | verdict | prefill tok/s | decode tok/s | TTFT s |
|---|---|---|---|---|---|---|---|
| launch 1, try 1 | 08:47:41 | docker-desktop 73, 70, 84, 74, 76 % | 46, 66, 43, 30, 57 | superseded (`.json.attempt1`) | 176.12 | 25.47 | 5.85 |
| launch 1, try 2 | 08:53:17 | docker-desktop 72, 76, 80, 78 % | 24, 16, 21, 18 | overlap-twice (`.json.overlapped`) | 205.88 | 25.66 | 5.01 |

- The form, decided before this window (the cells header's "Sittings 2 and 3"): the sampler reads cmux (a terminal app
  on the Mac's screen) as it reads WindowServer (`sys=`, never an overlap), and every sample line ends with cmux's
  %cpu; NotificationCenter, Chrome, rclone and every other process still overlap. The grounds, from sitting 1: the
  four tries that cmux alone overlapped (cmux at 32-61 %) ran at prefill 205.9-206.4 tok/s and decode 25.84-25.91
  tok/s, within 0.3 % of each other and within 0.4 % of a launch before the window (206.0 / 25.81); and cmux runs at
  8-115 % whether the 27B runs or not. 3 launches, the runs of a protocol row on the Android route
  (`android/bench/run_campaign.py`: `cell["opts"].get("runs", "3")`); a launch starts only when the window still holds
  it and its retake.
- The sitting: anchor phase `2026-11-21-dashboard-v1-m4max-qwen38-27b-s2-anchor-mac` (ADMITTED, ratio 1.021 against
  sitting 1's payload: `scripts/dashboard_job.py` `admit()` judges an anchor against the newest admitted session of
  the same device and engine build in the summary the job's own run rebuilt from disk, uncommitted dirs included);
  this payload COMPLETED, ratio 0.995 against its anchor phase. Docker Desktop's CLI plugin ran through the anchor
  runs too: it was at 73.3 % CPU just before them (17:46:26 local, `cli/session.txt`) and at 73 % after them
  (17:47:41 local, launch 1's first sample). `scripts/session_check.py` passes this pair with sitting 1's dirs in the
  set. The job ran through the local wrapper sitting 1's NOTES describes.
- Both tries read the GPU caches built before the first window (sizes and times beside the model unchanged),
  registered `name=GPU WebGPU` with "Statically linked GPU accelerator registered." and allocated the KV for 2,048
  tokens. `pmset -g therm` recorded no thermal warning. Prefill's two levels across the day: sitting 3's NOTES.
- Engine and files as in sitting 1 (`cli/engine/`, `app-path-cli/`, `cli/`); in `cli/`, the account name in paths
  reads USER and the window's lock label `<window>`.
