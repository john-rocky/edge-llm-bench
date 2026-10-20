#!/bin/bash
# Galaxy S26 driver for the NPU checks (asr-npu-v1, docs/asr-npu-v1.md) of the litert-samples
# speech_recognition benchmark build (package ….npucheck): B = NpuCompareTest (one model file, the CPU
# or the NPU, fixed encoder inputs, every output written), A and C = AsrBenchTest (the app's file
# pipeline) on LibriSpeech test-clean S32's first rows. asr-fix-v1's driver (tools/asr-fix/
# run_fix_s26.sh) with this round's package, files, arms and the compare runs; no cool-down wait
# (nothing here is timed: the checks are about the outputs and the text).
#
#   run_npu_s26.sh freeze                 # copy the built APKs (debug app, bench app, bench test) + sha256, app commit
#   run_npu_s26.sh setup                  # debug app: models, mel inputs, WAVs into its files dir (run-as); bench build over it
#   run_npu_s26.sh compare <b-arm>        # NpuCompareTest: am instrument, poll, pull
#   run_npu_s26.sh run <arm> <set>        # AsrBenchTest: probe, am instrument, poll (watchdog), probe, pull
#   run_npu_s26.sh check <tag>            # one line on a run (tools/asr-fix/check_run.py)
#   run_npu_s26.sh freeze2                # the decoder-only run's test APK (apk2/) + sha256, app commit
#   run_npu_s26.sh install-test2          # that test APK over the installed one (the app and its files stay)
#   run_npu_s26.sh decoder <d-arm>        # DecoderBufferTest on b-tdt-cpu's encoder outputs (on the phone), 3 passes
#   run_npu_s26.sh cleanup                # uninstall the two packages (their files dir goes too) and round 6's .prcheck pair, /data before / after
#   run_npu_s26.sh freeze3                # the decoder-only run 2's test APK (apk3/)
#   run_npu_s26.sh setup-min              # after a cleanup: the app with the SM8850 TDT file + its tokenizer, the apk3 test APK
#   run_npu_s26.sh decoder2 <p|t-arm>     # DecoderBufferTest, seeded encoder outputs: p-npu-shared / p-npu-separate (pattern
#                                         # mode) and t-npu-shared / t-npu-separate (TdtDecoder), one pass of four windows
#   run_npu_s26.sh finish                 # put the stay-awake setting back
#   DRY=1 run_npu_s26.sh ...              # print the adb commands, run none of them
#
# <b-arm>: b-tdt-cpu  the TDT 5 s f32 stateful file on the CPU (encode on each window, decode / decode_1
#                     on its own encoder outputs)
#          b-tdt-npu  the TDT SM8850 AOT file on the NPU (the same; decode / decode_1 also on b-tdt-cpu's
#                     encoder outputs)
#          b-ctc-cpu  the CTC 5 s f32 file on the CPU (encode on each window)
#          b-ctc-npu  the CTC SM8850 AOT file on the NPU
# <arm>:   a-ctc-i8   parakeet-ctc-0.6b, CPU, the entry's own file (5 s i8)
#          a-ctc-f32  parakeet-ctc-0.6b, CPU, the 5 s f32 file (model_file)
#          c-npu-shared    parakeet-tdt-0.6b-v3, NPU (SM8850 AOT), tdt_fix, tdt_buffers shared (the app's buffers)
#          c-npu-separate  the same, tdt_buffers separate
#          c-cpu-shared    parakeet-tdt-0.6b-v3, CPU, the 5 s f32 stateful file (model_file), tdt_fix, shared
#          c-cpu-separate  the same, tdt_buffers separate (its text against c-cpu-shared checks the separate form)
# <d-arm>: d-cpu-shared        TdtDecoder (tdt_fix) on the CPU f32 stateful file, the app's buffers: the reference tokens
#          d-npu-shared        the SM8850 file on the NPU, the app's buffers, encode run before each window
#          d-npu-separate      the same, tdt_buffers separate
#          d-npu-shared-noenc  the same as d-npu-shared without the encode run
# <set>:   first<N> (the first N rows of S32) | smoke<N> (the same rows)
#
# Records go to results/raw/2026-10-20-asr-npu-v1-s26-android/ (REC=... to override): per AsrBenchTest
# run <tag>.jsonl, .vmhwm.log, .load-logcat.txt, .done, .cmd, .events.tsv, .logcat.log,
# .probe-before.json / .probe-after.json (+ .tokens.log on the NPU); per compare run <tag>.json,
# .load-logcat.txt, .logcat.log, .cmd, .probe-*.json; the raw outputs (<tag>.*.f32) go to
# .build/asr-npu/compare/. A retake keeps the earlier files as <file>.attemptK.
#
# The phone is touched only under the S26 hold held by a keeper named asr_npu_s26 (HOLD_OK=1 skips the
# check). No adb shell call leaves a background child on the phone: the tests start through
# `am instrument` without -w and the driver polls with short calls.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
DRY="${DRY:-0}"
SERIAL="${SERIAL:-RFGL80R6A6H}"
PKG=com.google.ai.edge.examples.asr.npucheck
RUNNER="$PKG.test/androidx.test.runner.AndroidJUnitRunner"
APPDIR="${APPDIR:-$HOME/code/litert-samples-asr-npu-wt/samples/litert/speech_recognition/AndroidApp}"
B="${B:-$ROOT/.build/asr-npu}"
REC="${REC:-$ROOT/results/raw/2026-10-20-asr-npu-v1-s26-android}"
[ "$DRY" = 1 ] && REC="$B/dry-rec"  # a dry run writes its logs beside the build, never into the record
HOLD="$HOME/code/litertlm-convert/community_accel_work/s2_npu_sweep/.device_hold"
DT=/data/local/tmp/edge-llm-bench/asr-npu
EXT="/sdcard/Android/data/$PKG/files"
FILES="/data/user/0/$PKG/files"
WAV_DIR="$FILES/sets/test-clean"
WARMUP_ID=1995-1836-0004
STALL_S="${STALL_S:-600}"
POLL_S="${POLL_S:-5}"
MAX_FAILS=3
mkdir -p "$B" "$REC"

