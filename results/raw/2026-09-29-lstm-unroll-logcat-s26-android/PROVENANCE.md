# Provenance — 2026-09-29 LiteRT #10300 logcat capture

## Device (read from the phone during this session; `logs/commands.log`)

| item | value |
|---|---|
| model / SoC | Samsung Galaxy S26 `SM-S942Q`, `ro.soc.model` SM8850 (Adreno 840), `ro.hardware` qcom |
| build | `samsung/m1qjpnx/m1q:16/BP4A.251205.006/S942QOPS1AZF2_SJP1AZF2:user/release-keys`, Android 16, security patch 2026-06-05 |
| kernel (tombstone) | `6.12.30-android16-5-pd30ff70-abogkiS942QOPS1AZF2-4k` |
| GL driver (`dumpsys SurfaceFlinger`) | `Qualcomm, Adreno (TM) 840, OpenGL ES 3.2 V@0842.19.8 (GIT@87ff20b216, Ifbe74a3179, 1774509467) (Date:03/26/26)` |
| `ro.gfx.driver.0` / `.1` | `com.samsung.gamedriver.sm8850` / `com.qualcomm.qti.gpudrivers.canoe.api36` |
| `ro.hardware.egl` / `ro.hardware.vulkan` | adreno / adreno |
| Adreno banner in the runner's log | `QUALCOMM build 87ff20b216, Ifbe74a3179`, `Build Date 03/26/26`, `Remote Branch refs/tags/AU_LINUX_ANDROID_LA.VENDOR.16.2.0.11.00.00.1195.535`, `Driver Version 0842.19.8` |
| screen | `svc power stayon usb` for the session (Dozing → Awake, locked); `stayon false` at teardown (Dozing) |
| battery | 79 %, 29.6–29.9 °C at every launch (`dumpsys battery`) |
| adb | `adb devices -l`: `RFGL80R6A6H device usb:8-3.1 product:m1qjpnx model:SM_S942Q device:m1q` |

Vendor libraries named in the backtrace, sha256 as read on the phone (`sha256sum`):

| file | bytes | sha256 | BuildId (tombstone) |
|---|---:|---|---|
| `/vendor/lib64/libCB.so` | 13,798,856 | `7b21cee609002beca597ff476cec711035f2ff83f6c3b9453b731d9608f26a96` | `e651fb789fe27a3b19a77d04b7ce30ab` |
| `/vendor/lib64/libOpenCL_adreno.so` | 200,576 | `91457bfa039314cf25fe0bd6a437a22ce12dfe2bac95b62060da9f9fa5e19136` | `8d35447313afeccc53451d5db5dc6a3b` |
| `/vendor/lib64/libOpenCL.so` | 87,904 | `cbd57e6dd9a9f47c2e7371fb91a3db0fe3c63518fd092a2744c83b20e3fd937d` | — |
| `/vendor/lib64/egl/libGLESv2_adreno.so` | 4,783,512 | `458da37e57aec139e263f840b6e51be8cc56698cc07c3b064ae23ca4ef8df8ee` | — |

## Runner and runtime (the 2026-09-26 files, pushed unchanged; sha256 verified on the phone before and during every launch)

