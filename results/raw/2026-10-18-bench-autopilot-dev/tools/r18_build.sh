#!/usr/bin/env bash
# r18_build.sh LOGDIR - round r18's two builds from SIDE (the frozen source of the 18 Pro app and the Mac yardstick) in one
# quiet_hold window: the Mac yardstick into MAIN/.build/dd-mac-q06cand (fresh derived data, SourcePackages an APFS clone of
# the iPhone build's, as round r13 built dd-mac-tmpl), then the iPhone app into MAIN/.build/dd-ios-0180-18pro (the app
# before it kept beside it as BenchmarkApp.app.r19-1312). SIDE carries r17's four uncommitted files (the 1K task's new
# tail, tonight's switch): MAIN's versions go in for the builds and r17's come back after (trap, sha256-checked). The one
# other SIDE-vs-MAIN source difference allowed is ModelCatalog.swift, which must equal this branch's (the candidate entry).
# Logs and the before / after lines go to LOGDIR. Exit 0 = both builds succeeded and r17's files are back.
set -uo pipefail
[ $# -eq 1 ] || { echo "usage: $0 LOGDIR" >&2; exit 2; }
L=$1; mkdir -p "$L"; OUT=$L/build.out; : > "$OUT"
M=$HOME/code/edge-llm-bench
REPO=$(cd "$(dirname "$0")/../../../.." && pwd)
D=$M/.build/dd-ios-0180-18pro
SIDE=$D/src/ios/BenchmarkApp
DM=$M/.build/dd-mac-q06cand
A=$D/Build/Products/Release-iphoneos/BenchmarkApp.app
R17=(Benchmark/BenchmarkRunner.swift Benchmark/BenchmarkTask.swift Benchmark/Tasks/LongContextTask.swift Models/BenchmarkResult.swift)
AS=$L/side-r17-aside
log(){ echo "[$(date '+%T')] $*" | tee -a "$OUT"; }

pgrep -x xcodebuild >/dev/null && { log "an xcodebuild is running; not building"; exit 3; }
cmp -s "$REPO/ios/BenchmarkApp/Sources/Models/ModelCatalog.swift" "$SIDE/Sources/Models/ModelCatalog.swift" \
  || { log "SIDE ModelCatalog.swift differs from the branch's; not building"; exit 4; }
want=$(printf '%s\n' "${R17[@]}" Models/ModelCatalog.swift | sort)
have=$(diff -rq "$SIDE/Sources" "$M/ios/BenchmarkApp/Sources" | sed -nE "s|^Files $SIDE/Sources/(.*) and .* differ$|\1|p" | sort)
[ "$have" = "$want" ] || { log "SIDE vs MAIN sources: expected r17's four files + ModelCatalog.swift, found:"; echo "$have" | tee -a "$OUT"; \
  diff -rq "$SIDE/Sources" "$M/ios/BenchmarkApp/Sources" | grep -v '^Files' | tee -a "$OUT"; exit 5; }
log "SIDE vs MAIN before: r17's four files + ModelCatalog.swift (as expected)"

# r17's files aside, MAIN's in; back on any exit
mkdir -p "$AS"; : > "$AS/sha256.txt"
for rel in "${R17[@]}"; do
  mkdir -p "$AS/$(dirname "$rel")"; cp -p "$SIDE/Sources/$rel" "$AS/$rel"
  echo "$(shasum -a 256 "$AS/$rel" | cut -d' ' -f1)  $rel" >> "$AS/sha256.txt"
  cp "$M/ios/BenchmarkApp/Sources/$rel" "$SIDE/Sources/$rel"
done
restore(){
  for rel in "${R17[@]}"; do cp -p "$AS/$rel" "$SIDE/Sources/$rel"; done
  ok=1
  while read -r sha rel; do [ "$(shasum -a 256 "$SIDE/Sources/$rel" | cut -d' ' -f1)" = "$sha" ] || ok=0; done < "$AS/sha256.txt"
  log "r17's four files restored in SIDE (sha256 check: $([ $ok -eq 1 ] && echo OK || echo MISMATCH))"
}
trap restore EXIT
left=$(diff -rq "$SIDE/Sources" "$M/ios/BenchmarkApp/Sources" | sed -nE "s|^Files $SIDE/Sources/(.*) and .* differ$|\1|p")
[ "$left" = "Models/ModelCatalog.swift" ] || { log "after the swap SIDE still differs from MAIN in: $left"; exit 6; }
log "SIDE vs MAIN for the builds: ModelCatalog.swift only"
log "pins before: MAIN $(shasum -a 256 "$M/ios/BenchmarkApp/Vendored/engine-pins.json" | cut -c1-16) SIDE $(shasum -a 256 "$SIDE/Vendored/engine-pins.json" | cut -c1-16)"

[ -e "$A.r19-1312" ] || cp -c -R "$A" "$A.r19-1312"
log "iPhone app before: $(stat -f %Sm -t '%m-%d %H:%M' "$A/BenchmarkApp") sha256 $(shasum -a 256 "$A/BenchmarkApp" | cut -c1-16) (kept as BenchmarkApp.app.r19-1312: $(shasum -a 256 "$A.r19-1312/BenchmarkApp" | cut -c1-16))"
if [ ! -d "$DM/SourcePackages" ]; then mkdir -p "$DM"; cp -c -R "$D/SourcePackages" "$DM/SourcePackages"; fi

cat > "$L/builds.sh" <<EOF
set -uo pipefail
cd "$SIDE"
echo "mac build start \$(date '+%T')"
gtimeout 1800 xcodebuild -project BenchmarkApp.xcodeproj -scheme yardstick -configuration Release -destination "platform=macOS,arch=arm64" \
  -derivedDataPath "$DM" -onlyUsePackageVersionsFromResolvedFile -skipPackagePluginValidation -skipMacroValidation \
  ARCHS=arm64 ONLY_ACTIVE_ARCH=YES build > "$L/mac-build.log" 2>&1
echo "mac build rc=\$? \$(date '+%T')"
echo "ios build start \$(date '+%T')"
gtimeout 1800 xcodebuild build -project BenchmarkApp.xcodeproj -scheme BenchmarkApp -configuration Release -destination generic/platform=iOS \
  -derivedDataPath "$D" -allowProvisioningUpdates -allowProvisioningDeviceRegistration -skipPackagePluginValidation -skipMacroValidation \
  DEVELOPMENT_TEAM=MFN25KNUGJ PRODUCT_BUNDLE_IDENTIFIER=com.example.CoreMLLLMChat > "$L/ios-build.log" 2>&1
echo "ios build rc=\$? \$(date '+%T')"
EOF
log "quiet_hold r18-q06cand-build start"
python3 "$HOME/code/standup/tools/quiet/quiet_hold.py" r18-q06cand-build -- bash "$L/builds.sh" 2>&1 | tee -a "$OUT"
for f in mac ios; do log "$f: $(grep -E '\*\* BUILD (SUCCEEDED|FAILED) \*\*' "$L/$f-build.log" | tail -1)"; grep -E '\.swift:[0-9]+:[0-9]+: error' "$L/$f-build.log" | head -3 | tee -a "$OUT"; done
log "pins after: MAIN $(shasum -a 256 "$M/ios/BenchmarkApp/Vendored/engine-pins.json" | cut -c1-16) SIDE $(shasum -a 256 "$SIDE/Vendored/engine-pins.json" | cut -c1-16)"
grep -q '\*\* BUILD SUCCEEDED \*\*' "$L/mac-build.log" && grep -q '\*\* BUILD SUCCEEDED \*\*' "$L/ios-build.log"