log() { echo "[asr-npu $(date +%H:%M:%S)] $*" >&2; }

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
sys.exit(0 if d.get("script") == "asr_npu_s26" else 1)
PY
}

need_hold() {
  hold_ok || { log "the S26 hold is not ours (asr_npu_s26 with a live keeper): $(cat "$HOLD" 2>/dev/null)"; exit 4; }
}

dexopt_of() {  # package -> "<compiler filter>/<reason>" of its APK, from dumpsys package
  A shell "dumpsys package $1" | python3 -c '
import re, sys
m = re.search(r"\[status=([^\]]+)\]\s*\[reason=([^\]]+)\]", sys.stdin.read())
print((m.group(1) + "/" + m.group(2)) if m else "unknown")'
}

screen_state() {  # one line: wakefulness and the keyguard lines
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

# Local file under .build/asr-npu/models -> path under the app's files dir (model_metadata.json keys
# parakeet-tdt-0.6b-v3 and parakeet-ctc-0.6b, ModelMetadataManager's names; model_f32.tflite = the
# CPU file of the B and C runs, read through model_file / NpuCompareTest's model).
MODEL_MAP="tdt-tokenizer.json parakeet-tdt-0.6b-v3/tokenizer.json
ctc-tokenizer.json parakeet-ctc-0.6b/tokenizer.json
parakeet_ctc_0.6b_5s_i8.tflite parakeet-ctc-0.6b/model.tflite
parakeet_ctc_0.6b_5s_f32_Qualcomm_SM8850.tflite parakeet-ctc-0.6b/model_npu.tflite
parakeet_tdt_0.6b_v3_5s_f32_stateful_Qualcomm_SM8850.tflite parakeet-tdt-0.6b-v3/model_npu.tflite
parakeet_ctc_0.6b_5s_f32.tflite parakeet-ctc-0.6b/model_f32.tflite
parakeet_tdt_0.6b_v3_5s_f32_stateful.tflite parakeet-tdt-0.6b-v3/model_f32.tflite"

cmd_setup() {
  need_hold
  local apk="$B/apk" f dst want got n free_kb L="$REC/setup.log"
  [ -f "$apk/app-bench.apk" ] || { log "no frozen APK: run freeze first"; exit 2; }
  : > "$L"
  {
    echo "# setup $(date '+%F %T %Z')"
    cat "$apk/SHA256SUMS" "$apk/APP_COMMIT"
    echo "stay_on_while_plugged_in before: $(A shell settings get global stay_on_while_plugged_in | tr -d '\r')"
    echo "/data before: $(A shell df -k /data | tail -1 | tr -s ' ')"
  } >> "$L"
  # /data must take every file (about 8.0 GB in the app's files dir) plus the largest staging copy.
  free_kb=$(A shell df -k /data | tail -1 | awk '{print $4}')
  if [ "$DRY" != 1 ] && [ "${free_kb:-0}" -lt 12000000 ]; then log "/data has ${free_kb} kB free, below 12 GB"; exit 3; fi
  # 1. The debug build (same package and key): run-as can write its files dir.
  A install -r -t "$apk/app-debug.apk" >&2 || { log "install debug app failed"; exit 2; }
  echo "installed app-debug.apk (debuggable, for run-as)" >> "$L"
  A shell svc power stayon usb
  A shell input keyevent KEYCODE_WAKEUP
  A shell mkdir -p "$DT/models" "$DT/sets" "$DT/mel"
  # 2. Models one at a time: pushed to /data/local/tmp, copied into the app's files dir with run-as,
  # sha256 read back on the phone against models.lock.json (the Hub's hash), the staging copy removed.
  echo "$MODEL_MAP" | while read -r f dst; do
    want=$(python3 -c 'import json,sys; print({r["local"].split("/")[-1]: r["sha256"] for r in json.load(open(sys.argv[1]))}[sys.argv[2]])' "$B/models/models.lock.json" "$f")
    got=$(A shell run-as "$PKG" sha256sum "files/$dst" 2>/dev/null | cut -c1-64)
    if [ "$got" = "$want" ]; then echo "model $f -> files/$dst already there sha256_phone=$got OK" | tee -a "$L" >&2; continue; fi
    A push "$B/models/$f" "$DT/models/$f" >&2 || { log "push $f failed"; exit 2; }
    A shell "run-as $PKG sh -c 'mkdir -p files/${dst%/*} && cat > files/$dst' < $DT/models/$f"
    got=$(A shell run-as "$PKG" sha256sum "files/$dst" | cut -c1-64)
    A shell rm -f "$DT/models/$f"
    echo "model $f -> files/$dst route=run-as sha256_local=$want sha256_phone=$got $([ "$got" = "$want" ] && echo OK || echo MISMATCH)" | tee -a "$L" >&2
    [ "$DRY" = 1 ] || [ "$got" = "$want" ] || exit 3
  done || exit $?
  # 3. The B inputs: the app's encoder inputs of the chosen windows (MelDumpTest, mel/MANIFEST).
  while read -r f want; do
    A push "$B/mel/$f" "$DT/mel/$f" >/dev/null
    A shell "run-as $PKG sh -c 'mkdir -p files/npucheck/mel && cat > files/npucheck/mel/$f' < $DT/mel/$f"
    got=$(A shell run-as "$PKG" sha256sum "files/npucheck/mel/$f" | cut -c1-64)
    echo "mel $f sha256_local=$want sha256_phone=$got $([ "$got" = "$want" ] && echo OK || echo MISMATCH)" | tee -a "$L" >&2
    [ "$DRY" = 1 ] || [ "$got" = "$want" ] || exit 3
  done < "$B/mel/MANIFEST"
  # 4. WAVs: one tar (manifest-device.tsv with every row + F20 + W), unpacked in the app's files dir.
  want=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["tar_sha256"])' "$B/set/test-clean-F20W.tar.json")
  A push "$B/set/test-clean-F20W.tar" "$DT/sets/test-clean-F20W.tar" >&2
  got=$(A shell sha256sum "$DT/sets/test-clean-F20W.tar" | cut -c1-64)
  A shell "run-as $PKG sh -c 'mkdir -p files/sets/test-clean && cd files/sets/test-clean && tar -xf -' < $DT/sets/test-clean-F20W.tar"
  n=$(A shell "run-as $PKG ls files/sets/test-clean | grep -c '\.wav\$'" | tr -d '\r')
  echo "wav set tar sha256_local=$want sha256_phone=$got wavs_unpacked=$n ($WAV_DIR)" | tee -a "$L" >&2
  if [ "$DRY" != 1 ] && { [ "$got" != "$want" ] || [ "$n" != 21 ]; }; then log "WAV set check failed"; exit 3; fi
  A shell rm -rf "$DT"
  echo "staging removed ($DT); /data: $(A shell df -k /data | tail -1 | tr -s ' ')" | tee -a "$L" >&2
  # 5. The bench build over it (the data stays) and the test APK.
  A install -r "$apk/app-bench.apk" >&2 || { log "install bench app failed"; exit 2; }
  A install -r -t "$apk/app-bench-androidTest.apk" >&2 || { log "install bench test failed"; exit 2; }
  {
    echo "installed app-bench.apk + app-bench-androidTest.apk over it (install -r: data kept)"
    echo "pkgFlags: $(A shell "dumpsys package $PKG | grep -m2 -E 'pkgFlags=|privateFlags='" | tr -s ' \r\n' ' ')"
    echo "dexopt app: $(dexopt_of "$PKG")"
    echo "dexopt test: $(dexopt_of "$PKG.test")"
    echo "screen: $(screen_state)"
  } | tee -a "$L" >&2
  log "setup done"
}

