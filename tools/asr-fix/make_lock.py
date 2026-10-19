#!/usr/bin/env python3
"""Write the record's LOCK.json for asr-fix-v1 (docs/asr-fix-v1.md; asr-burst-v1's make_lock.py): the
app commit, the three APKs, every native library inside the measured APK with the artifact it came
from (and whether asr-burst-v1's bench APK carried the same bytes), the sherpa-onnx AAR the build
still bundles (its arm64 libraries; no arm of this round loads them), the LiteRT artifacts, the two
model files, the WAV set and the build tools. Reads only.

Usage: make_lock.py --apk-dir .build/asr-fix/apk --aar <sherpa-onnx-1.13.8.aar> --aar-x <unzipped AAR dir>
                    --models .build/asr-fix/models/models.lock.json --set .build/asr-fix/set
                    --litert-lock <asr-litert-app-v1 LOCK.json> --npu-sums <kev_work/npu/libs/SHA256SUMS>
                    --burst-lock <asr-burst-v1 LOCK.json> --app-dir <AndroidApp dir> --out <record dir>/LOCK.json
"""
import argparse
import hashlib
import io
import json
import os
import pathlib
import re
import subprocess
import sys
import zipfile


# The app's own native library: CMake (src/main/cpp/tokenizer_jni.cc + libtokenizers_c.a), built per
# build type (bench = CMake Release, debug = Debug) and per checkout, so its bytes are this build's.
APP_CMAKE_LIBS = {"libtokenizer_jni.so"}


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for block in iter(lambda: f.read(1 << 22), b""):
            h.update(block)
    return h.hexdigest()


def needed(path):
    out = subprocess.run(["/usr/bin/objdump", "-p", str(path)], capture_output=True, text=True).stdout
    return [line.split()[-1] for line in out.splitlines() if line.strip().startswith("NEEDED")]


