#!/bin/bash
# Galaxy S26 driver for the LiteRT ASR app arms (asr-litert-app-v1, docs/asr-litert-app-v1.md): the
# litert-samples speech_recognition app's own file pipeline, run by its instrumented test
# AsrBenchTest over LibriSpeech test-clean WAVs, one process per run.
#
#   run_app_s26.sh freeze                    # copy the built APKs to .build/asr-litert-app/apk (+ sha256, app commit)
#   run_app_s26.sh setup                     # install both APKs; models into the app's files dir (run-as), WAV set
#   run_app_s26.sh run <arm> <set> [label]   # cool, probe, am instrument, poll (watchdog, restart), probe, pull
#   run_app_s26.sh finish                    # put the stay-awake setting back
#   DRY=1 run_app_s26.sh ...                 # print the adb commands, run none of them
#
# <arm>: l1 CPU 5 s | l2 GPU 5 s | l3 NPU 5 s (AOT SM8850) | l4 CPU 30 s | l5 GPU 30 s
# <set>: S4 | full | smoke<N> (first N rows of S4) | warm<N> (same rows, a second load) |
#        spread10 (S4 rows 0, 65, ..., 585: ten lengths from 35 s to 2.7 s)
# [label]: cold | warm for the header; default = cold for the first process of a model and
#          accelerator since setup copied the models, warm after that. FOREGROUND=1 runs the test
#          with MainActivity in the foreground (tag suffix -fg).
#
# Records go to results/raw/2026-10-19-asr-litert-app-v1-s26-android/ (REC=... to override):
# <tag>.jsonl (header, one row per utterance, footer), .vmhwm.log, .load-logcat.txt (the test's own
# log right after the model was built), .done, .cmd, .events.tsv, .logcat.log (LiteRT / delegate /
# test lines of the app process), .cpufreq-host.tsv (each poll's ceilings), .probe-before.json /
# .probe-after.json. A retake of a tag keeps the earlier files as <file>.attemptK.
#
# Knobs: WAV_ROUTE=internal (WAVs in the app's internal files dir, when it cannot read the external
# one), AM_WAIT=1 (`am instrument -w` through a Mac-side background adb client), COOL_CEILING=0
# (cool start without waiting for full CPU ceilings), STALL_S / POLL_S / COOL_MAX_S,
# RESUME_AFTER=<id> [PART=p2] (a second part of a run, tag <tag>-p2, starting after <id>).
# Planned stop (a hold's end): `touch .build/asr-litert-app/stop-<tag>`; the driver stops the app at
# its next poll, records `planned-stop`, pulls and exits (never kill the driver: it would read the
# stopped app as a crash and relaunch it).
#
# The phone is touched only under the S26 hold held by a keeper named asr_litert_s26 (HOLD_OK=1
# skips the check). No adb shell call leaves a background child on the phone: the test starts
# through `am instrument` without -w and the driver polls with short calls.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
DRY="${DRY:-0}"
SERIAL="${SERIAL:-RFGL80R6A6H}"
PKG=com.google.ai.edge.examples.asr
RUNNER="$PKG.test/androidx.test.runner.AndroidJUnitRunner"
APPDIR="${APPDIR:-$HOME/code/litert-samples-asr-bench-wt/samples/litert/speech_recognition/AndroidApp}"
B="$ROOT/.build/asr-litert-app"
REC="${REC:-$ROOT/results/raw/2026-10-19-asr-litert-app-v1-s26-android}"
HOLD="$HOME/code/litertlm-convert/community_accel_work/s2_npu_sweep/.device_hold"
DT=/data/local/tmp/edge-llm-bench/asr-litert-app
EXT="/sdcard/Android/data/$PKG/files"
# Where the WAV set lives on the phone: the app's external files dir (default) or, when the app
# cannot read what adb wrote there, its internal files dir (WAV_ROUTE=internal, unpacked with run-as).
WAV_ROUTE="${WAV_ROUTE:-external}"
if [ "$WAV_ROUTE" = internal ]; then WAV_DIR="/data/user/0/$PKG/files/sets/test-clean"; else WAV_DIR="$EXT/sets/test-clean"; fi
STALL_S="${STALL_S:-600}"
POLL_S="${POLL_S:-15}"
COOL_MAX_S="${COOL_MAX_S:-900}"
COOL_BATTERY_C="${COOL_BATTERY_C:-36.0}"
MAX_FAILS=3
mkdir -p "$B" "$REC"

log() { echo "[asr-app $(date +%H:%M:%S)] $*" >&2; }

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
sys.exit(0 if d.get("script") == "asr_litert_s26" else 1)
PY
}

need_hold() {
  hold_ok || { log "the S26 hold is not ours (asr_litert_s26 with a live keeper): $(cat "$HOLD" 2>/dev/null)"; exit 4; }
}