cmd_finish() {
  local before
  before=$(sed -n 's/^stay_on_while_plugged_in before: //p' "$REC/setup.log" | head -1)
  [ -n "$before" ] && A shell settings put global stay_on_while_plugged_in "$before"
  log "stay_on_while_plugged_in restored to ${before:-?}"
}

keep_earlier() {  # tag -> an earlier capture of the tag is kept beside it as <file>.attemptK
  local tag=$1 k=1 f
  [ "$DRY" = 1 ] && return 0
  ls "$REC/$tag".* 2>/dev/null | grep -q -v '\.attempt[0-9]*$' || return 0
  while ls "$REC/$tag".*.attempt$k >/dev/null 2>&1; do k=$((k + 1)); done
  for f in "$REC/$tag".*; do case "$f" in *.attempt[0-9]*) ;; *) mv "$f" "$f.attempt$k" ;; esac; done
  log "earlier capture of $tag kept as *.attempt$k"
}

grab_tokens() {  # tag -> append the merger's "decode: tokenId=" lines logcat still holds (an excerpt: the buffer turns over)
  local tag=$1 raw="$B/logcat-asr-$1.txt"
  A logcat -d -v threadtime -s ASR:D > "$raw" 2>/dev/null
  python3 - "$raw" "$REC/$tag.tokens.log" <<'PY'
import os, sys
raw, out = sys.argv[1], sys.argv[2]
have = set(open(out).read().splitlines()) if os.path.exists(out) else set()
with open(out, "a") as f:
    for line in open(raw, errors="replace"):
        line = line.rstrip("\n")
        if "decode: tokenId=" in line and line not in have:
            f.write(line + "\n")
            have.add(line)
PY
}

