#!/usr/bin/env bash
# Round-mode driver for catalog X2's iPhone leg (2026-10-17, iPhone 18 Pro). The iPhone matrix runner
# (scripts/bench_matrix_iphone.sh) runs each cell once; the S26 and Mac legs of X2 ran their allocation
# ladders in ROUNDS (every cell once per round, the order reversed on even rounds), which keeps the thermal
# history of the three allocations paired within a round. This script does that on the phone with the
# runner's launch physics (gtimeout, --terminate-existing, </dev/null, pull by mtime into device-jsonl/)
# and nothing else: no capture gate, no retry, no quarantine — every record stays, the readout
# (tools/ladder.py) shows every round, and the reader judges.
#
#   ROUNDS=6 COOLDOWN=60 BENCH_UDID=<udid> APP=com.example.CoreMLLLMChat \
#     tools/round_driver.sh <cells-file> <campaign> <deadline-epoch> [extra launch args...]
#
#   - anchor=1 rows (matrices grammar) run once at the head and once at the tail of the sitting
#   - every other row runs once per round; runs= / context-tokens= / backend= / output-cap= / engine-counters=
#     are forwarded to the app as the runner forwards them
#   - the deadline: no launch starts when its estimate (the cell's last duration, else 120 s) would end after
#     it; the tail anchor is skipped when it does not fit; a hung launch is killed at the deadline + 90 s
#   - after a launch the thermal_final of its last run adds to the cooldown: fair +60 s, serious +300 s,
#     critical +600 s (the dashboard's iPhone runner pauses 600 s after serious/critical)
#   - a cell whose launch produced no record is marked dead and skipped in later rounds (DEAD.txt)
#   - a launch refused by CoreDevice (locked phone, lost trust) ends the sitting (DEVICE_REFUSED.txt)
#   - launches.tsv: one line per launch (round, index, cell, allocation, start, end, rc, records, thermal)
#   - PURGE=1 adds --purge-engine-cache to every launch (probe sittings only)
set -euo pipefail

CELLS="${1:?cells file}"; CAMPAIGN="${2:?campaign}"; DEADLINE="${3:?deadline epoch}"; shift 3
EXTRA_LAUNCH=("$@")
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../../../.." && pwd)"
. "$REPO/scripts/lib/matrix_common.sh"

