#!/usr/bin/env bash
# Generic Mac matrix runner — loops `yardstick run` over the mac cells of a
# cells file (matrices/README.md grammar).
#
#   scripts/bench_matrix_mac.sh run matrices/release-regression-litert.cells
#
# Round mode (2026-09-18): ROUNDS=N runs the whole cell list N times (one
# launch of RUNS runs per cell per round, order reversed on even rounds) —
# the paired A/B shape for cells that differ only in context-tokens= or
# backend=; capture files are keyed on both. Gate off in round mode.
#   ROUNDS=8 RUNS=2 BASE_COOLDOWN=10 scripts/bench_matrix_mac.sh run <cells>
#
# Binary resolution: $YS_BIN -> $DD_MAC/Build/Products/Release/yardstick
# (scripts/build_yardstick_mac.sh) -> error. The runner REFUSES the spm-lite
# flavor (SwiftPM build; four runtimes compiled out — silently wrong matrix)
# unless YS_ALLOW_SPM=1.
#
# core-ai cells: prompt tasks (short-chat, long-context-*) run through the
# yardstick's CoreAIRuntime like every other arm — same protocol, same record
# (since 2026-09-08; the bundle is side-loaded under BENCH_COREAI_MODELS_DIR,
# a missing one logs SKIPPED with its reason). native-benchmark-* cells still
# dispatch to scripts/coreai_mac_wrapper.sh (external Apple llm-benchmark
# binary; own timing, no --context-tokens — documented comparability caveat).
set -uo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
. "$REPO/scripts/lib/matrix_common.sh"

# Repo-local build dir: an out-of-repo default (~/bench-dd-mac) let a fresh
# clone silently run whatever stale yardstick another checkout had built —
# an unpinned harness under this clone's protocol (2026-08-26 rehearsal).
DD_MAC="${DD_MAC:-$REPO/.build/dd-mac}"
YS="${YS_BIN:-$DD_MAC/Build/Products/Release/yardstick}"
# Engine-pin witness: without this the CLI stamps nothing and rows read
# "pre-stamp" (found 2026-08-27 — the convention lived in the lockfile but
# no runner wired it). stamp_engine_pins.sh regenerates the file at build.
export BENCH_ENGINE_PINS_FILE="${BENCH_ENGINE_PINS_FILE:-$REPO/ios/BenchmarkApp/Vendored/engine-pins.json}"
DEFAULT_RUNS="${RUNS:-4}"
BASE_COOLDOWN="${BASE_COOLDOWN:-30}"
CAMPAIGN="${CAMPAIGN:-$(date +%F)-mac-matrix}"
OUT="$REPO/results/raw/$CAMPAIGN"
UZU_PYTHON="${UZU_PYTHON:-python3}"
UZU_MODEL_DIR="${UZU_MODEL_DIR:-$REPO/models/uzu}"
DRY_RUN=0
# Core AI bundles are side-loaded, one folder per catalog id (CoreAIRuntime.bundleSpec):
# <BENCH_COREAI_MODELS_DIR>/<folder>/{metadata.json, <name>.aimodel | .aimodelc, tokenizer/}.
# Default = the Documents/CoreAIModels layout the app uses on the phone. Staging
# recipe: docs/dashboard-cells-v1.md "Core AI arm".
export BENCH_COREAI_MODELS_DIR="${BENCH_COREAI_MODELS_DIR:-$HOME/Documents/CoreAIModels}"

log(){ printf '\n=== %s ===\n' "$*"; }

coreai_folder(){ # <model-id> -> bundle folder, mirroring CoreAIRuntime.bundleSpec for the dashboard ids
  case "$1" in
    core-ai/qwen3-0.6b-gpu) echo qwen3_0_6b_gpu ;;
    core-ai/qwen3-0.6b-4bit-gpu) echo qwen3_0_6b_4bit_gpu ;;
    core-ai/qwen3-1.7b-gpu) echo qwen3_1_7b_gpu ;;
    core-ai/qwen3-4b-gpu)   echo qwen3_4b_gpu ;;
    core-ai/gemma4-e2b-gpu) echo gemma4_e2b_gpu ;;
    core-ai/gemma4-e4b-gpu) echo gemma4_e4b_gpu ;;
    *) echo "" ;;   # other ids: no preflight here; yardstick reports the miss itself
  esac
}

