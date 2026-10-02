#!/usr/bin/env bash
# One command for the long-context column's day-0 re-measure on a new LiteRT-LM tag:
# the same cells as the stored sitting, into a fresh campaign, then the regression
# verdicts (anchor-normalized, context_tokens in the key) and the allocation-ladder
# table against the stored sitting. docs/day0-npu-dynamic-kv-v1.md §① says when to
# fire it and how to read the two outputs.
#
#   scripts/longctx_day0.sh <leg> <tag> [--check-only] [--baseline <campaign-substr>]
#
#   leg   mac | s26-gemmae2b | s26-qwen06 | s26-gemmae4b | s26-qwen17 | s26-qwen4 | s26-gpu-retake
#   tag   the LiteRT-LM tag the staged binaries carry (e.g. v0.18.0); stamped into the
#         campaign name and the regression report, checked against the staged build
#
# The Mac leg is one sitting (8 rounds × 2 runs, ≈4 h on 2026-09-18); the S26 leg is
# five sittings of one model each plus the GPU re-take (as stored), ≈2–3 h each —
# one leg per invocation, never two drivers on one device. Exit codes: 2 = usage /
# precondition, 3 = device busy (from the runner), 1 = REGRESSION somewhere, 0 = clean.
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 2
LEG="${1:-}"; TAG="${2:-}"; shift 2 2>/dev/null || { sed -n '2,20p' "$0"; exit 2; }
CHECK_ONLY=0; BASELINE=""
while [ $# -gt 0 ]; do
  case "$1" in
    --check-only) CHECK_ONLY=1; shift;;
    --baseline) BASELINE="$2"; shift 2;;
    *) echo "unknown option $1" >&2; exit 2;;
  esac
done
[ -n "$TAG" ] || { sed -n '2,20p' "$0"; exit 2; }

# leg -> cells file, stored baseline sitting, platform, runner env (as the cells
# files' own headers prescribe; the baselines are the admitted sittings of
# docs/dashboard-cells-v1.md "Long-context column")
case "$LEG" in
  mac)            CELLS=matrices/dashboard-longctx-v1.cells;                   BASE=2026-09-18-dashboard-longctx-v1-m4max-mac;                 PLATFORM=mac;;
  s26-gemmae2b)   CELLS=matrices/dashboard-longctx-v1-android-s26-gemmae2b.cells; BASE=2026-09-20-dashboard-longctx-v1-s26-android-gemmae2b;   PLATFORM=android;;
  s26-qwen06)     CELLS=matrices/dashboard-longctx-v1-android-s26-qwen06.cells;   BASE=2026-09-20-dashboard-longctx-v1-s26-android-qwen06;     PLATFORM=android;;
  s26-gemmae4b)   CELLS=matrices/dashboard-longctx-v1-android-s26-gemmae4b.cells; BASE=2026-09-21-dashboard-longctx-v1-s26-android-gemmae4b;   PLATFORM=android;;
  s26-qwen17)     CELLS=matrices/dashboard-longctx-v1-android-s26-qwen17.cells;   BASE=2026-09-23-dashboard-longctx-v1-s26-android-qwen17-retake; PLATFORM=android;;
  s26-qwen4)      CELLS=matrices/dashboard-longctx-v1-android-s26-qwen4.cells;    BASE=2026-09-24-dashboard-longctx-v1-s26-android-qwen4;      PLATFORM=android;;
  s26-gpu-retake) CELLS=matrices/dashboard-longctx-v1-android-s26-gpu-retake.cells; BASE=2026-09-24-dashboard-longctx-v1-s26-android-gpu-retake; PLATFORM=android;;
  *) echo "unknown leg '$LEG'" >&2; sed -n '8,10p' "$0"; exit 2;;
esac
[ -n "$BASELINE" ] && BASE="$BASELINE"
[ -f "$CELLS" ] || { echo "cells file missing: $CELLS" >&2; exit 2; }
[ -d "results/raw/$BASE" ] || { echo "baseline campaign dir missing: results/raw/$BASE" >&2; exit 2; }
CAMPAIGN="$(date +%F)-dashboard-longctx-v1-${LEG}-day0-${TAG}"
[ -e "results/raw/$CAMPAIGN" ] && { echo "campaign dir exists: results/raw/$CAMPAIGN (same-day retake: pass a different tag label or move it)" >&2; exit 2; }

