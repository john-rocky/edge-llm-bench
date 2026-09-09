#!/bin/bash
# Local pass-through of the Route B APK on ONE adb device: build (optional) -> install both APKs ->
# `am instrument` with the same arguments DDP will get -> pull the records into
# results/raw/<campaign>/app-path-android/ -> check them with scripts/build_summary.py's loader.
#
#   android/ddp-bench/run_local.sh [--serial S] [--campaign NAME] [--backend cpu|gpu] [--runs N]
#       [--cooldown S] [--repo HF_REPO] [--file NAME] [--model /local/file.litertlm] [--no-gate]
#       [--no-build] [--token-file ~/.cache/huggingface/token]
#
# --model pushes a local .litertlm to /data/local/tmp/edge-llm-bench/ and passes model_path (no
# download, no token on the device). Without it the phone downloads from the Hub itself, with the
# token from --token-file (default: the huggingface-cli login) for gated repos.
#
# Exit codes: 0 = test passed and records pulled; 1 = test failed (records still pulled when they
# exist); 2 = usage / no device / build failure. Never starts while another driver holds the phone.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
SERIAL=""; CAMPAIGN=""; BACKEND="cpu"; RUNS="3"; COOLDOWN="60"; REPO=""; FILE=""; MODEL=""; GATE="true"
BUILD=1; TOKEN_FILE="$HOME/.cache/huggingface/token"; EXTRA=()
while [ $# -gt 0 ]; do
  case "$1" in
    --serial) SERIAL="$2"; shift 2 ;;
    --campaign) CAMPAIGN="$2"; shift 2 ;;
    --backend) BACKEND="$2"; shift 2 ;;
    --runs) RUNS="$2"; shift 2 ;;
    --cooldown) COOLDOWN="$2"; shift 2 ;;
    --repo) REPO="$2"; shift 2 ;;
    --file) FILE="$2"; shift 2 ;;
    --model) MODEL="$2"; shift 2 ;;
    --no-gate) GATE="false"; shift ;;
    --no-build) BUILD=0; shift ;;
    --token-file) TOKEN_FILE="$2"; shift 2 ;;
    -e) EXTRA+=(-e "$2" "$3"); shift 3 ;;
    *) sed -n 2,16p "$0"; exit 2 ;;
  esac
done
export JAVA_HOME="${JAVA_HOME:-/Library/Java/JavaVirtualMachines/temurin-17.jdk/Contents/Home}"
export ANDROID_HOME="${ANDROID_HOME:-$HOME/Library/Android/sdk}"
ADB=(adb); [ -n "$SERIAL" ] && ADB=(adb -s "$SERIAL")

# ---- device present? (the native lane's one-driver-per-device lock is honoured, not bypassed)
if ! "${ADB[@]}" get-state >/dev/null 2>&1; then
  echo "[ddp-bench] no adb device$( [ -n "$SERIAL" ] && echo " with serial $SERIAL")" >&2; exit 2
fi
DEV_SERIAL="${SERIAL:-$("${ADB[@]}" get-serialno </dev/null | tr -d '\r\n')}"
MODEL_NAME=$("${ADB[@]}" shell getprop ro.product.model </dev/null | tr -d '\r\n')
for lock in "$ROOT/logs/dashboard-job/hold.json" "/tmp/edge-llm-bench-android-$DEV_SERIAL.lock"; do
  if [ -e "$lock" ] && grep -q "$DEV_SERIAL" "$lock" 2>/dev/null; then
    echo "[ddp-bench] $lock names $DEV_SERIAL — another driver owns this phone; not starting" >&2; exit 2
  fi
done
CAMPAIGN="${CAMPAIGN:-$(date +%F)-ddp-apk-$(echo "$MODEL_NAME" | tr 'A-Z ' 'a-z-')-android}"
echo "[ddp-bench] device=$MODEL_NAME ($DEV_SERIAL) campaign=$CAMPAIGN backend=$BACKEND runs=$RUNS"

# ---- build
if [ $BUILD = 1 ]; then
  (cd "$HERE" && ./gradlew --no-daemon -q :app:assembleDebug :app:assembleDebugAndroidTest) || { echo "[ddp-bench] build failed" >&2; exit 2; }
fi
APP="$HERE/app/build/outputs/apk/debug/app-debug.apk"
TEST="$HERE/app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk"
[ -f "$APP" ] && [ -f "$TEST" ] || { echo "[ddp-bench] APKs missing under app/build/outputs — build first" >&2; exit 2; }

# ---- install (fresh every time: the model cache lives in the app's files dir and survives -r)
"${ADB[@]}" install -r -t "$APP" </dev/null >/dev/null || { echo "[ddp-bench] install app failed" >&2; exit 2; }
"${ADB[@]}" install -r -t "$TEST" </dev/null >/dev/null || { echo "[ddp-bench] install test failed" >&2; exit 2; }

