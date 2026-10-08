#!/usr/bin/env bash
# Android driver for the ExecuTorch arm's cells (matrices/dashboard-executorch-v1-android.cells,
# docs/executorch-arm-v1.md) on one phone: every cell's cold launches through android/bench/run_campaign.py,
# one model at a time, inside device-hold windows of at most WINDOW_MIN minutes taken from the shared
# phone's queue (community_accel_work/queue_cli.py, hold_cli.py). Run on the Galaxy S26 and the Pixel 8a.
#
#   android/scripts/executorch_matrix_android.sh <state_dir> [<model> ...]
#       models: 0.6B 1.7B E2B 4B E4B (default: the five, lightest first; pass only the rows that run on
#       the phone, a row exclude-on= the phone would take a window for nothing)
#   android/scripts/executorch_matrix_android.sh --plan [<model> ...]   # the windows the estimates give, no device
#
# A unit is one cells row: a one-row cells file run by run_campaign.py, with its cold launches,
# cooldowns and capture gate. A window holds the units of one model while the next unit's estimate
# (its cooldowns and launches plus one gate retry, unit_estimate) fits in what is left of it, else it
# closes and the next window pushes the model again. Units already in <state_dir>/units_done.tsv are
# skipped, so a second call continues where the first stopped; MAX_WINDOWS=<n> stops after n windows.
#
# One window:
#   enqueue <QUEUE_PREFIX>-<model>[-<task>] -> keeper (this script's --keeper mode: its pid owns the
#   hold; it stops the window's run and cleans the phone when the window's time runs out or this
#   driver is gone) -> queue_cli.py wait -> the phone's state, other lanes' engines on it, free space
#   -> the files the run overwrites outside its own names are pulled to the window's dir -> the
#   runner directory is pushed (sha256 checked) -> per unit: battery <= BATTERY_MAX_C (up to
#   BATTERY_WAIT s), the skin gate (below), then run_campaign.py in a session of its own (stopped CUT_S s
#   before the window ends) -> what was pushed is removed and every overwritten file put back, a
#   listing checks it -> the keeper gives the hold back.
#
# Skin gate: before each unit, `dumpsys thermalservice` once per SKIN_POLL s until the SKIN_SENSOR value
# from the "Current temperatures from HAL" block is <= SKIN_MAX_C. The "Cached temperatures" block holds
# the value of the HAL's last throttling-status callback, not the temperature now: on the Galaxy S26 it
# reads 37.9 for as long as the status stays 0 (the value at which it last fell back below 38.0), so it is
# logged beside the current value and gates only with SKIN_SOURCE=cached. A unit whose reading stays above
# SKIN_MAX_C for SKIN_WAIT s is not started: the window goes back (phone cleaned, hold released) and the
# next window tries again; SKIN_STRIKES such windows in a row stop the driver. Every gate is a row of
# <state_dir>/skin_gate.tsv (readings, threshold, seconds waited, result).
# Records land where run_campaign.py writes them (results/raw/$CAMPAIGN/app-path-android, or under
# BENCH_RAW_ROOT); <state_dir> keeps driver.log, units_done.tsv and per window the phone's state, the
# listings before and after, the queue lines and each unit's console.
#
# Env (default):
#   SERIAL (RFGL80R6A6H, the Galaxy S26). The phone's entry in SCHEDULE (ops/dashboard-v1/schedule.json; a
#   test points it elsewhere), the device whose serial is SERIAL, gives the defaults of CPU_MASK, HOLD,
#   HOLD_ALSO and CAMPAIGN; a serial the schedule does not list keeps the forms in brackets. --plan prints them.
#   CPU_MASK (the entry's cpu_mask: f0 on the Pixel 8a, empty on the S26; []): BENCH_CPU_MASK for
#     run_cell.py, the launch's taskset mask, empty = no taskset (devices/*.md say each phone's choice)
#   HOLD (the entry's hold; [community_accel_work/s2_npu_sweep/.device_hold])
#   HOLD_ALSO (the entry's hold_also_check, space-separated; [$HOLD.s26 $HOLD.$SERIAL]): the phone's other
#     hold files, read before any adb call of a window
#   CAMPAIGN (<date of the first call>-dashboard-executorch-v1-<the entry's key; [s26]>-android, kept in
#   <state_dir>/CAMPAIGN; the team dashboard reads only campaigns named with "dashboard")
#   CELLS (<repo>/matrices/dashboard-executorch-v1-android.cells)
#   ET_MODEL_DIR (~/code/edge-llm-bench/models/executorch)  BENCH_ANDROID_BIN_DIR (~/code/edge-llm-bench/android/bin)
#   QUEUE_PREFIX (et-r5-s26)  SUPERVISOR (edge-llm-bench-24)
#   WINDOW_MIN (45)  MARGIN_S (180: kept free at a window's end before a unit starts)  CUT_S (150)
#   WAIT_TIMEOUT (36000)  ROUND_HOURS (10)  MAX_WINDOWS (no limit)
#   NO_NEW_WINDOW_AFTER (epoch: no window is queued or started from then on)
#   HARD_STOP (epoch: every window ends, phone clean and hold back, before it; a window whose first unit
#     would not fit is not started) -- e.g. the weekly job's firing on the same phone
#   EVIDENCE_DIR (<state_dir>/evidence: the phone's power and cap state read at each window's start and end)
#   BATTERY_MAX_C (36.0)  BATTERY_WAIT (600)
#   SKIN_SENSOR (SKIN; empty = no skin gate)  SKIN_SOURCE (current | cached)  SKIN_MAX_C (the sensor's first
#   hot throttling threshold in the dump's "Temperature static thresholds from HAL" minus SKIN_MARGIN_C (2.0);
#   36.0 when the dump has none)  SKIN_WAIT (900)  SKIN_POLL (30)  SKIN_STRIKES (3)
#   LAUNCH_PROBES (empty; e.g. "3 10"): seconds after each launch's adb shell appears on the host at which
#     the phone's whole `dumpsys thermalservice` and every policy's scaling_cur_freq / scaling_max_freq are
#     read once (read only, two adb shells per launch; <window>/<unit>.probes.txt, and the campaign's
#     LAUNCH_PROBES.txt says which units had them)
#   COOLDOWN (120) and GATE_COOLDOWN (180) as run_campaign.py reads them; its other env passes through
#   (THERMAL_WAIT, CPUCAP_WAIT, GATE_RETRY, BENCH_RAW_ROOT, BENCH_LOCK_DIR). BENCH_SITTING,
#   BENCH_SESSION_DEADLINE, BENCH_STRICT_SMOKE and ROUNDS are unset for the units (a by-hand matrix).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SELF="$REPO_ROOT/android/scripts/$(basename "$0")"
SERIAL="${SERIAL:-RFGL80R6A6H}"
schedule_entry() {  # <schedule.json> <serial>: the device's key, cpu_mask, hold, hold_also_check, one per line
  python3 - "$1" "$2" <<'PY' 2>/dev/null
import json, os, sys
for key, dev in json.load(open(sys.argv[1])).get("devices", {}).items():
    if dev.get("serial") == sys.argv[2]:
        print(key)
        print(dev.get("cpu_mask", ""))
        print(os.path.expanduser(dev.get("hold") or ""))
        print(" ".join(os.path.expanduser(p) for p in dev.get("hold_also_check", [])))
        break
PY
}
SCHEDULE="${SCHEDULE:-$REPO_ROOT/ops/dashboard-v1/schedule.json}"
ENTRY="$(schedule_entry "$SCHEDULE" "$SERIAL" || true)"
DEV_KEY="$(echo "$ENTRY" | sed -n 1p)"
ENTRY_MASK="$(echo "$ENTRY" | sed -n 2p)"
if [[ -n "${CPU_MASK+x}" ]]; then MASK_SOURCE=env
else CPU_MASK="$ENTRY_MASK"; MASK_SOURCE="${DEV_KEY:+schedule.json $DEV_KEY}"; MASK_SOURCE="${MASK_SOURCE:-no schedule entry}"; fi
CAMPAIGN_ENV="${CAMPAIGN:-}"
CELLS="${CELLS:-$REPO_ROOT/matrices/dashboard-executorch-v1-android.cells}"
export ET_MODEL_DIR="${ET_MODEL_DIR:-$HOME/code/edge-llm-bench/models/executorch}"
export BENCH_ANDROID_BIN_DIR="${BENCH_ANDROID_BIN_DIR:-$HOME/code/edge-llm-bench/android/bin}"
CAW="$HOME/code/litertlm-convert/community_accel_work"
HOLD="${HOLD:-$(echo "$ENTRY" | sed -n 3p)}"
HOLD="${HOLD:-$CAW/s2_npu_sweep/.device_hold}"
if [[ -z "${HOLD_ALSO+x}" ]]; then
  HOLD_ALSO="$(echo "$ENTRY" | sed -n 4p)"
  [[ -n "$DEV_KEY" ]] || HOLD_ALSO="$HOLD.s26 $HOLD.$SERIAL"
