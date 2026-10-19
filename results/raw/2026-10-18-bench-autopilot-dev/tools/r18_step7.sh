#!/bin/bash
# Round 18, step 7 (after the supervisor's go, the cells files in main): the candidate's sittings, one per device and
# cells file, from the main checkout's job route. Lines that start with "R18 " are the ones to read.
#   mac-stage           APFS clone of the candidate into the yardstick's side-load dir, sha256-checked (no device)
#   mac-job             the Mac sitting: DD_MAC=.build/dd-mac-q06cand, the job takes the window itself; waits for it
#   ios-push            a keeper (45 min at most) queues for the 18 Pro and takes its hold; the phone attached and
#                       unlocked; the candidate copied into the app's side-load dir, its size checked, the bytes copied
#                       back and hashed; the r18 app installed; the 2x2 GPU engine-build smoke (graph 2026-08-05 /
#                       2026-09-21 x LlmMetadata 2026-08-05 / current, one short-chat launch each); the candidate back
#                       in its place and hashed again; the hold released
#   ios-job             the iPhone sitting (the job takes the hold itself) once no other keeper waits; waits for it
#   android DEV HALF    DEV = s26 | pixel8a, HALF = gpu | cpu: a keeper queues and takes DEV's hold, the job runs with
#                       BENCH_SITTING=1 --hold-held-by <keeper>, the hold is released when the job ends
# OUT = a dir for the logs (required). Exit: 0 = done; 1 = a step failed; 3 = the device stayed busy past WAIT_S
# (dequeued); 4 = another keeper waits in the line (no job); the job's own exit code otherwise (mac-job, ios-job,
# android).
set -u
MAIN=$HOME/code/edge-llm-bench
TOOLS=$HOME/code/litertlm-convert/community_accel_work
CAND=$HOME/.cache/edge-llm-bench/litert-candidates/out/Qwen3-0.6B_dynamic_wi4b32_afp32.r0805meta018.litertlm
SHA=e6bf25c0cf7e1a09d19fc6ad716072bb5b8ac96a0eca75075a69f7ce8c1a8f91
# the 2x2 smoke's diagnostic files: (a) the 2026-08-05 file as on the Hub, (c) the current graph + the 2026-08-05 LlmMetadata
IN_0805=$HOME/.cache/edge-llm-bench/litert-candidates/in/Qwen3-0.6B_dynamic_wi4b32_afp32.litertlm
SHA_0805=e3e290109da4388d65a17510a0c66af91c8039f52d2c465868dbc43c09a776cf
DIAG_C=$HOME/.cache/edge-llm-bench/litert-candidates/diag/Qwen3-0.6B_dynamic_wi4b32_afp32.r0921meta0805.litertlm
SHA_C=8368cfa34c0414e626078704b7c8e319f3b3325c36cc261bdea4f2736d13552d
SIDELOAD=models/litert-lm/litert-local__Qwen3-0.6B-r0805meta018
UDID=00008160-000038CA02C00036
APPID=com.example.CoreMLLLMChat
APP=$MAIN/.build/dd-ios-0180-18pro/Build/Products/Release-iphoneos/BenchmarkApp.app
OUT=${OUT:?set OUT to a dir for the logs}
WAIT_S=${WAIT_S:-5400}
say() { echo "R18 $(date +%H:%M:%S) $*"; }
mkdir -p "$OUT" || exit 1

need_main_cells() {
  [ -f "$MAIN/matrices/$1" ] || { say "STOP $MAIN/matrices/$1 is not there (not merged yet)"; exit 1; }
  cmp -s "$MAIN/matrices/$1" "$(cd "$(dirname "$0")/../../../.." && pwd)/matrices/$1" \
    || say "NOTE main's matrices/$1 differs from this tree's copy (the job runs main's)"
}
start_job() {   # $1 = device key, $2 = cells file, $3 = suffix, rest = extra job args; env from the caller; waits
  local dev=$1 cells=$2 suffix=$3; shift 3
  local log=logs/dashboard-job/$(date +%F)-$dev-$suffix.byhand.out
  ( cd "$MAIN" && python3 scripts/dashboard_job.py "$dev" --cells "matrices/$cells" --suffix "$suffix" --once "$@" \
      < /dev/null > "$log" 2>&1 )
  local rc=$?
  say "job $dev $suffix exit $rc (log $MAIN/$log; ledger: $(grep -F -- "-$suffix-" "$MAIN/logs/dashboard-job/ledger.tsv" | tail -1 | cut -f3-8 | tr '\t' ' '))"
  return $rc
}
keeper_take() {   # $1 = hold file, $2 = queue name, $3 = minutes the slot takes; sets KEEPER
  # the hold names this pid for the queue wait and the whole slot: it must outlive both, so a 4-hour sleep that the
  # release (or this script's exit) kills
  sleep 14400 &
  KEEPER=$!
  trap 'kill $KEEPER 2>/dev/null' EXIT
  say "keeper pid $KEEPER (a sleep killed at the release) for $1"
  python3 "$TOOLS/queue_cli.py" enqueue "$1" "$2" edge-llm-bench-55 "$3" | sed 's/^/    /'
  if ! python3 "$TOOLS/queue_cli.py" wait "$1" "$2" "$KEEPER" --timeout "$WAIT_S"; then
    python3 "$TOOLS/queue_cli.py" dequeue "$1" "$2" > /dev/null
    say "STOP the device stayed busy for $WAIT_S s (queue_cli wait timed out); dequeued"
    exit 3
  fi
  say "hold $1 taken by keeper $KEEPER"
}

