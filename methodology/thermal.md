# Thermal methodology

iPhones throttle aggressively under sustained ML workloads. A benchmark that ignores this is misleading.

## What we sample

`ProcessInfo.processInfo.thermalState` returns one of:

- `.nominal` — phone is fine
- `.fair` — slight elevation, no throttling yet
- `.serious` — performance is being reduced
- `.critical` — performance is being significantly reduced; if you do nothing, the phone will shut down

We poll this every 1 s on a background queue during a run.

## What we report

- **Initial state** — value at the moment the user starts the run
- **Peak state** — worst value observed during the run
- **Final state** — value 5 s after the run completes
- **Decode-rate degradation curve** — rolling 5-second window of decode tok/s over the entire run, plotted in the result detail view

A run that starts at `.nominal` and ends at `.serious` after 300 generated tokens is meaningfully different from one that stays at `.nominal` throughout.

## Pre-run guidance

To get reproducible numbers:

- Start runs with the phone at `.nominal`. If the previous run left it at `.serious`, wait.
- Don't run benchmarks while charging on a fast charger — charging itself heats the phone.
- Don't run with the phone in a case that traps heat.
- Disable background app refresh for unrelated heavy apps (Photos sync, iCloud backup).

The app's pre-flight checklist surfaces the current `thermalState`, charging state, and low-power-mode state, and warns if any of them would invalidate the result.

## Why we don't use raw sensor temperatures

iOS does not expose CPU/GPU/ANE die temperatures to third-party apps. `thermalState` is the closest we get. It is a coarse signal — but it is the same signal that would throttle a shipping app, so it is the right one to use.
