#!/bin/bash
# Galaxy S26 driver of asr-sigbuf-v1's MainActivity check (docs/asr-sigbuf-v1.md): SigbufMainActivityTest
# from the apk3 sets (the check build with that test, on top of the second form of the change, 035a442e).
# MainActivity loads parakeet-tdt-0.6b-v3 itself; .sigbufcheck.fix on the CPU and the GPU, .sigbufcheck.npu
# on the NPU; one WAV through the activity's own objects per backend. A file of its own so the sitting of
# run_sigbuf_s26.sh is never edited while it runs; the cleanup and the stay-awake setting go through
# run_sigbuf_s26.sh cleanup / this script's finish.
#
#   run_mainact_s26.sh setup          # the debug APKs of fix / npu-fix (apk3) over whatever is installed; the files
#                                     # MainActivity reads (sha256 on the phone, pushed only when missing or wrong);
#                                     # the bench + test APKs (apk3) over them
#   run_mainact_s26.sh run fix|npu    # SigbufMainActivityTest: probe, am instrument, poll, probe, pull
#   run_mainact_s26.sh finish         # the stay-awake setting back (mainact-setup.log)
#   DRY=1 run_mainact_s26.sh ...
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
DRY="${DRY:-0}"
SERIAL="${SERIAL:-RFGL80R6A6H}"
BASE=com.google.ai.edge.examples.asr.sigbufcheck
B="${B:-$ROOT/.build/asr-sigbuf}"
MAPKD="${MAPKD:-$B/apk3}"   # its own name: the sitting exports APKD for run_sigbuf_s26.sh
REC="${REC:-$ROOT/results/raw/2026-10-22-asr-sigbuf-v1-s26-android}"
[ "$DRY" = 1 ] && REC="$B/dry-rec"
HOLD="$HOME/code/litertlm-convert/community_accel_work/s2_npu_sweep/.device_hold"
DT=/data/local/tmp/edge-llm-bench/asr-sigbuf
L="$REC/mainact-setup.log"
mkdir -p "$B" "$REC"

log() { echo "[asr-sigbuf-mainact $(date +%H:%M:%S)] $*" >&2; }
A() {
  if [ "$DRY" = 1 ]; then echo "DRY adb -s $SERIAL $*" >&2; return 0; fi
  adb -s "$SERIAL" "$@" </dev/null
}
need_hold() {
  [ "$DRY" = 1 ] && return 0
  python3 - "$HOLD" <<'PY' || { log "the S26 hold is not ours: $(cat "$HOLD" 2>/dev/null)"; exit 4; }
import json, os, sys
d = json.load(open(sys.argv[1]))
os.kill(int(d["pid"]), 0)
sys.exit(0 if d.get("script") == "asr_sigbuf_s26" else 1)
PY
}
sha_of() {
  python3 -c 'import json,sys; print({r["local"].split("/")[-1]: r["sha256"] for r in json.load(open(sys.argv[1]))}[sys.argv[2]])' \
    "$B/models/models.lock.json" "$1"
}
dexopt_of() {
  [ "$DRY" = 1 ] && { echo dry; return 0; }
  A shell "dumpsys package $1" | python3 -c '
import re, sys
m = re.search(r"\[status=([^\]]+)\]\s*\[reason=([^\]]+)\]", sys.stdin.read())
print((m.group(1) + "/" + m.group(2)) if m else "unknown")'
}

# set package local-file files-path
FILES="fix $BASE.fix parakeet_tdt_0.6b_v3_5s_i8_stateful.tflite parakeet-tdt-0.6b-v3/model.tflite
fix $BASE.fix tdt-tokenizer.json parakeet-tdt-0.6b-v3/tokenizer.json
npu-fix $BASE.npu parakeet_tdt_0.6b_v3_5s_f32_stateful_Qualcomm_SM8850.tflite parakeet-tdt-0.6b-v3/model_npu.tflite
npu-fix $BASE.npu tdt-tokenizer.json parakeet-tdt-0.6b-v3/tokenizer.json"

