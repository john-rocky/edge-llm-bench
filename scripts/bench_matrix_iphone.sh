#!/usr/bin/env bash
# Generic iPhone matrix runner — drives BenchmarkApp headlessly over an arbitrary
# cells file (matrices/README.md grammar), one `devicectl process launch` per cell.
#
# Supersedes scripts/bench_warm_matrix_iphone.sh for new campaigns (that script
# stays frozen as provenance for its published captures). Differences:
#   - platform column + task column + per-cell overrides (runs / context-tokens /
#     max-tokens / cooldown) come from the cells file, not env
#   - anchor=1 cells run first (session-anchor normalization, regression_diff --anchors)
#   - exclude=/manual= cells are skipped with the reason logged to SKIPPED.txt
#   - optional catalog preflight: CATALOG_JSON=<yardstick list --json output>
#
#   BENCH_UDID=<udid> scripts/bench_matrix_iphone.sh run matrices/apple-warm-matrix.cells
#   scripts/bench_matrix_iphone.sh pull      # recover an aborted session
#   scripts/bench_matrix_iphone.sh report
#
# Physics carried over verbatim from the warm-matrix driver (hard-won):
#   - gtimeout --kill-after=30: LiteRT-LM can hang at teardown
#     (callback_thread_pool DEADLINE_EXCEEDED) and never exit; completed runs
#     are already persisted on-device, so killing the console is lossless.
#   - </dev/null: devicectl --console forwards stdin, which would otherwise
#     swallow the rest of the cell list feeding the while-read loop.
#   - capture gate (scripts/cell_gate.py): every run must start nominal AND the
#     warm spread must stay under 5% (spread-rule). A flagged capture is moved
#     to device-jsonl-flagged/ (kept for audit, out of build_summary's glob),
#     the cell cools THERMAL_COOLDOWN and re-runs once; a flagged retry stands
#     with a FLAGGED.txt note.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
. "$REPO/scripts/lib/matrix_common.sh"

DEV="${BENCH_UDID:-${DEV:-A6F3E849-1947-5202-9AD1-9C881CA58EEF}}"  # devicectl id, iPhone 17 Pro
APP="${APP:-com.example.CoreMLLLMChat}"              # borrowed App ID (memory entitlements)
DEFAULT_RUNS="${RUNS:-4}"
BASE_COOLDOWN="${BASE_COOLDOWN:-100}"                # s between cells (fairness cold-warm-split)
THERMAL_COOLDOWN="${THERMAL_COOLDOWN:-240}"          # s before the one thermal re-run
# `fair` is this phone's charging label (the anchor rule handles it); `serious` /
# `critical` is a real escalation. Owner decision 2026-09-09: pause, capped —
# a capture that saw serious/critical waits SERIOUS_COOLDOWN before its retry
# and again before the next cell, instead of the 240 s, and the run goes on.
SERIOUS_COOLDOWN="${SERIOUS_COOLDOWN:-600}"
CELL_TIMEOUT="${CELL_TIMEOUT:-3600}"                 # litert teardown stalls: keep 3600 for litert cells
CAMPAIGN="${CAMPAIGN:-$(date +%F)-iphone-matrix}"
OUT="$REPO/results/raw/$CAMPAIGN"

log(){ printf '\n=== %s ===\n' "$*"; }

STAMP(){ echo "$OUT/.campaign_start"; }
pull_new(){ # records (*.json) + endurance turn sidecars (*.turns.ndjson, next to their record)
  local tmp; tmp="$(mktemp -d)"
  xcrun devicectl device copy from --device "$DEV" --domain-type appDataContainer \
    --domain-identifier "$APP" --source Documents/results --destination "$tmp" >/dev/null 2>&1
  mkdir -p "$OUT/device-jsonl"
  local n=0 f base
  while IFS= read -r -d '' f; do
    base="$(basename "$f")"
    # A quarantined capture is still on the device: once moved to
    # device-jsonl-flagged/ it must not be pulled back into the session
    # (observed 2026-09-04: the HOT retry re-pulled the flagged trio).
    [ -e "$OUT/device-jsonl/$base" ] || [ -e "$OUT/device-jsonl-flagged/$base" ] \
      || { cp "$f" "$OUT/device-jsonl/$base"; n=$((n+1)); }
  done < <(find "$tmp" \( -name "*.json" -o -name "*.ndjson" \) -newer "$(STAMP)" -print0 2>/dev/null)
  rm -rf "$tmp"
  echo "$n"
}

