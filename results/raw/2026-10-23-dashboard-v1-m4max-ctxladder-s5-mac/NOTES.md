# 2026-10-23-dashboard-v1-m4max-ctxladder-s5-mac — notes

One dashboard-job sitting on the Mac Studio M4 Max (`Mac16,9`) and, inside the same Mac measurement window (the lane's
quiet_hold; the job took no window of its own), the context ladder of Qwen3 0.6B's all-composite export E2 on the
CPU, XNNPACK and YNNPACK, at max_num_tokens 2,048 / 8,192 / 16,384 / 32,768 (lane ctx-ladder, round r1;
cells `matrices/ctx-ladder-q06-e2-ynnpack-mac.cells`, whose header gives the build, the file and the order).
The session's plan (cli/PLAN): stages 2048 8192 16384 32768, launches 6, gap 2, retake_gap 3, gate_s 0, gate_quiet 10; 5 whole rounds (cli/ROUNDS). With gate_s above 0, every try first waited, up to gate_s seconds, until the last gate_quiet seconds held no other process above 30 % CPU (the sampler's definition); the wait and its result (quiet or timeout) are in the try's meta, and the number still rests on the sampler during the launch.

- The sitting: anchor phase `2026-10-23-dashboard-v1-m4max-ctxladder-s5-anchor-mac`, payload = the platform's session anchor row
  (SESSION.json: COMPLETED, anchor nominal, ratio 0.994 vs reference (60bd0d7880c82980f9481f8be78862e9b63c58a3)). Driver of the window: the lane's
  `job_inwindow.py` (the job's own code; its quiet-lock take, Mac preflight and post step replaced: the window was
  the lane's, the doctor and the yardstick were the shared checkout's, the post is this commit).
- The ladder: `app-path-cli/` = the CLI's launches as schema-v1 records (`scripts/import_litert_cli.py`; the Android
  route's parsers), `cli/` = each launch's console (`/usr/bin/time -l` lines and `EXIT_CODE=` at its end), the 5-s
  sampler's lines of other processes above 30 % CPU (`*.samp`), the launch's meta (argv, UTC start / end, the cache
  files beside the model before and after, `pmset -g therm` before and after), the overlap verdict, the run log, and
  the manifests the import read. A launch after the first that another process overlapped was taken once more (`*.try1.*`, record
  `.json.attempt1`); one overlapped again stands as `.json.overlapped` (no number). Launch 1 of each allocation and
  arm builds the XNNPACK weight cache beside that allocation's own clone of the model (`firstEver`; never retaken).
- Engine: `cli/engine/` (SHA256SUMS: `litert_lm_advanced_main` add87d1f24cd…, otool -L, the kit's BUILD_INFO.txt).
  The records stamp `engineVersion` head-lm2ef6baeb-rtd469ea48-xnn878f1d8c-ynn-cpuonly, the tag of the Android side build of the same sources and flags.
- File: E2, `Qwen3-0.6B_dynamic_wi4b32_afp32.gpucomposites-e2.litertlm`, one APFS clone per allocation, each sha256 fbbf0657efe9… (read at this commit).
- Launches per allocation and arm: {'2048:off': 3, '2048:on': 2, '8192:off': 5, '8192:on': 4, '16384:off': 3, '16384:on': 5, '32768:off': 2, '32768:on': 3}.
- The anchor rows ran the shared checkout's yardstick: yardstick /Users/USER/code/edge-llm-bench/.build/dd-mac/Build/Products/Release/yardstick: 45161840 bytes, modified Oct 20 15:40:41 2026 sha256 e070fc39cbdb6cd353f37b0a0620ee42f575058c89ec35c1
