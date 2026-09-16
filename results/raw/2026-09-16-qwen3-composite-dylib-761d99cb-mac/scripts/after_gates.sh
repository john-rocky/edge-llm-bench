#!/bin/zsh
# Waits for after_driver.sh (pid $1) and the 0.17.1 venv, then runs the composite bundles through the released
# litert-lm 0.17.1 CLI (litert-lm-api 0.17.1 runtime, GPU = WebGPU path) — does yesterday's release execute the composites?
set -u
PID=$1
S=/private/tmp/claude-501/-Users-majimadaisuke-code-litertlm-convert/7ffdfeee-f1e0-4c0c-b6d2-9072c447fa05/scratchpad
CLI=$HOME/venvs/lt0171run/bin/litert-lm
while kill -0 $PID 2>/dev/null; do sleep 10; done
while ! grep -q "pip rc=" $HOME/code/litertlm-convert/qwen3_gpuopt_work/logs/dylib_761d99cb/pip_lt0171run.log 2>/dev/null; do sleep 10; done
echo "=== 0.17.1 CLI runs start $(date '+%F %T')  $($CLI --version 2>&1 | head -1)"
P="$(cat $HOME/code/litertlm-convert/qwen3_gpuopt_work/logs/metal_20260911/prompt_1000.txt)"
for pair in cli171_06b_11:p1024_06b_11flags cli171_06b_9:p1024_06b_9flags cli171_4b_11:p1024_4b_11flags; do
  L=${pair%%:*}; B=${pair##*:}; LOG=$S/legs/${L}_run.log
  echo "### CMD: $CLI run $S/models/$B/model.litertlm --backend gpu --thinking false --cache no --verbose --prompt '<prompt_1000.txt>' < /dev/null  # $L $(date '+%F %T')" >> $S/legs/runlog.txt
  ( $CLI run $S/models/$B/model.litertlm --backend gpu --thinking false --cache no --verbose --prompt "$P" < /dev/null > $LOG 2>&1; echo "EXIT_CODE=$?" >> $LOG )
  echo "== $L  $(grep -o 'EXIT_CODE=[0-9]*' $LOG) verr=$(grep -c 'Validation error' $LOG) shape_mismatch=$(grep -c 'Shape mismatch' $LOG) accel=[$(grep -o -E 'name=GPU [A-Za-z]+' $LOG | sort -u | tr '\n' ' ')] wgsl=$(grep -c -i 'wgsl\|shader' $LOG)"
  echo "   text: $(grep -v -E '^(I0000|W0000|E0000|INFO|WARNING|VERBOSE|ERROR|\[)' $LOG | tr '\n' ' ' | sed -E 's/^ +//' | cut -c1-300)"
done
echo "=== done $(date '+%F %T')"
