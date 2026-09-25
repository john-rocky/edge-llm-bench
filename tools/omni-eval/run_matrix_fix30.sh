#!/bin/zsh
# Fixed-engine CPU matrix (Slaney/power mel + whisper prompt), same watchdog as run_matrix.sh.
set -u
B=$HOME/code/edge-llm-bench/.build/omni-eval
D=$HOME/code/edge-llm-bench/.build/omni-runner-66058c82-fix
M=$HOME/code/edge-llm-bench/.build/asr-models
O=$B/runs/2026-09-25-fix-mac
HANG_S=${HANG_S:-60}
mkdir -p $O
P=$O/progress-30s.log

next_id_after() {
  local manifest=$1 last=$2
  if [ -z "$last" ]; then head -1 $manifest | cut -f1; else awk -F'\t' -v l="$last" 'f{print $1; exit} $1==l{f=1}' $manifest; fi
}

run() {
  local model=$1 set=$2 backend=$3
  local tag=$model-$set-$backend
  local manifest=$B/sets/librispeech-test-$set/manifest.tsv
  if grep -q '"type":"footer"' $O/$tag.jsonl 2>/dev/null; then echo "SKIP $tag (done)" >> $P; return; fi
  echo "START $tag $(date +%H:%M:%S)" >> $P
  local extra="" attempt=0
  while true; do
    attempt=$((attempt+1))
    local cmd="$D/omni_eval_runner --model_name=$model --cache_dir=$M --backend=$backend --num_threads=4 --manifest=$manifest --output=$O/$tag.jsonl $extra"
    echo "### CMD: $cmd" >> $O/$tag.cmd
    ${=cmd} 2>> $O/$tag.stderr.log &
    local pid=$!
    local last_n=-1 stalled=0 rc=""
    while kill -0 $pid 2>/dev/null; do
      sleep 10
      local n=$(wc -l < $O/$tag.jsonl 2>/dev/null || echo 0)
      if [ "$n" = "$last_n" ]; then stalled=$((stalled+10)); else stalled=0; last_n=$n; fi
      if [ $stalled -ge $HANG_S ]; then
        local last_id=$(grep -o '"id":"[^"]*"' $O/$tag.jsonl | tail -1 | cut -d'"' -f4)
        local hung=$(next_id_after $manifest "$last_id")
        echo "$tag	$hung	stalled ${HANG_S}s after $last_id	$(date +%H:%M:%S)" >> $O/HANGS.txt
        echo "HANG $tag on $hung (killing pid $pid, resume after it)" >> $P
        kill $pid 2>/dev/null; sleep 2; kill -9 $pid 2>/dev/null
        extra="--start_after=$hung --append"; rc=hang
        break
      fi
    done
    if [ "$rc" != hang ]; then wait $pid; rc=$?; break; fi
    if [ $attempt -ge 50 ]; then echo "GIVE UP $tag" >> $P; break; fi
  done
  echo "END $tag rc=$rc attempts=$attempt $(date +%H:%M:%S) $(tail -1 $O/$tag.jsonl 2>/dev/null | cut -c1-200)" >> $P
}


run parakeet-tdt-0.6b-v3-30s clean cpu

run parakeet-tdt-0.6b-v3-30s other cpu
echo "FIX30 MATRIX DONE $(date +%H:%M:%S)" >> $P
