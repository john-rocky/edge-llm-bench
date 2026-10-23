#!/usr/bin/env bash
# Build litert_lm_main and litert_lm_advanced_main for android_arm64 at a tag or a git ref.
#
# LiteRT-LM releases ship no Android binary (verified v0.14.0/v0.15.0/v0.16.0/v0.17.0:
# assets are two xcframeworks + litert_lm_main.macos_arm64 only), so the Android
# arm is a per-release source build. The Maven litertlm-android AAR is the
# official artifact but exposes only the Kotlin API — no CLI — so using it would
# mean an instrumented APK harness (recorded as a phase-2 option in
# methodology/android.md).
#
# Prerequisites (owner machine, one-time):
#   - bazelisk (brew install bazelisk) — respects the checkout's .bazelversion
#   - Android NDK r28b+ (Android Studio SDK manager)
#   - git-lfs (the checkout's prebuilt/android_arm64/*.so are LFS objects)
#   - ~10-20 min and a few GB of bazel cache on first build per tag
#
# Env:
#   LITERTLM_TAG      tag to build (default: v0.17.0)
#   LITERTLM_REF      a git ref to build instead of a tag (not with LITERTLM_TAG): a commit sha
#                     (7-40 hex digits), a branch, or pr/<N> (the pull request's head). Its label
#                     names the output dir and the pins entry: main-<sha9> for a sha or the branch
#                     main, <branch with / as ->-<sha9> for another branch, pr<N>-<sha9> for a PR
#                     (sha9 = the first 9 hex digits of the commit git ls-remote resolves); a tag
#                     named here builds as LITERTLM_TAG does
#   LITERTLM_DRY_RUN  1: check the NDK and bazelisk, resolve the ref (git ls-remote; a short sha that
#                     is no ref's tip through the GitHub commits API), print label= / commit= / src= /
#                     out= and every command a build runs, then exit 0 having run none of them
#                     (nothing cloned, fetched, built or written)
#   ANDROID_NDK_HOME  NDK path (default: newest under ~/Library/Android/sdk/ndk)
#   LITERTLM_SRC      scratch clone dir (default: ~/.cache/apple-silicon-llm-bench/litert-lm-<label>)
#   LITERTLM_GPU_ACCELERATOR  prebuilt: empty the Android branches of runtime/executor:default_static_gpu_accelerator
#                     and runtime/components:default_static_gpu_samplers in the checkout, so the binaries load the
#                     checkout's prebuilt libLiteRtGpuAccelerator.so (and top-k sampler) at run time, the GPU path of
#                     the v0.18.0 build; the label gets -pregpu. Unset: as the checkout builds (main of 2026-10-23 links
#                     a GPU accelerator and sampler built from source into an Android binary)
#
# Output: android/bin/<label>/ = both tools, every prebuilt/android_arm64/*.so of the checkout,
# SHA256SUMS (the tools and the .so files) and BUILD_INFO (requested ref, label, commit, describe,
# commit date and subject, remote, NDK and bazel versions, build time, host arch; no home path), and
# the entry litert-lm.<label> in android/engine-pins.json, written by android/scripts/pins_add.py.
# A DDP run uses a build that is not android_pins' tag with `bench matrix --ddp <id> --engine-build
# <label>` (android/README.md, "Build from head or a PR").
#
# NOTE: this intentionally does NOT build inside ios/BenchmarkApp/Vendored/LiteRT-LM.
# That checkout is the iOS pin; bazel output there would pollute the vendored state.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
REMOTE="https://github.com/google-ai-edge/LiteRT-LM.git"
DRY_RUN="${LITERTLM_DRY_RUN:-}"
[[ "$DRY_RUN" != "0" ]] || DRY_RUN=""
LABEL_RE='^[A-Za-z0-9][A-Za-z0-9._-]*$'
PR_RE='^pr/([0-9]+)$'
SHA_RE='^[0-9a-fA-F]{7,40}$'
FULL_RE='^[0-9a-f]{40}$'

