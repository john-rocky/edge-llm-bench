#!/bin/bash
# Galaxy S26 driver of asr-sigbuf-v1 (docs/asr-sigbuf-v1.md): the litert-samples speech_recognition check
# builds of the TdtDecoder change. asr-npu-v1's driver (tools/asr-npu/run_npu_s26.sh) with this round's
# packages, files and runs; nothing here waits for a cool-down beyond the test's own ceiling wait.
#
#   run_sigbuf_s26.sh setup [npu]       # the three debug APKs (or the .npu one); models, WAVs and encoder outputs into
#                                       # their files dirs (run-as, sha256 read back on the phone); the bench + test APKs
#   run_sigbuf_s26.sh update-apks       # the main + fix bench / test APKs of $APKD over the installed packages
#                                       # (install -r: their files stay; the second form of the change)
#   run_sigbuf_s26.sh bench <tag>       # SigbufBenchTest: probe, am instrument, poll, probe, pull
#   run_sigbuf_s26.sh decoder <tag>     # SigbufDecoderTest on the four encoder outputs, three passes
#   run_sigbuf_s26.sh swap-npu-main     # the npu-main bench + test APKs over the .npu package (its files stay)
#   run_sigbuf_s26.sh identity <tag>    # one line: the run's windows against the run it pairs with (compare.py)
#   run_sigbuf_s26.sh cleanup [npu]     # uninstall the six packages (their files dirs go too), or only the .npu pair
#                                       # (the sitting that leaves the ja runs for a second hold); /data before / after
#   run_sigbuf_s26.sh finish            # put the stay-awake setting back
#   DRY=1 run_sigbuf_s26.sh ...         # print the adb commands, run none of them
#
# Packages (applicationIdSuffix of the check build, build_apks.sh):
#   .sigbufcheck.main  upstream main's TdtDecoder, LiteRT 2.3.0 + litert-gpu 2.3.0
#   .sigbufcheck.fix   the TdtDecoder change, the same LiteRT
#   .sigbufcheck.npu   LiteRT 2.2.0 + the Qualcomm runtime (qualcomm_runtime_v81, QAIRT 2.47.0 HTP libraries):
#                      the npu-fix set at setup, the npu-main set after swap-npu-main
# <bench tag>: <v3|ja>-<cpu|gpu>-<main|fix>-r<N>   S32's first 20 rows + the warm-up row W; v3 = parakeet-tdt-0.6b-v3
#                                                 (5 s i8 stateful), ja = parakeet-tdt_ctc-0.6b-ja (5 s i8); v3 runs
#                                                 wait for the cpufreq ceilings before every row (pace ceiling)
#              v3-npu-app-<fix|main>              the NPU entry (SM8850 file), S32's first 3 rows, 630 tokens per window
# <decoder tag>: dec-<cpu-f32|npu>-<fix|main>     TdtDecoder on b-tdt-cpu's encoder outputs (asr-npu-v1), 3 passes:
#                                                 cpu-f32 = the 5 s f32 stateful file on the CPU, npu = the SM8850 file
#
# Records go to results/raw/2026-10-22-asr-sigbuf-v1-s26-android/ (REC=... to override): per run <tag>.jsonl or
# <tag>.json, <tag>.log.txt (the test's logcat tap), <tag>.done, <tag>.cmd, <tag>.logcat.log (the app process's
# runtime lines logcat still holds at the end), <tag>.probe-before.json / .probe-after.json. A retake keeps the
# earlier files as <file>.attemptK.
#
# The phone is touched only under the S26 hold held by a keeper named asr_sigbuf_s26 (HOLD_OK=1 skips the
# check). No adb shell call leaves a background child on the phone: the tests start through `am instrument`
# without -w and the driver polls with short calls.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
DRY="${DRY:-0}"
SERIAL="${SERIAL:-RFGL80R6A6H}"
BASE=com.google.ai.edge.examples.asr.sigbufcheck
PKG_MAIN=$BASE.main
PKG_FIX=$BASE.fix
PKG_NPU=$BASE.npu
B="${B:-$ROOT/.build/asr-sigbuf}"
# The APK sets (build_apks.sh): apk/ = the first form of the change (9ca8adad), apk2/ = the second (035a442e).
APKD="${APKD:-$B/apk}"
REC="${REC:-$ROOT/results/raw/2026-10-22-asr-sigbuf-v1-s26-android}"
[ "$DRY" = 1 ] && REC="$B/dry-rec"  # a dry run writes its logs beside the build, never into the record
HOLD="$HOME/code/litertlm-convert/community_accel_work/s2_npu_sweep/.device_hold"
DT=/data/local/tmp/edge-llm-bench/asr-sigbuf
WARMUP_ID=1995-1836-0004
POLL_S="${POLL_S:-3}"
mkdir -p "$B" "$REC"

