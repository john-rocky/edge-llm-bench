#!/usr/bin/env bash
# Mac-side driver for the asr-sherpa-v1 A1 arm on the Galaxy S26: sherpa-onnx v1.13.8
# (android-aarch64-termux-static), parakeet-tdt-0.6b-v3 int8, CPU, 4 threads, greedy search.
# Every adb call is short: the measured process runs on the phone under nohup
# (device_run.sh) and is polled through its done marker. adb steps refuse to run unless the
# S26 hold names this lane's keeper. DRY=1 prints the adb commands instead of running them.
#
#   tools/asr-sherpa/run_sherpa_s26.sh <step> [args]
#
#   stage                         Mac only: lists (W + S4, smoke, warm), the S4 WAV tar, expected sha256s
#   push                          binaries, model, device_run.sh, lists, WAVs; sha256 read back -> SHA256SUMS
#   help <binary>                 the binary's --help without lib/ (raw error) and with it -> <record>/<binary>.{nolib,help}.txt
#   version                       bin/sherpa-onnx-version -> <record>/sherpa-onnx-version.txt
#   cool [max_s]                  wait for battery <= 36.0 C and Thermal Status 0 (default max 900 s)
#   probe <label>                 probe.sh -> <record>/probe-<label>.json
#   start <tag> <list> <binary>   device_run.sh under nohup with the A1 flags; writes <record>/<tag>.cmd
#   wait <tag> [max_s]            poll the done marker every 15 s (default max 1500 s)
#   pull <tag>                    the run's files from the phone into the record dir
#   stage-full / push-full        the full test-clean list and WAV tar (only when the hold has time)
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
repo=$(cd "$here/../.." && pwd)
SERIAL=${SERIAL:-RFGL80R6A6H}
DRY=${DRY:-0}
P=/data/local/tmp/edge-llm-bench/asr-sherpa
MODEL=sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8
REC=${REC:-$repo/results/raw/2026-10-19-asr-sherpa-v1-s26-android}
SET=$repo/.build/omni-eval/sets/librispeech-test-clean
SH=$repo/.build/sherpa-onnx/extract/sherpa-onnx-v1.13.8-android-aarch64-termux-static.tar.bz2/sherpa-onnx-v1.13.8-android-aarch64-termux-static/bin
MD=$repo/.build/sherpa-onnx/extract/$MODEL.tar.bz2/$MODEL
CXX=$repo/.build/sherpa-onnx/extract/cxx-runtime/libc++_shared.so  # fetch.sh with NDK=; LOCK.json cxx_runtime
STAGE=$repo/.build/asr-sherpa/stage
HOLD=${HOLD:-$HOME/code/litertlm-convert/community_accel_work/s2_npu_sweep/.device_hold}
HOLD_SCRIPT=asr_sherpa_s26
BINS="sherpa-onnx-offline-parallel sherpa-onnx-offline sherpa-onnx-version"
MODEL_FILES="encoder.int8.onnx decoder.int8.onnx joiner.int8.onnx tokens.txt"
W_ID=1995-1836-0004  # manifest.tsv row 1, outside S4: the binary's warm-up file
A1_FLAGS="--encoder=$P/models/$MODEL/encoder.int8.onnx --decoder=$P/models/$MODEL/decoder.int8.onnx --joiner=$P/models/$MODEL/joiner.int8.onnx --tokens=$P/models/$MODEL/tokens.txt --model-type=nemo_transducer --num-threads=4 --decoding-method=greedy_search"
PARALLEL_FLAGS="--batch-size=1 --nj=1"

say() { echo "$(date '+%H:%M:%S') $*"; }
log() { mkdir -p "$REC"; say "$*" | tee -a "$REC/progress.log"; }

adbx() {  # adb on the S26 only, never another phone
  if [ "$DRY" = 1 ]; then echo "+ adb -s $SERIAL $*"; else adb -s "$SERIAL" "$@"; fi
}

