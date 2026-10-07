#!/usr/bin/env bash
# Build the ONNX Runtime GenAI Android CLIs against the OFFICIAL release
# libraries, into android/bin/ortgenai-<version>/ (gitignored):
#   ortgenai_run     harness driver (android/ortgenai/ortgenai_run.cpp): stops at
#                    EOS or the budget, model chat template, the prefill / TTFT /
#                    decode cut points of model_benchmark
#   model_benchmark  upstream benchmark/c at the same tag, unchanged (forced
#                    length: min_length = prompt + generation length)
# next to the three runtime libraries they need on the device:
#   libonnxruntime-genai.so, libmat.so  release AAR (jni/arm64-v8a). libmat.so is
#                    the 1DS telemetry SDK, a DT_NEEDED of the GenAI library.
#   libonnxruntime.so  Maven onnxruntime-android: the GenAI AAR does not ship it;
#                    GenAI dlopens it at its first call (ORT_LIB_PATH first).
# Every download is checked against a pinned sha256. MANIFEST.txt records the
# sha256 and origin of each file, the NDK, and each binary's DT_NEEDED.
#
# No rpath; run on the device as
#   LD_LIBRARY_PATH=<dir> ORT_LIB_PATH=<dir>/libonnxruntime.so ORT_DISABLE_TELEMETRY=1 ./ortgenai_run ...
# (ortgenai_run refuses to start without ORT_DISABLE_TELEMETRY=1).
#
# Env:
#   ANDROID_NDK_HOME  NDK path (default: newest under ~/Library/Android/sdk/ndk)
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
GENAI_VERSION=0.17.0
ORT_VERSION=1.30.0
API=28
OUT="$REPO_ROOT/android/bin/ortgenai-$GENAI_VERSION"
DL="$OUT/download"
SRC="$OUT/src/benchmark/c"

# The previous MANIFEST, read before this build replaces it: a binary whose
# sha256 changes stays listed on a "history:" line, so output made with an
# earlier build (an engine log naming the old sha) still finds its source.
PREV_MANIFEST="$(cat "$OUT/MANIFEST.txt" 2>/dev/null || true)"
PREV_WRITTEN="$(printf '%s\n' "$PREV_MANIFEST" | sed -n '1s/.*build_android\.sh //p')"

GENAI_AAR="onnxruntime-genai-android-$GENAI_VERSION.aar"
GENAI_AAR_URL="https://github.com/microsoft/onnxruntime-genai/releases/download/v$GENAI_VERSION/$GENAI_AAR"
GENAI_AAR_SHA256=f8b28a9ce448d97e0d5ab9614eae018a4d994d739de84e9fc5f9ff3b6673dd50
ORT_AAR="onnxruntime-android-$ORT_VERSION.aar"
ORT_AAR_URL="https://repo1.maven.org/maven2/com/microsoft/onnxruntime/onnxruntime-android/$ORT_VERSION/$ORT_AAR"
ORT_AAR_SHA256=e7fb945e402205f6db858d65bb78d2bdb0812317b383976c9e3bceb4862c73f1
BENCH_URL="https://raw.githubusercontent.com/microsoft/onnxruntime-genai/v$GENAI_VERSION/benchmark/c"
BENCH_FILES=(
  "5eaedbd1d31e5e36002ed438fa792b547d5a98f4d6a7a88cf736ab743fb9326f main.cpp"
  "807e39c55e2459f15196e22c58c328a92988207ed3db4e812cc7ffe6dc2a4a2d options.cpp"
  "134eeb591da80890b65d4c1cfedfffebe2525efee7a0469c3fa143f9a5ace517 options.h"
  "5f75787cea602df6cd9cb5ac62b3be67cf2979492f808187023cad3f034fa951 resource_utils.h"
  "478fb519b9fceda51770f199eda4f24fda2c9b299115639f4af247f8a5737f76 posix/resource_utils.cpp"
)

if [[ -z "${ANDROID_NDK_HOME:-}" ]]; then
  ANDROID_NDK_HOME="$(ls -d "$HOME"/Library/Android/sdk/ndk/* 2>/dev/null | sort -V | tail -1 || true)"
fi
[[ -n "$ANDROID_NDK_HOME" && -d "$ANDROID_NDK_HOME" ]] || {
  echo "ERROR: ANDROID_NDK_HOME not set and no NDK under ~/Library/Android/sdk/ndk" >&2; exit 1; }
BIN="$ANDROID_NDK_HOME/toolchains/llvm/prebuilt/darwin-x86_64/bin"
CXX="$BIN/clang++"
READELF="$BIN/llvm-readelf"
NDK_REVISION="$(sed -n 's/^Pkg.Revision *= *//p' "$ANDROID_NDK_HOME/source.properties")"
echo "== NDK: $NDK_REVISION"

sha256() { shasum -a 256 "$1" | cut -d' ' -f1; }

fetch() {  # fetch <url> <dest> <sha256>: download unless present and matching, then verify
  local url=$1 dest=$2 want=$3 got
  if [[ ! -f "$dest" || "$(sha256 "$dest")" != "$want" ]]; then
    mkdir -p "$(dirname "$dest")"
    echo "== fetching $url"
    curl -fsSL --retry 3 -o "$dest" "$url"
  fi
  got="$(sha256 "$dest")"
  [[ "$got" == "$want" ]] || {
    echo "ERROR: sha256 of $dest is $got, expected $want ($url)" >&2; exit 1; }
}

