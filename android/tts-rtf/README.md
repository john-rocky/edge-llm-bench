# tts-rtf-v1 Android harness (docs/tts-rtf-v1.md "Android leg")

The Android leg measures the Qwen3-TTS sample's **own app**
(`john-rocky/litert-samples` `compiled_model_api/text_to_speech_lm/kotlin_cpu/android`,
branch `qwen3-tts-sample`, commit `a1f5edf3948e9575824bf6ea568fc90ad6a8fef0`) through
an instrumentation test that calls the sample's engine exactly as MainActivity does.
This directory keeps the two things added beside the sample so the build can be
reproduced; the sample's `src/main` is not modified.

- `TtsRtfBench.kt` — goes to
  `app/src/androidTest/java/com/google/ai/edge/examples/text_to_speech_lm/TtsRtfBench.kt`.
- `build.gradle.kts.patch` — `testInstrumentationRunner`, the androidx.test /
  junit test dependencies, and the LiteRT AAR pin raised from the sample's 2.1.5 to
  2.1.6 (the Mac leg's runtime version; `provenance.litertAar` carries the AAR sha256).

```bash
git -C ~/code/litert-samples worktree add --detach ~/code/litert-samples-qwen3tts-a1f5edf-wt a1f5edf3948e9575824bf6ea568fc90ad6a8fef0
cd ~/code/litert-samples-qwen3tts-a1f5edf-wt/compiled_model_api/text_to_speech_lm/kotlin_cpu/android
git apply ~/code/edge-llm-bench/android/tts-rtf/build.gradle.kts.patch
mkdir -p app/src/androidTest/java/com/google/ai/edge/examples/text_to_speech_lm
cp ~/code/edge-llm-bench/android/tts-rtf/TtsRtfBench.kt app/src/androidTest/java/com/google/ai/edge/examples/text_to_speech_lm/
echo "sdk.dir=$HOME/Library/Android/sdk" > local.properties
JAVA_HOME=$(/usr/libexec/java_home -v 17) ./gradlew --no-daemon :app:assembleDebug :app:assembleDebugAndroidTest
adb -s <serial> install -r -t app/build/outputs/apk/debug/app-debug.apk
adb -s <serial> install -r -t app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk
./install_to_device.sh   # the sample's own model push (Hub -> the app's filesDir); the driver verifies every file's hash on the phone
cd ~/code/edge-llm-bench && scripts/tts_rtf_android.py matrices/tts-rtf-v1.cells --campaign <campaign> --serial <serial> --recipes default   # this build has no fast path
```

The harness writes `<name>.json` (timings, stage clocks, tokenizer self-test, VmHWM,
and which graphs the launch ran: the graph files in filesDir, the engine's selection
flags, the graph files the process mapped) and `<name>_24k.wav` under
`/sdcard/Android/data/com.google.ai.edge.examples.text_to_speech_lm/files/tts-rtf/`;
`scripts/tts_rtf_android.py` pulls them, runs the ASR round trip on the Mac and writes
the records.

## Fast-graph recipe row (`recipe=mtp-folded-int8-codec-split`, docs/tts-rtf-v1.md)

The same steps on `a1f5edf` + the sample's fast-path commit `50fb1674` (branch
`qwen3-tts-fast-path`, a local branch of `~/Downloads/litert-upstream/litert-samples`;
cherry-picked locally, never pushed), then the three fast graphs pushed beside the
default set the way that branch's `install_to_device.sh` pushes them
(`mtp_folded_int8.tflite` goes to filesDir as `mtp_folded.tflite`). The one build runs
both android rows; the driver parks the fast files for the default row.

```bash
git -C ~/code/litert-samples fetch ~/Downloads/litert-upstream/litert-samples qwen3-tts-fast-path
git -C ~/code/litert-samples worktree add --detach ~/code/litert-samples-qwen3tts-fast-wt a1f5edf3948e9575824bf6ea568fc90ad6a8fef0
cd ~/code/litert-samples-qwen3tts-fast-wt && git -c user.name=john-rocky -c user.email=rockyshikoku@gmail.com cherry-pick 50fb167438ab3bb1ff1d6f55d2708aa5cdd5c1b3
cd compiled_model_api/text_to_speech_lm/kotlin_cpu/android   # then the patch / harness copy / build / install lines above
M=~/code/edge-llm-bench/.build/tts-models/Qwen3-TTS-12Hz-0.6B-Base
HF_HUB_DISABLE_XET=1 hf download litert-community/Qwen3-TTS-12Hz-0.6B-Base codec_partA.tflite mtp_folded_int8.tflite codec_partB.tflite --revision 528cca7d2ddf6f5c1e1127f24a7f8786f80fa6e8 --local-dir $M
for p in "mtp_folded_int8.tflite mtp_folded.tflite" "codec_partA.tflite codec_partA.tflite" "codec_partB.tflite codec_partB.tflite"; do
  adb -s <serial> push $M/${p%% *} /data/local/tmp/${p##* }; adb -s <serial> shell chmod 644 /data/local/tmp/${p##* }
  adb -s <serial> shell run-as com.google.ai.edge.examples.text_to_speech_lm cp /data/local/tmp/${p##* } files/${p##* }
  adb -s <serial> shell rm /data/local/tmp/${p##* }; done
cd ~/code/edge-llm-bench && TTS_ANDROID_APP_DIR=~/code/litert-samples-qwen3tts-fast-wt/compiled_model_api/text_to_speech_lm/kotlin_cpu/android \
  scripts/tts_rtf_android.py matrices/tts-rtf-v1.cells --campaign <campaign> --serial <serial> --pause 120 --interleave --wait-uncapped --warmup-rounds 1
```
