# 2026-09-24 TTS real-time factor v1 — Mac leg, first cell: numbers and findings

Definition: `docs/tts-rtf-v1.md`. Identities (pipeline commit, venv, model files, ASR instrument,
host): `PROVENANCE.md`. Records: one JSONL (three process launches), the worker's stderr, its
timing JSON and the round-trip ASR log per launch under `logs/`, the synthesized audio under
`audio/` (the three launches produced byte-identical audio — seed 1 — so one copy of the 24 kHz
output and one of the 16 kHz round-trip input are kept; every record carries the sha256).
Session 14:02:53–14:05:20 JST; anchor (MLX Qwen3-0.6B short-chat) warm 561.2 tok/s, 2 % above
the 527–550 band of the last five Mac sessions (not throttled).

## The table (Qwen3-TTS-12Hz-0.6B-Base, the public LiteRT reference pipeline, `ai-edge-litert` 2.1.6 CompiledModel, CPU / XNNPACK, 8 threads)

RTF = synthesize() wall / audio seconds, **median of 3 launches, range in brackets**; the stage
clocks are the pipeline's own.

| graphs (recipe) | arm | RTF | synthesis s | audio s (frames) | prefill / talker / MTP / codec s | load s | peak RSS MB | audio check |
|---|---|---|---|---|---|---|---|---|
| `talker_int4` (blockwise-32 OCTAV) + `mtp_fp32` + `codec_decoder_fp32` — the sample's default set | litert-cpu | **2.416** [2.411–2.520] | 22.4 [22.4–23.4] | 9.28 (116) | 0.13 / 2.7 / 18.6 / 1.06 | 0.63 | 4,757 | passes: round-trip WER **0.000** ×3 (parakeet-tdt-0.6b-v3 transcribes the 27 words back exactly) |

Reading: 2.4 means the pipeline needs 2.4 s of compute for every second of speech — 22 s for a
9.3 s utterance on this Mac, all of it on the CPU. The MTP inner loop is 83 % of it (18.6 s: the
78 M-parameter residual-codebook transformer is invoked 17 times per 80 ms frame, single-threaded
by the pipeline's design); the talker decode is 12 %, the codec 5 %, the prompt prefill 0.6 %.
The card's own M4 Max figure for this configuration is "RTF ≈ 2.5" — the same number.

Spread: launches 2 and 3 agree within 0.2 %; launch 1 is +4 % (talker 2.91 vs 2.6–2.7 s, MTP 19.2
vs 18.4–18.6 s) with nothing but `cmux` at 31 % beside it — a first-process effect, disclosed.
The `Storage` system extension ran at 92 % at launch 2 without moving it. Output audio: peak
|sample| 0.498, RMS −25.1 dBFS, identical bytes on all three launches (sampling with a fixed seed
is deterministic on this path).

## Findings

1. **The public Qwen3-TTS LiteRT pipeline is 2.4× slower than real time on an M4 Max CPU at its
   defaults**, and the cost sits in one place: the MTP loop (17 single-threaded invokes of a
   440 MB fp32 graph per frame). The card's fast path (`mtp_folded_int8` + `codec_partA/B`, on a
   later sample branch) is a second recipe row for this task, not a v1 cell.
2. **The round trip is exact.** parakeet-tdt-0.6b-v3 (the asr-rtf-v1 CPU instrument) returns the
   27 input words verbatim, punctuation included, on all three launches — WER 0.000 against the
   input text. The audio check therefore says "intelligible and complete", nothing about voice
   quality; a listener has the WAV.
3. **There is no LiteRT-LM engine path for a public TTS bundle yet** (`omni/tts` expects file
   layouts that are not on the Hub and ships no CLI), so this row's `runtime` is `litert-cpu`
   (the LiteRT runtime through the model's own host loop), not `litert-lm-cpu`; the two never pool.
4. **The Hub throttled this host to ~0.2 MB/s all afternoon**; the three `.tflite` graphs came
   from a verified local archive copy and the 735 MB of host tables + tokenizer from the Hub over
   24 parallel range requests (PROVENANCE.md) — every file's sha256 equals the Hub's LFS sha256
   (`provenance.hfLfsSha256Verified` all true).

Not run this sitting: the `talker_fp32` recipe, greedy decoding, other voices / languages,
Kokoro-82M (host steps only in the torch reference today), Sopro / Kitten / Matcha, any GPU or
phone leg.
