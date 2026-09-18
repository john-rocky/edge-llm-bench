# 2026-09-19 ASR real-time factor v1 — Mac leg, first cell: numbers and findings

Definition: `docs/asr-rtf-v1.md`. Identities (engine build, dylibs, model files, tokenizers,
audio set, host): `PROVENANCE.md`. Records: one JSONL per cell (three process launches
each), runner stderr per launch under `logs/`, the diagnosis runs under `probes/`.
Session 06:27:30–06:37:15 JST; anchor (MLX Qwen3-0.6B short-chat) warm 539.9 tok/s, in band.

## The table (LiteRT-LM `main@1dadd00c` `omni/asr`, stream = 82.335 s LibriSpeech dev-clean 1272)

RTF = engine processing wall / audio seconds, median of 3 launches, range in brackets.
WER is the text check (default `timestamp` merger, manifest normalization), not a ranking.

| model (litert-community) | file | arm | RTF | processing s | load s | first text ms | WER (S/D/I), 3 launches | peak RSS MB | text check |
|---|---|---|---|---|---|---|---|---|---|
| moonshine-tiny | `moonshine_tiny_5s_i8.tflite` | litert-lm-cpu | **0.0466** [0.0466–0.0467] | 3.83 | 0.05 | 287 | 0.441 (31/0/52) ×3 identical | 168 | passes with a caveat: the default merger duplicates overlap text (0.245 under `levenshtein`, `probes/`) |
| moonshine-tiny | same | litert-lm-gpu | 0.0323 [0.0268–0.0338] | 2.66 | 0.16 | 180 | 0.973 / 1.931 / 1.590 — garbage after the first chunk, different every launch | 231 | **FAILS** — the rate is not a measurement (spread-rule too: ±20 %) |
| whisper-tiny | `whisper_tiny_30s_i8.tflite` | litert-lm-cpu | **0.0440** [0.0432–0.0442] | 3.62 | 0.06 | 2054 | 0.372 (31/21/18) ×3 | 366 | passes |
| whisper-tiny | same | litert-lm-gpu | **0.0190** [0.0189–0.0190] | 1.56 | 0.13 | 892 | 0.351 ×3 | 278 | passes |
| parakeet-tdt-0.6b-v3 | `parakeet_tdt_0.6b_v3_5s_i8_stateful.tflite` | litert-lm-cpu | **0.0265** [0.0264–0.0267] | 2.18 | 0.37 | 167 | 0.197 (11/22/4) ×3 | 1308 | passes |
| parakeet-tdt-0.6b-v3 | same | litert-lm-gpu | **0.0177** [0.0176–0.0178] | 1.46 | 0.60 | 119 | 0.266 ×3 | 1353 | passes: per-word decode agrees with the CPU run (`adam/atom`, `mr/mister`); the extra 0.07 is two chunk-boundary merges (a duplicated half-sentence, the last three short utterances dropped) |
| Qwen3-ASR-0.6B | `qwen3_asr_0.6b_5s_i8.litertlm` | litert-lm-cpu | **0.0934** [0.0932–0.0935] | 7.69 | 0.78 | 1000 | 0.463 (33/8/46) ×3 | 2460 | weak: the model's per-chunk header tokens leak into the text (`<asr_text>`, `English`, `Vocalization`, `recognize the pitch.`) — the engine's `decodeSkipUntilTokenId` handles only the first chunk of a stream |
| Qwen3-ASR-0.6B | same | litert-lm-gpu | 0.2256 [0.2247–0.2263] | 18.58 | 0.74 | — | **no text at all**, ×3 | 1277 | **FAILS** — empty transcript, and 2.4× the CPU time |

Spread: every cell but moonshine-gpu repeats within ±1 % across the three launches
(the CPU transcripts are byte-identical launch to launch; whisper-gpu and parakeet-gpu
are deterministic too). `first text ms` is chunk-loop start → first confirmed text on
stdout; whisper's 2.05 s on CPU is the 30 s window plus the decoder's lazy second
compile inside the first chunk (`logs/…whisper…_cpu_run1.stderr.log`: a second
`Creating LiteRT environment` after `Starting speech recognition`).

