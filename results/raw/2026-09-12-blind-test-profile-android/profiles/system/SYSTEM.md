# System profile: litert-community/gemma-4-E2B-it-litert-lm, native-benchmark-128x256, Android GPU backend

Pixel 8a, Android 16, LiteRT-LM v0.16.0 vendored pin, simpleperf 1.build.15081906,
`cpu-clock:u` (shell user, no kernel samples), 2026-09-12/13.

## Rates (control vs profiled — a profiled rate is never a speed row)

| capture | decode tok/s | notes |
|---|---|---|
| control (this skill, fresh run) | 8.70 | byte-identical command, no profiler |
| `./bench profile` control (step 2, same sitting) | 8.63 | cross-check, agrees within 1% |
| simpleperf-attached run (the one this reading is from) | 8.92 | attach cost here reads as ~0 on the rate; the sampling itself (`cpu-clock:u`, 1000 Hz, 8 s window, attached after decode had already started) did not depress the rate measurably for this model/backend, unlike the CPU-backend whole-process case documented in the profile-litert-lm-system skill |

## Reading

**What code?** Top self symbols on the GPU backend, 8 s attached during decode
(5,776 samples): `libLiteRtGpuAccelerator.so[+105788]` 7.10% (stripped, offset
only), `pthread_mutex_lock`/`pthread_mutex_unlock` 5.35% each, Mali driver
`clSetKernelArg` 3.41%, `tflite::half::operator float()` 3.31% (fp16<->fp32
conversion in the engine binary itself, which does carry symbols),
`__memmove_aarch64_simd` 2.93%. Grouping the many additional
`libLiteRtGpuAccelerator.so[+...]` and Mali `libGLES_mali.so` (`mcl_*`) lines
below the 0.5% cutoff, the shape matches the skill's own worked example for
Qwen3-0.6B GPU: the CPU side here is submission (kernel-arg binding, payload
assembly, mutexes) rather than math, not the per-op table's "launch" count.

**Which threads?** `--sort comm,tid`: 91.71% of samples on the main
`litert_lm_advanced_main` thread (tid 10789), 8.29% on `mali-event-hand`
(tid 10792) — one calling thread plus the driver's event thread, same pattern
the skill describes for the GPU backend (there: 94%/driver-thread split on a
smaller model).

**Who calls it?** The dwarf caller tree resolves cleanly for this GPU-backend
capture (unlike the skill's own note about flat frame-pointer stacks — dwarf
was requested here from the start, so `Children` != `Self` throughout):
`Tasks::Decode` -> `LlmLiteRtCompiledModelExecutorBase::Decode` ->
`DecodeLogits` -> `DecodeInternal` -> `BindTensorsAndRunDecode` ->
`CompiledModel::RunAsync`/`RunCApi` -> `tflite::Subgraph::InvokeImpl` ->
(94.37% of that node) `libLiteRtGpuAccelerator.so[+109470]` -> ... ->
`clEnqueueNDRangeKernel` -> `mcl_enqueue_ndrange_kernel` ->
`mcl_command_device::init` -> `mcl_gpu_device::create_payload` ->
`mcl_gpu_payload_manager::commit` -> `mcl_gpu_payload::assign`, which itself
splits into `__memmove_aarch64_simd` (31%), `set_constant_implicit_args` (30%)
and `mcl_gpu_payload_csf::finalize` (26%) — i.e. most of the GPU-side CPU time
under `InvokeImpl` is spent building and submitting the OpenCL kernel-launch
payload for each op, not executing kernels on the CPU. Full text:
`litert-community_..._gpu_simpleperf-attach-dwarf-callers.txt`.

**Candidate, not conclusion:** the driver-heavy CPU side with a large payload-
assembly share per launch, paired with `./bench profile`'s 1300 launches/step
for this model (step 2, `PROFILE.md`), points at launch count/batching as
worth testing — never a conclusion from this one sampled window.

## Attach-timing note (see session_provenance.txt for the full story)

The skill's own worked example uses a fixed `sleep 12` (for Qwen3-0.6B) before
attaching, immediately after starting the control run with no cooldown
mentioned. For this model (2.5 GB, 2026-09-12 warm on-device caches) that
fixed sleep does not transfer: Init time swung from 2.15 s to 26.9 s across
otherwise-identical back-to-back invocations with no cooldown between them,
so two attach attempts landed inside Init instead of decode and had to be
discarded. Only a run preceded by a ~20 s device-idle cooldown reproduced the
fast (~4.4 s) Init the skill's timing assumes. This is a real gap, not
operator error: nothing in the skill flags that consecutive manual
invocations need a cooldown the way the harness's own runner already applies
between cells/runs.

Runtime: https://github.com/google-ai-edge/litert ; engine: https://github.com/google-ai-edge/LiteRT-LM

## Follow-up (2026-09-13 08:00, the skill's author)

The fixed `sleep 12` before attaching is what failed twice above; the skill now
waits for the engine's end-of-prefill line (`tasks.cc:490 Failed to get prefill
profile summary`) instead. Re-run here with that form on the same bundle:
`*_gpu_simpleperf-attach-marker-dwarf.log` / `-report.txt` — Init Executor
31.6 s, decode 8.86 tok/s, 5,849 samples, the same top symbols
(`libLiteRtGpuAccelerator.so[+105788]` 7.1 %, `pthread_mutex_lock` 5.6 %,
`clSetKernelArg` 3.5 %). The blind run's own attach-dwarf `.log` and
`-report.txt` were overwritten by this re-run (same file name); its
`-callers.txt` and `-threads.txt` (5,776 samples) are the originals.
