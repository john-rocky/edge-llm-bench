#!/bin/bash
# One asr-npu sitting on the Galaxy S26 (docs/asr-npu-v1.md): waits for the keeper's hold, then
# setup -> B (the four compare runs) -> A (the two CTC CPU runs) -> C (the four TDT runs) -> finish,
# and gives the hold back. The decoder-only sitting: STEPS="install2 d cleanup" LIMIT_S=1080 (the new
# test APK, the four DecoderBufferTest runs, then the two packages uninstalled, always last). A step starts only while the sitting's end (the hold + 42 min) is more than
# its need away; a skipped step is logged. Prints one line per step start / end (a Monitor waits on
# them) and the final SITTING DONE / SITTING STOPPED line.
#
#   SIG=<keeper's signal dir> STEPS="setup b a c" tools/asr-npu/sitting.sh > .build/asr-npu/logs/sitting-N.log 2>&1
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
D="$HERE/run_npu_s26.sh"
SIG=${SIG:?}
STEPS=${STEPS:-setup b a c}
LIMIT_S=${LIMIT_S:-2520}   # 42 min of the 45 min hold, the rest for finish and the release
say() { echo "[sitting $(date +%T)] $*"; }
until [ -f "$SIG/HOLD_ACQUIRED" ]; do
  [ -f "$SIG/RELEASE" ] && { say "SITTING STOPPED before the hold (release file)"; exit 4; }
  sleep 5
done
t0=$(cat "$SIG/HOLD_ACQUIRED")
end=$((t0 + LIMIT_S))
say "HOLD at $(date -r "$t0" +%T), the sitting ends by $(date -r "$end" +%T)"
fits() {  # seconds needed -> 0 when the step still fits before the end
  [ $(( $(date +%s) + $1 )) -le "$end" ]
}
step() {  # need_s label command...
  local need=$1 label=$2; shift 2
  if ! fits "$need"; then say "SKIP $label (needs ${need}s, $(( end - $(date +%s) ))s left)"; return 9; fi
  say "STEP $label"
  DEADLINE=$end "$@"
  local rc=$?
  say "END $label rc=$rc"
  return $rc
}
stopped=""
for s in $STEPS; do
  case "$s" in
    setup) step 900 setup bash "$D" setup || { stopped="setup failed"; break; } ;;
    b)
      for arm in b-tdt-cpu b-tdt-npu b-ctc-cpu b-ctc-npu; do step 240 "compare $arm" bash "$D" compare "$arm"; done ;;
    a)
      for arm in a-ctc-i8 a-ctc-f32; do step 420 "run $arm" bash "$D" run "$arm" first20; done ;;
    c)
      for arm in c-npu-shared c-npu-separate c-cpu-shared c-cpu-separate; do step 420 "run $arm" bash "$D" run "$arm" smoke10; done ;;
    install2) step 120 install-test2 bash "$D" install-test2 || { stopped="install-test2 failed"; break; } ;;
    d)
      for arm in d-cpu-shared d-npu-shared d-npu-separate d-npu-shared-noenc; do step 150 "decoder $arm" bash "$D" decoder "$arm"; done ;;
    setupmin) step 300 setup-min bash "$D" setup-min || { stopped="setup-min failed"; break; } ;;
    d2)
      for arm in p-npu-shared p-npu-separate t-npu-shared t-npu-separate; do step 120 "decoder2 $arm" bash "$D" decoder2 "$arm"; done ;;
    cleanup) ;;  # below, after the loop, whatever happened before it
    *) say "unknown step $s" ;;
  esac
done
case " $STEPS " in
  *" cleanup "*) say "STEP cleanup"; bash "$D" cleanup; say "END cleanup rc=$?" ;;
esac
bash "$D" finish
touch "$SIG/RELEASE"
if [ -n "$stopped" ]; then say "SITTING STOPPED ($stopped)"; else say "SITTING DONE"; fi
