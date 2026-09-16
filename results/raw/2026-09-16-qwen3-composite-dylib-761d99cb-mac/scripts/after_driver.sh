#!/bin/zsh
# Waits for run_all.sh (pid $1) to exit, then runs the 8Q gates on the release dylib (GPU-serial).
set -u
PID=$1
while kill -0 $PID 2>/dev/null; do sleep 10; done
S=/private/tmp/claude-501/-Users-majimadaisuke-code-litertlm-convert/7ffdfeee-f1e0-4c0c-b6d2-9072c447fa05/scratchpad
G=$HOME/code/litertlm-convert/qwen3_gpuopt_work/logs/dylib_761d99cb/gate8q_adv.py
PY=$HOME/venvs/lt094dev/bin/python3
echo "=== gates start $(date '+%F %T')"
for pair in rel_06b_9:p1024_06b_9flags rel_4b_9:p1024_4b_9flags rel_06b_11:p1024_06b_11flags; do
  L=${pair%%:*}; B=${pair##*:}
  echo "### CMD: python3 gate8q_adv.py --run $S/run-release --label $L --json $S/legs/gate8q_${L}.json $S/models/$B/model.litertlm  # $(date '+%F %T')" >> $S/legs/runlog.txt
  $PY $G --run $S/run-release --label $L --json $S/legs/gate8q_${L}.json $S/models/$B/model.litertlm 2>&1 | tail -10
done
echo "=== gates done $(date '+%F %T')"
