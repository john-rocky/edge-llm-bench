# iPhone 17 Pro

Primary iPhone reference. The newest A-series silicon at the time of
writing; sets the ceiling for what is possible on iPhone today.

| Field | Value |
|-------|-------|
| Chip | Apple A19 Pro (TBD — confirm at first measurement) |
| Neural Engine | 16-core ANE |
| RAM | TBD |
| iOS version tested | iOS 26 |
| Storage class | Internal NVMe |
| Power | Plugged in, brightness fixed (see methodology) |

## Notes

- Newest A-series silicon — sets the ceiling for what is possible on iPhone today.
- Largest RAM budget in the iPhone lineup at release — most permissive jetsam threshold.
- Apple Intelligence-capable: `PrivateFoundationModelsApple` / Apple FM
  runs through the same harness once iOS 26.x ships the relevant API.

## Build

```sh
cd ios/BenchmarkApp
./scripts/bootstrap.sh
open BenchmarkApp.xcodeproj
# set Team in Signing & Capabilities, select iPhone 17 Pro, ⌘R
```

## Results

See the runtime/model rows in [`../RESULTS.md`](../RESULTS.md) filtered to `iPhone 17 Pro`.
