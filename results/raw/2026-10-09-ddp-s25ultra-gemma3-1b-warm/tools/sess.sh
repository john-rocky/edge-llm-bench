#!/bin/bash
# sess.sh cpu: one billed DDP session on pa3q-35, Gemma 3 1B IT int4 (litert-community gemma3-1b-it-int4.litertlm),
# --num-iterations 2 --warmup-runs 0 --max-num-tokens 4096, through tools/litert_warm2.py (the CLI with the first
# process's appended --num_iterations=1 changed to 2, so both processes run two cycles). Other flags at the CLI
# defaults (prefill 1024 / decode 256). Same venv, binary and bundle as results/raw/2026-10-09-ddp-s25ultra-gemma3-1b.
C="$HOME/code/edge-llm-bench/results/raw/2026-10-09-ddp-s25ultra-gemma3-1b-warm"
S="${SCRATCH:?set SCRATCH}"
V="${VENV:?set VENV}"
M="$HOME/.cache/huggingface/hub/models--litert-community--Gemma3-1B-IT/snapshots/a6306a4e292016480083b73b8dc6f3f939ae04c3/gemma3-1b-it-int4.litertlm"
b="$1"; label="gemma3-1b-$b-iter2x2-max4096"
mkdir -p "$S/sessions"; out="$S/sessions/$label.$(date +%s).out"
RL_TAIL=400 "$C/tools/rl.sh" "billed DDP session: Gemma 3 1B IT int4 $b, both processes --num_iterations=2 (tools/litert_warm2.py), --warmup-runs 0 --max-num-tokens 4096 (prefill 1024 / decode 256 at the defaults)" \
  "source $V/bin/activate && LITERT_GCP_PROJECT=litert-edge-portal python3 $C/tools/litert_warm2.py benchmark '$M' --ddp --device pa3q-35 --$b --num-iterations 2 --warmup-runs 0 --max-num-tokens 4096" > "$out" 2>&1
rc=$(grep -o '^exit=[0-9]*' "$out" | tail -1 | cut -d= -f2)
sid=$(grep -o "session-[0-9a-f]\{8\}" "$out" | head -1)
name=$(grep -o "litert-cli-benchmark-[0-9a-f]\{8\}" "$out" | head -1)
passed=$(grep -c "finished: PASSED" "$out")
printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$(TZ=Asia/Tokyo date '+%Y-%m-%d %H:%M:%S')" "$label" "$b" "2x2/4096" "${sid:-none}" "${name:-none}" "${rc:-?}" "passed=$passed" >> "$C/sessions.tsv"
echo "$out"
