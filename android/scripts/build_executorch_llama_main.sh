#!/usr/bin/env bash
# Build ExecuTorch's llama_main (examples/models/llama) for android arm64-v8a at a pinned tag.
#
# ExecuTorch releases ship no Android runner binary (v1.5.1 GitHub release assets:
# PyTorch.ExecuTorch.1.5.1.pack and PyTorch.ExecuTorch.pdsc only, read 2026-10-07), so the
# Android arm is a per-release source build that follows the tag's own recipe:
# examples/models/llama/README.md "Step 4: Run benchmark on Android phone" = two CMake
# stages (ExecuTorch built and installed into cmake-out-android, then examples/models/llama
# built against that install). The flags below are that README's; ET_BACKEND=vulkan adds
# EXECUTORCH_BUILD_VULKAN=ON and builds into its own directory.
#
# No preset file is passed (the README passes none), so EXECUTORCH_PAL_DEFAULT stays posix
# and ET_LOG lines (backend registration, threadpool size, Stats report) go to stderr. The
# android-arm64-v8a preset would set the android PAL, which sends them to logcat instead.
#
# Prerequisites (owner machine, one-time):
#   - an ExecuTorch checkout at the tag with the build's submodules, in a directory named
#     exactly `executorch` (the tag's CMakeLists.txt refuses any other name, pytorch/executorch#6475)
#   - Android NDK r28c (the README's tested NDK; Android Studio SDK manager)
#   - a python whose torch wheel matches the tag's torch_pin.py (kernel codegen imports
#     torchgen and reads its native_functions.yaml) and has pyyaml
#   - vulkan only: a glslc that supports GL_EXT_integer_dot_product (brew install shaderc);
#     the NDK's shader-tools glslc does not
#
# Env:
#   ET_TAG          tag to build (default: v1.5.1)
#   ET_BACKEND      xnnpack | vulkan (default: xnnpack)
#   ET_SRC          checkout dir, basename `executorch`
#                   (default: ~/.cache/apple-silicon-llm-bench/executorch-<tag>/executorch)
#   ANDROID_NDK     NDK path (default: ~/Library/Android/sdk/ndk/28.2.13676358, else the newest there)
#   ET_PYTHON       python for the codegen (default: python3)
#   GLSLC           vulkan only (default: glslc on PATH)
#   ET_JOBS         parallel build jobs (default: 16, as in the README)
#   BENCH_BIN_ROOT  where engine binaries live (default: <repo>/android/bin)
#
# Output: <BENCH_BIN_ROOT>/executorch-<tag>/ (xnnpack) or executorch-<tag>-vulkan/: llama_main,
# SHA256SUMS, BUILD_INFO.json (requested tag, observed describe, flags of both stages, toolchain).
# The pin registry (android/engine-pins.json) is not written here; the witness entry is printed
# for whoever registers it.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TAG="${ET_TAG:-v1.5.1}"
BACKEND="${ET_BACKEND:-xnnpack}"
SRC="${ET_SRC:-$HOME/.cache/apple-silicon-llm-bench/executorch-$TAG/executorch}"
PY="${ET_PYTHON:-python3}"
JOBS="${ET_JOBS:-16}"
BIN_ROOT="${BENCH_BIN_ROOT:-$REPO_ROOT/android/bin}"

case "$BACKEND" in
  xnnpack) BUILD_DIR=cmake-out-android; OUT="$BIN_ROOT/executorch-$TAG" ;;
  vulkan)  BUILD_DIR=cmake-out-android-vulkan; OUT="$BIN_ROOT/executorch-$TAG-vulkan" ;;
  *) echo "ERROR: ET_BACKEND must be xnnpack or vulkan (got '$BACKEND')" >&2; exit 2 ;;
esac

if [[ ! -f "$SRC/CMakeLists.txt" ]]; then
  cat >&2 <<EOF
