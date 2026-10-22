#!/bin/bash
# The second Mac window of asr-sigbuf-v1 (docs/asr-sigbuf-v1.md), after mac_job.sh built the main, npu-fix
# and npu-main sets and the fix set stopped at the JVM test task's name:
#   python3 ~/code/standup/tools/quiet/quiet_hold.py asr-sigbuf-mac2 -- gtimeout 1800 bash tools/asr-sigbuf/mac_job2.sh
# 1. build_apks.sh fix (the fix set + the sample's JVM tests), no style gate (it ran in the first window)
# 2. why the style gate's `:app:assembleDebug` fails: the Gradle error on the change's branch and on
#    upstream main (the worktree back on the change's branch afterwards)
# 3. LOCK.json (make_lock.py) and the sitting's dry run
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
B="$ROOT/.build/asr-sigbuf"
PY="$B/venv/bin/python"
REC="${REC:-$ROOT/results/raw/2026-10-22-asr-sigbuf-v1-s26-android}"
WT="$HOME/code/litert-samples-asr-sigbuf-wt"
APPDIR="$WT/samples/litert/speech_recognition/AndroidApp"
echo "MAC JOB2 start $(date +%T)"
NO_GATE=1 bash "$ROOT/tools/asr-sigbuf/build_apks.sh" fix || { echo "MAC JOB2 FAIL build"; exit 1; }
for ref in speech-recognition-tdt-separate-buffers 367816dac824a1984648582060424a817dd5d69d; do
  git -C "$WT" checkout -q "$ref" || { echo "MAC JOB2 FAIL checkout $ref"; exit 1; }
  log="$B/logs/gate-assembleDebug-${ref:0:12}.log"
  bash "$APPDIR/gradlew" -p "$APPDIR" --console=plain :app:assembleDebug > "$log" 2>&1
  echo "assembleDebug on $(git -C "$WT" rev-parse --short HEAD) ($ref): exit $?; $(grep -A3 'What went wrong' "$log" | tr -s '\n' ' ' | cut -c1-400)"
done
git -C "$WT" checkout -q speech-recognition-tdt-separate-buffers
echo "worktree on $(git -C "$WT" branch --show-current) $(git -C "$WT" rev-parse --short HEAD)"
"$PY" -I "$ROOT/tools/asr-sigbuf/make_lock.py" --out "$REC/LOCK.json" || echo "make_lock exit $?"
DRY=1 bash "$ROOT/tools/asr-sigbuf/sitting.sh" dry 2>&1 | tail -40
echo "MAC JOB2 DONE $(date +%T)"
