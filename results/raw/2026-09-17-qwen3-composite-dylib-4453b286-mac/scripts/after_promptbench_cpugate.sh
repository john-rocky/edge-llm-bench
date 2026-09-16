#!/bin/zsh
# After the promptbench chain: the 0.6B composite bundle answered the rhyme prompt 'violets.' on the new Metal dylib (7/8).
# Is that the graph (the composite export's numerics) or the Metal kernels? Same bundle, same binary, --backend=cpu (XNNPACK),
# full 8Q; and the bundle without the composites on CPU as the control.
set -u
S=${S:?}
while ! grep -q '=== promptbench done' $S/legs/driver.log; do sleep 10; done
PY=$HOME/venvs/lt094dev/bin/python3; [ -x "$PY" ] || PY=python3
NEW=$S/run-4453b286; M=$S/models
echo "=== cpu gates start $(date '+%F %T')  load=$(uptime | sed 's/.*load averages: //')"
for pair in cpu_06b_11:p1024_06b_11flags cpu_06b_9:p1024_06b_9flags; do
  L=${pair%%:*}; B=${pair##*:}
  echo "### CMD: python3 gate8q_adv_backend.py --backend cpu --run $NEW --label $L --json $S/legs/gate8q_${L}.json $M/$B/model.litertlm  # $(date '+%F %T')" >> $S/legs/runlog.txt
  $PY $S/scripts/gate8q_adv_backend.py --backend cpu --run $NEW --label $L --json $S/legs/gate8q_${L}.json $M/$B/model.litertlm 2>&1 | tail -10
done
echo "=== cpu gates done $(date '+%F %T')"