coreai_bundle_ready(){ # <model-id> -> 0 when staged (or an id this preflight does not know); else a SKIPPED line, 1
  local folder dir
  folder="$(coreai_folder "$1")"
  [ -z "$folder" ] && return 0
  dir="$BENCH_COREAI_MODELS_DIR/$folder"
  if [ ! -f "$dir/metadata.json" ]; then
    echo "SKIPPED core-ai $1 $task reason=coreai-bundle-not-staged ($dir)" | tee -a "$OUT/SKIPPED.txt"
    return 1
  fi
  # Bundle identity next to the session (stored-report-rule): the record carries
  # the catalog's quant label, not the artifact — so the asset the engine loaded,
  # its content hash and byte size go to session_provenance.txt.
  python3 - "$dir" "$1" >> "$OUT/session_provenance.txt" <<'PY'
import json, os, sys
d, mid = sys.argv[1], sys.argv[2]
meta = json.load(open(os.path.join(d, "metadata.json")))
main = meta.get("assets", {}).get("main", "")
asset = os.path.join(d, main)
hp = os.path.join(asset, "main.hash")
h = open(hp, "rb").read().hex() if os.path.exists(hp) else "n/a"
total = sum(os.path.getsize(os.path.realpath(os.path.join(r, f)))
            for r, _, fs in os.walk(asset) for f in fs)
print(f"core-ai bundle {mid}: {d} main={main} main.hash={h} asset_bytes={total} "
      f"compiled={meta.get('compilation', {}).get('date', '?')}")
PY
  return 0
}

run_ys_cell(){
  # One capture attempt for the current loop cell (bash dynamic scope: rt/mid/
  # task_arg/runs/extra/slug are run_cell locals). Wrapped in gtimeout when
  # present (CELL_TIMEOUT, default 1800 s): a litert cell can hang at teardown
  # after its records are on disk (CLAUDE.md), and a hung launch must not stall
  # the session — the records already appended stand.
  local -a to=()
  command -v gtimeout >/dev/null && to=(gtimeout "${CELL_TIMEOUT:-1800}")
  ${to[@]+"${to[@]}"} "$YS" run --runtime "$rt" --model-id "$mid" --task "$task_arg" --runs "$runs" \
    ${extra[@]+"${extra[@]}"} --output "$OUT/${slug}.jsonl" 2>&1 | tail -4
}

guard(){
  # Unified memory: a heavy CPU/GPU pipeline moves these numbers (spread-rule).
  # NB: pattern must not match the repo name "ios-llm-benchmark" in task paths.
  # The named-script list kept going stale (2026-08-27: export_gemma4_pf_pipelined
  # ran at 100% CPU/7 GB straight past it, and that morning's mac session came
  # out ~11% low) — so also match the coreai export venv and any scratchpad
  # export_*.py wholesale; refusing too eagerly costs a cooldown, missing costs
  # a session.
  if ps aux | grep -E "coreai\.llm\.export|release/llm-benchmark |export_simple_template\.py|scratchpad/export_[A-Za-z0-9_]*\.py|coreai-models/\.venv/bin/python|coreai-build compile" | grep -v grep >/dev/null; then
    echo "refusing to start: heavy pipeline running (unified-memory contention)" >&2; exit 1
  fi
}

