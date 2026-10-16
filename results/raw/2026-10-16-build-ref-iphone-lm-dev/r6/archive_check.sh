#!/bin/bash
# K/r6/archive-check.txt: the checks of K/r3/archive-check.txt on the archive ios/ddp/out/BenchmarkApp-ddp-xctest.zip,
# plus the harness's thermal gate strings in the app binary. Usage: archive_check.sh <repo> <scratch dir>
# The archive is unzipped into <scratch dir>/archive (removed first); the output has the home directory as ~.
set -euo pipefail
REPO="$1"
X="$2/archive"
ZIP="$REPO/ios/ddp/out/BenchmarkApp-ddp-xctest.zip"
APP="$X/Release-iphoneos/BenchmarkAppDDP.app"
XCF="$REPO/ios/ddp/out/build/SourcePackages/artifacts/litert-lm/CLiteRTLM/CLiteRTLM.xcframework"
rm -rf "$X"
mkdir -p "$X"
unzip -q "$ZIP" -d "$X"
{
  echo "# $(date '+%Y-%m-%d %H:%M:%S %Z') archive checks (home -> ~)"
  echo "## archive"
  echo "bytes: $(stat -f '%z' "$ZIP")"
  echo "sha256: $(shasum -a 256 "$ZIP" | cut -d' ' -f1)"
  echo "## unzip -l (top entries)"
  unzip -l "$ZIP" | awk '{print $4}' | grep -E '^(Release-iphoneos/BenchmarkAppDDP\.app/([^/]+|(Frameworks|PlugIns)/[^/]+/)|[^/]+\.xctestrun|BUILD_INFO)$' \
    | grep -v -E '/(_CodeSignature|[^/]+\.lproj)/$' || true
  echo "entries: $(unzip -l "$ZIP" | tail -1 | sed 's/^ *//')"
  echo "## BUILD_INFO"
  cat "$X/BUILD_INFO"
  echo "## app Frameworks/"
  ls "$APP/Frameworks"
  echo "## PlugIns/"
  ls "$APP/PlugIns"
  echo "## engine-pins.json in the app"
  cat "$APP/engine-pins.json"
  echo "## codesign -d --entitlements - (app)"
  codesign -d --entitlements - "$APP" 2>/dev/null | sed -n '/^\[Dict\]/,$p;/^{/,/^}/p' | grep -v '^\[' || true
  echo "## embedded.mobileprovision"
  security cms -D -i "$APP/embedded.mobileprovision" > "$X/profile.plist" 2>/dev/null
  for k in Name UUID TeamIdentifier.0 ExpirationDate Entitlements.application-identifier \
           'Entitlements.com\.apple\.developer\.kernel\.increased-memory-limit' \
           'Entitlements.com\.apple\.developer\.kernel\.extended-virtual-addressing' Entitlements.get-task-allow; do
    echo "$k = $(plutil -extract "$k" raw -o - "$X/profile.plist" 2>/dev/null || echo unread)"
  done
  echo "## .xctestrun"
  plutil -p "$X"/*.xctestrun | grep -E 'FormatVersion|TestBundlePath|TestHostBundleIdentifier|TestHostPath'
  echo "## test bundle signature"
  codesign -dv "$APP/PlugIns/BenchmarkAppDDPTests.xctest" 2>&1 | grep -E '^(Identifier|Format|TeamIdentifier)='
  echo "## the harness's thermal gate in the app binary (strings)"
  strings "$APP/BenchmarkAppDDP" | grep -E 'thermal_gate|waited_s=|timed_out=' | sort -u
  echo "## CLiteRTLM: the embedded binary against the v0.18.0 xcframework (LC_UUID)"
  echo "xcframework ios-arm64 = $(dwarfdump --uuid "$XCF/ios-arm64/CLiteRTLM.framework/CLiteRTLM" | awk '{print $2}')"
  echo "embedded            = $(dwarfdump --uuid "$APP/Frameworks/CLiteRTLM.framework/CLiteRTLM" | awk '{print $2}')"
} 2>&1 | sed "s#$HOME#~#g"