ROUNDS="${ROUNDS:-6}"
COOLDOWN="${COOLDOWN:-60}"
DEV="${BENCH_UDID:-00008160-000038CA02C00036}"
APP="${APP:-com.example.CoreMLLLMChat}"
PURGE="${PURGE:-0}"
LAUNCH_TIMEOUT_MAX="${LAUNCH_TIMEOUT_MAX:-900}"
OUT="$REPO/results/raw/$CAMPAIGN"
mkdir -p "$OUT/device-jsonl"
LOG="$OUT/driver.log"
log(){ printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*" | tee -a "$LOG"; }
STAMP="$OUT/.campaign_start"
[ -f "$STAMP" ] || touch "$STAMP"

if ! xcrun devicectl list devices 2>/dev/null | grep -q "$DEV.*connected"; then
  log "device $DEV not connected — nothing launched"; exit 2
fi
{
  xcrun devicectl device info details --device "$DEV" 2>/dev/null | grep -E "OS Build Update|OS Version|Marketing Name"
  date "+session start %F %T %Z"
  echo "cells: $CELLS"; echo "rounds: $ROUNDS cooldown: $COOLDOWN deadline: $(date -r "$DEADLINE" "+%F %T")"
  echo "driver: $0 extra: ${EXTRA_LAUNCH[*]:-} purge: $PURGE"
} >> "$OUT/session_provenance.txt"
pymobiledevice3 lockdown get --udid "$DEV" --domain com.apple.mobile.battery 2>/dev/null \
  > "$OUT/battery-start.json" || true

pull_new(){ # records newer than the campaign start not yet in device-jsonl/, copied; prints their names
  local tmp; tmp="$(mktemp -d)"
  xcrun devicectl device copy from --device "$DEV" --domain-type appDataContainer \
    --domain-identifier "$APP" --source Documents/results --destination "$tmp" >/dev/null 2>&1 || true
  local f base
  while IFS= read -r -d '' f; do
    base="$(basename "$f")"
    [ -e "$OUT/device-jsonl/$base" ] || { cp "$f" "$OUT/device-jsonl/$base"; echo "$base"; }
  done < <(find "$tmp" -name "*.json" -newer "$STAMP" -print0 2>/dev/null)
  rm -rf "$tmp"
}

mkdir -p "$OUT/.dur"   # per-cell last launch duration (bash 3.2: files, not associative arrays)
launch_idx=0
launch(){ # <round> <runtime> <model-id> <task> <runs> <ctx-or-dash> [launch args...] -> 0 ok, 3 refused
  local round="$1" rt="$2" mid="$3" task="$4" runs="$5" ctx="$6"; shift 6
  launch_idx=$((launch_idx + 1))
  local key; key="$(echo "${rt}|${mid}|${task}|${ctx}" | tr '/|.' '___')"
  local now; now=$(date +%s)
  local est=120; [ -f "$OUT/.dur/$key" ] && est="$(cat "$OUT/.dur/$key")"
  if [ $((now + est)) -gt "$DEADLINE" ]; then
    log "DEADLINE: $key would end after the deadline (est ${est}s) — not launched"
    echo "deadline $round $key" >> "$OUT/DEADLINE.txt"; return 4
  fi
  local tmo=$(( DEADLINE + 90 - now )); [ "$tmo" -gt "$LAUNCH_TIMEOUT_MAX" ] && tmo="$LAUNCH_TIMEOUT_MAX"
  local tag; tag="$(echo "${rt}_${mid}_${task}" | tr '/.' '__')"
  local console="$OUT/console_r${round}_$(printf '%02d' "$launch_idx")_${tag}_ctx${ctx}.txt"
  local purge=(); [ "$PURGE" = 1 ] && purge=(--purge-engine-cache)
  log "LAUNCH r$round #$launch_idx $rt $mid $task runs=$runs ctx=$ctx $* ${purge[*]:-} (timeout ${tmo}s)"
  local t0 t1 rc=0 pid
  t0="$(date -u +%Y-%m-%dT%H:%M:%SZ)"; local s0; s0=$(date +%s)
  gtimeout --kill-after=30 "$tmo" \
    xcrun devicectl device process launch --console --terminate-existing --device "$DEV" "$APP" \
    -- --yardstick-autorun --runtime "$rt" --model-id "$mid" --task "$task" --runs "$runs" "$@" \
    ${purge[@]+"${purge[@]}"} ${EXTRA_LAUNCH[@]+"${EXTRA_LAUNCH[@]}"} \
    </dev/null > "$console" 2>&1 &
  pid=$!
  # the app saves each record before its RUN_OK line and exits after ALL_DONE; a LiteRT teardown can
  # hang for minutes after that (the runner's gtimeout exists for it) — end the console 30 s after ALL_DONE
  local waited=0
  while kill -0 "$pid" 2>/dev/null; do
    sleep 2
    if grep -qE "YARDSTICK_ALL_DONE|YARDSTICK_FATAL|YARDSTICK_RUN_FAIL" "$console" 2>/dev/null; then
      waited=$((waited + 2))
      if [ "$waited" -ge 30 ]; then log "console ended by the driver 30 s after ALL_DONE/FATAL (teardown)"; kill "$pid" 2>/dev/null || true; fi
    fi
  done
  wait "$pid" || rc=$?
  t1="$(date -u +%Y-%m-%dT%H:%M:%SZ)"; echo $(( $(date +%s) - s0 + 15 )) > "$OUT/.dur/$key"
  local pulled; pulled="$(pull_new | paste -sd';' -)"
  local th_i th_f
  th_i="$(grep -o 'thermal_initial=[a-z]*' "$console" | head -1 | cut -d= -f2)"
  th_f="$(grep -o 'thermal_final=[a-z]*' "$console" | tail -1 | cut -d= -f2)"
  local okn; okn="$(grep -c YARDSTICK_RUN_OK "$console" || true)"
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$round" "$launch_idx" "$rt" "$mid" "$task" "$ctx" \
    "$t0" "$t1" "$rc" "${okn:-0}" "${th_i:-?}" "${th_f:-?}" "$(basename "$console")" "${pulled:-}" >> "$OUT/launches.tsv"
  log "  -> rc=$rc RUN_OK=${okn:-0} thermal ${th_i:-?}->${th_f:-?} records: ${pulled:-none}"
  grep -E "YARDSTICK_(RUN_OK|RUN_FAIL|FATAL|NOTE|WARN)|RegisterAccelerator.*GPU|YARDSTICK_CACHE_PURGE|YARDSTICK_METAL_DEVICE" "$console" \
    | sed 's/^/     /' | tee -a "$LOG" >/dev/null
  if tail -40 "$console" | grep -qE "CoreDeviceError error 4016|not able to fulfill the requested usage assertion|could not be, unlocked|specified device was not found|Device is not connected"; then
    log "DEVICE_REFUSED: the launch was refused by CoreDevice — sitting ended, nothing retried"
    tail -5 "$console" >> "$OUT/DEVICE_REFUSED.txt"; return 3
  fi
  [ -z "$pulled" ] && return 5
  case "${th_f:-}" in
    fair) EXTRA_COOL=60 ;; serious) EXTRA_COOL=300 ;; critical) EXTRA_COOL=600 ;; *) EXTRA_COOL=0 ;;
  esac
  return 0
}

