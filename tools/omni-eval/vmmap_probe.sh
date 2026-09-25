#!/bin/zsh
D=$HOME/code/edge-llm-bench/.build/omni-runner-66058c82; M=$HOME/code/edge-llm-bench/.build/asr-models; B=$HOME/code/edge-llm-bench/.build/omni-eval; O=$B/runs/2026-09-25-rss-probe-mac
DYLD_LIBRARY_PATH=$D $D/omni_eval_runner --model_name=whisper-tiny --cache_dir=$M --backend=gpu --num_threads=4 --manifest=$B/sets/librispeech-test-clean/manifest.tsv --limit=120 --output=$O/vmmap-whisper-gpu-120.jsonl 2>/dev/null &
pid=$!
# early snapshot at ~10 utterances, late at ~100
while [ $(grep -c '"id"' $O/vmmap-whisper-gpu-120.jsonl 2>/dev/null) -lt 10 ]; do sleep 1; done
vmmap --summary $pid > $O/vmmap-whisper-gpu-early.txt 2>&1
while [ $(grep -c '"id"' $O/vmmap-whisper-gpu-120.jsonl 2>/dev/null) -lt 100 ]; do sleep 1; done
vmmap --summary $pid > $O/vmmap-whisper-gpu-late.txt 2>&1
wait $pid
