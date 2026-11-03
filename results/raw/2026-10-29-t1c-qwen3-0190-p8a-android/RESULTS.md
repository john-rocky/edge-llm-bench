# RESULTS — Pixel 8a, PyPI litert-lm-api 0.19.0 Android wheel (2026-10-29; N4 sittings 2026-11-02 and 2026-11-03)

Generated on 2026-11-02 by the lane's `summarize.py` from `logs/p8a/` of this dir (its only arithmetic: the median over runs and processes, and the new-vs-compared ratio). The output follows as printed, its device header line with this dir's path. The two dated sections after it were made the same way on their days, from `logs/p8a-2026-11-02/` and `logs/p8a-2026-11-03/`.

```

## Pixel 8a (logs/p8a), PyPI litert-lm-api 0.19.0 Android wheel on CPython 3.14.8
device: 2026-10-29 15:24:47 model=Pixel 8a release=16 build_id=CP1A.260505.005 fingerprint=google/akita/akita:16/CP1A.260505.005/15081906:user/release-keys
selftest: exit 0, versions {'python': '3.14.8', 'platform': 'android', 'machine': 'aarch64', 'litert-lm-api': '0.19.0'}, lib sha256 28fa8433febc49a9

### N17 vs I17B
- GPU dashboard leg N17 (cold): exit 0, prefill 584.5 / 597.6 tok/s (1338 tokens), decode 13.9 / 14.3 tok/s (iterations), topic words 10, deleg [prefill_128 436/436 CL; prefill_1024 436/436 CL; decode 406/406 CL], errors 1, first: 10-29 13:22:58.732  9747  9747 E libEGL  : call to OpenGL ES API with no current context (logged once per thread)
- GPU dashboard leg I17B (keep): exit 0, prefill 233.8 / 237.6 tok/s (1338 tokens), decode 9.0 / 9.0 tok/s (iterations), topic words 11, deleg [prefill_128 1298/1298 CL; decode 1244/1244 CL; decode_embedder 1/4 XNN; prefill_embedder_128 1/4 XNN], errors 1, first: 10-29 13:50:58.215 16532 16532 E libEGL  : call to OpenGL ES API with no current context (logged once per thread)
- GPU protocol N17: median over 3 processes 753.9 / 14.83 tok/s; A 758.7 / 14.79 (runs 751.2 / 762.0 / 758.7; ready=True, thermal 1, kgsl none); B 753.9 / 14.88 (runs 745.3 / 753.9 / 756.4; ready=True, thermal 1, kgsl none); C 751.2 / 14.83 (runs 742.0 / 751.3 / 751.2; ready=True, thermal 1, kgsl none)
- GPU protocol I17B: median over 3 processes 251.8 / 9.01 tok/s; A 249.9 / 8.96 (runs 249.6 / 249.9 / 249.9; ready=True, thermal 1, kgsl none); B 251.9 / 9.02 (runs 248.7 / 252.8 / 251.9; ready=True, thermal 1, kgsl none); C 251.8 / 9.01 (runs 251.1 / 252.4 / 251.8; ready=True, thermal 1, kgsl none)
- new vs current (GPU): prefill +199.5 %, decode +64.6 %
- 8Q N17 (Session, bundle sampler): 8/8: q1 ok ['17 + 25 = 42.'] | q2 ok ['The capital of Japan is Tokyo.'] | q3 ok ['Cold.'] | q4 ok ['A week has 7 days.'] | q5 ok ['"Merci" is how you say "thank you" in French.'] | q6 ok ['56'] | q7 ok ['0.9 is larger than 0.11.'] | q8 ok ['Roses are red, violets are blue.']
- CPU protocol A N17: 52.8 / 5.46 tok/s (runs prefill 78.5 / 52.8 / 51.3, decode 5.99 / 5.46 / 4.40; ceilings at start policy0:1704000/1704000,policy4:2367000/2367000,policy8:2914000/2914000; exit 0)
- CPU protocol A I17B: 35.7 / 3.40 tok/s (runs prefill 73.8 / 35.4 / 35.7, decode 4.26 / 3.40 / 2.78; ceilings at start policy0:1704000/1704000,policy4:2367000/2367000,policy8:2914000/2914000; exit 0)
- new vs current (CPU, one process each): prefill +47.9 %, decode +60.8 %

### W17B (control alone, its own sitting)
- GPU protocol W17B: median over 3 processes 271.3 / 19.46 tok/s; A 270.1 / 19.49 (exit 0); B 271.3 / 19.46 (exit 0); C 272.4 / 19.33 (exit 0)
- GPU dashboard leg W17B: exit 0, prefill 236.6 / 239.7, decode 18.7 / 19.0, topic words 10
- CPU protocol A W17B: 39.4 / 6.68 tok/s (exit 0)
```

