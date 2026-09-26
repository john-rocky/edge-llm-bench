#!/bin/bash
# git bisect run step: build //swift:CLiteRTLM_mac at HEAD, render the Swift-package message shape
# through the C API, exit 0 (good: prompt text present), 1 (bad: empty user turn), 125 (skip: build failed).
export PATH=/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin
export GIT_LFS_SKIP_SMUDGE=1
W=~/code/litert-lm-bisect-wt
S=/private/tmp/claude-501/-Users-majimadaisuke-code-edge-llm-bench/298ce1ca-383c-4dd7-939a-363aeef8d8bc/scratchpad/capi
M=~/.cache/huggingface/hub/models--litert-community--Qwen3-0.6B/snapshots/a3c5d805ae362dff7f580bc25f2dfb9a5a7eaa76/qwen3_0_6b_mixed_int4.litertlm
cd "$W" || exit 125
h=$(git rev-parse --short HEAD)
echo "$(date '+%T') $h start" >> "$S/bisect/bisect.log"
PROV=prebuilt/macos_arm64/libGemmaModelConstraintProvider.dylib
cp ~/code/litert-lm-1dadd00c-wt/$PROV "$PROV"
echo "### CMD: bazelisk build //swift:CLiteRTLM_mac   # bisect step at $h $(date '+%F %T %Z')" >> "$S/runlog.log"
if ! bazelisk build //swift:CLiteRTLM_mac > "$S/bisect/build_$h.log" 2>&1; then
  echo "$(date '+%T') $h BUILD-FAIL" >> "$S/bisect/bisect.log"; git checkout -- "$PROV"; exit 125
fi
rm -rf "$S/bisect/lib_$h"; mkdir -p "$S/bisect/lib_$h"
unzip -q -o bazel-bin/swift/CLiteRTLM_mac.zip -d "$S/bisect/lib_$h"
cp "$PROV" "$S/bisect/lib_$h/CLiteRTLM_mac/"
git checkout -- "$PROV"
out=$(gtimeout 300 python3 "$S/capi_render_shapes.py" "$S/bisect/lib_$h/CLiteRTLM_mac/libCLiteRTLM_mac.dylib" "$M" 2> "$S/bisect/probe_$h.stderr.txt")
printf '%s\n' "$out" > "$S/bisect/probe_$h.stdout.txt"
if printf '%s\n' "$out" | grep -qF 'array_text: render="<|im_start|>user\nExplain what on-device AI'; then
  echo "$(date '+%T') $h GOOD" >> "$S/bisect/bisect.log"; exit 0
elif printf '%s\n' "$out" | grep -qF 'array_text: render="<|im_start|>user\n<|im_end|>'; then
  echo "$(date '+%T') $h BAD" >> "$S/bisect/bisect.log"; exit 1
else
  echo "$(date '+%T') $h PROBE-UNCLEAR" >> "$S/bisect/bisect.log"; exit 125
fi
