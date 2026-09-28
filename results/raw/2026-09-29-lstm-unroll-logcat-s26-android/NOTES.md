# 2026-09-29 LiteRT #10300: full-buffer logcat around the unrolled-LSTM SIGSEGV (Galaxy S26, Adreno, OpenCL)

**Question.** In google-ai-edge/LiteRT#10300
(https://github.com/google-ai-edge/LiteRT/issues/10300) the 2.2.0 GPU accelerator's
`CompiledModel` creation dies with SIGSEGV inside the vendor OpenCL driver once an unrolled
LSTM passes ~85 sequential steps (T=84 compiles, T=88 faults). On 2026-09-28 the LiteRT side
asked for (1) the complete logcat sequence from the seconds leading up to the SIGSEGV, to look
for driver-level resource limits, out-of-memory alerts or compilation warnings printed by the
vendor driver, and (2) whether any configuration options beyond the reported ones are applied
to `GpuOptions` during `CompiledModel` creation. The 2026-09-26 sweep behind the issue kept
only a pid-filtered logcat and the crash buffer's tombstone, so the fault was re-run here with
every logcat buffer cleared before each launch and dumped after it.

**Answer.**

1. In the three faulting launches (T=88 with FP32 precision twice, T=88 with the runtime's
   default precision once) no process writes a driver warning, an out-of-memory line or a
   resource-limit line into any logcat buffer between the runner's start and the fault. The
   runner's last line is always `delegate_kernel.cc:911 Initializing OpenCL-based API from
   graph.`; 257–277 ms later comes `Fatal signal 11 (SIGSEGV) … fault addr 0x4f`, then the
   tombstone. The only vendor-driver lines in the windows are the runner's own `AdrenoGLES-0`
   banner at process start (driver 0842.19.8, build 87ff20b216) and, in the tombstone, the
   frames `libCB.so cb_enqueue_nd_range_kernel+1780` ← `libOpenCL_adreno.so
   qCLDrvAPI_clEnqueueNDRangeKernel+180` ← `libLiteRtClGlAccelerator.so`. The 25-frame
   backtrace (pc offsets and libraries) is identical in all three launches and identical to the
   2026-09-26 tombstone in the issue. The passing T=84 launches print the same lines up to
   `Initializing OpenCL-based API from graph.` and then `DestroyAccelerator` at exit; nothing
   else differs on the system side (thermal service, DVFS hints, performance HAL, adbd).
2. The runner adds nothing to `GpuOptions` beyond FP32 precision. Its options are exactly:
   `LiteRtCreateOptions`; `LiteRtSetOptionsHardwareAccelerators(kLiteRtHwAcceleratorGpu)`;
   one opaque option `runtime_options_string` = `enable_profiling = false` +
   `error_reporter_mode = 1`; one opaque option `gpu_options` = `precision = 2`
   (`android/round12/gpu_runner.cc` lines 379–387 of the 2026-09-26 run directory, sha256 in
   PROVENANCE.md). With the `gpu_options` payload omitted entirely (runner mode `default`) T=88
   faults the same way at the same pc; the delegate then logs `options->kernel_batch_size: 0`
   instead of `-1`, and `hint_waiting_for_completion: false` in both cases.

## Launches (device clock, JST; one process each; all buffers cleared 6 s before each start)

| launch | graph | runner mode | runner pid | started | exit | last runner line before the fault / result | fault | window lines (kept / redacted) | battery °C |
|---|---|---|---:|---|---:|---|---|---:|---:|
| `smoke-t84-fp32` | `lstm_h128_t84_uni_fp32` | `single` | 28975 | 07:57:04.295 | 0 | compiles (330 ms), runs; peak RSS 155 MB | — | 1110 (88 / 1022) | 29.6 → 29.6 |
| `t88-fp32-1` | `lstm_h128_t88_uni_fp32` | `single` | 29338 | 08:01:59.833 | 139 | `delegate_kernel.cc:911 Initializing OpenCL-based API from graph.` | SIGSEGV at 08:02:00.229, fault addr 0x4f; RSS 12.8 MB | 403 (140 / 263) | 29.8 → 29.8 |
| `t88-fp32-2` | `lstm_h128_t88_uni_fp32` | `single` | 29457 | 08:02:55.724 | 139 | `delegate_kernel.cc:911 Initializing OpenCL-based API from graph.` | SIGSEGV at 08:02:56.122, fault addr 0x4f; RSS 13.2 MB | 256 (135 / 121) | 29.8 → 29.8 |
| `t84-fp32-1` | `lstm_h128_t84_uni_fp32` | `single` | 29581 | 08:03:51.671 | 0 | compiles (320 ms), runs; peak RSS 154 MB | — | 205 (75 / 130) | 29.9 → 29.9 |
| `t88-default-1` | `lstm_h128_t88_uni_fp32` | `default` | 29671 | 08:04:47.689 | 139 | `delegate_kernel.cc:911 Initializing OpenCL-based API from graph.` | SIGSEGV at 08:04:48.070, fault addr 0x4f; RSS 12.8 MB | 179 (127 / 52) | 29.9 → 29.8 |

Runner mode `single` = `gpu_options` `precision = 2` (FP32), 1 repetition, 0 warm-ups: the
mode of the 2026-09-26 sweep (the tombstone in the issue shows `single 1 0` in its Cmdline).
Mode `fp32` passes the same options and differs only after creation (5 repetitions, 2
warm-ups), so it was not re-run. Mode `default` passes no `gpu_options` payload. `window
lines` = every line of every buffer between 5 s before the runner started and the end of its
tombstone (or 1 s after its exit); `kept` / `redacted` = what `logs/<launch>.window.txt`
carries and what it drops (below). `RSS` = the runner's own `/proc/self/status` VmHWM sample
written to `run.json` just before `LiteRtCreateCompiledModel` (the last sample a faulting run
writes). `battery °C` = `dumpsys battery` before → after the launch. The delegate selected
2278/2278 (T=88) and 2174/2174 (T=84) nodes into 1 partition in every launch (runner stderr).

## Instrument

`capture.py` (this directory): per launch, hold check → foreign-process check → `dumpsys
battery` → sha256 re-check of the pushed files → `logcat -c -b all` → `logcat -g` → wait 6 s →
device `date` → `adb shell "env LD_LIBRARY_PATH=/data/local/tmp/litert10300
/data/local/tmp/litert10300/gpu_runner <graph> <inputs> <out> <mode> 1 0 /data/local/tmp/litert10300
<manifest> 900; echo ##EXIT=$?"` with stdout / stderr to `logs/<launch>.runner.{stdout,stderr}.log`
→ device `date` → 3 s → `logcat -b all -d -v threadtime -v uid` → pull the runner's `run.json` /
`memory.json` → `dumpsys battery`. Every command with its timestamp and exit code is in
`logs/commands.log` (`### CMD:` lines; the Mac home directory is written as `/Users/USER`).
`scrub_window.py` cuts the public window. The runner, its two runtime libraries, the two
graphs and the input packs are the 2026-09-26 files (PROVENANCE.md); nothing was rebuilt.
The device was `svc power stayon usb` for the session (screen awake and locked, as the
2026-09-26 driver set per launch) and restored to `false` at teardown; the remote directory
was removed and its absence verified. The 45 s pauses between launches and the battery gate
are this session's; the 2026-09-26 sweep ran its 13 graphs back to back (about 4 s apart) and
recorded the battery without gating on it.

Buffers on this phone (`logcat -g`): main 5 MiB, system 2 MiB, crash 512 KiB, kernel 4 MiB
(0 B readable for the shell user); `-b all` also returns radio and events. After a clear, a
window of 5–6 s held 264–1,658 lines across all buffers, far below the ring sizes, so nothing
in the window was overwritten.

## Files

- `logs/<launch>.window.txt` — the public window, verbatim lines. Kept: every line of the
  runner's pid; the tombstone (`DEBUG`, from `crash_dump64`) and the crash pipeline
  (`crash_dump64`, `tombstoned`); system lines whose tag names the GPU driver, memory
  pressure, thermal state, DVFS / performance HAL or the graphics allocator; any line naming
  the runner. Dropped and counted in the file's header (`redacted: N lines from unrelated
  apps/services`): SystemUI / lock-screen / wallpaper, telephony, sensors, audio, video codecs,
  Wi-Fi, Bluetooth, package/config persistence — a personal phone's traffic. Every dropped
  line of every window was read once (grouped by tag and message) before the rule was fixed;
  none names the GPU, the driver, memory pressure or the runner. `grep -c -i -E
  'majimadaisuke|/Users/|RFGL80R6A6H|@gmail'` is 0 on every public file (`logs/commands.log`
  carries the adb serial, as the earlier records in this repository do).
- `logs/<launch>.runner.stderr.log` / `.stdout.log` — the runner's own output (LiteRT INFO /
  VERBOSE lines, `Segmentation fault`, `##EXIT=<code>`).
- `logs/<launch>.runner.run.json` / `.runner.memory.json` — the runner's report pulled from the
  phone (options as written by the runner, pid, stage, RSS samples).
- `run.json` — per-launch metadata (device props, pushed-file sha256, device clock at clear /
  start / end, exit codes, window bounds and counts, battery), written by `capture.py`.
- `private/` (not committed, `.gitignore`) — the full `-b all` dumps, the unscrubbed windows
  and the pulled output directories; kept on disk as audit trail.
- `gpu_runner.cc` — verbatim copy of the runner's source (the 2026-09-26 `android/round12/gpu_runner.cc`); the
  options it passes are lines 379–387.
- `SHA256SUMS` — the pushed files (as on the phone), the public logs and the scripts.

Next: a comment on #10300 with the window excerpt and the options answer, after the owner's go.

This directory holds no JSONL, so `scripts/build_summary.py` does not read it.
