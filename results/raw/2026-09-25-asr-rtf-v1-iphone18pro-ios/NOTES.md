# 2026-09-25 ASR real-time factor v1 — iPhone 18 Pro leg: numbers and findings

Definition: `docs/asr-rtf-v1.md` (iPhone leg section). Identities: `PROVENANCE.md`. Same
stream, protocol and models as the Mac and S26 legs of 2026-09-19; the engine is LiteRT-LM
`main@66058c82` (the Mac/S26 legs: `1dadd00c`; `omni/asr` differs only in session plumbing,
`model_metadata.json` is byte-identical) compiled into `ios/AsrBench` through the
`asr_runner` code path. One sitting 17:48–18:13 JST (four invocations of
`scripts/asr_rtf_iphone.py`, `runlog.txt`), the phone on USB, every launch at thermal
`nominal` except the last two Qwen3-ASR GPU launches (`fair`, see the table). 45 s between
launches, 60–90 s between cells.

## The table (LiteRT-LM `main@66058c82` `omni/asr`, stream = 82.335 s LibriSpeech dev-clean 1272)

RTF = engine processing wall on the phone clock / audio seconds, median of 3 launches, range
in brackets. `load` = app launch → `Starting speech recognition` (engine + session creation).
`peak MB` = the process's `phys_footprint` (what iOS's memory limit counts; `resident_size`
is 1.2–1.9× that for the two 0.6B models because the mapped model file counts there).

| model (litert-community) | file | arm | RTF | processing s | load s | first text ms | WER (S/D/I), 3 launches | peak MB | text check |
|---|---|---|---|---|---|---|---|---|---|
| moonshine-tiny | `moonshine_tiny_5s_i8.tflite` | litert-lm-cpu | **0.0663** [0.0661–0.0667] | 5.46 | 0.07 | 407 | 0.441 (31/0/52) ×3 — transcript byte-identical to the Mac and S26 CPU runs | 107 | passes with the merger caveat of the Mac leg |
| moonshine-tiny | same | litert-lm-gpu (Metal) | 0.0314 [0.0312–0.0314] | 2.58 | 0.22 | 150 | 1.532 (64/5/219) ×3 — garbage after the first window, the same garbage on all three launches | 188 | **FAILS** — the rate is not a measurement (LiteRT-LM #3685 reproduces on this phone's Metal, deterministically here where the Mac drifted differently per launch) |
| whisper-tiny | `whisper_tiny_30s_i8.tflite` | litert-lm-cpu | **0.0453** [0.0452–0.0453] | 3.73 | 0.07 | 2118 | 0.372 (31/21/18) ×3 — byte-identical to the Mac and S26 CPU runs | 289 | passes |
| whisper-tiny | same | litert-lm-gpu (Metal) | **0.0469** [0.0467–0.0470] | 3.86 | 0.21 | 2197 | 0.351 (29/21/16) ×3 — the same text as the Mac and S26 GPU runs | 364 | passes |
| parakeet-tdt-0.6b-v3 | `parakeet_tdt_0.6b_v3_5s_i8_stateful.tflite` | litert-lm-cpu | **0.0305** [0.0303–0.0305] | 2.51 | 0.36 | 197 | 0.197 (11/22/4) ×3 — byte-identical to the Mac CPU run (the S26 CPU run differed at one chunk boundary, 0.229) | 712 | passes |
| parakeet-tdt-0.6b-v3 | same | litert-lm-gpu (Metal) | **0.0381** [0.0381–0.0382] | 3.14 | 2.12 | 244 | 0.266 (9/26/15) ×3 — the same text as the Mac and S26 GPU runs | 773 | passes (the same two chunk-boundary merges as on the Mac) |
| Qwen3-ASR-0.6B | `qwen3_asr_0.6b_5s_i8.litertlm` | litert-lm-cpu | **0.1233** [0.1229–0.1238] | 10.15 | 0.75 | 1203 | 0.463 (33/8/46) ×3 — byte-identical to the Mac and S26 CPU runs, header-token leak included | 1529 | weak (engine-side header leak, as on the Mac and S26) |
| Qwen3-ASR-0.6B | same | litert-lm-gpu (Metal) | 0.4624 [0.4620–0.4629] | 38.07 | 1.35 | — | **no text at all** ×3 | 1188 | **FAILS** — empty transcript (LiteRT-LM #3684 reproduces on this phone's Metal); launches 2 and 3 ended / started at thermal `fair` |

Spread: every cell repeats within ±1 % across the three launches, and every cell's three
transcripts are byte-identical to each other. `first text ms` is chunk-loop start → the
first confirmed text inside the app; whisper's ~2.1 s is the 30 s window plus the decoder's
lazy second compile inside the first chunk, as on the Mac.

## Findings

1. **The CPU path is the same engine everywhere.** moonshine, whisper and Qwen3-ASR give
   transcripts byte-identical to the Mac and the S26 (XNNPACK int8, same graph);
   parakeet's iPhone text equals the Mac's, while the S26 differed at one chunk boundary
   (2026-09-19 leg). The header-token leak of Qwen3-ASR reproduces byte-for-byte.
2. **Both GPU text failures of the Mac leg are Metal failures, not Mac failures.**
   moonshine i8 on the iPhone's Metal transcribes the first window and then emits garbage
   (WER 1.53, 219 insertions) — deterministically across three launches, where the Mac
   drifted differently each launch; Qwen3-ASR `.litertlm` on Metal returns no text at all
   (as on the Mac's Metal and on the S26's OpenCL). Issues #3685 and #3684 gain an iPhone
   reproduction each (no new issue; a comment when they have an owner).
3. **Where Metal helps on this phone:** moonshine only on paper (its text is wrong);
   whisper-tiny and parakeet run slower on Metal than on the CPU here (0.0469 vs 0.0453,
   0.0381 vs 0.0305) — the Mac halved both on Metal, the S26's OpenCL was 1.4–3.0× slower.
   Every GPU launch also pays the dylib load and Metal setup in `load` (parakeet 2.1 s vs
   0.4 s on the CPU).
4. **Qwen3-ASR on Metal warms the phone**: 38 s of processing per launch took the thermal
   state to `fair` by the second launch and the third started `fair` (all other 21
   launches stayed `nominal`). The rows are marked; the number is void anyway (no text).
5. **Instrument:** the OSS bazel build for iOS links no static accelerator, so the GPU rows
   run through the prebuilt dylib loaded by name after a `chdir` to the app's Frameworks
   folder (`PROVENANCE.md`); `Dynamically loaded GPU accelerator(libLiteRtMetalAccelerator.dylib)
   registered.` is in every GPU console. The LLVM profile runtime linked from a Rust
   dependency writes nothing (sandbox) and is not instrumentation of the engine.

## Not done today

- The f32 recipes, the merger / overlap cell sets, per-utterance latency (as on the other
  legs); an LLM session anchor on the phone (the first session of the family here; the
  thermal state per launch is the control instead).
- The OmniEngine entry point (`omni/omni_engine.h`) on iOS: not built (it pulls the TTS
  dependencies, espeak-ng among them); the ASR rows go through `AsrEngine` directly, which
  is what `asr_runner` and the Mac/S26 rows use.
