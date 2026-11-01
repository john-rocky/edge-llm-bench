# T1c on LiteRT-LM 0.19.0 — Galaxy S26 column (2026-10-29)

**Terms.** T1c = a lane (2026-10-15) that exported Qwen3-1.7B with int8 channelwise weights (`dynamic_wi8_afp32`) and Qwen3-4B with int4 block-32 weights (`dynamic_wi4b32_afp32`) through litert-torch's GPU-composite path (`--apply_gpu_composites=True`, the flag of the Qwen3-0.6B export E2 in `results/raw/2026-10-26-t1b-qwen3-0181-s26-android/`) and compared them with the Hugging Face files of the time on early runtimes (the nightly wheel 0.19.0.dev20261013 and LiteRT-LM main@b7c40ea81). The same comparison on a released LiteRT-LM was left open. The lane's own files (device scripts, plans, tables) are in a private lane repo; the lines this README relies on are restated here. The files of this column:

| label | file (litert-community repo) | role |
|---|---|---|
| N17 | `Qwen3-1.7B_dynamic_wi8_afp32_gpu_composites.litertlm` (Qwen3-1.7B, added 2026-10-27, commit d6678881) | the 1.7B int8 GPU-composite file |
| I17B | `Qwen3_1.7B.litertlm` as it was before 2026-10-31 (lfs sha256 362ec1c9…) | the 1.7B int8 file it is compared with |
| N4 | `Qwen3-4B_dynamic_wi4b32_afp32_gpu_composites.litertlm` (Qwen3-4B, added 2026-10-27, commit a45912eb) | the 4B int4 block-32 GPU-composite file |
| M4B | `qwen3_4b_mixed_int4.litertlm` as it was before 2026-10-31 (lfs sha256 569fe029…) | the 4B file it is compared with |
| W17B | `Qwen3-1.7B_dynamic_wi4b32_afp32.litertlm` (lfs sha256 2a72330b…, unchanged since) | the file of the 1.7B GPU cells of `matrices/dashboard-text-v1.cells`, alone in its own hold |

**Question.** Do N17 and N4 build their GPU engine on the Galaxy S26 with LiteRT-LM 0.19.0, and how fast are they against I17B and M4B? The phone ran the PyPI `litert-lm-api` 0.19.0 Android (aarch64) wheel on CPython 3.14.8 on the phone (`liblitert-lm.so` 22,656,360 B, sha256 `28fa8433…fc78`, `logs/s26/KIT_kpy_gpu_selftest_1.json`), not this repo's Android build (the repo's pin moved to v0.19.0 on 2026-10-31, c22ebe61).

**Answer: yes.** Both files built the OpenCL engine with every node on the GPU (N17: 436/436, 436/436, 406/406 for prefill_128, prefill_1024 and decode; N4: 556/556, 556/556, 518/518), both answered the eight short questions 8/8, and both were faster than the file they are compared with in the same hold: 1.7B +299.8 % prefill / +93.0 % decode, 4B +42.5 % / +3.6 % (GPU protocol, below).

**How.** One process per leg, `legpy.py` on the phone's CPython importing the wheel:

- protocol = `litert_lm.Benchmark(model, backend, prefill_tokens=1024, decode_tokens=256, max_num_tokens=2048)` (the class the `litert-lm benchmark` CLI runs), one engine, 3 runs; a process's figure = the median of its 3 runs; three processes A / B / C; the row = the median over A / B / C;
- dashboard prompt = `Engine(max_num_tokens=2048, enable_benchmark=True)`, per iteration a new conversation and `send_message(prompt, max_output_tokens=256)`, 2 iterations, with the 1K prompt of T1b's column (sha256 `f64fb515…`, 1,338 tokens);
- eight questions = `Engine(max_num_tokens=1280)`, a session with host-rendered ChatML and the bundle's sampler, one regex per question (GPU, N17 and N4 only);
- CPU protocol = the protocol on the CPU backend, one process per file.

