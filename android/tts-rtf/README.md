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
cd ~/code/edge-llm-bench && scripts/tts_rtf_android.py matrices/tts-rtf-v1.cells --campaign <campaign> --serial <serial>
```

The harness writes `<name>.json` (timings, stage clocks, tokenizer self-test, VmHWM)
and `<name>_24k.wav` under `/sdcard/Android/data/com.google.ai.edge.examples.text_to_speech_lm/files/tts-rtf/`;
`scripts/tts_rtf_android.py` pulls them, runs the ASR round trip on the Mac and writes
the records.