log() { echo "[asr-sigbuf $(date +%H:%M:%S)] $*" >&2; }

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
sys.exit(0 if d.get("script") == "asr_sigbuf_s26" else 1)
PY
}

need_hold() {
  hold_ok || { log "the S26 hold is not ours (asr_sigbuf_s26 with a live keeper): $(cat "$HOLD" 2>/dev/null)"; exit 4; }
}

dexopt_of() {  # package -> "<compiler filter>/<reason>" of its APK, from dumpsys package
  [ "$DRY" = 1 ] && { echo dry; return 0; }
  A shell "dumpsys package $1" | python3 -c '
import re, sys
m = re.search(r"\[status=([^\]]+)\]\s*\[reason=([^\]]+)\]", sys.stdin.read())
print((m.group(1) + "/" + m.group(2)) if m else "unknown")'
}

screen_state() {  # one line: wakefulness and the keyguard lines
  A shell "dumpsys power | grep -m1 mWakefulness=; dumpsys window | grep -m3 -E 'mKeyguardShowing|mAodShowing|mKeyguardGoingAway'" | tr -s ' \r\n' ' '
}

data_free() { A shell df -k /data | tail -1 | tr -s ' '; }

sha_of() {  # local name under models/ -> sha256 from models.lock.json
  python3 -c 'import json,sys; print({r["local"].split("/")[-1]: r["sha256"] for r in json.load(open(sys.argv[1]))}[sys.argv[2]])' \
    "$B/models/models.lock.json" "$1"
}

# local file under .build/asr-sigbuf/models -> path under the files dir -> packages
FILE_MAP="parakeet_tdt_0.6b_v3_5s_i8_stateful.tflite parakeet-tdt-0.6b-v3/model.tflite $PKG_MAIN,$PKG_FIX
tdt-tokenizer.json parakeet-tdt-0.6b-v3/tokenizer.json $PKG_MAIN,$PKG_FIX,$PKG_NPU
parakeet_tdt_ctc_0.6b_ja_5s_i8.tflite parakeet-tdt_ctc-0.6b-ja/model.tflite $PKG_MAIN,$PKG_FIX
ja-tokenizer.json parakeet-tdt_ctc-0.6b-ja/tokenizer.json $PKG_MAIN,$PKG_FIX
parakeet_tdt_0.6b_v3_5s_f32_stateful_Qualcomm_SM8850.tflite parakeet-tdt-0.6b-v3/model_npu.tflite $PKG_NPU
parakeet_tdt_0.6b_v3_5s_f32_stateful.tflite parakeet-tdt-0.6b-v3/model_f32.tflite $PKG_NPU"

