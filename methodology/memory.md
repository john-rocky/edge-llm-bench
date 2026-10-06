# Memory methodology

iOS will jetsam an app that uses too much memory. For LLM runtimes this is the dominant failure mode after thermal throttling.

## Sampling

We read **`phys_footprint`** via the Mach `task_info` `TASK_VM_INFO` call — the
byte count iOS charges the process and the exact value **jetsam** uses to decide
what to kill (dirty + compressed + IOKit-attributed memory):

```swift
var info = task_vm_info_data_t()
var count = mach_msg_type_number_t(MemoryLayout<task_vm_info_data_t>.size / MemoryLayout<integer_t>.size)
let result = withUnsafeMutablePointer(to: &info) {
    $0.withMemoryRebound(to: integer_t.self, capacity: Int(count)) {
        task_info(mach_task_self_, task_flavor_t(TASK_VM_INFO), $0, &count)
    }
}
// info.phys_footprint  (bytes)
```

Sampled every 100 ms on a background queue during a run. Runs captured before
2026-06 used `mach_task_basic_info.resident_size` (RSS); `phys_footprint` is
typically **higher** because RSS omits compressed pages, so numbers across the
two eras are not byte-identical — re-measure a device to compare on one basis.
`MemoryMonitor.residentMB()` is still available for the RSS reference.

## Reported values

- `baseline_mb` — before the model is loaded
- `after_load_mb` — once the runtime reports model ready
- `peak_during_prefill_mb` — peak during prompt processing (not recorded separately:
  the sampler's window behind `peak_during_decode_mb` covers prefill too — "Peak memory")
- `peak_during_decode_mb` — peak during generation
- `after_generation_mb` — sampled 200 ms after generation completes
- `after_unload_mb` — only when the runtime exposes an unload API

The interesting deltas:

- `after_load_mb - baseline_mb` ≈ model + runtime overhead
- `peak_during_decode_mb - after_load_mb` ≈ KV cache + transient buffers
- `after_generation_mb - after_load_mb` ≈ steady-state cost of an idle loaded model

## Peak memory

The high-water fields, per writer, and the `results/summary/device-runs.csv`
columns they feed (2026-10-06). Every MB here is MiB (bytes / 2^20) except uzu's.

| writer | record field → summary column | instrument | window |
|---|---|---|---|
| Apple `BenchmarkRunner` (iOS app, Mac yardstick) | `memoryPeakDuringDecodeMB` → `mem_footprint_peak_mb` | `phys_footprint`, every 100 ms (`MemorySampler`) | from right after the model load (`memoryAfterLoadMB`) to the end of generation: prefill and decode, every call of a sustained task; load outside. The field's name says decode; its window is the whole generation |
| Apple `BenchmarkRunner` | `memoryPeakResidentMB` → `mem_resident_peak_mb` | `resident_size`, the same ticks | the same window. Mapped weight pages fault in and out, so this peak is page-cache noise (66–281 % run to run on 2026-07-26 while the footprint held ~1 %, `MemorySampler`) — read the footprint peak |
| Android `android/bench/run_cell.py` | `memoryPeakResidentMB` → `mem_resident_peak_mb` | VmHWM of `/proc/<engine pid>/status`, the largest read, kB / 1024 | reads every 0.5 s from 1 s after launch until the engine exits; VmHWM is the kernel's high-water mark since process start, so load, prefill and decode are inside. `provenance.rssBasis` says so per record. The VmRSS median beside it (`memoryMedianResidentMB`) has the same window — unlike the Apple median it includes load. A GPU arm's driver buffers are not in RSS (`docs/dashboard-cells-v1.md`) |
| other Android drivers (endurance, ASR, TTS, VL, the APK lane) | `memoryPeakResidentMB` → `mem_resident_peak_mb` | VmHWM | each driver's doc |
| uzu (`scripts/uzu_mac.py`) | `memoryPeakResidentMB` → `mem_resident_peak_mb` | `RUSAGE_CHILDREN.ru_maxrss`, decimal MB (bytes / 1e6) | includes model load (`docs/uzu-arm-v1.md`) |

Which rows have a peak: every `BenchmarkRunner` row in the repo carries both Apple
fields. `run_cell.py` read VmHWM only under `BENCH_STRICT_SMOKE=1` until
2026-10-06, so its earlier rows carry a peak only from those sittings (the
long-context S26 ladder); the Android short-chat rows before that date have none,
and none is reconstructed from them. Runs from 2026-10-06 on read it on every launch.

Aggregation: `render_leaderboard.arm_row` gives `mem_peak` = the median over the
session's runs of each run's footprint peak, else its resident peak (the same
per-row basis choice as `mem`), and `mem_peak_n` = the runs that had one. The
dashboard shows it as "mem peak MB". The Apple and Android windows differ (load
outside / inside), so a peak compares across arms of one platform, not across
platforms.

## `phys_footprint` vs `resident_size` vs `os_proc_available_memory()`

`resident_size` (RSS) omits compressed pages, so under memory pressure it
*under-reports* by hundreds of MB — it is **not** the number jetsam charges.
`os_proc_available_memory()` reports remaining headroom, but its semantics
shifted across iOS versions. `phys_footprint` is the stable, jetsam-relevant
figure and the one Instruments' "Memory" gauge shows, so that is what we report.

## Jetsam budget

The actual jetsam threshold depends on the device, foreground/background state, and what other apps are doing — Apple does not publish exact numbers. As a rule of thumb on a 6 GB iPhone:

- Foreground app, screen on: ~3 GB before jetsam risk
- Background app: ~200-500 MB

We do not enforce a budget in the benchmark. If a runtime gets jetsam'd, that is the result.

## Wired-memory ticket (MLX)

MLX Swift exposes `WiredMemoryTicket` for coordinating concurrent generations. We do **not** use it in the standalone benchmark, because the benchmark only runs one generation at a time. A separate "concurrent inference" task may be added later.
