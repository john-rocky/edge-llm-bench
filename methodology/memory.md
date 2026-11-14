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
session's runs, first-ever runs (the engine-cache build) left out, of each run's
footprint peak, else its resident peak (the same per-row basis choice as `mem`),
and `mem_peak_n` = the runs that had one; process-cold and warm runs pool in it.
The dashboard shows it as "mem peak MB".

A footprint peak does not compare across runtimes, even on one platform: each
runtime keeps its weights in a different place. MLX allocates them, so they are
in the footprint; llama.cpp and LiteRT-LM map them from a file (the GGUF,
LiteRT-LM's weight cache), so they sit in the page table or in memory the GPU
wraps, outside the footprint. Across runtimes, read the total of the next
section. The Apple and Android windows differ as well (load
outside / inside), so no peak compares across platforms.

## Three places and a total (Apple, 2026-11-14)

A run's memory can sit in three places, and which ones depends on the runtime:

| place | what is in it | read from |
|---|---|---|
| 1. `phys_footprint` | dirty and compressed memory, and the Metal buffers a runtime allocates (MLX keeps its weights there) | `task_info(TASK_VM_INFO)` |
| 2. mapped file pages in the page table (`external`) | a mapped model or weight cache the CPU has read (llama.cpp's GGUF, LiteRT-LM's CPU weight cache) | the same call |
| 3. memory the GPU wraps without a copy | a mapped model file or anonymous memory handed to the GPU with `newBufferWithBytesNoCopy`, which the OS charges to nobody (LiteRT-LM's GPU weight cache; llama.cpp's GGUF, KV cache and compute buffers) | the pages in RAM of the VM objects behind the wrapped regions (full VM region query) |

Place 3 overlaps the other two wherever the CPU has touched wrapped memory too.
Measured on an Apple M4 Max under macOS 27 with 256 MB test buffers:

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
the page table (the region query answers from the page table in footprint mode,
`vm.self_region_footprint`). So the total adds, beyond `phys_footprint` and
`external`, exactly the wrapped pages outside the page table, the pages only the
GPU holds (`wrappedGPUOnlyMB`).

A wrap shows in the VM region query: the region turns "true shared" and its VM
object gains a reference (a shared file mapping 2 → 3, anonymous memory 1 → 2; a
private file mapping's top VM object turns anonymous and true shared at the
GPU's first read). The sampler (`MemoryMonitor.measureOverlap`) finds those
regions and walks their pages. A runtime may wrap only part of a mapping:
llama.cpp leaves the tensors the CPU computes out of its GPU buffers but maps the
whole GGUF. Counting the whole VM object needs no knowledge of which part is
wrapped, because whatever of it is in the page table is subtracted again. So
place 3 alone is not what the GPU holds: for llama.cpp it counts the whole GGUF's
VM object, and the total subtracts the part in the page table. The
error left: file pages of a wrapped region that stay cached in RAM, outside the
page table and outside the wrapped part, count as GPU-held. A file mapped shared
by plain mappings of other processes reads "shared", not "true shared", and is
left out. Confirming a wrapped private file mapping takes the full region query,
which walks every page of the mapping (10-38 ms for a 3.7 GB model file mapped in
pieces), so the sampler runs it only while Metal's figure beyond the ledger
exceeds the sizes of the regions already found by 32 MiB, that is while the GPU
holds memory not located yet.

The sampler measures at the first tick, again once `external`, `internal` or
Metal's figure beyond the ledger has moved by 16 MiB, or place 3 itself moved by
16 MiB at the last measurement (250 ms apart at least: a wrapped file the GPU
reads for the first time pages in over seconds), and every 2 s while the process
has wrapped regions (the GPU touching a wrapped page moves none of those
counters). A measurement takes about 0.7 ms per 600 regions plus 0.7-0.8 ms
per 512 MB walked, twice per wrapped region; the record carries the count and
the time (`memoryOverlapQueries`, `memoryOverlapQueryMS`).

LiteRT's profiler estimates place 3 from Metal instead: `MTLDevice.currentAllocatedSize`
(macOS: summed over every device) beyond the whole kernel ledger
(`mappedWeightsMB`, kept beside the measured place 3, `wrappedResidentMB`). That
estimate counts a wrapped buffer at its length whether or not its pages are in
RAM, counts an allocated resource before its pages are charged to the ledger, and
falls short by any graphics memory the ledger holds outside Metal's figure (the
GPU driver's own: 161 MB after the first GPU command of the test above). It
cannot give the overlaps either: they are pages of the wrapped part only, and
the VM query does not see which part of a mapping a GPU buffer covers.

The same readings give the figures of LiteRT's memory profiler
(google-ai-edge/LiteRT `litert/core/util/memory_profiling/`), under its names:

| record fields (peak / median) | LiteRT | definition |
|---|---|---|
| `memoryPeakResidentMB` | host `resident_bytes` | `resident_size` |
| `memoryPeakDuringDecodeMB` | host `platform_attributed_bytes` | `phys_footprint` |
| `memory{Peak,Median}AcceleratorAttributedMB` | accelerator `attributed_bytes` | the ledger's graphics and neural parts, compressed included |
| `memory{Peak,Median}AcceleratorPresentMB` | accelerator `total_bytes` | the ledger's graphics and neural pages in RAM, plus Metal's figure beyond the whole ledger |
| `memory{Peak,Median}ResidentInRAMMB` | `MemorySnapshot.resident_in_ram` | host resident + accelerator present |

Resident in RAM counts a page twice when it is both in the page table and
accelerator memory: a Metal buffer the CPU has written (in the test, writing a
256 MB shared buffer raised `resident_size` and the graphics ledger by 256 MB
each) or a wrapped file the CPU has read. It is not a total; `memory*TotalMB` is.

Record fields and `results/summary/device-runs.csv` columns, all over the window
of `memoryPeakDuringDecodeMB`, MiB, empty on records from an older binary (no
`memoryAccountingBasis`). That window starts
after the model load in `BenchmarkRunner`; in the yardstick's native paths it is
the whole native call, and LiteRT-LM's `benchmark()` builds its engine inside it.

| record field | column |
|---|---|
| `memory{Median,Peak}TotalMB` | `mem_total_{median,peak}_mb` |
| `memory{Median,Peak}ExternalMB` | `mem_external_{median,peak}_mb` |
| `memory{Median,Peak}AcceleratorPresentMB` | `mem_accel_present_{median,peak}_mb` |
| `memory{Median,Peak}AcceleratorAttributedMB` | `mem_accel_attributed_{median,peak}_mb` |
| `memory{Median,Peak}ResidentInRAMMB` | `mem_resident_in_ram_{median,peak}_mb` |
| `memoryAtTotalPeak.overlapMB` (both overlaps) | `mem_overlap_at_total_peak_mb` |

`memoryAtTotalPeak` holds the whole reading at the total's peak, every part in
MiB, so the parts add up to it (`hostAttributedMB` + `externalMB` +
`wrappedResidentMB` - `overlapExternalMB` - `overlapFootprintMB` = `totalMB`);
`memoryAccountingBasis` names this definition (`apple-vm-wrapped-pages-v1`). The
total is empty when the wrapped regions could not be measured (the page-table
query refused). Which number answers what: the total for "does it fit in RAM",
across runtimes; `phys_footprint` for "will iOS kill it" (jetsam charges the
footprint, not mapped clean pages or pages only the GPU holds).

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
