# Measurement methodology

How every number in [`RESULTS.md`](../RESULTS.md) is defined, sampled, and reported.

## Wall clock

All time measurements use `Date.timeIntervalSinceReferenceDate` (a `CFAbsoluteTime` snapshot) on the same thread that drives generation. We **do not** use `DispatchTime.now()` because we want elapsed wall time across thread hops, and we **do not** use `Process.systemUptime` because it pauses while the device is asleep, which we want to capture as a real anomaly.

### TTFT (time to first token)

`TTFT = t_first_token_decoded - t_generate_called`

Includes prefill of the prompt. Reported in **milliseconds**, not seconds, because for short prompts on fast runtimes the value is dominated by sub-second prefill.

### Prefill tok/s

`prefill_tok_s = prompt_token_count / prefill_time`

Where `prefill_time` is the wall time from `generate(...)` being called to the moment the first generated token's logits are produced. For runtimes that do not expose a separate prefill timer, we infer it as `TTFT - 1 / decode_tok_s` (i.e., subtract one decoded-token's worth of time).

### Decode tok/s

`decode_tok_s = generated_token_count / generate_time`

Where `generate_time` excludes the prefill window. This is the steady-state generation rate the user feels.

### Total time

Wall clock from `generate(...)` call to the runtime returning a final completion event. Includes prefill + decode + any internal teardown.

## Memory

Sampled with the Mach `task_info(MACH_TASK_BASIC_INFO)` call, which gives `resident_size` in bytes. We track:

- `baseline` — sampled before the model is loaded
- `after_load` — sampled after the runtime reports the model is ready
- `peak_during_decode` — peak observed during the generation loop, sampled every 100 ms on a background queue
- `after_generation` — sampled 200 ms after generation completes (gives MLX/Metal a chance to release transient buffers)
- `after_unload` — only reported when the runtime exposes an unload API

We **do not** use `os_proc_available_memory()` because it reports a different number on different iOS versions and is not directly comparable to historical data.

## Thermal

`ProcessInfo.processInfo.thermalState` enum values, sampled every 1 s during the run. Reported:

- `before` — value at the moment the user taps **Run**
- `peak` — worst (highest) state observed
- `after` — value 5 s after generation completes

We also publish a "speed drop" curve: rolling-window decode tok/s over the run, so a thermal-throttled runtime is visible.

## Storage

- App binary size — `MainBundle.appStoreReceiptURL` ancestor `.app` bundle's `du -sk` equivalent, computed via `FileManager.attributesOfItem`
- Model file size — sum of all files in the model directory (weights + config + tokenizer)
- Tokenizer size — only the tokenizer files (separated because some runtimes ship tokenizers separately)
- Total installed size — app bundle + model directory

## Charging / low-power state

Both can dramatically change measured throughput. We record:

- `UIDevice.current.batteryState`
- `UIDevice.current.batteryLevel`
- `ProcessInfo.processInfo.isLowPowerModeEnabled`

A run that started with the phone charging or in low-power mode is flagged in the result row.

## Cancellation latency

The interval between calling the runtime's `cancel()` (or task cancellation) and the runtime acknowledging stop (final `.info` event or completion handler). Critical for chat-style apps.

## Reporting precision

- Times in seconds: 2 decimal places.
- Times in milliseconds: integer.
- Tokens/sec: 1 decimal place.
- Memory: integer MB.
- Percentages (speed drop): integer.

We don't pretend to more precision than the underlying sampling supports.
