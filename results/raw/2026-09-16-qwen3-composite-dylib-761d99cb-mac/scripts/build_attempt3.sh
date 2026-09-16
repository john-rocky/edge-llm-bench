#!/bin/zsh
set -x
LOG=$HOME/code/litertlm-convert/qwen3_gpuopt_work/logs/dylib_761d99cb
cd $HOME/code/LiteRT-761d99cb || exit 9
date
git status --short
cat tools/build_defs/swift/BUILD
TARGET=//litert/runtime/accelerators/gpu:ml_drift_metal_accelerator_dylib
T0=$SECONDS
bazelisk build -c opt --config=macos_arm64 $TARGET > $LOG/build_attempt3_macos_arm64_stub.log 2>&1
RC=$?
echo "attempt3 --config=macos_arm64 (+swift stub) rc=$RC wall=$((SECONDS-T0))s"
grep -E "^(ERROR|FAILED)|Build completed|INFO: Elapsed|error:|actions" $LOG/build_attempt3_macos_arm64_stub.log | tail -20
OUT=bazel-bin/litert/runtime/accelerators/gpu/libLiteRtMetalAccelerator.dylib
ls -la $OUT
shasum -a 256 $OUT
otool -L $OUT | head -20
echo "BUILD3_DONE rc=$RC"
date