cmd_setup() {  # [npu] -> all three packages, or only the .npu one (its files, then its bench build)
  need_hold
  local L="$REC/setup.log" f dst pkgs p want got n free_kb set sets inscope
  case "${1:-all}" in
    npu) sets="npu-fix"; inscope=" $PKG_NPU " ;;
    ja) sets="main fix"; inscope=" $PKG_MAIN $PKG_FIX " ;;   # the ja files only (the ja runs of a later hold)
    *) sets="main fix npu-fix"; inscope=" $PKG_MAIN $PKG_FIX $PKG_NPU " ;;
  esac
  for set in $sets; do
    [ -f "$APKD/$set/app-bench.apk" ] || { log "no APK set $set in $APKD: run build_apks.sh first"; exit 2; }
  done
  : > "$L"
  {
    echo "# setup ${1:-all} $(date '+%F %T %Z') (APK sets from $APKD)"
    for set in main fix npu-fix npu-main; do
      [ -f "$APKD/$set/SHA256SUMS" ] && { echo "## $set"; cat "$APKD/$set/SHA256SUMS" "$APKD/$set/APP_COMMIT"; }
    done
    echo "stay_on_while_plugged_in before: $(A shell settings get global stay_on_while_plugged_in | tr -d '\r')"
    echo "/data before: $(data_free)"
  } >> "$L"
  # /data must take every copy (about 6.1 GB in the three files dirs) plus the largest staging file (2.4 GB).
  free_kb=$(A shell df -k /data | tail -1 | awk '{print $4}')
  if [ "$DRY" != 1 ] && [ "${free_kb:-0}" -lt 12000000 ]; then log "/data has ${free_kb} kB free, below 12 GB"; exit 3; fi
  # 1. The debug builds (same packages and key as the bench builds): run-as can write their files dirs.
  for set in $sets; do
    A install -r -t "$APKD/$set/app-debug.apk" >&2 || { log "install $set debug app failed"; exit 2; }
    echo "installed $set/app-debug.apk (debuggable, for run-as)" >> "$L"
  done
  A shell svc power stayon usb
  A shell input keyevent KEYCODE_WAKEUP
  A shell mkdir -p "$DT"
  # 2. Each file pushed once to /data/local/tmp, copied into every package that needs it with run-as,
  # sha256 read back on the phone per copy against models.lock.json (the Hub's hash), the staging copy removed.
  echo "$FILE_MAP" | while read -r f dst pkgs; do
    targets=""
    for p in ${pkgs//,/ }; do case "$inscope" in *" $p "*) targets="$targets $p" ;; esac; done
    [ -n "$targets" ] || continue
    [ "${1:-all}" = ja ] && case "$f" in *ja*) ;; *) continue ;; esac
    want=$(sha_of "$f")
    A push "$B/models/$f" "$DT/$f" >&2 || { log "push $f failed"; exit 2; }
    for p in $targets; do
      A shell "run-as $p sh -c 'mkdir -p files/${dst%/*} && cat > files/$dst' < $DT/$f"
      got=$(A shell run-as "$p" sha256sum "files/$dst" | cut -c1-64)
      echo "model $f -> $p files/$dst sha256_local=$want sha256_phone=$got $([ "$got" = "$want" ] && echo OK || echo MISMATCH)" | tee -a "$L" >&2
      [ "$DRY" = 1 ] || [ "$got" = "$want" ] || exit 3
    done
    A shell rm -f "$DT/$f"
  done || exit $?
  # 3. The encoder outputs of asr-npu-v1's b-tdt-cpu (the decoder-only runs) into the .npu files dir.
  enc_files=""
  case "$inscope" in *" $PKG_NPU "*) enc_files=$(ls "$B"/enc/b-tdt-cpu.enc.w*.out0.f32) ;; esac
  for f in $enc_files; do
    want=$(shasum -a 256 "$f" | cut -c1-64)
    A push "$f" "$DT/${f##*/}" >/dev/null
    A shell "run-as $PKG_NPU sh -c 'mkdir -p files/sigbuf/enc && cat > files/sigbuf/enc/${f##*/}' < $DT/${f##*/}"
    got=$(A shell run-as "$PKG_NPU" sha256sum "files/sigbuf/enc/${f##*/}" | cut -c1-64)
    A shell rm -f "$DT/${f##*/}"
    echo "enc ${f##*/} -> $PKG_NPU sha256_local=$want sha256_phone=$got $([ "$got" = "$want" ] && echo OK || echo MISMATCH)" | tee -a "$L" >&2
    [ "$DRY" = 1 ] || [ "$got" = "$want" ] || exit 3
  done
  # 4. WAVs: one tar (manifest-device.tsv with every row + F20 + W), unpacked into every files dir.
  want=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["tar_sha256"])' "$B/set/test-clean-F20W.tar.json")
  A push "$B/set/test-clean-F20W.tar" "$DT/test-clean-F20W.tar" >&2
  got=$(A shell sha256sum "$DT/test-clean-F20W.tar" | cut -c1-64)
  for p in $inscope; do
    A shell "run-as $p sh -c 'mkdir -p files/sets/test-clean && cd files/sets/test-clean && tar -xf -' < $DT/test-clean-F20W.tar"
    n=$(A shell "run-as $p ls files/sets/test-clean | grep -c '\.wav\$'" | tr -d '\r')
    echo "wav set -> $p tar sha256_local=$want sha256_phone=$got wavs_unpacked=$n" | tee -a "$L" >&2
    if [ "$DRY" != 1 ] && { [ "$got" != "$want" ] || [ "$n" != 21 ]; }; then log "WAV set check failed ($p)"; exit 3; fi
  done
  A shell rm -rf "$DT"
  echo "staging removed ($DT); /data: $(data_free)" | tee -a "$L" >&2
  # 5. The bench builds over the debug ones (install -r: the data stays) and the test APKs.
  for set in $sets; do
    A install -r "$APKD/$set/app-bench.apk" >&2 || { log "install $set bench app failed"; exit 2; }
    A install -r -t "$APKD/$set/app-bench-androidTest.apk" >&2 || { log "install $set bench test failed"; exit 2; }
  done
  [ "$DRY" = 1 ] || echo npu-fix > "$B/npu-installed"
  {
    echo "installed the bench + bench test APKs of $sets over the debug ones (install -r: data kept)"
    for p in $inscope; do
      echo "$p pkgFlags: $(A shell "dumpsys package $p | grep -m2 -E 'pkgFlags=|privateFlags='" | tr -s ' \r\n' ' ')"
      echo "$p dexopt app: $(dexopt_of "$p"), test: $(dexopt_of "$p.test")"
    done
    echo "screen: $(screen_state)"
  } | tee -a "$L" >&2
  log "setup done"
}

