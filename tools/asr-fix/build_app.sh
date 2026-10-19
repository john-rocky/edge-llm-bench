#!/bin/bash
# Build the asr-fix-v1 app (docs/asr-fix-v1.md) from the litert-samples worktree: the JVM tests
# (TdtGreedyLoopTest with the rest), the debug APK (setup route: run-as), the bench APK (measured:
# not debuggable) and the bench test APK. Run it inside a Mac quiet window:
#
#   python3 ~/code/standup/tools/quiet/quiet_wait.py -- python3 ~/code/standup/tools/quiet/quiet_hold.py \
#     asr-fix-app-build -- gtimeout 900 bash tools/asr-fix/build_app.sh > .build/asr-fix/build_N.log 2>&1
set -euo pipefail
APPDIR="${APPDIR:-$HOME/code/litert-samples-asr-fix-wt/samples/litert/speech_recognition/AndroidApp}"
echo "start $(date +%T) $(git -C "$APPDIR" rev-parse --short HEAD) dirty=$(git -C "$APPDIR" status --porcelain -- . | grep -vc '^??' || true)"
bash "$APPDIR/gradlew" -p "$APPDIR" --console=plain \
  :app:testBenchUnitTest :app:assembleDebug :app:assembleBench :app:assembleBenchAndroidTest
python3 - "$APPDIR/app/build/test-results/testBenchUnitTest" <<'PY'
import pathlib, sys, xml.etree.ElementTree as ET
tests = failures = errors = skipped = 0
for p in sorted(pathlib.Path(sys.argv[1]).glob("TEST-*.xml")):
    r = ET.parse(p).getroot()
    tests += int(r.get("tests")); failures += int(r.get("failures")); errors += int(r.get("errors")); skipped += int(r.get("skipped"))
    print(f"  {r.get('name')}: {r.get('tests')} tests, {r.get('failures')} failures, {r.get('errors')} errors, {r.get('time')} s")
print(f"JVM tests: {tests} run, {failures} failures, {errors} errors, {skipped} skipped")
PY
echo "end $(date +%T)"
