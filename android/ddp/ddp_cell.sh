#!/system/bin/sh
# ddp_cell.sh — one cell of edge-llm-bench on a Developer Device Platform (DDP) unit: the job's
# androidNativeBinary (android/ddp/run_ddp.py builds the job; design:
# results/raw/2026-10-15-ddp-backend-dev/DESIGN.md). Runs --runs fresh engine processes of one
# command, each inside the adb route's on-device sampler shell (android/bench/run_cell.py
# sampler_shell: the same string, built here from the args), and keeps everything under
# --output_dir for the session's pull:
#   provenance.txt    getprop identity, kernel, taskset / timeout paths, argc and every arg, sha256 of
#                     the engine files, the model(s) and the prompt(s) on the unit
#   run<i>.state      before the run: the gate waits, epoch, thermal, mWakefulness, stay-on setting,
#                     dumpsys battery; after it: epoch, thermal, dumpsys battery
#   run<i>.log        the sampler shell's stdout (what run_once's adb call returns): CPUPOLICY / CPUMAX /
#                     VmRSS / VmHWM / Cpus_allowed_list lines, ===ENGINE_OUTPUT===, the engine's output,
#                     EXIT_CODE=<n>; run<i>.err its stderr
#   run<i>.exit       the engine's exit code (from EXIT_CODE=; "missing" without one)
#   run<i>.engine.txt the engine's own output file of the run; run<i>_logcat.txt logcat of the run
#   run<i>.skipped    a run not started: the --budget would not hold it
#   wrapper.log       this script's progress lines (the platform keeps no stdout of a native binary)
# Args (key=value; --command= LAST — every argv element after it is joined with one space, so the
# command is the same whether the platform keeps that element whole or splits it at its spaces):
#   --runs=N --cooldown=S --mask=<hex|none> --env=<VAR=value> --binname=<engine tool> --dir=<device dir>
#   --output_dir=<dir> --timeout=<s per run> --thermal_wait=<s> --cpucap_wait=<s> --budget=<s, 0 = none>
#   --cell=<capture stem> [--print_shell=1: print the sampler shell and stop] --command=<engine command>
# Android /system/bin/sh (mksh / toybox): no arrays, no `local`. Always exits 0 so the pull step runs;
# each run's own exit code is in run<i>.exit.

RUNS=1
COOLDOWN=0
MASK=none
ENV="LD_LIBRARY_PATH=."
ENV_SET=0
ERR_FILE=""
BINNAME=""
DIR=/data/local/tmp/llmbench
OUTPUT_DIR=""
TIMEOUT=1800
THERMAL_WAIT=600
CPUCAP_WAIT=300
BUDGET=0
CELL=""
PRINT_SHELL=0
CMD=""
IN_CMD=0
UNKNOWN=""
for ARG in "$@"; do
  if [ "$IN_CMD" = 1 ]; then
    CMD="$CMD $ARG"
    continue
  fi
  case "$ARG" in
    --runs=*) RUNS="${ARG#*=}" ;;
    --cooldown=*) COOLDOWN="${ARG#*=}" ;;
    --mask=*) MASK="${ARG#*=}" ;;
    --env=*)
      if [ "$ENV_SET" = 0 ]; then
        ENV="${ARG#*=}"
        ENV_SET=1
      else
        ENV="$ENV ${ARG#*=}"
      fi
      ;;
    --err_file=*) ERR_FILE="${ARG#*=}" ;;
    --binname=*) BINNAME="${ARG#*=}" ;;
    --dir=*) DIR="${ARG#*=}" ;;
    --output_dir=*) OUTPUT_DIR="${ARG#*=}" ;;
    --timeout=*) TIMEOUT="${ARG#*=}" ;;
    --thermal_wait=*) THERMAL_WAIT="${ARG#*=}" ;;
    --cpucap_wait=*) CPUCAP_WAIT="${ARG#*=}" ;;
    --budget=*) BUDGET="${ARG#*=}" ;;
    --cell=*) CELL="${ARG#*=}" ;;
    --print_shell=*) PRINT_SHELL="${ARG#*=}" ;;
    --command=*) CMD="${ARG#--command=}"; IN_CMD=1 ;;
    *) UNKNOWN="$UNKNOWN $ARG" ;;
  esac
done
[ -n "$OUTPUT_DIR" ] || OUTPUT_DIR="$DIR/ddp-out"

# run_cell.sampler_shell(cmd, binname, f"{DEV_DIR}/run_out.txt", env, taskset_prefix, timeout_prefix),
# piece for piece (android/ddp/selftest.py compares the two strings byte for byte)
case "$MASK" in
  none|"") TASKSET_PREFIX="" ;;
  *) TASKSET_PREFIX="taskset $MASK " ;;
