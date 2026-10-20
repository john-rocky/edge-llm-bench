#!/bin/bash
# The Mac-side build of asr-npu-v1 (docs/asr-npu-v1.md), after mac_prep.sh, inside one Mac
# measurement window:
#   python3 ~/code/standup/tools/quiet/quiet_hold.py asr-npu-build -- gtimeout 1500 bash tools/asr-npu/mac_build.sh
# 1. build_app.sh with the mel jobs (JVM tests incl. MelDumpTest, debug / bench / bench test APKs)
# 2. B's inputs (pick_windows.py -> .build/asr-npu/mel + MANIFEST, the record's b-inputs.json)
# 3. the APKs frozen (run_npu_s26.sh freeze) and the record's LOCK.json (make_lock.py)
# 4. the driver's dry run (setup, the compare runs, the A / C runs: no adb)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
B="$ROOT/.build/asr-npu"
PY="$B/venv/bin/python"
REC="$ROOT/results/raw/2026-10-20-asr-npu-v1-s26-android"
APPDIR="$HOME/code/litert-samples-asr-npu-wt/samples/litert/speech_recognition/AndroidApp"
echo "start $(date +%T)"
MEL_JOBS="$B/mel-jobs.json" bash "$ROOT/tools/asr-npu/build_app.sh"
ls "$B/mel-all" | head -40
"$PY" -I "$ROOT/tools/asr-npu/pick_windows.py" --mel-all "$B/mel-all" --out "$B/mel" --record "$REC/b-inputs.json"
bash "$ROOT/tools/asr-npu/run_npu_s26.sh" freeze
"$PY" -I "$ROOT/tools/asr-npu/make_lock.py" --apk-dir "$B/apk" --models "$B/models/models.lock.json" --mel "$B/mel/MANIFEST" \
  --set "$B/set" --fix-lock "$ROOT/results/raw/2026-10-19-asr-fix-v1-s26-android/LOCK.json" \
  --npu-sums "$HOME/code/litertlm-convert/kev_work/npu/libs/SHA256SUMS" --app-dir "$APPDIR" --out "$REC/LOCK.json" || echo "make_lock exit $? (see unmatched above)"
export DRY=1
bash "$ROOT/tools/asr-npu/run_npu_s26.sh" setup 2>&1 | grep -c 'DRY adb' | sed 's/^/dry setup adb commands: /'
for b in b-tdt-cpu b-tdt-npu b-ctc-cpu b-ctc-npu; do bash "$ROOT/tools/asr-npu/run_npu_s26.sh" compare $b 2>&1 | grep 'am instrument' | cut -c1-400; done
for a in a-ctc-i8 a-ctc-f32; do bash "$ROOT/tools/asr-npu/run_npu_s26.sh" run $a first20 2>&1 | grep 'am instrument' | cut -c1-300; done
for c in c-npu-shared c-npu-separate c-cpu-shared c-cpu-separate; do bash "$ROOT/tools/asr-npu/run_npu_s26.sh" run $c smoke10 2>&1 | grep 'am instrument' | cut -c1-300; done
echo "end $(date +%T)"
