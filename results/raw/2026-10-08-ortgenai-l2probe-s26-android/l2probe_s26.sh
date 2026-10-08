#!/bin/bash
# Host side of ORT GenAI round r2c on the Galaxy S26 (2026-10-08, by hand): the
# L2 cache value ONNX Runtime 1.30.0 sizes the GroupQueryAttention CPU flash
# tiles from, and the prefill with that path switched off. adb, perl and POSIX
# tools only (no python: the Mac measurement-window guard). The r2b helpers (adb
# wrapper, hold check, device state, gate, engine / sampler line filters) are
# sourced from ../2026-10-07-ortgenai-diag-s26-android/diag_s26.sh, and each
# launch goes through r2b's on-device sampler run_diag.sh, unchanged.
#
#   dry   no adb: builds l2probe (android/ortgenai/l2probe.c, NDK clang) into
#         $L2PROBE_DIR, checks the local inputs, prints the plan
#   all   the whole device part in one call, so a stopped session still leaves
#         the phone clean and the hold returned:
#           probe    busy checks, device state, env inheritance through sh
#           push     l2probe, the runtime files only if missing or changed
#                    (sha256), the model folder (bytes checked)
#           (a)      l2probe: what bionic's sysconf() reports for the caches
#           (b)(c)   sysfs cacheinfo of every CPU (index entries of cpu0 and
#                    cpu6), MIDR per CPU, SoC properties, /proc/cpuinfo
#           (d)      model_benchmark -l 512, then -l 1024 --profile_prefill (the
#                    r2b D2c / D1 shapes), both with
#                    ORT_GQA_DISABLE_FLASH_ATTENTION=1, each after the gate,
#                    120 s apart; the engine's environment is read from /proc
#                    while it runs
#           clean    the model folder (only if this call pushed it), this
#                    round's out/ files, l2probe; the runtime dir stays
#           release  touches $RELEASE_FILE: the keeper (hold_keeper.sh) gives
#                    the hold back
#
# Env: KEEPER_PID, RELEASE_FILE (all); L2PROBE_DIR (dry, all). The frame starts
# at the hold's own "started" time. Log: host.log next to this file.
# Offline tests only: R2C_HOLD, R2C_LOCK, R2C_OUTDIR, R2C_PAUSE_S, DIAG_LOG.
# Frame: 15 min from the hold acquisition. `all` does not start with less than
# 8 min left; no run starts with less than 4 min left; each run's on-device
# limit is cut to end 2 min before the frame does (pull, clean, release).
# Gate (r2b's): every policy's scaling_max_freq == cpuinfo_max_freq, Thermal
# Status 0, battery <= 34.0 C.
set -uo pipefail

R2C_DIR="$(cd "$(dirname "$0")" && pwd)"
R2B_DIR="$(cd "$R2C_DIR/../2026-10-07-ortgenai-diag-s26-android" && pwd)"
DIAG_SOURCE_ONLY=1
DIAG_LOG="${DIAG_LOG:-$R2C_DIR/host.log}"
# shellcheck source=../2026-10-07-ortgenai-diag-s26-android/diag_s26.sh
source "$R2B_DIR/diag_s26.sh"
# diag_s26.sh takes its HERE from $0 (this file), so REPO, BIN, MODEL and LOG
# resolve as they should; this round's own values:
SCRIPT=ortgenai_r2c_l2
HOLD="${R2C_HOLD:-$HOLD}"
LOCK="${R2C_LOCK:-$LOCK}"
OUTDIR="${R2C_OUTDIR:-$R2C_DIR/device}"
FRAME_S=$((15 * 60))
START_MIN_S=$((8 * 60))
STOP_MARGIN_S=$((4 * 60))
END_MARGIN_S=$((2 * 60))
PAUSE_S="${R2C_PAUSE_S:-120}"
DATA_MIN_KB=$((1536 * 1024))
NOFLASH="ORT_GQA_DISABLE_FLASH_ATTENTION=1"
L2SRC="$REPO/android/ortgenai/l2probe.c"
MB="-i $MODEL_DIR --use_random_tokens -g 8 -ml 2048 -r 1 -w 0 -v -e cpu"
# id | tag | limit_s | model_benchmark args
PLAN="E1|r2c-E1-mb-l512-noflash|180|$MB -l 512
E2|r2c-E2-mb-l1024-profile-noflash|300|$MB -l 1024 --profile_prefill"

