#!/bin/bash
# Per-op profiling on the S26 (after the X13 campaign, under the same hold):
# Gemma 4 E2B (loser) and Qwen3-0.6B mixed_int4 (winner) x cpu/gpu, with
# litert_lm_advanced_main v0.16.0 (the pinned binary on the phone).
# Each pair: one plain --benchmark run (control, rate) then one --enable_profiling run.
set -u
SER=RFGL80R6A6H
DEV=/data/local/tmp/llmbench
OUT=${OUT:-$(cd "$(dirname "$0")" && pwd)/prof}
P=${P:-128}; D=${D:-256}; COOL=${COOL:-90}
mkdir -p "$OUT"
model_of() { case $1 in
  gemma4e2b) echo models/litert-community_gemma-4-E2B-it-litert-lm_gemma-4-E2B-it.litertlm;;
  qwen3_0_6b) echo models/litert-community_Qwen3-0.6B_qwen3_0_6b_mixed_int4.litertlm;;
  qwen3_0_6b_wi4b32) echo models/litert-local_Qwen3-0.6B-dynamic-wi4b32_Qwen3-0.6B_dynamic_wi4b32_afp32.litertlm;;
  qwen25_1_5b_q8) echo models/litert-community_Qwen2.5-1.5B-Instruct_Qwen2.5-1.5B-Instruct_multi-prefill-seq_q8_ekv4096.litertlm;;
esac; }
wait_nominal() { for i in $(seq 1 40); do s=$(adb -s $SER shell dumpsys thermalservice | grep 'Thermal Status' | tr -dc 0-9); [ "$s" = "0" ] && return 0; echo "thermal status $s — waiting"; sleep 30; done; echo "thermal gate timeout; ran anyway"; }
run() { # tag model backend profiling(0/1)
  local tag=$1 m=$2 b=$3 prof=$4 flag=""; [ "$prof" = 1 ] && flag="--enable_profiling"
  local log="$OUT/${tag}_${b}_$([ "$prof" = 1 ] && echo prof || echo ctrl).log"
  wait_nominal
  echo "=== $(date +%T) $tag $b prof=$prof -> $log"
  adb -s $SER shell "cd $DEV && LD_LIBRARY_PATH=. ./litert_lm_advanced_main --backend=$b --model_path=$DEV/$m --benchmark --benchmark_prefill_tokens=$P --benchmark_decode_tokens=$D --max_num_tokens=${MAXTOK:-1024} --async=false $flag > $DEV/prof_out.txt 2>&1 < /dev/null; echo EXIT_CODE=\$? >> $DEV/prof_out.txt"
  adb -s $SER pull "$DEV/prof_out.txt" "$log" >/dev/null
  grep -E "Prefill Speed|Decode Speed|EXIT_CODE|Failed to start profiling" "$log" | head -5
  sleep $COOL
}
for rnd in 1 2; do  # alternate cpu/gpu per model; round 1 control, round 2 profiled
  for tag in ${TAGS:-qwen3_0_6b gemma4e2b}; do
    for b in cpu gpu; do run $tag "$(model_of $tag)" $b $((rnd-1)); done
  done
done
echo "=== prof done $(date +%T)"