ERROR: no ExecuTorch checkout at $SRC
  git clone --depth 1 --branch $TAG https://github.com/pytorch/executorch.git "$SRC"
  git -C "$SRC" submodule update --init --depth 1 third-party/flatbuffers third-party/flatcc \\
    third-party/gflags third-party/json third-party/pocketfft third-party/ao \\
    kernels/optimized/third-party/eigen backends/xnnpack/third-party \\
    backends/vulkan/third-party
  git -C "$SRC" submodule update --init --recursive --depth 1 extension/llm/tokenizers
EOF
  exit 1
fi
[[ "$(basename "$SRC")" == "executorch" ]] || {
  echo "ERROR: ET_SRC basename must be 'executorch' (the tag's CMakeLists.txt refuses '$(basename "$SRC")'); clone or link it as .../executorch" >&2; exit 1; }
OBSERVED="$(git -C "$SRC" describe --tags --always)"
COMMIT="$(git -C "$SRC" rev-parse HEAD)"
echo "== source: $SRC at $OBSERVED ($COMMIT)"
[[ "$OBSERVED" == "$TAG" ]] || echo "WARN: observed $OBSERVED != requested $TAG (recorded as-is in BUILD_INFO.json)"

if [[ -z "${ANDROID_NDK:-}" ]]; then
  if [[ -d "$HOME/Library/Android/sdk/ndk/28.2.13676358" ]]; then
    ANDROID_NDK="$HOME/Library/Android/sdk/ndk/28.2.13676358"
  elif [[ -n "${ANDROID_NDK_HOME:-}" ]]; then
    ANDROID_NDK="$ANDROID_NDK_HOME"
  else
    ANDROID_NDK="$(ls -d "$HOME"/Library/Android/sdk/ndk/* 2>/dev/null | sort -V | tail -1 || true)"
  fi
fi
[[ -n "$ANDROID_NDK" && -f "$ANDROID_NDK/build/cmake/android.toolchain.cmake" ]] || {
  echo "ERROR: no NDK (set ANDROID_NDK; the README tested r28c)" >&2; exit 1; }
export ANDROID_NDK
NDK_REV="$(sed -n 's/^Pkg.Revision *= *//p' "$ANDROID_NDK/source.properties")"
NDK_NAME="$(sed -n 's/^Pkg.ReleaseName *= *//p' "$ANDROID_NDK/source.properties")"
echo "== NDK: $ANDROID_NDK ($NDK_NAME, $NDK_REV)"
[[ "$NDK_NAME" == "r28c" ]] || echo "WARN: NDK $NDK_NAME, the tag's README tested r28c"

TORCH_PIN="$(sed -n 's/^TORCH_VERSION *= *"\(.*\)"/\1/p' "$SRC/torch_pin.py" 2>/dev/null || true)"
TORCH_SEEN="$("$PY" -c 'import torchgen, yaml, importlib.metadata as m; print(m.version("torch"))' 2>/dev/null)" || {
  echo "ERROR: $PY cannot import torchgen and yaml (pip install torch==${TORCH_PIN:-<torch_pin.py>} pyyaml)" >&2; exit 1; }
echo "== codegen python: $PY (torch $TORCH_SEEN; the tag pins ${TORCH_PIN:-?})"
[[ -z "$TORCH_PIN" || "$TORCH_SEEN" == "$TORCH_PIN"* ]] || echo "WARN: torch $TORCH_SEEN != the tag's pin $TORCH_PIN"

