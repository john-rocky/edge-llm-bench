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
| Android `android/bench/run_cell.py` | `memoryPeakResidentMB` → `mem_resident_peak_mb` | VmHWM of `/proc/<engine pid>/status`, the largest read, kB / 1024 | reads every 0.5 s from 1 s after launch until the engine exits; VmHWM is the kernel's high-water mark since process start, so load, prefill and decode are inside. `provenance.rssBasis` says so per record. The VmRSS median beside it (`memoryMedianResidentMB`) has the same window — unlike the Apple median it includes load. Whether a GPU arm's device memory is in VmRSS depends on the GPU (methodology `android.md`, "GPU memory and VmRSS") |
| other Android drivers (endurance, ASR, TTS, VL, the APK lane) | `memoryPeakResidentMB` → `mem_resident_peak_mb` | VmHWM | each driver's doc |
| uzu (`scripts/uzu_mac.py`) | `memoryPeakResidentMB` → `mem_resident_peak_mb` | `RUSAGE_CHILDREN.ru_maxrss`, decimal MB (bytes / 1e6) | includes model load (`docs/uzu-arm-v1.md`) |

Which rows have a peak: every `BenchmarkRunner` row in the repo carries both Apple
fields. `run_cell.py` read VmHWM only under `BENCH_STRICT_SMOKE=1` until
2026-10-06, so its earlier rows carry a peak only from those sittings (the
long-context S26 ladder); the Android short-chat rows before that date have none,
and none is reconstructed from them. Runs from 2026-10-06 on read it on every launch.

Aggregation: `render_leaderboard.arm_row` gives `mem_peak` = the median over the
session's runs of each run's
footprint peak, else its resident peak (the same per-row basis choice as `mem`),
and `mem_peak_n` = the runs that had one; process-cold and warm runs pool in it.
The dashboard shows it as "mem peak MB".