# ---- arguments (identical names to --additional-test-options on DDP)
ARGS=(-e backend "$BACKEND" -e runs "$RUNS" -e cooldown_s "$COOLDOWN" -e gate "$GATE" -e campaign "$CAMPAIGN")
[ -n "$REPO" ] && ARGS+=(-e hf_repo "$REPO")
[ -n "$FILE" ] && ARGS+=(-e hf_file "$FILE")
if [ -n "$MODEL" ]; then
  [ -f "$MODEL" ] || { echo "[ddp-bench] --model $MODEL not found" >&2; exit 2; }
  DEV_MODEL="/data/local/tmp/edge-llm-bench/$(basename "$MODEL")"
  "${ADB[@]}" shell mkdir -p /data/local/tmp/edge-llm-bench </dev/null
  "${ADB[@]}" push "$MODEL" "$DEV_MODEL" </dev/null >/dev/null || { echo "[ddp-bench] push failed" >&2; exit 2; }
  "${ADB[@]}" shell chmod 755 /data/local/tmp/edge-llm-bench </dev/null; "${ADB[@]}" shell chmod 644 "$DEV_MODEL" </dev/null
  ARGS+=(-e model_path "$DEV_MODEL")
elif [ -s "$TOKEN_FILE" ]; then
  ARGS+=(-e hf_token "$(tr -d '\r\n' < "$TOKEN_FILE")")
fi
ARGS+=("${EXTRA[@]}")

OUT="$ROOT/results/raw/$CAMPAIGN/app-path-android"
mkdir -p "$OUT"
"${ADB[@]}" logcat -c </dev/null 2>/dev/null
"${ADB[@]}" shell rm -rf "/sdcard/Android/data/io.github.johnrocky.edgellmbench/files/edge-llm-bench/$CAMPAIGN" </dev/null 2>/dev/null

# ---- run. `am instrument -w` blocks until the test ends; -r gives raw status lines (the log).
echo "[ddp-bench] am instrument ... ($(date +%H:%M:%S))"
"${ADB[@]}" shell am instrument -w -r "${ARGS[@]}" \
  io.github.johnrocky.edgellmbench.test/androidx.test.runner.AndroidJUnitRunner </dev/null \
  | tee "$OUT/am_instrument.txt"
INST_RC=${PIPESTATUS[0]}
if grep -q "^INSTRUMENTATION_STATUS_CODE: -2\|^INSTRUMENTATION_CODE: 0\|FAILURES" "$OUT/am_instrument.txt"; then TEST_RC=1; else TEST_RC=0; fi
grep -q "OK (1 test)" "$OUT/am_instrument.txt" && TEST_RC=0

# ---- pull records + the device log (the native LiteRT-LM output lives in logcat)
"${ADB[@]}" pull "/sdcard/Android/data/io.github.johnrocky.edgellmbench/files/edge-llm-bench/$CAMPAIGN/app-path-android/." "$OUT/" </dev/null >/dev/null 2>&1 \
  || echo "[ddp-bench] no records to pull (the test died before the first record?)"
"${ADB[@]}" logcat -d </dev/null > "$OUT/logcat.txt" 2>/dev/null
echo "[ddp-bench] records: $(ls "$OUT"/*.json 2>/dev/null | wc -l | tr -d ' ') under results/raw/$CAMPAIGN/app-path-android/"
grep -h "SUMMARY\|GATE \|run [0-9]*/[0-9]* " "$OUT/logcat.txt" | grep EDGE_LLM_BENCH | sed 's/.*EDGE_LLM_BENCH: /[device] /'

# ---- the records must be what the accumulation layer accepts
python3 - "$ROOT" "$OUT" <<'PY'
import glob, json, os, sys
root, out = sys.argv[1], sys.argv[2]
sys.path.insert(0, os.path.join(root, "scripts"))
import importlib.util
spec = importlib.util.spec_from_file_location("bs", os.path.join(root, "scripts", "build_summary.py"))
bs = importlib.util.module_from_spec(spec); spec.loader.exec_module(bs)
n = 0
for f in sorted(glob.glob(os.path.join(out, "litert-lm-*_run*.json"))):
    d = json.load(open(f))
    for k in ("schemaVersion", "runtime", "model", "task", "timestamp"):
        assert k in d, f"{f}: missing {k}"
    assert bs.platform_of(d) == "android", f"{f}: platform_of != android"
    m = d.get("metrics", {})
    print(f"  {os.path.basename(f)}: decode={m.get('decodeTokensPerSecond')} prefill={m.get('promptTokensPerSecond')} "
          f"ttft_ms={m.get('firstTokenLatencyMS')} gen={m.get('generatedTokenCount')} rss_mb={m.get('memoryMedianResidentMB') and round(m['memoryMedianResidentMB'])} "
          f"gate={d.get('quality',{}).get('gate',{}).get('verdict')} firstEver={m.get('firstEver')}")
    n += 1
print(f"[ddp-bench] {n} record(s) pass the result.v1 shape check (platform=android)")
PY
exit $TEST_RC