MODEL_PUSHED=0
CLEAN_NEEDED=0
LOCKPID=""

phase_dry() {
  log "r2c phase dry (no adb)"
  [[ -n "${L2PROBE_DIR:-}" ]] || die "L2PROBE_DIR is not set"
  local ndk cc ok=1 want got f
  ndk="${ANDROID_NDK_HOME:-$(ls -d "$HOME"/Library/Android/sdk/ndk/* 2>/dev/null | sort -V | tail -1)}"
  cc="$ndk/toolchains/llvm/prebuilt/darwin-x86_64/bin/clang"
  mkdir -p "$L2PROBE_DIR"
  # dynamically linked on purpose: the device's libc.so answers sysconf()
  if "$cc" --target=aarch64-linux-android28 -O2 -Wall -fPIE -pie -o "$L2PROBE_DIR/l2probe" "$L2SRC" 2>"$L2PROBE_DIR/build.err"; then
    log "dry: l2probe built: sha256 $(sha_local "$L2PROBE_DIR/l2probe") from l2probe.c sha256 $(sha_local "$L2SRC"); ndk $(sed -n 's/^Pkg.Revision *= *//p' "$ndk/source.properties"); $("$cc" --version | head -1); flags --target=aarch64-linux-android28 -O2 -Wall -fPIE -pie"
  else
    log "dry: l2probe build FAILED: $(tr '\n' ' ' <"$L2PROBE_DIR/build.err")"
    ok=0
  fi
  for f in $RUNTIME_FILES; do
    want="$(awk -v f="$f" '$2 == f {print $1}' "$BIN/MANIFEST.txt")"
    got="$(sha_local "$BIN/$f")"
    if [[ -n "$want" && "$want" == "$got" ]]; then log "dry: $f sha256 $got = MANIFEST"; else log "dry: $f sha256 $got != MANIFEST ${want:-missing}"; ok=0; fi
  done
  log "dry: run_diag.sh (r2b, unchanged) sha256 $(sha_local "$R2B_DIR/run_diag.sh"); diag_s26.sh (sourced) sha256 $(sha_local "$R2B_DIR/diag_s26.sh")"
  for f in $MODEL_FILES; do
    if [[ -f "$MODEL/$f" ]]; then log "dry: model $f $(stat -Lf %z "$MODEL/$f") bytes"; else log "dry: model $f MISSING"; ok=0; fi
  done
  log "dry: hold now: $(cat "$HOLD" 2>/dev/null || echo none)"
  while IFS='|' read -r id tag limit args; do
    log "dry: plan $id $tag limit=${limit}s: $NOFLASH sh $D/run_diag.sh $tag - $limit model_benchmark $args"
  done <<<"$PLAN"
  (( ok )) && log "dry: PASS" || die "dry: local inputs do not match"
}

frame_start_of_hold() {  # epoch seconds of the hold's "started" field
  local s
  s="$(sed -n 's/.*"started": "\([0-9-]* [0-9:]*\)".*/\1/p' "$HOLD")"
  [[ -n "$s" ]] || return 1
  date -j -f '%Y-%m-%d %H:%M:%S' "$s" +%s
}

finish() {  # EXIT trap of `all`: clean if the device was touched, give the hold back
  local rc=$? i
  trap - EXIT
  if (( CLEAN_NEEDED )); then clean || log "clean: failed (see above)"; fi
  [[ -n "$LOCKPID" ]] && kill "$LOCKPID" 2>/dev/null
  touch "$RELEASE_FILE"
  log "release requested ($RELEASE_FILE); exit code $rc"
  for i in $(seq 1 20); do
    grep -q "\"pid\": $KEEPER_PID," "$HOLD" 2>/dev/null || break
    command sleep 1
  done
  log "hold now: $(cat "$HOLD" 2>/dev/null || echo none)"
  exit "$rc"
}

