#!/bin/bash
# Galaxy S26 driver for the burst arms (asr-burst-v1, docs/asr-burst-v1.md): the instrumented test
# AsrBenchTest of the litert-samples speech_recognition benchmark build — the app's LiteRT pipeline
# (B-L1..B-L5) or sherpa-onnx's release AAR (B-A1) — over LibriSpeech test-clean S16, one utterance at
# a time under the test's burst pacing, MainActivity in front, one process per run. This is the
# asr-litert-app-v1 driver (tools/asr-litert-app/run_app_s26.sh of that round) with: its own package
# (….burst, beside the sustained runs' app), the bench build installed over the debug one and compiled
# with `cmd package compile -m speed`, the burst / foreground / engine arguments, and a deadline.
#
#   run_burst_s26.sh freeze                    # copy the built APKs (debug app, bench app, bench test) + sha256, app commit
#   run_burst_s26.sh setup                     # debug app: models + WAVs into its files dir (run-as); bench build over it; compile -m speed
#   run_burst_s26.sh run <arm> <set> [label]   # cool, probe, am instrument, poll (watchdog, restart, deadline), probe, pull
#   run_burst_s26.sh finish                    # put the stay-awake setting back
#   DRY=1 run_burst_s26.sh ...                 # print the adb commands, run none of them
#
# <arm>: b-a1 sherpa-onnx CPU | b-l1 LiteRT CPU 5 s | b-l2 GPU 5 s | b-l3 NPU 5 s (AOT SM8850) |
#        b-l4 CPU 30 s | b-l5 GPU 30 s | b-l6 parakeet-ctc-0.6b NPU 5 s (AOT SM8850, the app's CTC entry)
# <set>: S32 (the burst set since LANE §0 revision 5) | S16 (the first set) | smoke<N> (the first N rows
#        of S32; SMOKE_EVERY=16 for S16's) | warm<N> (the same rows, a later load) | cfg<N> (the same rows
#        with sherpa_debug=true: sherpa-onnx logs its config at load; not measured)
# [label]: cold | warm for the header; default = cold for the first process of an engine, model and
#          accelerator since setup, warm after that.
#
# Records go to results/raw/2026-10-19-asr-burst-v1-s26-android/ (REC=... to override): <tag>.jsonl
# (header, warm-up row, one row per utterance, footer; a resumed run appends its own header and
# footer), .vmhwm.log, .ceil.log, .load-logcat.txt, .done, .cmd, .events.tsv, .logcat.log,
# .cpufreq-host.tsv, .probe-before.json / .probe-after.json (+ .resumeK). A retake of a tag keeps the
# earlier files as <file>.attemptK.
#
# Knobs: DEADLINE=<epoch s> (force-stop the run when it passes, so the hold is given back in time;
# RESUME=1 later continues the same tag from its first row without a result; START_AFTER=<id> starts a
# new tag after that id of its selection, e.g. S32 after the S32 rows a stopped S16 run wrote), REQUIRE_TOP_APP=0
# (measure even when the app process is not the resumed top app; it is recorded), FOREGROUND=0 (no
# activity in front), COOL_CEILING=0, STALL_S / POLL_S / COOL_MAX_S.
#
# The phone is touched only under the S26 hold held by a keeper named asr_burst_s26 (HOLD_OK=1 skips
# the check). No adb shell call leaves a background child on the phone: the test starts through
# `am instrument` without -w and the driver polls with short calls.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
DRY="${DRY:-0}"
SERIAL="${SERIAL:-RFGL80R6A6H}"
PKG=com.google.ai.edge.examples.asr.burst
RUNNER="$PKG.test/androidx.test.runner.AndroidJUnitRunner"
APPDIR="${APPDIR:-$HOME/code/litert-samples-asr-burst-wt/samples/litert/speech_recognition/AndroidApp}"
B="${B:-$ROOT/.build/asr-burst}"
REC="${REC:-$ROOT/results/raw/2026-10-19-asr-burst-v1-s26-android}"
[ "$DRY" = 1 ] && REC="$B/dry-rec"  # a dry run writes its logs beside the build, never into the record
HOLD="$HOME/code/litertlm-convert/community_accel_work/s2_npu_sweep/.device_hold"
DT=/data/local/tmp/edge-llm-bench/asr-burst
EXT="/sdcard/Android/data/$PKG/files"
# The WAVs live in the app's internal files dir (unpacked with run-as while the debug build is
# installed): asr-litert-app-v1 found that the app cannot read what adb writes into its external dir.
WAV_DIR="/data/user/0/$PKG/files/sets/test-clean"
WARMUP_ID=1995-1836-0004
STALL_S="${STALL_S:-600}"
POLL_S="${POLL_S:-10}"
COOL_MAX_S="${COOL_MAX_S:-900}"
COOL_BATTERY_C="${COOL_BATTERY_C:-36.0}"
MAX_FAILS=3
mkdir -p "$B" "$REC"