mac_stage() {
  local dir=$HOME/Documents/$SIDELOAD
  mkdir -p "$dir" || exit 1
  [ -e "$dir/$(basename "$CAND")" ] || cp -c "$CAND" "$dir/$(basename "$CAND")" || exit 1
  local got; got=$(shasum -a 256 "$dir/$(basename "$CAND")" | cut -d' ' -f1)
  ls -la "$dir" | sed 's/^/    /'
  [ "$got" = "$SHA" ] || { say "FAIL the staged copy hashes $got"; exit 1; }
  say "DONE mac-stage: $dir/$(basename "$CAND") sha256 $got; ~/Documents/models/litert-lm/litert-community__Qwen3-0.6B/ holds $(ls -A "$HOME/Documents/models/litert-lm/litert-community__Qwen3-0.6B" | wc -l | tr -d ' ') entries"
}

ios_push() {
  [ -d "$APP" ] || { say "FAIL no app at $APP"; exit 1; }
  keeper_take "$HOME/code/coreai/ondevice/.device_hold" r18-push-q06cand 30
  local rc=0
  (
    set -o pipefail
    xcrun devicectl list devices > "$OUT/devices.txt" 2>&1
    grep "$UDID" "$OUT/devices.txt" | grep -q -e available -e connected || { say "FAIL $UDID not available ($OUT/devices.txt)"; exit 1; }
    xcrun devicectl device info lockState --device "$UDID" > "$OUT/lockstate.txt" 2>&1 || { say "FAIL lockState query failed"; exit 1; }
    grep -q "passcodeRequired: false" "$OUT/lockstate.txt" || { say "FAIL the phone is locked ($OUT/lockstate.txt)"; exit 1; }
    say "OK $UDID attached and unlocked"
    xcrun devicectl device info files --device "$UDID" --domain-type appDataContainer --domain-identifier "$APPID" \
      --subdirectory Documents/models/litert-lm -j "$OUT/litert-before.json" > "$OUT/litert-before.txt" 2>&1 \
      || { say "FAIL listing Documents/models/litert-lm ($OUT/litert-before.txt)"; exit 1; }
    python3 -I - "$OUT/litert-before.json" <<'EOF'
import json, sys
for f in json.load(open(sys.argv[1]))["result"]["files"]:
    if "Qwen3-0.6B" in f["relativePath"] and not f["resources"]["isDirectory"]:
        print(f"    before: {f['relativePath']} {f['metadata']['size']:,} B")
EOF
    say "copy the candidate into Documents/$SIDELOAD/"
    xcrun devicectl device copy to --device "$UDID" --domain-type appDataContainer --domain-identifier "$APPID" \
      --source "$CAND" --destination "Documents/$SIDELOAD/$(basename "$CAND")" -t 1200 > "$OUT/copy-to.txt" 2>&1 \
      || { say "FAIL copy to ($OUT/copy-to.txt)"; exit 1; }
    xcrun devicectl device info files --device "$UDID" --domain-type appDataContainer --domain-identifier "$APPID" \
      --subdirectory Documents/models/litert-lm -j "$OUT/litert-after.json" > "$OUT/litert-after.txt" 2>&1 \
      || { say "FAIL listing after the copy"; exit 1; }
    python3 -I - "$OUT/litert-after.json" "$(stat -f %z "$CAND")" "litert-local__Qwen3-0.6B-r0805meta018/$(basename "$CAND")" <<'EOF' || exit 1
import json, sys
files = {f["relativePath"]: f["metadata"]["size"] for f in json.load(open(sys.argv[1]))["result"]["files"]
         if not f["resources"]["isDirectory"]}
for p, s in sorted(files.items()):
    if "Qwen3-0.6B" in p:
        print(f"    after: {p} {s:,} B")
want, key = int(sys.argv[2]), sys.argv[3]
side = [p for p in files if p.startswith("litert-local__Qwen3-0.6B-r0805meta018/")]
if files.get(key) != want or side != [key]:
    print(f"FAIL the side-load dir holds {side} ({files.get(key)} B, want {want})"); sys.exit(1)
EOF
    mkdir -p "$OUT/back"
    xcrun devicectl device copy from --device "$UDID" --domain-type appDataContainer --domain-identifier "$APPID" \
      --source "Documents/$SIDELOAD/$(basename "$CAND")" --destination "$OUT/back/$(basename "$CAND")" -t 1200 \
      > "$OUT/copy-from.txt" 2>&1 || { say "FAIL copy back ($OUT/copy-from.txt)"; exit 1; }
    got=$(shasum -a 256 "$OUT/back/$(basename "$CAND")" | cut -d' ' -f1); rm -f "$OUT/back/$(basename "$CAND")"
    [ "$got" = "$SHA" ] || { say "FAIL the phone's copy hashes $got"; exit 1; }
    say "OK the phone's copy hashes $got (copied back and hashed)"
    say "install $APP (binary sha256 $(shasum -a 256 "$APP/BenchmarkApp" | cut -c1-16))"
    xcrun devicectl device install app --device "$UDID" "$APP" > "$OUT/install.txt" 2>&1 || { say "FAIL install ($OUT/install.txt)"; exit 1; }
    grep -iE 'installationURL|bundleID|databaseSequenceNumber' "$OUT/install.txt" | head -3 | sed 's/^/    /'
    xcrun devicectl device info apps --device "$UDID" --bundle-id "$APPID" > "$OUT/apps-after.txt" 2>&1
    # the supervisor's 2x2 (13:5x): one GPU short-chat launch per graph x LlmMetadata, engine built or not and the first
    # error line; (a) and (c) are put in the candidate's place under its name for one launch each (diagnostic, their
    # records stay on the phone outside every campaign: a sitting pulls only records newer than its own start), then
    # the candidate goes back and is hashed again; --purge-engine-cache before every launch (the GPU cache key is the
    # file's name, mtime and size, and (a) and (b) have the same name and size there)
    smoke() {   # $1 = label, $2 = model id
      gtimeout --kill-after=30 600 xcrun devicectl device process launch --console --terminate-existing --device "$UDID" "$APPID" \
        -- --yardstick-autorun --runtime litert-lm --model-id "$2" --task short-chat --runs 1 --purge-engine-cache \
        < /dev/null > "$OUT/smoke_$1.txt" 2>&1
      local built=no
      grep -q YARDSTICK_RUN_OK "$OUT/smoke_$1.txt" && built=yes
      say "SMOKE $1 engine built: $built; first error: $(grep -m1 -E 'error:|Failed to create|YARDSTICK_RUN_FAIL|YARDSTICK_FATAL' "$OUT/smoke_$1.txt" | cut -c1-220)"
    }
    put() {   # $1 = local file whose bytes go to the candidate's place, $2 = its sha256
      xcrun devicectl device copy to --device "$UDID" --domain-type appDataContainer --domain-identifier "$APPID" \
        --source "$1" --destination "Documents/$SIDELOAD/$(basename "$CAND")" -t 1200 > "$OUT/put.txt" 2>&1 \
        || { say "FAIL copy of $1 ($OUT/put.txt)"; return 1; }
      xcrun devicectl device copy from --device "$UDID" --domain-type appDataContainer --domain-identifier "$APPID" \
        --source "Documents/$SIDELOAD/$(basename "$CAND")" --destination "$OUT/back/check.litertlm" -t 1200 \
        > "$OUT/put-back.txt" 2>&1 || { say "FAIL copy back after putting $1"; return 1; }
      local got; got=$(shasum -a 256 "$OUT/back/check.litertlm" | cut -d' ' -f1); rm -f "$OUT/back/check.litertlm"
      [ "$got" = "$2" ] || { say "FAIL the candidate's place hashes $got after putting $1 (want $2)"; return 1; }
      say "OK the candidate's place holds $(basename "$1") ($got)"
    }
    # the first launch after an install dies in the scene-create watchdog (memory bench-app-install-must-be-release):
    # one throwaway launch first
    t_install=$(date -u +%Y-%m-%dT%H-%M-%S)
    gtimeout --kill-after=30 300 xcrun devicectl device process launch --console --terminate-existing --device "$UDID" "$APPID" \
      -- --yardstick-autorun --runtime mlx-swift --model-id mlx-community/Qwen3-0.6B-4bit --task short-chat --runs 1 \
      < /dev/null > "$OUT/throwaway.txt" 2>&1
    say "throwaway launch: $(grep -c YARDSTICK_RUN_OK "$OUT/throwaway.txt") RUN_OK line(s)"
    smoke d_graph0921_meta018 litert-community/Qwen3-0.6B/dynamic_wi4b32_afp32
    smoke b_graph0805_meta018 litert-community/Qwen3-0.6B/dynamic_wi4b32_afp32_r0805meta018
    put "$IN_0805" "$SHA_0805" && smoke a_graph0805_meta0805 litert-community/Qwen3-0.6B/dynamic_wi4b32_afp32_r0805meta018
    put "$DIAG_C" "$SHA_C" && smoke c_graph0921_meta0805 litert-community/Qwen3-0.6B/dynamic_wi4b32_afp32_r0805meta018
    put "$CAND" "$SHA" || { say "FAIL the candidate is not back in its place: no sitting until it is"; exit 1; }
    # the records the slot made (newer than the install): build configuration, arm, prompt tokens
    mkdir -p "$OUT/records"
    xcrun devicectl device copy from --device "$UDID" --domain-type appDataContainer --domain-identifier "$APPID" \
      --source Documents/results --destination "$OUT/records" > "$OUT/records-copy.txt" 2>&1
    python3 -I - "$OUT/records" "$t_install" <<'EOF'
import glob, json, os, sys
for f in sorted(glob.glob(os.path.join(sys.argv[1], "**", "*.json"), recursive=True)):
    if os.path.basename(f).rsplit("_", 1)[-1][:19] < sys.argv[2]:
        continue
    try:
        r = json.load(open(f))
    except Exception:
        continue
    m = r.get("metrics", {})
    print(f"    record {os.path.basename(f)[:90]}: {r.get('runtime')} {r['model'].get('id')} "
          f"build {r.get('device', {}).get('buildConfiguration')} prompt {m.get('promptTokenCount')} "
          f"gen {m.get('generatedTokenCount')} decode {m.get('decodeTokensPerSecond')}")
EOF
    say "DONE ios-push"
  ) 2>&1 | tee -a "$OUT/ios-push.log"
  rc=${PIPESTATUS[0]}
  python3 "$TOOLS/hold_cli.py" release "$HOME/code/coreai/ondevice/.device_hold" "$KEEPER"
  kill "$KEEPER" 2>/dev/null
  say "hold released (push exit $rc)"
  exit "$rc"
}

