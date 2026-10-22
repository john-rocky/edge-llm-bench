#!/bin/bash
# One asr-sigbuf sitting on the Galaxy S26 (docs/asr-sigbuf-v1.md): waits for the keeper's hold, then runs
# the steps in order and gives the hold back. A step (or an A / B pair) starts only while the sitting's
# end (the hold + LIMIT_S) is more than its need away; a skipped one is logged. After every fix run its
# windows are compared with the main run of the same pair (compare.py pair): a token that differs stops
# the sitting (IDENTITY MISMATCH; the cleanup still runs). Prints one line per step start / end and the
# final SITTING DONE / SITTING STOPPED line (a Monitor waits on them).
#
#   SIG=<keeper's signal dir> tools/asr-sigbuf/sitting.sh [steps] > .build/asr-sigbuf/logs/sitting-N.log 2>&1
#   DRY=1 tools/asr-sigbuf/sitting.sh dry      # print every step's adb commands, touch nothing
#
# Steps (hold 1 default "setup v3cpu v3gpu npu cleanupnpu"; hold 2 "jacpu jagpu jar2 cleanup"):
#   setup   run_sigbuf_s26.sh setup
#   v3cpu   v3-cpu-main-r1, v3-cpu-fix-r1, v3-cpu-main-r2, v3-cpu-fix-r2 (A B A B)
#   v3gpu   the same on the GPU
#   npu     dec-cpu-f32-fix, dec-npu-fix, v3-npu-app-fix, swap-npu-main, dec-cpu-f32-main, dec-npu-main, v3-npu-app-main
#   jacpu   ja-cpu-main-r1, ja-cpu-fix-r1;  jagpu  ja-gpu-main-r1, ja-gpu-fix-r1
#   jar2    ja-cpu-main-r2, ja-cpu-fix-r2, ja-gpu-main-r2, ja-gpu-fix-r2 (when the time is left)
#   cleanup run_sigbuf_s26.sh cleanup (all six packages), cleanupnpu run_sigbuf_s26.sh cleanup npu (the .npu
#           pair only, the .main / .fix files stay for the ja runs of hold 2); always last when named
#   update  run_sigbuf_s26.sh update-apks (the .main / .fix bench + test APKs of $APKD over the installed ones)
#   setupnpu run_sigbuf_s26.sh setup npu;  npufix  the npu step's three runs before swap-npu-main
# The second form of the change (035a442e): APKD=.build/asr-sigbuf/apk2 P=f2- and
#   hold 2 "update setupnpu v3cpu1 v3gpu1 npufix jacpu jagpu v3r2 cleanupauto" (a later hold for what is left).
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
D="$HERE/run_sigbuf_s26.sh"
DRY="${DRY:-0}"
say() { echo "[sitting $(date +%T)] $*"; }

if [ "${1:-}" = dry ]; then
  export DRY=1
  bash "$D" setup 2>&1 | grep -c 'DRY adb' | sed 's/^/dry setup adb commands: /'
  for t in v3-cpu-main-r1 v3-gpu-fix-r2 ja-cpu-main-r1 ja-gpu-fix-r1 v3-npu-app-fix v3-npu-app-main; do
    bash "$D" bench "$t" 2>&1 | grep 'am instrument' | cut -c1-420
  done
  for t in dec-cpu-f32-fix dec-npu-fix dec-cpu-f32-main dec-npu-main; do bash "$D" decoder "$t" 2>&1 | grep 'am instrument' | cut -c1-420; done
  bash "$D" swap-npu-main 2>&1 | grep -c 'DRY adb' | sed 's/^/dry swap adb commands: /'
  bash "$D" cleanup 2>&1 | grep -c ' uninstall com' | sed 's/^/dry cleanup uninstalls: /'
  exit 0
fi

SIG=${SIG:?}
STEPS=${1:-${STEPS:-setup v3cpu v3gpu npu cleanupnpu}}
P=${P:-}   # tag prefix of the runs (f2- = the second form of the change, APKD=.build/asr-sigbuf/apk2)
LIMIT_S=${LIMIT_S:-2520}   # 42 min of the 45 min hold, the rest for the cleanup and the release
until [ -f "$SIG/HOLD_ACQUIRED" ]; do
  [ -f "$SIG/RELEASE" ] && { say "SITTING STOPPED before the hold (release file)"; exit 4; }
  sleep 5
