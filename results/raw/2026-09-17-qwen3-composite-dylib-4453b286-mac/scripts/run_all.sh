#!/bin/zsh
# Driver, 2026-09-17: the prebuilt Metal dylib from LiteRT-LM main 4453b286 (PR #3605, LiteRT 1901301f) vs the v0.17.0
# release dylib, same litert_lm_advanced_main (v0.17.0 tag build), same 4 bundles, Fengwu's two benchmark configs.
#   run-4453b286 = new dylib (sha256 dcd3c3ef…), run-release = v0.17.0 dylib (ac988ae2…). GPU-serial, one process at a time.
set -u
S=${S:?}
LEG=$S/scripts/leg.sh
export LEG_OUT=$S/legs; mkdir -p $LEG_OUT; export LEG_RUNLOG=$LEG_OUT/runlog.txt
NEW=$S/run-4453b286; REL=$S/run-release; M=$S/models
echo "=== start $(date '+%F %T')  load=$(uptime | sed 's/.*load averages: //')"
ps aux | grep -E "yardstick|litert_lm|llm-bench|gsm8k|litert-lm|mlx|python|bazel" | grep -v -E "grep|claude|run_all|leg.sh" | awk '$3>20{print "   other proc (>20% cpu):", $2, $3, $11}'
# --- (1) text runs, new dylib (new_06b_11 already done at 04:56)
$LEG $NEW $M/p1024_06b_9flags/model.litertlm  new_06b_9  run
$LEG $NEW $M/p1024_4b_11flags/model.litertlm  new_4b_11  run
$LEG $NEW $M/p1024_4b_9flags/model.litertlm   new_4b_9   run
# --- (2) Fengwu config 2 (1024/256): new dylib ×4 bundles, release ×2 9-flag bundles (today's control); A then B
for P in A B; do
  $LEG $NEW $M/p1024_06b_11flags/model.litertlm new_06b_11_$P b1k
  $LEG $NEW $M/p1024_06b_9flags/model.litertlm  new_06b_9_$P  b1k
  $LEG $REL $M/p1024_06b_9flags/model.litertlm  rel_06b_9_$P  b1k
  $LEG $NEW $M/p1024_4b_11flags/model.litertlm  new_4b_11_$P  b1k
  $LEG $NEW $M/p1024_4b_9flags/model.litertlm   new_4b_9_$P   b1k
  $LEG $REL $M/p1024_4b_9flags/model.litertlm   rel_4b_9_$P   b1k
done
# --- (3) Fengwu config 1 (31744/256): new dylib ×4 bundles A/B, release ×2 9-flag bundles ×1 (control)
$LEG $NEW $M/p1024_06b_11flags/model.litertlm new_06b_11_A b31k
$LEG $NEW $M/p1024_06b_9flags/model.litertlm  new_06b_9_A  b31k
$LEG $REL $M/p1024_06b_9flags/model.litertlm  rel_06b_9_A  b31k
$LEG $NEW $M/p1024_4b_11flags/model.litertlm  new_4b_11_A  b31k
$LEG $NEW $M/p1024_4b_9flags/model.litertlm   new_4b_9_A   b31k
$LEG $REL $M/p1024_4b_9flags/model.litertlm   rel_4b_9_A   b31k
$LEG $NEW $M/p1024_06b_11flags/model.litertlm new_06b_11_B b31k
$LEG $NEW $M/p1024_06b_9flags/model.litertlm  new_06b_9_B  b31k
$LEG $NEW $M/p1024_4b_11flags/model.litertlm  new_4b_11_B  b31k
$LEG $NEW $M/p1024_4b_9flags/model.litertlm   new_4b_9_B   b31k
echo "=== benchmarks done $(date '+%F %T')  load=$(uptime | sed 's/.*load averages: //')"
# --- (4) 8Q gates, new dylib: the two composite bundles first, then the two without the composites
PY=$HOME/venvs/lt094dev/bin/python3; [ -x "$PY" ] || PY=python3
for pair in new_06b_11:p1024_06b_11flags new_4b_11:p1024_4b_11flags new_06b_9:p1024_06b_9flags new_4b_9:p1024_4b_9flags; do
  L=${pair%%:*}; B=${pair##*:}
  echo "### CMD: python3 gate8q_adv.py --run $NEW --label $L --json $S/legs/gate8q_${L}.json $M/$B/model.litertlm  # $(date '+%F %T')" >> $LEG_RUNLOG
  $PY $S/scripts/gate8q_adv.py --run $NEW --label $L --json $S/legs/gate8q_${L}.json $M/$B/model.litertlm 2>&1 | tail -10
done
echo "=== all done $(date '+%F %T')  load=$(uptime | sed 's/.*load averages: //')"