Host: no CPU speed limit at any launch (`pmset -g therm`); foreign processes ≥20 % CPU at
launch time are in each record (`provenance.hostBefore.others`): a Chrome renderer
(78–86 %) on 7 of the 24 launches, Spotlight / `mediaanalysisd` indexing the freshly
written WAVs on 4, a sibling session's Python (42–99 %) on 2. The affected launches sit
inside their cells' ±1 % — the runs are 4-thread and the host has 16 cores.

## Findings

1. **Moonshine i8 on Metal transcribes the first window and then drifts into
   hallucinated, repetitive text** ("a little bit of a little bit of …"), differently
   on every launch, while the CPU run of the same file is byte-stable. Diagnosis runs
   (`probes/probe_moonshine_gpu.sh`, outputs there):
   - a 9.9 s clip (2–3 windows) on GPU: WER 0.25 vs 0.125 CPU — a duplicated
     phrase at the first window boundary, deterministic over two launches; the
     breakdown grows with the number of windows;
   - overlap 0 on GPU: still 0.87 (CPU overlap 0: 0.26) → not the merger;
   - `--num_threads 1` on GPU: still 1.43 → not a CPU-side thread race;
   - the **f32 file on GPU aborts** in `CompiledModel::Create` →
     `DelegatePrepare()` → `ReplaceNodeSubsetsWithDelegateKernels` (`probes/ms_f32_gpu.err`,
     twice); the same f32 file on CPU reads 0.31 (better than i8's 0.44 — the
     i8 encoder costs accuracy on CPU too, as the 2026-08-07 card work found).
   So the i8 file compiles on Metal (its DRQ decoder ops presumably fall back to
   XNNPACK) but the state that crosses windows — the 64-token buffer the decoder
   re-scores each step, or the encoder output buffer — is not what the CPU path sees.
   Mechanism not pinned; a per-window dump of the decode inputs on both backends
   is the next instrument. Not filed (owner decision).
2. **Qwen3-ASR `.litertlm` on Metal produces no text** on any launch (exit 0,
   `Finished speech recognition` logged, 18.6 s of processing), the same
   binary on CPU produces text at 7.7 s. The GPU log shows the audio encoder
   compiled with 112/113 external tensors and the LM through
   `LiteRtLmRunner` on Metal (`gpu_backend_metal.mm … Residency Set`), no
   warning. Whether the LM emits nothing, never emits the `<asr_text>` skip
   token (151704), or the merger drops everything is not visible from outside
   the runner. Not filed (owner decision).
3. **Qwen3-ASR on CPU leaks its per-chunk header** into the merged transcript
   (the model prefixes each window's output with language / style tags and
   `<asr_text>`; `decodeSkipUntilTokenId` strips it once per stream, so from the
   second window on the tags appear in the text). Engine-side, not the export.
   RTF 0.093 stands; the WER (0.46) is dominated by it plus overlap duplicates.
4. **The default `timestamp` merger is model-sensitive** (CPU, full stream,
   `probes/`): Moonshine 0.44 → 0.245 under `levenshtein`, Whisper 0.372 →
   0.484 (it drops 70 words), Parakeet 0.197 → 0.186. Processing time is
   unchanged by the merger. v1 keeps the engine default and prints WER beside
   every RTF; a merger comparison is its own cell set.
5. **Overlap 0.4 is 1.7× the audio**: Moonshine CPU RTF 0.047 at the default vs
   0.027 at overlap 0 (`probes/ms_i8_cpu_ov0`). The default is what the Kotlin
   API's session will pay; it is the protocol, stated in every record.
6. **Where the GPU helps on this Mac (i8 files, fp32 GPU precision):** whisper-tiny
   2.3× (0.044 → 0.019), parakeet 1.5× (0.0265 → 0.0177), both with intact text;
   moonshine's 1.4× and Qwen3-ASR's 0.4× are attached to failed text checks and
   must not be read as speeds.

## Not done today

- iPhone / Android legs (no released engine; a device build of `asr_runner` or the
  Kotlin API after #3672).
- f32 recipes as a second row per model (whisper / parakeet / Qwen3-ASR f32 not run;
  moonshine f32 only as the GPU-crash control above).
- Per-utterance launches (short-clip latency, where a 1.6 s utterance pays a full
  5 s or 30 s window).
- A `levenshtein`-merger cell set, and an overlap-0 cell set, for the WER story.
