#!/usr/bin/env bash
# Mac-side driver for the asr-qnn-v1 A2 arm on the Galaxy S26 (docs/asr-qnn-v1.md): sherpa-onnx v1.13.8 built
# with QNN (tools/asr-qnn/build.sh), k2-fsa's parakeet-ctc-0.6b SM8850 context binary (30 s window), QAIRT
# 2.40.0.251030's HTP libraries. Every adb call is short: the measured process runs on the phone under nohup
# (device_run.sh) and is polled through its done marker. adb steps refuse to run unless the S26 hold names
# this lane's keeper. DRY=1 prints the adb commands instead of running them.
#
#   tools/asr-qnn/run_qnn_s26.sh <step> [args]
#
#   stage                          Mac only: lists, the W + S4 WAV tar, expected sha256s
#   push                           binaries, libraries, model, device_run.sh, lists, WAVs; sha256 read back
#   help                           the CLI's and the driver's --help -> <record>/*.help.txt
#   version                        bin/sherpa-onnx-version -> <record>/sherpa-onnx-version.txt
#   debuginfo                      sherpa-onnx-offline --debug=1 on one WAV (QNN backend build id, window, tensors)
#   cool [max_s]                   wait for battery <= 36.0 C and Thermal Status 0 (default max 900 s), then
#                                  CPUCAP_WAIT s for every ceiling (default 300)
#   probe <label>                  probe.sh -> <record>/probe-<label>.json
#   driver <tag> <list> <pace> <load_label>   device_run.sh <tag> driver (lists/<list>), writes <record>/<tag>.cmd
#   cli <tag> <list>               device_run.sh <tag> cli (sherpa-onnx-offline-parallel --wav-scp=lists/<list>)
#   wait <tag> [max_s]             poll the done marker every 10 s (default max 1500 s)
#   pull <tag>                     the run's files from the phone into the record dir
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
repo=$(cd "$here/../.." && pwd)
SERIAL=${SERIAL:-RFGL80R6A6H}
DRY=${DRY:-0}
P=/data/local/tmp/edge-llm-bench/asr-qnn
MODEL=sherpa-onnx-qnn-SM8850-binary-parakeet-ctc-0.6b-30s
B=${B:-$repo/.build/asr-qnn}
REC=${REC:-$repo/results/raw/2026-10-19-asr-qnn-v1-s26-android}
SET=${SET:-$HOME/code/edge-llm-bench-wt-asr-sherpa/.build/omni-eval/sets/librispeech-test-clean}  # r1's WAVs
SB=$B/src/sherpa-onnx/build-android-arm64-v8a/install
QNN=$B/extract/qairt/qairt/2.40.0.251030
MD=$B/extract/model/$MODEL
DRV=$B/build-out/asr-qnn-burst-driver
STAGE=$B/stage
HOLD=${HOLD:-$HOME/code/litertlm-convert/community_accel_work/s2_npu_sweep/.device_hold}
HOLD_SCRIPT=asr_qnn_s26
BINS="sherpa-onnx-offline-parallel sherpa-onnx-offline sherpa-onnx-version"
QNN_LIBS="aarch64-android/libQnnHtp.so aarch64-android/libQnnHtpPrepare.so aarch64-android/libQnnSystem.so aarch64-android/libQnnHtpV81Stub.so hexagon-v81/unsigned/libQnnHtpV81Skel.so"
MODEL_FILES="model.bin tokens.txt info.txt"
W_ID=1995-1836-0004  # manifest row 1, outside S4 / S32: the warm-up file
QNN_FLAGS="--provider=qnn --tokens=$P/models/$MODEL/tokens.txt --nemo-ctc.qnn-backend-lib=$P/lib/libQnnHtp.so --nemo-ctc.qnn-system-lib=$P/lib/libQnnSystem.so --nemo-ctc.qnn-context-binary=$P/models/$MODEL/model.bin --num-threads=4 --decoding-method=greedy_search"
PARALLEL_FLAGS="--batch-size=1 --nj=1"
# quant-per-arm-rule: how k2-fsa made the context binary (LOCK.json model.export_recipe); to_jsonl.py writes the same line
QUANT="QNN post-training quantization with calibration inputs: weights 8-bit (qnn-onnx-converter default), activations 16-bit, bias 32-bit (k2-fsa export-parakeet-ctc-qnn 9961aee6); context binary for SM8850 / HTP v81 made with QAIRT 2.40.0.251030"