need_hold() {
  [ "$DRY" = 1 ] && return 0
  local who
  who=$(python3 -I -c 'import json, sys
try:
    d = json.load(open(sys.argv[1]))
except Exception:
    d = {}
print(d.get("script", ""))' "$HOLD")
  if [ "$who" != "$HOLD_SCRIPT" ]; then
    echo "the S26 hold is not this lane's (holder: '${who:-none}'): take it with queue_cli.py wait first" >&2
    exit 4
  fi
}

list_line() { echo "$1 $P/sets/$2/$1.wav"; }

stage() {
  [ "$(sed -n 2p "$SET/manifest.tsv" | cut -f1)" = "$W_ID" ] || { echo "manifest row 1 is not $W_ID" >&2; exit 1; }
  rm -rf "$STAGE"; mkdir -p "$STAGE/lists" "$STAGE/tar/S4" "$STAGE/tar/W"
  ids=$(cut -f1 "$SET/manifest-S4.tsv")
  {
    list_line "$W_ID" W
    for id in $ids; do list_line "$id" S4; done
  } > "$STAGE/lists/S4.scp"
  head -n 4 "$STAGE/lists/S4.scp" > "$STAGE/lists/smoke.scp"
  sed -n 2,4p "$STAGE/lists/S4.scp" > "$STAGE/lists/smoke-offline.scp"
  head -n 1 "$STAGE/lists/S4.scp" > "$STAGE/lists/warm.scp"
  for id in $ids; do cp -c "$SET/$id.wav" "$STAGE/tar/S4/" 2>/dev/null || cp "$SET/$id.wav" "$STAGE/tar/S4/"; done
  cp "$SET/$W_ID.wav" "$STAGE/tar/W/"
  (cd "$STAGE/tar" && COPYFILE_DISABLE=1 tar --format ustar --no-mac-metadata --no-xattrs -cf "$STAGE/S4.tar" W S4)
  {
    for f in $BINS; do echo "$(shasum -a 256 "$SH/$f" | cut -d' ' -f1)  bin/$f"; done
    for f in $MODEL_FILES; do echo "$(shasum -a 256 "$MD/$f" | cut -d' ' -f1)  models/$MODEL/$f"; done
    echo "$(shasum -a 256 "$CXX" | cut -d' ' -f1)  lib/libc++_shared.so"
    echo "$(shasum -a 256 "$here/device_run.sh" | cut -d' ' -f1)  device_run.sh"
    for f in S4 smoke smoke-offline warm; do echo "$(shasum -a 256 "$STAGE/lists/$f.scp" | cut -d' ' -f1)  lists/$f.scp"; done
    echo "$(shasum -a 256 "$SET/$W_ID.wav" | cut -d' ' -f1)  sets/W/$W_ID.wav"
  } > "$STAGE/expected.sha256"
  chain=$(python3 -I -c 'import json, sys; print(json.load(open(sys.argv[1]))["wav_sha256_chain"])' "$SET/SET-S4.json")
  echo "$chain" > "$STAGE/S4.chain"
  say "staged: $(wc -l < "$STAGE/lists/S4.scp" | tr -d ' ') lines in S4.scp (W + S4), tar $(tar -tf "$STAGE/S4.tar" | grep -c '\.wav$') wav, $(du -h "$STAGE/S4.tar" | cut -f1), chain $chain"
  if tar -tf "$STAGE/S4.tar" | grep -q '/\._'; then echo "AppleDouble entries in S4.tar" >&2; exit 1; fi
}

stage_full() {
  mkdir -p "$STAGE/lists" "$STAGE/tar-full/full"
  {
    list_line "$W_ID" W
    cut -f1 "$SET/manifest.tsv" | while read -r id; do list_line "$id" full; done
  } > "$STAGE/lists/full.scp"
  cut -f1 "$SET/manifest.tsv" | while read -r id; do cp -c "$SET/$id.wav" "$STAGE/tar-full/full/" 2>/dev/null || cp "$SET/$id.wav" "$STAGE/tar-full/full/"; done
  (cd "$STAGE/tar-full" && COPYFILE_DISABLE=1 tar --format ustar --no-mac-metadata --no-xattrs -cf "$STAGE/full.tar" full)
  echo "$(shasum -a 256 "$STAGE/lists/full.scp" | cut -d' ' -f1)  lists/full.scp" > "$STAGE/expected-full.sha256"
  python3 -I -c 'import json, sys; print(json.load(open(sys.argv[1]))["full"]["wav_sha256_chain"])' "$SET/SET-S4.json" > "$STAGE/full.chain"
  say "staged full: $(wc -l < "$STAGE/lists/full.scp" | tr -d ' ') lines (W + 2620), $(du -h "$STAGE/full.tar" | cut -f1)"
}

verify() {  # <expected file> <chain file> <list name> -> append to SHA256SUMS, exit 1 on any mismatch
  local expected=$1 chainf=$2 list=$3 got bad=0 dev_chain
  got=$(adbx shell "cd $P && sha256sum $(cut -d' ' -f3 "$expected" | tr '\n' ' ')")
  [ "$DRY" = 1 ] && { echo "$got"; return 0; }
  mkdir -p "$REC"
  while read -r sha path; do
    dev=$(echo "$got" | awk -v p="$path" '$2 == p {print $1}')
    echo "$dev  $path" >> "$REC/SHA256SUMS"
    if [ "$dev" != "$sha" ]; then echo "MISMATCH $path: phone ${dev:-none} != Mac $sha" >&2; bad=1; fi
  done < "$expected"
  dev_chain=$(adbx shell "cd $P && tail -n +2 lists/$list | while read id p; do cat \$p; done | sha256sum" | cut -d' ' -f1)
  echo "# $dev_chain  sets: the WAVs of lists/$list after its first line (W), concatenated in list order (phone); SET-S4.json chain $(cat "$chainf")" >> "$REC/SHA256SUMS"
  if [ "$dev_chain" != "$(cat "$chainf")" ]; then echo "MISMATCH chain $list: phone $dev_chain != $(cat "$chainf")" >&2; bad=1; fi
  [ $bad = 0 ] && log "sha256 read back on the phone: all match ($(wc -l < "$expected" | tr -d ' ') files + the $list WAV chain $dev_chain)"
  return $bad
}

push() {
  need_hold
  [ -f "$STAGE/S4.tar" ] || { echo "run stage first" >&2; exit 1; }
  adbx shell "mkdir -p $P/bin $P/lib $P/models/$MODEL $P/sets $P/lists $P/runs"
  for f in $BINS; do adbx push "$SH/$f" "$P/bin/$f"; done
  adbx push "$CXX" "$P/lib/libc++_shared.so"
  for f in $MODEL_FILES; do adbx push "$MD/$f" "$P/models/$MODEL/$f"; done
  adbx push "$here/device_run.sh" "$P/device_run.sh"
  for f in S4 smoke smoke-offline warm; do adbx push "$STAGE/lists/$f.scp" "$P/lists/$f.scp"; done
  adbx push "$STAGE/S4.tar" "$P/sets/S4.tar"
  adbx shell "cd $P/sets && rm -rf S4 W && tar -xf S4.tar && rm S4.tar && chmod 755 $P/bin/*"
  rm -f "$REC/SHA256SUMS"
  verify "$STAGE/expected.sha256" "$STAGE/S4.chain" S4.scp
}

push_full() {
  need_hold
  adbx push "$STAGE/lists/full.scp" "$P/lists/full.scp"
  adbx push "$STAGE/full.tar" "$P/sets/full.tar"
  adbx shell "cd $P/sets && rm -rf full && tar -xf full.tar && rm full.tar"
  verify "$STAGE/expected-full.sha256" "$STAGE/full.chain" full.scp
}

help_of() {  # the binary's --help without the C++ runtime (raw error), then with it
  need_hold
  mkdir -p "$REC"
  # A copy in a dir with no ../lib: the binary's RUNPATH $ORIGIN/../lib would find lib/ from bin/.
  adbx shell "mkdir -p $P/nolib-test/bin && cp $P/bin/$1 $P/nolib-test/bin/ && cd $P/nolib-test && echo '\$ env -u LD_LIBRARY_PATH nolib-test/bin/$1 --help (no libc++_shared.so in \$ORIGIN, \$ORIGIN/../lib or LD_LIBRARY_PATH)'; env -u LD_LIBRARY_PATH ./bin/$1 --help 2>&1 | head -n 5; echo exit=\$?; cd $P && rm -rf $P/nolib-test" > "$REC/$1.nolib.txt" || true
  adbx shell "cd $P && LD_LIBRARY_PATH=$P/lib bin/$1 --help 2>&1; echo exit=\$?" > "$REC/$1.help.txt" || true
  say "help $1: without lib/ $(head -n 2 "$REC/$1.nolib.txt" | tr '\n' ' ' | cut -c1-160) | with lib/: $(wc -l < "$REC/$1.help.txt" | tr -d ' ') lines"
}

version() {
  need_hold
  mkdir -p "$REC"
  adbx shell "cd $P && LD_LIBRARY_PATH=$P/lib bin/sherpa-onnx-version 2>&1; echo exit=\$?" > "$REC/sherpa-onnx-version.txt" || true
  say "version: $(tr '\n' ' ' < "$REC/sherpa-onnx-version.txt" | cut -c1-200)"
}

clocks() {  # CPUCAP_WAIT > 0: then wait up to that long for every policy's scaling_max_freq = cpuinfo_max_freq
  local max=${CPUCAP_WAIT:-0} waited=0 out
  [ "$max" -gt 0 ] || return 0
  while :; do
    out=$(adbx shell 'for d in /sys/devices/system/cpu/cpufreq/policy*; do echo "${d##*/} $(cat $d/scaling_max_freq) $(cat $d/cpuinfo_max_freq)"; done' | tr -d '\r')
    if ! echo "$out" | awk '$2 != $3 {bad = 1} END {exit bad}'; then :; else
      log "clocks: full after ${waited}s ($(echo "$out" | tr '\n' ' '))"; return 0
    fi
    if [ $waited -ge "$max" ]; then
      log "clocks: still capped after ${waited}s, started anyway (cpu-capped-at-start: $(echo "$out" | tr '\n' ' '))"; return 0
    fi
    sleep 10; waited=$((waited + 10))
  done
}

cool() {
  need_hold
  local max=${1:-900} waited=0 out t s
  while :; do
    out=$(adbx shell "dumpsys battery | grep -m 1 temperature; dumpsys thermalservice | grep -m 1 'Thermal Status'")
    [ "$DRY" = 1 ] && { echo "$out"; return 0; }
    t=$(echo "$out" | sed -n 's/.*temperature: *\([0-9-]*\).*/\1/p')
    s=$(echo "$out" | sed -n 's/.*Thermal Status: *\([0-9]*\).*/\1/p')
    if [ -n "$t" ] && [ "$t" -le 360 ] && [ "$s" = 0 ]; then
      log "cool: waited ${waited}s, battery $t (0.1 C), Thermal Status $s"
      clocks; return 0
    fi
    if [ $waited -ge "$max" ]; then
      log "cool: gave up after ${waited}s (started anyway), battery $t (0.1 C), Thermal Status $s"; return 0
    fi
    sleep 10; waited=$((waited + 10))
  done
}

probe() {
  need_hold
  mkdir -p "$REC"
  if [ "$DRY" = 1 ]; then echo "+ $here/probe.sh $1 $SERIAL > $REC/probe-$1.json"; return 0; fi
  "$here/probe.sh" "$1" "$SERIAL" > "$REC/probe-$1.json"
  python3 -I - "$REC/probe-$1.json" <<'EOF' | tee -a "$REC/progress.log"
import json, sys
d = json.load(open(sys.argv[1]))
pol = " ".join(f"{k}={v['scaling_max_freq_kHz']}/{v['cpuinfo_max_freq_kHz']}" for k, v in d["policies"].items())
print(f"probe {d['label']}: battery {d['battery']['temperature_C']} C, Thermal Status {d['thermal_status']}, "
      f"MemAvailable {d['mem_kB'].get('MemAvailable')} kB, scaling/cpuinfo max kHz {pol}, screen {d.get('wakefulness')}")
EOF
}

start() {
  need_hold
  local tag=$1 list=$2 bin=$3 flags=$A1_FLAGS cmdline
  case $bin in *-parallel) flags="$flags $PARALLEL_FLAGS" ;; esac
  cmdline="cd $P && nohup sh device_run.sh $tag lists/$list bin/$bin $flags > runs/$tag.runner.log 2>&1 < /dev/null &"
  mkdir -p "$REC"
  {
    echo "### phone: Galaxy S26 $SERIAL, cwd $P"
    echo "### launch (adb shell): $cmdline"
    case $bin in
      *-parallel) echo "### CMD: LD_LIBRARY_PATH=$P/lib bin/$bin $flags --wav-scp=$P/runs/$tag.scp" ;;
      *) echo "### CMD: LD_LIBRARY_PATH=$P/lib bin/$bin $flags <the paths of $P/runs/$tag.scp, one batch>" ;;
    esac
  } > "$REC/$tag.cmd"
  if [ "$DRY" = 1 ]; then echo "+ gtimeout 30 adb -s $SERIAL shell \"$cmdline\""; return 0; fi
  gtimeout 30 adb -s "$SERIAL" shell "$cmdline" || log "start: the adb client did not return in 30 s (the run is under nohup; checking)"
  sleep 2
  log "start $tag: $(adbx shell "head -n 1 $P/runs/$tag.runner.log" | tr -d '\r')"
}

