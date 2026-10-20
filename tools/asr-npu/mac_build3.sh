#!/bin/bash
# The decoder-only run 2's build (docs/asr-npu-v1.md), inside one Mac measurement window:
#   python3 ~/code/standup/tools/quiet/quiet_hold.py asr-npu-build3 -- gtimeout 900 bash tools/asr-npu/mac_build3.sh
# The bench test APK (seeded encoder outputs, the pattern mode, its own logcat), frozen to
# .build/asr-npu/apk3, then the driver's dry run of the sitting (no adb).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
APPDIR="$HOME/code/litert-samples-asr-npu-wt/samples/litert/speech_recognition/AndroidApp"
echo "start $(date +%T) $(git -C "$APPDIR" rev-parse --short HEAD)"
bash "$APPDIR/gradlew" -p "$APPDIR" --console=plain --continue :app:assembleBenchAndroidTest
bash "$ROOT/tools/asr-npu/run_npu_s26.sh" freeze3
for f in $(unzip -Z1 "$ROOT/.build/asr-npu/apk3/app-bench-androidTest.apk" | grep '\.dex$'); do
  unzip -p "$ROOT/.build/asr-npu/apk3/app-bench-androidTest.apk" "$f" | strings | grep -m2 -E 'BufferPattern|enc_source' || true
done | sort -u | head -4
export DRY=1
bash "$ROOT/tools/asr-npu/run_npu_s26.sh" setup-min 2>&1 | grep -c 'DRY adb' | sed 's/^/dry setup-min adb commands: /'
for d in p-npu-shared p-npu-separate t-npu-shared t-npu-separate; do
  bash "$ROOT/tools/asr-npu/run_npu_s26.sh" decoder2 $d 2>&1 | grep 'am instrument' | cut -c1-420
done
bash "$ROOT/tools/asr-npu/run_npu_s26.sh" cleanup 2>&1 | grep -c 'DRY adb' | sed 's/^/dry cleanup adb commands: /'
echo "end $(date +%T)"
