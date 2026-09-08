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
- Build/run: `android/README.md` (engine acquisition, driver, campaign runner).
