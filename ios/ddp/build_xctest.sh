#!/bin/bash
# Builds the lab build of the bench app (ios/BenchmarkApp/project-ddp.yml: the LiteRT-LM arm, iOS 18.0
# floor) with its XCTest, and zips them the way Developer Device Platform takes an iOS test
# (https://docs.cloud.google.com/developer-device-platform/device-run/ios): the Release products
# directory and the .xctestrun manifest at the root of the archive, plus BUILD_INFO (the engine the
# app carries and the build's identity), which run_ddp_ios_lm.py copies into every record. The test
# action builds Release, so the archive holds the build the rows come from. xcodebuild signs the app
# once here; the lab re-signs it.
#
# Usage: DEVELOPMENT_TEAM=<Apple team id> [BUNDLE_ID=<app bundle id>] [DEVELOPER_DIR=<Xcode.app>] \
#          ios/ddp/build_xctest.sh [<out.zip>]
# Needs ios/BenchmarkApp/Vendored/LiteRT-LM (the tag's checkout with
# ios/BenchmarkApp/patches/litert-lm-swift-benchmark-maxnumtokens.patch applied: scripts/bootstrap.sh
# step 3, LITERTLM_TAG=v0.18.0) and Xcode. DEVELOPER_DIR picks the Xcode when several are installed;
# the lab runs Xcode 26.2 by default, and the project resolves with Xcode 26 (no MLX in it).
# BUNDLE_ID (default com.iosllmbenchmark.benchmarkapp.ddp, project-ddp.yml's DDP_BUNDLE_ID) is the
# app's id; the test bundle takes it with ".tests" appended. Default output:
# ios/ddp/out/BenchmarkApp-ddp-xctest.zip; the derived data is ios/ddp/out/build, removed first.
# Exit status: 1 without DEVELOPMENT_TEAM or when xcodebuild or zip fail, 2 without the vendored
# LiteRT-LM checkout or its patch, 3 when xcodebuild wrote no manifest or no Release products.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
APP_DIR="$REPO/ios/BenchmarkApp"
: "${DEVELOPMENT_TEAM:?set DEVELOPMENT_TEAM to your Apple team id (xcodebuild signs the app before the lab re-signs it)}"
OUT="${1:-$HERE/out/BenchmarkApp-ddp-xctest.zip}"
case "$OUT" in *.zip) ;; *) OUT="$OUT.zip";; esac  # zip appends the suffix itself otherwise
BUILD="$HERE/out/build"
LITERT="$APP_DIR/Vendored/LiteRT-LM"
if [ ! -f "$LITERT/Package.swift" ]; then
  echo "no $LITERT: GIT_LFS_SKIP_SMUDGE=1 git clone --depth 1 --branch v0.18.0" \
    "https://github.com/google-ai-edge/LiteRT-LM.git $LITERT, then apply the patch below" >&2
  exit 2
fi
if ! grep -q "maxNumTokens: Int? = nil" "$LITERT/swift/Benchmark.swift"; then
  echo "$LITERT is not patched: git -C $LITERT apply $APP_DIR/patches/litert-lm-swift-benchmark-maxnumtokens.patch" >&2
  exit 2
fi
# The sources as built: the tree id of ios/BenchmarkApp (tracked and untracked files, .gitignore
# applied), comparable with `git rev-parse <commit>:ios/BenchmarkApp` once they are committed.
INDEX="$(mktemp)"
rm -f "$INDEX"
SOURCE_TREE="$(cd "$REPO" && GIT_INDEX_FILE="$INDEX" git add -A -- ios/BenchmarkApp \
  && GIT_INDEX_FILE="$INDEX" git write-tree --prefix=ios/BenchmarkApp/)"
rm -f "$INDEX"

rm -rf "$BUILD"
xcodebuild build-for-testing -project "$APP_DIR/BenchmarkApp-ddp.xcodeproj" -scheme BenchmarkAppDDP \
  -destination "generic/platform=iOS" -derivedDataPath "$BUILD" -allowProvisioningUpdates \
  DEVELOPMENT_TEAM="$DEVELOPMENT_TEAM" ${BUNDLE_ID:+DDP_BUNDLE_ID="$BUNDLE_ID"}
PRODUCTS="$BUILD/Build/Products"
APP="$PRODUCTS/Release-iphoneos/BenchmarkAppDDP.app"
if ! ls "$PRODUCTS"/*.xctestrun >/dev/null 2>&1 || [ ! -d "$APP" ]; then
  echo "xcodebuild left no .xctestrun or no Release-iphoneos/BenchmarkAppDDP.app under $PRODUCTS; nothing to submit" >&2
  exit 3
fi
pin() {  # the app's own engine-pins.json (what its records stamp): litert-lm.<key>
  /usr/bin/plutil -extract "litert-lm.$1" raw -o - "$APP/engine-pins.json" 2>/dev/null || echo unread
}
{
  echo "litert_lm=$(pin version)"
  echo "litert_lm_artifact=$(pin artifact)"
  echo "app=$(/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "$APP/Info.plist") (BenchmarkAppDDP, Release, iOS 18.0 floor)"
  echo "xcode=$(xcodebuild -version | tr '\n' ' ' | sed 's/ *$//')"
  echo "sdk=iphoneos$(xcrun --sdk iphoneos --show-sdk-version)"
  echo "commit=$(git -C "$REPO" rev-parse HEAD)"
  echo "ios_benchmarkapp_tree=$SOURCE_TREE"
  echo "built=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "host_arch=$(uname -m)"
} > "$PRODUCTS/BUILD_INFO"
cat "$PRODUCTS/BUILD_INFO"
mkdir -p "$(dirname "$OUT")"
OUT="$(cd "$(dirname "$OUT")" && pwd)/$(basename "$OUT")"  # zip runs from the products directory
rm -f "$OUT"
(cd "$PRODUCTS" && zip -qrMM "$OUT" Release-iphoneos ./*.xctestrun BUILD_INFO -x "*.dSYM/*")
echo "test archive: $OUT ($(du -h "$OUT" | cut -f1))"
