#!/bin/bash
# sess.sh <label> <backend: cpu|gpu> <model path or gs:// url> [attempt]: one billed DDP session on pa3q-35, logged to the run-log.
S=/private/tmp/claude-501/-Users-USER-code-edge-llm-bench/5f1069b5-75f5-48a0-8cf8-e569a9902f1e/scratchpad
label="$1"; backend="$2"; model="$3"; attempt="${4:-1}"
out="$S/sessions/$label-$backend-a$attempt.out"
mkdir -p "$S/sessions"
RL_TAIL=400 "$S/tools/rl.sh" "billed DDP session: $label $backend attempt $attempt, CLI defaults (prefill 1024, decode 256, max 1280, 5 iterations)" \
  "source $S/.venv-nightly/bin/activate && LITERT_GCP_PROJECT=litert-edge-portal litert benchmark '$model' --ddp --device pa3q-35 --$backend" > "$out" 2>&1
rc=$(grep -o '^exit=[0-9]*' "$out" | tail -1 | cut -d= -f2)
sid=$(grep -o "session-[0-9a-f]\{8\}" "$out" | head -1)
name=$(grep -o "litert-cli-benchmark-[0-9a-f]\{8\}" "$out" | head -1)
printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$(TZ=Asia/Tokyo date '+%Y-%m-%d %H:%M:%S')" "$label" "$backend" "$attempt" "${sid:-none}" "${name:-none}" "${rc:-?}" >> "$S/sessions/sessions.tsv"
grep -v '^\.*$' "$out" | tail -45
