# Galaxy S26 (SM-S942Q)

- SoC: Qualcomm Snapdragon SM8850 (Adreno GPU) — the flagship counterpart to
  the Pixel 8a's mid-range Tensor G3. Never pool or average rows across the
  two devices (same-device-class rule); each carries its own anchors.
- CPU topology (read on-device 2026-08-25): cpu0-5 @ 3.63 GHz (performance)
  + cpu6-7 @ 4.74 GHz (prime). The lane's standard `taskset f0` mask lands on
  cpu4-7 = 2 performance + 2 prime here (on Pixel 8a it means the 4 mid
  cores) — the mask is recorded per run in `conditions.cpuAffinity`, so rows
  stay comparable within the device either way.
- RAM: 12 GB
- Memory bandwidth ceiling (for the `bw util` column): 84.8 GB/s, derived
  from Qualcomm's product brief ("Support for LP-DDR5x memory, up to
  5300MHz" = 10.6 Gbps per pin × 64-bit ÷ 8); the brief states the clock,
  not GB/s, and the phone's DRAM may run below the SoC maximum —
  `devices/memory-bandwidth.json`, `basis: derived-from-vendor-spec`, rendered
  with a `~`.
- First measured: 2026-08-25 (this repo's first flagship Android row space);
  Android version + security patch are recorded per run in the JSON
  (`device.systemVersion` / `device.securityPatch`).
- Access: adb over USB, serial RFGL80R6A6H. USB debugging authorized.
- Power/screen policy for speed cells: USB attached; the screen state is read
  from the phone before every launch and stamped in `conditions.screen`
  (`on-usb` / `off-usb (mWakefulness=…)`); on and off are both admissible for
  the speed cells (the display is not used); the anchor decides the session —
  same protocol as pixel-8a.md. Until 2026-09-26 the runners wrote a fixed
  `on-usb` (rows without `conditions.screenSource`; `Awake` / `Dozing` there
  are sitting-mode readings). Energy cells: manual, unplugged
  (methodology/android.md).
- NPU and GPU: a Hexagon v81 NPU (llama.cpp's log: `Hexagon Arch version v81`)
  and an Adreno 840 GPU (OpenCL 3.0). Since 2026-10-07 two llama.cpp arms run
  on them, `llama.cpp-npu` (`--device HTP0`) and `llama.cpp-gpu`
  (`--device GPUOpenCL`), from llama.cpp's official Snapdragon release asset
  as a side build (`b11469-snapdragon`, in
  `/data/local/tmp/llmbench/engines/b11469-snapdragon/`) with the official
  wrapper's settings; a launch counts only when the engine's own lines show
  the device. LiteRT-LM on the NPU (`litert-lm-npu`) needs a runtime built
  with the Qualcomm dispatch libraries and a bundle compiled for SM8850: this
  repo has one, its own export of Qwen3 0.6B (KV cache fixed at 1,024
  tokens), run on its own build of `litert_lm_advanced_main` (LiteRT-LM main
  of 2026-08-21, QAIRT 2.47 libraries, V81 skel) with the hardware KV-cache
  update off; since 2026-10-08 the runner drives it as a side build
  (`main-20260821-selfbuilt`, flat in
  `/data/local/tmp/llmbench/engines/main-20260821-selfbuilt/`, the skel in
  `dsp/`), a launch counting only when the engine's lines show the NPU chosen,
  registered and dispatched to. The binary itself has no host copy: on this
  phone it is `/data/local/tmp/litertlm_npu/litert_lm_advanced_main`, which
  the build's directory takes a copy of. The LiteRT-LM cpu/gpu rows are
  unchanged. The NPU and GPU arms' memory columns read the host process only
  — the HTP0 / OpenCL / NPU buffers sit outside VmRSS. Details, settings and
  the disclosures: `docs/dashboard-cells-v1.md` "NPU and Android GPU rows" and
  "LiteRT-LM on the NPU".
- CPU affinity choice: **this device runs unmasked** (`BENCH_CPU_MASK=`,
  recorded per run as `conditions.cpuAffinity: none`). The lane's default
  `taskset f0` was tuned on the Pixel 8a's four contiguous mid cores; here it
  spans the perf/prime cluster boundary and collapses ggml's thread sync —
  llama.cpp Qwen3-0.6B measured 15.0 tok/s under f0 vs 105.6 unmasked on the
  same binary (six probes:
  `results/raw/2026-08-25-s26-llama-affinity-probes/NOTES.md`). The
  2026-08-25-s26-first-session llama rows were captured under f0 and are
  superseded by 2026-08-25-s26-llama-nomask (Qwen3-0.6B ~104, DeepSeek-R1
  ~47 tok/s, all nominal); they stay in raw with their conditions recorded.
  litert-lm cells are unaffected (litert_lm_main manages its own threads).
- CPU-frequency caps are transient, not a standing state of this phone: while
  another lane's benchmark loaded it, `scaling_max_freq` read 42–55% of
  `cpuinfo_max_freq` (policy0 2.0/3.6 GHz, policy6 1.98/4.74 GHz; 2026-09-07
  18:11, battery 100% on USB), and at idle the caps were gone (2026-09-08 06:39,
  before the first automated dashboard session). The dashboard job's preflight
  reads a cap as "busy" and polls — the right reading; do not measure under one.
- What sets the cap (a diagnosis on 2026-10-08: five llama-bench loads of
  Qwen3 0.6B, USB attached, screen dozing; standup ROUND-r6 of the NPU rows
  lane): the SoC's temperature, not the skin sensor or charging. Both
  clusters' step-down began at AP sensor readings of 46-51 °C (the two loads
  that read the AP; the CPU load's earlier policy6 dips, at 31-44 °C, are not
  explained) while the skin sensor read 29-38 °C (under its first threshold,
  38.0 °C) and `Thermal Status` stayed 0, and loads capped alike charging
  (`dumpsys battery` status 2) and not (status 4) — no phone setting removes
  it. The load sets the speed and the order, not the depth: a CPU load
  (llama.cpp on cpu6-7 and about two of cpu0-5) took policy6 down 1.1-2.1 s
  in and policy0 8.1-10.7 s in; an NPU load (the HTP0 side build: cpu0-5
  busy, cpu6-7 idle) took both together 9-16 s in; four of the five loads
  reached 2227 / 2227 MHz (38.6 / 53.0 % below the maxima). At rest the cap
  lifted 12-37 s after the load and did not return during the rests (60 s to
  5 min). `dumpsys thermalservice`'s "Cached temperatures" kept SKIN at
  37.9 °C through all 27 reads while "Current temperatures from HAL" moved
  between 28.9 and 37.9 °C: read the HAL's current values. Because the cap is
  the phone's, the NPU and GPU arms count a capped run (cpu-cap-rule,
  `methodology/fairness-rules.md` §13); the CPU arms keep the 15 % line.
- Build/run: `android/README.md` (engine acquisition, driver, campaign runner).
