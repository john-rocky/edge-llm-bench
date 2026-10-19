#!/bin/bash
# Round 16, step 8: the iPhone 18 Pro leg, after the supervisor's go. Two parts, because the job route reads the
# main checkout's cells file and the push does not:
#   push  a keeper (a sleep, 45 min at most) queues for the phone and takes its hold (queue_cli.py enqueue + wait);
#         push_mlx_4bit_18pro.sh --keeper <pid> copies the two 4bit bundles over USB and checks every file's size;
#         the hold is released.
#   job   once matrices/mlx-gemma4-file-ios.cells is in main and no other keeper waits in the phone's line, the job
#         route starts from the main checkout in its own session (nohup) and takes the hold itself:
#         scripts/dashboard_job.py iphone18pro --cells matrices/mlx-gemma4-file-ios.cells --suffix mlx-ptq --once
# Lines that start with "R16 " are the ones to read.
# Exit: 0 = done (push: both bundles on the phone; job: started); 1 = the push failed, or main lacks the cells
# file (no job); 3 = the phone stayed busy past WAIT_S (dequeued); 4 = another keeper waits in the line (no job).
#   OUT=<dir for the push logs> bash r16_step8.sh push
#   OUT=<dir> [SUFFIX=mlx-ptq-r3] bash r16_step8.sh job   # a retake takes a new suffix: the same campaign name
#                                                       # re-pulls a stopped sitting's records
set -u
MAIN=$HOME/code/edge-llm-bench
TOOLS=$HOME/code/litertlm-convert/community_accel_work
HOLD=$HOME/code/coreai/ondevice/.device_hold
NAME=r16-push-mlx-4bit
CELLS=matrices/mlx-gemma4-file-ios.cells
HERE=$(cd "$(dirname "$0")" && pwd)
OUT=${OUT:?set OUT to a dir for the push logs}
WAIT_S=${WAIT_S:-1800}            # the launch's stop condition: the phone busy for 30 min or more
say() { echo "R16 $(date +%H:%M:%S) $*"; }
mkdir -p "$OUT" || exit 1

push() {
  sleep 2700 &
  KEEPER=$!
  trap 'kill $KEEPER 2>/dev/null' EXIT
  say "keeper pid $KEEPER (a 45-minute sleep)"
  python3 "$TOOLS/queue_cli.py" enqueue "$HOLD" "$NAME" edge-llm-bench-55 45 | sed 's/^/    /'
  if ! python3 "$TOOLS/queue_cli.py" wait "$HOLD" "$NAME" "$KEEPER" --timeout "$WAIT_S"; then
    python3 "$TOOLS/queue_cli.py" dequeue "$HOLD" "$NAME" > /dev/null
    say "STOP the phone stayed busy for $WAIT_S s (queue_cli wait timed out); dequeued"
    exit 3
  fi
  say "hold taken by keeper $KEEPER"
  # the bundles may already be there (an earlier push; an app installed over itself keeps its container)
  OUT="$OUT" CHECK_ONLY=1 bash "$HERE/push_mlx_4bit_18pro.sh" --keeper "$KEEPER"
  rc=$?
  if [ $rc -ne 0 ]; then
    say "the check found a bundle missing or different: copying"
    OUT="$OUT" bash "$HERE/push_mlx_4bit_18pro.sh" --keeper "$KEEPER"
    rc=$?
  fi
  python3 "$TOOLS/hold_cli.py" release "$HOLD" "$KEEPER"
  say "hold released (push exit $rc)"
  kill "$KEEPER" 2>/dev/null
  if [ $rc -ne 0 ]; then
    say "STOP the push failed (exit $rc)"
    exit 1
  fi
  say "DONE push: both bundles on the phone"
  exit 0
}

job() {
  [ -f "$MAIN/$CELLS" ] || { say "STOP $MAIN/$CELLS is not there (not merged yet): no job"; exit 1; }
  cmp -s "$MAIN/$CELLS" "$HERE/../../../../$CELLS" \
    || say "NOTE main's $CELLS differs from this tree's copy (the job runs main's)"
  python3 "$TOOLS/queue_cli.py" list "$HOLD" > "$OUT/queue-before-job.txt" 2>&1
  if grep -q "(keeper waiting)" "$OUT/queue-before-job.txt"; then
    say "WAIT another keeper waits in the line, so the job did not start: $(tr '\n' ' ' < "$OUT/queue-before-job.txt")"
    exit 4
  fi
  LOG=logs/dashboard-job/$(date +%F)-iphone18pro-mlx-ptq.byhand.out
  cd "$MAIN" || exit 1
  # its own session, so the job outlives this driver and whatever ends the driver's process group
  python3 -I -c 'import os, sys; os.setsid(); os.execvp(sys.argv[1], sys.argv[1:])' \
    nohup python3 scripts/dashboard_job.py iphone18pro --cells "$CELLS" --suffix "${SUFFIX:-mlx-ptq}" --once \
    < /dev/null >> "$LOG" 2>&1 &
  say "job started: pid $! (cwd $MAIN, log $LOG)"
  exit 0
}

case "${1:-}" in
  push) push ;;
  job) job ;;
  *) sed -n 2,16p "$0" >&2; exit 2 ;;
esac
