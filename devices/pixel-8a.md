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
- Power/screen policy for speed cells: USB attached, screen on
  (`conditions.screen: "on-usb"`) — the Android counterpart of the iPhone
  plugged-speed protocol. Energy cells: manual, unplugged (methodology/android.md).
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
- Build/run: `android/README.md` (engine acquisition, driver, campaign runner).
