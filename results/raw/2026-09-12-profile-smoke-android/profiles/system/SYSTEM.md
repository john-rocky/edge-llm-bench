# System profile (simpleperf) — Pixel 8a, 2026-09-12 19:39–19:55 JST

Bundle: `litert-community/Qwen3-0.6B` `qwen3_0_6b_mixed_int4.litertlm`; engine
`litert_lm_advanced_main` v0.16.0 (sha e5de2d90…, the pinned release binary, not
stripped — symbols resolve on the device); `--benchmark` 128 prefill × 256 decode,
`--max_num_tokens=1024`, `taskset f0` (the four mid cores, the Pixel 8a's standard
mask in this harness); Android 16, thermal status 0 before every run, 60 s between
runs; one run per row. The per-op pair for the same cell is in `../PROFILE.md`.

`simpleperf` is `/system/bin/simpleperf` (version 1.build.15081906). As the `shell`
user only user-space samples are allowed (`-e cpu-clock:u`; plain `cpu-clock` is
refused with "Can't record kernel samples"), so kernel time — the GPU driver
ioctls, page faults, scheduling — is not in any table below. `perf*.data` were
pulled and then removed from the phone; the reports are the stored reading;
the witnesses (build, simpleperf version, binary sha) are in `session_provenance.txt`.

## Rates (the profiled rows are never speed rows)

| row | file | decode tok/s | samples |
|---|---|---:|---:|
| cpu control | `*_cpu_ctrl.log` | 16.44 | – |
| cpu, simpleperf over the whole process, `--call-graph fp`, 1000 Hz | `*_cpu_simpleperf.log` | 14.31 | 54,164 |
| cpu, simpleperf attached for 8 s during decode, fp | `*_cpu_simpleperf-attach.log` | 15.04 | 20,715 |
| cpu, attached 8 s, `--call-graph dwarf` | `*_cpu_simpleperf-attach-dwarf.log` | 16.18 | 14,823 |
| gpu control | `*_gpu_ctrl.log` | 15.12 | – |
| gpu, whole process, fp | `*_gpu_simpleperf.log` | 15.23 | 16,441 |
| gpu, attached 8 s during decode, fp | `*_gpu_simpleperf-attach.log` | 15.45 | 5,894 |

Whole-process sampling at 1000 Hz cost the CPU-backend run 13 % of its decode
rate; the 8-second attach cost 2–9 %; the GPU-backend rows moved within 3 %.
No sample was lost in any row.

## CPU backend — where the user-space time goes (attach window, dwarf row)

| self % | symbol | what it is |
|---:|---|---|
| 36.4 | `xnn_qd8_f32_qb4w_gemm_minmax_ukernel_1x16c8__neoni8mm` | the M=1 int4-weight GEMM kernel (decode) |
| 30.9 | `thread_main` | the XNNPACK thread-pool worker loop itself — waiting for work, not computing |
| 7.5 | `__memmove_aarch64_simd` | libc copies |
| 7.5 | `xnn_f32_gemm_minmax_ukernel_7x8__asm_aarch64_neonfma_ld128_2` | an f32 GEMM |
| 7.2 | `xnn_x32_packw_gemm_goi_ukernel_x8__neon_ld4lane_u4_prfm` | weight packing, run inside the decode step |
| 2.5 | `__aarch64_swp4_acq` | atomics (pool synchronisation) |

Three pool threads and the calling main thread split the samples evenly (23–26 %
each, `--sort comm,tid`), so no core is idle by assignment — but a third of the sampled time is the pool
spinning. Frame-pointer stacks were flat on this binary (Children = Self for
every symbol in the fp row's `-g caller` output, stored at the end of
`*_cpu_simpleperf-attach-report.txt`), so the caller view comes from the dwarf row only:
`thread_main` → `thread_parallelize_2d_tile_2d_dynamic` → `xnn_compute_qp8gemm`
→ the int4 kernel carries 37 %; `thread_parallelize_2d_tile_1d_dynamic` →
`xnn_compute_batched_packw_gemm_goi` → the packing kernel carries 5.7 %; the
main thread's own 25 % sits under `SessionAdvanced::WaitUntilDone` →
`Tasks::Decode` → `CompiledModel::RunAsync`. Over the 8 s window the four
threads (three pool threads and the main thread) were on-CPU in user space for 65 % of the possible samples
(20,715 of 32,000 at fp); the rest is kernel or off-CPU and invisible here.

Per-op view of the same step (`../PROFILE.md`): 61.3 ms wall, 36.4 ms of the
profiled op time in attention+KV nodes, 6.5 ms of the wall outside the
profiled ops. The system view does not contradict it — it adds that the
"compute" is a single M=1 kernel plus pool spin plus a per-step repack,
which the op table cannot separate.

## GPU backend — what the CPU side does while the GPU decodes

Only the CPU side is visible: user-space samples of a process whose work is on
the Mali GPU. In the 8 s attach window 94 % of the samples are the main thread
(5,540 of 8,000 possible: on-CPU in user space 69 % of the window; the rest is
kernel/driver or waiting), 6 % `mali-event-hand` (the driver's event thread).

| self % (dso) | shared object | note |
|---:|---|---|
| 38.0 | `libLiteRtGpuAccelerator.so` | stripped in the release — offsets only (`[+105788]` 4.4 % top) |
| 33.4 | `/vendor/lib64/egl/libGLES_mali.so` | `clSetKernelArg`, `mcl_gpu_kernel::setarg_constant`, `mcl_command_device::init`, `mcl_gpu_payload::*` — per-kernel argument setting and command construction |
| 19.5 | `libc.so` | `pthread_mutex_lock/unlock` (7.7 %), `memmove`, `memset`, scudo malloc/free |
| 6.6 | `litert_lm_advanced_main` | `tflite::half::operator float()`, `TopKTokenIds`, `TopPSampler` — the sampler on the CPU |

Reading: the CPU time of a GPU decode step here is OpenCL submission and
sampling, not model math; how long the GPU itself takes per kernel is not
observable with this tool on this phone (the per-op profile's 856 launches
per step is the only kernel-level number we have). One bundle, one phone, one
version: inputs to a re-test, not properties of the runtime.
