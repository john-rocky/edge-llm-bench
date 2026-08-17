# Mac — Apple M4 Max

Primary Mac reference. Fill in build / OS / RAM details before recording rows.

| Field | Value |
|-------|-------|
| Chip | Apple M4 Max |
| GPU cores | TBD (32 or 40, depending on bin) |
| Neural Engine | 16-core ANE |
| RAM | TBD |
| macOS version tested | macOS 26 |
| Storage class | TBD (internal SSD) |
| Power | Plugged in, "High Power" mode |

## Notes

- Sets the upper bound for what Apple Silicon can do on a workstation today.
- GPU-rich: MLX (GPU path) vs CoreML (ANE path) split here is the widest in the lineup — the README headline `5.3× MLX over CoreML` decode number for Gemma 4 E2B was taken on this class of machine.
- Thermal headroom is large; sustained-decode runs rarely throttle.

## Build

For now, run via the iOS BenchmarkApp on a connected iPhone, or wait for the Phase-2 macOS app target (tracked in [`../README.md`](../README.md#roadmap)).

## Results

See the runtime/model rows in [`../RESULTS.md`](../RESULTS.md) filtered to `Apple M4 Max`.