say() { echo "$(date '+%H:%M:%S') $*"; }
log() { mkdir -p "$REC"; say "$*" | tee -a "$REC/progress.log"; }

adbx() {  # adb on the S26 only, never another phone
  if [ "$DRY" = 1 ]; then echo "+ adb -s $SERIAL $*" >&2; else adb -s "$SERIAL" "$@"; fi
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
    echo "the S26 hold is not this lane's (holder: '${who:-none}'): take it with hold_keeper.sh first" >&2
    exit 4
  fi
}

stage() {
  [ "$(sed -n 2p "$SET/manifest.tsv" | cut -f1)" = "$W_ID" ] || { echo "manifest row 1 is not $W_ID" >&2; exit 1; }
  for f in $BINS; do [ -x "$SB/bin/$f" ] || { echo "no $SB/bin/$f: run build.sh" >&2; exit 1; }; done
  [ -x "$DRV" ] || { echo "no $DRV: run build.sh driver" >&2; exit 1; }
  rm -rf "$STAGE"; mkdir -p "$STAGE/lists" "$STAGE/tar/S4" "$STAGE/tar/W"
  python3 -I - "$SET" "$STAGE" "$P" "$W_ID" <<'EOF'
import hashlib, json, sys
src, stage, p, w_id = sys.argv[1:5]
full = [json.loads(l) for l in open(f"{src}/manifest.jsonl")]
s4 = [json.loads(l) for l in open(f"{src}/manifest-S4.jsonl")]
s32 = full[::32]  # the burst set (asr LANE §0 amendment 5: S16 -> S32, every other S16 row)
assert full[1]["id"] == w_id and len(s4) == 655 and len(s32) == 82
assert {r["id"] for r in s32} <= {r["id"] for r in s4}
w = full[1]
wav = lambda sub, r: f"{p}/sets/{sub}/{r['id']}.wav"
# the CLI's wav-scp: "id path", W first (the binary's untimed warm-up and first timed file)
with open(f"{stage}/lists/S4.scp", "w") as f:
    f.write(f"{w_id} {wav('W', w)}\n")
    for r in s4:
        f.write(f"{r['id']} {wav('S4', r)}\n")
# the driver's lists: "id<TAB>path<TAB>seconds" (seconds_written, as asr-sherpa-v1 / asr-burst-v1)
def tsv(name, rows):
    with open(f"{stage}/lists/{name}.tsv", "w") as f:
        for r in rows:
            f.write(f"{r['id']}\t{wav('S4', r)}\t{r['seconds_written']}\n")
tsv("S32", s32)
tsv("smoke3", [s32[0], s32[41], s32[81]])   # 34.955 s (past the 30 s window), a middle and a short one
tsv("warm1", [s32[41]])
with open(f"{stage}/W.seconds", "w") as f:
    f.write(f"{w['seconds_written']}\n")
with open(f"{stage}/ids-S4.txt", "w") as f:
    f.write("".join(r["id"] + "\n" for r in s4))
def chain(rows):
    h = hashlib.sha256()
    for r in rows:
        h.update(open(f"{src}/{r['id']}.wav", "rb").read())
    return h.hexdigest()
s4_set = json.load(open(f"{src}/SET-S4.json"))
assert chain(s4) == s4_set["wav_sha256_chain"], "S4 chain differs from SET-S4.json"
over = lambda rows: [[r["id"], r["seconds_written"]] for r in rows if r["seconds_written"] > 30.0]
s32_set = {
    "set": "librispeech-test-clean-S32",
    "rule": "manifest.tsv rows at index 0, 32, 64, ... (every 32nd row from the first, file order; every 8th row of S4, every 2nd row of S16)",
    "utterances": len(s32), "total_seconds": sum(r["seconds_written"] for r in s32),
    "wav_sha256_chain": chain(s32),
    "first_ids": [r["id"] for r in s32[:3]], "last_id": s32[-1]["id"],
    "warmup": {"id": w_id, "row_index": 1, "seconds": w["seconds_written"],
               "wav_sha256": hashlib.sha256(open(f"{src}/{w_id}.wav", "rb").read()).hexdigest()},
    "over_30_s": {"S32": over(s32), "S4": over(s4), "W": over([w])},
    "full": {"utterances": len(full), "total_seconds": sum(r["seconds_written"] for r in full), "wav_sha256_chain": chain(full)},
    "source_set_dir": src,
}
json.dump(s32_set, open(f"{stage}/SET-S32.json", "w"), indent=2)
print(f"S4 {len(s4)} chain {s4_set['wav_sha256_chain'][:12]} (= SET-S4.json), S32 {len(s32)} "
      f"({s32_set['total_seconds']:.3f} s) chain {s32_set['wav_sha256_chain'][:12]}, full chain {s32_set['full']['wav_sha256_chain'][:12]}, "
      f"W {w_id} {w['seconds_written']} s, over 30 s: S4 {len(s32_set['over_30_s']['S4'])}, S32 {len(s32_set['over_30_s']['S32'])}")
EOF
  mkdir -p "$REC"
  cp "$STAGE/SET-S32.json" "$REC/SET-S32.json"
  cp "$SET/SET-S4.json" "$REC/SET-S4.json"
  while read -r id; do cp -c "$SET/$id.wav" "$STAGE/tar/S4/" 2>/dev/null || cp "$SET/$id.wav" "$STAGE/tar/S4/"; done < "$STAGE/ids-S4.txt"
  cp "$SET/$W_ID.wav" "$STAGE/tar/W/"
  (cd "$STAGE/tar" && COPYFILE_DISABLE=1 tar --format ustar --no-mac-metadata --no-xattrs -cf "$STAGE/S4.tar" W S4)
  {
    for f in $BINS; do echo "$(shasum -a 256 "$SB/bin/$f" | cut -d' ' -f1)  bin/$f"; done
    echo "$(shasum -a 256 "$DRV" | cut -d' ' -f1)  bin/asr-qnn-burst-driver"
    echo "$(shasum -a 256 "$SB/lib/libonnxruntime.so" | cut -d' ' -f1)  lib/libonnxruntime.so"
    for f in $QNN_LIBS; do echo "$(shasum -a 256 "$QNN/lib/$f" | cut -d' ' -f1)  lib/${f##*/}"; done
    for f in $MODEL_FILES; do echo "$(shasum -a 256 "$MD/$f" | cut -d' ' -f1)  models/$MODEL/$f"; done
    echo "$(shasum -a 256 "$here/device_run.sh" | cut -d' ' -f1)  device_run.sh"
    for f in S4.scp S32.tsv smoke3.tsv warm1.tsv; do echo "$(shasum -a 256 "$STAGE/lists/$f" | cut -d' ' -f1)  lists/$f"; done
    echo "$(shasum -a 256 "$SET/$W_ID.wav" | cut -d' ' -f1)  sets/W/$W_ID.wav"
  } > "$STAGE/expected.sha256"
  python3 -I -c 'import json, sys; print(json.load(open(sys.argv[1]))["wav_sha256_chain"])' "$SET/SET-S4.json" > "$STAGE/S4.chain"
  say "staged: $(wc -l < "$STAGE/lists/S4.scp" | tr -d ' ') lines in S4.scp (W + S4), $(wc -l < "$STAGE/lists/S32.tsv" | tr -d ' ') in S32.tsv, tar $(tar -tf "$STAGE/S4.tar" | grep -c '\.wav$') wav ($(du -h "$STAGE/S4.tar" | cut -f1)), S4 chain $(cat "$STAGE/S4.chain")"
  if tar -tf "$STAGE/S4.tar" | grep -q '/\._'; then echo "AppleDouble entries in S4.tar" >&2; exit 1; fi
}

