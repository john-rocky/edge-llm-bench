#!/usr/bin/env bash
# Builds the asr-qnn-v1 A2 arm's phone binaries from source (docs/asr-qnn-v1.md):
#   1. sherpa-onnx v1.13.8 (tag commit 11afbd00) with the Qualcomm NPU (QNN) and its executables, as
#      sherpa's docs build it: SHERPA_ONNX_ENABLE_QNN=ON SHERPA_ONNX_ENABLE_BINARY=ON ./build-android-arm64-v8a.sh
#      (QNN_SDK_ROOT = the QAIRT that made the model's context binary, fetch.sh; the script downloads
#      onnxruntime itself). The sherpa tree is not modified.
#   2. tools/asr-qnn/burst_driver.cc against the same build: compiled with the flags CMake generated for
#      sherpa-onnx-offline and linked with that target's link line, its object swapped for the driver's.
#      v1.13.8's C / C++ / JNI APIs carry no QNN settings for a NeMo CTC model, so the driver uses the
#      classes the executables use (sherpa-onnx/csrc).
#   3. the driver's host self-test (pacing, cap rule, JSON) with the Mac's clang: burst_driver.cc -DHOST_TEST.
#
#   tools/asr-qnn/build.sh [all|sherpa|driver|hosttest]      (default all)
#
# Env: ANDROID_NDK (default ~/Library/Android/sdk/ndk/28.2.13676358), B (default <repo>/.build/asr-qnn).
# Run it behind the Mac quiet window (quiet_hold.py): the sherpa build is minutes of 4 compile jobs.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
repo=$(cd "$here/../.." && pwd)
B=${B:-$repo/.build/asr-qnn}
SRC=$B/src/sherpa-onnx
TAG=v1.13.8
COMMIT=11afbd009a7f8c08f4bcf2fc1b265d0df4670fbf
QNN_SDK_ROOT=${QNN_SDK_ROOT:-$B/extract/qairt/qairt/2.40.0.251030}
ANDROID_NDK=${ANDROID_NDK:-$HOME/Library/Android/sdk/ndk/28.2.13676358}
OUT=$B/build-out
step=${1:-all}

say() { echo "$(date '+%H:%M:%S') $*"; }

sherpa() {
  [ -f "$QNN_SDK_ROOT/include/QNN/QnnInterface.h" ] || { echo "no QAIRT headers at $QNN_SDK_ROOT: run fetch.sh" >&2; exit 1; }
  if [ ! -d "$SRC/.git" ]; then
    mkdir -p "$(dirname "$SRC")"
    git -c advice.detachedHead=false clone --depth 1 --branch "$TAG" https://github.com/k2-fsa/sherpa-onnx.git "$SRC"
  fi
  local head
  head=$(git -C "$SRC" rev-parse HEAD)
  [ "$head" = "$COMMIT" ] || { echo "sherpa-onnx HEAD $head is not $TAG ($COMMIT)" >&2; exit 1; }
  [ -z "$(git -C "$SRC" status --porcelain --untracked-files=no)" ] || { echo "the sherpa-onnx tree is modified" >&2; exit 1; }
  mkdir -p "$B/logs"
  # The script's default platform android-21 cannot link the executables with NDK 28: the prebuilt
  # libonnxruntime.so 1.28.2 it downloads needs libc symbols of API 23-24 (__write_chk@LIBC_N, stderr@LIBC,
  # ...) and lld refuses them for an executable (--no-allow-shlib-undefined). sherpa's CI builds the
  # libraries only (no executables), its docs used NDK 22.1. The script's own knob picks API 24; the S26 runs
  # API 36. A build dir configured for another platform is removed first (the toolchain is fixed at configure).
  local platform=${SHERPA_ONNX_ANDROID_PLATFORM:-android-24}
  local cache=$SRC/build-android-arm64-v8a/CMakeCache.txt
  if [ -f "$cache" ] && ! grep -q "^ANDROID_PLATFORM:UNINITIALIZED=$platform\$" "$cache"; then
    say "removing $SRC/build-android-arm64-v8a (configured for $(sed -n 's/^ANDROID_PLATFORM:UNINITIALIZED=//p' "$cache"))"
    rm -rf "$SRC/build-android-arm64-v8a"
  fi
  say "sherpa-onnx $TAG ($head) with QNN_SDK_ROOT=$QNN_SDK_ROOT ANDROID_NDK=$ANDROID_NDK platform=$platform"
  # CMake 4 refuses projects that declare cmake_minimum_required below 3.5 (some fetched dependencies);
  # CMAKE_POLICY_VERSION_MINIMUM=3.5 lets them configure (policy defaults only, no source change).
  (cd "$SRC" && env SHERPA_ONNX_ENABLE_QNN=ON SHERPA_ONNX_ENABLE_BINARY=ON ANDROID_NDK="$ANDROID_NDK" \
      QNN_SDK_ROOT="$QNN_SDK_ROOT" SHERPA_ONNX_ANDROID_PLATFORM="$platform" CMAKE_POLICY_VERSION_MINIMUM=3.5 \
      ./build-android-arm64-v8a.sh) \
    > "$B/logs/sherpa-build.log" 2>&1 || { tail -n 40 "$B/logs/sherpa-build.log" >&2; exit 1; }
  say "sherpa-onnx built: $(ls "$SRC/build-android-arm64-v8a/install/bin" | wc -l | tr -d ' ') executables"
  (cd "$SRC/build-android-arm64-v8a/install" && shasum -a 256 bin/sherpa-onnx-offline-parallel bin/sherpa-onnx-offline bin/sherpa-onnx-version lib/libonnxruntime.so)
}

