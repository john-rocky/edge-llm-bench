#!/usr/bin/env python3
"""Write the record's LOCK.json for asr-pr-v1 (docs/asr-pr-v1.md; asr-fix-v1's make_lock.py): the
PR branch and the benchmark commit, the three APKs, every native library inside the measured APK
with the artifact it came from, the LiteRT 2.3.0 witness (the LiteRT AARs Gradle resolved, their
sha256 and the sha256 of every arm64 library inside them, matched byte for byte with the APK's), the
sherpa-onnx AAR the benchmark build still bundles (no run of this round loads it), the model files,
the WAV set and the build tools. Reads only.

Usage: make_lock.py --apk-dir .build/asr-pr/apk --aar <sherpa-onnx-1.13.8.aar>
                    --models .build/asr-pr/models/models.lock.json --parquet .build/asr-pr/download/PARQUET.json
                    --set .build/asr-pr/set --app-dir <AndroidApp dir> --pr-dir <PR worktree>
                    --fix-lock <asr-fix-v1 LOCK.json> --out <record dir>/LOCK.json
"""
import argparse
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
import zipfile

# The app's own native library: CMake (src/main/cpp/tokenizer_jni.cc + libtokenizers_c.a), built per
# build type and per checkout, so its bytes are this build's.
APP_CMAKE_LIBS = {"libtokenizer_jni.so"}
GRADLE_LITERT = pathlib.Path.home() / ".gradle/caches/modules-2/files-2.1/com.google.ai.edge.litert"


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for block in iter(lambda: f.read(1 << 22), b""):
            h.update(block)
    return h.hexdigest()


def sha1_file(p):
    h = hashlib.sha1()
    with open(p, "rb") as f:
        for block in iter(lambda: f.read(1 << 22), b""):
            h.update(block)
    return h.hexdigest()