state_get() {  # key -> "1" when a process loaded it since the last model copy
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

cmd_freeze() {
  local out="$B/apk" commit dirty
  mkdir -p "$out"
  cp "$APPDIR/app/build/outputs/apk/debug/app-debug.apk" "$out/app-debug.apk"
  cp "$APPDIR/app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk" "$out/app-debug-androidTest.apk"
  commit=$(git -C "$APPDIR" rev-parse HEAD)
  dirty=$(git -C "$APPDIR" status --porcelain -- . | grep -v '^??' | wc -l | tr -d ' ')
  (cd "$out" && shasum -a 256 app-debug.apk app-debug-androidTest.apk > SHA256SUMS)
  echo "$commit dirty_tracked_files=$dirty" > "$out/APP_COMMIT"
  cat "$out/SHA256SUMS" "$out/APP_COMMIT"
}

# Local model file -> path under the app's files dir (model_metadata.json keys, ModelMetadataManager paths).
MODEL_MAP="parakeet_tdt_0.6b_v3_5s_i8_stateful.tflite parakeet-tdt-0.6b-v3/model.tflite
parakeet_tdt_0.6b_v3_5s_f32_stateful_Qualcomm_SM8850.tflite parakeet-tdt-0.6b-v3/model_npu.tflite
tokenizer.json parakeet-tdt-0.6b-v3/tokenizer.json
parakeet_tdt_0.6b_v3_30s_i8_stateful.tflite parakeet-tdt-0.6b-v3-30s/model.tflite
tokenizer.json parakeet-tdt-0.6b-v3-30s/tokenizer.json"

cmd_setup() {
  need_hold
  local apk="$B/apk" models="$B/models" set="$B/device-set" f dst want got
  [ -f "$apk/app-debug.apk" ] || { log "no frozen APK: run freeze first"; exit 2; }
  : > "$REC/setup.log"
  {
    echo "# setup $(date '+%F %T %Z')"
    cat "$apk/SHA256SUMS" "$apk/APP_COMMIT"
    echo "stay_on_while_plugged_in before: $(A shell settings get global stay_on_while_plugged_in | tr -d '\r')"
  } >> "$REC/setup.log"
  A install -r -t "$apk/app-debug.apk" >&2 || { log "install app failed"; exit 2; }
  A install -r -t "$apk/app-debug-androidTest.apk" >&2 || { log "install test failed"; exit 2; }
  A shell svc power stayon usb
  A shell input keyevent KEYCODE_WAKEUP
  A shell mkdir -p "$DT/models" "$DT/sets"
  # Models: pushed to /data/local/tmp, then copied into the app's own files dir with run-as (debug
  # APK), where LiteRtRunner finds them and skips its download. sha256 read back on the phone.
  echo "$MODEL_MAP" | while read -r f dst; do
    want=$(shasum -a 256 "$models/$f" | cut -c1-64)
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
  # WAV set: one tar (2620 WAVs + manifest-device.tsv), unpacked in the app's external files dir.
  want=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["tar_sha256"])' "$set/test-clean.tar.json")
  got=$(A shell sha256sum "$DT/sets/test-clean.tar" 2>/dev/null | cut -c1-64)
  [ "$got" = "$want" ] || A push "$set/test-clean.tar" "$DT/sets/test-clean.tar" >&2
  got=$(A shell sha256sum "$DT/sets/test-clean.tar" | cut -c1-64)
  if [ "$WAV_ROUTE" = internal ]; then
    A shell "run-as $PKG sh -c 'mkdir -p files/sets/test-clean && cd files/sets/test-clean && tar -xf -' < $DT/sets/test-clean.tar"
    n=$(A shell "run-as $PKG ls files/sets/test-clean | grep -c '\.wav\$'" | tr -d '\r')
  else
    A shell "mkdir -p $EXT/sets/test-clean $EXT/bench && cd $EXT/sets/test-clean && tar -xf $DT/sets/test-clean.tar"
    n=$(A shell "ls $EXT/sets/test-clean | grep -c '\.wav\$'" | tr -d '\r')
  fi
  echo "wav set tar sha256_local=$want sha256_phone=$got wavs_unpacked=$n route=$WAV_ROUTE ($WAV_DIR)" | tee -a "$REC/setup.log" >&2
  if [ "$DRY" != 1 ] && { [ "$got" != "$want" ] || [ "$n" != 2620 ]; }; then log "WAV set check failed"; exit 3; fi
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
  local t0 p why waited
  t0=$(date +%s)
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
    [ $waited -ge "$COOL_MAX_S" ] && { echo "cool: started anyway after ${waited}s ($why)"; return 0; }
    sleep 20
  done
}

