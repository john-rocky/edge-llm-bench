#!/usr/bin/env bash
# Put one LiteRT-LM build on a phone's flat bench dir and prove it is the pinned one.
#
#   android/scripts/deploy_litert_lm_android.sh <tag> [serial] [--check] [--reset-caches]
#
#   <tag>           an android/engine-pins.json litert-lm key with a local build in
#                   android/bin/<tag>/ (android/scripts/build_litert_lm_main.sh)
#   [serial]        the phone; default $BENCH_ANDROID_SERIAL (neither: exit 2)
#   --check         push nothing: compare what is on the phone with the pin
#   --reset-caches  also delete the engine caches beside every LiteRT-LM bundle in
#                   /data/local/tmp/llmbench/models and those bundles' firstEver markers
#
# Why:
#   - The flat build's witness (android/bench/run_cell.py observed_engine) checks the tool's
#     sha256 only, never the .so files beside it: a phone whose litert_lm_main is v0.18.0 and
#     whose accelerator libraries are still v0.16.0 stamps its rows v0.18.0. So this script
#     pushes all nine files (litert_lm_main, litert_lm_advanced_main, the seven .so) and
#     compares the phone's sha256 of every one with the pin's entry; one mismatch = exit 1.
#   - A new engine rebuilds the bundles' engine caches (XNNPACK weight cache, GPU program
#     caches) on its first launch. run_cell.py labels that launch firstEver from a marker in
#     /data/local/tmp/llmbench/markers/; a marker left from the old engine makes the
#     cache-building run 1 read as an ordinary cold run and pool as speed. --reset-caches
#     removes the caches and the markers together, by the rule scripts/dashboard_job.py's
#     storage rotation uses (android_rotate: models/<base>_*, models/<base>.*,
#     markers/<base>.*.cachebuilt), for every .litertlm bundle on the phone. Model files and
#     raw records are never deleted.
#
# Exit: 0 every file matches the pin; 1 a mismatch (or a local build that is not the pin);
# 2 usage / no serial / no pin entry / no local build.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DEV_DIR=/data/local/tmp/llmbench
PINS="$REPO_ROOT/android/engine-pins.json"

usage() { sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//' >&2; exit 2; }

TAG="" SERIAL="" CHECK=0 RESET=0
for a in "$@"; do
  case "$a" in
    --check) CHECK=1 ;;
    --reset-caches) RESET=1 ;;
    -h|--help) usage ;;
    -*) echo "unknown option: $a" >&2; usage ;;
    *) if [[ -z "$TAG" ]]; then TAG="$a"; elif [[ -z "$SERIAL" ]]; then SERIAL="$a"; else usage; fi ;;
  esac
done
[[ -n "$TAG" ]] || usage
SERIAL="${SERIAL:-${BENCH_ANDROID_SERIAL:-}}"
if [[ -z "$SERIAL" ]]; then
  echo "no serial: pass it or set BENCH_ANDROID_SERIAL" >&2
  exit 2
fi
ADB=(adb -s "$SERIAL")
BIN="$REPO_ROOT/android/bin/$TAG"

# "<file> <sha256>" for the nine files of the pin (tools first, then so_files)
PIN_LINES="$(python3 - "$PINS" "$TAG" <<'PY'
import json, sys
pins, tag = sys.argv[1], sys.argv[2]
e = json.load(open(pins)).get("litert-lm", {}).get(tag)
if not e or not e.get("litert_lm_main_sha256") or not e.get("litert_lm_advanced_main_sha256") \
        or not e.get("so_files"):
    sys.exit(f"android/engine-pins.json has no complete litert-lm {tag} entry "
             "(litert_lm_main_sha256, litert_lm_advanced_main_sha256, so_files)")
print("litert_lm_main", e["litert_lm_main_sha256"])
print("litert_lm_advanced_main", e["litert_lm_advanced_main_sha256"])
for name, sha in sorted(e["so_files"].items()):
    print(name, sha)
PY
)" || exit 2
FILES=()
while read -r name _; do FILES+=("$name"); done <<< "$PIN_LINES"
pin_sha() { awk -v n="$1" '$1 == n {print $2}' <<< "$PIN_LINES"; }

echo "== LiteRT-LM $TAG -> $SERIAL:$DEV_DIR (${#FILES[@]} files; $([[ $CHECK == 1 ]] && echo 'check only' || echo 'push + check'))"

if [[ $CHECK == 0 ]]; then
  [[ -d "$BIN" ]] || { echo "no local build at $BIN (android/scripts/build_litert_lm_main.sh $TAG)" >&2; exit 2; }
  # the local files must be the pin before anything reaches the phone
  bad_local=0
  for name in "${FILES[@]}"; do
    if [[ ! -f "$BIN/$name" ]]; then
      echo "local $BIN/$name missing" >&2; bad_local=1; continue
    fi
    got="$(shasum -a 256 "$BIN/$name" | awk '{print $1}')"
    if [[ "$got" != "$(pin_sha "$name")" ]]; then
      echo "local $BIN/$name sha256 $got != pin $(pin_sha "$name")" >&2; bad_local=1
    fi
  done
  [[ $bad_local == 0 ]] || { echo "the local build is not the pinned $TAG: nothing pushed" >&2; exit 1; }
  "${ADB[@]}" shell "mkdir -p $DEV_DIR"
  for name in "${FILES[@]}"; do
    "${ADB[@]}" push "$BIN/$name" "$DEV_DIR/$name" >/dev/null
    echo "pushed $name"
  done
  "${ADB[@]}" shell "cd $DEV_DIR && chmod 755 ${FILES[*]}"
fi

# the phone's sha256 of every pinned file, in one shell
dev_out="$("${ADB[@]}" shell "cd $DEV_DIR && for f in ${FILES[*]}; do if [ -f \"\$f\" ]; then sha256sum \"\$f\"; else echo \"missing \$f\"; fi; done")"
printf '%-38s %-16s %-16s %s\n' file expected device result
bad=0
for name in "${FILES[@]}"; do
  want="$(pin_sha "$name")"
  have="$(awk -v n="$name" '$2 == n {print $1}' <<< "${dev_out//$'\r'/}")"
  if [[ "$have" == "$want" ]]; then res=OK; else res=NG; bad=1; fi
  printf '%-38s %-16s %-16s %s\n' "$name" "${want:0:12}…" "${have:0:12}${have:+…}" "$res"
done

if [[ $RESET == 1 ]]; then
  echo "== reset: engine caches and firstEver markers of every .litertlm bundle in $DEV_DIR/models"
  "${ADB[@]}" shell "cd $DEV_DIR/models 2>/dev/null || exit 0; for f in *.litertlm; do [ -f \"\$f\" ] || continue; for c in \"\$f\"_* \"\$f\".*; do if [ -e \"\$c\" ]; then rm -f \"\$c\" && echo \"removed $DEV_DIR/models/\$c\"; fi; done; for m in $DEV_DIR/markers/\"\$f\".*.cachebuilt; do if [ -e \"\$m\" ]; then rm -f \"\$m\" && echo \"removed \$m\"; fi; done; done"
fi

if [[ $bad == 1 ]]; then
  echo "NG: the phone's flat build is not the pinned LiteRT-LM $TAG" >&2
  exit 1
fi
echo "OK: the phone's flat build is the pinned LiteRT-LM $TAG (all ${#FILES[@]} files)"