flag_of() {  # <flags.make> <NAME>: the value of "NAME = ..." in a CMake flags.make
  sed -n "s/^$2 = //p" "$1"
}

driver() {
  local bdir=$SRC/build-android-arm64-v8a
  local tdir=$bdir/sherpa-onnx/csrc/CMakeFiles/sherpa-onnx-offline.dir
  [ -f "$tdir/flags.make" ] && [ -f "$tdir/link.txt" ] || { echo "no sherpa-onnx-offline target in $bdir: build sherpa first" >&2; exit 1; }
  local rule cxx defines includes flags obj link
  # The compile rule of sherpa-onnx-offline.cc.o in build.make: "cd <dir> && <clang++ --target=... --sysroot=...>
  # $(CXX_DEFINES) $(CXX_INCLUDES) $(CXX_FLAGS) ... -c <source>"; the compiler words are the part before $(CXX_DEFINES).
  rule=$(grep -m1 -F 'sherpa-onnx-offline.cc.o -c ' "$tdir/build.make")
  cxx=${rule#*&& }
  cxx=${cxx%% \$(CXX_DEFINES)*}
  defines=$(flag_of "$tdir/flags.make" CXX_DEFINES)
  includes=$(flag_of "$tdir/flags.make" CXX_INCLUDES)
  flags=$(flag_of "$tdir/flags.make" CXX_FLAGS)
  case $cxx in *clang++*--target=aarch64*) ;; *) echo "could not read the compile rule: $cxx" >&2; exit 1 ;; esac
  mkdir -p "$OUT"
  obj=$OUT/burst_driver.cc.o
  say "driver: compile with sherpa-onnx-offline's rule ($cxx)"
  # The generated lines are shell words (quoted paths included): eval keeps their quoting.
  (cd "$bdir/sherpa-onnx/csrc" && eval "$cxx $defines $includes $flags -o \"$obj\" -c \"$here/burst_driver.cc\"")
  # link.txt: "<compiler> <flags> <objects of sherpa-onnx-offline> -o ../../bin/sherpa-onnx-offline <libs>"
  link=$(sed -e "s#CMakeFiles/sherpa-onnx-offline.dir/sherpa-onnx-offline.cc.o#$obj#" \
             -e "s#--dependency-file=CMakeFiles/sherpa-onnx-offline.dir/link.d#--dependency-file=$OUT/link.d#" \
             -e "s#-o \\.\\./\\.\\./bin/sherpa-onnx-offline #-o $OUT/asr-qnn-burst-driver #" "$tdir/link.txt")
  case $link in *"$obj"*"$OUT/asr-qnn-burst-driver"*) ;; *) echo "could not rewrite link.txt: $link" >&2; exit 1 ;; esac
  # CMake runs link.txt itself (no shell: "-Wl,-rpath,$ORIGIN/../lib" stays literal); so does this.
  printf '%s\n' "$link" > "$OUT/link.txt"
  (cd "$bdir/sherpa-onnx/csrc" && cmake -E cmake_link_script "$OUT/link.txt" --verbose=1)
  # install/strip strips the executables; the driver gets the same.
  local strip
  strip=$(sed -n 's/^CMAKE_STRIP:FILEPATH=//p' "$bdir/CMakeCache.txt")
  cp "$OUT/asr-qnn-burst-driver" "$OUT/asr-qnn-burst-driver.unstripped"
  "$strip" "$OUT/asr-qnn-burst-driver"
  say "driver built: $(shasum -a 256 "$OUT/asr-qnn-burst-driver")"
}

hosttest() {
  mkdir -p "$OUT"
  clang++ -std=c++17 -O1 -Wall -Wextra -DHOST_TEST -o "$OUT/burst_driver_hosttest" "$here/burst_driver.cc" -lpthread
  "$OUT/burst_driver_hosttest"
}

case $step in
  all) sherpa; driver; hosttest ;;
  sherpa) sherpa ;;
  driver) driver ;;
  hosttest) hosttest ;;
  *) echo "unknown step $step (all|sherpa|driver|hosttest)" >&2; exit 2 ;;
esac
