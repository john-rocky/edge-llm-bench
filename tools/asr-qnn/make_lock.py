#!/usr/bin/env python3
"""LOCK.json of the asr-qnn-v1 A2 arm: every file the phone runs, by sha256, and where its version is read.

  python3 -I tools/asr-qnn/make_lock.py <.build/asr-qnn> <LOCK.json>

Reads what fetch.sh downloaded and extracted and what build.sh built; reads versions from the files themselves
(sdk.yaml, the build id inside model.bin, the onnxruntime strings inside libonnxruntime.so).
"""
import hashlib
import json
import pathlib
import re
import subprocess
import sys

MODEL = "sherpa-onnx-qnn-SM8850-binary-parakeet-ctc-0.6b-30s"
QAIRT = "2.40.0.251030"
QNN_LIBS = ["aarch64-android/libQnnHtp.so", "aarch64-android/libQnnHtpPrepare.so", "aarch64-android/libQnnSystem.so",
            "aarch64-android/libQnnHtpV81Stub.so", "hexagon-v81/unsigned/libQnnHtpV81Skel.so"]
BINS = ["sherpa-onnx-offline-parallel", "sherpa-onnx-offline", "sherpa-onnx-version"]


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def entry(p, **extra):
    p = pathlib.Path(p)
    return {"bytes": p.stat().st_size, "sha256": sha(p), **extra}


def strings(p, pattern, limit=4):
    data = pathlib.Path(p).read_bytes()
    out = []
    for m in re.finditer(pattern, data):
        s = m.group(0).decode("ascii", "replace")
        if s not in out:
            out.append(s)
        if len(out) >= limit:
            break
    return out