log() { echo "[asr-burst $(date +%H:%M:%S)] $*" >&2; }

A() {  # adb on the S26 (DRY: print only)
  if [ "$DRY" = 1 ]; then echo "DRY adb -s $SERIAL $*" >&2; return 0; fi
  adb -s "$SERIAL" "$@" </dev/null
}

hold_ok() {
  [ "$DRY" = 1 ] && return 0
  [ "${HOLD_OK:-0}" = 1 ] && return 0
  python3 - "$HOLD" <<'PY'
import json, os, sys
try:
    d = json.load(open(sys.argv[1]))
    os.kill(int(d["pid"]), 0)
except Exception as e:
    print(f"hold check: {e}", file=sys.stderr); sys.exit(1)
sys.exit(0 if d.get("script") == "asr_burst_s26" else 1)
PY
}

need_hold() {
  hold_ok || { log "the S26 hold is not ours (asr_burst_s26 with a live keeper): $(cat "$HOLD" 2>/dev/null)"; exit 4; }
}

state_get() {  # key -> "1" when a process loaded it since the last setup
  python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(1 if sys.argv[2] in d.get("loaded",[]) else 0)' \
    "$B/device_state.json" "$1" 2>/dev/null || echo 0
}

state_add() {
  python3 - "$B/device_state.json" "$1" <<'PY'
import json, os, sys
p, k = sys.argv[1], sys.argv[2]
d = json.load(open(p)) if os.path.exists(p) else {}
d.setdefault("loaded", [])
if k not in d["loaded"]:
    d["loaded"].append(k)
json.dump(d, open(p, "w"), indent=1)
PY
}

dexopt_of() {  # package -> "<compiler filter>/<reason>" of its APK, from dumpsys package
  A shell "dumpsys package $1" | python3 -c '
import re, sys
m = re.search(r"\[status=([^\]]+)\]\s*\[reason=([^\]]+)\]", sys.stdin.read())
print((m.group(1) + "/" + m.group(2)) if m else "unknown")'
}

screen_state() {  # one line: wakefulness and the keyguard lines (MainActivity in front needs an unlocked screen)
  A shell "dumpsys power | grep -m1 mWakefulness=; dumpsys window | grep -m3 -E 'mKeyguardShowing|mAodShowing|mKeyguardGoingAway'" | tr -s ' \r\n' ' '
}

cmd_freeze() {
  local out="$B/apk" commit dirty
  mkdir -p "$out"
  cp "$APPDIR/app/build/outputs/apk/debug/app-debug.apk" "$out/app-debug.apk"
  cp "$APPDIR/app/build/outputs/apk/bench/app-bench.apk" "$out/app-bench.apk"
  cp "$APPDIR/app/build/outputs/apk/androidTest/bench/app-bench-androidTest.apk" "$out/app-bench-androidTest.apk"
  commit=$(git -C "$APPDIR" rev-parse HEAD)
  dirty=$(git -C "$APPDIR" status --porcelain -- . | grep -v '^??' | wc -l | tr -d ' ')
  (cd "$out" && shasum -a 256 app-debug.apk app-bench.apk app-bench-androidTest.apk > SHA256SUMS)
  echo "$commit dirty_tracked_files=$dirty" > "$out/APP_COMMIT"
  cat "$out/SHA256SUMS" "$out/APP_COMMIT"
}

