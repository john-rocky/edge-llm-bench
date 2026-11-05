# RESULTS — Pixel 8a, PyPI litert-lm-api 0.19.0 Android wheel (2026-11-05)

Generated on 2026-11-05 by the harness's `summarize.py` from `logs/p8a-2026-11-05/` of this dir. The only arithmetic in this output is each process's median of its 3 runs and the median over the processes. The output follows as printed, with the log directory's absolute path in the heading replaced by `logs/p8a-2026-11-05`. `N4 vs M4B` is the tool's fixed heading for this pair. M4B is the harness's label for `qwen3_4b_mixed_int4.litertlm` as it was before 2026-10-31 (lfs sha256 `569fe029…`); it did not run in this sitting.

```

## Pixel 8a (logs/p8a-2026-11-05), PyPI litert-lm-api 0.19.0 Android wheel on CPython 3.14.8
device: 2026-11-05 15:31:08 model=Pixel 8a release=16 build_id=CP1A.260505.005 fingerprint=google/akita/akita:16/CP1A.260505.005/15081906:user/release-keys
selftest: exit 0, versions {'python': '3.14.8', 'platform': 'android', 'machine': 'aarch64', 'litert-lm-api': '0.19.0'}, lib sha256 28fa8433febc49a9

### N4 vs M4B
- GPU protocol N4: median over 2 processes 104.6 / 8.74 tok/s; A 104.5 / 9.38 (runs 106.4 / 104.5 / 100.5; ready=True, thermal 1, kgsl none); B 104.6 / 8.10 (runs 106.0 / 104.6 / 82.8; ready=True, thermal 1, kgsl none); C - / - (runs ; ready=True, thermal 1, kgsl none; exit 137: 11-05 15:47:10.242 13507 13507 E libEGL  : call to OpenGL ES API with no current context (logged once per thread))
```

The third process's own stop line (`logs/p8a-2026-11-05/N4_kpy_gpu_proto_C.err`, last line): `MEMGUARD: MemAvailable 358900 kB < 400000 at 1793861265: killed`. It finished no run: its stdout has no iteration line. The `exit 137:` text after C in the output above is the tool's first error line of that process, not the stop's cause.