def main() -> int:
    ap = argparse.ArgumentParser()
    for a in ("apk-dir", "aar", "aar-x", "models", "set", "litert-lock", "npu-sums", "burst-lock", "app-dir", "out"):
        ap.add_argument("--" + a, required=True)
    args = ap.parse_args()
    apk_dir = pathlib.Path(args.apk_dir)
    app_dir = pathlib.Path(args.app_dir)

    sums = dict(reversed(line.split()) for line in open(apk_dir / "SHA256SUMS") if line.strip())
    commit, dirty = (open(apk_dir / "APP_COMMIT").read().split() + [""])[:2]

    # Native libraries in the measured APK and where each came from.
    litert = json.load(open(args.litert_lock))
    litert_libs = litert["litert"]["native_libs_in_apk_sha256"]
    npu = {os.path.basename(l.split()[-1]): l.split()[0] for l in open(args.npu_sums) if l.strip()}
    aar_x = pathlib.Path(args.aar_x)
    aar_libs = {p.name: sha256_file(p) for p in sorted((aar_x / "jni/arm64-v8a").glob("*.so"))}
    libs = {}
    with zipfile.ZipFile(apk_dir / "app-bench.apk") as z:
        for n in sorted(z.namelist()):
            if n.startswith("lib/arm64-v8a/") and n.endswith(".so"):
                name = n.rsplit("/", 1)[1]
                s = sha256_bytes(z.read(n))
                origin = ("sherpa-onnx-1.13.8.aar jni/arm64-v8a" if aar_libs.get(name) == s else
                          "Qualcomm runtime (kev_work/npu/libs, asr-litert-app-v1 LOCK npu_runtime_libs)" if npu.get(name) == s else
                          "same bytes as the asr-litert-app-v1 APK (LiteRT 2.2.0 AARs)" if litert_libs.get(name) == s else
                          "the app's own CMake target (src/main/cpp), built in this worktree" if name in APP_CMAKE_LIBS else
                          "UNMATCHED")
                libs[name] = {"sha256": s, "bytes": z.getinfo(n).file_size, "origin": origin}
    burst = json.load(open(args.burst_lock))
    burst_libs = {k: v["sha256"] for k, v in burst["native_libs_in_bench_apk"].items()}
    for name, v in libs.items():
        v["same_bytes_as_asr_burst_v1_bench_apk"] = burst_libs.get(name) == v["sha256"]
    with zipfile.ZipFile(apk_dir / "app-debug.apk") as z:
        debug_libs = {n.rsplit("/", 1)[1]: sha256_bytes(z.read(n)) for n in z.namelist()
                      if n.startswith("lib/arm64-v8a/") and n.endswith(".so")}

    ort = aar_x / "jni/arm64-v8a/libonnxruntime.so"
    blob = ort.read_bytes()
    aar = {
        "asset": "https://github.com/k2-fsa/sherpa-onnx/releases/download/v1.13.8/sherpa-onnx-1.13.8.aar",
        "release": "k2-fsa/sherpa-onnx v1.13.8 (tag commit 11afbd009a7f8c08f4bcf2fc1b265d0df4670fbf, published 2026-09-10T14:00:23Z)",
        "github_digest": "sha256:633c24321e06b1fe79feafa03ea16cbc0f8a286641e2da3559bac91bdb13bd96",
        "github_size": 50129134,
        "github_updated_at": "2026-09-10T14:59:21Z",
        "bytes": os.path.getsize(args.aar),
        "sha256": sha256_file(args.aar),
        "classes_jar_sha256": sha256_file(aar_x / "classes.jar"),
        "jni_arm64_v8a": {name: {"sha256": s, "bytes": (aar_x / "jni/arm64-v8a" / name).stat().st_size,
                                 "needed": needed(aar_x / "jni/arm64-v8a" / name)} for name, s in aar_libs.items()},
        "onnxruntime": {
            "version_strings": sorted(set(re.findall(rb"(?<![0-9.])1\.28\.[0-9]+", blob))),
            "build_info": sorted(set(m.decode() for m in re.findall(rb"ORT Build Info: [ -~]{0,96}?build type=[A-Za-z]+", blob))),
        },
        "jni_same_as_asr_sherpa_v1_android_tar": "the four arm64 libraries have the sha256 of sherpa-onnx-v1.13.8-android.tar.bz2 jniLibs (asr-sherpa-v1 LOCK onnxruntime.android_jnilibs: libonnxruntime.so 33847ad4…)",
    }
    aar["onnxruntime"]["version_strings"] = [v.decode() for v in aar["onnxruntime"]["version_strings"]]

    tar_rec = json.load(open(pathlib.Path(args.set) / "test-clean-S4W.tar.json"))
    set_recs = {n: json.load(open(pathlib.Path(args.set) / f"SET-{n}.json")) for n in ("S4", "S16", "S32")}
    wrapper = (app_dir / "gradle/wrapper/gradle-wrapper.properties").read_text()
    versions = (app_dir / "gradle/libs.versions.toml").read_text()
    lock = {
        "harness": "asr-fix-v1",
        "app": {
            "repo": "google-ai-edge/litert-samples",
            "path": "samples/litert/speech_recognition/AndroidApp",
            "upstream_commit": "d15f8ae9",
            "base": "asr-burst-v1 benchmark commit 5f23093f (branch asr-bench-s26-burst: 89f0c45e + 289d4672 + ddbb14c7 + 5f23093f)",
            "bench_branch": "asr-bench-s26-fix",
            "bench_commit": commit,
            "dirty_tracked_files_at_freeze": dirty,
            "application_id": "com.google.ai.edge.examples.asr.burstfix (applicationIdSuffix .burstfix)",
            "test_application_id": "com.google.ai.edge.examples.asr.burstfix.test",
            "measured_build_type": "bench = initWith(release) + debug signing key: not debuggable, no minify; testBuildType = bench",
            "setup_build_type": "debug (debuggable: run-as copies the models and WAVs into the app's files dir before the bench build is installed over it)",
        },
        "apk": sums,
        "native_libs_in_bench_apk": libs,
        "native_libs_debug_apk_differ": {k: {"debug_sha256": debug_libs.get(k), "bench_sha256": v["sha256"]}
                                         for k, v in libs.items() if debug_libs.get(k) != v["sha256"]},
        "sherpa_onnx_aar": aar,
        "litert": {k: litert["litert"][k] for k in ("version", "resolved", "aars")},
        "npu_runtime_libs": {k: litert["npu_runtime_libs"][k] for k in ("staging", "origin", "license")},
        "models": json.load(open(args.models)),
        "wav_set": {**tar_rec,
                    **{f"{n.lower()}_set": {k: r[k] for k in ("set", "rule", "utterances", "total_seconds", "wav_sha256_chain", "first_ids", "last_id")}
                       for n, r in set_recs.items()},
                    "full_chain": set_recs["S4"]["full"]["wav_sha256_chain"]},
        "build": {
            "gradle_wrapper": re.search(r"distributionUrl=.*/gradle-([0-9.]+)-", wrapper).group(1),
            "agp": re.search(r'^agp = "([^"]+)"', versions, re.M).group(1),
            "kotlin": re.search(r'^kotlin = "([^"]+)"', versions, re.M).group(1),
            "launcher_java_home": os.environ.get("JAVA_HOME"),
            "compileSdk": 35, "targetSdk": 35, "minSdk": 31,
        },
    }
    pathlib.Path(args.out).write_text(json.dumps(lock, indent=2) + "\n")
    unmatched = [k for k, v in libs.items() if v["origin"] == "UNMATCHED"]
    print(json.dumps({"apk": sums, "libs": len(libs), "unmatched": unmatched,
                      "differ_from_asr_burst_v1": sorted(k for k, v in libs.items() if not v["same_bytes_as_asr_burst_v1_bench_apk"]),
                      "debug_apk_libs_differ": sorted(lock["native_libs_debug_apk_differ"]),
                      "aar_sha256": aar["sha256"], "ort": aar["onnxruntime"]}, indent=1))
    return 1 if unmatched else 0


if __name__ == "__main__":
    sys.exit(main())
