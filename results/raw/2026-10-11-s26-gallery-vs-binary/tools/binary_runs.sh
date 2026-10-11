#!/bin/bash
# Galaxy S26 (SM-S942Q): the LiteRT-LM benchmark binary from gs://litert/binaries/latest (litert_lm_advanced_main,
# sha256 adac974b…2d06, object dated 2026-09-18) at the arguments of the bug line-ups — prefill 1024 / decode 256 /
# --max_num_tokens=4096 / one iteration — as cold processes (no cache files in the run dir) and cached processes
# (a new process with the cache files the previous one wrote), with a 1-second sampler of CPU / GPU clocks and
# thermal zones, the logcat window of each process, and (for the tags in TRACE_TAGS) a Perfetto trace.
#
#   SERIAL=RFGL80R6A6H OUT=<results dir> KIT=<dir with the binary + 6 libs> PLAN="G1:gpu:e2b:cold G2:gpu:e2b:cached …" \
#   TRACE_TAGS="G1 G2" PERFETTO_CFG=<pbtxt> bash binary_runs.sh
#
# Plan item = <tag>:<backend>:<bundle key>:<cold|cached>. Bundle keys: e2b = gemma-4-E2B-it.litertlm (copied on the
# phone from /data/local/tmp when its sha256 matches, else pushed from E2B_LOCAL), g3 = gemma3-1b-it-int4.litertlm
# (pushed from G3_LOCAL). Everything the run needs lives in $DEV on the phone; `cleanup` removes it.
set -u
SERIAL=${SERIAL:-RFGL80R6A6H}
A() { adb -s "$SERIAL" "$@" < /dev/null; }
OUT=${OUT:?results dir}
KIT=${KIT:?kit dir}
DEV=${DEV:-/data/local/tmp/s26-gallery-vs-binary}
PLAN=${PLAN:-}
TRACE_TAGS=${TRACE_TAGS:-}
PERFETTO_CFG=${PERFETTO_CFG:-}
TRACE_DIR=${TRACE_DIR:-$OUT/perfetto}
GAP_S=${GAP_S:-30}
BIN_SHA=adac974bea147273b5bc64232d808905667eee69587161368146680df92e2d06
E2B=gemma-4-E2B-it.litertlm;  E2B_SHA=181938105e0eefd105961417e8da75903eacda102c4fce9ce90f50b97139a63c
G3=gemma3-1b-it-int4.litertlm; G3_SHA=1325ae366d31950f137c9c357b9fa89448b176d76998180c08ceaca78bba98be
E2B_LOCAL=${E2B_LOCAL:-}
G3_LOCAL=${G3_LOCAL:-}
LIBS="libGemmaModelConstraintProvider.so libLiteRtDispatch_GoogleTensor.so libLiteRtDispatch_MediaTek.so libLiteRtDispatch_Qualcomm.so libLiteRtOpenClAccelerator.so libLiteRtTopKOpenClSampler.so"
ZONES="36 5 24 63 55"   # gpuss-0, cpu-0-0-0, cpu-1-0-0, battery, sys-therm-0 (read back as names in steps.log)
mkdir -p "$OUT" "$TRACE_DIR"
LOG="$OUT/steps.log"
say() { echo "[$(date '+%F %T')] $*" | tee -a "$LOG"; }
dsha() { A shell "sha256sum $1" | awk '{print $1}' | tr -d '\r'; }
dtemp() { A shell "cat /sys/devices/system/cpu/cpufreq/policy0/scaling_cur_freq /sys/devices/system/cpu/cpufreq/policy0/scaling_max_freq /sys/devices/system/cpu/cpufreq/policy6/scaling_cur_freq /sys/devices/system/cpu/cpufreq/policy6/scaling_max_freq /sys/class/kgsl/kgsl-3d0/clock_mhz /sys/class/kgsl/kgsl-3d0/gpu_busy_percentage; for z in $ZONES; do cat /sys/class/thermal/thermal_zone\$z/temp; done" 2>/dev/null | tr -d '\r' | tr '\n' ' '; }

cmd=${1:-run}
if [ "$cmd" = cleanup ]; then
  say "cleanup: rm -rf $DEV, perfetto traces of this run"
  A shell "rm -rf $DEV; ls /data/misc/perfetto-traces/ | grep -E '^(G|C|P)[0-9]+.*perfetto-trace' | sed 's#^#/data/misc/perfetto-traces/#' | xargs -r rm -f" >/dev/null 2>&1
  say "cleanup: $(A shell "ls $DEV 2>&1" | tr -d '\r' | head -1)"
  exit 0
fi