fi
# the keeper (this script again, --keeper) reads the same phone
export SERIAL CPU_MASK HOLD HOLD_ALSO
QCLI="${QCLI:-$CAW/queue_cli.py}"
HCLI="${HCLI:-$CAW/hold_cli.py}"
QUEUE_PREFIX="${QUEUE_PREFIX:-et-r5-s26}"
SUPERVISOR="${SUPERVISOR:-edge-llm-bench-24}"
WINDOW_MIN="${WINDOW_MIN:-45}"
MARGIN_S="${MARGIN_S:-180}"
CUT_S="${CUT_S:-150}"
WAIT_TIMEOUT="${WAIT_TIMEOUT:-36000}"
ROUND_HOURS="${ROUND_HOURS:-10}"
MAX_WINDOWS="${MAX_WINDOWS:-0}"
NO_NEW_WINDOW_AFTER="${NO_NEW_WINDOW_AFTER:-}"
HARD_STOP="${HARD_STOP:-}"
BATTERY_MAX_C="${BATTERY_MAX_C:-36.0}"
BATTERY_WAIT="${BATTERY_WAIT:-600}"
SKIN_SENSOR="${SKIN_SENSOR-SKIN}"
SKIN_SOURCE="${SKIN_SOURCE:-current}"
SKIN_MAX_C_ENV="${SKIN_MAX_C:-}"
SKIN_MARGIN_C="${SKIN_MARGIN_C:-2.0}"
SKIN_WAIT="${SKIN_WAIT:-900}"
SKIN_POLL="${SKIN_POLL:-30}"
SKIN_STRIKES="${SKIN_STRIKES:-3}"
case "$SKIN_SOURCE" in current|cached) ;; *) echo "ERROR: SKIN_SOURCE is current or cached, not $SKIN_SOURCE" >&2; exit 2 ;; esac
LAUNCH_PROBES="${LAUNCH_PROBES:-}"
COOLDOWN="${COOLDOWN:-120}"
GATE_COOLDOWN="${GATE_COOLDOWN:-180}"
ET_TAG="${BENCH_EXECUTORCH_TAG:-v1.5.1}"
DEV=/data/local/tmp/llmbench
RUNNER_DIR="executorch-$ET_TAG"
RUNNERS="llama_main gemma4_e2e_runner"
# run_cell.py writes or overwrites these outside a model's own names: pulled before a window, put
# back (or removed when they were absent) after it
SHARED_FILES="prompts/short-chat.txt prompts/long-context-1024-gen256.txt run_out.txt run_err.txt"
WINDOW_S=$((WINDOW_MIN * 60))

now() { date '+%Y-%m-%d %H:%M:%S'; }
log() { echo "$(now) $*" | tee -a "$STATE/driver.log"; }
adbs() { adb -s "$SERIAL" "$@" </dev/null; }

model_pattern() {  # a model key -> the cells model id's prefix
  case "$1" in
    0.6B) echo "own-export/Qwen3-0[.]6B-" ;;
    1.7B) echo "own-export/Qwen3-1[.]7B-" ;;
    4B) echo "own-export/Qwen3-4B-" ;;
    E2B) echo "own-export/gemma-4-E2B-" ;;
    E4B) echo "own-export/gemma-4-E4B-" ;;
    *) return 1 ;;
  esac
}
model_rows() {  # the model's cells rows, in file order (comments and blank lines dropped)
  sed 's/#.*//' "$CELLS" | grep -E "^android[[:space:]]+executorch[[:space:]]+$(model_pattern "$1")" || true
}
field() { echo "$1" | awk -v n="$2" '{print $n}'; }
opt() {  # <row> <key>: the value of the row's key= option, empty when absent
  local w
  for w in $1; do [[ "$w" == "$2="* ]] && { echo "${w#*=}"; return 0; }; done
  return 0
}
task_label() { case "$1" in short-chat) echo short ;; long-context-1024-gen256) echo 1k ;; *) echo "$1" ;; esac; }
launch_estimate() {  # <model> <task>: one launch's wall seconds with run_cell's own probes (a ceiling)
  case "$1:$2" in
    0.6B:short-chat) echo 15 ;; 0.6B:*) echo 30 ;;
    1.7B:short-chat) echo 20 ;; 1.7B:*) echo 45 ;;
    E2B:short-chat) echo 40 ;; E2B:*) echo 75 ;;
    4B:short-chat) echo 40 ;; 4B:*) echo 100 ;;
    E4B:short-chat) echo 60 ;; E4B:*) echo 150 ;;
    *) echo 150 ;;
  esac
}
unit_estimate() {  # <model> <row>: run_campaign's 3 launches, each after its cooldown, plus one gate retry
  local task cooldown l
  task="$(field "$2" 4)"; cooldown="$(opt "$2" cooldown)"; cooldown="${cooldown:-$COOLDOWN}"
  l="$(launch_estimate "$1" "$task")"
  echo $((3 * (cooldown + l) + GATE_COOLDOWN + 2 * COOLDOWN + 3 * l + 60))
}
unit_done() { [[ -f "$STATE/units_done.tsv" ]] && grep -q -F -x "$1	$2" "$STATE/units_done.tsv"; }
dev_prefix() {  # <row>: run_cell.ensure_model's device name for the row's .pte, without .pte
  local id file
  id="$(field "$1" 3)"; file="$(opt "$1" file)"
  echo "$DEV/models/${id//\//_}_${file%.pte}"
}

holds() {  # <pid>: the hold file names this pid
  python3 - "$HOLD" "$1" <<'PY' 2>/dev/null
import json, sys
try:
    sys.exit(0 if json.load(open(sys.argv[1])).get("pid") == int(sys.argv[2]) else 1)
except Exception:
    sys.exit(1)
PY
}

device_state() {  # the phone's state now: build, thermal, battery, screen, cpufreq caps, free space, uptime, memory and swap
  adbs shell "echo model=\$(getprop ro.product.model) android=\$(getprop ro.build.version.release) \
patch=\$(getprop ro.build.version.security_patch) soc=\$(getprop ro.soc.model); \
dumpsys thermalservice | grep -m1 'Thermal Status'; \
dumpsys battery | grep -E '^  (level|temperature|status|AC powered|USB powered):'; \
dumpsys power | grep -m1 mWakefulness=; echo stay_on_while_plugged_in=\$(settings get global stay_on_while_plugged_in); \
for p in /sys/devices/system/cpu/cpufreq/policy*; do h=; m=; r=; read h <\$p/cpuinfo_max_freq; \
read m <\$p/scaling_max_freq; read r <\$p/related_cpus; echo \"CPUFREQ \${p##*/} hw=\$h max=\$m cpus=\$r\"; done; \
df -h /data | tail -1; echo uptime=\$(cat /proc/uptime); grep -E '^(MemTotal|MemAvailable|SwapTotal|SwapFree):' /proc/meminfo"
}