# what this script prints (and BUILD_INFO) carries the home dir as ~: a log or a record names no user
tilde() { printf '%s' "$*" | sed "s#$HOME#~#g"; }
no_home() { sed -E -e "s#$HOME#~#g" -e 's#/(Users|home)/[^/[:space:]]+#~#g'; }
# the words of a command as a shell would read them back (single quotes where needed)
quote_args() {
  local a out=""
  for a in "$@"; do
    case "$a" in
      "" | *[!A-Za-z0-9_./:=@%+,-]*) a="'$(printf '%s' "$a" | sed "s/'/'\\\\''/g")'" ;;
    esac
    out="$out $a"
  done
  printf '%s' "${out# }"
}
# a build step: printed, then run (a dry run prints it only)
run() {
  echo "+ $(tilde "$(quote_args "$@")")"
  [[ -n "$DRY_RUN" ]] || "$@"
}
run_in() {
  local dir="$1"; shift
  echo "+ (cd $(tilde "$(quote_args "$dir")") && $(tilde "$(quote_args "$@")"))"
  [[ -n "$DRY_RUN" ]] || (cd "$dir" && "$@")
}
# git ls-remote of the given refs (all refs with none), "<sha> <ref>" per line; a failure stops the script
ls_remote() {
  local out
  if ! out="$(git ls-remote "$REMOTE" "$@" 2>&1)"; then
    echo "ERROR: git ls-remote $REMOTE $*: $out" >&2
    return 1
  fi
  printf '%s\n' "$out"
}
# the commit of <ref> in ls-remote output: an annotated tag's peeled ^{} line first
sha_of() {
  printf '%s\n' "$1" | awk -v r="$2" '$2 == r "^{}" {p = $1} $2 == r {s = $1} END {print (p != "" ? p : s)}'
}
# the full sha GitHub's commits API gives for a short one (empty when it gives none)
github_commit() {
  local repo
  repo="$(printf '%s' "$REMOTE" | sed -n 's#^https://github\.com/\([^/]*/[^/]*\)\.git$#\1#p')"
  [[ -n "$repo" ]] || return 0
  curl -fsSL -H 'Accept: application/vnd.github+json' "https://api.github.com/repos/$repo/commits/$1" 2>/dev/null \
    | python3 -c 'import json, sys; print(json.load(sys.stdin).get("sha", ""))' 2>/dev/null || true
}

if [[ -n "${LITERTLM_TAG:-}" && -n "${LITERTLM_REF:-}" ]]; then
  echo "ERROR: LITERTLM_TAG=$LITERTLM_TAG and LITERTLM_REF=$LITERTLM_REF are both set: give one" \
       "(LITERTLM_TAG=<tag>, or LITERTLM_REF=<sha | branch | pr/N>)" >&2
  exit 1
fi
TAG="${LITERTLM_TAG:-}"
REF="${LITERTLM_REF:-}"
REF="${REF#refs/heads/}"
[[ -n "$TAG$REF" ]] || TAG="v0.17.0"

if [[ -z "${ANDROID_NDK_HOME:-}" ]]; then
  ANDROID_NDK_HOME="$(ls -d "$HOME"/Library/Android/sdk/ndk/* 2>/dev/null | sort -V | tail -1 || true)"
fi
[[ -n "$ANDROID_NDK_HOME" && -d "$ANDROID_NDK_HOME" ]] || {
  echo "ERROR: ANDROID_NDK_HOME not set and no NDK under ~/Library/Android/sdk/ndk" >&2; exit 1; }
export ANDROID_NDK_HOME
echo "== NDK: $(tilde "$ANDROID_NDK_HOME")"

command -v bazelisk >/dev/null || { echo "ERROR: bazelisk not installed (brew install bazelisk)" >&2; exit 1; }
command -v git >/dev/null || { echo "ERROR: git not installed" >&2; exit 1; }
[[ -n "$DRY_RUN" ]] || command -v python3 >/dev/null || {
  echo "ERROR: python3 not found (android/scripts/pins_add.py writes the pins entry after the build)" >&2; exit 1; }