cmd_update_apks() {  # the bench + test APKs of main and fix from $APKD over the installed .main / .fix (their files stay)
  need_hold
  local L="$REC/update-apks.log" set p
  for set in main fix; do
    [ -f "$APKD/$set/app-bench.apk" ] || { log "no APK set $set in $APKD"; exit 2; }
    A install -r "$APKD/$set/app-bench.apk" >&2 || { log "install $set bench app failed"; exit 2; }
    A install -r -t "$APKD/$set/app-bench-androidTest.apk" >&2 || { log "install $set bench test failed"; exit 2; }
  done
  {
    echo "# update-apks $(date '+%F %T %Z'): main + fix bench / bench test APKs from $APKD over the installed packages (install -r: data kept)"
    for set in main fix; do echo "## $set"; cat "$APKD/$set/SHA256SUMS" "$APKD/$set/APP_COMMIT"; done
    for p in $PKG_MAIN $PKG_FIX; do echo "$p dexopt app: $(dexopt_of "$p"), test: $(dexopt_of "$p.test")"; done
  } | tee -a "$L" >&2
}

cmd_swap_npu_main() {
  need_hold
  local L="$REC/setup.log"
  A install -r "$APKD/npu-main/app-bench.apk" >&2 || { log "install npu-main bench app failed"; exit 2; }
  A install -r -t "$APKD/npu-main/app-bench-androidTest.apk" >&2 || { log "install npu-main bench test failed"; exit 2; }
  [ "$DRY" = 1 ] || echo npu-main > "$B/npu-installed"
  {
    echo "# swap-npu-main $(date '+%F %T %Z'): npu-main/app-bench.apk + app-bench-androidTest.apk over $PKG_NPU (install -r: data kept)"
    echo "$PKG_NPU dexopt app: $(dexopt_of "$PKG_NPU"), test: $(dexopt_of "$PKG_NPU.test")"
    echo "files kept: $(A shell "run-as $PKG_NPU ls files 2>&1; ls -l /sdcard/Android/data/$PKG_NPU 2>&1 | head -1" | tr -s ' \r\n' ' ')"
  } | tee -a "$L" >&2
}

