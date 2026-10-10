#!/bin/bash
# s26_reboot_cold.sh (2026-10-10): on the Galaxy S26 (SM-S942Q), under the shared hold, run the DDP sessions' benchmark
# binary (gs://litert/binaries/latest, sha256 adac974b...) at the LiteRT team's test arguments (prefill 1024 / decode 256,
# --max_num_tokens=4096, one cycle per process) to see what a FIRST pass on a freshly booted phone reads, against a first
# pass on the running phone with the model file just written (the shape of the DDP "first process"):
#   R0  gpu  gemma-4-E2B-it   caches cleared, phone up for days, bundle just copied on the phone   (today's push-hot baseline)
#   R0b gpu  same             caches present                                                        (today's cached baseline)
#   reboot, boot completed + 120 s, screen off
#   G1  gpu  gemma-4-E2B-it   caches cleared, first process after the boot (page cache empty, background jobs of a boot)
#   G2  gpu  same             caches present, second process after the boot
#   reboot, boot completed + 120 s, screen off
#   C1  cpu  gemma3-1b-it-int4   caches cleared, first process after the boot
#   C2  cpu  same                caches present
#   push the gemma3 bundle again (overwrites the file = just written), caches cleared
#   C3  cpu  gemma3-1b-it-int4   caches cleared, file just pushed       (push-hot control for the cpu case)
#   C4  cpu  same                caches present
# One run per setting; no thermal control beyond what the log shows. Zones and GPU clock are logged before and after each run.
set -u
BENCH=/Users/USER/code/edge-llm-bench
OUT=$BENCH/results/raw/2026-10-10-s26-reboot-cold; mkdir -p "$OUT"
KIT=${KIT:-/private/tmp/claude-501/-Users-USER-code/7821f881-51f7-49d6-af4d-7b2ed69dbe10/scratchpad/lm-kit}
CA=/Users/USER/code/litertlm-convert/community_accel_work
L="$CA/s2_npu_sweep/.device_hold"
NAME=edge-llm-bench/s26-reboot-cold
SUP=ddp-s25ultra-lm
SERIAL=RFGL80R6A6H
DEV=/data/local/tmp/s26-reboot-cold
E2B=gemma-4-E2B-it.litertlm
E2B_SHA=181938105e0eefd105961417e8da75903eacda102c4fce9ce90f50b97139a63c
G3=gemma3-1b-it-int4.litertlm
G3_LOCAL=/Users/USER/.cache/huggingface/hub/models--litert-community--Gemma3-1B-IT/snapshots/a6306a4e292016480083b73b8dc6f3f939ae04c3/gemma3-1b-it-int4.litertlm
G3_SHA=1325ae366d31950f137c9c357b9fa89448b176d76998180c08ceaca78bba98be
BIN_SHA=adac974bea147273b5bc64232d808905667eee69587161368146680df92e2d06
A() { adb -s "$SERIAL" "$@"; }
say() { echo "[$(TZ=Asia/Tokyo date '+%F %T')] $*" | tee -a "$OUT/steps.log"; }
dtemp() { A shell "cat /sys/class/thermal/thermal_zone69/temp /sys/class/thermal/thermal_zone59/temp /sys/class/kgsl/kgsl-3d0/clock_mhz" 2>/dev/null | tr -d '\r' | tr '\n' ' '; }
wake() { A shell "dumpsys power 2>/dev/null | grep -m1 'mWakefulness='" | tr -d '\r '; }

rel="$OUT/.release"; rm -f "$rel"
( start=$(date +%s); while [ ! -f "$rel" ] && [ $(( $(date +%s) - start )) -lt 7200 ]; do sleep 5; done ) &
kp=$!
python3 "$CA/queue_cli.py" enqueue "$L" "$NAME" "$SUP" 20 >/dev/null
say "QUEUED keeper $kp: $(python3 "$CA/queue_cli.py" list "$L" | tr '\n' ' ' | cut -c1-300)"
if ! python3 "$CA/queue_cli.py" wait "$L" "$NAME" "$kp" --timeout 900 --poll 5 >> "$OUT/steps.log" 2>&1; then
  python3 "$CA/queue_cli.py" dequeue "$L" "$NAME" >/dev/null; touch "$rel"; say "HOLD_GAVE_UP (15 min in the queue)"; exit 3
fi
say "HOLD_TAKEN: $(head -c 300 "$L")"
release() {
  A shell "rm -rf $DEV" >/dev/null 2>&1
  python3 "$CA/hold_cli.py" release "$L" "$kp" >/dev/null; touch "$rel"
  say "HOLD_RELEASED: hold now $( [ -f "$L" ] && head -c 200 "$L" || echo free); device dir removed"
}
trap release EXIT