cap_evidence() {  # <window dir> <pre|post>: the phone's power, thermal and cpufreq-cap state, read only
  mkdir -p "$EVIDENCE_DIR"
  {
    echo "== $(now) $(basename "$1") $2"
    echo "== dumpsys thermalservice"; adbs shell "dumpsys thermalservice"
    echo "== /sys/class/power_supply/battery"
    adbs shell "for f in status capacity temp current_now charge_type; do if [ -r /sys/class/power_supply/battery/\$f ]; then echo \"\$f=\$(cat /sys/class/power_supply/battery/\$f)\"; else echo \"\$f: not readable\"; fi; done"
    echo "== scaling_max_freq / cpuinfo_max_freq"
    adbs shell "for p in /sys/devices/system/cpu/cpufreq/policy*; do echo \"\${p##*/} \$(cat \$p/scaling_max_freq) / \$(cat \$p/cpuinfo_max_freq)\"; done"
    echo "== dumpsys battery | head -20"; adbs shell "dumpsys battery | head -20"
    for ns in global system secure; do
      echo "== settings list $ns (power|perf|processing|battery_protect|protect)"
      adbs shell "settings list $ns | grep -i -E 'power|perf|processing|battery_protect|protect'; true"
    done
    echo "== dumpsys battery (plugged|status|level|powered)"; adbs shell "dumpsys battery | grep -i -E 'plugged|status|level|powered'; true"
    echo "== settings list global (power|perf|cpu|limit|processing)"
    adbs shell "settings list global | grep -i -E 'power|perf|cpu|limit|processing'; true"
    echo "== cpufreq policy governor / related_cpus"
    adbs shell "for p in /sys/devices/system/cpu/cpufreq/policy*; do echo \"\${p##*/} governor=\$(cat \$p/scaling_governor) related_cpus=\$(cat \$p/related_cpus)\"; done"
  } >"$EVIDENCE_DIR/$(basename "$1")-$2.txt" 2>&1 || true
}

skin_parse() {  # `dumpsys thermalservice` on stdin -> "<cached> <its status> <current> <its status> <first hot threshold>"
  # for SKIN_SENSOR, "-" for each value the dump does not have (the blocks: Cached temperatures, Current
  # temperatures from HAL, Temperature static thresholds from HAL; a NaN threshold is none)
  awk -v s="$SKIN_SENSOR" '
    /^Cached temperatures:/ { sec = "cached"; next }
    /^Current temperatures from HAL:/ { sec = "current"; next }
    /^Temperature static thresholds from HAL:/ { sec = "thresh"; next }
    /^[^[:space:]]/ { sec = "" }
    index($0, "mName=" s ",") == 0 { next }
    sec == "cached" || sec == "current" {
      v = $0; sub(/.*mValue=/, "", v); sub(/,.*/, "", v)
      st = $0; sub(/.*mStatus=/, "", st); sub(/[^0-9].*/, "", st)
      val[sec] = v; stat[sec] = st
    }
    sec == "thresh" {
      t = $0; sub(/.*mHotThrottlingThresholds=\[/, "", t); sub(/[],].*/, "", t)
      if (t ~ /^-?[0-9]+([.][0-9]+)?$/) hot1 = t
    }
    function d(x) { return x == "" ? "-" : x }
    END { print d(val["cached"]), d(stat["cached"]), d(val["current"]), d(stat["current"]), d(hot1) }'
}
skin_read() {  # the phone's SKIN_SENSOR now (skin_parse's five fields), empty when the dump could not be read
  local out
  out="$(adbs shell "dumpsys thermalservice" 2>/dev/null || true)"
  [[ "$out" == *"Thermal Status"* ]] || return 0
  echo "$out" | skin_parse
}
skin_line() {  # a device-state line from skin_read's fields
  local r; r="$(skin_read)"
  [[ -n "$r" ]] || { echo "SKIN_GATE ${SKIN_SENSOR:-off}: thermalservice not read"; return 0; }
  set -- $r
  echo "SKIN_GATE ${SKIN_SENSOR:-off}: current $3 (status $4), cached $1 (status $2), first hot threshold $5"
}
skin_max() {  # <first hot threshold or -> -> the gate's maximum and where it comes from
  if [[ -n "$SKIN_MAX_C_ENV" ]]; then echo "$SKIN_MAX_C_ENV SKIN_MAX_C"
  elif [[ "$1" != - ]]; then awk -v t="$1" -v m="$SKIN_MARGIN_C" 'BEGIN { printf "%.1f hot-threshold-%s-minus-%s\n", t - m, t, m }'
  else echo "36.0 no-hot-threshold-in-the-dump"; fi
}

skin_gate() {  # <window dir> <model> <task> <deadline epoch> -> 0 run the unit, 1 above SKIN_MAX_C for SKIN_WAIT s (the
  # window goes back), 2 the deadline came first (no time left in the window), 3 no SKIN_SENSOR in the dump,
  # 4 the dump could not be read; SKIN_GATE_WAITED = the seconds waited, one row of skin_gate.tsv either way
  local ws=$1 model=$2 task=$3 t0 deadline r cached cst cur ccs hot1 max maxsrc reading first="" last="" polls=0 absent=0 rc
  SKIN_GATE_WAITED=0
  [[ -n "$SKIN_SENSOR" ]] || return 0
  t0=$(date +%s); deadline=$((t0 + SKIN_WAIT)); (( $4 < deadline )) && deadline=$4
  [[ -s "$STATE/skin_gate.tsv" ]] || printf 'time\twindow\tmodel\ttask\tsensor\tsource\thot1_c\tmax_c\tmax_from\tfirst_c\tlast_c\tcached_c\tcurrent_c\twaited_s\tpolls\tresult\n' >"$STATE/skin_gate.tsv"
  cached=-; cur=-; hot1=-; max=-; maxsrc=-
  while :; do
    r="$(skin_read)"; polls=$((polls + 1))
    if [[ -n "$r" ]]; then
      read -r cached cst cur ccs hot1 <<<"$r"
      read -r max maxsrc <<<"$(skin_max "$hot1")"
      if [[ "$SKIN_SOURCE" == cached ]]; then reading=$cached; else reading=$cur; fi
      if [[ "$reading" == - ]]; then
        absent=$((absent + 1))
        # a dump without the sensor twice: waiting does not bring it
        if (( absent >= 2 )); then rc=3; break; fi
      else
        absent=0; [[ -n "$first" ]] || first=$reading; last=$reading
        if awk -v r="$reading" -v m="$max" 'BEGIN { exit !(r <= m) }'; then rc=0; break; fi
        (( polls > 1 )) || log "  $SKIN_SENSOR $reading C ($SKIN_SOURCE; cached $cached, current $cur) > $max ($maxsrc): waiting up to $(( deadline - t0 )) s"
      fi
    fi
    if (( $(date +%s) >= deadline )); then
      if [[ -z "$first" && "$absent" == 0 ]]; then rc=4
      elif (( deadline < t0 + SKIN_WAIT )); then rc=2
      else rc=1; fi
      break
    fi
    local nap=$(( absent > 0 ? 5 : SKIN_POLL )) left=$(( deadline - $(date +%s) ))
    (( left < nap )) && nap=$(( left > 1 ? left : 1 ))
    sleep "$nap"
  done
  SKIN_GATE_WAITED=$(( $(date +%s) - t0 ))
  local result
  case $rc in 0) result=pass ;; 1) result=window-returned ;; 2) result=no-time-left ;; 3) result=no-sensor ;; *) result=unreadable ;; esac
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$(now)" "$(basename "$ws")" "$model" "$task" \
    "$SKIN_SENSOR" "$SKIN_SOURCE" "$hot1" "$max" "$maxsrc" "${first:--}" "${last:--}" "$cached" "$cur" "$SKIN_GATE_WAITED" "$polls" "$result" \
    >>"$STATE/skin_gate.tsv"
  case $rc in
    0) log "  $SKIN_SENSOR $last C ($SKIN_SOURCE; cached $cached, current $cur) <= $max ($maxsrc) after $SKIN_GATE_WAITED s" ;;
    1) log "  $SKIN_SENSOR ${last:-?} C ($SKIN_SOURCE; cached $cached, current $cur) still > $max after $SKIN_GATE_WAITED s (SKIN_WAIT $SKIN_WAIT)" ;;
    2) log "  $SKIN_SENSOR ${last:-?} C ($SKIN_SOURCE) still > $max when the window had no time left for the unit ($SKIN_GATE_WAITED s)" ;;
    3) log "  no $SKIN_SENSOR in the dump's ${SKIN_SOURCE/current/Current temperatures from HAL} block (two reads)" ;;
    *) log "  dumpsys thermalservice could not be read for $SKIN_GATE_WAITED s" ;;
  esac
  return $rc
}

