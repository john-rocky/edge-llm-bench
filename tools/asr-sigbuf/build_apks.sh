#!/bin/bash
# Build the asr-sigbuf-v1 APK sets (docs/asr-sigbuf-v1.md) from the litert-samples worktree, inside a
# Mac measurement window (mac_job.sh step 5). Each set = the debug APK (setup route: run-as), the bench
# APK and the bench test APK, copied with sha256 and the commit into .build/asr-sigbuf/apk/<set>/:
#
#   main      branch sigbufcheck-main (upstream main + the check build), LiteRT 2.3.0, .sigbufcheck.main
#   fix       branch sigbufcheck (the TdtDecoder change + the same check build), LiteRT 2.3.0, .sigbufcheck.fix
#   npu-fix   branch sigbufcheck, LiteRT 2.2.0 + the Qualcomm runtime libraries, .sigbufcheck.npu
#   npu-main  branch sigbufcheck-main, the same NPU build, .sigbufcheck.npu (installed over npu-fix to switch)
#
# The JVM tests of the sample (testBenchUnitTest: AGP 9 runs unit tests for the testBuildType only) run
# once on the fix branch. The worktree ends on the change's branch (speech-recognition-tdt-separate-buffers).
#
#   bash tools/asr-sigbuf/build_apks.sh [set...]     # default: all four
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
B="$ROOT/.build/asr-sigbuf"
WT="${WT:-$HOME/code/litert-samples-asr-sigbuf-wt}"
APPDIR="$WT/samples/litert/speech_recognition/AndroidApp"
NPU_SRC="$HOME/code/litertlm-convert/kev_work/npu/libs"
NPU_LIBS="$B/npu-jnilibs"
JLIBROSA_SRC="$HOME/code/litert-samples-asr-npu-wt/samples/litert/speech_recognition/AndroidApp/app/libs/jlibrosa-1.1.8-SNAPSHOT-jar-with-dependencies.jar"
SETS=("$@")
[ ${#SETS[@]} -gt 0 ] || SETS=(main fix npu-fix npu-main)
echo "BUILD start $(date +%T) sets: ${SETS[*]}"

# jLibrosa (the app's download task fetches it from GitHub when missing): the same bytes as the earlier
# benchmark builds of this sample (sha256 dc6ec953...).
mkdir -p "$APPDIR/app/libs"
[ -f "$APPDIR/app/libs/jlibrosa-1.1.8-SNAPSHOT-jar-with-dependencies.jar" ] || cp "$JLIBROSA_SRC" "$APPDIR/app/libs/"
# The Qualcomm runtime libraries (kev_work/npu/libs PROVENANCE.md), without the LiteRT core the AAR carries.
mkdir -p "$NPU_LIBS/arm64-v8a"
for f in libLiteRtCompilerPlugin_Qualcomm.so libLiteRtDispatch_Qualcomm.so libQnnHtp.so libQnnHtpPrepare.so \
  libQnnHtpV81CalculatorStub.so libQnnHtpV81Skel.so libQnnHtpV81Stub.so libQnnIr.so libQnnSaver.so libQnnSystem.so; do
  [ -f "$NPU_LIBS/arm64-v8a/$f" ] || cp "$NPU_SRC/$f" "$NPU_LIBS/arm64-v8a/$f"
done
(cd "$NPU_LIBS/arm64-v8a" && shasum -a 256 *.so > "$NPU_LIBS/SHA256SUMS")
want=$(grep -v -E 'libLiteRt\.so|libLiteRtClGlAccelerator\.so' "$NPU_SRC/SHA256SUMS" | sort)
got=$(sort "$NPU_LIBS/SHA256SUMS")
[ "$want" = "$got" ] || { echo "BUILD FAILED: the staged NPU libraries differ from $NPU_SRC/SHA256SUMS"; exit 1; }

rc=0
for set in "${SETS[@]}"; do
  case "$set" in
    main) branch=sigbufcheck-main; props=(-Psigbufcheck.suffix=.sigbufcheck.main) ;;
    fix) branch=sigbufcheck; props=(-Psigbufcheck.suffix=.sigbufcheck.fix) ;;
    npu-fix) branch=sigbufcheck; props=(-Psigbufcheck.suffix=.sigbufcheck.npu "-Psigbufcheck.npuLibs=$NPU_LIBS") ;;
    npu-main) branch=sigbufcheck-main; props=(-Psigbufcheck.suffix=.sigbufcheck.npu "-Psigbufcheck.npuLibs=$NPU_LIBS") ;;
    *) echo "unknown set $set"; rc=1; continue ;;
  esac
  git -C "$WT" checkout -q "$branch" || { echo "BUILD FAILED: checkout $branch"; rc=1; continue; }
  tasks=(:app:assembleDebug :app:assembleBench :app:assembleBenchAndroidTest)
  [ "$set" = fix ] && tasks+=(:app:testBenchUnitTest)
  echo "BUILD $set: $branch $(git -C "$WT" rev-parse --short HEAD) ${props[*]} $(date +%T)"
  if ! bash "$APPDIR/gradlew" -p "$APPDIR" --console=plain --continue "${props[@]}" "${tasks[@]}" > "$B/logs/gradle-$set.log" 2>&1; then
    echo "BUILD FAILED: $set (log $B/logs/gradle-$set.log)"; grep -E '^e: |error:|FAILURE|What went wrong' -A3 "$B/logs/gradle-$set.log" | head -40
    rc=1; continue
  fi
  out="${APK_OUT:-$B/apk}/$set"
  mkdir -p "$out"
  cp "$APPDIR/app/build/outputs/apk/debug/app-debug.apk" "$out/app-debug.apk"
  cp "$APPDIR/app/build/outputs/apk/bench/app-bench.apk" "$out/app-bench.apk"
  cp "$APPDIR/app/build/outputs/apk/androidTest/bench/app-bench-androidTest.apk" "$out/app-bench-androidTest.apk"
  (cd "$out" && shasum -a 256 app-debug.apk app-bench.apk app-bench-androidTest.apk > SHA256SUMS)
  {
    echo "branch $branch"
    echo "commit $(git -C "$WT" rev-parse HEAD)"
    echo "dirty_tracked_files $(git -C "$WT" status --porcelain -- . | grep -cv '^??')"
    echo "tdt_decoder_blob $(git -C "$WT" rev-parse HEAD:samples/litert/speech_recognition/AndroidApp/app/src/main/java/com/google/ai/edge/examples/asr/TdtDecoder.kt)"
    echo "gradle_props ${props[*]}"
  } > "$out/APP_COMMIT"
  if [ "$set" = fix ]; then
    python3 - "$APPDIR/app/build/test-results/testBenchUnitTest" > "$out/JVM_TESTS" <<'PY'
import pathlib, sys, xml.etree.ElementTree as ET
t = f = e = s = 0
for p in sorted(pathlib.Path(sys.argv[1]).glob("TEST-*.xml")):
    r = ET.parse(p).getroot()
    t += int(r.get("tests")); f += int(r.get("failures")); e += int(r.get("errors")); s += int(r.get("skipped"))
    print(f"  {r.get('name')}: {r.get('tests')} tests, {r.get('failures')} failures, {r.get('errors')} errors")
print(f"JVM tests: {t} run, {f} failures, {e} errors, {s} skipped")
PY
    tail -1 "$out/JVM_TESTS"
  fi
  echo "BUILD $set OK $(date +%T)"; cat "$out/SHA256SUMS"
done
git -C "$WT" checkout -q speech-recognition-tdt-separate-buffers
echo "BUILD end rc=$rc $(date +%T) (worktree on $(git -C "$WT" branch --show-current))"
# The style gate on the change's branch, in the same window (NO_GATE=1 skips it).
[ "${NO_GATE:-0}" = 1 ] || bash "$ROOT/tools/asr-sigbuf/style_gate.sh"
exit $rc