check_binary(){
  [ -x "$YS" ] || { echo "no yardstick at $YS — run scripts/build_yardstick_mac.sh" >&2; exit 1; }
  local ver flavor
  ver="$("$YS" version 2>/dev/null || true)"
  flavor="$(sed -n 's/.*flavor=\([a-z-]*\).*/\1/p' <<<"$ver")"
  if [ -z "$flavor" ]; then
    echo "WARNING: $YS predates 'yardstick version' — cannot verify build flavor" >&2
  elif [ "$flavor" = "spm-lite" ] && [ "${YS_ALLOW_SPM:-0}" != "1" ]; then
    echo "refusing spm-lite yardstick ($YS): llama-cpp/coreml/executorch/anemll are" >&2
    echo "compiled out of the SwiftPM build. Use scripts/build_yardstick_mac.sh" >&2
    echo "(or YS_ALLOW_SPM=1 if every mac cell is mlx/litert/apple-fm)." >&2
    exit 1
  fi
  echo "yardstick: $YS ${ver:+($ver)}"
}

run_cell(){
  # One cell (one line of the cells file) in round $1. bash dynamic scope:
  # `first` and OUT/YS come from cmd_run; rt/mid/task/task_arg/runs/extra/slug
  # are read by run_ys_cell.
  local round="$1" line="$2"
  local rt mid task rest
  read -r rt mid task rest <<<"$line"
  read -r -a opts <<<"${rest:-}"
  local runs cool ctx maxtok backend slug
  runs="$(cell_opt runs "$DEFAULT_RUNS" ${opts[@]+"${opts[@]}"})"
  cool="$(cell_opt cooldown "$BASE_COOLDOWN" ${opts[@]+"${opts[@]}"})"
  ctx="$(cell_opt context-tokens "" ${opts[@]+"${opts[@]}"})"
  maxtok="$(cell_opt max-tokens "" ${opts[@]+"${opts[@]}"})"
  backend="$(cell_opt backend "" ${opts[@]+"${opts[@]}"})"
  # Capture file = cell identity. backend= and context-tokens= are part of it
  # (2026-09-18): the long-context column runs one (arm, model, task) at several
  # KV allocations, and the litert cpu/gpu arms never pool — without the suffix
  # the second such cell appended into the first one's file and was then
  # "already captured".
  slug="$(echo "${rt}_${mid}_${task}" | tr '/.' '__')"
  [ -n "$backend" ] && slug="${slug}_${backend}"
  [ -n "$ctx" ] && slug="${slug}_ctx${ctx}"

  if [ "$rt" = "uzu" ]; then
    local uzu_file recipe thinking
    local -a uzu_args=()
    uzu_file="$(cell_opt file "" ${opts[@]+"${opts[@]}"})"
    recipe="$(cell_opt recipe "" ${opts[@]+"${opts[@]}"})"
    thinking="$(cell_opt thinking model-default ${opts[@]+"${opts[@]}"})"
    # File, recipe and thinking mode are distinct capture identities.
    slug="${slug}_$(printf '%s' "$uzu_file|$recipe|$thinking" | shasum -a 256 | cut -c1-12)"
    uzu_args+=(--thinking "$thinking")
    if [ -n "$uzu_file" ]; then
      case "$uzu_file" in /*) ;; *) uzu_file="$UZU_MODEL_DIR/$uzu_file" ;; esac
      uzu_args+=(--model-path "$uzu_file" --record-model-id "$mid")
    else
      uzu_args+=(--model-id "$mid")
    fi
    [ -n "$ctx" ] && uzu_args+=(--context-tokens "$ctx")
    if [ "$DRY_RUN" = 1 ]; then
      "$UZU_PYTHON" "$REPO/scripts/uzu_mac.py" "${uzu_args[@]}" --recipe "$recipe" \
        --task "$task" --runs "$runs" --pause "${UZU_PAUSE:-5}" --output "$OUT/${slug}.jsonl" --dry-run
      return
    fi
  fi
  if [ "$DRY_RUN" = 1 ]; then
    printf 'DRY-RUN existing arm: %s run --runtime %s --model-id %s --task %s --runs %s\n' "$YS" "$rt" "$mid" "$task" "$runs"
    return
  fi

  [ "$first" = 1 ] && first=0 || { log "cooldown ${cool}s"; sleep "$cool"; }

  if [ "$rt" = "core-ai" ]; then
    case "$task" in
      native-benchmark-*)
        # Engine-native synthetic benchmark = Apple's external llm-benchmark
        # binary (own timing, no --context-tokens; the caveat travels in the
        # wrapper's provenance note).
        "$REPO/scripts/coreai_mac_wrapper.sh" "$mid" "$task" "$runs" "$OUT" \
          || echo "FAIL core-ai $mid $task" >> "$OUT/FAILURES.txt"
        return ;;
    esac
    # Prompt tasks run through yardstick's CoreAIRuntime below, like every
    # other arm. A bundle that is not staged is SKIPPED with its reason —
    # "not yet measured" in the table, not four failed runs.
    coreai_bundle_ready "$mid" || return
  fi
  if [ "$rt" = "cactus" ]; then
    echo "SKIPPED $rt $mid $task reason=no-mac-arm" | tee -a "$OUT/SKIPPED.txt"
    return
  fi

  # Resume-safe: a JSONL that already holds >= runs records (x rounds so far)
  # is a finished cell for this round.
  if [ "${FORCE:-0}" != "1" ] && [ -f "$OUT/${slug}.jsonl" ] \
     && [ "$(grep -c '"task"' "$OUT/${slug}.jsonl" 2>/dev/null || echo 0)" -ge $((runs * round)) ]; then
    log "SKIP $slug round $round (already captured; FORCE=1 to redo)"
    return
  fi

  # asr-rtf-* cells (docs/asr-rtf-v1.md): LiteRT-LM's own ASR CLI through
  # scripts/asr_rtf_mac.py, not yardstick — same campaign dir, same record shape,
  # one JSONL per cell; the post-capture gate below reads decode metrics and does
  # not apply. validate_cells.py already requires backend= and file= here.
  if [ "$rt" = "uzu" ]; then
    if [ -n "$uzu_file" ] && [ ! -f "$uzu_file/config.json" ]; then
      echo "SKIPPED $rt $mid $task reason=uzu-own-export-not-staged ($uzu_file)" | tee -a "$OUT/SKIPPED.txt"
      return
    fi
    log "CELL $rt / $mid / $task recipe=$recipe runs=$runs round=$round (cold processes; smoke only)"
    "$UZU_PYTHON" "$REPO/scripts/uzu_mac.py" "${uzu_args[@]}" --recipe "$recipe" \
      --task "$task" --runs "$runs" --pause "${UZU_PAUSE:-5}" --timeout "${CELL_TIMEOUT:-600}" \
      --output "$OUT/${slug}.jsonl" --campaign-dir "$OUT" \
      || echo "FAIL $rt $mid $task round=$round" >> "$OUT/FAILURES.txt"
    # The driver validates schema, finite counters, total token budget and text.
    # These contended cold smoke rows are not admitted as warm dashboard timing.
    return
  fi
  case "$task" in asr-rtf-*)
    log "CELL $rt / $mid / $task backend=$backend runs=$runs round=$round ($(date +%H:%M:%S))"
    python3 "$REPO/scripts/asr_rtf_mac.py" --model-id "$mid" --task "$task" --backend "$backend" \
      --file "$(cell_opt file "" ${opts[@]+"${opts[@]}"})" --runs "$runs" \
      --output "$OUT/${slug}.jsonl" --campaign-dir "$OUT" \
      || echo "FAIL $rt $mid $task backend=$backend round=$round" >> "$OUT/FAILURES.txt"
    return ;;
  esac
  # vl-* cells (docs/vl-response-v1.md): LiteRT-LM's own CLI with an image in the
  # prompt, through scripts/vl_response_mac.py — same campaign dir, same record shape.
  case "$task" in vl-*)
    log "CELL $rt / $mid / $task backend=$backend runs=$runs round=$round ($(date +%H:%M:%S))"
    python3 "$REPO/scripts/vl_response_mac.py" --model-id "$mid" --task "$task" --backend "$backend" \
      --file "$(cell_opt file "" ${opts[@]+"${opts[@]}"})" --runs "$runs" \
      --output "$OUT/${slug}.jsonl" --campaign-dir "$OUT"
    case $? in
      0) ;;
      75) echo "SKIPPED $rt $mid $task backend=$backend reason=model-file-not-staged" | tee -a "$OUT/SKIPPED.txt" ;;
      *) echo "FAIL $rt $mid $task backend=$backend round=$round" >> "$OUT/FAILURES.txt" ;;
    esac
    return ;;
  esac
  # tts-rtf-* cells (docs/tts-rtf-v1.md): the model's public LiteRT reference
  # pipeline in its pinned venv, through scripts/tts_rtf_mac.py (runtime `litert`).
  case "$task" in tts-rtf-*)
    log "CELL $rt / $mid / $task runs=$runs round=$round ($(date +%H:%M:%S))"
    python3 "$REPO/scripts/tts_rtf_mac.py" --model-id "$mid" --task "$task" \
      --file "$(cell_opt file "" ${opts[@]+"${opts[@]}"})" --runs "$runs" \
      --output "$OUT/${slug}.jsonl" --campaign-dir "$OUT" \
      || echo "FAIL $rt $mid $task round=$round" >> "$OUT/FAILURES.txt"
    return ;;
  esac

  local extra=() task_arg="$task"
  [ -n "$ctx" ] && extra+=(--context-tokens "$ctx")
  [ -n "$maxtok" ] && extra+=(--max-tokens "$maxtok")
  # backend= on a mac litert-lm row selects the engine's compute backend
  # (cpu rows stamp runtime litert-lm-cpu — a separate arm, as on Android).
  if [ -n "$backend" ]; then
    if [ "$rt" = "litert-lm" ]; then
      extra+=(--litert-backend "$backend")
    else
      echo "SKIPPED $rt $mid $task reason=backend-option-is-litert-lm-only" | tee -a "$OUT/SKIPPED.txt"
      return
    fi
  fi
  case "$task" in native-benchmark-*)
    # The native benchmark runs INSTEAD of a task (yardstick resolves --task
    # before the native branch, so it must still name a real task id).
    extra+=(--litert-native-benchmark "${task#native-benchmark-}")
    task_arg="short-chat" ;;
  esac

  log "CELL $rt / $mid / $task${backend:+ backend=$backend}${ctx:+ ctx=$ctx} runs=$runs round=$round ($(date +%H:%M:%S))"
  if ! run_ys_cell; then
    echo "FAIL $rt $mid $task${backend:+ backend=$backend}${ctx:+ ctx=$ctx} round=$round" >> "$OUT/FAILURES.txt"
  fi
  # Post-capture gate (scripts/cell_gate.py): a HOT or wide-spread capture is
  # quarantined (.jsonl.attempt1 — kept in raw, outside build_summary's
  # *.jsonl glob) and the cell re-runs ONCE after a real cooldown. SHORT is
  # never retried here — that is a failure, and failed runs stay.
  if [ -f "$OUT/${slug}.jsonl" ] && [ "${GATE_RETRY:-1}" = "1" ]; then
    gate="$(python3 "$REPO/scripts/cell_gate.py" --runs "$runs" --jsonl "$OUT/${slug}.jsonl")" || true
    case "$gate" in DEGENERATE*)
      # A repetition loop reproduces on re-run: flag it, keep the capture,
      # never read its rate as a speed (cell_gate.py; the 2026-09-08 finding).
      echo "GATE_FAIL $rt $mid $task verdict='$gate' (output is a repetition loop — not retried; the rate is not a measurement)" \
        | tee -a "$OUT/FLAGGED.txt" ;;
    esac
    case "$gate" in HOT*|SPREAD*|DEAD*|COLLAPSE*)
      log "gate: $gate — quarantine + cooldown ${GATE_COOLDOWN:-180}s, re-run once"
      mv "$OUT/${slug}.jsonl" "$OUT/${slug}.jsonl.attempt1"
      sleep "${GATE_COOLDOWN:-180}"
      run_ys_cell || echo "FAIL $rt $mid $task (gate retry)" >> "$OUT/FAILURES.txt"
      gate2="$(python3 "$REPO/scripts/cell_gate.py" --runs "$runs" --jsonl "$OUT/${slug}.jsonl" 2>/dev/null)" || true
      case "$gate2" in HOT*|SPREAD*|DEAD*|COLLAPSE*)
        echo "GATE_FAIL $rt $mid $task first='$gate' retry='$gate2' (retry kept; ⚠ downstream)" \
          | tee -a "$OUT/FLAGGED.txt" ;;
      esac ;;
    esac
  fi
}

cmd_run(){
  local cells_file="${1:?usage: run <cells-file>}"
  case "${2:-}" in
    --dry-run) DRY_RUN=1 ;;
    "") ;;
    *) echo "unknown option: $2" >&2; exit 1 ;;
  esac
  python3 "$REPO/scripts/validate_cells.py" "$cells_file" || exit 1
  if [ "$DRY_RUN" = 1 ]; then
    local first=1 dry_line
    while IFS= read -r dry_line; do run_cell 1 "$dry_line" || return; done < <(cells_for mac "$cells_file")
    return
  fi
  check_binary
  guard
  mkdir -p "$OUT"
  { sw_vers; date "+session start %F %T"; echo "cells: $cells_file"; } >> "$OUT/session_provenance.txt"

  local -a cell_lines=()
  local line
  while IFS= read -r line; do cell_lines+=("$line"); done \
    < <(cells_for mac "$cells_file" 2> >(tee -a "$OUT/SKIPPED.txt" >&2))

  # ROUNDS=N (default 1): the whole cell list N times, one launch of `runs`
  # runs per cell per round, order reversed on even rounds (ROUND_ALTERNATE=1,
  # the default) so a slow drift hits every cell from both sides — the paired
  # A/B shape of litertlm-convert/ynnpack_work/bench_ab.py, on the matrix
  # runner. Records accumulate in the cell's JSONL across rounds; the
  # per-launch gate is off in round mode (its quarantine would move a file
  # holding earlier rounds) and the spread is judged over the rounds afterwards.
  local rounds="${ROUNDS:-1}" alternate="${ROUND_ALTERNATE:-1}"
  if [ "$rounds" -gt 1 ]; then
    log "ROUNDS=$rounds (ROUND_ALTERNATE=$alternate): post-capture gate off, spread judged across rounds"
    echo "rounds: $rounds alternate=$alternate runs-per-launch=$DEFAULT_RUNS gate=off" >> "$OUT/session_provenance.txt"
    GATE_RETRY=0
  fi
  local first=1 round k idx n=${#cell_lines[@]}
  for round in $(seq 1 "$rounds"); do
    if [ "$rounds" -gt 1 ]; then
      log "ROUND $round/$rounds ($(date +%H:%M:%S), $(uptime | sed 's/.*load/load/'))"
      # Host-idleness audit trail (the ynnpack A/B logged the same): load and
      # the top CPU consumers at every round start, next to the records.
      { echo "== round $round $(date '+%F %T')"; uptime; ps -Ao pcpu,pid,comm -r | head -5; } >> "$OUT/host_load.log"
    fi
    for ((k = 0; k < n; k++)); do
      if [ "$rounds" -gt 1 ] && [ "$alternate" = 1 ] && [ $((round % 2)) -eq 0 ]; then
        idx=$((n - 1 - k))
      else
        idx=$k
      fi
      run_cell "$round" "${cell_lines[$idx]}"
    done
  done

  log "campaign dir: $OUT"
  [ -f "$OUT/FAILURES.txt" ] && { echo "failures (failed-runs-stay — keep in the table):"; cat "$OUT/FAILURES.txt"; }
  [ -f "$OUT/SKIPPED.txt" ] && { echo "skipped:"; cat "$OUT/SKIPPED.txt"; }
  exit 0
}

case "${1:-}" in
  run) shift; cmd_run "$@" ;;
  *) sed -n '2,18p' "$0"; exit 1 ;;
esac
