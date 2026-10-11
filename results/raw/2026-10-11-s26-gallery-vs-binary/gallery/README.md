# Google AI Edge Gallery 1.0.20 — Benchmark screen sessions on the Galaxy S26 (SM-S942Q, Android 16), 2026-10-11 15:20–15:58 JST

What one session is (`../PLAN.md`, `../tools/gallery_bench.py`): the app is force-stopped and started, Models page → the
model item's **Benchmark** button → accelerator GPU or CPU, prefill 1,024, decode 256, number of runs 3 → Benchmark →
Continue. The screen's view model calls the LiteRT-LM Kotlin `benchmark()` once per run with a fresh engine; all runs of
the session share one temporary cache dir, so run 1 starts with no cache files (cold) and runs 2–3 with the files run 1
wrote, inside one app process (BenchmarkViewModel.kt 153–202 of the 1.0.20 source). The model files were placed at the
app's download paths (sha256 read back on the phone = the files of the two bugs: `gemma-4-E2B-it.litertlm`
18193810…, `gemma3-1b-it-int4.litertlm` 1325ae36…); the app's own allowlist caps Gemma3-1B-IT at max tokens 1,024,
which disables the screen at 1,024 + 256, so an override list with that one value at 4,096 sat in
`/data/local/tmp/model_allowlist_test.json` for the sitting (`../tools/model_allowlist_test.json`; the Gemma-4 entry is the
published one, max tokens 4,000). The engine's max tokens are not set by the app (litertlm.cc `nativeCreateBenchmark`:
`EngineSettings::CreateDefault` + cache dir + prefill/decode counts); the app's log does not print the value.

Conditions: screen on the whole sitting (`svc power stayon usb`; the app needs it), phone unlocked, the app's own
language set to en-US for the sitting (the phone is ja-JP; the driver matches English labels; reset afterwards), USB
power, nothing else of ours running on the phone; a cool-down to ≤ 35–36 °C (max of the gpuss-0 / cpu-0-0-0 / cpu-1-0-0
zones, at most 3–4 min) before every session. A 1-second sampler ran beside each session (`<tag>.sample.csv`, the
columns of `../binary/`'s sampler) and a Perfetto trace for E2B-gpu-1 (`../../2026-10-11-s26-perfetto/`; the G3-cpu-1 session's trace was refused by the tracing service: five earlier sessions were still open, see the perfetto folder's README).

How the numbers were read: the app's results viewer shows one card per session with Prefill speed, Decode speed, Time to
first token, First init time (run 1) and Steady init time (runs 2..N) at an aggregation (avg / median / min / max);
tapping a value opens its series sheet with the per-run graph (runs left to right) and the four aggregates. With three
runs the three values are {min, median, max}; which run has which comes from the order of the graph's three points by
height (`gallery_bench.py graph_point_order`, read from the sheet's screenshot `ui-series-<tag>-<metric>.png`; the
graph's tap read-out reports the y-axis value at the tap, not a point). Two near-equal values (e.g. 49.26 / 49.25) rely
on a 1-pixel difference, so treat them as equal. `<tag>.results-ui.json` holds everything the viewer showed; the app's
engine lines (tags litert / native / tflite) are in `<tag>.logcat.txt` and `<tag>.logcat-benchmark-lines.txt`.

Not measurements: `*.attempt*` (driver attempts that did not reach a run: the Japanese UI, the menu without a Benchmark
item, the keyboard hiding the third field, an item under the navigation bar); `debug-*.png`; the help sheet "How to
compare benchmark runs" that covered the viewer during E2B-gpu-2 (dismissed by hand; the run itself had finished).
Numbers: `table.md`.
