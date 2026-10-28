# Pixel 11 Pro (grizzly)

- SoC: Google Tensor G6 (`ro.soc.manufacturer` Google, `ro.soc.model`
  Tensor G6; `ro.board.platform` malibu). CPU: 7 cores in three cpufreq
  policies — policy0 = cpu0-1 (2649 MHz max), policy2 = cpu2-5 (3379 MHz),
  policy6 = cpu6 (4109 MHz); `/proc/cpuinfo` reads implementer 0x41 on all
  seven, part 0xd8b on six and 0xd8c on one. No core names here: none has
  been read from a vendor source. GPU: PowerVR (`ro.hardware.egl` and
  `ro.hardware.vulkan` = powervr; `/vendor/lib64/libOpenCL.so` present).
- RAM: 16 GB (`MemTotal` 16,030,780 kB).
- Memory bandwidth ceiling: none citable — no vendor data rate or bus width
  has been read for Tensor G6, so `devices/memory-bandwidth.json` carries
  `null` and the `bw util` column renders n/a, as for the Pixel 8a.
- Storage: 462 GiB `/data` (df, KiB / 1024²), 459.1 GB free at registration
  as the job counts it (KiB / 10^6, 2026-10-27 13:29; 437.8 GiB). The whole
  weekly set runs as one session: the entry has no `split`. After the first
  sitting the bench's directory on the phone (`/data/local/tmp/llmbench`:
  the engines, the models and the caches LiteRT-LM writes beside each
  bundle) held 40.8 GB (`du -sk`, KiB / 10^6, 2026-10-27); `storage_gb_full`
  41 records it, though the job reads it only for an entry with a `split`.
  Without one the job never falls back to halves; a full disk fails the push
  (a `FAILURES.txt` line and adb's "No space left on device" in the
  sitting's log, no record) or the run (a record with its exit code) — never
  silently.
- First measured: 2026-10-27, Android 17 (SDK 37), build
  CD1A.260618.001.A7, security patch 2026-06-05; the records carry
  `device.systemVersion` / `device.securityPatch` per run.
- Access: adb over USB (serial 67170DLKX00C9J). The screen lock was set to
  none for the bench (`locksettings set-disabled true`); USB debugging must
  stay authorized.
- Power/screen policy for speed cells: USB attached and charging, as for the
  other phones; `stay_on_while_plugged_in` 15 keeps the screen on while
  powered; the screen state is read before every launch and stamped in
  `conditions.screen`. Energy cells: manual, unplugged (methodology/android.md).
- NPU: n/a. The pinned LiteRT-LM v0.18.0 README names no NPU target vendor
  (Google Tensor is not named; read 2026-10-27), and the bench's LiteRT-LM NPU
  path is the S26's Qualcomm dispatch side build. The phone carries Edge TPU
  vendor libraries (`libedgetpu_litert.so`, `libdarwinn_hal.so`, …), which no
  bench row uses.
- CPU placement: every launch on this phone runs under `taskset 7c` (cpu2-6:
  policy2's four cores and policy6's one; `cpu_mask` in
  `ops/dashboard-v1/schedule.json`), llama.cpp with the runner's `-t 4`. The
  mask was chosen on llama.cpp's anchor row. The Pixel 8a's default `f0` does not fit
  this phone (cpu4-7 = two policy2 cores, cpu6, and a cpu7 that does not
  exist). Chosen on 2026-10-27 from the weekly set's own llama.cpp anchor row
  (`unsloth/Qwen3-0.6B-GGUF` Q4_K_M short-chat, cold, 3 runs per mask, b11721,
  every run thermal nominal and uncapped), one by-hand campaign per mask in
  this order (run range = (max − min) / median):

  | mask | cores | decode tok/s (runs) | median | run range | prefill tok/s median (runs) |
  |---|---|---|---|---|---|
  | none | cpu0-6 | 83.7 / 76.1 / 83.7 | 83.7 | 9.1 % | 91.9 (78.5 / 91.9 / 120.5) |
  | `7c` | cpu2-6 | 82.0 / 85.4 / 82.6 | 82.6 | 4.1 % | 141.2 (141.2 / 50.3 / 160.6) |
  | `3c` | cpu2-5 | 67.8 / 67.4 / 68.6 | 67.8 | 1.8 % | 131.9 (81.1 / 138.0 / 131.9) |

  Records: `results/raw/2026-10-27-pixel11pro-llama-mask-{all,7c,3c}-android`.
  The medians of no mask and `7c` differ by 1.3 %, less than either mask's own
  run-to-run range; `7c` has the narrower range and keeps the threads off
  cpu0-1, so it is the setting. `3c` is the steadiest, its median 18 % under
  `7c`'s. Unlike
  the Galaxy S26 (a mask across the cluster boundary broke ggml's thread
  sync there), `7c` spans two policies here without a collapse in these
  cold short-chat runs (see Heat for the long-context cells). The short-chat
  prefill figures (a one-sentence prompt, `prompts/text/short-chat.txt`, 48
  bytes, under the model's chat template) are too noisy to rank by.
  LiteRT-LM may set its own affinity (on the Pixel 8a it widens `f0` to
  4-8); here every LiteRT-LM record's `conditions.cpusAllowedList` read 2-6,
  the launch mask (`conditions.cpuAffinity`).
- Session anchor (llama.cpp `unsloth/Qwen3-0.6B-GGUF` Q4_K_M short-chat,
  cold, n=3, under `7c`): 84.0 in the first sitting's anchor phase and 84.5
  on the payload's own anchor rows (2026-10-27, every run thermal nominal;
  ratio 1.006). The anchor phase was admitted at ratio 1.239 against its
  reference, the `3c` mask campaign (67.8): that ratio is the mask change,
  not drift (the `7c` probe read 82.6, 1.7 % under the anchor phase's 84.0;
  82.6 / 67.8 = 1.218). The set's second anchor cell
  (`matrices/anchors.cells`, LiteRT-LM GPU Qwen3-0.6B short-chat) read 30.57
  in the anchor phase (n=2: its first run, the bundle's first GPU launch on
  the phone, is left out as `firstEver`) and 30.91 (n=3) in the payload.
- Heat: in the first sitting (2026-10-27 13:46-23:33, USB, screen on) 48 of
  the payload's 120 runs are flagged cpu-capped, 30 of them with a fall past
  15 %, all on the CPU arms (litert-lm-cpu 21, llama.cpp 9; cpu-cap-rule: no
  number). llama.cpp's long-context cells of Qwen3-4B, gemma-4-E4B and
  gemma-4-E2B read 0.4-2.0 tok/s decode in 13 of their 15 runs (the gate's
  first runs counted), each with policy6's ceiling lowered: 1843 of 4109 MHz
  in 11, 2649 and 3033 in the other two; policy2's stood at 1804-2899 of
  3379 MHz in the same runs (1804 in five of them, 0.4-1.1 tok/s). The two
  E2B runs with policy6's at 3782
  and 4013 MHz read 14.4 and 18.6. The gate re-ran the two Gemma cells and
  kept the re-runs, flagged. What lowers the decode that far is not
  established.
- Build/run: `android/README.md` (engine acquisition, push, driver). The flat
  build in `/data/local/tmp/llmbench` was put on the phone on 2026-10-27 by
  `android/scripts/deploy_litert_lm_android.sh v0.18.0 <serial> --reset-caches`
  (the script's nine-file sha check passed on 2026-10-27; its output was not
  kept — the records witness the two LiteRT-LM tools' sha256 against the pin)
  and the README's llama.cpp b11721 push (witness: both tools b11721).