probe() {
  log "probe"
  if perl -MFcntl=:flock -e 'open(my $f, ">", $ARGV[0]) or exit 2; flock($f, LOCK_EX | LOCK_NB) or exit 1; exit 0' "$LOCK"; then
    log "probe lock: free ($LOCK)"
  else
    die "probe lock: HELD ($LOCK): another driver is on the phone"
  fi
  log "probe hold: $(cat "$HOLD")"
  # bench drivers on the Mac: the launch's pattern, plus any python spelling
  # (Homebrew's framework binary is ".../MacOS/Python"). A driver drives the
  # phone whose campaign lock it (or its parent) holds open; one on another
  # serial is not this phone's, one with no lock cannot be placed and stops us.
  local p lk pp mine="" seen=""
  for p in $( { pgrep -f '^[^ ]*[p]ython[0-9.]* [^ ]*android/bench/run_'; pgrep -f 'android/bench/[r]un_(campaign|cell|profile)'; } | sort -u); do
    lk="$(lsof -p "$p" 2>/dev/null | grep -o 'edge-llm-bench-android-[A-Za-z0-9_]*\.lock' | head -1)"
    if [[ -z "$lk" ]]; then
      pp="$(ps -o ppid= -p "$p" | tr -d ' ')"
      lk="$(lsof -p "$pp" 2>/dev/null | grep -o 'edge-llm-bench-android-[A-Za-z0-9_]*\.lock' | head -1)"
    fi
    seen="$seen pid $p ($(ps -o command= -p "$p" | grep -o 'android/bench/run_[a-z_]*\.py' | head -1), lock ${lk:-none});"
    [[ -z "$lk" || "$lk" == "edge-llm-bench-android-$SERIAL.lock" ]] && mine="$mine $p"
  done
  [[ -z "$mine" ]] || die "probe host drivers on this phone or unplaced:$mine;$seen"
  log "probe host drivers: ${seen:- none} (none on $SERIAL)"
  adb devices | grep -q "^$SERIAL[[:space:]]*device" || die "probe: $SERIAL is not in adb devices: $(adb devices | tr '\n' ';')"
  local eng; eng="$(sh_dev "ps -A | grep -E 'litert_lm|llama|ortgenai|model_benchmark|llama_main|executor' | grep -v grep" | tr -d '\r' | tr '\n' ';')"
  [[ -z "$eng" ]] || die "probe device engines: $eng"
  log "probe device engines: none"
  log "probe android: $(sh_dev 'echo $(getprop ro.product.model) / Android $(getprop ro.build.version.release) / patch $(getprop ro.build.version.security_patch) / $(getprop ro.build.fingerprint) / uptime $(cut -d" " -f1 /proc/uptime) / cpus online $(cat /sys/devices/system/cpu/online)' | tr -d '\r')"
  local df avail; df="$(sh_dev 'df -k /data | tail -1' | tr -d '\r')"
  avail="$(awk '{print $4}' <<<"$df")"
  log "probe disk: $df"
  [[ "$avail" =~ ^[0-9]+$ && "$avail" -ge $DATA_MIN_KB ]] || die "probe disk: /data free ${avail:-?} KB < 1.5 GB"
  log "probe runtime dir: $(sh_dev "ls -l $D" | tr -d '\r' | tr '\n' ';')"
  log "probe out/: $(sh_dev "ls -la $D/out 2>&1" | tr -d '\r' | tr '\n' ';')"
  log "probe model dir: $(sh_dev "ls -la $MODEL_DIR 2>&1" | tr -d '\r' | tr '\n' ';')"
  log "probe env through sh: $(sh_dev "$NOFLASH sh -c 'Y=1 cat /proc/self/environ' | tr '\\000' '\\n' | grep -E '^(ORT_GQA_DISABLE_FLASH_ATTENTION|Y)='" | tr -d '\r' | tr '\n' ' ')"
  state || die "probe: adb state read failed"
  log "probe state: $STATE_LINE"
  [[ "${THERMAL:-9}" =~ ^[0-9]+$ && "$THERMAL" -lt 3 ]] || die "probe: thermal status ${THERMAL:-?} (>= 3 or unread)"
}

