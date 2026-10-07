#!/bin/bash
# s26_cycle_drop_2.sh (round 4): on the Galaxy S26 (SM-S942Q), under the shared hold, run the DDP sessions' benchmark binary
# (gs://litert/binaries/latest, sha256 adac974b...) on gemma-4-E2B-it.litertlm, gpu, prefill 1024 / decode 256 /
# max_num_tokens 1280, with a 1 s thermal + clock log beside it, to see where a second cycle's decode drop comes from:
#   A0: one process without caches (writes the ML Drift caches; = the DDP "first process")
#   A : one process, --num_iterations=3, caches present (= the DDP "measured process" at 3 cycles), 0 s after A0
#   B : three processes, --num_iterations=1 each, 0 s between them, caches present
#   rest 180 s
#   C : A again after the rest
# One run per setting; nothing here is a measurement (phone state not controlled beyond what the log shows).
set -u
S=/private/tmp/claude-501/-Users-USER-code-edge-llm-bench/d21f53ca-5923-4da1-b5fc-7e34ecbf7034/scratchpad
BIN=/private/tmp/claude-501/-Users-USER-code-edge-llm-bench/5f1069b5-75f5-48a0-8cf8-e569a9902f1e/scratchpad/lm-latest
CA=/Users/USER/code/litertlm-convert/community_accel_work
L="$CA/s2_npu_sweep/.device_hold"
NAME=edge-llm-bench/ddp-s25ultra-gemma-gpu-cycle-drop-4
SUP=ddp-s25ultra-lm
SERIAL=RFGL80R6A6H
DEV=/data/local/tmp/ddp-lm-cycle-drop
OUT="$S/s26-cycle-drop-4"; mkdir -p "$OUT"
E2B=gemma-4-E2B-it.litertlm
E2B_SHA=181938105e0eefd105961417e8da75903eacda102c4fce9ce90f50b97139a63c
BIN_SHA=adac974bea147273b5bc64232d808905667eee69587161368146680df92e2d06
A() { adb -s "$SERIAL" "$@"; }
say() { echo "[$(TZ=Asia/Tokyo date '+%F %T')] $*" | tee -a "$OUT/steps.log"; }
dtemp() { A shell "cat /sys/class/thermal/thermal_zone69/temp /sys/class/thermal/thermal_zone59/temp /sys/class/kgsl/kgsl-3d0/clock_mhz" | tr -d '\r' | tr '\n' ' '; }

rel="$S/.s26_cycle_release4"; rm -f "$rel"
( start=$(date +%s); while [ ! -f "$rel" ] && [ $(( $(date +%s) - start )) -lt 14400 ]; do sleep 5; done ) &
kp=$!
python3 "$CA/queue_cli.py" enqueue "$L" "$NAME" "$SUP" 30 >/dev/null
say "QUEUED keeper $kp: $(python3 "$CA/queue_cli.py" list "$L" | tr '\n' ' ' | cut -c1-300)"
if ! python3 "$CA/queue_cli.py" wait "$L" "$NAME" "$kp" --timeout 1200 --poll 5 >> "$OUT/steps.log" 2>&1; then
  python3 "$CA/queue_cli.py" dequeue "$L" "$NAME" >/dev/null; touch "$rel"; say "HOLD_GAVE_UP (20 min in the queue)"; exit 3
fi
say "HOLD_TAKEN: $(head -c 300 "$L")"
LOGPID=""
release() {
  [ -n "$LOGPID" ] && { A shell "rm -f $DEV/.log_on"; sleep 3; kill "$LOGPID" 2>/dev/null; }
  A pull "$DEV/thermal.tsv" "$OUT/thermal.tsv" >/dev/null 2>&1
  A shell "rm -rf $DEV" >/dev/null 2>&1
  python3 "$CA/hold_cli.py" release "$L" "$kp" >/dev/null; touch "$rel"
  say "HOLD_RELEASED: hold now $( [ -f "$L" ] && head -c 200 "$L" || echo free); device dir removed"
}
trap release EXIT

# preflight under the hold
[ "$(A get-state 2>/dev/null)" = "device" ] || { say "PREFLIGHT no adb device"; exit 4; }
host=$(pgrep -fl "run_campaign.py|run_cell.py" | grep -v grep | head -2 | tr '\n' ' ')
say "PREFLIGHT host drivers (expected: the Pixel 8a dashboard matrix only, serial 4C131JEKB15210): ${host:-none}"
case "$host" in *s26*|*S26*|*RFGL80R6A6H*) say "PREFLIGHT a host driver names the S26"; exit 4;; esac
eng=$(A shell "ps -A -o NAME | grep -E 'litert_lm|llama' | head -3" | tr -d '\r')
[ -z "$eng" ] || { say "PREFLIGHT foreign engine on the phone: $eng"; exit 4; }
batt=$(A shell dumpsys battery | grep -E '^  (level|temperature)' | tr -d '\r' | tr '\n' ' ')
say "PREFLIGHT ok: battery $batt free $(A shell df -h /data/local/tmp | tail -1 | awk '{print $4}' | tr -d '\r'); zones battery/sys-therm-0 (m°C) gpu MHz: $(dtemp)"
lvl=$(A shell dumpsys battery | grep -E '^  level' | tr -dc '0-9'); [ "${lvl:-0}" -ge 30 ] || { say "STOP battery level $lvl < 30"; exit 4; }

