# 2026-09-24 TTS real-time factor, v1 — first cell, Mac leg

Task family definition: `docs/tts-rtf-v1.md`. Cells: `matrices/tts-rtf-v1.cells`
(`./bench matrix matrices/tts-rtf-v1.cells --platform mac --campaign 2026-09-24-tts-rtf-v1-m4max`,
session start 14:02:53 JST). Numbers and findings: `NOTES.md` here. One JSONL for the cell, one
record per process launch; per launch under `logs/`: the worker's stderr, its timing JSON
(`*.worker.json`) and the round-trip ASR's stderr (stored-report-rule). Audio under `audio/`
(sha256 in every record and in `SHA256SUMS`).

## Host

Mac Studio M4 Max 128 GB (`Mac16,9`), macOS 27.0 (26A428), 16 cores. Session anchor (`mlx-swift`
Qwen3-0.6B-4bit short-chat, runs=3): warm 561.2 / 565.2 tok/s, cold 560.0, thermal nominal — 2 %
above the last five Mac sessions' band (527–550 warm). The sitting ran inside a window another
session (an Xcode-building Core AI lane) had agreed to keep free of builds (14:00–14:15); the
per-launch foreign-process samples (`provenance.hostBefore/After.others`) show only `cmux`
(31–35 %), the system `Storage` extension (92 % at launch 2) and a Chrome renderer (23 %).
`pmset -g therm` reported no CPU speed limit.

## Instrument

- **Pipeline**: `qwen3_tts_pipeline.py` (sha256 `6822feca…2248a0`) from `john-rocky/litert-samples`,
  path `compiled_model_api/text_to_speech_lm/python`, branch `qwen3-tts-sample`, commit
  `a1f5edf3948e9575824bf6ea568fc90ad6a8fef0` (2026-07-11), fetched with `gh api` on 2026-09-24
  into `.build/qwen3-tts-sample-a1f5edf/`. `scripts/tts_rtf_worker.py` imports it unchanged and
  calls `Qwen3TtsPipeline(model_dir, talker_file='talker_int4.tflite', num_threads=8)` then
  `synthesize(text, speaker, language='english', do_sample=True, seed=1)` — the sample's own
  `synthesize.py` call with a fixed seed.
- **Runtime**: `.build/tts-venv` (Python 3.12.12 via pyenv): `ai-edge-litert==2.1.6`,
  `ml_dtypes==0.6.0`, `numpy==2.5.3`, `tokenizers==0.23.2`, `soundfile==0.14.0`,
  `huggingface_hub==1.32.0` (full `pip freeze` in every record's `provenance.venvFreeze`).
  CompiledModel with `CpuOptions` (XNNPACK); 8 threads for talker / codec, 1 for the MTP graph
  (fixed by the pipeline).
- **Record identity**: `runtime: litert-cpu`, `engineVersion: ai-edge-litert 2.1.6 +
  qwen3-tts-sample@a1f5edf`, `harnessStamp: tts-rtf-v1-2026-09-24`.

## Model files (`.build/tts-models/Qwen3-TTS-12Hz-0.6B-Base/`; every sha256 = the Hub's LFS sha256, `provenance.hfLfsSha256Verified` true for all nine)

| file | sha256 | where it came from |
|---|---|---|
| `talker_int4.tflite` (256 MB) | `e03df54e…848db` | local archive copy (`/Volumes/HD-SGDA/archive/litertlm-convert/out/qwen3tts-day0/folder/`), verified against the Hub API |
| `mtp_fp32.tflite` (441 MB) | `7cc01b40…adf03` | same |
| `codec_decoder_fp32.tflite` (457 MB) | `491e10c2…da39d` | same |
| `tokenizer.json` (11 MB) | `a7d41145…1fab` | the Hub, 2026-09-24 (24 parallel range requests — the Hub served ~0.2 MB/s per connection from this host all afternoon) |
| `tables/codec_embedding_fp32.npy` (13 MB) | `47fa9e30…9e39` | the Hub, same way |
| `tables/mtp_embeddings_fp16.npy` (63 MB) | `fea581b6…6706` | the Hub, same way |
| `tables/text_embedding_fp16.npy` (622 MB) | `6fab9de0…441e` | the Hub, same way (two stalled chunks refetched, whole-file sha256 verified) |
| `tables/text_projection_fp32.npz` (25 MB) | `ebb0f6a7…c100` | the Hub, same way |
| `voices/demo_speaker.npy` (4 KB) | `b1527f54…1c3c` | local copy (`flutter_gemma/…/test/golden/qwen3/voices/`), verified against the Hub API |

Repo revision on the Hub at fetch time: `528cca7d` (litert-community/Qwen3-TTS-12Hz-0.6B-Base,
created 2026-07-07). `HF_SHA256SUMS` (the Hub's per-file sha256 as fetched from
`https://huggingface.co/api/models/<repo>?blobs=true`) is reproduced in `SHA256SUMS`.

## Round-trip ASR (the audio check)

LiteRT-LM `omni/asr` `asr_runner` at `main@1dadd00c` — the asr-rtf-v1 build of 2026-09-19
(`~/code/edge-llm-bench/.build/asr-runner-1dadd00c`, sha256 in that campaign's `SHA256SUMS`) —
with `parakeet_tdt_0.6b_v3_5s_i8_stateful.tflite` (sha256 `334745b8…d16b`, re-downloaded
from the Hub this afternoon, verified; the asr-rtf-v1 record carries the same sha256),
`--backend cpu --num_threads 4 --overlap_ratio 0.4 --text_merger_type timestamp` (the asr-rtf-v1
defaults). Input: the 24 kHz PCM16 WAV converted to 16 kHz PCM16 mono with macOS `afconvert`
(`-f WAVE -d LEI16@16000 -c 1`). WER against the input text after the ASR set's normalization
(lower-case, hyphen → space, `[a-z0-9']` only): 0.000 on all three launches; transcript in
every record.

## Fixture

`evaldata/tts/libri1272-2sent/manifest.json`: "The little girl had been asleep, but she heard the
raps and opened the door. The other voice snapped with a harsh urgency, clearly used to command."
(27 words; LibriSpeech dev-clean 1272-135031-0003 + 1272-141231-0011 references, CC BY 4.0,
re-cased and punctuated), `language: english`, voice `voices/demo_speaker.npy`.
