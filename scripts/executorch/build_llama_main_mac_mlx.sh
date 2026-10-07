#!/usr/bin/env bash
# Build ExecuTorch's llama_main for macOS arm64 with the MLX delegate (Apple GPU, Release)
# from a tagged source tree, as the tag's own presets do (upstream CI test-mlx-stories110m:
# mlx-release, then the llama runner):
#
#   cmake --preset mlx-release   (tools/cmake/preset/mlx.cmake: the MLX delegate, module /
#                                 data loader / LLM runner, optimized + quantized + LLM kernels;
#                                 no XNNPACK; logging compiled in at level Error)
#   examples/models/llama with the llama-mlx preset's cache (Release, EXECUTORCH_BUILD_MLX=ON,
#                                 which copies mlx.metallib beside llama_main)
#   -> cmake-out-mlx/examples/models/llama/llama_main + mlx.metallib
#
# Both presets name ${sourceDir}/cmake-out as their build and install dir (CMakePresets.json
# "common"); this script passes -B / -DCMAKE_INSTALL_PREFIX / CMAKE_FIND_ROOT_PATH so the
# XNNPACK build in cmake-out stays as it is. The MLX submodule (backends/mlx/third-party/mlx)
# must be checked out at the tag's pinned commit; the delegate's CMake applies its patches/.
#
# Then copies llama_main and mlx.metallib to OUT (MLX loads the metallib colocated with the
# binary first; the build-tree path compiled into libmlx is only the fallback) and prints the
# sha256s, otool -L, the delegate symbols linked in and the cache options.
#
# Env:
#   ET_DIR   source tree (default: ~/code/executorch-convert/et-v1.5.1/executorch)
#   ET_TAG   tag the tree must describe as (default: v1.5.1)
#   ET_VENV  venv with torch for the codegen (default: ~/code/executorch-convert/.venv-et151)
#   OUT      where the runner is copied (default: <repo>/.build/executorch-<tag>-mlx)
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
ET_DIR="${ET_DIR:-$HOME/code/executorch-convert/et-v1.5.1/executorch}"
ET_TAG="${ET_TAG:-v1.5.1}"
ET_VENV="${ET_VENV:-$HOME/code/executorch-convert/.venv-et151}"
OUT="${OUT:-$REPO/.build/executorch-$ET_TAG-mlx}"
BUILD="$ET_DIR/cmake-out-mlx"

[[ "$(basename "$ET_DIR")" == executorch ]] || {
  echo "ERROR: $ET_DIR: the directory must be named exactly 'executorch' (#6475)" >&2; exit 1; }
observed="$(git -C "$ET_DIR" describe --tags --exact-match 2>/dev/null || git -C "$ET_DIR" describe --tags)"
[[ "$observed" == "$ET_TAG" ]] || {
  echo "ERROR: $ET_DIR describes as '$observed', expected '$ET_TAG'" >&2; exit 1; }
mlx_status="$(git -C "$ET_DIR" submodule status backends/mlx/third-party/mlx)"
[[ "$mlx_status" == " "* ]] || {
  echo "ERROR: backends/mlx/third-party/mlx is not at the pinned commit: $mlx_status" >&2
  echo "  git -C $ET_DIR submodule update --init --depth 1 -- backends/mlx/third-party/mlx" >&2; exit 1; }
xcrun -sdk macosx --find metal >/dev/null || {
  echo "ERROR: no Metal compiler (the MLX delegate needs Xcode's, not the Command Line Tools)" >&2; exit 1; }
[[ -x "$ET_VENV/bin/python" ]] || { echo "ERROR: no python in $ET_VENV" >&2; exit 1; }
export VIRTUAL_ENV="$ET_VENV" PATH="$ET_VENV/bin:$PATH"
"$ET_VENV/bin/python" -c 'import torch, torchgen' || {
  echo "ERROR: $ET_VENV lacks torch (the codegen imports torchgen)" >&2; exit 1; }

echo "== source $ET_DIR ($observed, $(git -C "$ET_DIR" rev-parse HEAD))"
echo "== mlx submodule $mlx_status"
echo "== python $("$ET_VENV/bin/python" -c 'import sys, torch; print(sys.executable, "torch", torch.__version__)')"
echo "== cmake $(cmake --version | head -1); $(xcrun clang --version | head -1); metal $(xcrun -sdk macosx metal --version 2>&1 | head -1)"
cd "$ET_DIR"

echo "== [mlx] cmake --preset mlx-release -B $BUILD  ($(date '+%H:%M:%S'))"
cmake --preset mlx-release -B "$BUILD" -DCMAKE_INSTALL_PREFIX="$BUILD"
cmake --build "$BUILD" --config Release --target install -j
echo "== [mlx] examples/models/llama (llama-mlx cache)  ($(date '+%H:%M:%S'))"
cmake -S examples/models/llama -B "$BUILD/examples/models/llama" \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_FIND_ROOT_PATH="$BUILD" -DEXECUTORCH_BUILD_MLX=ON
cmake --build "$BUILD/examples/models/llama" --config Release --target llama_main -j
bin="$BUILD/examples/models/llama/llama_main"
lib="$BUILD/examples/models/llama/mlx.metallib"
[[ -x "$bin" ]] || { echo "ERROR: $bin not built" >&2; exit 1; }
[[ -f "$lib" ]] || { echo "ERROR: $lib not copied beside llama_main" >&2; exit 1; }
echo "== [mlx] built $bin"

mkdir -p "$OUT"
cp -p "$bin" "$lib" "$OUT/"
echo "== copied to $OUT"

echo "== cache options"
grep -E '^(CMAKE_BUILD_TYPE|CMAKE_OSX_DEPLOYMENT_TARGET|EXECUTORCH_BUILD_(MLX|XNNPACK|COREML|METAL|KERNELS_QUANTIZED|KERNELS_LLM|KERNELS_OPTIMIZED|KERNELS_TORCHAO|EXTENSION_LLM_RUNNER)|EXECUTORCH_ENABLE_LOGGING|ET_MIN_LOG_LEVEL|ET_MLX_ENABLE_OP_LOGGING|EXECUTORCH_BUILD_PRESET_FILE|PYTHON_EXECUTABLE):' \
  "$BUILD/CMakeCache.txt" | sort
echo "== binaries"
for f in "$OUT/llama_main" "$OUT/mlx.metallib"; do
  ls -l "$f"; shasum -a 256 "$f"
done
file "$OUT/llama_main"
otool -L "$OUT/llama_main" | sed 1d
echo "== backend ids in the binary (the names register_backend is called with)"
# grep without -q reads to the end: an early exit would SIGPIPE strings and fail the pipe
for name in MLXBackend XnnpackBackend CoreMLBackend MetalBackend VulkanBackend; do
  n="$(strings -a "$OUT/llama_main" | grep -cx "$name" || true)"
  echo "$name: $n"
done
# the delegate builds MLX with MLX_METAL_JIT=ON: kernels outside the small metallib are
# compiled from source when a process first uses them
echo "== MLX sub-build: $(grep -E '^MLX_(METAL_JIT|BUILD_METAL):' "$BUILD/backends/mlx/mlx/CMakeCache.txt" | tr '\n' ' ')"
echo "== MLX submodule patches: $(git -C "$ET_DIR/backends/mlx/third-party/mlx" status --short | tr '\n' ' ')"
echo "== done $(date '+%H:%M:%S')"
