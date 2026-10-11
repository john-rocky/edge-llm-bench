#!/bin/bash
# The Gallery sessions of PLAN.md, one after another, each from a fresh app process, with a cool-down to COOL_MC
# (m°C, max of zones cpu-0-0-0 / cpu-1-0-0 / gpuss-0) before every session and the screen kept on for the sitting.
#   SERIAL=RFGL80R6A6H OUT=<results dir> SESSIONS="E2B-gpu-1:Gemma-4-E2B-it:GPU:trace E2B-gpu-2:Gemma-4-E2B-it:GPU …" bash run_gallery_sessions.sh
# Session item = <tag>:<model name>:<GPU|CPU>[:trace|-][:<runs>]. Prefill / decode / runs = 1024 / 256 / 3 unless PREFILL / DECODE / RUNS
# (or the item's fifth field) say otherwise; a 1-run session is a cold run in a fresh process by construction.
set -u
SERIAL=${SERIAL:-RFGL80R6A6H}
OUT=${OUT:?results dir}
SESSIONS=${SESSIONS:?}
COOL_MC=${COOL_MC:-34000}
COOL_MAX_S=${COOL_MAX_S:-600}
PREFILL=${PREFILL:-1024}; DECODE=${DECODE:-256}; RUNS=${RUNS:-3}
PERFETTO_CFG=${PERFETTO_CFG:-}
TRACE_DIR=${TRACE_DIR:?perfetto trace dir (e.g. results/raw/2026-10-11-s26-perfetto/traces)}
HERE=$(cd "$(dirname "$0")" && pwd)
LOG="$OUT/steps.log"
say() { echo "[$(date '+%F %T')] $*" | tee -a "$LOG"; }
A() { adb -s "$SERIAL" "$@" < /dev/null; }
zmax() { A shell "cat /sys/class/thermal/thermal_zone5/temp /sys/class/thermal/thermal_zone24/temp /sys/class/thermal/thermal_zone36/temp" | tr -d '\r' | sort -n | tail -1; }

stay_before=$(A shell settings get global stay_on_while_plugged_in | tr -d '\r')
say "sessions start; stay_on_while_plugged_in was '$stay_before' (set to usb for the sitting, restored at the end)"
A shell "svc power stayon usb; input keyevent KEYCODE_WAKEUP" >/dev/null 2>&1
for item in $SESSIONS; do
  IFS=: read -r tag model accel trace runs <<< "$item"
  runs=${runs:-$RUNS}
  t0=$(date +%s)
  while :; do z=$(zmax); [ "$z" -le "$COOL_MC" ] && break; [ $(( $(date +%s) - t0 )) -ge "$COOL_MAX_S" ] && { say "cool-down limit reached at $z m°C"; break; }; sleep 15; done
  say "session $tag: zones max $z m°C after $(( $(date +%s) - t0 )) s cool-down; locked=$(A shell dumpsys trust 2>/dev/null | grep -m1 -o 'deviceLocked=[0-9]' | tr -d '\r')"
  minwait=$(( runs * ${PER_RUN_S:-12} ))
  args=(session --out "$OUT" --model "$model" --accel "$accel" --prefill "$PREFILL" --decode "$DECODE" --runs "$runs" --tag "$tag" --min-wait "$minwait")
  [ "${trace:-}" = trace ] && [ -n "$PERFETTO_CFG" ] && args+=(--perfetto-cfg "$PERFETTO_CFG" --trace-dir "$TRACE_DIR")
  SERIAL=$SERIAL python3 "$HERE/gallery_bench.py" "${args[@]}" > "$OUT/$tag.driver.log" 2>&1
  rc=$?
  say "session $tag rc=$rc: $(grep -E 'runs done|SESSION .* END|Error|Traceback|RuntimeError|TimeoutError' "$OUT/$tag.driver.log" | tail -3 | tr '\n' ' ' | cut -c1-300)"
done
A shell "svc power stayon ${stay_before:-false}" >/dev/null 2>&1
[ "${stay_before:-0}" = 0 ] && A shell "svc power stayon false" >/dev/null 2>&1
say "sessions done; stay_on_while_plugged_in now '$(A shell settings get global stay_on_while_plugged_in | tr -d '\r')'"