done
t0=$(cat "$SIG/HOLD_ACQUIRED")
end=$((t0 + LIMIT_S))
say "HOLD at $(date -r "$t0" +%T), the sitting ends by $(date -r "$end" +%T)"
fits() { [ $(( $(date +%s) + $1 )) -le "$end" ]; }
stopped=""
skipped=""   # a step or pair left out for time: cleanupauto then keeps .main / .fix for a later hold
step() {  # need_s label command...
  local need=$1 label=$2; shift 2
  [ -n "$stopped" ] && return 9
  if ! fits "$need"; then say "SKIP $label (needs ${need}s, $(( end - $(date +%s) ))s left)"; skipped=1; return 9; fi
  say "STEP $label"
  DEADLINE=$end "$@"
  local rc=$?
  say "END $label rc=$rc"
  return $rc
}
pair() {  # need_per_run main_tag fix_tag: both or neither, then the identity check of the fix run
  local need=$1 a=$2 b=$3 line
  [ -n "$stopped" ] && return 9
  if ! fits $((2 * need)); then
    say "SKIP pair $a / $b (needs $((2 * need))s, $(( end - $(date +%s) ))s left)"; skipped=1
    case "$a" in *ja-*) ja_skipped=1 ;; esac
    return 9
  fi
  step "$need" "bench $a" bash "$D" bench "$a"
  step "$need" "bench $b" bash "$D" bench "$b" || return 0
  line=$(bash "$D" identity "$b" 2>&1)
  say "IDENTITY $line"
  case "$line" in
    *MISMATCH*) stopped="identity mismatch in $b"; say "IDENTITY MISMATCH ($b): the sitting stops" ;;
    INCOMPLETE*) skipped=1; case "$a" in *ja-*) ja_skipped=1 ;; esac ;;
  esac
}
for s in $STEPS; do
  case "$s" in
    setup) step 720 setup bash "$D" setup || { stopped="setup failed"; } ;;
    v3cpu)
      pair 180 "${P}v3-cpu-main-r1" "${P}v3-cpu-fix-r1"
      pair 180 "${P}v3-cpu-main-r2" "${P}v3-cpu-fix-r2" ;;
    v3gpu)
      pair 180 "${P}v3-gpu-main-r1" "${P}v3-gpu-fix-r1"
      pair 180 "${P}v3-gpu-main-r2" "${P}v3-gpu-fix-r2" ;;
    v3cpu1) pair 180 "${P}v3-cpu-main-r1" "${P}v3-cpu-fix-r1" ;;
    v3gpu1) pair 180 "${P}v3-gpu-main-r1" "${P}v3-gpu-fix-r1" ;;
    v3r2)
      pair 180 "${P}v3-cpu-main-r2" "${P}v3-cpu-fix-r2"
      pair 180 "${P}v3-gpu-main-r2" "${P}v3-gpu-fix-r2" ;;
    update) step 240 update-apks bash "$D" update-apks || { stopped="update-apks failed"; } ;;
    setupnpu) step 480 "setup npu" bash "$D" setup npu || { stopped="setup npu failed"; } ;;
    setupja) step 360 "setup ja" bash "$D" setup ja || { stopped="setup ja failed"; } ;;
    mainact)
      # MainActivity's own decoder (run_mainact_s26.sh, the apk3 sets): its setup, then the NPU and the CPU / GPU.
      if step 300 "mainact setup" bash "$HERE/run_mainact_s26.sh" setup; then
        step 240 "mainact npu" bash "$HERE/run_mainact_s26.sh" run npu
        step 180 "mainact fix" bash "$HERE/run_mainact_s26.sh" run fix
      else
        stopped="mainact setup failed"
      fi ;;
    npu | npufix)
      step 150 "decoder ${P}dec-cpu-f32-fix" bash "$D" decoder "${P}dec-cpu-f32-fix"
      step 120 "decoder ${P}dec-npu-fix" bash "$D" decoder "${P}dec-npu-fix"
      step 180 "bench ${P}v3-npu-app-fix" bash "$D" bench "${P}v3-npu-app-fix"
      if [ "$s" = npu ] && step 90 swap-npu-main bash "$D" swap-npu-main; then
        step 150 "decoder ${P}dec-cpu-f32-main" bash "$D" decoder "${P}dec-cpu-f32-main"
        step 120 "decoder ${P}dec-npu-main" bash "$D" decoder "${P}dec-npu-main"
        step 180 "bench ${P}v3-npu-app-main" bash "$D" bench "${P}v3-npu-app-main"
      fi ;;
    jacpu) pair 330 "${P}ja-cpu-main-r1" "${P}ja-cpu-fix-r1" ;;
    jagpu) pair 330 "${P}ja-gpu-main-r1" "${P}ja-gpu-fix-r1" ;;
    jar2)
      pair 180 "${P}ja-cpu-main-r2" "${P}ja-cpu-fix-r2"
      pair 180 "${P}ja-gpu-main-r2" "${P}ja-gpu-fix-r2" ;;
    cleanup | cleanupnpu | cleanupauto) ;;  # below, after the loop, whatever happened before it
    *) say "unknown step $s" ;;
  esac
done
case " $STEPS " in
  *" cleanup "*) say "STEP cleanup"; bash "$D" cleanup; say "END cleanup rc=$?" ;;
  *" cleanupnpu "*) say "STEP cleanup npu"; bash "$D" cleanup npu; say "END cleanup npu rc=$?" ;;
  *" cleanupauto "*)
    # Everything when the ja pairs ran (the v3 r2 pairs are optional); else only the .npu pair, so the
    # .main / .fix files stay for the ja runs of a later hold.
    if [ -n "${ja_skipped:-}" ] && [ -z "$stopped" ]; then
      say "STEP cleanup npu (ja runs left)"; bash "$D" cleanup npu; say "END cleanup npu rc=$?"
    else
      say "STEP cleanup"; bash "$D" cleanup; say "END cleanup rc=$?"
    fi ;;
esac
bash "$D" finish
touch "$SIG/RELEASE"
if [ -n "$stopped" ]; then say "SITTING STOPPED ($stopped)"; else say "SITTING DONE"; fi