# Local file under .build/asr-burst/models -> path under the app's files dir (model_metadata.json keys,
# ModelMetadataManager paths; AsrBenchTest's sherpa model dir).
SH=sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8
MODEL_MAP="parakeet_tdt_0.6b_v3_5s_i8_stateful.tflite parakeet-tdt-0.6b-v3/model.tflite
parakeet_tdt_0.6b_v3_5s_f32_stateful_Qualcomm_SM8850.tflite parakeet-tdt-0.6b-v3/model_npu.tflite
tokenizer.json parakeet-tdt-0.6b-v3/tokenizer.json
parakeet_tdt_0.6b_v3_30s_i8_stateful.tflite parakeet-tdt-0.6b-v3-30s/model.tflite
tokenizer.json parakeet-tdt-0.6b-v3-30s/tokenizer.json
$SH/encoder.int8.onnx $SH/encoder.int8.onnx
$SH/decoder.int8.onnx $SH/decoder.int8.onnx
$SH/joiner.int8.onnx $SH/joiner.int8.onnx
$SH/tokens.txt $SH/tokens.txt
parakeet_ctc_0.6b_5s_f32_Qualcomm_SM8850.tflite parakeet-ctc-0.6b/model_npu.tflite
tokenizer-ctc.json parakeet-ctc-0.6b/tokenizer.json"

