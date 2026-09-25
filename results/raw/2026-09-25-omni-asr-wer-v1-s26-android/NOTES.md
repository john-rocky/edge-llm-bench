# 2026-09-25 ASR WER through OmniEngine, v1 — Galaxy S26 leg (SM-S942Q, Android 16), CPU

Definition: `docs/omni-asr-wer-v1.md`; the Mac leg with the full table, the window repro and the
hang analysis: `../2026-09-25-omni-asr-wer-v1-m4max-mac/NOTES.md`. Same runner source (`tools/omni-eval/
omni_eval_runner.cc`, `--start_after`/`--append` resume, watchdog 60 s), built with NDK r28
(`bazelisk build --config=android_arm64 --enable_platform_specific_config //omni:omni_eval_runner`),
same model files and tokenizers pushed to `/data/local/tmp/edge-llm-bench/omni/`, the WAV sets
pushed as-is, `phone_matrix.sh` run under `nohup` on the phone (`tools/omni-eval/phone_matrix.sh`).
Each cell waits for the battery to cool to 36 °C first; the phone was at thermal status 2–3 and
45–47 °C by the end of every cell, so the RTFx here is a throttled, sustained number.

| bundle | set | WER | S / D / I | hung | empty | RTFx | Mac CPU WER |
|---|---|---|---|---|---|---|---|
| parakeet-tdt-0.6b-v3 (i8) | test-clean | **17.67** | 1328 / 5991 / 2048 | 0 | 11 | 19.9 | 17.67 |
| whisper-tiny (i8) | test-clean | **12.46** | 4807 / 556 / 1240 | 0 | 0 | 9.7 | 12.46 (byte-identical S/D/I) |
| parakeet-tdt-0.6b-v3 (i8) | test-other | **16.74** | 2432 / 4079 / 2332 | 1 | 9 | 20.4 | 18.25 |
| whisper-tiny (i8) | test-other | (running) | | | | | 29.58 |

The transcripts are the Mac's: whisper-tiny is byte-identical, parakeet differs in a few dozen
words out of 53,000 (int8 kernel differences between XNNPACK on arm64 Linux and macOS). The hang
lands on 4198-12259-0032 here as on the Mac; 3764-168670-0046, which hangs on the Mac CPU, completes
on the phone — the loop condition sits on a numeric edge, which is why a cap in the decoder rather
than a per-file workaround is the fix.
