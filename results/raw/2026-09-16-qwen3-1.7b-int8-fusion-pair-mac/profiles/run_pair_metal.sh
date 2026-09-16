#!/usr/bin/env bash
# One model: warmup (cache build) -> control (unprofiled) -> profiled, on the Metal accelerator path
# (run dir holds ONLY libGemmaModelConstraintProvider / libLiteRtMetalAccelerator / libLiteRtTopKMetalSampler,
#  so the registry falls through to "GPU Metal"). Same flag set as the 2026-09-13 Mac pair.
#   ./run_pair_metal.sh <run-dir> <model.litertlm> <tag> <profiles-dir> [rest-seconds]
set -u
RUN=$1; MODEL=$2; TAG=$3; OUT=$4; REST=${5:-60}
BIN=$RUN/litert_lm_advanced_main
FLAGS="--backend=gpu --model_path=$MODEL --benchmark --benchmark_prefill_tokens=128 --benchmark_decode_tokens=256 --async=false --max_num_tokens=1024"
LOGR=${PROFILE_RUNLOG:-$OUT/runlog.txt}
run_one() { # kind extra-flags
  local kind=$1; shift
  local log=$OUT/${TAG}_gpu_${kind}.log
  echo "### CMD: cd $RUN && DYLD_LIBRARY_PATH=$RUN ./litert_lm_advanced_main $FLAGS $* < /dev/null  # $kind $(date +%F' '%T)" >> "$LOGR"
  ( cd "$RUN" && DYLD_LIBRARY_PATH=$RUN ./litert_lm_advanced_main $FLAGS "$@" < /dev/null > "$log" 2>&1; echo "EXIT_CODE=$?" >> "$log" )
  grep -E "EXIT_CODE=|Decode Speed|Prefill Speed|Time to first token|RegisterAccelerator|Dynamically loaded|Validation error|shape mismatch|UNIMPLEMENTED|Failed" "$log" | head -12
}
echo "=== $TAG warmup"; run_one warmup
sleep "$REST"
echo "=== $TAG ctrl";   run_one ctrl
sleep "$REST"
echo "=== $TAG prof";   run_one prof --enable_profiling
