#!/bin/bash
# The Mac-side summary of asr-sigbuf-v1 (docs/asr-sigbuf-v1.md) after the three holds, inside one Mac window
# (Python reads every APK for LOCK.json):
#   python3 ~/code/standup/tools/quiet/quiet_hold.py asr-sigbuf-post -- gtimeout 900 bash tools/asr-sigbuf/mac_post.sh
# compare.py summary for both forms (compare-f1.json / compare-f2.json in the record; the verdicts with the
# cost ratio in .build/asr-sigbuf/verdicts-f1.json / -f2.json), then LOCK.json (make_lock.py, the three APK dirs).
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
B="$ROOT/.build/asr-sigbuf"
PY="$B/venv/bin/python"
REC="$ROOT/results/raw/2026-10-22-asr-sigbuf-v1-s26-android"
echo "MAC POST start $(date +%T)"
for p in f1- f2-; do
  echo "== compare $p"
  "$PY" -I "$ROOT/tools/asr-sigbuf/compare.py" summary "$REC" "$p" || echo "compare $p exit $?"
done
"$PY" -I "$ROOT/tools/asr-sigbuf/make_lock.py" --out "$REC/LOCK.json" || echo "make_lock exit $?"
echo "MAC POST DONE $(date +%T)"
