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
#
# native-benchmark-<P>x<D> rows (2026-10-08, docs/coreai-arm-v1.md): one launch runs the
# engine's own benchmark instead of a task — litert-lm --litert-native-benchmark (runs= calls of
# benchmark(), call 1 cold), core-ai --coreai-native-benchmark (Apple's llm-benchmark measurement
# on the stock path: runs= timed trials after the warmup trial, printed as trial 0, cold). The
# app writes no record for them: the console's YARDSTICK_NATIVE_OK lines are imported with
# scripts/import_native_benchmark.py --schema-v1 into <campaign>/app-path-native/, --like = this
# campaign's task record of the same arm and model (so a model's task row runs first; without
# one the console is listed in NATIVE_IMPORT_PENDING.txt). No capture gate on them. A core-ai
# row's backend=ane is arm identity only (records stamp core-ai-ane); nothing is passed for it.
#
#   DRY_RUN=1 scripts/bench_matrix_iphone.sh run <cells>   # print every launch; no device call
#     (the loop below runs with xcrun / gtimeout / sleep replaced by printers and the campaign
#     directory in a temp dir: nothing under results/, no wait)
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
. "$REPO/scripts/lib/matrix_common.sh"

DEV="${BENCH_UDID:-${DEV:-C7A74909-7573-5A0F-9201-F7D03DC811EF}}"  # devicectl id, iPhone 18 Pro (the bench iPhone from
                                                                       # 2026-09-25; the 17 Pro A6F3E849-… only when phones run short)
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
if [ "${DRY_RUN:-0}" = 1 ]; then
  # Every device call of this script goes through xcrun (gtimeout only wraps it): print it to
  # the terminal (fd 3) instead; `device info details` answers the two lines the provenance
  # grep expects. The campaign directory is a temp dir and cooldowns do not wait.
  exec 3>&1
  OUT="$(mktemp -d)/$CAMPAIGN"
  printf 'DRY-RUN campaign dir (temp): %s\n' "$OUT" >&3
  xcrun(){
    printf 'DRY-RUN xcrun %s\n' "$*" >&3
    case "$*" in *"device info details"*) printf 'OS Version: (dry run)\nOS Build Update: (dry run)\n' ;; esac
  }
  gtimeout(){ while [ $# -gt 0 ] && [ "${1#--}" != "$1" ]; do shift; done; shift; "$@"; }
  sleep(){ :; }
fi

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

count_lines(){ # <pattern> <file> -> how many lines of the file match (0 when it does not exist)
  local n=0
  [ -f "$2" ] && n="$(grep -c -- "$1" "$2" || true)"
  echo "${n:-0}"
}

native_cell(){ # <runtime> <model-id> <task> <runs> [extra launch args...] — one native-benchmark launch
  # The engine's own benchmark instead of a task (header: native-benchmark rows). `--task`
  # still names a real task id (the app reads it before the native branch). Always returns 0:
  # a launch with no YARDSTICK_NATIVE_OK line is logged, and the session goes on.
  local rt="$1" mid="$2" task="$3" runs="$4"; shift 4
  local flag arm=""
  case "$rt" in
    litert-lm) flag=--litert-native-benchmark; arm=litert-lm ;;
    core-ai)   flag=--coreai-native-benchmark; arm=core-ai-ane ;;
    *) echo "SKIPPED $rt $mid $task reason=no-native-benchmark-entry-on-ios" | tee -a "$OUT/SKIPPED.txt"; return 0 ;;
  esac
  # a LiteRT-LM CPU row stamps litert-lm-cpu (--litert-backend cpu among the extra args)
  local a prev=""
  for a in "$@"; do [ "$prev" = "--litert-backend" ] && [ "$a" = cpu ] && arm=litert-lm-cpu; prev="$a"; done
  local logf="$OUT/console_$(echo "${rt}_${mid}_${task}" | tr '/.' '__').txt"
  local ok0 fatal0 t0 t1 ok fatal
  ok0="$(count_lines YARDSTICK_NATIVE_OK "$logf")"; fatal0="$(count_lines YARDSTICK_FATAL "$logf")"
  t0="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  log "CELL $rt / $mid / $task runs=$runs (native: one launch, $flag) $* ($(date +%H:%M:%S))"
  gtimeout --kill-after=30 "$CELL_TIMEOUT" \
    xcrun devicectl device process launch --console --terminate-existing --device "$DEV" "$APP" \
    -- --yardstick-autorun --runtime "$rt" --model-id "$mid" --task short-chat --runs "$runs" "$@" \
    "$flag" "${task#native-benchmark-}" \
    </dev/null 2>&1 | tee -a "$logf" \
    | grep -E "YARDSTICK_(BEGIN|NATIVE_OK|WARN|FATAL|ALL_DONE)" || true
  t1="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  ok=$(( $(count_lines YARDSTICK_NATIVE_OK "$logf") - ok0 ))
  fatal=$(( $(count_lines YARDSTICK_FATAL "$logf") - fatal0 ))
  # the importer counts launches from the lines (a LiteRT-LM run=1 or a Core AI trial that does
  # not go up starts one) and takes one start time per launch that printed any
  [ "$ok" -gt 0 ] && echo "$t0" >> "$logf.launch_times"
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$t0" "$t1" "$arm" "$mid" "$task" "$runs" "$ok" "$fatal" \
    >> "$OUT/native_launches.tsv"
  echo "native lines=$ok fatal=$fatal ($(basename "$logf"))"
  native_import "$arm" "$mid" "$logf"
  return 0
}