verify() {  # -> <record>/SHA256SUMS; exit 1 on any mismatch. The S4 and S32 chains are recomputed on the phone.
  local got bad=0 dev_s4 dev_s32 s32
  got=$(adbx shell "cd $P && sha256sum $(cut -d' ' -f3 "$STAGE/expected.sha256" | tr '\n' ' ')")
  dev_s4=$(adbx shell "cd $P && tail -n +2 lists/S4.scp | while read id p; do cat \$p; done | sha256sum" | cut -d' ' -f1)
  dev_s32=$(adbx shell "cd $P && cut -f2 lists/S32.tsv | while read p; do cat \$p; done | sha256sum" | cut -d' ' -f1)
  [ "$DRY" = 1 ] && return 0
  s32=$(python3 -I -c 'import json, sys; print(json.load(open(sys.argv[1]))["wav_sha256_chain"])' "$REC/SET-S32.json")
  mkdir -p "$REC"
  : > "$REC/SHA256SUMS"
  while read -r sha path; do
    dev=$(echo "$got" | awk -v p="$path" '$2 == p {print $1}')
    echo "$dev  $path" >> "$REC/SHA256SUMS"
    if [ "$dev" != "$sha" ]; then echo "MISMATCH $path: phone ${dev:-none} != Mac $sha" >&2; bad=1; fi
  done < "$STAGE/expected.sha256"
  echo "# $dev_s4  sets: the WAVs of lists/S4.scp after its first line (W), concatenated in list order (phone); SET-S4.json chain $(cat "$STAGE/S4.chain")" >> "$REC/SHA256SUMS"
  echo "# $dev_s32  sets: the WAVs of lists/S32.tsv in list order (phone); SET-S32.json chain $s32" >> "$REC/SHA256SUMS"
  [ "$dev_s4" = "$(cat "$STAGE/S4.chain")" ] || { echo "MISMATCH S4 chain: phone $dev_s4" >&2; bad=1; }
  [ "$dev_s32" = "$s32" ] || { echo "MISMATCH S32 chain: phone $dev_s32 != $s32" >&2; bad=1; }
  [ $bad = 0 ] && log "sha256 read back on the phone: all match ($(wc -l < "$STAGE/expected.sha256" | tr -d ' ') files, S4 chain $dev_s4, S32 chain $dev_s32)"
  return $bad
}

