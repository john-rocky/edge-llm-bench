#!/bin/zsh
# Driver, 2026-09-18: the prebuilt Metal dylib from LiteRT-LM main 1dadd00c (LiteRT 0da36b31, which includes the fused
# FlashAttention-2 prefill kernel 89116780) vs the 09-17 prebuilt from 4453b286 (LiteRT 1901301f, one commit before it),
# same litert_lm_advanced_main (v0.17.0 tag build, sha256 56137e57…), Fengwu's two benchmark configs.
# Bundles: the published p1024 files (11 flags / 9 flags, 2026-09-11) + today's 12-flag exports (the 11-flag command +
# --use_sdpa_composite_for_prefill=True, litert-torch main 731ef0a; chain_p1024_12flags.sh) + the flag-only control "11n" (the
# 11-flag command at litert-torch 1e2d37f = the same exporter drift without the prefill composite; chain_p1024_11flags_1e2d37f.sh).
#   run-1dadd00c = new dylib (sha256 49df4fd5…), run-4453b286 = 09-17 dylib (dcd3c3ef…). GPU-serial, one process at a time.
# DRY=1 lists the legs without running anything.
set -u
S=${S:?}
LEG=$S/scripts/leg.sh
export LEG_OUT=$S/legs; mkdir -p $LEG_OUT; export LEG_RUNLOG=$LEG_OUT/runlog.txt
NEW=$S/run-1dadd00c; CTL=$S/run-4453b286; M=$S/models
DRY=${DRY:-0}
NLEG=0; NFAIL=0
leg() { if [ "$DRY" = 1 ]; then echo "DRY leg: dylib=$(basename $1) bundle=$(basename $(dirname $2)) label=$3 mode=$4"; else NLEG=$((NLEG+1)); $LEG "$@" || NFAIL=$((NFAIL+1)); fi }
echo "=== start $(date '+%F %T')  load=$(uptime | sed 's/.*load averages: //')"
OTHER=$(ps aux | grep -E "yardstick|litert_lm|llm-bench|llama|gsm8k|litert-lm|mlx|python|bazel" | grep -v -E "grep|claude|run_all|leg.sh|orchestrate" | awk '$3>20{print "   other proc (>20% cpu):", $2, $3, $11}')
if [ -n "$OTHER" ]; then echo "$OTHER"; if [ "${FORCE:-0}" != 1 ] && [ "$DRY" != 1 ]; then echo "ABORT: another measurement is using this host (paired A/B rule) — re-run when it is idle, or FORCE=1"; exit 5; fi; fi
# --- (0) compatibility leg: the published 11-flag 0.6B bundle on the NEW dylib through the v0.17.0-tag CLI; abort if it fails
leg $NEW $M/p1024_06b_11flags/model.litertlm new_06b_11 run
if [ "$DRY" != 1 ]; then
  L=$LEG_OUT/new_06b_11_run.log
  if ! grep -q 'EXIT_CODE=0' "$L" || [ "$(grep -c 'Shape mismatch' "$L")" != 0 ]; then
    echo "ABORT $(date '+%F %T'): the first leg failed (exit code or shape mismatch) — read $L before running anything else"; exit 3
  fi
  grep -q -i -E 'railway|1879' "$L" || echo "WARN: the first leg's answer does not mention the railway/1879 — read the text in $L"
fi
# --- (1) text runs on the new dylib (996-token passage + /no_think): the two 12-flag exports and the other published files
leg $NEW $M/p1024_06b_12flags/model.litertlm new_06b_12 run
leg $NEW $M/p1024_06b_11flags_1e2d37f/model.litertlm new_06b_11n run
leg $NEW $M/p1024_06b_9flags/model.litertlm  new_06b_9  run
leg $NEW $M/p1024_4b_12flags/model.litertlm  new_4b_12  run
leg $NEW $M/p1024_4b_11flags/model.litertlm  new_4b_11  run
leg $NEW $M/p1024_4b_11flags_1e2d37f/model.litertlm new_4b_11n run
leg $NEW $M/p1024_4b_9flags/model.litertlm   new_4b_9   run
# --- (1b) informational, 0.6B 12-flag export on the new dylib: a verbose-log run (--min_log_severity=0) and a per-op profiling
#          run (--enable_profiling=true), to look for a runtime line that names the prefill SDPA kernel (the default log has none)
leg $NEW $M/p1024_06b_12flags/model.litertlm new_06b_12 runv
leg $NEW $M/p1024_06b_12flags/model.litertlm new_06b_12 runp
# --- (2) Fengwu config 2 (1024/256): new dylib × 6 bundles, 09-17 dylib × the 4 published bundles (same-session control); A then B
for P in A B; do
  leg $NEW $M/p1024_06b_12flags/model.litertlm new_06b_12_$P b1k
  leg $NEW $M/p1024_06b_11flags/model.litertlm new_06b_11_$P b1k
  leg $CTL $M/p1024_06b_11flags/model.litertlm ctl_06b_11_$P b1k
  leg $NEW $M/p1024_06b_11flags_1e2d37f/model.litertlm new_06b_11n_$P b1k
  leg $NEW $M/p1024_06b_9flags/model.litertlm  new_06b_9_$P  b1k
  leg $CTL $M/p1024_06b_9flags/model.litertlm  ctl_06b_9_$P  b1k
  leg $NEW $M/p1024_4b_12flags/model.litertlm  new_4b_12_$P  b1k
  leg $NEW $M/p1024_4b_11flags/model.litertlm  new_4b_11_$P  b1k
  leg $CTL $M/p1024_4b_11flags/model.litertlm  ctl_4b_11_$P  b1k
  leg $NEW $M/p1024_4b_11flags_1e2d37f/model.litertlm new_4b_11n_$P b1k
  leg $NEW $M/p1024_4b_9flags/model.litertlm   new_4b_9_$P   b1k
  leg $CTL $M/p1024_4b_9flags/model.litertlm   ctl_4b_9_$P   b1k
