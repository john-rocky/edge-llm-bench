#!/usr/bin/env bash
# Fetch the OFFICIAL llama.cpp Android binary at the same tag the Apple arm pins.
#
# b8999 (environment.lock.json -> arms."llama.cpp".tag) ships
# llama-<tag>-bin-android-arm64.tar.gz in its GitHub release — an official
# artifact (fairness rule: prefer the official runtime SDK), so no NDK build.
# That build is CPU-only (no OpenCL/Vulkan): the `llama.cpp` arm.
#
# LLAMA_FLAVOR=snapdragon fetches the release's Snapdragon asset instead,
# llama-<tag>-bin-android-arm64-snapdragon.tar.gz: the same tools with the
# Hexagon (HTP) and Adreno OpenCL backends, laid out as bin/ (7 KB launchers)
# + lib/ (the engine). It unpacks to android/bin/llama-<tag>-snapdragon and is
# registered in android/engine-pins.json as <tag>-snapdragon, with the shared
# libs the witness checks on the device (so_files) — a side build for the
# llama.cpp-npu / llama.cpp-gpu arms (cells engine-build=<tag>-snapdragon;
# docs/dashboard-cells-v1.md "NPU and Android GPU rows"). The lock's pin does
# not move. An already-unpacked dir is not fetched again: the script then only
# hashes it and (re)writes its pin.
#
# Env:
#   LLAMA_TAG     release tag (default: b8999 — keep in lockstep with the Apple arm)
#   LLAMA_FLAVOR  empty (the CPU-only asset) or snapdragon
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TAG="${LLAMA_TAG:-b8999}"
FLAVOR="${LLAMA_FLAVOR:-}"
case "$FLAVOR" in
  "")
    OUT="$REPO_ROOT/android/bin/llama-$TAG"
    TAR="llama-$TAG-bin-android-arm64.tar.gz"
    PIN="$TAG"
    TOOLS="$OUT"
    ;;
  snapdragon)
    OUT="$REPO_ROOT/android/bin/llama-$TAG-snapdragon"
    TAR="llama-$TAG-bin-android-arm64-snapdragon.tar.gz"
    PIN="$TAG-snapdragon"
    TOOLS="$OUT/bin"
    ;;
  *)
    echo "ERROR: LLAMA_FLAVOR=$FLAVOR (want empty or snapdragon)" >&2; exit 1 ;;
esac
URL="https://github.com/ggml-org/llama.cpp/releases/download/$TAG/$TAR"

mkdir -p "$OUT"
if [[ ! -x "$TOOLS/llama-bench" ]]; then
  echo "== fetching $URL"
  curl -fL --retry 3 -o "$OUT/$TAR" "$URL"
  tar -xzf "$OUT/$TAR" -C "$OUT" --strip-components=1
  rm -f "$OUT/$TAR"
fi
[[ -x "$TOOLS/llama-bench" && -x "$TOOLS/llama-cli" ]] || {
  echo "ERROR: llama-bench / llama-cli not found after extraction — inspect $OUT" >&2; exit 1; }

if [[ -z "$FLAVOR" ]]; then
  (cd "$OUT" && shasum -a 256 llama-bench llama-cli | tee SHA256SUMS)
else
  # the witness libs (run_cell.observed_engine): the backends, the CPU backend, the
  # llama core and the two tools' implementations
  (cd "$OUT" && shasum -a 256 bin/llama-bench bin/llama-cli lib/libggml-hexagon.so \
     lib/libggml-htp-v81.so lib/libggml-opencl.so lib/libggml-cpu.so lib/libllama.so \
     lib/libllama-cli-impl.so lib/libllama-bench-impl.so | tee SHA256SUMS)
fi

python3 - "$REPO_ROOT" "$TAG" "$OUT" "$TAR" "$PIN" "$TOOLS" "$FLAVOR" <<'PY'
import json, os, sys, hashlib
root, tag, out, tar, pin, tools, flavor = sys.argv[1:8]
pins_path = os.path.join(root, "android", "engine-pins.json")
pins = json.load(open(pins_path)) if os.path.exists(pins_path) else {}
def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()
entry = {
    "artifact": tar,
    "llama_bench_sha256": sha(os.path.join(tools, "llama-bench")),
    "llama_cli_sha256": sha(os.path.join(tools, "llama-cli")),
}
if flavor == "snapdragon":
    libs = ["libggml-hexagon.so", "libggml-htp-v81.so", "libggml-opencl.so", "libggml-cpu.so",
            "libllama.so", "libllama-cli-impl.so", "libllama-bench-impl.so"]
    entry["so_files"] = {name: sha(os.path.join(out, "lib", name)) for name in libs}
pins.setdefault("llama.cpp", {})[pin] = entry
json.dump(pins, open(pins_path, "w"), indent=2)
print(f"pins updated: {pins_path} (llama.cpp {pin})")
PY

echo "== done: $OUT"
