# 2026-09-29 TTS real-time factor, v1 — Galaxy S26, fast-graph recipe row interleaved with the default row

Task family definition: `docs/tts-rtf-v1.md` (sections "Android leg" and "Fast-graph recipe row"). Cells:
both `android` rows of `matrices/tts-rtf-v1.cells` — the default graph set and
`recipe=mtp-folded-int8-codec-split` — run as one interleaved sitting
(`TTS_ANDROID_APP_DIR=~/code/litert-samples-qwen3tts-fast-wt/compiled_model_api/text_to_speech_lm/kotlin_cpu/android
scripts/tts_rtf_android.py matrices/tts-rtf-v1.cells --campaign 2026-09-29-tts-rtf-fast-s26 --serial RFGL80R6A6H
--pause 120 --interleave --wait-uncapped --warmup-rounds 1`). Numbers and findings: `NOTES.md` here. One JSONL
per row, one record per process launch; the warm-up launches in `*.jsonl.warmup` (same shape,
`metrics.warmup: true`, outside the `*.jsonl` the summary reads). Per launch under `logs/`: the
`am instrument` stream, the harness's JSON (`*.worker.json`), the phone log slice (`*.logcat.txt`), the
round-trip ASR's stderr and the second-opinion ASR's stderr (stored-report-rule). Audio under `audio/`
(24 kHz as the app wrote it, 16 kHz as the ASR read it; one copy per row, since every launch of a row wrote
the same bytes; sha256 in every record and in `SHA256SUMS`). The driver's log is `runlog.txt`;
`hub-api-blobs.json` is the Hub API answer the file check used. The thrown-out first pass is `attempt1/`
(its records keep the file paths they were written with; the files they name are under `attempt1/` at the
same relative paths).

## Phone

Galaxy S26 (`SM-S942Q`, Snapdragon `SM8850`, product `m1q`), Android 16, security patch 2026-06-05, adb
serial `RFGL80R6A6H`, USB attached, battery 79 % (the phone holds it there), no CPU affinity mask (the S26
runs unmasked, `devices/galaxy-s26.md`), `stay_on_while_plugged_in = 0` throughout (not changed by this
lane). Screen state as measured before every launch (`conditions.screen`): `Dozing` for the warm-ups and the
first three measured launches, `Awake` from fast run 2 on (it woke between 02:20:31 and 02:24:48 JST; not by
this sitting's commands, cause not checked). The phone's shared hold
(`~/code/litertlm-convert/community_accel_work/s2_npu_sweep/.device_hold`, `tts-fast-s26`, owner = a keeper
shell, pid 92756) was held by this lane from 00:40:11 JST, before the first install, to 02:32:10, after the
output dir on the phone was cleared; the next lane took it at 02:32:23. The recurring dashboard job fired at
02:00 and re-chose at 02:15 and 02:30; it listed the S26 as done for the week (admitted 2026-09-28 05:26) and
measured nothing (`logs/dashboard-job/2026-09-29-auto.log`). One other app process sat cached on the phone
all night (`com.google.ai.edge.examples.litert_model_zoo`, `oom_score_adj` 940, no CPU in `top` at 00:39);
not touched.

## Instrument

- **App**: the sample's own Android app, `john-rocky/litert-samples`
  `compiled_model_api/text_to_speech_lm/kotlin_cpu/android`, built at local commit
  `4dcb1a3765198b9a9a8074deb807a4694cd94823` = `a1f5edf3948e9575824bf6ea568fc90ad6a8fef0` (branch
  `qwen3-tts-sample`, the 2026-09-27 capture's commit) + a cherry-pick of
  `50fb167438ab3bb1ff1d6f55d2708aa5cdd5c1b3` ("Qwen3-TTS: fast MTP + split codec paths (auto-selected when
  present)", 2026-07-08, branch `qwen3-tts-fast-path`, which exists only in
  `~/Downloads/litert-upstream/litert-samples`; fetched from there, cherry-picked in the detached worktree
  `~/code/litert-samples-qwen3tts-fast-wt`, not pushed anywhere). `git merge-tree` of the pick is clean, and
  the `kotlin_cpu/android` tree after it is `50fb1674`'s (`c14e73f4…`; `a1f5edf`'s is `92d157e9…`): the pick
  changes `Qwen3TtsEngine.kt` (sha256 `452a566b…3534`, was `d3c7e47b…fe85e`) and `install_to_device.sh`;
  `QwenBpeTokenizer.kt` `77ac64fd…5194`, `Npy.kt` `e8765184…3d3c`, `MainActivity.kt` `64face0a…7ad3` are
  the 2026-09-27 files (`provenance.pipelineSha256`, `provenance.pipelineCommitDetail`). Added beside it, as
  on 2026-09-27 (copies in `android/tts-rtf/`): the harness `app/src/androidTest/.../TtsRtfBench.kt` and the
  gradle patch (test runner + androidx.test / junit, LiteRT AAR pin 2.1.5 → **2.1.6**). The harness now also
  records the graph evidence and the process counters: sha256 `c977265c…3df4` for the kept pass and the
  warm-ups, `f5fd8b6d…aee2` for the thrown-out pass (no counters yet).
