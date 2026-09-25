#!/bin/zsh
# RSS over sessions: run N utterances through one engine process and sample RSS every 5 s.
# usage: rss_probe.sh <model> <backend> <n> <out_prefix>
set -u
model=$1 backend=$2 n=$3 out=$4
D=$HOME/code/edge-llm-bench/.build/omni-runner-66058c82
M=$HOME/code/edge-llm-bench/.build/asr-models
B=$HOME/code/edge-llm-bench/.build/omni-eval
cmd="$D/omni_eval_runner --model_name=$model --cache_dir=$M --backend=$backend --num_threads=4 --manifest=$B/sets/librispeech-test-clean/manifest.tsv --limit=$n --output=$out.jsonl"
echo "### CMD: DYLD_LIBRARY_PATH=$D $cmd" > $out.cmd
if [ "$backend" = gpu ]; then DYLD_LIBRARY_PATH=$D ${=cmd} 2> $out.stderr.log & else ${=cmd} 2> $out.stderr.log & fi
pid=$!
echo "t_s,utterances_done,rss_mb" > $out.rss.csv
t0=$(date +%s)
while kill -0 $pid 2>/dev/null; do
  rss=$(ps -o rss= -p $pid | tr -d ' '); done_n=$(grep -c '"id"' $out.jsonl 2>/dev/null)
  echo "$(( $(date +%s) - t0 )),$done_n,$(( ${rss:-0} / 1024 ))" >> $out.rss.csv
  sleep 5
done
wait $pid; echo "exit $?" >> $out.cmd
tail -3 $out.rss.csv
