#!/bin/bash
# Host side of the ORT GenAI Galaxy S26 1K prefill diagnosis (round r2b,
# 2026-10-07), by hand. adb, perl and POSIX tools only: no python, because the
# Mac measurement-window guard stops python3 commands while another lane's
# window is open (round r2's trap). Every phase except dry refuses to run unless
# the S26 hold names this round's keeper (KEEPER_PID); the supervisor's go comes
# before the first non-dry phase.
#
#   dry            no adb: local inputs (binaries against MANIFEST.txt, model
#                  folder, prompt), the run plan
#   probe          the device-busy probe list and the device state
#   push           runtime dir (changed files only, sha256 checked), model
#                  folder (bytes checked), the 1K prompt (sha256 checked)
#   run [ids...]   the runs in order (default: all), each = frame check, gate,
#                  launch through run_diag.sh, pull of that run's files
#   pull           the whole device out/ again
#   clean          removes the model folder and out/ (the runtime dir stays)
#
# Env: KEEPER_PID (every phase but dry), FRAME_START (epoch seconds of the hold
# acquisition; run). Log: host.log next to this file, wall-clock time from date.
#
# Frame: 45 min from FRAME_START. No run starts with less than 8 min left, a
# gate waits at most until then, and each run's on-device time limit is cut to
# end 3 min before the frame does (pull, clean, release).
# Gate (cpu-cap-rule shape, battery 34.0 C for this diagnosis): every policy's
# scaling_max_freq == cpuinfo_max_freq, Thermal Status 0, battery <= 34.0 C.
# The ladder's 2nd and 3rd launches check the caps and thermal only; a cap
# sends them through the full gate.
set -uo pipefail

SERIAL=RFGL80R6A6H
SCRIPT=ortgenai_r2b_diag
D=/data/local/tmp/llmbench/ortgenai
DEV=/data/local/tmp/llmbench
MODEL_DIR=$DEV/models/onnx-community_Qwen3-0.6B-ONNX_cpu-int4-kld-block-128
PROMPT=$DEV/prompts/long-context-1024-gen256.txt
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../../.." && pwd)"
BIN="$REPO/android/bin/ortgenai-0.17.0"
MODEL="$HOME/.cache/huggingface/hub/models--onnx-community--Qwen3-0.6B-ONNX/snapshots/da1453100cf3ff33ef56d17983fc7a8648706db6/onnxruntime/cpu_and_mobile/cpu-int4-kld-block-128"
LOCAL_PROMPT="$REPO/prompts/text/long-context-1024-gen256.txt"
HOLD="$HOME/code/litertlm-convert/community_accel_work/s2_npu_sweep/.device_hold"
LOCK=/tmp/edge-llm-bench-android-$SERIAL.lock
LOG="${DIAG_LOG:-$HERE/host.log}"   # DIAG_LOG: offline tests only
OUTDIR="$HERE/device"
RUNTIME_FILES="libonnxruntime-genai.so libmat.so libonnxruntime.so ortgenai_run model_benchmark"
MODEL_FILES="chat_template.jinja config.json genai_config.json model.onnx tokenizer.json tokenizer_config.json"
FRAME_S=$((45 * 60))
STOP_MARGIN_S=$((8 * 60))
END_MARGIN_S=$((3 * 60))
BATTERY_MAX=340   # deci-C
GATE_POLL_S=15
COOL_PAUSE_S=60   # after a launch of a minute or more, before its gate

