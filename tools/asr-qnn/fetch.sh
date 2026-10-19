#!/usr/bin/env bash
# Inputs of the asr-qnn-v1 A2 arm (docs/asr-qnn-v1.md), each in its own empty directory under .build/asr-qnn:
#   - k2-fsa's QNN context binary of parakeet-ctc-0.6b for SM8850, 30 s window (release asr-models-qnn-binary),
#     checked against the release's sha256 digest;
#   - QAIRT 2.40.0.251030 (the QNN SDK the context binary was made with: the release body and the build id the
#     binary carries), Qualcomm's public download; its headers (to build sherpa-onnx) and the HTP libraries the
#     phone loads are extracted. Qualcomm's license lets these libraries ship only inside an application: they are
#     used here for the measurement and never committed or published.
#   - sherpa-onnx v1.13.8 (shallow clone of the tag; build.sh builds it).
#
#   tools/asr-qnn/fetch.sh            download (skipped when the file is there and its sha256 matches), extract, clone
#   tools/asr-qnn/fetch.sh lock <out> LOCK.json after build.sh: versions, sha256 of every file the phone runs
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
repo=$(cd "$here/../.." && pwd)
B=${B:-$repo/.build/asr-qnn}
MODEL=sherpa-onnx-qnn-SM8850-binary-parakeet-ctc-0.6b-30s
MODEL_URL=https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models-qnn-binary/$MODEL.tar.bz2
MODEL_SHA256=31a71db22d129d198612689e61bf5c5fc8f6480bd09b3cc71def8f0fb99273ee  # the release asset's digest
QAIRT=2.40.0.251030
QAIRT_URL=https://softwarecenter.qualcomm.com/api/download/software/sdks/Qualcomm_AI_Runtime_Community/All/$QAIRT/v$QAIRT.zip
QAIRT_PARTS="include/* lib/aarch64-android/* lib/hexagon-v81/* sdk.yaml LICENSE.pdf QNN_README.txt QAIRT_ReleaseNotes.txt NOTICE.txt QNN_NOTICE.txt"
SHERPA_TAG=v1.13.8
SHERPA_COMMIT=11afbd009a7f8c08f4bcf2fc1b265d0df4670fbf

say() { echo "$(date '+%H:%M:%S') $*"; }
sha() { shasum -a 256 "$1" | cut -d' ' -f1; }

fetch() {
  mkdir -p "$B/download/model" "$B/download/qairt" "$B/extract/model" "$B/extract/qairt" "$B/logs"
  local m=$B/download/model/$MODEL.tar.bz2
  if [ ! -f "$m" ] || [ "$(sha "$m")" != "$MODEL_SHA256" ]; then
    say "model: downloading $MODEL_URL"
    curl -fL --retry 3 -sS -o "$m" "$MODEL_URL"
  fi
  [ "$(sha "$m")" = "$MODEL_SHA256" ] || { echo "model tar sha256 $(sha "$m") != release digest $MODEL_SHA256" >&2; exit 1; }
  say "model: $(stat -f %z "$m") B, sha256 = release digest $MODEL_SHA256"
  [ -f "$B/extract/model/$MODEL/model.bin" ] || tar xjf "$m" -C "$B/extract/model"

  local z=$B/download/qairt/v$QAIRT.zip
  if [ ! -f "$z" ]; then
    say "QAIRT: downloading $QAIRT_URL (no login; Qualcomm publishes no digest: its sha256 goes to LOCK.json)"
    curl -fL --retry 3 -sS -o "$z" "$QAIRT_URL"
  fi
  local parts=() p
  for p in $QAIRT_PARTS; do parts+=("qairt/$QAIRT/$p"); done
  unzip -tq "$z" "${parts[@]}" > /dev/null || { echo "QAIRT zip: the parts used here fail their CRC test" >&2; exit 1; }
  unzip -q -o "$z" "${parts[@]}" -d "$B/extract/qairt"
  grep -q "build_id: 251030114326_189385" "$B/extract/qairt/qairt/$QAIRT/sdk.yaml" || { echo "unexpected sdk.yaml" >&2; exit 1; }
  # The context binary carries the build id of the QNN SDK that made it.
  LC_ALL=C grep -a -q "v2.40.0.251030114326_189385" "$B/extract/model/$MODEL/model.bin" \
    || { echo "model.bin does not carry QAIRT $QAIRT's build id" >&2; exit 1; }
  say "QAIRT: $(stat -f %z "$z") B, sha256 $(sha "$z"), build id 251030114326_189385 = the one in model.bin"

  local src=$B/src/sherpa-onnx
  if [ ! -d "$src/.git" ]; then
    mkdir -p "$B/src"
    git -c advice.detachedHead=false clone --depth 1 --branch "$SHERPA_TAG" https://github.com/k2-fsa/sherpa-onnx.git "$src"
  fi
  [ "$(git -C "$src" rev-parse HEAD)" = "$SHERPA_COMMIT" ] || { echo "sherpa-onnx is not $SHERPA_TAG" >&2; exit 1; }
  say "sherpa-onnx $SHERPA_TAG = $SHERPA_COMMIT"
}

case ${1:-fetch} in
  fetch) fetch ;;
  lock) python3 -I "$here/make_lock.py" "$B" "${2:?usage: fetch.sh lock <LOCK.json>}" ;;
  *) echo "usage: fetch.sh [fetch | lock <LOCK.json>]" >&2; exit 2 ;;
esac