| file on the phone (`/data/local/tmp/litert10300/`) | bytes | sha256 | origin |
|---|---:|---|---|
| `gpu_runner` | 7,911,128 | `e46d461a4ca270c3828e53706a33bb47c55a68b66b997959243a2346a0af1af7` | `android/round12/gpu_runner` of the 2026-09-26 run directory; build `synthetic-lstm-compile-v1`, NDK 29.0.13113456 `aarch64-linux-android28-clang++ -std=c++17 -O2 -fPIE -pie -static-libstdc++` against the 2.2.0 headers, source `android/round12/gpu_runner.cc` sha256 `246dfe866ded37610d01c0ba4c5cf8aa4a81cfb7f3821d72b20bf216103319c8` (`results/round12/runner_provenance.json` there) |
| `libLiteRt.so` | 5,508,376 | `97355a36cb8ac7628cf407773291e98da79f3ef184cc43cb0e57dedf5f0c0637` | LiteRT 2.2.0 Android AAR, arm64-v8a (`android/vendor/lib/` of the run directory, carried over from its GLiNER2.5 predecessor with the same digests) |
| `libLiteRtClGlAccelerator.so` | 3,105,544 | `7c63d606a48e9479499c012f6732623f9e6fc26250c5bdf6724af205d73eb0fb` | LiteRT 2.2.0 Android AAR, arm64-v8a (same origin) |
| `lstm_h128_t84_uni_fp32.tflite` | 1,108,840 | `f29388ee4277c66110a207fe783b186dfcf03082e4956f13bccd8d274e36b43a` | release `lstm-unroll-gpu-compile-repro-2026-09-26` asset (same digest) |
| `lstm_h128_t88_uni_fp32.tflite` | 1,123,864 | `886dcd62f4012fb455d45a020c18dd49652e5273c5856c50e62bc9a4cc000435` | release `lstm-unroll-gpu-compile-repro-2026-09-26` asset (same digest) |
| `inputs_lstm_h128_t84_uni_fp32/{manifest.tsv,word_states.f32,text_mask.f32}` | 81 / 86,016 / 336 | in `run.json` `pushed` | `results/repro_round12/inputs/lstm_h128_t84_uni_fp32/` of the run directory (seeded, `repro.py`) |
| `inputs_lstm_h128_t88_uni_fp32/{manifest.tsv,word_states.f32,text_mask.f32}` | 81 / 90,112 / 352 | in `run.json` `pushed` | `results/repro_round12/inputs/lstm_h128_t88_uni_fp32/` |

The two 2.2.0 libraries and the runner binary are the same bytes the 2026-09-26 sweep pushed
(its hash logs `009_hash_gpu_runner`, `011_hash_libLiteRt`, `013_hash_libLiteRtClGlAccelerator`
carry the same digests).

## Options the runner passes to `LiteRtCreateCompiledModel` (`gpu_runner.cc` 379–387; a verbatim copy of the 2026-09-26 `android/round12/gpu_runner.cc` is in this directory, sha256 above)

```
LiteRtCreateOptions(&options)
LiteRtSetOptionsHardwareAccelerators(options, kLiteRtHwAcceleratorGpu)
LiteRtCreateOpaqueOptions("runtime_options_string", "enable_profiling = false\nerror_reporter_mode = 1\n", free, &o1); LiteRtAddOpaqueOptions(options, o1)
if mode is fp32 or single:
  LiteRtCreateOpaqueOptions("gpu_options", "precision = 2\n", free, &o2); LiteRtAddOpaqueOptions(options, o2)
LiteRtCreateEnvironment(1, {kLiteRtEnvOptionTagRuntimeLibraryDir = /data/local/tmp/litert10300}, &env)
LiteRtCreateModelFromFile(env, <graph>, &model)
LiteRtCreateCompiledModel(env, model, options, &compiled)
```

Mode `default` skips the `gpu_options` block. No other option, environment tag or accelerator
setting is touched. `precision = 2` is `kLiteRtDelegatePrecisionFp32` (`litert/c/litert_common.h`
of the 2.2.0 headers: Default 0, Fp16 1, Fp32 2, Fp16WithFp32Accum 3).

## Timeline (JST, this session)

| time | event |
|---|---|
| 07:54:07 | S26 hold taken (`litert-10300-logcat`, keeper pid 45252) |
| 07:54:34 | device identity, GL driver, processes, battery, `logcat -g`, vendor lib hashes read |
| 07:56:57 | files pushed and hash-verified, `stayon usb` |
| 07:57:04 | `smoke-t84-fp32` |
| 08:01:59 / 08:02:55 / 08:03:51 / 08:04:47 | `t88-fp32-1` / `t88-fp32-2` / `t84-fp32-1` / `t88-default-1` |
| 08:06:47 | `stayon false`, remote directory removed and verified absent |
| 08:06:48 | hold released |