skin_config() {
  if [[ -z "$SKIN_SENSOR" ]]; then echo "skin gate: off (SKIN_SENSOR empty)"; return 0; fi
  echo "skin gate: $SKIN_SENSOR from the dump's ${SKIN_SOURCE/current/current (HAL)} block <= ${SKIN_MAX_C_ENV:-its first hot threshold - $SKIN_MARGIN_C (36.0 without one)}, up to $SKIN_WAIT s per unit (reads every $SKIN_POLL s), $SKIN_STRIKES windows back in a row stop; launch probes: ${LAUNCH_PROBES:-none}"
}
now_hires() { perl -MTime::HiRes=time -e 'printf "%.3f\n", time'; }
launch_probes() {  # <window dir> <unit tag> <run_campaign pid>: LAUNCH_PROBES s after each of the unit's launches appears
  # on the host (run_cell's adb shell of the engine), the phone's thermal HAL and cpufreq, read once each. One launch
  # at a time: a launch that starts before the last offset of the one before is not read (cells cooldowns >= 120 s)
  local ws=$1 tag=$2 upid=$3 out="$1/$2.probes.txt" seen=" " p t0 off n=0 d all q pp
  while kill -0 "$upid" 2>/dev/null; do
    all=" $(pgrep -f -- "-s $SERIAL shell .*[=]==ENGINE_OUTPUT===" 2>/dev/null | tr '\n' ' ')"
    p=""
    for q in $all; do
      [[ "$seen" != *" $q "* ]] || continue
      # a fork of a launch's adb (the same command line until it execs) is not a launch
      pp="$(ps -o ppid= -p "$q" 2>/dev/null | tr -d ' ')"
      if [[ -n "$pp" && "$all" == *" $pp "* ]]; then seen="$seen$q "; continue; fi
      p=$q; break
    done
    if [[ -n "$p" ]]; then
      seen="$seen$p "; n=$((n + 1)); t0=$(now_hires)
      echo "== launch $n: adb pid $p seen at $(date -r "${t0%.*}" '+%F %T').${t0#*.} (t=0)" >>"$out"
      for off in $LAUNCH_PROBES; do
        d=$(awk -v t="$t0" -v o="$off" -v n="$(now_hires)" 'BEGIN { d = t + o - n; printf "%.3f", (d < 0 ? 0 : d) }')
        sleep "$d"
        if ! kill -0 "$p" 2>/dev/null; then echo "== +${off} s: the launch had ended" >>"$out"; break; fi
        {
          echo "== +${off} s: read from t=$(awk -v t="$t0" -v n="$(now_hires)" 'BEGIN { printf "%.2f", n - t }')"
          adbs shell "dumpsys thermalservice; for q in /sys/devices/system/cpu/cpufreq/policy*; do \
echo \"CPUFREQ \${q##*/} cur=\$(cat \$q/scaling_cur_freq) max=\$(cat \$q/scaling_max_freq)\"; done" || echo "== adb failed"
          echo "== +${off} s: done at t=$(awk -v t="$t0" -v n="$(now_hires)" 'BEGIN { printf "%.2f", n - t }')"
        } >>"$out" 2>&1
      done
    fi
    sleep 0.2
  done
}

window_end() {  # <acquired epoch>: the window's end, WINDOW_MIN after the hold or HARD_STOP if sooner
  local e=$(($1 + WINDOW_S))
  if [[ -n "$HARD_STOP" ]] && (( HARD_STOP < e )); then e=$HARD_STOP; fi
  echo "$e"
}

window_allowed() {  # <seconds the window needs>: may it start now? (WINDOW_GATE says why not)
  local t; t=$(date +%s)
  if [[ -n "$NO_NEW_WINDOW_AFTER" ]] && (( t >= NO_NEW_WINDOW_AFTER )); then
    WINDOW_GATE="no new window from $(date -r "$NO_NEW_WINDOW_AFTER" '+%T') (NO_NEW_WINDOW_AFTER)"; return 1
  fi
  if [[ -n "$HARD_STOP" ]] && (( t + $1 > HARD_STOP - MARGIN_S )); then
    WINDOW_GATE="a window of about $1 s would not end before $(date -r "$HARD_STOP" '+%T') (HARD_STOP)"; return 1
  fi
  return 0
}

other_live_holds() {  # other phones' live holds beside $HOLD (an iPhone's excepted): the adb server is theirs too
  python3 - "$HOLD" $HOLD_ALSO <<'PY' 2>/dev/null || true
import glob, json, os, sys
mine = {os.path.abspath(p) for p in sys.argv[1:]}
name = os.path.basename(sys.argv[1])
stem = "." + name[1:].split(".")[0] if name.startswith(".") else name.split(".")[0]
for f in sorted(glob.glob(os.path.join(os.path.dirname(os.path.abspath(sys.argv[1])), stem + "*"))):
    if os.path.abspath(f) in mine or ".queue" in f or "iphone" in os.path.basename(f).lower():
        continue
    try:
        pid = int(json.load(open(f))["pid"])
    except Exception:
        continue
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        continue
    except Exception:
        pass
    print(f"{os.path.basename(f)} pid {pid}")
PY
}

foreign_engines() {  # engine processes of any lane (binaries and models live under /data/local/tmp)
  adbs shell "ps -A -o PID,ARGS 2>/dev/null | grep -E '[/]data/local/tmp/|[.]/(llama|litert|executorch|gemma4|qnn|genai)' ; true"
}

