#!/bin/bash
# Galaxy S26 (SM-S942Q): LiteRT-LM #3577 — the MiniCPM5-2B dynamic_wi4c_hr_afp32 bundle (the issue's fp32-activation
# repack, sha256 036cfca8…) through the v0.18.0 release kit's litert_lm_advanced_main, GPU and CPU, each in a fresh
# process, with the issue's two prompts. Output text, exit code, delegation lines, the registered accelerator and the
# peak VmHWM of each process are recorded; nothing is pooled.
#
#   SERIAL=RFGL80R6A6H OUT=<results dir> KIT=<android/bin/v0.18.0> BUNDLE=<local .litertlm> \
#   PLAN="g1:gpu:A c1:cpu:A g2:gpu:A c2:cpu:A g3:gpu:B c3:cpu:B" bash s26_3577.sh
#
# Plan item = <tag>:<gpu|cpu>:<A|B>. Prompt A = "What is the capital of France?" (the issue's kit control);
# prompt B = "What is the capital of France? Answer with one word." (the issue's AAR gate prompt).
# LIBSET=opencl pushes only the OpenCL accelerator + sampler + constraint provider (default: every .so of the kit).
set -u
SERIAL=${SERIAL:-RFGL80R6A6H}
A() { adb -s "$SERIAL" "$@" < /dev/null; }
OUT=${OUT:?results dir}
KIT=${KIT:?kit dir}
BUNDLE=${BUNDLE:?local bundle}
DEV=${DEV:-/data/local/tmp/s26-3577-v0180}
PLAN=${PLAN:-}
LIBSET=${LIBSET:-all}
MODEL=minicpm5-2b_dynamic_wi4c_hr_afp32_fp32act.litertlm
PROMPT_A='What is the capital of France?'
PROMPT_B='What is the capital of France? Answer with one word.'
mkdir -p "$OUT"
LOG="$OUT/steps.log"
say() { echo "[$(date '+%F %T')] $*" | tee -a "$LOG"; }
dsha() { A shell "sha256sum $1" | awk '{print $1}' | tr -d '\r'; }

cmd=${1:-run}
if [ "$cmd" = cleanup ]; then
  say "cleanup: rm -rf $DEV"; A shell "rm -rf $DEV" >/dev/null 2>&1; say "cleanup: $(A shell "ls $DEV 2>&1" | tr -d '\r' | head -1)"; exit 0
fi

say "START serial=$SERIAL model=$(A shell getprop ro.product.model | tr -d '\r') build=$(A shell getprop ro.build.display.id | tr -d '\r') uptime=$(A shell cat /proc/uptime | tr -d '\r')"
say "battery: $(A shell dumpsys battery | tr -d '\r' | grep -E 'level|status|USB' | tr '\n' ' ') thermal: $(A shell dumpsys thermalservice | tr -d '\r' | grep -m1 'Thermal Status')"

# 1. the kit (every file's sha256 read back on the phone; the kit's SHA256SUMS lists the libs and litert_lm_main)
A shell "mkdir -p $DEV" >/dev/null
case $LIBSET in
  opencl) LIBS="libLiteRtOpenClAccelerator.so libLiteRtTopKOpenClSampler.so libGemmaModelConstraintProvider.so";;
  *) LIBS=$(cd "$KIT" && ls *.so);;
esac
for f in litert_lm_advanced_main $LIBS; do
  A push "$KIT/$f" "$DEV/$f" >/dev/null 2>&1 || { say "push failed: $f"; exit 5; }
  mac=$(shasum -a 256 "$KIT/$f" | cut -c1-64); dev=$(dsha $DEV/$f)
  [ "$mac" = "$dev" ] || { say "sha256 mismatch on the phone: $f"; exit 5; }
  listed=$(grep " $f\$" "$KIT/SHA256SUMS" | cut -c1-64)
  say "pushed $f sha256 ${dev:0:12} (SHA256SUMS: ${listed:-not listed})"
done
A shell "chmod 755 $DEV/litert_lm_advanced_main" >/dev/null

