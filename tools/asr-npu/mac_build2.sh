#!/bin/bash
# The decoder-only run's build (docs/asr-npu-v1.md), inside one Mac measurement window:
#   python3 ~/code/standup/tools/quiet/quiet_hold.py asr-npu-build2 -- gtimeout 900 bash tools/asr-npu/mac_build2.sh
# The bench test APK with DecoderBufferTest (the app APK on the phone stays the frozen one), frozen to
# .build/asr-npu/apk2, then the driver's dry run of the sitting (no adb).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
APPDIR="$HOME/code/litert-samples-asr-npu-wt/samples/litert/speech_recognition/AndroidApp"
echo "start $(date +%T) $(git -C "$APPDIR" rev-parse --short HEAD)"
bash "$APPDIR/gradlew" -p "$APPDIR" --console=plain --continue :app:assembleBenchAndroidTest
bash "$ROOT/tools/asr-npu/run_npu_s26.sh" freeze2
for f in $(unzip -Z1 "$ROOT/.build/asr-npu/apk2/app-bench-androidTest.apk" | grep '\.dex$'); do
  unzip -p "$ROOT/.build/asr-npu/apk2/app-bench-androidTest.apk" "$f" | strings | grep -m1 'DecoderBufferTest' || true
done | sort -u | head -3
export DRY=1
bash "$ROOT/tools/asr-npu/run_npu_s26.sh" install-test2 2>&1 | grep -c 'DRY adb' | sed 's/^/dry install-test2 adb commands: /'
for d in d-cpu-shared d-npu-shared d-npu-separate d-npu-shared-noenc; do
  bash "$ROOT/tools/asr-npu/run_npu_s26.sh" decoder $d 2>&1 | grep 'am instrument' | cut -c1-420
done
bash "$ROOT/tools/asr-npu/run_npu_s26.sh" cleanup 2>&1 | grep -c 'DRY adb' | sed 's/^/dry cleanup adb commands: /'
echo "end $(date +%T)"