echo "leg=$LEG tag=$TAG cells=$CELLS baseline=$BASE campaign=$CAMPAIGN"
fail=0
# --- preconditions: the staged engine IS the tag (the witness stamps whatever runs;
# a stale build would produce a correct-looking ladder under the wrong name)
if [ "$PLATFORM" = mac ]; then
  staged=$(grep -m1 -oE 'LITERTLM_TAG:-[^}]+' ios/BenchmarkApp/scripts/bootstrap.sh | sed 's/LITERTLM_TAG:-//')
  if [ "$staged" = "$TAG" ]; then echo "ok    bootstrap.sh LITERTLM_TAG default = $TAG"
  else echo "FAIL  bootstrap.sh LITERTLM_TAG default is '$staged', not $TAG — bump it, rerun bootstrap.sh + scripts/build_yardstick_mac.sh (docs/OPERATIONS.md 'an engine shipped a release'; wipe .build/dd-mac when the vendored tag changes)"; fail=1; fi
  if pgrep -f 'bench_matrix_mac.sh|dashboard_job.py' >/dev/null; then echo "FAIL  another Mac runner / dashboard job is running"; fail=1; else echo "ok    no other Mac runner"; fi
else
  if [ -f "android/bin/$TAG/litert_lm_advanced_main" ]; then echo "ok    android/bin/$TAG/litert_lm_advanced_main staged (push per android/README.md; the runner hash-pins what it runs)"
  else echo "FAIL  android/bin/$TAG/litert_lm_advanced_main missing — LITERTLM_TAG=$TAG android/scripts/build_litert_lm_main.sh, then push"; fail=1; fi
  if grep -q "\"$TAG\"" android/engine-pins.json; then echo "ok    android/engine-pins.json has a $TAG entry"
  else echo "FAIL  android/engine-pins.json has no $TAG entry (the runner refuses an unpinned binary; add the observed sha256s)"; fail=1; fi
  if [ -f logs/dashboard-job/ledger.tsv ]; then echo "info  last dashboard-job line: $(tail -1 logs/dashboard-job/ledger.tsv | cut -f1-5)"; fi
  if pgrep -f 'run_campaign.py|dashboard_job.py' >/dev/null; then echo "FAIL  another Android driver / dashboard job is running (the night job holds the S26 02:00–06:30 on its day)"; fail=1; else echo "ok    no other Android driver on this host"; fi
fi
python3 scripts/validate_cells.py "$CELLS" >/dev/null 2>&1 && echo "ok    cells validate" || { echo "FAIL  validate_cells.py $CELLS"; fail=1; }
[ $fail -eq 0 ] || { echo "preconditions failed — nothing measured"; exit 2; }
[ $CHECK_ONLY -eq 1 ] && { echo "check-only: would run the capture below"; }

# --- capture, exactly as the stored sitting (its cells header is the protocol)
if [ "$PLATFORM" = mac ]; then
  echo "+ ROUNDS=8 RUNS=2 BASE_COOLDOWN=10 CAMPAIGN=$CAMPAIGN scripts/bench_matrix_mac.sh run $CELLS"
  [ $CHECK_ONLY -eq 1 ] || ROUNDS=8 RUNS=2 BASE_COOLDOWN=10 CAMPAIGN="$CAMPAIGN" scripts/bench_matrix_mac.sh run "$CELLS"
else
  echo "+ ROUNDS=8 COOLDOWN=30 THERMAL_WAIT=600 BENCH_CPU_MASK= BENCH_ANDROID_SERIAL=RFGL80R6A6H CAMPAIGN=$CAMPAIGN python3 android/bench/run_campaign.py $CELLS"
  [ $CHECK_ONLY -eq 1 ] || ROUNDS=8 COOLDOWN=30 THERMAL_WAIT=600 BENCH_CPU_MASK= BENCH_ANDROID_SERIAL=RFGL80R6A6H CAMPAIGN="$CAMPAIGN" python3 android/bench/run_campaign.py "$CELLS"
fi
rc=$?
[ $CHECK_ONLY -eq 1 ] && exit 0
[ $rc -eq 3 ] && { echo "device busy (rc=3) — nothing measured"; exit 3; }
[ -d "results/raw/$CAMPAIGN" ] || { echo "no campaign dir after the run (rc=$rc) — nothing to diff"; exit 2; }

# --- verdicts + ladder (both rebuild results/summary from this checkout's disk; commit
# the summary only as rebuilt from the git index — CLAUDE.md)
python3 scripts/regression_report.py --engine litert-lm --version "$TAG" device \
  --baseline "campaign:$BASE" --candidate "campaign:$CAMPAIGN" --anchors "$CELLS" \
  --engine-under-test litert-lm
vrc=$?
python3 scripts/longctx_ladder_diff.py --baseline "campaign:$BASE" --candidate "campaign:$CAMPAIGN" \
  --no-rebuild --csv-out "results/raw/$CAMPAIGN/ladder-vs-$BASE.csv" | tee "results/raw/$CAMPAIGN/ladder-vs-$BASE.md"
echo "ladder: results/raw/$CAMPAIGN/ladder-vs-$BASE.md ; verdicts: results/regression-reports/$(date +%F)-litert-lm-$TAG/"
exit $vrc
