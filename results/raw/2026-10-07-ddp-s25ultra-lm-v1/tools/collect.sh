#!/bin/bash
# collect.sh <driver dir with upstream collect_lm.py + matrix.yaml> <sessions root> <out dir>
# One collect_lm.py call per model repo (google-ai-edge/litert-samples benchmark/driver at 17e5db06);
# every session of the sitting is passed, a job without a prefill turn is reported FAILED by the script.
DRV="$1"; D="$2"; OUT="$3"
run() { python3 "$DRV/collect_lm.py" --matrix "$DRV/matrix.yaml" --data-dir "$OUT" "$@"; echo "rc=$?"; }
run "$D/session-a7c5ae10" "$D/session-10701be8" --model litert-community/Qwen3-0.6B --model-size-mb 497.52
run "$D/session-75cdf64a" "$D/session-83804732" ${EXTRA_17B:+"$D/$EXTRA_17B"} --model litert-community/Qwen3-1.7B --task text-generation --model-size-mb 2056.73
run "$D/session-fb63c76d" "$D/session-981d881c" --model litert-community/Qwen3-4B --task text-generation --model-size-mb 2659.06
run "$D/session-aecaca6b" "$D/session-0d1cde8d" --model litert-community/gemma-4-E2B-it-litert-lm --task text-generation --model-size-mb 2588.15
run "$D/session-565fe3f9" "$D/session-e06d4f0b" --model litert-community/gemma-4-E4B-it-litert-lm --task text-generation --model-size-mb 3659.53