grab_logcat() {  # tag pid -> append the app process's runtime / delegate / test lines (no ASR merger lines)
  local tag=$1 pid=$2 raw="$B/logcat-raw-$1.txt"
  A logcat -d -v threadtime > "$raw" 2>/dev/null
  python3 - "$raw" "$REC/$tag.logcat.log" "$pid" <<'PY'
import os, re, sys
raw, out, pid = sys.argv[1], sys.argv[2], sys.argv[3]
keep = re.compile(r"litert|LiteRt|tflite|TfLite|xnnpack|XNNPACK|delegate|Delegate|Dispatch|Accelerator|accelerator|"
                  r"NPU|npu|Qnn|QNN|qnn|Htp|HTP|fastrpc|AsrBench|NpuCompare|TestRunner|"
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

compare_spec() {  # b-arm -> "model accelerator inputs-kind extra"
  case "$1" in
    b-tdt-cpu) echo "parakeet-tdt-0.6b-v3/model_f32.tflite cpu tdt -e decode_self true" ;;
    b-tdt-npu) echo "parakeet-tdt-0.6b-v3/model_npu.tflite npu tdt -e decode_self true -e decode_from $(tdt_cpu_encoder_outputs)" ;;
    b-ctc-cpu) echo "parakeet-ctc-0.6b/model_f32.tflite cpu ctc" ;;
    b-ctc-npu) echo "parakeet-ctc-0.6b/model_npu.tflite npu ctc" ;;
    *) return 1 ;;
  esac
}

mel_inputs() {  # tdt | ctc -> comma-separated files-dir paths of that model's B inputs (mel/MANIFEST order)
  awk -v k="$1" '$1 ~ "^"k"-" {printf "%snpucheck/mel/%s", (n++ ? "," : ""), $1}' "$B/mel/MANIFEST"
}

tdt_cpu_encoder_outputs() {  # b-tdt-cpu's encoder outputs on the phone, in window order
  local n i list=""
  n=$(awk '$1 ~ /^tdt-/' "$B/mel/MANIFEST" | wc -l | tr -d ' ')
  for ((i = 0; i < n; i++)); do list="$list${list:+,}$EXT/npucheck/b-tdt-cpu.enc.w$i.out0.f32"; done
  echo "$list"
}

cmd_compare() {
  local arm=$1 spec model accel kind extra tag=$1 am n st pid t0 done_flag
  spec=$(compare_spec "$arm") || { log "unknown compare arm $arm"; exit 2; }
  read -r model accel kind extra <<<"$spec"
  need_hold
  keep_earlier "$tag"
  "$HERE/probe.sh" before > "$REC/$tag.probe-before.json"
  A shell "rm -f $EXT/npucheck/$tag.*"
  A logcat -c
  am="am instrument -r -e class com.google.ai.edge.examples.asr.NpuCompareTest -e model $model -e accelerator $accel -e inputs $(mel_inputs "$kind") -e repeats 2 -e foreground front -e tag $tag $extra $RUNNER"
  echo "# $tag $(date '+%F %T %Z')" >> "$REC/$tag.cmd"
  echo "$(date '+%T') adb -s $SERIAL shell $am" >> "$REC/$tag.cmd"
  log "compare $tag ($model on $accel)"
  A shell "$am" > "$B/$tag.instrument.txt"
  [ "$DRY" = 1 ] && return 0
  t0=$(date +%s)
  while :; do
    sleep "$POLL_S"
    st=$(A shell "[ -f $EXT/npucheck/$tag.done ] && echo done=1; echo pid=\$(pidof $PKG)" | tr -d '\r')
    done_flag=$(echo "$st" | sed -n 's/^done=//p'); pid=$(echo "$st" | sed -n 's/^pid=//p')
    [ "$done_flag" = 1 ] && break
    if [ -z "$pid" ] && [ $(( $(date +%s) - t0 )) -gt 20 ]; then log "$tag: the process is gone without a done marker"; break; fi
    if [ $(( $(date +%s) - t0 )) -gt "$STALL_S" ]; then log "$tag: no done marker after ${STALL_S}s, stopped"; A shell am force-stop "$PKG"; break; fi
    [ -n "$pid" ] && n=$pid
  done
  sleep 2
  grab_logcat "$tag" "${n:-x}" >/dev/null
  A logcat -b crash -d >> "$REC/$tag.crash.log" 2>/dev/null
  [ -s "$REC/$tag.crash.log" ] || rm -f "$REC/$tag.crash.log"
  "$HERE/probe.sh" after > "$REC/$tag.probe-after.json"
  mkdir -p "$B/compare"
  A pull "$EXT/npucheck/." "$B/compare/" >/dev/null 2>&1
  for f in json load-logcat.txt done; do [ -f "$B/compare/$tag.$f" ] && cp "$B/compare/$tag.$f" "$REC/$tag.$f"; done
  log "$tag: $(cat "$REC/$tag.done" 2>/dev/null || echo 'no done marker') ($(ls "$B/compare/$tag".*.f32 2>/dev/null | wc -l | tr -d ' ') output files)"
}

