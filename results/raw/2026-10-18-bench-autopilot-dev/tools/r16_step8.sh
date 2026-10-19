#!/bin/bash
# Round 16, step 8: the iPhone 18 Pro leg in one go, after the supervisor's go (the cells file merged into main).
#   1. a keeper (a sleep, 45 min at most) queues for the phone and takes its hold (queue_cli.py enqueue + wait);
#   2. push_mlx_4bit_18pro.sh --keeper <pid> copies the two 4bit bundles over USB and checks every file's size;
#   3. the hold is released;
#   4. when no other keeper waits in the line, the job route starts from the main checkout (nohup) and takes the
#      hold itself: scripts/dashboard_job.py iphone18pro --cells matrices/mlx-gemma4-file-ios.cells --suffix mlx-ptq --once
# Lines that start with "R16 " are the ones to read: start, hold, the push's result, the job started or not.
# Exit: 0 = the job started; 1 = the push failed or main lacks the cells file (no job); 3 = the phone stayed busy
# past WAIT_S (dequeued, no job); 4 = another keeper waits in the line after the release (no job; queue again).
#   OUT=<dir for the push logs> bash r16_step8.sh
set -u
MAIN=$HOME/code/edge-llm-bench
TOOLS=$HOME/code/litertlm-convert/community_accel_work
HOLD=$HOME/code/coreai/ondevice/.device_hold
NAME=r16-push-mlx-4bit
CELLS=matrices/mlx-gemma4-file-ios.cells
HERE=$(cd "$(dirname "$0")" && pwd)
OUT=${OUT:?set OUT to a dir for the push logs}
WAIT_S=${WAIT_S:-1800}            # the launch's stop condition: the phone busy for 30 min or more
LOG=logs/dashboard-job/$(date +%F)-iphone18pro-mlx-ptq.byhand.out
say() { echo "R16 $(date +%H:%M:%S) $*"; }

[ -f "$MAIN/$CELLS" ] || { say "STOP $MAIN/$CELLS is not there (not merged yet): nothing done"; exit 1; }
cmp -s "$MAIN/$CELLS" "$HERE/../../../../$CELLS" \
  || say "NOTE main's $CELLS differs from this branch's copy (the job runs main's)"

sleep 2700 &
KEEPER=$!
trap 'kill $KEEPER 2>/dev/null' EXIT
say "keeper pid $KEEPER (a 45-minute sleep)"
python3 "$TOOLS/queue_cli.py" enqueue "$HOLD" "$NAME" edge-llm-bench-55 45 | sed 's/^/    /'
if ! python3 "$TOOLS/queue_cli.py" wait "$HOLD" "$NAME" "$KEEPER" --timeout "$WAIT_S"; then
  python3 "$TOOLS/queue_cli.py" dequeue "$HOLD" "$NAME" > /dev/null
  say "STOP the phone stayed busy for $WAIT_S s (queue_cli wait timed out); dequeued, no job"
  exit 3
fi
say "hold taken by keeper $KEEPER"
OUT="$OUT" bash "$HERE/push_mlx_4bit_18pro.sh" --keeper "$KEEPER"
rc=$?
python3 "$TOOLS/hold_cli.py" release "$HOLD" "$KEEPER"
say "hold released (push exit $rc)"
kill "$KEEPER" 2>/dev/null
if [ $rc -ne 0 ]; then
  say "STOP the push failed (exit $rc): no job"
  exit 1
fi
python3 "$TOOLS/queue_cli.py" list "$HOLD" > "$OUT/queue-after-release.txt" 2>&1
if grep -q "(keeper waiting)" "$OUT/queue-after-release.txt"; then
  say "WAIT another keeper waits in the line, so the job did not start (queue again): $(tr '\n' ' ' < "$OUT/queue-after-release.txt")"
  exit 4
fi
cd "$MAIN" || exit 1
# its own session, so the job outlives this driver and whatever ends the driver's process group
python3 -I -c 'import os, sys; os.setsid(); os.execvp(sys.argv[1], sys.argv[1:])' \
  nohup python3 scripts/dashboard_job.py iphone18pro --cells "$CELLS" --suffix mlx-ptq --once \
  < /dev/null > "$LOG" 2>&1 &
say "job started: pid $! (cwd $MAIN, log $LOG)"
exit 0
