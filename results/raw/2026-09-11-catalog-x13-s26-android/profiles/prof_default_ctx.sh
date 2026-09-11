#!/bin/bash
# Bundle-default context (no --max_num_tokens) benchmark pairs, same p128/d256, no profiling:
# the refutation test for "the CPU pays for the allocated KV length".
set -u
SER=RFGL80R6A6H; DEV=/data/local/tmp/llmbench; OUT=$(cd "$(dirname "$0")" && pwd)/prof_defaultctx; mkdir -p "$OUT"
HOLD=~/code/litertlm-convert/community_accel_work/s2_npu_sweep/.device_hold; CLI=~/code/litertlm-convert/community_accel_work/hold_cli.py
python3 "$CLI" acquire "$HOLD" edge-llm-bench/x13-profile-s26-defaultctx "$$" || { echo "hold refused"; exit 3; }
trap 'python3 "$CLI" release "$HOLD" "$$"; echo "hold released $(date +%T)"' EXIT
run() { local tag=$1 m=$2 b=$3 extra=$4 log="$OUT/${tag}_${b}_${5}.log"
  for i in $(seq 1 40); do s=$(adb -s $SER shell dumpsys thermalservice | grep 'Thermal Status' | tr -dc 0-9); [ "$s" = "0" ] && break; echo "thermal $s waiting"; sleep 30; done
  echo "=== $(date +%T) $tag $b $5 -> $log"
  adb -s $SER shell "cd $DEV && LD_LIBRARY_PATH=. ./litert_lm_advanced_main --backend=$b --model_path=$DEV/$m --benchmark --benchmark_prefill_tokens=128 --benchmark_decode_tokens=256 --async=false $extra > $DEV/prof_out.txt 2>&1 < /dev/null; echo EXIT_CODE=\$? >> $DEV/prof_out.txt"
  adb -s $SER pull "$DEV/prof_out.txt" "$log" >/dev/null; grep -E "Prefill Speed|Decode Speed|EXIT_CODE|max_tokens:" "$log" | head -4; sleep 60; }
W=models/litert-local_Qwen3-0.6B-dynamic-wi4b32_Qwen3-0.6B_dynamic_wi4b32_afp32.litertlm
M=models/litert-community_Qwen3-0.6B_qwen3_0_6b_mixed_int4.litertlm
for b in cpu gpu; do run wi4b32 $W $b "" default; done
for b in cpu gpu; do run wi4b32 $W $b "--max_num_tokens=4096" ctx4096; done
for b in cpu gpu; do run mixed_int4 $M $b "" default; done
echo "=== defaultctx done $(date +%T)"