cmd_freeze2() {  # the decoder-only run's test APK (the app APK on the phone stays the frozen one)
  local out="$B/apk2" commit dirty
  mkdir -p "$out"
  cp "$APPDIR/app/build/outputs/apk/androidTest/bench/app-bench-androidTest.apk" "$out/app-bench-androidTest.apk"
  commit=$(git -C "$APPDIR" rev-parse HEAD)
  dirty=$(git -C "$APPDIR" status --porcelain -- . | grep -v '^??' | wc -l | tr -d ' ')
  (cd "$out" && shasum -a 256 app-bench-androidTest.apk > SHA256SUMS)
  echo "$commit dirty_tracked_files=$dirty" > "$out/APP_COMMIT"
  cat "$out/SHA256SUMS" "$out/APP_COMMIT"
}

cmd_install_test2() {  # the new test APK over the installed one (the app and its files stay)
  need_hold
  local L="$REC/setup-decoder.log"
  {
    echo "# install-test2 $(date '+%F %T %Z')"
    cat "$B/apk2/SHA256SUMS" "$B/apk2/APP_COMMIT"
    echo "app apk on the phone: $(A shell pm path "$PKG" | tr -d '\r')"
    echo "stay_on_while_plugged_in before: $(A shell settings get global stay_on_while_plugged_in | tr -d '\r')"
    echo "/data: $(A shell df -k /data | tail -1 | tr -s ' ')"
  } >> "$L"
  A shell svc power stayon usb
  A shell input keyevent KEYCODE_WAKEUP
  A install -r -t "$B/apk2/app-bench-androidTest.apk" >&2 || { log "install test APK failed"; exit 2; }
  {
    echo "installed apk2/app-bench-androidTest.apk (install -r -t)"
    echo "encoder outputs on the phone: $(A shell "ls -l $EXT/npucheck/ | grep -c 'b-tdt-cpu.enc.w[0-9].out0.f32'" | tr -d '\r') files"
  } | tee -a "$L" >&2
}

decoder_spec() {  # arm -> "model accelerator tdt_buffers run_encode"
  case "$1" in
    d-cpu-shared) echo "parakeet-tdt-0.6b-v3/model_f32.tflite cpu shared true" ;;
    d-npu-shared) echo "parakeet-tdt-0.6b-v3/model_npu.tflite npu shared true" ;;
    d-npu-separate) echo "parakeet-tdt-0.6b-v3/model_npu.tflite npu separate true" ;;
    d-npu-shared-noenc) echo "parakeet-tdt-0.6b-v3/model_npu.tflite npu shared false" ;;
    *) return 1 ;;
  esac
}

cmd_decoder() {  # DecoderBufferTest on b-tdt-cpu's four encoder outputs, three passes
  local arm=$1 spec model accel buffers runenc tag=$1 am st pid t0 done_flag n="" inputs
  spec=$(decoder_spec "$arm") || { log "unknown decoder arm $arm"; exit 2; }
  read -r model accel buffers runenc <<<"$spec"
  need_hold
  keep_earlier "$tag"
  inputs=$(tdt_cpu_encoder_outputs)
  "$HERE/probe.sh" before > "$REC/$tag.probe-before.json"
  A shell "rm -f $EXT/npucheck/$tag.*"
  A logcat -c
  am="am instrument -r -e class com.google.ai.edge.examples.asr.DecoderBufferTest -e model $model -e accelerator $accel -e tdt_buffers $buffers -e run_encode $runenc -e enc_inputs $inputs -e passes 3 -e foreground front -e tag $tag $RUNNER"
  echo "# $tag $(date '+%F %T %Z')" >> "$REC/$tag.cmd"
  echo "$(date '+%T') adb -s $SERIAL shell $am" >> "$REC/$tag.cmd"
  log "decoder $tag ($model on $accel, tdt_buffers=$buffers, run_encode=$runenc)"
  A shell "$am" > "$B/$tag.instrument.txt"
  [ "$DRY" = 1 ] && return 0
  t0=$(date +%s)
  while :; do
    sleep "$POLL_S"
    st=$(A shell "[ -f $EXT/npucheck/$tag.done ] && echo done=1; echo pid=\$(pidof $PKG)" | tr -d '\r')
    done_flag=$(echo "$st" | sed -n 's/^done=//p'); pid=$(echo "$st" | sed -n 's/^pid=//p')
    [ "$done_flag" = 1 ] && break
    if [ -z "$pid" ] && [ $(( $(date +%s) - t0 )) -gt 20 ]; then log "$tag: the process is gone without a done marker"; break; fi
    if [ $(( $(date +%s) - t0 )) -gt 300 ]; then log "$tag: no done marker after 300s, stopped"; A shell am force-stop "$PKG"; break; fi
    [ -n "$pid" ] && n=$pid
  done
  sleep 2
  for f in json done; do A pull "$EXT/npucheck/$tag.$f" "$REC/$tag.$f" >/dev/null 2>&1; done
  # A short run ends before the first poll reads its pid (2026-10-20: 2.4 s, the app's lines were not
  # kept): the test writes its pid into the report.
  [ -n "$n" ] || n=$(jq -r '.pid // empty' "$REC/$tag.json" 2>/dev/null)
  grab_logcat "$tag" "${n:-x}" >/dev/null
  A logcat -b crash -d >> "$REC/$tag.crash.log" 2>/dev/null
  [ -s "$REC/$tag.crash.log" ] || rm -f "$REC/$tag.crash.log"
  "$HERE/probe.sh" after > "$REC/$tag.probe-after.json"
  log "$tag: $(cat "$REC/$tag.done" 2>/dev/null || echo 'no done marker')"
}

