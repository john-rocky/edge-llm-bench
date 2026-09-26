# 2026-09-26 LiteRT #10231 control on the Galaxy S26 (Adreno, OpenCL)

**Question.** The Metal GPU delegate computes `ADD(runtime [1024, 768], constant [1, 1024, 768])`
wrong: google-ai-edge/LiteRT#10231 (https://github.com/google-ai-edge/LiteRT/issues/10231),
found in the folded LFM2.5-VL-450M vision encoder, Mac record
`../2026-09-24-vl-response-v1-m4max-mac/NOTES.md` finding 1. Does the same graph come out
wrong on Android's OpenCL GPU path?

**Answer: yes, at both precisions.** The rank-3 constant ADD differs from the CPU in 97.5 %
of its elements in fp32 (max |diff| 3.80). The two controls agree with the CPU: the same ADD
after a RESHAPE to rank 3, and the table fed as a runtime input (fp32 max |diff| ≤ 4.8e-7,
0 elements above 1e-4). So the miscompute is not specific to Metal.

## Instrument

LiteRT's own numerics tool, `gpu_numerics_check_cl_gl`
(`@litert//litert/tools:gpu_numerics_check_cl_gl`). It runs one graph on the CPU (XNNPACK)
and on the GPU accelerator and compares every output element. Built in the LiteRT-LM
`1dadd00c` workspace (`~/code/litert-lm-1dadd00c-wt`), whose external LiteRT is
`0da36b31be45720a2f729d329739f32eb3e17e99` (`WORKSPACE` `LITERT_REF`):
`ANDROID_NDK_HOME=~/Library/Android/sdk/ndk/28.2.13676358 bazelisk build --config=android_arm64
--enable_platform_specific_config @litert//litert/tools:gpu_numerics_check_cl_gl`,
2026-09-26 09:26:23 JST, 9 actions, exit 0 (`logs/bazel_gpu_numerics_check_cl_gl_android.log`).
The first target tried, `@litert//litert/tools:gpu_numerics_check`, fails analysis in this
workspace because `@litert_prebuilts` is not defined there
(`logs/bazel_gpu_numerics_check_android_failed.log`).

GPU = `libLiteRtGpuAccelerator.so` from LiteRT-LM's `prebuilt/android_arm64/` at `1dadd00c`
(sha256 `88e716f4…`, the file the VL leg used), loaded by dlopen from `LD_LIBRARY_PATH`. Every
log shows `Dynamically loaded GPU accelerator(libLiteRtGpuAccelerator.so) registered`,
`Loaded OpenCL library with dlopen`, `Created OpenCL device` and the whole graph on the GPU
(`Replacing 2 out of 2` / `3 out of 3 node(s) with delegate (LITERT_CL)`); the CPU side
delegates all nodes to XNNPACK. `SHA256SUMS` here lists the tool binary, the three graphs and
the two OpenCL-side `.so` files.

Inputs: the tool's deterministic pattern (`--deterministic_inputs`, default true: element i
of input b = (((i + 17·b) mod 41) − 20) × 0.05), not the image; the tool copies the CPU
input bytes into the GPU input buffers. Threshold 1e-4 (the tool's `--epsilon` default); `--fail_on_threshold=false` lets all
six runs finish. Precision: fp32 (default) and fp16 (`--use_fp16`).

Each run (exact line after `### CMD:` in `logs/run-<graph>-<fp32|fp16>.log`):

```
adb -s RFGL80R6A6H shell "cd /data/local/tmp/edge-llm-bench/vl/probe && LD_LIBRARY_PATH=/data/local/tmp/edge-llm-bench/vl/bin \
  ./gpu_numerics_check_cl_gl --graph=<graph>.tflite --print_diff_stats --print_difference_distribution \
  --fail_on_threshold=false [--use_fp16]"
```

## Device

Galaxy S26 `SM-S942Q`, SoC SM8850 (Adreno 840), Android 16, security patch 2026-06-05, adb
serial `RFGL80R6A6H`. GL driver `V@0842.19.8 (03/26/26)`, `ro.gfx.driver.0 =
com.samsung.gamedriver.sm8850` (read from the phone by the session that ran the control; no
copy is stored in this directory). Runs 09:31:02–09:31:04 JST, before the VL leg's anchor
(09:35) on the same phone.

## Graphs

The three files of release `metal-add-repro-2026-09-24`
(https://github.com/john-rocky/edge-llm-bench/releases/tag/metal-add-repro-2026-09-24); their
sha256 in `SHA256SUMS` equal the release's asset digests. All three are the first two ops of
the folded LFM2.5-VL-450M vision encoder, output [1024, 768]:

- `fc_add_const_rank3.tflite`: FULLY_CONNECTED, then ADD with the constant table at rank 3
  `[1, 1024, 768]`, as the converter emits it.
- `prefix2-reshape3.tflite`: the FC output reshaped to `[1, 1024, 768]` before the same ADD
  (rank 3 + rank 3).
- `prefix2-input.tflite`: the table as a second runtime input instead of a constant.

## Results (CPU − GPU over 786,432 output elements)

| graph | precision | max abs diff | mean abs diff | elements > 1e-4 | cosine |
|---|---|---|---|---|---|
| `fc_add_const_rank3` | fp32 | 3.804 | 0.383 | 766,808 (97.5 %) | 0.583 |
| `fc_add_const_rank3` | fp16 | 3.811 | 0.383 | 783,931 (99.7 %) | 0.583 |
| `prefix2-reshape3` | fp32 | 4.8e-7 | 1.8e-8 | 0 | 1.000000 |
| `prefix2-reshape3` | fp16 | 0.0198 | 0.00108 | 693,780 (88.2 %) | 0.999997 |
| `prefix2-input` | fp32 | 3.6e-7 | 1.8e-8 | 0 | 1.000000 |
| `prefix2-input` | fp16 | 0.0195 | 0.00107 | 691,441 (87.9 %) | 0.999997 |

In `fc_add_const_rank3` fp32 the first 768 elements (row 1) match and the first mismatch is
element #768, the start of row 2. The fp16 rows of the two controls stay within 0.02 of the
CPU: fp16 rounding, not the miscompute. The Mac's `repro_add.py` reads cosine 0.59 on its
random input; this tool reads 0.583 on its deterministic one.

## Reading

The rank-mismatched constant ADD is computed wrong on Adreno through OpenCL at both
precisions, while the RESHAPE and runtime-input versions match the CPU (fp32 exact, fp16
within rounding). The miscompute of #10231 is therefore not specific to Metal.

Through the engine this does not show on Android yet. The LFM2.5-VL GPU rows stop earlier, at
the `RESIZE_BILINEAR` compile error (`../2026-09-26-vl-response-v1-s26-android/NOTES.md`
finding 2). The effect on the caption becomes visible only with a folded bundle
(google-ai-edge/litert-torch#1260).

Next: a comment on #10231 with this table, after the owner's go.

This directory holds no JSONL, so `scripts/build_summary.py` does not read it.
