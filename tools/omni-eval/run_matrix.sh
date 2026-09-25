#!/bin/zsh
# LibriSpeech test-clean / test-other through OmniEngine (main@66058c82), Mac M4 Max.
# Sequential: one runner process at a time, 4 threads; GPU rows hold the machine GPU lock.
set -u
S=$OMNI_EVAL_DIR
B=$HOME/code/edge-llm-bench/.build/omni-eval
D=$HOME/code/edge-llm-bench/.build/omni-runner-66058c82
M=$HOME/code/edge-llm-bench/.build/asr-models
O=$B/runs/2026-09-25-librispeech-mac
LOCK=$HOME/code/coreai-kit/scripts/with-gpu-lock.py
PY=/opt/homebrew/bin/python3
mkdir -p $O
P=$O/progress.log

# Android build first (it would perturb the timing if it ran during a cell).
( cd $HOME/code/litert-lm-omni-wt && ANDROID_NDK_HOME=$HOME/Library/Android/sdk/ndk/28.2.13676358 \
  bazelisk build --config=android_arm64 --enable_platform_specific_config //omni:omni_eval_runner \
  > $S/build-android-2.log 2>&1; echo "android build EXIT $? $(date +%H:%M:%S)" >> $P )

run() {
  local model=$1 set=$2 backend=$3
  local tag=$model-$set-$backend
  if grep -q '"type":"footer"' $O/$tag.jsonl 2>/dev/null; then echo "SKIP $tag (done)" >> $P; return; fi
  echo "START $tag $(date +%H:%M:%S) therm=[$(pmset -g therm | tr '\n' ' ' | tr -s ' ')] load=[$(uptime | sed 's/.*load averages: //')]" >> $P
  local cmd="$D/omni_eval_runner --model_name=$model --cache_dir=$M --backend=$backend --num_threads=4 --manifest=$B/sets/librispeech-test-$set/manifest.tsv --output=$O/$tag.jsonl"
  echo "### CMD: $cmd" > $O/$tag.cmd
  if [ "$backend" = gpu ]; then
    DYLD_LIBRARY_PATH=$D $PY $LOCK -- ${=cmd} 2> $O/$tag.stderr.log
  else
    ${=cmd} 2> $O/$tag.stderr.log
  fi
  local rc=$?
  echo "END $tag rc=$rc $(date +%H:%M:%S) $(tail -1 $O/$tag.jsonl 2>/dev/null | cut -c1-220)" >> $P
}

for set in clean other; do run parakeet-tdt-0.6b-v3 $set cpu; done
for set in clean other; do run whisper-tiny $set cpu; done
for set in clean other; do run parakeet-tdt-0.6b-v3 $set gpu; done
for set in clean other; do run whisper-tiny $set gpu; done
echo "MATRIX DONE $(date +%H:%M:%S)" >> $P
