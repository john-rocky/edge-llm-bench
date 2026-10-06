# 2026-10-06-dashboard-longctx1024-v1-s26-b1-android — notes

Hand-run round-mode sitting of the 1024 / 256 set (task `long-context-1024-gen256`) on the
**Galaxy S26** (SM-S942Q `RFGL80R6A6H`, Android 16, patch 2026-08-05, SM8850; USB, charging,
screen off = `mWakefulness=Dozing`, `stay_on_while_plugged_in=0`; unmasked, `BENCH_CPU_MASK=`).
Engines: LiteRT-LM v0.16.0 (`litert_lm_advanced_main` two-iteration path for the 1024 rows,
`litert_lm_main` for the short-chat anchor), llama.cpp b8999 (`llama-cli -st`).
Not a dashboard-job sitting (no SESSION.json, no admission). The android rows of
`matrices/dashboard-longctx1024-v1-android-{a,b1,b2}.cells` were split by model into five
campaigns (`-s26-a1` Qwen3-0.6B, `-a2` Qwen3-1.7B, `-a3` Gemma 4 E2B, `-b1` Qwen3-4B, `-b2` Gemma 4
E4B), each with the two session anchors at `runs=1` (one anchor launch per round, the shape of
`matrices/dashboard-longctx-v1-android-s26.cells`); the 1024 rows are verbatim. Command:
`ROUNDS=3 BENCH_TEXT_CHECK=1 BENCH_ANDROID_SERIAL=RFGL80R6A6H BENCH_CPU_MASK= ./bench matrix
<file> --platform android --campaign 2026-10-06-dashboard-longctx1024-v1-s26-<x>` (round mode:
gate off, one launch per cell per round, order reversed on even rounds, COOLDOWN 120 s,
THERMAL_WAIT 600 s). A LiteRT 1024 launch writes two records (iteration 1 cold, iteration 2
warm) and its decoded texts (`*.decoded.txt`, textCheck in the record); a llama.cpp launch
writes one record without token counts (b8999 prints only `[ Prompt: X t/s | Generation: Y t/s ]`;
`-n 256` caps the output). Expected 21 records = 7 per round x 3. The device hold
(`community_accel_work/s2_npu_sweep/.device_hold`) was taken per campaign through
`queue_cli.py` and given back after it; before each campaign a preflight waited for battery
<= 33.0 C and no CPU-frequency cap.

Cells of this campaign:

```
android litert-lm litert-community/Qwen3-0.6B short-chat anchor=1 runs=1 backend=gpu file=qwen3_0_6b_mixed_int4.litertlm
android llama.cpp unsloth/Qwen3-0.6B-GGUF short-chat anchor=1 runs=1 file=Qwen3-0.6B-Q4_K_M.gguf
android litert-lm litert-community/Qwen3-4B long-context-1024-gen256 backend=cpu cooldown=300 file=qwen3_4b_mixed_int4.litertlm context-tokens=2048
android litert-lm litert-community/Qwen3-4B long-context-1024-gen256 backend=gpu cooldown=300 file=qwen3_4b_mixed_int4.litertlm context-tokens=2048
android llama.cpp unsloth/Qwen3-4B-GGUF long-context-1024-gen256 cooldown=300 file=Qwen3-4B-Q4_K_M.gguf context-tokens=2048
```

Hold 17:04:56–18:06:46 JST. At the hold the phone was at battery 37.6 C with one CPU policy
capped at 2227/4742 MHz (after a3); the preflight waited 8 min (32.9 C, no cap). 21 / 21
records, textCheck 12 / 12 PASS, FAILURES none. Launches ended at thermal `light` / `moderate`;
the runner's thermal gate waited for status 0 before each launch. LiteRT CPU Qwen3-4B
(`qwen3_4b_mixed_int4.litertlm`): prefill 40 tok/s (TTFT about 34 s), decode about 2.8–3.2 tok/s,
VmHWM 7.4 GB; llama.cpp Qwen3-4B prefill 13 tok/s.
The rows' `cooldown=300` is not read in round mode: the runner sleeps COOLDOWN (120 s) before every launch and then waits for thermal status 0.
