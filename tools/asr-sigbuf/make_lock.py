#!/usr/bin/env python3
"""LOCK.json of asr-sigbuf-v1 (docs/asr-sigbuf-v1.md): the APK sets (sha256, commit, the TdtDecoder.kt blob,
Gradle properties), every native library in the bench APKs (sha256; the Qualcomm runtime matched against
kev_work/npu/libs/SHA256SUMS), the LiteRT AARs the builds resolved, the models (models.lock.json: the Hub's
LFS sha256), the encoder outputs of the decoder-only runs, the WAV set, jLibrosa.

  make_lock.py --out results/raw/2026-10-22-asr-sigbuf-v1-s26-android/LOCK.json
Plain python3.
"""
import argparse
import hashlib
import json
import pathlib
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
B = ROOT / ".build" / "asr-sigbuf"
HOME = pathlib.Path.home()
NPU_SUMS = HOME / "code/litertlm-convert/kev_work/npu/libs/SHA256SUMS"
APPDIR = HOME / "code/litert-samples-asr-sigbuf-wt/samples/litert/speech_recognition/AndroidApp"
GRADLE_FILES = HOME / ".gradle/caches/modules-2/files-2.1/com.google.ai.edge.litert"
SETS = {
    "main": "com.google.ai.edge.examples.asr.sigbufcheck.main",
    "fix": "com.google.ai.edge.examples.asr.sigbufcheck.fix",
    "npu-fix": "com.google.ai.edge.examples.asr.sigbufcheck.npu",
    "npu-main": "com.google.ai.edge.examples.asr.sigbufcheck.npu",
}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def kv_file(path):
    out = {}
    for line in open(path):
        if line.strip():
            k, _, v = line.strip().partition(" ")
            out[k] = v
    return out


