#!/usr/bin/env bash
# Build ExecuTorch's llama_main for macOS arm64 (XNNPACK CPU, Release) from a
# tagged source tree, as examples/models/llama/README.md "Step 3" does:
#
#   cmake --workflow --preset llm-release                  # core + LLM libs -> cmake-out
#   (cd examples/models/llama && cmake --workflow --preset llama-release)
#   -> cmake-out/examples/models/llama/llama_main
#
# The llm preset (tools/cmake/preset/llm.cmake) turns on XNNPACK, the optimized,
# quantized and LLM kernels, the LLM runner and, on Darwin, Core ML and the
# torchao kernels. A Release build compiles ET_LOG out (EXECUTORCH_ENABLE_LOGGING
# defaults to the Debug flag, tools/cmake/preset/default.cmake), so that binary
# prints only the generated text and the PyTorchObserver stats line.
#
# --log-build adds a second binary from the same source and the same preset with
# EXECUTORCH_ENABLE_LOGGING=ON (level Info) in cmake-out-log/. It is a witness
# only: its log names the thread-pool size, the pte metadata the runner read and
# RSS after load. Numbers come from the stock binary.
#
# The source tree must sit in a directory named exactly `executorch`
# (CMakeLists.txt FATAL_ERROR, pytorch/executorch#6475). Python for the codegen
# steps (torchgen) is the export venv: ET_VENV.
#
# Env:
#   ET_DIR      source tree (default: ~/code/executorch-convert/et-v1.5.1/executorch)
#   ET_TAG      tag the tree must describe as (default: v1.5.1)
#   ET_VENV     venv with torch for the codegen (default: ~/code/executorch-convert/.venv-et151)
set -euo pipefail

ET_DIR="${ET_DIR:-$HOME/code/executorch-convert/et-v1.5.1/executorch}"
ET_TAG="${ET_TAG:-v1.5.1}"
ET_VENV="${ET_VENV:-$HOME/code/executorch-convert/.venv-et151}"
LOG_BUILD=0
for arg in "$@"; do
  case "$arg" in
    --log-build) LOG_BUILD=1 ;;
    --log-only) LOG_BUILD=2 ;;
    *) echo "usage: $0 [--log-build | --log-only]" >&2; exit 2 ;;
  esac
done

[[ "$(basename "$ET_DIR")" == executorch ]] || {
  echo "ERROR: $ET_DIR: the directory must be named exactly 'executorch' (#6475)" >&2; exit 1; }
observed="$(git -C "$ET_DIR" describe --tags --exact-match 2>/dev/null || git -C "$ET_DIR" describe --tags)"
[[ "$observed" == "$ET_TAG" ]] || {
  echo "ERROR: $ET_DIR describes as '$observed', expected '$ET_TAG'" >&2; exit 1; }
[[ -x "$ET_VENV/bin/python" ]] || { echo "ERROR: no python in $ET_VENV" >&2; exit 1; }
export VIRTUAL_ENV="$ET_VENV" PATH="$ET_VENV/bin:$PATH"
"$ET_VENV/bin/python" -c 'import torch, torchgen' || {
  echo "ERROR: $ET_VENV lacks torch (the codegen imports torchgen)" >&2; exit 1; }

echo "== source $ET_DIR ($observed, $(git -C "$ET_DIR" rev-parse HEAD))"
echo "== python $("$ET_VENV/bin/python" -c 'import sys, torch; print(sys.executable, "torch", torch.__version__)')"
echo "== cmake $(cmake --version | head -1); $(xcrun clang --version | head -1)"
cd "$ET_DIR"

if [[ "$LOG_BUILD" != 2 ]]; then
  echo "== [stock] cmake --workflow --preset llm-release  ($(date '+%H:%M:%S'))"
  cmake --workflow --preset llm-release
  echo "== [stock] examples/models/llama: cmake --workflow --preset llama-release  ($(date '+%H:%M:%S'))"
  (cd examples/models/llama && cmake --workflow --preset llama-release)
  bin="$ET_DIR/cmake-out/examples/models/llama/llama_main"
  [[ -x "$bin" ]] || { echo "ERROR: $bin not built" >&2; exit 1; }
  echo "== [stock] built $bin"
fi

if [[ "$LOG_BUILD" != 0 ]]; then
  out="$ET_DIR/cmake-out-log"
  echo "== [log] llm-release + EXECUTORCH_ENABLE_LOGGING=ON -> $out  ($(date '+%H:%M:%S'))"
  cmake --preset llm-release -B "$out" -DCMAKE_INSTALL_PREFIX="$out" \
    -DEXECUTORCH_ENABLE_LOGGING=ON -DEXECUTORCH_LOG_LEVEL=Info
  cmake --build "$out" --config Release --target install -j
  cmake -S examples/models/llama -B "$out/examples/models/llama" \
    -DCMAKE_BUILD_TYPE=Release -DCMAKE_FIND_ROOT_PATH="$out"
  cmake --build "$out/examples/models/llama" --config Release --target llama_main -j
  [[ -x "$out/examples/models/llama/llama_main" ]] || { echo "ERROR: log build missing" >&2; exit 1; }
  echo "== [log] built $out/examples/models/llama/llama_main"
fi

echo "== cache options"
for d in cmake-out cmake-out-log; do
  [[ -f "$ET_DIR/$d/CMakeCache.txt" ]] || continue
  echo "-- $d/CMakeCache.txt"
  grep -E '^(CMAKE_BUILD_TYPE|EXECUTORCH_BUILD_(XNNPACK|KERNELS_QUANTIZED|KERNELS_LLM|KERNELS_OPTIMIZED|KERNELS_TORCHAO|COREML|EXTENSION_LLM_RUNNER)|EXECUTORCH_ENABLE_LOGGING|EXECUTORCH_LOG_LEVEL|EXECUTORCH_BUILD_PRESET_FILE|PYTHON_EXECUTABLE):' \
    "$ET_DIR/$d/CMakeCache.txt" | sort
done
echo "== binaries"
for b in "$ET_DIR"/cmake-out/examples/models/llama/llama_main "$ET_DIR"/cmake-out-log/examples/models/llama/llama_main; do
  [[ -x "$b" ]] || continue
  ls -l "$b"; file "$b"; shasum -a 256 "$b"
  otool -L "$b" | sed 1d
done
echo "== done $(date '+%H:%M:%S')"
