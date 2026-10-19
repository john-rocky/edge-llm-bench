#!/bin/bash
# Galaxy S26 hold keeper for one asr-burst sitting (asr-litert-app-v1's keeper with this lane's name):
# queue first (queue_cli enqueue + wait with this script's pid as the owner), hold the phone until
# $SIG/RELEASE appears, the watched session process exits or the safety limit passes, then release.
# Prints one line when the hold is taken and one when it is given back (a Monitor can wait on them).
# Never forces a hold.
#
#   WATCH_PID=<session pid> SIG=<dir> tools/asr-burst/hold_keeper.sh
#   touch <SIG>/RELEASE                  # give the phone back
set -u
CAW="$HOME/code/litertlm-convert/community_accel_work"
LOCK="$CAW/s2_npu_sweep/.device_hold"
NAME=asr_burst_s26
SIG=${SIG:?}
WATCH_PID=${WATCH_PID:?}
HOLD_LIMIT=${HOLD_LIMIT:-4500}    # 75 min: a safety net over the 45 min plan (the driver stops its runs first)
WAIT_LIMIT=${WAIT_LIMIT:-21600}
mkdir -p "$SIG"
rm -f "$SIG/RELEASE" "$SIG/HOLD_ACQUIRED"
echo "keeper pid $$ queued $(date '+%F %T') (watch $WATCH_PID)"
python3 "$CAW/queue_cli.py" enqueue "$LOCK" "$NAME" edge-llm-bench-c0 45 >/dev/null
python3 "$CAW/queue_cli.py" wait "$LOCK" "$NAME" $$ --timeout "$WAIT_LIMIT" &
waiter=$!
while kill -0 $waiter 2>/dev/null; do
  if ! kill -0 "$WATCH_PID" 2>/dev/null || [ -f "$SIG/RELEASE" ]; then
    kill $waiter 2>/dev/null; wait $waiter 2>/dev/null
    python3 "$CAW/queue_cli.py" dequeue "$LOCK" "$NAME" >/dev/null
    python3 "$CAW/hold_cli.py" release "$LOCK" $$ >/dev/null 2>&1
    echo "KEEPER STOPPED while waiting $(date '+%F %T')"
    exit 4
  fi
  sleep 5
done
wait $waiter
rc=$?
if [ $rc != 0 ]; then
  python3 "$CAW/queue_cli.py" dequeue "$LOCK" "$NAME" >/dev/null
  echo "KEEPER GAVE UP (queue_cli wait exit $rc) $(date '+%F %T')"
  exit 3
fi
date '+%s' > "$SIG/HOLD_ACQUIRED"
echo "HOLD_ACQUIRED pid $$ $(date '+%F %T')"
acquired=$(date +%s)
reason=release-file
while [ ! -f "$SIG/RELEASE" ]; do
  if [ $(( $(date +%s) - acquired )) -gt "$HOLD_LIMIT" ]; then reason=safety-limit; break; fi
  if ! kill -0 "$WATCH_PID" 2>/dev/null; then reason="watched pid $WATCH_PID gone"; break; fi
  sleep 5
done
python3 "$CAW/hold_cli.py" release "$LOCK" $$
rm -f "$SIG/HOLD_ACQUIRED"
echo "HOLD_RELEASED $(date '+%F %T') ($reason)"
