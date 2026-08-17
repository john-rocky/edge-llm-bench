# Energy methodology

iOS does not expose powermetrics-style energy counters to third-party apps. What we *can* read is `UIDevice.current.batteryLevel`, reported in 1% steps. We use that as the basis for an honest, if coarse, energy estimate.

## How a J/token number is produced

```
joules_used        = (start_battery_pct - end_battery_pct) × pack_capacity_Wh × 3600
joules_per_token   = joules_used / generated_token_count
```

Where:

- `start_battery_pct` and `end_battery_pct` are sampled at the start and end of a run.
- `pack_capacity_Wh` comes from a per-device lookup table keyed off `utsname().machine` (e.g. `iPhone17,1` → 13.0 Wh for iPhone 16 Pro). Numbers come from public datasheets / iFixit teardowns. Unknown devices fall back to 12 Wh.
- `1 Wh = 3600 J`.

## Limits of the metric

1. **1% resolution.** A 30-second short-chat run on a 0.6B model may consume far less than 1% of pack capacity. In that case the energy column shows `—` rather than a fake number.
2. **Whole-system attribution.** The number includes the display, radios, background processes, and anything else running. For comparability across runs, the pre-flight checklist surfaces brightness, Airplane Mode, and Low Power Mode state.
3. **Pack capacity drift.** Battery capacity falls as the device ages. A 90%-health iPhone 16 Pro has ~11.7 Wh of usable capacity, not the 13.0 Wh of a new pack. The result row records device hardware id, so contributors with significantly aged batteries can flag their measurements.
4. **Charging skews everything.** A run started while charging is flagged; the J/token field is suppressed for those runs (the battery level can rise during the run, producing nonsense numbers).
5. **Thermal throttling skews everything.** A throttled run does less work for the same energy. The result includes peak `thermalState` so users can correlate.

## When the metric is meaningful

The J/token number is **most useful for sustained runs** — Task C (512-token sustained generation) and the optional 1024-token variant. Those runs typically show a measurable battery delta and produce stable per-token energy estimates. The number is **least useful** for short-chat runs (Task A) on small models, where the run is faster than the battery sampler's 1% step.

## Why not MetricKit / `MXEnergyMetric`?

`MetricKit` reports daily aggregates per app session, not per-run numbers. Useful for production telemetry, useless for "I just ran this benchmark — how did it do?".

## Why not `IOPMCopyBatteryInfo`?

It's a private API that gives mAh delta directly. Apps that ship with it get rejected at App Store review, but more importantly we want this benchmark to reflect what a shipping app would experience — i.e. only public APIs.

## Future work

- **Energy/token by phase** — split prefill energy from decode energy so we can separately compare runtimes whose prefill is heavy (CoreML stateful KV chunked prefill) from those whose decode is heavy (llama.cpp large-batch GPU).
- **Display-corrected joules** — subtract a "screen on, idle app" baseline measured at the same brightness, leaving runtime-attributable joules.
- **MetricKit as a sanity check** — record per-day aggregate alongside the per-run estimate; if they diverge by more than 2× that is a signal something is wrong with the per-run methodology.
