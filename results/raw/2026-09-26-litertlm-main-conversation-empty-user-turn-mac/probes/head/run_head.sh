#!/bin/bash
# upstream/main head check: build the C API dylib and the CLI at 5e3bd637, run the ctypes probe and the CLI on the CPU.
export PATH=/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin
export GIT_LFS_SKIP_SMUDGE=1
S=/private/tmp/claude-501/-Users-majimadaisuke-code-edge-llm-bench/298ce1ca-383c-4dd7-939a-363aeef8d8bc/scratchpad/capi
W=~/code/litert-lm-bisect-wt
M=~/.cache/huggingface/hub/models--litert-community--Qwen3-0.6B/snapshots/a3c5d805ae362dff7f580bc25f2dfb9a5a7eaa76/qwen3_0_6b_mixed_int4.litertlm
L=$S/head/head.log
cd "$W" || exit 1
date '+%F %T start' > "$L"
git bisect reset >> "$L" 2>&1
git checkout --detach 5e3bd637 >> "$L" 2>&1
git rev-parse HEAD >> "$L"
PROV=prebuilt/macos_arm64/libGemmaModelConstraintProvider.dylib
cp ~/code/litert-lm-1dadd00c-wt/$PROV "$PROV"
echo "### CMD: bazelisk build //swift:CLiteRTLM_mac //runtime/engine:litert_lm_main   # upstream/main 5e3bd637 $(date '+%F %T %Z')" >> "$S/runlog.log"
bazelisk build //swift:CLiteRTLM_mac //runtime/engine:litert_lm_main > "$S/head/build_5e3bd637.log" 2>&1
echo "BUILD EXIT=$? $(date '+%T')" >> "$L"
rm -rf "$S/head/lib"; mkdir -p "$S/head/lib"; unzip -q -o bazel-bin/swift/CLiteRTLM_mac.zip -d "$S/head/lib"; cp "$PROV" "$S/head/lib/CLiteRTLM_mac/"
shasum -a 256 "$S/head/lib/CLiteRTLM_mac/libCLiteRTLM_mac.dylib" >> "$L"; ls -la "$S/head/lib/CLiteRTLM_mac/libCLiteRTLM_mac.dylib" >> "$L"
cd "$S"
echo "### CMD: python3 capi_render_probe.py head/lib/CLiteRTLM_mac/libCLiteRTLM_mac.dylib qwen3_0_6b_mixed_int4.litertlm   # $(date '+%F %T %Z') upstream/main 5e3bd637" >> "$S/runlog.log"
gtimeout 300 python3 capi_render_probe.py head/lib/CLiteRTLM_mac/libCLiteRTLM_mac.dylib "$M" 48 > head/head.probe.stdout.txt 2> head/head.probe.stderr.txt
echo "PROBE EXIT=$?" >> "$L"
echo "### CMD: python3 capi_render_shapes.py head/lib/CLiteRTLM_mac/libCLiteRTLM_mac.dylib qwen3_0_6b_mixed_int4.litertlm   # $(date '+%F %T %Z') upstream/main 5e3bd637" >> "$S/runlog.log"
gtimeout 300 python3 capi_render_shapes.py head/lib/CLiteRTLM_mac/libCLiteRTLM_mac.dylib "$M" > head/head.shapes.stdout.txt 2> head/head.shapes.stderr.txt
echo "SHAPES EXIT=$?" >> "$L"
cd "$W"
mkdir -p "$S/head/cli"; cp bazel-bin/runtime/engine/litert_lm_main "$S/head/cli/"; cp "$PROV" "$S/head/cli/"
git checkout -- "$PROV"
cd "$S/head/cli"
echo "### CMD: DYLD_LIBRARY_PATH=. ./litert_lm_main --backend cpu --model_path qwen3_0_6b_mixed_int4.litertlm --input_prompt \"Explain what on-device AI means in simple terms.\"   # $(date '+%F %T %Z') upstream/main 5e3bd637" >> "$S/runlog.log"
DYLD_LIBRARY_PATH=. gtimeout 600 ./litert_lm_main --backend cpu --model_path "$M" --input_prompt "Explain what on-device AI means in simple terms." > cli.stdout.txt 2> cli.stderr.txt
echo "CLI EXIT=$? $(date '+%T')" >> "$L"
date '+%F %T done' >> "$L"