done
# --- (3) Fengwu config 1 (31744/256, --max_num_tokens=32768): new dylib × 6 bundles A/B; 09-17 dylib × 11-flag and 9-flag A/B
for P in A B; do
  leg $NEW $M/p1024_06b_12flags/model.litertlm new_06b_12_$P b31k
  leg $NEW $M/p1024_06b_11flags/model.litertlm new_06b_11_$P b31k
  leg $CTL $M/p1024_06b_11flags/model.litertlm ctl_06b_11_$P b31k
  leg $NEW $M/p1024_06b_11flags_1e2d37f/model.litertlm new_06b_11n_$P b31k
  leg $NEW $M/p1024_06b_9flags/model.litertlm  new_06b_9_$P  b31k
  leg $CTL $M/p1024_06b_9flags/model.litertlm  ctl_06b_9_$P  b31k
  leg $NEW $M/p1024_4b_12flags/model.litertlm  new_4b_12_$P  b31k
  leg $NEW $M/p1024_4b_11flags/model.litertlm  new_4b_11_$P  b31k
  leg $CTL $M/p1024_4b_11flags/model.litertlm  ctl_4b_11_$P  b31k
  leg $NEW $M/p1024_4b_11flags_1e2d37f/model.litertlm new_4b_11n_$P b31k
  leg $NEW $M/p1024_4b_9flags/model.litertlm   new_4b_9_$P   b31k
  leg $CTL $M/p1024_4b_9flags/model.litertlm   ctl_4b_9_$P   b31k
done
echo "=== benchmarks done $(date '+%F %T')  load=$(uptime | sed 's/.*load averages: //')"
# --- (4) 8Q gates on the new dylib: the two 12-flag exports first, then the two published 11-flag files
PY=$HOME/venvs/lt094dev/bin/python3; [ -x "$PY" ] || PY=python3
for pair in new_06b_12:p1024_06b_12flags new_4b_12:p1024_4b_12flags new_06b_11:p1024_06b_11flags new_4b_11:p1024_4b_11flags; do
  L=${pair%%:*}; B=${pair##*:}
  if [ "$DRY" = 1 ]; then echo "DRY gate: label=$L bundle=$B dylib=$(basename $NEW)"; continue; fi
  echo "### CMD: python3 gate8q_adv.py --run $NEW --label $L --json $S/legs/gate8q_${L}.json $M/$B/model.litertlm  # $(date '+%F %T')" >> $LEG_RUNLOG
  $PY $S/scripts/gate8q_adv.py --run $NEW --label $L --json $S/legs/gate8q_${L}.json $M/$B/model.litertlm 2>&1 | tail -10
done
# --- (5) the 12-flag exports on the 09-17 dylib (his stated reason for stopping 4453b286 short of the FA2 kernel: the GQA
#         query-packing mismatch): text run, then one 31,744 process per model only if the text run exited 0 with 0 mismatches
for pair in ctl_06b_12:p1024_06b_12flags ctl_4b_12:p1024_4b_12flags; do
  L=${pair%%:*}; B=${pair##*:}
  leg $CTL $M/$B/model.litertlm $L run
  if [ "$DRY" = 1 ] || { grep -q 'EXIT_CODE=0' $LEG_OUT/${L}_run.log && [ "$(grep -c 'Shape mismatch' $LEG_OUT/${L}_run.log)" = 0 ]; }; then
    leg $CTL $M/$B/model.litertlm ${L}_A b31k
  else
    echo "   skip ${L}_A b31k: the text run did not exit 0 with 0 mismatches (recorded as the answer to 'does the new export need the new prebuilt')"
  fi
done
echo "=== legs run: $NLEG, legs with exit!=0 or shape mismatch>0: $NFAIL, timed out (EXIT_CODE=124): $(find $LEG_OUT -name '*.log' -exec grep -l 'EXIT_CODE=124' {} + 2>/dev/null | wc -l | tr -d ' ')"
echo "=== stray files beside the bundles (must be none):"; find $M -type f ! -name model.litertlm | sed 's/^/   /'
[ "$DRY" = 1 ] || $PY $S/scripts/summarize.py $LEG_OUT > $LEG_OUT/SUMMARY_benchmarks.txt 2>&1
echo "=== all done $(date '+%F %T')  load=$(uptime | sed 's/.*load averages: //')"
