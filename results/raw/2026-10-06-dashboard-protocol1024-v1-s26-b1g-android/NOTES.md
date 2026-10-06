# 2026-10-06-dashboard-protocol1024-v1-s26-b1g-android — notes

Hand-run sitting of the protocol rows (task `native-benchmark-1024x256`: the engines' own synthetic
benchmarks, prefill forced to exactly 1024 tokens with no prompt, decode 256) on the **Galaxy S26**
(SM-S942Q `RFGL80R6A6H`, Android 16, SM8850; USB, charging, screen off; unmasked, `BENCH_CPU_MASK=`).
Engines: LiteRT-LM v0.16.0 `litert_lm_advanced_main --benchmark --benchmark_prefill_tokens=1024
--benchmark_decode_tokens=256 --max_num_tokens=2048` (one cold process per run), llama.cpp b8999
`llama-bench -p 1024 -n 256 -o json` (its default repetitions and warmup; coldRun false), and
`litert_lm_main` / `llama-cli` for the two short-chat session anchors. Not a dashboard-job sitting
(no SESSION.json, no admission). The android rows of `matrices/dashboard-protocol1024-v1-android.cells`
were split into eight campaigns (`-s26-a1` Qwen3-0.6B, `-a2` Qwen3-1.7B, `-a3l` / `-a3g` Gemma 4 E2B
LiteRT-LM / llama.cpp, `-b1l` / `-b1g` Qwen3-4B, `-b2l` / `-b2g` Gemma 4 E4B) so that each device hold
stays near 45 minutes (non-round mode sleeps the row's cooldown before every launch: 300 s for the
Gemma 4 and 4B rows); each campaign carries the two session anchors at `runs=1`; the payload rows are
verbatim. This one: Qwen3-4B, llama.cpp. Command: `BENCH_ANDROID_SERIAL=RFGL80R6A6H BENCH_CPU_MASK= ./bench matrix
<file> --platform android --campaign 2026-10-06-dashboard-protocol1024-v1-s26-b1g` (non-round mode:
anchors first, then the payload interleaved per run, three runs per row, the capture gate on).

Cells of this campaign:

```
android litert-lm litert-community/Qwen3-0.6B short-chat anchor=1 runs=1 backend=gpu file=qwen3_0_6b_mixed_int4.litertlm
android llama.cpp unsloth/Qwen3-0.6B-GGUF short-chat anchor=1 runs=1 file=Qwen3-0.6B-Q4_K_M.gguf
android llama.cpp unsloth/Qwen3-4B-GGUF native-benchmark-1024x256 cooldown=300 file=Qwen3-4B-Q4_K_M.gguf
```

Hold (`community_accel_work/s2_npu_sweep/.device_hold`, taken through `queue_cli.py`) 00:30:45–01:38:46 JST.
Preflight under the hold: free 18.6 GB, battery 32.8 C, thermal status 0, caps none, uptime 100.62 h, MemAvailable 7.31 GB, swap 2.05 GB, mWakefulness=Awake (waited 5 min for battery <= 33.0 C and no CPU cap).
Records 5 / expected 5; payload prompt / generated token counts [(1024, 256)]; firstEver
0; thermal start->end ['moderate->critical', 'nominal->nominal', 'nominal->severe', 'severe->critical']; engines ['litert-lm-gpu v0.16.0', 'llama.cpp b8999'].
Gate retries: 1
- gate retry llama.cpp unsloth/Qwen3-4B-GGUF native-benchmark-1024x256 verdict=SPREAD 12.9 (block re-run, not interleaved)
Quarantined captures (kept, outside the summary glob): 3 `*.json.attempt1`.
FAILURES: none. FLAGGED: 1
- GATE_FAIL llama.cpp unsloth/Qwen3-4B-GGUF native-benchmark-1024x256 first='SPREAD 12.9' retry='HOT nominal,moderate,severe' (retry kept; ⚠ downstream).
