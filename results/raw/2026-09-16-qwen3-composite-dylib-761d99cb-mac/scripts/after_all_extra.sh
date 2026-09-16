#!/bin/zsh
# After the chained jobs: reconcile the 1,024-token --benchmark_prefill_tokens prefill (9.3k) with the 09-11 prompt-mode
# reading (6.0-6.9k, 996-token passage, litert_lm_main): same binary as today, --benchmark with the real prompt, 0.6B 9 flags ×2.
set -u
PID=$1
while kill -0 $PID 2>/dev/null; do sleep 10; done
S=/private/tmp/claude-501/-Users-majimadaisuke-code-litertlm-convert/7ffdfeee-f1e0-4c0c-b6d2-9072c447fa05/scratchpad
RUN=$S/run-release; B=$S/models/p1024_06b_9flags/model.litertlm
P="$(cat $HOME/code/litertlm-convert/qwen3_gpuopt_work/logs/metal_20260911/prompt_1000.txt) /no_think"
for i in 1 2; do
  LOG=$S/legs/rel_06b_9_promptbench_r$i.log
  echo "### CMD: cd $RUN && DYLD_LIBRARY_PATH=$RUN ./litert_lm_advanced_main --backend=gpu --model_path=$B --benchmark=true --input_prompt='<prompt_1000.txt> /no_think' --max_num_tokens=4096 --disable_cache=true < /dev/null  # promptbench r$i $(date '+%F %T')" >> $S/legs/runlog.txt
  ( cd $RUN && DYLD_LIBRARY_PATH=$RUN ./litert_lm_advanced_main --backend=gpu --model_path=$B --benchmark=true --input_prompt="$P" --max_num_tokens=4096 --disable_cache=true < /dev/null > $LOG 2>&1; echo "EXIT_CODE=$?" >> $LOG )
  echo "== promptbench r$i $(grep -o 'EXIT_CODE=[0-9]*' $LOG) $(grep -E 'Processed|Prefill Speed|Decode Speed' $LOG | sed -E 's/^[[:space:]]+//' | tr '\n' ' ')"
done
echo "=== extra done $(date '+%F %T')"
