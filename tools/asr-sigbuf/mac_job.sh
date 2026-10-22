#!/bin/bash
# The Mac side of asr-sigbuf-v1 (docs/asr-sigbuf-v1.md), inside one Mac measurement window:
#   python3 ~/code/standup/tools/quiet/quiet_hold.py asr-sigbuf-mac -- gtimeout 3000 bash tools/asr-sigbuf/mac_job.sh
# 1. the venv (numpy, pyarrow, soundfile, tflite) when missing
# 2. the bytes of every staged file against the Hub (stage_models.sh verify -> models.lock.json)
# 3. the LibriSpeech test-clean parquet unpacked to WAVs (tools/omni-eval/prep_librispeech.py), then
#    S32 / F20 / W and the phone's tar (tools/asr-npu/make_set.py: the S32 chain must be asr-fix-v1's)
# 4. every model file's signatures and I/O (tools/asr-npu/model_io.py -> models-io.json)
# 5. when .build/asr-sigbuf/BUILD_READY exists: build_apks.sh (the four APK sets, frozen), LOCK.json,
#    the driver's dry run; otherwise the window ends after step 4 and the build waits for the next one
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
B="$ROOT/.build/asr-sigbuf"
PY="$B/venv/bin/python"
REC="${REC:-$ROOT/results/raw/2026-10-22-asr-sigbuf-v1-s26-android}"
echo "MAC JOB start $(date +%T)"
if [ ! -x "$PY" ]; then
  python3 -m venv "$B/venv" && "$B/venv/bin/pip" install -q numpy pyarrow soundfile tflite flatbuffers \
    || { echo "MAC JOB FAIL venv"; exit 1; }
fi
"$PY" -c 'import numpy, pyarrow, soundfile, tflite; print("venv:", "numpy", numpy.__version__, "pyarrow", pyarrow.__version__, "soundfile", soundfile.__version__)'
if [ ! -f "$B/models/models.lock.json" ]; then
  bash "$ROOT/tools/asr-sigbuf/stage_models.sh" verify || { echo "MAC JOB FAIL verify"; exit 1; }
fi
SET="$B/sets/librispeech-test-clean"
if [ ! -f "$SET/SET.json" ]; then
  "$PY" -I "$ROOT/tools/omni-eval/prep_librispeech.py" "$B/data/test.clean-00000-of-00001.parquet" "$SET" \
    || { echo "MAC JOB FAIL prep_librispeech"; exit 1; }
fi
echo "full chain: $("$PY" -I -c 'import json, sys; print(json.load(open(sys.argv[1]))["wav_sha256_chain"])' "$SET/SET.json")"
if [ ! -f "$B/set/test-clean-F20W.tar.json" ]; then
  "$PY" -I "$ROOT/tools/asr-npu/make_set.py" "$SET" "$B/set" --record "$REC" || { echo "MAC JOB FAIL make_set"; exit 1; }
fi
if [ ! -f "$B/models/models-io.json" ]; then
  "$PY" -I "$ROOT/tools/asr-npu/model_io.py" "$B"/models/*.tflite --json "$B/models/models-io.json" | grep -v '^  subgraph\|more subgraphs'
fi
echo "MAC JOB prep end $(date +%T)"
if [ -f "$B/BUILD_READY" ]; then
  bash "$ROOT/tools/asr-sigbuf/build_apks.sh" || { echo "MAC JOB FAIL build"; exit 1; }
  "$PY" -I "$ROOT/tools/asr-sigbuf/make_lock.py" --out "$REC/LOCK.json" || echo "make_lock exit $?"
  DRY=1 bash "$ROOT/tools/asr-sigbuf/sitting.sh" dry 2>&1 | tail -40
  echo "MAC JOB DONE (build) $(date +%T)"
else
  echo "MAC JOB DONE (prep only: no BUILD_READY) $(date +%T)"
fi