wait_done() {
  need_hold
  local tag=$1 max=${2:-1500} waited=0 out
  if [ "$DRY" = 1 ]; then adbx shell "cat $P/runs/$tag.done"; return 0; fi
  while :; do
    out=$(adb -s "$SERIAL" shell "cat $P/runs/$tag.done 2>/dev/null; cat $P/runs/$tag.hangs 2>/dev/null; true" 2>&1 | tr -d '\r') || out="adb error: $out"
    case $out in
      *attempts=*) log "DONE $tag: $(echo "$out" | tail -n 1) (polled ${waited}s)"; return 0 ;;
      "adb error"*|*"no devices"*|*"not found"*) log "wait $tag: $out" ;;
    esac
    if [ $waited -ge "$max" ]; then log "WAIT-TIMEOUT $tag after ${waited}s"; return 3; fi
    sleep 15; waited=$((waited + 15))
  done
}

pull() {
  need_hold
  local tag=$1 f
  mkdir -p "$REC"
  for f in $(adbx shell "ls $P/runs" | tr -d '\r' | grep -E "^$tag(\.|$)"); do
    adbx pull "$P/runs/$f" "$REC/$f" > /dev/null
  done
  say "pulled $tag: $(ls "$REC" | grep -c -E "^$tag\.") files"
}

step=${1:?step: stage|push|help|version|cool|probe|start|wait|pull|stage-full|push-full}
shift
case $step in
  stage) stage ;;
  stage-full) stage_full ;;
  push) push ;;
  push-full) push_full ;;
  help) help_of "$@" ;;
  version) version ;;
  cool) cool "$@" ;;
  probe) probe "$@" ;;
  start) start "$@" ;;
  wait) wait_done "$@" ;;
  pull) pull "$@" ;;
  *) echo "unknown step $step" >&2; exit 2 ;;
esac