cmd_finish() {
  local before
  before=$(sed -n 's/^stay_on_while_plugged_in before: //p' "$REC/setup.log" 2>/dev/null | head -1)
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

grab_logcat() {  # tag pid -> append the app process's runtime / delegate / test lines logcat still holds
  local tag=$1 pid=$2 raw="$B/logcat-raw-$1.txt"
  [ "$DRY" = 1 ] && return 0
  A logcat -d -v threadtime > "$raw" 2>/dev/null
  python3 - "$raw" "$REC/$tag.logcat.log" "$pid" <<'PY'
import os, re, sys
raw, out, pid = sys.argv[1], sys.argv[2], sys.argv[3]
keep = re.compile(r"litert|LiteRt|tflite|TfLite|xnnpack|XNNPACK|delegate|Delegate|Dispatch|Accelerator|accelerator|"
                  r"NPU|npu|GPU|gpu|OpenCL|Adreno|Qnn|QNN|qnn|Htp|HTP|fastrpc|Sigbuf|TestRunner|"
                  r"AndroidRuntime|FATAL|Fatal signal|libc|DEBUG|tombstone")
skip = re.compile(r"QnnGraph_execute|QnnMem_register|QnnMem_deRegister|graphExecute|ExecuteGraph|Executing graph")
have = set(open(out).read().splitlines()) if os.path.exists(out) else set()
new, skipped = [], 0
for line in open(raw, errors="replace"):
    line = line.rstrip("\n")
    f = line.split()
    same = len(f) > 2 and f[2] == pid
    if same and skip.search(line):
        skipped += 1
        continue
    if (same and keep.search(line)) or re.search(r"AndroidRuntime|Fatal signal|DEBUG  |tombstone|crash_dump", line) \
            or ("com.google.ai.edge.examples.asr.sigbufcheck" in line and "ActivityManager" in line):
        if line not in have:
            new.append(line)
            have.add(line)
with open(out, "a") as f:
    for line in new:
        f.write(line + "\n")
    if skipped:
        f.write(f"# (per-run QNN lines of pid {pid} left out: {skipped}; the counts are in the test's own log tap)\n")
print(len(new))
PY
}

bench_spec() {  # tag (an f1- / f2- form prefix is ignored) -> "package model accelerator limit max_tokens pace warmup npu_set"
  local tag=${1#f[0-9]-} model accel arm
  case "$tag" in
    v3-npu-app-fix) echo "$PKG_NPU parakeet-tdt-0.6b-v3 npu 3 630 none - npu-fix"; return 0 ;;
    v3-npu-app-main) echo "$PKG_NPU parakeet-tdt-0.6b-v3 npu 3 630 none - npu-main"; return 0 ;;
  esac
  IFS=- read -r model accel arm _ <<<"$tag"
  case "$model" in v3) model=parakeet-tdt-0.6b-v3 ;; ja) model=parakeet-tdt_ctc-0.6b-ja ;; *) return 1 ;; esac
  case "$accel" in cpu | gpu) ;; *) return 1 ;; esac
  case "$arm" in main) arm=$PKG_MAIN ;; fix) arm=$PKG_FIX ;; *) return 1 ;; esac
  [[ "$tag" =~ -r[0-9]+$ ]] || return 1
  if [ "$model" = parakeet-tdt-0.6b-v3 ]; then
    echo "$arm $model $accel 20 2000 ceiling $WARMUP_ID -"
  else
    echo "$arm $model $accel 20 2000 none $WARMUP_ID -"
  fi
}

decoder_spec() {  # tag (an f1- / f2- form prefix is ignored) -> "accelerator model_file npu_set"
  case "${1#f[0-9]-}" in
    dec-cpu-f32-fix) echo "cpu parakeet-tdt-0.6b-v3/model_f32.tflite npu-fix" ;;
    dec-npu-fix) echo "npu - npu-fix" ;;
    dec-cpu-f32-main) echo "cpu parakeet-tdt-0.6b-v3/model_f32.tflite npu-main" ;;
    dec-npu-main) echo "npu - npu-main" ;;
    *) return 1 ;;
  esac
}