esac
TIMEOUT_PREFIX="timeout -k 5 $TIMEOUT "
OUT_FILE="$DIR/run_out.txt"
CPUFREQ=/sys/devices/system/cpu/cpufreq
CPU_HEAD='for p in '"$CPUFREQ"'/policy*; do h=; r=; read h <$p/cpuinfo_max_freq; read r <$p/related_cpus; echo "CPUPOLICY ${p##*/} ${h:--} $r"; done; '
CPU_TICK='c=CPUMAX; for f in '"$CPUFREQ"'/policy*/scaling_max_freq; do m=; read m <$f; c="$c ${m:--}"; done; [ "$c" = "$pc" ] || echo "$c"; pc=$c; '
RSS_COMMAND="grep -E 'VmRSS|VmHWM|Cpus_allowed_list'"
if [ -z "$ERR_FILE" ]; then
  SHELL_STR="cd $DIR && $ENV $TASKSET_PREFIX$TIMEOUT_PREFIX$CMD >$OUT_FILE 2>&1 </dev/null & pid=\$!; $CPU_HEAD${CPU_TICK}sleep 1; epid=\$(pgrep -n -f $BINNAME); [ -z \"\$epid\" ] && epid=\$pid; sk=; while kill -0 \$pid 2>/dev/null; do $RSS_COMMAND /proc/\$epid/status 2>/dev/null; ${CPU_TICK}sleep 0.5; done; wait \$pid; ec=\$?; echo ===ENGINE_OUTPUT===; cat $OUT_FILE; echo EXIT_CODE=\$ec"
else
  SHELL_STR="cd $DIR && $ENV $TASKSET_PREFIX$TIMEOUT_PREFIX$CMD >$OUT_FILE 2>$ERR_FILE </dev/null & pid=\$!; $CPU_HEAD${CPU_TICK}sleep 1; epid=\$(pgrep -n -f $BINNAME); [ -z \"\$epid\" ] && epid=\$pid; sk=; while kill -0 \$pid 2>/dev/null; do $RSS_COMMAND /proc/\$epid/status 2>/dev/null; ${CPU_TICK}sleep 0.5; done; wait \$pid; ec=\$?; echo ===ENGINE_OUTPUT===; cat $OUT_FILE; echo EXIT_CODE=\$ec; echo ===ENGINE_STDERR===; cat $ERR_FILE 2>/dev/null; rm -f $ERR_FILE"
fi

if [ "$PRINT_SHELL" = 1 ]; then
  printf '%s\n' "$SHELL_STR"
  exit 0
fi

mkdir -p "$OUTPUT_DIR"
LOG="$OUTPUT_DIR/wrapper.log"
T0=$(date +%s)
say() {
  echo "$(date +%s) $*" | tee -a "$LOG"
}
say "ddp_cell.sh start cell=$CELL runs=$RUNS cooldown=$COOLDOWN mask=$MASK timeout=$TIMEOUT budget=$BUDGET"

BAD=""
for V in "$RUNS" "$COOLDOWN" "$TIMEOUT" "$THERMAL_WAIT" "$CPUCAP_WAIT" "$BUDGET"; do
  case "$V" in
    ""|*[!0-9]*) BAD="$BAD $V" ;;
  esac
done
[ -n "$CMD" ] || BAD="$BAD (no --command)"
[ -n "$BINNAME" ] || BAD="$BAD (no --binname)"
[ -n "$UNKNOWN" ] && say "unknown args:$UNKNOWN"
if [ -n "$BAD" ]; then
  say "bad args:$BAD — no run started"
  exit 0
fi

# a pushed binary may arrive without the execute bit (09-17 session); the .so files are dlopen'ed
for B in litert_lm_main litert_lm_advanced_main llama-cli llama-bench "$BINNAME"; do
  [ -f "$DIR/$B" ] && chmod 755 "$DIR/$B"
done
for B in "$DIR"/engines/*/bin/* "$DIR"/executorch-*/*; do
  [ -f "$B" ] && chmod 755 "$B"
done
for D in "$DIR"/engines/*; do
  [ -d "$D" ] && mkdir -p "$D/clcache"
done

PROV="$OUTPUT_DIR/provenance.txt"
{
  echo "date: $(date)"
  echo "epoch: $T0"
  for P in ro.product.model ro.product.device ro.build.fingerprint ro.serialno ro.build.version.release \
           ro.build.version.security_patch ro.soc.model; do
    echo "$P: $(getprop "$P")"
  done
  echo "kernel: $(uname -a)"
  echo "taskset: $(command -v taskset)"
  echo "timeout: $(command -v timeout)"
  echo "cell: $CELL"
  echo "argc: $#"
  for ARG in "$@"; do
    echo "arg: $ARG"
  done
  echo "sha256:"
  sha256sum "$DIR"/litert_lm_main "$DIR"/litert_lm_advanced_main "$DIR"/llama-cli "$DIR"/llama-bench "$DIR"/*.so "$DIR"/engines/*/bin/* "$DIR"/engines/*/lib/*.so "$DIR"/executorch-*/* "$DIR"/models/* "$DIR"/prompts/* 2>&1
} > "$PROV"
say "provenance written"

thermal_now() {
  dumpsys thermalservice 2>/dev/null | grep -m1 'Thermal Status:' | tr -cd '0-9'
}

# run_campaign.wait_nominal: Thermal Status 0, polled every 30 s for at most $1 s
gate_thermal() {
  GW0=$(date +%s)
  GATE_TIMED_OUT=0
  while :; do
    [ "$(thermal_now)" = 0 ] && break
    NOW=$(date +%s)
    if [ $((NOW - GW0)) -ge "$1" ]; then
      GATE_TIMED_OUT=1
      break
    fi
    W=$(($1 - (NOW - GW0)))
    [ "$W" -gt 30 ] && W=30
    sleep "$W"
  done
  GATE_WAITED=$(($(date +%s) - GW0))
}

# run_cell.wait_cpu_uncapped: every policy's scaling_max_freq back at its cpuinfo_max_freq, polled
# every 10 s for at most $1 s; CAP_LAST = the capped policies of the last read
caps_now() {
  CAPS=""
  for P in "$CPUFREQ"/policy*; do
    H=
    M=
    read H 2>/dev/null <"$P/cpuinfo_max_freq"
    read M 2>/dev/null <"$P/scaling_max_freq"
    case "$H" in ""|*[!0-9]*) continue ;; esac
    case "$M" in ""|*[!0-9]*) continue ;; esac
    [ "$M" -lt "$H" ] && CAPS="$CAPS ${P##*/} $M/$H"
  done
  echo "$CAPS"
}