push() {
  need_hold
  [ -f "$STAGE/S4.tar" ] || { echo "run stage first" >&2; exit 1; }
  adbx shell "rm -rf $P && mkdir -p $P/bin $P/lib $P/models/$MODEL $P/sets $P/lists $P/runs"
  for f in $BINS; do adbx push "$SB/bin/$f" "$P/bin/$f"; done
  adbx push "$DRV" "$P/bin/asr-qnn-burst-driver"
  adbx push "$SB/lib/libonnxruntime.so" "$P/lib/libonnxruntime.so"
  for f in $QNN_LIBS; do adbx push "$QNN/lib/$f" "$P/lib/${f##*/}"; done
  for f in $MODEL_FILES; do adbx push "$MD/$f" "$P/models/$MODEL/$f"; done
  adbx push "$here/device_run.sh" "$P/device_run.sh"
  for f in S4.scp S32.tsv smoke3.tsv warm1.tsv; do adbx push "$STAGE/lists/$f" "$P/lists/$f"; done
  adbx push "$STAGE/S4.tar" "$P/sets/S4.tar"
  adbx shell "cd $P/sets && tar -xf S4.tar && rm S4.tar && chmod 755 $P/bin/*"
  verify
}

help_of() {
  need_hold
  mkdir -p "$REC"
  adbx shell "cd $P && LD_LIBRARY_PATH=$P/lib bin/sherpa-onnx-offline-parallel --help 2>&1; echo exit=\$?" > "$REC/sherpa-onnx-offline-parallel.help.txt" || true
  adbx shell "cd $P && LD_LIBRARY_PATH=$P/lib bin/asr-qnn-burst-driver --help 2>&1; echo exit=\$?" > "$REC/asr-qnn-burst-driver.help.txt" || true
  say "help: parallel $(wc -l < "$REC/sherpa-onnx-offline-parallel.help.txt" | tr -d ' ') lines ($(grep -c 'qnn' "$REC/sherpa-onnx-offline-parallel.help.txt") with qnn), driver $(wc -l < "$REC/asr-qnn-burst-driver.help.txt" | tr -d ' ') lines"
}