# the label and the commit: a tag is its own label; a ref resolves to a commit first (git ls-remote),
# and git fetch takes a full object name only, so a short sha is resolved before the fetch as well
COMMIT=""
FETCH=""
RESOLVED=""
if [[ -n "$REF" ]]; then
  REQUESTED="$REF"
  if [[ "$REF" =~ $PR_RE ]]; then
    N="${BASH_REMATCH[1]}"
    FETCH="refs/pull/$N/head"
    LS="$(ls_remote "$FETCH")"
    COMMIT="$(sha_of "$LS" "$FETCH")"
    [[ -n "$COMMIT" ]] || { echo "ERROR: LITERTLM_REF=$REF: $REMOTE has no $FETCH" >&2; exit 1; }
    LABEL="pr$N-${COMMIT:0:9}"
    RESOLVED="git ls-remote $REMOTE $FETCH"
  elif [[ "$REF" =~ $SHA_RE ]]; then
    HEX="$(printf '%s' "$REF" | tr 'A-F' 'a-f')"
    if [[ ${#HEX} -eq 40 ]]; then
      COMMIT="$HEX"
      RESOLVED="a full sha (no lookup)"
    else
      LS="$(ls_remote)"
      COMMIT="$(printf '%s\n' "$LS" | awk -v p="$HEX" 'index($1, p) == 1 && !seen[$1]++ {n++; s = $1} END {if (n == 1) print s}')"
      RESOLVED="the tip of a ref (git ls-remote $REMOTE)"
      if [[ -z "$COMMIT" ]]; then
        COMMIT="$(github_commit "$HEX")"
        RESOLVED="the GitHub commits API (commits/$HEX)"
      fi
      [[ "$COMMIT" =~ $FULL_RE && "$COMMIT" == "$HEX"* ]] || {
        echo "ERROR: LITERTLM_REF=$REF: no single commit of $REMOTE starts with it (no ref's tip, and the" \
             "GitHub commits API gave none): give the full 40-digit sha" >&2; exit 1; }
    fi
    FETCH="$COMMIT"
    LABEL="main-${COMMIT:0:9}"
  else
    LS="$(ls_remote "refs/heads/$REF" "refs/tags/$REF" "refs/tags/$REF^{}")"
    COMMIT="$(sha_of "$LS" "refs/heads/$REF")"
    if [[ -n "$COMMIT" ]]; then
      FETCH="refs/heads/$REF"
      SAFE="$(printf '%s' "$REF" | tr -c 'A-Za-z0-9._-' '-' | sed 's/^[^A-Za-z0-9]*//')"
      LABEL="$SAFE-${COMMIT:0:9}"
      RESOLVED="git ls-remote $REMOTE $FETCH"
    else
      COMMIT="$(sha_of "$LS" "refs/tags/$REF")"
      [[ -n "$COMMIT" ]] || {
        echo "ERROR: LITERTLM_REF=$REF: $REMOTE has no branch or tag of that name (a sha is 7-40 hex" \
             "digits, a pull request is pr/<N>)" >&2; exit 1; }
      TAG="$REF"
      REF=""
      RESOLVED="git ls-remote $REMOTE refs/tags/$TAG (a tag: built as LITERTLM_TAG=$TAG)"
    fi
  fi
fi
if [[ -n "$TAG" ]]; then
  REQUESTED="$TAG"
  LABEL="$TAG"
  if [[ -n "$DRY_RUN" && -z "$COMMIT" ]]; then
    LS="$(ls_remote "refs/tags/$TAG" "refs/tags/$TAG^{}")"
    COMMIT="$(sha_of "$LS" "refs/tags/$TAG")"
    [[ -n "$COMMIT" ]] || { echo "ERROR: LITERTLM_TAG=$TAG: $REMOTE has no such tag" >&2; exit 1; }
    RESOLVED="git ls-remote $REMOTE refs/tags/$TAG"
  fi
fi
GPU_ACCEL="${LITERTLM_GPU_ACCELERATOR:-}"
case "$GPU_ACCEL" in
  "") ;;
  prebuilt) LABEL="$LABEL-pregpu" ;;
  *) echo "ERROR: LITERTLM_GPU_ACCELERATOR=$GPU_ACCEL: only prebuilt (or unset)" >&2; exit 1 ;;
esac
[[ "$LABEL" =~ $LABEL_RE ]] || {
  echo "ERROR: label '$LABEL' (from $REQUESTED) is not of the form $LABEL_RE" >&2; exit 1; }