- **Runtime**: `com.google.ai.edge.litert:litert:2.1.6` (AAR sha256 `6bbbf3e1…31ed`), `CompiledModel` with
  `Accelerator.CPU` — XNNPACK — at the app's own thread counts: talker 4 in both rows; MTP 2 (`mtp_fp32`) or
  4 (`mtp_folded`); codec 4 (`codec_decoder_fp32`) or 4 + 4 (`codec_partA`, then `codec_partB` with
  `CpuOptions(4, 4, null)`, xnnpack_flags 4 = FORCE_FP16).
- **Build**: Gradle 8.11.1 wrapper, AGP 8.7.3, Kotlin 2.2.10, Temurin JDK 17.0.16, 2026-09-29 00:47 JST;
  `app-debug.apk` sha256 `605f5163…5b1b` (installed 00:52:15 with `adb install -r -t` over the 2026-09-27
  build; the app's data survived), `app-debug-androidTest.apk` `72ab711f…a0ef` (00:52:15, thrown-out pass)
  and `2395457e…5768` (rebuilt with the counters, installed 01:47:48; the app APK rebuilt to the same bytes
  and was not reinstalled).
- **Switching rows**: the app picks the folded MTP when `files/mtp_folded.tflite` exists and the split codec
  when `files/codec_partB.tflite` exists. Before every launch the driver renamed the three fast files to
  `<name>.parked` (default row) or back (fast row) inside the app's filesDir, then listed filesDir
  (`provenance.graphSelection.filesDirBeforeLaunch`). The harness read, outside the timed regions, the graph
  files present, the engine's `mtpFolded` / `codecSplit` flags (reflection) and the `.tflite` files mapped
  in `/proc/self/maps`; the driver checked all three against the row (`metrics.ttsGraphSelectionCheck`,
  pass in every launch of both passes).
- **What one launch does**: as on 2026-09-27 — `am instrument -w -r -e text <the 27 words> -e language
  english -e seed 1 -e name <slug>_runN <pkg>.test/androidx.test.runner.AndroidJUnitRunner`, a fresh app
  process, `Qwen3TtsEngine(filesDir)` (timed as load), the sample's tokenizer self-test (6 cases, PASS in
  every launch), `synthesize(text, language = "english", greedy = false, seed = 1)` (timed =
  `ttsSynthesisSeconds`), the 24 kHz PCM16 WAV and the JSON to the app's external files dir, pulled by the
  host; `VmHWM` polled every 0.5 s and read after synthesis. New: page faults and CPU time of the process
  across load and across synthesis (`/proc/self/stat`, `provenance.processCounters`).
- **Launch gate**: thermal status 0, battery ≤ 36.0 °C and, new with `--wait-uncapped`, every CPU policy
  uncapped (`scaling_max_freq == cpuinfo_max_freq`); 120 s before every launch, the first included.