# one push of the binary and its libraries (the DDP binary is not on the phone: vl/bin has sha 8d1329e9...)
A shell "mkdir -p $DEV" || exit 5
t0=$(date +%s); bytes=0
for f in litert_lm_advanced_main libGemmaModelConstraintProvider.so libLiteRtDispatch_GoogleTensor.so libLiteRtDispatch_MediaTek.so libLiteRtDispatch_Qualcomm.so libLiteRtOpenClAccelerator.so libLiteRtTopKOpenClSampler.so; do
  A push "$BIN/$f" "$DEV/$f" >/dev/null 2>&1 || { say "push failed: $f"; exit 5; }
  bytes=$(( bytes + $(stat -f %z "$BIN/$f") ))
done
say "PUSHED binary + 6 libs: $bytes bytes in $(( $(date +%s) - t0 )) s"
got=$(A shell "chmod 755 $DEV/litert_lm_advanced_main; sha256sum $DEV/litert_lm_advanced_main" | awk '{print $1}' | tr -d '\r')
[ "$got" = "$BIN_SHA" ] && say "sha256 ok litert_lm_advanced_main $got" || { say "sha256 MISMATCH binary $got"; exit 5; }

# the bundle: the copy already on the phone (same file the s26-repro used), sha256 checked
t0=$(date +%s)
A shell "cp /data/local/tmp/edge-llm-bench/vl/models/$E2B $DEV/$E2B"
got=$(A shell "sha256sum $DEV/$E2B" | awk '{print $1}' | tr -d '\r')
[ "$got" = "$E2B_SHA" ] && say "staged $E2B from /data/local/tmp/edge-llm-bench/vl/models (copy on the phone, $(( $(date +%s) - t0 )) s), sha256 ok $got" || { say "sha256 MISMATCH $E2B $got"; exit 5; }

# 1 s thermal + clock log, on the phone, pulled at the end. zones: battery(69) sys-therm-0(59) ac(68) ddr(47)
# cpu-0-*(5..16) cpu-1-*(24..27) gpuss-0..10(36..46); clock_mhz + gpu_busy_percentage of kgsl-3d0; cpu0/cpu2/cpu6/cpu7 cur freq
ZONES="69 59 68 47 5 6 7 8 9 10 11 12 13 14 15 16 24 25 26 27 36 37 38 39 40 41 42 43 44 45 46"
hdr="epoch\tdevtime"; for z in $ZONES; do hdr="$hdr\t$(A shell cat /sys/class/thermal/thermal_zone$z/type | tr -d '\r')"; done
hdr="$hdr\tgpu_mhz\tgpu_busy\tcpu0_khz\tcpu2_khz\tcpu6_khz\tcpu7_khz"
A shell "printf '$hdr\n' > $DEV/thermal.tsv; touch $DEV/.log_on"
A shell "while [ -f $DEV/.log_on ]; do l=\"\$(date +%s)\t\$(date +%H:%M:%S)\"; for z in $ZONES; do l=\"\$l\t\$(cat /sys/class/thermal/thermal_zone\$z/temp)\"; done; l=\"\$l\t\$(cat /sys/class/kgsl/kgsl-3d0/clock_mhz)\t\$(cat /sys/class/kgsl/kgsl-3d0/gpu_busy_percentage | tr -d ' %')\"; for c in 0 2 6 7; do l=\"\$l\t\$(cat /sys/devices/system/cpu/cpu\$c/cpufreq/scaling_cur_freq)\"; done; echo \"\$l\" >> $DEV/thermal.tsv; sleep 1; done" >/dev/null 2>&1 &
LOGPID=$!
sleep 3; say "thermal log running (pid $LOGPID): $(A shell "wc -l < $DEV/thermal.tsv" | tr -d '\r') lines so far"

