#!/bin/bash
# sess2048.sh <label> <model path>: one billed DDP cpu session on pa3q-35 with --max-num-tokens 2048 (the other flags at the CLI defaults).
S=/private/tmp/claude-501/-Users-USER-code-edge-llm-bench/5f1069b5-75f5-48a0-8cf8-e569a9902f1e/scratchpad
label="$1"; model="$2"
out="$S/sessions/$label-cpu-n2048.out"
RL_TAIL=400 "$S/tools/rl.sh" "billed DDP session: $label cpu, --max-num-tokens 2048 (prefill 1024, decode 256, 5 iterations at the defaults); the 1280 default fails to allocate on this bundle" \
  "source $S/.venv-nightly/bin/activate && LITERT_GCP_PROJECT=litert-edge-portal litert benchmark '$model' --ddp --device pa3q-35 --cpu --max-num-tokens 2048" > "$out" 2>&1
rc=$(grep -o '^exit=[0-9]*' "$out" | tail -1 | cut -d= -f2)
sid=$(grep -o "session-[0-9a-f]\{8\}" "$out" | head -1)
name=$(grep -o "litert-cli-benchmark-[0-9a-f]\{8\}" "$out" | head -1)
printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$(TZ=Asia/Tokyo date '+%Y-%m-%d %H:%M:%S')" "$label-n2048" "cpu" "1" "${sid:-none}" "${name:-none}" "${rc:-?}" >> "$S/sessions/sessions.tsv"
grep -v '^\.*$' "$out" | grep -v " [IWDV] [A-Za-z_.]* *: " | tail -8
