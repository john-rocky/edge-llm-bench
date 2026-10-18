#!/usr/bin/env bash
# Run a command under the shared iPhone hold (hold_cli.py / queue_cli.py of the conversion lane): enqueue
# under <name>, wait for the hold with this process as keeper, export HOLD_DEADLINE (start + <minutes> * 60 - 120 s),
# run the command, release on exit whatever happens. One sitting per call; 45 minutes at most (house rule).
#
#   tools/with_hold.sh <name> <minutes> -- <command...>
set -euo pipefail
NAME="${1:?hold name}"; MIN="${2:?minutes}"; shift 2; [ "${1:-}" = "--" ] && shift
[ "$MIN" -le 45 ] || { echo "a hold is 45 minutes at most" >&2; exit 2; }
HOLD="${IPHONE_HOLD:-$HOME/code/litertlm-convert/community_accel_work/.iphone_hold}"
CLI="$HOME/code/litertlm-convert/community_accel_work"
python3 "$CLI/queue_cli.py" enqueue "$HOLD" "$NAME" fable-x2-iphone "$MIN" >/dev/null
python3 "$CLI/queue_cli.py" wait "$HOLD" "$NAME" $$ --timeout "${WAIT_TIMEOUT:-1800}"
START=$(date +%s)
export HOLD_DEADLINE=$(( START + MIN * 60 - 120 ))
release(){ python3 "$CLI/hold_cli.py" release "$HOLD" $$ >/dev/null 2>&1 || true; echo "[with_hold] released $(date +%T) (held $(( $(date +%s) - START )) s)"; }
trap release EXIT
echo "[with_hold] acquired $(date +%T) as $NAME pid $$, deadline $(date -r "$HOLD_DEADLINE" +%T)"
"$@"
