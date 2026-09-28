# 2026-09-29 TTS real-time factor v1 — Galaxy S26, the fast-graph recipe row interleaved with the default row: numbers and findings

Definition: `docs/tts-rtf-v1.md` (sections "Android leg" and "Fast-graph recipe row"). Identities (app
build, AAR, model files as read on the phone, ASR instrument, phone): `PROVENANCE.md`. Records: one JSONL
per row (three measured launches each, 02:12:38–02:31:05 JST), the warm-up round beside them
(`*.jsonl.warmup`, one launch per row, not measurements), per launch under `logs/` the `am instrument`
stream, the harness's JSON (timings, stage clocks, the graph evidence, process counters), the logcat slice
and both ASR logs; the audio under `audio/` (every launch of a row produced the same bytes, so one copy
per row of the 24 kHz output and of the 16 kHz round-trip input is kept; sha256 in every record). Session
anchor right before it (`../2026-09-29-tts-rtf-fast-s26-anchor-retake-android/`, unmasked, 01:53:59–02:04:46):
llama.cpp b8999 Qwen3-0.6B-GGUF short-chat decode 107.7 / 109.6 / 108.2 tok/s, median 108.2 against the
newest admitted session on the phone, this night's first anchor (105.3, n = 3,
`../2026-09-29-tts-rtf-fast-s26-anchor-android/`), ratio 1.028 — ADMITTED under the dashboard's rule
(`scripts/dashboard_job.py` `admit()`; `SESSION.json` here and in the anchor dir); against the recurring
job's own session of the night before (104.7, `2026-09-28-dashboard-v1-s26-android`) the ratio is 1.033. The
litert-lm-gpu anchor: 57.77 / 52.53 / 52.14, median 52.53 (1.01 against the first anchor's 52.03, 0.94
against 55.98 the night before; not gating).

## The table (Qwen3-TTS-12Hz-0.6B-Base, the public LiteRT reference pipeline's own Android app built with the fast-path auto-select, `com.google.ai.edge.litert:litert` 2.1.6 CompiledModel, CPU / XNNPACK; both rows in one sitting, interleaved default, fast, default, fast, default, fast; 120 s before every launch)

RTF = synthesize() wall / audio seconds, **median of 3 launches, range in brackets**; the stage clocks
are the engine's own (medians).

| row (graphs) | RTF | synthesis s | audio s (frames) | prefill / talker / MTP / codec s | load s | peak RSS MB | audio check |
|---|---|---|---|---|---|---|---|
| default: `talker_int4` + `mtp_fp32` (2 threads) + `codec_decoder_fp32` | **9.13** [8.94–9.26] | 84.8 [82.9–86.0] | 9.28 (116) | 0.29 / 5.19 / 70.61 / 7.42 | 2.23 [2.12–3.85] | 3,778 | passes: WER **0.148** ×3 (parakeet: "voice snapped with" doubled at a 5 s chunk seam + "used a command"), **0.000** ×3 (whisper-tiny) |
| fast (`recipe=mtp-folded-int8-codec-split`): `talker_int4` + `mtp_folded_int8` (4 threads, in-graph greedy residuals) + `codec_partA` fp32 / `codec_partB` FORCE_FP16 | **1.72** [1.67–1.73] | 14.6 [14.2–14.6] | 8.48 (106) | 0.33 / 4.32 / 6.68 / 2.63 | 4.16 [4.13–4.19] | 4,035 | passes: WER **0.074** ×3 (parakeet: "voice was I snapped"), **0.037** ×3 (whisper-tiny: "wraps" for "raps") |

In this sitting the default row's RTF is **5.3 ×** the fast row's (9.13 / 1.72). Per 80 ms frame the MTP
stage takes 609 ms in the default row and 63 ms in the fast row, the codec 64 and 25 ms, the talker 45 and
41 ms (medians of the per-launch stage clock / frames). The host glue outside the four stage clocks is
0.6 s in every launch of both rows.

Process counters across synthesize() (`/proc/self/stat`, all threads; new in this harness): the default
row used 163.6 / 169.2 / 167.2 CPU seconds (1.97 cores on average), 17.6–18.2 CPU seconds per second of
audio; the fast row 46.3 / 47.4 / 47.0 CPU seconds (3.2–3.3 cores), 5.46–5.59 per second of audio. The
wall-clock factor (5.3) and the CPU-time factor (3.2) differ because the fast row gives the MTP 4 threads
where the default row gives it 2 — the app's own values in both rows.

Spread: default 8.94 / 9.26 / 9.13 (3.6 % of the median), fast 1.67 / 1.72 / 1.73 (3.1 %); both inside the
5 % bar. Every launch started with no CPU frequency cap (the launch gate waited for it: 61 s before fast
run 1 and default run 2, 46 s before fast run 2) and every one ended with a cap. Battery at launch
34.5 / 36.0 / 35.2 °C (default) and 35.9 / 35.8 / 35.8 °C (fast), thermal status nominal before and after
every launch. Screen: off (`Dozing`) for the first three measured launches, on (`Awake`) from fast run 2 on
— it woke between 02:20:31 and 02:24:48 JST; `stay_on_while_plugged_in` stayed 0 and nothing this sitting
runs wakes it; what did was not checked. Both states are admissible (`devices/galaxy-s26.md`) and each record carries its
own.

