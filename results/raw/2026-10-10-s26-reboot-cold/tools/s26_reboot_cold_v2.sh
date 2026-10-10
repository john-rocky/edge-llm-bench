#!/bin/bash
# s26_reboot_cold_v2.sh (2026-10-10 09:2x): continuation of s26_reboot_cold.sh after its REBOOT 1 (09:08:24 JST).
# v1 rebooted the S26 and then waited for adb for ten minutes: after a reboot the phone shows no adb device until its
# first unlock (the user unlocks it once). v1 was stopped (its hold released); this script takes the hold, waits for the
# phone to appear, confirms the boot is the 09:08 one (uptime), and runs the post-boot processes without a second reboot:
#   G1  gpu  gemma-4-E2B-it      caches cleared, first process of this model since the boot (its file not read since the boot)
#   G2  gpu  same                caches present
#   copy the E2B bundle again on the phone (= the file just written, the DDP "first process after the push" shape)
#   G3  gpu  gemma-4-E2B-it      caches cleared, file just written
#   G4  gpu  same                caches present
#   C1  cpu  gemma3-1b-it-int4   caches cleared, first process of this model since the boot (file not read since the boot)
#   C2  cpu  same                caches present
#   push the gemma3 bundle again from the Mac (file just written)
#   C3  cpu  gemma3-1b-it-int4   caches cleared, file just pushed
#   C4  cpu  same                caches present
# The bundles are not sha256-checked before the runs (reading them would warm the page cache); their sizes are listed and
# the sha256 of each is taken AFTER the runs. v1's R0 / R0b (before the reboot) stay in steps.log as the pre-reboot rows.
set -u
BENCH=/Users/USER/code/edge-llm-bench
OUT=$BENCH/results/raw/2026-10-10-s26-reboot-cold; mkdir -p "$OUT"
CA=/Users/USER/code/litertlm-convert/community_accel_work
L="$CA/s2_npu_sweep/.device_hold"
NAME=edge-llm-bench/s26-reboot-cold-v2
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
say() { echo "[$(TZ=Asia/Tokyo date '+%F %T')] [v2] $*" | tee -a "$OUT/steps.log"; }
dtemp() { A shell "cat /sys/class/thermal/thermal_zone69/temp /sys/class/thermal/thermal_zone59/temp /sys/class/kgsl/kgsl-3d0/clock_mhz" 2>/dev/null | tr -d '\r' | tr '\n' ' '; }
wake() { A shell "dumpsys power 2>/dev/null | grep -m1 'mWakefulness='" | tr -d '\r '; }
up() { A shell 'cat /proc/uptime' 2>/dev/null | awk '{print $1}' | tr -d '\r'; }

rel="$OUT/.release-v2"; rm -f "$rel"
( start=$(date +%s); while [ ! -f "$rel" ] && [ $(( $(date +%s) - start )) -lt 7200 ]; do sleep 5; done ) &
kp=$!
python3 "$CA/queue_cli.py" enqueue "$L" "$NAME" "$SUP" 25 >/dev/null
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

# wait for the phone (first unlock after the 09:08 reboot), up to 60 min
say "WAITING for adb: the S26 shows no device until its first unlock after the reboot"
t0=$(date +%s); n=0
while [ "$(A get-state 2>/dev/null | tr -d '\r')" != "device" ]; do
  sleep 5; n=$((n+1)); [ $((n % 12)) -eq 0 ] && say "still waiting ($(( $(date +%s) - t0 )) s)"
  [ $(( $(date +%s) - t0 )) -lt 3600 ] || { say "no adb device in 60 min; giving up"; exit 8; }