MB="-i $MODEL_DIR --use_random_tokens -g 8 -ml 2048 -r 1 -w 0 -v -e cpu"
RUN1K="-i $MODEL_DIR --prompt_file $PROMPT -g 32 -ml 2048"
# id | tag | mask | limit_s | gate (full|caps) | pause after (s) | binary | args
PLAN="D2a|r2b-D2-mb-l64|-|120|full|10|model_benchmark|$MB -l 64
D2b|r2b-D2-mb-l256|-|120|caps|10|model_benchmark|$MB -l 256
D2c|r2b-D2-mb-l512|-|180|caps|$COOL_PAUSE_S|model_benchmark|$MB -l 512
D1|r2b-D1-mb-l1024-profile|-|300|full|$COOL_PAUSE_S|model_benchmark|$MB -l 1024 --profile_prefill
D3|r2b-D3-run-threads6|-|300|full|$COOL_PAUSE_S|ortgenai_run|$RUN1K --threads 6
D6|r2b-D6-run-default|-|300|full|$COOL_PAUSE_S|ortgenai_run|$RUN1K
D4|r2b-D4-run-threads8|-|300|full|$COOL_PAUSE_S|ortgenai_run|$RUN1K --threads 8
D5|r2b-D5-run-mask-c0|c0|420|full|0|ortgenai_run|$RUN1K"

log() { echo "$(date '+%F %T') $*" | tee -a "$LOG"; }
die() { log "STOP: $*"; exit 1; }
adbs() { gtimeout "${ADB_TIMEOUT:-120}" adb -s "$SERIAL" "$@" </dev/null; }  # stdin: the PLAN loop reads a here-string
sh_dev() { adbs shell "$1"; }
sha_local() { shasum -a 256 "$1" | cut -d' ' -f1; }
sha_dev() { sh_dev "if [ -e $1 ]; then sha256sum $1; else echo MISSING; fi" | tr -d '\r' | awk '{print $1}'; }

own_hold() {
  [[ -n "${KEEPER_PID:-}" ]] || die "KEEPER_PID is not set"
  local h
  h="$(cat "$HOLD" 2>/dev/null)"
  [[ "$h" == *"\"pid\": $KEEPER_PID,"* && "$h" == *"\"script\": \"$SCRIPT\""* ]] ||
    die "the S26 hold is not this round's (keeper $KEEPER_PID): ${h:-no hold file}; no adb"
  kill -0 "$KEEPER_PID" 2>/dev/null || die "keeper pid $KEEPER_PID is gone; no adb"
}

# state: one line, and sets CAPPED (policies below hw), THERMAL, BATT (deci-C)
state() {
  local raw
  raw="$(sh_dev 'for p in /sys/devices/system/cpu/cpufreq/policy*; do echo POL ${p##*/} $(cat $p/cpuinfo_max_freq) $(cat $p/scaling_max_freq); done;
    dumpsys thermalservice | sed -n "s/^Thermal Status: */THERMAL /p";
    dumpsys battery | sed -n "s/^ *temperature: */BATT /p; s/^ *level: */LEVEL /p; s/^ *status: */BSTATUS /p";
    sed -n "s/^MemAvailable: *\([0-9]*\).*/MEMAVAIL \1/p" /proc/meminfo;
    dumpsys power | sed -n "s/.*mWakefulness=\([A-Za-z]*\).*/WAKE \1/p" | head -1' | tr -d '\r')" || return 1
  CAPPED="$(awk '$1=="POL" && $3!=$4 {printf "%s ", $2}' <<<"$raw")"
  THERMAL="$(awk '$1=="THERMAL" {print $2}' <<<"$raw")"
  BATT="$(awk '$1=="BATT" {print $2}' <<<"$raw")"
  local mem; mem="$(awk '$1=="MEMAVAIL"{print $2}' <<<"$raw")"
  STATE_LINE="thermal=${THERMAL:-?} battery=${BATT:-?}dC capped=${CAPPED:-none} $(awk '$1=="POL" {printf "%s=%s/%s ", $2, $4, $3}' <<<"$raw")level=$(awk '$1=="LEVEL"{print $2}' <<<"$raw") bstatus=$(awk '$1=="BSTATUS"{print $2}' <<<"$raw") MemAvailable=$(( ${mem:-0} / 1024 ))MB wake=$(awk '$1=="WAKE"{print $2}' <<<"$raw")"
}

remaining() { echo $(( FRAME_S - ( $(date +%s) - FRAME_START ) )); }

