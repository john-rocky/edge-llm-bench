#!/bin/zsh
# Re-export parakeet-tdt-0.6b-v3 with a 30 s input window using the official litert-samples recipe.
set -u
cd ~/code/litert-samples
export HF_HUB_OFFLINE=1 PYTHONPATH=.
python compiled_model_api/speech_recognition/convert/convert_to_tflite.py \
  --model nvidia/parakeet-tdt-0.6b-v3 --input_sec 30 --stateful_after 4 --quant drq \
  --sample_audio ~/code/edge-llm-bench/.build/omni-eval/sets/librispeech-test-clean/4507-16021-0047.wav \
  --output /Users/majimadaisuke/code/edge-llm-bench/.build/asr-models/parakeet_tdt_0.6b_v3_30s_i8_stateful.tflite
echo "EXIT $?"