arm_spec() {  # arm -> "model accelerator window"
  case "$1" in
    l1) echo "parakeet-tdt-0.6b-v3 cpu 5s" ;;
    l2) echo "parakeet-tdt-0.6b-v3 gpu 5s" ;;
    l3) echo "parakeet-tdt-0.6b-v3 npu 5s" ;;
    l4) echo "parakeet-tdt-0.6b-v3-30s cpu 30s" ;;
    l5) echo "parakeet-tdt-0.6b-v3-30s gpu 30s" ;;
    *) return 1 ;;
  esac
}

next_id() {  # jsonl every limit [resume_after] -> the first id of the selection without a row ("" = none left)
  python3 - "$1" "$B/device-set/manifest-device.tsv" "$2" "$3" "${4:-}" <<'PY'
import json, sys
jsonl, manifest, every, limit, resume = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
ids = [l.split("\t")[0] for l in open(manifest) if l.strip()][::every]
if limit > 0:
    ids = ids[:limit]
if resume:
    ids = ids[ids.index(resume) + 1:]
seen = set()
try:
    for l in open(jsonl):
        r = json.loads(l)
        if "id" in r:
            seen.add(r["id"])
except FileNotFoundError:
    pass
print(next((i for i in ids if i not in seen), ""))
PY
}

