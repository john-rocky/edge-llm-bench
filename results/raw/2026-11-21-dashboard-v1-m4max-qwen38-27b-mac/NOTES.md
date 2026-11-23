# 2026-11-21-dashboard-v1-m4max-qwen38-27b-mac — notes

One dashboard-job sitting on the Mac Studio M4 Max (`Mac16,9`) and, inside the same Mac measurement window, the
protocol launches of the Qwen3.8-27B file published in litert-community/Qwen3.8-27B
(`Qwen3.8-27B_wi4b32_32k.litertlm`, Hub commit 392f105a) on the GPU, run by the CLI of a LiteRT-LM main 5dcf0602
build (cells `matrices/qwen38-27b-main-mac.cells`, whose header gives the build, the file and the form).

This sitting holds no number of the 27B: all five of its tries were overlapped by another process in the 5-s sampler.
Sitting 2 (`2026-11-21-dashboard-v1-m4max-qwen38-27b-s2-mac`) holds no number either; sitting 3
(`2026-11-21-dashboard-v1-m4max-qwen38-27b-s3-mac`) holds the row, and its NOTES give prefill's two levels across the
day.

- The sitting: anchor phase `2026-11-21-dashboard-v1-m4max-qwen38-27b-anchor-mac`, payload = the platform's session
  anchor row (SESSION.json: COMPLETED, anchor nominal, ratio 0.984 vs reference). The job ran through a local wrapper
  of its own code with three calls replaced: the quiet-lock take (the window was the enclosing one), the Mac preflight
  (the job's mac_guard and hdd_gate, then scripts/doctor.py's check_common and check_mac on the shared checkout's
  yardstick and Vendored engines) and the post step (nothing was posted).
- The 27B: `app-path-cli/` = the tries as schema-v1 records (`scripts/import_litert_cli.py`), none counted (`.json.attempt1`,
  `.json.overlapped`); `cli/` = each try's console (`/usr/bin/time -l` lines and `EXIT_CODE=` at its end; `gtimeout 240`
  runs outside `/usr/bin/time`, so the "peak memory footprint" line is the CLI's own), the 5-s sampler's lines
  (`*.samp`: the processes above 30 % CPU outside the try's process tree, kernel_task and WindowServer apart as `sys=`),
  the try's meta, the verdict, `runlog.txt`, `overlap.txt`, `session.txt` and the manifest the import read.
- Plan: 4 launches, 300 s apart, one retake of a launch another process overlapped; a launch overlapped twice is no
  number. The tries:

  | try | start (UTC) | overlapped by (sampler) | verdict | prefill tok/s | decode tok/s | TTFT s |
  |---|---|---|---|---|---|---|
  | launch 1, try 1 | 08:07:03 | NotificationCenter 36 % | superseded (`.json.attempt1`) | 176.61 | 25.57 | 5.84 |
  | launch 1, try 2 | 08:12:32 | cmux 61 % | overlap-twice (`.json.overlapped`) | 205.93 | 25.91 | 5.01 |
  | launch 2, try 1 | 08:18:04 | cmux 40 %, 32 % | superseded (`.json.attempt1`) | 206.15 | 25.84 | 5.01 |
  | launch 2, try 2 | 08:23:36 | cmux 40 %, 57 % | overlap-twice (`.json.overlapped`) | 206.36 | 25.90 | 5.00 |
  | launch 3, try 1 | 08:29:04 | cmux 59 % | overlapped, no time for its retake: no record | 206.05 | 25.87 | 5.01 |

  Every try read the GPU caches built before the window (their sizes and times beside the model unchanged), registered
  `name=GPU WebGPU` with "Statically linked GPU accelerator registered." and allocated the KV for 2,048 tokens
  (`magic_number=32771, target_number=2048`).
- Engine: `cli/engine/` (SHA256SUMS: `litert_lm_advanced_main` 8b08c7d4b6ce…, otool -L, BUILD_INFO.txt). The records
  stamp `engineVersion` main-5dcf06020, the tag of the Android side build of the same commit.
- File: `Qwen3.8-27B_wi4b32_32k.litertlm`, sha256 94867fc29ccf… (the Hub's LFS sha256), on the Mac's internal disk.
- The anchor rows ran the shared checkout's yardstick (`cli/yardstick-witness.txt`).
- In `cli/`, the account name in paths reads USER and the window's lock label reads `<window>`.
