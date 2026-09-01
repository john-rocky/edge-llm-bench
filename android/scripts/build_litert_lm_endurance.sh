#!/usr/bin/env bash
# Build the harness's endurance driver (android/native/litert_lm_endurance_main.cc)
# against a pristine LiteRT-LM checkout at the pinned tag, for android_arm64.
#
# Why this exists: the stock CLIs cannot run methodology/endurance.md —
# litert_lm_main is one message per process and --multi_turns is an
# interactive stdin loop with no rollover — so the Android lane needs the
# same thing the Mac lane already has in Swift: harness code driving the
# engine's Conversation API. The engine sources stay pristine (the driver is
# staged as a NEW bazel package, runtime/endurance/, never patched into
# upstream files); the produced binary sha256 AND the driver source sha256
# are recorded in android/engine-pins.json, so every row's witness discloses
# exactly which harness code measured it.
#
# Deliberately does NOT rebuild litert_lm_main/advanced_main: bazel outputs
# are not bit-reproducible across invocations, and overwriting the pinned,
# already-pushed binaries would break the registry/witness match for every
# existing row. This script only ADDS the endurance binary to android/bin/<tag>/.
#
# Prerequisites, env vars, and durations: identical to build_litert_lm_main.sh
# (bazelisk, NDK r28b+, ~10-20 min cold / minutes warm per tag).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TAG="${LITERTLM_TAG:-v0.16.0}"
SRC="${LITERTLM_SRC:-$HOME/.cache/apple-silicon-llm-bench/litert-lm-$TAG}"
OUT="$REPO_ROOT/android/bin/$TAG"
DRIVER_CC="$REPO_ROOT/android/native/litert_lm_endurance_main.cc"
DRIVER_BUILD="$REPO_ROOT/android/native/BUILD.endurance"

if [[ -z "${ANDROID_NDK_HOME:-}" ]]; then
  ANDROID_NDK_HOME="$(ls -d "$HOME"/Library/Android/sdk/ndk/* 2>/dev/null | sort -V | tail -1 || true)"
fi
[[ -n "$ANDROID_NDK_HOME" && -d "$ANDROID_NDK_HOME" ]] || {
  echo "ERROR: ANDROID_NDK_HOME not set and no NDK under ~/Library/Android/sdk/ndk" >&2; exit 1; }
export ANDROID_NDK_HOME
command -v bazelisk >/dev/null || { echo "ERROR: bazelisk not installed (brew install bazelisk)" >&2; exit 1; }

if [[ ! -d "$SRC/.git" ]]; then
  echo "== cloning LiteRT-LM $TAG -> $SRC"
  mkdir -p "$(dirname "$SRC")"
  git clone --depth 1 --branch "$TAG" https://github.com/google-ai-edge/LiteRT-LM.git "$SRC"
fi
OBSERVED="$(git -C "$SRC" describe --tags --always)"
echo "== source at: $OBSERVED"
[[ "$OBSERVED" == "$TAG" ]] || echo "WARN: observed tag $OBSERVED != requested $TAG (recorded as-is in pins)"
# The staged package lives outside upstream's tree of record; still verify we
# are not building on top of local modifications to ENGINE sources.
if ! git -C "$SRC" diff --quiet -- . ':!runtime/endurance' 2>/dev/null; then
  echo "ERROR: $SRC has local modifications to upstream sources — the witness would lie" >&2
  exit 1
fi

echo "== staging harness package runtime/endurance/ (upstream files untouched)"
mkdir -p "$SRC/runtime/endurance"
cp -f "$DRIVER_CC" "$SRC/runtime/endurance/litert_lm_endurance_main.cc"
cp -f "$DRIVER_BUILD" "$SRC/runtime/endurance/BUILD"

echo "== bazel build (android_arm64)"
# --enable_platform_specific_config: required on a macOS host (see
# build_litert_lm_main.sh; upstream google-ai-edge/LiteRT-LM#3247).
(cd "$SRC" && bazelisk build --config=android_arm64 --enable_platform_specific_config \
  //runtime/endurance:litert_lm_endurance_main)

mkdir -p "$OUT"
cp -f "$SRC/bazel-bin/runtime/endurance/litert_lm_endurance_main" "$OUT/litert_lm_endurance_main"
chmod +x "$OUT/litert_lm_endurance_main"

# Append the endurance fields to the tag's existing pins entry (witness:
# binary sha + the harness source sha it was built from).
python3 - "$REPO_ROOT" "$TAG" "$OBSERVED" "$OUT" "$DRIVER_CC" <<'PY'
import json, os, sys, hashlib
root, tag, observed, out, driver_cc = sys.argv[1:6]
pins_path = os.path.join(root, "android", "engine-pins.json")
pins = json.load(open(pins_path)) if os.path.exists(pins_path) else {}
def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()
entry = pins.setdefault("litert-lm", {}).setdefault(tag, {"requested_tag": tag})
entry["observed_endurance_build"] = observed
entry["litert_lm_endurance_main_sha256"] = sha(os.path.join(out, "litert_lm_endurance_main"))
entry["endurance_driver_source_sha256"] = sha(driver_cc)
entry["endurance_driver_note"] = (
    "harness driver (android/native/litert_lm_endurance_main.cc) compiled "
    "against pristine upstream sources at this tag; methodology/endurance.md")
json.dump(pins, open(pins_path, "w"), indent=2)
print(f"pins updated: {pins_path}")
PY

(cd "$OUT" && shasum -a 256 litert_lm_endurance_main)
echo "== done: $OUT/litert_lm_endurance_main"