Output audio: default 116 frames / 9.28 s, peak |sample| 0.519, RMS −25.3 dBFS — the **same bytes as the
2026-09-27 capture** on the `a1f5edf` build (`b8c030a2…`): with the fast files parked, this build's default
path gives the `a1f5edf` build's output for this input (eight launches tonight: one smoke, three in the
thrown-out pass, the warm-up, three here); fast 106 frames / 8.48 s, peak 0.314, RMS −26.7 dBFS, the same
bytes (`dcddab13…`) on all nine fast launches of the night (two smokes, three in the thrown-out pass, the
warm-up, three here). The two rows' audio differs by design: the fast row picks the 15 residual
codebooks by argmax inside the folded graph, and only the first codebook draws from `java.util.Random(1)`.

## Findings

1. **On the Galaxy S26 CPU the app's fast graphs synthesize the 27-word sentence at RTF 1.72, the default
   graphs at 9.13 in the same sitting** — 14.6 s for 8.5 s of speech, and 84.8 s for 9.3 s. The MTP
   stage goes from 83 % of the default row's time to 46 % of the fast row's (70.6 → 6.7 s); the codec from
   7.4 to 2.6 s; the talker, the same graph in both rows, is now the second-largest stage (4.3 s).
2. **The fast row changes three things at once, and this capture does not separate them**: the MTP fold
   with its int8 weights and its thread count (2 → 4), the codec split with its fp16 back half, and the
   residual-codebook choice (in-graph greedy instead of host sampling). The per-stage clocks locate the
   time (MTP and codec) but do not attribute it among fold, int8, threads and fp16. The app selects the
   folded MTP and the split codec by separate files, so a one-change row is possible; none was run.
3. **Both rows' audio passes the round trip.** whisper-tiny returns the default row's 27 words exactly and
   the fast row's with one substitution ("wraps"); the protocol instrument (parakeet) reads 0.148 and 0.074,
   its errors sitting where the 2026-09-27 NOTES found the chunk-seam doubling (default) and in one phrase
   ("voice was I snapped", fast). Nobody listened to the files; they are stored.
4. **The first pass of this sitting was thrown out (spread-rule).** Admitted by
   `../2026-09-29-tts-rtf-fast-s26-anchor-android/` (llama.cpp 105.1 / 105.3 / 107.1, ratio 1.006 against the
   same reference) and run 01:28–01:44 JST without a warm-up round, the fast row read 1.80 / 1.68 / 1.66
   (8.4 %) while the default row read 8.13 / 8.15 / 8.41 (3.5 %). Kept as `attempt1/` (records
   `*.jsonl.attempt1`, all logs, one audio copy per row — the same bytes). The slow launch was the first
   fast launch of the pass; its talker, MTP and codec stages and its load (+0.5 s) were all slower than in
   the pass's other two fast launches (the prefill was not). **Why is not
   established**: the retake put one unmeasured launch of each row first, and its first fast launch (the
   warm-up, 1.73) did not repeat the slowdown; the new page-fault counters do not track the time either
   (fast run 2: 142,850 major faults during synthesis, RTF 1.723; fast run 3: 391, 1.725).
5. **The default row's number moves with the phone's temperature more than the fast row's.** The thrown-out
   pass started its default launches at 31.6–34.1 °C and read 8.13–8.41; the kept pass, after the warm-up
   round, at 34.5–36.0 °C and read 8.94–9.26 (+12 % in the median); the fast row's median moved +2 %
   (1.68 → 1.72). Every launch of both rows ended with a CPU frequency cap; when in the launch the cap
   came is not recorded. The ratio between the rows differs between the two passes: 5.3 in the kept pass,
   4.8 in the thrown-out one.
6. **Which graphs ran is recorded per launch, not assumed.** Every record carries the graph files filesDir
   held, the engine's own `mtpFolded` / `codecSplit` flags and the graph files the process mapped; the
   default row's launches mapped `talker_int4` + `mtp_fp32` + `codec_decoder_fp32` with both flags false,
   the fast row's `talker_int4` + `mtp_folded` + `codec_partA` + `codec_partB` with both true
   (`metrics.ttsGraphSelectionCheck: pass` ×8, warm-ups included). All 13 model files hashed on the phone
   to the Hub's LFS sha256 / git blob ids before the first launch and again after the last.

The 2026-09-27 capture of the default row (RTF 8.62 [8.40–8.83], `../2026-09-27-tts-rtf-v1-s26-android/`) is
a different sitting on a different build and is not pooled with this one.

Not run this sitting: the one-change rows (folded MTP alone, split codec alone), the fast graphs on the Mac
leg (the Python sample at `a1f5edf` has no fast path), `talker_fp32`, greedy decoding of the first codebook,
other voices / languages, any GPU or NPU path (the app is CPU-only), Pixel 8a, iPhone.
