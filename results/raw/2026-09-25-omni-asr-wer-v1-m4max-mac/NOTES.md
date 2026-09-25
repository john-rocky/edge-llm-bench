# 2026-09-25 ASR WER through OmniEngine, v1 — Mac leg (M4 Max), LibriSpeech test-clean / test-other

Definition: `docs/omni-asr-wer-v1.md`. Engine LiteRT-LM `main@66058c82` (+ the macOS espeak-ng
BUILD patch in `tools/omni-eval/`), bundles `litert-community/parakeet-tdt-0.6b-v3`
(`parakeet_tdt_0.6b_v3_5s_i8_stateful.tflite`) and `litert-community/whisper-tiny`
(`whisper_tiny_30s_i8.tflite`), engine defaults (5 s / 30 s windows, overlap 0.4, timestamp
merger, 4 threads). Scoring = Open ASR Leaderboard normalizer + corpus WER. Reference column =
the leaderboard's own H200 numbers for the source models (`scripts/data/en_shortform.csv`,
2026-03-26) and, for whisper-tiny, `openai-whisper tiny` greedy on the same WAVs with the same
scorer (the leaderboard lists only `tiny.en`).

## The table

WER in percent after the leaderboard normalizer, corpus level; S/D/I = substitutions / deletions /
insertions over the set's reference words (test-clean 53,000; test-other 52,841). "hung" = utterances
the engine never returned from (watchdog-killed, scored as empty). RTFx = audio seconds / engine wall
seconds, model load excluded (the GPU rows' CPU-side stages share the 4 threads). The leaderboard
column is the leaderboard's own H200 run of the source model (`scripts/data/en_shortform.csv`,
2026-03-26); for whisper-tiny the reference is `openai-whisper tiny` greedy on the same WAVs with the
same scorer, run on this Mac (the leaderboard lists only `tiny.en`: 5.66 / 15.45).

| bundle | set | arm | WER | S / D / I | hung | empty | RTFx | peak RSS | reference WER |
|---|---|---|---|---|---|---|---|---|---|
| parakeet-tdt-0.6b-v3 (i8) | test-clean | CPU | **17.67** | 1362 / 5961 / 2040 | 0 | 11 | 36.0 | 1.40 GB | 1.92 (NeMo, leaderboard) |
| parakeet-tdt-0.6b-v3 (i8) | test-clean | GPU Metal | 17.93 | 1384 / 5683 / 2437 | 1 | 7 | 60.3 | 27.2 GB | 1.92 |
| parakeet-tdt-0.6b-v3 (i8) | test-other | CPU | **18.25** | 2510 / 4002 / 3132 | 2 | 8 | 34.2 | 1.38 GB | 3.59 |
| parakeet-tdt-0.6b-v3 (i8) | test-other | GPU Metal | 16.88 | 2373 / 3912 / 2635 | 1 | 8 | 62.5 | 29.0 GB | 3.59 |
| whisper-tiny (i8) | test-clean | CPU | **12.46** | 4807 / 556 / 1240 | 0 | 0 | 20.6 | 0.40 GB | 7.44 (openai-whisper tiny, this Mac) |
| whisper-tiny (i8) | test-clean | GPU Metal | 12.48 | 4797 / 539 / 1277 | 0 | 1 | 49.0 | 70.1 GB | 7.44 |
| whisper-tiny (i8) | test-other | CPU | **29.58** | 11325 / 1520 / 2787 | 0 | 19 | 19.5 | 0.40 GB | 16.79 |
| whisper-tiny (i8) | test-other | GPU Metal | 29.90 | 11323 / 1530 / 2948 | 0 | 25 | 44.9 | 71.9 GB | 16.79 |

Galaxy S26 (SM-S942Q, Android 16, CPU, same binary source with NDK r28): parakeet test-clean
**17.67** (1328 / 5991 / 2048, RTFx 19.9), whisper-tiny test-clean **12.46** (4807 / 556 / 1240,
byte-identical S/D/I to the Mac, RTFx 9.7). The phone throttled (battery 45–47 °C, thermal status
2–3 by the end of each cell), which is in the RTFx, not in the text. The test-other cells are in
`../2026-09-25-omni-asr-wer-v1-s26-android/` when they finish.

### By utterance length (WER %, Mac CPU)

The window is the whole story for parakeet: utterances that fit one 5 s window score close to the
model; every additional window costs. whisper-tiny goes the other way: the 30 s zero-padded window
hurts short clips most, and the reference `openai-whisper tiny` pads to 30 s too but does not lose
them.