run() {  # run <tag> <num_iterations> <clear_caches 0|1> [extra flags...]: one process; stdout+stderr and the logcat of its window are kept
  local tag="$1" n="$2" clr="$3"; shift 3; local extra="$*"
  local t0; t0=$(A shell "date '+%m-%d %H:%M:%S.000'" | tr -d '\r')
  [ "$clr" = 1 ] && A shell "rm -f $DEV/*_mldrift_*cache*.bin $DEV/*.xnnpack_cache*"
  local before; before=$(A shell "ls $DEV/*_mldrift_*cache*.bin 2>/dev/null | wc -l" | tr -d '\r ')
  say "START $tag num_iterations=$n extra=[$extra] caches_before=$before zones battery/sys-therm-0 gpu MHz: $(dtemp)"
  A shell "cd $DEV && timeout 900 env LD_LIBRARY_PATH=$DEV ./litert_lm_advanced_main --backend=gpu --model_path=$DEV/$E2B --benchmark=true --benchmark_prefill_tokens=1024 --benchmark_decode_tokens=256 --num_iterations=$n --report_peak_memory_footprint=true --metric_proto_file_path=$DEV/metrics-$tag.pb $extra; echo rc=\$?" > "$OUT/$tag.stdout.txt" 2>&1
  A logcat -d -T "$t0" > "$OUT/$tag.logcat.txt" 2>/dev/null
  A pull "$DEV/metrics-$tag.pb" "$OUT/metrics-$tag.pb" >/dev/null 2>&1
  local src="$OUT/$tag.logcat.txt"
  say "END $tag $(grep -o 'rc=[0-9]*' "$OUT/$tag.stdout.txt" | tail -1)" \
      "prefill=$(grep -o 'Prefill Speed: [0-9.]*' "$src" | awk '{print $3}' | tr '\n' ',')" \
      "decode=$(grep -o 'Decode Speed: [0-9.]*' "$src" | awk '{print $3}' | tr '\n' ',')" \
      "err=$(grep -c -E 'Failed to|Invalid decode|INTERNAL|FATAL' "$src")" \
      "zones battery/sys-therm-0 gpu MHz: $(dtemp)"
}
first_decode() { grep -o 'Decode Speed: [0-9.]*' "$OUT/$1.logcat.txt" | head -1 | awk '{print $3}'; }

# round 4: how Gemma 4 E2B gpu prefill moves with --max_num_tokens. One cycle per process (--num_iterations=1), the
# other arguments as the DDP sessions'. A = no --max_num_tokens (engine default, the Kotlin app's condition),
# B = --max_num_tokens=1280 (DDP), C = --max_num_tokens=4096; A B C three times in turn, 30 s apart, caches present.
# D1 = A's arguments without cache files (cold; it also writes the caches the rest use); D2 = the same at the end.
# Quiet phone only: screen dozing, no other hold. Stop if A's first prefill is under 3000 tok/s.
wake() { A shell "dumpsys power 2>/dev/null | grep -m1 'mWakefulness='" | tr -d '\r '; }
maxtok() { grep -m1 -o 'max_tokens: [0-9]*' "$OUT/$1.logcat.txt" | tail -1; }
w=$(wake); say "SCREEN before the runs: $w"
case "$w" in *Dozing*|*Asleep*) ;; *) say "STOP screen is not dozing ($w): another lane may be using the phone"; exit 6;; esac
run D1 1 1
say "D1 $(maxtok D1) init=$(grep -m1 -o 'Init Total: [0-9.]* ms' "$OUT/D1.logcat.txt")"
sleep 30
for rep in 1 2 3; do
  run A$rep 1 0
  say "A$rep $(maxtok A$rep) init=$(grep -m1 -o 'Init Total: [0-9.]* ms' "$OUT/A$rep.logcat.txt") caches=$(A shell "ls $DEV/*_mldrift_*cache*.bin 2>/dev/null | wc -l" | tr -d '\r ')"
  if [ "$rep" = 1 ]; then
    p1=$(grep -o 'Prefill Speed: [0-9.]*' "$OUT/A1.logcat.txt" | tail -1 | awk '{print $3}')
    low=$(awk -v d="${p1:-0}" 'BEGIN{print (d+0 < 3000) ? 1 : 0}')
    [ "$low" = 1 ] && { say "STOP-CONDITION: A1 prefill ${p1:-none} < 3000 (phone state differs); stopping"; exit 7; }
  fi
  sleep 30
  run B$rep 1 0 --max_num_tokens=1280
  say "B$rep $(maxtok B$rep) init=$(grep -m1 -o 'Init Total: [0-9.]* ms' "$OUT/B$rep.logcat.txt") caches=$(A shell "ls $DEV/*_mldrift_*cache*.bin 2>/dev/null | wc -l" | tr -d '\r ')"
  sleep 30
  run C$rep 1 0 --max_num_tokens=4096
  say "C$rep $(maxtok C$rep) init=$(grep -m1 -o 'Init Total: [0-9.]* ms' "$OUT/C$rep.logcat.txt") caches=$(A shell "ls $DEV/*_mldrift_*cache*.bin 2>/dev/null | wc -l" | tr -d '\r ')"
  sleep 30
done
say "SCREEN after the A/B/C runs: $(wake)"
run D2 1 1
say "D2 $(maxtok D2) init=$(grep -m1 -o 'Init Total: [0-9.]* ms' "$OUT/D2.logcat.txt")"
say "CAPTURES in all windows: $(cat "$OUT"/*.logcat.txt | grep -c 'Capture layer list') touch-boost: $(cat "$OUT"/*.logcat.txt | grep -c 'Touch Boost')"
say "DONE"