cleanup_device() {  # <window dir>: remove what the window pushed, put back what it overwrote, list
  local ws=$1 prefix f rc=0
  prefix="$(cat "$ws/DEV_PREFIX")"
  echo "== $(now) cleanup"
  if [[ ! -f "$ws/before.txt" ]]; then echo "== nothing pushed (no listing before the window)"; return 0; fi
  # a launch the window stopped may still run on the phone: only this lane's runner directory
  adbs shell "pkill -f '[e]xecutorch-v1[.]5[.]1/'; true"
  adbs shell "rm -f $prefix.pte $prefix.tokenizer.json $prefix.*.prompt.txt; true"
  if [[ ! -f "$ws/RUNNER_DIR_KEPT" ]]; then
    adbs shell "rm -rf $DEV/$RUNNER_DIR; true"
  fi
  for f in $SHARED_FILES; do
    if grep -q -x "ABSENT $DEV/$f" "$ws/before.txt"; then
      adbs shell "rm -f $DEV/$f; true"
    elif [[ -f "$ws/backup/$f" ]]; then
      adbs push "$ws/backup/$f" "$DEV/$f" >/dev/null
      if [[ "$(adbs shell "sha256sum $DEV/$f" | cut -d' ' -f1)" == "$(shasum -a 256 "$ws/backup/$f" | cut -d' ' -f1)" ]]; then
        echo "restored $DEV/$f"
      else
        echo "RESTORE FAILED $DEV/$f"; rc=1
      fi
    else
      echo "NOT RESTORED (no copy pulled before the window): $DEV/$f"; rc=1
    fi
  done
  for d in prompts models; do
    if grep -q -x "DIR_ABSENT $d" "$ws/before.txt"; then adbs shell "rmdir $DEV/$d 2>/dev/null; true"; fi
  done
  adbs shell "ls -la $DEV $DEV/models $DEV/prompts 2>&1; ls -d $DEV/$RUNNER_DIR $prefix.* 2>&1; \
for f in $SHARED_FILES; do if [ -e $DEV/\$f ]; then sha256sum $DEV/\$f; else echo ABSENT $DEV/\$f; fi; done" >"$ws/after.txt" 2>&1 || rc=1
  cat "$ws/after.txt"
  # nothing of the window's own may remain; every shared file as before
  if grep -F "$prefix." "$ws/after.txt" | grep -v -q "No such file"; then echo "LEFT: model files"; rc=1; fi
  if [[ ! -f "$ws/RUNNER_DIR_KEPT" ]] && grep -E "^$DEV/$RUNNER_DIR\$|^d.* $RUNNER_DIR\$" "$ws/after.txt" | grep -v -q "No such file"; then
    echo "LEFT: runner directory"; rc=1
  fi
  for f in $SHARED_FILES; do
    if [[ "$(grep -E "( |^ABSENT )$DEV/$f\$" "$ws/before.txt" | head -1)" != "$(grep -E "( |^ABSENT )$DEV/$f\$" "$ws/after.txt" | head -1)" ]]; then
      echo "CHANGED: $DEV/$f"; rc=1
    fi
  done
  echo "== cleanup $([[ $rc == 0 ]] && echo CLEAN || echo NOT-CLEAN)"
  return $rc
}

# ---------------------------------------------------------------- keeper mode
if [[ "${1:-}" == --keeper ]]; then
  STATE="$2"; WS="$3"; LABEL="$4"; DRIVER="$5"
  me=$$
  echo "$(now) keeper $me for $LABEL (driver $DRIVER, window ${WINDOW_S}s from the hold)"
  acq=""; reason=release
  while [[ ! -f "$WS/RELEASE" ]]; do
    t=$(date +%s)
    if [[ -z "$acq" ]] && holds "$me"; then
      acq=$t; echo "$acq" >"$WS/KEEPER_ACQUIRED"; echo "$(now) hold names keeper $me"
    fi
    if [[ -n "$acq" ]] && (( t >= $(window_end "$acq") )); then reason=window-time; break; fi
    if ! kill -0 "$DRIVER" 2>/dev/null; then reason="driver $DRIVER gone"; break; fi
    sleep 5
  done
  pkill -f "[q]ueue_cli.py wait $HOLD $LABEL " 2>/dev/null || true
  if [[ "$reason" != release ]] && holds "$me"; then
    echo "$(now) $reason: stopping the window's run before the hold goes back"
    if [[ "$reason" == window-time ]]; then kill -TERM "$DRIVER" 2>/dev/null || true; fi
    if [[ -f "$WS/UNIT_PGID" ]]; then
      pg="$(cat "$WS/UNIT_PGID")"
      kill -TERM -- "-$pg" 2>/dev/null || true; sleep 5; kill -KILL -- "-$pg" 2>/dev/null || true
    fi
    if [[ -f "$WS/DEV_PREFIX" ]]; then
      cleanup_device "$WS" >>"$WS/cleanup.txt" 2>&1 || echo "$(now) cleanup NOT clean (cleanup.txt)"
    fi
    echo "$(now) keeper stopped the window: $reason" >>"$WS/KEEPER_STOPPED"
  fi
  python3 "$HCLI" release "$HOLD" "$me" || true
  python3 "$QCLI" dequeue "$HOLD" "$LABEL" >/dev/null || true
  touch "$WS/RELEASED"
  echo "$(now) keeper exit ($reason)"
  exit 0
fi

