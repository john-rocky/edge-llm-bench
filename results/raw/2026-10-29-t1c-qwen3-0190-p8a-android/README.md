# T1c on LiteRT-LM 0.19.0 — Pixel 8a column (2026-10-29)

**Terms.** T1c = a lane (2026-10-15) that exported Qwen3-1.7B with int8 channelwise weights (`dynamic_wi8_afp32`) and Qwen3-4B with int4 block-32 weights (`dynamic_wi4b32_afp32`) through litert-torch's GPU-composite path (`--apply_gpu_composites=True`) and compared them with the Hugging Face files of the time. This dir is the Pixel 8a column of that comparison on the released LiteRT-LM 0.19.0; the Galaxy S26 column of the same day, with the same wheel, harness and labels, is `results/raw/2026-10-29-t1c-qwen3-0190-s26-android/`. N17 and N4 below are litert-community's uploads of 2026-10-27: the same sizes as T1c's own exports, other bytes. The lane's own files (device scripts, plans, tables, round notes) are in a private lane repo; the lines this README relies on are restated here, with their lane-repo path where a line is cited. The files of this column:

| label | file (litert-community repo) | role |
|---|---|---|
| N17 | `Qwen3-1.7B_dynamic_wi8_afp32_gpu_composites.litertlm` (Qwen3-1.7B, added 2026-10-27, commit d6678881) | the 1.7B int8 GPU-composite file |
| I17B | `Qwen3_1.7B.litertlm` as it was before 2026-10-31 (lfs sha256 362ec1c9…) | the 1.7B int8 file it is compared with |
| W17B | `Qwen3-1.7B_dynamic_wi4b32_afp32.litertlm` (lfs sha256 2a72330b…, unchanged since) | the file of the 1.7B GPU cells of `matrices/dashboard-text-v1-android-a.cells`, alone in its own group |
| N4 | `Qwen3-4B_dynamic_wi4b32_afp32_gpu_composites.litertlm` (Qwen3-4B, added 2026-10-27, commit a45912eb, lfs sha256 a11d1b4c…) | the 4B int4 block-32 GPU-composite file; one process on 2026-11-02 (below) |

**Question.** Does N17 build its GPU engine on the Pixel 8a with LiteRT-LM 0.19.0, how fast is it against I17B, and does N4 run there? The phone ran the PyPI `litert-lm-api` 0.19.0 Android (aarch64) wheel on CPython 3.14.8 on the phone (`liblitert-lm.so` 22,656,360 B, sha256 `28fa8433…fc78`, `logs/p8a/KIT_kpy_gpu_selftest_1.json`), not this repo's Android build (the repo's pin moved to v0.19.0 on 2026-10-31, c22ebe61).

**Answer.** N17: yes. It built the OpenCL engine with every node on the GPU (436/436, 436/436, 406/406 for prefill_128, prefill_1024 and decode), answered the eight short questions 8/8, and was faster than I17B in the same hold: +199.5 % prefill / +64.6 % decode (GPU protocol, below). N4: no rate. Its GPU engine was built with every node on the GPU (556/556, 556/556, 518/518), and 2 s after the benchmark's session was created the lane's memory guard stopped the process (exit 137).

**How.** One process per leg, `legpy.py` on the phone's CPython importing the wheel, as in the S26 column:

- protocol = `litert_lm.Benchmark(model, backend, prefill_tokens=1024, decode_tokens=256, max_num_tokens=2048)` (the class the `litert-lm benchmark` CLI runs), one engine, 3 runs; a process's figure = the median of its 3 runs; three processes A / B / C; the row = the median over A / B / C;
- dashboard prompt = `Engine(max_num_tokens=2048, enable_benchmark=True)`, per iteration a new conversation and `send_message(prompt, max_output_tokens=256)`, 2 iterations, with the 1K prompt of T1b's column (sha256 `f64fb515…`, 1,338 tokens);
- eight questions = `Engine(max_num_tokens=1280)`, a session with host-rendered ChatML and the bundle's sampler, one regex per question (GPU, N17 only);
- CPU protocol = the protocol on the CPU backend, one process per file.

Shared Pixel 8a holds (Pixel 8a, Android 16, build CP1A.260505.005), JST, from the driver's start and end lines of each `runlog.txt`; the phone dir was removed at the end of each:

| ticket | time | legs |
|---|---|---|
| `s29q3-p8a-a` | 2026-10-29 13:19:01–13:57:43 | the wheel's selftest, N17's legs, I17B's GPU legs |
| `s29q3-p8a-b` | 2026-10-29 13:57:52–14:36:57 | I17B's CPU leg, a Qwen3-0.6B pair, W17B's GPU legs |
| `s29q3-p8a-c` | 2026-10-29 15:24:47–15:45:23 | a CPU recheck of the 0.6B pair, W17B's CPU leg |
| `t1c-p8a-4b-1102` | 2026-11-02 16:46:39–16:49:12 | the wheel's selftest, N4's push, one cold N4 GPU protocol process (`logs/p8a-2026-11-02/`) |

The 0.6B legs are not in this dir, as in the S26 column; their lines are in `logs/p8a/runlog.txt`. Hold `-a`'s kit carried four more CPython libraries than the later holds' (680 and 676 files, `logs/p8a/runlog.txt` lines 8 and 88; nothing loaded them); the python3 launcher, libpython, standard library and wheel are the same bytes in every hold, 2026-11-02's included.