say "START serial=$SERIAL model=$(A shell getprop ro.product.model | tr -d '\r') build=$(A shell getprop ro.build.display.id | tr -d '\r') uptime=$(A shell cat /proc/uptime | tr -d '\r')"
say "zones: $(A shell "for z in $ZONES; do printf '%s=%s ' \$z \$(cat /sys/class/thermal/thermal_zone\$z/type); done" | tr -d '\r')"
say "battery: $(A shell dumpsys battery | tr -d '\r' | grep -E 'level|status|USB' | tr '\n' ' ')"
say "thermal status: $(A shell dumpsys thermalservice | tr -d '\r' | grep -m1 'Thermal Status')"

# 1. the kit
A shell "mkdir -p $DEV" >/dev/null
for f in litert_lm_advanced_main $LIBS; do
  [ -f "$KIT/$f" ] || { say "missing in KIT: $f"; exit 5; }
  A push "$KIT/$f" "$DEV/$f" >/dev/null 2>&1 || { say "push failed: $f"; exit 5; }
  say "pushed $f sha256 $(dsha $DEV/$f | cut -c1-12) (mac $(shasum -a 256 "$KIT/$f" | cut -c1-12))"
done
A shell "chmod 755 $DEV/litert_lm_advanced_main" >/dev/null
got=$(dsha $DEV/litert_lm_advanced_main); [ "$got" = "$BIN_SHA" ] || { say "binary sha256 mismatch: $got"; exit 5; }
say "binary sha256 ok ${got:0:12}"
[ -n "$PERFETTO_CFG" ] && { A push "$PERFETTO_CFG" "/data/misc/perfetto-configs/llm_trace.pbtxt" >/dev/null 2>&1; say "pushed perfetto config to /data/misc/perfetto-configs (the perfetto command cannot read /data/local/tmp)"; }

# 2. the bundles
stage_bundle() { # key
  local name sha local_src
  case $1 in e2b) name=$E2B; sha=$E2B_SHA; local_src=$E2B_LOCAL;; g3) name=$G3; sha=$G3_SHA; local_src=$G3_LOCAL;; *) say "unknown bundle $1"; exit 5;; esac
  if [ "$(A shell "test -f $DEV/$name && echo y" | tr -d '\r')" = y ]; then say "$name already staged"; return; fi
  local t0=$(date +%s)
  if [ "$1" = e2b ] && [ "$(A shell "test -f /data/local/tmp/$name && echo y" | tr -d '\r')" = y ] && [ "$(dsha /data/local/tmp/$name)" = "$sha" ]; then
    A shell "cp /data/local/tmp/$name $DEV/$name" >/dev/null; say "staged $name (copy on the phone, $(( $(date +%s) - t0 )) s)"
  else
    [ -f "$local_src" ] || { say "no local copy for $1: $local_src"; exit 5; }
    A push "$local_src" "$DEV/$name" >/dev/null 2>&1 || { say "push failed: $name"; exit 5; }
    say "pushed $name from the Mac ($(( $(date +%s) - t0 )) s)"
  fi
  local got=$(dsha $DEV/$name); [ "$got" = "$sha" ] || { say "$name sha256 mismatch: $got"; exit 5; }
  say "$name sha256 ok ${got:0:12} bytes $(A shell "stat -c %s $DEV/$name" | tr -d '\r')"
}