poll_done() {  # pkg tag stall_s -> waits for <tag>.done; prints the last pid seen; force-stops on stall / deadline
  local pkg=$1 tag=$2 stall=$3 ext="/sdcard/Android/data/$1/files/sigbuf" t0 st pid done_flag n="" now
  t0=$(date +%s)
  while :; do
    sleep "$POLL_S"
    st=$(A shell "[ -f $ext/$tag.done ] && echo done=1; echo pid=\$(pidof $pkg)" | tr -d '\r')
    done_flag=$(echo "$st" | sed -n 's/^done=//p'); pid=$(echo "$st" | sed -n 's/^pid=//p')
    [ -n "$pid" ] && n=$pid
    [ "$done_flag" = 1 ] && break
    now=$(date +%s)
    if [ -z "$pid" ] && [ $((now - t0)) -gt 25 ]; then log "$tag: the process is gone without a done marker"; break; fi
    if [ $((now - t0)) -gt "$stall" ]; then log "$tag: no done marker after ${stall}s, stopped"; A shell am force-stop "$pkg"; break; fi
    if [ -n "${DEADLINE:-}" ] && [ "$now" -ge "$DEADLINE" ]; then log "$tag: the sitting's end reached, stopped"; A shell am force-stop "$pkg"; break; fi
  done
  echo "$n"
}

check_npu_set() {  # wanted set -> exit 2 unless the .npu package carries it
  local have
  [ "$DRY" = 1 ] && return 0
  have=$(cat "$B/npu-installed" 2>/dev/null)
  [ "$have" = "$1" ] || { log "the .npu package carries ${have:-nothing}, this run needs $1"; exit 2; }
}

cmd_bench() {
  local tag=$1 spec pkg model accel limit maxtok pace warmup nset am pid ext extra=""
  spec=$(bench_spec "$tag") || { log "unknown bench tag $tag"; exit 2; }
  read -r pkg model accel limit maxtok pace warmup nset <<<"$spec"
  need_hold
  [ "$nset" != - ] && check_npu_set "$nset"
  keep_earlier "$tag"
  ext="/sdcard/Android/data/$pkg/files/sigbuf"
  [ "$warmup" != - ] && extra="-e warmup_id $warmup"
  "$HERE/probe.sh" before > "$REC/$tag.probe-before.json"
  echo "# $tag $(date '+%F %T %Z')" >> "$REC/$tag.cmd"
  echo "dexopt: app $(dexopt_of "$pkg"), test $(dexopt_of "$pkg.test"); screen: $(screen_state)" >> "$REC/$tag.cmd"
  A shell "rm -f $ext/$tag.*"
  A logcat -c
  am="am instrument -r -e class com.google.ai.edge.examples.asr.SigbufBenchTest -e model $model -e accelerator $accel -e manifest /data/user/0/$pkg/files/sets/test-clean/manifest-device.tsv -e every 32 -e limit $limit -e max_tokens $maxtok -e pace $pace $extra -e foreground front -e tag $tag $pkg.test/androidx.test.runner.AndroidJUnitRunner"
  echo "$(date '+%T') adb -s $SERIAL shell $am" >> "$REC/$tag.cmd"
  log "bench $tag ($pkg, $model, $accel, limit $limit, max_tokens $maxtok, pace $pace)"
  A shell "$am" > "$B/$tag.instrument.txt"
  [ "$DRY" = 1 ] && return 0
  pid=$(poll_done "$pkg" "$tag" 900)
  sleep 1
  for f in jsonl log.txt done; do A pull "$ext/$tag.$f" "$REC/$tag.$f" >/dev/null 2>&1; done
  grab_logcat "$tag" "${pid:-x}" >/dev/null
  A logcat -b crash -d > "$REC/$tag.crash.log" 2>/dev/null
  [ -s "$REC/$tag.crash.log" ] || rm -f "$REC/$tag.crash.log"
  "$HERE/probe.sh" after > "$REC/$tag.probe-after.json"
  log "$tag: $(cat "$REC/$tag.done" 2>/dev/null || echo 'no done marker'); $(grep -c '"type": "utterance"' "$REC/$tag.jsonl" 2>/dev/null) rows; tap: $(tail -1 "$REC/$tag.jsonl" 2>/dev/null | python3 -c 'import json,sys; print(json.loads(sys.stdin.read()).get("log"))' 2>/dev/null)"
}