STAGE1_EXTRA=()
GLSLC_VERSION=""
if [[ "$BACKEND" == vulkan ]]; then
  GLSLC="${GLSLC:-$(command -v glslc || true)}"
  [[ -n "$GLSLC" && -x "$GLSLC" ]] || { echo "ERROR: no glslc (brew install shaderc, or set GLSLC)" >&2; exit 1; }
  [[ "$GLSLC" != "$ANDROID_NDK"/* ]] || {
    echo "ERROR: $GLSLC is the NDK's glslc, which lacks GL_EXT_integer_dot_product (brew install shaderc)" >&2; exit 1; }
  GLSLC_VERSION="$("$GLSLC" --version | head -1)"
  echo "== glslc: $GLSLC ($GLSLC_VERSION)"
  STAGE1_EXTRA=(-DEXECUTORCH_BUILD_VULKAN=ON "-DGLSLC_PATH=$GLSLC")
fi

TOOLCHAIN=(-DCMAKE_TOOLCHAIN_FILE="$ANDROID_NDK/build/cmake/android.toolchain.cmake"
           -DANDROID_ABI=arm64-v8a -DANDROID_PLATFORM=android-23
           -DCMAKE_INSTALL_PREFIX="$BUILD_DIR" -DCMAKE_BUILD_TYPE=Release)
STAGE1=(-DEXECUTORCH_BUILD_EXTENSION_DATA_LOADER=ON -DEXECUTORCH_BUILD_EXTENSION_FLAT_TENSOR=ON
        -DEXECUTORCH_BUILD_EXTENSION_MODULE=ON -DEXECUTORCH_BUILD_EXTENSION_TENSOR=ON
        -DEXECUTORCH_BUILD_EXTENSION_NAMED_DATA_MAP=ON -DEXECUTORCH_BUILD_EXTENSION_LLM=ON
        -DEXECUTORCH_BUILD_EXTENSION_LLM_RUNNER=ON -DEXECUTORCH_ENABLE_LOGGING=1
        -DPYTHON_EXECUTABLE="$PY" -DEXECUTORCH_BUILD_XNNPACK=ON
        -DEXECUTORCH_BUILD_KERNELS_OPTIMIZED=ON -DEXECUTORCH_BUILD_KERNELS_QUANTIZED=ON
        -DEXECUTORCH_BUILD_KERNELS_LLM=ON ${STAGE1_EXTRA[@]+"${STAGE1_EXTRA[@]}"})
STAGE2=(-DPYTHON_EXECUTABLE="$PY" -DEXECUTORCH_BUILD_XNNPACK=ON
        -DEXECUTORCH_BUILD_KERNELS_OPTIMIZED=ON -DEXECUTORCH_BUILD_KERNELS_QUANTIZED=ON
        -DEXECUTORCH_BUILD_KERNELS_LLM=ON -DSUPPORT_REGEX_LOOKAHEAD=ON)

cd "$SRC"
echo "== stage 1: ExecuTorch -> $SRC/$BUILD_DIR (install)"
cmake "${TOOLCHAIN[@]}" "${STAGE1[@]}" -B"$BUILD_DIR" .
cmake --build "$BUILD_DIR" -j"$JOBS" --target install --config Release
echo "== stage 2: examples/models/llama -> $SRC/$BUILD_DIR/examples/models/llama"
cmake "${TOOLCHAIN[@]}" "${STAGE2[@]}" -B"$BUILD_DIR/examples/models/llama" examples/models/llama
cmake --build "$BUILD_DIR/examples/models/llama" -j"$JOBS" --config Release

BIN="$SRC/$BUILD_DIR/examples/models/llama/llama_main"
[[ -x "$BIN" ]] || { echo "ERROR: $BIN not built" >&2; exit 1; }
READELF="$(ls "$ANDROID_NDK"/toolchains/llvm/prebuilt/*/bin/llvm-readelf | head -1)"
NEEDED="$("$READELF" -d "$BIN" | sed -n 's/.*(NEEDED).*\[\(.*\)\]/\1/p' | sort | tr '\n' ' ')"
echo "== NEEDED: $NEEDED"
for lib in $NEEDED; do
  case "$lib" in
    libc.so|libm.so|libdl.so|liblog.so|libandroid.so) ;;
    *) echo "WARN: $lib is not an Android system library: push it beside llama_main" ;;
  esac
