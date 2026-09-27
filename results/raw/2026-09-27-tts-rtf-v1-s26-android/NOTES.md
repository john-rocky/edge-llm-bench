# 2026-09-27 TTS real-time factor v1 — Galaxy S26 leg, first phone cell: numbers and findings

Definition: `docs/tts-rtf-v1.md` (section "Android leg"). Identities (app build, AAR, model
files as read on the phone, ASR instrument, phone): `PROVENANCE.md`. Records: one JSONL (three
process launches, 12:09:30–12:17:45 JST), per launch under `logs/` the `am instrument` stream,
the harness's timing JSON, the logcat slice and both ASR logs; the synthesized audio under
`audio/` (all launches produced byte-identical audio — seed 1, `java.util.Random` — so one copy
of the 24 kHz output and one of the 16 kHz round-trip input are kept; sha256 in every record).
Session anchor right before it (`../2026-09-27-tts-rtf-v1-s26-anchor-retake-android/`, unmasked,
11:56:23–12:08): llama.cpp b8999 Qwen3-0.6B-GGUF short-chat decode 107.9 / 107.8 / 106.8 tok/s,
median 107.8 against the reference 107.6 (n = 3, `2026-09-27-dashboard-v1-s26-android`, the
recurring job's sitting of the same night), ratio 1.002 — ADMITTED under the dashboard's rule
(`scripts/dashboard_job.py` `admit()`; `SESSION.json` here and in the anchor dir). The
litert-lm-gpu anchor: 58.5 / 52.4 / 52.8, median 52.75 vs 53.75.

## The table (Qwen3-TTS-12Hz-0.6B-Base, the public LiteRT reference pipeline's own Android app, `com.google.ai.edge.litert:litert` 2.1.6 CompiledModel, CPU / XNNPACK, talker 4 / MTP 2 / codec 4 threads)

RTF = synthesize() wall / audio seconds, **median of 3 launches, range in brackets**; the stage
clocks are the engine's own.

| graphs (recipe) | arm | RTF | synthesis s | audio s (frames) | prefill / talker / MTP / codec s | load s | peak RSS MB | audio check |
|---|---|---|---|---|---|---|---|---|
| `talker_int4` (blockwise-32 OCTAV) + `mtp_fp32` + `codec_decoder_fp32` — the sample's default set | litert-cpu | **8.62** [8.40–8.83] | 80.0 [78.0–82.0] | 9.28 (116) | 0.30 / 5.08 / 66.6 / 7.37 | 2.14 [2.14–2.70] | 3,772 | passes: round-trip WER **0.148** ×3 with the protocol instrument (parakeet, 5 s chunks: one doubled phrase at a chunk seam + "used a command"), **0.000** ×3 with the whisper-tiny second opinion (one 30 s window) |

Reading: 8.6 means the S26's CPU needs 8.6 s of compute for every second of speech — 80 s for
the 9.3 s utterance. The MTP inner loop is 83 % of it (66.6 s: the 78 M-parameter residual-codebook
graph invoked 17 times per 80 ms frame, on 2 threads by the app's design), the codec 9 %, the
talker decode 6 %, the prompt prefill 0.4 %. The engine's own RTF (stage clocks / audio,
`ttsPipelineRealTimeFactor`) is 8.55: the host glue between the graphs is 1 % here.

Spread: launches 1 → 2 → 3 read 8.40, 8.62, 8.83 (+2.6 %, +2.5 %) at 120 s pauses, battery
33.0 → 37.6 °C. Every launch started with no CPU frequency cap and ended with one
(`provenance.deviceAfter.cpuFreqCapped`: `scaling_max_freq` below `cpuinfo_max_freq` on at least
one policy) — an 80 s CPU-bound synthesis is long enough for the phone to lower its clocks
during the run, and the next launch begins a little warmer. Range 5 % around the median,
disclosed; the median is the number. Thermal status was nominal before and after every launch;
screen off (`Dozing`) throughout; no other process above the noise in the logcat slices.

Output audio: 116 frames / 9.28 s, peak |sample| 0.519, RMS −25.3 dBFS, the same bytes on all
three launches and on the two launches before them (seeded sampling is deterministic on this
path, as on the Mac). Not the Mac leg's bytes (a different RNG draws the samples), and the same
frame count as the Mac leg's output.

## Findings

1. **The public Qwen3-TTS LiteRT pipeline runs at RTF 8.6 on the Galaxy S26 CPU at the Android
   app's defaults** — 80 s for 9.3 s of speech, thermal nominal, and the cost sits where the Mac
   leg found it: the MTP loop (17 invokes of the 440 MB fp32 graph per frame; the app gives it 2
   threads, the Python sample 1). The talker and codec together are 15 %. The card's own phone
   figure for this configuration is "Pixel 8a … RTF ≈ 6.7" on a different text and a different
   phone; it is not this row.
2. **The audio is intelligible and complete.** whisper-tiny returns the 27 input words exactly
   (WER 0.000 ×3). The protocol instrument (parakeet-tdt-0.6b-v3, 5 s chunks, 0.4 overlap,
   timestamp merger) returns 0.148 ×3 — 1 substitution ("used a command") and 3 insertions, the
   phrase "voice snapped with" doubled at a chunk seam — the same transcript on every launch
   because the audio is the same bytes. The row passes the 0.5 bar with either reading; the
   protocol's number is the 0.148, the second opinion says the seam is the instrument's, not the
   speech's. (On the Mac leg's audio the seam fell elsewhere and parakeet read 0.000.)
3. **The first pass of this sitting was thrown out (spread-rule).** Launched at 45 s pauses right
   after the smoke run and a 10 min anchor, on a phone already at 33.6 °C with the CPU already
   capped, three launches read 8.31 / 8.86 / 9.32 (+12 %). Kept as `attempt1/` (records
   `*.jsonl.attempt1`, their logs and one audio copy — the same bytes). After 25 min idle
   (battery 38.8 → 33.5 °C, caps cleared) the anchor was re-run and the cell re-taken at 120 s
   pauses: 5 % range. A phone TTS cell wants a cool start and long pauses; the Mac leg's 5 s
   pause does not transfer.
4. **The sitting's first anchor was invalid by operator error, not by the phone.**
   `../2026-09-27-tts-rtf-v1-s26-anchor-android/` ran `./bench matrix` without `BENCH_CPU_MASK=`,
   so the llama.cpp anchor ran under `taskset f0` — the mask the S26 must not use
   (`devices/galaxy-s26.md`) — and read 9.8–10.1 tok/s against 107.6 (`SESSION.json` there:
   NOT_ADMITTED, anchor-collapse). The litert-lm-gpu anchor in the same run was normal
   (52.4–52.7). The records stay as raw with `conditions.cpuAffinity: taskset f0`; the unmasked
   retake is the sitting's anchor.
5. **Same graphs, same Hub bytes as the Mac leg, verified on the phone.** The app's copies (pushed
   on 2026-09-19 by the sample's own install script) hash to the Hub's LFS sha256 for the eight
   LFS files and to the Hub's git blob ids for `vocab.json` / `merges.txt`; the sample's tokenizer
   self-test passes (6 cases) in every launch.

Not run this sitting: the `talker_fp32` recipe (the app hard-codes `talker_int4`), greedy
decoding, other voices / languages, the Mac leg's 8 / 1 / 8 thread split on the phone (a second
recipe row, not v1), any GPU path (the app is CPU-only), Pixel 8a, iPhone (no iOS sample).