- **Record identity**: `runtime: litert-cpu`, `engineVersion: ai-edge-litert (Android AAR) 2.1.6 +
  qwen3-tts-sample@4dcb1a3` (both rows — the same build), `harnessStamp: tts-rtf-v1-android-2026-09-29`; the
  row is `conditions.ttsRecipe` (`default` / `mtp-folded-int8-codec-split`) and `model.quantization`.

## Model files (the app's `filesDir`; hashes read ON THE PHONE with `run-as … sha256sum` before the first launch and after the last, against the Hub API at revision `528cca7d`)

| Hub path | on-phone name | pushed | sha256 | Hub check | row |
|---|---|---|---|---|---|
| `talker_int4.tflite` (256 MB) | same | 2026-09-19 | `e03df54e…848db` | = LFS sha256 | both |
| `mtp_fp32.tflite` (441 MB) | same | 2026-09-19 | `7cc01b40…adf03` | = LFS sha256 | default |
| `codec_decoder_fp32.tflite` (457 MB) | same | 2026-09-19 | `491e10c2…da39d` | = LFS sha256 | default |
| `mtp_folded_int8.tflite` (230 MB) | `mtp_folded.tflite` | 2026-09-29 00:52 | `f5ab8f82…191b4b` | = LFS sha256 | fast |
| `codec_partA.tflite` (163 MB) | same | 2026-09-29 00:52 | `9d3733c2…499c8c` | = LFS sha256 | fast |
| `codec_partB.tflite` (294 MB) | same | 2026-09-29 00:52 | `3486fafd…46155f` | = LFS sha256 | fast |
| `tables/codec_embedding_fp32.npy` (13 MB) | `codec_embedding_fp32.npy` | 2026-09-19 | `47fa9e30…9e39` | = LFS sha256 | both |
| `tables/mtp_embeddings_fp16.npy` (63 MB) | `mtp_embeddings_fp16.npy` | 2026-09-19 | `fea581b6…6706` | = LFS sha256 | both |
| `tables/text_embedding_fp16.npy` (622 MB) | `text_embedding_fp16.npy` | 2026-09-19 | `6fab9de0…441e` | = LFS sha256 | both |
| `tables/text_projection_fp32.npz` (25 MB) | `text_projection_fp32.npz` | 2026-09-19 | `ebb0f6a7…c100` | = LFS sha256 | both |
| `voices/demo_speaker.npy` (4 KB) | `demo_speaker.npy` | 2026-09-19 | `b1527f54…1c3c` | = LFS sha256 | both |
| `vocab.json` (2.8 MB, not LFS) | same | 2026-09-19 | `ca10d7e9…0910` | git blob sha1 `4783fe10…c569` = Hub blobId | both |
| `merges.txt` (1.7 MB, not LFS) | same | 2026-09-19 | `599bab54…6f5e3` | git blob sha1 `20024bfe…c2f0` = Hub blobId | both |

The three fast files were downloaded to `.build/tts-models/Qwen3-TTS-12Hz-0.6B-Base/` at revision `528cca7d`
(`hf_hub_download`, `HF_HUB_DISABLE_XET=1`), hashed on the Mac to the Hub's LFS sha256, and pushed the way
the fast branch's `install_to_device.sh` pushes (`adb push` to `/data/local/tmp`, `run-as … cp` into
`files/`, the temp copy removed). Read from the files (flatbuffer constants by dtype): `mtp_folded_int8` —
inputs `[1,1,1024]` hidden, `[1,1,1024]` first-codebook embedding, `[15,2048]` noise; outputs 15 int32 codes
and `[15,2048]` logits; int8 per-channel weights on 50 tensors (110 MB), 14 fp32 constants of `[2048, 1024]`
(117 MB), 15 `ARG_MAX`; `codec_partA` fp32 (codes `[1,16,64]` → `[1,1024,64]`), `codec_partB` fp32
(`[1,1024,64]` → 122,880 samples). On-disk totals as the rows read them (`model.onDiskSizeMB`): default
1,880.8 MB, fast 1,669.8 MB.