cmd_setup() {
  need_hold
  local apk="$B/apk" models="$B/models" set="$B/set" f dst want got n
  [ -f "$apk/app-bench.apk" ] || { log "no frozen APK: run freeze first"; exit 2; }
  : > "$REC/setup.log"
  {
    echo "# setup $(date '+%F %T %Z')"
    cat "$apk/SHA256SUMS" "$apk/APP_COMMIT"
    echo "stay_on_while_plugged_in before: $(A shell settings get global stay_on_while_plugged_in | tr -d '\r')"
  } >> "$REC/setup.log"
  # 1. The debug build (same package and key): run-as can write its files dir.
  A install -r -t "$apk/app-debug.apk" >&2 || { log "install debug app failed"; exit 2; }
  echo "installed app-debug.apk (debuggable, for run-as)" >> "$REC/setup.log"
  A shell svc power stayon usb
  A shell input keyevent KEYCODE_WAKEUP
  A shell mkdir -p "$DT/models/$SH" "$DT/sets"
  # 2. Models: pushed to /data/local/tmp, copied into the app's own files dir with run-as, where
  # LiteRtRunner and the sherpa engine read them. sha256 read back on the phone and compared with the
  # record each file came with (models.lock.json, stage_models.sh).
  echo "$MODEL_MAP" | while read -r f dst; do
    want=$(python3 -c 'import json,sys; print({r["local"]: r["expected_sha256"] for r in json.load(open(sys.argv[1]))}[sys.argv[2]])' "$models/models.lock.json" "$f")
    got=$(A shell sha256sum "$DT/models/$f" 2>/dev/null | cut -c1-64)
    if [ "$got" != "$want" ]; then
      A push "$models/$f" "$DT/models/$f" >&2 || { log "push $f failed"; exit 2; }
      got=$(A shell sha256sum "$DT/models/$f" | cut -c1-64)
    fi
    A shell "run-as $PKG sh -c 'mkdir -p files/${dst%/*} && cat > files/$dst' < $DT/models/$f"
    got=$(A shell run-as "$PKG" sha256sum "files/$dst" | cut -c1-64)
    echo "model $f -> files/$dst route=run-as sha256_local=$want sha256_phone=$got $([ "$got" = "$want" ] && echo OK || echo MISMATCH)" | tee -a "$REC/setup.log" >&2
    [ "$DRY" = 1 ] || [ "$got" = "$want" ] || exit 3
  done || exit $?
  # The app's copies are checked: the staging copies go (about 4.4 GB of the phone's /data).
  A shell rm -rf "$DT/models"
  echo "staging copies removed ($DT/models); /data: $(A shell df -h /data | tail -1 | tr -s ' ')" | tee -a "$REC/setup.log" >&2
  # 3. WAVs: one tar (manifest-device.tsv with every row + the 164 S16 WAVs + W), unpacked in the
  # app's internal files dir.
  want=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["tar_sha256"])' "$set/test-clean-S16W.tar.json")
  got=$(A shell sha256sum "$DT/sets/test-clean-S16W.tar" 2>/dev/null | cut -c1-64)
  [ "$got" = "$want" ] || A push "$set/test-clean-S16W.tar" "$DT/sets/test-clean-S16W.tar" >&2
  got=$(A shell sha256sum "$DT/sets/test-clean-S16W.tar" | cut -c1-64)
  A shell "run-as $PKG sh -c 'mkdir -p files/sets/test-clean && cd files/sets/test-clean && tar -xf -' < $DT/sets/test-clean-S16W.tar"
  n=$(A shell "run-as $PKG ls files/sets/test-clean | grep -c '\.wav\$'" | tr -d '\r')
  echo "wav set tar sha256_local=$want sha256_phone=$got wavs_unpacked=$n ($WAV_DIR)" | tee -a "$REC/setup.log" >&2
  if [ "$DRY" != 1 ] && { [ "$got" != "$want" ] || [ "$n" != 165 ]; }; then log "WAV set check failed"; exit 3; fi
  # 4. The measured build over it (the data stays), the test APK, then AOT for both.
  A install -r "$apk/app-bench.apk" >&2 || { log "install bench app failed"; exit 2; }
  A install -r -t "$apk/app-bench-androidTest.apk" >&2 || { log "install bench test failed"; exit 2; }
  {
    echo "installed app-bench.apk + app-bench-androidTest.apk over it (install -r: data kept)"
    echo "pkgFlags: $(A shell "dumpsys package $PKG | grep -m2 -E 'pkgFlags=|privateFlags='" | tr -s ' \r\n' ' ')"
    echo "compile app: $(A shell cmd package compile -m speed -f "$PKG" | tr -d '\r')"
    echo "compile test: $(A shell cmd package compile -m speed -f "$PKG.test" | tr -d '\r')"
    echo "dexopt app: $(dexopt_of "$PKG")"
    echo "dexopt test: $(dexopt_of "$PKG.test")"
    echo "screen: $(screen_state)"
  } | tee -a "$REC/setup.log" >&2
  echo '{"loaded": []}' > "$B/device_state.json"
  log "setup done"
}

cmd_finish() {
  local before
  before=$(sed -n 's/^stay_on_while_plugged_in before: //p' "$REC/setup.log" | head -1)
  [ -n "$before" ] && A shell settings put global stay_on_while_plugged_in "$before"
  log "stay_on_while_plugged_in restored to ${before:-?}"
}