A footprint peak does not compare across runtimes, even on one platform: each
runtime keeps its weights in a different place. MLX allocates them, so they are
in the footprint; llama.cpp and LiteRT-LM map them from a file (the GGUF,
LiteRT-LM's weight cache), so they sit in the page table or in memory the GPU
wraps, outside the footprint. Across runtimes on macOS, read the total of the
next section. The Apple and Android windows differ as well, so no peak compares
across platforms.

## Three places and a total (Apple, 2026-11-14)

macOS only: on iOS the sampler reads `phys_footprint` and `resident_size` as before, now from
one `task_info(TASK_VM_INFO)` call, and the records carry none of the fields below.

A run's memory can sit in three places, and which ones depends on the runtime:

| place | what is in it | read from |
|---|---|---|
| 1. `phys_footprint` | anonymous memory the CPU has touched, in RAM or compressed, and the Metal buffers a runtime allocates (MLX keeps its weights there) | `task_info(TASK_VM_INFO)` |
| 2. mapped file pages in the page table (`external`) | a mapped model or weight cache the CPU has read (llama.cpp's GGUF, LiteRT-LM's CPU weight cache) | the same call |
| 3. memory the GPU wraps without a copy | a mapped model file or anonymous memory handed to the GPU with `newBufferWithBytesNoCopy` (LiteRT-LM's GPU weight cache; llama.cpp's GGUF, KV cache and compute buffers) | the pages in RAM of the VM objects behind the regions that look wrapped by the GPU (full VM region query; see below) |

Place 3 overlaps the other two wherever the CPU has touched wrapped memory too.
Measured on an Apple M4 Max under macOS 27 with test buffers:

- a file mapped shared (`MAP_SHARED`, as llama.cpp maps its GGUF): the pages
  the CPU has read stay in the page table, so they are in places 2 and 3;
- anonymous memory the runtime allocates and wraps (llama.cpp's KV cache and
  compute buffers on Apple silicon): the pages the CPU has touched are in places
  1 and 3;
- a file mapped private: at the GPU's first read its pages leave the page table
  for an anonymous VM object the GPU shares; the pages the CPU touches after
  that are in places 1 and 3;
- pages only the GPU has touched are in place 3 alone.

The total counts each page once:

    total = place 1 + place 2 + place 3 - overlap(2, 3) - overlap(1, 3)

Both overlaps are measured, not assumed: they are the wrapped regions' pages in
the page table (for these regions the region query answers from the page table
in footprint mode, `vm.self_region_footprint`). So the total adds, beyond
`phys_footprint` and
`external`, the wrapped pages outside the page table
(`wrappedGPUOnlyMB`).

A wrap shows in the VM region query: a shared file mapping's VM object gains a
reference (a third with one buffer), and the
region turns "true shared" at the GPU's first read; anonymous memory turns true
shared with a second reference; a private file mapping's top VM object turns
anonymous and true shared at the GPU's first read.
`MemoryMonitor.measureOverlap` finds those
regions and walks their pages. A runtime may wrap only part of a mapping:
llama.cpp leaves the tensors the CPU computes out of its GPU buffers but maps the
whole GGUF. So
place 3 alone is not what the GPU holds: for llama.cpp it counts the whole GGUF's
VM object.
File pages of a wrapped region that stay cached in RAM, outside
the page table and outside the wrapped part, count in the total. Memory the GPU
does not wrap can look wrapped too, and its pages outside the page table count
in the total too.
A file mapped shared
by plain mappings of other processes reads "shared", not "true shared", and is
left out. Confirming a wrapped private file mapping takes the full region query;
the sampler runs it only while Metal's figure beyond the ledger
(`mappedWeightsMB`, described below) exceeds the sizes of the regions already
found by 32 MiB, that is while the GPU holds memory not located yet.

The sampler measures at the start, again once `external`, `internal` or
Metal's figure beyond the ledger has moved by 16 MiB, or place 3 itself moved by
16 MiB at the last measurement (250 ms apart at least: a wrapped file the GPU
reads for the first time is paged in over seconds), and every 2 s while the process
has wrapped regions (the GPU touching a wrapped page moves none of those
counters). A measurement is one query per region of the process plus the page
walks, twice per wrapped region; the record carries the count and
the time (`memoryOverlapQueries`, `memoryOverlapQueryMS`). A sample between two
measurements uses the last one. A measurement that fails counts in
`memoryOverlapQueries` and in `memoryOverlapFailedQueries`, leaves the last
measurement in use the same way, and is tried again at the same pace.

`memoryAtTotalPeak` also carries Metal's own figure, `MTLDevice.currentAllocatedSize`,
as `metalAllocatedMB`, and the part of it beyond
the kernel ledger as `mappedWeightsMB`: the "Metal's figure beyond the ledger" the
sampler uses above. The ledger is the part of `phys_footprint` the kernel charges to
the GPU and the Neural Engine (`graphicsMB`, `neuralMB` and their compressed parts).
`mappedWeightsMB` is not place 3 (`wrappedResidentMB`): Metal's figure is the size of
what is allocated, whether or not its pages are in RAM, and place 3 counts the pages
in RAM. The ledger also holds graphics memory that is not in Metal's figure, which
lowers `mappedWeightsMB` (a record shows such memory where `graphicsMB`
exceeds `metalAllocatedMB`).

Record fields and `results/summary/device-runs.csv` columns, all over the window
of `memoryPeakDuringDecodeMB`, MiB, empty on records from an older binary (no
`memoryAccountingBasis`). That window starts
after the model load in `BenchmarkRunner`; in the yardstick's native paths it is
the whole native call, and LiteRT-LM's `benchmark()` creates its `Engine` inside it.

| record field | column |
|---|---|
| `memory{Median,Peak}TotalMB` | `mem_total_{median,peak}_mb` |
| `memory{Median,Peak}ExternalMB` | `mem_external_{median,peak}_mb` |
| `memoryAtTotalPeak.overlapMB` (both overlaps) | `mem_overlap_at_total_peak_mb` |

`memoryAtTotalPeak` holds the reading at the total's peak, every part in
MiB, so the parts add up to it: `hostAttributedMB` (`phys_footprint`) +
`externalMB` + `wrappedResidentMB` - `overlapExternalMB` -
`overlapFootprintMB` = `totalMB`. `memoryAccountingBasis` names this
definition (`apple-vm-wrapped-pages-v1`). The total is empty when the
measurement at the start fails, even if a later one succeeds. Which number
answers what: the total for "does it fit in RAM",
across runtimes; `phys_footprint` for "will iOS kill it" (jetsam charges the
footprint, not file-backed pages or pages only the GPU holds).

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
