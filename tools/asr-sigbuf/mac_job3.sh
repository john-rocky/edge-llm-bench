#!/bin/bash
# The third Mac window of asr-sigbuf-v1 (docs/asr-sigbuf-v1.md): the second form of the change (035a442e,
# the copies on the NPU only, after the first form's GPU decode time went past the cost line) and the
# check build on top of it, built into .build/asr-sigbuf/apk2/ (the first form's APKs stay in apk/), and
# the style gate on the change's branch.
#   python3 ~/code/standup/tools/quiet/quiet_hold.py asr-sigbuf-mac3 -- gtimeout 1800 bash tools/asr-sigbuf/mac_job3.sh
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
B="$ROOT/.build/asr-sigbuf"
echo "MAC JOB3 start $(date +%T)"
APK_OUT="$B/apk2" NO_GATE=1 bash "$ROOT/tools/asr-sigbuf/build_apks.sh" main fix npu-fix || { echo "MAC JOB3 FAIL build"; exit 1; }
bash "$ROOT/tools/asr-sigbuf/style_gate.sh"
echo "MAC JOB3 DONE $(date +%T)"
