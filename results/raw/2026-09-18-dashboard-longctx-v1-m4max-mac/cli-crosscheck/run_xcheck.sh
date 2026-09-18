#!/bin/bash
# Exact-count cross-check of the yardstick long-context ladder with the engine's own --benchmark
# mode: prefill 2048 / decode 256 at --max_num_tokens 2304 / 4096 / 8192, 3 iterations per process,
# two passes (forward, then reversed) per (file, backend). CPU = the c363e172 XNNPACK build the K5
# rows were measured with (ynnpack_work bin/mac no_ynnpack); GPU = the v0.17.0 tag CLI with ONLY the
# WebGPU accelerator dylibs beside it (the delegate family the v0.16.0 Swift package uses on the Mac).
set -u
S=$(cd "$(dirname "$0")" && pwd); OUT=${XCHECK_OUT:-$S/out}; mkdir -p "$OUT"
H=$HOME/.cache/huggingface/hub
F06=$H/models--litert-community--Qwen3-0.6B/snapshots/8414150f2e9dcc82449bcc9c5abc404b399a4d06/Qwen3-0.6B_dynamic_wi4b32_afp32.litertlm
F17=$H/models--litert-community--Qwen3-1.7B/snapshots/73fbc3fe8271c162a603ee66f6e7ed25b6211195/Qwen3_1.7B.litertlm
FE2=$H/models--litert-community--gemma-4-E2B-it-litert-lm/snapshots/b3ca0d2f076785a8f4b2219ddbd2bdb99954eae1/gemma-4-E2B-it.litertlm
leg(){ # <rundir> <backend> <label> <model> <ctx> <pass>
  local RUN=$S/$1 BE=$2 L=$3 M=$4 C=$5 P=$6 LOG
  LOG=$OUT/${L}_${BE}_ctx${C}_p${P}.log
  echo "### $L $BE ctx=$C pass=$P $(date '+%F %T') load=$(uptime | sed 's/.*load averages: //')" | tee -a "$OUT/runlog.txt"
  ( cd "$RUN" && DYLD_LIBRARY_PATH=$RUN ./litert_lm_advanced_main --backend=$BE --model_path=$M --disable_cache=true \
      --benchmark=true --num_iterations=3 --max_num_tokens=$C --benchmark_prefill_tokens=2048 --benchmark_decode_tokens=256 \
      < /dev/null > "$LOG" 2>&1; echo "EXIT_CODE=$?" >> "$LOG" )
  printf "  %s accel=[%s] invalid_decode=%s | " "$(grep -o 'EXIT_CODE=[0-9]*' "$LOG")" "$(grep -o -E 'name=(GPU [A-Za-z]+|CpuAccelerator)' "$LOG" | sort -u | tr '\n' ' ')" "$(grep -c 'Invalid decode' "$LOG")"
  grep -E 'Prefill Speed|Decode Speed|Time to first token' "$LOG" | sed -E 's/^[[:space:]]+//' | tr '\n' ' '; echo
  sleep 5
}
for P in 1 2; do
  if [ $P = 1 ]; then CTXS="2304 4096 8192"; else CTXS="8192 4096 2304"; fi
  for C in $CTXS; do
    leg run-cpu cpu qwen3-0.6b-wi4b32 "$F06" $C $P
    leg run-cpu cpu qwen3-1.7b-int8 "$F17" $C $P
    leg run-cpu cpu gemma-4-e2b "$FE2" $C $P
    leg run-webgpu gpu qwen3-0.6b-wi4b32 "$F06" $C $P
    leg run-webgpu gpu gemma-4-e2b "$FE2" $C $P
  done
done
echo "XCHECK_DONE $(date '+%F %T')"