gate() {  # gate <full|caps>: 0 = pass, 1 = no pass before the stop margin
  local mode=$1
  while :; do
    state || { log "gate: adb state read failed"; return 1; }
    local ok=0
    if [[ -z "$CAPPED" && "$THERMAL" == 0 ]]; then
      if [[ "$mode" == caps ]] || [[ -n "$BATT" && "$BATT" -le $BATTERY_MAX ]]; then ok=1; fi
    fi
    if (( ok )); then log "gate pass ($mode): $STATE_LINE"; return 0; fi
    log "gate wait ($mode): $STATE_LINE"
    mode=full
    (( $(remaining) - GATE_POLL_S > STOP_MARGIN_S )) || return 1
    sleep $GATE_POLL_S
  done
}

phase_dry() {
  log "phase dry (no adb)"
  local ok=1 want got
  for f in $RUNTIME_FILES; do
    want="$(awk -v f="$f" '$2 == f {print $1}' "$BIN/MANIFEST.txt")"
    got="$(sha_local "$BIN/$f")"
    if [[ -n "$want" && "$want" == "$got" ]]; then log "dry: $f sha256 $got = MANIFEST"; else log "dry: $f sha256 $got != MANIFEST ${want:-missing}"; ok=0; fi
  done
  log "dry: run_diag.sh sha256 $(sha_local "$HERE/run_diag.sh")"
  for f in $MODEL_FILES; do
    if [[ -f "$MODEL/$f" ]]; then log "dry: model $f $(stat -Lf %z "$MODEL/$f") bytes"; else log "dry: model $f MISSING"; ok=0; fi
  done
  log "dry: prompt long-context-1024-gen256.txt sha256 $(sha_local "$LOCAL_PROMPT")"
  log "dry: hold now: $(cat "$HOLD" 2>/dev/null || echo none)"
  while IFS='|' read -r id tag mask limit gmode pause bin args; do
    log "dry: plan $id $tag gate=$gmode limit=${limit}s pause=${pause}s mask=$mask: $bin $args"
  done <<<"$PLAN"
  (( ok )) && log "dry: PASS" || die "dry: local inputs do not match"
}

phase_probe() {
  own_hold
  log "phase probe"
  if perl -MFcntl=:flock -e 'open(my $f, ">", $ARGV[0]) or exit 2; flock($f, LOCK_EX | LOCK_NB) or exit 1; exit 0' "$LOCK"; then
    log "probe lock: free ($LOCK)"
  else
    log "probe lock: HELD ($LOCK)"
  fi
  log "probe hold: $(cat "$HOLD")"
  log "probe host drivers: $(pgrep -fl '^[^ ]*[p]ython[0-9.]* [^ ]*android/bench/run_' || echo none)"
  local eng; eng="$(sh_dev "ps -A | grep -E 'litert_lm|llama|ortgenai|model_benchmark|executor' | grep -v grep" | tr -d '\r' | tr '\n' ';')"
  log "probe device engines: ${eng:-none}"
  log "probe android: $(sh_dev 'echo $(getprop ro.product.model) / Android $(getprop ro.build.version.release) / patch $(getprop ro.build.version.security_patch) / $(getprop ro.build.fingerprint) / uptime $(cut -d" " -f1 /proc/uptime) / cpus online $(cat /sys/devices/system/cpu/online)' | tr -d '\r')"
  log "probe disk: $(sh_dev 'df -k /data | tail -1' | tr -d '\r')"
  log "probe runtime dir: $(sh_dev "ls -l $D" | tr -d '\r' | tr '\n' ';')"
  log "probe taskset: $(sh_dev 'command -v taskset || echo missing' | tr -d '\r')"
  state || die "probe: adb state read failed"
  log "probe state: $STATE_LINE"
}