SRC="${LITERTLM_SRC:-$HOME/.cache/apple-silicon-llm-bench/litert-lm-$LABEL}"
OUT="$REPO_ROOT/android/bin/$LABEL"
SO_SRC="$SRC/prebuilt/android_arm64"
echo "requested=$REQUESTED"
echo "label=$LABEL"
echo "commit=${COMMIT:-(the commit of the tag, read after the clone)}"
[[ -z "$RESOLVED" ]] || echo "resolved=$RESOLVED"
if [[ ! -d "$SRC/.git" ]]; then
  echo "src=$(tilde "$SRC")"
elif [[ -n "$TAG" ]]; then
  echo "src=$(tilde "$SRC") (exists: built as it is)"
else
  echo "src=$(tilde "$SRC") (exists: fetch + checkout only)"
fi
echo "out=$(tilde "$OUT")"

if [[ -n "$TAG" ]]; then
  if [[ ! -d "$SRC/.git" ]]; then
    echo "== cloning LiteRT-LM $TAG -> $(tilde "$SRC")"
    run mkdir -p "$(dirname "$SRC")"
    run git clone --depth 1 --branch "$TAG" "$REMOTE" "$SRC"
  fi
else
  echo "== fetching LiteRT-LM $REQUESTED ($COMMIT) -> $(tilde "$SRC")"
  if [[ ! -d "$SRC/.git" ]]; then
    run mkdir -p "$(dirname "$SRC")"
    run git init -q "$SRC"
    run git -C "$SRC" remote add origin "$REMOTE"
  fi
  # git-lfs (filter.lfs in the git config) smudges prebuilt/android_arm64/*.so at the checkout
  run git -C "$SRC" fetch --depth 1 origin "$FETCH"
  run git -C "$SRC" checkout -q --detach FETCH_HEAD
fi

if [[ -n "$DRY_RUN" ]]; then
  OBSERVED="<git describe --tags --always of the checkout>"
