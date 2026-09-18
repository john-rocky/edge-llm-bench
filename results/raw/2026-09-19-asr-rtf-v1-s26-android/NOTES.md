# 2026-09-19 ASR real-time factor v1 — Galaxy S26 leg: numbers and findings

Definition: `docs/asr-rtf-v1.md`. Identities: `PROVENANCE.md`. Same stream, protocol and
engine commit as the Mac leg (`../2026-09-19-asr-rtf-v1-m4max-mac/`), the runner built for
`android_arm64`. Two sittings: 07:00–07:31 JST (all eight cells, 5 s between launches) and
07:33–07:45 (the four CPU cells again at 45 s between launches). The first sitting's CPU
captures drifted +12–27 % from launch 1 to launch 3 (moonshine 0.043 → 0.054, whisper
0.049 → 0.066, Qwen3-ASR 0.151 → 0.192 → 0.151; parakeet held) and are quarantined as
`*_cpu.jsonl.attempt1` (spread-rule); the retake repeats within ±1–4 %. The GPU cells of
sitting 1 repeat within ±1 % and stand. `runlog.txt` / `logs/driver_*.log` carry every gate
wait; the battery temperature before and after each launch is in the record.

## The table (LiteRT-LM `main@1dadd00c` `omni/asr`, stream = 82.335 s LibriSpeech dev-clean 1272)

RTF = engine processing wall on the phone clock / audio seconds, median of 3 launches,
range in brackets. Battery 35.0–36.0 °C at every kept launch, thermal status 0 throughout
except the last Qwen3-ASR GPU launch (ended at status 1, 38.9 °C). No CPU frequency cap.

| model (litert-community) | file | arm | RTF | processing s | load s | first text ms | WER (3 launches) | peak RSS MB | text check |
|---|---|---|---|---|---|---|---|---|---|
| moonshine-tiny | `moonshine_tiny_5s_i8.tflite` | litert-lm-cpu | **0.0416** [0.0416–0.0421] | 3.42 | 0.14 | 300 | 0.441 ×3 — transcript byte-identical to the Mac CPU run | 198 | passes (merger caveat as on the Mac) |
| moonshine-tiny | same | litert-lm-gpu (OpenCL) | **0.0560** [0.0557–0.0560] | 4.61 | 1.18 | 357 | 0.335 ×3 — intact text, deterministic | 258 | passes — the Metal drift does not reproduce on Adreno |
| whisper-tiny | `whisper_tiny_30s_i8.tflite` | litert-lm-cpu | **0.0482** [0.0481–0.0486] | 3.97 | 0.16 | 2246 | 0.372 ×3 — byte-identical to the Mac CPU run | 357 | passes |
| whisper-tiny | same | litert-lm-gpu | **0.0701** [0.0699–0.0702] | 5.77 | 1.00 | 3243 | 0.351 ×3 (same text as the Mac GPU run) | 278 | passes |
| parakeet-tdt-0.6b-v3 | `parakeet_tdt_0.6b_v3_5s_i8_stateful.tflite` | litert-lm-cpu | **0.0272** [0.0271–0.0273] | 2.24 | 0.66 | 198 | 0.229 ×3 — differs from the Mac CPU run (0.197) at one chunk boundary ("heard the raps and opened" → "was where is that") and `whirr`/`whir` | 1328 | passes |
| parakeet-tdt-0.6b-v3 | same | litert-lm-gpu | **0.0825** [0.0821–0.0828] | 6.79 | 6.25 | 467 | 0.266 ×3 (same text as the Mac GPU run) | 1358 | passes; 3.0× the CPU time, 6 s of OpenCL compile per launch |
| Qwen3-ASR-0.6B | `qwen3_asr_0.6b_5s_i8.litertlm` | litert-lm-cpu | **0.1463** [0.1414–0.1475] | 12.05 | 1.41 | 1666 | 0.463 ×3 — byte-identical to the Mac CPU run, header-token leak included | 2385 | weak (engine-side header leak, as on the Mac) |
| Qwen3-ASR-0.6B | same | litert-lm-gpu | 1.497 [1.330–1.516] | 123 | 4.22 | — | **no text at all** ×3 | 859 | **FAILS** — empty transcript, slower than real time, 8× the CPU time |

## Findings

1. **The Qwen3-ASR `.litertlm` GPU failure is not Metal-specific.** On Adreno (OpenCL,
   `libLiteRtGpuAccelerator.so` from `prebuilt/android_arm64/` at `1dadd00c`) the same file
   returns an empty transcript on 3/3 launches with the same log shape as the Mac (audio
   encoder with 112/113 external tensors, LM initialised on the GPU, no warning between
   `Starting` and `Finished`), at 110–125 s for 82 s of audio. The Mac issue draft now
   says both platforms.
2. **The moonshine Metal drift is Metal-specific.** OpenCL transcribes the whole stream
   with intact text (WER 0.335, deterministic); the CPU transcripts are byte-identical
   between the M4 Max and the S26 for moonshine, whisper and Qwen3-ASR (XNNPACK int8,
   same graph), parakeet differs at one chunk boundary.
3. **On this phone the GPU is slower than the CPU for every ASR model** (moonshine 1.35×,
   whisper 1.45×, parakeet 3.0×, Qwen3-ASR 10×) — the opposite of the Mac, where Metal
   halved whisper and parakeet. Same direction as the catalog's LLM-decode finding for
   Android GPU (K17). Parakeet's GPU launch also spends 6.2 s compiling OpenCL kernels
   (no cache dir handed to the runner).
4. **Phone protocol:** 5 s between launches lets the CPU cells heat run to run (+12–27 %
   by launch 3); 45 s holds them within ±1 %. `scripts/asr_rtf_android.py` now defaults to
   45 s between launches and 90 s between cells; the battery-temperature gate (≤ 36 °C)
   waited 15–120 s before most launches while the phone charged over USB.
5. **Header-token leak reproduces byte-for-byte on the phone** (Qwen3-ASR CPU), so it is
   engine text handling, not a platform numerics effect.

## Not done today

- NPU (`_Qualcomm_SM8850` AOT files exist for moonshine / whisper / parakeet; the runner's
  `--backend npu` needs the QNN libraries staged) — a separate sitting.
- The LLM session anchor on the phone; f32 recipes; per-utterance latency.
