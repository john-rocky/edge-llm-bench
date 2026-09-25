#!/bin/zsh
cd /Users/majimadaisuke/code/edge-llm-bench/.build/omni-runner-66058c82-fix2c
run() { model=$1; man=$2; tag=$3; shift 3; env "$@" ./omni_eval_runner --model_name=$model --cache_dir=/Users/majimadaisuke/code/edge-llm-bench/.build/asr-models --backend=cpu --num_threads=4 --manifest=$man --output=/Users/majimadaisuke/code/edge-llm-bench/.build/omni-eval/runs/2026-09-25-ab-short-mac/$tag.jsonl 2>/Users/majimadaisuke/code/edge-llm-bench/.build/omni-eval/runs/2026-09-25-ab-short-mac/$tag.stderr.log; echo "END $tag rc=$? $(date +%H:%M:%S)" >> /Users/majimadaisuke/code/edge-llm-bench/.build/omni-eval/runs/2026-09-25-ab-short-mac/progress2.log; }
for m in 0 2 4 8 16; do
  if [ $m = 0 ]; then run parakeet-tdt-0.6b-v3 /Users/majimadaisuke/code/edge-llm-bench/.build/omni-eval/sets/librispeech-test-clean/manifest-short5.tsv 5s-c-stop0 OMNI_VALID_STOP=0; else run parakeet-tdt-0.6b-v3 /Users/majimadaisuke/code/edge-llm-bench/.build/omni-eval/sets/librispeech-test-clean/manifest-short5.tsv 5s-c-m$m OMNI_VALID_MARGIN=$m; fi
done
for m in 0 2 4 8 16; do
  if [ $m = 0 ]; then run parakeet-tdt-0.6b-v3-30s /Users/majimadaisuke/code/edge-llm-bench/.build/omni-eval/sets/librispeech-test-clean/manifest-short5-300.tsv 30s-c-stop0 OMNI_VALID_STOP=0; else run parakeet-tdt-0.6b-v3-30s /Users/majimadaisuke/code/edge-llm-bench/.build/omni-eval/sets/librispeech-test-clean/manifest-short5-300.tsv 30s-c-m$m OMNI_VALID_MARGIN=$m; fi
done
echo "AB2 DONE $(date +%H:%M:%S)" >> /Users/majimadaisuke/code/edge-llm-bench/.build/omni-eval/runs/2026-09-25-ab-short-mac/progress2.log