cell_files(){ # <runtime> <model-id> <task> -> matching device-jsonl paths, sorted
  RT="$1" MID="$2" TASK="$3" OUT="$OUT" python3 - <<'PY'
import glob, os
pat = (os.environ["RT"] + "_" + os.environ["MID"].replace("/", "_")
       + "_" + os.environ["TASK"] + "_*.json")
for f in sorted(glob.glob(os.path.join(os.environ["OUT"], "device-jsonl", pat))):
    print(f)
PY
}

cell_verdict(){ # <runtime> <model-id> <task> <runs> -> OK / SHORT n / HOT ... / SPREAD pct / DEAD n / COLLAPSE pct / GATE_ERROR
  local files v
  files="$(cell_files "$1" "$2" "$3")"
  [ -z "$files" ] && { echo "SHORT 0"; return 0; }
  # word-splitting is safe: device-jsonl names carry no spaces
  # shellcheck disable=SC2086
  v="$(python3 "$REPO/scripts/cell_gate.py" --runs "$4" $files 2>/dev/null)" || true
  # a crashed gate must not read as a pass (empty matched no flag pattern and
  # the capture sailed through — the guard's own failure mode, audited 2026-08-27)
  echo "${v:-GATE_ERROR}"
}

quarantine_cell(){ # <runtime> <model-id> <task> <runs> — move the judged capture aside.
  # The flagged runs must leave device-jsonl/: build_summary ingests that whole
  # dir, so a kept-in-place flagged capture would pool into the same session
  # median the re-run was meant to clean (the pre-2026-08-26 behavior).
  mkdir -p "$OUT/device-jsonl-flagged"
  cell_files "$1" "$2" "$3" | tail -n "$4" | while IFS= read -r f; do
    # An endurance record names its per-turn sidecar; the series goes with it.
    local sc
    sc="$(python3 -c 'import json,sys; print((json.load(open(sys.argv[1])).get("endurance") or {}).get("turnsSidecar") or "")' "$f" 2>/dev/null || true)"
    [ -n "$sc" ] && [ -e "$OUT/device-jsonl/$sc" ] && mv "$OUT/device-jsonl/$sc" "$OUT/device-jsonl-flagged/"
    mv "$f" "$OUT/device-jsonl-flagged/"
  done
}

run_cell(){ # <runtime> <model-id> <task> <runs> [extra launch args...]
  local rt="$1" mid="$2" task="$3" runs="$4"; shift 4
  local logf="$OUT/console_$(echo "${rt}_${mid}_${task}" | tr '/.' '__').txt"
  log "CELL $rt / $mid / $task runs=$runs $* ($(date +%H:%M:%S))"
  local rc=0
  gtimeout --kill-after=30 "$CELL_TIMEOUT" \
    xcrun devicectl device process launch --console --terminate-existing --device "$DEV" "$APP" \
    -- --yardstick-autorun --runtime "$rt" --model-id "$mid" --task "$task" --runs "$runs" "$@" \
    </dev/null 2>&1 | tee -a "$logf" \
    | grep -E "YARDSTICK_(BEGIN|RUN_OK|RUN_FAIL|FATAL|ALL_DONE)" || rc=$?
  # PIPESTATUS is bash-specific; recover the launch status from gtimeout's exit
  # conventions where it matters: 124 = timeout (runs already persisted on
  # device — lossless, note and continue).
  return 0
}