done
say "adb device after $(( $(date +%s) - t0 )) s; boot_completed=$(A shell getprop sys.boot_completed | tr -d '\r'); uptime $(up) s; screen $(wake)"
u=$(up); case "$u" in ''|*[!0-9.]*) say "uptime unreadable: '$u'"; exit 9;; esac
if [ "${u%.*}" -gt 20000 ]; then say "STOP uptime ${u%.*} s > 5.5 h: not the 09:08 boot"; exit 9; fi
# preflight
host=$(pgrep -fl "run_campaign.py|run_cell.py" | grep -v grep | head -2 | tr '\n' ' ')
say "PREFLIGHT host drivers: ${host:-none}"
case "$host" in *s26*|*S26*|*RFGL80R6A6H*) say "PREFLIGHT a host driver names the S26"; exit 4;; esac
eng=$(A shell "ps -A -o NAME | grep -E 'litert_lm|llama' | head -3" | tr -d '\r')
[ -z "$eng" ] || { say "PREFLIGHT foreign engine on the phone: $eng"; exit 4; }
batt=$(A shell dumpsys battery | grep -E '^  (level|temperature)' | tr -d '\r' | tr '\n' ' ')
say "PREFLIGHT ok: battery $batt free $(A shell df -h /data/local/tmp | tail -1 | awk '{print $4}' | tr -d '\r'); load $(A shell 'cat /proc/loadavg' | tr -d '\r'); zones battery/sys-therm-0 (m°C) gpu MHz: $(dtemp)"
lvl=$(A shell dumpsys battery | grep -E '^  level' | tr -dc '0-9'); [ "${lvl:-0}" -ge 30 ] || { say "STOP battery level $lvl < 30"; exit 4; }
# the files pushed by v1 must still be there (sizes only; no read of the bundles before the runs)
say "FILES after the boot: $(A shell "ls -l $DEV/litert_lm_advanced_main $DEV/$E2B $DEV/$G3" | tr -d '\r' | awk '{print $5, $8}' | tr '\n' ';')"
got=$(A shell "sha256sum $DEV/litert_lm_advanced_main" | awk '{print $1}' | tr -d '\r')
[ "$got" = "$BIN_SHA" ] || { say "sha256 MISMATCH binary $got"; exit 5; }
say "sha256 ok binary ${got:0:12}; caches present now: $(A shell "ls $DEV/*cache* 2>/dev/null | wc -l" | tr -d '\r ')"
# settle, then screen off (the phone is unlocked and lit right after the unlock)
sleep 60
A shell "input keyevent 223" >/dev/null 2>&1
sleep 15
say "SETTLED: uptime $(up) s; screen $(wake); load $(A shell 'cat /proc/loadavg' | tr -d '\r')"

run() {  # run <tag> <backend> <model> <clear_caches 0|1>: one process, one cycle; stdout+stderr and the logcat of its window are kept
  local tag="$1" be="$2" model="$3" clr="$4"
  local t0; t0=$(A shell "date '+%m-%d %H:%M:%S.000'" | tr -d '\r')
  [ "$clr" = 1 ] && A shell "rm -f $DEV/*_mldrift_*cache*.bin $DEV/*xnnpack*cache* $DEV/*.xnnpack_cache*"
  local before; before=$(A shell "ls $DEV/*cache* 2>/dev/null | wc -l" | tr -d '\r ')
  say "START $tag backend=$be model=$model caches_before=$before uptime=$(up)s zones battery/sys-therm-0 gpu MHz: $(dtemp)"
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

run G1 gpu "$E2B" 1
sleep 30
run G2 gpu "$E2B" 0
sleep 30
t0=$(date +%s); A shell "cp /data/local/tmp/edge-llm-bench/vl/models/$E2B $DEV/$E2B"; say "re-copied $E2B on the phone ($(( $(date +%s) - t0 )) s)"
run G3 gpu "$E2B" 1
sleep 30
run G4 gpu "$E2B" 0
sleep 30
run C1 cpu "$G3" 1
sleep 30
run C2 cpu "$G3" 0
sleep 30
t0=$(date +%s); A push "$G3_LOCAL" "$DEV/$G3" >/dev/null 2>&1; say "re-pushed $G3 from the Mac ($(( $(date +%s) - t0 )) s)"
run C3 cpu "$G3" 1
sleep 30
run C4 cpu "$G3" 0
say "sha256 after the runs: $(A shell "cd $DEV && sha256sum $E2B $G3" | tr -d '\r' | awk '{print substr($1,1,12), $2}' | tr '\n' ';')  (expected ${E2B_SHA:0:12} / ${G3_SHA:0:12})"
say "DONE"