version() {
  need_hold
  mkdir -p "$REC"
  adbx shell "cd $P && LD_LIBRARY_PATH=$P/lib bin/sherpa-onnx-version 2>&1; echo exit=\$?" > "$REC/sherpa-onnx-version.txt" || true
  say "version: $(tr '\n' ' ' < "$REC/sherpa-onnx-version.txt" | cut -c1-200)"
}

debuginfo() {  # the plain CLI with --debug=1 on the W file: what the QNN backend and the context report at load
  need_hold
  mkdir -p "$REC"
  local cmd="cd $P && export LD_LIBRARY_PATH=$P/lib && export ADSP_LIBRARY_PATH=\"$P/lib;\$ADSP_LIBRARY_PATH\" && bin/sherpa-onnx-offline $QNN_FLAGS --debug=1 sets/W/$W_ID.wav"
  echo "### CMD: $cmd" > "$REC/debuginfo.cmd"
  adbx shell "$cmd > runs/debuginfo.stdout.log 2> runs/debuginfo.stderr.log; echo rc=\$? > runs/debuginfo.exit" || true
  adbx pull "$P/runs/debuginfo.stdout.log" "$REC/debuginfo.stdout.log" > /dev/null
  adbx pull "$P/runs/debuginfo.stderr.log" "$REC/debuginfo.stderr.log" > /dev/null
  adbx pull "$P/runs/debuginfo.exit" "$REC/debuginfo.exit" > /dev/null
  say "debuginfo: $(cat "$REC/debuginfo.exit" 2>/dev/null) | $(grep -h -E 'backend build ID|max_num_frames|Truncate|Htp' "$REC/debuginfo.stderr.log" "$REC/debuginfo.stdout.log" 2>/dev/null | head -n 5 | tr '\n' ' ' | cut -c1-300)"
}

clocks() {  # wait up to CPUCAP_WAIT s for every policy's scaling_max_freq = cpuinfo_max_freq
  local max=${CPUCAP_WAIT:-300} waited=0 out
  [ "$max" -gt 0 ] || return 0
  while :; do
    out=$(adbx shell 'for d in /sys/devices/system/cpu/cpufreq/policy*; do echo "${d##*/} $(cat $d/scaling_max_freq) $(cat $d/cpuinfo_max_freq)"; done' | tr -d '\r')
    [ "$DRY" = 1 ] && return 0
    if echo "$out" | awk '$2 != $3 {bad = 1} END {exit bad}'; then
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
    [ "$DRY" = 1 ] && { clocks; return 0; }
    t=$(echo "$out" | sed -n 's/.*temperature: *\([0-9-]*\).*/\1/p')
    s=$(echo "$out" | sed -n 's/.*Thermal Status: *\([0-9]*\).*/\1/p')
    if [ -n "$t" ] && [ "$t" -le 360 ] && [ "$s" = 0 ]; then
      log "cool: waited ${waited}s, battery $t (0.1 C), Thermal Status $s"
      clocks; return 0
    fi
    if [ $waited -ge "$max" ]; then
      log "cool: gave up after ${waited}s (started anyway), battery $t (0.1 C), Thermal Status $s"; clocks; return 0
    fi
    sleep 10; waited=$((waited + 10))
  done
}