PRCHECK=com.google.ai.edge.examples.asr.prcheck  # the same lane's round 6 (asr-pr), closed; uninstalled here on the supervisor's word

cmd_freeze3() {  # the decoder-only run 2's test APK (seeded encoder output, the pattern mode, its own logcat)
  local out="$B/apk3" commit dirty
  mkdir -p "$out"
  cp "$APPDIR/app/build/outputs/apk/androidTest/bench/app-bench-androidTest.apk" "$out/app-bench-androidTest.apk"
  commit=$(git -C "$APPDIR" rev-parse HEAD)
  dirty=$(git -C "$APPDIR" status --porcelain -- . | grep -v '^??' | wc -l | tr -d ' ')
  (cd "$out" && shasum -a 256 app-bench-androidTest.apk > SHA256SUMS)
  echo "$commit dirty_tracked_files=$dirty" > "$out/APP_COMMIT"
  cat "$out/SHA256SUMS" "$out/APP_COMMIT"
}

cmd_setup_min() {  # after the cleanup: the app again with the SM8850 TDT file and its tokenizer only, the run 2 test APK
  need_hold
  local apk="$B/apk" L="$REC/setup-decoder2.log" f dst want got
  {
    echo "# setup-min $(date '+%F %T %Z')"
    cat "$apk/SHA256SUMS" "$B/apk3/SHA256SUMS" "$B/apk3/APP_COMMIT"
    echo "stay_on_while_plugged_in before: $(A shell settings get global stay_on_while_plugged_in | tr -d '\r')"
    echo "/data before: $(A shell df -k /data | tail -1 | tr -s ' ')"
  } >> "$L"
  A install -r -t "$apk/app-debug.apk" >&2 || { log "install debug app failed"; exit 2; }
  A shell svc power stayon usb
  A shell input keyevent KEYCODE_WAKEUP
  A shell mkdir -p "$DT/models"
  printf '%s\n' "parakeet_tdt_0.6b_v3_5s_f32_stateful_Qualcomm_SM8850.tflite parakeet-tdt-0.6b-v3/model_npu.tflite" \
    "tdt-tokenizer.json parakeet-tdt-0.6b-v3/tokenizer.json" | while read -r f dst; do
    want=$(python3 -c 'import json,sys; print({r["local"].split("/")[-1]: r["sha256"] for r in json.load(open(sys.argv[1]))}[sys.argv[2]])' "$B/models/models.lock.json" "$f")
    A push "$B/models/$f" "$DT/models/$f" >&2 || { log "push $f failed"; exit 2; }
    A shell "run-as $PKG sh -c 'mkdir -p files/${dst%/*} && cat > files/$dst' < $DT/models/$f"
    got=$(A shell run-as "$PKG" sha256sum "files/$dst" | cut -c1-64)
    A shell rm -f "$DT/models/$f"
    echo "model $f -> files/$dst sha256_local=$want sha256_phone=$got $([ "$got" = "$want" ] && echo OK || echo MISMATCH)" | tee -a "$L" >&2
    [ "$DRY" = 1 ] || [ "$got" = "$want" ] || exit 3
  done || exit $?
  A shell rm -rf "$DT"
  A install -r "$apk/app-bench.apk" >&2 || { log "install bench app failed"; exit 2; }
  A install -r -t "$B/apk3/app-bench-androidTest.apk" >&2 || { log "install test APK failed"; exit 2; }
  echo "installed app-bench.apk + apk3/app-bench-androidTest.apk; /data: $(A shell df -k /data | tail -1 | tr -s ' ')" | tee -a "$L" >&2
}

decoder2_spec() {  # arm -> "mode tdt_buffers"
  case "$1" in
    p-npu-shared) echo "pattern shared" ;;
    p-npu-separate) echo "pattern separate" ;;
    t-npu-shared) echo "tdt shared" ;;
    t-npu-separate) echo "tdt separate" ;;
    *) return 1 ;;
  esac
}