ios_job() {
  need_main_cells q06-candidate-ios.cells
  python3 "$TOOLS/queue_cli.py" list "$HOME/code/coreai/ondevice/.device_hold" > "$OUT/queue-before-ios-job.txt" 2>&1
  if grep -q "(keeper waiting)" "$OUT/queue-before-ios-job.txt"; then
    say "WAIT another keeper waits in the line, so the job did not start: $(tr '\n' ' ' < "$OUT/queue-before-ios-job.txt")"
    exit 4
  fi
  start_job iphone18pro q06-candidate-ios.cells q06cand
  exit $?
}

mac_job() {
  need_main_cells q06-candidate-mac.cells
  [ -x "$MAIN/.build/dd-mac-q06cand/Build/Products/Release/yardstick" ] || { say "FAIL no yardstick in .build/dd-mac-q06cand"; exit 1; }
  export DD_MAC=$MAIN/.build/dd-mac-q06cand
  start_job m4max q06-candidate-mac.cells q06cand
  exit $?
}

android() {
  local dev=$1 half=$2 hold
  case "$dev" in
    s26) hold=$TOOLS/s2_npu_sweep/.device_hold ;;
    pixel8a) hold=$TOOLS/s2_npu_sweep/.device_hold.pixel8a ;;
    *) say "usage: android s26|pixel8a gpu|cpu"; exit 2 ;;
  esac
  case "$half" in gpu|cpu) ;; *) say "usage: android s26|pixel8a gpu|cpu"; exit 2 ;; esac
  need_main_cells "q06-candidate-android-$half.cells"
  [ "$(shasum -a 256 "$CAND" | cut -d' ' -f1)" = "$SHA" ] || { say "FAIL $CAND does not hash $SHA"; exit 1; }
  keeper_take "$hold" "r18-q06cand-$dev-$half" 60
  export BENCH_SITTING=1
  start_job "$dev" "q06-candidate-android-$half.cells" "q06cand-$half" --hold-held-by "$KEEPER"
  local rc=$?
  python3 "$TOOLS/hold_cli.py" release "$hold" "$KEEPER"
  kill "$KEEPER" 2>/dev/null
  say "hold released ($dev $half, job exit $rc)"
  exit $rc
}

case "${1:-}" in
  mac-stage) mac_stage ;;
  mac-job) mac_job ;;
  ios-push) ios_push ;;
  ios-job) ios_job ;;
  android) android "${2:-}" "${3:-}" ;;
  *) sed -n 2,16p "$0" >&2; exit 2 ;;
esac
