#!/bin/bash
# The Mac-side reading of one asr-npu sitting (docs/asr-npu-v1.md), inside one Mac measurement window:
#   python3 ~/code/standup/tools/quiet/quiet_hold.py asr-npu-post -- gtimeout 900 bash tools/asr-npu/mac_post.sh
# 1. B: compare.py over the pulled outputs -> <REC>/b-compare.json
# 2. A / C: summarize.py -> <REC>/summary/ (score.py, the r2 L1 rows of the same ids for the NPU runs)
# 3. LOCK.json again (make_lock.py)
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
B="$ROOT/.build/asr-npu"
PY="$B/venv/bin/python"
REC="$ROOT/results/raw/2026-10-20-asr-npu-v1-s26-android"
APPDIR="$HOME/code/litert-samples-asr-npu-wt/samples/litert/speech_recognition/AndroidApp"
echo "start $(date +%T)"
"$PY" -I "$ROOT/tools/asr-npu/compare.py" --compare-dir "$B/compare" --mel-dir "$B/mel" --out "$REC/b-compare.json" \
  --tdt-tokenizer "$B/models/tdt-tokenizer.json" --ctc-tokenizer "$B/models/ctc-tokenizer.json"
echo "compare exit $?"
"$PY" -I "$ROOT/tools/asr-npu/summarize.py" --rec "$REC" --set-dir "$B/set" --out "$REC/summary" \
  --l1-ref "$ROOT/results/raw/2026-10-19-asr-litert-app-v1-s26-android/l1-litert-cpu-5s-S4.jsonl"
echo "summarize exit $?"
"$PY" -I "$ROOT/tools/asr-npu/make_lock.py" --apk-dir "$B/apk" --models "$B/models/models.lock.json" --mel "$B/mel/MANIFEST" \
  --set "$B/set" --fix-lock "$ROOT/results/raw/2026-10-19-asr-fix-v1-s26-android/LOCK.json" \
  --npu-sums "$HOME/code/litertlm-convert/kev_work/npu/libs/SHA256SUMS" --app-dir "$APPDIR" --out "$REC/LOCK.json"
echo "make_lock exit $?"
echo "end $(date +%T)"
