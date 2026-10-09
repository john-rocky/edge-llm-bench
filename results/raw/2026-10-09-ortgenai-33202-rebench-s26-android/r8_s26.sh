#!/bin/bash
# Host side of ORT GenAI round r8-33202 on the Galaxy S26 (2026-10-09, by hand):
# microsoft/onnxruntime PR #33202 (CPU GroupQueryAttention flash tiles when the
# L2 size is unknown) measured with the commands of issue #33196. Only
# libonnxruntime.so differs between the two runtime dirs on the phone:
#   old  /data/local/tmp/llmbench/ortgenai         the dashboard's pinned dir
#        (Maven onnxruntime-android 1.30.0): read and run, never written
#   new  /data/local/tmp/llmbench/ortgenai-33202   libonnxruntime.so built from
#        v1.30.0 + the PR (android/bin/ortgenai-33202/); libonnxruntime-genai.so,
#        libmat.so, model_benchmark and ortgenai_run copied on the phone from the
#        old dir (sha256 checked against MANIFEST.txt), plus ortgenai_run_dl
#        (android/ortgenai/ortgenai_run.cpp with --dump-logits) and run_r8.sh
# Every launch goes through run_r8.sh (this dir); flash off =
# ORT_GQA_DISABLE_FLASH_ATTENTION=1 in the launch's environment. adb, perl and
# POSIX tools only (no python: the Mac measurement-window guard). r2b's helpers
# (adb wrapper, hold check, device state, engine / sampler line filters) are
# sourced from ../2026-10-07-ortgenai-diag-s26-android/diag_s26.sh.
#
#   dry   no adb: local inputs against their sha256, both blocks' commands
#   A     block A, one hold: probe, push, 8 model_benchmark launches
#         (--use_random_tokens -g 8 -ml 2048 -r 1 -w 0 -v -e cpu; -l 512, and
#         -l 1024 --profile_prefill), old / new x flash on / off, 120 s apart,
#         each after the full gate; pull; clean (this block's out/ files, the
#         model folder if this block pushed it); release
#   B     block B, one hold: probe, push (what is missing), 4 ortgenai_run
#         launches on the 1K task prompt at budget 256 (the dashboard cell's
#         command), old / new x on / off, 120 s apart, full gate; then 4
#         ortgenai_run_dl --dump-logits launches at budget 8, 30 s apart, the
#         light gate; pull (the logits files to $DUMP_DIR, outside the repo);
#         clean (out/, the model folder if this block pushed it); release
# Both blocks list the old dir's files with sha256 at the start and the end
# (device/r8-<block>-olddir-{before,after}.txt) and log whether they match.
#
# Env: KEEPER_PID, RELEASE_FILE (A, B); DUMP_DIR (B). Log: host.log here.
# Offline tests only: R8_HOLD, R8_LOCK, R8_OUTDIR, R8_PAUSE_S, R8_DUMP_PAUSE_S, DIAG_LOG.
# Frame: 30 min from the hold's own "started" time. Block A does not start
# with less than 20 min left, block B with less than 15; no launch starts with
# less than 4 min left; each launch's on-device limit is cut to end 2 min
# before the frame does (pull, clean, release).
# Gates: full = every policy's scaling_max_freq == cpuinfo_max_freq, Thermal
# Status 0, battery <= 34.0 C (r2c's); light = Thermal Status < 3 (the dump
# launches compare numbers, not times).
set -uo pipefail