# preflight under the hold
[ "$(A get-state 2>/dev/null)" = "device" ] || { say "PREFLIGHT no adb device"; exit 4; }
host=$(pgrep -fl "run_campaign.py|run_cell.py" | grep -v grep | head -2 | tr '\n' ' ')
say "PREFLIGHT host drivers: ${host:-none}"
case "$host" in *s26*|*S26*|*RFGL80R6A6H*) say "PREFLIGHT a host driver names the S26"; exit 4;; esac
eng=$(A shell "ps -A -o NAME | grep -E 'litert_lm|llama' | head -3" | tr -d '\r')
[ -z "$eng" ] || { say "PREFLIGHT foreign engine on the phone: $eng"; exit 4; }
batt=$(A shell dumpsys battery | grep -E '^  (level|temperature)' | tr -d '\r' | tr '\n' ' ')
say "PREFLIGHT ok: battery $batt free $(A shell df -h /data/local/tmp | tail -1 | awk '{print $4}' | tr -d '\r'); uptime $(A shell uptime | tr -d '\r'); zones battery/sys-therm-0 (m°C) gpu MHz: $(dtemp)"
lvl=$(A shell dumpsys battery | grep -E '^  level' | tr -dc '0-9'); [ "${lvl:-0}" -ge 30 ] || { say "STOP battery level $lvl < 30"; exit 4; }
w=$(wake); say "SCREEN before the runs: $w"
case "$w" in *Dozing*|*Asleep*) ;; *) say "STOP screen is not dozing ($w): another lane may be using the phone"; exit 6;; esac

# push the binary and its six libraries; sha256 of each checked on the phone
A shell "mkdir -p $DEV" || exit 5
t0=$(date +%s); bytes=0
for f in litert_lm_advanced_main libGemmaModelConstraintProvider.so libLiteRtDispatch_GoogleTensor.so libLiteRtDispatch_MediaTek.so libLiteRtDispatch_Qualcomm.so libLiteRtOpenClAccelerator.so libLiteRtTopKOpenClSampler.so; do
  A push "$KIT/$f" "$DEV/$f" >/dev/null 2>&1 || { say "push failed: $f"; exit 5; }
  bytes=$(( bytes + $(stat -f %z "$KIT/$f") ))
done
say "PUSHED binary + 6 libs: $bytes bytes in $(( $(date +%s) - t0 )) s"
A shell "chmod 755 $DEV/litert_lm_advanced_main; cd $DEV && sha256sum litert_lm_advanced_main *.so" | tr -d '\r' | while read -r s f; do say "sha256 $f ${s:0:12}"; done
got=$(A shell "sha256sum $DEV/litert_lm_advanced_main" | awk '{print $1}' | tr -d '\r')
[ "$got" = "$BIN_SHA" ] || { say "sha256 MISMATCH binary $got"; exit 5; }

# the bundles: E2B = the copy already on the phone; gemma3 = pushed from the Hub cache
t0=$(date +%s)
A shell "cp /data/local/tmp/edge-llm-bench/vl/models/$E2B $DEV/$E2B"
got=$(A shell "sha256sum $DEV/$E2B" | awk '{print $1}' | tr -d '\r')
[ "$got" = "$E2B_SHA" ] && say "staged $E2B (copy on the phone, $(( $(date +%s) - t0 )) s), sha256 ok ${got:0:12}" || { say "sha256 MISMATCH $E2B $got"; exit 5; }
t0=$(date +%s)
A push "$G3_LOCAL" "$DEV/$G3" >/dev/null 2>&1 || { say "push failed: $G3"; exit 5; }
got=$(A shell "sha256sum $DEV/$G3" | awk '{print $1}' | tr -d '\r')
[ "$got" = "$G3_SHA" ] && say "pushed $G3 ($(( $(date +%s) - t0 )) s), sha256 ok ${got:0:12}" || { say "sha256 MISMATCH $G3 $got"; exit 5; }