cmd_decoder() {
  local tag=$1 spec accel mfile nset am pid ext inputs extra="" i
  spec=$(decoder_spec "$tag") || { log "unknown decoder tag $tag"; exit 2; }
  read -r accel mfile nset <<<"$spec"
  need_hold
  check_npu_set "$nset"
  keep_earlier "$tag"
  ext="/sdcard/Android/data/$PKG_NPU/files/sigbuf"
  inputs=""
  for i in 0 1 2 3; do inputs="$inputs${inputs:+,}sigbuf/enc/b-tdt-cpu.enc.w$i.out0.f32"; done
  [ "$mfile" != - ] && extra="-e model_file $mfile"
  "$HERE/probe.sh" before > "$REC/$tag.probe-before.json"
  echo "# $tag $(date '+%F %T %Z')" >> "$REC/$tag.cmd"
  A shell "rm -f $ext/$tag.*"
  A logcat -c
  am="am instrument -r -e class com.google.ai.edge.examples.asr.SigbufDecoderTest -e model parakeet-tdt-0.6b-v3 -e accelerator $accel $extra -e enc_inputs $inputs -e passes 3 -e run_encode true -e foreground front -e tag $tag $PKG_NPU.test/androidx.test.runner.AndroidJUnitRunner"
  echo "$(date '+%T') adb -s $SERIAL shell $am" >> "$REC/$tag.cmd"
  log "decoder $tag ($accel, model_file $mfile, $nset)"
  A shell "$am" > "$B/$tag.instrument.txt"
  [ "$DRY" = 1 ] && return 0
  pid=$(poll_done "$PKG_NPU" "$tag" 300)
  sleep 1
  for f in json log.txt done; do A pull "$ext/$tag.$f" "$REC/$tag.$f" >/dev/null 2>&1; done
  [ -n "$pid" ] || pid=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["device"]["pid"])' "$REC/$tag.json" 2>/dev/null)
  grab_logcat "$tag" "${pid:-x}" >/dev/null
  A logcat -b crash -d > "$REC/$tag.crash.log" 2>/dev/null
  [ -s "$REC/$tag.crash.log" ] || rm -f "$REC/$tag.crash.log"
  "$HERE/probe.sh" after > "$REC/$tag.probe-after.json"
  log "$tag: $(cat "$REC/$tag.done" 2>/dev/null || echo 'no done marker'); tap: $(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("log"))' "$REC/$tag.json" 2>/dev/null)"
}

cmd_cleanup() {  # [npu] -> uninstall the six packages (their files dirs with about 6.1 GB go too), or only the .npu pair
  need_hold
  local L="$REC/cleanup.log" p pkgs
  if [ "${1:-all}" = npu ]; then
    pkgs="$PKG_NPU.test $PKG_NPU"
  else
    pkgs="$PKG_MAIN.test $PKG_MAIN $PKG_FIX.test $PKG_FIX $PKG_NPU.test $PKG_NPU"
  fi
  {
    echo "# cleanup ${1:-all} $(date '+%F %T %Z')"
    echo "/data before: $(data_free)"
    echo "packages before: $(A shell "pm list packages | grep -E '$BASE'" | tr -d '\r' | tr '\n' ' ')"
    for p in $pkgs; do
      echo "uninstall $p: $(A uninstall "$p" 2>&1 | tr -d '\r')"
    done
    echo "packages after: $(A shell "pm list packages | grep -E '$BASE'" | tr -d '\r' | tr '\n' ' ')"
    echo "/data after: $(data_free)"
  } | tee -a "$L" >&2
  [ "$DRY" = 1 ] || rm -f "$B/npu-installed"
}

case "${1:-}" in
  setup) shift; cmd_setup "${1:-all}" ;;
  update-apks) cmd_update_apks ;;
  bench) shift; [ $# -ge 1 ] || { sed -n 2,40p "$0"; exit 2; }; cmd_bench "$1" ;;
  decoder) shift; [ $# -ge 1 ] || { sed -n 2,40p "$0"; exit 2; }; cmd_decoder "$1" ;;
  swap-npu-main) cmd_swap_npu_main ;;
  identity) shift; python3 "$HERE/compare.py" pair "$REC" "$1" ;;
  cleanup) shift; cmd_cleanup "${1:-all}" ;;
  finish) cmd_finish ;;
  *) sed -n 2,40p "$0"; exit 2 ;;
esac
