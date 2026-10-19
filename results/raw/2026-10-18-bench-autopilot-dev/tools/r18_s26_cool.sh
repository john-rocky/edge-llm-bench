#!/bin/bash
# r18_s26_cool.sh LEG... (LEG = gpu | cpu) - round r18's Galaxy S26 sittings after the 15:18 refusal (the job's preflight read
# the CPU ceiling capped at 2668/4742 MHz right after another lane's sitting; supervisor 16:5x): per leg, a keeper joins the
# END of the shared S26 queue (no front) and takes the hold; then the cool check of r15's chain (sitting2_r15.sh `cool_now`):
# "Thermal Status: 0" and every cpufreq policy's scaling_max_freq at its cpuinfo_max_freq, read every 30 s, 21 reads (10 min).
# Cool = the job with BENCH_SITTING=1 --hold-held-by <keeper>, the hold released when it ends. Not cool = the hold released,
# the keeper joins the end of the queue again (3 attempts per leg). Stops at the first non-zero job exit (the S26's second
# refusal would be the launch's stop condition). Lines to read start with "R18 ". Every adb call reads /dev/null.
#   OUT=<dir> bash r18_s26_cool.sh gpu cpu
set -u
MAIN=$HOME/code/edge-llm-bench
TOOLS=$HOME/code/litertlm-convert/community_accel_work
Q=$TOOLS/queue_cli.py
HC=$TOOLS/hold_cli.py
HOLD=$TOOLS/s2_npu_sweep/.device_hold
SERIAL=RFGL80R6A6H
CAND=$HOME/.cache/edge-llm-bench/litert-candidates/out/Qwen3-0.6B_dynamic_wi4b32_afp32.r0805meta018.litertlm
SHA=e6bf25c0cf7e1a09d19fc6ad716072bb5b8ac96a0eca75075a69f7ce8c1a8f91
OUT=${OUT:?set OUT to a dir for the logs}
CAPS='for p in /sys/devices/system/cpu/cpufreq/policy*; do h=; m=; read h <$p/cpuinfo_max_freq; read m <$p/scaling_max_freq; echo "${p##*/} $m/$h"; done; dumpsys thermalservice | grep -m1 "Thermal Status"'
say() { echo "R18 $(date +%H:%M:%S) $*"; }
mkdir -p "$OUT" || exit 1
[ "$(shasum -a 256 "$CAND" | cut -d' ' -f1)" = "$SHA" ] || { say "FAIL $CAND does not hash $SHA"; exit 1; }
KEEPER=""; NAME=""
cleanup() {
  if [ -n "$KEEPER" ]; then
    python3 "$HC" release "$HOLD" "$KEEPER" < /dev/null > /dev/null 2>&1
    kill "$KEEPER" 2>/dev/null
  fi
  [ -n "$NAME" ] && python3 "$Q" dequeue "$HOLD" "$NAME" < /dev/null > /dev/null 2>&1
  KEEPER=""; NAME=""
}
trap 'cleanup; say "EXIT"' EXIT
cool_now() {   # 0 = thermal status 0 and no policy capped; prints the reading
  local s
  s=$(adb -s "$SERIAL" shell "$CAPS" < /dev/null 2>&1 | tr -d '\r')
  echo "$s" | tr '\n' ' '
  echo "$s" | awk '/^policy/ {split($2, a, "/"); if (a[1] != a[2]) c = 1} END {exit c}' && echo "$s" | grep -q 'Thermal Status: 0'
}
for leg in "$@"; do
  case "$leg" in gpu|cpu) ;; *) say "usage: $0 gpu|cpu ..."; exit 2 ;; esac
  [ -f "$MAIN/matrices/q06-candidate-android-$leg.cells" ] || { say "STOP main lacks matrices/q06-candidate-android-$leg.cells"; exit 1; }
  done_leg=0
  for attempt in 1 2 3; do
    sleep 14400 &
    KEEPER=$!; NAME="r18-q06cand-s26-$leg"
    python3 "$Q" enqueue "$HOLD" "$NAME" edge-llm-bench-55 60 < /dev/null > /dev/null
    say "QUEUED s26 $leg attempt $attempt keeper $KEEPER (end of the queue)"
    if ! python3 "$Q" wait "$HOLD" "$NAME" "$KEEPER" --timeout 14400 < /dev/null > "$OUT/wait-$leg-$attempt.txt" 2>&1; then
      say "STOP the queue wait gave up after 4 h ($leg attempt $attempt)"; exit 3
    fi
    NAME=""   # wait dequeues the entry when it takes the hold
    say "HOLD s26 $leg attempt $attempt keeper $KEEPER"
    ok=1; r=""
    for t in $(seq 1 21); do
      r=$(cool_now) && { ok=0; break; }
      [ "$t" -lt 21 ] && sleep 30
    done
    say "COOLCHECK s26 $leg attempt $attempt cool=$((1 - ok)) after $t read(s): $r"
    if [ "$ok" -ne 0 ]; then
      cleanup
      say "NOT COOL s26 $leg attempt $attempt after 10 min in the hold: hold released, joining the end of the queue again"
      continue
    fi
    log=logs/dashboard-job/2026-10-19-s26-q06cand-$leg.r18-cool-$attempt.byhand.out
    ( cd "$MAIN" && BENCH_SITTING=1 python3 scripts/dashboard_job.py s26 --cells "matrices/q06-candidate-android-$leg.cells" \
        --suffix "q06cand-$leg" --once --hold-held-by "$KEEPER" < /dev/null > "$log" 2>&1 )
    rc=$?
    cleanup
    say "JOB s26 $leg exit $rc (log $MAIN/$log; ledger: $(grep -F -- "-s26-q06cand-$leg-android" "$MAIN/logs/dashboard-job/ledger.tsv" | tail -1 | cut -f3-8 | tr '\t' ' '))"
    [ "$rc" -eq 0 ] || exit "$rc"
    done_leg=1
    break
  done
  [ "$done_leg" -eq 1 ] || { say "STOP s26 $leg not cool in 3 holds"; exit 4; }
done
say "ALL DONE s26 $*"
