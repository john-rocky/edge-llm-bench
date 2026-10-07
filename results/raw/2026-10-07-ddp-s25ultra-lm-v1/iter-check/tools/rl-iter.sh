#!/bin/bash
# rl-iter.sh "<note>" <command...>: append "### CMD:" + output + exit code to iter-check/run-log-iter.txt, echo the tail.
LOG="$HOME/code/edge-llm-bench/results/raw/2026-10-07-ddp-s25ultra-lm-v1/iter-check/run-log-iter.txt"
note="$1"; shift
{ echo; echo "### CMD: $*  ($note)"; echo "### START $(TZ=Asia/Tokyo date '+%Y-%m-%d %H:%M:%S JST')"; } >> "$LOG"
tmp=$(mktemp)
bash -c "$*" > "$tmp" 2>&1
rc=$?
cat "$tmp" >> "$LOG"
{ echo "exit=$rc"; echo "### END $(TZ=Asia/Tokyo date '+%H:%M:%S JST')"; } >> "$LOG"
tail -${RL_TAIL:-40} "$tmp"; echo "exit=$rc"
rm -f "$tmp"
exit $rc