cmd_decoder2() {  # DecoderBufferTest on seeded encoder outputs (seed 1..4), one pass, the SM8850 file on the NPU
  local arm=$1 spec mode buffers tag=$1 am st pid t0 done_flag n=""
  spec=$(decoder2_spec "$arm") || { log "unknown decoder2 arm $arm"; exit 2; }
  read -r mode buffers <<<"$spec"
  need_hold
  keep_earlier "$tag"
  "$HERE/probe.sh" before > "$REC/$tag.probe-before.json"
  A shell "rm -f $EXT/npucheck/$tag.*"
  A logcat -c
  am="am instrument -r -e class com.google.ai.edge.examples.asr.DecoderBufferTest -e model parakeet-tdt-0.6b-v3/model_npu.tflite -e accelerator npu -e mode $mode -e tdt_buffers $buffers -e run_encode false -e enc_source seed:1 -e windows 4 -e passes 1 -e pattern_runs 64 -e foreground front -e tag $tag $RUNNER"
  echo "# $tag $(date '+%F %T %Z')" >> "$REC/$tag.cmd"
  echo "$(date '+%T') adb -s $SERIAL shell $am" >> "$REC/$tag.cmd"
  log "decoder2 $tag (mode=$mode, tdt_buffers=$buffers)"
  A shell "$am" > "$B/$tag.instrument.txt"
  [ "$DRY" = 1 ] && return 0
  t0=$(date +%s)
  while :; do
    sleep 2
    st=$(A shell "[ -f $EXT/npucheck/$tag.done ] && echo done=1; echo pid=\$(pidof $PKG)" | tr -d '\r')
    done_flag=$(echo "$st" | sed -n 's/^done=//p'); pid=$(echo "$st" | sed -n 's/^pid=//p')
    [ -n "$pid" ] && n=$pid
    [ "$done_flag" = 1 ] && break
    if [ -z "$pid" ] && [ $(( $(date +%s) - t0 )) -gt 20 ]; then log "$tag: the process is gone without a done marker"; break; fi
    if [ $(( $(date +%s) - t0 )) -gt 240 ]; then log "$tag: no done marker after 240s, stopped"; A shell am force-stop "$PKG"; break; fi
  done
  sleep 2
  for f in json done logcat.txt; do A pull "$EXT/npucheck/$tag.$f" "$REC/$tag.$f" >/dev/null 2>&1; done
  [ -n "$n" ] || n=$(jq -r '.pid // empty' "$REC/$tag.json" 2>/dev/null)
  grab_logcat "$tag" "${n:-x}" >/dev/null
  A logcat -b crash -d >> "$REC/$tag.crash.log" 2>/dev/null
  [ -s "$REC/$tag.crash.log" ] || rm -f "$REC/$tag.crash.log"
  "$HERE/probe.sh" after > "$REC/$tag.probe-after.json"
  log "$tag: $(cat "$REC/$tag.done" 2>/dev/null || echo 'no done marker'); memHandle lines $(grep -c 'Failed to find memHandle' "$REC/$tag.logcat.txt" 2>/dev/null)"
}

cmd_cleanup() {  # uninstall this round's two packages (their files dir with the 8.0 GB of models goes too) and round 6's two
  need_hold
  local L="$REC/cleanup.log" p
  {
    echo "# cleanup $(date '+%F %T %Z')"
    echo "/data before: $(A shell df -k /data | tail -1 | tr -s ' ')"
    echo "packages before: $(A shell "pm list packages | grep -E 'com.google.ai.edge.examples.asr.(npucheck|prcheck)'" | tr -d '\r' | tr '\n' ' ')"
    for p in "$PKG.test" "$PKG" "$PRCHECK.test" "$PRCHECK"; do
      echo "uninstall $p: $(A uninstall "$p" 2>&1 | tr -d '\r')"
    done
    echo "packages after: $(A shell "pm list packages | grep -c -E 'com.google.ai.edge.examples.asr.(npucheck|prcheck)'" | tr -d '\r')"
    echo "/data after: $(A shell df -k /data | tail -1 | tr -s ' ')"
  } | tee -a "$L" >&2
}

arm_spec() {  # arm -> "model accelerator tdt_fix tdt_buffers model_file"
  case "$1" in
    a-ctc-i8) echo "parakeet-ctc-0.6b cpu false shared -" ;;
    a-ctc-f32) echo "parakeet-ctc-0.6b cpu false shared parakeet-ctc-0.6b/model_f32.tflite" ;;
    c-npu-shared) echo "parakeet-tdt-0.6b-v3 npu true shared -" ;;
    c-npu-separate) echo "parakeet-tdt-0.6b-v3 npu true separate -" ;;
    c-cpu-shared) echo "parakeet-tdt-0.6b-v3 cpu true shared parakeet-tdt-0.6b-v3/model_f32.tflite" ;;
    c-cpu-separate) echo "parakeet-tdt-0.6b-v3 cpu true separate parakeet-tdt-0.6b-v3/model_f32.tflite" ;;
    *) return 1 ;;
  esac
}

