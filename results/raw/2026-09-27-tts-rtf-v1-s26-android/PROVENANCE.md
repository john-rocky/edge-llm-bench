# 2026-09-27 TTS real-time factor, v1 — Galaxy S26 leg (first phone cell)

Task family definition: `docs/tts-rtf-v1.md` (section "Android leg"). Cells: the `android` row of
`matrices/tts-rtf-v1.cells` (`scripts/tts_rtf_android.py matrices/tts-rtf-v1.cells --campaign
2026-09-27-tts-rtf-v1-s26 --serial RFGL80R6A6H --pause 120`). Numbers and findings: `NOTES.md`
here. One JSONL for the cell, one record per process launch; per launch under `logs/`: the
`am instrument` stream, the harness's timing JSON (`*.worker.json`), the phone log slice
(`*.logcat.txt`), the round-trip ASR's stderr and the second-opinion ASR's stderr
(stored-report-rule). Audio under `audio/` (24 kHz as the app wrote it, 16 kHz as the ASR read it;
sha256 in every record and in `SHA256SUMS`). The driver's log is `runlog.txt`;
`hub-api-blobs.json` is the Hub API answer the file check used.

## Phone

Galaxy S26 (`SM-S942Q`, Snapdragon `SM8850`, product `m1q`), Android 16, security patch
2026-06-05, adb serial `RFGL80R6A6H`, USB attached, battery 79 % (the phone holds it there),
screen off throughout (`conditions.screen: off-usb (mWakefulness=Dozing)`, measured before every
launch; `stay_on_while_plugged_in = 0`), no CPU affinity mask (the app's threads are scheduled by
the OS; the S26 runs unmasked, `devices/galaxy-s26.md`). The phone's shared hold
(`~/code/litertlm-convert/community_accel_work/s2_npu_sweep/.device_hold`, holder pid 66833,
`tts-rtf-s26`) was held by this lane from 11:06 JST, before the first install, to after the last
launch. The recurring dashboard job had measured the S26 the same night (02:00–05:27 JST,
`logs/dashboard-job/ledger.tsv`); its next firing is 02:00, after this sitting.

## Instrument

- **App**: the sample's own Android app, `john-rocky/litert-samples`
  `compiled_model_api/text_to_speech_lm/kotlin_cpu/android`, branch `qwen3-tts-sample`, commit
  `a1f5edf3948e9575824bf6ea568fc90ad6a8fef0` (2026-07-11) — the same commit as the Mac leg's
  Python pipeline — checked out as a detached worktree
  (`~/code/litert-samples-qwen3tts-a1f5edf-wt`). `src/main` is byte-identical to the commit:
  `Qwen3TtsEngine.kt` sha256 `d3c7e47b…fe85e`, `QwenBpeTokenizer.kt` `77ac64fd…5194`,
  `Npy.kt` `e8765184…3d3c`, `MainActivity.kt` `64face0a…7ad3` (`provenance.pipelineSha256`).
  Added beside it, copies in `android/tts-rtf/`: the instrumentation harness
  `app/src/androidTest/.../TtsRtfBench.kt` (sha256 `5399b899…8d7a`) and, in
  `app/build.gradle.kts`, the test runner + androidx.test / junit test dependencies and the LiteRT
  AAR pin raised from the sample's 2.1.5 to **2.1.6** (the Mac leg's runtime version).
- **Runtime**: `com.google.ai.edge.litert:litert:2.1.6` (AAR sha256 `6bbbf3e1…31ed`, Maven
  Google), `CompiledModel` with `Accelerator.CPU` and `CpuOptions(threads)` — XNNPACK — at the
  sample's own thread counts: talker 4, MTP 2, codec 4 (`Qwen3TtsEngine.load()`).
- **Build**: Gradle 8.11.1 wrapper, AGP 8.7.3, Kotlin 2.2.10, Temurin JDK 17.0.16, 2026-09-27
  11:07 JST; `app-debug.apk` sha256 `44cace97…7bec`, `app-debug-androidTest.apk` sha256
  `f194886d…0b71`, both installed with `adb install -r -t` at 11:08:31 JST over the copy the
  same sample had installed on this phone on 2026-09-19 (the app's data — the model files —
  survived the reinstall).
- **What one launch does**: `am instrument -w -r -e text <the 27 words> -e language english
  -e seed 1 -e name <slug>_runN <pkg>.test/androidx.test.runner.AndroidJUnitRunner` — a fresh app
  process; the harness constructs `Qwen3TtsEngine(filesDir)` (load, timed), runs the sample's
  tokenizer self-test (`assets/tokenizer_test_vectors.json`, 6 cases), then
  `synthesize(text, language = "english", greedy = false, seed = 1)` (timed = `ttsSynthesisSeconds`),
  writes the 24 kHz PCM16 WAV and the timing JSON to the app's external files dir; the host
  pulls both. Memory: `VmHWM` of the app process, polled by the host every 0.5 s and read by the
  harness after synthesis (`metrics.memoryPeakResidentMB` = the larger).
- **Record identity**: `runtime: litert-cpu`, `engineVersion: ai-edge-litert (Android AAR) 2.1.6
  + qwen3-tts-sample@a1f5edf`, `harnessStamp: tts-rtf-v1-android-2026-09-27`.

## Model files (the app's `filesDir`, pushed by the sample's `install_to_device.sh` on 2026-09-19; hashes read ON THE PHONE with `run-as … sha256sum` on 2026-09-27 and compared with the Hub API at revision `528cca7d`)