def apk_libs(apk):
    libs = {}
    with zipfile.ZipFile(apk) as z:
        for info in z.infolist():
            if info.filename.startswith("lib/") and info.filename.endswith(".so"):
                libs[info.filename.split("/")[-1]] = {"sha256": hashlib.sha256(z.read(info)).hexdigest(), "bytes": info.file_size}
    return libs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    npu = {}
    for line in open(NPU_SUMS):
        if line.strip():
            s, name = line.split()
            npu[name] = s
    lock = {
        "harness": "asr-sigbuf-v1",
        "app": {
            "repo": "google-ai-edge/litert-samples",
            "path": "samples/litert/speech_recognition/AndroidApp",
            "upstream_main": "367816dac824a1984648582060424a817dd5d69d",
            "upstream_tdt_decoder_blob": "683e118c (TdtDecoder.kt at 367816da)",
            "change_branch": "speech-recognition-tdt-separate-buffers",
            "check_branches": {"sigbufcheck-main": "upstream main + the check build", "sigbufcheck": "the change + the same check build"},
            "test_build_type": "bench = initWith(release) + debug signing key: not debuggable, no minify",
            "setup_build_type": "debug (debuggable: run-as copies the files into the app's files dir before the bench build is installed over it)",
        },
        "apk_sets": {},
        "litert_aars": {},
        "npu_runtime_libs": {
            "staging": "~/code/litertlm-convert/kev_work/npu/libs (PROVENANCE.md); the ten Qualcomm files copied to .build/asr-sigbuf/npu-jnilibs",
            "origin": "LiteRT v2.2.0 release litert_npu_runtime_libraries.zip (qualcomm_runtime_v81: libLiteRtDispatch_Qualcomm.so) + "
                      "litert_npu_runtime_libraries_jit.zip (libLiteRtCompilerPlugin_Qualcomm.so) + QAIRT 2.47.0 lib/aarch64-android and lib/hexagon-v81/unsigned",
            "license": "QAIRT AI Stack License: inside an APK only, benchmarking use; not redistributed standalone",
            "sha256": npu,
        },
    }
    for form_dir, form in (("apk", "form1"), ("apk2", "form2"), ("apk3", "form2-mainact")):
        for name, pkg in SETS.items():
            d = B / form_dir / name
            if not (d / "APP_COMMIT").exists():
                continue
            commit = kv_file(d / "APP_COMMIT")
            libs = apk_libs(d / "app-bench.apk")
            litert = "2.2.0" if name.startswith("npu") else "2.3.0"
            for lib, rec in libs.items():
                if lib in ("libLiteRt.so", "libLiteRtClGlAccelerator.so", "liblitert_jni.so", "libLiteRtGpuAccelerator.so"):
                    rec["origin"] = f"LiteRT {litert} Maven AAR contents"
                    if litert == "2.2.0" and lib in npu:
                        # kev_work's staging keeps the 2.2.0 core too (not packaged from there; the AAR's copy)
                        rec["same_bytes_as_staging_2_2_0"] = rec["sha256"] == npu[lib]
                elif lib in npu:
                    rec["origin"] = "Qualcomm runtime (kev_work/npu/libs SHA256SUMS)"
                    rec["matches_staging"] = rec["sha256"] == npu[lib]
                elif lib == "libtokenizer_jni.so":
                    rec["origin"] = "the app's own CMake target (src/main/cpp), built in the worktree"
            lock["apk_sets"][f"{form}/{name}"] = {
                "application_id": pkg,
                "test_application_id": pkg + ".test",
                "apk_sha256": {f: sha256(d / f) for f in ("app-debug.apk", "app-bench.apk", "app-bench-androidTest.apk")},
                **commit,
                "native_libs_in_bench_apk": libs,
            }
    for art in ("litert", "litert-api", "litert-gpu"):
        for ver in ("2.2.0", "2.3.0"):
            for aar in sorted((GRADLE_FILES / art / ver).glob(f"*/{art}-{ver}.aar")) if (GRADLE_FILES / art / ver).exists() else []:
                lock["litert_aars"][f"{art}-{ver}.aar"] = {"sha256": sha256(aar), "bytes": aar.stat().st_size}
    lock["litert_versions"] = {"main / fix": "litert 2.3.0 + litert-gpu 2.3.0 (the app's build.gradle.kts)",
                               "npu-fix / npu-main": "litert 2.2.0 (the release of the NPU runtime archive; v2.3.0 has none)"}
    lock["models"] = json.load(open(B / "models" / "models.lock.json"))
    lock["models_on_phone"] = {
        "parakeet_tdt_0.6b_v3_5s_i8_stateful.tflite": "parakeet-tdt-0.6b-v3/model.tflite in .main and .fix (the entry's CPU / GPU file)",
        "parakeet_tdt_ctc_0.6b_ja_5s_i8.tflite": "parakeet-tdt_ctc-0.6b-ja/model.tflite in .main and .fix",
        "tdt-tokenizer.json": "parakeet-tdt-0.6b-v3/tokenizer.json in all three",
        "ja-tokenizer.json": "parakeet-tdt_ctc-0.6b-ja/tokenizer.json in .main and .fix",
        "parakeet_tdt_0.6b_v3_5s_f32_stateful_Qualcomm_SM8850.tflite": "parakeet-tdt-0.6b-v3/model_npu.tflite in .npu (the entry's NPU file)",
        "parakeet_tdt_0.6b_v3_5s_f32_stateful.tflite": "parakeet-tdt-0.6b-v3/model_f32.tflite in .npu (dec-cpu-f32-*)",
    }
    lock["encoder_outputs"] = {
        "origin": "asr-npu-v1 b-tdt-cpu (results/raw/2026-10-20-asr-npu-v1-s26-android): the 5 s f32 stateful file's encode on the CPU "
                  "for LibriSpeech 4507-16021-0047 windows 1, 6, 11 and an all-zero input, raw float32 [1, 1024, 63]",
        "files": {p.name: {"sha256": sha256(p), "bytes": p.stat().st_size} for p in sorted((B / "enc").glob("*.f32"))},
    }
    tar = B / "set" / "test-clean-F20W.tar.json"
    if tar.exists():
        lock["wav_set"] = json.load(open(tar))
    jl = APPDIR / "app/libs/jlibrosa-1.1.8-SNAPSHOT-jar-with-dependencies.jar"
    if jl.exists():
        lock["jlibrosa_jar_sha256"] = sha256(jl)
    pathlib.Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(args.out).write_text(json.dumps(lock, indent=1) + "\n")
    bad = [f"{s}:{l}" for s, v in lock["apk_sets"].items() for l, r in v["native_libs_in_bench_apk"].items() if r.get("matches_staging") is False]
    print(f"LOCK: {len(lock['apk_sets'])} APK sets, {len(lock['litert_aars'])} AARs, {len(lock['models'])} models, "
          f"{len(lock['encoder_outputs']['files'])} encoder outputs; NPU libs not matching the staging: {bad or 'none'}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