R8_DIR="$(cd "$(dirname "$0")" && pwd)"
R2B_DIR="$(cd "$R8_DIR/../2026-10-07-ortgenai-diag-s26-android" && pwd)"
DIAG_SOURCE_ONLY=1
DIAG_LOG="${DIAG_LOG:-$R8_DIR/host.log}"
# shellcheck source=../2026-10-07-ortgenai-diag-s26-android/diag_s26.sh
source "$R2B_DIR/diag_s26.sh"
# diag_s26.sh takes HERE from $0 (this file): REPO, BIN (the release
# ortgenai-0.17.0 dir), MODEL, LOCAL_PROMPT and LOG resolve as they should.
HOLD="${R8_HOLD:-$HOLD}"
LOCK="${R8_LOCK:-$LOCK}"
OUTDIR="${R8_OUTDIR:-$R8_DIR/device}"
D_OLD=$D
D8=$DEV/ortgenai-33202
BIN8="$REPO/android/bin/ortgenai-33202"
NEW_ORT_SHA=9fa431b6527d0d5d04da0d18e54ad9d51d0ce92b857f17a5d7e41f3abf78ce4b
COPIED_FILES="libonnxruntime-genai.so libmat.so model_benchmark ortgenai_run"
FRAME_S=$((30 * 60))
STOP_MARGIN_S=$((4 * 60))
END_MARGIN_S=$((2 * 60))
PAUSE_S="${R8_PAUSE_S:-120}"
DUMP_PAUSE_S="${R8_DUMP_PAUSE_S:-30}"
DATA_MIN_KB=$((1536 * 1024))
NOFLASH="ORT_GQA_DISABLE_FLASH_ATTENTION=1"
MB="-i $MODEL_DIR --use_random_tokens -g 8 -ml 2048 -r 1 -w 0 -v -e cpu"
RUN256="-i $MODEL_DIR --prompt_file $PROMPT -g 256 -ml 2048"
RUN8="-i $MODEL_DIR --prompt_file $PROMPT -g 8 -ml 2048"
# id | tag | runtime dir | ONNX Runtime | flash | gate | limit_s | binary | args (DUMP = --dump-logits <the launch's dir>/logits.f32)
# Block A pairs every comparison in adjacent launches: 512 old on, new on, new
# off, old off; 1024 in the reverse order (old off, new off, new on, old on).
PLAN_A="A1|r8-A1-mb512-old-on|old|old|on|full|180|model_benchmark|$MB -l 512
A2|r8-A2-mb512-new-on|new|new|on|full|180|model_benchmark|$MB -l 512
A3|r8-A3-mb512-new-off|new|new|off|full|180|model_benchmark|$MB -l 512
A4|r8-A4-mb512-old-off|old|old|off|full|180|model_benchmark|$MB -l 512
A5|r8-A5-mb1024p-old-off|old|old|off|full|300|model_benchmark|$MB -l 1024 --profile_prefill
A6|r8-A6-mb1024p-new-off|new|new|off|full|300|model_benchmark|$MB -l 1024 --profile_prefill
A7|r8-A7-mb1024p-new-on|new|new|on|full|300|model_benchmark|$MB -l 1024 --profile_prefill
A8|r8-A8-mb1024p-old-on|old|old|on|full|300|model_benchmark|$MB -l 1024 --profile_prefill"
# B5-B8 run ortgenai_run_dl from the new dir; B7 and B8 load the release
# library through ORT_LIB_PATH (the GenAI libraries are the same bytes).
PLAN_B="B1|r8-B1-run1k-old-on|old|old|on|full|300|ortgenai_run|$RUN256
B2|r8-B2-run1k-new-on|new|new|on|full|300|ortgenai_run|$RUN256
B3|r8-B3-run1k-new-off|new|new|off|full|300|ortgenai_run|$RUN256
B4|r8-B4-run1k-old-off|old|old|off|full|300|ortgenai_run|$RUN256
B5|r8-B5-dl-new-on|new|new|on|light|120|ortgenai_run_dl|$RUN8 DUMP
B6|r8-B6-dl-new-off|new|new|off|light|120|ortgenai_run_dl|$RUN8 DUMP
B7|r8-B7-dl-old-off|new|old|off|light|120|ortgenai_run_dl|$RUN8 DUMP
B8|r8-B8-dl-old-on|new|old|on|light|180|ortgenai_run_dl|$RUN8 DUMP"

BLOCK=""
MODEL_PUSHED=0
CLEAN_NEEDED=0
LOCKPID=""

dir_of() { [[ "$1" == old ]] && echo "$D_OLD" || echo "$D8"; }

command_of() {  # command_of <tag> <rt> <ort> <flash> <limit> <bin> <args>: the adb shell command of one launch
  local tag=$1 rt ort env="" args=$7
  rt="$(dir_of "$2")"; ort="$(dir_of "$3")"
  [[ "$4" == off ]] && env="$NOFLASH "
  args="${args/DUMP/--dump-logits $D8/out/$tag.d/logits.f32}"
  echo "${env}sh $D8/run_r8.sh $tag $rt $ort $5 $rt/$6 $args"
}