cool() {  # battery <= COOL_BATTERY_C, thermal status 0, every CPU ceiling at its maximum; at most COOL_MAX_S
  local t0 p why waited max=$COOL_MAX_S
  t0=$(date +%s)
  # A sitting's deadline shortens the wait: the run must still have MIN_RUN_S before it.
  if [ -n "${DEADLINE:-}" ] && [ $(( DEADLINE - t0 - ${MIN_RUN_S:-300} )) -lt "$max" ]; then max=$(( DEADLINE - t0 - ${MIN_RUN_S:-300} )); fi
  [ "$max" -le 0 ] && { echo "cool: not started, the deadline is less than ${MIN_RUN_S:-300}s away"; return 5; }
  while :; do
    p=$("$HERE/probe.sh" cool)
    why=$(python3 - "$p" "$COOL_BATTERY_C" "${COOL_CEILING:-1}" <<'PY'
import json, sys
try:
    p = json.loads(sys.argv[1])
except ValueError:
    print("probe unreadable"); sys.exit(0)
lim = float(sys.argv[2])
w = []
if p.get("battery_celsius", 99) > lim:
    w.append("battery %s C" % p.get("battery_celsius"))
if p.get("thermal_status", 9) != 0:
    w.append("thermal %s" % p.get("thermal_status"))
if sys.argv[3] == "1":
    for k, v in sorted(p.get("cpufreq", {}).items()):
        if v.get("ceiling_drop_pct", 0) > 0:
            w.append("%s ceiling -%s%%" % (k, v["ceiling_drop_pct"]))
print("; ".join(w) or "ok")
PY
)
    waited=$(( $(date +%s) - t0 ))
    [ "$why" = ok ] && { echo "cool: ok after ${waited}s"; return 0; }
    if [ $waited -ge "$max" ]; then
      [ "$max" -lt "$COOL_MAX_S" ] && { echo "cool: not started after ${waited}s ($why), the deadline is near"; return 5; }
      echo "cool: started anyway after ${waited}s ($why)"; return 0
    fi
    sleep 20
  done
}

arm_spec() {  # arm -> "engine model accelerator window"
  case "$1" in
    b-a1) echo "sherpa $SH cpu -" ;;
    b-l1) echo "litert parakeet-tdt-0.6b-v3 cpu 5s" ;;
    b-l2) echo "litert parakeet-tdt-0.6b-v3 gpu 5s" ;;
    b-l3) echo "litert parakeet-tdt-0.6b-v3 npu 5s" ;;
    b-l4) echo "litert parakeet-tdt-0.6b-v3-30s cpu 30s" ;;
    b-l5) echo "litert parakeet-tdt-0.6b-v3-30s gpu 30s" ;;
    b-l6) echo "litert parakeet-ctc-0.6b npu ctc-5s" ;;
    *) return 1 ;;
  esac
}

ids_left() {  # jsonl every limit -> "<first id of the selection without a row> <the id before it>" ("" = none)
  python3 - "$1" "$B/set/manifest-device.tsv" "$2" "$3" <<'PY'
import json, sys
jsonl, manifest, every, limit = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
ids = [l.split("\t")[0] for l in open(manifest) if l.strip()][::every]
if limit > 0:
    ids = ids[:limit]
seen = set()
try:
    for l in open(jsonl):
        r = json.loads(l)
        if "id" in r:
            seen.add(r["id"])
except FileNotFoundError:
    pass
nxt = next((n for n, i in enumerate(ids) if i not in seen), None)
print("" if nxt is None else ids[nxt], "" if not nxt else ids[nxt - 1])
PY
}

grab_logcat() {  # tag pid -> append the app process's runtime / delegate / test lines (no ASR merger lines)
  local tag=$1 pid=$2 raw="$B/logcat-raw-$1.txt"
  A logcat -d -v threadtime > "$raw" 2>/dev/null
  python3 - "$raw" "$REC/$tag.logcat.log" "$pid" <<'PY'
import os, re, sys
raw, out, pid = sys.argv[1], sys.argv[2], sys.argv[3]
keep = re.compile(r"litert|LiteRt|tflite|TfLite|xnnpack|XNNPACK|delegate|Delegate|Dispatch|Accelerator|accelerator|"
                  r"OpenCL|opencl|GPU|gpu|NPU|npu|Qnn|QNN|qnn|Htp|HTP|sherpa|onnxruntime|AsrBench|TestRunner|"
                  r"AndroidRuntime|FATAL|Fatal signal|libc|DEBUG|tombstone|ActivityManager.*" + re.escape("com.google.ai.edge.examples.asr"))
have = set(open(out).read().splitlines()) if os.path.exists(out) else set()
new = []
for line in open(raw, errors="replace"):
    line = line.rstrip("\n")
    f = line.split()
    same = len(f) > 2 and f[2] == pid
    if " D ASR " in line or " D ASR:" in line:
        continue
    if (same and keep.search(line)) or re.search(r"AndroidRuntime|Fatal signal|DEBUG  |tombstone|crash_dump", line) \
            or ("com.google.ai.edge.examples.asr" in line and "ActivityManager" in line):
        if line not in have:
            new.append(line)
            have.add(line)
with open(out, "a") as f:
    for line in new:
        f.write(line + "\n")
print(len(new))
PY
}