cmd_setup() {
  need_hold
  local set p f dst want got n
  : > "$L"
  {
    echo "# mainact setup $(date '+%F %T %Z') (APK sets from $MAPKD)"
    for set in fix npu-fix; do echo "## $set"; cat "$MAPKD/$set/SHA256SUMS" "$MAPKD/$set/APP_COMMIT"; done
    echo "stay_on_while_plugged_in before: $(A shell settings get global stay_on_while_plugged_in | tr -d '\r')"
    echo "/data before: $(A shell df -k /data | tail -1 | tr -s ' ')"
    echo "packages before: $(A shell "pm list packages | grep -E '$BASE'" | tr -d '\r' | tr '\n' ' ')"
  } >> "$L"
  for set in fix npu-fix; do
    A install -r -t "$MAPKD/$set/app-debug.apk" >&2 || { log "install $set debug app failed"; exit 2; }
  done
  A shell svc power stayon usb
  A shell input keyevent KEYCODE_WAKEUP
  A shell mkdir -p "$DT"
  echo "$FILES" | while read -r set p f dst; do
    want=$(sha_of "$f")
    got=$(A shell run-as "$p" sha256sum "files/$dst" 2>/dev/null | cut -c1-64)
    if [ "$DRY" != 1 ] && [ "$got" = "$want" ]; then echo "file $f -> $p files/$dst already there sha256_phone=$got OK" | tee -a "$L" >&2; continue; fi
    A push "$B/models/$f" "$DT/$f" >&2 || { log "push $f failed"; exit 2; }
    A shell "run-as $p sh -c 'mkdir -p files/${dst%/*} && cat > files/$dst' < $DT/$f"
    got=$(A shell run-as "$p" sha256sum "files/$dst" | cut -c1-64)
    A shell rm -f "$DT/$f"
    echo "file $f -> $p files/$dst sha256_local=$want sha256_phone=$got $([ "$got" = "$want" ] && echo OK || echo MISMATCH)" | tee -a "$L" >&2
    [ "$DRY" = 1 ] || [ "$got" = "$want" ] || exit 3
  done || exit $?
  want=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["tar_sha256"])' "$B/set/test-clean-F20W.tar.json")
  A push "$B/set/test-clean-F20W.tar" "$DT/test-clean-F20W.tar" >&2
  got=$(A shell sha256sum "$DT/test-clean-F20W.tar" | cut -c1-64)
  for p in $BASE.fix $BASE.npu; do
    A shell "run-as $p sh -c 'mkdir -p files/sets/test-clean && cd files/sets/test-clean && tar -xf -' < $DT/test-clean-F20W.tar"
    n=$(A shell "run-as $p ls files/sets/test-clean | grep -c '\.wav\$'" | tr -d '\r')
    echo "wav set -> $p tar sha256_local=$want sha256_phone=$got wavs=$n" | tee -a "$L" >&2
    if [ "$DRY" != 1 ] && { [ "$got" != "$want" ] || [ "$n" != 21 ]; }; then log "WAV set check failed ($p)"; exit 3; fi
  done
  A shell rm -rf "$DT"
  for set in fix npu-fix; do
    A install -r "$MAPKD/$set/app-bench.apk" >&2 || { log "install $set bench app failed"; exit 2; }
    A install -r -t "$MAPKD/$set/app-bench-androidTest.apk" >&2 || { log "install $set bench test failed"; exit 2; }
  done
  {
    echo "installed the apk3 bench + bench test APKs of fix and npu-fix (install -r: data kept)"
    for p in $BASE.fix $BASE.npu; do echo "$p dexopt app: $(dexopt_of "$p"), test: $(dexopt_of "$p.test")"; done
    echo "/data after: $(A shell df -k /data | tail -1 | tr -s ' ')"
  } | tee -a "$L" >&2
}