| bucket (n clean / other) | parakeet clean | parakeet other | whisper-tiny clean | ref whisper clean | whisper-tiny other | ref whisper other |
|---|---|---|---|---|---|---|
| < 5 s, one window (1089 / 1419) | 3.24 | 6.69 | 18.32 | 9.74 | 38.53 | 21.03 |
| 5–10 s (917 / 1031) | 12.38 | 14.59 | 12.31 | 7.74 | 29.31 | 16.17 |
| 10–20 s (522 / 443) | 25.73 | 27.41 | 10.26 | 6.16 | 24.49 | 14.76 |
| ≥ 20 s (92 / 46) | 34.36 | 43.06 | 9.55 | 6.58 | 20.70 | 13.82 |

parakeet's errors are deletions at window boundaries (5961 of 9363 on test-clean) plus insertion
runs (6 utterances carry 1471 of the 2040 insertions on test-clean; 11 carry 2109 of 3132 on
test-other) — the same TDT loop as the hang, escaping late. Excluding the runs and the empty
transcripts, test-clean is still 14.4 %.

## The window drop — minimal reproduction

Utterance 4507-16021-0047 (test-clean, 34.955 s) cut into its 5 s windows, each piece run alone
through `omni/asr:asr_runner` (CPU, `--overlap_ratio=0`, so one window, no merger). Reference =
`openai-whisper tiny` greedy on the same piece. `tools/omni-eval/make_pieces.py` makes the files.

| piece (seconds) | engine parakeet-tdt-0.6b-v3 i8 | engine parakeet f32 | engine whisper-tiny i8 | openai-whisper tiny |
|---|---|---|---|---|
| c0 (0–5) | Yesterday you were trembling for a health that is dear to you, to | same | Yesterday we're trembling for a health that is dear to you today. | Yesterday you were trembling for a health that is dear to you to do |
| c1 (5–10) | *(empty)* | *(empty)* | *(empty)* | you fear for your own. Tomorrow it will be anxiety about my... |
| c2 (10–15) | *(empty)* | *(empty)* | *(empty)* | the day after tomorrow the die tribe of a slanderer. |
| c3 (15–20) | They after that the misfortune of some friend. | – | After that, the misfortune of some friend, then the prevailing | – |
| c4 (20–25) | *(empty)* | *(empty)* | whether then something that has been broken or lost then a place | whether, then something that has been broken or lost, then a pl... |
| c5 (25–30) | *(empty)* | – | with which your conscience and your vertebral column rip. | – |
| c6 (30–35) | Again, the course of public affairs. | – | I don't chew. Again, the course of public affairs. | – |

The same 5 s of audio with the window start moved (parakeet i8, one window each):

| window start | parakeet i8 |
|---|---|
| 4.5 s | To day you fear for your own. To morrow it will be anxiety |
| 4.9 s | Today you fear for your own. |
| 5.0 s (= c1) | *(empty)* |
| 5.1 s | Okay, you fear for your own. Tomorrow it will be anxiety about money. |
| 5.25 s | You fear for your own. Tomorrow it will be anxiety about money. |
| 5.5 s | Fear for your own. Tomorrow it will be anxiety about money. |
| 6.0 s | *(empty)* |