# 3. one process
run_one() { # tag backend key cold|cached
  local tag=$1 be=$2 key=$3 mode=$4 model
  case $key in e2b) model=$E2B;; g3) model=$G3;; esac
  stage_bundle "$key"
  if [ "$mode" = cold ]; then A shell "rm -f $DEV/*cache* $DEV/*mldrift* $DEV/*.bin" >/dev/null 2>&1; fi
  local caches_before=$(A shell "ls $DEV 2>/dev/null | grep -c -E 'cache|mldrift'" | tr -d '\r')
  local mark=$(A shell "date '+%m-%d %H:%M:%S.000'" | tr -d '\r')
  # one remote shell per process: (perfetto --detach) -> the 1 s sampler in the background of that shell -> the binary ->
  # kill the sampler -> (perfetto --attach --stop). A sampler started from its own `adb shell` call kept that call open.
  local traced=0 pf_start="" pf_stop=""
  if [ -n "$PERFETTO_CFG" ] && [[ " $TRACE_TAGS " == *" $tag "* ]]; then
    traced=1
    pf_start="perfetto --detach=$tag -c /data/misc/perfetto-configs/llm_trace.pbtxt --txt -o /data/misc/perfetto-traces/$tag.perfetto-trace > $DEV/$tag.perfetto-start.txt 2>&1 </dev/null; sleep 2;"
    pf_stop="sleep 1; perfetto --attach=$tag --stop > $DEV/$tag.perfetto-stop.txt 2>&1 </dev/null;"
  fi
  say "START $tag backend=$be model=$model mode=$mode caches_before=$caches_before traced=$traced uptime=$(A shell cat /proc/uptime | tr -d '\r' | cut -d' ' -f1) sample: $(dtemp)"
  A shell "cd $DEV && rm -f sample-$tag.csv; $pf_start ( while :; do echo \"\$(date +%s) \$(cut -d' ' -f1 /proc/uptime) \$(cat /sys/devices/system/cpu/cpufreq/policy0/scaling_cur_freq /sys/devices/system/cpu/cpufreq/policy0/scaling_max_freq /sys/devices/system/cpu/cpufreq/policy6/scaling_cur_freq /sys/devices/system/cpu/cpufreq/policy6/scaling_max_freq /sys/class/kgsl/kgsl-3d0/clock_mhz /sys/class/kgsl/kgsl-3d0/gpu_busy_percentage 2>/dev/null | tr '\n' ' ') \$(for z in $ZONES; do cat /sys/class/thermal/thermal_zone\$z/temp; done | tr '\n' ' ')\" >> $DEV/sample-$tag.csv; sleep 1; done ) >/dev/null 2>&1 </dev/null & SP=\$!; timeout 900 env LD_LIBRARY_PATH=$DEV ./litert_lm_advanced_main --backend=$be --model_path=$DEV/$model --benchmark=true --benchmark_prefill_tokens=1024 --benchmark_decode_tokens=256 --max_num_tokens=4096 --num_iterations=1 --report_peak_memory_footprint=true --metric_proto_file_path=$DEV/metrics-$tag.pb; echo rc=\$?; kill \$SP 2>/dev/null; $pf_stop echo remote_done" > "$OUT/$tag.stdout.txt" 2>&1
  local rc=$(grep -o 'rc=[0-9]*' "$OUT/$tag.stdout.txt" | tail -1)
  if [ "$traced" = 1 ]; then
    A pull "$DEV/$tag.perfetto-start.txt" "$OUT/$tag.perfetto-start.txt" >/dev/null 2>&1; A pull "$DEV/$tag.perfetto-stop.txt" "$OUT/$tag.perfetto-stop.txt" >/dev/null 2>&1
    say "perfetto $tag: start=[$(tr -d '\r' < "$OUT/$tag.perfetto-start.txt" 2>/dev/null | tail -1)] stop=[$(tr -d '\r' < "$OUT/$tag.perfetto-stop.txt" 2>/dev/null | tail -1)]"
    sleep 1; A pull "/data/misc/perfetto-traces/$tag.perfetto-trace" "$TRACE_DIR/$tag.perfetto-trace" >/dev/null 2>&1 && say "perfetto trace pulled: $tag.perfetto-trace $(stat -f %z "$TRACE_DIR/$tag.perfetto-trace") bytes"
  fi
  A pull "$DEV/sample-$tag.csv" "$OUT/$tag.sample.csv" >/dev/null 2>&1
  A pull "$DEV/metrics-$tag.pb" "$OUT/metrics-$tag.pb" >/dev/null 2>&1
  A logcat -d -T "$mark" > "$OUT/$tag.logcat.txt" 2>/dev/null
  local caches_after=$(A shell "ls $DEV 2>/dev/null | grep -c -E 'cache|mldrift'" | tr -d '\r')
  local pf=$(grep -o 'Prefill Speed[^,]*' "$OUT/$tag.stdout.txt" | tail -1 | grep -o '[0-9.]* tokens' | cut -d' ' -f1)
  local dc=$(grep -o 'Decode Speed[^,]*' "$OUT/$tag.stdout.txt" | tail -1 | grep -o '[0-9.]* tokens' | cut -d' ' -f1)
  local tt=$(grep -o 'Time To First Token[^,]*' "$OUT/$tag.stdout.txt" | tail -1 | grep -o '[0-9.]* s' | cut -d' ' -f1)
  local it=$(grep -o 'Init Total: [0-9.]* ms' "$OUT/$tag.stdout.txt" | tail -1)
  local pk=$(grep -o 'Peak private footprint[^,]*' "$OUT/$tag.stdout.txt" | tail -1)
  local mt=$(grep -o 'max_tokens: [0-9]*' "$OUT/$tag.stdout.txt" | tail -1)
  local acc=$(grep -o 'RegisterAccelerator[^"]*name=[A-Za-z_]*' "$OUT/$tag.logcat.txt" | tail -1)
  say "END $tag $rc prefill=$pf decode=$dc ttft=$tt $it $pk $mt caches_after=$caches_after $acc sample: $(dtemp)"
}

for item in $PLAN; do
  IFS=: read -r tag be key mode <<< "$item"
  run_one "$tag" "$be" "$key" "$mode"
  say "gap ${GAP_S}s"; sleep "$GAP_S"
done
say "DONE plan=[$PLAN]"
say "sha256 after the runs: $(for k in $E2B $G3; do [ "$(A shell "test -f $DEV/$k && echo y" | tr -d '\r')" = y ] && printf '%s %s; ' "$(dsha $DEV/$k | cut -c1-12)" "$k"; done)"