take_lock() {  # the campaign lock other bench drivers probe, held by a perl child until exit
  local flag i; flag="$(mktemp)"
  perl -MFcntl=:flock -e 'open(my $f, ">", $ARGV[0]) or exit 2; flock($f, LOCK_EX | LOCK_NB) or exit 1;
    open(my $o, ">", $ARGV[2]); print $o "locked\n"; close $o; sleep 1 while kill 0, $ARGV[1];' "$LOCK" $$ "$flag" >/dev/null 2>&1 &
  LOCKPID=$!
  disown "$LOCKPID"
  for i in 1 2 3 4 5 6 7 8 9 10; do
    [[ "$(cat "$flag" 2>/dev/null)" == locked ]] && break
    kill -0 "$LOCKPID" 2>/dev/null || break
    command sleep 0.5
  done
  if [[ "$(cat "$flag" 2>/dev/null)" != locked ]]; then
    rm -f "$flag"; kill "$LOCKPID" 2>/dev/null; LOCKPID=""
    die "campaign lock taken by another driver: $LOCK"
  fi
  rm -f "$flag"
  log "campaign lock taken ($LOCK, perl pid $LOCKPID)"
}

push_round() {
  log "push"
  sh_dev "mkdir -p $D" >/dev/null
  local f want got src
  want="$(sha_local "$L2PROBE_DIR/l2probe")"
  ADB_TIMEOUT=120 adbs push "$L2PROBE_DIR/l2probe" "$D/l2probe" >/dev/null || die "push l2probe failed"
  sh_dev "chmod 755 $D/l2probe" >/dev/null
  got="$(sha_dev "$D/l2probe")"
  [[ "$got" == "$want" ]] || die "push verification failed: l2probe device $got local $want"
  log "push l2probe sha256 $want"
  for f in $RUNTIME_FILES run_diag.sh; do
    src="$BIN/$f"; [[ "$f" == run_diag.sh ]] && src="$R2B_DIR/run_diag.sh"
    want="$(sha_local "$src")"
    got="$(sha_dev "$D/$f")"
    if [[ "$got" == "$want" ]]; then log "push runtime $f present, sha256 $want"; continue; fi
    ADB_TIMEOUT=600 adbs push "$src" "$D/$f" >/dev/null || die "push $f failed"
    local after; after="$(sha_dev "$D/$f")"
    [[ "$after" == "$want" ]] || die "push verification failed: $f device $after local $want"
    log "push runtime $f sha256 $want (device had ${got:-nothing})"
  done
  sh_dev "chmod 755 $D/ortgenai_run $D/model_benchmark" >/dev/null
  local present size
  present="$(sh_dev "[ -e $MODEL_DIR ] && echo yes || echo no" | tr -d '\r')"
  if [[ "$present" == yes ]]; then
    for f in $MODEL_FILES; do
      size="$(stat -Lf %z "$MODEL/$f")"
      got="$(sh_dev "stat -c %s $MODEL_DIR/$f 2>/dev/null" | tr -d '\r')"
      [[ "$got" == "$size" ]] || die "model folder present but not ours: $f device ${got:-missing} bytes, local $size; not overwritten"
    done
    log "push model folder present before this round, every file's bytes match: used as is and left in place"
    return 0
  fi
  sh_dev "mkdir -p $MODEL_DIR" >/dev/null
  MODEL_PUSHED=1
  for f in $MODEL_FILES; do
    src="$(readlink -f "$MODEL/$f")"
    size="$(stat -Lf %z "$src")"
    ADB_TIMEOUT=1800 adbs push "$src" "$MODEL_DIR/$f" >/dev/null || die "push model $f failed"
    got="$(sh_dev "stat -c %s $MODEL_DIR/$f" | tr -d '\r')"
    [[ "$got" == "$size" ]] || die "push verification failed: model $f device $got bytes, local $size"
    log "push model $f $got bytes"
  done
  log "push done; disk: $(sh_dev 'df -k /data | tail -1' | tr -d '\r')"
}

