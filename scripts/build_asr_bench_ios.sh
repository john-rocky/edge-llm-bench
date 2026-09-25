#!/usr/bin/env bash
# Builds the static library behind ios/AsrBench (the asr-rtf-* iPhone leg) from a LiteRT-LM
# worktree and stages it, the shim header and the commit's prebuilt iOS Metal accelerator
# under ios/AsrBench/Frameworks/, then regenerates the Xcode project with xcodegen.
#
#   scripts/build_asr_bench_ios.sh ~/code/litert-lm-asr-ios-wt        # a worktree at the pinned commit
#
# The worktree must carry bench_ios/ (the shim + BUILD; copy from tools/asr-bench-ios/ when it is
# not there yet) and prebuilt/ios_arm64/libLiteRtMetalAccelerator.dylib pulled from LFS
# (`git lfs pull origin --include=prebuilt/ios_arm64/libLiteRtMetalAccelerator.dylib`).
# bazel --config=ios_arm64 is 30-60 min from a cold output base (bazel 7.6.1 via bazelisk, Xcode 27).
set -euo pipefail
WT="${1:?usage: build_asr_bench_ios.sh <litert-lm worktree>}"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
APP="$REPO/ios/AsrBench"
if [ ! -d "$WT/bench_ios" ]; then
  mkdir -p "$WT/bench_ios"
  cp "$REPO/tools/asr-bench-ios/BUILD" "$REPO/tools/asr-bench-ios/asr_bench_shim.h" "$REPO/tools/asr-bench-ios/asr_bench_shim.cc" "$WT/bench_ios/"
fi
COMMIT="$(git -C "$WT" rev-parse --short=8 HEAD)"
(cd "$WT" && bazelisk build --config=ios_arm64 //bench_ios:asr_bench_static)
mkdir -p "$APP/Frameworks/include"
LIB="$(ls "$WT"/bazel-bin/bench_ios/*asr_bench_static*.a | head -1)"
cp "$LIB" "$APP/Frameworks/libasr_bench_static.a"
cp "$WT/bench_ios/asr_bench_shim.h" "$APP/Frameworks/include/"
cp "$WT/prebuilt/ios_arm64/libLiteRtMetalAccelerator.dylib" "$APP/Frameworks/"
cp "$WT/omni/asr/model_metadata.json" "$APP/Frameworks/"
mkdir -p "$REPO/.build/asr-runner-$COMMIT-ios"
cp "$WT/omni/asr/model_metadata.json" "$REPO/.build/asr-runner-$COMMIT-ios/"
echo "main@$COMMIT (LiteRT-LM $(git -C "$WT" log -1 --format='%cd %s' --date=short | cut -c1-80); bench_ios/asr_bench_shim over //omni/asr:asr_engine, bazel --config=ios_arm64, $(date '+%F %T'))" > "$APP/Frameworks/BUILD_INFO"
(cd "$APP/Frameworks" && shasum -a 256 libasr_bench_static.a libLiteRtMetalAccelerator.dylib model_metadata.json > SHA256SUMS)
cp "$APP/Frameworks/BUILD_INFO" "$APP/Frameworks/SHA256SUMS" "$REPO/.build/asr-runner-$COMMIT-ios/"
(cd "$APP" && xcodegen generate >/dev/null)
echo "staged: $APP/Frameworks ($(cat "$APP/Frameworks/BUILD_INFO"))"
