# Coverage

`results/summary/device-runs.csv` has every stored run, including engines and devices added after this table was written.

**measured** = stored capture sessions in `results/raw/` today. **wired** =
the arm builds at its pinned version but has no stored captures yet. **n/a**
always carries its reason — that is part of the method, not an apology.

| engine | Mac Studio (M4 Max) | iPhone 17 Pro | Pixel 8a | Galaxy S26 | Windows laptop (Core Ultra 9 386H / RTX 5080 Laptop) |
|---|---|---|---|---|---|
| LiteRT-LM | measured | measured | measured (cpu, gpu) | measured (cpu, gpu) | measured (cpu, gpu, npu: Gemma 4 E2B; cpu, gpu: Gemma 4 E4B, Qwen3 0.6B / 1.7B / 4B; gpu on the integrated GPU too (`adapter=igpu`): all five models) |
| llama.cpp | wired | wired | measured (cpu) | measured (cpu) | measured (cpu, vulkan, cuda: Gemma 4 E2B / E4B, Qwen3 0.6B / 1.7B / 4B) |
| MLX | measured | measured | n/a — Apple-only | n/a — Apple-only | n/a — Apple-only |
| Core AI | measured (Qwen3 0.6B / 1.7B / 4B, own exports; Gemma 4 rows excluded with the reason) | measured | n/a — Apple-only | n/a — Apple-only | n/a — Apple-only |
| Cactus | n/a — no Mac arm | wired | planned | planned | n/a — no Windows arm |

- Android LiteRT NPU is n/a on both devices — the NPU path is Early Access
  only (`methodology/android.md`).
- Android llama.cpp is the official CPU release binary at the same tag as
  the Apple arm; GPU would need a custom NDK build and is a disclosed gap.
- Android v1 has no warm regime and no TTFT on llama-cli; every disclosed
  deviation is in `methodology/android.md`.
- Mac Core AI runs through the yardstick's `CoreAIRuntime` since 2026-09-08
  (the pinned `coreai-models` checkout, macOS 27 SDK): the dashboard's Qwen3
  0.6B / 1.7B / 4B rows are our own side-loaded exports, published under
  `mlboydaisuke/*-CoreAI-official` where they exist
  (`docs/dashboard-cells-v1.md`, "Core AI arm (v2)"; identities in
  `environment.lock.json`).
- The Core AI arm is best-effort for Gemma 4: PLE models need an
  unpublished engine patch (`COREAI_STATIC_INPUTS`); a clean clone reports
  `unsupported`, and the dashboard keeps those rows as `exclude=` with the
  reason. Missing exports stay visible as reasoned rows (DeepSeek-R1
  1.5B: bundle pending export).
- Cactus Android is a phase-2 slot at the pinned commit; until then the
  driver reports the row with its reason.
- Energy cells are manual by design (battery-delta needs the cable out).