else
  HEAD_SHA="$(git -C "$SRC" rev-parse HEAD)"
  if [[ -n "$COMMIT" && "$HEAD_SHA" != "$COMMIT" ]]; then
    echo "ERROR: $(tilde "$SRC") is at $HEAD_SHA, not the $COMMIT that $REQUESTED named at git ls-remote" \
         "(it moved since?): run again" >&2
    exit 1
  fi
  COMMIT="$HEAD_SHA"
  OBSERVED="$(git -C "$SRC" describe --tags --always)"
  echo "== source at: $OBSERVED ($COMMIT)"
  [[ -z "$TAG" || "$OBSERVED" == "$TAG" ]] || echo "WARN: observed tag $OBSERVED != requested $TAG (recorded as-is in pins)"
  # GPU backend needs the accelerator .so set next to the binary on device (LD_LIBRARY_PATH=.);
  # checked before the build: pins_add.py refuses a build without it, and a git-lfs pointer
  shopt -s nullglob
  SOS=("$SO_SRC"/*.so)
  shopt -u nullglob
  [[ ${#SOS[@]} -gt 0 ]] || { echo "ERROR: no .so in $(tilde "$SO_SRC") (the GPU accelerator set): nothing to pin" >&2; exit 1; }
  for f in "${SOS[@]}"; do
    if [[ "$(head -c 23 "$f" | LC_ALL=C tr -d '\000')" == "version https://git-lfs" ]]; then
      echo "ERROR: $(tilde "$f") is a git-lfs pointer, not the library: git lfs install, then" \
           "git -C $(tilde "$SRC") lfs pull" >&2
      exit 1
    fi
  done
fi

echo "== bazel build (android_arm64) — first build takes 10-20 min"
# --enable_platform_specific_config: required on a macOS host — without it the
# rules_rust tool crates (thiserror etc.) fail with E0463 "can't find crate for
# thiserror_impl" because .bazelrc's `build:android` disables the host's
# build:macos config. Upstream: google-ai-edge/LiteRT-LM#3247.
# Both binaries: plain main runs prompt tasks (benchmark reporting is on by
# default); ONLY advanced_main consumes --benchmark_prefill_tokens /
# --benchmark_decode_tokens (verified in v0.16.0 sources — the plain main
# silently runs its default prompt instead), so synthetic PxD rows need it.
if [[ "$GPU_ACCEL" == "prebuilt" ]]; then
  # the Android branch of the select in runtime/executor/BUILD -> no statically linked GPU accelerator; the
  # registry then dlopens libLiteRtGpuAccelerator.so next to the binary (log: "Dynamically loaded GPU accelerator")
  run perl -0pi -e 's|("\@platforms//os:android": \[)\s*"\@litert//litert/runtime/accelerators/gpu:ml_drift_gpu_accelerator",\s*(\],)|$1$2|' \
    "$SRC/runtime/executor/BUILD"
  # and the static OpenCL top-k sampler, which is created from the static accelerator's device (runtime/components/BUILD:
  # default_static_gpu_samplers), so the sampler is the prebuilt libLiteRtTopKOpenClSampler.so as in the v0.18.0 build
  run perl -0pi -e 's|("\@platforms//os:android": \[)":top_k_opencl_sampler_static"(\],)|$1$2|' \
    "$SRC/runtime/components/BUILD"
  for b in runtime/executor/BUILD runtime/components/BUILD; do
    [[ -n "$DRY_RUN" ]] || grep -q '"@platforms//os:android": \[\],' "$SRC/$b" || {
      echo "ERROR: $b: the Android static GPU line was not found to empty" >&2; exit 1; }
  done
fi
run_in "$SRC" bazelisk build --config=android_arm64 --enable_platform_specific_config \
  //runtime/engine:litert_lm_main //runtime/engine:litert_lm_advanced_main

run mkdir -p "$OUT"
run cp -f "$SRC/bazel-bin/runtime/engine/litert_lm_main" "$OUT/litert_lm_main"
run cp -f "$SRC/bazel-bin/runtime/engine/litert_lm_advanced_main" "$OUT/litert_lm_advanced_main"
run chmod +x "$OUT/litert_lm_main" "$OUT/litert_lm_advanced_main"
if [[ -n "$DRY_RUN" ]]; then
  echo "+ cp -f $(tilde "$SO_SRC")/*.so $(tilde "$OUT")/"
  echo "+ (cd $(tilde "$OUT") && shasum -a 256 litert_lm_main litert_lm_advanced_main *.so | tee SHA256SUMS)"
  echo "+ BUILD_INFO -> $(tilde "$OUT")/BUILD_INFO (requested label commit describe commit_date subject remote ndk bazel bazelisk built host_arch)"
else
  run cp -f "${SOS[@]}" "$OUT/"
  (cd "$OUT" && shasum -a 256 litert_lm_main litert_lm_advanced_main *.so | tee SHA256SUMS)
  BAZEL_VERSION="$(cd "$SRC" && bazelisk version 2>/dev/null || true)"
  {
    echo "requested=$REQUESTED"
    echo "label=$LABEL"
    echo "commit=$COMMIT"
    echo "describe=$OBSERVED"
    echo "commit_date=$(git -C "$SRC" log -1 --format=%cI)"
    echo "subject=$(git -C "$SRC" log -1 --format=%s)"
    echo "remote=$REMOTE"
    echo "ndk=$(basename "$ANDROID_NDK_HOME")"
    echo "bazel=$(printf '%s\n' "$BAZEL_VERSION" | sed -n 's/^Build label: //p')"
    echo "bazelisk=$(printf '%s\n' "$BAZEL_VERSION" | sed -n 's/^Bazelisk version: v\{0,1\}//p')"
    echo "built=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "host_arch=$(uname -m)"
    echo "gpu_accelerator=${GPU_ACCEL:-as built (static from source on main of 2026-10-23)}"
  } | no_home > "$OUT/BUILD_INFO"
  cat "$OUT/BUILD_INFO"
fi

# Record the observed build (registry = requested tag or ref, witness = observed describe + sha256),
# same registry/witness convention as environment.lock.json engine_version_stamping; android_pins
# (the dashboard pin) is not touched: a pin bump is a person's decision (docs/OPERATIONS.md)
run python3 "$REPO_ROOT/android/scripts/pins_add.py" "$LABEL" "$OUT" --requested "$REQUESTED" \
  --observed "$OBSERVED" --note "android/scripts/build_litert_lm_main.sh at $LABEL (bazel source build, $(date +%Y-%m-%d); commit $COMMIT)" \
  --replace

if [[ -n "$DRY_RUN" ]]; then
  echo "== dry run: nothing cloned, fetched, built or written"
else
  echo "== done: $(tilde "$OUT")"
fi