cmd_run() {
  local arm=$1 setname=$2 label=${3:-} spec engine model accel win every limit tag key fg dbg="" fails=0 lost=0
  # In front: the bench build's window over the keyguard; the run stops before the load unless the
  # app process is the resumed top app (REQUIRE_TOP_APP=0 only records where it ran).
  fg="-e foreground front -e require_top_app $([ "${REQUIRE_TOP_APP:-1}" = 1 ] && echo true || echo false)"
  spec=$(arm_spec "$arm") || { log "unknown arm $arm"; exit 2; }
  read -r engine model accel win <<<"$spec"
  every=${SMOKE_EVERY:-32}
  case "$setname" in
    S32) every=32; limit=0 ;;
    S16) every=16; limit=0 ;;
    smoke*) limit=${setname#smoke} ;;
    warm*) limit=${setname#warm}; label=${label:-warm} ;;
    cfg*) limit=${setname#cfg}; dbg="-e sherpa_debug true" ;;
    *) log "unknown set $setname"; exit 2 ;;
  esac
  key="$engine/$model/$accel"
  [ -n "$label" ] || { [ "$(state_get "$key")" = 1 ] && label=warm || label=cold; }
  if [ "$engine" = sherpa ]; then tag="$arm-sherpa-cpu-$setname"; else tag="$arm-litert-$accel-$win-$setname"; fi
  [ "${FOREGROUND:-1}" = 0 ] && fg=""
  need_hold
  local seg="" start_after="" failed="" kind=""
  if [ "${RESUME:-0}" = 1 ]; then
    # Continue a run stopped at a deadline: the next process starts after the last row it wrote.
    local k=1
    while [ -f "$REC/$tag.probe-before.resume$k.json" ]; do k=$((k + 1)); done
    seg=".resume$k"
    A pull "$EXT/bench/$tag.jsonl" "$B/$tag.partial.jsonl" >/dev/null 2>&1
    read -r failed start_after <<<"$(ids_left "$B/$tag.partial.jsonl" "$every" "$limit")"
    [ -n "$failed" ] || { log "$tag: nothing left to resume"; return 0; }
    failed=""
    log "resume $tag after ${start_after:-the start} (segment $seg)"
  elif [ "$DRY" != 1 ] && ls "$REC/$tag".* 2>/dev/null | grep -q -v '\.attempt[0-9]*$'; then
    # A retake keeps the earlier capture beside it as <file>.attemptK (audit trail, out of every glob).
    local k=1 f
    while ls "$REC/$tag".*.attempt$k >/dev/null 2>&1; do k=$((k + 1)); done
    for f in "$REC/$tag".*; do case "$f" in *.attempt[0-9]*) ;; *) mv "$f" "$f.attempt$k" ;; esac; done
    log "earlier capture of $tag kept as *.attempt$k"
  fi
  if [ -n "${START_AFTER:-}" ] && [ -z "$seg" ]; then
    start_after=$START_AFTER  # a new tag that continues another run's rows (the first process only)
    log "$tag starts after $START_AFTER"
  fi
  local commit; commit=$(cut -d' ' -f1 "$B/apk/APP_COMMIT" 2>/dev/null)
  log "run $tag$seg (engine=$engine model=$model accelerator=$accel every=$every limit=$limit label=$label)"
  echo "# $tag$seg $(date '+%F %T %Z') label=$label" >> "$REC/$tag.cmd"
  if [ "$DRY" = 1 ]; then
    echo "DRY cool (battery <= $COOL_BATTERY_C C, thermal 0, full ceilings, <= ${COOL_MAX_S}s)" >&2
  else
    cool | tee -a "$REC/$tag.cmd" >&2
    if [ "${PIPESTATUS[0]}" = 5 ]; then
      log "$tag: not started (deadline)"
      [ -f "$REC/$tag.events.tsv" ] && printf '%s\tnot-started\tdeadline during cool\n' "$(date +%T)" >> "$REC/$tag.events.tsv"
      return 5
    fi
  fi
  "$HERE/probe.sh" before > "$REC/$tag.probe-before$seg.json"
  local dx_app dx_test
  dx_app=$(dexopt_of "$PKG"); dx_test=$(dexopt_of "$PKG.test")
  echo "dexopt: app $dx_app, test $dx_test; screen: $(screen_state)" >> "$REC/$tag.cmd"
  [ -n "$seg" ] || A shell "rm -f $EXT/bench/$tag.*"
  A logcat -c
  local attempt=0 n last_n t_change now st pid done_flag ceil header_pid="" grabbed=0 stopped=""
  [ -n "$seg" ] || printf 'time\tevent\tdetail\n' > "$REC/$tag.events.tsv"
  [ -n "$seg" ] || printf 'time\tceilings_khz\n' > "$REC/$tag.cpufreq-host.tsv"
  while :; do
    attempt=$((attempt + 1))
    local extra=""
    [ -n "$start_after" ] && extra="-e start_after $start_after"
    [ -n "$failed" ] && extra="$extra -e failed_id $failed -e failed_kind $kind"
    local am="am instrument -r -e engine $engine -e model $model -e accelerator $accel -e manifest $WAV_DIR/manifest-device.tsv -e every $every -e limit $limit -e tag $tag -e load_label $label -e app_commit ${commit:-unknown} -e dexopt_app $dx_app -e dexopt_test $dx_test -e pace burst -e warmup_id $WARMUP_ID $fg $dbg $extra $RUNNER"
    echo "$(date '+%T') attempt $attempt$seg: adb -s $SERIAL shell $am" >> "$REC/$tag.cmd"
    printf '%s\tlaunch\tattempt %s%s %s\n' "$(date +%T)" "$attempt" "$seg" "$extra" >> "$REC/$tag.events.tsv"
    A shell "$am"
    [ "$DRY" = 1 ] && break
    last_n=-1; t_change=$(date +%s); grabbed=0
    while :; do
      sleep "$POLL_S"
      st=$(A shell "echo n=\$(cat $EXT/bench/$tag.jsonl 2>/dev/null | wc -l); [ -f $EXT/bench/$tag.done ] && echo done=1; echo pid=\$(pidof $PKG); echo ceil=\$(cat /sys/devices/system/cpu/cpufreq/policy*/scaling_max_freq | tr '\n' ',')" | tr -d '\r')
      if ! echo "$st" | grep -q '^n='; then
        # adb lost the phone for this poll: neither a crash nor progress. 20 misses = stop.
        lost=$((lost + 1))
        printf '%s\tadb-miss\t%s\n' "$(date +%T)" "$lost" >> "$REC/$tag.events.tsv"
        [ $lost -ge 20 ] && { printf '%s\tstop\tphone unreachable over adb\n' "$(date +%T)" >> "$REC/$tag.events.tsv"; break 2; }
        continue
      fi
      lost=0
      n=$(echo "$st" | sed -n 's/^n=//p'); n=${n:-0}
      done_flag=$(echo "$st" | sed -n 's/^done=//p')
      pid=$(echo "$st" | sed -n 's/^pid=//p')
      ceil=$(echo "$st" | sed -n 's/^ceil=//p')
      now=$(date +%s)
      printf '%s\t%s\n' "$(date +%T)" "$ceil" >> "$REC/$tag.cpufreq-host.tsv"
      if [ "$n" != "$last_n" ]; then last_n=$n; t_change=$now; fi
      if [ $grabbed = 0 ] && [ -n "$pid" ] && [ "$n" -gt 0 ]; then
        header_pid=$pid
        printf '%s\theader\tpid %s, %s logcat lines\n' "$(date +%T)" "$pid" "$(grab_logcat "$tag" "$pid")" >> "$REC/$tag.events.tsv"
        grabbed=1
      fi
      if [ "$done_flag" = 1 ]; then
        printf '%s\tdone\t%s lines\n' "$(date +%T)" "$n" >> "$REC/$tag.events.tsv"
        break 2
      fi
      if [ -n "${DEADLINE:-}" ] && [ "$now" -ge "$DEADLINE" ]; then
        A shell am force-stop "$PKG"; sleep 3
        grab_logcat "$tag" "${header_pid:-$pid}" >/dev/null
        printf '%s\tdeadline\tstopped at %s lines (resume with RESUME=1)\n' "$(date +%T)" "$n" >> "$REC/$tag.events.tsv"
        log "$tag: deadline reached, stopped at $n lines"
        stopped=deadline
        break 2
      fi
      if [ -z "$pid" ] || [ $((now - t_change)) -ge "$STALL_S" ]; then
        if [ -n "$pid" ]; then kind=hang; A shell am force-stop "$PKG"; sleep 3; else kind=crash; fi
        A pull "$EXT/bench/$tag.jsonl" "$B/$tag.partial.jsonl" >/dev/null 2>&1
        grab_logcat "$tag" "${header_pid:-$pid}" >/dev/null
        A logcat -b crash -d >> "$REC/$tag.crash.log" 2>/dev/null
        read -r failed start_after <<<"$(ids_left "$B/$tag.partial.jsonl" "$every" "$limit")"
        fails=$((fails + 1))
        printf '%s\t%s\tutterance %s (fail %s of %s), %s lines so far, %ss without a new line\n' \
          "$(date +%T)" "$kind" "${failed:-none}" "$fails" "$MAX_FAILS" "$n" "$((now - t_change))" >> "$REC/$tag.events.tsv"
        log "$kind on ${failed:-?} ($fails/$MAX_FAILS)"
        if ! grep -q -E '"type": ?"header"' "$B/$tag.partial.jsonl" 2>/dev/null || [ -z "$failed" ] || [ $fails -ge $MAX_FAILS ]; then
          printf '%s\tstop\t%s\n' "$(date +%T)" "no header (load failed) / nothing left / $MAX_FAILS failures" >> "$REC/$tag.events.tsv"
          break 2
        fi
        start_after=$failed
        break
      fi
    done
  done
  "$HERE/probe.sh" after > "$REC/$tag.probe-after$seg.json"
  if [ "$DRY" != 1 ]; then
    grab_logcat "$tag" "${header_pid:-x}" >/dev/null
    for f in jsonl vmhwm.log ceil.log load-logcat.txt done; do A pull "$EXT/bench/$tag.$f" "$REC/$tag.$f" >/dev/null 2>&1; done
    state_add "$key"
    log "$tag: $(cat "$REC/$tag.done" 2>/dev/null || echo "no done marker${stopped:+ ($stopped)}") ($(grep -c -E '"type": ?"utterance"' "$REC/$tag.jsonl" 2>/dev/null) rows)"
  fi
}

case "${1:-}" in
  freeze) cmd_freeze ;;
  setup) cmd_setup ;;
  run) shift; [ $# -ge 2 ] || { sed -n 2,34p "$0"; exit 2; }; cmd_run "$@" ;;
  check) shift; python3 "$HERE/check_run.py" "$REC/$1.jsonl" ${2:+--ref "$2"} ;;  # one line on a run (tag [reference jsonl])
  finish) cmd_finish ;;
  *) sed -n 2,34p "$0"; exit 2 ;;
esac
