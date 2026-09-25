# tools/omni-eval — LiteRT-LM OmniEngine ASR evaluation (2026-09-25)

Definition and results: `docs/omni-asr-wer-v1.md`, `results/raw/2026-09-25-omni-asr-wer-v1-*/NOTES.md`.

- `omni_eval_runner.cc` + `omni.BUILD.patch`: the C++ runner (OmniEngine → PushInputSource, one session per utterance, JSONL out; `--start_after/--append` resume, `--push_chunk_ms`, `--reuse_session`).
- `prep_librispeech.py`, `score.py` (+ `leaderboard_normalizer/`, vendored from huggingface/open_asr_leaderboard, Apache-2.0), `buckets.py`: dataset unpack, leaderboard-style WER, length buckets.
- `run_matrix.sh`, `phone_matrix.sh`: Mac and Galaxy S26 drivers with the 60 s output-stall watchdog (HANGS.txt, resume after the stalled utterance). `run_matrix_fix.sh`, `run_matrix_fix30.sh`: the same for the fixed engine / the 30 s export.
- `ref_whisper.py`: openai-whisper tiny reference on the same WAVs. `nemo_tx.py`, `nemo_cross.py`, `nemo_windows.py`, `nemo_like_feats.py`, `tdt_drive.py`: the NeMo parakeet-tdt-0.6b-v3 reference, encoder/decoder cross-wiring with the tflite export, the 5 s-window empty-rate measurement, NeMo-style features, and a Python driver that reproduces the engine's TDT loop on the tflite.
- `make_pieces.py`: the 5 s pieces of 4507-16021-0047. `rss_probe.sh`, `rss_probe_extra.sh`, `vmmap_probe.sh`: the GPU per-session memory probes.
- `convert_30s.sh`: re-export parakeet-tdt-0.6b-v3 with a 30 s window through litert-samples' official recipe (`compiled_model_api/speech_recognition/convert`, litert-torch 0.9.4).
- `patches/`: against LiteRT-LM main@66058c82 — `01-mel-slaney-power.patch` (librosa-compatible Slaney/power mel behind `melScale`/`melPower` metadata keys), `02-whisper-prompt-token-ids.patch` (`decodePromptTokenIds` for the stateless decoder), `03-model-metadata.patch` (whisper-tiny and parakeet entries using them, plus a `parakeet-tdt-0.6b-v3-30s` entry), `04-espeak-ng-macos-build.patch` (`//omni:omni_engine` on macOS), `05-tdt-max-symbols-per-step.patch` (the hang cap). `espeak_ng.BUILD.macos.patch` and `tdt_decoder.max-symbols-per-step.patch` are the same two, kept at their first paths.