## Round-trip ASR (the audio check, on the Mac)

Unchanged from 2026-09-27: LiteRT-LM `omni/asr` `asr_runner` at `main@1dadd00c`, `parakeet_tdt_0.6b_v3_5s_i8_stateful.tflite`
(sha256 `334745b8…d16b`), `--backend cpu --num_threads 4 --overlap_ratio 0.4 --text_merger_type timestamp`,
input = the app's WAV converted to 16 kHz PCM16 mono with `afconvert`, WER after the ASR set's normalization
(`metrics.ttsRoundTripWordErrorRate`, bar 0.5); second opinion, provenance only: `whisper_tiny_30s_i8.tflite`
(sha256 `6748ac56…4a9`), same runner and flags.

## Fixture

`evaldata/tts/libri1272-2sent/manifest.json` (sha256 `7e689dcb…5275`): "The little girl had been asleep, but
she heard the raps and opened the door. The other voice snapped with a harsh urgency, clearly used to
command." (27 words), `language: english`, voice `demo_speaker.npy`, seed 1.

## Sitting (JST, 2026-09-29)

| time | what | where |
|---|---|---|
| 00:40:11 | hold taken (`tts-fast-s26`, keeper pid 92756) | `hold_keeper.sh` (standup drafts) |
| 00:47–00:52 | build, both APKs installed, the three fast files pushed | this file, "Instrument" |
| 00:52:46–00:53:08 | smoke by hand, fast graphs (RTF 1.79, selection flags true, mapped files the fast set; not a measurement) | standup drafts |
| 00:59:33–01:03:29 | driver smoke, one launch per row, 20 s pause, warm phone (default 9.22, fast 1.90; not measurements) | standup drafts |
| 01:06:02–01:16:05 | cool-down to battery 32.0 °C, no CPU cap | standup drafts `chain.log` |
| 01:16:05–01:26:51 | anchor, unmasked: llama.cpp 105.1 / 105.3 / 107.1 (ratio 1.006 vs 104.7), litert-lm-gpu 53.62 / 52.03 / 52.0 → ADMITTED | `../2026-09-29-tts-rtf-fast-s26-anchor-android/` |
| 01:26:52–01:44:12 | payload, first pass, D F D F D F, no warm-up: default 8.13 / 8.15 / 8.41, fast 1.80 / 1.68 / 1.66 → thrown out (spread-rule, fast row 8.4 %) | `attempt1/` |
| 01:48:57–01:53:59 | cool-down to battery 32.0 °C, no CPU cap | `chain2.log` |
| 01:53:59–02:04:46 | anchor retake, unmasked: llama.cpp 107.7 / 109.6 / 108.2 (ratio 1.028 vs this night's first anchor, 1.033 vs 104.7), litert-lm-gpu 57.77 / 52.53 / 52.14 → ADMITTED | `../2026-09-29-tts-rtf-fast-s26-anchor-retake-android/` |
| 02:04:47–02:31:05 | **the cell**: warm-up round (default 8.32, fast 1.73), then default 8.94 / fast 1.67 / default 9.26 / fast 1.72 / default 9.13 / fast 1.73 | the JSONLs here |
| 02:31–02:32 | files re-hashed on the phone (13 OK), the app's output dir cleared, hold released 02:32:10 | `runlog.txt`, standup drafts |

Deviations from the brief, all recorded here: (1) a warm-up round (one unmeasured launch per row) came before
the measured launches of the kept pass — added after the first pass failed the spread-rule on its first fast
launch, so that every measured launch had the same launch history; (2) the launch gate also waited for
uncapped CPUs (`--wait-uncapped`); (3) the harness gained the page-fault / CPU-time counters between the
passes (test APK rebuilt, app APK unchanged); (4) admission was judged by `admit()` against the checkout's
summary as `./bench matrix` had just rebuilt it — the helper meant to judge against a temp summary did not
reach `admit()` (`load_rows` binds its CSV path at import); re-judged with the path rebound, both anchors
give the same reference and ratio (files in the standup drafts).
