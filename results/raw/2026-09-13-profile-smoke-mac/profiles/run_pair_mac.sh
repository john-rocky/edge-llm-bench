#!/bin/bash
# run_pair_mac.sh - one (control, profiled) pair of LiteRT-LM's native benchmark on a Mac,
# run by hand in the layout android/bench/run_profile.py writes, so that
# scripts/profile/profile_report.py reads it unchanged. Stored beside the logs it produced.
#
#   BACKEND=gpu bash run_pair_mac.sh
#
# Env: BIN (litert_lm_advanced_main built from the LiteRT-LM tag), LIBDIR (that tag's
# prebuilt/macos_arm64 - the accelerator dylibs go beside the binary, as upstream's
# build-and-run.md says for GPU), MODEL (.litertlm), OUT (the profiles dir), BACKEND
# (cpu|gpu), P / D / CTX (prefill, decode, max_num_tokens), COOLDOWN (seconds between runs).
# Per run: RSS sampled with ps every 0.5 s (the Android runner reads VmRSS the same way),
# the engine's stdout+stderr after ===ENGINE_OUTPUT===, EXIT_CODE= last. The first run of a
# backend is the engine's cache-building run (the Android runner's firstEver) and is kept as
# <tag>_<backend>_warmup.log, outside the pair; the pair is the second run (control) and the
# third (the same command plus --enable_profiling).
set -u
: "${BIN:?}" "${LIBDIR:?}" "${MODEL:?}" "${OUT:?}" "${BACKEND:?}"
P=${P:-128}; D=${D:-256}; CTX=${CTX:-1024}; COOLDOWN=${COOLDOWN:-60}
RUN=${RUN:-$(dirname "$BIN")}
TAG="$(basename "$MODEL" .litertlm)_${P}x${D}_ctx${CTX}${TAGSUFFIX:-}"
mkdir -p "$OUT"
cd "$RUN" || exit 8
export DYLD_LIBRARY_PATH="$RUN"
CORE="./litert_lm_advanced_main --backend=$BACKEND --model_path=$MODEL --benchmark --benchmark_prefill_tokens=$P --benchmark_decode_tokens=$D --async=false --max_num_tokens=$CTX"

one_run() {  # $1 = log path, $2 = extra flags
  local log="$1" extra="$2" start end pid ec
  : > "$log"
  start=$(date +%s)
  echo "### CMD: cd $RUN && DYLD_LIBRARY_PATH=$RUN $CORE $extra" >> "$RUNLOG"
  ( gtimeout -k 10 ${RUN_TIMEOUT:-600} $CORE $extra > "$RUN/run_out.txt" 2>&1 ) &
  pid=$!
  while kill -0 $pid 2>/dev/null; do
    epid=$(pgrep -P $pid -n litert_lm_advanced_main 2>/dev/null || echo $pid)
    r=$(ps -o rss= -p $epid 2>/dev/null | tr -d ' ')
    [ -n "$r" ] && echo "VmRSS:	 $r kB" >> "$log"
    sleep 0.5
  done
  wait $pid; ec=$?
  end=$(date +%s)
  { echo "===ENGINE_OUTPUT==="; cat "$RUN/run_out.txt"; echo "EXIT_CODE=$ec"; } >> "$log"
  echo "run $(basename "$log") exit=$ec elapsed=$((end-start))s $(grep -o 'Decode Speed: [0-9.]* tokens/sec' "$log" | tail -1) load=$(sysctl -n vm.loadavg)" | tee -a "$OUT/session_provenance.txt"
}

echo "pair $TAG $BACKEND start $(date '+%F %T') bin_sha256=$(shasum -a 256 "$BIN" | cut -c1-64) model_sha256=$(shasum -a 256 "$MODEL" | cut -c1-64) load=$(sysctl -n vm.loadavg)" | tee -a "$OUT/session_provenance.txt"
one_run "$OUT/${TAG}_${BACKEND}_warmup.log" ""
sleep "$COOLDOWN"
one_run "$OUT/${TAG}_${BACKEND}_ctrl.log" ""
sleep "$COOLDOWN"
one_run "$OUT/${TAG}_${BACKEND}_prof.log" "--enable_profiling"
echo "pair $TAG $BACKEND end $(date '+%F %T')" | tee -a "$OUT/session_provenance.txt"