done
# backend registration names compiled in (ET_LOG prints them at load on the device)
for name in XnnpackBackend VulkanBackend; do
  echo "== $name in binary: $(LC_ALL=C grep -c -a "$name" "$BIN" || true) match(es)"
done
if [[ "$BACKEND" == vulkan ]] && ! LC_ALL=C grep -q -a VulkanBackend "$BIN"; then
  echo "ERROR: vulkan build without VulkanBackend in llama_main" >&2; exit 1
fi

mkdir -p "$OUT"
cp -f "$BIN" "$OUT/llama_main"
chmod +x "$OUT/llama_main"
(cd "$OUT" && shasum -a 256 llama_main | tee SHA256SUMS)
file "$OUT/llama_main"
ls -l "$OUT/llama_main"

python3 - "$OUT" "$TAG" "$OBSERVED" "$COMMIT" "$BACKEND" "$ANDROID_NDK" "$NDK_NAME" "$NDK_REV" \
  "$PY" "$TORCH_SEEN" "$TORCH_PIN" "$GLSLC_VERSION" "$NEEDED" "$SRC/$BUILD_DIR" \
  "$(printf '%s\n' "${TOOLCHAIN[@]}" "${STAGE1[@]}")" "$(printf '%s\n' "${TOOLCHAIN[@]}" "${STAGE2[@]}")" <<'PY'
import hashlib, json, os, platform, subprocess, sys, time
(out, tag, observed, commit, backend, ndk, ndk_name, ndk_rev, py, torch_seen, torch_pin,
 glslc, needed, build_dir, stage1, stage2) = sys.argv[1:17]
binary = os.path.join(out, "llama_main")
sha = hashlib.sha256(open(binary, "rb").read()).hexdigest()
def cache(key):  # the value stage 1 configured, as CMakeCache.txt holds it
    for line in open(os.path.join(build_dir, "CMakeCache.txt"), errors="replace"):
        if line.startswith(key + ":"):
            return line.split("=", 1)[1].strip()
    return None
info = {
    "engine": "executorch", "binary": "llama_main", "backend": backend,
    "requested_tag": tag, "observed": observed, "commit": commit, "llama_main_sha256": sha,
    "size_bytes": os.path.getsize(binary), "needed": needed.split(),
    "recipe": "examples/models/llama/README.md Step 4 (two CMake stages)",
    "stage1_flags": stage1.split("\n"), "stage2_flags": stage2.split("\n"),
    "configured": {k: cache(k) for k in (
        "EXECUTORCH_PAL_DEFAULT", "EXECUTORCH_ENABLE_LOGGING", "EXECUTORCH_LOG_LEVEL",
        "EXECUTORCH_XNNPACK_ENABLE_KLEIDI", "EXECUTORCH_XNNPACK_SHARED_WORKSPACE",
        "EXECUTORCH_XNNPACK_ENABLE_WEIGHT_CACHE", "EXECUTORCH_BUILD_VULKAN", "ANDROID_STL",
        "CMAKE_BUILD_TYPE")},
    "ndk": {"path": ndk, "release": ndk_name, "revision": ndk_rev},
    "cmake": subprocess.run(["cmake", "--version"], capture_output=True, text=True).stdout.splitlines()[0],
    "codegen_python": {"path": py, "torch": torch_seen, "tag_torch_pin": torch_pin},
    "glslc": glslc or None,
    "built_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "host": platform.platform(),
}
json.dump(info, open(os.path.join(out, "BUILD_INFO.json"), "w"), indent=2)
key = tag if backend == "xnnpack" else f"{tag}-{backend}"
print("witness entry (android/engine-pins.json, not written here):")
print(json.dumps({"executorch": {key: {"requested_tag": tag, "observed": observed,
                                        "llama_main_sha256": sha}}}, indent=2))
PY

echo "== done: $OUT"