phase_push() {
  own_hold
  log "phase push"
  sh_dev "mkdir -p $D $MODEL_DIR $DEV/prompts" >/dev/null
  local f want got
  for f in $RUNTIME_FILES run_diag.sh; do
    local src="$BIN/$f"; [[ "$f" == run_diag.sh ]] && src="$HERE/run_diag.sh"
    want="$(sha_local "$src")"
    got="$(sha_dev "$D/$f")"
    if [[ "$got" == "$want" ]]; then log "push runtime $f present, sha256 $want"; continue; fi
    local before="$got"
    ADB_TIMEOUT=600 adbs push "$src" "$D/$f" >/dev/null || die "push $f failed"
    got="$(sha_dev "$D/$f")"
    [[ "$got" == "$want" ]] || die "push verification failed: $f device $got local $want"
    log "push runtime $f sha256 $want (was ${before:-missing})"
  done
  sh_dev "chmod 755 $D/ortgenai_run $D/model_benchmark" >/dev/null
  for f in $MODEL_FILES; do
    local src size
    src="$(readlink -f "$MODEL/$f")"
    size="$(stat -Lf %z "$src")"
    ADB_TIMEOUT=1800 adbs push "$src" "$MODEL_DIR/$f" >/dev/null || die "push model $f failed"
    got="$(sh_dev "stat -c %s $MODEL_DIR/$f" | tr -d '\r')"
    [[ "$got" == "$size" ]] || die "push verification failed: model $f device $got bytes, local $size"
    log "push model $f $got bytes"
  done
  want="$(sha_local "$LOCAL_PROMPT")"
  got="$(sha_dev "$PROMPT")"
  if [[ "$got" == MISSING || -z "$got" ]]; then
    adbs push "$LOCAL_PROMPT" "$PROMPT" >/dev/null || die "push prompt failed"
    got="$(sha_dev "$PROMPT")"
    log "push prompt long-context-1024-gen256.txt sha256 $got"
  elif [[ "$got" == "$want" ]]; then
    log "prompt long-context-1024-gen256.txt present, sha256 matches $want"
  fi
  [[ "$got" == "$want" ]] || die "$PROMPT is $got, local $want: not ours, not overwritten"
  log "push done; disk: $(sh_dev 'df -k /data | tail -1' | tr -d '\r')"
}

engine_lines() {  # engine_lines <engine.txt>: the lines that carry results or errors
  grep -E '^(ORTGENAI|Error|Exception|Batch size|Model Creation|Generator Creation|Prompt processing|Token generation|Token sampling|E2E|Peak working set|Profiling|WARNING)|avg \((us|tokens/s|ms)\)' "$1" || true
}

sampler_lines() {  # sampler_lines <sampler.txt>: launch, caps, sockets, thread count, end
  grep -E '^(START|LAUNCH|CPUMAX|SOCKET|KILLED|EXIT_CODE|END|LOGCAT_LINES|OUTDIR)' "$1" || true
  awk '$1=="TICK" {for (i=2;i<=NF;i++) if ($i ~ /^Threads:/) {split($i,a,":"); if (a[2]+0 > m) m=a[2]+0}} END {print "max Threads: " m+0}' "$1"
}

