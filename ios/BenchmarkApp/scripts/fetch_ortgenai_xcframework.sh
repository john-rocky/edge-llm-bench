#!/usr/bin/env bash
# Fetch the ONNX Runtime GenAI release XCFramework the iPhone's onnxruntime-genai arm links
# (docs/ortgenai-arm-v1.md "iPhone"), check it against its pinned sha256, and lay out what
# the build reads:
#
#   Vendored/onnxruntime-genai.xcframework          the release framework, unmodified (a
#                                                    dynamic framework, CPU EP; ios-arm64 /
#                                                    simulator / Mac Catalyst slices, no macOS)
#   Vendored/onnxruntime-genai.xcframework.tag      "<version> <zip sha256>", written only after
#                                                    the zip matched its pin; stamp_engine_pins.sh
#                                                    turns it into the arm's engineVersion
#   Vendored/onnxruntime-genai-module/module.modulemap
#                                                    the release ships headers without a module
#                                                    map, and its hyphenated name cannot be a
#                                                    framework module: this map exposes the C API
#                                                    (ort_genai_c.h) as the Swift module
#                                                    `onnxruntime_genai` (project.yml
#                                                    SWIFT_INCLUDE_PATHS). It exists only next to
#                                                    the framework, so canImport(onnxruntime_genai)
#                                                    is false — and the adapter a stub — without it.
#
# Pin: environment.lock.json arms.onnxruntime-genai.ios.release_zip. Idempotent: a framework
# whose tag names the pinned version and sha is left alone.
set -euo pipefail

cd "$(dirname "$0")/.."   # ios/BenchmarkApp

ORTGENAI_VERSION="${ORTGENAI_VERSION:-0.17.0}"
ORTGENAI_ZIP_SHA256="${ORTGENAI_ZIP_SHA256:-699697a1cf0699978083478a028857c188814f027a41b100dad1116cf45ce6cb}"
URL="https://github.com/microsoft/onnxruntime-genai/releases/download/v${ORTGENAI_VERSION}/onnxruntime-genai-ios-${ORTGENAI_VERSION}.zip"

V="Vendored"
FW="${V}/onnxruntime-genai.xcframework"
TAG="${FW}.tag"
MODDIR="${V}/onnxruntime-genai-module"
mkdir -p "${V}"

if [ -d "${FW}" ] && [ "$(cat "${TAG}" 2>/dev/null || true)" = "${ORTGENAI_VERSION} ${ORTGENAI_ZIP_SHA256}" ]; then
    echo "onnxruntime-genai.xcframework ${ORTGENAI_VERSION} already vendored (${TAG})"
else
    # Another version, a partial unpack or no tag: start over (no module map without a framework).
    rm -rf "${FW}" "${TAG}" "${MODDIR}"
    WORK="$(mktemp -d -t ortgenai-xcf)"
    trap 'rm -rf "${WORK}"' EXIT
    mkdir "${WORK}/dl" "${WORK}/unpack"
    echo "Downloading onnxruntime-genai-ios-${ORTGENAI_VERSION}.zip …"
    curl -L --fail -o "${WORK}/dl/release.zip" "${URL}"
    GOT="$(shasum -a 256 "${WORK}/dl/release.zip" | awk '{print $1}')"
    if [ "${GOT}" != "${ORTGENAI_ZIP_SHA256}" ]; then
        echo "ERROR: ${URL}" >&2
        echo "       sha256 ${GOT}, pinned ${ORTGENAI_ZIP_SHA256} — not vendored" >&2
        exit 1
    fi
    unzip -q "${WORK}/dl/release.zip" -d "${WORK}/unpack"
    SLICE="${WORK}/unpack/onnxruntime-genai.xcframework/ios-arm64/onnxruntime-genai.framework"
    if [ ! -f "${SLICE}/onnxruntime-genai" ] || [ ! -f "${SLICE}/Headers/ort_genai_c.h" ]; then
        echo "ERROR: the zip has no ios-arm64 onnxruntime-genai.framework with Headers/ort_genai_c.h" >&2
        exit 1
    fi
    mv "${WORK}/unpack/onnxruntime-genai.xcframework" "${FW}"
    printf '%s %s\n' "${ORTGENAI_VERSION}" "${ORTGENAI_ZIP_SHA256}" > "${TAG}"
fi

# Device builds only (the bench runs on phones): the map points at the ios-arm64 slice's header.
mkdir -p "${MODDIR}"
cat > "${MODDIR}/module.modulemap" <<'EOF'
module onnxruntime_genai [system] {
    header "../onnxruntime-genai.xcframework/ios-arm64/onnxruntime-genai.framework/Headers/ort_genai_c.h"
    export *
}
EOF

echo "onnxruntime-genai ${ORTGENAI_VERSION} -> ${FW}"
echo "  ios-arm64 binary sha256 $(shasum -a 256 "${FW}/ios-arm64/onnxruntime-genai.framework/onnxruntime-genai" | awk '{print $1}')"
echo "  module map -> ${MODDIR}/module.modulemap"