launch_refused(){ # <runtime> <model-id> <task> -> 0 when the cell's launch was refused by CoreDevice (no app run at all)
  # The device-side reasons a launch fails without the app running: the trusted USB
  # session gone (error 4016, seen 2026-09-09 06:42 — 13 cells then cycled through
  # their cooldowns for 47 min), a locked phone, a device no longer listed.
  local logf="$OUT/console_$(echo "${1}_${2}_${3}" | tr '/.' '__').txt"
  [ -f "$logf" ] || return 1
  tail -40 "$logf" | grep -qE "CoreDeviceError error 4016|not able to fulfill the requested usage assertion|could not be, unlocked|specified device was not found|Device is not connected"
}

preflight(){ # <cells-file>
  [ -n "${CATALOG_JSON:-}" ] || { echo "preflight: CATALOG_JSON unset — skipping (advisory)"; return 0; }
  python3 "$REPO/scripts/validate_cells.py" --catalog "$CATALOG_JSON" "$1"
}

cmd_run(){
  local cells_file="${1:?usage: run <cells-file>}"
  python3 "$REPO/scripts/validate_cells.py" "$cells_file"
  preflight "$cells_file"
  mkdir -p "$OUT/device-jsonl"
  [ -f "$(STAMP)" ] || touch "$(STAMP)"
  xcrun devicectl device info details --device "$DEV" 2>/dev/null \
    | grep -E "OS Build Update|OS Version" >> "$OUT/session_provenance.txt"
  date "+session start %F %T" >> "$OUT/session_provenance.txt"
  echo "cells: $cells_file" >> "$OUT/session_provenance.txt"

  local first=1 refused=0 serious_wait=0
  # cells_for prints anchors first and logs CELL_SKIP lines to stderr.
  while read -r rt mid task rest; do
    read -r -a opts <<<"${rest:-}"
    local runs cool ctx maxtok
    runs="$(cell_opt runs "$DEFAULT_RUNS" ${opts[@]+"${opts[@]}"})"
    cool="$(cell_opt cooldown "$BASE_COOLDOWN" ${opts[@]+"${opts[@]}"})"
    ctx="$(cell_opt context-tokens "" ${opts[@]+"${opts[@]}"})"
    maxtok="$(cell_opt max-tokens "" ${opts[@]+"${opts[@]}"})"
    local extra=()
    [ -n "$ctx" ] && extra+=(--context-tokens "$ctx")
    [ -n "$maxtok" ] && extra+=(--max-tokens "$maxtok")

    [ "$first" = 1 ] && first=0 || { log "cooldown ${cool}s"; sleep "$cool"; }
    if [ "${serious_wait:-0}" -gt 0 ]; then
      log "previous capture saw serious/critical thermal — pausing ${serious_wait}s more before this cell"
      sleep "$serious_wait"; serious_wait=0
    fi
    run_cell "$rt" "$mid" "$task" "$runs" ${extra[@]+"${extra[@]}"}
    local pulled verdict
    pulled="$(pull_new)"; verdict="$(cell_verdict "$rt" "$mid" "$task" "$runs")"
    echo "pulled=$pulled verdict=$verdict"
    local retry_cool="$THERMAL_COOLDOWN"
    case "$verdict" in *serious*|*critical*) retry_cool="$SERIOUS_COOLDOWN"; serious_wait="$SERIOUS_COOLDOWN" ;; esac
    # A phone that stopped accepting launches ends the session now: two cells in a
    # row refused by CoreDevice with nothing pulled is a lost device, not two cell
    # failures. Captured cells stand; the job reads DEVICE_LOST.txt (verdict DEVICE).
    if [[ "$pulled" == 0 && "$verdict" == SHORT* ]] && launch_refused "$rt" "$mid" "$task"; then
      refused=$((refused + 1))
      if [ "$refused" -ge 2 ]; then
        echo "DEVICE_LOST after $rt $mid $task: the phone refused $refused launches in a row ($(date +%T)) — session ended, captured cells stand; remaining cells not attempted" \
          | tee -a "$OUT/DEVICE_LOST.txt"
        break
      fi
    else
      refused=0
    fi
    if [[ "$verdict" == DEGENERATE* ]]; then
      # A repetition loop reproduces on re-run: flag, keep, never retry (cell_gate.py).
      echo "GATE_FAIL $rt $mid $task verdict='$verdict' (output is a repetition loop — not retried; the rate is not a measurement)" \
        | tee -a "$OUT/FLAGGED.txt"
    fi
    if [[ "$verdict" == HOT* || "$verdict" == SPREAD* || "$verdict" == DEAD* || "$verdict" == COLLAPSE* || "$verdict" == GATE_ERROR* ]]; then
      log "gate: $verdict — quarantine flagged capture, cooldown ${retry_cool}s, re-run once"
      quarantine_cell "$rt" "$mid" "$task" "$runs"
      sleep "$retry_cool"
      run_cell "$rt" "$mid" "$task" "$runs" ${extra[@]+"${extra[@]}"}
      pulled="$(pull_new)"; verdict="$(cell_verdict "$rt" "$mid" "$task" "$runs")"
      echo "pulled=$pulled verdict=$verdict"
      case "$verdict" in *serious*|*critical*) serious_wait="$SERIOUS_COOLDOWN" ;; esac
      [[ "$verdict" == HOT* || "$verdict" == SPREAD* || "$verdict" == DEAD* || "$verdict" == COLLAPSE* || "$verdict" == GATE_ERROR* ]] \
        && echo "GATE_FAIL $rt $mid $task retry='$verdict' (retry kept; flagged capture in device-jsonl-flagged/)" \
        | tee -a "$OUT/FLAGGED.txt"
    fi
  done < <(cells_for ios "$cells_file" 2> >(tee -a "$OUT/SKIPPED.txt" >&2))
  cmd_report
}

