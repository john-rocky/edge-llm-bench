#!/bin/bash
# sess-aligned.sh <gpu|cpu>: one billed DDP session on pa3q-35, Gemma 4 E2B, --num-iterations 1 --warmup-runs 0 --max-num-tokens 4096
# (the LiteRT team's Kotlin test allocates the engine default, 4096 when the bundle carries no limit; the benchmark
# binary picks 1280 on its own when the flag is absent, so 4096 is passed explicitly). Other flags at the CLI defaults.
S=/private/tmp/claude-501/-Users-USER-code-edge-llm-bench/d21f53ca-5923-4da1-b5fc-7e34ecbf7034/scratchpad/r5
V=/private/tmp/claude-501/-Users-USER-code-edge-llm-bench/5f1069b5-75f5-48a0-8cf8-e569a9902f1e/scratchpad/.venv-nightly
M=/Users/USER/.cache/huggingface/hub/models--litert-community--gemma-4-E2B-it-litert-lm/snapshots/b3ca0d2f076785a8f4b2219ddbd2bdb99954eae1/gemma-4-E2B-it.litertlm
b="$1"; label="gemma-4-e2b-$b-iter1-max4096"
out="$S/sessions/$label.out"
RL_TAIL=400 "$S/tools/rl-aligned.sh" "billed DDP session: Gemma 4 E2B $b, --num-iterations 1 --warmup-runs 0 --max-num-tokens 4096 (prefill 1024 / decode 256 at the defaults)" \
  "source $V/bin/activate && LITERT_GCP_PROJECT=litert-edge-portal litert benchmark '$M' --ddp --device pa3q-35 --$b --num-iterations 1 --warmup-runs 0 --max-num-tokens 4096" > "$out" 2>&1
rc=$(grep -o '^exit=[0-9]*' "$out" | tail -1 | cut -d= -f2)
sid=$(grep -o "session-[0-9a-f]\{8\}" "$out" | head -1)
name=$(grep -o "litert-cli-benchmark-[0-9a-f]\{8\}" "$out" | head -1)
printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$(TZ=Asia/Tokyo date '+%Y-%m-%d %H:%M:%S')" "$label" "$b" "1/4096" "${sid:-none}" "${name:-none}" "${rc:-?}" >> "$S/sessions/sessions-aligned.tsv"
grep -v '^\.*$' "$out" | grep -v " [IWDV] [A-Za-z_.]* *: " | tail -12
