#!/bin/bash
# Builds a lab build of the bench app with its XCTest, and zips it the way Developer Device Platform
# takes an iOS test (https://docs.cloud.google.com/developer-device-platform/device-run/ios): the
# Release products directory and the .xctestrun manifest at the root of the archive, plus BUILD_INFO
# (the engine the app carries and the build's identity), which run_ddp_ios_lm.py copies into every
# record. The test action builds Release, so the archive holds the build the rows come from.
# xcodebuild signs the app once here (DDP refuses an unsigned archive: IOS_APP_SIGNING_ERROR); the lab
# re-signs it.
#
# One arm per archive (--engine; the arms' static libraries are not linked together):
#   litert      ios/BenchmarkApp/project-ddp.yml             Vendored/LiteRT-LM (the tag's checkout +
#               ios/BenchmarkApp/patches/litert-lm-swift-benchmark-maxnumtokens.patch: scripts/bootstrap.sh
#               step 3, LITERTLM_TAG=v0.18.0)
#   llamacpp    ios/BenchmarkApp/project-ddp-llamacpp.yml    Vendored/llama.xcframework (+ .tag)
#   executorch  ios/BenchmarkApp/project-ddp-executorch.yml  Vendored/executorch (the package
#               ios/ddp/make_executorch_package.sh makes from a checkout's locally built frameworks)
#   mlx         ios/BenchmarkApp/project-ddp-mlx.yml         (SwiftPM; Swift tools 6.3 + Metal toolchain)
#
# Usage: [--engine litert|llamacpp|executorch|mlx] [<out.zip>]
#   Signing (env): DEVELOPMENT_TEAM=<Apple team id> (required); BUNDLE_ID=<app bundle id> (default
#   com.iosllmbenchmark.benchmarkapp.ddp, the test bundle takes ".tests"); for a manual profile instead
#   of Automatic signing: PROVISIONING_PROFILE=<uuid or name> [CODE_SIGN_IDENTITY="Apple Development"]
#   [ENTITLEMENTS=<file>|"" to drop the memory entitlements a wildcard profile cannot carry].
#   SWIFT_CONDITIONS="<cond> ..." adds Swift compilation conditions (e.g. LITERTLM_YNNPACK for a
#   LiteRT-LM built with YNNPACK, which enables the app's --litert-ynnpack flag).
#   DEVELOPER_DIR picks the Xcode when several are installed. With xcodegen on PATH (or XCODEGEN=<bin>)
#   the engine's spec is generated first; otherwise its .xcodeproj must exist.
# Default output: ios/ddp/out/BenchmarkApp-ddp[-<engine>]-xctest.zip; derived data in
# ios/ddp/out/build[-<engine>], removed first.
# Exit status: 1 without DEVELOPMENT_TEAM, a bad flag, or when xcodebuild or zip fail; 2 without the
# engine's vendored inputs; 3 when xcodebuild wrote no manifest or no Release products.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
APP_DIR="$REPO/ios/BenchmarkApp"
ENGINE="litert"
OUT=""
while [ $# -gt 0 ]; do
  case "$1" in
    --engine) ENGINE="${2:?--engine needs a value}"; shift 2 ;;
    --engine=*) ENGINE="${1#*=}"; shift ;;
    -*) echo "unknown flag $1" >&2; exit 1 ;;
    *) OUT="$1"; shift ;;
  esac
done
case "$ENGINE" in
  litert)     SPEC=project-ddp.yml;            SUFFIX="";             PIN_KEY="litert-lm" ;;
  llamacpp)   SPEC=project-ddp-llamacpp.yml;   SUFFIX="-llamacpp";    PIN_KEY="llama.cpp" ;;
  executorch) SPEC=project-ddp-executorch.yml; SUFFIX="-executorch";  PIN_KEY="executorch" ;;
  mlx)        SPEC=project-ddp-mlx.yml;        SUFFIX="-mlx";         PIN_KEY="mlx-swift" ;;
  *) echo "--engine $ENGINE: litert, llamacpp, executorch or mlx" >&2; exit 1 ;;
esac
: "${DEVELOPMENT_TEAM:?set DEVELOPMENT_TEAM to your Apple team id (xcodebuild signs the app before the lab re-signs it)}"
PROJECT="$APP_DIR/BenchmarkApp-ddp$SUFFIX.xcodeproj"
OUT="${OUT:-$HERE/out/BenchmarkApp-ddp$SUFFIX-xctest.zip}"
case "$OUT" in *.zip) ;; *) OUT="$OUT.zip";; esac  # zip appends the suffix itself otherwise
BUILD="$HERE/out/build$SUFFIX"
V="$APP_DIR/Vendored"

