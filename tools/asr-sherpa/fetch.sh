#!/usr/bin/env bash
# sherpa-onnx release assets for the asr-sherpa-v1 A1 arm: the Android aarch64 (termux)
# binary tarball and the parakeet-tdt-0.6b-v3 int8 model, each checked against the
# sha256 digest GitHub publishes for the asset, unpacked, and pinned in LOCK.json.
#
#   NDK=<android ndk root> tools/asr-sherpa/fetch.sh [static|shared] [out-dir]   (default: static .build/sherpa-onnx)
#
# Downloads go to <out>/download/ (an empty dir of their own), archives unpack under
# <out>/extract/<asset>/, nothing inside them is run on the Mac. LOCK.json goes to <out>/.
# The termux binaries need the NDK's shared C++ runtime (DT_NEEDED libc++_shared.so), which
# a stock Android shell does not have and none of the v1.13.8 Android assets ships: with NDK
# set, its aarch64 libc++_shared.so is copied to <out>/extract/cxx-runtime/ and pinned too.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
repo=$(cd "$here/../.." && pwd)
FLAVOR=${1:-static}
OUT=${2:-$repo/.build/sherpa-onnx}
NDK=${NDK:-}
GH_REPO=k2-fsa/sherpa-onnx
TAG=v1.13.8
BIN_ASSET=sherpa-onnx-$TAG-android-aarch64-termux-$FLAVOR.tar.bz2
MODEL_TAG=asr-models
MODEL_ASSET=sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8.tar.bz2
mkdir -p "$OUT/download" "$OUT/extract"

fetch() {  # <release tag> <asset name> -> download, digest check, unpack; prints the asset's JSON
  local tag=$1 name=$2 meta want got
  meta=$(gh api "repos/$GH_REPO/releases/tags/$tag" \
    --jq ".assets[] | select(.name == \"$name\") | {name, size, updated_at, digest, url: .browser_download_url}")
  want=$(printf '%s' "$meta" | python3 -I -c 'import json, sys; print(json.load(sys.stdin)["digest"].removeprefix("sha256:"))')
  if [ ! -f "$OUT/download/$name" ]; then
    gh release download "$tag" -R "$GH_REPO" -p "$name" -D "$OUT/download"
  fi
  got=$(shasum -a 256 "$OUT/download/$name" | cut -d' ' -f1)
  if [ "$got" != "$want" ]; then
    echo "sha256 mismatch for $name: $got != GitHub digest $want" >&2
    exit 1
  fi
  if [ ! -d "$OUT/extract/$name" ]; then
    mkdir -p "$OUT/extract/$name.tmp"
    tar -xjf "$OUT/download/$name" -C "$OUT/extract/$name.tmp"
    mv "$OUT/extract/$name.tmp" "$OUT/extract/$name"
  fi
  printf '%s' "$meta" | python3 -I -c 'import json, sys; d = json.load(sys.stdin); d["sha256"] = sys.argv[1]; print(json.dumps(d))' "$got"
}

bin_json=$(fetch "$TAG" "$BIN_ASSET")
model_json=$(fetch "$MODEL_TAG" "$MODEL_ASSET")
JNI_ASSET=sherpa-onnx-$TAG-android.tar.bz2  # the app (jniLibs) build: only its ONNX Runtime version is read
jni_json=$(fetch "$TAG" "$JNI_ASSET")
published=$(gh api "repos/$GH_REPO/releases/tags/$TAG" --jq .published_at)
tag_commit=$(gh api "repos/$GH_REPO/commits/$TAG" --jq .sha)
ndk_rev=
if [ -n "$NDK" ]; then
  ndk_rev=$(sed -n 's/^Pkg.Revision *= *//p' "$NDK/source.properties")
  mkdir -p "$OUT/extract/cxx-runtime"
  cp "$NDK/toolchains/llvm/prebuilt/darwin-x86_64/sysroot/usr/lib/aarch64-linux-android/libc++_shared.so" "$OUT/extract/cxx-runtime/"
fi