fetch "$GENAI_AAR_URL" "$DL/$GENAI_AAR" "$GENAI_AAR_SHA256"
fetch "$ORT_AAR_URL" "$DL/$ORT_AAR" "$ORT_AAR_SHA256"
for entry in "${BENCH_FILES[@]}"; do
  fetch "$BENCH_URL/${entry#* }" "$SRC/${entry#* }" "${entry%% *}"
done

unzip -o -q -j "$DL/$GENAI_AAR" jni/arm64-v8a/libonnxruntime-genai.so jni/arm64-v8a/libmat.so -d "$OUT"
unzip -o -q -j "$DL/$GENAI_AAR" headers/ort_genai.h headers/ort_genai_c.h -d "$OUT/headers"
unzip -o -q -j "$DL/$ORT_AAR" jni/arm64-v8a/libonnxruntime.so -d "$OUT"

# libc++ is linked statically: the GenAI library carries its own (no
# libc++_shared.so in its DT_NEEDED) and only the C API crosses the boundary.
CXXFLAGS=(--target="aarch64-linux-android$API" -std=c++20 -O2 -Wall -fPIE -pie -static-libstdc++)
LIBS=(-L"$OUT" -lonnxruntime-genai -ldl)
echo "== building ortgenai_run"
"$CXX" "${CXXFLAGS[@]}" -I"$OUT/headers" -o "$OUT/ortgenai_run" \
  "$REPO_ROOT/android/ortgenai/ortgenai_run.cpp" "${LIBS[@]}"
echo "== building model_benchmark (upstream benchmark/c v$GENAI_VERSION, unchanged)"
"$CXX" "${CXXFLAGS[@]}" -I"$OUT/headers" -I"$SRC" -o "$OUT/model_benchmark" \
  "$SRC/main.cpp" "$SRC/options.cpp" "$SRC/posix/resource_utils.cpp" "${LIBS[@]}"

needed() { "$READELF" -d "$1" | sed -n 's/.*(NEEDED).*\[\(.*\)\]/\1/p' | tr '\n' ' '; }
for b in ortgenai_run model_benchmark; do
  if needed "$OUT/$b" | grep -q 'libc++'; then
    echo "ERROR: $b needs a shared libc++ ($(needed "$OUT/$b"))" >&2; exit 1
  fi
done

{
  echo "# android/bin/ortgenai-$GENAI_VERSION, written by android/ortgenai/build_android.sh $(date '+%Y-%m-%d %H:%M %Z')"
  echo "# sha256  file  origin"
  for f in libonnxruntime-genai.so libmat.so; do
    echo "$(sha256 "$OUT/$f")  $f  $GENAI_AAR_URL jni/arm64-v8a"
  done
  echo "$(sha256 "$OUT/libonnxruntime.so")  libonnxruntime.so  $ORT_AAR_URL jni/arm64-v8a"
  for f in ort_genai.h ort_genai_c.h; do
    echo "$(sha256 "$OUT/headers/$f")  headers/$f  $GENAI_AAR_URL headers"
  done
  echo "$GENAI_AAR_SHA256  download/$GENAI_AAR  $GENAI_AAR_URL"
  echo "$ORT_AAR_SHA256  download/$ORT_AAR  $ORT_AAR_URL"
  for entry in "${BENCH_FILES[@]}"; do
    echo "${entry%% *}  src/benchmark/c/${entry#* }  $BENCH_URL/${entry#* }"
  done
  echo "$(sha256 "$OUT/ortgenai_run")  ortgenai_run  built from android/ortgenai/ortgenai_run.cpp (sha256 $(sha256 "$REPO_ROOT/android/ortgenai/ortgenai_run.cpp"))"
  echo "$(sha256 "$OUT/model_benchmark")  model_benchmark  built from src/benchmark/c (upstream v$GENAI_VERSION, unchanged)"
  printf '%s\n' "$PREV_MANIFEST" | grep '^history: ' || true
  for b in ortgenai_run model_benchmark; do
    prev="$(printf '%s\n' "$PREV_MANIFEST" | awk -v b="$b" '$2 == b {print; exit}')"
    if [[ -n "$prev" && "${prev%% *}" != "$(sha256 "$OUT/$b")" ]]; then
      echo "history: $prev; in the MANIFEST written $PREV_WRITTEN, replaced $(date '+%Y-%m-%d %H:%M %Z')"
    fi
  done
  echo "ndk: $NDK_REVISION"
  echo "clang: $("$CXX" --version | head -1)"
  echo "flags: ${CXXFLAGS[*]} -lonnxruntime-genai -ldl"
  for b in ortgenai_run model_benchmark libonnxruntime-genai.so libmat.so libonnxruntime.so; do
    echo "NEEDED $b: $(needed "$OUT/$b")"
  done
} > "$OUT/MANIFEST.txt"

cat "$OUT/MANIFEST.txt"
echo "== done: $OUT"