phase_run() {
  own_hold
  [[ -n "${FRAME_START:-}" ]] || die "FRAME_START is not set"
  log "phase run ${*:-(all)}; frame left $(( $(remaining) / 60 )) min"
  # the campaign lock other bench drivers probe, held by a perl child for this phase
  local lockflag; lockflag="$(mktemp)"
  perl -MFcntl=:flock -e 'open(my $f, ">", $ARGV[0]) or exit 2; flock($f, LOCK_EX | LOCK_NB) or do { print {*STDOUT} "held\n"; exit 1 };
    open(my $o, ">", $ARGV[2]); print $o "locked\n"; close $o; sleep 1 while kill 0, $ARGV[1];' "$LOCK" $$ "$lockflag" >/dev/null 2>&1 &
  local lockpid=$! i
  disown $lockpid  # the EXIT trap kills it; no job-control "Terminated" line at exit
  for i in 1 2 3 4 5 6 7 8 9 10; do
    [[ "$(cat "$lockflag" 2>/dev/null)" == locked ]] && break
    kill -0 $lockpid 2>/dev/null || break
    command sleep 0.5
  done
  [[ "$(cat "$lockflag" 2>/dev/null)" == locked ]] || { kill $lockpid 2>/dev/null; die "campaign lock held by another driver: $LOCK"; }
  log "campaign lock taken ($LOCK, perl pid $lockpid)"
  trap 'kill '"$lockpid"' 2>/dev/null; rm -f '"$lockflag" EXIT
  mkdir -p "$OUTDIR"
  local first=1
  while IFS='|' read -r id tag mask limit gmode pause bin args; do
    if (( $# )) && [[ " $* " != *" $id "* ]]; then continue; fi
    local left; left=$(remaining)
    if (( left < STOP_MARGIN_S )); then log "frame: $(( left / 60 )) min left (< 8): $id and later not started"; return 0; fi
    if ! gate "$gmode"; then log "frame: gate did not pass before the 8 min margin: $id and later not started"; return 0; fi
    left=$(remaining)
    if (( left < STOP_MARGIN_S )); then log "frame: $(( left / 60 )) min left (< 8): $id and later not started"; return 0; fi
    local lim=$limit
    (( lim > left - END_MARGIN_S )) && lim=$(( left - END_MARGIN_S ))
    log "launch $id $tag: mask=$mask limit=${lim}s: $bin $args"
    local out rc
    out="$(ADB_TIMEOUT=$(( lim + 120 )) adbs shell "sh $D/run_diag.sh $tag $mask $lim $bin $args" 2>&1)"; rc=$?
    out="$(tr -d '\r' <<<"$out")"
    if [[ $rc -ne 0 && "$out" != *EXIT_CODE=* && "$out" != *KILLED* ]]; then
      log "launch $id: lost (adb rc $rc, output ${out: -300}); no record, not re-run"
      log "adb devices: $(adb devices | tr '\n' ';')"
      return 1
    fi
    log "launch $id: ${out##*$'\n'}"
    ADB_TIMEOUT=300 adbs pull "$D/out/$tag.engine.txt" "$D/out/$tag.sampler.txt" "$D/out/$tag.d" "$OUTDIR/" >/dev/null ||
      log "pull $id: failed (the files stay on the device for the final pull)"
    if [[ -f "$OUTDIR/$tag.engine.txt" ]]; then
      engine_lines "$OUTDIR/$tag.engine.txt" | sed "s/^/  $id | /" | tee -a "$LOG" >/dev/null
      sampler_lines "$OUTDIR/$tag.sampler.txt" | sed "s/^/  $id ~ /" | tee -a "$LOG" >/dev/null
    fi
    state && log "after $id: $STATE_LINE"
    if [[ "$out" == *KILLED* ]]; then log "$id was killed at its limit; continuing"; fi
    (( pause > 0 )) && { log "pause ${pause}s"; sleep "$pause"; }
  done <<<"$PLAN"
  log "phase run done; frame left $(( $(remaining) / 60 )) min"
}

phase_pull() {
  own_hold
  mkdir -p "$OUTDIR"
  ADB_TIMEOUT=300 adbs pull "$D/out/." "$OUTDIR/" >/dev/null || die "pull failed"
  log "pulled: $(ls "$OUTDIR" | tr '\n' ' ')"
}

phase_clean() {
  own_hold
  sh_dev "rm -rf $MODEL_DIR $D/out" >/dev/null
  log "clean: model folder and out/ removed; left: $(sh_dev "ls -d $MODEL_DIR $D/out 2>/dev/null; ls $D" | tr -d '\r' | tr '\n' ' ')"
  log "clean: disk $(sh_dev 'df -k /data | tail -1' | tr -d '\r'); engines: $(sh_dev "ps -A | grep -E 'ortgenai|model_benchmark' | grep -v grep" | tr -d '\r' || echo none)"
}

[[ -n "${DIAG_SOURCE_ONLY:-}" ]] && return 0   # offline tests source the functions

case "${1:-}" in
  dry) phase_dry ;;
  probe) phase_probe ;;
  push) phase_push ;;
  run) shift; phase_run "$@" ;;
  pull) phase_pull ;;
  clean) phase_clean ;;
  *) sed -n '2,30p' "$0"; exit 2 ;;
esac
