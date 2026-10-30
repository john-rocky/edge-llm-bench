#!/usr/bin/env bash
# Fetch the OFFICIAL llama.cpp Android binary at the same tag the Apple arm pins.
#
# b11721 (environment.lock.json -> arms."llama.cpp".tag, since 2026-10-19; b8999
# before) ships llama-<tag>-bin-android-arm64.tar.gz in its GitHub release — an
# official artifact (fairness rule: prefer the official runtime SDK), so no NDK
# build. That build is CPU-only (no OpenCL/Vulkan): the `llama.cpp` arm. Its
# llama-cli / llama-bench are 7 KB launchers (from b10903 on; b11721's are
# byte-identical to b10903's): the pin also records the libs they load
# (so_files: their DT_NEEDED closure in the tar + the CPU backend variants ggml
# picks from at run time), which the witness checks beside the tools on the
# device (run_cell.observed_engine).
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
#   LLAMA_TAG     release tag (default: b11721 — keep in lockstep with the Apple arm)
#   LLAMA_FLAVOR  empty (the CPU-only asset) or snapdragon
#   BENCH_BIN_ROOT   where engine binaries live (default: <repo>/android/bin)
#   LLAMA_PINS_FILE  the registry the pin is written to (default: <repo>/android/engine-pins.json);
#                    e.g. another harness's BENCH_EXTRA_PINS registry, so a label that is not on
#                    main never touches this repo's
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BIN_ROOT="${BENCH_BIN_ROOT:-$REPO_ROOT/android/bin}"
PINS_FILE="${LLAMA_PINS_FILE:-$REPO_ROOT/android/engine-pins.json}"
TAG="${LLAMA_TAG:-b11721}"
FLAVOR="${LLAMA_FLAVOR:-}"
case "$FLAVOR" in
  "")
    OUT="$BIN_ROOT/llama-$TAG"
    TAR="llama-$TAG-bin-android-arm64.tar.gz"
    PIN="$TAG"
    TOOLS="$OUT"
    ;;
  snapdragon)
    OUT="$BIN_ROOT/llama-$TAG-snapdragon"
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

python3 - "$PINS_FILE" "$TAG" "$OUT" "$TAR" "$PIN" "$TOOLS" "$FLAVOR" <<'PY'
import json, os, sys, hashlib, struct
pins_path, tag, out, tar, pin, tools, flavor = sys.argv[1:8]
pins = json.load(open(pins_path)) if os.path.exists(pins_path) else {}
def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()
def dt_needed(p):
    # the DT_NEEDED names of an ELF64 little-endian file (PT_DYNAMIC, its string table
    # mapped through the PT_LOAD segments)
    data = open(p, "rb").read()
    if data[:4] != b"\x7fELF" or data[4] != 2 or data[5] != 1:
        return []
    phoff, = struct.unpack_from("<Q", data, 0x20)
    phentsize, phnum = struct.unpack_from("<HH", data, 0x36)
    loads, dyn = [], None
    for i in range(phnum):
        p_type, _, off, vaddr, _, filesz, _, _ = struct.unpack_from("<IIQQQQQQ", data, phoff + i * phentsize)
        if p_type == 1:
            loads.append((vaddr, off, filesz))
        elif p_type == 2:
            dyn = (off, filesz)
    if not dyn:
        return []
    needed, strtab = [], None
    for at in range(dyn[0], dyn[0] + dyn[1], 16):
        d_tag, val = struct.unpack_from("<qQ", data, at)
        if d_tag == 0:
            break
        if d_tag == 1:
            needed.append(val)
        elif d_tag == 5:
            strtab = val
    base = next(strtab - va + off for va, off, size in loads if va <= strtab < va + size)
    return [data[base + n:data.index(b"\0", base + n)].decode() for n in needed]
entry = {
    "artifact": tar,
    "llama_bench_sha256": sha(os.path.join(tools, "llama-bench")),
    "llama_cli_sha256": sha(os.path.join(tools, "llama-cli")),
}
if flavor == "snapdragon":
    libs = ["libggml-hexagon.so", "libggml-htp-v81.so", "libggml-opencl.so", "libggml-cpu.so",
            "libllama.so", "libllama-cli-impl.so", "libllama-bench-impl.so"]
    entry["so_files"] = {name: sha(os.path.join(out, "lib", name)) for name in libs}
else:
    # the libs the two tools load from the flat dir: their DT_NEEDED closure inside the tar
    # (system libs are not in it) and every CPU backend variant (ggml dlopens the best one)
    libs, todo = [], ["llama-cli", "llama-bench"]
    while todo:
        for name in dt_needed(os.path.join(out, todo.pop(0))):
            if name not in libs and os.path.isfile(os.path.join(out, name)):
                libs.append(name)
                todo.append(name)
    libs += [f for f in os.listdir(out) if f.startswith("libggml-cpu") and f.endswith(".so")]
    entry["so_files"] = {name: sha(os.path.join(out, name)) for name in sorted(libs)}
    with open(os.path.join(out, "SHA256SUMS"), "a") as fh:
        for name, digest in entry["so_files"].items():
            fh.write(f"{digest}  {name}\n")
            print(f"{digest}  {name}")
pins.setdefault("llama.cpp", {})[pin] = entry
json.dump(pins, open(pins_path, "w"), indent=2)
print(f"pins updated: {pins_path} (llama.cpp {pin})")
PY

echo "== done: $OUT"