phase_dry() {
  log "r8 phase dry (no adb)"
  local ok=1 want got f
  for f in $RUNTIME_FILES; do
    want="$(awk -v f="$f" '$2 == f {print $1}' "$BIN/MANIFEST.txt")"
    got="$(sha_local "$BIN/$f")"
    if [[ -n "$want" && "$want" == "$got" ]]; then log "dry: release $f sha256 $got = MANIFEST"; else log "dry: release $f sha256 $got != MANIFEST ${want:-missing}"; ok=0; fi
  done
  got="$(sha_local "$BIN8/libonnxruntime.so")"
  if [[ "$got" == "$NEW_ORT_SHA" ]]; then log "dry: new libonnxruntime.so sha256 $got (v1.30.0 + PR #33202, ROUND8)"; else log "dry: new libonnxruntime.so sha256 $got != $NEW_ORT_SHA"; ok=0; fi
  log "dry: ortgenai_run_dl sha256 $(sha_local "$BIN8/ortgenai_run_dl") (android/ortgenai/ortgenai_run.cpp sha256 $(sha_local "$REPO/android/ortgenai/ortgenai_run.cpp"))"
  log "dry: run_r8.sh sha256 $(sha_local "$R8_DIR/run_r8.sh"); diag_s26.sh (sourced) sha256 $(sha_local "$R2B_DIR/diag_s26.sh")"
  for f in $MODEL_FILES; do
    if [[ -f "$MODEL/$f" ]]; then log "dry: model $f $(stat -Lf %z "$MODEL/$f") bytes"; else log "dry: model $f MISSING"; ok=0; fi
  done
  log "dry: prompt long-context-1024-gen256.txt sha256 $(sha_local "$LOCAL_PROMPT")"
  log "dry: hold now: $(cat "$HOLD" 2>/dev/null || echo none); also: $(cat "$HOLD.s26" "$HOLD.RFGL80R6A6H" 2>/dev/null || echo none)"
  local id tag rt ort flash gmode limit bin args
  while IFS='|' read -r id tag rt ort flash gmode limit bin args; do
    log "dry: plan $id gate=$gmode limit=${limit}s: $(command_of "$tag" "$rt" "$ort" "$flash" "$limit" "$bin" "$args")"
  done <<<"$PLAN_A
$PLAN_B"
  (( ok )) && log "dry: PASS" || die "dry: local inputs do not match"
}

frame_start_of_hold() {  # epoch seconds of the hold's "started" field
  local s
  s="$(sed -n 's/.*"started": "\([0-9-]* [0-9:]*\)".*/\1/p' "$HOLD")"
  [[ -n "$s" ]] || return 1
  date -j -f '%Y-%m-%d %H:%M:%S' "$s" +%s
}

