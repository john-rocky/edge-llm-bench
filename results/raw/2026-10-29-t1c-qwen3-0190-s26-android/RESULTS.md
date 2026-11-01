# RESULTS — Galaxy S26, PyPI litert-lm-api 0.19.0 Android wheel (2026-10-29)

Generated on 2026-11-01 by the lane's `summarize.py` from `logs/s26/` of this dir (its only arithmetic: the median over runs and processes, and the new-vs-compared ratio). The output follows as printed, its device header line with this dir's path.

```

## Galaxy S26 (logs/s26), PyPI litert-lm-api 0.19.0 Android wheel on CPython 3.14.8
device: 2026-10-29 17:27:59 model=SM-S942Q release=16 build_id=BP4A.251205.006 fingerprint=samsung/m1qjpnx/m1q:16/BP4A.251205.006/S942QOPS1AZH9_SJP1AZH9:user/release-keys
selftest: exit 0, versions {'python': '3.14.8', 'platform': 'android', 'machine': 'aarch64', 'litert-lm-api': '0.19.0'}, lib sha256 28fa8433febc49a9

### N17 vs I17B
- GPU dashboard leg N17 (cold): exit 0, prefill 1,690.3 / 1,396.2 tok/s (1338 tokens), decode 27.9 / 28.3 tok/s (iterations), topic words 12, deleg [prefill_128 436/436 CL; prefill_1024 436/436 CL; decode 406/406 CL], errors 2, first: 10-29 13:29:05.647 26200 26200 E Adreno-AppProfiles: QSPM AIDL service doesn't exist
- GPU dashboard leg I17B (keep): exit 0, prefill 583.2 / 471.2 tok/s (1338 tokens), decode 17.5 / 15.2 tok/s (iterations), topic words 14, deleg [prefill_128 1298/1298 CL; decode 1244/1244 CL; decode_embedder 1/4 XNN; prefill_embedder_128 1/4 XNN], errors 2, first: 10-29 13:48:29.753 31952 31952 E Adreno-AppProfiles: QSPM AIDL service doesn't exist
- GPU protocol N17: median over 3 processes 2,063.7 / 29.69 tok/s; A 2,061.1 / 29.73 (runs 2,392.2 / 2,061.1 / 1,573.1; ready=True, thermal 0, kgsl 1300/0/39500); B 2,392.7 / 29.40 (runs 2,392.7 / 2,393.8 / 1,403.4; ready=True, thermal 0, kgsl 1300/0/41500); C 2,063.7 / 29.69 (runs 2,375.8 / 2,063.7 / 1,594.9; ready=True, thermal 0, kgsl 1300/0/41500)
- GPU protocol I17B: median over 3 processes 516.1 / 15.39 tok/s; A 516.1 / 15.39 (runs 642.1 / 516.1 / 345.5; ready=True, thermal 0, kgsl 1300/0/41500); B 483.5 / 14.92 (runs 620.1 / 483.5 / 343.7; ready=True, thermal 0, kgsl 1300/0/41500); C 526.9 / 16.00 (runs 621.3 / 526.9 / 351.2; ready=True, thermal 0, kgsl 1300/0/41800)
- new vs current (GPU): prefill +299.8 %, decode +93.0 %
- 8Q N17 (Session, bundle sampler): 8/8: q1 ok ['17 + 25 = 42.'] | q2 ok ['The capital of Japan is Tokyo.'] | q3 ok ['Cold.'] | q4 ok ['A week has 7 days.'] | q5 ok ['"Merci" in French.'] | q6 ok ['56'] | q7 ok ['0.9 is larger than 0.11.'] | q8 ok ['Roses are red, violets are blue.']
- CPU protocol A N17: 250.6 / 15.09 tok/s (runs prefill 344.1 / 248.8 / 250.6, decode 17.50 / 15.09 / 13.76; ceilings at start policy0:3628800/3628800,policy6:4742400/4742400; exit 0)
- CPU protocol A I17B: 190.5 / 8.01 tok/s (runs prefill 305.9 / 190.5 / 166.1, decode 9.00 / 8.01 / 7.66; ceilings at start policy0:3628800/3628800,policy6:4742400/4742400; exit 0)
- new vs current (CPU, one process each): prefill +31.6 %, decode +88.3 %

### N4 vs M4B
- GPU dashboard leg N4 (cold): exit 0, prefill 429.1 / 419.0 tok/s (1338 tokens), decode 18.7 / 18.8 tok/s (iterations), topic words 14, deleg [prefill_128 556/556 CL; prefill_1024 556/556 CL; decode 518/518 CL], errors 2, first: 10-29 14:40:04.368  3673  3673 E Adreno-AppProfiles: QSPM AIDL service doesn't exist
- GPU dashboard leg M4B (keep): exit 0, prefill 322.8 / 299.3 tok/s (1338 tokens), decode 18.3 / 18.3 tok/s (iterations), topic words 11, deleg [main 1753/1753 CL; main 1680/1680 CL], errors 2, first: 10-29 15:17:00.749 15788 15788 E Adreno-AppProfiles: QSPM AIDL service doesn't exist
- GPU protocol N4: median over 3 processes 525.6 / 19.54 tok/s; A 528.2 / 19.54 (runs 534.6 / 528.2 / 481.7; ready=True, thermal 0, kgsl 1300/0/41800); B 416.7 / 18.92 (runs 536.1 / 384.8 / 416.7; ready=True, thermal 0, kgsl 1300/0/41500); C 525.6 / 19.56 (runs 534.2 / 525.6 / 478.7; ready=True, thermal 0, kgsl 1300/0/41500)
- GPU protocol M4B: median over 3 processes 368.9 / 18.86 tok/s; A 368.1 / 18.74 (runs 380.2 / 368.1 / 341.6; ready=False, thermal 1, kgsl 1300/0/41500); B 370.8 / 18.86 (runs 377.5 / 370.8 / 346.3; ready=True, thermal 0, kgsl 1300/0/41100); C 368.9 / 18.97 (runs 378.1 / 368.9 / 344.1; ready=True, thermal 0, kgsl 1300/0/41500)
- new vs current (GPU): prefill +42.5 %, decode +3.6 %
- 8Q N4 (Session, bundle sampler): 8/8: q1 ok ['17 + 25 = 42'] | q2 ok ['The capital of Japan is Tokyo.'] | q3 ok ['Cold.'] | q4 ok ['7 days.'] | q5 ok ['Merci.'] | q6 ok ['56'] | q7 ok ['0.9 is larger than 0.11.'] | q8 ok ['Blue.']
- CPU protocol A N4: 41.1 / 9.69 tok/s (runs prefill 50.2 / 41.1 / 36.4, decode 10.81 / 9.69 / 9.51; ceilings at start policy0:3628800/3628800,policy6:4742400/4742400; exit 0)
- CPU protocol A M4B: 40.8 / 3.11 tok/s (runs prefill 45.1 / 39.9 / 40.8, decode 3.13 / 3.11 / 2.97; ceilings at start policy0:3628800/3628800,policy6:4742400/4742400; exit 0)
- new vs current (CPU, one process each): prefill +0.7 %, decode +211.3 %

### W17B (control alone, its own sitting)
- GPU protocol W17B: median over 3 processes 1,187.0 / 38.80 tok/s; A 1,175.4 / 34.05 (exit 0); B 1,188.0 / 38.84 (exit 0); C 1,187.0 / 38.80 (exit 0)
- GPU dashboard leg W17B: exit 0, prefill 978.8 / 965.7, decode 36.9 / 37.4, topic words 10
- CPU protocol A W17B: 107.2 / 17.69 tok/s (exit 0)
```
