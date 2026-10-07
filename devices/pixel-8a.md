# Pixel 8a (akita)

- SoC: Google Tensor G3 (1× Cortex-X3 + 4× A715 + 4× A510; Mali-G715 GPU)
- RAM: 8 GB (Google's spec sheet: "8 GB LPDDR5X")
- Memory bandwidth ceiling: none citable — Google publishes no data rate or
  bus width, and TechInsights' Tensor G3 floorplan analysis identifies a
  Micron LPDDR5 (not 5X) part on the Pixel 8 package, so even the memory
  generation is contested. `devices/memory-bandwidth.json` carries `null`
  and the `bw util` column renders n/a on this device rather than a guess.
- First measured: 2026-08 (Android lane v1); Android version + security patch
  are recorded per run in the JSON (`device.systemVersion` /
  `device.securityPatch`) — the OS moves under a long campaign, the records
  carry the truth.
- Access: adb over USB. USB debugging must be authorized (the on-device dialog
  reappears after revocation); keep the screen unlocked for the first connect.
- Power/screen policy for speed cells: USB attached (the Android counterpart
  of the iPhone plugged-speed protocol); the screen state is read from the
  phone before every launch and stamped in `conditions.screen` (`on-usb` /
  `off-usb (mWakefulness=…)`); on and off are both admissible for the speed
  cells (the display is not used); the anchor decides the session. Until
  2026-09-26 the runners wrote a fixed `on-usb` (rows without
  `conditions.screenSource`; `Awake` / `Dozing` there are sitting-mode
  readings). Energy cells: manual, unplugged (methodology/android.md).
- NPU: not reachable (LiteRT NPU path is Early Access Program only) — LiteRT
  rows are cpu/gpu; the NPU row stays n/a with that reason.
- Session anchor (llama.cpp `unsloth/Qwen3-0.6B-GGUF` Q4_K_M, cold, n=3) is
  unsteady on this phone: its median moved 22-37 tok/s between the halves of
  one sitting with every run at thermal nominal (2026-09-08: probe 22.6,
  a 23.1, b1 37.1, b2 27.2; runs 20.3-37.5) and 27.3-28.3 on 2026-09-05
  (runs 22.5-34.9). The admission rule's 0.5 collapse bar absorbs this and
  every half was admitted; the ratio it records is the anchor's own noise,
  not device drift — 13 of the other 14 cells reproduced their 2026-09-05
  median within 10% on 2026-09-08. Regenerate the figures from
  `results/summary/device-runs.csv` (campaign `*-dashboard-v1-pixel8a-*`).
- Memory, not only storage, moves this phone's numbers: llama.cpp Gemma 4 E4B
  (Q4_K_M) declares about 8 GB of buffers here (4.7 GB weights + 2.6 GB CPU
  repack) on 7.5 GB of RAM. It read 5.0 tok/s on every cold run on
  2026-09-05, then about 5 on the first run and 0.9-1.6 on every later run on
  2026-09-08 and 2026-09-09 (13 h uptime, 1 GB of swap in use, 2.5 GB of
  resident user apps; engine, OS, recipe, thermal state unchanged), and
  5.1 / 5.0 / 5.4 nine minutes after a reboot plus `am kill-all`. The
  dashboard job therefore reboots this phone before a sitting when its
  uptime is over 2 h (`reboot_before` in `ops/dashboard-v1/schedule.json`)
  and logs uptime / MemAvailable / swap in use before and after; the cell
  gate flags the shape either way (COLLAPSE on the median, LEVEL on a
  uniformly slow re-run). Mechanism unmeasured; the reboot is the remedy
  that was tested.
- CPU placement differs by engine, by design. Cores: cpu0-3 Cortex-A510
  (cpufreq policy0, 1704 MHz), cpu4-7 Cortex-A715 (policy4, 2367 MHz), cpu8
  Cortex-X3 (policy8, 2914 MHz). llama.cpp runs where the runner puts it:
  `taskset f0` + `-t 4`, the four A715 cores (the runner's setting, tuned on
  this phone). LiteRT-LM sets its own affinity to cpu4-8 on the Tensor G3
  (A715 x4 + X3; `kTensorAffinities` in LiteRT-LM's
  `runtime/engine/cpu_affinity_utils.cc`, read at v0.14.0-alpha.0-90):
  launched under `taskset f0`, the v0.16.0 CPU engine widened to 4-8 within a
  second and the GPU engine read 4-8 from the first sample (2026-10-07). Rows
  compare each engine at its own placement, not an equalized one: widening
  llama.cpp's mask changes the tuned setting (on the Galaxy S26 a mask across
  the cluster boundary broke ggml's thread sync: 15 tok/s masked, 105.6
  unmasked, `run_cell.py` CPU_MASK), and the runner's mask does not hold
  LiteRT-LM's own choice. Records say both: `conditions.cpuAffinity` is the
  launch mask, `conditions.cpusAllowedList` the engine's `Cpus_allowed_list`
  read during the run (since 2026-10-07). While the phone charges, policy4 can
  sit below 2367 MHz mid-run with the thermal status at 0; such runs are
  flagged and pool into no number (`methodology/fairness-rules.md` §13
  cpu-cap-rule).
- Build/run: `android/README.md` (engine acquisition, driver, campaign runner).