def main():
    b, out = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
    here = pathlib.Path(__file__).resolve().parent
    qroot = b / "extract/qairt/qairt" / QAIRT
    sdk = dict(l.split(": ", 1) for l in (qroot / "sdk.yaml").read_text().splitlines() if ": " in l and not l.startswith("#"))
    mdir = b / "extract/model" / MODEL
    src = b / "src/sherpa-onnx"
    inst = src / "build-android-arm64-v8a/install"
    cache = (src / "build-android-arm64-v8a/CMakeCache.txt").read_text()
    cached = lambda key: (re.search(rf"^{key}:[A-Z]+=(.*)$", cache, re.M) or [None, None])[1]
    # The toolchain's ar lives at <ndk>/toolchains/llvm/prebuilt/<host>/bin/llvm-ar.
    ndk = pathlib.Path(cached("CMAKE_AR") or "").parents[5] if cached("CMAKE_AR") else pathlib.Path("")
    ndk_rev = None
    if (ndk / "source.properties").exists():
        ndk_rev = (re.search(r"Pkg.Revision = (\S+)", (ndk / "source.properties").read_text()) or [None, None])[1]
    ort = inst / "lib/libonnxruntime.so"
    cmake_version = subprocess.run(["cmake", "--version"], capture_output=True, text=True).stdout.splitlines()[0]
    lock = {
        "arm": "A2: sherpa-onnx v1.13.8 + QNN (HTP), parakeet-ctc-0.6b SM8850 context binary, 30 s window",
        "qairt": {
            "version": QAIRT,
            "sdk_yaml": {k: sdk.get(k) for k in ("product", "version", "build_id", "qnn_backend_api_version", "android-ndk")},
            "zip_url": f"https://softwarecenter.qualcomm.com/api/download/software/sdks/Qualcomm_AI_Runtime_Community/All/{QAIRT}/v{QAIRT}.zip",
            "zip": entry(b / f"download/qairt/v{QAIRT}.zip", note="public download, no login; Qualcomm publishes no digest"),
            "license_note": "Qualcomm's license: the libraries ship only inside an application; used here for the measurement, never committed or published",
            "phone_libs": {pathlib.Path(l).name: entry(qroot / "lib" / l, zip_path=f"qairt/{QAIRT}/lib/{l}") for l in QNN_LIBS},
            "libQnnHtp_build_strings": strings(qroot / "lib/aarch64-android/libQnnHtp.so", rb"v2\.\d+\.\d+\.\d+[0-9_]*"),
        },
        "model": {
            "name": MODEL,
            "url": f"https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models-qnn-binary/{MODEL}.tar.bz2",
            "release": "k2-fsa/sherpa-onnx asr-models-qnn-binary, asset updated 2026-06-17T15:55:18Z",
            "tar": entry(b / f"download/model/{MODEL}.tar.bz2", release_digest="sha256:31a71db22d129d198612689e61bf5c5fc8f6480bd09b3cc71def8f0fb99273ee"),
            "files": {n: entry(mdir / n) for n in ("model.bin", "tokens.txt", "info.txt")},
            "info_txt": (mdir / "info.txt").read_text().strip(),
            "readme": "none in the tar (info.txt, tokens.txt, model.bin, test_wavs/)",
            "qnn_sdk_of_the_context_binary": {
                "build_id_strings_in_model_bin": strings(mdir / "model.bin", rb"v2\.\d+\.\d+\.\d{12}_\d+(?:\.[0-9a-f]+)?"),
                "release_body": "Context binary files in this page are generated using qnn sdk 2.40.0.251030",
            },
            "export_recipe": {
                "workflow": "k2-fsa/sherpa-onnx .github/workflows/export-parakeet-ctc-qnn.yaml at 9961aee6 (2026-06-18, 'Export Parakeet CTC models to QNN (#3686)'; the release assets are dated 2026-06-17, the PR's runs)",
                "num_frames": "num_seconds * 100 = 3000 for 30 s; model input x [1, frames, 80] (sherpa's QNN impl reads it from the graph)",
                "converter": "qnn-onnx-converter --input_list <calibration raws> --use_native_input_files --act_bitwidth 16 --bias_bitwidth 32 (weights_bitwidth default 8: QAIRT 2.40 converter source) = post-training quantized, int8 weights, 16-bit activations",
                "context_config": "scripts/qnn/generate_config.py: SM8850 soc_id 87, dsp_arch v81, vtcm_mb 8, O 3, perf_profile burst (for qnn-context-binary-generator)",
            },
        },
        "sherpa_onnx": {
            "tag": "v1.13.8",
            "commit": subprocess.run(["git", "-C", str(src), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(),
            "build": {
                "command": "SHERPA_ONNX_ENABLE_QNN=ON SHERPA_ONNX_ENABLE_BINARY=ON SHERPA_ONNX_ANDROID_PLATFORM=android-24 CMAKE_POLICY_VERSION_MINIMUM=3.5 QNN_SDK_ROOT=<qairt> ANDROID_NDK=<ndk> ./build-android-arm64-v8a.sh (tools/asr-qnn/build.sh)",
                "android_platform": cached("ANDROID_PLATFORM"),
                "android_platform_why": "the script's default android-21 does not link the executables with NDK 28: libonnxruntime.so 1.28.2 needs API 23-24 libc symbols (__write_chk@LIBC_N ...), lld refuses them for an executable",
                "ndk": str(ndk), "ndk_revision": ndk_rev, "cmake": cmake_version,
                "build_type": cached("CMAKE_BUILD_TYPE"), "shared_libs": cached("BUILD_SHARED_LIBS"),
                "qnn": cached("SHERPA_ONNX_ENABLE_QNN"), "binary": cached("SHERPA_ONNX_ENABLE_BINARY"),
                "stl": "c++_static (the toolchain default; the executables need no libc++_shared.so)",
            },
            "bins": {n: entry(inst / "bin" / n) for n in BINS},
        },
        "driver": {
            "source": entry(here / "burst_driver.cc", path="tools/asr-qnn/burst_driver.cc"),
            "bin": entry(b / "build-out/asr-qnn-burst-driver", how="compiled with sherpa-onnx-offline's compile rule, linked with its link.txt (object swapped), stripped"),
        },
        "onnxruntime": {
            "version_strings": strings(ort, rb"\b1\.\d+\.\d+\b", limit=1) + strings(ort, rb"ORT Build Info: [ -~]{0,120}"),
            "lib": entry(ort, source="https://github.com/csukuangfj/onnxruntime-libs/releases/download/v1.28.2/onnxruntime-android-1.28.2.zip (downloaded by build-android-arm64-v8a.sh)"),
            "note": "the model graph runs on the HTP through the QNN API (sherpa-onnx/csrc/qnn), not through onnxruntime",
        },
    }
    out.write_text(json.dumps(lock, indent=2, ensure_ascii=False) + "\n")
    print(f"LOCK.json: QAIRT {lock['qairt']['sdk_yaml']['build_id']}, model.bin {lock['model']['files']['model.bin']['sha256'][:12]}, "
          f"build ids in model.bin {lock['model']['qnn_sdk_of_the_context_binary']['build_id_strings_in_model_bin']}, "
          f"sherpa {lock['sherpa_onnx']['commit'][:8]}, onnxruntime {lock['onnxruntime']['version_strings']}")


if __name__ == "__main__":
    main()
