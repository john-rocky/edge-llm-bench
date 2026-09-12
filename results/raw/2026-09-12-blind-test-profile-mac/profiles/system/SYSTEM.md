# System profile: litert-community/gemma-4-E2B-it-litert-lm, native-benchmark 128x1024 ctx2048, Mac (Metal System Trace)

Mac Studio (Mac16,9), macOS 27.0, Xcode 27.0, LiteRT-LM v0.16.0 vendored
(yardstick harness=2026-07-30-agreed-protocol-r4), 2026-09-13.

## Rates (control vs traced — a profiled rate is never a speed row)

| capture | decode tok/s | init s | ttft ms |
|---|---|---|---|
| control (this skill) | 158.69 | 4.62 | 52.7 |
| step 1 short-chat, same bundle (cross-check) | 158.23 / 159.81 | - | - |
| Metal System Trace attach | 156.67 | 1.16 | 38.4 |

Tracing cost ~1.3% of the decode rate (158.69 -> 156.67), close to the
skill's own "tracing moved the rate under 1%" for Qwen3-0.6B; init/ttft swing
between the two runs is host-load noise, not attributable to the tracer since
the tracer attaches after launch.

## Reading

**Is the GPU busy?** `xctrace_tables.py gpu` on the exported
`metal-gpu-intervals` table, filtered to the `yardstick` process: 12,043
Compute intervals, 4,922.7 ms busy over a 5,496.6 ms process window -
**89.6% occupancy** (Fragment channel: 2 intervals, ~0%). Gap distribution
between intervals: median 1 us, p90 385 us, max 5.4 ms - a GPU-bound decode,
though with a longer tail of gaps than the skill's own Qwen3-0.6B reading
(99.7% occupancy, 1 us median gap there); Gemma 4 E2B's larger per-step
compute leaves more room for a handful of longer stalls.

Full table: `gemma-4-e2b_128x1024_ctx2048_mst_gpu-intervals.txt`; raw export
`gemma-4-e2b_128x1024_ctx2048_mst_metal-gpu-intervals.xml` (local only,
gitignored, 17 MB).

Time Profiler twin was not run - the task asked for one Instruments trace
(Metal System Trace) attached to the runner, not the CPU-side twin the skill
also offers.

## Note on the trace bundle

The `.trace` bundle stores the traced process's whole environment, and
`xcrun xctrace export --toc` prints it — including any credential the shell
exports. No value is stored in this campaign; the bundle was deleted once the
`--xpath` table export and its summary were written (the export holds no
environment). The skill now says so; export tables by `--xpath` only.
