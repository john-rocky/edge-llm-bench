# Context-length A/B on four CPUs (2026-09-02/03) — the K5 primary logs

Copied from the YNNPACK task work so the public record of LiteRT-LM #2568 has
them. Model: gemma-3-270m-it, dynamic int8 export (litert-torch-nightly
0.10.0.dev20260831, prefill 128/1024). Binary: `litert_lm_advanced_main` built
from LiteRT-LM main `c363e172` (2026-09-01), XNNPACK path = the "A" side of
each pair (`--enable_ynnpack` off); the "B" side is the experimental YNNPACK
delegate. `--benchmark --benchmark_prefill_tokens=1024 --benchmark_decode_tokens=256`,
8 paired reps, driver `bench_ab.py`; each directory holds `runs.jsonl` (per-rep speeds + flags; the per-rep engine logs stay in the
lab tree, 23 MB). `*_maxtokNNNN` = 1024-token prefill under `--max_num_tokens=NNNN`;
`*_prefillNNNN` = the cache filled by an NNNN-token prefill. `prof_m4/` = the
M4 Max `--enable_profiling` runs, parsed by `prof_summarize.py`.

Decode tok/s, XNNPACK side, medians (max_num_tokens 1280 / 2048 / 4096):
M4 Max 190.8 / 161.7 / 124.6; Galaxy S26 139.9 / 117.0 / 80.2; Pixel 8a 66.9 /
55.2 / 40.2; Raspberry Pi 5 23.7 / 17.7 / 11.8. Filled-cache rows: Pi 5 17.5
(P2048) / 11.6 (P4096); M4 Max 156.1 (P2048, max 2304) / 121.1 (P4096, max 4352).
