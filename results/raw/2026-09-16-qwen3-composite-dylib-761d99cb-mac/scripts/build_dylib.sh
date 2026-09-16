#!/bin/zsh
# Build libLiteRtMetalAccelerator.dylib at LiteRT 761d99cb (Fengwu 2026-09-16 instruction), CI-style configure first.
set -x
LOG=$HOME/code/litertlm-convert/qwen3_gpuopt_work/logs/dylib_761d99cb
cd $HOME/code/LiteRT-761d99cb || exit 9
date
git log --oneline -1
cat .bazelversion
xcodebuild -version
xcode-select -p
PY=$HOME/venvs/lt094dev/bin/python3
[ -x "$PY" ] || PY=$HOME/venvs/lt093ctl/bin/python
$PY --version
export PYTHON_BIN_PATH=$PY
export PYTHON_LIB_PATH=$($PY -c 'import site; print(site.getsitepackages()[0])')
export TF_NEED_ROCM=0 TF_NEED_CUDA=0 TF_SET_ANDROID_WORKSPACE=0 CC_OPT_FLAGS='-Wno-sign-compare'
$PY configure.py < /dev/null 2>&1 | tail -25
echo "configure rc=${pipestatus[1]}"
cat .litert_configure.bazelrc 2>/dev/null
TARGET=//litert/runtime/accelerators/gpu:ml_drift_metal_accelerator_dylib
T0=$SECONDS
bazelisk build -c opt --config=darwin_arm64 $TARGET > $LOG/build_attempt1_darwin_arm64.log 2>&1
RC1=$?
echo "attempt1 --config=darwin_arm64 rc=$RC1 wall=$((SECONDS-T0))s"; tail -5 $LOG/build_attempt1_darwin_arm64.log
CFG=darwin_arm64
if [ $RC1 -ne 0 ]; then
  CFG=macos_arm64
  T0=$SECONDS
  bazelisk build -c opt --config=macos_arm64 $TARGET > $LOG/build_attempt2_macos_arm64.log 2>&1
  RC2=$?
  echo "attempt2 --config=macos_arm64 rc=$RC2 wall=$((SECONDS-T0))s"; grep -E "^(ERROR|FAILED)|Build completed|INFO: Elapsed|error:" $LOG/build_attempt2_macos_arm64.log | tail -20
fi
bazelisk version 2>&1 | grep -E "Build label|Bazelisk"
OUT=bazel-bin/litert/runtime/accelerators/gpu/libLiteRtMetalAccelerator.dylib
ls -la $OUT
shasum -a 256 $OUT
otool -L $OUT | head -20
echo "BUILD_DONE config=$CFG"
date
