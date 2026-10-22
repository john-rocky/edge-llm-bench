#!/bin/bash
# The fourth Mac window of asr-sigbuf-v1 (docs/asr-sigbuf-v1.md): the check build with SigbufMainActivityTest
# (MainActivity loads the entry itself; the decoder it built) on top of the second form of the change,
# the fix and npu-fix sets into .build/asr-sigbuf/apk3/ (hold 3).
#   python3 ~/code/standup/tools/quiet/quiet_hold.py asr-sigbuf-mac4 -- gtimeout 1800 bash tools/asr-sigbuf/mac_job4.sh
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
B="$ROOT/.build/asr-sigbuf"
echo "MAC JOB4 start $(date +%T)"
APK_OUT="$B/apk3" NO_GATE=1 bash "$ROOT/tools/asr-sigbuf/build_apks.sh" fix npu-fix || { echo "MAC JOB4 FAIL build"; exit 1; }
echo "MAC JOB4 DONE $(date +%T)"