cmd_run() {
  local which=$1 pkg accels tag am ext t0 st pid n="" done_flag now
  case "$which" in
    fix) pkg=$BASE.fix; accels=cpu,gpu ;;
    npu) pkg=$BASE.npu; accels=npu ;;
    *) log "run fix|npu"; exit 2 ;;
  esac
  need_hold
  tag="f2-mainact-$which"
  ext="/sdcard/Android/data/$pkg/files/sigbuf"
  "$HERE/probe.sh" before > "$REC/$tag.probe-before.json"
  echo "# $tag $(date '+%F %T %Z')" >> "$REC/$tag.cmd"
  A shell "rm -f $ext/$tag.*"
  A logcat -c
  am="am instrument -r -e class com.google.ai.edge.examples.asr.SigbufMainActivityTest -e model parakeet-tdt-0.6b-v3 -e accelerators $accels -e manifest /data/user/0/$pkg/files/sets/test-clean/manifest-device.tsv -e every 32 -e rows 1 -e max_tokens 630 -e tag $tag $pkg.test/androidx.test.runner.AndroidJUnitRunner"
  echo "$(date '+%T') adb -s $SERIAL shell $am" >> "$REC/$tag.cmd"
  log "run $tag ($pkg, $accels)"
  A shell "$am" > "$B/$tag.instrument.txt"
  [ "$DRY" = 1 ] && return 0
  t0=$(date +%s)
  while :; do
    sleep 3
    st=$(A shell "[ -f $ext/$tag.done ] && echo done=1; echo pid=\$(pidof $pkg)" | tr -d '\r')
    done_flag=$(echo "$st" | sed -n 's/^done=//p'); pid=$(echo "$st" | sed -n 's/^pid=//p')
    [ -n "$pid" ] && n=$pid
    [ "$done_flag" = 1 ] && break
    now=$(date +%s)
    if [ -z "$pid" ] && [ $((now - t0)) -gt 25 ]; then log "$tag: the process is gone without a done marker"; break; fi
    if [ $((now - t0)) -gt 420 ]; then log "$tag: no done marker after 420 s, stopped"; A shell am force-stop "$pkg"; break; fi
  done
  sleep 1
  for f in json log.txt done; do A pull "$ext/$tag.$f" "$REC/$tag.$f" >/dev/null 2>&1; done
  A logcat -d -v threadtime > "$B/logcat-raw-$tag.txt" 2>/dev/null
  awk -v p="${n:-x}" '$3 == p' "$B/logcat-raw-$tag.txt" | grep -E "litert|LiteRt|tflite|Sigbuf|TestRunner|AndroidRuntime|DEBUG|Accelerator|Dispatch" | grep -v -E "QnnGraph_execute|QnnMem_" > "$REC/$tag.logcat.log" 2>/dev/null
  A logcat -b crash -d > "$REC/$tag.crash.log" 2>/dev/null
  [ -s "$REC/$tag.crash.log" ] || rm -f "$REC/$tag.crash.log"
  "$HERE/probe.sh" after > "$REC/$tag.probe-after.json"
  log "$tag: $(cat "$REC/$tag.done" 2>/dev/null || echo 'no done marker'); $(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print([(a["accelerator"], a["loaded"], a.get("separate_buffers"), [r.get("error") for r in a.get("rows", [])]) for a in d["accelerators"]], d["log"])' "$REC/$tag.json" 2>/dev/null)"
}

cmd_finish() {
  local before
  before=$(sed -n 's/^stay_on_while_plugged_in before: //p' "$L" 2>/dev/null | head -1)
  [ -n "$before" ] && A shell settings put global stay_on_while_plugged_in "$before"
  log "stay_on_while_plugged_in restored to ${before:-?}"
}

case "${1:-}" in
  setup) cmd_setup ;;
  run) shift; cmd_run "${1:-}" ;;
  finish) cmd_finish ;;
  *) sed -n 2,14p "$0"; exit 2 ;;
esac
