#!/bin/zsh
# leg.sh <run-dir> <bundle.litertlm> <label> <mode>   mode = run | b1k | b31k | runv (run + --min_log_severity=0) | runp (run + --enable_profiling=true)
# One process on the Metal accelerator path: the run dir holds ONLY litert_lm_advanced_main (LiteRT-LM v0.17.0 tag build,
# sha256 56137e57…) + libGemmaModelConstraintProvider + libLiteRtTopKMetalSampler + ONE libLiteRtMetalAccelerator.dylib
# (v0.17.0 release, 4453b286 = 09-17 prebuilt, or 1dadd00c = 09-18 prebuilt), so the registry logs "name=GPU Metal". Flags = Fengwu's 2026-09-16 pair minus
# --use_metal (not a flag of the OSS 0.17.0 CLI); "run" = the 996-token passage prompt + /no_think, max_num_tokens 4096.
set -u
RUN=$1; B=$2; L=$3; MODE=$4
OUT=${LEG_OUT:?set LEG_OUT}; RUNLOG=${LEG_RUNLOG:-$OUT/runlog.txt}
PROMPT_FILE=$HOME/code/litertlm-convert/qwen3_gpuopt_work/logs/metal_20260911/prompt_1000.txt
case $MODE in
  run)  FLAGS=(--backend=gpu --model_path=$B --input_prompt="$(cat $PROMPT_FILE) /no_think" --max_num_tokens=4096 --disable_cache=true); SHOWN="--backend=gpu --model_path=$B --input_prompt='<prompt_1000.txt> /no_think' --max_num_tokens=4096 --disable_cache=true";;
  b1k)  FLAGS=(--backend=gpu --model_path=$B --disable_cache=true --benchmark=true --num_iterations=3 --max_num_tokens=1280 --benchmark_prefill_tokens=1024 --benchmark_decode_tokens=256); SHOWN="${FLAGS[*]}";;
  b31k) FLAGS=(--backend=gpu --model_path=$B --disable_cache=true --benchmark=true --num_iterations=3 --max_num_tokens=32768 --benchmark_prefill_tokens=31744 --benchmark_decode_tokens=256); SHOWN="${FLAGS[*]}";;
  runv) FLAGS=(--backend=gpu --model_path=$B --input_prompt="$(cat $PROMPT_FILE) /no_think" --max_num_tokens=4096 --disable_cache=true --min_log_severity=0); SHOWN="--backend=gpu --model_path=$B --input_prompt='<prompt_1000.txt> /no_think' --max_num_tokens=4096 --disable_cache=true --min_log_severity=0";;
  runp) FLAGS=(--backend=gpu --model_path=$B --input_prompt="$(cat $PROMPT_FILE) /no_think" --max_num_tokens=4096 --disable_cache=true --enable_profiling=true); SHOWN="--backend=gpu --model_path=$B --input_prompt='<prompt_1000.txt> /no_think' --max_num_tokens=4096 --disable_cache=true --enable_profiling=true";;
  *) echo "bad mode $MODE"; exit 2;;
esac
LOG=$OUT/${L}_${MODE}.log
GPU=$(for i in 1 2 3; do ioreg -r -d 1 -c IOAccelerator 2>/dev/null | grep -o '"Device Utilization %"=[0-9]*' | head -1 | cut -d= -f2; sleep 2; done | tr '\n' '/')
OTHER=$(ps aux | grep -E "yardstick|litert_lm|llm-bench|llama|gsm8k|litert-lm|mlx|bazel" | grep -v -E "grep|claude|run_all|leg.sh|orchestrate" | awk '$3>20{printf "%s(%s%%) ", $11, $3}')
echo "### CMD: cd $RUN && DYLD_LIBRARY_PATH=$RUN ./litert_lm_advanced_main $SHOWN < /dev/null  # $L $MODE $(date '+%F %T') gpu_util_before=$GPU load=$(uptime | sed 's/.*load averages: //') other_procs=[${OTHER:-none}]" >> "$RUNLOG"
T0=$SECONDS
( cd "$RUN" && DYLD_LIBRARY_PATH=$RUN gtimeout 1800 ./litert_lm_advanced_main "${FLAGS[@]}" < /dev/null > "$LOG" 2>&1; echo "EXIT_CODE=$?" >> "$LOG" )   # 124 = the 30-min timeout fired
W=$((SECONDS-T0))
ACC=$(grep -o -E 'name=GPU [A-Za-z]+' "$LOG" | sort -u | tr '\n' ' ')
SM=$(grep -c 'Shape mismatch' "$LOG"); VE=$(grep -c 'Validation error' "$LOG"); RC=$(grep -o 'EXIT_CODE=[0-9]*' "$LOG")
NC=$(grep -c 'cache_dir: :nocache' "$LOG")
echo "== $L $MODE  $RC wall=${W}s accel=[$ACC] shape_mismatch=$SM verr=$VE nocache_lines=$NC gpu_before=$GPU other=[${OTHER:-none}]"
if [ "$MODE" = run ]; then
  echo "   text: $(awk '/^advanced_settings:/{p=1;next} /^EXIT_CODE=|^BenchmarkInfo:/{p=0} p' "$LOG" | grep -v -E '^(I0000|W0000|E0000|INFO|WARNING|VERBOSE|ERROR)' | tr '\n' ' ' | sed -E 's/^ +//' | cut -c1-260)"
fi
grep -E 'Prefill Speed|Decode Speed|Time to first token|Processed' "$LOG" | sed -E 's/^[[:space:]]+//' | tr '\n' ' ' | sed 's/ duration\.//g'; echo
[ "$RC" = "EXIT_CODE=0" ] && [ "$SM" = 0 ] || { echo "   LEG_FAIL $L $MODE ($RC shape_mismatch=$SM)"; exit 1; }
exit 0