ids_left() {  # jsonl limit -> "<first id of the selection without a row> <the id before it>" ("" = none)
  python3 - "$1" "$B/set/manifest-device.tsv" 32 "$2" <<'PY'
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

cmd_run() {
  local arm=$1 setname=$2 spec model accel fix buffers mfile limit tag fails=0 lost=0 tokens=0
  spec=$(arm_spec "$arm") || { log "unknown arm $arm"; exit 2; }
  read -r model accel fix buffers mfile <<<"$spec"
  case "$setname" in
    first*) limit=${setname#first} ;;
    smoke*) limit=${setname#smoke} ;;
    *) log "unknown set $setname"; exit 2 ;;
  esac
  tag="$arm-$setname"
  [ "$accel" = npu ] && tokens=1
  need_hold
  keep_earlier "$tag"
  local commit start_after="" failed="" kind="" extra mf=""
  commit=$(cut -d' ' -f1 "$B/apk/APP_COMMIT" 2>/dev/null)
  [ "$mfile" != - ] && mf="-e model_file $mfile"
  log "run $tag (model=$model accelerator=$accel tdt_fix=$fix tdt_buffers=$buffers model_file=$mfile limit=$limit)"
  echo "# $tag $(date '+%F %T %Z')" >> "$REC/$tag.cmd"
  "$HERE/probe.sh" before > "$REC/$tag.probe-before.json"
  local dx_app dx_test
  dx_app=$(dexopt_of "$PKG"); dx_test=$(dexopt_of "$PKG.test")
  echo "dexopt: app $dx_app, test $dx_test; screen: $(screen_state)" >> "$REC/$tag.cmd"
  A shell "rm -f $EXT/bench/$tag.*"
  A logcat -c
  local attempt=0 n last_n t_change now st pid done_flag header_pid="" grabbed=0
  printf 'time\tevent\tdetail\n' > "$REC/$tag.events.tsv"
  while :; do
    attempt=$((attempt + 1))
    extra=""
    [ -n "$start_after" ] && extra="-e start_after $start_after"
    [ -n "$failed" ] && extra="$extra -e failed_id $failed -e failed_kind $kind"
    local am="am instrument -r -e class com.google.ai.edge.examples.asr.AsrBenchTest -e engine litert -e model $model -e accelerator $accel -e tdt_fix $fix -e tdt_buffers $buffers $mf -e manifest $WAV_DIR/manifest-device.tsv -e every 32 -e limit $limit -e tag $tag -e load_label cold -e app_commit ${commit:-unknown} -e dexopt_app $dx_app -e dexopt_test $dx_test -e pace none -e warmup_id $WARMUP_ID -e foreground front -e require_top_app false $extra $RUNNER"
    echo "$(date '+%T') attempt $attempt: adb -s $SERIAL shell $am" >> "$REC/$tag.cmd"
    printf '%s\tlaunch\tattempt %s %s\n' "$(date +%T)" "$attempt" "$extra" >> "$REC/$tag.events.tsv"
    A shell "$am" > "$B/$tag.instrument.txt"
    [ "$DRY" = 1 ] && break
    last_n=-1; t_change=$(date +%s); grabbed=0
    while :; do
      sleep "$POLL_S"
      st=$(A shell "echo n=\$(cat $EXT/bench/$tag.jsonl 2>/dev/null | wc -l); [ -f $EXT/bench/$tag.done ] && echo done=1; echo pid=\$(pidof $PKG)" | tr -d '\r')
      if ! echo "$st" | grep -q '^n='; then
        lost=$((lost + 1))
        printf '%s\tadb-miss\t%s\n' "$(date +%T)" "$lost" >> "$REC/$tag.events.tsv"
        [ $lost -ge 20 ] && { printf '%s\tstop\tphone unreachable over adb\n' "$(date +%T)" >> "$REC/$tag.events.tsv"; break 2; }
        continue
      fi
      lost=0
      n=$(echo "$st" | sed -n 's/^n=//p'); n=${n:-0}
      done_flag=$(echo "$st" | sed -n 's/^done=//p')
      pid=$(echo "$st" | sed -n 's/^pid=//p')
      now=$(date +%s)
      [ "$tokens" = 1 ] && [ -n "$pid" ] && grab_tokens "$tag"
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
        printf '%s\tdeadline\tstopped at %s lines\n' "$(date +%T)" "$n" >> "$REC/$tag.events.tsv"
        log "$tag: deadline reached, stopped at $n lines"
        break 2
      fi
      if [ -z "$pid" ] || [ $((now - t_change)) -ge "$STALL_S" ]; then
        if [ -n "$pid" ]; then kind=hang; A shell am force-stop "$PKG"; sleep 3; else kind=crash; fi
        A pull "$EXT/bench/$tag.jsonl" "$B/$tag.partial.jsonl" >/dev/null 2>&1
        grab_logcat "$tag" "${header_pid:-$pid}" >/dev/null
        A logcat -b crash -d >> "$REC/$tag.crash.log" 2>/dev/null
        read -r failed start_after <<<"$(ids_left "$B/$tag.partial.jsonl" "$limit")"
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
    log "$tag: $(cat "$REC/$tag.done" 2>/dev/null || echo "no done marker") ($(grep -c -E '"type": ?"utterance"' "$REC/$tag.jsonl" 2>/dev/null) rows)"
  fi
}

case "${1:-}" in
  freeze) cmd_freeze ;;
  freeze2) cmd_freeze2 ;;
  setup) cmd_setup ;;
  install-test2) cmd_install_test2 ;;
  compare) shift; [ $# -ge 1 ] || { sed -n 2,51p "$0"; exit 2; }; cmd_compare "$1" ;;
  decoder) shift; [ $# -ge 1 ] || { sed -n 2,51p "$0"; exit 2; }; cmd_decoder "$1" ;;
  freeze3) cmd_freeze3 ;;
  setup-min) cmd_setup_min ;;
  decoder2) shift; [ $# -ge 1 ] || { sed -n 2,51p "$0"; exit 2; }; cmd_decoder2 "$1" ;;
  cleanup) cmd_cleanup ;;
  run) shift; [ $# -ge 2 ] || { sed -n 2,51p "$0"; exit 2; }; cmd_run "$@" ;;
  check) shift; python3 "$ROOT/tools/asr-fix/check_run.py" "$REC/$1.jsonl" ${2:+--ref "$2"} ;;
  finish) cmd_finish ;;
  *) sed -n 2,51p "$0"; exit 2 ;;
esac