case "$ENGINE" in
  litert)
    LITERT="$V/LiteRT-LM"
    if [ ! -f "$LITERT/Package.swift" ]; then
      echo "no $LITERT: GIT_LFS_SKIP_SMUDGE=1 git clone --depth 1 --branch v0.18.0" \
        "https://github.com/google-ai-edge/LiteRT-LM.git $LITERT, then apply the patch below" >&2
      exit 2
    fi
    if ! grep -q "maxNumTokens: Int? = nil" "$LITERT/swift/Benchmark.swift"; then
      echo "$LITERT is not patched: git -C $LITERT apply $APP_DIR/patches/litert-lm-swift-benchmark-maxnumtokens.patch" >&2
      exit 2
    fi ;;
  llamacpp)
    if [ ! -d "$V/llama.xcframework" ]; then
      echo "no $V/llama.xcframework: scripts/bootstrap.sh step 1 (release zip) or a source build" >&2
      exit 2
    fi ;;
  executorch)
    if [ ! -f "$V/executorch/Package.swift" ] || [ ! -d "$V/executorch/Frameworks/backend_mlx.xcframework" ]; then
      echo "no $V/executorch package: build ExecuTorch's frameworks from source" \
        "(scripts/build_apple_frameworks.sh --Release --xnnpack --mlx --llm --optimized --quantized)," \
        "then ios/ddp/make_executorch_package.sh <checkout>" >&2
      exit 2
    fi ;;
esac

XCODEGEN="${XCODEGEN:-$(command -v xcodegen || true)}"
if [ -n "$XCODEGEN" ]; then
  (cd "$APP_DIR" && "$XCODEGEN" generate --spec "$SPEC")
elif [ ! -d "$PROJECT" ]; then
  echo "no $PROJECT and no xcodegen: xcodegen generate --spec $SPEC" >&2
  exit 2
fi

# The sources as built: the tree id of ios/BenchmarkApp (tracked and untracked files, .gitignore
# applied), comparable with `git rev-parse <commit>:ios/BenchmarkApp` once they are committed.
INDEX="$(mktemp)"
rm -f "$INDEX"
SOURCE_TREE="$(cd "$REPO" && GIT_INDEX_FILE="$INDEX" git add -A -- ios/BenchmarkApp \
  && GIT_INDEX_FILE="$INDEX" git write-tree --prefix=ios/BenchmarkApp/ 2>/dev/null || echo unread)"
rm -f "$INDEX"

SIGN=(DEVELOPMENT_TEAM="$DEVELOPMENT_TEAM")
if [ -n "${SWIFT_CONDITIONS:-}" ]; then SIGN+=(DDP_SWIFT_CONDITIONS="$SWIFT_CONDITIONS"); fi
if [ -n "${BUNDLE_ID:-}" ]; then SIGN+=(DDP_BUNDLE_ID="$BUNDLE_ID"); fi
if [ -n "${PROVISIONING_PROFILE:-}" ]; then
  SIGN+=(DDP_CODE_SIGN_STYLE=Manual DDP_PROVISIONING_PROFILE="$PROVISIONING_PROFILE"
         DDP_CODE_SIGN_IDENTITY="${CODE_SIGN_IDENTITY:-Apple Development}")
else
  SIGN+=(-allowProvisioningUpdates)
fi
if [ "${ENTITLEMENTS+set}" = set ]; then
  # An empty CODE_SIGN_ENTITLEMENTS still signs with the memory entitlements, so "" selects an
  # empty entitlements file instead.
  SIGN+=(DDP_ENTITLEMENTS="${ENTITLEMENTS:-BenchmarkAppDDP-NoMemoryLimits.entitlements}")
fi

rm -rf "$BUILD"
# Package plug-ins and macros (mlx-swift's CudaBuild, swift-syntax) are trusted here: the build is
# non-interactive, so Xcode cannot ask.
xcodebuild build-for-testing -project "$PROJECT" -scheme BenchmarkAppDDP \
  -destination "generic/platform=iOS" -derivedDataPath "$BUILD" \
  -skipPackagePluginValidation -skipMacroValidation "${SIGN[@]}"
PRODUCTS="$BUILD/Build/Products"
APP="$PRODUCTS/Release-iphoneos/BenchmarkAppDDP.app"
if ! ls "$PRODUCTS"/*.xctestrun >/dev/null 2>&1 || [ ! -d "$APP" ]; then
  echo "xcodebuild left no .xctestrun or no Release-iphoneos/BenchmarkAppDDP.app under $PRODUCTS; nothing to submit" >&2
  exit 3
fi
pin() {  # the app's own engine-pins.json (what its records stamp): <engine>.<key>
  # (not plutil -extract: its key path splits "llama.cpp" at the dot)
  /usr/bin/python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))[sys.argv[2]][sys.argv[3]])' \
    "$APP/engine-pins.json" "$PIN_KEY" "$1" 2>/dev/null || echo unread
}
{
  echo "engine=$ENGINE"
  echo "engine_runtime=$PIN_KEY"
  echo "engine_version=$(pin version)"
  echo "engine_artifact=$(pin artifact)"
  if [ "$ENGINE" = litert ]; then  # the keys run_ddp_ios_lm.py reads for the LiteRT-LM arm
    echo "litert_lm=$(pin version)"
    echo "litert_lm_artifact=$(pin artifact)"
  fi
  echo "app=$(/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "$APP/Info.plist") (BenchmarkAppDDP, $SPEC, Release, iOS 18.0 floor)"
  echo "signing=$(codesign -dvv "$APP" 2>&1 | sed -n 's/^Authority=//p' | head -1)"
  echo "xcode=$(xcodebuild -version | tr '\n' ' ' | sed 's/ *$//')"
  echo "sdk=iphoneos$(xcrun --sdk iphoneos --show-sdk-version)"
  echo "commit=$(git -C "$REPO" rev-parse HEAD 2>/dev/null || echo unread)"
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
