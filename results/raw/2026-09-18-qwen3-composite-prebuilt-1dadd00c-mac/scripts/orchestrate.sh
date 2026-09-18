#!/bin/zsh
# 2026-09-18 one-shot orchestration for the host gap (after user GO): 12-flag exports + inventories -> APFS clones into the
# run tree -> sha256 of everything -> run_all.sh (compatibility leg, text runs, Fengwu's two configs A/B, 8Q gates).
# Idempotent: exports are skipped when their bundles already exist. Usage: (S=<scratchpad> nohup ./orchestrate.sh > <S>/legs/orchestrate.log 2>&1 &)
set -u
S=${S:?}; W=$HOME/code/litertlm-convert/qwen3_gpuopt_work
mkdir -p $S/legs
echo "=== orchestrate start $(date '+%F %T')  load=$(uptime | sed 's/.*load averages: //')"
if [ ! -s $W/out/p1024_06b_12flags/model.litertlm ] || [ ! -s $W/out/p1024_4b_12flags/model.litertlm ]; then
  echo "### CMD: (cd $W && ./chain_p1024_12flags.sh > logs/chain_p1024_12flags_driver.txt 2>&1)  # $(date '+%F %T')" >> $S/legs/runlog.txt
  (cd $W && ./chain_p1024_12flags.sh > logs/chain_p1024_12flags_driver.txt 2>&1)
  echo "--- chain driver tail:"; tail -30 $W/logs/chain_p1024_12flags_driver.txt
  [ "$(grep -c '^   exit 0 ' $W/logs/chain_p1024_12flags_driver.txt)" = 2 ] || { echo "ABORT: an export exited non-zero (see $W/logs/chain_p1024_12flags_driver.txt)"; exit 4; }
else
  echo "exports present, skipping chain"
fi
# hard gates (exit 6): the flag took effect (prefill sdpa composites: 12-flag = N, 11-flag = 0), the weights and the other
# composites are identical, and the remaining op differences are printed. Pairs: 12-flag vs the published file; 12-flag vs the
# flag-only control (11 flags at 1e2d37f); the control vs the published file (= the exporter drift alone).
for m in 06b:28 4b:36; do b=${m%%:*}; n=${m##*:}
  echo "--- gate $b: 12flags(731ef0a) vs published 11flags(6d4c622)";        python3 $S/scripts/inventory_gate.py $W/logs/ops_p1024_${b}_12flags.txt $W/logs/ops_p1024_${b}_11flags.txt $n $n 0 || exit 6
  echo "--- gate $b: 12flags(731ef0a) vs 11flags(1e2d37f) control";          python3 $S/scripts/inventory_gate.py $W/logs/ops_p1024_${b}_12flags.txt $W/logs/ops_p1024_${b}_11flags_1e2d37f.txt $n $n 0 || exit 6
  echo "--- gate $b: 11flags(1e2d37f) control vs published 11flags(6d4c622)"; python3 $S/scripts/inventory_gate.py $W/logs/ops_p1024_${b}_11flags_1e2d37f.txt $W/logs/ops_p1024_${b}_11flags.txt $n 0 0 || exit 6
done
for b in p1024_06b_12flags p1024_4b_12flags p1024_06b_11flags_1e2d37f p1024_4b_11flags_1e2d37f; do
  [ -s $W/out/$b/model.litertlm ] || { echo "ABORT: $W/out/$b/model.litertlm missing"; exit 4; }
  mkdir -p $S/models/$b; [ -s $S/models/$b/model.litertlm ] || cp -c $W/out/$b/model.litertlm $S/models/$b/model.litertlm
done
(cd $S && shasum -a 256 models/*/model.litertlm run-*/* > $S/legs/sha256.txt && stat -f '%z %N' models/*/model.litertlm run-*/libLiteRtMetalAccelerator.dylib >> $S/legs/sha256.txt)
$S/scripts/run_all.sh
echo "=== orchestrate done $(date '+%F %T')  load=$(uptime | sed 's/.*load averages: //')"