probe() {
  need_hold
  mkdir -p "$REC"
  if [ "$DRY" = 1 ]; then echo "+ $here/probe.sh $1 $SERIAL > $REC/probe-$1.json" >&2; return 0; fi
  "$here/probe.sh" "$1" "$SERIAL" > "$REC/probe-$1.json"
  python3 -I - "$REC/probe-$1.json" <<'EOF' | tee -a "$REC/progress.log"
import json, sys
d = json.load(open(sys.argv[1]))
pol = " ".join(f"{k}={v['scaling_max_freq_kHz']}/{v['cpuinfo_max_freq_kHz']}" for k, v in d["policies"].items())
hal = " ".join(f"{t['name']}={t['value_C']}" for t in d.get("hal_temperatures", []) if t["name"] in ("AP", "SKIN", "BAT", "battery", "skin"))
print(f"probe {d['label']}: battery {d['battery']['temperature_C']} C, Thermal Status {d['thermal_status']}, HAL {hal}, "
      f"MemAvailable {d['mem_kB'].get('MemAvailable')} kB, scaling/cpuinfo max kHz {pol}, screen {d.get('wakefulness')}, procs {d.get('procs')}")
EOF
}

launch() {  # <tag> <cmdline> <CMD line for the record>
  local tag=$1 cmdline=$2
  mkdir -p "$REC"
  { echo "### phone: Galaxy S26 $SERIAL, cwd $P"; echo "### launch (adb shell): $cmdline"; echo "### CMD: $3"; } > "$REC/$tag.cmd"
  if [ "$DRY" = 1 ]; then echo "+ gtimeout 30 adb -s $SERIAL shell \"$cmdline\"" >&2; return 0; fi
  gtimeout 30 adb -s "$SERIAL" shell "$cmdline" || log "launch: the adb client did not return in 30 s (the run is under nohup; checking)"
  sleep 2
  log "start $tag: $(adbx shell "head -n 1 $P/runs/$tag.runner.log" | tr -d '\r')"
}

driver_run() {  # <tag> <list> <pace> <load_label>
  need_hold
  local tag=$1 list=$2 pace=$3 label=$4 wsec flags info
  wsec=$(cat "$STAGE/W.seconds")
  info="repo=$(git -C "$repo" rev-parse --short HEAD),driver_sha256=$(shasum -a 256 "$DRV" | cut -c1-12),list_sha256=$(shasum -a 256 "$STAGE/lists/$list" | cut -c1-12)"
  # the phone's shell parses the command line: the recipe is one single-quoted word (device_run.sh keeps it one argument)
  flags="$QNN_FLAGS --list=$P/lists/$list --pace=$pace --warmup-id=$W_ID --warmup-wav=$P/sets/W/$W_ID.wav --warmup-seconds=$wsec --load-label=$label --model-name=$MODEL --run-info=$info --quant-recipe='$QUANT'"
  launch "$tag" "cd $P && nohup sh device_run.sh $tag driver $flags > runs/$tag.runner.log 2>&1 < /dev/null &" \
    "LD_LIBRARY_PATH=$P/lib ADSP_LIBRARY_PATH=\"$P/lib;\" bin/asr-qnn-burst-driver $flags --out=$P/runs/$tag.jsonl --ceil-log=$P/runs/$tag.ceil.log --tag=$tag"
}

cli_run() {  # <tag> <list>
  need_hold
  local tag=$1 list=$2
  launch "$tag" "cd $P && nohup sh device_run.sh $tag cli lists/$list $QNN_FLAGS $PARALLEL_FLAGS > runs/$tag.runner.log 2>&1 < /dev/null &" \
    "LD_LIBRARY_PATH=$P/lib ADSP_LIBRARY_PATH=\"$P/lib;\" bin/sherpa-onnx-offline-parallel $QNN_FLAGS $PARALLEL_FLAGS --wav-scp=$P/runs/$tag.scp"
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
    sleep 10; waited=$((waited + 10))
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

step=${1:?step: stage|push|help|version|debuginfo|cool|probe|driver|cli|wait|pull}
shift
case $step in
  stage) stage ;;
  push) push ;;
  help) help_of ;;
  version) version ;;
  debuginfo) debuginfo ;;
  cool) cool "$@" ;;
  probe) probe "$@" ;;
  driver) driver_run "$@" ;;
  cli) cli_run "$@" ;;
  wait) wait_done "$@" ;;
  pull) pull "$@" ;;
  *) echo "unknown step $step" >&2; exit 2 ;;
esac