Other controls on c1: 1 / 4 / 8 threads, GPU (Metal), `levenshtein` merger — all empty for
parakeet. A 20 ms fade-in/out on c1 makes whisper-tiny transcribe it ("Hey, you fear for your
own tomorrow it will be anxiety about my"); parakeet stays empty. Piece loudness is not the
cause (c1 rms 0.089 is the loudest window; c0, which works, is 0.036).

Whole utterance through the engine (default overlap 0.4): parakeet i8 drops the c1/c2 region
("…dear to you, to About money the day after tomorrow…") and, from the last window on, loops
("Again, it's a little bit more than a little bit of a little bit of …", 419 insertions);
the f32 file drops the same text and ends "Again, it's a very good thing." (no loop). Identical
across the OmniEngine path (whole push, 100 ms pushes, session reuse), `asr_runner` at
`main@66058c82` and at `main@1dadd00c` (2026-09-17), CPU and GPU.

## GPU (Metal) memory grows per session

`tools/omni-eval/rss_probe.sh`: one engine process, one session per utterance over the first 300
test-clean utterances, RSS sampled every 5 s (`rss-probe/*.rss.csv`):

| bundle | arm | RSS at ~15 utterances | RSS at the end | growth |
|---|---|---|---|---|
| whisper-tiny | CPU | 382 MB | 360 MB (295 utt.) | flat |
| parakeet-tdt-0.6b-v3 | CPU | 1336 MB | 1307 MB (292 utt.) | flat |
| whisper-tiny | GPU Metal | 718 MB | 7984 MB (292 utt.) | **26.3 MB per session** |
| parakeet-tdt-0.6b-v3 | GPU Metal | 1533 MB | 3476 MB (204 utt., then the 7176-92135-0025 hang) | **10.3 MB per session** |

That is the 70 GB / 27 GB peak RSS in the table (2620 sessions). Whatever the GPU path allocates per
session is not released when the session is destroyed; the CPU path releases it.

## Findings

1. **Through OmniEngine, parakeet-tdt-0.6b-v3 scores 17.7 / 18.3 (test-clean / test-other) against the
   source model's 1.9 / 3.6, and the loss sits on the window path.** Utterances inside one 5 s window
   score 3.2 / 6.7; each additional window costs (34 / 43 over 20 s). Whole windows come back empty
   depending on where they start (c1 of 4507-16021-0047 empty at a 5.0 s start, transcribed at 5.1 s),
   the same in the i8 and f32 files, so it is the engine's chunk path or the 5 s stateful export, not
   the weights. Which of the two is not separated here.
2. **whisper-tiny scores 12.5 / 29.6 against 7.4 / 16.8 for openai-whisper tiny on the same files**, with
   substitutions dominating and the widest gap on clips under 5 s (18.3 vs 9.7). Almost every clip
   fits one 30 s window, so the window path is not its explanation; the cause is not found here.
3. **`TdtDecoder::Decode` can loop forever**: a non-blank token with duration 0 on the padded tail
   frames never advances `time_index`. Three utterances hang; the same loop, escaping late, is the
   "a little bit of" insertion runs (6 utterances / 1471 insertions on test-clean CPU). A 10-symbol cap
   per time index (NeMo's `max_symbols_per_step`, 10 in the FastConformer configs) ends the hangs in
   under half a second (`tools/omni-eval/tdt_decoder.max-symbols-per-step.patch`).
4. **The GPU (Metal) path leaks per session**: 26 MB (whisper-tiny) / 10 MB (parakeet) per session,
   70 GB / 27 GB over a 2620-session pass; the CPU path is flat. Text is within 1.4 WER points of
   CPU; speed 1.7–2.4× CPU.
5. **`//omni:omni_engine` does not build on macOS at main** — its TTS dependency pulls espeak-ng whose
   `speech.h` includes `<endian.h>`; espeak-ng's own `src/include/compat/` shims fix it when the C
   sources get that include path (`tools/omni-eval/espeak_ng.BUILD.macos.patch`). The Mac numbers
   above were taken with that patch.
6. **The engine is deterministic across platforms**: the Galaxy S26 reproduces test-clean at 17.67 and
   12.46, whisper-tiny byte-identical; the hang set differs by one utterance (numeric edge).
7. Not done: the TTS side (`kokoro-82m`) — the engine wants `kokoro_acoustic.tflite` +
   `kokoro_vocoder.tflite` + voices + espeak-ng data, or one `.litertlm`; nothing in that shape is on
   the Hub (litert-community/Kokoro-82M is a three-file split from June).

## The hang — mechanism and a fix candidate

Three utterances never return (3764-168670-0046 and 4198-12259-0032 on test-other CPU, 4198-12259-0032 again and
7176-92135-0025 on GPU; `HANGS.txt`); each hangs on its own too. They never return from `ProcessNext()` through the OmniSession path (CPU 300 %+, RSS flat); `asr_runner`'s
`FileAudioSource` path completes the same files. A diagnostic build of `omni/asr/tdt_decoder.cc`
(1000-step guard, log) shows where it spins:

    TDT_LOOP_GUARD: time_index=61 max_time_index=63 steps_at_same_time=1000 total_steps=1031

`TdtDecoder::Decode` advances `time_index += (duration == 0 && token == blank) ? 1 : duration`. On
the zero-padded tail frames of the last window the i8 model keeps predicting a non-blank token with
duration 0, so `time_index` never moves and the loop never ends; the "a little bit of a little bit
of …" insertion runs (4507-16021-0047, 419 insertions) are the same loop escaping late. NeMo's
greedy TDT decoder caps this (`max_symbols_per_step`, default 10); this loop has no cap.

`tools/omni-eval/tdt_decoder.max-symbols-per-step.patch` (36 lines) adds the cap: after 10
symbols at one time index, advance one frame. With it, the three utterances finish in 0.44 / 0.45 /
1.30 s:

| utterance | main@66058c82 | with the cap |
|---|---|---|
| 3764-168670-0046 (test-other) | never returns | "You surely must have a gimlet. You will make a few holes here and there around my mouth, and you will nail the top plancon loosely. Good. And what if you should have a little bit of a little should happen to cough or to sneeze?" |
| 4198-12259-0032 (test-other) | never returns | "Let us wind our horns by the sound of flagguns and bottles and That whoever hath lost his thirst, come not hither to seek it, and he's not a man who was a" |
| 4507-16021-0047 (test-clean) | 419-word insertion loop | ends "Again, it's a little bit more than a little" (the dropped middle is unchanged: a separate defect) |

The matrix above runs the unpatched engine; a watchdog kills a cell after 60 s without output,
records the utterance in `HANGS.txt`, and resumes after it, so the WER counts those utterances as
fully deleted.
