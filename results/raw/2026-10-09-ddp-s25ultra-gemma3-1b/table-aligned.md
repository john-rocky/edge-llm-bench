# Gemma 3 1B IT int4 on DDP Galaxy S25 Ultra (pa3q-35), gpu and cpu, three sessions each, lined up with the LiteRT team's test arguments — 2026-10-09

Bundle: litert-community/Gemma3-1B-IT `gemma3-1b-it-int4.litertlm`, current version (Hub commit 42d538a9, 2025-08-15;
sha256 `1325ae366d31950f137c9c357b9fa89448b176d76998180c08ceaca78bba98be`, 584,417,280 bytes; the same bytes are
published as `Gemma3-1B-IT_multi-prefill-seq_q4_ekv4096.litertlm`). Its LlmMetadata carries no max_num_tokens
(`peek/gemma3-1b-litertlm-peek-2026-10-09.txt`, litert-lm-builder 0.18.0), so an app that sets no limit gets the engine
default, 4096 for a 1024-token prompt.

Arguments: `litert benchmark <bundle> --ddp --device pa3q-35 --gpu|--cpu --num-iterations 1 --warmup-runs 0
--max-num-tokens 4096`, the rest at the CLI defaults (prefill 1024 / decode 256). CLI litert-cli-nightly
0.3.0.dev20261006; binary `gs://litert/binaries/latest/android_arm64/litert_lm/litert_lm_advanced_main` (object dated
2026-09-18, sha256 adac974b…2d06 in every provenance.txt). Each session runs the binary twice in one job: the first
process starts without caches (cold; it writes the ML Drift caches on the gpu, the XNNPACK cache on the cpu), the
measured process starts with them (cached). One cycle per process. Six sessions, order gpu, cpu, gpu, cpu, gpu, cpu,
10:43–11:09 JST, each PASSED at the first try. The gpu path is OpenCL (the binary's log); the cpu path runs 4 threads.

The first table is the one to quote: per backend and process the median over the three sessions with [min–max].
The other side's numbers are not in this file.

| backend | process | n | prefill tok/s median [min–max] | decode tok/s | TTFT s | init ms | peak mem MB | sessions | device builds |
|---|---|---:|---|---|---|---|---|---|---|
| gpu | first (cold, no caches) | 3 | 2534.9 [2531.1–2537.8] | 47.41 [47.04–47.59] | 0.430 [0.420–0.430] | 4958 [4954–4987] | 870.0 [869.3–870.7] | session-9877d6db, session-ae06ef8d, session-ecc7faac | S938U1UEU2AYD9, S938U1UEU1AYB3, S938U1UEU2AYD9 |
| gpu | measured (cached) | 3 | 2516.5 [2507.5–2530.2] | 47.98 [47.02–48.34] | 0.428 [0.426–0.430] | 2290 [2271–2432] | 813.2 [813.1–813.2] | session-9877d6db, session-ae06ef8d, session-ecc7faac | S938U1UEU2AYD9, S938U1UEU1AYB3, S938U1UEU2AYD9 |
| cpu | first (cold, no caches) | 3 | 381.2 [380.7–383.8] | 56.68 [56.56–56.68] | 2.700 [2.690–2.710] | 1528 [1484–1588] | 1585.9 [1408.7–1591.1] | session-416669e7, session-4afc8fc2, session-b315a4d7 | S938U1UEU2AYD9, S938U1UEU1AYB3, S938U1UEU1AYB3 |
| cpu | measured (cached) | 3 | 365.4 [362.7–368.5] | 56.23 [55.66–56.81] | 2.820 [2.797–2.841] | 302 [296–302] | 1175.0 [1173.5–1176.2] | session-416669e7, session-4afc8fc2, session-b315a4d7 | S938U1UEU2AYD9, S938U1UEU1AYB3, S938U1UEU1AYB3 |

| backend | session | process | prefill tok/s | decode tok/s | TTFT s | init ms | peak mem MB | device build | date (device clock) |
|---|---|---|---:|---:|---:|---:|---:|---|---|
| gpu | session-9877d6db | first (cold, no caches) | 2531.1 | 47.59 | 0.430 | 4987 | 870.7 | S938U1UEU2AYD9 | Thu Oct  8 18:45:50 PDT 2026 |
| gpu | session-9877d6db | measured (cached) | 2507.5 | 47.02 | 0.430 | 2271 | 813.1 | S938U1UEU2AYD9 | Thu Oct  8 18:45:50 PDT 2026 |
| gpu | session-ae06ef8d | first (cold, no caches) | 2537.8 | 47.41 | 0.420 | 4954 | 870.0 | S938U1UEU1AYB3 | Thu Oct  8 18:52:26 PDT 2026 |
| gpu | session-ae06ef8d | measured (cached) | 2516.5 | 48.34 | 0.428 | 2290 | 813.2 | S938U1UEU1AYB3 | Thu Oct  8 18:52:26 PDT 2026 |
| gpu | session-ecc7faac | first (cold, no caches) | 2534.9 | 47.04 | 0.430 | 4958 | 869.3 | S938U1UEU2AYD9 | Thu Oct  8 19:04:55 PDT 2026 |
| gpu | session-ecc7faac | measured (cached) | 2530.2 | 47.98 | 0.426 | 2432 | 813.2 | S938U1UEU2AYD9 | Thu Oct  8 19:04:55 PDT 2026 |
| cpu | session-416669e7 | first (cold, no caches) | 383.8 | 56.68 | 2.690 | 1528 | 1591.1 | S938U1UEU2AYD9 | Thu Oct  8 18:49:05 PDT 2026 |
| cpu | session-416669e7 | measured (cached) | 368.5 | 55.66 | 2.797 | 302 | 1176.2 | S938U1UEU2AYD9 | Thu Oct  8 18:49:05 PDT 2026 |
| cpu | session-4afc8fc2 | first (cold, no caches) | 380.7 | 56.56 | 2.710 | 1588 | 1585.9 | S938U1UEU1AYB3 | Thu Oct  8 18:57:23 PDT 2026 |
| cpu | session-4afc8fc2 | measured (cached) | 362.7 | 56.23 | 2.841 | 302 | 1175.0 | S938U1UEU1AYB3 | Thu Oct  8 18:57:23 PDT 2026 |
| cpu | session-b315a4d7 | first (cold, no caches) | 381.2 | 56.68 | 2.700 | 1484 | 1408.7 | S938U1UEU1AYB3 | Thu Oct  8 19:08:11 PDT 2026 |
| cpu | session-b315a4d7 | measured (cached) | 365.4 | 56.81 | 2.820 | 296 | 1173.5 | S938U1UEU1AYB3 | Thu Oct  8 19:08:11 PDT 2026 |

| backend | session | exits | max_num_tokens (args / settings dump) | backend line | error lines | threads | bundle sha256 | binary sha256 |
|---|---|---|---|---|---:|---|---|---|
| gpu | session-9877d6db | warm-up 0, measured 0 | 4096 / 4096 | gpu | 0 | - | 1325ae36… | adac974b… |
| gpu | session-ae06ef8d | warm-up 0, measured 0 | 4096 / 4096 | gpu | 0 | - | 1325ae36… | adac974b… |
| gpu | session-ecc7faac | warm-up 0, measured 0 | 4096 / 4096 | gpu | 0 | - | 1325ae36… | adac974b… |
| cpu | session-416669e7 | warm-up 0, measured 0 | 4096 / 4096 | cpu | 0 | 4 | 1325ae36… | adac974b… |
| cpu | session-4afc8fc2 | warm-up 0, measured 0 | 4096 / 4096 | cpu | 0 | 4 | 1325ae36… | adac974b… |
| cpu | session-b315a4d7 | warm-up 0, measured 0 | 4096 / 4096 | cpu | 0 | 4 | 1325ae36… | adac974b… |

Reading: the gpu rows are tight (prefill spread 0.3 % cold, 0.9 % cached; decode 1.2 % / 2.8 %), and cold and cached
give the same prefill (2535 vs 2517) — unlike Gemma 4 E2B on 10-08, where the cached process was 3–11 % faster. The cpu
cached process is slower in prefill than the cold one (365 vs 381, −4 %), the same direction as Gemma 4 E2B cpu (−6 to
−8 %); cpu decode is the same in both (56.2 vs 56.7). Cold init is 2.2× cached on the gpu (4958 vs 2290 ms) and 5× on
the cpu (1528 vs 302 ms). The cpu first process's peak memory (1409–1591 MB) includes writing the 508 MB XNNPACK cache;
the measured process sits at 1175 MB. The sessions landed on both firmware builds of the pool (AYD9 and AYB3) with no
visible difference between them.

Files: `ddp-session/<session>/<backend>-pa3q-35/` (metrics.pb, metrics.pb.txt, provenance.txt, logcat-process.txt),
`sessions.tsv`, `run-log.txt` (every command, pre-flight checks and the bucket cleanup included), `peek/`, `tools/`
(rl.sh, sess.sh, run-round.sh, gather.py, mktable.py; this file's tables are mktable.py's output).
