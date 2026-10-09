#!/bin/bash
# Owner of the Galaxy S26 hold for one block of ORT GenAI round r8-33202
# (2026-10-09): r2c's hold_keeper.sh with the block's queue name and size as
# arguments. Puts the block in the queue (idempotent), runs the queue's `wait`
# as its child with this script's pid as the hold owner (the line's order; the
# hold is taken 2 s after it is free), then keeps the hold until the release
# file appears (r8_s26.sh touches it when the block is done) or HOLD_MAX_S has
# passed since the hold named it, and gives it back through hold_cli.py. If the
# hold has not come by the deadline it stops the wait and leaves the line. The
# python steps run from here, not from the command line, because of the Mac
# measurement-window guard (round r2's trap).
#   usage: hold_keeper.sh <queue name> <minutes> <release-file> <hold-max-s> <deadline HH:MM>
# Env (offline tests only): KEEPER_HOLD, KEEPER_LOG.
set -uo pipefail
CAW="$HOME/code/litertlm-convert/community_accel_work"
HOLD="${KEEPER_HOLD:-$CAW/s2_npu_sweep/.device_hold}"
LOG="${KEEPER_LOG:-$(cd "$(dirname "$0")" && pwd)/host.log}"
SCRIPT=$1
MINUTES=$2
REL=$3
MAX=$4
DEADLINE=$(date -j -f '%Y-%m-%d %H:%M:%S' "$(date +%F) $5:00" +%s) || exit 2

log() { echo "$(date '+%F %T') keeper $$: $*" >>"$LOG"; }
mine() { grep -q "\"pid\": $$," "$HOLD" 2>/dev/null && grep -q "\"script\": \"$SCRIPT\"" "$HOLD" 2>/dev/null; }
leave_line() { python3 "$CAW/queue_cli.py" dequeue "$HOLD" "$SCRIPT" >/dev/null 2>&1; }

log "start: $SCRIPT (~$MINUTES min), hold $HOLD, release file $REL, hold max ${MAX}s, deadline $5"
python3 "$CAW/queue_cli.py" enqueue "$HOLD" "$SCRIPT" edge-llm-bench-df "$MINUTES" >>"$LOG" 2>&1
python3 "$CAW/queue_cli.py" wait "$HOLD" "$SCRIPT" $$ --timeout $(( DEADLINE - $(date +%s) )) --poll 2 >>"$LOG" 2>&1 &
wpid=$!
got=""
while [[ -z "$got" ]]; do
  if mine; then
    got=$(date +%s)
  elif ! kill -0 "$wpid" 2>/dev/null; then
    wait "$wpid"; rc=$?
    if mine; then got=$(date +%s); else log "wait exited (rc $rc) without the hold; leaving the line"; leave_line; exit 3; fi
  elif (( $(date +%s) > DEADLINE )); then
    kill "$wpid" 2>/dev/null
    log "deadline $5 passed without the hold; wait stopped, leaving the line"
    leave_line
    exit 3
  else
    sleep 2
  fi
done
log "hold acquired: $(cat "$HOLD")"
reason=""
while [[ -z "$reason" ]]; do
  if [[ -e "$REL" ]]; then
    reason="release file"
  elif (( $(date +%s) - got >= MAX )); then
    reason="hold max ${MAX}s"
  elif ! mine; then
    log "the hold no longer names this keeper: $(cat "$HOLD" 2>/dev/null || echo none); exiting"
    exit 4
  else
    sleep 2
  fi
done
python3 "$CAW/hold_cli.py" release "$HOLD" $$ >>"$LOG" 2>&1
log "hold returned ($reason) after $(( $(date +%s) - got )) s; hold now: $(cat "$HOLD" 2>/dev/null || echo none)"
