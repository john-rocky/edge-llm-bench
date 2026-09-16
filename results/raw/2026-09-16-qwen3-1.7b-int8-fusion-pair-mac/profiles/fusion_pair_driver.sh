#!/usr/bin/env bash
# Qwen3-1.7B int8: published unfused (CPU-recipe) file vs fused GPU-graph export (rope inlined), Mac Metal path, LiteRT-LM v0.17.0
set -u
SP=/private/tmp/claude-501/-Users-majimadaisuke-code-standup/ffaa944f-6fbb-429f-99ea-bdd2ec1fa608/scratchpad
RUN=$SP/run-metal-0170; MODELS=$SP/models
OUT=$HOME/code/edge-llm-bench/results/raw/2026-09-16-qwen3-1.7b-int8-fusion-pair-mac/profiles
mkdir -p "$RUN" "$MODELS" "$OUT"
SRC=/private/tmp/claude-501/-Users-majimadaisuke-code-litertlm-convert/6f688ea3-b666-4bfc-8dbf-b5728df4a11f/scratchpad/run-metal-0170
echo "### CMD: cp -c $SRC/{litert_lm_advanced_main,*.dylib} $RUN/  $(date +%F' '%T)" >> "$OUT/runlog.txt"
cp -c "$SRC"/litert_lm_advanced_main "$SRC"/*.dylib "$RUN"/ || { echo "COPY_RUN_FAILED"; exit 1; }
UNF=$HOME/.cache/huggingface/hub/models--litert-community--Qwen3-1.7B/snapshots/73fbc3fe8271c162a603ee66f6e7ed25b6211195/Qwen3_1.7B.litertlm
FUS=$HOME/code/litertlm-convert/qwen3_gpuopt_work/out/dtypeonly_1p7b_norope/wi8/Qwen3-1.7B_wi8_gpuflags_norope.litertlm
echo "### CMD: cp -cL $UNF $FUS $MODELS/  $(date +%F' '%T)" >> "$OUT/runlog.txt"
cp -cL "$UNF" "$MODELS"/Qwen3_1.7B.litertlm || cp -L "$UNF" "$MODELS"/Qwen3_1.7B.litertlm
cp -c "$FUS" "$MODELS"/ || cp "$FUS" "$MODELS"/
( cd "$RUN" && shasum -a 256 litert_lm_advanced_main *.dylib ) > "$OUT/sha256.txt"
( cd "$MODELS" && shasum -a 256 *.litertlm ) >> "$OUT/sha256.txt"
cp "$HOME/code/edge-llm-bench/results/raw/2026-09-16-minicpm5-2b-profile-mac/profiles/run_pair_metal.sh" "$OUT/"
cp "$HOME/code/edge-llm-bench/results/raw/2026-09-16-minicpm5-2b-profile-mac/profiles/gpu_nodes.py" "$OUT/"
export PROFILE_RUNLOG="$OUT/runlog.txt"
uptime >> "$OUT/runlog.txt"
bash "$OUT/run_pair_metal.sh" "$RUN" "$MODELS/Qwen3_1.7B.litertlm" litert-community_Qwen3-1.7B_int8-unfused-published_128x256_ctx1024 "$OUT" 60
sleep 60
bash "$OUT/run_pair_metal.sh" "$RUN" "$MODELS/Qwen3-1.7B_wi8_gpuflags_norope.litertlm" litert-local_Qwen3-1.7B_wi8_gpuflags_norope-fused_128x256_ctx1024 "$OUT" 60
uptime >> "$OUT/runlog.txt"
echo "DRIVER_DONE $(date +%F' '%T)" | tee -a "$OUT/runlog.txt"