run() {  # run <tag> <backend> <model> <clear_caches 0|1>: one process, one cycle; stdout+stderr and the logcat of its window are kept
  local tag="$1" be="$2" model="$3" clr="$4"
  local t0; t0=$(A shell "date '+%m-%d %H:%M:%S.000'" | tr -d '\r')
  [ "$clr" = 1 ] && A shell "rm -f $DEV/*_mldrift_*cache*.bin $DEV/*xnnpack*cache* $DEV/*.xnnpack_cache*"
  local before; before=$(A shell "ls $DEV/*cache* 2>/dev/null | wc -l" | tr -d '\r ')
  say "START $tag backend=$be model=$model caches_before=$before uptime=$(A shell 'cat /proc/uptime' | awk '{print $1}' | tr -d '\r')s zones battery/sys-therm-0 gpu MHz: $(dtemp)"
  A shell "cd $DEV && timeout 900 env LD_LIBRARY_PATH=$DEV ./litert_lm_advanced_main --backend=$be --model_path=$DEV/$model --benchmark=true --benchmark_prefill_tokens=1024 --benchmark_decode_tokens=256 --max_num_tokens=4096 --num_iterations=1 --report_peak_memory_footprint=true --metric_proto_file_path=$DEV/metrics-$tag.pb; echo rc=\$?" > "$OUT/$tag.stdout.txt" 2>&1
  A logcat -d -T "$t0" > "$OUT/$tag.logcat.txt" 2>/dev/null
  A pull "$DEV/metrics-$tag.pb" "$OUT/metrics-$tag.pb" >/dev/null 2>&1
  local src="$OUT/$tag.logcat.txt"
  say "END $tag $(grep -o 'rc=[0-9]*' "$OUT/$tag.stdout.txt" | tail -1)" \
      "prefill=$(grep -o 'Prefill Speed: [0-9.]*' "$src" | awk '{print $3}' | tr '\n' ',')" \
      "decode=$(grep -o 'Decode Speed: [0-9.]*' "$src" | awk '{print $3}' | tr '\n' ',')" \
      "ttft=$(grep -o -i 'Time To First Token: [0-9.]*' "$src" | awk '{print $5}' | tr '\n' ',')" \
      "init=$(grep -m1 -o 'Init Total: [0-9.]* ms' "$src")" \
      "max_tokens=$(grep -m1 -o 'max_tokens: [0-9]*' "$src" | awk '{print $2}')" \
      "err=$(grep -c -E 'Failed to|Invalid decode|INTERNAL|FATAL' "$src")" \
      "caches_after=$(A shell "ls $DEV/*cache* 2>/dev/null | wc -l" | tr -d '\r ')" \
      "zones battery/sys-therm-0 gpu MHz: $(dtemp)"
}
reboot_and_settle() {  # reboot, wait for boot_completed, then 120 s, then screen off
  say "REBOOT $1: uptime before $(A shell 'cat /proc/uptime' | awk '{print $1}' | tr -d '\r')s"
  A reboot
  sleep 20
  local t0=$(date +%s)
  A wait-for-device
  while [ "$(A shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" != "1" ]; do
    sleep 3; [ $(( $(date +%s) - t0 )) -lt 420 ] || { say "REBOOT $1: boot_completed not seen in 7 min"; exit 8; }
  done
  say "REBOOT $1: boot_completed after $(( $(date +%s) - t0 )) s; settling 120 s"
  sleep 120
  A shell "input keyevent 223" >/dev/null 2>&1   # KEYCODE_SLEEP: screen off (the lock screen is on after a boot)
  sleep 15
  say "REBOOT $1: settled; uptime $(A shell 'cat /proc/uptime' | awk '{print $1}' | tr -d '\r')s; screen $(wake); battery $(A shell dumpsys battery | grep -E '^  (level|temperature)' | tr -d '\r' | tr '\n' ' '); load $(A shell 'cat /proc/loadavg' | tr -d '\r')"
  ls "$DEV" >/dev/null 2>&1; A shell "ls $DEV/$E2B $DEV/$G3 $DEV/litert_lm_advanced_main" | tr -d '\r' | tr '\n' ' ' | sed 's/^/  files after boot: /'; echo
}

run R0 gpu "$E2B" 1
sleep 30
run R0b gpu "$E2B" 0
reboot_and_settle 1
run G1 gpu "$E2B" 1
sleep 30
run G2 gpu "$E2B" 0
reboot_and_settle 2
run C1 cpu "$G3" 1
sleep 30
run C2 cpu "$G3" 0
sleep 30
t0=$(date +%s); A push "$G3_LOCAL" "$DEV/$G3" >/dev/null 2>&1; say "re-pushed $G3 ($(( $(date +%s) - t0 )) s), sha256 $(A shell "sha256sum $DEV/$G3" | awk '{print substr($1,1,12)}' | tr -d '\r')"
run C3 cpu "$G3" 1
sleep 30
run C4 cpu "$G3" 0
say "DONE"