Shared Galaxy S26 hold (SM-S942Q, Android 16, build BP4A.251205.006), JST: ticket `s29q3-s26-e` 13:26:49–14:08:22 (the wheel's selftest, then N17 and I17B), `-f` 14:36:53–15:17:56 (N4 and M4B), `-h` 17:27:58–17:45:12 (W17B); the phone dir was removed at the end of each. Holds `-a` to `-d` (13:08–13:19) stopped before any model leg (a kit push that did not verify, then the selftest's `cannot locate symbol "OpenSSL_add_all_algorithms"`), and hold `-g` (15:40–16:17) ran a Qwen3-0.6B pair whose legs are not in this dir; all of them are in `logs/s26/runlog.txt`.

**Numbers** (these holds only; not pooled with T1c's 2026-10-15 columns or with any page row):

| row | N17 | I17B | N4 | M4B |
|---|---|---|---|---|
| GPU protocol 1024 / 256, median over 3 processes (prefill / decode tok/s) | 2,063.7 / 29.69 | 516.1 / 15.39 | 525.6 / 19.54 | 368.9 / 18.86 |
| against the compared file | +299.8 % / +93.0 % | — | +42.5 % / +3.6 % | — |
| GPU dashboard prompt (1,338 tokens), prefill then decode, iterations 1 / 2 | 1,690.3 / 1,396.2; 27.9 / 28.3 | 583.2 / 471.2; 17.5 / 15.2 | 429.1 / 419.0; 18.7 / 18.8 | 322.8 / 299.3; 18.3 / 18.3 |
| eight questions (GPU, bundle sampler) | 8/8 | not run | 8/8 | not run |
| CPU protocol 1024 / 256, one process | 250.6 / 15.09 | 190.5 / 8.01 | 41.1 / 9.69 | 40.8 / 3.11 |

W17B alone (hold `-h`): GPU protocol 1,187.0 / 38.80; dashboard prompt 978.8 / 965.7 prefill, 36.9 / 37.4 decode; CPU protocol 107.2 / 17.69.

- Every GPU protocol process of the four files started with the GPU at 1300 MHz and power level 0 (`kgsl` in `RESULTS.md`). M4B's process A started at thermal status 1 (`ready=False`); its B and C, and every other protocol process of the four files, at 0.
- Inside a GPU process the third run's prefill is lower than the first's (N17 A: 2,392.2 / 2,061.1 / 1,573.1 tok/s; N4 A: 534.6 / 528.2 / 481.7); the row takes each process's median run, as above.
- The CPU rows are one process each with both CPU clusters' ceilings at their maximum at the start of the leg; their runs fall too (N17: 344.1 / 248.8 / 250.6 prefill). Sustained figures, not a headline.
- I17B's separate embedder subgraphs (`decode_embedder`, `prefill_embedder_128`) delegate 1 of 4 nodes to XNNPACK; every other subgraph of the four files ran all its nodes on LITERT_CL (dashboard-prompt legs, `RESULTS.md`).

**After this sitting.** On 2026-10-31 litert-community/Qwen3-1.7B (commit ebb4eef4, 04:56 UTC) and litert-community/Qwen3-4B (commit 965e091f, 05:08 UTC) replaced `Qwen3_1.7B.litertlm` and `qwen3_4b_mixed_int4.litertlm` "with the GPU-composite export" (the commit titles); the names now hold 1,754,890,240 B (lfs `e4059962…`) and 2,272,935,936 B (lfs `4877b236…`), and the `_gpu_composites` names are no longer in the main tree. This dir holds no run of the bytes now under the kept names. The Android cells download their file by name from main (`android/bench/run_cell.py`, `hf_hub_download(model_id, fname)`) and push it again when its sha256 differs, so from the first sitting on the v0.19.0 pin the 1.7B CPU cells and both 4B cells run those bytes; the 1.7B GPU cells run W17B, which did not change.

**Files.** `RESULTS.md` (the lane's `summarize.py` run on this dir's `logs/s26/` on 2026-11-01), `logs/s26/` (each leg's stderr, parsed JSON, meta and stdout for N17, I17B, N4, M4B, W17B and the wheel's selftest; `runlog.txt`, the keeper's log of every hold of the day; `device_props.txt`). The legs' logcat files are left out: they carry other processes' lines.

Nothing here is a schema record: `scripts/build_summary.py` reads only `app-path*/` and `device-jsonl/` JSON, so `results/summary` does not change.