cache_reads() {
  mkdir -p "$OUTDIR"
  sh_dev "$D/l2probe; echo EXIT=\$?" | tr -d '\r' >"$OUTDIR/r2c-l2probe.txt"
  log "(a) l2probe: $(tr '\n' ';' <"$OUTDIR/r2c-l2probe.txt")"
  sh_dev 'for c in /sys/devices/system/cpu/cpu[0-9]*; do
      n=${c##*/}
      if [ -d $c/cache ]; then echo "CACHEDIR $n $(ls $c/cache | tr "\n" " ")"; else echo "CACHEDIR $n absent"; fi
      echo "MIDR $n $(cat $c/regs/identification/midr_el1 2>&1)"
    done
    for n in 0 6; do
      for d in /sys/devices/system/cpu/cpu$n/cache/index*; do
        [ -d "$d" ] || { echo "INDEX cpu$n none ($d)"; continue; }
        l="INDEX cpu$n ${d##*/}"
        for k in level type size shared_cpu_list ways_of_associativity coherency_line_size number_of_sets physical_line_partition allocation_policy write_policy id; do
          [ -e $d/$k ] && l="$l $k=$(cat $d/$k 2>&1 | tr " " ",")"
        done
        echo "$l"
      done
      echo "LS cpu$n/cache: $(ls -la /sys/devices/system/cpu/cpu$n/cache 2>&1 | tr "\n" ";")"
    done
    for p in ro.soc.manufacturer ro.soc.model ro.board.platform ro.hardware ro.product.model ro.build.version.release ro.build.version.sdk ro.build.fingerprint; do echo "PROP $p=$(getprop $p)"; done
    echo "UNAME $(uname -srm)"' | tr -d '\r' >"$OUTDIR/r2c-cache.txt"
  log "(b) cache dirs: $(grep -E '^(CACHEDIR|INDEX)' "$OUTDIR/r2c-cache.txt" | tr '\n' ';')"
  sh_dev 'cat /proc/cpuinfo' | tr -d '\r' >"$OUTDIR/r2c-cpuinfo.txt"
  log "(c) /proc/cpuinfo: $(grep -c '^processor' "$OUTDIR/r2c-cpuinfo.txt") processors; parts: $(sed -n 's/^CPU part[[:space:]]*: *//p' "$OUTDIR/r2c-cpuinfo.txt" | sort | uniq -c | awk '{printf "%s x%s ", $2, $1}'); hardware: $(sed -n 's/^Hardware[[:space:]]*: *//p' "$OUTDIR/r2c-cpuinfo.txt" | head -1)"
}

launch() {  # launch <id> <tag> <limit_s> <args>: one engine launch through run_diag.sh, flash path off
  local id=$1 tag=$2 lim=$3 args=$4 tmp bg i epid="" out rc
  tmp="$(mktemp -d)"
  local cmd="$NOFLASH sh $D/run_diag.sh $tag - $lim model_benchmark $args"
  log "launch $id $tag: limit=${lim}s: $cmd"
  ( ADB_TIMEOUT=$(( lim + 120 )) adbs shell "$cmd" >"$tmp/out" 2>&1; echo $? >"$tmp/rc" ) &
  bg=$!
  for i in $(seq 1 40); do
    command sleep 0.5
    epid="$(sh_dev "sed -n 's/.*engine_pid=\([0-9]*\).*/\1/p' $D/out/$tag.sampler.txt 2>/dev/null" | tr -d '\r')"
    [[ -n "$epid" || -e "$tmp/rc" ]] && break
  done
  if [[ "$epid" =~ ^[0-9]+$ ]]; then
    sh_dev "echo ENGINE_PID=$epid; echo EXE=\$(readlink /proc/$epid/exe); tr '\\000' '\\n' </proc/$epid/environ | grep -E '^(ORT_|LD_LIBRARY_PATH=)' || echo ENVIRON_UNREAD" | tr -d '\r' >"$OUTDIR/$tag.environ.txt"
    log "  $id environ: $(tr '\n' ' ' <"$OUTDIR/$tag.environ.txt")"
  else
    log "  $id environ: engine pid not seen (${epid:-none})"
  fi
  wait "$bg"
  out="$(tr -d '\r' <"$tmp/out")"; rc="$(cat "$tmp/rc" 2>/dev/null || echo '?')"
  rm -rf "$tmp"
  if [[ "$rc" != 0 && "$out" != *EXIT_CODE=* && "$out" != *KILLED* ]]; then
    log "launch $id: lost (adb rc $rc, output ${out: -300}); no record, not re-run"
    log "adb devices: $(adb devices | tr '\n' ';')"
    return 1
  fi
  log "launch $id: ${out##*$'\n'}"
  ADB_TIMEOUT=300 adbs pull "$D/out/$tag.engine.txt" "$D/out/$tag.sampler.txt" "$D/out/$tag.d" "$OUTDIR/" >/dev/null ||
    log "pull $id: failed (the files stay on the device until clean)"
  if [[ -f "$OUTDIR/$tag.engine.txt" ]]; then
    engine_lines "$OUTDIR/$tag.engine.txt" | sed "s/^/  $id | /" | tee -a "$LOG" >/dev/null
    sampler_lines "$OUTDIR/$tag.sampler.txt" | sed "s/^/  $id ~ /" | tee -a "$LOG" >/dev/null
  fi
  state && log "after $id: $STATE_LINE"
  [[ "$out" == *KILLED* ]] && log "$id was killed at its limit"
  return 0
}

runs() {
  local first=1 id tag limit args left lim
  while IFS='|' read -r id tag limit args; do
    if (( ! first )); then log "pause ${PAUSE_S}s"; sleep "$PAUSE_S"; fi
    first=0
    left=$(remaining)
    if (( left < STOP_MARGIN_S )); then log "frame: $(( left / 60 )) min left (< 4): $id and later not started"; return 0; fi
    if ! gate full; then log "frame: gate did not pass before the 4 min margin: $id and later not started"; return 0; fi
    left=$(remaining)
    if (( left < STOP_MARGIN_S )); then log "frame: $(( left / 60 )) min left (< 4): $id and later not started"; return 0; fi
    lim=$limit
    (( lim > left - END_MARGIN_S )) && lim=$(( left - END_MARGIN_S ))
    launch "$id" "$tag" "$lim" "$args" || return 1
  done <<<"$PLAN"
}

clean() {
  local local_list dev_list
  dev_list="$(sh_dev "cd $D/out 2>/dev/null && for f in r2c-*; do [ -e \"\$f\" ] && echo \"\$f\"; done" | tr -d '\r' | sort | tr '\n' ' ')"
  local_list="$(ls "$OUTDIR" 2>/dev/null | grep -E '^r2c-E' | grep -v environ | sort | tr '\n' ' ')"
  log "clean: device out/ r2c files: ${dev_list:-none}; pulled: ${local_list:-none}"
  if (( MODEL_PUSHED )); then sh_dev "rm -rf $MODEL_DIR" >/dev/null; fi
  sh_dev "rm -rf $D/out/r2c-*; rmdir $D/out 2>/dev/null; rm -f $D/l2probe" >/dev/null
  log "clean: model folder $( (( MODEL_PUSHED )) && echo removed || echo 'not pushed by this round, left'), out/ r2c files and l2probe removed; left: $(sh_dev "ls -d $MODEL_DIR $D/out 2>/dev/null; ls $D" | tr -d '\r' | tr '\n' ' ')"
  log "clean: disk $(sh_dev 'df -k /data | tail -1' | tr -d '\r'); engines: $(sh_dev "ps -A | grep -E 'ortgenai|model_benchmark|l2probe' | grep -v grep" | tr -d '\r' | tr '\n' ';')"
}

phase_all() {
  [[ -n "${RELEASE_FILE:-}" && -n "${L2PROBE_DIR:-}" ]] || die "RELEASE_FILE and L2PROBE_DIR must be set"
  [[ -x "$L2PROBE_DIR/l2probe" ]] || die "no $L2PROBE_DIR/l2probe (run dry first)"
  own_hold
  trap finish EXIT
  trap 'exit 143' TERM INT
  FRAME_START="$(frame_start_of_hold)" || die "cannot read the hold's started time"
  local left; left=$(remaining)
  log "r2c phase all: hold since $(date -r "$FRAME_START" '+%H:%M:%S'), frame left $(( left / 60 )) min $(( left % 60 )) s"
  (( left >= START_MIN_S )) || die "frame: $(( left / 60 )) min left (< 8): not started"
  probe
  take_lock
  CLEAN_NEEDED=1
  push_round
  cache_reads
  runs
  log "phase all done; frame left $(( $(remaining) / 60 )) min"
}

case "${1:-}" in
  dry) phase_dry ;;
  all) phase_all ;;
  *) sed -n '2,36p' "$0"; exit 2 ;;
esac