# Every regular file of both trees: path, size, sha256; `file` and DT_NEEDED for the binaries.
python3 -I - "$OUT" "$BIN_ASSET" "$MODEL_ASSET" "$TAG" "$published" "$tag_commit" "$bin_json" "$model_json" "$ndk_rev" "$JNI_ASSET" "$jni_json" > "$OUT/LOCK.json" <<'EOF'
import hashlib, json, os, pathlib, re, subprocess, sys
out, bin_asset, model_asset, tag, published, tag_commit, bin_json, model_json, ndk_rev, jni_asset, jni_json = sys.argv[1:12]

def ort_strings(p):
    """ONNX Runtime's version (ORT_VERSION, a NUL-terminated "1.x.y") and build-info strings in a binary."""
    b = pathlib.Path(p).read_bytes()
    return {"version_strings": sorted({m.decode() for m in re.findall(rb"\x00(1\.\d{1,2}\.\d{1,2})\x00", b)}),
            "build_info": sorted({m.decode() for m in re.findall(rb"ORT Build Info: [^\x00]*", b)})}

def needed(p):
    r = subprocess.run(["/usr/bin/objdump", "-p", str(p)], capture_output=True, text=True)
    return [l.split()[1] for l in r.stdout.splitlines() if l.strip().startswith("NEEDED")]

def tree(root, with_file):
    rows = []
    root = pathlib.Path(root)
    for p in sorted(root.rglob("*")):
        if p.is_symlink():
            rows.append({"path": str(p.relative_to(root)), "symlink": os.readlink(p)})
        elif p.is_file():
            h = hashlib.sha256()
            with open(p, "rb") as f:
                for block in iter(lambda: f.read(1 << 20), b""):
                    h.update(block)
            row = {"path": str(p.relative_to(root)), "size": p.stat().st_size, "sha256": h.hexdigest()}
            if with_file and ("/bin/" in "/" + row["path"] or p.suffix == ".so" or ".so." in p.name):
                row["file"] = subprocess.run(["file", "-b", str(p)], capture_output=True, text=True).stdout.strip()
                row["needed"] = needed(p)
            rows.append(row)
    return rows

lock = {
    "repo": "k2-fsa/sherpa-onnx", "tag": tag, "tag_commit": tag_commit, "published_at": published,
    "binary_asset": json.loads(bin_json), "model_asset": json.loads(model_json),
    "binary_files": tree(pathlib.Path(out) / "extract" / bin_asset, True),
    "model_files": tree(pathlib.Path(out) / "extract" / model_asset, False),
}
ext = pathlib.Path(out) / "extract"
static_bin = next((ext / bin_asset).rglob("bin/sherpa-onnx-offline-parallel"))
jni_ort = next((ext / jni_asset).rglob("arm64-v8a/libonnxruntime.so"))
lock["onnxruntime"] = {
    "termux_binary": {"file": str(static_bin.relative_to(ext / bin_asset)), **ort_strings(static_bin)},
    "android_jnilibs": {"asset": json.loads(jni_json), "file": str(jni_ort.relative_to(ext / jni_asset)),
                        "size": jni_ort.stat().st_size,
                        "sha256": hashlib.sha256(jni_ort.read_bytes()).hexdigest(), **ort_strings(jni_ort)},
}
if ndk_rev:
    lock["cxx_runtime"] = {
        "why": "the termux binaries need libc++_shared.so (DT_NEEDED); no v1.13.8 Android asset ships it",
        "source": f"Android NDK {ndk_rev}, toolchains/llvm/prebuilt/darwin-x86_64/sysroot/usr/lib/aarch64-linux-android/libc++_shared.so",
        "files": tree(pathlib.Path(out) / "extract" / "cxx-runtime", True),
    }
print(json.dumps(lock, indent=2))
EOF
python3 -I -c 'import json, sys; d = json.load(open(sys.argv[1])); print(d["binary_asset"]["name"], d["binary_asset"]["sha256"]); print(d["model_asset"]["name"], d["model_asset"]["sha256"]); print(len(d["binary_files"]), "binary-tree files,", len(d["model_files"]), "model files")' "$OUT/LOCK.json"