cooldown(){ # never sleeps past the deadline: a cooldown that would end after it ends the sitting (hold 6 of 2026-10-17
  # slept 360 s past its deadline and held the phone 48.8 min against the 45-min rule)
  local s=$((COOLDOWN + ${EXTRA_COOL:-0})); EXTRA_COOL=0
  local left=$(( DEADLINE - $(date +%s) ))
  if [ "$left" -le "$s" ]; then log "cooldown ${s}s would pass the deadline (${left}s left) — sitting ends"; echo "deadline cooldown ${s}s" >> "$OUT/DEADLINE.txt"; STOP=1; return 0; fi
  log "cooldown ${s}s"; sleep "$s"
}

cell_args(){ # <opts...> -> prints the launch args for a row (one per line)
  local ctx maxtok counters be outcap
  ctx="$(cell_opt context-tokens "" "$@")"; maxtok="$(cell_opt max-tokens "" "$@")"
  counters="$(cell_opt engine-counters "" "$@")"; be="$(cell_opt backend "" "$@")"
  outcap="$(cell_opt output-cap "" "$@")"
  [ -n "$ctx" ] && printf '%s\n%s\n' --context-tokens "$ctx"
  [ -n "$maxtok" ] && printf '%s\n%s\n' --max-tokens "$maxtok"
  [ -n "$counters" ] && printf '%s\n%s\n' --litert-engine-counters "$counters"
  [ -n "$be" ] && printf '%s\n%s\n' --litert-backend "$be"
  [ -n "$outcap" ] && printf '%s\n%s\n' --litert-output-cap "$outcap"
  return 0
}

ANCHORS=(); LADDER=()
while IFS= read -r line; do
  case " $line " in *" anchor=1 "*) ANCHORS+=("$line") ;; *) LADDER+=("$line") ;; esac
done < <(cells_for ios "$CELLS" 2>> "$OUT/SKIPPED.txt")
log "sitting: ${#ANCHORS[@]} anchor row(s), ${#LADDER[@]} ladder row(s), $ROUNDS round(s), deadline $(date -r "$DEADLINE" +%H:%M:%S)"

run_row(){ # <round> <row>
  local round="$1" row="$2" rt mid task rest
  read -r rt mid task rest <<<"$row"
  local opts=(); read -r -a opts <<<"${rest:-}"
  local runs ctx; runs="$(cell_opt runs 2 ${opts[@]+"${opts[@]}"})"; ctx="$(cell_opt context-tokens "-" ${opts[@]+"${opts[@]}"})"
  local args=(); while IFS= read -r a; do args+=("$a"); done < <(cell_args ${opts[@]+"${opts[@]}"})
  local rc=0
  launch "$round" "$rt" "$mid" "$task" "$runs" "$ctx" ${args[@]+"${args[@]}"} || rc=$?
  return $rc
}

STOP=0
for a in ${ANCHORS[@]+"${ANCHORS[@]}"}; do
  rc=0; run_row 0 "$a" || rc=$?
  [ "$rc" = 3 ] && { STOP=1; break; }
  cooldown; [ "$STOP" = 1 ] && break
done
if [ "$STOP" = 0 ]; then
  for ((r = 1; r <= ROUNDS; r++)); do
    order=(); if (( r % 2 == 1 )); then order=("${LADDER[@]}"); else for ((i = ${#LADDER[@]} - 1; i >= 0; i--)); do order+=("${LADDER[$i]}"); done; fi
    log "=== round $r ($(date +%H:%M:%S))"
    for row in "${order[@]}"; do
      if [ -f "$OUT/DEAD.txt" ] && grep -qF -- "$row" "$OUT/DEAD.txt"; then log "skip dead cell: $row"; continue; fi
      rc=0; run_row "$r" "$row" || rc=$?
      case "$rc" in
        3) STOP=1; break ;;
        4) STOP=1; break ;;              # deadline
        5) echo "round $r: no record — $row" >> "$OUT/DEAD.txt"; log "DEAD cell (no record): $row"; cooldown ;;
        *) cooldown ;;
      esac
      [ "$STOP" = 1 ] && break
    done
    [ "$STOP" = 1 ] && break
  done
fi
if [ "$STOP" = 0 ] || grep -q deadline "$OUT/DEADLINE.txt" 2>/dev/null; then
  for a in ${ANCHORS[@]+"${ANCHORS[@]}"}; do run_row 99 "$a" || true; done
fi
pymobiledevice3 lockdown get --udid "$DEV" --domain com.apple.mobile.battery 2>/dev/null \
  > "$OUT/battery-end.json" || true
date "+session end %F %T %Z" >> "$OUT/session_provenance.txt"
log "done: $(ls "$OUT/device-jsonl" | wc -l | tr -d ' ') records in device-jsonl/"