**Numbers** (the 2026-10-29 holds only; not pooled with the S26 column, with T1c's sixth round (2026-10-16, lab phones) or with any page row):

| row | N17 | I17B |
|---|---|---|
| GPU protocol 1024 / 256, median over 3 processes (prefill / decode tok/s) | 753.9 / 14.83 | 251.8 / 9.01 |
| against the compared file (from the unrounded medians) | +199.5 % / +64.6 % | — |
| GPU dashboard prompt (1,338 tokens), prefill then decode, iterations 1 / 2 | 584.5 / 597.6; 13.9 / 14.3 | 233.8 / 237.6; 9.0 / 9.0 |
| eight questions (GPU, bundle sampler) | 8/8 | not run |
| CPU protocol 1024 / 256, one process | 52.8 / 5.46 (hold `-a`) | 35.7 / 3.40 (hold `-b`) |

W17B alone (GPU legs in hold `-b`, CPU leg in hold `-c`): GPU protocol 271.3 / 19.46; dashboard prompt 236.6 / 239.7 prefill, 18.7 / 19.0 decode; CPU protocol 39.4 / 6.68.

- Every timed process of the three files (GPU and CPU protocol, dashboard prompt) started at thermal status 1 with every CPU policy's ceiling at its maximum; on this phone the lane's ready gate takes status 1 once the ceilings are clear (`ready=True` in `RESULTS.md`). The Mali GPU's clock is not read (`kgsl none`).
- Inside each GPU protocol process the three runs stay within 1.7 % of each other in prefill and 2.9 % in decode (the widest: I17B B 248.7 / 252.8 / 251.9 tok/s prefill, N17 A 14.54 / 14.96 / 14.79 tok/s decode).
- A cold GPU process of N17 wrote a 1,725,694,528 B weight cache beside the file (its stderr: `Weights preparation on Gpu is disabled for PowerVR, Broadcom, Mali GPUs …`), and LiteRT-LM reported 107.4 s (dashboard leg) and 104.9 s (protocol A) of init; the cached processes B and C reported 16.1 and 13.5 s (`init_ms` in `runlog.txt`).
- The CPU rows are one process each; their runs fall (N17: 78.5 / 52.8 / 51.3 prefill; I17B: 73.8 / 35.4 / 35.7). Sustained figures, not a headline.
- I17B's separate embedder subgraphs (`decode_embedder`, `prefill_embedder_128`) delegate 1 of 4 nodes to XNNPACK; every other subgraph of N17, I17B and W17B ran all its nodes on LITERT_CL (dashboard-prompt legs, `RESULTS.md` and `runlog.txt`).

**4B on this phone.** The lane's 2026-10-29 plan ran no 4B pair here (lane repo `qwen3_gpuopt_work/replace_0190_20261029/device/run_p8a.sh` line 4: "No 4B pair on this 8 GB phone"). It went by T1c's sixth round (2026-10-16) on a Developer Device Platform lab Pixel 8a (Android 15, LiteRT-LM main@b7c40ea81's `litert_lm_advanced_main`, T1c's own 4B export: N4's size, other bytes; lane repo `qwen3_gpuopt_work/exports_4b_17b_20261015/ROUND6.md` lines 33, 57 and 86): there the 4B GPU dashboard-prompt process built its engine, about 4 s into the first inference MemAvailable fell to 242,856 kB, and the guard stopped it (exit 137); by the plan's rule the compared file M4B was then not tried. This repo's dashboard has left the Pixel 8a's Qwen3-4B rows out since 2026-10-07 (`docs/dashboard-cells-v1.md`, "Per-device exclusion (2026-10-07)"). Neither record was this phone with this runtime and N4, so on 2026-11-02 N4 got one GPU protocol process here, with the same wheel, scripts and guard (MemAvailable under 400,000 kB on two reads 2 s apart → stop). MemAvailable was 2,773,368 kB at the start; the engine was built (556/556, 556/556, 518/518 on LITERT_CL, a 2,011,150,872 B weight cache written), the benchmark's session was created 42 s in, and at 44 s the guard stopped the process (exit 137, no run finished; the read on its stop line was 140,776 kB, and its lowest read over the 2 s polls was 0 kB, `MEMMIN` in the meta's `R` field). The phone did not reboot (uptime rose), and right after the stop MemAvailable read 3,849,092 kB. What this shows: with this wheel and the guard's 400,000 kB line, the process was stopped 2 s after its session was created; whether a run would finish without the guard, or with a smaller `max_num_tokens`, was not tried. This dir has no N4 or M4B rate for the Pixel 8a.

**After this sitting.** On 2026-10-31 litert-community/Qwen3-1.7B (commit ebb4eef4, 04:56 UTC) and litert-community/Qwen3-4B (commit 965e091f, 05:08 UTC) replaced `Qwen3_1.7B.litertlm` and `qwen3_4b_mixed_int4.litertlm` "with the GPU-composite export" (the commit titles), and the `_gpu_composites` names are no longer in the main tree. This dir holds no run of the bytes now under the kept names. The Android cells download their file by name from main; on this phone they are the 1.7B rows of `matrices/dashboard-text-v1-android-a.cells`, so from its first sitting on the v0.19.0 pin the 1.7B CPU cells run the bytes now under `Qwen3_1.7B.litertlm`, and the 1.7B GPU cells run W17B, which did not change.

**Files.** `RESULTS.md` (the lane's `summarize.py` run on this dir's `logs/p8a/` and `logs/p8a-2026-11-02/` on 2026-11-02), `logs/p8a/` (each leg's stderr, parsed JSON, meta and stdout for N17, I17B, W17B and the wheel's selftest; `runlog.txt`, the lane's log of the three holds; `device_props.txt`), `logs/p8a-2026-11-02/` (the same for the selftest and N4's process; its `runlog.txt`, with the bundle's local path shortened to the file name; `device_props.txt`). The legs' logcat files are left out: they carry other processes' lines.

Nothing here is a schema record: `scripts/build_summary.py` reads `app-path*/` and `device-jsonl/` JSON and campaign-dir `*.jsonl`, and this dir has none, so `results/summary` does not change.
