#!/usr/bin/env python3
"""Write the record's LOCK.json for asr-npu-v1 (docs/asr-npu-v1.md; asr-fix-v1's make_lock.py without
the sherpa-onnx part): the app commit, the three APKs, every native library inside the bench APK
with where its bytes came from (the Qualcomm runtime staging SHA256SUMS, or the same bytes as the
asr-fix-v1 bench APK = LiteRT 2.2.0, or the app's own CMake library), the LiteRT artifacts, the model
files (the Hub's hash), the B inputs, the WAV set and the build tools. Reads only.

Usage: make_lock.py --apk-dir .build/asr-npu/apk --models .build/asr-npu/models/models.lock.json
                    --mel .build/asr-npu/mel/MANIFEST --set .build/asr-npu/set
                    --fix-lock <asr-fix-v1 LOCK.json> --npu-sums <kev_work/npu/libs/SHA256SUMS>
                    --app-dir <AndroidApp dir> --out <record dir>/LOCK.json
"""
import argparse
import hashlib
import json
import os
import pathlib
import re
import sys
import zipfile

APP_CMAKE_LIBS = {"libtokenizer_jni.so"}
# The LiteRT runtime libraries: the Maven AARs' contents (kev_work/npu/libs/PROVENANCE.md l.7 for the
# two the staging dir also holds); the staging SHA256SUMS lists them beside the Qualcomm files.
LITERT_AAR_LIBS = {"libLiteRt.so", "libLiteRtClGlAccelerator.so", "liblitert_jni.so"}


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    for a in ("apk-dir", "models", "mel", "set", "fix-lock", "npu-sums", "app-dir", "out"):
        ap.add_argument("--" + a, required=True)
    args = ap.parse_args()
    apk_dir = pathlib.Path(args.apk_dir)
    app_dir = pathlib.Path(args.app_dir)
    sums = dict(reversed(line.split()) for line in open(apk_dir / "SHA256SUMS") if line.strip())
    commit, dirty = (open(apk_dir / "APP_COMMIT").read().split() + [""])[:2]
    fix = json.load(open(args.fix_lock))
    fix_libs = {k: v["sha256"] for k, v in fix["native_libs_in_bench_apk"].items()}
    npu = {os.path.basename(l.split()[-1]): l.split()[0] for l in open(args.npu_sums) if l.strip()}
    libs = {}
    with zipfile.ZipFile(apk_dir / "app-bench.apk") as z:
        for n in sorted(z.namelist()):
            if n.startswith("lib/arm64-v8a/") and n.endswith(".so"):
                name = n.rsplit("/", 1)[1]
                s = sha256_bytes(z.read(n))
                origin = ("LiteRT 2.2.0 Maven AAR contents (litert-2.2.0.aar / litert-api-2.2.0.aar; same bytes as the asr-fix-v1 bench APK)"
                          if name in LITERT_AAR_LIBS and fix_libs.get(name) == s else
                          "Qualcomm runtime (kev_work/npu/libs SHA256SUMS: LiteRT v2.2.0 qualcomm_runtime_v81 + QAIRT 2.47.0)" if npu.get(name) == s else
                          "same bytes as the asr-fix-v1 bench APK" if fix_libs.get(name) == s else
                          "the app's own CMake target (src/main/cpp), built in this worktree" if name in APP_CMAKE_LIBS else
                          "UNMATCHED")
                libs[name] = {"sha256": s, "bytes": z.getinfo(n).file_size, "origin": origin,
                              "same_bytes_as_asr_fix_v1_bench_apk": fix_libs.get(name) == s}
    mel = [dict(zip(("file", "sha256"), l.split())) for l in open(args.mel) if l.strip()]
    tar_rec = json.load(open(pathlib.Path(args.set) / "test-clean-F20W.tar.json"))
    wrapper = (app_dir / "gradle/wrapper/gradle-wrapper.properties").read_text()
    versions = (app_dir / "gradle/libs.versions.toml").read_text()
    lock = {
        "harness": "asr-npu-v1",
        "app": {
            "repo": "google-ai-edge/litert-samples",
            "path": "samples/litert/speech_recognition/AndroidApp",
            "upstream_commit": "d15f8ae9",
            "base": "asr-fix-v1 benchmark commit 6885e170 (branch asr-bench-s26-fix)",
            "bench_branch": "asr-bench-s26-npu",
            "bench_commit": commit,
            "dirty_tracked_files_at_freeze": dirty,
            "application_id": "com.google.ai.edge.examples.asr.npucheck (applicationIdSuffix .npucheck)",
            "test_application_id": "com.google.ai.edge.examples.asr.npucheck.test",
            "test_build_type": "bench = initWith(release) + debug signing key: not debuggable, no minify",
            "setup_build_type": "debug (debuggable: run-as copies the models, the B inputs and the WAVs into the app's files dir before the bench build is installed over it)",
        },
        "apk": sums,
        "native_libs_in_bench_apk": libs,
        "litert": fix["litert"],
        "npu_runtime_libs": fix["npu_runtime_libs"],
        "models": json.load(open(args.models)),
        "b_inputs": mel,
        "wav_set": tar_rec,
        "build": {
            "gradle_wrapper": re.search(r"distributionUrl=.*/gradle-([0-9.]+)-", wrapper).group(1),
            "agp": re.search(r'^agp = "([^"]+)"', versions, re.M).group(1),
            "kotlin": re.search(r'^kotlin = "([^"]+)"', versions, re.M).group(1),
            "compileSdk": 35, "targetSdk": 35, "minSdk": 31,
        },
    }
    pathlib.Path(args.out).write_text(json.dumps(lock, indent=2) + "\n")
    unmatched = [k for k, v in libs.items() if v["origin"] == "UNMATCHED"]
    print(json.dumps({"apk": sums, "libs": len(libs), "unmatched": unmatched,
                      "differ_from_asr_fix_v1": sorted(k for k, v in libs.items() if not v["same_bytes_as_asr_fix_v1_bench_apk"])},
                     indent=1))
    return 1 if unmatched else 0


if __name__ == "__main__":
    sys.exit(main())