grab_logcat() {  # tag pid -> append the app process's LiteRT / delegate / test lines (no ASR merger lines)
  local tag=$1 pid=$2 raw="$B/logcat-raw-$1.txt"
  A logcat -d -v threadtime > "$raw" 2>/dev/null
  python3 - "$raw" "$REC/$tag.logcat.log" "$pid" <<'PY'
import os, re, sys
raw, out, pid = sys.argv[1], sys.argv[2], sys.argv[3]
keep = re.compile(r"litert|LiteRt|tflite|TfLite|xnnpack|XNNPACK|delegate|Delegate|Dispatch|Accelerator|accelerator|"
                  r"OpenCL|opencl|GPU|gpu|NPU|npu|Qnn|QNN|qnn|Htp|HTP|AsrBench|TestRunner|AndroidRuntime|FATAL|"
                  r"Fatal signal|libc|DEBUG|tombstone|ActivityManager.*" + re.escape("com.google.ai.edge.examples.asr"))
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
  local arm=$1 setname=$2 label=${3:-} spec model accel win every limit tag key fg="" fails=0 lost=0
  spec=$(arm_spec "$arm") || { log "unknown arm $arm"; exit 2; }
  model=${spec%% *}; win=${spec##* }; accel=${spec#* }; accel=${accel%% *}
  case "$setname" in
    S4) every=4; limit=0 ;;
    full) every=1; limit=0 ;;
    spread10) every=260; limit=10 ;;  # S4 rows 0, 65, 130, ... (the set is sorted by length: 35 s down to 2.7 s)
    smoke*) every=4; limit=${setname#smoke} ;;
    warm*) every=4; limit=${setname#warm}; label=${label:-warm} ;;
    *) log "unknown set $setname"; exit 2 ;;
  esac
  key="$model/$accel"
  [ -n "$label" ] || { [ "$(state_get "$key")" = 1 ] && label=warm || label=cold; }
  tag="$arm-litert-$accel-$win-$setname"
  [ "${FOREGROUND:-0}" = 1 ] && { tag="$tag-fg"; fg="-e foreground true"; }
  # RESUME_AFTER=<id>: a second part of a run stopped at a hold's end, under its own tag (-p2).
  local resume="${RESUME_AFTER:-}"
  [ -n "$resume" ] && tag="$tag-${PART:-p2}"
  need_hold
  if [ "$DRY" != 1 ] && ls "$REC/$tag".* 2>/dev/null | grep -q -v '\.attempt[0-9]*$'; then
    # A retake keeps the earlier capture beside it as <file>.attemptK (audit trail, out of every glob).
    local k=1 f
    while ls "$REC/$tag".*.attempt$k >/dev/null 2>&1; do k=$((k + 1)); done
    for f in "$REC/$tag".*; do case "$f" in *.attempt[0-9]*) ;; *) mv "$f" "$f.attempt$k" ;; esac; done
    log "earlier capture of $tag kept as *.attempt$k"
  fi
  local commit; commit=$(cut -d' ' -f1 "$B/apk/APP_COMMIT" 2>/dev/null)
  log "run $tag (model=$model accelerator=$accel every=$every limit=$limit label=$label)"
  echo "# $tag $(date '+%F %T %Z') label=$label" >> "$REC/$tag.cmd"
  if [ "$DRY" = 1 ]; then
    echo "DRY cool (battery <= $COOL_BATTERY_C C, thermal 0, full ceilings, <= ${COOL_MAX_S}s)" >&2
  else
    cool | tee -a "$REC/$tag.cmd" >&2
  fi
  "$HERE/probe.sh" before > "$REC/$tag.probe-before.json"
  # The app's ART compilation state (JIT-only after a fresh install; background dexopt may change it).
  A shell "dumpsys package $PKG | grep -E 'compilation_filter|\[status='" | sed 's/^/dexopt: /' >> "$REC/$tag.cmd"
  A shell "rm -f $EXT/bench/$tag.*"
  A logcat -c
  local start_after="" failed="" kind="" attempt=0 n last_n t_change now st pid done_flag ceil header_pid="" grabbed=0
  printf 'time\tevent\tdetail\n' > "$REC/$tag.events.tsv"
  printf 'time\tceilings_khz\n' > "$REC/$tag.cpufreq-host.tsv"
  while :; do
    attempt=$((attempt + 1))
    local extra=""
    [ -n "$resume" ] && extra="-e start_after $resume"
    [ -n "$start_after" ] && extra="-e start_after $start_after -e failed_id $failed -e failed_kind $kind"
    local am="am instrument -r -e model $model -e accelerator $accel -e manifest $WAV_DIR/manifest-device.tsv -e every $every -e limit $limit -e tag $tag -e load_label $label -e app_commit ${commit:-unknown} $fg $extra $RUNNER"
    echo "$(date '+%T') attempt $attempt: adb -s $SERIAL shell $am" >> "$REC/$tag.cmd"
    printf '%s\tlaunch\tattempt %s %s\n' "$(date +%T)" "$attempt" "$extra" >> "$REC/$tag.events.tsv"
    if [ "${AM_WAIT:-0}" = 1 ] && [ "$DRY" != 1 ]; then
      # Fallback form: `am instrument -w` in the foreground of one remote shell whose adb client runs
      # in the background on the Mac (nothing is left in the background on the phone).
      ( adb -s "$SERIAL" shell "${am/am instrument -r/am instrument -w -r}" </dev/null >> "$REC/$tag.am.log" 2>&1 & )
    else
      A shell "$am"
    fi
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
      if [ $grabbed = 0 ] && [ -n "$pid" ] && A shell "grep -q -E '\"type\": ?\"header\"' $EXT/bench/$tag.jsonl" 2>/dev/null; then
        header_pid=$pid
        printf '%s\theader\tpid %s, %s logcat lines\n' "$(date +%T)" "$pid" "$(grab_logcat "$tag" "$pid")" >> "$REC/$tag.events.tsv"
        grabbed=1
      fi
      if [ -f "$B/stop-$tag" ]; then
        # A planned stop (the hold's end): the driver stops the app itself, so it is never read as a crash.
        A shell am force-stop "$PKG"
        rm -f "$B/stop-$tag"
        printf '%s\tplanned-stop\t%s lines\n' "$(date +%T)" "$n" >> "$REC/$tag.events.tsv"
        break 2
      fi
      if [ "$done_flag" = 1 ]; then
        printf '%s\tdone\t%s lines\n' "$(date +%T)" "$n" >> "$REC/$tag.events.tsv"
        break 2
      fi
      if [ -z "$pid" ] || [ $((now - t_change)) -ge "$STALL_S" ]; then
        if [ -n "$pid" ]; then kind=hang; A shell am force-stop "$PKG"; sleep 3; else kind=crash; fi
        A pull "$EXT/bench/$tag.jsonl" "$B/$tag.partial.jsonl" >/dev/null 2>&1
        grab_logcat "$tag" "${header_pid:-$pid}" >/dev/null
        A logcat -b crash -d >> "$REC/$tag.crash.log" 2>/dev/null
        failed=$(next_id "$B/$tag.partial.jsonl" "$every" "$limit" "$resume")
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
  "$HERE/probe.sh" after > "$REC/$tag.probe-after.json"
  if [ "$DRY" != 1 ]; then
    grab_logcat "$tag" "${header_pid:-x}" >/dev/null
    for f in jsonl vmhwm.log load-logcat.txt done; do A pull "$EXT/bench/$tag.$f" "$REC/$tag.$f" >/dev/null 2>&1; done
    state_add "$key"
    log "$tag: $(cat "$REC/$tag.done" 2>/dev/null || echo 'no done marker') ($(grep -c -E '"type": ?"utterance"' "$REC/$tag.jsonl" 2>/dev/null) rows)"
  fi
}

case "${1:-}" in
  freeze) cmd_freeze ;;
  setup) cmd_setup ;;
  run) shift; [ $# -ge 2 ] || { sed -n 2,35p "$0"; exit 2; }; cmd_run "$@" ;;
  finish) cmd_finish ;;
  *) sed -n 2,35p "$0"; exit 2 ;;
esac