wait_cpucap() {
  CW0=$(date +%s)
  CAP_TIMED_OUT=0
  while :; do
    CAP_LAST=$(caps_now)
    [ -z "$CAP_LAST" ] && break
    NOW=$(date +%s)
    if [ $((NOW - CW0)) -ge "$1" ]; then
      CAP_TIMED_OUT=1
      break
    fi
    W=$(($1 - (NOW - CW0)))
    [ "$W" -gt 10 ] && W=10
    sleep "$W"
  done
  CAP_WAITED=$(($(date +%s) - CW0))
}

state_block() {
  echo "${1}_epoch=$(date +%s)"
  echo "${1}_ns=$(date +%s%N 2>/dev/null)"
  echo "${1}_thermal=$(dumpsys thermalservice 2>/dev/null | grep -m1 'Thermal Status:')"
  echo "${1}_wakefulness=$(dumpsys power 2>/dev/null | grep -m1 'mWakefulness=')"
  echo "${1}_stay_on=$(settings get global stay_on_while_plugged_in 2>/dev/null)"
  echo "${1}_battery_begin"
  dumpsys battery 2>/dev/null
  echo "${1}_battery_end"
}

# the seconds left for gate waits once a run's timeout and the pull margin are kept back
spare() {
  if [ "$BUDGET" -gt 0 ]; then
    S=$((BUDGET - ($(date +%s) - T0) - TIMEOUT - 60))
    [ "$S" -lt 0 ] && S=0
    [ "$S" -lt "$1" ] && echo "$S" && return
  fi
  echo "$1"
}

I=1
while [ "$I" -le "$RUNS" ]; do
  NEED=$((TIMEOUT + 60))
  [ "$I" -gt 1 ] && NEED=$((NEED + COOLDOWN))
  LEFT=$((BUDGET - ($(date +%s) - T0)))
  if [ "$BUDGET" -gt 0 ] && [ "$LEFT" -lt "$NEED" ]; then
    echo "run $I not started: $LEFT s of the $BUDGET s budget left, $NEED s needed" > "$OUTPUT_DIR/run$I.skipped"
    say "run $I not started (budget)"
    break
  fi
  if [ "$I" -gt 1 ] && [ "$COOLDOWN" -gt 0 ]; then
    say "cooldown $COOLDOWN s"
    sleep "$COOLDOWN"
  fi
  gate_thermal "$(spare "$THERMAL_WAIT")"
  wait_cpucap "$(spare "$CPUCAP_WAIT")"
  ST="$OUTPUT_DIR/run$I.state"
  {
    echo "run=$I"
    echo "thermal_gate_waited_s=$GATE_WAITED"
    echo "thermal_gate_timed_out=$GATE_TIMED_OUT"
    echo "cpucap_waited_s=$CAP_WAITED"
    echo "cpucap_timed_out=$CAP_TIMED_OUT"
    echo "cpucap_caps=$CAP_LAST"
    state_block start
  } > "$ST"
  logcat -c 2>/dev/null
  say "run $I start"
  sh -c "$SHELL_STR" > "$OUTPUT_DIR/run$I.log" 2> "$OUTPUT_DIR/run$I.err"
  EC=$(grep '^EXIT_CODE=' "$OUTPUT_DIR/run$I.log" | tail -n 1)
  EC=${EC#EXIT_CODE=}
  [ -n "$EC" ] || EC=missing
  echo "$EC" > "$OUTPUT_DIR/run$I.exit"
  cp "$OUT_FILE" "$OUTPUT_DIR/run$I.engine.txt" 2>/dev/null
  logcat -d > "$OUTPUT_DIR/run${I}_logcat.txt" 2>/dev/null
  state_block end >> "$ST"
  say "run $I end exit=$EC"
  I=$((I + 1))
done

say "all runs finished"
ls -l "$OUTPUT_DIR" | tee -a "$LOG"
exit 0
