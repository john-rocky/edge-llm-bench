#!/bin/zsh
# After run_all.sh (pid $1): the 09-11 measurement form (--benchmark=true with the 996-token passage prompt, decode over the
# generated answer) on the NEW dylib, so the 09-11 void rates (0.6B 447 / 4B 144 decode with wrong output) get their
# correct-output counterpart in the same mode; 2 processes per bundle, 4 bundles. Then the same for the release dylib on
# the two bundles without the composites (control).
set -u
PID=$1; S=${S:?}
while kill -0 $PID 2>/dev/null; do sleep 10; done
NEW=$S/run-4453b286; REL=$S/run-release; M=$S/models
P="$(cat $HOME/code/litertlm-convert/qwen3_gpuopt_work/logs/metal_20260911/prompt_1000.txt) /no_think"
echo "=== promptbench start $(date '+%F %T')  load=$(uptime | sed 's/.*load averages: //')"
for spec in $NEW:p1024_06b_11flags:new_06b_11 $NEW:p1024_06b_9flags:new_06b_9 $NEW:p1024_4b_11flags:new_4b_11 $NEW:p1024_4b_9flags:new_4b_9 $REL:p1024_06b_9flags:rel_06b_9 $REL:p1024_4b_9flags:rel_4b_9; do
  RUN=${spec%%:*}; rest=${spec#*:}; B=${rest%%:*}; L=${rest##*:}
  for i in 1 2; do
    LOG=$S/legs/${L}_promptbench_r$i.log
    GPU=$(ioreg -r -d 1 -c IOAccelerator 2>/dev/null | grep -o '"Device Utilization %"=[0-9]*' | head -1 | cut -d= -f2)
    echo "### CMD: cd $RUN && DYLD_LIBRARY_PATH=$RUN ./litert_lm_advanced_main --backend=gpu --model_path=$M/$B/model.litertlm --benchmark=true --input_prompt='<prompt_1000.txt> /no_think' --max_num_tokens=4096 --disable_cache=true < /dev/null  # $L promptbench r$i $(date '+%F %T') gpu_util_before=$GPU load=$(uptime | sed 's/.*load averages: //')" >> $S/legs/runlog.txt
    ( cd $RUN && DYLD_LIBRARY_PATH=$RUN ./litert_lm_advanced_main --backend=gpu --model_path=$M/$B/model.litertlm --benchmark=true --input_prompt="$P" --max_num_tokens=4096 --disable_cache=true < /dev/null > $LOG 2>&1; echo "EXIT_CODE=$?" >> $LOG )
    echo "== $L promptbench r$i $(grep -o 'EXIT_CODE=[0-9]*' $LOG) sm=$(grep -c 'Shape mismatch' $LOG) $(grep -E 'Processed|Prefill Speed|Decode Speed' $LOG | sed -E 's/^[[:space:]]+//' | tr '\n' ' ')"
  done
done
echo "=== promptbench done $(date '+%F %T')"
