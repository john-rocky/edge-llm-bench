# 2026-10-09 — Gemma 3 1B IT int4 on DDP Galaxy S25 Ultra (pa3q-35), gpu and cpu, lined up with the LiteRT team's test arguments

Second model of the line-up with the LiteRT team's internal S25 Ultra numbers (the first was Gemma 4 E2B on 2026-10-08,
`results/raw/2026-10-07-ddp-s25ultra-lm-v1/iter-check/`). The public bundle litert-community/Gemma3-1B-IT
`gemma3-1b-it-int4.litertlm` (current version, sha256 1325ae36…98be, 584,417,280 bytes, verified against the Hub API
before the first session) ran on the Developer Device Platform (DDP) device pool `pa3q-35` through `litert benchmark
--ddp` with LiteRT-LM's benchmark binary, at the team's arguments: prefill 1024 / decode 256, max tokens 4096 (the
bundle's metadata sets no limit, so the team's test gets the engine default 4096; the benchmark binary would pick 1280
on its own, so 4096 is passed explicitly), one cycle per process, three sessions per backend, order gpu, cpu, gpu, cpu,
gpu, cpu. Every session PASSED at the first try, both processes exit 0, no error line, max_tokens 4096 in every args
row and settings dump. The numbers and the reading are in `table-aligned.md`; the first table there (median [min–max]
per backend × cold / cached) is the one to quote. Single runtime, one model: nothing here compares runtimes, and
nothing is added to the leaderboard data (no run record in the result.v1 shape; `results/summary/` is unchanged). The
six uploaded input dirs were removed from the project bucket after the round (inputs back to 11,680,278,877 bytes;
session outputs stay). The 10-08 lane's venv was gone, so the same CLI version (litert-cli-nightly 0.3.0.dev20261006,
the cached wheel) was installed into a new one; the binary is the same bucket object (sha adac974b…2d06).
