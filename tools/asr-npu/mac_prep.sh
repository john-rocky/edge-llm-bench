#!/bin/bash
# The Mac-side data of asr-npu-v1 (docs/asr-npu-v1.md), run inside one Mac measurement window:
#   python3 ~/code/standup/tools/quiet/quiet_hold.py asr-npu-prep -- gtimeout 1800 bash tools/asr-npu/mac_prep.sh
# 1. the bytes of every staged file against the Hub (stage_models.sh verify -> models.lock.json)
# 2. the LibriSpeech test-clean parquet unpacked to WAVs (tools/omni-eval/prep_librispeech.py)
# 3. S32 / F20 / F10 / W and the phone's tar (make_set.py; the S32 chain must be asr-fix-v1's)
# 4. every model file's signatures and I/O (model_io.py -> models-io.json)
# 5. then mac_build.sh in the same window (build, B inputs, freeze, LOCK.json, dry run)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
B="$ROOT/.build/asr-npu"
PY="$B/venv/bin/python"
REC="${REC:-$ROOT/results/raw/2026-10-20-asr-npu-v1-s26-android}"
echo "start $(date +%T)"
bash "$ROOT/tools/asr-npu/stage_models.sh" verify
SET="$B/sets/librispeech-test-clean"
if [ ! -f "$SET/SET.json" ]; then
  "$PY" -I "$ROOT/tools/omni-eval/prep_librispeech.py" "$B/data/test.clean-00000-of-00001.parquet" "$SET"
fi
echo "full chain: $("$PY" -I -c 'import json, sys; print(json.load(open(sys.argv[1]))["wav_sha256_chain"])' "$SET/SET.json")"
"$PY" -I "$ROOT/tools/asr-npu/make_set.py" "$SET" "$B/set" --record "$REC"
"$PY" -I "$ROOT/tools/asr-npu/model_io.py" "$B"/models/*.tflite --json "$B/models/models-io.json" | grep -v '^  subgraph\|more subgraphs'
echo "prep end $(date +%T)"
# The build in the same window (one wait instead of two).
bash "$ROOT/tools/asr-npu/mac_build.sh"