| Hub path | on-phone name | sha256 | Hub check |
|---|---|---|---|
| `talker_int4.tflite` (256 MB) | same | `e03df54e…848db` | = LFS sha256 |
| `mtp_fp32.tflite` (441 MB) | same | `7cc01b40…adf03` | = LFS sha256 |
| `codec_decoder_fp32.tflite` (457 MB) | same | `491e10c2…da39d` | = LFS sha256 |
| `tables/codec_embedding_fp32.npy` (13 MB) | `codec_embedding_fp32.npy` | `47fa9e30…9e39` | = LFS sha256 |
| `tables/mtp_embeddings_fp16.npy` (63 MB) | `mtp_embeddings_fp16.npy` | `fea581b6…6706` | = LFS sha256 |
| `tables/text_embedding_fp16.npy` (622 MB) | `text_embedding_fp16.npy` | `6fab9de0…441e` | = LFS sha256 |
| `tables/text_projection_fp32.npz` (25 MB) | `text_projection_fp32.npz` | `ebb0f6a7…c100` | = LFS sha256 |
| `voices/demo_speaker.npy` (4 KB) | `demo_speaker.npy` | `b1527f54…1c3c` | = LFS sha256 |
| `vocab.json` (2.8 MB, not LFS) | same | `ca10d7e9…0910` | git blob sha1 `4783fe10…c569` = Hub blobId |
| `merges.txt` (1.7 MB, not LFS) | same | `599bab54…6f5e3` | git blob sha1 `20024bfe…c2f0` = Hub blobId |

All ten are the same bytes the Mac leg measured (its `SHA256SUMS`) where the Mac leg used them;
the Mac leg read `tokenizer.json` (the `tokenizers` library) where the Android app reads
`vocab.json` + `merges.txt` (its own Kotlin BPE). `provenance.hfLfsSha256Verified` is true for
all ten in every record. On-disk total 1,880.8 MB (`model.onDiskSizeMB`).

## Round-trip ASR (the audio check, on the Mac)

The asr-rtf-v1 instrument, unchanged from the Mac leg: LiteRT-LM `omni/asr` `asr_runner` at
`main@1dadd00c` (`.build/asr-runner-1dadd00c`), `parakeet_tdt_0.6b_v3_5s_i8_stateful.tflite`
(sha256 `334745b8…d16b`), `--backend cpu --num_threads 4 --overlap_ratio 0.4
--text_merger_type timestamp`; input = the app's 24 kHz PCM16 WAV converted to 16 kHz PCM16 mono
with `afconvert`; WER against the input text after the ASR set's normalization
(`metrics.ttsRoundTripWordErrorRate`, bar 0.5). **Second opinion, provenance only**
(`provenance.roundTripSecondOpinion`): `whisper_tiny_30s_i8.tflite` (sha256 `6748ac56…4a9`), same
runner and flags — a ~10 s clip is one 30 s window, so no chunk-merge seam.

## Fixture

`evaldata/tts/libri1272-2sent/manifest.json` (sha256 `7e689dcb…5275`): "The little girl had
been asleep, but she heard the raps and opened the door. The other voice snapped with a harsh
urgency, clearly used to command." (27 words), `language: english`, voice `demo_speaker.npy`.

## Sitting (JST)

| time | what | where |
|---|---|---|
| 11:06:03 | hold taken (`tts-rtf-s26`, pid 66833) | — |
| 11:07–11:08 | APKs built and installed | PROVENANCE "Instrument" |
| 11:08:32–11:09:52 | driver smoke, one launch by hand (RTF 8.15, tokenizer self-test PASS; not a measurement) | not stored (scratch) |
| 11:11:50–11:25 | anchor, **masked by mistake** (`taskset f0`): llama.cpp 9.8 / 10.1 / 10.0 tok/s, litert-lm-gpu 52.55 / 52.7 / 52.38 → NOT_ADMITTED (anchor-collapse) | `../2026-09-27-tts-rtf-v1-s26-anchor-android/` + its `SESSION.json` |
| 11:23:14–11:29:44 | cell, first pass, 45 s pauses, warm start: 8.31 / 8.86 / 9.32 → thrown out (spread-rule) | `attempt1/` |
| 11:31–11:56 | idle cool-down: battery 38.8 → 33.5 °C, CPU caps cleared | `runlog.txt` has none of it; the chain script's log is not stored |
| 11:56:23–12:08 | anchor, unmasked (`BENCH_CPU_MASK=`): llama.cpp 107.9 / 107.8 / 106.8 (median 107.8 vs 107.6, ratio 1.002), litert-lm-gpu 58.54 / 52.44 / 52.75 → ADMITTED | `../2026-09-27-tts-rtf-v1-s26-anchor-retake-android/` + its `SESSION.json` |
| 12:09:30–12:17:45 | **the cell**, 120 s pauses, battery 33.0 °C at launch 1: 8.40 / 8.62 / 8.83 | the JSONL here |
| 12:20 | hold released, the app's output dir on the phone removed | — |

Gate before every launch: thermal status 0 and battery ≤ 36.0 °C (the asr-rtf-v1 Android leg's
rule); in the retake it never had to wait (33.0 / 34.6 / 35.4 °C at launch). The dashboard's
recurring job did not fire during the sitting (its firings are 02:00 and 05:30).

Deviation from the brief: the campaign directory is `…-s26-android/`, the repo's suffix for
phone captures (asr / vl legs), not `…-s26/`.