native_like(){ # <arm> <model-id> -> this campaign's task record of that arm and model (the 1K text task first, newest)
  ARM="$1" MID="$2" OUT="$OUT" python3 - <<'PY'
import glob, json, os
best = None
for f in glob.glob(os.path.join(os.environ["OUT"], "device-jsonl", "*.json")):
    try:
        r = json.load(open(f))
    except (OSError, ValueError):
        continue
    task = r.get("task") or ""
    if (r.get("runtime") != os.environ["ARM"] or (r.get("model") or {}).get("id") != os.environ["MID"]
            or task.startswith("native-benchmark-")):
        continue
    key = (task == "long-context-1024-gen256", r.get("timestamp") or "")
    if best is None or key > best[0]:
        best = (key, f)
if best:
    print(best[1])
PY
}

native_import(){ # <arm> <model-id> <console log> -> schema-v1 records in app-path-native/, or a NATIVE_IMPORT_PENDING line
  local arm="$1" mid="$2" logf="$3" like dev instrument rc=0
  if [ ! -s "$logf.launch_times" ]; then
    echo "NATIVE_IMPORT_PENDING $(basename "$logf") (no launch printed a YARDSTICK_NATIVE_OK line)" \
      | tee -a "$OUT/NATIVE_IMPORT_PENDING.txt"
    return 0
  fi
  like="$(native_like "$arm" "$mid")"
  if [ -z "$like" ]; then
    echo "NATIVE_IMPORT_PENDING $(basename "$logf") (no $arm task record of $mid in device-jsonl/ for --like)" \
      | tee -a "$OUT/NATIVE_IMPORT_PENDING.txt"
    return 0
  fi
  dev="$(python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))["device"]["modelIdentifier"])' "$like" 2>/dev/null)" || dev=""
  if [ -z "$dev" ]; then
    echo "NATIVE_IMPORT_PENDING $(basename "$logf") (--like $(basename "$like") has no device.modelIdentifier)" \
      | tee -a "$OUT/NATIVE_IMPORT_PENDING.txt"
    return 0
  fi
  case "$arm" in
    core-ai-ane) instrument="core-ai llm-benchmark measurement (CoreAIRuntime.nativeBenchmarkStock) via BenchmarkApp --coreai-native-benchmark" ;;
    *) instrument="litert-lm native benchmark() via BenchmarkApp --litert-native-benchmark" ;;
  esac
  # every launch of the console so far, again: the importer numbers a console's lines 1..N, so the
  # records of a later launch land beside the earlier ones (same files rewritten, new ids)
  python3 "$REPO/scripts/import_native_benchmark.py" --schema-v1 "$logf" --out "$OUT/app-path-native" \
    --like "$like" --launch-times "$(paste -sd, "$logf.launch_times")" --instrument "$instrument" \
    --device "$dev" 2>> "$OUT/native_import.log" || rc=$?
  if [ "$rc" = 0 ]; then
    echo "NATIVE_IMPORTED $(basename "$logf") -> app-path-native/ (--like $(basename "$like"))"
  else
    echo "NATIVE_IMPORT_PENDING $(basename "$logf") (importer exit $rc; native_import.log)" \
      | tee -a "$OUT/NATIVE_IMPORT_PENDING.txt"
  fi
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
    local counters
    counters="$(cell_opt engine-counters "" ${opts[@]+"${opts[@]}"})"   # litert-lm: on|off (see MediaPipeRuntime.loadModel)
    local extra=()
    [ -n "$ctx" ] && extra+=(--context-tokens "$ctx")
    [ -n "$maxtok" ] && extra+=(--max-tokens "$maxtok")
    [ -n "$counters" ] && extra+=(--litert-engine-counters "$counters")
    local be
    be="$(cell_opt backend "" ${opts[@]+"${opts[@]}"})"   # arm identity
    # litert-lm: the app's --litert-backend cpu|gpu. executorch: the delegate is the build's
    # (ios/BenchmarkApp/project-executorch.yml links XNNPACK only) and its records carry the
    # arm id executorch-<backend>, which names their files (ResultStore) — the gate looks
    # them up by that id (docs/executorch-arm-v1.md "iPhone"). onnxruntime-genai: the release
    # XCFramework is CPU-only (no flag) and its records carry onnxruntime-genai-<backend> the
    # same way (docs/ortgenai-arm-v1.md "iPhone").
    [ -n "$be" ] && [ "$rt" = litert-lm ] && extra+=(--litert-backend "$be")
    local rec_rt="$rt"
    [ "$rt" = executorch ] && [ -n "$be" ] && rec_rt="executorch-$be"
    [ "$rt" = onnxruntime-genai ] && [ -n "$be" ] && rec_rt="onnxruntime-genai-$be"

    [ "$first" = 1 ] && first=0 || { log "cooldown ${cool}s"; sleep "$cool"; }
    if [ "${serious_wait:-0}" -gt 0 ]; then
      log "previous capture saw serious/critical thermal — pausing ${serious_wait}s more before this cell"
      sleep "$serious_wait"; serious_wait=0
    fi
    case "$task" in native-benchmark-*)
      # the engine's own benchmark: one launch, its console lines imported, no capture gate
      native_cell "$rt" "$mid" "$task" "$runs" ${extra[@]+"${extra[@]}"}
      continue ;;
    esac
    run_cell "$rt" "$mid" "$task" "$runs" ${extra[@]+"${extra[@]}"}
    local pulled verdict
    pulled="$(pull_new)"; verdict="$(cell_verdict "$rec_rt" "$mid" "$task" "$runs")"
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
      quarantine_cell "$rec_rt" "$mid" "$task" "$runs"
      sleep "$retry_cool"
      run_cell "$rt" "$mid" "$task" "$runs" ${extra[@]+"${extra[@]}"}
      pulled="$(pull_new)"; verdict="$(cell_verdict "$rec_rt" "$mid" "$task" "$runs")"
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
