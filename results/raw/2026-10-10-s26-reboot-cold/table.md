# Galaxy S26 (SM-S942Q): a first process after a reboot against a first process right after the model file was written — LiteRT-LM benchmark binary, 2026-10-10

Question: does a benchmark process whose model file has not been read since the phone booted read slower than one started right after the file was pushed? (The shape of a benchmark app's first pass after APK start and model transfer, against the shape of a DDP session's first process after its push.) One run per setting; nothing here is a measurement with a spread.

Binary: `litert_lm_advanced_main` from `gs://litert/binaries/latest/android_arm64/litert_lm/` (object dated 2026-09-18, sha256 `adac974b…2d06`, checked on the phone) with its six libraries (sha256 of each in `steps.log`). Arguments, every process: `--benchmark=true --benchmark_prefill_tokens=1024 --benchmark_decode_tokens=256 --max_num_tokens=4096 --num_iterations=1 --report_peak_memory_footprint=true`, `--backend=gpu` for Gemma 4 E2B, `--backend=cpu` for Gemma 3 1B (`number_of_threads: 4` in the log; the GPU path is OpenCL per the log). `max_tokens: 4096` in every settings dump. Bundles: `gemma-4-E2B-it.litertlm` (litert-community, sha256 `18193810…a63c`, 2,588,147,712 bytes) and `gemma3-1b-it-int4.litertlm` (litert-community/Gemma3-1B-IT, sha256 `1325ae36…98be`, 584,417,280 bytes); both sha256 checked on the phone before the reboot and again after the runs (the bundles were not read between the boot and their first process). Screen dozing during every run; no other hold on the phone; battery 79 %.

Sequence (JST): R0 / R0b at 09:07–09:08 on the phone that had been up 7.5 days (the E2B copy written 12 s before R0); reboot at 09:08:24; the phone showed no adb device until its first unlock, which came at 12:4x (`steps.log`: the v1 script gave up at 09:20, v2 waited until 10:21 and gave up, v2 relaunched at 12:44); 60 s settle + screen off; G1–G4, C1–C4 at 12:45–12:51 with 30 s between processes. Uptime at G1: 13,038 s (3.6 h after the boot).

| tag | backend / bundle | model file state | caches at start | prefill tok/s | decode tok/s | TTFT s | init ms | peak private MB | exit | error lines (binary) |
|---|---|---|---|---:|---:|---:|---:|---:|---|---:|
| R0 | gpu / Gemma 4 E2B | written 12 s earlier (copied on the phone), before the reboot | 0 | 2862.25 | 45.44 | 0.38 | 6594.56 | 752.2 | 0 | 0 |
| R0b | gpu / Gemma 4 E2B | same, caches present | 2 | 3093.73 | 44.10 | 0.35 | 2362.44 | 724.4 | 0 | 0 |
| G1 | gpu / Gemma 4 E2B | not read since the boot (3.6 h earlier) | 0 | 2847.86 | 47.04 | 0.38 | 5369.63 | 757.2 | 0 | 0 |
| G2 | gpu / Gemma 4 E2B | same, caches present | 2 | 3187.12 | 45.70 | 0.34 | 1860.25 | 728.5 | 0 | 0 |
| G3 | gpu / Gemma 4 E2B | written 11 s earlier (copied on the phone again) | 0 | 2834.41 | 46.58 | 0.38 | 6323.62 | 764.6 | 0 | 0 |
| G4 | gpu / Gemma 4 E2B | same, caches present | 2 | 3200.73 | 45.82 | 0.34 | 2206.23 | 730.0 | 0 | 0 |
| C1 | cpu / Gemma 3 1B | not read since the boot | 0 | 1003.28 | 52.73 | 1.04 | 3566.31 | 1377.2 | 0 | 0 |
| C2 | cpu / Gemma 3 1B | same, caches present | 1 | 1010.94 | 53.50 | 1.03 | 486.72 | 1229.5 | 0 | 0 |
| C3 | cpu / Gemma 3 1B | written 13 s earlier (pushed from the Mac again) | 0 | 1010.78 | 52.82 | 1.03 | 1701.20 | 1376.8 | 0 | 0 |
| C4 | cpu / Gemma 3 1B | same, caches present | 1 | 1005.10 | 53.69 | 1.04 | 493.56 | 1229.7 | 0 | 0 |

"caches at start" = the ML Drift cache files (gpu) or the XNNPACK cache (cpu) in the run directory; a process with 0 writes them. The G1 logcat window holds one line matching the error pattern, from the system (`FreecessController … Failed to read pid …`), none from the binary. Values from the binary's log lines (`Prefill Speed`, `Decode Speed`, `Time To First Token`, `Init Total`, `Peak private footprint`); `metrics-<tag>.pb` holds the same cycle.

## Reading (this phone only; the S26 is a different SoC from the S25 Ultra pool, so values do not transfer, only the comparison within this table)

- Gemma 4 E2B, gpu: the first process after the reboot (G1, file not read since the boot) reads 2847.86 prefill / 47.04 decode against 2834.41 / 46.58 for a first process right after the file was written (G3) and 2862.25 / 45.44 before the reboot (R0): the same within 1 % on prefill. Init 5369.63 ms (G1) against 6323.62 (G3) and 6594.56 (R0): not longer after the boot. The cached processes (G2, G4, R0b) read 3093.73–3200.73 prefill, 10–12 % above the cold ones, init 1860–2362 ms.
- Gemma 3 1B, cpu: the first process after the reboot (C1) reads 1003.28 prefill / 52.73 decode against 1010.78 / 52.82 right after the push (C3): equal within 1 %. Init is where the two differ: 3566.31 ms (C1) against 1701.20 (C3) and 486.72–493.56 cached — reading a 584 MB file that is not in the page cache costs about 1.9 s of init on this phone and nothing on prefill, decode or TTFT.
- So on this phone, with this binary, a first process whose model file has not been read since the boot does not read a lower prefill or decode than a first process right after the push; the file state shows only in init, and only on cpu here.

Files: `steps.log` (every step with its time, the v1 reboot attempt and the waits included), `<tag>.stdout.txt`, `<tag>.logcat.txt` (the logcat window of each process), `metrics-<tag>.pb`, `run-log.txt` (the scripts' own output), `tools/s26_reboot_cold.sh` (v1: R0, R0b, the reboot) and `tools/s26_reboot_cold_v2.sh` (G1–C4). Not rows of `results/summary`; not added to any leaderboard data.