finish() {  # EXIT trap of A / B: clean if the phone was touched, give the hold back
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

also_holds() {  # the S26's other hold names (ops/dashboard-v1/schedule.json hold_also_check)
  local f p
  for f in "$HOLD.s26" "$HOLD.RFGL80R6A6H"; do
    [[ -e "$f" ]] || continue
    p="$(sed -n 's/.*"pid": \([0-9]*\),.*/\1/p' "$f")"
    if [[ -z "$p" ]]; then die "probe: unowned hold present: $f"; fi
    if [[ "$p" != "$KEEPER_PID" ]] && kill -0 "$p" 2>/dev/null; then die "probe: $f held by live pid $p: $(cat "$f")"; fi
    log "probe: stale hold in $f (pid $p not alive): left alone"
  done
}

olddir_list() {  # olddir_list <label>: every file of the old dir with its sha256, to device/r8-<block>-olddir-<label>.txt
  local out="$OUTDIR/r8-$BLOCK-olddir-$1.txt"
  mkdir -p "$OUTDIR"
  sh_dev "cd $D_OLD && for f in *; do if [ -f \"\$f\" ]; then echo \"\$(sha256sum \"\$f\" | cut -d' ' -f1) \$(stat -c %s \"\$f\") \$f\"; else echo \"dir - \$f\"; fi; done" | tr -d '\r' >"$out"
  log "old dir ($1): $(awk '{printf "%s %s; ", $3, substr($1, 1, 8)}' "$out")"
}

probe() {
  log "probe ($BLOCK)"
  if perl -MFcntl=:flock -e 'open(my $f, ">", $ARGV[0]) or exit 2; flock($f, LOCK_EX | LOCK_NB) or exit 1; exit 0' "$LOCK"; then
    log "probe lock: free ($LOCK)"
  else
    die "probe lock: HELD ($LOCK): another driver is on the phone"
  fi
  log "probe hold: $(cat "$HOLD")"
  also_holds
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
  log "probe new dir: $(sh_dev "ls -l $D8 2>&1" | tr -d '\r' | tr '\n' ';')"
  log "probe model dir: $(sh_dev "ls -la $MODEL_DIR 2>&1" | tr -d '\r' | tr '\n' ';')"
  log "probe prompt: $(sh_dev "ls -l $PROMPT 2>&1" | tr -d '\r')"
  log "probe env through sh: $(sh_dev "$NOFLASH sh -c 'Y=1 cat /proc/self/environ' | tr '\\000' '\\n' | grep -E '^(ORT_GQA_DISABLE_FLASH_ATTENTION|Y)='" | tr -d '\r' | tr '\n' ' ')"
  olddir_list before
  local f want got
  for f in $RUNTIME_FILES; do
    want="$(awk -v f="$f" '$2 == f {print $1}' "$BIN/MANIFEST.txt")"
    got="$(awk -v f="$f" '$3 == f {print $1}' "$OUTDIR/r8-$BLOCK-olddir-before.txt")"
    [[ "$got" == "$want" ]] || die "probe: old dir $f is ${got:-missing}, MANIFEST $want: not the pinned runtime"
  done
  log "probe old dir: the 5 runtime files = MANIFEST"
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

push_file() {  # push_file <local> <device path>: push unless the device copy has the same sha256
  local src=$1 dst=$2 want got
  want="$(sha_local "$src")"
  got="$(sha_dev "$dst")"
  if [[ "$got" == "$want" ]]; then log "push $dst present, sha256 $want"; return 0; fi
  ADB_TIMEOUT=600 adbs push "$src" "$dst" >/dev/null || die "push $dst failed"
  got="$(sha_dev "$dst")"
  [[ "$got" == "$want" ]] || die "push verification failed: $dst device $got local $want"
  log "push $dst sha256 $want"
}

push_round() {
  log "push ($BLOCK)"
  sh_dev "mkdir -p $D8" >/dev/null
  local f want got size src present
  push_file "$BIN8/libonnxruntime.so" "$D8/libonnxruntime.so"
  for f in $COPIED_FILES; do
    want="$(awk -v f="$f" '$2 == f {print $1}' "$BIN/MANIFEST.txt")"
    got="$(sha_dev "$D8/$f")"
    if [[ "$got" == "$want" ]]; then log "push $D8/$f present, sha256 $want"; continue; fi
    sh_dev "cp $D_OLD/$f $D8/$f" >/dev/null
    got="$(sha_dev "$D8/$f")"
    [[ "$got" == "$want" ]] || die "copy verification failed: $D8/$f is $got, MANIFEST $want"
    log "copy $D_OLD/$f -> $D8/$f, sha256 $want (= MANIFEST)"
  done
  push_file "$BIN8/ortgenai_run_dl" "$D8/ortgenai_run_dl"
  push_file "$R8_DIR/run_r8.sh" "$D8/run_r8.sh"
  sh_dev "chmod 755 $D8/model_benchmark $D8/ortgenai_run $D8/ortgenai_run_dl" >/dev/null
  if [[ "$BLOCK" == B ]]; then
    want="$(sha_local "$LOCAL_PROMPT")"
    got="$(sha_dev "$PROMPT")"
    if [[ "$got" == MISSING || -z "$got" ]]; then
      sh_dev "mkdir -p $DEV/prompts" >/dev/null
      adbs push "$LOCAL_PROMPT" "$PROMPT" >/dev/null || die "push prompt failed"
      got="$(sha_dev "$PROMPT")"
      log "push prompt long-context-1024-gen256.txt sha256 $got"
    fi
    [[ "$got" == "$want" ]] || die "$PROMPT is $got, local $want: not ours, not overwritten"
    log "prompt $PROMPT sha256 $want"
  fi
  present="$(sh_dev "[ -e $MODEL_DIR ] && echo yes || echo no" | tr -d '\r')"
  if [[ "$present" == yes ]]; then
    for f in $MODEL_FILES; do
      size="$(stat -Lf %z "$MODEL/$f")"
      got="$(sh_dev "stat -c %s $MODEL_DIR/$f 2>/dev/null" | tr -d '\r')"
      [[ "$got" == "$size" ]] || die "model folder present but not ours: $f device ${got:-missing} bytes, local $size; not overwritten"
    done
    log "push model folder present before this block, every file's bytes match: used as is and left in place"
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

gate8() {  # gate8 <full|light>: 0 = pass, 1 = no pass before the stop margin
  local mode=$1 ok
  while :; do
    state || { log "gate: adb state read failed"; return 1; }
    ok=0
    if [[ "$mode" == light ]]; then
      [[ "$THERMAL" =~ ^[0-9]+$ && "$THERMAL" -lt 3 ]] && ok=1
    elif [[ -z "$CAPPED" && "$THERMAL" == 0 && -n "$BATT" && "$BATT" -le $BATTERY_MAX ]]; then
      ok=1
    fi
    if (( ok )); then log "gate pass ($mode): $STATE_LINE"; return 0; fi
    log "gate wait ($mode): $STATE_LINE"
    (( $(remaining) - GATE_POLL_S > STOP_MARGIN_S )) || return 1
    sleep "$GATE_POLL_S"
  done
}

engine_lines8() {  # the lines of an engine log that carry results, the logits dump or errors
  grep -E '^(ORTGENAI|LOGITS_DUMP|Error|Exception|Batch size|Model Creation|Generator Creation|Prompt processing|Token generation|Token sampling|E2E|Peak working set|Profiling|WARNING)|avg \((us|tokens/s|ms)\)|p50 \(us\)' "$1" || true
}

launch() {  # launch <id> <tag> <rt> <ort> <flash> <limit_s> <bin> <args>
  local id=$1 tag=$2 rt=$3 ort=$4 flash=$5 lim=$6 bin=$7 args=$8 cmd out rc dest
  cmd="$(command_of "$tag" "$rt" "$ort" "$flash" "$lim" "$bin" "$args")"
  log "launch $id $tag: limit=${lim}s: $cmd"
  out="$(ADB_TIMEOUT=$(( lim + 120 )) adbs shell "$cmd" 2>&1)"; rc=$?
  out="$(tr -d '\r' <<<"$out")"
  if [[ $rc -ne 0 && "$out" != *EXIT_CODE=* && "$out" != *KILLED* ]]; then
    log "launch $id: lost (adb rc $rc, output ${out: -300}); no record, not re-run"
    log "adb devices: $(adb devices | tr '\n' ';')"
    return 1
  fi
  log "launch $id: ${out##*$'\n'}"
  mkdir -p "$OUTDIR"
  ADB_TIMEOUT=300 adbs pull "$D8/out/$tag.engine.txt" "$D8/out/$tag.sampler.txt" "$OUTDIR/" >/dev/null ||
    log "pull $id: logs failed (the files stay on the device until clean)"
  dest="$OUTDIR"
  [[ "$args" == *DUMP* ]] && dest="$DUMP_DIR"
  mkdir -p "$dest"
  ADB_TIMEOUT=300 adbs pull "$D8/out/$tag.d" "$dest/" >/dev/null || log "pull $id: $tag.d failed"
  log "pulled $id: $(ls "$OUTDIR" | grep -c "^$tag\.") log files; $tag.d -> $dest: $(ls "$dest/$tag.d" 2>/dev/null | tr '\n' ' ')"
  if [[ -f "$OUTDIR/$tag.engine.txt" ]]; then
    engine_lines8 "$OUTDIR/$tag.engine.txt" | sed "s/^/  $id | /" | tee -a "$LOG" >/dev/null
    { grep -E '^(ORTLIB|ENV) ' "$OUTDIR/$tag.sampler.txt"; grep -E 'git-commit-id|Attempting to dlopen' "$OUTDIR/$tag.sampler.txt"; sampler_lines "$OUTDIR/$tag.sampler.txt"; } |
      sed "s/^/  $id ~ /" | tee -a "$LOG" >/dev/null
  fi
  state && log "after $id: $STATE_LINE"
  [[ "$out" == *KILLED* ]] && log "$id was killed at its limit"
  return 0
}

runs() {  # runs <plan>
  local first=1 id tag rt ort flash gmode limit bin args left lim pause
  while IFS='|' read -r id tag rt ort flash gmode limit bin args; do
    if (( ! first )); then
      pause=$PAUSE_S; [[ "$gmode" == light ]] && pause=$DUMP_PAUSE_S
      log "pause ${pause}s"; sleep "$pause"
    fi
    first=0
    left=$(remaining)
    if (( left < STOP_MARGIN_S )); then log "frame: $(( left / 60 )) min left (< 4): $id and later not started"; return 0; fi
    if ! gate8 "$gmode"; then log "frame: gate did not pass before the 4 min margin: $id and later not started"; return 0; fi
    left=$(remaining)
    if (( left < STOP_MARGIN_S )); then log "frame: $(( left / 60 )) min left (< 4): $id and later not started"; return 0; fi
    lim=$limit
    (( lim > left - END_MARGIN_S )) && lim=$(( left - END_MARGIN_S ))
    launch "$id" "$tag" "$rt" "$ort" "$flash" "$lim" "$bin" "$args" || return 1
  done <<<"$1"
}

clean() {
  local dev_list
  dev_list="$(sh_dev "cd $D8/out 2>/dev/null && for f in r8-$BLOCK*; do [ -e \"\$f\" ] && echo \"\$f\"; done" | tr -d '\r' | sort | tr '\n' ' ')"
  log "clean ($BLOCK): device out/ files: ${dev_list:-none}"
  # an engine of this round still running (a lost launch): stop it before removing its files
  log "clean ($BLOCK): engines of this round before: $(sh_dev "pgrep -fl 'llmbench/ortgenai[-0-9]*/(model_benchmark|ortgenai_run)' || echo none" | tr -d '\r' | tr '\n' ';')"
  sh_dev "pkill -f 'llmbench/ortgenai[-0-9]*/(model_benchmark|ortgenai_run)'" >/dev/null
  if (( MODEL_PUSHED )); then sh_dev "rm -rf $MODEL_DIR" >/dev/null; fi
  sh_dev "rm -rf $D8/out/r8-$BLOCK*; rmdir $D8/out 2>/dev/null" >/dev/null
  log "clean ($BLOCK): model folder $( (( MODEL_PUSHED )) && echo removed || echo 'not pushed by this block, left'), out/ r8-$BLOCK files removed; left: $(sh_dev "ls -d $MODEL_DIR $D8/out 2>/dev/null; ls $D8" | tr -d '\r' | tr '\n' ' ')"
  log "clean ($BLOCK): disk $(sh_dev 'df -k /data | tail -1' | tr -d '\r'); engines: $(sh_dev "ps -A | grep -E 'ortgenai|model_benchmark' | grep -v grep" | tr -d '\r' | tr '\n' ';')"
  olddir_list after
  if cmp -s "$OUTDIR/r8-$BLOCK-olddir-before.txt" "$OUTDIR/r8-$BLOCK-olddir-after.txt"; then
    log "old dir unchanged ($BLOCK): every file's sha256 and size the same before and after"
  else
    log "old dir CHANGED ($BLOCK): $(diff "$OUTDIR/r8-$BLOCK-olddir-before.txt" "$OUTDIR/r8-$BLOCK-olddir-after.txt" | tr '\n' ';')"
  fi
}

phase_block() {  # phase_block <A|B>
  BLOCK=$1
  SCRIPT=ortgenai_r8_$BLOCK
  local plan start_min left
  if [[ "$BLOCK" == A ]]; then plan=$PLAN_A; start_min=$((20 * 60)); else plan=$PLAN_B; start_min=$((15 * 60)); fi
  [[ -n "${RELEASE_FILE:-}" ]] || die "RELEASE_FILE must be set"
  [[ "$BLOCK" == A || -n "${DUMP_DIR:-}" ]] || die "DUMP_DIR must be set for block B"
  own_hold
  trap finish EXIT
  trap 'exit 143' TERM INT
  FRAME_START="$(frame_start_of_hold)" || die "cannot read the hold's started time"
  left=$(remaining)
  log "r8 block $BLOCK: hold since $(date -r "$FRAME_START" '+%H:%M:%S'), frame left $(( left / 60 )) min $(( left % 60 )) s"
  (( left >= start_min )) || die "frame: $(( left / 60 )) min left (< $(( start_min / 60 ))): block $BLOCK not started"
  probe
  take_lock
  CLEAN_NEEDED=1
  push_round
  runs "$plan" || die "block $BLOCK: a launch was lost (see above); the later launches were not started"
  log "block $BLOCK runs done; frame left $(( $(remaining) / 60 )) min"
}

case "${1:-}" in
  dry) phase_dry ;;
  A | B) phase_block "$1" ;;
  *) sed -n '2,44p' "$0"; exit 2 ;;
esac
