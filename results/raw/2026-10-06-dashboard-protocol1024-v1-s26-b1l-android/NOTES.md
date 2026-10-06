# 2026-10-06-dashboard-protocol1024-v1-s26-b1l-android — notes

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
verbatim. This one: Qwen3-4B, LiteRT-LM cpu + gpu. Command: `BENCH_ANDROID_SERIAL=RFGL80R6A6H BENCH_CPU_MASK= ./bench matrix
<file> --platform android --campaign 2026-10-06-dashboard-protocol1024-v1-s26-b1l` (non-round mode:
anchors first, then the payload interleaved per run, three runs per row, the capture gate on).

Cells of this campaign:

```
android litert-lm litert-community/Qwen3-0.6B short-chat anchor=1 runs=1 backend=gpu file=qwen3_0_6b_mixed_int4.litertlm
android llama.cpp unsloth/Qwen3-0.6B-GGUF short-chat anchor=1 runs=1 file=Qwen3-0.6B-Q4_K_M.gguf
android litert-lm litert-community/Qwen3-4B native-benchmark-1024x256 backend=cpu cooldown=300 file=qwen3_4b_mixed_int4.litertlm context-tokens=2048
android litert-lm litert-community/Qwen3-4B native-benchmark-1024x256 backend=gpu cooldown=300 file=qwen3_4b_mixed_int4.litertlm context-tokens=2048
```

Hold (`community_accel_work/s2_npu_sweep/.device_hold`, taken through `queue_cli.py`) 23:40:46–00:30:45 JST.
Preflight under the hold: free 18.6 GB, battery 33.0 C, thermal status 0, caps none, uptime 99.89 h, MemAvailable 6.94 GB, swap 2.39 GB, mWakefulness=Dozing (waited 11 min for battery <= 33.0 C and no CPU cap).
Records 8 / expected 8; payload prompt / generated token counts [(1024, 256)]; firstEver
0; thermal start->end ['nominal->nominal']; engines ['litert-lm-cpu v0.16.0', 'litert-lm-gpu v0.16.0', 'llama.cpp b8999'].
Gate retries: 0
FAILURES: none. FLAGGED: none.
