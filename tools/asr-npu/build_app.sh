#!/bin/bash
# Build the asr-npu-v1 app (docs/asr-npu-v1.md) from the litert-samples worktree, inside one Mac
# measurement window: the JVM tests (MelDumpTest writes the B inputs when MEL_JOBS names its job
# file), the debug APK (setup route: run-as), the bench APK and the bench test APK (AsrBenchTest,
# NpuCompareTest).
#
#   python3 ~/code/standup/tools/quiet/quiet_hold.py asr-npu-app-build -- gtimeout 900 \
#     env MEL_JOBS=.build/asr-npu/mel-jobs.json bash tools/asr-npu/build_app.sh > .build/asr-npu/logs/build_N.log 2>&1
set -euo pipefail
APPDIR="${APPDIR:-$HOME/code/litert-samples-asr-npu-wt/samples/litert/speech_recognition/AndroidApp}"
echo "start $(date +%T) $(git -C "$APPDIR" rev-parse --short HEAD) dirty=$(git -C "$APPDIR" status --porcelain -- . | grep -vc '^??' || true)"
mel=()
[ -n "${MEL_JOBS:-}" ] && mel=("-Pnpucheck.melDump=$(cd "$(dirname "$MEL_JOBS")" && pwd)/$(basename "$MEL_JOBS")")
bash "$APPDIR/gradlew" -p "$APPDIR" --console=plain --continue ${mel[@]+"${mel[@]}"} \
  :app:testBenchUnitTest :app:assembleDebug :app:assembleBench :app:assembleBenchAndroidTest
python3 - "$APPDIR/app/build/test-results/testBenchUnitTest" <<'PY'
import pathlib, sys, xml.etree.ElementTree as ET
tests = failures = errors = skipped = 0
for p in sorted(pathlib.Path(sys.argv[1]).glob("TEST-*.xml")):
    r = ET.parse(p).getroot()
    tests += int(r.get("tests")); failures += int(r.get("failures")); errors += int(r.get("errors")); skipped += int(r.get("skipped"))
    print(f"  {r.get('name')}: {r.get('tests')} tests, {r.get('failures')} failures, {r.get('errors')} errors, {r.get('skipped')} skipped, {r.get('time')} s")
print(f"JVM tests: {tests} run, {failures} failures, {errors} errors, {skipped} skipped")
PY
echo "end $(date +%T)"