# 2. the bundle
if [ "$(A shell "test -f $DEV/$MODEL && echo y" | tr -d '\r')" != y ]; then
  t0=$(date +%s); A push "$BUNDLE" "$DEV/$MODEL" >/dev/null 2>&1 || { say "push failed: bundle"; exit 5; }
  say "pushed $MODEL ($(( $(date +%s) - t0 )) s)"
fi
got=$(dsha $DEV/$MODEL); say "bundle sha256 on the phone ${got:0:16} bytes $(A shell "stat -c %s $DEV/$MODEL" | tr -d '\r') (mac $(shasum -a 256 "$BUNDLE" | cut -c1-16))"
[ "${got:0:16}" = "$(shasum -a 256 "$BUNDLE" | cut -c1-16)" ] || { say "bundle sha256 mismatch"; exit 5; }

# 3. one fresh process; the probe loop on the phone records the peak VmHWM and the exit code (the binary is the
#    backgrounded process itself — a `timeout` wrapper would make $! the wrapper's pid and VmHWM read 4 MB: runs g1–c3)
run_one() { # tag backend A|B
  local tag=$1 be=$2 p=$3 prompt
  [ "$p" = A ] && prompt=$PROMPT_A || prompt=$PROMPT_B
  A shell "rm -f $DEV/*cache* $DEV/*mldrift* $DEV/*.bin" >/dev/null 2>&1   # every process starts without cache files
  local mark=$(A shell "date '+%m-%d %H:%M:%S.000'" | tr -d '\r')
  say "START $tag backend=$be prompt=$p uptime=$(A shell cat /proc/uptime | tr -d '\r' | cut -d' ' -f1) cpu7_max=$(A shell cat /sys/devices/system/cpu/cpufreq/policy6/scaling_max_freq | tr -d '\r') gpu_mhz=$(A shell cat /sys/class/kgsl/kgsl-3d0/clock_mhz | tr -d '\r')"
  A shell "cd $DEV && rm -f run_$tag.log && ( env LD_LIBRARY_PATH=$DEV ./litert_lm_advanced_main --backend=$be --sampler_backend=cpu --model_path=$DEV/$MODEL --input_prompt='$prompt' > run_$tag.log 2>&1 < /dev/null & P=\$!; PEAK=0; T0=\$(date +%s); while kill -0 \$P 2>/dev/null; do V=\$(awk '/VmHWM/{print \$2}' /proc/\$P/status 2>/dev/null); [ -n \"\$V\" ] && [ \"\$V\" -gt \"\$PEAK\" ] && PEAK=\$V; [ \$(( \$(date +%s) - T0 )) -gt 1500 ] && { kill -9 \$P; echo KILLED_AT_1500S; }; sleep 0.2; done; wait \$P; echo EXIT=\$?; echo PEAK_VmHWM_MB=\$((PEAK/1024)) )" > "$OUT/$tag.probe.txt" 2>&1
  A pull "$DEV/run_$tag.log" "$OUT/$tag.log" >/dev/null 2>&1
  A logcat -d -T "$mark" > "$OUT/$tag.logcat.txt" 2>/dev/null
  local acc=$(grep -o 'RegisterAccelerator[^"]*name=[A-Za-z_]*' "$OUT/$tag.log" "$OUT/$tag.logcat.txt" 2>/dev/null | tail -1 | sed 's/.*name=//')
  local cl=$(grep -o 'Replacing [0-9]* out of [0-9]* node(s) with delegate ([A-Za-z_]*)' "$OUT/$tag.log" | sort | uniq -c | tr -s ' ' | tr '\n' ';')
  local ans=$(grep -v -E '^(I|W|E|V|D)[0-9]{4} |^\[|^INFO|^WARNING|^ERROR|^[0-9]{4}-|^$' "$OUT/$tag.log" | head -c 300 | tr '\n' ' ')
  say "END $tag $(tr -d '\r' < "$OUT/$tag.probe.txt" | tr '\n' ' ') accelerator=$acc delegation=[$cl] text_head=[$ans]"
}

for item in $PLAN; do
  IFS=: read -r tag be p <<< "$item"
  run_one "$tag" "$be" "$p"
  sleep 20
done
after=$(dsha $DEV/$MODEL); say "DONE plan=[$PLAN]; bundle sha256 after the runs ${after:0:16}"
