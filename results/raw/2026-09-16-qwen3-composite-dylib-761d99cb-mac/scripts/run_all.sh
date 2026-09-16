#!/bin/zsh
# Driver, 2026-09-16: the 761d99cb dylib cannot be built from OSS (see FINDINGS §15), so this measures what the
# public runtime can do today with Fengwu's two benchmark configs, all on litert_lm_advanced_main (v0.17.0 tag build):
#   (1) release v0.17.0 dylib: text run on all 4 bundles (shape-mismatch count + output), b1k ×2 and b31k ×2 on the
#       two 9-flag bundles (valid numbers), b1k ×1 on the two 11-flag bundles (void: wrong output, kept for the record);
#   (2) litert_prebuilts.zip "latest" (2026-08-13) macOS dylib: text run on the two 11-flag bundles.
set -u
LEG=$HOME/code/litertlm-convert/qwen3_gpuopt_work/logs/dylib_761d99cb/leg.sh
S=/private/tmp/claude-501/-Users-majimadaisuke-code-litertlm-convert/7ffdfeee-f1e0-4c0c-b6d2-9072c447fa05/scratchpad
export LEG_OUT=$S/legs; mkdir -p $LEG_OUT; export LEG_RUNLOG=$LEG_OUT/runlog.txt
REL=$S/run-release; PRE=$S/run-prebuilt0813; M=$S/models
echo "=== start $(date '+%F %T')  load=$(uptime | sed 's/.*load averages: //')"
ps aux | grep -E "yardstick|litert_lm|llm-bench|gsm8k|litert-lm|mlx" | grep -v -E "grep|claude|run_all|leg.sh" | awk '{print "   other proc:", $2, $3, $11}' 
# --- (1a) text runs, release dylib
$LEG $REL $M/p1024_06b_11flags/model.litertlm rel_06b_11 run
$LEG $REL $M/p1024_06b_9flags/model.litertlm  rel_06b_9  run
$LEG $REL $M/p1024_4b_11flags/model.litertlm  rel_4b_11  run
$LEG $REL $M/p1024_4b_9flags/model.litertlm   rel_4b_9   run
# --- (2) text runs, 08-13 public prebuilt dylib, composite bundles
$LEG $PRE $M/p1024_06b_11flags/model.litertlm pre0813_06b_11 run
$LEG $PRE $M/p1024_4b_11flags/model.litertlm  pre0813_4b_11  run
# --- (1b) Fengwu config 2 (1024/256), release dylib
$LEG $REL $M/p1024_06b_9flags/model.litertlm  rel_06b_9_A  b1k
$LEG $REL $M/p1024_4b_9flags/model.litertlm   rel_4b_9_A   b1k
$LEG $REL $M/p1024_06b_11flags/model.litertlm rel_06b_11_void b1k
$LEG $REL $M/p1024_4b_11flags/model.litertlm  rel_4b_11_void  b1k
$LEG $REL $M/p1024_06b_9flags/model.litertlm  rel_06b_9_B  b1k
$LEG $REL $M/p1024_4b_9flags/model.litertlm   rel_4b_9_B   b1k
# --- (1c) Fengwu config 1 (31744/256), release dylib, 9-flag bundles ×2
$LEG $REL $M/p1024_06b_9flags/model.litertlm  rel_06b_9_A  b31k
$LEG $REL $M/p1024_4b_9flags/model.litertlm   rel_4b_9_A   b31k
$LEG $REL $M/p1024_06b_9flags/model.litertlm  rel_06b_9_B  b31k
$LEG $REL $M/p1024_4b_9flags/model.litertlm   rel_4b_9_B   b31k
echo "=== done $(date '+%F %T')  load=$(uptime | sed 's/.*load averages: //')"