def git(d, *a):
    return subprocess.run(["git", "-C", str(d), *a], capture_output=True, text=True).stdout.strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    for a in ("apk-dir", "aar", "models", "parquet", "set", "app-dir", "pr-dir", "fix-lock", "out"):
        ap.add_argument("--" + a, required=True)
    args = ap.parse_args()
    apk_dir = pathlib.Path(args.apk_dir)
    app_dir = pathlib.Path(args.app_dir)

    sums = dict(reversed(line.split()) for line in open(apk_dir / "SHA256SUMS") if line.strip())
    commit, dirty = (open(apk_dir / "APP_COMMIT").read().split() + [""])[:2]

    # The LiteRT AARs Gradle resolved for the build (version 2.3.0) and their arm64 libraries.
    litert = {}
    aar_libs = {}
    for aar in sorted(GRADLE_LITERT.glob("*/2.3.0/*/*-2.3.0.aar")):
        with zipfile.ZipFile(aar) as z:
            libs = {n.rsplit("/", 1)[1]: {"sha256": sha256_bytes(z.read(n)), "bytes": z.getinfo(n).file_size}
                    for n in sorted(z.namelist()) if n.startswith("jni/arm64-v8a/") and n.endswith(".so")}
        litert[aar.name] = {
            "maven": f"com.google.ai.edge.litert:{aar.parent.parent.parent.name}:2.3.0",
            "sha256": sha256_file(aar), "sha1": sha1_file(aar), "gradle_cache_dir_sha1": aar.parent.name,
            "bytes": aar.stat().st_size, "jni_arm64_v8a": libs,
        }
        for name, v in libs.items():
            aar_libs[(name, v["sha256"])] = aar.name
    with zipfile.ZipFile(args.aar) as z:
        sherpa_libs = {n.rsplit("/", 1)[1]: sha256_bytes(z.read(n)) for n in z.namelist()
                       if n.startswith("jni/arm64-v8a/") and n.endswith(".so")}

    fix = json.load(open(args.fix_lock))
    fix_libs = {k: v["sha256"] for k, v in fix["native_libs_in_bench_apk"].items()}
    libs = {}
    with zipfile.ZipFile(apk_dir / "app-bench.apk") as z:
        for n in sorted(z.namelist()):
            if n.startswith("lib/arm64-v8a/") and n.endswith(".so"):
                name = n.rsplit("/", 1)[1]
                s = sha256_bytes(z.read(n))
                origin = (aar_libs[(name, s)] + " jni/arm64-v8a" if (name, s) in aar_libs else
                          "sherpa-onnx-1.13.8.aar jni/arm64-v8a" if sherpa_libs.get(name) == s else
                          "the app's own CMake target (src/main/cpp), built in this worktree" if name in APP_CMAKE_LIBS else
                          "UNMATCHED")
                libs[name] = {"sha256": s, "bytes": z.getinfo(n).file_size, "origin": origin,
                              "same_bytes_as_asr_fix_v1_bench_apk": fix_libs.get(name) == s,
                              "in_asr_fix_v1_bench_apk": name in fix_libs}
    with zipfile.ZipFile(apk_dir / "app-debug.apk") as z:
        debug_libs = {n.rsplit("/", 1)[1]: sha256_bytes(z.read(n)) for n in z.namelist()
                      if n.startswith("lib/arm64-v8a/") and n.endswith(".so")}

    set_dir = pathlib.Path(args.set)
    tar_rec = json.load(open(set_dir / "test-clean-S32WE.tar.json"))
    s32 = json.load(open(set_dir / "SET-S32.json"))
    edge = json.load(open(set_dir / "SET-edge.json"))
    wrapper = (app_dir / "gradle/wrapper/gradle-wrapper.properties").read_text()
    versions = (app_dir / "gradle/libs.versions.toml").read_text()
    pr_dir = pathlib.Path(args.pr_dir)
    lock = {
        "harness": "asr-pr-v1",
        "pr_branch": {
            "repo": "google-ai-edge/litert-samples",
            "path": "samples/litert/speech_recognition/AndroidApp",
            "upstream_commit": git(pr_dir, "merge-base", "HEAD", "upstream/main"),
            "upstream_main_at_lock": git(pr_dir, "rev-parse", "upstream/main"),
            "branch": git(pr_dir, "rev-parse", "--abbrev-ref", "HEAD"),
            "head": git(pr_dir, "rev-parse", "HEAD"),
            # A later amend of a commit message keeps the tree: the tree is what was built and run.
            "head_tree": git(pr_dir, "rev-parse", "HEAD^{tree}"),
            "commits": git(pr_dir, "log", "--format=%H %s", "upstream/main..HEAD").splitlines(),
        },
        "app": {
            "bench_branch": git(app_dir, "rev-parse", "--abbrev-ref", "HEAD"),
            "bench_commit": commit,
            "bench_parent": git(app_dir, "rev-parse", "HEAD~1"),
            "dirty_tracked_files_at_freeze": dirty,
            "application_id": "com.google.ai.edge.examples.asr.prcheck (applicationIdSuffix .prcheck)",
            "test_application_id": "com.google.ai.edge.examples.asr.prcheck.test",
            "measured_build_type": "bench = initWith(release) + debug signing key: not debuggable, no minify; testBuildType = bench",
            "setup_build_type": "debug (debuggable: run-as copies the models and WAVs into the app's files dir before the bench build is installed over it)",
        },
        "apk": sums,
        "native_libs_in_bench_apk": libs,
        "native_libs_debug_apk_differ": {k: {"debug_sha256": debug_libs.get(k), "bench_sha256": v["sha256"]}
                                         for k, v in libs.items() if debug_libs.get(k) != v["sha256"]},
        "litert": {"version": "2.3.0", "dependencies": ["com.google.ai.edge.litert:litert:2.3.0",
                                                         "com.google.ai.edge.litert:litert-gpu:2.3.0"],
                   "aars": litert},
        "sherpa_onnx_aar": {"asset": "https://github.com/k2-fsa/sherpa-onnx/releases/download/v1.13.8/sherpa-onnx-1.13.8.aar",
                            "sha256": sha256_file(args.aar), "bytes": os.path.getsize(args.aar),
                            "jni_arm64_v8a": sherpa_libs,
                            "note": "bundled as in asr-burst-v1 / asr-fix-v1 (AsrBenchTest's sherpa engine); no run of this round loads it"},
        "models": json.load(open(args.models)),
        "parquet": json.load(open(args.parquet)),
        "wav_set": {**tar_rec, "s32_set": {k: s32[k] for k in ("set", "rule", "utterances", "total_seconds",
                                                               "wav_sha256_chain", "first_ids", "last_id", "matches_asr_fix_v1")},
                    "full_chain": s32["full"]["wav_sha256_chain"], "edge": edge["rows"]},
        "build": {
            "gradle_wrapper": re.search(r"distributionUrl=.*/gradle-([0-9.]+)-", wrapper).group(1),
            "agp": re.search(r'^agp = "([^"]+)"', versions, re.M).group(1),
            "kotlin": re.search(r'^kotlin = "([^"]+)"', versions, re.M).group(1),
            "daemon_toolchain": re.search(r"toolchainVersion=(\d+)",
                                          (app_dir / "gradle/gradle-daemon-jvm.properties").read_text()).group(1),
            "compileSdk": 35, "targetSdk": 35, "minSdk": 31,
        },
    }
    pathlib.Path(args.out).write_text(json.dumps(lock, indent=2) + "\n")
    unmatched = [k for k, v in libs.items() if v["origin"] == "UNMATCHED"]
    print(json.dumps({"apk": sums, "libs": {k: v["origin"] for k, v in libs.items()}, "unmatched": unmatched,
                      "litert_aars": {k: v["sha256"][:16] for k, v in litert.items()},
                      "same_as_asr_fix_v1": sorted(k for k, v in libs.items() if v["same_bytes_as_asr_fix_v1_bench_apk"]),
                      "debug_apk_libs_differ": sorted(lock["native_libs_debug_apk_differ"])}, indent=1))
    return 1 if unmatched or not litert else 0


if __name__ == "__main__":
    sys.exit(main())