# ---------------------------------------------------------------- plan mode
if [[ "${1:-}" == --plan ]]; then
  shift
  MODELS=("$@"); [[ ${#MODELS[@]} -gt 0 ]] || MODELS=(0.6B 1.7B E2B 4B E4B)
  echo "phone $SERIAL (${DEV_KEY:-not in $SCHEDULE}): cpu mask ${CPU_MASK:-none} ($MASK_SOURCE), hold $HOLD, other hold files ${HOLD_ALSO:-none}; a new state dir's campaign ${CAMPAIGN:-$(date +%F)-dashboard-executorch-v1-${DEV_KEY:-s26}-android}"
  echo "$(skin_config)"
  for model in "${MODELS[@]}"; do
    used=0; w=0
    while IFS= read -r row; do
      [[ -n "$row" ]] || continue
      est="$(unit_estimate "$model" "$row")"
      if (( w == 0 || used + est > WINDOW_S - MARGIN_S )); then w=$((w + 1)); used=0; fi
      used=$((used + est))
      echo "$model window $w: $(field "$row" 4) cooldown=$(opt "$row" cooldown) estimate ${est}s (window so far ${used}s of $((WINDOW_S - MARGIN_S)))"
    done <<<"$(model_rows "$model")"
  done
  exit 0
fi

# ---------------------------------------------------------------- driver
STATE="${1:?usage: executorch_matrix_android.sh <state_dir> [<model> ...] | --plan [<model> ...]}"; shift
mkdir -p "$STATE"; STATE="$(cd "$STATE" && pwd)"
MODELS=("$@"); [[ ${#MODELS[@]} -gt 0 ]] || MODELS=(0.6B 1.7B E2B 4B E4B)
ROUND_END=$(( $(date +%s) + ROUND_HOURS * 3600 ))
[[ -f "$STATE/ROUND_END" ]] && ROUND_END="$(cat "$STATE/ROUND_END")" || echo "$ROUND_END" >"$STATE/ROUND_END"
# one campaign per state dir: a later call (another window, another day) writes into the same one
if [[ -f "$STATE/CAMPAIGN" ]]; then
  CAMPAIGN="$(cat "$STATE/CAMPAIGN")"
  [[ -z "$CAMPAIGN_ENV" || "$CAMPAIGN_ENV" == "$CAMPAIGN" ]] || { echo "ERROR: $STATE runs campaign $CAMPAIGN, not $CAMPAIGN_ENV" >&2; exit 2; }
else
  CAMPAIGN="${CAMPAIGN_ENV:-$(date +%F)-dashboard-executorch-v1-${DEV_KEY:-s26}-android}"
  echo "$CAMPAIGN" >"$STATE/CAMPAIGN"
fi
touch "$STATE/units_done.tsv"
EVIDENCE_DIR="${EVIDENCE_DIR:-$STATE/evidence}"

# inputs on the host before any queue entry
for model in "${MODELS[@]}"; do
  model_pattern "$model" >/dev/null || { echo "ERROR: unknown model key $model (0.6B 1.7B E2B 4B E4B)" >&2; exit 2; }
  [[ "$(model_rows "$model" | grep -c .)" -gt 0 ]] || { echo "ERROR: no $model row in $CELLS" >&2; exit 2; }
  while IFS= read -r row; do
    pte="$ET_MODEL_DIR/$(opt "$row" file)"
    [[ -f "$pte" ]] || { echo "ERROR: $pte is not staged" >&2; exit 2; }
  done <<<"$(model_rows "$model")"
done
for r in $RUNNERS; do
  [[ -x "$BENCH_ANDROID_BIN_DIR/$RUNNER_DIR/$r" ]] || { echo "ERROR: no $BENCH_ANDROID_BIN_DIR/$RUNNER_DIR/$r" >&2; exit 2; }
done
OUT_DIR="${BENCH_RAW_ROOT:-$REPO_ROOT/results/raw}/$CAMPAIGN/app-path-android"
log "driver $$: models ${MODELS[*]}, campaign $CAMPAIGN, window ${WINDOW_MIN} min, round end $(date -r "$ROUND_END" '+%F %T')"
log "phone $SERIAL (${DEV_KEY:-not in $SCHEDULE}): cpu mask ${CPU_MASK:-none} ($MASK_SOURCE), hold $HOLD, other hold files ${HOLD_ALSO:-none}"
if [[ -n "$DEV_KEY" && "$CPU_MASK" != "$ENTRY_MASK" ]]; then
  log "NOTE: CPU_MASK=${CPU_MASK:-<empty>} from the env; the schedule's cpu_mask for $DEV_KEY is ${ENTRY_MASK:-<empty>}"
fi
log "$(skin_config)"

WINDOWS_RUN=0
STOP=""

run_unit() {  # <window dir> <model> <row> -> rc of run_campaign.py (124 = stopped at the window's cut)
  local ws=$1 model=$2 row=$3 task tag cells pid rc=0 cut
  task="$(field "$row" 4)"; tag="unit-$(task_label "$task")"
  cells="$ws/$tag.cells"
  { echo "# $tag of $(basename "$CELLS") (android/scripts/$(basename "$SELF"), window $(basename "$ws"))"
    echo "$row"; } >"$cells"
  cut=$(( $(cat "$ws/WINDOW_END") - CUT_S ))
  # a session of its own: the window's cut stops run_campaign.py, run_cell.py and their adb at once
  python3 -c 'import os, sys; os.setsid(); os.execvp(sys.argv[1], sys.argv[1:])' \
    env -u BENCH_SITTING -u BENCH_SESSION_DEADLINE -u BENCH_STRICT_SMOKE -u ROUNDS -u BENCH_ROUND_WAKEFULNESS \
    CAMPAIGN="$CAMPAIGN" BENCH_ANDROID_SERIAL="$SERIAL" BENCH_CPU_MASK="$CPU_MASK" COOLDOWN="$COOLDOWN" \
    GATE_COOLDOWN="$GATE_COOLDOWN" python3 "$REPO_ROOT/android/bench/run_campaign.py" "$cells" \
    >"$ws/$tag.console.txt" 2>&1 </dev/null &
  pid=$!
  echo "$pid" >"$ws/UNIT_PGID"
  log "  $model $task: run_campaign.py pid $pid (console $(basename "$ws")/$tag.console.txt, cut at $(date -r "$cut" '+%T'))"
  local probes=""
  if [[ -n "$LAUNCH_PROBES" ]]; then
    mkdir -p "$OUT_DIR"
    echo "$(now) $model $task: the driver read the phone's dumpsys thermalservice and each cpufreq policy's scaling_cur_freq / scaling_max_freq ${LAUNCH_PROBES// /, } s after each launch's adb shell appeared on the host (android/scripts/$(basename "$SELF") LAUNCH_PROBES, read only, two adb shells per launch)" >>"$OUT_DIR/LAUNCH_PROBES.txt"
    launch_probes "$ws" "$tag" "$pid" &
    probes=$!
    log "  $model $task: launch probes at +${LAUNCH_PROBES// / s, +} s (pid $probes, $(basename "$ws")/$tag.probes.txt)"
  fi
  while kill -0 "$pid" 2>/dev/null; do
    if (( $(date +%s) >= cut )); then
      log "  $model $task: window cut reached, stopping the unit"
      kill -TERM -- "-$pid" 2>/dev/null || true; sleep 5; kill -KILL -- "-$pid" 2>/dev/null || true
      adbs shell "pkill -f '[e]xecutorch-v1[.]5[.]1/'; true" || true
      echo "$model	$task	cut at $(now)" >>"$STATE/units_cut.tsv"
      rc=124; break
    fi
    if ! kill -0 "$KEEPER" 2>/dev/null; then
      log "  $model $task: keeper $KEEPER gone, stopping the unit"
      kill -TERM -- "-$pid" 2>/dev/null || true; sleep 5; kill -KILL -- "-$pid" 2>/dev/null || true
      rc=125; break
    fi
    sleep 5
  done
  if (( rc == 0 )); then wait "$pid" || rc=$?; else wait "$pid" 2>/dev/null || true; fi
  if [[ -n "$probes" ]]; then
    # the last launch's reads first (the probe loop ends by itself after its last offset)
    local o maxoff=0
    for o in $LAUNCH_PROBES; do (( o > maxoff )) && maxoff=$o; done
    for _ in $(seq 1 $(( (maxoff + 2) * 5 ))); do kill -0 "$probes" 2>/dev/null || break; sleep 0.2; done
    kill "$probes" 2>/dev/null || true; wait "$probes" 2>/dev/null || true
  fi
  rm -f "$ws/UNIT_PGID"
  return $rc
}

battery_gate() {  # battery temperature <= BATTERY_MAX_C, up to BATTERY_WAIT s
  local t0 temp
  t0=$(date +%s)
  while :; do
    temp="$(adbs shell "dumpsys battery" | sed -n 's/^ *temperature: *\(-\{0,1\}[0-9]*\).*/\1/p' | head -1 || true)"
    if [[ -n "$temp" ]] && awk -v t="$temp" -v m="$BATTERY_MAX_C" 'BEGIN { exit !(t / 10 <= m) }'; then
      log "  battery $(awk -v t="$temp" 'BEGIN { printf "%.1f", t / 10 }') C <= $BATTERY_MAX_C after $(( $(date +%s) - t0 )) s"
      return 0
    fi
    if (( $(date +%s) - t0 >= BATTERY_WAIT )); then
      log "  battery gate: ${temp:-?}/10 C after ${BATTERY_WAIT} s, the unit runs anyway"
      return 1
    fi
    sleep 15
  done
}

window() {  # <model> -> runs one window from the model's first unit not done; sets STOP on a stop
  local model=$1 rows first="" row label n ws wait_s acq wend k=0 est pte need avail ec need_s others usb sg strikes
  rows="$(model_rows "$model")"
  while IFS= read -r row; do
    [[ -n "$row" ]] || continue
    if ! unit_done "$model" "$(field "$row" 4)"; then first="$row"; break; fi
  done <<<"$rows"
  [[ -n "$first" ]] || return 0
  if [[ "$first" == "$(echo "$rows" | head -1)" ]]; then label="$QUEUE_PREFIX-$model"
  else label="$QUEUE_PREFIX-$model-$(task_label "$(field "$first" 4)")"; fi
  # the first unit and the push of its model must end before HARD_STOP; nothing starts after NO_NEW_WINDOW_AFTER
  need_s=$(( $(unit_estimate "$model" "$first") + $(stat -L -f %z "$ET_MODEL_DIR/$(opt "$first" file)") / 30000000 + 120 ))
  if ! window_allowed "$need_s"; then log "window for $model $(field "$first" 4) not queued: $WINDOW_GATE"; STOP="$WINDOW_GATE"; return 0; fi
  n=1
  for d in "$STATE"/w[0-9]*; do [[ -d "$d" ]] && n=$((n + 1)); done
  ws="$STATE/w$(printf %02d "$n")-$label"
  mkdir -p "$ws"
  dev_prefix "$first" >"$ws/DEV_PREFIX"
  if ! python3 "$QCLI" enqueue "$HOLD" "$label" "$SUPERVISOR" "$WINDOW_MIN" >>"$ws/queue.txt" 2>&1; then
    log "window $(basename "$ws"): enqueue failed ($(tail -1 "$ws/queue.txt"))"; STOP="enqueue failed"; return 0
  fi
  # the keeper in a session of its own: a signal to the driver's process group leaves it to clean up
  python3 -c 'import os, sys; os.setsid(); os.execvp(sys.argv[1], sys.argv[1:])' \
    bash "$SELF" --keeper "$STATE" "$ws" "$label" $$ >>"$ws/keeper.log" 2>&1 </dev/null &
  KEEPER=$!
  wait_s=$(( ROUND_END - $(date +%s) )); (( wait_s < WAIT_TIMEOUT )) || wait_s=$WAIT_TIMEOUT
  log "window $(basename "$ws"): queued as $label, keeper $KEEPER, waiting up to ${wait_s} s"
  if ! python3 "$QCLI" wait "$HOLD" "$label" "$KEEPER" --timeout "$wait_s" >>"$ws/queue.txt" 2>&1; then
    log "window $(basename "$ws"): no hold within ${wait_s} s"
    touch "$ws/RELEASE"; wait "$KEEPER" 2>/dev/null || true
    STOP="no hold within ${wait_s} s"; return 0
  fi
  acq=$(date +%s); wend=$(window_end "$acq")
  echo "$acq" >"$ws/ACQUIRED_AT"; echo "$wend" >"$ws/WINDOW_END"
  holds "$KEEPER" || { log "window $(basename "$ws"): the hold does not name keeper $KEEPER"; STOP="hold not ours"; touch "$ws/RELEASE"; wait "$KEEPER" 2>/dev/null || true; return 0; }
  if ! window_allowed "$need_s"; then
    log "window $(basename "$ws"): $WINDOW_GATE -- the hold goes back untouched"; STOP="$WINDOW_GATE"
    touch "$ws/RELEASE"; wait "$KEEPER" 2>/dev/null || true; return 0
  fi
  log "window $(basename "$ws"): hold acquired $(date -r "$acq" '+%F %T'), window ends $(date -r "$wend" '+%T')"
  WINDOWS_RUN=$((WINDOWS_RUN + 1))
  # the phone's other hold files (ops/dashboard-v1/schedule.json hold_also_check): a live owner there is a lane
  # using the phone under another name
  for f in $HOLD_ALSO; do
    # busy unless it names a pid that is gone (an empty or unreadable hold counts as busy, device_hold.py)
    if [[ -e "$f" ]] && python3 - "$f" <<'PY' 2>/dev/null; then
import json, os, sys
try:
    pid = int(json.load(open(sys.argv[1]))["pid"])
except Exception:
    sys.exit(0)
try:
    os.kill(pid, 0)
except ProcessLookupError:
    sys.exit(1)
except Exception:
    pass
sys.exit(0)
PY
      log "window $(basename "$ws"): $f names a live owner: $(cat "$f")"
      STOP="another hold file is live"; touch "$ws/RELEASE"; wait "$KEEPER" 2>/dev/null || true; return 0
    fi
  done

  if [[ "$(adbs get-state 2>/dev/null)" != device ]]; then
    # a phone back on USB can stay invisible until the adb server restarts (no cell of ours runs now); the
    # server serves every phone on this Mac: not while another phone is held (its lane's adb would be cut)
    others="$(other_live_holds)"
    usb="ioreg: $(ioreg -p IOUSB -l 2>/dev/null | grep -c "\"USB Serial Number\" = \"$SERIAL\"" || true) USB entries with its serial"
    if [[ -n "$others" ]]; then
      log "  $SERIAL not on adb ($usb); the adb server is not restarted while other phones are held: $(echo "$others" | tr '\n' ' ')"
    else
      log "  $SERIAL not on adb ($usb): restarting the adb server once"
      adb kill-server </dev/null >/dev/null 2>&1 || true; adb start-server </dev/null >/dev/null 2>&1 || true; sleep 3
    fi
  fi
  if [[ "$(adbs get-state 2>/dev/null)" != device ]]; then
    log "window $(basename "$ws"): $SERIAL is not on adb"
    STOP="device not on adb"; touch "$ws/RELEASE"; wait "$KEEPER" 2>/dev/null || true; return 0
  fi
  device_state >"$ws/device_pre.txt" 2>&1 || true
  skin_line >>"$ws/device_pre.txt" 2>&1 || true
  cap_evidence "$ws" pre
  adbs shell "ps -A -o PID,ARGS 2>&1 | head -3" >"$ws/ps_sample.txt" 2>&1 || true
  sed 's/^/    /' "$ws/device_pre.txt" | tee -a "$STATE/driver.log"
  foreign_engines >"$ws/foreign.txt" 2>&1 || true
  if [[ -s "$ws/foreign.txt" ]]; then
    log "window $(basename "$ws"): another lane's engine runs on the phone under our hold:"; sed 's/^/    /' "$ws/foreign.txt" | tee -a "$STATE/driver.log"
    STOP="foreign engine on the phone"; touch "$ws/RELEASE"; wait "$KEEPER" 2>/dev/null || true; return 0
  fi
  # what this window will overwrite outside its own names, pulled first
  adbs shell "ls -la $DEV $DEV/models $DEV/prompts $DEV/$RUNNER_DIR 2>&1; \
for f in $SHARED_FILES; do if [ -e $DEV/\$f ]; then sha256sum $DEV/\$f; else echo ABSENT $DEV/\$f; fi; done; \
for d in models prompts $RUNNER_DIR; do if [ -d $DEV/\$d ]; then echo DIR_PRESENT \$d; else echo DIR_ABSENT \$d; fi; done" >"$ws/before.txt" 2>&1 \
    && grep -q -x "DIR_[A-Z]* $RUNNER_DIR" "$ws/before.txt" || {
    log "window $(basename "$ws"): the listing before the window failed"; mv "$ws/before.txt" "$ws/before.failed.txt" 2>/dev/null || true
    STOP="listing failed"; touch "$ws/RELEASE"; wait "$KEEPER" 2>/dev/null || true; return 0; }
  for f in $SHARED_FILES; do
    if grep -q -E " $DEV/$f\$" "$ws/before.txt" && ! grep -q -E "^ABSENT $DEV/$f\$" "$ws/before.txt"; then
      mkdir -p "$(dirname "$ws/backup/$f")"
      if ! adbs pull "$DEV/$f" "$ws/backup/$f" >/dev/null 2>&1; then
        # a file the run would overwrite and that could not be kept: nothing is pushed
        log "window $(basename "$ws"): could not pull $DEV/$f"; STOP="pull failed"; rm -f "$ws/before.txt"
        touch "$ws/RELEASE"; wait "$KEEPER" 2>/dev/null || true; return 0
      fi
    fi
  done
  log "  before: $(grep -c . "$ws/before.txt") lines, pulled: $(cd "$ws" && find backup -type f 2>/dev/null | tr '\n' ' ')"
  # free space for the model
  pte="$ET_MODEL_DIR/$(opt "$first" file)"
  need=$(( $(stat -L -f %z "$pte") / 1024 + 1048576 ))
  avail="$(adbs shell "df -k /data | tail -1" | awk '{print $4}' || true)"
  if [[ -z "$avail" ]] || (( avail < need )); then
    log "window $(basename "$ws"): /data has ${avail:-?} KB free, the model needs $need KB"
    STOP="no space for the model"; cleanup_device "$ws" >>"$ws/cleanup.txt" 2>&1 || true
    touch "$ws/RELEASE"; wait "$KEEPER" 2>/dev/null || true; return 0
  fi
  # the runner directory (both runners; pushed by hand as the docs say), sha256 against the host
  if grep -q -x "DIR_PRESENT $RUNNER_DIR" "$ws/before.txt"; then
    if [[ "$(adbs shell "cd $DEV/$RUNNER_DIR && sha256sum $RUNNERS" | sort)" == "$(cd "$BENCH_ANDROID_BIN_DIR/$RUNNER_DIR" && shasum -a 256 $RUNNERS | sort)" ]]; then
      log "  $DEV/$RUNNER_DIR was there with the same runners (removed after the window)"
    else
      log "window $(basename "$ws"): $DEV/$RUNNER_DIR is there with other bytes; not touching it"
      touch "$ws/RUNNER_DIR_KEPT"; STOP="foreign runner directory"; cleanup_device "$ws" >>"$ws/cleanup.txt" 2>&1 || true
      touch "$ws/RELEASE"; wait "$KEEPER" 2>/dev/null || true; return 0
    fi
  else
    { adbs push "$BENCH_ANDROID_BIN_DIR/$RUNNER_DIR" "$DEV/" && adbs shell "cd $DEV/$RUNNER_DIR && chmod 755 $RUNNERS"; } \
      >"$ws/push.txt" 2>&1 || log "  the runner push failed ($(basename "$ws")/push.txt)"
  fi
  if [[ "$(adbs shell "cd $DEV/$RUNNER_DIR && sha256sum $RUNNERS" | sort)" != "$(cd "$BENCH_ANDROID_BIN_DIR/$RUNNER_DIR" && shasum -a 256 $RUNNERS | sort)" ]]; then
    log "window $(basename "$ws"): runner sha256 on the phone differs from the host"
    STOP="runner push mismatch"; cleanup_device "$ws" >>"$ws/cleanup.txt" 2>&1 || true
    touch "$ws/RELEASE"; wait "$KEEPER" 2>/dev/null || true; return 0
  fi
  log "  runners on the phone: $(adbs shell "cd $DEV/$RUNNER_DIR && sha256sum $RUNNERS" | awk '{printf "%s %s… ", $2, substr($1, 1, 12)}')"

  # units
  while IFS= read -r row; do
    [[ -n "$row" ]] || continue
    unit_done "$model" "$(field "$row" 4)" && continue
    est="$(unit_estimate "$model" "$row")"
    if (( k > 0 && $(date +%s) + est > wend - MARGIN_S )); then
      log "  next unit $(field "$row" 4) (estimate ${est} s) does not fit before $(date -r $((wend - MARGIN_S)) '+%T'): window closes"
      break
    fi
    k=$((k + 1))
    battery_gate || true
    sg=0; skin_gate "$ws" "$model" "$(field "$row" 4)" $((wend - MARGIN_S)) || sg=$?
    case $sg in
      0) [[ -z "$SKIN_SENSOR" ]] || echo 0 >"$STATE/skin_returns"
         if (( SKIN_GATE_WAITED > 0 && $(date +%s) + est > wend - MARGIN_S )); then
           log "  unit $(field "$row" 4) (estimate ${est} s) no longer fits before $(date -r $((wend - MARGIN_S)) '+%T') after the skin wait: window closes"
           break
         fi ;;
      1) strikes=$(( $(cat "$STATE/skin_returns" 2>/dev/null || echo 0) + 1 )); echo "$strikes" >"$STATE/skin_returns"
         log "  window $(basename "$ws") goes back: $SKIN_SENSOR above its maximum for $SKIN_WAIT s ($strikes window(s) in a row)"
         if (( strikes >= SKIN_STRIKES )); then STOP="$SKIN_SENSOR above its maximum for SKIN_WAIT in $strikes windows in a row"; fi
         break ;;
      2) log "  window $(basename "$ws") closes: no time left for the unit while $SKIN_SENSOR was above its maximum"; break ;;
      3) STOP="no $SKIN_SENSOR in the phone's thermalservice dump"; break ;;
      *) STOP="thermalservice unreadable"; break ;;
    esac
    log "  unit $model $(field "$row" 4) starts (estimate ${est} s)"
    ec=0; run_unit "$ws" "$model" "$row" || ec=$?
    log "  unit $model $(field "$row" 4) ended rc=$ec; records now $(ls "$OUT_DIR"/*.json 2>/dev/null | grep -c "_$(field "$row" 3 | tr '/' '_')_$(field "$row" 4)" || true)"
    if (( ec != 0 )); then STOP="unit $model $(field "$row" 4) rc $ec"; break; fi
    echo "$model	$(field "$row" 4)" >>"$STATE/units_done.tsv"
  done <<<"$rows"

  # nothing of the window stays on the phone
  if cleanup_device "$ws" >"$ws/cleanup.txt" 2>&1; then
    log "  cleanup: clean ($(basename "$ws")/after.txt)"
  else
    log "  cleanup: NOT clean ($(basename "$ws")/cleanup.txt)"; STOP="cleanup not clean"
  fi
  device_state >"$ws/device_post.txt" 2>&1 || true
  skin_line >>"$ws/device_post.txt" 2>&1 || true
  cap_evidence "$ws" post
  touch "$ws/RELEASE"
  for _ in $(seq 1 24); do [[ -f "$ws/RELEASED" ]] && break; sleep 5; done
  wait "$KEEPER" 2>/dev/null || true
  if holds "$KEEPER" && ! kill -0 "$KEEPER" 2>/dev/null; then
    # a keeper that died leaves its pid in the hold, and queue_cli.py waits on any hold file
    log "window $(basename "$ws"): keeper $KEEPER is gone with the hold: releasing it for its pid"
    python3 "$HCLI" release "$HOLD" "$KEEPER" >>"$ws/queue.txt" 2>&1 || true
    python3 "$QCLI" dequeue "$HOLD" "$label" >/dev/null 2>&1 || true
  fi
  if holds "$KEEPER"; then log "window $(basename "$ws"): the hold still names keeper $KEEPER"; STOP="hold not released"; fi
  log "window $(basename "$ws"): released at $(now) (held $(( $(date +%s) - acq )) s)"
}

for model in "${MODELS[@]}"; do
  while [[ -z "$STOP" ]]; do
    left=0
    while IFS= read -r row; do
      [[ -n "$row" ]] || continue
      unit_done "$model" "$(field "$row" 4)" || left=$((left + 1))
    done <<<"$(model_rows "$model")"
    (( left > 0 )) || break
    if (( MAX_WINDOWS > 0 && WINDOWS_RUN >= MAX_WINDOWS )); then STOP="MAX_WINDOWS=$MAX_WINDOWS reached"; break; fi
    window "$model"
  done
  [[ -z "$STOP" ]] || break
done
log "driver $$ done: ${STOP:-every unit of ${MODELS[*]} ran}; $(grep -c . "$STATE/units_done.tsv") unit(s) done in $STATE/units_done.tsv"
case "$STOP" in ""|"MAX_WINDOWS="*) exit 0 ;; *) exit 3 ;; esac
