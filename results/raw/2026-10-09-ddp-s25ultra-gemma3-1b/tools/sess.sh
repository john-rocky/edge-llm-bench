#!/bin/bash
# sess.sh <gpu|cpu>: one billed DDP session on pa3q-35, Gemma 3 1B IT int4 (litert-community gemma3-1b-it-int4.litertlm),
# --num-iterations 1 --warmup-runs 0 --max-num-tokens 4096. The bundle's LlmMetadata carries no max_num_tokens
# (peek/gemma3-1b-litertlm-peek-2026-10-09.txt), so the LiteRT team's Kotlin test gets the engine default, 4096 for a
# 1024-token prompt; the benchmark binary picks 1280 on its own when the flag is absent, so 4096 is passed explicitly.
# Other flags at the CLI defaults (prefill 1024 / decode 256).
C="$HOME/code/edge-llm-bench/results/raw/2026-10-09-ddp-s25ultra-gemma3-1b"
S="${SCRATCH:?set SCRATCH}"
V="$S/.venv-nightly"
M="$HOME/.cache/huggingface/hub/models--litert-community--Gemma3-1B-IT/snapshots/a6306a4e292016480083b73b8dc6f3f939ae04c3/gemma3-1b-it-int4.litertlm"
b="$1"; label="gemma3-1b-$b-iter1-max4096"
mkdir -p "$S/sessions"; out="$S/sessions/$label.$(date +%s).out"
RL_TAIL=400 "$C/tools/rl.sh" "billed DDP session: Gemma 3 1B IT int4 $b, --num-iterations 1 --warmup-runs 0 --max-num-tokens 4096 (prefill 1024 / decode 256 at the defaults)" \
  "source $V/bin/activate && LITERT_GCP_PROJECT=litert-edge-portal litert benchmark '$M' --ddp --device pa3q-35 --$b --num-iterations 1 --warmup-runs 0 --max-num-tokens 4096" > "$out" 2>&1
rc=$(grep -o '^exit=[0-9]*' "$out" | tail -1 | cut -d= -f2)
sid=$(grep -o "session-[0-9a-f]\{8\}" "$out" | head -1)
name=$(grep -o "litert-cli-benchmark-[0-9a-f]\{8\}" "$out" | head -1)
passed=$(grep -c "finished: PASSED" "$out")
printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$(TZ=Asia/Tokyo date '+%Y-%m-%d %H:%M:%S')" "$label" "$b" "1/4096" "${sid:-none}" "${name:-none}" "${rc:-?}" "passed=$passed" >> "$C/sessions.tsv"
echo "$out"