## 2026-11-02: N4, one GPU protocol process (its own sitting)

The same tool on `logs/p8a-2026-11-02/` (2026-11-02), as printed, its device header line with this dir's path:

```

## Pixel 8a (logs/p8a-2026-11-02), PyPI litert-lm-api 0.19.0 Android wheel on CPython 3.14.8
device: 2026-11-02 16:46:40 model=Pixel 8a release=16 build_id=CP1A.260505.005 fingerprint=google/akita/akita:16/CP1A.260505.005/15081906:user/release-keys
selftest: exit 0, versions {'python': '3.14.8', 'platform': 'android', 'machine': 'aarch64', 'litert-lm-api': '0.19.0'}, lib sha256 28fa8433febc49a9

### N4 vs M4B
- GPU protocol N4: median over 0 processes - / - tok/s; A - / - (runs ; ready=True, thermal 0, kgsl none; exit 137: 11-02 16:48:29.306  6398  6398 E libEGL  : call to OpenGL ES API with no current context (logged once per thread))
```

The process's own stop line (`logs/p8a-2026-11-02/N4_kpy_gpu_proto_A.err`, last line; the parsed `memguard_line` of `N4_kpy_gpu_proto_A.json`): `MEMGUARD: MemAvailable 140776 kB < 400000 at 1793605749: killed`.

## 2026-11-03: N4, one GPU and one CPU protocol process (its own sitting)

The same tool on `logs/p8a-2026-11-03/` (2026-11-03), as printed, its device header line with this dir's path:

```

## Pixel 8a (logs/p8a-2026-11-03), PyPI litert-lm-api 0.19.0 Android wheel on CPython 3.14.8
device: 2026-11-03 12:19:27 model=Pixel 8a release=16 build_id=CP1A.260505.005 fingerprint=google/akita/akita:16/CP1A.260505.005/15081906:user/release-keys
selftest: exit 0, versions {'python': '3.14.8', 'platform': 'android', 'machine': 'aarch64', 'litert-lm-api': '0.19.0'}, lib sha256 28fa8433febc49a9

### N4 vs M4B
- GPU protocol N4: median over 0 processes - / - tok/s; A - / - (runs ; ready=True, thermal 0, kgsl none; exit 137: 11-03 12:22:10.328  3579  3579 E libEGL  : call to OpenGL ES API with no current context (logged once per thread))
- CPU protocol A N4: 16.7 / 4.89 tok/s (runs prefill 24.7 / 16.7 / 12.9, decode 5.46 / 4.60 / 4.89; ceilings at start policy0:1704000/1704000,policy4:2367000/2367000,policy8:2914000/2914000; exit 0)
```

The GPU process's own stop line (`logs/p8a-2026-11-03/N4_kpy_gpu_proto_A.err`, last line): `MEMGUARD: MemAvailable 360076 kB < 400000 at 1793676206: killed`. Its first run finished before the stop. That run is in its stdout (`N4_kpy_gpu_proto_A.out`) and not in the tool's line above, because `legpy.py` prints the run list in one line at the end of the process, which a stopped process never reaches. It is one run of a stopped process, not a rate: `iteration 1: prefill 106.2 tok/s (1024), decode 9.59 tok/s (256), init 74845 ms, ttft 9.748 s`.
