# Mac — Apple M4 Max

Primary Mac reference. Fill in build / OS / RAM details before recording rows.

| Field | Value |
|-------|-------|
| Chip | Apple M4 Max (Mac Studio, `Mac16,9`) |
| GPU cores | 40 (`system_profiler SPDisplaysDataType`, read 2026-09-08 — the 16-core CPU / 40-core GPU bin) |
| Neural Engine | 16-core ANE |
| RAM | 128 GB unified |
| Memory bandwidth ceiling | 546 GB/s — Apple, Mac Studio (2025) Tech Specs (support.apple.com/en-us/122211) for the 16-core CPU / 40-core GPU M4 Max; the 14/32 bin is 410 GB/s. Registry: `devices/memory-bandwidth.json` (the `bw util` column) |
| macOS version tested | macOS 27.0 (the dashboard sessions; earlier rows macOS 26) |
| Storage class | internal SSD |
| Power | Plugged in, "High Power" mode |

## Notes

- Sets the upper bound for what Apple Silicon can do on a workstation today.
- GPU-rich: MLX (GPU path) vs CoreML (ANE path) split here is the widest in the lineup — the README headline `5.3× MLX over CoreML` decode number for Gemma 4 E2B was taken on this class of machine.
- Thermal headroom is large; sustained-decode runs rarely throttle.

## Build

For now, run via the iOS BenchmarkApp on a connected iPhone, or wait for the Phase-2 macOS app target (tracked in [`../README.md`](../README.md#roadmap)).

## Results

See the runtime/model rows in [`../RESULTS.md`](../RESULTS.md) filtered to `Apple M4 Max`.