cmd_pull(){
  mkdir -p "$OUT"
  [ -f "$(STAMP)" ] || touch -t 197001010000 "$(STAMP)"
  echo "pulled $(pull_new) new files -> $OUT/device-jsonl"
}

cmd_report(){
  OUT="$OUT" python3 - <<'PY'
import json, glob, os, statistics, collections
out = os.environ["OUT"]
cells = collections.defaultdict(list)
for f in sorted(glob.glob(os.path.join(out, "device-jsonl", "*.json"))):
    d = json.load(open(f))
    key = (d["runtime"], d["model"]["id"], d["task"])
    cells[key].append(d)
lines = ["| runtime | model | task | cold (run1) | warm (med r2-4) | n | thermal |",
         "|---|---|---|---|---|---|---|"]
for (rt, mid, task), rows in sorted(cells.items()):
    rows.sort(key=lambda d: d["timestamp"])
    cold = [r for r in rows if r["metrics"].get("coldRun")]
    warm = [r for r in rows if not r["metrics"].get("coldRun")]
    cold_s = f"{cold[-1]['metrics']['decodeTokensPerSecond']:.1f}" if cold else "—"
    wtps = [r["metrics"]["decodeTokensPerSecond"] for r in warm[-3:]]
    warm_s = f"{statistics.median(wtps):.1f}" if wtps else "—"
    therm = sorted({r["metrics"].get("initialThermalState", "?") for r in rows})
    lines.append(f"| {rt} | {mid} | {task} | {cold_s} | {warm_s} | {len(rows)} | {','.join(therm)} |")
report = "\n".join(lines) + "\n"
open(os.path.join(out, "summary.md"), "w").write(report)
print(report)
PY
}

case "${1:-}" in
  run)    shift; cmd_run "$@" ;;
  pull)   cmd_pull ;;
  report) cmd_report ;;
  *) sed -n '2,25p' "$0"; exit 1 ;;
esac
